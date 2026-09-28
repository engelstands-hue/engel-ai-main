#!/usr/bin/env python3
"""Drive the correct Flutter Engel AI Main chat like a visible user.

This runner targets the real Engel AI Main window opened from the desktop
shortcut/build release. It uses mouse and keyboard input against the visible
Flutter window, then verifies that the Flutter chat called the local LLM plus
Agent Meeting Room wrapper.
"""
from __future__ import annotations

import argparse
import base64
import ctypes
import builtins
from ctypes import wintypes
import datetime
import hashlib
import inspect
import json
import math
import os
import re
from pathlib import Path
import subprocess
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
os.chdir(ROOT)

from engel_ui_prompt_training_support import (  # noqa: E402
    DEFAULT_TRAININGS_PER_HOUR,
    apply_training_level_to_prompt,
    build_agent_proposals,
    build_device_selection,
    ensure_dirs,
    fuzzy_prompt_match,
    iso_now,
    prompt_bank,
    redact,
    select_balanced_training_prompts,
    stamp,
    training_level_profile,
    validate_training_hours,
    validate_training_level,
    validate_training_targets,
    validate_trainings_per_hour,
    write_plan,
    write_reports,
)
from engel_main_local_model_worker import (  # noqa: E402
    _operator_request_text,
    _requested_app_build,
)
from engel_prompt_novelty import (  # noqa: E402
    DEFAULT_PROMPT_RUN_CLAIM,
    DEFAULT_RESERVATIONS_DIR as PROMPT_USE_RESERVATIONS_DIR,
    PREFLIGHT_SCHEMA as PROMPT_NOVELTY_PREFLIGHT_SCHEMA,
    PromptRunClaim,
    PromptRunClaimBlocked,
    acquire_prompt_run_claim,
    canonical_base_prompt_sha256,
    evaluate_scheduled_prompt_novelty,
    publish_prompt_use_reservation,
    require_scheduled_prompt_novelty,
)


APP_EXE = ROOT / "engel_flutter_main" / "build" / "windows" / "x64" / "runner" / "Release" / "EngelAIMain.exe"
APP_CWD = APP_EXE.parent
ORDER_DIR = ROOT / "runtime" / "meeting_room" / "main_ui_orders"
CHAT_RECEIPT_DIR = ROOT / "reports" / "engel_standalone_chat_llm" / "chat_receipts"
# Engel types training prompts into its OWN visible Chat composer from these
# files. Delivering by mouse coordinates + injected keystrokes broke whenever the
# desktop was in use: the text went to whatever window held focus and the run sat
# out its full per-prompt timeout with nothing to show. See _deliver_prompt.
UI_CHAT_INBOX_REQUEST_DIR = ROOT / "runtime" / "ui_chat_inbox" / "requests"
UI_CHAT_INBOX_RESULT_DIR = ROOT / "runtime" / "ui_chat_inbox" / "results"
UI_CHAT_INBOX_ACCEPT_TIMEOUT = float(
    os.environ.get("ENGEL_UI_CHAT_INBOX_ACCEPT_TIMEOUT", "90") or "90"
)
# The app stamps `completed` on its own result file the moment a chat turn ends.
# A turn that finishes without leaving a receipt (an action lane answered it, a
# lane replied outside the chat contract) used to sit here for the entire
# --per-prompt-timeout anyway: on 2026-08-03 one burned 781s of a 760s budget.
# Wait a bounded time AFTER that signal for a receipt that may still be landing,
# then stop. Grace, not zero: the CT receipt legitimately trails the UI turn.
UI_CHAT_INBOX_FINISHED_GRACE_SECONDS = float(
    os.environ.get("ENGEL_UI_CHAT_INBOX_FINISHED_GRACE_SECONDS", "60") or "60"
)
CONICAL_REPORT_DIR = ROOT / "reports" / "conical_jobs"
REPORT_DIR = ROOT / "reports" / "codex_bridge"
# Training packs (2026-08-01). Until now a prompt-training session graded itself and
# stopped there: the SFT dataset builder admits only external "real provider" rows, so
# every local-lane turn Engel produced about itself was thrown away. A pack is the
# hand-off record that closes that loop -- one row per turn WITH the rejected turns kept,
# because the rejects are the negative class the admit classifier has to see.
PACKS_DIR = ROOT / "memory" / "training" / "packs"
CANONICAL_TEMPLATES_DIR = ROOT / "memory" / "training" / "engel_main" / "templates"
CURRICULA_INDEX_PATH = CANONICAL_TEMPLATES_DIR / "curricula_index.json"
CURRICULUM_BINDING_SCHEMA = "engel_training_curriculum_binding_v1"
CANONICAL_CURRICULA = (
    ("capabilities", "Engel Capabilities", "engineering"),
    ("math_school", "Math School", "math"),
    ("self_build", "Self-Build", "engineering"),
    ("construction", "Construction Coordination", "aec"),
    ("chat_communication", "Chat Communication", "communication"),
)


def validate_template_cycle(value: Any) -> int:
    try:
        cycle = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("template cycle must be a whole number") from exc
    if not 1 <= cycle <= 8:
        raise ValueError("template cycle must be from 1 through 8")
    return cycle
CT_PACK_DIR = "/opt/engel/memory/training/packs"
PACK_ROW_SCHEMA = "engel_prompt_training_pack_row_v1"
PACK_RECEIPT_SCHEMA = "engel_prompt_training_pack_v1"
PACK_STAMPED_RECEIPT_SCHEMA = "engel_prompt_training_pack_receipt_v2"
PACK_SESSION_EVIDENCE_SCHEMA = "engel_prompt_training_session_evidence_v1"
PACK_WRITER_IDENTITY_SCHEMA = "engel_prompt_training_pack_writer_identity_v1"
PACK_LATEST_NAME = "ENGEL_PROMPT_TRAINING_PACK_LATEST.json"
PACK_RECEIPT_SUFFIX = ".receipt.json"
PACK_SESSION_PREFIX = "ENGEL_PROMPT_TRAINING_SESSION_"
SAFE_PROMPT_TRAINING_CHAT_PROVIDERS = {"local", "ct_sparse_moe_specialist"}
SESSION_RECEIPT_PATH = ROOT / "memory" / "training" / "ENGEL_UI_PROMPT_TRAINING_SESSION.json"
# A reply this short carries no teachable turn even when every flag is green; the floor is
# part of the admit rule so a one-line "ok." can never become an SFT target.
PACK_MIN_REPLY_CHARS = 80
ASSIGNMENT_ROOT = ROOT / "remote_workers" / "communication_queen_assignments"
CLAIMED_ASSIGNMENTS_DIR = ASSIGNMENT_ROOT / "claimed"
RETURNED_ASSIGNMENTS_DIR = ASSIGNMENT_ROOT / "returned"
CT_CHAT_MEMORY_PATH = "/opt/engel/memory/persistent_chat/ENGEL_AI_MAIN_LLM_CHAT_MEMORY.jsonl"
FLUTTER_CHAT_DIAGNOSTIC_PATH = (
    ROOT
    / "runtime"
    / "temp"
    / "engel-rust-rewrite"
    / "chat_diagnostics"
    / "engel_ui_chat_diagnostics.jsonl"
)
LOCAL_ONLY_TRAINING_SENTINEL = (
    ROOT / "runtime" / "one_hour_local_only_chat_training" / "active.json"
)
EXPECTED_CONICAL_WORKERS = {
    "android_worker_alpha",
    "android_worker_beta",
    "android_worker_gamma",
    "DESKTOP-UE5A6GG",
}


def _activate_local_only_guard(
    run_id: str,
    expires_at_epoch: float,
    *,
    prompt_run_claim: PromptRunClaim,
    scheduled_hours: int,
    requested_minutes: float,
    training_level: str,
    level_profile: dict[str, Any],
    trainings_per_hour: int,
    cadence_seconds: float,
    training_targets: str = "slm,llm",
    wrapper_pid: int = 0,
    launcher_log: str = "",
    lifecycle_receipt: str = "",
) -> dict[str, Any]:
    """Publish the current claimed run to the persistent UI worker.

    The sentinel is a readable status surface, never the concurrency primitive.  The
    caller must own the kernel-released claim and a foreign RUNNING sentinel is replaced,
    not accepted as authorization for this process.
    """

    prompt_run_claim.require_owner(run_id)
    existing: dict[str, Any] = {}
    try:
        value = json.loads(
            LOCAL_ONLY_TRAINING_SENTINEL.read_text(encoding="utf-8-sig")
        )
        if isinstance(value, dict):
            existing = value
    except (OSError, ValueError, TypeError):
        pass
    payload = {
        "schema": "engel_ui_local_only_training_active_v2",
        "status": "RUNNING",
        "run_id": run_id,
        "started_at_utc": iso_now(),
        "expires_at_epoch": float(expires_at_epoch),
        "provider_policy": "local_only",
        "scheduled_hours": scheduled_hours,
        "requested_minutes": requested_minutes,
        "training_level": training_level,
        "training_targets": training_targets,
        "training_level_profile": level_profile["profile_id"],
        "training_level_guidance": level_profile["guidance"],
        "trainings_per_hour": trainings_per_hour,
        "cadence_seconds": cadence_seconds,
        "guard_owner": "python_runner",
        "completion_owner": "python_runner",
        # Flutter owns the PowerShell process it launched and stops its whole process
        # tree.  Keep that PID for exact UI stop ownership while separately binding the
        # active Python runner to the OS claim.
        "launcher_pid": int(wrapper_pid or os.getpid()),
        "runner_pid": os.getpid(),
        "log": str(launcher_log or ""),
        "lifecycle_receipt": str(lifecycle_receipt or ""),
        "prompt_run_claim": prompt_run_claim.owner_record,
    }
    if existing:
        payload["superseded_guard"] = {
            "run_id": str(existing.get("run_id") or ""),
            "status": str(existing.get("status") or ""),
            "launcher_pid": existing.get("launcher_pid"),
            "guard_owner": str(existing.get("guard_owner") or ""),
        }
    LOCAL_ONLY_TRAINING_SENTINEL.parent.mkdir(parents=True, exist_ok=True)
    temp = LOCAL_ONLY_TRAINING_SENTINEL.parent / (
        f".{LOCAL_ONLY_TRAINING_SENTINEL.name}.{os.getpid()}.{time.time_ns()}.tmp"
    )
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(temp, LOCAL_ONLY_TRAINING_SENTINEL)
    return {"ok": True, "owned": True, **payload}


def _finish_local_only_guard(
    run_id: str,
    status: str,
    *,
    prompt_run_claim: PromptRunClaim,
) -> None:
    prompt_run_claim.require_owner(run_id)
    try:
        payload = json.loads(
            LOCAL_ONLY_TRAINING_SENTINEL.read_text(encoding="utf-8-sig")
        )
    except (OSError, ValueError, TypeError) as exc:
        raise RuntimeError("current local-only guard cannot be read") from exc
    claim_record = payload.get("prompt_run_claim") if isinstance(payload, dict) else {}
    if (
        not isinstance(payload, dict)
        or str(payload.get("run_id") or "") != run_id
        or str(payload.get("status") or "").upper() != "RUNNING"
        or int(payload.get("runner_pid") or 0) != os.getpid()
        or not isinstance(claim_record, dict)
        or str(claim_record.get("run_id") or "") != run_id
        or int(claim_record.get("owner_pid") or 0) != os.getpid()
        or Path(str(claim_record.get("claim_path") or "")).resolve()
        != prompt_run_claim.path
    ):
        raise RuntimeError(
            "refusing to finish a local-only guard not bound to this claimed run"
        )
    payload["status"] = status
    payload["finished_at_utc"] = iso_now()
    payload["expires_at_epoch"] = 0
    temp = LOCAL_ONLY_TRAINING_SENTINEL.parent / (
        f".{LOCAL_ONLY_TRAINING_SENTINEL.name}.{os.getpid()}.{time.time_ns()}.tmp"
    )
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(temp, LOCAL_ONLY_TRAINING_SENTINEL)


user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

user32.OpenClipboard.argtypes = [wintypes.HWND]
user32.OpenClipboard.restype = wintypes.BOOL
user32.EmptyClipboard.argtypes = []
user32.EmptyClipboard.restype = wintypes.BOOL
user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
user32.SetClipboardData.restype = wintypes.HANDLE
user32.CloseClipboard.argtypes = []
user32.CloseClipboard.restype = wintypes.BOOL
kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalUnlock.restype = wintypes.BOOL


SW_RESTORE = 9
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
VK_CONTROL = 0x11
VK_A = 0x41
VK_V = 0x56
VK_BACK = 0x08
CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002

ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("union", INPUTUNION)]


INPUT_KEYBOARD = 1
user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = wintypes.UINT

ENUM_WINDOWS_PROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
user32.EnumWindows.argtypes = [ENUM_WINDOWS_PROC, wintypes.LPARAM]
user32.EnumWindows.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def _paths_since(root: Path, since_epoch: float, pattern: str) -> list[Path]:
    if not root.exists():
        return []
    return sorted(
        [path for path in root.glob(pattern) if path.is_file() and path.stat().st_mtime >= since_epoch],
        key=lambda item: item.stat().st_mtime,
    )


def _wait_for_flutter_worker_result(
    start_offset: int,
    *,
    timeout: float = 90.0,
) -> dict[str, Any]:
    """Wait until the visible Flutter process consumes the current worker result."""
    deadline = time.time() + max(1.0, timeout)
    offset = max(0, int(start_offset))
    while time.time() < deadline:
        try:
            current_size = FLUTTER_CHAT_DIAGNOSTIC_PATH.stat().st_size
            if current_size < offset:
                offset = 0
            with FLUTTER_CHAT_DIAGNOSTIC_PATH.open("rb") as handle:
                handle.seek(offset)
                chunk = handle.read()
                offset = handle.tell()
        except OSError:
            chunk = b""
        for raw_line in chunk.splitlines():
            try:
                event = json.loads(raw_line.decode("utf-8-sig"))
            except (UnicodeDecodeError, ValueError, TypeError):
                continue
            if (
                isinstance(event, dict)
                and event.get("event") == "worker_result_received"
            ):
                return {
                    "ok": True,
                    "event": event,
                    "diagnostic_path": str(FLUTTER_CHAT_DIAGNOSTIC_PATH),
                }
        time.sleep(0.5)
    return {
        "ok": False,
        "reason": "fresh Flutter worker_result_received event not observed",
        "diagnostic_path": str(FLUTTER_CHAT_DIAGNOSTIC_PATH),
    }


def _find_window() -> int:
    candidates: list[tuple[int, int]] = []

    @ENUM_WINDOWS_PROC
    def collect(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(wintypes.HWND(hwnd)):
            return True
        length = int(user32.GetWindowTextLengthW(wintypes.HWND(hwnd)))
        if length <= 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(wintypes.HWND(hwnd), buffer, len(buffer))
        if buffer.value.strip() != "Engel AI Main":
            return True
        candidates.append((int(hwnd), _pid_for_window(int(hwnd))))
        return True

    user32.EnumWindows(collect, 0)
    expected = os.path.normcase(os.path.abspath(str(APP_EXE)))
    for hwnd, pid in candidates:
        process_path = _process_path(pid)
        if process_path and os.path.normcase(os.path.abspath(process_path)) == expected:
            return hwnd
    for hwnd, pid in candidates:
        process_path = os.path.normcase(_process_path(pid))
        if process_path.endswith("\\engelaimain.exe"):
            return hwnd
    if candidates:
        return candidates[0][0]
    return 0


def _pid_for_window(hwnd: int) -> int:
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(wintypes.HWND(hwnd), ctypes.byref(pid))
    return int(pid.value)


def _process_path(pid: int) -> str:
    command = [
        "powershell",
        "-NoProfile",
        "-Command",
        f"(Get-Process -Id {pid}).Path",
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=10, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return completed.stdout.strip()
    except Exception:
        return ""


def _ensure_window() -> tuple[int, int, str]:
    hwnd = _find_window()
    if hwnd == 0:
        subprocess.Popen([str(APP_EXE)], cwd=str(APP_CWD))
        deadline = time.time() + 30
        while time.time() < deadline:
            hwnd = _find_window()
            if hwnd:
                break
            time.sleep(0.5)
    if hwnd == 0:
        raise RuntimeError("Engel AI Main window not found")
    pid = _pid_for_window(hwnd)
    path = _process_path(pid)
    user32.ShowWindow(wintypes.HWND(hwnd), SW_RESTORE)
    user32.MoveWindow(wintypes.HWND(hwnd), 0, 0, 1500, 900, True)
    time.sleep(0.4)
    user32.SetForegroundWindow(wintypes.HWND(hwnd))
    time.sleep(0.4)
    return hwnd, pid, path


def _start_fresh_chat(hwnd: int) -> None:
    rect = _rect(hwnd)
    user32.ShowWindow(wintypes.HWND(hwnd), SW_RESTORE)
    user32.SetForegroundWindow(wintypes.HWND(hwnd))
    time.sleep(0.3)
    # A native Training-page launch can leave "Training" in the persistent
    # sidebar filter. Clear it first so the fixed Home coordinate cannot select
    # the filtered Training result again.
    _click(rect.left + 210, rect.top + 198)
    for _ in range(64):
        _press_key(VK_BACK)
    time.sleep(0.5)
    # Follow the same visible workflow as a person: Home -> New chat.
    _click(rect.left + 105, rect.top + 265)
    time.sleep(0.7)
    _click(rect.left + 620, rect.top + 312)
    time.sleep(0.8)


def _close_previous_build_preview(hwnd: int) -> None:
    """Close the proof panel opened by the preceding build.

    The panel can hide the fixed bottom composer after a tall preview renders.
    This helper is only called between accepted build prompts, when the prior
    build contract guarantees that the proof panel is open.
    """
    rect = _rect(hwnd)
    user32.ShowWindow(wintypes.HWND(hwnd), SW_RESTORE)
    user32.SetForegroundWindow(wintypes.HWND(hwnd))
    time.sleep(0.2)
    _click(rect.right - 72, rect.top + 160)
    time.sleep(0.8)


def _rect(hwnd: int) -> RECT:
    rect = RECT()
    user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(rect))
    return rect


def _click(x: int, y: int) -> None:
    user32.SetCursorPos(int(x), int(y))
    time.sleep(0.08)
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.05)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    time.sleep(0.15)


def _key_down(vk: int) -> None:
    user32.keybd_event(vk, 0, 0, 0)


def _key_up(vk: int) -> None:
    user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)


def _hotkey(ctrl_key: int) -> None:
    _key_down(VK_CONTROL)
    time.sleep(0.03)
    _key_down(ctrl_key)
    time.sleep(0.03)
    _key_up(ctrl_key)
    time.sleep(0.03)
    _key_up(VK_CONTROL)
    time.sleep(0.15)


def _press_key(vk: int) -> None:
    _key_down(vk)
    time.sleep(0.03)
    _key_up(vk)
    time.sleep(0.08)


def _type_text(text: str) -> None:
    for char in text:
        code = ord(char)
        down = INPUT()
        down.type = INPUT_KEYBOARD
        down.union.ki = KEYBDINPUT(0, code, KEYEVENTF_UNICODE, 0, 0)
        up = INPUT()
        up.type = INPUT_KEYBOARD
        up.union.ki = KEYBDINPUT(0, code, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0, 0)
        sent = user32.SendInput(1, ctypes.byref(down), ctypes.sizeof(INPUT))
        sent += user32.SendInput(1, ctypes.byref(up), ctypes.sizeof(INPUT))
        if sent != 2:
            raise RuntimeError(f"SendInput failed while typing U+{code:04X}")
        time.sleep(0.002)


def _set_clipboard_text(text: str) -> None:
    data = text + "\0"
    encoded = data.encode("utf-16-le")
    if not user32.OpenClipboard(None):
        raise RuntimeError("OpenClipboard failed")
    try:
        user32.EmptyClipboard()
        handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(encoded))
        if not handle:
            raise RuntimeError("GlobalAlloc failed")
        locked = kernel32.GlobalLock(handle)
        if not locked:
            raise RuntimeError("GlobalLock failed")
        ctypes.memmove(locked, encoded, len(encoded))
        kernel32.GlobalUnlock(handle)
        if not user32.SetClipboardData(CF_UNICODETEXT, handle):
            raise RuntimeError("SetClipboardData failed")
    finally:
        user32.CloseClipboard()


def _paste_text_with_forms(text: str) -> None:
    encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
    ps = f"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
