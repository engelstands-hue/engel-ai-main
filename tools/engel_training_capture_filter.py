#!/usr/bin/env python3
"""Identity-safe training capture filter for Engel chat and Discord data.

This module is intentionally small and dependency-free because it runs both on
the ROG workspace and on CT246. It does not write trusted memory and it does
not promote adapters. It only classifies candidate training pairs.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import argparse
import json
import os
from pathlib import Path
import re
from typing import Any


IDENTITY_LOCK = "ENGEL_DISCORD_CURRENT_SENDER_IDENTITY_V1"
CURRENT_LINE = "current user message:"

SECRET_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"sk-[A-Za-z0-9_\-]{18,}",
        r"ghp_[A-Za-z0-9]{20,}",
        r"AIza[0-9A-Za-z_\-]{30,}",
        r"xox[bap]-[A-Za-z0-9\-]+",
        r"BEGIN [A-Z ]*PRIVATE KEY",
        r"password\s*[:=]\s*\S+",
        r"api[_ -]?key\s*[:=]\s*\S+",
        r"bearer\s+[A-Za-z0-9_\-\.]{24,}",
        r"[A-Fa-f0-9]{64,}",
    )
]

CANNED_MARKERS = (
    "Agent Meeting Room has a live server room",
    "Good morning, Joshua. I am ready",
    "Use the Discord bridge media tool",
    "server chat brain is connected",
    "I am here. I will answer the current message directly",
    "You are right to flag it. The fast fallback",
    "I am here with you; what should we work on next",
)

JOSHUA_ONLY_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\byou are (?:joshua|josh)\b",
        r"\byou'?re (?:joshua|josh)\b",
        r"\bhello[, ]+(?:joshua|josh)\b",
        r"\bgood (?:morning|afternoon|evening)[, ]+(?:joshua|josh)\b",
        r"\b(?:joshua|josh),\s+(?:routing|I|this|that|yes|no|the)\b",
        r"\boperator\b.*\b(?:joshua|josh)\b",
    )
]

CHASE_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\byou are (?:chase|lokal)\b",
        r"\byou'?re (?:chase|lokal)\b",
        r"\bhello[, ]+(?:chase|lokal)\b",
    )
]


@dataclass
class CaptureDecision:
    schema: str
    accept: bool
    bucket: str
    source: str
    reasons: list[str]
    identity_safe: bool
    secret_safe: bool
    quality_score: float
    sender_id: str
    resolved_actor: str
    authority_level: str


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_root() -> Path:
    env_root = os.environ.get("ENGEL_APP_ROOT") or os.environ.get("ENGEL_PROJECT_ROOT")
    if env_root:
        return Path(env_root)
    if Path("/opt/engel").exists():
        return Path("/opt/engel")
    return Path(__file__).resolve().parents[1]


def current_user_line(text: str) -> str:
    low = text.casefold()
    idx = low.rfind(CURRENT_LINE)
    if idx < 0:
        return text
    return text[idx + len(CURRENT_LINE) :].strip() or text


def compact_text(value: Any, limit: int = 4000) -> str:
    text = " ".join(str(value or "").replace("\x00", "").split())
    return text[:limit]


def has_secret(text: str) -> bool:
    return any(pattern.search(text) for pattern in SECRET_PATTERNS)


def has_marker(text: str, markers: tuple[str, ...] = CANNED_MARKERS) -> bool:
    return any(marker in text for marker in markers)


def load_identity_registry(root: Path | None = None) -> dict[str, Any]:
    base = root or default_root()
    path = base / "memory" / "ENGEL_DISCORD_IDENTITY_REGISTRY_V1.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def identity_from_record(record: dict[str, Any] | None, root: Path | None = None) -> dict[str, str]:
    record = record or {}
    nested = record.get("discord_identity")
    if not isinstance(nested, dict):
        nested = {}

    sender_id = str(
        record.get("discord_author_id")
        or nested.get("sender_id")
        or nested.get("author_id")
        or record.get("author_id")
        or ""
    )
    resolved_actor = str(record.get("discord_resolved_actor") or nested.get("resolved_actor") or "")
    authority_level = str(record.get("discord_authority_level") or nested.get("authority_level") or "")

    if sender_id and (not resolved_actor or not authority_level):
        registry = load_identity_registry(root)
        user = registry.get("known_users", {}).get(sender_id)
        if isinstance(user, dict):
            resolved_actor = resolved_actor or str(user.get("resolved_actor") or "")
            authority_level = authority_level or str(user.get("authority_level") or "")

    return {
        "sender_id": sender_id,
        "resolved_actor": resolved_actor or "unknown",
        "authority_level": authority_level or "unknown",
    }


# (2026-08-01) Sources that are owner-authored by construction. A prompt-training run only
# proceeds against the operator's own visible Engel window, on his machine, with every
# provider lane refused -- there is no guest on that lane for Engel to confuse Joshua with.
# Without this, the guest-answered-as-Joshua rule below reads the actor as "unknown" and
# routes ordinary chat prose that addresses Joshua by name ("Joshua, I checked the run ...")
# into negative_eval, which would silently discard most of the chat-communication material
# the training loop exists to collect. The identity is carried by the SOURCE, never by a
# field inside the record, so a hand-edited pack cannot forge owner authority; and the
# answering-as-Chase rule below stays armed for exactly the confusion that IS possible here.
OWNER_LANE_SOURCES = frozenset({"prompt_training"})


def actor_is_joshua(actor: str, authority: str, sender_id: str) -> bool:
    return actor == "joshua" or authority == "owner" or sender_id == "DISCORD_OWNER_USER_ID"


def actor_is_chase(actor: str, sender_id: str) -> bool:
    return actor in {"chase", "chase_lokal", "lokal"} or sender_id == "189914577100603392"


def text_matches_any(text: str, patterns: list[re.Pattern[str]]) -> bool:
    return any(pattern.search(text) for pattern in patterns)


def classify_training_pair(
    *,
    source: str,
    user: Any,
    assistant: Any,
    record: dict[str, Any] | None = None,
    root: Path | None = None,
) -> CaptureDecision:
    source_norm = str(source or "unknown").casefold()
    user_text = compact_text(current_user_line(str(user or "")), limit=2000)
    assistant_text = compact_text(assistant, limit=4000)
    blob = user_text + "\n" + assistant_text
    reasons: list[str] = []
    bucket = "positive"
    quality = 1.0

    identity = identity_from_record(record, root=root)
    sender_id = identity["sender_id"]
    actor = identity["resolved_actor"]
    authority = identity["authority_level"]
    if source_norm in OWNER_LANE_SOURCES and actor == "unknown" and authority == "unknown":
        actor, authority = "joshua", "owner"
    is_discord = source_norm == "discord" or source_norm.startswith("discord")

    if len(user_text) < 3:
        reasons.append("user_text_too_short")
    if len(assistant_text) < 30:
        reasons.append("assistant_text_too_short")
    if has_marker(assistant_text):
        reasons.append("canned_or_repeated_marker")
    if has_secret(blob):
        reasons.append("secret_like_content")

    identity_safe = True
    if is_discord:
        lock = str((record or {}).get("discord_identity_lock") or "")
        if lock != IDENTITY_LOCK:
            reasons.append("missing_discord_identity_lock")
            identity_safe = False
        if not sender_id:
            reasons.append("missing_discord_author_id")
            identity_safe = False
        if actor in {"", "unknown"}:
            reasons.append("missing_discord_resolved_actor")
            identity_safe = False
        if authority in {"", "unknown"}:
            reasons.append("missing_discord_authority_level")
            identity_safe = False

    if not actor_is_joshua(actor, authority, sender_id) and text_matches_any(assistant_text, JOSHUA_ONLY_PATTERNS):
        reasons.append("identity_confusion_guest_answered_as_joshua")
        identity_safe = False
        bucket = "negative_eval"

    if actor_is_joshua(actor, authority, sender_id) and text_matches_any(assistant_text, CHASE_PATTERNS):
        reasons.append("identity_confusion_joshua_answered_as_chase")
        identity_safe = False
        bucket = "negative_eval"

    if is_discord and str((record or {}).get("reply_was_weak_or_repeated")).casefold() == "true":
        reasons.append("discord_reply_marked_weak_or_repeated")

    secret_safe = "secret_like_content" not in reasons
    if reasons and bucket != "negative_eval":
        bucket = "reject"
    if bucket == "reject":
        quality = 0.0
    elif bucket == "negative_eval":
        quality = 0.1
    elif source_norm in {"identity_seed", "verified_repair", "repair_receipt"}:
        quality = 1.0
    elif is_discord:
        quality = 0.75
    else:
        quality = 0.65

    return CaptureDecision(
        schema="ENGEL_TRAINING_CAPTURE_DECISION_V1",
        accept=bucket == "positive",
        bucket=bucket,
        source=source_norm,
        reasons=reasons,
        identity_safe=identity_safe,
        secret_safe=secret_safe,
        quality_score=quality,
        sender_id=sender_id,
        resolved_actor=actor,
        authority_level=authority,
    )


def decision_dict(decision: CaptureDecision) -> dict[str, Any]:
    return asdict(decision)


def iter_jsonl(path: Path):
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except Exception:
            continue


def scan_discord_log(path: Path, root: Path | None = None) -> dict[str, Any]:
    counts: dict[str, int] = {"positive": 0, "negative_eval": 0, "reject": 0}
    samples: list[dict[str, Any]] = []
    for obj in iter_jsonl(path):
        decision = classify_training_pair(
            source="discord",
            user=obj.get("prompt") or "",
            assistant=obj.get("assistant_reply") or "",
            record=obj,
            root=root,
        )
        counts[decision.bucket] = counts.get(decision.bucket, 0) + 1
        if decision.bucket != "positive" and len(samples) < 20:
            samples.append({"decision": decision_dict(decision), "prompt": compact_text(obj.get("prompt"), 300)})
    return {
        "schema": "ENGEL_TRAINING_CAPTURE_FILTER_SCAN_V1",
        "scanned_at_utc": utc_now(),
        "path": str(path),
        "counts": counts,
        "sample_rejections": samples,
    }


def self_test() -> dict[str, Any]:
    chase_record = {
        "discord_identity_lock": IDENTITY_LOCK,
        "discord_author_id": "189914577100603392",
        "discord_resolved_actor": "chase_lokal",
        "discord_authority_level": "guest",
    }
    josh_record = {
        "discord_identity_lock": IDENTITY_LOCK,
        "discord_author_id": "DISCORD_OWNER_USER_ID",
        "discord_resolved_actor": "joshua",
        "discord_authority_level": "owner",
    }
    cases = {
        "chase_good": classify_training_pair(
            source="discord",
            user="who am i",
            assistant="You are Chase/Lokal in this Discord lane, not Joshua.",
            record=chase_record,
        ),
        "chase_bad": classify_training_pair(
            source="discord",
            user="who am i",
            assistant="You are Joshua, the owner of Engel AI Main.",
            record=chase_record,
        ),
        "josh_good": classify_training_pair(
            source="discord",
            user="who am i",
            assistant="You are Joshua, the owner/operator for Engel AI Main.",
            record=josh_record,
        ),
        "missing_metadata": classify_training_pair(
            source="discord",
            user="who am i",
            assistant="You are Joshua, the owner/operator for Engel AI Main.",
            record={},
        ),
    }
    ok = (
        cases["chase_good"].accept
        and cases["chase_bad"].bucket == "negative_eval"
        and cases["josh_good"].accept
        and cases["missing_metadata"].bucket in {"reject", "negative_eval"}
    )
    return {
        "schema": "ENGEL_TRAINING_CAPTURE_FILTER_SELF_TEST_V1",
        "ok": ok,
        "cases": {name: decision_dict(decision) for name, decision in cases.items()},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Engel identity-safe training capture filter.")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--scan-discord-log", default="")
    parser.add_argument("--report", default="")
    parser.add_argument("--root", default="")
    args = parser.parse_args(argv)

    root = Path(args.root) if args.root else default_root()
    if args.self_test:
        result = self_test()
    elif args.scan_discord_log:
        result = scan_discord_log(Path(args.scan_discord_log), root=root)
    else:
        result = self_test()

    if args.report:
        report = Path(args.report)
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("ok", True) is not False else 1


if __name__ == "__main__":
    raise SystemExit(main())
