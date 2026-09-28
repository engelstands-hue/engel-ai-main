from __future__ import annotations

import ast
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "engel_ai_model_review_approval.py"
VERIFIER = ROOT / "tools" / "verify_engel_ai_model_review_approval.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_AI_MODEL_REVIEW_APPROVAL_V1.md"
APPROVAL_ROOT = ROOT / "reports" / "ai_model_review_approvals"
RECEIPTS = APPROVAL_ROOT / "receipts"
MANIFESTS = APPROVAL_ROOT / "manifests"
EXAMPLES = APPROVAL_ROOT / "examples"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"
READINESS_VERIFIER = ROOT / "tools" / "verify_engel_ai_runtime_readiness.py"
INTAKE_VERIFIER = ROOT / "tools" / "verify_engel_ai_manual_model_file_intake.py"
MODEL_PLAN_VERIFIER = ROOT / "tools" / "verify_engel_model_library_plan.py"

FORBIDDEN_IMPORTS = {
    "requests",
    "urllib",
    "socket",
    "webbrowser",
    "subprocess",
    "threading",
    "multiprocessing",
    "asyncio",
    "http",
    "ftplib",
    "smtplib",
    "openai",
    "anthropic",
}

FORBIDDEN_CALLS = {
    "eval",
    "__import__",
    "compile",
    "Popen",
    "system",
    "startfile",
    "run",
    "call",
    "check_call",
    "check_output",
    "rglob",
    "walk",
    "unlink",
    "rename",
}

REQUIRED_COMMANDS = [
    "ai model review approval status",
    "ai model review approval list",
    "ai model review approval validate-folder",
    "ai model review approval approve-folder",
    "ai model review approval approve-expected",
    "ai model review approval manifest",
    "ai model review approval json",
]


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
    spec = importlib.util.spec_from_file_location("engel_ai_model_review_approval", MODULE)
    require(spec is not None and spec.loader is not None, "could not load model review approval module")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_ai_model_review_approval"] = module
    spec.loader.exec_module(module)
    return module


def check_files() -> None:
    for path in [MODULE, VERIFIER, REPORT, APPROVAL_ROOT, RECEIPTS, MANIFESTS, EXAMPLES, READINESS_VERIFIER, INTAKE_VERIFIER, MODEL_PLAN_VERIFIER]:
        require(path.exists(), "missing required path: " + str(path.relative_to(ROOT)))


