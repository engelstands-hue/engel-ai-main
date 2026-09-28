from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
APPROVAL_MANIFEST = PROJECT_ROOT / "reports" / "ai_model_review_approvals" / "manifests" / "engel_ai_model_review_approval_manifest.json"
OFFLINE_RUNTIME_CONTRACT = PROJECT_ROOT / "memory" / "ENGEL_OFFLINE_MODEL_RUNTIME_CONTRACT_V1.json"
LOCAL_RUNTIME_PATH_CONFIG = PROJECT_ROOT / "reports" / "ai_runtime_path_config" / "manifests" / "engel_ai_local_runtime_path_config_manifest.json"
REPORT_ROOT = PROJECT_ROOT / "reports" / "ai_runtime_dry_runs"
RECEIPT_DIR = REPORT_ROOT / "receipts"
CONFIG_DIR = REPORT_ROOT / "configs"
EXAMPLES_DIR = REPORT_ROOT / "examples"
DRY_RUN_MANIFEST = CONFIG_DIR / "engel_ai_runtime_dry_run_manifest.json"

MAX_READ_CHARS = 200_000
FINAL_DECISION_READY = "RUNTIME DRY-RUN RECORDED — MODEL NOT LOADED — NO INFERENCE"
FINAL_DECISION_BLOCKED = "RUNTIME DRY-RUN BLOCKED — RUNTIME BINARY NOT CONFIGURED — MODEL NOT LOADED — NO INFERENCE"

MODEL_KEY_TO_TIER = {
    "tiny_seed": "Tiny Seed Mode",
    "daily_local": "Daily Local Mode",
    "research_worker": "Research Worker Mode",
    "alternative_research_worker": "Alternative Research Worker",
}


class RuntimeDryRunError(ValueError):
    pass


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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
    return (slug or "runtime_dry_run")[:max_length]


def safe_stamp(value: str) -> str:
    return value.replace(":", "").replace("-", "").replace("+00:00", "Z")


