"""The only place an authored agent may CHANGE anything -- bounded, reversible, audited.

Everything else on the agent surface is deliberately incapable of acting: the author
writes records, the runner generates text, the goal loop observes state. None of them
contains a subprocess or an exec. That was the right default, and it left one honest gap:
an agent given a goal it could only reach by changing something could do nothing but
report `stalled`. This module closes that gap, and it is the single component in the
system where a mistake can damage the workspace. So it is built as a series of refusals.

The blast radius, stated plainly
--------------------------------
  * ONLY these action kinds exist: write_file, append_file. There is no delete, no move,
    no rename, no command execution, no network. Deletion is where irreversible harm
    lives, so it is simply absent rather than guarded.
  * Writes are confined to ALLOWED_ROOTS -- `reports/` and
    `memory/training/engel_main/generated/`. These are the two places an agent's output
    legitimately belongs: findings and drafted material.
  * Paths are repo-relative, may not contain `..`, may not be absolute, and are resolved
    and re-checked against the workspace root AFTER resolution, so a symlink cannot walk
    out of the box.
  * Every applied write backs the previous bytes up first, and `--rollback` restores an
    entire run from its receipt. An action that cannot be undone is not offered.

Self-escalation is the threat that matters
------------------------------------------
The realistic failure is not an agent deleting the workspace; it is an agent quietly
widening its own authority and then acting freely. Four denials exist specifically for
that, and they are absolute -- they are checked even inside ALLOWED_ROOTS:

    memory/agents/**   the registry holding `allow_actions` -- an agent must never be
                       able to grant itself the very permission this module checks
    tools/**           the verifiers and gates, including this file -- an agent that can
                       edit its own gate has no gate
    .git/**            history
    scripts/**         the verifier sweep registration

Nothing here shells out, so even a fully granted agent cannot run a command through this
path. It can write files in two directories, and that is all it can ever do.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
BACKUP_DIR = ROOT / "runtime" / "agent_action_backups"
RECEIPT_DIR = ROOT / "reports" / "agent_actions"
SCHEMA = "engel_agent_action_run_v1"

sys.path.insert(0, str(TOOLS))
import engel_agent_author as author  # noqa: E402

KNOWN_ACTIONS = ("write_file", "append_file")

# Where an agent's output legitimately belongs: findings, and drafted material.
ALLOWED_ROOTS = ("reports", "memory/training/engel_main/generated")

# Absolute denials, checked even inside an allowed root. Each closes a self-escalation
# path, not a tidiness concern.
DENIED_PREFIXES = ("memory/agents", "tools", ".git", "scripts")

# A run may touch at most this many files. A bounded actor that can rewrite a thousand
# files in one run is not meaningfully bounded.
MAX_ACTIONS_PER_RUN = 20
MAX_BYTES_PER_ACTION = 512_000


class ActionRefused(PermissionError):
    """Raised when an action is outside the agent's bounds. Never downgraded to a warning."""


@dataclass(frozen=True)
class Action:
    kind: str
    path: str
    content: str

    def describe(self) -> str:
        return f"{self.kind} {self.path} ({len(self.content)} chars)"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def resolve_target(rel: str) -> Path:
    """Resolve a repo-relative path, refusing anything that leaves the box.

    The resolved path is re-checked against ROOT, so a symlink inside an allowed root
    cannot be used to walk out -- checking the string alone would miss that."""
    raw = str(rel or "").strip().replace("\\", "/")
    if not raw:
        raise ActionRefused("an action must name a path")
    candidate = Path(raw)
    if candidate.is_absolute():
        raise ActionRefused(f"path must be repo-relative, got absolute {raw!r}")
    if ".." in candidate.parts:
        raise ActionRefused(f"path may not traverse upward: {raw!r}")

    posix = candidate.as_posix()
    if not any(posix == root or posix.startswith(root + "/") for root in ALLOWED_ROOTS):
        raise ActionRefused(
            f"{raw!r} is outside the writable roots ({', '.join(ALLOWED_ROOTS)}) -- an "
            "agent writes findings and drafted material, nothing else"
        )
    for denied in DENIED_PREFIXES:
        if posix == denied or posix.startswith(denied + "/"):
            raise ActionRefused(
                f"{raw!r} is permanently denied ({denied}/) -- that path controls the "
                "agent's own authority or its gates"
            )

    target = (ROOT / candidate).resolve()
    try:
        target.relative_to(ROOT.resolve())
    except ValueError:
        raise ActionRefused(f"{raw!r} resolves outside the workspace") from None
    # Re-check the RESOLVED path, so a symlink cannot smuggle a denied prefix.
    resolved_rel = target.relative_to(ROOT.resolve()).as_posix()
    for denied in DENIED_PREFIXES:
        if resolved_rel == denied or resolved_rel.startswith(denied + "/"):
            raise ActionRefused(f"{raw!r} resolves into a denied path ({denied}/)")
    return target


