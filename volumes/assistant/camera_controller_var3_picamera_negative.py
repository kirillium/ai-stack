# volumes/assistant/camera_controller.py

import time
import threading
from pathlib import Path
import yaml
import cv2

try:
    from picamera2 import Picamera2
    PICAMERA2_AVAILABLE = True
except ImportError:
    PICAMERA2_AVAILABLE = False


class CameraController:
    def __init__(self, config_path="/app/config.yaml"):
        self.config_path = config_path
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

        cam = self.config.get("camera", {})
        self.width = cam.get("width", 1280)
        self.height = cam.get("height", 720)
        self.fps = cam.get("fps", 30)
        self.output_dir = Path(cam.get("output_dir", "/app/audio/camera"))
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.lock = threading.Lock()
        self.picam2 = None

    def open(self):
        if not PICAMERA2_AVAILABLE:
            raise ImportError("picamera2 не установлен")

        if self.picam2 is not None:
            return True

        self.picam2 = Picamera2()
        config = self.picam2.create_preview_configuration(
            main={"size": (self.width, self.height), "format": "RGB888"}
        )
        self.picam2.configure(config)
        self.picam2.start()
        time.sleep(0.5)
        return True

    def close(self):
        if self.picam2 is not None:
            self.picam2.stop()
            self.picam2.close()
            self.picam2 = None

    def get_frame(self):
        with self.lock:
            if self.picam2 is None:
                self.open()

            frame = self.picam2.capture_array()
            if frame is None:
                return False, None

            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            return True, frame_bgr

    def capture_snapshot(self, filename=None):
        ret, frame = self.get_frame()
        if not ret:
            return False, None

        if filename is None:
            filename = self.output_dir / f"snapshot_{int(time.time())}.jpg"

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
