import subprocess
import yaml
from miio.exceptions import DeviceException, DeviceInfoUnavailableException, PayloadDecodeException


class CleanerController:
    def __init__(self, config_path="config.yaml"):
        self.config_path = config_path
        self.config = self._load_config()
        self.vacuum_cfg = self.config.get("vacuum", {})
        self.device = None
        self.device_class_name = None

    def _load_config(self):
        with open(self.config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def _get_ip_token(self):
        ip = self.vacuum_cfg.get("ip")
        token = self.vacuum_cfg.get("token")
        if not ip or not token or token == "PUT_TOKEN_HERE":
            raise ValueError("Не заданы ip/token пылесоса")
        return ip, token

    def _get_device_class(self):
        model = (self.vacuum_cfg.get("model") or "").lower()

        if model.startswith("roborock"):
            from miio import RoborockVacuum
            return RoborockVacuum, "RoborockVacuum"

        if model.startswith("viomi"):
            from miio import ViomiVacuum
            return ViomiVacuum, "ViomiVacuum"

        if model in ("g1", "g1vacuum", "xiaomi-vacuum-g1"):
            from miio import G1Vacuum
            return G1Vacuum, "G1Vacuum"

        return None, None

    def connect(self):
        ip, token = self._get_ip_token()

        device_cls, device_name = self._get_device_class()
        if device_cls is not None:
            self.device = device_cls(ip, token)
            self.device_class_name = device_name
            return self.device

        from miio.device import Device
        self.device = Device(ip, token)
        self.device_class_name = "Device"
        return self.device

    def status(self):
        return (self.device or self.connect()).status()

    def start(self):
        return (self.device or self.connect()).start()

    def stop(self):
        return (self.device or self.connect()).stop()

    def info(self):
        dev = self.device or self.connect()
        return dev.info()

    def discover(self):
        cmd = ["docker", "exec", "-it", "ai-miio-tool", "sh", "-lc", "miio discover --sync"]
        return subprocess.run(cmd, capture_output=True, text=True, timeout=180)

    def debug_connect(self):
        try:
            self.connect()
            return True, f"Подключено: {self.device_class_name}"
        except Exception as e:
            return False, str(e)

    def debug_info(self):
        try:
            return True, str(self.info())
        except ValueError as e:
            return False, f"config error: {e}"
        except DeviceInfoUnavailableException as e:
            return False, f"device info unavailable: {e}"
        except PayloadDecodeException as e:
            return False, f"payload decode error: {e}"
        except DeviceException as e:
            return False, f"device error: {e}"
        except Exception as e:
            return False, f"unexpected error: {e}"

    def debug_status(self):
        try:
            return True, str(self.status())
        except ValueError as e:
            return False, f"config error: {e}"
        except DeviceInfoUnavailableException as e:
            return False, f"device info unavailable: {e}"
        except PayloadDecodeException as e:
            return False, f"payload decode error: {e}"
        except DeviceException as e:
            return False, f"device error: {e}"
        except Exception as e:
            return False, f"unexpected error: {e}"

    def debug_start(self):
        try:
            result = self.start()
            return True, f"start ok: {result}"
        except ValueError as e:
            return False, f"config error: {e}"
        except DeviceInfoUnavailableException as e:
            return False, f"device info unavailable: {e}"
        except PayloadDecodeException as e:
            return False, f"payload decode error: {e}"
        except DeviceException as e:
            return False, f"device error: {e}"
        except Exception as e:
            return False, f"unexpected error: {e}"

    def debug_stop(self):
        try:
            result = self.stop()
            return True, f"stop ok: {result}"
        except ValueError as e:
            return False, f"config error: {e}"
        except DeviceInfoUnavailableException as e:
            return False, f"device info unavailable: {e}"
        except PayloadDecodeException as e:
            return False, f"payload decode error: {e}"
        except DeviceException as e:
            return False, f"device error: {e}"
        except Exception as e:
            return False, f"unexpected error: {e}"
