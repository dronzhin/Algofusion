import fitz  # PyMuPDF
import os
from PIL import Image, ImageEnhance, ImageFilter
import numpy as np

#import utils.preprocessing as pp
from .images import convert_dpi, rotate_image

# import os
from pathlib import Path
# from PIL import Image

FILES_PATH = '../tmp/'

def convert_pdf_to_images(pdf_path, output_folder, dpi=600):
    """Конвертирует PDF в изображения через PyMuPDF"""
    
    doc = fitz.open(pdf_path)
    
    # Расчет масштаба: 72 DPI — базовое, нам нужно больше
    zoom = dpi / 72
    matrix = fitz.Matrix(zoom, zoom)
    
    for page_num in range(len(doc)):
        # print(f"📄 Страница № {page_num + 1} из {len(doc)}")
        page = doc[page_num]
        
        # Рендер страницы в изображение
        pix = page.get_pixmap(matrix=matrix)
        
        # Сохранение
        output_path = f"{output_folder}/{pdf_path.stem}_page_{page_num + 1}.png"
        pix.save(output_path)
        
        print(f"✅ Страница {page_num + 1} сохранена: {output_path}")
    
    doc.close()


# 4.1 Искусственные трёхканальные цветные -> в серые по min значению из 3-х каналов
def preprocessing_stage_4_1(input_img: Image) -> Image:

    pixels = input_img.load()
    width, height = input_img.size
    for x in range(width):
        for y in range(height):
            # текущие значения R,G,B пикселя
            r, g, b = pixels[x, y][:3]
            # диапазон различий между каналами
            min_val = min(r, g, b)
            max_val = max(r, g, b)
            diff = max_val - min_val
            # пиксель в черно-белый
            if 1 <= diff <= 11:
                gray_value = min_val
                pixels[x, y] = (gray_value, gray_value, gray_value)

    return input_img


# 4.1 Искусственные трёхканальные цветные -> в серые по min значению из 3-х каналов
def preprocessing_stage_4_1_to_folder(input_folder, output_folder):
    # input_folder = 'png_600' 
    # output_folder = 'png_600_11_min'
    os.makedirs(output_folder, exist_ok=True)

    for filename in os.listdir(input_folder):
        if filename.endswith('.png'):
            pdf_path = os.path.join(input_folder, filename)
            input_img = Image.open(pdf_path)
            pixels = input_img.load()
            width, height = input_img.size
            for x in range(width):
                for y in range(height):
                    # текущие значения R,G,B пикселя
                    r, g, b = pixels[x, y][:3]
                    # диапазон различий между каналами
                    min_val = min(r, g, b)
                    max_val = max(r, g, b)
                    diff = max_val - min_val
                    # пиксель в черно-белый
                    if 1 <= diff <= 11:
                        gray_value = min_val
                        pixels[x, y] = (gray_value, gray_value, gray_value)
            output_img_path = os.path.join(output_folder, f'{os.path.splitext(filename)[0]}.png')
            input_img.save(output_img_path)


# 4.2 Трёхканальные цветные -> в серые по everage значению из 3-х каналов
def preprocessing_stage_4_2(input_img: Image) -> Image:

    pixels = input_img.load()
    width, height = input_img.size
    for x in range(width):
        for y in range(height):
            # текущие значения R,G,B пикселя
            r, g, b = pixels[x, y][:3]
            # диапазон различий между каналами
            min_val = min(r, g, b)
            max_val = max(r, g, b)
            diff = max_val - min_val
            # пиксель в черно-белый
            if 12 <= diff <= 32:
                gray_value = int((min_val + max_val)/2)
                pixels[x, y] = (gray_value, gray_value, gray_value)
    
    return input_img


# 4.2 Трёхканальные цветные -> в серые по everage значению из 3-х каналов
def preprocessing_stage_4_2_to_folder(input_folder, output_folder):
    # input_folder = 'png_600_11_min' 
    # output_folder = 'png_600_11_32_eve'
    os.makedirs(output_folder, exist_ok=True)  

    for filename in os.listdir(input_folder):
        if filename.endswith('.png'):
            pdf_path = os.path.join(input_folder, filename)
            input_img = Image.open(pdf_path)
            pixels = input_img.load()
            width, height = input_img.size
            for x in range(width):
                for y in range(height):
                    # текущие значения R,G,B пикселя
                    r, g, b = pixels[x, y][:3]
                    # диапазон различий между каналами
                    min_val = min(r, g, b)
                    max_val = max(r, g, b)
                    diff = max_val - min_val
                    # пиксель в черно-белый
                    if 12 <= diff <= 32:
                        gray_value = int((min_val + max_val)/2)
                        pixels[x, y] = (gray_value, gray_value, gray_value)
            output_img_path = os.path.join(output_folder, f'{os.path.splitext(filename)[0]}.png')
            input_img.save(output_img_path)


