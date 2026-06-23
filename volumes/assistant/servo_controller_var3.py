import yaml
import time
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Явно указать native backend для gpiozero
os.environ['GPIOZERO_PINFACTORY'] = 'native'

try:
    from gpiozero import Servo
    GPIOZERO_AVAILABLE = True
    logger.info("✅ gpiozero доступен")
except ImportError:
    GPIOZERO_AVAILABLE = False
    logger.error("❌ gpiozero НЕ доступен")


class ServoController:
    def __init__(self, config_path='config.yaml'):
        if not GPIOZERO_AVAILABLE:
            raise ImportError("gpiozero не установлен — добавь в requirements.txt: gpiozero")
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        self.pin = config['servo']['pin']
        self.min_angle = config['servo']['min_angle']
        self.max_angle = config['servo']['max_angle']
        self.move_delay = config['servo']['move_delay']
        
        try:
            self.servo = Servo(self.pin)
            logger.info(f"✅ Сервопривод SG-90 инициализирован на GPIO{self.pin}")
        except Exception as e:
            logger.error(f"❌Ошибка инициализации: {e}")
            raise
    
    def set_angle(self, angle):
        if angle < self.min_angle: angle = self.min_angle
        if angle > self.max_angle: angle = self.max_angle
        
        self.servo.value = (angle - self.min_angle) / (self.max_angle - self.min_angle)
        time.sleep(self.move_delay)
    
    def turn_right(self, angle=120):
        self.set_angle(angle)
    
    def turn_left(self, angle=60):
        self.set_angle(angle)
    
    def reset(self):
        self.set_angle(90)
    
    def cleanup(self):
        if GPIOZERO_AVAILABLE and self.servo:
            self.servo.off()
