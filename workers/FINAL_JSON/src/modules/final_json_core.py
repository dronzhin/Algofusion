# ===== FINAL GOLD JSON BUILDER: one file or whole folder =====

import json
import copy
from pathlib import Path
from typing import Any, Mapping


# =========================
# CONFIG
# =========================
# Один файл:
INPUT_PATH = Path("data") / "pred_reconciled"

# Если захотите прогнать всю папку, замените строку выше на:
# INPUT_PATH = Path("data") / "pred_reconciled"

OUTPUT_DIR = Path("data") / "final_json"
OVERRIDE_FILE_KEY = None  # например: "Waybill_7-15.pdf"


# =========================
# BUILDER
# =========================
WRAPPED_DOC_TYPES = {"invoice", "payment_order", "Account-protocol"}
FLAT_DOC_TYPES = {"waybill"}
SUPPORTED_DOC_TYPES = WRAPPED_DOC_TYPES | FLAT_DOC_TYPES


def _strip_private_fields(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _strip_private_fields(item)
            for key, item in value.items()
            if not str(key).startswith("_")
        }
    if isinstance(value, list):
        return [_strip_private_fields(item) for item in value]
    return value


def _ensure_mapping(value: Any, message: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(message)
    return value


def build_final_json_document(
    doc_type: str,
    payload: Mapping[str, Any],
    *,
    file_key: str | None = None,
) -> dict[str, Any]:
    if doc_type not in SUPPORTED_DOC_TYPES:
        raise ValueError(
            f"Unsupported doc_type: {doc_type!r}. "
            f"Expected one of: {sorted(SUPPORTED_DOC_TYPES)!r}."
        )

    payload = _ensure_mapping(payload, "`payload` must be a mapping.")
    cleaned_payload = _strip_private_fields(copy.deepcopy(dict(payload)))

    if doc_type in WRAPPED_DOC_TYPES:
        if not file_key:
            raise ValueError(
                f"`file_key` is required for {doc_type!r} final JSON output."
            )
        return {doc_type: {file_key: cleaned_payload}}

    return cleaned_payload


def build_final_json(
    pred_reconciled: Mapping[str, Any],
    *,
    file_key: str | None = None,
) -> dict[str, Any]:
    pred_reconciled = _ensure_mapping(
        pred_reconciled,
        "`pred_reconciled` must be a mapping.",
    )
    cleaned = _strip_private_fields(copy.deepcopy(dict(pred_reconciled)))
    top_keys = list(cleaned.keys())

    if len(top_keys) == 1 and top_keys[0] in WRAPPED_DOC_TYPES:
        doc_type = top_keys[0]
        docs = _ensure_mapping(
            cleaned[doc_type],
            f"`pred_reconciled[{doc_type!r}]` must be a mapping.",
        )
        if len(docs) != 1:
            raise ValueError(
                f"Expected exactly one file payload inside {doc_type!r}, got {len(docs)}."
            )

        existing_file_key, payload = next(iter(docs.items()))
        payload = _ensure_mapping(
            payload,
            f"`pred_reconciled[{doc_type!r}][{existing_file_key!r}]` must be a mapping.",
        )
        return build_final_json_document(
            doc_type,
            payload,
            file_key=file_key or str(existing_file_key),
        )

    if "document_type" in cleaned and "items" in cleaned:
        return build_final_json_document("waybill", cleaned, file_key=file_key)

    if len(top_keys) == 1 and top_keys[0] == "waybill":
        payload = _ensure_mapping(
            cleaned["waybill"],
            "`pred_reconciled['waybill']` must be a mapping.",
        )
        return build_final_json_document("waybill", payload, file_key=file_key)

    raise ValueError(
        "Could not detect document shape. Expected wrapped "
        "invoice/payment_order/account-protocol JSON or flat waybill payload."
    )


