#!/usr/bin/env python3
"""
Engel AI Main — multi-provider failover run loop ("long-run using other AI").

Ported from OpenClaw (MIT-licensed, https://github.com/openclaw/openclaw) —
its embedded-agent runner. One request drives one RUN; inside the run a bounded
outer retry/failover loop attempts an ordered chain of provider "lanes"
(primary + fallbacks[]). On a CLASSIFIED failure it first retries/rotates the
same lane for transient reasons, then ESCALATES to the next lane — which can be a
different AI — announcing each fallback. The first usable reply wins. This is how
Engel "long-runs using other AI": a turn keeps working by escalating across every
provider it has instead of failing on the first error.

Design source (OpenClaw dist/):
  * embedded-agent-*.js       — the outer `while` attempt loop + escalate-on-FailoverError
  * selection-*.js            — resolveMaxRunRetryIterations(candidates, cfg)
  * failover-error-*.d.ts     — FailoverError { reason, provider, model, profileId, suspend }
  * types-*.d.ts              — FailoverReason (the 15 codes, reproduced verbatim below)
  * types.openclaw-*.d.ts     — AgentModelListConfig { primary, fallbacks[] },
                                AgentRunRetriesConfig { base:24, perProfile:8, min:32, max:160 }
  * fallback-notice-state-*.js — announces the active fallback to the user mid-run

Reimplemented natively in Python over Engel's own provider bridges (no OpenClaw
runtime dependency). Attribution kept per the MIT license.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


# --- FailoverReason: the 15 codes, verbatim from OpenClaw types-CF0DHR3y.d.ts ---
FAILOVER_REASONS = (
    "auth", "auth_permanent", "format", "rate_limit", "overloaded", "billing",
    "server_error", "timeout", "context_overflow", "model_not_found",
    "session_expired", "empty_response", "no_error_details", "unclassified", "unknown",
)

# Reasons worth a same-lane retry/rotate before escalating (transient).
TRANSIENT_REASONS = {"rate_limit", "overloaded", "server_error", "timeout", "empty_response", "no_error_details"}
# Reasons that are pointless to retry on the same lane — escalate immediately.
HARD_REASONS = {"auth", "auth_permanent", "billing", "model_not_found", "context_overflow", "format"}


class FailoverError(Exception):
    """Structured error carrying model fallback/failover metadata across layers.
    Mirrors OpenClaw's FailoverError."""

    def __init__(self, reason: str, provider: str = "", model: str = "",
                 profile_id: str = "", suspend: bool = False, detail: str = ""):
        super().__init__(f"{provider or 'lane'}:{model or '-'} failover reason={reason} {detail}".strip())
        self.reason = reason if reason in FAILOVER_REASONS else "unknown"
        self.provider = provider
        self.model = model
        self.profile_id = profile_id
        self.suspend = suspend
        self.detail = detail


def classify_failover(status_code: Optional[int], text: str, exc: Optional[BaseException]) -> str:
    """Classify a lane failure into a FailoverReason. Port of OpenClaw's classifier
    logic, mapped onto HTTP status + error text + Python exception types."""
    low = (text or "").lower()
    if exc is not None:
        if isinstance(exc, (TimeoutError,)) or "timed out" in low or "timeout" in low:
            return "timeout"
        if isinstance(exc, (ConnectionRefusedError,)):
            return "server_error"
        if isinstance(exc, urllib.error.URLError) and not isinstance(exc, urllib.error.HTTPError):
            return "server_error"  # lane unreachable -> escalate
    if status_code is not None:
        if status_code == 429:
            return "rate_limit"
        if status_code == 503:
            return "overloaded"
        if status_code in (500, 502, 504):
            return "server_error"
        if status_code == 408:
            return "timeout"
        if status_code in (401, 403):
            return "auth_permanent" if ("invalid" in low or "revoked" in low) else "auth"
        if status_code == 404:
            return "model_not_found"
        if status_code == 402:
            return "billing"
    # Body-text signals (for 2xx-with-error or bridge ok:false payloads).
    if any(k in low for k in ("quota", "rate limit", "resource_exhausted", "too many requests")):
        return "rate_limit"
    if any(k in low for k in ("overloaded", "capacity", "unavailable")):
        return "overloaded"
    if any(k in low for k in ("api key", "unauthorized", "permission", "no reachable")):
        return "auth"
    if any(k in low for k in ("context length", "context_overflow", "maximum context", "too long")):
        return "context_overflow"
    if any(k in low for k in ("not found", "no such model", "unknown model")):
        return "model_not_found"
    if "timed out" in low or "timeout" in low:
        return "timeout"
    if not low.strip():
        return "no_error_details"
    return "unclassified"


