"""Minimal typed artifact cards for chat/Meeting Room transcripts (P1 gap)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

SCHEMA = "engel_artifact_card_v1"


def make_artifact_card(
    kind: str,
    title: str,
    body: str,
    *,
    status: str = "info",
    refs: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "kind": str(kind).strip()[:64] or "note",
        "title": str(title).strip()[:160] or "artifact",
        "body": str(body).strip()[:4000],
        "status": str(status).strip()[:32] or "info",
        "refs": [str(item) for item in (refs or [])][:12],
        "created_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "inline": True,
    }


def render_artifact_card(card: dict[str, Any]) -> str:
    lines = [
        f"[artifact:{card.get('kind')}|{card.get('status')}]",
        str(card.get("title") or ""),
        str(card.get("body") or ""),
    ]
    refs = card.get("refs") or []
    if refs:
        lines.append("refs: " + "; ".join(str(item) for item in refs))
    return "\n".join(lines).strip()
