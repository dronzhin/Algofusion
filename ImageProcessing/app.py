from fastapi import FastAPI, File, UploadFile, HTTPException, Form
import io
from PIL import Image
from pdf2image import convert_from_bytes
import base64

app = FastAPI(title="Чёрно-белый конвертер")


@app.post("/convert")
async def convert_image(
        file: UploadFile = File(...),
        threshold: int = Form(128),  # Принимаем как Form поле
        output_format: str = Form("base64")
):
    """
    Конвертирует изображения и PDF в бинарный формат с заданным порогом.
    """
    # Проверка типа файла
    if not file.content_type.startswith(("image/", "application/pdf")):
        raise HTTPException(status_code=400, detail="Неподдерживаемый тип файла")

    contents = await file.read()

    try:
        # Обработка в зависимости от типа файла
        if file.content_type == "application/pdf":
            images = convert_from_bytes(contents)
        else:
            img = Image.open(io.BytesIO(contents))
            images = [img]

        # Конвертация в бинарный формат
        binary_images = []
        for img in images:
            # Преобразование в grayscale если необходимо
            if img.mode != 'L':
                img = img.convert('L')

            # Отладочная информация
            print(f"Обработка изображения: mode={img.mode}, size={img.size}, threshold={threshold}")

            # Бинаризация
            if threshold < 0:
                threshold = 0
            elif threshold > 255:
                threshold = 255

            img_bw = img.point(lambda x: 255 if x > threshold else 0, mode='1')
            binary_images.append(img_bw)

        # Сохранение в PNG
        png_buffers = []
        for i, img in enumerate(binary_images):
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            png_buffers.append(buf.getvalue())
            print(f"Страница {i + 1}: сохранено {len(buf.getvalue())} байт")

        # Кодирование в base64
        b64_list = [base64.b64encode(data).decode('utf-8') for data in png_buffers]
        return {"images_base64": b64_list}

    except Exception as e:
        print(f"Ошибка обработки: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка обработки: {str(e)}")