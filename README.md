==============================
Raspberry Pi Monitoring Server
==============================

Description:
------------
This project is a complete web server built with Flask, designed to monitor a Raspberry Pi in real time. It includes user authentication, a dynamic dashboard, live-updating charts, weather data integration, and Telegram alerts for critical system metrics.

Implemented Features:
---------------------

🔐 AUTHENTICATION
- Login page with JWT-based session authentication.

📊 DASHBOARD
- Real-time display of:
  - CPU temperature
  - Memory usage
  - Disk usage
  - Power status (mocked)
  - Energy consumption (simulated value)
- All metrics are displayed using auto-updating charts.

🌐 NETWORK MONITORING
- Displays per-interface network data:
  - Bytes sent/received
  - Packets sent/received

🌦️ WEATHER MODULE
- Interactive weather map using Windy API and OpenWeatherMap.
- Supports overlays: wind, temperature, pressure, and radar.
- Displays local weather data using geolocation.

🚨 TELEGRAM ALERT SYSTEM
- Automatically sends alerts to a Telegram chat when:
  - CPU temperature exceeds 70°C
  - Simulated energy usage exceeds 60W

🌍 PUBLIC PORTFOLIO
- Publicly accessible endpoint showing Ismaele Carbonari’s portfolio.
- Includes biography, projects, work experience, and contact info.

🔐 ACCESS CONTROL
- Dashboard and API endpoints require login.
- `/weather` and `/portfolio` are public endpoints.

🛡️ HTTPS WITH DUCKDNS & NGINX
- Server exposed via DuckDNS with HTTPS support.
- Let's Encrypt certificate obtained via Certbot and served through NGINX reverse proxy.

👟 AUTOSTART ON BOOT
- The Flask server starts automatically at boot using a `systemd` service.

Project Structure:
------------------
- `app.py`         → Flask main application
- `templates/`     → HTML templates (login, dashboard, weather, portfolio)
- `static/`        → CSS and JS assets
- `venv/`          → Virtual environment (excluded via .gitignore)
- `.gitignore`     → Ignores temp files, virtualenv, caches
- `pimonitor.service` → systemd unit file for auto-start

Requirements:
-------------
- Python 3.9+ (recommended: 3.11 on Raspberry Pi OS)
- Flask
- psutil
- requests
- pyjwt
- certbot, nginx (for HTTPS support with DuckDNS)
