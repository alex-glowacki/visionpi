#!/usr/bin/env python3
# vision/detect_model1.py
"""
Model 1: single-pipeline inference.

Writes /tmp/detections.json atomically on each inference frame.

- Input:     rtsp://127.0.0.1:8554/stream
- JSON:      /tmp/detections.json

Requires:
- hailonet, hailofilter, hailooverlay GStreamer plugins
- hailo Python bindings (import hailo)
"""

from __future__ import annotations

import json
import os
import signal
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import gi
gi.require_version("Gst", "1.0")
from gi.repository import Gst, GLib

import hailo


@dataclass
class Settings:
    input_uri: str = "rtsp://127.0.0.1:8554/stream"
    output_uri: str = "rtsp://127.0.0.1:8554/detect"
    out_json: str = "/tmp/detections.json"
    infer_width: int = 640
    infer_height: int = 640
    fps: str = "30/1"
    bitrate_kbps: int = 3000
    hef_path: str = "/usr/local/hailo/resources/models/hailo10h/yolov8m.hef"
    post_so: str = "/usr/local/hailo/resources/so/libyolo_hailortpp_postprocess.so"
    post_fn: str = "filter_letterbox"
    min_conf: float = 0.25


def atomic_write_json(path: str, payload: Dict[str, Any]) -> None:
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".detections.", dir=d)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(payload, f, indent=2)
        os.replace(tmp_path, path)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass


def bbox_to_dict(det: Any) -> Optional[Dict[str, float]]:
    try:
        bbox = det.get_bbox()
    except Exception:
        return None
    if bbox is None:
        return None
    try:
        return {
            "x": float(bbox.xmin()),
            "y": float(bbox.ymin()),
            "w": float(bbox.width()),
            "h": float(bbox.height()),
        }
    except Exception:
        return None


class DetectModel1:
    def __init__(self, s: Settings) -> None:
        self.s = s
        self.frame_id = 0
        self._running = False
        self.loop: Optional[GLib.MainLoop] = None

        self.pipeline = Gst.parse_launch(self._pipeline_str())

        self.appsink = self.pipeline.get_by_name("json_sink")
        if self.appsink is None:
            raise RuntimeError("appsink 'json_sink' not found in pipeline")

    def _pipeline_str(self) -> str:
        s = self.s
        return (
            # TCP transport required — MediaMTX must have rtspTransport: tcp in mediamtx.yml
            f'rtspsrc location="{s.input_uri}" protocols=tcp latency=0 is-live=true ! '
            f'rtph264depay ! h264parse ! avdec_h264 ! '
            f'videoconvert ! videoscale ! '
            f'video/x-raw,format=RGB,width={s.infer_width},height={s.infer_height},framerate={s.fps} ! '
            # hailonet: force-writable=true required for linking; queue is AFTER, not before
            f'hailonet hef-path="{s.hef_path}" batch-size=1 force-writable=true ! '
            f'queue ! '
            f'hailofilter so-path="{s.post_so}" function-name={s.post_fn} ! '
            f'tee name=t '
            # Branch 1: JSON appsink tap
            f't. ! queue ! appsink name=json_sink emit-signals=false sync=false '
            f'max-buffers=1 drop=true '
            # Branch 2: fakesink (temporary — replace with RTSP output once JSON confirmed)
            f't. ! queue ! fakesink'
        )

    def _process_sample(self, sample: Any) -> None:
        buf = sample.get_buffer()
        if buf is None:
            return

        detections_out: List[Dict[str, Any]] = []

        try:
            roi = hailo.get_roi_from_buffer(buf)
            dets = roi.get_objects_typed(hailo.HAILO_DETECTION)
        except Exception:
            dets = []

        for det in dets:
            try:
                label = det.get_label()
            except Exception:
                label = ""
            try:
                conf = float(det.get_confidence())
            except Exception:
                conf = 0.0
            if conf < self.s.min_conf:
                continue

            track_id = 0
            try:
                u = det.get_objects_typed(hailo.HAILO_UNIQUE_ID)
                if len(u) == 1:
                    track_id = int(u[0].get_id())
            except Exception:
                pass

            detections_out.append({
                "track_id": track_id,
                "label": label,
                "confidence": conf,
                "bbox": bbox_to_dict(det),
            })

        payload = {
            "ts": time.time(),
            "frame_id": self.frame_id,
            "image": {
                "width": self.s.infer_width,
                "height": self.s.infer_height,
                "format": "RGB",
            },
            "source": {"input": self.s.input_uri, "output": self.s.output_uri},
            "detections": detections_out,
        }
        self.frame_id += 1

        atomic_write_json(self.s.out_json, payload)
        print(
            f"[MODEL1] wrote frame_id={self.frame_id} "
            f"detections={len(detections_out)}",
            flush=True,
        )

    def _on_bus_message(self, bus: Gst.Bus, msg: Gst.Message) -> None:
        t = msg.type
        if t == Gst.MessageType.ERROR:
            err, dbg = msg.parse_error()
            print(f"[GST][ERROR] {err} debug={dbg}", file=sys.stderr, flush=True)
            self.stop()
        elif t == Gst.MessageType.EOS:
            print("[GST] EOS", flush=True)
            self.stop()
        elif t == Gst.MessageType.ASYNC_DONE:
            print("[GST] async-done (pipeline fully running)", flush=True)
        elif t == Gst.MessageType.STATE_CHANGED:
            if msg.src == self.pipeline:
                old, new, _ = msg.parse_state_changed()
                print(
                    f"[GST] pipeline state: "
                    f"{old.value_nick} → {new.value_nick}",
                    flush=True,
                )

    def run(self) -> None:
        signal.signal(signal.SIGTERM, lambda _sig, _frame: self.stop())

        context = GLib.MainContext.default()
        self.loop = GLib.MainLoop(context)

        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self._on_bus_message)

        self.pipeline.set_state(Gst.State.PLAYING)

        print(
            f"[MODEL1] Running: {self.s.input_uri} → "
            f"inference ({self.s.infer_width}×{self.s.infer_height}) → "
            f"{self.s.out_json}",
            flush=True,
        )

        self._running = True

        def _appsink_poll() -> None:
            while self._running:
                sample = self.appsink.emit("try-pull-sample", 100 * Gst.MSECOND)
                if sample is not None:
                    self._process_sample(sample)

        poll_thread = threading.Thread(target=_appsink_poll, daemon=True)
        poll_thread.start()

        try:
            self.loop.run()
        except KeyboardInterrupt:
            print("\n[MODEL1] Ctrl+C — shutting down", flush=True)
        finally:
            self._running = False
            poll_thread.join(timeout=2.0)
            self.stop()

    def stop(self) -> None:
        self._running = False
        try:
            self.pipeline.set_state(Gst.State.NULL)
        except Exception:
            pass
        try:
            if self.loop and self.loop.is_running():
                self.loop.quit()
        except Exception:
            pass


def main() -> None:
    Gst.init(None)
    app = DetectModel1(Settings())
    app.run()


if __name__ == "__main__":
    main()