from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import engel_large_chat_llm as large_chat  # noqa: E402

MANIFEST_PATH = ROOT / "memory" / "models" / "ENGEL_LARGE_CHAT_LLM_MANIFEST.json"
RUNNER_PATH = ROOT / "engel_llama_cli_runner.py"
STANDALONE_PATH = ROOT / "tools" / "run_engel_standalone_chat_llm.py"
CONFIG_PATH = ROOT / "memory" / "personality" / "ENGEL_CHAT_PROVIDER_CONFIG.json"
LATEST_REPORT = ROOT / "runtime" / "engel_large_chat_llm_verifier_latest.json"


def add_check(checks: list[dict[str, Any]], name: str, ok: bool, detail: str = "") -> None:
    checks.append({"name": name, "ok": bool(ok), "detail": detail})


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    if path.drive.lower() == "c:":
        raise RuntimeError(f"refusing verifier write on C: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    checks: list[dict[str, Any]] = []
    manifest = read_json(MANIFEST_PATH)
    status = large_chat.large_chat_model_status()
    runner_source = RUNNER_PATH.read_text(encoding="utf-8", errors="replace")
    standalone_source = STANDALONE_PATH.read_text(encoding="utf-8", errors="replace")
    module_source = (ROOT / "engel_large_chat_llm.py").read_text(encoding="utf-8", errors="replace")
    config = read_json(CONFIG_PATH)

    add_check(checks, "manifest_exists", MANIFEST_PATH.exists(), str(MANIFEST_PATH))
    add_check(checks, "manifest_schema", manifest.get("schema") == "engel_large_chat_llm_manifest_v1", str(manifest.get("schema")))
    add_check(checks, "manifest_has_no_fixed_size_gate", int(manifest.get("minimum_model_bytes") or 0) == 0, str(manifest.get("minimum_model_bytes")))
    add_check(checks, "manifest_no_auto_download", manifest.get("download_enabled") is False, str(manifest.get("download_enabled")))
    add_check(checks, "manifest_no_provider_calls", manifest.get("provider_calls_enabled") is False, str(manifest.get("provider_calls_enabled")))
    add_check(checks, "manifest_no_runpod_api", manifest.get("runpod_api_enabled") is False, str(manifest.get("runpod_api_enabled")))
    add_check(checks, "store_not_os_drive", str(status.get("model_store_root_os_drive")) == "False", str(status.get("model_store_root")))
    add_check(checks, "store_has_required_capacity", status.get("model_store_has_required_free") is True or status.get("selected_model_present") is True, str(status.get("model_store_free_gib")))
    add_check(checks, "status_network_disabled", status.get("network_enabled") is False, str(status.get("network_enabled")))
    add_check(checks, "status_provider_disabled", status.get("provider_calls_enabled") is False, str(status.get("provider_calls_enabled")))
    add_check(checks, "status_server_disabled", status.get("server_enabled") is False, str(status.get("server_enabled")))
    add_check(checks, "status_trusted_memory_write_disabled", status.get("trusted_memory_write_enabled") is False, str(status.get("trusted_memory_write_enabled")))
    add_check(checks, "module_no_network_imports", all(term not in module_source for term in ["import urllib", "import requests", "import socket", "http.client"]), "network imports absent")
    add_check(checks, "module_uses_llama_cli_single_turn", "_build_chat_cmd" in module_source and "run_large_chat_with_llama_cli" in module_source, "llama.cpp bounded path")
    add_check(checks, "runner_prefers_large_model", "select_large_chat_model" in runner_source, "engel_llama_cli_runner.py")
    add_check(checks, "standalone_has_large_local_attempt", "run_large_local_chat_if_available" in standalone_source, "standalone bridge")
    add_check(checks, "standalone_extracts_text_field", "container.get(\"text\")" in standalone_source, "extract_local_reply supports llama-cli text")
    add_check(
        checks,
        "chat_config_browser_bridge_enabled",
        config.get("chatgpt_browser_for_natural_chat") is True
        and config.get("prefer_chatgpt_browser_over_api") is True
        and config.get("fallback_to_local_on_browser_error") is True,
        str(
            {
                k: config.get(k)
                for k in [
                    "chatgpt_browser_for_natural_chat",
                    "prefer_chatgpt_browser_over_api",
                    "fallback_to_local_on_browser_error",
                ]
            }
        ),
    )
    add_check(
        checks,
        "chat_config_selected_chat_auto_or_local",
        str(config.get("selected_chat_provider") or "").lower() in {"auto", "local"},
        str(config.get("selected_chat_provider")),
    )

    selected_total = int(status.get("selected_model_total_bytes") or 0)
    if status.get("selected_model_present"):
        add_check(checks, "selected_model_has_weight_file", selected_total > 0, str(status.get("selected_model_total_gib")))
        add_check(checks, "selected_model_path_exists", Path(str(status.get("selected_model_path"))).exists(), str(status.get("selected_model_path")))
    else:
        add_check(checks, "selected_model_not_required_for_readiness", True, "no fixed minimum GGUF size is required")

    ok = all(check["ok"] for check in checks)
    payload = {
        "schema": "engel_large_chat_llm_verifier_v1",
        "ok": ok,
        "checks": checks,
        "large_chat_llm_status": status,
        "report_path": str(LATEST_REPORT),
    }
    write_json(LATEST_REPORT, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
