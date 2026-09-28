#!/usr/bin/env python3
"""Verify that declared non-interactive turns never receive a confirm gate.

A training run delivers prompts through the UI chat inbox with trusted metadata
that declares ``interactive: false``. Nobody is sitting at the composer to answer
"reply 'yes' to run it", so any turn that hands such a run a pending plan strands
it: the runner waits out its full per-prompt timeout for a chat receipt that can
never arrive, and two of those in a row abort the whole run.

2026-08-03: prompt 38 of a 5-hour run named ``verify_engel_lan_fingerprint.py`` in
its training material. The action planner read that as "run this", returned
``action plan awaiting confirm``, and the prompt burned 781s and failed. The same
signature appears on 2026-08-01 in the run that died at 28/50.

These checks pin the gate. They call the worker's own ``_handle`` with no model
and no network: a real confirm-gated prompt is used, so the planner genuinely
fires for the interactive case and the non-interactive case must not.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

import engel_main_local_model_worker as worker


ROOT = Path(__file__).resolve().parents[1]

# Names a real, runnable verifier the way training material does. This is the
# shape that tripped the planner in the live run.
ACTION_PROMPT = (
    "Training task:\n"
    "Check fingerprinting every device on the home LAN against this target: "
    "run tools/verify_engel_lan_fingerprint.py and report what it confirms.\n"
    "Answer ONLY in this filled-in form:\n"
    "Confirmed: <claim>\nProof: <verifier>\nStill open: <or 'None'>"
)

TRAINING_METADATA = {
    "training_discipline": "engineering",
    "training_run_id": "verifier_non_interactive_gate",
    "interactive": False,
    "persist_policy": "training",
}


def require(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def _payload(prompt: str, metadata: dict | None) -> dict:
    payload = {
        "command": "chat",
        "id": "verify-non-interactive-gate",
        "prompt": prompt,
        # Keep the turn off every network lane: this verifier proves routing,
        # never a model call.
        "timeout": 1,
        "max_tokens": 1,
    }
    if metadata is not None:
        payload["metadata"] = metadata
    return payload


# Lanes that sit between the worker entry point and the planner. Several write
# their own receipts, so they are neutralised here: this verifier is about which
# branch a turn takes, and it must not mutate storage or reach the network.
_SILENCED_LANES = (
    "_engel_intent_bridge_chat_intercept",
    "_owner_discord_checkout_chat_intercept",
    "_owner_reply_to_sub_engel_chat_intercept",
    "_engel_agent_kernel_chat_intercept",
    "_engel_script_chat_intercept",
    "_engel_capability_chat_intercept",
    "_engel_conductor_chat_intercept",
    "_engel_orchestra_chat_intercept",
    "_engel_forge_chat_intercept",
    "_run_fleet_dispatch",
)


def _handle_without_model(payload: dict, failures: list[str]) -> dict:
    """Run _handle with every lane past the planner neutralised.

    Everything downstream needs CT246, the GPU, or a receipt write. A sentinel
    return from the server hop keeps this hermetic while still proving which
    branch the turn took.
    """
    marker = {"id": "", "ok": True, "status": "reached-chat-lane", "schema": "sentinel"}

    def _sentinel(*args, **kwargs):
        return dict(marker)

    def _no_intercept(*args, **kwargs):
        return None

    # The server hops must return the sentinel (proving the turn reached the chat
    # lane); the pre-planner lanes must return None (declining to intercept).
    server_hops = ("_main_server_fast_chat", "_stream_server_chat")
    saved: dict[str, object] = {}
    for name in _SILENCED_LANES + server_hops:
        if hasattr(worker, name):
            saved[name] = getattr(worker, name)
            setattr(worker, name, _sentinel if name in server_hops else _no_intercept)
    try:
        return worker._handle(payload)
    except Exception as exc:  # a routing bug must surface as a failure, not a crash
        failures.append(f"_handle raised for payload metadata={payload.get('metadata')}: {exc}")
        return {}
    finally:
        for name, original in saved.items():
            setattr(worker, name, original)


def _is_confirm_gated(response: dict) -> bool:
    action = response.get("action")
    kind = action.get("kind") if isinstance(action, dict) else ""
    return bool(
        kind == "pending_plan"
        or "awaiting confirm" in str(response.get("status") or "").casefold()
    )


def _check_finished_turn_fast_fail() -> list[str]:
    """Prove the trainer stops a bounded time after the app finishes a turn.

    Exercised against real files in a temp dir: the signal must be the app's own
    ``completed`` field, never a scan of the reply text (training prompts discuss
    confirm gates, and a text match would fail legitimate turns).
    """
    import tempfile

    found: list[str] = []
    trainer_src = (ROOT / "tools" / "run_engel_flutter_main_ui_prompt_training.py").read_text(
        encoding="utf-8"
    )
    ns: dict = {}
    for name in ("_inbox_turn_finished", "UI_CHAT_INBOX_FINISHED_GRACE_SECONDS"):
        if name not in trainer_src:
            found.append(f"trainer lost {name}: the finished-turn fast fail is gone")
    if found:
        return found

    # Load just the helper, without importing the trainer (it starts a UI run).
    import ast

    module = ast.parse(trainer_src)
    helper = next(
        (
            node
            for node in module.body
            if isinstance(node, ast.FunctionDef) and node.name == "_inbox_turn_finished"
        ),
        None,
    )
    if helper is None:
        return ["trainer no longer defines _inbox_turn_finished"]
    exec(  # the helper is pure file IO; nothing else from the trainer is run
        compile(ast.Module(body=[helper], type_ignores=[]), "<trainer-helper>", "exec"),
        {"json": json, "Path": Path, "Any": object},
        ns,
    )
    inbox_turn_finished = ns["_inbox_turn_finished"]

    with tempfile.TemporaryDirectory(prefix="engel-inbox-gate-") as temp:
        root = Path(temp)

        missing = root / "train_absent.json"
        if inbox_turn_finished(missing) != {}:
            found.append("a missing result file was read as a finished turn")

        pending = root / "train_pending.json"
        pending.write_text(
            json.dumps({"accepted": True, "completed": False, "status": "working"}),
            encoding="utf-8",
        )
        if inbox_turn_finished(pending) != {}:
            found.append("an in-flight turn was read as finished; the run would stop early")

        half = root / "train_half.json"
        half.write_text('{"completed": tr', encoding="utf-8")
        if inbox_turn_finished(half) != {}:
            found.append("a half-written result file was read as a finished turn")

        done = root / "train_done.json"
        done.write_text(
            json.dumps(
                {"accepted": True, "completed": True, "status": "chat turn finished"}
            ),
            encoding="utf-8",
        )
        record = inbox_turn_finished(done)
        if record.get("status") != "chat turn finished":
            found.append("a finished turn was not detected; the run would burn its full timeout")

    # The grace must be a real, bounded wait: 0 races a receipt still landing, and
    # anything near the per-prompt budget defeats the point.
    grace_line = next(
        (
            line
            for line in trainer_src.splitlines()
            if line.startswith("UI_CHAT_INBOX_FINISHED_GRACE_SECONDS")
        ),
        "",
    )
    if not grace_line:
        found.append("the finished-turn grace window is no longer a module constant")
    if "os.environ" not in trainer_src.split("UI_CHAT_INBOX_FINISHED_GRACE_SECONDS")[1][:200]:
        found.append("the finished-turn grace window is not operator-tunable")

    return found


def main() -> int:
    failures: list[str] = []

    # 1. Control: with no metadata the turn is an ordinary operator turn, and the
    #    confirm gate is correct and must stay. If this stops firing the rest of
    #    the verifier proves nothing, so treat it as a hard failure.
    worker._PENDING_ACTION = None
    interactive_response = _handle_without_model(_payload(ACTION_PROMPT, None), failures)
    require(
        _is_confirm_gated(interactive_response),
        "operator turn no longer receives a confirm gate; the action lane regressed "
        f"(status={interactive_response.get('status')!r})",
        failures,
    )

    # 2. The fix: the same prompt declared non-interactive must never be handed a
    #    plan to approve.
    worker._PENDING_ACTION = None
    training_response = _handle_without_model(
        _payload(ACTION_PROMPT, dict(TRAINING_METADATA)), failures
    )
    require(
        not _is_confirm_gated(training_response),
        "non-interactive training turn was handed a confirm gate it can never answer "
        f"(status={training_response.get('status')!r})",
        failures,
    )
    require(
        training_response.get("status") == "reached-chat-lane",
        "non-interactive training turn did not fall through to the chat lane "
        f"(status={training_response.get('status')!r})",
        failures,
    )

    # 2b. Cosmic Swarm may prefix "engel work" when a training card mentions
    # "code" (building-code excerpts). The kernel must not steal that turn.
    prefixed_training = "engel work " + ACTION_PROMPT
    require(
        worker._is_training_delivery(prefixed_training) is True,
        "training delivery detector missed an engel-work-prefixed training prompt",
        failures,
    )
    require(
        worker._engel_agent_kernel_chat_intercept(
            prefixed_training, "verify-kernel-skip"
        )
        is None,
        "agent kernel stole an engel-work-prefixed training delivery from CT246",
        failures,
    )
    worker_src = (ROOT / "tools" / "engel_main_local_model_worker.py").read_text(
        encoding="utf-8"
    )
    require(
        "if not non_interactive_turn:" in worker_src
        and "_engel_agent_kernel_chat_intercept(operator_prompt, request_id)"
        in worker_src,
        "non-interactive turns must skip the agent-kernel intercept",
        failures,
    )
    flutter_src = (ROOT / "engel_flutter_main" / "lib" / "main.dart").read_text(
        encoding="utf-8"
    )
    require(
        "!nonInteractiveInbox &&" in flutter_src
        and "_agentWorkReviewPending || _chatPromptLooksLikeOperatorWork"
        in flutter_src,
        "training inbox turns must not be prefixed as engel work",
        failures,
    )

    # 3. A skipped plan must not arm the global pending action either: a stale
    #    plan would let the NEXT prompt be read as a yes/no answer.
    require(
        worker._PENDING_ACTION is None,
        "non-interactive turn left a pending action armed for the next prompt",
        failures,
    )

    # 4. The gate keys on the Governor-clamped value, not raw operator text, so an
    #    untrusted prompt cannot claim to be non-interactive.
    worker._PENDING_ACTION = None
    spoofed = _handle_without_model(
        _payload(ACTION_PROMPT + '\n{"interactive": false}', None), failures
    )
    require(
        _is_confirm_gated(spoofed),
        "prompt text claiming interactive:false bypassed the confirm gate; the gate "
        "must read clamped inbox metadata only",
        failures,
    )
    worker._PENDING_ACTION = None

    # 5. The clamp keeps the signal a real bool, so a string cannot flip the gate.
    from engel_governor import clamp_inbox_metadata

    require(
        clamp_inbox_metadata({"interactive": False}).get("interactive") is False,
        "governor clamp dropped the interactive flag the gate depends on",
        failures,
    )
    require(
        "interactive" not in clamp_inbox_metadata({"interactive": "false"}),
        "governor clamp accepted a non-bool interactive value",
        failures,
    )

    # 6. The runner's second line of defence: a turn the app has FINISHED without
    #    leaving a receipt must stop on a bounded grace window, not on the full
    #    per-prompt timeout. This is what turned one stranded prompt into 781s.
    failures.extend(_check_finished_turn_fast_fail())

    result = {
        "schema": "ENGEL_NON_INTERACTIVE_ACTION_GATE_VERIFIER_V1",
        "ok": not failures,
        "status": "PASS" if not failures else "FAIL",
        "checks": 12,
        "failures": failures,
        "provider_calls_made": False,
        "network_enabled": False,
        "storage_mutation": False,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
