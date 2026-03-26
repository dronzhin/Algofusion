FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

RUN useradd -m -u 1000 layoutuser && chown -R layoutuser:layoutuser /app
USER layoutuser

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import redis, os; redis.Redis.from_url(os.getenv('REDIS_URL', 'redis://redis:6379/0')).ping()" || exit 1

ENTRYPOINT ["python", "-m", "src.main"]
