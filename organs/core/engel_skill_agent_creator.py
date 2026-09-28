#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any


ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
PRIMARY_SKILLS_ROOT = ROOT / "skills"
MANAGED_SKILLS_ROOT = ROOT / ".agents" / "skills"
AGENTS_ROOT = ROOT / "agents"
MEMORY_SKILLS_ROOT = ROOT / "memory" / "skills"
MEMORY_AGENTS_ROOT = ROOT / "memory" / "agents"
SKILL_REGISTRY_PATH = MEMORY_SKILLS_ROOT / "ENGEL_SAVED_SKILL_REGISTRY.json"
AGENT_REGISTRY_PATH = MEMORY_AGENTS_ROOT / "ENGEL_SAVED_AGENT_REGISTRY.json"
RECEIPT_ROOT = ROOT / "reports" / "agent_skill_creation"

SLUG_RE = re.compile(r"[^a-z0-9]+")
CREATE_WORDS = ("create", "make", "build", "save", "add", "new", "write")
SKILL_ROOTS = (PRIMARY_SKILLS_ROOT, MANAGED_SKILLS_ROOT)


class EngelSkillAgentCreatorError(ValueError):
    pass


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _clean_text(value: Any, limit: int = 16000) -> str:
    text = str(value or "").replace("\x00", "")
    text = "".join(ch for ch in text if ch in "\t\r\n" or ord(ch) >= 32).strip()
    if len(text) > limit:
        return text[:limit].rstrip()
    return text


def _clip(value: Any, limit: int = 500) -> str:
    text = " ".join(_clean_text(value).replace("\r", " ").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def slugify(value: Any, fallback_prefix: str = "engel-created") -> str:
    text = _clean_text(value, 180).casefold().replace("&", " and ")
    slug = SLUG_RE.sub("-", text).strip("-")
    if not slug:
        slug = f"{fallback_prefix}-{_stamp().casefold()}"
    return slug[:80].strip("-") or fallback_prefix


def _is_inside(path: Path, root: Path) -> bool:
    resolved = path.resolve(strict=False)
    resolved_root = root.resolve(strict=False)
    try:
        resolved.relative_to(resolved_root)
        return True
    except ValueError:
        return False


def _safe_path(path: Path, root: Path = ROOT) -> Path:
    resolved = path.resolve(strict=False)
    if not _is_inside(resolved, root):
        raise EngelSkillAgentCreatorError(f"refusing to write outside Engel root: {resolved}")
    return resolved


def _project_path(path: Path) -> str:
    try:
        return str(path.resolve(strict=False).relative_to(ROOT.resolve(strict=False))).replace("\\", "/")
    except ValueError:
        return str(path)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        if not path.is_file():
            return {}
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    resolved = _safe_path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    resolved = _safe_path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(text, encoding="utf-8", newline="\n")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    resolved = _safe_path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    with resolved.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _yaml_value(value: Any) -> str:
    return json.dumps(_clean_text(value, 1200), ensure_ascii=False)


def _requirements() -> dict[str, list[str]]:
    return {"bins": [], "anyBins": [], "env": [], "config": [], "os": []}


def _default_skill_entry(
    *,
    name: str,
    description: str,
    slug: str,
    source: str,
    base_dir: Path,
    file_path: Path,
    created_at: str,
    updated_at: str,
    always: bool = True,
) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "source": source,
        "bundled": False,
        "filePath": str(file_path),
        "baseDir": str(base_dir),
        "skillKey": slug,
        "primaryEnv": "engel-ai-main-server",
        "emoji": "",
        "homepage": "",
        "always": always,
        "disabled": False,
        "blockedByAllowlist": False,
        "eligible": True,
        "requirements": _requirements(),
        "missing": _requirements(),
        "configChecks": [],
        "install": [],
        "created_at_utc": created_at,
        "updated_at_utc": updated_at,
    }


def _skill_markdown(
    *,
    slug: str,
    name: str,
    description: str,
    instructions: str,
    trigger_phrases: list[str],
    created_at: str,
    updated_at: str,
) -> str:
    triggers = trigger_phrases or [
        f"Use this skill when the user asks Engel AI Main to handle {name}.",
        f"Use this skill when the request names {name}.",
    ]
    trigger_block = "\n".join(f"- {item}" for item in triggers)
    instruction_text = instructions or (
        "Handle the request directly, save the useful result to Engel persistent memory when appropriate, "
        "and return a concise receipt with the changed paths or verified state."
    )
    return f"""---
name: {_yaml_value(slug)}
description: {_yaml_value(description)}
version: "1.0.0"
source: "engel-ai-main-server"
created_at_utc: {_yaml_value(created_at)}
updated_at_utc: {_yaml_value(updated_at)}
---

# {name}

## Purpose

{description}

## Trigger Conditions

{trigger_block}

## Operating Instructions

{instruction_text}

## Save Contract

- Save durable outputs under Engel AI Main storage, not temporary chat state.
- Update the Engel skill registry after changes.
- Include a receipt path or registry key in the response when this skill creates or changes files.
- Do not expose secrets in skill files, receipts, chat replies, or logs.
"""


