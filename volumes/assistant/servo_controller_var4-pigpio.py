import yaml
import time
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Установка режима soft для pigpio (локальный, без daemon)
os.environ['PIGPIO_ADDR'] = 'soft'
os.environ['PIGPIO_PORT'] = '8888'

# Импорт pigpio
try:
    import pigpio
    PIGPIO_AVAILABLE = True
    logger.info("✅ pigpio доступен")
except ImportError:
    PIGPIO_AVAILABLE = False
    logger.error("❌ pigpio НЕ доступен — установи в requirements.txt: pigpio")


class ServoController:
    def __init__(self, config_path='config.yaml'):
        if not PIGPIO_AVAILABLE:
            raise ImportError("pigpio не установлен — добавь в requirements.txt: pigpio")
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        self.pin = config['servo']['pin']
        self.min_angle = config['servo']['min_angle']
        self.max_angle = config['servo']['max_angle']
        self.move_delay = config['servo']['move_delay']
        
        # Инициализация pigpio в режиме 'soft' (локальный)
        self.pi = pigpio.pi('soft')  # ← НОВЫЙ КОД: pigpio.pi('soft'), не pigpio.Pi()
        
        if self.pi < 0:
            raise RuntimeError("Не удалось подключиться к pigpio")
        
        # Установка режима PWM (1 = PWM, не pigio.PWM)
        self.pi.set_mode(self.pin, 1)
        self.pi.set_PWM_frequency(self.pin, 50)
        self.pi.set_PWM_range(self.pin, 1000)
        
        logger.info(f"✅ Сервопривод SG-90 инициализирован на GPIO{self.pin} (pigpio soft)")
    
    def set_angle(self, angle):
        if angle < self.min_angle:
            angle = self.min_angle
        if angle > self.max_angle:
            angle = self.max_angle
        
        pwm_value = 100 + (angle / 180.0) * 800
        self.pi.set_PWM_dutycycle(self.pin, int(pwm_value))
        time.sleep(self.move_delay)
    
    def turn_right(self, angle=120):
        self.set_angle(angle)
        logger.info(f"🔄 Вправо на {angle}°")
    
    def turn_left(self, angle=60):
        self.set_angle(angle)
        logger.info(f"🔄 Влево на {angle}°")
    
    def reset(self):
        self.set_angle(90)
        logger.info("🎯 В центр (90°)")
    
    def cleanup(self):
        if PIGPIO_AVAILABLE and self.pi >= 0:
            self.pi.set_PWM_dutycycle(self.pin, 0)
            self.pi.stop()
            logger.info("🔌 Отключен")


if __name__ == '__main__':
    servo = ServoController()
    try:
        servo.turn_left()
        time.sleep(1)
        servo.reset()
        time.sleep(1)
        servo.turn_right()
        time.sleep(1)
        servo.reset()
    finally:
        servo.cleanup()
