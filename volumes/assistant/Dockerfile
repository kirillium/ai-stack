# assistant/Dockerfile
FROM python:3.11-slim

WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV YOLO_CONFIG_DIR=/tmp/ultralytics

# Установка системных зависимостей
#RUN apt-get update && apt-get install -y \
RUN apt-get update && apt-get install -y --no-install-recommends \
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
#для видеосервиса
    libcap-dev \
#    ca-certificates \
#    python3-libcamera \  ставится, нужно для picamera
###    python3-kms++ \  не ставится, нужно для picamera
#    libcamera-ipa \   ставится, нужно для picamera
###    python3-picamera2 \   не ставится
#    rpicam-apps \    нужен для видеопотока в браузер; напрямую не устанавливается. Устанавливается через обходной путь в безопасности, см.ниже
# для сервопривода
    gcc \
    python3-dev \
#    liblgpio-dev \
#    lgpio \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# для режима распознавания face_recognition
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    gfortran \
    libopenblas-dev \
    liblapack-dev \
    libx11-dev \
    libgtk-3-dev \
    libjpeg-dev \
    libboost-all-dev \
#    python3-dev \   уже установлено
#    libgl1 \      уже установлено
#    libglib2.0-0 \   уже установлено
    && rm -rf /var/lib/apt/lists/*

# Обходной вариант для установки rpicam-apps (ТОЛЬКО этот пакет, нужно для видео в браузере, сервис видео-потока)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    gnupg \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

RUN mkdir -p /usr/share/keyrings
RUN curl -fsSL https://archive.raspberrypi.com/debian/raspberrypi.gpg.key \
    | gpg --dearmor -o /usr/share/keyrings/raspberrypi-archive-keyring.gpg

RUN printf "Types: deb\nURIs: http://archive.raspberrypi.com/debian/\nSuites: trixie\nComponents: main\nSigned-By: /usr/share/keyrings/raspberrypi-archive-keyring.gpg\n" \
    > /etc/apt/sources.list.d/raspberrypi.sources

RUN printf 'Acquire::AllowInsecureRepositories "true";\nAcquire::AllowDowngradeToInsecureRepositories "true";\nAPT::Get::AllowUnauthenticated "true";\n' \
    > /etc/apt/apt.conf.d/99allow-insecure-repos

RUN apt-get update && apt-get install -y --no-install-recommends \
    rpicam-apps \
    && rm -rf /var/lib/apt/lists/* \
    && rm -f /etc/apt/apt.conf.d/99allow-insecure-repos \
    && apt-get clean


#RUN apt-get install -y rpi-gpio

# Копирование requirements
COPY requirements.txt .

# Установка Python зависимостей
RUN pip install --no-cache-dir -r requirements.txt

#временно, для отладки camera-stream
#RUN python -m pip show Flask && python -c "import flask; print(flask.__version__)"

# Копирование скрипта оркестратора
COPY orchestrator.py .
COPY config.yaml .
COPY commands.yaml .
COPY directive_handlers.py .
COPY camera_stream.py .
COPY camera_controller.py .

# Создание директории для данных
#RUN mkdir -p /data
RUN mkdir -p /app/audio
RUN mkdir -p /app/audio/server_music

# Установка wyoming client для openwakeword
#RUN pip install --no-cache-dir wyoming

# Запуск оркестратора
CMD ["python", "orchestrator.py"]
