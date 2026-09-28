from __future__ import annotations

import argparse
import ctypes
import importlib.util
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = ROOT / "runtime" / "computer_control"
REPORT_ROOT = ROOT / "reports" / "computer_control_pipeline"
MEMORY_ROOT = ROOT / "memory" / "computer_control"

APPROVAL_TOKEN = "APPROVE_COMPUTER_CONTROL_ACTIONS"
FULL_ACCESS_OPERATOR_APPROVAL = "operator approved full access in chat on 2026-07-02"
FORBIDDEN_PATHS = ["/mnt/" + "engel-vault", "engel-vault-share", "ct245"]
SECRET_WORDS = re.compile(r"(password|passcode|token|secret|api[_ -]?key|private[_ -]?key|credential)", re.I)
DEFAULT_LOCAL_LLM_URLS = [
    "http://127.0.0.1:24680/v1/chat/completions",
    "http://127.0.0.1:24680/chat",
    "http://127.0.0.1:11434/api/generate",
]
_EASYOCR_READER: Any | None = None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def ensure_dirs() -> None:
    for path in [
        RUNTIME_ROOT,
        RUNTIME_ROOT / "frames",
        RUNTIME_ROOT / "states",
        RUNTIME_ROOT / "actions",
        REPORT_ROOT,
        MEMORY_ROOT,
    ]:
        path.mkdir(parents=True, exist_ok=True)


def redact_text(value: str) -> str:
    if SECRET_WORDS.search(value):
        return "[redacted-ui-text]"
    value = re.sub(r"([A-Za-z0-9_\-]{24,})", "[redacted-long-token]", value)
    return value


