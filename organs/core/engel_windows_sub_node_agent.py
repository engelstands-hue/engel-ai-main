#!/usr/bin/env python3
"""Windows Sub-Engel node agent.

This preserves Windows and exposes a pair-gated control node for trusted
Engel AI Main. The HTTP surface is intentionally allowlisted; broader desktop
authority is explicit through CT246's paired, authenticated direct-work and
reviewed deployment channels, not an unauthenticated raw shell.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import secrets
import signal
import shutil
import socket
import string
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib import error, request


ROLE = "windows_sub_engel_node"
DISPLAY_ROLE = "Windows Sub-Engel Node"
APPROVAL_TOKEN = "APPROVE_ENGEL_WINDOWS_SUB_NODE"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8776
PAIRING_TTL_SECONDS = 15 * 60
SESSION_TTL_SECONDS = int(os.environ.get("ENGEL_WINDOWS_SUB_NODE_SESSION_TTL_SECONDS", str(30 * 24 * 60 * 60)))
TOKEN_LENGTH = 8
MAX_REQUEST_BYTES = 1_048_576
MAX_OUTPUT_BYTES = 60000
DEFAULT_CONTROLLER_URL = "http://192.0.2.40:8788"
SHARED_ROOM_NAME = "ENGEL_SHARED_NODE_ROOM"
SHARED_WORK_ORDERS_DIR = "SUB_ENGEL_WORK_ORDERS"
SHARED_SENT_WORK_DIR = "SUB_ENGEL_SENT_WORK"
SHARED_ACTIVE_WORK_REQUEST = "SUB_ENGEL_ACTIVE_WORK_REQUEST.json"
LOCAL_HELPER_MANIFEST_NAME = "sub_engel_local_helper_model.json"
MEMORY_DIR_NAME = "memory"
MEMORY_CORE_NAME = "sub_engel_memory.json"
MEMORY_EPISODES_NAME = "sub_engel_episodes.jsonl"
MAIN_FULL_CONTROL_NAME = "main-full-control.json"
MAIN_DESTRUCTIVE_CONFIRM = "APPROVE_SUB_ENGEL_DESTRUCTIVE_DISK"
MAX_LLM_PROMPT_CHARS = 10000
MAX_LLM_OUTPUT_CHARS = 6000
MAX_MEMORY_CONTEXT_CHARS = 3000
MAX_MEMORY_EPISODES_IN_PROMPT = 8
MAX_MEMORY_EPISODE_TEXT_CHARS = 1200
MAX_MEMORY_RECENT_EPISODES = 30
MAX_MEMORY_NOTES = 120
DIRECT_WORK_ACTION = "direct_work.execute"
DIRECT_WORK_SCHEMA = "engel_sub_engel_direct_work_order_v1"
DIRECT_WORK_RECEIPT_SCHEMA = "engel_sub_engel_direct_work_receipt_v1"
TRAINING_SAFE_JOB_TYPES = {
    "inventory_summary",
    "read_only_status",
    "status_snapshot",
    "training_status",
}
TRAINING_MUTATION_TERMS = (
    "build",
    "compile",
    "convert",
    "copy",
    "delete",
    "download",
    "edit",
    "fine-tune",
    "finetune",
    "install",
    "kill",
    "move",
    "patch",
    "restart",
    "run model",
    "service",
    "start model",
    "stop",
    "train",
    "update",
    "write",
)


def find_training_mutation_terms(text: str) -> list[str]:
    normalized = str(text or "").lower()
    return sorted({
        term
        for term in TRAINING_MUTATION_TERMS
        if re.search(rf"(?<![a-z0-9_]){re.escape(term)}(?![a-z0-9_])", normalized)
    })

_PEFT_RUNTIME_CACHE: dict[str, Any] = {}

ALLOWED_ACTIONS = {
    "node.status",
    "node.hardware",
    "node.safety",
    "node.controller",
    "net.status",
    "net.diagnose",
    "install.status",
    "install.preflight",
    "install.list_disks",
    "ui.dashboard",
    "ui.visible_status",
    "local_llm.status",
    "direct_work.execute",
    "session.renew",
    "training.status",
    "training_safe.execute",
    "memory.status",
    "main.control_status",
    "main.shell",
    "disk.control",
    "remote.status",
}

BLOCKED_ACTIONS = [
    "shell",
    "exec",
    "ssh",
    "reboot",
    "shutdown",
    "package.install",
    "install.install",
    "disk.partition",
    "disk.format",
    "disk.erase",
    "wifi.connect",
    "provider.start",
    "model.start",
    "controller.runtime.start",
    "background.worker.start",
    "registry.write",
    "service.install",
    "firewall.modify",
    "shared_room.status",
    "shared_room.process_latest_work_order",
    "shared_room.process_pending_work_orders",
]


def is_os_drive_path(path: str | Path) -> bool:
    text = str(path).replace("/", "\\").lower()
    return text.startswith("c:\\") or text.startswith("\\\\?\\c:\\")


def approved_env_path(key: str) -> Path | None:
    raw = os.environ.get(key)
    if not raw:
        return None
    candidate = Path(raw)
    if is_os_drive_path(candidate):
        return None
    return candidate


def default_node_root() -> Path:
    override = approved_env_path("ENGEL_WINDOWS_SUB_NODE_ROOT")
    if override:
        return override
    return Path("D:/EngelWindowsSubNode")


def default_state_dir() -> Path:
    override = approved_env_path("ENGEL_WINDOWS_SUB_NODE_STATE")
    if override:
        return override
    return default_node_root() / "state"


STATE_DIR = default_state_dir()


def pairing_path() -> Path:
    return STATE_DIR / "pairing-session.json"


def session_path() -> Path:
    return STATE_DIR / "session-token.json"


def public_state_path() -> Path:
    return STATE_DIR / "windows-sub-node-state.json"


def receipt_path() -> Path:
    return STATE_DIR / "remote-control-receipts.jsonl"


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def utc_stamp(value: datetime | None = None) -> str:
    return (value or utc_now()).isoformat().replace("+00:00", "Z")


def parse_utc(value: str) -> datetime | None:
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def ensure_state_dir() -> None:
    if is_os_drive_path(STATE_DIR):
        raise OSError(f"refusing Windows Sub-Engel state on C: {STATE_DIR}")
    STATE_DIR.mkdir(parents=True, exist_ok=True)


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def write_json(path: Path, data: dict[str, Any]) -> None:
    ensure_state_dir()
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def redacted(value: str) -> str:
    if len(value) <= 4:
        return "****"
    return "*" * (len(value) - 4) + value[-4:]


def generate_pairing_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(TOKEN_LENGTH))


def is_expired(expires_at_utc: str) -> bool:
    parsed = parse_utc(expires_at_utc)
    return parsed is None or utc_now() >= parsed


def append_receipt(record: dict[str, Any]) -> None:
    try:
        ensure_state_dir()
        with receipt_path().open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"timestamp_utc": utc_stamp(), **record}, sort_keys=True) + "\n")
    except OSError:
        pass


def memory_dir() -> Path:
    return STATE_DIR / MEMORY_DIR_NAME


def memory_core_path() -> Path:
    return memory_dir() / MEMORY_CORE_NAME


def memory_episodes_path() -> Path:
    return memory_dir() / MEMORY_EPISODES_NAME


def main_full_control_path() -> Path:
    return STATE_DIR / MAIN_FULL_CONTROL_NAME


def ensure_memory_dir() -> None:
    ensure_state_dir()
    memory_dir().mkdir(parents=True, exist_ok=True)


def clamp_text(value: Any, limit: int) -> str:
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def default_memory_core() -> dict[str, Any]:
    now = utc_stamp()
    return {
        "schema": "engel_sub_engel_persistent_memory_v1",
        "created_at_utc": now,
        "updated_at_utc": now,
        "hostname": socket.gethostname(),
        "node_root": str(default_node_root()),
        "state_dir": str(STATE_DIR),
        "memory_policy": {
            "scope": "Sub-Engel local durable runtime context",
            "source_of_truth": "paired Main work orders, Sub-Engel receipts, local runtime status",
            "prompt_injection_rule": "Work order instructions outrank memory. Memory is context, not permission.",
            "model_training_rule": "This memory is not weight training; it is retrieved into each helper prompt and grows after every processed work order.",
        },
        "durable_facts": [
            "Engel AI Main is the paired trusted controller for this desktop.",
            "Sub-Engel should prefer the PEFT LoRA artifact through transformers/peft.",
            "Legacy llama.cpp CUDA/GGUF fallback is disabled unless ENGEL_SUB_ENGEL_ENABLE_LLAMA_CPP_FALLBACK=1.",
            "The helper must load persistent memory before answering Main work orders so it does not respond cold.",
        ],
        "learned_notes": [],
        "known_paths": {
            "node_root": str(default_node_root()),
            "state_dir": str(STATE_DIR),
            "memory_core": str(memory_core_path()),
            "memory_episodes": str(memory_episodes_path()),
            "work_transport": "ct246_authenticated_direct_http",
        },
        "runtime_preferences": {
            "preferred_local_llm_runtime": "peft_lora_transformers",
            "legacy_llama_cpp_fallback_enabled": False,
            "keep_peft_loaded_per_worker_process": True,
        },
        "current_focus": "Keep Sub-Engel aware of CT246 direct orders, PEFT LoRA status, local runtime blockers, and returned proof.",
        "counters": {
            "episodes": 0,
            "work_orders_processed": 0,
            "memory_notes_learned": 0,
        },
        "recent_episodes": [],
    }


def normalize_memory_core(core: dict[str, Any]) -> dict[str, Any]:
    if not core:
        return default_memory_core()
    default = default_memory_core()
    merged = {**default, **core}
    for key in ("memory_policy", "known_paths", "runtime_preferences", "counters"):
        value = merged.get(key)
        if not isinstance(value, dict):
            merged[key] = default[key]
        else:
            merged[key] = {**default[key], **value}
    for key in ("durable_facts", "learned_notes", "recent_episodes"):
        if not isinstance(merged.get(key), list):
            merged[key] = default[key]
    merged["schema"] = default["schema"]
    merged["hostname"] = socket.gethostname()
    merged["node_root"] = str(default_node_root())
    merged["state_dir"] = str(STATE_DIR)
    merged["known_paths"]["node_root"] = str(default_node_root())
    merged["known_paths"]["state_dir"] = str(STATE_DIR)
    merged["known_paths"]["memory_core"] = str(memory_core_path())
    merged["known_paths"]["memory_episodes"] = str(memory_episodes_path())
    merged["known_paths"].pop("shared_room", None)
    merged["known_paths"]["work_transport"] = "ct246_authenticated_direct_http"
    for key in ("last_source_work_order", "last_done_file"):
        value = str(merged["known_paths"].get(key) or "")
        if "my drive" in value.lower() or (len(value) > 2 and value[1:3] == ":\\"
                                           and value[0].upper() in {"E", "F", "G"}):
            merged["known_paths"].pop(key, None)
    runtime_preferences = merged["runtime_preferences"]
    adapter_dir = str(runtime_preferences.get("last_adapter_dir") or "")
    if "my drive" in adapter_dir.lower() or (len(adapter_dir) > 2 and adapter_dir[1:3] == ":\\"
                                              and adapter_dir[0].upper() in {"E", "F", "G"}):
        runtime_preferences["last_adapter_dir"] = ""
    return merged


def read_memory_core() -> dict[str, Any]:
    core = normalize_memory_core(read_json(memory_core_path()))
    if not memory_core_path().is_file():
        write_memory_core(core)
    return core


def write_memory_core(core: dict[str, Any]) -> None:
    ensure_memory_dir()
    core["updated_at_utc"] = utc_stamp()
    memory_core_path().write_text(json.dumps(core, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_memory_episode(record: dict[str, Any]) -> None:
    ensure_memory_dir()
    with memory_episodes_path().open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")


def read_memory_episode_tail(limit: int = MAX_MEMORY_EPISODES_IN_PROMPT) -> list[dict[str, Any]]:
    path = memory_episodes_path()
    if limit <= 0 or not path.is_file():
        return []
    try:
        size = path.stat().st_size
        with path.open("rb") as fh:
            if size > 256 * 1024:
                fh.seek(size - 256 * 1024)
                fh.readline()
            lines = fh.readlines()
    except OSError:
        return []
    episodes: list[dict[str, Any]] = []
    for raw in lines[-limit:]:
        try:
            data = json.loads(raw.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            episodes.append(data)
    return episodes


def unique_memory_items(values: list[Any], limit: int) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = clamp_text(value, 500)
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
        if len(out) >= limit:
            break
    return out


def extract_memory_notes(order_payload: dict[str, Any]) -> list[str]:
    text = str(order_payload.get("order_text") or "")
    notes: list[str] = []
    prefixes = ("remember:", "memory:", "fact:", "preference:", "learn:")
    for line in text.splitlines():
        clean = line.strip(" -\t")
        lower = clean.lower()
        for prefix in prefixes:
            if lower.startswith(prefix):
                notes.append(clamp_text(clean[len(prefix):].strip(), 500))
                break
    return [note for note in notes if note]


def peft_runtime_cache_status() -> dict[str, Any]:
    cache_key = str(_PEFT_RUNTIME_CACHE.get("key") or "")
    return {
        "enabled": True,
        "scope": "per running Sub-Engel Python process",
        "loaded": bool(cache_key),
        "key": cache_key,
        "base_model": _PEFT_RUNTIME_CACHE.get("base_model", ""),
        "adapter_dir": _PEFT_RUNTIME_CACHE.get("adapter_dir", ""),
        "loaded_at_utc": _PEFT_RUNTIME_CACHE.get("loaded_at_utc", ""),
        "last_used_at_utc": _PEFT_RUNTIME_CACHE.get("last_used_at_utc", ""),
    }


def memory_status_payload(include_recent: bool = False, include_context: bool = False) -> dict[str, Any]:
    core = read_memory_core()
    counters = core.get("counters") if isinstance(core.get("counters"), dict) else {}
    payload: dict[str, Any] = {
        "ok": True,
        "schema": core.get("schema", ""),
        "memory_core": str(memory_core_path()),
        "memory_episodes": str(memory_episodes_path()),
        "created_at_utc": core.get("created_at_utc", ""),
        "updated_at_utc": core.get("updated_at_utc", ""),
        "state_dir_on_os_drive": is_os_drive_path(STATE_DIR),
        "episodes": counters.get("episodes", 0),
        "work_orders_processed": counters.get("work_orders_processed", 0),
        "memory_notes_learned": counters.get("memory_notes_learned", 0),
        "current_focus": core.get("current_focus", ""),
        "known_paths": core.get("known_paths", {}),
        "runtime_preferences": core.get("runtime_preferences", {}),
        "peft_runtime_cache": peft_runtime_cache_status(),
        "mode": "persistent_json_memory_plus_process_peft_cache",
    }
    if include_recent:
        payload["durable_facts"] = core.get("durable_facts", [])
        payload["learned_notes"] = core.get("learned_notes", [])
        payload["recent_episodes"] = core.get("recent_episodes", [])
    if include_context:
        payload["prompt_context_preview"] = persistent_memory_context({})
    return payload


def main_full_control_config() -> dict[str, Any]:
    config = read_json(main_full_control_path())
    if not config:
        config = {
            "schema": "engel_sub_engel_main_full_control_v1",
            "enabled": False,
            "enabled_at_utc": "",
            "enabled_by": "",
            "scope": "paired Main shell and disk control",
            "requires_pairing_session": True,
            "audit_receipts": True,
            "shell": {
                "enabled": False,
                "max_timeout_seconds": 120,
                "default_timeout_seconds": 30,
                "working_directory": str(default_node_root()),
            },
            "disk": {
                "enabled": False,
                "allow_destructive": False,
                "destructive_confirm_token": MAIN_DESTRUCTIVE_CONFIRM,
            },
            "notes": [
                "Unauthenticated raw shell remains disabled.",
                "This tier is reachable only through the paired Main bearer-authenticated command endpoint.",
            ],
        }
    return config


def main_full_control_enabled() -> bool:
    if env_flag("ENGEL_SUB_ENGEL_ENABLE_MAIN_FULL_CONTROL", False):
        return True
    return bool(main_full_control_config().get("enabled"))


def main_shell_enabled() -> bool:
    config = main_full_control_config()
    shell = config.get("shell") if isinstance(config.get("shell"), dict) else {}
    return main_full_control_enabled() and bool(shell.get("enabled", True))


def main_disk_enabled() -> bool:
    config = main_full_control_config()
    disk = config.get("disk") if isinstance(config.get("disk"), dict) else {}
    return main_full_control_enabled() and bool(disk.get("enabled", True))


def destructive_disk_allowed() -> bool:
    config = main_full_control_config()
    disk = config.get("disk") if isinstance(config.get("disk"), dict) else {}
    return main_disk_enabled() and bool(disk.get("allow_destructive", False))


def main_full_control_status_payload() -> dict[str, Any]:
    config = main_full_control_config()
    shell = config.get("shell") if isinstance(config.get("shell"), dict) else {}
    disk = config.get("disk") if isinstance(config.get("disk"), dict) else {}
    return {
        "ok": True,
        "enabled": main_full_control_enabled(),
        "config_path": str(main_full_control_path()),
        "requires_pairing_session": True,
        "audit_receipts": True,
        "shell_enabled": main_shell_enabled(),
        "disk_enabled": main_disk_enabled(),
        "destructive_disk_allowed": destructive_disk_allowed(),
        "destructive_disk_confirm_token": MAIN_DESTRUCTIVE_CONFIRM if destructive_disk_allowed() else "",
        "shell": shell,
        "disk": {**disk, "destructive_confirm_token": MAIN_DESTRUCTIVE_CONFIRM if destructive_disk_allowed() else ""},
        "allowed_actions": sorted(ALLOWED_ACTIONS),
    }


def full_control_rejected(action: str, reason: str) -> dict[str, Any]:
    return json_action_result(action, {
        "ok": False,
        "error": reason,
        "control_status": main_full_control_status_payload(),
    }, return_code=2)


def action_main_control_status() -> dict[str, Any]:
    return json_action("main.control_status", main_full_control_status_payload())


def requested_timeout(body: dict[str, Any], default_seconds: float, max_seconds: float) -> float:
    try:
        requested = float(body.get("timeout_seconds", default_seconds))
    except (TypeError, ValueError):
        requested = default_seconds
    return max(1.0, min(requested, max_seconds))


def action_main_shell(body: dict[str, Any]) -> dict[str, Any]:
    if not main_shell_enabled():
        return full_control_rejected("main.shell", "paired Main shell control is not enabled on this Sub-Engel")
    command = str(body.get("command") or body.get("script") or "").strip()
    if not command:
        return json_action_result("main.shell", {"ok": False, "error": "missing command"}, return_code=2)
    config = main_full_control_config()
    shell = config.get("shell") if isinstance(config.get("shell"), dict) else {}
    cwd_text = str(body.get("cwd") or shell.get("working_directory") or default_node_root()).strip()
    cwd = Path(cwd_text)
    if cwd_text and not cwd.exists():
        return json_action_result("main.shell", {"ok": False, "error": f"cwd does not exist: {cwd}"}, return_code=2)
    timeout = requested_timeout(
        body,
        float(shell.get("default_timeout_seconds") or 30),
        float(shell.get("max_timeout_seconds") or 120),
    )
    append_receipt({
        "event": "main_shell_requested",
        "command_sha256": sha256_text(command),
        "cwd": str(cwd),
        "timeout_seconds": timeout,
    })
    result = run_fixed([
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        command,
    ], timeout=timeout, cwd=cwd)
    result["action"] = "main.shell"
    result["cwd"] = str(cwd)
    result["paired_main_full_control"] = True
    result["command_sha256"] = sha256_text(command)
    append_receipt({
        "event": "main_shell_completed",
        "command_sha256": sha256_text(command),
        "return_code": result.get("return_code"),
        "timeout_seconds": timeout,
    })
    return result


def disk_confirmed(body: dict[str, Any]) -> bool:
    return str(body.get("confirm") or body.get("confirmation") or "").strip() == MAIN_DESTRUCTIVE_CONFIRM


def disk_control_path(body: dict[str, Any], key: str = "path") -> Path:
    raw = str(body.get(key) or "").strip()
    if not raw:
        raise ValueError(f"missing {key}")
    return Path(raw)


def disk_json_action(payload: dict[str, Any], return_code: int = 0) -> dict[str, Any]:
    return json_action_result("disk.control", payload, return_code=return_code)


def action_disk_control(body: dict[str, Any]) -> dict[str, Any]:
    if not main_disk_enabled():
        return full_control_rejected("disk.control", "paired Main disk control is not enabled on this Sub-Engel")
    operation = str(body.get("operation") or body.get("op") or "list").strip().lower()
    destructive_ops = {"delete", "remove", "rmdir", "move_replace", "write_text"}
    if operation in destructive_ops and not (destructive_disk_allowed() and disk_confirmed(body)):
        return disk_json_action({
            "ok": False,
            "error": f"operation {operation} requires destructive disk enablement and confirm={MAIN_DESTRUCTIVE_CONFIRM}",
            "destructive_disk_allowed": destructive_disk_allowed(),
        }, return_code=2)
    try:
        if operation in {"list", "drives", "volumes"}:
            script = (
                "$ErrorActionPreference='SilentlyContinue';"
                "$obj=[ordered]@{};"
                "$obj.volumes=Get-Volume | Select-Object DriveLetter,FileSystemLabel,FileSystem,DriveType,HealthStatus,Size,SizeRemaining;"
                "$obj.disks=Get-Disk | Select-Object Number,FriendlyName,SerialNumber,BusType,PartitionStyle,OperationalStatus,HealthStatus,Size;"
                "$obj | ConvertTo-Json -Depth 5 -Compress"
            )
            result = ps(script, timeout=20)
            result["action"] = "disk.control"
            result["operation"] = operation
            return result
        if operation in {"status", "path_status"}:
            path = disk_control_path(body)
            exists = path.exists()
            stat = path.stat() if exists else None
            return disk_json_action({
                "ok": True,
                "operation": operation,
                "path": str(path),
                "exists": exists,
                "is_file": path.is_file() if exists else False,
                "is_dir": path.is_dir() if exists else False,
                "size_bytes": stat.st_size if stat and path.is_file() else None,
                "modified_at_utc": utc_stamp(datetime.fromtimestamp(stat.st_mtime, timezone.utc)) if stat else "",
                "on_os_drive": is_os_drive_path(path),
            })
        if operation == "mkdir":
            path = disk_control_path(body)
            path.mkdir(parents=True, exist_ok=True)
            return disk_json_action({"ok": True, "operation": operation, "path": str(path), "exists": path.is_dir()})
        if operation == "read_text":
            path = disk_control_path(body)
            max_chars = int(body.get("max_chars") or 12000)
            text = path.read_text(encoding=str(body.get("encoding") or "utf-8-sig"), errors="replace")
            return disk_json_action({"ok": True, "operation": operation, "path": str(path), "text": clamp_text(text, max_chars)})
        if operation == "write_text":
            path = disk_control_path(body)
            path.parent.mkdir(parents=True, exist_ok=True)
            text = str(body.get("text") or "")
            path.write_text(text, encoding=str(body.get("encoding") or "utf-8"))
            return disk_json_action({"ok": True, "operation": operation, "path": str(path), "bytes": path.stat().st_size})
        if operation == "hash":
            path = disk_control_path(body)
            return disk_json_action({"ok": True, "operation": operation, "path": str(path), "sha256": sha256_file(path)})
        if operation == "copy":
            source = disk_control_path(body, "source")
            destination = disk_control_path(body, "destination")
            if source.is_dir():
                shutil.copytree(source, destination, dirs_exist_ok=bool(body.get("dirs_exist_ok", True)))
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
            return disk_json_action({"ok": True, "operation": operation, "source": str(source), "destination": str(destination)})
        if operation in {"move", "move_replace"}:
            source = disk_control_path(body, "source")
            destination = disk_control_path(body, "destination")
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists() and operation == "move":
                return disk_json_action({"ok": False, "error": f"destination exists: {destination}"}, return_code=2)
            if destination.exists() and operation == "move_replace":
                if destination.is_dir():
                    shutil.rmtree(destination)
                else:
                    destination.unlink()
            shutil.move(str(source), str(destination))
            return disk_json_action({"ok": True, "operation": operation, "source": str(source), "destination": str(destination)})
        if operation in {"delete", "remove", "rmdir"}:
            path = disk_control_path(body)
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
            return disk_json_action({"ok": True, "operation": operation, "path": str(path), "deleted": True})
    except Exception as exc:
        return disk_json_action({"ok": False, "operation": operation, "error": str(exc)}, return_code=1)
    return disk_json_action({
        "ok": False,
        "error": f"unsupported disk operation: {operation}",
        "supported_operations": ["list", "status", "mkdir", "read_text", "write_text", "hash", "copy", "move", "move_replace", "delete"],
    }, return_code=2)


def persistent_memory_context(order_payload: dict[str, Any]) -> str:
    core = read_memory_core()
    facts = unique_memory_items(list(core.get("durable_facts", [])), 12)
    notes = unique_memory_items(list(core.get("learned_notes", [])), 12)
    recent = read_memory_episode_tail(MAX_MEMORY_EPISODES_IN_PROMPT)
    known_paths = core.get("known_paths") if isinstance(core.get("known_paths"), dict) else {}
    runtime_preferences = core.get("runtime_preferences") if isinstance(core.get("runtime_preferences"), dict) else {}

    lines = [
        "Persistent Sub-Engel memory context:",
        "Use this as durable context from prior Main orders and local receipts. Current work order still controls.",
        f"Memory core: {memory_core_path()}",
        f"Current focus: {clamp_text(core.get('current_focus', ''), 500)}",
        f"Runtime preference: {runtime_preferences.get('preferred_local_llm_runtime', 'peft_lora_transformers')}",
        f"Legacy llama.cpp fallback enabled: {runtime_preferences.get('legacy_llama_cpp_fallback_enabled', False)}",
    ]
    work_transport = str(known_paths.get("work_transport") or "").strip()
    if work_transport:
        lines.append(f"Work transport: {work_transport}")
    if facts:
        lines.append("Durable facts:")
        lines.extend([f"- {item}" for item in facts])
    if notes:
        lines.append("Learned notes:")
        lines.extend([f"- {item}" for item in notes])
    if recent:
        lines.append("Recent episodes:")
        for episode in recent:
            lines.append(
                "- "
                + "; ".join([
                    f"{episode.get('completed_at_utc', '')}",
                    f"job={episode.get('job_type', '')}",
                    f"order={episode.get('order_id', '')}",
                    f"engine={episode.get('worker_engine', '')}",
                    clamp_text(episode.get("summary", ""), 240),
                ])
            )
    return clamp_text("\n".join(lines), MAX_MEMORY_CONTEXT_CHARS)


def record_persistent_memory_episode(
    order_payload: dict[str, Any],
    executor: dict[str, Any],
    result_meta: dict[str, Any],
) -> dict[str, Any]:
    now = utc_stamp()
    order_id = str(order_payload.get("id") or result_meta.get("order_id") or "").strip()
    job_type = str(order_payload.get("job_type") or "meeting_work").strip()
    selected = order_payload.get("selected_node") if isinstance(order_payload.get("selected_node"), dict) else {}
    status = executor.get("status") if isinstance(executor.get("status"), dict) else {}
    peft_status = status.get("peft_lora_runtime") if isinstance(status.get("peft_lora_runtime"), dict) else {}
    adapter = peft_status.get("adapter") if isinstance(peft_status.get("adapter"), dict) else {}
    episode = {
        "schema": "engel_sub_engel_memory_episode_v1",
        "completed_at_utc": now,
        "hostname": socket.gethostname(),
        "order_id": order_id,
        "job_type": job_type,
        "target": order_payload.get("target", ""),
        "target_label": order_payload.get("target_label", ""),
        "selected_node": selected,
        "source_work_order": result_meta.get("source_work_order", ""),
        "incoming_file": result_meta.get("incoming_file", ""),
        "done_file": result_meta.get("done_file", ""),
        "worker_engine": executor.get("engine", ""),
        "llm_attempted": bool(executor.get("llm_attempted")),
        "runtime_mode": status.get("runtime_mode", ""),
        "peft_ready": bool(peft_status.get("ready")),
        "peft_adapter_dir": adapter.get("artifact_dir", ""),
        "base_model": peft_status.get("base_model_path_or_id", ""),
        "fallback_reason": clamp_text(executor.get("fallback_reason", ""), 700),
        "summary": clamp_text(order_payload.get("order_text", ""), MAX_MEMORY_EPISODE_TEXT_CHARS),
        "result_excerpt": clamp_text(executor.get("output", ""), MAX_MEMORY_EPISODE_TEXT_CHARS),
        "memory_notes_from_order": extract_memory_notes(order_payload),
    }
    append_memory_episode(episode)

    core = read_memory_core()
    counters = core.get("counters") if isinstance(core.get("counters"), dict) else {}
    counters["episodes"] = int(counters.get("episodes") or 0) + 1
    counters["work_orders_processed"] = int(counters.get("work_orders_processed") or 0) + 1

    notes = list(core.get("learned_notes", []))
    notes = extract_memory_notes(order_payload) + notes
    core["learned_notes"] = unique_memory_items(notes, MAX_MEMORY_NOTES)
    counters["memory_notes_learned"] = len(core["learned_notes"])
    core["counters"] = counters
    core["current_focus"] = clamp_text(order_payload.get("order_text", "") or executor.get("output", ""), 700)

    known_paths = core.get("known_paths") if isinstance(core.get("known_paths"), dict) else {}
    known_paths.pop("shared_room", None)
    known_paths["work_transport"] = "ct246_authenticated_direct_http"
    known_paths["last_source_work_order"] = str(result_meta.get("source_work_order", ""))
    known_paths["last_done_file"] = str(result_meta.get("done_file", ""))
    core["known_paths"] = known_paths

    runtime_preferences = core.get("runtime_preferences") if isinstance(core.get("runtime_preferences"), dict) else {}
    runtime_preferences["preferred_local_llm_runtime"] = "peft_lora_transformers"
    runtime_preferences["legacy_llama_cpp_fallback_enabled"] = env_flag("ENGEL_SUB_ENGEL_ENABLE_LLAMA_CPP_FALLBACK", False)
    runtime_preferences["keep_peft_loaded_per_worker_process"] = True
    runtime_preferences["last_runtime_mode"] = status.get("runtime_mode", "")
    runtime_preferences["last_peft_ready"] = bool(peft_status.get("ready"))
    runtime_preferences["last_base_model"] = peft_status.get("base_model_path_or_id", "")
    runtime_preferences["last_adapter_dir"] = adapter.get("artifact_dir", "")
    core["runtime_preferences"] = runtime_preferences

    recent = [episode] + [item for item in core.get("recent_episodes", []) if isinstance(item, dict)]
    core["recent_episodes"] = recent[:MAX_MEMORY_RECENT_EPISODES]
    write_memory_core(core)
    return {
        "ok": True,
        "memory_core": str(memory_core_path()),
        "memory_episodes": str(memory_episodes_path()),
        "episode_order_id": order_id,
        "updated_at_utc": now,
        "episodes": counters["episodes"],
        "work_orders_processed": counters["work_orders_processed"],
    }


def console_notice(message: str) -> None:
    try:
        print(f"[{utc_stamp()}] {message}", flush=True)
    except OSError:
        pass


def truncate(value: str) -> str:
    raw = value.encode("utf-8", errors="replace")
    if len(raw) <= MAX_OUTPUT_BYTES:
        return value
    return raw[:MAX_OUTPUT_BYTES].decode("utf-8", errors="replace") + "\n[windows-sub-engel: output truncated]\n"


def silent_subprocess_kwargs() -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        if creationflags:
            kwargs["creationflags"] = creationflags
        if hasattr(subprocess, "STARTUPINFO") and hasattr(subprocess, "STARTF_USESHOWWINDOW"):
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0
            kwargs["startupinfo"] = startupinfo
    return kwargs


def run_fixed(
    argv: list[str],
    timeout: float = 12.0,
    env: dict[str, str] | None = None,
    cwd: str | Path | None = None,
) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            argv,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            env=env,
            cwd=str(cwd) if cwd else None,
            **silent_subprocess_kwargs(),
        )
        return {
            "argv": argv,
            "return_code": proc.returncode,
            "stdout": truncate(proc.stdout),
            "stderr": truncate(proc.stderr),
            "timeout_seconds": timeout,
            "cwd": str(cwd) if cwd else "",
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "argv": argv,
            "return_code": 124,
            "stdout": truncate(exc.stdout or ""),
            "stderr": "Action timed out.",
            "timeout_seconds": timeout,
            "cwd": str(cwd) if cwd else "",
        }
    except OSError as exc:
        return {
            "argv": argv,
            "return_code": 127,
            "stdout": "",
            "stderr": str(exc),
            "timeout_seconds": timeout,
            "cwd": str(cwd) if cwd else "",
        }


def ps(script: str, timeout: float = 15.0) -> dict[str, Any]:
    return run_fixed([
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        script,
    ], timeout=timeout)


def training_guard_marker_paths() -> list[Path]:
    paths = [
        STATE_DIR / "training-guard.json",
        STATE_DIR / "active-training.json",
        default_node_root() / "training" / "active.json",
    ]
    override = approved_env_path("ENGEL_SUB_ENGEL_TRAINING_GUARD")
    if override:
        paths.insert(0, override)
    return paths


def _marker_reports_active(payload: dict[str, Any]) -> bool:
    if payload.get("active") is True or payload.get("training_active") is True:
        return True
    status = str(payload.get("status") or payload.get("state") or "").strip().lower()
    return status in {"active", "running", "started", "training"}


def _training_processes() -> list[dict[str, Any]]:
    if os.name != "nt":
        return []
    result = ps(
        "$ErrorActionPreference='SilentlyContinue'; "
        "$items = Get-CimInstance Win32_Process | Where-Object { "
        "($_.Name -match '^(python|pythonw|torchrun|accelerate)(\\.exe)?$') -and "
        "($_.CommandLine -match '(?i)(train|trainer|finetun|lora|qlora|peft)') "
        "} | ForEach-Object { [pscustomobject]@{ "
        "process_id=[int]$_.ProcessId; name=[string]$_.Name; started=[string]$_.CreationDate "
        "} }; @($items) | ConvertTo-Json -Compress",
        timeout=12.0,
    )
    if result.get("return_code") != 0:
        return []
    try:
        decoded = json.loads(str(result.get("stdout") or "[]"))
    except json.JSONDecodeError:
        return []
    rows = decoded if isinstance(decoded, list) else [decoded]
    processes: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            process_id = int(row.get("process_id") or row.get("ProcessId") or 0)
        except (TypeError, ValueError):
            process_id = 0
        if process_id <= 0:
            continue
        processes.append({
            "process_id": process_id,
            "name": str(row.get("name") or row.get("Name") or ""),
            "started": str(row.get("started") or row.get("CreationDate") or ""),
        })
    return sorted(processes, key=lambda item: int(item["process_id"]))


def training_status_payload() -> dict[str, Any]:
    marker_records: list[dict[str, Any]] = []
    for marker in training_guard_marker_paths():
        if not marker.is_file():
            continue
        payload = read_json(marker)
        marker_records.append({
            "path": str(marker),
            "active": _marker_reports_active(payload),
            "status": str(payload.get("status") or payload.get("state") or ""),
            "run_id": str(payload.get("run_id") or payload.get("job_id") or ""),
            "process_id": int(payload.get("process_id") or payload.get("pid") or 0),
        })
    processes = _training_processes()
    active = bool(processes) or any(item["active"] for item in marker_records)
    process_ids = sorted({
        *[int(item["process_id"]) for item in processes if int(item["process_id"]) > 0],
        *[int(item["process_id"]) for item in marker_records if int(item["process_id"]) > 0 and item["active"]],
    })
    return {
        "ok": True,
        "schema": "engel_sub_engel_training_guard_v1",
        "observed_at_utc": utc_stamp(),
        "training_active": active,
        "training_process_ids": process_ids,
        "training_processes": processes,
        "marker_records": marker_records,
        "guard_source": "process_and_marker_probe",
        "mutation_performed": False,
        "process_control_used": False,
    }


def training_safe_work_order_policy(order_payload: dict[str, Any]) -> dict[str, Any]:
    job_type = str(order_payload.get("job_type") or "").strip().lower()
    order_text = str(order_payload.get("order_text") or order_payload.get("task") or "").strip().lower()
    explicit_safe = order_payload.get("training_safe") is True and order_payload.get("non_invasive") is True
    mutation_terms = find_training_mutation_terms(order_text)
    safe = explicit_safe and job_type in TRAINING_SAFE_JOB_TYPES and not mutation_terms
    return {
        "training_safe": safe,
        "explicit_training_safe": explicit_safe,
        "job_type": job_type,
        "mutation_terms": mutation_terms,
        "executor_mode": "read_only" if safe else "blocked",
    }


def action_training_status() -> dict[str, Any]:
    return json_action("training.status", training_status_payload())


def action_training_safe_execute(body: dict[str, Any] | None = None) -> dict[str, Any]:
    raw = dict(body or {})
    task = dict(raw.get("payload") or {}) if isinstance(raw.get("payload"), dict) else raw
    if "order_text" not in task:
        task["order_text"] = str(task.get("task") or "")
    policy = training_safe_work_order_policy(task)
    training_before = training_status_payload()
    if not policy.get("training_safe"):
        return json_action_result("training_safe.execute", {
            "ok": False,
            "overall_ok": False,
            "status": "blocked_not_training_safe",
            "training_guard_observed": True,
            "training_guard_before": training_before,
            "training_safe_policy": policy,
            "mutation_performed": False,
            "process_control_used": False,
            "local_llm_attempted": False,
        }, return_code=7)
    training_after = training_status_payload()
    unchanged = (
        training_before.get("training_process_ids", [])
        == training_after.get("training_process_ids", [])
    )
    result = {
        "ok": unchanged,
        "overall_ok": unchanged,
        "status": "returned_training_safe_status",
        "schema": "engel_sub_engel_training_safe_task_result_v1",
        "completed_at_utc": utc_stamp(),
        "hostname": socket.gethostname(),
        "task_id": str(task.get("task_id") or task.get("id") or ""),
        "job_type": policy.get("job_type"),
        "result": {
            "hostname": socket.gethostname(),
            "node_root": str(default_node_root()),
            "state_dir": str(STATE_DIR),
            "training_active": bool(training_before.get("training_active")),
            "training_process_ids": training_before.get("training_process_ids", []),
        },
        "training_guard_observed": True,
        "training_guard_before": training_before,
        "training_guard_after": training_after,
        "training_processes_unchanged": unchanged,
        "training_safe_policy": policy,
        "mutation_performed": False,
        "process_control_used": False,
        "local_llm_attempted": False,
    }
    append_receipt({
        "event": "training_safe_task_returned",
        "task_id": result["task_id"],
        "training_active": result["result"]["training_active"],
        "training_processes_unchanged": unchanged,
    })
    return json_action_result("training_safe.execute", result, return_code=0 if unchanged else 8)


def support_roots() -> list[Path]:
    roots: list[Path] = []
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable).resolve()
        roots.extend([exe.parent.parent, exe.parent])
    here = Path(__file__).resolve().parent
    roots.extend([
        here,
        here / "workflows" / "sub_engel_nodes" / "standalone",
        Path.cwd(),
        default_node_root(),
    ])
    out: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        try:
            key = str(root.resolve()).lower()
        except OSError:
            key = str(root).lower()
        if key not in seen:
            seen.add(key)
            out.append(root)
    return out


def local_helper_manifest_path() -> Path | None:
    override = approved_env_path("ENGEL_SUB_ENGEL_LOCAL_HELPER_MANIFEST")
    if override and override.is_file():
        return override
    for root in support_roots():
        candidate = root / "models" / LOCAL_HELPER_MANIFEST_NAME
        if candidate.is_file():
            return candidate
    return None


def resolve_local_helper_model(manifest_path: Path, manifest: dict[str, Any]) -> Path:
    included = manifest.get("included_model") if isinstance(manifest.get("included_model"), dict) else {}
    rel = str(included.get("file") or "").strip()
    candidates: list[Path] = []
    if rel:
        rel_path = Path(rel)
        if rel_path.is_absolute():
            candidates.append(rel_path)
        candidates.extend([
            manifest_path.parent.parent / rel_path,
            manifest_path.parent / rel_path,
            manifest_path.parent / rel_path.name,
        ])
        for root in support_roots():
            candidates.append(root / rel_path)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0] if candidates else Path("")


def local_helper_model_status(include_hash: bool = False) -> dict[str, Any]:
    manifest_path = local_helper_manifest_path()
    if not manifest_path:
        return {
            "ok": False,
            "manifest_found": False,
            "error": "local helper model manifest not found",
        }
    manifest = read_json(manifest_path)
    included = manifest.get("included_model") if isinstance(manifest.get("included_model"), dict) else {}
    model_path = resolve_local_helper_model(manifest_path, manifest)
    expected_size = int(included.get("size_bytes") or 0)
    expected_sha = str(included.get("sha256") or "").upper()
    exists = model_path.is_file()
    status: dict[str, Any] = {
        "manifest_found": True,
        "manifest_path": str(manifest_path),
        "model_path": str(model_path),
        "model_exists": exists,
        "expected_size_bytes": expected_size,
        "family": included.get("family", ""),
        "format": included.get("format", ""),
        "quantization": included.get("quantization", ""),
        "model_output_trusted": False,
    }
    if exists:
        actual_size = model_path.stat().st_size
        status["actual_size_bytes"] = actual_size
        status["size_ok"] = actual_size == expected_size
        if include_hash:
            actual_sha = sha256_file(model_path)
            status["expected_sha256"] = expected_sha
            status["actual_sha256"] = actual_sha
            status["sha256_ok"] = actual_sha == expected_sha
            status["ok"] = actual_size == expected_size and actual_sha == expected_sha
        else:
            status["ok"] = actual_size == expected_size
    else:
        status["ok"] = False
        status["error"] = "local helper model file not found"
    return status


def local_llm_cli_candidates() -> list[Path]:
    candidates: list[Path] = []
    for key in ("ENGEL_SUB_ENGEL_LLM_CLI", "ENGEL_LOCAL_LLM_CLI", "LLAMA_CLI"):
        raw = os.environ.get(key, "").strip()
        if raw:
            candidates.append(Path(raw))
    for root in support_roots():
        candidates.extend([
            root / "runtimes" / "llama.cpp" / "cuda" / "llama-cli.exe",
            root / "runtimes" / "llama.cpp" / "cpu" / "llama-cli.exe",
            root / "bin" / "llama-cli.exe",
            root / "llama-cli.exe",
            root / "llama.cpp" / "llama-cli.exe",
            root / "runtimes" / "llama.cpp" / "llama-cli.exe",
        ])
    for name in ("llama-cli.exe", "llama-cli", "main.exe"):
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))
    out: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate).lower()
        if key not in seen:
            seen.add(key)
            out.append(candidate)
    return out


def find_local_llm_cli() -> Path | None:
    for candidate in local_llm_cli_candidates():
        if candidate.is_file() and not is_os_drive_path(candidate):
            return candidate
    return None


def local_llm_runtime_env(cli: Path) -> dict[str, str]:
    env = os.environ.copy()
    dll_dirs: list[Path] = [cli.parent]
    for root in support_roots():
        dll_dirs.extend([
            root / "runtimes" / "llama.cpp" / "cuda",
            root / "runtimes" / "llama.cpp" / "cuda_dlls",
            root / "runtimes" / "llama.cpp" / "cpu",
        ])
    existing = [
        str(path)
        for path in dll_dirs
        if path.is_dir() and not is_os_drive_path(path)
    ]
    if existing:
        env["PATH"] = os.pathsep.join(existing + [env.get("PATH", "")])
    return env


def local_helper_manifest() -> dict[str, Any]:
    manifest_path = local_helper_manifest_path()
    return read_json(manifest_path) if manifest_path else {}


def env_flag(key: str, default: bool = False) -> bool:
    raw = os.environ.get(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def module_status(names: list[str]) -> dict[str, Any]:
    try:
        from importlib import metadata
    except ImportError:
        metadata = None  # type: ignore[assignment]
    modules: dict[str, Any] = {}
    ok = True
    for name in names:
        version = ""
        error_text = ""
        if metadata is None:
            error_text = "importlib.metadata unavailable"
        else:
            try:
                version = metadata.version(name)
            except Exception as exc:
                error_text = str(exc)
        present = bool(version)
        ok = ok and present
        modules[name] = {
            "present": present,
            "version": version,
            "error": error_text,
        }
    return {"ok": ok, "modules": modules}


def adapter_base_model(adapter_dir: Path) -> str:
    config = read_json(adapter_dir / "adapter_config.json")
    return str(config.get("base_model_name_or_path") or "").strip()


def peft_adapter_candidates() -> list[Path]:
    candidates: list[Path] = []
    override = approved_env_path("ENGEL_SUB_ENGEL_PEFT_ADAPTER_DIR")
    if override:
        candidates.append(override)
    manifest_path = local_helper_manifest_path()
    manifest = read_json(manifest_path) if manifest_path else {}
    adapter = manifest.get("trained_lora_adapter") if isinstance(manifest.get("trained_lora_adapter"), dict) else {}
    rel = str(adapter.get("packaged_dir") or adapter.get("dir") or "").strip()
    if rel:
        rel_path = Path(rel)
        if rel_path.is_absolute():
            candidates.append(rel_path)
        if manifest_path:
            candidates.extend([
                manifest_path.parent.parent / rel_path,
                manifest_path.parent / rel_path,
            ])
        for root in support_roots():
            candidates.append(root / rel_path)
    out: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        try:
            key = str(candidate.resolve()).lower()
        except OSError:
            key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(candidate)
    return out


def lora_artifact_status(include_hash: bool = False) -> dict[str, Any]:
    manifest_path = local_helper_manifest_path()
    manifest = read_json(manifest_path) if manifest_path else {}
    adapter = manifest.get("trained_lora_adapter") if isinstance(manifest.get("trained_lora_adapter"), dict) else {}
    candidates = peft_adapter_candidates()
    found = next((path for path in candidates if path.is_dir() and not is_os_drive_path(path)), None)
    adapter_model = found / "adapter_model.safetensors" if found else Path("")
    receipt = read_json(found / "ENGEL_LORA_TRAINING_RECEIPT.json") if found else {}
    receipt_files = receipt.get("adapter_files") if isinstance(receipt.get("adapter_files"), dict) else {}
    receipt_model = receipt_files.get("adapter_model.safetensors") if isinstance(receipt_files.get("adapter_model.safetensors"), dict) else {}
    expected_sha = str(receipt_model.get("sha256") or adapter.get("adapter_model_sha256") or "").upper()
    status: dict[str, Any] = {
        "present": bool(found and adapter_model.is_file()),
        "artifact_dir": str(found or (candidates[0] if candidates else "")),
        "adapter_model": str(adapter_model) if found else "",
        "format": adapter.get("format", "peft_safetensors"),
        "base_model_name_or_path": adapter_base_model(found) if found else "",
        "training_receipt": str(found / "ENGEL_LORA_TRAINING_RECEIPT.json") if found and (found / "ENGEL_LORA_TRAINING_RECEIPT.json").is_file() else "",
        "trained_at_utc": adapter.get("trained_at_utc", ""),
        "selected_by": "D-local packaged adapter or explicit approved D-local override",
        "runtime_loaded_by_current_gguf_cli": False,
        "runtime_note": "PEFT LoRA adapter artifact is primary. It must be loaded with transformers/peft and its Qwen base model; llama.cpp GGUF/CUDA does not load this PEFT adapter.",
    }
    if adapter_model.is_file():
        status["adapter_model_size_bytes"] = adapter_model.stat().st_size
        status["expected_adapter_model_sha256"] = expected_sha
        if include_hash:
            actual_sha = sha256_file(adapter_model)
            status["actual_adapter_model_sha256"] = actual_sha
            status["sha256_ok"] = bool(expected_sha) and actual_sha == expected_sha
    return status


def gpu_hardware_inventory() -> dict[str, Any]:
    if os.name != "nt":
        return {
            "checked": False,
            "platform": os.name,
            "gpus": [],
            "primary_vendor": "unknown",
            "cuda_applicable": False,
            "directml_candidate": False,
            "summary": "GPU inventory is only implemented for Windows Sub-Engel nodes.",
        }
    script = (
        "$ErrorActionPreference='SilentlyContinue';"
        "Get-CimInstance Win32_VideoController | "
        "Select-Object Name,AdapterRAM,DriverVersion,PNPDeviceID | "
        "ConvertTo-Json -Depth 4 -Compress"
    )
    result = ps(script, timeout=10)
    gpus: list[dict[str, Any]] = []
    if result.get("return_code") == 0 and str(result.get("stdout") or "").strip():
        try:
            payload = json.loads(str(result.get("stdout") or ""))
            raw_items = payload if isinstance(payload, list) else [payload]
            for item in raw_items:
                if isinstance(item, dict):
                    name = str(item.get("Name") or "").strip()
                    lower = name.lower()
                    if "nvidia" in lower:
                        vendor = "nvidia"
                    elif "radeon" in lower or "amd" in lower:
                        vendor = "amd"
                    elif "intel" in lower:
                        vendor = "intel"
                    else:
                        vendor = "unknown"
                    gpus.append({
                        "name": name,
                        "vendor": vendor,
                        "adapter_ram_bytes": item.get("AdapterRAM", 0),
                        "driver_version": str(item.get("DriverVersion") or ""),
                        "pnp_device_id": str(item.get("PNPDeviceID") or ""),
                    })
        except Exception as exc:
            return {
                "checked": True,
                "gpus": [],
                "primary_vendor": "unknown",
                "cuda_applicable": False,
                "directml_candidate": False,
                "summary": f"GPU inventory parse failed: {exc}",
            }
    primary_vendor = next((str(item.get("vendor")) for item in gpus if item.get("vendor") != "unknown"), "unknown")
    cuda_applicable = primary_vendor == "nvidia"
    directml_candidate = primary_vendor in {"amd", "intel", "nvidia"}
    if cuda_applicable:
        summary = "NVIDIA GPU detected; CUDA is applicable if the driver exposes a CUDA device."
    elif primary_vendor == "amd":
        summary = "AMD Radeon GPU detected; CUDA is not applicable. Use CPU now or a DirectML/ONNX path if enabled later."
    elif primary_vendor == "intel":
        summary = "Intel GPU detected; CUDA is not applicable. Use CPU now or a DirectML/ONNX path if enabled later."
    else:
        summary = "No CUDA-capable NVIDIA GPU detected; CPU runtime is the safe default."
    return {
        "checked": True,
        "gpus": gpus,
        "primary_vendor": primary_vendor,
        "cuda_applicable": cuda_applicable,
        "directml_candidate": directml_candidate,
        "summary": summary,
    }


def peft_lora_runtime_status(include_hash: bool = False) -> dict[str, Any]:
    adapter_status = lora_artifact_status(include_hash=include_hash)
    modules = module_status(["torch", "transformers", "peft", "accelerate", "safetensors"])
    base_model = os.environ.get("ENGEL_SUB_ENGEL_PEFT_BASE_MODEL", "").strip() or str(adapter_status.get("base_model_name_or_path") or "")
    base_path = Path(base_model) if base_model else Path("")
    base_is_local = bool(base_model and base_path.exists())
    base_download_allowed = env_flag("ENGEL_SUB_ENGEL_ALLOW_PEFT_BASE_DOWNLOAD", False)
    gpu_inventory = gpu_hardware_inventory()
    cuda: dict[str, Any] = {"checked": False}
    try:
        import torch  # type: ignore

        cuda_available = bool(torch.cuda.is_available())
        cuda = {
            "checked": True,
            "torch_version": getattr(torch, "__version__", ""),
            "torch_cuda_available": cuda_available,
            "cuda_version": getattr(getattr(torch, "version", object()), "cuda", ""),
            "device_count": torch.cuda.device_count() if cuda_available else 0,
            "device_0": torch.cuda.get_device_name(0) if cuda_available else "",
        }
        if not cuda_available:
            cuda["not_available_reason"] = (
                "CUDA is not applicable on this Sub-Engel hardware; detected GPU is not NVIDIA."
                if not gpu_inventory.get("cuda_applicable")
                else "PyTorch did not see a CUDA device from the NVIDIA driver."
            )
    except Exception as exc:
        cuda = {"checked": True, "error": str(exc)}

    blocking: list[str] = []
    if not adapter_status.get("present"):
        blocking.append("PEFT LoRA adapter artifact not found")
    if not modules.get("ok"):
        blocking.append("PEFT Python modules are not all installed")
    if not base_model:
        blocking.append("adapter_config.json does not name a base model")
    elif not (base_is_local or base_download_allowed):
        blocking.append(
            "base model is not local and automatic Hugging Face download is disabled; set ENGEL_SUB_ENGEL_PEFT_BASE_MODEL to a local Qwen path or ENGEL_SUB_ENGEL_ALLOW_PEFT_BASE_DOWNLOAD=1"
        )
    ready = not blocking
    return {
        "preferred": True,
        "ready": ready,
        "blocking_reasons": blocking,
        "adapter": adapter_status,
        "runtime_imports": modules,
        "base_model_path_or_id": base_model,
        "base_model_local": base_is_local,
        "base_model_download_allowed": base_download_allowed,
        "hardware_accelerator": gpu_inventory,
        "torch_cuda": cuda,
        "active_torch_device": "cuda" if cuda.get("torch_cuda_available") else "cpu",
        "directml_candidate": bool(gpu_inventory.get("directml_candidate")),
        "runtime_mode": "peft_lora_transformers" if ready else "peft_lora_waiting_for_base_model",
        "legacy_llama_cpp_cuda_allowed": env_flag("ENGEL_SUB_ENGEL_ENABLE_LLAMA_CPP_FALLBACK", False),
        "process_model_cache": peft_runtime_cache_status(),
    }


def local_llm_status_payload(include_hash: bool = False) -> dict[str, Any]:
    model = local_helper_model_status(include_hash=include_hash)
    cli = find_local_llm_cli()
    manifest = local_helper_manifest()
    runtime = manifest.get("runtime") if isinstance(manifest.get("runtime"), dict) else {}
    cli_backend = "cuda" if cli and "cuda" in str(cli).lower() else "cpu_or_unknown"
    peft_status = peft_lora_runtime_status(include_hash=include_hash)
    torch_cuda = peft_status.get("torch_cuda") if isinstance(peft_status.get("torch_cuda"), dict) else {}
    cpu_peft_allowed = env_flag("ENGEL_SUB_ENGEL_ALLOW_CPU_PEFT_GENERATION", False)
    memory_safe_gguf = bool(
        peft_status.get("ready")
        and not torch_cuda.get("torch_cuda_available")
        and not cpu_peft_allowed
        and model.get("ok")
        and cli
    )
    legacy_allowed = env_flag("ENGEL_SUB_ENGEL_ENABLE_LLAMA_CPP_FALLBACK", False) or memory_safe_gguf
    gpu_layers_default = (
        runtime.get("gpu_layers_default", 99 if cli_backend == "cuda" else 0)
        if torch_cuda.get("torch_cuda_available")
        else 0
    )
    return {
        "ok": bool(peft_status.get("ready") or (model.get("ok") and cli)),
        "preferred_runtime": "quantized_gguf_cpu" if memory_safe_gguf else "peft_lora_transformers",
        "peft_lora_runtime": peft_status,
        "legacy_llama_cpp": {
            "enabled": legacy_allowed,
            "model": model,
            "runtime_cli": str(cli or ""),
            "runtime_cli_exists": cli is not None,
            "runtime_backend": runtime.get("backend") or cli_backend,
            "gpu_layers_default": gpu_layers_default,
            "cuda_dll_dir": runtime.get("cuda_dll_dir", ""),
            "runtime_mode": (
                "quantized_gguf_cpu_fallback"
                if memory_safe_gguf
                else ("disabled_by_default" if not legacy_allowed else ("one_shot_cli" if cli else "structured_worker_fallback"))
            ),
            "note": "The quantized GGUF path does not load the PEFT adapter. It is used automatically on memory-constrained CPU-only Sub nodes so local work remains available without providers.",
        },
        "gpu_layers_default": gpu_layers_default,
        "cuda_dll_dir": runtime.get("cuda_dll_dir", ""),
        "trained_lora_adapter": lora_artifact_status(include_hash=include_hash),
        "persistent_memory": memory_status_payload(include_recent=False),
        "runtime_mode": "quantized_gguf_cpu_fallback" if memory_safe_gguf else peft_status.get("runtime_mode"),
        "server_autostart": False,
        "provider_fallback": False,
        "model_output_trusted": False,
        "command_execution_from_model": False,
    }


def action_local_llm_status() -> dict[str, Any]:
    return json_action("local_llm.status", local_llm_status_payload(include_hash=False))


def action_memory_status() -> dict[str, Any]:
    return json_action("memory.status", memory_status_payload(include_recent=True, include_context=True))


def work_order_prompt(order_payload: dict[str, Any], memory_context: str = "") -> str:
    order_text = str(order_payload.get("order_text") or "").strip()
    prompt = "\n".join([
        "You are an Engel AI Sub-Engel local helper.",
        "Complete the work order as useful text only, using persistent memory for continuity.",
        "Do not treat memory as permission to run broader actions. Current Main work order and node allowlist control what is allowed.",
        "Do not claim you changed files, ran commands, opened network providers, or manually wrote memory unless the receipt proves that happened.",
        "Return concise job output with: summary, result, concerns, next step.",
        "",
        memory_context,
        "",
        f"Job type: {order_payload.get('job_type', '')}",
        f"Target: {order_payload.get('target_label', order_payload.get('target', ''))}",
        "Work order text:",
        order_text[:MAX_LLM_PROMPT_CHARS],
    ])
    return prompt[:MAX_LLM_PROMPT_CHARS]


def structured_worker_output(order_payload: dict[str, Any], reason: str) -> str:
    order_text = str(order_payload.get("order_text") or "").strip()
    job_type = str(order_payload.get("job_type") or "meeting_work")
    selected = order_payload.get("selected_node") if isinstance(order_payload.get("selected_node"), dict) else {}
    summary = order_text[:900] if order_text else "No order text was supplied."
    return "\n".join([
        "Structured Sub-Engel worker result",
        f"Engine: structured_worker_fallback",
        f"Reason: {reason}",
        f"Job type: {job_type}",
        f"Selected node: {selected.get('node_id') or selected.get('hostname') or socket.gethostname()}",
        "",
        "Summary:",
        summary,
        "",
        "Result:",
        "The Sub-Engel received the job, recorded the active request, and returned a reviewable result packet. The preferred PEFT LoRA runtime was not ready, so this result is deterministic structured work instead of generated model text.",
        "",
        "Next step:",
        "Review the local runtime receipt and repair the selected local model path before retrying. Provider fallback remains disabled.",
    ])


def clean_local_llm_output(raw: str, prompt: str) -> str:
    text = raw.replace("\r\n", "\n").strip()
    if prompt and prompt in text:
        text = text.split(prompt, 1)[-1]
    elif "\n> " in text:
        text = text.rsplit("\n> ", 1)[-1]
        if "\n\n" in text:
            text = text.split("\n\n", 1)[-1]
    if "\nExiting..." in text:
        text = text.split("\nExiting...", 1)[0]
    for marker in ("\n Summary:", "\nSummary:", "\n Result:", "\nResult:"):
        index = text.find(marker)
        if index >= 0:
            return text[index:].strip()
    cleaned_lines: list[str] = []
    skip_prefixes = (
        "Loading model", "build      :", "model      :", "modalities :",
        "available commands:", "/exit", "/regen", "/clear", "/read", "/glob", ">",
    )
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or any(stripped.startswith(prefix) for prefix in skip_prefixes):
            continue
        if stripped and not any(ch.isalnum() for ch in stripped):
            continue
        cleaned_lines.append(line)
    cleaned = "\n".join(cleaned_lines).strip()
    return cleaned or raw.strip()

def run_local_llm_server(prompt: str, status: dict[str, Any]) -> dict[str, Any] | None:
    """Try the persistent local llama-server first; return None to fall back to one-shot CLI.

    Never raises: any connection/parse problem returns None so the caller's
    existing llama-cli path runs unchanged. Server binds 127.0.0.1 only.
    """
    server_url = os.environ.get("ENGEL_SUB_ENGEL_LLM_SERVER_URL", "http://127.0.0.1:8790").strip()
    if not server_url:
        return None
    base = server_url.rstrip("/")
    try:
        # The server attempt gets its own SMALL budget so a hung server cannot
        # stack with the CLI fallback's 120s (server 45s + CLI 120s worst case).
        timeout_seconds = float(os.environ.get("ENGEL_SUB_ENGEL_LLM_SERVER_TIMEOUT_SECONDS", "45"))
    except ValueError:
        timeout_seconds = 45.0
    try:
        payload = json.dumps({
            "prompt": prompt,
            "n_predict": int(os.environ.get("ENGEL_SUB_ENGEL_LLM_MAX_TOKENS", "128")),
            "temperature": float(os.environ.get("ENGEL_SUB_ENGEL_LLM_TEMP", "0.2")),
            "stream": False,
        }).encode("utf-8")
        req = request.Request(
            base + "/completion",
            data=payload,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=timeout_seconds) as resp:
            body = json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception:
        return None
    if not isinstance(body, dict):
        # Valid JSON that is not an object (list/str/null/number) means whatever
        # answered on this port is not llama-server: fall back, never raise.
        return None
    output = str(body.get("content") or "").strip()
    if not output:
        return None
    return {
        "ok": True,
        "engine": "local_llm_server",
        "llm_attempted": True,
        "status": status,
        "trained_lora_adapter": status.get("trained_lora_adapter", {}),
        "runtime": {
            "server_url": base,
            "timeout_seconds": timeout_seconds,
            "tokens_predicted": body.get("tokens_predicted"),
        },
        "output": output[:MAX_LLM_OUTPUT_CHARS],
        "model_output_trusted": False,
    }


def get_or_load_peft_runtime(base_model: str, adapter_dir: str) -> tuple[dict[str, Any], bool]:
    cache_key = f"{base_model}|{str(Path(adapter_dir))}"
    cached_key = str(_PEFT_RUNTIME_CACHE.get("key") or "")
    if cached_key == cache_key and _PEFT_RUNTIME_CACHE.get("model") and _PEFT_RUNTIME_CACHE.get("tokenizer"):
        _PEFT_RUNTIME_CACHE["last_used_at_utc"] = utc_stamp()
        return _PEFT_RUNTIME_CACHE, True

    import torch  # type: ignore
    from peft import PeftModel  # type: ignore
    from transformers import AutoModelForCausalLM, AutoTokenizer  # type: ignore

    dtype = torch.float16 if torch.cuda.is_available() else torch.float32
    tokenizer = AutoTokenizer.from_pretrained(adapter_dir, trust_remote_code=False)
    if getattr(tokenizer, "pad_token_id", None) is None and getattr(tokenizer, "eos_token", None):
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        base_model,
        torch_dtype=dtype,
        device_map="auto",
        low_cpu_mem_usage=True,
        trust_remote_code=False,
    )
    model = PeftModel.from_pretrained(model, adapter_dir)
    model.eval()

    _PEFT_RUNTIME_CACHE.clear()
    _PEFT_RUNTIME_CACHE.update({
        "key": cache_key,
        "base_model": base_model,
        "adapter_dir": adapter_dir,
        "loaded_at_utc": utc_stamp(),
        "last_used_at_utc": utc_stamp(),
        "torch": torch,
        "tokenizer": tokenizer,
        "model": model,
    })
    return _PEFT_RUNTIME_CACHE, False


def run_peft_lora_helper(prompt: str, status: dict[str, Any]) -> dict[str, Any] | None:
    peft_status = status.get("peft_lora_runtime") if isinstance(status.get("peft_lora_runtime"), dict) else {}
    if not peft_status.get("ready"):
        return None
    torch_cuda = peft_status.get("torch_cuda") if isinstance(peft_status.get("torch_cuda"), dict) else {}
    if not torch_cuda.get("torch_cuda_available") and not env_flag("ENGEL_SUB_ENGEL_ALLOW_CPU_PEFT_GENERATION", False):
        return None
    adapter = peft_status.get("adapter") if isinstance(peft_status.get("adapter"), dict) else {}
    adapter_dir = str(adapter.get("artifact_dir") or "").strip()
    base_model = str(peft_status.get("base_model_path_or_id") or "").strip()
    if not adapter_dir or not base_model:
        return None
    try:
        runtime, cache_reused = get_or_load_peft_runtime(base_model, adapter_dir)
        torch = runtime["torch"]
        tokenizer = runtime["tokenizer"]
        model = runtime["model"]
        max_new_tokens = int(os.environ.get("ENGEL_SUB_ENGEL_PEFT_MAX_NEW_TOKENS", "64"))
        temperature = float(os.environ.get("ENGEL_SUB_ENGEL_PEFT_TEMP", "0.2"))
        inputs = tokenizer(prompt, return_tensors="pt")
        if torch.cuda.is_available():
            inputs = {key: value.to(model.device) for key, value in inputs.items()}
        with torch.no_grad():
            generated = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=temperature > 0,
                temperature=temperature if temperature > 0 else None,
                pad_token_id=tokenizer.eos_token_id,
            )
        output = tokenizer.decode(generated[0][inputs["input_ids"].shape[-1]:], skip_special_tokens=True).strip()
        if not output:
            return None
        return {
            "ok": True,
            "engine": "peft_lora_transformers",
            "llm_attempted": True,
            "status": status,
            "trained_lora_adapter": adapter,
            "runtime": {
                "base_model": base_model,
                "adapter_dir": adapter_dir,
                "torch_cuda_available": bool(torch.cuda.is_available()),
                "device": str(getattr(model, "device", "")),
                "max_new_tokens": max_new_tokens,
                "process_cache_reused": cache_reused,
                "process_cache_loaded_at_utc": runtime.get("loaded_at_utc", ""),
            },
            "output": output[:MAX_LLM_OUTPUT_CHARS],
            "model_output_trusted": False,
        }
    except Exception as exc:
        return {
            "ok": True,
            "engine": "structured_worker_fallback",
            "llm_attempted": True,
            "fallback_reason": f"PEFT LoRA runtime failed: {exc}",
            "status": status,
            "trained_lora_adapter": adapter,
            "output": "",
            "model_output_trusted": False,
        }


def attach_executor_memory(result: dict[str, Any], memory_context: str) -> dict[str, Any]:
    result["persistent_memory"] = memory_status_payload(include_recent=False)
    result["memory_context_used"] = bool(memory_context)
    result["memory_context_chars"] = len(memory_context)
    return result


def run_local_helper_llm(order_payload: dict[str, Any]) -> dict[str, Any]:
    status = local_llm_status_payload(include_hash=False)
    memory_context = persistent_memory_context(order_payload)
    prompt = work_order_prompt(order_payload, memory_context=memory_context)
    peft_result = run_peft_lora_helper(prompt, status)
    if peft_result is not None:
        if peft_result.get("output"):
            return attach_executor_memory(peft_result, memory_context)
        reason = str(peft_result.get("fallback_reason") or "PEFT LoRA runtime returned no output")
        return attach_executor_memory({
            "ok": True,
            "engine": "structured_worker_fallback",
            "llm_attempted": bool(peft_result.get("llm_attempted")),
            "fallback_reason": reason,
            "status": status,
            "trained_lora_adapter": status.get("trained_lora_adapter", {}),
            "output": structured_worker_output(order_payload, reason),
            "model_output_trusted": False,
        }, memory_context)

    peft_status = status.get("peft_lora_runtime") if isinstance(status.get("peft_lora_runtime"), dict) else {}
    legacy = status.get("legacy_llama_cpp") if isinstance(status.get("legacy_llama_cpp"), dict) else {}
    if not legacy.get("enabled"):
        reasons = peft_status.get("blocking_reasons") if isinstance(peft_status.get("blocking_reasons"), list) else []
        reason = "; ".join(str(item) for item in reasons) or "PEFT LoRA runtime is preferred but not ready; legacy llama.cpp CUDA fallback is disabled"
        return attach_executor_memory({
            "ok": True,
            "engine": "structured_worker_fallback",
            "llm_attempted": False,
            "fallback_reason": reason,
            "status": status,
            "trained_lora_adapter": status.get("trained_lora_adapter", {}),
            "output": structured_worker_output(order_payload, reason),
            "model_output_trusted": False,
        }, memory_context)

    server_result = run_local_llm_server(prompt, status)
    if server_result is not None:
        server_result["legacy_fallback_used"] = True
        return attach_executor_memory(server_result, memory_context)
    # (2026-07-11) The PEFT-preferred status restructure nested the legacy
    # fields under status["legacy_llama_cpp"] and redefined top-level "ok" as
    # PEFT-readiness — but this executor still read the old FLAT shape, so the
    # legacy one-shot was unreachable (always "missing local LLM CLI") even
    # with the fallback enabled and a valid ENGEL_SUB_ENGEL_LLM_CLI. Read the
    # nested shape first, keep the flat reads as back-compat, and gate on the
    # MODEL check's own ok (peft-readiness is irrelevant to the legacy path).
    model = legacy.get("model") if isinstance(legacy.get("model"), dict) else {}
    if not model:
        model = status.get("model") if isinstance(status.get("model"), dict) else {}
    cli = str(legacy.get("runtime_cli") or status.get("runtime_cli") or "")
    if not (model.get("ok") and cli and model.get("model_path")):
        reason = "missing local LLM CLI" if not cli else str(model.get("error") or "local helper model unavailable")
        return attach_executor_memory({
            "ok": True,
            "engine": "structured_worker_fallback",
            "llm_attempted": False,
            "fallback_reason": reason,
            "status": status,
            "trained_lora_adapter": status.get("trained_lora_adapter", {}),
            "output": structured_worker_output(order_payload, reason),
            "model_output_trusted": False,
        }, memory_context)
    runtime = local_helper_manifest().get("runtime") if isinstance(local_helper_manifest().get("runtime"), dict) else {}
    gpu_layers = os.environ.get("ENGEL_SUB_ENGEL_LLM_GPU_LAYERS", "").strip()
    if not gpu_layers:
        gpu_layers = str(legacy.get("gpu_layers_default", status.get("gpu_layers_default", 0)))
    argv = [
        cli,
        "-m",
        str(model.get("model_path")),
        "-p",
        prompt,
        "-n",
        str(int(os.environ.get("ENGEL_SUB_ENGEL_LLM_MAX_TOKENS", "128"))),
        # (2026-07-11) Without -c, llama-cli sizes the KV cache for the model's
        # FULL training context (32k on Mistral-7B ≈ a 4GB buffer) — the alloc
        # failed on the ROG (0xC0000005) whenever the GPU chat server was also
        # resident. A work-order prompt + 384-token reply fits easily in 4k.
        "-c",
        str(int(os.environ.get("ENGEL_SUB_ENGEL_LLM_CTX", "4096"))),
        "--temp",
        str(float(os.environ.get("ENGEL_SUB_ENGEL_LLM_TEMP", "0.2"))),
        "--no-display-prompt",
        "--single-turn",
        "--no-show-timings",
        "--no-warmup",
    ]
    if gpu_layers:
        argv.extend(["-ngl", gpu_layers])
    run = run_fixed(
        argv,
        timeout=float(os.environ.get("ENGEL_SUB_ENGEL_LLM_TIMEOUT_SECONDS", "300")),
        env=local_llm_runtime_env(Path(cli)),
    )
    output = clean_local_llm_output(str(run.get("stdout") or ""), prompt)
    if run.get("return_code") == 0 and output:
        return attach_executor_memory({
            "ok": True,
            "engine": "local_llm_one_shot",
            "llm_attempted": True,
            "status": status,
            "trained_lora_adapter": status.get("trained_lora_adapter", {}),
            "runtime": {
                "argv0": cli,
                "return_code": run.get("return_code"),
                "timeout_seconds": run.get("timeout_seconds"),
                "gpu_layers": gpu_layers,
            },
            "output": output[:MAX_LLM_OUTPUT_CHARS],
            "model_output_trusted": False,
        }, memory_context)
    reason = str(run.get("stderr") or "local LLM runtime returned no output")[:1000]
    return attach_executor_memory({
        "ok": True,
        "engine": "structured_worker_fallback",
        "llm_attempted": True,
        "fallback_reason": reason,
        "status": status,
        "trained_lora_adapter": status.get("trained_lora_adapter", {}),
        "runtime": {
            "argv0": cli,
            "return_code": run.get("return_code"),
            "timeout_seconds": run.get("timeout_seconds"),
            "gpu_layers": gpu_layers,
        },
        "output": structured_worker_output(order_payload, reason),
        "model_output_trusted": False,
    }, memory_context)


def direct_work_safe_id(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw or len(raw) > 160:
        raise ValueError("work order id must contain 1-160 characters")
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", raw).strip("._-")
    if not safe:
        raise ValueError("work order id has no safe filename characters")
    return safe[:160]


def action_direct_work_execute(body: dict[str, Any]) -> dict[str, Any]:
    supplied = body.get("work_order")
    if supplied is None:
        supplied = body.get("payload")
    if not isinstance(supplied, dict):
        return json_action_result(DIRECT_WORK_ACTION, {
            "ok": False,
            "error": "work_order must be a JSON object",
        }, return_code=2)

    order_payload = dict(supplied)
    order_id = str(order_payload.get("id") or order_payload.get("order_id") or "").strip()
    order_text = str(order_payload.get("order_text") or "").strip()
    try:
        safe_id = direct_work_safe_id(order_id)
    except ValueError as exc:
        return json_action_result(DIRECT_WORK_ACTION, {"ok": False, "error": str(exc)}, return_code=2)
    if not order_text:
        return json_action_result(DIRECT_WORK_ACTION, {
            "ok": False,
            "error": "work_order.order_text is required",
        }, return_code=2)
    if len(order_text) > MAX_LLM_PROMPT_CHARS:
        return json_action_result(DIRECT_WORK_ACTION, {
            "ok": False,
            "error": f"work_order.order_text exceeds {MAX_LLM_PROMPT_CHARS} characters",
        }, return_code=2)

    order_payload["id"] = order_id
    order_payload["order_id"] = order_id
    order_payload["schema"] = str(order_payload.get("schema") or DIRECT_WORK_SCHEMA)
    order_payload["proof_required"] = bool(order_payload.get("proof_required", True))
    order_payload["source"] = "CT246 Engel AI Main authenticated direct HTTP"
    order_payload["transport"] = "ct246_authenticated_direct_http"

    targets_this_node, target_reason = work_order_targets_this_node(order_payload)
    if not targets_this_node:
        return json_action_result(DIRECT_WORK_ACTION, {
            "ok": False,
            "error": "work order does not target this Sub-Engel",
            "reason": target_reason,
            "order_id": order_id,
            "hostname": socket.gethostname(),
        }, return_code=2)

    paths = node_work_dirs()
    incoming = paths["incoming"] / f"direct-{safe_id}.json"
    done = paths["done"] / f"direct-{safe_id}.done.json"
    canonical = json.dumps(order_payload, sort_keys=True, separators=(",", ":"))
    order_sha256 = sha256_text(canonical)

    if done.exists():
        existing = read_json(done)
        if str(existing.get("order_sha256") or "") != order_sha256:
            return json_action_result(DIRECT_WORK_ACTION, {
                "ok": False,
                "error": "work order id already completed with different content",
                "order_id": order_id,
                "done_file": str(done),
            }, return_code=2)
        existing["idempotent_replay"] = True
        return json_action_result(DIRECT_WORK_ACTION, existing)

    if incoming.exists():
        existing_order = read_json(incoming)
        existing_sha256 = sha256_text(json.dumps(existing_order, sort_keys=True, separators=(",", ":")))
        if existing_sha256 != order_sha256:
            return json_action_result(DIRECT_WORK_ACTION, {
                "ok": False,
                "error": "work order id is already staged with different content",
                "order_id": order_id,
                "incoming_file": str(incoming),
            }, return_code=2)
    else:
        write_json(incoming, order_payload)

    training_before = training_status_payload()
    training_policy = training_safe_work_order_policy(order_payload)
    operator_status = "done"
    if training_before.get("training_active") and training_policy.get("training_safe"):
        executor = {
            "ok": True,
            "engine": "training-safe-status-snapshot",
            "output": json.dumps({
                "hostname": socket.gethostname(),
                "training_active": True,
                "training_process_ids": training_before.get("training_process_ids", []),
                "node_root": str(paths["root"]),
                "state_dir": str(STATE_DIR),
            }, sort_keys=True),
            "llm_attempted": False,
            "status": training_before,
            "trained_lora_adapter": {},
        }
    elif training_before.get("training_active"):
        operator_status = "deferred_training_active"
        executor = {
            "ok": False,
            "engine": "training-guard",
            "output": "Work deferred because Sub-Engel training is active and the task is not an approved read-only status job.",
            "llm_attempted": False,
            "status": training_before,
            "trained_lora_adapter": {},
        }
    else:
        executor = run_local_helper_llm(order_payload)

    training_after = training_status_payload()
    training_processes_unchanged = (
        training_before.get("training_process_ids", [])
        == training_after.get("training_process_ids", [])
    )
    if training_before.get("training_active"):
        memory_update = {
            "ok": True,
            "status": "skipped_training_active",
            "mutation_performed": False,
        }
    else:
        try:
            memory_update = record_persistent_memory_episode(
                order_payload,
                executor,
                {
                    "action": DIRECT_WORK_ACTION,
                    "order_id": order_id,
                    "source_work_order": "authenticated_http_request",
                    "incoming_file": str(incoming),
                    "done_file": str(done),
                },
            )
        except Exception as exc:
            memory_update = {
                "ok": False,
                "error": str(exc),
                "memory_core": str(memory_core_path()),
                "memory_episodes": str(memory_episodes_path()),
            }

    worker_engine = str(executor.get("engine") or "")
    real_worker_engines = {
        "local_llm_one_shot",
        "local_llm_server",
        "peft_lora_transformers",
        "training-safe-status-snapshot",
    }
    real_worker_completion = bool(
        worker_engine in real_worker_engines
        and str(executor.get("output") or "").strip()
    )
    local_llm_completed = bool(
        worker_engine in {
            "local_llm_one_shot",
            "local_llm_server",
            "peft_lora_transformers",
        }
        and executor.get("llm_attempted") is True
    )
    overall_ok = (
        bool(executor.get("ok"))
        and real_worker_completion
        and training_processes_unchanged
        and bool(memory_update.get("ok"))
    )
    receipt = {
        "schema": DIRECT_WORK_RECEIPT_SCHEMA,
        "ok": overall_ok,
        "event": (
            "windows_sub_engel_direct_work_completed"
            if overall_ok
            else "windows_sub_engel_direct_work_failed"
        ),
        "runtime": "engel-ai-rs",
        "source": "CT246 Engel AI Main authenticated direct HTTP",
        "transport": "ct246_authenticated_direct_http",
        "action": DIRECT_WORK_ACTION,
        "hostname": socket.gethostname(),
        "completed_at_utc": utc_stamp(),
        "order_id": order_id,
        "order_sha256": order_sha256,
        "incoming_file": str(incoming),
        "done_file": str(done),
        "operator_status": operator_status,
        "worker_engine": worker_engine,
        "worker_output": str(executor.get("output", ""))[:MAX_LLM_OUTPUT_CHARS],
        "local_llm_attempted": bool(executor.get("llm_attempted")),
        "local_llm_completed": local_llm_completed,
        "real_worker_completion": real_worker_completion,
        "fallback_reason": str(executor.get("fallback_reason") or "")[:1000],
        "local_llm_status": executor.get("status", {}),
        "trained_lora_adapter": executor.get("trained_lora_adapter", {}),
        "persistent_memory": memory_update,
        "training_guard_observed": True,
        "training_guard_before": training_before,
        "training_guard_after": training_after,
        "training_processes_unchanged": training_processes_unchanged,
        "training_safe_policy": training_policy,
        "model_output_trusted": False,
        "auto_apply": False,
        "requires_review_before_apply": True,
    }
    write_json(done, receipt)
    receipt_path = unique_child(
        paths["receipts"],
        f"direct-work-{safe_id}-{utc_now().strftime('%Y%m%dT%H%M%SZ')}.json",
    )
    write_json(receipt_path, {**receipt, "receipt_file": str(receipt_path)})
    receipt["receipt_file"] = str(receipt_path)
    append_receipt({
        "event": "direct_work_completed",
        "order_id": order_id,
        "order_sha256": order_sha256,
        "worker_engine": receipt["worker_engine"],
        "local_llm_attempted": receipt["local_llm_attempted"],
        "overall_ok": overall_ok,
        "training_processes_unchanged": training_processes_unchanged,
    })
    return json_action_result(DIRECT_WORK_ACTION, receipt, return_code=0 if overall_ok else 3)


def json_action(action: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "action": action,
        "return_code": 0,
        "stdout": json.dumps(payload, indent=2, sort_keys=True),
        "stderr": "",
        "timeout_seconds": 0,
    }


def json_action_result(action: str, payload: dict[str, Any], return_code: int = 0) -> dict[str, Any]:
    return {
        "action": action,
        "return_code": return_code,
        "stdout": json.dumps(payload, indent=2, sort_keys=True),
        "stderr": "" if return_code == 0 else str(payload.get("error", "action failed")),
        "timeout_seconds": 0,
    }


def text_action(action: str, text: str) -> dict[str, Any]:
    return {
        "action": action,
        "return_code": 0,
        "stdout": text,
        "stderr": "",
        "timeout_seconds": 0,
    }


def public_state() -> dict[str, Any]:
    state = read_json(public_state_path())
    merged = {
        "role": ROLE,
        "display_role": DISPLAY_ROLE,
        "node_os": "windows",
        "remote_control": "paired_main_trusted_control",
        "authority_model": "paired_main_trusted_full_control",
        "control_planes": {
            "http_api": "bearer-authenticated allowlisted actions",
            "paired_main_shell": "main.shell action, bearer-authenticated and audited, gated by state/main-full-control.json",
            "paired_main_disk_control": "disk.control action, bearer-authenticated and audited, gated by state/main-full-control.json",
            "direct_work": "CT246 authenticated direct_work.execute -> reviewed proof return",
            "agent_refresh": "CT246 authenticated staged deployment with SHA256 proof and rollback copy",
        },
        "default_enabled": False,
        "lan_bind_requires_approval": True,
        "pairing_required": True,
        "approval_token_required_for_lan": APPROVAL_TOKEN,
        "allowed_actions": sorted(ALLOWED_ACTIONS),
        "blocked_actions": BLOCKED_ACTIONS,
        "raw_shell": False,
        "paired_main_shell": main_shell_enabled(),
        "paired_main_disk_control": main_disk_enabled(),
        "paired_main_destructive_disk_control": destructive_disk_allowed(),
        "main_full_control": main_full_control_status_payload(),
        "ssh": False,
        "disk_install_remote": False,
        "provider_api_runtime": False,
        "model_runtime": False,
        "background_workers": False,
        **state,
    }
    # Runtime state is allowed to add details, but it must not make the node
    # advertise a stale action or control schema after the source changes.
    merged["allowed_actions"] = sorted(ALLOWED_ACTIONS)
    merged["blocked_actions"] = BLOCKED_ACTIONS
    merged["authority_model"] = "paired_main_trusted_full_control"
    merged["control_planes"] = {
        "http_api": "bearer-authenticated allowlisted actions",
        "paired_main_shell": "main.shell action, bearer-authenticated and audited, gated by state/main-full-control.json",
        "paired_main_disk_control": "disk.control action, bearer-authenticated and audited, gated by state/main-full-control.json",
        "direct_work": "CT246 authenticated direct_work.execute -> reviewed proof return",
        "agent_refresh": "CT246 authenticated staged deployment with SHA256 proof and rollback copy",
    }
    merged["paired_main_shell"] = main_shell_enabled()
    merged["paired_main_disk_control"] = main_disk_enabled()
    merged["paired_main_destructive_disk_control"] = destructive_disk_allowed()
    merged["main_full_control"] = main_full_control_status_payload()
    session = read_json(session_path())
    if session and not is_expired(str(session.get("expires_at_utc", ""))):
        merged["pairing_status"] = "paired"
        merged["controller_name"] = session.get("controller_name", merged.get("controller_name", ""))
        merged["session_expires_at_utc"] = session.get("expires_at_utc", "")
    return merged


def write_public_state(**updates: Any) -> None:
    state = public_state()
    state.update(updates)
    try:
        write_json(public_state_path(), state)
    except OSError:
        pass


def create_pairing_session() -> dict[str, Any]:
    ensure_state_dir()
    code = generate_pairing_code()
    created = utc_now()
    session = {
        "role": ROLE,
        "node_os": "windows",
        "pairing_code_hash": sha256_text(code),
        "pairing_code_hint": redacted(code),
        "created_at_utc": utc_stamp(created),
        "expires_at_utc": utc_stamp(created + timedelta(seconds=PAIRING_TTL_SECONDS)),
        "used": False,
    }
    write_json(pairing_path(), session)
    write_public_state(pairing_status="waiting", last_pairing_code_hint=redacted(code))
    return {"pairing_code": code, **session}


def valid_proposed_session_token(token: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9_-]{32,256}", str(token or "")))


def create_session(
    controller_name: str,
    proposed_session_token: str = "",
) -> dict[str, Any]:
    ensure_state_dir()
    if proposed_session_token and not valid_proposed_session_token(proposed_session_token):
        raise ValueError("proposed session token has an invalid shape")
    token = proposed_session_token or secrets.token_urlsafe(32)
    created = utc_now()
    data = {
        "role": ROLE,
        "node_os": "windows",
        "session_token_hash": sha256_text(token),
        "session_token_hint": redacted(token),
        "controller_name": controller_name[:80] if controller_name else "engel-ai-controller",
        "created_at_utc": utc_stamp(created),
        "expires_at_utc": utc_stamp(created + timedelta(seconds=SESSION_TTL_SECONDS)),
    }
    write_json(session_path(), data)
    write_public_state(pairing_status="paired", controller_name=data["controller_name"])
    return {"session_token": token, **data}


def action_session_renew() -> dict[str, Any]:
    current = read_json(session_path())
    controller_name = str(current.get("controller_name") or "Engel AI Controller")
    renewed = create_session(controller_name)
    append_receipt({
        "event": "paired_session_renewed",
        "controller_name": renewed["controller_name"],
        "expires_at_utc": renewed["expires_at_utc"],
    })
    return json_action("session.renew", {
        "ok": True,
        "session_token": renewed["session_token"],
        "session_token_hint": renewed["session_token_hint"],
        "controller_name": renewed["controller_name"],
        "expires_at_utc": renewed["expires_at_utc"],
        "renewed_at_utc": utc_stamp(),
    })


def current_session_valid(token: str) -> tuple[bool, str]:
    session = read_json(session_path())
    if not session:
        return False, "no paired session"
    if is_expired(str(session.get("expires_at_utc", ""))):
        return False, "paired session expired"
    expected = str(session.get("session_token_hash", ""))
    if not secrets.compare_digest(sha256_text(token), expected):
        return False, "invalid bearer token"
    return True, "ok"


def current_session_record_is_live() -> bool:
    session = read_json(session_path())
    return bool(
        session
        and str(session.get("session_token_hash") or "")
        and not is_expired(str(session.get("expires_at_utc") or ""))
    )


def host_requires_lan_approval(host: str) -> bool:
    return host not in {"127.0.0.1", "localhost", "::1"}


def local_ips() -> list[str]:
    found: list[str] = []
    try:
        host = socket.gethostname()
        for _, _, _, _, sockaddr in socket.getaddrinfo(host, None):
            ip = str(sockaddr[0])
            if ":" not in ip and not ip.startswith("127.") and ip not in found:
                found.append(ip)
    except OSError:
        pass
    return found


def action_node_status() -> dict[str, Any]:
    node_root = default_node_root()
    session = read_json(session_path())
    paired = bool(session and not is_expired(str(session.get("expires_at_utc", ""))))
    temp_dir = node_root / "temp"
    return json_action("node.status", {
        "role": ROLE,
        "display_role": DISPLAY_ROLE,
        "node_os": "windows",
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "node_root": str(node_root),
        "state_dir": str(STATE_DIR),
        "node_root_on_os_drive": is_os_drive_path(node_root),
        "state_dir_on_os_drive": is_os_drive_path(STATE_DIR),
        "temp_dir": str(temp_dir),
        "temp_dir_on_os_drive": is_os_drive_path(temp_dir),
        "local_ips": local_ips(),
        "controller": str(session.get("controller_name") or "not paired") if paired else "not paired",
        "remote_control": "paired Main trusted-control node",
        "authority_model": "paired_main_trusted_full_control",
        "provider_api_runtime": "inactive",
        "model_runtime": "local LLM runtime may be active on localhost",
        "background_workers": "authenticated direct listener only; shared-room polling disabled",
        "raw_shell": "disabled except paired Main main.shell action when full-control gate is enabled",
        "paired_main_shell": main_shell_enabled(),
        "paired_main_disk_control": main_disk_enabled(),
        "paired_main_destructive_disk_control": destructive_disk_allowed(),
        "main_full_control": main_full_control_status_payload(),
        "ssh": "disabled",
    })


def action_node_hardware() -> dict[str, Any]:
    script = (
        "$ErrorActionPreference='SilentlyContinue';"
        "$obj=[ordered]@{};"
        "$obj.computer=Get-CimInstance Win32_ComputerSystem | "
        "Select-Object Manufacturer,Model,TotalPhysicalMemory;"
        "$obj.cpu=Get-CimInstance Win32_Processor | "
        "Select-Object Name,NumberOfCores,NumberOfLogicalProcessors;"
        "$obj.os=Get-CimInstance Win32_OperatingSystem | "
        "Select-Object Caption,Version,BuildNumber,OSArchitecture,LastBootUpTime;"
        "$obj.disks=Get-CimInstance Win32_LogicalDisk | "
        "Select-Object DeviceID,DriveType,Size,FreeSpace,FileSystem;"
        "$obj | ConvertTo-Json -Depth 4 -Compress"
    )
    result = ps(script, timeout=20)
    return {"action": "node.hardware", **result}


def action_node_safety() -> dict[str, Any]:
    return text_action("node.safety", "\n".join([
        "Windows Sub-Engel safety posture:",
        "  Preserves Windows: yes",
        f"  Paired Main shell action: {'enabled' if main_shell_enabled() else 'disabled'}",
        f"  Paired Main disk.control action: {'enabled' if main_disk_enabled() else 'disabled'}",
        f"  Destructive disk.control operations: {'enabled with confirmation token' if destructive_disk_allowed() else 'disabled'}",
        "  Raw unauthenticated shell: disabled",
        "  SSH: disabled",
        "  Paired Main authority: trusted full-control intent",
        "  HTTP command surface: bearer-authenticated allowlist",
        "  Deployment: CT246 authenticated staged update with SHA256 and rollback proof",
        "  Remote disk install/format/partition endpoint: disabled; use audited disk.control for allowed file operations",
        "  Package install from remote: disabled",
        "  Windows service install: disabled",
        "  Firewall modification: disabled",
        "  Provider/API runtime: inactive",
        "  Local model runtime: allowed on localhost for Sub-Engel work",
        "  Background workers: authenticated direct listener only; shared-room polling disabled",
        "  Pairing: local one-time code required",
    ]))


def action_node_controller() -> dict[str, Any]:
    return text_action("node.controller", "\n".join([
        "Main controller: Engel AI / Engel App",
        "Primary controller/runtime: CT246 engel-ai-main on engel-spine-01",
        r"ROG face/source checkout: D:\b.WorkSpace\Engel App",
        "Controller handshake: local one-time pairing code",
        "Remote control: paired Main is trusted; HTTP remains allowlisted and audited",
        "Main shell: main.shell action is available when the local full-control gate is enabled.",
        "Main disk control: disk.control action is available when the local full-control gate is enabled.",
        "Shared-room orders/deployment: trusted Main control lane with proof return",
        "Blocked remotely by default: unaudited raw shell, SSH, disk install/format/partition endpoint, reboot, service install, firewall modification.",
    ]))


def action_net_status() -> dict[str, Any]:
    result = run_fixed(["ipconfig"], timeout=12)
    return {"action": "net.status", **result}


def action_net_diagnose() -> dict[str, Any]:
    ipconfig = run_fixed(["ipconfig", "/all"], timeout=18)
    route = run_fixed(["route", "print"], timeout=18)
    wlan = run_fixed(["netsh", "wlan", "show", "interfaces"], timeout=12)
    return text_action("net.diagnose", "\n".join([
        "[ipconfig /all]",
        ipconfig["stdout"] or ipconfig["stderr"],
        "[route print]",
        route["stdout"] or route["stderr"],
        "[netsh wlan show interfaces]",
        wlan["stdout"] or wlan["stderr"],
    ]))


def action_install_status() -> dict[str, Any]:
    return text_action("install.status", "Windows-preserve mode. Engel OS install-to-disk is not available through this Windows Sub-Engel agent.")


def action_install_preflight() -> dict[str, Any]:
    return text_action("install.preflight", "\n".join([
        "Windows Sub-Engel install preflight:",
        "  Mode: windows_preserve",
        "  Install capability: blocked",
        "  Reason: this agent preserves the existing Windows OS",
        "  Remote disk install: disabled",
        "  Remote partition/format/erase: disabled",
        "  Use Engel OS ISO only on machines intended for Engel OS installation.",
    ]))


def action_install_list_disks() -> dict[str, Any]:
    script = (
        "$ErrorActionPreference='SilentlyContinue';"
        "Get-Disk | Select-Object Number,FriendlyName,SerialNumber,BusType,Size,PartitionStyle,OperationalStatus,IsBoot,IsSystem,IsReadOnly | "
        "ConvertTo-Json -Depth 3 -Compress"
    )
    result = ps(script, timeout=15)
    result["action"] = "install.list_disks"
    if result["return_code"] != 0 and not result["stdout"]:
        result["stdout"] = "Disk listing unavailable without changing anything."
    return result


def dashboard() -> str:
    state = public_state()
    gpu = gpu_hardware_inventory()
    gpu_names = ", ".join(str(item.get("name") or "unknown") for item in gpu.get("gpus", [])) or "none detected"
    adapter = lora_artifact_status(include_hash=False)
    base_model = adapter_base_model(Path(str(adapter.get("artifact_dir") or ""))) if adapter.get("artifact_dir") else ""
    return "\n".join([
        "ENGEL WINDOWS SUB-ENGEL NODE",
        "================================",
        f"Role: {DISPLAY_ROLE}",
        f"Hostname: {socket.gethostname()}",
        f"OS: {platform.platform()}",
        f"IPs: {', '.join(local_ips()) or 'none detected'}",
        f"Remote control: {state.get('remote_control', 'paired_main_trusted_control')}",
        f"Authority model: {state.get('authority_model', 'paired_main_trusted_full_control')}",
        f"Pairing: {state.get('pairing_status', 'not active')}",
        "",
        "Hardware and model runtime:",
        f"  GPU: {gpu_names}",
        f"  GPU vendor: {gpu.get('primary_vendor', 'unknown')}",
        f"  CUDA applicable: {gpu.get('cuda_applicable', False)}",
        f"  Runtime device: {'cuda' if gpu.get('cuda_applicable') else 'cpu'}",
        f"  DirectML candidate: {gpu.get('directml_candidate', False)}",
        f"  Runtime note: {gpu.get('summary', '')}",
        f"  PEFT LoRA adapter: {'present' if adapter.get('present') else 'missing'}",
        f"  PEFT base model: {base_model or 'not detected'}",
        "  Legacy GGUF/CUDA fallback: disabled by default",
        "",
        "Control safety:",
        "Raw shell: disabled",
        "SSH: disabled",
        "Remote disk install/format/partition: disabled",
        "Provider/API runtime: inactive",
        "Local model runtime: allowed on localhost for Sub-Engel work",
        "Background workers: authenticated direct listener only; shared-room polling disabled",
        "",
        "Next commands:",
        "  python engel_windows_sub_node_agent.py status",
        "  python engel_windows_sub_node_agent.py token",
        f"  python engel_windows_sub_node_agent.py serve --lan --approve {APPROVAL_TOKEN}",
    ])


def action_ui_visible_status() -> dict[str, Any]:
    timestamp = utc_stamp()
    gpu = gpu_hardware_inventory()
    gpu_names = ", ".join(str(item.get("name") or "unknown") for item in gpu.get("gpus", [])) or "none detected"
    text = "\n".join([
        "ENGEL DEVICE-SIDE VISIBLE PROOF",
        "================================",
        f"Time UTC: {timestamp}",
        f"Hostname: {socket.gethostname()}",
        f"IPs: {', '.join(local_ips()) or 'none detected'}",
        f"GPU: {gpu_names}",
        f"GPU vendor: {gpu.get('primary_vendor', 'unknown')}",
        f"CUDA applicable: {gpu.get('cuda_applicable', False)}",
        f"Runtime device: {'cuda' if gpu.get('cuda_applicable') else 'cpu'}",
        f"Runtime note: {gpu.get('summary', '')}",
        "Source: pair-gated Engel AI controller command",
        "Action: allowlisted UI/status proof for trusted Main control session",
        "Raw shell: disabled",
        "SSH: disabled",
        "Remote disk install/format/partition: disabled",
        "Provider/API runtime: inactive",
        "Local model runtime: allowed on localhost for Sub-Engel work",
        "Background workers: authenticated direct listener only; shared-room polling disabled",
    ])
    write_public_state(
        last_visible_status_at_utc=timestamp,
        last_visible_status_source="engel_ai_controller",
    )
    append_receipt({"event": "visible_status", "hostname": socket.gethostname()})
    console_notice(text.replace("\n", " | "))
    return text_action("ui.visible_status", text)


def shared_room_drive_roots() -> list[str]:
    # Shared-drive work transport is retired. Keep legacy command parsing inert.
    return []


def discover_shared_room_dir() -> Path | None:
    # CT246 authenticated HTTP is the only active work transport.
    return None


def node_work_dirs() -> dict[str, Path]:
    root = default_node_root()
    if is_os_drive_path(root):
        raise OSError(f"refusing Windows Sub-Engel work on C: {root}")
    paths = {
        "root": root,
        "incoming": root / "workspace" / "jobs" / "incoming",
        "done": root / "workspace" / "jobs" / "done",
        "outbox": root / "workspace" / "meeting_room" / "outbox",
        "receipts": root / "receipts",
    }
    for path in paths.values():
        if path == root:
            path.mkdir(parents=True, exist_ok=True)
        else:
            path.mkdir(parents=True, exist_ok=True)
    return paths


def unique_child(parent: Path, name: str) -> Path:
    candidate = parent / name
    if not candidate.exists():
        return candidate
    suffix = candidate.suffix
    stem = candidate.stem
    stamp = utc_now().strftime("%Y%m%dT%H%M%SZ")
    for index in range(1, 1000):
        other = parent / f"{stem}.{stamp}.{index}{suffix}"
        if not other.exists():
            return other
    return parent / f"{stem}.{stamp}.{secrets.token_hex(4)}{suffix}"


def append_shared_room_bus(room_dir: Path, channel: str, message: str, extra: dict[str, Any] | None = None) -> None:
    bus = room_dir / "engel_shared_room_bus.jsonl"
    record = {
        "timestamp_utc": utc_stamp(),
        "channel": channel,
        "source": socket.gethostname(),
        "role": ROLE,
        "message": message,
    }
    if extra:
        record.update(extra)
    try:
        with bus.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True) + "\n")
    except OSError:
        pass


def work_order_sync_wait_seconds() -> float:
    raw = os.environ.get("ENGEL_SUB_ENGEL_WORK_ORDER_SYNC_WAIT_SECONDS", "30")
    try:
        return max(0.0, min(120.0, float(raw)))
    except ValueError:
        return 30.0


def requested_work_order_from_active_marker(
    room_dir: Path,
    work_orders: Path,
    min_created_at: datetime,
) -> tuple[Path | None, dict[str, Any], str]:
    marker = room_dir / SHARED_ACTIVE_WORK_REQUEST
    deadline = time.time() + work_order_sync_wait_seconds()
    last_payload: dict[str, Any] = {}
    while True:
        request_payload = read_json(marker)
        if request_payload:
            last_payload = request_payload
            created = parse_utc(str(request_payload.get("created_at_utc") or ""))
            if created and created >= min_created_at:
                requested_name = str(request_payload.get("work_order_name") or "").strip()
                requested_id = str(request_payload.get("order_id") or "").strip()
                if not requested_name and requested_id:
                    requested_name = f"{requested_id}.json"
                if not requested_name:
                    return None, request_payload, "fresh active request marker is missing work_order_name/order_id"
                requested_path = work_orders / Path(requested_name).name
                if requested_path.is_file():
                    return requested_path, request_payload, ""
                if time.time() >= deadline:
                    return requested_path, request_payload, "active requested work order did not sync to this Sub-Engel before timeout"
        if time.time() >= deadline:
            if last_payload:
                return None, last_payload, "active request marker did not refresh before timeout"
            return None, {}, ""
        time.sleep(1.0)


def current_node_id_candidates() -> set[str]:
    names = {
        socket.gethostname(),
        os.environ.get("COMPUTERNAME", ""),
        os.environ.get("HOSTNAME", ""),
    }
    return {name.strip().lower() for name in names if str(name or "").strip()}


def work_order_selected_id_candidates(order_payload: dict[str, Any]) -> set[str]:
    selected = order_payload.get("selected_node") if isinstance(order_payload.get("selected_node"), dict) else {}
    # (2026-07-11) target_node is a hostname STRING in legacy orders but a
    # meeting-room DESCRIPTOR DICT (agent/bridge/skill/station labels, no
    # identity) in current ones. Stringifying that dict made a fake "selected
    # identity" that matched no host, so EVERY node skipped EVERY meeting-room
    # order ("selected node is not this Sub-Engel") and nothing returned since
    # 7/8. Only identity-ish fields may nominate a node.
    target_node = order_payload.get("target_node")
    if isinstance(target_node, dict):
        target_node_values = [
            target_node.get("node_id", ""),
            target_node.get("hostname", ""),
            target_node.get("computer_name", ""),
            target_node.get("stable_identity", ""),
            target_node.get("stable_id", ""),
        ]
    else:
        target_node_values = [target_node or ""]
    values = [
        order_payload.get("selected_stable_identity", ""),
        *target_node_values,
        order_payload.get("target_hostname", ""),
        order_payload.get("node_id", ""),
        order_payload.get("hostname", ""),
        selected.get("node_id", ""),
        selected.get("stable_id", ""),
        selected.get("stable_identity", ""),
        selected.get("hostname", ""),
        selected.get("computer_name", ""),
    ]
    return {str(value).strip().lower() for value in values if str(value or "").strip()}


def work_order_targets_this_node(order_payload: dict[str, Any]) -> tuple[bool, str]:
    selected_ids = work_order_selected_id_candidates(order_payload)
    local_ids = current_node_id_candidates()
    if selected_ids:
        if selected_ids.intersection(local_ids):
            return True, "selected node identity matches this Sub-Engel"
        return False, f"selected node is not this Sub-Engel: {sorted(selected_ids)}"
    target = " ".join([
        str(order_payload.get("target", "")),
        str(order_payload.get("target_label", "")),
    ]).lower()
    if "windows_sub_engel" in target or "windows sub-engel" in target:
        return True, "no selected node identity; target is Windows Sub-Engel"
    return False, f"work order target is not Windows Sub-Engel: {target or 'missing target'}"


def returned_file_matches_current_node(path: Path) -> bool:
    payload = read_json(path)
    values = {
        payload.get("hostname", "") if isinstance(payload, dict) else "",
        path.name.split("__", 1)[0] if "__" in path.name else "",
    }
    returned_ids = {str(value).strip().lower() for value in values if str(value or "").strip()}
    return bool(returned_ids.intersection(current_node_id_candidates()))


def returned_files_for_work_order(
    sent_work: Path,
    source: Path,
    order_payload: dict[str, Any],
    current_node_only: bool = False,
) -> list[Path]:
    if not sent_work.is_dir():
        return []
    order_id = str(order_payload.get("id") or source.stem).strip()
    stems = {source.stem}
    if order_id:
        stems.add(order_id)
    matches: list[Path] = []
    for item in sent_work.glob("*.json"):
        if not item.is_file():
            continue
        name = item.name
        if any(f"__{stem}.done" in name or f"__{stem}." in name and ".done" in name for stem in stems):
            if current_node_only and not returned_file_matches_current_node(item):
                continue
            matches.append(item)
            continue
        if order_id and order_id in name and ".done" in name:
            if current_node_only and not returned_file_matches_current_node(item):
                continue
            matches.append(item)
    return sorted(matches, key=lambda path: path.stat().st_mtime, reverse=True)


def process_shared_room_work_order(
    source: Path,
    room_dir: Path,
    sent_work: Path,
    active_request: dict[str, Any] | None = None,
    action: str = "shared_room.process_latest_work_order",
) -> dict[str, Any]:
    active_request = active_request or {}
    try:
        preview_payload = read_json(source)
        targets_this_node, target_reason = work_order_targets_this_node(preview_payload)
        if not targets_this_node:
            return {
                "ok": False,
                "overall_ok": False,
                "event": "windows_sub_engel_work_order_skipped_wrong_node",
                "runtime": "engel-ai-rs",
                "source": "paired Main trusted-control shared-room action",
                "action": action,
                "hostname": socket.gethostname(),
                "completed_at_utc": utc_stamp(),
                "shared_room": str(room_dir),
                "source_work_order": str(source),
                "order_id": preview_payload.get("id", source.stem),
                "target": preview_payload.get("target", ""),
                "target_label": preview_payload.get("target_label", ""),
                "selected_node": preview_payload.get("selected_node", {}),
                "reason": target_reason,
                "auto_return": True,
                "auto_apply": False,
                "requires_review_before_apply": True,
            }
        returned = returned_files_for_work_order(sent_work, source, preview_payload, current_node_only=True)
        if returned:
            return {
                "ok": True,
                "overall_ok": True,
                "event": "windows_sub_engel_work_order_already_returned_by_this_node",
                "runtime": "engel-ai-rs",
                "source": "paired Main trusted-control shared-room action",
                "action": action,
                "hostname": socket.gethostname(),
                "completed_at_utc": utc_stamp(),
                "shared_room": str(room_dir),
                "source_work_order": str(source),
                "order_id": preview_payload.get("id", source.stem),
                "exported_file": str(returned[0]),
                "auto_return": True,
                "auto_apply": False,
                "requires_review_before_apply": True,
            }
        paths = node_work_dirs()
        incoming = unique_child(paths["incoming"], source.name)
        shutil.copy2(source, incoming)
        order_payload = read_json(incoming)
        training_before = training_status_payload()
        training_policy = training_safe_work_order_policy(order_payload)
        operator_status = "done"
        if training_before.get("training_active") and training_policy.get("training_safe"):
            executor = {
                "ok": True,
                "engine": "training-safe-status-snapshot",
                "output": json.dumps({
                    "hostname": socket.gethostname(),
                    "training_active": True,
                    "training_process_ids": training_before.get("training_process_ids", []),
                    "node_root": str(paths["root"]),
                    "state_dir": str(STATE_DIR),
                }, sort_keys=True),
                "llm_attempted": False,
                "status": training_before,
                "trained_lora_adapter": {},
            }
        elif training_before.get("training_active"):
            operator_status = "deferred_training_active"
            executor = {
                "ok": False,
                "engine": "training-guard",
                "output": "Work deferred because Sub-Engel training is active and the task is not an approved read-only status job.",
                "llm_attempted": False,
                "status": training_before,
                "trained_lora_adapter": {},
            }
        else:
            executor = run_local_helper_llm(order_payload)
        training_after = training_status_payload()
        training_processes_unchanged = (
            training_before.get("training_process_ids", [])
            == training_after.get("training_process_ids", [])
        )
        done = unique_child(paths["done"], f"{incoming.stem}.done.json")
        if training_before.get("training_active"):
            memory_update = {
                "ok": True,
                "status": "skipped_training_active",
                "mutation_performed": False,
            }
        else:
            try:
                memory_update = record_persistent_memory_episode(
                    order_payload,
                    executor,
                    {
                        "action": action,
                        "order_id": order_payload.get("id", source.stem),
                        "source_work_order": str(source),
                        "incoming_file": str(incoming),
                        "done_file": str(done),
                    },
                )
            except Exception as exc:
                memory_update = {
                    "ok": False,
                    "error": str(exc),
                    "memory_core": str(memory_core_path()),
                    "memory_episodes": str(memory_episodes_path()),
                }
        result = {
            "event": "windows_sub_engel_work_order_processed_once",
            "runtime": "engel-ai-rs",
            "source": "paired Main trusted-control shared-room action",
            "action": action,
            "hostname": socket.gethostname(),
            "completed_at_utc": utc_stamp(),
            "node_root": str(paths["root"]),
            "node_root_on_os_drive": is_os_drive_path(paths["root"]),
            "state_dir": str(STATE_DIR),
            "state_dir_on_os_drive": is_os_drive_path(STATE_DIR),
            "shared_room": str(room_dir),
            "source_work_order": str(source),
            "incoming_file": str(incoming),
            "done_file": str(done),
            "source_size_bytes": incoming.stat().st_size,
            "operator_status": operator_status,
            "proof_required": bool(order_payload.get("proof_required", True)),
            "order_id": order_payload.get("id", source.stem),
            "target": order_payload.get("target", ""),
            "target_label": order_payload.get("target_label", ""),
            "selected_node": order_payload.get("selected_node", {}),
            "active_request": active_request,
            "order_text": str(order_payload.get("order_text", ""))[:4000],
            "worker_engine": executor.get("engine", ""),
            "worker_output": str(executor.get("output", ""))[:MAX_LLM_OUTPUT_CHARS],
            "local_llm_attempted": bool(executor.get("llm_attempted")),
            "local_llm_status": executor.get("status", {}),
            "trained_lora_adapter": executor.get("trained_lora_adapter", {}),
            "persistent_memory": memory_update,
            "training_guard_observed": True,
            "training_guard_before": training_before,
            "training_guard_after": training_after,
            "training_processes_unchanged": training_processes_unchanged,
            "training_safe_policy": training_policy,
            "non_invasive": bool(training_policy.get("training_safe")) if training_before.get("training_active") else False,
            "model_output_trusted": False,
            "executor": executor,
            "auto_return": True,
            "auto_apply": False,
            "requires_review_before_apply": True,
        }
        done.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        sent_work.mkdir(parents=True, exist_ok=True)
        exported = unique_child(sent_work, f"{socket.gethostname()}__{done.name}")
        shutil.copy2(done, exported)
        receipt = {
            **result,
            "event": "windows_sub_engel_shared_room_export",
            "exported_file": str(exported),
            "overall_ok": (
                incoming.exists()
                and done.exists()
                and exported.exists()
                and bool(executor.get("ok", True))
                and training_processes_unchanged
            ),
        }
        receipt_path = unique_child(paths["receipts"], f"shared-room-process-{utc_now().strftime('%Y%m%dT%H%M%SZ')}.json")
        receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        append_shared_room_bus(
            room_dir,
            "RESULT",
            f"Windows Sub-Engel returned {operator_status} proof for {source.name} as {exported.name}.",
            {"work_order": source.name, "exported_file": str(exported), "receipt_path": str(receipt_path)},
        )
        append_receipt({
            "event": "shared_room_work_order_processed",
            "work_order": str(source),
            "exported_file": str(exported),
            "receipt_path": str(receipt_path),
        })
        console_notice(f"Shared-room work order processed: {source.name} -> {exported.name}")
        return receipt
    except OSError as exc:
        return {
            "ok": False,
            "overall_ok": False,
            "error": str(exc),
            "shared_room": str(room_dir),
            "source_work_order": str(source),
        }


def action_shared_room_status() -> dict[str, Any]:
    roots = shared_room_drive_roots()
    discovered_room = discover_shared_room_dir()
    room_dir = discovered_room or Path("")
    room_found = discovered_room is not None
    live_doc = room_dir / "Engel_Shared_Node_Room_LIVE.md" if room_found else Path("")
    bus = room_dir / "engel_shared_room_bus.jsonl" if room_found else Path("")
    message_count = 0
    latest_message = ""
    if bus.is_file():
        try:
            lines = [line for line in bus.read_text(encoding="utf-8").splitlines() if line.strip()]
            message_count = len(lines)
            latest_message = lines[-1] if lines else ""
        except OSError:
            latest_message = ""
    return json_action("shared_room.status", {
        "hostname": socket.gethostname(),
        "drive_roots": roots,
        "room_dir": str(room_dir),
        "room_exists": bool(room_found and room_dir.is_dir()),
        "live_doc": str(live_doc),
        "live_doc_exists": live_doc.is_file(),
        "bus": str(bus),
        "bus_exists": bus.is_file(),
        "message_count": message_count,
        "latest_message": latest_message,
        "purpose": "Google Drive synced fallback room for Engel Main and Sub-Engel node communication",
    })


def action_shared_room_process_latest_work_order() -> dict[str, Any]:
    action = "shared_room.process_latest_work_order"
    room_dir = discover_shared_room_dir()
    if not room_dir:
        return json_action_result(action, {
            "ok": False,
            "error": "Google Drive ENGEL_SHARED_NODE_ROOM was not found on this Sub-Engel node",
            "drive_roots": shared_room_drive_roots(),
        }, return_code=2)

    work_orders = room_dir / SHARED_WORK_ORDERS_DIR
    sent_work = room_dir / SHARED_SENT_WORK_DIR
    if not work_orders.is_dir():
        return json_action_result(action, {
            "ok": False,
            "error": f"missing shared work order folder: {work_orders}",
            "shared_room": str(room_dir),
        }, return_code=3)

    min_request_created_at = utc_now() - timedelta(seconds=15)
    requested_source, active_request, active_request_error = requested_work_order_from_active_marker(
        room_dir,
        work_orders,
        min_request_created_at,
    )
    if active_request_error:
        return json_action_result(action, {
            "ok": False,
            "error": active_request_error,
            "active_request": active_request,
            "work_orders": str(work_orders),
            "minimum_created_at_utc": utc_stamp(min_request_created_at),
        }, return_code=8)
    if requested_source is not None:
        if not requested_source.is_file():
            return json_action_result(action, {
                "ok": False,
                "error": "active requested work order did not sync to this Sub-Engel before timeout",
                "active_request": active_request,
                "requested_work_order": str(requested_source),
                "work_orders": str(work_orders),
            }, return_code=8)
        source = requested_source.resolve()
    else:
        try:
            orders = sorted(
                [item for item in work_orders.glob("*.json") if item.is_file()],
                key=lambda item: item.stat().st_mtime,
                reverse=True,
            )
        except OSError as exc:
            return json_action_result(action, {
                "ok": False,
                "error": str(exc),
                "shared_room": str(room_dir),
            }, return_code=4)

        if not orders:
            return json_action_result(action, {
                "ok": False,
                "error": "no shared work orders are available",
                "work_orders": str(work_orders),
            }, return_code=5)

        source = orders[0].resolve()
    receipt = process_shared_room_work_order(source, room_dir, sent_work, active_request, action)
    return json_action_result(action, receipt, return_code=0 if receipt.get("overall_ok") else 7)


def action_shared_room_process_pending_work_orders(limit: int | None = None) -> dict[str, Any]:
    action = "shared_room.process_pending_work_orders"
    room_dir = discover_shared_room_dir()
    if not room_dir:
        return json_action_result(action, {
            "ok": False,
            "error": "Google Drive ENGEL_SHARED_NODE_ROOM was not found on this Sub-Engel node",
            "drive_roots": shared_room_drive_roots(),
        }, return_code=2)

    work_orders = room_dir / SHARED_WORK_ORDERS_DIR
    sent_work = room_dir / SHARED_SENT_WORK_DIR
    if not work_orders.is_dir():
        return json_action_result(action, {
            "ok": False,
            "error": f"missing shared work order folder: {work_orders}",
            "shared_room": str(room_dir),
        }, return_code=3)

    try:
        orders = sorted(
            [item for item in work_orders.glob("*.json") if item.is_file()],
            key=lambda item: item.stat().st_mtime,
        )
    except OSError as exc:
        return json_action_result(action, {
            "ok": False,
            "error": str(exc),
            "shared_room": str(room_dir),
        }, return_code=4)

    max_items = limit if limit is not None else int(os.environ.get("ENGEL_SUB_ENGEL_AUTO_RETURN_LIMIT", "10"))
    max_items = max(1, min(100, int(max_items)))
    processed: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for source in orders:
        payload = read_json(source)
        returned = returned_files_for_work_order(sent_work, source, payload, current_node_only=True)
        if returned:
            skipped.append({
                "work_order": str(source),
                "reason": "already returned",
                "returned_file": str(returned[0]),
            })
            continue
        targets_this_node, target_reason = work_order_targets_this_node(payload)
        if not targets_this_node:
            skipped.append({
                "work_order": str(source),
                "reason": target_reason,
            })
            continue
        receipt = process_shared_room_work_order(source.resolve(), room_dir, sent_work, {}, action)
        processed.append({
            "work_order": str(source),
            "overall_ok": bool(receipt.get("overall_ok")),
            "exported_file": receipt.get("exported_file", ""),
            "worker_engine": receipt.get("worker_engine", ""),
        })
        if len(processed) >= max_items:
            break

    payload = {
        "ok": True,
        "event": "windows_sub_engel_pending_work_orders_processed",
        "auto_return": True,
        "auto_apply": False,
        "requires_review_before_apply": True,
        "hostname": socket.gethostname(),
        "completed_at_utc": utc_stamp(),
        "shared_room": str(room_dir),
        "work_orders": str(work_orders),
        "sent_work": str(sent_work),
        "limit": max_items,
        "processed_count": len(processed),
        "skipped_count": len(skipped),
        "processed": processed,
        "skipped": skipped[:50],
    }
    append_receipt({
        "event": "shared_room_pending_work_orders_processed",
        "processed_count": len(processed),
        "skipped_count": len(skipped),
    })
    return json_action_result(action, payload, return_code=0)


def auto_process_work_orders_loop(interval_seconds: float, limit: int, cycles: int) -> int:
    interval_seconds = max(2.0, min(3600.0, interval_seconds))
    limit = max(1, min(100, limit))
    write_public_state(
        auto_return_state="running",
        auto_return_started_at_utc=utc_stamp(),
        auto_return_interval_seconds=interval_seconds,
        auto_return_limit=limit,
    )
    console_notice(f"Sub-Engel auto-return loop started interval={interval_seconds}s limit={limit} cycles={cycles or 'forever'}")
    count = 0
    try:
        while True:
            count += 1
            result = action_shared_room_process_pending_work_orders(limit=limit)
            payload = read_json_from_stdout(result.get("stdout", ""))
            console_notice(
                "Auto-return scan "
                f"{count}: return_code={result.get('return_code')} "
                f"processed={payload.get('processed_count', 0)} "
                f"skipped={payload.get('skipped_count', 0)}"
            )
            write_public_state(
                auto_return_state="running",
                auto_return_last_scan_at_utc=utc_stamp(),
                auto_return_last_return_code=result.get("return_code"),
                auto_return_last_processed=payload.get("processed_count", 0),
                auto_return_last_skipped=payload.get("skipped_count", 0),
            )
            if cycles and count >= cycles:
                break
            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        console_notice("Sub-Engel auto-return loop stopped by operator.")
    finally:
        write_public_state(auto_return_state="stopped", auto_return_stopped_at_utc=utc_stamp())
    return 0


def read_json_from_stdout(value: Any) -> dict[str, Any]:
    try:
        data = json.loads(str(value or "{}"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}



def controller_url_candidates() -> list[str]:
    values: list[str] = []
    for key in ("ENGEL_CONTROLLER_URL", "ENGEL_MAIN_CONTROLLER_URL", "ENGEL_WINDOWS_SUB_NODE_CONTROLLER_URL"):
        raw = os.environ.get(key, "").strip()
        if raw:
            values.append(raw)
    profile = read_json(default_node_root() / "config" / "node-profile.json")
    for key in ("controller_url", "main_controller_url"):
        raw = str(profile.get(key, "")).strip()
        if raw:
            values.append(raw)
    values.append(DEFAULT_CONTROLLER_URL)

    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = value.rstrip("/")
        if not clean:
            continue
        if "://" not in clean:
            clean = "http://" + clean
        if clean.lower() not in seen:
            seen.add(clean.lower())
            out.append(clean)
    return out


def post_node_ready_to_controller() -> dict[str, Any]:
    """Post node readiness without rotating an already-live Main session."""
    pairing: dict[str, Any] = {}
    paired_session = read_json(session_path())
    if not current_session_record_is_live():
        try:
            pairing = create_pairing_session()
        except OSError as exc:
            return {"ok": False, "error": str(exc), "stage": "create_pairing_session"}

    node_root = default_node_root()
    temp_dir = node_root / "temp"
    profile = read_json(node_root / "config" / "node-profile.json")
    supervisor = read_json(node_root / "config" / "supervisor-state.json")
    payload = {
        "ok": True,
        "source": "windows_sub_engel_agent_serve_start",
        "computer_name": socket.gethostname(),
        "user": os.environ.get("USERNAME") or os.environ.get("USER") or "",
        "node_ip": (local_ips() or [""])[0],
        "node_ips": local_ips(),
        "agent_path": str(Path(__file__).resolve()),
        "node_root": str(node_root),
        "node_root_on_os_drive": is_os_drive_path(node_root),
        "state_dir": str(STATE_DIR),
        "state_dir_on_os_drive": is_os_drive_path(STATE_DIR),
        "temp_dir": str(temp_dir),
        "temp_dir_on_os_drive": is_os_drive_path(temp_dir),
        "file_structure_root": str(profile.get("file_structure_root") or node_root),
        "file_structure_version": str(profile.get("file_structure_version") or ""),
        "python": {
            "exe": sys.executable,
            "args": [],
            "source": "node-agent-serve-start",
        },
        "supervisor": supervisor if supervisor else {"started": False},
        "operator_confirmed": {
            "source": "agent serve startup callback",
            "vscode_open": bool(profile.get("operator_confirmed", {}).get("vscode_open", False)) if isinstance(profile.get("operator_confirmed"), dict) else False,
            "codex_signed_in": bool(profile.get("operator_confirmed", {}).get("codex_signed_in", False)) if isinstance(profile.get("operator_confirmed"), dict) else False,
        },
        "pairing_required": bool(pairing),
        "session_token_hint": str(paired_session.get("session_token_hint") or "")
        if not pairing
        else "",
        "session_expires_at_utc": str(paired_session.get("expires_at_utc") or "")
        if not pairing
        else "",
        "timestamp": utc_stamp(),
    }
    if pairing:
        payload["pairing_code"] = pairing["pairing_code"]

    attempts: list[dict[str, Any]] = []
    body = json.dumps(payload).encode("utf-8")
    for controller_url in controller_url_candidates():
        target = controller_url.rstrip("/") + "/node-ready"
        req = request.Request(
            target,
            data=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=5) as resp:
                response_text = resp.read().decode("utf-8", errors="replace")
            append_receipt({
                "event": "node_ready_posted",
                "controller_url": controller_url,
                "pairing_code_hint": pairing.get("pairing_code_hint", ""),
                "pairing_required": bool(pairing),
            })
            console_notice(
                f"Posted {'pairing' if pairing else 'session-preserving'} "
                f"node-ready callback to {target}."
            )
            return {
                "ok": True,
                "controller_url": controller_url,
                "http_status": getattr(resp, "status", 200),
                "response": response_text[:1000],
            }
        except error.HTTPError as exc:
            attempts.append({"controller_url": controller_url, "http_status": exc.code, "error": str(exc)})
        except Exception as exc:
            attempts.append({"controller_url": controller_url, "error": str(exc)})
    append_receipt({
        "event": "node_ready_post_failed",
        "attempts": attempts,
        "pairing_code_hint": pairing.get("pairing_code_hint", ""),
        "pairing_required": bool(pairing),
    })
    console_notice("Fresh node-ready callback could not reach Main controller.")
    return {"ok": False, "attempts": attempts}


ACTION_HANDLERS = {
    "node.status": action_node_status,
    "node.hardware": action_node_hardware,
    "node.safety": action_node_safety,
    "node.controller": action_node_controller,
    "net.status": action_net_status,
    "net.diagnose": action_net_diagnose,
    "install.status": action_install_status,
    "install.preflight": action_install_preflight,
    "install.list_disks": action_install_list_disks,
    "ui.dashboard": lambda: text_action("ui.dashboard", dashboard()),
    "ui.visible_status": action_ui_visible_status,
    "local_llm.status": action_local_llm_status,
    "session.renew": action_session_renew,
    "training.status": action_training_status,
    "memory.status": action_memory_status,
    "main.control_status": action_main_control_status,
    "remote.status": lambda: text_action("remote.status", render_status()),
}


PARAM_ACTION_HANDLERS = {
    "main.shell": action_main_shell,
    "disk.control": action_disk_control,
    DIRECT_WORK_ACTION: action_direct_work_execute,
    "training_safe.execute": action_training_safe_execute,
}


def run_allowed_action(action: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    if action in PARAM_ACTION_HANDLERS:
        return PARAM_ACTION_HANDLERS[action](body or {})
    handler = ACTION_HANDLERS[action]
    return handler()


class PairingRequestHandler(BaseHTTPRequestHandler):
    server_version = "EngelWindowsSubNode/1"

    def log_message(self, fmt: str, *args: Any) -> None:
        append_receipt({"event": "http_log", "client": self.client_address[0], "message": fmt % args})

    def send_json(self, status: int, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def read_body(self) -> dict[str, Any] | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_json(400, {"ok": False, "error": "invalid content length"})
            return None
        if length > MAX_REQUEST_BYTES:
            self.send_json(413, {"ok": False, "error": "request too large"})
            return None
        try:
            raw = self.rfile.read(length) if length else b"{}"
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.send_json(400, {"ok": False, "error": "invalid json"})
            return None
        if not isinstance(data, dict):
            self.send_json(400, {"ok": False, "error": "json body must be an object"})
            return None
        return data

    def require_auth(self) -> bool:
        header = self.headers.get("Authorization", "")
        prefix = "Bearer "
        if not header.startswith(prefix):
            self.send_json(401, {"ok": False, "error": "missing bearer token"})
            return False
        ok, reason = current_session_valid(header[len(prefix) :].strip())
        if not ok:
            self.send_json(401, {"ok": False, "error": reason})
            return False
        return True

    def do_GET(self) -> None:
        if self.path == "/health":
            node_root = default_node_root()
            session = read_json(session_path())
            paired = bool(session and not is_expired(str(session.get("expires_at_utc", ""))))
            training_guard = training_status_payload()
            self.send_json(200, {
                "ok": True,
                "service": "engel-windows-sub-node",
                "role": ROLE,
                "node_kind": "windows_sub_engel_node",
                "node_os": "windows",
                "hostname": socket.gethostname(),
                "node_root": str(node_root),
                "state_dir": str(STATE_DIR),
                "node_root_on_os_drive": is_os_drive_path(node_root),
                "state_dir_on_os_drive": is_os_drive_path(STATE_DIR),
                "local_ips": local_ips(),
                "pairing_required": not paired,
                "training_guard": {
                    "schema": training_guard.get("schema"),
                    "observed_at_utc": training_guard.get("observed_at_utc"),
                    "training_active": bool(training_guard.get("training_active")),
                    "training_process_count": len(training_guard.get("training_process_ids") or []),
                    "mutation_performed": False,
                },
                "allowed_actions": sorted(ALLOWED_ACTIONS),
                "blocked_actions": BLOCKED_ACTIONS,
            })
            return
        if self.path == "/actions":
            if not self.require_auth():
                return
            self.send_json(200, {"ok": True, "allowed_actions": sorted(ALLOWED_ACTIONS), "blocked_actions": BLOCKED_ACTIONS})
            return
        if self.path == "/node/status":
            if not self.require_auth():
                return
            self.send_json(200, {"ok": True, "result": action_node_status()})
            return
        if self.path == "/node/hardware":
            if not self.require_auth():
                return
            self.send_json(200, {"ok": True, "result": action_node_hardware()})
            return
        self.send_json(404, {"ok": False, "error": "unknown endpoint"})

    def do_POST(self) -> None:
        if self.path == "/pair":
            body = self.read_body()
            if body is None:
                return
            pairing = read_json(pairing_path())
            code = str(body.get("pairing_code", "")).strip()
            controller_name = str(body.get("controller_name", "engel-ai-controller")).strip()
            proposed_token = str(body.get("proposed_session_token") or "").strip()
            if not pairing:
                self.send_json(409, {"ok": False, "error": "no active pairing code; run python engel_windows_sub_node_agent.py token on the node"})
                return
            if is_expired(str(pairing.get("expires_at_utc", ""))):
                self.send_json(409, {"ok": False, "error": "pairing code expired; generate a new one"})
                return
            if not secrets.compare_digest(sha256_text(code), str(pairing.get("pairing_code_hash", ""))):
                append_receipt({"event": "pair_rejected", "client": self.client_address[0], "reason": "invalid code"})
                self.send_json(403, {"ok": False, "error": "invalid pairing code"})
                return
            if proposed_token and not valid_proposed_session_token(proposed_token):
                self.send_json(400, {"ok": False, "error": "proposed session token has an invalid shape"})
                return
            if bool(pairing.get("used")):
                current = read_json(session_path())
                replay_ok = bool(
                    proposed_token
                    and current
                    and not is_expired(str(current.get("expires_at_utc") or ""))
                    and secrets.compare_digest(
                        sha256_text(proposed_token),
                        str(current.get("session_token_hash") or ""),
                    )
                    and str(current.get("controller_name") or "") == (
                        controller_name[:80] if controller_name else "engel-ai-controller"
                    )
                )
                if not replay_ok:
                    self.send_json(409, {"ok": False, "error": "pairing code already used; generate a new one"})
                    return
                self.send_json(200, {
                    "ok": True,
                    "idempotent_replay": True,
                    "role": ROLE,
                    "node_kind": "windows_sub_engel_node",
                    "node_os": "windows",
                    "hostname": socket.gethostname(),
                    "local_ips": local_ips(),
                    "session_token": proposed_token,
                    "expires_at_utc": current.get("expires_at_utc", ""),
                    "allowed_actions": sorted(ALLOWED_ACTIONS),
                    "blocked_actions": BLOCKED_ACTIONS,
                })
                return
            pairing["used"] = True
            pairing["used_at_utc"] = utc_stamp()
            try:
                session = create_session(controller_name, proposed_token)
            except ValueError as exc:
                self.send_json(400, {"ok": False, "error": str(exc)})
                return
            write_json(pairing_path(), pairing)
            append_receipt({"event": "paired", "client": self.client_address[0], "controller_name": session["controller_name"]})
            console_notice(f"Paired with {session['controller_name']} from {self.client_address[0]}.")
            self.send_json(200, {
                "ok": True,
                "role": ROLE,
                "node_kind": "windows_sub_engel_node",
                "node_os": "windows",
                "hostname": socket.gethostname(),
                "local_ips": local_ips(),
                "session_token": session["session_token"],
                "expires_at_utc": session["expires_at_utc"],
                "allowed_actions": sorted(ALLOWED_ACTIONS),
                "blocked_actions": BLOCKED_ACTIONS,
            })
            return
        if self.path == "/node/command":
            if not self.require_auth():
                return
            body = self.read_body()
            if body is None:
                return
            action = str(body.get("action", "")).strip()
            if action not in ALLOWED_ACTIONS:
                append_receipt({"event": "command_blocked", "client": self.client_address[0], "action": action})
                self.send_json(403, {
                    "ok": False,
                    "error": "action is not in the Windows Sub-Engel allowlist",
                    "action": action,
                    "allowed_actions": sorted(ALLOWED_ACTIONS),
                    "blocked_actions": BLOCKED_ACTIONS,
                })
                return
            console_notice(f"Command received from {self.client_address[0]}: {action}")
            result = run_allowed_action(action, body)
            append_receipt({
                "event": "command",
                "client": self.client_address[0],
                "action": action,
                "return_code": result.get("return_code"),
            })
            console_notice(f"Command completed: {action} return_code={result.get('return_code')}")
            self.send_json(200, {"ok": result.get("return_code") == 0, "result": result})
            return
        self.send_json(404, {"ok": False, "error": "unknown endpoint"})


def render_status() -> str:
    state = public_state()
    pairing = read_json(pairing_path())
    session = read_json(session_path())
    lines = [
        "Engel Windows Sub-Engel Node",
        f"Node root: {default_node_root()}",
        f"State directory: {STATE_DIR}",
        f"Node root on OS drive: {is_os_drive_path(default_node_root())}",
        f"State directory on OS drive: {is_os_drive_path(STATE_DIR)}",
        "Remote control: paired Main trusted-control node",
        f"Authority model: {state.get('authority_model', 'paired_main_trusted_full_control')}",
        f"Server state: {state.get('server_state', 'not_running')}",
        f"LAN bind approval required: {APPROVAL_TOKEN}",
        f"Paired Main shell: {'enabled' if main_shell_enabled() else 'disabled'}",
        f"Paired Main disk.control: {'enabled' if main_disk_enabled() else 'disabled'}",
        f"Destructive disk.control: {'enabled with confirmation token' if destructive_disk_allowed() else 'disabled'}",
        "Raw unauthenticated shell: disabled",
        "SSH: disabled",
        "Remote disk install/format/partition endpoint: disabled",
        "Provider/API runtime: inactive",
        "Local model runtime: allowed on localhost for Sub-Engel work",
        "Background workers: authenticated direct listener only; shared-room polling disabled",
    ]
    if session and not is_expired(str(session.get("expires_at_utc", ""))):
        lines.append(f"Pairing: paired to {session.get('controller_name', 'unknown')} until {session.get('expires_at_utc')}")
    elif pairing and not is_expired(str(pairing.get("expires_at_utc", ""))) and not pairing.get("used"):
        lines.append(f"Pairing: waiting with code {pairing.get('pairing_code_hint')} until {pairing.get('expires_at_utc')}")
    else:
        lines.append("Pairing: not active")
    return "\n".join(lines)


def print_token() -> int:
    try:
        session = create_pairing_session()
    except OSError as exc:
        print(f"Unable to write pairing state: {exc}", file=sys.stderr)
        return 1
    print("Engel Windows Sub-Engel Pairing")
    print(f"Pairing code: {session['pairing_code']}")
    print(f"Expires UTC: {session['expires_at_utc']}")
    print("Pairing code is one-time and short-lived.")
    print("")
    print("Start foreground LAN server on this Windows node:")
    print(f"  python engel_windows_sub_node_agent.py serve --lan --approve {APPROVAL_TOKEN}")
    print("")
    print("Pair from Engel App/controller:")
    print("  python engel_sub_node_remote_control.py pair --url http://WINDOWS-NODE-IP:8776 --pairing-code CODE")
    return 0


def forget_pairing() -> int:
    removed = 0
    for path in [pairing_path(), session_path()]:
        try:
            path.unlink()
            removed += 1
        except FileNotFoundError:
            pass
        except OSError as exc:
            print(f"Unable to remove {path}: {exc}", file=sys.stderr)
            return 1
    write_public_state(pairing_status="unpaired", controller_name="")
    append_receipt({"event": "forget_pairing", "removed_count": removed})
    print("Windows Sub-Engel pairing/session cleared.")
    return 0


def serve(host: str, port: int) -> int:
    ensure_state_dir()
    write_public_state(
        remote_control="running_pairing_required",
        server_state="running",
        server_host=host,
        server_port=port,
        server_pid=os.getpid(),
        started_at_utc=utc_stamp(),
    )
    # Local model work can run for several minutes. Keep authenticated status,
    # shell, disk, and session-renewal actions responsive while one worker is
    # generating by serving each request on its own daemon thread.
    server = ThreadingHTTPServer((host, port), PairingRequestHandler)
    ready_post = post_node_ready_to_controller()
    write_public_state(last_node_ready_post=ready_post, last_node_ready_post_at_utc=utc_stamp())

    def _stop(_signum: int, _frame: Any) -> None:
        raise KeyboardInterrupt

    try:
        signal.signal(signal.SIGTERM, _stop)
    except (AttributeError, ValueError):
        pass
    print("Engel Windows Sub-Engel server")
    print(f"Listening on: {host}:{port}")
    print("Pairing required. Paired Main is trusted; HTTP actions remain allowlisted and audited.")
    print("Unaudited raw shell, SSH, remote disk install, provider/API runtime, and destructive workers are disabled.")
    print(f"Main callback posted: {bool(ready_post.get('ok'))}")
    print("Visible proof: paired controller commands print in this foreground window.")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Engel Windows Sub-Engel server.")
    finally:
        server.server_close()
        write_public_state(server_state="stopped", stopped_at_utc=utc_stamp())
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Pair-gated Windows Sub-Engel node agent")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("status", help="show local Windows Sub-Engel status")
    sub.add_parser("token", help="generate a short-lived local pairing code")
    sub.add_parser("dashboard", help="print a local text dashboard")
    sub.add_parser("local-llm-status", help="print packaged local LLM runtime status as JSON")
    sub.add_parser("training-status", help="print read-only training guard status as JSON")
    sub.add_parser("shared-room-status", help="print shared-room status as JSON")
    sub.add_parser("process-latest-work-order", help="process the latest shared-room work order once")
    pending_parser = sub.add_parser("process-pending-work-orders", help="process pending shared-room work orders for this Sub-Engel")
    pending_parser.add_argument("--limit", type=int, default=10, help="maximum pending work orders to return in one scan")
    auto_parser = sub.add_parser("auto-process-work-orders", help="continuously return pending shared-room work orders")
    auto_parser.add_argument("--interval", type=float, default=10.0, help="seconds between shared-room scans")
    auto_parser.add_argument("--limit", type=int, default=10, help="maximum work orders to return per scan")
    auto_parser.add_argument("--cycles", type=int, default=0, help="scan count; 0 means run until stopped")
    sub.add_parser("forget", help="clear pairing and session state")

    serve_parser = sub.add_parser("serve", help="start the foreground HTTP control endpoint")
    serve_parser.add_argument("--host", default=DEFAULT_HOST, help="bind address; default is localhost")
    serve_parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="bind port")
    serve_parser.add_argument("--lan", action="store_true", help="bind to 0.0.0.0 for LAN controller access")
    serve_parser.add_argument("--approve", default="", help="required token for LAN bind")

    args = parser.parse_args(argv)
    command = args.command or "status"
    if command == "status":
        print(render_status())
        return 0
    if command == "token":
        return print_token()
    if command == "dashboard":
        print(dashboard())
        return 0
    if command == "local-llm-status":
        print(json.dumps(local_llm_status_payload(include_hash=False), indent=2, sort_keys=True))
        return 0
    if command == "training-status":
        print(json.dumps(training_status_payload(), indent=2, sort_keys=True))
        return 0
    if command == "shared-room-status":
        result = action_shared_room_status()
        print(result.get("stdout", ""))
        return int(result.get("return_code", 1))
    if command == "process-latest-work-order":
        result = action_shared_room_process_latest_work_order()
        print(result.get("stdout", ""))
        if result.get("stderr"):
            print(result.get("stderr"), file=sys.stderr)
        return int(result.get("return_code", 1))
    if command == "process-pending-work-orders":
        result = action_shared_room_process_pending_work_orders(limit=args.limit)
        print(result.get("stdout", ""))
        if result.get("stderr"):
            print(result.get("stderr"), file=sys.stderr)
        return int(result.get("return_code", 1))
    if command == "auto-process-work-orders":
        return auto_process_work_orders_loop(
            interval_seconds=float(args.interval),
            limit=int(args.limit),
            cycles=int(args.cycles),
        )
    if command == "forget":
        return forget_pairing()
    if command == "serve":
        host = "0.0.0.0" if args.lan else args.host
        if host_requires_lan_approval(host) and args.approve != APPROVAL_TOKEN:
            print("LAN Windows Sub-Engel bind requires explicit approval:", file=sys.stderr)
            print(f"  --approve {APPROVAL_TOKEN}", file=sys.stderr)
            return 2
        return serve(host, args.port)
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
