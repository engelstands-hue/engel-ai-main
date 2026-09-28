#!/usr/bin/env python3
"""
Engel persona + voice layer (2026-07-10).

The "context discipline" layer for Engel's local chat: a strict STYLE CARD, a
GRADED example bank of good user->reply pairs, few-shot RETRIEVAL of the most
relevant voice examples, and periodic DISTILLATION of chats into stable voice
notes. This is what gives a local model personality without training — the model
gets its voice from clean, retrieved context, and only graded replies are ever
saved (bad logs poison the style).

Composes into the existing chat prompt via `persona_context(prompt)`, which rides
the `extra_memory` rail already wired into build_large_local_system_prompt /
run_chat. Fine-tuning (a small style LoRA) comes LATER, fed by this same graded
bank — see `export_finetune_pairs()`.

Stdlib only, fail-open, cached — safe to deploy to CT246 and call from the worker.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PERSONA_DIR = ROOT / "memory" / "personality"
STYLE_CARD_PATH = PERSONA_DIR / "ENGEL_STYLE_CARD.md"
EXAMPLE_BANK_PATH = PERSONA_DIR / "engel_voice_examples.jsonl"
VOICE_NOTES_PATH = PERSONA_DIR / "ENGEL_VOICE_NOTES.md"

# only replies at/above this grade are kept as voice examples — the whole point is
# to never poison the style with mediocre logs.
GRADE_THRESHOLD = 0.75
MAX_BANK = 600            # keep the most recent N examples
MAX_EXAMPLE_CHARS = 700   # clip a single example so one long reply can't eat the budget

_CACHE: dict[str, tuple[float, object]] = {}
_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then", "of", "to", "in", "on", "for",
    "with", "is", "are", "was", "be", "it", "this", "that", "you", "i", "me", "my",
    "we", "do", "does", "can", "could", "would", "should", "how", "what", "why", "when",
    "where", "which", "please", "engel", "so", "at", "as", "by", "from", "up", "out",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_cached(path: Path, ttl: float = 30.0, clip: int = 4000) -> str:
    key = str(path)
    hit = _CACHE.get(key)
    now = time.time()
    if hit and now - hit[0] < ttl:
        return hit[1]  # type: ignore[return-value]
    text = ""
    try:
        if path.exists():
            text = path.read_text(encoding="utf-8", errors="replace").strip()[:clip]
    except Exception:
        text = ""
    _CACHE[key] = (now, text)
    return text


def style_card() -> str:
    """The strict voice spec, always injected."""
    return _read_cached(STYLE_CARD_PATH, clip=3000)


def voice_notes() -> str:
    """Distilled, stable voice observations (may be empty until first distill)."""
    return _read_cached(VOICE_NOTES_PATH, clip=1500)


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {w for w in words if len(w) > 2 and w not in _STOPWORDS}


def _relevance(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if not inter:
        return 0.0
    return inter / math.sqrt(len(a) * len(b))  # cosine-ish overlap


# ---------------------------------------------------------------- example bank
def _grade_value(grade) -> float:
    """Accept a float, a bool, or a style-score dict; return 0..1."""
    if isinstance(grade, bool):
        return 1.0 if grade else 0.0
    if isinstance(grade, (int, float)):
        return max(0.0, min(1.0, float(grade)))
    if isinstance(grade, dict):
        for k in ("score", "grade", "style_score", "quality"):
            v = grade.get(k)
            if isinstance(v, (int, float)):
                return max(0.0, min(1.0, float(v)))
        for k in ("pass", "passed", "ok"):
            if k in grade:
                return 1.0 if grade.get(k) else 0.0
    return 0.0


# Secret shapes. A captured turn containing any of these is NEVER persisted — voice
# examples feed few-shot context, the fine-tune export, and land on disk, so a leaked key
# would propagate three ways. Better to drop a would-be exemplar than to store a credential.
_SECRET_RE = re.compile(
    r"(?xi)"
    r"\bsk-[a-z0-9]{16,}\b"                                # OpenAI-style keys
    r"|\b(?:ghp|gho|ghu|ghs|ghr)_[a-z0-9]{20,}\b"          # GitHub tokens
    r"|\bAKIA[0-9A-Z]{12,}\b"                              # AWS access key id
    r"|\bxox[baprs]-[a-z0-9-]{10,}\b"                      # Slack tokens
    r"|\bAIza[0-9A-Za-z_\-]{20,}\b"                        # Google API keys
    r"|\bey[a-z0-9_\-]{8,}\.[a-z0-9_\-]{8,}\.[a-z0-9_\-]{6,}\b"  # JWT
    r"|\b[a-f0-9]{40,}\b"                                  # long hex (sha / raw secrets)
    r"|-----BEGIN[A-Z ]*PRIVATE KEY-----"                 # PEM private key
    r"|(?:api[_\s-]?key|secret|password|passwd|bearer|client[_\s-]?secret|access[_\s-]?token|private[_\s-]?key)\s*[:=]\s*\S{6,}"
)
_EMAIL_RE = re.compile(r"\b[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}\b", re.I)
_DIGITS_RE = re.compile(r"(?<!\d)(?:\d[\s.\-]?){10,18}(?!\d)")  # phone / card / account runs


def _looks_secret(text: str) -> bool:
    return bool(text) and bool(_SECRET_RE.search(text))


def _scrub_pii(text: str) -> str:
    """Redact emails and long digit runs (phone / card / account) from stored text."""
    text = _EMAIL_RE.sub("[email]", text)
    text = _DIGITS_RE.sub("[number]", text)
    return text


def add_example(user: str, reply: str, grade=1.0, *, source: str = "chat",
                tags: "list[str] | None" = None, depth: "int | None" = None) -> bool:
    """Save a graded user->reply voice example IF it clears the grade threshold and
    isn't a near-duplicate. Fail-open (never raises); returns True if saved.
    A turn carrying a secret shape is dropped; emails/phone-like runs are redacted."""
    try:
        user = (user or "").strip()
        reply = (reply or "").strip()
        if len(user) < 3 or len(reply) < 8:
            return False
        g = _grade_value(grade)
        if g < GRADE_THRESHOLD:
            return False
        # never persist a turn that carries a credential (leaks 3 ways: context, export, disk)
        if _looks_secret(user) or _looks_secret(reply):
            return False
        user = _scrub_pii(user)
        reply = _scrub_pii(reply)
        # skip degenerate / non-voice replies
        low = reply.lower()
        if any(bad in low for bad in ("as an ai language model", "i am qwen", "alibaba")):
            return False
        uhash = hashlib.sha256(user.lower().encode("utf-8")).hexdigest()[:16]
        existing = _load_bank()
        for e in existing[-120:]:  # cheap recent-dup check
            if e.get("uhash") == uhash:
                return False
        rec = {
            "ts": _now(), "uhash": uhash,
            "user": user[:600], "reply": reply[:MAX_EXAMPLE_CHARS],
            "grade": round(g, 3), "source": source, "tags": list(tags or []),
            # (NT-1) cascade depth that produced this exemplar (bridge vs quick-lane voice differ)
            "activation_depth": depth,
        }
        PERSONA_DIR.mkdir(parents=True, exist_ok=True)
        with EXAMPLE_BANK_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        _CACHE.pop("bank", None)
        _maybe_trim_bank()
        # periodic DISTILLATION: refresh the stable voice notes every 25 clean captures
        # so the notes track the current voice without a separate scheduler.
        try:
            if len(_load_bank()) % 25 == 0:
                distill_notes()
        except Exception:
            pass
        return True
    except Exception:
        return False


def _load_bank() -> "list[dict]":
    hit = _CACHE.get("bank")
    now = time.time()
    if hit and now - hit[0] < 20.0:
        return hit[1]  # type: ignore[return-value]
    out: list[dict] = []
    try:
        if EXAMPLE_BANK_PATH.exists():
            for line in EXAMPLE_BANK_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line.startswith("{"):
                    continue
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        out = []
    _CACHE["bank"] = (now, out)
    return out


def _maybe_trim_bank() -> None:
    """Keep only the most recent MAX_BANK examples (bounded file)."""
    try:
        bank = _load_bank()
        if len(bank) <= MAX_BANK:
            return
        keep = bank[-MAX_BANK:]
        tmp = EXAMPLE_BANK_PATH.with_suffix(".jsonl.tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            for e in keep:
                fh.write(json.dumps(e, ensure_ascii=False) + "\n")
        tmp.replace(EXAMPLE_BANK_PATH)
        _CACHE.pop("bank", None)
    except Exception:
        pass


def retrieve_examples(prompt: str, k: int = 3, min_score: float = 0.12) -> "list[dict]":
    """Top-k voice examples most relevant to the prompt (few-shot). Scored by token
    overlap with a small grade + recency nudge; only examples above min_score."""
    bank = _load_bank()
    if not bank:
        return []
    pt = _tokens(prompt)
    if not pt:
        return []
    n = len(bank)
    scored = []
    for i, e in enumerate(bank):
        rel = _relevance(pt, _tokens(e.get("user", "")))
        if rel < min_score:
            continue
        recency = (i / n) * 0.05          # newer examples nudged up
        grade = (float(e.get("grade", 0.75)) - 0.75) * 0.2
        scored.append((rel + recency + grade, e))
    scored.sort(key=lambda t: t[0], reverse=True)
    return [e for _, e in scored[:k]]


def format_examples(examples: "list[dict]") -> str:
    if not examples:
        return ""
    lines = ["VOICE EXAMPLES — how Engel has answered similar things well "
             "(match this voice; do NOT copy the content):"]
    for e in examples:
        u = " ".join(str(e.get("user", "")).split())[:200]
        r = str(e.get("reply", "")).strip()
        lines.append(f"\nJoshua: {u}\nEngel: {r}")
    return "\n".join(lines)


# ---------------------------------------------------------------- composed block
def persona_context(prompt: str, k: int = 3, budget: int = 1600) -> str:
    """The persona/voice block to fold into the chat prompt: strict style card +
    a few retrieved voice examples + distilled voice notes. Budget-capped, with the
    style card always kept (examples/notes trimmed first)."""
    card = style_card()
    notes = voice_notes()
    examples = format_examples(retrieve_examples(prompt, k=k))
    blocks = []
    if card:
        blocks.append("ENGEL STYLE CARD (follow strictly):\n" + card)
    if examples:
        blocks.append(examples)
    if notes:
        blocks.append("ENGEL VOICE NOTES (learned preferences):\n" + notes)
    text = "\n\n".join(blocks).strip()
    if len(text) > budget:
        # keep the card whole; trim from the end (notes, then examples).
        head = ("ENGEL STYLE CARD (follow strictly):\n" + card) if card else ""
        rest = text[len(head):][: max(0, budget - len(head))]
        text = (head + rest).strip()
    return text


# ------------------------------------------------------------------- distillation
def distill_notes(max_examples: int = 80, llm=None) -> dict:
    """Summarize recent graded examples into stable voice notes (memory\\personality\\
    ENGEL_VOICE_NOTES.md). Deterministic heuristic by default; if `llm(prompt)->str`
    is given, also fold in an LLM one-paragraph summary. Fail-open."""
    try:
        bank = _load_bank()[-max_examples:]
        if not bank:
            return {"ok": False, "reason": "no examples yet"}
        reply_words = [len(str(e.get("reply", "")).split()) for e in bank]
        avg_words = round(sum(reply_words) / len(reply_words)) if reply_words else 0
        joined = "\n".join(str(e.get("reply", "")) for e in bank).lower()
        has_paths = sum(1 for e in bank if re.search(r"[\\/][\w.\-]+\.\w{1,4}\b|workspaces\\", str(e.get("reply", ""))))
        has_code = sum(1 for e in bank if "```" in str(e.get("reply", "")))
        obs = [
            f"- Preferred reply length ~{avg_words} words (keep concise; expand only when asked).",
            f"- {round(100*has_paths/len(bank))}% of good replies cite a real path/command/receipt — prefer evidence over description.",
            f"- {round(100*has_code/len(bank))}% include a code block — use fenced code only when the answer is code.",
            "- Lead with the answer/result; short sentences; no unprompted architecture dumps.",
        ]
        if "sorry" in joined and joined.count("sorry") > len(bank) * 0.15:
            obs.append("- WATCH: over-apologizing showed up — acknowledge once, then move to the fix.")
        llm_para = ""
        if callable(llm):
            try:
                sample = "\n\n".join(f"Q: {e.get('user','')[:120]}\nA: {e.get('reply','')[:300]}" for e in bank[-20:])
                llm_para = (llm(
                    "From these graded Engel replies, write ONE short paragraph (<=4 sentences) of "
                    "STABLE voice guidance for Engel — tone, length, what Joshua likes. No preamble.\n\n" + sample
                ) or "").strip()[:600]
            except Exception:
                llm_para = ""
        body = [
            "# Engel Voice Notes",
            "",
            f"_Distilled {datetime.now(timezone.utc).strftime('%Y-%m-%d')} from {len(bank)} graded examples._",
            "",
        ] + obs
        if llm_para:
            body += ["", "## Summary", llm_para]
        PERSONA_DIR.mkdir(parents=True, exist_ok=True)
        VOICE_NOTES_PATH.write_text("\n".join(body) + "\n", encoding="utf-8")
        _CACHE.pop(str(VOICE_NOTES_PATH), None)
        return {"ok": True, "examples": len(bank), "avg_words": avg_words, "path": str(VOICE_NOTES_PATH)}
    except Exception as exc:
        return {"ok": False, "reason": str(exc)[:160]}


def export_finetune_pairs(out_path: "str | None" = None) -> dict:
    """Export the graded bank as JSONL chat pairs for a LATER style LoRA (voice/format
    only — not private facts). Returns {ok, count, path}."""
    try:
        bank = _load_bank()
        rows = [{"messages": [
            {"role": "user", "content": e.get("user", "")},
            {"role": "assistant", "content": e.get("reply", "")},
        ]} for e in bank if e.get("user") and e.get("reply")]
        dest = Path(out_path) if out_path else (PERSONA_DIR / "engel_voice_finetune.jsonl")
        dest.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
        return {"ok": True, "count": len(rows), "path": str(dest)}
    except Exception as exc:
        return {"ok": False, "reason": str(exc)[:160]}


def _cli(argv=None) -> int:
    import sys
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = __import__("argparse").ArgumentParser(description="Engel persona/voice layer.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("card")
    ctx = sub.add_parser("context"); ctx.add_argument("prompt")
    ad = sub.add_parser("add"); ad.add_argument("--user", required=True); ad.add_argument("--reply", required=True); ad.add_argument("--grade", type=float, default=1.0)
    rt = sub.add_parser("retrieve"); rt.add_argument("prompt"); rt.add_argument("-k", type=int, default=3)
    sub.add_parser("distill")
    sub.add_parser("export")
    sub.add_parser("stats")
    a = ap.parse_args(argv)
    if a.cmd == "card":
        print(style_card())
    elif a.cmd == "context":
        print(persona_context(a.prompt))
    elif a.cmd == "add":
        print("saved" if add_example(a.user, a.reply, a.grade, source="cli") else "rejected")
    elif a.cmd == "retrieve":
        for e in retrieve_examples(a.prompt, k=a.k):
            print(f"- ({e.get('grade')}) {e.get('user','')[:80]}")
    elif a.cmd == "distill":
        print(json.dumps(distill_notes(), indent=2))
    elif a.cmd == "export":
        print(json.dumps(export_finetune_pairs(), indent=2))
    elif a.cmd == "stats":
        bank = _load_bank()
        print(json.dumps({"examples": len(bank), "card_bytes": len(style_card()), "notes_bytes": len(voice_notes())}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
