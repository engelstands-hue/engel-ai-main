#!/usr/bin/env python3
"""Read all Markdown handoff files/content under D:\\b.WorkSpace."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(r"D:\b.WorkSpace")
OUT_DIR = ROOT / "Engel App" / "reports" / "codex_bridge"
STAMP = "20260530"
JSON_PATH = OUT_DIR / f"D_WORKSPACE_HANDOFF_READ_INDEX_{STAMP}.json"
MD_PATH = OUT_DIR / f"D_WORKSPACE_HANDOFF_READ_INDEX_{STAMP}.md"

HANDOFF_RE = re.compile(r"hand\s*[- ]?\s*off|handoff", re.IGNORECASE)


def utc_stamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def get_all_markdown_paths() -> list[Path]:
    rg = subprocess.run(
        ["rg", "--files", "--hidden", "--no-ignore", str(ROOT), "-g", "*.md"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if rg.returncode not in (0, 1):
        print(rg.stderr, file=sys.stderr)
        raise SystemExit(rg.returncode)
    return sorted(Path(line.strip()) for line in rg.stdout.splitlines() if line.strip())


def read_record(path: Path) -> dict[str, Any]:
    sha = hashlib.sha256()
    byte_count = 0
    newline_count = 0
    headings: list[str] = []
    matches = []
    match_count = 0
    carry = ""
    logical_line = 0
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            sha.update(chunk)
            byte_count += len(chunk)
            newline_count += chunk.count(b"\n")
            text = chunk.decode("utf-8", errors="replace")
            combined = carry + text
            lines = combined.splitlines(keepends=True)
            if lines and not (lines[-1].endswith("\n") or lines[-1].endswith("\r")):
                carry = lines.pop()
                if len(carry) > 65536:
                    carry = carry[-65536:]
            else:
                carry = ""
            for line in lines:
                logical_line += 1
                clean = line.rstrip("\r\n")
                if len(headings) < 30 and clean.lstrip().startswith("#"):
                    headings.append(clean.strip()[:500])
                found = HANDOFF_RE.findall(clean)
                match_count += len(found)
                if found and len(matches) < 25:
                    matches.append({"line": logical_line, "text": clean.strip()[:260]})
    if carry:
        logical_line += 1
        clean = carry.rstrip("\r\n")
        if len(headings) < 30 and clean.lstrip().startswith("#"):
            headings.append(clean.strip()[:500])
        found = HANDOFF_RE.findall(clean)
        match_count += len(found)
        if found and len(matches) < 25:
            matches.append({"line": logical_line, "text": clean.strip()[:260]})
    line_count = newline_count + (1 if byte_count else 0)
    return {
        "path": rel(path),
        "bytes": byte_count,
        "lines": line_count,
        "sha256": sha.hexdigest(),
        "name_match": bool(HANDOFF_RE.search(path.name)),
        "content_match_count": match_count,
        "headings": headings,
        "matches": matches,
    }


def content_handoff_paths() -> set[Path]:
    rg = subprocess.run(
        [
            "rg",
            "-l",
            "--hidden",
            "--no-ignore",
            "-i",
            r"hand[[:space:]]*[- ]?[[:space:]]*off|handoff",
            str(ROOT),
            "-g",
            "*.md",
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if rg.returncode not in (0, 1):
        print(rg.stderr, file=sys.stderr)
        raise SystemExit(rg.returncode)
    return {Path(line.strip()) for line in rg.stdout.splitlines() if line.strip()}


def main() -> int:
    candidates: set[Path] = set()
    errors: list[dict[str, str]] = []
    for path in get_all_markdown_paths():
        if HANDOFF_RE.search(path.name):
            candidates.add(path)
    candidates.update(content_handoff_paths())

    records = []
    for path in sorted(candidates):
        try:
            records.append(read_record(path))
        except Exception as exc:
            errors.append({"path": rel(path), "error": f"{type(exc).__name__}: {exc}"})

    payload = {
        "ok": not errors,
        "created_at_utc": utc_stamp(),
        "root": str(ROOT),
        "handoff_markdown_files_read": len(records),
        "errors": errors,
        "records": records,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# D Workspace Handoff Read Index",
        "",
        f"Created UTC: `{payload['created_at_utc']}`",
        f"Root scanned: `{ROOT}`",
        f"Handoff Markdown files read: `{len(records)}`",
        f"Read errors: `{len(errors)}`",
        "",
        "## Files",
        "",
    ]
    for record in records[:500]:
        first_heading = record["headings"][0] if record["headings"] else ""
        lines.append(f"- `{record['path']}` ({record['bytes']} bytes) {first_heading}")
    if len(records) > 500:
        lines.append(f"- ... {len(records) - 500} additional handoff Markdown files in JSON index")
    lines.extend([
        "",
        "## Output",
        "",
        f"- JSON index: `{JSON_PATH}`",
    ])
    MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "ok": not errors,
        "handoff_markdown_files_read": len(records),
        "errors": len(errors),
        "json": str(JSON_PATH),
        "markdown": str(MD_PATH),
    }, indent=2))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