def resolve_max_run_retry_iterations(candidate_count: int, base: int = 24, per_profile: int = 8,
                                     lo: int = 32, hi: int = 160) -> int:
    """OpenClaw selection-*.js: base + max(1, candidates) * perProfile, clamped [min, max].
    This is the total 'keep working' budget for one run — a retry/failover budget,
    NOT an autonomous self-prompt counter."""
    raw = base + max(1, candidate_count) * per_profile
    return max(lo, min(hi, raw))


@dataclass
class Lane:
    """A provider 'lane' = one AI Engel can route a turn to. Equivalent to an entry
    in OpenClaw's { primary, fallbacks[] } model list."""
    id: str
    label: str
    call: Callable[[str, int, int], str]   # (prompt, timeout_s, max_tokens) -> reply text; raises FailoverError


@dataclass
class Attempt:
    lane: str
    ok: bool
    reason: str
    latency_ms: int
    reply_chars: int
    note: str = ""


@dataclass
class RunResult:
    ok: bool
    reply: str
    lane: str
    provider: str
    attempts: list = field(default_factory=list)
    iterations: int = 0
    elapsed_ms: int = 0
    status: str = ""


# ---------------------------------------------------------------------------
# Engel lanes — each hits a real Engel endpoint and raises FailoverError on fail.
# ---------------------------------------------------------------------------
def _post_json(url: str, body: dict, timeout: int) -> tuple[int, dict, str]:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return resp.status, json.loads(raw), raw
            except json.JSONDecodeError:
                return resp.status, {}, raw
    except urllib.error.HTTPError as e:
        raw = ""
        try:
            raw = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        raise FailoverError(classify_failover(e.code, raw, e), detail=f"HTTP {e.code}") from e
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        raise FailoverError(classify_failover(None, str(e), e), detail=str(e)[:200]) from e


def _extract_reply(payload: dict) -> str:
    if not isinstance(payload, dict):
        return ""
    for key in ("assistant_reply", "reply", "assistant_output_text"):
        v = payload.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    receipt = payload.get("receipt")
    if isinstance(receipt, dict):
        for key in ("assistant_reply", "reply", "assistant_output_text"):
            v = receipt.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()
    # OpenAI-shaped
    try:
        return str(payload["choices"][0]["message"]["content"]).strip()
    except Exception:
        return ""


def _make_bridge_lane(lane_id: str, label: str, port: int, provider: str) -> Lane:
    def call(prompt: str, timeout_s: int, max_tokens: int) -> str:
        status, payload, raw = _post_json(
            f"http://127.0.0.1:{port}/chat",
            {"prompt": prompt, "max_tokens": max_tokens, "timeout_seconds": timeout_s, "timeout": timeout_s},
            timeout_s + 5,
        )
        if isinstance(payload, dict) and payload.get("ok") is False:
            err = json.dumps(payload.get("receipt", payload))[:400]
            raise FailoverError(classify_failover(status, err, None), provider=provider, detail="bridge ok:false")
        reply = _extract_reply(payload)
        if not reply:
            raise FailoverError("empty_response", provider=provider, detail="no reply text")
        return reply
    return Lane(lane_id, label, call)


