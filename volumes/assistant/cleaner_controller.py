import subprocess
import yaml
#from miio import DeviceFactory

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
            raise ValueError("Не заданы vacuum.ip или vacuum.token")
        return ip, token

    def connect(self):
        ip, token = self._get_ip_token()
        self.device = DeviceFactory.create(ip, token)
        return self.device

    def status(self):
        return (self.device or self.connect()).status()

    def start(self):
        return (self.device or self.connect()).start()

    def stop(self):
        return (self.device or self.connect()).stop()

    def discover(self):
        cmd = ["docker", "exec", "-it", "ai-miio-tool", "sh", "-lc", "miio discover --sync"]
        return subprocess.run(cmd, capture_output=True, text=True, timeout=180)
