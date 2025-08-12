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
import occupancyGrid as og
import matplotlib.pyplot as plt
from config import SECRET_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, PASSWORD, OPENWEATHER_API, WINDY_API
import threading, time, subprocess, serial

PORT = "/dev/ttyACM1" 
BAUD=115200
TEMP_ON = 50.0
TEMP_OFF = 45.0


X_MIN, X_MAX = -50,50
Y_MIN, Y_MAX = -50,50
RESOLUTION   = 5

og = og.OccupancyGrid(X_MIN, X_MAX, Y_MIN, Y_MAX, RESOLUTION)


app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
app.url_map.strict_slashes = False

TELEGRAM_BOT_TOKEN = TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID = TELEGRAM_CHAT_ID
ALERT_INTERVAL = 300

sensor_records = []
MAX_RECORDS = 100

CPU_TEMP_THRESHOLD = 70.0
VOLTAGE_THRESHOLD = 4.8

FACE_ALERT_INTERVAL = 30

last_recognized_alerts = {}
last_unrecognized_alert = 0

KNOWN_FACES_DIR = "known_faces"
known_face_encodings = []
known_face_names = []
lidarData=[]

def load_known_faces(directory):
    if not os.path.exists(directory):
        print(f"Directory {directory} not found!")
        return
    for filename in os.listdir(directory):
        if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            path = os.path.join(directory, filename)
            img = cv2.imread(path)
            if img is None:
                print(f"Unable to read image: {filename}")
                continue
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            encs = face_recognition.face_encodings(rgb)
            if encs:
                known_face_encodings.append(encs[0])
                known_face_names.append(os.path.splitext(filename)[0])
                print(f"Loaded encoding for {filename}")
            else:
                print(f"No face found in {filename}")

load_known_faces(KNOWN_FACES_DIR)
print("Reference faces loaded.")


def process_face(image_path):
    image = face_recognition.load_image_file(image_path)
    locs = face_recognition.face_locations(image)
    encs = face_recognition.face_encodings(image, locs)
    if not encs:
        print("No face detected in uploaded image.")
        return "No face"
    enc = encs[0]
    matches = face_recognition.compare_faces(known_face_encodings, enc)
    dists = face_recognition.face_distance(known_face_encodings, enc)
    if dists.size > 0:
        best = np.argmin(dists)
        if matches[best]:
            name = known_face_names[best]
            print(f"Recognized: {name}")
            return name
    print("Unknown face.")
    return "unknown"


def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        resp = requests.post(url, data=payload)
        if resp.status_code == 200:
            print("Telegram alert sent:", message)
        else:
            print("Telegram error:", resp.text)
    except Exception as e:
        print("Exception sending Telegram alert:", e)


def get_voltage():
    try:
        import Adafruit_ADS1x15
        adc = Adafruit_ADS1x15.ADS1115()
        GAIN = 1
        val = adc.read_adc(0, gain=GAIN)
        voltage = val * (4.096 / 32767) * 2
        return round(voltage, 2)
    except Exception as e:
        print("Voltage read error:", e)
        return round(random.uniform(4.5, 5.2), 2)


STREAM_URL = 'http://192.168.1.103/stream'

