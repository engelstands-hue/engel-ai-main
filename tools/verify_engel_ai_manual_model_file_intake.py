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
MODULE = ROOT / "engel_ai_manual_model_file_intake.py"
VERIFIER = ROOT / "tools" / "verify_engel_ai_manual_model_file_intake.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_AI_MANUAL_MODEL_FILE_INTAKE_V1.md"
INTAKE_ROOT = ROOT / "reports" / "ai_model_intake"
RECEIPTS = INTAKE_ROOT / "receipts"
MANIFESTS = INTAKE_ROOT / "manifests"
EXAMPLES = INTAKE_ROOT / "examples"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"
READINESS_VERIFIER = ROOT / "tools" / "verify_engel_ai_runtime_readiness.py"
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
    "ai manual model file intake status",
    "ai manual model file intake list",
    "ai manual model file intake validate",
    "ai manual model file intake intake",
    "ai manual model file intake intake-expected",
    "ai manual model file intake manifest",
    "ai manual model file intake json",
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
    spec = importlib.util.spec_from_file_location("engel_ai_manual_model_file_intake", MODULE)
    require(spec is not None and spec.loader is not None, "could not load model intake module")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_ai_manual_model_file_intake"] = module
    spec.loader.exec_module(module)
    return module


def check_files() -> None:
    for path in [MODULE, VERIFIER, REPORT, INTAKE_ROOT, RECEIPTS, MANIFESTS, EXAMPLES, READINESS_VERIFIER, MODEL_PLAN_VERIFIER]:
        require(path.exists(), "missing required path: " + str(path.relative_to(ROOT)))


def check_static_safety() -> None:
    source = read(MODULE)
    tree = ast.parse(source)
    for needle in [
        "MAX_AUTO_HASH_BYTES",
        "skipped_large_file_policy",
        "untrusted_until_model_review",
        "present_unreviewed",
        "runtime_ready",
        "inference_enabled",
        "auto_load_enabled",
        "MODEL FILE RECORDED FOR REVIEW - NOT LOADED - NOT TRUSTED",
        "external_unreviewed",
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


def capture_main(module, args: list[str]) -> str:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = module.main(args)
    require(code == 0, "command failed: " + " ".join(args))
    return buffer.getvalue()


def check_runtime_behavior() -> None:
    module = load_module()
    for command in ["status", "list", "manifest", "json"]:
        output = capture_main(module, [command])
        require(output.strip(), "empty output for command: " + command)
    json_payload = json.loads(capture_main(module, ["json"]))
    require(json_payload["safety_flags"]["inference_enabled"] is False, "inference must be disabled")
    require(json_payload["safety_flags"]["model_load_enabled"] is False, "model loading must be disabled")
    require(json_payload["safety_flags"]["download_enabled"] is False, "download must be disabled")

    with tempfile.TemporaryDirectory() as temp_name:
        temp = Path(temp_name)
        fixture = temp / "tiny-fixture.gguf"
        fixture.write_bytes(b"GGUF tiny verifier fixture\n")
        non_model = temp / "not-a-model.txt"
        non_model.write_text("not a model\n", encoding="utf-8")
        folder = temp / "folder.gguf"
        folder.mkdir()

        non_model_validation = module.validate_model_file(str(non_model))
        require(non_model_validation["valid"] is False, "non-GGUF file must be rejected")
        require(non_model_validation["reason"] == "non_gguf_rejected", "non-GGUF rejection reason mismatch")
        folder_validation = module.validate_model_file(str(folder))
        require(folder_validation["valid"] is False, "directory must be rejected")
        require(folder_validation["reason"] == "directory_rejected", "directory rejection reason mismatch")
        traversal_validation = module.validate_model_file(r"..\unsafe.gguf")
        require(traversal_validation["valid"] is False, "path traversal must be rejected")

        fixture_validation = module.validate_model_file(str(fixture))
        require(fixture_validation["valid"] is True, "tiny GGUF fixture should validate")
        require(fixture_validation["root_status"] == "external_unreviewed", "outside fixture must be documented as external_unreviewed")

        receipt_dir = temp / "receipts"
        result = module.intake_model_file(str(fixture), receipt_dir=receipt_dir, created_at="2026-05-17T00:00:00Z")
        receipt_json = Path(result["receipt_json"])
        if not receipt_json.is_absolute():
            receipt_json = ROOT / receipt_json
        require(receipt_json.exists(), "receipt JSON missing")
        payload = json.loads(receipt_json.read_text(encoding="utf-8"))
        require(payload["final_decision"] == module.FINAL_DECISION, "receipt final decision mismatch")
        require(payload["hash_status"] == "computed", "tiny fixture hash should be computed")
        require(isinstance(payload["sha256"], str) and len(payload["sha256"]) == 64, "computed SHA-256 missing")
        for key in ["runtime_ready", "inference_enabled", "auto_load_enabled", "approved_for_runtime", "download_enabled", "provider_api_enabled"]:
            require(payload[key] is False, "receipt safety value must be false: " + key)
        require(payload["trust_level"] == "untrusted_until_model_review", "trust level mismatch")
        require(payload["review_status"] == "present_unreviewed", "review status mismatch")
        receipt_text = receipt_json.with_suffix(".md").read_text(encoding="utf-8")
        require("MODEL FILE RECORDED FOR REVIEW - NOT LOADED - NOT TRUSTED" in receipt_text, "receipt markdown missing final decision")
        require("Model was not loaded" in receipt_text, "receipt markdown missing no-load statement")


def check_docs_and_registration() -> None:
    report = read(REPORT)
    for needle in [
        "ENGEL_AI_MANUAL_MODEL_FILE_INTAKE_V1",
        "Metadata only",
        "Model tiers",
        "Hashing policy",
        "MODEL FILE RECORDED FOR REVIEW - NOT LOADED - NOT TRUSTED",
        "does not load models",
        "Full codex verifier result",
    ]:
        require(needle in report, "report missing required text: " + needle)
    commands = read(COMMANDS)
    for command in REQUIRED_COMMANDS:
        require(command in commands, "ENGEL_COMMANDS missing command: " + command)
    codex = read(CODEX_VERIFY)
    require("tools\\verify_engel_ai_manual_model_file_intake.py" in codex, "codex verifier missing model intake verifier")


def main() -> int:
    try:
        check_files()
        check_static_safety()
        check_runtime_behavior()
        check_docs_and_registration()
    except CheckFailure as exc:
        print("[FAIL]", exc)
        return 1
    print("[PASS] Engel AI Manual Model File Intake verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
