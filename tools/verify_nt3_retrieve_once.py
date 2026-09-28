#!/usr/bin/env python3
"""NT-3 verifier — retrieve-once, carry-forward per-turn recall memo.

Read-only, no model runtime, no provider/network calls (the recall bodies are stubbed with
counters). Emits a receipt. ok=True iff:
  (a) within one turn scope, each memoized recall computes at most ONCE across repeated calls,
  (b) content identity: the memoized value equals the underlying uncached value,
  (c) reentrancy: a nested begin() does not own/reset the outer scope's cache,
  (d) no active scope -> compute live every call (identical to un-memoized behaviour),
  (e) the 3 real recall wrappers (_semantic_memory_context / _recent_chat_context /
      _facts_for_prompt) each hit their *_uncached body at most once per turn.

  python tools/verify_nt3_retrieve_once.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
RECEIPT_DIR = ROOT / "reports" / "engel_nt3_retrieve_once"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def main() -> int:
    failures: list[str] = []
    import_ok = False
    try:
        import engel_main_server_chat_http_service as svc  # noqa: E402
        import_ok = True
    except Exception as exc:
        failures.append(f"import failed: {exc}")

    if import_ok:
        begin, end, memo = svc._begin_turn_recall_cache, svc._end_turn_recall_cache, svc._turn_recall_memo

        # (d) no active scope -> compute live every call
        calls = {"n": 0}
        def compute():
            calls["n"] += 1
            return "VALUE"
        memo(("k",), compute); memo(("k",), compute)
        if calls["n"] != 2:
            failures.append(f"no-scope: expected 2 live computes, got {calls['n']}")

        # (a)+(b) inside a scope: compute once, same value
        tok = begin()
        calls["n"] = 0
        v1 = memo(("k",), compute)
        v2 = memo(("k",), compute)
        if calls["n"] != 1:
            failures.append(f"in-scope: expected 1 compute, got {calls['n']}")
        if not (v1 == v2 == "VALUE"):
            failures.append(f"content-identity: values differ ({v1!r},{v2!r})")

        # (c) reentrancy: nested begin returns None + does not reset outer cache
        inner_tok = begin()
        if inner_tok is not None:
            failures.append("reentrancy: nested begin() should return None (outer owns the cache)")
        end(inner_tok)  # must be a no-op
        calls["n"] = 0
        memo(("k",), compute)  # still cached from before
        if calls["n"] != 0:
            failures.append("reentrancy: inner end() wrongly cleared the outer cache")
        end(tok)
        # after outer end, cache is gone -> computes live again
        calls["n"] = 0
        memo(("k",), compute)
        if calls["n"] != 1:
            failures.append("teardown: after outer end the cache should be cleared")

        # (e) the 3 real wrappers memoize their *_uncached body once per turn
        for name in ("_semantic_memory_context", "_recent_chat_context", "_facts_for_prompt"):
            wrapper = getattr(svc, name, None)
            uncached_name = name + "_uncached"
            orig = getattr(svc, uncached_name, None)
            if wrapper is None or orig is None:
                failures.append(f"{name}: wrapper or {uncached_name} missing")
                continue
            hits = {"n": 0}
            def stub(*a, _h=hits, **k):
                _h["n"] += 1
                return "STUB"
            setattr(svc, uncached_name, stub)
            try:
                tok = begin()
                if name == "_facts_for_prompt":
                    r1, r2 = wrapper(), wrapper()
                else:
                    r1, r2 = wrapper("some prompt here"), wrapper("some prompt here")
                end(tok)
                if hits["n"] != 1:
                    failures.append(f"{name}: expected 1 uncached call per turn, got {hits['n']}")
                if not (r1 == r2 == "STUB"):
                    failures.append(f"{name}: memoized value not carried forward ({r1!r},{r2!r})")
            finally:
                setattr(svc, uncached_name, orig)

    ok = not failures
    receipt = {
        "schema": "engel_nt3_retrieve_once_verifier_v1",
        "task": "NT-3 retrieve-once carry-forward",
        "created_at_utc": _now(),
        "ok": ok,
        "import_ok": import_ok,
        "failures": failures,
        "read_only": True,
        "model_runtime_loaded": False,
        "provider_calls_made": False,
    }
    RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    rp = RECEIPT_DIR / f"ENGEL_NT3_RETRIEVE_ONCE_{_now()}.json"
    rp.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"NT-3 verifier: {'PASS' if ok else 'FAIL'}  ({len(failures)} failures)")
    for f in failures:
        print("  !!", f)
    print(f"  receipt: {rp}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
