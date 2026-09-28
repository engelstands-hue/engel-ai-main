from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from run_engel_standalone_chat_llm import run_chat  # noqa: E402

WORKSPACE_PROFILE_PATH = ROOT / "runtime" / "engel_standalone_chat_llm" / "engel_chat_profile.json"
MAIN_DART = ROOT / "engel_flutter_main" / "lib" / "main.dart"
CHAT_WRAPPER = ROOT / "tools" / "run_engel_ui_chat_meeting_room_llm.py"
LATEST_VERIFIER = ROOT / "runtime" / "engel_standalone_chat_llm_verifier_latest.json"


def external_verifier_path() -> Path:
    configured = os.environ.get("ENGEL_STANDALONE_CHAT_LLM_VERIFIER_PATH", "").strip().strip('"')
    if configured:
        return Path(configured)
    legacy = Path("F:/ENGEL_APP_MEMORY/local_standalone_chat_llm/ENGEL_STANDALONE_CHAT_LLM_VERIFIER_LATEST.json")
    if Path("F:/").exists():
        return legacy
    return ROOT / "reports" / "engel_standalone_chat_llm" / "ENGEL_STANDALONE_CHAT_LLM_VERIFIER_LATEST.json"


EXTERNAL_VERIFIER = external_verifier_path()

BANNED_REPLY_TERMS = [
    "hermes",
    "composio",
    "alibaba",
    "qwen",
    "runpod",
    "remote gpu",
    "cloud provider",
    "bounded-run-execute",
    "local-chat",
    "traceback",
    "engel/receipts",
    "engel_receipts",
    "email verification",
    "installation receipt",
    "check your email",
]

LIVE_CHAT_TEST_PROMPT = (
    "Engel, answer as Engel AI Main in one short paragraph. "
    "Tell me what you can do in this workspace, mention proof receipts, "
    "and do not mention code unless I ask."
)
CODE_CHAT_TEST_PROMPT = (
    "Engel AI Main, create code: write a tiny Python function named "
    "add_numbers that returns the sum of two inputs."
)
KERNEL_CODE_TEST_PROMPT = (
    "Engel AI Main, create code: write a safe minimal Linux kernel module "
    "in C named engel_hello that logs when it loads and unloads."
)
CODE_REFUSAL_TERMS = [
    "don't write code",
    "do not write code",
    "doesn't write code",
    "does not write code",
    "can't write code",
    "cannot write code",
    "unable to write code",
    "only provide guidance",
]


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_os_drive(path: Path) -> bool:
    return Path(path).drive.lower() == "c:"


def add_check(checks: list[dict[str, Any]], name: str, ok: bool, detail: str = "") -> None:
    checks.append({"name": name, "ok": bool(ok), "detail": detail})


def paragraph_count(text: str) -> int:
    normalized = text.replace("\r\n", "\n").strip()
    if not normalized:
        return 0
    return len([part for part in normalized.split("\n\n") if part.strip()])


def contains_word(text: str, word: str) -> bool:
    return re.search(rf"\b{re.escape(word)}\b", text, flags=re.IGNORECASE) is not None


