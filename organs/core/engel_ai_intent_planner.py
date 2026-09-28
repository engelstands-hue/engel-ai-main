from __future__ import annotations

import re
from dataclasses import dataclass, field

from engel_prompt_injection_guard import check_prompt_injection


AUTHORITY_BOUNDARY = "Josh > Guardian > Engel/runtime"
AUTHORITY_BLOCK_REASON = (
    "Josh remains final human authority. Guardian remains second. "
    "Engel/runtime remains below both gates."
)


@dataclass(frozen=True)
class EngelAIPlan:
    user_text: str
    normalized_text: str
    intent_type: str
    matched_route: str
    action_summary: str
    target_summary: str
    risk_level: str
    approval_required: bool
    approval_token: str
    guardian_required: bool
    prompt_injection_check_required: bool
    authority_check_required: bool
    model_allowed: bool
    model_allowed_scope: str
    deterministic_route_required: bool
    can_execute_now: bool
    blocked: bool
    block_reason: str
    suggested_command: str
    next_step_text: str
    safety_notes: list[str] = field(default_factory=list)
    proceed_allowed: bool = False
    proceed_block_reason: str = ""
    executable_command: str = ""
    execution_mode: str = "plan_only"


KNOWN_EXACT_COMMANDS = {
    "status",
    "commands",
    "help",
    "human command mode status",
    "human command help",
    "guarded write status",
    "mind growth status",
    "upgrade connections status",
    "future upgrades status",
    "future upgrade status",
    "upgrade readiness status",
    "next upgrades status",
    "complex routes status",
    "long term memory drive status",
    "long-term memory drive status",
    "engel long term memory status",
    "python teaching mode status",
    "python lesson help",
    "python learning path",
    "offline seed llm status",
    "offline llm status",
    "engel mind seed status",
    "colony hive status",
    "colony hive map",
    "colony hive permissions",
    "colony hive queen links",
    "colony hive communication queen",
    "colony hive remote queens",
    "communication queen status",
    "prompt injection status",
    "ai help",
    "ai planner status",
}

SAFE_PROCEED_EXACT_COMMANDS = {
    "ai help",
    "ai planner status",
    "human command mode status",
    "human command help",
    "guarded write status",
    "mind growth status",
    "upgrade connections status",
    "future upgrades status",
    "future upgrade status",
    "upgrade readiness status",
    "next upgrades status",
    "complex routes status",
    "long term memory drive status",
    "long-term memory drive status",
    "engel long term memory status",
    "prompt injection status",
}

SAFE_PROCEED_PREFIXES = (
    "research file ",
    "research folder ",
    "prompt injection check ",
)

PROCEED_BLOCKED_INTENTS = {
    "human_report_write",
    "human_file_write",
    "human_local_install_copy",
    "human_dependency_install",
    "python_lesson_run",
    "remote_queen_request",
    "package_or_system_install_request",
    "source_edit_request",
    "trusted_memory_request",
    "queue_or_route_mutation_request",
    "autonomy_request",
    "authority_inversion_attempt",
    "unsafe_or_blocked",
    "unknown_command_candidate",
}


AUTHORITY_INVERSION_PATTERNS = (
    r"\bguardian\s+(above|over|before|outranks?|supersedes|overrides?|replaces?)\s+josh\b",
    r"\bjosh\s+(below|under|after|beneath|subordinate\s+to)\s+guardian\b",
    r"\breplace\s+josh\s+with\s+guardian\b",
    r"\b(ignore|remove|disable|bypass)\s+josh\b",
    r"\b(remove|disable)\s+josh\s+(approval|gate|authority)\b",
    r"\bmake\s+guardian\s+(the\s+)?(top|highest|owner|operator|approver|authority)\b",
    r"\bguardian\s+(is\s+)?(top|highest)\s+(authority|approver)\b",
)

REMOTE_QUEEN_PATTERNS = (
    "remote queen",
    "remote queens",
    "trusted wifi",
    "wifi pairing",
    "pair device",
    "device pairing",
    "communication queen runtime",
)

