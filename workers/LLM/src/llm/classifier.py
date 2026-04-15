#!/usr/bin/env python3
# workers/LLM/src/llm/classifier.py
"""
Классификатор документов на базе Ollama.
✅ Исправлено для Qwen 3.5: устойчивость к пустым ответам, убраны конфликтующие stop-токены.
"""

from typing import Tuple, Optional, Dict, Any, List
import json
import re
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from shared.utils.logger import setup_logger
from shared.models.file.enums import DocumentType
from workers.LLM.src.llm.base import ClassifierEngine
from workers.LLM.prompts import load_classifier_prompt

logger = setup_logger("workers.llm.classifier")


class OllamaClassifier(ClassifierEngine):
    """Универсальный классификатор на базе Ollama API."""

    name = "ollama_classifier"

    CLASSIFICATION_SCHEMA = {
        "type": "object",
        "properties": {
            "type": {"type": "string", "enum": []},
            "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0}
        },
        "required": ["type", "confidence"],
        "additionalProperties": False
    }

    def __init__(self, config: dict):
        super().__init__(config)
        self.endpoint = config.get("ollama_endpoint", "http://ollama:11434")
        self.model = config.get("ollama_model", "qwen2.5:1.5b")
        self.timeout = config.get("ollama_timeout", 120)

        raw_types = config.get("allowed_doc_types", [])
        self.allowed_types: List[str] = []
        for t in raw_types:
            parsed = DocumentType.safe_parse(t)
            if parsed:
                self.allowed_types.append(parsed.value)
            elif t in [dt.value for dt in DocumentType]:
                self.allowed_types.append(t)

        if not self.allowed_types:
            self.allowed_types = [dt.value for dt in DocumentType]

        self._schema = self.CLASSIFICATION_SCHEMA.copy()
        self._schema["properties"]["type"]["enum"] = self.allowed_types

        # 🔹 Qwen 3.5 плохо работает с format:schema, используем format:"json"
        self._supports_format_schema = False

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.RequestError, json.JSONDecodeError, ValueError)),
        reraise=True
    )
    def _call_ollama(self, prompt: str, schema: Optional[Dict[str, Any]] = None) -> str:
        """Вызов Ollama API с защитой от пустых ответов Qwen 3.5."""
        url = f"{self.endpoint}/api/chat"

        # 🔹 Упрощаем payload: убираем system message (он конфликтует с format:"json" в Qwen 3.5)
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "format": "json",  # 🔹 Жёстко используем "json", схема встроена в промпт
            "options": {
                "temperature": 0.1,  # 🔹 0.1 вместо 0.0 предотвращает вырождение Qwen 3.5
                "num_predict": 256,
                "num_ctx": 4096,
                # 🔹 Убираем stop-токены: они часто срезают ответ у Qwen 3.5
            }
        }

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            result = response.json()

            # 🔹 Безопасное извлечение контента
            content = result.get("message", {}).get("content", "").strip()
            if not content:
                logger.warning(f"⚠️ Пустой ответ от Ollama. Raw: {result}")
                raise ValueError("Empty response from model")  # Триггерит retry

            return self._extract_json_from_response(content)

    def _extract_json_from_response(self, text: str) -> str:
        """Извлекает валидный JSON из ответа."""
        text = re.sub(r'```json\s*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'```\s*$', '', text)
        text = re.sub(r'^```.*?\n', '', text, flags=re.DOTALL)

        start = text.find('{')
        end = text.rfind('}') + 1
        if start >= 0 and end > start:
            candidate = text[start:end]
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                pass
        return text.strip()

    def classify(self, text: str) -> Tuple[str, float]:
        """Классификация текста документа."""
        truncated = text[:3000]
        prompt = load_classifier_prompt(text=truncated, allowed_types=self.allowed_types)

        try:
            response = self._call_ollama(prompt, schema=self._schema)
            result = json.loads(response)
            doc_type = result.get("type", "unknown")
            confidence = float(result.get("confidence", 0.0))
            confidence = min(max(confidence, 0.0), 1.0)

            if doc_type not in self.allowed_types:
                logger.warning(f"⚠️ Неизвестный тип: {doc_type}, fallback на unknown")
                return "unknown", 0.0

            logger.debug(f"✅ Классификация: {doc_type} ({confidence:.2f})")
            return doc_type, confidence

        except json.JSONDecodeError as e:
            logger.error(f"❌ Ошибка парсинга JSON: {e}, raw: {response[:200]}")
            return "unknown", 0.0
        except Exception as e:
            logger.error(f"❌ Ошибка классификации: {e}")
            return "unknown", 0.0