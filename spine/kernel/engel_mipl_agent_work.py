"""Bounded MIPL agent, task, and skill work packages for Engel AI Main.

This module closes the seam between Engel's high-level skill vocabulary and
the authored-agent runtime.  A work package has one agent, one task, one or
more catalogued skills, and one MIPL packet stream that proves the binding.

Safety boundaries:

* preview performs no write;
* create writes a draft agent and an assigned-draft task, but never runs it;
* activation is a separate named-operator step;
* operator-gated skill tools remain unavailable until a named operator grants
  them with a reason;
* a run is one bounded local authored-agent session, never a background loop;
* MIPL remains non-authorizing and every transition is receipted.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping


ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
TOOLS = ROOT / "tools"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import engel_mipl as mipl  # noqa: E402
import engel_agent_author as author  # noqa: E402
import engel_agent_runner as runner  # noqa: E402


TASK_SCHEMA = "engel_authored_agent_task_v1"
EVENT_SCHEMA = "engel_mipl_agent_work_event_v1"
RECEIPT_DIR = ROOT / "reports" / "mipl_agent_work"
MAX_TASKS = 500
DEFAULT_SKILLS = ("repository_research", "reporting")
TASK_STATES = (
    "assigned_draft",
    "ready_read_only",
    "ready",
    "review_required",
    "run_failed",
    "completed",
    "retired",
)


class AgentWorkError(ValueError):
    """Raised when an agent work package or transition is inadmissible."""


@dataclass(frozen=True)
class SkillSpec:
    skill_id: str
    name: str
    description: str
    tools: tuple[str, ...]
    gated_tools: tuple[str, ...] = ()

    def packet(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "tools": list(self.tools + self.gated_tools),
            "requires_action_grant": bool(self.gated_tools),
        }


# Compact capability truth for authored agents.  These are deliberately based
# on tools the current authored-agent runtime actually knows; a skill name may
# not claim a capability for which no tool contract exists.
SKILL_CATALOG: dict[str, SkillSpec] = {
    "repository_research": SkillSpec(
        "repository_research",
        "Repository research",
        "Read and search workspace evidence without changing it.",
        ("read_files", "search_repo", "summarize"),
    ),
    "summarization": SkillSpec(
        "summarization",
        "Summarization",
        "Condense supplied evidence while preserving failures and uncertainty.",
        ("summarize",),
    ),
    "reporting": SkillSpec(
        "reporting",
        "Evidence reporting",
        "Draft a reviewable report from cited evidence.",
        ("draft_report",),
    ),
    "conversation": SkillSpec(
        "conversation",
        "Operator conversation",
        "Return a bounded, direct response to the operator.",
        ("chat_reply",),
    ),
    "reasoned_analysis": SkillSpec(
        "reasoned_analysis",
        "Reasoned analysis",
        "Analyze supplied evidence and return a bounded explanation for review.",
        ("read_files", "summarize", "chat_reply"),
    ),
    "implementation_planning": SkillSpec(
        "implementation_planning",
        "Implementation planning",
        "Inspect code and draft a bounded implementation plan or candidate report.",
        ("read_files", "search_repo", "summarize", "draft_report"),
    ),
    "coordination": SkillSpec(
        "coordination",
        "Agent coordination",
        "Coordinate evidence and handoffs without silently dispatching other workers.",
        ("read_files", "search_repo", "summarize", "chat_reply"),
    ),
    "verification": SkillSpec(
        "verification",
        "Verification",
        "Inspect proof and, after an operator grant, run a named verifier.",
        ("read_files", "search_repo", "summarize"),
        ("run_verifier",),
    ),
    "capability_evaluation": SkillSpec(
        "capability_evaluation",
        "Capability evaluation",
        "Review capability evidence and run the evaluation harness after a grant.",
        ("read_files", "summarize"),
        ("capability_eval",),
    ),
    "curriculum_design": SkillSpec(
        "curriculum_design",
        "Curriculum design",
        "Review training evidence and propose curriculum only after a grant.",
        ("read_files", "draft_report"),
        ("propose_curriculum",),
    ),
}

_NORMAL = re.compile(r"[^a-z0-9]+")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize(value: Any) -> str:
    return _NORMAL.sub("_", str(value or "").strip().casefold()).strip("_")


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _hash(value: Any) -> str:
    data = value if isinstance(value, bytes) else _canonical(value)
    return hashlib.sha256(data).hexdigest()


def resolve_skill(ref: Any) -> SkillSpec:
    """Resolve a canonical id, display name, or Meeting Room-style label."""
    normalized = _normalize(ref)
    if normalized in SKILL_CATALOG:
        return SKILL_CATALOG[normalized]
    for spec in SKILL_CATALOG.values():
        if normalized == _normalize(spec.name):
            return spec

    # Meeting Room owns a large domain-specific label roster.  This bridge
    # maps those labels onto the smaller set of capabilities the authored
    # runtime can genuinely enforce.
    keyword_routes: tuple[tuple[tuple[str, ...], str], ...] = (
        (
            (
                "verification",
                "verify",
                "audit",
                "testing",
                "static_analysis",
                "safety",
                "failure_triage",
            ),
            "verification",
        ),
        (("capability", "evaluation", "benchmark"), "capability_evaluation"),
        (("curriculum", "training"), "curriculum_design"),
        (("report", "storytelling"), "reporting"),
        (("summar",), "summarization"),
        (
            ("orchestration", "worker", "bridge", "agent", "agency", "dispatch"),
            "coordination",
        ),
        (
            (
                "coding",
                "code",
                "architect",
                "design",
                "ui",
                "engineering",
                "patch",
                "python",
                "sqlite",
                "packaging",
                "development",
                "file_structure",
                "game_art",
                "mobile_web",
                "qt",
                "wsl",
                "runtime",
                "custom",
                "factory_refinement",
            ),
            "implementation_planning",
        ),
        (
            (
                "math",
                "portfolio",
                "quant",
                "graph",
                "visualization",
                "llm",
                "logic_reasoning",
                "financial_strategy",
                "news_correlation",
            ),
            "reasoned_analysis",
        ),
        (
            (
                "research",
                "reference",
                "memory",
                "history",
                "historical",
                "analysis",
                "economics",
                "finance",
                "market",
                "literature",
                "intelligence",
                "manuals",
                "receipts",
                "rag",
                "offline_docs",
            ),
            "repository_research",
        ),
        (("conversation", "chat", "prompt"), "conversation"),
    )
    for keywords, skill_id in keyword_routes:
        if any(keyword in normalized for keyword in keywords):
            return SKILL_CATALOG[skill_id]
    raise AgentWorkError(
        f"unknown skill {ref!r}; choose one of: {', '.join(SKILL_CATALOG)}"
    )


def resolve_skills(refs: Iterable[Any]) -> list[SkillSpec]:
    if isinstance(refs, str):
        refs = [refs]
    result: list[SkillSpec] = []
    for ref in list(refs)[: mipl.MAX_SKILLS_PER_TASK]:
        spec = resolve_skill(ref)
        if spec.skill_id not in {item.skill_id for item in result}:
            result.append(spec)
    if not result:
        result = [SKILL_CATALOG[skill] for skill in DEFAULT_SKILLS]
    return result


def _tool_binding(skills: Iterable[SkillSpec]) -> tuple[list[str], list[str]]:
    safe: list[str] = []
    pending: list[str] = []
    for skill in skills:
        for tool in skill.tools:
            if tool not in safe:
                safe.append(tool)
        for tool in skill.gated_tools:
            if tool not in pending:
                pending.append(tool)
    # The catalog itself must never drift beyond the authoring allowlist.
    unknown = (set(safe) | set(pending)) - set(author.KNOWN_TOOLS)
    if unknown:
        raise AgentWorkError(f"skill catalog references unknown tools: {sorted(unknown)}")
    if set(pending) - set(author.PRIVILEGED_TOOLS):
        raise AgentWorkError("skill catalog marks a non-privileged tool as operator-gated")
    return safe, pending


def _clean_task(value: Any) -> str:
    text = " ".join(str(value or "").split())
    if len(text) < 12:
        raise AgentWorkError("task must describe a concrete result in at least 12 characters")
    if len(text) > mipl.MAX_TASK_CHARS:
        raise AgentWorkError(f"task exceeds the MIPL bound of {mipl.MAX_TASK_CHARS} characters")
    return text


def _clean_items(values: Iterable[Any], *, limit: int, item_limit: int) -> list[str]:
    if isinstance(values, str):
        values = [values]
    result: list[str] = []
    for raw in list(values)[:limit]:
        text = " ".join(str(raw or "").split())
        if not text:
            continue
        if len(text) > item_limit:
            raise AgentWorkError(f"item exceeds its {item_limit}-character MIPL bound")
        if text not in result:
            result.append(text)
    return result


def _task_id(agent_id: str, task: str, created: str) -> str:
    digest = _hash(f"{agent_id}|{task}|{created}".encode("utf-8"))[:12]
    return f"engel_task_{digest}"


def _load_registry(path: Path) -> dict[str, Any]:
    registry = author.load_registry(path)
    registry.setdefault("agents", [])
    registry.setdefault("tasks", [])
    if not isinstance(registry["tasks"], list):
        raise AgentWorkError("agent registry tasks field is not a list")
    return registry


def _atomic_save_registry(registry: dict[str, Any], path: Path) -> None:
    registry["schema"] = author.SCHEMA
    registry["updated_at_utc"] = _utc_now()
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        prefix=path.name + ".",
        suffix=".tmp",
        dir=path.parent,
        delete=False,
    )
    temp_path = Path(handle.name)
    try:
        with handle:
            json.dump(registry, handle, indent=2, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _write_event(event: str, agent: Mapping[str, Any], task: Mapping[str, Any]) -> Path:
    RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    payload = {
        "schema": EVENT_SCHEMA,
        "event": event,
        "at_utc": _utc_now(),
        "agent_id": agent.get("agent_id"),
        "agent_name": agent.get("name"),
        "task_id": task.get("task_id"),
        "task_status": task.get("status"),
        "skill_ids": list(task.get("skill_ids") or []),
        "mipl_sha256": task.get("mipl_sha256"),
        "execution_authorized_by_mipl": False,
    }
    path = RECEIPT_DIR / f"ENGEL_MIPL_AGENT_WORK_{event.upper()}_{stamp}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    (RECEIPT_DIR / "LATEST.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return path


def _build_work_package(
    *,
    name: str,
    task: str,
    skill_refs: Iterable[Any],
    purpose: str = "",
    direction: str = "",
    completion: Iterable[Any] = (),
    criteria: Iterable[Any] = (),
    max_turns: int = 6,
    authored_by: str = "engel_ai_main",
    registry: dict[str, Any],
) -> dict[str, Any]:
    clean_task = _clean_task(task)
    skills = resolve_skills(skill_refs)
    safe_tools, pending_tools = _tool_binding(skills)
    clean_purpose = " ".join(str(purpose or "").split()) or (
        "Complete the assigned Engel task with explicit skill and evidence bounds"
    )
    clean_direction = " ".join(str(direction or "").split()) or (
        "Work only on the assigned task. Use only the skills and tools in this record, "
        "preserve failures, return evidence for operator review, and stop after one "
        "bounded result. Do not claim completion from your own assertion."
    )
    agent = author.author_agent(
        name,
        clean_purpose,
        clean_direction,
        tools=safe_tools,
        allow_actions=False,
        max_turns=max_turns,
        authored_by=authored_by,
        registry=registry,
    )
    agent["skills"] = [skill.skill_id for skill in skills]
    agent["pending_tools"] = pending_tools
    agent["history"].append(
        {
            "at_utc": _utc_now(),
            "event": "mipl_skills_bound",
            "by": authored_by,
            "skills": list(agent["skills"]),
            "ready_tools": list(safe_tools),
            "pending_operator_tools": list(pending_tools),
        }
    )

    created = _utc_now()
    task_id = _task_id(str(agent["agent_id"]), clean_task, created)
    completion_values = _clean_items(
        completion,
        limit=mipl.MAX_COMPLETION_CRITERIA,
        item_limit=500,
    ) or ["Return evidence or an explicit failure for operator review"]
    criteria_values = _clean_items(criteria, limit=mipl.MAX_CRITERIA, item_limit=800) or [
        "agent, task, and skill references match",
        "failures and proof return to HIPL comprehension",
    ]
    expression_hash = _hash(clean_task.encode("utf-8"))
    lifted_hash = _hash(
        {
            "objective": clean_task,
            "agent_id": agent["agent_id"],
            "skill_ids": agent["skills"],
            "completion": completion_values,
        }
    )
    ir = mipl.compile_agent_task_ir(
        expression_hash=expression_hash,
        lifted_intent_hash=lifted_hash,
        agent_id=agent["agent_id"],
        agent_name=agent["name"],
        agent_purpose=agent["purpose"],
        task_id=task_id,
        task_objective=clean_task,
        skills=[skill.packet() for skill in skills],
        criteria=criteria_values,
        completion=completion_values,
        max_turns=max_turns,
        lifecycle="draft",
    )
    task_row = {
        "schema": TASK_SCHEMA,
        "task_id": task_id,
        "agent_id": agent["agent_id"],
        "objective": clean_task,
        "skill_ids": list(agent["skills"]),
        "ready_tools": list(safe_tools),
        "pending_operator_tools": list(pending_tools),
        "completion_criteria": completion_values,
        "verification_criteria": criteria_values,
        "max_turns": max_turns,
        "status": "assigned_draft",
        "execution_authorized": False,
        "created_at_utc": created,
        "updated_at_utc": created,
        "mipl": ir,
        "mipl_sha256": ir["wire"]["sha256"],
        "history": [
            {
                "at_utc": created,
                "event": "assigned_as_draft",
                "by": authored_by,
                "note": "creation is not activation or execution",
            }
        ],
    }
    registry.setdefault("tasks", []).append(task_row)
    return {"agent": agent, "task": task_row, "mipl": ir}


def preview_work_package(**kwargs: Any) -> dict[str, Any]:
    """Build a work package in memory.  The caller's registry is not written."""
    registry_path = Path(kwargs.pop("registry_path", author.REGISTRY))
    registry = copy.deepcopy(_load_registry(registry_path))
    return _build_work_package(registry=registry, **kwargs)


