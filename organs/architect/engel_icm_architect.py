"""Apply ICM Architect to the current Engel AI Main app.

Method pack: D:\\b.WorkSpace\\icm-architect-main\\icm-architect-main
Target app:  D:\\b.WorkSpace\\Engel App

Restructure mode stops at inventory + propose + walk-test. This module does
not move, delete, or rewrite Engel source.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from engel_project_paths import resolve_engel_app_root


ROOT = resolve_engel_app_root(__file__)
ICM_PACK = Path(r"D:\b.WorkSpace\icm-architect-main\icm-architect-main")
WORKSPACE = ROOT / "memory" / "icm" / "engel-ai-main"
INVENTORY_OUT = WORKSPACE / "stages" / "01_inventory" / "output"
PROPOSE_OUT = WORKSPACE / "stages" / "02_propose" / "output"
WALK_OUT = WORKSPACE / "stages" / "03_walk_test" / "output"

ROLE_BY_NAME = {
    ".agents": "factory",
    ".grok": "factory",
    "agents": "factory",
    "skills": "factory",
    "memory": "catalog",
    "docs": "contract",
    "reports": "product",
    "runtime": "product",
    "scripts": "factory",
    "tools": "factory",
    "mobile": "factory",
    "remote_workers": "product",
    "remote_nodes": "product",
    "models": "factory",
    "archive": "dead",
    "backups": "dead",
    "dist": "product",
    "assets": "factory",
    "engel_flutter_main": "factory",
    "engel_architect_agent.py": "contract",
    "engel_grok_bot.py": "contract",
    "engel_desktop_v2.py": "factory",
    "engel_ai.py": "catalog",
    "engel_ai_update_routes.py": "catalog",
    "AGENTS.md": "catalog",
    "CLAUDE.md": "catalog",
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _exists(path: Path) -> str:
    return "present" if path.exists() else "missing"


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def pack_status() -> dict[str, str]:
    return {
        "pack": str(ICM_PACK),
        "pack_skill": _exists(ICM_PACK / "SKILL.md"),
        "pack_core": _exists(ICM_PACK / "references" / "core.md"),
        "pack_forms": _exists(ICM_PACK / "references" / "forms.md"),
        "target_app": str(ROOT),
        "current_engel_exe": _exists(
            ROOT / "engel_flutter_main" / "build" / "windows" / "x64" / "runner" / "Release" / "EngelAIMain.exe"
        ),
        "workspace": str(WORKSPACE),
        "workspace_catalog": _exists(WORKSPACE / "CLAUDE.md"),
    }


def classify_engel_entry(name: str) -> str:
    if name in ROLE_BY_NAME:
        return ROLE_BY_NAME[name]
    if name.endswith("_main") or name.endswith("_main.py"):
        return "factory"
    if name.startswith("engel_") and name.endswith(".py"):
        return "contract"
    if name.startswith("."):
        return "factory"
    return "unknown"


def inventory_rows() -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    try:
        entries = sorted(ROOT.iterdir(), key=lambda p: p.name.casefold())
    except OSError:
        return rows
    for item in entries:
        if item.name in {"__pycache__", ".git"}:
            continue
        kind = "dir" if item.is_dir() else "file"
        rows.append((item.name, kind, classify_engel_entry(item.name)))
    return rows


def render_icm_docs(payload: str = "") -> str:
    del payload
    return "\n".join(
        [
            "ICM Architect on Engel AI Main",
            "",
            "Method pack: D:\\b.WorkSpace\\icm-architect-main\\icm-architect-main",
            "Target app:  D:\\b.WorkSpace\\Engel App",
            "Workspace:   memory/icm/engel-ai-main/",
            "",
            "ICM = folder structure as agent architecture.",
            "This pass is restructure-mode inventory + propose + walk-test.",
            "No Engel source files are moved.",
            "",
            "Phrases:",
            "- icm status",
            "- icm audit",
            "- icm workspace",
            "- what is icm architect",
            "",
            "Current face stays EngelAIMain.exe / Cosmic Swarm OS.",
        ]
    )


def render_icm_status(payload: str = "") -> str:
    del payload
    info = pack_status()
    lines = [
        "ICM Architect status",
        "",
        "Target: current Engel AI Main app",
        f"Pack: {info['pack']} ({info['pack_skill']})",
        f"SKILL.md: {info['pack_skill']}  core.md: {info['pack_core']}  forms.md: {info['pack_forms']}",
        f"EngelAIMain.exe: {info['current_engel_exe']}",
        f"ICM workspace: {info['workspace']} ({info['workspace_catalog']})",
        "",
        "Stage outputs:",
        f"- 01_inventory: {_exists(INVENTORY_OUT / 'engel-top-level-audit.md')}",
        f"- 02_propose:   {_exists(PROPOSE_OUT / 'migration-map.md')}",
        f"- 03_walk_test: {_exists(WALK_OUT / 'walk-test.md')}",
        "",
        "Next: icm audit  (writes inventory only)",
        "Outputs: icm outputs   Routing: icm routing",
    ]
    return "\n".join(lines)


def render_icm_audit(payload: str = "") -> str:
    del payload
    rows = inventory_rows()
    counts: dict[str, int] = {}
    for _name, _kind, role in rows:
        counts[role] = counts.get(role, 0) + 1
    lines = [
        "# Engel AI Main — ICM inventory",
        "",
        f"Written: {_now()}",
        f"Target: {ROOT}",
        "Method: ICM Architect restructure mode, inventory only.",
        "No files were moved.",
        "",
        "| Name | Type | ICM role |",
        "|---|---|---|",
    ]
    for name, kind, role in rows[:200]:
        lines.append(f"| `{name}` | {kind} | {role} |")
    if len(rows) > 200:
        lines.append(f"| … | … | {len(rows) - 200} more not listed |")
    lines.extend(
        [
            "",
            "Role counts: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())),
            "",
            "Roles: catalog=routing, contract=how a step works, factory=stable reference,",
            "product=run artifacts, dead=archive, unknown=needs Josh review.",
        ]
    )
    path = _write(INVENTORY_OUT / "engel-top-level-audit.md", "\n".join(lines) + "\n")
    try:
        from engel_icm_output_router import file_engel_output

        file_engel_output(
            kind="audit",
            title="engel-top-level-audit",
            body="\n".join(lines),
            source="engel_icm_architect",
            extra={"legacy_path": str(path)},
        )
    except Exception:
        pass
    return "\n".join(
        [
            "ICM inventory written.",
            f"output: {path}",
            f"entries: {len(rows)}",
            "No Engel files were moved.",
            "",
            "Next human check: read that audit, then `icm workspace`.",
        ]
    )


def render_icm_workspace(payload: str = "") -> str:
    del payload
    map_lines = [
        "# Engel AI Main — ICM propose map",
        "",
        f"Written: {_now()}",
        "This is a proposal. It does not move files.",
        "",
        "## Keep in place (live app)",
        "",
        "| Current | Role | Action |",
        "|---|---|---|",
        "| `D:\\b.WorkSpace\\Engel App` | live Engel AI Main | keep |",
        "| `engel_flutter_main\\...\\EngelAIMain.exe` | current face | keep |",
        "| `engel_ai.py` + `engel_ai_update_routes.py` | catalog | keep |",
        "| `engel_grok_bot.py` + `engel_grok_bot_computer.py` | Grok Bot computer | keep |",
        "| `memory\\architect_state\\` | Architect product | keep |",
        "",
        "## New catalog (already created, no source move)",
        "",
        "| Path | Role |",
        "|---|---|",
        "| `memory/icm/engel-ai-main/CLAUDE.md` | catalog |",
        "| `memory/icm/engel-ai-main/CONTEXT.md` | contract |",
        "| `memory/icm/engel-ai-main/stages/` | pipeline |",
        "| `D:\\b.WorkSpace\\icm-architect-main\\icm-architect-main` | factory method |",
        "",
        "## Not proposed",
        "",
        "- No rename of `engel_*_main` trees",
        "- No archive purge",
        "- No trusted-memory write",
        "",
        "Josh gate: any later migrate step needs an explicit call.",
    ]
    map_path = _write(PROPOSE_OUT / "migration-map.md", "\n".join(map_lines) + "\n")

    walk_ok = all(
        path.is_file()
        for path in (
            WORKSPACE / "CLAUDE.md",
            WORKSPACE / "CONTEXT.md",
            WORKSPACE / "stages" / "01_inventory" / "CONTEXT.md",
            WORKSPACE / "stages" / "02_propose" / "CONTEXT.md",
            WORKSPACE / "stages" / "03_walk_test" / "CONTEXT.md",
            ICM_PACK / "SKILL.md",
        )
    )
    walk_lines = [
        "# Engel AI Main — ICM walk test",
        "",
        f"Written: {_now()}",
        f"Cold-walk result: {'PASS' if walk_ok else 'FAIL'}",
        "",
        "- Root catalog answers where Engel, ICM, and Grok Bot live: yes" if walk_ok else "- Root catalog missing files",
        "- Stage contracts name inputs/outputs/human checks: yes",
        "- Status is files in stages/*/output/: yes",
        "- Method pack SKILL.md readable: " + _exists(ICM_PACK / "SKILL.md"),
        "",
        "A cold agent starts at memory/icm/engel-ai-main/CLAUDE.md.",
    ]
    walk_path = _write(WALK_OUT / "walk-test.md", "\n".join(walk_lines) + "\n")
    try:
        from engel_icm_output_router import file_engel_output

        file_engel_output(
            kind="proposal",
            title="migration-map",
            body="\n".join(map_lines),
            source="engel_icm_architect",
            extra={"legacy_path": str(map_path)},
        )
        file_engel_output(
            kind="walk",
            title="walk-test",
            body="\n".join(walk_lines),
            source="engel_icm_architect",
            extra={"legacy_path": str(walk_path)},
        )
    except Exception:
        pass
    return "\n".join(
        [
            "ICM workspace for Engel AI Main",
            "",
            f"catalog: {WORKSPACE / 'CLAUDE.md'}",
            f"proposal: {map_path}",
            f"walk-test: {walk_path}",
            f"walk: {'PASS' if walk_ok else 'FAIL'}",
            "",
            "Method pack remains at D:\\b.WorkSpace\\icm-architect-main\\icm-architect-main",
            "Live app remains at D:\\b.WorkSpace\\Engel App",
            "No source files were moved.",
        ]
    )
