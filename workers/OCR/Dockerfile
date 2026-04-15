FROM python:3.12-slim

# Метаданные
LABEL org.opencontainers.image.title="Algofusion OCR Worker"
LABEL org.opencontainers.image.description="Worker для OCR-обработки: Tesseract, EasyOCR, Surya, GLM"
LABEL org.opencontainers.image.version="0.1.0"

# 🔹 Аргументы для UID/GID
ARG TARGET_UID=1000
ARG TARGET_GID=1000

# 🔹 Создаём группу и пользователя
RUN groupadd -g ${TARGET_GID} appgroup && \
    useradd -u ${TARGET_UID} -g appgroup -m -s /bin/bash appuser

# 🔹 Переменные окружения для кэша
ENV HF_HOME=/app/cache/huggingface \
    TRANSFORMERS_CACHE=/app/cache/huggingface/hub \
    SURYA_CACHE_DIR=/app/cache/surya \
    TORCH_HOME=/app/cache/torch \
    TORCHINDUCTOR_CACHE_DIR=/app/cache/torch/inductor \
    XDG_CACHE_HOME=/app/cache/xdg \
    XDG_DATA_HOME=/app/cache/xdg/data \
    XDG_CONFIG_HOME=/app/cache/xdg/config \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/app \
    USER=appuser \
    LOGNAME=appuser \
    USERNAME=appuser \
    OCR_DEFAULT_ENGINE=tesseract \
    OCR_DEFAULT_LANG=rus+eng \
    OCR_TESSERACT_OEM=1 \
    OCR_TESSERACT_PSM=11 \
    OCR_TESSERACT_PREPROCESS=0 \
    OCR_TESSERACT_DPI=300 \
    OCR_EASYOCR_GPU=0 \
    OCR_EASYOCR_MIN_SCORE=0.5 \
    OCR_GLM_PROMPT="Text Recognition:" \
    OCR_GLM_MAX_TOKENS=2048 \
    OCR_GLM_TEMPERATURE=0.0 \
    # 🔹 Отключаем предупреждения и ускоряем работу с кэшем
    HF_HUB_DISABLE_SYMLINKS_WARNING=1 \
    HF_HUB_DISABLE_PROGRESS_BARS=1 \
    HF_DATASETS_OFFLINE=0

# === Системные зависимости ===
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-rus tesseract-ocr-eng \
    poppler-utils \
    libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 \
    libsndfile1 curl git \
    && rm -rf /var/lib/apt/lists/* && ldconfig

WORKDIR /app

# 🔹 Создаём структуру каталогов
RUN mkdir -p /app/cache/huggingface/hub \
             /app/cache/surya \
             /app/cache/torch/inductor \
             /app/cache/xdg/data \
             /app/cache/xdg/config \
             /app/workers/OCR/src \
             /app/shared \
             /app/core/services

# === Установка Python-зависимостей ===
COPY workers/OCR/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# =============================================================================
# 🔹 ПРЕДЗАГРУЗКА МОДЕЛЕЙ (от root) + ФИКС ПРАВ ДОСТУПА
# =============================================================================
RUN python << 'EOF'
import os
import stat

os.environ["HF_HOME"] = "/app/cache/huggingface"
os.environ["TORCH_HOME"] = "/app/cache/torch"

from transformers import AutoProcessor, AutoModelForImageTextToText
from huggingface_hub import snapshot_download

print('🔹 Предзагрузка модели zai-org/GLM-OCR...')
try:
    # 🔹 Скачиваем модель явно, чтобы контролировать процесс
    model_path = snapshot_download(
        repo_id="zai-org/GLM-OCR",
        cache_dir="/app/cache/huggingface",
        ignore_patterns=["*.pt", "*.bin"],  # 🔹 Опционально: не качать pytorch веса, если используем safetensors
        local_files_only=False,
        resume_download=True
    )
    print(f'✅ Модель скачана в: {model_path}')

    # 🔹 Явно загружаем процессор и модель, чтобы кэшировать custom code
    AutoProcessor.from_pretrained("zai-org/GLM-OCR", trust_remote_code=True, cache_dir="/app/cache/huggingface")
    AutoModelForImageTextToText.from_pretrained(
        "zai-org/GLM-OCR",
        trust_remote_code=True,
        torch_dtype="auto",
        cache_dir="/app/cache/huggingface"
    )
    print('✅ GLM-OCR процессор и модель предзагружены')

except Exception as e:
    print(f'⚠️ Не удалось предзагрузить GLM-OCR: {e}')
    print('   Модель будет загружена при первом запуске')

# 🔹 КЛЮЧЕВОЕ: Делаем весь кэш читаемым для всех пользователей
# Это решает проблему "root создал, appuser не может прочитать"
import pathlib
cache_path = pathlib.Path("/app/cache")
for path in cache_path.rglob("*"):
    try:
        # Добавляем права на чтение для group и other
        current_mode = path.stat().st_mode
        if path.is_file():
            path.chmod(current_mode | stat.S_IRGRP | stat.S_IROTH)
        elif path.is_dir():
            path.chmod(current_mode | stat.S_IXGRP | stat.S_IXOTH | stat.S_IRGRP | stat.S_IROTH)
    except Exception as perm_error:
        print(f'⚠️ Не удалось изменить права для {path}: {perm_error}')

print('✅ Права доступа к кэшу настроены')
EOF

# =============================================================================
# 🔹 Копирование кода
# =============================================================================
COPY shared/ ./shared/
COPY core/services/redis_client.py ./core/services/redis_client.py
COPY core/services/file_service.py ./core/services/file_service.py
COPY workers/OCR/worker.py ./workers/OCR/worker.py
COPY workers/OCR/src/ ./workers/OCR/src/

# 🔹 Финальная настройка прав: весь /app принадлежит appuser
# 🔹 Это переопределит любые права, установленные выше, но файлы останутся читаемыми
RUN chown -R appuser:appgroup /app && \
    # 🔹 Дополнительно: гарантируем, что кэш доступен на чтение
    chmod -R a+rX /app/cache

# 🔹 Переключаемся на non-root пользователя
USER appuser

# 🔹 Рабочая директория
WORKDIR /app

# 🔹 Проверка кэша при старте (опционально, для отладки)
# Раскомментируйте, если нужно видеть путь к кэшу в логах
# RUN echo 'import os; print(f"✅ HF_HOME at runtime: {os.environ.get(\"HF_HOME\")}")' > /app/check_cache.py

CMD ["python", "workers/OCR/worker.py"]