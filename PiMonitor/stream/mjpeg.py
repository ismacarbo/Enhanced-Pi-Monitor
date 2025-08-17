import time, requests, numpy as np, cv2
from utils.telegram import send_telegram_alert
from detectors.yolo_face import detect_and_draw


import os
STREAM_URL = os.getenv("STREAM_URL", "http://192.168.1.103/stream")

OBJ_ALERT_INTERVAL = 30
_last_obj_alerts = {"person": 0.0}

def gen_frames():
    try:
        with requests.get(STREAM_URL, stream=True, timeout=10) as r:
            r.raise_for_status()
            buffer = bytearray()

            for chunk in r.iter_content(chunk_size=4096):
                if not chunk:
                    continue
                buffer.extend(chunk)

                
                while True:
                    start = buffer.find(b'\xff\xd8')  
                    end   = buffer.find(b'\xff\xd9')  
                    if start != -1 and end != -1 and end > start:
                        jpg = bytes(buffer[start:end+2])
                        del buffer[:end+2]

                        frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                        if frame is None:
                            continue

                        
                        target_w = 640
                        if frame.shape[1] > target_w:
                            scale = target_w / frame.shape[1]
                            frame = cv2.resize(frame, (target_w, int(frame.shape[0]*scale)))

                        
                        frame, hits = detect_and_draw(frame)

                        
                        now = time.time()
                        person_detected = any(lbl == "person" and conf >= 0.6 for (lbl, conf, _) in hits)
                        if person_detected and now - _last_obj_alerts["person"] > OBJ_ALERT_INTERVAL:
                            send_telegram_alert("👤 Rilevata PERSONA nel frame")
                            _last_obj_alerts["person"] = now

                        ok, out_jpg = cv2.imencode('.jpg', frame)
                        if not ok:
                            continue

                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + out_jpg.tobytes() + b'\r\n')
                    else:
                        break
    except Exception as e:
        print("Stream error:", e)
        return
