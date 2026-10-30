#!/usr/bin/env python3
"""Engel MCP loader (graphwright 2026-10-30).

Reads staged server cards in /opt/engel/runtime/next_stage/mcp/*.json
(schema engel_mcp_server_stage_v1), skips cards with enabled_by_default false,
lists tools lazily with a TTL cache, and calls one tool with a hard timeout.
Keys come from env_file / process env by NAME; values are never logged,
returned, or written to receipts. No background threads or loops.
"""
from __future__ import annotations

import hashlib
import json
import os
import select
import subprocess
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STAGE_DIR = Path(os.environ.get("ENGEL_MCP_STAGE_DIR", "/opt/engel/runtime/next_stage/mcp"))
RECEIPT_DIR = Path("/opt/engel/reports/engel_mcp_tool_calls")
LIST_TTL_SECONDS = float(os.environ.get("ENGEL_MCP_LIST_TTL_SECONDS", "600"))
LIST_TIMEOUT_SECONDS = float(os.environ.get("ENGEL_MCP_LIST_TIMEOUT_SECONDS", "20"))
CALL_TIMEOUT_SECONDS = float(os.environ.get("ENGEL_MCP_CALL_TIMEOUT_SECONDS", "60"))
FAIL_COOLDOWN_SECONDS = float(os.environ.get("ENGEL_MCP_FAIL_COOLDOWN_SECONDS", "120"))
PROTOCOL = "2025-03-26"
_LOCK = threading.Lock()
_TOOLS_CACHE: dict[str, dict[str, Any]] = {}
_FAILED_AT: dict[str, float] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _env_file(path: str) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path:
        return out
    try:
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                out[key.strip()] = value.strip()
    except OSError:
        pass
    return out


def _secret(card: dict[str, Any], name: str) -> str:
    return str(os.environ.get(name) or _env_file(str(card.get("env_file") or "")).get(name) or "")


def load_cards(include_disabled: bool = False) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for path in sorted(STAGE_DIR.glob("*.json")):
        try:
            card = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(card, dict) or not card.get("name"):
            continue
        card["_file"] = path.name
        if card.get("enabled_by_default") is not True and not include_disabled:
            continue
        cards.append(card)
    return cards


def _card(name: str) -> dict[str, Any] | None:
    for card in load_cards():
        if card.get("name") == name:
            return card
    return None


def _messages(extra: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": PROTOCOL, "capabilities": {}, "clientInfo": {"name": "engel-ai-main", "version": "1"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        *extra,
    ]


def _http(card: dict[str, Any], msgs: list[dict[str, Any]], timeout: float) -> dict[int, dict[str, Any]]:
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream", "User-Agent": "EngelAI-Main/1.0"}
    auth_env = str(card.get("auth_env") or "")
    if auth_env:
        token = _secret(card, auth_env)
        if not token:
            raise RuntimeError(f"auth env {auth_env} not set")
        headers[str(card.get("auth_header") or "Authorization")] = f"{card.get('auth_scheme') or 'Bearer'} {token}".strip()
    deadline = time.monotonic() + timeout
    session = ""
    replies: dict[int, dict[str, Any]] = {}
    for msg in msgs:
        left = deadline - time.monotonic()
        if left <= 0:
            raise TimeoutError("mcp http deadline")
        h = dict(headers)
        if session:
            h["Mcp-Session-Id"] = session
        req = urllib.request.Request(str(card["url"]), json.dumps(msg).encode("utf-8"), h, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=left) as resp:
                session = resp.headers.get("Mcp-Session-Id") or session
                raw = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"http {exc.code}") from None
        if "id" not in msg:
            continue
        for line in raw.splitlines():
            if line.startswith("data:"):
                raw = line[5:]
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            raise RuntimeError("mcp reply was not json") from None
        replies[int(msg["id"])] = data
    return replies


def _stdio(card: dict[str, Any], msgs: list[dict[str, Any]], timeout: float) -> dict[int, dict[str, Any]]:
    env = dict(os.environ)
    env.update({str(k): str(v) for k, v in (card.get("env") or {}).items()})
    for target, source in (card.get("env_map") or {}).items():
        value = _secret(card, str(source))
        if not value:
            raise RuntimeError(f"env {source} not set")
        env[str(target)] = value
    cmd = [str(card["command"])] + [str(a) for a in card.get("args") or []]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env, text=True, cwd=str(card.get("cwd") or "/opt/engel"))
    replies: dict[int, dict[str, Any]] = {}
    deadline = time.monotonic() + timeout
    try:
        for msg in msgs:
            proc.stdin.write(json.dumps(msg) + "\n")
            proc.stdin.flush()
            if "id" not in msg:
                continue
            while True:
                left = deadline - time.monotonic()
                if left <= 0:
                    raise TimeoutError("mcp stdio deadline")
                ready, _, _ = select.select([proc.stdout], [], [], min(left, 2.0))
                if not ready:
                    if proc.poll() is not None:
                        raise RuntimeError(f"mcp server exited {proc.returncode}")
                    continue
                line = proc.stdout.readline()
                if not line:
                    raise RuntimeError("mcp server closed stdout")
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if data.get("id") == msg["id"]:
                    replies[int(msg["id"])] = data
                    break
    finally:
        proc.kill()
        try:
            proc.wait(timeout=3)
        except Exception:
            pass
    return replies


