#!/usr/bin/env bash
# deploy/install_services.sh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICES_DIR="$REPO_DIR/deploy/services"

echo "Installing systemd services from $SERVICES_DIR ..."

# Vision pipeline - enabled and starting on boot
sudo cp "$SERVICES_DIR/hailo-detect-rtsp.service" \
        /etc/systemd/system/hailo-detect-rtsp.service

# Follow behavior - installed but NOT enabled on boot (manual start only)
# To enable on boot later, run:
#    sudo systemctl enable visionpi-follow
#    sudo systemctl start visionpi-follow
sudo cp "$SERVICES_DIR/visionpi-follow.service" \
        /etc/systemd/system/visionpi-follow.service

sudo systemctl daemon-reload

# Enable and start vision pipeline
sudo systemctl enable --now hailo-detect-rtsp

echo ""
echo "Done."
echo ""
echo "Vision pipeline: enabled on boot (hailo-detect-rtsp)"
echo "Follow service: installed but NOT enabled on boot (visionpi-follow)"
echo ""
echo "To start the follow service manually:"
echo "  sudo systemctl start visionpi-follow"
echo "  sudo journalctl -fu visionpi-follow     # live logs"
echo ""
echo "To enable follow service on boot when ready:"
echo "  sudo systemctl enable visionpi-follow"