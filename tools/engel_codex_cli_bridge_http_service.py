#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import shutil
import subprocess
import sys
import threading
import time
import traceback
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports" / "codex_cli_bridge"
OUTPUT_DIR = ROOT / "runtime" / "codex_cli_bridge"
ARTIFACT_WORKSPACE = ROOT / "runtime" / "codex_cli_artifact_workspace"
CHAT_WORKSPACE = Path(
    os.environ.get("ENGEL_CODEX_CLI_CHAT_WORKSPACE", str(ROOT))
)
DEFAULT_TIMEOUT_SECONDS = float(os.environ.get("ENGEL_CODEX_CLI_REQUEST_TIMEOUT_SECONDS", "120") or "120")
# gpt-5.4 was retired for ChatGPT-account Codex (probed 2026-08-01: the API
# rejects it outright); gpt-5.5 and gpt-5.4-mini are the supported slugs.
DEFAULT_MODEL = os.environ.get("ENGEL_CODEX_CLI_MODEL", "gpt-5.5").strip() or "gpt-5.5"
DEFAULT_SANDBOX = os.environ.get("ENGEL_CODEX_CLI_SANDBOX", "read-only").strip() or "read-only"
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def _clip(value: Any, limit: int = 4000) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[:limit] + "...[clipped]"


def _strip_ansi(value: str) -> str:
    return ANSI_RE.sub("", value).replace("\r\n", "\n").replace("\r", "\n").strip()


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


def _codex_exe_path() -> Path:
    def coerce_windows_executable(path: Path) -> Path:
        if os.name != "nt":
            return path
        try:
            if path.suffix.lower() != ".ps1":
                return path
            for suffix in (".cmd", ".exe"):
                sibling = path.with_suffix(suffix)
                if sibling.is_file():
                    return sibling
        except OSError:
            return path
        return path

    configured = os.environ.get("ENGEL_CODEX_CLI_EXE", "").strip()
    if configured:
        path = coerce_windows_executable(Path(configured))
        if path.is_file():
            return path

    for command_name in ("codex.cmd", "codex.exe", "codex"):
        found = shutil.which(command_name)
        if found:
            path = coerce_windows_executable(Path(found))
            if path.is_file():
                return path

    candidates = [
        ROOT / "runtime" / "codex" / "codex.exe",
        Path(r"D:\npm-global\codex.cmd"),
        Path(r"C:\Users\ziese\AppData\Roaming\npm\codex.cmd"),
    ]
    vscode_extensions = Path.home() / ".vscode" / "extensions"
    if vscode_extensions.is_dir():
        candidates.extend(
            sorted(
                vscode_extensions.glob("openai.chatgpt-*/bin/windows-x86_64/codex.exe"),
                key=lambda item: item.stat().st_mtime if item.exists() else 0,
                reverse=True,
            )
        )
    for candidate in candidates:
        try:
            path = coerce_windows_executable(candidate)
            if path.is_file():
                return path
        except OSError:
            continue
    return coerce_windows_executable(Path(configured or "codex"))


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


def _engel_prompt(prompt: str, request: dict[str, Any]) -> str:
    instruction = str(request.get("system") or request.get("system_prompt") or "").strip()
    if request.get("artifact_only") is True:
        base = (
            "You are Engel AI Main's bounded artifact generator. Do not inspect the "
            "filesystem, repository, git state, tools, services, or environment. Do not "
            "run commands. Generate the requested artifact directly from the supplied "
            "prompt. Obey its FILE markers and fenced-code output protocol exactly. "
            "Return only the requested file bodies with no planning narration."
        )
    else:
        base = (
            "You are Codex integrated into Engel AI Main as the code, architecture, "
            "debugging, and repository reasoning lane.\n"
            "Reply as Engel AI Main speaking to Joshua. Do not say you are a separate app "
            "unless Joshua asks which bridge handled the turn.\n"
            "This bridge is read-only by default. Do not edit files, install packages, "
            "launch services, or claim you changed the machine unless the prompt includes "
            "explicit approval and proof that Engel's approval gates allow it.\n"
            "Be concrete and concise. Prefer exact file names, routes, and next checks over "
            "generic advice. Avoid repeated template responses."
        )
    if instruction:
        base += "\n\nEngel context:\n" + instruction
    return f"{base}\n\nJoshua's request:\n{prompt}\n\nCodex lane reply:"


def _terminate_process_tree(process: subprocess.Popen[str]) -> bool:
    if process.poll() is not None:
        return True
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        else:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)
    except Exception:
        try:
            process.kill()
            process.wait(timeout=5)
        except Exception:
            pass
    return process.poll() is not None


