#!/usr/bin/env python3
# motors/driver_base.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


def clamp(x: float, lo: float, hi: float) -> float:
    """Clamp x into [lo, hi]."""
    return lo if x < lo else hi if x > hi else x


@dataclass(frozen=True)
class TrackCommand:
    """Convenience type for track commands in normalized range [-1..+1]."""
    left: float
    right: float
    
    
class MotorDriver(Protocol):
    """
    Interface for anything that can drive the robot's left/right tracks.
    
    Values are normalized speed in [-1..+1]:
        -1.0    = full reverse
        0.0     = stop
        +1.0    = full forward
    """
    
    def set_tracks(self, left: float, right: float) -> None:
        """Set track speeds in range [-1..+1]."""
        
    def stop(self) -> None:
        """Stop both tracks immediately."""