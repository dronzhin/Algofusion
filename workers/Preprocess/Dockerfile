# workers/Preprocess/Dockerfile
FROM python:3.11-slim

# Метаданные
LABEL org.opencontainers.image.title="Algofusion Preprocess Worker"
LABEL org.opencontainers.image.description="Worker для предобработки изображений: конвертация, бинаризация, поворот"
LABEL org.opencontainers.image.version="0.1.0"

# Переменные окружения
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PROCESSOR_PDF_DPI=600 \
    PROCESSOR_BG_THRESHOLD=128 \
    PROCESSOR_BIN_THRESHOLD=128 \
    PROCESSOR_MEDIAN_ITER=5 \
    PROCESSOR_MEDIAN_SIZE=3 \
    PROCESSOR_ROT_ANGLE_THRESH=0.5 \
    PROCESSOR_ROT_SCALE=1.0

# === Системные зависимости (обновлённые для Debian 12+) ===
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Для pdf2image (конвертация PDF)
    poppler-utils \
    # Для OpenCV (поворот изображений) — обновлённые имена пакетов
    libgl1 \
    libglib2.0-0 \
    # Утилиты для отладки
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && ldconfig  # ← Обновляем кэш библиотек

# Рабочая директория
WORKDIR /app

# === Зависимости процессора (тяжелые, только здесь) ===
COPY workers/Preprocess/requirements.txt .
RUN pip install -r requirements.txt

# === Копируем ОБЩИЙ код (нужен всем контейнерам) ===
COPY shared/ ./shared/
COPY core/services/redis_client.py ./core/services/redis_client.py
COPY core/services/file_service.py ./core/services/file_service.py

# === Копируем КОД ПРОЦЕССОРА (явно, игнорируя глобальный .dockerignore) ===
COPY workers/Preprocess/src/ ./workers/Preprocess/src/
COPY workers/Preprocess/worker.py ./workers/Preprocess/worker.py

# Health check: проверяем подключение к Redis
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "from core.services.redis_client import get_redis_client; get_redis_client().client.ping()" || exit 1

# Точка входа
CMD ["python", "workers/Preprocess/worker.py"]