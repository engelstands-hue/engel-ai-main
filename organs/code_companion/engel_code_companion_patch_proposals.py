from __future__ import annotations

import difflib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import engel_code_companion_contextual_talk as contextual_talk
import engel_code_companion_products as product_templates
import engel_untrusted_content_guard as untrusted_content_guard


ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
AUTHORITY = "Josh > Guardian > Engel/runtime"
PRODUCT_PATCH_PROPOSAL = "PRODUCT_PATCH_PROPOSAL"
PATCH_PROPOSAL_ONLY = "PATCH_PROPOSAL_ONLY"
NOT_APPLIED = "NOT_APPLIED"
PRODUCT_ONLY = "PRODUCT_ONLY"
NOT_TRUSTED_MEMORY = "NOT_TRUSTED_MEMORY"
SELECT_PRODUCT_REQUIRED = "SELECT_PRODUCT_REQUIRED"
BLOCKED_UNSAFE_PATCH_REQUEST = "BLOCKED_UNSAFE_PATCH_REQUEST"
APPROVE_PRODUCT_PATCH = "APPROVE_PRODUCT_PATCH"
MAX_PATCH_READ_CHARS = 80_000

UNSAFE_PATCH_REQUEST_PATTERNS: tuple[tuple[str, str], ...] = (
    ("runtime source edit", r"\b(edit|modify|patch|rewrite|change)\b.{0,70}\b(engel runtime|runtime source|engel source|engel_app|engel_companion)\b"),
    ("guardian bypass", r"\b(ignore|bypass|disable|override)\b.{0,45}\b(guardian|safety|authority)\b"),
    ("authority hierarchy change", r"\b(change|invert|override)\b.{0,55}\b(authority hierarchy|josh|guardian)\b"),
    ("trusted memory write", r"\b(write|update|store|promote|make permanent)\b.{0,55}\b(trusted memory|memory candidate|memory index)\b"),
    ("package install", r"\b(install|pip install|npm install|add package|download package|dependency)\b"),
    ("code execution", r"\b(execute|executes|run|runs|launch|start)\b.{0,45}\b(code|test|generated|script|program|now|immediately)\b"),
    ("api or network", r"\b(call|calls|use|uses|connect|fetch|scrape|send)\b.{0,65}\b(api|network|openai|provider|http|https|web)\b"),
    ("queue route source mutation", r"\b(mutate|change|rewrite|edit)\b.{0,55}\b(queue|route|runtime source|source tree)\b"),
    ("broad external edit", r"\b(edit|modify|patch|rewrite)\b.{0,55}\b(D:\\|E:\\|G:\\|external memory|whole drive|outside product)\b"),
    ("embedded approval token", r"\bAPPROVE_[A-Z_]+\b"),
)

PATCH_REQUEST_PATTERNS: tuple[str, ...] = (
    r"\bimprove\s+this\s+product\b",
    r"\bimprove\s+selected\s+product\b",
    r"\bmake\s+this\s+product\s+better\b",
    r"\bmake\s+(the\s+)?readme\s+better(\s+too)?\b",
    r"\bmake\s+the\s+docs\s+better(\s+too)?\b",
    r"\bimprove\s+readme\b",
    r"\bimprove\s+this\s+product.{0,80}\breadme\b",
    r"\badd\s+(better\s+)?instructions\b",
    r"\badd\s+(a\s+)?smoke\s+test\b",
    r"\badd\s+(a\s+)?test\s+plan\b",
    r"\bmake\s+(this\s+)?product\s+easier\s+to\s+use\b",
    r"\bimprove\s+manifest\b",
    r"\bpatch\s+proposal\b",
    r"\bpropose\s+changes\b",
    r"\bimprove\s+dashboard\s+copy\b",
)


@dataclass(frozen=True)
class PatchProposalFile:
    relative_path: str
    action: str
    proposed_content: str
    diff_preview: str
    operation: str = ""


