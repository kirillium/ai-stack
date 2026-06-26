import time
from pathlib import Path
import subprocess
import tempfile
import numpy as np
import cv2
import yaml


class CameraController:
    def __init__(self, config_path="/app/config.yaml"):
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

        cam = self.config.get("camera", {})
        self.width = cam.get("width", 1280)
        self.height = cam.get("height", 720)
        self.timeout = cam.get("timeout_ms", 200)
        self.output_dir = Path(cam.get("output_dir", "/app/audio/camera"))
        self.output_dir.mkdir(parents=True, exist_ok=True)

        cascade_name = cam.get("cascade", "haarcascade_frontalface_default.xml")
        self.cascade = cv2.CascadeClassifier(cv2.data.haarcascades + cascade_name)
        if self.cascade.empty():
            raise RuntimeError(f"Не удалось загрузить cascade: {cascade_name}")

        self.label = cam.get("label", "face")
        self.min_size = tuple(cam.get("min_size", [40, 40]))
        self.scale_factor = float(cam.get("scale_factor", 1.1))
        self.min_neighbors = int(cam.get("min_neighbors", 5))

    def get_raw_frame(self):
        tmp = self.output_dir / f"_tmp_{int(time.time() * 1000)}.jpg"
        cmd = [
            "rpicam-jpeg",
            "--output", str(tmp),
            "--width", str(self.width),
            "--height", str(self.height),
            "--timeout", str(self.timeout),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0 or not tmp.exists():
            return False, None

        data = tmp.read_bytes()
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass

        arr = np.frombuffer(data, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        return (frame is not None), frame

    def annotate_frame(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        items = self.cascade.detectMultiScale(
            gray,
            scaleFactor=self.scale_factor,
            minNeighbors=self.min_neighbors,
            minSize=self.min_size,
        )
        for (x, y, w, h) in items:
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(
                frame,
                self.label,
                (x, max(20, y - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2,
            )
        return frame

    def capture_snapshot(self, filename=None):
        ok, frame = self.get_raw_frame()
        if not ok:
            return False, None

        frame = self.annotate_frame(frame)

        if filename is None:
            filename = self.output_dir / f"snapshot_{int(time.time())}.jpg"
        else:
            filename = Path(filename)

        saved = cv2.imwrite(str(filename), frame)
        return saved, str(filename)

    def mjpeg_generator(self):
        while True:
            ok, frame = self.get_raw_frame()
            if not ok:
                time.sleep(0.1)
                continue

            frame = self.annotate_frame(frame)
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
