from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any

import engel_code_companion_examples as example_scripts
import engel_code_companion_contextual_talk as contextual_talk
import engel_code_companion_conversation_commands as conversation_commands
import engel_code_companion_continue_product as continue_product
import engel_code_companion_patch_apply as patch_apply
import engel_code_companion_patch_proposals as patch_proposals
import engel_code_companion_project_builder as project_builder
import engel_code_companion_product_session as product_session
import engel_code_companion_products as product_templates
import engel_research_summary_proposals as research_summaries
import engel_untrusted_content_guard as untrusted_content_guard


AUTHORITY = "Josh > Guardian > Engel/runtime"
PLAN_ONLY = "PLAN_ONLY"
READY_TO_CREATE = "READY_TO_CREATE"
BLOCKED = "BLOCKED"
NOT_RUNTIME = "NOT_RUNTIME"
NOT_APPLIED = "NOT_APPLIED"
PROPOSAL_ONLY = "PROPOSAL_ONLY"
PRODUCT_IMPROVEMENT_PROPOSAL = "PRODUCT_IMPROVEMENT_PROPOSAL"
PRODUCT_PATCH_PROPOSAL = patch_proposals.PRODUCT_PATCH_PROPOSAL
CONTINUE_PRODUCT_PLAN = continue_product.CONTINUE_PRODUCT_PLAN
RESEARCH_TO_PRODUCT_PLAN = "RESEARCH_TO_PRODUCT_PLAN"
PROJECT_BUILDER_PLAN = project_builder.PROJECT_BUILDER_PLAN
SELECT_PRODUCT_REQUIRED = "SELECT_PRODUCT_REQUIRED"
SELECT_RESEARCH_SUMMARY_REQUIRED = "SELECT_RESEARCH_SUMMARY_REQUIRED"
HIGH_RISK_RESEARCH_SOURCE = "HIGH_RISK_RESEARCH_SOURCE"

SCRIPT_TARGETS = {"python_script", "java_script", "html_page"}
PRODUCT_TARGETS = {
    "python_cli_product",
    "python_gui_product",
    "java_console_product",
    "html_dashboard_product",
    "html_mini_app_product",
}

UNSAFE_REQUEST_PATTERNS: tuple[tuple[str, str], ...] = (
    ("runtime source edit", r"\b(edit|modify|patch|rewrite|change)\b.{0,60}\b(engel runtime|runtime source|engel source|engel_app|engel_companion)\b"),
    ("guardian bypass", r"\b(ignore|bypass|disable|override)\b.{0,40}\b(guardian|safety|authority)\b"),
    ("authority inversion", r"\b(guardian\s+(is|should be|must be).{0,25}(above|higher than)\s+josh|josh\s+(is\s+)?not\s+required)\b"),
    ("package install", r"\b(install|pip install|npm install|add package|download package)\b"),
    ("powershell command", r"\b(powershell|start-process|cmd\.exe|shell command|run command)\b"),
    ("delete files", r"\b(delete|remove|wipe|rmtree|unlink)\b.{0,40}\b(file|folder|directory|project|source|runtime)\b"),
    ("api or provider call", r"\b(call|use|connect to|send to)\b.{0,40}\b(api|openai|provider|anthropic|network)\b"),
    ("network use", r"\b(use network|fetch|requests|socket|websocket|http://|https://|scrape)\b"),
    ("credential access", r"\b(scrape|steal|read|exfiltrate|upload)\b.{0,40}\b(credential|cookie|token|password|secret|api key)\b"),
    ("auto approval", r"\b(auto[- ]?approve|approve automatically|accept approval token from file|APPROVE_[A-Z_]+)\b"),
    ("trusted memory write", r"\b(write|update|store|make permanent)\b.{0,40}\b(trusted memory|memory index|durable memory)\b"),
    ("browser launch", r"\b(launch|open|drive|control)\b.{0,35}\b(browser|chrome|edge|firefox)\b"),
    ("hidden action", r"\b(hide this from josh|secretly|without josh|do not tell josh)\b"),
    ("execute now", r"\b(execute|run)\b.{0,40}\b(this code|generated code|now|immediately)\b"),
)

IMPROVEMENT_REQUEST_PATTERNS: tuple[str, ...] = (
    r"\bimprove\s+this\s+product\b",
    r"\bimprove\s+selected\s+product\b",
    r"\bmake\s+this\s+product\s+better\b",
    r"\bmake\s+(the\s+)?readme\s+better(\s+too)?\b",
    r"\bmake\s+the\s+docs\s+better(\s+too)?\b",
    r"\badd\s+better\s+readme\b",
    r"\badd\s+instructions\b",
    r"\badd\s+tests\b",
    r"\badd\s+smoke\s+test\b",
    r"\badd\s+test\s+plan\b",
    r"\bimprove\s+docs\b",
    r"\bmake\s+this\s+product\s+easier\s+to\s+use\b",
    r"\bmake\s+product\s+easier\s+to\s+use\b",
    r"\bimprove\s+manifest\b",
    r"\bpatch\s+proposal\b",
    r"\bpropose\s+changes\b",
    r"\bimprove\s+dashboard\s+copy\b",
    r"\bimprove\s+product\s+health\b",
    r"\bfix\s+product\s+warnings\b",
    r"\bbetter\s+instructions\b",
    r"\bbetter\s+tests\b",
)

RESEARCH_TO_PRODUCT_REQUEST_PATTERNS: tuple[str, ...] = (
    r"\bmake\s+a\s+product\s+from\s+this\s+research\s+summary\b",
    r"\bturn\s+this\s+research\s+into\s+a\s+dashboard\b",
    r"\bcreate\s+a\s+product\s+plan\s+from\s+this\s+intake\b",
    r"\bmake\s+an?\s+app\s+from\s+this\s+research\b",
    r"\bbuild\s+a\s+tool\s+from\s+this\s+summary\b",
    r"\bmake\s+a\s+product\s+from\s+this\s+research\b",
    r"\bcreate\s+a\s+product\s+from\s+this\s+summary\b",
    r"\buse\s+this\s+research\s+to\s+create\s+a\s+product\b",
    r"\bmake\s+a\s+code\s+companion\s+product\s+from\s+this\s+research\b",
)


@dataclass(frozen=True)
class TalkToCodeIntent:
    raw_text: str
    intent_type: str
    language: str
    product_template: str
    product_name: str
    file_name: str
    selected_product: str
    research_summary_id: str = ""
    research_intake_receipt_id: str = ""
    research_source_kind: str = ""
    research_source_label: str = ""
    research_risk_level: str = ""
    unsafe_markers: tuple[str, ...] = field(default_factory=tuple)
    requires_approval: bool = False
    blocked_reason: str = ""


@dataclass(frozen=True)
class TalkToCodePlan:
    status: str
    idea_summary: str
    target_type: str
    recommended_template: str
    files_to_create: tuple[str, ...]
    save_root: str
    validation_method: str
    guardian_review: tuple[str, ...]
    approval_required: bool
    safety_notes: tuple[str, ...]
    intent: TalkToCodeIntent | None = None
    not_runtime: bool = True
    not_applied: bool = True