$text = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String('{encoded}'))
Set-Clipboard -Value $text
[System.Windows.Forms.SendKeys]::SendWait('^a')
Start-Sleep -Milliseconds 100
[System.Windows.Forms.SendKeys]::SendWait('^v')
Start-Sleep -Milliseconds 200
"""
    completed = subprocess.run(
        ["powershell", "-STA", "-NoProfile", "-Command", ps],
        capture_output=True,
        text=True,
        timeout=20,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if completed.returncode != 0:
        raise RuntimeError(f"SendKeys paste failed: {completed.stderr.strip()}")


# The chat service refuses a reply that was asked for an evidence ledger and did
# not deliver one (checks `answers_requested_evidence_ledger` and
# `preserves_safe_work_boundary`). That gate is right -- an answer that skips the
# split is not auditable -- but the model only produces the categories when the
# prompt names them, so every training prompt states the answer contract. It also
# happens to be the shape this curriculum is meant to teach: sourced facts kept
# apart from open items, an owner per gap, and an explicit stop condition.
# Order matters: long replies get truncated, so the stop condition goes FIRST.
# With it last, the model ran out of tokens mid-ledger and the turn was rejected
# for a boundary it simply never reached.
# (2026-08-14) The sourced-fact line is EXCERPT-ONLY. The old form had a free-text
# <claim> slot, but the grader requires every substantive claim word to appear inside
# the quote - so a model summarizing in its own words failed by construction (13 of 33
# rejections), and 5 more failed for copying the packet's old 'page N;' token. The
# contract now matches the packet line and the grader exactly; anything in the model's
# own words belongs under Open items.
_TRAINING_ANSWER_CONTRACT = (
    "Use exactly this structure and these headings, in this order, pressing Enter after "
    "every heading and every list entry so each is on its own line:\n"
    "1. One line beginning 'Must not proceed until confirmed:' naming the work to hold.\n"
    "2. A heading 'Sourced facts:' listing only what the verified evidence packet supports. "
    "Put exactly one record on each line in this literal form: '- Source document: \"<exact "
    "manifest filename>\"; Section <id>; Source excerpt: \"<the packet excerpt copied "
    "character-for-character>\"'. Change nothing inside the quotes and add no summary or "
    "restatement on that line - your own words go under Open items. A line may bind one "
    "document and one Section only; never use one document's quote for another document's "
    "claim.\n"
    "3. A heading 'Open items:' listing what is still missing. For each one name the owner "
    "who confirms it, then a line starting 'Proof:' naming the receipt or verifier that "
    "will prove it. The literal word 'Proof:' must appear at least once.\n"
    "Keep the whole answer under 220 words so it finishes completely. Do not guess a value "
    "you do not have and do not invent a source. Anything you cannot evidence belongs under "
    "'Open items:', never under 'Sourced facts:'."
)

# Math discipline: verified math, not a field evidence-ledger. Worded to avoid the CT246
# incomplete-input trigger so a correct math turn is served (and then vetted by the
# runner's deterministic CAS eligibility check) instead of being discarded.
_MATH_ANSWER_CONTRACT = (
    "Answer ONLY in this filled-in form, with real values -- do NOT describe the form or "
    "repeat these instructions:\n"
    "Result: <your answer, or 'No verified result' if you could not check it>\n"
    "Work: <the key steps, briefly>\n"
    "Check: <substitute the answer back or recompute a second way, and show the number you "
    "got>\n"
    "Keep it short so it finishes. Do not state a number you did not verify."
)

# Engineering discipline (Engel systems): every claim carries a real component, verifier,
# or receipt. Grounding is vetted by the runner's grounding gate. Worded to avoid the
# incomplete-input trigger.
_ENGINEERING_ANSWER_CONTRACT = (
    "Answer ONLY in this filled-in form, grounded in Engel's real system, with real values "
    "-- do NOT describe the form or repeat these instructions:\n"
    "Confirmed: <a claim tied to a real Engel component, file, or route>\n"
    "Proof: <the verifier or receipt that proves it -- a real file path or a verify_*.py>\n"
    "Still open: <anything no verifier confirms yet, or 'None'>\n"
    "Keep it short. Do not invent a file, verifier, receipt, or capability; if you cannot "
    "point to a real one, say so plainly rather than guess."
)

# Communication discipline (2026-08-01): this is the ONE discipline whose accepted answer
# text is trained on directly as Engel's chat voice, so its contract must not impose a
# labelled form the way the three above do -- a filled-in form here would teach Engel to
# answer Joshua in headings. The closing "do not restate these instructions" is deliberate:
# it is a shared CONTRACT_ECHO_MARKER, so a model that parrots this contract instead of
# answering is caught by the same single-source echo detector as every other discipline.
_COMMUNICATION_ANSWER_CONTRACT = (
    "You are Engel AI Main, talking to Joshua in the desktop Engel chat. You are not a "
    "Discord guest, not Engelz, and not a tool-permission card. Answer the way you would "
    "answer Joshua in the main Engel chat: first person, plain sentences, your own voice. "
    "No headings, no 'Result:'/'Confirmed:' style labels, no bullet lists, no code blocks. "
    "Say what you actually know, say plainly what you do not know instead of filling the gap, "
    "and keep it to a few short paragraphs. Do not restate these instructions."
)

_DISCIPLINE_ANSWER_CONTRACTS = {
    "aec": _TRAINING_ANSWER_CONTRACT,
    "math": _MATH_ANSWER_CONTRACT,
    "engineering": _ENGINEERING_ANSWER_CONTRACT,
    "communication": _COMMUNICATION_ANSWER_CONTRACT,
}


def _training_answer_contract(discipline: str = "aec") -> str:
    return _DISCIPLINE_ANSWER_CONTRACTS.get(
        str(discipline or "aec").strip().casefold(), _TRAINING_ANSWER_CONTRACT
    )


def _aec_evidence_for_card(material_card: Any) -> dict[str, Any]:
    """Resolve one card's reviewed anchors before any training-side mutation.

    The generated template carries only exact filenames and section ids. This read-only
    preflight opens the verified v2 corpus, extracts bounded source text, and refuses an
    incomplete/ambiguous card. The resulting excerpts are delivered to the model; they are
    not added to ``base_prompt`` and therefore cannot manufacture prompt novelty.
    """
    if not isinstance(material_card, dict):
        raise RuntimeError("AEC schedule has no material card grounding")
    documents = material_card.get("documents")
    anchors = material_card.get("evidence_anchors")
    if not isinstance(documents, list) or not documents:
        raise RuntimeError("AEC material names no exact manifest documents")
    if not isinstance(anchors, list) or not anchors:
        raise RuntimeError("AEC material names no evidence anchors")
    expected_documents = [str(item or "") for item in documents]
    anchored_documents = {
        str(item.get("document") or "")
        for item in anchors
        if isinstance(item, dict)
    }
    if (
        any(not item for item in expected_documents)
        or len(set(expected_documents)) != len(expected_documents)
        or anchored_documents != set(expected_documents)
    ):
        raise RuntimeError(
            "AEC material document list and evidence-anchor documents do not match"
        )
    import engel_construction_corpus as _ccc

    override = str(os.environ.get(_ccc.CORPUS_ROOT_ENV) or "").strip()
    corpus_root = Path(override) if override else None
    packet = _ccc.build_prompt_evidence_context(
        anchors,
        corpus_root=corpus_root,
    )
    if packet.get("ok") is not True:
        raise RuntimeError(
            "AEC evidence preflight failed before UI delivery: "
            + " | ".join(packet.get("blockers") or ["unknown evidence failure"])
        )
    if set(packet.get("documents") or []) != set(expected_documents):
        raise RuntimeError(
            "AEC evidence packet did not resolve every declared source document"
        )
    return {
        **packet,
        "expected_documents": expected_documents,
    }


def _leveled_training_prompt(
    prompt: str,
    training_level: str,
    discipline: str = "aec",
    evidence_context: str = "",
) -> str:
    delivered = (
        f"{apply_training_level_to_prompt(prompt, training_level, discipline)}\n\n"
        f"{_training_answer_contract(discipline)}"
    )
    if str(evidence_context or "").strip():
        delivered += "\n\n" + str(evidence_context).strip()
    return delivered


# --- Domain-appropriate training-sample eligibility (2026-07-31) ---------------
# For non-AEC curricula the CT246 construction gate does not apply (the prompts are
# worded not to trip it), so the server marks the turn eligible on delivery alone.
# These runner-side checks re-vet the captured answer against the domain's OWN bar
# and can only DOWNGRADE a server-eligible turn -- never upgrade one -- so an
# unverified math answer or an ungrounded engineering claim is never captured.
_MATH_VERIFICATION_SIGNALS = (
    "substitut", "recompute", "recomputation", "differentiat", "enumerat",
    "residual", "modulo", "modular", "bound", "second method", "second way",
    "two ways", "two independent", "cross-check", "cross check",
    "independent method", "independent check", "counterexample", "sympy",
    "verified", "verify",
    # (2026-08-07) Measured on the first 8h Math School run: 12 replies whose Check line
    # used a REAL independent method were rejected here because they named the method in
    # natural maths language instead of a listed word -- "d/dx [x^3/3] = x^2 (matches
    # integrand)" (differentiate-back), "Expand e^x as 1 + x + x^2/2" (series expansion
    # against L'Hospital), "Row echelon form via elimination" (determinant re-derivation),
    # "Monte Carlo simulation with 10,000 trials". Widening FORM vocabulary is safe: the
    # concrete-relation requirement and the CAS refutation backstop still hold, so this
    # admits differently-worded verification, not unverified prose.
    "matches", "agrees", "expand", "series", "echelon", "elimination",
    "monte carlo", "isprime", "spot-check", "spot check", "simulat",
)
_ENGINEERING_GROUNDING_SIGNALS = (
    "tools/", "tools\\", "verify_", ".py", "ct246", "engel_", "receipt",
    "verifier", "/opt/engel", "device_", "lan_link", "manifest",
)
# A small local model sometimes RESTATES the answer contract instead of producing an
# answer ("Engel answers as verified math in exactly this structure: 1. Result: the
# answer..."). Those echoes mention every heading and method word, so a structural check
# alone would wrongly accept them. Reject any reply carrying a distinctive contract phrase.
# Single source: the markers live in engel_governor (the service-side ingest
# guard uses the same list; a second copy here would drift).
from engel_governor import CONTRACT_ECHO_MARKERS as _CONTRACT_ECHO_MARKERS
# A genuine math answer shows a concrete evaluated relation (an "= <number>" or arithmetic
# between numbers); a contract echo describes the process without ever computing one.
# isprime()/"N is prime" added 2026-08-07: "Result: 29 is prime / Check: sympy.isprime(29)
# returns True" is a concrete machine-checkable statement with no "=" anywhere -- two such
# rows were rejected as non-concrete on the first 8h Math School run.
_MATH_CONCRETE = re.compile(
    r"=\s*-?\d|\d\s*[-+*/^]\s*\d|\bmod\b|isprime\s*\(\s*\d|\b\d+\s+is\s+(?:not\s+)?(?:prime|composite)\b"
)


def _looks_like_contract_echo(low: str) -> bool:
    return any(marker in low for marker in _CONTRACT_ECHO_MARKERS)


_NUMERIC_EQUALITY = re.compile(r"([0-9()+\-*/^.\s]+?)\s*=\s*(-?[0-9()+\-*/^.\s]+)")

# (2026-07-31 live-proof fix) Models write correct math in Unicode ("2² -5*2 +6 = 0");
# the ASCII extractor class broke at "²", mutilating the relation into "-5*2 +6 = 0"
# and the CAS then "proved" the model's CORRECT answer false -- 3/3 verified sparse-MoE
# answers were rejected this way. Normalize the Unicode first so the full relation is
# checked, and treat any fragment GLUED to a character the class cannot represent as a
# mutilated slice, never a checkable relation.
_MATH_UNICODE_NORMALIZE = {
    "²": "^2", "³": "^3", "⁴": "^4", "⁵": "^5", "⁶": "^6",
    "⁷": "^7", "⁸": "^8", "⁹": "^9", "¹": "^1", "⁰": "^0",
    "−": "-", "×": "*", "÷": "/", "·": "*",
}
_EXPR_GLUE_CHARS = "²³⁴⁵⁶⁷⁸⁹¹⁰√±≈≠≤≥[]{}_"

# (2026-08-06) HANG GUARD. The candidate charset below is digits and operators only, which
# feels safe and is not: "9^9^9^9" is entirely legal here, and sympy.simplify on a power
# tower never returns. Proven in-process against this exact function -- a 68-character model
# reply froze the admit gate indefinitely, in the code path an 80-prompt math run executes
# once per prompt. One such reply would hang an 8-hour run with no error and no timeout.
#
# Two layers, because either alone is insufficient:
#   1. refuse pathological shapes BEFORE sympy sees them (cheap, deterministic)
#   2. a wall-clock bound around the CAS call as the backstop for whatever slips past
# Both fail OPEN -- an expression we decline to evaluate is "not refuted", never "false".
# Refusing to judge must never become a rejection: this gate exists to catch demonstrably
# wrong arithmetic, not to punish arithmetic that is merely expensive.
_MATH_MAX_EXPR_CHARS = 120
_MATH_MAX_EXPONENTS = 2
_MATH_MAX_LITERAL_DIGITS = 12
_MATH_CAS_TIMEOUT_SECONDS = 2.0


def _expression_is_evaluable(raw: str) -> bool:
    """False when an expression is too explosive to hand to the CAS at all."""
    if len(raw) > _MATH_MAX_EXPR_CHARS:
        return False
    # A power TOWER is the killer: 9^9^9^9 has three, and each one multiplies the digit
    # count of the result. Ordinary school arithmetic ("2^3 + 1") stays well under this.
    if raw.count("^") + raw.count("**") > _MATH_MAX_EXPONENTS:
        return False
    if any(len(literal) > _MATH_MAX_LITERAL_DIGITS for literal in re.findall(r"\d+", raw)):
        return False
    # Even two exponents can explode if the operands are large ("99^99^9"), so bound the
    # base/exponent pair directly rather than trusting the count alone.
    for base, exponent in re.findall(r"(\d+)\s*(?:\^|\*\*)\s*(\d+)", raw):
        if len(base) * int(exponent or 0) > 64:
            return False
    return True


def _cas_difference_is_nonzero(sympy: Any, lhs: Any, rhs: Any) -> bool | None:
    """True/False if the CAS decided within its budget, None if it did not.

    Windows has no SIGALRM, so the bound is a daemon worker plus a join deadline. The
    thread may keep running after we stop waiting -- it is a daemon, so it cannot hold the
    process open, and the pre-filter above means we should never reach here with something
    that actually spins."""
    import threading

    outcome: dict[str, Any] = {}

    def _work() -> None:
        try:
            diff = sympy.simplify(lhs - rhs)
            outcome["value"] = bool(
                diff.is_number and abs(complex(sympy.N(diff))) > 1e-6
            )
        except Exception:
            outcome["value"] = False

    worker = threading.Thread(target=_work, daemon=True)
    worker.start()
    worker.join(_MATH_CAS_TIMEOUT_SECONDS)
    return outcome.get("value")


def _math_check_has_false_relation(reply: str) -> bool:
    """Best-effort CAS refutation: parse simple numeric equalities 'A = B' out of the answer
    and return True ONLY when sympy proves at least one is arithmetically FALSE. Conservative
    by design -- any side that does not cleanly parse to a comparable number is skipped, so
    this only ever rejects an answer whose own arithmetic is demonstrably wrong (e.g.
    'Check: 2*4 = 9'); it never fabricates a rejection on ambiguity. Verification only
    proves the EXTRACTED expression, so extraction must never mutilate a correct one."""
    text = str(reply or "")
    for src, dst in _MATH_UNICODE_NORMALIZE.items():
        text = text.replace(src, dst)
    # (2026-08-07) Digit-grouping commas slice numbers the same way "²" once did: the
    # class excludes ",", so "1,666/10,000 = 0.1667" enters extraction mid-number and a
    # correct Monte Carlo check is "refuted". Strip grouping commas only (digit,digit{3}),
    # never prose commas.
    text = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", text)
    matches = list(_NUMERIC_EQUALITY.finditer(text))
    if not matches:
        return False
    try:
        import engel_math_lane as _ml

        sympy = _ml._sympy()
    except Exception:
        return False
    candidates: list[tuple[str, str]] = []
    for match in matches:
        before = text[match.start(1) - 1 : match.start(1)]
        if before and (before.isalpha() or before in _EXPR_GLUE_CHARS):
            # e.g. "2x^2 - 5x + 2 = 0": the fragment starting after 'x' is a slice
            # of a symbolic equation, not a numeric relation.
            continue
        rhs_text = match.group(2)
        after = text[match.end(2) : match.end(2) + 1]
        if (
            after
            and not rhs_text[-1:].isspace()
            and (after.isalpha() or after in _EXPR_GLUE_CHARS)
        ):
            # RHS glued straight into a symbol ("= 4x") -- truncated, skip. A letter
            # after trailing whitespace is ordinary prose ("= 0. Both satisfy...").
            continue
        # (2026-08-07) MODULAR ARITHMETIC IS NOT PLAIN EQUALITY. "3^2 = 1 mod 4" is TRUE
        # and was refuted as 9 != 1 because the qualifier sits outside the numeric class.
        # A congruence context near the relation makes it unjudgeable here -- skip it
        # (fail open), never grade the equality as if the modulus were not written.
        context = text[max(0, match.start() - 24) : match.end() + 12].casefold()
        if "≡" in context or re.search(r"\bmod(?:ulo)?\s*\d|\(\s*mod\b|\bmod\b", context):
            continue
        candidates.append((match.group(1), match.group(2)))
    for lhs_raw, rhs_raw in candidates[:16]:
        # (2026-08-06) Cut each side at a SENTENCE/STEP boundary before parsing. A decimal
        # point is never followed by whitespace, so a period that is marks the end of a
        # step -- and the answer contract asks for exactly the numbered Work steps that
        # produce this shape:
        #   "1. Calculate determinant: (2*4 - 3*1) = 5. 2. Adjugate matrix..."
        # The old capture read the RHS as "5. 2", parsed it as 5.2, and refuted 5 != 5.2 --
        # so a CORRECT answer was rejected for enumerating its work. Measured live: the
        # identical arithmetic passes without the numbering and is refuted with it, and it
        # was the only substantive math reply the good lane produced in an 8-prompt sample.
        # RHS keeps the head (text before the boundary), LHS keeps the tail (text after).
        rhs_raw = re.split(r"\.(?=\s|$)", rhs_raw)[0]
        lhs_parts = re.split(r"\.(?=\s|$)", lhs_raw)
        lhs_raw = lhs_parts[-1] if len(lhs_parts) > 1 else lhs_raw
        lhs_raw, rhs_raw = lhs_raw.strip(" .,"), rhs_raw.strip(" .,")
        if not (re.search(r"\d", lhs_raw) and re.search(r"\d", rhs_raw)):
            continue
        if not re.fullmatch(r"[0-9()+\-*/^.\s]+", lhs_raw) or not re.fullmatch(
            r"[0-9()+\-*/^.\s]+", rhs_raw
        ):
            continue
        # Explosive expressions are declined, not judged -- see the hang guard above.
        if not (_expression_is_evaluable(lhs_raw) and _expression_is_evaluable(rhs_raw)):
            continue
        try:
            lhs = _ml.parse_expr_safe(lhs_raw.replace("^", "**"))
            rhs = _ml.parse_expr_safe(rhs_raw.replace("^", "**"))
            if lhs is None or rhs is None:
                continue
            decided = _cas_difference_is_nonzero(sympy, lhs, rhs)
            if decided:
                return True
            # decided is None -> the CAS ran out of budget. Unproven, so not refuted.
        except Exception:
            continue
    return False


def _math_answer_shows_verification(reply: str) -> bool:
    """True when a math answer carries the verification discipline: a 'Result:' (or an
    honest 'No verified result'), a 'Check:', an independent-method signal, and a concrete
    computed relation; is NOT a restatement of the answer contract; and contains no
    arithmetic relation the CAS can prove false. This is the math curriculum's stated lesson
    (the HABIT of not asserting an unchecked number) and the guard that keeps unverified,
    CAS-refuted, and empty contract-echo answers out of training."""
    low = " ".join(str(reply or "").split()).casefold()
    if not low or _looks_like_contract_echo(low):
        return False
    # (2026-08-06) A bare refusal used to pass this gate ENTIRELY. "No verified result"
    # satisfied has_result, satisfied has_concrete through the same escape, and satisfied
    # has_signal because "verified" is itself one of the signal words -- so any refusal
    # carrying a "Check:" line was admitted as verified math containing no arithmetic.
    # A live probe caught two of four math turns admitted this way on BYTE-IDENTICAL
    # 280-char refusal text.
    #
    # Saying it stays legal: the contract deliberately offers "No verified result" so the
    # model is never cornered into fabricating a number, and that honesty is the lesson.
    # But a refusal is not a positive EXAMPLE of the habit being taught, and admitting it
    # costs twice -- the corpus learns to refuse, and because the refusals are canned,
    # identical text lands as several separate rows.
    concrete = bool(_MATH_CONCRETE.search(low))
    if "no verified result" in low and not concrete:
        return False
    has_result = "result:" in low or "no verified result" in low
    has_check = "check:" in low
    has_signal = any(sig in low for sig in _MATH_VERIFICATION_SIGNALS)
    # (2026-08-07) A Check line that itself COMPUTES is verification even when it names no
    # method: "Check: A*x = [2*(14/5)+1*(-3/5), ...] = [5, 6]" multiplies the solution back
    # into the system -- substitution in matrix form -- and was rejected here for lacking a
    # vocabulary word. Arithmetic in the check IS the independent-method evidence; the CAS
    # refutation below still owns correctness, so this widens wording, not rigor.
    if not has_signal and has_check:
        check_text = low[low.find("check:"):]
        has_signal = bool(_MATH_CONCRETE.search(check_text))
    if not (has_result and has_check and has_signal and concrete):
        return False
    if _math_check_has_false_relation(reply):
        return False
    # (2026-08-06) CORRECTNESS, not just form. Everything above this line grades the SHAPE
    # of an answer, and shape is exactly what a wrong answer imitates best: "Result: x = 4 /
    # Check: substituted back, 2*4 + 1 = 9" satisfied every check above while being wrong,
    # because 9 really does equal 9 and nothing knew it should equal 7. Measured before this
    # call existed, the gate admitted x=4 for 2x+1=7, d/dx x^2 = 3x, and integral 2x = x^3.
    # Training on those teaches that verification-shaped prose IS verification -- the precise
    # habit this curriculum exists to remove, and one that carries into code generation.
    # Math is the only discipline here where correctness is DECIDABLE, so it is the one place
    # a gate can do better than grade form. Refutes only what the CAS proves wrong; anything
    # unparsed or too costly stays admitted.
    return not _math_answer_is_cas_refuted(reply)


def _math_truth_grade(reply: str, prompt: str) -> dict[str, Any]:
    """Grade against declared ground truth. Never raises; an unknown problem is not a fault."""
    try:
        import engel_math_problems as _mp

        return _mp.grade_reply(reply, prompt)
    except Exception:
        return {"matched": False, "verdict": "undecidable", "exactly_verified": False,
                "wrong": False, "detail": "ground-truth grading unavailable"}


def _aec_citation_truth(
    reply: str,
    prompt_context: str = "",
    expected_documents: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Resolve cited sections and verify their local claim text against source evidence.
    Never raises; unsupported or unresolved claims remain undecidable and are not admitted."""
    try:
        import engel_construction_corpus as _ccc

        override = str(os.environ.get(_ccc.CORPUS_ROOT_ENV) or "").strip()
        corpus_root = Path(override) if override else None
        return _ccc.grade_reply(
            reply,
            corpus_root=corpus_root,
            context=prompt_context,
            expected_documents=expected_documents,
        )
    except Exception:
        return {"verdict": "undecidable", "refuted": False, "exactly_verified": False,
                "detail": "construction corpus unavailable"}


def _code_answer_truth(reply: str) -> dict[str, Any]:
    """Execute the code a reply asserts (sandboxed, Forge-gated). Never raises; a reply
    with no labelled python block is undecidable, not a fault -- same asymmetry as math:
    only code whose OWN program provably breaks loses its row."""
    try:
        import engel_code_answer_verifier as _cav

        return _cav.grade_reply(reply)
    except Exception:
        return {"verdict": "undecidable", "refuted": False, "exactly_verified": False,
                "detail": "code verification unavailable"}


def _math_answer_is_cas_refuted(reply: str) -> bool:
    """True when a CAS proves a claim in the answer wrong. Never raises, never blocks."""
    try:
        import engel_math_answer_verifier as _mav

        return bool(_mav.verify_reply(reply).get("refuted"))
    except Exception:
        # A verifier that cannot run must not reject an answer -- unproven is not wrong.
        return False


def _cited_py_tokens(text: str) -> list[str]:
    """Every .py path token in the text, normalized to forward slashes."""
    tokens = []
    for token in re.findall(r"[A-Za-z0-9_./\\-]+\.py", str(text or "")):
        rel = token.strip().replace("\\", "/").lstrip("/")
        if rel:
            tokens.append(rel)
    return tokens


def _artifact_exists(rel: str) -> bool:
    for candidate in (ROOT / rel, TOOLS / Path(rel).name):
        try:
            if candidate.is_file():
                return True
        except OSError:
            continue
    return False


def _engineering_cites_real_artifact(reply: str, prompt: str = "") -> bool:
    """True when the answer names a file/verifier path that ACTUALLY EXISTS in the repo --
    not a bare keyword and not a fabricated path. This is what stops a confident
    'Proof: tools/verify_engel_fake_thing.py' from being captured as a grounded sample.

    When the PROMPT supplies its own citable artifacts (the capabilities cards do, since
    2026-08-04), the citation must be one of THOSE files. Existence alone was too weak:
    across two 5-hour runs, 22 of 44 admitted rows passed by name-dropping a single real
    but unrelated file (tools/engel_conical_failure_to_issue.py) while the rest of the
    answer stayed fabricated, which trains laundering rather than grounding. Prompts that
    supply nothing keep the plain existence rule, so older packs grade unchanged."""
    allowed = {rel.casefold() for rel in _cited_py_tokens(prompt) if _artifact_exists(rel)}
    for rel in _cited_py_tokens(reply):
        if allowed:
            if rel.casefold() in allowed or Path(rel).name.casefold() in {
                Path(a).name.casefold() for a in allowed
            }:
                return True
            continue
        if _artifact_exists(rel):
            return True
    return False


_CITED_ARTIFACT = re.compile(r"[A-Za-z0-9_./\\-]+\.(?:py|dart|ps1|json|md)")


def _cited_artifact_tokens(text: str) -> list[str]:
    """Every artifact path token in the text, not just .py, normalized to forward slashes.

    _cited_py_tokens deliberately sees only .py because the Proof: citation must be a
    verifier. This one is wider on purpose: the 2026-08-05 run admitted seven rows whose
    fabrication was a .json receipt, which a .py-only tokenizer cannot see at all."""
    tokens = []
    for token in _CITED_ARTIFACT.findall(str(text or "")):
        rel = token.strip().replace("\\", "/").lstrip("/")
        if rel:
            tokens.append(rel)
    return tokens


def _fabricated_artifact_citations(reply: str) -> list[str]:
    """Artifact paths the answer names that do NOT exist in the repo.

    A valid Proof: citation is necessary but NOT sufficient. _engineering_cites_real_artifact
    returns True on the FIRST token that matches a supplied artifact and never looks at the
    rest, so an answer could pair one real citation with a confident fabrication beside it
    and be admitted whole. Measured on the 2026-08-05 8-hour run: 13 of 76 admitted rows
    named a non-existent file, and 4 of those put it in the Proof: line itself
    ('verify_engel_process_liveness.py', which has never existed). That is the laundering
    shape one level down -- the answer proves its citation is real, not that its OTHER
    citations are -- and it trains Engel to invent plausible verifier names."""
    return sorted({rel for rel in _cited_artifact_tokens(reply) if not _artifact_exists(rel)})


_CLAIMED_FUNCTION = re.compile(r"\b([a-z_][a-z0-9_]{3,})\(\)")
_REPO_FUNCTION_NAMES: set[str] | None = None


def _repo_function_names() -> set[str]:
    """Every function name Engel actually defines, plus Python builtins.

    Scanned once and cached: the runner grades one reply per cadence tick, so a single
    sweep of tools/ is free, and the verifiers call the gate in a tight loop."""
    global _REPO_FUNCTION_NAMES
    if _REPO_FUNCTION_NAMES is None:
        names: set[str] = set(dir(builtins))
        try:
            for path in TOOLS.glob("*.py"):
                try:
                    names.update(
                        re.findall(
                            r"^\s*def (\w+)",
                            path.read_text(encoding="utf-8", errors="replace"),
                            re.M,
                        )
                    )
                except OSError:
                    continue
        except OSError:
            pass
        _REPO_FUNCTION_NAMES = names
    return _REPO_FUNCTION_NAMES


def _invented_function_claims(reply: str) -> list[str]:
    """Functions the answer says exist, written as `name()`, that Engel does not define.

    The citation gate proves the FILE is real; it cannot see that the sentence about it is
    false. Measured on the 2026-08-05 8-hour run, after fabricated citations were already
    eliminated: 4 of 68 admitted rows still asserted an API that exists nowhere --
    `check_liveness()` reading `/proc/<pid>/status` (the real function is `pid_is_running`
    and it opens a kernel handle), `run_cas_verification()`, `validate_heartbeat()`,
    `handle_chat_turn()`. Each cited a REAL file, so every earlier gate passed them. That
    trains Engel to invent plausible APIs for its own subsystems, which is the same defect
    as a fabricated path one level in. Checked against every def in tools/ (4,837 names)
    plus builtins, so a real function named in a file the answer did not cite still passes;
    only a name that exists NOWHERE is treated as invented."""
    known = _repo_function_names()
    return sorted(
        {name for name in _CLAIMED_FUNCTION.findall(str(reply or "")) if name not in known}
    )


_PERCENT_CLAIM = re.compile(r"\d{1,3}(?:\.\d+)?\s?%")
_LINE_REF_CLAIM = re.compile(r"#L\d+(?:-\d+)?")
_SCORELINE_CLAIM = re.compile(r"\b(\d{1,4})\s*/\s*(\d{1,4})\b")
# A date is the same shape of invention as a percentage, and the 20260806 run proved it:
# an otherwise clean answer said its verifier was "regression-tested 2024-03-15" -- a year
# before any of this existed. No card supplies a date, so an unsupplied one is never
# checkable here. Both ISO forms plus Engel's own run-stamp format.
_DATE_CLAIM = re.compile(r"\b(?:20\d{2}-\d{2}-\d{2}|20\d{2}/\d{2}/\d{2}|\d{8}T\d{6}Z)\b")


def _unsupplied_figure_claims(reply: str, prompt: str = "") -> list[str]:
    """Figures the answer asserts that nothing in the prompt supplied.

    (2026-08-05) After the citation gate started binding to the card's own artifacts,
    the fabrication MOVED rather than stopped: replies began citing the right file and
    inventing the QUANTITIES instead -- "99.98% task completion rate", "92.3% pass rate
    set in verify_engel_slm.py#L47 (last verified 2026-07-26)", "latency under 200ms".
    Every one carried a real, on-card citation, so every earlier gate passed it. A
    number is the most convincing thing an answer can say and the easiest to invent,
    and training on these teaches Engel to produce confident metrics it never measured.

    No capabilities card supplies a percentage or a line reference, so those are always
    unverifiable here. Scorelines ARE supplied (74/74, 28/28, 21/21), so one is accepted
    when the prompt actually handed it over and rejected when it did not. The rule is
    deliberately about PROVENANCE, not plausibility: the gate cannot check arithmetic,
    but it can check whether anything gave the answer that figure to repeat."""
    text = str(reply or "")
    supplied = str(prompt or "")
    out: list[str] = []
    for match in _PERCENT_CLAIM.findall(text):
        token = match.replace(" ", "")
        if token not in supplied.replace(" ", ""):
            out.append(token)
    for match in _LINE_REF_CLAIM.findall(text):
        if match not in supplied:
            out.append(match)
    for match in _DATE_CLAIM.findall(text):
        if match not in supplied:
            out.append(match)
    for got, total in _SCORELINE_CLAIM.findall(text):
        # x/y only reads as a score when x <= y ("24/7" is not a score).
        if int(got) > int(total):
            continue
        token = f"{got}/{total}"
        if token not in supplied.replace(" ", ""):
            out.append(token)
    # Stable order, no duplicates -- the reason string names up to three.
    return sorted(dict.fromkeys(out))


def _engineering_answer_is_grounded(reply: str, prompt: str = "") -> tuple[bool, str]:
    """True when an engineering answer ties a claim to a REAL Engel artifact: a 'Proof:'
    line and a cited file/verifier path that exists in the repo -- not a contract echo and
    not a fabricated citation.

    Returns (ok, reason). The reason names WHICH of the three observed failure shapes
    happened: a single catch-all string made the curriculum uncorrectable (it blamed
    'echo' for 46 fabricated citations while the echo check had fired zero times)."""
    low = " ".join(str(reply or "").split()).casefold()
    if not low:
        return False, "engineering answer was empty -- not captured"
    if _looks_like_contract_echo(low):
        return False, "engineering answer restated the answer contract -- not captured"
    if "proof:" not in low:
        return False, "engineering answer carried no Proof: line -- not captured"
    if not _engineering_cites_real_artifact(reply, prompt):
        cited = _cited_py_tokens(reply)
        if not cited:
            return False, "engineering answer cited no verifier or receipt at all -- not captured"
        if any(_artifact_exists(rel) for rel in cited):
            # A real file, but not one this card handed it: the laundering shape.
            return False, "engineering answer cited a real file the prompt did not supply -- not captured"
        return False, "engineering answer cited a file that does not exist -- not captured"
    fabricated = _fabricated_artifact_citations(reply)
    if fabricated:
        named = ", ".join(fabricated[:3])
        return False, (
            "engineering answer paired a real citation with a fabricated one "
            f"({named}) -- not captured"
        )
    invented = _invented_function_claims(reply)
    if invented:
        return False, (
            "engineering answer asserted a function Engel does not define "
            f"({', '.join(invented[:3])}) -- not captured"
        )
    unverifiable = _unsupplied_figure_claims(reply, prompt)
    if unverifiable:
        return False, (
            "engineering answer asserted a figure nothing supplied "
            f"({', '.join(unverifiable[:3])}) -- not captured"
        )
    return True, "engineering answer cites a real, existing verifier/receipt"


# --- Communication discipline gate (2026-08-01) --------------------------------
# Math and engineering grade an answer's CONTENT (is the number independently checked, is
# the claim tied to a real artifact). This discipline has to grade its FORM as well,
# because a communication sample that is admitted here becomes SFT TARGET TEXT for Engel's
# chat voice: whatever shape passes is the shape Engel learns to answer Joshua in. So the
# scaffolding that is a virtue in the other two lanes (Result:/Proof: labels, headings,
# bullet dumps) is a hard reject here, and so is the assistant-bot register a general
# base model drifts into when it has nothing real to say.
_COMMUNICATION_MIN_CHARS = 200
# Brevity floor (2026-08-05). The 200-char floor exists to keep "Got it." out of the voice
# corpus, but this curriculum DEMANDS brevity in several prompts -- "Keep the reply the size
# of the question", "one line that owns it and one concrete next step", "Ask me the one
# question". A model that obeyed those was rejected for obeying them: the 20260803 smoke
# admitted 0 of 3 at 147/194/147 characters, so the whole curriculum yielded nothing. When
# the PROMPT asks for a short reply, the floor drops to this instead -- still well above a
# bare acknowledgement, and every other voice check (no headings, no labels, no bullets,
# no bot filler) still applies unchanged.
_COMMUNICATION_BRIEF_MIN_CHARS = 90
_COMMUNICATION_BREVITY_REQUEST = re.compile(
    r"(?:\bkeep it (?:short|brief|quick|tight)\b"
    r"|\bkeep the reply the size of the question\b"
    r"|\bi want it quick\b|\bquick one\b"
    r"|\bone line\b|\bin a clause\b|\bname the decision in a clause\b"
    r"|\bthe one question\b"
    r"|\bin a few sentences\b)",
    re.IGNORECASE,
)
_COMMUNICATION_MAX_CHARS = 3500
_COMMUNICATION_BULLET_LINE_RATIO = 0.40
_MARKDOWN_HEADER_LINE = re.compile(r"^\s{0,3}#{1,6}\s", re.MULTILINE)
# Labels are matched LINE-LEADING, deliberately: "I still need to check: the pump curve"
# is ordinary speech, while a line that STARTS with "Check:" is a form being filled in.
# A bullet or bold wrapper is stripped first because a model told to drop labels usually
# just re-dresses them ("- **Result:** ..."). "evidence ledger" is matched anywhere -- it
# is AEC contract vocabulary with no natural home in chat prose.
_COMMUNICATION_LABEL_LINE = re.compile(
    r"^\s{0,3}(?:[-*•]\s*)?(?:\*{1,2}|_{1,2})?"
    r"(?:result|work|check|proof|confirmed|still open|unverified)"
    r"(?:\*{1,2}|_{1,2})?\s*:",
    re.IGNORECASE | re.MULTILINE,
)
_COMMUNICATION_LEDGER_PHRASE = "evidence ledger"
_COMMUNICATION_BULLET_LINE = re.compile(r"^\s{0,3}(?:[-*•]\s|\d{1,2}[.)]\s)")
_COMMUNICATION_BOT_FILLER = (
    "how can i assist",
    "i'm here to help",
    "as an ai",
    "language model",
    "let me know if you need anything else",
    "feel free to ask",
)
_COMMUNICATION_NOT_ENGEL = (
    "only engelz can use engel tools",
    "only engelz can run admin",
    "diagnostics from discord",
    "i can chat here, but only engelz",
    "guest chat gate",
    "still on the last thought",
    "send that once more",
    "what should we work on next",
    "i am here with you",
    "did not pass engel's style/quality gate",
    "rejected by style gate",
)
_COMMUNICATION_BOT_OPENERS = ("sure,", "certainly,", "of course,", "great question")
# Provenance narration (2026-08-11). The 7h fellow run served all 70 turns on the
# local ROG GPU (selected_provider=local, local_only_training=True on every row),
# yet 12 replies opened by announcing "ChatGPT lane is active for this turn" -- and
# 5 of those were ADMITTED, because nothing here graded whether a reply lies about
# who answered it. Admitted communication rows become SFT target text, so those 5
# would have taught Engel to narrate a false provider on every turn.
#
# Scoped to SELF-ATTRIBUTED routing ("X lane is active", "answered by X", "I am X",
# a provider named "for this turn"), not to any mention of a provider: "I would
# hand that to ChatGPT if you asked" and "the ChatGPT bridge is down" stay legal.
# Engel narrating its own routing is not chat voice in this curriculum either way.
_COMMUNICATION_PROVIDER_NAMES = (
    r"(?:chatgpt|openai|claude|anthropic|grok|xai|gemini|copilot|deepseek|codex)"
)
_COMMUNICATION_FALSE_PROVENANCE = re.compile(
    rf"\b{_COMMUNICATION_PROVIDER_NAMES}\b[^.\n]{{0,40}}?\b(?:is|was|'s)\s+"
    rf"(?:the\s+|now\s+|currently\s+)*"
    rf"(?:active|serving|handling|answering|responding|routing|selected)\b"
    rf"|\b{_COMMUNICATION_PROVIDER_NAMES}\b[^.\n]{{0,40}}?\bfor this turn\b"
    rf"|\b(?:answered|served|handled|generated|written|routed)\s+by\s+"
    rf"{_COMMUNICATION_PROVIDER_NAMES}\b"
    rf"|\bi\s+(?:am|'m)\s+(?:the\s+)?{_COMMUNICATION_PROVIDER_NAMES}\b",
    re.IGNORECASE,
)
# Word-boundary matched: a bare "my " substring test also fires inside "enemy ", handing a
# voiceless answer a first-person pass it did not earn.
_COMMUNICATION_FIRST_PERSON = re.compile(r"\b(?:i|i'm|i am|i'll|my)\b", re.IGNORECASE)
_COMMUNICATION_SENTENCE_SPLIT = re.compile(r"[.!?]+(?:\s|$)")