def _rpc(card: dict[str, Any], extra: list[dict[str, Any]], timeout: float) -> dict[int, dict[str, Any]]:
    if card.get("transport") == "stdio":
        return _stdio(card, _messages(extra), timeout)
    return _http(card, _messages(extra), timeout)


def list_tools(name: str, *, force: bool = False) -> dict[str, Any]:
    card = _card(name)
    if card is None:
        return {"ok": False, "server": name, "error": "server not enabled or not found", "tools": []}
    with _LOCK:
        cached = _TOOLS_CACHE.get(name)
        if cached and not force and time.time() - cached["at"] < LIST_TTL_SECONDS:
            return cached["result"]
        failed = _FAILED_AT.get(name, 0.0)
        if not force and time.time() - failed < FAIL_COOLDOWN_SECONDS:
            return {"ok": False, "server": name, "error": "fast-fail cooldown after recent failure", "tools": []}
    started = time.monotonic()
    try:
        replies = _rpc(card, [{"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}], LIST_TIMEOUT_SECONDS)
        tools = replies.get(2, {}).get("result", {}).get("tools", [])
        result = {
            "ok": True,
            "server": name,
            "transport": card.get("transport"),
            "tools": [{"name": t.get("name"), "description": str(t.get("description") or "")[:200]} for t in tools if isinstance(t, dict)],
            "latency_seconds": round(time.monotonic() - started, 2),
            "listed_at_utc": _now(),
        }
    except Exception as exc:
        result = {"ok": False, "server": name, "error": f"{type(exc).__name__}: {str(exc)[:160]}", "tools": []}
        with _LOCK:
            _FAILED_AT[name] = time.time()
        return result
    with _LOCK:
        _TOOLS_CACHE[name] = {"at": time.time(), "result": result}
        _FAILED_AT.pop(name, None)
    return result


def registry_snapshot(*, list_now: bool = True) -> dict[str, Any]:
    servers = []
    for card in load_cards(include_disabled=True):
        enabled = card.get("enabled_by_default") is True
        entry = {"name": card.get("name"), "file": card.get("_file"), "enabled": enabled, "transport": card.get("transport"), "source": card.get("source", "")}
        if enabled and list_now and card.get("name") != "engel-playwright-browser":
            listing = list_tools(str(card.get("name")))
            entry.update({"ok": listing.get("ok"), "tools": [t["name"] for t in listing.get("tools", [])], "error": listing.get("error", "")})
        servers.append(entry)
    return {"schema": "engel_mcp_registry_v1", "stage_dir": str(STAGE_DIR), "servers": servers, "updated_at_utc": _now()}


def call_tool(server: str, tool: str, arguments: dict[str, Any] | None = None, *, source: str = "chat") -> dict[str, Any]:
    started = time.monotonic()
    card = _card(server)
    receipt: dict[str, Any] = {
        "schema": "engel_mcp_tool_call_receipt_v1",
        "server": server,
        "tool": tool,
        "arguments_sha256": hashlib.sha256(json.dumps(arguments or {}, sort_keys=True).encode()).hexdigest(),
        "source": source,
        "started_at_utc": _now(),
        "secrets_logged": False,
    }
    if card is None:
        receipt.update({"ok": False, "error": "server not enabled or not found"})
    else:
        try:
            replies = _rpc(card, [{"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": tool, "arguments": arguments or {}}}], CALL_TIMEOUT_SECONDS)
            reply = replies.get(3, {})
            if "error" in reply:
                receipt.update({"ok": False, "error": str(reply["error"])[:300]})
            else:
                res = reply.get("result", {})
                text = "\n".join(str(c.get("text") or "") for c in res.get("content", []) if isinstance(c, dict))
                receipt.update({"ok": not bool(res.get("isError")), "result_text": text[:4000], "is_error": bool(res.get("isError"))})
        except Exception as exc:
            receipt.update({"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:200]}"})
    receipt["latency_seconds"] = round(time.monotonic() - started, 2)
    try:
        RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path = RECEIPT_DIR / f"ENGEL_MCP_TOOL_CALL_{stamp}.json"
        path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        receipt["receipt_path"] = str(path)
    except OSError:
        pass
    return receipt