@dataclass(frozen=True)
class TalkToCodeResult:
    ok: bool
    status: str
    path: Path | None
    files_written: tuple[Path, ...]
    validation_status: str
    message: str
    output: str
    not_runtime: bool = True
    not_applied: bool = True


def _compact_text(text: str, max_chars: int = 260) -> str:
    collapsed = " ".join((text or "").strip().split())
    if not collapsed:
        return "No idea text provided."
    if len(collapsed) > max_chars:
        return collapsed[: max_chars - 3].rstrip() + "..."
    return collapsed


def _scan_unsafe_request(text: str) -> tuple[str, ...]:
    markers: list[str] = []
    lowered = (text or "").lower()
    for label, pattern in UNSAFE_REQUEST_PATTERNS:
        if re.search(pattern, lowered, re.IGNORECASE):
            markers.append(label)
    guard = untrusted_content_guard.detect_prompt_injection_markers(text or "")
    if guard.authority_attack and "authority attack" not in markers:
        markers.append("authority attack")
    if guard.tool_attack and "tool attack" not in markers:
        markers.append("tool attack")
    if guard.memory_attack and "memory attack" not in markers:
        markers.append("memory attack")
    if guard.data_exfiltration_attack and "data exfiltration attack" not in markers:
        markers.append("data exfiltration attack")
    return tuple(dict.fromkeys(markers))


def _is_product_improvement_request(text: str) -> bool:
    lowered = (text or "").lower()
    if "improvement" in lowered and "product" in lowered:
        return True
    if "improve" in lowered and ("product" in lowered or "readme" in lowered or "docs" in lowered or "tests" in lowered):
        return True
    return any(re.search(pattern, lowered, re.IGNORECASE) for pattern in IMPROVEMENT_REQUEST_PATTERNS)


def _is_research_to_product_request(text: str) -> bool:
    lowered = (text or "").lower()
    if "research summary" in lowered and any(word in lowered for word in ("product", "dashboard", "app", "tool")):
        return True
    if "this research" in lowered and any(word in lowered for word in ("product", "dashboard", "app", "tool")):
        return True
    if "this intake" in lowered and any(word in lowered for word in ("product", "dashboard", "app", "tool")):
        return True
    if "this summary" in lowered and any(word in lowered for word in ("product", "dashboard", "app", "tool")):
        return True
    return any(re.search(pattern, lowered, re.IGNORECASE) for pattern in RESEARCH_TO_PRODUCT_REQUEST_PATTERNS)


def _is_continue_product_request(text: str) -> bool:
    return continue_product.is_continue_product_request(text)


def _extract_block(text: str, label: str) -> str:
    pattern = re.compile(r"(?im)^" + re.escape(label) + r":\s*$\n(?P<value>.+?)(?:\n\s*\n|$)", re.S)
    match = pattern.search(text or "")
    if match:
        return match.group("value").strip()
    inline = re.compile(r"(?im)^" + re.escape(label) + r":\s*(?P<value>.+)$")
    match = inline.search(text or "")
    return match.group("value").strip() if match else ""


def _risk_rank(risk_level: str) -> int:
    return {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "BLOCKED": 3}.get(str(risk_level or "LOW").upper(), 0)


def _extract_risk(text: str) -> str:
    risk = _extract_block(text, "Risk").upper()
    for value in ("BLOCKED", "HIGH", "MEDIUM", "LOW"):
        if value in risk:
            return value
    return "LOW"


def _max_risk(*risk_levels: str) -> str:
    return max((str(risk or "LOW").upper() for risk in risk_levels), key=_risk_rank)


def _research_embedded_markers(text: str) -> tuple[str, ...]:
    markers = _scan_unsafe_request(text)
    if re.search(r"\bAPPROVE_[A-Z_]+\b", text or "", re.IGNORECASE):
        markers = tuple(dict.fromkeys((*markers, "embedded approval token")))
    return markers


def _load_research_summary(summary_id: str) -> tuple[Path, str, str, str]:
    path = research_summaries.resolve_research_summary_id(summary_id)
    text = untrusted_content_guard.safe_excerpt(path.read_text(encoding="utf-8", errors="replace"), 18_000)
    guard = untrusted_content_guard.classify_untrusted_content_risk(text, "Talk-to-Code research summary: " + path.name)
    embedded_markers = _research_embedded_markers(text)
    embedded_risk = "BLOCKED" if embedded_markers else "LOW"
    risk_level = _max_risk(_extract_risk(text), guard.risk_level, embedded_risk)
    source_label = _extract_block(text, "Source label") or _extract_block(text, "Source") or path.name
    return path, text, risk_level, source_label


def _load_research_intake_receipt(receipt_id: str) -> tuple[Path, str, str, str]:
    receipt = research_summaries.read_research_intake_receipt(receipt_id)
    embedded_markers = _research_embedded_markers(receipt.text)
    embedded_risk = "BLOCKED" if embedded_markers else "LOW"
    risk_level = _max_risk(receipt.risk_level, receipt.guard_risk_level, embedded_risk)
    source_label = receipt.source_label or receipt.receipt_id
    return receipt.path, receipt.text, risk_level, source_label


def _research_template_from_text(idea_text: str, summary_text: str) -> str:
    combined = f"{idea_text}\n{summary_text}".lower()
    if "dashboard" in combined or "research notes" in combined or "report" in combined:
        return "html_dashboard_starter"
    if "app" in combined and "html" in combined:
        return "html_mini_app"
    if "gui" in combined or "window" in combined:
        return "python_gui_starter"
    if "java" in combined:
        return "java_console_starter"
    return "python_cli_starter"


def _explicit_name_from_text(text: str) -> str:
    match = re.search(r"\b(?:called|named|name(?:d)? as)\s+([a-zA-Z0-9][a-zA-Z0-9 _-]{1,80})", text or "", re.IGNORECASE)
    if not match:
        return ""
    raw = re.split(r"[.;,\n]", match.group(1), maxsplit=1)[0]
    words = _safe_words(raw, limit=6)
    return " ".join(words).title() if words else ""


def _research_product_name(idea_text: str, summary_id: str, source_label: str) -> str:
    explicit = _explicit_name_from_text(idea_text)
    if explicit:
        return explicit
    words = _safe_words(source_label or summary_id, limit=5)
    if words:
        return "Research " + " ".join(words).title()
    return "Research Summary Product"


def _safe_words(text: str, limit: int = 5) -> list[str]:
    words = re.findall(r"[a-zA-Z0-9]+", text.lower())
    filtered = [w for w in words if w not in {
        "engel",
        "create",
        "make",
        "build",
        "small",
        "simple",
        "product",
        "script",
        "app",
        "application",
        "that",
        "with",
        "has",
        "and",
        "for",
        "the",
        "a",
        "an",
        "my",
        "please",
        "called",
        "named",
    }]
    return filtered[:limit]


