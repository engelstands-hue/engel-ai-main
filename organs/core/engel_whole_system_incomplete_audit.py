from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import engel_global_password_gate


PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
MAX_READ_CHARS = 60_000

PRIORITY_ORDER = ["critical", "high", "medium", "low"]


@dataclass(frozen=True)
class IncompleteItem:
    priority: str
    rank: int
    title: str
    evidence: list[str]
    suggested_next_action: str
    safety_impact: str
    blocks_engel_ai_setup: bool
    blocks_packaging: bool
    blocks_real_apply: bool
    blocks_phone_automation: bool


def exists(path: str) -> bool:
    return (PROJECT_ROOT / path).exists()


def read_bounded(path: str) -> str:
    candidate = PROJECT_ROOT / path
    if not candidate.exists() or not candidate.is_file():
        return ""
    return candidate.read_text(encoding="utf-8", errors="replace")[:MAX_READ_CHARS]


def phase_report_mentions(path: str, text: str) -> bool:
    return text.lower() in read_bounded(path).lower()


def item(
    priority: str,
    rank: int,
    title: str,
    evidence: list[str],
    suggested_next_action: str,
    safety_impact: str,
    *,
    blocks_engel_ai_setup: bool = False,
    blocks_packaging: bool = False,
    blocks_real_apply: bool = False,
    blocks_phone_automation: bool = False,
) -> IncompleteItem:
    return IncompleteItem(
        priority,
        rank,
        title,
        evidence,
        suggested_next_action,
        safety_impact,
        blocks_engel_ai_setup,
        blocks_packaging,
        blocks_real_apply,
        blocks_phone_automation,
    )


def build_items() -> list[IncompleteItem]:
    items: list[IncompleteItem] = []
    rank = 1
    password_configured = engel_global_password_gate.is_global_password_gate_configured()
    if not password_configured:
        items.append(
            item(
                "critical",
                rank,
                "Global password/protected-action gate is valid but unconfigured, so real protected apply remains blocked.",
                [
                    "memory\\ENGEL_GLOBAL_PASSWORD_GATE_V1.json",
                    "reports\\codex_bridge\\ENGEL_CODE_COMPANION_PROTECTED_APPLY_PASSWORD_GATE_INTEGRATION_SMOKE.md",
                    "engel_code_companion_protected_patch_apply.py",
                ],
                "Configure the global password gate through the existing hidden-prompt setup only when Josh is ready to authorize protected writes.",
                "Fail-closed. This protects source files, but blocks real protected patch apply.",
                blocks_real_apply=True,
            )
        )
        rank += 1

    if phase_report_mentions(
        "reports\\codex_bridge\\ENGEL_CODE_COMPANION_TINY_DOCUMENTATION_PATCH_APPLY_SMOKE.md",
        "blocked",
    ):
        items.append(
            item(
                "critical",
                rank,
                "Code Companion tiny documentation patch apply smoke remains blocked.",
                ["reports\\codex_bridge\\ENGEL_CODE_COMPANION_TINY_DOCUMENTATION_PATCH_APPLY_SMOKE.md"],
                "After password-gate setup, rerun the tiny documentation-only apply smoke through the full protected apply chain.",
                "No source behavior changed; the apply ladder has not yet completed one real protected apply.",
                blocks_real_apply=True,
            )
        )
        rank += 1

    if not exists("engel_code_companion_protected_rollback.py"):
        items.append(
            item(
                "high",
                rank,
                "Protected rollback MVP is not implemented because no real apply backup exists yet.",
                [
                    "reports\\code_companion_patch_applies\\backups",
                    "reports\\code_companion_patch_applies\\rollback",
                ],
                "Complete one gated documentation-only apply first, then add protected rollback against its backup metadata.",
                "Rollback remains manual/not available for real applies until the MVP exists.",
                blocks_real_apply=False,
            )
        )
        rank += 1

    if not phase_report_mentions(
        "reports\\codex_bridge\\ENGEL_REMOTE_WORKER_PHASE_12_ENGEL_CONTROLLED_PHONE_LINK_MANAGER.md",
        "live smoke",
    ):
        items.append(
            item(
                "high",
                rank,
                "Remote Worker Link Manager is implemented, but a fresh live phone smoke after the manager may still be pending.",
                ["reports\\codex_bridge\\ENGEL_REMOTE_WORKER_PHASE_12_ENGEL_CONTROLLED_PHONE_LINK_MANAGER.md"],
                "Run a visible LAN Link Manager start/pair/status/check/stop smoke with the dedicated phone when convenient.",
                "Phone automation remains safer if treated as manual/observed until the manager is live-smoked.",
                blocks_phone_automation=True,
            )
        )
        rank += 1

    if phase_report_mentions("reports\\codex_bridge\\ENGEL_MODEL_LIBRARY_PLAN_V1.md", "disabled") or phase_report_mentions(
        "reports\\codex_bridge\\ENGEL_MANUAL_MODEL_INTAKE_EVALUATION_V1.md",
        "manual",
    ):
        items.append(
            item(
                "high",
                rank,
                "Engel AI model/runtime readiness is still plan/manual-evaluation oriented.",
                [
                    "reports\\codex_bridge\\ENGEL_MODEL_LIBRARY_PLAN_V1.md",
                    "reports\\codex_bridge\\ENGEL_MANUAL_MODEL_INTAKE_EVALUATION_V1.md",
                    "reports\\codex_bridge\\ENGEL_LLM_AND_PYTHON_LIBRARY_INTAKE_PLAN_V1.md",
                ],
                "Build the next AI readiness dashboard/intake step before expecting local model inference.",
                "Keeps provider/model execution disabled; blocks deeper Engel AI runtime setup.",
                blocks_engel_ai_setup=True,
            )
        )
        rank += 1

    if phase_report_mentions("reports\\codex_bridge\\ENGEL_NON_MODEL_LIBRARY_PLAN_V1.md", "manual"):
        items.append(
            item(
                "medium",
                rank,
                "Non-model library approvals remain manual/status-only.",
                ["reports\\codex_bridge\\ENGEL_NON_MODEL_LIBRARY_PLAN_V1.md"],
                "Continue with bounded local library intake approvals before enabling any automated indexing.",
                "Safe local library material remains gated and not auto-indexed.",
                blocks_engel_ai_setup=False,
            )
        )
        rank += 1

    items.append(
        item(
            "medium",
            rank,
            "Recent Code Companion and Remote Worker modules have not been packaged into live EXEs.",
            [
                "reports\\codex_bridge\\ENGEL_CODE_COMPANION_PATCH_CLASS_ALLOWLIST_V1.md",
                "reports\\codex_bridge\\ENGEL_CODE_COMPANION_PATCH_APPLY_UI_REVIEW_SURFACE_V1.md",
                "reports\\codex_bridge\\ENGEL_REMOTE_WORKER_PHASE_12_ENGEL_CONTROLLED_PHONE_LINK_MANAGER.md",
            ],
            "Run a package refresh only after the password-gate status decision and any desired live phone smoke.",
            "Live EXEs may lag source modules; source/verifiers remain current.",
            blocks_packaging=True,
        )
    )
    rank += 1

    if not exists("tools\\engel_code_companion_review_surface.py"):
        review_title = "Code Companion review surface is missing."
    else:
        review_title = "Code Companion review surface is standalone and not yet packaged or merged into the main GUI."
    items.append(
        item(
            "medium",
            rank,
            review_title,
            ["reports\\codex_bridge\\ENGEL_CODE_COMPANION_PATCH_APPLY_UI_REVIEW_SURFACE_V1.md"],
            "Decide whether to keep it standalone or add a read-only main GUI tab in a later GUI phase.",
            "No apply risk; this is a UX/accessibility completion item.",
        )
    )
    rank += 1

    pid_path = PROJECT_ROOT / "memory" / "engel_super_swarm_hive_3d.pid"
    if pid_path.exists():
        items.append(
            item(
                "low",
                rank,
                "Runtime PID file exists and should stay out of commits.",
                ["memory\\engel_super_swarm_hive_3d.pid"],
                "Leave runtime PID files unstaged or restore them before commits.",
                "No product blocker; repository hygiene only.",
            )
        )
        rank += 1

    items.append(
        item(
            "low",
            rank,
            "Packaging has intentionally been skipped across several safety phases.",
            ["reports\\codex_bridge"],
            "Schedule one scoped EXE repackage after the current safety gates are settled.",
            "No source safety issue; users of live EXEs may not see newest tooling.",
            blocks_packaging=True,
        )
    )
    return items


