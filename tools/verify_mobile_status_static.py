from __future__ import annotations

import ast
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

OWNERSHIP_JSON = ROOT / "memory" / "ENGEL_MOBILE_STATUS_PANEL_OWNERSHIP_CONTRACT_V1.json"
OWNERSHIP_MD = ROOT / "memory" / "ENGEL_MOBILE_STATUS_PANEL_OWNERSHIP_CONTRACT_V1.md"
OWNERSHIP_REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_MOBILE_STATUS_PANEL_OWNERSHIP_CONTRACT_V1.md"

COMPANION = ROOT / "engel_companion.py"
SUPER_SWARM = ROOT / "tools" / "engel_super_swarm_hive_3d_scaffold.py"
HIVE_SERVICES = ROOT / "engel_hive_data_services.py"

MOBILE_CONFIGS = [
    ROOT / "memory" / "ENGEL_MOBILE_CONNECTION_CONTRACT_V1.json",
    ROOT / "memory" / "MOBILE_CONNECTION_STATUS_DISPLAY_DESIGN_V1.json",
    ROOT / "memory" / "MOBILE_CONNECTION_DESKTOP_STATUS_SURFACE_CONTRACT_V1.json",
    ROOT / "memory" / "V2APP_ENGEL_MOBILE_CONNECTION_CONTRACT.json",
    ROOT / "memory" / "V2APP_MOBILE_CONNECTION_STATUS_DISPLAY_DESIGN.json",
    ROOT / "memory" / "V2APP_MOBILE_CONNECTION_DESKTOP_STATUS_SURFACE_CONTRACT.json",
    ROOT / "memory" / "ROUTE_VERIFICATION_SET_V1.json",
    ROOT / "memory" / "V2TEST_A_ROUTE_REGRESSION_MATRIX.json",
]

MOBILE_REPORTS = [
    ROOT / "reports" / "codex_bridge" / "ENGEL_MOBILE_CONNECTION_CONTRACT.md",
    ROOT / "reports" / "codex_bridge" / "MOBILE_CONNECTION_COMPANION_READONLY_TAB.md",
    ROOT / "reports" / "codex_bridge" / "MOBILE_CONNECTION_SUPER_SWARM_READONLY_TAB.md",
    ROOT / "reports" / "codex_bridge" / "MOBILE_CONNECTION_STATUS_DISPLAY_DESIGN.md",
    ROOT / "reports" / "codex_bridge" / "MOBILE_CONNECTION_DESKTOP_STATUS_SURFACE_CONTRACT.md",
]

SOURCE_SUFFIXES = {".py", ".ps1", ".bat", ".cmd", ".sh", ".spec"}
BINARY_SUFFIXES = {
    ".exe",
    ".dll",
    ".pyd",
    ".pyc",
    ".pyo",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".zip",
    ".7z",
    ".tar",
    ".gz",
    ".pyz",
    ".pkg",
}

EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "build",
    "dist",
    "live",
    "backups",
    "node_modules",
}

SOURCE_EXCLUDE_PREFIXES = {
    ("reports",),
    ("memory",),
}

MOBILE_CONTEXT_TERMS = [
    "mobile",
    "engel mobile",
    "engel mobile connection",
    "engel_mobile_bridge",
    "mobile connection",
    "mobile runtime",
    "mobile packet",
    "mobile pairing",
]

ENGEL_MOBILE_CONTEXT_TERMS = [
    "engel mobile",
    "engel mobile connection",
    "engel_mobile",
    "mobile connection",
    "mobile runtime",
    "mobile packet",
    "mobile pairing",
]

SAFE_DISABLED_HINTS = [
    "false",
    "0",
    "blocked",
    "disabled",
    "display-only",
    "not enabled",
    "not implemented",
    "non-actioning",
    "planned",
    "review-required",
    "review required",
    "untrusted",
]

NON_ENGEL_MOBILE_SOURCE_PREFIXES = {
    ("engelcode_main",),
    ("external",),
}

