#!/usr/bin/env python3
"""Engel Self-Upgrade Catalog Router — quick routing to any part of the
governed self-upgrade system.

Serves the Conical Agentic Sentient Self Upgrading System primary goal:
after the system was built, this is how Engel (and the operator) finds the
right part again fast. Reads memory/ENGEL_SELF_UPGRADE_SYSTEM_CATALOG_V1.json.

    route --query "<text>"  -> best-matching parts with exact commands/paths
    list                    -> every part_id + one-line purpose
    show <part_id>          -> the full catalog entry
    verify                  -> every cataloged tool/verifier path resolves

DECISION/LOOKUP ONLY: reads the catalog, returns matches, executes nothing,
mutates nothing, writes no trusted memory.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "memory" / "ENGEL_SELF_UPGRADE_SYSTEM_CATALOG_V1.json"


def load_catalog() -> "dict[str, Any]":
    data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    if data.get("schema") != "ENGEL_SELF_UPGRADE_SYSTEM_CATALOG_V1":
        raise ValueError("catalog schema mismatch")
    return data


def _tokens(text: str) -> "set[str]":
    return {t for t in re.split(r"[^a-z0-9]+", text.lower()) if len(t) > 2}


def score_part(query: str, part: "dict[str, Any]") -> float:
    """Keyword-phrase and token-overlap scoring; exact phrase hits dominate."""
    q = " ".join(query.lower().split())
    q_tokens = _tokens(query)
    score = 0.0
    for phrase in part.get("route_keywords", []):
        p = str(phrase).lower()
        if p and p in q:
            score += 10.0
        else:
            overlap = _tokens(p) & q_tokens
            score += 2.0 * len(overlap)
    if str(part.get("part_id", "")).replace("_", " ") in q:
        score += 8.0
    score += 0.5 * len(_tokens(str(part.get("purpose", ""))) & q_tokens)
    return score


def route(query: str, limit: int = 3) -> "dict[str, Any]":
    catalog = load_catalog()
    scored = sorted(
        ({"score": score_part(query, p), "part": p} for p in catalog.get("parts", [])),
        key=lambda item: item["score"], reverse=True,
    )
    matches = [s for s in scored if s["score"] > 0][:max(1, limit)]
    return {
        "schema": "ENGEL_SELF_UPGRADE_CATALOG_ROUTE_V1",
        "query": query,
        "match_count": len(matches),
        "matches": [
            {
                "part_id": m["part"]["part_id"],
                "score": round(m["score"], 1),
                "purpose": m["part"]["purpose"],
                "tool": m["part"].get("tool"),
                "verifier": m["part"].get("verifier"),
                "commands": m["part"].get("commands", []),
                "receipts": m["part"].get("receipts", []),
            }
            for m in matches
        ],
        "actor_note": "lookup only; executes nothing",
    }


def _existing_path_fragment(entry: str) -> "bool | None":
    """True/False when the entry names a checkable in-repo path; None when it
    is descriptive text (URL, chat command, UI hint, multi-path prose)."""
    text = str(entry).strip()
    first = text.split(" ")[0].split("(")[0]
    if not first or not ("/" in first or "\\" in first):
        return None
    if first.startswith(("http", "GET", "curl", "/opt/")):
        return None
    candidate = first.replace("\\", "/").rstrip("/")
    if "*" in candidate:
        return (ROOT / candidate).parent.is_dir()
    return (ROOT / candidate).exists()


def verify() -> "dict[str, Any]":
    catalog = load_catalog()
    problems: list[dict[str, Any]] = []
    checked = 0
    for part in catalog.get("parts", []):
        for field in ("tool", "verifier"):
            result = _existing_path_fragment(str(part.get(field) or ""))
            if result is None:
                continue
            checked += 1
            if result is False:
                problems.append({"part_id": part["part_id"], "field": field,
                                 "value": part.get(field)})
        for receipt in part.get("receipts", []):
            result = _existing_path_fragment(receipt)
            if result is None:
                continue
            checked += 1
            if result is False:
                problems.append({"part_id": part["part_id"], "field": "receipts",
                                 "value": receipt})
    return {
        "schema": "ENGEL_SELF_UPGRADE_CATALOG_VERIFY_V1",
        "ok": not problems,
        "parts": len(catalog.get("parts", [])),
        "paths_checked": checked,
        "missing": problems,
    }


def _cli(argv: "list[str] | None" = None) -> int:
    import argparse

    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    parser = argparse.ArgumentParser(description="Engel self-upgrade catalog router (lookup only)")
    sub = parser.add_subparsers(dest="command")
    p_route = sub.add_parser("route")
    p_route.add_argument("--query", required=True)
    p_route.add_argument("--limit", type=int, default=3)
    sub.add_parser("list")
    p_show = sub.add_parser("show")
    p_show.add_argument("part_id")
    sub.add_parser("verify")
    args = parser.parse_args(argv)

    if args.command == "route":
        print(json.dumps(route(args.query, args.limit), indent=2, ensure_ascii=False))
        return 0
    if args.command == "show":
        catalog = load_catalog()
        part = next((p for p in catalog["parts"] if p["part_id"] == args.part_id), None)
        print(json.dumps(part or {"error": f"unknown part_id {args.part_id}"},
                         indent=2, ensure_ascii=False))
        return 0 if part else 1
    if args.command == "verify":
        result = verify()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result["ok"] else 1
    catalog = load_catalog()
    for part in catalog["parts"]:
        print(f"{part['part_id']}: {str(part['purpose']).split('.')[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