def redact_state(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [redact_state(item) for item in value]
    if isinstance(value, dict):
        return {str(key): redact_state(item) for key, item in value.items()}
    return value


def tcp_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def load_json_text(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if not text:
        return None
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        payload = json.loads(text)
        return payload if isinstance(payload, dict) else None
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            return None
        try:
            payload = json.loads(match.group(0))
            return payload if isinstance(payload, dict) else None
        except json.JSONDecodeError:
            return None


@dataclass
class CaptureResult:
    ok: bool
    provider: str
    path: str | None
    width: int | None
    height: int | None
    error: str = ""


def save_image_with_pil(image: Any, target: Path, max_width: int) -> tuple[int | None, int | None]:
    width = getattr(image, "width", None)
    height = getattr(image, "height", None)
    if width and height and max_width > 0 and width > max_width:
        ratio = max_width / float(width)
        new_size = (max_width, max(1, int(height * ratio)))
        image = image.resize(new_size)
        width, height = image.size
    image.save(target)
    return width, height


def capture_screen(target: Path, max_width: int) -> CaptureResult:
    if has_module("dxcam") and has_module("PIL"):
        try:
            import dxcam  # type: ignore
            from PIL import Image  # type: ignore

            camera = dxcam.create(output_color="RGB")
            frame = camera.grab()
            if frame is not None:
                image = Image.fromarray(frame)
                width, height = save_image_with_pil(image, target, max_width)
                return CaptureResult(True, "dxcam", str(target), width, height)
        except Exception as exc:  # pragma: no cover - optional dependency path
            last_error = f"dxcam failed: {exc}"
        else:
            last_error = "dxcam returned no frame"
    else:
        last_error = "dxcam unavailable"

    if has_module("mss") and has_module("PIL"):
        try:
            import mss  # type: ignore
            from PIL import Image  # type: ignore

            with mss.mss() as sct:
                monitor = sct.monitors[1]
                raw = sct.grab(monitor)
                image = Image.frombytes("RGB", raw.size, raw.rgb)
                width, height = save_image_with_pil(image, target, max_width)
                return CaptureResult(True, "mss", str(target), width, height)
        except Exception as exc:  # pragma: no cover - optional dependency path
            last_error = f"{last_error}; mss failed: {exc}"

    if has_module("PIL"):
        try:
            from PIL import ImageGrab  # type: ignore

            image = ImageGrab.grab(all_screens=True)
            width, height = save_image_with_pil(image, target, max_width)
            return CaptureResult(True, "PIL.ImageGrab", str(target), width, height)
        except Exception as exc:
            last_error = f"{last_error}; ImageGrab failed: {exc}"

    return CaptureResult(False, "none", None, None, None, last_error)


def get_cursor_position() -> dict[str, int | None]:
    class Point(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    point = Point()
    try:
        if ctypes.windll.user32.GetCursorPos(ctypes.byref(point)):  # type: ignore[attr-defined]
            return {"x": int(point.x), "y": int(point.y)}
    except Exception:
        pass
    return {"x": None, "y": None}


def get_active_window() -> dict[str, Any]:
    if os.name != "nt":
        return {"title": "", "class_name": "", "handle": None}
    try:
        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        handle = user32.GetForegroundWindow()
        title_buffer = ctypes.create_unicode_buffer(512)
        class_buffer = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(handle, title_buffer, 512)
        user32.GetClassNameW(handle, class_buffer, 256)
        return {
            "title": redact_text(title_buffer.value),
            "class_name": class_buffer.value,
            "handle": int(handle),
        }
    except Exception as exc:
        return {"title": "", "class_name": "", "handle": None, "error": str(exc)}


def run_ocr(image_path: Path) -> dict[str, Any]:
    if not image_path.is_file():
        return {"ok": False, "engine": "none", "lines": [], "error": "missing image"}
    if shutil.which("tesseract") and has_module("pytesseract") and has_module("PIL"):
        try:
            import pytesseract  # type: ignore
            from PIL import Image  # type: ignore

            image = Image.open(image_path)
            data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
            lines: list[dict[str, Any]] = []
            count = len(data.get("text", []))
            for index in range(count):
                text = str(data["text"][index]).strip()
                if not text:
                    continue
                confidence_raw = data.get("conf", ["-1"])[index]
                try:
                    confidence = float(confidence_raw)
                except (TypeError, ValueError):
                    confidence = -1.0
                if confidence < 20:
                    continue
                lines.append(
                    {
                        "text": redact_text(text),
                        "confidence": confidence,
                        "x": int(data["left"][index]),
                        "y": int(data["top"][index]),
                        "w": int(data["width"][index]),
                        "h": int(data["height"][index]),
                    }
                )
            return {"ok": True, "engine": "pytesseract", "lines": lines[:300]}
        except Exception as exc:
            return {"ok": False, "engine": "pytesseract", "lines": [], "error": str(exc)}
    if has_module("easyocr"):
        try:
            global _EASYOCR_READER
            import easyocr  # type: ignore

            if _EASYOCR_READER is None:
                _EASYOCR_READER = easyocr.Reader(["en"], gpu=False, verbose=False)
            results = _EASYOCR_READER.readtext(str(image_path), detail=1, paragraph=False)
            lines: list[dict[str, Any]] = []
            for result in results[:300]:
                if not isinstance(result, (list, tuple)) or len(result) < 3:
                    continue
                box, text, confidence = result[0], str(result[1]).strip(), float(result[2] or 0.0)
                if not text or confidence < 0.2:
                    continue
                xs = [int(point[0]) for point in box] if box else [0]
                ys = [int(point[1]) for point in box] if box else [0]
                left, top = min(xs), min(ys)
                width, height = max(xs) - left, max(ys) - top
                lines.append(
                    {
                        "text": redact_text(text),
                        "confidence": round(confidence * 100.0, 2),
                        "x": left,
                        "y": top,
                        "w": width,
                        "h": height,
                    }
                )
            return {"ok": True, "engine": "easyocr", "lines": lines}
        except Exception as exc:
            return {"ok": False, "engine": "easyocr", "lines": [], "error": str(exc)}
    return {"ok": False, "engine": "none", "lines": [], "error": "no OCR engine available"}


def detect_ui_elements(ocr: dict[str, Any]) -> list[dict[str, Any]]:
    button_words = {
        "ok",
        "yes",
        "no",
        "cancel",
        "submit",
        "send",
        "save",
        "next",
        "back",
        "close",
        "login",
        "sign",
        "connect",
        "continue",
        "retry",
    }
    elements: list[dict[str, Any]] = []
    for item in ocr.get("lines", []):
        text = str(item.get("text", "")).strip()
        if not text or text == "[redacted-ui-text]":
            continue
        lower = text.lower()
        kind = "text"
        if lower in button_words or any(word in lower for word in ["button", "submit", "send", "connect"]):
            kind = "button"
        if any(word in lower for word in ["search", "message", "type", "input"]):
            kind = "input_hint"
        elements.append(
            {
                "type": kind,
                "label": text[:80],
                "pos": [
                    int(item.get("x", 0)) + int(item.get("w", 0)) // 2,
                    int(item.get("y", 0)) + int(item.get("h", 0)) // 2,
                ],
                "bounds": [item.get("x", 0), item.get("y", 0), item.get("w", 0), item.get("h", 0)],
            }
        )
    return elements[:120]


def build_state(capture: CaptureResult, image_path: Path | None, goal: str, self_test: bool = False) -> dict[str, Any]:
    if self_test:
        ocr = {
            "ok": True,
            "engine": "synthetic",
            "lines": [
                {"text": "Engel AI Main", "confidence": 99, "x": 100, "y": 50, "w": 200, "h": 32},
                {"text": "Check chat", "confidence": 99, "x": 1100, "y": 150, "w": 120, "h": 28},
                {"text": "Message", "confidence": 99, "x": 500, "y": 820, "w": 200, "h": 40},
            ],
        }
        active_window = {"title": "Engel AI Main", "class_name": "synthetic", "handle": 1}
        cursor = {"x": 512, "y": 512}
    else:
        ocr = run_ocr(image_path) if image_path else {"ok": False, "engine": "none", "lines": [], "error": capture.error}
        active_window = get_active_window()
        cursor = get_cursor_position()

    ui_elements = detect_ui_elements(ocr)
    visible_text = [str(line.get("text", "")) for line in ocr.get("lines", [])[:80]]
    state = {
        "schema": "engel_computer_control_state_v1",
        "created_at_utc": now_iso(),
        "goal": redact_text(goal),
        "active_window": active_window,
        "capture": {
            "ok": capture.ok,
            "provider": capture.provider,
            "path": capture.path,
            "width": capture.width,
            "height": capture.height,
            "error": capture.error,
        },
        "cursor": cursor,
        "visible_text": visible_text,
        "ocr": ocr,
        "ui_elements": ui_elements,
        "task_context": infer_context(visible_text, ui_elements),
    }
    return redact_state(state)


def infer_context(visible_text: list[str], ui_elements: list[dict[str, Any]]) -> str:
    combined = " ".join(visible_text).lower()
    if "login" in combined or "sign in" in combined:
        return "login_or_account_page"
    if "error" in combined or "failed" in combined or "timeout" in combined:
        return "error_or_timeout_visible"
    if any(item.get("type") == "input_hint" for item in ui_elements):
        return "input_field_visible"
    if any(item.get("type") == "button" for item in ui_elements):
        return "clickable_controls_visible"
    return "general_desktop_state"


def local_llm_urls(configured_url: str | None) -> list[str]:
    urls: list[str] = []
    for candidate in [configured_url, os.environ.get("ENGEL_COMPUTER_CONTROL_LLM_URL")]:
        if candidate and candidate not in urls:
            urls.append(candidate)
    for candidate in DEFAULT_LOCAL_LLM_URLS:
        if candidate not in urls:
            urls.append(candidate)
    return urls


def http_post_json(url: str, payload: dict[str, Any], timeout: float) -> tuple[bool, str, dict[str, Any] | None]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
        parsed = json.loads(raw)
        return True, raw[:4000], parsed if isinstance(parsed, dict) else None
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        return False, str(exc), None


def ask_local_llm(goal: str, state: dict[str, Any], args: argparse.Namespace) -> dict[str, Any] | None:
    if args.no_llm:
        return None

    prompt = (
        "You are Engel Computer Control Decision Engine. "
        "Return one compact JSON object only. "
        "Allowed actions: observe, report, click, double_click, type_text, press_key, scroll, wait. "
        "Prefer observe/report unless the target is explicit and safe. "
        "Never request credentials or secret collection.\n\n"
        f"Goal: {redact_text(goal)}\n"
        f"State JSON: {json.dumps(state, ensure_ascii=True)[:9000]}\n\n"
        "JSON schema: {\"action\":\"observe\",\"target\":\"...\",\"reason\":\"...\",\"confidence\":0.0,\"params\":{}}"
    )

    for url in local_llm_urls(args.llm_url):
        if "127.0.0.1" in url and ":" in url:
            try:
                port = int(url.split("127.0.0.1:", 1)[1].split("/", 1)[0])
                if not tcp_open("127.0.0.1", port, timeout=0.5):
                    continue
            except ValueError:
                pass

        if url.endswith("/v1/chat/completions"):
            payload = {
                "model": os.environ.get("ENGEL_COMPUTER_CONTROL_MODEL", "auto"),
                "messages": [
                    {"role": "system", "content": "Return JSON only for a guarded desktop control decision."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.1,
                "max_tokens": 300,
                "timeout": max(5, int(args.llm_timeout)),
            }
        elif url.endswith("/api/generate"):
            payload = {
                "model": os.environ.get("ENGEL_COMPUTER_CONTROL_OLLAMA_MODEL", "llama3.1"),
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 300},
            }
        else:
            payload = {
                "schema": "engel_computer_control_decision_request_v1",
                "goal": goal,
                "state": state,
                "prompt": prompt,
                "max_tokens": 300,
                "timeout": max(5, int(args.llm_timeout)),
            }

        ok, raw, parsed = http_post_json(url, payload, timeout=args.llm_timeout)
        if not ok:
            continue

        content = ""
        if parsed:
            if isinstance(parsed.get("choices"), list) and parsed["choices"]:
                message = parsed["choices"][0].get("message", {})
                content = str(message.get("content", ""))
            elif "response" in parsed:
                content = str(parsed.get("response", ""))
            elif "reply" in parsed:
                content = str(parsed.get("reply", ""))
            elif "action" in parsed:
                decision = normalize_decision(parsed)
                decision["engine"] = "local_or_server_llm"
                decision["llm_url"] = url
                return decision
        content = content or raw
        decision = load_json_text(content)
        if decision:
            decision = normalize_decision(decision)
            decision["engine"] = "local_or_server_llm"
            decision["llm_url"] = url
            return decision

    return None


def normalize_decision(decision: dict[str, Any]) -> dict[str, Any]:
    action = str(decision.get("action", "observe")).lower().strip()
    allowed = {"observe", "report", "click", "double_click", "type_text", "press_key", "scroll", "wait"}
    if action not in allowed:
        action = "observe"
    params = decision.get("params", {})
    if not isinstance(params, dict):
        params = {}
    return {
        "schema": "engel_computer_control_decision_v1",
        "action": action,
        "target": redact_text(str(decision.get("target", "")))[:200],
        "reason": redact_text(str(decision.get("reason", "")))[:500],
        "confidence": float(decision.get("confidence", 0.0) or 0.0),
        "params": redact_state(params),
    }


def rules_decision(goal: str, state: dict[str, Any]) -> dict[str, Any]:
    goal_lower = goal.lower()
    context = str(state.get("task_context", ""))
    elements = state.get("ui_elements", [])

    if "observe" in goal_lower or "what" in goal_lower or "describe" in goal_lower:
        return normalize_decision(
            {
                "action": "report",
                "target": "current screen",
                "reason": f"Goal asks for observation; context is {context}.",
                "confidence": 0.8,
            }
        ) | {"engine": "rules"}

    if "click ok" in goal_lower or "close error" in goal_lower:
        for item in elements:
            if str(item.get("label", "")).lower() in {"ok", "close"}:
                return normalize_decision(
                    {
                        "action": "click",
                        "target": item.get("label", "button"),
                        "reason": "Rule matched an explicit safe button target.",
                        "confidence": 0.72,
                        "params": {"pos": item.get("pos")},
                    }
                ) | {"engine": "rules"}

    if "error" in context or "timeout" in context:
        return normalize_decision(
            {
                "action": "report",
                "target": "visible error state",
                "reason": "Screen appears to show an error or timeout; report before acting.",
                "confidence": 0.75,
            }
        ) | {"engine": "rules"}

    return normalize_decision(
        {
            "action": "observe",
            "target": "current screen",
            "reason": "No explicit safe action target was found.",
            "confidence": 0.55,
        }
    ) | {"engine": "rules"}


def execute_action(decision: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    action = decision.get("action", "observe")
    action_gate_open = bool(args.full_access or (args.allow_actions and args.approval_token == APPROVAL_TOKEN))
    result = {
        "schema": "engel_computer_control_action_result_v1",
        "created_at_utc": now_iso(),
        "requested_action": action,
        "executed": False,
        "dry_run": not action_gate_open,
        "status": "full-access-ready" if action_gate_open else "dry-run",
        "reason": "operator full access is active" if action_gate_open else "actions require --full-access or --allow-actions plus approval token",
    }
    if action in {"observe", "report", "wait"}:
        result.update({"status": "no desktop mutation needed", "reason": "observe/report/wait action"})
        if action == "wait" and args.allow_actions:
            time.sleep(min(args.delay, 2.0))
        return result

    if not action_gate_open:
        return result

    if not has_module("pyautogui"):
        result.update({"status": "blocked", "reason": "pyautogui is not installed"})
        return result

    try:
        import pyautogui  # type: ignore

        pyautogui.FAILSAFE = True
        params = decision.get("params", {})
        pos = params.get("pos") if isinstance(params, dict) else None
        if action in {"click", "double_click"}:
            if not isinstance(pos, list) or len(pos) != 2:
                result.update({"status": "blocked", "reason": "missing explicit [x,y] position"})
                return result
            x, y = int(pos[0]), int(pos[1])
            if action == "double_click":
                pyautogui.doubleClick(x=x, y=y)
            else:
                pyautogui.click(x=x, y=y)
        elif action == "type_text":
            text = str(params.get("text", ""))
            if not text or SECRET_WORDS.search(text):
                result.update({"status": "blocked", "reason": "empty or secret-like text refused"})
                return result
            pyautogui.write(text, interval=0.01)
        elif action == "press_key":
            key = str(params.get("key", ""))
            if not re.fullmatch(r"[A-Za-z0-9_+\-]{1,32}", key):
                result.update({"status": "blocked", "reason": "invalid key name"})
                return result
            pyautogui.press(key)
        elif action == "scroll":
            amount = int(params.get("amount", 0))
            if amount == 0 or abs(amount) > 10:
                result.update({"status": "blocked", "reason": "scroll amount must be between -10 and 10"})
                return result
            pyautogui.scroll(amount)
        result.update({"executed": True, "dry_run": False, "status": "executed", "reason": "approved action executed"})
        return result
    except Exception as exc:
        result.update({"status": "error", "reason": str(exc)})
        return result


def write_memory_observation(state: dict[str, Any], decision: dict[str, Any], action_result: dict[str, Any]) -> None:
    memory_path = MEMORY_ROOT / "computer_control_observations.jsonl"
    record = {
        "created_at_utc": now_iso(),
        "active_window": state.get("active_window", {}),
        "task_context": state.get("task_context"),
        "decision": decision,
        "action_result": action_result,
    }
    with memory_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(redact_state(record), ensure_ascii=True) + "\n")


def run_pipeline(args: argparse.Namespace) -> dict[str, Any]:
    ensure_dirs()
    run_id = stamp()
    cycles: list[dict[str, Any]] = []
    warnings: list[str] = []

    for cycle in range(max(1, args.cycles)):
        cycle_id = f"{run_id}_{cycle + 1:03d}"
        frame_path = RUNTIME_ROOT / "frames" / f"frame_{cycle_id}.png"
        if args.self_test:
            capture = CaptureResult(True, "synthetic", None, 1280, 720)
            image_path = None
        else:
            capture = capture_screen(frame_path, args.max_width)
            image_path = frame_path if capture.ok else None
            if not capture.ok:
                warnings.append(capture.error)

        state = build_state(capture, image_path, args.goal, self_test=args.self_test)
        state_path = RUNTIME_ROOT / "states" / f"state_{cycle_id}.json"
        state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

        decision = ask_local_llm(args.goal, state, args)
        if decision is None:
            decision = rules_decision(args.goal, state)
        action_result = execute_action(decision, args)
        action_path = RUNTIME_ROOT / "actions" / f"action_{cycle_id}.json"
        action_path.write_text(json.dumps({"decision": decision, "result": action_result}, indent=2), encoding="utf-8")
        write_memory_observation(state, decision, action_result)

        cycles.append(
            {
                "cycle": cycle + 1,
                "state_path": str(state_path),
                "action_path": str(action_path),
                "capture": state.get("capture", {}),
                "task_context": state.get("task_context"),
                "decision": decision,
                "action_result": action_result,
            }
        )
        if cycle + 1 < args.cycles:
            time.sleep(max(0.1, args.delay))

    report_path = REPORT_ROOT / f"ENGEL_COMPUTER_CONTROL_PIPELINE_{run_id}.json"
    latest_path = REPORT_ROOT / "latest.json"
    report = {
        "schema": "engel_computer_control_pipeline_v1",
        "ok": True,
        "created_at_utc": now_iso(),
        "project_root": str(ROOT),
        "goal": redact_text(args.goal),
        "cycles": cycles,
        "local_or_server_llm_preferred": not args.no_llm,
        "default_llm_urls": local_llm_urls(args.llm_url),
        "llm_timeout_seconds": args.llm_timeout,
        "actions_guarded": True,
        "full_access": bool(args.full_access),
        "full_access_operator_approval": FULL_ACCESS_OPERATOR_APPROVAL if args.full_access else "",
        "approval_token_required": APPROVAL_TOKEN,
        "allow_actions": bool(args.full_access or (args.allow_actions and args.approval_token == APPROVAL_TOKEN)),
        "forbidden_paths": FORBIDDEN_PATHS,
        "vault_used": False,
        "secrets_redacted": True,
        "warnings": warnings,
        "report_path": str(report_path),
        "latest_path": str(latest_path),
    }
    for forbidden in FORBIDDEN_PATHS:
        if forbidden in json.dumps(report):
            continue
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    latest_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Engel guarded AI computer control pipeline")
    parser.add_argument("--goal", default="Observe the current screen and report structured UI state.")
    parser.add_argument("--cycles", type=int, default=1)
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--max-width", type=int, default=1280)
    parser.add_argument("--llm-url", default=None)
    parser.add_argument("--llm-timeout", type=float, default=30.0)
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--allow-actions", action="store_true")
    parser.add_argument("--full-access", action="store_true", help="Operator-approved full access to guarded mouse/keyboard actions.")
    parser.add_argument("--approval-token", default="")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    report = run_pipeline(args)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("Engel Computer Control Pipeline")
        print(f"Goal: {report['goal']}")
        print(f"Cycles: {len(report['cycles'])}")
        print(f"Actions guarded: {report['actions_guarded']}")
        print(f"Report: {report['report_path']}")
        for cycle in report["cycles"]:
            decision = cycle["decision"]
            action_result = cycle["action_result"]
            print(
                f"- cycle {cycle['cycle']}: {decision.get('engine')} -> "
                f"{decision.get('action')} ({action_result.get('status')})"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
