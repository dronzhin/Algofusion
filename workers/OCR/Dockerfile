# workers/OCR/Dockerfile
FROM python:3.12-slim

# Метаданные
LABEL org.opencontainers.image.title="Algofusion OCR Worker"
LABEL org.opencontainers.image.description="Worker для OCR-обработки: Tesseract, EasyOCR, Surya, GLM"
LABEL org.opencontainers.image.version="0.1.0"

# 🔹 Аргументы для динамического UID/GID (передаются при сборке)
ARG TARGET_UID=1000
ARG TARGET_GID=1000

# 🔹 Создаём группу и пользователя с указанными ID
# Это решает проблему getpwuid(): uid not found: 1000
RUN groupadd -g ${TARGET_GID} appgroup && \
    useradd -u ${TARGET_UID} -g appgroup -m -s /bin/bash appuser

# 🔹 Переменные окружения для кэша (явные пути, не зависящие от getpass)
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
    OCR_GLM_TEMPERATURE=0.0

# === Системные зависимости ===
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-rus tesseract-ocr-eng \
    poppler-utils \
    libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 \
    libsndfile1 curl git \
    && rm -rf /var/lib/apt/lists/* && ldconfig

# Рабочая директория
WORKDIR /app

# 🔹 Создаём структуру каталогов для кэша и назначаем права
# Важно: делаем это ДО установки пакетов и копирования кода
RUN mkdir -p /app/cache/huggingface/hub \
             /app/cache/surya \
             /app/cache/torch/inductor \
             /app/cache/xdg/data \
             /app/cache/xdg/config \
             /app/workers/OCR/src \
             /app/shared \
             /app/core/services && \
    chown -R appuser:appgroup /app

# === Установка Python-зависимостей (пока ещё root) ===
COPY workers/OCR/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 🔹 ПРЕДЗАГРУЗКА МОДЕЛЕЙ ПРИ СБОРКЕ
# 🔹 Выполняем от имени root, чтобы избежать проблем с правами
# 🔹 Модели сохранятся в /app/cache, который потом будет принадлежать appuser
RUN python << 'EOF'
import os
os.environ["HF_HOME"] = "/app/cache/huggingface"
os.environ["TORCH_HOME"] = "/app/cache/torch"

from transformers import AutoProcessor, AutoModelForImageTextToText
print('🔹 Предзагрузка модели zai-org/GLM-OCR...')
try:
    AutoProcessor.from_pretrained('zai-org/GLM-OCR', trust_remote_code=True)
    AutoModelForImageTextToText.from_pretrained(
        'zai-org/GLM-OCR',
        trust_remote_code=True,
        torch_dtype='auto'
    )
    print('✅ GLM-OCR модель предзагружена в кэш')
except Exception as e:
    print(f'⚠️ Не удалось предзагрузить GLM-OCR: {e}')
    print('   Модель будет загружена при первом запуске')
EOF

# 🔹 Опционально: предзагрузка Surya detection (без FoundationPredictor)
RUN python << 'EOF' || true
import os
os.environ["HF_HOME"] = "/app/cache/huggingface"
os.environ["SURYA_CACHE_DIR"] = "/app/cache/surya"

try:
    from surya.detection import DetectionPredictor
    print('🔹 Предзагрузка Surya detection...')
    DetectionPredictor()
    print('✅ Surya detection предзагружена')
except Exception as e:
    print(f'⚠️ Не удалось предзагрузить Surya: {e}')
EOF

# === Копирование кода ===
# 🔹 Копируем с сохранением прав (будут переопределены ниже)
COPY shared/ ./shared/
COPY core/services/redis_client.py ./core/services/redis_client.py
COPY core/services/file_service.py ./core/services/file_service.py
COPY workers/OCR/worker.py ./workers/OCR/worker.py
COPY workers/OCR/src/ ./workers/OCR/src/

# 🔹 Финальная настройка прав: весь /app принадлежит appuser
RUN chown -R appuser:appgroup /app

# 🔹 Переключаемся на non-root пользователя
USER appuser

# 🔹 Рабочая директория для пользователя
WORKDIR /app

CMD ["python", "workers/OCR/worker.py"]