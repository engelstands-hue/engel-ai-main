from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPANION = ROOT / "engel_companion.py"
RESEARCH_OFFICE = ROOT / "engel_research_office.py"
VERIFIER = ROOT / "tools" / "verify_engel_ai_growth_gui_tabs.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_COLONY_HIVE_STATUS_TAB_REMOVAL_V1.md"

REMOVED_STATUS_TABS = [
    "AI Growth",
    "Self-Learning",
    "Candidate Review",
    "Code Companion Review",
    "Global Safety",
    "System Integration",
    "Self-Fix",
    "Memory Promotion",
    "Research-to-Fix",
]

REQUIRED_BACKEND_REFERENCES = [
    "engel_ai_growth_dashboard",
    "engel_self_learning_status_surface",
    "engel_candidate_review_dashboard",
    "engel_code_companion_candidate_review_status",
    "engel_global_password_gate",
    "engel_system_integration_status",
    "engel_low_risk_self_fix_status_surface",
    "engel_memory_promotion_writer",
    "engel_research_to_fix_loop",
]

FORBIDDEN_VISIBLE_TAB_SNIPPETS = [
    "self.tabs.addTab(self._make_ai_growth_gui_status_tab(tab_name), tab_name)",
    "self.ai_audit_tabs.addTab(self._build_ai_growth_combo_panel(), \"GROWTH\")",
]

FORBIDDEN_BEHAVIOR_COMMANDS = [
    "llama-cli",
    "llama-server",
    "rpc-server",
    "ollama",
]

FORBIDDEN_TRUE_ASSIGNMENTS = [
    ("provider_api_enabled", "True"),
    ("server_enabled", "True"),
    ("trusted_memory_write_enabled", "True"),
    ("startup_auto_load_enabled", "True"),
    ("background_daemon_enabled", "True"),
]


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def check_files_exist() -> None:
    for path in [COMPANION, RESEARCH_OFFICE, VERIFIER, REPORT]:
        require(path.exists() and path.is_file(), "required file missing: " + str(path))


def check_colony_hive_tabs_removed() -> None:
    research_office = read(RESEARCH_OFFICE)
    for snippet in FORBIDDEN_VISIBLE_TAB_SNIPPETS:
        require(snippet not in research_office, "research office still exposes removed status tabs: " + snippet)
    require(
        "self.tabs.addTab(self._make_permissions_tab(), \"Permissions\")" in research_office,
        "expected useful Permissions tab anchor missing",
    )
    require(
        "for tab_name in AI_GROWTH_GUI_TAB_NAMES:" not in research_office,
        "research office still loops removed AI growth tab names into top-level tabs",
    )


def check_companion_growth_tab_removed() -> None:
    companion = read(COMPANION)
    for snippet in FORBIDDEN_VISIBLE_TAB_SNIPPETS:
        require(snippet not in companion, "companion still exposes removed growth audit tab: " + snippet)
    for tab in ["PLAN", "BODY", "RECEIPTS", "MOBILE"]:
        require(f'"{tab}"' in companion, "companion lost expected remaining audit tab: " + tab)


def check_backend_contracts_preserved() -> None:
    combined = read(COMPANION) + "\n" + read(RESEARCH_OFFICE)
    for module_name in REQUIRED_BACKEND_REFERENCES:
        require(module_name in combined, "backend status reference unexpectedly removed: " + module_name)
    require(
        "render_ai_growth_gui_tab_text" in combined,
        "read-only backend render helper should remain available for non-tab status checks",
    )


def check_report() -> None:
    text = read(REPORT)
    for tab in REMOVED_STATUS_TABS:
        require(tab in text, "removal report missing tab name: " + tab)
    for needle in [
        "STATUS_TABS_REMOVED",
        "BACKEND_CONTRACTS_PRESERVED",
        "Packaging skipped",
        "did not remove backend safety contracts",
    ]:
        require(needle in text, "removal report missing required text: " + needle)


def check_no_runtime_enablement() -> None:
    combined = read(COMPANION) + "\n" + read(RESEARCH_OFFICE) + "\n" + read(REPORT)
    for snippet in FORBIDDEN_BEHAVIOR_COMMANDS:
        require(snippet not in combined, "runtime/provider behavior appears enabled: " + snippet)
    for name, value in FORBIDDEN_TRUE_ASSIGNMENTS:
        snippet = f"{name} = {value}"
        require(snippet not in combined, "runtime/provider behavior appears enabled: " + snippet)


def main() -> int:
    try:
        check_files_exist()
        check_colony_hive_tabs_removed()
        check_companion_growth_tab_removed()
        check_backend_contracts_preserved()
        check_report()
        check_no_runtime_enablement()
    except CheckFailure as exc:
        print("[FAIL]", exc)
        return 1
    print("[PASS] Engel Colony Hive status tab removal verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
