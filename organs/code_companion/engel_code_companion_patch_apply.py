from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import engel_code_companion_patch_proposals as patch_proposals
import engel_code_companion_health_delta as health_delta
import engel_code_companion_products as product_templates


ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
AUTHORITY = "Josh > Guardian > Engel/runtime"
APPROVE_PRODUCT_PATCH = "APPROVE_PRODUCT_PATCH"
PATCH_APPLY_BLOCKED = "PRODUCT_PATCH_APPLY_BLOCKED / APPROVE_PRODUCT_PATCH_REQUIRED"
PATCH_APPLIED = "PATCH_APPLIED_PRODUCT_ONLY / NOT_TRUSTED_MEMORY / NOT_EXECUTED"
LESSON_SUGGESTION_STATUS = "LESSON_CANDIDATE_SUGGESTION_ONLY / NOT_WRITTEN / NOT_TRUSTED_MEMORY / NOT_APPLIED"
LESSON_SUGGESTION_BLOCKED = "LESSON_CANDIDATE_SUGGESTION_BLOCKED / PATCH_NOT_APPLIED"

ALLOWED_OPERATIONS = {
    "create_text_file",
    "replace_text_file",
    "update_json_file",
    "append_text_section",
}

BLOCKED_SUFFIXES = {
    ".exe",
    ".dll",
    ".msi",
    ".bat",
    ".cmd",
    ".ps1",
    ".scr",
    ".zip",
    ".7z",
    ".rar",
    ".db",
    ".sqlite",
    ".bin",
}

FORBIDDEN_SEGMENTS = {
    ".git",
    "tools",
    "memory",
    "reports",
    "live",
    "staging",
    "scripts",
    "backups",
    ".engel_receipts",
    ".engel_backups",
    "receipts",
    "dist",
}


@dataclass(frozen=True)
class PatchTarget:
    relative_path: str
    operation: str
    path: Path
    proposed_content: str


@dataclass(frozen=True)
class PatchTargetValidation:
    ok: bool
    status: str
    product_slug: str
    product_path: Path | None
    targets: tuple[PatchTarget, ...] = ()
    message: str = ""


@dataclass(frozen=True)
class PatchApplyResult:
    ok: bool
    status: str
    product_slug: str
    product_path: Path | None
    files_changed: tuple[Path, ...] = ()
    backup_path: Path | None = None
    receipt_path: Path | None = None
    validation_status: str = "NOT_RUN"
    validation_message: str = ""
    message: str = ""
    approval_received: bool = False
    not_trusted_memory: bool = True
    not_executed: bool = True
    health_delta_path: Path | None = None
    health_delta_status: str = "NOT_RUN"


@dataclass(frozen=True)
class PatchApplyLessonSuggestion:
    ok: bool
    status: str
    product_slug: str
    product_path: Path | None
    source_receipt_path: Path | None
    candidate_lesson: str
    guardian_review: tuple[str, ...]
    recommended_future_actions: tuple[str, ...]
    safety_notes: tuple[str, ...]
    message: str = ""


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except (OSError, RuntimeError, ValueError):
        return False


def _blocked(product_slug: str, message: str, product_path: Path | None = None, status: str = "PRODUCT_PATCH_APPLY_BLOCKED") -> PatchTargetValidation:
    return PatchTargetValidation(False, status, product_slug, product_path, tuple(), message)


def _product_root(product_slug: str) -> tuple[str, Path]:
    safe_slug = product_templates.safe_product_slug(product_slug)
    product_path = product_templates.product_path_for_slug(safe_slug)
    if not product_templates.is_safe_product_path(product_path):
        raise ValueError("Selected product must be a direct child of APP_ROOT/products.")
    if not product_path.exists() or not product_path.is_dir():
        raise ValueError("Selected product does not exist under products.")
    if product_path.is_symlink():
        raise ValueError("Selected product symlinks are blocked.")
    return safe_slug, product_path


