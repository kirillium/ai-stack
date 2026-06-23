# directive_handlers.py - обработчики часто используемых команд

import subprocess
import requests
import json
import os
from datetime import datetime
import shutil
#from servo_controller import ServoController   # Раскомментировать, как появится библиотека для сервопривода

# Глобальные переменные для музыки (импортируются из orchestrator.py)
music_process = None
music_playing = False
current_stream = None  # Текущий источник: "jamendo" или "server"
#servo = ServoController('config.yaml')  # Раскомментировать, как появится библиотека для сервопривода

# Импортируем CONFIG из orchestrator.py (он будет загружен перед этим модулем)
CONFIG = None

def init_handlers(config):
    """Инициализирует handlers с CONFIG из orchestrator.py"""
    CONFIG = config


# === МУЗЫКА (Jamendo) ===

def get_jamendo_radio_url(radio_id=None):
    """Получает URL аудио-радио Jamendo через API v3.0"""
    if CONFIG is None:
        return None
    
    client_id = CONFIG["jamendo"]["client_id"]
    if radio_id is None:
        radio_id = CONFIG["jamendo"]["radio_id"]
    
    try:
        response = requests.get(
            "https://api.jamendo.com/v3.0/radios/",
            params={
                "client_id": client_id,
                "format": "json",
                "id": radio_id
            },
            timeout=10
        )
        
        if response.status_code != 200:
            print(f"❌Ошибка Jamendo API: {response.status_code}")
            return None
        
        radios = response.json().get("radios", [])
        if not radios:
            print("❌Радио не найдено")
            return None
        
        radio = radios[0]
        stream_url = radio.get("stream", {}).get(CONFIG["jamendo"]["stream_format"])
        
        if not stream_url:
            print("❌Нет URL потока в respuesta")
            return None
        
        print(f"✅URL радио Jamendo: {stream_url}")
        return stream_url
        
    except Exception as e:
        print(f"❌Ошибка получения радио Jamendo: {e}")
        return None


def get_jamendo_track_url(search_query=None):
    """Получает URL трека Jamendo через API v3.0"""
    if CONFIG is None:
        return None
    
    client_id = CONFIG["jamendo"]["client_id"]
    
    try:
        params = {
            "client_id": client_id,
            "format": "json",
            "limit": 1
        }
        if search_query:
            params["artist_name"] = search_query
        
        response = requests.get(
            "https://api.jamendo.com/v3.0/tracks/",
            params=params,
            timeout=10
        )
        
        if response.status_code != 200:
            print(f"❌Ошибка Jamendo API: {response.status_code}")
            return None
        
        tracks = response.json().get("tracks", [])
        if not tracks:
            print("❌Треки не найдены")
            return None
        
        track = tracks[0]
        stream_url = track.get("sound", {}).get(CONFIG["jamendo"]["stream_format"])
        
        if not stream_url:
            print("❌Нет URL потока в respuesta")
            return None
        
        print(f"✅URL трека Jamendo: {stream_url}")
        return stream_url
        
    except Exception as e:
        print(f"❌Ошибка получения трека Jamendo: {e}")
        return None


