from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
REPORT_ROOT = PROJECT_ROOT / "reports" / "memory_roots_storage_layout"
RECEIPT_DIR = REPORT_ROOT / "receipts"
EXAMPLES_DIR = REPORT_ROOT / "examples"
MANIFEST_JSON = PROJECT_ROOT / "memory" / "ENGEL_MEMORY_ROOTS_STORAGE_LAYOUT_V1.json"
MANIFEST_MD = PROJECT_ROOT / "memory" / "ENGEL_MEMORY_ROOTS_STORAGE_LAYOUT_V1.md"
LF = "\n"

APPROVAL_TOKEN = "APPROVE_MEMORY_ROOT_SCAFFOLD"
FINAL_DECISION_SUCCESS = "MEMORY ROOT SCAFFOLD CREATED — NO MODEL LOAD — NO INFERENCE — NO FILE MIGRATION"
FINAL_DECISION_MISSING = "CT246/HDD MEMORY ROOT MISSING - SCAFFOLD NOT CREATED"
MANIFEST_FINAL_DECISION = "MEMORY ROOTS RECORDED - CT246/HDD SCAFFOLD CREATED IF APPROVED - NO MODEL LOAD - NO INFERENCE"

APPROVED_ROOTS = [
    {
        "path": "/opt/engel",
        "drive_description": "CT246 engel-ai-main fast SSD runtime root",
        "role": "active_runtime_chat_models_services",
        "preferred_for": [
            "runtime binaries",
            "llama.cpp or local runtime tools",
            "large model libraries",
            "active chat service state",
            "approved fast model/cache storage",
        ],
    },
    {
        "path": "/opt/engel/models-active",
        "drive_description": "CT246 engel-ai-main active model SSD root",
        "role": "active_inference_models",
        "preferred_for": [
            "approved active GGUF/transformer models",
            "current local LLM serving models",
            "promotion-gated model adapters",
        ],
    },
    {
        "path": "/mnt/engel-hdd-vault",
        "drive_description": "Dell PowerEdge HDD/ZFS archive root",
        "role": "bulk_archive_training_outputs_datasets",
        "preferred_for": [
            "training outputs after receipt",
            "bulk datasets",
            "cold model/archive storage",
        ],
        "note": "This is the Dell server HDD vault; CT245 offline-vault routes are disabled.",
    },
]

PREFERRED_RUNTIME_ROOT = "/opt/engel"
EXISTING_MODEL_ROOT = "/opt/engel/models-active"
EXPANSION_LIBRARY_ROOT = "/mnt/engel-hdd-vault"

TARGET_ROOT = Path("/mnt/engel-hdd-vault")
TARGET_SCAFFOLD_FOLDERS = [
    "models",
    "models/manual_downloads",
    "models/approved_for_review",
    "models/runtime_dry_run_eligible",
    "models/quarantine",
    "runtimes",
    "runtimes/llama.cpp",
    "runtimes/quarantine",
    "libraries",
    "libraries/non_model",
    "libraries/approved",
    "libraries/quarantine",
    "libraries/research_papers",
    "libraries/architecture_refs",
    "libraries/math",
    "libraries/coding_languages",
    "libraries/offline_docs",
    "libraries/engel_manuals",
    "chat_exports",
    "chat_exports/incoming",
    "chat_exports/reviewed",
    "chat_exports/invalid",
    "remote_worker",
    "remote_worker/packets",
    "remote_worker/results",
    "remote_worker/receipts",
    "code_companion",
    "code_companion/candidates",
    "code_companion/plans",
    "code_companion/bundles",
    "code_companion/dry_runs",
    "code_companion/receipts",
    "backups",
    "backups/manual",
    "backups/exports",
    "receipts",
    "reports",
    "manifests",
    "quarantine",
]

MAJOR_FOLDERS = [
    "",
    "models",
    "runtimes",
    "libraries",
    "chat_exports",
    "remote_worker",
    "code_companion",
    "backups",
    "receipts",
    "reports",
    "manifests",
    "quarantine",
]

