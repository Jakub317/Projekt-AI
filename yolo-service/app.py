import io
import os
from flask import Flask, request, jsonify
from ultralytics import YOLO
from PIL import Image

app = Flask(__name__)
MODEL_PATH = "/var/www/yolo-service/models/best.pt"
model = None

def load_model():
    global model
    if os.path.exists(MODEL_PATH):
        print(f"Ładowanie modelu z {MODEL_PATH}...")
        model = YOLO(MODEL_PATH)
        print("Model załadowany.")
    else:
        print("Brak modelu. Oczekiwanie na upload z portalu.")

load_model()

@app.route("/reload", methods=["POST"])
def reload():
    try:
        load_model()
        return jsonify({"status": "ok", "message": "Model przeładowany"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/detect", methods=["POST"])
def detect():
    if model is None:
        return jsonify({"error": "Brak załadowanego modelu"}), 503
    if "file" not in request.files:
        return jsonify({"error": "Brak pliku"}), 400
    
    file = request.files["file"]
    try:
        img = Image.open(io.BytesIO(file.read()))
        results = model.predict(img, conf=0.25, verbose=False)
        frames = []
        if results and len(results) > 0:
            for box in results[0].boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                frames.append({
                    "x": int(x1), "y": int(y1),
                    "w": int(x2 - x1), "h": int(y2 - y1),
                    "confidence": round(float(box.conf[0]), 2)
                })
        return jsonify({"frames": frames})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=9000)
