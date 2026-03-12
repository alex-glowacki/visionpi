#!/usr/bin/env python3
# motors/mock_driver.py

from __future__ import annotations

import time
from typing import Optional

from motors.driver_base import clamp


class MockMotorDriver:
    """
    Safe motor driver for development and testing.
    
    Implements the MotorDriver interface (set_tracks + stop) without any
    hardware. Prints commands at a limited rate so the terminal isn't spammed.
    Inputs are clamped to [-1..+1].
    
    State (_last_left, _last_right) is always updated regardless of the
    print throttle, so it can be inspected reliably in tests.
    """
    
    def __init__(self, print_hz: float = 10.0) -> None:
        self._min_dt = 1.0 / max(1e-6, float(print_hz))
        self._last_print = 0.0
        self._last_left: Optional[float] = None
        self._last_right: Optional[float] = None
        
    def set_tracks(self, left: float, right: float) -> None:
        left = clamp(left, -1.0, 1.0)
        right = clamp(right, -1.0, 1.0)
        
        now = time.monotonic()
        
        changed = (
            self._last_left is None
            or self._last_right is None
            or abs(left - self._last_left) > 0.02
            or abs(right - self._last_right) > 0.02
        )
        
        # Always track current command regardless of print throttle.
        self._last_left = left
        self._last_right = right
        
        # Only print when value changed meaningfully AND enough time has passed.
        if changed and (now - self._last_print) >= self._min_dt:
            print(f"[MOTORS] left={left:+.2f} right={right:+.2f}")
            self._last_print = now
        
    def stop(self) -> None:
        self.set_tracks(0.0, 0.0)