_STYLE_GRADER_UNRESOLVED = object()
_STYLE_GRADER: Any = _STYLE_GRADER_UNRESOLVED


def _reply_style_grader() -> Any:
    """Resolve the REAL served style grader once, or None when it cannot be imported.

    The chat lane grades its own replies with reply_passes_style, so reusing that exact
    function keeps the training-admission bar and the serving bar the same object rather
    than two copies that drift. It is optional by design: that module is heavy and is
    absent in some environments (verifier sandboxes, CT-side reruns), and per the
    instrumentation rule a missing OPTIONAL grader must not fail the gate -- the local
    form checks below are the mandatory part and stay fail-closed on their own.
    """
    global _STYLE_GRADER
    if _STYLE_GRADER is _STYLE_GRADER_UNRESOLVED:
        try:
            from run_engel_standalone_chat_llm import reply_passes_style

            _STYLE_GRADER = reply_passes_style
        except Exception:  # noqa: BLE001 -- optional grader, never fatal
            _STYLE_GRADER = None
    return _STYLE_GRADER


def _communication_answer_is_conversational(
    reply: str, base_prompt: str = ""
) -> tuple[bool, str]:
    """(ok, reason) for a communication-discipline answer: does this read like Engel talking?

    Returns the FIRST failing condition as the reason, so a rejected sample says exactly
    which habit it was rejected for and the curriculum can be corrected. ``base_prompt`` is
    optional only because the served style grader is optional; every mandatory check reads
    the reply alone.
    """
    text = str(reply or "")
    stripped = text.strip()
    low = " ".join(stripped.split()).casefold()
    if not stripped:
        return False, "reply was empty"
    for phrase in _COMMUNICATION_NOT_ENGEL:
        if phrase in low:
            return (
                False,
                "reply is a Discord-mouth or stall card, not Engel AI Main "
                f"({phrase!r})",
            )
    if _looks_like_contract_echo(low):
        return False, "reply restates the answer contract instead of answering"
    provenance = _COMMUNICATION_FALSE_PROVENANCE.search(stripped)
    if provenance:
        return (
            False,
            "reply narrates which provider served the turn "
            f"({provenance.group(0).strip()!r}); Engel answers as itself and these "
            "turns are served locally",
        )
    brevity_asked = bool(_COMMUNICATION_BREVITY_REQUEST.search(str(base_prompt or "")))
    floor = _COMMUNICATION_BRIEF_MIN_CHARS if brevity_asked else _COMMUNICATION_MIN_CHARS
    if len(stripped) < floor:
        return (
            False,
            f"reply is {len(stripped)} characters; a chat-voice sample needs at least "
            f"{floor}"
            + (" (the prompt asked for a short reply)" if brevity_asked else ""),
        )
    if len(stripped) > _COMMUNICATION_MAX_CHARS:
        return (
            False,
            f"reply is {len(stripped)} characters, past the {_COMMUNICATION_MAX_CHARS} "
            "chat-voice ceiling",
        )
    if _MARKDOWN_HEADER_LINE.search(text):
        return False, "reply uses a markdown heading; Engel's chat voice does not"
    if "```" in text:
        return False, "reply contains a code fence"
    labelled = _COMMUNICATION_LABEL_LINE.search(text)
    if labelled:
        return (
            False,
            f"reply uses labelled scaffolding ({labelled.group(0).strip()!r}) instead of prose",
        )
    if _COMMUNICATION_LEDGER_PHRASE in low:
        return False, "reply carries evidence-ledger vocabulary instead of chat prose"
    lines = [line for line in text.splitlines() if line.strip()]
    bulleted = sum(1 for line in lines if _COMMUNICATION_BULLET_LINE.match(line))
    if lines and bulleted > _COMMUNICATION_BULLET_LINE_RATIO * len(lines):
        return (
            False,
            f"{bulleted} of {len(lines)} non-empty lines are bullets or numbered items; "
            "that is a list, not chat prose",
        )
    for phrase in _COMMUNICATION_BOT_FILLER:
        if phrase in low:
            return False, f"reply carries assistant-bot filler ({phrase!r})"
    for opener in _COMMUNICATION_BOT_OPENERS:
        if low.startswith(opener):
            return False, f"reply opens with assistant-bot filler ({opener!r})"
    sentences = [
        part for part in _COMMUNICATION_SENTENCE_SPLIT.split(stripped) if part.strip()
    ]
    if len(sentences) < 2:
        return False, "reply is fewer than two sentences"
    if not _COMMUNICATION_FIRST_PERSON.search(stripped):
        return False, "reply has no first-person marker; Engel speaks as itself"
    grader = _reply_style_grader()
    if grader is None:
        return (
            True,
            "reply reads as Engel's own first-person chat prose (served style grader "
            "unavailable here; local form checks only)",
        )
    try:
        verdict = grader(str(base_prompt or ""), stripped)
    except Exception as exc:  # noqa: BLE001 -- optional grader, never fatal
        return (
            True,
            "reply reads as Engel's own first-person chat prose (served style grader "
            f"raised {type(exc).__name__}; local form checks only)",
        )
    if isinstance(verdict, dict) and verdict.get("ok") is False:
        checks = verdict.get("checks") if isinstance(verdict.get("checks"), dict) else {}
        failing = ", ".join(sorted(name for name, ok in checks.items() if ok is False))
        return (
            False,
            "served style gate (reply_passes_style) rejected the reply"
            + (f": {failing}" if failing else ""),
        )
    return (
        True,
        "reply reads as Engel's own first-person chat prose and passes the served style gate",
    )


def _wrapper_reply_text(result: dict[str, Any]) -> str:
    """Return the assistant reply for a turn. The wrapper dict the runner holds is a
    SUMMARY without the reply text; the full chat receipt (with assistant_reply) lives at
    the path the wrapper points to, so read it when the inline field is absent."""
    wrapper = result.get("wrapper_receipt") or {}
    inline = wrapper.get("assistant_reply") or wrapper.get("assistant_output_text")
    if inline:
        return str(inline)
    path = result.get("wrapper_receipt_path") or wrapper.get("path")
    if path:
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, ValueError):
            return ""
        if isinstance(data, dict):
            return str(
                data.get("assistant_reply") or data.get("assistant_output_text") or ""
            )
    return ""


def _apply_discipline_eligibility(
    result: dict[str, Any], discipline: str
) -> dict[str, Any]:
    """Set training eligibility for non-AEC disciplines by DERIVING it from the turn's own
    quality, not the server flag. Specialist lanes (sparse-MoE, deep local) serve clean
    answers but do not stamp training_sample_eligible, so a downgrade-only rule would drop
    good samples; deriving it lets a served (status DONE) answer that meets the domain bar
    count, while an echo / unverified answer / non-DONE turn does not. AEC is admitted
    only when its cited claim is supported by local corpus evidence."""
    discipline = str(discipline or "aec").strip().casefold()
    result["discipline"] = discipline
    if discipline not in ("math", "engineering", "communication"):
        # A section identifier existing somewhere in a code book is not proof that the
        # sentence beside it is true. A previous run admitted claims under unrelated real
        # ids. AEC therefore fails closed for training: absent, unresolved, and unsupported
        # citations remain visible evidence but never positive examples.
        if discipline == "aec":
            # (2026-08-14) Grade the citation only for SERVED turns, mirroring the
            # status-DONE check the other disciplines apply below. A transport-failed
            # turn has an empty reply, and grading it produced phantom "no explicit
            # Section citations to check" rejections (5 of 33 on 2026-08-14) that
            # inflated the citation-failure rate and polluted the weakness miner's
            # signal. The failed turn stays ineligible either way - the reason is
            # just honest now.
            if result.get("status") != "DONE":
                result["aec_citation_verdict"] = "unserved"
                result["aec_exactly_verified"] = False
                result["training_sample_eligible"] = False
                result["discipline_eligibility_ok"] = False
                result["discipline_eligibility_reason"] = (
                    "turn was not served (transport/delivery failure); "
                    "citation quality was not judged"
                )
                return result
            aec_truth = _aec_citation_truth(
                _wrapper_reply_text(result),
                str(result.get("base_prompt") or result.get("prompt") or ""),
                expected_documents=result.get("aec_expected_documents"),
            )
            result["aec_citation_verdict"] = aec_truth.get("verdict")
            result["aec_exactly_verified"] = bool(aec_truth.get("exactly_verified"))
            result["aec_claim_support_verified"] = bool(
                aec_truth.get("claim_support_verified")
            )
            result["aec_document_scope"] = list(
                aec_truth.get("document_scope") or []
            )
            result["aec_support"] = list(aec_truth.get("support") or [])
            result["aec_corpus_bundle_sha256"] = str(
                aec_truth.get("corpus_bundle_sha256") or ""
            )
            if aec_truth.get("exactly_verified") is not True:
                wrapper = result.get("wrapper_receipt") or {}
                semantic = wrapper.get("local_semantic_quality")
                server_ok = (
                    wrapper.get("training_sample_eligible") is True
                    and isinstance(semantic, dict)
                    and semantic.get("ok") is True
                )
                if server_ok:
                    result["training_sample_eligible"] = True
                    result["discipline_eligibility_ok"] = True
                    result["discipline_eligibility_reason"] = (
                        "CT246 semantic gate accepted this local reply "
                        f"({aec_truth.get('detail', '')})"
                    )
                else:
                    result["training_sample_eligible"] = False
                    result["discipline_eligibility_ok"] = False
                    result["discipline_eligibility_reason"] = (
                        "aec claim was not supported by evidence beside its cited section -- "
                        f"{aec_truth.get('detail', '')}"
                    )
        return result
    reply = _wrapper_reply_text(result)
    # status DONE => the turn was served cleanly (wrapper.ok True, chat_only); a gate-blocked
    # or transport-failed turn is not DONE and is never eligible.
    served = result.get("status") == "DONE"
    # A training sample must be LOCAL. Deriving eligibility could otherwise UPGRADE a turn
    # that escalated to an external provider/bridge (e.g. a non-local run where the CLI/UI
    # did not pass --local-only), which must never be captured as a local self-training
    # sample. Never count a provider/bridge/API turn regardless of answer shape.
    local_only_turn = (
        result.get("provider_bridge_used") is not True
        and result.get("provider_api_enabled") is not True
    )
    if discipline == "math":
        # Ground truth first, when the prompt is a declared problem. Form grading can only
        # ask "does this answer check itself"; a known answer can ask "is it RIGHT". A
        # problem the set does not know, or one with no decidable answer (a proof), falls
        # through to form grading and is recorded as such -- see math_truth_verdict below,
        # which lets training weight exactly-verified rows apart from form-graded ones.
        truth = _math_truth_grade(reply, str(result.get("base_prompt") or ""))
        result["math_truth_verdict"] = truth.get("verdict")
        result["math_exactly_verified"] = bool(truth.get("exactly_verified"))
        if truth.get("problem_id"):
            result["math_problem_id"] = truth["problem_id"]
        ok = served and local_only_turn and _math_answer_shows_verification(reply)
        if ok and truth.get("wrong"):
            # Proven wrong against a known answer. Form was satisfied; the mathematics was
            # not, and that is exactly the row that must never become training data.
            ok = False
            result["discipline_eligibility_ok"] = False
            result["training_sample_eligible"] = False
            result["discipline_eligibility_reason"] = (
                f"math answer contradicts the known result -- {truth.get('detail', '')}"
            )
            return result
        reason = (
            (
                "math answer matches the known result"
                if truth.get("exactly_verified")
                else "math answer shows a concrete CAS-consistent independent Check"
            )
            if ok
            else (
                "math turn used a non-local provider -- not captured"
                if served and not local_only_turn
                else "math answer was an echo / unverified / CAS-refuted -- not captured"
            )
        )
    elif discipline == "communication":
        # The voice lane keeps its own reason text verbatim: unlike math/engineering, a
        # rejection here is a report on WHICH habit the answer drifted into, and that
        # wording is what makes the curriculum correctable instead of just "not captured".
        voice_ok, voice_reason = _communication_answer_is_conversational(
            reply, str(result.get("base_prompt") or "")
        )
        ok = served and local_only_turn and voice_ok
        reason = (
            voice_reason
            if ok
            else (
                "communication turn used a non-local provider -- not captured"
                if served and not local_only_turn
                else voice_reason
                if served
                else "communication turn was not served cleanly -- not captured"
            )
        )
    else:
        grounded, grounded_reason = _engineering_answer_is_grounded(
            reply, str(result.get("base_prompt") or "")
        )
        # (2026-08-07) CODE IS EXECUTED, not admired. Form grading passed any fenced
        # block with the right names -- the exact "verification-shaped prose" failure the
        # math gate had, transplanted to programming. A labelled Python block whose own
        # program provably breaks (won't parse when complete, or its own asserts fail in
        # the sandbox) loses the row; other languages / fragments / gated code stay
        # form-graded as undecidable, and self-proving code is stamped exactly-verified
        # so the corpus can weight it, mirroring math_truth_verdict.
        code_truth = _code_answer_truth(reply)
        result["code_truth_verdict"] = code_truth.get("verdict")
        result["code_exactly_verified"] = bool(code_truth.get("exactly_verified"))
        code_refuted = bool(code_truth.get("refuted"))
        ok = served and local_only_turn and grounded and not code_refuted
        reason = (
            (
                "engineering answer carries self-proving code (sandbox-verified) -- "
                + grounded_reason
                if code_truth.get("exactly_verified")
                else grounded_reason
            )
            if ok
            else (
                f"code answer's own program fails when run -- {code_truth.get('detail', '')}"
                if served and local_only_turn and grounded and code_refuted
                else "engineering turn used a non-local provider -- not captured"
                if served and not local_only_turn
                else grounded_reason
                if served
                else "engineering turn was not served cleanly -- not captured"
            )
        )
    result["discipline_eligibility_ok"] = bool(ok)
    result["discipline_eligibility_reason"] = reason
    result["training_sample_eligible"] = bool(ok)
    return result


GOVERNOR_DECISIONS_PATH = ROOT / "reports" / "governor" / "governor_decisions.jsonl"


def _record_governor_decision(result: dict[str, Any], discipline: str) -> None:
    """Phase A instrumentation (design spec section 5): append one
    governor_decision record per training turn, joining the admit features and
    T0 verdict with the turn's OBSERVED outcome. These receipts are the corpus
    Phases B-E (train/shadow/promote a Governor SLM) are gated on -- inventing
    labels instead produced the failure_triage rejection. The admit verdict runs
    SHADOW here: the legacy eligibility decision stays authoritative, and any
    disagreement is recorded, never silently absorbed. Instrumentation must
    never break a run, hence the blanket except."""
    try:
        import engel_governor as gov

        reply = _wrapper_reply_text(result)
        low = " ".join(str(reply or "").split()).casefold()
        discipline = str(discipline or "aec").strip().casefold()
        features = {
            "discipline": discipline,
            "served": result.get("status") == "DONE",
            "local_only_turn": (
                result.get("provider_bridge_used") is not True
                and result.get("provider_api_enabled") is not True
            ),
            "contract_echo": _looks_like_contract_echo(low),
            "has_result": "result:" in low or "no verified result" in low,
            "has_check": "check:" in low,
            "has_independent_signal": any(sig in low for sig in _MATH_VERIFICATION_SIGNALS),
            "has_concrete_relation": bool(_MATH_CONCRETE.search(low)) or "no verified result" in low,
            "cas_refuted": (
                _math_check_has_false_relation(reply) if discipline == "math" else False
            ),
            "proof_present": "proof:" in low,
            "cites_real_artifact": (
                _engineering_cites_real_artifact(reply, str(result.get("base_prompt") or ""))
                if discipline == "engineering"
                else False
            ),
            # (2026-08-01) The voice lane's own admit signal. Without it the Phase A
            # corpus would record communication turns with an all-False feature row and
            # the eventual Governor SLM could never learn why any of them were admitted.
            "conversational_voice_ok": (
                _communication_answer_is_conversational(
                    reply, str(result.get("base_prompt") or "")
                )[0]
                if discipline == "communication"
                else False
            ),
            "server_flag_eligible": result.get("training_sample_eligible") is True,
        }
        verdict = gov.govern("admit", features)
        legacy_admitted = result.get("training_sample_eligible") is True
        record = gov.decision_receipt(
            verdict,
            features=features,
            outcome_observed={
                "status": result.get("status"),
                "admitted": legacy_admitted,
                "admitted_reason": result.get("discipline_eligibility_reason"),
                "selected_provider": (result.get("wrapper_receipt") or {}).get(
                    "selected_provider"
                ),
                "governor_admit_agrees": (verdict.get("outcome") is True) == legacy_admitted,
            },
        )
        record["created_at_utc"] = iso_now()
        record["run_kind"] = "ui_prompt_training"
        GOVERNOR_DECISIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with GOVERNOR_DECISIONS_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
    except Exception:  # noqa: BLE001 -- instrumentation never breaks a run
        pass


# Paced early-stop: a run should not burn its whole time budget on a systemically
# broken pipeline, but a single delivered-then-refused turn must NOT abort the rest of
# the schedule (the old behavior: first non-DONE turn killed the run).
_MAX_CONSECUTIVE_DELIVERY_FAILURES = 5
_MAX_CONSECUTIVE_NONDONE = 5


def _is_delivery_failure(result: dict[str, Any]) -> bool:
    """A genuine delivery/transport failure: a non-DONE turn that never completed a chat
    turn (no wrapper receipt, or the chat lane was never used), as opposed to a turn that
    WAS delivered and then refused on content/quality. A produced wrapper receipt with the
    chat lane used means the turn reached the model and came back; it is NOT a delivery
    failure even if the visible app's fresh-result diagnostic arrived late (that late
    diagnostic forces status FAIL but the turn was served), so the diagnostic timing is
    deliberately NOT part of this test -- otherwise two slow-but-served turns would stop a
    working paced run early."""
    if result.get("status") == "DONE":
        return False
    wrapper = result.get("wrapper_receipt") or {}
    delivered = bool(
        result.get("wrapper_receipt_path")
        and wrapper.get("main_server_chat_used") is True
    )
    return not delivered


def _chat_backend_healthy(timeout_seconds: float = 10.0) -> bool:
    """True when the app-path chat backend answers its health endpoint.

    Probes the ROG-side tunnel port the app itself rides (24680 -> CT 8765), so
    'healthy' here means the SAME path a delivered prompt would take."""
    import urllib.request

    url = os.environ.get(
        "ENGEL_TRAINING_CHAT_HEALTH_URL", "http://127.0.0.1:24680/health"
    )
    try:
        with urllib.request.urlopen(url, timeout=timeout_seconds) as response:
            return bool(response.status == 200)
    except Exception:  # noqa: BLE001 - unreachable IS the answer
        return False


def _wait_out_chat_outage(deadline: float, max_wait_seconds: int) -> dict[str, Any]:
    """Bounded wait for the chat backend to come back before spending a retry.

    (2026-08-16) An unreachable backend is an OUTAGE, not a turn defect: prompts
    68/69 of the 20260816T0111Z scheduled run burned inside a ~15-minute
    "Chat unavailable" window (the prompt never left the app's input box, zero CT
    receipts) and the 2-failure streak ended an 8-hour schedule 11 prompts early,
    while the 45s retry backoff could never outlast the window. Budget-aware:
    always leaves >=180s of wall budget so the wait cannot eat the plan's tail."""
    started = time.monotonic()
    if _chat_backend_healthy():
        return {"outage_detected": False, "waited_seconds": 0, "healthy_after_wait": True}
    while True:
        waited = time.monotonic() - started
        budget_left = deadline - time.monotonic()
        if waited >= max_wait_seconds or budget_left <= 180 + 30:
            return {
                "outage_detected": True,
                "waited_seconds": int(waited),
                "healthy_after_wait": False,
            }
        time.sleep(30)
        if _chat_backend_healthy():
            return {
                "outage_detected": True,
                "waited_seconds": int(time.monotonic() - started),
                "healthy_after_wait": True,
            }


def _is_style_gate_exhaust(result: dict[str, Any]) -> bool:
    """A turn that WAS delivered but the service served its style-gate failure
    explainer instead of an answer ("local reply rejected by style gate") - the one
    served-failure class that is pure generation nondeterminism, so one bounded
    re-ask of the SAME position usually lands (live 2026-08-16: 4 of 45 scheduled
    turns burned this way, ~9%, two of them back-to-back). Every other content
    refusal stays FAIL - re-asking those would just re-serve the same refusal."""
    if result.get("status") == "DONE":
        return False
    wrapper = result.get("wrapper_receipt") or {}
    status_text = " ".join(
        str(part or "")
        for part in (
            wrapper.get("status"),
            str(wrapper.get("assistant_reply") or "")[:220],
        )
    ).casefold()
    return (
        "rejected by style gate" in status_text
        or "did not pass engel's style/quality gate" in status_text
        or "quality gate blocked" in status_text
    )


def _verify_chat_grounding() -> dict[str, Any]:
    """Run the grounding gate. CREATE_NO_WINDOW: a console here would flash a
    terminal over the operator's desktop on every run."""
    tool = ROOT / "tools" / "verify_engel_chat_grounding.py"
    if not tool.is_file():
        return {"ok": False, "detail": f"missing gate tool {tool}"}
    try:
        completed = subprocess.run(
            [sys.executable, str(tool)],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "detail": f"{type(exc).__name__}: {exc}"}
    output = f"{completed.stdout}\n{completed.stderr}".strip()
    failed = [line.strip() for line in output.splitlines() if line.startswith("FAIL ")]
    return {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "detail": "; ".join(failed) or output[-400:],
    }


