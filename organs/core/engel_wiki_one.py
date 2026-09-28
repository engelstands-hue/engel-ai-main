"""Wiki One — Windows body map and CODE-landing journal.

Read-only status for the map. Journal stamps are append-only working records
under wiki/journal. Not trusted memory, not ALIVE_STATE, not digest/history.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from engel_project_paths import resolve_engel_app_root

ROOT = resolve_engel_app_root(__file__)
WIKI = ROOT / "wiki"
ONE_MD = WIKI / "ONE.md"
CONTEXT_MD = WIKI / "CONTEXT.md"
CONTRACT_MD = WIKI / "CONTRACT.md"
ORGANS_JSON = WIKI / "organs.json"
EFFECTS_MD = WIKI / "effects" / "CONTEXT.md"
JOURNAL_DIR = WIKI / "journal"
JOURNAL_JSONL = JOURNAL_DIR / "JOURNAL.jsonl"
JOURNAL_LATEST = JOURNAL_DIR / "LATEST.md"
STAMP_TOOL = ROOT / "tools" / "stamp_wiki_one_journal.py"

ALLOWED_LANES = (
    "grok",
    "claude",
    "codex",
    "cursor",
    "auto",
    "android",
    "sub-engel",
    "chatgpt",
    "local",
)
SECRET_TOKENS = ("token", "secret", "password", "authorization", "api_key", "private_key")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_catalog() -> dict[str, Any]:
    payload = json.loads(ORGANS_JSON.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("organs.json is not an object")
    organs = payload.get("organs")
    if not isinstance(organs, list) or not organs:
        raise ValueError("organs.json missing organs")
    return payload


def save_catalog(catalog: dict[str, Any]) -> None:
    ORGANS_JSON.write_text(
        json.dumps(catalog, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def organ_life(item: dict[str, Any]) -> str:
    life = str(item.get("life") or "").strip().lower()
    if life:
        return life
    universe = str(item.get("universe") or "").strip().lower()
    if universe == "live":
        return "alive"
    if universe in {"leftover", "ghost"}:
        return universe
    return "alive"


def write_one_markdown(catalog: dict[str, Any] | None = None) -> None:
    data = catalog or load_catalog()
    organs = [item for item in data.get("organs", []) if isinstance(item, dict)]
    alive_count = sum(1 for item in organs if organ_life(item) == "alive")
    clusters: dict[str, list[dict[str, Any]]] = {}
    for item in organs:
        clusters.setdefault(str(item.get("cluster") or "other"), []).append(item)
    lines = [
        "# Wiki One — Engel AI Main canonical second brain",
        "",
        "Status: LIVE / ORGANS ALIVE / NOT_TRUSTED_MEMORY",
        "",
        "Engel AI Main is **alive**. Wiki One is its canonical second brain.",
        "Host: `" + str(data.get("host") or "LAPTOP-0KUVK82E") + "`.",
        "Role: " + str(data.get("role") or "Engel AI Main is LIVE."),
        "",
        "Organs: **" + str(len(organs)) + "** — **" + str(alive_count) + " alive**.",
        "",
        "The **whole Engel AI Main** — Cosmic Swarm OS (`EngelAIMain.exe`) included — must **read** this before CODE and **update** it when organs, talks-to, sources, or duties change. Then **stamp Journal**.",
        "",
        "On Cosmic Swarm Home: tab **Wiki**, Ask Engel `wiki one` / `wiki journal` / `update wiki one`, Quick access **Wiki One**.",
        "",
        "Contract: `wiki/CONTRACT.md`. Authority: **"
        + str(data.get("authority") or "Josh > Guardian > Engel/runtime")
        + "**.",
        "",
        "Machine twin: `wiki/organs.json`. Walk: `wiki/CONTEXT.md`. Impact: `wiki/effects/CONTEXT.md`. Stamps: `wiki/journal/`.",
        "",
        "## Land CODE",
        "",
        "1. Read this file.",
        "2. Open the organ you will touch (`wiki/effects/CONTEXT.md` if more than one).",
        "3. If the organ changed, update this file **and** `wiki/organs.json` in the same job.",
        "4. Land the smallest safe change.",
        "5. Stamp Journal:",
        "",
        "```text",
        r"D:\b.WorkSpace\Engel App\runtime\python310\python.exe tools\stamp_wiki_one_journal.py --wiki-read --lane <lane> --worker <name> --organs <id,id> --summary \"one line\" --files \"a.py;b.py\" --receipt \"reports/codex_bridge/<NAME>.md\"",
        "```",
        "",
        "## Organs (ALIVE)",
        "",
        "| id | organ | life | home | does | talks to |",
        "|---|---|---|---|---|---|",
    ]
    for item in organs:
        talks = ", ".join(str(x) for x in (item.get("talks_to") or []))
        lines.append(
            "| {id} | {name} | {life} | {home} | {does} | {talks} |".format(
                id=item.get("id"),
                name=item.get("name"),
                life=organ_life(item),
                home=item.get("home"),
                does=str(item.get("does") or "").replace("|", "/"),
                talks=talks,
            )
        )
    lines.extend(["", "## Hits / does not hit", "", "| organ | If you change this, it hits | It does not hit |", "|---|---|---|"])
    for item in organs:
        lines.append(
            "| {name} | {hits} | {not_hit} |".format(
                name=item.get("name"),
                hits=str(item.get("hits") or "").replace("|", "/"),
                not_hit=str(item.get("does_not_hit") or "").replace("|", "/"),
            )
        )
    lines.extend(["", "## Clusters", ""])
    for cluster, items in clusters.items():
        lines.append("### " + cluster)
        lines.append("")
        for item in items:
            lines.append(
                "- **{name}** (`{id}`) — ALIVE — {does}".format(
                    name=item.get("name"),
                    id=item.get("id"),
                    does=item.get("does"),
                )
            )
        lines.append("")
    peers = data.get("not_this_body") or []
    if peers:
        lines.extend(["## Neighbors (not this nest)", ""])
        for row in peers:
            lines.append("- " + str(row))
        lines.append("")
    lines.extend(
        [
            "## Auto",
            "",
            "Auto lanes load `wiki/organs.json`. Status routes: `wiki one`, `wiki journal`, `update wiki one`.",
            "Organs are **alive**. Wiki One does not write the `ALIVE_STATE` file.",
            "",
        ]
    )
    ONE_MD.write_text("\n".join(lines), encoding="utf-8")


def organ_ids(catalog: dict[str, Any] | None = None) -> list[str]:
    data = catalog or load_catalog()
    return [str(item.get("id") or "") for item in data.get("organs", []) if isinstance(item, dict)]


def organ_by_id(organ_id: str, catalog: dict[str, Any] | None = None) -> dict[str, Any] | None:
    data = catalog or load_catalog()
    for item in data.get("organs", []):
        if isinstance(item, dict) and str(item.get("id") or "") == organ_id:
            return item
    return None


def _scrub(text: str) -> str:
    lowered = text.lower()
    if any(tok in lowered for tok in SECRET_TOKENS):
        return "<redacted>"
    return text.replace("\n", " ").strip()[:400]


def _line(parts: list[str]) -> str:
    return "\n".join(parts)


def render_wiki_one_status(payload: str = "") -> str:
    catalog = load_catalog()
    organs = [item for item in catalog.get("organs", []) if isinstance(item, dict)]
    wanted = str(payload or "").strip().lower()
    lines = [
        "Wiki One — canonical second brain for Engel AI Main",
        "",
        "Host: " + str(catalog.get("host") or "LAPTOP-0KUVK82E"),
        "Role: " + str(catalog.get("role") or ""),
        "Authority: " + str(catalog.get("authority") or "Josh > Guardian > Engel/runtime"),
        "Organs: " + str(len(organs)) + " alive",
        "Life: ALIVE (Engel AI Main is live; Wiki One does not write ALIVE_STATE)",
        "Read before CODE: wiki/ONE.md",
        "Update when organs change: wiki/ONE.md + wiki/organs.json (see wiki/CONTRACT.md)",
        "Stamp after CODE: tools/stamp_wiki_one_journal.py --wiki-read",
        "Journal: wiki/journal/JOURNAL.jsonl (not trusted memory)",
        "",
    ]
    if wanted and wanted not in {"status", "map", "wiki one"}:
        organ = organ_by_id(wanted.replace(" ", "_"), catalog) or next(
            (item for item in organs if wanted in str(item.get("name") or "").lower() or wanted == str(item.get("id") or "")),
            None,
        )
        if organ:
            lines.extend(
                [
                    "Organ: " + str(organ.get("name")),
                    "id: " + str(organ.get("id")),
                    "home: " + str(organ.get("home")),
                    "does: " + str(organ.get("does")),
                    "talks to: " + ", ".join(str(x) for x in organ.get("talks_to") or []),
                    "sources: " + ", ".join(str(x) for x in organ.get("sources") or []),
                    "hits: " + str(organ.get("hits")),
                    "does not hit: " + str(organ.get("does_not_hit")),
                    "",
                    "Safety: READ_ONLY_STATUS_ONLY / NO_TRUSTED_MEMORY_WRITE",
                ]
            )
            return _line(lines)
    for item in organs:
        lines.append(
            "- {id}: {name} ({home}) — {does} | talks to {talks}".format(
                id=item.get("id"),
                name=item.get("name"),
                home=item.get("home"),
                does=item.get("does"),
                talks=", ".join(str(x) for x in item.get("talks_to") or []),
            )
        )
    lines.extend(
        [
            "",
            "Not this body:",
            *[("- " + str(row)) for row in catalog.get("not_this_body") or []],
            "",
            "Safety: READ_ONLY_STATUS_ONLY / NO_TRUSTED_MEMORY_WRITE / NO_ALIVE_STATE",
        ]
    )
    return _line(lines)


def _journal_entries(limit: int = 20) -> list[dict[str, Any]]:
    if not JOURNAL_JSONL.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for raw in JOURNAL_JSONL.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows[-limit:]


def render_wiki_one_update(payload: str = "") -> str:
    del payload
    return _line(
        [
            "Wiki One update duty — canonical second brain for Engel AI Main",
            "",
            "Wiki One is the living body map. Every lane must read it and update it.",
            "Contract: wiki/CONTRACT.md",
            "Map: wiki/ONE.md",
            "Auto twin: wiki/organs.json",
            "",
            "READ before CODE, dispatch, or organ work.",
            "UPDATE wiki/ONE.md and wiki/organs.json in the same job when an organ,",
            "talks-to, source, home, hits, or duty changes.",
            "STAMP Journal after CODE with tools/stamp_wiki_one_journal.py --wiki-read",
            "",
            "Lanes: Grok, Claude, Codex, Cursor, ChatGPT, local LLMs, CT246,",
            "Meeting Room agents, Grok Bots, Android workers, Sub-Engel, auto.",
            "",
            "This chat route is read-only. Workers edit the wiki files themselves.",
            "Not trusted memory. Not ALIVE_STATE.",
        ]
    )


def render_wiki_one_journal(payload: str = "") -> str:
    rows = _journal_entries(20)
    lines = [
        "Wiki One Journal",
        "",
        "Stamps: " + str(len(rows)) + " shown (latest first, cap 20)",
        "Path: wiki/journal/JOURNAL.jsonl",
        "Not trusted memory. Not ALIVE_STATE.",
        "",
    ]
    if not rows:
        lines.append("No stamps yet.")
        return _line(lines)
    for item in reversed(rows):
        lines.append(
            "- {utc} lane={lane} worker={worker} organs={organs} wiki_read={read} summary={summary}".format(
                utc=item.get("utc"),
                lane=item.get("lane"),
                worker=item.get("worker"),
                organs=",".join(str(x) for x in item.get("organs") or []),
                read=item.get("wiki_read"),
                summary=item.get("summary"),
            )
        )
    return _line(lines)


def stamp_journal(
    *,
    lane: str,
    worker: str,
    organs: list[str],
    summary: str,
    files: list[str],
    receipt: str,
    wiki_read: bool,
) -> dict[str, Any]:
    if not wiki_read:
        return {"ok": False, "error": "refused: read wiki/ONE.md and pass --wiki-read before stamping"}
    if not ONE_MD.is_file() or not ORGANS_JSON.is_file():
        return {"ok": False, "error": "Wiki One map missing"}
    lane_key = str(lane or "").strip().lower()
    if lane_key not in ALLOWED_LANES:
        return {"ok": False, "error": "unknown lane"}
    catalog = load_catalog()
    known = set(organ_ids(catalog))
    organ_list = [str(item).strip() for item in organs if str(item).strip()]
    if not organ_list:
        return {"ok": False, "error": "name at least one organ id"}
    unknown = [item for item in organ_list if item not in known]
    if unknown:
        return {"ok": False, "error": "unknown organs: " + ",".join(unknown)}
    receipt_text = str(receipt or "").strip()
    if receipt_text:
        receipt_path = Path(receipt_text)
        if receipt_path.is_absolute() and "codex_bridge" not in str(receipt_path).replace("\\", "/"):
            return {"ok": False, "error": "receipt must stay under reports/codex_bridge"}
        if ".." in Path(receipt_text).parts:
            return {"ok": False, "error": "receipt path rejected"}
    record = {
        "schema": "engel_wiki_one_journal_v1",
        "utc": utc_now(),
        "lane": lane_key,
        "worker": _scrub(str(worker or "unknown")),
        "wiki_read": True,
        "organs": organ_list,
        "summary": _scrub(str(summary or "")),
        "files": [_scrub(str(item)) for item in files if str(item).strip()][:40],
        "receipt": _scrub(receipt_text),
        "organs_alive": True,
        "wrote_trusted_memory": False,
        "wrote_alive_state_file": False,
    }
    JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
    with JOURNAL_JSONL.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    JOURNAL_LATEST.write_text(
        _line(
            [
                "# Wiki One Journal — latest",
                "",
                "- utc: " + str(record["utc"]),
                "- lane: " + str(record["lane"]),
                "- worker: " + str(record["worker"]),
                "- organs: " + ", ".join(organ_list),
                "- summary: " + str(record["summary"]),
                "- files: " + "; ".join(str(item) for item in record["files"]),
                "- receipt: " + str(record["receipt"]),
                "",
                "wiki_read: true",
                "organs_alive: yes",
                "wrote_trusted_memory: no",
                "wrote_ALIVE_STATE_file: no",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return {"ok": True, "path": str(JOURNAL_JSONL), "utc": record["utc"]}


def session_start_text() -> str:
    return _line(
        [
            "Wiki One is the Engel AI Main body map. Read wiki/ONE.md before landing CODE.",
            "Update wiki/ONE.md and wiki/organs.json when organs, talks-to, sources, or duties change.",
            "Then stamp Journal: tools/stamp_wiki_one_journal.py --wiki-read ...",
            "Contract: wiki/CONTRACT.md. This laptop is the face/controller, not CT246 and not Sub-Engel.",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Wiki One status")
    parser.add_argument("mode", nargs="?", default="status", choices=["status", "journal", "update", "session-start", "write-one"])
    parser.add_argument("payload", nargs="?", default="")
    args = parser.parse_args(argv)
    if args.mode == "journal":
        print(render_wiki_one_journal(args.payload))
        return 0
    if args.mode == "update":
        print(render_wiki_one_update(args.payload))
        return 0
    if args.mode == "session-start":
        print(session_start_text())
        return 0
    if args.mode == "write-one":
        write_one_markdown()
        print("wrote " + str(ONE_MD))
        return 0
    print(render_wiki_one_status(args.payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