def _gpu_lane() -> Lane:
    def call(prompt: str, timeout_s: int, max_tokens: int) -> str:
        status, payload, raw = _post_json(
            "http://127.0.0.1:8899/v1/chat/completions",
            {"messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens,
             "temperature": 0.3, "stop": ["[Joshua]:", "\nUser:"]},
            timeout_s + 5,
        )
        reply = _extract_reply(payload)
        if not reply:
            raise FailoverError("empty_response", provider="rog-rtx2070-gpu", detail="no completion")
        return reply
    return Lane("rog-gpu", "ROG RTX 2070 GPU (llama.cpp)", call)


def _ct246_lane() -> Lane:
    def call(prompt: str, timeout_s: int, max_tokens: int) -> str:
        status, payload, raw = _post_json(
            "http://127.0.0.1:24680/chat",
            {"prompt": prompt, "provider": "local", "max_tokens": max_tokens, "timeout": min(timeout_s, 45)},
            timeout_s + 5,
        )
        if isinstance(payload, dict) and payload.get("ok") is False:
            raise FailoverError(classify_failover(status, raw, None), provider="ct246-local", detail="ct ok:false")
        reply = _extract_reply(payload)
        if not reply:
            raise FailoverError("empty_response", provider="ct246-local", detail="no reply")
        return reply
    return Lane("ct246-local", "CT246 local model (via tunnel)", call)


def default_engel_lanes() -> dict[str, Lane]:
    """Every AI Engel can route a chat turn to, keyed by id."""
    return {
        "rog-gpu": _gpu_lane(),
        "ct246-local": _ct246_lane(),
        "gemini-api": _make_bridge_lane("gemini-api", "Gemini API (gemini-2.5-flash)", 24886, "gemini"),
        "grok-cli": _make_bridge_lane("grok-cli", "Grok CLI", 24880, "xai"),
        "claude-cli": _make_bridge_lane("claude-cli", "Claude CLI (sonnet)", 24882, "anthropic"),
        "codex-cli": _make_bridge_lane("codex-cli", "Codex CLI (gpt-5.4)", 24888, "openai"),
        "chatgpt-browser": _make_bridge_lane("chatgpt-browser", "ChatGPT browser", 24884, "openai"),
    }


# Default ordered chain: fast local first, then cheap API, then CLIs, browser last.
DEFAULT_CHAIN = ["rog-gpu", "ct246-local", "gemini-api", "grok-cli", "claude-cli", "codex-cli", "chatgpt-browser"]

# Declarative provider catalog (OpenClaw models.providers port): add/reorder AIs
# in JSON with no code change. Falls back to the hardcoded lanes if absent.
DEFAULT_CATALOG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "runtime", "config", "engel_failover_catalog.json",
)


def _lane_from_catalog(lane_id: str, cfg: dict) -> Lane:
    kind = str(cfg.get("kind") or "engel-bridge")
    url = str(cfg.get("url") or "")
    label = str(cfg.get("label") or lane_id)
    provider = str(cfg.get("provider") or lane_id)

    if kind == "openai":
        def call(prompt: str, timeout_s: int, max_tokens: int) -> str:
            _s, payload, _r = _post_json(url, {
                "messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens,
                "temperature": 0.3, "stop": ["[Joshua]:", "\nUser:"]}, timeout_s + 5)
            reply = _extract_reply(payload)
            if not reply:
                raise FailoverError("empty_response", provider=provider, detail="no completion")
            return reply
    elif kind == "engel-chat":
        def call(prompt: str, timeout_s: int, max_tokens: int) -> str:
            status, payload, raw = _post_json(url, {
                "prompt": prompt, "provider": "local", "max_tokens": max_tokens,
                "timeout": min(timeout_s, 45)}, timeout_s + 5)
            if isinstance(payload, dict) and payload.get("ok") is False:
                raise FailoverError(classify_failover(status, raw, None), provider=provider, detail="ct ok:false")
            reply = _extract_reply(payload)
            if not reply:
                raise FailoverError("empty_response", provider=provider, detail="no reply")
            return reply
    else:  # engel-bridge
        def call(prompt: str, timeout_s: int, max_tokens: int) -> str:
            status, payload, _r = _post_json(url, {
                "prompt": prompt, "max_tokens": max_tokens,
                "timeout_seconds": timeout_s, "timeout": timeout_s}, timeout_s + 5)
            if isinstance(payload, dict) and payload.get("ok") is False:
                err = json.dumps(payload.get("receipt", payload))[:400]
                raise FailoverError(classify_failover(status, err, None), provider=provider, detail="bridge ok:false")
            reply = _extract_reply(payload)
            if not reply:
                raise FailoverError("empty_response", provider=provider, detail="no reply text")
            return reply
    return Lane(lane_id, label, call)


