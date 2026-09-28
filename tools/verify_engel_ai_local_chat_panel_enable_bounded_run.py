from __future__ import annotations

import ast
from pathlib import Path
import py_compile
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
GUI_HOST = ROOT / "engel_companion.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_AI_LOCAL_CHAT_PANEL_ENABLE_BOUNDED_RUN_V1.md"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"
READINESS = ROOT / "engel_ai_runtime_readiness.py"
VERIFIER = ROOT / "tools" / "verify_engel_ai_local_chat_panel_enable_bounded_run.py"

BOUNDED_SMOKE_MODULE = ROOT / "engel_ai_bounded_local_chat_smoke.py"
BOUNDED_SMOKE_VERIFIER = ROOT / "tools" / "verify_engel_ai_bounded_local_chat_smoke.py"
READ_ONLY_PANEL_VERIFIER = ROOT / "tools" / "verify_engel_ai_read_only_local_chat_panel_integration.py"
FILTER_TUNING_VERIFIER = ROOT / "tools" / "verify_engel_ai_first_response_output_filter_tuning.py"
EXIT_FIX_VERIFIER = ROOT / "tools" / "verify_engel_ai_first_local_response_smoke_exit_fix.py"
FIRST_SMOKE_VERIFIER = ROOT / "tools" / "verify_engel_ai_first_local_response_smoke.py"
SWAP_APPROVAL_VERIFIER = ROOT / "tools" / "verify_engel_ai_llama_cpp_runtime_swap_approval.py"
MEMORY_ROOTS_VERIFIER = ROOT / "tools" / "verify_engel_memory_roots_storage_layout.py"
READINESS_VERIFIER = ROOT / "tools" / "verify_engel_ai_runtime_readiness.py"

CHAIN_VERIFIERS = [
    BOUNDED_SMOKE_VERIFIER,
    READ_ONLY_PANEL_VERIFIER,
    FILTER_TUNING_VERIFIER,
    EXIT_FIX_VERIFIER,
    FIRST_SMOKE_VERIFIER,
    SWAP_APPROVAL_VERIFIER,
    MEMORY_ROOTS_VERIFIER,
    READINESS_VERIFIER,
]


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")


def section(source: str, start: str, end: str) -> str:
    require(start in source, "missing section start: " + start)
    require(end in source, "missing section end: " + end)
    return source.split(start, 1)[1].split(end, 1)[0]