README_BY_FOLDER = {
    "": (
        "# Engel Memory Root\n\n"
        "This is an approved Engel memory root.\n\n"
        "Drive: Seagate FireCuda Gaming 1TB hard drive, P/N 3EDAP6-500.\n\n"
        "Purpose: local/offline Engel memory and library expansion.\n\n"
        "Content remains untrusted until reviewed and approved. No model is loaded from here automatically. "
        "No inference starts from this root automatically. No downloads or installs happen automatically. "
        "Quarantine folders are for unreviewed material.\n"
    ),
    "models": "# Engel Models Area\n\nManual model files may be staged here for future review. Nothing is loaded automatically.\n",
    "runtimes": "# Engel Runtime Tools Area\n\nLocal runtime binaries may be placed here manually. Nothing is executed automatically.\n",
    "libraries": "# Engel Library Expansion Area\n\nApproved and quarantined non-model materials can be organized here. No auto-indexing is enabled.\n",
    "chat_exports": "# Engel Chat Exports Area\n\nManual chat exports can be staged here for bounded review. Content remains untrusted.\n",
    "remote_worker": "# Engel Remote Worker Area\n\nRemote worker packets/results may be stored here as untrusted review material.\n",
    "code_companion": "# Engel Code Companion Area\n\nPatch candidates, plans, bundles, dry-runs, and receipts remain review-only unless later protected gates apply.\n",
    "backups": "# Engel Backups Area\n\nManual backups and exports may live here. Nothing is restored automatically.\n",
    "receipts": "# Engel Receipts Area\n\nSmall local receipts can be stored here for review.\n",
    "reports": "# Engel Reports Area\n\nLocal reports can be stored here for review.\n",
    "manifests": "# Engel Manifests Area\n\nLocal manifests can be stored here for review.\n",
    "quarantine": "# Engel Quarantine Area\n\nUnreviewed content belongs here until explicitly approved.\n",
}


class MemoryRootsLayoutError(ValueError):
    pass


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_stamp(value: str) -> str:
    return value.replace(":", "").replace("-", "").replace("+00:00", "Z")


def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", LF).replace("\r", LF)


def normalize_lf(text: str) -> str:
    normalized = normalize_newlines(text)
    return normalized.rstrip(LF) + LF


def read_text_lf(path: Path) -> str:
    return normalize_newlines(path.read_text(encoding="utf-8-sig"))


def write_text_if_changed(path: Path, text: str) -> bool:
    desired = normalize_lf(text)
    desired_bytes = desired.encode("utf-8")
    if path.exists():
        existing_bytes = path.read_bytes()
        try:
            existing_text = existing_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            existing_text = existing_bytes.decode("utf-8", errors="replace")
        if normalize_lf(existing_text) == desired and existing_bytes == desired_bytes:
            return False
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline=LF) as handle:
        handle.write(desired)
    return True