def _agent_markdown(
    *,
    name: str,
    slug: str,
    role: str,
    instructions: str,
    skills: list[str],
    created_at: str,
    updated_at: str,
) -> str:
    skill_lines = "\n".join(f"- {skill}" for skill in skills) if skills else "- Use all saved Engel AI Main skills allowed by the registry."
    instruction_text = instructions or (
        "Operate as part of Engel AI Main, use the server-side model runtime when available, "
        "save durable work to Engel persistent memory, and return receipts for changes."
    )
    return f"""# {name}

Role: {role}
Agent key: {slug}
Source: engel-ai-main-server
Created: {created_at}
Updated: {updated_at}

## Operating Instructions

{instruction_text}

## Skills

{skill_lines}

## Persistence Contract

- Save durable state in Engel AI Main memory or registry files.
- Record changed files and receipt paths.
- Do not expose or copy secrets.
"""


def _load_skill_registry() -> dict[str, Any]:
    raw = _load_json(SKILL_REGISTRY_PATH)
    skills = raw.get("skills") if isinstance(raw.get("skills"), dict) else {}
    return {
        "schema": "engel_saved_skill_registry_v1",
        "root": str(ROOT),
        "primarySkillsRoot": str(PRIMARY_SKILLS_ROOT),
        "managedSkillsRoot": str(MANAGED_SKILLS_ROOT),
        "skills": dict(skills),
        "updated_at_utc": str(raw.get("updated_at_utc") or ""),
    }


def _load_agent_registry() -> dict[str, Any]:
    raw = _load_json(AGENT_REGISTRY_PATH)
    agents = raw.get("agents") if isinstance(raw.get("agents"), dict) else {}
    return {
        "schema": "engel_saved_agent_registry_v1",
        "root": str(ROOT),
        "agentsRoot": str(AGENTS_ROOT),
        "agents": dict(agents),
        "updated_at_utc": str(raw.get("updated_at_utc") or ""),
    }


def _save_skill_registry(registry: dict[str, Any]) -> None:
    registry["updated_at_utc"] = _iso_now()
    _write_json(SKILL_REGISTRY_PATH, registry)


def _save_agent_registry(registry: dict[str, Any]) -> None:
    registry["updated_at_utc"] = _iso_now()
    _write_json(AGENT_REGISTRY_PATH, registry)


def _parse_frontmatter(path: Path) -> dict[str, str]:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except Exception:
        return {}
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    meta: dict[str, str] = {}
    for line in text[3:end].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        clean = value.strip().strip("'\"")
        meta[key.strip()] = clean
    return meta