def parse_action(spec: dict[str, Any]) -> Action:
    kind = str(spec.get("kind") or "").strip()
    if kind not in KNOWN_ACTIONS:
        raise ActionRefused(
            f"unknown action {kind!r} -- this executor performs only "
            f"{', '.join(KNOWN_ACTIONS)}; there is no delete, move, or command execution"
        )
    content = spec.get("content")
    if not isinstance(content, str):
        raise ActionRefused("an action needs string content")
    if len(content.encode("utf-8")) > MAX_BYTES_PER_ACTION:
        raise ActionRefused(f"content exceeds {MAX_BYTES_PER_ACTION} bytes")
    return Action(kind=kind, path=str(spec.get("path") or ""), content=content)


def check_permitted(agent: dict[str, Any]) -> None:
    """The grant check. Everything below assumes this passed."""
    if not agent.get("allow_actions"):
        raise ActionRefused(
            f"agent {agent.get('name')!r} has no action grant -- an operator must grant it "
            "with: engel_agent_author.py grant-actions --agent <name> --granted-by <you> "
            "--reason <why>"
        )
    if str(agent.get("status")) != "active":
        raise ActionRefused(f"agent is {agent.get('status')!r}; only an active agent acts")


def execute(
    agent: dict[str, Any],
    actions: list[Action],
    *,
    apply: bool = False,
) -> dict[str, Any]:
    """Validate every action first, then apply. Dry-run unless `apply` is true.

    Validation is a separate pass on purpose: a run that would touch one denied path
    performs NONE of its actions, so a partially-applied batch cannot leave the workspace
    in a state nobody designed."""
    check_permitted(agent)
    if not actions:
        raise ActionRefused("no actions supplied")
    if len(actions) > MAX_ACTIONS_PER_RUN:
        raise ActionRefused(
            f"{len(actions)} actions exceeds the per-run ceiling of {MAX_ACTIONS_PER_RUN}"
        )

    planned: list[dict[str, Any]] = []
    for action in actions:
        target = resolve_target(action.path)  # raises on any violation
        existed = target.is_file()
        planned.append(
            {
                "kind": action.kind,
                "path": action.path,
                "resolved": str(target),
                "existed": existed,
                "before_sha256": _sha(target.read_bytes()) if existed else None,
                "bytes": len(action.content.encode("utf-8")),
            }
        )

    stamp = _utc_now()
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "run_at_utc": stamp,
        "agent_id": agent.get("agent_id"),
        "agent_name": agent.get("name"),
        "direction_version": agent.get("direction_version"),
        "applied": bool(apply),
        "action_count": len(actions),
        "actions": planned,
        "backup_dir": None,
    }
    if not apply:
        receipt["note"] = "dry run -- nothing was written; pass --apply to perform these"
        return receipt

    run_backup = BACKUP_DIR / stamp.replace(":", "").replace("-", "")
    run_backup.mkdir(parents=True, exist_ok=True)
    receipt["backup_dir"] = str(run_backup)

    for action, row in zip(actions, planned):
        target = Path(row["resolved"])
        if row["existed"]:
            # Back the previous bytes up BEFORE touching them, so rollback is total.
            backup = run_backup / (hashlib.sha256(row["path"].encode()).hexdigest()[:16] + ".bak")
            backup.write_bytes(target.read_bytes())
            row["backup"] = str(backup)
        target.parent.mkdir(parents=True, exist_ok=True)
        if action.kind == "write_file":
            target.write_text(action.content, encoding="utf-8")
        else:
            with target.open("a", encoding="utf-8") as handle:
                handle.write(action.content)
        row["after_sha256"] = _sha(target.read_bytes())
    return receipt


