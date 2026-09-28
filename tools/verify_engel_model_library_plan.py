from __future__ import annotations

import json
import re
import sys
from pathlib import Path


_file = globals().get("__file__")
if not _file or not isinstance(_file, str) or _file.startswith("<"):
    ROOT = Path.cwd()
else:
    try:
        ROOT = Path(_file).resolve().parents[1]
    except (OSError, ValueError, IndexError):
        ROOT = Path.cwd()

JSON_PATH = ROOT / "memory" / "ENGEL_MODEL_LIBRARY_PLAN_V1.json"
MD_PATH = ROOT / "memory" / "ENGEL_MODEL_LIBRARY_PLAN_V1.md"
PRESENCE_HELPER_PATH = ROOT / "tools" / "engel_model_library_presence_status.py"
PRESENCE_VERIFIER_PATH = ROOT / "tools" / "verify_engel_model_library_presence_status.py"

REQUIRED_TIERS = {
    "Tiny Seed Mode": "Qwen2.5-0.5B-Instruct GGUF",
    "Daily Local Mode": "Qwen2.5-3B-Instruct GGUF",
    "Research Worker Mode": "Qwen2.5-7B-Instruct GGUF",
    "Alternative Research Worker": "Mistral-7B-Instruct v0.3 GGUF",
}

FALSE_MODEL_FLAGS = [
    "startup_auto_load_allowed",
    "trusted_memory_write_allowed",
    "network_download_allowed",
    "auto_download_allowed",
    "provider_api_allowed",
    "browser_api_allowed",
    "model_runtime_call_allowed",
    "inference_allowed_in_this_phase",
]

FALSE_ROOT_FLAGS = [
    "network_download_allowed",
    "auto_download_allowed",
    "provider_api_allowed",
    "browser_api_allowed",
    "model_runtime_call_allowed",
    "inference_allowed_in_this_phase",
    "startup_auto_load_allowed",
    "trusted_memory_write_allowed",
    "project_memory_write_allowed",
    "queue_mutation_allowed",
    "route_mutation_allowed",
    "background_workers_allowed",
]

LOCAL_STATUS_VALUES = {"present", "missing", "unknown", "split_present", "split_partial"}
MANUAL_PRESENCE_STATUS_VALUES = {
    "PRESENT / NOT_LOADED / NOT_RUNTIME",
    "MISSING / NOT_LOADED / NOT_RUNTIME",
    "UNKNOWN / NOT_LOADED / NOT_RUNTIME",
    "SPLIT_PRESENT / NOT_MERGED / NOT_LOADED / NOT_RUNTIME",
    "SPLIT_PARTIAL / NOT_MERGED / NOT_LOADED / NOT_RUNTIME",
    "MISSING / NOT_MERGED / NOT_LOADED / NOT_RUNTIME",
    "PRESENT / MERGED / NOT_LOADED / NOT_RUNTIME",
    "MISSING / MERGED_FILE_NOT_FOUND / NOT_LOADED / NOT_RUNTIME",
}


class CheckFailure(Exception):
    pass


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _read_text(path: Path) -> str:
    if not path.exists():
        raise CheckFailure("missing required file: " + _rel(path))
    return path.read_text(encoding="utf-8", errors="replace")


def _load_json(path: Path) -> dict:
    try:
        data = json.loads(_read_text(path))
    except json.JSONDecodeError as exc:
        raise CheckFailure("manifest JSON is invalid: " + str(exc)) from exc
    if not isinstance(data, dict):
        raise CheckFailure("manifest JSON must be an object")
    return data


def _normalize_path_text(value: str) -> str:
    return value.replace("/", "\\").strip()


