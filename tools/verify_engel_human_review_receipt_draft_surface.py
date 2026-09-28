#!/usr/bin/env python3
from __future__ import annotations

import ast
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SURFACE = ROOT / "engel_human_review_receipt_draft_surface.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_HUMAN_REVIEW_RECEIPT_DRAFT_SURFACE_V1.md"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import engel_human_review_receipt_draft_surface as surface  # noqa: E402


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def sample_receipt_draft() -> dict:
    return {
        "material_id": "SAMPLE_RECEIPT_DRAFT_MATERIAL",
        "title": "Sample receipt draft material",
        "author_or_origin": "sample human source note",
        "source_type": "manual_review_candidate",
        "source_notes": "Draft-only source notes.",
        "original_location": "REFERENCE_ONLY_ORIGINAL_LOCATION",
        "intended_reference_location": "REFERENCE_ONLY_APPROVED_LIBRARY_LOCATION",
        "category": "math",
        "subcategory": "sample",
        "version_or_date": "2099-01-01",
        "file_format": "metadata_only",
        "estimated_scope": "short",
        "reviewer_name_or_id": "sample_reviewer",
        "review_date": "2099-01-02",
        "review_context": "draft-only verifier smoke",
        "review_depth": "metadata_only",
        "reviewer_confidence": "medium",
        "decision": "hold_for_later",
        "reason_for_decision": "Verifier sample remains draft-only.",
        "not_trusted_memory_acknowledged": True,
        "no_auto_index_acknowledged": True,
        "no_execution_acknowledged": True,
        "no_training_acknowledged": True,
        "no_runtime_loading_acknowledged": True,
        "no_network_or_provider_action_acknowledged": True,
        "no_startup_or_background_action_acknowledged": True,
        "prompt_injection_risk_observed": False,
        "hostile_instruction_risk": False,
        "hidden_or_embedded_instruction_risk": False,
        "malicious_code_or_command_risk": False,
        "unsafe_external_link_or_download_risk": False,
        "citation_or_source_spoofing_risk": False,
        "poisoned_example_or_bad_training_data_risk": False,
        "risk_notes": "No real material reviewed in verifier smoke.",
        "may_not_write_trusted_memory": True,
        "requires_separate_memory_candidate_proposal": True,
        "requires_separate_human_approval_for_memory": True,
        "math_claims_need_verification": True,
        "code_examples_not_auto_executable": True,
        "commands_not_auto_runnable": True,
        "package_install_not_allowed": True,
        "final_decision": "hold_for_later",
        "reviewer_signature_or_marker": "sample_marker",
        "timestamp": "2099-01-02T00:00:00Z",
        "next_manual_action": "Human reviewer decides the next manual step.",
        "no_automation_confirmed": True,
    }


def check_required_files() -> tuple[str, str]:
    require(SURFACE.exists(), "missing human review receipt draft surface")
    require(REPORT.exists(), "missing human review receipt draft surface report")
    return read(SURFACE), read(REPORT)


def check_required_text(combined: str) -> None:
    for status in [
        "RECEIPT_DRAFT_ONLY",
        "HUMAN_GUIDED",
        "NO_REAL_RECEIPTS",
        "NO_APPROVAL_ACTION",
        "NOT_TRUSTED_MEMORY",
        "NO_LEARNING_TRIGGER",
        "NO_RUNTIME_TRIGGER",
    ]:
        require(status in combined, "missing receipt draft status: " + status)

    for label in [
        "RECEIPT_DRAFT_ONLY",
        "NOT_REAL_RECEIPT",
        "NOT_APPROVAL",
        "NOT_TRUSTED_MEMORY",
        "NO_AUTOMATION_TRIGGERED",
    ]:
        require(label in combined, "missing receipt draft label: " + label)

    for section in [
        "Material Identity",
        "Human Reviewer",
        "Review Decision",
        "Safety Boundary Acknowledgments",
        "Prompt Injection / Content Risk Review",
        "Research Use Boundary",
        "Engel Memory Boundary",
        "Math / Code Specific Review",
        "Future Queen / Colony Use Notes",
        "Final Human Signoff",
    ]:
        require(section in combined, "missing receipt template section: " + section)

    for phrase in [
        "receipt draft only",
        "not a real receipt",
        "not approval",
        "not trusted memory",
        "no receipt writer",
        "no trusted-memory write",
        "no material operations",
        "draft-only receipt preview",
        "safety acknowledgments",
        "prompt-injection risk prompts",
        "memory boundary prompts",
        "math/code-specific review prompts",
    ]:
        require(phrase in combined.lower(), "missing receipt draft boundary wording: " + phrase)


