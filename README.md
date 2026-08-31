# Raspberry Pi Monitoring Server

Description:
------------
This project is a complete web server built with Flask, designed to monitor a Raspberry Pi in real time and provide enhanced features including face recognition, hardware statistics, weather integration, and Telegram alerts.

The repository now also contains an optional self-hosted Wiki.js knowledge base. It runs beside the existing Flask application; it does not replace the portfolio, dashboard, routes, authentication, or current process startup.

Implemented Features:
---------------------

🔐 AUTHENTICATION  
- Login page with JWT-based session authentication.  
- Protected dashboard and API endpoints.

📸 FACE RECOGNITION MODULE (NEW)  
- Integration with ESP32-CAM for live MJPEG streaming.  
- Real-time face recognition using OpenCV and face_recognition.  
- Notifies via Telegram when a known face is detected.  
- Sends alert for unknown or unauthorized faces.  
- `/video_feed` endpoint: MJPEG stream with face overlays.  
- `/stream_face`: browser-accessible stream viewer (login required).  

📊 DASHBOARD  
- Real-time display of:
  - CPU temperature
  - Memory usage
  - Disk usage
  - Power status (mocked)
  - Energy consumption (simulated value)  
- Auto-refreshing charts using Chart.js.

🌐 NETWORK MONITORING  
- Displays per-interface network metrics:
  - Bytes sent/received
  - Packets sent/received

🌦️ WEATHER MODULE  
- Interactive weather map using Windy API and OpenWeatherMap.
- Supports overlays: wind, temperature, pressure, and radar.
- Displays local weather using geolocation (JavaScript-based).

🚨 TELEGRAM ALERT SYSTEM  
- Sends alerts to a Telegram bot chat when:
  - CPU temperature exceeds 70°C
  - Energy usage exceeds 60W
  - An unknown face is detected

🌍 PUBLIC PORTFOLIO  
- Public endpoint showing Ismaele Carbonari’s portfolio.
- Includes biography, projects, experience, and contact info.

🔐 ACCESS CONTROL  
- Dashboard and all system/network APIs are protected by JWT login.
- `/weather` and `/portfolio` are public routes.
- Face stream (`/stream_face`) requires authentication.

🛡️ HTTPS WITH DUCKDNS & NGINX  
- Publicly available via DuckDNS domain.
- HTTPS enabled with Let's Encrypt certificates via Certbot.
- NGINX reverse proxy used to serve Flask app securely.

👟 AUTOSTART ON BOOT  
- Flask app launches at system boot using `systemd`.
- Unit file: `pimonitor.service`

Hardware Integration:
---------------------
- 🧠 Raspberry Pi 4/3B+ recommended  
- 📷 ESP32-CAM module:
  - Provides MJPEG video stream to Flask
  - Configurable static IP or mDNS
  - Connects over local Wi-Fi

Project Structure:
------------------
- `app.py`               → Flask main application
- `templates/`           → HTML templates (login, dashboard, weather, portfolio, stream)
- `static/`              → CSS and JS files
- `known_faces/`         → Directory of reference images for face recognition
- `pimonitor.service`    → referenced host systemd unit (not checked into this repository)
- `.gitignore`           → Excludes venv, cache, and temp files
- `venv/`                → Python virtual environment (excluded from Git)
- `PiMonitor/knowledge/` → Framework-independent knowledge models and Wiki.js source
- `infrastructure/wikijs/` → Isolated Wiki.js/PostgreSQL Compose stack and operations
- `scripts/export_wiki_knowledge.py` → Normalized JSONL export for future ingestion
- `docs/`                → Future RAG architecture and Wiki content conventions

Requirements:
-------------
- Python 3.9+ (recommended: 3.11 on Raspberry Pi OS)
- Flask
- OpenCV (`opencv-python`)
- face_recognition
- psutil
- requests
- pyjwt
- numpy
- certbot (for HTTPS)
- nginx (reverse proxy)
- mDNS (Avahi or Bonjour for ESP32 name resolution)

How to Access:
--------------
- Local:
  - `http://<your-pi-ip>:5000/` → Main login page
  - `http://<your-pi-ip>:5000/stream_face` → Face recognition stream (after login)

- From ESP32-CAM:
  - Hardcoded/static IP (e.g. `http://192.168.1.103/stream`)
  - or use `esp32cam.local` if mDNS is supported

How the existing Flask app starts:
----------------------------------
- The entrypoint is `PiMonitor/app.py`, which creates the Flask application and listens on `0.0.0.0:5000` when executed directly.
- Run it from `PiMonitor/` so its current top-level imports resolve: `cd PiMonitor && python3 app.py`.
- The existing app expects a local, Git-ignored `PiMonitor/config.py`. A safe environment-backed starting point is provided at `PiMonitor/config.py.example`.
- The README describes nginx/systemd deployment, but those host configuration files are not checked into this repository. The Wiki.js nginx file is therefore optional and separate.

Wiki.js quick start:
--------------------

```sh
cp infrastructure/wikijs/.env.example infrastructure/wikijs/.env
chmod 600 infrastructure/wikijs/.env
# Generate a password, put it in the new .env, then start:
openssl rand -base64 48
make wiki-up
make wiki-status
```

Open `http://127.0.0.1:3000` on the server for first-time setup. PostgreSQL is not exposed on a host port. For LAN/Tailscale access and the recommended HTTPS subdomain setup, see [`infrastructure/wikijs/README.md`](infrastructure/wikijs/README.md).

Set `WIKIJS_URL` in the Flask process environment to enable the Knowledge Base card in the authenticated dashboard. The card opens the JWT-protected `/wiki` launcher, which issues a short-lived, HTTP-only access cookie before redirecting to Wiki.js. For a public sibling subdomain, set `WIKIJS_AUTH_COOKIE_DOMAIN` to the shared parent domain and protect the Wiki.js nginx virtual host with `auth_request`, as shown in the supplied nginx example. The public portfolio does not expose the link. Set `WIKIJS_API_TOKEN` only in the backend environment when extraction is needed; it is never sent to templates.

Administration and backups:
---------------------------

```sh
make wiki-logs
make wiki-restart
make wiki-backup
make wiki-restore BACKUP=/absolute/path/to/wikijs-backup.dump
make wiki-down
```

Detailed configuration, API token setup, restore safeguards, upgrades, reverse proxy setup, and troubleshooting are in [`infrastructure/wikijs/README.md`](infrastructure/wikijs/README.md).

GitHub validates tests, templates, scripts, and Compose on every push to `main`. A separate manual production workflow is ready for SSH-based deployment after its protected secrets are configured; see [`docs/GITHUB_ACTIONS.md`](docs/GITHUB_ACTIONS.md).

Future local knowledge assistant:
---------------------------------

Wiki.js remains the canonical human-editable source. The current knowledge layer can export normalized Markdown documents but intentionally contains no embeddings, vector database, LLM, or chat endpoint. See [`docs/KNOWLEDGE_ARCHITECTURE.md`](docs/KNOWLEDGE_ARCHITECTURE.md) and [`docs/WIKI_CONTENT_GUIDE.md`](docs/WIKI_CONTENT_GUIDE.md).

Telegram Bot:
-------------
- Notifications for system alerts and face detection
- Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in the existing local `PiMonitor/config.py` (or through the environment-backed example); do not put real tokens in Git.

License:
--------
MIT

Author:
-------
Ismaele Carbonari  
