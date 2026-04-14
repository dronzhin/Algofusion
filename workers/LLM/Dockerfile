# workers/LLM/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Системные зависимости
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Копируем requirements ДО кода (оптимизация кеширования слоев)
COPY workers/LLM/requirements.txt /app/workers/LLM/requirements.txt

# Устанавливаем зависимости (каждая команда отдельно для надежности)
RUN pip install --no-cache-dir -r /app/workers/LLM/requirements.txt

# Копируем исходный код
COPY shared/ /app/shared/
COPY core/ /app/core/
COPY workers/LLM/ /app/workers/LLM/

RUN find /app -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
RUN find /app -name "*.pyc" -delete 2>/dev/null || true
RUN find /app -name "*.pyo" -delete 2>/dev/null || true

# Создаём непривилегированного пользователя
ARG UID=1000
ARG GID=1000
RUN groupadd -g ${GID} appuser && useradd -u ${UID} -g appuser -m appuser
RUN chown -R appuser:appuser /app
USER appuser

# Проверка работоспособности
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD python -c "from workers.LLM.src.config import LLMProcessingConfig; print('OK')" || exit 1

# Точка входа
CMD ["python", "workers/LLM/worker.py"]