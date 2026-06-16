# directive_handlers.py - обработчики часто используемых команд

import subprocess
import requests
import json
import os
from datetime import datetime

# Глобальные переменные для музыки (импортируются из orchestrator.py)
music_process = None
music_playing = False

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
    global music_process, music_playing
    
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
        print("✅Музыка запущена")
        return (True, "Музыка включена")
        
    except Exception as e:
        print(f"❌Ошибка запуска музыки: {e}")
        return (False, f"Не удалось включить музыку: {e}")


def handle_stop_music(transcript):
    """
    Обрабатывает команду прекращения музыки.
    Возвращает: (success, response_text)
    """
    global music_process, music_playing
    
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
        print("✅Музыка прекращена")
        return (True, "Музыка прекращена")
        
    except Exception as e:
        print(f"❌Ошибка прекращения музыки: {e}")
        music_playing = False
        return (False, f"Не удалось остановить музыку: {e}")


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


# === НАПОМИНАНЙ ===

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