def write_lf_text(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def ensure_folders() -> None:
    for folder in [REPORT_ROOT, RECEIPT_DIR, CONFIG_DIR, EXAMPLES_DIR]:
        folder.mkdir(parents=True, exist_ok=True)


def project_relative(path: Path) -> str:
    try:
        return str(path.resolve(strict=False).relative_to(PROJECT_ROOT.resolve(strict=False))).replace("/", "\\")
    except ValueError:
        return str(path.resolve(strict=False))


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace")[:MAX_READ_CHARS])
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def approval_entries() -> list[dict[str, Any]]:
    entries = read_json(APPROVAL_MANIFEST).get("entries")
    if not isinstance(entries, list):
        return []
    return [entry for entry in entries if isinstance(entry, dict)]


def model_key_for_tier(tier: str) -> str | None:
    for key, mapped_tier in MODEL_KEY_TO_TIER.items():
        if mapped_tier == tier:
            return key
    return None


def approval_entry_for_key(model_key: str) -> dict[str, Any] | None:
    tier = MODEL_KEY_TO_TIER.get(model_key)
    if not tier:
        return None
    for entry in approval_entries():
        if entry.get("model_tier") == tier:
            return entry
    return None


def approval_entry_for_receipt(path_text: str) -> dict[str, Any] | None:
    path = Path(path_text)
    resolved = path if path.is_absolute() else PROJECT_ROOT / path
    try:
        resolved.resolve(strict=False).relative_to((PROJECT_ROOT / "reports" / "ai_model_review_approvals").resolve(strict=False))
    except ValueError:
        return None
    data = read_json(resolved)
    return data if data.get("model_review_approval_version") == "1" else None


def latest_dry_run_entries_by_key() -> dict[str, dict[str, Any]]:
    data = read_json(DRY_RUN_MANIFEST)
    entries = data.get("entries")
    if not isinstance(entries, list):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if isinstance(entry, dict) and isinstance(entry.get("model_key"), str):
            result[entry["model_key"]] = entry
    return result


def runtime_contract() -> dict[str, Any]:
    return read_json(OFFLINE_RUNTIME_CONTRACT)


def runtime_path_config() -> dict[str, Any]:
    return read_json(LOCAL_RUNTIME_PATH_CONFIG)


def configured_runtime_binary_path() -> str | None:
    path_config = runtime_path_config()
    configured_path = path_config.get("runtime_binary_path")
    if path_config.get("runtime_path_approved") is True and isinstance(configured_path, str) and configured_path.strip():
        return configured_path.strip()
    contract = runtime_contract()
    candidate_keys = [
        "runtime_binary_path",
        "llama_cli_path",
        "llama_cpp_cli_path",
        "llama_cpp_binary_path",
        "local_runtime_binary_path",
    ]
    for key in candidate_keys:
        value = contract.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    candidates = contract.get("runtime_binary_candidates")
    if isinstance(candidates, list):
        for value in candidates:
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def runtime_status() -> dict[str, Any]:
    configured = configured_runtime_binary_path()
    path_config = runtime_path_config()
    if configured:
        binary_path = Path(configured)
        present = binary_path.exists() and binary_path.is_file()
        if path_config.get("runtime_path_approved") is True:
            backend = str(path_config.get("runtime_backend") or "llama_cpp")
        else:
            backend = "llama_cpp_candidate"
    else:
        binary_path = None
        present = False
        backend = "not_configured"
    return {
        "runtime_backend": backend,
        "runtime_binary_path": str(binary_path.resolve(strict=False)) if binary_path else None,
        "runtime_binary_present": present,
        "runtime_contract_present": OFFLINE_RUNTIME_CONTRACT.exists(),
        "runtime_path_config_present": LOCAL_RUNTIME_PATH_CONFIG.exists(),
        "runtime_path_approved": bool(path_config.get("runtime_path_approved") is True),
        "runtime_process_start_enabled": False,
        "inference_enabled": False,
        "model_load_enabled": False,
        "provider_api_enabled": False,
    }


def validate_approval_entry(entry: dict[str, Any] | None) -> dict[str, Any]:
    if not entry:
        return {"valid": False, "reason": "model_approval_missing"}
    model_path = Path(str(entry.get("model_file_path", "")))
    model_key = model_key_for_tier(str(entry.get("model_tier", "")))
    if not model_key:
        return {"valid": False, "reason": "unknown_model_tier"}
    if entry.get("approved_for_runtime_dry_run") is not True:
        return {"valid": False, "reason": "not_approved_for_runtime_dry_run", "model_key": model_key}
    if entry.get("runtime_dry_run_eligible") is not True:
        return {"valid": False, "reason": "not_runtime_dry_run_eligible", "model_key": model_key}
    if entry.get("inference_enabled") is True or entry.get("auto_load_enabled") is True:
        return {"valid": False, "reason": "unsafe_approval_flags", "model_key": model_key}
    if not model_path.exists() or not model_path.is_file():
        return {"valid": False, "reason": "model_file_missing", "model_key": model_key, "model_file_path": str(model_path)}
    if model_path.suffix.lower() != ".gguf":
        return {"valid": False, "reason": "non_gguf_model_rejected", "model_key": model_key, "model_file_path": str(model_path)}
    return {
        "valid": True,
        "reason": "valid_runtime_dry_run_model",
        "model_key": model_key,
        "model_tier": entry.get("model_tier"),
        "model_name": entry.get("model_name"),
        "model_file_path": str(model_path.resolve(strict=False)),
        "model_approval_receipt": entry.get("receipt_path"),
        "approval_entry": entry,
    }


def validate_model(reference: str) -> dict[str, Any]:
    if reference in MODEL_KEY_TO_TIER:
        return validate_approval_entry(approval_entry_for_key(reference))
    return validate_approval_entry(approval_entry_for_receipt(reference))


def command_preview_for(model_path: str, runtime: dict[str, Any]) -> str:
    executable = runtime.get("runtime_binary_path") or "llama-cli"
    return f'COMMAND PREVIEW ONLY — NOT EXECUTED\n{executable} --model "{model_path}" --ctx-size <placeholder> --threads <placeholder> --n-predict 0'


def build_config_preview(model_key: str) -> dict[str, Any]:
    validation = validate_model(model_key)
    if not validation["valid"]:
        raise RuntimeDryRunError(str(validation["reason"]))
    runtime = runtime_status()
    model_path = str(validation["model_file_path"])
    return {
        "runtime_config_preview_version": "1",
        "created_by": "Engel AI Offline Runtime Dry Run",
        "model_key": model_key,
        "model_tier": validation["model_tier"],
        "model_name": validation["model_name"],
        "model_file_path": model_path,
        "runtime_backend": runtime["runtime_backend"],
        "runtime_binary_path": runtime["runtime_binary_path"],
        "runtime_binary_present": runtime["runtime_binary_present"],
        "context_size": "<placeholder>",
        "threads": "<placeholder>",
        "gpu_layers": "<placeholder>",
        "n_predict": 0,
        "command_preview": command_preview_for(model_path, runtime),
        "command_preview_label": "COMMAND PREVIEW ONLY — NOT EXECUTED",
        "inference_enabled": False,
        "model_load_enabled": False,
        "process_start_enabled": False,
        "provider_api_enabled": False,
        "trusted_memory_write_enabled": False,
    }


def approval_receipt_path_for_entry(entry: dict[str, Any]) -> str | None:
    target = str(entry.get("model_file_path", ""))
    receipt_path = entry.get("receipt_path")
    if isinstance(receipt_path, str) and receipt_path:
        return receipt_path
    receipt_root = PROJECT_ROOT / "reports" / "ai_model_review_approvals" / "receipts"
    if not receipt_root.exists():
        return None
    for receipt in sorted(receipt_root.iterdir()):
        if not receipt.is_file() or receipt.suffix.lower() != ".json":
            continue
        data = read_json(receipt)
        if data.get("model_file_path") == target:
            return project_relative(receipt)
    return None


def build_dry_run_receipt(model_key: str, *, created_at: str | None = None) -> dict[str, Any]:
    validation = validate_model(model_key)
    if not validation["valid"]:
        raise RuntimeDryRunError(str(validation["reason"]))
    approval_entry = validation["approval_entry"]
    runtime = runtime_status()
    config = build_config_preview(model_key)
    ready = bool(runtime["runtime_binary_present"])
    final_decision = FINAL_DECISION_READY if ready else FINAL_DECISION_BLOCKED
    return {
        "runtime_dry_run_version": "1",
        "created_at": created_at or now_utc(),
        "created_by": "Engel AI Offline Runtime Dry Run",
        "model_key": model_key,
        "model_tier": validation["model_tier"],
        "model_name": validation["model_name"],
        "model_file_path": validation["model_file_path"],
        "model_approval_receipt": approval_receipt_path_for_entry(approval_entry),
        "approved_for_runtime_dry_run": True,
        "runtime_dry_run_completed": True,
        "runtime_dry_run_ready": ready,
        "runtime_ready": False,
        "approved_for_runtime": False,
        "inference_enabled": False,
        "auto_load_enabled": False,
        "model_loaded": False,
        "process_started": False,
        "command_executed": False,
        "provider_api_enabled": False,
        "trusted_memory_write_enabled": False,
        "runtime_backend": runtime["runtime_backend"],
        "runtime_binary_path": runtime["runtime_binary_path"],
        "runtime_binary_present": runtime["runtime_binary_present"],
        "runtime_contract_present": runtime["runtime_contract_present"],
        "command_preview": config["command_preview"],
        "config_preview": config,
        "final_decision": final_decision,
    }


def empty_manifest() -> dict[str, Any]:
    return {
        "manifest_version": "1",
        "created_by": "Engel AI Offline Runtime Dry Run",
        "updated_at": None,
        "entry_count": 0,
        "entries": [],
        "safety": {
            "inference_enabled": False,
            "model_load_enabled": False,
            "runtime_process_start_enabled": False,
            "provider_api_enabled": False,
            "trusted_memory_write_enabled": False,
            "source_route_queue_mutation": False,
        },
    }


def load_manifest() -> dict[str, Any]:
    data = read_json(DRY_RUN_MANIFEST)
    return data if data else empty_manifest()


def write_manifest(entries: list[dict[str, Any]], *, updated_at: str | None = None) -> Path:
    ensure_folders()
    by_key: dict[str, dict[str, Any]] = {}
    for entry in entries:
        by_key[str(entry.get("model_key"))] = entry
    rows = [by_key[key] for key in MODEL_KEY_TO_TIER if key in by_key]
    payload = empty_manifest()
    payload["updated_at"] = updated_at or now_utc()
    payload["entries"] = rows
    payload["entry_count"] = len(rows)
    write_lf_text(DRY_RUN_MANIFEST, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return DRY_RUN_MANIFEST


def update_manifest_with(entry: dict[str, Any]) -> Path:
    entries = [item for item in load_manifest().get("entries", []) if isinstance(item, dict)]
    entries = [item for item in entries if item.get("model_key") != entry.get("model_key")]
    entries.append(entry)
    return write_manifest(entries, updated_at=str(entry["created_at"]))


def render_receipt_markdown(entry: dict[str, Any]) -> str:
    lines = [
        "# Engel AI Offline Runtime Dry-Run Receipt",
        "",
        f"- timestamp: `{entry['created_at']}`",
        f"- model_key: `{entry['model_key']}`",
        f"- model_tier: `{entry['model_tier']}`",
        f"- model_name: `{entry['model_name']}`",
        f"- model_file_path: `{entry['model_file_path']}`",
        f"- approved_for_runtime_dry_run: `{entry['approved_for_runtime_dry_run']}`",
        f"- runtime_dry_run_completed: `{entry['runtime_dry_run_completed']}`",
        f"- runtime_dry_run_ready: `{entry['runtime_dry_run_ready']}`",
        f"- runtime_ready: `{entry['runtime_ready']}`",
        f"- inference_enabled: `{entry['inference_enabled']}`",
        f"- auto_load_enabled: `{entry['auto_load_enabled']}`",
        f"- model_loaded: `{entry['model_loaded']}`",
        f"- process_started: `{entry['process_started']}`",
        f"- command_executed: `{entry['command_executed']}`",
        f"- runtime_backend: `{entry['runtime_backend']}`",
        f"- runtime_binary_path: `{entry['runtime_binary_path']}`",
        f"- runtime_binary_present: `{entry['runtime_binary_present']}`",
        f"- final_decision: `{entry['final_decision']}`",
        "",
        "COMMAND PREVIEW ONLY — NOT EXECUTED",
        "",
        "```text",
        str(entry["command_preview"]),
        "```",
        "",
        "Runtime dry-run only. No model was loaded, no runtime process was started, and no inference was run.",
    ]
    return "\n".join(lines) + "\n"


def write_dry_run_artifacts(entry: dict[str, Any]) -> dict[str, str]:
    ensure_folders()
    stamp = safe_stamp(str(entry["created_at"]))
    stem = f"RUNTIME_DRY_RUN_{stamp}_{safe_slug(str(entry['model_key']))}_{safe_slug(str(entry['model_tier']))}"
    receipt_json = RECEIPT_DIR / f"{stem}.json"
    receipt_md = RECEIPT_DIR / f"{stem}.md"
    config_json = CONFIG_DIR / f"{stem}_config_preview.json"
    config_md = CONFIG_DIR / f"{stem}_command_preview.md"
    write_lf_text(receipt_json, json.dumps(entry, indent=2, sort_keys=True) + "\n")
    write_lf_text(receipt_md, render_receipt_markdown(entry))
    write_lf_text(config_json, json.dumps(entry["config_preview"], indent=2, sort_keys=True) + "\n")
    write_lf_text(
        config_md,
        "# Engel AI Runtime Command Preview\n\nCOMMAND PREVIEW ONLY — NOT EXECUTED\n\n```text\n"
        + str(entry["command_preview"])
        + "\n```\n\nNo model was loaded. No process was started. No inference was run.\n",
    )
    manifest_path = update_manifest_with(entry)
    return {
        "receipt_json": project_relative(receipt_json),
        "receipt_markdown": project_relative(receipt_md),
        "config_json": project_relative(config_json),
        "config_markdown": project_relative(config_md),
        "manifest_path": project_relative(manifest_path),
    }


def dry_run_model(model_key: str, *, created_at: str | None = None) -> dict[str, Any]:
    entry = build_dry_run_receipt(model_key, created_at=created_at)
    artifacts = write_dry_run_artifacts(entry)
    return {"dry_run_status": "recorded", "entry": entry, **artifacts}


def dry_run_all() -> dict[str, Any]:
    created_at = now_utc()
    results: list[dict[str, Any]] = []
    for model_key in MODEL_KEY_TO_TIER:
        try:
            results.append(dry_run_model(model_key, created_at=created_at))
        except RuntimeDryRunError as exc:
            results.append({"model_key": model_key, "dry_run_status": "not_recorded", "reason": str(exc)})
    return {"runtime_dry_run_all_version": "1", "results": results}


def list_models_payload() -> list[dict[str, Any]]:
    dry_runs = latest_dry_run_entries_by_key()
    rows: list[dict[str, Any]] = []
    for model_key, tier in MODEL_KEY_TO_TIER.items():
        entry = approval_entry_for_key(model_key)
        validation = validate_approval_entry(entry)
        dry_run = dry_runs.get(model_key)
        rows.append(
            {
                "model_key": model_key,
                "model_tier": tier,
                "model_name": entry.get("model_name") if entry else None,
                "model_file_path": entry.get("model_file_path") if entry else None,
                "approved_for_runtime_dry_run": bool(entry and entry.get("approved_for_runtime_dry_run") is True),
                "validation_status": validation["reason"],
                "runtime_dry_run_receipt_present": dry_run is not None,
                "runtime_dry_run_ready": bool(dry_run and dry_run.get("runtime_dry_run_ready") is True),
                "runtime_binary_present": bool(dry_run and dry_run.get("runtime_binary_present") is True),
                "runtime_ready": False,
                "inference_enabled": False,
                "auto_load_enabled": False,
            }
        )
    return rows


def status_payload() -> dict[str, Any]:
    ensure_folders()
    receipts = [path for path in RECEIPT_DIR.glob("*.json") if path.is_file()] if RECEIPT_DIR.exists() else []
    configs = [path for path in CONFIG_DIR.glob("*.json") if path.is_file()] if CONFIG_DIR.exists() else []
    runtime = runtime_status()
    return {
        "offline_runtime_dry_run_status_version": "1",
        "mode": "runtime_wiring_dry_run_only",
        "folders": {
            "root": project_relative(REPORT_ROOT),
            "receipts": project_relative(RECEIPT_DIR),
            "configs": project_relative(CONFIG_DIR),
            "examples": project_relative(EXAMPLES_DIR),
        },
        "approval_manifest_present": APPROVAL_MANIFEST.exists(),
        "approved_models_count": len(approval_entries()),
        "receipt_count": len(receipts),
        "config_count": len(configs),
        "runtime_adapter_status": runtime,
        "safety_flags": {
            "inference_enabled": False,
            "model_load_enabled": False,
            "runtime_process_start_enabled": False,
            "provider_api_enabled": False,
            "download_enabled": False,
            "trusted_memory_write_enabled": False,
            "source_route_queue_mutation": False,
        },
    }


def render_status() -> str:
    data = status_payload()
    runtime = data["runtime_adapter_status"]
    lines = [
        "Engel AI Offline Runtime Dry Run V1",
        "Mode: runtime wiring dry-run only; no model load and no inference",
        "",
        f"approval_manifest_present: {data['approval_manifest_present']}",
        f"approved_models_count: {data['approved_models_count']}",
        f"receipts: {data['receipt_count']}",
        f"configs: {data['config_count']}",
        f"runtime_backend: {runtime['runtime_backend']}",
        f"runtime_binary_path: {runtime['runtime_binary_path']}",
        f"runtime_binary_present: {runtime['runtime_binary_present']}",
        "",
        "Safety:",
    ]
    lines.extend(f"- {key}: {value}" for key, value in data["safety_flags"].items())
    return "\n".join(lines) + "\n"


def render_list_models() -> str:
    lines = ["Engel AI Offline Runtime Dry-Run Models", ""]
    for row in list_models_payload():
        lines.append(
            f"- {row['model_key']}: {row['model_tier']} / approved={row['approved_for_runtime_dry_run']} / "
            f"dry_run_ready={row['runtime_dry_run_ready']} / inference={row['inference_enabled']} / "
            f"path={row['model_file_path']}"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Engel AI Offline Runtime Dry Run V1")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status")
    subparsers.add_parser("list-models")
    validate_parser = subparsers.add_parser("validate-model")
    validate_parser.add_argument("model_reference")
    preview_parser = subparsers.add_parser("preview")
    preview_parser.add_argument("model_key")
    dry_parser = subparsers.add_parser("dry-run")
    dry_parser.add_argument("model_key")
    subparsers.add_parser("dry-run-all")
    subparsers.add_parser("json")
    args = parser.parse_args(argv)

    try:
        if args.command == "status":
            print(render_status(), end="")
        elif args.command == "list-models":
            ensure_folders()
            print(render_list_models(), end="")
        elif args.command == "validate-model":
            print(json.dumps(validate_model(args.model_reference), indent=2, sort_keys=True))
        elif args.command == "preview":
            print(json.dumps(build_config_preview(args.model_key), indent=2, sort_keys=True))
        elif args.command == "dry-run":
            print(json.dumps(dry_run_model(args.model_key), indent=2, sort_keys=True))
        elif args.command == "dry-run-all":
            print(json.dumps(dry_run_all(), indent=2, sort_keys=True))
        elif args.command == "json":
            payload = status_payload()
            payload["models"] = list_models_payload()
            payload["dry_run_manifest"] = load_manifest()
            print(json.dumps(payload, indent=2, sort_keys=True))
    except RuntimeDryRunError as exc:
        print(json.dumps({"ok": False, "reason": str(exc)}, indent=2, sort_keys=True))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