AUTONOMY_PATTERNS = (
    "act alone",
    "run yourself",
    "autonomous",
    "autonomy",
    "background worker",
    "background workers",
    "hidden timed job",
    "timed job",
    "run forever",
    "keep running",
    "loop by yourself",
    "without approval",
)

SOURCE_EDIT_PATTERNS = (
    "edit source",
    "source edit",
    "patch source",
    "change source",
    "edit engel_app.py",
    "change engel_app.py",
    "modify engel_app.py",
    "edit routes",
    "change routes",
    "modify routes",
)

TRUSTED_MEMORY_PATTERNS = (
    "trusted memory",
    "remember this forever",
    "write to memory",
    "save to memory",
    "make this trusted",
    "trust this memory",
)

QUEUE_ROUTE_MUTATION_PATTERNS = (
    "queue mutation",
    "mutate queue",
    "change queue",
    "route mutation",
    "mutate route",
    "enable route",
    "disable route",
)

SYSTEM_INSTALL_PATTERNS = (
    "system install",
    "install build tools",
    "install visual studio",
    "run installer",
    "add to path",
    "choco install",
    "winget install",
    "npm install",
)


def normalize_text(text: str) -> str:
    raw = str(text or "").strip().lower()
    return " ".join(raw.split())


def _contains_any(normalized_text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in normalized_text for phrase in phrases)


def _command_is_safe_for_proceed(command: str) -> bool:
    normalized = normalize_text(command)
    if not normalized:
        return False
    if " to report " in (" " + normalized + " "):
        return False
    if normalized in SAFE_PROCEED_EXACT_COMMANDS:
        return True
    return any(normalized.startswith(prefix) for prefix in SAFE_PROCEED_PREFIXES)


def _derive_proceed_fields(
    *,
    intent_type: str,
    blocked: bool,
    block_reason: str,
    approval_required: bool,
    suggested_command: str,
) -> tuple[bool, str, str, str]:
    command = str(suggested_command or "").strip()
    if blocked:
        return (
            False,
            block_reason or "Plan is blocked by Guardian safety rules.",
            command,
            "blocked",
        )
    if approval_required:
        return (
            False,
            "Approval required; this GUI Proceed button does not accept approval tokens.",
            command,
            "requires_approval",
        )
    if intent_type in PROCEED_BLOCKED_INTENTS:
        return (
            False,
            "Proceed is disabled for this intent type; use a separate explicit approved route if one exists.",
            command,
            "blocked" if intent_type in {"authority_inversion_attempt", "remote_queen_request", "autonomy_request", "unsafe_or_blocked"} else "plan_only",
        )
    if not command:
        return (
            False,
            "No deterministic command is available for Proceed.",
            "",
            "plan_only",
        )
    if _command_is_safe_for_proceed(command):
        return (True, "", command, "deterministic_route")
    return (
        False,
        "No approval-free Human Command Mode Proceed route is enabled for this plan.",
        command,
        "plan_only",
    )


def can_proceed(plan: EngelAIPlan) -> bool:
    return bool(getattr(plan, "proceed_allowed", False))


def proceed_block_reason(plan: EngelAIPlan) -> str:
    reason = str(getattr(plan, "proceed_block_reason", "") or "").strip()
    if reason:
        return reason
    if can_proceed(plan):
        return ""
    return "Proceed is not available for this plan."


def _matches_authority_inversion(text: str) -> bool:
    normalized = normalize_text(text)
    return any(re.search(pattern, normalized, flags=re.IGNORECASE) for pattern in AUTHORITY_INVERSION_PATTERNS)


def _split_keyword(rest: str, keyword: str) -> tuple[str, str]:
    pattern = re.compile(r"\s+" + re.escape(keyword) + r"\s+", flags=re.IGNORECASE)
    match = pattern.search(rest)
    if not match:
        return rest.strip(), ""
    return rest[: match.start()].strip(), rest[match.end() :].strip()


