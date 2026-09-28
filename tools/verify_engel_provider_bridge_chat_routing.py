#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports" / "codex_bridge"
DEFAULT_BASE_URL = "http://127.0.0.1:24680"


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def clip(value: Any, limit: int = 800) -> str:
    text = str(value or "")
    return text if len(text) <= limit else text[:limit] + "...[clipped]"


def http_json(method: str, url: str, payload: dict[str, Any] | None = None, timeout: int = 180) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        method=method,
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
        return {"ok": False, "status_code": exc.code, "error": clip(error_body or str(exc), 1400)}
    except Exception as exc:
        return {"ok": False, "status_code": 0, "error": clip(str(exc), 1400)}


def get_nested(data: dict[str, Any], *keys: str) -> Any:
    cur: Any = data
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def chat(base_url: str, prompt: str, timeout: int) -> dict[str, Any]:
    result = http_json("POST", base_url.rstrip("/") + "/chat", {"prompt": prompt}, timeout=timeout)
    if not result.get("ok"):
        return {
            "ok": False,
            "http_ok": False,
            "status_code": result.get("status_code"),
            "error": result.get("error", ""),
        }
    data = result.get("json") if isinstance(result.get("json"), dict) else {}
    receipt = data.get("receipt") if isinstance(data.get("receipt"), dict) else {}
    return {
        "ok": bool(data.get("ok")),
        "http_ok": True,
        "status": data.get("status", ""),
        "provider": data.get("provider", ""),
        "runtime_provider": data.get("runtime_provider", ""),
        "reply": clip(data.get("assistant_reply", ""), 1000),
        "bridge_used": bool(receipt.get("provider_bridge_used")),
        "route_reason": receipt.get("provider_bridge_route_reason", ""),
        "fallback_used": bool(receipt.get("explicit_provider_fallback_used")),
        "failed_provider": receipt.get("explicit_provider_failed_provider", ""),
        "memory": bool(receipt.get("persistent_chat_memory_appended")),
        "meeting_room": bool(receipt.get("meeting_room_server_used")),
        "attempts": [
            {
                "provider": attempt.get("provider", ""),
                "ok": attempt.get("ok"),
                "bridge_kind": attempt.get("bridge_kind", ""),
                "model": attempt.get("model", ""),
                "error": clip(attempt.get("error", ""), 500),
            }
            for attempt in (receipt.get("provider_bridge_attempts") if isinstance(receipt.get("provider_bridge_attempts"), list) else [])
            if isinstance(attempt, dict)
        ],
    }


def check_status(base_url: str, timeout: int) -> dict[str, Any]:
    result = http_json("GET", base_url.rstrip("/") + "/providers/status", timeout=timeout)
    if not result.get("ok"):
        return {"ok": False, "error": result.get("error", ""), "status_code": result.get("status_code")}
    data = result.get("json") if isinstance(result.get("json"), dict) else {}
    providers = data.get("providers") if isinstance(data.get("providers"), dict) else {}
    return {
        "ok": True,
        "chatgpt_route": bool(get_nested(providers, "openai", "local_route", "ok")),
        "claude_route": bool(get_nested(providers, "anthropic", "local_route", "ok")),
        "grok_route": bool(get_nested(providers, "xai", "local_route", "ok")),
        "gemini_route": bool(get_nested(providers, "gemini", "local_route", "ok")),
        "codex_route": bool(get_nested(providers, "codex", "local_route", "ok")),
        "grok_version": str(get_nested(providers, "xai", "local_route", "version") or ""),
        "codex_version": str(get_nested(providers, "codex", "local_route", "version") or ""),
        "grok_secret": bool(get_nested(providers, "xai", "secret_present")),
        "gemini_secret": bool(get_nested(providers, "gemini", "secret_present")),
        "gemini_usable": bool(get_nested(providers, "gemini", "usable")),
        "persistent_memory_path": str(data.get("persistent_memory_path") or ""),
        "updated_at_utc": str(data.get("updated_at_utc") or ""),
    }


