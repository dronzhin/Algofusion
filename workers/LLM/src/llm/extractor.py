#!/usr/bin/env python3
# workers/LLM/src/llm/extractor.py
"""
Экстрактор структурированных данных на базе Ollama с strict JSON Schema mode.
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
    """Экстрактор данных на базе Ollama API с strict JSON Schema."""

    name = "ollama_extractor"

    def __init__(self, config: dict):
        super().__init__(config)
        self.endpoint = config.get("ollama_endpoint", "http://ollama:11434")
        self.model = config.get("ollama_model", "qwen2.5:7b")
        self.timeout = config.get("ollama_timeout", 120)
        self.temperature = config.get("temperature", 0.1)
        self.max_tokens = config.get("max_tokens", 4096)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.RequestError, json.JSONDecodeError)),
        reraise=True
    )
    def _call_ollama(self, prompt: str, schema: Optional[Dict[str, Any]] = None) -> str:
        """Вызов Ollama API с strict JSON Schema mode."""
        url = f"{self.endpoint}/api/generate"

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
            }
        }

        # 🔹 КЛЮЧЕВОЕ: передаём JSON Schema напрямую в Ollama
        if schema and schema.get("properties"):
            payload["format"] = schema
        else:
            payload["format"] = "json"

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            result = response.json()
            raw_response = result.get("response", "")
            return self._extract_json_from_response(raw_response)

    def _extract_json_from_response(self, text: str) -> str:
        """Извлекает валидный JSON из ответа."""
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*$', '', text)
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

    def extract(
            self,
            text: str,
            schema: Optional[Dict[str, Any]],
            doc_type: str,
            prompt_hints: str = ""
    ) -> Optional[Dict[str, Any]]:
        """Извлечение структурированных данных с strict JSON Schema."""
        prompt = load_extractor_prompt(
            text=text,
            schema=schema or {},
            doc_type=doc_type,
            prompt_hints=prompt_hints
        )

        try:
            response = self._call_ollama(prompt, schema=schema)
            extracted = json.loads(response)

            if extracted and isinstance(extracted, dict):
                if schema and "required" in schema:
                    missing = [f for f in schema["required"] if f not in extracted and not f.startswith("_")]
                    if missing:
                        logger.warning(f"⚠️ Отсутствуют обязательные поля для {doc_type}: {missing}")

                extracted["_meta"] = {
                    "document_type": doc_type,
                    "model": self.model,
                    "schema_used": bool(schema),
                }

            return extracted if isinstance(extracted, dict) else None

        except json.JSONDecodeError as e:
            logger.error(f"❌ Ошибка парсинга JSON: {e}, raw: {response[:100]}")
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка экстракции: {e}")
            return None