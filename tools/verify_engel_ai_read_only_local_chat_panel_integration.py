from __future__ import annotations

import ast
from pathlib import Path
import py_compile
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
GUI_HOST = ROOT / "engel_companion.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_AI_READ_ONLY_LOCAL_CHAT_PANEL_INTEGRATION_V1.md"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"
BOUNDED_SMOKE_MODULE = ROOT / "engel_ai_bounded_local_chat_smoke.py"
BOUNDED_SMOKE_VERIFIER = ROOT / "tools" / "verify_engel_ai_bounded_local_chat_smoke.py"

FILTER_TUNING_VERIFIER = ROOT / "tools" / "verify_engel_ai_first_response_output_filter_tuning.py"
EXIT_FIX_VERIFIER = ROOT / "tools" / "verify_engel_ai_first_local_response_smoke_exit_fix.py"
FIRST_SMOKE_VERIFIER = ROOT / "tools" / "verify_engel_ai_first_local_response_smoke.py"
SWAP_APPROVAL_VERIFIER = ROOT / "tools" / "verify_engel_ai_llama_cpp_runtime_swap_approval.py"
MEMORY_ROOTS_VERIFIER = ROOT / "tools" / "verify_engel_memory_roots_storage_layout.py"
READINESS_VERIFIER = ROOT / "tools" / "verify_engel_ai_runtime_readiness.py"


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


def run_command(args: list[str], timeout: int = 240) -> str:
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
    require(result.returncode == 0, "command failed: " + " ".join(args) + "\n" + (result.stdout + result.stderr)[-1200:])
    return result.stdout + result.stderr


def check_files_and_compile() -> None:
    for path in [GUI_HOST, REPORT, COMMANDS, CODEX_VERIFY, FILTER_TUNING_VERIFIER, EXIT_FIX_VERIFIER, FIRST_SMOKE_VERIFIER, SWAP_APPROVAL_VERIFIER, MEMORY_ROOTS_VERIFIER, READINESS_VERIFIER]:
        require(path.exists(), "missing required path: " + str(path.relative_to(ROOT)))
    run_command([sys.executable, "-m", "py_compile", str(GUI_HOST)], timeout=120)
    run_command([sys.executable, "-m", "py_compile", str(Path(__file__))], timeout=120)


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
        "UNTRUSTED LOCAL MODEL OUTPUT",
        "Trusted memory writes: disabled",
        "Persistent chat: disabled",
        "Server mode: disabled",
        "Provider/cloud: disabled",
        "build_read_only_local_chat_panel_status",
        "render_read_only_local_chat_panel_status",
        "read_only_local_chat_panel_version",
        "runtime_binary_present",
        "model_key",
        "tiny_seed",
        "first_local_response_smoke_passed",
        "first_response_output_filter_tuning_passed",
        "bounded_local_chat_smoke_present",
        "bounded_local_chat_smoke_passed",
        "output_marked_untrusted",
        "model_output_trusted",
        "trusted_memory_write_enabled",
        "persistent_chat_loop_enabled",
        "server_enabled",
        "provider_api_enabled",
        "chat_enabled",
        "runtime_ready_for_inference",
        "gui_runtime_execution_enabled",
        "NO MODEL RUN ON OPEN/REFRESH",
        "Local AI",
        "Refresh Local AI Status",
        "Open Latest Receipt",
        "Copy CLI Command",
        "Run One Bounded Local Chat Smoke",
        "setEnabled(False)",
        "one-time approval token",
        "python engel_ai_bounded_local_chat_smoke.py run --approval <APPROVAL_TOKEN>",
    ]:
        require(needle in source, "GUI host missing required text: " + needle)

    require("self.ai_audit_tabs.addTab(self.local_ai_read_only_panel, \"Local AI\")" in source, "Local AI tab is not merged into existing Companion tab host")
    require("QApplication(" not in combined, "panel section must not create a standalone QApplication")
    require("QMainWindow" not in combined, "panel section must not create a standalone window")
    require("QDialog" not in combined, "panel section must not create a token dialog")

    for forbidden in [
        "APPROVE_BOUNDED_LOCAL_CHAT_SMOKE",
        "subprocess",
        "Popen",
        ".run(",
        "os.system",
        "startfile",
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
        "chat_enabled\": True",
        "server_enabled\": True",
        "persistent_chat_loop_enabled\": True",
        "gui_runtime_execution_enabled\": True",
    ]:
        require(forbidden.lower() not in combined.lower(), "panel section contains forbidden behavior/text: " + forbidden)

    require(".clicked.connect(self.refresh_local_ai_read_only_panel)" in panel_section, "refresh button is not wired")
    require(".clicked.connect(self.open_latest_local_ai_receipt)" in panel_section, "open receipt button is not wired")
    require(".clicked.connect(self.copy_local_ai_cli_command)" in panel_section, "copy CLI button is not wired")
    if "local_ai_run_button.clicked.connect" in panel_section:
        require("run_local_ai_bounded_smoke_from_panel" in panel_section, "run button must call the bounded smoke panel handler")
        require("local_ai_approval_input.clear()" in panel_section, "approval token input must be cleared")
        require("run_chat_smoke(approval)" in panel_section, "GUI must delegate to existing bounded smoke module")
    else:
        require("local_ai_run_button.setEnabled(False)" in panel_section, "unwired run button must remain disabled")


