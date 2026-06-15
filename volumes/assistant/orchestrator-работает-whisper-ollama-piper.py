import subprocess
import json
import sounddevice as sd
import numpy as np
from scipy.io.wavfile import write
import requests
import asyncio
import time
import os
from pathlib import Path

# Конфигурация
CONFIG = {
    "wake_word_model": "ok_nabu",
    "whisper_model": "base",
    "ollama_model": "qwen2.5:1.5b",
    "audio_device": "default",
    "wake_word_threshold": 0.5,
    "sample_rate": 48000,
    "channels": 1,
    
    "whisper_url_base": "http://whisper:8200",
    "ollama_url": "http://ollama:11434/api/generate",
    "piper_url_base": "http://piper:5000",
}

# ТЕСТОВЫЙ режим (True для теста с test.wav)
TEST_MODE = False

# 1. Запись с микрофона
def record_audio(duration=5, fs=CONFIG["sample_rate"]):
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
    audio_int16 = (audio_data * 32767).astype(np.int16)
    write(output_path, fs, audio_int16)
    return output_path

# 3. Транскрибация через Whisper.cpp
def transcribe(audio_path):
    print("🔄 Транскрибация через Whisper...")
    
    try:
        whisper_url = f"{CONFIG['whisper_url_base']}/inference"
        
        with open(audio_path, 'rb') as f:
            files = {'file': f}
            data = {'response_format': 'json'}
            
            response = requests.post(
                whisper_url,
                files=files,
                data=data,
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

# 4. Запрос к Ollama
def ask_llm(prompt):
    print("🤖 Запрос к Ollama (LLM)...")
    
    try:
        payload = {
            "model": CONFIG["ollama_model"],
            "prompt": prompt,
            "stream": False,
            "system": "Вы — помощник умной колонки. Отвечайте кратко, на русском, максимум 20 слов."
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
        print(f"❌ Ошибка LLM: {e}")
        return None

# 5. Синтез речи через Piper
def synthesize(text):
    print("🔊 Синтез речи через Piper...")
    
    try:
        # Piper использует GET запрос с параметром ?text=
        piper_url = f"{CONFIG['piper_url_base']}/?text={text}"
        
        response = requests.get(
            piper_url,
            timeout=30
        )
        
        if response.status_code == 200:
            audio_path = "/tmp/response.wav"
            with open(audio_path, 'wb') as f:
                f.write(response.content)
            print(f"✅ Аудио: {audio_path} ({len(response.content)} байт)")
            return audio_path
        else:
            print(f"❌ Ошибка Piper: {response.status_code} - {response.text[:100]}")
            return None
            
    except Exception as e:
        print(f"❌ Ошибка синтеза: {e}")
        return None

# 6. Воспроизведение аудио
def play_audio(audio_path):
    print("▶️ Воспроизведение...")
    try:
        cmd = ["aplay", "-D", "default", audio_path]
        subprocess.run(cmd, check=True, capture_output=True)
        print("✅ Аудио воспроизведено")
    except Exception as e:
        print(f"❌ Ошибка воспроизведения: {e}")

# ВРЕМЕННО: всегда True для теста (без реальной детекции wake word)
def detect_wake_word():
    print("🔍 Ожидание wake word...")
    recording, fs = record_audio(duration=2)
    save_audio(recording, fs, "/tmp/wakeword.wav")
    return True

class VoiceAssistant:
    def __init__(self):
        self.is_running = False
    
    async def process_command(self, test_mode=False):
        print("\n" + "="*50)
        print("🎙️ ОБРАБОТКА КОМАНДЫ")
        print("="*50)
        
        if test_mode:
            print("🧪 ТЕСТ: использую test.wav")
            audio_path = "/app/volumes/whisper/test.wav"
            transcript = "привет как тебя зовут"
            print(f"📝 ТЕСТ-текст: {transcript}")
        else:
            recording, fs = record_audio(duration=10)
            audio_path = save_audio(recording, fs)
            transcript = transcribe(audio_path)
            if not transcript:
                print("❌ Не распознано")
                return
        
        response = ask_llm(transcript)
        if not response:
            print("❌ Нет ответа LLM")
            return
        
        audio_path = synthesize(response)
        if not audio_path:
            print("❌ Нет синтеза")
            return
        
        play_audio(audio_path)
        print("\n✅ Готов\n")
    
    def run(self):
        print("\n" + "="*50)
        print("🚀 ЗАПУСК УМНОЙ КОЛОНКИ")
        print(f"Whisper: {CONFIG['whisper_model']}")
        print(f"Ollama: {CONFIG['ollama_model']}")
        print("="*50)
        print("\n🔁 Автоматический режим: записываю каждые 2 сек\n")
        
        self.is_running = True
        
        while self.is_running:
            try:
                # Ждать wake word (временно: всегда True)
                if detect_wake_word():
                    print("✅ Wake word detected!")
                    asyncio.run(self.process_command(test_mode=TEST_MODE))
                
                time.sleep(0.5)
                
            except KeyboardInterrupt:
                print("\n🛑 STOP")
                self.is_running = False
            except Exception as e:
                print(f"❌ Error: {e}")
                time.sleep(1)

def main():
    assistant = VoiceAssistant()
    assistant.run()

if __name__ == "__main__":
    main()
