from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUPER_SWARM_SOURCE = ROOT / "tools" / "engel_super_swarm_hive_3d_scaffold.py"
CONSUMER_VERIFIER = ROOT / "tools" / "verify_super_swarm_hive_data_consumer.py"


class CheckSet:
    def __init__(self) -> None:
        self.passes: list[str] = []
        self.failures: list[str] = []

    def ok(self, name: str) -> None:
        self.passes.append(name)
        print("PASS " + name)

    def fail(self, name: str, detail: str) -> None:
        message = name + ": " + detail
        self.failures.append(message)
        print("FAIL " + message)


def _read_source(checks: CheckSet) -> str:
    if not SUPER_SWARM_SOURCE.exists():
        checks.fail("super_swarm_source_exists", "missing " + str(SUPER_SWARM_SOURCE))
        return ""
    try:
        source = SUPER_SWARM_SOURCE.read_text(encoding="utf-8-sig", errors="replace")
    except Exception as exc:
        checks.fail("super_swarm_source_readable", type(exc).__name__ + ": " + str(exc))
        return ""
    checks.ok("super_swarm_source_exists")
    checks.ok("super_swarm_source_readable")
    return source


def _compile_source(source: str, checks: CheckSet) -> ast.AST | None:
    try:
        compile(source, str(SUPER_SWARM_SOURCE), "exec")
    except SyntaxError as exc:
        checks.fail("super_swarm_source_compiles", str(exc))
        return None
    checks.ok("super_swarm_source_compiles")
    try:
        tree = ast.parse(source, filename=str(SUPER_SWARM_SOURCE))
    except SyntaxError as exc:
        checks.fail("super_swarm_ast_parse", str(exc))
        return None
    checks.ok("super_swarm_ast_parse")
    return tree


def _theme_markers(source: str, checks: CheckSet) -> None:
    markers = {
        "theme_marker": "SUPER_SWARM_MINIMAL_TECH_THEME_MARKER",
        "theme_name": "Engel Minimal Tech Console",
        "true_data_only_marker": "SWARM_THEME_TRUE_DATA_ONLY",
        "bg_primary": "SWARM_BG_PRIMARY",
        "bg_panel": "SWARM_BG_PANEL",
        "bg_card": "SWARM_BG_CARD",
        "border_subtle": "SWARM_BORDER_SUBTLE",
        "text_primary": "SWARM_TEXT_PRIMARY",
        "text_muted": "SWARM_TEXT_MUTED",
        "accent_safe": "SWARM_ACCENT_SAFE",
        "badge_disabled": "SWARM_BADGE_DISABLED",
        "badge_warning": "SWARM_BADGE_WARNING",
        "node_focus": "SWARM_NODE_FOCUS",
        "global_stylesheet_tokens": "def global_stylesheet",
        "text_box_style_tokens": "def text_box_style",
    }
    missing = [name for name, marker in markers.items() if marker not in source]
    if missing:
        checks.fail("minimal_tech_theme_markers", "missing " + ", ".join(missing))
    else:
        checks.ok("minimal_tech_theme_markers")


def _required_behavior_markers(source: str, checks: CheckSet) -> None:
    markers = {
        "wrapper_import": "from engel_hive_data_services import build_hive_snapshot",
        "wrapper_call": "build_hive_snapshot(ROOT)",
        "communication_queen_label": "Communication Queen",
        "communication_queen_key": "communication_queen",
        "guardian_label": "Guardian",
        "guardian_key": "guardian_layer",
        "mind_summary_key": "mind_summary",
        "plan_marker": "Plan",
        "receipts_marker": "Receipts",
        "mobile_marker": "Mobile",
        "remote_queen_marker": "Remote Queen",
        "disabled_runtime_marker": "Runtime: Disabled",
        "provider_off_marker": "PROVIDER OFF",
        "no_mutation_marker": "NO MUTATION",
        "proceed_disabled_marker": "self.ai_proceed_button.setEnabled(False)",
    }
    missing = [name for name, marker in markers.items() if marker not in source]
    if missing:
        checks.fail("required_behavior_markers_preserved", "missing " + ", ".join(missing))
    else:
        checks.ok("required_behavior_markers_preserved")

    forbidden_direct_import_terms = [
        "from engel_research_office_data import build_colony_hive_snapshot",
        "import engel_research_office_data",
    ]
    found = [term for term in forbidden_direct_import_terms if term in source]
    if found:
        checks.fail("no_direct_research_office_data_import", "; ".join(found))
    else:
        checks.ok("no_direct_research_office_data_import")


