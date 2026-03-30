from PIL import Image
from pathlib import Path
import numpy as np
import cv2


def convert_dpi(
    input_img: Image, 
    from_dpi: int = 600, 
    to_dpi: int = 300
) -> Image:
    """
    Физически меняет размер изображения для конвертации DPI
    """
    # Вычисляем коэффициент масштабирования
    scale = to_dpi / from_dpi  # 300 / 600 = 0.5
    
    # Новый размер
    new_width = int(input_img.width * scale)
    new_height = int(input_img.height * scale)
    new_size = (new_width, new_height)
    
    # Изменяем размер (LANCZOS даёт лучшее качество при уменьшении)
    return input_img.resize(new_size, resample=Image.LANCZOS)


# Угол по линиям (Hough)
def detect_skew_angle_by_hough_lines(
    image: np.ndarray,
    canny1: int = 50,
    canny2: int = 150,
    hough_threshold: int = 150,
    min_line_length: int = 200,
    max_line_gap: int = 20,
    max_abs_angle: float = 20.0
) -> float:
    """
    Определяет угол перекоса документа (в градусах) по линиям таблиц/рамок.

    Подходит для:
    - цветных и серых сканов
    - документов без белого фона
    - накладных, счетов, таблиц, бланков

    Возвращает:
        float: угол поворота (в градусах).
               Положительный -> поворот против часовой стрелки.
               Отрицательный -> по часовой стрелке.
    """

    # --- 1. Переводим в grayscale ---
    # Цвет нам не нужен, линии лучше видны в градациях серого
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # --- 2. Лёгкое размытие ---
    # Убираем мелкий шум, не разрушая линии
    gray = cv2.GaussianBlur(gray, (5, 5), 0)

    # --- 3. Поиск границ ---
    # Canny стабилен даже при плохом фоне
    edges = cv2.Canny(gray, canny1, canny2, apertureSize=3)

    #plt.imshow(edges)

    # --- 4. Поиск линий (вероятностный Хафф) ---
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180 / 4,
        threshold=hough_threshold,
        minLineLength=min_line_length,
        maxLineGap=max_line_gap
    )

    angles = []

    # --- 5. Считаем углы найденных линий ---
    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]

            # угол линии относительно горизонтали
            angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))

            # оставляем только почти горизонтальные линии
            if abs(angle) <= max_abs_angle:
                angles.append(angle)

    # --- 6. Итоговый угол ---
    # Медиана устойчива к выбросам (подписи, печати, случайные линии)
    if len(angles) == 0:
        return 0.0, False, angles

    return float(np.median(angles)), True, angles



# Угол по текстовым контурам
def detect_skew_angle_by_text_contours(image: np.ndarray) -> float:
    """
    Определение угла по тексту.
    Используется как fallback.
    """

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # adaptive threshold устойчив к плохому фону
    th = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_MEAN_C,
        cv2.THRESH_BINARY_INV,
        31,
        15
    )

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    th = cv2.morphologyEx(th, cv2.MORPH_OPEN, kernel)

    contours, _ = cv2.findContours(
        th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    angles = []

    for cnt in contours:
        if cv2.contourArea(cnt) < 2000:
            continue

        rect = cv2.minAreaRect(cnt)
        angle = rect[-1]

        # нормализация угла OpenCV
        if angle < -45:
            angle = 90 + angle

        angles.append(angle)

    if not angles:
        return 0.0, False, angles

    return float(np.median(angles)), True, angles


# Функция определения угла: сначала пробуем по линиям, потом по текстовым контурам
def detect_skew_angle(image: np.ndarray) -> float:
    """
    Определяет угол перекоса документа.

    Алгоритм:
    1) Пытаемся найти угол по линиям (Hough) — самый надёжный способ
    2) Если линий мало или результат нестабилен → fallback на текст

    Возвращает:
        float — угол поворота в градусах
    """

    # ===============================
    # 1. Попытка №1 — ПО ЛИНИЯМ
    # ===============================

    angle, reliable, _ = detect_skew_angle_by_hough_lines(image)

    if reliable:
        return angle

    # ===============================
    # 2. Fallback — ПО ТЕКСТУ
    # ===============================

    angle, reliable, _ = detect_skew_angle_by_text_contours(image)
    return angle
    
# Визуализация линий Hough
def visualize_hough_lines(image: np.ndarray) -> np.ndarray:
    """
    Возвращает копию изображения с нарисованными
    почти горизонтальными линиями Hough.
    """

    vis = image.copy()

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    # display(Image.fromarray(edges))

    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180 / 4,
        threshold=150,
        minLineLength=200,
        maxLineGap=20
    )

    if lines is None:
        return vis

    for line in lines:
        x1, y1, x2, y2 = line[0]
        angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))

        # рисуем только те линии, которые участвуют в расчёте
        if abs(angle) <= 15:
            cv2.line(vis, (x1, y1), (x2, y2), (0, 0, 255), 2)

            # подпишем угол
            mx, my = (x1 + x2) // 2, (y1 + y2) // 2
            cv2.putText(
                vis,
                f"{angle:.1f}",
                (mx, my),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                (0, 0, 255),
                1
            )

    return vis


# Визуализация контуров текста (fallback)
def visualize_text_contours(image: np.ndarray) -> np.ndarray:
    """
    Возвращает изображение с контурами текста
    и их ориентацией (fallback-метод).
    """

    vis = image.copy()

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    th = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_MEAN_C,
        cv2.THRESH_BINARY_INV,
        31,
        15
    )

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    th = cv2.morphologyEx(th, cv2.MORPH_OPEN, kernel)

    contours, _ = cv2.findContours(
        th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    for cnt in contours:
        if cv2.contourArea(cnt) < 2000:
            continue

        rect = cv2.minAreaRect(cnt)
        box = cv2.boxPoints(rect)
        box = box.astype(int)

        angle = rect[-1]
        if angle < -45:
            angle = 90 + angle

        # рисуем прямоугольник текста
        cv2.drawContours(vis, [box], 0, (255, 0, 0), 2)

        cx, cy = np.mean(box, axis=0).astype(int)
        cv2.putText(
            vis,
            f"{angle:.1f}",
            (cx, cy),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            (255, 0, 0),
            1
        )

    return vis

def rotate_image_by_angle(image: np.ndarray, angle: float) -> np.ndarray:
    """
    Поворачивает изображение на заданный угол
    с сохранением содержимого.
    """
    h, w = image.shape[:2]
    center = (w // 2, h // 2)

    M = cv2.getRotationMatrix2D(center, angle, 1.0)

    rotated = cv2.warpAffine(
        image,
        M,
        (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE
    )

    return rotated


def rotate_image(image_src: Image) -> Image:
    
    img = np.array(image_src)
    angle = detect_skew_angle(img)
    print(f"Угол: {angle:.2f}°")

    # визуализация
    #vis_lines = visualize_hough_lines(img)
    #vis_text = visualize_text_contours(img)

    # cv2.imwrite(f"debug_{i:05}_hough.png", vis_lines)
    # cv2.imwrite(f"debug_{i:05}_text.png", vis_text)

    # итоговое выравнивание
    return Image.fromarray(rotate_image_by_angle(img, angle))
