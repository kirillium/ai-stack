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

# Загрузка конфигурации из YAML
def load_config():
    config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

CONFIG = load_config()

# 1. Запись аудио с микрофона
def record_audio(duration=None, fs=None):
    if duration is None:
        duration = CONFIG["audio"]["duration_wakeword"]
    if fs is None:
        fs = CONFIG["audio"]["sample_rate"]

    channels = CONFIG["audio"]["channels"]

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
#            data={'response_format': 'json'},
            data={
                'response_format': 'json',
                'language': CONFIG["models"].get("whisper_language", "ru")  # CHANGE
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
def play_audio(audio_path):
    print("▶️ Воспроизведение...")
    try:
        audio_device = CONFIG["audio"].get("output_device", CONFIG["audio"]["input_device"])
        cmd = ["aplay", "-D", audio_device, audio_path]
        subprocess.run(cmd, check=True, capture_output=True)
        print("✅ Аудио воспроизведено")
    except Exception as e:
        print(f"❌ Ошибка воспроизведения: {e}")

# 7. Детекция Wake Word (через Wyoming protocol openwakeword)
#def detect_wake_word():
#    print("🔍 Ожидание wake word...")
#    duration = CONFIG["audio"]["duration_wakeword"]
#    recording, fs = record_audio(duration=duration)
#    save_audio(recording, fs)
#    return True

#Вариант Г: Временное решение (простой threshold на громкость)
def detect_wake_word():
    print("🔍 Ожидание wake word (по громкости)...")

    recording, fs = record_audio(duration=2)

    # Вычисление громкости
    volume = np.mean(np.abs(recording))
    threshold = 0.05  # Подстроить

    print(f"📊 Volume: {volume}")

    if volume > threshold:
        print("✅ Возможно wake word!")
        return True
    return False

#Основной класс оркестратора умной колонки
class VoiceAssistant:
    def __init__(self):
        self.is_running = False

#Обработка голосовой команды
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
            transcript = transcribe(audio_path, test_mode=False) # 2. Транскрибация
            if not transcript:
                print("❌ Не распознано")
                return

        response = ask_llm(transcript) # 3. Запрос к LLM
        if not response:
            print("❌ Нет ответа LLM")
            return

        audio_path = synthesize(response) # 4. Синтез речи
        if not audio_path:
            print("❌ Нет синтеза")
            return

        play_audio(audio_path) # 5. Воспроизведение
        print("\n✅ Готов\n")

#Главный цикл работы ассистента
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

#Точка входа
def main():
    assistant = VoiceAssistant()
    assistant.run()

if __name__ == "__main__":
    main()