def gen_frames():
    try:
        stream = requests.get(STREAM_URL, stream=True, timeout=10)
    except Exception as e:
        print("Stream connection error:", e)
        return

    buffer = b''
    global last_unrecognized_alert, last_recognized_alerts
    for chunk in stream.iter_content(chunk_size=1024):
        buffer += chunk
        start = buffer.find(b'\xff\xd8')
        end = buffer.find(b'\xff\xd9')
        if start != -1 and end != -1:
            jpg = buffer[start:end+2]
            buffer = buffer[end+2:]
            frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
            if frame is None:
                continue

            small = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
            rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
            locs = face_recognition.face_locations(rgb)
            encs = face_recognition.face_encodings(rgb, locs)
            now = time.time()

            for (top, right, bottom, left), enc in zip(locs, encs):
                matches = face_recognition.compare_faces(known_face_encodings, enc)
                dists = face_recognition.face_distance(known_face_encodings, enc)
                name = "unknown"
                if dists.size > 0 and matches[np.argmin(dists)]:
                    name = known_face_names[np.argmin(dists)].upper()

                if name != "unknown":
                    last = last_recognized_alerts.get(name, 0)
                    if now - last > FACE_ALERT_INTERVAL:
                        send_telegram_alert(f"Face recognized: {name}")
                        last_recognized_alerts[name] = now
                else:
                    if now - last_unrecognized_alert > FACE_ALERT_INTERVAL:
                        send_telegram_alert("Alert: Unrecognized face!")
                        last_unrecognized_alert = now

                # scale back up for display
                top, right, bottom, left = map(lambda v: v*4, (top, right, bottom, left))
                cv2.rectangle(frame, (left, top), (right, bottom), (0,255,0), 2)
                cv2.rectangle(frame, (left, bottom-35), (right, bottom), (0,255,0), cv2.FILLED)
                cv2.putText(frame, name, (left+6, bottom-6),
                            cv2.FONT_HERSHEY_COMPLEX, 1, (255,255,255), 2)

            _, jpg = cv2.imencode('.jpg', frame)
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + jpg.tobytes() + b'\r\n')


def token_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        token = session.get('jwt')
        if not token:
            return redirect(url_for('login'))
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            user = data['username']
        except:
            return redirect(url_for('login'))
        return f(user, *args, **kwargs)
    return wrapped


@app.route("/")
def home():
    return redirect(url_for("login"))


@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        u = request.form.get('username')
        p = request.form.get('password')
        if u == 'ismacarbo' and p == PASSWORD:
            token = jwt.encode({
                'username': u,
                'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=30)
            }, app.config['SECRET_KEY'], algorithm="HS256")
            session['jwt'] = token
            return redirect(url_for('dashboard'))
        return render_template('login.html', error="Invalid credentials")
    return render_template('login.html')


@app.route('/dashboard')
@token_required
def dashboard(user):
    return render_template('dashboard.html', username=user)


@app.route('/weather')
def weather():
    return render_template('weather.html', openweather_key=OPENWEATHER_API, windy_key=WINDY_API)


@app.route('/portfolio')
def portfolio():
    return render_template('portfolio.html')


@app.route('/api/system', methods=['GET'])
@token_required
def system_info(user):
    try:
        cpu_temp = get_temp_c()
        print(cpu_temp)
    except:
        cpu_temp = 0.0
        print(cpu_temp)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    voltage = get_voltage()
    if cpu_temp > CPU_TEMP_THRESHOLD:
        send_telegram_alert(f"Alert: CPU temp high ({cpu_temp} °C)!")
    if voltage < VOLTAGE_THRESHOLD:
        send_telegram_alert(f"Alert: Low voltage ({voltage} V)!")
    return jsonify({
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
    })


@app.route('/api/network', methods=['GET'])
@token_required
def network_info(user):
    counters = psutil.net_io_counters(pernic=True)
    out = {iface: {
                "bytes_sent": stats.bytes_sent,
                "bytes_recv": stats.bytes_recv,
                "packets_sent": stats.packets_sent,
                "packets_recv": stats.packets_recv
            } for iface, stats in counters.items()}
    return jsonify(out)


@app.route('/api/temperature', methods=['GET'])
def temperature():
    t = request.args.get('temp')
    h = request.args.get('hum')
    if t and h:
        try:
            tv = float(t)
            hv = float(h)
            print(f"Received temp: {tv} °C, hum: {hv} %")
            return jsonify({"status":"success","temperature":tv,"humidity":hv}),200
        except:
            return jsonify({"status":"error","message":"Invalid values"}),400
    return jsonify({"status":"error","message":"Missing params"}),400


