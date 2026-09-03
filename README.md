# Enhanced Pi Monitor

Web application for a Raspberry Pi homelab: public portfolio, protected
operations dashboard, host metrics, GDP/MQTT device health, occupancy map,
weather, face recognition and an optional Wiki.js knowledge base.

## Runtime architecture

```text
Browser (HTTPS)
      |
    nginx
      |
Gunicorn 127.0.0.1:5000
      |
    Flask
      +-- host metrics / network / LiDAR
      +-- GDP status from systemd + /run/gdp-server/devices.json
      +-- camera / face recognition
      +-- protected Wiki.js launcher
```

Gunicorn is the production server. Flask's built-in server binds only to
loopback when `app.py` is run manually and must not be exposed directly.

## Authentication boundaries

- `/portfolio`, `/projects` and project detail pages are public.
- `/dashboard`, `/weather`, camera, registration and Wiki.js launcher require a
  signed Flask session.
- Protected `/api/*` endpoints return JSON `401`, never an HTML redirect.
- Legacy ingestion endpoints use `X-Device-Token` or `Authorization: Bearer`:
  `/api/temperature`, `/api/face`, `POST /api/irrigation_data` and
  `/api/lidarDatas`.
- Browser state-changing forms use a CSRF token. Login failures are throttled.

Sessions expire after 30 minutes. Production cookies are `Secure`, `HttpOnly`
and `SameSite=Lax`. Keep all secrets in the Git-ignored `PiMonitor/config.py`;
`PiMonitor/config.py.example` documents the environment-backed interface.

Required values:

```text
FLASK_SECRET_KEY       at least 32 random characters
PIMONITOR_PASSWORD     dashboard password
PIMONITOR_DEVICE_TOKEN random token for legacy device HTTP ingestion
```

`OPENWEATHER_API`, `WINDY_API`, `TELEGRAM_BOT_TOKEN` and
`TELEGRAM_CHAT_ID` are optional. If Telegram is absent, notifications are
silently disabled. If the voltage ADC is absent, the API reports `null`; it
never generates simulated hardware measurements.

## Dashboard and GDP integration

The authenticated dashboard polls read-only endpoints for:

- CPU temperature, memory, disk and optional ADC voltage;
- per-second RX/TX throughput on the primary non-virtual interface;
- systemd status of `gdp-server.service` and
  `autoirrigation-mqtt.service`;
- MQTT broker reachability;
- the bounded GDP device snapshot at `/run/gdp-server/devices.json`;
- environmental history and LiDAR occupancy state.

The monitor does not control systemd services. The GDP service writes the
snapshot atomically; the monitor sanitizes and bounds it before returning it to
the browser. A device is considered stale after 90 seconds by default. Override
with `GDP_STATUS_FILE` and `GDP_DEVICE_STALE_SECONDS` in the systemd environment.

## Local development

The vision dependencies are intentionally part of the runtime requirements and
are comparatively large.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r PiMonitor/requirements.txt
cp PiMonitor/config.py.example PiMonitor/config.py
# Export the required variables before starting.
cd PiMonitor
../.venv/bin/python app.py
```

Run the lightweight unit suite without importing the vision runtime:

```sh
python -m unittest discover -s PiMonitor/tests -v
```

## Raspberry Pi deployment

The checked-in unit runs one Gunicorn worker with four threads on
`127.0.0.1:5000`, starts the optional serial fan worker once and applies basic
systemd hardening. The fixed production checkout is
`/home/ismacarbo/Desktop/Enhanced-Pi-Monitor`.

```sh
cd /home/ismacarbo/Desktop/Enhanced-Pi-Monitor
git pull --ff-only
make deploy-pi
```

The deploy target installs dependencies, validates local configuration, installs
`infrastructure/systemd/pimonitor.service`, restarts it and checks the public
portfolio endpoint. nginx remains the only public web listener.

## Wiki.js

Wiki.js/PostgreSQL is an optional isolated Compose stack. It remains the
canonical human-editable knowledge source and is not coupled to the monitor
runtime.

```sh
cp infrastructure/wikijs/.env.example infrastructure/wikijs/.env
chmod 600 infrastructure/wikijs/.env
make wiki-up
make wiki-status
make wiki-backup
```

Set `WIKIJS_URL` for the protected launcher and `WIKIJS_API_TOKEN` only in the
backend when exporting documents. Full setup and recovery procedures are in
[`infrastructure/wikijs/README.md`](infrastructure/wikijs/README.md).

## Repository map

```text
PiMonitor/
  app.py, wsgi.py          application factory and production entry point
  auth.py                  browser session, CSRF, throttling, device token
  routes/                  browser, telemetry, service and Wiki.js routes
  templates/, static/      responsive UI
  detectors/, stream/      vision pipeline
  occupancy/               thread-safe LiDAR grid state
  knowledge/               source-neutral knowledge models
infrastructure/systemd/    production monitor unit
infrastructure/wikijs/     optional Wiki.js stack
scripts/deploy_pi.sh       reproducible Pi rollout
```

GitHub Actions runs authentication, service status, Wiki.js and knowledge tests,
compiles Python/Jinja sources and validates deployment scripts. Production
deployment is manual and uses protected SSH secrets.