DANGEROUS_LITERAL_PATTERNS = [
    "start_mobile_runtime",
    "enable_mobile_runtime",
    "mobile_pair",
    "pair_mobile",
    "mobile_packet_receiver",
    "process_mobile_packet",
    "import_mobile_packet",
    "mobile_command_authority",
    "mobile_command_channel",
    "mobile_socket",
    "mobile_server",
    "remote queen through mobile",
    "mobile on by default",
]

GENERIC_NETWORK_PATTERNS = [
    "websocket",
    "socketserver",
    "listen(",
    "bind(",
    "accept(",
]

FALSE_FLAG_KEYS = {
    "mobile_runtime_enabled",
    "mobile_pairing_enabled",
    "mobile_packet_processing_enabled",
    "mobile_command_authority_enabled",
    "mobile_networking_enabled",
    "networking_or_mobile_runtime_enabled",
    "networking_enabled",
    "packet_receiver_enabled",
    "route_handlers_enabled",
    "runtime_enabled",
    "device_pairing_enabled",
    "remote_queen_mobile_handoff_enabled",
    "websocket_enabled",
    "socket_enabled",
    "http_server_enabled",
    "http_client_enabled",
    "runtime_worker_enabled",
    "remote_execution_enabled",
}

FUTURE_ROUTE_FLAGS = {"implemented_now", "should_execute_in_test", "runtime_enabled", "enabled_now"}


class Checks:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.skips: list[str] = []
        self.infos: list[str] = []

    def ok(self, name: str, detail: str = "") -> None:
        print_line("PASS", name, detail)

    def fail(self, name: str, detail: str) -> None:
        message = name + ": " + detail
        self.failures.append(message)
        print_line("FAIL", name, detail)

    def info(self, name: str, detail: str = "") -> None:
        self.infos.append(name + (": " + detail if detail else ""))
        print_line("INFO", name, detail)

    def skip(self, name: str, detail: str) -> None:
        self.skips.append(name + ": " + detail)
        print_line("SKIP", name, detail)


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


def read_json(path: Path, checks: Checks, label: str) -> Any:
    text = read_text(path, checks, label)
    if not text:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        checks.fail(label + "_json_parse", f"{rel(path)} line {exc.lineno}: {exc.msg}")
        return None
    checks.ok(label + "_json_parse", rel(path))
    return data


def require_markers(text: str, markers: dict[str, str], checks: Checks, label: str) -> None:
    missing = [name for name, marker in markers.items() if marker not in text]
    if missing:
        checks.fail(label, "missing " + ", ".join(missing))
    else:
        checks.ok(label)


def contains_any(text: str, terms: list[str]) -> bool:
    lower = text.lower()
    return any(term.lower() in lower for term in terms)


def parse_ast(text: str, path: Path, checks: Checks, label: str) -> ast.AST | None:
    try:
        compile(text, str(path), "exec")
    except SyntaxError as exc:
        checks.fail(label + "_compiles", str(exc))
        return None
    checks.ok(label + "_compiles")
    try:
        tree = ast.parse(text, filename=str(path))
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
        elif isinstance(node, ast.ImportFrom):
            roots.add((node.module or "").split(".", 1)[0])
    return roots