def check_docs_and_report() -> None:
    commands = read(COMMANDS)
    require("companion local ai read-only smoke panel" in commands, "command docs missing Companion local AI panel entry")
    require("UNTRUSTED" in commands, "command docs missing untrusted output boundary")
    codex = read(CODEX_VERIFY)
    require("tools\\verify_engel_ai_read_only_local_chat_panel_integration.py" in codex, "codex verify missing panel verifier")
    report = read(REPORT)
    for needle in [
        "ENGEL_AI_READ_ONLY_LOCAL_CHAT_PANEL_INTEGRATION_V1",
        "Integrated host: `engel_companion.py`",
        "Existing surface used: Companion right-column `QTabWidget`",
        "Panel title: `Engel Local AI — Read-Only Smoke Panel`",
        "Standalone GUI created: `False`",
        "Bounded local chat smoke module: missing in this phase",
        "UNTRUSTED LOCAL MODEL OUTPUT",
        "Runtime execution on GUI open: `False`",
        "Runtime execution on refresh: `False`",
        "Trusted memory write: `False`",
        "Full Codex verifier result",
        "Packaging skipped",
    ]:
        require(needle in report, "report missing required text: " + needle)


def check_optional_bounded_smoke_dependency() -> None:
    if BOUNDED_SMOKE_MODULE.exists():
        require(BOUNDED_SMOKE_VERIFIER.exists(), "bounded smoke module exists but verifier is missing")
        run_command([sys.executable, "-m", "py_compile", str(BOUNDED_SMOKE_MODULE)], timeout=120)
        run_command([sys.executable, "-m", "py_compile", str(BOUNDED_SMOKE_VERIFIER)], timeout=120)
    else:
        source = read(GUI_HOST)
        require("bounded_local_chat_smoke_present" in source, "panel must report missing bounded smoke module")
        require("Run ENGEL_AI_BOUNDED_LOCAL_CHAT_SMOKE_V1 first." in source, "panel must fail closed when bounded smoke module is missing")


def check_downstream_verifiers() -> None:
    for verifier in [
        FILTER_TUNING_VERIFIER,
        EXIT_FIX_VERIFIER,
        FIRST_SMOKE_VERIFIER,
        SWAP_APPROVAL_VERIFIER,
        MEMORY_ROOTS_VERIFIER,
        READINESS_VERIFIER,
    ]:
        py_compile.compile(str(verifier), doraise=True)


def main() -> int:
    try:
        check_files_and_compile()
        check_gui_static_contract()
        check_docs_and_report()
        check_optional_bounded_smoke_dependency()
        check_downstream_verifiers()
    except CheckFailure as exc:
        print("ENGEL_AI_READ_ONLY_LOCAL_CHAT_PANEL_INTEGRATION_VERIFY_FAIL")
        print(str(exc))
        return 1
    print("ENGEL_AI_READ_ONLY_LOCAL_CHAT_PANEL_INTEGRATION_VERIFY_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
