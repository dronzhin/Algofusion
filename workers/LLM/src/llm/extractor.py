#!/usr/bin/env python3
# workers/LLM/src/llm/extractor.py
"""
Экстрактор структурированных данных на базе Ollama — УНИВЕРСАЛЬНЫЙ.
✅ Исправлено для Qwen 3.5: устойчивость к пустым ответам, убраны конфликтующие параметры.
"""

from typing import Optional, Dict, Any
import re
import json
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from shared.utils.logger import setup_logger
from workers.LLM.src.llm.base import ExtractorEngine
from workers.LLM.prompts import load_extractor_prompt

logger = setup_logger("workers.llm.extractor")


class OllamaExtractor(ExtractorEngine):
    """Универсальный экстрактор с валидацией против OCR-текста."""

    name = "ollama_extractor"

    def __init__(self, config: dict):
        super().__init__(config)
        self.endpoint = config.get("ollama_endpoint", "http://ollama:11434")
        self.model = config.get("ollama_model", "qwen2.5:7b")
        self.timeout = config.get("ollama_timeout", 120)

        # 🔹 Qwen 3.5: temperature 0.1 вместо 0.0 предотвращает вырождение
        self.temperature = config.get("temperature", 0.1)
        self.max_tokens = config.get("max_tokens", 4096)

        # 🔹 Qwen 3.5 плохо работает с format:schema → принудительно "json"
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

        # 🔹 Упрощаем payload: убираем system message (конфликтует с format:"json" в Qwen 3.5)
        # Инструкция уже внутри промпта из load_extractor_prompt()
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "format": "json",  # 🔹 Жёстко используем "json", схема встроена в промпт
            "options": {
                "temperature": self.temperature,  # 🔹 0.1 вместо 0.0
                "top_p": 0.95,
                "num_predict": self.max_tokens,
                "num_ctx": 8192,  # 🔹 Увеличиваем контекст для длинных документов
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
                raise ValueError("Empty response from model")  # 🔹 Триггерит retry

            return self._extract_json_from_response(content)

    def _extract_json_from_response(self, text: str) -> str:
        """Извлекает валидный JSON из ответа."""
        # 🔹 Удаляем markdown code blocks
        text = re.sub(r'```json\s*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'```\s*$', '', text)
        text = re.sub(r'^```.*?\n', '', text, flags=re.DOTALL)

        # 🔹 Ищем JSON объект
        start = text.find('{')
        end = text.rfind('}') + 1
        if start >= 0 and end > start:
            candidate = text[start:end]
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                pass

        # 🔹 Ищем массив
        start_arr = text.find('[')
        end_arr = text.rfind(']') + 1
        if start_arr >= 0 and end_arr > start_arr:
            candidate = text[start_arr:end_arr]
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                pass

        return text.strip()

    def extract(
            self,
            text: str,
            schema: Optional[Dict[str, Any]],
            doc_type: str
    ) -> Optional[Dict[str, Any]]:
        """Извлечение данных с защитой от галлюцинаций."""
        prompt = load_extractor_prompt(
            text=text,
            schema=schema or {},
            doc_type=doc_type,
            prompt_hints=""
        )

        try:
            response = self._call_ollama(prompt, schema=schema)
            extracted = json.loads(response)

            if extracted and isinstance(extracted, dict):
                # 🔹 Пост-валидация: убираем поля, которых нет в схеме
                if schema and "properties" in schema:
                    allowed_fields = set(schema["properties"].keys()) | {"_meta"}
                    for key in list(extracted.keys()):
                        if key not in allowed_fields and not key.startswith("_"):
                            logger.warning(f"⚠️ Удалено лишнее поле '{key}' (галлюцинация?)")
                            del extracted[key]

                # 🔹 Добавляем метаданные
                extracted["_meta"] = {
                    "document_type": doc_type,
                    "model": self.model,
                    "schema_used": bool(schema),
                }

            return extracted if isinstance(extracted, dict) else None

        except json.JSONDecodeError as e:
            logger.error(f"❌ Ошибка парсинга JSON: {e}, raw: {response[:200]}")
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка экстракции: {e}")
            return None