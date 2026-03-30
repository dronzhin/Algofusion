FROM python:3.10-slim

WORKDIR /app

COPY workers/preprocessing_stage_1/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN apt-get update && apt-get install -y --no-install-recommends \
    # Для pdf2image (конвертация PDF)
    poppler-utils \
    # Для OpenCV (поворот изображений) — обновлённые имена пакетов
    libgl1 \
    libglib2.0-0 \
    # Утилиты для отладки
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && ldconfig  # ← Обновляем кэш библиотек



# Копируем весь код в образ
COPY shared/ ./shared/
COPY core/ ./core/
COPY workers/preprocessing_stage_1 ./workers/preprocessing_stage_1/

CMD ["python", "workers/preprocessing_stage_1/worker.py"]