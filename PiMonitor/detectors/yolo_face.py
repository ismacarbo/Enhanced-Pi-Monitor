import os, time, threading, numpy as np, cv2, face_recognition
from pathlib import Path
from ultralytics import YOLO



yolo = YOLO("yolov8n.pt")


TOLERANCE = 0.5  
BASE = Path(__file__).resolve().parent.parent
KNOWN_FACES_DIR = str(BASE / "known_faces")

known_face_encodings = []
known_face_names = []


_last_face_crop_jpg = None
_last_face_lock = threading.Lock()

def _load_known_faces(directory: str):
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
        return
    for filename in os.listdir(directory):
        if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            path = os.path.join(directory, filename)
            img = cv2.imread(path)
            if img is None:
                continue
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            encs = face_recognition.face_encodings(rgb)
            if encs:
                known_face_encodings.append(encs[0])
                name = os.path.splitext(filename)[0]
                
                if "_" in name:
                    name = name.split("_")[0]
                known_face_names.append(name)

_load_known_faces(KNOWN_FACES_DIR)

def detect_and_draw(frame):
    """
    Esegue:
    - Object detection con YOLO (tutte le classi)
    - Se trova "person", cerca un volto nel ROI con face_recognition
    - Disegna box + label oggetti e volto
    - Aggiorna _last_face_crop_jpg con il volto migliore del frame
    Ritorna: frame_disegnato, hits = [(label, conf, (x1,y1,x2,y2)), ...]
    """
    results = yolo.predict(source=frame, imgsz=640, conf=0.5, iou=0.45, verbose=False)[0]

    hits = []
    H, W = frame.shape[:2]
    best_face_area = 0
    best_face_jpg = None

    
    for box in results.boxes:
      cls_id = int(box.cls[0])
      conf   = float(box.conf[0])
      x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
      label = yolo.names[cls_id]
      hits.append((label, conf, (x1, y1, x2, y2)))
      cv2.rectangle(frame, (x1, y1), (x2, y2), (0,255,0), 2)
      txt = f"{label} {conf*100:.1f}%"
      ytxt = y1 - 10 if y1 - 10 > 10 else y1 + 20
      cv2.putText(frame, txt, (x1, ytxt), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2)

    
    for (label, conf, (x1, y1, x2, y2)) in hits:
        if label != "person":
            continue
        x1c, y1c = max(0, x1), max(0, y1)
        x2c, y2c = min(W-1, x2), min(H-1, y2)
        if x2c <= x1c or y2c <= y1c:
            continue
        roi = frame[y1c:y2c, x1c:x2c]
        if roi.size == 0:
            continue

        rgb = cv2.cvtColor(roi, cv2.COLOR_BGR2RGB)
        face_locs = face_recognition.face_locations(rgb, model='hog')  
        encs = face_recognition.face_encodings(rgb, face_locs)

        for (top, right, bottom, left), enc in zip(face_locs, encs):
            top    += y1c; bottom += y1c; left += x1c; right += x1c

            name = "unknown"
            if known_face_encodings:
                dists = face_recognition.face_distance(known_face_encodings, enc)
                j = int(np.argmin(dists))
                if dists[j] < TOLERANCE:
                    name = known_face_names[j]

            cv2.rectangle(frame, (left, top), (right, bottom), (0,180,255), 2)
            tag = f"{name}"
            ytag = top - 10 if top - 10 > 10 else top + 20
            cv2.putText(frame, tag, (left, ytag), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 2)

            area = (right - left) * (bottom - top)
            if area > best_face_area:
                best_face_area = area
                face_crop = frame[top:bottom, left:right]
                ok, jpg = cv2.imencode(".jpg", face_crop)
                if ok:
                    best_face_jpg = jpg.tobytes()

    if best_face_jpg is not None:
        with _last_face_lock:
            global _last_face_crop_jpg
            _last_face_crop_jpg = best_face_jpg

    return frame, hits

def get_last_face_jpg():
    with _last_face_lock:
        return _last_face_crop_jpg

def register_face_from_last(name: str):
    """
    Salva l'ultimo face-crop in known_faces/ con etichetta 'name'
    e aggiorna le liste in RAM per il riconoscimento.
    """
    data = get_last_face_jpg()
    if not data:
        return False, "No face available"
    os.makedirs(KNOWN_FACES_DIR, exist_ok=True)
    path = os.path.join(KNOWN_FACES_DIR, f"{name}_{int(time.time())}.jpg")
    with open(path, "wb") as f:
        f.write(data)

    img = face_recognition.load_image_file(path)
    locs = face_recognition.face_locations(img, model='hog')
    encs = face_recognition.face_encodings(img, locs)
    if not encs:
        try: os.remove(path)
        except: pass
        return False, "No face found"

    known_face_encodings.append(encs[0])
    known_face_names.append(name)
    return True, path

def register_face_from_upload(file_bytes: bytes, name: str):
    os.makedirs(KNOWN_FACES_DIR, exist_ok=True)
    path = os.path.join(KNOWN_FACES_DIR, f"{name}_{int(time.time())}.jpg")
    with open(path, "wb") as f:
        f.write(file_bytes)

    img = face_recognition.load_image_file(path)
    locs = face_recognition.face_locations(img, model='hog')
    encs = face_recognition.face_encodings(img, locs)
    if not encs:
        try: os.remove(path)
        except: pass
        return False, "No face found"
    known_face_encodings.append(encs[0])
    known_face_names.append(name)
    return True, path