def audit_payload() -> dict[str, Any]:
    items = build_items()
    buckets: dict[str, list[dict[str, Any]]] = {priority: [] for priority in PRIORITY_ORDER}
    for audit_item in items:
        buckets[audit_item.priority].append(audit_item.__dict__.copy())
    return {
        "audit_version": "1",
        "created_by": "Engel Code Companion",
        "mode": "read_only_report_only",
        "priority_order": PRIORITY_ORDER,
        "item_count": len(items),
        "buckets": buckets,
        "safety": {
            "source_mutation": False,
            "route_mutation": False,
            "queue_mutation": False,
            "trusted_memory_write": False,
            "provider_api_cloud_browser": False,
            "wsl_hermes_docker": False,
            "background_workers": False,
        },
    }


def render_status() -> str:
    payload = audit_payload()
    lines = [
        "Engel whole-system incomplete audit",
        f"mode: {payload['mode']}",
        f"item_count: {payload['item_count']}",
    ]
    for priority in PRIORITY_ORDER:
        lines.append(f"{priority}: {len(payload['buckets'][priority])}")
    return "\n".join(lines)


def render_report() -> str:
    payload = audit_payload()
    lines = [
        "# Engel Whole-System Incomplete Items Audit",
        "",
        "Mode: read-only/report-only. No source, route, queue, or trusted-memory mutation is performed.",
        "",
        "## Ranked Priorities",
    ]
    for priority in PRIORITY_ORDER:
        lines.extend(["", f"### {priority.title()}"])
        bucket = payload["buckets"][priority]
        if not bucket:
            lines.append("- None currently identified.")
            continue
        for entry in bucket:
            lines.append(f"{entry['rank']}. {entry['title']}")
            lines.append(f"   - evidence: {', '.join(entry['evidence'])}")
            lines.append(f"   - suggested next action: {entry['suggested_next_action']}")
            lines.append(f"   - safety impact: {entry['safety_impact']}")
            lines.append(
                "   - blocks: "
                + f"AI setup={entry['blocks_engel_ai_setup']}, "
                + f"packaging={entry['blocks_packaging']}, "
                + f"real apply={entry['blocks_real_apply']}, "
                + f"phone automation={entry['blocks_phone_automation']}"
            )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only Engel whole-system incomplete item audit.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="Show audit status.")
    sub.add_parser("report", help="Print markdown audit report.")
    sub.add_parser("json", help="Print JSON audit payload.")
    args = parser.parse_args(argv)

    if args.command == "status":
        print(render_status())
        return 0
    if args.command == "report":
        print(render_report(), end="")
        return 0
    if args.command == "json":
        print(json.dumps(audit_payload(), indent=2, sort_keys=True))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
