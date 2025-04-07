from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import jwt
import datetime
import psutil
import subprocess
import random
import time
import requests
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = 'Ismaele04!'  


TELEGRAM_BOT_TOKEN = "7927241484:AAEva_3VmnzjLoLwlwAoRj1u54wq7Tmp2us"
TELEGRAM_CHAT_ID = "695326432"
ALERT_INTERVAL = 300  
last_alert_time = 0


CPU_TEMP_THRESHOLD = 70.0  
ENERGY_THRESHOLD = 60.0    

def get_energy_consumption():
    """
    Funzione di esempio che simula l'energia consumata in watt.
    In un'applicazione reale sostituisci questo valore con la lettura di un sensore.
    """
    return round(random.uniform(40, 80), 2)

def send_telegram_alert(message):
    global last_alert_time
    now = time.time()
    
    if now - last_alert_time > ALERT_INTERVAL:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message
        }
        try:
            response = requests.post(url, data=payload)
            if response.status_code == 200:
                print("Telegram alert sent.")
                last_alert_time = now
            else:
                print("Error sending Telegram alert:", response.text)
        except Exception as e:
            print("Exception sending Telegram alert:", e)


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = session.get('jwt')
        if not token:
            return redirect(url_for('login'))
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = data['username']
        except Exception as e:
            return redirect(url_for('login'))
        return f(current_user, *args, **kwargs)
    return decorated

@app.route("/")
def home():
    return redirect(url_for("login"))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == 'ismacarbo' and password == '211104!!isma':
            token = jwt.encode({
                'username': username,
                'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=30)
            }, app.config['SECRET_KEY'], algorithm="HS256")
            session['jwt'] = token
            return redirect(url_for('dashboard'))
        return render_template('login.html', error="Invalid credentials")
    return render_template('login.html')


@app.route('/dashboard')
@token_required
def dashboard(current_user):
    return render_template('dashboard.html', username=current_user)


@app.route('/weather')
def weather():
    
    return render_template('weather.html')


@app.route('/portfolio')
def portfolio():
    return render_template('portfolio.html')



@app.route('/api/system', methods=['GET'])
@token_required
def system_info(current_user):
    try:
        temp_output = subprocess.check_output(["vcgencmd", "measure_temp"]).decode()
        cpu_temp = float(temp_output.split('=')[1].split("'")[0])
    except Exception as e:
        cpu_temp = 0.0

    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    energy = get_energy_consumption()

    
    if cpu_temp > CPU_TEMP_THRESHOLD:
        send_telegram_alert(f"Alert: CPU temperature is high ({cpu_temp} °C)!")
    if energy > ENERGY_THRESHOLD:
        send_telegram_alert(f"Alert: Energy consumption is high ({energy} W)!")

    data = {
        "cpu_temperature": cpu_temp,
        "memory": {
            "total": mem.total,
            "used": mem.used,
            "free": mem.free,
            "percent": mem.percent
        },
        "disk": {
            "total": disk.total,
            "used": disk.used,
            "free": disk.free,
            "percent": disk.percent
        },
        "energy_consumption": energy,
        "power_status": "Online"  
    }
    return jsonify(data)


@app.route('/api/network', methods=['GET'])
@token_required
def network_info(current_user):
    net_io = psutil.net_io_counters(pernic=True)
    network_data = {}
    for iface, stats in net_io.items():
        network_data[iface] = {
            "bytes_sent": stats.bytes_sent,
            "bytes_recv": stats.bytes_recv,
            "packets_sent": stats.packets_sent,
            "packets_recv": stats.packets_recv
        }
    return jsonify(network_data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
