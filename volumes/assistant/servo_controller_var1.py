import yaml
from gpiozero import Servo
from time import sleep
import logging
#import os
#os.environ['GPIOZERO_PINFACTORY'] = 'native'
from gpiozero import Servo
from gpiozero.pinfactory import PinFactory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ServoController:
    """
    Контроллер сервопривода SG-90 для Raspberry Pi 5.
    Все команды по повороту явно прописаны здесь.
    """
    
    def __init__(self, config_path='config.yaml'):
        """Инициализация сервопривода из Config.yaml"""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            self.pin = config['servo']['pin']
            self.min_angle = config['servo']['min_angle']
            self.max_angle = config['servo']['max_angle']
            self.min_duty = config['servo']['min_duty']
            self.max_duty = config['servo']['max_duty']
            self.pwm_frequency = config['servo']['pwm_frequency']
            self.move_delay = config['servo']['move_delay']
            
            # Инициализация Servo через gpiozero (поддержка Pi 5)
            self.servo = Servo(self.pin)
            logger.info(f"✅ Сервопривод SG-90 инициализирован на GPIO{self.pin}")
        
        except FileNotFoundError:
            logger.error("❌ Config.yaml не найден. Создайте файл с секцией servo.")
            raise
        except KeyError as e:
            logger.error(f"❌ Отсутствует параметр в Config.yaml: {e}")
            raise
    
    # ==================== ЯВНО ПРОПИСАННЫЕ КОМАНДЫ ПОВОРОТА ====================
    
    def turn_right(self, angle: int = 120):
        """
        Повернуть сервопривод ВПРАВО.
        
        Args:
            angle: Угол в градусах (по умолчанию 120°)
        """
        self.set_angle(angle)
        logger.info(f"🔄 Сервопривод повернут вправо на {angle}°")
    
    def turn_left(self, angle: int = 60):
        """
        Повернуть сервопривод ВЛЕВО.
        
        Args:
            angle: Угол в градусах (по умолчанию 60°)
        """
        self.set_angle(angle)
        logger.info(f"🔄 Сервопривод повернут влево на {angle}°")
    
    def reset(self):
        """
        Возврат сервопривода в ЦЕНТРАЛЬНОЕ положение (90°).
        """
        self.set_angle(90)
        logger.info("🎯 Сервопривод возвращён в центр (90°)")
    
    def set_angle(self, angle: int):
        """
        Установить произвольный угол сервопривода.
        
        Args:
            angle: Угол в градусах (0-180)
        """
        if angle < self.min_angle or angle > self.max_angle:
            logger.warning(f"⚠️ Угол {angle}° вне диапазона [{self.min_angle}°, {self.max_angle}°]")
            # Корректировка в допустимый диапазон
            angle = max(self.min_angle, min(angle, self.max_angle))
        
        # Вычисление duty cycle для PWM
        duty_ratio = (angle - self.min_angle) / (self.max_angle - self.min_angle)
        self.servo.value = duty_ratio
        
        sleep(self.move_delay)
        logger.debug(f"⚙️ Установлен угол {angle}° (duty: {duty_ratio:.2f})")
    
    # ==================== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ====================
    
    def get_current_position(self) -> float:
        """Получить текущее положение (duty cycle 0.0-1.0)"""
        return self.servo.value if self.servo else 0.0
    
    def cleanup(self):
        """Очистка ресурсов (отключение сервопривода)"""
        if self.servo:
            self.servo.off()
            logger.info("🔌 Сервопривод отключен")


# ==================== ТЕСТОВЫЙ РЕЖИМ ====================

if __name__ == '__main__':
    """Тест сервопривода SG-90 при запуске напрямую"""
    servo = ServoController()
    try:
        print("=" * 50)
        print("ТЕСТ SERVO-CONTROLLER SG-90")
        print("=" * 50)
        
        print("\n1. Влево (60°)...")
        servo.turn_left()
        sleep(1)
        
        print("\n2. В центр (90°)...")
        servo.reset()
        sleep(1)
        
        print("\n3. Вправо (120°)...")
        servo.turn_right()
        sleep(1)
        
        print("\n4. Возврат в центр...")
        servo.reset()
        
        print("\n✅ Тест завершён")
    
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
    
    finally:
        servo.cleanup()
