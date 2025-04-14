# Raspberry Pi Monitoring Server

Description:
------------
This project is a complete web server built with Flask, designed to monitor a Raspberry Pi in real time and provide enhanced features including face recognition, hardware statistics, weather integration, and Telegram alerts.

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
- `pimonitor.service`    → systemd unit file to autostart Flask on boot
- `.gitignore`           → Excludes venv, cache, and temp files
- `venv/`                → Python virtual environment (excluded from Git)

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

Telegram Bot:
-------------
- Notifications for system alerts and face detection
- Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `app.py`

License:
--------
MIT

Author:
-------
Ismaele Carbonari  
