from __future__ import annotations

import ast
import sys
from pathlib import Path


_file = globals().get("__file__")
if not _file or not isinstance(_file, str) or _file.startswith("<"):
    ROOT = Path.cwd()
else:
    try:
        ROOT = Path(_file).resolve().parents[1]
    except (OSError, ValueError, IndexError):
        ROOT = Path.cwd()

TOOLS_ROOT = ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

HELPER_PATH = TOOLS_ROOT / "engel_model_library_presence_status.py"

from engel_model_library_presence_status import (  # noqa: E402
    collect_model_presence_statuses,
    model_status_by_role,
    render_model_presence_status,
)


class CheckFailure(Exception):
    pass


def _read(path: Path) -> str:
    if not path.exists():
        raise CheckFailure("missing required file: " + str(path))
    return path.read_text(encoding="utf-8", errors="replace")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def _assert_static_helper() -> None:
    source = _read(HELPER_PATH)
    tree = ast.parse(source)
    blocked_imports = {
        "requests",
        "socket",
        "subprocess",
        "threading",
        "multiprocessing",
        "urllib",
        "webbrowser",
        "openai",
        "anthropic",
        "llama_cpp",
        "ollama",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                _require(alias.name.split(".")[0] not in blocked_imports, "helper imports blocked module: " + alias.name)
        elif isinstance(node, ast.ImportFrom):
            _require((node.module or "").split(".")[0] not in blocked_imports, "helper imports blocked module: " + str(node.module))
    for forbidden in [
        ".rglob(",
        "os.walk",
        "**",
        "requests.",
        "http://",
        "https://",
        "socket",
        "subprocess",
        "Start-Process",
        "llama_cpp",
        "ollama",
        "from llama_cpp",
    ]:
        _require(forbidden not in source, "helper contains forbidden pattern: " + forbidden)
    for required in [
        "MAX_RECORDED_FILES_PER_MODEL",
        "expected_local_folder",
        "expected_file_pattern",
        "expected_files",
        "split_file_set_required",
        "merged_file_required",
        "retained_split_files",
        "NOT_LOADED",
        "NOT_RUNTIME",
        "MERGED",
        "BLOCKED / NOT_PERFORMED",
        "def collect_model_presence_statuses",
        "def render_model_presence_status",
    ]:
        _require(required in source, "helper missing required text: " + required)


def _assert_statuses() -> None:
    statuses = collect_model_presence_statuses()
    _require(len(statuses) == 4, "expected four model statuses")
    roles = {status.role for status in statuses}
    for role in {"tiny_seed_mode", "daily_local_mode", "research_worker_mode", "alternative_research_worker"}:
        _require(role in roles, "missing role: " + role)
    by_role = model_status_by_role(statuses)
    expected_statuses = {
        "tiny_seed_mode": "PRESENT / NOT_LOADED / NOT_RUNTIME",
        "daily_local_mode": "PRESENT / NOT_LOADED / NOT_RUNTIME",
        "research_worker_mode": "PRESENT / MERGED / NOT_LOADED / NOT_RUNTIME",
        "alternative_research_worker": "PRESENT / NOT_LOADED / NOT_RUNTIME",
    }
    for role, expected_status in expected_statuses.items():
        _require(by_role[role].status == expected_status, "unexpected status for " + role + ": " + by_role[role].status)
    for status in statuses:
        _require(status.status in {
            "PRESENT / NOT_LOADED / NOT_RUNTIME",
            "MISSING / NOT_LOADED / NOT_RUNTIME",
            "UNKNOWN / NOT_LOADED / NOT_RUNTIME",
            "SPLIT_PRESENT / NOT_MERGED / NOT_LOADED / NOT_RUNTIME",
            "SPLIT_PARTIAL / NOT_MERGED / NOT_LOADED / NOT_RUNTIME",
            "MISSING / NOT_MERGED / NOT_LOADED / NOT_RUNTIME",
            "PRESENT / MERGED / NOT_LOADED / NOT_RUNTIME",
            "MISSING / MERGED_FILE_NOT_FOUND / NOT_LOADED / NOT_RUNTIME",
        }, "unexpected status: " + status.status)
        _require(status.loaded_status == "NOT_LOADED", "loaded status must be NOT_LOADED")
        _require(status.runtime_status == "NOT_RUNTIME", "runtime status must be NOT_RUNTIME")
        _require(status.trusted_memory_write == "BLOCKED / NOT_PERFORMED", "trusted memory write boundary mismatch")
        _require(status.network_download == "BLOCKED / NOT_PERFORMED", "network/download boundary mismatch")
        _require(status.inference == "DISABLED / NOT_PERFORMED", "inference boundary mismatch")
        _require(status.expected_file_pattern == "*.gguf", "presence helper should only check .gguf pattern")
        _require(status.expected_files, "presence helper should track exact expected files")
        _require(status.detected_file_count_bounded <= 5, "detected file list must be bounded")
    research_worker = by_role["research_worker_mode"]
    _require(research_worker.split_file_set_required is False, "Qwen 7B should use merged primary file now")
    _require(research_worker.merged_file_required is True, "Qwen 7B should require merged file")
    _require(research_worker.merge_status == "MERGED", "Qwen 7B should report merged shelf file")
    _require(research_worker.detected_file_count_bounded == 1, "Qwen 7B should detect exactly one merged shelf file")
    _require(research_worker.detected_retained_split_files_bounded == (
        "qwen2.5-7b-instruct-q5_k_m-00001-of-00002.gguf",
        "qwen2.5-7b-instruct-q5_k_m-00002-of-00002.gguf",
    ), "Qwen 7B retained split files should still be detected")
    for role in ["tiny_seed_mode", "daily_local_mode", "alternative_research_worker"]:
        _require(by_role[role].split_file_set_required is False, role + " should not require split files")
        _require(by_role[role].merged_file_required is False, role + " should not require merged file")
        _require(by_role[role].detected_file_count_bounded == 1, role + " should detect exactly one shelf file")
    rendered = render_model_presence_status(statuses)
    for phrase in [
        "MODEL_LIBRARY_PRESENCE_STATUS / READ_ONLY / NOT_LOADED / NOT_RUNTIME",
        "Manual model file presence does not enable model runtime.",
        "does not download, load, infer, call APIs/network, write trusted memory",
        "PRESENT / MERGED / NOT_LOADED / NOT_RUNTIME",
        "retained split files",
        "NOT_LOADED",
        "NOT_RUNTIME",
    ]:
        _require(phrase in rendered, "rendered status missing phrase: " + phrase)


def main() -> int:
    _assert_static_helper()
    _assert_statuses()
    print("PASS: Engel Model Library Presence Status verifier")
    print("- helper checks only expected model folders from the plan")
    print("- model presence remains NOT_LOADED / NOT_RUNTIME")
    print("- no network, download, runtime, inference, recursive scan, or trusted-memory behavior is present")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CheckFailure as exc:
        print("FAIL: " + str(exc), file=sys.stderr)
        raise SystemExit(1)