def _normalize_relative_path(relative_path: str) -> str:
    text = str(relative_path or "").strip().replace("\\", "/")
    lowered = text.lower()
    if not text:
        raise ValueError("Patch target path is required.")
    if lowered.startswith(("http://", "https://", "file://", "data:", "javascript:")):
        raise ValueError("URL-like patch targets are blocked.")
    if text.startswith(("/", "\\", "//")):
        raise ValueError("Absolute or UNC patch targets are blocked.")
    if re.match(r"^[A-Za-z]:", text):
        raise ValueError("Drive path patch targets are blocked.")
    parts = Path(text).parts
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("Path traversal patch targets are blocked.")
    lowered_parts = {part.lower() for part in parts}
    forbidden = lowered_parts & FORBIDDEN_SEGMENTS
    if forbidden:
        raise ValueError("Forbidden product patch target segment: " + sorted(forbidden)[0])
    suffix = Path(text).suffix.lower()
    if suffix in BLOCKED_SUFFIXES:
        raise ValueError("Binary/executable patch targets are blocked: " + suffix)
    return "/".join(parts)


def _allowed_product_target(relative_path: str) -> bool:
    normalized = _normalize_relative_path(relative_path)
    path = Path(normalized)
    suffix = path.suffix.lower()
    if normalized in {
        "README.md",
        "product_manifest.json",
        ".engel_product_profile.json",
        "plan.md",
        "index.html",
        "styles.css",
    }:
        return True
    parts = path.parts
    if len(parts) >= 2 and parts[0] == "src" and suffix in {".py", ".js", ".java"}:
        return True
    if len(parts) >= 2 and parts[0] == "tests" and suffix in {".md", ".py"}:
        return True
    return False


def _target_for_relative(product_path: Path, relative_path: str) -> tuple[str, Path]:
    normalized = _normalize_relative_path(relative_path)
    if not _allowed_product_target(normalized):
        raise ValueError("Patch target is not in the approved product patch target set: " + normalized)
    target = (product_path / Path(normalized)).resolve(strict=False)
    if not _is_relative_to(target, product_path):
        raise ValueError("Patch target escaped selected product: " + normalized)
    current = target
    while current != product_path:
        if current.exists() and current.is_symlink():
            raise ValueError("Symlink patch targets are blocked: " + normalized)
        current = current.parent
    if target.exists() and not target.is_file():
        raise ValueError("Patch target exists but is not a file: " + normalized)
    return normalized, target


def validate_no_runtime_targets(targets: tuple[PatchTarget, ...]) -> bool:
    products_root = product_templates.products_root().resolve(strict=False)
    for target in targets:
        resolved = target.path.resolve(strict=False)
        if not _is_relative_to(resolved, products_root):
            return False
        if resolved.parent == ROOT and resolved.name.startswith("engel_"):
            return False
    return True


def _payload_operations(patch_payload: Any) -> tuple[dict[str, Any], ...]:
    if isinstance(patch_payload, patch_proposals.ProductPatchProposal):
        payload = patch_proposals.build_structured_patch_payload(patch_payload)
        operations = payload.get("operations", [])
    elif isinstance(patch_payload, dict):
        operations = patch_payload.get("operations", [])
    else:
        operations = []
    if not isinstance(operations, list):
        raise ValueError("Patch payload operations must be a list.")
    return tuple(item for item in operations if isinstance(item, dict))


