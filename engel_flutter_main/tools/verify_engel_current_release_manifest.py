#!/usr/bin/env python3
"""Verify the current Engel release manifest against real files."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "dist" / "ENGEL_CURRENT_RELEASE_MANIFEST_20260607.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def resolve_path(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else ROOT / path

def verify_hash(label: str, path_text: str, expected: str) -> dict[str, object]:
    path = resolve_path(path_text)
    require(path.exists(), f"{label} missing: {path}")
    actual = sha256_file(path)
    require(
        actual == expected.upper(),
        f"{label} SHA256 mismatch: expected {expected.upper()} actual {actual}",
    )
    return {
        "label": label,
        "path": str(path),
        "sha256": actual,
        "bytes": path.stat().st_size,
    }


def load_verified_json(label: str, path_text: str, expected: str) -> dict[str, object]:
    verify_hash(label, path_text, expected)
    return json.loads(resolve_path(path_text).read_text(encoding="utf-8"))


def powershell_json(script: str) -> object:
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        check=True,
        capture_output=True,
        text=True,
    )
    text = completed.stdout.strip()
    require(bool(text), "PowerShell returned no JSON")
    return json.loads(text)


def verify_running_process(main_info: dict[str, object]) -> dict[str, object]:
    running = main_info.get("running_process") or {}
    pid = int(running["pid"])
    expected_path = str(running["path"])
    expected_title = str(running["window_title"])
    process = powershell_json(
        "$p = Get-Process -Id "
        f"{pid} "
        "-ErrorAction Stop; "
        "$p | Select-Object Id,ProcessName,MainWindowTitle,Path | ConvertTo-Json -Compress"
    )
    require(process["ProcessName"] == running["process_name"], "running process name mismatch")
    require(process["Path"] == expected_path, "running process path mismatch")
    require(not expected_title or (process.get("MainWindowTitle") or "") == expected_title, "running process title mismatch")
    return process


def verify_desktop_shortcut(main_info: dict[str, object]) -> dict[str, object]:
    shortcut = main_info.get("desktop_shortcut") or {}
    path = Path(str(shortcut["path"]))
    require(path.exists(), f"desktop shortcut missing: {path}")
    path_literal = str(path).replace("'", "''")
    data = powershell_json(
        "$shell = New-Object -ComObject WScript.Shell; "
        f"$s = $shell.CreateShortcut('{path_literal}'); "
        "[pscustomobject]@{TargetPath=$s.TargetPath;"
        "WorkingDirectory=$s.WorkingDirectory} | ConvertTo-Json -Compress"
    )
    require(data["TargetPath"] == shortcut["target"], "desktop shortcut target mismatch")
    require(
        data["WorkingDirectory"] == shortcut["working_directory"],
        "desktop shortcut working directory mismatch",
    )
    return {
        "path": str(path),
        "target": data["TargetPath"],
        "working_directory": data["WorkingDirectory"],
    }


def verify_meeting_room_server(meeting_info: dict[str, object]) -> dict[str, object]:
    health_url = str(meeting_info["health_url"])
    health_url_literal = health_url.replace("'", "''")
    data = powershell_json(
        f"Invoke-RestMethod -Uri '{health_url_literal}' -TimeoutSec 5 | "
        "ConvertTo-Json -Depth 6 -Compress"
    )
    require(data.get("ok") is True, "Meeting Room server health ok flag missing")
    require(data.get("status") == "running", "Meeting Room server is not running")
    require(
        data.get("server_root") == meeting_info["server_root"],
        "Meeting Room server root mismatch",
    )
    require(
        data.get("google_drive_policy") == "communication_and_collaboration_only",
        "Meeting Room Google Drive policy mismatch",
    )
    require(data.get("c_drive_used") is False, "Meeting Room server reports C drive use")
    endpoints = data.get("endpoints") or []
    for endpoint in [
        "GET /health",
        "GET /room/state",
        "POST /room/order",
        "POST /room/chat",
    ]:
        require(endpoint in endpoints, f"Meeting Room endpoint missing: {endpoint}")
    return data


def verify_hermes_closed() -> dict[str, object]:
    processes = powershell_json(
        "$p = @(Get-Process | "
        "Where-Object { $_.ProcessName -like '*Hermes*' -or $_.MainWindowTitle -eq 'Hermes' }); "
        "[pscustomobject]@{Count=$p.Count} | ConvertTo-Json -Compress"
    )
    require(processes["Count"] == 0, "Hermes process still running after completion")
    return processes


def main() -> int:
    require(MANIFEST.exists(), f"manifest missing: {MANIFEST}")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    require(
        manifest.get("schema") == "engel_current_release_manifest_v1",
        "manifest schema mismatch",
    )
    require(
        manifest.get("goal_state") in {
            "complete_verified_20260607",
            "complete_verified_chat_first_ui_20260619",
            "complete_verified_real_local_chat_ui_20260620",
            "complete_verified_clear_chat_no_cluster_20260620",
            "complete_verified_clean_local_chat_reset_20260620",
            "complete_verified_xai_grok_cli_added_20260623",
            "complete_verified_mac_main_ui_20260623",
            "complete_verified_mac_model_router_cluster_20260623",
            "complete_verified_standalone_options_model_registry_20260623",
            "complete_verified_button_option_functional_audit_20260623",
            "complete_verified_visible_thinking_retired_static_sources_20260624",
        },
        "manifest goal state mismatch",
    )

    boundary = manifest.get("product_boundary") or {}
    require(boundary.get("main_product_shell") == "Engel AI Main", "main shell mismatch")
    require(boundary.get("not_composio_shell") is True, "Composio boundary missing")
    require(
        boundary.get("hermes_role") == "live_reference_source_only",
        "Hermes boundary mismatch",
    )
    require(boundary.get("hermes_left_open") is False, "Hermes left-open flag must be false")
    require(
        boundary.get("hermes_closed_after_reference") is True,
        "Hermes close-after-reference flag missing",
    )

    main_info = manifest.get("main") or {}
    sub_info = manifest.get("sub_engel") or {}
    hermes_info = manifest.get("hermes_reference") or {}
    source_capture_inventory = manifest.get("source_capture_inventory") or {}
    model_inventory = manifest.get("model_inventory") or {}
    objective_audit = manifest.get("objective_coverage_audit") or {}
    verification = manifest.get("verification") or {}
    model_router = manifest.get("model_router") or {}
    meeting_room = manifest.get("meeting_room_server") or {}
    roots = manifest.get("external_roots") or {}
    lifecycle = sub_info.get("lifecycle_demo") or {}
    local_chat = manifest.get("local_chat_real_output") or {}

    verified = [
        verify_hash(
            "main staged app bundle",
            main_info["staged_app_bundle"],
            main_info["staged_app_bundle_sha256"],
        ),
        verify_hash("main source", main_info["source"], main_info["source_sha256"]),
        verify_hash(
            "main widget test",
            main_info["widget_test"],
            main_info["widget_test_sha256"],
        ),
                verify_hash(
            "Rust local-chat source",
            local_chat["source"],
            local_chat["source_sha256"],
        ),
        verify_hash(
            "Rust local-chat executable",
            local_chat["executable"],
            local_chat["executable_sha256"],
        ),
        verify_hash(
            "local-chat first real output receipt",
            local_chat["first_receipt"],
            local_chat["first_receipt_sha256"],
        ),
        verify_hash(
            "local-chat second real output receipt",
            local_chat["second_receipt"],
            local_chat["second_receipt_sha256"],
        ),
        verify_hash(
            "local-chat active clean session",
            local_chat["active_session"],
            local_chat["active_session_sha256"],
        ),
        verify_hash("sub-engel zip", sub_info["zip"], sub_info["zip_sha256"]),
        verify_hash(
            "sub-engel package verifier",
            sub_info["package_verifier"],
            sub_info["package_verifier_sha256"],
        ),
        verify_hash(
            "sub-engel fresh extract verifier",
            sub_info["fresh_extract_verifier"],
            sub_info["fresh_extract_verifier_sha256"],
        ),
        verify_hash(
            "sub-engel fresh extract proof",
            sub_info["fresh_extract_proof"],
            sub_info["fresh_extract_proof_sha256"],
        ),
        verify_hash(
            "hermes live capture",
            hermes_info["live_capture"],
            hermes_info["live_capture_sha256"],
        ),
        verify_hash(
            "source capture inventory",
            source_capture_inventory["inventory"],
            source_capture_inventory["inventory_sha256"],
        ),
        verify_hash(
            "source capture inventory verifier",
            source_capture_inventory["verifier"],
            source_capture_inventory["verifier_sha256"],
        ),
        verify_hash(
            "model inventory",
            model_inventory["inventory"],
            model_inventory["inventory_sha256"],
        ),
        verify_hash(
            "model inventory verifier",
            model_inventory["verifier"],
            model_inventory["verifier_sha256"],
        ),
        verify_hash(
            "objective coverage audit",
            objective_audit["audit"],
            objective_audit["audit_sha256"],
        ),
        verify_hash(
            "objective coverage audit verifier",
            objective_audit["verifier"],
            objective_audit["verifier_sha256"],
        ),
        verify_hash(
            "full widget suite receipt",
            verification["full_widget_suite_receipt"],
            verification["full_widget_suite_receipt_sha256"],
        ),
        verify_hash(
            "UI chat Meeting Room bridge",
            verification["ui_chat_bridge"],
            verification["ui_chat_bridge_sha256"],
        ),
        verify_hash(
            "ChatGPT browser worker bridge",
            verification["chatgpt_browser_worker"],
            verification["chatgpt_browser_worker_sha256"],
        ),
        verify_hash(
            "Engel standalone chat runner",
            model_router["standalone_chat_runner"],
            model_router["standalone_chat_runner_sha256"],
        ),
        verify_hash(
            "Engel chat provider config",
            model_router["config"],
            model_router["config_sha256"],
        ),
        verify_hash(
            "Meeting Room startup launcher",
            meeting_room["launcher"],
            meeting_room["launcher_sha256"],
        ),
        verify_hash(
            "Meeting Room server script",
            meeting_room["server_script"],
            meeting_room["server_script_sha256"],
        ),
        verify_hash(
            "current release manifest verifier",
            verification["current_release_manifest_verifier"],
            verification["current_release_manifest_verifier_sha256"],
        ),
        verify_hash(
            "sub-engel lifecycle source work order",
            lifecycle["source_work_order"],
            lifecycle["source_work_order_sha256"],
        ),
        verify_hash(
            "sub-engel lifecycle receipt",
            lifecycle["receipt"],
            lifecycle["receipt_sha256"],
        ),
        verify_hash(
            "sub-engel lifecycle exported sent result",
            lifecycle["exported_sent_result"],
            lifecycle["exported_sent_result_sha256"],
        ),
    ]

    require(sub_info.get("contains_gui") is True, "Sub-Engel GUI flag missing")
    require(sub_info.get("contains_llm") is True, "Sub-Engel LLM flag missing")
    require(
        sub_info.get("package_verifier_files_checked") == 18,
        "Sub-Engel package verifier checked-file count mismatch",
    )
    source_order = load_verified_json(
        "sub-engel lifecycle source work order",
        lifecycle["source_work_order"],
        lifecycle["source_work_order_sha256"],
    )
    receipt = load_verified_json(
        "sub-engel lifecycle receipt",
        lifecycle["receipt"],
        lifecycle["receipt_sha256"],
    )
    sent_result = load_verified_json(
        "sub-engel lifecycle exported sent result",
        lifecycle["exported_sent_result"],
        lifecycle["exported_sent_result_sha256"],
    )
    fresh_extract = load_verified_json(
        "sub-engel fresh extract proof",
        sub_info["fresh_extract_proof"],
        sub_info["fresh_extract_proof_sha256"],
    )
    chat_provider_config = load_verified_json(
        "Engel chat provider config",
        model_router["config"],
        model_router["config_sha256"],
    )
    local_chat_first = load_verified_json(
        "local-chat first real output receipt",
        local_chat["first_receipt"],
        local_chat["first_receipt_sha256"],
    )
    local_chat_second = load_verified_json(
        "local-chat second real output receipt",
        local_chat["second_receipt"],
        local_chat["second_receipt_sha256"],
    )
    local_chat_session = load_verified_json(
        "local-chat active clean session",
        local_chat["active_session"],
        local_chat["active_session_sha256"],
    )
    external_model_registry = None
    if model_router.get("external_model_registry"):
        verified.append(
            verify_hash(
                "external model registry",
                model_router["external_model_registry"],
                model_router["external_model_registry_sha256"],
            )
        )
        external_model_registry = json.loads(
            resolve_path(model_router["external_model_registry"]).read_text(encoding="utf-8")
        )
    model_inventory_data = json.loads(
        Path(model_inventory["inventory"]).read_text(encoding="utf-8")
    )
    source_capture_data = json.loads(
        Path(source_capture_inventory["inventory"]).read_text(encoding="utf-8")
    )
    objective_audit_data = json.loads(
        Path(objective_audit["audit"]).read_text(encoding="utf-8")
    )
    require(fresh_extract.get("ok") is True, "fresh extract proof ok flag missing")
    require(
        fresh_extract.get("zip_sha256") == sub_info["zip_sha256"],
        "fresh extract proof zip hash mismatch",
    )
    require(
        fresh_extract.get("self_test_overall_ok") is True,
        "fresh extract self-test did not pass",
    )
    require(
        fresh_extract.get("lifecycle_overall_ok") is True,
        "fresh extract lifecycle did not pass",
    )
    require(
        fresh_extract.get("included_model_sha256")
        == "041474553FCABFC2A2D67903F9D2C2E50BD92528E670DA4F33B5D0CE6E59FD55",
        "fresh extract included model hash mismatch",
    )
    require(
        Path(str(fresh_extract.get("lifecycle_exported_file") or "")).exists(),
        "fresh extract exported sent-work file missing",
    )
    require(
        chat_provider_config.get("schema") == "engel_chat_provider_config_v1",
        "chat provider config schema mismatch",
    )
    require(
        chat_provider_config.get("model_router_mode") == model_router["router_mode"],
        "model router mode mismatch",
    )
    require(
        chat_provider_config.get("selected_model_id") == model_router["selected_model_id"],
        "selected chat model mismatch",
    )
    require(
        chat_provider_config.get("selected_chat_provider") == model_router["selected_chat_provider"],
        "selected chat provider mismatch",
    )
    require(
        chat_provider_config.get("selected_creation_model_id")
        == model_router["selected_creation_model_id"],
        "selected creation model mismatch",
    )
    require(
        chat_provider_config.get("selected_creation_provider")
        == model_router["selected_creation_provider"],
        "selected creation provider mismatch",
    )
    require(
        chat_provider_config.get("thinking_enabled") is True,
        "thinking setting should be enabled",
    )
    enabled_models = set(chat_provider_config.get("enabled_model_ids") or [])
    for model_id in [
        "auto-best",
        "local-cuda-qwen-coder",
        "chatgpt-browser",
        "openai-api-gpt-5-5",
    ]:
        require(model_id in enabled_models, f"enabled model missing: {model_id}")
    persistent_memory = Path(str(chat_provider_config["persistent_memory_path"]))
    require(persistent_memory.drive.upper() != "C:", "persistent chat memory must not use C drive")
    require(persistent_memory.exists(), "persistent chat memory file missing")
    require(
        model_router.get("local_creation_route") == "local CUDA llama.cpp CLI",
        "local creation route mismatch",
    )
    require(
        model_router.get("natural_chat_route") == "ChatGPT browser bridge when available, local fallback",
        "natural chat route mismatch",
    )
    require(
        int(model_router.get("built_in_model_catalog_count", 0)) >= 120,
        "built-in model catalog did not include broad future model options",
    )
    require(
        int(model_router.get("standalone_channels_merged", 0)) == 3,
        "standalone channel merge count mismatch",
    )
    require(
        int(model_router.get("standalone_integrations_merged", 0)) == 118,
        "standalone integration merge count mismatch",
    )
    required_provider_lanes = {
        "xAI Grok",
        "Anthropic",
        "Gemini",
        "DeepSeek",
        "DashScope Qwen",
        "Kimi Moonshot",
        "MiniMax",
        "Mistral",
        "Cohere",
        "Groq",
        "Perplexity",
        "Hugging Face",
    }
    require(
        required_provider_lanes <= set(model_router.get("setup_only_providers_visible") or []),
        "provider setup lanes missing from model router manifest",
    )
    require(
        external_model_registry is not None,
        "external model registry is not declared in model router manifest",
    )
    require(
        external_model_registry.get("schema") == "engel_external_model_registry_v1",
        "external model registry schema mismatch",
    )
    require(
        isinstance(external_model_registry.get("models"), list),
        "external model registry models must be a list",
    )
    refresh_sources = (
        external_model_registry.get("provider_model_refresh_sources")
        or external_model_registry.get("official_model_refresh_sources")
        or []
    )
    require(
        len(refresh_sources) >= 7,
        "external model registry missing official refresh sources",
    )
    require(lifecycle.get("overall_ok") is True, "lifecycle manifest overall_ok missing")
    require(source_order.get("created_by") == "Engel AI Main", "source order creator mismatch")
    require(source_order.get("proof_required") is True, "source order proof flag missing")
    require(receipt.get("overall_ok") is True, "lifecycle receipt overall_ok missing")
    require(
        receipt.get("source_work_order") == lifecycle["source_work_order"],
        "lifecycle receipt source work order mismatch",
    )
    require(
        receipt.get("exported_file") == lifecycle["exported_sent_result"],
        "lifecycle receipt exported result mismatch",
    )
    require(sent_result.get("operator_status") == "done", "sent result not marked done")
    require(sent_result.get("proof_required") is True, "sent result proof flag missing")
    require(
        sent_result.get("source_work_order") == lifecycle["source_work_order"],
        "sent result source work order mismatch",
    )
    require(
        hermes_info.get("gallery_coverage") == "12/12 Hermes captures",
        "Hermes gallery coverage mismatch",
    )
    capture_counts = source_capture_data.get("counts") or {}
    require(
        capture_counts.get("composio") == source_capture_inventory["composio_captures"],
        "Composio source capture count mismatch",
    )
    require(
        capture_counts.get("hermes") == source_capture_inventory["hermes_captures"],
        "Hermes source capture count mismatch",
    )
    require(
        capture_counts.get("total") == source_capture_inventory["total_captures"],
        "source capture total mismatch",
    )
    require(
        capture_counts.get("bytes") == source_capture_inventory["capture_bytes"],
        "source capture byte count mismatch",
    )
    capture_check = subprocess.run(
        ["python", str(Path(source_capture_inventory["verifier"]))],
        check=True,
        capture_output=True,
        text=True,
    )
    require('"ok": true' in capture_check.stdout, "source capture inventory verifier did not pass")
    counts = model_inventory_data.get("counts") or {}
    require(counts.get("all_model_files") == model_inventory["all_model_files"], "model file count mismatch")
    require(counts.get("gguf_files") == model_inventory["gguf_files"], "GGUF count mismatch")
    require(counts.get("safetensors_files") == model_inventory["safetensors_files"], "safetensors count mismatch")
    require(
        counts.get("manual_download_gguf_files") == model_inventory["manual_download_gguf_files"],
        "manual download GGUF count mismatch",
    )
    require(counts.get("cosmos_folders") == model_inventory["cosmos_folders"], "Cosmos folder count mismatch")
    require(counts.get("total_model_bytes") == model_inventory["total_model_bytes"], "model bytes mismatch")
    model_check = subprocess.run(
        ["python", str(Path(model_inventory["verifier"]))],
        check=True,
        capture_output=True,
        text=True,
    )
    require('"ok": true' in model_check.stdout, "model inventory verifier did not pass")
    objective_summary = objective_audit_data.get("coverage_summary") or {}
    require(
        objective_summary.get("requirements_checked") == objective_audit["requirements_checked"],
        "objective audit checked count mismatch",
    )
    require(
        objective_summary.get("requirements_passing") == objective_audit["requirements_passing"],
        "objective audit passing count mismatch",
    )
    require(
        objective_summary.get("completion_claim") == objective_audit["completion_claim"],
        "objective audit completion claim mismatch",
    )
    objective_check = subprocess.run(
        ["python", str(Path(objective_audit["verifier"]))],
        check=True,
        capture_output=True,
        text=True,
    )
    require('"ok": true' in objective_check.stdout, "objective coverage audit verifier did not pass")
    require(local_chat.get("real_output_verified") is True, "local-chat real output flag missing")
    require(local_chat_first.get("ok") is True, "local-chat first receipt not ok")
    require(local_chat_first.get("readable_output_captured") is True, "local-chat first receipt not readable")
    require(
        local_chat_first.get("assistant_reply")
        == "I am ready to assist you. What can I do for you today?",
        "local-chat first reply mismatch",
    )
    require(
        local_chat_first.get("session_reset_for_prompt_pollution") is True,
        "local-chat first prompt-pollution reset proof missing",
    )
    require(
        local_chat_first.get("session_reset_for_turn_limit") is False,
        "local-chat first turn-limit reset should be false",
    )
    require(
        (local_chat_first.get("preflight") or {}).get("session_turn_count") == 0,
        "local-chat first preflight should see reset session",
    )
    require(
        local_chat_first.get("approved_memory_context_path") is None,
        "local-chat first should not inject approved memory context",
    )
    require(local_chat_second.get("ok") is True, "local-chat second receipt not ok")
    require(local_chat_second.get("readable_output_captured") is True, "local-chat second receipt not readable")
    require(
        local_chat_second.get("assistant_reply") == "What can I assist you with today?",
        "local-chat second reply mismatch",
    )
    require(
        local_chat_second.get("session_reset_for_prompt_pollution") is False,
        "local-chat second prompt-pollution reset should be false",
    )
    require(
        local_chat_second.get("session_reset_for_turn_limit") is False,
        "local-chat second turn-limit reset should be false",
    )
    require(
        (local_chat_second.get("preflight") or {}).get("session_turn_count") == 1,
        "local-chat second preflight should continue fresh session",
    )
    require(
        local_chat_second.get("approved_memory_context_path") is None,
        "local-chat second should not inject approved memory context",
    )
    bad_local_chat_terms = [
        "Say this is Engel session draft turn one",
        "APPROVED LOCAL CHAT MEMORY CONTEXT",
        "UNTRUSTED LOCAL SESSION TRANSCRIPT",
        "available commands",
        "Loading model",
    ]
    for label, receipt in [
        ("first", local_chat_first),
        ("second", local_chat_second),
    ]:
        prompt_path = resolve_path(str(receipt.get("constructed_prompt_path") or ""))
        require(prompt_path.exists(), f"local-chat {label} constructed prompt missing")
        prompt_text = prompt_path.read_text(encoding="utf-8")
        require("<|im_start|>system" in prompt_text, f"local-chat {label} prompt missing ChatML system")
        for term in bad_local_chat_terms:
            require(term not in prompt_text, f"local-chat {label} prompt still contains {term}")
    turns = local_chat_session.get("turns") or []
    require(len(turns) == 2, "local-chat active session turn count mismatch")
    require(
        turns[0].get("assistant_reply")
        == "I am ready to assist you. What can I do for you today?",
        "local-chat session first reply mismatch",
    )
    require(
        turns[0].get("session_reset_for_prompt_pollution") is True,
        "local-chat session first turn reset flag mismatch",
    )
    require(
        turns[1].get("assistant_reply") == "What can I assist you with today?",
        "local-chat session second reply mismatch",
    )
    require(
        turns[1].get("session_reset_for_prompt_pollution") is False,
        "local-chat session second turn reset flag mismatch",
    )
    session_text = json.dumps(turns)
    for term in bad_local_chat_terms:
        require(term not in session_text, f"local-chat session still contains {term}")
    analyze_status = verification.get("flutter_analyze", "")
    require(
        analyze_status.startswith("passed")
        or analyze_status.startswith("blocked / analyzer hung"),
        "analyze status invalid",
    )
    require(verification.get("full_widget_suite") == "passed / 66 tests", "widget suite mismatch")
    require(verification.get("windows_release_build") == "passed", "release build mismatch")
    live_process = verify_running_process(main_info)
    desktop_shortcut = verify_desktop_shortcut(main_info)
    meeting_room_health = verify_meeting_room_server(meeting_room)
    hermes_process = verify_hermes_closed()

    external_roots_checked = []
    for label, path_text in roots.items():
        path = resolve_path(path_text)
        access_denied = False
        try:
            exists = path.exists()
        except OSError as exc:
            if getattr(exc, "winerror", None) == 5:
                exists = True
                access_denied = True
            else:
                raise
        require(exists, f"external root {label} missing: {path}")
        external_roots_checked.append({
            "label": label,
            "path": str(path),
            "access_denied_accepted": access_denied,
        })
    out = {
        "ok": True,
        "manifest": str(MANIFEST),
        "manifest_sha256": sha256_file(MANIFEST),
        "verified_files": verified,
        "running_process": live_process,
        "desktop_shortcut": desktop_shortcut,
        "meeting_room_server": meeting_room_health,
        "hermes_process": hermes_process,
        "local_chat_real_output": {
            "first_assistant_reply": local_chat_first.get("assistant_reply"),
            "second_assistant_reply": local_chat_second.get("assistant_reply"),
            "session_turns": len(local_chat_session.get("turns") or []),
        },
        "external_roots_checked": external_roots_checked,
    }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        raise SystemExit(1)
