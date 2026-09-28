"""Engel's capability index -- how Engel finds its own parts from intent.

Engel owns 517 registry routes and 2,120 aliases, and the only search over them
was a whole-needle substring filter (engel_route_explorer.filter_route_catalog).
Measured 2026-07-31, EVERY goal-shaped query returned zero hits:

    "warn me if a phone worker is offline"  -> 0
    "check the health of the whole system"  -> 0
    "is my memory being saved"              -> 0
    "how busy is the gpu"                   -> 0

So neither an operator nor a model could get from an intention to the phrase
that serves it. The EngelScript draft flow made the cost concrete: the grammar
card could only hand the model three hard-coded example phrases, so a drafted
plan was a guess against a 517-route library it could not see.

This module is the retrieval layer that closes that gap:

* **Deterministic first.** Scoring is IDF-weighted token overlap over each
  route's label + aliases + group + id, with an exact-alias bonus and a
  length normalizer so alias-rich routes cannot dominate. Pure function of
  the registry: same query, same ranking, no clock, no network, no model.
* **Optional semantic rerank**, reusing the embedder the SLM runtime already
  serves (engel_slm_runtime) -- no second model, no new dependency. It only
  REORDERS the deterministic candidate set and is skipped entirely when the
  runtime is not ready, so ROG-side and cold-start behaviour stay identical.
* **Safety-aware.** Every hit carries the route's own registry flags, and
  `phrasebook()` (the model-facing view) offers only read-only, AI-safe,
  script-executable routes -- what a drafted plan is allowed to contain.

Consumers: `engel_script.draft_prompt` (real phrases in the drafting card),
the `engel.capability.search` route, and any lane that needs "what can Engel
actually do about X".

Verifier: tools/verify_engel_capability_index.py.
"""
from __future__ import annotations

import math
import re
import threading
from typing import Any

# Words that carry no routing signal. Kept small and explicit: an over-eager
# stoplist silently deletes real intent ("status", "memory", "worker" are all
# meaningful here and must NOT be stopped).
_STOPWORDS = frozenset(
    """a an and are as at be by can could do does for from get give had has have
    how i if in into is it its let me my need needs of on or please should show
    so tell that the their them then there these this to us want was we what
    when where which who why will with would you your""".split()
)

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_MIN_SCORE = 0.08  # below this a "hit" is noise; better to return nothing


def _fold(token: str) -> str:
    """Fold a simple English plural so query and registry vocabulary meet.

    Without this, "worker" never matched the aliases "phone workerS" and
    "phone" never matched the label "connected phoneS" -- the correctly named
    route lost to an unrelated one-alias action route (live 2026-07-31).
    Applied to BOTH sides, so the rule only has to be consistent, not
    linguistically perfect. -ss/-us/-is are preserved (status, class, analysis).
    """
    if len(token) > 3 and token.endswith("s") and not token.endswith(("ss", "us", "is")):
        if token.endswith("es") and len(token) > 4:
            return token[:-2]
        return token[:-1]
    return token


def _tokens(text: Any) -> list[str]:
    return [
        _fold(token)
        for token in _TOKEN_RE.findall(str(text or "").casefold())
        if token not in _STOPWORDS and len(token) > 1
    ]