# 4.3 Трёхканальные цветные -> в серые по max значению из 3-х каналов
def preprocessing_stage_4_3(input_img: Image) -> Image:
    
    pixels = input_img.load()
    # размеры изображения
    width, height = input_img.size
    # Обход по каждому пикселю
    for x in range(width):
        for y in range(height):
            # текущие значения R,G,B пикселя
            r, g, b = pixels[x, y][:3]
            # диапазон различий между каналами
            min_val = min(r, g, b)
            max_val = max(r, g, b)
            diff = max_val - min_val
            # пиксель в черно-белый
            if 33 <= diff <= 255:
                gray_value = max_val
                pixels[x, y] = (gray_value, gray_value, gray_value)
    
    return input_img


# 4.3 Трёхканальные цветные -> в серые по max значению из 3-х каналов
def preprocessing_stage_4_3_to_folder(input_folder, output_folder):
    # input_folder = 'png_600_11_32_eve' 
    # output_folder = 'png_600_11_32_255_max'
    os.makedirs(output_folder, exist_ok=True)  

    for filename in os.listdir(input_folder):
        if filename.endswith('.png'):
            pdf_path = os.path.join(input_folder, filename)
            input_img = Image.open(pdf_path)
            pixels = input_img.load()
            # размеры изображения
            width, height = input_img.size
            # Обход по каждому пикселю
            for x in range(width):
                for y in range(height):
                    # текущие значения R,G,B пикселя
                    r, g, b = pixels[x, y][:3]
                    # диапазон различий между каналами
                    min_val = min(r, g, b)
                    max_val = max(r, g, b)
                    diff = max_val - min_val
                    # пиксель в черно-белый
                    if 33 <= diff <= 255:
                        gray_value = max_val
                        pixels[x, y] = (gray_value, gray_value, gray_value)
            output_img_path = os.path.join(output_folder, f'{os.path.splitext(filename)[0]}_.png')
            input_img.save(output_img_path)


# 5.2 Свыше 128 - фон
def preprocessing_stage_5_2_binarization(input_img: Image) -> Image:
    
    img_array = np.array(input_img)

    #img_array[img_array <= 128]  = 0
    #img_array[img_array > 128] = 255

    img_array[img_array < 96] = 0
    img_array[(96 <= img_array) & (img_array<= 128)] = 128
    img_array[img_array > 128] = 255

    img_array = img_array.astype(np.uint8)
    processed_image = Image.fromarray(img_array)

    img_fi = processed_image.filter(ImageFilter.MedianFilter(size=3)) # ФИЛЬТР ШУМА №1
    img_fil = img_fi.filter(ImageFilter.MedianFilter(size=3)) # ФИЛЬТР ШУМА №2
    img_filt = img_fil.filter(ImageFilter.MedianFilter(size=3)) # ФИЛЬТР ШУМА №3
    img_filte = img_filt.filter(ImageFilter.MedianFilter(size=3)) # ФИЛЬТР ШУМА №1
    img_filter = img_filte.filter(ImageFilter.MedianFilter(size=3)) # ФИЛЬТР ШУМА №2
    #img_filtere = img_filter.filter(ImageFilter.MedianFilter(size=3)) # ФИЛЬТР ШУМА №3
    #img_filtered = img_filtere.filter(ImageFilter.MedianFilter(size=3)) # ФИЛЬТР ШУМА №3

    return Image.fromarray(img_array.astype(np.uint8))


