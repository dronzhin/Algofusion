# utils/errors.py
from typing import Any, Optional

class APIError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None, response_data: Any = None):
        self.message = message
        self.status_code = status_code
        self.response_data = response_data
        super().__init__(self.message)

    def __str__(self):
        if self.status_code:
            return f"APIError ({self.status_code}): {self.message}"
        return f"APIError: {self.message}"

class FileProcessingError(Exception):
    pass

class ValidationError(Exception):
    pass

class ImageProcessingError(Exception):
    pass