class CapabilityIndex:
    """Built once from the route registry, then queried. Rebuilt only when the
    registry's route count changes (routes are static at runtime)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._docs: list[dict[str, Any]] = []
        self._idf: dict[str, float] = {}
        self._built_for_route_count = -1

    # ------------------------------------------------------------------ build
    def _build(self) -> None:
        from engel_route_explorer import route_catalog_for_gui

        catalog = route_catalog_for_gui()
        docs: list[dict[str, Any]] = []
        document_frequency: dict[str, int] = {}
        for entry in catalog:
            aliases = [str(alias) for alias in entry.get("aliases", [])]
            # The id contributes its own words ("engel.android_workers.status"
            # -> android workers status), which is often the clearest signal.
            text_parts = [
                str(entry.get("label", "")),
                str(entry.get("group", "")),
                str(entry.get("route_id", "")).replace(".", " ").replace("_", " "),
                *aliases,
            ]
            tokens = _tokens(" ".join(text_parts))
            counts: dict[str, int] = {}
            for token in tokens:
                counts[token] = counts.get(token, 0) + 1
            for token in counts:
                document_frequency[token] = document_frequency.get(token, 0) + 1
            # Field weighting: the label and the primary alias are the route's
            # own best description of itself; a word buried in its tenth alias
            # is weaker evidence.
            headline = set(
                _tokens(str(entry.get("label", "")))
                + _tokens(str(entry.get("primary_alias", "")))
            )
            docs.append(
                {
                    "route_id": str(entry.get("route_id", "")),
                    "label": str(entry.get("label", "")),
                    "group": str(entry.get("group", "")),
                    "primary_alias": str(entry.get("primary_alias", "")),
                    "aliases": aliases,
                    "aliases_cf": [alias.casefold() for alias in aliases],
                    "read_only": bool(entry.get("read_only")),
                    "status_only": bool(entry.get("status_only")),
                    "mode": str(entry.get("mode", "")),
                    "counts": counts,
                    "headline": headline,
                    # Normalize by DISTINCT vocabulary, not total tokens: an
                    # alias-rich route restating the same words must not be
                    # punished for being well described (this is exactly what
                    # buried "android workers status" under a one-alias action
                    # route on 2026-07-31).
                    "norm": math.sqrt(len(counts)) or 1.0,
                }
            )
        total = max(1, len(docs))
        self._idf = {
            token: math.log(1.0 + total / (1.0 + frequency))
            for token, frequency in document_frequency.items()
        }
        self._docs = docs
        self._built_for_route_count = len(catalog)

    def ensure_built(self) -> None:
        with self._lock:
            if self._docs:
                return
            self._build()

    def route_count(self) -> int:
        self.ensure_built()
        return len(self._docs)

    # -------------------------------------------------------------- retrieval
    def _lexical(self, query: str, limit: int) -> list[dict[str, Any]]:
        query_tokens = _tokens(query)
        if not query_tokens:
            return []
        query_counts: dict[str, int] = {}
        for token in query_tokens:
            query_counts[token] = query_counts.get(token, 0) + 1
        low_query = " ".join(str(query or "").casefold().split())
        scored: list[tuple[float, dict[str, Any]]] = []
        query_idf_total = sum(self._idf.get(token, 0.0) for token in query_counts) or 1.0
        for doc in self._docs:
            counts = doc["counts"]
            headline = doc["headline"]
            overlap = 0.0
            matched_idf = 0.0
            for token, query_count in query_counts.items():
                doc_count = counts.get(token)
                if not doc_count:
                    continue
                idf = self._idf.get(token, 0.0)
                # sublinear term frequency: a route repeating a word in ten
                # aliases is not ten times more relevant.
                weight = (1.0 + math.log(doc_count)) * (1.0 + math.log(query_count))
                if token in headline:
                    weight *= 1.6  # matched the route's own headline wording
                overlap += idf * weight
                matched_idf += idf
            if overlap <= 0.0:
                continue
            # Coverage: a route that answers MORE of what was asked wins. Without
            # this, a single strong-but-incidental word ("offline") outranked the
            # route matching two of three query words (live 2026-07-31).
            coverage = matched_idf / query_idf_total
            score = (overlap / doc["norm"]) * (0.45 + 0.55 * coverage)
            # An alias the operator (or model) said almost verbatim is the
            # strongest possible signal -- lexical overlap alone under-ranks it.
            for alias in doc["aliases_cf"]:
                if alias and (alias in low_query or low_query in alias):
                    score += 1.5
                    break
            scored.append((score, doc))
        scored.sort(key=lambda pair: (-pair[0], pair[1]["route_id"]))
        best = scored[0][0] if scored else 0.0
        results = []
        for score, doc in scored[: max(1, limit)]:
            if score < _MIN_SCORE:
                continue
            results.append(
                {
                    "route_id": doc["route_id"],
                    "label": doc["label"],
                    "group": doc["group"],
                    "phrase": doc["primary_alias"],
                    "read_only": doc["read_only"],
                    "status_only": doc["status_only"],
                    "mode": doc["mode"],
                    "score": round(float(score), 4),
                    "relative": round(float(score / best), 4) if best else 0.0,
                    "ranked_by": "lexical",
                }
            )
        return results

    def _rerank(self, query: str, hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Reorder the deterministic candidates with the embedder the SLM
        runtime already serves. Never changes WHICH routes are candidates, so
        a model outage can only cost ordering, never recall."""
        if len(hits) < 2:
            return hits
        try:
            from engel_slm_runtime import get_slm_runtime

            runtime = get_slm_runtime()
            if not runtime.is_ready() or runtime._embedder is None:
                return hits
            texts = [f"{hit['label']} ({hit['phrase']})" for hit in hits]
            vectors = runtime._embed([str(query)] + texts)
            query_vector = vectors[0]
            scored = []
            for hit, vector in zip(hits, vectors[1:]):
                dot = float(sum(a * b for a, b in zip(query_vector, vector)))
                left = math.sqrt(float(sum(a * a for a in query_vector))) or 1.0
                right = math.sqrt(float(sum(b * b for b in vector))) or 1.0
                similarity = dot / (left * right)
                merged = dict(hit)
                merged["similarity"] = round(similarity, 4)
                # Blend, never replace: the deterministic score carries the
                # exact-alias and IDF evidence the embedding cannot see.
                merged["score"] = round(
                    float(hit["score"]) * 0.6 + similarity * 1.4, 4
                )
                merged["ranked_by"] = "lexical+embedding"
                scored.append(merged)
            scored.sort(key=lambda item: (-item["score"], item["route_id"]))
            return scored
        except Exception:  # noqa: BLE001 -- rerank is an optimisation, never a dependency
            return hits

    def search(
        self, query: str, limit: int = 8, *, rerank: bool = True
    ) -> list[dict[str, Any]]:
        self.ensure_built()
        # Retrieve deeper than requested so the optional rerank has room to
        # actually reorder, then cut to the caller's limit.
        hits = self._lexical(query, max(limit * 3, limit))
        if rerank:
            hits = self._rerank(query, hits)
        return hits[: max(1, limit)]

    def phrasebook(self, query: str, limit: int = 6) -> list[dict[str, Any]]:
        """Model-facing view: only routes a script may actually execute."""
        candidates = self.search(query, limit=limit * 3)
        allowed = []
        for hit in candidates:
            try:
                from engel_script import route_step_safety

                if route_step_safety(hit["phrase"]).get("allowed") is not True:
                    continue
            except Exception:  # noqa: BLE001 -- fall back to registry flags
                if not (hit["read_only"] and hit["status_only"]):
                    continue
            allowed.append(hit)
            if len(allowed) >= limit:
                break
        return allowed