# 5.2 Свыше 128 - фон
def preprocessing_stage_5_2_binarization_to_folder(input_folder, output_folder):

    '''
    input_folder = 'png_600_11_32_255_max' 
    output_folder = 'png_600_128_background'
    os.makedirs(output_folder, exist_ok=True)  # Создание папки, если её нет

    for filename in os.listdir(input_folder):
        if filename.endswith('.png'):
            img_path = os.path.join(input_folder, filename)
            img = Image.open(img_path)
            img_array = np.array(img)
            img_array[img_array > 128] = 255
            img_array = img_array.astype(np.uint8)
            processed_image = Image.fromarray(img_array)
            output_path = os.path.join(output_folder, filename)
            processed_image.save(output_path)
    print("завершено")

    input_folder = 'png_600_128_background' 
    output_folder = 'png_600_128_255_bi3ch'
    '''
    os.makedirs(output_folder, exist_ok=True)  # Создание папки, если её нет

    for filename in os.listdir(input_folder):
        if filename.endswith('.png'):
            img_path = os.path.join(input_folder, filename)
            img = Image.open(img_path)
            img_array = np.array(img)

            #img_array[img_array <= 128]  = 0
            #img_array[img_array > 128] = 255

            img_array[img_array < 96] = 0
            img_array[(96 <= img_array) & (img_array<= 128)] = 128
            img_array[img_array > 128] = 255

            img_array = img_array.astype(np.uint8)
            processed_image = Image.fromarray(img_array)

            img_fi = processed_image.filter(ImageFilter.MedianFilter(size=3)) # ФИЛЬТР ШУМА №1
            img_fil = img_fi.filter(ImageFilter.MedianFilter(size=3)) # ФИЛЬТР ШУМА №2
            img_filt = img_fil.filter(ImageFilter.MedianFilter(size=3)) # ФИЛЬТР ШУМА №3
            img_filte = img_filt.filter(ImageFilter.MedianFilter(size=3)) # ФИЛЬТР ШУМА №1
            img_filter = img_filte.filter(ImageFilter.MedianFilter(size=3)) # ФИЛЬТР ШУМА №2
            #img_filtere = img_filter.filter(ImageFilter.MedianFilter(size=3)) # ФИЛЬТР ШУМА №3
            #img_filtered = img_filtere.filter(ImageFilter.MedianFilter(size=3)) # ФИЛЬТР ШУМА №3

            
            output_path = os.path.join(output_folder, filename)
            img_filter.save(output_path)

    print("завершено")


def preprocessing_image(input_img_path, output_img_path):
    
    img = Image.open(input_img_path)

    # Поворот
    print("rotate_image")
    img = rotate_image(img)

    print("preprocessing_stage_4_1")
    img = preprocessing_stage_4_1(img)

    print("preprocessing_stage_4_2")
    img = preprocessing_stage_4_2(img)

    print("preprocessing_stage_4_3")
    img = preprocessing_stage_4_3(img)
    
    print("preprocessing_stage_5_2")
    img = preprocessing_stage_5_2_binarization(img)

    # To 300 DPI
    img = convert_dpi(img, from_dpi=600, to_dpi=300)

    img.save(output_img_path, dpi=(300, 300))


def preprocessing_file(input_file_path: Path, output_file_path: Path) -> bool:
    print('preprocessing_file - start')
    
    try:
        output_folder_path = output_file_path.parent
        print(f'output_folder_path - {output_folder_path}')
        os.makedirs(output_folder_path, exist_ok=True)

        if input_file_path.suffix == '.pdf':
            convert_pdf_to_images(input_file_path, output_folder_path, dpi = 600)
            for filename in os.listdir(output_folder_path):
                img_full_path = os.path.join(output_folder_path, filename)
                preprocessing_image(img_full_path, img_full_path)
        else:
            print(f'input_file_path.name = {input_file_path.name}')
            #output_img_full_path = os.path.join(output_folder_path, f'{os.path.splitext(input_file_path)[0]}.png')
            output_img_full_path = os.path.join(output_folder_path, f'{input_file_path.name}.png')
            preprocessing_image(input_file_path, output_img_full_path)

        res = True
    except:
        res = False

    print('preprocessing_file - stop')
    return res

def preprocessing():
    print('preprocessing - start')
    
    input_folder = Path(FILES_PATH) / 'input'
    output_folder = Path(FILES_PATH) / 'output'
    os.makedirs(output_folder, exist_ok=True)  #
    for filename in os.listdir(input_folder):
        if filename.endswith('.pdf'):
            pdf_path = input_folder / filename
            convert_pdf_to_images(pdf_path, output_folder, dpi = 600)
    
    for filename in os.listdir(output_folder):
        
        img_full_path = os.path.join(output_folder, filename)
        print(f'img_full_path - {img_full_path}')
    
        if os.path.isdir(img_full_path):
            # Ничего не делаем
            continue
        
        img = Image.open(img_full_path)

        # Поворот
        print("rotate_image")
        img = rotate_image(img)

        print("preprocessing_stage_4_1")
        img = preprocessing_stage_4_1(img)

        print("preprocessing_stage_4_2")
        img = preprocessing_stage_4_2(img)

        print("preprocessing_stage_4_3")
        img = preprocessing_stage_4_3(img)
        
        print("preprocessing_stage_5_2")
        img = preprocessing_stage_5_2_binarization(img)

        # To 300 DPI
        img = convert_dpi(img, from_dpi=600, to_dpi=300)

        output_img_path = os.path.join(output_folder, f'{os.path.splitext(filename)[0]}.png')
        img.save(output_img_path, dpi=(300, 300))

    print('preprocessing - stop')    


if __name__ == "__main__":
    preprocessing()