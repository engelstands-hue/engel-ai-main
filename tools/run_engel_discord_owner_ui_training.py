#!/usr/bin/env python3
"""Run bounded owner chat training through the real Discord desktop UI.

The script uses the logged-in Engelz desktop client to submit ordinary messages,
then verifies each turn in CT246's Discord training log. It never uses the bot
token or a Discord user token to impersonate the owner.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import time
from typing import Any

from engel_local_first_receipt_proof import evaluate_local_first_evidence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE = ROOT / "memory" / "training" / "ENGEL_DISCORD_OWNER_COMMUNICATION_ONE_HOUR_20260716.json"
REPORT_DIR = ROOT / "reports" / "codex_bridge"
GUILD_ID = "1148755185703850014"
CHANNEL_ID = "1148755186752430163"
OWNER_ID = "DISCORD_OWNER_USER_ID"
CT_HOST = os.environ.get("ENGEL_MAIN_SERVER_HOST", "192.0.2.50")
CT_PORT = os.environ.get("ENGEL_MAIN_SERVER_SSH_PORT", "24622")
CT_USER = os.environ.get("ENGEL_MAIN_SERVER_SSH_USER", "root")
CT_KEY = Path(os.environ.get("ENGEL_MAIN_SERVER_SSH_KEY", str(Path.home() / ".ssh" / "engel_ai_main_ct246_ed25519")))
TRAINING_LOG = "/opt/engel/memory/discord_bridge/ENGEL_DISCORD_CHAT_TRAINING.jsonl"
PERSISTENT_LOG = "/opt/engel/memory/persistent_chat/ENGEL_AI_MAIN_LLM_CHAT_MEMORY.jsonl"
PUBLIC_LEAK_TERMS = (
    "systemctl",
    "ct 246",
    "reverse ssh",
    "ssh tunnel",
    "/opt/engel",
    "127.0.0.1",
    "192.168.",
    "workspace_receipt_path",
    "runtime_provider",
    "selected_provider",
    "server chat route",
)


user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002
KEYEVENTF_KEYUP = 0x0002
SW_RESTORE = 9
VK_CONTROL = 0x11
VK_V = 0x56
VK_RETURN = 0x0D
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004

kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalUnlock.restype = wintypes.BOOL
kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalFree.restype = wintypes.HGLOBAL
user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
user32.SetClipboardData.restype = wintypes.HANDLE


class Rect(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + f"_p{os.getpid()}"


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_prompts(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    prompts = payload.get("prompts") if isinstance(payload, dict) else None
    if not isinstance(prompts, list):
        return []
    return [str(item).strip() for item in prompts if str(item).strip()]


def ssh_output(*remote_args: str, timeout: int = 20) -> str:
    command = [
        "ssh",
        "-i",
        str(CT_KEY),
        "-p",
        str(CT_PORT),
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=8",
        f"{CT_USER}@{CT_HOST}",
        *remote_args,
    ]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "CT246 SSH command failed").strip())
    return result.stdout


def remote_line_count(path: str) -> int:
    output = ssh_output("wc", "-l", path)
    match = re.search(r"^\s*(\d+)", output)
    if not match:
        raise RuntimeError(f"could not parse line count for {path}")
    return int(match.group(1))


def recent_training_rows(limit: int = 40) -> list[dict[str, Any]]:
    output = ssh_output("tail", "-n", str(limit), TRAINING_LOG)
    rows: list[dict[str, Any]] = []
    for line in output.splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def recent_persistent_rows(limit: int = 240) -> list[dict[str, Any]]:
    output = ssh_output("tail", "-n", str(limit), PERSISTENT_LOG)
    rows: list[dict[str, Any]] = []
    for line in output.splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def remote_receipt_payload(path: str) -> dict[str, Any]:
    clean = str(path or "").strip()
    allowed_root = "/opt/engel/reports/engel_standalone_chat_llm/chat_receipts/"
    if not clean.startswith(allowed_root) or not clean.endswith(".json"):
        return {}
    try:
        value = json.loads(ssh_output("cat", "--", clean, timeout=20))
    except (RuntimeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _parse_utc(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def local_model_proof(prompt: str, not_before_utc: str) -> dict[str, Any]:
    not_before = _parse_utc(not_before_utc)
    for row in reversed(recent_persistent_rows()):
        if str(row.get("prompt") or "").strip() != prompt:
            continue
        scope = str(row.get("chat_context_scope") or "")
        if not scope.startswith("discord:"):
            continue
        updated = str(row.get("updated_at_utc") or row.get("created_at_utc") or "")
        updated_at = _parse_utc(updated)
        if not_before is not None and (updated_at is None or updated_at < not_before):
            continue
        receipt = remote_receipt_payload(str(row.get("workspace_receipt_path") or ""))
        evidence = dict(receipt)
        evidence.update({key: value for key, value in row.items() if value is not None and value != ""})
        if not str(evidence.get("provider") or evidence.get("runtime_provider") or "").strip() and row.get("provider_api_enabled") is None:
            continue
        proof = evaluate_local_first_evidence(evidence)
        return {
            **proof,
            "chat_context_scope": scope,
            "updated_at_utc": updated,
        }
    return {"verified": False, "error": "no matching CT246 model receipt"}


def find_discord_window() -> int:
    handles: list[int] = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    @callback_type
    def collect(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        title = buffer.value
        if title == "Discord" or title.endswith(" - Discord"):
            handles.append(int(hwnd))
        return True

    user32.EnumWindows(collect, 0)
    return handles[0] if handles else 0


def discord_window_title(hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def ensure_discord_channel(timeout: float = 30.0) -> tuple[int, bool]:
    was_running = bool(find_discord_window())
    os.startfile(f"discord://-/channels/{GUILD_ID}/{CHANNEL_ID}")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        hwnd = find_discord_window()
        if hwnd and discord_window_title(hwnd).startswith("#general | Engel AI Main Chat"):
            user32.ShowWindow(hwnd, SW_RESTORE)
            user32.SetForegroundWindow(hwnd)
            time.sleep(2.0 if was_running else 8.0)
            return hwnd, was_running
        time.sleep(1.0)
    raise RuntimeError("logged-in Discord desktop window did not become available")


def set_clipboard_text(text: str) -> None:
    encoded = (text + "\0").encode("utf-16-le")
    handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(encoded))
    if not handle:
        raise RuntimeError("GlobalAlloc failed for Discord clipboard input")
    pointer = kernel32.GlobalLock(handle)
    if not pointer:
        kernel32.GlobalFree(handle)
        raise RuntimeError("GlobalLock failed for Discord clipboard input")
    ctypes.memmove(pointer, encoded, len(encoded))
    kernel32.GlobalUnlock(handle)
    for _ in range(20):
        if user32.OpenClipboard(None):
            break
        time.sleep(0.05)
    else:
        kernel32.GlobalFree(handle)
        raise RuntimeError("could not open Windows clipboard")
    try:
        user32.EmptyClipboard()
        if not user32.SetClipboardData(CF_UNICODETEXT, handle):
            raise RuntimeError("SetClipboardData failed")
        handle = 0
    finally:
        user32.CloseClipboard()
        if handle:
            kernel32.GlobalFree(handle)


def key(vk: int, down: bool) -> None:
    user32.keybd_event(vk, 0, 0 if down else KEYEVENTF_KEYUP, 0)


def submit_discord_prompt(hwnd: int, prompt: str) -> None:
    rect = Rect()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        raise RuntimeError("could not read Discord window bounds")
    width = rect.right - rect.left
    height = rect.bottom - rect.top
    if width < 700 or height < 500:
        raise RuntimeError(f"Discord window is too small for guarded input: {width}x{height}")
    user32.ShowWindow(hwnd, SW_RESTORE)
    user32.SetForegroundWindow(hwnd)
    set_clipboard_text(prompt)
    time.sleep(0.4)
    user32.SetCursorPos(rect.left + int(width * 0.53), rect.bottom - 48)
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    time.sleep(0.3)
    key(VK_CONTROL, True)
    key(VK_V, True)
    key(VK_V, False)
    key(VK_CONTROL, False)
    time.sleep(0.25)
    key(VK_RETURN, True)
    key(VK_RETURN, False)


def normalized_reply(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold()).strip()


def wait_for_training_row(prompt: str, baseline_count: int, timeout: float) -> tuple[dict[str, Any] | None, int]:
    deadline = time.monotonic() + timeout
    latest_count = baseline_count
    while time.monotonic() < deadline:
        time.sleep(5.0)
        latest_count = remote_line_count(TRAINING_LOG)
        if latest_count <= baseline_count:
            continue
        for row in reversed(recent_training_rows()):
            if str(row.get("prompt") or "").strip() == prompt:
                return row, latest_count
    return None, latest_count


def assess_row(
    row: dict[str, Any] | None,
    previous_replies: set[str],
    prior_turns: list[dict[str, Any]] | None = None,
) -> list[str]:
    if not row:
        return ["no CT246 Discord training receipt for the visible owner message"]
    failures: list[str] = []
    reply = str(row.get("assistant_reply") or "").strip()
    low = reply.casefold()
    if str(row.get("discord_author_id") or "") != OWNER_ID:
        failures.append("Discord sender was not locked to Joshua owner ID")
    if str(row.get("discord_authority_level") or "") != "owner":
        failures.append("Discord owner authority was not preserved")
    if str(row.get("route") or "") != "discord_chat_model":
        failures.append("turn did not use the normal Engel Discord chat model route")
    if row.get("training_sample_eligible") is not True or row.get("quality_gate_blocked") is True:
        failures.append("CT quality gate blocked the turn; audit receipt exists but no training sample was accepted")
    if not reply:
        failures.append("assistant reply was empty")
    prompt = str(row.get("prompt") or "").casefold()
    if "storefront" in prompt:
        stale_domain_terms = [
            term
            for term in ("equipment cutout", "rooftop", "parapet", "screen footprint", "plan view")
            if term in low and term not in prompt
        ]
        if stale_domain_terms:
            failures.append(
                "reply carried stale rooftop/plan context into the storefront turn: "
                + ", ".join(stale_domain_terms)
            )
    if "```" in reply and not any(
        term in prompt
        for term in [
            "code",
            "script",
            "python",
            "javascript",
            "typescript",
            "rust",
            "powershell",
            "function",
            "program",
            "build an app",
            "create an app",
            "make an app",
        ]
    ):
        failures.append("ordinary conversation was wrapped in a code block")
    if "last answer" in prompt and ("handled by engel" in prompt or "guessing" in prompt):
        invented_proof = [term for term in ("file path", "return code", "proof receipt", "receipt path") if term in low]
        if invented_proof:
            failures.append("reply invented previous-turn proof: " + ", ".join(invented_proof))
    if row.get("reply_was_weak_or_repeated") is True:
        failures.append("bridge marked the reply weak or repeated")
    if low.startswith("from engel's memory:"):
        failures.append("reply exposed a raw semantic-memory retrieval dump instead of a conversational answer")
    product_voice = [
        term
        for term in (
            "assist you",
            "feel free",
            "how can i assist",
            "i'm here to help you with",
            "i am here to help you with",
            "if you encounter any issues",
            "if you need assistance",
            "if you need any",
            "let's continue working together",
            "let us continue working together",
            "working together efficiently",
        )
        if term in low
    ]
    if product_voice and any(term in prompt for term in ("feel normal", "normal person", "more casually", "little formal")):
        failures.append("reply used generic product-assistant language: " + ", ".join(product_voice))
    leaks = [term for term in PUBLIC_LEAK_TERMS if term in low]
    if leaks:
        failures.append("public reply leaked backend terms: " + ", ".join(leaks))
    normalized = normalized_reply(reply)
    if normalized and normalized in previous_replies:
        failures.append("assistant reply repeated an earlier reply verbatim")
    if normalized:
        previous_replies.add(normalized)
    prior_turns = prior_turns or []
    profile_drift_terms = (
        "mechanical design",
        "cad/cam",
        "3d modeling",
        "cutting machine",
        "shop drawing",
        "drafting",
    )
    target_turn: dict[str, Any] | None = None
    if any(term in prompt for term in ("normal person", "more casually", "little formal")) and prior_turns:
        target_turn = prior_turns[-1]
    elif "two messages ago" in prompt and len(prior_turns) >= 2:
        target_turn = prior_turns[-2]
    if target_turn:
        target_text = " ".join(
            (
                str(target_turn.get("prompt") or ""),
                str(target_turn.get("assistant_reply") or ""),
            )
        ).casefold()
        normal_thread_target = any(
            term in target_text for term in ("normal", "natural", "conversation", "following the thread")
        )
        if normal_thread_target:
            if not any(term in low for term in ("normal", "natural", "conversation", "thread")):
                failures.append("reply lost the recent normal-conversation subject")
            drift = [term for term in profile_drift_terms if term in low]
            if drift:
                failures.append("reply mixed unrelated profile/work facts into the recent turn: " + ", ".join(drift))
            sentence_count = len(
                [part for part in re.split(r"(?<=[.!?])(?:\s+|$)", reply) if part.strip()]
            )
            if sentence_count > 2:
                failures.append("casual conversation reply exceeded two sentences")
            if any(term in prompt for term in ("normal person", "more casually", "little formal")) and not re.search(
                r"\b(i|i'm|i am|i've|i will|i'll|we|we're|it's|yeah)\b", low
            ):
                failures.append("casual rewrite described Engel in the third person")
    if "two messages ago" in prompt and not any(
        low.startswith(prefix) for prefix in ("we were", "we talked", "you asked", "you said", "two messages ago")
    ):
        failures.append("two-messages-ago recall did not answer directly")
    if "two messages ago" in prompt and "but now" in low:
        failures.append("two-messages-ago recall blended in the newer rewrite")
    expectations: list[str] = []
    if "profession" in prompt:
        expectations = ["draft", "cad", "design"]
    elif "kind of work" in prompt:
        expectations = ["draft", "drawing", "design", "bim", "modular", "automation"]
    elif "same engel" in prompt:
        expectations = ["same", "one engel", "desktop", "discord"]
    elif "media feature" in prompt:
        expectations = ["media", "gif", "image", "animation"]
        if "media library" in low or "main menu" in low:
            failures.append("reply invented a desktop Media Library instead of recalling the real Discord media lane")
    elif "not sure" in prompt:
        expectations = ["ask", "confirm", "not sure", "do not know", "don't know"]
    elif "two messages ago" in prompt:
        expectations = ["normal", "conversation", "media", "gif", "formal"]
    elif "jz drafting" in prompt:
        expectations = ["draft", "design", "business"]
    elif "drafting workflow" in prompt:
        expectations = ["draft", "drawing", "cad", "dimension", "check"]
    if expectations and not any(term in low for term in expectations):
        failures.append("reply did not address the prompt's expected subject")
    return failures


def close_discord() -> None:
    subprocess.run(["taskkill", "/IM", "Discord.exe", "/T", "/F"], capture_output=True, text=True, timeout=20, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run real owner messages through the logged-in Discord desktop UI.")
    parser.add_argument("--minutes", type=float, default=60.0)
    parser.add_argument("--template", default=str(DEFAULT_TEMPLATE))
    parser.add_argument("--max-prompts", type=int, default=0)
    parser.add_argument("--reply-timeout", type=float, default=180.0)
    parser.add_argument("--close-on-exit", action="store_true")
    parser.add_argument(
        "--allow-verified-provider-escalation",
        action="store_true",
        help="accept a provider turn only when its CT receipt proves local failure first",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    prompts = load_prompts(Path(args.template).resolve())
    if args.max_prompts > 0:
        prompts = prompts[: args.max_prompts]
    if not prompts:
        raise SystemExit("Discord owner UI training template has no prompts")
    requested_seconds = max(1.0, args.minutes * 60.0)
    run_id = "engel_discord_owner_ui_training_" + stamp()
    event_path = REPORT_DIR / f"ENGEL_DISCORD_OWNER_UI_TRAINING_{run_id}.jsonl"
    report_path = REPORT_DIR / f"ENGEL_DISCORD_OWNER_UI_TRAINING_{run_id}.json"
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    started_at = iso_now()
    started_mono = time.monotonic()
    deadline = started_mono + requested_seconds
    interval = requested_seconds / len(prompts)
    before_training = remote_line_count(TRAINING_LOG)
    before_persistent = remote_line_count(PERSISTENT_LOG)
    hwnd, was_running = ensure_discord_channel()
    results: list[dict[str, Any]] = []
    previous_replies: set[str] = set()
    try:
        for index, prompt in enumerate(prompts):
            due = started_mono + index * interval
            while time.monotonic() < due:
                time.sleep(min(5.0, due - time.monotonic()))
            baseline = remote_line_count(TRAINING_LOG)
            submitted_at = iso_now()
            submit_discord_prompt(hwnd, prompt)
            print(json.dumps({"event": "discord_owner_prompt_submitted", "index": index + 1, "prompt": prompt}, ensure_ascii=False), flush=True)
            row, observed_count = wait_for_training_row(prompt, baseline, max(15.0, args.reply_timeout))
            if row is None and index == 0:
                hwnd, _ = ensure_discord_channel()
                baseline = remote_line_count(TRAINING_LOG)
                submit_discord_prompt(hwnd, prompt)
                print(json.dumps({"event": "discord_owner_prompt_retried", "index": index + 1}, ensure_ascii=False), flush=True)
                row, observed_count = wait_for_training_row(prompt, baseline, max(15.0, args.reply_timeout))
            failures = assess_row(row, previous_replies, results)
            model_proof = local_model_proof(prompt, submitted_at) if row is not None else {"verified": False, "error": "Discord receipt missing"}
            route_verified = model_proof.get("verified") is True or (
                args.allow_verified_provider_escalation
                and model_proof.get("verified_local_first_escalation") is True
            )
            if not route_verified:
                failures.append(
                    "turn did not prove a local Engel model or a provider escalation after local failure"
                )
            prompt_low = prompt.casefold()
            if any(
                term in prompt_low
                for term in ("incomplete", "missing", "unconfirmed", "not shown", "conflict", "unknown")
            ):
                semantic_quality = model_proof.get("local_semantic_quality")
                if not isinstance(semantic_quality, dict):
                    semantic_quality = model_proof.get("local_ct_lora_first_semantic_quality")
                if not isinstance(semantic_quality, dict) or semantic_quality.get("required") is not True:
                    failures.append("incomplete-input turn did not activate the CT semantic quality gate")
            result = {
                "prompt_index": index + 1,
                "prompt": prompt,
                "submitted_at_utc": submitted_at,
                "training_count_before": baseline,
                "training_count_after": observed_count,
                "receipt_found": row is not None,
                "assistant_reply": str((row or {}).get("assistant_reply") or ""),
                "route": str((row or {}).get("route") or ""),
                "owner_id_verified": str((row or {}).get("discord_author_id") or "") == OWNER_ID,
                "local_model_proof": model_proof,
                "training_sample_eligible": (row or {}).get("training_sample_eligible") is True,
                "failures": failures,
                "ok": not failures,
            }
            results.append(result)
            with event_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps({"schema": "engel_discord_owner_ui_training_event_v1", "run_id": run_id, **result}, ensure_ascii=False) + "\n")
            print(json.dumps({"event": "discord_owner_turn", "index": index + 1, "ok": not failures, "reply": result["assistant_reply"][:220]}, ensure_ascii=False), flush=True)
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            print(json.dumps({"event": "discord_owner_training_wait", "seconds_remaining": int(max(0, remaining))}), flush=True)
            time.sleep(min(30.0, max(0.1, remaining)))
    finally:
        if args.close_on_exit and not was_running:
            close_discord()
    after_training = remote_line_count(TRAINING_LOG)
    after_persistent = remote_line_count(PERSISTENT_LOG)
    actual_seconds = time.monotonic() - started_mono
    report = {
        "schema": "engel_discord_owner_ui_training_report_v1",
        "run_id": run_id,
        "started_at_utc": started_at,
        "finished_at_utc": iso_now(),
        "requested_minutes": args.minutes,
        "actual_duration_seconds": round(actual_seconds, 3),
        "real_logged_in_owner_ui": True,
        "discord_user_token_used": False,
        "guild_id": GUILD_ID,
        "channel_id": CHANNEL_ID,
        "owner_id": OWNER_ID,
        "allow_verified_provider_escalation": args.allow_verified_provider_escalation,
        "prompt_count": len(prompts),
        "passed_prompt_count": sum(1 for item in results if item.get("ok") is True),
        "local_only_turn_count": sum(
            1 for item in results
            if item.get("local_model_proof", {}).get("verified") is True
        ),
        "verified_pipeline_escalation_count": sum(
            1 for item in results
            if item.get("local_model_proof", {}).get("verified_local_first_escalation") is True
        ),
        "training_lines_before": before_training,
        "training_lines_after": after_training,
        "persistent_lines_before": before_persistent,
        "persistent_lines_after": after_persistent,
        "results": results,
    }
    report["ok"] = (
        actual_seconds >= requested_seconds
        and len(results) == len(prompts)
        and all(item.get("ok") is True for item in results)
        and after_training >= before_training + len(prompts)
        and after_persistent > before_persistent
    )
    report["status"] = "PASS" if report["ok"] else "FAIL"
    write_json(report_path, report)
    print(json.dumps({"event": "discord_owner_training_complete", "status": report["status"], "report": str(report_path)}, ensure_ascii=False), flush=True)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