def create_work_package(**kwargs: Any) -> dict[str, Any]:
    """Atomically persist one draft agent and its assigned draft task."""
    registry_path = Path(kwargs.pop("registry_path", author.REGISTRY))
    registry = _load_registry(registry_path)
    if len(registry["tasks"]) >= MAX_TASKS:
        raise AgentWorkError(
            f"agent task registry reached its {MAX_TASKS}-task bound; retire old tasks first"
        )
    package = _build_work_package(registry=registry, **kwargs)
    _atomic_save_registry(registry, registry_path)
    package["receipt_path"] = str(
        _write_event("created", package["agent"], package["task"])
    )
    return package


def find_task(registry: Mapping[str, Any], ref: Any) -> dict[str, Any]:
    needle = str(ref or "").strip().casefold()
    for task in registry.get("tasks", []):
        if isinstance(task, dict) and needle == str(task.get("task_id") or "").casefold():
            return task
    raise AgentWorkError(f"no authored-agent task matches {ref!r}")


def validate_task_binding(
    registry: Mapping[str, Any], task: Mapping[str, Any]
) -> dict[str, Any]:
    ir = task.get("mipl")
    validation = mipl.validate_ir(ir) if isinstance(ir, Mapping) else {"ok": False}
    if validation.get("ok") is not True:
        raise AgentWorkError("task MIPL packet is missing, tampered, or invalid")
    records = mipl.packet_records(ir)
    agent_packet = next(row["args"] for row in records if row["opcode"] == "AGENT")
    task_packet = next(row["args"] for row in records if row["opcode"] == "TASK")
    assign_packet = next(row["args"] for row in records if row["opcode"] == "ASSIGN")
    agent = author.find_agent(dict(registry), str(task.get("agent_id") or ""))
    expected_skills = list(task.get("skill_ids") or [])
    if not (
        agent_packet.get("agent_id") == agent.get("agent_id") == task.get("agent_id")
        and task_packet.get("task_id") == task.get("task_id")
        and assign_packet.get("task_id") == task.get("task_id")
        and assign_packet.get("agent_id") == agent.get("agent_id")
        and assign_packet.get("skills") == expected_skills == list(agent.get("skills") or [])
        and task.get("mipl_sha256") == ir.get("wire", {}).get("sha256")
    ):
        raise AgentWorkError("agent, task, skill, or MIPL references no longer match")
    return agent


