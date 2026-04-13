# ui/components/file_detail/__init__.py
"""
Компоненты страницы деталей файла.
"""

from .file_info import render_file_info_section
from .progress import render_progress_section
from .history import render_history_section
from .file_structure import render_file_structure_section
from .llm_editor import render_llm_editor_section
from .actions import render_actions_section

__all__ = [
    "render_file_info_section",
    "render_progress_section",
    "render_history_section",
    "render_file_structure_section",
    "render_llm_editor_section",
    "render_actions_section",
]