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
import urllib.error
import urllib.parse
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports" / "gemini_api_bridge"
PROVIDER_BRIDGE_ENV_FILE = Path(
    os.environ.get("ENGEL_PROVIDER_BRIDGE_ENV_FILE", str(ROOT / "run" / "secrets" / "provider_bridges.env"))
)
CONNECTOR_PROFILE_PATH = ROOT / "runtime" / "connector_profiles" / "providers" / "gemini.json"
SECRET_NAMES = [
    "ENGEL_GEMINI_API_KEY",
    "GEMINI_API_KEY",
    "ENGEL_GOOGLE_API_KEY",
    "GOOGLE_API_KEY",
    "GOOGLE_GENAI_API_KEY",
    "GENAI_API_KEY",
    "GOOGLE_GENERATIVE_AI_API_KEY",
    "ENGEL_GOOGLE_GENAI_API_KEY",
    "ENGEL_GOOGLE_GENERATIVE_AI_API_KEY",
    "GOOGLE_AI_API_KEY",
    "ENGEL_GOOGLE_AI_API_KEY",
]
MODEL_ENV_NAMES = [
    "ENGEL_GEMINI_CHAT_MODEL",
    "ENGEL_GOOGLE_CHAT_MODEL",
    "GEMINI_MODEL",
    "GOOGLE_MODEL",
    "GOOGLE_GENAI_MODEL",
]
# gemini-1.5-flash is retired (404 on v1beta) and gemini-2.0-flash returns
# free_tier limit:0 on many keys. gemini-2.5-flash is the current free-tier
# flash and gemini-flash-latest auto-tracks Google's newest flash, so the lane
# keeps working as models rotate. 2.0-flash stays last for keys with paid quota.
MODEL_FALLBACKS = ["gemini-2.5-flash", "gemini-flash-latest", "gemini-2.0-flash"]
GENERATE_CONTENT_URL_TEMPLATE = os.environ.get(
    "ENGEL_GEMINI_GENERATE_CONTENT_URL_TEMPLATE",
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
).strip()
DEFAULT_TIMEOUT_SECONDS = float(os.environ.get("ENGEL_GEMINI_API_REQUEST_TIMEOUT_SECONDS", "60") or "60")


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def _clip(value: Any, limit: int = 4000) -> str:
    text = str(value or "")
    return text if len(text) <= limit else text[:limit] + "...[clipped]"


def _read_env_file() -> dict[str, str]:
    values: dict[str, str] = {}
    if not PROVIDER_BRIDGE_ENV_FILE.is_file():
        return values
    try:
        for raw in PROVIDER_BRIDGE_ENV_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            name = name.strip()
            value = value.strip().strip('"').strip("'")
            if name:
                values[name] = value
    except Exception:
        return values
    return values


def _read_windows_registry_env(names: list[str]) -> dict[str, tuple[str, str]]:
    if os.name != "nt":
        return {}
    try:
        import winreg  # type: ignore
    except Exception:
        return {}
    locations = [
        ("user_env_registry", winreg.HKEY_CURRENT_USER, r"Environment"),
        (
            "machine_env_registry",
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
        ),
    ]
    values: dict[str, tuple[str, str]] = {}
    for source_type, hive, subkey in locations:
        try:
            with winreg.OpenKey(hive, subkey) as key:
                for name in names:
                    if name in values:
                        continue
                    try:
                        value, _kind = winreg.QueryValueEx(key, name)
                    except OSError:
                        continue
                    text = str(value or "").strip()
                    if text:
                        values[name] = (text, source_type)
        except OSError:
            continue
    return values