def load_catalog(path: Optional[str] = None) -> "tuple[dict[str, Lane], list[str]]":
    """Build lanes + default chain from the declarative catalog JSON. Falls back
    to the hardcoded lanes/chain if the file is missing or invalid."""
    path = path or DEFAULT_CATALOG_PATH
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        lanes = {lid: _lane_from_catalog(lid, cfg) for lid, cfg in (data.get("lanes") or {}).items()}
        chain = [c for c in (data.get("default_chain") or []) if c in lanes]
        if lanes and chain:
            return lanes, chain
    except Exception:
        pass
    return default_engel_lanes(), DEFAULT_CHAIN


def run_with_failover(
    prompt: str,
    chain: Optional[list[str]] = None,
    lanes: Optional[dict[str, Lane]] = None,
    *,
    timeout_s: int = 60,
    max_tokens: int = 1024,
    same_lane_rotations: int = 1,
    on_event: Optional[Callable[[dict], None]] = None,
) -> RunResult:
    """Port of OpenClaw's embedded-agent outer run loop.

    Attempts each lane in `chain` order. On a transient FailoverError it rotates
    (retries) the same lane up to `same_lane_rotations` times with backoff; on a
    hard reason it escalates immediately. Escalating to the next lane = "using
    another AI". First usable reply wins. Bounded by resolveMaxRunRetryIterations.
    """
    if lanes is None or chain is None:
        cat_lanes, cat_chain = load_catalog()
        if lanes is None:
            lanes = cat_lanes
        if chain is None:
            chain = cat_chain
    chain = [c for c in chain if c in lanes]
    if not chain:
        return RunResult(False, "", "", "", status="no valid lanes in chain")

    def emit(kind: str, **kw):
        if on_event:
            on_event({"event": kind, **kw})

    max_iters = resolve_max_run_retry_iterations(len(chain))
    started = time.perf_counter()
    attempts: list[Attempt] = []
    iterations = 0

    emit("run_start", chain=chain, max_iterations=max_iters, prompt_chars=len(prompt))

    for position, lane_id in enumerate(chain):
        lane = lanes[lane_id]
        rotation = 0
        while True:
            if iterations >= max_iters:
                emit("budget_exhausted", iterations=iterations)
                break
            iterations += 1
            emit("lane_attempt", lane=lane_id, label=lane.label, position=position + 1,
                 of=len(chain), iteration=iterations, rotation=rotation)
            t0 = time.perf_counter()
            try:
                reply = lane.call(prompt, timeout_s, max_tokens)
                lat = int((time.perf_counter() - t0) * 1000)
                attempts.append(Attempt(lane_id, True, "", lat, len(reply)))
                emit("lane_ok", lane=lane_id, latency_ms=lat, reply_chars=len(reply))
                return RunResult(
                    True, reply, lane_id, lane.label, attempts=attempts,
                    iterations=iterations, elapsed_ms=int((time.perf_counter() - started) * 1000),
                    status=f"replied via {lane.label}" + (f" after failover ({position} lane(s) skipped)" if position else ""),
                )
            except FailoverError as fe:
                lat = int((time.perf_counter() - t0) * 1000)
                attempts.append(Attempt(lane_id, False, fe.reason, lat, 0, fe.detail))
                emit("lane_fail", lane=lane_id, reason=fe.reason, latency_ms=lat, detail=fe.detail)
                # Transient + rotations left -> retry same lane; else escalate.
                if fe.reason in TRANSIENT_REASONS and rotation < same_lane_rotations:
                    rotation += 1
                    backoff = min(2.0, 0.4 * rotation)
                    emit("lane_rotate", lane=lane_id, rotation=rotation, backoff_s=backoff)
                    time.sleep(backoff)
                    continue
                # escalate
                if position + 1 < len(chain):
                    emit("escalate", to=chain[position + 1], from_lane=lane_id, reason=fe.reason)
                break
            except Exception as exc:  # unexpected -> classify + escalate
                lat = int((time.perf_counter() - t0) * 1000)
                reason = classify_failover(None, str(exc), exc)
                attempts.append(Attempt(lane_id, False, reason, lat, 0, str(exc)[:160]))
                emit("lane_fail", lane=lane_id, reason=reason, latency_ms=lat, detail=str(exc)[:160])
                if position + 1 < len(chain):
                    emit("escalate", to=chain[position + 1], from_lane=lane_id, reason=reason)
                break
        if iterations >= max_iters:
            break

    elapsed = int((time.perf_counter() - started) * 1000)
    emit("run_fail", attempts=len(attempts), iterations=iterations)
    return RunResult(False, "", "", "", attempts=attempts, iterations=iterations, elapsed_ms=elapsed,
                     status=f"all {len(chain)} lanes failed ({iterations} attempts)")


