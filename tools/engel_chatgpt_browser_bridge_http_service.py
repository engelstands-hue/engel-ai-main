#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import traceback
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import engel_chatgpt_browser_worker  # noqa: E402

REPORT_DIR = ROOT / "reports" / "chatgpt_browser_bridge"
DEFAULT_TIMEOUT_SECONDS = int(float(os.environ.get("ENGEL_CHATGPT_BROWSER_BRIDGE_TIMEOUT_SECONDS", "180") or "180"))


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def _clip(value: Any, limit: int = 4000) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[:limit] + "...[clipped]"


def _read_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length") or "0")
    if length <= 0:
        return {}
    parsed = json.loads(handler.rfile.read(length).decode("utf-8-sig", errors="replace"))
    if not isinstance(parsed, dict):
        raise ValueError("JSON body must be an object")
    return parsed


def _plain_chat_prompt_from_request(request: dict[str, Any]) -> str:
    return str(request.get("prompt") or request.get("message") or "").strip()


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Access-Control-Allow-Origin", "http://127.0.0.1")
    handler.end_headers()
    handler.wfile.write(body)


def _prompt_from_completion_request(request: dict[str, Any]) -> str:
    messages = request.get("messages")
    if not isinstance(messages, list):
        return str(request.get("prompt") or "").strip()
    parts: list[str] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        role = str(message.get("role") or "user").strip() or "user"
        content = message.get("content")
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            text = "\n".join(
                str(part.get("text") or "").strip()
                for part in content
                if isinstance(part, dict) and str(part.get("text") or "").strip()
            )
        else:
            text = ""
        if text.strip():
            parts.append(f"{role}: {text.strip()}")
    return "\n\n".join(parts).strip()


def _bridge_status() -> dict[str, Any]:
    worker = engel_chatgpt_browser_worker.status_payload()
    py = Path(str(worker.get("browser_python_path") or ""))
    return {
        "schema": "engel_chatgpt_browser_bridge_status_v1",
        "ok": py.is_file() or bool(worker.get("worker_running")),
        "provider": "openai",
        "provider_label": "ChatGPT browser worker on ROG",
        "route": "CT 246 -> SSH reverse tunnel -> ROG local ChatGPT browser worker",
        "root": str(ROOT),
        "oauth_tokens_exposed": False,
        "writes_secrets": False,
        "chat_only": True,
        "worker_running": bool(worker.get("worker_running")),
        "worker_pid": worker.get("worker_pid"),
        "worker_status": worker,
        "updated_at_utc": _iso_now(),
    }


def _send_chatgpt(prompt: str, request: dict[str, Any], started: float) -> dict[str, Any]:
    # Floor is 45s (not 15s): a cold browser reconnect costs ~40s (Chromium
    # launch + page.goto), and a 15s floor returned a false 502 while the worker
    # kept going and orphaned an ok:true reply ~25s later. 45s lets one reconnect
    # finish and return the real answer.
    timeout = max(45, min(300, int(float(request.get("timeout_seconds") or DEFAULT_TIMEOUT_SECONDS))))
    max_tokens = max(80, min(1600, int(request.get("max_tokens") or request.get("max_completion_tokens") or 420)))
    result = engel_chatgpt_browser_worker.send_chatgpt_browser_prompt(
        prompt=prompt,
        personality=str(request.get("personality") or ""),
        trusted_memory=str(request.get("trusted_memory") or request.get("system_prompt") or ""),
        timeout=timeout,
        max_tokens=max_tokens,
    )
    reply = str(result.get("assistant_reply") or "").strip()
    result["latency_ms"] = int((time.perf_counter() - started) * 1000)
    result["assistant_reply"] = reply
    result["assistant_output_text"] = reply
    result["provider"] = "ChatGPT browser worker on ROG"
    result["runtime_provider"] = "chatgpt-browser-ui"
    return result


def _write_receipt(prompt: str, result: dict[str, Any]) -> str:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"ENGEL_CHATGPT_BROWSER_BRIDGE_CHAT_{_stamp()}.json"
    payload = {
        "schema": "engel_chatgpt_browser_bridge_chat_receipt_v1",
        "ok": result.get("ok") is True,
        "updated_at_utc": _iso_now(),
        "prompt": prompt,
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "prompt_chars": len(prompt),
        "assistant_reply": result.get("assistant_reply", ""),
        "provider": result.get("provider", "ChatGPT browser worker on ROG"),
        "runtime_provider": result.get("runtime_provider", ""),
        "status": result.get("status", ""),
        "latency_ms": result.get("latency_ms"),
        "oauth_tokens_exposed": False,
        "secret_values_written": False,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(path)


def _completion_response(reply: str, result: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "chatcmpl-engel-chatgpt-browser-" + _stamp(),
        "object": "chat.completion",
        "created": int(time.time()),
        "model": "chatgpt-browser-ui",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": reply}, "finish_reason": "stop"}],
        "engel": {
            "ok": result.get("ok") is True,
            "provider": result.get("provider", "ChatGPT browser worker on ROG"),
            "runtime_provider": result.get("runtime_provider", "chatgpt-browser-ui"),
        },
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "EngelChatGPTBrowserBridge/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("[%s] %s\n" % (_iso_now(), fmt % args))
        sys.stderr.flush()

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        if path in {"/", "/health", "/status"}:
            _json_response(self, 200, _bridge_status())
            return
        _json_response(self, 404, {"ok": False, "status": "not found", "path": self.path})

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        if path not in {"/chat", "/v1/chat/completions"}:
            _json_response(self, 404, {"ok": False, "status": "not found", "path": self.path})
            return
        started = time.perf_counter()
        try:
            request = _read_json(self)
            prompt = _prompt_from_completion_request(request) if path == "/v1/chat/completions" else _plain_chat_prompt_from_request(request)
            if not prompt:
                raise ValueError("prompt is empty")
            result = _send_chatgpt(prompt, request, started)
            result["receipt_path"] = _write_receipt(prompt, result)
            if path == "/v1/chat/completions":
                _json_response(self, 200 if result.get("ok") is True else 502, _completion_response(str(result.get("assistant_reply") or ""), result))
                return
            payload = {
                "schema": "engel_chatgpt_browser_bridge_chat_response_v1",
                "ok": result.get("ok") is True,
                "status": result.get("status", ""),
                "assistant_reply": result.get("assistant_reply", ""),
                "provider": result.get("provider", ""),
                "runtime_provider": result.get("runtime_provider", ""),
                "receipt": result,
                "updated_at_utc": _iso_now(),
            }
            _json_response(self, 200 if payload["ok"] else 502, payload)
        except Exception as exc:
            _json_response(
                self,
                500,
                {
                    "schema": "engel_chatgpt_browser_bridge_chat_response_v1",
                    "ok": False,
                    "status": "ChatGPT browser bridge service error",
                    "error": _clip(str(exc), 1000),
                    "traceback_tail": traceback.format_exc()[-2000:],
                    "updated_at_utc": _iso_now(),
                },
            )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Engel ROG-local ChatGPT browser HTTP bridge.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=24884)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Engel ChatGPT browser bridge listening on {args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