def run_command(args: list[str], timeout: int = 420) -> str:
    result = subprocess.run(
        args,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
        timeout=timeout,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    require(result.returncode == 0, "command failed: " + " ".join(args) + "\n" + (result.stdout + result.stderr)[-1600:])
    return result.stdout + result.stderr


def check_files_and_compile() -> None:
    for path in [GUI_HOST, REPORT, COMMANDS, CODEX_VERIFY, READINESS, VERIFIER, BOUNDED_SMOKE_MODULE, *CHAIN_VERIFIERS]:
        require(path.exists(), "missing required path: " + str(path.relative_to(ROOT)))
    run_command([sys.executable, "-m", "py_compile", str(GUI_HOST)], timeout=120)
    run_command([sys.executable, "-m", "py_compile", str(VERIFIER)], timeout=120)


def check_gui_static_contract() -> None:
    source = read(GUI_HOST)
    ast.parse(source)
    helper_section = section(
        source,
        "# ENGEL_AI_READ_ONLY_LOCAL_CHAT_PANEL_INTEGRATION_V1_START",
        "# ENGEL_AI_READ_ONLY_LOCAL_CHAT_PANEL_INTEGRATION_V1_END",
    )
    panel_section = section(
        source,
        "# ENGEL_AI_READ_ONLY_LOCAL_CHAT_PANEL_INTEGRATION_V1_PANEL_START",
        "# ENGEL_AI_READ_ONLY_LOCAL_CHAT_PANEL_INTEGRATION_V1_PANEL_END",
    )
    supervised_start = panel_section.find("Engel Local AI — Supervised Open Chat")
    bounded_panel_section = panel_section[:supervised_start] if supervised_start != -1 else panel_section
    combined = helper_section + "\n" + bounded_panel_section

    for needle in [
        "Engel Local AI",
        "Engel Local AI — Bounded Run",
        "UNTRUSTED LOCAL MODEL OUTPUT",
        "Bounded local chat smoke",
        "Trusted memory writes: disabled",
        "Persistent chat: disabled",
        "Server mode: disabled",
        "Provider/cloud: disabled",
        "Open chat: disabled",
        "Runtime ready for inference: false",
        "local_ai_approval_input",
        "setClearButtonEnabled(True)",
        "one-time approval token",
        "local_ai_run_button.clicked.connect(self.run_local_ai_bounded_smoke_from_panel)",
        "def run_local_ai_bounded_smoke_from_panel",
        "run_chat_smoke(approval)",
        "local_ai_approval_input.clear()",
        "approval = \"\"",
        "gui_runtime_execution_enabled",
        "runtime_process_running",
        "approval_token_stored",
        "model_output_trusted",
        "runtime_ready_for_inference",
        "open_chat_enabled",
        "copy_cli_command",
    ]:
        require(needle in source, "GUI source missing required text: " + needle)

    require("self.ai_audit_tabs.addTab(self.local_ai_read_only_panel, \"Local AI\")" in source, "Local AI tab is not merged into the existing Companion tab host")
    require("QApplication(" not in combined, "panel section must not create a standalone application")
    require("QDialog" not in combined, "panel section must not create a token dialog")
    require("QInputDialog" not in combined, "panel should use the visible one-time field, not a dialog")
    require("APPROVE_BOUNDED_LOCAL_CHAT_SMOKE" not in combined, "GUI helper/panel section must not store the raw approval token")
    require("approval_token_verified" in panel_section, "GUI result summary must show approval verification without storing the raw token")

    for forbidden in [
        "subprocess",
        "Popen",
        "shell=True",
        "llama-server.exe",
        "rpc-server.exe",
        "ollama",
        "requests",
        "urllib",
        "webbrowser",
        "openai",
        "anthropic",
        "wsl",
        "docker",
        "hermes",
        "write_trusted_memory",
        "trusted_memory_write_enabled\": True",
        "model_output_trusted\": True",
        "runtime_ready_for_inference\": True",
        "open_chat_enabled\": True",
        "chat_enabled\": True",
        "server_enabled\": True",
        "persistent_chat_loop_enabled\": True",
    ]:
        require(forbidden.lower() not in combined.lower(), "GUI panel contains forbidden behavior/text: " + forbidden)


def check_docs_report_readiness() -> None:
    commands = read(COMMANDS)
    for needle in [
        "companion local ai bounded run panel",
        "one visible one-time approval token",
        "clears the token after use",
        "open chat, persistent chat, server, provider/cloud, runtime_ready_for_inference, and trusted-memory writes disabled",
    ]:
        require(needle in commands, "command docs missing: " + needle)

    codex = read(CODEX_VERIFY)
    require("tools\\verify_engel_ai_local_chat_panel_enable_bounded_run.py" in codex, "codex verify missing new panel run verifier")

    readiness = read(READINESS)
    for needle in [
        "LOCAL_CHAT_PANEL_ENABLE_REPORT",
        "local_chat_panel_bounded_run_enabled",
        "ENGEL_AI_LOCAL_CHAT_PANEL_BOUNDED_RUN_READY",
        "open_chat_enabled",
        "runtime_ready_for_inference",
    ]:
        require(needle in readiness, "readiness missing: " + needle)

    report = read(REPORT)
    for needle in [
        "ENGEL_AI_LOCAL_CHAT_PANEL_ENABLE_BOUNDED_RUN_V1",
        "GUI host: `engel_companion.py`",
        "Panel title: `Engel Local AI — Bounded Run`",
        "Raw approval token stored: `False`",
        "Token clears after use: `True`",
        "Execution delegates to: `engel_ai_bounded_local_chat_smoke.run_chat_smoke(approval)`",
        "UNTRUSTED LOCAL MODEL OUTPUT",
        "runtime_ready_for_inference: `False`",
        "open_chat_enabled: `False`",
        "persistent_chat_loop_enabled: `False`",
        "Packaging skipped",
    ]:
        require(needle in report, "report missing: " + needle)


def check_chain_verifiers() -> None:
    for verifier in CHAIN_VERIFIERS:
        py_compile.compile(str(verifier), doraise=True)


def main() -> int:
    try:
        check_files_and_compile()
        check_gui_static_contract()
        check_docs_report_readiness()
        check_chain_verifiers()
    except CheckFailure as exc:
        print("ENGEL_AI_LOCAL_CHAT_PANEL_ENABLE_BOUNDED_RUN_VERIFY_FAIL")
        print(str(exc))
        return 1
    print("ENGEL_AI_LOCAL_CHAT_PANEL_ENABLE_BOUNDED_RUN_VERIFY_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