# ---------------------------------------------------------------------------
# CLI — the "long-run using other AI" demo. Prints a live verbose failover trace.
# ---------------------------------------------------------------------------
def _cli_event(ev: dict) -> None:
    k = ev.get("event")
    if k == "run_start":
        print(f"● run start — chain: {' -> '.join(ev['chain'])}  (budget {ev['max_iterations']} attempts)", file=sys.stderr)
    elif k == "lane_attempt":
        print(f"  ▸ [{ev['position']}/{ev['of']}] trying {ev['label']} …", file=sys.stderr)
    elif k == "lane_ok":
        print(f"  ✓ {ev['lane']} replied in {ev['latency_ms']}ms ({ev['reply_chars']} chars)", file=sys.stderr)
    elif k == "lane_fail":
        print(f"  ✗ {ev['lane']} failed: {ev['reason']} ({ev['latency_ms']}ms) {ev.get('detail','')}", file=sys.stderr)
    elif k == "lane_rotate":
        print(f"  ↻ retrying {ev['lane']} (rotation {ev['rotation']}, backoff {ev['backoff_s']}s)", file=sys.stderr)
    elif k == "escalate":
        print(f"  ↪ failing over to {ev['to']} (reason: {ev['reason']})", file=sys.stderr)
    elif k == "run_fail":
        print(f"● run failed after {ev['iterations']} attempts", file=sys.stderr)


def main(argv: Optional[list[str]] = None) -> int:
    # Windows consoles default to cp1252 and choke on the trace glyphs; keep the
    # nice Unicode where it works (logs/SSE/Flutter) and never crash a terminal.
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="Engel multi-AI failover run loop (ported from OpenClaw).")
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--chain", default="", help="comma-separated lane ids; default = " + ",".join(DEFAULT_CHAIN))
    ap.add_argument("--timeout", type=int, default=60)
    ap.add_argument("--max-tokens", type=int, default=512)
    ap.add_argument("--json", action="store_true", help="emit the full run receipt as JSON on stdout")
    args = ap.parse_args(argv)
    chain = [c.strip() for c in args.chain.split(",") if c.strip()] or None
    result = run_with_failover(args.prompt, chain=chain, timeout_s=args.timeout,
                               max_tokens=args.max_tokens, on_event=_cli_event)
    if args.json:
        print(json.dumps({
            "ok": result.ok, "reply": result.reply, "lane": result.lane, "provider": result.provider,
            "iterations": result.iterations, "elapsed_ms": result.elapsed_ms, "status": result.status,
            "attempts": [a.__dict__ for a in result.attempts],
        }, indent=2))
    else:
        print(f"\n=== {result.status} ({result.elapsed_ms}ms, {result.iterations} attempts) ===")
        if result.ok:
            print(result.reply)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
