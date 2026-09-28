from __future__ import annotations

import subprocess
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import engel_codex_cli_bridge_http_service as bridge  # noqa: E402
import engel_claude_cli_bridge_http_service as claude_bridge  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    original_exe = bridge._codex_exe_path
    original_process_runner = bridge._run_codex_process
    original_output = bridge.OUTPUT_DIR
    original_workspace = bridge.CHAT_WORKSPACE
    original_claude_exe = claude_bridge.CLAUDE_EXE
    try:
        with tempfile.TemporaryDirectory(prefix="engel-codex-timeout-") as temp:
            root = Path(temp)
            exe = root / "codex.exe"
            exe.write_bytes(b"test")
            bridge._codex_exe_path = lambda: exe
            bridge.OUTPUT_DIR = root / "output"
            bridge.CHAT_WORKSPACE = root / "workspace"

            def complete_timeout(args, **_kwargs):
                output_path = Path(args[args.index("--output-last-message") + 1])
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(
                    "FILE: main.py\n```python\nprint('repaired')\n```",
                    encoding="utf-8",
                )
                return {
                    "timed_out": True,
                    "returncode": 1,
                    "stdout": "",
                    "stderr": "",
                    "process_pid": 1234,
                    "process_tree_terminated": True,
                }

            bridge._run_codex_process = complete_timeout
            result = bridge._run_codex("repair it", {}, time.perf_counter())
            require(result.get("ok") is True, "complete timeout output was discarded")
            require(result.get("timed_out") is True, "salvage lost timeout evidence")
            require(
                result.get("process_tree_terminated") is True,
                "timeout salvage lost process-tree cleanup evidence",
            )
            require("FILE: main.py" in str(result.get("assistant_reply") or ""), "salvaged reply missing")

            def incomplete_timeout(args, **_kwargs):
                output_path = Path(args[args.index("--output-last-message") + 1])
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text("FILE: main.py\n```python\nprint('partial')", encoding="utf-8")
                return {
                    "timed_out": True,
                    "returncode": 1,
                    "stdout": "",
                    "stderr": "",
                    "process_pid": 1235,
                    "process_tree_terminated": True,
                }

            bridge._run_codex_process = incomplete_timeout
            rejected = bridge._run_codex("repair it", {}, time.perf_counter())
            require(rejected.get("ok") is False, "incomplete timeout output was accepted")
            require(
                rejected.get("process_tree_terminated") is True,
                "rejected timeout lost process-tree cleanup evidence",
            )

        bridge_source = (
            TOOLS / "engel_codex_cli_bridge_http_service.py"
        ).read_text(encoding="utf-8")
        require(
            '["taskkill", "/PID", str(process.pid), "/T", "/F"]' in bridge_source,
            "Windows Codex timeout does not terminate the full process tree",
        )
        require(
            'request.get("artifact_only") is True' in bridge_source
            and "bounded artifact generator" in bridge_source
            and "filesystem, repository, git state" in bridge_source,
            "artifact-only Codex generation is not isolated from repository inspection",
        )
        server_source = (
            TOOLS / "engel_main_server_chat_http_service.py"
        ).read_text(encoding="utf-8")
        require(
            '"artifact_only": True' in server_source,
            "CT246 build generation does not request artifact-only Codex mode",
        )
        require(
            '"file_marker_count"' in server_source and '"fence_count"' in server_source,
            "failed local build drafts lack structural diagnostics",
        )

        gemini_source = (TOOLS / "engel_gemini_api_bridge_http_service.py").read_text(encoding="utf-8")
        require('"attempts": result.get("attempts", [])' in gemini_source, "Gemini attempts absent from receipts")
        require('"error": result.get("error", "")' in gemini_source, "Gemini error absent from receipts")
        with tempfile.TemporaryDirectory(prefix="engel-claude-direct-") as temp:
            root = Path(temp)
            shim = root / "claude.cmd"
            direct = root / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
            shim.write_text("@echo off\n", encoding="ascii")
            direct.parent.mkdir(parents=True)
            direct.write_bytes(b"test")
            claude_bridge.CLAUDE_EXE = shim
            require(claude_bridge._claude_exe_path() == direct, "Claude bridge kept the cmd wrapper")
        print("PASS: Codex timeout salvage is guarded; Gemini failures are observable; Claude uses its direct executable")
        return 0
    finally:
        bridge._codex_exe_path = original_exe
        bridge._run_codex_process = original_process_runner
        bridge.OUTPUT_DIR = original_output
        bridge.CHAT_WORKSPACE = original_workspace
        claude_bridge.CLAUDE_EXE = original_claude_exe


if __name__ == "__main__":
    raise SystemExit(main())
