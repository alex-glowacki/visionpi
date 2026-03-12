# Pi Setup

## Prerequisites

- Raspberry Pi with Hailo AI Kit (Hailo-10H or compatible)
- `hailo-apps` installed with `venv_hailo_apps` at `~/hailo-apps/venv_hailo_apps/`
- MediaMTX RTSP server running (see `deploy/services/`)

## 1. Clone the repo

```bash
git clone https://github.com/<your-org>/visionpi-robot.git
cd visionpi-robot
```

## 2. Install dependencies

```bash
source ~/hailo-apps/venv_hailo_apps/bin/activate
pip install -e ".[pi]"
```

## 3. Apply hailo-apps patches (if needed)

```bash
bash deploy/apply_patches.sh
```

## 4. Install systemd services

```bash
bash deploy/install_services.sh
```

## 5. Run

```bash
# Terminal 1 — vision pipeline
source ~/hailo-apps/venv_hailo_apps/bin/activate
python3 -u vision/detect_to_json.py

# Terminal 2 — follow person
python3 -m apps.follow_person --driver real
```

## Development (no hardware)

```bash
pip install -e ".[dev]"
pytest
python3 -m apps.follow_person  # mock mode, no Nano needed
```
