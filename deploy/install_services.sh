#!/usr/bin/env bash
# deploy/install_services.sh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICES_DIR="$REPO_DIR/deploy/services"

echo "Installing systemd services from $SERVICES_DIR ..."

sudo cp "$SERVICES_DIR/hailo-detect-rtsp.services" \
        /etc/systemd/system/hailo-detect-rtsp.service

sudo systemctl daemon-reload
sudo systemctl enable --now hailo-detect-rtsp

echo "Done."