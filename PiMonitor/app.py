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
app.config['SECRET_KEY'] = ''  


TELEGRAM_BOT_TOKEN = ""
TELEGRAM_CHAT_ID = ""
ALERT_INTERVAL = 300  
last_alert_time = 0


CPU_TEMP_THRESHOLD = 70.0  
ENERGY_THRESHOLD = 60.0    

def get_energy_consumption():
    """
    work in progress
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
        if username == 'ismacarbo' and password == '':
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

@app.route('/api/temperature', methods=['GET'])
def temperature():
    temp = request.args.get('temp')
    hum = request.args.get('hum')
    if temp and hum:
        try:
            temp_value = float(temp)
            hum_value = float(hum)
            
            print(f"Temperatura ricevuta: {temp_value} °C, Umidità ricevuta: {hum_value} %")
            return jsonify({"status": "success", "temperature": temp_value, "humidity": hum_value}), 200
        except ValueError:
            return jsonify({"status": "error", "message": "Valori non validi"}), 400
    else:
        return jsonify({"status": "error", "message": "Parametri mancanti"}), 400


def send_telegram_photo(photo_path, caption):
    """
    Invia una foto al canale/utente Telegram specificato.
    """
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    with open(photo_path, 'rb') as photo_file:
        files = {'photo': photo_file}
        data = {
            'chat_id': TELEGRAM_CHAT_ID,
            'caption': caption
        }
        try:
            response = requests.post(url, data=data, files=files)
            if response.status_code == 200:
                print("Foto inviata correttamente a Telegram.")
            else:
                print("Errore nell'invio a Telegram:", response.text)
        except Exception as e:
            print("Eccezione nell'invio della foto a Telegram:", e)

def process_face(image_path):
    """
    work in progress
    """
    
    riconosciuto = random.choice([True, False])
    return "nome" if riconosciuto else "no"

@app.route('/api/face', methods=['POST'])
def face_recognition():
    
    image_data = request.get_data()
    if not image_data:
        return jsonify({"status": "error", "message": "Nessun dato ricevuto"}), 400

    
    image_path = "received_face.jpg"
    try:
        with open(image_path, "wb") as f:
            f.write(image_data)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Errore nel salvataggio dell'immagine: {e}"}), 500

    
    riconoscimento = process_face(image_path)
    print(f"Risultato riconoscimento: {riconoscimento}")

    
    send_telegram_photo(image_path, caption=riconoscimento)

    return jsonify({"status": "success", "message": "Immagine ricevuta e inviata a Telegram", "riconoscimento": riconoscimento}), 200



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
