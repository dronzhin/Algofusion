# workers/OCR/Dockerfile
FROM python:3.12-slim

# Метаданные
LABEL org.opencontainers.image.title="Algofusion OCR Worker"
LABEL org.opencontainers.image.description="Worker для OCR-обработки: Tesseract, EasyOCR, Surya, GLM"
LABEL org.opencontainers.image.version="0.1.0"

# 🔹 Переменные для кэша HuggingFace
ENV HF_HOME=/root/.cache/huggingface \
    TRANSFORMERS_CACHE=/root/.cache/huggingface/hub \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
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

# === Установка Python-зависимостей ===
COPY workers/OCR/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 🔹 ПРЕДЗАГРУЗКА МОДЕЛЕЙ ПРИ СБОРКЕ
# 🔹 Скачиваем GLM-OCR модель в кэш, чтобы она была в образе
RUN python << 'EOF'
from transformers import AutoProcessor, AutoModelForImageTextToText
print('🔹 Предзагрузка модели zai-org/GLM-OCR...')
AutoProcessor.from_pretrained('zai-org/GLM-OCR', trust_remote_code=True)
AutoModelForImageTextToText.from_pretrained(
    'zai-org/GLM-OCR',
    trust_remote_code=True,
    torch_dtype='auto'
)
print('✅ Модель предзагружена в кэш')
EOF

# 🔹 Опционально: предзагрузить другие тяжёлые модели (раскомментируйте при необходимости)
RUN python << 'EOF'
from surya.detection import DetectionPredictor
from surya.recognition import RecognitionPredictor
DetectionPredictor()
RecognitionPredictor()
print('✅ Surya модели предзагружены')
EOF

# === Проверка установки ===
RUN python -c "import pytesseract; print('✅ Tesseract OK')" && \
    python -c "import easyocr; print('✅ EasyOCR OK')" && \
    python -c "import surya; print('✅ Surya OK')" && \
    python -c "from transformers import AutoModelForImageTextToText; print('✅ Transformers OK')"

# === Копирование кода ===
COPY shared/ ./shared/
COPY core/services/redis_client.py ./core/services/redis_client.py
COPY core/services/file_service.py ./core/services/file_service.py
COPY workers/OCR/worker.py ./workers/OCR/worker.py
COPY workers/OCR/src/ ./workers/OCR/src/

# 🔹 Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c " \
from core.services.redis_client import get_redis_client; \
from workers.OCR.src.ocr.tesseract import TesseractEngine; \
from workers.OCR.src.ocr.easyocr import EasyOCREngine; \
from workers.OCR.src.ocr.surya import SuryaEngine; \
from workers.OCR.src.ocr.glm import GLMEngine; \
get_redis_client().client.ping(); \
print('✅ All OCR engines available')" || exit 1

CMD ["python", "workers/OCR/worker.py"]