def rollback(receipt: dict[str, Any]) -> dict[str, Any]:
    """Undo an applied run using its own receipt."""
    if not receipt.get("applied"):
        raise ActionRefused("that receipt was a dry run; there is nothing to roll back")
    restored, removed, problems = [], [], []
    for row in receipt.get("actions", []):
        target = Path(row["resolved"])
        try:
            if row.get("existed") and row.get("backup"):
                target.write_bytes(Path(row["backup"]).read_bytes())
                restored.append(row["path"])
            elif not row.get("existed") and target.is_file():
                # The run created this file; undoing means removing what it created.
                target.unlink()
                removed.append(row["path"])
        except OSError as exc:
            problems.append(f"{row['path']}: {exc}")
    return {
        "ok": not problems,
        "restored": restored,
        "removed_created": removed,
        "problems": problems,
    }


def write_receipt(receipt: dict[str, Any]) -> Path:
    RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(receipt["run_at_utc"]).replace(":", "").replace("-", "")
    path = RECEIPT_DIR / f"ENGEL_AGENT_ACTIONS_{receipt.get('agent_id')}_{stamp}.json"
    path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")
    (RECEIPT_DIR / "ENGEL_AGENT_ACTIONS_LATEST.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", required=True)
    parser.add_argument(
        "--action", action="append", default=[],
        help='JSON action, repeatable: {"kind":"write_file","path":"reports/x.md","content":"..."}',
    )
    parser.add_argument(
        "--actions-file", default="",
        help=(
            "path to a JSON file holding a list of actions. Prefer this for anything real: "
            "inline JSON containing spaces or '#' is mangled by PowerShell's native "
            "argument handling before python ever sees it"
        ),
    )
    parser.add_argument("--apply", action="store_true",
                        help="perform the actions (default is a dry run)")
    parser.add_argument("--rollback", default="",
                        help="path to a prior applied receipt to undo")
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args(argv)

    registry = author.load_registry()
    try:
        if args.rollback:
            prior = json.loads(Path(args.rollback).read_text(encoding="utf-8-sig"))
            print(json.dumps(rollback(prior), indent=2))
            return 0
        agent = author.find_agent(registry, args.agent)
        specs: list[Any] = [json.loads(raw) for raw in args.action]
        if args.actions_file:
            loaded = json.loads(Path(args.actions_file).read_text(encoding="utf-8-sig"))
            if not isinstance(loaded, list):
                raise ActionRefused("--actions-file must hold a JSON list of actions")
            specs.extend(loaded)
        actions = [parse_action(spec) for spec in specs]
        receipt = execute(agent, actions, apply=args.apply)
    except (author.AgentAuthorError, ActionRefused, ValueError) as exc:
        print(json.dumps({"ok": False, "refused": str(exc)}, indent=2))
        return 1

    path = write_receipt(receipt)
    if args.summary:
        print(json.dumps(
            {
                "ok": True,
                "agent": receipt["agent_name"],
                "applied": receipt["applied"],
                "action_count": receipt["action_count"],
                "paths": [a["path"] for a in receipt["actions"]],
                "backup_dir": receipt["backup_dir"],
                "receipt": str(path),
            },
            indent=2,
        ))
    else:
        print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