def check_contract(checks: Checks) -> None:
    data = read_json(OWNERSHIP_JSON, checks, "ownership_contract")
    read_text(OWNERSHIP_MD, checks, "ownership_markdown")
    read_text(OWNERSHIP_REPORT, checks, "ownership_report")
    if not isinstance(data, dict):
        checks.fail("ownership_contract_shape", "expected object")
        return

    expected_false_flags = [
        "mobile_runtime_enabled",
        "mobile_pairing_enabled",
        "mobile_packet_processing_enabled",
        "mobile_command_authority_enabled",
    ]
    missing_or_true = [key for key in expected_false_flags if data.get(key) is not False]
    if missing_or_true:
        checks.fail("ownership_runtime_flags_false", ", ".join(missing_or_true))
    else:
        checks.ok("ownership_runtime_flags_false")

    true_flags = [key for key in ("no_source_changes", "no_ui_changes_now", "no_route_changes") if data.get(key) is not True]
    if true_flags:
        checks.fail("ownership_no_change_flags_true", ", ".join(true_flags))
    else:
        checks.ok("ownership_no_change_flags_true")

    primary = data.get("primary_owner")
    primary_text = json.dumps(primary, sort_keys=True).lower()
    if isinstance(primary, dict) and "companion" in primary_text and "mobile" in primary_text:
        checks.ok("ownership_primary_owner_companion")
    else:
        checks.fail("ownership_primary_owner_companion", "primary_owner must identify Companion Mobile status")

    secondary_text = json.dumps(data.get("secondary_surfaces"), sort_keys=True).lower()
    if "super swarm" in secondary_text and ("readonly" in secondary_text or "read-only" in secondary_text):
        checks.ok("ownership_super_swarm_secondary_readonly")
    else:
        checks.fail("ownership_super_swarm_secondary_readonly", "secondary surfaces must identify Super Swarm as read-only")

    classifications_text = json.dumps(data.get("classifications"), sort_keys=True).lower()
    if "mobile_interactive_review_required" in classifications_text and "mobile_runtime_forbidden" in classifications_text:
        checks.ok("ownership_interactive_runtime_review_boundary")
    else:
        checks.fail("ownership_interactive_runtime_review_boundary", "missing review/forbidden classification for Mobile runtime wiring")


def check_companion(checks: Checks) -> None:
    source = read_text(COMPANION, checks, "companion_source")
    if not source:
        return
    tree = parse_ast(source, COMPANION, checks, "companion_source")

    markers = {
        "mobile_tab": 'self.ai_audit_tabs.addTab(self.mobile_connection_panel, "MOBILE")',
        "mobile_panel": "MobileConnectionReadOnlyPanel",
        "mobile_title": "Engel Mobile Connection",
        "runtime_not_enabled": "Contract installed; runtime not enabled",
        "planned_badge": "Mobile: Planned",
        "runtime_disabled": "Runtime: Disabled",
        "networking_not_implemented": "Networking: Not implemented",
        "pairing_not_implemented": "Pairing: Not implemented",
        "packets_untrusted": "Packets: Untrusted",
        "commands_blocked": "Commands: Blocked",
        "human_approval": "Human approval: Required",
        "remote_workers_blocked": "Engel Remote Workers: Blocked",
        "metrics_runtime_false": "mobile_runtime_enabled: false",
        "metrics_pairing_false": "mobile_pairing_enabled: false",
        "handoff_false": "remote_queen_mobile_handoff_enabled: false",
        "future_actions_disabled": "button.setEnabled(False)",
    }
    require_markers(source, markers, checks, "companion_mobile_markers")

    if 'self.mobile_toggle = QPushButton("Mobile OFF"' in source:
        checks.ok("companion_mobile_toggle_marker_present")
        require_markers(
            source,
            {
                "toggle_connected": "self.mobile_toggle.toggled.connect(self.toggle_mobile_session_button)",
                "toggle_hidden": "self.mobile_toggle.hide()",
                "bridge_guard": 'process_launch_guard_v2process_b("engel_mobile_bridge.py")',
            },
            checks,
            "companion_mobile_toggle_review_boundary",
        )
    else:
        checks.skip("companion_mobile_toggle_marker_present", "Mobile toggle marker absent in current source")

    if "self.mobile_toggle.show()" in source:
        checks.fail("companion_mobile_toggle_not_shown", "self.mobile_toggle.show() present")
    else:
        checks.ok("companion_mobile_toggle_not_shown")

    init_prefix = source.split("def toggle_mobile_session_button", 1)[0]
    if "mobile_toggle.setChecked(True)" in init_prefix:
        checks.fail("companion_no_mobile_on_by_default", "mobile toggle defaults to checked before runtime handler")
    else:
        checks.ok("companion_no_mobile_on_by_default")

    if '_start_script_process("engel_mobile_bridge.py"' in source or "_start_script_process(\n                    \"engel_mobile_bridge.py\"" in source:
        if "MOBILE_INTERACTIVE_REVIEW_REQUIRED" in read_text(OWNERSHIP_JSON, checks, "ownership_contract_for_toggle_boundary"):
            checks.info("companion_existing_mobile_bridge_wiring_review_required", "hidden/guarded path is not approved as runtime authority")
        else:
            checks.fail("companion_existing_mobile_bridge_wiring_review_required", "ownership contract lacks review-required classification")
    else:
        checks.ok("companion_no_mobile_bridge_start_path")

    if tree is not None:
        roots = import_roots(tree)
        forbidden_imports = sorted(roots & {"socket", "socketserver", "websocket", "websockets", "fastapi", "flask"})
        if forbidden_imports:
            checks.fail("companion_no_mobile_network_imports", ", ".join(forbidden_imports))
        else:
            checks.ok("companion_no_mobile_network_imports")


