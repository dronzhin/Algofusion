# shared/models/file/routing.py
from pathlib import Path
from typing import Optional, Dict, List
from .enums import FileType

QUEUES = {
    "preprocess": "files:preprocess",
    "ocr": "files:ocr",
    "llm": "files:llm",
    "export": "files:export",
}

def get_queue_for_module(module: str) -> Optional[str]:
    return QUEUES.get(module)

def get_all_queues() -> Dict[str, str]:
    return QUEUES.copy()

def is_valid_queue_module(module: str) -> bool:
    return module in QUEUES

def detect_file_type(filename: str) -> FileType:
    ext = Path(filename).suffix.lower()
    mapping = {
        FileType.IMAGE: {".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".gif", ".webp"},
        FileType.PDF: {".pdf"},
        FileType.DOCUMENT: {".doc", ".docx", ".odt", ".rtf"},
        FileType.TEXT: {".txt", ".md", ".csv", ".json", ".xml"},
    }
    for ft, exts in mapping.items():
        if ext in exts:
            return ft
    return FileType.UNKNOWN

def get_allowed_modules(file_type: FileType) -> List[str]:
    routing = {
        FileType.IMAGE: ["preprocess", "ocr", "llm"],
        FileType.PDF: ["preprocess", "ocr", "llm"],
        FileType.DOCUMENT: ["preprocess", "llm"],
        FileType.TEXT: ["llm"],
        FileType.UNKNOWN: [],
    }
    return routing.get(file_type, [])

def get_base_path(file_id: str, base_dir: str = "/shared/files") -> Path:
    return Path(base_dir) / file_id

def get_original_path(file_id: str, original_filename: str, base_dir: str = "/shared/files") -> Path:
    return get_base_path(file_id, base_dir) / "original" / original_filename

def get_module_input_path(job: "FileJob", module: str, base_dir: str = "/shared/files") -> Path:
    base = get_base_path(job.file_id, base_dir)
    if module == "preprocess":
        return get_original_path(job.file_id, job.original_filename, base_dir)
    elif module == "ocr":
        preprocessed = base / "preprocessed" / job.original_filename
        return preprocessed if preprocessed.exists() else get_original_path(job.file_id, job.original_filename, base_dir)
    elif module == "llm":
        return base / "ocr" / f"{Path(job.original_filename).stem}.txt"
    elif module == "export":
        return base / "llm" / "analysis.json"
    return get_original_path(job.file_id, job.original_filename, base_dir)

def get_module_output_path(job: "FileJob", module: str, base_dir: str = "/shared/files") -> Path:
    base = get_base_path(job.file_id, base_dir) / module
    base.mkdir(parents=True, exist_ok=True)
    if module == "ocr":
        return base / f"{Path(job.original_filename).stem}.txt"
    elif module == "llm":
        return base / "analysis.json"
    elif module == "export":
        return base / f"{Path(job.original_filename).stem}_1c.xml"
    return base / job.original_filename

def get_export_path(job: "FileJob", base_dir: str = "/shared/files") -> Path:
    export_dir = get_base_path(job.file_id, base_dir) / "export"
    export_dir.mkdir(parents=True, exist_ok=True)
    return export_dir / f"{Path(job.original_filename).stem}_1c.xml"

def get_archive_path(job: "FileJob", base_dir: str = "/shared/files") -> Path:
    archive_dir = get_base_path(job.file_id, base_dir) / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    return archive_dir / f"{job.file_id}_processed.zip"