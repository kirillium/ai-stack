# volumes/assistant/camera_controller.py

import time
import threading
import subprocess
from pathlib import Path
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

        self.lock = threading.Lock()
        print(f"[camera] rpicam-jpeg mode width={self.width} height={self.height} timeout={self.timeout}ms")

    def capture_snapshot(self, filename=None):
        if filename is None:
            filename = self.output_dir / f"snapshot_{int(time.time())}.jpg"
        else:
            filename = Path(filename)

        cmd = [
            "rpicam-jpeg",
            "--output", str(filename),
            "--width", str(self.width),
            "--height", str(self.height),
            "--timeout", str(self.timeout),
        ]

        print(f"[camera] running: {' '.join(cmd)}")
        proc = subprocess.run(cmd, capture_output=True, text=True)

        if proc.returncode != 0:
            print(f"[camera] rpicam-jpeg failed rc={proc.returncode}")
            if proc.stdout:
                print(f"[camera] stdout: {proc.stdout.strip()}")
            if proc.stderr:
                print(f"[camera] stderr: {proc.stderr.strip()}")
            return False, None

        if not filename.exists() or filename.stat().st_size == 0:
            print("[camera] snapshot file missing or empty")
            return False, None

        print(f"[camera] snapshot saved: {filename}")
        return True, str(filename)

    def mjpeg_generator(self):
        while True:
            ok, path = self.capture_snapshot()
            if not ok:
                time.sleep(0.5)
                continue

            try:
                with open(path, "rb") as f:
                    jpeg = f.read()
            except Exception as e:
                print(f"[camera] read snapshot failed: {e}")
                time.sleep(0.2)
                continue

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" +
                jpeg +
                b"\r\n"
            )

            time.sleep(0.1)
