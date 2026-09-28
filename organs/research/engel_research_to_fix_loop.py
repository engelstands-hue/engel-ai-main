from __future__ import annotations

import argparse
import datetime
import json
from pathlib import Path
import sys
import textwrap
from typing import Any


PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
MAX_RECENT_FILES = 5

LOOP_VERSION = "Engel Research-to-Fix Loop V1"

# ── V1 CLI subcommand additions (status / list / inspect / propose) ───
# Extended from the original render_status/render_summary surface. The
# legacy `--status` / `--summary` flag mode is preserved below for the
# callers in engel_companion.py / engel_daily_cycle_runner.py /
# engel_research_office.py.

CONTRACT_JSON_REL = "memory/ENGEL_RESEARCH_TO_FIX_LOOP_CONTRACT_V1.json"
APPROVAL_TOKEN_FUTURE = "APPROVE_FIX_CANDIDATE"

# Project-relative input folders for the V1 subcommand surface. Bounded
# scan. Project-relative ONLY.
#
# Tightened 2026-05-19: removed "reports/codex_bridge" — that folder is
# the home for *past completed* Codex task receipts. Scanning it surfaces
# 100+ historical wins as if they were pending fix candidates, which is
# misleading. Forward-looking research findings can still land in
# reports/research/ or reports/learning_jobs/ and be picked up here.
SCAN_FOLDERS_V1 = [
    "reports/candidate_learning_output_review",
    "reports/learning_jobs",
    "reports/memory_candidates",
    "reports/memory_candidate_proposals",
    "reports/fix_candidate_queue",
    "reports/research",
]

# Hard bounds — any input over the limit is skipped.
MAX_FILES_PER_FOLDER = 200
MAX_BYTES_PER_FILE = 256 * 1024  # 256 KB
ALLOWED_SUFFIXES = {".md", ".json", ".txt"}
SUSPECT_PATTERNS = [
    "issue:", "problem:", "bug:", "broken", "fail", "error",
    "candidate:", "candidate_id", "lesson:", "fix:", "suggested fix",
    "regression", "missing", "stale",
]

# Boundary guards (constants used by the verifier — see file footer).
RESEARCH_TO_FIX_DOES_NOT_WRITE_SOURCE = True
RESEARCH_TO_FIX_DOES_NOT_CALL_NETWORK = True
RESEARCH_TO_FIX_DOES_NOT_RUN_MODEL = True
RESEARCH_TO_FIX_DOES_NOT_PROMOTE_MEMORY = True
RESEARCH_TO_FIX_DOES_NOT_START_BACKGROUND_WORKER = True

LOOP_STATUS = [
    "RESEARCH_TO_FIX_LOOP",
    "LOCAL_ONLY",
    "CANDIDATE_CHAIN_ONLY",
    "NO_VERIFIER_UPDATE",
    "NO_SELF_FIX_POLICY_UPDATE",
    "NO_RUNNER_ACTIVATION",
    "NO_PATCH_APPLY",
    "NO_SOURCE_MUTATION",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_BACKGROUND_WORKER",
]

CANDIDATE_COMPONENTS = [
    ("research notes", "Research notes", "reports\\self_research_notes"),
    ("lesson candidates", "Lesson candidates", "reports\\lesson_candidates"),
    ("memory candidate proposals", "Memory candidate proposals", "reports\\memory_candidates"),
    ("verifier improvement candidates", "Verifier improvement candidates", "reports\\verifier_improvement_candidates"),
    ("self-fix improvement candidates", "Self-fix improvement candidates", "reports\\self_fix_improvement_candidates"),
]

PLANNING_REFERENCES = [
    ("low-risk self-fix contract", "Low-Risk Self-Fix Runner Contract V1", "memory\\ENGEL_LOW_RISK_SELF_FIX_RUNNER_CONTRACT_V1.md"),
    ("low-risk runner status", "Low-Risk Self-Fix Runner V1", "engel_low_risk_self_fix_runner.py"),
    ("self-fix autopilot contract", "Engel Self-Fix Autopilot Contract V1", "memory\\ENGEL_SELF_FIX_AUTOPILOT_CONTRACT_V1.md"),
]

BOUNDARIES = [
    "candidate-only boundary: research-derived outputs remain proposals and candidates",
    "no apply boundary: this loop does not apply improvements automatically",
    "no verifier edits are performed",
    "no self-fix policy edits are performed",
    "no runner activation is performed",
    "no patch apply is performed",
    "no source mutation is performed",
    "no trusted memory writes are performed",
    "no provider/network/browser behavior is used",
    "no background worker is started",
]

