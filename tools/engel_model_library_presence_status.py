from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


_file = globals().get("__file__")
if not _file or not isinstance(_file, str) or _file.startswith("<"):
    ROOT = Path.cwd()
else:
    try:
        ROOT = Path(_file).resolve().parents[1]
    except (OSError, ValueError, IndexError):
        ROOT = Path.cwd()

PLAN_PATH = ROOT / "memory" / "ENGEL_MODEL_LIBRARY_PLAN_V1.json"
MAX_RECORDED_FILES_PER_MODEL = 5


@dataclass(frozen=True)
class ModelPresenceStatus:
    tier: str
    role: str
    model_display_name: str
    expected_local_folder: str
    expected_file_pattern: str
    expected_files: tuple[str, ...]
    split_file_set_required: bool
    merged_file_required: bool
    retained_split_files: tuple[str, ...]
    local_file_status: str
    status: str
    merge_status: str
    detected_file_count_bounded: int
    detected_files_bounded: tuple[str, ...]
    detected_retained_split_files_bounded: tuple[str, ...]
    loaded_status: str
    runtime_status: str
    trusted_memory_write: str
    network_download: str
    inference: str


def load_model_library_plan() -> dict[str, object]:
    return json.loads(PLAN_PATH.read_text(encoding="utf-8"))


def _model_entries(plan: dict[str, object]) -> list[dict[str, object]]:
    models = plan.get("models")
    if not isinstance(models, list):
        return []
    return [model for model in models if isinstance(model, dict)]


def _expected_model_folders(plan: dict[str, object]) -> set[str]:
    folders: set[str] = set()
    layout = plan.get("folder_layout")
    if isinstance(layout, dict):
        model_folders = layout.get("model_folders")
        if isinstance(model_folders, dict):
            folders.update(str(value) for value in model_folders.values() if isinstance(value, str))
    for model in _model_entries(plan):
        folder = model.get("expected_local_folder")
        if isinstance(folder, str):
            folders.add(folder)
    return folders


def _bounded_gguf_names(folder: Path) -> tuple[str, ...]:
    if not folder.exists() or not folder.is_dir():
        return ()
    names: list[str] = []
    try:
        for child in folder.iterdir():
            if child.is_file() and child.suffix.lower() == ".gguf":
                names.append(child.name)
                if len(names) >= MAX_RECORDED_FILES_PER_MODEL:
                    break
    except OSError:
        return ()
    return tuple(sorted(names))


def _expected_file_names(model: dict[str, object]) -> tuple[str, ...]:
    return _safe_gguf_names(model.get("expected_files"))


def _retained_split_file_names(model: dict[str, object]) -> tuple[str, ...]:
    return _safe_gguf_names(model.get("retained_split_files"))


def _safe_gguf_names(files: object) -> tuple[str, ...]:
    if not isinstance(files, list):
        return ()
    names: list[str] = []
    for item in files:
        if not isinstance(item, str):
            continue
        name = Path(item).name
        if name == item and name.lower().endswith(".gguf"):
            names.append(name)
    return tuple(names[:MAX_RECORDED_FILES_PER_MODEL])


def _existing_expected_files(folder: Path, expected_files: tuple[str, ...]) -> tuple[str, ...]:
    names: list[str] = []
    for name in expected_files[:MAX_RECORDED_FILES_PER_MODEL]:
        try:
            candidate = folder / name
            if candidate.exists() and candidate.is_file():
                names.append(name)
        except OSError:
            continue
    return tuple(names)


