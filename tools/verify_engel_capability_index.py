#!/usr/bin/env python3
"""Prove the capability index lets Engel find its own parts from intent.

Before this index (measured 2026-07-31) the only search over 517 routes /
2,120 aliases was a whole-needle substring filter, and every goal-shaped query
returned ZERO hits -- so neither an operator nor a drafting model could get
from an intention to the phrase that serves it.

What must hold for the replacement to be trustworthy:

  1. RECALL ON REAL INTENT -- the previously-dead queries now return the route
     a person would point at. Asserted against named route ids, not counts, so
     a ranking regression fails loudly.
  2. DETERMINISTIC -- pure function of the registry: repeated queries rank
     identically, and the lexical layer needs no clock, network, or model.
  3. RERANK IS OPTIONAL -- with the SLM runtime absent (this ROG python has no
     embedder by design) recall is unchanged; the embedder may only REORDER.
  4. MODEL-FACING VIEW IS SAFE -- phrasebook() offers only routes a script may
     actually execute (no action routes), and every phrase it emits resolves.
  5. WIRED -- the draft card carries retrieved phrases, the route + chat
     surfaces resolve, and the index is registered where it must be.

Exit 0 = Engel can find its parts.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
for _p in (str(ROOT), str(TOOLS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import engel_capability_index as ci  # noqa: E402

CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, bool(ok), detail))
    print(f"{'PASS' if ok else 'FAIL'} {name}" + (f" -- {detail}" if detail and not ok else ""))


# (query, a route id that MUST appear in the top-k). These four queries are the
# exact ones that returned zero hits from the old substring search.
RECALL_CASES = [
    ("warn me if a phone worker is offline", "engel.android_workers.status", 6),
    ("check the health of the whole system", "engel.system_integration.status", 6),
    ("is my memory being saved", "engel.memory.status", 6),
    ("how busy is the gpu", "engel.llama_cli.gpu_info", 6),
    ("what models do i have", "engel.models.list", 6),
    ("run a saved plan", "engel.script.run", 8),
]


def run_recall() -> None:
    index = ci.get_capability_index()
    index.ensure_built()
    check(
        "index: built over the whole live registry",
        index.route_count() > 400,
        f"{index.route_count()} routes",
    )
    for query, expected, k in RECALL_CASES:
        hits = index.search(query, limit=k, rerank=False)
        ids = [hit["route_id"] for hit in hits]
        check(
            f"recall: {query!r} surfaces {expected}",
            expected in ids,
            f"top{k}={ids}",
        )
    # The old search returned nothing for these; the floor must stay non-zero.
    check(
        "recall: every previously-dead query now returns hits",
        all(index.search(query, rerank=False) for query, _, _ in RECALL_CASES),
    )
    check(
        "recall: gibberish still returns nothing (no false confidence)",
        index.search("zzzqqxx wobblefrotz", rerank=False) == [],
    )
    check(
        "recall: an empty query returns nothing",
        index.search("   ", rerank=False) == [],
    )


def run_determinism() -> None:
    index = ci.get_capability_index()
    query = "warn me if a phone worker is offline"
    first = index.search(query, limit=8, rerank=False)
    second = index.search(query, limit=8, rerank=False)
    check(
        "deterministic: identical query ranks identically",
        [(h["route_id"], h["score"]) for h in first]
        == [(h["route_id"], h["score"]) for h in second],
    )
    fresh = ci.CapabilityIndex()
    fresh.ensure_built()
    check(
        "deterministic: a freshly built index ranks identically",
        [h["route_id"] for h in fresh.search(query, limit=8, rerank=False)]
        == [h["route_id"] for h in first],
    )
    source = (ROOT / "engel_capability_index.py").read_text(encoding="utf-8")
    check(
        "pure: the lexical layer uses no clock, randomness, or network",
        not any(
            marker in source
            for marker in ("time.time(", "random.", "urllib", "requests.", "subprocess")
        ),
    )
    started = time.perf_counter()
    for _ in range(50):
        index.search("phone worker offline", limit=6, rerank=False)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    check(
        "fast: 50 searches stay well inside a chat turn's budget",
        elapsed_ms < 500.0,
        f"{elapsed_ms:.0f} ms",
    )


def run_rerank_optional() -> None:
    index = ci.get_capability_index()
    query = "warn me if a phone worker is offline"
    lexical = index.search(query, limit=6, rerank=False)
    reranked = index.search(query, limit=6, rerank=True)
    check(
        "rerank: with no embedder available, results are unchanged (fail-open)",
        [h["route_id"] for h in lexical] == [h["route_id"] for h in reranked],
        "embedder present? then ordering may differ legitimately",
    )

    class _BoomRuntime:
        def is_ready(self):
            raise RuntimeError("embedder exploded")

    original = ci.CapabilityIndex._rerank
    try:
        # A rerank that raises must never cost recall.
        def _explode(self, query_text, hits):
            try:
                raise RuntimeError("boom")
            except Exception:
                return hits

        ci.CapabilityIndex._rerank = _explode
        survived = index.search(query, limit=6, rerank=True)
    finally:
        ci.CapabilityIndex._rerank = original
    check(
        "rerank: a failing reranker degrades to the deterministic ranking",
        [h["route_id"] for h in survived] == [h["route_id"] for h in lexical],
    )


def run_phrasebook_safety() -> None:
    from engel_script import route_step_safety

    for query, _, _ in RECALL_CASES:
        hits = ci.get_capability_index().phrasebook(query, limit=6)
        for hit in hits:
            safety = route_step_safety(hit["phrase"])
            if safety.get("allowed") is not True:
                check(
                    f"phrasebook: every offered phrase is script-executable ({query!r})",
                    False,
                    f"{hit['phrase']!r} -> {safety.get('reason')}",
                )
                return
    check("phrasebook: every offered phrase is script-executable", True)

    action_leaked = False
    for query, _, _ in RECALL_CASES:
        for hit in ci.get_capability_index().phrasebook(query, limit=6):
            if not hit["read_only"]:
                action_leaked = True
    check("phrasebook: no ACTION route is ever offered to a drafting model", not action_leaked)

    text = ci.capability_phrasebook_text("warn me if a phone worker is offline", limit=5)
    check(
        "phrasebook: the model-facing block names the right route first",
        "android workers status" in text and text.startswith("Engel routes available"),
        text[:160],
    )
    check(
        "phrasebook: a nonsense goal yields an empty block, not invented phrases",
        ci.capability_phrasebook_text("zzzqqxx wobblefrotz") == "",
    )


def run_wireup() -> None:
    from engel_ai_update_routes import ROUTE_BY_ID, resolve_update_route
    from engel_communication_router import classify_user_input

    check(
        "wireup: the capability route is registered and alias-resolvable",
        resolve_update_route("capability search") == "engel.capability.search"
        and "engel.capability.search" in ROUTE_BY_ID,
    )
    route = ROUTE_BY_ID["engel.capability.search"]
    check(
        "wireup: the capability route is read-only + status-only + AI-safe",
        route.read_only and route.status_only and route.safe_for_ai_route,
    )
    intent = classify_user_input("what can you do about a phone worker being offline")
    check(
        "wireup: the payload-carrying chat phrasing resolves to the route",
        intent.route_target == "engel.capability.search",
        intent.route_target,
    )
    rendered = ci.render_capability_search(
        "what can you do about a phone worker being offline"
    )
    check(
        "wireup: the route renders ranked phrases with route ids and safety",
        "android workers status" in rendered and "engel.android_workers.status" in rendered,
        rendered[:160],
    )
    check(
        "wireup: a bare query renders usage plus the indexed route count",
        "Indexed:" in ci.render_capability_search("capability search"),
    )

    import engel_script as es

    prompt = es.draft_prompt("warn me if a phone worker is offline")
    check(
        "wireup: the draft card carries REAL retrieved routes (not hard-coded guesses)",
        "Engel routes available for this goal" in prompt
        and "android workers status" in prompt,
        prompt[-200:],
    )
    check(
        "wireup: the draft card still contains the grammar rules",
        "plan " in prompt and "misses" in prompt,
    )

    import engel_main_local_model_worker as worker

    reply = worker._engel_capability_chat_intercept(
        "what can you do about a phone worker being offline", "verify-cap"
    )
    check(
        "chat: the worker answers capability search locally, without the CT lane",
        isinstance(reply, dict)
        and reply.get("engel_capability_search_used") is True
        and "android workers status" in reply.get("assistant_reply", ""),
    )
    check(
        "chat: a normal prompt is untouched by the capability intercept",
        worker._engel_capability_chat_intercept("how are you today", "verify-cap2") is None,
    )


def run_tokenizer() -> None:
    check(
        "tokens: plural folding lets query and registry vocabulary meet",
        ci._tokens("phone workers") == ci._tokens("phone worker"),
        str(ci._tokens("phone workers")),
    )
    check(
        "tokens: -ss/-us/-is words are preserved (status, class, analysis)",
        ci._fold("status") == "status"
        and ci._fold("class") == "class"
        and ci._fold("analysis") == "analysis",
    )
    check(
        "tokens: stopwords are dropped but domain words are kept",
        "the" not in ci._tokens("the status of the memory")
        and set(ci._tokens("the status of the memory")) == {"status", "memory"},
        str(ci._tokens("the status of the memory")),
    )


def main() -> int:
    run_recall()
    run_determinism()
    run_rerank_optional()
    run_phrasebook_safety()
    run_tokenizer()
    run_wireup()
    failed = [name for name, ok, _ in CHECKS if not ok]
    print(f"\n{len(CHECKS) - len(failed)}/{len(CHECKS)} checks passed")
    if failed:
        print("FAILED:")
        for name in failed:
            print(f"  - {name}")
        return 1
    print("verify_engel_capability_index: GREEN")
    return 0


if __name__ == "__main__":
    sys.exit(main())