def check_ast_safety(source: str) -> None:
    tree = ast.parse(source)
    forbidden_imports = {
        "os",
        "pathlib",
        "shutil",
        "subprocess",
        "requests",
        "urllib",
        "socket",
        "glob",
    }
    forbidden_calls = {
        "open",
        "read_text",
        "write",
        "write_text",
        "writelines",
        "mkdir",
        "unlink",
        "rename",
        "replace",
        "rmdir",
        "copy",
        "copytree",
        "move",
        "iterdir",
        "rglob",
        "glob",
        "walk",
        "run",
        "Popen",
        "system",
        "startfile",
        "exec",
        "eval",
    }
    forbidden_function_fragments = [
        "write",
        "save",
        "real_receipt",
        "approve",
        "import_material",
        "trusted_memory",
        "scan_material",
        "index_material",
    ]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                require(root not in forbidden_imports, "forbidden import in receipt draft surface: " + alias.name)
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".", 1)[0]
            require(root not in forbidden_imports, "forbidden import-from in receipt draft surface: " + str(node.module))
        elif isinstance(node, ast.Call):
            name = ""
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            require(name not in forbidden_calls, "forbidden active call in receipt draft surface: " + name)
        elif isinstance(node, ast.FunctionDef):
            lowered = node.name.lower()
            for fragment in forbidden_function_fragments:
                require(fragment not in lowered, "forbidden writer/action function name: " + node.name)


def check_surface_constants() -> None:
    for status in [
        "RECEIPT_DRAFT_ONLY",
        "HUMAN_GUIDED",
        "NO_REAL_RECEIPTS",
        "NO_APPROVAL_ACTION",
        "NOT_TRUSTED_MEMORY",
        "NO_LEARNING_TRIGGER",
        "NO_RUNTIME_TRIGGER",
    ]:
        require(status in surface.RECEIPT_DRAFT_STATUS, "surface status constant missing: " + status)

    for label in [
        "RECEIPT_DRAFT_ONLY",
        "NOT_REAL_RECEIPT",
        "NOT_APPROVAL",
        "NOT_TRUSTED_MEMORY",
        "NO_AUTOMATION_TRIGGERED",
    ]:
        require(label in surface.DRAFT_LABELS, "surface label constant missing: " + label)

    for key in [
        "receipt_draft_only",
        "human_guided",
        "no_real_receipts",
        "no_receipt_writer",
        "no_approval_action",
        "not_trusted_memory",
        "no_learning_trigger",
        "no_runtime_trigger",
        "no_material_import",
        "no_material_copy",
        "no_material_move",
        "no_material_scan",
        "no_indexing",
        "no_embedding",
        "no_execution",
        "no_trusted_memory_write",
    ]:
        require(surface.DRAFT_BOUNDARY.get(key) is True, "surface boundary flag missing: " + key)


def check_preview_smoke() -> None:
    manifest = surface.build_surface_manifest()
    require(manifest["surface_name"] == "Engel Human Review Receipt Draft Surface V1", "manifest surface name mismatch")
    require("Prompt Injection / Content Risk Review" in manifest["receipt_template_sections"], "manifest missing prompt injection section")
    require("not_trusted_memory_acknowledged" in manifest["safety_acknowledgments"], "manifest missing safety acknowledgment")
    require("requires_separate_memory_candidate_proposal" in manifest["memory_boundary_prompts"], "manifest missing memory boundary prompt")
    require("math_claims_need_verification" in manifest["math_code_specific_review_prompts"], "manifest missing math/code prompt")

    empty_preview = surface.build_receipt_draft_preview()
    require(empty_preview["outcome"] == "receipt_draft_incomplete", "empty preview must be incomplete")
    require("material_id" in empty_preview["missing_fields"], "empty preview must identify missing material_id")

    ready_preview = surface.build_receipt_draft_preview(sample_receipt_draft())
    require(ready_preview["outcome"] == "receipt_draft_ready", "sample preview should be draft-ready")
    require(ready_preview["category_allowed"] is True, "sample category should be allowed")
    require(ready_preview["decision_allowed"] is True, "sample decision should be allowed")
    require(ready_preview["draft_boundary"]["no_real_receipts"] is True, "preview must preserve no-real-receipts boundary")
    require(ready_preview["draft_receipt"]["engel_memory_boundary"]["may_not_write_trusted_memory"] is True, "preview must preserve memory boundary")
    require(ready_preview["draft_receipt"]["math_code_specific_review"]["code_examples_not_auto_executable"] is True, "preview must preserve code boundary")

    rendered = surface.render_surface_text().lower() + surface.render_receipt_draft_preview(sample_receipt_draft()).lower()
    for phrase in [
        "receipt draft only",
        "not a real receipt",
        "not approval",
        "not trusted memory",
        "no receipt writer",
        "no automation triggered",
    ]:
        require(phrase in rendered, "rendered surface missing phrase: " + phrase)


def main() -> int:
    try:
        source, report = check_required_files()
        check_required_text(source + "\n" + report)
        check_ast_safety(source)
        check_surface_constants()
        check_preview_smoke()
    except (CheckFailure, SyntaxError) as exc:
        print("FAIL: Engel Human Review Receipt Draft Surface V1 verifier")
        print("- " + str(exc))
        return 1

    print("PASS: Engel Human Review Receipt Draft Surface V1 verifier")
    print("- draft surface exists and exposes required receipt template sections")
    print("- receipt draft labels and no-real-receipt boundaries are present")
    print("- preview smoke remains in-memory and draft-only")
    print("- no receipt writer, approval action, material operation, or trusted-memory behavior was added")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