def _named_operator(value: Any, action: str) -> str:
    operator = " ".join(str(value or "").split())
    if not operator or operator.casefold() == "engel_ai_main":
        raise AgentWorkError(f"{action} requires a named human operator")
    return operator


def activate_task(
    task_ref: Any,
    *,
    approved_by: Any,
    registry_path: Path = author.REGISTRY,
) -> dict[str, Any]:
    """Activate the assigned agent; this still does not run the task."""
    operator = _named_operator(approved_by, "activation")
    registry = _load_registry(Path(registry_path))
    task = find_task(registry, task_ref)
    agent = validate_task_binding(registry, task)
    if task.get("status") not in {"assigned_draft", "run_failed", "review_required"}:
        raise AgentWorkError(f"task cannot activate from state {task.get('status')!r}")
    author.set_status(registry, str(agent["agent_id"]), "active", by=operator)
    task["status"] = "ready_read_only" if task.get("pending_operator_tools") else "ready"
    task["execution_authorized"] = True
    task["activated_by"] = operator
    task["updated_at_utc"] = _utc_now()
    task["history"].append(
        {
            "at_utc": task["updated_at_utc"],
            "event": "activated",
            "by": operator,
            "note": "activation permits a bounded run; MIPL itself granted nothing",
        }
    )
    _atomic_save_registry(registry, Path(registry_path))
    receipt = _write_event("activated", agent, task)
    return {"agent": agent, "task": task, "receipt_path": str(receipt)}


