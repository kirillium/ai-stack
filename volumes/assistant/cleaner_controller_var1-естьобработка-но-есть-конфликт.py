import subprocess
import yaml
from pathlib import Path
from miio import DeviceFactory

dev = DeviceFactory.create(ip, token)

class CleanerController:
    def __init__(self, config_path="config.yaml"):
        self.config_path = config_path
        self.config = self._load_config()
        self.vacuum_cfg = self.config.get("vacuum", {})
        self.device = None

    def _load_config(self):
        with open(self.config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def _get_ip_token(self):
        ip = self.vacuum_cfg.get("ip")
        token = self.vacuum_cfg.get("token")
        if not ip or not token:
            raise ValueError("Не заданы vacuum.ip или vacuum.token в config.yaml")
        return ip, token

    def connect(self):
        ip, token = self._get_ip_token()
        model = self.vacuum_cfg.get("model")
        self.device = DeviceFactory.create(ip, token, model=model)
        return self.device

    def status(self):
        dev = self.device or self.connect()
        return dev.status()

    def start(self):
        dev = self.device or self.connect()
        return dev.start()

    def stop(self):
        dev = self.device or self.connect()
        return dev.stop()

    def discover(self):
        if not self.vacuum_cfg.get("discover", {}).get("enabled", True):
            return "Discovery disabled"
        cmd = ["docker", "exec", "miio-tool", "sh", "-lc", "miio discover --sync"]
        return subprocess.run(cmd, capture_output=True, text=True, timeout=self.vacuum_cfg.get("discover", {}).get("timeout_sec", 180))

def debug_discover(self):
    cmd = ["docker", "exec", "miio-tool", "sh", "-lc", "miio discover --sync"]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=180)

def debug_status(self):
    return self.status()

def debug_start(self):
    return self.start()

def debug_stop(self):
    return self.stop()	