NEXT_SAFE_STEPS = [
    "Review candidate files manually.",
    "Choose one verifier or self-fix improvement candidate for separate human review.",
    "Create a dedicated implementation task only after human approval.",
    "Run the targeted verifier and standard guard verifiers before any future policy or source change.",
]


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def project_path(relative_path: str) -> Path:
    path = (PROJECT_ROOT / relative_path).resolve()
    if not is_relative_to(path, PROJECT_ROOT.resolve()):
        raise ValueError("research-to-fix path escaped project root")
    return path


def safe_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def candidate_files(relative_folder: str, limit: int = MAX_RECENT_FILES) -> list[Path]:
    folder = project_path(relative_folder)
    if not folder.exists() or not folder.is_dir():
        return []
    files = [item for item in folder.iterdir() if item.is_file() and item.name != ".gitkeep"]
    files.sort(key=safe_mtime, reverse=True)
    return files[:limit]


def candidate_count(relative_folder: str) -> int:
    folder = project_path(relative_folder)
    if not folder.exists() or not folder.is_dir():
        return 0
    return sum(1 for item in folder.iterdir() if item.is_file() and item.name != ".gitkeep")


def reference_status(relative_path: str) -> str:
    path = project_path(relative_path)
    if path.exists() and path.is_file():
        return "present"
    return "missing"


def render_status() -> str:
    lines: list[str] = [
        LOOP_VERSION,
        "",
        "Status:",
    ]
    lines.extend(f"- {status}" for status in LOOP_STATUS)
    lines.extend(
        [
            "",
            "Research-to-fix candidate chain:",
            "- Self-Learning Mini Runner V1 creates candidate learning outputs.",
            "- Verifier Improvement Candidate V1 proposes verifier improvements only.",
            "- Self-Fix Improvement Candidate V1 proposes future self-fix improvements only.",
            "- Low-risk self-fix policy planning remains separate from any apply behavior.",
            "",
            "Candidate folders (non-recursive counts and recent file names):",
        ]
    )
    for _key, label, relative_folder in CANDIDATE_COMPONENTS:
        count = candidate_count(relative_folder)
        lines.append(f"- {label}: {relative_folder}\\ ({count} files)")
        recent = candidate_files(relative_folder)
        if recent:
            for path in recent:
                lines.append(f"  - {path.name}")
        else:
            lines.append("  - no candidate files found")

    lines.extend(["", "Low-risk self-fix planning references:"])
    for _key, label, relative_path in PLANNING_REFERENCES:
        lines.append(f"- {label}: {relative_path} ({reference_status(relative_path)})")

    lines.extend(["", "Boundaries:"])
    lines.extend(f"- {boundary}" for boundary in BOUNDARIES)

    lines.extend(["", "Next safe steps:"])
    lines.extend(f"- {step}" for step in NEXT_SAFE_STEPS)
    return "\n".join(lines) + "\n"


def render_summary() -> str:
    total = sum(candidate_count(relative_folder) for _key, _label, relative_folder in CANDIDATE_COMPONENTS)
    lines: list[str] = [
        LOOP_VERSION + " Summary",
        "",
        "Status:",
    ]
    lines.extend(f"- {status}" for status in LOOP_STATUS)
    lines.extend(
        [
        f"Total candidate files visible non-recursively: {total}",
        "",
        "Counts:",
        ]
    )
    for _key, label, relative_folder in CANDIDATE_COMPONENTS:
        lines.append(f"- {label}: {candidate_count(relative_folder)}")
    lines.extend(
        [
            "",
            "Required display:",
            "- research notes",
            "- lesson candidates",
            "- memory candidate proposals",
            "- verifier improvement candidates",
            "- self-fix improvement candidates",
            "- low-risk self-fix contract",
            "- low-risk runner status",
            "- candidate-only boundary",
            "- no apply boundary",
            "",
            "Summary boundary:",
        ]
    )
    lines.extend(f"- {boundary}" for boundary in BOUNDARIES)
    return "\n".join(lines) + "\n"


def usage_text() -> str:
    return textwrap.dedent(
        """\
        Engel Research-to-Fix Loop V1

        Usage:
          python engel_research_to_fix_loop.py --status
          python engel_research_to_fix_loop.py --summary

        Boundary:
          Status/summary only. No verifier update, no self-fix policy update, no runner activation,
          no patch apply, no source mutation, no trusted-memory write, no provider/network/browser,
          and no background worker.
        """
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=True, description="Show the bounded research-to-fix candidate chain.")
    parser.add_argument("--status", action="store_true", help="Show detailed research-to-fix candidate chain status.")
    parser.add_argument("--summary", action="store_true", help="Show a compact research-to-fix candidate chain summary.")
    return parser