def create_skill(
    *,
    name: str,
    description: str = "",
    instructions: str = "",
    trigger_phrases: list[str] | None = None,
    slug: str | None = None,
    created_by: str = "engel-ai-main-server",
) -> dict[str, Any]:
    clean_name = _clean_text(name, 180)
    if not clean_name:
        raise EngelSkillAgentCreatorError("skill name is required")
    clean_description = _clean_text(description or f"{clean_name} saved Engel AI Main skill.", 4000)
    clean_instructions = _clean_text(instructions, 16000)
    clean_triggers = [_clean_text(item, 500) for item in (trigger_phrases or []) if _clean_text(item, 500)]
    skill_key = slugify(slug or clean_name, "engel-skill")
    now = _iso_now()
    registry = _load_skill_registry()
    previous = registry["skills"].get(skill_key) if isinstance(registry["skills"].get(skill_key), dict) else {}
    created_at = str(previous.get("created_at_utc") or now)
    markdown = _skill_markdown(
        slug=skill_key,
        name=clean_name,
        description=clean_description,
        instructions=clean_instructions,
        trigger_phrases=clean_triggers,
        created_at=created_at,
        updated_at=now,
    )
    written_files: list[str] = []
    previous_sha256 = ""
    for root in SKILL_ROOTS:
        base_dir = _safe_path(root / skill_key)
        skill_path = base_dir / "SKILL.md"
        if not previous_sha256 and skill_path.is_file():
            try:
                previous_sha256 = hashlib.sha256(skill_path.read_bytes()).hexdigest()
            except Exception:
                previous_sha256 = ""
        _write_text(skill_path, markdown)
        _write_json(
            base_dir / "skill.json",
            {
                "schema": "engel_saved_skill_manifest_v1",
                "skillKey": skill_key,
                "name": clean_name,
                "description": clean_description,
                "source": "engel-ai-main-server",
                "created_at_utc": created_at,
                "updated_at_utc": now,
                "created_by": created_by,
                "skill_md_sha256": _sha256_text(markdown),
            },
        )
        written_files.extend([str(skill_path), str(base_dir / "skill.json")])
    primary_dir = PRIMARY_SKILLS_ROOT / skill_key
    primary_file = primary_dir / "SKILL.md"
    entry = _default_skill_entry(
        name=clean_name,
        description=clean_description,
        slug=skill_key,
        source="engel-ai-main-server",
        base_dir=primary_dir,
        file_path=primary_file,
        created_at=created_at,
        updated_at=now,
    )
    entry.update(
        {
            "instructions_preview": _clip(clean_instructions, 700),
            "trigger_phrases": clean_triggers,
            "mirrors": [str(MANAGED_SKILLS_ROOT / skill_key / "SKILL.md")],
            "created_by": created_by,
            "skill_md_sha256": _sha256_text(markdown),
            "previous_skill_md_sha256": previous_sha256,
            "project_path": _project_path(primary_file),
        }
    )
    registry["skills"][skill_key] = entry
    _save_skill_registry(registry)
    receipt = {
        "schema": "engel_skill_creation_receipt_v1",
        "ok": True,
        "status": "saved skill",
        "skillKey": skill_key,
        "name": clean_name,
        "created_new": not bool(previous),
        "updated_at_utc": now,
        "written_files": written_files,
        "registry_path": str(SKILL_REGISTRY_PATH),
        "entry": entry,
    }
    receipt_path = RECEIPT_ROOT / f"ENGEL_SKILL_CREATED_{skill_key}_{_stamp()}.json"
    receipt["receipt_path"] = str(receipt_path)
    _write_json(receipt_path, receipt)
    _append_jsonl(MEMORY_SKILLS_ROOT / "ENGEL_SKILL_CREATION_EVENTS.jsonl", receipt)
    return receipt


def create_agent(
    *,
    name: str,
    role: str = "",
    instructions: str = "",
    skills: list[str] | None = None,
    slug: str | None = None,
    created_by: str = "engel-ai-main-server",
) -> dict[str, Any]:
    clean_name = _clean_text(name, 180)
    if not clean_name:
        raise EngelSkillAgentCreatorError("agent name is required")
    agent_key = slugify(slug or clean_name, "engel-agent")
    clean_role = _clean_text(role or f"{clean_name} Engel AI Main agent.", 1000)
    clean_instructions = _clean_text(instructions, 16000)
    clean_skills = [slugify(item, "skill") for item in (skills or []) if _clean_text(item, 200)]
    now = _iso_now()
    registry = _load_agent_registry()
    previous = registry["agents"].get(agent_key) if isinstance(registry["agents"].get(agent_key), dict) else {}
    created_at = str(previous.get("created_at_utc") or now)
    markdown = _agent_markdown(
        name=clean_name,
        slug=agent_key,
        role=clean_role,
        instructions=clean_instructions,
        skills=clean_skills,
        created_at=created_at,
        updated_at=now,
    )
    agent_path = _safe_path(AGENTS_ROOT / f"{agent_key}.md")
    previous_sha256 = ""
    if agent_path.is_file():
        try:
            previous_sha256 = hashlib.sha256(agent_path.read_bytes()).hexdigest()
        except Exception:
            previous_sha256 = ""
    _write_text(agent_path, markdown)
    definition_path = MEMORY_AGENTS_ROOT / "definitions" / f"{agent_key}.json"
    entry = {
        "agentKey": agent_key,
        "slug": agent_key,
        "name": clean_name,
        "role": clean_role,
        "instructions_preview": _clip(clean_instructions, 700),
        "skills": clean_skills,
        "source": "engel-ai-main-server",
        "created_by": created_by,
        "created_at_utc": created_at,
        "updated_at_utc": now,
        "filePath": str(agent_path),
        "definitionPath": str(definition_path),
        "agent_md_sha256": _sha256_text(markdown),
        "previous_agent_md_sha256": previous_sha256,
    }
    _write_json(definition_path, {"schema": "engel_saved_agent_definition_v1", **entry, "instructions": clean_instructions})
    registry["agents"][agent_key] = entry
    _save_agent_registry(registry)
    receipt = {
        "schema": "engel_agent_creation_receipt_v1",
        "ok": True,
        "status": "saved agent",
        "agentKey": agent_key,
        "name": clean_name,
        "created_new": not bool(previous),
        "updated_at_utc": now,
        "written_files": [str(agent_path), str(definition_path)],
        "registry_path": str(AGENT_REGISTRY_PATH),
        "entry": entry,
    }
    receipt_path = RECEIPT_ROOT / f"ENGEL_AGENT_CREATED_{agent_key}_{_stamp()}.json"
    receipt["receipt_path"] = str(receipt_path)
    _write_json(receipt_path, receipt)
    _append_jsonl(MEMORY_AGENTS_ROOT / "ENGEL_AGENT_CREATION_EVENTS.jsonl", receipt)
    return receipt