@dataclass(frozen=True)
class ProductPatchProposal:
    ok: bool
    status: str
    product_slug: str
    product_path: Path | None
    user_request: str
    files: tuple[PatchProposalFile, ...] = ()
    context_text: str = ""
    guardian_review: tuple[str, ...] = ()
    safety_notes: tuple[str, ...] = ()
    message: str = ""
    blocked_reason: str = ""
    unsafe_markers: tuple[str, ...] = field(default_factory=tuple)


def is_patch_proposal_request(text: str) -> bool:
    lowered = (text or "").lower()
    if not lowered.strip():
        return False
    if "research" in lowered and any(word in lowered for word in ("summary", "intake")):
        return False
    return any(re.search(pattern, lowered, re.IGNORECASE) for pattern in PATCH_REQUEST_PATTERNS)


def scan_unsafe_patch_request(text: str) -> tuple[str, ...]:
    markers: list[str] = []
    lowered = (text or "").lower()
    for label, pattern in UNSAFE_PATCH_REQUEST_PATTERNS:
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


def _compact_text(text: str, max_chars: int = 260) -> str:
    collapsed = " ".join(str(text or "").strip().split())
    if not collapsed:
        return "No request provided."
    if len(collapsed) > max_chars:
        return collapsed[: max_chars - 3].rstrip() + "..."
    return collapsed


def _guardian_review() -> tuple[str, ...]:
    return (
        "Product files changed now: NO",
        "Engel runtime source edit: NO",
        "Code execution now: NO",
        "Package install: NO",
        "API/network: NO",
        "Trusted memory write: NO",
        "Approval required before apply: YES",
        "Future token: APPROVE_PRODUCT_PATCH",
        f"{AUTHORITY} preserved: YES",
    )


def _safety_notes() -> tuple[str, ...]:
    return (
        "This patch proposal did not edit files.",
        "This patch proposal did not execute code.",
        "This patch proposal did not update trusted memory.",
        "This patch proposal did not change Engel behavior.",
        "Future apply is not implemented in this task.",
    )


def _blocked(
    *,
    product_slug: str,
    product_path: Path | None,
    request: str,
    reason: str,
    markers: tuple[str, ...] = (),
) -> ProductPatchProposal:
    return ProductPatchProposal(
        ok=False,
        status=reason,
        product_slug=product_slug,
        product_path=product_path,
        user_request=_compact_text(request),
        context_text=contextual_talk.render_context_for_selected_product(product_slug or None),
        guardian_review=_guardian_review(),
        safety_notes=_safety_notes(),
        message=reason,
        blocked_reason=reason,
        unsafe_markers=markers,
    )


def _product_root_for_slug(slug: str) -> tuple[str, Path]:
    safe_slug = product_templates.safe_product_slug(slug)
    product_path = product_templates.product_path_for_slug(safe_slug)
    if not product_templates.is_safe_product_path(product_path):
        raise ValueError("Selected product must be a direct child of APP_ROOT/products.")
    if not product_path.exists() or not product_path.is_dir():
        raise ValueError("Selected product does not exist under products.")
    if product_path.is_symlink():
        raise ValueError("Selected product symlinks are blocked.")
    return safe_slug, product_path


def _relative_target(product_path: Path, relative_text: str) -> Path:
    raw = str(relative_text or "").strip().replace("\\", "/")
    if not raw or raw.startswith(("/", "\\")) or "://" in raw or raw.startswith("//") or re.match(r"^[A-Za-z]:", raw):
        raise ValueError("Unsafe product patch path: " + str(relative_text))
    parts = Path(raw).parts
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("Path traversal blocked in patch proposal path: " + str(relative_text))
    target = (product_path / Path(*parts)).resolve()
    try:
        target.relative_to(product_path.resolve())
    except ValueError as exc:
        raise ValueError("Patch proposal path escaped product root: " + str(relative_text)) from exc
    return target


def _read_existing_text(product_path: Path, relative_text: str) -> str:
    target = _relative_target(product_path, relative_text)
    if not target.exists() or not target.is_file() or target.is_symlink():
        return ""
    try:
        with target.open("r", encoding="utf-8", errors="replace") as handle:
            return handle.read(MAX_PATCH_READ_CHARS + 1)[:MAX_PATCH_READ_CHARS]
    except OSError:
        return ""


