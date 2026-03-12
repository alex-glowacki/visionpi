#!/usr/bin/env python3
# vision/detect_model1.py
"""
Model 1: single-pipeline inference.

Publishes /detect (RTSP) AND writes /tmp/detections.json atomically.

- Input:     rtsp://127.0.0.1:8554/stream
- Output:    rtsp://127.0.0.1:8554/detect
- JSON:     /tmp/detections.json

Requires:
- hailonet, hailofilter, hailooverlay Gstreamer plugins
- hailo Python bindings (import hailo)
"""

from __future__ import annotations

import json
import os
import tempfile
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
    width: int = 1280
    height: int = 720
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

        self.loop = GLib.MainLoop()
        self.pipeline = Gst.parse_launch(self._pipeline_str())

        self.appsink = self.pipeline.get_by_name("json_sink")
        if self.appsink is None:
            raise RuntimeError("appsink 'json_sink' not found in pipeline")
        self.appsink.connect("new-sample", self._on_new_sample)

        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self._on_bus_message)

    def _pipeline_str(self) -> str:
        s = self.s
        return (
            f'rtspsrc location="{s.input_uri}" latency=100 protocols=tcp ! '
            f'rtph264depay ! h264parse ! avdec_h264 ! '
            f'videoconvert ! videoscale ! '
            f'video/x-raw,format=RGB,width={s.width},height={s.height},framerate={s.fps} ! '
            f'queue ! '
            f'hailonet hef-path="{s.hef_path}" batch-size=1 ! '
            f'queue ! '
            f'hailofilter so-path="{s.post_so}" function-name={s.post_fn} ! '
            f'tee name=t '
            # Branch 1: JSON tap
            f't. ! queue ! appsink name=json_sink emit-signals=true sync=false '
            f'max-buffers=1 drop=true '
            # Branch 2: Overlay + publish /detect
            f't. ! queue ! hailooverlay ! '
            f'videoconvert ! video/x-raw,format=I420 ! '
            f'x264enc tune=zerolatency bitrate={s.bitrate_kbps} speed-preset=ultrafast '
            f'key-int-max=30 bframes=0 byte-stream=true ! '
            f'h264parse config-interval=1 ! '
            f'rtspclientsink location="{s.output_uri}"'
        )

    def _on_new_sample(self, sink: Gst.Element) -> Gst.FlowReturn:
        sample = sink.emit("pull-sample")
        if sample is None:
            return Gst.FlowReturn.OK

        buf = sample.get_buffer()
        if buf is None:
            return Gst.FlowReturn.OK

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
            "image": {"width": self.s.width, "height": self.s.height, "format": "RGB"},
            "source": {"input": self.s.input_uri, "output": self.s.output_uri},
            "detections": detections_out,
        }
        self.frame_id += 1

        atomic_write_json(self.s.out_json, payload)
        return Gst.FlowReturn.OK

    def _on_bus_message(self, bus: Gst.Bus, msg: Gst.Message) -> None:
        t = msg.type
        if t == Gst.MessageType.ERROR:
            err, dbg = msg.parse_error()
            print(f"[GST][ERROR] {err} debug={dbg}")
            self.stop()
        elif t == Gst.MessageType.EOS:
            print("[GST] EOS")
            self.stop()

    def run(self) -> None:
        self.pipeline.set_state(Gst.State.PLAYING)
        print("[MODEL1] Running: /stream → detect+overlay → /detect AND /tmp/detections.json")
        try:
            self.loop.run()
        except KeyboardInterrupt:
            print("\n[MODEL1] Ctrl+C")
        finally:
            self.stop()

    def stop(self) -> None:
        try:
            self.pipeline.set_state(Gst.State.NULL)
        except Exception:
            pass
        try:
            if self.loop.is_running():
                self.loop.quit()
        except Exception:
            pass


def main() -> None:
    Gst.init(None)
    app = DetectModel1(Settings())
    app.run()


if __name__ == "__main__":
    main()