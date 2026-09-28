#!/usr/bin/env python3
"""Side-by-side comparison point for Engel chat.

Runs the SAME prompt through (a) the live Engel chat lane (the local-first service on
127.0.0.1:8765, exactly as the app and Discord see it) and (b) the newest installed
reference model (NVIDIA Nemotron 3.5 Lightning 30B-A3B via the standalone llama.cpp
b10423 build), then writes one receipt with both replies and timings.

Why this exists (operator, 2026-08-14): "Chat needs a comparison point for Chat."
A weak live reply ("which tool do you want to use to create the PDF...") is only
visibly weak next to what another model does with the identical ask. This tool makes
that comparison a one-command receipt instead of an impression.

Boundaries: the live-lane call is sent with chat_only=true so a comparison can never
dispatch work orders or actions (same narrow-only flag the Discord peer lane uses).
The reference model runs as a bounded subprocess with its own timeout. Nothing here
writes to training packs - a comparison is evidence, not a training row.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import re
import subprocess
import time
import urllib.error
import urllib.request

CHAT_URL = os.environ.get("ENGEL_CHAT_COMPARE_CHAT_URL", "http://127.0.0.1:8765/chat")
NEMOTRON_BIN_DIR = Path(
    os.environ.get(
        "ENGEL_NEMOTRON_BIN_DIR", "/opt/engel/tools/llama-cpp-b10423/llama-b10423"
    )
)
NEMOTRON_MODEL = Path(
    os.environ.get(
        "ENGEL_NEMOTRON_MODEL",
        "/opt/engel/models-active/llm/nemotron-3.5-lightning-30b-a3b/"
        "NVIDIA-Nemotron-3.5-Lightning-30B-A3B-UD-Q4_K_M.gguf",
    )
)
REPORT_DIR = Path(os.environ.get("ENGEL_CHAT_COMPARE_REPORT_DIR", "/opt/engel/reports/chat_compare"))

# 6 threads leaves headroom for the live chat service on the same container; a
# comparison must never starve the lane it is comparing against.
NEMOTRON_THREADS = int(os.environ.get("ENGEL_NEMOTRON_THREADS", "6") or "6")
NEMOTRON_TIMEOUT_SECONDS = float(os.environ.get("ENGEL_NEMOTRON_TIMEOUT_SECONDS", "420") or "420")

THINK_BLOCK = re.compile(r"\[Start thinking\].*?\[End thinking\]\s*", re.S)
STATS_LINE = re.compile(r"^\[ Prompt: .*t/s.*\]\s*$")


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def build_live_payload(prompt: str, with_actions: bool = False) -> dict:
    """Mirror the request shape the Discord bridge sends, minus Discord identity.

    chat_only is the narrow-only guard: it can only DISABLE action dispatch on the CT
    side, never enable anything, so a default comparison run cannot create orders (the
    exact failure mode peer chatter hit on 2026-08-13: 11 orders in 3 minutes).
    with_actions=True drops the guard so a build-shaped ask shows what the APP would
    actually do (scaffold + run in /opt/engel/workspaces) - the operator opts into the
    side effects explicitly via --with-actions; it is never the default.
    """
    payload = {
        "prompt": str(prompt or "").strip() or "Hello Engel",
        "source": "chat_compare",
        "chat_only": True,
        "timeout": 90,
        "max_tokens": 420,
        "prefer_fast_local_chat": True,
        "metadata": {"purpose": "chat_compare_reference_run", "training_opt_out": True},
    }
    if with_actions:
        del payload["chat_only"]
    return payload


def ask_live_lane(prompt: str, with_actions: bool = False) -> dict:
    """One retry on 422/502/503, the same lesson the Discord bridge learned live:
    those statuses mean THIS attempt failed, not that the turn is unanswerable."""
    payload = json.dumps(build_live_payload(prompt, with_actions)).encode("utf-8")
    last_error = ""
    for attempt in range(2):
        started = time.time()
        try:
            req = urllib.request.Request(
                CHAT_URL, data=payload, headers={"Content-Type": "application/json"}
            )
            # A build-lane turn scaffolds, generates and RUNS code - minutes, not
            # seconds - so the action-enabled probe needs the long leash.
            with urllib.request.urlopen(req, timeout=560 if with_actions else 150) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
            receipt = data.get("receipt") if isinstance(data.get("receipt"), dict) else {}
            return {
                "ok": True,
                "reply": str(data.get("assistant_reply") or data.get("reply") or "").strip(),
                "selected_provider": str(receipt.get("selected_provider") or data.get("provider") or ""),
                "seconds": round(time.time() - started, 1),
                "attempts": attempt + 1,
            }
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:400]
            last_error = f"HTTP {exc.code}: {body}"
            if exc.code in (422, 502, 503) and attempt == 0:
                time.sleep(1.5)
                continue
            break
        except Exception as exc:  # noqa: BLE001 - recorded honestly below
            last_error = f"{type(exc).__name__}: {exc}"
            break
    return {"ok": False, "reply": "", "error": last_error, "seconds": 0.0}


def parse_llama_cli_output(stdout: str) -> str:
    """Pull the actual reply out of llama-cli's single-turn transcript.

    The b10423 chat UI prints a banner, command help, the echoed "> <prompt>" line,
    the reply, then a "[ Prompt: x t/s | Generation: y t/s ]" stats line. The reply is
    everything between the LAST echoed prompt line and the stats line.
    """
    lines = str(stdout or "").replace("\r", "\n").split("\n")
    last_echo = -1
    for i, line in enumerate(lines):
        if line.startswith("> ") and len(line) > 2:
            last_echo = i
    if last_echo < 0:
        return ""
    reply: list[str] = []
    for line in lines[last_echo + 1:]:
        if STATS_LINE.match(line.strip()) or line.strip() in {">", "Exiting..."}:
            break
        reply.append(line)
    return "\n".join(reply).strip()


def strip_thinking(reply: str) -> str:
    """Drop a closed [Start thinking]...[End thinking] block; a reasoning trace is not
    the answer. An UNCLOSED block is kept verbatim - honest raw output beats a guess
    about where thinking ended."""
    return THINK_BLOCK.sub("", str(reply or "")).strip()


def ask_nemotron(prompt: str, max_tokens: int) -> dict:
    cli = NEMOTRON_BIN_DIR / "llama-cli"
    if not cli.is_file() or not NEMOTRON_MODEL.is_file():
        return {"ok": False, "reply": "", "error": "nemotron binary or model missing", "seconds": 0.0}
    cmd = [
        str(cli), "-m", str(NEMOTRON_MODEL), "-st", "-p", str(prompt),
        "-n", str(max_tokens), "--temp", "1.0", "--top-p", "0.95",
        "-t", str(NEMOTRON_THREADS), "--no-display-prompt",
    ]
    env = dict(os.environ, LD_LIBRARY_PATH=str(NEMOTRON_BIN_DIR))
    started = time.time()
    try:
        proc = subprocess.run(
            cmd, cwd=str(NEMOTRON_BIN_DIR), env=env, capture_output=True,
            text=True, timeout=NEMOTRON_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "reply": "", "error": f"timeout after {NEMOTRON_TIMEOUT_SECONDS}s", "seconds": round(time.time() - started, 1)}
    raw = parse_llama_cli_output(proc.stdout)
    reply = strip_thinking(raw)
    if not reply and not raw:
        return {
            "ok": False, "reply": "",
            "error": f"no reply parsed (exit {proc.returncode}): {proc.stdout[-300:]!r}",
            "seconds": round(time.time() - started, 1),
        }
    return {
        "ok": True,
        "reply": reply,
        "raw_reply": raw if raw != reply else "",
        "seconds": round(time.time() - started, 1),
    }


def compare(prompts: list[str], max_tokens: int, with_actions: bool = False) -> dict:
    rows = []
    for prompt in prompts:
        live = ask_live_lane(prompt, with_actions)
        reference = ask_nemotron(prompt, max_tokens)
        rows.append({"prompt": prompt, "live_lane": live, "nemotron_3_5_lightning": reference})
    note = (
        "with_actions run: the live lane could route to the build/scaffold lanes and "
        "REALLY built/ran what it describes, exactly as an app turn would."
        if with_actions
        else
        "chat_only suppresses ALL action lanes on the CT side (build/scaffold/"
        "workspace), so for a build-shaped ask this shows the TEXT lane's answer, "
        "not what the app would actually do - rerun with --with-actions to see the "
        "app behavior (real side effects in /opt/engel/workspaces)."
    )
    receipt = {
        "schema": "engel_chat_compare_receipt_v1",
        "created_at_utc": iso_now(),
        "chat_url": CHAT_URL,
        "reference_model": NEMOTRON_MODEL.name,
        "reference_runtime": "llama.cpp b10423 standalone CPU build",
        "chat_only": not with_actions,
        "note": note,
        "rows": rows,
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORT_DIR / f"ENGEL_CHAT_COMPARE_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    out.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    receipt["receipt_path"] = str(out)
    return receipt


def selftest() -> int:
    checks: list[tuple[str, bool]] = []
    payload = build_live_payload("hello")
    checks.append(("chat_only is true by default", payload["chat_only"] is True))
    checks.append(("training opt-out is declared", payload["metadata"]["training_opt_out"] is True))
    checks.append(("empty prompt gets a safe default", build_live_payload("")["prompt"] == "Hello Engel"))
    action_payload = build_live_payload("hello", with_actions=True)
    # ABSENT, not false: the CT service treats an explicit chat_only=false as a
    # per-turn decision; omitting the key leaves it exactly app-shaped.
    checks.append(("--with-actions omits chat_only entirely", "chat_only" not in action_payload))
    checks.append(("--with-actions still opts out of training",
                   action_payload["metadata"]["training_opt_out"] is True))
    transcript = (
        "Loading model... |-\\|/\nbuild      : b10423\nmodel      : x.gguf\n"
        "available commands:\n  /exit or Ctrl+C     stop or exit\n\n"
        "> In one short sentence: what is the capital of France?\n"
        "[Start thinking]\nsome hidden work\n[End thinking]\n"
        "The capital of France is Paris.\n\n"
        "[ Prompt: 5.4 t/s | Generation: 6.1 t/s ]\n\n> \n\nExiting...\n"
    )
    parsed = parse_llama_cli_output(transcript)
    checks.append(("reply parsed from transcript", "capital of France is Paris" in parsed))
    checks.append(("stats line excluded", "t/s" not in parsed))
    checks.append(("banner excluded", "build" not in parsed and "/exit" not in parsed))
    cleaned = strip_thinking(parsed)
    checks.append(("closed thinking block stripped", cleaned == "The capital of France is Paris."))
    checks.append(("unclosed thinking kept verbatim",
                   strip_thinking("[Start thinking]\npartial") == "[Start thinking]\npartial"))
    failed = [name for name, ok in checks if not ok]
    for name, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    print(f"{len(checks) - len(failed)}/{len(checks)} selftest checks passed")
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare the live Engel chat lane against Nemotron 3.5 Lightning.")
    parser.add_argument("--prompt", action="append", default=[], help="prompt to compare (repeatable)")
    # A reasoning model spends its first few hundred tokens thinking; 300 got eaten
    # before the visible answer started (live 2026-08-14 first run). 800 at ~6 t/s is
    # still ~2 minutes per prompt.
    parser.add_argument("--max-tokens", type=int, default=800, help="reference-model token budget per prompt")
    parser.add_argument(
        "--with-actions", action="store_true",
        help="drop the chat_only guard so the live lane may build/scaffold for real (app behavior)",
    )
    parser.add_argument("--selftest", action="store_true", help="offline checks only, no network or model")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    prompts = [p for p in (args.prompt or []) if str(p).strip()]
    if not prompts:
        parser.error("at least one --prompt is required (or --selftest)")
    receipt = compare(prompts, args.max_tokens, with_actions=args.with_actions)
    for row in receipt["rows"]:
        live = row["live_lane"]
        ref = row["nemotron_3_5_lightning"]
        print("=" * 72)
        print("PROMPT:", row["prompt"])
        print(f"-- live lane ({live.get('selected_provider') or 'n/a'}, {live.get('seconds')}s, ok={live.get('ok')}):")
        print((live.get("reply") or live.get("error") or "")[:800])
        print(f"-- nemotron-3.5-lightning ({ref.get('seconds')}s, ok={ref.get('ok')}):")
        print((ref.get("reply") or ref.get("error") or "")[:800])
    print("=" * 72)
    print("RECEIPT:", receipt["receipt_path"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
