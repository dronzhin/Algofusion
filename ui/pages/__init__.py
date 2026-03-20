# ui/pages/__init__.py
"""UI Pages."""
from ui.pages.main_page import render_main_page
from ui.pages.file_detail_page import render_file_detail_page

__all__ = ["render_main_page", "render_file_detail_page"]