def _run_codex_process(
    args: list[str],
    *,
    input_text: str,
    cwd: Path,
    env: dict[str, str],
    timeout: float,
) -> dict[str, Any]:
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    popen_kwargs: dict[str, Any] = {}
    if os.name == "nt":
        creationflags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        popen_kwargs["start_new_session"] = True
    process = subprocess.Popen(
        args,
        cwd=str(cwd),
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=creationflags,
        **popen_kwargs,
    )
    try:
        stdout, stderr = process.communicate(input=input_text, timeout=timeout)
        return {
            "timed_out": False,
            "returncode": process.returncode,
            "stdout": stdout or "",
            "stderr": stderr or "",
            "process_pid": process.pid,
            "process_tree_terminated": False,
        }
    except subprocess.TimeoutExpired:
        terminated = _terminate_process_tree(process)
        try:
            stdout, stderr = process.communicate(timeout=5)
        except Exception:
            stdout, stderr = "", ""
        return {
            "timed_out": True,
            "returncode": process.returncode,
            "stdout": stdout or "",
            "stderr": stderr or "",
            "process_pid": process.pid,
            "process_tree_terminated": terminated,
        }


# `codex --version` costs a real subprocess, and on Windows the CLI resolves to a
# .cmd shim -- so Python must go through cmd.exe. With Windows Terminal as the
# default console host, that console is handed off via DCOM and SHOWS A WINDOW even
# under CREATE_NO_WINDOW, so every status poll flashed a terminal on the operator's
# screen. The version cannot change while the CLI file is untouched, so probe once
# and reuse it; re-probe only when the file changes or the TTL lapses. Failures get
# a much shorter TTL so a repaired CLI is picked up quickly instead of staying stale.
_VERSION_CACHE_TTL_SECONDS = float(os.environ.get("ENGEL_CODEX_VERSION_CACHE_TTL", "900") or "900")
_VERSION_CACHE_FAIL_TTL_SECONDS = float(os.environ.get("ENGEL_CODEX_VERSION_CACHE_FAIL_TTL", "60") or "60")
_version_cache_lock = threading.Lock()
_version_cache: dict[str, Any] = {}