def _import_checks(tree: ast.AST, checks: CheckSet) -> None:
    import_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                import_roots.add(alias.name.split(".", 1)[0])
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            import_roots.add(module.split(".", 1)[0])

    forbidden_roots = {
        "requests",
        "urllib",
        "httpx",
        "socket",
        "ollama",
        "llama_cpp",
        "transformers",
        "torch",
    }
    present = sorted(import_roots & forbidden_roots)
    if present:
        checks.fail("no_provider_network_model_imports_added", ", ".join(present))
    else:
        checks.ok("no_provider_network_model_imports_added")


def _function_block(source: str, needle: str) -> str:
    lines = source.splitlines()
    start = None
    for index, line in enumerate(lines):
        if needle in line:
            start = index
            break
    if start is None:
        return ""
    end = len(lines)
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if line.startswith("    def ") or line.startswith("def "):
            end = index
            break
    return "\n".join(lines[start:end])


def _theme_only_block(source: str) -> str:
    chunks: list[str] = []
    start_marker = "# ENGEL_SUPER_SWARM_MINIMAL_TECH_THEME_V1_START"
    end_marker = "# ENGEL_SUPER_SWARM_MINIMAL_TECH_THEME_V1_END"
    start = source.find(start_marker)
    end = source.find(end_marker)
    if start != -1 and end != -1 and end > start:
        chunks.append(source[start : end + len(end_marker)])

    for needle in [
        "def _draw_starfield",
        "def _draw_global_swarm_perimeter",
        "def _draw_colony_guardian_halos",
        "def _draw_communication_queen",
        "def _draw_remote_queens",
        "def _draw_polyline",
        "def _draw_dotted_polyline",
        "def pill",
        "def summary_card",
        "def mini_metric",
        "def detail_panel",
        "def tool_button",
        "def text_box_style",
        "def global_stylesheet",
    ]:
        block = _function_block(source, needle)
        if block:
            chunks.append(block)
    return "\n".join(chunks)


def _theme_static_safety(source: str, checks: CheckSet) -> None:
    block = _theme_only_block(source)
    if not block:
        checks.fail("theme_block_present", "theme token/method block not found")
        return
    checks.ok("theme_block_present")

    forbidden_tokens = [
        "requests",
        "urllib",
        "httpx",
        "socket",
        "ollama",
        "llama_cpp",
        "transformers",
        "torch",
        "pip ",
        "install",
        "PyInstaller",
        "build.exe",
        "write_text",
        "write_bytes",
        "register_trusted_memory",
        "TRUSTED_MEMORY",
        "setEnabled(True)",
        "route_mutation",
        "queue_mutation",
        "trusted_memory_write",
        "Popen",
        "startfile",
        "open(",
    ]
    found = [token for token in forbidden_tokens if token in block]
    if found:
        checks.fail("theme_block_no_forbidden_behavior", ", ".join(found))
    else:
        checks.ok("theme_block_no_forbidden_behavior")

    suspicious_copy = [
        "fake live",
        "fake telemetry",
        "online",
        "autonomous",
        "provider enabled",
        "network enabled",
    ]
    found_copy = [token for token in suspicious_copy if token.lower() in block.lower()]
    if found_copy:
        checks.fail("theme_block_no_fake_live_copy", ", ".join(found_copy))
    else:
        checks.ok("theme_block_no_fake_live_copy")


def _run_consumer_verifier(checks: CheckSet) -> None:
    if not CONSUMER_VERIFIER.exists():
        checks.fail("super_swarm_consumer_verifier_exists", "missing " + str(CONSUMER_VERIFIER))
        return
    result = subprocess.run(
        [sys.executable, str(CONSUMER_VERIFIER)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode == 0:
        checks.ok("super_swarm_hive_data_consumer_verifier_passes")
    else:
        detail = (result.stdout + "\n" + result.stderr).strip()
        checks.fail("super_swarm_hive_data_consumer_verifier_passes", detail[-1000:])


def main() -> int:
    checks = CheckSet()
    source = _read_source(checks)
    tree = None
    if source:
        tree = _compile_source(source, checks)
        _theme_markers(source, checks)
        _required_behavior_markers(source, checks)
        _theme_static_safety(source, checks)
    if tree is not None:
        _import_checks(tree, checks)
    _run_consumer_verifier(checks)

    if checks.failures:
        print()
        print("SUPER_SWARM_MINIMAL_TECH_THEME_VERIFICATION_FAIL")
        for failure in checks.failures:
            print("- " + failure)
        return 1
    print()
    print("SUPER_SWARM_MINIMAL_TECH_THEME_VERIFICATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
