from __future__ import annotations

import ast
import importlib.util
import io
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
WRITER = ROOT / "engel_memory_promotion_writer.py"
VERIFIER = ROOT / "tools" / "verify_engel_memory_promotion_writer.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_MEMORY_PROMOTION_WRITER_V1.md"
PROPOSAL_DIR = ROOT / "reports" / "memory_candidates"
RECEIPT_DIR = ROOT / "reports" / "memory_promotion_receipts"

REQUIRED_STATUSES = [
    "MEMORY_PROMOTION_WRITER",
    "HUMAN_APPROVAL_REQUIRED",
    "APPROVAL_TOKEN_REQUIRED",
    "SOURCE_CHAIN_REQUIRED",
    "PROMPT_INJECTION_REVIEW_REQUIRED",
    "AUTHORITY_REVIEW_REQUIRED",
    "RECEIPT_REQUIRED",
    "BOUNDED_MEMORY_WRITE_ONLY",
    "NO_SOURCE_MUTATION",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_MODEL_TRAINING",
    "NO_RUNTIME_TRIGGER",
    "NO_BACKGROUND_WORKER",
]

RECEIPT_FIELDS = [
    "memory_promotion_receipt_id",
    "memory_candidate_proposal_id",
    "source_research_note_id",
    "source_lesson_candidate_id",
    "source_chain",
    "approved_by",
    "approval_token",
    "promotion_decision",
    "prompt_injection_review_result",
    "authority_review_result",
    "uncertainty_notes",
    "reason_to_remember",
    "core_continuity_linkage",
    "trusted_memory_target",
    "receipt_created_at",
    "rollback_note",
    "human_intervention_required",
    "no_automatic_memory_promotion",
    "no_source_mutation",
    "no_provider_network_browser",
    "no_model_training",
    "no_runtime_trigger",
]


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read_writer() -> str:
    return WRITER.read_text(encoding="utf-8", errors="replace")


def load_writer():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("engel_memory_promotion_writer", WRITER)
    require(spec is not None and spec.loader is not None, "could not load memory promotion writer module spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_memory_promotion_writer"] = module
    spec.loader.exec_module(module)
    return module


def check_files_exist() -> None:
    for path in [WRITER, VERIFIER, REPORT]:
        require(path.exists() and path.is_file(), "required file missing: " + str(path))
    require(PROPOSAL_DIR.exists() and PROPOSAL_DIR.is_dir(), "proposal folder missing: reports\\memory_candidates")
    require(RECEIPT_DIR.exists() and RECEIPT_DIR.is_dir(), "receipt folder missing: reports\\memory_promotion_receipts")
    require((RECEIPT_DIR / ".gitkeep").exists(), "receipt folder placeholder missing")


def check_required_text() -> None:
    text = read_writer() + "\n" + REPORT.read_text(encoding="utf-8", errors="replace")
    for needle in REQUIRED_STATUSES:
        require(needle in text, "writer missing status: " + needle)
    for needle in [
        "APPROVE_PROMOTE_MEMORY_CANDIDATE",
        "--proposal",
        "--approve-token",
        "--dry-run",
        "--write",
        "--password-prompt",
        "engel_global_password_gate",
        "promote_memory_candidate",
        "Protected action requires --password-prompt.",
        "reports\\memory_candidates",
        "reports\\memory_promotion_receipts",
        "APPROVED_TRUSTED_MEMORY_TARGET_UNCLEAR",
        "TRUSTED_MEMORY_TARGET_IMPLEMENTED = False",
        "STOPPED_UNCLEAR_APPROVED_TRUSTED_MEMORY_LOCATION",
        "No trusted memory is written",
        "Exact approval token required",
        "no automatic promotion",
        "no source mutation",
        "no provider/network/browser",
        "no model training",
        "no runtime trigger",
    ]:
        require(needle in text, "writer missing boundary or CLI text: " + needle)
    for field in RECEIPT_FIELDS:
        require(field in text, "writer missing receipt field: " + field)


