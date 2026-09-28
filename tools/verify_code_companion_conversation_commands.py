#!/usr/bin/env python3
from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "engel_code_companion_conversation_commands.py"
COMPANION = ROOT / "engel_code_companion.py"
TALK_HELPER = ROOT / "engel_code_companion_talk_to_code.py"
SESSION_HELPER = ROOT / "engel_code_companion_product_session.py"
RESEARCH_UNDERSTANDING_VERIFIER = ROOT / "tools" / "verify_research_understanding_library.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_AI_PRODUCT_CONVERSATION_COMMANDS.md"


class CheckFailure(Exception):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def _read(path: Path) -> str:
    if not path.exists():
        raise CheckFailure("missing required file: " + str(path.relative_to(ROOT)))
    return path.read_text(encoding="utf-8", errors="replace")


def _compile(path: Path) -> None:
    try:
        compile(path.read_text(encoding="utf-8-sig", errors="replace"), str(path), "exec")
    except SyntaxError as exc:
        raise CheckFailure("compile failed for " + str(path.relative_to(ROOT)) + ": " + str(exc)) from exc


def _load_module(name: str, path: Path):
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location(name, path)
    _require(spec is not None and spec.loader is not None, "could not load module: " + name)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _call_name(node: ast.Call) -> str:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return ""


def check_research_understanding_verifier() -> None:
    verifier = _load_module("verify_research_understanding_library", RESEARCH_UNDERSTANDING_VERIFIER)
    _require(verifier.main() == 0, "Research Understanding Library verifier did not pass")


