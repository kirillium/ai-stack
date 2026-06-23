import yaml
import time
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ServoController:
    def __init__(self, config_path='config.yaml'):
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        self.pin = config['servo']['pin']
        self.min_angle = config['servo']['min_angle']
        self.max_angle = config['servo']['max_angle']
        self.move_delay = config['servo']['move_delay']
        
        # Установка GPIO через os.system (sysfs)
        os.system(f"gpio mode {self.pin} pwm")
        os.system(f"gpio pwm-mode {self.pin} 1")
        os.system(f"gpio pwm-bits {self.pin} 1")
        os.system(f"gpio pwm-range {self.pin} 1000")
        os.system(f"gpio pwm-frequency {self.pin} 50")
        
        logger.info(f"✅ Сервопривод инициализирован на GPIO{self.pin} (sysfs)")
    
    def set_angle(self, angle):
        if angle < self.min_angle:
            angle = self.min_angle
        if angle > self.max_angle:
            angle = self.max_angle
        
        pwm_value = 100 + (angle / 180.0) * 800
        os.system(f"gpio pwm {self.pin} {int(pwm_value)}")
        time.sleep(self.move_delay)
    
    def turn_right(self, angle=120):
        self.set_angle(angle)
    
    def turn_left(self, angle=60):
        self.set_angle(angle)
    
    def reset(self):
        self.set_angle(90)
    
    def cleanup(self):
        os.system(f"gpio pwm {self.pin} 0")


if __name__ == '__main__':
    servo = ServoController()
    try:
        servo.turn_left()
        time.sleep(1)
        servo.reset()
        servo.turn_right()
        time.sleep(1)
        servo.reset()
    finally:
        servo.cleanup()
