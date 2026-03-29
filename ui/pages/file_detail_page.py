"""Document detail page."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import streamlit as st

from shared.utils.logger import setup_logger
from ui.utils.constants import MODULE_LABELS, MODULES_ORDER
from ui.utils.formatters import (
    format_datetime_full,
    format_file_size_human,
    render_status_badge_safe,
)

logger = setup_logger("ui.pages.file_detail_page")

FIELD_LABELS = {
    "document_type": "Тип документа",
    "document_series": "Серия",
    "document_number": "Номер документа",
    "date": "Дата",
    "document_date": "Дата документа",
    "invoice_number": "Номер счета",
    "invoice_date": "Дата счета",
    "payment_deadline": "Срок оплаты",
    "payment_order_number": "Номер платежного поручения",
    "payment_order_type": "Тип платежного поручения",
    "basis": "Основание",
    "note": "Примечание",
    "name": "Наименование",
    "address": "Адрес",
    "tax_id": "УНП / ИНН",
    "quantity_total": "Итого количество",
    "cost_total": "Сумма без НДС",
    "vat_total": "Сумма НДС",
    "cost_with_vat_total": "Сумма с НДС",
    "vat_total_words": "НДС прописью",
    "cost_with_vat_total_words": "Сумма прописью",
    "urgent": "Срочный платеж",
    "non_urgent": "Несрочный платеж",
}


def render_file_detail_page(session_state) -> None:
    file_index = session_state.editing_file_index
    redis_client = session_state.redis_client

    if file_index is None or not redis_client:
        st.error("Документ не выбран.")
        _render_back_button(session_state)
        return

    files = redis_client.get_all_files()
    if file_index >= len(files):
        st.error("Документ не найден.")
        _render_back_button(session_state)
        return

    file_data = files[file_index]
    base_path = _resolve_base_path(session_state, file_data)
    payload, payload_path = _load_primary_payload(base_path)
    payload_kind, editable_payload, wrap_keys = _unwrap_payload(payload)
    scalar_fields = _collect_scalar_fields(editable_payload)
    items = _extract_items(editable_payload)
    preview_path = _find_preview_image(base_path)

    _render_back_button(session_state)
    _render_document_header(file_data, payload_kind)
    _render_pipeline_progress(file_data)

    tabs = st.tabs(["Обзор", "Поля", "Товары", "Файлы", "Raw JSON", "История"])

    with tabs[0]:
        _render_overview_tab(file_data, editable_payload, preview_path, payload_kind)
    with tabs[1]:
        _render_fields_tab(file_data, payload, editable_payload, wrap_keys, scalar_fields, payload_path)
    with tabs[2]:
        _render_items_tab(payload, editable_payload, wrap_keys, items, payload_path)
    with tabs[3]:
        _render_files_tab(file_data, base_path, payload_path)
    with tabs[4]:
        if payload is not None:
            st.json(payload)
        else:
            st.info("Итоговый JSON пока не найден.")
    with tabs[5]:
        _render_history_tab(file_data)


def _render_back_button(session_state) -> None:
    if st.button("Назад к документам"):
        session_state.current_page = "main"
        session_state.editing_file_index = None
        st.rerun()


def _render_document_header(file_data: Dict[str, Any], payload_kind: str) -> None:
    title = file_data.get("original_filename", "Документ")
    left, right = st.columns([3, 1.2], gap="large")
    with left:
        st.markdown(f"## {title}")
        st.caption(payload_kind)
    with right:
        render_status_badge_safe(file_data.get("status", "uploaded"), st)

    meta_cols = st.columns(4, gap="small")
    meta_cols[0].metric("Файл", title)
    meta_cols[1].metric("Размер", format_file_size_human(file_data.get("file_size", 0)))
    meta_cols[2].metric("Создан", format_datetime_full(file_data.get("created_at")))
    meta_cols[3].metric("Обновлен", format_datetime_full(file_data.get("updated_at")))


def _render_pipeline_progress(file_data: Dict[str, Any]) -> None:
    completed = set(file_data.get("completed_modules", []))
    current = file_data.get("current_module")

    st.markdown("### Этапы обработки")
    cols = st.columns(len(MODULES_ORDER), gap="small")
    for col, module in zip(cols, MODULES_ORDER):
        if module in completed:
            state = "Готово"
            color = "#2F6B55"
        elif current == module:
            state = "Сейчас"
            color = "#C46A3A"
        else:
            state = "Ожидает"
            color = "#7C766D"
        with col:
            st.markdown(
                f"""
                <div style="border:1px solid #D9D2C3;border-radius:14px;padding:10px 12px;background:#FFFDF8;">
                    <div style="font-size:12px;color:#6E675E;">{MODULE_LABELS.get(module, module)}</div>
                    <div style="font-size:14px;font-weight:600;color:{color};margin-top:4px;">{state}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _render_overview_tab(
    file_data: Dict[str, Any],
    payload: Dict[str, Any],
    preview_path: Path | None,
    payload_kind: str,
) -> None:
    left, right = st.columns([1.4, 1.8], gap="large")
    with left:
        st.markdown("#### Карточка документа")
        for label, value in _overview_pairs(payload, payload_kind):
            st.markdown(f"**{label}:** {value}")
    with right:
        st.markdown("#### Превью")
        if preview_path and preview_path.exists():
            st.image(str(preview_path), use_container_width=True)
        else:
            st.info("Превью пока недоступно.")


