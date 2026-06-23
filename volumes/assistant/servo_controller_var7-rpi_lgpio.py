import yaml
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Импорт rpi-lgpio (как rpi_lgpio с underscore)
try:
#    import rpi_lgpio as lgpio
    import rpi_lgpio_nightly as lgpio
    LGPIO_AVAILABLE = True
    logger.info("✅ rpi_lgpio доступен")
except ImportError:
    LGPIO_AVAILABLE = False
    logger.error("❌ rpi_lgpio НЕ доступен — установи в requirements.txt: rpi-lgpio")


class ServoController:
    def __init__(self, config_path='config.yaml'):
        if not LGPIO_AVAILABLE:
            raise ImportError("rpi-lgpio не установлен — добавь в requirements.txt: rpi-lgpio")
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        self.pin = config['servo']['pin']
        self.min_angle = config['servo']['min_angle']
        self.max_angle = config['servo']['max_angle']
        self.move_delay = config['servo']['move_delay']
        self.pwm_frequency = config['servo']['pwm_frequency']
        
        # Инициализация rpi-lgpio
        self.chip = lgpio.chip_open(0)
        lgpio.gpio_claim_output(self.chip, self.pin)
        lgpio.set_pwm_frequency(self.chip, self.pin, self.pwm_frequency)
        lgpio.set_pwm_range(self.chip, self.pin, 1000)
        
        logger.info(f"✅ Сервопривод SG-90 инициализирован на GPIO{self.pin} (rpi_lgpio)")
    
    def set_angle(self, angle):
        if angle < self.min_angle:
            angle = self.min_angle
        if angle > self.max_angle:
            angle = self.max_angle
        
        pwm_value = 100 + (angle / 180.0) * 800
        lgpio.set_pwm_value(self.chip, self.pin, int(pwm_value))
        time.sleep(self.move_delay)
    
    def turn_right(self, angle=120):
        self.set_angle(angle)
    
    def turn_left(self, angle=60):
        self.set_angle(angle)
    
    def reset(self):
        self.set_angle(90)
    
    def cleanup(self):
        lgpio.set_pwm_value(self.chip, self.pin, 0)
        lgpio.gpio_free(self.chip, self.pin)
        lgpio.chip_close(self.chip)


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
