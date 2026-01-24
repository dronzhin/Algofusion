# components/error_handler.py
import streamlit as st
import traceback
from utils import APIError, FileProcessingError, ValidationError, ImageProcessingError


class StreamlitErrorHandler:
    """
    Централизованный обработчик ошибок для Streamlit-приложения.
    Работает только с UI — не содержит бизнес-логики.
    """

    @staticmethod
    def handle_api_error(error: Exception, operation_name: str = "операция") -> bool:
        """
        Обработка ошибок при вызове API
        """
        error_type = type(error).__name__
        error_message = str(error)

        st.error(f"❌ Ошибка при выполнении {operation_name}: **{error_type}**")
        st.error(f"**Детали:** {error_message}")

        if "ConnectionError" in error_type:
            st.warning("⚠️ **Не удаётся подключиться к серверу.**")
            st.markdown("Убедитесь, что FastAPI сервер запущен на http://localhost:8000")
        elif "Timeout" in error_type:
            st.warning("⏰ **Превышено время ожидания ответа от сервера.**")
            st.markdown("Попробуйте уменьшить размер файла")
        elif isinstance(error, APIError):
            if error.status_code == 404:
                st.warning("🔍 **Ресурс не найден.** Проверьте URL и параметры запроса.")
            elif error.status_code == 400:
                st.warning("❌ **Неверные параметры запроса.** Проверьте введенные данные.")
            elif error.status_code and error.status_code >= 500:
                st.warning("🔥 **Ошибка сервера.** Сервис может быть временно недоступен.")

        StreamlitErrorHandler._show_error_details(error, operation_name)
        return False

    @staticmethod
    def handle_file_error(error: Exception, file_name: str = "файл") -> bool:
        """
        Обработка ошибок при работе с файлами
        """
        error_type = type(error).__name__
        error_message = str(error)

        st.error(f"❌ Ошибка при обработке файла **'{file_name}'**: {error_type}")
        st.error(f"**Детали:** {error_message}")

        if "empty" in error_message.lower() or "corrupt" in error_message.lower():
            st.warning("⚠️ **Файл пустой или поврежден.** Пожалуйста, загрузите другой файл.")
        elif isinstance(error, MemoryError) or "memory" in error_message.lower():
            st.warning("⚠️ **Недостаточно памяти.** Попробуйте уменьшить размер файла.")
        elif isinstance(error, FileProcessingError):
            st.warning("⚠️ **Проблема с обработкой файла.** Попробуйте другой формат.")

        StreamlitErrorHandler._show_error_details(error, f"file_{file_name}")
        return False

    @staticmethod
    def handle_validation_error(error: Exception, field_name: str = "поле") -> bool:
        """
        Обработка ошибок валидации
        """
        error_message = str(error)

        st.error(f"❌ Ошибка валидации для **{field_name}**:")
        st.error(f"**Детали:** {error_message}")

        if "threshold" in field_name.lower():
            st.info("ℹ️ Порог бинаризации должен быть целым числом в диапазоне от 0 до 255")
        elif "angle" in field_name.lower():
            st.info("ℹ️ Угол поворота должен быть числом в диапазоне от -360 до 360 градусов")
        elif "file" in field_name.lower():
            st.info("ℹ️ Проверьте формат и размер файла")

        return False

    @staticmethod
    def handle_image_processing_error(error: Exception, operation_name: str = "обработка") -> bool:
        """
        Обработка ошибок при обработке изображений
        """
        error_type = type(error).__name__
        error_message = str(error)

        st.error(f"❌ Ошибка при {operation_name} изображения: **{error_type}**")
        st.error(f"**Детали:** {error_message}")

        if "PIL" in error_type or "Image" in error_type:
            st.warning("⚠️ **Проблема с обработкой изображения.** Убедитесь, что файл не поврежден.")
        elif "OpenCV" in error_type or "cv2" in error_type:
            st.warning("⚠️ **Ошибка при использовании OpenCV.** Проверьте версию библиотеки.")
        elif isinstance(error, ImageProcessingError):
            st.warning("⚠️ **Специфическая ошибка обработки изображения.** Попробуйте другой формат файла.")
        elif "memory" in error_message.lower() or isinstance(error, MemoryError):
            st.warning("⚠️ **Недостаточно памяти для обработки изображения.** Попробуйте уменьшить разрешение.")

        StreamlitErrorHandler._show_error_details(error, f"image_{operation_name}")
        return False

    @staticmethod
    def show_success_message(message: str, operation_name: str = "операция") -> bool:
        """
        Показать сообщение об успешном выполнении
        """
        st.success(f"✅ **{operation_name.capitalize()}** выполнена успешно!")
        if message:
            st.info(message)
        return True

    @staticmethod
    def show_warning_message(message: str, title: str = "Внимание") -> bool:
        """
        Показать предупреждающее сообщение
        """
        st.warning(f"⚠️ **{title}**:")
        st.warning(message)
        return False

    @staticmethod
    def _show_error_details(error: Exception, key_suffix: str):
        """
        Внутренний метод для показа подробной информации об ошибке
        """
        with st.expander("🔍 Показать подробную информацию об ошибке", expanded=False):
            st.markdown("**Трейсбек ошибки:**")
            st.code(traceback.format_exc(), language="python")

            # Дополнительная информация
            if hasattr(error, '__dict__'):
                st.markdown("**Атрибуты исключения:**")
                try:
                    st.json(str(error.__dict__))
                except:
                    st.text(str(error.__dict__))
            elif hasattr(error, 'args') and error.args:
                st.markdown("**Аргументы исключения:**")
                st.json(str(error.args))


error_handler = StreamlitErrorHandler()