def write_lf_text(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def ensure_report_folders() -> None:
    for folder in [REPORT_ROOT, RECEIPT_DIR, EXAMPLES_DIR]:
        folder.mkdir(parents=True, exist_ok=True)


def project_relative(path: Path) -> str:
    try:
        return str(path.resolve(strict=False).relative_to(PROJECT_ROOT.resolve(strict=False))).replace("/", "\\")
    except ValueError:
        return str(path.resolve(strict=False))


def external_path(path: Path) -> str:
    return str(path.resolve(strict=False))


def root_status(root: dict[str, Any]) -> dict[str, Any]:
    path = Path(str(root["path"]))
    row = {
        "path": str(root["path"]),
        "drive_description": root["drive_description"],
        "role": root["role"],
        "preferred_for": root.get("preferred_for", []),
        "present": path.exists() and path.is_dir(),
        "recursive_scan_enabled": False,
    }
    if "note" in root:
        row["note"] = root["note"]
    if str(root["path"]) == EXPANSION_LIBRARY_ROOT:
        row["scaffold_created"] = f_scaffold_status()["complete"]
    return row


def approved_root_statuses() -> list[dict[str, Any]]:
    return [root_status(root) for root in APPROVED_ROOTS]


def approved_root_contracts(*, f_scaffold_created: bool) -> list[dict[str, Any]]:
    contracts: list[dict[str, Any]] = []
    for root in APPROVED_ROOTS:
        row: dict[str, Any] = {
            "path": str(root["path"]),
            "drive_description": root["drive_description"],
            "role": root["role"],
            "preferred_for": list(root.get("preferred_for", [])),
            "recursive_scan_enabled": False,
        }
        if "note" in root:
            row["note"] = root["note"]
        if str(root["path"]) == EXPANSION_LIBRARY_ROOT:
            row["scaffold_created"] = f_scaffold_created
        contracts.append(row)
    return contracts


def target_expected_paths() -> list[Path]:
    return [TARGET_ROOT / Path(relative) for relative in TARGET_SCAFFOLD_FOLDERS]


def f_marker_paths() -> list[Path]:
    paths = [TARGET_ROOT / "README_ENGEL_MEMORY_ROOT.md"]
    for relative in MAJOR_FOLDERS:
        if relative:
            paths.append(TARGET_ROOT / relative / "README.md")
    for relative in TARGET_SCAFFOLD_FOLDERS:
        paths.append(TARGET_ROOT / relative / ".gitkeep")
    return paths


def f_drive_present() -> bool:
    anchor = Path(TARGET_ROOT.anchor) if TARGET_ROOT.anchor else TARGET_ROOT
    return anchor.exists()


def f_scaffold_status() -> dict[str, Any]:
    expected = target_expected_paths()
    missing = [external_path(path) for path in expected if not path.exists() or not path.is_dir()]
    markers = f_marker_paths()
    missing_markers = [external_path(path) for path in markers if not path.exists() or not path.is_file()]
    return {
        "root_path": str(TARGET_ROOT),
        "drive_present": f_drive_present(),
        "root_present": TARGET_ROOT.exists() and TARGET_ROOT.is_dir(),
        "expected_folder_count": len(expected),
        "missing_folders": missing,
        "marker_file_count": len(markers),
        "missing_marker_files": missing_markers,
        "complete": not missing and not missing_markers and TARGET_ROOT.exists(),
        "recursive_scan_enabled": False,
    }


def load_existing_manifest_json(json_path: Path | None = None) -> dict[str, Any] | None:
    path = json_path or MANIFEST_JSON
    if not path.exists():
        return None
    try:
        data = json.loads(read_text_lf(path))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def read_existing_created_at(json_path: Path | None = None) -> str | None:
    data = load_existing_manifest_json(json_path)
    value = data.get("created_at") if data else None
    return value if isinstance(value, str) and value else None


def read_existing_f_scaffold_created(json_path: Path | None = None) -> bool | None:
    data = load_existing_manifest_json(json_path)
    roots = data.get("approved_roots") if data else None
    if not isinstance(roots, list):
        return None
    for root in roots:
        if isinstance(root, dict) and root.get("path") == EXPANSION_LIBRARY_ROOT:
            value = root.get("scaffold_created")
            return value if isinstance(value, bool) else None
    return None


def resolve_manifest_created_at(fallback: str | None = None) -> str:
    return read_existing_created_at() or fallback or now_utc()


def resolve_f_scaffold_created(fallback: bool | None = None) -> bool:
    if fallback is not None:
        return fallback
    existing = read_existing_f_scaffold_created()
    if existing is not None:
        return existing
    return bool(f_scaffold_status()["complete"])


def manifest_payload(created_at: str | None = None, f_scaffold_created: bool | None = None) -> dict[str, Any]:
    resolved_created_at = resolve_manifest_created_at(created_at)
    resolved_f_scaffold_created = resolve_f_scaffold_created(f_scaffold_created)
    return {
        "memory_roots_layout_version": "1",
        "created_at": resolved_created_at,
        "created_by": "Engel Memory Roots Storage Layout",
        "approved_roots": approved_root_contracts(f_scaffold_created=resolved_f_scaffold_created),
        "preferred_runtime_root": PREFERRED_RUNTIME_ROOT,
        "existing_model_root": EXISTING_MODEL_ROOT,
        "expansion_library_root": EXPANSION_LIBRARY_ROOT,
        "auto_index_enabled": False,
        "inference_enabled": False,
        "download_enabled": False,
        "trusted_memory_write_enabled": False,
        "model_load_enabled": False,
        "runtime_execution_enabled": False,
        "provider_api_enabled": False,
        "source_route_queue_mutation": False,
        "final_decision": MANIFEST_FINAL_DECISION,
    }


def render_manifest_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Engel Memory Roots Storage Layout V1",
        "",
        f"- created_at: `{payload['created_at']}`",
        f"- preferred_runtime_root: `{payload['preferred_runtime_root']}`",
        f"- existing_model_root: `{payload['existing_model_root']}`",
        f"- expansion_library_root: `{payload['expansion_library_root']}`",
        "",
        "## Approved Roots",
    ]
    for root in payload["approved_roots"]:
        lines.extend(
            [
                f"- `{root['path']}`",
                f"  - drive: {root['drive_description']}",
                f"  - role: {root['role']}",
                "  - preferred_for:",
            ]
        )
        lines.extend(f"    - {item}" for item in root.get("preferred_for", []))
        lines.append(f"  - recursive_scan_enabled: `{str(root['recursive_scan_enabled']).lower()}`")
        if "scaffold_created" in root:
            lines.append(f"  - scaffold_created: `{str(root['scaffold_created']).lower()}`")
        if "note" in root:
            lines.append(f"  - note: {root['note']}")
    lines.extend(
        [
            "",
            "## Safety",
            f"- auto_index_enabled: `{str(payload['auto_index_enabled']).lower()}`",
            f"- inference_enabled: `{str(payload['inference_enabled']).lower()}`",
            f"- download_enabled: `{str(payload['download_enabled']).lower()}`",
            f"- trusted_memory_write_enabled: `{str(payload['trusted_memory_write_enabled']).lower()}`",
            f"- model_load_enabled: `{str(payload['model_load_enabled']).lower()}`",
            f"- runtime_execution_enabled: `{str(payload['runtime_execution_enabled']).lower()}`",
            f"- provider_api_enabled: `{str(payload['provider_api_enabled']).lower()}`",
            f"- source_route_queue_mutation: `{str(payload['source_route_queue_mutation']).lower()}`",
            f"- final_decision: `{payload['final_decision']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def write_manifest(created_at: str | None = None, f_scaffold_created: bool | None = None) -> dict[str, Any]:
    payload = manifest_payload(created_at=created_at, f_scaffold_created=f_scaffold_created)
    json_changed = write_text_if_changed(MANIFEST_JSON, json.dumps(payload, indent=2, sort_keys=True))
    markdown_changed = write_text_if_changed(MANIFEST_MD, render_manifest_markdown(payload))
    return {
        "manifest_json": project_relative(MANIFEST_JSON),
        "manifest_markdown": project_relative(MANIFEST_MD),
        "manifest_json_changed": json_changed,
        "manifest_markdown_changed": markdown_changed,
    }


def validate_layout() -> dict[str, Any]:
    return {
        "valid": all(root["present"] for root in approved_root_statuses()) and f_scaffold_status()["complete"],
        "approved_roots": approved_root_statuses(),
        "f_scaffold_status": f_scaffold_status(),
        "preferred_runtime_root": PREFERRED_RUNTIME_ROOT,
        "existing_model_root": EXISTING_MODEL_ROOT,
        "expansion_library_root": EXPANSION_LIBRARY_ROOT,
        "recursive_scan_enabled": False,
        "auto_index_enabled": False,
        "inference_enabled": False,
    }


def scaffold_f(*, approval_token: str | None, created_at: str | None = None) -> dict[str, Any]:
    if approval_token != APPROVAL_TOKEN:
        raise MemoryRootsLayoutError("approval_token_rejected")
    timestamp = created_at or now_utc()
    ensure_report_folders()
    if not f_drive_present():
        entry = {
            "memory_root_scaffold_receipt_version": "1",
            "created_at": timestamp,
            "created_by": "Engel Memory Roots Storage Layout",
            "target_root": str(TARGET_ROOT),
            "approval_token_name": APPROVAL_TOKEN,
            "approval_token_verified": True,
            "f_drive_present": False,
            "folders_created_or_confirmed": [],
            "marker_files_created_or_confirmed": [],
            "files_moved": False,
            "models_loaded": False,
            "inference_enabled": False,
            "download_enabled": False,
            "trusted_memory_write_enabled": False,
            "final_decision": FINAL_DECISION_MISSING,
        }
        artifacts = write_receipt(entry)
        write_manifest(created_at=timestamp)
        return {"scaffold_status": "missing_f_drive", "entry": entry, **artifacts}

    created_folders: list[str] = []
    created_markers: list[str] = []
    for folder in [TARGET_ROOT, *target_expected_paths()]:
        folder.mkdir(parents=True, exist_ok=True)
        created_folders.append(external_path(folder))
    for relative, text in README_BY_FOLDER.items():
        if relative:
            path = TARGET_ROOT / relative / "README.md"
        else:
            path = TARGET_ROOT / "README_ENGEL_MEMORY_ROOT.md"
        write_lf_text(path, text)
        created_markers.append(external_path(path))
    for folder in target_expected_paths():
        marker = folder / ".gitkeep"
        if not marker.exists():
            write_lf_text(marker, "")
        created_markers.append(external_path(marker))
    entry = {
        "memory_root_scaffold_receipt_version": "1",
        "created_at": timestamp,
        "created_by": "Engel Memory Roots Storage Layout",
        "target_root": str(TARGET_ROOT),
        "approval_token_name": APPROVAL_TOKEN,
        "approval_token_verified": True,
        "f_drive_present": True,
        "folders_created_or_confirmed": created_folders,
        "marker_files_created_or_confirmed": created_markers,
        "files_moved": False,
        "files_deleted": False,
        "files_copied_from_existing_roots": False,
        "models_loaded": False,
        "runtime_executed": False,
        "inference_enabled": False,
        "download_enabled": False,
        "install_enabled": False,
        "auto_index_enabled": False,
        "trusted_memory_write_enabled": False,
        "source_route_queue_mutation": False,
        "final_decision": FINAL_DECISION_SUCCESS,
    }
    artifacts = write_receipt(entry)
    manifest_paths = write_manifest(created_at=timestamp, f_scaffold_created=True)
    return {"scaffold_status": "created_or_confirmed", "entry": entry, **artifacts, **manifest_paths}


def write_receipt(entry: dict[str, Any]) -> dict[str, str]:
    ensure_report_folders()
    stamp = safe_stamp(str(entry["created_at"]))
    receipt_json = RECEIPT_DIR / f"MEMORY_ROOT_SCAFFOLD_{stamp}.json"
    receipt_md = RECEIPT_DIR / f"MEMORY_ROOT_SCAFFOLD_{stamp}.md"
    write_lf_text(receipt_json, json.dumps(entry, indent=2, sort_keys=True) + "\n")
    write_lf_text(
        receipt_md,
        "# Engel Memory Root Scaffold Receipt\n\n"
        f"- timestamp: `{entry['created_at']}`\n"
        f"- target_root: `{entry['target_root']}`\n"
        f"- approval_token_name: `{entry['approval_token_name']}`\n"
        f"- approval_token_verified: `{entry['approval_token_verified']}`\n"
        f"- files_moved: `{entry.get('files_moved', False)}`\n"
        f"- models_loaded: `{entry.get('models_loaded', False)}`\n"
        f"- inference_enabled: `{entry.get('inference_enabled', False)}`\n"
        f"- final_decision: `{entry['final_decision']}`\n\n"
        "No files were moved between drives. No model was loaded. No inference was run.\n",
    )
    return {"receipt_json": project_relative(receipt_json), "receipt_markdown": project_relative(receipt_md)}


def status_payload() -> dict[str, Any]:
    receipts = [path for path in RECEIPT_DIR.glob("*.json") if path.is_file()] if RECEIPT_DIR.exists() else []
    return {
        "memory_roots_status_version": "1",
        "approved_roots": approved_root_statuses(),
        "f_scaffold_status": f_scaffold_status(),
        "preferred_runtime_root": PREFERRED_RUNTIME_ROOT,
        "existing_model_root": EXISTING_MODEL_ROOT,
        "expansion_library_root": EXPANSION_LIBRARY_ROOT,
        "receipt_count": len(receipts),
        "manifest_json_present": MANIFEST_JSON.exists(),
        "manifest_markdown_present": MANIFEST_MD.exists(),
        "safety_flags": {
            "recursive_scan_enabled": False,
            "auto_index_enabled": False,
            "inference_enabled": False,
            "model_load_enabled": False,
            "download_enabled": False,
            "install_enabled": False,
            "trusted_memory_write_enabled": False,
            "source_route_queue_mutation": False,
        },
    }


def render_status() -> str:
    data = status_payload()
    lines = [
        "Engel Memory Roots Storage Layout V1",
        "",
        "Approved roots:",
    ]
    for root in data["approved_roots"]:
        lines.append(f"- {root['path']}: role={root['role']} / present={root['present']} / recursive_scan_enabled={root['recursive_scan_enabled']}")
    scaffold = data["f_scaffold_status"]
    lines.extend(
        [
            "",
            f"Archive scaffold complete: {scaffold['complete']}",
            f"Archive missing folders: {len(scaffold['missing_folders'])}",
            f"Archive missing marker files: {len(scaffold['missing_marker_files'])}",
            f"preferred_runtime_root: {data['preferred_runtime_root']}",
            f"existing_model_root: {data['existing_model_root']}",
            f"expansion_library_root: {data['expansion_library_root']}",
            "",
            "Safety:",
        ]
    )
    lines.extend(f"- {key}: {value}" for key, value in data["safety_flags"].items())
    return "\n".join(lines) + "\n"


def render_roots() -> str:
    lines = ["Engel Approved Memory Roots", ""]
    for root in approved_root_statuses():
        lines.append(f"- {root['path']}: {root['drive_description']} / role={root['role']} / present={root['present']}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Engel Memory Roots Storage Layout V1")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status")
    subparsers.add_parser("roots")
    scaffold_parser = subparsers.add_parser("scaffold-f")
    scaffold_parser.add_argument("--approval", required=True)
    subparsers.add_parser("validate")
    subparsers.add_parser("manifest")
    subparsers.add_parser("json")
    args = parser.parse_args(argv)

    try:
        if args.command == "status":
            print(render_status(), end="")
        elif args.command == "roots":
            print(render_roots(), end="")
        elif args.command == "scaffold-f":
            print(json.dumps(scaffold_f(approval_token=args.approval), indent=2, sort_keys=True))
        elif args.command == "validate":
            print(json.dumps(validate_layout(), indent=2, sort_keys=True))
        elif args.command == "manifest":
            paths = write_manifest()
            payload = manifest_payload()
            payload["manifest_paths"] = paths
            print(json.dumps(payload, indent=2, sort_keys=True))
        elif args.command == "json":
            payload = status_payload()
            payload["manifest"] = manifest_payload()
            print(json.dumps(payload, indent=2, sort_keys=True))
    except MemoryRootsLayoutError as exc:
        print(json.dumps({"ok": False, "reason": str(exc)}, indent=2, sort_keys=True))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
