from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import engel_code_companion_products as product_templates
import engel_untrusted_content_guard as untrusted_content_guard


ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
AUTHORITY = "Josh > Guardian > Engel/runtime"
PROJECT_BUILDER_PLAN = "PROJECT_BUILDER_PLAN"
PLAN_ONLY = "PLAN_ONLY"
READY_TO_CREATE = "READY_TO_CREATE"
BLOCKED = "BLOCKED"
NOT_TRUSTED_MEMORY = "NOT_TRUSTED_MEMORY"
NOT_APPLIED = "NOT_APPLIED"
PRODUCT_STATUS = product_templates.PRODUCT_STATUS
APPROVAL_TOKEN = product_templates.APPROVAL_TOKEN

TEMPLATE_PYTHON_CLI = "python_cli"
TEMPLATE_HTML_DASHBOARD = "html_dashboard"
TEMPLATE_STATIC_LANDING_PAGE = "static_landing_page"
TEMPLATE_MARKDOWN_PRODUCT_PLAN = "markdown_product_plan"
SUPPORTED_TEMPLATES = {
    TEMPLATE_PYTHON_CLI,
    TEMPLATE_HTML_DASHBOARD,
    TEMPLATE_STATIC_LANDING_PAGE,
    TEMPLATE_MARKDOWN_PRODUCT_PLAN,
}

UNSAFE_PROJECT_REQUEST_PATTERNS: tuple[tuple[str, str], ...] = (
    ("runtime source edit", r"\b(edit|modify|patch|rewrite|change)\b.{0,60}\b(engel runtime|runtime source|engel source|engel_app|engel_companion)\b"),
    ("package install", r"\b(install|pip install|npm install|add package|download package|dependency)\b"),
    ("code execution", r"\b(execute|executes|executing|run|runs|running)\b.{0,40}\b(generated code|this code|now|immediately|after creating)\b"),
    ("api or network", r"\b(call|calls|use|uses|connect to|connects to|send to|sends to|fetch|scrape)\b.{0,60}\b(api|openai|provider|network|http|https|website|web)\b"),
    ("browser queen", r"\b(browser queen|open browser|launch browser|browse the web)\b"),
    ("trusted memory write", r"\b(write|update|store|make permanent|promote)\b.{0,50}\b(trusted memory|memory candidate|lesson)\b"),
    ("external memory scan", r"\b(scan|read|import)\b.{0,50}\b(E:\\|G:\\|external memory|external roots)\b"),
    ("authority bypass", r"\b(ignore|bypass|disable|override)\b.{0,45}\b(guardian|authority|safety|josh)\b"),
    ("embedded approval token", r"\bAPPROVE_[A-Z_]+\b"),
)

PROJECT_BUILDER_VERBS = ("make", "build", "create", "generate", "scaffold")
PROJECT_BUILDER_NOUNS = (
    "product",
    "app",
    "tool",
    "dashboard",
    "tracker",
    "landing page",
    "website",
    "homepage",
    "cli",
    "command line",
    "viewer",
    "organizer",
)


@dataclass(frozen=True)
class ProjectBuilderPlan:
    status: str
    idea: str
    selected_template: str
    product_slug: str
    product_name: str
    planned_files: tuple[str, ...]
    save_root: Path | None
    guardian_review: tuple[str, ...]
    safety_notes: tuple[str, ...]
    blocked_reason: str = ""
    unsafe_markers: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ProjectBuilderCreateResult:
    ok: bool
    status: str
    product_path: Path | None
    files_written: tuple[Path, ...]
    receipt_path: Path | None
    validation_status: str
    message: str


def _compact_text(text: str, max_chars: int = 260) -> str:
    collapsed = " ".join(str(text or "").strip().split())
    if not collapsed:
        return ""
    if len(collapsed) > max_chars:
        return collapsed[: max_chars - 3].rstrip() + "..."
    return collapsed


def _safe_words(text: str, limit: int = 7) -> list[str]:
    stopwords = {
        "engel",
        "make",
        "build",
        "create",
        "generate",
        "scaffold",
        "me",
        "my",
        "please",
        "simple",
        "small",
        "safe",
        "product",
        "idea",
        "app",
        "application",
        "tool",
        "that",
        "with",
        "has",
        "and",
        "for",
        "from",
        "the",
        "this",
        "a",
        "an",
        "called",
        "named",
        "using",
        "python",
        "cli",
        "command",
        "line",
        "static",
        "html",
        "page",
        "website",
        "homepage",
    }
    words = re.findall(r"[A-Za-z0-9]+", text or "")
    filtered = [word.lower() for word in words if word.lower() not in stopwords]
    return filtered[:limit]