def _strip_report_request_suffix(rest: str) -> str:
    patterns = (
        r"\s+and\s+make\s+(me\s+)?a\s+report\b.*$",
        r"\s+and\s+create\s+(me\s+)?a\s+report\b.*$",
        r"\s+with\s+a\s+report\b.*$",
    )
    value = rest.strip()
    for pattern in patterns:
        value = re.sub(pattern, "", value, flags=re.IGNORECASE).strip()
    return value


def _extract_after_prefix(user_text: str, prefixes: tuple[str, ...]) -> str:
    lower = user_text.lower()
    for prefix in prefixes:
        if lower.startswith(prefix):
            return user_text[len(prefix) :].strip()
    for prefix in prefixes:
        marker = " " + prefix
        idx = lower.find(marker)
        if idx >= 0:
            return user_text[idx + len(marker) :].strip()
    return ""


def _package_reason_from_install_dependency(text: str) -> tuple[str, str]:
    rest = _extract_after_prefix(text, ("install dependency ",))
    if rest.endswith(" APPROVE_INSTALL"):
        rest = rest[: -len(" APPROVE_INSTALL")].strip()
    package, reason = _split_keyword(rest, "for")
    return package.strip(), reason.strip()


def _base_plan(
    user_text: str,
    *,
    intent_type: str,
    matched_route: str,
    action_summary: str,
    target_summary: str = "none",
    risk_level: str = "low",
    approval_required: bool = False,
    approval_token: str = "",
    guardian_required: bool = True,
    prompt_injection_check_required: bool = True,
    authority_check_required: bool = True,
    model_allowed: bool = False,
    model_allowed_scope: str = "not allowed for execution; deterministic planner only",
    deterministic_route_required: bool = True,
    can_execute_now: bool = False,
    blocked: bool = False,
    block_reason: str = "",
    suggested_command: str = "",
    next_step_text: str = "Run the suggested deterministic command only if you want Engel to proceed.",
    safety_notes: list[str] | None = None,
) -> EngelAIPlan:
    notes = [
        "Planner is deterministic, local, and plan-only.",
        "No provider/API/network call.",
        "No model-command execution.",
        "No autonomy, background worker, queue mutation, trusted-memory write, source edit, or ALIVE_STATE write.",
        "Authority boundary: " + AUTHORITY_BOUNDARY + ".",
    ]
    if safety_notes:
        notes.extend(safety_notes)
    proceed_allowed, proceed_reason, executable_command, execution_mode = _derive_proceed_fields(
        intent_type=intent_type,
        blocked=blocked,
        block_reason=block_reason,
        approval_required=approval_required,
        suggested_command=suggested_command,
    )
    return EngelAIPlan(
        user_text=str(user_text or ""),
        normalized_text=normalize_text(user_text),
        intent_type=intent_type,
        matched_route=matched_route,
        action_summary=action_summary,
        target_summary=target_summary or "none",
        risk_level=risk_level,
        approval_required=approval_required,
        approval_token=approval_token,
        guardian_required=guardian_required,
        prompt_injection_check_required=prompt_injection_check_required,
        authority_check_required=authority_check_required,
        model_allowed=model_allowed,
        model_allowed_scope=model_allowed_scope,
        deterministic_route_required=deterministic_route_required,
        can_execute_now=can_execute_now,
        blocked=blocked,
        block_reason=block_reason,
        suggested_command=suggested_command,
        next_step_text=next_step_text,
        safety_notes=notes,
        proceed_allowed=proceed_allowed,
        proceed_block_reason=proceed_reason,
        executable_command=executable_command,
        execution_mode=execution_mode,
    )


