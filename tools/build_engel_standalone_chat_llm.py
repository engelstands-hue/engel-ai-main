from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from engel_vault_paths import engel_memory_path

from run_engel_runpod_stretch import (  # noqa: E402
    ENGEL_CHAT_PERSONALITY,
    StretchError,
    ensure_runtime_env,
    is_os_drive,
    load_engel_runtime,
    openai_post,
)

CONFIG_PATH = engel_memory_path("F", "runpod", "engel_runpod_config.json")
WORKSPACE_PROFILE_DIR = ROOT / "runtime" / "engel_standalone_chat_llm"
EXTERNAL_PROFILE_DIR = engel_memory_path("F", "runpod", "standalone_chat_llm")
WORKSPACE_PROFILE_PATH = WORKSPACE_PROFILE_DIR / "engel_chat_profile.json"
EXTERNAL_PROFILE_PATH = EXTERNAL_PROFILE_DIR / "engel_chat_profile.json"
WORKSPACE_RECEIPT_DIR = ROOT / "reports" / "engel_standalone_chat_llm" / "receipts"
EXTERNAL_RECEIPT_DIR = EXTERNAL_PROFILE_DIR / "receipts"

BANNED_IDENTITY_TERMS = [
    "hermes",
    "composio",
    "alibaba",
    "qwen",
    "i am runpod",
    "as runpod",
    "i am mistral",
    "as mistral",
    "engel_logs",
    "engel/logs",
    "log file",
    "logs directory",
    "task_123",
]

ENGEL_STANDALONE_SYSTEM_PROMPT = (
    ENGEL_CHAT_PERSONALITY
    + "\n\n"
    + "You are the conversational brain inside Engel AI Main. "
    + "The operator should feel like they are talking to Engel, not reading a code runner. "
    + "Answer as one assistant in a normal chat window. "
    + "Current-turn contract: answer only the current user message, and follow explicit length, paragraph, and wording constraints. "
    + "If the user asks for one short paragraph, return exactly one compact paragraph. "
    + "Do not talk about training, datasets, scripts, code, privacy policy, onboarding, or setup unless the current user message explicitly asks for that topic. "
    + "If the user greets Engel or asks what Engel can do, answer as Engel AI Main with workspace capabilities in plain language. "
    + "For workspace capability questions, use this center: Engel can chat, coordinate Sub-Engels through shared-room files, use Rust background tools, use local models, use remote GPU capacity when configured, and show proof receipts for real work. "
    + "Do not expose command lines, JSON, implementation details, receipts, or backend names unless the user asks for proof or diagnostics. "
    + "When the user asks for work, state the next concrete action in plain language and keep momentum. "
    + "When you cannot actually perform an action from this chat turn, say what is missing without pretending. "
    + "Mention Sub-Engels, phones, shared room files, Rust background, local models, or RunPod only as Engel capabilities, never as separate products. "
    + "Avoid generic setup language. Avoid saying you are a model. Avoid listing features unless the user asks. "
    + "Keep the first response compact, useful, and direct. For proof, talk about real receipt files only when they exist; do not invent log folders, fake screenshots, fake training, or fake completed work. Avoid apology filler."
)

BUILD_PROMPTS = [
    {
        "name": "plain_engel_greeting",
        "prompt": "The operator opens Engel chat and says: hello. Reply as Engel in two short sentences.",
    },
    {
        "name": "confused_ui_repair",
        "prompt": "The operator says: this is big and confusing and not easy to chat with. Reply as Engel, not as a developer.",
    },
    {
        "name": "proof_honesty",
        "prompt": "The operator says: prove this actually ran. Reply as Engel in two short sentences. Say real proof comes from receipt files/results that actually exist. Do not mention log folders.",
    },
]


