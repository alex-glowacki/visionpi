#!/usr/bin/env bash
# deploy/apply_patches.sh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PATH="$REPO_DIR/patches/hailo-apps/hailo-apps.diff"
HAILO_APPS_DIR="$HOME/hailo-apps"

if [ ! -d "$HAILO_APPS_DIR" ]; then
    echo "ERROR: hailo-apps not found at $HAILO_APPS_DIR"
    exit 1
fi

cd "$HAILO_APPS_DIR"
echo "Applying path: $PATCH"
git apply "$PATCH"
echo "Done."