from fastapi import FastAPI, File, UploadFile, HTTPException, Query
import io
from PIL import Image
from pdf2image import convert_from_bytes
import base64

app = FastAPI(title="Чёрно-белый конвертер (только 2 цвета)")


@app.post("/convert")
async def convert_image(
        file: UploadFile = File(...),
        threshold: int = Query(128, ge=0, le=255, description="Порог бинаризации (0–255)")
):
    """
    Принимает PDF, JPG, PNG.
    Конвертирует все страницы в строго чёрно-белые изображения (режим '1', без dithering).
    Возвращает список base64-изображений.

    Параметры:
      - file: загружаемый файл
      - threshold: порог яркости (по умолчанию 128). Пиксели ярче — белые, темнее — чёрные.
    """
    if not file.content_type.startswith(("image/", "application/pdf")):
        raise HTTPException(status_code=400, detail="Неподдерживаемый тип файла")

    contents = await file.read()

    try:
        # Обработка PDF или изображения
        if file.content_type == "application/pdf":
            images = convert_from_bytes(contents)
        else:
            img = Image.open(io.BytesIO(contents))
            images = [img]

        binary_images = []
        for img in images:
            # Приведение к grayscale, если нужно
            if img.mode != 'L':
                img = img.convert('L')
            # Бинаризация без dithering: только чёрный (0) и белый (255)
            img_bw = img.point(lambda x: 255 if x > threshold else 0, mode='1')
            binary_images.append(img_bw)

        # Сохранение в PNG-байты
        png_buffers = []
        for img in binary_images:
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            png_buffers.append(buf.getvalue())

        # Кодирование в base64
        b64_list = [base64.b64encode(data).decode('utf-8') for data in png_buffers]
        return {"images_base64": b64_list}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка обработки: {str(e)}")