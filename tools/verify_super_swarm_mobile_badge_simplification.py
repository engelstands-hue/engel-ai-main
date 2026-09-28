from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUPER_SWARM = ROOT / "tools" / "engel_super_swarm_hive_3d_scaffold.py"
COMPANION = ROOT / "engel_companion.py"
MOBILE_STATIC_VERIFIER = ROOT / "tools" / "verify_mobile_status_static.py"

PANEL_START = "# ENGEL_MOBILE_CONNECTION_SUPER_SWARM_READONLY_TAB_V1_PANEL_START"
PANEL_END = "# ENGEL_MOBILE_CONNECTION_SUPER_SWARM_READONLY_TAB_V1_PANEL_END"

COMPACT_MARKERS = {
    "mobile_panel": "MobileConnectionReadOnlyPanel",
    "compact_badge_object": "MobileConnectionCompactBadge",
    "compact_badge_title": "Super Swarm compact Mobile badge",
    "mobile_planned_disabled": "Mobile: planned / disabled",
    "runtime_off": "Runtime: OFF",
    "pairing_off": "Pairing: OFF",
    "packets_off": "Packets: OFF",
    "command_authority_off": "Command authority: OFF",
    "local_readonly": "Local-only / read-only",
    "companion_owner": "Companion remains the full Mobile status owner",
}

LEGACY_STATIC_MARKERS = {
    "mobile_title": "Engel Mobile Connection",
    "runtime_not_enabled": "Contract installed; runtime not enabled",
    "legacy_planned": "Mobile: Planned",
    "legacy_runtime_disabled": "Runtime: Disabled",
    "legacy_networking": "Networking: Not implemented",
    "legacy_pairing": "Pairing: Not implemented",
    "legacy_packets": "Packets: Untrusted",
    "legacy_commands": "Commands: Blocked",
    "legacy_approval": "Human approval: Required",
    "remote_workers_variable": "MOBILE_SWARM_REMOTE_QUEENS_LABEL",
    "runtime_false": "mobile_runtime_enabled: false",
    "pairing_false": "mobile_pairing_enabled: false",
    "handoff_false": "remote_queen_mobile_handoff_enabled: false",
    "disabled_action_sentinel": "button.setEnabled(False)",
}

PRESERVED_SUPER_SWARM_MARKERS = {
    "hive_snapshot_import": "from engel_hive_data_services import build_hive_snapshot",
    "hive_snapshot_call": "build_hive_snapshot(ROOT)",
    "communication_queen": "Communication Queen",
    "guardian": "Guardian",
    "mind_summary": "mind_summary",
    "plan_tab": "Plan",
    "receipts_tab": "Receipts",
    "mobile_tab_label": '"Mobile"',
    "mobile_tab_registration": 'self.ai_audit_tabs.addTab(self._build_mobile_connection_panel(), "Mobile")',
    "remote_workers_label": "Engel Remote Workers",
}

DANGEROUS_TERMS = [
    "engel_mobile_bridge",
    "start_mobile_runtime",
    "enable_mobile_runtime",
    "mobile_pair",
    "pair_mobile",
    "mobile_packet_receiver",
    "process_mobile_packet",
    "import_mobile_packet",
    "mobile_command_channel",
    "mobile_socket",
    "mobile_server",
    "remote queen through mobile",
    "mobile on by default",
]

GENERIC_NETWORK_TERMS = [
    "websocket",
    "socketserver",
    "listen(",
    "bind(",
    "accept(",
]

SAFE_DISABLED_HINTS = [
    "false",
    "off",
    "blocked",
    "disabled",
    "not enabled",
    "not implemented",
    "planned",
    "read-only",
    "unavailable",
    "untrusted",
]


class Checks:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.infos: list[str] = []

    def ok(self, name: str, detail: str = "") -> None:
        print_line("PASS", name, detail)

    def fail(self, name: str, detail: str) -> None:
        self.failures.append(name + ": " + detail)
        print_line("FAIL", name, detail)

    def info(self, name: str, detail: str = "") -> None:
        self.infos.append(name + (": " + detail if detail else ""))
        print_line("INFO", name, detail)


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


def require_markers(source: str, markers: dict[str, str], checks: Checks, label: str) -> None:
    missing = [name for name, marker in markers.items() if marker not in source]
    if missing:
        checks.fail(label, "missing " + ", ".join(missing))
    else:
        checks.ok(label)


def extract_panel_block(source: str, checks: Checks) -> str:
    start = source.find(PANEL_START)
    end = source.find(PANEL_END)
    if start < 0 or end < 0 or end <= start:
        checks.fail("mobile_panel_block", "panel start/end markers missing or out of order")
        return ""
    checks.ok("mobile_panel_block")
    return source[start:end]


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


def line_has_safe_hint(line: str) -> bool:
    lower = line.lower()
    return any(hint in lower for hint in SAFE_DISABLED_HINTS)


