#!/usr/bin/env python3
# vision/detect_to_json.py
"""
Publishes Hailo detection metadata to /tmp/detections.json for the autonomy layer.

Run inside venv_hailo_apps:
    source ~/hailo-apps/venv_hailo_apps/bin/activate
    python3 -u vision/detect_to_json.py
    
Monitor output:
    watch -n 0.2 'ls -lah /tmp/detections.json; echo; head -n 15 /tmp/detections.json'
"""

import sys
import json
import os
import tempfile
import time
from typing import Any, Dict, List, Optional

# Force hailo-apps to use RTSP input even when started as a service.
if "--input" not in sys.argv:
    sys.argv += ["--input", "rtsp://127.0.0.1:8554/stream"]
    
import gi
gi.require_version("Gst", "1.0")
from gi.repository import Gst

import hailo

from hailo_apps.python.pipeline_apps.detection.detection_pipeline import GStreamerDetectionApp
from hailo_apps.python.core.common.buffer_utils import get_caps_from_pad
from hailo_apps.python.core.common.hailo_logger import get_logger
from hailo_apps.python.core.gstreamer.gstreamer_app import app_callback_class

hailo_logger = get_logger(__name__)

# Force RTSP output instead of a local video sink.
os.environ["GST_VIDEO_SINK"] = (
    "videoconvert ! "
    "video/x-raw,format=I420 ! "
    "x264enc tune=zerolatency bitrate=3000 speed-preset=ultrafast "
    "key-int-max=30 bframes=0 byte-stream=true ! "
    "h264parse config-interval=1 ! "
    "rtspclientsink location=rtsp://127.0.0.1:8554/detect protocols=tcp"
)

OUT_PATH = "/tmp/detections.json"
WRITE_EVERY_N_FRAMES = 5
_last_write_frame = 1


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
        
        
def _clamp01(v: float) -> float:
    return 0.0 if v < 0.0 else 1.0 if v > 1.0 else v


def bbox_to_dict(det: Any) -> Optional[Dict[str, float]]:
    """Best-effort normalized bbox extraction from a Hailo detection object."""
    try:
        bbox = det.get_bbox()
    except Exception:
        return None
    
    if bbox is None:
        return None
    
    # Try method-call form first
    for names in (("xmin", "ymin", "width", "height"), ("x", "y", "w", "h")):
        a, b, c, d = names
        try:
            fa, fb, fc, fd = getattr(bbox, a), getattr(bbox, b), getattr(bbox, c), getattr(bbox, d)
            if all(callable(x) for x in (fa, fb, fc, fd)):
                return {
                    "x": _clamp01(float(fa())),
                    "y": _clamp01(float(fb())),
                    "w": _clamp01(float(fc())),
                    "h": _clamp01(float(fd())),
                }
        except Exception:
            pass
        
    # Then attribute form
    for names in (("xmin", "ymin", "width", "height"), ("x", "y", "w", "h")):
        a, b, c, d = names
        try:
            if all(hasattr(bbox, k) for k in (a, b, c, d)):
                return {
                    "x": _clamp01(float(getattr(bbox, a))),
                    "y": _clamp01(float(getattr(bbox, b))),
                    "w": _clamp01(float(getattr(bbox, c))),
                    "h": _clamp01(float(getattr(bbox, d))),
                }
        except Exception:
            pass
        
    return None


class UserJSONCallbackData(app_callback_class):
    def __init__(self) -> None:
        super().__init__()
        self.use_frame = False      # prevent any OpenCV/UI code paths
        
        
def app_callback(element, buffer, user_data: UserJSONCallbackData):
    if buffer is None:
        hailo_logger.warning("Received None buffer.")
        return
    
    frame_idx = int(user_data.get_count())
    
    pad = element.get_static_pad("src")
    fmt, width, height = get_caps_from_pad(pad)
    
    roi = hailo.get_roi_from_buffer(buffer)
    detections = roi.get_objects_typed(hailo.HAILO_DETECTION)
    
    det_list: List[Dict[str, Any]] = []
    for det in detections:
        try:
            label = det.get_label()
        except Exception:
            label = None
            
        try:
            confidence = float(det.get_confidence())
        except Exception:
            confidence = None
            
        track_id = 0
        try:
            track = det.get_objects_typed(hailo.HAILO_UNIQUE_ID)
            if len(track) == 1:
                track_id = int(track[0].get_id())
        except Exception:
            pass
        
        det_list.append({
            "track_id": track_id,
            "label": label,
            "confidence": confidence,
            "bbox": bbox_to_dict(det),
        })
        
    payload: Dict[str, Any] = {
        "ts": time.time(),
        "frame_id": frame_idx,
        "image": {"width": width, "height": height, "format": fmt},
        "detections": det_list,
    }
    
    global _last_write_frame
    if (frame_idx % WRITE_EVERY_N_FRAMES) == 0 and frame_idx != _last_write_frame:
        atomic_write_json(OUT_PATH, payload)
        _last_write_frame = frame_idx
        print(
            f"[detect_to_json] wrote {OUT_PATH} "
            f"frame_id={frame_idx} ts={payload['ts']}",
            flush=True,
        )
        

def main() -> None:
    hailo_logger.info("Starting Detection → JSON (visionpi-robot).")
    user_data = UserJSONCallbackData()
    app = GStreamerDetectionApp(app_callback, user_data)
    app.run()
    

if __name__ == "__main__":
    Gst.init(None)
    main()