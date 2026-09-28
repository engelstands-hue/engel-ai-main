from __future__ import annotations

import difflib
import json
from dataclasses import dataclass
from pathlib import Path

import engel_code_companion_products as products


APP_ROOT = Path(__file__).resolve().parent
AUTHORITY = "Josh > Guardian > Engel/runtime"
PROPOSAL_STATUS = "PROPOSAL_ONLY / NOT_APPLIED / PRODUCT_ONLY"
MAX_READ_CHARS = 40_000


@dataclass(frozen=True)
class ReadmeManifestFileProposal:
    relative_path: str
    action: str
    existing_content: str
    proposed_content: str
    diff: str


@dataclass(frozen=True)
class ReadmeManifestProposal:
    ok: bool
    status: str
    product_slug: str
    product_path: Path | None
    health_status: str = "UNKNOWN"
    readme: ReadmeManifestFileProposal | None = None
    manifest: ReadmeManifestFileProposal | None = None
    profile_status: str = "UNKNOWN"
    guardian_review: tuple[str, ...] = ()
    safety_notes: tuple[str, ...] = ()
    message: str = ""


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _blocked(slug: str, message: str, product_path: Path | None = None) -> ReadmeManifestProposal:
    return ReadmeManifestProposal(
        ok=False,
        status="README_MANIFEST_PROPOSAL_BLOCKED / NOT_APPLIED",
        product_slug=str(slug or ""),
        product_path=product_path,
        guardian_review=_guardian_review(product_context=False),
        safety_notes=(
            "README/Manifest proposal was blocked.",
            "No product files were changed.",
            "No runtime source files were changed.",
            "No product code was executed.",
        ),
        message=message,
    )


def _guard_product_slug(slug: str) -> str:
    text = str(slug or "").strip()
    lowered = text.lower()
    if not text:
        raise ValueError("Product slug is required.")
    if lowered.startswith(("http://", "https://")):
        raise ValueError("URL product identifiers are blocked.")
    if text.startswith(("\\\\", "//", "\\", "/")):
        raise ValueError("Absolute or UNC product paths are blocked.")
    if ":" in text:
        raise ValueError("Drive paths and path-like product identifiers are blocked.")
    if "/" in text or "\\" in text:
        raise ValueError("Product identifiers must be plain bounded handles.")
    if ".." in text:
        raise ValueError("Path traversal product identifiers are blocked.")
    return products.safe_product_slug(text)


def _product_root(slug: str) -> tuple[str, Path]:
    safe_slug = _guard_product_slug(slug)
    product_path = products.product_path_for_slug(safe_slug)
    if not products.is_safe_product_path(product_path):
        raise ValueError("Product path is outside APP_ROOT/products.")
    return safe_slug, product_path


def _target_for_relative(product_path: Path, relative_path: str) -> Path:
    text = str(relative_path or "").strip().replace("\\", "/")
    if not text or text.startswith(("/", "\\")) or ":" in text:
        raise ValueError("Proposal target must be a relative product path.")
    parts = Path(text).parts
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("Proposal target cannot escape the product folder.")
    target = (product_path / Path(*parts)).resolve(strict=False)
    root = product_path.resolve(strict=False)
    if not _is_relative_to(target, root):
        raise ValueError("Proposal target resolved outside the product folder.")
    return target


def _read_text_if_present(path: Path) -> str:
    if not path.exists() or not path.is_file() or path.is_symlink():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    return text[:MAX_READ_CHARS]


