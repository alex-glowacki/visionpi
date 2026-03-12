# VisionPi Robot

Person-following rover built with:

| Component               | Role                                              |
| ----------------------- | ------------------------------------------------- |
| Raspberry Pi / VisionPi | AI vision, behaviour logic, command dispatch      |
| Arduino Nano R4         | Real-time motor control, LiDAR, IMU, LEDs, safety |
| Sabertooth 2×12         | H-bridge motor driver (R/C mode)                  |
| TF-Luna LiDAR           | Forward obstacle detection                        |
| Modulino Movement       | IMU — tilt protection + yaw damping               |
| Modulino Pixels         | Status LED display                                |

The system is designed as a **general rover platform**. Person-following is
one app; teleop, patrol, and other behaviours can be added under `apps/`
without touching the core layers.

---

## Quick Start

### Development (no hardware needed)

```bash
git clone https://github.com/<your-org>/visionpi-robot.git
cd visionpi-robot

pip install -e ".[dev]"

# Run unit tests
pytest

# Run person-follow loop with a mock driver (no Nano, no camera)
python3 -m apps.follow_person
```

### On the Pi (real hardware)

See **[docs/02-pi-setup.md](docs/02-pi-setup.md)** for full setup instructions.

```bash
# Terminal 1: start the vision pipeline
source ~/hailo-apps/venv_hailo_apps/bin/activate
python3 -u vision/detect_to_json.py

# Terminal 2: start the follow-person app
python3 -m apps.follow_person --driver real
```

---

## Repo Layout

```
visionpi-robot/
├── apps/                          # Runnable entrypoints
│   ├── follow_person.py           # Full person-follow loop
│   └── follow_controller_cli.py   # Controller-only harness (tuning/debug)
│
├── motors/                        # Motor driver abstraction
│   ├── driver_base.py             # MotorDriver protocol + helpers
│   ├── mock_driver.py             # Fake driver (no hardware)
│   └── real_driver.py             # pyserial → Arduino Nano R4
│
├── robot/                         # Core robot logic (pure, no I/O)
│   ├── follow_controller.py       # FollowController class
│   └── params.py                  # FollowParams dataclass
│
├── vision/                        # Vision pipeline
│   ├── detect_to_json.py          # Hailo GStreamer → /tmp/detections.json
│   ├── detect_model1.py           # Alternative single-pipeline model
│   └── detections_reader.py       # Reads detections JSON → DetectionFrame
│
├── scripts/                       # Utility tools
│   └── motor_test_rc.py           # Manual motor test sequence
│
├── tests/                         # Test suite
│   ├── conftest.py                # Shared pytest fixtures
│   ├── test_follow_controller.py  # Unit tests (no hardware required)
│   └── test_nano_driver.py        # Hardware smoke test (manual, Nano required)
│
├── firmware/
│   └── nano/visionpi_motor_controller/
│       ├── platformio.ini
│       ├── include/config.h
│       ├── src/main.cpp           # Active firmware
│       └── archive/               # Historical firmware snapshots
│
├── deploy/                        # Pi deployment config
│   ├── services/                  # systemd service files
│   ├── apply_patches.sh
│   └── install_services.sh
│
└── docs/
    ├── 00-overview.md
    ├── 01-serial-protocol.md
    └── 02-pi-setup.md
```

---

## Serial Protocol (Pi → Nano)

Commands are plain text over USB serial at 115200 baud:

```
<left>,<right>\n
```

Values in `[-1.0, +1.0]`. Examples:

```
0.300,0.300     # forward 30%
-0.250,-0.250   # reverse 25%
-0.250,0.250    # spin left
0.000,0.000     # stop
```

The Nano enforces all low-level safety independently (LiDAR stop, tilt stop,
host timeout). See [docs/01-serial-protocol.md](docs/01-serial-protocol.md)
for the full reference.

---

## Running Tests

```bash
pytest                                       # all unit tests
pytest -v                                    # verbose
pytest tests/test_follow_controller.py       # specific file
```

The hardware smoke test must be run manually with the Nano connected:

```bash
python3 tests/test_nano_driver.py
```
