#!/usr/bin/env python3
# tests/test_nano_driver.py
"""
Manual Nano + Sabertooth smoke test.

This is an INTEGRATION test that requires the Nano to be physically connected.
It is NOT collected by pytest automatically (no test_ prefix on the function).

Run manually:
    python3 tests/test_nano_driver.py
"""

import time
from motors.real_driver import RealMotorDriver


def run() -> None:
    driver = RealMotorDriver()
    
    try:
        print("Forward...")
        for _ in range(50):
            driver.set_tracks(0.3, 0.3)
            time.sleep(0.03)
            
        print("Stop...")
        driver.stop()
        time.sleep(1.0)
        
        print("Reverse...")
        for _ in range(50):
            driver.set_tracks(-0.3, -0.3)
            time.sleep(0.03)
            
        print("Done.")
        driver.stop()
        
    finally:
        driver.close()
        
        
if __name__ == "__main__":
    run()