from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from engel_vault_paths import engel_memory_path

DEFAULT_ENGEL_HOME = engel_memory_path("F", "engel-home")
DEFAULT_RECEIPT_DIR = engel_memory_path("F", "runpod", "receipts")
DEFAULT_SECRET_PATH = engel_memory_path("F", "secrets", "runpod_api_key.txt")
ENGEL_CHAT_PERSONALITY = (
    "You are Engel AI Main, an agentic desktop assistant for this Windows Engel workspace. "
    "Speak like one clear chat assistant: direct, practical, calm, and plain-spoken. "
    "Keep answers useful and compact unless the user asks for depth. "
    "Be honest about real proof, receipts, limits, and failures. "
    "Do not claim work ran unless it actually ran. "
    "Do not present yourself as another product, provider, model vendor, or cloud host. "
    "Use application, systems, kernel, driver, firmware, script, web, and tooling code creation/modification/explanation/debugging, Sub-Engels, shared-room work, Rust background tools, local models, and remote GPU capacity only as Engel AI capabilities when they are configured. "
    "When the user asks for code or asks whether Engel can create code, answer that Engel AI Main can create code in this workspace and provide the concrete code, patch plan, or next build step requested. "
    "For legitimate kernel, driver, or firmware requests, provide safe minimal skeletons or examples instead of refusing. "
    "Do not say Engel cannot write code, does not write code directly, or only provides guidance. "
    "Do not repeat setup text, memory excerpts, loader output, or previous answers. "
    "Answer the user's current message directly and obey any requested length or format. "
    "Do not switch into training, setup, dataset, code, privacy, or onboarding language unless the current user message explicitly asks for it. "
    "Do not say Ready unless the user asks for that exact word."
)


class StretchError(RuntimeError):
    pass


def is_os_drive(path: Path) -> bool:
    text = str(path).replace("/", "\\").lower()
    return text.startswith("c:\\") or text.startswith("\\\\?\\c:\\")


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def configure_imports() -> None:
    agent_root = ROOT / "engel_agent_main"
    cli_root = agent_root / "engel_cli"
    for path in [str(agent_root), str(cli_root)]:
        if path not in sys.path:
            sys.path.insert(0, path)


def ensure_runtime_env() -> Path:
    engel_home = Path(os.environ.get("ENGEL_HOME") or DEFAULT_ENGEL_HOME)
    if is_os_drive(engel_home):
        raise StretchError(f"refusing ENGEL_HOME on C: {engel_home}")
    engel_home.mkdir(parents=True, exist_ok=True)
    os.environ["ENGEL_HOME"] = str(engel_home)

    os.environ.setdefault("ENGEL_RUNPOD_API_KEY_FILE", str(DEFAULT_SECRET_PATH))
    if not os.environ.get("RUNPOD_API_KEY", "").strip() and DEFAULT_SECRET_PATH.exists():
        os.environ["RUNPOD_API_KEY"] = DEFAULT_SECRET_PATH.read_text(encoding="utf-8-sig").strip()
    return engel_home


def load_engel_runtime() -> dict[str, Any]:
    configure_imports()
    from engel_cli.env_loader import load_engel_dotenv
    from engel_cli.runtime_provider import resolve_runtime_provider

    load_engel_dotenv()
    runtime = resolve_runtime_provider()
    base_url = str(runtime.get("base_url") or "").strip().rstrip("/")
    model = str(runtime.get("model") or "").strip()
    api_key = str(runtime.get("api_key") or "").strip()
    requested = str(runtime.get("requested_provider") or "").strip()
    if requested != "runpod-engel":
        raise StretchError(f"Engel resolver is not using runpod-engel: {requested or '<missing>'}")
    if not base_url.startswith("https://api.runpod.ai/v2/"):
        raise StretchError(f"resolved provider is not RunPod: {base_url or '<missing>'}")
    if not model:
        raise StretchError("resolved RunPod model is missing")
    if not api_key:
        raise StretchError("resolved RunPod API key is missing")
    return runtime