def classify_intent(user_text: str) -> EngelAIPlan:
    text = str(user_text or "").strip()
    normalized = normalize_text(text)

    if not normalized:
        return _base_plan(
            text,
            intent_type="unknown_command_candidate",
            matched_route="none",
            action_summary="Empty request; nothing to classify.",
            risk_level="low",
            deterministic_route_required=False,
            next_step_text="Type `ai plan <request>` or an exact deterministic command.",
        )

    if normalized in {"hi", "hello", "hey", "hi engel", "hello engel"}:
        return _base_plan(
            text,
            intent_type="companion_chat",
            matched_route="Local companion chat",
            action_summary="Local companion response only.",
            risk_level="low",
            model_allowed=True,
            model_allowed_scope="optional companion phrasing only; output remains untrusted and cannot execute",
            deterministic_route_required=False,
            can_execute_now=True,
            suggested_command="",
            next_step_text="Use normal chat or an exact deterministic command.",
        )

    if normalized.startswith("prompt injection check ") or normalized in {"prompt injection status"}:
        return _base_plan(
            text,
            intent_type="prompt_injection_check",
            matched_route="Human Command Mode",
            action_summary="Read-only prompt-injection guard diagnostic.",
            target_summary=text,
            risk_level="low",
            can_execute_now=True,
            suggested_command=text,
            next_step_text="Run the exact diagnostic command if you want the guard output.",
        )

    if _matches_authority_inversion(text):
        return _base_plan(
            text,
            intent_type="authority_inversion_attempt",
            matched_route="Guardian safety block",
            action_summary="Blocked attempt to reorder the fixed authority hierarchy.",
            target_summary="authority hierarchy",
            risk_level="blocked",
            approval_required=False,
            can_execute_now=False,
            blocked=True,
            block_reason=AUTHORITY_BLOCK_REASON,
            suggested_command="prompt injection check <text>",
            next_step_text="Do not run this as an action. Use `prompt injection check <text>` only as a diagnostic if needed.",
            safety_notes=["Authority inversion attempts cannot be approved by Guardian or Engel/runtime."],
        )

    prompt_check = check_prompt_injection(text)
    if prompt_check.verdict in {"block", "review"}:
        return _base_plan(
            text,
            intent_type="unsafe_or_blocked",
            matched_route="Prompt Injection Guard",
            action_summary="Blocked or review-required prompt-injection risk.",
            target_summary="untrusted user text",
            risk_level="blocked" if prompt_check.verdict == "block" else "high",
            blocked=True,
            block_reason=f"Prompt-injection guard verdict={prompt_check.verdict} score={prompt_check.score:.2f}.",
            suggested_command="prompt injection check <text>",
            next_step_text="Use the diagnostic command only; no action should run from this text.",
        )

    if normalized in KNOWN_EXACT_COMMANDS:
        return _base_plan(
            text,
            intent_type="known_command",
            matched_route="Existing deterministic route",
            action_summary="Exact known command.",
            target_summary=text,
            risk_level="low",
            can_execute_now=True,
            suggested_command=text,
            next_step_text="Run the exact deterministic command if you want Engel to proceed.",
        )

    if normalized.startswith("python teaching mode status") or normalized.startswith("python lesson help") or normalized.startswith("python learning path"):
        return _base_plan(
            text,
            intent_type="python_teaching",
            matched_route="Human Command Mode / Python Teaching Mode",
            action_summary="Read-only Python teaching/status route.",
            target_summary=text,
            risk_level="low",
            can_execute_now=True,
            suggested_command=text,
        )

    if normalized.startswith("run python lesson "):
        token_present = normalized.endswith(" approve_run")
        return _base_plan(
            text,
            intent_type="python_lesson_run",
            matched_route="Human Command Mode / Python Teaching Mode",
            action_summary="Bounded Python lesson run under lesson-only guardrails.",
            target_summary=text,
            risk_level="medium",
            approval_required=True,
            approval_token="APPROVE_RUN",
            can_execute_now=token_present,
            suggested_command=text if token_present else text + " APPROVE_RUN",
            next_step_text="Run only the exact Python lesson command with APPROVE_RUN if the lesson path is approved.",
        )

    if "offline seed" in normalized or "offline llm" in normalized or "engel mind seed" in normalized:
        return _base_plan(
            text,
            intent_type="offline_seed_brain_status",
            matched_route="Human Command Mode",
            action_summary="Read-only Offline Seed LLM status.",
            risk_level="low",
            can_execute_now=True,
            suggested_command="offline seed llm status",
        )

    if "communication queen" in normalized and "status" in normalized:
        return _base_plan(
            text,
            intent_type="communication_queen_status",
            matched_route="Human Command Mode",
            action_summary="Read-only Communication Queen scaffold/status view.",
            risk_level="low",
            can_execute_now=True,
            suggested_command="communication queen status",
            safety_notes=["Communication Queen runtime remains disabled."],
        )

    if "colony hive" in normalized or "hive status" in normalized or "queen links" in normalized or "mycelium" in normalized:
        return _base_plan(
            text,
            intent_type="colony_hive_status",
            matched_route="Human Command Mode",
            action_summary="Read-only local Hive/colony status surface.",
            risk_level="low",
            can_execute_now=True,
            suggested_command="colony hive status",
        )

    if "authority" in normalized or "hierarchy" in normalized or "who is above" in normalized:
        return _base_plan(
            text,
            intent_type="authority_hierarchy_status",
            matched_route="Authority Hierarchy Guard",
            action_summary="Explain fixed authority order.",
            target_summary="authority hierarchy",
            risk_level="low",
            deterministic_route_required=False,
            suggested_command="prompt injection status",
            next_step_text="Review the fixed hierarchy: " + AUTHORITY_BOUNDARY + ".",
        )

    if _contains_any(normalized, REMOTE_QUEEN_PATTERNS):
        return _base_plan(
            text,
            intent_type="remote_queen_request",
            matched_route="Blocked/proposal-only Remote Queen boundary",
            action_summary="Remote Queen runtime/device/network request.",
            target_summary=text,
            risk_level="blocked",
            approval_required=True,
            blocked=True,
            block_reason="Remote Queen runtime remains disabled until separately approved and verified.",
            suggested_command="colony hive remote queens",
            next_step_text="Use read-only Remote Queen status only; do not start WiFi, pairing, or runtime behavior.",
            safety_notes=["No WiFi discovery, pairing, remote execution, or background service is enabled."],
        )

    if _contains_any(normalized, AUTONOMY_PATTERNS):
        return _base_plan(
            text,
            intent_type="autonomy_request",
            matched_route="Guardian safety block",
            action_summary="Autonomy/background/loop request.",
            target_summary=text,
            risk_level="blocked",
            approval_required=True,
            blocked=True,
            block_reason="Autonomy, background workers, hidden timed jobs, and self-directed action remain disabled.",
            next_step_text="Create a proposal/report only if a future approved autonomy contract exists.",
        )

    if _contains_any(normalized, SOURCE_EDIT_PATTERNS) or re.search(r"\bedit\s+\S+\.py\b", normalized):
        return _base_plan(
            text,
            intent_type="source_edit_request",
            matched_route="Source-edit contract required",
            action_summary="Source/code/route edit request.",
            target_summary=text,
            risk_level="high",
            approval_required=True,
            blocked=False,
            suggested_command="create a source-edit plan/report first",
            next_step_text="Prepare a source-edit plan with scope, backup, verifier list, and explicit approval before editing.",
            safety_notes=["Planner output does not edit source."],
        )

    if _contains_any(normalized, TRUSTED_MEMORY_PATTERNS):
        return _base_plan(
            text,
            intent_type="trusted_memory_request",
            matched_route="Trusted-memory approval gate",
            action_summary="Trusted-memory write request.",
            target_summary=text,
            risk_level="high",
            approval_required=True,
            blocked=True,
            block_reason="Automatic trusted-memory writes are disabled.",
            suggested_command="create a memory proposal/report if an approved route exists",
            next_step_text="Keep this as an untrusted proposal until Josh approves a verifier-covered trusted-memory path.",
        )

    if _contains_any(normalized, QUEUE_ROUTE_MUTATION_PATTERNS):
        return _base_plan(
            text,
            intent_type="queue_or_route_mutation_request",
            matched_route="Queue/route mutation approval gate",
            action_summary="Queue or route mutation request.",
            target_summary=text,
            risk_level="high",
            approval_required=True,
            blocked=True,
            block_reason="Queue and route mutation are not available from the AI planner.",
            next_step_text="Create a separate approved route-change plan/report before any mutation.",
        )

    if _contains_any(normalized, SYSTEM_INSTALL_PATTERNS):
        return _base_plan(
            text,
            intent_type="package_or_system_install_request",
            matched_route="System install blocked",
            action_summary="Package/system installer request.",
            target_summary=text,
            risk_level="blocked",
            approval_required=True,
            blocked=True,
            block_reason="System installs require a separate approved task with exact installer/source and rollback plan.",
            suggested_command="dependency install plan <package> for <reason>",
            next_step_text="Use dependency planning only; no install happens from this plan.",
        )

    if normalized.startswith("install dependency ") or normalized.startswith("dependency install plan "):
        package, reason = _package_reason_from_install_dependency(text)
        target = package or text
        suggested = text
        approval_required = normalized.startswith("install dependency ")
        if normalized.startswith("install dependency "):
            if package and reason:
                suggested = f"install dependency {package} for {reason} APPROVE_INSTALL"
            else:
                suggested = "install dependency <package> for <reason> APPROVE_INSTALL"
        return _base_plan(
            text,
            intent_type="human_dependency_install",
            matched_route="Human Command Mode approved dependency install",
            action_summary="Dependency install planning or exact approval-token route.",
            target_summary=target,
            risk_level="high",
            approval_required=approval_required,
            approval_token="APPROVE_INSTALL" if approval_required else "",
            can_execute_now=normalized.endswith(" approve_install"),
            suggested_command=suggested,
            next_step_text="No install happens from this plan. Run the exact deterministic command only after review.",
            safety_notes=["Dependency install route uses the existing approval token; planner does not install packages."],
        )

    if normalized.startswith("install package ") or normalized.startswith("request package install "):
        return _base_plan(
            text,
            intent_type="package_or_system_install_request",
            matched_route="Human Command Mode package install request/proposal",
            action_summary="Package install request; not executed by planner.",
            target_summary=text,
            risk_level="high",
            approval_required=True,
            suggested_command="request package install <package> for <reason>",
            next_step_text="Use proposal/planning routes only; no install happens from this plan.",
        )

    if normalized.startswith("install local file ") or "copy file" in normalized:
        return _base_plan(
            text,
            intent_type="human_local_install_copy",
            matched_route="Human Command Mode guarded local copy",
            action_summary="Guarded local file copy/install into approved Engel folders.",
            target_summary=text,
            risk_level="medium",
            suggested_command=text if normalized.startswith("install local file ") else "install local file <source_path> to <destination_folder>",
            next_step_text="Run only the exact deterministic copy command if source and destination are approved.",
        )

    if normalized.startswith("put text in file ") or "write file" in normalized or "put this in file" in normalized:
        return _base_plan(
            text,
            intent_type="human_file_write",
            matched_route="Human Command Mode guarded write",
            action_summary="Guarded exact inline file write.",
            target_summary=text,
            risk_level="medium",
            suggested_command=text if normalized.startswith("put text in file ") else "put text in file <path> :: <text>",
            next_step_text="Run only the exact deterministic write command under approved write roots.",
            safety_notes=["Planner output does not write files."],
        )

    report_requested = bool(
        re.search(r"\b(make|create|write|generate)\s+(me\s+)?(a\s+)?report\b", normalized)
        or " to report " in (" " + normalized + " ")
    )
    if normalized.startswith("research file ") or normalized.startswith("research this file "):
        target = _extract_after_prefix(text, ("research file ", "research this file "))
        return _base_plan(
            text,
            intent_type="human_file_research",
            matched_route="Human Command Mode",
            action_summary="Bounded local file research.",
            target_summary=target,
            risk_level="low",
            can_execute_now=normalized.startswith("research file "),
            suggested_command="research file " + (target or "<path>"),
        )

    if (
        normalized.startswith("research folder ")
        or normalized.startswith("research this folder ")
        or normalized.startswith("summarize folder ")
        or "research this folder" in normalized
    ):
        rest = _extract_after_prefix(text, ("research folder ", "research this folder ", "summarize folder "))
        target, report_name = _split_keyword(rest, "to report")
        target = _strip_report_request_suffix(target)
        if report_requested:
            suggested = "research folder " + (target or "<path>") + " to report " + (report_name or "<name.md>")
            return _base_plan(
                text,
                intent_type="human_report_write",
                matched_route="Human Command Mode",
                action_summary="Bounded folder research plus approved-root report write.",
                target_summary=target,
                risk_level="medium",
                approval_required=False,
                suggested_command=suggested,
                next_step_text="Run the suggested deterministic command only if the report name stays under approved report roots.",
                safety_notes=["Report output remains untrusted until reviewed."],
            )
        return _base_plan(
            text,
            intent_type="human_file_research",
            matched_route="Human Command Mode",
            action_summary="Bounded folder research.",
            target_summary=target,
            risk_level="low",
            can_execute_now=normalized.startswith("research folder "),
            suggested_command="research folder " + (target or "<path>"),
        )

    if "gui" in normalized or "layout" in normalized or "view" in normalized or "readability" in normalized:
        return _base_plan(
            text,
            intent_type="gui_view_or_layout_request",
            matched_route="GUI/source-edit planning boundary",
            action_summary="GUI/view/layout improvement request.",
            target_summary=text,
            risk_level="medium",
            approval_required=True,
            suggested_command="create a GUI/source-edit plan first",
            next_step_text="Treat GUI changes as source-edit work with backup and verifier checks.",
            safety_notes=["Planner does not add buttons or execute GUI actions."],
        )

    if "check this for prompt injection" in normalized or "scan this for prompt injection" in normalized:
        return _base_plan(
            text,
            intent_type="prompt_injection_check",
            matched_route="Human Command Mode",
            action_summary="Read-only prompt-injection check.",
            target_summary=text,
            risk_level="low",
            suggested_command="prompt injection check <text>",
        )

    return _base_plan(
        text,
        intent_type="unknown_command_candidate",
        matched_route="none",
        action_summary="No safe deterministic route matched.",
        target_summary=text,
        risk_level="medium",
        deterministic_route_required=True,
        suggested_command="ai plan <more specific request>",
        next_step_text="Ask for a plan with a clearer target or use an exact deterministic command.",
        safety_notes=["Unknown requests are not auto-executed."],
    )