def grant_task_actions(
    task_ref: Any,
    *,
    granted_by: Any,
    reason: Any,
    registry_path: Path = author.REGISTRY,
) -> dict[str, Any]:
    """Enable only the privileged tools already requested by bound skills."""
    operator = _named_operator(granted_by, "action grant")
    why = " ".join(str(reason or "").split())
    registry = _load_registry(Path(registry_path))
    task = find_task(registry, task_ref)
    agent = validate_task_binding(registry, task)
    author.grant_actions(
        registry,
        str(agent["agent_id"]),
        granted_by=operator,
        reason=why,
    )
    task["pending_operator_tools"] = []
    task["ready_tools"] = list(agent.get("tools") or [])
    if task.get("execution_authorized"):
        task["status"] = "ready"
    task["updated_at_utc"] = _utc_now()
    task["history"].append(
        {
            "at_utc": task["updated_at_utc"],
            "event": "skill_tools_granted",
            "by": operator,
            "reason": why,
            "tools": list(agent.get("tools") or []),
        }
    )
    _atomic_save_registry(registry, Path(registry_path))
    receipt = _write_event("granted", agent, task)
    return {"agent": agent, "task": task, "receipt_path": str(receipt)}


def run_task(
    task_ref: Any,
    *,
    approved_by: Any,
    reply_source: Callable[[str], str] | None = None,
    registry_path: Path = author.REGISTRY,
    timeout: int = 180,
) -> dict[str, Any]:
    """Run one active assignment once, returning it for operator review."""
    operator = _named_operator(approved_by, "task run")
    registry = _load_registry(Path(registry_path))
    task = find_task(registry, task_ref)
    agent = validate_task_binding(registry, task)
    if not task.get("execution_authorized") or agent.get("status") != "active":
        raise AgentWorkError("task is not activated; activation is a separate operator step")
    if task.get("status") not in {"ready", "ready_read_only", "review_required", "run_failed"}:
        raise AgentWorkError(f"task cannot run from state {task.get('status')!r}")
    source = reply_source or (lambda prompt: runner._http_reply(prompt, timeout))
    task_prompt = "\n".join(
        (
            f"Assigned task: {task['objective']}",
            "Bound skills: " + ", ".join(task.get("skill_ids") or []),
            "Completion evidence expected:",
            *[f"- {item}" for item in task.get("completion_criteria") or []],
            "Return a candidate result for operator review. Your reply does not mark the task complete.",
        )
    )
    run_receipt = runner.run_agent(
        agent,
        task_prompt,
        reply_source=source,
        max_turns=min(int(task.get("max_turns") or 1), 25),
    )
    run_path = runner.write_receipt(run_receipt)
    task["status"] = "review_required" if run_receipt.get("ok") else "run_failed"
    task["updated_at_utc"] = _utc_now()
    task["last_run_receipt"] = str(run_path)
    task["history"].append(
        {
            "at_utc": task["updated_at_utc"],
            "event": "bounded_run_returned" if run_receipt.get("ok") else "bounded_run_failed",
            "by": operator,
            "run_receipt": str(run_path),
            "note": "model output requires operator review; it is not completion proof",
        }
    )
    _atomic_save_registry(registry, Path(registry_path))
    event_path = _write_event("run_returned", agent, task)
    return {
        "agent": agent,
        "task": task,
        "run_receipt": run_receipt,
        "run_receipt_path": str(run_path),
        "event_receipt_path": str(event_path),
    }


