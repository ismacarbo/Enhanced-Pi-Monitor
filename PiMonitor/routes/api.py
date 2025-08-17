from flask import request, jsonify, Response, redirect, url_for
from auth import token_required
from utils.sensors import get_voltage, get_temp_c
import psutil, datetime, os
from utils.names import sanitize_name
from detectors.yolo_face import get_last_face_jpg, register_face_from_last, register_face_from_upload
from occupancy.state import update_from_points, get_probability_map
from utils.telegram import send_telegram_alert


sensor_records = []
MAX_RECORDS = 100

CPU_TEMP_THRESHOLD = 70.0
VOLTAGE_THRESHOLD  = 4.8

def register_api_routes(app):
    @app.route('/api/system', methods=['GET'])
    @token_required
    def system_info(user):
        try:
            cpu_temp = get_temp_c()
        except Exception:
            cpu_temp = 0.0
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
                "total": mem.total, "used": mem.used, "free": mem.free, "percent": mem.percent
            },
            "disk": {
                "total": disk.total, "used": disk.used, "free": disk.free, "percent": disk.percent
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
        t = request.args.get('temp'); h = request.args.get('hum')
        if t and h:
            try:
                tv = float(t); hv = float(h)
                print(f"Received temp: {tv} °C, hum: {hv} %")
                return jsonify({"status":"success","temperature":tv,"humidity":hv}), 200
            except Exception:
                return jsonify({"status":"error","message":"Invalid values"}), 400
        return jsonify({"status":"error","message":"Missing params"}), 400

    
    @app.route('/api/face', methods=['POST'])
    def face_api():
        data = request.get_data()
        if not data:
            return jsonify({"status":"error","message":"No data"}), 400
        
        
        ok, msg = register_face_from_upload(data, name='api')
        if ok:
            send_telegram_alert(f"Face registered (API): api")
            return jsonify({"status":"success","message":"Registered","recognition":"api"}), 200
        else:
            send_telegram_alert("Alert (API): No face in upload!")
            return jsonify({"status":"error","message":msg}), 400

    
    @app.route('/last_face.jpg')
    def last_face():
        data = get_last_face_jpg()
        if not data:
            return "No face captured yet", 404
        return Response(data, mimetype='image/jpeg')

    @app.route('/register', methods=['GET','POST'])
    def register():
        if request.method == 'POST':
            name = sanitize_name(request.form.get('name', ''))
            if not name:
                return "Missing name", 400
            ok, msg = register_face_from_last(name)
            if not ok:
                return f"Error: {msg}", 400
            return redirect(url_for('register_success', who=name))
        
        return """
        <html><head><title>Register Face</title></head>
        <body>
          <h1>Register Face</h1>
          <div>
            <p>Ultimo volto catturato dallo stream (se disponibile):</p>
            <img src="/last_face.jpg" style="max-width:320px; border:1px solid 
                 onerror="this.replaceWith(document.createTextNode('Nessun volto catturato'));" />
          </div>
          <form method="POST" style="margin-top:20px">
            <label>Nome (etichetta): <input name="name" required /></label>
            <button type="submit">Salva volto</button>
          </form>
          <p style="margin-top:10px"><a href="/objects">↩ Torna allo stream</a></p>
        </body></html>
        """

    @app.route('/register_success')
    def register_success():
        who = request.args.get('who', 'utente')
        return f"Registrato: {who}. Ora sarà riconosciuto nello stream."

    @app.route('/api/register_face', methods=['POST'])
    def api_register_face():
        name = sanitize_name(request.form.get('name',''))
        file = request.files.get('image')
        if not name or not file:
            return jsonify({"status":"error","message":"name or image missing"}), 400
        ok, msg = register_face_from_upload(file.read(), name)
        if ok:
            return jsonify({"status":"success","name":name})
        else:
            return jsonify({"status":"error","message":msg}), 400

    
    @app.route('/api/irrigation_data', methods=['POST'])
    def add_irrigation_data():
        payload = request.get_json(force=True)
        try:
            moisture = float(payload.get('moisture'))
            light    = float(payload.get('light'))
        except Exception:
            return jsonify({"status":"error","message":"Invalid payload"}), 400

        timestamp = datetime.datetime.utcnow().isoformat()
        sensor_records.append({"time": timestamp, "moisture": moisture, "light": light})
        if len(sensor_records) > MAX_RECORDS:
            sensor_records.pop(0)

        if moisture < 50:
            from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID  
            send_telegram_alert(f"💧 Low moisture alert: {moisture:.1f}%")

        return jsonify({"status":"success"}), 201

    @app.route('/api/irrigation_data', methods=['GET'])
    @token_required
    def get_irrigation_data(user):
        return jsonify(sensor_records)

    
    @app.route('/api/lidarDatas', methods=['POST'])
    def getLidarDatas():
        data = request.get_json(force=True)
        points = data.get('points', [])
        update_from_points(points)
        print(f"payload LiDAR received: {data}")
        return jsonify({"status": "received", "received": data}), 201

    @app.route('/api/occupancy_map.json')
    def occupancy_map_json():
        return jsonify(get_probability_map())
