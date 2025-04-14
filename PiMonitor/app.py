from flask import Flask, render_template, request, jsonify, redirect, url_for, session, Response
import jwt
import datetime
import psutil
import subprocess
import random
import time
import requests
import cv2
import face_recognition
import numpy as np
import os
from functools import wraps
from config import SECRET_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, PASSWORD, OPENWEATHER_API, WINDY_API

app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY

TELEGRAM_BOT_TOKEN = TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID = TELEGRAM_CHAT_ID
ALERT_INTERVAL = 300  

CPU_TEMP_THRESHOLD = 70.0    
VOLTAGE_THRESHOLD = 4.8      

FACE_ALERT_INTERVAL = 30     

last_recognized_alerts = {}
last_unrecognized_alert = 0

KNOWN_FACES_DIR = "known_faces"
known_face_encodings = []
known_face_names = []

def load_known_faces(directory):
    if not os.path.exists(directory):
        print(f"La cartella {directory} non esiste!")
        return
    for filename in os.listdir(directory):
        if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            image_path = os.path.join(directory, filename)
            image = cv2.imread(image_path)
            if image is None:
                print(f"Impossibile leggere l'immagine: {filename}")
                continue
            
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            encodings = face_recognition.face_encodings(image_rgb)
            if encodings:
                known_face_encodings.append(encodings[0])
                known_face_names.append(os.path.splitext(filename)[0])
                print(f"Caricato encoding per {filename}")
            else:
                print(f"Nessuna faccia trovata in {filename}")

load_known_faces(KNOWN_FACES_DIR)
print("Caricamento immagini di riferimento completato.")

def process_face(image_path):
    image = face_recognition.load_image_file(image_path)
    face_locations = face_recognition.face_locations(image)
    face_encodings = face_recognition.face_encodings(image, face_locations)
    
    if len(face_encodings) == 0:
        print("Nessuna faccia rilevata nell'immagine ricevuta.")
        return "Nessuna faccia"
    
    face_encoding = face_encodings[0]
    matches = face_recognition.compare_faces(known_face_encodings, face_encoding)
    face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)
    
    if len(face_distances) > 0:
        best_match_index = np.argmin(face_distances)
        if matches[best_match_index]:
            recognized_name = known_face_names[best_match_index]
            print(f"Riconosciuto: {recognized_name}")
            return recognized_name
    print("Faccia non riconosciuta.")
    return "unknown"

def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }
    try:
        response = requests.post(url, data=payload)
        if response.status_code == 200:
            print("Telegram alert sent:", message)
        else:
            print("Error sending Telegram alert:", response.text)
    except Exception as e:
        print("Exception sending Telegram alert:", e)


def get_voltage():
    try:
        
        import Adafruit_ADS1x15
        adc = Adafruit_ADS1x15.ADS1115()
        GAIN = 1
        value = adc.read_adc(0, gain=GAIN)
        
        voltage = value * (4.096 / 32767) * 2
        return round(voltage, 2)
    except Exception as e:
        print("Errore nella lettura del voltaggio:", e)
        
        return round(random.uniform(4.5, 5.2), 2)

STREAM_URL = 'http://192.168.1.103/stream'

def gen_frames():
    try:
        stream = requests.get(STREAM_URL, stream=True, timeout=10)
    except requests.exceptions.RequestException as e:
        print("Errore nella connessione allo stream:", e)
        return

    bytes_data = b''
    global last_unrecognized_alert, last_recognized_alerts
    for chunk in stream.iter_content(chunk_size=1024):
        bytes_data += chunk
        a = bytes_data.find(b'\xff\xd8')
        b = bytes_data.find(b'\xff\xd9')
        if a != -1 and b != -1:
            jpg = bytes_data[a:b+2]
            bytes_data = bytes_data[b+2:]
            frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
            if frame is None:
                continue

            small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
            rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
            
            face_locations = face_recognition.face_locations(rgb_small_frame)
            face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)
            
            current_time = time.time()
            
            for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
                matches = face_recognition.compare_faces(known_face_encodings, face_encoding)
                face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)
                name = "unknown"
                if len(face_distances) > 0:
                    best_match_index = np.argmin(face_distances)
                    if matches[best_match_index]:
                        name = known_face_names[best_match_index].upper()
                
                if name != "unknown":
                    last_time = last_recognized_alerts.get(name, 0)
                    if current_time - last_time > FACE_ALERT_INTERVAL:
                        send_telegram_alert(f"Riconoscimento faccia: {name}")
                        last_recognized_alerts[name] = current_time
                else:
                    if current_time - last_unrecognized_alert > FACE_ALERT_INTERVAL:
                        send_telegram_alert("Alert: Faccia non riconosciuta!")
                        last_unrecognized_alert = current_time

                top, right, bottom, left = top * 4, right * 4, bottom * 4, left * 4
                cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
                cv2.rectangle(frame, (left, bottom - 35), (right, bottom), (0, 255, 0), cv2.FILLED)
                cv2.putText(frame, name, (left + 6, bottom - 6),
                            cv2.FONT_HERSHEY_COMPLEX, 1, (255, 255, 255), 2)
            
            ret, buffer = cv2.imencode('.jpg', frame)
            frame_jpeg = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_jpeg + b'\r\n')

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
        if username == 'ismacarbo' and password == PASSWORD:
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
    return render_template('weather.html',openweather_key=OPENWEATHER_API,windy_key=WINDY_API)

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
    voltage = get_voltage()
    
    if cpu_temp > CPU_TEMP_THRESHOLD:
        send_telegram_alert(f"Alert: CPU temperature is high ({cpu_temp} °C)!")
    if voltage < VOLTAGE_THRESHOLD:
        send_telegram_alert(f"Alert: Batteria/UPS a voltaggio basso ({voltage} V)!")

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
        "voltage": voltage,
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

@app.route('/api/face', methods=['POST'])
def face_recognition_api():
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
    
    if riconoscimento != "unknown" and riconoscimento != "Nessuna faccia":
        send_telegram_alert(f"Riconoscimento faccia (API): {riconoscimento}")
    else:
        send_telegram_alert("Alert (API): Faccia non riconosciuta!")
    
    return jsonify({"status": "success", "message": "Immagine ricevuta e processata", "riconoscimento": riconoscimento}), 200

@app.route('/video_feed')
@token_required
def video_feed(current_user):
    return Response(gen_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/stream_face')
@token_required
def stream_face(current_user):
    return """
    <html>
      <head>
        <title>Stream Riconoscimento Facciale</title>
      </head>
      <body>
        <h1>Stream con riconoscimento facciale</h1>
        <img src="/video_feed" style="width:80%;">
      </body>
    </html>
    """

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