def _name_from_text(text: str, fallback: str) -> str:
    match = re.search(r"\b(?:called|named|name(?:d)? as)\s+([a-zA-Z0-9][a-zA-Z0-9 _-]{1,80})", text or "", re.IGNORECASE)
    if match:
        raw = match.group(1)
        raw = re.split(r"[.;,\n]", raw, maxsplit=1)[0]
        words = _safe_words(raw, limit=6)
        if words:
            return " ".join(words).title()
    words = _safe_words(text or "", limit=4)
    if words:
        return " ".join(words).title()
    return fallback


def _script_file_name(text: str, language: str) -> str:
    extensions = {"python": ".py", "java": ".java", "html": ".html"}
    extension = extensions[language]
    explicit = re.search(r"\b([A-Za-z0-9][A-Za-z0-9_-]{1,64}" + re.escape(extension) + r")\b", text or "")
    if explicit:
        return example_scripts.safe_script_name(explicit.group(1), language)
    name = _name_from_text(text, f"Engel {language.title()} Example")
    if language == "java":
        class_name = "".join(part.capitalize() for part in re.findall(r"[A-Za-z0-9]+", name)) or "EngelJavaExample"
        return example_scripts.safe_script_name(f"{class_name}.java", language)
    slug = "_".join(re.findall(r"[a-z0-9]+", name.lower())) or f"engel_{language}_example"
    return example_scripts.safe_script_name(f"{slug}{extension}", language)


def _guardian_review(
    *,
    product_only: bool,
    approval_required: bool,
    runtime_source_edit: bool = False,
    network_api: bool = False,
    package_install: bool = False,
    code_execution_now: bool = False,
    trusted_memory_write: bool = False,
) -> tuple[str, ...]:
    return (
        f"Runtime source edit: {'YES' if runtime_source_edit else 'NO'}",
        f"Product-only change: {'YES' if product_only else 'NO'}",
        f"Network/API: {'YES' if network_api else 'NO'}",
        f"Package install: {'YES' if package_install else 'NO'}",
        f"Code execution now: {'YES' if code_execution_now else 'NO'}",
        f"Trusted memory write: {'YES' if trusted_memory_write else 'NO'}",
        f"Approval required: {'YES' if approval_required else 'NO'}",
        f"{AUTHORITY} preserved: YES",
    )


def classify_talk_to_code_intent(text: str) -> TalkToCodeIntent:
    raw_text = text or ""
    unsafe_markers = _scan_unsafe_request(raw_text)
    if unsafe_markers:
        return TalkToCodeIntent(
            raw_text=raw_text,
            intent_type=BLOCKED,
            language="",
            product_template="",
            product_name="",
            file_name="",
            selected_product="",
            unsafe_markers=unsafe_markers,
            requires_approval=False,
            blocked_reason="Unsafe or out-of-scope request: " + ", ".join(unsafe_markers),
        )

    lowered = raw_text.lower()
    if _is_continue_product_request(raw_text):
        return TalkToCodeIntent(raw_text, CONTINUE_PRODUCT_PLAN, "", "", "", "", "", requires_approval=False)
    conversation = conversation_commands.classify_product_conversation_command(raw_text)
    if conversation.domain == "safety_guardian" or conversation.resolved_intent.startswith("unsafe_"):
        return TalkToCodeIntent(
            raw_text=raw_text,
            intent_type=BLOCKED,
            language="",
            product_template="",
            product_name="",
            file_name="",
            selected_product="",
            unsafe_markers=(conversation.resolved_intent,),
            requires_approval=False,
            blocked_reason="Conversation command blocked by Guardian boundary: " + conversation.resolved_intent,
        )
    if conversation.resolved_intent in {"continue_product", "product_next_safe_action"}:
        return TalkToCodeIntent(raw_text, CONTINUE_PRODUCT_PLAN, "", "", "", "", "", requires_approval=False)
    if conversation.resolved_intent in {"improve_product", "patch_proposal", "readme_manifest_proposal", "product_test_plan"}:
        return TalkToCodeIntent(raw_text, PRODUCT_PATCH_PROPOSAL, "", "", "", "", "", requires_approval=False)
    if conversation.resolved_intent == "research_to_product" and conversation.confidence in {"HIGH", "MEDIUM"}:
        return TalkToCodeIntent(raw_text, RESEARCH_TO_PRODUCT_PLAN, "", "", "", "", "", requires_approval=True)
    if "package" in lowered:
        return TalkToCodeIntent(raw_text, "package_preview", "", "", "", "", "", requires_approval=True)
    if "launch" in lowered or re.search(r"\brun\b", lowered):
        return TalkToCodeIntent(raw_text, "launch_preview", "", "", "", "", "", requires_approval=True)
    if _is_research_to_product_request(raw_text):
        return TalkToCodeIntent(raw_text, RESEARCH_TO_PRODUCT_PLAN, "", "", "", "", "", requires_approval=True)
    if _is_product_improvement_request(raw_text):
        return TalkToCodeIntent(raw_text, PRODUCT_PATCH_PROPOSAL, "", "", "", "", "", requires_approval=False)
    if project_builder.is_project_builder_request(raw_text):
        project_plan = project_builder.build_project_builder_plan(raw_text)
        if project_plan.status == project_builder.BLOCKED:
            return TalkToCodeIntent(
                raw_text=raw_text,
                intent_type=PROJECT_BUILDER_PLAN,
                language="",
                product_template=project_plan.selected_template,
                product_name=project_plan.product_name,
                file_name="",
                selected_product="",
                unsafe_markers=project_plan.unsafe_markers,
                requires_approval=True,
                blocked_reason=project_plan.blocked_reason,
            )
        language = (
            "python"
            if project_plan.selected_template == project_builder.TEMPLATE_PYTHON_CLI
            else "html"
            if project_plan.selected_template in {project_builder.TEMPLATE_HTML_DASHBOARD, project_builder.TEMPLATE_STATIC_LANDING_PAGE}
            else "markdown"
        )
        return TalkToCodeIntent(
            raw_text=raw_text,
            intent_type=PROJECT_BUILDER_PLAN,
            language=language,
            product_template=project_plan.selected_template,
            product_name=project_plan.product_name,
            file_name="",
            selected_product="",
            requires_approval=True,
        )

    wants_java = "java" in lowered
    wants_python = "python" in lowered or "py " in f"{lowered} "
    wants_html = any(token in lowered for token in ("html", "web page", "webpage", "website", "dashboard", "mini app"))
    wants_script = "script" in lowered or "example" in lowered
    wants_cli = "cli" in lowered or "command line" in lowered or "tool" in lowered
    wants_gui = "gui" in lowered or "window" in lowered or "tkinter" in lowered
    wants_dashboard = "dashboard" in lowered or "website" in lowered
    wants_mini = "mini app" in lowered or ("html" in lowered and "css" in lowered and "js" in lowered)

    if wants_java and ("app" in lowered or "console" in lowered or "product" in lowered):
        name = _name_from_text(raw_text, "Java Console Product")
        return TalkToCodeIntent(raw_text, "java_console_product", "java", "java_console_starter", name, "", "")
    if wants_java:
        return TalkToCodeIntent(raw_text, "java_script", "java", "", "", _script_file_name(raw_text, "java"), "")

    if wants_gui:
        name = _name_from_text(raw_text, "Python GUI Product")
        return TalkToCodeIntent(raw_text, "python_gui_product", "python", "python_gui_starter", name, "", "")
    if wants_cli:
        name = _name_from_text(raw_text, "Python CLI Product")
        return TalkToCodeIntent(raw_text, "python_cli_product", "python", "python_cli_starter", name, "", "")

    if wants_mini:
        name = _name_from_text(raw_text, "HTML Mini App")
        return TalkToCodeIntent(raw_text, "html_mini_app_product", "html", "html_mini_app", name, "", "")
    if wants_dashboard:
        name = _name_from_text(raw_text, "HTML Dashboard Product")
        return TalkToCodeIntent(raw_text, "html_dashboard_product", "html", "html_dashboard_starter", name, "", "")
    if wants_html:
        return TalkToCodeIntent(raw_text, "html_page", "html", "", "", _script_file_name(raw_text, "html"), "")

    if wants_python and wants_script:
        return TalkToCodeIntent(raw_text, "python_script", "python", "", "", _script_file_name(raw_text, "python"), "")
    if wants_python:
        name = _name_from_text(raw_text, "Python CLI Product")
        return TalkToCodeIntent(raw_text, "python_cli_product", "python", "python_cli_starter", name, "", "")

    return TalkToCodeIntent(
        raw_text=raw_text,
        intent_type=BLOCKED,
        language="",
        product_template="",
        product_name="",
        file_name="",
        selected_product="",
        blocked_reason="Could not map idea to a supported bounded script or product type.",
    )


