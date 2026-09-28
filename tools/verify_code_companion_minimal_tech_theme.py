from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE_COMPANION_PATH = ROOT / "engel_code_companion.py"
COMPANION_PATH = ROOT / "engel_companion.py"
BASE_VERIFIER_PATH = ROOT / "tools" / "verify_engel_code_companion.py"


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


def _read(path: Path, label: str, checks: CheckSet) -> str:
    if not path.exists():
        checks.fail(label + "_exists", "missing " + str(path))
        return ""
    try:
        source = path.read_text(encoding="utf-8-sig", errors="replace")
    except Exception as exc:
        checks.fail(label + "_readable", type(exc).__name__ + ": " + str(exc))
        return ""
    checks.ok(label + "_exists")
    checks.ok(label + "_readable")
    return source


def _compile_source(source: str, checks: CheckSet) -> ast.AST | None:
    try:
        compile(source, str(CODE_COMPANION_PATH), "exec")
    except SyntaxError as exc:
        checks.fail("code_companion_source_compiles", str(exc))
        return None
    checks.ok("code_companion_source_compiles")
    try:
        tree = ast.parse(source, filename=str(CODE_COMPANION_PATH))
    except SyntaxError as exc:
        checks.fail("code_companion_ast_parse", str(exc))
        return None
    checks.ok("code_companion_ast_parse")
    return tree


def _theme_markers(source: str, checks: CheckSet) -> None:
    markers = {
        "theme_marker": "CODE_COMPANION_MINIMAL_TECH_THEME_MARKER",
        "theme_name": "Engel Minimal Tech Console",
        "bg_primary": "CODE_COMPANION_BG_PRIMARY",
        "bg_panel": "CODE_COMPANION_BG_PANEL",
        "bg_card": "CODE_COMPANION_BG_CARD",
        "border_subtle": "CODE_COMPANION_BORDER_SUBTLE",
        "border_focus": "CODE_COMPANION_BORDER_FOCUS",
        "text_primary": "CODE_COMPANION_TEXT_PRIMARY",
        "text_muted": "CODE_COMPANION_TEXT_MUTED",
        "badge_pass": "CODE_COMPANION_BADGE_PASS",
        "badge_fail": "CODE_COMPANION_BADGE_FAIL",
        "badge_blocked": "CODE_COMPANION_BADGE_BLOCKED",
        "badge_proposal": "CODE_COMPANION_BADGE_PROPOSAL",
        "badge_approval": "CODE_COMPANION_BADGE_APPROVAL_REQUIRED",
        "accent_safe": "CODE_COMPANION_ACCENT_SAFE",
        "stylesheet": "def _stylesheet(self) -> str:",
    }
    missing = [name for name, marker in markers.items() if marker not in source]
    if missing:
        checks.fail("minimal_tech_theme_markers", "missing " + ", ".join(missing))
    else:
        checks.ok("minimal_tech_theme_markers")