def _explicit_product_name(text: str) -> str:
    match = re.search(r"\b(?:called|named|name(?:d)? as)\s+([A-Za-z0-9][A-Za-z0-9 _-]{1,80})", text or "", re.IGNORECASE)
    if not match:
        return ""
    raw = re.split(r"[.;,\n]", match.group(1), maxsplit=1)[0]
    words = _safe_words(raw, limit=8)
    return " ".join(words).title() if words else ""


def _explicit_name_path_escape(text: str) -> bool:
    match = re.search(r"\b(?:called|named|name(?:d)? as)\s+(.{1,100})", text or "", re.IGNORECASE)
    if not match:
        return False
    raw = re.split(r"[;,\n]", match.group(1), maxsplit=1)[0].strip()
    if not raw:
        return False
    lowered = raw.lower()
    return (
        ".." in raw
        or "\\" in raw
        or "/" in raw
        or "://" in lowered
        or raw.startswith((".", "~"))
        or bool(re.match(r"^[A-Za-z]:", raw))
    )


def product_name_from_idea(idea: str, selected_template: str = "") -> str:
    explicit = _explicit_product_name(idea)
    if explicit:
        return explicit
    words = _safe_words(idea, limit=6)
    if words:
        return " ".join(words).title()
    if selected_template == TEMPLATE_PYTHON_CLI:
        return "Engel Project CLI"
    if selected_template == TEMPLATE_STATIC_LANDING_PAGE:
        return "Engel Landing Page"
    if selected_template == TEMPLATE_HTML_DASHBOARD:
        return "Engel Dashboard"
    return "Engel Product Plan"


def _scan_unsafe_project_request(text: str) -> tuple[str, ...]:
    markers: list[str] = []
    lowered = (text or "").lower()
    for label, pattern in UNSAFE_PROJECT_REQUEST_PATTERNS:
        if re.search(pattern, lowered, re.IGNORECASE):
            markers.append(label)
    guard = untrusted_content_guard.detect_prompt_injection_markers(text or "")
    if guard.authority_attack:
        markers.append("authority attack")
    if guard.tool_attack:
        markers.append("tool attack")
    if guard.memory_attack:
        markers.append("memory attack")
    if guard.data_exfiltration_attack:
        markers.append("data exfiltration attack")
    return tuple(dict.fromkeys(markers))


def is_project_builder_request(text: str) -> bool:
    lowered = (text or "").lower()
    if not lowered.strip():
        return False
    if re.search(r"\b(called|named)\b", lowered) and any(token in lowered for token in ("product", "script", "dashboard", "cli")):
        return False
    if "script" in lowered and "product" not in lowered and "cli" not in lowered and "tool" not in lowered:
        return False
    has_verb = any(re.search(r"\b" + re.escape(verb) + r"\b", lowered) for verb in PROJECT_BUILDER_VERBS)
    has_noun = any(noun in lowered for noun in PROJECT_BUILDER_NOUNS)
    if has_verb and has_noun:
        return True
    if "habit tracker" in lowered or "research notes" in lowered or "organizes text files" in lowered:
        return True
    return False


def classify_project_template(idea: str) -> str:
    lowered = (idea or "").lower()
    if any(token in lowered for token in ("landing page", "homepage", "marketing page", "splash page")):
        return TEMPLATE_STATIC_LANDING_PAGE
    if any(token in lowered for token in ("cli", "command line", "organize files", "organizes text files", "text files")):
        return TEMPLATE_PYTHON_CLI
    if any(token in lowered for token in ("dashboard", "tracker", "table", "view", "viewer", "research notes", "notes")):
        return TEMPLATE_HTML_DASHBOARD
    if any(token in lowered for token in ("tool", "utility", "organizer")):
        return TEMPLATE_PYTHON_CLI
    return TEMPLATE_MARKDOWN_PRODUCT_PLAN


