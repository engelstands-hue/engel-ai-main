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
MODULE = ROOT / "engel_memory_roots_storage_layout.py"
VERIFIER = ROOT / "tools" / "verify_engel_memory_roots_storage_layout.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_MEMORY_ROOTS_STORAGE_LAYOUT_V1.md"
STABLE_FIX_REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_MEMORY_ROOTS_STABLE_WRITE_FIX_V1.md"
REPORT_ROOT = ROOT / "reports" / "memory_roots_storage_layout"
RECEIPTS = REPORT_ROOT / "receipts"
EXAMPLES = REPORT_ROOT / "examples"
MANIFEST_JSON = ROOT / "memory" / "ENGEL_MEMORY_ROOTS_STORAGE_LAYOUT_V1.json"
MANIFEST_MD = ROOT / "memory" / "ENGEL_MEMORY_ROOTS_STORAGE_LAYOUT_V1.md"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"
READINESS = ROOT / "engel_ai_runtime_readiness.py"
RUNTIME_PATH_CONFIG = ROOT / "engel_ai_local_runtime_path_config.py"
READINESS_VERIFIER = ROOT / "tools" / "verify_engel_ai_runtime_readiness.py"
RUNTIME_PATH_VERIFIER = ROOT / "tools" / "verify_engel_ai_local_runtime_path_config.py"
OFFLINE_DRY_RUN_VERIFIER = ROOT / "tools" / "verify_engel_ai_offline_runtime_dry_run.py"
MODEL_APPROVAL_VERIFIER = ROOT / "tools" / "verify_engel_ai_model_review_approval.py"

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
    "memory roots storage layout status",
    "memory roots storage layout roots",
    "memory roots storage layout scaffold-f",
    "memory roots storage layout validate",
    "memory roots storage layout manifest",
    "memory roots storage layout json",
]

ALLOWED_MARKER_NAMES = {"README.md", "README_ENGEL_MEMORY_ROOT.md", ".gitkeep"}
STABLE_FILES = [MANIFEST_JSON, MANIFEST_MD]
SAFETY_FLAGS = [
    "auto_index_enabled",
    "inference_enabled",
    "download_enabled",
    "trusted_memory_write_enabled",
    "model_load_enabled",
    "runtime_execution_enabled",
    "provider_api_enabled",
    "source_route_queue_mutation",
]


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def read_json(path: Path) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(data, dict), "JSON file did not contain an object: " + str(path.relative_to(ROOT)))
    return data


def stable_file_snapshot() -> dict[Path, bytes]:
    return {path: path.read_bytes() for path in STABLE_FILES}


def require_stable_snapshot_unchanged(before: dict[Path, bytes], context: str) -> None:
    for path, content in before.items():
        require(path.read_bytes() == content, context + " changed stable file: " + str(path.relative_to(ROOT)))


def require_lf_file(path: Path) -> None:
    data = path.read_bytes()
    rel = str(path.relative_to(ROOT))
    require(not data.startswith(b"\xef\xbb\xbf"), rel + " must be UTF-8 without BOM")
    require(b"\r" not in data, rel + " must use LF line endings only")
    require(data.endswith(b"\n"), rel + " must end with one LF newline")
    require(not data.endswith(b"\n\n"), rel + " must not end with extra blank newlines")


def load_module(name: str, path: Path):
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, "could not load module: " + path.name)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def check_files() -> None:
    for path in [
        MODULE,
        VERIFIER,
        REPORT,
        STABLE_FIX_REPORT,
        MANIFEST_JSON,
        MANIFEST_MD,
        REPORT_ROOT,
        RECEIPTS,
        EXAMPLES,
        READINESS,
        RUNTIME_PATH_CONFIG,
        READINESS_VERIFIER,
        RUNTIME_PATH_VERIFIER,
        OFFLINE_DRY_RUN_VERIFIER,
        MODEL_APPROVAL_VERIFIER,
    ]:
        require(path.exists(), "missing required path: " + str(path.relative_to(ROOT)))