_INDEX = CapabilityIndex()


def get_capability_index() -> CapabilityIndex:
    return _INDEX


def search_capabilities(query: str, limit: int = 8) -> list[dict[str, Any]]:
    return _INDEX.search(query, limit=limit)


def capability_phrasebook_text(query: str, limit: int = 6) -> str:
    """The block that goes into a model prompt: real, executable phrases."""
    hits = _INDEX.phrasebook(query, limit=limit)
    if not hits:
        return ""
    lines = ["Engel routes available for this goal (use these phrases exactly):"]
    lines.extend(f'  "{hit["phrase"]}"   # {hit["label"]}' for hit in hits)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Route surface: engel.capability.search
# ---------------------------------------------------------------------------
_QUERY_PREFIXES = (
    "what can you do about",
    "what can engel do about",
    "engel capabilities for",
    "capability search",
    "find engel route for",
    "which route",
)


def _query_from_text(text: str) -> str:
    low = " ".join(str(text or "").strip().split())
    lowered = low.casefold()
    for prefix in _QUERY_PREFIXES:
        if lowered.startswith(prefix):
            return low[len(prefix):].strip(" :?-")
    return low


def render_capability_search(text: str = "") -> str:
    query = _query_from_text(text)
    index = get_capability_index()
    if not query:
        return (
            "Engel capability search -- ask what Engel can do about something.\n"
            f"Indexed: {index.route_count()} routes.\n"
            'Examples: "what can you do about a phone worker being offline", '
            '"engel capabilities for memory", "which route shows gpu load".'
        )
    hits = index.search(query, limit=8)
    if not hits:
        return (
            f"Engel capability search -- no route matched {query!r} "
            f"(searched {index.route_count()} routes). "
            "Try different words, or 'engel route explorer' to browse."
        )
    lines = [f"Engel capabilities for: {query}", ""]
    for hit in hits:
        flag = "read-only" if hit["read_only"] else "ACTION"
        lines.append(f'  "{hit["phrase"]}"')
        lines.append(
            f"      {hit['label']}  [{hit['group']} | {flag} | {hit['route_id']}]"
        )
    lines.append("")
    lines.append(
        f"Ranked by {hits[0]['ranked_by']} over {index.route_count()} routes. "
        "Say a phrase to run it, or put it in an EngelScript plan."
    )
    return "\n".join(lines)
