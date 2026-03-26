FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

COPY requirements.txt .
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

RUN useradd -m -u 1000 ocruser && chown -R ocruser:ocruser /app
USER ocruser

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import redis, os; redis.Redis.from_url(os.getenv('REDIS_URL', 'redis://redis:6379/0')).ping()" || exit 1

ENTRYPOINT ["python", "-m", "src.main"]
