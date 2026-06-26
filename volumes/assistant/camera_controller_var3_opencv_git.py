# volumes/assistant/camera_controller.py

import cv2
import time
import threading
from pathlib import Path
import yaml


class CameraController:
    def __init__(self, config_path="/app/config.yaml"):
        self.config_path = config_path
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

        cam = self.config.get("camera", {})
        self.device = cam.get("device", 0)
        self.width = cam.get("width", 1280)
        self.height = cam.get("height", 720)
        self.fps = cam.get("fps", 30)
        self.fourcc = cam.get("fourcc", "MJPG")
        self.output_dir = Path(cam.get("output_dir", "/app/audio/camera"))
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.cap = None
        self.lock = threading.Lock()

    def open(self):
        if self.cap is not None and self.cap.isOpened():
            return True

        self.cap = cv2.VideoCapture(self.device)
        if not self.cap.isOpened():
            return False

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_FPS, self.fps)

        if self.fourcc:
            self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*self.fourcc))

        return True

    def close(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None

    def get_frame(self):
        with self.lock:
            if not self.open():
                return False, None

            ret, frame = self.cap.read()
            return ret, frame

    def capture_snapshot(self, filename=None):
        ret, frame = self.get_frame()
        if not ret:
            return False, None

        if filename is None:
            filename = self.output_dir / f"snapshot_{int(time.time())}.jpg"
        else:
            filename = Path(filename)

        cv2.imwrite(str(filename), frame)
        return True, str(filename)

    def mjpeg_generator(self):
        while True:
            ret, frame = self.get_frame()
            if not ret:
                time.sleep(0.1)
                continue

            ok, buf = cv2.imencode(".jpg", frame)
            if not ok:
                time.sleep(0.05)
                continue

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" +
                buf.tobytes() +
                b"\r\n"
            )