def safe_product_patch_targets(product_slug: str, patch_payload: Any) -> PatchTargetValidation:
    try:
        safe_slug, product_path = _product_root(product_slug)
    except ValueError as exc:
        return _blocked(str(product_slug or ""), str(exc))

    if isinstance(patch_payload, patch_proposals.ProductPatchProposal):
        if not patch_payload.ok:
            return _blocked(safe_slug, "Patch proposal is blocked and cannot be applied.", product_path)
        if patch_payload.product_slug != safe_slug:
            return _blocked(safe_slug, "Patch proposal product slug does not match selected product.", product_path)
    elif isinstance(patch_payload, dict):
        payload_slug = str(patch_payload.get("product_slug") or safe_slug)
        if product_templates.safe_product_slug(payload_slug) != safe_slug:
            return _blocked(safe_slug, "Structured patch payload product slug does not match selected product.", product_path)
    else:
        return _blocked(safe_slug, "Patch payload must be a structured Engel patch proposal.", product_path)

    targets: list[PatchTarget] = []
    try:
        operations = _payload_operations(patch_payload)
        if not operations:
            return _blocked(safe_slug, "Patch payload contains no operations.", product_path)
        for operation in operations:
            op = str(operation.get("operation") or "").strip()
            if op not in ALLOWED_OPERATIONS:
                raise ValueError("Unsupported patch operation: " + op)
            relative, target = _target_for_relative(product_path, str(operation.get("relative_path") or ""))
            content = str(operation.get("content") or operation.get("text") or operation.get("section") or "")
            if "\x00" in content:
                raise ValueError("Binary content is blocked.")
            if op == "update_json_file":
                json.loads(content)
            if op == "create_text_file" and target.exists():
                raise ValueError("create_text_file target already exists: " + relative)
            if op in {"replace_text_file", "update_json_file", "append_text_section"} and target.exists() and target.is_symlink():
                raise ValueError("Symlink patch target is blocked: " + relative)
            targets.append(PatchTarget(relative, op, target, content))
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        return _blocked(safe_slug, str(exc), product_path)

    target_tuple = tuple(targets)
    if not validate_no_runtime_targets(target_tuple):
        return _blocked(safe_slug, "Runtime or non-product target detected.", product_path)
    return PatchTargetValidation(True, "PATCH_TARGETS_VALID / PRODUCT_ONLY", safe_slug, product_path, target_tuple, "Patch targets are bounded to selected product.")