def _diff(relative_path: str, before: str, after: str) -> str:
    rendered = list(
        difflib.unified_diff(
            before.splitlines(),
            after.splitlines(),
            fromfile=relative_path + " (current)",
            tofile=relative_path + " (proposed)",
            lineterm="",
        )
    )
    return "\n".join(rendered or ["# New file has no existing content."])


def _manifest_payload(product_slug: str, product_path: Path, request: str, existing_text: str) -> dict[str, object]:
    payload: dict[str, object] = {}
    if existing_text.strip():
        try:
            parsed = json.loads(existing_text)
            if isinstance(parsed, dict):
                payload = parsed
        except json.JSONDecodeError:
            payload = {}
    payload.setdefault("name", product_slug.replace("_", " ").title())
    payload.setdefault("slug", product_slug)
    payload.setdefault("created_by", "Engel Code Companion")
    payload["status"] = product_templates.PRODUCT_STATUS
    payload["authority"] = AUTHORITY
    payload["root_policy"] = "APP_ROOT/products only"
    payload["dependencies"] = []
    payload["install_required"] = False
    payload["patch_proposal"] = {
        "status": "PATCH_PROPOSAL_ONLY / NOT_APPLIED",
        "request": _compact_text(request),
        "future_apply_token": APPROVE_PRODUCT_PATCH,
        "runtime_source_edit": False,
        "trusted_memory_write": "BLOCKED / NOT_PERFORMED",
    }
    try:
        payload["product_root"] = str(product_path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        payload["product_root"] = product_slug
    return payload


def _readme_proposal(product_slug: str, request: str, existing_text: str) -> str:
    title = product_slug.replace("_", " ").title()
    base = existing_text.strip()
    if not base:
        base = "# " + title + "\n\nStatus: " + product_templates.PRODUCT_STATUS + "\n\nAuthority: " + AUTHORITY + "\n"
    addition = "\n\n## Usage Notes\n\n- Open this product from Code Companion Preview before running anything.\n- Review product health before packaging or launch work.\n- Keep generated content product-only and proposal-reviewed.\n\n## Smoke Test Plan\n\n1. Preview README.md.\n2. Preview product_manifest.json.\n3. Run Product Health from Code Companion.\n4. Do not execute generated code unless a separate approved launch/verification flow is used.\n\nPatch proposal request: " + _compact_text(request) + "\n"
    if "## Usage Notes" in base and "## Smoke Test Plan" in base:
        addition = "\n\n## Patch Proposal Notes\n\n- Confirm README instructions remain current.\n- Confirm smoke test plan is easy for Josh to follow.\n\nPatch proposal request: " + _compact_text(request) + "\n"
    return base.rstrip() + addition


def _test_plan_proposal(product_slug: str, request: str, existing_text: str) -> str:
    base = existing_text.strip()
    if not base:
        base = "# Smoke Test Plan\n\nStatus: " + product_templates.PRODUCT_STATUS + "\n\nAuthority: " + AUTHORITY + "\n"
    addition = "\n\n## Proposed Manual Smoke\n\n1. Confirm README.md is present and readable.\n2. Confirm product_manifest.json parses as JSON.\n3. Confirm Product Preview opens without executing product code.\n4. Confirm Product Health reports expected product-only boundaries.\n5. Record any issues before requesting a future patch apply.\n\nRequest: " + _compact_text(request) + "\n"
    return base.rstrip() + addition


def _source_copy_proposal(relative_path: str, request: str, existing_text: str) -> str:
    if not existing_text.strip():
        return existing_text
    lowered_path = relative_path.lower()
    note = "Engel patch proposal: " + _compact_text(request)
    if lowered_path.endswith(".html"):
        marker = "\n<!-- " + note + " -->\n"
    elif lowered_path.endswith(".css"):
        marker = "\n/* " + note + " */\n"
    elif lowered_path.endswith(".py"):
        marker = "\n# " + note + "\n"
    elif lowered_path.endswith(".js"):
        marker = "\n// " + note + "\n"
    else:
        marker = "\n\n" + note + "\n"
    return existing_text.rstrip() + marker


def _candidate_files(product_slug: str, product_path: Path, request: str) -> list[tuple[str, str]]:
    lowered = request.lower()
    proposals: list[tuple[str, str]] = []

    if any(token in lowered for token in ("readme", "instruction", "easier to use", "better", "smoke test", "test plan", "patch proposal")):
        before = _read_existing_text(product_path, "README.md")
        proposals.append(("README.md", _readme_proposal(product_slug, request, before)))

    if any(token in lowered for token in ("manifest", "dashboard copy", "patch proposal", "better")):
        before = _read_existing_text(product_path, "product_manifest.json")
        manifest = _manifest_payload(product_slug, product_path, request, before)
        proposals.append(("product_manifest.json", json.dumps(manifest, indent=2) + "\n"))

    if any(token in lowered for token in ("smoke test", "test plan", "tests", "simple test")):
        before = _read_existing_text(product_path, "tests/test_smoke_plan.md")
        proposals.append(("tests/test_smoke_plan.md", _test_plan_proposal(product_slug, request, before)))

    if "dashboard copy" in lowered or "copy" in lowered:
        for relative in ("index.html", "src/main.py"):
            before = _read_existing_text(product_path, relative)
            if before.strip():
                proposals.append((relative, _source_copy_proposal(relative, request, before)))
                break

    if not proposals:
        before = _read_existing_text(product_path, "README.md")
        proposals.append(("README.md", _readme_proposal(product_slug, request, before)))
        before_plan = _read_existing_text(product_path, "tests/test_smoke_plan.md")
        proposals.append(("tests/test_smoke_plan.md", _test_plan_proposal(product_slug, request, before_plan)))

    # Preserve order while avoiding duplicate relative paths.
    unique: dict[str, str] = {}
    for relative, content in proposals:
        unique.setdefault(relative, content)
    return list(unique.items())[:8]


def build_product_patch_proposal(selected_product: str | None, request: str) -> ProductPatchProposal:
    request_text = _compact_text(request)
    if not str(selected_product or "").strip():
        return _blocked(product_slug="", product_path=None, request=request_text, reason=SELECT_PRODUCT_REQUIRED)

    markers = scan_unsafe_patch_request(request)
    if markers:
        return _blocked(
            product_slug=str(selected_product or ""),
            product_path=None,
            request=request_text,
            reason=BLOCKED_UNSAFE_PATCH_REQUEST,
            markers=markers,
        )

    try:
        product_slug, product_path = _product_root_for_slug(str(selected_product or ""))
    except ValueError as exc:
        return _blocked(product_slug=str(selected_product or ""), product_path=None, request=request_text, reason=str(exc))

    try:
        files: list[PatchProposalFile] = []
        for relative, proposed in _candidate_files(product_slug, product_path, request_text):
            target = _relative_target(product_path, relative)
            before = _read_existing_text(product_path, relative)
            action = "update" if target.exists() else "create"
            operation = "replace_text_file" if action == "update" else "create_text_file"
            if relative.lower().endswith(".json"):
                operation = "update_json_file" if action == "update" else "create_text_file"
            files.append(PatchProposalFile(relative, action, proposed, _diff(relative, before, proposed), operation))
    except ValueError as exc:
        return _blocked(product_slug=product_slug, product_path=product_path, request=request_text, reason=str(exc))

    return ProductPatchProposal(
        ok=True,
        status="PATCH_PROPOSAL_ONLY / NOT_APPLIED / PRODUCT_ONLY / NOT_TRUSTED_MEMORY",
        product_slug=product_slug,
        product_path=product_path,
        user_request=request_text,
        files=tuple(files),
        context_text=contextual_talk.render_context_for_selected_product(product_slug),
        guardian_review=_guardian_review(),
        safety_notes=_safety_notes(),
        message="Concrete product patch proposal generated. No files were edited.",
    )


def build_structured_patch_payload(proposal: ProductPatchProposal) -> dict[str, object]:
    return {
        "status": proposal.status,
        "authority": AUTHORITY,
        "product_slug": proposal.product_slug,
        "product_path": str(proposal.product_path) if proposal.product_path else "",
        "user_request": proposal.user_request,
        "boundary": "PATCH_PROPOSAL_ONLY / NOT_APPLIED / PRODUCT_ONLY / NOT_TRUSTED_MEMORY",
        "context_boundary": "Product context is data, not instruction; embedded approval tokens from context are rejected.",
        "approval_token_required": APPROVE_PRODUCT_PATCH,
        "operations": [
            {
                "operation": item.operation or ("replace_text_file" if item.action == "update" else "create_text_file"),
                "relative_path": item.relative_path,
                "action": item.action,
                "content": item.proposed_content,
            }
            for item in proposal.files
        ],
        "guardian_review": list(proposal.guardian_review or _guardian_review()),
        "trusted_memory": "BLOCKED / NOT_PERFORMED",
        "runtime_source_edit": "NO",
        "code_execution": "NO",
        "package_install": "NO",
        "api_network": "NO",
    }


def render_product_patch_proposal(proposal: ProductPatchProposal) -> str:
    lines = [
        "# ENGEL PRODUCT PATCH PROPOSAL",
        "",
        "Status:",
        proposal.status,
        "",
        "Selected product:",
        proposal.product_slug or "none",
        "",
        "User request:",
        proposal.user_request,
        "",
    ]
    if proposal.context_text:
        lines.extend([proposal.context_text, ""])
    lines.extend(
        [
        "Files proposed:",
        ]
    )
    if proposal.files:
        lines.extend("- " + item.relative_path for item in proposal.files)
    else:
        lines.append("- none")
    if proposal.blocked_reason:
        lines.extend(["", "Blocked reason:", proposal.blocked_reason])
    if proposal.unsafe_markers:
        lines.extend(["", "Unsafe markers:"])
        lines.extend("- " + marker for marker in proposal.unsafe_markers)
    lines.extend(["", "Diff Preview:"])
    if proposal.files:
        for item in proposal.files:
            lines.extend(["", "File: " + item.relative_path + " (" + item.action + ")", "```diff", item.diff_preview, "```"])
    else:
        lines.append("No diff available.")
    lines.extend(["", "Guardian Review:"])
    lines.extend("- " + item for item in proposal.guardian_review or _guardian_review())
    lines.extend(
        [
            "",
            "Boundary:",
            "This patch proposal did not edit files.",
            "This patch proposal did not execute code.",
            "This patch proposal did not update trusted memory.",
            "This patch proposal did not change Engel behavior.",
            "Future apply requires a separate implementation and explicit APPROVE_PRODUCT_PATCH approval.",
            "",
            "Safety:",
        ]
    )
    lines.extend("- " + item for item in proposal.safety_notes or _safety_notes())
    if proposal.message:
        lines.extend(["", "Message:", proposal.message])
    if proposal.ok:
        payload = build_structured_patch_payload(proposal)
        payload_preview = {
            key: value
            for key, value in payload.items()
            if key not in {"operations"}
        }
        payload_preview["operations"] = [
            {
                "operation": item["operation"],
                "relative_path": item["relative_path"],
                "action": item["action"],
                "content_sha256_hint": "available inside structured in-memory payload",
            }
            for item in payload["operations"]
            if isinstance(item, dict)
        ]
        lines.extend(
            [
                "",
                "Structured Patch Payload:",
                "```json",
                json.dumps(payload_preview, indent=2),
                "```",
            ]
        )
    return "\n".join(lines)


def render_patch_apply_future_only(proposal: ProductPatchProposal) -> str:
    return "\n".join(
        [
            "# ENGEL PRODUCT PATCH APPLY",
            "",
            "Status:",
            "PRODUCT_PATCH_APPLY_BLOCKED / APPROVE_PRODUCT_PATCH_REQUIRED / NOT_APPLIED",
            "",
            "Selected product:",
            proposal.product_slug or "none",
            "",
            "Boundary:",
            "Apply requires exact APPROVE_PRODUCT_PATCH from explicit user input.",
            "No product files were edited.",
            "No Engel runtime source was edited.",
            "No generated code was executed.",
            "No trusted memory was written.",
            "",
            "Proposal preview:",
            render_product_patch_proposal(proposal),
        ]
    )
