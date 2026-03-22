from flask import Flask, render_template, Response, jsonify, request
import json
import os
from gesture_engine import GestureEngine

app = Flask(__name__)
engine = GestureEngine()

def get_config_path():
    return os.path.join(os.path.dirname(__file__), "config.json")

def generate_frames():
    while True:
        frame_bytes = engine.get_frame_bytes()
        if frame_bytes:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/camera')
def camera():
    return render_template('camera.html')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/status', methods=['GET'])
def engine_status():
    return jsonify({"running": engine.running})

@app.route('/api/start', methods=['POST'])
def start_engine():
    engine.start()
    return jsonify({"status": "started", "running": True})

@app.route('/api/stop', methods=['POST'])
def stop_engine():
    engine.stop()
    return jsonify({"status": "stopped", "running": False})

@app.route('/api/config', methods=['GET', 'POST'])
def manage_config():
    if request.method == 'GET':
        try:
            with open(get_config_path(), "r") as f:
                config = json.load(f)
            return jsonify(config)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    if request.method == 'POST':
        try:
            data = request.json
            with open(get_config_path(), "w") as f:
                json.dump(data, f, indent=4)
            # Re-load config in engine immediately
            engine.load_config()
            return jsonify({"status": "success", "config": data})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000, threaded=True)