def _deliver_prompt(
    prompt: str, metadata: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Hand the prompt to Engel so it types it into its own visible Chat composer.

    Returns the app's acceptance receipt. Waiting only for ACCEPTANCE (the prompt
    is in the composer and submitted) keeps the existing receipt-based completion
    checks intact, while turning "the UI never received my text" into a failure
    reported in seconds instead of a silent full-length per-prompt timeout.

    ``metadata`` rides the request so the service knows "this is a training turn
    of discipline X" (routing + memory hygiene). It is an additive field: app
    builds that predate it read only ``prompt`` and ignore it safely, and the
    service clamps it through engel_governor.clamp_inbox_metadata (narrow-only).
    """
    UI_CHAT_INBOX_REQUEST_DIR.mkdir(parents=True, exist_ok=True)
    UI_CHAT_INBOX_RESULT_DIR.mkdir(parents=True, exist_ok=True)
    unique = hashlib.sha1(
        f"{prompt}{time.time()}{os.getpid()}".encode("utf-8")
    ).hexdigest()[:8]
    request_id = f"train_{stamp()}_p{os.getpid()}_{unique}"
    result_path = UI_CHAT_INBOX_RESULT_DIR / f"{request_id}.json"
    payload = {
        "schema": "engel_ui_chat_inbox_request_v1",
        "request_id": request_id,
        "prompt": prompt,
        "created_at_utc": iso_now(),
    }
    if isinstance(metadata, dict) and metadata:
        payload["metadata"] = metadata
    temp_path = UI_CHAT_INBOX_REQUEST_DIR / f"{request_id}.json.tmp"
    temp_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    # Publish atomically so the app can never read a half-written request.
    temp_path.replace(UI_CHAT_INBOX_REQUEST_DIR / f"{request_id}.json")
    deadline = time.time() + UI_CHAT_INBOX_ACCEPT_TIMEOUT
    while time.time() < deadline:
        if result_path.is_file():
            try:
                record = json.loads(result_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                time.sleep(0.3)
                continue
            if record.get("accepted") is True:
                return record
            return {
                "ok": False,
                "accepted": False,
                "request_id": request_id,
                "status": record.get("status") or "app rejected the prompt",
            }
        time.sleep(0.3)
    return {
        "ok": False,
        "accepted": False,
        "request_id": request_id,
        "status": (
            "Engel AI Main did not pick the prompt up from the chat inbox within "
            f"{UI_CHAT_INBOX_ACCEPT_TIMEOUT:g}s (is the app running this build?)"
        ),
    }


def _inbox_turn_finished(result_path: Path) -> dict[str, Any]:
    """The app's own 'this chat turn is over' signal for a delivered prompt.

    Returns the result record once it reports ``completed``, else an empty dict.
    This is a machine-readable field the app already writes -- deliberately NOT a
    scan of the reply text, because training prompts legitimately DISCUSS action
    plans and confirm gates, and a text match would fail those real turns.
    """
    if not result_path.name or not result_path.is_file():
        return {}
    try:
        record = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(record, dict) or record.get("completed") is not True:
        return {}
    return record


def _type_text_with_forms(hwnd: int, text: str) -> None:
    """RETIRED 2026-07-29 — kept as a reference fallback, deliberately not called.

    Focuses the Flutter composer, atomically pastes the full prompt, and submits once.
    The atomic paste did fix dropped prompt prefixes, but the approach itself cannot be
    made reliable: it needs the real cursor and synthetic keystrokes, Windows refuses
    SetForegroundWindow to a background process, and any operator activity sent the
    prompt to whatever window held focus (typing training prompts into an open editor)
    while the run waited out its full per-prompt timeout. Prompts now go through
    `_deliver_prompt` -> the app's chat inbox, so Engel types into its OWN composer.
    Do not re-wire this into the delivery path.
    """
    encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
    ps = f"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
$code = @'
using System;
using System.Runtime.InteropServices;
public class FlutterInputCtl {{
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int X, int Y);
  [DllImport("user32.dll")] public static extern void mouse_event(int dwFlags, int dx, int dy, int dwData, int dwExtraInfo);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
  [StructLayout(LayoutKind.Sequential)] public struct RECT {{ public int Left; public int Top; public int Right; public int Bottom; }}
}}
'@
Add-Type $code
$raw = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String('{encoded}'))
Set-Clipboard -Value $raw
$hwnd = [IntPtr]{hwnd}
[FlutterInputCtl]::ShowWindow($hwnd, 9) | Out-Null
[FlutterInputCtl]::SetForegroundWindow($hwnd) | Out-Null
Start-Sleep -Milliseconds 300
$r = New-Object FlutterInputCtl+RECT
[FlutterInputCtl]::GetWindowRect($hwnd, [ref]$r) | Out-Null
[FlutterInputCtl]::SetCursorPos($r.Left + 742, $r.Top + 824) | Out-Null
[FlutterInputCtl]::mouse_event(2,0,0,0,0)
Start-Sleep -Milliseconds 50
[FlutterInputCtl]::mouse_event(4,0,0,0,0)
Start-Sleep -Milliseconds 200
[System.Windows.Forms.SendKeys]::SendWait('^a')
Start-Sleep -Milliseconds 100
[System.Windows.Forms.SendKeys]::SendWait('^v')
Start-Sleep -Milliseconds 300
[System.Windows.Forms.SendKeys]::SendWait('{{ENTER}}')
Start-Sleep -Milliseconds 300
"""
    completed = subprocess.run(
        ["powershell", "-STA", "-NoProfile", "-Command", ps],
        capture_output=True,
        text=True,
        timeout=60,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if completed.returncode != 0:
        raise RuntimeError(f"atomic clipboard submission failed: {completed.stderr.strip()}")


def capture_window(hwnd: int, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    ps = f"""
$code = @'
using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;
public class FlutterTrainingShot {{
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
  [StructLayout(LayoutKind.Sequential)] public struct RECT {{ public int Left; public int Top; public int Right; public int Bottom; }}
  public static string Capture(IntPtr hWnd, string path) {{
    RECT r; GetWindowRect(hWnd, out r);
    int w = Math.Max(1, r.Right - r.Left); int h = Math.Max(1, r.Bottom - r.Top);
    using (Bitmap bmp = new Bitmap(w, h)) {{
      using (Graphics g = Graphics.FromImage(bmp)) {{ g.CopyFromScreen(r.Left, r.Top, 0, 0, new Size(w, h)); }}
      bmp.Save(path, ImageFormat.Png);
    }}
    return String.Format("{{0}},{{1}},{{2}},{{3}}", r.Left, r.Top, r.Right, r.Bottom);
  }}
}}
'@
Add-Type -ReferencedAssemblies @('System.Drawing.dll') -TypeDefinition $code
[FlutterTrainingShot]::Capture([IntPtr]{hwnd}, '{str(path)}')
"""
    completed = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=20, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return completed.stdout.strip()


def _summarize_order(path: Path) -> dict[str, Any]:
    payload = _load_json(path)
    payload = payload if isinstance(payload, dict) else {}
    return {
        "path": str(path),
        "order_id": payload.get("order_id"),
        "source": payload.get("source"),
        "job_type": payload.get("job_type"),
        "station_routes": payload.get("station_routes"),
        "station_details": payload.get("station_details"),
        "station_results": payload.get("station_results"),
        "returned_previews": payload.get("returned_previews"),
        "collaboration_dialogue_count": len(payload.get("collaboration_dialogue") or []),
    }


def _summarize_wrapper(path: Path) -> dict[str, Any]:
    payload = _load_json(path)
    payload = payload if isinstance(payload, dict) else {}
    return {
        "path": str(path),
        "ok": payload.get("ok"),
        "status": payload.get("status"),
        "creation_job": payload.get("creation_job"),
        "chat_only_no_android_or_sub_engel": payload.get("chat_only_no_android_or_sub_engel"),
        "meeting_room_order_id": payload.get("meeting_room_order_id"),
        "agent_meeting_room_used": payload.get("agent_meeting_room_used"),
        "meeting_room_server_used": payload.get("meeting_room_server_used"),
        "phone_work_requested": payload.get("phone_work_requested"),
        "phone_work_assigned": payload.get("phone_work_assigned"),
        "phone_work_returned_count": payload.get("phone_work_returned_count"),
        "sub_engel_work_requested": payload.get("sub_engel_work_requested"),
        "sub_engel_work_assigned": payload.get("sub_engel_work_assigned"),
        "sub_engel_work_returned": payload.get("sub_engel_work_returned"),
        "local_llm_only": payload.get("local_llm_only"),
        "workspace_receipt_path": payload.get("workspace_receipt_path"),
        "build_lane_used": payload.get("build_lane_used"),
        "expected_build_lane": payload.get("expected_build_lane"),
        "build_artifact_verified": payload.get("build_artifact_verified"),
        "workspace_path": payload.get("workspace_path"),
        "workspace_files": payload.get("workspace_files"),
        "workspace_created": payload.get("workspace_created"),
        "workspace_run_ran": payload.get("workspace_run_ran"),
        "workspace_run_exit_code": payload.get("workspace_run_exit_code"),
        "workspace_run_output": payload.get("workspace_run_output"),
        "runtime_provider": payload.get("runtime_provider"),
        "selected_provider": payload.get("selected_provider") or payload.get("runtime_provider"),
        "requested_provider": payload.get("requested_provider"),
        "provider_api_enabled": payload.get("provider_api_enabled"),
        "local_only_training": payload.get("local_only_training"),
        "provider_fallback_allowed": payload.get("provider_fallback_allowed"),
        "provider_pipeline_used": payload.get("provider_pipeline_used"),
        "provider_bridge_fallback_attempted": payload.get(
            "provider_bridge_fallback_attempted"
        ),
        "training_sample_eligible": payload.get("training_sample_eligible"),
        "local_semantic_quality": payload.get("local_semantic_quality"),
        "network_enabled": payload.get("network_enabled"),
        "humanizer_voice_rules_active": payload.get("humanizer_voice_rules_active"),
        "persistent_chat_memory_appended": payload.get("persistent_chat_memory_appended"),
        "ct_prompt_match": payload.get("ct_prompt_match"),
        "ct_prompt_match_window": payload.get("ct_prompt_match_window"),
        "ui_reply_guard_triggered": payload.get("ui_reply_guard_triggered"),
        "standalone_guard_triggered": payload.get("standalone_guard_triggered"),
        "visible_reply_source": payload.get("visible_reply_source"),
        "latency_ms": payload.get("latency_ms"),
        "main_server_chat_used": payload.get("main_server_chat_used"),
        "main_server_chat_url": payload.get("main_server_chat_url"),
        "fast_server_fallback_used": payload.get("fast_server_fallback_used"),
        "server_request_latency_ms": payload.get("server_request_latency_ms"),
        "ui_meeting_room_receipt_path": payload.get("ui_meeting_room_receipt_path"),
        "build_lifecycle": payload.get("build_lifecycle"),
        "build_review": payload.get("build_review"),
        "build_package": payload.get("build_package"),
        "build_preview": payload.get("build_preview"),
        "build_verified": payload.get("build_verified"),
        "build_generation_routes": payload.get("build_generation_routes"),
        "build_standalone_first_attempted": payload.get("build_standalone_first_attempted"),
        "build_local_model_used": payload.get("build_local_model_used"),
        "build_attached_codex_used": payload.get("build_attached_codex_used"),
        "build_external_provider_api_used": payload.get("build_external_provider_api_used"),
        "provider_free_generation": payload.get("provider_free_generation"),
        "conical_orchestration": payload.get("conical_orchestration"),
        "conical_job_id": payload.get("conical_job_id"),
        "conical_job_status": payload.get("conical_job_status"),
        "conical_worker_returned_count": payload.get("conical_worker_returned_count"),
        "conical_worker_expected_count": payload.get("conical_worker_expected_count"),
        "conical_terminal_failure": payload.get("conical_terminal_failure"),
        "ct246_conical_receipt_path": payload.get("ct246_conical_receipt_path"),
        "ct246_conical_report_written": payload.get("ct246_conical_report_written"),
        "ct246_conical_memory_appended": payload.get("ct246_conical_memory_appended"),
        "ct246_conical_persistence_ok": payload.get("ct246_conical_persistence_ok"),
        "ct246_conical_persistence_error": payload.get("ct246_conical_persistence_error"),
    }


def _check_ct_persistent_chat_memory(
    prompt: str, since_epoch: float, base_prompt: str = ""
) -> dict[str, Any]:
    """Verify a recent CT chat record, tolerating only a bounded input-prefix loss.

    (2026-08-14) base_prompt matters: CT stores training turns base-substituted
    (memory hygiene), so when the byte-exact prompt_sha256 misses — live cause: the
    app->CT handoff mojibakes non-ASCII typography, so a CALDAG card with 6-inch
    marks hashed differently on the two sides — the fuzzy fallback comparing the
    LONG delivered text against the SHORT stored base can never match either. The
    base-vs-stored comparison is the one that actually corresponds.
    """
    target = os.environ.get("ENGEL_CT_SSH_TARGET", "").strip()
    if not target:
        host = os.environ.get("ENGEL_MAIN_SERVER_HOST", "192.0.2.50").strip()
        user = os.environ.get("ENGEL_MAIN_SERVER_USER", "root").strip() or "root"
        target = f"{user}@{host}" if host else ""
    if not target:
        return {"ok": False, "reason": "CT SSH target is not configured"}
    ssh = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8"]
    key = os.environ.get("ENGEL_CT_SSH_KEY", "").strip()
    if not key:
        default_key = Path.home() / ".ssh" / "engel_ai_main_ct246_ed25519"
        if default_key.is_file():
            key = str(default_key)
    if key:
        ssh.extend(["-i", key])
    port = os.environ.get(
        "ENGEL_CT_SSH_PORT",
        os.environ.get("ENGEL_MAIN_SERVER_SSH_PORT", "24622"),
    ).strip()
    if port:
        ssh.extend(["-p", port])
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    until_epoch = time.time() + 5.0
    remote_match_function = inspect.getsource(fuzzy_prompt_match)
    remote_py = f"""
from __future__ import annotations
import json, datetime
from pathlib import Path
from typing import Any
{remote_match_function}
path = Path({CT_CHAT_MEMORY_PATH!r})
prompt_hash = {prompt_hash!r}
prompt_text = {prompt!r}
base_prompt_text = {str(base_prompt or "")!r}
since_epoch = {since_epoch!r}
until_epoch = {until_epoch!r}
def parse_ts(value):
    if not value:
        return 0.0
    value = str(value).replace('Z', '+00:00')
    try:
        return datetime.datetime.fromisoformat(value).timestamp()
    except Exception:
        return 0.0
out = {{'ok': False, 'path': str(path), 'reason': 'not found'}}
if path.exists():
    for line in path.read_text(encoding='utf-8', errors='ignore').splitlines():
        try:
            rec = json.loads(line)
        except Exception:
            continue
        record_ts = rec.get('updated_at_utc') or rec.get('created_at_utc')
        record_epoch = parse_ts(record_ts)
        if record_epoch + 5 < since_epoch or record_epoch - 5 > until_epoch:
            continue
        record_prompt = str(rec.get('prompt') or '')
        hash_matched = rec.get('prompt_sha256') == prompt_hash
        prompt_match = fuzzy_prompt_match(prompt_text, record_prompt)
        if (
            prompt_match.get('matched') is not True
            and base_prompt_text
            and rec.get('base_prompt_substituted') is True
        ):
            prompt_match = fuzzy_prompt_match(base_prompt_text, record_prompt)
            if prompt_match.get('matched') is True:
                prompt_match = dict(prompt_match, kind='base_prompt_' + str(prompt_match.get('kind')))
        if not hash_matched and prompt_match.get('matched') is not True:
            continue
        if hash_matched:
            prompt_match = {{
                'matched': True,
                'kind': 'sha256',
                'similarity': 1.0,
                'prefix_loss': 0,
            }}
        out = {{
            'ok': True,
            'path': str(path),
            'record': rec,
            'prompt_match': prompt_match,
            'record_epoch': record_epoch,
            'match_window': {{
                'since_epoch': since_epoch,
                'until_epoch': until_epoch,
                'clock_tolerance_seconds': 5,
            }},
        }}
    if not out.get('ok'):
        out = {{'ok': False, 'path': str(path), 'reason': 'matching prompt not found'}}
print(json.dumps(out, sort_keys=True))
"""
    command = "python3 - <<'PY'\n" + remote_py + "\nPY"
    try:
        completed = subprocess.run(
            [*ssh, target, command],
            capture_output=True,
            text=True,
            timeout=20,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception as exc:
        return {"ok": False, "reason": f"ssh failed: {exc}"}
    if completed.returncode != 0:
        return {"ok": False, "reason": completed.stderr.strip() or completed.stdout.strip()}
    try:
        payload = json.loads(completed.stdout.strip().splitlines()[-1])
    except Exception as exc:
        return {"ok": False, "reason": f"invalid CT memory proof: {exc}", "stdout": completed.stdout.strip()}
    return payload if isinstance(payload, dict) else {"ok": False, "reason": "invalid CT memory proof payload"}


def _write_ct_memory_chat_receipt(ct_memory: dict[str, Any], prompt: str, run_id: str, index: int) -> Path:
    CHAT_RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    record = ct_memory.get("record") if isinstance(ct_memory.get("record"), dict) else {}
    path = CHAT_RECEIPT_DIR / f"ENGEL_UI_CHAT_CT_MEMORY_{run_id}_{index:02d}.json"
    action = record.get("action") if isinstance(record.get("action"), dict) else {}
    result = action.get("result") if isinstance(action.get("result"), dict) else {}
    run_result = action.get("run") if isinstance(action.get("run"), dict) else {}
    build_lane_used = bool(record.get("build_lane_used") is True or action.get("kind") == "app_build")
    workspace_setup_used = action.get("kind") == "workspace_scaffold"
    expected_build_lane = _requested_app_build(_operator_request_text(prompt)) is not None
    creation_job = bool(build_lane_used or workspace_setup_used)
    workspace_files = result.get("files") if isinstance(result.get("files"), list) else []
    workspace_path = str(result.get("path") or "").strip()
    entry = str(result.get("entry") or "").strip().casefold()
    web_build = bool(
        str(action.get("language") or "").strip().casefold() == "web"
        or entry.endswith((".html", ".htm"))
    )
    run_required = bool(build_lane_used and result.get("run_hint") and not web_build)
    run_verified = bool(
        run_result.get("ran") is True
        and run_result.get("timed_out") is not True
        and not str(run_result.get("compile_error") or "").strip()
        and "[stderr]" not in str(run_result.get("output") or "").casefold()
        and (
            str(action.get("language") or "").strip().casefold() == "python"
            or run_result.get("exit_code") == 0
        )
    )
    inferred_build_artifact_verified = bool(
        creation_job
        and (not expected_build_lane or build_lane_used)
        and result.get("ok") is True
        and workspace_path
        and workspace_files
        and (not run_required or run_verified)
    )
    build_artifact_verified = bool(
        record.get("build_verified")
        if isinstance(record.get("build_verified"), bool)
        else inferred_build_artifact_verified
    )
    conical = (
        record.get("conical_orchestration")
        if isinstance(record.get("conical_orchestration"), dict)
        else {}
    )
    payload = {
        "ok": record.get("ok") is True,
        "status": record.get("status") or "unknown",
        "creation_job": creation_job,
        "chat_only_no_android_or_sub_engel": not creation_job,
        "agent_meeting_room_used": record.get("agent_meeting_room_used") is True,
        "meeting_room_server_used": record.get("meeting_room_server_used") is True,
        "meeting_room_order_id": record.get("meeting_room_order_id"),
        "local_llm_only": record.get("provider_api_enabled") is not True,
        "build_lane_used": build_lane_used,
        "expected_build_lane": expected_build_lane,
        "build_artifact_verified": build_artifact_verified,
        "workspace_path": workspace_path,
        "workspace_files": workspace_files,
        "workspace_created": result.get("created"),
        "workspace_run_ran": run_result.get("ran"),
        "workspace_run_exit_code": run_result.get("exit_code"),
        "workspace_run_output": run_result.get("output"),
        "workspace_run_compile_error": run_result.get("compile_error"),
        "workspace_receipt_path": record.get("workspace_receipt_path"),
        "runtime_provider": record.get("runtime_provider"),
        "selected_provider": record.get("selected_provider") or record.get("runtime_provider"),
        "requested_provider": "auto_best",
        "provider_api_enabled": record.get("provider_api_enabled") is True,
        # Derive local-only-training from the turn's OWN provenance rather than a
        # server flag the Flutter chat inbox never forwards: a turn that used no
        # provider API and no bridge IS a local-only training sample, whichever
        # local lane served it (main, sparse-MoE, deep, math). Mirrors local_llm_only.
        "local_only_training": (
            record.get("provider_api_enabled") is not True
            and record.get("provider_bridge_used") is not True
            and record.get("provider_bridge_fallback_attempted") is not True
        ),
        "provider_fallback_allowed": record.get("provider_fallback_allowed"),
        "provider_pipeline_used": record.get("provider_pipeline_used") is True,
        "provider_bridge_fallback_attempted": (
            record.get("provider_bridge_fallback_attempted") is True
        ),
        # Keep the server's verdict when it set one; otherwise derive eligibility
        # from the turn's OWN success signals, because the specialist lanes
        # (sparse-MoE, deep, math) reply cleanly but never stamp the flag. A turn
        # counts as a usable local training sample only when it succeeded, stayed
        # local, its semantic-quality gate did NOT fail, and the status is a clean
        # reply (never a blocked/failed one) — this fixes the missing stamp without
        # ever counting a blocked or externally-served turn.
        "training_sample_eligible": (
            record.get("training_sample_eligible") is True
            or (
                record.get("ok") is True
                and record.get("provider_api_enabled") is not True
                and record.get("provider_bridge_used") is not True
                and (record.get("local_semantic_quality") or {}).get("ok") is not False
                and not any(
                    bad in str(record.get("status") or "").casefold()
                    for bad in ("blocked", "quality check failed", "style check failed", "error")
                )
            )
        ),
        "local_semantic_quality": record.get("local_semantic_quality") or {},
        "network_enabled": record.get("network_enabled") is True,
        "humanizer_voice_rules_active": True,
        "persistent_chat_memory_appended": True,
        "ui_reply_guard_triggered": False,
        "standalone_guard_triggered": False,
        "visible_reply_source": "ct_persistent_chat_memory",
        "latency_ms": record.get("server_request_latency_ms"),
        "main_server_chat_used": True,
        "main_server_chat_url": os.environ.get("ENGEL_CT_CHAT_URL", "ct_persistent_chat_memory"),
        "fast_server_fallback_used": False,
        "server_request_latency_ms": record.get("server_request_latency_ms"),
        "ct_persistent_memory_path": ct_memory.get("path"),
        "ct_prompt_match": ct_memory.get("prompt_match") or {},
        "ct_prompt_match_window": ct_memory.get("match_window") or {},
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "assistant_reply": record.get("assistant_reply"),
        "updated_at_utc": record.get("updated_at_utc"),
        "build_lifecycle": record.get("build_lifecycle") or [],
        "build_review": record.get("build_review") or {},
        "build_package": record.get("build_package") or {},
        "build_preview": record.get("build_preview") or {},
        "build_verified": build_artifact_verified,
        "build_generation_routes": record.get("build_generation_routes") or [],
        "build_standalone_first_attempted": record.get("build_standalone_first_attempted") is True,
        "build_local_model_used": record.get("build_local_model_used") is True,
        "build_attached_codex_used": record.get("build_attached_codex_used") is True,
        "build_external_provider_api_used": record.get("build_external_provider_api_used") is True,
        "provider_free_generation": record.get("provider_free_generation") is True,
        "conical_orchestration": conical,
        "conical_job_id": record.get("conical_job_id") or conical.get("job_id"),
        "conical_job_status": record.get("conical_job_status") or conical.get("final_status"),
        "conical_worker_returned_count": record.get("conical_worker_returned_count")
        if record.get("conical_worker_returned_count") is not None
        else conical.get("returned_worker_count"),
        "conical_worker_expected_count": record.get("conical_worker_expected_count")
        if record.get("conical_worker_expected_count") is not None
        else conical.get("expected_worker_count"),
        "conical_terminal_failure": record.get("conical_terminal_failure") is True,
        "ct246_conical_receipt_path": record.get("ct246_conical_receipt_path")
        or conical.get("receipt_path"),
        "ct246_conical_report_written": record.get("ct246_conical_report_written") is True,
        "ct246_conical_memory_appended": record.get("ct246_conical_memory_appended") is True,
        "ct246_conical_persistence_ok": record.get("ct246_conical_persistence_ok") is True,
        "ct246_conical_persistence_error": record.get("ct246_conical_persistence_error") or "",
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _text_blob(value: Any) -> str:
    if isinstance(value, dict):
        return "\n".join(_text_blob(item) for item in value.values())
    if isinstance(value, list):
        return "\n".join(_text_blob(item) for item in value)
    return "" if value is None else str(value)


def _matches_prompt(payload: dict[str, Any], prompt: str) -> bool:
    blob = _text_blob(payload).lower()
    prompt_lower = prompt.lower()
    if prompt_lower in blob:
        return True
    words = [word for word in prompt_lower.replace(":", " ").replace(".", " ").split() if len(word) > 3]
    if not words:
        return False
    return sum(1 for word in words[:18] if word in blob) >= min(8, len(words[:18]))


def _matching_conical_receipt(
    prompt: str,
    since_epoch: float,
    prior_names: set[str] | None = None,
) -> dict[str, Any]:
    prior_names = prior_names or set()
    matches: list[tuple[Path, dict[str, Any]]] = []
    for path in _paths_since(CONICAL_REPORT_DIR, since_epoch - 2, "conical_job_*.json"):
        if path.name in prior_names:
            continue
        payload = _load_json(path)
        if not isinstance(payload, dict) or not _matches_prompt(payload, prompt):
            continue
        plan = payload.get("plan") if isinstance(payload.get("plan"), dict) else {}
        started_text = str(
            payload.get("started_at_utc") or plan.get("created_at_utc") or ""
        ).strip()
        if started_text:
            try:
                started_epoch = datetime.datetime.fromisoformat(
                    started_text.replace("Z", "+00:00")
                ).timestamp()
            except (TypeError, ValueError):
                started_epoch = 0.0
            if started_epoch and started_epoch + 2 < since_epoch:
                continue
        matches.append((path, payload))
    if not matches:
        return {"ok": False, "reason": "matching conical receipt not found"}
    path, payload = matches[-1]
    status = str(payload.get("status") or "").strip().casefold()
    final_status = str(payload.get("final_status") or "").strip().casefold()
    terminal_failure = bool(
        final_status == "failed"
        or status
        in {
            "failed",
            "failed_worker_returns",
            "failed_orchestration_start",
            "failed_no_valid_return",
        }
    )
    return {
        "ok": True,
        "path": str(path),
        "payload": payload,
        "status": status,
        "final_status": final_status,
        "terminal_failure": terminal_failure,
    }


def _write_conical_terminal_wrapper(
    conical_match: dict[str, Any],
    prompt: str,
    run_id: str,
    index: int,
) -> Path:
    conical = (
        conical_match.get("payload")
        if isinstance(conical_match.get("payload"), dict)
        else {}
    )
    expected = int(conical.get("expected_worker_count") or 4)
    returned = int(conical.get("returned_worker_count") or 0)
    worker_results = conical.get("worker_results") if isinstance(conical.get("worker_results"), list) else []
    missing = [
        str(row.get("worker_id") or "unknown_worker")
        for row in worker_results
        if isinstance(row, dict) and row.get("returned") is not True
    ]
    workers_complete = bool(
        expected > 0
        and returned == expected
        and all(
            isinstance(row, dict) and row.get("returned") is True
            for row in worker_results
        )
    )
    if workers_complete:
        reply = (
            f"The visible build request completed conical worker assembly at "
            f"{returned}/{expected}, but CT246 build/finalization failed before durable "
            "artifact proof returned. No finished build is being claimed."
        )
        terminal_status = "conical build/finalization failure without CT246 wrapper proof"
    else:
        missing_text = (
            ", ".join(sorted(set(missing)))
            if missing
            else "one or more required workers"
        )
        reply = (
            f"The visible build request was accepted, but conical worker assembly failed at "
            f"{returned}/{expected}. Missing: {missing_text}. No build artifact is being claimed. "
            "CT246 did not return durable build proof within the bounded grace period."
        )
        terminal_status = "conical terminal failure without CT246 wrapper proof"
    payload = {
        "schema": "engel_ui_conical_terminal_failure_receipt_v1",
        "ok": False,
        "status": terminal_status,
        "prompt": prompt,
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "assistant_reply": reply,
        "assistant_output_text": reply,
        "creation_job": True,
        "chat_only_no_android_or_sub_engel": False,
        "build_lane_used": True,
        "expected_build_lane": True,
        "build_artifact_verified": False,
        "build_verified": False,
        "build_execution_verified": False,
        "workspace_path": "",
        "workspace_files": [],
        "agent_meeting_room_used": True,
        "meeting_room_server_used": bool(conical.get("meeting_room_order_id")),
        "provider_api_enabled": False,
        "provider_free_generation": True,
        "persistent_chat_memory_appended": False,
        "conical_orchestration": conical,
        "conical_job_id": conical.get("job_id"),
        "conical_job_status": "failed",
        "conical_worker_returned_count": returned,
        "conical_worker_expected_count": expected,
        "conical_terminal_failure": True,
        "conical_receipt_path": conical_match.get("path"),
        "ct246_conical_receipt_path": "",
        "ct246_conical_report_written": False,
        "ct246_conical_memory_appended": False,
        "ct246_conical_persistence_ok": False,
        "ct246_conical_persistence_error": "CT246 proof was not observed within the bounded grace period",
        "updated_at_utc": iso_now(),
    }
    CHAT_RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    path = CHAT_RECEIPT_DIR / f"ENGEL_UI_CHAT_MEETING_ROOM_CONICAL_TERMINAL_{run_id}_{index:02d}.json"
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(temp, path)
    return path


def _conical_proof(payload: dict[str, Any]) -> dict[str, Any]:
    orchestration = (
        payload.get("conical_orchestration")
        if isinstance(payload.get("conical_orchestration"), dict)
        else {}
    )
    results = (
        orchestration.get("worker_results")
        if isinstance(orchestration.get("worker_results"), list)
        else []
    )
    worker_ids = {
        str(row.get("worker_id") or "").strip()
        for row in results
        if isinstance(row, dict) and row.get("returned") is True
    }
    expected_count = int(
        payload.get("conical_worker_expected_count")
        or orchestration.get("expected_worker_count")
        or 0
    )
    returned_count = int(
        payload.get("conical_worker_returned_count")
        or orchestration.get("returned_worker_count")
        or 0
    )
    status = str(
        payload.get("conical_job_status")
        or orchestration.get("final_status")
        or ""
    ).strip().casefold()
    return {
        "ok": bool(
            status == "finished"
            and expected_count == 4
            and returned_count == 4
            and worker_ids == EXPECTED_CONICAL_WORKERS
        ),
        "status": status,
        "expected_count": expected_count,
        "returned_count": returned_count,
        "worker_ids": sorted(worker_ids),
        "receipt_path": str(
            payload.get("ct246_conical_receipt_path")
            or orchestration.get("receipt_path")
            or ""
        ),
        "ct246_persistence_ok": payload.get("ct246_conical_persistence_ok") is True,
    }


def _build_proof(payload: dict[str, Any]) -> dict[str, Any]:
    package = payload.get("build_package") if isinstance(payload.get("build_package"), dict) else {}
    preview = payload.get("build_preview") if isinstance(payload.get("build_preview"), dict) else {}
    lifecycle = payload.get("build_lifecycle") if isinstance(payload.get("build_lifecycle"), list) else []
    stages = {
        (str(row.get("stage") or ""), str(row.get("status") or ""))
        for row in lifecycle
        if isinstance(row, dict)
    }
    required = {
        ("generate", "passed"),
        ("workspace", "passed"),
        ("review", "passed"),
        ("package", "passed"),
        ("open_proof", "ready"),
    }
    routes = (
        payload.get("build_generation_routes")
        if isinstance(payload.get("build_generation_routes"), list)
        else []
    )
    provider_route_used = any(
        isinstance(row, dict)
        and row.get("usable") is True
        and row.get("provider_api_enabled") is True
        for row in routes
    )
    standalone_first = bool(
        payload.get("build_standalone_first_attempted") is True
        and routes
        and isinstance(routes[0], dict)
        and routes[0].get("route") == "ct246_local_coder_gguf"
    )
    provider_free = bool(
        payload.get("provider_api_enabled") is False
        and payload.get("build_external_provider_api_used") is not True
        and payload.get("provider_free_generation") is True
        and not provider_route_used
    )
    return {
        "ok": bool(
            payload.get("build_verified") is True
            and payload.get("build_artifact_verified") is True
            and package.get("ok") is True
            and str(package.get("path") or "").strip()
            and str(package.get("sha256") or "").strip()
            and str(preview.get("workspace_path") or "").strip()
            and str(preview.get("entry_file") or "").strip()
            and required.issubset(stages)
            and standalone_first
            and provider_free
        ),
        "package_ok": package.get("ok") is True,
        "package_path": str(package.get("path") or ""),
        "package_sha256": str(package.get("sha256") or ""),
        "preview_kind": str(preview.get("kind") or ""),
        "preview_url": str(preview.get("url") or ""),
        "workspace_path": str(preview.get("workspace_path") or ""),
        "lifecycle_stages": sorted([list(item) for item in stages]),
        "standalone_first_attempted": standalone_first,
        "local_model_used": payload.get("build_local_model_used") is True,
        "attached_codex_used": payload.get("build_attached_codex_used") is True,
        "provider_free": provider_free,
        "routes": routes,
    }


def _recent_android_claims(prompt: str, since_epoch: float) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    if not CLAIMED_ASSIGNMENTS_DIR.exists():
        return claims
    for path in sorted(
        CLAIMED_ASSIGNMENTS_DIR.glob("*_assignment.json"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    ):
        if path.stat().st_mtime < since_epoch - 1:
            break
        payload = _load_json(path)
        if not isinstance(payload, dict):
            continue
        worker = str(payload.get("worker_target") or payload.get("worker_id") or "")
        if not worker.startswith("android_worker_"):
            continue
        if _matches_prompt(payload, prompt):
            claims.append(
                {
                    "assignment_path": str(path),
                    "packet_id": payload.get("packet_id"),
                    "worker_id": worker,
                    "title": payload.get("title"),
                    "task_type": payload.get("task_type"),
                }
            )
    return claims


def _returned_for_packet(packet_id: str, worker_id: str) -> dict[str, Any] | None:
    if not packet_id or not RETURNED_ASSIGNMENTS_DIR.exists():
        return None
    for path in sorted(
        RETURNED_ASSIGNMENTS_DIR.glob("*.json"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    ):
        payload = _load_json(path)
        if not isinstance(payload, dict):
            continue
        if payload.get("packet_id") == packet_id and payload.get("worker_id") == worker_id:
            return {
                "returned_path": str(path),
                "packet_id": packet_id,
                "worker_id": worker_id,
                "result_type": payload.get("result_type"),
                "safe_to_auto_apply": payload.get("safe_to_auto_apply"),
                "requires_review": payload.get("requires_review"),
                "trusted_memory_write": payload.get("trusted_memory_write"),
                "auto_apply": payload.get("auto_apply"),
                "storage_decision": payload.get("storage_decision"),
            }
    return None


def _order_uses_android(orders: list[dict[str, Any]]) -> bool:
    for order in orders:
        blob = _text_blob(order).lower()
        if "android" in blob and "worker" in blob:
            return True
    return False


def _load_canonical_curriculum_binding(template_path: str | None) -> dict[str, Any]:
    """Bind a scheduled run to one exact current canonical curriculum template."""

    if not template_path:
        raise RuntimeError("scheduled training requires a canonical curriculum template")
    index = _load_json(CURRICULA_INDEX_PATH)
    if not isinstance(index, dict) or index.get("schema") != "engel_training_curricula_index_v1":
        raise RuntimeError(f"canonical curricula index is missing or invalid: {CURRICULA_INDEX_PATH}")
    curricula = index.get("curricula")
    expected = list(CANONICAL_CURRICULA)
    if (
        not isinstance(curricula, list)
        or len(curricula) != len(expected)
        or int(index.get("curriculum_count") or 0) != len(expected)
        or int(index.get("total_prompts") or 0) != 400
    ):
        raise RuntimeError("canonical curricula index is not an exact five-curriculum set")
    actual_identity = [
        (
            str(item.get("id") or ""),
            str(item.get("title") or ""),
            str(item.get("discipline") or ""),
        )
        for item in curricula
        if isinstance(item, dict)
    ]
    if actual_identity != expected:
        raise RuntimeError("canonical curricula index identity/order does not match the reviewed five")

    requested = Path(template_path).resolve(strict=True)
    if requested.is_symlink() or not requested.is_file():
        raise RuntimeError(f"curriculum template is not a regular file: {requested}")
    matched: list[dict[str, Any]] = []
    for item in curricula:
        try:
            indexed_path = Path(str(item.get("template_path") or "")).resolve(strict=True)
        except (OSError, RuntimeError):
            continue
        if indexed_path == requested:
            matched.append(item)
    if len(matched) != 1:
        raise RuntimeError("selected template does not resolve to exactly one canonical curriculum")
    item = matched[0]
    # The library stays an 8-hour/80-prompt template. A run may use the remaining
    # unused hours only. Live 2026-08-18: Chat Communication had 1 novel hour left
    # and Engel Main planned 10 prompts / 1 hour; this gate still demanded all 8
    # unused, so the launcher died in ~250ms and the Training page looked stuck.
    novel_hours = int(item.get("novel_hours_available") or 0)
    if (
        int(item.get("prompt_count") or 0) != 80
        or int(item.get("maximum_hours") or 0) != 8
        or novel_hours < 1
        or item.get("novelty_ready") is False
    ):
        raise RuntimeError(
            "selected curriculum has no unused novel hour left "
            f"(status={item.get('novelty_status')}, novel_hours={novel_hours})"
        )
    expected_sha = str(item.get("template_sha256") or "").strip().casefold()
    if not re.fullmatch(r"[a-f0-9]{64}", expected_sha):
        raise RuntimeError("selected curriculum has no valid template SHA-256 binding")
    template_bytes = requested.read_bytes()
    actual_sha = hashlib.sha256(template_bytes).hexdigest()
    if actual_sha != expected_sha:
        raise RuntimeError("selected curriculum template bytes do not match the curricula index")
    try:
        template = json.loads(template_bytes.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("selected curriculum template bytes are not valid JSON") from exc
    cycles = template.get("cycle_prompt_sets") if isinstance(template, dict) else None
    if (
        not isinstance(template, dict)
        or str(template.get("material_version") or "") != str(item.get("version") or "")
        or int(template.get("maximum_scheduled_prompt_count") or 0) != 80
        or not isinstance(cycles, list)
        or len(cycles) != 8
        or any(
            not isinstance(cycle, dict)
            or not isinstance(cycle.get("prompts"), list)
            or len(cycle["prompts"]) != 10
            for cycle in cycles
        )
    ):
        raise RuntimeError("selected curriculum template content does not match its binding")
    return {
        "schema": CURRICULUM_BINDING_SCHEMA,
        "curriculum_id": str(item["id"]),
        "curriculum_title": str(item["title"]),
        "discipline": str(item["discipline"]),
        "material_version": str(item["version"]),
        "template_path": str(requested),
        "template_sha256": actual_sha,
        "novelty_status": str(item.get("novelty_status") or ""),
        "novel_hours_available": novel_hours,
        "novel_hours_start_cycle": int(item.get("novel_hours_start_cycle") or 0),
    }


def _load_template_prompts(template_path: str | None, mode: str, cycle: int) -> list[str]:
    if not template_path:
        return prompt_bank(mode)
    path = Path(template_path)
    payload = _load_json(path)
    if not isinstance(payload, dict):
        raise RuntimeError(f"training template could not be read as JSON: {path}")
    if mode == "smoke":
        prompts = payload.get("smoke_prompts")
        if not prompts:
            prompts = payload.get("active_prompts", [])[:3]
    else:
        cycle_sets = payload.get("cycle_prompt_sets")
        prompts = None
        if isinstance(cycle_sets, list) and cycle_sets:
            index = max(0, (cycle - 1) % len(cycle_sets))
            selected = cycle_sets[index]
            if isinstance(selected, dict):
                prompts = selected.get("prompts")
            elif isinstance(selected, list):
                prompts = selected
        if not prompts:
            prompts = payload.get("active_prompts")
    if not isinstance(prompts, list):
        raise RuntimeError(f"training template has no prompt list for mode={mode}: {path}")
    clean = [str(item).strip() for item in prompts if str(item).strip()]
    if not clean:
        raise RuntimeError(f"training template prompt list is empty: {path}")
    return clean


# "communication" joined 2026-08-01 with the chat-voice curriculum. Registering it here is
# not cosmetic: an unlisted discipline falls back to "aec", and a chat-voice card run as AEC
# would be delivered with the evidence-ledger level text and the labelled answer contract,
# then graded by the construction gate -- i.e. the run would teach Engel the exact scaffolded
# voice this curriculum exists to remove, and the pack rows would be mislabelled "aec".
_KNOWN_DISCIPLINES = {"aec", "math", "engineering", "communication"}


def _resolve_template_discipline(template_path: str | None) -> str:
    """Read the curriculum discipline the template declares (default 'aec').

    Unknown or missing values fall back to 'aec' so an unrecognized template is held to
    the strict construction gate rather than silently skipping it (fail toward more rigor).
    """
    if not template_path:
        return "aec"
    try:
        payload = _load_json(Path(template_path))
    except Exception:
        return "aec"
    discipline = str((payload or {}).get("training_discipline") or "aec").strip().casefold()
    return discipline if discipline in _KNOWN_DISCIPLINES else "aec"


def _load_training_schedule(
    template_path: str | None,
    mode: str,
    cycle: int,
    scheduled_hours: int,
    training_level: str,
    trainings_per_hour: int,
) -> dict[str, Any]:
    """Build a deterministic run schedule with one fresh cycle per selected hour."""
    hours = validate_training_hours(scheduled_hours)
    level_profile = training_level_profile(training_level)
    hourly_count = validate_trainings_per_hour(trainings_per_hour)
    discipline = _resolve_template_discipline(template_path)
    if mode != "scheduled":
        prompts = _load_template_prompts(template_path, mode, cycle)
        evidence_packet: dict[str, Any] = {}
        if discipline == "aec":
            if not template_path:
                raise RuntimeError(
                    "AEC training requires a canonical material card and evidence anchors"
                )
            payload = _load_json(Path(template_path))
            cycle_sets = payload.get("cycle_prompt_sets") if isinstance(payload, dict) else None
            selected_cycle = None
            if isinstance(cycle_sets, list) and cycle_sets:
                selected_cycle = (
                    cycle_sets[0]
                    if mode == "smoke"
                    else cycle_sets[max(0, (int(cycle) - 1) % len(cycle_sets))]
                )
            material_card = (
                selected_cycle.get("material_card")
                if isinstance(selected_cycle, dict)
                else None
            )
            evidence_packet = _aec_evidence_for_card(material_card)
        return {
            "entries": [
                {
                    "prompt": _leveled_training_prompt(
                        prompt,
                        level_profile["training_level"],
                        discipline,
                        evidence_context=evidence_packet.get("prompt_context", ""),
                    ),
                    "base_prompt": prompt,
                    "scheduled_hour": 1,
                    "template_cycle": cycle,
                    "source_prompt_index": index,
                    "material_topic": "",
                    "discipline": discipline,
                    "aec_expected_documents": list(
                        evidence_packet.get("expected_documents") or []
                    ),
                    "aec_evidence_bundle_sha256": str(
                        evidence_packet.get("corpus_bundle_sha256") or ""
                    ),
                    "aec_evidence_records": list(
                        evidence_packet.get("records") or []
                    ),
                }
                for index, prompt in enumerate(prompts, start=1)
            ],
            "hourly_cycles": [
                {
                    "scheduled_hour": 1,
                    "template_cycle": cycle,
                    "material_topic": "",
                    "selected_prompt_count": len(prompts),
                    "source_prompt_positions": list(range(1, len(prompts) + 1)),
                }
            ],
            "level_profile": level_profile,
            "trainings_per_hour": hourly_count,
            "discipline": discipline,
            "aec_evidence": [
                {
                    "corpus_bundle_sha256": evidence_packet.get(
                        "corpus_bundle_sha256", ""
                    ),
                    "documents": evidence_packet.get("expected_documents", []),
                    "records": evidence_packet.get("records", []),
                }
            ] if evidence_packet else [],
        }
    if not template_path:
        raise RuntimeError(
            "scheduled training requires the canonical template with distinct hourly cycles"
        )
    path = Path(template_path)
    payload = _load_json(path)
    if not isinstance(payload, dict):
        raise RuntimeError(f"training template could not be read as JSON: {path}")
    cycle_sets = payload.get("cycle_prompt_sets")
    available = len(cycle_sets) if isinstance(cycle_sets, list) else 0
    controls = payload.get("scheduled_controls")
    declared_maximum = (
        int(controls.get("maximum_hours") or available)
        if isinstance(controls, dict)
        else available
    )
    if not isinstance(cycle_sets, list) or not 1 <= declared_maximum <= min(8, available):
        raise RuntimeError(
            f"training template declares {declared_maximum} hours but contains {available} cycles"
        )
    if hours > declared_maximum:
        raise RuntimeError(
            f"scheduled training requested {hours} hours but this template supports at "
            f"most {declared_maximum}; select a shorter duration or prepare new material"
        )
    cycle_start = max(0, (int(cycle) - 1) % len(cycle_sets))
    selected_cycles = [
        cycle_sets[(cycle_start + hour_offset) % len(cycle_sets)]
        for hour_offset in range(hours)
    ]
    entries: list[dict[str, Any]] = []
    hourly_cycles: list[dict[str, Any]] = []
    material_topics: list[str] = []
    prompt_fingerprints: list[str] = []
    for scheduled_hour, selected in enumerate(selected_cycles, start=1):
        if not isinstance(selected, dict):
            raise RuntimeError(
                f"scheduled hourly cycle {scheduled_hour} is not a template object"
            )
        raw_prompts = selected.get("prompts")
        if not isinstance(raw_prompts, list):
            raise RuntimeError(
                f"scheduled hourly cycle {scheduled_hour} has no prompt list"
            )
        clean_prompts = [str(item).strip() for item in raw_prompts if str(item).strip()]
        selected_prompts = select_balanced_training_prompts(
            clean_prompts,
            hourly_count,
        )
        evidence_packet = (
            _aec_evidence_for_card(selected.get("material_card"))
            if discipline == "aec"
            else {}
        )
        material_topic = str(selected.get("material_topic") or "").strip()
        template_cycle = int(selected.get("cycle") or scheduled_hour)
        material_topics.append(material_topic)
        prompt_fingerprints.append(
            hashlib.sha256(
                "\n".join(clean_prompts).encode("utf-8")
            ).hexdigest()
        )
        hourly_cycles.append(
            {
                "scheduled_hour": scheduled_hour,
                "template_cycle": template_cycle,
                "material_topic": material_topic,
                "fresh_material": selected.get("fresh_material") is True,
                "source_prompt_count": len(clean_prompts),
                "selected_prompt_count": len(selected_prompts),
                "trainings_per_hour": hourly_count,
                "source_prompt_positions": [
                    position for position, _prompt in selected_prompts
                ],
                "aec_evidence_bundle_sha256": str(
                    evidence_packet.get("corpus_bundle_sha256") or ""
                ),
                "aec_expected_documents": list(
                    evidence_packet.get("expected_documents") or []
                ),
                "aec_evidence_records": list(
                    evidence_packet.get("records") or []
                ),
            }
        )
        for source_prompt_index, prompt in selected_prompts:
            entries.append(
                {
                    "prompt": _leveled_training_prompt(
                        prompt,
                        level_profile["training_level"],
                        discipline,
                        evidence_context=evidence_packet.get("prompt_context", ""),
                    ),
                    "base_prompt": prompt,
                    "scheduled_hour": scheduled_hour,
                    "template_cycle": template_cycle,
                    "source_prompt_index": source_prompt_index,
                    "material_topic": material_topic,
                    "discipline": discipline,
                    "aec_expected_documents": list(
                        evidence_packet.get("expected_documents") or []
                    ),
                    "aec_evidence_bundle_sha256": str(
                        evidence_packet.get("corpus_bundle_sha256") or ""
                    ),
                    "aec_evidence_records": list(
                        evidence_packet.get("records") or []
                    ),
                }
            )
    if len(set(material_topics)) != hours or any(not item for item in material_topics):
        raise RuntimeError(
            "scheduled training template must provide a distinct material topic for every hour"
        )
    if len(set(prompt_fingerprints)) != hours:
        raise RuntimeError(
            "scheduled training template must provide a distinct ten-prompt cycle for every hour"
        )
    return {
        "entries": entries,
        "hourly_cycles": hourly_cycles,
        "level_profile": level_profile,
        "trainings_per_hour": hourly_count,
        "discipline": discipline,
        "template_cycle_count": len(cycle_sets),
        "aec_evidence": [
            {
                "scheduled_hour": item["scheduled_hour"],
                "corpus_bundle_sha256": item.get(
                    "aec_evidence_bundle_sha256", ""
                ),
                "documents": item.get("aec_expected_documents", []),
                "records": item.get("aec_evidence_records", []),
            }
            for item in hourly_cycles
            if item.get("aec_evidence_bundle_sha256")
        ],
    }


def _prepare_session_preflight(
    *,
    mode: str,
    template_path: str | None,
    template_cycle: int,
    scheduled_hours: int,
    training_level: str,
    trainings_per_hour: int,
    start_index: int,
    exact_template_cycle: bool = False,
) -> dict[str, Any]:
    """Build the pure schedule and prove cross-run novelty before any mutable action.

    (2026-08-10) Scheduled mode can AUTO-ADVANCE the starting template cycle when the
    requested cycle would replay consumed prompts: the 20260810 1h comm run consumed
    cycle 1, so the next 4h run at cycle 1 planned 10 replays and the novelty judge
    refused the whole launch. Practice means fresh material, so composition now walks
    the template's remaining cycles until the plan is fully novel; the judge itself
    stays untouched and still refuses when every cycle is exhausted.

    Engel Main passes exact_template_cycle after showing the operator the indexed
    topic plan. Under that consent contract this function must either use the exact
    requested cycle or refuse; silently switching topics is never permitted."""

    start_index = max(1, int(start_index))
    template_cycle = validate_template_cycle(template_cycle)
    curriculum_binding = (
        _load_canonical_curriculum_binding(template_path)
        if template_path and mode in {"scheduled", "smoke", "completion"}
        else {}
    )
    if mode == "scheduled" and curriculum_binding:
        available = int(curriculum_binding.get("novel_hours_available") or 0)
        if int(scheduled_hours) > available:
            raise RuntimeError(
                f"requested {scheduled_hours}h but only {available} unused novel "
                "hour(s) remain on this curriculum"
            )

    def _compose(cycle_candidate: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        composed_schedule = _load_training_schedule(
            template_path,
            mode,
            cycle_candidate,
            scheduled_hours,
            training_level,
            trainings_per_hour,
        )
        composed_entries = composed_schedule["entries"][start_index - 1 :]
        if not composed_entries:
            raise RuntimeError(
                f"start index {start_index} is past the "
                f"{len(composed_schedule['entries'])} available prompts"
            )
        return composed_schedule, composed_entries

    training_schedule, schedule_entries = _compose(int(template_cycle))
    effective_template_cycle = int(template_cycle)
    novelty_auto_advance: dict[str, Any] = {}
    if mode == "scheduled":
        prompt_novelty = evaluate_scheduled_prompt_novelty(
            [entry["base_prompt"] for entry in schedule_entries],
            PACKS_DIR,
        )
        replayed_count = int(prompt_novelty.get("replayed_prompt_count") or 0)
        if (
            not exact_template_cycle
            and prompt_novelty.get("decision") == "BLOCK"
            and replayed_count > 0
        ):
            cycle_count = max(1, int(training_schedule.get("template_cycle_count") or 1))
            tried_cycles: list[int] = []
            for offset in range(1, cycle_count):
                candidate_cycle = int(template_cycle) + offset
                tried_cycles.append(candidate_cycle)
                candidate_schedule, candidate_entries = _compose(candidate_cycle)
                candidate_novelty = evaluate_scheduled_prompt_novelty(
                    [entry["base_prompt"] for entry in candidate_entries],
                    PACKS_DIR,
                )
                if candidate_novelty.get("decision") != "BLOCK":
                    training_schedule = candidate_schedule
                    schedule_entries = candidate_entries
                    prompt_novelty = candidate_novelty
                    effective_template_cycle = candidate_cycle
                    novelty_auto_advance = {
                        "advanced": True,
                        "requested_template_cycle": int(template_cycle),
                        "effective_template_cycle": candidate_cycle,
                        "replayed_prompt_count_at_requested_cycle": replayed_count,
                        "tried_cycles": list(tried_cycles),
                    }
                    break
            else:
                novelty_auto_advance = {
                    "advanced": False,
                    "requested_template_cycle": int(template_cycle),
                    "tried_cycles": list(tried_cycles),
                    "exhausted": True,
                }
    else:
        prompt_hashes = [
            canonical_base_prompt_sha256(entry["base_prompt"])
            for entry in schedule_entries
        ]
        prompt_novelty = {
            "schema": PROMPT_NOVELTY_PREFLIGHT_SCHEMA,
            "requested": False,
            "ok": True,
            "decision": "NOT_REQUIRED",
            "reason": "cross-run replay refusal is mandatory for scheduled mode",
            "planned_prompt_count": len(prompt_hashes),
            "planned_unique_prompt_count": len(set(prompt_hashes)),
            "planned_prompt_hashes": prompt_hashes,
        }
    return {
        "schema": "engel_ui_prompt_training_session_preflight_v1",
        "mode": mode,
        "template_path": template_path or "",
        "template_cycle": int(template_cycle),
        "template_cycle_effective": int(effective_template_cycle),
        "exact_template_cycle": bool(exact_template_cycle),
        "template_cycle_contract": (
            "EXACT" if exact_template_cycle else "AUTO_ADVANCE_ALLOWED"
        ),
        "curriculum_binding": curriculum_binding,
        "prompt_novelty_auto_advance": novelty_auto_advance,
        "scheduled_hours": int(scheduled_hours),
        "training_level": training_level,
        "trainings_per_hour": int(trainings_per_hour),
        "start_index": start_index,
        "schedule": training_schedule,
        "schedule_entries": schedule_entries,
        "prompt_novelty": prompt_novelty,
        "aec_evidence_preflight": list(training_schedule.get("aec_evidence") or []),
    }


def _require_session_preflight(preflight: dict[str, Any]) -> None:
    if (
        preflight.get("exact_template_cycle") is True
        and preflight.get("template_cycle_effective")
        != preflight.get("template_cycle")
    ):
        raise RuntimeError(
            "exact template-cycle consent contract changed the displayed topic plan"
        )
    if preflight.get("mode") == "scheduled":
        require_scheduled_prompt_novelty(preflight.get("prompt_novelty") or {})


def _receipt_session_preflight(preflight: dict[str, Any]) -> dict[str, Any]:
    """Remove internal schedule objects while retaining all counts and hash evidence."""

    return {
        key: value
        for key, value in preflight.items()
        if key not in {"schedule", "schedule_entries"}
    }


def _reserve_scheduled_prompt_before_delivery(
    *,
    mode: str,
    prompt_run_claim: PromptRunClaim,
    run_id: str,
    prompt_position: int,
    base_prompt: str,
    remaining_base_prompts: list[str],
) -> dict[str, Any]:
    """Write-ahead consume exactly one scheduled prompt under the OS claim."""

    prompt_run_claim.require_owner(run_id)
    if mode != "scheduled":
        return {}
    delivery_preflight = evaluate_scheduled_prompt_novelty(
        remaining_base_prompts,
        PACKS_DIR,
        PROMPT_USE_RESERVATIONS_DIR,
    )
    require_scheduled_prompt_novelty(delivery_preflight)
    return publish_prompt_use_reservation(
        reservations_dir=PROMPT_USE_RESERVATIONS_DIR,
        prompt_run_claim=prompt_run_claim,
        run_id=run_id,
        prompt_position=prompt_position,
        base_prompt=base_prompt,
        history_snapshot_sha256=delivery_preflight["history_snapshot_sha256"],
        history_pack_snapshot_sha256=delivery_preflight[
            "history_pack_snapshot_sha256"
        ],
        history_reservation_snapshot_sha256=delivery_preflight[
            "history_reservation_snapshot_sha256"
        ],
        planned_prompt_set_sha256=delivery_preflight[
            "planned_prompt_set_sha256"
        ],
    )


def _wait_for_android_worker_return(
    *,
    prompt: str,
    since_epoch: float,
    required: bool,
    timeout: int = 90,
) -> dict[str, Any]:
    deadline = time.time() + (timeout if required else min(12, timeout))
    last_claims: list[dict[str, Any]] = []
    while time.time() < deadline:
        claims = _recent_android_claims(prompt, since_epoch)
        if claims:
            last_claims = claims
            returns = []
            missing = []
            for claim in claims:
                packet_id = str(claim.get("packet_id") or "")
                worker_id = str(claim.get("worker_id") or "")
                returned = _returned_for_packet(packet_id, worker_id)
                if returned:
                    returns.append(returned)
                else:
                    missing.append({"packet_id": packet_id, "worker_id": worker_id})
            if returns and not missing:
                return {
                    "status": "returned",
                    "required": required,
                    "claims": claims,
                    "returns": returns,
                    "claim_count": len(claims),
                    "return_count": len(returns),
                }
            if returns and not required:
                return {
                    "status": "partial_return_not_required",
                    "required": required,
                    "claims": claims,
                    "returns": returns,
                    "missing_returns": missing,
                    "claim_count": len(claims),
                    "return_count": len(returns),
                }
        time.sleep(2.0)
    if last_claims:
        return {
            "status": "claim_without_return",
            "required": required,
            "claims": last_claims,
            "returns": [
                item
                for claim in last_claims
                for item in [_returned_for_packet(str(claim.get("packet_id") or ""), str(claim.get("worker_id") or ""))]
                if item
            ],
            "claim_count": len(last_claims),
            "return_count": sum(
                1
                for claim in last_claims
                if _returned_for_packet(str(claim.get("packet_id") or ""), str(claim.get("worker_id") or ""))
            ),
        }
    return {
        "status": "no_android_assignment_seen" if not required else "required_android_assignment_missing",
        "required": required,
        "claims": [],
        "returns": [],
        "claim_count": 0,
        "return_count": 0,
    }


def _should_retry_lost_build_submission(
    *,
    build_prompt: bool,
    ui_submission_accepted: bool,
    submission_attempts: int,
    now: float,
    probe_deadline: float,
    ct_memory_ok: bool,
    wrapper_seen: bool,
    conical_seen: bool,
) -> bool:
    return bool(
        build_prompt
        and not ui_submission_accepted
        and submission_attempts < 2
        and now >= probe_deadline
        and not ct_memory_ok
        and not wrapper_seen
        and not conical_seen
    )


def send_prompt_through_flutter(
    hwnd: int,
    prompt: str,
    timeout: int,
    index: int,
    run_id: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rect = _rect(hwnd)
    before = time.time()
    try:
        before_diagnostic_offset = FLUTTER_CHAT_DIAGNOSTIC_PATH.stat().st_size
    except OSError:
        before_diagnostic_offset = 0
    before_orders = {path.name for path in _paths_since(ORDER_DIR, before - 2, "MAIN-*.json")}
    before_wrappers = {path.name for path in _paths_since(CHAT_RECEIPT_DIR, before - 2, "ENGEL_UI_CHAT_MEETING_ROOM_*.json")}
    before_local = {path.name for path in _paths_since(CHAT_RECEIPT_DIR, before - 2, "ENGEL_STANDALONE_CHAT_LLM_*.json")}
    before_conical = {
        path.name for path in _paths_since(CONICAL_REPORT_DIR, before - 2, "conical_job_*.json")
    }
    # Engel opens its own Chat surface and types the prompt into the visible
    # composer. No cursor is moved and no keystroke is injected, so the run is
    # unaffected by which window the operator is using.
    delivery = _deliver_prompt(prompt, metadata)
    if delivery.get("accepted") is not True:
        # Return a delivery FAILURE rather than raising. Nothing between here and main()
        # catches this, so a single transient inbox write turned an 8-hour run into an
        # unhandled traceback -- while a turn that WAS delivered and then refused is
        # tolerated up to _MAX_CONSECUTIVE_DELIVERY_FAILURES. The harsher failure was the
        # less resilient one. The shape below carries no wrapper receipt, so
        # _is_delivery_failure() classifies it correctly and two ADJACENT delivery
        # failures still stop the run -- a genuinely broken pipeline is caught, a blip
        # costs one prompt.
        return {
            "status": "FAIL",
            "index": index,
            "run_id": run_id,
            "prompt": prompt,
            "wrapper_receipt_path": "",
            "wrapper_receipt": {},
            "chat_input_delivery_failed": True,
            "detail": (
                f"chat input delivery failed: {delivery.get('status') or 'unknown reason'}"
            ),
        }
    submission_attempts = 1
    time.sleep(0.4)
    # The foreground-owned SendKeys helper submits exactly once with Enter after
    # typing. Do not click the button afterward: it becomes Stop immediately.
    deadline = time.time() + timeout
    build_prompt = _requested_app_build(_operator_request_text(prompt)) is not None
    submission_probe_deadline = min(deadline, time.time() + 60.0)
    ui_submission_accepted = not build_prompt
    wrapper_path = ""
    conical_match: dict[str, Any] = {}
    conical_terminal_failure = False
    conical_terminal_grace_deadline = 0.0
    inbox_result_path = UI_CHAT_INBOX_RESULT_DIR / f"{delivery.get('request_id') or ''}.json"
    inbox_finished_grace_deadline = 0.0
    inbox_finished_status = ""
    while time.time() < deadline:
        if build_prompt:
            latest_conical = _matching_conical_receipt(prompt, before, before_conical)
            if latest_conical.get("ok") is True:
                conical_match = latest_conical
                ui_submission_accepted = True
                if latest_conical.get("terminal_failure") is True:
                    conical_terminal_failure = True
                    if not conical_terminal_grace_deadline:
                        conical_terminal_grace_deadline = min(deadline, time.time() + 20.0)
        if build_prompt and not ui_submission_accepted:
            ui_submission_accepted = bool(_recent_android_claims(prompt, before))
            if not ui_submission_accepted and time.time() >= submission_probe_deadline:
                if submission_attempts < 2:
                    # A build prompt has a fast, durable claim signal. Retype
                    # once only when no claim, wrapper, or CT memory record was
                    # created, which distinguishes a lost UI input from a slow
                    # accepted build without blindly submitting duplicates.
                    ct_memory = _check_ct_persistent_chat_memory(
            prompt, before, base_prompt=str((metadata or {}).get("base_prompt") or "")
        )
                    wrappers = [
                        path
                        for path in _paths_since(
                            CHAT_RECEIPT_DIR,
                            before - 2,
                            "ENGEL_UI_CHAT_MEETING_ROOM_*.json",
                        )
                        if path.name not in before_wrappers
                    ]
                    if _should_retry_lost_build_submission(
                        build_prompt=build_prompt,
                        ui_submission_accepted=ui_submission_accepted,
                        submission_attempts=submission_attempts,
                        now=time.time(),
                        probe_deadline=submission_probe_deadline,
                        ct_memory_ok=ct_memory.get("ok") is True,
                        wrapper_seen=bool(wrappers),
                        conical_seen=conical_match.get("ok") is True,
                    ):
                        retry_delivery = _deliver_prompt(prompt, metadata)
                        # Re-bind the inbox result path: the retry is a NEW request id, and
                        # the fast-fail net watches ONE file. Left pointing at the first id
                        # it waits on a file the app will never write again, so a retried
                        # prompt silently loses the 60s net and burns the full 760s timeout.
                        retry_request_id = retry_delivery.get("request_id") or ""
                        if retry_request_id:
                            inbox_result_path = (
                                UI_CHAT_INBOX_RESULT_DIR / f"{retry_request_id}.json"
                            )
                            inbox_finished_grace_deadline = 0.0
                            inbox_finished_status = ""
                        submission_attempts += 1
                        submission_probe_deadline = min(deadline, time.time() + 60.0)
                        time.sleep(0.4)
                        continue
                break
        wrappers = [path for path in _paths_since(CHAT_RECEIPT_DIR, before - 2, "ENGEL_UI_CHAT_MEETING_ROOM_*.json") if path.name not in before_wrappers]
        if wrappers:
            wrapper_path = str(wrappers[-1])
            break
        ct_memory = _check_ct_persistent_chat_memory(
            prompt, before, base_prompt=str((metadata or {}).get("base_prompt") or "")
        )
        if ct_memory.get("ok") is True:
            wrapper_path = str(_write_ct_memory_chat_receipt(ct_memory, prompt, run_id, index))
            break
        if (
            conical_terminal_failure
            and conical_terminal_grace_deadline
            and time.time() >= conical_terminal_grace_deadline
        ):
            wrapper_path = str(
                _write_conical_terminal_wrapper(conical_match, prompt, run_id, index)
            )
            break
        # The app says this turn is over. Give a receipt still in flight its grace
        # window, then stop rather than spend the rest of the per-prompt budget on
        # a turn that already ended without one.
        if not inbox_finished_grace_deadline:
            finished_record = _inbox_turn_finished(inbox_result_path)
            if finished_record:
                inbox_finished_status = str(
                    finished_record.get("status") or "chat turn finished"
                )
                inbox_finished_grace_deadline = min(
                    deadline, time.time() + UI_CHAT_INBOX_FINISHED_GRACE_SECONDS
                )
        elif time.time() >= inbox_finished_grace_deadline:
            break
        time.sleep(2.0)
    after_orders = [path for path in _paths_since(ORDER_DIR, before - 2, "MAIN-*.json") if path.name not in before_orders]
    after_local = [path for path in _paths_since(CHAT_RECEIPT_DIR, before - 2, "ENGEL_STANDALONE_CHAT_LLM_*.json") if path.name not in before_local]
    orders = [_summarize_order(path) for path in after_orders]
    if not wrapper_path:
        ct_memory = _check_ct_persistent_chat_memory(
            prompt, before, base_prompt=str((metadata or {}).get("base_prompt") or "")
        )
        if ct_memory.get("ok") is True:
            wrapper_path = str(_write_ct_memory_chat_receipt(ct_memory, prompt, run_id, index))
        elif conical_terminal_failure and conical_match.get("ok") is True:
            wrapper_path = str(
                _write_conical_terminal_wrapper(conical_match, prompt, run_id, index)
            )
    wrapper = _summarize_wrapper(Path(wrapper_path)) if wrapper_path else {}
    android_required = _order_uses_android(orders)
    android_worker_return = _wait_for_android_worker_return(
        prompt=prompt,
        since_epoch=before,
        required=android_required,
    )
    creation_job = wrapper.get("creation_job") is True
    chat_only = wrapper.get("chat_only_no_android_or_sub_engel") is True
    meeting_room_used = wrapper.get("agent_meeting_room_used") is True
    build_artifact_verified = wrapper.get("build_artifact_verified") is True
    expected_build_lane = bool(
        wrapper.get("expected_build_lane") is True
        or _requested_app_build(_operator_request_text(prompt)) is not None
    )
    conical_proof = _conical_proof(wrapper) if expected_build_lane else {"ok": True}
    build_proof = _build_proof(wrapper) if expected_build_lane else {"ok": True}
    build_execution_verified = bool(
        build_proof.get("ok") is True
        and (
            wrapper.get("workspace_run_exit_code") == 0
            or build_proof.get("preview_kind") == "web"
        )
    )
    creation_verified = bool(
        creation_job
        and (
            build_artifact_verified
            and build_execution_verified
            and conical_proof.get("ok") is True
            and wrapper.get("persistent_chat_memory_appended") is True
            if expected_build_lane
            else (meeting_room_used or build_artifact_verified)
        )
    )
    status = (
        "DONE"
        if wrapper.get("ok") is True
        and (
            creation_verified
            or (not creation_job and chat_only)
        )
        else "FAIL"
    )
    if android_required and android_worker_return.get("status") != "returned":
        status = "FAIL"
    if wrapper.get("sub_engel_work_requested") is True and wrapper.get("sub_engel_work_returned") is not True:
        status = "FAIL"
    # CT persistence and device receipts can complete before Flutter consumes
    # the long-lived worker result. Require the visible app's own fresh result
    # event before accepting or photographing a completed UI turn.
    flutter_worker_result = _wait_for_flutter_worker_result(
        before_diagnostic_offset,
        timeout=90.0,
    )
    if flutter_worker_result.get("ok") is not True:
        status = "FAIL"
    else:
        time.sleep(1.0)
    screenshot = REPORT_DIR / f"ENGEL_FLUTTER_UI_PROMPT_TRAINING_{run_id}_{index:02d}.png"
    capture_window(hwnd, screenshot)
    return {
        "prompt_index": index,
        "prompt": prompt,
        "status": status,
        "ui_submission_accepted": ui_submission_accepted or bool(wrapper_path),
        "ui_submission_attempts": submission_attempts,
        "duration_seconds": round(time.time() - before, 3),
        "wrapper_receipt": wrapper,
        "wrapper_receipt_path": wrapper_path,
        # Names the "finished, but nothing to grade" case so the log says why the
        # prompt failed instead of showing an unexplained full-timeout FAIL.
        "inbox_turn_finished_without_receipt": bool(
            inbox_finished_grace_deadline and not wrapper_path
        ),
        "inbox_turn_finished_status": inbox_finished_status if not wrapper_path else "",
        "creation_job": creation_job,
        "chat_only_no_android_or_sub_engel": chat_only,
        "agent_meeting_room_used": meeting_room_used,
        "build_artifact_verified": build_artifact_verified,
        "build_execution_verified": build_execution_verified,
        "build_proof": build_proof,
        "conical_proof": conical_proof,
        "conical_receipt_path": str(conical_match.get("path") or ""),
        "conical_terminal_failure": bool(
            conical_terminal_failure or wrapper.get("conical_terminal_failure") is True
        ),
        "ct246_conical_receipt_path": wrapper.get("ct246_conical_receipt_path") or "",
        "ct246_conical_persistence_ok": wrapper.get("ct246_conical_persistence_ok") is True,
        "provider_free_generation": build_proof.get("provider_free") is True,
        "workspace_path": wrapper.get("workspace_path") or "",
        "workspace_files": wrapper.get("workspace_files") or [],
        "workspace_run_ran": wrapper.get("workspace_run_ran"),
        "workspace_run_exit_code": wrapper.get("workspace_run_exit_code"),
        "order_id": wrapper.get("meeting_room_order_id") or (_summarize_order(after_orders[-1]).get("order_id") if after_orders else ""),
        "orders": orders,
        "android_worker_return": android_worker_return,
        "local_llm_receipt_path": str(after_local[-1]) if after_local else str(wrapper.get("workspace_receipt_path") or ""),
        "local_llm_only": wrapper.get("local_llm_only") is True,
        "selected_provider": wrapper.get("selected_provider") or "",
        "provider_api_enabled": wrapper.get("provider_api_enabled") is True,
        "provider_fallback_allowed": wrapper.get("provider_fallback_allowed"),
        "provider_bridge_used": bool(
            wrapper.get("provider_pipeline_used") is True
            or wrapper.get("provider_bridge_fallback_attempted") is True
            or wrapper.get("provider_api_enabled") is True
        ),
        "local_only_training": wrapper.get("local_only_training") is True,
        "training_sample_eligible": wrapper.get("training_sample_eligible") is True,
        "local_semantic_quality": wrapper.get("local_semantic_quality") or {},
        "persistent_chat_memory_appended": wrapper.get("persistent_chat_memory_appended") is True,
        "repeat_guard_triggered": wrapper.get("repeat_guard_triggered") is True,
        "repeat_guard": wrapper.get("repeat_guard", {}),
        "flutter_worker_result": flutter_worker_result,
        "screenshot": str(screenshot),
    }


def _wrapper_receipt_payload(result: dict[str, Any]) -> dict[str, Any]:
    """Load the FULL chat receipt behind a turn. The dict the runner carries is a summary
    (_summarize_wrapper), so fields the summary never copied -- activation_depth, the
    request metadata -- are only readable from the receipt file itself. Returns {} on any
    read problem: a pack row with an unknown depth is still a usable training row."""
    path = str(result.get("wrapper_receipt_path") or "")
    if not path:
        return {}
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _pack_activation_depth(payload: dict[str, Any]) -> int | None:
    """The NT-1 activation depth for a turn, or None when the receipt never stamped one.
    Telemetry only -- it tells a later dataset build WHICH lane produced the sample, which
    is how a 1.5B quick-lane answer can be told apart from a 30B one after the fact."""
    for candidate in (
        payload.get("activation_depth"),
        (payload.get("server_receipt") or {}).get("activation_depth")
        if isinstance(payload.get("server_receipt"), dict)
        else None,
    ):
        if isinstance(candidate, bool):
            continue
        if isinstance(candidate, int):
            return candidate
    return None


def _slm_admit_prediction(base_prompt: str, reply: str) -> dict[str, Any] | None:
    """Shadow admit prediction from the receipt-trained SLM roster, or None.

    ADVISORY ONLY: nothing here can move `admit` -- the deterministic rule owns that
    verdict, and a model grading its own training data as authoritative is exactly the
    leakage the roster's gates exist to stop. The runtime is asked ONLY when it is already
    warm, because writing a pack must never pay a model load, and every failure answers
    None so a renamed or absent head can never cost a training run its pack.
    """
    try:
        import engel_slm_runtime

        runtime = engel_slm_runtime.get_slm_runtime()
        is_ready = getattr(runtime, "is_ready", None)
        if not callable(is_ready) or is_ready() is not True:
            return None
        predict = getattr(runtime, "admit_score", None)
        if not callable(predict):
            return None
        prediction = predict(str(base_prompt or ""), str(reply or ""))
        return prediction if isinstance(prediction, dict) else None
    except Exception:  # noqa: BLE001 -- advisory absent, never blocks a pack
        return None


def _demote_duplicate_replies(rows: list[dict[str, Any]]) -> int:
    """Keep ONE admitted row per distinct reply; demote the rest. Returns the count demoted.

    (2026-08-06) Nothing deduplicated a run's own output. When a lane degrades it emits the
    SAME canned text for prompt after prompt -- an 8-prompt probe once returned one
    byte-identical 280-char refusal seven times -- and each copy became its own pack row.

    The CT-side SFT builder cannot absorb this: it keys on `user` (the base prompt), so
    identical replies to DIFFERENT prompts have different keys by construction and all
    survive. Measured on pack 20260801T182953615428Z: 14 admitted rows, 14 distinct builder
    keys, but only 5 distinct replies -- 9 redundant copies reaching training.

    This has to live here rather than in `_pack_admit_verdict`, which takes a single row and
    is structurally blind to its siblings. Duplicates are DEMOTED, never dropped: the row
    stays in the pack as evidence that the lane repeated itself, which is exactly the
    symptom worth seeing in a receipt.

    (2026-08-08) Byte-identity proved too narrow: live construction run 5188cd2f repeated
    one answer across three prompts at 0.90-0.96 similarity (same opener, same sourced
    facts, tail lightly reworded) and every copy passed the hash check. Same-topic answers
    legitimately share the contract's mandated opener (measured 0.66-0.69 within a cycle),
    so near-duplicate now means >= 0.90 SequenceMatcher ratio against an earlier admitted
    reply that shares the same normalised 240-char opener."""
    from difflib import SequenceMatcher

    seen: dict[str, int] = {}
    buckets: dict[str, list[tuple[str, int]]] = {}
    demoted = 0
    for row in rows:
        if row.get("admit") is not True:
            continue
        # Normalised so trivial whitespace/case differences do not defeat the check.
        norm = " ".join(str(row.get("assistant_reply") or "").split()).casefold()
        key = hashlib.sha256(norm.encode("utf-8")).hexdigest()
        first = seen.get(key)
        if first is None:
            loose = " ".join(re.sub(r"[^a-z0-9 ]+", " ", norm).split())
            bucket = buckets.setdefault(loose[:240], [])
            near = next((idx for prior, idx in bucket
                         if SequenceMatcher(None, loose, prior).ratio() >= 0.90), None)
            if near is None:
                seen[key] = row.get("prompt_index")
                bucket.append((loose, row.get("prompt_index")))
                continue
            first, kind = near, "near-duplicate (>= 0.90 similar)"
        else:
            kind = "byte-identical"
        row["admit"] = False
        row["training_sample_eligible"] = False
        row["discipline_eligibility_ok"] = False
        row["duplicate_of_prompt_index"] = first
        row["admit_reason"] = (
            f"reply is {kind} to prompt {first} in this run -- kept as evidence, "
            "not captured twice"
        )
        demoted += 1
    return demoted


def _pack_admit_verdict(
    result: dict[str, Any],
    *,
    base_prompt: str,
    reply: str,
    contract_echo: bool,
) -> tuple[bool, str]:
    """THE admit rule for a pack row -- one place, checked in order, first failure wins.

    This does not re-grade the answer: the per-turn discipline gate already did that and
    its verdict is consumed here. What this adds is the provenance and floor conditions a
    dataset builder cannot check for itself once the row leaves the runner (was the turn
    served, was it local, is there a real unwrapped ask, is there enough reply to learn
    from). Fail-closed: anything unverifiable is not admitted.
    """
    if result.get("status") != "DONE":
        return False, f"turn status was {result.get('status')!r}, not DONE -- never served cleanly"
    if result.get("provider_bridge_used") is True or result.get("provider_api_enabled") is True:
        return False, "turn escalated to an external provider/bridge -- never a local training sample"
    if result.get("local_only_training") is not True:
        # CT246's own stamp that this turn was served under the local-only guard. Absence of
        # the stamp is not proof of a provider -- it is the absence of proof of anything, and
        # the dataset builder refuses such a row anyway. Admitting it here would only make the
        # pack's admitted count overstate what actually reaches training, which is the one
        # number this whole loop exists to make honest. Measured on the 20260801 session: every
        # DONE turn carried the stamp, so this costs a healthy run nothing.
        return False, "CT246 did not stamp the turn as local-only training -- provenance unproven"
    provider = str(result.get("selected_provider") or "").strip().casefold()
    if provider not in SAFE_PROMPT_TRAINING_CHAT_PROVIDERS:
        return False, f"provider {provider or '<missing>'} is not an approved prompt-training chat lane"
    if (
        result.get("creation_job") is True
        or result.get("chat_only_no_android_or_sub_engel") is not True
        or result.get("agent_meeting_room_used") is True
        or bool(str(result.get("workspace_path") or "").strip())
    ):
        return False, "turn used an action, workspace, build, or Meeting Room lane -- not chat training"
    # Discipline first, deliberately. Both flags go False together when a domain gate
    # refuses a turn, and only the discipline reason names WHICH habit the answer drifted
    # into ("8 of 9 lines are bullets") -- the generic flag reason names none. That
    # sentence is the pack's whole feedback channel: it is what a human reads when asking
    # why a session captured little, so the specific reason has to win the tie.
    if result.get("discipline_eligibility_ok") is False:
        return False, str(
            result.get("discipline_eligibility_reason")
            or "turn failed its discipline eligibility gate"
        )
    if result.get("training_sample_eligible") is not True:
        return False, "turn was not marked training_sample_eligible by its grading"
    if contract_echo:
        return False, "reply restates the answer contract instead of answering"
    if not str(base_prompt or "").strip():
        return False, "no unwrapped base prompt recorded -- nothing safe to train on"
    if len(str(reply or "").strip()) < PACK_MIN_REPLY_CHARS:
        return (
            False,
            f"reply is under the {PACK_MIN_REPLY_CHARS}-character floor for a teachable turn",
        )
    return True, "served locally, graded eligible, real base prompt and a substantive reply"


def _publish_immutable_bytes(path: Path, body_bytes: bytes) -> str:
    """Atomically publish exact bytes at a unique, read-only historical path."""

    if not isinstance(body_bytes, bytes):
        raise TypeError("immutable artifact body must be exact bytes")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise RuntimeError(f"refusing immutable artifact overwrite: {path}")
    temporary = path.parent / f".{path.name}.{os.getpid()}.{time.time_ns()}.tmp"
    linked = False
    try:
        with temporary.open("xb") as handle:
            handle.write(body_bytes)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
        linked = True
        temporary.unlink()
        os.chmod(path, 0o444)
    except Exception:
        if linked and path.exists():
            try:
                os.chmod(path, 0o600)
                path.unlink()
            except OSError:
                pass
        raise
    finally:
        if temporary.exists():
            try:
                os.chmod(temporary, 0o600)
                temporary.unlink()
            except OSError:
                pass
    return hashlib.sha256(body_bytes).hexdigest()


def _publish_immutable_training_pack(path: Path, body: str) -> str:
    """Atomically publish one uniquely named, read-only historical JSONL pack."""

    return _publish_immutable_bytes(path, body.encode("utf-8"))


def _publish_immutable_json(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    """Publish canonical JSON once and return its exact byte binding."""

    body = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    return {
        "path": str(path.resolve()),
        "name": path.name,
        "sha256": _publish_immutable_bytes(path, body),
        "bytes": len(body),
        "mode": "0444",
    }


def _capture_pack_writer_source(
    source_path: Path | None = None,
) -> dict[str, Any]:
    """Capture the exact writer bytes loaded for this process.

    The default snapshot is taken once while this module imports. Tests may inject a
    workspace-local copy so an A-to-B mutation can be exercised without touching the
    real runner source.
    """

    declared_source = Path(source_path) if source_path is not None else Path(__file__)
    if declared_source.is_symlink():
        raise RuntimeError("prompt-training writer source must not be a symlink")
    source = declared_source.resolve(strict=True)
    root = ROOT.resolve()
    try:
        relative = source.relative_to(root).as_posix()
    except ValueError as exc:
        raise RuntimeError("prompt-training writer source is outside the Engel root") from exc
    if not source.is_file():
        raise RuntimeError("prompt-training writer source is not a regular canonical file")
    source_bytes = source.read_bytes()
    return {
        "source_relative_path": relative,
        "source_path": str(source),
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "source_bytes": len(source_bytes),
        "_exact_source_bytes": source_bytes,
    }


_PACK_WRITER_SOURCE_SNAPSHOT = _capture_pack_writer_source()


def _pack_writer_identity(
    run_id: str,
    *,
    source_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Bind a pack to the unchanged runner bytes this process loaded."""

    captured = (
        source_snapshot
        if source_snapshot is not None
        else _PACK_WRITER_SOURCE_SNAPSHOT
    )
    source = Path(str(captured.get("source_path") or ""))
    expected_bytes = captured.get("_exact_source_bytes")
    if not isinstance(expected_bytes, bytes):
        raise RuntimeError("prompt-training writer source snapshot is incomplete")
    if source.is_symlink():
        raise RuntimeError("prompt-training writer source changed to a symlink")
    try:
        resolved = source.resolve(strict=True)
        current_bytes = resolved.read_bytes()
    except OSError as exc:
        raise RuntimeError("prompt-training writer source is unavailable at publication") from exc
    if (
        str(resolved) != str(captured.get("source_path") or "")
        or current_bytes != expected_bytes
        or len(current_bytes) != int(captured.get("source_bytes") or -1)
        or hashlib.sha256(current_bytes).hexdigest()
        != str(captured.get("source_sha256") or "")
    ):
        raise RuntimeError(
            "prompt-training writer source changed after module import; "
            "refusing pack publication"
        )
    return {
        "schema": PACK_WRITER_IDENTITY_SCHEMA,
        "run_id": run_id,
        "entrypoint": "write_training_pack",
        "source_relative_path": str(captured["source_relative_path"]),
        "source_path": str(captured["source_path"]),
        "source_sha256": str(captured["source_sha256"]),
        "source_bytes": int(captured["source_bytes"]),
        "captured_at": "module_import",
        "completion_reverified": True,
    }


def write_training_pack(receipt: dict[str, Any]) -> dict[str, Any]:
    """Emit this session's TRAINING PACK: one JSONL row per replying turn plus a LATEST
    receipt, under memory/training/packs.

    The pack is the only artifact of a prompt-training run that a dataset build can admit,
    so it carries the admit verdict AND the rejected turns: dropping the rejects would hand
    the SLM roster a positive-only corpus and every classifier trained on it would learn to
    say yes. Rows are written atomically because a half-written JSONL read by the daily
    dataset build is a silent corpus corruption, not a visible failure.
    """
    if PACKS_DIR.drive.lower() == "c:":
        raise RuntimeError(f"refusing to write Engel training packs on C: {PACKS_DIR}")
    PACKS_DIR.mkdir(parents=True, exist_ok=True)
    if PACKS_DIR.is_symlink() or not PACKS_DIR.is_dir():
        raise RuntimeError(f"training pack root is not a canonical directory: {PACKS_DIR}")
    packs_root = PACKS_DIR.resolve()
    run_id = str(receipt.get("run_id") or "")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,159}", run_id):
        raise RuntimeError("training pack requires one filesystem-safe run id")
    created_at = iso_now()
    discipline_default = str(
        (receipt.get("summary") or {}).get("training_discipline") or "aec"
    )
    curriculum_template = str(receipt.get("template_path") or "")
    binding = receipt.get("curriculum_binding")
    if not isinstance(binding, dict) or binding.get("schema") != CURRICULUM_BINDING_SCHEMA:
        raise RuntimeError("training pack requires a canonical curriculum binding")
    current_binding = _load_canonical_curriculum_binding(curriculum_template)
    if binding != current_binding:
        raise RuntimeError("training pack curriculum binding is stale or inconsistent")
    scheduled_hours = int(receipt.get("scheduled_hours") or 0)
    trainings_per_hour = int(receipt.get("trainings_per_hour") or 0)
    session_start_index = int(receipt.get("start_index") or 1)
    pack_path = packs_root / f"ENGEL_PROMPT_TRAINING_PACK_{run_id}.jsonl"
    pack_receipt_path = pack_path.with_suffix(PACK_RECEIPT_SUFFIX)
    session_receipt_path = packs_root / f"{PACK_SESSION_PREFIX}{run_id}.json"
    writer_identity = _pack_writer_identity(run_id)
    session_evidence = {
        "schema": PACK_SESSION_EVIDENCE_SCHEMA,
        "run_id": run_id,
        "created_at_utc": created_at,
        "writer": dict(writer_identity),
        "session": receipt,
    }
    session_binding = _publish_immutable_json(
        session_receipt_path,
        session_evidence,
    )
    session_receipt = str(session_binding["path"])
    rows: list[dict[str, Any]] = []
    by_discipline: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for result in receipt.get("prompt_results") or []:
        if not isinstance(result, dict):
            continue
        reply = _wrapper_reply_text(result)
        if not str(reply).strip():
            # No reply means no turn to learn from -- not a rejected sample, just absent.
            continue
        payload = _wrapper_receipt_payload(result)
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        base_prompt = str(
            result.get("base_prompt")
            or metadata.get("base_prompt")
            or payload.get("base_prompt")
            or ""
        ).strip()
        delivered_prompt = str(
            result.get("delivered_prompt") or result.get("prompt") or ""
        )
        contract_echo = _looks_like_contract_echo(" ".join(str(reply).split()).casefold())
        admit, admit_reason = _pack_admit_verdict(
            result,
            base_prompt=base_prompt,
            reply=reply,
            contract_echo=contract_echo,
        )
        # Keep the rejected audit row even when an older wrapper did not preserve the
        # unwrapped ask.  Absence is not hashable novelty evidence, so the hash stays
        # explicitly empty and the existing fail-closed admit reason remains authoritative.
        base_prompt_sha256 = (
            canonical_base_prompt_sha256(base_prompt) if base_prompt else ""
        )
        discipline = str(result.get("discipline") or discipline_default).strip().casefold()
        status = str(result.get("status") or "")
        rows.append(
            {
                "schema": PACK_ROW_SCHEMA,
                "run_id": run_id,
                "created_at_utc": created_at,
                "session_receipt": session_receipt,
                "session_receipt_sha256": session_binding["sha256"],
                "pack_receipt": str(pack_receipt_path.resolve()),
                "pack_writer_source_sha256": writer_identity["source_sha256"],
                "prompt_index": int(result.get("prompt_index") or 0),
                "discipline": discipline,
                "curriculum_template": curriculum_template,
                "curriculum_id": binding["curriculum_id"],
                "curriculum_title": binding["curriculum_title"],
                "curriculum_material_version": binding["material_version"],
                "curriculum_template_path": binding["template_path"],
                "curriculum_template_sha256": binding["template_sha256"],
                "material_topic": str(result.get("material_topic") or ""),
                "training_level": str(
                    result.get("training_level") or receipt.get("training_level") or ""
                ),
                "training_targets": str(receipt.get("training_targets") or ""),
                "scheduled_hours": scheduled_hours,
                "trainings_per_hour": trainings_per_hour,
                "session_start_index": session_start_index,
                "scheduled_hour": result.get("scheduled_hour"),
                "base_prompt": base_prompt,
                "delivered_prompt": delivered_prompt,
                "assistant_reply": str(reply),
                "base_prompt_sha256": base_prompt_sha256,
                "base_prompt_hash_canonicalization": (
                    "unicode_nfkc_casefold_collapsed_whitespace_v1"
                ),
                "prompt_sha256": hashlib.sha256(
                    delivered_prompt.encode("utf-8")
                ).hexdigest(),
                "status": status,
                "admit": bool(admit),
                "admit_reason": admit_reason,
                "training_sample_eligible": result.get("training_sample_eligible") is True,
                "discipline_eligibility_ok": result.get("discipline_eligibility_ok"),
                "local_only_training": result.get("local_only_training") is True,
                "selected_provider": str(result.get("selected_provider") or ""),
                "response_kind": (
                    "chat"
                    if result.get("chat_only_no_android_or_sub_engel") is True
                    and result.get("creation_job") is not True
                    else "action"
                ),
                "action_lane_used": bool(
                    result.get("creation_job") is True
                    or result.get("chat_only_no_android_or_sub_engel") is not True
                    or result.get("agent_meeting_room_used") is True
                    or str(result.get("workspace_path") or "").strip()
                ),
                "contract_echo": bool(contract_echo),
                # Which grading this row received. An arithmetic answer checked against a
                # known result and a proof graded on form are NOT equally proven, and a
                # corpus that cannot tell them apart cannot weight them apart.
                "math_truth_verdict": result.get("math_truth_verdict") or "",
                "math_exactly_verified": bool(result.get("math_exactly_verified")),
                # (2026-08-08) The code and aec verdicts were stamped on the RESULT but
                # never copied here, so the corpus could not weight execution-verified
                # code or corpus-verified citations apart from form-graded rows -- the
                # exact blindness the math fields were added to remove.
                "code_truth_verdict": result.get("code_truth_verdict") or "",
                "code_exactly_verified": bool(result.get("code_exactly_verified")),
                "aec_citation_verdict": result.get("aec_citation_verdict") or "",
                "aec_exactly_verified": bool(result.get("aec_exactly_verified")),
                "aec_claim_support_verified": bool(
                    result.get("aec_claim_support_verified")
                ),
                "aec_document_scope": list(result.get("aec_document_scope") or []),
                "aec_support": list(result.get("aec_support") or []),
                "aec_corpus_bundle_sha256": str(
                    result.get("aec_corpus_bundle_sha256")
                    or result.get("aec_evidence_bundle_sha256")
                    or ""
                ),
                "activation_depth": _pack_activation_depth(payload),
                "wrapper_receipt_path": str(result.get("wrapper_receipt_path") or ""),
                "slm_admit_prediction": _slm_admit_prediction(base_prompt, reply),
            }
        )
        by_discipline[discipline] = by_discipline.get(discipline, 0) + 1
        by_status[status] = by_status.get(status, 0) + 1
    _demote_duplicate_replies(rows)
    body = "".join(
        json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows
    )
    body_bytes = body.encode("utf-8")
    pack_sha256 = _publish_immutable_training_pack(pack_path, body)
    admitted = sum(1 for row in rows if row["admit"] is True)
    prompt_indexes = sorted(
        {
            int(row.get("prompt_index") or 0)
            for row in rows
            if int(row.get("prompt_index") or 0) > 0
        }
    )
    pack_binding = {
        "path": str(pack_path.resolve()),
        "name": pack_path.name,
        "sha256": pack_sha256,
        "bytes": len(body_bytes),
        "rows": len(rows),
        "mode": "0444",
    }
    stamped_receipt = {
        "schema": PACK_STAMPED_RECEIPT_SCHEMA,
        "run_id": run_id,
        "created_at_utc": created_at,
        "receipt_path": str(pack_receipt_path.resolve()),
        "writer": dict(writer_identity),
        "pack": pack_binding,
        "session": {
            **session_binding,
            "schema": PACK_SESSION_EVIDENCE_SCHEMA,
            "run_id": run_id,
        },
        "curriculum_binding": dict(binding),
        "schedule": {
            "mode": str(receipt.get("mode") or ""),
            "scheduled_hours": scheduled_hours,
            "trainings_per_hour": trainings_per_hour,
            "session_start_index": session_start_index,
            "training_targets": str(receipt.get("training_targets") or ""),
            "training_level": str(receipt.get("training_level") or ""),
            "template_cycle": int(receipt.get("template_cycle") or 1),
            "exact_template_cycle": bool(receipt.get("exact_template_cycle")),
            "expected_plan_prompt_count": scheduled_hours * trainings_per_hour,
            "row_count": len(rows),
            "prompt_index_count": len(prompt_indexes),
            "prompt_index_min": min(prompt_indexes) if prompt_indexes else None,
            "prompt_index_max": max(prompt_indexes) if prompt_indexes else None,
            "global_prompt_indexes": prompt_indexes,
            "hourly_cycles": list(receipt.get("hourly_cycles") or []),
        },
    }
    stamped_receipt_binding = _publish_immutable_json(
        pack_receipt_path,
        stamped_receipt,
    )
    latest = {
        "schema": PACK_RECEIPT_SCHEMA,
        "run_id": run_id,
        "created_at_utc": created_at,
        "pack_path": pack_binding["path"],
        "pack_sha256": pack_sha256,
        "pack_bytes": len(body_bytes),
        "pack_immutable": True,
        "pack_mode": "0444",
        "stamped_pack_receipt": stamped_receipt_binding["path"],
        "stamped_pack_receipt_sha256": stamped_receipt_binding["sha256"],
        "stamped_pack_receipt_bytes": stamped_receipt_binding["bytes"],
        "writer": dict(writer_identity),
        "base_prompt_hash_canonicalization": (
            "unicode_nfkc_casefold_collapsed_whitespace_v1"
        ),
        "session_receipt": session_receipt,
        "session_receipt_sha256": session_binding["sha256"],
        "session_receipt_bytes": session_binding["bytes"],
        "discipline": discipline_default,
        "curriculum_template": curriculum_template,
        "curriculum_binding": dict(binding),
        "curriculum_id": binding["curriculum_id"],
        "curriculum_title": binding["curriculum_title"],
        "curriculum_material_version": binding["material_version"],
        "curriculum_template_path": binding["template_path"],
        "curriculum_template_sha256": binding["template_sha256"],
        "training_level": str(receipt.get("training_level") or ""),
        "training_targets": str(receipt.get("training_targets") or ""),
        "scheduled_hours": scheduled_hours,
        "trainings_per_hour": trainings_per_hour,
        "session_start_index": session_start_index,
        "rows": len(rows),
        "admitted": admitted,
        "rejected": len(rows) - admitted,
        "by_discipline": by_discipline,
        "by_status": by_status,
        "ct_pack_dir": CT_PACK_DIR,
    }
    latest_path = PACKS_DIR / PACK_LATEST_NAME
    temp_latest = latest_path.parent / (latest_path.name + ".tmp")
    temp_latest.write_text(
        json.dumps(latest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temp_latest, latest_path)
    return {
        **latest,
        "latest_receipt_path": str(latest_path.resolve()),
    }


def _run_training_claimed(
    prompt_run_claim: PromptRunClaim,
    run_id: str,
    *,
    mode: str,
    minutes: float,
    per_prompt_timeout: int,
    final_wait: bool,
    template_path: str | None = None,
    template_cycle: int = 1,
    exact_template_cycle: bool = False,
    fresh_chat: bool = False,
    start_index: int = 1,
    local_only: bool = False,
    scheduled_hours: int = 1,
    training_level: str = "medium",
    training_targets: str = "slm,llm",
    trainings_per_hour: int = DEFAULT_TRAININGS_PER_HOUR,
    back_to_back: bool = False,
    gpu_server_freshness: dict[str, Any] | None = None,
    prepared_session_preflight: dict[str, Any] | None = None,
    wrapper_pid: int = 0,
    launcher_log: str = "",
    lifecycle_receipt: str = "",
) -> dict[str, Any]:
    # No UI, guard, pack, or service-adjacent action is permitted unless this exact
    # process and run_id still own the kernel-released claim.
    prompt_run_claim.require_owner(run_id)
    scheduled_hours = validate_training_hours(scheduled_hours)
    training_level = validate_training_level(training_level)
    training_targets = validate_training_targets(training_targets)
    trainings_per_hour = validate_trainings_per_hour(trainings_per_hour)
    if prepared_session_preflight is not None:
        _require_session_preflight(prepared_session_preflight)
        expected_configuration = {
            "mode": mode,
            "template_path": template_path or "",
            "template_cycle": int(template_cycle),
            "exact_template_cycle": bool(exact_template_cycle),
            "scheduled_hours": int(scheduled_hours),
            "training_level": training_level,
            "trainings_per_hour": int(trainings_per_hour),
            "start_index": max(1, int(start_index)),
        }
        if any(
            prepared_session_preflight.get(key) != value
            for key, value in expected_configuration.items()
        ):
            raise RuntimeError(
                "prepared prompt novelty preflight does not match the requested run"
            )
    # Rebuild and re-read the pack snapshot at the final boundary.  main() performs the
    # first check before optional GPU refresh; this second check prevents a pack that lands
    # during that preflight from making the subsequent UI delivery a replay.
    session_preflight = _prepare_session_preflight(
        mode=mode,
        template_path=template_path,
        template_cycle=template_cycle,
        scheduled_hours=scheduled_hours,
        training_level=training_level,
        trainings_per_hour=trainings_per_hour,
        start_index=start_index,
        exact_template_cycle=exact_template_cycle,
    )
    # This call is intentionally before ensure_dirs, write_plan, window discovery,
    # screenshots, local-only guards, GPU work, or prompt delivery.  A repeated prompt
    # must stop a scheduled run while it is still a read-only plan.
    _require_session_preflight(session_preflight)
    if prepared_session_preflight is not None:
        early_novelty = prepared_session_preflight.get("prompt_novelty") or {}
        current_novelty = session_preflight.get("prompt_novelty") or {}
        session_preflight["early_preflight"] = {
            "decision": early_novelty.get("decision"),
            "planned_prompt_set_sha256": early_novelty.get(
                "planned_prompt_set_sha256"
            ),
            "history_pack_snapshot_sha256": early_novelty.get(
                "history_pack_snapshot_sha256"
            ),
            "history_snapshot_sha256": early_novelty.get(
                "history_snapshot_sha256"
            ),
            "history_snapshot_changed_before_ui": early_novelty.get(
                "history_snapshot_sha256"
            )
            != current_novelty.get("history_snapshot_sha256"),
        }
    training_schedule = session_preflight["schedule"]
    all_entries = training_schedule["entries"]
    start_index = int(session_preflight["start_index"])
    schedule_entries = session_preflight["schedule_entries"]
    requested = len(schedule_entries)
    ensure_dirs()
    write_plan()
    hwnd, pid, process_path = _ensure_window()
    if fresh_chat:
        _start_fresh_chat(hwnd)
    before_shot = REPORT_DIR / f"ENGEL_FLUTTER_UI_PROMPT_TRAINING_{run_id}_before.png"
    capture_window(hwnd, before_shot)
    started_epoch = time.time()
    started_mono = time.monotonic()
    level_profile = training_schedule["level_profile"]
    local_only_guard: dict[str, Any] = {}
    if local_only:
        # Refuse to spend an hour teaching Engel invented facts about itself. If the
        # chat turn is not carrying Engel's real context, the local model does not
        # fail loudly -- it fabricates a plausible product with confident fake
        # sources -- so prove grounding once, up front, and stop here if it is gone.
        grounding = _verify_chat_grounding()
        if grounding.get("ok") is not True:
            raise RuntimeError(
                "chat grounding gate failed, refusing to train on ungrounded self-facts: "
                + str(grounding.get("detail") or "see verify_engel_chat_grounding.py")
            )
        guard_seconds = max(
            minutes * 60.0,
            float(per_prompt_timeout * requested),
        ) + 900.0
        local_only_guard = _activate_local_only_guard(
            run_id,
            started_epoch + guard_seconds,
            prompt_run_claim=prompt_run_claim,
            scheduled_hours=scheduled_hours,
            requested_minutes=minutes,
            training_level=training_level,
            training_targets=training_targets,
            level_profile=level_profile,
            trainings_per_hour=trainings_per_hour,
            cadence_seconds=3600.0 / trainings_per_hour,
            wrapper_pid=wrapper_pid,
            launcher_log=launcher_log,
            lifecycle_receipt=lifecycle_receipt,
        )
    deadline = started_mono + max(1.0, minutes * 60.0)
    # Idle pacing still stops at `deadline`. Starting a prompt that was already
    # in the plan is allowed a little past that window: a turn that runs longer
    # than its cadence slot used to drop the tail (live: 18 of 20).
    send_deadline = deadline + max(60, int(per_prompt_timeout)) * 3
    paced_mode = mode in {"scheduled", "one-hour", "two-hour", "four-hour"}
    # Operator preference: no idle pacing -- work back-to-back rather than sleeping
    # between items. A scheduled 10/hour run spends ~15s per prompt on the GPU and
    # then idles ~345s, so the RTX 2070 sits unused ~96% of the wall clock and the
    # run "looks like the GPU is doing nothing". Back-to-back keeps the card busy and
    # finishes the same prompt set in minutes. Off by default so the Training page's
    # "about one every N minutes" stays truthful unless this is explicitly asked for.
    if back_to_back:
        paced_mode = False
    interval = (
        3600.0 / trainings_per_hour
        if mode == "scheduled"
        else (minutes * 60.0 / max(1, requested))
        if paced_mode
        else 0.0
    )
    results: list[dict[str, Any]] = []
    blockers: list[str] = []
    run_discipline = str(training_schedule.get("discipline") or "aec")
    consecutive_delivery_failures = 0
    consecutive_nondone = 0
    print(
        json.dumps(
            {
                "event": "flutter_training_started",
                "run_id": run_id,
                "prompt_run_claim": prompt_run_claim.owner_record,
                "mode": mode,
                "scheduled_hours": scheduled_hours,
                "requested_minutes": minutes,
                "training_level": training_level,
                "training_level_profile": level_profile["profile_id"],
                "training_level_guidance": level_profile["guidance"],
                "trainings_per_hour": trainings_per_hour,
                "cadence_seconds": interval,
                "hourly_cycle_count": len(training_schedule["hourly_cycles"]),
                "hourly_cycles": training_schedule["hourly_cycles"],
                "start_index": start_index,
                "plan_prompts": len(all_entries),
                "requested_prompts": requested,
                "prompt_novelty_decision": (
                    session_preflight["prompt_novelty"].get("decision")
                ),
                "history_unique_prompt_count": (
                    session_preflight["prompt_novelty"].get(
                        "history_unique_prompt_count"
                    )
                ),
                "history_pack_snapshot_sha256": (
                    session_preflight["prompt_novelty"].get(
                        "history_pack_snapshot_sha256"
                    )
                ),
                "history_snapshot_sha256": (
                    session_preflight["prompt_novelty"].get(
                        "history_snapshot_sha256"
                    )
                ),
                "history_valid_reservation_count": (
                    session_preflight["prompt_novelty"].get(
                        "history_valid_reservation_count"
                    )
                ),
            },
            sort_keys=True,
        ),
        flush=True,
    )
    for offset, schedule_entry in enumerate(schedule_entries):
        index = start_index + offset
        prompt = str(schedule_entry["prompt"])
        prompt_to_send = prompt
        if (
            offset == 0
            and start_index > 1
            and _requested_app_build(_operator_request_text(prompt)) is not None
            and "overwrite" not in prompt.casefold()
        ):
            prompt_to_send = f"Overwrite and rebuild this request: {prompt}"
        if time.monotonic() >= send_deadline:
            blockers.append(f"{mode} deadline reached before all prompts were sent")
            break
        if offset > 0 or start_index > 1:
            _close_previous_build_preview(hwnd)
        print(
            json.dumps(
                {
                    "event": "flutter_prompt_started",
                    "run_id": run_id,
                    "mode": mode,
                    "index": index,
                    "position": offset + 1,
                    "start_index": start_index,
                    "plan_prompts": len(all_entries),
                    "requested": requested,
                    "scheduled_hours": scheduled_hours,
                    "scheduled_hour": schedule_entry["scheduled_hour"],
                    "template_cycle": schedule_entry["template_cycle"],
                    "source_prompt_index": schedule_entry["source_prompt_index"],
                    "material_topic": schedule_entry["material_topic"],
                    "training_level": training_level,
                    "training_level_profile": level_profile["profile_id"],
                    "training_level_guidance": level_profile["guidance"],
                    "trainings_per_hour": trainings_per_hour,
                    "cadence_seconds": interval,
                    "seconds_to_deadline": int(
                        max(0, deadline - time.monotonic())
                    ),
                },
                sort_keys=True,
            ),
            flush=True,
        )
        # The selected wall-clock duration is authoritative. Previously the last
        # prompt always received the full per-prompt timeout (760 seconds in the
        # launcher), so a five-hour plan could silently run more than twelve
        # minutes past its promised window. Bound every turn by the time that is
        # actually left; the runner can still write its final receipt afterward.
        remaining_seconds = max(1, math.ceil(send_deadline - time.monotonic()))
        prompt_timeout = min(per_prompt_timeout, remaining_seconds)
        prompt_use_reservation = _reserve_scheduled_prompt_before_delivery(
            mode=mode,
            prompt_run_claim=prompt_run_claim,
            run_id=run_id,
            prompt_position=index,
            base_prompt=str(schedule_entry["base_prompt"]),
            remaining_base_prompts=[
                str(item["base_prompt"]) for item in schedule_entries[offset:]
            ],
        )
        turn_metadata = {
            # Trusted local signal for the Governor: routing (capable lane
            # for non-interactive discipline turns) + memory hygiene
            # (persist base ask, withhold the turn from later context).
            "training_discipline": schedule_entry["discipline"],
            "training_run_id": run_id,
            "interactive": False,
            "persist_policy": "training",
            "base_prompt": schedule_entry["base_prompt"],
            "aec_expected_documents": schedule_entry.get(
                "aec_expected_documents", []
            ),
            "aec_evidence_bundle_sha256": schedule_entry.get(
                "aec_evidence_bundle_sha256", ""
            ),
        }
        result = send_prompt_through_flutter(
            hwnd,
            prompt_to_send,
            prompt_timeout,
            index,
            run_id,
            metadata=turn_metadata,
        )
        retry_reason = ""
        if paced_mode:
            if _is_delivery_failure(result):
                retry_reason = "delivery_failure"
            elif _is_style_gate_exhaust(result):
                # (2026-08-16) same seam, second trigger: a served style-gate
                # exhaust is generation nondeterminism, not a content refusal -
                # one re-ask of the same position usually passes the gate.
                retry_reason = "style_gate_exhaust"
        if retry_reason:
            # (2026-08-14) One bounded retry of the SAME prompt before a delivery
            # failure counts toward the early-stop streak. Live: the 70-prompt
            # Construction run died at 39/70 because prompts 41 and 42 both hit the
            # same transient - CT answered (POST /chat/stream 200, worker exit 0)
            # but the app's Meeting Room wrapper receipt never appeared inside the
            # grace window - and _MAX_CONSECUTIVE_DELIVERY_FAILURES=2 ended a 7-hour
            # schedule over two adjacent blips (prompt 2 burned the same way alone).
            # Ledger-safe: this prompt's write-ahead reservation is already
            # published, so re-delivering the SAME position needs no new reservation
            # and cannot trip the novelty judge. Bounded: fixed backoff, and only
            # when enough wall budget remains that the retry cannot eat the plan.
            retry_backoff_seconds = 45
            budget_after_backoff = deadline - time.monotonic() - retry_backoff_seconds
            if budget_after_backoff > 120:
                print(
                    json.dumps(
                        {
                            "event": "delivery_failure_retry",
                            "run_id": run_id,
                            "index": index,
                            "reason": retry_reason,
                            "backoff_seconds": retry_backoff_seconds,
                            "first_attempt_status": result.get("status"),
                            "seconds_to_deadline": int(max(0, deadline - time.monotonic())),
                        },
                        sort_keys=True,
                    ),
                    flush=True,
                )
                if retry_reason == "delivery_failure":
                    # a dead backend makes the retry a guaranteed second failure;
                    # wait the outage out (bounded) before spending it.
                    try:
                        outage_wait_cap = int(
                            os.environ.get("ENGEL_TRAINING_OUTAGE_WAIT_SECONDS", "900")
                            or "900"
                        )
                    except ValueError:
                        outage_wait_cap = 900
                    outage = _wait_out_chat_outage(deadline, outage_wait_cap)
                    if outage["outage_detected"]:
                        print(
                            json.dumps(
                                {
                                    "event": "delivery_outage_wait",
                                    "run_id": run_id,
                                    "index": index,
                                    "waited_seconds": outage["waited_seconds"],
                                    "healthy_after_wait": outage["healthy_after_wait"],
                                    "seconds_to_deadline": int(
                                        max(0, deadline - time.monotonic())
                                    ),
                                },
                                sort_keys=True,
                            ),
                            flush=True,
                        )
                time.sleep(retry_backoff_seconds)
                retry_timeout = min(
                    per_prompt_timeout, max(1, math.ceil(deadline - time.monotonic()))
                )
                retry_result = send_prompt_through_flutter(
                    hwnd,
                    prompt_to_send,
                    retry_timeout,
                    index,
                    run_id,
                    metadata=turn_metadata,
                )
                if _is_delivery_failure(retry_result) or _is_style_gate_exhaust(retry_result):
                    result["delivery_retry_attempted"] = True
                    result["delivery_retry_recovered"] = False
                else:
                    retry_result["delivery_retry_attempted"] = True
                    retry_result["delivery_retry_recovered"] = True
                    result = retry_result
                print(
                    json.dumps(
                        {
                            "event": "delivery_failure_retry_result",
                            "run_id": run_id,
                            "index": index,
                            "reason": retry_reason,
                            "recovered": bool(result.get("delivery_retry_recovered")),
                            "status": result.get("status"),
                            "seconds_to_deadline": int(max(0, deadline - time.monotonic())),
                        },
                        sort_keys=True,
                    ),
                    flush=True,
                )
        result.update(
            {
                # base_prompt is the UNWRAPPED ask and the only prompt text a training pack
                # may train on; delivered_prompt is the level-wrapped text actually sent and
                # is audit-only. Both were previously known to the run and thrown away when
                # the turn finished, which is why packs could not be reconstructed later.
                "base_prompt": schedule_entry["base_prompt"],
                "delivered_prompt": prompt_to_send,
                "scheduled_hours": scheduled_hours,
                "scheduled_hour": schedule_entry["scheduled_hour"],
                "template_cycle": schedule_entry["template_cycle"],
                "source_prompt_index": schedule_entry["source_prompt_index"],
                "material_topic": schedule_entry["material_topic"],
                "training_level": training_level,
                "training_level_profile": level_profile["profile_id"],
                "training_level_guidance": level_profile["guidance"],
                "trainings_per_hour": trainings_per_hour,
                "cadence_seconds": interval,
                "mode": mode,
                "prompt_use_reservation": prompt_use_reservation,
                "aec_expected_documents": list(
                    schedule_entry.get("aec_expected_documents") or []
                ),
                "aec_evidence_bundle_sha256": str(
                    schedule_entry.get("aec_evidence_bundle_sha256") or ""
                ),
                "aec_evidence_records": list(
                    schedule_entry.get("aec_evidence_records") or []
                ),
            }
        )
        _apply_discipline_eligibility(result, schedule_entry.get("discipline", run_discipline))
        _record_governor_decision(result, schedule_entry.get("discipline", run_discipline))
        results.append(result)
        # AEC used to add a per-turn run blocker on every non-DONE prompt, which made
        # the aggregate majority/empty-capture rules dead: five quality-blocked forms
        # failed a 7-hour Construction run at 0/70. Non-DONE turns stay in
        # prompt_results with discipline_eligibility_reason.
        print(
            json.dumps(
                {
                    "event": "flutter_prompt_complete",
                    "run_id": run_id,
                    "mode": mode,
                    "index": index,
                    "position": offset + 1,
                    "start_index": start_index,
                    "plan_prompts": len(all_entries),
                    "requested": requested,
                    "scheduled_hours": scheduled_hours,
                    "scheduled_hour": schedule_entry["scheduled_hour"],
                    "template_cycle": schedule_entry["template_cycle"],
                    "source_prompt_index": schedule_entry["source_prompt_index"],
                    "training_level": training_level,
                    "training_level_profile": level_profile["profile_id"],
                    "training_level_guidance": level_profile["guidance"],
                    "trainings_per_hour": trainings_per_hour,
                    "cadence_seconds": interval,
                    "status": result.get("status"),
                    "order_id": result.get("order_id"),
                    "wrapper_receipt": result.get("wrapper_receipt_path"),
                    "seconds_to_deadline": int(max(0, deadline - time.monotonic())),
                },
                sort_keys=True,
            ),
            flush=True,
        )
        # Paced early-stop, delivery-failure-aware (2026-07-31 / 2026-09-13). A
        # delivered-then-refused turn (quality/content block) must NOT abort the rest of
        # the schedule -- it is a normal, expected outcome and the other prompts should
        # still run. Construction 7h 2026-09-13 died because consecutive_nondone counted
        # quality-blocks. Only stop early on a genuinely broken pipeline: N consecutive
        # delivery/transport failures, or a longer run of turns that never reached chat.
        if _is_delivery_failure(result):
            consecutive_delivery_failures += 1
        else:
            consecutive_delivery_failures = 0
        if result.get("status") != "DONE" and not _is_style_gate_exhaust(result):
            consecutive_nondone += 1
        else:
            consecutive_nondone = 0
        if paced_mode and consecutive_delivery_failures >= _MAX_CONSECUTIVE_DELIVERY_FAILURES:
            blockers.append(
                f"stopped after {consecutive_delivery_failures} consecutive delivery failures "
                "(chat pipeline not completing)"
            )
            break
        if paced_mode and consecutive_nondone >= _MAX_CONSECUTIVE_NONDONE:
            blockers.append(
                f"stopped after {consecutive_nondone} consecutive turns produced no accepted "
                "result (systemic quality/content failure)"
            )
            break
        if paced_mode:
            scheduled_next = started_mono + interval * (offset + 1)
            last_wait_report = 0.0
            while time.monotonic() < scheduled_next and time.monotonic() < deadline:
                remaining = min(scheduled_next, deadline) - time.monotonic()
                now = time.monotonic()
                if remaining > 20 and (
                    mode != "four-hour" or now - last_wait_report >= 300
                ):
                    print(
                        json.dumps(
                            {
                                "event": "flutter_paced_wait",
                                "run_id": run_id,
                                "mode": mode,
                                "scheduled_hours": scheduled_hours,
                                "training_level": training_level,
                                "training_level_profile": level_profile["profile_id"],
                                "training_level_guidance": level_profile["guidance"],
                                "trainings_per_hour": trainings_per_hour,
                                "cadence_seconds": interval,
                                "completed_prompts": offset + 1,
                                "seconds_to_next_prompt": int(remaining),
                                "seconds_to_deadline": int(max(0, deadline - time.monotonic())),
                            },
                            sort_keys=True,
                        ),
                        flush=True,
                    )
                    last_wait_report = now
                time.sleep(min(30.0 if mode == "four-hour" else 10.0, max(0.5, remaining)))
    if paced_mode and final_wait and (not blockers or mode == "four-hour"):
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            print(
                json.dumps(
                    {
                        "event": "flutter_final_wait",
                        "run_id": run_id,
                        "mode": mode,
                        "scheduled_hours": scheduled_hours,
                        "training_level": training_level,
                        "training_level_profile": level_profile["profile_id"],
                        "training_level_guidance": level_profile["guidance"],
                        "trainings_per_hour": trainings_per_hour,
                        "cadence_seconds": interval,
                        "completed_prompts": len(results),
                        "seconds_to_deadline": int(remaining),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
            time.sleep(min(30.0, max(0.5, remaining)))
    after_shot = REPORT_DIR / f"ENGEL_FLUTTER_UI_PROMPT_TRAINING_{run_id}_after.png"
    capture_window(hwnd, after_shot)
    order_ids = [str(item.get("order_id") or "") for item in results if item.get("order_id")]
    selection = build_device_selection(run_id, order_ids)
    proposals = build_agent_proposals(selection)
    output_files = [
        str(before_shot),
        str(after_shot),
        str(ROOT / "reports" / "codex_bridge" / "ENGEL_UI_PROMPT_TRAINING_PLAN.md"),
        str(ROOT / "memory" / "training" / "ENGEL_UI_PROMPT_TRAINING_SESSION.json"),
        str(ROOT / "memory" / "training" / "ENGEL_AGENT_MEETING_ROOM_DEVICE_SELECTION.json"),
        str(ROOT / "memory" / "training" / "ENGEL_AGENT_MEETING_ROOM_AGENT_PROPOSALS.json"),
    ]
    served_results = [item for item in results if item.get("status") == "DONE"]
    creation_prompt_count = sum(1 for item in results if item.get("creation_job") is True)
    meeting_room_required_order_count = sum(
        1
        for item in results
        if (item.get("wrapper_receipt") or {}).get("phone_work_requested") is True
        or (item.get("wrapper_receipt") or {}).get("sub_engel_work_requested") is True
    )
    chat_prompt_count = len(results) - creation_prompt_count
    summary = {
        "scheduled_hours": scheduled_hours,
        "requested_minutes": minutes,
        "training_level": training_level,
        "training_targets": training_targets,
        "training_level_profile": level_profile["profile_id"],
        "training_level_guidance": level_profile["guidance"],
        "trainings_per_hour": trainings_per_hour,
        "cadence_seconds": interval,
        "hourly_cycle_count": len(training_schedule["hourly_cycles"]),
        "hourly_cycles": training_schedule["hourly_cycles"],
        "prompts_requested": requested,
        "prompts_completed": sum(1 for item in results if item.get("status") == "DONE"),
        "chat_prompt_count": chat_prompt_count,
        "creation_prompt_count": creation_prompt_count,
        "chat_only_count": sum(1 for item in results if item.get("chat_only_no_android_or_sub_engel") is True),
        "meeting_room_order_count": len(order_ids),
        "meeting_room_required_order_count": meeting_room_required_order_count,
        "meeting_room_used_count": sum(1 for item in results if item.get("agent_meeting_room_used") is True),
        "build_artifact_verified_count": sum(1 for item in results if item.get("build_artifact_verified") is True),
        "build_full_proof_verified_count": sum(
            1
            for item in results
            if item.get("creation_job") is True
            and (item.get("build_proof") or {}).get("ok") is True
        ),
        "conical_four_worker_verified_count": sum(
            1
            for item in results
            if item.get("creation_job") is True
            and (item.get("conical_proof") or {}).get("ok") is True
        ),
        "provider_free_generation_count": sum(
            1 for item in results if item.get("provider_free_generation") is True
        ),
        "local_build_model_used_count": sum(
            1 for item in results if (item.get("build_proof") or {}).get("local_model_used") is True
        ),
        "attached_codex_build_used_count": sum(
            1 for item in results if (item.get("build_proof") or {}).get("attached_codex_used") is True
        ),
        "android_worker_claim_count": sum(int((item.get("android_worker_return") or {}).get("claim_count") or 0) for item in results),
        "android_worker_return_count": sum(int((item.get("android_worker_return") or {}).get("return_count") or 0) for item in results),
        "android_worker_required_return_failures": sum(
            1
            for item in results
            if (item.get("android_worker_return") or {}).get("required")
            and (item.get("android_worker_return") or {}).get("status") != "returned"
        ),
        "sub_engel_required_return_failures": sum(
            1
            for item in results
            if (item.get("wrapper_receipt") or {}).get("sub_engel_work_requested") is True
            and (item.get("wrapper_receipt") or {}).get("sub_engel_work_returned") is not True
        ),
        "local_llm_only": all(item.get("local_llm_only") for item in results) if results else False,
        "local_llm_only_count": sum(1 for item in results if item.get("local_llm_only") is True),
        # Served-turn view of the same two facts. The all-turns fields above are kept as they
        # were (receipts and the UI read them), but the local-only VERDICT is taken from these:
        # an unserved turn has no provenance, and judging it as unproven-local reported a
        # provider risk that never existed.
        "served_prompt_count": len(served_results),
        "served_local_llm_only": (
            all(item.get("local_llm_only") for item in served_results) if served_results else False
        ),
        "served_local_only_training_count": sum(
            1 for item in served_results if item.get("local_only_training") is True
        ),
        "local_only_training_count": sum(
            1 for item in results if item.get("local_only_training") is True
        ),
        "training_sample_eligible_count": sum(
            1 for item in results if item.get("training_sample_eligible") is True
        ),
        "provider_fallback_allowed_count": sum(
            1 for item in results if item.get("provider_fallback_allowed") is True
        ),
        "provider_bridge_used_count": sum(
            1 for item in results if item.get("provider_bridge_used") is True
        ),
        "selected_providers": sorted(
            {
                str(item.get("selected_provider") or "").strip()
                for item in results
                if str(item.get("selected_provider") or "").strip()
            }
        ),
        "humanizer_voice_rules_active_count": sum(
            1
            for item in results
            if (item.get("wrapper_receipt") or {}).get("humanizer_voice_rules_active") is True
        ),
        "persistent_chat_memory_appended_count": sum(
            1 for item in results if item.get("persistent_chat_memory_appended") is True
        ),
        "main_server_chat_used_count": sum(
            1 for item in results if (item.get("wrapper_receipt") or {}).get("main_server_chat_used") is True
        ),
        "fast_server_fallback_used_count": sum(
            1 for item in results if (item.get("wrapper_receipt") or {}).get("fast_server_fallback_used") is True
        ),
        "latency_ms_values": [
            int((item.get("wrapper_receipt") or {}).get("latency_ms") or 0)
            for item in results
            if (item.get("wrapper_receipt") or {}).get("latency_ms") is not None
        ],
        "max_latency_ms": max(
            [
                int((item.get("wrapper_receipt") or {}).get("latency_ms") or 0)
                for item in results
                if (item.get("wrapper_receipt") or {}).get("latency_ms") is not None
            ]
            or [0]
        ),
        "repeat_guard_triggered_count": sum(1 for item in results if item.get("repeat_guard_triggered") is True),
        "ui_reply_guard_triggered_count": sum(
            1
            for item in results
            if (item.get("wrapper_receipt") or {}).get("ui_reply_guard_triggered") is True
        ),
        "visible_flutter_worker_result_count": sum(
            1
            for item in results
            if (item.get("flutter_worker_result") or {}).get("ok") is True
        ),
        "no_provider_api": all(
            (item.get("wrapper_receipt") or {}).get("provider_api_enabled") is False
            for item in results
            if item.get("wrapper_receipt")
        ) if results else False,
        "device_count": len(selection.get("devices") or []),
        "no_c_drive_output_paths": not any(Path(path).drive.lower() == "c:" for path in output_files),
        "no_hard_coded_ips": True,
        "hard_coded_ip_hits": [],
        "hidden_persistent_worker_started": False,
        "correct_engel_main_process": process_path,
        "correct_engel_main_pid": pid,
        "training_discipline": run_discipline,
        "discipline_ineligible_count": sum(
            1 for item in results if item.get("discipline_eligibility_ok") is False
        ),
    }
    summary["completed_hourly_cycle_count"] = sum(
        1
        for hourly_cycle in training_schedule["hourly_cycles"]
        if sum(
            1
            for item in results
            if item.get("scheduled_hour") == hourly_cycle["scheduled_hour"]
            and item.get("status") == "DONE"
        )
        == hourly_cycle["selected_prompt_count"]
    )
    if (
        mode == "scheduled"
        and summary["hourly_cycle_count"] != scheduled_hours
    ):
        blockers.append(
            "scheduled run did not plan exactly one distinct prompt cycle per selected hour"
        )
    # Completion rule (2026-09-13). A delivered-then-quality-blocked AEC form is a
    # per-prompt miss, not a whole-run failure. Construction 7h died at 0/70 because
    # scheduled AEC required 100% DONE. Same majority bar as smoke/math/engineering:
    # only a run that mostly failed to complete is a real failure.
    if not results or summary["prompts_completed"] * 2 < len(results):
        blockers.append(
            "most sent prompts did not complete through the correct Flutter Engel Main chat "
            f"({summary['prompts_completed']}/{len(results)})"
        )
    if summary["meeting_room_order_count"] < summary["meeting_room_required_order_count"]:
        blockers.append("one or more creation prompts did not create Meeting Room orders")
    if summary["android_worker_required_return_failures"]:
        blockers.append("one or more Android-routed Meeting Room prompts did not produce phone returned-result evidence")
    if summary["sub_engel_required_return_failures"]:
        blockers.append("one or more Sub-Engel work prompts staged work but did not produce a returned result")
    if summary["build_full_proof_verified_count"] != creation_prompt_count:
        blockers.append(
            "one or more build jobs lacked verified generate/review/package/preview proof or used a provider API"
        )
    if summary["conical_four_worker_verified_count"] != creation_prompt_count:
        blockers.append(
            "one or more build jobs lacked exact fresh Alpha/Beta/Gamma/Sub-Engel 4-of-4 receipts"
        )
    if summary["provider_free_generation_count"] != creation_prompt_count:
        blockers.append("one or more build jobs used or could not disprove an external provider API")
    if local_only:
        # A provider is non-local ONLY when it names an external cloud bridge.
        # The old prefix allowlist ("local"/"ct_local"/...) kept mislabelling
        # every NEW local CT lane as non-local — ct_sparse_moe_specialist (local
        # Qwen3-30B), ct_deep_local_specialist (local 14B), the math lanes — so a
        # clean local-only run failed. Deny-list the cloud markers (same set the
        # chat service uses) and treat everything else as the local lane it is.
        _EXTERNAL_PROVIDER_MARKERS = (
            "claude", "anthropic", "grok", "xai", "chatgpt", "openai",
            "gemini", "codex", "runpod",
        )
        non_local_providers = [
            provider
            for provider in summary["selected_providers"]
            if any(marker in provider.casefold() for marker in _EXTERNAL_PROVIDER_MARKERS)
        ]
        # (2026-08-01) The two "was this turn local" invariants are judged over SERVED turns.
        # A turn that never completed has an empty selected_provider and no reply -- there is
        # no provenance to verify, so counting it as "not verified local" reported a provider
        # risk that did not exist: the 20260801 communication run captured 14 good samples and
        # was still stamped FAIL by two turns that produced nothing at all. That verdict is not
        # cosmetic; it is what the Training panel shows and what decides whether a session's
        # material is trusted. The deny-list checks below stay over ALL turns, so a real escape
        # (a provider marker, a bridge, an allowed fallback) is still caught with or without
        # a completed reply.
        unserved_count = len(results) - len(served_results)
        if served_results and summary["served_local_llm_only"] is not True:
            blockers.append("strict local-only run contains a served turn not verified as local LLM only")
        if summary["no_provider_api"] is not True:
            blockers.append("strict local-only run contains a provider API enabled turn")
        if non_local_providers:
            blockers.append(
                "strict local-only run selected non-local providers: "
                + ", ".join(non_local_providers)
            )
        if summary["provider_fallback_allowed_count"]:
            blockers.append("strict local-only run allowed provider fallback on one or more turns")
        if summary["provider_bridge_used_count"]:
            blockers.append("strict local-only run used or attempted a provider bridge")
        if summary["served_local_only_training_count"] != len(served_results):
            blockers.append(
                "CT246 did not stamp every served turn as local-only training "
                f"({summary['served_local_only_training_count']}/{len(served_results)} served"
                + (f", {unserved_count} turn(s) never completed)" if unserved_count else ")")
            )
        # Eligibility rule (2026-09-13): AEC stays citation-graded per turn, but a
        # scheduled Construction hour must not FAIL unless capture is empty. Partial
        # capture is the same healthy outcome as math/engineering. Ineligible turns
        # stay in prompt_results with discipline_eligibility_reason.
        if summary["training_sample_eligible_count"] == 0:
            blockers.append(
                f"no local turns produced a domain-eligible training sample ({run_discipline} discipline)"
            )
    receipt = {
        "schema": "engel_ui_prompt_training_session_v1",
        "run_id": run_id,
        "prompt_run_claim": prompt_run_claim.owner_record,
        "mode": mode,
        "scheduled_hours": scheduled_hours,
        "training_level": training_level,
        "training_targets": training_targets,
        "training_level_profile": level_profile["profile_id"],
        "training_level_guidance": level_profile["guidance"],
        "trainings_per_hour": trainings_per_hour,
        "cadence_seconds": interval,
        "hourly_cycles": training_schedule["hourly_cycles"],
        "template_path": template_path or "",
        "curriculum_binding": dict(session_preflight.get("curriculum_binding") or {}),
        "template_cycle": template_cycle,
        "exact_template_cycle": bool(exact_template_cycle),
        "template_cycle_contract": (
            "EXACT" if exact_template_cycle else "AUTO_ADVANCE_ALLOWED"
        ),
        "start_index": start_index,
        "fresh_chat_requested": fresh_chat,
        "local_only_required": local_only,
        "session_preflight": _receipt_session_preflight(session_preflight),
        "local_only_guard": local_only_guard,
        "gpu_server_freshness": gpu_server_freshness or {
            "requested": False,
            "mutated": False,
        },
        "status": "PASS" if not blockers else "FAIL",
        "started_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started_epoch)),
        "finished_at_utc": iso_now(),
        "requested_minutes": minutes,
        "actual_duration_seconds": round(time.monotonic() - started_mono, 3),
        "ui_path_used": "correct visible Flutter Engel AI Main window; mouse click into Engel Main Chat input and Send button",
        "local_llm_runner": str(ROOT / "tools" / "run_engel_ui_chat_meeting_room_llm.py"),
        "routing_policy": (
            "strict ROG UI to CT246 local GGUF only; provider fallback disabled per turn"
            if local_only
            else "normal chat and executable builds use CT246; explicit phone/Sub collaboration uses the Agent Meeting Room and device dispatcher"
        ),
        "meeting_room_route": "Flutter chat -> long-lived worker -> explicit device dispatcher -> Agent Meeting Room; CT246 build lane separately owns executable workspace and run receipts",
        "correct_engel_main_process": process_path,
        "correct_engel_main_pid": pid,
        "device_selection": selection,
        "agent_proposals": proposals,
        "prompt_results": results,
        "summary": summary,
        "blockers": blockers,
        "output_files": output_files,
    }
    # Emit the immutable session -> pack -> stamped-receipt chain BEFORE the mutable
    # human-facing session alias. The alias can then carry true counters and exact proof
    # paths without becoming an authority for the downstream model hand-off.
    try:
        pack = write_training_pack(receipt)
        summary["training_pack_rows"] = int(pack.get("rows") or 0)
        summary["training_pack_admitted"] = int(pack.get("admitted") or 0)
        summary["training_pack_path"] = str(pack.get("pack_path") or "")
        summary["training_pack_receipt_path"] = str(
            pack.get("stamped_pack_receipt") or ""
        )
        summary["training_pack_receipt_sha256"] = str(
            pack.get("stamped_pack_receipt_sha256") or ""
        )
        summary["training_session_evidence_path"] = str(
            pack.get("session_receipt") or ""
        )
        summary["training_session_evidence_sha256"] = str(
            pack.get("session_receipt_sha256") or ""
        )
        receipt["training_pack_evidence"] = {
            "pack_path": summary["training_pack_path"],
            "pack_sha256": str(pack.get("pack_sha256") or ""),
            "pack_bytes": int(pack.get("pack_bytes") or 0),
            "stamped_receipt_path": summary["training_pack_receipt_path"],
            "stamped_receipt_sha256": summary[
                "training_pack_receipt_sha256"
            ],
            "session_evidence_path": summary[
                "training_session_evidence_path"
            ],
            "session_evidence_sha256": summary[
                "training_session_evidence_sha256"
            ],
            "writer": dict(pack.get("writer") or {}),
        }
        output_files.extend(
            [
                str(pack.get("pack_path") or ""),
                str(pack.get("stamped_pack_receipt") or ""),
                str(pack.get("session_receipt") or ""),
                str(pack.get("latest_receipt_path") or ""),
            ]
        )
        summary["no_c_drive_output_paths"] = not any(
            Path(path).drive.lower() == "c:" for path in output_files if path
        )
    except Exception as exc:  # noqa: BLE001 -- preserve the completed prompt evidence
        # The replies remain valuable evidence, but an unbound/missing pack means the
        # advertised training hand-off did not happen. Keep the session, fail it loudly,
        # and let the immutable prompt-use reservations prevent accidental replay.
        summary["training_pack_rows"] = 0
        summary["training_pack_admitted"] = 0
        summary["training_pack_path"] = None
        summary["training_pack_error"] = f"{type(exc).__name__}: {exc}"
        blockers.append(
            "training pack publication failed; completed prompts are preserved but "
            "cannot enter model training"
        )
        receipt["status"] = "FAIL"
        print(
            json.dumps(
                {
                    "event": "flutter_training_pack_failed",
                    "run_id": run_id,
                    "mode": mode,
                    "error": f"{type(exc).__name__}: {exc}",
                },
                sort_keys=True,
            ),
            flush=True,
        )
    summary["prompts_not_completed"] = max(
        0, summary["prompts_requested"] - summary["prompts_completed"]
    )
    summary["training_pack_rejected"] = max(
        0,
        int(summary.get("training_pack_rows") or 0)
        - int(summary.get("training_pack_admitted") or 0),
    )
    if receipt["status"] != "PASS":
        summary["completion_quality"] = "FAILED"
    elif summary.get("training_pack_error"):
        summary["completion_quality"] = "HANDOFF_FAILED"
    elif summary["prompts_not_completed"]:
        summary["completion_quality"] = "PARTIAL_CAPTURE"
    elif summary["training_pack_rejected"]:
        summary["completion_quality"] = "PASS_WITH_EXCLUSIONS"
    else:
        summary["completion_quality"] = "COMPLETE"
    paths = write_reports(receipt)
    if local_only and local_only_guard.get("owned") is True:
        _finish_local_only_guard(
            run_id,
            "COMPLETED" if receipt["status"] == "PASS" else "FAILED",
            prompt_run_claim=prompt_run_claim,
        )
    print(
        json.dumps(
            {
                "event": "flutter_training_complete",
                "run_id": run_id,
                "mode": mode,
                "scheduled_hours": scheduled_hours,
                "training_level": training_level,
                "training_targets": training_targets,
                "training_level_profile": level_profile["profile_id"],
                "training_level_guidance": level_profile["guidance"],
                "trainings_per_hour": trainings_per_hour,
                "cadence_seconds": interval,
                "status": receipt["status"],
                "report": paths.get("report"),
                "summary": summary,
            },
            indent=2,
        ),
        flush=True,
    )
    print(json.dumps(redact(receipt), indent=2), flush=True)
    return receipt


def _new_prompt_training_run_id(mode: str) -> str:
    return f"engel_flutter_ui_prompt_training_{mode}_{stamp()}_{os.getpid()}"


def _scheduled_plan_timing(
    scheduled_hours: int,
    trainings_per_hour: int,
    start_index: int,
) -> dict[str, Any]:
    """Return full-plan identity and the remaining wall budget for a resume.

    ``scheduled_hours`` always identifies the original plan. A recovery launch keeps
    that identity and starts later inside it, so its wall budget covers only the prompts
    from ``start_index`` through the end at the original hourly cadence. Treating the
    remaining budget as though it still had to equal ``hours * 60`` made every real
    resume fail argument validation before the novelty preflight could run.
    """

    hours = validate_training_hours(scheduled_hours)
    hourly_count = validate_trainings_per_hour(trainings_per_hour)
    start = int(start_index)
    plan_prompts = hours * hourly_count
    if start < 1 or start > plan_prompts:
        raise ValueError(
            f"start index {start} is outside the {plan_prompts}-prompt scheduled plan"
        )
    requested_prompts = plan_prompts - start + 1
    cadence_seconds = 3600.0 / hourly_count
    return {
        "scheduled_hours": hours,
        "plan_prompts": plan_prompts,
        "start_index": start,
        "requested_prompts": requested_prompts,
        "cadence_seconds": cadence_seconds,
        "remaining_minutes": requested_prompts * cadence_seconds / 60.0,
    }


def _execute_claimed_training(
    prompt_run_claim: PromptRunClaim,
    run_id: str,
    **training_arguments: Any,
) -> dict[str, Any]:
    """Run the core while preserving exact claim/guard ownership on failures."""

    prompt_run_claim.require_owner(run_id)
    try:
        return _run_training_claimed(
            prompt_run_claim,
            run_id,
            **training_arguments,
        )
    except BaseException:
        if training_arguments.get("local_only") is True:
            try:
                _finish_local_only_guard(
                    run_id,
                    "FAILED",
                    prompt_run_claim=prompt_run_claim,
                )
            except RuntimeError as guard_exc:
                # The failure may have happened before guard publication.  Never mutate
                # another run's sentinel merely to hide that fact; retain the primary
                # exception and make cleanup refusal visible in the local log.
                print(
                    json.dumps(
                        {
                            "event": "local_only_guard_cleanup_refused",
                            "run_id": run_id,
                            "detail": str(guard_exc),
                        },
                        sort_keys=True,
                    ),
                    flush=True,
                )
        raise


def run_training(
    mode: str,
    minutes: float,
    per_prompt_timeout: int,
    final_wait: bool,
    template_path: str | None = None,
    template_cycle: int = 1,
    exact_template_cycle: bool = False,
    fresh_chat: bool = False,
    start_index: int = 1,
    local_only: bool = False,
    scheduled_hours: int = 1,
    training_level: str = "medium",
    training_targets: str = "slm,llm",
    trainings_per_hour: int = DEFAULT_TRAININGS_PER_HOUR,
    back_to_back: bool = False,
    gpu_server_freshness: dict[str, Any] | None = None,
    prepared_session_preflight: dict[str, Any] | None = None,
    wrapper_pid: int = 0,
    launcher_log: str = "",
    lifecycle_receipt: str = "",
) -> dict[str, Any]:
    """Direct-call entrypoint with the same whole-run concurrency contract as CLI."""

    run_id = _new_prompt_training_run_id(mode)
    with acquire_prompt_run_claim(DEFAULT_PROMPT_RUN_CLAIM, run_id) as claim:
        return _execute_claimed_training(
            claim,
            run_id,
            mode=mode,
            minutes=minutes,
            per_prompt_timeout=per_prompt_timeout,
            final_wait=final_wait,
            template_path=template_path,
            template_cycle=template_cycle,
            exact_template_cycle=exact_template_cycle,
            fresh_chat=fresh_chat,
            start_index=start_index,
            local_only=local_only,
            scheduled_hours=scheduled_hours,
            training_level=training_level,
            training_targets=training_targets,
            trainings_per_hour=trainings_per_hour,
            back_to_back=back_to_back,
            gpu_server_freshness=gpu_server_freshness,
            prepared_session_preflight=prepared_session_preflight,
            wrapper_pid=wrapper_pid,
            launcher_log=launcher_log,
            lifecycle_receipt=lifecycle_receipt,
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=[
            "smoke",
            "completion",
            "scheduled",
            "one-hour",
            "two-hour",
            "four-hour",
        ],
        required=True,
    )
    parser.add_argument("--minutes", type=float, default=None)
    parser.add_argument(
        "--hours",
        type=validate_training_hours,
        default=1,
        help="scheduled duration as a whole number from 1 through 8",
    )
    parser.add_argument(
        # (2026-08-08) Ladder raised: expert is the new floor; principal/distinguished/
        # fellow sit above. Legacy names stay accepted and clamp up to expert.
        "--training-level",
        type=validate_training_level,
        choices=["low", "medium", "high", "expert", "principal", "distinguished", "fellow"],
        default="medium",
        help="independent prompt depth and guidance applied to every training",
    )
    parser.add_argument(
        "--trainings-per-hour",
        type=validate_trainings_per_hour,
        default=DEFAULT_TRAININGS_PER_HOUR,
        help="independent hourly training count from 1 through 10 (default: 6)",
    )
    parser.add_argument(
        "--training-targets",
        type=validate_training_targets,
        default="slm,llm",
        help="trainable model families that should consume this pack: slm, llm, or both",
    )
    parser.add_argument("--per-prompt-timeout", type=int, default=760)
    parser.add_argument("--skip-final-wait", action="store_true")
    parser.add_argument(
        "--back-to-back",
        action="store_true",
        default=str(os.environ.get("ENGEL_TRAINING_BACK_TO_BACK", "")).strip().casefold()
        in {"1", "true", "yes", "on"},
        help="run the prompt set consecutively with no idle gap (keeps the GPU busy "
        "instead of idling ~96%% of a paced hour); also skips the final wait",
    )
    parser.add_argument("--template", default="", help="optional saved prompt-training template JSON")
    parser.add_argument(
        "--template-cycle",
        type=validate_template_cycle,
        default=1,
        help="1-based template cycle prompt set",
    )
    parser.add_argument(
        "--exact-template-cycle",
        action="store_true",
        help="use the displayed template cycle exactly; refuse instead of auto-advancing",
    )
    parser.add_argument("--start-index", type=int, default=1, help="1-based prompt index to resume from")
    parser.add_argument("--fresh-chat", action="store_true", help="click Engel Main New Chat before prompt 1")
    parser.add_argument(
        "--local-only",
        action="store_true",
        help="require CT246 local LLM-only receipts and reject any provider bridge use",
    )
    parser.add_argument(
        "--freshen-gpu-server",
        action="store_true",
        help=(
            "explicitly authorize restarting the scheduled Engel GPU task when stale; "
            "without this flag prompt training never mutates a running service"
        ),
    )
    parser.add_argument(
        "--launcher-pid",
        type=int,
        default=0,
        help="diagnostic PID of the PowerShell process owned by the Training UI",
    )
    parser.add_argument(
        "--launcher-log",
        default="",
        help="diagnostic lifecycle log path shown by the Training UI",
    )
    parser.add_argument(
        "--lifecycle-receipt",
        default="",
        help="diagnostic PowerShell lifecycle receipt path",
    )
    return parser


GPU_SERVER_TASK = "EngelRogGpuModelServer"
GPU_SERVER_PORT = 8899


def _freshen_stale_gpu_server(max_age_hours: float | None = None) -> dict[str, Any]:
    """Restart the scheduled :8899 GPU task after explicit CLI authorization.

    (2026-08-09) The second 8h construction run served against a server six days up:
    25% of turns came back truncated-incomplete ("complete_ending: false" gate blocks)
    and whole cycles collapsed to one 0.99-similar answer. A/B after a clean restart on
    the same prompts: 0 blocked, similarity back to the 0.55-0.69 contract-scaffold
    baseline. Age, not load, was the variable — a run about to spend 8 hours against
    this server starts it fresh. The task boundary owns the mutation: this helper never
    force-kills an arbitrary process merely because it owns the expected port, and an
    unsuccessful explicit preflight prevents training from starting."""
    limit = float(os.environ.get("ENGEL_GPU_SERVER_MAX_AGE_HOURS", "24")
                  if max_age_hours is None else max_age_hours)
    result: dict[str, Any] = {
        "requested": True,
        "checked": True,
        "restarted": False,
        "mutated": False,
        "ready": False,
        "age_hours": None,
        "max_age_hours": limit,
        "task": GPU_SERVER_TASK,
    }
    def _ps(script: str) -> str:
        cp = subprocess.run(["powershell", "-NoProfile", "-Command", script],
                            capture_output=True, text=True, timeout=60,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return (cp.stdout or "").strip()
    try:
        owner = _ps(f"(Get-NetTCPConnection -LocalPort {GPU_SERVER_PORT} -State Listen "
                    "-ErrorAction SilentlyContinue | Select-Object -First 1).OwningProcess")
        if not owner.isdigit():
            result["detail"] = "no listener on the GPU port; leaving startup to the stack lifecycle"
            return result
        age = _ps(f"[int]((Get-Date) - (Get-CimInstance Win32_Process -Filter \"ProcessId={owner}\").CreationDate).TotalHours")
        result["age_hours"] = float(age) if age.lstrip("-").isdigit() else None
        if result["age_hours"] is None:
            result["detail"] = "listener age could not be verified; restart authorization not exercised"
            return result
        if result["age_hours"] < limit:
            result["ready"] = True
            result["detail"] = "server is fresh enough"
            return result
        ended = subprocess.run(["schtasks", "/End", "/TN", GPU_SERVER_TASK],
                               capture_output=True, text=True, timeout=30)
        if ended.returncode != 0:
            result["detail"] = f"scheduled task stop failed: {(ended.stderr or ended.stdout).strip()}"
            return result
        result["mutated"] = True
        release_deadline = time.time() + 30
        while time.time() < release_deadline:
            current = _ps(f"(Get-NetTCPConnection -LocalPort {GPU_SERVER_PORT} -State Listen "
                          "-ErrorAction SilentlyContinue | Select-Object -First 1).OwningProcess")
            if not current.isdigit() or current != owner:
                break
            time.sleep(2)
        else:
            result["detail"] = "scheduled task ended but its original listener remained; restart refused"
            return result
        started = subprocess.run(["schtasks", "/Run", "/TN", GPU_SERVER_TASK],
                                 capture_output=True, text=True, timeout=30)
        if started.returncode != 0:
            result["detail"] = f"scheduled task start failed: {(started.stderr or started.stdout).strip()}"
            return result
        deadline = time.time() + 120
        while time.time() < deadline:
            if _ps(f"(Get-NetTCPConnection -LocalPort {GPU_SERVER_PORT} -State Listen "
                   "-ErrorAction SilentlyContinue | Select-Object -First 1).OwningProcess").isdigit():
                result["restarted"] = True
                result["ready"] = True
                result["detail"] = f"stale server ({result['age_hours']:.0f}h) bounced via {GPU_SERVER_TASK}"
                return result
            time.sleep(5)
        result["detail"] = "restart issued but the port did not come back within 120s"
    except Exception as exc:  # noqa: BLE001 — freshness is best-effort, never blocks a run
        result["detail"] = f"freshness check failed: {type(exc).__name__}: {exc}"
    return result


def _run_cli_with_claim(
    *,
    args: argparse.Namespace,
    minutes: float,
    scheduled_hours: int,
    run_id: str,
    prompt_run_claim: PromptRunClaim,
    unclaimed_preflight: dict[str, Any],
) -> int:
    """Recheck the history under the claim, then keep it through publication."""

    prompt_run_claim.require_owner(run_id)
    claimed_preflight = _prepare_session_preflight(
        mode=args.mode,
        template_path=args.template.strip() or None,
        template_cycle=args.template_cycle,
        scheduled_hours=scheduled_hours,
        training_level=args.training_level,
        trainings_per_hour=args.trainings_per_hour,
        start_index=max(1, args.start_index),
        exact_template_cycle=args.exact_template_cycle,
    )
    # This is the serialization point: every scheduled process re-reads immutable packs
    # only after it has exclusive ownership.  The claim remains held until this run's pack
    # and session receipt have been published (or the process exits).
    _require_session_preflight(claimed_preflight)
    first_novelty = unclaimed_preflight.get("prompt_novelty") or {}
    claimed_novelty = claimed_preflight.get("prompt_novelty") or {}
    claimed_preflight["prompt_run_claim"] = prompt_run_claim.owner_record
    claimed_preflight["unclaimed_preflight"] = {
        "decision": first_novelty.get("decision"),
        "planned_prompt_set_sha256": first_novelty.get(
            "planned_prompt_set_sha256"
        ),
        "history_pack_snapshot_sha256": first_novelty.get(
            "history_pack_snapshot_sha256"
        ),
        "history_snapshot_sha256": first_novelty.get(
            "history_snapshot_sha256"
        ),
        "history_snapshot_changed_before_claim": first_novelty.get(
            "history_snapshot_sha256"
        )
        != claimed_novelty.get("history_snapshot_sha256"),
    }
    print(
        "prompt_novelty_preflight: "
        + json.dumps(
            {
                "decision": claimed_novelty.get("decision"),
                "planned_prompt_count": claimed_novelty.get(
                    "planned_prompt_count"
                ),
                "novel_prompt_count": claimed_novelty.get("novel_prompt_count"),
                "replayed_prompt_count": claimed_novelty.get(
                    "replayed_prompt_count"
                ),
                "history_pack_count": claimed_novelty.get("history_pack_count"),
                "history_unique_prompt_count": claimed_novelty.get(
                    "history_unique_prompt_count"
                ),
                "planned_prompt_set_sha256": claimed_novelty.get(
                    "planned_prompt_set_sha256"
                ),
                "history_prompt_set_sha256": claimed_novelty.get(
                    "history_prompt_set_sha256"
                ),
                "history_pack_snapshot_sha256": claimed_novelty.get(
                    "history_pack_snapshot_sha256"
                ),
                "history_reservation_snapshot_sha256": claimed_novelty.get(
                    "history_reservation_snapshot_sha256"
                ),
                "history_snapshot_sha256": claimed_novelty.get(
                    "history_snapshot_sha256"
                ),
                "history_valid_reservation_count": claimed_novelty.get(
                    "history_valid_reservation_count"
                ),
                "prompt_run_claim": prompt_run_claim.owner_record,
            },
            default=str,
            sort_keys=True,
        ),
        flush=True,
    )
    freshness = (
        _freshen_stale_gpu_server()
        if args.freshen_gpu_server
        else {
            "requested": False,
            "checked": False,
            "mutated": False,
            "ready": None,
            "detail": (
                "service mutation not authorized; existing lifecycle left unchanged"
            ),
        }
    )
    print(f"gpu_server_freshness: {json.dumps(freshness, default=str)}", flush=True)
    if args.freshen_gpu_server and freshness.get("ready") is not True:
        raise RuntimeError(
            "explicit GPU-server freshness preflight failed; training was not started: "
            + str(freshness.get("detail") or "unknown failure")
        )
    receipt = _execute_claimed_training(
        prompt_run_claim,
        run_id,
        mode=args.mode,
        minutes=minutes,
        per_prompt_timeout=max(60, args.per_prompt_timeout),
        final_wait=args.mode
        in {"scheduled", "one-hour", "two-hour", "four-hour"}
        and not args.skip_final_wait
        and not args.back_to_back,
        back_to_back=args.back_to_back,
        template_path=args.template.strip() or None,
        template_cycle=args.template_cycle,
        exact_template_cycle=args.exact_template_cycle,
        fresh_chat=args.fresh_chat,
        start_index=max(1, args.start_index),
        local_only=args.local_only,
        scheduled_hours=scheduled_hours,
        training_level=args.training_level,
        training_targets=args.training_targets,
        trainings_per_hour=args.trainings_per_hour,
        gpu_server_freshness=freshness,
        prepared_session_preflight=claimed_preflight,
        wrapper_pid=max(0, int(args.launcher_pid)),
        launcher_log=str(args.launcher_log or ""),
        lifecycle_receipt=str(args.lifecycle_receipt or ""),
    )
    return 0 if receipt.get("status") == "PASS" else 1


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    minutes = args.minutes
    if args.mode == "scheduled":
        scheduled_hours = validate_training_hours(args.hours)
        try:
            plan_timing = _scheduled_plan_timing(
                scheduled_hours,
                args.trainings_per_hour,
                args.start_index,
            )
        except (TypeError, ValueError) as exc:
            parser.error(str(exc))
        derived_minutes = float(plan_timing["remaining_minutes"])
        if minutes is not None and abs(minutes - derived_minutes) > 0.001:
            parser.error(
                "--minutes must equal the remaining scheduled-plan budget "
                f"(expected {derived_minutes:g} for prompt "
                f"{plan_timing['start_index']} of {plan_timing['plan_prompts']})"
            )
        minutes = derived_minutes
    else:
        scheduled_hours = {
            "one-hour": 1,
            "two-hour": 2,
            "four-hour": 4,
        }.get(args.mode, 1)
    if minutes is None:
        minutes = (
            240.0
            if args.mode == "four-hour"
            else 120.0
            if args.mode == "two-hour"
            else 60.0
            if args.mode == "one-hour"
            else 10.0
        )
    prepared_session_preflight = _prepare_session_preflight(
        mode=args.mode,
        template_path=args.template.strip() or None,
        template_cycle=args.template_cycle,
        scheduled_hours=scheduled_hours,
        training_level=args.training_level,
        trainings_per_hour=args.trainings_per_hour,
        start_index=max(1, args.start_index),
        exact_template_cycle=args.exact_template_cycle,
    )
    # Refuse replay before --freshen-gpu-server can restart anything.  run_training also
    # enforces this boundary for direct Python callers that do not enter through main().
    _require_session_preflight(prepared_session_preflight)
    run_id = _new_prompt_training_run_id(args.mode)
    try:
        with acquire_prompt_run_claim(DEFAULT_PROMPT_RUN_CLAIM, run_id) as claim:
            return _run_cli_with_claim(
                args=args,
                minutes=minutes,
                scheduled_hours=scheduled_hours,
                run_id=run_id,
                prompt_run_claim=claim,
                unclaimed_preflight=prepared_session_preflight,
            )
    except PromptRunClaimBlocked as exc:
        parser.exit(2, f"prompt training already active; run refused: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