def _render_fields_tab(
    file_data: Dict[str, Any],
    full_payload: Dict[str, Any] | None,
    editable_payload: Dict[str, Any],
    wrap_keys: List[str],
    scalar_fields: List[Tuple[Tuple[str, ...], Any]],
    payload_path: Path | None,
) -> None:
    if full_payload is None or payload_path is None:
        st.info("Финальный JSON для редактирования пока не найден.")
        return

    st.markdown("#### Поля документа")
    if not scalar_fields:
        st.caption("Простые поля для редактирования не найдены.")
        return

    values: Dict[Tuple[str, ...], Any] = {}
    with st.form(f"fields_form_{file_data.get('file_id')}"):
        current_group = None
        for path, value in scalar_fields:
            group = path[0] if len(path) > 1 else "common"
            if group != current_group:
                current_group = group
                title = _group_label(group)
                st.markdown(f"##### {title}")

            label = _field_label(path)
            widget_key = "field_" + "__".join(path)
            values[path] = _render_field_widget(widget_key, label, value)

        submitted = st.form_submit_button("Сохранить поля", use_container_width=True, type="primary")

    if submitted:
        updated_full_payload = copy.deepcopy(full_payload)
        target = _get_wrapped_target(updated_full_payload, wrap_keys)
        for path, new_value in values.items():
            _set_nested_value(target, path, new_value)
        payload_path.write_text(json.dumps(updated_full_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        st.success("Изменения сохранены в итоговый JSON.")


def _render_items_tab(
    full_payload: Dict[str, Any] | None,
    editable_payload: Dict[str, Any],
    wrap_keys: List[str],
    items: Tuple[str | None, List[Dict[str, Any]]],
    payload_path: Path | None,
) -> None:
    items_key, rows = items
    if full_payload is None or payload_path is None or not rows or not items_key:
        st.info("Табличная часть не найдена.")
        return

    st.markdown("#### Табличная часть")
    edited_rows = st.data_editor(rows, use_container_width=True, num_rows="dynamic")
    if st.button("Сохранить табличную часть", type="primary", key="save_items"):
        updated_full_payload = copy.deepcopy(full_payload)
        target = _get_wrapped_target(updated_full_payload, wrap_keys)
        if hasattr(edited_rows, "to_dict"):
            target[items_key] = edited_rows.to_dict("records")
        else:
            target[items_key] = list(edited_rows)
        payload_path.write_text(json.dumps(updated_full_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        st.success("Табличная часть сохранена.")


def _render_files_tab(file_data: Dict[str, Any], base_path: Path, payload_path: Path | None) -> None:
    st.markdown("#### Связанные файлы")
    files_to_show = []
    original_path = base_path / "original" / file_data.get("original_filename", "")
    if original_path.exists():
        files_to_show.append(("Исходный файл", original_path))
    if payload_path and payload_path.exists():
        files_to_show.append(("Финальный JSON", payload_path))

    cleaner_files = sorted((base_path / "cleaner").glob("*")) if (base_path / "cleaner").exists() else []
    if cleaner_files:
        files_to_show.append(("Очищенная страница", cleaner_files[0]))

    for label, path in files_to_show:
        with st.container(border=True):
            st.markdown(f"**{label}**")
            st.code(str(path))
            if path.is_file():
                mime = "application/json" if path.suffix.lower() == ".json" else None
                st.download_button(
                    f"Скачать: {label}",
                    data=path.read_bytes(),
                    file_name=path.name,
                    mime=mime,
                    key=f"download_{label}_{path.name}",
                )

    with st.expander("Технические папки", expanded=False):
        for child in sorted(base_path.iterdir()):
            st.markdown(f"- `{child.name}`")


def _render_history_tab(file_data: Dict[str, Any]) -> None:
    st.markdown("#### История обработки")
    history = list(reversed(file_data.get("history", [])))
    if not history:
        st.caption("История пока пуста.")
    for record in history:
        ok = "OK" if record.get("success") else "ERR"
        action = record.get("action", "-")
        module = record.get("module", "-")
        timestamp = format_datetime_full(record.get("timestamp"))
        st.markdown(f"**{timestamp}** | `{module}` | {ok} | {action}")
        if record.get("error"):
            st.caption(record["error"])

    if file_data.get("errors"):
        st.markdown("#### Ошибки")
        for error in file_data["errors"]:
            st.error(error)


def _resolve_base_path(session_state, file_data: Dict[str, Any]) -> Path:
    base = Path(session_state.settings.shared_files_path)
    storage_dir = file_data.get("storage_dir")
    if storage_dir:
        preferred = base / storage_dir
        if preferred.exists():
            return preferred
    by_name = base / Path(file_data.get("original_filename", "document")).stem
    if by_name.exists():
        return by_name
    return base / file_data.get("file_id", "")


def _load_primary_payload(base_path: Path) -> Tuple[Dict[str, Any] | None, Path | None]:
    final_dir = base_path / "data" / "final_json"
    if final_dir.exists():
        candidates = sorted(final_dir.glob("*.json"))
        if candidates:
            path = candidates[0]
            try:
                return json.loads(path.read_text(encoding="utf-8")), path
            except Exception as exc:
                logger.warning("Failed to read final json %s: %s", path, exc)
    return None, None


def _unwrap_payload(payload: Dict[str, Any] | None) -> Tuple[str, Dict[str, Any], List[str]]:
    if not isinstance(payload, dict):
        return "Документ", {}, []

    if "document_type" in payload:
        return str(payload.get("document_type") or "Документ"), payload, []

    if len(payload) == 1:
        root_key, root_value = next(iter(payload.items()))
        if isinstance(root_value, dict) and len(root_value) == 1:
            doc_id, inner = next(iter(root_value.items()))
            if isinstance(inner, dict):
                return root_key.replace("_", " ").title(), inner, [root_key, doc_id]
        if isinstance(root_value, dict):
            return root_key.replace("_", " ").title(), root_value, [root_key]

    return "Документ", payload, []


def _collect_scalar_fields(data: Dict[str, Any], prefix: Tuple[str, ...] = ()) -> List[Tuple[Tuple[str, ...], Any]]:
    fields: List[Tuple[Tuple[str, ...], Any]] = []
    for key, value in data.items():
        path = prefix + (key,)
        if isinstance(value, dict):
            fields.extend(_collect_scalar_fields(value, path))
        elif isinstance(value, list):
            continue
        else:
            fields.append((path, value))
    return fields


def _extract_items(data: Dict[str, Any]) -> Tuple[str | None, List[Dict[str, Any]]]:
    for key, value in data.items():
        if isinstance(value, list) and value and isinstance(value[0], dict):
            return key, value
    return None, []


def _field_label(path: Tuple[str, ...]) -> str:
    if len(path) == 1:
        return FIELD_LABELS.get(path[0], path[0].replace("_", " ").capitalize())
    return FIELD_LABELS.get(path[-1], path[-1].replace("_", " ").capitalize())


def _group_label(group: str) -> str:
    labels = {
        "common": "Основные данные",
        "sender": "Отправитель",
        "receiver": "Получатель",
        "payer": "Плательщик",
        "supplier": "Поставщик",
        "customer": "Покупатель",
        "payee": "Получатель платежа",
        "payment_details": "Детали платежа",
        "execution_details": "Исполнение",
        "signatory": "Подписи",
        "totals": "Итоги",
        "approvals": "Подтверждение",
        "footer": "Подвал",
    }
    return labels.get(group, group.replace("_", " ").capitalize())


def _render_field_widget(widget_key: str, label: str, value: Any) -> Any:
    if isinstance(value, bool):
        return st.checkbox(label, value=value, key=widget_key)
    if isinstance(value, int) and not isinstance(value, bool):
        return st.number_input(label, value=value, step=1, key=widget_key)
    if isinstance(value, float):
        return st.number_input(label, value=float(value), key=widget_key)
    return st.text_input(label, value="" if value is None else str(value), key=widget_key)


def _set_nested_value(target: Dict[str, Any], path: Tuple[str, ...], value: Any) -> None:
    node = target
    for part in path[:-1]:
        node = node.setdefault(part, {})
    leaf = path[-1]
    current = node.get(leaf)
    if current is None:
        node[leaf] = value
    elif isinstance(current, bool):
        node[leaf] = bool(value)
    elif isinstance(current, int) and not isinstance(current, bool):
        node[leaf] = int(value)
    elif isinstance(current, float):
        node[leaf] = float(value)
    else:
        node[leaf] = value


def _get_wrapped_target(payload: Dict[str, Any], wrap_keys: Iterable[str]) -> Dict[str, Any]:
    node = payload
    for key in wrap_keys:
        node = node[key]
    return node


def _overview_pairs(payload: Dict[str, Any], payload_kind: str) -> List[Tuple[str, Any]]:
    pairs: List[Tuple[str, Any]] = [("Тип", payload_kind)]
    candidates = [
        ("Номер", payload.get("document_number") or payload.get("invoice_number") or payload.get("payment_order_number")),
        ("Дата", payload.get("date") or payload.get("invoice_date") or payload.get("document_date")),
        ("Основание", payload.get("basis")),
    ]
    for section in ("sender", "receiver", "supplier", "customer", "payer", "payee"):
        value = payload.get(section)
        if isinstance(value, dict):
            pairs.append((_group_label(section), value.get("name") or "-"))
    totals = payload.get("totals")
    if isinstance(totals, dict):
        candidates.append(("Сумма", totals.get("cost_with_vat_total") or totals.get("cost_total")))
    for label, value in candidates:
        if value not in (None, "", []):
            pairs.append((label, value))
    return pairs


def _find_preview_image(base_path: Path) -> Path | None:
    for relative in (
        Path("cleaner"),
        Path("final_rebuilt_auto"),
        Path("original"),
    ):
        target = base_path / relative
        if not target.exists():
            continue
        for suffix in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
            match = next(target.rglob(suffix), None)
            if match:
                return match
    return None
