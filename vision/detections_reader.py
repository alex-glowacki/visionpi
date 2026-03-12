#!/usr/bin/env python3
# vision/detections_reader.py

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class Detection:
    track_id: int
    label: str
    confidence: float
    # Normalized bbox (0..1) as written by the vision pipelines
    x: float
    y: float
    w: float
    h: float
    
    
@dataclass
class DetectionFrame:
    ts: float
    frame_id: int
    width: int
    height: int
    detections: List[Detection]
    
    
class DetectionsReader:
    """
    Reads /tmp/detections.json written aromically by the vision pipeline.
    
    Uses simple polling - low overhead, suitable for robotics prototypes.
    
    Returns None if the file doesn't exist, can't be parsed, or contains
    the same frame_id as the last successful read (no new frame yet).
    """
    
    def __init__(self, path: str = "/tmp/detections.json") -> None:
        self.path = Path(path)
        self._last_frame_id: Optional[int] = None
        
    def read_latest(self) -> Optional[DetectionFrame]:
        if not self.path.exists():
            return None
        
        try:
            raw = self.path.read_text()
            payload = json.loads(raw)
        except Exception:
            # File may be mid-write or invalid; trad as "no new frame".
            return None
        
        try:
            frame_id = int(payload.get("frame_id", -1))
            if self._last_frame_id is not None and frame_id == self._last_frame_id:
                return None
            self._last_frame_id = frame_id
            
            img = payload.get("image") or {}
            width = int(img.get("width", 0))
            height = int(img.get("height", 0))
            
            dets: List[Detection] = []
            for d in payload.get("detections") or []:
                bbox = d.get("bbox") or {}
                dets.append(
                    Detection(
                        track_id=int(d.get("track_id", 0)),
                        label=str(d.get("label", "")),
                        confidence=float(d.get("confidence", 0.0)),
                        x=float(bbox.get("x", 0.0)),
                        y=float(bbox.get("y", 0.0)),
                        w=float(bbox.get("w", 0.0)),
                        h=float(bbox.get("h", 0.0)),
                    )
                )
                
            return DetectionFrame(
                ts=float(payload.get("ts", time.time())),
                frame_id=frame_id,
                width=width,
                height=height,
                detections=dets,
            )
        except Exception:
            return None