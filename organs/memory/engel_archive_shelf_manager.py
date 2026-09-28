from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from typing import Any

import engel_memory_archive_status


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_archive_shelf_status() -> dict[str, Any]:
    snapshot = engel_memory_archive_status.build_memory_archive_snapshot()
    roots = []
    for root in snapshot.get("configured_archive_roots", []):
        roots.append(
            {
                "path": root.get("path", ""),
                "status": "available" if root.get("available") else "optional_unavailable",
                "available": bool(root.get("available")),
                "marker_path": root.get("marker_path", ""),
                "marker_present": bool(root.get("marker_present")),
                "top_level_folder_count": int(root.get("top_level_folder_count", 0) or 0),
                "top_level_file_count": int(root.get("top_level_file_count", 0) or 0),
            }
        )

    return {
        "schema": "engel_archive_shelf_manager_v1",
        "generated_at": now_utc(),
        "mode": "STATUS_ONLY_OPTIONAL_ARCHIVE_SHELF_MANAGER",
        "active_work_root": snapshot.get("active_work_root"),
        "active_memory_root": snapshot.get("active_memory_root"),
        "project_local_archive_fallback": snapshot.get("project_local_archive_fallback"),
        "external_archive_required": False,
        "missing_external_archive_is_failure": False,
        "archive_status": snapshot.get("archive_status"),
        "available_archive_roots": snapshot.get("available_archive_roots", []),
        "configured_archive_roots": roots,
        "deprecated_paths": snapshot.get("deprecated_paths", []),
        "safety": {
            "status_only": True,
            "archive_migration_enabled": False,
            "archive_copy_enabled": False,
            "archive_sync_enabled": False,
            "archive_delete_enabled": False,
            "archive_create_enabled": False,
            "trusted_memory_write_enabled": False,
            "memory_promotion_enabled": False,
            "source_patch_apply_enabled": False,
            "queue_route_mutation_enabled": False,
            "provider_calls_enabled": False,
            "model_runtime_enabled": False,
            "background_worker_enabled": False,
        },
    }


def render_archive_shelf_status() -> str:
    status = build_archive_shelf_status()
    lines = [
        "Engel Archive Shelf Manager",
        "",
        "Mode: status-only optional archive shelf surface",
        "Active work root: " + str(status["active_work_root"]),
        "Active memory root: " + str(status["active_memory_root"]),
        "Project-local archive fallback: " + str(status["project_local_archive_fallback"]),
        "Archive status: " + str(status["archive_status"]),
        "External archive required: False",
        "Missing external archive is failure: False",
        "",
        "Configured optional archive shelves:",
    ]
    for root in status["configured_archive_roots"]:
        lines.append(
            "- {path} | {state} | marker={marker} | top-level folders/files={folders}/{files}".format(
                path=root["path"],
                state=root["status"],
                marker=root["marker_present"],
                folders=root["top_level_folder_count"],
                files=root["top_level_file_count"],
            )
        )
    lines.extend(
        [
            "",
            "Deprecated paths:",
        ]
    )
    for path in status["deprecated_paths"]:
        lines.append("- " + str(path) + " (not required)")
    lines.extend(
        [
            "",
            "Safety:",
            "- STATUS_ONLY",
            "- OPTIONAL_EFG_ARCHIVE_ROOTS",
            "- NO_I_DRIVE_REQUIRED",
            "- NO_ARCHIVE_MIGRATION",
            "- NO_ARCHIVE_COPY",
            "- NO_ARCHIVE_SYNC",
            "- NO_ARCHIVE_DELETE",
            "- NO_ARCHIVE_CREATE",
            "- NO_TRUSTED_MEMORY_WRITE",
            "- NO_MEMORY_PROMOTION",
            "- NO_SOURCE_PATCH_APPLY",
            "- NO_QUEUE_ROUTE_MUTATION",
            "- NO_PROVIDER_CALL",
            "- NO_MODEL_RUNTIME",
            "- NO_BACKGROUND_WORKER",
        ]
    )
    return "\n".join(lines)


def render_archive_shelf_report() -> str:
    return "# Engel Archive Shelf Manager\n\n" + render_archive_shelf_status()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Status-only optional archive shelf manager.")
    parser.add_argument("command", choices=("status", "json", "report"), nargs="?", default="status")
    args = parser.parse_args(argv)
    if args.command == "json":
        print(json.dumps(build_archive_shelf_status(), indent=2, sort_keys=True))
    elif args.command == "report":
        print(render_archive_shelf_report())
    else:
        print(render_archive_shelf_status())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
