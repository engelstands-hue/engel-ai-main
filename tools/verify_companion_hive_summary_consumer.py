from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPANION_PATH = ROOT / "engel_companion.py"
HELPER_VERIFIER_PATH = ROOT / "tools" / "verify_companion_hive_summary_helper.py"


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


def _read_companion(checks: CheckSet) -> str:
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


def _required_markers(source: str, checks: CheckSet) -> None:
    markers = {
        "helper_import_or_reference": "build_companion_hive_summary",
        "hive_status_card_object": "CompanionHiveStatusCard",
        "hive_status_label_object": "CompanionHiveSummaryStatus",
        "hive_launcher_button": "self.research_office_button = QPushButton(\"Hive\"",
        "hive_launcher_connect": "self.research_office_button.clicked.connect(self.open_colony_hive_gui)",
        "hive_launcher_lazy_window": "from engel_research_office import EngelColonyHiveWindow",
        "open_colony_hive_gui_method": "def open_colony_hive_gui",
        "ai_plan_tab": "self.ai_audit_tabs.addTab(self.ai_plan_panel, \"PLAN\")",
        "ai_receipts_tab": "self.ai_audit_tabs.addTab(self.ai_receipt_viewer_panel, \"RECEIPTS\")",
        "mobile_tab": "self.ai_audit_tabs.addTab(self.mobile_connection_panel, \"MOBILE\")",
        "code_companion_button": "self.code_companion_button = QPushButton(\"Code\"",
        "code_companion_launcher": "self.code_companion_button.clicked.connect(self.open_code_companion)",
        "source_trust_copy": "local_readonly_snapshot",
    }
    missing = [name for name, marker in markers.items() if marker not in source]
    if missing:
        checks.fail("companion_required_markers", "missing " + ", ".join(missing))
    else:
        checks.ok("companion_required_markers")


def _ast_static_checks(source: str, checks: CheckSet) -> None:
    try:
        tree = ast.parse(source, filename=str(COMPANION_PATH))
    except SyntaxError as exc:
        checks.fail("companion_ast_parse", str(exc))
        return
    checks.ok("companion_ast_parse")

    import_roots: set[str] = set()
    helper_import_ok = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                import_roots.add(alias.name.split(".", 1)[0])
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            import_roots.add(module.split(".", 1)[0])
            if module == "engel_hive_data_services":
                for alias in node.names:
                    if alias.name == "build_companion_hive_summary":
                        helper_import_ok = True

    forbidden_new_roots = {
        "requests",
        "urllib",
        "httpx",
        "socket",
        "ollama",
        "llama_cpp",
        "transformers",
        "torch",
    }
    present_forbidden = sorted(import_roots & forbidden_new_roots)
    if present_forbidden:
        checks.fail("no_provider_network_model_imports_added", ", ".join(present_forbidden))
    else:
        checks.ok("no_provider_network_model_imports_added")

    if helper_import_ok:
        checks.ok("helper_import_present")
    else:
        checks.fail("helper_import_present", "missing import from engel_hive_data_services")


def _feature_block(source: str) -> str:
    needles = [
        "def _compact_hive_status_value",
        "def _format_hive_summary_status_text",
        "def _refresh_hive_summary_card",
        "def _build_hive_summary_card",
    ]
    chunks: list[str] = []
    lines = source.splitlines()
    for needle in needles:
        start = None
        for index, line in enumerate(lines):
            if needle in line:
                start = index
                break
        if start is None:
            continue
        end = len(lines)
        for index in range(start + 1, len(lines)):
            line = lines[index]
            if line.startswith("    def ") and needle not in line:
                end = index
                break
        chunks.append("\n".join(lines[start:end]))
    return "\n".join(chunks)


def _feature_static_checks(source: str, checks: CheckSet) -> None:
    block = _feature_block(source)
    if not block:
        checks.fail("feature_block_present", "Hive summary helper/card methods not found")
        return
    checks.ok("feature_block_present")

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
        "write_text",
        "write_bytes",
        "append_file",
        "trusted_memory",
        "queue_mutation",
        "route_mutation",
        "setEnabled(True)",
        "Popen",
        "startfile",
        "open(",
    ]
    found = [token for token in forbidden_tokens if token in block]
    if found:
        checks.fail("feature_block_no_forbidden_behavior", ", ".join(found))
    else:
        checks.ok("feature_block_no_forbidden_behavior")

    if "setText(" in block and "build_companion_hive_summary(ROOT)" in block:
        checks.ok("feature_uses_summary_as_readonly_text")
    else:
        checks.fail("feature_uses_summary_as_readonly_text", "expected helper call and label setText")


def _layout_order_check(source: str, checks: CheckSet) -> None:
    hive = source.find("right_layout.addWidget(self.research_office_button)")
    card = source.find("right_layout.addWidget(self.hive_summary_card)")
    code = source.find("right_layout.addWidget(self.code_companion_button)")
    tabs = source.find("right_layout.addWidget(self.ai_audit_tabs, 1)")
    if hive == -1 or card == -1 or code == -1 or tabs == -1:
        checks.fail("hive_summary_layout_order", "missing layout markers")
        return
    if hive < card < code < tabs:
        checks.ok("hive_summary_layout_order")
    else:
        checks.fail("hive_summary_layout_order", "expected Hive button, summary card, Code button, tabs")


def _run_helper_verifier(checks: CheckSet) -> None:
    if not HELPER_VERIFIER_PATH.exists():
        checks.fail("helper_verifier_exists", "missing " + str(HELPER_VERIFIER_PATH))
        return
    sys.dont_write_bytecode = True
    try:
        spec = importlib.util.spec_from_file_location("verify_companion_hive_summary_helper", HELPER_VERIFIER_PATH)
        if spec is None or spec.loader is None:
            checks.fail("helper_verifier_load", "could not load module spec")
            return
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        result = module.main()
    except Exception as exc:
        checks.fail("helper_verifier_passes", type(exc).__name__ + ": " + str(exc))
        return
    if result == 0:
        checks.ok("helper_verifier_passes")
    else:
        checks.fail("helper_verifier_passes", "returned " + str(result))


def main() -> int:
    checks = CheckSet()
    source = _read_companion(checks)
    if source:
        _required_markers(source, checks)
        _ast_static_checks(source, checks)
        _feature_static_checks(source, checks)
        _layout_order_check(source, checks)
    _run_helper_verifier(checks)

    if checks.failures:
        print()
        print("COMPANION_HIVE_SUMMARY_CONSUMER_VERIFICATION_FAIL")
        for failure in checks.failures:
            print("- " + failure)
        return 1
    print()
    print("COMPANION_HIVE_SUMMARY_CONSUMER_VERIFICATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