def _required_behavior_markers(source: str, companion_source: str, checks: CheckSet) -> None:
    markers = {
        "app_title": 'APP_TITLE = "ENGEL CODE COMPANION"',
        "window_class": "class CodeCompanionWindow",
        "window_title": 'self.setWindowTitle("Engel Code Companion")',
        "workshop_ready": "Workshop ready.",
        "topbar": "QFrame#TopBar",
        "panel": "QFrame#Panel",
        "file_list": "Workshop Files",
        "editor_marker": "QPlainTextEdit#Editor",
        "output_marker": "QPlainTextEdit#Output",
        "ask_engel": "Ask Engel",
        "output_label": "Output",
        "run_action": "def action_run_file",
        "write_action": "def action_engel_write",
        "edit_action": "def action_engel_edit",
        "explain_action": "def action_engel_explain",
        "report_only_statement": "REPORT_ONLY_STATEMENT",
        "product_boundary_statement": "PRODUCT_BUILDER_BOUNDARY_STATEMENT",
        "design_boundary_statement": "DESIGN_FIRST_BOUNDARY_STATEMENT",
        "approve_change": "APPROVE_CHANGE",
        "approve_launch": "APPROVE_LAUNCH",
        "approve_package": "APPROVE_PACKAGE",
        "approve_install": "APPROVE_INSTALL",
        "proposal_only": "PROPOSAL_ONLY / NOT_APPLIED",
        "blocked": "BLOCKED",
        "design_only": "DESIGN ONLY / NOT APPLIED",
    }
    missing = [name for name, marker in markers.items() if marker not in source]
    if missing:
        checks.fail("required_code_companion_markers_preserved", "missing " + ", ".join(missing))
    else:
        checks.ok("required_code_companion_markers_preserved")

    launcher_markers = {
        "open_code_companion": "def open_code_companion",
        "source_launch_path": "engel_code_companion.py",
    }
    launcher_missing = [name for name, marker in launcher_markers.items() if marker not in companion_source]
    if launcher_missing:
        checks.fail("launcher_compatibility_markers_preserved", "missing " + ", ".join(launcher_missing))
    else:
        checks.ok("launcher_compatibility_markers_preserved")


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
        if line.startswith("        def ") or line.startswith("    def ") or line.startswith("def "):
            end = index
            break
    return "\n".join(lines[start:end])


def _theme_only_block(source: str) -> str:
    chunks: list[str] = []
    start_marker = "# ENGEL_CODE_COMPANION_MINIMAL_TECH_THEME_V1_START"
    end_marker = "# ENGEL_CODE_COMPANION_MINIMAL_TECH_THEME_V1_END"
    start = source.find(start_marker)
    end = source.find(end_marker)
    if start != -1 and end != -1 and end > start:
        chunks.append(source[start : end + len(end_marker)])

    stylesheet = _function_block(source, "def _stylesheet(self) -> str:")
    if stylesheet:
        chunks.append(stylesheet)
    return "\n".join(chunks)


def _theme_static_safety(source: str, checks: CheckSet) -> None:
    block = _theme_only_block(source)
    if not block:
        checks.fail("theme_block_present", "theme token/stylesheet block not found")
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
        "route_mutation",
        "queue_mutation",
        "trusted_memory_write",
        "Popen",
        "startfile",
        "open(",
        "APPROVE_CHANGE",
        "APPROVE_LAUNCH",
        "APPROVE_PACKAGE",
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
        "auto-run",
        "auto run",
        "auto-apply",
        "auto apply",
        "provider enabled",
        "network enabled",
    ]
    found_copy = [token for token in suspicious_copy if token.lower() in block.lower()]
    if found_copy:
        checks.fail("theme_block_no_fake_live_or_auto_apply_copy", ", ".join(found_copy))
    else:
        checks.ok("theme_block_no_fake_live_or_auto_apply_copy")


def _run_base_verifier(checks: CheckSet) -> None:
    if not BASE_VERIFIER_PATH.exists():
        checks.fail("base_code_companion_verifier_exists", "missing " + str(BASE_VERIFIER_PATH))
        return
    result = subprocess.run(
        [sys.executable, str(BASE_VERIFIER_PATH)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode == 0:
        checks.ok("base_code_companion_verifier_passes")
    else:
        detail = (result.stdout + "\n" + result.stderr).strip()
        checks.fail("base_code_companion_verifier_passes", detail[-1000:])


def main() -> int:
    checks = CheckSet()
    source = _read(CODE_COMPANION_PATH, "code_companion_source", checks)
    companion_source = _read(COMPANION_PATH, "companion_source", checks)
    tree = None
    if source:
        tree = _compile_source(source, checks)
        _theme_markers(source, checks)
        _theme_static_safety(source, checks)
    if source and companion_source:
        _required_behavior_markers(source, companion_source, checks)
    if tree is not None:
        _import_checks(tree, checks)
    _run_base_verifier(checks)

    if checks.failures:
        print()
        print("CODE_COMPANION_MINIMAL_TECH_THEME_VERIFICATION_FAIL")
        for failure in checks.failures:
            print("- " + failure)
        return 1
    print()
    print("CODE_COMPANION_MINIMAL_TECH_THEME_VERIFICATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