def _planned_files_for_template(template_id: str) -> tuple[str, ...]:
    if template_id == TEMPLATE_PYTHON_CLI:
        return ("README.md", "product_manifest.json", ".engel_product_profile.json", "src/main.py", "tests/test_smoke_plan.md")
    if template_id == TEMPLATE_HTML_DASHBOARD:
        return ("README.md", "product_manifest.json", ".engel_product_profile.json", "index.html", "styles.css")
    if template_id == TEMPLATE_STATIC_LANDING_PAGE:
        return ("README.md", "product_manifest.json", ".engel_product_profile.json", "index.html", "styles.css")
    return ("README.md", "product_manifest.json", "plan.md")


def _template_label(template_id: str) -> str:
    return {
        TEMPLATE_PYTHON_CLI: "Python CLI",
        TEMPLATE_HTML_DASHBOARD: "HTML dashboard",
        TEMPLATE_STATIC_LANDING_PAGE: "Static landing page",
        TEMPLATE_MARKDOWN_PRODUCT_PLAN: "Markdown product plan",
    }.get(template_id, template_id)


def _project_type_for_profile(template_id: str) -> str:
    if template_id == TEMPLATE_PYTHON_CLI:
        return "python_script"
    if template_id in {TEMPLATE_HTML_DASHBOARD, TEMPLATE_STATIC_LANDING_PAGE}:
        return "html_website"
    return "custom_project"


def _entrypoint_for_template(template_id: str) -> str:
    if template_id == TEMPLATE_PYTHON_CLI:
        return "src/main.py"
    if template_id in {TEMPLATE_HTML_DASHBOARD, TEMPLATE_STATIC_LANDING_PAGE}:
        return "index.html"
    return "README.md"


def _guardian_review() -> tuple[str, ...]:
    return (
        "Runtime source edit: NO",
        "Product-only creation: YES",
        "Code execution now: NO",
        "Package install: NO",
        "API/network: NO",
        "Trusted memory write: NO",
        "Approval required before create: YES",
        f"{AUTHORITY} preserved: YES",
    )


def _blocked_plan(idea: str, reason: str, markers: tuple[str, ...] = ()) -> ProjectBuilderPlan:
    return ProjectBuilderPlan(
        status=BLOCKED,
        idea=_compact_text(idea) or "No product idea provided.",
        selected_template="",
        product_slug="",
        product_name="",
        planned_files=tuple(),
        save_root=None,
        guardian_review=_guardian_review(),
        safety_notes=(
            reason,
            "No product scaffold was created.",
            "Talk-to-Code Project Builder did not edit runtime source, execute code, install packages, call APIs/network, scan external memory, or write trusted memory.",
        ),
        blocked_reason=reason,
        unsafe_markers=markers,
    )


def build_project_builder_plan(idea: str) -> ProjectBuilderPlan:
    compact = _compact_text(idea)
    if not compact:
        return _blocked_plan(idea, "ASK_FOR_DETAILS_REQUIRED: describe the product idea before planning.")

    markers = _scan_unsafe_project_request(idea)
    if markers:
        return _blocked_plan(idea, "UNSAFE_PROJECT_BUILDER_REQUEST: " + ", ".join(markers), markers)
    if _explicit_name_path_escape(idea):
        return _blocked_plan(idea, "UNSAFE_PRODUCT_SLUG: path traversal or path-like product name is blocked.")

    selected_template = classify_project_template(idea)
    if selected_template not in SUPPORTED_TEMPLATES:
        return _blocked_plan(idea, "UNSUPPORTED_PROJECT_TEMPLATE")

    product_name = product_name_from_idea(idea, selected_template)
    try:
        product_slug = product_templates.safe_product_slug(product_name)
        save_root = product_templates.product_path_for_slug(product_slug)
    except ValueError as exc:
        return _blocked_plan(idea, "UNSAFE_PRODUCT_SLUG: " + str(exc))

    return ProjectBuilderPlan(
        status=READY_TO_CREATE,
        idea=compact,
        selected_template=selected_template,
        product_slug=product_slug,
        product_name=product_name,
        planned_files=_planned_files_for_template(selected_template),
        save_root=save_root,
        guardian_review=_guardian_review(),
        safety_notes=(
            "PLAN_ONLY / NOT_TRUSTED_MEMORY / NOT_APPLIED until Josh clicks Create or an explicit create action is called.",
            "Create writes only under products\\<safe_slug>.",
            "Generated products are bounded artifacts, not trusted memory.",
            "No generated code execution, package install, API/network call, Browser Queen use, external memory scan, runtime source edit, or trusted memory write.",
        ),
    )


