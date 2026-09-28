"""Engel's knowledge of THIS computer: what software lives on it, where, and in what state.

Two sources, kept distinct so Engel never confuses a guess with a reading:

  curated  - human/agent-reviewed entries (name, what_it_is, state, evidence). These
             were written by reading the actual project files.
  scanned  - what a filesystem walk can prove by itself: marker files (pyproject,
             package.json, pubspec, build.gradle, Cargo.toml, .git, .sln), language
             mix, file count, newest modification. No interpretation.

A scanned entry NEVER claims to know what a project is - it reports markers. A curated
entry carries its evidence string. `state` on a scanned-only project is
"scanned_uncurated", which is an honest "seen but not understood yet".

The scan is CHECKPOINTED and RESUMABLE: a full sweep of a 655GB drive can take a long
time, so `scan()` writes progress after every root and can be re-run to continue
(operator directive 2026-08-16: "check this computer even if it takes days").

CLI:
  python tools/engel_machine_estate.py --summary
  python tools/engel_machine_estate.py --search "drafting"
  python tools/engel_machine_estate.py --scan            # resumable sweep
  python tools/engel_machine_estate.py --scan --roots "D:\\DNOP,D:\\m.workspace"
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SCHEMA = "engel_machine_estate_inventory_v1"
ROOT = Path(__file__).resolve().parents[1]
ESTATE_PATH = ROOT / "memory" / "ENGEL_MACHINE_ESTATE_INVENTORY_V1.json"

# Directory names that are never projects in their own right.
_SKIP_DIRS = frozenset({
    "node_modules", "__pycache__", ".git", ".hg", ".svn", "venv", ".venv", "env",
    "site-packages", "dist-info", "build", "dist", "out", "target", ".gradle",
    ".idea", ".vscode", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".next",
    ".nuxt", "obj", "bin", "Debug", "Release", ".cargo", ".rustup", ".pnpm-store",
    "npm-cache", "npm-global", "AppData", "Windows", "$Recycle.Bin",
    "System Volume Information", "flutter_local_sdk", "jbr", "plugins",
})

# marker file -> what it proves
_MARKERS = {
    "pyproject.toml": "python-package",
    "requirements.txt": "python",
    "setup.py": "python-package",
    "package.json": "node",
    "pubspec.yaml": "flutter-dart",
    "build.gradle": "gradle-jvm",
    "build.gradle.kts": "gradle-jvm",
    "Cargo.toml": "rust",
    "go.mod": "go",
    "CMakeLists.txt": "cmake",
    "Dockerfile": "container",
    "docker-compose.yml": "container-stack",
    "README.md": "documented",
    "AGENTS.md": "agent-instructions",
    "CLAUDE.md": "agent-instructions",
}
_CODE_SUFFIXES = {
    ".py": "python", ".dart": "dart", ".kt": "kotlin", ".java": "java",
    ".ts": "typescript", ".tsx": "typescript", ".js": "javascript",
    ".jsx": "javascript", ".rs": "rust", ".go": "go", ".cs": "csharp",
    ".cpp": "cpp", ".c": "c", ".swift": "swift", ".ps1": "powershell",
    ".sh": "shell", ".rb": "ruby", ".php": "php", ".sql": "sql",
}


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_estate(path: Path | None = None) -> dict[str, Any]:
    """The inventory as stored; an empty shell when nothing has been recorded yet."""
    target = path or ESTATE_PATH
    if not target.is_file():
        return {"schema": SCHEMA, "projects": [], "scan_state": {}, "updated_at_utc": ""}
    try:
        data = json.loads(target.read_text(encoding="utf-8-sig"))
    except Exception:
        return {"schema": SCHEMA, "projects": [], "scan_state": {}, "updated_at_utc": "",
                "load_error": f"inventory at {target} is unreadable"}
    if not isinstance(data, dict):
        return {"schema": SCHEMA, "projects": [], "scan_state": {}, "updated_at_utc": ""}
    data.setdefault("projects", [])
    data.setdefault("scan_state", {})
    return data


def save_estate(data: dict[str, Any], path: Path | None = None) -> Path:
    target = path or ESTATE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    data["schema"] = SCHEMA
    data["updated_at_utc"] = _iso_now()
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, target)
    return target


def _norm(path: str) -> str:
    return str(path or "").replace("/", "\\").rstrip("\\").casefold()


def _inspect_dir(directory: Path) -> dict[str, Any] | None:
    """Marker/language evidence for one candidate directory. None when not a project."""
    markers: list[str] = []
    languages: dict[str, int] = {}
    file_count = 0
    newest = 0.0
    try:
        entries = list(os.scandir(directory))
    except (OSError, PermissionError):
        return None
    for entry in entries:
        try:
            if entry.is_file(follow_symlinks=False):
                file_count += 1
                name = entry.name
                if name in _MARKERS:
                    markers.append(_MARKERS[name])
                suffix = Path(name).suffix.casefold()
                if suffix in _CODE_SUFFIXES:
                    languages[_CODE_SUFFIXES[suffix]] = languages.get(_CODE_SUFFIXES[suffix], 0) + 1
                stat = entry.stat()
                newest = max(newest, stat.st_mtime)
            elif entry.is_dir(follow_symlinks=False) and entry.name == ".git":
                markers.append("git-repo")
        except (OSError, PermissionError):
            continue
    if not markers and not languages:
        return None
    return {
        "path": str(directory),
        "name": directory.name,
        "markers": sorted(set(markers)),
        "languages": dict(sorted(languages.items(), key=lambda kv: -kv[1])[:5]),
        "code_file_count": sum(languages.values()),
        "file_count": file_count,
        "newest_file_utc": (datetime.fromtimestamp(newest, timezone.utc).isoformat()
                            if newest else ""),
        "state": "scanned_uncurated",
        "source": "filesystem_scan",
        "scanned_at_utc": _iso_now(),
    }


def scan(roots: Iterable[str], *, max_depth: int = 3, budget_seconds: float = 900.0,
         path: Path | None = None) -> dict[str, Any]:
    """Resumable marker sweep. Merges findings into the inventory, preserving curation.

    Stops when the time budget is spent and records where it stopped, so the next run
    picks up the unfinished roots instead of restarting."""
    estate = load_estate(path)
    by_path = {_norm(p.get("path", "")): p for p in estate["projects"]}
    started = time.monotonic()
    scan_state = estate.get("scan_state") or {}
    completed_roots = set(scan_state.get("completed_roots") or [])
    found_new = 0
    updated = 0
    stopped_early = False

    for root in roots:
        if _norm(root) in {_norm(r) for r in completed_roots}:
            continue
        # >= not >: a zero/exhausted budget must stop even when the platform clock
        # reports exactly 0.0 elapsed (Windows monotonic resolution is ~15ms).
        if time.monotonic() - started >= budget_seconds:
            stopped_early = True
            break
        base = Path(root)
        if not base.is_dir():
            continue
        stack: list[tuple[Path, int]] = [(base, 0)]
        while stack:
            if time.monotonic() - started >= budget_seconds:
                stopped_early = True
                break
            directory, depth = stack.pop()
            record = _inspect_dir(directory)
            if record:
                key = _norm(record["path"])
                existing = by_path.get(key)
                if existing is None:
                    by_path[key] = record
                    found_new += 1
                else:
                    # curation wins on meaning; the scan only refreshes hard evidence
                    for field in ("markers", "languages", "code_file_count",
                                  "file_count", "newest_file_utc", "scanned_at_utc"):
                        existing[field] = record[field]
                    existing.setdefault("source", "filesystem_scan")
                    updated += 1
            if depth >= max_depth:
                continue
            try:
                for entry in os.scandir(directory):
                    if not entry.is_dir(follow_symlinks=False):
                        continue
                    if entry.name in _SKIP_DIRS or entry.name.startswith("$"):
                        continue
                    stack.append((Path(entry.path), depth + 1))
            except (OSError, PermissionError):
                continue
        else:
            completed_roots.add(str(base))
        if stopped_early:
            break

    estate["projects"] = list(by_path.values())
    estate["scan_state"] = {
        "completed_roots": sorted(completed_roots),
        "last_scan_utc": _iso_now(),
        "last_scan_stopped_early": stopped_early,
        "last_scan_new": found_new,
        "last_scan_updated": updated,
    }
    save_estate(estate, path)
    return {
        "ok": True,
        "new_projects": found_new,
        "refreshed": updated,
        "total": len(estate["projects"]),
        "stopped_early": stopped_early,
        "completed_roots": sorted(completed_roots),
    }


def search(query: str, *, limit: int = 12, path: Path | None = None) -> list[dict[str, Any]]:
    """Rank inventory entries against a plain-language query. Empty list = say so."""
    terms = [t for t in str(query or "").casefold().split() if len(t) > 2]
    if not terms:
        return []
    scored: list[tuple[int, dict[str, Any]]] = []
    for project in load_estate(path)["projects"]:
        haystack = " ".join(str(project.get(field) or "") for field in
                            ("name", "path", "what_it_is", "notable_capabilities",
                             "state", "evidence")).casefold()
        haystack += " " + " ".join(project.get("markers") or [])
        haystack += " " + " ".join((project.get("languages") or {}).keys())
        score = sum(3 if term in str(project.get("name") or "").casefold() else
                    (1 if term in haystack else 0) for term in terms)
        if score:
            scored.append((score, project))
    scored.sort(key=lambda pair: (-pair[0], str(pair[1].get("name") or "")))
    return [p for _, p in scored[:limit]]


def summary(path: Path | None = None) -> dict[str, Any]:
    estate = load_estate(path)
    projects = estate["projects"]
    by_state: dict[str, int] = {}
    languages: dict[str, int] = {}
    for project in projects:
        by_state[str(project.get("state") or "unknown")] = by_state.get(
            str(project.get("state") or "unknown"), 0) + 1
        for language, count in (project.get("languages") or {}).items():
            languages[language] = languages.get(language, 0) + count
    curated = [p for p in projects if p.get("what_it_is")]
    live = [p for p in curated if str(p.get("state")) in {"active", "complete-working"}]
    return {
        "schema": "engel_machine_estate_summary_v1",
        "inventory_path": str(path or ESTATE_PATH),
        "total_projects": len(projects),
        "curated_projects": len(curated),
        "scanned_only": len(projects) - len(curated),
        "by_state": dict(sorted(by_state.items(), key=lambda kv: -kv[1])),
        "top_languages": dict(sorted(languages.items(), key=lambda kv: -kv[1])[:8]),
        "live_projects": sorted(str(p.get("name")) for p in live)[:40],
        "scan_state": estate.get("scan_state") or {},
        "updated_at_utc": estate.get("updated_at_utc", ""),
    }


def estate_brief(limit: int = 14) -> str:
    """One compact paragraph Engel can speak from about this machine."""
    data = summary()
    if not data["total_projects"]:
        return "No machine estate inventory has been recorded yet."
    live = ", ".join(data["live_projects"][:limit])
    return (
        f"This machine's estate inventory holds {data['total_projects']} projects "
        f"({data['curated_projects']} reviewed in detail). Live/working ones include: {live}. "
        f"Full record: {data['inventory_path']}."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--search", default="")
    parser.add_argument("--brief", action="store_true")
    parser.add_argument("--scan", action="store_true")
    parser.add_argument("--roots", default="D:\\")
    parser.add_argument("--max-depth", type=int, default=3)
    parser.add_argument("--budget-seconds", type=float, default=900.0)
    args = parser.parse_args(argv)

    if args.scan:
        roots = [r.strip() for r in args.roots.split(",") if r.strip()]
        print(json.dumps(scan(roots, max_depth=args.max_depth,
                              budget_seconds=args.budget_seconds), indent=2))
        return 0
    if args.search:
        hits = search(args.search)
        if not hits:
            print(json.dumps({"query": args.search, "matches": 0,
                              "note": "nothing in the inventory matches that"}, indent=2))
            return 0
        print(json.dumps({"query": args.search, "matches": len(hits), "results": [
            {"name": h.get("name"), "path": h.get("path"), "state": h.get("state"),
             "what_it_is": str(h.get("what_it_is") or "")[:220]} for h in hits]},
            indent=2, ensure_ascii=False))
        return 0
    if args.brief:
        print(estate_brief())
        return 0
    print(json.dumps(summary(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