def check_static_safety() -> None:
    for path in [MODULE, READINESS, RUNTIME_PATH_CONFIG]:
        source = read(path)
        tree = ast.parse(source)
        for forbidden in [
            "requests.",
            "socket.",
            "webbrowser.",
            "openai.",
            "anthropic.",
            "ollama",
            "llama.cpp server",
            "start_llama",
            "pip install",
            "invoke-webrequest",
            "curl ",
            "wsl.exe",
            "docker.",
            ".rglob(",
            "os.walk(",
        ]:
            require(forbidden not in source.lower(), path.name + " contains forbidden behavior text: " + forbidden)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    require(alias.name.split(".")[0] not in FORBIDDEN_IMPORTS, "forbidden import in " + path.name + ": " + alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                require(node.module.split(".")[0] not in FORBIDDEN_IMPORTS, "forbidden import in " + path.name + ": " + node.module)
            elif isinstance(node, (ast.While, ast.AsyncFunctionDef)):
                raise CheckFailure(path.name + " contains forbidden worker shape")
            elif isinstance(node, ast.Call):
                func = node.func
                name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
                if isinstance(func, ast.Name) and name == "exec":
                    raise CheckFailure(path.name + " contains forbidden call: exec")
                require(name not in FORBIDDEN_CALLS, path.name + " contains forbidden call: " + name)

    source = read(MODULE)
    for needle in [
        "APPROVE_MEMORY_ROOT_SCAFFOLD",
        "/opt/engel",
        "/opt/engel/models-active",
        "/mnt/engel-hdd-vault",
        "CT246 engel-ai-main fast SSD runtime root",
        "active_runtime_chat_models_services",
        "active_inference_models",
        "bulk_archive_training_outputs_datasets",
        "MEMORY ROOT SCAFFOLD CREATED",
        "NO MODEL LOAD",
        "NO INFERENCE",
        "NO FILE MIGRATION",
    ]:
        require(needle in source, "storage layout module missing required text: " + needle)
    for needle in [
        "def read_existing_created_at",
        "def normalize_lf",
        "def write_text_if_changed",
        "existing_bytes == desired_bytes",
        "write_text_if_changed(MANIFEST_JSON",
        "write_text_if_changed(MANIFEST_MD",
        "read_existing_created_at() or fallback or now_utc()",
    ]:
        require(needle in source, "storage layout module missing stable writer contract: " + needle)
    require("write_lf_text(MANIFEST_JSON" not in source, "manifest JSON must use compare-before-write")
    require("write_lf_text(MANIFEST_MD" not in source, "manifest markdown must use compare-before-write")
    status_block = source.split("def status_payload()", 1)[1].split("def render_status", 1)[0]
    require("ensure_report_folders" not in status_block, "status_payload must be read-only")
    json_block = source.split('elif args.command == "json":', 1)[1].split("except MemoryRootsLayoutError", 1)[0]
    require("write_manifest" not in json_block, "json command must not rewrite stable manifest files")
    require("/mnt/engel-hdd-vault" in read(READINESS), "readiness must represent the Dell HDD archive root")
    require("/mnt/engel-hdd-vault" in read(RUNTIME_PATH_CONFIG), "runtime path config must recognize the Dell HDD archive root")


def capture_main(module, args: list[str]) -> tuple[int, str]:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = module.main(args)
    return int(code), buffer.getvalue()


def check_stable_contract_files() -> None:
    for path in STABLE_FILES:
        require(path.exists(), "missing stable file: " + str(path.relative_to(ROOT)))
        require_lf_file(path)

    manifest = read_json(MANIFEST_JSON)
    markdown = read(MANIFEST_MD)
    created_at = manifest.get("created_at")
    require(isinstance(created_at, str) and created_at, "manifest created_at must be a stable string")
    require(f"- created_at: `{created_at}`" in markdown, "markdown created_at must match JSON created_at")
    require("f_scaffold_status" not in manifest, "stable manifest must not include volatile F scaffold status")

    roots = manifest.get("approved_roots")
    require(isinstance(roots, list), "manifest approved_roots must be a list")
    by_path = {root.get("path"): root for root in roots if isinstance(root, dict)}
    expected_roles = {
        "/opt/engel": "active_runtime_chat_models_services",
        "/opt/engel/models-active": "active_inference_models",
        "/mnt/engel-hdd-vault": "bulk_archive_training_outputs_datasets",
    }
    require(set(by_path) == set(expected_roles), "stable manifest must contain exactly the CT246 SSD and Dell HDD roots")
    for path_text, role in expected_roles.items():
        root = by_path[path_text]
        require(root.get("role") == role, "role mismatch in stable manifest: " + path_text)
        require(root.get("recursive_scan_enabled") is False, "recursive scan must remain false: " + path_text)
        require("present" not in root, "stable manifest root must not include volatile presence: " + path_text)
        preferred = root.get("preferred_for")
        require(isinstance(preferred, list) and preferred, "preferred_for missing in stable manifest: " + path_text)

    require(by_path["/mnt/engel-hdd-vault"].get("scaffold_created") is False, "unmounted Dell HDD scaffold state must remain false")
    require("Dell server HDD vault" in str(by_path["/mnt/engel-hdd-vault"].get("note")), "Dell HDD note missing")
    require(manifest.get("preferred_runtime_root") == "/opt/engel", "preferred runtime root mismatch")
    require(manifest.get("existing_model_root") == "/opt/engel/models-active", "existing model root mismatch")
    require(manifest.get("expansion_library_root") == "/mnt/engel-hdd-vault", "expansion library root mismatch")
    for key in SAFETY_FLAGS:
        require(manifest.get(key) is False, "stable manifest safety flag must remain false: " + key)
        require(f"- {key}: `false`" in markdown, "markdown safety flag missing or not false: " + key)


def check_runtime_behavior() -> None:
    module = load_module("engel_memory_roots_storage_layout", MODULE)
    for command in ["status", "roots", "validate", "json"]:
        code, output = capture_main(module, [command])
        require(code == 0, "command failed: " + command)
        require(output.strip(), "empty output for command: " + command)

    payload = json.loads(capture_main(module, ["json"])[1])
    root_paths = {root["path"] for root in payload["approved_roots"]}
    for root in ["/opt/engel", "/opt/engel/models-active", "/mnt/engel-hdd-vault"]:
        require(root in root_paths, "missing approved root: " + root)
    roles = {root["path"]: root["role"] for root in payload["approved_roots"]}
    require(roles["/opt/engel"] == "active_runtime_chat_models_services", "CT246 runtime role mismatch")
    require(roles["/opt/engel/models-active"] == "active_inference_models", "CT246 model role mismatch")
    require(roles["/mnt/engel-hdd-vault"] == "bulk_archive_training_outputs_datasets", "Dell HDD role mismatch")
    require(payload["manifest"]["preferred_runtime_root"] == "/opt/engel", "preferred runtime root mismatch")
    require(payload["manifest"]["existing_model_root"] == "/opt/engel/models-active", "existing model root mismatch")
    require(payload["manifest"]["expansion_library_root"] == "/mnt/engel-hdd-vault", "expansion library root mismatch")
    for key in [
        "recursive_scan_enabled",
        "auto_index_enabled",
        "inference_enabled",
        "model_load_enabled",
        "download_enabled",
        "install_enabled",
        "trusted_memory_write_enabled",
        "source_route_queue_mutation",
    ]:
        require(payload["safety_flags"][key] is False, "safety flag must remain false: " + key)

    stable_before = stable_file_snapshot()
    created_at_before = read_json(MANIFEST_JSON)["created_at"]
    for command in ["status", "json", "manifest", "manifest", "status"]:
        code, output = capture_main(module, [command])
        require(code == 0, "stability command failed: " + command)
        require(output.strip(), "empty stability output for command: " + command)
    require_stable_snapshot_unchanged(stable_before, "repeated status/generation")
    created_at_after = read_json(MANIFEST_JSON)["created_at"]
    require(created_at_after == created_at_before, "created_at changed during repeated status/generation")

    with tempfile.TemporaryDirectory(prefix="engel_memory_roots_") as temp_name:
        temp = Path(temp_name)
        fake_target = temp / "engel-hdd-vault"
        receipt_dir = temp / "receipts"
        manifest_json = temp / "memory_manifest.json"
        manifest_md = temp / "memory_manifest.md"
        original = (module.TARGET_ROOT, module.RECEIPT_DIR, module.MANIFEST_JSON, module.MANIFEST_MD)
        module.TARGET_ROOT = fake_target
        module.RECEIPT_DIR = receipt_dir
        module.MANIFEST_JSON = manifest_json
        module.MANIFEST_MD = manifest_md
        try:
            try:
                module.scaffold_f(approval_token=None)
            except module.MemoryRootsLayoutError as exc:
                require(str(exc) == "approval_token_rejected", "missing token refusal mismatch")
            else:
                raise CheckFailure("missing approval token must refuse")
            try:
                module.scaffold_f(approval_token="WRONG_TOKEN")
            except module.MemoryRootsLayoutError as exc:
                require(str(exc) == "approval_token_rejected", "wrong token refusal mismatch")
            else:
                raise CheckFailure("wrong approval token must refuse")

            result = module.scaffold_f(approval_token="APPROVE_MEMORY_ROOT_SCAFFOLD", created_at="2026-05-17T00:00:00Z")
            require(result["scaffold_status"] == "created_or_confirmed", "scaffold should be created in fixture")
            receipt = json.loads(Path(result["receipt_json"]).read_text(encoding="utf-8"))
            require(receipt["final_decision"] == module.FINAL_DECISION_SUCCESS, "receipt decision mismatch")
            require(receipt["approval_token_name"] == "APPROVE_MEMORY_ROOT_SCAFFOLD", "receipt token name mismatch")
            require(receipt["approval_token_verified"] is True, "receipt token verification mismatch")
            for key in [
                "files_moved",
                "files_deleted",
                "files_copied_from_existing_roots",
                "models_loaded",
                "runtime_executed",
                "inference_enabled",
                "download_enabled",
                "install_enabled",
                "auto_index_enabled",
                "trusted_memory_write_enabled",
                "source_route_queue_mutation",
            ]:
                require(receipt[key] is False, "receipt safety value must be false: " + key)
            status = module.f_scaffold_status()
            require(status["complete"] is True, "fixture archive scaffold should be complete")
            expected_relatives = {str(Path(item)) for item in module.TARGET_SCAFFOLD_FOLDERS}
            actual_dirs = {str(path.relative_to(fake_target)) for path in fake_target.iterdir() if path.is_dir()}
            require({"models", "runtimes", "libraries", "chat_exports", "remote_worker", "code_companion"}.issubset(actual_dirs), "major scaffold folders missing")
            for marker in module.f_marker_paths():
                require(marker.name in ALLOWED_MARKER_NAMES, "unexpected marker file name: " + marker.name)
                require(marker.exists(), "expected marker missing: " + str(marker))
            for path in fake_target.rglob("*"):
                if path.is_file():
                    require(path.name in ALLOWED_MARKER_NAMES, "scaffold created unexpected file: " + path.name)
                    require(path.stat().st_size < 4096, "marker file too large: " + str(path))
            manifest = json.loads(manifest_json.read_text(encoding="utf-8"))
            require(manifest["created_at"] == "2026-05-17T00:00:00Z", "fixture manifest created_at fallback mismatch")
            fixture_roots = {root["path"]: root for root in manifest["approved_roots"]}
            require(fixture_roots["/mnt/engel-hdd-vault"]["scaffold_created"] is True, "fixture manifest scaffold state mismatch")
            require("f_scaffold_status" not in manifest, "fixture stable manifest must not include volatile scaffold status")
            require("CT246/HDD SCAFFOLD CREATED IF APPROVED" in manifest["final_decision"], "manifest decision mismatch")
        finally:
            module.TARGET_ROOT, module.RECEIPT_DIR, module.MANIFEST_JSON, module.MANIFEST_MD = original

    runtime_config = load_module("engel_ai_local_runtime_path_config_for_memory_roots", RUNTIME_PATH_CONFIG)
    roots = {root["path"]: root["role"] for root in runtime_config.approved_root_statuses()}
    require("/mnt/engel-hdd-vault" in roots, "runtime path config must list the Dell HDD root")
    require(roots["/mnt/engel-hdd-vault"] == "bulk_archive_training_outputs_datasets", "runtime path Dell HDD role mismatch")
    require(str(runtime_config.PREFERRED_RUNTIME_ROOT).replace("\\", "/") == "/opt/engel", "CT246 must remain the preferred runtime root")

    readiness = load_module("engel_ai_runtime_readiness_for_memory_roots", READINESS)
    readiness_payload = readiness.readiness_payload()
    runtime_boundaries = readiness_payload["runtime_boundaries"]
    readiness_roots = {root["path"]: root for root in runtime_boundaries["approved_engel_roots"]}
    require("/mnt/engel-hdd-vault" in readiness_roots, "readiness must list the Dell HDD root")
    require(runtime_boundaries["preferred_runtime_root"] == "/opt/engel/runtime", "readiness preferred runtime root mismatch")
    require(runtime_boundaries["expansion_library_root"] == "/mnt/engel-hdd-vault/libraries", "readiness expansion library root mismatch")
    require(runtime_boundaries["runtime_path_config_status"]["inference_enabled"] is False, "readiness inference must remain false")


def check_docs_and_registration() -> None:
    report = read(REPORT)
    for needle in [
        "ENGEL_MEMORY_ROOTS_STORAGE_LAYOUT_V1",
        "/opt/engel",
        "/opt/engel/models-active",
        "/mnt/engel-hdd-vault",
        "CT246 SSD",
        "Dell internal HDD",
        "This phase records and scaffolds Engel memory roots only.",
        "Packaging skipped",
    ]:
        require(needle in report, "report missing required text: " + needle)
    stable_report = read(STABLE_FIX_REPORT)
    for needle in [
        "ENGEL_MEMORY_ROOTS_STABLE_WRITE_FIX_V1",
        "created_at preservation",
        "Compare-before-write",
        "LF line endings",
        "Repeated-run stability proof",
        "Full Codex verifier result",
        "Packaging skipped",
        "This phase stabilizes memory-root file writes only. It does not change storage roots, scan drives, enable indexing, load models, run inference, download/install anything, write trusted memory, mutate routes/queues, or package EXEs.",
    ]:
        require(needle in stable_report, "stable-write report missing required text: " + needle)
    commands = read(COMMANDS)
    for command in REQUIRED_COMMANDS:
        require(command in commands, "command docs missing: " + command)
    codex_verify = read(CODEX_VERIFY)
    require("tools\\verify_engel_memory_roots_storage_layout.py" in codex_verify, "codex verifier missing memory roots verifier")


def main() -> int:
    stable_before = stable_file_snapshot() if all(path.exists() for path in STABLE_FILES) else {}
    try:
        check_files()
        check_static_safety()
        check_stable_contract_files()
        check_runtime_behavior()
        check_docs_and_registration()
        if stable_before:
            require_stable_snapshot_unchanged(stable_before, "verifier")
    except CheckFailure as exc:
        print("[FAIL] " + str(exc))
        return 1
    print("[PASS] Engel Memory Roots Storage Layout verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