def render_project_builder_plan(plan: ProjectBuilderPlan) -> str:
    lines = [
        "# ENGEL PROJECT BUILDER PLAN",
        "",
        "Status:",
        (
            f"{PLAN_ONLY} / {NOT_TRUSTED_MEMORY} / {NOT_APPLIED}"
            if plan.status != BLOCKED
            else f"{BLOCKED} / {NOT_TRUSTED_MEMORY} / {NOT_APPLIED}"
        ),
        "",
        "Idea:",
        plan.idea,
        "",
        "Selected template:",
        plan.selected_template or "none",
        "",
        "Product slug:",
        plan.product_slug or "none",
        "",
        "Planned files:",
    ]
    if plan.planned_files:
        lines.extend("- " + path for path in plan.planned_files)
    else:
        lines.append("- none")
    lines.extend(["", "Guardian Review:"])
    lines.extend("- " + item for item in plan.guardian_review)
    lines.extend(["", "Boundary:"])
    lines.extend(
        [
            "Talk-to-Code Project Builder != Trusted Memory.",
            "Generated products != Trusted Memory.",
            "Product plans are proposals until created.",
            "Created products are bounded artifacts, not runtime source changes.",
        ]
    )
    lines.extend(["", "Safety:"])
    lines.extend("- " + note for note in plan.safety_notes)
    lines.extend(["", "Next:"])
    if plan.status == BLOCKED:
        lines.append("Revise the request before Create.")
    else:
        lines.append("Click Create only if Josh wants this bounded product scaffold generated.")
    return "\n".join(lines)


def _project_readme(plan: ProjectBuilderPlan) -> str:
    title = plan.product_name or plan.product_slug.replace("_", " ").title()
    return "\n".join(
        [
            "# " + title,
            "",
            "Status: " + PRODUCT_STATUS,
            "",
            "Authority: " + AUTHORITY,
            "",
            "Template: " + _template_label(plan.selected_template),
            "",
            "Idea:",
            plan.idea,
            "",
            "Boundary:",
            "- Product-only scaffold under APP_ROOT/products.",
            "- Generated product != Trusted Memory.",
            "- No Engel runtime source edit.",
            "- No generated-code execution by this create action.",
            "- No package install.",
            "- No API or network behavior.",
            "",
        ]
    )


def _manifest(plan: ProjectBuilderPlan, generated_files: tuple[str, ...]) -> str:
    payload = {
        "name": plan.product_name,
        "slug": plan.product_slug,
        "template_id": plan.selected_template,
        "created_by": "Engel Code Companion",
        "created_by_mode": "Talk-to-Code Project Builder",
        "status": PRODUCT_STATUS,
        "authority": AUTHORITY,
        "root_policy": "APP_ROOT/products only",
        "generated_files": list(generated_files),
        "dependencies": [],
        "install_required": False,
        "runtime_source_edit": False,
        "trusted_memory_write": "BLOCKED / NOT_PERFORMED",
    }
    return json.dumps(payload, indent=2) + "\n"


def _profile(plan: ProjectBuilderPlan) -> str:
    entrypoint = _entrypoint_for_template(plan.selected_template)
    product_type = _project_type_for_profile(plan.selected_template)
    launch_profiles: list[dict[str, object]]
    verification_profiles: list[dict[str, object]]
    if product_type == "python_script":
        launch_profiles = [
            {
                "name": "Run Python CLI",
                "kind": "launch",
                "command": ["python", entrypoint],
                "requires_approval": True,
            }
        ]
        verification_profiles = [
            {
                "name": "Compile Python CLI",
                "kind": "verify",
                "command": ["python", "-m", "py_compile", entrypoint],
                "requires_approval": True,
            }
        ]
    elif product_type == "html_website":
        launch_profiles = [
            {
                "name": "Open HTML Manually",
                "kind": "launch",
                "command": [],
                "requires_approval": True,
                "disabled": True,
                "instructions": "Open index.html manually if Josh chooses to inspect the product.",
            }
        ]
        verification_profiles = [
            {
                "name": "Basic HTML Structure",
                "kind": "verify",
                "command": [],
                "mode": "html_basic_structure",
                "requires_approval": True,
            }
        ]
    else:
        launch_profiles = [
            {
                "name": "Launch Instructions Only",
                "kind": "launch",
                "command": [],
                "requires_approval": True,
                "disabled": True,
            }
        ]
        verification_profiles = [
            {
                "name": "Bounded Structure Check",
                "kind": "verify",
                "command": [],
                "mode": "bounded_structure",
                "requires_approval": True,
            }
        ]
    payload = {
        "schema": "engel_product_profile_v1",
        "product_name": plan.product_slug,
        "product_type": product_type,
        "entrypoint": entrypoint,
        "allowed_launch_profiles": launch_profiles,
        "allowed_verification_profiles": verification_profiles,
        "allowed_package_profiles": [
            {
                "name": "Create Source Zip",
                "kind": "package",
                "mode": "source_zip",
                "output_dir": "dist",
                "requires_approval": True,
            }
        ],
        "authority": AUTHORITY,
        "safety": "APPROVAL_GATED / PRODUCT_ONLY / NOT_RUNTIME",
        "project_builder_boundary": "NOT_TRUSTED_MEMORY / NOT_APPLIED",
    }
    return json.dumps(payload, indent=2) + "\n"


