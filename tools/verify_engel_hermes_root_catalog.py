#!/usr/bin/env python3
"""Gate for Hermes skill + root agent catalog import into Engel AI Main."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "runtime" / "next_stage" / "hermes_agent_catalog" / "IMPORT_SUMMARY.json"
OPTIONAL_SUMMARY = ROOT / "runtime" / "next_stage" / "hermes_agent_catalog" / "OPTIONAL_IMPORT_SUMMARY.json"
SKILL_REG = ROOT / "memory" / "skills" / "ENGEL_SAVED_SKILL_REGISTRY.json"
AGENT_REG = ROOT / "memory" / "agents" / "ENGEL_SAVED_AGENT_REGISTRY.json"
HERMES_SRC = ROOT / "engel_agent_main" / "skills"
OPTIONAL_SRC = ROOT / "engel_agent_main" / "optional-skills"
CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""))


def main() -> int:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    optional = json.loads(OPTIONAL_SUMMARY.read_text(encoding="utf-8")) if OPTIONAL_SUMMARY.is_file() else {}
    skills = json.loads(SKILL_REG.read_text(encoding="utf-8")).get("skills") or {}
    agents = json.loads(AGENT_REG.read_text(encoding="utf-8")).get("agents") or {}
    hermes_keys = [k for k in skills if str(k).startswith("engel-hermes-")]
    src_skills = list(HERMES_SRC.rglob("SKILL.md"))
    opt_src = list(OPTIONAL_SRC.rglob("SKILL.md"))
    opt_saved = list(optional.get("skills_saved") or [])
    check("summary_ok", bool(summary.get("ok")))
    check("source_skill_count_89", len(src_skills) == 89, str(len(src_skills)))
    check("optional_source_81", len(opt_src) == 81, str(len(opt_src)))
    check("saved_hermes_170", len(hermes_keys) == 170, str(len(hermes_keys)))
    check("summary_skills_89", int(summary.get("skills_count") or 0) == 89)
    check("optional_summary_81", int(optional.get("skills_count") or 0) == 81, str(optional.get("skills_count")))
    check("optional_files", all((ROOT / "skills" / k / "SKILL.md").is_file() for k in opt_saved))
    check("summary_agents_60", int(summary.get("agents_count") or 0) == 60)
    check("agents_include_prior", "engel-prototyper" in agents and "skill-creator-agent" in agents)
    check("agents_total_62", len(agents) >= 62, str(len(agents)))
    missing_skill_files = [k for k in hermes_keys if not (ROOT / "skills" / k / "SKILL.md").is_file()]
    missing_mirrors = [k for k in hermes_keys if not (ROOT / ".agents" / "skills" / k / "SKILL.md").is_file()]
    check("skill_files_exist", not missing_skill_files, ",".join(missing_skill_files[:5]))
    check("skill_mirrors_exist", not missing_mirrors, ",".join(missing_mirrors[:5]))
    check("original_hermes_untouched", (HERMES_SRC / "software-development" / "plan" / "SKILL.md").is_file())
    check("original_backend_card", (ROOT / "agents" / "backend-architect.md").is_file())
    backend = (ROOT / "agents" / "backend-architect.md").read_text(encoding="utf-8", errors="replace")
    check("original_backend_not_flattened", backend.startswith("---"))
    god = (ROOT / "skills" / "engel-hermes-godmode" / "SKILL.md").read_text(encoding="utf-8", errors="replace")
    check("godmode_authority", "Josh > Guardian" in god)
    check("godmode_defensive", "Defensive review only" in god)
    poly = (ROOT / "skills" / "engel-hermes-polymarket" / "SKILL.md").read_text(encoding="utf-8", errors="replace")
    check("polymarket_disarmed", "DISARMED" in poly)
    hyper = ROOT / "skills" / "engel-hermes-hyperliquid" / "SKILL.md"
    check("hyperliquid_present", hyper.is_file())
    if hyper.is_file():
        htext = hyper.read_text(encoding="utf-8", errors="replace")
        check("hyperliquid_disarmed", "DISARMED" in htext)
        check("hyperliquid_recreated", "recreated Engel skill" in htext)
    sample_agent = ROOT / "agents" / "engel-backend-architect.md"
    check("saved_backend_agent", sample_agent.is_file())
    if sample_agent.is_file():
        text = sample_agent.read_text(encoding="utf-8", errors="replace")
        check("saved_agent_authority", "Josh > Guardian" in text)
        check("saved_agent_source_pointer", "agents/backend-architect.md" in text.replace("\\", "/"))
    archive = ROOT / "runtime" / "next_stage" / "hermes_agent_catalog" / "agent_cards"
    check("archive_60", archive.is_dir() and len(list(archive.glob("*.md"))) == 60, str(len(list(archive.glob("*.md"))) if archive.is_dir() else 0))
    failed = [name for name, ok, _ in CHECKS if not ok]
    print("RESULT " + ("PASS" if not failed else "FAIL") + f" {len(CHECKS) - len(failed)}/{len(CHECKS)}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
