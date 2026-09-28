from __future__ import annotations

import ast
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
EVALUATOR = ROOT / "engel_manual_model_intake_evaluator.py"
VERIFIER = ROOT / "tools" / "verify_engel_manual_model_intake_evaluator.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_MANUAL_MODEL_INTAKE_EVALUATION_V1.md"
REVIEW_ROOT = ROOT / "reports" / "model_intake_reviews"
MANUAL_ROOT_TEXT = r"G:\ENGEL_APP_MEMORY\models\manual_downloads"


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    if not path.exists():
        raise CheckFailure("missing required file: " + str(path.relative_to(ROOT)))
    return path.read_text(encoding="utf-8", errors="replace")


def check_files_exist() -> None:
    for path in [EVALUATOR, VERIFIER]:
        require(path.exists() and path.is_file(), "required file missing: " + str(path.relative_to(ROOT)))
    require(REVIEW_ROOT.exists(), "model intake review folder missing")


def check_static_source() -> None:
    source = read(EVALUATOR)
    tree = ast.parse(source)
    for option in ["--candidate", "--dry-run", "--write-review", "--mark-rejected", "--approval-token"]:
        require(option in source, "missing CLI option: " + option)
    for label in [
        "MODEL_INTAKE_REVIEW_ONLY",
        "NO_MODEL_LOADING",
        "NO_INFERENCE",
        "NO_TRAINING",
        "NO_AUTO_MOVE",
        "NO_AUTO_DELETE",
        "NO_AUTO_DOWNLOAD",
        "NO_NETWORK",
        "NO_BROWSER",
        "NO_PROVIDER_CALLS",
        "NO_TRUSTED_MEMORY_WRITE",
        "HUMAN_APPROVAL_REQUIRED",
    ]:
        require(label in source, "missing required boundary label: " + label)
    for decision in [
        "APPROVED_FOR_MODEL_LIBRARY_CANDIDATE",
        "HOLD_NEEDS_HUMAN_SOURCE_REVIEW",
        "HOLD_UNSUPPORTED_FORMAT",
        "HOLD_TOO_LARGE_FOR_CURRENT_MACHINE",
        "REJECT_NOT_A_MODEL",
        "REJECT_UNSAFE_OR_UNKNOWN_ORIGIN",
        "QUARANTINE_CANDIDATE",
    ]:
        require(decision in source, "missing decision label: " + decision)
    for required in [
        MANUAL_ROOT_TEXT,
        "is_under_manual_downloads",
        "NO_MODEL_LOADING",
        "no_inference_performed",
        "no_movement_performed",
        "no_deletion_performed",
        "NOT_AN_AI_MODEL",
        "WSL",
        "Ubuntu",
        "distro export",
        "environment/runtime dependency notes",
        "Tiny Seed Mode",
        "Daily Local Mode",
        "Research Worker Mode",
        "Alternative Research Worker",
        "FILENAME_AND_FILESYSTEM_METADATA_ONLY_NOT_INSTRUCTIONS",
        "APPROVE_MODEL_REJECTION_MARK",
        "do not merge into Engel model library",
    ]:
        require(required in source, "missing required source text: " + required)
    forbidden_imports = {
        "requests",
        "urllib",
        "socket",
        "webbrowser",
        "openai",
        "subprocess",
        "threading",
        "multiprocessing",
        "shutil",
        "llama_cpp",
        "ollama",
        "torch",
        "transformers",
    }
    forbidden_calls = {
        "unlink",
        "remove",
        "rmdir",
        "rename",
        "rglob",
        "walk",
        "load",
        "infer",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                require(alias.name.split(".")[0] not in forbidden_imports, "forbidden import: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            require(node.module.split(".")[0] not in forbidden_imports, "forbidden import: " + node.module)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute):
                require(func.attr not in forbidden_calls, "forbidden call: " + func.attr)
            elif isinstance(func, ast.Name):
                require(func.id not in {"eval", "exec", "__import__"}, "forbidden dynamic call: " + func.id)
        elif isinstance(node, ast.While):
            raise CheckFailure("while loops are forbidden")
    for forbidden_text in [
        "delete(",
        "DeleteFile",
        "Start-Process",
        "http://",
        "https://",
        "llama_cpp",
        "from_pretrained",
        "AutoModel",
        "pipeline(",
        "model.generate",
    ]:
        require(forbidden_text not in source, "forbidden behavior text present: " + forbidden_text)


def load_module():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import engel_manual_model_intake_evaluator as evaluator

    return evaluator


def check_runtime_behavior() -> None:
    evaluator = load_module()
    manual_root = evaluator.MANUAL_DOWNLOADS_ROOT
    fake = manual_root / "engel_fake_wsl_ubuntu_runtime_export.tar"
    review = evaluator.evaluate_candidate(str(fake), mode="dry-run")
    if fake.exists():
        require(review["decision"] == "REJECT_NOT_A_MODEL", "WSL/Ubuntu candidate should be rejected as not model")
        require(review["detected_type"] == "NOT_AN_AI_MODEL", "WSL/Ubuntu candidate should classify as NOT_AN_AI_MODEL")
    else:
        require(review["decision"] == "QUARANTINE_CANDIDATE", "missing fake candidate should fail closed")
        require("candidate path does not exist" in review.get("errors", []), "missing fake candidate should report missing path")
    outside = ROOT / "README.md"
    outside_review = evaluator.evaluate_candidate(str(outside), mode="dry-run")
    require(outside_review["decision"] == "QUARANTINE_CANDIDATE", "outside path should fail closed")
    require(any("manual_downloads" in item for item in outside_review.get("errors", [])), "outside path should require manual_downloads boundary")
    rendered = evaluator.render_review(outside_review)
    for phrase in [
        "no model loading",
        "no inference",
        "no movement performed",
        "no deletion performed",
        "human approval required",
    ]:
        require(phrase in rendered, "rendered review missing boundary: " + phrase)
    with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
        temp_path = Path(temp_dir) / "candidate.gguf"
        temp_path.write_text("metadata smoke only", encoding="utf-8")
        temp_review = evaluator.evaluate_candidate(str(temp_path), mode="dry-run")
        require(temp_review["decision"] == "QUARANTINE_CANDIDATE", "project-local temp outside manual downloads must fail closed")


def check_report_if_present() -> None:
    if not REPORT.exists():
        return
    text = read(REPORT)
    for needle in [
        "Engel Manual Model Intake Evaluation V1",
        "files read first",
        "evaluator behavior",
        "verification results",
        "smoke results",
        "no model loading",
        "no inference",
        "no deletion",
        "packaging skipped",
    ]:
        require(needle in text, "report missing text: " + needle)


def main() -> int:
    checks = [
        ("files", check_files_exist),
        ("static_source", check_static_source),
        ("runtime_behavior", check_runtime_behavior),
        ("report", check_report_if_present),
    ]
    failures: list[str] = []
    for name, fn in checks:
        try:
            fn()
            print("PASS " + name)
        except CheckFailure as exc:
            failures.append(f"{name}: {exc}")
            print(f"FAIL {name}: {exc}")
        except Exception as exc:
            failures.append(f"{name}: unexpected error: {exc}")
            print(f"FAIL {name}: unexpected error: {exc}")
    if failures:
        print("\nEngel Manual Model Intake Evaluator verifier FAILED")
        for failure in failures:
            print("- " + failure)
        return 1
    print("\nEngel Manual Model Intake Evaluator verifier PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