def check_super_swarm(checks: Checks) -> None:
    source = read_text(SUPER_SWARM, checks, "super_swarm_source")
    if not source:
        return
    tree = parse_ast(source, SUPER_SWARM, checks, "super_swarm_source")

    markers = {
        "mobile_tab": 'self.ai_audit_tabs.addTab(self._build_mobile_connection_panel(), "Mobile")',
        "mobile_panel": "MobileConnectionReadOnlyPanel",
        "mobile_title": "Engel Mobile Connection",
        "runtime_not_enabled": "Contract installed; runtime not enabled",
        "planned_badge": "Mobile: Planned",
        "runtime_disabled": "Runtime: Disabled",
        "networking_not_implemented": "Networking: Not implemented",
        "pairing_not_implemented": "Pairing: Not implemented",
        "packets_untrusted": "Packets: Untrusted",
        "commands_blocked": "Commands: Blocked",
        "human_approval": "Human approval: Required",
        "remote_workers_blocked": "Engel Remote Workers",
        "metrics_runtime_false": "mobile_runtime_enabled: false",
        "metrics_pairing_false": "mobile_pairing_enabled: false",
        "handoff_false": "remote_queen_mobile_handoff_enabled: false",
        "future_actions_disabled": "button.setEnabled(False)",
    }
    require_markers(source, markers, checks, "super_swarm_mobile_markers")

    if "engel_mobile_bridge.py" in source or "_start_script_process" in source and "mobile" in source.lower():
        checks.fail("super_swarm_no_mobile_runtime_start_behavior", "Mobile runtime/session start reference found")
    else:
        checks.ok("super_swarm_no_mobile_runtime_start_behavior")

    if tree is not None:
        roots = import_roots(tree)
        forbidden_imports = sorted(roots & {"socket", "socketserver", "websocket", "websockets", "fastapi", "flask"})
        if forbidden_imports:
            checks.fail("super_swarm_no_mobile_network_imports", ", ".join(forbidden_imports))
        else:
            checks.ok("super_swarm_no_mobile_network_imports")


def check_hive_services(checks: Checks) -> None:
    source = read_text(HIVE_SERVICES, checks, "hive_services_source")
    if not source:
        return
    markers = {
        "mobile_status": '"mobile_status": "planned_disabled"',
        "mobile_runtime_flag": '"mobile_runtime_enabled"',
        "device_pairing_flag": '"device_pairing_enabled"',
        "remote_queen_flag": '"remote_queen_runtime_enabled"',
    }
    require_markers(source, markers, checks, "hive_mobile_readonly_disabled_markers")
    forbidden = [pattern for pattern in DANGEROUS_LITERAL_PATTERNS if pattern in source.lower()]
    if forbidden:
        checks.fail("hive_no_mobile_runtime_networking", ", ".join(forbidden))
    else:
        checks.ok("hive_no_mobile_runtime_networking")


def should_skip_source(path: Path) -> bool:
    try:
        parts = tuple(part.lower() for part in path.relative_to(ROOT).parts)
    except ValueError:
        return True
    if any(part in EXCLUDE_DIRS for part in parts):
        return True
    if path.suffix.lower() in BINARY_SUFFIXES:
        return True
    if parts[:1] in SOURCE_EXCLUDE_PREFIXES:
        return True
    return False