# ── V1 subcommand surface (status / list / inspect / propose) ─────────
def _safe_under_root(p: Path) -> bool:
    """Block any path that resolves outside the project root."""
    try:
        p.resolve().relative_to(PROJECT_ROOT.resolve())
        return True
    except ValueError:
        return False


def _now_token() -> str:
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def _load_contract() -> dict[str, Any]:
    p = PROJECT_ROOT / CONTRACT_JSON_REL
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _iter_files_bounded(folder: Path, remaining: int) -> list[Path]:
    """Depth-1 bounded directory listing using only iterdir() — matches the
    legacy module's iteration style and avoids the AST-forbidden .glob().
    No recursion."""
    out: list[Path] = []
    try:
        children = sorted(folder.iterdir(), key=lambda p: p.name)
    except OSError:
        return out
    for p in children:
        if len(out) >= remaining:
            break
        try:
            if p.is_file():
                out.append(p)
        except OSError:
            continue
    return out


def _scan_folder_v1(folder_rel: str) -> list[dict[str, Any]]:
    """Bounded scan of an approved project-relative folder. Returns at most
    MAX_FILES_PER_FOLDER entries. Skips binaries / oversized / unsafe paths.
    Every entry is treated as UNTRUSTED text. No recursion."""
    items: list[dict[str, Any]] = []
    folder = PROJECT_ROOT / folder_rel
    if not folder.exists() or not folder.is_dir():
        return items
    for p in _iter_files_bounded(folder, MAX_FILES_PER_FOLDER):
        if not _safe_under_root(p):
            continue
        if p.suffix.lower() not in ALLOWED_SUFFIXES:
            continue
        try:
            size = p.stat().st_size
        except OSError:
            continue
        if size <= 0 or size > MAX_BYTES_PER_FILE:
            continue
        items.append({
            "path": p.relative_to(PROJECT_ROOT).as_posix(),
            "size_bytes": size,
            "kind": "research_or_candidate_learning_output",
        })
    return items


def _read_untrusted_text(rel_path: str) -> str:
    """Read a project-relative file as UNTRUSTED text. Never exec/eval."""
    p = PROJECT_ROOT / rel_path
    if not _safe_under_root(p):
        return ""
    if not p.exists() or not p.is_file():
        return ""
    try:
        return p.read_text(encoding="utf-8", errors="replace")[:MAX_BYTES_PER_FILE]
    except OSError:
        return ""


def _suspected_issue_summary(text: str) -> str:
    """Pick a single bounded line from untrusted text for human review.
    No interpretation, no execution."""
    for line in text.splitlines():
        l = line.strip()
        if not l:
            continue
        if any(token in l.lower() for token in SUSPECT_PATTERNS):
            return l[:200]
    for line in text.splitlines():
        l = line.strip()
        if l:
            return l[:200]
    return ""


def _guess_fix_area(rel_path: str) -> str:
    low = rel_path.lower()
    if "memory_candidate" in low or low.startswith("memory/") or "/memory/" in low:
        return "memory"
    if "verifier" in low:
        return "verifier"
    if "contract" in low:
        return "contract"
    if low.endswith(".md"):
        return "doc"
    if "research" in low.split("/"):
        return "research"
    return "unknown"


def cmd_status() -> int:
    contract = _load_contract()
    items_total = 0
    folder_summary: list[tuple[str, str, int]] = []
    for folder in SCAN_FOLDERS_V1:
        full = PROJECT_ROOT / folder
        if not full.exists():
            folder_summary.append((folder, "missing", 0))
            continue
        items = _scan_folder_v1(folder)
        items_total += len(items)
        folder_summary.append((folder, "scanned", len(items)))

    print("# Engel Research-to-Fix Loop V1 -- STATUS")
    print()
    print(f"Contract present:        {'YES' if contract else 'NO'}  ({CONTRACT_JSON_REL})")
    if contract:
        for key in (
            "status", "can_apply_fixes", "can_edit_source",
            "can_promote_memory", "can_run_models", "can_use_network",
            "requires_human_review",
        ):
            print(f"{key + ':':25s}{contract.get(key, '?')}")
    print()
    print("Source folders scanned (bounded, project-relative only):")
    for folder, state, n in folder_summary:
        mark = "+" if state == "scanned" else "-"
        print(f"  {mark} {folder:50s}  {state:8s}  items={n}")
    print()
    print(f"Total candidate-eligible items observed: {items_total}")
    print()
    print("Apply / promote / source-write: DISABLED (by contract).")
    print(f"Future apply phase will require token: {APPROVAL_TOKEN_FUTURE}")
    return 0