def _skill_entry_from_file(base_dir: Path, source: str) -> dict[str, Any]:
    skill_path = base_dir / "SKILL.md"
    meta = _parse_frontmatter(skill_path)
    key = base_dir.name
    name = meta.get("name") or key
    description = meta.get("description") or f"{name} skill."
    return _default_skill_entry(
        name=name,
        description=description,
        slug=key,
        source=source,
        base_dir=base_dir,
        file_path=skill_path,
        created_at=meta.get("created_at_utc") or "",
        updated_at=meta.get("updated_at_utc") or "",
        always=True,
    )


def list_saved_skills() -> list[dict[str, Any]]:
    registry = _load_skill_registry()
    merged: dict[str, dict[str, Any]] = {}
    for key, value in registry.get("skills", {}).items():
        if isinstance(value, dict):
            merged[str(key)] = dict(value)
    for root, source in ((PRIMARY_SKILLS_ROOT, "engel-ai-main-server"), (MANAGED_SKILLS_ROOT, "openengel-managed")):
        if not root.is_dir():
            continue
        for child in sorted(root.iterdir(), key=lambda item: item.name.casefold()):
            if not child.is_dir() or not (child / "SKILL.md").is_file():
                continue
            entry = _skill_entry_from_file(child, source)
            current = merged.get(entry["skillKey"], {})
            entry.update(current)
            merged[entry["skillKey"]] = entry
    return sorted(merged.values(), key=lambda item: str(item.get("skillKey") or "").casefold())


def list_saved_agents() -> list[dict[str, Any]]:
    registry = _load_agent_registry()
    merged: dict[str, dict[str, Any]] = {}
    for key, value in registry.get("agents", {}).items():
        if isinstance(value, dict):
            merged[str(key)] = dict(value)
    if AGENTS_ROOT.is_dir():
        for path in sorted(AGENTS_ROOT.glob("*.md"), key=lambda item: item.name.casefold()):
            key = path.stem
            merged.setdefault(
                key,
                {
                    "agentKey": key,
                    "slug": key,
                    "name": path.stem.replace("-", " ").title(),
                    "role": "Engel AI Main agent.",
                    "skills": [],
                    "source": "engel-ai-main-server",
                    "filePath": str(path),
                },
            )
    return sorted(merged.values(), key=lambda item: str(item.get("agentKey") or "").casefold())


def skill_status_report() -> dict[str, Any]:
    return {
        "schema": "engel_skill_status_report_v1",
        "ok": True,
        "workspaceDir": str(ROOT),
        "managedSkillsDir": str(MANAGED_SKILLS_ROOT),
        "skills": list_saved_skills(),
        "updated_at_utc": _iso_now(),
    }


def agent_status_report() -> dict[str, Any]:
    return {
        "schema": "engel_agent_status_report_v1",
        "ok": True,
        "workspaceDir": str(ROOT),
        "agentsRoot": str(AGENTS_ROOT),
        "agents": list_saved_agents(),
        "updated_at_utc": _iso_now(),
    }


def creator_status() -> dict[str, Any]:
    return {
        "schema": "engel_skill_agent_creator_status_v1",
        "ok": True,
        "root": str(ROOT),
        "primarySkillsRoot": str(PRIMARY_SKILLS_ROOT),
        "managedSkillsRoot": str(MANAGED_SKILLS_ROOT),
        "agentsRoot": str(AGENTS_ROOT),
        "skillRegistryPath": str(SKILL_REGISTRY_PATH),
        "agentRegistryPath": str(AGENT_REGISTRY_PATH),
        "savedSkillCount": len(list_saved_skills()),
        "savedAgentCount": len(list_saved_agents()),
        "updated_at_utc": _iso_now(),
    }