def registry_status(registry_path: Path = author.REGISTRY) -> dict[str, Any]:
    registry = _load_registry(Path(registry_path))
    tasks = [task for task in registry.get("tasks", []) if isinstance(task, dict)]
    states = {state: 0 for state in TASK_STATES}
    for task in tasks:
        states[str(task.get("status") or "unknown")] = states.get(
            str(task.get("status") or "unknown"), 0
        ) + 1
    valid = 0
    invalid = 0
    for task in tasks:
        try:
            validate_task_binding(registry, task)
            valid += 1
        except (AgentWorkError, author.AgentAuthorError, mipl.MiplError):
            invalid += 1
    return {
        "schema": author.SCHEMA,
        "registry": str(registry_path),
        "agents": len(registry.get("agents", [])),
        "tasks": len(tasks),
        "valid_bindings": valid,
        "invalid_bindings": invalid,
        "task_states": states,
        "skill_catalog": len(SKILL_CATALOG),
        "mipl_profile": mipl.PROFILE,
        "execution_authorized_by_mipl": False,
    }


def _summary(package: Mapping[str, Any], *, preview: bool = False) -> dict[str, Any]:
    agent = package.get("agent") or {}
    task = package.get("task") or {}
    ir = package.get("mipl") or task.get("mipl") or {}
    return {
        "ok": True,
        "preview": preview,
        "agent_id": agent.get("agent_id"),
        "agent_name": agent.get("name"),
        "agent_status": agent.get("status"),
        "task_id": task.get("task_id"),
        "task_status": task.get("status"),
        "skill_ids": task.get("skill_ids"),
        "ready_tools": task.get("ready_tools"),
        "pending_operator_tools": task.get("pending_operator_tools"),
        "mipl_packets": ir.get("wire", {}).get("packet_count"),
        "mipl_bytes": ir.get("wire", {}).get("encoded_bytes"),
        "mipl_sha256": ir.get("wire", {}).get("sha256"),
        "execution_authorized": task.get("execution_authorized", False),
        "receipt_path": package.get("receipt_path"),
    }