def openai_post(base_url: str, api_key: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    request = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def openai_get_models(base_url: str, api_key: str, timeout: int) -> dict[str, Any]:
    request = urllib.request.Request(
        base_url.rstrip("/") + "/models",
        headers={"Authorization": f"Bearer {api_key}"},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def check_personality_response(text: str) -> bool:
    lowered = text.lower()
    banned = ["hermes", "composio", "alibaba", "qwen", "i ran", "completed training"]
    if any(term in lowered for term in banned):
        return False
    return "engel" in lowered and bool(text.strip()) and len(text.strip()) <= 500

def task_specs() -> list[dict[str, Any]]:
    return [
        {
            "name": "engel_personality_voice",
            "prompt": (
                "Answer as Engel AI in two short sentences. Say what you are for, "
                "and be honest that receipts prove only work that actually ran."
            ),
            "max_tokens": 120,
            "check": check_personality_response,
        },
        {
            "name": "runpod_receipt_honesty",
            "prompt": "In one short sentence, say Engel AI only claims RunPod work when receipts show it really ran.",
            "max_tokens": 80,
            "check": lambda text: "engel" in text.lower() and ("receipt" in text.lower() or "proof" in text.lower()),
        },
        {
            "name": "math_reasoning",
            "prompt": "What is 17 multiplied by 19? Reply with only the number.",
            "max_tokens": 10,
            "check": lambda text: re.search(r"\b323\b", text) is not None,
        },
        {
            "name": "json_contract",
            "prompt": (
                "Return compact JSON only with keys ok, provider, model_ready. "
                "Use ok true, provider runpod-engel, model_ready true."
            ),
            "max_tokens": 80,
            "check": check_json_contract,
        },
        {
            "name": "code_microtask",
            "prompt": "Write only a tiny Python function named add_numbers that returns the sum of a and b.",
            "max_tokens": 80,
            "check": lambda text: "def add_numbers" in text and "return" in text and "+" in text,
        },
        {
            "name": "engel_summary",
            "prompt": "In one short sentence, say Engel AI is using RunPod for remote inference.",
            "max_tokens": 40,
            "check": lambda text: "Engel" in text and "RunPod" in text,
        },
    ]

def check_json_contract(text: str) -> bool:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return False
    return (
        data.get("ok") is True
        and str(data.get("provider") or "").lower() == "runpod-engel"
        and data.get("model_ready") is True
    )


def run_stretch(*, timeout: int, max_tasks: int) -> dict[str, Any]:
    engel_home = ensure_runtime_env()
    receipt_dir = DEFAULT_RECEIPT_DIR
    if is_os_drive(receipt_dir):
        raise StretchError(f"refusing receipt dir on C: {receipt_dir}")
    receipt_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = receipt_dir / f"RUNPOD_ENGEL_STRETCH_{utc_stamp()}.json"

    runtime = load_engel_runtime()
    base_url = str(runtime.get("base_url") or "").strip().rstrip("/")
    model = str(runtime.get("model") or "").strip()
    api_key = str(runtime.get("api_key") or "").strip()

    started = time.perf_counter()
    receipt: dict[str, Any] = {
        "ok": False,
        "schema": "engel_runpod_stretch_v1",
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
        "visible_path": "Engel Main chat -> Rust UI shell bridge -> Engel Agent provider resolver -> RunPod OpenAI-compatible endpoint",
        "engel_home": str(engel_home),
        "provider": "runpod-engel",
        "runtime_provider": runtime.get("provider"),
        "requested_provider": runtime.get("requested_provider"),
        "api_mode": runtime.get("api_mode"),
        "base_url": base_url,
        "model": model,
        "personality": ENGEL_CHAT_PERSONALITY,
        "api_key_present": True,
        "api_key_value_visible": False,
        "receipt_path": str(receipt_path),
        "c_drive_used": False,
        "models_probe": {},
        "tasks": [],
    }

    try:
        models_started = time.perf_counter()
        models_data = openai_get_models(base_url, api_key, timeout)
        model_ids = [
            item.get("id")
            for item in models_data.get("data", [])
            if isinstance(item, dict) and item.get("id")
        ]
        receipt["models_probe"] = {
            "ok": True,
            "model_count": len(model_ids),
            "model_ids": model_ids[:10],
            "latency_ms": int((time.perf_counter() - models_started) * 1000),
        }
    except Exception as exc:
        receipt["models_probe"] = {"ok": False, "error": str(exc)}

    for spec in task_specs()[:max_tasks]:
        prompt = spec["prompt"]
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": ENGEL_CHAT_PERSONALITY},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
            "max_tokens": spec["max_tokens"],
        }
        task_started = time.perf_counter()
        task: dict[str, Any] = {
            "name": spec["name"],
            "ok": False,
            "prompt_chars": len(prompt),
            "response_text": "",
            "latency_ms": 0,
        }
        try:
            data = openai_post(base_url, api_key, payload, timeout)
            text = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            task["response_text"] = str(text).strip()
            task["latency_ms"] = int((time.perf_counter() - task_started) * 1000)
            task["ok"] = bool(spec["check"](task["response_text"]))
            usage = data.get("usage")
            if isinstance(usage, dict):
                task["usage"] = {
                    "prompt_tokens": usage.get("prompt_tokens"),
                    "completion_tokens": usage.get("completion_tokens"),
                    "total_tokens": usage.get("total_tokens"),
                }
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:1000]
            task["error"] = f"HTTP {exc.code}: {body}"
            task["latency_ms"] = int((time.perf_counter() - task_started) * 1000)
        except Exception as exc:
            task["error"] = str(exc)
            task["latency_ms"] = int((time.perf_counter() - task_started) * 1000)
        receipt["tasks"].append(task)

    receipt["elapsed_ms"] = int((time.perf_counter() - started) * 1000)
    receipt["task_count"] = len(receipt["tasks"])
    receipt["passed_task_count"] = sum(1 for task in receipt["tasks"] if task.get("ok") is True)
    receipt["ok"] = (
        receipt["models_probe"].get("ok") is True
        and receipt["task_count"] > 0
        and receipt["passed_task_count"] == receipt["task_count"]
    )
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    return receipt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a live Engel RunPod stretch test.")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--max-tasks", type=int, default=5)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        receipt = run_stretch(timeout=args.timeout, max_tasks=max(1, args.max_tasks))
    except StretchError as exc:
        print(json.dumps({"ok": False, "error": str(exc), "api_key_value_visible": False}, indent=2))
        return 1
    print(json.dumps(receipt, indent=2))
    return 0 if receipt.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())



