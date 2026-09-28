from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import engel_archive_shelf_manager
import engel_memory_candidate_inventory


ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _source_contains(path: Path, needles: list[str]) -> bool:
    if not path.exists():
        return False
    source = path.read_text(encoding="utf-8", errors="replace")
    return all(needle in source for needle in needles)


def _code_companion_status() -> dict[str, Any]:
    companion = ROOT / "engel_code_companion.py"
    workshop = ROOT / "engel_code_workshop.py"
    return {
        "companion_source_exists": companion.exists(),
        "workshop_backend_exists": workshop.exists(),
        "new_ui_backend_wired": _source_contains(
            companion,
            [
                "engel_code_workshop as workshop",
                "Workshop Files",
                "Ask Engel",
                "workshop.run_file",
            ],
        ),
        "sandbox_workspace": str(ROOT / "code_workspace"),
        "run_timeout_seconds": 20
        if _source_contains(workshop, ["def run_file(relpath: str, timeout_seconds: int = 20)"])
        else None,
        "utf8_capture": _source_contains(workshop, ["encoding=\"utf-8\"", "PYTHONIOENCODING"]),
        "explicit_run_button": _source_contains(companion, ["Run", "action_run_file"]),
    }


def build_progress_dashboard() -> dict[str, Any]:
    inventory = engel_memory_candidate_inventory.build_inventory()
    archive = engel_archive_shelf_manager.build_archive_shelf_status()
    candidate_blocker = None
    if not inventory["counts_match"]:
        candidate_blocker = (
            "memory candidate count mismatch: runtime "
            + str(inventory["runtime_memory_candidate_count"])
            + " / expected "
            + str(inventory["expected_memory_candidate_count"])
        )

    return {
        "schema": "engel_progress_dashboard_v1",
        "generated_at": now_utc(),
        "active_workspace": str(ROOT),
        "mode": "READ_ONLY_PROGRESS_STATUS",
        "feature_expansion_pack": "ENGEL_FEATURE_EXPANSION_PACK_V1",
        "code_companion": _code_companion_status(),
        "memory_candidate_inventory": {
            "expected_memory_candidate_count": inventory["expected_memory_candidate_count"],
            "approved_receipt_memory_candidate_count": inventory["approved_receipt_memory_candidate_count"],
            "runtime_memory_candidate_count": inventory["runtime_memory_candidate_count"],
            "counts_match": inventory["counts_match"],
            "finding": inventory["finding"],
        },
        "archive_shelf_manager": {
            "archive_status": archive["archive_status"],
            "active_memory_root": archive["active_memory_root"],
            "project_local_archive_fallback": archive["project_local_archive_fallback"],
            "configured_archive_roots": archive["configured_archive_roots"],
            "external_archive_required": False,
        },
        "known_full_verifier_blocker": candidate_blocker,
        "packaging_status": "skipped",
        "safe_next_steps": [
            "review memory candidate inventory if counts mismatch",
            "keep archive shelves optional and E/F/G-configured",
            "run full Codex verifier before packaging",
        ],
        "safety": {
            "read_only_status_only": True,
            "packaging_enabled": False,
            "runtime_enabled": False,
            "provider_calls_enabled": False,
            "network_enabled": False,
            "trusted_memory_write_enabled": False,
            "memory_promotion_enabled": False,
            "candidate_approval_enabled": False,
            "source_mutation_from_candidate_enabled": False,
            "route_mutation_enabled": False,
            "queue_mutation_enabled": False,
            "background_worker_enabled": False,
            "autonomy_enabled": False,
        },
    }


def render_progress_status() -> str:
    dashboard = build_progress_dashboard()
    code = dashboard["code_companion"]
    inventory = dashboard["memory_candidate_inventory"]
    archive = dashboard["archive_shelf_manager"]
    lines = [
        "Engel Progress Dashboard",
        "",
        "Mode: read-only progress status",
        "Active workspace: " + str(dashboard["active_workspace"]),
        "Feature pack: " + str(dashboard["feature_expansion_pack"]),
        "",
        "Code Companion:",
        "- companion source exists: " + str(code["companion_source_exists"]),
        "- workshop backend exists: " + str(code["workshop_backend_exists"]),
        "- new UI/backend wired: " + str(code["new_ui_backend_wired"]),
        "- sandbox workspace: " + str(code["sandbox_workspace"]),
        "- run timeout seconds: " + str(code["run_timeout_seconds"]),
        "- UTF-8 capture: " + str(code["utf8_capture"]),
        "- explicit Run button: " + str(code["explicit_run_button"]),
        "",
        "Memory Candidate Inventory:",
        "- expected memory candidates: " + str(inventory["expected_memory_candidate_count"]),
        "- approved receipt memory candidates: " + str(inventory["approved_receipt_memory_candidate_count"]),
        "- runtime memory candidates: " + str(inventory["runtime_memory_candidate_count"]),
        "- counts match: " + str(inventory["counts_match"]),
        "- finding: " + str(inventory["finding"]),
        "",
        "Archive Shelf Manager:",
        "- archive status: " + str(archive["archive_status"]),
        "- active memory root: " + str(archive["active_memory_root"]),
        "- project-local fallback: " + str(archive["project_local_archive_fallback"]),
        "- external archive required: False",
        "",
        "Known full verifier blocker:",
        "- " + (str(dashboard["known_full_verifier_blocker"]) if dashboard["known_full_verifier_blocker"] else "none observed"),
        "",
        "Packaging:",
        "- " + str(dashboard["packaging_status"]),
        "",
        "Safety:",
        "- READ_ONLY_STATUS_ONLY",
        "- NO_PACKAGING",
        "- NO_RUNTIME_ENABLEMENT",
        "- NO_PROVIDER_NETWORK",
        "- NO_TRUSTED_MEMORY_WRITE",
        "- NO_MEMORY_PROMOTION",
        "- NO_CANDIDATE_APPROVAL",
        "- NO_SOURCE_MUTATION_FROM_CANDIDATE",
        "- NO_ROUTE_QUEUE_MUTATION",
        "- NO_BACKGROUND_WORKER",
        "- NO_AUTONOMY",
    ]
    return "\n".join(lines)


def render_progress_report() -> str:
    return "# Engel Progress Dashboard\n\n" + render_progress_status()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only Engel progress dashboard.")
    parser.add_argument("command", choices=("status", "json", "report"), nargs="?", default="status")
    args = parser.parse_args(argv)
    if args.command == "json":
        print(json.dumps(build_progress_dashboard(), indent=2, sort_keys=True))
    elif args.command == "report":
        print(render_progress_report())
    else:
        print(render_progress_status())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
