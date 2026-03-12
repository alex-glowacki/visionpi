#!/usr/bin/env python3
# motors/real_driver.py

from __future__ import annotations

import time
from typing import Optional

from motors.driver_base import clamp

try:
    import serial
    from serial.tools import list_ports
except ImportError as e:
    raise ImportError(
        "pyserial is required for real hardware. "
        "Install with: pip install -e '.[dev]'"
    ) from e
    

def _auto_detect_port() -> str:
    """
    Hueristically pick the most likely Nano port from all available serial ports.
    Scoring: Arduino descriptor > 'nano' in description > ACM device > USB device.
    """
    ports = list(list_ports.comports())
    if not ports:
        raise RuntimeError("No serial ports found. Is the Nano plugged in?")
    
    scored = []
    for p in ports:
        desc = (p.description or "").lower()
        hwid = (p.hwid or "").lower()
        dev = (p.device or "").lower()
        
        score = 0
        if "arduino" in desc or "arduino" in hwid:
            score += 5
        if "nano" in desc:
            score += 3
        if "acm" in dev:
            score += 3
        if "usb" in dev:
            score += 1
        
        scored.append((score, p.device))
        
    scored.sort(key=lambda x: -x[0])
    return scored[0][1]


class RealMotorDriver:
    """
    Sends ``left,right\\n`` commands to the Arduino Nano R4 over USB serial.
    
    Values must be in [-1.0, +1.0]. The Nano enforces its own safety stops
    (LiDAR, tilt, host timeout) independently of this driver.
    
    LiDAR telemetry is parsed from Nano debug lines so upstream code can
    optionally read distance values via :attr:`latest_lidar_cm` /
    :attr:`lidar_age_s`.
    """
    
    def __init__(
        self,
        port: Optional[str] = None,
        baud: int = 115200,
        write_hz: float = 30.0,
        warmup_s: float = 1.5,
        connect_timeout_s: float = 3.0,
    ) -> None:
        self.port = port or _auto_detect_port()
        self.baud = baud
        self._min_dt = 1.0 / max(1e-6, write_hz)
        self._last_send = 0.0
        self._last_left: Optional[float] = None
        self._last_right: Optional[float] = None
        
        self._latest_lidar_cm: Optional[int] = None
        self._last_lidar_ts = 0.0
        
        self.ser = serial.Serial(
            self.port,
            self.baud,
            timeout=0.1,
            write_timeout=connect_timeout_s,
        )
        
        time.sleep(warmup_s)    # allow Nano to reboot on serial open
        self.stop()
        
    def _drain_telemetry(self) -> None:
        """
        Non-blocking read of any pending lines from the Nano.
        Parses LiDAR distance from debug telemetry lines such as::
        
            LIDAR_CM=123 BLOCKED=0
        """
        try:
            while self.ser.in_waiting:
                line = self.ser.readline().decode(errors="ignore").strip()
                if line.startswith("LIDAR_CM="):
                    parts = line.split()
                    cm_str = parts[0].split("=", 1)[1]
                    try:
                        self._latest_lidar_cm = int(cm_str)
                        self._last_lidar_ts = time.monotonic()
                    except ValueError:
                        pass
        except Exception:
            # Never let telemetry parsing crash motor control.
            pass
        
    def set_tracks(self, left: float, right: float) -> None:
        self._drain_telemetry()
        
        left = clamp(left, -1.0, 1.0)
        right = clamp(right, -1.0, 1.0)
        
        now = time.monotonic()
        
        changed = (
            self._last_left is None
            or self._last_right is None
            or abs(left - self._last_left) > 0.01
            or abs(right - self._last_right) > 0.01
        )
        
        if not changed and (now - self._last_send) < self._min_dt:
            return
        
        line = f"{left:.3f},{right:.3f}\n"
        self.ser.write(line.encode("ascii", errors="ignore"))
        
        self._last_send = now
        self._last_left = left
        self._last_right = right
        
    def stop(self) -> None:
        self.ser.write(b"0.000,0.000\n")
        self._last_send = time.monotonic()
        self._last_left = 0.0
        self._last_right = 0.0
        
    def close(self) -> None:
        try:
            self.stop()
        finally:
            try:
                self.ser.close()
            except Exception:
                pass
    
    @property
    def latest_lidar_cm(self) -> Optional[int]:
        """Most recently parsed LiDAR distance in cm, or None if not yet received."""
        return self._latest_lidar_cm
    
    @property
    def lidar_age_s(self) -> float:
        """Seconds since the last valid LiDAR reading, or inf if never received."""
        if self._last_lidar_ts <= 0:
            return float("inf")
        return time.monotonic() - self._last_lidar_ts