def handle_play_music(transcript):
    """
    Обрабатывает команду включения музыки (Jamendo).
    Возвращает: (success, response_text)
    """
    global music_process, music_playing, current_stream
    
    if music_playing:
        print("⚠️ Музыка уже играет")
        return (True, "Музыка уже включена")
    
    # Проверка: есть ли в запросе название жанра
    artist = None
    words = transcript.lower().split()
    if "рок" in words:
        artist = "rock"
    elif "поп" in words:
        artist = "pop"
    elif "электрон" in words:
        artist = "electronic"
    
    # Получаем URL
    if artist:
        print(f"🎵 Поиск треков: {artist}")
        stream_url = get_jamendo_track_url(artist)
    else:
        print("🎵 Запуск радио Jamendo")
        stream_url = get_jamendo_radio_url()
    
    if not stream_url:
        return (False, "Не удалось получить URL музыки из Jamendo")
    
    # Запуск потока через mpv
    try:
        music_process = subprocess.Popen(
            ["mpv", "--no-video", stream_url],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        music_playing = True
        current_stream = "jamendo"
        print("✅Музыка запущена (Jamendo)")
        return (True, "Музыка включена")

    except Exception as e:
        print(f"❌Ошибка запуска музыки: {e}")
        return (False, f"Не удалось включить музыку: {e}")


def handle_stop_music(transcript):
    """
    Обрабатывает команду прекращения музыки.
    Возвращает: (success, response_text)
    """
    global music_process, music_playing, current_stream
    
    if not music_playing:
        print("⚠️ Музыка не играет")
        return (True, "Музыка уже выключена")
    
    print("🛑 Прекращение музыкального потока...")
    
    try:
        if music_process:
            music_process.terminate()
            music_process.wait(timeout=3)
        music_process = None
        music_playing = False
        current_stream = None
        print("✅Музыка прекращена")
        return (True, "Музыка прекращена")
        
    except Exception as e:
        print(f"❌Ошибка прекращения музыки: {e}")
        music_playing = False
        current_stream = None
        return (False, f"Не удалось остановить музыку: {e}")


# === МУЗЫКА С НАС (music_server) ===

def get_music_file_from_server():
    """
    Получает путь к музыкальному файлу на NAS.
    Пока используется фиксированный файл для отладки.
    В перспективе (Этап 2) будет поиск по исполнителю.
    Возвращает: (success, local_path или error_message)
    """
    if CONFIG is None:
        return (False, "Конфиг не загружен")
    
    ip = CONFIG["music_server"]["ip"]
    path = CONFIG["music_server"]["path"]
    username = CONFIG["music_server"].get("username", "")
    password = CONFIG["music_server"].get("password", "")
    
    # пока используем фиксированный файл для отладки
    # В Этапе 2 будет поиск по исполнителю
    filename = "04. Auslander.flac"
    artist_folder = "Rammstein - Rammstein - 2019"
    
    # Полный путь на сервере
    # Для Windows SMB: \\192.168.1.171\музыка\Rammstein...\04. Auslander.flac
    # Для Linux: /mnt/nas/музыка/Rammstein.../04. Auslander.flac
    
    # Попытка 1: Windows SMB формат
    server_path_windows = f"\\\\{ip}\\{path}\\{artist_folder}\\{filename}"
    
    # Попытка 2: Linux формат
    server_path_linux = f"/{ip}/{path}/{artist_folder}/{filename}"
    
    # Локальный кэш для скачивания файла
    cache_dir = "/app/audio/server_music"
    os.makedirs(cache_dir, exist_ok=True)
    
    local_path = os.path.join(cache_dir, filename)
    
    # Скачиваем файл через SMB (если нужно) или используем network path напрямую
    try:
        # Прямой доступ к network path (mpv может играть из network)
        # mpv поддерживает SMB пути в формате \\server\path
        print(f"🎵 Путь к файлу: {server_path_windows}")
        
        # Проверка доступности файла
        if os.path.exists(server_path_windows):
            print(f"✅Файл доступен: {server_path_windows}")
            return (True, server_path_windows)
        
        # Если не существует, попробуем Linux формат
        if os.path.exists(server_path_linux):
            print(f"✅Файл доступен: {server_path_linux}")
            return (True, server_path_linux)
        
        # Если файл не доступен напрямую, скачиваем через smbclient
        # (требуется установка smbclient в Docker)
        print(f"⚠️Файл не доступен напрямую, попробуем скачать...")
        
        # Команда для скачивания через smbclient
        # BEGIN: smb://user:pass@ip/path/file.wav
        smb_url = f"smb://{username}:{password}@{ip}/{path}/{artist_folder}/{filename}" if username else f"smb://{ip}/{path}/{artist_folder}/{filename}"
        
        # Скачивание через wget или curl
        download_cmd = [
            "wget",
            "-O", local_path,
            smb_url.replace("smb://", "http://")  # Замена для wget (если NAS поддерживает HTTP)
        ]
        
        # Альтернатива: через cp если mount
        # Сначала попробуем mount (если NAS mount в системе)
        
        # Пока возвращаем network path для mpv (mpv может играть из network)
        return (True, server_path_windows)
        
    except Exception as e:
        print(f"❌Ошибка доступа к файлу на сервере: {e}")
        return (False, f"Не удалось найти музыку на сервере: {e}")


def handle_play_music_server(transcript):
    """
    Обрабатывает команду включения музыки с NAS.
    Пока используется фиксированный файл (Этап 1).
    В перспективе (Этап 2) будет поиск по исполнителю из transcript.
    Возвращает: (success, response_text)
    """
    global music_process, music_playing, current_stream
    
    if music_playing:
        print("⚠️ Музыка уже играет")
        return (True, "Музыка уже включена")
    
    print("🎵 Запуск музыки с сервера...")
    
    # Получаем путь к файлу
    success, file_path = get_music_file_from_server()
    
    if not success:
        return (False, file_path)  # file_path содержит error message
    
    print(f"🎵 Запуск файла: {file_path}")
    
    # Запуск через mpv
    try:
        music_process = subprocess.Popen(
            ["mpv", "--no-video", file_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        music_playing = True
        current_stream = "server"
        print("✅Музыка с сервера запущена")
        return (True, "Запускаю музыку с сервера")
        
    except Exception as e:
        print(f"❌Ошибка запуска музыки с сервера: {e}")
        return (False, f"Не удалось включить музыку с сервера: {e}")


# === ГРОМКОСТЬ ===

def handle_volume_up(transcript):
    """
    Обрабатывает команду увеличения громкости.
    Шаг громкости из config.yaml.
    Возвращает: (success, response_text)
    """
    if CONFIG is None:
        return (False, "Конфиг не загружен")
    
    step = CONFIG["volume"]["step"]
    device = CONFIG["volume"].get("device", "default")
    
    try:
        # Использование amixer для управления громкостью
        # Увеличение громкости
        cmd = ["amixer", "-D", device, "set", "Master", f"{step}%+"]
        subprocess.run(cmd, check=True, capture_output=True)
        
        print(f"✅Громкость увеличена на {step}%")
        return (True, f"Громкость увеличена на {step}%")
        
    except Exception as e:
        print(f"❌Ошибка увеличения громкости: {e}")
        return (False, f"Не удалось увеличить громкость: {e}")


def handle_volume_down(transcript):
    """
    Обрабатывает команду уменьшения громкости.
    Шаг громкости из config.yaml.
    Возвращает: (success, response_text)
    """
    if CONFIG is None:
        return (False, "Конфиг не загружен")
    
    step = CONFIG["volume"]["step"]
    device = CONFIG["volume"].get("device", "default")
    
    try:
        # Уменьшение громкости
        cmd = ["amixer", "-D", device, "set", "Master", f"{step}%-"]
        subprocess.run(cmd, check=True, capture_output=True)
        
        print(f"✅Громкость уменьшена на {step}%")
        return (True, f"Громкость уменьшена на {step}%")
        
    except Exception as e:
        print(f"❌Ошибка уменьшения громкости: {e}")
        return (False, f"Не удалось уменьшить громкость: {e}")


# === ПЫЛЕСОС ===

def handle_vacuum_start(transcript):
    """
    Обрабатывает команду включения пылесоса.
    Возвращает: (success, response_text)
    """
    if CONFIG is None:
        return (False, "Конфиг не загружен")
    
    api_url = CONFIG["vacuum"]["api_url"]
    start_endpoint = CONFIG["vacuum"]["start_endpoint"]
    
    try:
        response = requests.post(
            f"{api_url}{start_endpoint}",
            timeout=10
        )
        
        if response.status_code == 200:
            print("✅Пылесос включён")
            return (True, "Пылесос включён")
        else:
            print(f"❌Ошибка пылесоса: {response.status_code}")
            return (False, f"Не удалось включить пылесос: {response.status_code}")
            
    except Exception as e:
        print(f"❌Ошибка подключения к пылесосу: {e}")
        return (False, f"Ошибка подключения к пылесосу: {e}")


def handle_vacuum_stop(transcript):
    """
    Обрабатывает команду выключения пылесоса.
    Возвращает: (success, response_text)
    """
    if CONFIG is None:
        return (False, "Конфиг не загружен")
    
    api_url = CONFIG["vacuum"]["api_url"]
    stop_endpoint = CONFIG["vacuum"]["stop_endpoint"]
    
    try:
        response = requests.post(
            f"{api_url}{stop_endpoint}",
            timeout=10
        )
        
        if response.status_code == 200:
            print("✅Пылесос выключён")
            return (True, "Пылесос выключён")
        else:
            print(f"❌Ошибка пылесоса: {response.status_code}")
            return (False, f"Не удалось выключить пылесос: {response.status_code}")
            
    except Exception as e:
        print(f"❌Ошибка подключения к пылесосу: {e}")
        return (False, f"Ошибка подключения к пылесосу: {e}")


# === НАПОМИНАНИЕ ===

def handle_reminder_set(transcript):
    """
    Обрабатывает команду установки напоминания.
    Возвращает: (success, response_text)
    """
    if CONFIG is None:
        return (False, "Конфиг не загружен")
    
    storage_file = CONFIG["reminder"]["storage_file"]
    
    # Простая реализация: сохранить в JSON файл
    try:
        # Загружаем существующие напоминания
        reminders = []
        if os.path.exists(storage_file):
            with open(storage_file, 'r', encoding='utf-8') as f:
                reminders = json.load(f)
        
        # Добавляем новое напоминание
        new_reminder = {
            "text": transcript,
            "timestamp": datetime.now().isoformat(),
            "done": False
        }
        reminders.append(new_reminder)
        
        # Сохраняем
        with open(storage_file, 'w', encoding='utf-8') as f:
            json.dump(reminders, f, ensure_ascii=False, indent=2)
        
        print("✅Напоминание установлено")
        return (True, "Напоминание установлено")
        
    except Exception as e:
        print(f"❌Ошибка хранения напоминания: {e}")
        return (False, f"Не удалось установить напоминание: {e}")

# === усправление сервоприводом ===
#def handle_servo(command):
#    if command == "поверни вправо":
#        servo.turn_right()
#        return "Сервопривод повернут вправо"
#    elif command == "поверни влево":
#        servo.turn_left()
#        return "Сервопривод повернут влево"
#    elif command == "возврат" or command == "центр":
#        servo.reset()
#        return "Сервопривод в центре"

# === СЕРВОПРИВОД ===
# пока ОСТАНОВЛЕНО. Код есть, нет библиотек для работы с сервоприводом. Выходы в код п работе с сервоприводов закомментированы. 
# Раскомментировать, как появится библиотека
def handle_servo_turn_right(transcript):
    """
    Обрабатывает команду "поверни вправо/направо".
    Возвращает: (success, response_text)
    """
    try:
#        servo.turn_right()   # Раскомментировать, как появится библиотека для сервопривода
        print("✅Сервопривод повернут вправо")
        return (True, "Камера повернута направо")
    
    except Exception as e:
        print(f"❌Ошибка поворота вправо: {e}")
        return (False, f"Не удалось повернуть вправо: {e}")


def handle_servo_turn_left(transcript):
    """
    Обрабатывает команду "поверни влево/налево".
    Возвращает: (success, response_text)
    """
    try:
#        servo.turn_left()   # Раскомментировать, как появится библиотека для сервопривода
        print("✅Сервопривод повернут влево")
        return (True, "Камера повернута налево")
    
    except Exception as e:
        print(f"❌Ошибка поворота влево: {e}")
        return (False, f"Не удалось повернуть влево: {e}")


def handle_servo_reset(transcript):
    """
    Обрабатывает команду "верни в центр/возврат/центр".
    Возвращает: (success, response_text)
    """
    try:
#        servo.reset()   # Раскомментировать, как появится библиотека для сервопривода
        print("✅Сервопривод в центре")
        return (True, "Камера возвращена в центр")
    
    except Exception as e:
        print(f"❌Ошибка возврата в центр: {e}")
        return (False, f"Не удалось вернуть в центр: {e}")

# === ПОГОДА ===

def handle_weather_get(transcript):
    """
    Обрабатывает команду получения погоды.
    Возвращает: (success, response_text с погодой)
    """
    if CONFIG is None:
        return (False, "Конфиг не загружен")
    
    api_url = CONFIG["weather"]["api_url"]
    api_key = CONFIG["weather"]["api_key"]
    city = CONFIG["weather"]["city"]
    
    try:
        # Пример для OpenWeatherMap
        response = requests.get(
            f"{api_url}/data/2.5/weather?q={city}&appid={api_key}&units=metric&lang=ru",
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            description = data["weather"][0]["description"]
            temp = data["main"]["temp"]
            
            weather_text = f"{description}, {temp}°C"
            print(f"✅Погода: {weather_text}")
            return (True, weather_text)
        else:
            print(f"❌Ошибка погоды: {response.status_code}")
            return (False, f"Не удалось получить погоду: {response.status_code}")
            
    except Exception as e:
        print(f"❌Ошибка подключения к API погоды: {e}")
        return (False, f"Ошибка получения погоды: {e}")
