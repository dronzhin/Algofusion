# workers/ocr/Dockerfile
FROM python:3.12-slim

WORKDIR /app

# ==================== Системные зависимости ====================
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Tesseract OCR
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-rus \
    # Для работы с изображениями
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    # Для PDF
    poppler-utils \
    # Очистка
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# ==================== Python зависимости ====================
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ==================== Исходный код ====================
COPY src/ ./src/

# ==================== Пользователь (безопасность) ====================
RUN useradd -m -u 1000 ocruser && chown -R ocruser:ocruser /app
USER ocruser

# ==================== Healthcheck ====================
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import redis; redis.Redis().ping()" || exit 1

# ==================== Точка входа ====================
ENTRYPOINT ["python", "-m", "src.main"]