def _python_cli_source(plan: ProjectBuilderPlan) -> str:
    title = plan.product_name.replace('"', "'")
    return "\n".join(
        [
            "# Engel Project Builder Product",
            "# Status: " + PRODUCT_STATUS,
            "# Authority: " + AUTHORITY,
            "",
            "def build_summary():",
            f"    return \"{title}: product-only CLI scaffold.\"",
            "",
            "",
            "def main():",
            "    print(build_summary())",
            "    print(\"Status: " + PRODUCT_STATUS + "\")",
            "",
            "",
            "if __name__ == \"__main__\":",
            "    main()",
            "",
        ]
    )


def _dashboard_html(plan: ProjectBuilderPlan, landing: bool = False) -> str:
    title = plan.product_name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    heading = "Product Overview" if landing else "Dashboard"
    return "\n".join(
        [
            "<!-- Engel Project Builder Product -->",
            "<!-- Status: " + PRODUCT_STATUS + " -->",
            "<!-- Authority: " + AUTHORITY + " -->",
            "<!doctype html>",
            "<html lang=\"en\">",
            "<head>",
            "  <meta charset=\"utf-8\">",
            "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">",
            "  <title>" + title + "</title>",
            "  <link rel=\"stylesheet\" href=\"styles.css\">",
            "</head>",
            "<body>",
            "  <main>",
            "    <header>",
            "      <p class=\"kicker\">PRODUCT_ONLY / NOT_RUNTIME / NOT_APPLIED</p>",
            "      <h1>" + title + "</h1>",
            "      <p>" + heading + " scaffold generated by Engel Project Builder.</p>",
            "    </header>",
            "    <section class=\"grid\" aria-label=\"status overview\">",
            "      <article><strong>Runtime source edit</strong><span>NO</span></article>",
            "      <article><strong>Code execution now</strong><span>NO</span></article>",
            "      <article><strong>Trusted memory write</strong><span>NO</span></article>",
            "    </section>",
            "  </main>",
            "</body>",
            "</html>",
            "",
        ]
    )


def _stylesheet() -> str:
    return "\n".join(
        [
            "/* Engel Project Builder Product",
            "   Status: " + PRODUCT_STATUS,
            "   Authority: " + AUTHORITY,
            "*/",
            "body { margin: 0; font-family: Arial, sans-serif; background: #f5f7fb; color: #172033; }",
            "main { max-width: 880px; margin: 0 auto; padding: 32px; }",
            "header { border-bottom: 1px solid #c8d1dc; padding-bottom: 18px; }",
            ".kicker { font-size: 12px; letter-spacing: 0; color: #4b5563; }",
            ".grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-top: 22px; }",
            "article { border: 1px solid #c8d1dc; border-radius: 8px; padding: 14px; background: white; }",
            "article span { display: block; margin-top: 8px; font-weight: 700; color: #0f766e; }",
            "",
        ]
    )


def _markdown_plan(plan: ProjectBuilderPlan) -> str:
    return "\n".join(
        [
            "# Product Plan",
            "",
            "Status: " + PRODUCT_STATUS,
            "",
            "Authority: " + AUTHORITY,
            "",
            "Idea:",
            plan.idea,
            "",
            "Planned direction:",
            "- Keep the product bounded under APP_ROOT/products.",
            "- Define files before implementation.",
            "- Add source only after Josh chooses a concrete template.",
            "",
            "Safety:",
            "- No runtime source edit.",
            "- No generated-code execution.",
            "- No package install.",
            "- No API or network behavior.",
            "- No trusted memory write.",
            "",
        ]
    )


