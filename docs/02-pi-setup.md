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

## 4. Configure MediaMTX

MediaMTX must serve RTP over TCP (not UDP) for `rtspsrc` to receive frames.
Edit `/opt/mediamtx/mediamtx.yml` and update the `paths:` section:

```yaml
paths:
  stream:
    rtspTransport: tcp
  detect:
    rtspTransport: tcp
  all_others:
```

Then restart MediaMTX:

```bash
sudo systemctl restart mediamtx
```

> **Why:** The `rtsp-publisher` service sends to MediaMTX over UDP, which is
> fine for publishing. But on the consumer side, `rtspsrc` cannot receive UDP
> RTP packets on loopback due to port routing. Forcing TCP on the MediaMTX
> path ensures consumers always receive RTP interleaved over the TCP control
> channel, which works reliably on loopback.

## 5. Install systemd services

```bash
bash deploy/install_services.sh
```

## 6. Run

```bash
# Terminal 1 — vision pipeline
source ~/hailo-apps/venv_hailo_apps/bin/activate
python3 -u vision/detect_model1.py

# Terminal 2 — follow person
python3 -m apps.follow_person --driver real
```

## Development (no hardware)

```bash
pip install -e ".[dev]"
pytest
python3 -m apps.follow_person  # mock mode, no Nano needed
```
