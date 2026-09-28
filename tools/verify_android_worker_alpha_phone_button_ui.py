from __future__ import annotations

import ast
import importlib.util
import io
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
ALPHA = ROOT / "remote_workers" / "android_worker_alpha"
START_UI = ALPHA / "start_remote_worker_ui.py"
PHONE_UI = ALPHA / "remote_worker_phone_ui.py"
START_SHELL = ALPHA / "start_worker_ui.sh"
WIDGET_SHORTCUT = ALPHA / "termux_widget_shortcuts" / "EngelWorkerAlphaUI"
CHOICES = ALPHA / "communication_queen_choices.py"
BRIDGE = ALPHA / "queen_choice_bridge.py"
CHOICE_POLICY = ALPHA / "config" / "queen_choice_policy.json"
PREAPPROVED_ACTIONS = ALPHA / "config" / "preapproved_worker_actions.json"
PHONE_BUTTON_JSON = ROOT / "memory" / "ENGEL_ANDROID_WORKER_ALPHA_PHONE_BUTTON_UI_V1.json"
PHONE_BUTTON_MD = ROOT / "memory" / "ENGEL_ANDROID_WORKER_ALPHA_PHONE_BUTTON_UI_V1.md"
ADB_HELPER = ROOT / "tools" / "setup_android_worker_alpha_adb.py"
ADB_VERIFIER = ROOT / "tools" / "verify_android_worker_alpha_adb_setup.py"
FORBIDDEN_SECOND_HELPER = ROOT / "tools" / "setup_android_worker_alpha_termux_adb.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_ANDROID_WORKER_ALPHA_PHONE_BUTTON_UI_V1.md"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"
FIRST_JOB_ID = "20260516T201324Z_android_worker_alpha_summarize_text_summarize_engel_remote_worke"

PREAPPROVAL_TOKEN = "APPROVE_ANDROID_WORKER_ALPHA_BOUNDED_JOB_CHOICES_V1"
REQUIRED_MENU = [
    "Refresh Status",
    "View Current Job",
    "View Communication Queen Choices",
    "Accept Queen Choice",
    "Run Assigned Job",
    "View Logs",
    "View Receipts",
    "Exit",
]
FORBIDDEN_IMPORTS = {
    "requests",
    "urllib",
    "socket",
    "webbrowser",
    "subprocess",
    "threading",
    "multiprocessing",
    "openai",
}


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def load_json(path: Path) -> dict[str, object]:
    data = json.loads(read(path))
    require(isinstance(data, dict), "JSON root is not object: " + str(path.relative_to(ROOT)))
    return data


def load_adb_helper():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("setup_android_worker_alpha_adb", ADB_HELPER)
    require(spec is not None and spec.loader is not None, "could not load ADB helper")
    module = importlib.util.module_from_spec(spec)
    sys.modules["setup_android_worker_alpha_adb"] = module
    spec.loader.exec_module(module)
    return module


def check_files_exist() -> None:
    for path in [
        START_UI,
        PHONE_UI,
        START_SHELL,
        WIDGET_SHORTCUT,
        CHOICES,
        BRIDGE,
        CHOICE_POLICY,
        PREAPPROVED_ACTIONS,
        PHONE_BUTTON_JSON,
        PHONE_BUTTON_MD,
        ADB_HELPER,
        ADB_VERIFIER,
    ]:
        require(path.exists(), "required phone button UI file missing: " + str(path.relative_to(ROOT)))
    require(not FORBIDDEN_SECOND_HELPER.exists(), "duplicate ADB/Termux helper must not exist")


def check_python_static_safety() -> None:
    for path in [START_UI, PHONE_UI, CHOICES, BRIDGE]:
        source = read(path)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    require(root not in FORBIDDEN_IMPORTS, f"{path.name} imports forbidden package: {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                root = node.module.split(".")[0]
                require(root not in FORBIDDEN_IMPORTS, f"{path.name} imports forbidden package: {node.module}")
            elif isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name):
                    require(func.id not in {"eval", "exec", "__import__"}, f"{path.name} uses forbidden dynamic call: {func.id}")
                elif isinstance(func, ast.Attribute):
                    require(func.attr not in {"system", "popen", "Popen"}, f"{path.name} contains shell execution call: {func.attr}")
            elif isinstance(node, ast.While):
                require(not (isinstance(node.test, ast.Constant) and node.test.value is True), f"{path.name} must not use while True")
        forbidden_active_snippets = [
            "adb install",
            "adb tcpip",
            "adb connect",
            "pkg install",
            "pip install",
            "requests.",
            "socket.",
            "webbrowser.",
            "openai.",
            "fake progress",
            "fake result",
        ]
        lowered = source.lower()
        for snippet in forbidden_active_snippets:
            require(snippet not in lowered, f"{path.name} contains forbidden active snippet: {snippet}")