def _extract_name(kind: str, prompt: str) -> str:
    patterns = [
        rf"\b{kind}\s+(?:called|named|as|name)\s+['\"]([^'\"]+)['\"]",
        rf"\b{kind}\s+(?:called|named|as|name)\s+([^.;\n]+)",
        rf"\bcreate\s+(?:a\s+|an\s+)?{kind}\s+['\"]([^'\"]+)['\"]",
        rf"['\"]([^'\"]+)['\"]",
    ]
    for pattern in patterns:
        match = re.search(pattern, prompt, flags=re.IGNORECASE)
        if match:
            candidate = _clean_text(match.group(1), 120)
            candidate = re.split(r"\b(?:that|to|for|with|and)\b", candidate, maxsplit=1, flags=re.IGNORECASE)[0].strip()
            if candidate:
                return candidate
    return "Engel Saved Skill" if kind == "skill" else "Engel Saved Agent"


def prompt_requests_creation(prompt: str) -> bool:
    low = prompt.casefold()
    if not any(word in low for word in CREATE_WORDS):
        return False
    return "skill" in low or "agent" in low


def handle_creation_prompt(prompt: str, *, created_by: str = "engel-ai-main-chat") -> dict[str, Any]:
    clean_prompt = _clean_text(prompt, 12000)
    if not prompt_requests_creation(clean_prompt):
        return {"ok": False, "handled": False, "status": "prompt did not request skill or agent creation"}
    low = clean_prompt.casefold()
    results: list[dict[str, Any]] = []
    if "skill" in low:
        name = _extract_name("skill", clean_prompt)
        results.append(
            create_skill(
                name=name,
                description=f"Created from Engel AI Main chat request: {_clip(clean_prompt, 900)}",
                instructions=clean_prompt,
                trigger_phrases=[f"Use when the user asks for {name}.", f"Use when Engel AI Main needs {name}."],
                created_by=created_by,
            )
        )
    if "agent" in low:
        name = _extract_name("agent", clean_prompt)
        skills = [str(result.get("skillKey")) for result in results if result.get("skillKey")]
        results.append(
            create_agent(
                name=name,
                role=f"Agent created from Engel AI Main chat request: {_clip(clean_prompt, 500)}",
                instructions=clean_prompt,
                skills=skills,
                created_by=created_by,
            )
        )
    labels = []
    for result in results:
        if result.get("skillKey"):
            labels.append(f"skill {result['skillKey']} -> {result['entry']['filePath']}")
        if result.get("agentKey"):
            labels.append(f"agent {result['agentKey']} -> {result['entry']['filePath']}")
    return {
        "ok": True,
        "handled": True,
        "schema": "engel_skill_agent_creation_prompt_result_v1",
        "status": "saved requested skill/agent",
        "prompt_sha256": hashlib.sha256(clean_prompt.encode("utf-8")).hexdigest(),
        "results": results,
        "reply": "Saved " + "; ".join(labels) + ". Registries and persistent creation events were updated.",
        "updated_at_utc": _iso_now(),
    }


def _self_test() -> dict[str, Any]:
    skill = create_skill(
        name="Engel Skill Creator Self Test",
        description="Verifies Engel AI Main can create and save a skill.",
        instructions="Create the skill, write SKILL.md, update registries, and return a receipt.",
        created_by="engel_skill_agent_creator_self_test",
    )
    agent = create_agent(
        name="Engel Skill Creator Self Test Agent",
        role="Verifies Engel AI Main can create and save an agent.",
        skills=[str(skill["skillKey"])],
        created_by="engel_skill_agent_creator_self_test",
    )
    return {
        "ok": True,
        "skill": skill,
        "agent": agent,
        "status": creator_status(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Create and save Engel AI Main skills and agents.")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--create-skill", action="store_true")
    parser.add_argument("--create-agent", action="store_true")
    parser.add_argument("--name", default="")
    parser.add_argument("--description", default="")
    parser.add_argument("--role", default="")
    parser.add_argument("--instructions", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        result = _self_test()
    elif args.create_skill:
        result = create_skill(name=args.name, description=args.description, instructions=args.instructions)
    elif args.create_agent:
        result = create_agent(name=args.name, role=args.role, instructions=args.instructions)
    else:
        result = creator_status()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