def cmd_list() -> int:
    print("# Engel Research-to-Fix Loop V1 -- LIST (untrusted preview)")
    print()
    print("All entries below are UNTRUSTED. No fix has been applied.")
    print()
    any_items = False
    for folder in SCAN_FOLDERS_V1:
        items = _scan_folder_v1(folder)
        if not items:
            continue
        any_items = True
        print(f"## {folder}  ({len(items)} item(s))")
        for it in items[:20]:
            kb = max(1, it["size_bytes"] // 1024)
            print(f"  - {it['path']}  ({kb} KB)")
        if len(items) > 20:
            print(f"  ...({len(items) - 20} more, hidden -- bounded preview)")
        print()
    if not any_items:
        print("(No items found in any approved input folder.)")
    return 0


def cmd_inspect_json() -> int:
    out: dict[str, Any] = {
        "loop_name": "engel_research_to_fix_loop_v1",
        "status": "inert_review_bridge_only",
        "scanned_folders": [],
        "total_items": 0,
        "trust_status": "all_inputs_untrusted",
        "apply_enabled": False,
        "future_apply_requires_token": APPROVAL_TOKEN_FUTURE,
    }
    total = 0
    for folder in SCAN_FOLDERS_V1:
        items = _scan_folder_v1(folder)
        out["scanned_folders"].append({
            "folder": folder,
            "exists": (PROJECT_ROOT / folder).exists(),
            "item_count": len(items),
            "items": items[:50],
        })
        total += len(items)
    out["total_items"] = total
    print(json.dumps(out, indent=2))
    return 0


def cmd_propose_dry_run() -> int:
    """Build fix-candidate proposals IN MEMORY only. Print them. Do not
    write any files. Do not modify any source. Do not promote any memory."""
    now = _now_token()
    candidates: list[dict[str, Any]] = []
    seq = 0
    for folder in SCAN_FOLDERS_V1:
        for item in _scan_folder_v1(folder):
            seq += 1
            rel = item["path"]
            text = _read_untrusted_text(rel)
            suspected = _suspected_issue_summary(text) or "(no suspect-pattern line found; included for review)"
            candidates.append({
                "candidate_id": f"research_to_fix_{now}_{seq:03d}",
                "status": "human_review_required",
                "trusted": False,
                "applied": False,
                "source": {
                    "kind": "research_or_candidate_learning_output",
                    "path": rel,
                },
                "suspected_issue": suspected,
                "suggested_fix_area": _guess_fix_area(rel),
                "risk_flags": [
                    "input_is_untrusted_text",
                    "no_verification_run",
                    "no_human_review_yet",
                ],
                "requires_human_decision": True,
                "requires_future_approval_token": APPROVAL_TOKEN_FUTURE,
                "notes": "Do not execute or trust source content. Dry-run preview only.",
            })

    print(json.dumps({
        "mode": "dry_run",
        "applied": False,
        "promoted_to_trusted_memory": False,
        "source_files_written": False,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "trust_statement": (
            "All candidates are human_review_required. None have been "
            "verified, applied, or promoted. No source, memory, queue, "
            "or route was modified by this command."
        ),
    }, indent=2))
    return 0


def _is_v1_subcommand(argv: list[str]) -> bool:
    return bool(argv) and argv[0] in {"status", "list", "inspect", "propose"}


def _dispatch_v1_subcommand(argv: list[str]) -> int:
    sub = argv[0]
    rest = argv[1:]
    if sub == "status":
        return cmd_status()
    if sub == "list":
        return cmd_list()
    if sub == "inspect":
        # `--json` accepted for explicitness; default is JSON regardless.
        return cmd_inspect_json()
    if sub == "propose":
        if "--dry-run" not in rest:
            print("Refusing: propose requires --dry-run in V1 (apply is disabled).", file=sys.stderr)
            return 2
        return cmd_propose_dry_run()
    print(f"Unknown subcommand: {sub}", file=sys.stderr)
    return 2


def main(argv: list[str] | None = None, stdout=None, stderr=None) -> int:
    out = stdout if stdout is not None else sys.stdout
    err = stderr if stderr is not None else sys.stderr
    argv_list = list(argv) if argv is not None else sys.argv[1:]

    # New V1 subcommand surface (status / list / inspect / propose).
    if _is_v1_subcommand(argv_list):
        return _dispatch_v1_subcommand(argv_list)

    # Legacy flag surface (--status / --summary) — preserved for the
    # callers in engel_companion / engel_daily_cycle_runner /
    # engel_research_office.
    args = build_parser().parse_args(argv_list)
    if args.status and args.summary:
        err.write("Choose either --status or --summary, not both.\n")
        return 2
    if args.status:
        out.write(render_status())
        return 0
    if args.summary:
        out.write(render_summary())
        return 0
    out.write(usage_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
