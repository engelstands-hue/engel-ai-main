"""Gate for the governing-verb intent rule that keeps ordinary chat out of the training-job
and training-launch lanes.

Why this exists
---------------
Card 7 of the capabilities curriculum ("routing each chat turn to the right lane by the verb
that governs it") had no verifier of its own to cite. In the 8-hour run the model answered by
inventing one (a fabricated `ENGEL_VERB_LANE_MAP_V1.json`), the same honest-gap-becomes-
fabrication failure the worker-liveness and recon cards showed. The remedy that worked twice
was to write the missing verifier and cite it; this is that verifier.

It pins the actual behaviour two real bugs turned on (see engel-ui-prompt-training-pipeline):

  * `_prompt_requests_training_job` fired on bare co-occurrence of "training" + "build", so
    a prompt asking to "build a compact evidence ledger" ABOUT training was answered with a
    training-package receipt instead of a real answer.
  * `_prompt_starts_local_training` fired on a bare "do", so the house rule "Do not propose
    an upgrade without a receipt" was one step from LAUNCHING a LoRA run from a chat line.

The fix required a verb to actually GOVERN the word "training". This verifier proves both the
positive contract (a real command still routes) and the negative contract (discussion does
not), and is deliberately non-vacuous: if either gate were widened back to bare co-occurrence,
the MUST-NOT cases below would fail.

The two gate functions live in engel_main_server_chat_http_service.py, which imports heavy
server deps at module load, so they are extracted by AST with their helpers rather than
imported -- the same technique the other training verifiers use for that module.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "tools" / "engel_main_server_chat_http_service.py"

CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""))


def _extract(names: list[str]) -> dict:
    """Pull the named functions plus every function/const they transitively reference from
    the service module, and exec them in an isolated namespace."""
    text = SERVICE.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(text)
    funcs, consts = {}, {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            funcs[node.name] = ast.get_source_segment(text, node)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    consts[t.id] = ast.get_source_segment(text, node)
    need_f, need_c, queue = set(), set(), list(names)
    while queue:
        n = queue.pop()
        if n in need_f or n not in funcs:
            continue
        need_f.add(n)
        for sub in ast.walk(ast.parse(funcs[n])):
            if isinstance(sub, ast.Name):
                if sub.id in funcs and sub.id not in need_f:
                    queue.append(sub.id)
                elif sub.id in consts:
                    need_c.add(sub.id)
    # Constants can reference OTHER constants (a compiled regex built from a shared
    # connector fragment), so close over their dependencies too or the exec below dies
    # on a NameError for a fragment the functions never mention directly.
    pending = list(need_c)
    while pending:
        c = pending.pop()
        for sub in ast.walk(ast.parse(consts[c])):
            if isinstance(sub, ast.Name) and sub.id in consts and sub.id not in need_c:
                need_c.add(sub.id)
                pending.append(sub.id)
    # Emit constants in source order so a fragment is defined before the regex using it.
    ordered = [c for c in consts if c in need_c]
    ns: dict = {"re": re}
    exec("\n\n".join([consts[c] for c in ordered] + [funcs[f] for f in need_f]), ns)
    return ns


def main() -> int:
    if not SERVICE.is_file():
        check("service_present", False, f"missing {SERVICE}")
        print("\n0/1 checks passed\nFAILED: service_present")
        return 1

    try:
        ns = _extract(
            [
                "_prompt_requests_training_job",
                "_prompt_starts_local_training",
                "_intent_gate_text",
            ]
        )
    except Exception as exc:  # noqa: BLE001
        check("gate_functions_extractable", False, f"{type(exc).__name__}: {exc}")
        print("\n0/1 checks passed\nFAILED: gate_functions_extractable")
        return 1

    check("gate_functions_extractable", True, "both gate functions loaded")
    requests_job = ns["_prompt_requests_training_job"]
    starts_local = ns["_prompt_starts_local_training"]
    gate_text = ns["_intent_gate_text"]

    # --- POSITIVE contract: a real command must still route to its lane ---
    JOB_MUST = [
        "run training now",
        "start training",
        "build a training dataset",
        "create a training package for the local llm",
        "prepare training for the coder model",
        "lora training run please",
    ]
    START_MUST = [
        "run training now",
        "start the training",
        "do the training run",
        "train the llm",
    ]
    job_hits = [p for p in JOB_MUST if requests_job(p)]
    start_hits = [p for p in START_MUST if starts_local(p)]
    check(
        "real_training_job_requests_route",
        len(job_hits) == len(JOB_MUST),
        f"{len(job_hits)}/{len(JOB_MUST)} routed; missed {[p for p in JOB_MUST if p not in job_hits]}",
    )
    check(
        "real_training_launch_requests_route",
        len(start_hits) == len(START_MUST),
        f"{len(start_hits)}/{len(START_MUST)} routed",
    )

    # --- NEGATIVE contract: discussion of training must NOT route (the two real bugs) ---
    JOB_MUST_NOT = [
        # bare co-occurrence of build + training, the exact prompt that misfired
        "build a compact evidence ledger about training and evaluating Engel's local models",
        "explain how training works in Engel",
        "what does the training curriculum cover",
        "summarize the training and evaluation pipeline",
        # the engineering answer contract phrasing that rides every capabilities prompt
        "cite the real component behind Engel's training loop and the verifier that proves it",
        # governance is satisfied ("run training" is adjacent) but it is a QUESTION, and
        # answering it with a training-package receipt is the original bug
        "why do we run training at night",
        "how do I build a training dataset",
    ]
    START_MUST_NOT = [
        # a bare "do" that must never launch a run
        "Do not propose an upgrade without a receipt",
        "how do I read the training report",
        "describe what starting a training run involves",
        "what happens when training completes",
    ]
    job_fp = [p for p in JOB_MUST_NOT if requests_job(p)]
    start_fp = [p for p in START_MUST_NOT if starts_local(p)]
    check(
        "training_discussion_does_not_request_job",
        not job_fp,
        f"FALSE POSITIVES: {job_fp}" if job_fp else "discussion stays chat",
    )
    check(
        "training_discussion_does_not_launch",
        not start_fp,
        f"FALSE POSITIVES (would LAUNCH a run): {start_fp}" if start_fp else "discussion never launches",
    )

    # --- the governing-verb rule is what separates them: same noun, verb decides ---
    check(
        "governing_verb_separates_ask_from_discussion",
        requests_job("build a training dataset") and not requests_job("build an argument about training"),
        "a verb governing 'training' routes; the same verb governing something else does not",
    )

    # --- intent gate reads only the CURRENT user line, not quoted context ---
    wrapped = (
        "Recent Discord context: Engel said run training completed. "
        "Current user message: what does the training report show me"
    )
    check(
        "intent_gate_ignores_quoted_context",
        gate_text(wrapped).strip() == "what does the training report show me"
        and not starts_local(wrapped),
        "a quoted earlier 'run training' must not launch a run on a plain question",
    )

    # Live 2026-08-17: Discord peer frames carry prior canned "it was repeating"
    # replies. The gate must see only the current Sub-Engel body.
    framed = (
        "[Context: you are replying to Sub-Engel, a peer worker node. "
        "Earlier in this exchange: It was repeating because casual chat was "
        "falling back to canned lines.]\n\n"
        "Night crew is on #1 kids tutor."
    )
    check(
        "intent_gate_strips_discord_peer_frame",
        gate_text(framed).strip() == "Night crew is on #1 kids tutor."
        and not starts_local(framed),
        "a Discord [Context:] frame must not poison the current user line",
    )

    failed = [n for n, ok, _ in CHECKS if not ok]
    print(f"\n{len(CHECKS) - len(failed)}/{len(CHECKS)} checks passed")
    if failed:
        print("FAILED: " + ", ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
