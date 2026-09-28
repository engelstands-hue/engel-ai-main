from __future__ import annotations

import os
from pathlib import Path
from typing import Any


ACTIVE_WORK_ROOT = Path(r"D:\b.WorkSpace\Engel App")
ACTIVE_MEMORY_ROOT = ACTIVE_WORK_ROOT / "memory"
# (2026-07-28) Restored to the documented project-local fallback; the prior
# runtime\engel_memory_archive variant existed nowhere on disk and broke the
# verifier-pinned contract.
PROJECT_LOCAL_ARCHIVE_FALLBACK = ACTIVE_MEMORY_ROOT / "ENGEL_APP_MEMORY"
EXTERNAL_ARCHIVE_ENV = "ENGEL_HDD_VAULT_ROOT"
# (2026-07-28) These are the ROG-side OPTIONAL Windows archive shelves per
# memory\ENGEL_COMMANDS.md and CLAUDE.md ("when present"). A prior session
# swapped in CT-side Linux roots (/opt/engel, /mnt/engel-hdd-vault) which can
# never exist on this Windows surface and broke the documented contract; the
# CT roots are governed by the runtime path normalizer, not this shelf status.
CONFIGURED_EXTERNAL_ARCHIVE_PATHS = (
    r"E:\ENGEL_APP_MEMORY",
    r"F:\ENGEL_APP_MEMORY",
    r"G:\ENGEL_APP_MEMORY",
)
# (2026-07-28) Keep the LITERAL deprecated path here: the route phrase
# "is I:\ENGEL_APP_MEMORY still needed" must be answerable from the status
# text, and verify_engel_ai_update_routes pins this exact list entry.
DEPRECATED_ARCHIVE_PATHS = (r"I:\ENGEL_APP_MEMORY",)


def _normalized_path_text(path_text: str) -> str:
    return path_text.strip().replace("/", "\\").rstrip("\\").casefold()


def _is_deprecated_archive_path(path_text: str) -> bool:
    normalized = _normalized_path_text(path_text)
    return any(normalized == _normalized_path_text(path) for path in DEPRECATED_ARCHIVE_PATHS)


def _configured_archive_paths(explicit_path: str | None = None) -> list[str]:
    raw_paths: list[str] = []
    if explicit_path is not None:
        raw_paths.append(explicit_path)
    else:
        env_path = os.environ.get(EXTERNAL_ARCHIVE_ENV, "").strip()
        if env_path:
            raw_paths.extend(part.strip() for part in env_path.split(";") if part.strip())
        else:
            raw_paths.extend(CONFIGURED_EXTERNAL_ARCHIVE_PATHS)

    paths: list[str] = []
    seen: set[str] = set()
    for raw_path in raw_paths:
        if not raw_path or _is_deprecated_archive_path(raw_path):
            continue
        normalized = _normalized_path_text(raw_path)
        if normalized not in seen:
            seen.add(normalized)
            paths.append(raw_path)
    return paths


def _shallow_folder_snapshot(root: Path) -> tuple[int, int, list[str], list[dict[str, Any]]]:
    folder_count = 0
    file_count = 0
    top_level_names: list[str] = []
    folder_layout: list[dict[str, Any]] = []
    try:
        for item in root.iterdir():
            top_level_names.append(item.name)
            if item.is_dir():
                folder_count += 1
                try:
                    child_count = sum(1 for _ in item.iterdir())
                except Exception:
                    child_count = -1
                folder_layout.append(
                    {
                        "name": item.name,
                        "path": str(item),
                        "role": "optional external archive folder",
                        "child_count": child_count,
                    }
                )
            elif item.is_file():
                file_count += 1
    except Exception:
        return 0, 0, [], []
    return folder_count, file_count, sorted(top_level_names)[:24], sorted(folder_layout, key=lambda row: str(row.get("name", "")))


