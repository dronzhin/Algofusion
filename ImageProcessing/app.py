# app.py
"""
Основное приложение FastAPI
"""
import logging
import time
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, UploadFile, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException as FastAPIHTTPException

from config import settings
from utils import setup_logging, get_logger
from endpoints import convert_image_endpoint, rotate_image_endpoint
from schemas import ConvertResponse, RotateResponse, HealthCheckResponse, ErrorResponse

# Настройка логирования
logger = setup_logging(
    log_level=settings.log_level,
    log_file=settings.log_file
)

# Глобальная переменная для времени запуска
startup_time = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    logger.info(f"Запуск приложения {settings.app_name} v{settings.app_version}")
    yield
    logger.info("Завершение работы приложения")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan
)


# Middleware для обработки ошибок
@app.middleware("http")
async def error_handling_middleware(request: Request, call_next):
    """Middleware для обработки ошибок"""
    try:
        response = await call_next(request)
        return response
    except FastAPIHTTPException as http_exc:
        # Пропускаем HTTP исключения дальше для стандартной обработки
        raise http_exc
    except Exception as e:
        logger.error(f"Необработанное исключение: {str(e)}")
        logger.error(f"Трейсбек: {traceback.format_exc()}")

        # Очищаем ошибку от непечатаемых символов
        safe_error = str(e).encode('utf-8', 'ignore').decode('utf-8')

        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": safe_error,
                "error_type": type(e).__name__,
                "timestamp": time.time()
            }
        )


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/convert", response_model=ConvertResponse)
async def convert_image(
        file: UploadFile = File(...),
        threshold: int = Form(settings.default_threshold, ge=0, le=255,
                             description="Порог бинаризации (0-255)")
):
    """
    Конвертирует изображения и PDF в бинарный формат с заданным порогом.
    """
    logger.info(f"Получен запрос на конвертацию файла: {file.filename}")
    result = await convert_image_endpoint(file, threshold)
    logger.info(f"Конвертация завершена, обработано {result.get('count', 0)} изображений")
    return result


@app.post("/rotate", response_model=RotateResponse)
async def rotate_image(
        file: UploadFile = File(...),
        min_line_length: int = Form(settings.default_min_line_length, ge=10, le=500,
                                   description="Минимальная длина линии"),
        max_line_gap: int = Form(settings.default_max_line_gap, ge=1, le=100,
                                description="Максимальный разрыв в линии"),
        use_morphology: bool = Form(False, description="Применять морфологические операции")
):
    """
    Находит самую длинную горизонтальную линию, определяет угол и поворачивает изображение.
    """
    logger.info(f"Получен запрос на поворот файла: {file.filename}")
    result = await rotate_image_endpoint(
        file, min_line_length, max_line_gap, use_morphology
    )
    logger.info(f"Поворот завершен, угол: {result.get('rotation_angle', 0):.2f}°")
    return result


@app.get("/", response_model=dict)
async def root():
    """Корневой эндпоинт"""
    return {
        "message": f"{settings.app_name} v{settings.app_version}",
        "endpoints": {
            "/convert": "POST - Конвертация в бинарный формат",
            "/rotate": "POST - Выравнивание по горизонтальной линии",
            "/health": "GET - Проверка состояния сервиса",
            "/docs": "GET - Документация API"
        },
        "documentation": "/docs",
        "config": {
            "debug": settings.debug,
            "host": settings.host,
            "port": settings.port
        }
    }


@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Эндпоинт для проверки здоровья сервера"""
    uptime = time.time() - startup_time if 'startup_time' in globals() else 0
    return HealthCheckResponse(
        status="healthy",
        timestamp=time.time(),
        version=settings.app_version,
        uptime=uptime
    )


if __name__ == "__main__":
    import uvicorn

    logger.info(f"Запуск сервера на {settings.host}:{settings.port}")

    uvicorn.run(
        "app:app",
        host=settings.host,
        port=settings.port,  # ← Теперь будет использовать PORT из env
        reload=settings.debug,
        workers=settings.workers,
        log_level=settings.log_level.lower()
    )