def _read_json_if_present(product_path: Path, relative_path: str) -> dict[str, object]:
    target = _target_for_relative(product_path, relative_path)
    if not target.exists() or not target.is_file() or target.is_symlink():
        return {}
    try:
        parsed = json.loads(target.read_text(encoding="utf-8", errors="replace"))
    except (OSError, TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _append_section_once(content: str, heading: str, body: str) -> str:
    if heading.lower() in content.lower():
        return content.rstrip() + "\n"
    return content.rstrip() + "\n\n" + heading + "\n" + body.strip() + "\n"


def _product_name(product_slug: str, manifest: dict[str, object], profile: dict[str, object]) -> str:
    for payload in (manifest, profile):
        value = payload.get("name")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return product_slug.replace("_", " ").title()


def _proposed_readme(product_slug: str, existing: str, manifest: dict[str, object], profile: dict[str, object]) -> str:
    name = _product_name(product_slug, manifest, profile)
    template = str(manifest.get("template_id") or profile.get("template_id") or "unknown")
    if existing.strip():
        proposed = existing.rstrip() + "\n"
    else:
        proposed = f"# {name}\n\nStatus: PRODUCT_ONLY / NOT_RUNTIME / NOT_APPLIED\n"
    proposed = _append_section_once(
        proposed,
        "## Purpose",
        f"{name} is a bounded Code Companion product. Template: {template}.",
    )
    proposed = _append_section_once(
        proposed,
        "## Usage",
        "Document manual inputs, expected outputs, and any approval-gated launch or package steps before use.",
    )
    proposed = _append_section_once(
        proposed,
        "## Validation",
        "Use product health and smoke-test checks as proposal-only guidance. Do not execute product code automatically.",
    )
    proposed = _append_section_once(
        proposed,
        "## Safety",
        "README/Manifest Proposal != Applied Change. Future edits require a separate explicit approval workflow.",
    )
    return proposed


def _normalize_manifest(product_slug: str, manifest: dict[str, object], profile: dict[str, object]) -> dict[str, object]:
    normalized = dict(manifest)
    normalized["name"] = _product_name(product_slug, manifest, profile)
    normalized["slug"] = product_slug
    normalized["template_id"] = str(normalized.get("template_id") or profile.get("template_id") or "unknown")
    normalized["created_by"] = str(normalized.get("created_by") or "Engel Code Companion")
    normalized["status"] = "PRODUCT_ONLY / NOT_RUNTIME / NOT_APPLIED"
    normalized["authority"] = AUTHORITY
    normalized["root_policy"] = "APP_ROOT/products only"
    dependencies = normalized.get("dependencies")
    normalized["dependencies"] = dependencies if isinstance(dependencies, list) else []
    normalized["install_required"] = bool(normalized.get("install_required")) if "install_required" in normalized else False
    normalized["proposal_boundary"] = "README/Manifest Proposal != Applied Change"
    normalized["proposal_status"] = PROPOSAL_STATUS
    return normalized


def _json_text(payload: dict[str, object]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _unified_diff(relative_path: str, old: str, new: str) -> str:
    diff = difflib.unified_diff(
        old.splitlines(),
        new.splitlines(),
        fromfile=relative_path,
        tofile=relative_path,
        lineterm="",
    )
    return "\n".join(diff)


def _file_proposal(product_path: Path, relative_path: str, proposed_content: str) -> ReadmeManifestFileProposal:
    target = _target_for_relative(product_path, relative_path)
    existing = _read_text_if_present(target)
    action = "update" if existing else "create"
    return ReadmeManifestFileProposal(
        relative_path=relative_path,
        action=action,
        existing_content=existing,
        proposed_content=proposed_content,
        diff=_unified_diff(relative_path, existing, proposed_content),
    )


def _guardian_review(product_context: bool = True) -> tuple[str, ...]:
    return (
        "- Product files changed now: NO",
        "- Runtime source edit: NO",
        "- Code execution: NO",
        "- API/network: NO",
        "- Package install: NO",
        "- Product-only context: " + ("YES" if product_context else "NO"),
        "- Approval required before apply: YES",
        "- Josh > Guardian > Engel/runtime preserved: YES",
    )


def build_readme_manifest_proposal(slug: str) -> ReadmeManifestProposal:
    try:
        safe_slug, product_path = _product_root(slug)
    except ValueError as exc:
        return _blocked(slug, str(exc))
    if not product_path.exists() or not product_path.is_dir():
        return _blocked(safe_slug, "Product folder does not exist.", product_path)
    if product_path.is_symlink():
        return _blocked(safe_slug, "Product folder symlinks are blocked.", product_path)

    health = products.product_health_check(safe_slug)
    manifest = _read_json_if_present(product_path, "product_manifest.json")
    profile = _read_json_if_present(product_path, ".engel_product_profile.json")
    readme_existing = _read_text_if_present(_target_for_relative(product_path, "README.md"))
    readme = _file_proposal(product_path, "README.md", _proposed_readme(safe_slug, readme_existing, manifest, profile))
    manifest_proposal = _file_proposal(
        product_path,
        "product_manifest.json",
        _json_text(_normalize_manifest(safe_slug, manifest, profile)),
    )
    profile_status = "PRESENT" if profile else "MISSING_OR_UNREADABLE"
    return ReadmeManifestProposal(
        ok=True,
        status=PROPOSAL_STATUS,
        product_slug=safe_slug,
        product_path=product_path,
        health_status=health.status,
        readme=readme,
        manifest=manifest_proposal,
        profile_status=profile_status,
        guardian_review=_guardian_review(),
        safety_notes=(
            "README/Manifest Proposal != Applied Change.",
            "No README or manifest files were edited.",
            "No runtime source files were changed.",
            "No product code was executed.",
            "No API/network/package behavior was added.",
        ),
        message="Deterministic README and manifest proposal rendered only.",
    )


def render_readme_manifest_proposal(proposal: ReadmeManifestProposal) -> str:
    root_text = "blocked"
    if proposal.product_path is not None:
        try:
            root_text = str(proposal.product_path.relative_to(APP_ROOT)).replace("\\", "/")
        except ValueError:
            root_text = str(proposal.product_path)
    lines = [
        "# README / Manifest Proposal",
        "",
        "Status:",
        proposal.status,
        "",
        "Authority:",
        AUTHORITY,
        "",
        "Boundary:",
        "README/Manifest Proposal != Applied Change.",
        "This proposal does not edit README.md, product_manifest.json, runtime files, or trusted memory.",
        "",
        "Product:",
        proposal.product_slug,
        "",
        "Root:",
        root_text,
        "",
        "Health status:",
        proposal.health_status,
        "",
        "Profile status:",
        proposal.profile_status,
        "",
        "README proposal:",
    ]
    if proposal.readme is not None:
        lines.extend(
            [
                "Action: " + proposal.readme.action,
                "```text",
                proposal.readme.proposed_content.rstrip(),
                "```",
                "",
                "README diff:",
                "```diff",
                proposal.readme.diff or "(no diff)",
                "```",
            ]
        )
    else:
        lines.append("No README proposal available.")
    lines.extend(["", "Manifest proposal:"])
    if proposal.manifest is not None:
        lines.extend(
            [
                "Action: " + proposal.manifest.action,
                "```json",
                proposal.manifest.proposed_content.rstrip(),
                "```",
                "",
                "Manifest diff:",
                "```diff",
                proposal.manifest.diff or "(no diff)",
                "```",
            ]
        )
    else:
        lines.append("No manifest proposal available.")
    lines.extend(["", "Guardian Review:"])
    lines.extend(proposal.guardian_review or _guardian_review(product_context=False))
    lines.extend(["", "Safety:"])
    lines.extend("- " + note for note in proposal.safety_notes)
    if proposal.message:
        lines.extend(["", "Message:", proposal.message])
    return "\n".join(lines).rstrip() + "\n"


__all__ = [
    "PROPOSAL_STATUS",
    "ReadmeManifestFileProposal",
    "ReadmeManifestProposal",
    "build_readme_manifest_proposal",
    "render_readme_manifest_proposal",
]