@app.route('/api/face', methods=['POST'])
def face_api():
    data = request.get_data()
    if not data:
        return jsonify({"status":"error","message":"No data"}),400
    path = "received_face.jpg"
    try:
        with open(path,"wb") as f:
            f.write(data)
    except Exception as e:
        return jsonify({"status":"error","message":str(e)}),500
    result = process_face(path)
    if result not in ["unknown","No face"]:
        send_telegram_alert(f"Face recognized (API): {result}")
    else:
        send_telegram_alert("Alert (API): Unrecognized face!")
    return jsonify({"status":"success","message":"Processed","recognition":result}),200


@app.route('/video_feed')
@token_required
def video_feed(user):
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/stream_face')
@token_required
def stream_face(user):
    return """
    <html><head><title>Face Stream</title></head>
    <body><h1>Facial Recognition Stream</h1>
    <img src="/video_feed" style="width:80%;">
    </body></html>
    """


@app.route('/api/irrigation_data', methods=['POST'])
def add_irrigation_data():
    payload = request.get_json(force=True)
    try:
        moisture = float(payload.get('moisture'))
        light    = float(payload.get('light'))
    except:
        return jsonify({"status":"error","message":"Invalid payload"}),400

    timestamp = datetime.datetime.utcnow().isoformat()
    sensor_records.append({
        "time": timestamp,
        "moisture": moisture,
        "light": light
    })
    if len(sensor_records) > MAX_RECORDS:
        sensor_records.pop(0)

    if moisture < 50:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": f"💧 Low moisture alert: {moisture:.1f}%"
            }
        )

    return jsonify({"status":"success"}),201


@app.route('/api/irrigation_data', methods=['GET'])
@token_required
def get_irrigation_data(user):
    return jsonify(sensor_records)

@app.route('/api/lidarDatas', methods=['POST'])
def getLidarDatas():
    data = request.get_json(force=True)
    points = data.get('points', [])

    
    scan = [(np.deg2rad(pt['angle']), pt['distance']) for pt in points]

    
    robot_pose = (0.0, 0.0, 0.0)

    og.inverse_sensor_update(robot_pose, scan)
    og.clampLogOdds()
    print(f"payload LiDAR received: {data}")
    return jsonify({"status": "received", "received": data}), 201

@app.route('/api/occupancy_map.json')
def occupancy_map_json():
    return jsonify(og.getProbabilityMap().tolist())

def get_temp_c():
    """Read Raspberry Pi CPU temperature in °C with fallback."""
    try:
        out = subprocess.check_output(["/usr/bin/vcgencmd", "measure_temp"]).decode()
        return float(out.split('=')[1].split("'")[0])
    except Exception as e:
        print(f"[fan] Error reading vcgencmd: {e}. Trying sysfs...", flush=True)
        try:
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                return float(f.read().strip()) / 1000.0
        except Exception as e2:
            print(f"[fan] Error reading sysfs temp: {e2}", flush=True)
            return 0.0

def checkTemp():
    """Thread that controls the fan based on CPU temperature."""
    while True:
        try:
            print(f"[fan] Opening serial on {PORT}...", flush=True)
            with serial.Serial(PORT, BAUD, timeout=1) as ser:
                print("[fan] Serial port opened successfully", flush=True)
                fan_on = False

                while True:
                    t = get_temp_c()
                    print(f"[fan] loop, T={t:.1f}", flush=True)

                    if t >= TEMP_ON:
                        ser.write(b"ON 200\n")  # PWM ~80%
                        if not fan_on:
                            fan_on = True
                            print(f"[fan] Fan ON (T={t:.1f}°C)", flush=True)

                    elif t < TEMP_OFF and fan_on:
                        ser.write(b"OFF\n")
                        fan_on = False
                        print(f"[fan] Fan OFF (T={t:.1f}°C)", flush=True)

                    time.sleep(2)

        except Exception as e:
            print(f"[fan] Serial error: {e}, retrying in 3s", flush=True)
            time.sleep(3)

if __name__ == "__main__":
    threading.Thread(target=checkTemp, daemon=True).start()
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)