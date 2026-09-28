#!/usr/bin/env python3
"""Conservative dead/stale code audit for Engel AI Main.

This tool is report-only. It does not delete, move, rewrite, import, or execute
project modules. Static findings are candidates unless backed by analyzer output.
"""

from __future__ import annotations

import ast
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports" / "codex_bridge"
TEMP_DIR = ROOT / "runtime" / "temp"

SKIP_DIR_PARTS = {
    ".git",
    ".dart_tool",
    ".pytest_cache",
    "__pycache__",
    "archive",
    "backups",
    "build",
    "dist",
    "node_modules",
    "reports",
    "runtime",
    "target",
    "venv",
    ".venv",
}

CODE_SUFFIXES = {".py", ".rs", ".dart", ".ps1"}
DOC_SUFFIXES = {".md", ".json", ".yaml", ".yml", ".toml", ".txt"}
SOURCE_SUFFIXES = CODE_SUFFIXES | DOC_SUFFIXES

STALE_TOKENS = [
    r"G:\\ENGEL_APP_MEMORY",
    r"E:\\ENGEL_APP_MEMORY",
    r"F:\\ENGEL_APP_MEMORY",
    "/mnt/engel-vault",
    "engel-vault-share",
    "engel-vault-main",
    "PowerVault",
    "DESKTOP-FIB17O7",
]


@dataclass
class Finding:
    severity: str
    category: str
    path: str
    line: int | None
    symbol: str
    evidence: str
    recommendation: str
    confidence: str = "candidate"


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("/", "\\")


def is_skipped(path: Path) -> bool:
    parts = set(path.relative_to(ROOT).parts[:-1])
    return bool(parts & SKIP_DIR_PARTS)


def iter_under(base: Path, suffixes: set[str]) -> Iterable[Path]:
    if not base.exists():
        return
    for path in base.rglob("*"):
        if path.is_file() and not is_skipped(path) and path.suffix.lower() in suffixes:
            yield path


def iter_sources() -> Iterable[Path]:
    """Return maintained Engel source/docs, not vendored/generated trees."""
    seen: set[Path] = set()

    direct_suffixes = SOURCE_SUFFIXES
    for path in ROOT.iterdir():
        if path.is_file() and path.suffix.lower() in direct_suffixes:
            seen.add(path)
            yield path

    focused_roots: list[tuple[Path, set[str]]] = [
        (ROOT / "tools", {".py"}),
        (ROOT / "scripts", {".ps1"}),
        (ROOT / "rust" / "engel-core-rs" / "src", {".rs"}),
        (ROOT / "engel_flutter_main" / "lib", {".dart"}),
        (ROOT / "engel_flutter_main" / "test", {".dart"}),
        (ROOT / "memory", {".md", ".json"}),
        (ROOT / "systemd", {".service", ".timer", ".sh", ".txt"}),
    ]
    for base, suffixes in focused_roots:
        for path in iter_under(base, suffixes):
            if path not in seen:
                seen.add(path)
                yield path


def read_text(path: Path) -> str:
    data = path.read_bytes()
    if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        return data.decode("utf-16", errors="replace").lstrip("\ufeff")
    if b"\x00" in data[:200]:
        return data.decode("utf-16", errors="replace").lstrip("\ufeff")
    return data.decode("utf-8", errors="replace").lstrip("\ufeff")