def check_phone_ui_content() -> None:
    source = read(PHONE_UI)
    for phrase in [
        "Remote Worker only. Communication Queen routes. Engel controls.",
        "Current Job",
        "Real Returned Status",
        "No real returned status packet yet.",
        "Job prepared. Awaiting on-device run.",
        "No returned result yet.",
        "No Communication Queen choices found.",
        "run_worker_main([], stdout=out, stderr=out)",
        "This does not write trusted memory or apply patches.",
    ]:
        require(phrase in source, "phone UI missing phrase/behavior: " + phrase)
    for item in REQUIRED_MENU:
        require(item in source, "phone UI missing menu item: " + item)
    start_text = read(START_UI)
    require("from remote_worker_phone_ui import main" in start_text, "start UI script must launch phone UI module")
    shell_text = read(START_SHELL)
    widget_text = read(WIDGET_SHORTCUT)
    for text, name in [(shell_text, "start_worker_ui.sh"), (widget_text, "EngelWorkerAlphaUI")]:
        require("start_remote_worker_ui.py" in text, name + " must launch start_remote_worker_ui.py")
        require("EngelRemoteWorker/android_worker_alpha" in text, name + " must point to Worker Alpha folder")


def check_choice_bridge_and_policy() -> None:
    policy = load_json(CHOICE_POLICY)
    actions = load_json(PREAPPROVED_ACTIONS)
    for payload, label in [(policy, "queen choice policy"), (actions, "preapproved worker actions")]:
        require(payload.get("worker_id") == "android_worker_alpha", label + " worker id mismatch")
        require(payload.get("preapproval_token") == PREAPPROVAL_TOKEN, label + " preapproval token missing")
        require(payload.get("trusted_memory_write") is False, label + " must block trusted memory write")
        require(payload.get("source_mutation") is False, label + " must block source mutation")
        require(payload.get("route_mutation") is False, label + " must block route mutation")
        require(payload.get("patch_apply") is False, label + " must block patch apply")
        require(payload.get("provider_network") is False, label + " must block provider network")
        require(payload.get("model_runtime") is False, label + " must block model runtime")
        require(payload.get("startup_autorun") is False, label + " must block startup autorun")
        require(payload.get("controls_engel") is False, label + " must block Engel control")
    require(policy.get("routing_layer") == "communication_queen_only", "policy must keep Communication Queen routing")
    require(policy.get("requires_choice_created_by") == "communication_queen", "policy must require Communication Queen choice source")
    require(policy.get("requires_target_worker_id") == "android_worker_alpha", "policy must target Alpha")
    require("run_assigned_allowed_job_locally_on_android" in policy.get("preapproval_scope", []), "policy missing bounded run scope")
    blocked_text = json.dumps(policy.get("preapproval_does_not_allow", []) + actions.get("blocked_actions", [])).lower()
    for phrase in [
        "trusted_memory_write",
        "patch_apply",
        "source_mutation",
        "route_mutation",
        "provider_network",
        "model_runtime",
        # hermes removed from the bounded-preapproval blocked list per
        # ENGEL_HERMES_POLICY_CHANGE_V1 (approved for local install +
        # human-driven testing). Ollama + llama_cpp + the rest stay blocked.
        "ollama",
        "llama_cpp",
        "startup_autorun",
        "control_engel",
    ]:
        require(phrase in blocked_text, "bounded preapproval missing blocked phrase: " + phrase)
    choices_source = read(CHOICES)
    bridge_source = read(BRIDGE)
    for phrase in [
        "created_by",
        "communication_queen",
        "target_worker_id",
        "android_worker_alpha",
        "job_packet_path",
        "input_files",
        PREAPPROVAL_TOKEN,
        "trusted_memory_write",
        "patch_apply",
        "model_runtime",
        "validate_choice",
    ]:
        require(phrase in choices_source, "choice validator missing: " + phrase)
    for phrase in [
        "write_acceptance_receipt",
        "run_started",
        "False",
        "requires_human_review_on_return",
        "accepted_for_local_worker_review",
    ]:
        require(phrase in bridge_source, "choice bridge missing: " + phrase)


