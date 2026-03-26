FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

RUN useradd -m -u 1000 parseruser && chown -R parseruser:parseruser /app
USER parseruser

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import redis, os; redis.Redis.from_url(os.getenv('REDIS_URL', 'redis://redis:6379/0')).ping()" || exit 1

ENTRYPOINT ["python", "-m", "src.main"]