def line_for_offset(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def load_analyzer_outputs() -> list[Finding]:
    findings: list[Finding] = []
    cargo_path = TEMP_DIR / "dead_code_cargo_check.txt"
    if cargo_path.exists():
        cargo = read_text(cargo_path)
        for match in re.finditer(
            r"warning: (?P<msg>.+?)\n\s+-->\s+(?P<path>.+?):(?P<line>\d+):(?P<col>\d+)",
            cargo,
            flags=re.MULTILINE,
        ):
            msg = match.group("msg").strip()
            path_text = match.group("path").strip()
            severity = "high" if "never used" in msg or "unused" in msg else "medium"
            findings.append(
                Finding(
                    severity=severity,
                    category="confirmed_rust_analyzer_warning",
                    path=path_text.replace("/", "\\"),
                    line=int(match.group("line")),
                    symbol=msg,
                    evidence="cargo check emitted this warning.",
                    recommendation=(
                        "Remove the item or wire it back into the intended route after a targeted test. "
                        "If intentionally retained, rename unused variables with a leading underscore or add a narrow allow with a comment."
                    ),
                    confidence="confirmed",
                )
            )
    flutter_path = TEMP_DIR / "dead_code_flutter_analyze.txt"
    if flutter_path.exists():
        flutter = read_text(flutter_path)
        if "No issues found" not in flutter:
            findings.append(
                Finding(
                    severity="medium",
                    category="flutter_analyzer_non_green",
                    path=rel(flutter_path),
                    line=None,
                    symbol="flutter analyze",
                    evidence=flutter.strip()[:600],
                    recommendation="Review analyzer output before removing any Dart UI code.",
                    confidence="confirmed",
                )
            )
    return findings


def stale_token_findings(source_paths: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    for path in source_paths:
        if path.suffix.lower() not in {".py", ".rs", ".dart", ".ps1", ".md", ".json"}:
            continue
        text = read_text(path)
        lower = text.lower()
        for token in STALE_TOKENS:
            if token.lower() not in lower:
                continue
            for match in re.finditer(re.escape(token), text, flags=re.IGNORECASE):
                line = line_for_offset(text, match.start())
                line_text = text.splitlines()[line - 1].strip()
                guard_words = ("refus", "forbidden", "offline", "do not use", "blocked", "historical")
                looks_guarded = any(word in line_text.lower() for word in guard_words)
                if looks_guarded and path.suffix.lower() in {".md", ".json"}:
                    severity = "info"
                    recommendation = "Historical/guard reference. Keep unless this document is active UI/runtime guidance and now misleads users."
                elif looks_guarded:
                    severity = "low"
                    recommendation = "Guard reference. Keep only if it blocks old storage/device use; otherwise replace with CT246 SSD/HDD policy."
                else:
                    severity = "high" if path.suffix.lower() in CODE_SUFFIXES else "medium"
                    recommendation = "Replace or retire this stale storage/device reference; current target is CT246 /opt/engel plus Dell engel-hdd-vault."
                findings.append(
                    Finding(
                        severity=severity,
                        category="stale_storage_or_device_reference",
                        path=rel(path),
                        line=line,
                        symbol=token,
                        evidence=line_text[:260],
                        recommendation=recommendation,
                    )
                )
    return findings


def python_reference_candidates(source_paths: list[Path]) -> list[Finding]:
    py_paths = [
        path
        for path in source_paths
        if path.suffix.lower() == ".py"
        and (path.parent == ROOT or path.parent == ROOT / "tools")
        and not path.name.startswith("verify_")
    ]
    corpus_by_path = {path: read_text(path) for path in source_paths if path.suffix.lower() in SOURCE_SUFFIXES}
    full_corpus = "\n".join(corpus_by_path.values())
    token_counts = Counter(re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", full_corpus))

    findings: list[Finding] = []
    for path in py_paths:
        stem = path.stem
        filename = path.name
        own = corpus_by_path[path]
        ref_count = (full_corpus.count(stem) - own.count(stem)) + (
            full_corpus.count(filename) - own.count(filename)
        )
        if ref_count == 0 and not stem.startswith("_"):
            findings.append(
                Finding(
                    severity="medium",
                    category="python_entrypoint_orphan_candidate",
                    path=rel(path),
                    line=1,
                    symbol=stem,
                    evidence="No static text reference to this Python module name was found outside the file in active source/docs.",
                    recommendation=(
                        "Confirm whether this is a manual tool, retired experiment, or dynamic route. "
                        "If manual, register it in commands/docs; if retired, quarantine after backup and route check."
                    ),
                )
            )

    # Public top-level definitions with no obvious references. This intentionally
    # skips render_* and verify_* because Engel routes commonly use those symbols.
    for path in py_paths:
        try:
            tree = ast.parse(corpus_by_path[path])
        except SyntaxError as exc:
            findings.append(
                Finding(
                    severity="high",
                    category="python_parse_error_blocks_static_audit",
                    path=rel(path),
                    line=exc.lineno,
                    symbol=path.name,
                    evidence=str(exc),
                    recommendation="Fix parse error before trusting dead-code results for this file.",
                    confidence="confirmed",
                )
            )
            continue
        own_token_counts = Counter(re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", corpus_by_path[path]))
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            name = node.name
            if (
                name.startswith("_")
                or name in {"main", "load", "save", "status", "run", "build"}
                or name.startswith(("render_", "verify_", "check_", "test_"))
            ):
                continue
            if token_counts.get(name, 0) - own_token_counts.get(name, 0) <= 0:
                findings.append(
                    Finding(
                        severity="low",
                        category="python_top_level_symbol_unreferenced_candidate",
                        path=rel(path),
                        line=node.lineno,
                        symbol=name,
                        evidence="Top-level public symbol has no static references outside its own definition.",
                        recommendation="Review before removal; dynamic dispatch and CLI argv may still call it.",
                    )
                )
    return findings


def dart_suppression_findings(source_paths: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    for path in source_paths:
        if path.suffix.lower() != ".dart":
            continue
        text = read_text(path)
        for match in re.finditer(r"//\s*ignore:\s*unused_element", text):
            line = line_for_offset(text, match.start())
            findings.append(
                Finding(
                    severity="low",
                    category="dart_unused_element_suppression",
                    path=rel(path),
                    line=line,
                    symbol="unused_element suppression",
                    evidence=text.splitlines()[line - 1].strip(),
                    recommendation="Review these UI helpers after feature routing is stable; Flutter analyzer is otherwise clean.",
                )
            )
    return findings


def duplicate_family_findings(source_paths: list[Path]) -> list[Finding]:
    py_root = [path for path in source_paths if path.parent == ROOT and path.suffix.lower() == ".py"]
    normalized: dict[str, list[Path]] = defaultdict(list)
    for path in py_root:
        key = re.sub(r"(_verified|_d_only|_exit_fix|_output_filter_tuning|_part\d+|_fixed|_new)$", "", path.stem)
        key = key.replace("_meetingroom", "_meeting_room")
        normalized[key].append(path)
    findings: list[Finding] = []
    for key, paths in sorted(normalized.items()):
        if len(paths) < 2:
            continue
        names = ", ".join(rel(path) for path in paths)
        findings.append(
            Finding(
                severity="medium",
                category="python_duplicate_family_candidate",
                path=rel(paths[0]),
                line=1,
                symbol=key,
                evidence=f"Related root Python files: {names}",
                recommendation="Confirm the active entrypoint and quarantine retired variants after route and receipt verification.",
            )
        )
    return findings


def summarize_files(source_paths: list[Path]) -> dict[str, int]:
    counts = Counter(path.suffix.lower() or "<no_ext>" for path in source_paths)
    return dict(sorted(counts.items()))


def rank_key(finding: Finding) -> tuple[int, str, str]:
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    return (order.get(finding.severity, 9), finding.category, finding.path)


def write_reports(payload: dict) -> tuple[Path, Path]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = payload["generated_utc"].replace("-", "").replace(":", "").replace("+00:00", "Z")
    json_path = REPORT_DIR / f"ENGEL_DEAD_CODE_AUDIT_{stamp}.json"
    md_path = REPORT_DIR / f"ENGEL_DEAD_CODE_AUDIT_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# Engel Dead/Stale Code Audit",
        "",
        f"Generated: `{payload['generated_utc']}`",
        "",
        "Mode: report-only. No files were deleted, moved, or rewritten.",
        "",
        "## Summary",
        "",
        f"- Source files scanned: `{payload['source_file_count']}`",
        f"- Findings: `{payload['finding_count']}`",
        f"- Confirmed analyzer findings: `{payload['confirmed_count']}`",
        f"- Candidate static findings: `{payload['candidate_count']}`",
        f"- Flutter analyzer: `{payload['analyzers']['flutter']}`",
        f"- Python linter availability: `{payload['analyzers']['python_linter']}`",
        "",
        "## Counts By Severity",
        "",
    ]
    for severity, count in payload["severity_counts"].items():
        lines.append(f"- `{severity}`: `{count}`")
    lines.extend(["", "## Findings", ""])
    for item in payload["findings"][: payload["findings_markdown_limit"]]:
        loc = item["path"] + (f":{item['line']}" if item.get("line") else "")
        lines.extend(
            [
                f"### {item['severity'].upper()} - {item['category']}",
                "",
                f"- Location: `{loc}`",
                f"- Symbol: `{item['symbol']}`",
                f"- Confidence: `{item['confidence']}`",
                f"- Evidence: {item['evidence']}",
                f"- Recommendation: {item['recommendation']}",
                "",
            ]
        )
    if payload["finding_count"] > payload["findings_markdown_limit"]:
        lines.extend(
            [
                "## Truncated Markdown",
                "",
                f"The Markdown report shows the top {payload['findings_markdown_limit']} ranked findings.",
                "The JSON report contains the full finding list.",
                "",
            ]
        )
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    source_paths = sorted(iter_sources())
    findings: list[Finding] = []
    findings.extend(load_analyzer_outputs())
    findings.extend(stale_token_findings(source_paths))
    findings.extend(python_reference_candidates(source_paths))
    findings.extend(dart_suppression_findings(source_paths))
    findings.extend(duplicate_family_findings(source_paths))

    # Keep Markdown readable while the JSON keeps the full ranked set.
    findings = sorted(findings, key=rank_key)
    severity_counts = Counter(f.severity for f in findings)
    confidence_counts = Counter(f.confidence for f in findings)

    flutter_output = read_text(TEMP_DIR / "dead_code_flutter_analyze.txt") if (TEMP_DIR / "dead_code_flutter_analyze.txt").exists() else ""
    py_linter = "not installed: ruff and pyflakes unavailable"

    payload = {
        "schema": "engel_dead_code_audit_v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "root": str(ROOT),
        "mode": "report_only_no_mutation",
        "source_file_count": len(source_paths),
        "source_counts_by_suffix": summarize_files(source_paths),
        "finding_count": len(findings),
        "confirmed_count": confidence_counts.get("confirmed", 0),
        "candidate_count": len(findings) - confidence_counts.get("confirmed", 0),
        "severity_counts": dict(severity_counts),
        "analyzers": {
            "cargo": "read runtime/temp/dead_code_cargo_check.txt if present",
            "flutter": "clean" if "No issues found" in flutter_output else "not clean or not run",
            "python_linter": py_linter,
        },
        "findings_markdown_limit": 300,
        "findings": [asdict(f) for f in findings],
        "notes": [
            "Candidate findings are not safe-delete instructions.",
            "Python route modules use dynamic dispatch; manually confirm route/command usage before quarantine.",
            "Stale storage/device references are ranked higher when they appear in source code without an obvious guard/refusal context.",
        ],
    }
    json_path, md_path = write_reports(payload)
    print(json.dumps({"ok": True, "json": str(json_path), "markdown": str(md_path), "findings": len(findings)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
