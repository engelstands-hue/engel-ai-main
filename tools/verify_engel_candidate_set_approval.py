from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "engel_candidate_set_approval.py"
RECEIPT = ROOT / "reports" / "candidate_set_approvals" / "ENGEL_CANDIDATE_SET_APPROVAL_186_LESSON_24_MEMORY.json"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_CANDIDATE_SET_APPROVAL_186_LESSON_24_MEMORY.md"
TRUSTED_MEMORY_TARGET = ROOT / "memory" / "ENGEL_TRUSTED_MEMORY_V1.jsonl"

APPROVAL_TOKEN = "APPROVE_EXISTING_CANDIDATE_SET_186_LESSON_24_MEMORY_NO_PROMOTION_NO_WRITE"
EXPECTED_LESSON_COUNT = 186
EXPECTED_MEMORY_COUNT = 24

REQUIRED_STATUS = [
    "CANDIDATE_SET_APPROVAL",
    "HUMAN_APPROVAL_RECORDED",
    "LESSON_CANDIDATES_APPROVED_FOR_LEARNING_REVIEW",
    "MEMORY_CANDIDATES_APPROVED_FOR_FUTURE_PROMOTION",
    "CANDIDATE_APPROVAL_ONLY",
    "NO_MEMORY_PROMOTION",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_PATCH_APPLY",
    "NO_LEARNING_JOB_RUN",
    "NO_MODEL_LOADING",
    "NO_INFERENCE",
    "NO_TRAINING",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_WSL_EXECUTION",
    "NO_HERMES_EXECUTION",
    "NO_ANDROID_CONNECTION",
    "NO_PACKAGE_INSTALL",
    "NO_DOWNLOAD",
    "NO_BACKGROUND_WORKER",
    "NO_STARTUP_AUTORUN",
    "TRUSTED_MEMORY_TARGET_REMAINS_DISABLED",
]

FORBIDDEN_IMPORTS = {
    "requests",
    "urllib",
    "socket",
    "webbrowser",
    "openai",
    "subprocess",
    "threading",
    "multiprocessing",
    "shutil",
    "glob",
    "os",
}

FORBIDDEN_CALLS = {
    "eval",
    "exec",
    "__import__",
    "startfile",
    "Popen",
    "system",
    "rglob",
    "glob",
    "walk",
    "unlink",
    "remove",
    "rename",
    "replace",
}


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def load_module():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("engel_candidate_set_approval", MODULE)
    require(spec is not None and spec.loader is not None, "could not load candidate set approval module")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_candidate_set_approval"] = module
    spec.loader.exec_module(module)
    return module


def check_files() -> None:
    for path in [MODULE, RECEIPT, REPORT]:
        require(path.exists() and path.is_file(), "missing required file: " + str(path.relative_to(ROOT)))
    if TRUSTED_MEMORY_TARGET.exists():
        require(TRUSTED_MEMORY_TARGET.is_file(), "trusted memory target path exists but is not a file")