def _is_local_path(value: str) -> bool:
    text = _normalize_path_text(value)
    if not text:
        return False
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", text):
        return False
    if text.startswith("\\\\"):
        return False
    parts = [part for part in text.split("\\") if part]
    if ".." in parts:
        return False
    if re.match(r"^[A-Za-z]:\\", text):
        return True
    return False


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def _assert_root_manifest(data: dict) -> None:
    _require(data.get("schema") == "ENGEL_MODEL_LIBRARY_PLAN_V1", "schema mismatch")
    status = str(data.get("status", ""))
    for phrase in ["LOCAL_MODEL_LIBRARY_PLAN", "NOT_TRUSTED_MEMORY", "NOT_DOWNLOADED", "NOT_LOADED", "NOT_APPLIED"]:
        _require(phrase in status, "status missing " + phrase)
    _require(data.get("runtime_effect") == "READ_ONLY_PLAN_STATUS_ONLY", "runtime effect must be read-only status only")
    _require(data.get("manual_presence_status") == "READ_ONLY_STATUS_ONLY / NOT_LOADED / NOT_RUNTIME", "manual presence status mismatch")
    _require(data.get("presence_helper_path") == r"tools\engel_model_library_presence_status.py", "presence helper path mismatch")
    _require(data.get("presence_verifier_path") == r"tools\verify_engel_model_library_presence_status.py", "presence verifier path mismatch")
    _require(PRESENCE_HELPER_PATH.exists(), "presence helper missing")
    _require(PRESENCE_VERIFIER_PATH.exists(), "presence verifier missing")
    _require(data.get("content_boundary") == "DATA_CONFIG_NOT_INSTRUCTION", "content boundary mismatch")
    _require(data.get("future_model_files_trust_status") == "UNTRUSTED_QUARANTINED_UNTIL_HUMAN_APPROVAL", "future model trust status mismatch")
    _require(data.get("actual_model_downloads") == "MANUAL_HUMAN_APPROVED_ONLY", "manual download boundary missing")
    _require(data.get("trusted_memory_write") == "BLOCKED / NOT_PERFORMED", "trusted memory write boundary mismatch")
    _require(data.get("human_approval_required") is True, "human approval must be required")
    for flag in FALSE_ROOT_FLAGS:
        _require(data.get(flag) is False, "root flag must be false: " + flag)


def _collect_folder_paths(folder_layout: object) -> list[str]:
    if not isinstance(folder_layout, dict):
        raise CheckFailure("folder_layout must be an object")
    paths: list[str] = []
    for key in [
        "library_root",
        "models_root",
        "quarantine_imports",
        "approved_library",
        "research_papers",
        "docs",
        "engel_reports",
    ]:
        value = folder_layout.get(key)
        if not isinstance(value, str):
            raise CheckFailure("folder_layout missing string path: " + key)
        paths.append(value)
    model_folders = folder_layout.get("model_folders")
    if not isinstance(model_folders, dict):
        raise CheckFailure("folder_layout missing model_folders")
    for key, value in model_folders.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise CheckFailure("model_folders must contain string keys and paths")
        paths.append(value)
    return paths


def _assert_folder_layout(data: dict) -> None:
    folder_layout = data.get("folder_layout")
    paths = _collect_folder_paths(folder_layout)
    for value in paths:
        _require(_is_local_path(value), "folder path is not a bounded local drive path: " + value)
    layout = folder_layout if isinstance(folder_layout, dict) else {}
    _require("quarantine_imports" in layout, "quarantine_imports missing from plan")
    _require("approved_library" in layout, "approved_library missing from plan")