def render_docs(_payload: str = "") -> str:
    return "\n".join(
        (
            "Engel MIPL Agent Work",
            "",
            "One packet binds: AGENT + one or more SKILL packets + TASK + ASSIGN.",
            "Create always produces a draft agent and assigned-draft task; it does not run.",
            "Activation, operator-gated tools, and one bounded run are separate receipted steps.",
            "MIPL never grants execution authority.",
            "",
            "Chat examples:",
            'mipl agent preview {"name":"Review Agent","task":"Review the latest training receipts","skills":["repository_research","reporting"]}',
            'mipl agent create {"name":"Review Agent","task":"Review the latest training receipts","skills":["repository_research","reporting"]}',
            "mipl agent list",
            'mipl agent activate {"task_id":"engel_task_...","approved_by":"Joshua"}',
            'mipl agent run {"task_id":"engel_task_...","approved_by":"Joshua"}',
            "",
            f"Bounds: {mipl.MAX_SKILLS_PER_TASK} skills, 25 turns, {mipl.MAX_TASK_CHARS} task characters, {mipl.MAX_WIRE_BYTES} wire bytes.",
        )
    )


def render_skills(_payload: str = "") -> str:
    lines = ["Engel authored-agent skill catalog", ""]
    for spec in SKILL_CATALOG.values():
        gate = (
            " | operator-gated: " + ", ".join(spec.gated_tools)
            if spec.gated_tools
            else ""
        )
        lines.append(
            f"- {spec.skill_id} -- {spec.name}: {spec.description} "
            f"[ready: {', '.join(spec.tools) or 'none'}{gate}]"
        )
    return "\n".join(lines)