def _build_files_for_intent(intent: TalkToCodeIntent) -> tuple[tuple[str, ...], str, str]:
    if intent.intent_type in SCRIPT_TARGETS:
        build = example_scripts.build_script_from_prompt(intent.language, intent.raw_text, intent.file_name)
        root = example_scripts.language_root(intent.language)
        validation = {
            "python": "ast / py_compile",
            "java": "Java class/file-name text validation; javac proposal-only",
            "html": "basic local HTML structure check",
        }[intent.language]
        return (build.filename,), str(root), validation

    if intent.intent_type in PRODUCT_TARGETS:
        build = product_templates.build_product_template(intent.product_template, intent.product_name, intent.raw_text)
        root = product_templates.product_path_for_slug(build.product_slug)
        validation = "bounded product file validation"
        return tuple(build.files.keys()), str(root), validation

    if intent.intent_type == PRODUCT_IMPROVEMENT_PROPOSAL:
        return tuple(), "selected product under products", "proposal-only product health/improvement review"
    if intent.intent_type == PRODUCT_PATCH_PROPOSAL:
        return tuple(), "selected product under products", "product patch proposal diff preview"
    if intent.intent_type == CONTINUE_PRODUCT_PLAN:
        return tuple(), "selected product under products", "read-only continue product plan"
    if intent.intent_type == RESEARCH_TO_PRODUCT_PLAN:
        build = product_templates.build_product_template(intent.product_template, intent.product_name, "")
        root = product_templates.product_path_for_slug(build.product_slug)
        return tuple(build.files.keys()), str(root), "bounded research-to-product file validation"
    if intent.intent_type == PROJECT_BUILDER_PLAN:
        plan = project_builder.build_project_builder_plan(intent.raw_text)
        return tuple(plan.planned_files), str(plan.save_root) if plan.save_root else "products", "bounded Project Builder product validation"
    if intent.intent_type == "package_preview":
        return tuple(), "selected product dist preview", "APPROVE_PACKAGE required in V3 packaging controls"
    if intent.intent_type == "launch_preview":
        return tuple(), "selected product launch preview", "APPROVE_LAUNCH required in V3 launch controls"
    return tuple(), "", "blocked"


