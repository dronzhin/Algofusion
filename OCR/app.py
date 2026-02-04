# app

# !/usr/bin/env python3
"""
Unified OCR Server — локальный запуск без Docker
Поддерживаемые модели: deepseek-ocr, deepseek-ocr2, paddleocr-vl-1.5, glm-ocr
Поддержка многостраничных документов (PDF, изображения) с метрикой уверенности
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
import io
import torch
import sys
import os
import time
from typing import List, Tuple, Optional

# Импорт логгера и утилит
from utils import logger, PDFHandler, confidence_calculator

# Добавляем текущую директорию в PATH
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Глобальное хранилище моделей (ленивая загрузка)
models = {}
model_load_times = {}  # Для отслеживания времени загрузки
pdf_handler = PDFHandler(dpi=300)  # Обработчик PDF


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan контекстный менеджер для инициализации и очистки при запуске/остановке сервера.
    """
    # ===== ON STARTUP =====
    logger.info("=" * 70)
    logger.info("🚀 Unified OCR Server запускается...")
    logger.info(f"   PyTorch CUDA: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        logger.info(
            f"   GPU: {torch.cuda.get_device_name(0)} | VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024 ** 3:.1f} GB")
    else:
        logger.warning("⚠️  GPU недоступен! Сервер будет работать на CPU (медленно)")
    logger.info("=" * 70)

    logger.info("\n📋 Доступные модели:")
    logger.info("  • deepseek-ocr      (1.3B) — базовый OCR")
    logger.info("  • deepseek-ocr2     (3B)   — таблицы + структура")
    logger.info("  • paddleocr-vl-1.5  (0.9B) — многоязычный текст")
    logger.info("  • glm-ocr           (0.9B) — быстрый чистый OCR")

    logger.info("\n🌐 API эндпоинты:")
    logger.info("  GET  /              — информация о сервере")
    logger.info("  GET  /models        — список моделей")
    logger.info("  POST /ocr           — распознавание текста (изображение или PDF)")
    logger.info("  GET  /docs          — интерактивная документация (Swagger)")
    logger.info("=" * 70)

    yield  # Сервер работает здесь

    # ===== ON SHUTDOWN =====
    logger.info("\n" + "=" * 70)
    logger.info("🛑 Unified OCR Server останавливается...")

    # Освобождаем память моделей
    global models
    if models:
        logger.info(f"Освобождение памяти: {len(models)} загруженных моделей")
        for model_name in list(models.keys()):
            del models[model_name]
        torch.cuda.empty_cache()
        logger.info("✅ Память очищена")

    logger.info("=" * 70 + "\n")


# Создаём приложение с контекстом жизненного цикла
app = FastAPI(
    title="Unified OCR Server",
    version="1.0",
    lifespan=lifespan
)

# CORS для локальной разработки
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def validate_file_type(file_bytes: bytes, filename: str) -> Optional[str]:
    """
    Валидация типа файла

    Args:
        file_bytes: байты файла
        filename: имя файла

    Returns:
        "pdf" | "image" | None (если не поддерживается)
    """
    # Проверка расширения
    ext = filename.lower().split('.')[-1]

    if ext in ['pdf']:
        return "pdf"
    elif ext in ['jpg', 'jpeg', 'png', 'bmp', 'tiff', 'webp']:
        return "image"
    else:
        return None