def check_static_safety() -> None:
    source = read(MODULE)
    tree = ast.parse(source)
    for needle in [
        "APPROVE_MODEL_DRY_RUN",
        "approved_for_runtime_dry_run_only",
        "human_approved_for_runtime_dry_run",
        "runtime_dry_run_eligible",
        "MODEL APPROVED FOR RUNTIME DRY-RUN ELIGIBILITY ONLY",
        "inference_enabled",
        "auto_load_enabled",
        "trusted_memory_write_enabled",
    ]:
        require(needle in source, "module missing required safety text: " + needle)
    for forbidden in [
        "requests.",
        "socket.",
        "webbrowser.",
        "openai.",
        "anthropic.",
        "ollama",
        "llama_cpp",
        "llama.cpp",
        "start_llama",
        "pip install",
        "invoke-webrequest",
        "curl ",
        "wsl.exe",
        "docker.",
        ".rglob(",
        "os.walk(",
    ]:
        require(forbidden not in source.lower(), "module contains forbidden behavior text: " + forbidden)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                require(alias.name.split(".")[0] not in FORBIDDEN_IMPORTS, "forbidden import: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            require(node.module.split(".")[0] not in FORBIDDEN_IMPORTS, "forbidden import: " + node.module)
        elif isinstance(node, (ast.While, ast.AsyncFunctionDef)):
            raise CheckFailure("module contains forbidden worker shape")
        elif isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
            if isinstance(func, ast.Name) and name == "exec":
                raise CheckFailure("module contains forbidden call: exec")
            require(name not in FORBIDDEN_CALLS, "module contains forbidden call: " + name)


def capture_main(module, args: list[str]) -> tuple[int, str]:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = module.main(args)
    return int(code), buffer.getvalue()


def check_runtime_behavior() -> None:
    module = load_module()
    for command in ["status", "list", "manifest", "json"]:
        code, output = capture_main(module, [command])
        require(code == 0, "command failed: " + command)
        require(output.strip(), "empty output for command: " + command)
    payload = json.loads(capture_main(module, ["json"])[1])
    require(payload["safety_flags"]["inference_enabled"] is False, "inference must remain disabled")
    require(payload["safety_flags"]["auto_load_enabled"] is False, "auto-load must remain disabled")
    require(payload["safety_flags"]["model_runtime_start_enabled"] is False, "runtime start must remain disabled")

    missing = module.validate_folder(str(ROOT / "does-not-exist-model-folder"))
    require(missing["valid"] is False and missing["reason"] == "folder_missing", "missing folder must be rejected")
    outside = module.validate_folder(str(ROOT))
    require(outside["valid"] is False and outside["reason"] == "outside_approved_model_folders_rejected", "outside folder must be rejected")
    traversal = module.validate_folder(r"..\unsafe-model-folder")
    require(traversal["valid"] is False and traversal["reason"] == "path_traversal_rejected", "path traversal must be rejected")

    EXAMPLES.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="verifier_model_review_", dir=EXAMPLES) as temp_name:
        fixture_folder = Path(temp_name)
        fixture_file = fixture_folder / "tiny-review-fixture.gguf"
        fixture_file.write_bytes(b"GGUF tiny review approval verifier fixture\n")
        valid = module.validate_folder(str(fixture_folder))
        require(valid["valid"] is True, "safe tiny fixture folder should validate")
        require(valid["root_status"] == "example_fixture", "fixture root status mismatch")

        with tempfile.TemporaryDirectory() as output_name:
            output = Path(output_name)
            receipt_dir = output / "receipts"
            manifest_path = output / "manifests" / "approval_manifest.json"

            try:
                module.approve_folder(
                    str(fixture_folder),
                    tier="Tiny Seed Mode",
                    approval_token=None,
                    receipt_dir=receipt_dir,
                    manifest_path=manifest_path,
                )
            except module.ModelReviewApprovalError as exc:
                require(str(exc) == "approval_token_rejected", "missing token rejection mismatch")
            else:
                raise CheckFailure("missing approval token must refuse")

            try:
                module.approve_folder(
                    str(fixture_folder),
                    tier="Tiny Seed Mode",
                    approval_token="WRONG_TOKEN",
                    receipt_dir=receipt_dir,
                    manifest_path=manifest_path,
                )
            except module.ModelReviewApprovalError as exc:
                require(str(exc) == "approval_token_rejected", "wrong token rejection mismatch")
            else:
                raise CheckFailure("wrong approval token must refuse")

            result = module.approve_folder(
                str(fixture_folder),
                tier="Tiny Seed Mode",
                approval_token="APPROVE_MODEL_DRY_RUN",
                receipt_dir=receipt_dir,
                manifest_path=manifest_path,
                created_at="2026-05-17T00:00:00Z",
            )
            receipt_json = Path(result["receipt_json"])
            if not receipt_json.is_absolute():
                receipt_json = ROOT / receipt_json
            require(receipt_json.exists(), "approval receipt JSON missing")
            receipt = json.loads(receipt_json.read_text(encoding="utf-8"))
            require(receipt["final_decision"] == module.FINAL_DECISION, "receipt final decision mismatch")
            require(receipt["approval_token_name"] == "APPROVE_MODEL_DRY_RUN", "approval token name missing")
            require(receipt["approval_token_verified"] is True, "approval token not verified")
            require(receipt["approved_for_runtime_dry_run"] is True, "dry-run approval missing")
            require(receipt["runtime_dry_run_eligible"] is True, "dry-run eligibility missing")
            for key in [
                "approved_for_runtime",
                "runtime_ready",
                "inference_enabled",
                "auto_load_enabled",
                "provider_api_enabled",
                "download_enabled",
                "trusted_memory_write_enabled",
            ]:
                require(receipt[key] is False, "receipt safety value must be false: " + key)
            receipt_text = receipt_json.with_suffix(".md").read_text(encoding="utf-8")
            require("MODEL APPROVED FOR RUNTIME DRY-RUN ELIGIBILITY ONLY" in receipt_text, "markdown receipt missing final decision")
            require("Model was not loaded" in receipt_text, "markdown receipt missing no-load statement")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            require(manifest["entry_count"] == 1, "test manifest entry count mismatch")
            require(manifest["safety"]["inference_enabled"] is False, "manifest inference must remain false")


def check_docs_and_registration() -> None:
    report = read(REPORT)
    for needle in [
        "ENGEL_AI_MODEL_REVIEW_APPROVAL_V1",
        "User-approved folders",
        "APPROVE_MODEL_DRY_RUN",
        "runtime dry-run eligibility only",
        "does not load models",
        "Full codex verifier result",
    ]:
        require(needle in report, "report missing required text: " + needle)
    commands = read(COMMANDS)
    for command in REQUIRED_COMMANDS:
        require(command in commands, "ENGEL_COMMANDS missing command: " + command)
    codex = read(CODEX_VERIFY)
    require("tools\\verify_engel_ai_model_review_approval.py" in codex, "codex verifier missing model review approval verifier")


def main() -> int:
    try:
        check_files()
        check_static_safety()
        check_runtime_behavior()
        check_docs_and_registration()
    except CheckFailure as exc:
        print("[FAIL]", exc)
        return 1
    print("[PASS] Engel AI Model Review Approval verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