def _assert_models(data: dict) -> None:
    models = data.get("models")
    if not isinstance(models, list):
        raise CheckFailure("models must be a list")
    by_tier = {str(model.get("tier")): model for model in models if isinstance(model, dict)}
    for tier, display_name in REQUIRED_TIERS.items():
        model = by_tier.get(tier)
        if not isinstance(model, dict):
            raise CheckFailure("missing model tier: " + tier)
        _require(model.get("model_display_name") == display_name, "model display name mismatch for " + tier)
        _require(model.get("human_approval_required") is True, "human approval missing for " + tier)
        for flag in FALSE_MODEL_FLAGS:
            _require(model.get(flag) is False, "model flag must be false for " + tier + ": " + flag)
        local_status = model.get("local_file_status")
        _require(local_status in LOCAL_STATUS_VALUES, "bad local_file_status for " + tier)
        manual_presence_status = model.get("manual_presence_status")
        _require(manual_presence_status in MANUAL_PRESENCE_STATUS_VALUES, "bad manual_presence_status for " + tier)
        folder = model.get("expected_local_folder")
        _require(isinstance(folder, str) and _is_local_path(folder), "model folder must be local for " + tier)
        expected_files = model.get("expected_files")
        _require(isinstance(expected_files, list) and bool(expected_files), "expected_files missing for " + tier)
        for name in expected_files:
            _require(isinstance(name, str) and name.endswith(".gguf"), "expected file must be .gguf for " + tier)
            _require("\\" not in name and "/" not in name and ".." not in name, "expected file must be a filename only for " + tier)
        split_required = model.get("split_file_set_required")
        _require(isinstance(split_required, bool), "split_file_set_required must be boolean for " + tier)
        if tier == "Research Worker Mode":
            _require(split_required is False, "Research Worker Mode should use merged primary file")
            _require(model.get("merged_file_required") is True, "Research Worker Mode should require merged file")
            _require(expected_files == ["qwen2.5-7b-instruct-q5_k_m.gguf"], "Research Worker Mode merged file mismatch")
            retained_split_files = model.get("retained_split_files")
            _require(isinstance(retained_split_files, list) and len(retained_split_files) == 2, "Research Worker Mode should retain two split file references")
            _require(model.get("merge_performed_by_engel_codex") is False, "Research Worker Mode merge must not be performed by Engel/Codex")
            _require(model.get("manual_merge_status") == "MERGED_BY_JOSH_OUTSIDE_ENGEL_CODEX", "Research Worker Mode manual merge status mismatch")
            _require(local_status == "present", "Research Worker Mode should be present")
            _require(manual_presence_status == "PRESENT / MERGED / NOT_LOADED / NOT_RUNTIME", "Research Worker Mode merged status mismatch")
        else:
            _require(split_required is False, "single-file model should not require split file set for " + tier)
            _require(local_status == "present", "single-file model should be present for " + tier)
            _require(manual_presence_status == "PRESENT / NOT_LOADED / NOT_RUNTIME", "single-file model presence status mismatch for " + tier)
        quant = model.get("recommended_quantization")
        _require(isinstance(quant, list) and bool(quant), "recommended quantization missing for " + tier)
        _require(model.get("trust_status") == "UNTRUSTED_QUARANTINED_UNTIL_HUMAN_APPROVAL", "model trust boundary mismatch for " + tier)


def _assert_markdown(text: str) -> None:
    normalized = " ".join(text.lower().replace("\\", "/").split())
    for phrase in [
        "engel model library plan v1",
        "local_model_library_plan / not_trusted_memory / manual_downloads_present / not_downloaded_by_engel_codex / not_loaded / not_applied",
        "actual model downloads remain manual/human-approved",
        "josh manually downloaded the listed shelf files outside engel/codex",
        "read_only_status_only / not_loaded / not_runtime",
        "tools/engel_model_library_presence_status.py",
        "tools/verify_engel_model_library_presence_status.py",
        "present / not_loaded / not_runtime",
        "present / merged / not_loaded / not_runtime",
        "manually merged by josh outside engel/codex",
        "split files still exist and should not be deleted",
        "g:/engel_app_memory/models/manual_downloads",
        "presence is shelf status only and never grants permission to load or infer",
        "qwen2.5-0.5b-instruct gguf",
        "qwen2.5-3b-instruct gguf",
        "qwen2.5-7b-instruct gguf",
        "mistral-7b-instruct v0.3 gguf",
        "quarantine_imports",
        "approved_library",
        "startup auto-load allowed: false",
        "network/download allowed: false",
        "inference allowed in this phase: false",
        "trusted-memory write allowed: false",
        "no provider/api/network/browser behavior is allowed",
        "manual model file presence does not enable model runtime",
        "no queue, route, provider, or source behavior is changed by this plan",
    ]:
        if phrase.lower().replace("\\", "/") not in normalized:
            raise CheckFailure("markdown missing phrase: " + phrase)


def main() -> int:
    data = _load_json(JSON_PATH)
    _assert_root_manifest(data)
    _assert_folder_layout(data)
    _assert_models(data)
    _assert_markdown(_read_text(MD_PATH))
    print("PASS: Engel Model Library Plan V1 verifier")
    print("- manifest JSON is valid")
    print("- all four model tiers are present")
    print("- auto-load, network/download, model runtime calls, and inference are disabled")
    print("- trusted-memory writes are disabled")
    print("- library folders are local drive paths")
    print("- quarantine_imports and approved_library are included")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CheckFailure as exc:
        print("FAIL: " + str(exc), file=sys.stderr)
        raise SystemExit(1)