def process_single_image_with_confidence(
        image: Image.Image,
        model_name: str,
        prompt: str,
        return_confidence: bool
) -> Tuple[str, Optional[float]]:
    """
    Обработка одного изображения через выбранную модель с расчётом уверенности

    Args:
        image: PIL Image
        model_name: имя модели
        prompt: промпт для модели
        return_confidence: возвращать ли метрику уверенности

    Returns:
        (распознанный текст, уверенность или None)
    """
    # Загрузка модели при первом запросе
    if model_name not in models:
        logger.info(f"⏳ Загрузка модели '{model_name}'...")
        load_start = time.time()

        try:
            if model_name == "deepseek-ocr":
                from models import DeepSeekOCRModel
                models[model_name] = DeepSeekOCRModel()
            elif model_name == "deepseek-ocr2":
                from models import DeepSeekOCR2Model
                models[model_name] = DeepSeekOCR2Model()
            elif model_name == "paddleocr-vl-1.5":
                from models import PaddleOCRVLModel
                models[model_name] = PaddleOCRVLModel()
            elif model_name == "glm-ocr":
                from models import GLMOCRModel
                models[model_name] = GLMOCRModel()

            load_time = time.time() - load_start
            model_load_times[model_name] = load_time
            logger.info(f"✅ Модель '{model_name}' загружена за {load_time:.2f} сек")

        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Ошибка загрузки модели '{model_name}': {error_msg}", exc_info=True)

            if "404 Client Error" in error_msg and "deepseek-ocr2" in model_name:
                error_msg = "DeepSeek-OCR 2 ещё не опубликована на Hugging Face."
            elif "trust_remote_code" in error_msg:
                error_msg = "Требуется явно разрешить trust_remote_code=True при загрузке модели"

            raise RuntimeError(f"Ошибка загрузки модели {model_name}: {error_msg}")

    # Инференс
    try:
        result, confidence = models[model_name].infer(image, prompt, return_confidence)
        return result, confidence
    except Exception as e:
        logger.error(f"❌ Ошибка инференса: {str(e)}", exc_info=True)
        raise


@app.get("/")
async def root():
    """Простая главная страница"""
    logger.debug("Запрос главной страницы")
    return {
        "message": "Unified OCR Server",
        "version": "1.0",
        "api_docs": "/docs",
        "models": "/models",
        "status": "running"
    }


@app.get("/models")
async def list_models():
    """Список доступных и загруженных моделей"""
    logger.info("Запрос списка моделей")

    available = [
        "deepseek-ocr",
        "deepseek-ocr2",
        "paddleocr-vl-1.5",
        "glm-ocr"
    ]

    loaded_info = {}
    for model_name in models.keys():
        load_time = model_load_times.get(model_name, "N/A")
        loaded_info[model_name] = {
            "status": "loaded",
            "load_time_sec": round(load_time, 2) if isinstance(load_time, float) else load_time
        }

    return {
        "available_models": available,
        "loaded_models": list(models.keys()),
        "loaded_models_details": loaded_info,
        "cuda_available": torch.cuda.is_available(),
        "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "total_loaded": len(models)
    }


