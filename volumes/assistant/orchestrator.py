# volumes/assistant/orchestrator.py

import subprocess
import json
import sounddevice as sd
import numpy as np
from scipy.io.wavfile import write
import requests
import asyncio
import time
import os
import yaml
import cv2
from pathlib import Path
import threading

# Глобальные переменные для управления музыкой
music_process = None  # Процесс mpv для потока
music_playing = False  # Флаг включения музыки


# Загрузка конфигурации из YAML
def load_config():
    config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

# Загрузка команд из commands.yaml
def load_commands():
    commands_path = os.path.join(os.path.dirname(__file__), 'commands.yaml')
    try:
        with open(commands_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print("⚠️ commands.yaml не найден, используем пустой список команд")
        return {"directive_commands": {}}

# Загрузка импортов обработчиков
def load_directive_handlers():
    """Импортирует функции обработчиков из directive_handlers.py"""
    from directive_handlers import (
        handle_play_music,
        handle_stop_music,
        handle_vacuum_start,
        handle_vacuum_stop,
#        handle_reminder_set,
        handle_set_reminder,
        handle_weather_get,
        handle_camera_snapshot,
        handle_camera_preview,
        handle_recognize_object,
        handle_track_object
    )
    return {
        "handle_play_music": handle_play_music,
        "handle_stop_music": handle_stop_music,
        "handle_vacuum_start": handle_vacuum_start,
        "handle_vacuum_stop": handle_vacuum_stop,
#        "handle_reminder_set": handle_reminder_set,
        "handle_set_reminder": handle_set_reminder,
        "handle_weather_get": handle_weather_get,
        "handle_camera_snapshot": handle_camera_snapshot,
        "handle_camera_preview": handle_camera_preview,
        "handle_recognize_object": handle_recognize_object,
        "handle_track_object": handle_track_object
    }

CONFIG = load_config()
COMMANDS = load_commands()
HANDLERS = load_directive_handlers()

# === ИНИЦИАЛИЗАЦИЯ СЕРВИСА НАПОМИНАНИЙ ===
from reminders import RemindersService

REMINDERS_CFG = CONFIG.get("reminders", {})
REMINDERS_DB_PATH = REMINDERS_CFG.get("db_path", "/data/assistdata.db")
REMINDERS_INTERVAL = REMINDERS_CFG.get("check_interval_seconds", 30)

rem_service = None

def speak_text(text):
    audio_path = synthesize(text)
    if audio_path:
        play_audio(audio_path)

def on_reminder_fire(reminder):
    text = reminder.get("text", "")
    remind_at = reminder.get("remind_at", "")
#    message = f"Вы просили напомнить: {text} в {remind_at}"   # отладка
#    print(message)  # отладка
    try:
#        speak_text(f"Вы просили напомнить: {text} в {remind_at}")
        speak_text(f"Лог")
        message = f"Вы просили напомнить: {text} в {remind_at}"   # отладка
        print(message)  # отладка
        #piper_say(speak_text)   # замените на реальную функцию озвучивания в orchestrator
    except Exception as e:
        print("Error in speak_text:", e)
# старый вариант
#    speak_text(message)
#    speak_text = f"Вы просили напомнить: {text} в {remind_at}"
#    try:
#        piper_say(speak_text)
#    except Exception as e:
#        print("Error in piper_say:", e)

def init_reminders_service():
    global rem_service
    if rem_service is None:
        rem_service = RemindersService(
            db_path=REMINDERS_DB_PATH,
            check_interval_seconds=REMINDERS_INTERVAL,
            on_fire_callback=on_reminder_fire,
            schema_path=os.path.join(os.path.dirname(__file__), "reminders_schema.sql"),
        )
        rem_service.start()

# инициализация напоминаний
#---------------------------------------------------------

# 1. Запись аудио с микрофона
def record_audio(duration=None, fs=None):
    if duration is None:
        duration = CONFIG["audio"]["duration_wakeword"]
    if fs is None:
        fs = CONFIG["audio"]["sample_rate"]

    # Для ЗАПИСИ всегда используем 1 канал (microphone mono)
    channels = 1
#    channels = CONFIG["audio"]["channels"]  # если channels=1 (моно), проблем нет, если channels=2 (стерео), то будет ошибка, т.к. микрофон поддерживает моно

    print(f"🎤 Запись аудио ({duration} сек)...")
    recording = sd.rec(
        int(duration * fs),
        samplerate=fs,
        channels=channels,
        dtype='float32'
    )
    sd.wait()
    return recording, fs

# 2. Сохранение аудио в WAV файл
def save_audio(audio_data, fs, output_dir=None):
    if output_dir is None:
        output_dir = CONFIG["storage"]["audio_output_dir"]

    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, "audio.wav")
    audio_int16 = (audio_data * 32767).astype(np.int16)
    write(output_path, fs, audio_int16)
    return output_path