def build_plan(user_text: str) -> EngelAIPlan:
    return classify_intent(user_text)


def _yes_no(value: bool) -> str:
    return "yes" if bool(value) else "no"


def render_classification(plan: EngelAIPlan) -> str:
    return "\n".join(
        [
            "# Engel AI Classification",
            "",
            "intent_type: " + plan.intent_type,
            "matched_route: " + (plan.matched_route or "none"),
            "risk_level: " + plan.risk_level,
            "approval_required: " + _yes_no(plan.approval_required),
            "blocked: " + _yes_no(plan.blocked),
            "suggested_command: " + (plan.suggested_command or "none"),
            "proceed_allowed: " + _yes_no(plan.proceed_allowed),
            "execution_mode: " + plan.execution_mode,
            "executable_command: " + (plan.executable_command or "none"),
            "proceed_block_reason: " + (plan.proceed_block_reason or "none"),
            "authority: " + AUTHORITY_BOUNDARY,
            "",
            "Safety: classification only; no action executed.",
        ]
    )


def render_plan(plan: EngelAIPlan) -> str:
    lines = [
        "# Engel AI Plan",
        "",
        "Intent: " + plan.intent_type,
        "Route: " + (plan.matched_route or "none"),
        "Action: " + (plan.action_summary or "none"),
        "Target: " + (plan.target_summary or "none"),
        "Risk: " + plan.risk_level,
        "Approval: " + ("required" if plan.approval_required else "not required for the plan itself"),
        "Approval token: " + (plan.approval_token or "none"),
        "Guardian: " + ("required" if plan.guardian_required else "not required"),
        "Prompt-injection check: " + ("required before model use or action" if plan.prompt_injection_check_required else "not required"),
        "Authority: " + AUTHORITY_BOUNDARY,
        "Model: " + ("allowed only for " + plan.model_allowed_scope if plan.model_allowed else plan.model_allowed_scope),
        "Deterministic route required: " + _yes_no(plan.deterministic_route_required),
        "Can execute now: " + _yes_no(plan.can_execute_now),
        "Blocked: " + _yes_no(plan.blocked),
        "Execution mode: " + plan.execution_mode,
        "Proceed allowed: " + _yes_no(plan.proceed_allowed),
        "Executable command: " + (plan.executable_command or "none"),
    ]
    if plan.block_reason:
        lines.append("Block reason: " + plan.block_reason)
    if plan.proceed_block_reason:
        lines.append("Proceed block reason: " + plan.proceed_block_reason)
    lines.extend(
        [
            "Suggested command: " + (plan.suggested_command or "none"),
            "Next step: " + (plan.next_step_text or "none"),
            "",
            "Safety notes:",
        ]
    )
    for note in plan.safety_notes:
        lines.append("- " + note)
    return "\n".join(lines)


