import time
from pathlib import Path
import subprocess
import numpy as np
import cv2
import yaml


class CameraController:
    def __init__(self, config_path="/app/config.yaml"):
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

        cam = self.config.get("camera", {})
        self.mode = cam.get("mode", "plain")

        self.width = int(cam.get("width", 1280))
        self.height = int(cam.get("height", 720))
        self.timeout = int(cam.get("timeout_ms", 200))
        self.output_dir = Path(cam.get("output_dir", "/app/audio/camera"))
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.face_label = cam.get("face_label", "face")
        self.face_min_size = tuple(cam.get("face_min_size", [40, 40]))
        self.face_scale_factor = float(cam.get("face_scale_factor", 1.1))
        self.face_min_neighbors = int(cam.get("face_min_neighbors", 5))

        cascade_name = cam.get("face_cascade", "haarcascade_frontalface_default.xml")
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + cascade_name)

        self.yolo_model_name = cam.get("yolo_model", "yolov8n.pt")
        self.yolo_imgsz = int(cam.get("yolo_imgsz", 640))
        self.yolo_conf = float(cam.get("yolo_conf", 0.35))
        self.yolo_iou = float(cam.get("yolo_iou", 0.45))
        self.yolo_device = cam.get("yolo_device", "cpu")
        self._yolo = None

    def _load_yolo(self):
        if self._yolo is None:
            from ultralytics import YOLO
            self._yolo = YOLO(self.yolo_model_name)
        return self._yolo

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

    def annotate_plain(self, frame):
        return frame

    def annotate_face(self, frame):
        if self.face_cascade.empty():
            return frame

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=self.face_scale_factor,
            minNeighbors=self.face_min_neighbors,
            minSize=self.face_min_size,
        )

        for (x, y, w, h) in faces:
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(
                frame,
                self.face_label,
                (x, max(20, y - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2,
            )
        return frame

    def annotate_yolo(self, frame):
        model = self._load_yolo()
        results = model.predict(
            source=frame,
            imgsz=self.yolo_imgsz,
            conf=self.yolo_conf,
            iou=self.yolo_iou,
            device=self.yolo_device,
            verbose=False,
        )

        if not results:
            return frame

        r = results[0]
        names = model.names if hasattr(model, "names") else {}

        if r.boxes is None:
            return frame

        for box in r.boxes:
            xyxy = box.xyxy[0].cpu().numpy().astype(int)
            x1, y1, x2, y2 = xyxy.tolist()
            conf = float(box.conf[0].cpu().numpy()) if box.conf is not None else 0.0
            cls = int(box.cls[0].cpu().numpy()) if box.cls is not None else -1
            name = names.get(cls, str(cls))
            label = f"{name} {conf:.2f}"

            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 2)
            cv2.putText(
                frame,
                label,
                (x1, max(20, y1 - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 255),
                2,
            )
        return frame

    def annotate_frame(self, frame):
        if self.mode == "plain":
            return self.annotate_plain(frame)
        if self.mode == "face":
            return self.annotate_face(frame)
        if self.mode == "yolo":
            return self.annotate_yolo(frame)
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
