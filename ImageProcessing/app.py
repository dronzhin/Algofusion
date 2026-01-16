from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from endpoints.convert import convert_image_endpoint
from endpoints.rotate import rotate_image_endpoint

app = FastAPI(title="Image Processing API", version="1.0.0")

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/convert")
async def convert_image(
    file: UploadFile = File(...),
    threshold: int = Form(128, ge=0, le=255, description="Порог бинаризации (0-255)")
):
    """
    Конвертирует изображения и PDF в бинарный формат с заданным порогом.
    """
    return await convert_image_endpoint(file, threshold)

@app.post("/rotate")
async def rotate_image(
    file: UploadFile = File(...),
    min_line_length: int = Form(50, ge=10, le=500, description="Минимальная длина линии"),
    max_line_gap: int = Form(20, ge=1, le=100, description="Максимальный разрыв в линии"),
    use_morphology: bool = Form(False, description="Применять морфологические операции")
):
    """
    Находит самую длинную горизонтальную линию, определяет угол и поворачивает изображение.
    """
    return await rotate_image_endpoint(file, min_line_length, max_line_gap, use_morphology)

@app.get("/")
async def root():
    return {
        "message": "Image Processing API",
        "endpoints": {
            "/convert": "POST - Конвертация в бинарный формат",
            "/rotate": "POST - Выравнивание по горизонтальной линии"
        },
        "documentation": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)