def render_help() -> str:
    return "\n".join(
        [
            "# Engel AI Intent + Plan Layer",
            "",
            "What it does:",
            "- Classifies user input.",
            "- Shows a visible safe plan.",
            "- Suggests deterministic commands through existing guardrails.",
            "",
            "What it does not do:",
            "- It does not execute unsafe actions.",
            "- It does not give the model command authority.",
            "- GUI Proceed can run only approval-free allowlisted deterministic routes.",
            "- It does not call providers, APIs, network, or cloud fallback.",
            "- It does not enable autonomy, background workers, Remote Queen runtime, trusted-memory writes, queue mutation, or source-edit autonomy.",
            "",
            "Authority:",
            "- " + AUTHORITY_BOUNDARY,
            "",
            "Commands:",
            "- ai help",
            "- ai planner status",
            "- ai classify <text>",
            "- ai plan <text>",
            "",
            "Use exact deterministic commands to execute approved actions.",
        ]
    )


def render_status() -> str:
    return "\n".join(
        [
            "# Engel AI Planner Status",
            "",
            "Planner enabled: yes",
            "Deterministic classification: yes",
            "Model execution authority: blocked",
            "Guardian required: yes",
            "Josh-first authority: yes",
            "Authority: " + AUTHORITY_BOUNDARY,
            "Supported intent count: " + str(len(SUPPORTED_INTENT_TYPES)),
            "Provider/API/network: disabled",
            "Autonomy/background workers: disabled",
            "Plan commands execute target actions: no",
            "GUI Proceed route: approval-free allowlisted deterministic commands only",
        ]
    )


SUPPORTED_INTENT_TYPES = (
    "companion_chat",
    "known_command",
    "human_file_research",
    "human_report_write",
    "human_file_write",
    "human_local_install_copy",
    "human_dependency_install",
    "python_teaching",
    "python_lesson_run",
    "offline_seed_brain_status",
    "colony_hive_status",
    "prompt_injection_check",
    "authority_hierarchy_status",
    "remote_queen_request",
    "communication_queen_status",
    "gui_view_or_layout_request",
    "package_or_system_install_request",
    "source_edit_request",
    "trusted_memory_request",
    "queue_or_route_mutation_request",
    "autonomy_request",
    "authority_inversion_attempt",
    "unsafe_or_blocked",
    "unknown_command_candidate",
)