def check_contract_docs() -> None:
    data = load_json(PHONE_BUTTON_JSON)
    text = read(PHONE_BUTTON_MD)
    require(data.get("contract_name") == "Engel Android Worker Alpha Phone Button UI V1", "phone button contract name mismatch")
    require(data.get("worker_id") == "android_worker_alpha", "phone button contract worker mismatch")
    require(data.get("adb_bridge_reused") == "tools\\setup_android_worker_alpha_adb.py", "contract must reuse existing ADB bridge")
    require(data.get("duplicate_adb_hook_allowed") is False, "contract must block duplicate hooks")
    require(data.get("push_mode") == "--push-phone-button-ui --i-understand-this-uses-adb", "contract push mode mismatch")
    require(data.get("prepare_mode") == "--prepare-phone-button-commands", "contract prepare mode mismatch")
    require(data.get("check_mode") == "--check-phone-ui", "contract check mode mismatch")
    require(data.get("preapproval_token") == PREAPPROVAL_TOKEN, "contract token mismatch")
    for item in REQUIRED_MENU:
        require(item in data.get("ui_actions", []), "contract missing UI action: " + item)
        require(item in text, "contract Markdown missing UI action: " + item)
    for label in data.get("status_labels", []):
        require(label in text, "contract Markdown missing status label: " + str(label))
    boundaries = data.get("hard_safety_boundaries", {})
    require(isinstance(boundaries, dict), "contract hard boundaries missing")
    for key in [
        "no_termux_install",
        "no_termux_widget_install",
        "no_apk_install",
        "no_python_package_install",
        "no_download",
        "no_worker_run_during_push",
        "no_ui_run_during_push",
        "no_fake_status",
        "no_fake_result",
        "no_fake_progress",
        "no_fake_log",
        "no_fake_receipt",
        "no_trusted_memory_write",
        "no_patch_apply",
        "no_provider_network_browser",
        "no_model_runtime",
        "no_hermes_ollama_llama_cpp",
        "no_background_service",
        "no_startup_autorun",
    ]:
        require(boundaries.get(key) is True, "contract boundary missing/false: " + key)
    for phrase in [
        "Android Worker Alpha is a Remote Worker / Mobile Worker, not a Queen.",
        "Communication Queen assigns and routes choices. Engel controls.",
        "No duplicate ADB or Termux helper is allowed.",
        "python tools\\setup_android_worker_alpha_adb.py --prepare-phone-button-commands",
        "python tools\\setup_android_worker_alpha_adb.py --push-phone-button-ui --i-understand-this-uses-adb",
        "python tools\\setup_android_worker_alpha_adb.py --check-phone-ui",
        PREAPPROVAL_TOKEN,
        "If no Queen choices exist",
        "No returned result yet.",
        "Job prepared. Awaiting on-device run.",
    ]:
        require(phrase in text, "phone button docs missing: " + phrase)


def check_adb_bridge_extension() -> None:
    source = read(ADB_HELPER)
    for phrase in [
        "--prepare-phone-button-commands",
        "--check-phone-ui",
        "--push-phone-button-ui",
        "PHONE_BUTTON_UI_FILES",
        "phone_button_push_commands",
        "run_push_phone_button_ui",
        "check_phone_ui",
        "write_phone_button_push_receipt",
        "--push-phone-button-ui requires " ,
    ]:
        require(phrase in source, "ADB helper missing phone button bridge: " + phrase)
    require("setup_android_worker_alpha_termux_adb" not in source, "ADB helper must not reference duplicate hook")
    module = load_adb_helper()
    out = io.StringIO()
    err = io.StringIO()
    require(module.main(["--prepare-phone-button-commands"], stdout=out, stderr=err) == 0, "prepare-phone-button-commands failed")
    prepared = out.getvalue()
    for phrase in [
        "Nothing in --prepare-phone-button-commands is executed",
        "start_remote_worker_ui.py",
        "remote_worker_phone_ui.py",
        "EngelWorkerAlphaUI",
        "python start_remote_worker_ui.py",
    ]:
        require(phrase in prepared, "prepare phone button output missing: " + phrase)
    out = io.StringIO()
    err = io.StringIO()
    require(module.main(["--push-phone-button-ui"], stdout=out, stderr=err) == 2, "push-phone-button-ui without ack must block")
    require("--push-phone-button-ui requires --i-understand-this-uses-adb" in err.getvalue(), "push-phone-button-ui missing explicit ack block")
    push_commands = [module.command_text(command) for command in module.phone_button_push_commands()]
    require(not any("run_assigned_job.py" in command for command in push_commands), "phone button push must not run worker")
    require(not any("python start_remote_worker_ui.py" in command for command in push_commands), "phone button push must not run UI")
    require("tools\\verify_android_worker_alpha_phone_button_ui.py" in read(CODEX_VERIFY), "codex verifier script missing phone button UI verifier")