def build_talk_to_code_plan(
    text: str,
    selected_product: str | None = None,
    selected_research_summary_id: str | None = None,
    selected_research_intake_receipt_id: str | None = None,
    session_memory: product_session.ProductSessionMemory | None = None,
) -> TalkToCodePlan:
    intent = classify_talk_to_code_intent(text)
    if not selected_product and session_memory is not None:
        resolved_product = session_memory.resolve_product_reference(text)
        if resolved_product and resolved_product != product_session.SELECT_PRODUCT_REQUIRED:
            selected_product = resolved_product
    if selected_product:
        intent = TalkToCodeIntent(
            raw_text=intent.raw_text,
            intent_type=intent.intent_type,
            language=intent.language,
            product_template=intent.product_template,
            product_name=intent.product_name,
            file_name=intent.file_name,
            selected_product=selected_product,
            research_summary_id=intent.research_summary_id,
            research_intake_receipt_id=intent.research_intake_receipt_id,
            research_source_kind=intent.research_source_kind,
            research_source_label=intent.research_source_label,
            research_risk_level=intent.research_risk_level,
            unsafe_markers=intent.unsafe_markers,
            requires_approval=intent.requires_approval,
            blocked_reason=intent.blocked_reason,
        )

    if intent.intent_type == RESEARCH_TO_PRODUCT_PLAN:
        selected_research_summary_id = str(selected_research_summary_id or "").strip()
        selected_research_intake_receipt_id = str(selected_research_intake_receipt_id or "").strip()
        if not selected_research_summary_id and not selected_research_intake_receipt_id:
            blocked_intent = TalkToCodeIntent(
                raw_text=intent.raw_text,
                intent_type=RESEARCH_TO_PRODUCT_PLAN,
                language=intent.language,
                product_template=intent.product_template,
                product_name=intent.product_name,
                file_name=intent.file_name,
                selected_product=intent.selected_product,
                research_summary_id="",
                research_intake_receipt_id="",
                research_source_kind="missing",
                unsafe_markers=intent.unsafe_markers,
                requires_approval=True,
                blocked_reason=SELECT_RESEARCH_SUMMARY_REQUIRED,
            )
            return TalkToCodePlan(
                status=BLOCKED,
                idea_summary=_compact_text(text),
                target_type=RESEARCH_TO_PRODUCT_PLAN,
                recommended_template="bounded research source required",
                files_to_create=tuple(),
                save_root="products",
                validation_method="blocked until a bounded Research Summary Proposal or Research Intake receipt is selected",
                guardian_review=(
                    "Research content trusted as instruction: NO",
                    "Runtime source edit: NO",
                    "Product-only creation: YES",
                    "Network/API: NO",
                    "Code execution now: NO",
                    "Trusted memory write: NO",
                    "Approval required before create: YES",
                    f"{AUTHORITY} preserved: YES",
                ),
                approval_required=True,
                safety_notes=(
                    SELECT_RESEARCH_SUMMARY_REQUIRED,
                    "Select a bounded Research Summary Proposal from reports\\research_intake\\summaries.",
                    "Or select a bounded Research Intake receipt from reports\\research_intake\\receipts.",
                    "No files were created.",
                    "Research content was not trusted as instruction.",
                ),
                intent=blocked_intent,
            )
        source_kind = "research_summary" if selected_research_summary_id else "research_intake"
        source_id = selected_research_summary_id if selected_research_summary_id else selected_research_intake_receipt_id
        try:
            if source_kind == "research_summary":
                source_path, source_text, risk_level, source_label = _load_research_summary(source_id)
            else:
                source_path, source_text, risk_level, source_label = _load_research_intake_receipt(source_id)
        except ValueError as exc:
            blocked_intent = TalkToCodeIntent(
                raw_text=intent.raw_text,
                intent_type=RESEARCH_TO_PRODUCT_PLAN,
                language=intent.language,
                product_template=intent.product_template,
                product_name=intent.product_name,
                file_name=intent.file_name,
                selected_product=intent.selected_product,
                research_summary_id=source_id if source_kind == "research_summary" else "",
                research_intake_receipt_id=source_id if source_kind == "research_intake" else "",
                research_source_kind=source_kind,
                unsafe_markers=intent.unsafe_markers,
                requires_approval=True,
                blocked_reason=str(exc),
            )
            return TalkToCodePlan(
                status=BLOCKED,
                idea_summary=_compact_text(text),
                target_type=RESEARCH_TO_PRODUCT_PLAN,
                recommended_template="bounded research source required",
                files_to_create=tuple(),
                save_root="products",
                validation_method="blocked: unsafe research summary ID" if source_kind == "research_summary" else "blocked: unsafe research intake receipt ID",
                guardian_review=(
                    "Research content trusted as instruction: NO",
                    "Runtime source edit: NO",
                    "Product-only creation: YES",
                    "Network/API: NO",
                    "Code execution now: NO",
                    "Trusted memory write: NO",
                    "Approval required before create: YES",
                    f"{AUTHORITY} preserved: YES",
                ),
                approval_required=True,
                safety_notes=(
                    "Research source ID is not bounded.",
                    "No files were created.",
                    "Research content was not trusted as instruction.",
                ),
                intent=blocked_intent,
            )
        template_id = _research_template_from_text(text, source_text)
        product_name = _research_product_name(text, source_path.stem, source_label)
        build = product_templates.build_product_template(template_id, product_name, "")
        blocked_by_risk = risk_level in {"HIGH", "BLOCKED"}
        blocked_reason = (
            "RESEARCH_SUMMARY_RISK_BLOCKED"
            if source_kind == "research_summary" and blocked_by_risk
            else HIGH_RISK_RESEARCH_SOURCE
            if blocked_by_risk
            else ""
        )
        research_intent = TalkToCodeIntent(
            raw_text=intent.raw_text,
            intent_type=RESEARCH_TO_PRODUCT_PLAN,
            language="html" if template_id.startswith("html") else "python",
            product_template=template_id,
            product_name=product_name,
            file_name="",
            selected_product=intent.selected_product,
            research_summary_id=source_path.name if source_kind == "research_summary" else "",
            research_intake_receipt_id=source_path.name if source_kind == "research_intake" else "",
            research_source_kind=source_kind,
            research_source_label=source_label,
            research_risk_level=risk_level,
            unsafe_markers=intent.unsafe_markers,
            requires_approval=True,
            blocked_reason=blocked_reason,
        )
        files = tuple(build.files.keys()) if build.validation.ok and not blocked_by_risk else tuple()
        source_note = (
            f"Source research summary: {source_path.name}"
            if source_kind == "research_summary"
            else f"Source research intake receipt: {source_path.name}"
        )
        return TalkToCodePlan(
            status=BLOCKED if blocked_by_risk else READY_TO_CREATE,
            idea_summary=_compact_text(text),
            target_type=RESEARCH_TO_PRODUCT_PLAN,
            recommended_template=template_id,
            files_to_create=files,
            save_root=str(product_templates.product_path_for_slug(build.product_slug)),
            validation_method="bounded product file validation",
            guardian_review=(
                "Research content trusted as instruction: NO",
                "Runtime source edit: NO",
                "Product-only creation: YES",
                "Network/API: NO",
                "Code execution now: NO",
                "Trusted memory write: NO",
                "Approval required before create: YES",
                f"{AUTHORITY} preserved: YES",
            ),
            approval_required=True,
            safety_notes=(
                "PLAN_ONLY / NOT_TRUSTED_MEMORY / NOT_APPLIED.",
                source_note,
                f"Untrusted Content Guard risk: {risk_level}",
                "Research Summary Proposal ≠ Trusted Memory.",
                "Research Intake ≠ Trusted Memory.",
                "Talk-to-Code research plan ≠ Trusted Memory.",
                "Created product ≠ trusted memory.",
                (
                    "HIGH_RISK_RESEARCH_SOURCE: HIGH/BLOCKED research risk prevents product creation; no research content becomes action."
                    if blocked_by_risk
                    else "Create uses existing bounded product helpers and does not treat research content as instruction."
                ),
            ),
            intent=research_intent,
        )

    if intent.intent_type == CONTINUE_PRODUCT_PLAN:
        continue_plan = continue_product.build_continue_product_plan(intent.raw_text, intent.selected_product)
        if not continue_plan.ok:
            blocked_intent = TalkToCodeIntent(
                raw_text=intent.raw_text,
                intent_type=CONTINUE_PRODUCT_PLAN,
                language=intent.language,
                product_template=intent.product_template,
                product_name=intent.product_name,
                file_name=intent.file_name,
                selected_product=intent.selected_product,
                unsafe_markers=intent.unsafe_markers,
                requires_approval=False,
                blocked_reason=continue_plan.blocked_reason or continue_plan.status,
            )
            return TalkToCodePlan(
                status=BLOCKED,
                idea_summary=_compact_text(text),
                target_type=CONTINUE_PRODUCT_PLAN,
                recommended_template="continue product plan",
                files_to_create=tuple(),
                save_root="selected product under products",
                validation_method="blocked until a bounded product is selected",
                guardian_review=continue_plan.guardian_review,
                approval_required=False,
                safety_notes=continue_plan.safety_notes,
                intent=blocked_intent,
            )
        continue_intent = TalkToCodeIntent(
            raw_text=intent.raw_text,
            intent_type=CONTINUE_PRODUCT_PLAN,
            language=intent.language,
            product_template=intent.product_template,
            product_name=intent.product_name,
            file_name=intent.file_name,
            selected_product=continue_plan.product_slug,
            unsafe_markers=intent.unsafe_markers,
            requires_approval=False,
        )
        return TalkToCodePlan(
            status=PROPOSAL_ONLY,
            idea_summary=_compact_text(text),
            target_type=CONTINUE_PRODUCT_PLAN,
            recommended_template=continue_plan.action_kind,
            files_to_create=tuple(),
            save_root=str(continue_plan.product_path) if continue_plan.product_path else "selected product under products",
            validation_method="read-only product cycle status and next safe action",
            guardian_review=continue_plan.guardian_review,
            approval_required=False,
            safety_notes=continue_plan.safety_notes,
            intent=continue_intent,
        )

    if intent.intent_type == PRODUCT_PATCH_PROPOSAL:
        proposal = patch_proposals.build_product_patch_proposal(intent.selected_product, intent.raw_text)
        if not proposal.ok:
            blocked_intent = TalkToCodeIntent(
                raw_text=intent.raw_text,
                intent_type=PRODUCT_PATCH_PROPOSAL,
                language=intent.language,
                product_template=intent.product_template,
                product_name=intent.product_name,
                file_name=intent.file_name,
                selected_product=intent.selected_product,
                unsafe_markers=proposal.unsafe_markers,
                requires_approval=False,
                blocked_reason=proposal.blocked_reason or proposal.status,
            )
            return TalkToCodePlan(
                status=BLOCKED,
                idea_summary=_compact_text(text),
                target_type=PRODUCT_PATCH_PROPOSAL,
                recommended_template="product patch proposal",
                files_to_create=tuple(item.relative_path for item in proposal.files),
                save_root=str(proposal.product_path) if proposal.product_path else "selected product under products",
                validation_method="blocked product patch proposal",
                guardian_review=proposal.guardian_review,
                approval_required=False,
                safety_notes=(
                    proposal.blocked_reason or proposal.status,
                    "No product files were changed.",
                    "No Engel runtime source was edited.",
                    "No generated code was executed.",
                    "No trusted memory was written.",
                ),
                intent=blocked_intent,
            )
        patch_intent = TalkToCodeIntent(
            raw_text=intent.raw_text,
            intent_type=PRODUCT_PATCH_PROPOSAL,
            language=intent.language,
            product_template=intent.product_template,
            product_name=intent.product_name,
            file_name=intent.file_name,
            selected_product=proposal.product_slug,
            unsafe_markers=intent.unsafe_markers,
            requires_approval=False,
        )
        return TalkToCodePlan(
            status=PROPOSAL_ONLY,
            idea_summary=_compact_text(text),
            target_type=PRODUCT_PATCH_PROPOSAL,
            recommended_template="product patch proposal",
            files_to_create=tuple(item.relative_path for item in proposal.files),
            save_root=str(proposal.product_path) if proposal.product_path else "selected product under products",
            validation_method="diff-style product patch proposal preview",
            guardian_review=proposal.guardian_review,
            approval_required=False,
            safety_notes=proposal.safety_notes,
            intent=patch_intent,
        )

    if intent.intent_type == PRODUCT_IMPROVEMENT_PROPOSAL and not intent.selected_product:
        blocked_intent = TalkToCodeIntent(
            raw_text=intent.raw_text,
            intent_type=PRODUCT_IMPROVEMENT_PROPOSAL,
            language=intent.language,
            product_template=intent.product_template,
            product_name=intent.product_name,
            file_name=intent.file_name,
            selected_product="",
            unsafe_markers=intent.unsafe_markers,
            requires_approval=False,
            blocked_reason=SELECT_PRODUCT_REQUIRED,
        )
        return TalkToCodePlan(
            status=BLOCKED,
            idea_summary=_compact_text(text),
            target_type=PRODUCT_IMPROVEMENT_PROPOSAL,
            recommended_template="existing Product Improve proposal",
            files_to_create=tuple(),
            save_root="selected product under products",
            validation_method="blocked until a bounded product is selected",
            guardian_review=(
                "Runtime source edit: NO",
                "Product-only context: YES",
                "Product files changed now: NO",
                "Code execution now: NO",
                "Trusted memory write: NO",
                "Approval required before apply: YES",
                f"{AUTHORITY} preserved: YES",
            ),
            approval_required=False,
            safety_notes=(
                SELECT_PRODUCT_REQUIRED,
                "Select a bounded product before asking Engel to improve this product.",
                "No files were changed.",
                "No product code was executed.",
            ),
            intent=blocked_intent,
        )

    if intent.intent_type == PROJECT_BUILDER_PLAN:
        project_plan = project_builder.build_project_builder_plan(intent.raw_text)
        return TalkToCodePlan(
            status=BLOCKED if project_plan.status == project_builder.BLOCKED else READY_TO_CREATE,
            idea_summary=_compact_text(text),
            target_type=PROJECT_BUILDER_PLAN,
            recommended_template=project_plan.selected_template,
            files_to_create=project_plan.planned_files,
            save_root=str(project_plan.save_root) if project_plan.save_root else "products",
            validation_method="bounded Project Builder product validation",
            guardian_review=project_plan.guardian_review,
            approval_required=True,
            safety_notes=project_plan.safety_notes,
            intent=TalkToCodeIntent(
                raw_text=intent.raw_text,
                intent_type=PROJECT_BUILDER_PLAN,
                language=intent.language,
                product_template=project_plan.selected_template,
                product_name=project_plan.product_name,
                file_name="",
                selected_product=intent.selected_product,
                unsafe_markers=project_plan.unsafe_markers,
                requires_approval=True,
                blocked_reason=project_plan.blocked_reason if project_plan.status == project_builder.BLOCKED else "",
            ),
        )

    if intent.intent_type == BLOCKED or intent.blocked_reason:
        reason = intent.blocked_reason or "Blocked by Guardian review."
        markers = set(intent.unsafe_markers)
        return TalkToCodePlan(
            status=BLOCKED,
            idea_summary=_compact_text(text),
            target_type=BLOCKED,
            recommended_template="",
            files_to_create=tuple(),
            save_root="",
            validation_method="blocked",
            guardian_review=_guardian_review(
                product_only=False,
                approval_required=False,
                runtime_source_edit="runtime source edit" in markers,
                network_api=bool(markers & {"api or provider call", "network use", "data exfiltration attack"}),
                package_install="package install" in markers,
                code_execution_now=bool(markers & {"powershell command", "execute now", "browser launch"}),
                trusted_memory_write=bool(markers & {"trusted memory write", "memory attack"}),
            ),
            approval_required=False,
            safety_notes=(
                reason,
                "No files will be created.",
                "Talk-to-Code did not edit runtime source, execute code, install packages, or write trusted memory.",
            ),
            intent=intent,
        )

    files, save_root, validation = _build_files_for_intent(intent)
    approval_required = intent.intent_type in {"package_preview", "launch_preview"}
    status = READY_TO_CREATE if intent.intent_type in SCRIPT_TARGETS | PRODUCT_TARGETS else PLAN_ONLY
    if intent.intent_type == PRODUCT_IMPROVEMENT_PROPOSAL:
        status = PROPOSAL_ONLY
    if intent.intent_type in {"package_preview", "launch_preview"}:
        status = PLAN_ONLY

    guardian_review = _guardian_review(
        product_only=intent.intent_type in PRODUCT_TARGETS,
        approval_required=approval_required,
    )
    if intent.intent_type == PRODUCT_IMPROVEMENT_PROPOSAL:
        guardian_review = (
            "Runtime source edit: NO",
            "Product-only context: YES",
            "Product files changed now: NO",
            "Code execution now: NO",
            "Trusted memory write: NO",
            "Approval required before apply: YES",
            f"{AUTHORITY} preserved: YES",
        )

    safety_notes = (
        "PLAN_ONLY / NOT_RUNTIME / NOT_APPLIED until Create is clicked.",
        "Create writes only under examples\\code_companion or products\\.",
        "Create uses existing bounded Code Companion script/product helpers only.",
        "No API, provider, network, package install, runtime source edit, trusted memory write, or generated-code execution.",
    )
    if intent.intent_type == PRODUCT_IMPROVEMENT_PROPOSAL:
        safety_notes = (
            "PLAN_ONLY / PROPOSAL_ONLY / NOT_APPLIED.",
            "Create renders the existing Product Improvement Proposal only.",
            "No product files are changed now.",
            "Use Lesson only with APPROVE_LESSON_CANDIDATE if Josh wants a lesson candidate.",
            "No API, provider, network, package install, runtime source edit, trusted memory write, or generated-code execution.",
        )

    return TalkToCodePlan(
        status=status,
        idea_summary=_compact_text(text),
        target_type=intent.intent_type,
        recommended_template=intent.product_template or intent.language or intent.intent_type,
        files_to_create=files,
        save_root=save_root,
        validation_method=validation,
        guardian_review=guardian_review,
        approval_required=approval_required,
        safety_notes=safety_notes,
        intent=intent,
    )