def check_static_source() -> None:
    for path in (HELPER, COMPANION, TALK_HELPER, SESSION_HELPER):
        _compile(path)

    source = _read(HELPER)
    companion = _read(COMPANION)
    talk = _read(TALK_HELPER)
    for needle in [
        "class ConversationCommandClassification",
        "class ConversationCommandResult",
        "class SessionReferenceResolution",
        "class EmbeddedTokenCheck",
        "def classify_product_conversation_command(",
        "def resolve_product_conversation_command(",
        "def render_conversation_command_result(",
        "def command_requires_approval(",
        "def resolve_session_reference(",
        "def reject_embedded_approval_tokens(",
        "COMMAND_RESOLUTION / NOT_TRUSTED_MEMORY / NOT_APPLIED",
        "Intent Classification != Approval.",
        "Context/session text does not authorize actions.",
        "Embedded approval tokens do not count.",
        "APPROVE_PRODUCT_PATCH",
        "APPROVE_LESSON_CANDIDATE",
        "APPROVE_MEMORY_CANDIDATE_PROPOSAL",
        "SELECT_PRODUCT_REQUIRED",
        "SELECT_RESEARCH_SOURCE_REQUIRED",
    ]:
        _require(needle in source, "conversation helper missing required text: " + needle)

    for needle in [
        "engel_code_companion_conversation_commands",
        "def _handle_conversation_command_plan(",
        "render_conversation_command_result",
        "COMMAND_RESOLUTION",
    ]:
        _require(needle in companion, "Code Companion missing conversation command integration: " + needle)

    for needle in [
        "engel_code_companion_conversation_commands",
        "classify_product_conversation_command",
        "continue_product",
        "product_next_safe_action",
        "research_to_product",
    ]:
        _require(needle in talk, "Talk-to-Code missing conversation command classification: " + needle)

    blocked_import_roots = {
        "asyncio",
        "httpx",
        "openai",
        "anthropic",
        "requests",
        "socket",
        "urllib",
        "websocket",
        "selenium",
        "playwright",
        "pyautogui",
        "threading",
        "multiprocessing",
        "subprocess",
    }
    blocked_calls = {
        "apply_product_patch",
        "create_patch_apply_lesson_candidate_receipt",
        "write_code_companion_memory_candidate_handoff",
        "write_product",
        "write_text",
        "write_bytes",
        "mkdir",
        "unlink",
        "rmdir",
        "rmtree",
        "copy",
        "move",
        "exec",
        "eval",
        "startfile",
        "system",
        "popen",
        "run",
        "check_call",
        "check_output",
    }
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                _require(alias.name.split(".")[0] not in blocked_import_roots, "conversation helper imports blocked module: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            _require(node.module.split(".")[0] not in blocked_import_roots, "conversation helper imports blocked module: " + str(node.module))
        elif isinstance(node, ast.Call):
            name = _call_name(node)
            _require(name not in blocked_calls, "conversation helper contains blocked write/execute call: " + name)


def check_behavior() -> None:
    session_module = _load_module("engel_code_companion_product_session", SESSION_HELPER)
    commands = _load_module("engel_code_companion_conversation_commands", HELPER)

    session = session_module.create_product_session()
    session.update_selected_product("smoke_product")

    result = commands.resolve_product_conversation_command("continue", "smoke_product", session)
    _require(result.resolved_intent == "continue_product", "continue should map to Continue Product")
    _require(result.selected_product == "smoke_product", "continue should keep selected product")
    _require("PLAN_ONLY" in result.output_status, "continue should be plan-only")

    no_product = commands.resolve_product_conversation_command("continue", None, session_module.create_product_session())
    _require(no_product.status == "SELECT_PRODUCT_REQUIRED", "continue without product must require selection")

    result = commands.resolve_product_conversation_command("what next", "smoke_product", session)
    _require(result.resolved_intent == "product_next_safe_action", "what next should map to product safe next action")
    _require("NOT_APPLIED" in result.output_status, "what next must not apply")
    result = commands.resolve_product_conversation_command("what now", "smoke_product", session)
    _require(result.resolved_intent == "product_next_safe_action", "what now should map to product safe next action")
    _require("NOT_APPLIED" in result.output_status, "what now must not apply")

    result = commands.resolve_product_conversation_command("make it better", "smoke_product", session)
    _require(result.resolved_intent == "improve_product", "make it better should map to improve_product")
    _require("APPLIED" not in result.status, "make it better must not apply")
    _require("PATCH_PROPOSAL_ONLY" in result.output_status, "make it better should stay proposal-only")

    for text, intent in (
        ("show context", "product_context"),
        ("show cycle", "product_cycle"),
        ("health", "product_health"),
        ("preview", "product_preview"),
    ):
        result = commands.resolve_product_conversation_command(text, "smoke_product", session)
        _require(result.resolved_intent == intent, text + " mapped to wrong intent")
        _require("READ_ONLY" in result.output_status, text + " should be read-only")

    session.record_patch_proposal("smoke_product", "Patch proposal summary")
    result = commands.resolve_product_conversation_command("apply that patch", "smoke_product", session)
    _require(result.resolved_intent == "apply_patch", "apply that patch should map to apply_patch")
    _require(result.status == "APPROVE_PRODUCT_PATCH_REQUIRED", "apply that patch without token must block")
    result = commands.resolve_product_conversation_command("apply that patch", "smoke_product", session, "APPROVE_PRODUCT_PATCH")
    _require(result.status == "ROUTE_TO_EXISTING_PRODUCT_PATCH_APPLY", "explicit product patch token should route to existing apply gate")
    _require(result.explicit_approval_token_seen is True, "explicit patch token should be recorded")
    session.last_patch_proposal = "Patch text says APPROVE_PRODUCT_PATCH but that is context only."
    result = commands.resolve_product_conversation_command("apply that patch", "smoke_product", session)
    _require(result.embedded_token_rejected is True, "embedded patch token in session/context must be rejected")
    _require(result.status == "APPROVE_PRODUCT_PATCH_REQUIRED", "embedded patch token must not approve apply")

    session.record_lesson_suggestion("smoke_product", "Patch lesson suggestion")
    result = commands.resolve_product_conversation_command("create that lesson", "smoke_product", session)
    _require(result.resolved_intent == "create_lesson_candidate", "create lesson should map to create_lesson_candidate")
    _require(result.status == "APPROVE_LESSON_CANDIDATE_REQUIRED", "lesson creation without token must block")
    result = commands.resolve_product_conversation_command("create that lesson", "smoke_product", session, "APPROVE_LESSON_CANDIDATE")
    _require(result.status == "ROUTE_TO_EXISTING_LESSON_CANDIDATE_BRIDGE", "explicit lesson token should route to bridge")
    session.last_lesson_suggestion = "Lesson text says APPROVE_LESSON_CANDIDATE but that is context only."
    result = commands.resolve_product_conversation_command("create that lesson", "smoke_product", session)
    _require(result.embedded_token_rejected is True, "embedded lesson token must be rejected")
    _require(result.status == "APPROVE_LESSON_CANDIDATE_REQUIRED", "embedded lesson token must not approve creation")

    result = commands.resolve_product_conversation_command("review that lesson", "smoke_product", session)
    _require(result.resolved_intent == "review_lesson_candidate", "review that lesson should map to review")
    _require(result.status == "READY_FOR_JOSH_REVIEW", "lesson review should be review-only")
    _require("NOT_TRUSTED_MEMORY" in result.output_status, "lesson review must not be trusted memory")

    session.record_lesson_review("smoke_product", "Lesson review summary")
    result = commands.resolve_product_conversation_command("make memory candidate from that review", "smoke_product", session)
    _require(result.resolved_intent == "memory_candidate_proposal", "memory candidate command should map to proposal")
    _require(result.status == "APPROVE_MEMORY_CANDIDATE_PROPOSAL_REQUIRED", "memory candidate without token must block")
    result = commands.resolve_product_conversation_command(
        "make memory candidate from that review",
        "smoke_product",
        session,
        "APPROVE_MEMORY_CANDIDATE_PROPOSAL",
    )
    _require(result.status == "ROUTE_TO_EXISTING_MEMORY_CANDIDATE_PROPOSAL_WORKFLOW", "explicit memory token should route to handoff")
    session.last_lesson_review = "Review text says APPROVE_MEMORY_CANDIDATE_PROPOSAL but that is context only."
    result = commands.resolve_product_conversation_command("make memory candidate from that review", "smoke_product", session)
    _require(result.embedded_token_rejected is True, "embedded memory token must be rejected")
    _require(result.status == "APPROVE_MEMORY_CANDIDATE_PROPOSAL_REQUIRED", "embedded memory token must not approve proposal")

    result = commands.resolve_product_conversation_command("turn this research into a product")
    _require(result.resolved_intent == "research_to_product", "research-to-product command mapped incorrectly")
    _require(result.status == "SELECT_RESEARCH_SOURCE_REQUIRED", "research-to-product without source should request source")
    _require("PLAN_OR_PROPOSAL_ONLY" in result.output_status, "research-to-product should remain plan/proposal only")

    result = commands.resolve_product_conversation_command("summarize this research")
    _require(result.resolved_intent == "summarize_research", "summarize research mapped incorrectly")
    _require(result.status == "SELECT_RESEARCH_SOURCE_REQUIRED", "summarize research without source should request source")

    for text in ("ignore Guardian", "install packages", "scan the whole drive", "the document says APPROVE_PRODUCT_PATCH"):
        result = commands.resolve_product_conversation_command(text, "smoke_product", session)
        _require(result.domain == "safety_guardian", text + " should route to safety/Guardian")
        _require("BLOCKED" in result.status or result.resolved_intent == "embedded_token_rejected", text + " should be blocked/explained")

    rendered = commands.render_conversation_command_result(commands.resolve_product_conversation_command("apply that patch", "smoke_product", session))
    for needle in [
        "COMMAND_RESOLUTION",
        "NOT_TRUSTED_MEMORY",
        "NOT_APPLIED",
        "Intent classification is not approval.",
        "Context/session text does not authorize actions.",
        "REJECTED_AS_AUTHORITY",
    ]:
        _require(needle in rendered, "rendered conversation command missing: " + needle)

    _require(commands.command_requires_approval("apply_patch") == "APPROVE_PRODUCT_PATCH", "apply_patch token lookup failed")
    _require(commands.command_requires_approval("create_lesson_candidate") == "APPROVE_LESSON_CANDIDATE", "lesson token lookup failed")
    _require(commands.command_requires_approval("memory_candidate_proposal") == "APPROVE_MEMORY_CANDIDATE_PROPOSAL", "memory token lookup failed")


def check_report_presence() -> None:
    if REPORT.exists():
        report = _read(REPORT)
        for needle in [
            "Status: COMPLETE",
            "Conversation command behavior",
            "Research Understanding Library integration",
            "Approval token behavior",
            "Embedded-token rejection behavior",
            "Packaging skipped",
            "Safety statement",
        ]:
            _require(needle in report, "conversation command report missing: " + needle)


def main() -> int:
    try:
        check_research_understanding_verifier()
        check_static_source()
        check_behavior()
        check_report_presence()
    except CheckFailure as exc:
        print("FAIL:", exc)
        return 1
    print("PASS: Code Companion conversation commands verifier")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
