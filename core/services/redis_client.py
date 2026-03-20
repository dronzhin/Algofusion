"""
Redis клиент для очередей и Pub/Sub.
Используется всеми контейнерами для коммуникации.
"""

import redis
import json
import os
from typing import Optional, Dict, Any, List
from datetime import datetime
from shared.utils.logger import setup_logger

logger = setup_logger("core.services.redis_client")


class RedisClient:
    """Обёртка над Redis для очередей и Pub/Sub."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        db: int = 0
    ):
        self.host = host or os.getenv("REDIS_HOST", "redis")
        self.port = int(port or os.getenv("REDIS_PORT", 6379))
        self.db = db
        self._client: Optional[redis.Redis] = None
        self._pubsub: Optional[redis.client.PubSub] = None
        logger.info(f"RedisClient инициализирован: {self.host}:{self.port}")

    @property
    def client(self) -> redis.Redis:
        """Ленивая инициализация клиента."""
        if self._client is None:
            try:
                self._client = redis.Redis(
                    host=self.host,
                    port=self.port,
                    db=self.db,
                    decode_responses=True,
                    socket_connect_timeout=5
                )
                # Проверка подключения
                self._client.ping()
                logger.info("Подключение к Redis успешно")
            except redis.ConnectionError as e:
                logger.error(f"Ошибка подключения к Redis: {e}")
                raise
        return self._client

    def publish_event(self, channel: str, event: Dict[str, Any]) -> int:
        """Публикация события в канал."""
        try:
            event["timestamp"] = datetime.utcnow().isoformat()
            payload = json.dumps(event, ensure_ascii=False)
            result = self.client.publish(channel, payload)
            logger.debug(f"Опубликовано событие в {channel}: {event.get('type')}")
            return result
        except Exception as e:
            logger.error(f"Ошибка публикации события: {e}")
            return 0

    def push_to_queue(self, queue: str, job_payload: str, priority: int = 0) -> int:
        """Добавление задания в очередь (с приоритетом)."""
        try:
            if priority > 0:
                queue = f"priority:{priority}:{queue}"
            result = self.client.lpush(queue, job_payload)
            logger.debug(f"Добавлено в очередь {queue}")
            return result
        except Exception as e:
            logger.error(f"Ошибка добавления в очередь {queue}: {e}")
            return 0

    def pop_from_queue(self, queue: str, timeout: int = 0) -> Optional[str]:
        """Получение задания из очереди (блокирующее)."""
        try:
            result = self.client.brpop(queue, timeout=timeout)
            if result:
                return result[1]
            return None
        except Exception as e:
            logger.error(f"Ошибка получения из очереди {queue}: {e}")
            return None

    def subscribe(self, channels: List[str]) -> redis.client.PubSub:
        """Подписка на каналы."""
        try:
            if self._pubsub is None:
                self._pubsub = self.client.pubsub()
            self._pubsub.subscribe(*channels)
            logger.info(f"Подписка на каналы: {channels}")
            return self._pubsub
        except Exception as e:
            logger.error(f"Ошибка подписки: {e}")
            raise

    def get_file_status(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Получение статуса файла из Redis."""
        try:
            key = f"file:{file_id}:status"
            data = self.client.get(key)
            return json.loads(data) if data else None
        except Exception as e:
            logger.error(f"Ошибка получения статуса файла {file_id}: {e}")
            return None

    def set_file_status(self, file_id: str, status: Dict[str, Any], ttl: int = 3600) -> bool:
        """Установка статуса файла в Redis."""
        try:
            key = f"file:{file_id}:status"
            self.client.setex(key, ttl, json.dumps(status, ensure_ascii=False))
            logger.debug(f"Статус файла {file_id} обновлён")
            return True
        except Exception as e:
            logger.error(f"Ошибка установки статуса файла {file_id}: {e}")
            return False

    def get_all_files(self) -> List[Dict[str, Any]]:
        """Получение всех файлов из Redis."""
        try:
            files = []
            for key in self.client.keys("file:*:status"):
                data = self.client.get(key)
                if data:
                    files.append(json.loads(data))
            return files
        except Exception as e:
            logger.error(f"Ошибка получения всех файлов: {e}")
            return []

    def delete_file_status(self, file_id: str) -> bool:
        """Удаление статуса файла."""
        try:
            key = f"file:{file_id}:status"
            self.client.delete(key)
            logger.debug(f"Статус файла {file_id} удалён")
            return True
        except Exception as e:
            logger.error(f"Ошибка удаления статуса файла {file_id}: {e}")
            return False

    def close(self):
        """Закрытие соединений."""
        if self._pubsub:
            self._pubsub.close()
        if self._client:
            self._client.close()
        logger.info("Соединения Redis закрыты")


# Глобальный экземпляр (синглтон)
_redis_client: Optional[RedisClient] = None


def get_redis_client() -> RedisClient:
    """Получение глобального экземпляра RedisClient."""
    global _redis_client
    if _redis_client is None:
        _redis_client = RedisClient()
    return _redis_client