def render_talk_to_code_plan(plan: TalkToCodePlan) -> str:
    if plan.target_type == PROJECT_BUILDER_PLAN and plan.intent:
        return contextual_talk.append_context_to_rendered_plan(
            project_builder.render_project_builder_plan(project_builder.build_project_builder_plan(plan.intent.raw_text)),
            plan.intent.selected_product,
        )
    if plan.target_type == CONTINUE_PRODUCT_PLAN and plan.intent:
        return continue_product.render_continue_product_plan(
            continue_product.build_continue_product_plan(plan.intent.raw_text, plan.intent.selected_product)
        )
    if plan.target_type == PRODUCT_PATCH_PROPOSAL and plan.intent:
        return patch_proposals.render_product_patch_proposal(
            patch_proposals.build_product_patch_proposal(plan.intent.selected_product, plan.intent.raw_text)
        )

    lines = [
        "# ENGEL TALK-TO-CODE RESEARCH PLAN" if plan.target_type == RESEARCH_TO_PRODUCT_PLAN else "# ENGEL TALK-TO-CODE PLAN",
        "",
        "Idea:",
        plan.idea_summary,
        "",
    ]
    if plan.target_type == RESEARCH_TO_PRODUCT_PLAN:
        source_id = SELECT_RESEARCH_SUMMARY_REQUIRED
        if plan.intent:
            source_id = plan.intent.research_summary_id or plan.intent.research_intake_receipt_id or SELECT_RESEARCH_SUMMARY_REQUIRED
        lines.extend(
            [
                "Source:",
                source_id,
                "",
                "Research path:",
                "Research Intake -> Research Office / Overnight Research",
                "",
                "Target:",
                plan.recommended_template,
                "",
            ]
        )
    else:
        lines.extend(
            [
                "Target:",
                "Product Improvement Proposal" if plan.target_type == PRODUCT_IMPROVEMENT_PROPOSAL else plan.target_type,
                "",
            ]
        )
    if plan.intent and plan.intent.selected_product:
        lines.extend(["Selected product:", plan.intent.selected_product, ""])
    if plan.intent and plan.intent.research_risk_level:
        lines.extend(["Untrusted Content Guard:", "Risk: " + plan.intent.research_risk_level, ""])
    lines.extend(
        [
            "Recommended template:",
            plan.recommended_template or "none",
            "",
            "Save root:",
            plan.save_root or "none",
            "",
            "Files:",
        ]
    )
    if plan.files_to_create:
        lines.extend(f"- {path}" for path in plan.files_to_create)
    else:
        lines.append("- none")
    lines.extend([
        "",
        "Validation:",
        plan.validation_method,
        "",
        "Guardian Review:",
    ])
    lines.extend(f"- {item}" for item in plan.guardian_review)
    lines.extend([
        "",
        "Status:",
        (
            f"{PLAN_ONLY} / {PROPOSAL_ONLY} / {NOT_APPLIED}"
            if plan.target_type == PRODUCT_IMPROVEMENT_PROPOSAL and plan.status != BLOCKED
            else f"{PLAN_ONLY} / NOT_TRUSTED_MEMORY / {NOT_APPLIED}"
            if plan.target_type == RESEARCH_TO_PRODUCT_PLAN and plan.status != BLOCKED
            else f"{BLOCKED} / NOT_TRUSTED_MEMORY / {NOT_APPLIED}"
            if plan.target_type == RESEARCH_TO_PRODUCT_PLAN
            else f"{plan.status} / {NOT_RUNTIME} / {NOT_APPLIED}"
        ),
        "",
        "Safety:",
    ])
    lines.extend(f"- {note}" for note in plan.safety_notes)
    if plan.status == READY_TO_CREATE and plan.target_type == RESEARCH_TO_PRODUCT_PLAN:
        lines.extend(["", "Next:", "Click Create only if Josh wants a bounded product generated."])
    elif plan.status == READY_TO_CREATE:
        lines.extend(["", "Next:", "Click Create to generate bounded files, or edit the idea."])
    elif plan.target_type == PRODUCT_IMPROVEMENT_PROPOSAL and plan.status != BLOCKED:
        lines.extend(
            [
                "",
                "Next:",
                "Use Improve to view proposal.",
                "Use Lesson only with APPROVE_LESSON_CANDIDATE if Josh wants a lesson candidate.",
            ]
        )
    elif plan.status == PLAN_ONLY:
        lines.extend(["", "Next:", "Use the dedicated approval-gated V3 controls for launch/package actions."])
    return "\n".join(lines)


