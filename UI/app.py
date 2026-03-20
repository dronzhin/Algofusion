# app.py
from core.state import AppState


def main():
    state = AppState.get()

    if state.current_page == "main":
        from ui.pages.main_page import render_main_page
        render_main_page(state)
    elif state.current_page == "edit":
        from ui.pages.edit_page import render_edit_page
        render_edit_page(state)


if __name__ == "__main__":
    main()