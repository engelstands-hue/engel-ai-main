from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
REPORT_ROOT = PROJECT_ROOT / "reports" / "ai_runtime_path_config"
RECEIPT_DIR = REPORT_ROOT / "receipts"
MANIFEST_DIR = REPORT_ROOT / "manifests"
EXAMPLES_DIR = REPORT_ROOT / "examples"
MANIFEST_PATH = MANIFEST_DIR / "engel_ai_local_runtime_path_config_manifest.json"

APPROVAL_TOKEN = "APPROVE_LOCAL_RUNTIME_PATH"
PREFERRED_RUNTIME_ROOT = Path("/opt/engel")
ALTERNATE_RUNTIME_ROOT = Path("/mnt/engel-hdd-vault")
EXISTING_MODEL_ROOT = Path("/opt/engel/models-active")
APPROVED_ROOTS = [
    {
        "path": "/opt/engel",
        "drive_description": "CT246 engel-ai-main fast SSD runtime root",
        "role": "active_runtime_chat_models_services",
    },
    {
        "path": "/opt/engel/models-active",
        "drive_description": "CT246 fast SSD active model root",
        "role": "active_inference_models",
    },
    {
        "path": "/mnt/engel-hdd-vault",
        "drive_description": "Dell PowerEdge HDD/ZFS vault for cold archive when mounted",
        "role": "bulk_archive_training_outputs_datasets",
    },
]
ALLOWED_RUNTIME_ROOTS = [
    ("preferred_runtime_root", PREFERRED_RUNTIME_ROOT),
    ("alternate_runtime_root", ALTERNATE_RUNTIME_ROOT),
]

FINAL_DECISION_SUCCESS = "LOCAL RUNTIME PATH RECORDED — NOT EXECUTED — NO MODEL LOAD — NO INFERENCE"
FINAL_DECISION_BLOCKED = "LOCAL RUNTIME PATH NOT CONFIGURED — BINARY MISSING — NOT EXECUTED"
MAX_READ_CHARS = 80_000


class RuntimePathConfigError(ValueError):
    pass


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_stamp(value: str) -> str:
    return value.replace(":", "").replace("-", "").replace("+00:00", "Z")


def safe_slug(value: str, max_length: int = 96) -> str:
    lowered = value.lower()
    chars: list[str] = []
    for char in lowered:
        if char.isascii() and char.isalnum():
            chars.append(char)
        elif char in {"-", "_", "."}:
            chars.append(char)
        else:
            chars.append("_")
    slug = "_".join(part for part in "".join(chars).strip("._-").split("_") if part)
    return (slug or "runtime_path_config")[:max_length]