def render_status(_payload: str = "") -> str:
    return json.dumps(registry_status(), indent=2, ensure_ascii=False)


def render_list(_payload: str = "") -> str:
    registry = _load_registry(author.REGISTRY)
    tasks = [task for task in registry.get("tasks", []) if isinstance(task, dict)]
    if not tasks:
        return "No MIPL authored-agent tasks yet. Use `mipl agent preview` first."
    lines = [f"MIPL authored-agent tasks: {len(tasks)}", ""]
    for task in reversed(tasks[-20:]):
        try:
            agent = author.find_agent(registry, str(task.get("agent_id") or ""))
            agent_name = agent.get("name")
        except author.AgentAuthorError:
            agent_name = "missing agent"
        lines.append(
            f"- {task.get('task_id')} | {task.get('status')} | {agent_name} | "
            f"{', '.join(task.get('skill_ids') or [])} | {task.get('objective')}"
        )
    return "\n".join(lines)


def _json_tail(text: str, command: str) -> dict[str, Any]:
    tail = text[len(command) :].strip()
    if not tail:
        raise AgentWorkError(f"{command} needs one JSON object; see `mipl agent docs`")
    try:
        payload = json.loads(tail)
    except ValueError as exc:
        raise AgentWorkError(f"{command} JSON is invalid: {exc}") from exc
    if not isinstance(payload, dict):
        raise AgentWorkError(f"{command} payload must be a JSON object")
    return payload


def _package_args(payload: Mapping[str, Any]) -> dict[str, Any]:
    skills = payload.get("skills") or DEFAULT_SKILLS
    if isinstance(skills, str):
        skills = [part.strip() for part in skills.split(",") if part.strip()]
    return {
        "name": payload.get("name", ""),
        "task": payload.get("task", ""),
        "skill_refs": skills,
        "purpose": payload.get("purpose", ""),
        "direction": payload.get("direction", ""),
        "completion": payload.get("completion") or (),
        "criteria": payload.get("criteria") or (),
        "max_turns": int(payload.get("max_turns") or 6),
        "authored_by": payload.get("authored_by", "engel_ai_main"),
    }