# 3. Транскрибация аудио через Whisper.cpp (REST API)
def transcribe(audio_path, test_mode=None):
    if test_mode is None:
        test_mode = CONFIG["runtime"]["test_mode"]

    if test_mode:
        print("🧪 ТЕСТ: использую заготовленный текст")
        transcript = "привет как тебя зовут"
        print(f"📝 ТЕСТ-текст: {transcript}")
        return transcript

    print("🔄 Транскрибация через Whisper...")

    try:
        response = requests.post(
            CONFIG["services"]["whisper_url"],
            files={'file': open(audio_path, 'rb')},
            data={
                'response_format': 'json',
                'language': CONFIG["models"].get("whisper_language", "ru")
            },
            timeout=60
        )

        print(f"Whisper статус: {response.status_code}")

        if response.status_code != 200:
            print(f"❌ Ошибка Whisper: {response.status_code}")
            return None

        result = response.json()
        text = result.get('text', '').strip()
        print(f"📝 Распознано: {text}")
        return text if text else None

    except Exception as e:
        print(f"❌ Ошибка транскрибации: {e}")
        return None

# 4. Запрос к LLM через Ollama API
def ask_llm(prompt):
    print("🤖 Запрос к Ollama (LLM)...")

    try:
        payload = {
            "model": CONFIG["models"]["ollama"],
            "prompt": prompt,
            "stream": False,
            "system": CONFIG["system"]["llm_system_prompt"]
        }

        response = requests.post(
            CONFIG["services"]["ollama_url"],
            json=payload,
            timeout=120
        )

        result = response.json()
        text = result.get('response', '').strip()
        print(f"💬 Ответ LLM: {text}")
        return text if text else None

    except Exception as e:
        print(f"❌ Ошибка LLM: {e}")
        return None

# 5. Синтез речи через Piper TTS
def synthesize(text):
    print("🔊 Синтез речи через Piper...")

    try:
        piper_url = CONFIG["services"]["piper_url"] + text

        response = requests.get(
            piper_url,
            timeout=30
        )

        if response.status_code == 200:
            output_dir = CONFIG["storage"]["audio_output_dir"]
            os.makedirs(output_dir, exist_ok=True)

            audio_path = os.path.join(output_dir, "response.wav")
            with open(audio_path, 'wb') as f:
                f.write(response.content)

            file_size = len(response.content)
            print(f"✅ Аудио: {audio_path} ({file_size} байт)")

            max_size_bytes = CONFIG["storage"]["max_audio_size_mb"] * 1024 * 1024
            if file_size > max_size_bytes:
                print(f"⚠️ файл > {CONFIG['storage']['max_audio_size_mb']} МБ, удаляем")
                os.remove(audio_path)
                return None

            return audio_path
        else:
            print(f"❌ Ошибка Piper: {response.status_code}")
            return None

    except Exception as e:
        print(f"❌ Ошибка синтеза: {e}")
        return None

# 6. Воспроизведение аудио через динамик
#def play_audio(audio_path):
#    print("▶️ Воспроизведение...")
#    try:
        # вариант 1
        # ПРОВЕРИТЬ, куда выводит. Похоже, ошибка выбора устройства
#        audio_device = CONFIG["audio"].get("output_device", CONFIG["audio"]["input_device"])
#        cmd = ["aplay", "-D", audio_device, audio_path]

        # вариант 2
        # ИЗМЕНИТЬЬ: используй plughw для авто-конвертации каналов
        # для варианта 2 НЕ ВНЕСЕНЫ правки в config
        #audio_device = CONFIG["audio"].get("output_device", 3)

        # Используем plughw (автоматически конвертирует mono→stereo)
#        cmd = ["aplay", "-D", f"plughw:{audio_device},0", audio_path]

#        subprocess.run(cmd, check=True, capture_output=True)
#        print("✅ Аудио воспроизведено")
#    except Exception as e:
#        print(f"❌ Ошибка воспроизведения: {e}")

# 6. Воспроизведение аудио через динамик
def play_audio(audio_path):
    print("▶️ Воспроизведение...")
    try:
        # Получаем card номер (только число, без device)
        audio_card = CONFIG["audio"].get("output_device", 0)

        # Используем plughw для авто-конвертации mono→stereo
        cmd = ["aplay", "-D", f"plughw:{audio_card},0", audio_path]

        subprocess.run(cmd, check=True, capture_output=True)
        print("✅ Аудио воспроизведено")
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка воспроизведения: {e}")
        print(f"   Проверь: aplay -l (доступные устройства)")
    except Exception as e:
        print(f"❌ Ошибка воспроизведения: {e}")


# 7. Детекция Wake Word (простой threshold на громкость)
def detect_wake_word():
    print("🔍 Ожидание wake word (по громкости)...")

    recording, fs = record_audio(duration=2)
    # Вычисление громкости
    volume = np.mean(np.abs(recording))

    # Порог громкости threshold из config.yaml
    threshold = CONFIG["runtime"]["wake_word_threshold"]

    print(f"📊 Volume: {volume}")
    print(f"📊 Threshold: {threshold}")

    if volume > threshold:
        print("✅ Возможно wake word!")
        return True
    return False