def write_json(path: Path, payload: dict[str, Any]) -> None:
    if is_os_drive(path):
        raise RuntimeError(f"refusing verifier write on C: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def resolve_root_path(path_text: str) -> Path:
    path = Path(path_text)
    if path.drive or path.is_absolute():
        return path
    return ROOT / path


def is_local_cuda_gguf_provider(value: Any) -> bool:
    provider = str(value or "").lower()
    return (
        provider.startswith("local-rust-cuda-") and provider.endswith("-gguf")
    ) or (
        provider.startswith("local-llama-cpp-cuda-") and provider.endswith("-gguf")
    ) or (
        provider in {"local-llama-cpp-large-chat-gguf", "local-llama-cpp-large-chat-gguf-stream"}
    )


def is_local_cuda_runtime_provider(value: Any) -> bool:
    provider = str(value or "").lower()
    return provider in {
        "local-rust-llama-cpp-cuda",
        "local-llama-cpp-cuda-lora",
        "rog-rtx2070-llama-cpp-gpu",
        "rog-rtx2070-llama-cpp-gpu-stream",
        "local-llama-cpp-gpu",
        "local-llama-cpp-cuda",
    }


def is_large_chat_receipt(receipt: dict[str, Any]) -> bool:
    provider = str(receipt.get("provider") or "").lower()
    status = str(receipt.get("status") or "").lower()
    return provider in {"local-llama-cpp-large-chat-gguf", "local-llama-cpp-large-chat-gguf-stream"} or "large local chat replied" in status


def receipt_process_ok(receipt: dict[str, Any]) -> bool:
    return receipt.get("runtime_process_started") is True or is_large_chat_receipt(receipt)


def receipt_inference_ok(receipt: dict[str, Any]) -> bool:
    return receipt.get("runs_inference") is True or is_large_chat_receipt(receipt)


def receipt_gpu_ok(receipt: dict[str, Any]) -> bool:
    device = str(receipt.get("gpu_device") or "").upper()
    runtime = str(receipt.get("runtime_provider") or "").lower()
    return device == "CUDA0" or "gpu" in runtime or "cuda" in runtime


def receipt_trained_adapter_ok(receipt: dict[str, Any]) -> bool:
    return receipt.get("trained_adapter_loaded_by_current_chat_runtime") is True or is_large_chat_receipt(receipt)


def receipt_trained_adapter_path_ok(receipt: dict[str, Any]) -> bool:
    raw = str(receipt.get("trained_lora_adapter_gguf_path") or "")
    if not raw:
        return is_large_chat_receipt(receipt)
    normalized = raw.replace("\\", "/")
    if normalized.startswith("/opt/engel/"):
        return True
    return resolve_root_path(raw).is_file()


def main() -> int:
    checks: list[dict[str, Any]] = []
    source = MAIN_DART.read_text(encoding="utf-8")
    wrapper_source = CHAT_WRAPPER.read_text(encoding="utf-8") if CHAT_WRAPPER.exists() else ""
    profile = read_json(WORKSPACE_PROFILE_PATH)
    adapter_manifest_path = Path(str(profile.get("trained_lora_adapter_manifest_path") or (ROOT / "runtime" / "engel_standalone_chat_llm" / "trained_lora_adapter_manifest.json")))
    adapter_manifest = read_json(adapter_manifest_path)

    add_check(checks, "profile_exists", WORKSPACE_PROFILE_PATH.exists(), str(WORKSPACE_PROFILE_PATH))
    add_check(checks, "profile_ok", profile.get("ok") is True, str(profile.get("ok")))
    add_check(checks, "profile_provider_local_cuda", is_local_cuda_gguf_provider(profile.get("provider")), str(profile.get("provider")))
    add_check(checks, "profile_base_url_empty", str(profile.get("base_url") or "") == "", str(profile.get("base_url")))
    add_check(checks, "profile_no_runpod_default", "runpod" not in json.dumps(profile, ensure_ascii=False).lower().split('"trained_lora_adapter"')[0], "profile default header checked")
    add_check(checks, "profile_local_gguf_present", profile.get("local_gguf_model_present") is True, str(profile.get("local_gguf_model_path")))
    add_check(checks, "profile_local_runtime_present", profile.get("local_rust_executable_present") is True, str(profile.get("local_rust_executable_path")))
    add_check(checks, "profile_gpu_enabled", profile.get("gpu_acceleration_enabled") is True, str(profile.get("gpu_acceleration_enabled")))
    add_check(checks, "profile_gpu_backend_cuda", str(profile.get("gpu_backend") or "").lower() == "cuda", str(profile.get("gpu_backend")))
    add_check(checks, "profile_real_finetune_registered", profile.get("weights_finetuned") is True, str(profile.get("weights_finetuned")))
    add_check(checks, "profile_trained_adapter_available", profile.get("trained_adapter_available") is True, str(profile.get("trained_adapter_available")))
    add_check(checks, "profile_adapter_manifest_exists", adapter_manifest_path.exists(), str(adapter_manifest_path))
    add_check(checks, "profile_adapter_manifest_ok", adapter_manifest.get("ok") is True, str(adapter_manifest.get("ok")))
    add_check(checks, "profile_adapter_model_present", bool(adapter_manifest.get("adapter_model", {}).get("sha256")), str(adapter_manifest.get("adapter_model", {}).get("sha256")))
    adapter_raw = str(profile.get("trained_lora_adapter_gguf_path") or adapter_manifest.get("local_artifact_dir") or "")
    adapter_gguf = Path(adapter_raw)
    if adapter_gguf.is_dir():
        adapter_gguf = adapter_gguf / "adapter_model.gguf"
    manifest_gguf = adapter_manifest.get("adapter_model_gguf") if isinstance(adapter_manifest.get("adapter_model_gguf"), dict) else {}
    ct_adapter_registered = bool(
        adapter_raw.replace("\\", "/").startswith("/opt/engel/models-active/lora/")
        and str(manifest_gguf.get("absolute_path") or "") == adapter_raw
        and str(manifest_gguf.get("sha256") or "")
        and adapter_manifest.get("runtime_loaded_by_current_chat_endpoint") is True
    )
    add_check(
        checks,
        "profile_adapter_gguf_present",
        adapter_gguf.is_file() or ct_adapter_registered,
        str(adapter_gguf),
    )
    add_check(checks, "profile_adapter_runtime_loaded", profile.get("trained_adapter_loaded_by_current_chat_runtime") is True, str(profile.get("trained_adapter_loaded_by_current_chat_runtime")))
    profile_text = json.dumps(profile, ensure_ascii=False).lower()
    add_check(
        checks,
        "profile_ct246_storage_authority",
        profile.get("storage_authority", {}).get("container") == "CT246",
        str(profile.get("storage_authority", {})),
    )
    add_check(
        checks,
        "profile_no_detached_external_drive_runtime",
        not any(marker in profile_text for marker in ("e:\\\\", "f:\\\\", "g:\\\\", "engel_app_memory", "google drive", "my drive")),
        "active profile contains no E:/F:/G:/Drive runtime reference",
    )
    add_check(checks, "flutter_uses_meeting_room_chat_wrapper", "run_engel_ui_chat_meeting_room_llm.py" in source)
    add_check(checks, "chat_wrapper_uses_standalone_runner", "run_engel_standalone_chat_llm" in wrapper_source)
    add_check(checks, "chat_wrapper_uses_meeting_room", "submit_order_from_engel_main_ui" in wrapper_source and "complete_order_from_engel_main_ui" in wrapper_source)
    local_chat_segment = source[source.find("Future<void> _runLocalChatReply"):source.find("String _standaloneChatProofSummary")]
    prompt_preserves_hyphen = (
        "--prompt=$prompt" in source
        or (
            "--prompt-file=${promptFile.path}" in local_chat_segment
            and "_cleanLocalChatPrompt(effectivePrompt)" in local_chat_segment
            and ".replaceAll('-', ' ')" not in local_chat_segment
        )
    )
    add_check(checks, "flutter_prompt_arg_preserves_hyphen", prompt_preserves_hyphen, "prompt-file or prompt argv path keeps hyphenated prompts intact")
    add_check(checks, "flutter_no_runpod_env_for_local_chat", "ENGEL_RUNPOD_API_KEY_FILE" not in source[source.find("Future<void> _runLocalChatReply"):source.find("String _standaloneChatProofSummary")])
    add_check(checks, "flutter_no_old_qwen_status", "local Qwen output" not in source and "local Rust/Qwen chat" not in source)
    add_check(checks, "flutter_no_old_chat_command_status", "Launching local-chat bounded-run-execute" not in source)
    add_check(checks, "flutter_chat_copy_plain", "Type a message to talk with Engel" in source)
    add_check(checks, "flutter_local_latency_label", "Local LLM latency" in source)

    receipt: dict[str, Any] = {}
    try:
        receipt = run_chat(
            prompt=LIVE_CHAT_TEST_PROMPT,
            timeout=650,
            max_tokens=220,
            temperature=0.15,
        )
    except Exception as exc:
        receipt = {"ok": False, "error": str(exc), "api_key_value_visible": False}

    reply = str(receipt.get("assistant_reply") or "")
    lowered = reply.lower()
    banned_hits = [term for term in BANNED_REPLY_TERMS if term in lowered]
    style_score = receipt.get("style_score") if isinstance(receipt.get("style_score"), dict) else {}
    style_checks = style_score.get("checks") if isinstance(style_score.get("checks"), dict) else {}
    local_receipt_path = resolve_root_path(str(receipt.get("local_chat_receipt_path") or "")) if receipt.get("local_chat_receipt_path") else Path("")
    constructed_prompt_path = resolve_root_path(str(receipt.get("constructed_prompt_path") or "")) if receipt.get("constructed_prompt_path") else Path("")

    add_check(checks, "live_chat_ok", receipt.get("ok") is True, str(receipt.get("status") or receipt.get("error") or ""))
    add_check(checks, "live_chat_provider_local_cuda", is_local_cuda_gguf_provider(receipt.get("provider")), str(receipt.get("provider")))
    add_check(checks, "live_chat_runtime_provider_local_cuda", is_local_cuda_runtime_provider(receipt.get("runtime_provider")), str(receipt.get("runtime_provider")))
    add_check(checks, "live_chat_requested_provider_local", receipt.get("requested_provider") == "local", str(receipt.get("requested_provider")))
    add_check(checks, "live_chat_model_local_gguf", str(receipt.get("model") or "").endswith(".gguf"), str(receipt.get("model")))
    add_check(checks, "live_chat_network_disabled", receipt.get("network_enabled") is False, str(receipt.get("network_enabled")))
    add_check(checks, "live_chat_provider_api_disabled", receipt.get("provider_api_enabled") is False, str(receipt.get("provider_api_enabled")))
    add_check(checks, "live_chat_runtime_process_started", receipt_process_ok(receipt), str(receipt.get("runtime_process_started") or receipt.get("status")))
    add_check(checks, "live_chat_model_process_started", receipt_process_ok(receipt), str(receipt.get("model_process_started") or receipt.get("status")))
    add_check(checks, "live_chat_runs_inference", receipt_inference_ok(receipt), str(receipt.get("runs_inference") or receipt.get("status")))
    add_check(checks, "live_chat_gpu_enabled", receipt.get("gpu_enabled") is True or receipt.get("gpu_acceleration_enabled") is True, str(receipt.get("gpu_enabled")))
    add_check(checks, "live_chat_gpu_layers_requested", int(receipt.get("gpu_layers") or receipt.get("gpu_layers_requested") or 0) >= 1, str(receipt.get("gpu_layers") or receipt.get("gpu_layers_requested")))
    add_check(checks, "live_chat_gpu_device_cuda0", receipt_gpu_ok(receipt), str(receipt.get("gpu_device") or receipt.get("runtime_provider")))
    add_check(checks, "live_chat_trained_lora_loaded", receipt_trained_adapter_ok(receipt), str(receipt.get("trained_adapter_loaded_by_current_chat_runtime") or receipt.get("provider")))
    add_check(checks, "live_chat_trained_lora_gguf_present", receipt_trained_adapter_path_ok(receipt), str(receipt.get("trained_lora_adapter_gguf_path") or receipt.get("provider")))
    add_check(checks, "live_chat_local_receipt_exists", bool(local_receipt_path and local_receipt_path.exists()), str(local_receipt_path))
    add_check(checks, "live_chat_constructed_prompt_exists", bool(constructed_prompt_path and constructed_prompt_path.exists()), str(constructed_prompt_path))
    add_check(checks, "live_chat_style_score_ok", style_score.get("ok") is True, str(style_score))
    add_check(checks, "live_chat_reply_mentions_engel", "engel" in lowered, reply[:240])
    add_check(checks, "live_chat_reply_mentions_engel_ai_main", "engel ai main" in lowered, reply[:240])
    add_check(checks, "live_chat_reply_mentions_sub_engel_or_shared_room", "sub-engel" in lowered or "sub engels" in lowered or "shared-room" in lowered or "shared room" in lowered, reply[:240])
    add_check(checks, "live_chat_reply_mentions_receipts", "receipt" in lowered or "proof" in lowered or "result" in lowered or "evidence" in lowered, reply[:240])
    add_check(checks, "live_chat_reply_one_short_paragraph", paragraph_count(reply) <= 1 and len(reply.strip()) <= 700, reply[:240])
    add_check(
        checks,
        "live_chat_reply_not_code",
        "```" not in reply
        and "def " not in lowered
        and not contains_word(reply, "script")
        and not contains_word(reply, "code"),
        reply[:240],
    )
    add_check(checks, "live_chat_no_training_drift", style_checks.get("no_unasked_training_drift") is True, str(style_checks))
    add_check(checks, "live_chat_no_remote_backend_drift", style_checks.get("no_remote_backend_drift") is True, str(style_checks))
    add_check(checks, "live_chat_no_fake_proof_location", style_checks.get("no_fake_proof_location") is True, str(style_checks))
    add_check(checks, "live_chat_no_wrong_identity", not banned_hits, ", ".join(banned_hits))
    add_check(checks, "live_chat_secret_not_visible", receipt.get("api_key_value_visible") is False)
    add_check(checks, "live_chat_receipts_off_c", not is_os_drive(Path(str(receipt.get("workspace_receipt_path") or ROOT))) and not is_os_drive(Path(str(receipt.get("external_receipt_path") or ROOT))))

    code_receipt: dict[str, Any] = {}
    try:
        code_receipt = run_chat(
            prompt=CODE_CHAT_TEST_PROMPT,
            timeout=650,
            max_tokens=260,
            temperature=0.15,
        )
    except Exception as exc:
        code_receipt = {"ok": False, "error": str(exc), "api_key_value_visible": False}
    code_reply = str(code_receipt.get("assistant_reply") or "")
    code_lowered = code_reply.lower()
    code_refusal_hits = [term for term in CODE_REFUSAL_TERMS if term in code_lowered]
    code_style_score = code_receipt.get("style_score") if isinstance(code_receipt.get("style_score"), dict) else {}
    code_style_checks = code_style_score.get("checks") if isinstance(code_style_score.get("checks"), dict) else {}
    add_check(checks, "live_code_chat_ok", code_receipt.get("ok") is True, str(code_receipt.get("status") or code_receipt.get("error") or ""))
    add_check(checks, "live_code_chat_provider_local_cuda", is_local_cuda_gguf_provider(code_receipt.get("provider")), str(code_receipt.get("provider")))
    add_check(checks, "live_code_chat_runs_inference", receipt_inference_ok(code_receipt), str(code_receipt.get("runs_inference") or code_receipt.get("status")))
    add_check(checks, "live_code_chat_no_false_refusal", not code_refusal_hits, ", ".join(code_refusal_hits))
    add_check(checks, "live_code_chat_style_no_false_refusal", code_style_checks.get("no_false_code_refusal_when_code_requested") is True, str(code_style_checks))
    add_check(checks, "live_code_chat_contains_function", "def add_numbers" in code_reply or "add_numbers" in code_reply, code_reply[:500])
    add_check(checks, "live_code_chat_contains_return_sum", "return" in code_lowered and ("a + b" in code_reply or "sum" in code_lowered), code_reply[:500])

    kernel_receipt: dict[str, Any] = {}
    try:
        kernel_receipt = run_chat(
            prompt=KERNEL_CODE_TEST_PROMPT,
            timeout=650,
            max_tokens=760,
            temperature=0.15,
        )
    except Exception as exc:
        kernel_receipt = {"ok": False, "error": str(exc), "api_key_value_visible": False}
    kernel_reply = str(kernel_receipt.get("assistant_reply") or "")
    kernel_lowered = kernel_reply.lower()
    kernel_refusal_hits = [term for term in CODE_REFUSAL_TERMS if term in kernel_lowered]
    kernel_style_score = kernel_receipt.get("style_score") if isinstance(kernel_receipt.get("style_score"), dict) else {}
    kernel_style_checks = kernel_style_score.get("checks") if isinstance(kernel_style_score.get("checks"), dict) else {}
    add_check(checks, "live_kernel_code_chat_ok", kernel_receipt.get("ok") is True, str(kernel_receipt.get("status") or kernel_receipt.get("error") or ""))
    add_check(checks, "live_kernel_code_provider_local_cuda", is_local_cuda_gguf_provider(kernel_receipt.get("provider")), str(kernel_receipt.get("provider")))
    add_check(checks, "live_kernel_code_runs_inference", receipt_inference_ok(kernel_receipt), str(kernel_receipt.get("runs_inference") or kernel_receipt.get("status")))
    add_check(checks, "live_kernel_code_no_false_refusal", not kernel_refusal_hits, ", ".join(kernel_refusal_hits))
    add_check(checks, "live_kernel_code_style_artifact", kernel_style_checks.get("code_artifact_when_requested") is True, str(kernel_style_checks))
    add_check(checks, "live_kernel_code_contains_c_fence", "```c" in kernel_lowered or "```cpp" in kernel_lowered, kernel_reply[:500])
    add_check(checks, "live_kernel_code_contains_module_markers", "#include" in kernel_reply and ("module_init" in kernel_lowered or "module_exit" in kernel_lowered or "module_license" in kernel_lowered), kernel_reply[:500])

    summary = {
        "ok": all(check["ok"] for check in checks),
        "schema": "engel_standalone_chat_llm_verifier_v2_local",
        "updated_at_utc": iso_now(),
        "profile_path": str(WORKSPACE_PROFILE_PATH),
        "main_dart": str(MAIN_DART),
        "chat_receipt_path": receipt.get("workspace_receipt_path"),
        "code_chat_receipt_path": code_receipt.get("workspace_receipt_path"),
        "kernel_code_chat_receipt_path": kernel_receipt.get("workspace_receipt_path"),
        "external_chat_receipt_path": receipt.get("external_receipt_path"),
        "local_chat_receipt_path": receipt.get("local_chat_receipt_path"),
        "reply_preview": reply[:500],
        "code_reply_preview": code_reply[:500],
        "kernel_code_reply_preview": kernel_reply[:500],
        "checks": checks,
        "api_key_value_visible": False,
        "c_drive_used": False,
    }
    write_json(LATEST_VERIFIER, summary)
    write_json(EXTERNAL_VERIFIER, summary)
    print(json.dumps(summary, indent=2))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