def build_memory_archive_snapshot(configured_external_archive_path: str | None = None) -> dict[str, Any]:
    configured_path = (configured_external_archive_path or "").strip()
    deprecated_configured_path = bool(configured_path and _is_deprecated_archive_path(configured_path))
    configured_archive_paths = _configured_archive_paths(configured_external_archive_path)
    archive_roots: list[dict[str, Any]] = []
    marker_paths: list[str] = []
    marker_present = False
    marker_preview = ""
    folder_count = 0
    file_count = 0
    top_level_names: list[str] = []
    folder_layout: list[dict[str, Any]] = []

    for archive_path in configured_archive_paths:
        root = Path(archive_path)
        available = root.exists()
        marker_path = root / ".ENGEL_STORAGE_ROOT"
        root_folder_count = 0
        root_file_count = 0
        root_top_names: list[str] = []
        root_folder_layout: list[dict[str, Any]] = []
        if available:
            root_folder_count, root_file_count, root_top_names, root_folder_layout = _shallow_folder_snapshot(root)
            folder_count += root_folder_count
            file_count += root_file_count
            top_level_names.extend(root_top_names)
            folder_layout.extend(root_folder_layout)
        root_marker_present = bool(available and marker_path.exists())
        if root_marker_present:
            marker_present = True
            marker_paths.append(str(marker_path))
            try:
                if not marker_preview:
                    marker_preview = marker_path.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")[:500].strip()
            except Exception:
                pass
        archive_roots.append(
            {
                "path": str(root),
                "available": available,
                "marker_path": str(marker_path),
                "marker_present": root_marker_present,
                "top_level_folder_count": root_folder_count,
                "top_level_file_count": root_file_count,
            }
        )

    available_roots = [root for root in archive_roots if root["available"]]
    external_available = bool(available_roots)
    selected_root = Path(str(available_roots[0]["path"])) if available_roots else None
    if external_available:
        archive_status = "available"
        external_archive_label = ", ".join(str(root["path"]) for root in available_roots)
    else:
        archive_status = "optional_unavailable"
        external_archive_label = "not configured / unavailable"

    return {
        "schema": "engel_memory_archive_status_v1",
        "archive_status": archive_status,
        "external_archive_required": False,
        "configured_external_archive_path": configured_path or None,
        "configured_external_archive_is_deprecated": deprecated_configured_path,
        "configured_external_archive_paths": configured_archive_paths,
        "configured_archive_roots": archive_roots,
        "available_archive_roots": [str(root["path"]) for root in available_roots],
        "external_archive_path": str(selected_root) if selected_root else None,
        "external_archive_label": external_archive_label,
        "external_archive_available": external_available,
        "missing_external_archive_is_failure": False,
        "active_work_root": str(ACTIVE_WORK_ROOT),
        "active_memory_root": str(ACTIVE_MEMORY_ROOT),
        "project_local_archive_fallback": str(PROJECT_LOCAL_ARCHIVE_FALLBACK),
        "project_local_archive_fallback_exists": PROJECT_LOCAL_ARCHIVE_FALLBACK.exists(),
        "deprecated_paths": list(DEPRECATED_ARCHIVE_PATHS),
        "i_drive_present": Path(r"I:\\").exists(),
        "path": str(selected_root) if selected_root else str(PROJECT_LOCAL_ARCHIVE_FALLBACK),
        "exists": external_available,
        "marker_path": ", ".join(marker_paths),
        "marker_present": marker_present,
        "marker_preview": marker_preview,
        "top_level_folder_count": folder_count,
        "top_level_file_count": file_count,
        "top_level_names": sorted(set(top_level_names))[:24],
        "folder_layout": folder_layout,
        "mode": "READ_ONLY_STATUS_ONLY_OPTIONAL_ARCHIVE_CHECK",
        "archive_migration_enabled": False,
        "archive_sync_enabled": False,
        "archive_copy_enabled": False,
        "archive_delete_enabled": False,
        "trusted_memory_write_enabled": False,
        "source_patch_apply_enabled": False,
        "queue_route_mutation_enabled": False,
    }


def render_memory_archive_status(configured_external_archive_path: str | None = None) -> str:
    snapshot = build_memory_archive_snapshot(configured_external_archive_path)
    lines = [
        "# Engel Memory Archive Status",
        "",
        "Mode: read-only/status-only optional archive check",
        "",
        "Long-term archive shelf:",
    ]
    if snapshot["external_archive_available"]:
        lines.append("Configured external archive roots are available.")
    else:
        lines.append("Optional external archive drive is not configured on this workstation.")
    lines.extend(
        [
            "",
            "External archive:",
            str(snapshot["external_archive_label"]),
            "",
            "Configured external archive roots:",
        ]
    )
    for archive_root in snapshot["configured_archive_roots"]:
        state = "available" if archive_root["available"] else "optional_unavailable"
        lines.append("- " + str(archive_root["path"]) + " | " + state)
    lines.extend(
        [
            "",
            "Archive status:",
            str(snapshot["archive_status"]),
            "",
            "Active work root:",
            str(snapshot["active_work_root"]),
            "",
            "Active memory:",
            str(snapshot["active_memory_root"]),
            "",
            "Project-local archive fallback:",
            str(snapshot["project_local_archive_fallback"]),
            "",
            "Deprecated archive paths:",
        ]
    )
    for path in snapshot["deprecated_paths"]:
        lines.append("- " + path + " (deprecated; not required; not checked as missing infrastructure)")
    lines.extend(
        [
            "",
            "Workstation note:",
            "- Retired I-drive archive paths are not required on the ROG controller.",
            "- Missing external archive storage is not a failure.",
            "- The project-local fallback is reported for future use only; this status route does not create it.",
            "",
            "External archive shallow details:",
            "- marker path: " + (str(snapshot["marker_path"]) if snapshot["marker_path"] else "not checked"),
            "- marker present: " + str(snapshot["marker_present"]),
            "- top-level folders/files: "
            + str(snapshot["top_level_folder_count"])
            + "/"
            + str(snapshot["top_level_file_count"]),
            "",
            "Safety:",
            "- READ_ONLY",
            "- STATUS_ONLY",
            "- OPTIONAL_EXTERNAL_ARCHIVE",
            "- NO_ARCHIVE_MIGRATION",
            "- NO_ARCHIVE_COPY",
            "- NO_ARCHIVE_SYNC",
            "- NO_ARCHIVE_DELETE",
            "- NO_TRUSTED_MEMORY_WRITE",
            "- NO_MEMORY_PROMOTION",
            "- NO_QUEUE_MUTATION",
            "- NO_ROUTE_MUTATION",
            "- NO_SOURCE_PATCH_APPLY",
            "- NO_PROVIDER_CALL",
            "- NO_NETWORK_CALL",
            "- NO_MODEL_RUNTIME",
            "- NO_BACKGROUND_WORKER",
            "- Authority order: Josh first, Guardian second, Engel/runtime below both.",
        ]
    )
    return "\n".join(lines)