def test_result(name: str, passed: bool, details: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "details": details}


def probe_memory_file(memory_path: str, markers: dict[str, str], max_lines: int = 1500) -> dict[str, Any]:
    path = Path(memory_path) if memory_path else Path()
    if not memory_path:
        return {"checked": False, "ok": False, "reason": "no memory path reported", "matches": {}}
    if not path.exists():
        return {"checked": False, "ok": False, "reason": f"memory path is not readable from this host: {memory_path}", "matches": {}}
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception as exc:
        return {"checked": False, "ok": False, "reason": f"failed reading memory path: {exc}", "matches": {}}
    window = lines[-max_lines:]
    matches: dict[str, Any] = {}
    for name, marker in markers.items():
        matched_line = ""
        matched_provider = ""
        matched_runtime = ""
        for line in reversed(window):
            if marker not in line:
                continue
            try:
                parsed = json.loads(line)
            except Exception:
                parsed = {}
            if isinstance(parsed, dict):
                prompt_text = str(parsed.get("prompt") or "")
                reply_text = str(parsed.get("assistant_reply") or parsed.get("assistant_output_text") or "")
                if marker not in prompt_text and marker not in reply_text:
                    continue
                matched_line = line[:1000]
                matched_provider = str(parsed.get("provider") or parsed.get("selected_provider") or "")
                matched_runtime = str(parsed.get("runtime_provider") or "")
            else:
                matched_line = line[:1000]
            break
        matches[name] = {
            "found": bool(matched_line),
            "marker": marker,
            "provider": matched_provider,
            "runtime_provider": matched_runtime,
            "preview": matched_line,
        }
    return {
        "checked": True,
        "ok": all(item.get("found") is True for item in matches.values()),
        "path": memory_path,
        "line_count": len(lines),
        "matches": matches,
    }


def build_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Engel Provider Bridge Chat Routing Verification",
        "",
        f"- Updated UTC: {report['updated_at_utc']}",
        f"- Base URL: `{report['base_url']}`",
        f"- Overall OK: `{report['overall_ok']}`",
        f"- Engel chat resilient OK: `{report['engel_chat_resilient_ok']}`",
        f"- Grok completion OK: `{report['grok_completion_ok']}`",
        f"- Gemini completion OK: `{report.get('gemini_completion_ok')}`",
        "",
        "## Provider Routes",
        "",
    ]
    status = report.get("status", {})
    for key in ("chatgpt_route", "claude_route", "grok_route", "gemini_route", "codex_route", "grok_version", "codex_version", "grok_secret", "gemini_secret", "gemini_usable", "persistent_memory_path"):
        lines.append(f"- {key}: `{status.get(key)}`")
    lines.extend(["", "## Tests", ""])
    for test in report.get("tests", []):
        details = test.get("details", {})
        lines.append(f"- {'PASS' if test.get('passed') else 'FAIL'} `{test.get('name')}`")
        if details.get("provider"):
            lines.append(f"  Provider: `{details.get('provider')}`")
        if details.get("route_reason"):
            lines.append(f"  Route reason: `{details.get('route_reason')}`")
        if details.get("runtime_provider"):
            lines.append(f"  Runtime: `{details.get('runtime_provider')}`")
        if details.get("reply"):
            lines.append(f"  Reply: {details.get('reply')}")
        if details.get("attempts"):
            attempts = ", ".join(f"{item.get('provider')}:{item.get('ok')}" for item in details.get("attempts", []))
            lines.append(f"  Attempts: `{attempts}`")
        if details.get("error"):
            lines.append(f"  Error: `{details.get('error')}`")
    memory_probe = report.get("persistent_memory_file_probe")
    if isinstance(memory_probe, dict):
        lines.extend(["", "## Persistent Memory File Probe", ""])
        lines.append(f"- Checked: `{memory_probe.get('checked')}`")
        lines.append(f"- OK: `{memory_probe.get('ok')}`")
        if memory_probe.get("path"):
            lines.append(f"- Path: `{memory_probe.get('path')}`")
        if memory_probe.get("reason"):
            lines.append(f"- Reason: {memory_probe.get('reason')}")
        matches = memory_probe.get("matches") if isinstance(memory_probe.get("matches"), dict) else {}
        for name, details in matches.items():
            if not isinstance(details, dict):
                continue
            lines.append(
                f"- {name}: found=`{details.get('found')}`, provider=`{details.get('provider')}`, runtime=`{details.get('runtime_provider')}`"
            )
    lines.extend(["", "## Notes", ""])
    lines.extend(f"- {note}" for note in report.get("notes", []))
    lines.append("")
    return "\n".join(lines)