def check_no_fake_seed_files() -> None:
    queen_choices = ALPHA / "inbox" / "queen_choices"
    if queen_choices.exists():
        for child in queen_choices.iterdir():
            require(child.name == ".gitkeep", "queen choice folder must not seed fake choices: " + child.name)
    for folder_name in ["status", "outbox", "logs", "receipts"]:
        folder = ALPHA / folder_name
        require(folder.exists(), "worker folder missing: " + folder_name)
        # status/outbox/receipts: validate JSON control files only.
        # outbox may also contain candidate-output files (e.g. *_summary.md)
        # referenced from the result JSON — those are bounded candidate
        # content, not control packets, and are not validated as JSON here.
        allowed_suffix = {".log"} if folder_name == "logs" else {".json"}
        for child in folder.iterdir():
            if child.name in {".gitkeep", "__pycache__"}:
                continue
            if child.suffix.lower() not in allowed_suffix:
                continue
            validate_real_returned_worker_file(child, folder_name)


def validate_real_returned_worker_file(path: Path, folder_name: str) -> None:
    require(path.is_file(), "unexpected returned worker folder entry: " + str(path.relative_to(ALPHA)))
    require(path.name.startswith(FIRST_JOB_ID), "returned worker file must match first real job id: " + str(path.relative_to(ALPHA)))
    if folder_name == "logs":
        require(path.suffix.lower() == ".log", "returned log must be .log: " + str(path.relative_to(ALPHA)))
        require(path.read_text(encoding="utf-8", errors="replace").strip(), "returned log must be non-empty")
        return
    payload = load_json(path)
    require(payload.get("worker_id") == "android_worker_alpha", "returned file worker mismatch: " + str(path.relative_to(ALPHA)))
    require(payload.get("job_id") == FIRST_JOB_ID, "returned file job mismatch: " + str(path.relative_to(ALPHA)))
    if folder_name == "status":
        require(payload.get("real_status") is True, "returned status must be real_status")
        require(payload.get("source") == "android_worker_returned_status", "returned status source mismatch")
        require(payload.get("manual_transfer_mode") is True, "returned status must remain manual transfer")
    elif folder_name == "outbox":
        require(payload.get("real_result") is True, "returned result must be real_result")
        require(payload.get("source") == "android_worker_returned_result", "returned result source mismatch")
        require(payload.get("requires_human_review") is True, "returned result must require human review")
        for field in ["trusted_memory_write", "source_mutation", "route_mutation", "patch_apply", "provider_network", "model_runtime"]:
            require(payload.get(field) is False, "returned result must keep blocked field false: " + field)
    elif folder_name == "receipts":
        require(payload.get("candidate_outputs_only") is True, "returned receipt must remain candidate outputs only")
        require(payload.get("human_review_required") is True, "returned receipt must require human review")
        for field in ["trusted_memory_write", "source_mutation", "route_mutation", "patch_apply", "provider_network", "model_runtime"]:
            require(payload.get(field) is False, "returned receipt must keep blocked field false: " + field)


def check_report() -> None:
    require(REPORT.exists(), "phone button UI report missing")
    report = read(REPORT)
    for phrase in [
        "Engel Android Worker Alpha Phone Button UI V1",
        "files changed",
        "button/launcher implementation",
        "phone UI behavior",
        "Communication Queen choice bridge behavior",
        "bounded preapproval policy",
        "ADB bridge mode added",
        "python tools\\setup_android_worker_alpha_adb.py --push-phone-button-ui --i-understand-this-uses-adb",
        "python tools\\setup_android_worker_alpha_adb.py --check-phone-ui",
        "no duplicate ADB helper was created",
        "no app/package install occurred",
        "no worker job was run",
        "no fake status/result/progress/log/receipt was created",
        "no trusted-memory write occurred",
        "no patch apply occurred",
        "verifier results",
        "packaging skipped",
    ]:
        require(phrase.lower() in report.lower(), "report missing: " + phrase)


def main() -> int:
    checks = [
        ("files_exist", check_files_exist),
        ("python_static_safety", check_python_static_safety),
        ("phone_ui_content", check_phone_ui_content),
        ("choice_bridge_and_policy", check_choice_bridge_and_policy),
        ("contract_docs", check_contract_docs),
        ("adb_bridge_extension", check_adb_bridge_extension),
        ("no_fake_seed_files", check_no_fake_seed_files),
        ("report", check_report),
    ]
    failures: list[str] = []
    for name, fn in checks:
        try:
            fn()
            print("PASS " + name)
        except CheckFailure as exc:
            failures.append(f"{name}: {exc}")
            print("FAIL " + name + ": " + str(exc))
        except Exception as exc:
            failures.append(f"{name}: unexpected error: {exc}")
            print("FAIL " + name + ": unexpected error: " + str(exc))
    if failures:
        print("\nAndroid Worker Alpha phone button UI verifier FAILED")
        for failure in failures:
            print("- " + failure)
        return 1
    print("\nAndroid Worker Alpha phone button UI verifier PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
