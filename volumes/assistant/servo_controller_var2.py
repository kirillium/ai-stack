import yaml
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Импорт lgpio напрямую
try:
    from rpi-lgpio import LGPIO
    lgpio = LGPIO()
#    import lgpio
    LGPIO_AVAILABLE = True
    logger.info("✅ lgpio доступен")
except ImportError:
    LGPIO_AVAILABLE = False
    logger.error("❌ lgpio НЕ доступен — установи в Dockerfile: pip install lgpio")


class ServoController:
    def __init__(self, config_path='config.yaml'):
        if not LGPIO_AVAILABLE:
            raise ImportError("lgpio не установлен — добавь в Dockerfile: pip install lgpio")
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        self.pin = config['servo']['pin']
        self.min_angle = config['servo']['min_angle']
        self.max_angle = config['servo']['max_angle']
        self.move_delay = config['servo']['move_delay']
        self.pwm_frequency = config['servo']['pwm_frequency']
        
        # Инициализация lgpio
        self.chip = lgpio.chip_open(0)
        self.chip_claim_gpio(self.chip, self.pin, lgpio.GPIO_OUTPUT)
        
        # Установка PWM (50 Гц для сервопривода)
        lgpio.set_pwm_frequency(self.chip, self.pin, self.pwm_frequency)
        
        logger.info(f"✅ Сервопривод SG-90 инициализирован на GPIO{self.pin}")
    
    def chip_claim_gpio(self, chip, pin, mode):
        """Claim GPIO pin (аналог gpio_claim_output)"""
        try:
            lgpio.gpio_claim_output(chip, pin)
        except:
            lgpio.gpio_claim_input(chip, pin)
            lgpio.write_gpio(chip, pin, mode)
    
    def set_angle(self, angle):
        if angle < self.min_angle: angle = self.min_angle
        if angle > self.max_angle: angle = self.max_angle
        
        # PWM duty: 0° = 1ms (5%), 180° = 2ms (10%) при 50 Гц
        duty_percent = 5.0 + (angle / 180.0) * 5.0
        pwm_value = int(duty_percent * 10)  # lgpio: 0-1000
        
        lgpio.set_pwm_value(self.chip, self.pin, pwm_value)
        time.sleep(self.move_delay)
        logger.debug(f"⚙️ Угол {angle}° (PWM: {pwm_value})")
    
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
        if LGPIO_AVAILABLE:
            lgpio.gpio_free(self.chip, self.pin)
            lgpio.chip_close(self.chip)
            logger.info("🔌 Отключен")


# ТЕСТ
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