def _core_product_files(plan: ProjectBuilderPlan) -> dict[str, str]:
    if plan.selected_template == TEMPLATE_PYTHON_CLI:
        files = {
            "README.md": _project_readme(plan),
            "src/main.py": _python_cli_source(plan),
            "tests/test_smoke_plan.md": "\n".join(
                [
                    "# Smoke Plan",
                    "",
                    "Status: " + PRODUCT_STATUS,
                    "",
                    "Authority: " + AUTHORITY,
                    "",
                    "This is a manual smoke plan only. The Project Builder create action did not execute generated code.",
                    "",
                ]
            ),
        }
    elif plan.selected_template == TEMPLATE_HTML_DASHBOARD:
        files = {
            "README.md": _project_readme(plan),
            "index.html": _dashboard_html(plan, landing=False),
            "styles.css": _stylesheet(),
        }
    elif plan.selected_template == TEMPLATE_STATIC_LANDING_PAGE:
        files = {
            "README.md": _project_readme(plan),
            "index.html": _dashboard_html(plan, landing=True),
            "styles.css": _stylesheet(),
        }
    else:
        files = {
            "README.md": _project_readme(plan),
            "plan.md": _markdown_plan(plan),
        }
    generated_files = tuple([*files.keys(), "product_manifest.json", ".engel_product_profile.json"])
    files["product_manifest.json"] = _manifest(plan, generated_files)
    return files


def _safe_relative_product_file(path_text: str) -> Path:
    raw = str(path_text or "").strip().replace("\\", "/")
    if not raw:
        raise ValueError("Empty product file path.")
    if raw.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", raw):
        raise ValueError("Absolute product file paths are blocked.")
    if raw.startswith(("//", "\\\\")) or "://" in raw:
        raise ValueError("URL/UNC product file paths are blocked.")
    parts = Path(raw).parts
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("Path traversal is blocked.")
    if any(part.startswith(".") for part in parts):
        raise ValueError("Hidden product source file paths are blocked.")
    return Path(*parts)


def _target_for_relative(product_path: Path, relative_text: str) -> Path:
    relative = _safe_relative_product_file(relative_text)
    target = (product_path / relative).resolve()
    product_root = product_path.resolve()
    try:
        target.relative_to(product_root)
    except ValueError as exc:
        raise ValueError("Product file escaped product root: " + relative_text) from exc
    return target


def _write_profile(product_path: Path, plan: ProjectBuilderPlan) -> Path:
    profile_path = (product_path / ".engel_product_profile.json").resolve()
    if profile_path.parent != product_path.resolve():
        raise ValueError("Product profile path escaped product root.")
    profile_path.write_text(_profile(plan), encoding="utf-8")
    return profile_path


