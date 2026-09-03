#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
EXPECTED_DIR=/home/ismacarbo/Desktop/Enhanced-Pi-Monitor

if [ "$PROJECT_DIR" != "$EXPECTED_DIR" ]; then
    echo "This deployment profile expects $EXPECTED_DIR, got $PROJECT_DIR" >&2
    exit 2
fi

cd "$PROJECT_DIR"
python3 -m venv venv
venv/bin/python -m pip install --disable-pip-version-check -r PiMonitor/requirements.txt
mkdir -p PiMonitor/known_faces
chmod 700 PiMonitor/known_faces
chmod 600 PiMonitor/config.py

(
    cd PiMonitor
    ../venv/bin/python - <<'PY'
import config

if len(config.SECRET_KEY) < 32:
    raise SystemExit("SECRET_KEY must contain at least 32 characters")
if not getattr(config, "DEVICE_API_TOKEN", ""):
    raise SystemExit("DEVICE_API_TOKEN must be configured")
PY
)

sudo -n install -m 0644 \
    infrastructure/systemd/pimonitor.service \
    /etc/systemd/system/pimonitor.service
sudo -n systemctl daemon-reload
sudo -n systemctl enable pimonitor.service
sudo -n systemctl restart pimonitor.service
sudo -n systemctl is-active --quiet pimonitor.service
curl --fail --silent --show-error http://127.0.0.1:5000/portfolio >/dev/null
sudo -n systemctl --no-pager --full status pimonitor.service
