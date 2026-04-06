# workers/LLM/Dockerfile
FROM python:3.11-slim-bookworm

# Метаданные
LABEL maintainer="Dmitry Ronzhin <dmitry@algofusion.ru>"
LABEL description="Algofusion LLM Worker with Ollama integration"

# Переменные окружения
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

# Системные зависимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    jq \
    && rm -rf /var/lib/apt/lists/*

# Пользователь для безопасности (совместимо с file-monitor)
ARG UID=1000
ARG GID=1000
RUN groupadd -g ${GID} algofusion && \
    useradd -u ${UID} -g algofusion -m -s /bin/bash algofusion

WORKDIR /app

# Зависимости
COPY workers/LLM/requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && \
    pip install -r /app/requirements.txt

# Исходный код
COPY shared/ /app/shared/
COPY workers/LLM/ /app/workers/LLM/

# Директории
RUN mkdir -p /shared/files /app/workers/LLM/schemas /app/workers/LLM/prompts && \
    chown -R algofusion:algofusion /app /shared/files

USER algofusion

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import redis; r=redis.Redis(host='${REDIS_HOST:-redis}', port=${REDIS_PORT:-6379}); r.ping()" || exit 1

CMD ["python", "-m", "workers.LLM.worker"]