def _render_create_result(result: TalkToCodeResult) -> str:
    lines = [
        "# ENGEL TALK-TO-CODE CREATE RESULT",
        "",
        "Status:",
        result.status,
        "",
        "Path:",
        str(result.path) if result.path else "none",
        "",
        "Validation:",
        result.validation_status,
        "",
        "Message:",
        result.message,
    ]
    if result.files_written:
        lines.extend(["", "Files written:"])
        lines.extend(f"- {path}" for path in result.files_written)
    lines.extend([
        "",
        "Safety:",
        "- Product/script only",
        "- No runtime source edit",
        "- No generated-code execution",
        "- No package install",
        "- No provider/API/network behavior",
        "- No trusted memory write",
        f"- {AUTHORITY} preserved",
    ])
    return "\n".join(lines)


def execute_talk_to_code_plan(plan: TalkToCodePlan, approval_token: str | None = None) -> TalkToCodeResult:
    if not plan.intent:
        result = TalkToCodeResult(False, "PLAN_REQUIRED", None, tuple(), "NOT_RUN", "Build a Talk-to-Code plan before Create.", "")
        return TalkToCodeResult(**{**result.__dict__, "output": _render_create_result(result)})
    if plan.status == BLOCKED:
        if plan.intent.blocked_reason == SELECT_PRODUCT_REQUIRED:
            status = SELECT_PRODUCT_REQUIRED
            message = "Select a bounded product before asking Engel to improve this product."
        elif plan.intent.blocked_reason == SELECT_RESEARCH_SUMMARY_REQUIRED:
            status = SELECT_RESEARCH_SUMMARY_REQUIRED
            message = "Select a bounded Research Summary Proposal or Research Intake receipt before asking Engel to build from research."
        elif plan.intent.blocked_reason == "RESEARCH_SUMMARY_RISK_BLOCKED":
            status = "RESEARCH_SUMMARY_RISK_BLOCKED"
            message = "HIGH/BLOCKED research summary risk prevents product creation."
        elif plan.intent.blocked_reason == HIGH_RISK_RESEARCH_SOURCE:
            status = HIGH_RISK_RESEARCH_SOURCE
            message = "HIGH/BLOCKED research source risk prevents product creation."
        else:
            status = BLOCKED
            message = "Guardian review blocked this request."
        result = TalkToCodeResult(False, status, None, tuple(), "BLOCKED", message, "")
        return TalkToCodeResult(**{**result.__dict__, "output": _render_create_result(result)})
    if plan.status not in {READY_TO_CREATE, PROPOSAL_ONLY}:
        result = TalkToCodeResult(
            False,
            "PLAN_ONLY",
            None,
            tuple(),
            "NOT_RUN",
            "This plan is preview/proposal-only. Use the dedicated approval-gated controls if applicable.",
            "",
        )
        return TalkToCodeResult(**{**result.__dict__, "output": _render_create_result(result)})

    intent = plan.intent
    if intent.intent_type in SCRIPT_TARGETS:
        build = example_scripts.build_script_from_prompt(intent.language, intent.raw_text, intent.file_name)
        path = example_scripts.save_script(intent.language, build.filename, build.content)
        validation = example_scripts.compile_or_validate_example(path, intent.language)
        result = TalkToCodeResult(
            validation.ok,
            "CREATED" if validation.ok else "CREATED_WITH_VALIDATION_WARNING",
            path,
            (path,),
            validation.status,
            validation.message,
            "",
        )
        return TalkToCodeResult(**{**result.__dict__, "output": _render_create_result(result)})

    if intent.intent_type in PRODUCT_TARGETS:
        write_result = product_templates.write_product(intent.product_name, intent.product_template, intent.raw_text, approval_token)
        files_written: tuple[Path, ...] = tuple(Path(p) for p in write_result.files_written)
        validation_status = getattr(write_result.validation, "status", "NOT_RUN")
        if write_result.ok and write_result.product_path is not None:
            validation_status = product_templates.validate_existing_product(write_result.product_path).status
        result = TalkToCodeResult(
            bool(write_result.ok),
            write_result.status,
            write_result.product_path,
            files_written,
            validation_status,
            write_result.message,
            "",
        )
        return TalkToCodeResult(**{**result.__dict__, "output": _render_create_result(result)})

    if intent.intent_type == CONTINUE_PRODUCT_PLAN:
        continue_plan = continue_product.build_continue_product_plan(intent.raw_text, intent.selected_product)
        return TalkToCodeResult(
            False,
            "CONTINUE_PRODUCT_PLAN_ONLY / NOT_APPLIED",
            continue_plan.product_path,
            tuple(),
            "NOT_RUN",
            "Continue Product Plan rendered only; no files were changed.",
            continue_product.render_continue_product_plan(continue_plan),
        )

    if intent.intent_type == PRODUCT_PATCH_PROPOSAL:
        proposal = patch_proposals.build_product_patch_proposal(intent.selected_product, intent.raw_text)
        if str(approval_token or "").strip() != patch_apply.APPROVE_PRODUCT_PATCH:
            result = patch_apply.apply_product_patch(proposal.product_slug or intent.selected_product, proposal, approval_token)
            output = patch_apply.render_product_patch_apply_result(result)
            return TalkToCodeResult(
                False,
                result.status,
                result.product_path,
                tuple(),
                result.validation_status,
                result.message,
                output,
            )
        result = patch_apply.apply_product_patch(proposal.product_slug, proposal, approval_token)
        return TalkToCodeResult(
            result.ok,
            result.status,
            result.product_path,
            result.files_changed,
            result.validation_status,
            result.message,
            patch_apply.render_product_patch_apply_result(result),
        )

    if intent.intent_type == PROJECT_BUILDER_PLAN:
        project_plan = project_builder.build_project_builder_plan(intent.raw_text)
        create_result = project_builder.create_project_builder_product(project_plan, approval_token)
        result = TalkToCodeResult(
            bool(create_result.ok),
            create_result.status,
            create_result.product_path,
            create_result.files_written,
            create_result.validation_status,
            create_result.message,
            project_builder.render_project_builder_create_result(create_result),
        )
        return result

    if intent.intent_type == RESEARCH_TO_PRODUCT_PLAN:
        write_result = product_templates.write_product(
            intent.product_name,
            intent.product_template,
            "Research-to-product bounded template. Research content is untrusted data and was not used as instruction.",
            approval_token,
        )
        files_written: tuple[Path, ...] = tuple(Path(p) for p in write_result.files_written)
        validation_status = getattr(write_result.validation, "status", "NOT_RUN")
        if write_result.ok and write_result.product_path is not None:
            validation_status = product_templates.validate_existing_product(write_result.product_path).status
        result = TalkToCodeResult(
            bool(write_result.ok),
            write_result.status,
            write_result.product_path,
            files_written,
            validation_status,
            (
                "Research-to-product created with bounded product template; "
                "Research content trusted as instruction: NO; trusted memory write: NO."
            )
            if write_result.ok
            else write_result.message,
            "",
        )
        return TalkToCodeResult(**{**result.__dict__, "output": _render_create_result(result)})

    if intent.intent_type == PRODUCT_IMPROVEMENT_PROPOSAL:
        if not intent.selected_product:
            result = TalkToCodeResult(False, "SELECT_PRODUCT_REQUIRED", None, tuple(), "NOT_RUN", "Select a product before asking to improve it.", "")
            return TalkToCodeResult(**{**result.__dict__, "output": _render_create_result(result)})
        proposal = product_templates.build_product_improvement_proposal(intent.selected_product)
        output = product_templates.render_product_improvement_proposal(proposal)
        return TalkToCodeResult(
            bool(proposal.ok),
            "PRODUCT_IMPROVEMENT_PROPOSAL_RENDERED" if proposal.ok else "PRODUCT_IMPROVEMENT_PROPOSAL_BLOCKED",
            product_templates.product_path_for_slug(intent.selected_product),
            tuple(),
            "NOT_RUN",
            "Improvement proposal rendered in output only; no files were changed.",
            output,
        )

    result = TalkToCodeResult(False, "PLAN_ONLY", None, tuple(), "NOT_RUN", "No create action is available for this plan.", "")
    return TalkToCodeResult(**{**result.__dict__, "output": _render_create_result(result)})