def _codex_version_probe(exe: Path) -> tuple[str, bool, bool]:
    """Return (version, ok, cached) for `codex --version`, spawning at most one
    subprocess per TTL window instead of one per status poll."""
    try:
        stat = exe.stat()
        signature = (str(exe), stat.st_mtime_ns, stat.st_size)
    except OSError:
        signature = (str(exe), 0, 0)
    now = time.monotonic()
    with _version_cache_lock:
        entry = _version_cache.get("entry")
        if entry is not None and entry["signature"] == signature:
            ttl = (
                _VERSION_CACHE_TTL_SECONDS
                if entry["ok"]
                else _VERSION_CACHE_FAIL_TTL_SECONDS
            )
            if (now - entry["probed_at"]) < ttl:
                return entry["version"], entry["ok"], True
    version = ""
    ok = False
    try:
        raw = subprocess.run(
            [str(exe), "--version"],
            cwd=str(CHAT_WORKSPACE if CHAT_WORKSPACE.is_dir() else ROOT),
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=10,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        version = _clip(_strip_ansi(raw.stdout), 300)
        ok = raw.returncode == 0
    except Exception as exc:
        version = _clip(str(exc), 300)
    with _version_cache_lock:
        _version_cache["entry"] = {
            "signature": signature,
            "version": version,
            "ok": ok,
            "probed_at": time.monotonic(),
        }
    return version, ok, False


def _bridge_status() -> dict[str, Any]:
    exe = _codex_exe_path()
    version = ""
    ok = False
    cached = False
    if exe.is_file():
        version, ok, cached = _codex_version_probe(exe)
    return {
        "schema": "engel_codex_cli_bridge_status_v1",
        "ok": ok,
        "provider": "codex",
        "provider_label": "Codex CLI on ROG",
        "root": str(ROOT),
        "workspace": str(CHAT_WORKSPACE),
        "codex_exe": str(exe),
        "codex_exe_present": exe.is_file(),
        "default_model": DEFAULT_MODEL,
        "default_sandbox": DEFAULT_SANDBOX,
        "auth_values_exposed": False,
        "oauth_tokens_exposed": False,
        "writes_secrets": False,
        "chat_only": True,
        "version": version,
        "version_from_cache": cached,
        "updated_at_utc": _iso_now(),
    }


def _run_codex(prompt: str, request: dict[str, Any], started: float) -> dict[str, Any]:
    exe = _codex_exe_path()
    if not exe.is_file():
        return {
            "ok": False,
            "status": "Codex CLI executable missing",
            "assistant_reply": "",
            "error": f"Codex CLI executable not found at {exe}",
        }
    CHAT_WORKSPACE.mkdir(parents=True, exist_ok=True)
    artifact_only = request.get("artifact_only") is True
    request_workspace = ARTIFACT_WORKSPACE if artifact_only else CHAT_WORKSPACE
    request_workspace.mkdir(parents=True, exist_ok=True)
    model = str(request.get("model") or request.get("provider_model") or DEFAULT_MODEL).strip()
    timeout = max(20.0, min(300.0, float(request.get("timeout_seconds") or DEFAULT_TIMEOUT_SECONDS)))
    sandbox = str(request.get("sandbox") or DEFAULT_SANDBOX).strip() or "read-only"
    if sandbox not in {"read-only", "workspace-write", "danger-full-access"}:
        sandbox = "read-only"

    args = [
        str(exe),
        "exec",
        "--sandbox",
        sandbox,
        "--skip-git-repo-check",
        "--ephemeral",
        "--color",
        "never",
        "--cd",
        str(request_workspace),
    ]
    if model:
        args.extend(["--model", model])
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    last_message_path = OUTPUT_DIR / f"codex_last_message_{_stamp()}.txt"
    args.extend(["--output-last-message", str(last_message_path)])
    args.append("-")

    env = dict(os.environ)
    env.setdefault("NO_COLOR", "1")
    cli_prompt = _engel_prompt(prompt, request)
    try:
        execution = _run_codex_process(
            args,
            input_text=cli_prompt,
            cwd=request_workspace,
            env=env,
            timeout=timeout,
        )
        stdout = _strip_ansi(str(execution.get("stdout") or ""))
        stderr = _strip_ansi(str(execution.get("stderr") or ""))
        last_message = ""
        try:
            if last_message_path.is_file():
                last_message = _strip_ansi(last_message_path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            last_message = ""
        reply_text = (last_message or "").strip()
        output = reply_text or stdout
        if execution.get("timed_out") is True:
            fence_count = reply_text.count("```")
            structured_reply_complete = (
                "FILE:" not in reply_text
                or (
                    fence_count >= 2
                    and fence_count % 2 == 0
                    and reply_text.endswith("```")
                )
            )
            if reply_text and structured_reply_complete:
                return {
                    "ok": True,
                    "status": "Codex CLI reply salvaged after process timeout",
                    "assistant_reply": reply_text,
                    "assistant_output_text": reply_text,
                    "provider": "Codex CLI on ROG",
                    "runtime_provider": model or "codex-default",
                    "selected_provider": "codex_cli",
                    "model": model or "codex-default",
                    "sandbox": sandbox,
                    "artifact_only": artifact_only,
                    "workspace": str(request_workspace),
                    "exit_code": execution.get("returncode"),
                    "error": "",
                    "timed_out": True,
                    "process_pid": execution.get("process_pid"),
                    "process_tree_terminated": execution.get("process_tree_terminated") is True,
                    "last_message_path": str(last_message_path),
                    "latency_ms": int((time.perf_counter() - started) * 1000),
                }
            return {
                "ok": False,
                "status": "Codex CLI timed out",
                "assistant_reply": "",
                "provider": "Codex CLI on ROG",
                "runtime_provider": model or "codex-default",
                "model": model or "codex-default",
                "sandbox": sandbox,
                "artifact_only": artifact_only,
                "workspace": str(request_workspace),
                "exit_code": execution.get("returncode"),
                "error": f"Timed out after {int(timeout)} seconds",
                "timed_out": True,
                "process_pid": execution.get("process_pid"),
                "process_tree_terminated": execution.get("process_tree_terminated") is True,
                "last_message_path": str(last_message_path),
                "latency_ms": int((time.perf_counter() - started) * 1000),
            }
        # Codex's GitHub-dependent "curated plugin sync" runs at startup of
        # `codex exec` and is irrelevant to chat. A transient GitHub hiccup can
        # make codex exit nonzero AFTER a valid --output-last-message reply is
        # already written. Treat a written reply as authoritative when the only
        # failure signal is that plugin-sync noise, so we don't 502 a real answer.
        _stderr_low = (stderr or "").lower()
        _sync_noise = any(
            marker in _stderr_low
            for marker in ("curated plugin", "plugin sync", "git sync failed", "marketplace")
        )
        returncode = execution.get("returncode")
        ok = bool(reply_text) and (returncode == 0 or _sync_noise)
        # Account-level failures must surface as themselves, not as a generic
        # "no usable reply" with the cause buried in a stderr blob (2026-08-01:
        # a retired model pin + quota exhaustion masqueraded as a bridge bug).
        status = "Codex CLI replied"
        if not ok:
            if "usage limit" in _stderr_low:
                status = "Codex account usage limit reached -- see error for the reset date"
            elif "not supported when using codex" in _stderr_low:
                status = (
                    "Codex model rejected by the account -- update "
                    "ENGEL_CODEX_CLI_MODEL to a supported slug"
                )
            else:
                status = "Codex CLI did not return a usable reply"
        return {
            "ok": ok,
            "status": status,
            "assistant_reply": output if ok else "",
            "assistant_output_text": output if ok else "",
            "provider": "Codex CLI on ROG",
            "runtime_provider": model or "codex-default",
            "selected_provider": "codex_cli",
            "model": model or "codex-default",
            "sandbox": sandbox,
            "artifact_only": artifact_only,
            "workspace": str(request_workspace),
            "exit_code": returncode,
            "error": "" if ok else _clip(stderr or stdout or output, 1400),
            "stderr_tail": "" if ok else _clip(stderr[-1600:], 1600),
            "stdout_tail": _clip(stdout[-1600:], 1600),
            "process_pid": execution.get("process_pid"),
            "process_tree_terminated": False,
            "last_message_path": str(last_message_path),
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }
    except Exception as exc:
        return {
            "ok": False,
            "status": "Codex CLI failed",
            "assistant_reply": "",
            "provider": "Codex CLI on ROG",
            "runtime_provider": model or "codex-default",
            "model": model or "codex-default",
            "sandbox": sandbox,
            "error": _clip(str(exc), 1400),
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }


def _write_receipt(prompt: str, result: dict[str, Any]) -> str:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"ENGEL_CODEX_CLI_BRIDGE_CHAT_{_stamp()}.json"
    payload = {
        "schema": "engel_codex_cli_bridge_chat_receipt_v1",
        "ok": result.get("ok") is True,
        "updated_at_utc": _iso_now(),
        "prompt": prompt,
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "prompt_chars": len(prompt),
        "assistant_reply": result.get("assistant_reply", ""),
        "status": result.get("status", ""),
        "error": result.get("error", ""),
        "provider": result.get("provider", "Codex CLI on ROG"),
        "runtime_provider": result.get("runtime_provider", ""),
        "sandbox": result.get("sandbox", DEFAULT_SANDBOX),
        "exit_code": result.get("exit_code"),
        "timed_out": result.get("timed_out") is True,
        "process_pid": result.get("process_pid"),
        "process_tree_terminated": result.get("process_tree_terminated") is True,
        "last_message_path": result.get("last_message_path", ""),
        "artifact_only": result.get("artifact_only") is True,
        "workspace": result.get("workspace", ""),
        "latency_ms": result.get("latency_ms"),
        "auth_values_exposed": False,
        "secret_values_written": False,
        "files_modified_by_bridge": False,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(path)


def _completion_response(request: dict[str, Any], reply: str, result: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "chatcmpl-engel-codex-cli-" + _stamp(),
        "object": "chat.completion",
        "created": int(time.time()),
        "model": result.get("model") or DEFAULT_MODEL or "codex-default",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": reply}, "finish_reason": "stop"}],
        "engel": {
            "ok": result.get("ok") is True,
            "provider": result.get("provider", "Codex CLI on ROG"),
            "runtime_provider": result.get("runtime_provider", ""),
            "sandbox": result.get("sandbox", DEFAULT_SANDBOX),
        },
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "EngelCodexCliBridge/1.0"

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
            result = _run_codex(prompt, request, started)
            result["receipt_path"] = _write_receipt(prompt, result)
            if path == "/v1/chat/completions":
                _json_response(self, 200 if result.get("ok") is True else 502, _completion_response(request, str(result.get("assistant_reply") or ""), result))
                return
            payload = {
                "schema": "engel_codex_cli_bridge_chat_response_v1",
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
                    "schema": "engel_codex_cli_bridge_chat_response_v1",
                    "ok": False,
                    "status": "Codex CLI bridge service error",
                    "error": str(exc),
                    "traceback_tail": traceback.format_exc()[-2000:],
                    "updated_at_utc": _iso_now(),
                },
            )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Engel ROG-local Codex CLI HTTP bridge.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=24888)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    CHAT_WORKSPACE.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Engel Codex CLI bridge listening on {args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
