#!/usr/bin/env python3
"""Verifier for Wiki One Windows body map, worker pre-CODE read, and Journal."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import engel_wiki_one as wiki  # noqa: E402
from engel_project_paths import workspace_module_path  # noqa: E402
from engel_ai_update_routes import resolve_update_route  # noqa: E402
from engel_communication_router import classify_user_input  # noqa: E402
from engel_route_explorer import _group_for_route  # noqa: E402


class Checks:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.passes = 0

    def check(self, condition: bool, name: str, detail: str = "") -> None:
        if condition:
            self.passes += 1
            print("PASS " + name + ((" -- " + detail) if detail else ""))
        else:
            self.failures.append(name + ((": " + detail) if detail else ""))
            print("FAIL " + name + ((" -- " + detail) if detail else ""))


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def main() -> int:
    checks = Checks()
    print("ENGEL_WIKI_ONE_VERIFIER")
    catalog = wiki.load_catalog()
    organs = [item for item in catalog.get("organs", []) if isinstance(item, dict)]
    ids = wiki.organ_ids(catalog)
    one = _read(wiki.ONE_MD)
    context = _read(wiki.CONTEXT_MD)
    contract = _read(wiki.CONTRACT_MD)
    effects = _read(wiki.EFFECTS_MD)
    agents = _read(ROOT / "AGENTS.md")
    claude = _read(ROOT / "CLAUDE.md") + _read(ROOT / "Claude.md")
    job = _read(ROOT / "CODEX_JOB.md")
    handoff = _read(ROOT / "CODEX_HANDOFF.md")
    commands = _read(ROOT / "memory" / "ENGEL_COMMANDS.md")
    rules = _read(ROOT / ".grok" / "rules" / "wiki-one.md")
    skill = _read(ROOT / ".agents" / "skills" / "engel-wiki-one" / "SKILL.md")
    verify_skill = _read(ROOT / ".agents" / "skills" / "engel-verify-and-report" / "SKILL.md")
    verify_skill_dup = _read(ROOT / "skills" / "engel-verify-and-report" / "SKILL.md")
    constitution = _read(ROOT / "memory" / "ENGEL_CORE_DIRECTION_AND_SAFETY_CONSTITUTION_V1.md")
    body_parts = _read(ROOT / "ENGEL_BODY_PARTS.md")
    icm = _read(ROOT / "memory" / "icm" / "engel-ai-main" / "CLAUDE.md")
    meeting = _read(ROOT / "memory" / "ENGEL_AGENT_MEETING_ROOM_CONTRACT_V1.md")
    grok_bot = _read(ROOT / "memory" / "ENGEL_GROK_BOT_CONTRACT_V1.md")
    grok_skill = _read(ROOT / ".agents" / "skills" / "engel-grok-bot" / "SKILL.md")
    android_skill = _read(ROOT / ".agents" / "skills" / "engel-android-worker-fleet" / "SKILL.md")
    collab_skill = _read(ROOT / ".agents" / "skills" / "engel-sub-engel-collab-align" / "SKILL.md")
    cursor_rule = _read(ROOT / ".cursor" / "rules" / "wiki-one.mdc")
    body_status = _read(workspace_module_path(ROOT, "engel_ai_body_status") or ROOT / "engel_ai_body_status.py")
    desktop = _read(ROOT / "engel_desktop_v2.py")
    flutter = _read(ROOT / "engel_flutter_main" / "lib" / "main.dart")
    module = _read(workspace_module_path(ROOT, "engel_wiki_one") or ROOT / "engel_wiki_one.py")

    checks.check(wiki.ONE_MD.is_file(), "wiki/ONE.md exists")
    checks.check(wiki.CONTEXT_MD.is_file(), "wiki/CONTEXT.md exists")
    checks.check(wiki.CONTRACT_MD.is_file(), "wiki/CONTRACT.md exists")
    checks.check(wiki.ORGANS_JSON.is_file(), "wiki/organs.json exists")
    checks.check(wiki.EFFECTS_MD.is_file(), "wiki/effects/CONTEXT.md exists")
    checks.check(len(organs) >= 20, "at least 20 organs", str(len(organs)))
    checks.check(len(ids) == len(set(ids)), "organ ids unique")
    checks.check(catalog.get("schema") == "engel_wiki_one_organs_v1", "organs schema")
    checks.check("Josh > Guardian" in str(catalog.get("authority") or ""), "authority order")
    checks.check("LAPTOP-0KUVK82E" in str(catalog.get("host") or "") or "LAPTOP-0KUVK82E" in one, "windows host named")

    known = set(ids)
    for item in organs:
        oid = str(item.get("id") or "")
        checks.check(bool(oid and item.get("name") and item.get("does") and item.get("home")), "organ fields " + oid)
        checks.check(str(item.get("life") or "").lower() == "alive" or str(item.get("universe") or "") == "live", "organ alive " + oid)
        talks = item.get("talks_to") or []
        bad = [str(x) for x in talks if str(x) not in known]
        checks.check(not bad, "talks_to resolve " + oid, ",".join(bad))
        checks.check(oid in one and str(item.get("name") or "") in one, "ONE.md lists " + oid)
        sources = item.get("sources") or []
        checks.check(isinstance(sources, list) and sources, "sources listed " + oid)

    checks.check("ORGANS ALIVE" in one or "alive" in one.lower(), "ONE.md organs alive")
    checks.check("chat_runtime" in known and "chat_llm" in known and "governor" in known, "Cosmic Swarm live desks present")
    checks.check("land CODE" in one and "stamp" in one.lower(), "ONE.md landing rule")
    checks.check("update" in one.lower() and "organs.json" in one, "ONE.md update duty")
    checks.check("stamp_wiki_one_journal.py" in context and "--wiki-read" in context, "CONTEXT landing command")
    checks.check("updates it" in context.lower() or "update" in context.lower(), "CONTEXT update duty")
    checks.check(
        "read" in contract.lower() and "update" in contract.lower() and "whole Engel AI Main" in contract,
        "CONTRACT read+update",
    )
    checks.check("If you are changing" in effects, "effects index")
    whole_surfaces = {
        "AGENTS.md": agents,
        "CLAUDE.md": claude,
        "CODEX_JOB.md": job,
        "CODEX_HANDOFF.md": handoff,
        "ENGEL_COMMANDS.md": commands,
        "Grok rule": rules,
        "wiki-one skill": skill,
        "verify-and-report skill": verify_skill,
        "verify-and-report skills copy": verify_skill_dup,
        "constitution": constitution,
        "ENGEL_BODY_PARTS.md": body_parts,
        "ICM catalog": icm,
        "Meeting Room contract": meeting,
        "Grok Bot contract": grok_bot,
        "Grok Bot skill": grok_skill,
        "Android worker skill": android_skill,
        "Sub-Engel collab skill": collab_skill,
        "Cursor Wiki One rule": cursor_rule,
        "AI body status": body_status,
        "Desktop V2": desktop,
        "Cosmic Swarm OS": flutter,
    }
    for name, text in whole_surfaces.items():
        checks.check("wiki/ONE.md" in text or "Wiki One" in text, name + " knows Wiki One")
        checks.check("update" in text.lower(), name + " names update duty")
    checks.check("stamp_wiki_one_journal" in agents, "AGENTS.md journal stamp")
    checks.check("wiki one" in commands.lower() and "update wiki one" in commands.lower(), "ENGEL_COMMANDS.md lists wiki update")
    checks.check("Wiki One" in skill and "--wiki-read" in skill, "wiki-one skill stamp")
    checks.check("wiki_phrases" in desktop and "engel_wiki_one" in desktop, "Desktop V2 intercepts wiki phrases")
    checks.check("Wiki One: wiki/ONE.md" in body_status, "AI body status surfaces Wiki One")
    checks.check("'wiki_one'" in flutter and "canonical second brain" in flutter, "Cosmic Swarm hosts Wiki One second brain")
    checks.check("home-wiki-one-shortcut" in flutter and "_openWikiBrain" in flutter, "Cosmic Swarm Home opens Wiki One")
    checks.check("Engel AI Main organs — ALIVE" in flutter, "Organs view says ALIVE")
    checks.check("cosmic_swarm" in known, "cosmic_swarm organ exists")
    checks.check("alive_state: false" not in _read(wiki.JOURNAL_LATEST), "Journal does not say organs not alive")

    blocked = ("requests", "urllib", "socket", "webbrowser")
    for name in blocked:
        checks.check(("import " + name) not in module and ("from " + name) not in module, "no " + name + " import")
    checks.check("ALIVE_STATE" in module and "trusted_memory" in module, "module names blocked writes")
    checks.check("C:\\\\Users" not in one and "C:/Users" not in module, "no C: user paths in map/module")

    refuse = wiki.stamp_journal(
        lane="grok",
        worker="verifier",
        organs=["wiki_one"],
        summary="should refuse",
        files=[],
        receipt="",
        wiki_read=False,
    )
    checks.check(refuse.get("ok") is False, "stamp refuses without wiki-read")
    bad_organ = wiki.stamp_journal(
        lane="grok",
        worker="verifier",
        organs=["not_an_organ"],
        summary="bad",
        files=[],
        receipt="",
        wiki_read=True,
    )
    checks.check(bad_organ.get("ok") is False, "stamp refuses unknown organ")
    ok_stamp = wiki.stamp_journal(
        lane="auto",
        worker="verify_wiki_one",
        organs=["wiki_one", "factories", "verifiers"],
        summary="Wiki One verifier sample stamp",
        files=["tools/verify_wiki_one.py"],
        receipt="reports/codex_bridge/ENGEL_WIKI_ONE_WINDOWS_BODY_20260829.md",
        wiki_read=True,
    )
    checks.check(ok_stamp.get("ok") is True, "stamp writes journal", str(ok_stamp.get("error") or ""))
    checks.check(wiki.JOURNAL_JSONL.is_file(), "journal jsonl exists")
    checks.check(wiki.JOURNAL_LATEST.is_file(), "journal LATEST.md exists")

    status = wiki.render_wiki_one_status()
    checks.check("Wiki One" in status and "face" in status and "ct246_body" in status, "status lists organs")
    journal = wiki.render_wiki_one_journal()
    checks.check("Wiki One Journal" in journal, "journal renderer")
    checks.check(resolve_update_route("wiki one") == "engel.wiki_one.status", "wiki one alias")
    checks.check(resolve_update_route("wiki journal") == "engel.wiki_one.journal", "wiki journal alias")
    checks.check(resolve_update_route("update wiki one") == "engel.wiki_one.update", "update wiki one alias")
    checks.check(_group_for_route("engel.wiki_one.status") == "Wiki One", "explorer group")
    intent = classify_user_input("wiki one")
    checks.check(intent.route_target == "engel.wiki_one.status", "router hits wiki one")
    journal_intent = classify_user_input("wiki journal")
    checks.check(journal_intent.route_target == "engel.wiki_one.journal", "router hits wiki journal")
    update_intent = classify_user_input("update wiki one")
    checks.check(update_intent.route_target == "engel.wiki_one.update", "router hits wiki update")
    update_text = wiki.render_wiki_one_update()
    checks.check(
        "canonical second brain" in update_text and "UPDATE" in update_text,
        "update duty renderer",
    )

    if checks.failures:
        print("ENGEL_WIKI_ONE_VERIFY_FAIL")
        for item in checks.failures:
            print(" - " + item)
        return 1
    print("ENGEL_WIKI_ONE_VERIFY_PASS " + str(checks.passes) + "/" + str(checks.passes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
