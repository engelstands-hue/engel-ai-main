from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPANION = ROOT / "engel_companion.py"
UNTRUSTED_VERIFIER = ROOT / "tools" / "verify_untrusted_content_policy.py"
DE_BRUIJN_VERIFIER = ROOT / "tools" / "verify_de_bruijn_import_boundaries.py"

FEATURE_START = "# ENGEL_LOCAL_LLM_AGENT_HYBRID_MODE_V1_START"
FEATURE_END = "# ENGEL_LOCAL_LLM_AGENT_HYBRID_MODE_V1_END"

REQUIRED_SOURCE_MARKERS = {
    "voice_mode_label": "Engel Voice Mode",
    "local_engel_marker": "Local Engel",
    "agent_relay_marker": "Agent Relay",
    "hybrid_marker": "Hybrid",
    "online_fallback_off": "Online fallback: OFF",
    "local_unavailable_blocker_start": "Local Engel is selected, but no approved local model runtime is active.",
    "local_unavailable_blocker_no_fallback": "I will not fall back to Agent Relay or online models.",
    "agent_relay_label": "Agent Relay: builder/handoff mode, not local Engel mind.",
    "untrusted_builder_output": "Untrusted builder output — review before use.",
    "local_output_label": "Local conversation output — commands require approval.",
    "command_execution_off": "Command execution: OFF",
    "trusted_memory_write_off": "Trusted memory write: OFF",
    "source_mutation_off": "Source mutation: OFF",
    "agent_output_trust": "Agent output trust: untrusted until reviewed",
    "send_to_agent_relay": "Send to Agent Relay",
    "keep_local": "Keep Local",
    "cancel": "Cancel",
    "hybrid_scaffold": "Hybrid mode available as UI/status scaffold. Agent handoff requires separate implementation.",
    "chat_mode_dispatch": "return self._run_chat_for_current_voice_mode(text)",
    "voice_mode_dispatch": "reply = self._run_chat_for_current_voice_mode(transcribed)",
}

FORBIDDEN_IMPORT_ROOTS = {
    "requests",
    "httpx",
    "urllib",
    "socket",
    "websocket",
    "websockets",
    "openai",
    "anthropic",
    "google.generativeai",
}

FORBIDDEN_FEATURE_TERMS = [
    "render_engel_agent_invocation",
    "browser_ai_chat_if_connected",
    "ask_brain_provider",
    "chatgpt",
    "claude",
    "gemini",
    "openai",
    "anthropic",
    "requests.",
    "httpx.",
    "urllib.",
    "socket.",
    "websocket",
    "subprocess.",
    "Popen(",
    "start_llama_server",
    "llama-server",
    "_start_script_process",
    "write_trusted_memory",
    "trusted_memory_target",
    "append_file(",
    "write_text(",
    "apply_patch",
    "route_mutation",
    "queue_mutation",
    "source_mutation_enabled",
    "mobile_runtime_enabled = True",
    "remote_queen_runtime_enabled = True",
]


class Checks:
    def __init__(self) -> None:
        self.failures: list[str] = []

    def ok(self, name: str, detail: str = "") -> None:
        print_line("PASS", name, detail)

    def fail(self, name: str, detail: str) -> None:
        self.failures.append(name + ": " + detail)
        print_line("FAIL", name, detail)


def print_line(status: str, name: str, detail: str = "") -> None:
    if detail:
        print(status + " " + name + " " + detail)
    else:
        print(status + " " + name)


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("/", "\\")
    except ValueError:
        return str(path)


def read_text(path: Path, checks: Checks, label: str) -> str:
    if not path.exists():
        checks.fail(label + "_exists", "missing " + rel(path))
        return ""
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    except Exception as exc:
        checks.fail(label + "_readable", type(exc).__name__ + ": " + str(exc))
        return ""
    checks.ok(label + "_exists", rel(path))
    checks.ok(label + "_readable", rel(path))
    return text


def compile_and_parse(source: str, path: Path, checks: Checks, label: str) -> ast.AST | None:
    try:
        compile(source, str(path), "exec")
    except SyntaxError as exc:
        checks.fail(label + "_compiles", str(exc))
        return None
    checks.ok(label + "_compiles")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        checks.fail(label + "_ast_parse", str(exc))
        return None
    checks.ok(label + "_ast_parse")
    return tree


