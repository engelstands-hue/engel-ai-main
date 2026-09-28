#!/usr/bin/env python3
"""Read every Markdown file under D:\\b.WorkSpace and write a D-only index."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(r"D:\b.WorkSpace")
OUT_DIR = ROOT / "Engel App" / "reports" / "codex_bridge"
STAMP = "20260530"
JSON_PATH = OUT_DIR / f"D_WORKSPACE_MARKDOWN_READ_INDEX_{STAMP}.json"
RECORDS_PATH = OUT_DIR / f"D_WORKSPACE_MARKDOWN_READ_RECORDS_{STAMP}.jsonl"
MD_PATH = OUT_DIR / f"D_WORKSPACE_MARKDOWN_READ_INDEX_{STAMP}.md"
PATHS_PATH = OUT_DIR / f"D_WORKSPACE_MARKDOWN_PATHS_{STAMP}.txt"

KEYWORDS = [
    "Sub-Engel",
    "Windows Sub-Engel",
    "Agent Meeting",
    "Meeting Room",
    "Codex",
    "Claude",
    "D:\\",
    "C:\\",
    "redacted@example.com",
    "DESKTOP-" + "FIB17O7",
    "192.0.2.44",
    "192.0.2.40",
]


def utc_stamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def bucket(path: Path) -> str:
    parts = path.relative_to(ROOT).parts
    if not parts:
        return "."
    if parts[0] == "Engel App" and len(parts) > 1:
        return "Engel App/" + parts[1]
    return parts[0]


def read_markdown(path: Path) -> dict[str, Any]:
    sha = hashlib.sha256()
    byte_count = 0
    newline_count = 0
    headings: list[str] = []
    keyword_counter: Counter[str] = Counter()
    first_nonempty = ""
    carry = ""
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            sha.update(chunk)
            byte_count += len(chunk)
            newline_count += chunk.count(b"\n")
            text = chunk.decode("utf-8", errors="replace")
            for kw in KEYWORDS:
                count = text.count(kw)
                if count:
                    keyword_counter[kw] += count
            if len(headings) < 25 or not first_nonempty:
                combined = carry + text
                lines = combined.splitlines(keepends=True)
                if lines and not (lines[-1].endswith("\n") or lines[-1].endswith("\r")):
                    carry = lines.pop()
                    if len(carry) > 65536:
                        carry = carry[-65536:]
                else:
                    carry = ""
                for line in lines:
                    clean = line.rstrip("\r\n")
                    if len(headings) < 25 and clean.lstrip().startswith("#"):
                        headings.append(clean.strip()[:500])
                    if not first_nonempty and clean.strip():
                        first_nonempty = clean.strip()[:240]
                    if len(headings) >= 25 and first_nonempty:
                        break
    if carry:
        clean = carry.rstrip("\r\n")
        if len(headings) < 25 and clean.lstrip().startswith("#"):
            headings.append(clean.strip()[:500])
        if not first_nonempty and clean.strip():
            first_nonempty = clean.strip()[:240]
    line_count = newline_count + (1 if byte_count else 0)
    keyword_hits = {kw: int(count) for kw, count in keyword_counter.items() if count}
    return {
        "path": rel(path),
        "bytes": byte_count,
        "lines": line_count,
        "sha256": sha.hexdigest(),
        "bucket": bucket(path),
        "first_nonempty": first_nonempty,
        "headings": headings,
        "keyword_hits": keyword_hits,
    }


def iter_markdown_paths():
    proc = subprocess.Popen(
        ["rg", "--files", "--hidden", "--no-ignore", str(ROOT), "-g", "*.md"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    assert proc.stdout is not None
    for line in proc.stdout:
        value = line.strip()
        if value:
            yield Path(value)
    stderr = proc.stderr.read() if proc.stderr else ""
    code = proc.wait()
    if code not in (0, 1):
        raise RuntimeError(stderr.strip() or f"rg exited with {code}")


def add_keyword_file(keyword_files: dict[str, list[dict[str, Any]]], keyword: str, item: dict[str, Any]) -> None:
    bucket = keyword_files[keyword]
    bucket.append(item)
    if len(bucket) > 500:
        bucket.sort(key=lambda entry: (-int(entry["count"]), str(entry["path"])))
        del bucket[200:]


def main() -> int:
    if not ROOT.exists():
        print(f"missing root: {ROOT}", file=sys.stderr)
        return 1

    errors: list[dict[str, str]] = []
    bucket_counts: Counter[str] = Counter()
    keyword_files: dict[str, list[dict[str, Any]]] = defaultdict(list)
    total_bytes = 0
    record_count = 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with RECORDS_PATH.open("w", encoding="utf-8") as records_fh, PATHS_PATH.open("w", encoding="utf-8") as paths_fh:
        try:
            paths_iter = iter_markdown_paths()
            for path in paths_iter:
                try:
                    record = read_markdown(path)
                except Exception as exc:
                    errors.append({"path": rel(path), "error": f"{type(exc).__name__}: {exc}"})
                    continue
                record_count += 1
                total_bytes += int(record["bytes"])
                bucket_counts[record["bucket"]] += 1
                records_fh.write(json.dumps(record, sort_keys=True) + "\n")
                paths_fh.write(record["path"] + "\n")
                for keyword, count in record["keyword_hits"].items():
                    add_keyword_file(keyword_files, keyword, {
                        "path": record["path"],
                        "count": count,
                        "bytes": record["bytes"],
                        "headings": record["headings"][:5],
                    })
        except Exception as exc:
            errors.append({"path": str(ROOT), "error": f"{type(exc).__name__}: {exc}"})

    for keyword in list(keyword_files):
        keyword_files[keyword].sort(key=lambda item: (-int(item["count"]), str(item["path"])))
        keyword_files[keyword] = keyword_files[keyword][:200]

    payload = {
        "ok": not errors,
        "created_at_utc": utc_stamp(),
        "root": str(ROOT),
        "policy": {
            "memory_write_root": "D:\\b.WorkSpace only",
            "c_drive_memory_file_created_in_error": "deleted",
            "do_not_save_memory_to_c_drive": True,
        },
        "markdown_files_read": record_count,
        "total_bytes_read": total_bytes,
        "errors": errors,
        "bucket_counts": dict(sorted(bucket_counts.items())),
        "keyword_files": keyword_files,
        "records_jsonl": str(RECORDS_PATH),
        "paths_txt": str(PATHS_PATH),
    }

    JSON_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    top_buckets = bucket_counts.most_common(40)
    c_refs = len(keyword_files.get("C:\\", []))
    d_refs = len(keyword_files.get("D:\\", []))
    lines = [
        "# D Workspace Markdown Read Index",
        "",
        f"Created UTC: `{payload['created_at_utc']}`",
        f"Root scanned: `{ROOT}`",
        f"Markdown files read: `{record_count}`",
        f"Total bytes read: `{total_bytes}`",
        f"Read errors: `{len(errors)}`",
        "",
        "## Policy",
        "",
        "- Memory writes must stay under `D:\\b.WorkSpace`.",
        "- The C-drive Codex memory file created earlier was deleted.",
        "- Do not save Engel project memory under `C:\\`.",
        "",
        "## Top Buckets",
        "",
    ]
    lines.extend(f"- `{name}`: {count}" for name, count in top_buckets)
    lines.extend([
        "",
        "## Keyword Coverage",
        "",
    ])
    for keyword in KEYWORDS:
        hits = keyword_files.get(keyword, [])
        lines.append(f"- `{keyword}`: {len(hits)} file(s)")
    lines.extend([
        "",
        "## Drive Reference Counts",
        "",
        f"- Files containing `D:\\`: {d_refs}",
        f"- Files containing `C:\\`: {c_refs}",
        "",
        "## Output Files",
        "",
        f"- JSON index: `{JSON_PATH}`",
        f"- JSONL per-file records: `{RECORDS_PATH}`",
        f"- Path list: `{PATHS_PATH}`",
        "",
        "Full per-file records are in the JSONL records file.",
    ])
    MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "ok": not errors,
        "markdown_files_read": record_count,
        "total_bytes_read": total_bytes,
        "errors": len(errors),
        "json": str(JSON_PATH),
        "records_jsonl": str(RECORDS_PATH),
        "markdown": str(MD_PATH),
        "paths": str(PATHS_PATH),
    }, indent=2))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
