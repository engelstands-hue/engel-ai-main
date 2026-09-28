"""Verify Engel's MIPL agent/task/skill work-package seam.

All stateful checks use a temporary registry and temporary receipt folders.  No
real agent is created, activated, granted, or run by this verifier, and the one
runner check uses an injected deterministic reply instead of a model or network.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import json
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(TOOLS))

import engel_ai_update_routes as routes  # noqa: E402
import engel_mipl as mipl  # noqa: E402
import engel_mipl_agent_work as work  # noqa: E402
import engel_agent_author as author  # noqa: E402
import engel_agent_runner as runner  # noqa: E402


checks: list[dict[str, object]] = []


def check(name: str, ok: bool, detail: str) -> None:
    checks.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": detail})


def refused(fn, *args, **kwargs) -> bool:
    try:
        fn(*args, **kwargs)
    except (work.AgentWorkError, author.AgentAuthorError, runner.AgentRunError, mipl.MiplError):
        return True
    except Exception:
        return False
    return False


HASH = hashlib.sha256(b"engel-mipl-agent-work").hexdigest()
SKILL_ROWS = [
    work.SKILL_CATALOG["repository_research"].packet(),
    work.SKILL_CATALOG["reporting"].packet(),
]
IR_ARGS = {
    "expression_hash": HASH,
    "lifted_intent_hash": HASH,
    "agent_id": "engel_agent_verifier",
    "agent_name": "Verifier Agent",
    "agent_purpose": "Review MIPL agent work evidence",
    "task_id": "engel_task_verifier",
    "task_objective": "Review the work packet and return its proof references.",
    "skills": SKILL_ROWS,
    "criteria": ["all references match", "failures return"],
    "completion": ["operator receives evidence"],
    "max_turns": 4,
}

# 1. Language packets are deterministic, bounded, and non-authorizing.
first = mipl.compile_agent_task_ir(**IR_ARGS)
second = mipl.compile_agent_task_ir(**IR_ARGS)
records = mipl.packet_records(first)
opcodes = [row["opcode"] for row in records]
check(
    "agent_task_compiler_is_deterministic",
    first == second and mipl.validate_ir(first)["ok"],
    "identical work contracts must compile to identical validated bytes",
)
check(
    "agent_task_packet_grammar_is_complete",
    opcodes
    == [
        "BEGIN",
        "INTENT",
        "BUDGET",
        "RESOLVE",
        "AGENT",
        "SKILL",
        "SKILL",
        "TASK",
        "ASSIGN",
        "GATE",
        "DISPATCH",
        "VERIFY",
        "RETURN",
        "END",
    ],
    "the stream must bind agent, every skill, task, assignment, gate, verifier, and return",
)
gate = next(row["args"] for row in records if row["opcode"] == "GATE")
dispatch = next(row["args"] for row in records if row["opcode"] == "DISPATCH")
check(
    "mipl_never_grants_execution",
    first["execution_authorized"] is False
    and gate == {"policy": "approval_and_governor", "failure": "closed"}
    and dispatch["authorization"] == "external_gate_required",
    "assignment packets must fail closed and defer authority to external gates",
)
profile = mipl.runtime_profile(first)
check(
    "agent_packet_stays_low_resource",
    profile["packet_count"] <= mipl.MAX_PACKETS
    and profile["encoded_bytes"] <= mipl.MAX_WIRE_BYTES
    and profile["model_required"] is False
    and profile["network_required"] is False,
    f"sample uses {profile['packet_count']} packets / {profile['encoded_bytes']} encoded bytes",
)
source = mipl.disassemble(first)
check(
    "agent_packet_source_round_trips",
    mipl.assemble(source)["wire"]["sha256"] == first["wire"]["sha256"],
    "MIPL/2 AGENT_TASK source must assemble without semantic drift",
)
tampered_ir = copy.deepcopy(first)
body = tampered_ir["wire"]["body"]
tampered_ir["wire"]["body"] = body[:-2] + ("AA" if body[-2:] != "AA" else "BB")
check(
    "tampered_agent_packet_is_refused",
    mipl.validate_ir(tampered_ir)["ok"] is False,
    "wire integrity must fail before any registry transition",
)

# 2. Every current Meeting Room skill label resolves onto an enforceable authored skill.
meeting_tree = ast.parse((ROOT / "engel_agent_meeting_room.py").read_text(encoding="utf-8-sig"))
meeting_skills: tuple[str, ...] = ()
for node in meeting_tree.body:
    if isinstance(node, ast.Assign) and any(
        isinstance(target, ast.Name) and target.id == "SKILL_TYPES" for target in node.targets
    ):
        meeting_skills = ast.literal_eval(node.value)
        break
unresolved = []
for label in meeting_skills:
    try:
        work.resolve_skill(label)
    except work.AgentWorkError:
        unresolved.append(label)
check(
    "meeting_room_skill_catalog_is_bridged",
    bool(meeting_skills) and not unresolved,
    f"resolved {len(meeting_skills)} Meeting Room labels; unresolved={unresolved}",
)
check(
    "catalog_tools_are_real_author_tools",
    all(
        set(spec.tools + spec.gated_tools) <= set(author.KNOWN_TOOLS)
        and set(spec.gated_tools) <= set(author.PRIVILEGED_TOOLS)
        for spec in work.SKILL_CATALOG.values()
    ),
    "a high-level skill may name only tools enforced by the authored-agent runtime",
)

# 3. Draft creation, activation, grants, and one run are separate transitions.
with tempfile.TemporaryDirectory(prefix="engel_mipl_agent_work_verify_") as temp:
    temp_root = Path(temp)
    registry_path = temp_root / "ENGEL_AGENT_REGISTRY.json"
    old_work_receipts = work.RECEIPT_DIR
    old_run_receipts = runner.RUN_DIR
    work.RECEIPT_DIR = temp_root / "work_receipts"
    runner.RUN_DIR = temp_root / "run_receipts"
    try:
        preview = work.preview_work_package(
            name="Temporary Review Agent",
            task="Review the latest training receipts and return evidence for operator review.",
            skill_refs=["verification", "reporting"],
            registry_path=registry_path,
        )
        check(
            "preview_performs_no_write",
            not registry_path.exists()
            and preview["agent"]["status"] == "draft"
            and preview["task"]["execution_authorized"] is False,
            "preview must compile the whole package without persisting or authorizing it",
        )
        created = work.create_work_package(
            name="Temporary Review Agent",
            task="Review the latest training receipts and return evidence for operator review.",
            skill_refs=["verification", "reporting"],
            registry_path=registry_path,
        )
        registry = author.load_registry(registry_path)
        task_id = created["task"]["task_id"]
        created_task = work.find_task(registry, task_id)
        bound_agent = work.validate_task_binding(registry, created_task)
        check(
            "create_persists_one_draft_assignment",
            registry_path.is_file()
            and len(registry["agents"]) == 1
            and len(registry["tasks"]) == 1
            and bound_agent["status"] == "draft"
            and created_task["status"] == "assigned_draft",
            "create must atomically save a draft agent and assigned-draft task in one registry",
        )
        check(
            "privileged_skill_tool_starts_pending",
            bound_agent["allow_actions"] is False
            and "run_verifier" not in bound_agent["tools"]
            and bound_agent["pending_tools"] == ["run_verifier"],
            "selecting Verification may not silently grant its verifier tool",
        )
        check(
            "draft_task_cannot_run",
            refused(
                work.run_task,
                task_id,
                approved_by="Joshua",
                reply_source=lambda _prompt: "should not run",
                registry_path=registry_path,
            ),
            "a created draft must not run before a separate activation",
        )
        check(
            "engel_cannot_activate_itself",
            refused(
                work.activate_task,
                task_id,
                approved_by="engel_ai_main",
                registry_path=registry_path,
            ),
            "activation must name a human operator",
        )
        activated = work.activate_task(
            task_id, approved_by="Joshua", registry_path=registry_path
        )
        check(
            "activation_is_separate_and_read_only",
            activated["agent"]["status"] == "active"
            and activated["task"]["status"] == "ready_read_only"
            and activated["task"]["execution_authorized"] is True
            and activated["agent"]["allow_actions"] is False,
            "activation may permit a run but may not grant gated skill tools",
        )
        check(
            "action_grant_requires_reason",
            refused(
                work.grant_task_actions,
                task_id,
                granted_by="Joshua",
                reason="ok",
                registry_path=registry_path,
            ),
            "operator-gated tools need a named operator and meaningful reason",
        )
        granted = work.grant_task_actions(
            task_id,
            granted_by="Joshua",
            reason="Approved to run the named local verifier for this bounded review",
            registry_path=registry_path,
        )
        check(
            "grant_enables_only_bound_pending_tool",
            granted["agent"]["allow_actions"] is True
            and "run_verifier" in granted["agent"]["tools"]
            and not granted["agent"]["pending_tools"]
            and granted["task"]["status"] == "ready",
            "a grant may enable only the privileged tools requested by the selected skills",
        )
        run_result = work.run_task(
            task_id,
            approved_by="Joshua",
            reply_source=lambda prompt: (
                "Candidate review returned with evidence."
                if "Bound skills: verification, reporting" in prompt
                else ""
            ),
            registry_path=registry_path,
        )
        check(
            "bounded_run_carries_skills_and_returns_for_review",
            run_result["run_receipt"]["ok"] is True
            and run_result["run_receipt"]["turns_used"] == 1
            and run_result["run_receipt"]["skills_assigned"]
            == ["verification", "reporting"]
            and run_result["task"]["status"] == "review_required",
            "one local turn must carry the binding and require review instead of self-completing",
        )
        check(
            "run_and_transitions_are_receipted",
            Path(run_result["run_receipt_path"]).is_file()
            and Path(run_result["event_receipt_path"]).is_file()
            and len(list((temp_root / "work_receipts").glob("*.json"))) >= 4,
            "create, activate, grant, and run return must leave local receipts",
        )
        registry_after = author.load_registry(registry_path)
        tampered_task = copy.deepcopy(work.find_task(registry_after, task_id))
        tampered_task["skill_ids"] = ["conversation"]
        check(
            "binding_drift_is_refused",
            refused(work.validate_task_binding, registry_after, tampered_task),
            "agent, task, skills, and MIPL references must remain identical",
        )
        author.revoke_actions(
            registry_after,
            str(granted["agent"]["agent_id"]),
            reason="verification finished",
        )
        revoked = author.find_agent(registry_after, str(granted["agent"]["agent_id"]))
        check(
            "revocation_removes_privileged_skill_tools",
            revoked["allow_actions"] is False
            and "run_verifier" not in revoked["tools"]
            and "run_verifier" in revoked["pending_tools"],
            "removing authority must physically remove privileged tools from the agent",
        )
        status = work.registry_status(registry_path)
        check(
            "registry_status_validates_bindings",
            status["tasks"] == 1
            and status["valid_bindings"] == 1
            and status["invalid_bindings"] == 0,
            "status must validate stored MIPL references rather than only count rows",
        )
    finally:
        work.RECEIPT_DIR = old_work_receipts
        runner.RUN_DIR = old_run_receipts

# 4. Bounds and refusals.
check(
    "unknown_skill_is_refused",
    refused(work.resolve_skill, "unlimited shell authority"),
    "agents may not invent a capability outside the skill catalog",
)
check(
    "excess_skills_are_bounded",
    len(work.resolve_skills(list(work.SKILL_CATALOG) * 3)) <= mipl.MAX_SKILLS_PER_TASK,
    "one task may carry no more than the low-resource skill bound",
)
check(
    "oversized_task_is_refused",
    refused(
        work.preview_work_package,
        name="Large Task Agent",
        task="x" * (mipl.MAX_TASK_CHARS + 1),
        skill_refs=["reporting"],
    ),
    "the orchestrator must refuse rather than silently truncate a task",
)

# 5. Engel Main route, worker, and UI wiring.
route_expectations = {
    "mipl agent docs": routes.ENGEL_MIPL_AGENT_DOCS_ROUTE_ID,
    "mipl agent skills": routes.ENGEL_MIPL_AGENT_SKILLS_ROUTE_ID,
    "mipl agent status": routes.ENGEL_MIPL_AGENT_STATUS_ROUTE_ID,
    "mipl agent list": routes.ENGEL_MIPL_AGENT_LIST_ROUTE_ID,
}
check(
    "engel_main_routes_resolve",
    all(routes.resolve_update_route(alias) == route_id for alias, route_id in route_expectations.items())
    and all(
        routes.route_metadata(route_id).get("target_module") == "engel_mipl_agent_work"
        for route_id in route_expectations.values()
    ),
    "docs, skill catalog, status, and task list must use the main route registry",
)
worker_source = (TOOLS / "engel_main_local_model_worker.py").read_text(encoding="utf-8")
ui_source = (ROOT / "engel_flutter_main" / "lib" / "main.dart").read_text(encoding="utf-8")
check(
    "engel_main_chat_and_ui_are_wired",
    "mipl\\s+agents?" in worker_source
    and "engel_mipl_agent_work" in worker_source
    and "agents-create-mipl-agent" in ui_source
    and "mipl-agent-create-draft" in ui_source
    and "skills-mipl-agent-catalog" in ui_source,
    "chat commands and the Agents/Skills pages must surface the work-package flow",
)

# 6. The compiler remains cheap and the orchestration module has no hidden executor.
tracemalloc.start()
started = time.perf_counter()
benchmark_ok = True
for _ in range(500):
    candidate = mipl.compile_agent_task_ir(**IR_ARGS)
    benchmark_ok = benchmark_ok and mipl.validate_ir(candidate)["ok"]
elapsed = time.perf_counter() - started
_current, peak = tracemalloc.get_traced_memory()
tracemalloc.stop()
check(
    "agent_packet_resource_benchmark",
    benchmark_ok and elapsed < 5.0 and peak < 8 * 1024 * 1024,
    f"500 compile+validate cycles in {elapsed:.3f}s; peak {peak / 1024:.1f} KiB",
)
module_source = (ROOT / "engel_mipl_agent_work.py").read_text(encoding="utf-8")
check(
    "orchestrator_has_no_shell_provider_or_background_loop",
    not any(
        token in module_source
        for token in (
            "subprocess.",
            "os.system(",
            "eval(",
            "exec(",
            "Thread(",
            "openai",
            "anthropic",
            "background worker",
        )
    ),
    "the seam may write bounded records and call the existing local runner, not become a new executor",
)

failed = [row for row in checks if row["status"] != "PASS"]
result = {
    "schema": "engel_mipl_agent_work_verification_v1",
    "status": "FAIL" if failed else "PASS",
    "passed": len(checks) - len(failed),
    "total": len(checks),
    "checks": checks,
    "benchmark": {
        "cycles": 500,
        "elapsed_seconds": round(elapsed, 6),
        "peak_kib": round(peak / 1024, 3),
        "sample_packets": profile["packet_count"],
        "sample_encoded_bytes": profile["encoded_bytes"],
    },
}
print(json.dumps(result, indent=2, ensure_ascii=False))
raise SystemExit(1 if failed else 0)