def check_forbidden_active_behavior() -> None:
    tree = ast.parse(read_writer())
    forbidden_imports = {
        "requests",
        "urllib",
        "socket",
        "webbrowser",
        "openai",
        "subprocess",
        "glob",
        "shutil",
        "threading",
        "multiprocessing",
    }
    forbidden_attributes = {"walk", "rglob", "glob", "unlink", "remove", "rename"}
    forbidden_names = {"exec", "eval", "__import__"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_name = alias.name.split(".")[0]
                require(root_name not in forbidden_imports, "writer imports forbidden module: " + alias.name)
        if isinstance(node, ast.ImportFrom) and node.module:
            root_name = node.module.split(".")[0]
            require(root_name not in forbidden_imports, "writer imports forbidden module: " + node.module)
        if isinstance(node, ast.While):
            raise CheckFailure("writer contains while loop")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            attr = node.func.attr
            if attr == "write_text":
                value = node.func.value
                require(isinstance(value, ast.Name) and value.id == "receipt_path", "writer can write only stopped receipts")
                continue
            if attr == "mkdir":
                value = node.func.value
                require(isinstance(value, ast.Name) and value.id == "RECEIPT_DIR", "writer can create only receipt folder")
                continue
            require(attr not in forbidden_attributes, "writer uses forbidden call: " + attr)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            require(node.func.id not in forbidden_names, "writer uses forbidden call: " + node.func.id)
    require("write_trusted_memory" not in read_writer(), "writer must not contain trusted memory write implementation")
    require("TRUSTED_MEMORY_TARGET_IMPLEMENTED = True" not in read_writer(), "trusted memory target must remain unimplemented")


def check_runtime_smoke() -> None:
    module = load_writer()
    require(module.TRUSTED_MEMORY_TARGET_IMPLEMENTED is False, "trusted memory target unexpectedly implemented")
    require(module.TRUSTED_MEMORY_TARGET_STATUS == "APPROVED_TRUSTED_MEMORY_TARGET_UNCLEAR", "target status mismatch")

    out = io.StringIO()
    err = io.StringIO()
    require(module.main([], stdout=out, stderr=err) == 0, "usage mode failed")
    usage = out.getvalue()
    require("MEMORY_PROMOTION_WRITER" in usage, "usage missing writer status")
    require("APPROVE_PROMOTE_MEMORY_CANDIDATE" in usage, "usage missing approval token")

    out = io.StringIO()
    err = io.StringIO()
    require(module.main(["--proposal", "missing.md", "--approve-token", "WRONG", "--write"], stdout=out, stderr=err) == 2, "wrong token was not refused")
    require("Exact approval token required" in err.getvalue(), "wrong token refusal missing exact-token message")

    out = io.StringIO()
    err = io.StringIO()
    require(
        module.main(["--proposal", "missing.md", "--approve-token", module.APPROVAL_TOKEN, "--write"], stdout=out, stderr=err) == 2,
        "write without password prompt was not refused",
    )
    require("Protected action requires --password-prompt." in err.getvalue(), "missing password prompt refusal missing")

    for unsafe in [
        "https://example.com/proposal.md",
        "..\\outside.md",
        "memory\\proposal.md",
        "proposal*.md",
        "G:\\ENGEL_APP_MEMORY\\proposal.md",
        "E:\\ENGEL_APP_MEMORY\\proposal.md",
    ]:
        try:
            module.resolve_proposal_path(unsafe)
        except module.MemoryPromotionWriterError:
            continue
        raise CheckFailure("writer accepted unsafe proposal name: " + unsafe)


def main() -> int:
    try:
        check_files_exist()
        check_required_text()
        check_forbidden_active_behavior()
        check_runtime_smoke()
    except CheckFailure as exc:
        print("[FAIL]", exc)
        return 1
    print("[PASS] Engel memory promotion writer verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