@app.post("/ocr")
async def ocr_inference(
        model_name: str = Form(...),
        image: UploadFile = File(...),
        prompt: str = Form("Extract all text"),
        return_confidence: bool = Form(True)
):
    """
    Распознавание текста с изображения или многостраничного документа

    Параметры:
      model_name: deepseek-ocr | deepseek-ocr2 | paddleocr-vl-1.5 | glm-ocr
      image: файл изображения (jpg, png) или PDF
      prompt: инструкция для модели (опционально)
      return_confidence: возвращать ли метрику уверенности (по умолчанию true)
    """
    start_time = time.time()
    request_id = f"req_{int(start_time * 1000)}"

    logger.info(f"[{request_id}] 📥 Новый запрос | Модель: {model_name} | Файл: {image.filename}")

    # Валидация модели
    valid_models = ["deepseek-ocr", "deepseek-ocr2", "paddleocr-vl-1.5", "glm-ocr"]
    if model_name not in valid_models:
        error_msg = f"Неверная модель '{model_name}'. Доступные: {', '.join(valid_models)}"
        logger.error(f"[{request_id}] ❌ {error_msg}")
        raise HTTPException(status_code=400, detail=error_msg)

    # Чтение файла
    try:
        file_bytes = await image.read()
        file_type = validate_file_type(file_bytes, image.filename)

        if file_type is None:
            raise HTTPException(
                status_code=400,
                detail=f"Неподдерживаемый формат файла: {image.filename}. Поддерживаются: PDF, JPG, PNG, BMP, TIFF, WEBP"
            )

        logger.debug(f"[{request_id}] 📁 Тип файла: {file_type.upper()} | Размер: {len(file_bytes) / 1024:.1f} KB")

    except Exception as e:
        logger.error(f"[{request_id}] ❌ Ошибка чтения файла: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Ошибка чтения файла: {str(e)}")

    # Обработка в зависимости от типа файла
    try:
        if file_type == "pdf":
            # Обработка многостраничного PDF
            logger.info(f"[{request_id}] 📄 Обработка многостраничного PDF...")

            # Конвертация PDF в изображения
            try:
                pages = pdf_handler.pdf_bytes_to_images(file_bytes)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

            if not pages:
                raise HTTPException(status_code=400, detail="PDF файл не содержит страниц")

            # Обработка каждой страницы
            results = []
            page_confidences = []

            for page_num, page_image in pages:
                page_start = time.time()
                logger.info(f"[{request_id}] 📄 Страница {page_num}/{len(pages)}...")

                try:
                    text, confidence = process_single_image_with_confidence(
                        page_image, model_name, prompt, return_confidence
                    )
                    page_confidences.append(confidence if confidence is not None else 0.5)

                    results.append({
                        "page_number": page_num,
                        "text": text,
                        "confidence": confidence,
                        "timing_seconds": round(time.time() - page_start, 2)
                    })

                    logger.info(
                        f"[{request_id}] ✅ Страница {page_num} обработана за {time.time() - page_start:.2f} сек" +
                        (f" | Уверенность: {confidence:.2f}" if confidence else ""))

                except Exception as e:
                    logger.error(f"[{request_id}] ❌ Ошибка обработки страницы {page_num}: {str(e)}", exc_info=True)
                    # Продолжаем обработку остальных страниц
                    results.append({
                        "page_number": page_num,
                        "error": str(e),
                        "text": None,
                        "confidence": None,
                        "timing_seconds": round(time.time() - page_start, 2)
                    })
                    page_confidences.append(0.1)  # Низкая уверенность при ошибке

            # Расчёт общей уверенности для документа (минимальная по страницам для консервативности)
            overall_confidence = min(page_confidences) if page_confidences else None

            total_time = time.time() - start_time

            logger.info(f"[{request_id}] ✅ PDF обработан | Всего: {total_time:.2f} сек | Страниц: {len(results)}")

            # Объединяем текст всех страниц
            combined_text = "\n\n--- СТРАНИЦА РАЗДЕЛИТЕЛЬ ---\n\n".join(
                f"[Страница {r['page_number']}]\n{r['text']}"
                for r in results if r.get('text')
            )

            return {
                "model": model_name,
                "prompt": prompt,
                "file_type": "pdf",
                "total_pages": len(pages),
                "processed_pages": len([r for r in results if r.get('text')]),
                "pages": results,
                "combined_text": combined_text,
                "confidence": overall_confidence,
                "confidence_per_page": page_confidences,
                "status": "success",
                "timing": {
                    "total_seconds": round(total_time, 2),
                    "pages": [r.get('timing_seconds', 0) for r in results]
                },
                "request_id": request_id
            }

        else:
            # Обработка одиночного изображения
            logger.debug(f"[{request_id}] 🖼️  Обработка изображения...")

            try:
                img = Image.open(io.BytesIO(file_bytes)).convert("RGB")
            except Exception as e:
                logger.error(f"[{request_id}] ❌ Ошибка обработки изображения: {str(e)}", exc_info=True)
                raise HTTPException(status_code=400, detail=f"Ошибка обработки изображения: {str(e)}")

            # Инференс
            infer_start = time.time()
            text, confidence = process_single_image_with_confidence(
                img, model_name, prompt, return_confidence
            )
            infer_time = time.time() - infer_start

            total_time = time.time() - start_time

            logger.info(f"[{request_id}] ✅ Успешно | Инференс: {infer_time:.2f} сек | Всего: {total_time:.2f} сек" +
                        (f" | Уверенность: {confidence:.2f}" if confidence else ""))
            logger.debug(f"[{request_id}] 📝 Результат (первые 100 символов): {text[:100]}...")

            return {
                "model": model_name,
                "prompt": prompt,
                "file_type": "image",
                "text": text,
                "confidence": confidence,
                "status": "success",
                "timing": {
                    "inference_seconds": round(infer_time, 2),
                    "total_seconds": round(total_time, 2)
                },
                "request_id": request_id
            }

    except Exception as e:
        logger.error(f"[{request_id}] ❌ Ошибка обработки: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка обработки: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    logger.info("\n🚀 Запуск сервера на http://localhost:8000")
    logger.info("   Документация: http://localhost:8000/docs\n")

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")