def is_verifier(path: Path) -> bool:
    return path.name.startswith("verify_") or "\\tools\\verify_" in ("\\" + rel(path).lower())


def iter_source_files() -> list[Path]:
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        current = Path(dirpath)
        kept_dirs: list[str] = []
        for dirname in dirnames:
            candidate = current / dirname
            if not should_skip_source(candidate):
                kept_dirs.append(dirname)
        dirnames[:] = kept_dirs
        for filename in filenames:
            path = current / filename
            if not path.is_file() or should_skip_source(path):
                continue
            if path.suffix.lower() in SOURCE_SUFFIXES:
                found.append(path)
    return found


def line_context(lines: list[str], index: int, radius: int = 3) -> str:
    start = max(0, index - radius)
    end = min(len(lines), index + radius + 1)
    return "\n".join(lines[start:end]).lower()


def is_safe_disabled_context(context: str) -> bool:
    lower = context.lower()
    return any(hint in lower for hint in SAFE_DISABLED_HINTS)


def is_non_engel_mobile_source(path: Path) -> bool:
    try:
        parts = tuple(part.lower() for part in path.relative_to(ROOT).parts)
    except ValueError:
        return False
    return any(parts[: len(prefix)] == prefix for prefix in NON_ENGEL_MOBILE_SOURCE_PREFIXES)


def check_forbidden_source_scan(checks: Checks) -> None:
    findings: list[str] = []
    review_required: list[str] = []
    scanned = 0
    safe_verifier_refs = 0
    safe_disabled_refs = 0
    unrelated_mobile_refs = 0

    for path in iter_source_files():
        if path.stat().st_size > 5_000_000:
            continue
        try:
            text = path.read_text(encoding="utf-8-sig", errors="replace")
        except Exception:
            continue
        scanned += 1
        lower_text = text.lower()
        if is_verifier(path):
            if contains_any(lower_text, DANGEROUS_LITERAL_PATTERNS + GENERIC_NETWORK_PATTERNS):
                safe_verifier_refs += 1
            continue

        lines = text.splitlines()
        for index, line in enumerate(lines):
            lower_line = line.lower()
            context = line_context(lines, index)
            if is_non_engel_mobile_source(path) and not contains_any(context, ENGEL_MOBILE_CONTEXT_TERMS):
                if contains_any(lower_line, DANGEROUS_LITERAL_PATTERNS + GENERIC_NETWORK_PATTERNS):
                    unrelated_mobile_refs += 1
                continue
            for pattern in DANGEROUS_LITERAL_PATTERNS:
                if pattern in lower_line:
                    if is_safe_disabled_context(context):
                        safe_disabled_refs += 1
                        continue
                    findings.append(f"{rel(path)}:{index + 1}: {pattern}")
            for pattern in GENERIC_NETWORK_PATTERNS:
                if pattern in lower_line and contains_any(context, MOBILE_CONTEXT_TERMS):
                    if is_safe_disabled_context(context):
                        safe_disabled_refs += 1
                        continue
                    findings.append(f"{rel(path)}:{index + 1}: {pattern}")

        if "engel_mobile_bridge.py" in lower_text and path.name == "engel_companion.py":
            review_required.append("engel_companion.py existing hidden Mobile bridge/session wiring remains review-required")

    checks.info("mobile_forbidden_source_scan_files_scanned", str(scanned))
    checks.info("mobile_forbidden_source_scan_safe_verifier_refs", str(safe_verifier_refs))
    checks.info("mobile_forbidden_source_scan_safe_disabled_refs", str(safe_disabled_refs))
    checks.info("mobile_forbidden_source_scan_unrelated_mobile_refs", str(unrelated_mobile_refs))
    for item in review_required:
        checks.info("mobile_source_review_required", item)
    if findings:
        checks.fail("mobile_forbidden_source_patterns", "; ".join(findings[:20]))
        if len(findings) > 20:
            checks.info("mobile_forbidden_source_patterns_suppressed", str(len(findings) - 20))
    else:
        checks.ok("mobile_forbidden_source_patterns", "0 active implementation findings")


