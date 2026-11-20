#!/usr/bin/env bash
# Install AURA as a systemd user service that starts when you log in.
#   scripts/install-service.sh            install + enable (starts next login)
#   scripts/install-service.sh --now      ...and start immediately
#   scripts/install-service.sh --remove   disable and uninstall
set -euo pipefail
cd "$(dirname "$0")/.."
UNIT_DIR="$HOME/.config/systemd/user"

if [[ "${1:-}" == "--remove" ]]; then
    systemctl --user disable --now aura.service 2>/dev/null || true
    rm -f "$UNIT_DIR/aura.service"
    systemctl --user daemon-reload
    echo "AURA service removed."
    exit 0
fi

mkdir -p "$UNIT_DIR"
ln -sf "$PWD/systemd/aura.service" "$UNIT_DIR/aura.service"
systemctl --user daemon-reload
systemctl --user enable aura.service
[[ "${1:-}" == "--now" ]] && systemctl --user restart aura.service
echo "AURA will start at login. Logs: journalctl --user -u aura -f"
