import os
import time
from pathlib import Path
import subprocess

import cv2
import numpy as np
import yaml

os.environ.setdefault("YOLO_CONFIG_DIR", "/tmp/ultralytics")


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
        self.yolo_log_detections = bool(cam.get("yolo_log_detections", True))
        self.yolo_log_cooldown_sec = float(cam.get("yolo_log_cooldown_sec", 2.0))
        self._last_yolo_log = 0.0
        self._last_yolo_items = set()
        self._yolo = None

        self.fr_target_path = Path(cam.get("face_recognition_target", "/app/targets/target.jpg"))
        self.fr_tolerance = float(cam.get("face_recognition_tolerance", 0.45))
        self.fr_model = cam.get("face_recognition_model", "hog")
        self.fr_label = cam.get("face_recognition_label", "target_match")
        self._fr = None
        self.target_encodings = []
        self._fr_target_loaded = False

        print(f"[camera] mode={self.mode}")
        if self.mode == "face":
            print(f"[camera] face cascade={cascade_name} label={self.face_label}")
        elif self.mode == "yolo":
            print(
                f"[camera] yolo model={self.yolo_model_name} "
                f"conf={self.yolo_conf} iou={self.yolo_iou} device={self.yolo_device}"
            )
        elif self.mode == "face_recognition":
            print(f"[camera] face_recognition target={self.fr_target_path} tolerance={self.fr_tolerance}")

    def _load_yolo(self):
        if self._yolo is None:
            from ultralytics import YOLO
            self._yolo = YOLO(self.yolo_model_name)
        return self._yolo

    def _load_face_recognition(self):
        if self._fr is None:
            import face_recognition
            self._fr = face_recognition
        return self._fr

    def _load_target_encodings(self):
        if not self.fr_target_path.exists():
            print(f"[face_recognition] target not found: {self.fr_target_path}")
            self.target_encodings = []
            self._fr_target_loaded = False
            return False

        try:
            fr = self._load_face_recognition()
        except Exception as e:
            print(f"[face_recognition] import error: {e}")
            self.target_encodings = []
            self._fr_target_loaded = False
            return False

        img = fr.load_image_file(str(self.fr_target_path))
        locations = fr.face_locations(img, model=self.fr_model)
        encodings = fr.face_encodings(img, locations)

        self.target_encodings = encodings
        self._fr_target_loaded = len(encodings) > 0
        print(
            f"[face_recognition] target encodings loaded="
            f"{self._fr_target_loaded} count={len(encodings)}"
        )
        return self._fr_target_loaded

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
            err = (proc.stderr or proc.stdout or "").strip()
            if err:
                print(f"[camera] rpicam-jpeg failed: {err}")
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
            print("[camera] face cascade is empty")
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

        detected = set()

        for box in r.boxes:
            xyxy = box.xyxy[0].cpu().numpy().astype(int)
            x1, y1, x2, y2 = xyxy.tolist()
            conf = float(box.conf[0].cpu().numpy()) if box.conf is not None else 0.0
            cls = int(box.cls[0].cpu().numpy()) if box.cls is not None else -1
            name = names.get(cls, str(cls))
            label = f"{name} {conf:.2f}"

            detected.add(name)

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

        now = time.time()
        if self.yolo_log_detections and detected:
            if (
                now - self._last_yolo_log >= self.yolo_log_cooldown_sec
                or detected != self._last_yolo_items
            ):
                print(f"[yolo] found: {', '.join(sorted(detected))}")
                self._last_yolo_log = now
                self._last_yolo_items = set(detected)

        return frame

    def annotate_face_recognition(self, frame):
        try:
            fr = self._load_face_recognition()
        except Exception as e:
            print(f"[face_recognition] import error: {e}")
            cv2.putText(
                frame,
                "face_recognition unavailable",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 0, 255),
                2,
            )
            return frame

        if not self._fr_target_loaded:
            if not self._load_target_encodings():
                cv2.putText(
                    frame,
                    "target not loaded",
                    (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 0, 255),
                    2,
                )
                return frame

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        locations = fr.face_locations(rgb, model=self.fr_model)
        encodings = fr.face_encodings(rgb, locations)

        for (top, right, bottom, left), enc in zip(locations, encodings):
            matches = fr.compare_faces(self.target_encodings, enc, tolerance=self.fr_tolerance)
            distances = fr.face_distance(self.target_encodings, enc)

            matched = bool(matches and any(matches))
            label = self.fr_label if matched else "unknown"
            color = (0, 255, 0) if matched else (0, 0, 255)

            cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
            cv2.putText(
                frame,
                label,
                (left, max(20, top - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                color,
                2,
            )

            if matched:
                best = float(np.min(distances)) if len(distances) else 1.0
                print(f"[face_recognition] MATCH {label} distance={best:.3f}")

        return frame

    def annotate_frame(self, frame):
        if self.mode == "plain":
            return self.annotate_plain(frame)
        if self.mode == "face":
            return self.annotate_face(frame)
        if self.mode == "yolo":
            return self.annotate_yolo(frame)
        if self.mode == "face_recognition":
            return self.annotate_face_recognition(frame)
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
