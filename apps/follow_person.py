#!/usr/bin/env python3
# apps/follow_person.py
"""
Full person-following application loop.

Run on Pi (real hardware):
    python3 -m apps.follow_person --driver real
    
Run on any machine (mock / no hardware):
    python3 -m apps.follow_person
"""

from __future__ import annotations

import argparse
import signal
import time
from typing import Optional

from motors.mock_driver import MockMotorDriver
from robot.follow_controller import FollowController
from robot.params import FollowParams
from vision.detections_reader import DetectionsReader, DetectionFrame


class Rate:
    """Fixed-rate loop timer using monotonic clock."""
    
    def __init__(self, hz: float) -> None:
        self.dt = 1.0 / max(1e-6, float(hz))
        self._next = time.monotonic()
        
    def sleep(self) -> None:
        self._next += self.dt
        now = time.monotonic()
        delay = self._next - now
        if delay > 0:
            time.sleep(delay)
        else:
            # Fell behind - reset to avoid a catch-up burst
            self._next = now
            

def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="VisionPi: follow a person using /tmp/detections.json"
    )
    p.add_argument("--path", default="/tmp/detections.json",
                   help="Path to detections JSON file")
    p.add_argument("--hz", type=float, default=15.0,
                   help="Control loop frequency (Hz)")

    g = p.add_argument_group("motor driver")
    g.add_argument("--driver", choices=["mock", "real"], default="mock",
                   help="Motor driver backend ('real' requires Nano over USB)")
    g.add_argument("--mock-print-hz", type=float, default=8.0,
                   help="Mock driver print rate (mock only)")
    g.add_argument("--port", default=None,
                   help="Serial port for Nano (auto-detected if omitted)")
    g.add_argument("--baud", type=int, default=115200,
                   help="USB serial baud rate (real only)")
    g.add_argument("--write-hz", type=float, default=20.0,
                   help="How often to refresh motor command to Nano (real only)")
    g.add_argument("--connect-timeout", type=float, default=2.0,
                   help="Seconds to wait after opening serial (real only)")

    g2 = p.add_argument_group("follow params (optional overrides)")
    g2.add_argument("--min-conf", type=float, default=None)
    g2.add_argument("--deadband", type=float, default=None)
    g2.add_argument("--steer-gain", type=float, default=None)
    g2.add_argument("--base-speed", type=float, default=None)
    g2.add_argument("--turn-speed", type=float, default=None)
    g2.add_argument("--hard-turn-err", type=float, default=None)
    return p


def _apply_overrides(params: FollowParams, args: argparse.Namespace) -> FollowParams:
    return FollowParams(
        min_conf=params.min_conf if args.min_conf is None else float(args.min_conf),
        deadband=params.deadband if args.deadband is None else float(args.deadband),
        steer_gain=params.steer_gain if args.steer_gain is None else float(args.steer_gain),
        base_speed=params.base_speed if args.base_speed is None else float(args.base_speed),
        turn_speed=params.turn_speed if args.turn_speed is None else float(args.turn_speed),
        hard_turn_err=params.hard_turn_err if args.hard_turn_err is None else float(args.hard_turn_err),
    )
    

def main() -> int:
    args = _build_argparser().parse_args()

    stop_flag = {"stop": False}

    def _handle_stop(_sig, _frame) -> None:
        stop_flag["stop"] = True

    signal.signal(signal.SIGINT, _handle_stop)
    signal.signal(signal.SIGTERM, _handle_stop)

    reader = DetectionsReader(path=args.path)

    if args.driver == "mock":
        driver = MockMotorDriver(print_hz=args.mock_print_hz)
    else:
        from motors.real_driver import RealMotorDriver
        driver = RealMotorDriver(
            port=args.port or None,
            baud=args.baud,
            write_hz=args.write_hz,
            connect_timeout_s=args.connect_timeout,
        )

    params = _apply_overrides(FollowParams(), args)
    controller = FollowController(driver=driver, params=params)
    rate = Rate(args.hz)

    print("[follow_person] starting loop")
    print(f"[follow_person] reading: {args.path}")
    print(f"[follow_person] params:  {params}")
    print(f"[follow_person] driver:  {args.driver}")

    last_status: Optional[str] = None
    last_frame_ts: float = 0.0
    stale_warn_every = 2.0
    next_stale_warn = time.monotonic() + stale_warn_every

    try:
        while not stop_flag["stop"]:
            frame: Optional[DetectionFrame] = reader.read_latest()

            if frame is None:
                driver.stop()
            else:
                last_frame_ts = frame.ts
                status = controller.update(frame)
                if status != last_status:
                    print(f"[follow_person] {status}")
                    last_status = status

            now = time.monotonic()
            if now >= next_stale_warn:
                age = time.time() - last_frame_ts if last_frame_ts else float("inf")
                if age > 1.5:
                    print(
                        f"[follow_person] WARNING: detections stale "
                        f"(age={age:.2f}s). Is the vision pipeline running?"
                    )
                next_stale_warn = now + stale_warn_every

            rate.sleep()

    finally:
        driver.stop()
        print("[follow_person] stopped")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())