def import_roots(tree: ast.AST) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".", 1)[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
    return roots


def extract_feature_block(source: str, checks: Checks) -> str:
    start = source.find(FEATURE_START)
    end = source.find(FEATURE_END)
    if start < 0 or end < 0 or end <= start:
        checks.fail("feature_block_present", "ENGEL_LOCAL_LLM_AGENT_HYBRID_MODE_V1 markers missing")
        return ""
    checks.ok("feature_block_present")
    return source[start:end]


def require_markers(source: str, markers: dict[str, str], checks: Checks, label: str) -> None:
    missing = [name for name, marker in markers.items() if marker not in source]
    if missing:
        checks.fail(label, "missing " + ", ".join(missing))
    else:
        checks.ok(label)


def check_feature_block_safety(block: str, checks: Checks) -> None:
    found = [term for term in FORBIDDEN_FEATURE_TERMS if term in block]
    if found:
        checks.fail("feature_block_no_forbidden_runtime_or_mutation_behavior", ", ".join(found))
    else:
        checks.ok("feature_block_no_forbidden_runtime_or_mutation_behavior")

    if "run_offline_seed_llm_for_companion_chat" in block and "_local_engel_runtime_status() != \"available\"" in block:
        checks.ok("local_llm_call_guarded_by_runtime_status")
    else:
        checks.fail("local_llm_call_guarded_by_runtime_status", "missing Local Engel availability guard")

    if "Local Engel" in block and "Agent Relay" in block and "Hybrid" in block:
        checks.ok("three_modes_present")
    else:
        checks.fail("three_modes_present", "mode labels missing")


def check_no_forbidden_imports(tree: ast.AST | None, checks: Checks) -> None:
    if tree is None:
        return
    roots = import_roots(tree)
    forbidden = sorted(root for root in roots if root in FORBIDDEN_IMPORT_ROOTS)
    if forbidden:
        checks.fail("no_provider_network_imports_added", ", ".join(forbidden))
    else:
        checks.ok("no_provider_network_imports_added")


def run_verifier(path: Path, pass_marker: str, checks: Checks, label: str) -> None:
    if not path.exists():
        checks.fail(label + "_exists", "missing " + rel(path))
        return
    result = subprocess.run(
        [sys.executable, str(path)],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode != 0:
        details = (result.stdout + "\n" + result.stderr).strip()
        checks.fail(label + "_passes", details[-4000:])
        return
    if pass_marker not in result.stdout:
        checks.fail(label + "_passes", "missing pass marker " + pass_marker)
        return
    checks.ok(label + "_passes", pass_marker)


def main() -> int:
    print("ENGEL_LOCAL_LLM_AGENT_HYBRID_MODE_VERIFIER")
    print("ROOT " + str(ROOT))
    print("Mode: static local verification only; no GUI/provider/network/model execution")

    checks = Checks()
    source = read_text(COMPANION, checks, "companion_source")
    if source:
        tree = compile_and_parse(source, COMPANION, checks, "companion_source")
        require_markers(source, REQUIRED_SOURCE_MARKERS, checks, "hybrid_mode_markers")
        block = extract_feature_block(source, checks)
        if block:
            check_feature_block_safety(block, checks)
        check_no_forbidden_imports(tree, checks)

    run_verifier(
        UNTRUSTED_VERIFIER,
        "UNTRUSTED_CONTENT_POLICY_VERIFICATION_PASS",
        checks,
        "untrusted_content_policy_verifier",
    )
    run_verifier(
        DE_BRUIJN_VERIFIER,
        "DE_BRUIJN_IMPORT_BOUNDARY_VERIFICATION_PASS",
        checks,
        "de_bruijn_import_boundary_verifier",
    )

    if checks.failures:
        print("\nLOCAL_LLM_AGENT_HYBRID_MODE_VERIFICATION_FAIL")
        for failure in checks.failures:
            print("FAILURE " + failure)
        return 1

    print("\nLOCAL_LLM_AGENT_HYBRID_MODE_VERIFICATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
