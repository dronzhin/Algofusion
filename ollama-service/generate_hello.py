#!/usr/bin/env python3
"""
OCR Test Suite: Генерация изображения → Распознавание через Ollama
Исправленная версия с надёжной проверкой готовности сервера
"""

import requests
import base64
import time
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from typing import Optional, Tuple


def generate_image_from_text(
        text: str,
        width: int = 300,
        height: int = 120,
        font_size: int = 48,
        bg_color: Tuple[int, int, int] = (255, 255, 255),
        text_color: Tuple[int, int, int] = (0, 0, 0),
        output_path: Optional[str] = None
) -> bytes:
    """Генерирует изображение с текстом и возвращает байты PNG"""
    img = Image.new('RGB', (width, height), color=bg_color)
    draw = ImageDraw.Draw(img)

    # Кроссплатформенный подбор шрифта
    fonts_to_try = [
        "DejaVuSans.ttf", "LiberationSans-Regular.ttf",  # Linux
        "Arial.ttf", "Arial",  # Windows
        "Helvetica.ttf", "Helvetica"  # macOS
    ]

    font = None
    for font_name in fonts_to_try:
        try:
            font = ImageFont.truetype(font_name, font_size)
            break
        except:
            continue

    if font is None:
        font = ImageFont.load_default()
        print("⚠️  Используется шрифт по умолчанию (системные шрифты не найдены)")

    # Центрирование текста
    text_bbox = draw.textbbox((0, 0), text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    x = (width - text_width) / 2
    y = (height - text_height) / 2

    draw.text((x, y), text, fill=text_color, font=font)

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    image_bytes = buffer.getvalue()

    if output_path:
        with open(output_path, "wb") as f:
            f.write(image_bytes)
        print(f"✅ Изображение сохранено: {output_path}")

    return image_bytes


def wait_for_ollama(
        ollama_url: str = "http://localhost:8003",
        timeout: int = 60
) -> bool:
    """
    Ждёт готовности Ollama сервера с повторными попытками

    Returns:
        True если сервер готов, False если таймаут
    """
    print(f"\n⏳ Ожидание готовности Ollama на {ollama_url} (таймаут: {timeout} сек)...")

    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            # Проверяем базовый эндпоинт (не требует загруженных моделей)
            resp = requests.get(f"{ollama_url}", timeout=5)
            if resp.status_code == 200:
                # Дополнительная проверка API
                api_resp = requests.get(f"{ollama_url}/api/tags", timeout=5)
                if api_resp.status_code == 200:
                    version = api_resp.json().get("version", "unknown")
                    print(f"✅ Ollama готов! Версия: {version}")
                    return True
        except requests.exceptions.RequestException:
            pass

        print(".", end="", flush=True)
        time.sleep(2)

    print("\n❌ Таймаут ожидания Ollama")
    return False


def ocr_image(
        image_bytes: bytes,
        model: str = "glm-ocr:latest",
        ollama_url: str = "http://localhost:8003"
) -> str:
    """Распознаёт текст с изображения через Ollama"""
    base64_image = base64.b64encode(image_bytes).decode('utf-8')

    response = requests.post(
        f"{ollama_url}/api/generate",
        json={
            "model": model,
            "prompt": "Extract all text. Return ONLY the text without any additional words or commentary.",
            "stream": False,
            "images": [base64_image],
            "options": {"temperature": 0.1}
        },
        timeout=120
    )
    response.raise_for_status()

    return response.json()["response"].strip()


def test_ocr_cycle(
        test_text: str = "привет",
        model: str = "glm-ocr:latest",
        ollama_url: str = "http://localhost:8003"
) -> bool:
    """Полный цикл тестирования: текст → изображение → распознавание"""
    print("\n" + "=" * 70)
    print(f"🧪 ТЕСТ OCR: '{test_text}' → модель {model}")
    print("=" * 70)

    # Генерация изображения
    print("\n🖼️  Шаг 1: Генерация изображения...")
    try:
        safe_filename = "".join(c if c.isalnum() else "_" for c in test_text)[:20]
        image_bytes = generate_image_from_text(
            text=test_text,
            width=300,
            height=120,
            font_size=48,
            output_path=f"test_{safe_filename}.png"
        )
        print(f"✅ Изображение создано ({len(image_bytes)} байт)")
    except Exception as e:
        print(f"❌ Ошибка генерации: {e}")
        return False

    # Проверка готовности Ollama
    print("\n🔍 Шаг 2: Проверка готовности Ollama...")
    if not wait_for_ollama(ollama_url, timeout=45):
        print(f"\n💡 Совет: Запустите контейнер и подождите 30 секунд:")
        print("   docker run -d --name ollama-ocr -p 8003:11434 -v ollama_/root/.ollama ollama/ollama:latest")
        print("   sleep 30")
        print("   docker exec ollama-ocr ollama pull glm-ocr:latest")
        return False

    # Распознавание
    print(f"\n🤖 Шаг 3: Распознавание текста моделью '{model}'...")
    try:
        recognized_text = ocr_image(image_bytes, model, ollama_url)
        print(f"✅ Распознано: '{recognized_text}'")
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            print(f"❌ Эндпоинт не найден — сервер не полностью инициализирован")
            print("   Подождите ещё 15-30 секунд после запуска контейнера")
            return False
        elif e.response.status_code == 400 and "model" in e.response.text.lower():
            print(f"❌ Модель '{model}' не загружена")
            print(f"   Загрузите модель: docker exec ollama-ocr ollama pull {model}")
            return False
        else:
            print(f"❌ Ошибка API ({e.response.status_code}): {e.response.text[:200]}")
            return False
    except Exception as e:
        print(f"❌ Ошибка распознавания: {type(e).__name__}: {e}")
        return False

    # Сравнение результатов
    print("\n📊 Шаг 4: Сравнение результатов...")
    print(f"   Оригинал:   '{test_text}'")
    print(f"   Распознано: '{recognized_text}'")

    original_norm = test_text.strip().lower()
    recognized_norm = recognized_text.strip().lower()

    if original_norm == recognized_norm:
        print("   ✅ УСПЕХ: текст распознан идеально!")
        return True
    else:
        # Простая метрика схожести
        matches = sum(1 for a, b in zip(original_norm, recognized_norm) if a == b)
        similarity = matches / max(len(original_norm), len(recognized_norm)) * 100
        print(f"   ⚠️  ЧАСТИЧНЫЙ УСПЕХ: схожесть {similarity:.0f}%")
        if similarity < 80:
            print(f"   💡 Совет: попробуйте модель 'deepseek-ocr:latest' для лучшей точности")
        return similarity >= 70


if __name__ == "__main__":
    print("=" * 70)
    print("🚀 OCR ТЕСТ: Генерация изображений → Распознавание через Ollama")
    print("=" * 70)

    # Проверка зависимости Pillow
    try:
        from PIL import Image
    except ImportError:
        print("\n❌ Ошибка: не установлен пакет Pillow")
        print("   Установите: pip install Pillow requests")
        exit(1)

    # Проверка запущенного контейнера через docker CLI
    import subprocess

    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=ollama-ocr", "--format", "{{.Status}}"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if "Up" in result.stdout:
            print("\n🐳 Контейнер ollama-ocr: ЗАПУЩЕН")
        else:
            print("\n⚠️  Контейнер ollama-ocr не обнаружен в списке запущенных")
            print(
                "   Запустите: docker run -d --name ollama-ocr -p 8003:11434 -v ollama_/root/.ollama ollama/ollama:latest")
    except Exception as e:
        print(f"\n⚠️  Не удалось проверить статус контейнера через docker CLI: {e}")

    # Запуск тестов
    results = []
    results.append(test_ocr_cycle("привет", "glm-ocr:latest"))
    results.append(test_ocr_cycle("Hello", "glm-ocr:latest"))
    results.append(test_ocr_cycle("12345", "deepseek-ocr:latest"))

    # Итоги
    print("\n" + "=" * 70)
    print(f"📈 ИТОГИ: {sum(results)}/{len(results)} тестов пройдено успешно")
    print("=" * 70)

    if all(results):
        print("\n✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ — ваш OCR-сервис работает корректно!")
    else:
        print("\n⚠️  Некоторые тесты завершились неудачно. Проверьте:")
        print("   1. Контейнер запущен более 30 секунд назад")
        print("   2. Модели загружены: docker exec ollama-ocr ollama pull glm-ocr:latest")
        print("   3. Порт 8003 не занят другим приложением: sudo lsof -i :8003")