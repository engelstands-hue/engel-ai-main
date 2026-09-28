from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPANION_PATH = ROOT / "engel_companion.py"
CONSUMER_VERIFIER_PATH = ROOT / "tools" / "verify_companion_hive_summary_consumer.py"


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
    if not COMPANION_PATH.exists():
        checks.fail("companion_source_exists", "missing " + str(COMPANION_PATH))
        return ""
    try:
        source = COMPANION_PATH.read_text(encoding="utf-8-sig", errors="replace")
    except Exception as exc:
        checks.fail("companion_source_readable", type(exc).__name__ + ": " + str(exc))
        return ""
    checks.ok("companion_source_exists")
    checks.ok("companion_source_readable")
    return source


def _compile_source(source: str, checks: CheckSet) -> ast.AST | None:
    try:
        compile(source, str(COMPANION_PATH), "exec")
    except SyntaxError as exc:
        checks.fail("companion_source_compiles", str(exc))
        return None
    checks.ok("companion_source_compiles")
    try:
        tree = ast.parse(source, filename=str(COMPANION_PATH))
    except SyntaxError as exc:
        checks.fail("companion_ast_parse", str(exc))
        return None
    checks.ok("companion_ast_parse")
    return tree


def _theme_markers(source: str, checks: CheckSet) -> None:
    markers = {
        "theme_marker": "COMPANION_MINIMAL_TECH_THEME_MARKER",
        "theme_name": "Engel Minimal Tech Console",
        "bg_primary": "COMPANION_BG_PRIMARY",
        "bg_panel": "COMPANION_BG_PANEL",
        "bg_card": "COMPANION_BG_CARD",
        "border_subtle": "COMPANION_BORDER_SUBTLE",
        "text_primary": "COMPANION_TEXT_PRIMARY",
        "badge_disabled": "COMPANION_BADGE_DISABLED",
        "badge_active": "COMPANION_BADGE_ACTIVE",
        "badge_warning": "COMPANION_BADGE_WARNING",
        "accent_safe": "COMPANION_ACCENT_SAFE",
        "minimal_toggle_stylesheet": "def _companion_minimal_toggle_stylesheet",
        "minimal_tab_stylesheet": "def _companion_minimal_tab_stylesheet",
        "minimal_panel_stylesheet": "def _companion_minimal_panel_stylesheet",
    }
    missing = [name for name, marker in markers.items() if marker not in source]
    if missing:
        checks.fail("minimal_tech_theme_markers", "missing " + ", ".join(missing))
    else:
        checks.ok("minimal_tech_theme_markers")


def _required_behavior_markers(source: str, checks: CheckSet) -> None:
    markers = {
        "open_colony_hive_gui": "def open_colony_hive_gui",
        "engel_colony_hive_window": "EngelColonyHiveWindow",
        "hive_status_card": "CompanionHiveStatusCard",
        "hive_summary_helper": "build_companion_hive_summary",
        "hive_launcher_button": "self.research_office_button = QPushButton(\"Hive\"",
        "hive_launcher_connection": "self.research_office_button.clicked.connect(self.open_colony_hive_gui)",
        "code_companion_button": "self.code_companion_button = QPushButton(\"Code\"",
        "code_companion_launcher": "self.code_companion_button.clicked.connect(self.open_code_companion)",
        "ai_plan_tab": "self.ai_audit_tabs.addTab(self.ai_plan_panel, \"PLAN\")",
        "ai_receipts_tab": "self.ai_audit_tabs.addTab(self.ai_receipt_viewer_panel, \"RECEIPTS\")",
        "mobile_tab": "self.ai_audit_tabs.addTab(self.mobile_connection_panel, \"MOBILE\")",
        "mobile_toggle": "self.mobile_toggle.toggled.connect(self.toggle_mobile_session_button)",
        "protected_action_registry": "protected_action_registry",
        "global_password_gate": "global_password_gate",
        "disabled_runtime_text": "Runtime: Disabled",
    }
    missing = [name for name, marker in markers.items() if marker not in source]
    if missing:
        checks.fail("required_behavior_markers_preserved", "missing " + ", ".join(missing))
    else:
        checks.ok("required_behavior_markers_preserved")


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


def _theme_only_block(source: str) -> str:
    chunks: list[str] = []
    start_marker = "# ENGEL_COMPANION_MINIMAL_TECH_THEME_V1_START"
    end_marker = "# ENGEL_COMPANION_MINIMAL_TECH_THEME_V1_END"
    start = source.find(start_marker)
    end = source.find(end_marker)
    if start != -1 and end != -1 and end > start:
        chunks.append(source[start : end + len(end_marker)])

    lines = source.splitlines()
    needles = [
        "def _companion_minimal_toggle_stylesheet",
        "def _companion_minimal_open_host_stylesheet",
        "def _companion_minimal_right_col_stylesheet",
        "def _companion_minimal_tab_stylesheet",
        "def _companion_minimal_panel_stylesheet",
    ]
    for needle in needles:
        start_index = None
        for index, line in enumerate(lines):
            if needle in line:
                start_index = index
                break
        if start_index is None:
            continue
        end_index = len(lines)
        for index in range(start_index + 1, len(lines)):
            if lines[index].startswith("    def "):
                end_index = index
                break
        chunks.append("\n".join(lines[start_index:end_index]))
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
        "subprocess",
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
        "Popen",
        "startfile",
        "open(",
    ]
    found = [token for token in forbidden_tokens if token in block]
    if found:
        checks.fail("theme_block_no_forbidden_behavior", ", ".join(found))
    else:
        checks.ok("theme_block_no_forbidden_behavior")


def _run_consumer_verifier(checks: CheckSet) -> None:
    if not CONSUMER_VERIFIER_PATH.exists():
        checks.fail("companion_hive_summary_consumer_verifier_exists", "missing " + str(CONSUMER_VERIFIER_PATH))
        return
    result = subprocess.run(
        [sys.executable, str(CONSUMER_VERIFIER_PATH)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode == 0:
        checks.ok("companion_hive_summary_consumer_verifier_passes")
    else:
        detail = (result.stdout + "\n" + result.stderr).strip()
        checks.fail("companion_hive_summary_consumer_verifier_passes", detail[-800:])


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
        print("COMPANION_MINIMAL_TECH_THEME_VERIFICATION_FAIL")
        for failure in checks.failures:
            print("- " + failure)
        return 1
    print()
    print("COMPANION_MINIMAL_TECH_THEME_VERIFICATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
