#!/usr/bin/env python3
# scripts/motor_test_rc.py
"""
Manual motor test: forward, stop, reverse, spin left, spin right.

Usage:
    python3 scripts/motor_test_rc.py
    python3 scripts/motor_test_rc.py --port /dev/ttyACM0
"""

import argparse
import time
from motors.real_driver import RealMotorDriver


def main() -> None:
    parser = argparse.ArgumentParser(description="Manual RC motor test sequence")
    parser.add_argument("--port", default=None, help="Serial port (auto-detect if omitted)")
    parser.add_argument("--baud", type=int, default=115200)
    args = parser.parse_args()
    
    driver = RealMotorDriver(port=args.port, baud=args.baud)
    
    def hold(left: float, right: float, sec: float, label: str) -> None:
        print(f"[TEST] {label:<20} L={left:+.2f} R={right:+.2f}")
        t0 = time.monotonic()
        while(time.monotonic() - t0) < sec:
            driver.set_tracks(left, right)
            time.sleep(0.03)
            
        
    try:
        hold( 0.0,   0.0,  2.0, "NEUTRAL / ARM")
        hold(+0.25, +0.25, 2.0, "FORWARD")
        hold( 0.0,   0.0,  1.0, "STOP")
        hold(-0.25, -0.25, 2.0, "REVERSE")
        hold( 0.0,   0.0,  1.0, "STOP")
        hold(-0.25, +0.25, 2.0, "SPIN LEFT")
        hold( 0.0,   0.0,  1.0, "STOP")
        hold(+0.25, -0.25, 2.0, "SPIN RIGHT")
        hold( 0.0,   0.0,  2.0, "FINAL STOP")
    finally:
        driver.close()


if __name__ == "__main__":
    main()