def _read_connector_profile() -> dict[str, Any]:
    try:
        if not CONNECTOR_PROFILE_PATH.is_file():
            return {}
        data = json.loads(CONNECTOR_PROFILE_PATH.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _public_connector_profile(profile: dict[str, Any], secret_present: bool) -> dict[str, Any]:
    if not profile:
        return {
            "present": False,
            "path": str(CONNECTOR_PROFILE_PATH),
            "stale": False,
            "secret_backed": False,
        }
    live_verified = bool(profile.get("live_verified") is True)
    stale = live_verified and not secret_present
    return {
        "present": True,
        "path": str(CONNECTOR_PROFILE_PATH),
        "status": str(profile.get("status") or ""),
        "env_name": str(profile.get("env_name") or ""),
        "live_verified": live_verified,
        "live_verify_state": str(profile.get("live_verify_state") or ""),
        "live_verify_code": int(profile.get("live_verify_code") or 0),
        "live_verified_at_utc": str(profile.get("live_verified_at_utc") or ""),
        "secret_backed": secret_present,
        "stale": stale,
        "warning": "connector profile says verified but no Gemini key is reachable" if stale else "",
    }


def _secret_source() -> dict[str, Any]:
    for name in SECRET_NAMES:
        value = os.environ.get(name, "")
        if value:
            return {
                "present": True,
                "secret": value,
                "source_type": "process_env",
                "name": name,
                "path": "",
                "value_length": len(value),
            }
    registry_values = _read_windows_registry_env(SECRET_NAMES)
    for name in SECRET_NAMES:
        found = registry_values.get(name)
        if not found:
            continue
        value, source_type = found
        return {
            "present": True,
            "secret": value,
            "source_type": source_type,
            "name": name,
            "path": "",
            "value_length": len(value),
        }
    env_values = _read_env_file()
    for name in SECRET_NAMES:
        value = env_values.get(name, "")
        if value:
            return {
                "present": True,
                "secret": value,
                "source_type": "env_file",
                "name": name,
                "path": str(PROVIDER_BRIDGE_ENV_FILE),
                "value_length": len(value),
            }
    return {"present": False, "secret": "", "source_type": "", "name": "", "path": "", "value_length": 0}


def _public_secret_source(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "present": bool(source.get("present") is True),
        "source_type": source.get("source_type", ""),
        "name": source.get("name", ""),
        "path": source.get("path", ""),
        "value_length": int(source.get("value_length") or 0),
    }


def _model_candidates(request: dict[str, Any] | None = None) -> list[str]:
    candidates: list[str] = []
    if isinstance(request, dict):
        requested = str(request.get("model") or request.get("provider_model") or "").strip()
        if requested:
            candidates.append(requested)
    registry_values = _read_windows_registry_env(MODEL_ENV_NAMES)
    for name in MODEL_ENV_NAMES:
        value = str(os.environ.get(name) or "").strip()
        if not value and name in registry_values:
            value = str(registry_values[name][0] or "").strip()
        if value:
            candidates.append(value)
    candidates.extend(MODEL_FALLBACKS)
    deduped: list[str] = []
    for item in candidates:
        if item and item not in deduped:
            deduped.append(item)
    return deduped


def _read_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length") or "0")
    if length <= 0:
        return {}
    body = handler.rfile.read(length).decode("utf-8-sig", errors="replace")
    parsed = json.loads(body)
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


def _system_prompt(prompt: str, request: dict[str, Any]) -> str:
    instruction = str(request.get("system") or request.get("system_prompt") or "").strip()
    base = (
        "Reply as Engel AI Main through the Gemini bridge. "
        "Do not claim you edited files, launched tools, or completed hidden work. "
        "Use Gemini for Google/long-context/general reasoning only. "
        "Keep the answer direct, conversational, and non-repetitive."
    )
    if instruction:
        base += " " + instruction.replace("\r", " ").replace("\n", " ")
    return base


def _provider_http_json(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: float) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            parsed = json.loads(resp.read().decode("utf-8", errors="replace"))
        return {"ok": True, "status_code": 200, "json": parsed if isinstance(parsed, dict) else {}}
    except urllib.error.HTTPError as exc:
        try:
            error_body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            error_body = ""
        return {"ok": False, "status_code": exc.code, "error": _clip(error_body or str(exc), 1400)}
    except Exception as exc:
        return {"ok": False, "status_code": 0, "error": _clip(str(exc), 1400)}


def _bridge_status() -> dict[str, Any]:
    source = _secret_source()
    profile = _read_connector_profile()
    secret_present = bool(source.get("present") is True)
    return {
        "schema": "engel_gemini_api_bridge_status_v1",
        "ok": True,
        "enabled": True,
        "usable": secret_present,
        "provider": "gemini",
        "provider_label": "Gemini API bridge on ROG",
        "root": str(ROOT),
        "env_file_present": PROVIDER_BRIDGE_ENV_FILE.is_file(),
        "secret_present": secret_present,
        "secret_source": _public_secret_source(source),
        "accepted_secret_names": SECRET_NAMES,
        "connector_profile": _public_connector_profile(profile, secret_present),
        "model_candidates": _model_candidates({}),
        "oauth_tokens_exposed": False,
        "writes_secrets": False,
        "chat_only": True,
        "updated_at_utc": _iso_now(),
    }


def _run_gemini(prompt: str, request: dict[str, Any], started: float) -> dict[str, Any]:
    source = _secret_source()
    if source.get("present") is not True:
        return {
            "ok": False,
            "status": "Gemini API key missing",
            "assistant_reply": "",
            "provider": "Gemini API bridge on ROG",
            "runtime_provider": "",
            "selected_provider": "gemini_api_bridge",
            "model": "",
            "error": "Gemini profile exists, but no reachable Gemini key was found. Set ENGEL_GEMINI_API_KEY/GEMINI_API_KEY/GOOGLE_API_KEY or another accepted Gemini key name on the laptop or in run/secrets/provider_bridges.env.",
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }
    secret = str(source.get("secret") or "")
    max_tokens = max(32, min(16384, int(request.get("max_tokens") or request.get("max_completion_tokens") or 500)))
    temperature = float(request.get("temperature") or 0.35)
    timeout = max(10.0, min(180.0, float(request.get("timeout_seconds") or DEFAULT_TIMEOUT_SECONDS)))
    attempts: list[dict[str, Any]] = []
    for model in _model_candidates(request):
        safe_model = urllib.parse.quote(model, safe="-_.")
        url = GENERATE_CONTENT_URL_TEMPLATE.format(model=safe_model)
        generation_config: dict[str, Any] = {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        }
        if request.get("thinking_budget") is not None:
            generation_config["thinkingConfig"] = {
                "thinkingBudget": int(request.get("thinking_budget") or 0)
            }
        payload = {
            "systemInstruction": {"parts": [{"text": _system_prompt(prompt, request)}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": generation_config,
        }
        result = _provider_http_json(url, payload, {"x-goog-api-key": secret}, timeout)
        attempts.append(
            {
                "provider": "gemini",
                "model": model,
                "ok": result.get("ok"),
                "status_code": result.get("status_code"),
                "error": result.get("error", ""),
            }
        )
        if not result.get("ok"):
            continue
        data = result.get("json") if isinstance(result.get("json"), dict) else {}
        candidates = data.get("candidates") if isinstance(data.get("candidates"), list) else []
        content = candidates[0].get("content") if candidates and isinstance(candidates[0], dict) else {}
        parts = content.get("parts") if isinstance(content, dict) and isinstance(content.get("parts"), list) else []
        reply = "\n".join(
            str(part.get("text") or "").strip()
            for part in parts
            if isinstance(part, dict) and str(part.get("text") or "").strip()
        ).strip()
        if reply:
            return {
                "ok": True,
                "status": "Gemini API replied",
                "assistant_reply": reply,
                "assistant_output_text": reply,
                "provider": "Gemini API bridge on ROG",
                "runtime_provider": model,
                "selected_provider": "gemini_api_bridge",
                "model": model,
                "attempts": attempts,
                "latency_ms": int((time.perf_counter() - started) * 1000),
            }
    return {
        "ok": False,
        "status": "Gemini API did not return a usable reply",
        "assistant_reply": "",
        "provider": "Gemini API bridge on ROG",
        "runtime_provider": "",
        "selected_provider": "gemini_api_bridge",
        "model": "",
        "attempts": attempts,
        "error": attempts[-1].get("error", "") if attempts else "no model candidates",
        "latency_ms": int((time.perf_counter() - started) * 1000),
    }


def _write_receipt(prompt: str, result: dict[str, Any]) -> str:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"ENGEL_GEMINI_API_BRIDGE_CHAT_{_stamp()}.json"
    payload = {
        "schema": "engel_gemini_api_bridge_chat_receipt_v1",
        "ok": result.get("ok") is True,
        "updated_at_utc": _iso_now(),
        "prompt": prompt,
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "prompt_chars": len(prompt),
        "assistant_reply": result.get("assistant_reply", ""),
        "provider": result.get("provider", "Gemini API bridge on ROG"),
        "runtime_provider": result.get("runtime_provider", ""),
        "status": result.get("status", ""),
        "error": result.get("error", ""),
        "attempts": result.get("attempts", []),
        "latency_ms": result.get("latency_ms"),
        "secret_values_written": False,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(path)


def _completion_response(request: dict[str, Any], reply: str, result: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "chatcmpl-engel-gemini-api-" + _stamp(),
        "object": "chat.completion",
        "created": int(time.time()),
        "model": result.get("model") or "",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": reply}, "finish_reason": "stop"}],
        "engel": {
            "ok": result.get("ok") is True,
            "provider": result.get("provider", "Gemini API bridge on ROG"),
            "runtime_provider": result.get("runtime_provider", ""),
        },
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "EngelGeminiApiBridge/1.0"

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
            result = _run_gemini(prompt, request, started)
            result["receipt_path"] = _write_receipt(prompt, result)
            if path == "/v1/chat/completions":
                _json_response(self, 200 if result.get("ok") is True else 502, _completion_response(request, str(result.get("assistant_reply") or ""), result))
                return
            payload = {
                "schema": "engel_gemini_api_bridge_chat_response_v1",
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
                    "schema": "engel_gemini_api_bridge_chat_response_v1",
                    "ok": False,
                    "status": "Gemini API bridge service error",
                    "error": str(exc),
                    "traceback_tail": traceback.format_exc()[-2000:],
                    "updated_at_utc": _iso_now(),
                },
            )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Engel ROG-local Gemini API HTTP bridge.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=24886)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Engel Gemini API bridge listening on {args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
