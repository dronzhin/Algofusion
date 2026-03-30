# workers/preprocessing_stage_1/worker.py
"""Worker для Preprocessing модуля."""

import json
import time
from datetime import datetime, timezone
# import signal
# import sys

from shared.models.file import FileJob, FileStatus
from shared.config.settings import get_settings
from shared.utils.logger import setup_logger
from shared.utils.helpers import safe_mkdir
from core.services.redis_client import get_redis_client

from utils.preprocessing import preprocessing_file

WORKER_NAME = "Preprocessing worker (stage 1)"

logger = setup_logger(f"{WORKER_NAME}")


class PreprocessingWorker:
    """Worker для обработки Preprocessing заданий."""

    def __init__(self):
        
        settings = get_settings()

        self.redis_client = get_redis_client()
        self.redis_timeout = getattr(settings, 'redis_timeout', 3) # Есть атрибут?

        self.shutdown_requested = False
        self.input_queue_name = getattr(settings, 'redis_queue_preprocess_stage_1_input', 'files:preprocess') # Есть атрибут?
        self.output_queue_name = getattr(settings, 'redis_queue_preprocess_stage_1_output', 'files:preprocess_output') # Есть атрибут?

        logger.info(
            f"{WORKER_NAME} инициализирован: "
            f"input_queue_name={self.input_queue_name}, "
            f"output_queue_name={self.output_queue_name} "
        )

    '''
    def _setup_signals(self):
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

    def _handle_signal(self, signum, frame):
        logger.info(f"Получен сигнал {signum}, остановка...")
        self.shutdown_requested = True

    def connect(self) -> bool:
        try:
            self.redis_client = redis.Redis.from_url(config.redis_url)
            self.redis_client.ping()
            logger.info(f"Подключено к Redis: {config.redis_url}")
            # logger.info(f"Доступные OCR движки: {self.module.get_available_engines()}")
            return True
        except redis.ConnectionError as e:
            logger.error(f"Ошибка подключения: {e}")
            return False
    '''

    def process_job(self, payload: str) -> bool:
        try:
            job = FileJob.from_payload(payload)

        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Неверный формат задачи: {e}")
            return False

        logger.info(f"Начало обработки файла file_id={job.file_id}; file_name={job.original_filename}")
        #print(f"job.get_base_path() = {job.get_base_path()}")
        #print(f"get_module_input_path(job.current_module) = {job.get_module_input_path(job.current_module)}")

        success = preprocessing_file(job.get_module_input_path(job.current_module), job.get_module_output_path(job.current_module))

        if success:
            logger.info(f"Файл обработан успешно")
            
            job.status = FileStatus.PROCESSING
            # Сохраняем статус в Redis
            self.redis_client.set_file_status(job.file_id, job.to_dict())

            # Отправляем в output очередь
            self.redis_client.push_to_queue(self.output_queue_name, job.to_payload(), priority=job.priority)

        else:
            # job_logger.error(f"{WORKER_NAME} для задачи отработал с ошибкой")
            logger.error(f"Ошибка обработки файла")

            job.status = FileStatus.FAILED
            # Сохраняем статус в Redis
            self.redis_client.set_file_status(job.file_id, job.to_dict())

        return success

    def run(self):
        
        logger.info(f"{WORKER_NAME} запущен")

        while True:
            try:
                # Забираем задачу из СПИСКА (блокирующее ожидание self.redis_timeout сек)
                job_payload = self.redis_client.pop_from_queue(self.input_queue_name, timeout=self.redis_timeout)
                
                # Если job_payload is None — просто таймаут, продолжаем цикл
                if job_payload:
                    logger.info(f"Получена задача: {job_payload[:100]}...")
                    
                    # функция обработки полученной задачи
                    self.process_job(job_payload)
                
            except KeyboardInterrupt:
                logger.info("Остановка по сигналу пользователя")
                break
            except Exception as e:
                logger.error(f"Критическая ошибка в цикле: {e}", exc_info=True)
                time.sleep(self.redis_timeout)  # Пауза перед перезапуском, чтобы не спамить логами
        
        # Очистка ресурсов
        self.redis_client.close()
        logger.info("Соединения закрыты")

        '''
        print(" Слушаем события...")

        if not self.connect():
            sys.exit(1)


        error_count = 0

        while not self.shutdown_requested:
            try:
                item = self.redis_client.blpop(self.queue_name, timeout=config.redis_timeout)

                if not item:
                    continue

                logger.info(f"001")

                _, payload = item
                success = self.process_job(payload)

                logger.info(f"002")

                error_count = 0 if success else error_count + 1
                if error_count >= 10:
                    logger.critical("Слишком много ошибок, остановка")
                    break

            except redis.ConnectionError as e:
                logger.error(f"Потеряно соединение: {e}")
                time.sleep(5)
                if not self.connect():
                    break
            except Exception as e:
                logger.exception(f"Ошибка: {e}")
                error_count += 1
                time.sleep(min(2 ** error_count, 60))

        '''

        logger.info(f"{WORKER_NAME} завершен")


def main():
    """Точка входа для контейнера."""
    logger.info(f"Запуск {WORKER_NAME} ...")

    try:
        worker = PreprocessingWorker()
        worker.run()
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    main()