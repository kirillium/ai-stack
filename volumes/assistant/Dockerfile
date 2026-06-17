# assistant/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    alsa-utils \
# для аудио и микрофона
    libasound2 \
    libportaudio2 \
    portaudio19-dev \
    curl \
    mpv \
#    alsa-oss \
# аудио с сервера
    smbclient \
    wget \
# для OpenCV
    libcamera-dev \
    libopenblas-dev \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    ffmpeg \
    g++ \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Копирование requirements
COPY requirements.txt .

# Установка Python зависимостей
RUN pip install --no-cache-dir -r requirements.txt

# Копирование скрипта оркестратора
COPY orchestrator.py .
COPY config.yaml .
COPY commands.yaml .
COPY directive_handlers.py .

# Создание директории для данных
#RUN mkdir -p /data
RUN mkdir -p /app/audio

# Установка wyoming client для openwakeword
#RUN pip install --no-cache-dir wyoming

# Запуск оркестратора
CMD ["python", "orchestrator.py"]