def _write_project_builder_receipt(
    product_path: Path,
    plan: ProjectBuilderPlan,
    files_written: tuple[Path, ...],
    validation_status: str,
    approval_used: bool,
    backup_path: Path | None,
) -> Path:
    receipt_dir = product_path / "receipts"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    receipt_path = receipt_dir / f"{stamp}_project_builder_created.md"
    index = 1
    while receipt_path.exists():
        index += 1
        receipt_path = receipt_dir / f"{stamp}_project_builder_created_{index}.md"
    relative_files = []
    for path in files_written:
        try:
            relative_files.append(str(path.relative_to(product_path)).replace("\\", "/"))
        except ValueError:
            relative_files.append(path.name)
    receipt_path.write_text(
        "\n".join(
            [
                "# Engel Project Builder Product Receipt",
                "",
                "Status:",
                "PRODUCT_CREATED / NOT_TRUSTED_MEMORY / NOT_APPLIED",
                "",
                "Authority:",
                AUTHORITY,
                "",
                "Idea:",
                plan.idea,
                "",
                "Selected template:",
                plan.selected_template,
                "",
                "Product root:",
                str(product_path),
                "",
                "Files written:",
                *["- " + item for item in relative_files],
                "",
                "Validation:",
                validation_status,
                "",
                "Overwrite approval used:",
                "YES" if approval_used else "NO",
                "",
                "Backup path:",
                str(backup_path) if backup_path else "none",
                "",
                "Safety:",
                "- Runtime source edit: NO",
                "- Code execution now: NO",
                "- Package install: NO",
                "- API/network: NO",
                "- Browser Queen invoked: NO",
                "- External memory scanned: NO",
                "- Trusted memory write: NO",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return receipt_path


def create_project_builder_product(plan: ProjectBuilderPlan, approval_token: str | None = None) -> ProjectBuilderCreateResult:
    if plan.status == BLOCKED:
        return ProjectBuilderCreateResult(False, BLOCKED, None, tuple(), None, "BLOCKED", plan.blocked_reason)
    if plan.selected_template not in SUPPORTED_TEMPLATES:
        return ProjectBuilderCreateResult(False, "UNSUPPORTED_PROJECT_TEMPLATE", None, tuple(), None, "NOT_RUN", "Unsupported Project Builder template.")
    try:
        product_path = product_templates.product_path_for_slug(plan.product_slug)
    except ValueError as exc:
        return ProjectBuilderCreateResult(False, "BLOCKED_PRODUCT_PATH", None, tuple(), None, "NOT_RUN", str(exc))
    if not product_templates.is_safe_product_path(product_path):
        return ProjectBuilderCreateResult(False, "BLOCKED_PRODUCT_PATH", product_path, tuple(), None, "NOT_RUN", "Product path escaped APP_ROOT/products.")
    if product_path.exists() and not product_path.is_dir():
        return ProjectBuilderCreateResult(False, "BLOCKED_PRODUCT_PATH", product_path, tuple(), None, "NOT_RUN", "Product path is not a directory.")

    core_files = _core_product_files(plan)
    validation = product_templates.validate_product_files(core_files)
    if not validation.ok:
        return ProjectBuilderCreateResult(False, validation.status, product_path, tuple(), None, validation.status, validation.message)

    backup_path: Path | None = None
    approval_used = False
    if product_path.exists():
        if str(approval_token or "").strip() != APPROVAL_TOKEN:
            return ProjectBuilderCreateResult(
                False,
                "BLOCKED_EXISTING_PRODUCT / APPROVE_CHANGE_REQUIRED",
                product_path,
                tuple(),
                None,
                validation.status,
                "Existing product overwrite requires the existing approved overwrite flow.",
            )
        backup_path = product_templates.backup_existing_product(product_path)
        approval_used = True

    product_templates.products_root().mkdir(parents=True, exist_ok=True)
    product_path.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    try:
        for relative_text, content in core_files.items():
            target = _target_for_relative(product_path, relative_text)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            written.append(target)
        if ".engel_product_profile.json" in plan.planned_files:
            written.append(_write_profile(product_path, plan))
        receipt_path = _write_project_builder_receipt(product_path, plan, tuple(written), validation.status, approval_used, backup_path)
    except Exception as exc:
        return ProjectBuilderCreateResult(False, "PROJECT_BUILDER_WRITE_BLOCKED", product_path, tuple(written), None, validation.status, str(exc))

    return ProjectBuilderCreateResult(
        True,
        "PROJECT_BUILDER_PRODUCT_CREATED" if not approval_used else "PROJECT_BUILDER_PRODUCT_OVERWRITTEN_WITH_APPROVE_CHANGE",
        product_path,
        tuple(written),
        receipt_path,
        validation.status,
        "Project Builder scaffold written under APP_ROOT/products. Generated code was not executed.",
    )


def render_project_builder_create_result(result: ProjectBuilderCreateResult) -> str:
    lines = [
        "# ENGEL PROJECT BUILDER CREATE RESULT",
        "",
        "Status:",
        result.status,
        "",
        "Product path:",
        str(result.product_path) if result.product_path else "none",
        "",
        "Validation:",
        result.validation_status,
        "",
        "Message:",
        result.message,
    ]
    if result.files_written:
        lines.extend(["", "Files written:"])
        lines.extend("- " + str(path) for path in result.files_written)
    lines.extend(
        [
            "",
            "Safety:",
            "- Product-only scaffold",
            "- No runtime source edit",
            "- No generated-code execution",
            "- No package install",
            "- No provider/API/network behavior",
            "- No Browser Queen use",
            "- No external memory scan",
            "- No trusted memory write",
            f"- {AUTHORITY} preserved",
        ]
    )
    return "\n".join(lines)