# === НОВЫЙ БЛОК: Обработка директивных команд ===
#def handle_directive_command(transcript): # старый вариант
def handle_directive_command(transcript, rem_service, orchestrator): # новый вариант
    """
    Проверяет transcript на совпадение с директивными командами из commands.yaml.
    Возвращает:
        - (True, response_text) если команда найдена и обработана
        - (False, None) если команда не найдена (нужно отправить в Ollama)
    """
    transcript_lower = transcript.lower()
    directive_commands = COMMANDS.get("directive_commands", {})
    
    for trigger, config in directive_commands.items():
        if trigger in transcript_lower:
            action = config.get("action")
            response_template = config.get("response", "")
            
            print(f"🎯 Директивная команда: {trigger} → {action}")
            handler = HANDLERS.get(f"handle_{action}")
            
            if not handler:
                print(f"⚠️ Нет обработчика для действия: {action}")
                return True, "Команда распознана, но обработчик не реализован"
            
            # Вызов обработчика
            try:
#                result = handler(transcript) # старый вариант
                result = handler(transcript, rem_service, orchestrator) # новый вариант 
                # Если обработчик возвращает строку (ответ пользователю)
                if isinstance(result, str):
                    return True, result
                
                # Если обработчик возвращает bool (успех/неудача)
                elif isinstance(result, bool):
                    if result:
                        return True, response_template
                    else:
                        return True, f"Не удалось выполнить: {action}"
                
                # Если обработчик возвращает tuple (success, response)
                elif isinstance(result, tuple):
                    success, response = result

#                    if success:
#                        return True, response
#                    else:
#                        return True, response
                    return True, response if response else response_template # новый вариант
                else:
                    return True, f"Команда {action} обработана"
                    
            except Exception as e:
                print(f"❌Ошибка в обработчике {action}: {e}")
                return True, f"Ошибка выполнения: {action}"
    
    # Команда не найдена → отправлять в Ollama
    return False, None


# Основной класс оркестратора умной колонки
class VoiceAssistant:
    def __init__(self):
        self.is_running = False

# Обработка голосовой команды
    async def process_command(self):
        print("\n" + "="*50)
        print("🎙️ ОБРАБОТКА КОМАНДЫ")
        print("="*50)

        test_mode = CONFIG["runtime"]["test_mode"]

        if test_mode:
            print("🧪 ТЕСТ-режим")
            transcript = "привет как тебя зовут"
            print(f"📝 ТЕСТ-текст: {transcript}")
        else:
            duration = CONFIG["audio"]["duration_command"]
            recording, fs = record_audio(duration=duration)
            audio_path = save_audio(recording, fs)
	    # 2. Транскрибация
            transcript = transcribe(audio_path, test_mode=False)
            if not transcript:
                print("❌ Не распознано")
                return

        # === НОВЫЙ БЛОК: Проверка на директивную команду ===
#        directive_found, response_text = handle_directive_command(transcript) # старый вариант
        directive_found, response_text = handle_directive_command(transcript, rem_service, self) # новый вариант

        if directive_found:
            print(f"💬 Ответ: {response_text}")
            audio_path = synthesize(response_text)
            if audio_path:
                play_audio(audio_path)
            print("\n✅ Готов\n")
            return  # НЕ отправляем в Ollama
        
        # === Остальной код: запрос к Ollama ===
	# 3. Запрос к LLM
        response = ask_llm(transcript)
        if not response:
            print("❌ Нет ответа LLM")
            return
	# 4. Синтез речи
        audio_path = synthesize(response)
        if not audio_path:
            print("❌ Нет синтеза")
            return

        play_audio(audio_path)
        print("\n✅ Готов\n")

# Главный цикл работы ассистента
    def run(self):
        print("\n" + "="*50)
        print("🚀 ЗАПУСК УМНОЙ КОЛОНКИ")
        print(f"Whisper: {CONFIG['models']['whisper']}")
        print(f"Ollama: {CONFIG['models']['ollama']}")
        print(f"Wake Word: {CONFIG['models']['wake_word']}")
        print(f"Audio dir: {CONFIG['storage']['audio_output_dir']}")
        print("="*50)
        print("\n🔁 Автоматический режим\n")

        self.is_running = True

        while self.is_running:
            try:
                # Ждём wake word (упрощённая реализация)
                # В полной версии - через wyoming-openwakeword
                if detect_wake_word():
                    print("✅ Wake word detected!")
                    asyncio.run(self.process_command())

                time.sleep(0.5) # Не перегружать CPU

            except KeyboardInterrupt:
                print("\n🛑 STOP")
                self.is_running = False
            except Exception as e:
                print(f"❌ Error: {e}")
                time.sleep(1)

# Точка входа
def main():
# старый вариант, без сервиса напоминаний
#    assistant = VoiceAssistant()
#    assistant.run()
# новый вариант, с сервисом напоминаний
    init_reminders_service()
    assistant = VoiceAssistant()
    try:
        assistant.run()
    finally:
        if rem_service:
            rem_service.stop()

if __name__ == "__main__":
    main()