def scalar_text(value: Any) -> str:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return str(value)
    if isinstance(value, dict):
        return " ".join(str(k) + " " + scalar_text(v) for k, v in value.items())
    if isinstance(value, list):
        return " ".join(scalar_text(item) for item in value)
    return str(value)


def walk_json(value: Any, path: str = "$") -> list[tuple[str, Any]]:
    items = [(path, value)]
    if isinstance(value, dict):
        for key, child in value.items():
            items.extend(walk_json(child, path + "." + str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            items.extend(walk_json(child, path + "[" + str(index) + "]"))
    return items


def is_dangerous_mobile_config_context(text: str) -> bool:
    lower = text.lower()
    if "mobile" not in lower:
        return False
    dangerous_terms = [
        "runtime",
        "pair",
        "packet",
        "receiver",
        "command",
        "socket",
        "server",
        "network",
        "remote queen",
        "handoff",
        "worker",
    ]
    return any(term in lower for term in dangerous_terms)


def check_config_object(data: Any, config_path: Path, checks: Checks) -> list[str]:
    findings: list[str] = []
    mobile_objects_seen = 0
    for json_path, value in walk_json(data):
        if not isinstance(value, dict):
            continue
        context = scalar_text(value)
        if "mobile" not in context.lower():
            continue
        mobile_objects_seen += 1
        for key in FALSE_FLAG_KEYS:
            if value.get(key) is True:
                findings.append(f"{rel(config_path)} {json_path}.{key}=true")
        if is_dangerous_mobile_config_context(context):
            for key in FUTURE_ROUTE_FLAGS:
                if value.get(key) is True:
                    findings.append(f"{rel(config_path)} {json_path}.{key}=true")
    checks.info("mobile_route_config_objects_checked", f"{rel(config_path)} objects={mobile_objects_seen}")
    return findings


def check_route_and_config(checks: Checks) -> None:
    findings: list[str] = []
    checked = 0
    for path in MOBILE_CONFIGS:
        if not path.exists():
            checks.skip("mobile_route_config_optional", rel(path))
            continue
        data = read_json(path, checks, "mobile_route_config")
        if data is None:
            findings.append(rel(path) + " parse failed")
            continue
        checked += 1
        findings.extend(check_config_object(data, path, checks))

    for report_path in MOBILE_REPORTS:
        if report_path.exists():
            checks.ok("mobile_report_reference_present", rel(report_path))
        else:
            checks.skip("mobile_report_reference_present", rel(report_path))

    if findings:
        checks.fail("mobile_route_config_no_runtime_execution", "; ".join(findings[:20]))
        if len(findings) > 20:
            checks.info("mobile_route_config_findings_suppressed", str(len(findings) - 20))
    else:
        checks.ok("mobile_route_config_no_runtime_execution", f"checked={checked}")


def main() -> int:
    checks = Checks()
    print("ENGEL_MOBILE_STATUS_STATIC_VERIFIER")
    print("ROOT " + str(ROOT))
    print("Mode: static local verification only; no GUI/runtime/provider/network/model execution")

    check_contract(checks)
    check_companion(checks)
    check_super_swarm(checks)
    check_hive_services(checks)
    check_forbidden_source_scan(checks)
    check_route_and_config(checks)

    if checks.failures:
        print()
        print("MOBILE_STATUS_STATIC_VERIFICATION_FAIL")
        for failure in checks.failures:
            print("- " + failure)
        return 1

    print()
    checks.ok("ownership contract checks")
    checks.ok("Companion marker checks")
    checks.ok("Super Swarm marker checks")
    checks.ok("Hive summary / data-service checks")
    checks.ok("forbidden pattern scan")
    checks.ok("route/config checks")
    print("MOBILE_STATUS_STATIC_VERIFICATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
