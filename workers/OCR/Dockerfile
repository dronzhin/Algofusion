# workers/ocr/Dockerfile
FROM python:3.11-slim

# Метаданные
LABEL org.opencontainers.image.title="Algofusion OCR Worker"
LABEL org.opencontainers.image.description="Worker для OCR-обработки: Tesseract, EasyOCR"
LABEL org.opencontainers.image.version="0.1.0"

# Переменные окружения
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    OCR_DEFAULT_ENGINE=tesseract \
    OCR_DEFAULT_LANG=rus+eng \
    OCR_TESSERACT_OEM=1 \
    OCR_TESSERACT_PSM=11 \
    OCR_TESSERACT_PREPROCESS=0 \
    OCR_TESSERACT_DPI=300 \
    OCR_EASYOCR_GPU=0 \
    OCR_EASYOCR_MIN_SCORE=0.5

# === Системные зависимости ===
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Tesseract OCR + языки
    tesseract-ocr \
    tesseract-ocr-rus \
    tesseract-ocr-eng \
    # Для pdf2image
    poppler-utils \
    # Для OpenCV/EasyOCR
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    # Утилиты
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && ldconfig

# Рабочая директория
WORKDIR /app

# === Зависимости OCR ===
COPY workers/OCR/requirements.txt .
RUN pip install -r requirements.txt

# === Копируем ОБЩИЙ код ===
COPY shared/ ./shared/
COPY core/services/redis_client.py ./core/services/redis_client.py
COPY core/services/file_service.py ./core/services/file_service.py

# === Копируем КОД OCR (плоская структура) ===
COPY workers/OCR/worker.py ./workers/OCR/worker.py
COPY workers/OCR/src/ ./workers/OCR/src/

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "from core.services.redis_client import get_redis_client; get_redis_client().client.ping()" || exit 1

# Точка входа
CMD ["python", "workers/OCR/worker.py"]