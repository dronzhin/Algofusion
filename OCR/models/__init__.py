# models/__init__.py

from models.deepseek_ocr import DeepSeekOCRModel
from models.deepseek_ocr2 import DeepSeekOCR2Model
from models.paddleocr_vl import PaddleOCRVLModel
from models.glm_ocr import GLMOCRModel

__all__ = [
    "DeepSeekOCRModel",
    "DeepSeekOCR2Model",
    "PaddleOCRVLModel",
    "GLMOCRModel"
]