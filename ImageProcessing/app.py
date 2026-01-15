from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import Response
import io
from PIL import Image
from pdf2image import convert_from_bytes
import base64

app = FastAPI(title="Image to Binary Converter")

@app.post("/convert")
async def convert_image(file: UploadFile = File(...), output_format: str = "bytes"):
    """
    Принимает файлы PDF, JPG, PNG.
    Параметр output_format: 'bytes' (по умолчанию) или 'base64'.
    Для PDF конвертирует первую страницу в изображение.
    Возвращает бинарные данные изображения.
    """
    if not file.content_type.startswith(("image/", "application/pdf")):
        raise HTTPException(status_code=400, detail="Unsupported file type")

    contents = await file.read()

    try:
        if file.content_type == "application/pdf":
            # Конвертируем первую страницу PDF в изображение
            images = convert_from_bytes(contents, first_page=1, last_page=1)
            img = images[0]
        else:
            # Открываем как изображение
            img = Image.open(io.BytesIO(contents)).convert("RGB")

        # Сохраняем в буфер
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        binary_data = buffer.getvalue()

        if output_format == "base64":
            b64 = base64.b64encode(binary_data).decode('utf-8')
            return {"binary_base64": b64}
        else:
            # Возвращаем чистые байты как тело ответа
            return Response(content=binary_data, media_type="application/octet-stream")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")