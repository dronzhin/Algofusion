# workers/LLM/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Копирование requirements
COPY workers/LLM/requirements.txt /app/workers/LLM/requirements.txt

# Установка Python-зависимостей
RUN pip install --no-cache-dir -r /app/workers/LLM/requirements.txt \

# Копирование кода
COPY shared/ /app/shared/
COPY core/ /app/core/
COPY workers/LLM/ /app/workers/LLM/

# Создаём пользователя для безопасности
ARG UID=1000
ARG GID=1000
RUN groupadd -g ${GID} appuser && useradd -u ${UID} -g appuser -m appuser
RUN chown -R appuser:appuser /app
USER appuser

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "from workers.LLM.src.config import LLMProcessingConfig; print('OK')" || exit 1

# Запуск воркера
CMD ["python", "workers/LLM/worker.py"]