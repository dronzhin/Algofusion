"""
Инициализация модуля llm.
Фабричные функции для создания компонентов.
"""

from workers.LLM.src.config import LLMProcessingConfig
from workers.LLM.src.llm.base import ClassifierEngine, ExtractorEngine, ConverterEngine
from workers.LLM.src.llm.classifier import OllamaClassifier
from workers.LLM.src.llm.extractor import OllamaExtractor


def create_classifier(config: LLMProcessingConfig) -> ClassifierEngine:
    """Фабрика классификаторов."""
    return OllamaClassifier({
        "ollama_endpoint": config.ollama_endpoint,
        "ollama_model": config.ollama_model,
        "ollama_timeout": config.ollama_timeout,
        "json_mode": config.json_mode,
        "allowed_doc_types": list(config.allowed_doc_types),
    })


def create_extractor(config: LLMProcessingConfig) -> ExtractorEngine:
    """Фабрика экстракторов."""
    return OllamaExtractor({
        "ollama_endpoint": config.ollama_endpoint,
        "ollama_model": config.ollama_model,
        "ollama_timeout": config.ollama_timeout,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "json_mode": config.json_mode,
    })


__all__ = [
    "create_classifier",
    "create_extractor",
    "ClassifierEngine",
    "ExtractorEngine",
    "ConverterEngine",
]