def check_forbidden_mobile_patterns(source: str, checks: Checks) -> None:
    findings: list[str] = []
    lines = source.splitlines()
    for index, line in enumerate(lines, start=1):
        lower = line.lower()
        for term in DANGEROUS_TERMS:
            if term in lower and not line_has_safe_hint(line):
                findings.append(f"{index}: {term}")
        if "mobile" in lower:
            for term in GENERIC_NETWORK_TERMS:
                if term in lower and not line_has_safe_hint(line):
                    findings.append(f"{index}: {term}")
    if findings:
        checks.fail("no_mobile_runtime_pairing_packet_command_implementation", "; ".join(findings[:12]))
    else:
        checks.ok("no_mobile_runtime_pairing_packet_command_implementation")


def check_compact_panel(block: str, checks: Checks) -> None:
    require_markers(block, COMPACT_MARKERS, checks, "compact_mobile_badge_markers")
    require_markers(block, LEGACY_STATIC_MARKERS, checks, "legacy_mobile_static_markers_preserved")

    forbidden_visible_controls = [
        "for action in MOBILE_CONNECTION_DISABLED_ACTIONS",
        "actions_layout.addWidget(button)",
        "self.mobile_docs_table",
        "QTableWidget(",
        "Pair Device",
        "Enable Mobile Runtime",
        "Open Mobile Inbox",
        "Review Pending Mobile Request",
    ]
    found = [term for term in forbidden_visible_controls if term in block]
    if found:
        checks.fail("no_full_mobile_controls_or_docs_table_in_panel", ", ".join(found))
    else:
        checks.ok("no_full_mobile_controls_or_docs_table_in_panel")

    if "button.hide()" in block and "Mobile runtime controls unavailable" in block:
        checks.ok("disabled_action_sentinel_hidden")
    else:
        checks.fail("disabled_action_sentinel_hidden", "legacy disabled-action sentinel must remain hidden")


def check_super_swarm_source(checks: Checks) -> None:
    source = read_text(SUPER_SWARM, checks, "super_swarm_source")
    if not source:
        return
    tree = compile_and_parse(source, SUPER_SWARM, checks, "super_swarm_source")
    require_markers(source, PRESERVED_SUPER_SWARM_MARKERS, checks, "surrounding_super_swarm_markers_preserved")
    block = extract_panel_block(source, checks)
    if block:
        check_compact_panel(block, checks)
    check_forbidden_mobile_patterns(source, checks)

    if "engel_mobile_bridge" in source:
        checks.fail("no_engel_mobile_bridge_reference", "Super Swarm source must not reference engel_mobile_bridge")
    else:
        checks.ok("no_engel_mobile_bridge_reference")

    if tree is not None:
        roots = import_roots(tree)
        forbidden_imports = sorted(roots & {"socket", "socketserver", "websocket", "websockets", "fastapi", "flask"})
        if forbidden_imports:
            checks.fail("no_mobile_network_runtime_imports", ", ".join(forbidden_imports))
        else:
            checks.ok("no_mobile_network_runtime_imports")


def check_companion_unchanged(checks: Checks) -> None:
    if not COMPANION.exists():
        checks.fail("companion_source_exists", "missing " + rel(COMPANION))
        return
    try:
        result = subprocess.run(
            ["git", "status", "--short", "--", "engel_companion.py"],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
            check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception as exc:
        checks.info("companion_git_status_unavailable", type(exc).__name__ + ": " + str(exc))
        return
    if result.returncode != 0:
        checks.info("companion_git_status_unavailable", result.stderr.strip())
        return
    status = result.stdout.strip()
    if status:
        checks.fail("companion_mobile_source_not_modified", status)
    else:
        checks.ok("companion_mobile_source_not_modified")


def run_mobile_static_verifier(checks: Checks) -> None:
    if not MOBILE_STATIC_VERIFIER.exists():
        checks.fail("mobile_static_verifier_exists", "missing " + rel(MOBILE_STATIC_VERIFIER))
        return
    result = subprocess.run(
        [sys.executable, str(MOBILE_STATIC_VERIFIER)],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode != 0:
        details = (result.stdout + "\n" + result.stderr).strip()
        checks.fail("verify_mobile_status_static_passes", details[-4000:])
        return
    if "MOBILE_STATUS_STATIC_VERIFICATION_PASS" not in result.stdout:
        checks.fail("verify_mobile_status_static_passes", "missing pass marker")
        return
    checks.ok("verify_mobile_status_static_passes", "MOBILE_STATUS_STATIC_VERIFICATION_PASS")


def main() -> int:
    print("ENGEL_SUPER_SWARM_MOBILE_BADGE_SIMPLIFICATION_VERIFIER")
    print("ROOT " + str(ROOT))
    print("Mode: static local verification only; no GUI/runtime/provider/network/model execution")
    checks = Checks()
    check_super_swarm_source(checks)
    check_companion_unchanged(checks)
    run_mobile_static_verifier(checks)

    if checks.failures:
        print("\nSUPER_SWARM_MOBILE_BADGE_SIMPLIFICATION_VERIFICATION_FAIL")
        for failure in checks.failures:
            print("FAILURE " + failure)
        return 1

    print("\nSUPER_SWARM_MOBILE_BADGE_SIMPLIFICATION_VERIFICATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