def render_chat(text: str) -> str:
    clean = " ".join(str(text or "").strip().split())
    low = clean.casefold()
    if low in {"mipl agent", "mipl agent docs", "mipl agent help"}:
        return render_docs()
    if low == "mipl agent skills":
        return render_skills()
    if low == "mipl agent status":
        return render_status()
    if low in {"mipl agent list", "mipl agents list"}:
        return render_list()
    if low.startswith("mipl agent preview "):
        package = preview_work_package(**_package_args(_json_tail(clean, "mipl agent preview")))
        return json.dumps(_summary(package, preview=True), indent=2, ensure_ascii=False)
    if low.startswith("mipl agent create "):
        package = create_work_package(**_package_args(_json_tail(clean, "mipl agent create")))
        return json.dumps(_summary(package), indent=2, ensure_ascii=False)
    if low.startswith("mipl agent activate "):
        payload = _json_tail(clean, "mipl agent activate")
        package = activate_task(payload.get("task_id"), approved_by=payload.get("approved_by"))
        return json.dumps(_summary(package), indent=2, ensure_ascii=False)
    if low.startswith("mipl agent grant "):
        payload = _json_tail(clean, "mipl agent grant")
        package = grant_task_actions(
            payload.get("task_id"),
            granted_by=payload.get("granted_by"),
            reason=payload.get("reason"),
        )
        return json.dumps(_summary(package), indent=2, ensure_ascii=False)
    if low.startswith("mipl agent run "):
        payload = _json_tail(clean, "mipl agent run")
        result = run_task(
            payload.get("task_id"),
            approved_by=payload.get("approved_by"),
            timeout=int(payload.get("timeout") or 180),
        )
        summary = _summary(result)
        summary["run_ok"] = result["run_receipt"].get("ok")
        summary["run_receipt_path"] = result.get("run_receipt_path")
        return json.dumps(summary, indent=2, ensure_ascii=False)
    raise AgentWorkError("unknown MIPL agent command; use `mipl agent docs`")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("docs")
    sub.add_parser("skills")
    sub.add_parser("status")
    sub.add_parser("list")

    def package_parser(name: str) -> argparse.ArgumentParser:
        item = sub.add_parser(name)
        item.add_argument("--name", required=True)
        item.add_argument("--task", required=True)
        item.add_argument("--purpose", default="")
        item.add_argument("--direction", default="")
        item.add_argument("--skill", action="append", default=[])
        item.add_argument("--completion", action="append", default=[])
        item.add_argument("--criteria", action="append", default=[])
        item.add_argument("--max-turns", type=int, default=6)
        item.add_argument("--authored-by", default="engel_ai_main")
        item.add_argument("--summary", action="store_true")
        return item

    package_parser("preview")
    package_parser("create")
    activate = sub.add_parser("activate")
    activate.add_argument("--task-id", required=True)
    activate.add_argument("--approved-by", required=True)
    grant = sub.add_parser("grant")
    grant.add_argument("--task-id", required=True)
    grant.add_argument("--granted-by", required=True)
    grant.add_argument("--reason", required=True)
    run = sub.add_parser("run")
    run.add_argument("--task-id", required=True)
    run.add_argument("--approved-by", required=True)
    run.add_argument("--timeout", type=int, default=180)

    args = parser.parse_args(argv)
    try:
        if args.command == "docs":
            print(render_docs())
            return 0
        if args.command == "skills":
            print(render_skills())
            return 0
        if args.command == "status":
            print(render_status())
            return 0
        if args.command == "list":
            print(render_list())
            return 0
        if args.command in {"preview", "create"}:
            kwargs = {
                "name": args.name,
                "task": args.task,
                "skill_refs": args.skill or DEFAULT_SKILLS,
                "purpose": args.purpose,
                "direction": args.direction,
                "completion": args.completion,
                "criteria": args.criteria,
                "max_turns": args.max_turns,
                "authored_by": args.authored_by,
            }
            package = (
                preview_work_package(**kwargs)
                if args.command == "preview"
                else create_work_package(**kwargs)
            )
            print(
                json.dumps(
                    _summary(package, preview=args.command == "preview")
                    if args.summary
                    else package,
                    indent=2,
                    ensure_ascii=False,
                )
            )
            return 0
        if args.command == "activate":
            result = activate_task(args.task_id, approved_by=args.approved_by)
        elif args.command == "grant":
            result = grant_task_actions(
                args.task_id,
                granted_by=args.granted_by,
                reason=args.reason,
            )
        else:
            result = run_task(
                args.task_id,
                approved_by=args.approved_by,
                timeout=args.timeout,
            )
        print(json.dumps(_summary(result), indent=2, ensure_ascii=False))
        return 0
    except (AgentWorkError, author.AgentAuthorError, runner.AgentRunError, mipl.MiplError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
