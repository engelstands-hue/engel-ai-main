#!/usr/bin/env python3
"""Prove the persister side of memory hygiene (docs/ENGEL_GOVERNOR_DESIGN.md section 4).

Companion to verify_engel_training_turn_context_exclusion.py (which proves the
READ paths). This verifier proves the WRITE path and the persist contract:

  1. A training turn is PERSISTED (the corpus and the trainer's DONE gate need
     the append) but stamped training_turn/context_eligible False, and the
     level-wrapper + answer contract is replaced by the base ask -- the contract
     text never enters the store at all.
  2. The DELIVERED prompt's sha256 is kept through the substitution, so the
     trainer's CT cross-check still hash-matches (substitution cannot break the
     DONE gate).
  3. A wrapper prompt with NO metadata and NO flags is still recognised as a
     training turn (the contract phrasing in the prompt is the metadata-free
     discriminator) -- the signal-death failure mode cannot resurrect the loop.
  4. An echo reply is tagged echo True + context_eligible False at ingest.
  5. A normal operator turn stays context_eligible True with its prompt intact
     (grounding is not starved).
  6. The reader honours the persist contract: context_eligible False / echo True
     records are quarantined; flag-less legacy records still load.

Everything runs against temp stores -- the live JSONLs are never touched.
Exit 0 = hygiene holds.
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
for _p in (ROOT, TOOLS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import engel_governor as gov  # noqa: E402
import engel_main_server_chat_http_service as svc  # noqa: E402
import run_engel_standalone_chat_llm as runner  # noqa: E402

CHECKS: list[tuple[str, bool, str]] = []

# A marker straight from the single-source list: presence in a persisted record
# is exactly the defect this work removes.
CONTRACT_LINE = "Answer ONLY in this filled-in form: 1. Result: <your answer>"
WRAPPER_PROMPT = (
    "Level 3 drill. " + CONTRACT_LINE + " Now: solve x + 3 = 7 and show a Check."
)
BASE_PROMPT = "solve x + 3 = 7 and show a Check"
CLEAN_REPLY = "Result: x = 4. Work: subtract 3. Check: 4 + 3 = 7 by substitution."
# The live-observed echo shape: the 7B restating the contract structure.
ECHO_REPLY = "Engel answers as verified math in exactly this structure: 1. Result: the answer."
NORMAL_PROMPT = "how is the chat lane feeling today?"
NORMAL_REPLY = "The chat lane is healthy and running on the local model."


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, bool(ok), detail))
    print(f"{'PASS' if ok else 'FAIL'} {name}" + (f" -- {detail}" if detail and not ok else ""))


def persist(receipt: dict, prompt: str, store: Path) -> dict:
    """Run the real persister against a temp store and return the appended record."""
    original = runner.PERSISTENT_LLM_CHAT_MEMORY_PATH
    runner.PERSISTENT_LLM_CHAT_MEMORY_PATH = store
    try:
        runner.append_persistent_chat_memory(receipt, prompt)
    finally:
        runner.PERSISTENT_LLM_CHAT_MEMORY_PATH = original
    lines = store.read_text(encoding="utf-8").strip().splitlines()
    return json.loads(lines[-1])


def run_persister_checks(tmp: Path) -> None:
    store = tmp / "persist_store.jsonl"
    delivered_sha = hashlib.sha256(WRAPPER_PROMPT.encode("utf-8")).hexdigest()

    # 1+2: metadata-carrying training turn -- substitution + isolation + DONE gate.
    record = persist(
        {
            "assistant_reply": CLEAN_REPLY,
            "ok": True,
            "status": "large local chat replied",
            "local_only_training": True,
            "prompt_sha256": delivered_sha,
            "governor_context": {
                "persist_policy": "training",
                "training_discipline": "math",
                "base_prompt": BASE_PROMPT,
            },
        },
        WRAPPER_PROMPT,
        store,
    )
    check(
        "persister: training turn IS persisted (append happened, DONE gate keeps its record)",
        record.get("assistant_reply") == CLEAN_REPLY,
    )
    check(
        "persister: training turn stamped training_turn=True, context_eligible=False",
        record.get("training_turn") is True and record.get("context_eligible") is False,
        f"record flags={ {k: record.get(k) for k in ('training_turn', 'context_eligible', 'echo')} }",
    )
    check(
        "persister: base ask persisted, wrapper + contract text NOT in the record",
        record.get("prompt") == BASE_PROMPT
        and record.get("base_prompt_substituted") is True
        and CONTRACT_LINE.casefold() not in json.dumps(record).casefold(),
        f"prompt={record.get('prompt')!r}",
    )
    check(
        "persister: delivered prompt sha kept through substitution (CT cross-check hash-match intact)",
        record.get("prompt_sha256") == delivered_sha,
    )

    # 3: flag-less wrapper prompt -- the metadata-free discriminator.
    record = persist(
        {"assistant_reply": CLEAN_REPLY, "ok": True, "status": "large local chat replied"},
        WRAPPER_PROMPT,
        store,
    )
    check(
        "persister: wrapper prompt with NO flags/metadata is still isolated (signal death cannot resurrect the loop)",
        record.get("training_turn") is True and record.get("context_eligible") is False,
        f"record flags={ {k: record.get(k) for k in ('training_turn', 'context_eligible')} }",
    )

    # 4: echo reply tagged at ingest.
    record = persist(
        {"assistant_reply": ECHO_REPLY, "ok": True, "status": "large local chat replied"},
        NORMAL_PROMPT,
        store,
    )
    check(
        "persister: echo reply tagged echo=True, context_eligible=False at ingest",
        record.get("echo") is True and record.get("context_eligible") is False,
        f"record flags={ {k: record.get(k) for k in ('echo', 'context_eligible')} }",
    )

    # 5: normal operator turn untouched.
    record = persist(
        {"assistant_reply": NORMAL_REPLY, "ok": True, "status": "large local chat replied"},
        NORMAL_PROMPT,
        store,
    )
    check(
        "persister: normal operator turn stays context_eligible=True with prompt intact (grounding not starved)",
        record.get("context_eligible") is True
        and record.get("training_turn") is False
        and record.get("echo") is False
        and record.get("prompt") == NORMAL_PROMPT,
        f"record flags={ {k: record.get(k) for k in ('context_eligible', 'training_turn', 'echo')} }",
    )


def run_reader_checks(tmp: Path) -> None:
    store = tmp / "reader_store.jsonl"

    def row(prompt: str, reply: str, **extra: object) -> dict:
        base: dict = {
            "prompt": prompt,
            "assistant_reply": reply,
            "ok": True,
            "status": "large local chat replied",
            "selected_provider": "local",
        }
        base.update(extra)
        return base

    rows = [
        row("legacy turn with no hygiene fields", "legacy reply"),
        row(NORMAL_PROMPT, NORMAL_REPLY, context_eligible=True),
        row(BASE_PROMPT, CLEAN_REPLY, training_turn=True, context_eligible=False),
        row("quarantined turn", "some reply", context_eligible=False),
        row("echo turn", ECHO_REPLY, echo=True),
    ]
    store.write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8"
    )
    original = svc.PERSISTENT_CHAT_MEMORY_PATH
    svc.PERSISTENT_CHAT_MEMORY_PATH = store
    try:
        records = svc._recent_chat_records_uncached()
    finally:
        svc.PERSISTENT_CHAT_MEMORY_PATH = original
    prompts = [str(r.get("prompt")) for r in records]
    check(
        "reader: context_eligible=False records are quarantined (training + explicit)",
        BASE_PROMPT not in prompts and "quarantined turn" not in prompts,
        f"prompts={prompts}",
    )
    check(
        "reader: echo=True records are quarantined",
        "echo turn" not in prompts,
        f"prompts={prompts}",
    )
    check(
        "reader: flag-less legacy records and normal eligible records still load",
        "legacy turn with no hygiene fields" in prompts and NORMAL_PROMPT in prompts,
        f"prompts={prompts}",
    )


def run_service_writer_checks(tmp: Path) -> None:
    """The 2026-07-31 live proof found sparse-MoE turns are persisted by the
    SERVICE's _append_final_chat_memory, not the runner's persister -- and landed
    unstamped. This proves the service chokepoint stamps them too."""
    store = tmp / "service_store.jsonl"
    original = svc.PERSISTENT_CHAT_MEMORY_PATH
    svc.PERSISTENT_CHAT_MEMORY_PATH = store
    try:
        ok, err = svc._append_final_chat_memory(
            WRAPPER_PROMPT,
            CLEAN_REPLY,
            {
                "ok": True,
                "status": "sparse MoE expert lane replied",
                "selected_provider": "ct_sparse_moe_specialist",
                "local_only_training": True,
                "governor_context": {
                    "persist_policy": "training",
                    "base_prompt": BASE_PROMPT,
                },
            },
            "sparse_moe",
        )
        rec_training = json.loads(
            store.read_text(encoding="utf-8").strip().splitlines()[-1]
        )
        ok2, _ = svc._append_final_chat_memory(
            NORMAL_PROMPT, NORMAL_REPLY, {"ok": True}, "big"
        )
        rec_normal = json.loads(
            store.read_text(encoding="utf-8").strip().splitlines()[-1]
        )
        # The live 2026-07-31 proof: the persister runs BEFORE the finalize path
        # stamps receipt["governor_context"], so substitution must also work from
        # the turn-scoped contextvar alone (receipt carries no governor_context).
        token = svc._TURN_GOVERNOR_CONTEXT.set(
            {"persist_policy": "training", "base_prompt": BASE_PROMPT}
        )
        try:
            ok3, _ = svc._append_final_chat_memory(
                WRAPPER_PROMPT,
                CLEAN_REPLY,
                {"ok": True, "local_only_training": True},
                "sparse_moe",
            )
        finally:
            svc._TURN_GOVERNOR_CONTEXT.reset(token)
        rec_turn_scoped = json.loads(
            store.read_text(encoding="utf-8").strip().splitlines()[-1]
        )
    finally:
        svc.PERSISTENT_CHAT_MEMORY_PATH = original
    check(
        "service writer: append succeeded for both turns",
        ok is True and ok2 is True,
        f"errors: {err}",
    )
    check(
        "service writer: sparse-MoE training turn stamped + base ask substituted (contract never persisted)",
        rec_training.get("training_turn") is True
        and rec_training.get("context_eligible") is False
        and rec_training.get("prompt") == BASE_PROMPT
        and rec_training.get("base_prompt_substituted") is True
        and CONTRACT_LINE.casefold() not in json.dumps(rec_training).casefold(),
        f"record flags={ {k: rec_training.get(k) for k in ('training_turn', 'context_eligible', 'prompt')} }",
    )
    check(
        "service writer: delivered-prompt sha kept through substitution",
        rec_training.get("prompt_sha256")
        == hashlib.sha256(
            svc._clean_text(WRAPPER_PROMPT).encode("utf-8")
        ).hexdigest(),
    )
    check(
        "service writer: normal turn stays context-eligible with prompt intact",
        rec_normal.get("context_eligible") is True
        and rec_normal.get("training_turn") is False
        and rec_normal.get("prompt") == svc._clean_text(NORMAL_PROMPT),
        f"record flags={ {k: rec_normal.get(k) for k in ('training_turn', 'context_eligible')} }",
    )
    check(
        "service writer: substitution works from the turn-scoped context alone (receipt lacks governor_context)",
        ok3 is True
        and rec_turn_scoped.get("base_prompt_substituted") is True
        and rec_turn_scoped.get("prompt") == BASE_PROMPT
        and rec_turn_scoped.get("context_eligible") is False,
        f"record flags={ {k: rec_turn_scoped.get(k) for k in ('base_prompt_substituted', 'prompt', 'context_eligible')} }",
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="engel_memory_hygiene_") as tmpdir:
        tmp = Path(tmpdir)
        run_persister_checks(tmp)
        run_reader_checks(tmp)
        run_service_writer_checks(tmp)
    failed = [name for name, ok, _ in CHECKS if not ok]
    print(f"\n{len(CHECKS) - len(failed)}/{len(CHECKS)} checks passed")
    if failed:
        print("FAILED:")
        for name in failed:
            print(f"  - {name}")
        return 1
    print("verify_engel_memory_hygiene: GREEN")
    return 0


if __name__ == "__main__":
    sys.exit(main())