def write_lf_text(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def ensure_folders() -> None:
    for folder in [REPORT_ROOT, RECEIPT_DIR, MANIFEST_DIR, EXAMPLES_DIR]:
        folder.mkdir(parents=True, exist_ok=True)


def project_relative(path: Path) -> str:
    try:
        return str(path.resolve(strict=False).relative_to(PROJECT_ROOT.resolve(strict=False))).replace("/", "\\")
    except ValueError:
        return str(path.resolve(strict=False))


def normalized_path_key(path: Path) -> str:
    return str(path.resolve(strict=False)).rstrip("\\/").lower()


def is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except ValueError:
        return False


def unsafe_path_reason(path_text: str) -> str | None:
    if "://" in path_text:
        return "uri_paths_are_rejected"
    if path_text.startswith("\\\\"):
        return "unc_paths_are_rejected"
    if "\n" in path_text or "\r" in path_text:
        return "multiline_paths_are_rejected"
    if any(part == ".." for part in Path(path_text).parts):
        return "path_traversal_rejected"
    return None


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace")[:MAX_READ_CHARS])
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def approved_root_statuses() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for root in APPROVED_ROOTS:
        path = Path(root["path"])
        rows.append(
            {
                "path": root["path"],
                "drive_description": root["drive_description"],
                "role": root["role"],
                "present": path.exists() and path.is_dir(),
                "recursive_scan_enabled": False,
            }
        )
    return rows


def approved_root_for_path(path: Path) -> dict[str, Any] | None:
    for root in APPROVED_ROOTS:
        root_path = Path(root["path"])
        if is_relative_to(path, root_path):
            return root
    return None


def validate_root(root_text: str) -> dict[str, Any]:
    unsafe = unsafe_path_reason(root_text)
    root_path = Path(root_text)
    resolved = root_path.resolve(strict=False)
    base = {
        "valid": False,
        "input_path": root_text,
        "root_path": str(resolved),
        "approved_role": None,
        "drive_description": None,
        "present": resolved.exists() and resolved.is_dir(),
        "recursive_scan_enabled": False,
        "reason": "",
    }
    if unsafe:
        base["reason"] = unsafe
        return base
    for root in APPROVED_ROOTS:
        if normalized_path_key(resolved) == normalized_path_key(Path(root["path"])):
            base["valid"] = True
            base["approved_role"] = root["role"]
            base["drive_description"] = root["drive_description"]
            base["reason"] = "approved_engel_memory_root"
            return base
    base["reason"] = "root_not_approved"
    return base


def runtime_root_status(path: Path, *, allow_example_fixture: bool = True) -> tuple[str, dict[str, Any] | None]:
    for status, runtime_root in ALLOWED_RUNTIME_ROOTS:
        if is_relative_to(path, runtime_root):
            return status, approved_root_for_path(runtime_root)
    if allow_example_fixture and is_relative_to(path, EXAMPLES_DIR):
        return "example_fixture", None
    root = approved_root_for_path(path)
    if root:
        return "approved_engel_root_but_not_runtime_root", root
    return "outside_approved_engel_roots", None


def validate_runtime(runtime_path_text: str, *, allow_example_fixture: bool = True) -> dict[str, Any]:
    unsafe = unsafe_path_reason(runtime_path_text)
    raw = Path(runtime_path_text)
    path = raw if raw.is_absolute() else PROJECT_ROOT / raw
    resolved = path.resolve(strict=False)
    base: dict[str, Any] = {
        "valid": False,
        "input_path": runtime_path_text,
        "runtime_binary_path": str(resolved),
        "runtime_binary_present": resolved.exists() and resolved.is_file(),
        "runtime_backend": "llama_cpp",
        "extension": resolved.suffix.lower(),
        "root_status": "unknown",
        "approved_root": None,
        "preferred_runtime_root": str(PREFERRED_RUNTIME_ROOT),
        "alternate_runtime_root": str(ALTERNATE_RUNTIME_ROOT),
        "existing_model_root": str(EXISTING_MODEL_ROOT),
        "execution_enabled": False,
        "model_load_enabled": False,
        "inference_enabled": False,
        "reason": "",
    }
    if unsafe:
        base["reason"] = unsafe
        return base
    root_status, root = runtime_root_status(resolved, allow_example_fixture=allow_example_fixture)
    base["root_status"] = root_status
    base["approved_root"] = root["path"] if root else None
    if not resolved.exists():
        base["reason"] = "runtime_binary_missing"
        return base
    if not resolved.is_file():
        base["reason"] = "runtime_path_is_not_file"
        return base
    if resolved.suffix.lower() != ".exe":
        base["reason"] = "windows_runtime_binary_must_be_exe"
        return base
    if root_status == "approved_engel_root_but_not_runtime_root":
        base["reason"] = "outside_approved_runtime_roots_rejected"
        return base
    if root_status == "outside_approved_engel_roots":
        base["reason"] = "outside_approved_runtime_roots_external_unreviewed"
        return base
    try:
        size = resolved.stat().st_size
    except OSError:
        size = None
    base.update(
        {
            "valid": True,
            "file_size_bytes": size,
            "runtime_binary_present": True,
            "runtime_path_approved": True,
            "reason": "runtime_binary_path_validated_without_execution",
        }
    )
    return base


def empty_manifest() -> dict[str, Any]:
    return {
        "runtime_path_config_version": "1",
        "created_by": "Engel AI Local Runtime Path Config",
        "updated_at": None,
        "approved_roots": approved_root_statuses(),
        "preferred_runtime_root": str(PREFERRED_RUNTIME_ROOT),
        "alternate_runtime_root": str(ALTERNATE_RUNTIME_ROOT),
        "existing_model_root": str(EXISTING_MODEL_ROOT),
        "runtime_backend": "not_configured",
        "runtime_binary_path": None,
        "runtime_binary_present": False,
        "runtime_path_approved": False,
        "approval_token_name": None,
        "approval_token_verified": False,
        "runtime_execution_enabled": False,
        "model_load_enabled": False,
        "inference_enabled": False,
        "auto_start_enabled": False,
        "provider_api_enabled": False,
        "download_enabled": False,
        "install_enabled": False,
        "trusted_memory_write_enabled": False,
        "final_decision": FINAL_DECISION_BLOCKED,
    }


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    data = read_json(path)
    return data if data else empty_manifest()


def build_runtime_path_config(runtime_path_text: str, *, backend: str, approval_token: str | None, created_at: str | None = None) -> dict[str, Any]:
    if approval_token != APPROVAL_TOKEN:
        raise RuntimePathConfigError("approval_token_rejected")
    if backend != "llama_cpp":
        raise RuntimePathConfigError("runtime_backend_rejected")
    validation = validate_runtime(runtime_path_text)
    if not validation["valid"]:
        raise RuntimePathConfigError(str(validation["reason"]))
    return {
        "runtime_path_config_version": "1",
        "created_at": created_at or now_utc(),
        "created_by": "Engel AI Local Runtime Path Config",
        "approved_roots": approved_root_statuses(),
        "preferred_runtime_root": str(PREFERRED_RUNTIME_ROOT),
        "alternate_runtime_root": str(ALTERNATE_RUNTIME_ROOT),
        "existing_model_root": str(EXISTING_MODEL_ROOT),
        "runtime_backend": "llama_cpp",
        "runtime_binary_path": validation["runtime_binary_path"],
        "runtime_binary_present": True,
        "runtime_path_approved": True,
        "runtime_root_status": validation["root_status"],
        "approved_root": validation["approved_root"],
        "approval_token_name": APPROVAL_TOKEN,
        "approval_token_verified": True,
        "runtime_execution_enabled": False,
        "model_load_enabled": False,
        "inference_enabled": False,
        "auto_start_enabled": False,
        "provider_api_enabled": False,
        "download_enabled": False,
        "install_enabled": False,
        "trusted_memory_write_enabled": False,
        "notes": "Runtime path was recorded only. The runtime binary was not executed.",
        "final_decision": FINAL_DECISION_SUCCESS,
    }


def render_receipt_markdown(entry: dict[str, Any]) -> str:
    return (
        "# Engel AI Local Runtime Path Config Receipt\n\n"
        f"- timestamp: `{entry['created_at']}`\n"
        f"- runtime_backend: `{entry['runtime_backend']}`\n"
        f"- runtime_binary_path: `{entry['runtime_binary_path']}`\n"
        f"- runtime_binary_present: `{entry['runtime_binary_present']}`\n"
        f"- runtime_path_approved: `{entry['runtime_path_approved']}`\n"
        f"- approval_token_name: `{entry['approval_token_name']}`\n"
        f"- approval_token_verified: `{entry['approval_token_verified']}`\n"
        f"- runtime_execution_enabled: `{entry['runtime_execution_enabled']}`\n"
        f"- model_load_enabled: `{entry['model_load_enabled']}`\n"
        f"- inference_enabled: `{entry['inference_enabled']}`\n"
        f"- auto_start_enabled: `{entry['auto_start_enabled']}`\n"
        f"- final_decision: `{entry['final_decision']}`\n\n"
        "No runtime was executed. No model was loaded. No inference was run. No download or install occurred.\n"
    )


def write_runtime_path_artifacts(entry: dict[str, Any], *, receipt_dir: Path = RECEIPT_DIR, manifest_path: Path = MANIFEST_PATH) -> dict[str, str]:
    ensure_folders()
    receipt_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    stamp = safe_stamp(str(entry["created_at"]))
    binary_name = Path(str(entry["runtime_binary_path"])).name
    stem = f"LOCAL_RUNTIME_PATH_{stamp}_{safe_slug(binary_name)}"
    receipt_json = receipt_dir / f"{stem}.json"
    receipt_md = receipt_dir / f"{stem}.md"
    manifest_payload = dict(entry)
    manifest_payload["updated_at"] = entry["created_at"]
    write_lf_text(receipt_json, json.dumps(entry, indent=2, sort_keys=True) + "\n")
    write_lf_text(receipt_md, render_receipt_markdown(entry))
    write_lf_text(manifest_path, json.dumps(manifest_payload, indent=2, sort_keys=True) + "\n")
    return {
        "receipt_json": project_relative(receipt_json),
        "receipt_markdown": project_relative(receipt_md),
        "manifest_path": project_relative(manifest_path),
    }


def set_runtime(
    runtime_path_text: str,
    *,
    backend: str,
    approval_token: str | None,
    receipt_dir: Path = RECEIPT_DIR,
    manifest_path: Path = MANIFEST_PATH,
    created_at: str | None = None,
) -> dict[str, Any]:
    entry = build_runtime_path_config(runtime_path_text, backend=backend, approval_token=approval_token, created_at=created_at)
    artifacts = write_runtime_path_artifacts(entry, receipt_dir=receipt_dir, manifest_path=manifest_path)
    return {"runtime_path_config_status": "recorded", "entry": entry, **artifacts}


def status_payload() -> dict[str, Any]:
    ensure_folders()
    manifest = load_manifest()
    receipts = [path for path in RECEIPT_DIR.glob("*.json") if path.is_file()] if RECEIPT_DIR.exists() else []
    return {
        "runtime_path_status_version": "1",
        "mode": "local_runtime_path_config_only",
        "approved_roots": approved_root_statuses(),
        "preferred_runtime_root": str(PREFERRED_RUNTIME_ROOT),
        "alternate_runtime_root": str(ALTERNATE_RUNTIME_ROOT),
        "existing_model_root": str(EXISTING_MODEL_ROOT),
        "configured_runtime_binary_path": manifest.get("runtime_binary_path"),
        "runtime_backend": manifest.get("runtime_backend", "not_configured"),
        "runtime_binary_present": bool(manifest.get("runtime_binary_present") is True and Path(str(manifest.get("runtime_binary_path"))).exists()),
        "runtime_path_approved": bool(manifest.get("runtime_path_approved") is True),
        "receipt_count": len(receipts),
        "manifest_present": MANIFEST_PATH.exists(),
        "folders": {
            "root": project_relative(REPORT_ROOT),
            "receipts": project_relative(RECEIPT_DIR),
            "manifests": project_relative(MANIFEST_DIR),
            "examples": project_relative(EXAMPLES_DIR),
        },
        "safety_flags": {
            "execution_enabled": False,
            "runtime_execution_enabled": False,
            "inference_enabled": False,
            "model_load_enabled": False,
            "auto_start_enabled": False,
            "provider_api_enabled": False,
            "download_enabled": False,
            "install_enabled": False,
            "trusted_memory_write_enabled": False,
            "source_route_queue_mutation": False,
            "recursive_scan_enabled": False,
        },
    }


def render_status() -> str:
    data = status_payload()
    lines = [
        "Engel AI Local Runtime Path Config V1",
        "Mode: local runtime path configuration only; no execution, no model load, no inference",
        "",
        "Approved Engel roots:",
    ]
    for root in data["approved_roots"]:
        lines.append(f"- {root['path']} ({root['role']}): present={root['present']}, recursive_scan_enabled={root['recursive_scan_enabled']}")
    lines.extend(
        [
            "",
            f"preferred_runtime_root: {data['preferred_runtime_root']}",
            f"alternate_runtime_root: {data['alternate_runtime_root']}",
            f"existing_model_root: {data['existing_model_root']}",
            f"configured_runtime_binary_path: {data['configured_runtime_binary_path']}",
            f"runtime_backend: {data['runtime_backend']}",
            f"runtime_binary_present: {data['runtime_binary_present']}",
            f"runtime_path_approved: {data['runtime_path_approved']}",
            "",
            "Safety:",
        ]
    )
    lines.extend(f"- {key}: {value}" for key, value in data["safety_flags"].items())
    return "\n".join(lines) + "\n"


def render_roots() -> str:
    lines = ["Engel Approved Memory Roots", ""]
    for root in approved_root_statuses():
        lines.append(
            f"- {root['path']}: drive={root['drive_description']} / role={root['role']} / present={root['present']} / recursive_scan_enabled={root['recursive_scan_enabled']}"
        )
    lines.append("")
    lines.append(f"Preferred runtime root: {PREFERRED_RUNTIME_ROOT}")
    lines.append(f"Alternate runtime root: {ALTERNATE_RUNTIME_ROOT}")
    lines.append(f"Existing model root: {EXISTING_MODEL_ROOT}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Engel AI Local Runtime Path Config V1")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status")
    subparsers.add_parser("roots")
    root_parser = subparsers.add_parser("validate-root")
    root_parser.add_argument("root_path")
    runtime_parser = subparsers.add_parser("validate-runtime")
    runtime_parser.add_argument("runtime_binary_path")
    set_parser = subparsers.add_parser("set-runtime")
    set_parser.add_argument("runtime_binary_path")
    set_parser.add_argument("--backend", required=True)
    set_parser.add_argument("--approval", required=True)
    subparsers.add_parser("manifest")
    subparsers.add_parser("json")
    args = parser.parse_args(argv)

    try:
        if args.command == "status":
            print(render_status(), end="")
        elif args.command == "roots":
            ensure_folders()
            print(render_roots(), end="")
        elif args.command == "validate-root":
            print(json.dumps(validate_root(args.root_path), indent=2, sort_keys=True))
        elif args.command == "validate-runtime":
            print(json.dumps(validate_runtime(args.runtime_binary_path), indent=2, sort_keys=True))
        elif args.command == "set-runtime":
            print(json.dumps(set_runtime(args.runtime_binary_path, backend=args.backend, approval_token=args.approval), indent=2, sort_keys=True))
        elif args.command == "manifest":
            ensure_folders()
            print(json.dumps(load_manifest(), indent=2, sort_keys=True))
        elif args.command == "json":
            payload = status_payload()
            payload["manifest"] = load_manifest()
            print(json.dumps(payload, indent=2, sort_keys=True))
    except RuntimePathConfigError as exc:
        print(json.dumps({"ok": False, "reason": str(exc)}, indent=2, sort_keys=True))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