def check_module_static() -> None:
    source = read(MODULE)
    tree = ast.parse(source)
    for status in REQUIRED_STATUS:
        require(status in source, "module missing required status: " + status)
    for cli in ["--status", "--json", "--write-receipt", "--verify-receipt"]:
        require(cli in source, "module missing CLI option: " + cli)
    for needle in [
        APPROVAL_TOKEN,
        "human_approved_for_learning_review",
        "human_approved_for_future_promotion",
        "trusted_memory_written",
        "memory_promotion_occurred",
        "patch_or_fix_applied",
        "learning_job_run",
        "disabled_until_human_target_approval",
        "candidate approval is not promotion",
    ]:
        require(needle in source, "module missing approval boundary text: " + needle)
    for unsafe in [
        "memory_promotion_occurred\": True",
        "trusted_memory_written\": True",
        "patch_or_fix_applied\": True",
        "learning_job_run\": True",
        "TRUSTED_MEMORY_V1.jsonl').write",
        "TRUSTED_MEMORY_V1.jsonl\").write",
    ]:
        require(unsafe not in source, "module contains unsafe approval behavior: " + unsafe)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                require(alias.name.split(".")[0] not in FORBIDDEN_IMPORTS, "module imports forbidden package: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            require(node.module.split(".")[0] not in FORBIDDEN_IMPORTS, "module imports forbidden package: " + node.module)
        elif isinstance(node, ast.While):
            raise CheckFailure("module contains while loop")
        elif isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
            if name in {"write_text", "mkdir", "replace"}:
                continue
            require(name not in FORBIDDEN_CALLS, "module contains forbidden call: " + name)


def check_receipt() -> None:
    receipt = json.loads(read(RECEIPT))
    require(receipt.get("approval_token") == APPROVAL_TOKEN, "approval token mismatch")
    require(receipt.get("blocked") is False, "approval receipt must not be blocked")
    require(receipt.get("status") == "candidate_set_approved_for_next_stage", "receipt status mismatch")
    require(receipt.get("approved_lesson_candidate_count") == EXPECTED_LESSON_COUNT, "approved lesson count mismatch")
    require(receipt.get("approved_memory_candidate_count") == EXPECTED_MEMORY_COUNT, "approved memory count mismatch")
    require(len(receipt.get("lesson_candidates", [])) == EXPECTED_LESSON_COUNT, "lesson candidate record count mismatch")
    require(len(receipt.get("memory_candidates", [])) == EXPECTED_MEMORY_COUNT, "memory candidate record count mismatch")
    for item in receipt.get("lesson_candidates", []):
        require(item.get("approval_status") == "human_approved_for_learning_review", "lesson approval status mismatch")
        require(item.get("approved_for") == "future_learning_review_use", "lesson approval scope mismatch")
        require(item.get("sha256"), "lesson record missing sha256")
        require(item.get("path"), "lesson record missing path")
        require(item.get("no_execution") is True, "lesson record must block execution")
        require(item.get("no_trusted_memory_write") is True, "lesson record must block trusted memory write")
        require(item.get("no_patch_apply") is True, "lesson record must block patch apply")
    for item in receipt.get("memory_candidates", []):
        require(item.get("approval_status") == "human_approved_for_future_promotion", "memory approval status mismatch")
        require(item.get("approved_for") == "future_promotion_eligibility_only", "memory approval scope mismatch")
        require(item.get("source_hash"), "memory record missing source hash")
        require(item.get("source_path"), "memory record missing source path")
        require(item.get("promotion_status") == "not_promoted", "memory record must not be promoted")
        require(item.get("trusted_memory_written") is False, "memory record must not write trusted memory")
    for key in [
        "trusted_memory_written",
        "memory_promotion_occurred",
        "patch_or_fix_applied",
        "learning_job_run",
        "source_mutation",
        "route_mutation",
        "provider_network_browser",
        "wsl_hermes_android_runtime",
        "model_loading",
        "inference",
        "training",
        "package_install",
        "download",
        "background_worker",
        "startup_autorun",
        "fake_approvals",
        "fake_promoted_memory",
        "fake_candidate_records",
    ]:
        require(receipt.get(key) is False, "receipt safety field must be false: " + key)
    require(receipt.get("trusted_memory_target_status") == "disabled_until_human_target_approval", "target status must remain disabled")
    require(receipt.get("trusted_memory_target_exists") is False, "approval receipt must not claim it created a trusted memory target")


def check_runtime_scan() -> None:
    module = load_module()
    status = module.count_status()
    require(status.get("actual_lesson_candidate_count") == EXPECTED_LESSON_COUNT, "runtime lesson count mismatch")
    require(status.get("actual_memory_candidate_count") == EXPECTED_MEMORY_COUNT, "runtime memory count mismatch")
    require(status.get("counts_match") is True, "runtime counts must match expected approval set")
    result = module.verify_receipt()
    require(result.get("valid") is True, "runtime receipt verification failed: " + "; ".join(result.get("failures", [])))
    rendered = module.render_status()
    for text in [
        "Candidate approval is not promotion.",
        "No trusted memory write, patch apply, or learning job run is performed.",
        APPROVAL_TOKEN,
    ]:
        require(text in rendered, "status missing text: " + text)


def check_report() -> None:
    text = read(REPORT)
    for needle in [
        "Engel Candidate Set Approval",
        APPROVAL_TOKEN,
        "exact lesson candidate count: 186",
        "exact memory candidate count: 24",
        "no memory was promoted",
        "no trusted memory was written",
        "no fixes were applied",
        "no learning jobs were run",
        "Packaging skipped",
    ]:
        require(needle in text, "report missing required text: " + needle)


def main() -> int:
    checks = [
        ("files", check_files),
        ("module_static", check_module_static),
        ("receipt", check_receipt),
        ("runtime_scan", check_runtime_scan),
        ("report", check_report),
    ]
    failures: list[str] = []
    for name, check in checks:
        try:
            check()
        except CheckFailure as exc:
            failures.append(f"{name}: {exc}")
    if failures:
        print("[FAIL] Engel Candidate Set Approval verifier failed.")
        for failure in failures:
            print("- " + failure)
        return 1
    print("[PASS] Engel Candidate Set Approval verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
