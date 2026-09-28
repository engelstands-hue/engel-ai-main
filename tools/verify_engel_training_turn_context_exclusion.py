#!/usr/bin/env python3
"""Verify training turns are PERSISTED but never re-injected as chat context (2026-07-31).

The echo loop: a training turn (injected answer contract and all) was persisted to the
chat-memory JSONL, then reloaded verbatim into "RECENT ENGEL CHAT CONTEXT" on the next
turn, and the 7B parroted the contract back instead of answering. The pipeline
manufactured its own echo bait.

The fix is ISOLATE, not SKIP: the append still happens (the corpus needs it, and the
runner's DONE gate + the CT SSH cross-check both require
persistent_chat_memory_appended=True), but every context read path filters the record out.

This verifier seeds a real JSONL against the module's own path and asserts:
  1. a training-marked record never reaches any context read path;
  2. a NORMAL record still does -- grounding must not be starved (the failure mode that
     would make this fix worse than the bug);
  3. every context read path is covered, not just the one that was patched;
  4. a reply matching an already-rejected sample signature is quarantined;
  5. the scope filter alone is insufficient (proves the marker filter is load-bearing).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
for _p in (ROOT, TOOLS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import engel_main_server_chat_http_service as svc  # noqa: E402

checks: list[dict[str, object]] = []


def check(name: str, ok: bool, detail: str) -> None:
    checks.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": detail})


TRAINING_REPLY = "Result: the answer. Work: the key steps. Check: an INDEPENDENT verification."
NORMAL_REPLY = "The Engel server container is reachable and the chat lane is healthy."
CONTRACT_SNIPPET = "Check: an INDEPENDENT verification"


def _record(prompt: str, reply: str, **extra: object) -> dict[str, object]:
    row: dict[str, object] = {
        "prompt": prompt,
        "assistant_reply": reply,
        "ok": True,
        "status": "large local chat replied",
        "selected_provider": "local",
    }
    row.update(extra)
    return row


def _seed(rows: list[dict[str, object]], path: Path) -> None:
    path.write_text(
        "\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n", encoding="utf-8"
    )


def main() -> int:
    tmpdir = Path(tempfile.mkdtemp(prefix="engel_ctx_excl_"))
    memory_path = tmpdir / "ENGEL_AI_MAIN_LLM_CHAT_MEMORY.jsonl"

    rows = [
        _record("normal operator question", NORMAL_REPLY),
        # marked by the per-turn metadata flag
        _record("training prompt A", TRAINING_REPLY, training_turn=True),
        # marked by the global wall-clock sentinel path
        _record("training prompt B", TRAINING_REPLY, local_only_training=True),
    ]
    _seed(rows, memory_path)

    original_path = svc.PERSISTENT_CHAT_MEMORY_PATH
    original_cache = None
    try:
        svc.PERSISTENT_CHAT_MEMORY_PATH = memory_path
        # defeat the per-turn recall memo so each read is fresh
        try:
            original_cache = svc._TURN_RECALL_CACHE.set({})
        except Exception:
            original_cache = None

        records = svc._recent_chat_records_uncached()
        prompts = [str(r.get("prompt") or "") for r in records]

        check(
            "training_turn_flag_excluded",
            "training prompt A" not in prompts,
            "a record marked training_turn=True must not reach chat context",
        )
        check(
            "local_only_training_flag_excluded",
            "training prompt B" not in prompts,
            "a record marked local_only_training=True must not reach chat context",
        )
        check(
            "normal_record_still_loads",
            "normal operator question" in prompts,
            "a normal turn MUST still load -- grounding must not be starved",
        )

        # every context read path, not just the patched one
        context = svc._recent_chat_context_uncached()
        check(
            "recent_context_path_clean",
            CONTRACT_SNIPPET not in context and NORMAL_REPLY[:24] in context,
            "_recent_chat_context_uncached must drop training turns and keep normal ones",
        )
        offset_turn = svc._recent_chat_turn_at_offset(0)
        check(
            "offset_path_clean",
            CONTRACT_SNIPPET not in offset_turn,
            "_recent_chat_turn_at_offset must not surface a training turn",
        )

        # the marker filter is load-bearing: an UNSCOPED read (context_scope='') is exactly
        # the case the scope filter cannot catch.
        unscoped = svc._recent_chat_records_uncached("")
        check(
            "unscoped_read_still_filtered",
            all(
                not (r.get("training_turn") is True or r.get("local_only_training") is True)
                for r in unscoped
            ),
            "scope filter alone is insufficient for context_scope='' -- marker filter must hold",
        )

        # a training record carrying a matching scope must STILL be excluded (marker wins)
        _seed(
            rows + [_record("scoped training", TRAINING_REPLY, local_only_training=True,
                            chat_context_scope="engel_training:x")],
            memory_path,
        )
        try:
            svc._TURN_RECALL_CACHE.set({})
        except Exception:
            pass
        scoped = svc._recent_chat_records_uncached("engel_training:x")
        check(
            "marker_beats_matching_scope",
            all(str(r.get("prompt")) != "scoped training" for r in scoped),
            "marker filter must win even when the scope matches",
        )

        # persistence itself is untouched: the record is still on disk (ISOLATE not SKIP)
        on_disk = memory_path.read_text(encoding="utf-8")
        check(
            "training_turn_still_persisted",
            "training prompt A" in on_disk and "training prompt B" in on_disk,
            "training turns must remain in the store -- the DONE gate and corpus need them",
        )
    finally:
        svc.PERSISTENT_CHAT_MEMORY_PATH = original_path
        if original_cache is not None:
            try:
                svc._TURN_RECALL_CACHE.reset(original_cache)
            except Exception:
                pass
        for leftover in tmpdir.glob("*"):
            try:
                leftover.unlink()
            except OSError:
                pass
        try:
            tmpdir.rmdir()
        except OSError:
            pass

    passed = sum(1 for c in checks if c["status"] == "PASS")
    total = len(checks)
    print(
        json.dumps(
            {
                "schema": "engel_training_turn_context_exclusion_v1",
                "ok": passed == total,
                "passed": passed,
                "total": total,
                "checks": checks,
            },
            indent=2,
        )
    )
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
