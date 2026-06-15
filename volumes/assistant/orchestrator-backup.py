# orchestrator.py - Скрипт оркестрации умной колонки
import subprocess
import json
import sounddevice as sd
import numpy as np
from scipy.io.wavfile import write
import requests
import asyncio
import time
import os
import wave
from pathlib import Path

# Конфигурация
CONFIG = {
    "wake_word_model": "ok_nabu",  # Модель из openwakeword
    "whisper_model": "base",
    "ollama_model": "gemma3:1b",
    "audio_device": "default",
    "wake_word_threshold": 0.5,
#    "sample_rate": 16000,
    "sample_rate": 48000,
    "channels": 1,
    
    # URLs сервисов (через docker network)
#    "whisper_url": "http://ai-whisper:8200/v1/audio/transcriptions",
    "whisper_url": "http://ai-whisper:8200",
    "ollama_url": "http://ai-ollama:11434/api/generate",
    "piper_url": "http://ai-piper:5000/api/tts",
}

# 1. Запись с микрофона
def record_audio(duration=5, fs=CONFIG["sample_rate"]):
    """Запись аудио с микрофона"""
    print(f"🎤 Запись аудио ({duration} сек)...")
    recording = sd.rec(
        int(duration * fs), 
        samplerate=fs, 
        channels=CONFIG["channels"], 
        dtype='float32'
    )
    sd.wait()
    return recording, fs

# 2. Сохранение аудио в WAV
def save_audio(audio_data, fs, output_path="/tmp/audio.wav"):
    """Сохранение аудио в WAV файл"""
    # Конвертация float32 в int16
    audio_int16 = (audio_data * 32767).astype(np.int16)
    write(output_path, fs, audio_int16)
    return output_path

# 3. Транскрибация через Whisper.cpp (REST API)
def transcribe(audio_path):
    """Транскрибация аудио через Whisper API"""
    print("🔄 Транскрибация через Whisper...")
    
    try:
        # whisper.cpp использует endpoint /inference
        whisper_url = "http://whisper:8200/inference"
        
        with open(audio_path, 'rb') as f:
            files = {'file': f}
            data = {
                'response_format': 'json',
            }
            
            response = requests.post(
                whisper_url,
                files=files,
                data=data,
                timeout=60
            )
        
        print(f"Whisper статус: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ Ошибка Whisper API: {response.status_code} - {response.text}")
            return None
        
        result = response.json()
        text = result.get('text', '').strip()
        print(f"📝 Распознано: {text}")
        return text if text else None
        
    except Exception as e:
        print(f"❌ Ошибка транскрибации: {e}")
        return None

# 4. Запрос к Ollama (LLM)
def ask_llm(prompt):
    """Запрос к LLM через Ollama API"""
    print("🤖 Запрос к Ollama (LLM)...")
    
    try:
        payload = {
            "model": CONFIG["ollama_model"],
            "prompt": prompt,
            "stream": False,
            "system": "Вы — помощник умной колонки. Отвечайте кратко, на русском языке, максимум 20 слов."
        }
        
        response = requests.post(
            CONFIG["ollama_url"],
            json=payload,
            timeout=120
        )
        
        result = response.json()
        text = result.get('response', '').strip()
        print(f"💬 Ответ LLM: {text}")
        return text if text else None
        
    except Exception as e:
        print(f"❌ Ошибка запроса к LLM: {e}")
        return None

# 5. Синтез речи через Piper TTS
def synthesize(text):
    """Синтез речи через Piper HTTP API"""
    print("🔊 Синтез речи через Piper...")
    
    try:
        # Piper HTTP API принимает POST с текстом и возвращает audio/wav
        response = requests.post(
            CONFIG["piper_url"],
            data=text.encode('utf-8'),
            headers={'Content-Type': 'text/plain; charset=utf-8'},
            timeout=30
        )
        
        if response.status_code == 200:
            # Сохраняем WAV файл
            audio_path = "/tmp/response.wav"
            with open(audio_path, 'wb') as f:
                f.write(response.content)
            print(f"✅ Аудио сохранено: {audio_path}")
            return audio_path
        else:
            print(f"❌ Ошибка Piper TTS: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Ошибка синтеза речи: {e}")
        return None

# 6. Воспроизведение аудио через динамик
def play_audio(audio_path):
    """Воспроизведение аудио через aplay"""
    print("▶️ Воспроизведение аудио...")
    
    try:
        cmd = ["aplay", "-D", "default", audio_path]
        subprocess.run(cmd, check=True, capture_output=True)
        print("✅ Аудио воспроизведено")
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка воспроизведения: {e}")
    except Exception as e:
        print(f"❌ Ошибка воспроизведения: {e}")

# 7. Детекция Wake Word (через Wyoming protocol openwakeword)
def detect_wake_word():
    """
    Детекция wake word через openwakeword.
    Используем Wyoming protocol клиент.
    """
    print("🔍 Ожидание wake word 'ok_nabu'...")
    
    try:
        # Используем wyoming-satellite для детекции wake word
        # или просто запускаем цикл с краткой записью
        recording, fs = record_audio(duration=2)
        audio_path = save_audio(recording, fs, "/tmp/wakeword.wav")
        
        # Для упрощения - возвращаем True (в реальной реализации
        # нужно подключить wyoming client для openwakeword)
        # Здесь можно использовать subprocess для вызова wyoming-openwakeword CLI
        return True
        
    except Exception as e:
        print(f"❌ Ошибка детекции wake word: {e}")
        return False


class VoiceAssistant:
    """Основной класс оркестратора умной колонки"""
    
    def __init__(self):
        self.is_running = False
    
    async def process_command(self):
        """Обработка голосовой команды"""
        print("\n" + "="*50)
        print("🎙️ ОБРАБОТКА ГОЛОСОВОЙ КОМАНДЫ")
        print("="*50)
        
        # 1. Запись аудио
        recording, fs = record_audio(duration=10)
        audio_path = save_audio(recording, fs)
        
        # 2. Транскрибация
        transcript = transcribe(audio_path)
        if not transcript:
            print("❌ Не удалось распознать речь")
            return
        
        # 3. Запрос к LLM
        response = ask_llm(transcript)
        if not response:
            print("❌ Не удалось получить ответ от LLM")
            return
        
        # 4. Синтез речи
        audio_path = synthesize(response)
        if not audio_path:
            print("❌ Не удалось синтезировать речь")
            return
        
        # 5. Воспроизведение
        play_audio(audio_path)
        
        print("\n✅ Готов к следующему запросу\n")
    
    def run(self):
        """Главный цикл работы ассистента"""
        print("\n" + "="*50)
        print("🚀 ЗАПУСК УМНОЙ КОЛОНКИ")
        print("="*50)
        print(f"Модель Whisper: {CONFIG['whisper_model']}")
        print(f"Модель Ollama: {CONFIG['ollama_model']}")
        print(f"Wake Word: {CONFIG['wake_word_model']}")
        print("="*50 + "\n")
        
        self.is_running = True
        
        while self.is_running:
            try:
                # Ждём wake word (упрощённая реализация)
                # В полной версии - через wyoming-openwakeword
                if detect_wake_word():
                    print("✅ Wake word обнаружен!")
                    asyncio.run(self.process_command())
                
                time.sleep(0.5)  # Не перегружать CPU
                
            except KeyboardInterrupt:
                print("\n🛑 Остановка ассистента...")
                self.is_running = False
            except Exception as e:
                print(f"❌ Ошибка в главном цикле: {e}")
                time.sleep(1)


def main():
    """Точка входа"""
    assistant = VoiceAssistant()
    assistant.run()


if __name__ == "__main__":
    main()
