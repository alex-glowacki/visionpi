#!/usr/bin/env python3
# apps/follow_controller_cli.py
"""
Controller-only CLI harness.

Reads detections from JSON and prints controller decisions without running
a full application loop. Useful for tuning params and validating logic
before connecting real hardware.

Run in mock mode (no hardware):
    python3 -m apps.follow_controller_cli --hz 10

Run with real Nano:
    python3 -m apps.follow_controller_cli --driver real --write-hz 20
"""

from __future__ import annotations

import argparse
import time
from typing import Optional

from motors.mock_driver import MockMotorDriver
from robot.follow_controller import FollowController
from robot.params import FollowParams
from vision.detections_reader import DetectionsReader, DetectionFrame


def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Controller-only harness: reads detections and prints decisions."
    )
    p.add_argument("--path", default="/tmp/detections.json",
                   help="Detections JSON file path")
    p.add_argument("--once", action="store_true",
                   help="Run one step then exit")
    p.add_argument("--hz", type=float, default=10.0,
                   help="Loop rate (ignored with --once)")

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

    g3 = p.add_argument_group("lidar safety (reads telemetry from Nano)")
    g3.add_argument("--lidar", action="store_true",
                    help="Enable TF-Luna LiDAR safety stop")
    g3.add_argument("--stop-cm", type=int, default=60,
                    help="Stop if LiDAR distance <= this (cm)")
    g3.add_argument("--lidar-stale-s", type=float, default=0.5,
                    help="Ignore LiDAR reading if older than this (seconds)")
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

    print("[follow_controller_cli] starting")
    print(f"[follow_controller_cli] path={args.path}")
    print(f"[follow_controller_cli] params={params}")
    print(f"[follow_controller_cli] driver={args.driver}")

    def step_once() -> int:
        frame: Optional[DetectionFrame] = reader.read_latest()
        if frame is None:
            print("[follow_controller_cli] no new frame available")
            driver.stop()
            return 1

        # Optional LiDAR safety override (reads telemetry parsed by RealMotorDriver)
        if args.lidar:
            dist_cm = getattr(driver, "latest_lidar_cm", None)
            age_s = getattr(driver, "lidar_age_s", 0.0)

            if dist_cm is not None and age_s < args.lidar_stale_s:
                if dist_cm <= args.stop_cm:
                    driver.stop()
                    print(
                        f"[follow_controller_cli] STOP (lidar) "
                        f"dist_cm={dist_cm} age_s={age_s:.2f}"
                    )
                    return 0

        status = controller.update(frame)
        print(f"[follow_controller_cli] {status}")
        return 0

    if args.once:
        rc = step_once()
        driver.stop()
        return rc

    try:
        while True:
            step_once()
            time.sleep(1.0 / max(0.1, args.hz))
    except KeyboardInterrupt:
        pass
    finally:
        driver.stop()
        print("[follow_controller_cli] stopped")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())