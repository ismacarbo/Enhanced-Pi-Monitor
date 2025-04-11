import cv2
import requests
import numpy as np
import os
import face_recognition


path = r'/home/isma/Desktop/attendace'

stream_url = 'http://192.168.1.112/stream'


images = []
classNames = []
myList = os.listdir(path)
print("Immagini trovate:", myList)
for file in myList:
    img = cv2.imread(os.path.join(path, file))
    if img is not None:
        images.append(img)
        classNames.append(os.path.splitext(file)[0])
    else:
        print("Errore nel caricamento dell'immagine:", file)
print("Class names:", classNames)

def findEncodings(images):
    encodeList = []
    for img in images:
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        encodes = face_recognition.face_encodings(img_rgb)
        if encodes:
            encodeList.append(encodes[0])
        else:
            print("Nessuna faccia rilevata per un'immagine di riferimento.")
    return encodeList

known_encodings = findEncodings(images)
print("Encoding Complete")


r = requests.get(stream_url, stream=True)
bytes_data = b''

while True:
    try:
        
        for chunk in r.iter_content(chunk_size=1024):
            bytes_data += chunk
            
            start = bytes_data.find(b'\xff\xd8')
            end = bytes_data.find(b'\xff\xd9')
            if start != -1 and end != -1:
                jpg = bytes_data[start:end+2]
                bytes_data = bytes_data[end+2:]
                
                img = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                if img is None:
                    continue

                
                img_small = cv2.resize(img, (0, 0), fx=0.25, fy=0.25)
                img_small_rgb = cv2.cvtColor(img_small, cv2.COLOR_BGR2RGB)

                
                facesCurFrame = face_recognition.face_locations(img_small_rgb)
                encodesCurFrame = face_recognition.face_encodings(img_small_rgb, facesCurFrame)

                
                for encodeFace, faceLoc in zip(encodesCurFrame, facesCurFrame):
                    matches = face_recognition.compare_faces(known_encodings, encodeFace)
                    faceDis = face_recognition.face_distance(known_encodings, encodeFace)
                    matchIndex = np.argmin(faceDis)
                    
                    if matches[matchIndex]:
                        name = classNames[matchIndex].upper()
                        y1, x2, y2, x1 = faceLoc
                        
                        y1, x2, y2, x1 = y1 * 4, x2 * 4, y2 * 4, x1 * 4
                        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        cv2.rectangle(img, (x1, y2 - 35), (x2, y2), (0, 255, 0), cv2.FILLED)
                        cv2.putText(img, name, (x1 + 6, y2 - 6), cv2.FONT_HERSHEY_COMPLEX, 
                                    1, (255, 255, 255), 2)

                cv2.imshow('Stream', img)
                
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    raise KeyboardInterrupt  
    except KeyboardInterrupt:
        print("Chiusura stream.")
        break
    except Exception as e:
        print("Errore nel processing dello stream:", e)
        break

cv2.destroyAllWindows()
