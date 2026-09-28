"""Gate for the bounded action executor (tools/engel_agent_action_executor.py).

This is the only component on the agent surface that can change the workspace, so this
gate is written almost entirely against REFUSALS. A permissive bug here is not a quality
problem, it is an agent editing its own permissions.

The checks that matter most are the four self-escalation denials. The realistic failure is
not an agent wrecking the repo; it is an agent quietly writing to `memory/agents/` to set
its own `allow_actions`, or to `tools/` to blunt the gate that would have caught it. Both
must be refused even though an operator has granted the agent the ability to act.

Every mutation in this file happens under `reports/` inside a scratch folder that is
removed at the end. Nothing else in the workspace is touched.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import engel_agent_action_executor as ex  # noqa: E402
import engel_agent_author as aa  # noqa: E402

checks: list[dict] = []
SCRATCH = "reports/agent_actions/_verify_scratch"


def check(name: str, ok: bool, detail: str) -> None:
    checks.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": detail})


def refused(fn, *a, **kw) -> bool:
    try:
        fn(*a, **kw)
    except (ex.ActionRefused, aa.AgentAuthorError):
        return True
    except Exception:
        return False
    return False


DIRECTION = (
    "Write findings to the reports directory and stop; do not attempt anything outside "
    "the writable roots."
)


def make_agent(*, granted: bool, active: bool = True, name: str = "Actor") -> dict:
    reg = {"schema": aa.SCHEMA, "updated_at_utc": None, "agents": []}
    agent = aa.author_agent(name, "produce written findings", DIRECTION,
                            tools=["read_files"], registry=reg)
    if granted:
        aa.grant_actions(reg, name, granted_by="Joshua",
                         reason="approved to write its findings under reports for review")
    if active:
        aa.set_status(reg, name, "active")
    return agent


granted = make_agent(granted=True)
ungranted = make_agent(granted=False, name="NoGrant")


def act(kind: str, path: str, content: str = "hello") -> ex.Action:
    return ex.Action(kind=kind, path=path, content=content)


# --- 1. the grant itself ----------------------------------------------------------
check("refuses_without_action_grant",
      refused(ex.execute, ungranted, [act("write_file", f"{SCRATCH}/a.md")], apply=False),
      "an agent with no action grant must not act, even in dry run")
draftish = make_agent(granted=True, active=False, name="DraftActor")
check("refuses_non_active_agent",
      refused(ex.execute, draftish, [act("write_file", f"{SCRATCH}/a.md")], apply=False),
      "a draft agent must not act even when granted")

# --- 2. SELF-ESCALATION: the denials that matter most -----------------------------
# These must be refused for a FULLY GRANTED agent -- the grant is not a bypass.
check("denies_writing_the_agent_registry",
      refused(ex.resolve_target, "memory/agents/ENGEL_AGENT_REGISTRY.json"),
      "an agent must never be able to edit the registry that stores its own allow_actions")
check("denies_writing_tools",
      refused(ex.resolve_target, "tools/verify_engel_agent_action_executor.py"),
      "an agent must never be able to edit its own gates")
check("denies_writing_this_executor",
      refused(ex.resolve_target, "tools/engel_agent_action_executor.py"),
      "an agent must never be able to rewrite the module that bounds it")
check("denies_writing_git", refused(ex.resolve_target, ".git/config"),
      "history must be out of reach")
check("denies_writing_scripts", refused(ex.resolve_target, "scripts/codex_verify.ps1"),
      "the verifier sweep registration must be out of reach")
check("granted_agent_still_denied_registry",
      refused(ex.execute, granted,
              [act("write_file", "memory/agents/ENGEL_AGENT_REGISTRY.json")], apply=False),
      "the action grant must NOT be a bypass for the self-escalation denials")

# --- 3. path containment -----------------------------------------------------------
check("refuses_absolute_path", refused(ex.resolve_target, "C:/Windows/System32/drivers/etc/hosts"),
      "an absolute path must be refused")
check("refuses_parent_traversal", refused(ex.resolve_target, "reports/../../outside.md"),
      "upward traversal must be refused")
check("refuses_outside_allowed_roots", refused(ex.resolve_target, "engel_conductor.py"),
      "a path outside the writable roots must be refused")
check("refuses_empty_path", refused(ex.resolve_target, "   "),
      "an empty path must be refused")
ok_target = ex.resolve_target(f"{SCRATCH}/fine.md")
check("accepts_path_inside_allowed_root", str(ok_target).startswith(str(ROOT)),
      "a path inside reports/ must resolve inside the workspace")
check("accepts_generated_material_root",
      str(ex.resolve_target("memory/training/engel_main/generated/x.json")).startswith(str(ROOT)),
      "drafted training material is a legitimate agent output location")

# --- 4. the action vocabulary is closed --------------------------------------------
for forbidden in ("delete_file", "move_file", "run_command", "exec", "http_post"):
    check(f"has_no_{forbidden}",
          refused(ex.parse_action, {"kind": forbidden, "path": f"{SCRATCH}/x", "content": ""}),
          f"{forbidden} must not exist in the action vocabulary")
check("action_vocabulary_is_two_kinds",
      set(ex.KNOWN_ACTIONS) == {"write_file", "append_file"},
      f"the executor must offer only write/append; found {ex.KNOWN_ACTIONS}")
check("refuses_non_string_content",
      refused(ex.parse_action, {"kind": "write_file", "path": f"{SCRATCH}/x", "content": 5}),
      "content must be a string")
check("refuses_oversized_content",
      refused(ex.parse_action,
              {"kind": "write_file", "path": f"{SCRATCH}/x", "content": "x" * (ex.MAX_BYTES_PER_ACTION + 1)}),
      "an oversized write must be refused")

# --- 5. batch bounds and all-or-nothing validation --------------------------------
check("refuses_over_budget_batch",
      refused(ex.execute, granted,
              [act("write_file", f"{SCRATCH}/f{i}.md") for i in range(ex.MAX_ACTIONS_PER_RUN + 1)],
              apply=False),
      "a batch beyond the per-run ceiling must be refused")
check("refuses_empty_batch", refused(ex.execute, granted, [], apply=False),
      "an empty batch must be refused rather than silently succeed")

mixed = [act("write_file", f"{SCRATCH}/good.md"), act("write_file", "tools/evil.py")]
check("one_bad_action_blocks_the_whole_batch",
      refused(ex.execute, granted, mixed, apply=True)
      and not (ROOT / SCRATCH / "good.md").exists(),
      "validation runs before any write, so a batch containing a denied path writes NOTHING")

# --- 6. dry run writes nothing -----------------------------------------------------
dry = ex.execute(granted, [act("write_file", f"{SCRATCH}/dry.md", "dry content")], apply=False)
check("dry_run_is_the_default_and_writes_nothing",
      dry["applied"] is False and not (ROOT / SCRATCH / "dry.md").exists(),
      "a dry run must plan without touching disk")
check("dry_run_reports_the_plan",
      dry["actions"][0]["path"].endswith("dry.md") and dry["action_count"] == 1,
      "a dry run must still report exactly what it would do")

# --- 7. apply, then roll back ------------------------------------------------------
applied = ex.execute(granted, [act("write_file", f"{SCRATCH}/real.md", "first version")], apply=True)
created = ROOT / SCRATCH / "real.md"
check("apply_writes_the_file",
      created.is_file() and created.read_text(encoding="utf-8") == "first version",
      "an applied write must actually land")
check("apply_records_hashes",
      applied["actions"][0]["after_sha256"] and applied["actions"][0]["before_sha256"] is None,
      "the receipt must record before/after hashes (before is null for a new file)")

overwrite = ex.execute(granted, [act("write_file", f"{SCRATCH}/real.md", "second version")], apply=True)
check("overwrite_backs_up_previous_bytes",
      overwrite["actions"][0].get("backup") and Path(overwrite["actions"][0]["backup"]).is_file(),
      "an overwrite must back the previous bytes up before touching them")
undo = ex.rollback(overwrite)
check("rollback_restores_previous_content",
      undo["ok"] and created.read_text(encoding="utf-8") == "first version",
      "rollback must restore exactly what was there before the run")
undo_create = ex.rollback(applied)
check("rollback_removes_a_created_file",
      undo_create["ok"] and not created.exists(),
      "rolling back a run that CREATED a file must remove it")
check("refuses_rollback_of_dry_run", refused(ex.rollback, dry),
      "a dry run has nothing to roll back and must say so")

appended = ex.execute(granted, [act("append_file", f"{SCRATCH}/log.md", "line one\n")], apply=True)
ex.execute(granted, [act("append_file", f"{SCRATCH}/log.md", "line two\n")], apply=True)
check("append_adds_without_truncating",
      (ROOT / SCRATCH / "log.md").read_text(encoding="utf-8") == "line one\nline two\n",
      "append must add to the file rather than replace it")

# --- 8. the module cannot execute anything ----------------------------------------
# Checked over the AST, not the text. A substring scan flunked this module for the word
# "subprocess" appearing in its own docstring explaining that it does not use one -- the
# same prose-vs-code confusion that has produced several false gates in this system. What
# matters is whether the module IMPORTS an execution/network facility or CALLS eval/exec,
# and only a parse can answer that.
import ast  # noqa: E402

tree = ast.parse((ROOT / "tools" / "engel_agent_action_executor.py").read_text(encoding="utf-8"))
BANNED_MODULES = {"subprocess", "socket", "urllib", "requests", "http", "ctypes", "shutil"}
imported: set[str] = set()
called: set[str] = set()
for node in ast.walk(tree):
    if isinstance(node, ast.Import):
        imported.update(alias.name.split(".")[0] for alias in node.names)
    elif isinstance(node, ast.ImportFrom) and node.module:
        imported.add(node.module.split(".")[0])
    elif isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Name):
            called.add(func.id)
        elif isinstance(func, ast.Attribute):
            called.add(func.attr)

check("executor_imports_no_execution_or_network_module",
      not (imported & BANNED_MODULES),
      f"a granted agent must not reach a command runner or the network; found {sorted(imported & BANNED_MODULES)}")
check("executor_never_calls_eval_or_exec",
      not ({"eval", "exec", "system", "popen", "spawn"} & called),
      f"dynamic execution must be absent; found {sorted({'eval','exec','system','popen','spawn'} & called)}")

shutil.rmtree(ROOT / SCRATCH, ignore_errors=True)

failed = sum(1 for c in checks if c["status"] != "PASS")
print(json.dumps(
    {
        "schema": "engel_agent_action_executor_verifier_v1",
        "status": "FAIL" if failed else "PASS",
        "passed": len(checks) - failed,
        "total": len(checks),
        "checks": checks,
    },
    indent=2,
))
raise SystemExit(1 if failed else 0)