class BuildError(RuntimeError):
    pass


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    if is_os_drive(path):
        raise BuildError(f"refusing to write standalone chat LLM file on C: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def score_reply(text: str) -> dict[str, Any]:
    stripped = text.strip()
    lowered = stripped.lower()
    banned_hits = [term for term in BANNED_IDENTITY_TERMS if term in lowered]
    checks = {
        "nonempty": bool(stripped),
        "mentions_engel": "engel" in lowered,
        "no_wrong_identity": not banned_hits,
        "not_code_dump": "```" not in stripped and "def " not in lowered and "import " not in lowered,
        "uses_receipt_proof_language_when_relevant": ("prove" not in lowered and "proof" not in lowered) or ("receipt" in lowered or "result" in lowered),
        "bounded": len(stripped) <= 900,
    }
    return {"ok": all(checks.values()), "checks": checks, "banned_hits": banned_hits}


def extract_reply(data: dict[str, Any]) -> str:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if isinstance(message, dict):
        return str(message.get("content") or "").strip()
    return ""


def run_build(*, timeout: int) -> dict[str, Any]:
    engel_home = ensure_runtime_env()
    runtime = load_engel_runtime()
    config = load_config()
    local_model_path = str(config.get("local_gguf_model_path") or "").strip()
    local_model_present = bool(local_model_path and Path(local_model_path).exists())
    stamp = utc_stamp()
    workspace_receipt_path = WORKSPACE_RECEIPT_DIR / f"ENGEL_STANDALONE_CHAT_LLM_BUILD_{stamp}.json"
    external_receipt_path = EXTERNAL_RECEIPT_DIR / f"ENGEL_STANDALONE_CHAT_LLM_BUILD_{stamp}.json"

    receipt: dict[str, Any] = {
        "ok": False,
        "schema": "engel_standalone_chat_llm_build_v1",
        "updated_at_utc": iso_now(),
        "build_kind": "standalone Engel chat LLM profile and live RunPod voice validation",
        "weights_finetuned": False,
        "weights_finetune_claim": "No fake fine-tune is claimed; this builds Engel's standalone chat profile and validates it with live RunPod LLM responses.",
        "provider": "runpod-engel",
        "runtime_provider": runtime.get("provider"),
        "requested_provider": runtime.get("requested_provider"),
        "base_url": runtime.get("base_url"),
        "model": runtime.get("model"),
        "local_gguf_model_path": local_model_path,
        "local_gguf_model_present": local_model_present,
        "engel_home": str(engel_home),
        "system_prompt": ENGEL_STANDALONE_SYSTEM_PROMPT,
        "profile_path": str(WORKSPACE_PROFILE_PATH),
        "external_profile_path": str(EXTERNAL_PROFILE_PATH),
        "workspace_receipt_path": str(workspace_receipt_path),
        "external_receipt_path": str(external_receipt_path),
        "api_key_present": bool(runtime.get("api_key")),
        "api_key_value_visible": False,
        "c_drive_used": False,
        "validation_turns": [],
        "errors": [],
    }

    base_url = str(runtime.get("base_url") or "").strip().rstrip("/")
    api_key = str(runtime.get("api_key") or "").strip()
    model = str(runtime.get("model") or "").strip()
    for spec in BUILD_PROMPTS:
        started = time.perf_counter()
        turn: dict[str, Any] = {
            "name": spec["name"],
            "prompt_chars": len(spec["prompt"]),
            "ok": False,
            "reply": "",
            "latency_ms": 0,
        }
        try:
            data = openai_post(
                base_url,
                api_key,
                {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": ENGEL_STANDALONE_SYSTEM_PROMPT},
                        {"role": "user", "content": spec["prompt"]},
                    ],
                    "temperature": 0.25,
                    "max_tokens": 220,
                },
                timeout,
            )
            reply = extract_reply(data)
            turn["reply"] = reply
            turn["latency_ms"] = int((time.perf_counter() - started) * 1000)
            turn["score"] = score_reply(reply)
            turn["ok"] = bool(turn["score"]["ok"])
            usage = data.get("usage")
            if isinstance(usage, dict):
                turn["usage"] = usage
        except Exception as exc:
            turn["latency_ms"] = int((time.perf_counter() - started) * 1000)
            turn["error"] = str(exc)
        receipt["validation_turns"].append(turn)
        if not turn.get("ok"):
            receipt["errors"].append({"turn": spec["name"], "error": turn.get("error") or turn.get("score")})

    receipt["passed_validation_turn_count"] = sum(1 for turn in receipt["validation_turns"] if turn.get("ok") is True)
    receipt["validation_turn_count"] = len(receipt["validation_turns"])
    receipt["ok"] = (
        receipt["validation_turn_count"] > 0
        and receipt["passed_validation_turn_count"] == receipt["validation_turn_count"]
        and bool(model)
    )

    profile = {
        "ok": bool(receipt["ok"]),
        "schema": "engel_standalone_chat_llm_profile_v1",
        "updated_at_utc": receipt["updated_at_utc"],
        "name": "Engel AI Standalone Chat LLM",
        "description": "Engel's normal chat brain for the main UI: conversational answer first, receipts available behind the scenes.",
        "provider": "runpod-engel",
        "model": model,
        "base_url": base_url,
        "local_gguf_model_path": local_model_path,
        "local_gguf_model_present": local_model_present,
        "weights_finetuned": False,
        "system_prompt": ENGEL_STANDALONE_SYSTEM_PROMPT,
        "forbidden_identity_terms": BANNED_IDENTITY_TERMS,
        "style_contract": [
            "Talk as Engel AI Main, not as code or infrastructure.",
            "Answer in normal chat language.",
            "Use proof language only when proof is relevant.",
            "Do not claim unrun work.",
            "Do not expose backend command details unless asked.",
        ],
        "build_receipt_path": str(workspace_receipt_path),
        "external_build_receipt_path": str(external_receipt_path),
        "api_key_value_visible": False,
        "c_drive_used": False,
    }

    write_json(WORKSPACE_PROFILE_PATH, profile)
    write_json(EXTERNAL_PROFILE_PATH, profile)
    write_json(workspace_receipt_path, receipt)
    write_json(external_receipt_path, receipt)
    latest_path = WORKSPACE_PROFILE_DIR / "latest_build_receipt.json"
    write_json(latest_path, receipt)
    return receipt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build Engel's standalone chat LLM profile with live RunPod validation.")
    parser.add_argument("--timeout", type=int, default=600)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        receipt = run_build(timeout=max(1, args.timeout))
    except (BuildError, StretchError) as exc:
        print(json.dumps({"ok": False, "error": str(exc), "api_key_value_visible": False}, indent=2))
        return 1
    print(json.dumps(receipt, indent=2))
    return 0 if receipt.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
