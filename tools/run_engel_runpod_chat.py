from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
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

WORKSPACE_RECEIPT_DIR = ROOT / "reports" / "engel_runpod_chat" / "receipts"
EXTERNAL_RECEIPT_DIR = engel_memory_path("F", "runpod", "chat_receipts")


class ChatBridgeError(RuntimeError):
    pass


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    if is_os_drive(path):
        raise ChatBridgeError(f"refusing to write chat receipt on C: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def extract_reply(data: dict[str, Any]) -> str:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if content is not None:
            return str(content).strip()
    text = first.get("text")
    return str(text).strip() if text is not None else ""


def build_receipt(prompt: str, timeout: int, max_tokens: int, temperature: float) -> dict[str, Any]:
    if not prompt.strip():
        raise ChatBridgeError("prompt is empty")

    engel_home = ensure_runtime_env()
    runtime = load_engel_runtime()
    base_url = str(runtime.get("base_url") or "").strip().rstrip("/")
    model = str(runtime.get("model") or "").strip()
    api_key = str(runtime.get("api_key") or "").strip()
    stamp = utc_stamp()
    workspace_receipt_path = WORKSPACE_RECEIPT_DIR / f"ENGEL_RUNPOD_CHAT_{stamp}.json"
    external_receipt_path = EXTERNAL_RECEIPT_DIR / f"ENGEL_RUNPOD_CHAT_{stamp}.json"

    receipt: dict[str, Any] = {
        "ok": False,
        "schema": "engel_runpod_chat_reply_v1",
        "updated_at_utc": iso_now(),
        "provider": "runpod-engel",
        "runtime_provider": runtime.get("provider"),
        "requested_provider": runtime.get("requested_provider"),
        "api_mode": runtime.get("api_mode"),
        "base_url": base_url,
        "model": model,
        "engel_home": str(engel_home),
        "prompt_chars": len(prompt),
        "assistant_reply": "",
        "assistant_output_text": "",
        "readable_output_captured": False,
        "api_key_present": bool(api_key),
        "api_key_value_visible": False,
        "c_drive_used": False,
        "workspace_receipt_path": str(workspace_receipt_path),
        "external_receipt_path": str(external_receipt_path),
        "latency_ms": 0,
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": ENGEL_CHAT_PERSONALITY},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    started = time.perf_counter()
    try:
        data = openai_post(base_url, api_key, payload, timeout)
        reply = extract_reply(data)
        receipt["latency_ms"] = int((time.perf_counter() - started) * 1000)
        receipt["assistant_reply"] = reply
        receipt["assistant_output_text"] = reply
        receipt["readable_output_captured"] = bool(reply)
        receipt["status"] = "chat replied" if reply else "chat no readable answer"
        receipt["ok"] = bool(reply)
        usage = data.get("usage")
        if isinstance(usage, dict):
            receipt["usage"] = {
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "total_tokens": usage.get("total_tokens"),
            }
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:1000]
        receipt["latency_ms"] = int((time.perf_counter() - started) * 1000)
        receipt["status"] = "runpod http error"
        receipt["error"] = f"HTTP {exc.code}: {body}"
    except Exception as exc:
        receipt["latency_ms"] = int((time.perf_counter() - started) * 1000)
        receipt["status"] = "runpod chat error"
        receipt["error"] = str(exc)

    write_json(workspace_receipt_path, receipt)
    write_json(external_receipt_path, receipt)
    return receipt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run one live Engel RunPod chat turn.")
    parser.add_argument("prompt", nargs="?", default="")
    parser.add_argument("--prompt", dest="prompt_option", default="")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--max-tokens", type=int, default=360)
    parser.add_argument("--temperature", type=float, default=0.2)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    prompt = (args.prompt_option or args.prompt or "").strip()
    try:
        receipt = build_receipt(
            prompt=prompt,
            timeout=max(1, args.timeout),
            max_tokens=max(1, args.max_tokens),
            temperature=args.temperature,
        )
    except (ChatBridgeError, StretchError) as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "schema": "engel_runpod_chat_reply_v1",
                    "status": "chat bridge blocked",
                    "error": str(exc),
                    "api_key_value_visible": False,
                },
                indent=2,
            )
        )
        return 1
    print(json.dumps(receipt, indent=2))
    return 0 if receipt.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