def run(base_url: str, timeout: int) -> dict[str, Any]:
    started = time.perf_counter()
    status = check_status(base_url, timeout=min(timeout, 30))
    tests: list[dict[str, Any]] = []
    run_marker = "ENGEL_BRIDGE_VERIFY_" + stamp()
    markers = {
        "explicit_chatgpt": run_marker + "_A",
        "explicit_claude": run_marker + "_B",
        "explicit_codex": run_marker + "_C",
        "auto_code_routes_to_codex": run_marker + "_D",
        "explicit_grok_completion_or_fallback": run_marker + "_E",
        "explicit_gemini_completion_or_fallback": run_marker + "_F",
    }

    chatgpt = chat(
        base_url,
        f"Use ChatGPT for this check. Reply exactly: ChatGPT bridge works. Verification marker: {markers['explicit_chatgpt']}",
        timeout,
    )
    tests.append(
        test_result(
            "explicit_chatgpt",
            chatgpt.get("ok") is True
            and str(chatgpt.get("provider", "")).startswith("ChatGPT/OpenAI")
            and chatgpt.get("bridge_used") is True
            and chatgpt.get("memory") is True
            and chatgpt.get("meeting_room") is True,
            chatgpt,
        )
    )

    claude = chat(
        base_url,
        f"Use Claude for this check. Reply exactly: Claude bridge works. Verification marker: {markers['explicit_claude']}",
        timeout,
    )
    tests.append(
        test_result(
            "explicit_claude",
            claude.get("ok") is True
            and str(claude.get("provider", "")).startswith("Claude/Anthropic")
            and claude.get("bridge_used") is True
            and claude.get("memory") is True
            and claude.get("meeting_room") is True,
            claude,
        )
    )

    codex = chat(
        base_url,
        f"Use Codex for this check. Reply exactly: Codex bridge works. Verification marker: {markers['explicit_codex']}",
        timeout,
    )
    tests.append(
        test_result(
            "explicit_codex",
            codex.get("ok") is True
            and str(codex.get("provider", "")).startswith("Codex/OpenAI")
            and codex.get("bridge_used") is True
            and codex.get("memory") is True
            and codex.get("meeting_room") is True,
            codex,
        )
    )

    code_auto = chat(
        base_url,
        f"Debug this Python bug: my function prints the result but returns None. Give one short fix. Verification marker: {markers['auto_code_routes_to_codex']}",
        timeout,
    )
    tests.append(
        test_result(
            "auto_code_routes_to_codex",
            code_auto.get("ok") is True
            and str(code_auto.get("provider", "")).startswith("Codex/OpenAI")
            and code_auto.get("route_reason") == "code_or_review"
            and code_auto.get("memory") is True
            and code_auto.get("meeting_room") is True,
            code_auto,
        )
    )

    grok = chat(
        base_url,
        f"Use Grok for this check. Reply in one short sentence that Engel keeps answering if Grok is limited. Verification marker: {markers['explicit_grok_completion_or_fallback']}",
        timeout,
    )
    grok_completion_ok = (
        grok.get("ok") is True
        and str(grok.get("provider", "")).startswith("Grok/xAI")
        and grok.get("bridge_used") is True
        and grok.get("memory") is True
        and grok.get("meeting_room") is True
    )
    grok_resilient_ok = (
        grok.get("ok") is True
        and grok.get("fallback_used") is True
        and grok.get("failed_provider") == "xai"
        and grok.get("bridge_used") is True
        and grok.get("memory") is True
        and grok.get("meeting_room") is True
    )
    tests.append(test_result("explicit_grok_completion_or_fallback", grok_completion_ok or grok_resilient_ok, grok))

    gemini = chat(
        base_url,
        f"Use Gemini for this check. Reply in one short sentence that Gemini is part of Engel routing. Verification marker: {markers['explicit_gemini_completion_or_fallback']}",
        timeout,
    )
    gemini_completion_ok = (
        gemini.get("ok") is True
        and str(gemini.get("provider", "")).startswith("Gemini/Google")
        and gemini.get("bridge_used") is True
        and gemini.get("memory") is True
        and gemini.get("meeting_room") is True
    )
    gemini_resilient_ok = (
        gemini.get("ok") is True
        and gemini.get("fallback_used") is True
        and gemini.get("failed_provider") == "gemini"
        and gemini.get("bridge_used") is True
        and gemini.get("memory") is True
        and gemini.get("meeting_room") is True
    )
    tests.append(test_result("explicit_gemini_completion_or_fallback", gemini_completion_ok or gemini_resilient_ok, gemini))

    required_routes_ok = (
        status.get("ok") is True
        and status.get("chatgpt_route") is True
        and status.get("claude_route") is True
        and status.get("grok_route") is True
        and status.get("gemini_route") is True
        and status.get("codex_route") is True
    )
    chat_tests_ok = all(test.get("passed") for test in tests[:4])
    engel_chat_resilient_ok = required_routes_ok and chat_tests_ok and (grok_completion_ok or grok_resilient_ok) and (gemini_completion_ok or gemini_resilient_ok)
    notes: list[str] = []
    if not grok_completion_ok and grok_resilient_ok:
        notes.append("Grok route is reachable, but xAI did not return a Grok completion; Engel fallback preserved chat and memory capture.")
    if status.get("gemini_usable") is not True:
        notes.append("Gemini route is wired, but Gemini completion is unavailable until a Gemini/Google API key is added.")
    elif not gemini_completion_ok and gemini_resilient_ok:
        notes.append("Gemini route is reachable, but Gemini did not return a completion; Engel fallback preserved chat and memory capture.")
    if not required_routes_ok:
        notes.append("One or more provider routes are down; restore the ROG persistent link and bridge services.")
    memory_probe = probe_memory_file(str(status.get("persistent_memory_path") or ""), markers)
    if memory_probe.get("checked") is True and memory_probe.get("ok") is not True:
        notes.append("Persistent memory file was readable but did not include every verification marker.")
    if memory_probe.get("checked") is not True:
        notes.append("Persistent memory file probe was skipped on this host; run the verifier inside CT 246 for file-level memory proof.")

    return {
        "schema": "engel_provider_bridge_chat_routing_verification_v1",
        "ok": engel_chat_resilient_ok,
        "overall_ok": engel_chat_resilient_ok and grok_completion_ok and gemini_completion_ok,
        "engel_chat_resilient_ok": engel_chat_resilient_ok,
        "grok_completion_ok": grok_completion_ok,
        "gemini_completion_ok": gemini_completion_ok,
        "updated_at_utc": iso_now(),
        "base_url": base_url,
        "status": status,
        "tests": tests,
        "persistent_memory_file_probe": memory_probe,
        "notes": notes,
        "latency_ms": int((time.perf_counter() - started) * 1000),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify Engel AI Main provider bridge chat routing.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args(argv)

    report = run(args.base_url, args.timeout)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    marker = stamp()
    json_path = REPORT_DIR / f"ENGEL_PROVIDER_BRIDGE_CHAT_ROUTING_VERIFY_{marker}.json"
    md_path = REPORT_DIR / f"ENGEL_PROVIDER_BRIDGE_CHAT_ROUTING_VERIFY_{marker}.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(build_markdown(report), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "overall_ok": report["overall_ok"], "json": str(json_path), "markdown": str(md_path)}, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