def collect_model_presence_statuses(plan: dict[str, object] | None = None) -> list[ModelPresenceStatus]:
    plan_data = plan if plan is not None else load_model_library_plan()
    allowed_folders = _expected_model_folders(plan_data)
    statuses: list[ModelPresenceStatus] = []
    for model in _model_entries(plan_data):
        tier = str(model.get("tier", "UNKNOWN_TIER"))
        role = str(model.get("role", "unknown_role"))
        display_name = str(model.get("model_display_name", "UNKNOWN_MODEL"))
        folder_text = str(model.get("expected_local_folder", ""))
        pattern = str(model.get("expected_file_pattern", "*.gguf"))
        expected_files = _expected_file_names(model)
        split_required = bool(model.get("split_file_set_required") is True)
        merged_required = bool(model.get("merged_file_required") is True)
        retained_split_files = _retained_split_file_names(model)
        detected_files: tuple[str, ...] = ()
        detected_retained_split_files: tuple[str, ...] = ()
        local_file_status = "unknown"
        if folder_text in allowed_folders and pattern == "*.gguf":
            folder = Path(folder_text)
            if expected_files:
                detected_files = _existing_expected_files(folder, expected_files)
            else:
                detected_files = _bounded_gguf_names(folder)
            if retained_split_files:
                detected_retained_split_files = _existing_expected_files(folder, retained_split_files)
            if split_required:
                if expected_files and len(detected_files) == len(expected_files):
                    local_file_status = "split_present"
                elif detected_files:
                    local_file_status = "split_partial"
                else:
                    local_file_status = "missing"
            else:
                local_file_status = "present" if detected_files else "missing"
        if merged_required:
            if local_file_status == "present":
                merge_status = "MERGED"
                status_text = "PRESENT / MERGED / NOT_LOADED / NOT_RUNTIME"
            else:
                merge_status = "MERGED_FILE_NOT_FOUND"
                status_text = "MISSING / MERGED_FILE_NOT_FOUND / NOT_LOADED / NOT_RUNTIME"
        elif split_required:
            merge_status = "NOT_MERGED"
            if local_file_status == "split_present":
                status_text = "SPLIT_PRESENT / NOT_MERGED / NOT_LOADED / NOT_RUNTIME"
            elif local_file_status == "split_partial":
                status_text = "SPLIT_PARTIAL / NOT_MERGED / NOT_LOADED / NOT_RUNTIME"
            else:
                status_text = "MISSING / NOT_MERGED / NOT_LOADED / NOT_RUNTIME"
        else:
            merge_status = "NOT_APPLICABLE"
            status_text = f"{local_file_status.upper()} / NOT_LOADED / NOT_RUNTIME"
        statuses.append(
            ModelPresenceStatus(
                tier=tier,
                role=role,
                model_display_name=display_name,
                expected_local_folder=folder_text,
                expected_file_pattern=pattern,
                expected_files=expected_files,
                split_file_set_required=split_required,
                merged_file_required=merged_required,
                retained_split_files=retained_split_files,
                local_file_status=local_file_status,
                status=status_text,
                merge_status=merge_status,
                detected_file_count_bounded=len(detected_files),
                detected_files_bounded=detected_files,
                detected_retained_split_files_bounded=detected_retained_split_files,
                loaded_status="NOT_LOADED",
                runtime_status="NOT_RUNTIME",
                trusted_memory_write="BLOCKED / NOT_PERFORMED",
                network_download="BLOCKED / NOT_PERFORMED",
                inference="DISABLED / NOT_PERFORMED",
            )
        )
    return statuses


def model_status_by_role(statuses: Iterable[ModelPresenceStatus]) -> dict[str, ModelPresenceStatus]:
    return {status.role: status for status in statuses}


def render_model_presence_status(statuses: Iterable[ModelPresenceStatus] | None = None) -> str:
    rows = list(statuses) if statuses is not None else collect_model_presence_statuses()
    lines = [
        "# Engel Model Library Presence Status",
        "",
        "Status:",
        "MODEL_LIBRARY_PRESENCE_STATUS / READ_ONLY / NOT_LOADED / NOT_RUNTIME",
        "",
        "Boundary:",
        "Manual model file presence does not enable model runtime.",
        "This status does not download, load, infer, call APIs/network, write trusted memory, start background workers, or change authority hierarchy.",
        "",
        "Models:",
    ]
    for item in rows:
        files = ", ".join(item.detected_files_bounded) if item.detected_files_bounded else "NONE"
        retained = (
            ", ".join(item.detected_retained_split_files_bounded)
            if item.detected_retained_split_files_bounded
            else "NONE"
        )
        lines.append(
            f"- {item.tier}: {item.model_display_name} / {item.status} / folder `{item.expected_local_folder}` / files {files} / retained split files {retained}"
        )
    return "\n".join(lines) + "\n"


def statuses_as_dicts(statuses: Iterable[ModelPresenceStatus] | None = None) -> list[dict[str, object]]:
    rows = list(statuses) if statuses is not None else collect_model_presence_statuses()
    return [asdict(item) for item in rows]


def main() -> int:
    print(render_model_presence_status())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
