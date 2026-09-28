"""On-demand cross-model consensus review for Engel AI Main (GAIS consensus lane).

Asks the same prompt to several INDEPENDENTLY-SERVED local voters, measures their
convergence with the deterministic agreement metric in engel_gais, and writes an
honest receipt. This is a REVIEW lane like engel_chat_compare, not a per-turn
vote: per-turn multi-model voting is not latency-feasible on this fleet today
(the CT in-process lanes share one model cache, and Nemotron 3.5 Lightning
reloads its 25GB GGUF per one-shot call at ~2 min/prompt), and the receipt says
exactly that instead of pretending Byzantine fault tolerance.

Voters (all local, run SEQUENTIALLY on purpose - parallel CT calls thrash the
shared model cache):
  routed    - the live routed chat lane, POST http://127.0.0.1:8765/chat (chat_only)
  quick     - the same service forced onto the fast local lane (prefer_fast_local_chat)
  gpu       - the ROG RTX 2070 llama.cpp server, POST :8899/v1/chat/completions
  nemotron  - one-shot llama-cli subprocess (opt-in via --include-nemotron; slow)

Runs on CT246 (paths and loopback URLs are CT-local). Usage:
  python3 tools/engel_gais_consensus.py --prompt "..." [--include-nemotron] [--max-tokens 320]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import engel_gais

SCHEMA = "engel_gais_consensus_v1"
ROOT = Path(__file__).resolve().parents[1]
RECEIPT_DIR = ROOT / "reports" / "gais_consensus"

CHAT_URL = os.environ.get("ENGEL_GAIS_ROUTED_CHAT_URL", "http://127.0.0.1:8765/chat")
GPU_URL = os.environ.get("ENGEL_ROG_GPU_CHAT_URL", "http://127.0.0.1:8899/v1/chat/completions")
NEMOTRON_BIN = Path(os.environ.get(
    "ENGEL_NEMOTRON_LLAMA_CLI",
    "/opt/engel/tools/llama-cpp-b10423/llama-b10423/llama-cli"))
NEMOTRON_GGUF = Path(os.environ.get(
    "ENGEL_NEMOTRON_GGUF",
    "/opt/engel/models-active/llm/nemotron-3.5-lightning-30b-a3b/"
    "NVIDIA-Nemotron-3.5-Lightning-30B-A3B-UD-Q4_K_M.gguf"))

# Agreement at/above this mean marks lexical consensus. Engineered threshold,
# same honesty rule as the confidence weights: declared, not statistically fit.
try:
    CONSENSUS_MEAN_THRESHOLD = float(
        os.environ.get("ENGEL_GAIS_CONSENSUS_THRESHOLD", "0.25") or 0.25)
    if not (0.0 < CONSENSUS_MEAN_THRESHOLD < 1.0):
        CONSENSUS_MEAN_THRESHOLD = 0.25
except ValueError:
    CONSENSUS_MEAN_THRESHOLD = 0.25


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _post_json(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body,
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def _vote_routed(prompt: str, max_tokens: int, *, prefer_fast: bool) -> tuple[str, str]:
    data = _post_json(CHAT_URL, {
        "prompt": prompt,
        "source": "gais_consensus",
        "chat_only": True,
        "timeout": 150,
        "max_tokens": max_tokens,
        "prefer_fast_local_chat": prefer_fast,
    }, timeout=180.0)
    reply = str(data.get("assistant_reply") or data.get("reply") or "").strip()
    receipt = data.get("receipt") if isinstance(data.get("receipt"), dict) else {}
    model_hint = str(receipt.get("selected_provider") or data.get("selected_provider") or "routed")
    return reply, model_hint


def _vote_gpu(prompt: str, max_tokens: int) -> tuple[str, str]:
    # single user-role message on purpose: the GPU big-lane model ignores the
    # system role, so anything important must ride in the user turn.
    data = _post_json(GPU_URL, {
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": max_tokens,
    }, timeout=120.0)
    choices = data.get("choices") or []
    reply = ""
    if choices and isinstance(choices[0], dict):
        reply = str(((choices[0].get("message") or {}).get("content")) or "").strip()
    return reply, str(data.get("model") or "rog_gpu_8899")


def _vote_nemotron(prompt: str, max_tokens: int) -> tuple[str, str]:
    if not NEMOTRON_BIN.is_file() or not NEMOTRON_GGUF.is_file():
        raise RuntimeError("nemotron llama-cli or GGUF not present on this host")
    env = dict(os.environ)
    env["LD_LIBRARY_PATH"] = str(NEMOTRON_BIN.parent)
    proc = subprocess.run(
        [str(NEMOTRON_BIN), "-m", str(NEMOTRON_GGUF), "-st", "-p", prompt,
         "-n", str(max(max_tokens, 800)), "--temp", "1.0", "--top-p", "0.95",
         "-t", "6", "--no-display-prompt"],
        capture_output=True, text=True, timeout=float(
            os.environ.get("ENGEL_NEMOTRON_TIMEOUT_SECONDS", "420") or 420),
        cwd=str(NEMOTRON_BIN.parent), env=env)
    if proc.returncode != 0:
        raise RuntimeError(f"llama-cli exit {proc.returncode}: {proc.stderr[-300:]}")
    text = proc.stdout
    # strip closed [Start thinking]...[End thinking] blocks, keep the answer
    while "[Start thinking]" in text and "[End thinking]" in text:
        head, _, rest = text.partition("[Start thinking]")
        _, _, tail = rest.partition("[End thinking]")
        text = head + tail
    # an UNCLOSED block means generation was cut mid-thought: keep only the head,
    # never leak half a thinking transcript into the vote
    if "[Start thinking]" in text:
        text = text.partition("[Start thinking]")[0]
    return text.strip(), "nemotron-3.5-lightning-30b-a3b"


def run_consensus(prompt: str, *, include_nemotron: bool = False,
                  max_tokens: int = 320) -> dict[str, Any]:
    voter_plan: list[tuple[str, Any]] = [
        ("routed", lambda: _vote_routed(prompt, max_tokens, prefer_fast=False)),
        ("quick", lambda: _vote_routed(prompt, max_tokens, prefer_fast=True)),
        ("gpu", lambda: _vote_gpu(prompt, max_tokens)),
    ]
    if include_nemotron:
        voter_plan.append(("nemotron", lambda: _vote_nemotron(prompt, max_tokens)))
    voters: list[dict[str, Any]] = []
    for name, call in voter_plan:  # sequential ON PURPOSE - shared model cache
        started = time.perf_counter()
        entry: dict[str, Any] = {"name": name}
        try:
            reply, model_hint = call()
            entry.update(ok=bool(reply), model_hint=model_hint,
                         reply=reply, reply_sha256=hashlib.sha256(
                             reply.encode("utf-8")).hexdigest())
            if not reply:
                entry["error"] = "empty reply"
        except Exception as exc:  # noqa: BLE001 - a dead voter is a recorded fact
            entry.update(ok=False, error=str(exc)[:300])
        entry["latency_ms"] = int((time.perf_counter() - started) * 1000)
        voters.append(entry)

    answered = [v for v in voters if v.get("ok")]
    agreement = engel_gais.consensus_agreement([v["reply"] for v in answered])
    # Numeric conflict VETOES consensus: two voters phrasing the same sentence
    # around different numbers is disagreement on the only substantive token,
    # however high the lexical convergence reads (caught by adversarial review:
    # "the answer is 7/9/12" scored 0.675 lexical agreement).
    numeric_conflict = bool(
        agreement.get("ok")
        and int(agreement.get("numeric_replies") or 0) >= 2
        and not agreement.get("numbers_agree"))
    consensus_reached = bool(
        agreement.get("ok")
        and not numeric_conflict
        and agreement.get("mean_pairwise_agreement", 0.0) >= CONSENSUS_MEAN_THRESHOLD)
    majority_voter = ""
    if agreement.get("ok"):
        majority_voter = answered[int(agreement["majority_index"])]["name"]

    # advisory tiebreaker from the trained reply-quality head, fail-open
    slm_scores: dict[str, Any] = {}
    try:
        from engel_slm_runtime import get_slm_runtime

        slm = get_slm_runtime()
        if slm.is_ready():
            for voter in answered:
                quality = slm.reply_quality(prompt, voter["reply"])
                if quality:
                    slm_scores[voter["name"]] = quality
    except Exception:  # noqa: BLE001
        pass

    receipt = {
        "schema": SCHEMA,
        "created_at_utc": _iso_now(),
        "prompt": prompt,
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "voters": [
            {**{k: v for k, v in voter.items() if k != "reply"},
             "reply": str(voter.get("reply") or "")[:800],
             "reply_chars": len(str(voter.get("reply") or "")),
             "reply_truncated": len(str(voter.get("reply") or "")) > 800}
            for voter in voters
        ],
        "voters_answered": len(answered),
        "agreement": agreement,
        "consensus_threshold": CONSENSUS_MEAN_THRESHOLD,
        "numeric_conflict": numeric_conflict,
        "consensus_reached": consensus_reached,
        "majority_voter": majority_voter,
        "slm_reply_quality_advisory": slm_scores,
        "byzantine_fault_tolerant": False,
        "honest_notes": [
            "on-demand review lane, not a per-turn vote",
            "routed and quick voters share the CT service (different lanes, same host), "
            "and the routed big lane is normally SERVED BY the same ROG llama.cpp "
            "process the gpu voter hits directly - agreement between routed and gpu "
            "can be self-correlation, not independence (check each voter's model_hint)",
            "reply_sha256 is computed over the FULL reply; the stored reply field is "
            "truncated at 800 chars when reply_truncated is true",
            "agreement measures lexical/numeric convergence between voters, not truth; "
            "a numeric conflict between voters vetoes consensus_reached",
        ],
    }
    RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = RECEIPT_DIR / f"ENGEL_GAIS_CONSENSUS_{stamp}.json"
    path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")
    receipt["receipt_path"] = str(path)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Engel GAIS cross-model consensus review")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--include-nemotron", action="store_true",
                        help="add the one-shot Nemotron voter (~2 min extra)")
    parser.add_argument("--max-tokens", type=int, default=320)
    args = parser.parse_args()
    receipt = run_consensus(args.prompt, include_nemotron=args.include_nemotron,
                            max_tokens=args.max_tokens)
    slim = dict(receipt)
    slim["voters"] = [
        {"name": v["name"], "ok": v.get("ok"), "model_hint": v.get("model_hint"),
         "latency_ms": v.get("latency_ms"), "error": v.get("error"),
         "reply_preview": str(v.get("reply") or "")[:160]}
        for v in receipt["voters"]
    ]
    print(json.dumps(slim, indent=2, ensure_ascii=False))
    return 0 if receipt["voters_answered"] >= 2 else 1


if __name__ == "__main__":
    raise SystemExit(main())
