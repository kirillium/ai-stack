# volumes/assistant/camera_stream.py

import os
from flask import Flask, Response, send_file
from camera_controller import CameraController

PORT = int(os.getenv("CAMERA_STREAM_PORT", "5001"))

app = Flask(__name__)
cam = CameraController("/app/config.yaml")


@app.get("/")
def index():
    return """
    <html>
      <head><title>Camera Stream</title></head>
      <body style="margin:0;background:#111;color:#eee;font-family:sans-serif;">
        <h3 style="padding:12px;">Camera Stream</h3>
        <img src="/stream" style="width:100%;max-width:1280px;" />
      </body>
    </html>
    """


@app.get("/snapshot")
def snapshot():
    ok, path = cam.capture_snapshot()
    if not ok:
        return ("camera error", 500)
    return send_file(path, mimetype="image/jpeg")


@app.get("/stream")
def stream():
    return Response(
        cam.mjpeg_generator(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, threaded=True)
