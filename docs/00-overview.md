# System Overview

## Goal

Build a rover platform that supports person-following today and can later expand
into additional behaviours such as teleop, patrol, obstacle-aware roaming, or
other robotics experiments.

## System Split

### Raspberry Pi (VisionPi)

Responsible for:

- Camera input
- Person detection (Hailo NPU + YOLOv8)
- Behaviour logic
- Sending motion commands to the Nano

### Arduino Nano R4

Responsible for:

- Motor control (Sabertooth 2×12 in R/C mode)
- TF-Luna LiDAR reading
- IMU reading (Modulino Movement / LSM6DSOX)
- LED status display (Modulino Pixels)
- Low-level safety stop logic

## Data Flow

```
Camera → Hailo NPU (YOLOv8)
       → /tmp/detections.json  (atomic write, every N frames)
       → FollowController      (pure control logic, runs on Pi)
       → RealMotorDriver       (USB serial → Nano)
       → Nano firmware          (enforces LiDAR / tilt / timeout safety)
       → Sabertooth 2x12
       → Track motors
```

## Repo Layout

```
visionpi-robot/
├── apps/                       # Runnable entrypoints
│   ├── follow_person.py        # Full person-follow loop
│   └── follow_controller_cli.py# Controller-only harness
│
├── motors/                     # Motor driver layer
│   ├── driver_base.py          # Protocol + helpers
│   ├── mock_driver.py          # Fake driver for dev/testing
│   └── real_driver.py          # pyserial driver → Nano USB
│
├── robot/                      # Core robot logic
│   ├── follow_controller.py    # Pure control logic (no I/O)
│   └── params.py               # FollowParams dataclass
│
├── vision/                     # Vision + detection processing
│   ├── detect_to_json.py       # Hailo GStreamer pipeline → /tmp/detections.json
│   ├── detect_model1.py        # Alternative single-pipeline model
│   └── detections_reader.py    # Reads /tmp/detections.json → DetectionFrame
│
├── scripts/                    # Utility tools (not part of the package)
│   └── motor_test_rc.py        # Manual RC motor test sequence
│
├── tests/                      # Test suite
│   ├── conftest.py             # Shared pytest fixtures
│   ├── test_follow_controller.py  # Unit tests (no hardware)
│   └── test_nano_driver.py     # Hardware smoke test (manual)
│
├── firmware/
│   └── nano/visionpi_motor_controller/
│       ├── platformio.ini
│       ├── include/config.h
│       ├── src/main.cpp        # Active firmware
│       └── archive/            # Historical firmware snapshots
│
├── deploy/                     # Deployment config
│   ├── services/               # systemd service files
│   ├── apply_patches.sh
│   └── install_services.sh
│
└── docs/
```

## Design Principle

The robot should be treated as a **reusable rover platform**.

Person-following is an _app_, not the whole architecture. New behaviours
should be added as new files under `apps/` using the same `MotorDriver`
interface, without touching `robot/` or `motors/`.