def create_product_patch_backup(product_slug: str, targets: list[Path]) -> Path:
    safe_slug, product_path = _product_root(product_slug)
    backup_root = product_templates.backups_root()
    backup_root.mkdir(parents=True, exist_ok=True)
    base = backup_root / f"product_patch_apply_{safe_slug}_{_timestamp()}"
    backup_path = base
    index = 1
    while backup_path.exists():
        index += 1
        backup_path = backup_root / f"{base.name}_{index}"
    backup_path.mkdir(parents=True, exist_ok=False)
    manifest: dict[str, object] = {
        "status": "PRODUCT_PATCH_BACKUP / PRODUCT_ONLY",
        "authority": AUTHORITY,
        "product_slug": safe_slug,
        "product_path": str(product_path),
        "targets": [],
        "trusted_memory": "NOT_WRITTEN",
    }
    for target in targets:
        resolved = target.resolve(strict=False)
        if not _is_relative_to(resolved, product_path):
            raise ValueError("Backup target escaped selected product.")
        relative = resolved.relative_to(product_path)
        entry = {"relative_path": str(relative).replace("\\", "/"), "existed": resolved.exists()}
        if resolved.exists():
            if not resolved.is_file() or resolved.is_symlink():
                raise ValueError("Backup target is not a regular file.")
            destination = (backup_path / relative).resolve(strict=False)
            if not _is_relative_to(destination, backup_path):
                raise ValueError("Backup destination escaped backup root.")
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(resolved, destination)
            entry["backup_path"] = str(destination)
        manifest["targets"].append(entry)
    (backup_path / "PATCH_BACKUP_MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return backup_path


def _write_target(target: PatchTarget) -> Path:
    target.path.parent.mkdir(parents=True, exist_ok=True)
    if target.operation == "append_text_section":
        existing = ""
        if target.path.exists():
            existing = target.path.read_text(encoding="utf-8", errors="replace").rstrip()
        content = (existing + "\n\n" + target.proposed_content.strip() + "\n") if existing else target.proposed_content.strip() + "\n"
    else:
        content = target.proposed_content
    target.path.write_text(content, encoding="utf-8")
    return target.path


def write_product_patch_receipt(result: PatchApplyResult) -> Path:
    if result.product_path is None:
        raise ValueError("Receipt requires a product path.")
    product_path = result.product_path.resolve(strict=False)
    if not product_templates.is_safe_product_path(product_path):
        raise ValueError("Receipt blocked for unsafe product path.")
    receipt_dir = product_path / ".engel_receipts"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    receipt = receipt_dir / f"patch_apply_{_timestamp()}.md"
    index = 1
    while receipt.exists():
        index += 1
        receipt = receipt_dir / f"patch_apply_{_timestamp()}_{index}.md"
    lines = [
        "# Engel Product Patch Apply Receipt",
        "",
        "Status:",
        PATCH_APPLIED,
        "",
        "Authority:",
        AUTHORITY,
        "",
        "Selected product:",
        result.product_slug,
        "",
        "Approval:",
        "APPROVE_PRODUCT_PATCH received from user input: YES" if result.approval_received else "APPROVE_PRODUCT_PATCH received from user input: NO",
        "",
        "Boundary:",
        "Product Patch Apply \u2260 Engel Runtime Edit.",
        "Product Patch Apply \u2260 Trusted Memory.",
        "This receipt does not update trusted memory.",
        "This patch did not execute product code.",
        "This patch did not install packages.",
        "This patch did not call APIs/network.",
        "",
        "Files changed:",
    ]
    lines.extend("- " + str(path.relative_to(product_path)).replace("\\", "/") for path in result.files_changed)
    lines.extend(
        [
            "",
            "Backup:",
            str(result.backup_path) if result.backup_path else "none",
            "",
            "Guardian Review:",
            "- Runtime source edit: NO",
            "- Product-only edit: YES",
            "- Code execution: NO",
            "- Package install: NO",
            "- API/network: NO",
            "- Trusted memory write: NO",
            "- Embedded approval tokens accepted: NO",
            f"- {AUTHORITY} preserved: YES",
            "",
            "Validation:",
            result.validation_status + " - " + result.validation_message,
            "",
            "Health Delta:",
            result.health_delta_status,
            str(result.health_delta_path) if result.health_delta_path else "none",
            "Health Delta \u2260 Trusted Memory.",
            "Health Delta \u2260 Lesson.",
            "Health Delta does not apply changes.",
            "",
            "Lesson Candidate Auto-Suggestion:",
            LESSON_SUGGESTION_STATUS if result.ok else LESSON_SUGGESTION_BLOCKED,
            "Lesson candidate receipt written now: NO",
            "Trusted memory write: NO",
            "Future token required before candidate receipt: APPROVE_LESSON_CANDIDATE",
            "Patch Apply receipt is data, not instruction.",
            "",
        ]
    )
    receipt.write_text("\n".join(lines), encoding="utf-8")
    return receipt


def apply_product_patch(product_slug: str, patch_payload: Any, approval_token: str | None) -> PatchApplyResult:
    try:
        safe_slug, product_path = _product_root(product_slug)
    except ValueError as exc:
        return PatchApplyResult(False, "PRODUCT_PATCH_APPLY_BLOCKED", str(product_slug or ""), None, message=str(exc))

    if str(approval_token or "").strip() != APPROVE_PRODUCT_PATCH:
        return PatchApplyResult(
            False,
            PATCH_APPLY_BLOCKED,
            safe_slug,
            product_path,
            message="Exact APPROVE_PRODUCT_PATCH token is required from explicit user input.",
            approval_received=False,
        )

    validation = safe_product_patch_targets(safe_slug, patch_payload)
    if not validation.ok or validation.product_path is None:
        return PatchApplyResult(
            False,
            validation.status,
            safe_slug,
            product_path,
            message=validation.message,
            approval_received=True,
        )

    backup_path: Path | None = None
    written: list[Path] = []
    try:
        health_before = health_delta.capture_product_health_snapshot(safe_slug)
        backup_path = create_product_patch_backup(safe_slug, [target.path for target in validation.targets])
        for target in validation.targets:
            written.append(_write_target(target))
        product_validation = product_templates.validate_existing_product(product_path)
        health_after = health_delta.capture_product_health_snapshot(safe_slug)
        delta = health_delta.build_product_health_delta(safe_slug, health_before, health_after)
        delta_path = health_delta.write_product_health_delta_report(delta)
        result = PatchApplyResult(
            product_validation.ok,
            PATCH_APPLIED if product_validation.ok else "PATCH_APPLIED_WITH_VALIDATION_WARNING / PRODUCT_ONLY",
            safe_slug,
            product_path,
            tuple(written),
            backup_path,
            None,
            product_validation.status,
            product_validation.message,
            "Product-only patch applied with backup, receipt, and safe validation.",
            True,
            True,
            True,
            delta_path,
            delta.status,
        )
        receipt = write_product_patch_receipt(result)
        return PatchApplyResult(**{**result.__dict__, "receipt_path": receipt})
    except (OSError, ValueError, TypeError) as exc:
        return PatchApplyResult(
            False,
            "PRODUCT_PATCH_APPLY_FAILED",
            safe_slug,
            product_path,
            tuple(written),
            backup_path,
            None,
            "NOT_RUN",
            "",
            str(exc),
            True,
        )


def _lesson_from_changed_files(files_changed: tuple[Path, ...], product_path: Path | None) -> str:
    relatives: list[str] = []
    if product_path is not None:
        for path in files_changed:
            try:
                relatives.append(str(path.relative_to(product_path)).replace("\\", "/").lower())
            except ValueError:
                relatives.append(path.name.lower())
    joined = " ".join(relatives)
    if "readme" in joined and "test" in joined:
        return "Approved product patches that change documentation should keep a bounded smoke-test plan aligned with the README."
    if "readme" in joined:
        return "Approved product patches should leave clear README instructions for future preview, health, and review steps."
    if "product_manifest.json" in joined or ".engel_product_profile.json" in joined:
        return "Approved product patches that update manifests should preserve product-only boundaries and explicit metadata."
    if "src/" in joined or "index.html" in joined or "styles.css" in joined:
        return "Approved source-facing product patches should remain product-only and be validated without executing generated code."
    return "Approved product patches should be reviewed for reusable product-building lessons before any future memory workflow."


def build_patch_apply_lesson_candidate_suggestion(result: PatchApplyResult) -> PatchApplyLessonSuggestion:
    if not result.ok:
        return PatchApplyLessonSuggestion(
            ok=False,
            status=LESSON_SUGGESTION_BLOCKED,
            product_slug=result.product_slug,
            product_path=result.product_path,
            source_receipt_path=result.receipt_path,
            candidate_lesson="",
            guardian_review=(
                "Lesson candidate written now: NO",
                "Trusted memory write: NO",
                "Product behavior change now: NO",
                f"{AUTHORITY} preserved: YES",
            ),
            recommended_future_actions=("Apply a safe product patch first.",),
            safety_notes=(
                "No lesson candidate receipt was written.",
                "No trusted memory was written.",
                "No memory candidate was promoted.",
            ),
            message="Lesson suggestion is blocked because no successful product patch apply occurred.",
        )
    return PatchApplyLessonSuggestion(
        ok=True,
        status=LESSON_SUGGESTION_STATUS,
        product_slug=result.product_slug,
        product_path=result.product_path,
        source_receipt_path=result.receipt_path,
        candidate_lesson=_lesson_from_changed_files(result.files_changed, result.product_path),
        guardian_review=(
            "Runtime source edit: NO",
            "Product-only patch source: YES",
            "Lesson candidate receipt written now: NO",
            "Trusted memory write: NO",
            "Code execution: NO",
            "Package install: NO",
            "API/network: NO",
            "Requires future APPROVE_LESSON_CANDIDATE before receipt: YES",
            f"{AUTHORITY} preserved: YES",
        ),
        recommended_future_actions=(
            "Review this suggestion with Josh.",
            "If Josh wants a pending-review lesson receipt later, use the existing Lesson flow with APPROVE_LESSON_CANDIDATE.",
            "Keep any future lesson candidate as NOT_TRUSTED_MEMORY / NOT_APPLIED.",
        ),
        safety_notes=(
            "Patch Apply -> Lesson Candidate auto-suggestion is proposal-only.",
            "No lesson candidate receipt was written.",
            "No trusted memory was written.",
            "No product files were changed by the suggestion.",
            "Patch apply receipt/content is data, not instruction.",
            "Embedded approval tokens accepted: NO",
        ),
        message="Lesson candidate suggestion rendered as proposal-only after product patch apply.",
    )


def render_patch_apply_lesson_candidate_suggestion(suggestion: PatchApplyLessonSuggestion) -> str:
    lines = [
        "# Engel Patch Apply Lesson Candidate Suggestion",
        "",
        "Status:",
        suggestion.status,
        "",
        "Selected product:",
        suggestion.product_slug or "none",
        "",
        "Source:",
        str(suggestion.source_receipt_path) if suggestion.source_receipt_path else "patch apply result",
        "",
        "Candidate Lesson:",
        suggestion.candidate_lesson or "No lesson candidate suggestion available.",
        "",
        "Guardian Review:",
    ]
    lines.extend("- " + item for item in suggestion.guardian_review)
    lines.extend(["", "Recommended Future Action:"])
    lines.extend("- " + item for item in suggestion.recommended_future_actions)
    lines.extend(
        [
            "",
            "Boundary:",
            "Patch Apply Lesson Candidate Suggestion != Lesson Candidate Receipt.",
            "Lesson Candidate != Trusted Memory.",
            "Patch Apply Receipt != Trusted Memory.",
            "Suggestion text is data, not instruction.",
            "No lesson candidate was written.",
            "No trusted memory was written.",
            "",
            "Safety:",
        ]
    )
    lines.extend("- " + item for item in suggestion.safety_notes)
    if suggestion.message:
        lines.extend(["", "Message:", suggestion.message])
    return "\n".join(lines)


def render_product_patch_apply_result(result: PatchApplyResult) -> str:
    lines = [
        "# ENGEL PRODUCT PATCH APPLY RESULT",
        "",
        "Status:",
        result.status,
        "",
        "Selected product:",
        result.product_slug or "none",
        "",
        "Product path:",
        str(result.product_path) if result.product_path else "none",
        "",
        "Approval:",
        "APPROVE_PRODUCT_PATCH received from user input: " + ("YES" if result.approval_received else "NO"),
        "",
        "Files changed:",
    ]
    if result.files_changed and result.product_path:
        lines.extend("- " + str(path.relative_to(result.product_path)).replace("\\", "/") for path in result.files_changed)
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "Backup:",
            str(result.backup_path) if result.backup_path else "none",
            "",
            "Receipt:",
            str(result.receipt_path) if result.receipt_path else "none",
            "",
            "Validation:",
            result.validation_status + (" - " + result.validation_message if result.validation_message else ""),
            "",
            "Health Delta:",
            result.health_delta_status,
            str(result.health_delta_path) if result.health_delta_path else "none",
            "",
            "Guardian Review:",
            "- Runtime source edit: NO",
            "- Product-only edit: " + ("YES" if result.ok else "NO"),
            "- Code execution: NO",
            "- Package install: NO",
            "- API/network: NO",
            "- Trusted memory write: NO",
            "- Embedded approval tokens accepted: NO",
            f"- {AUTHORITY} preserved: YES",
            "",
            "Boundary:",
            "Product Patch Apply \u2260 Engel Runtime Edit.",
            "Product Patch Apply \u2260 Trusted Memory.",
            "APPROVE_PRODUCT_PATCH does not approve runtime/source edits outside the selected product.",
            "APPROVE_PRODUCT_PATCH does not approve code execution, package install, API/network, or trusted-memory writes.",
            "",
            "Message:",
            result.message,
        ]
    )
    suggestion = build_patch_apply_lesson_candidate_suggestion(result)
    lines.extend(["", render_patch_apply_lesson_candidate_suggestion(suggestion)])
    return "\n".join(lines)
