from __future__ import annotations

import importlib.util
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
COMPANION = ROOT / "engel_companion.py"
RESEARCH_OFFICE = ROOT / "engel_research_office.py"
SCAFFOLD = ROOT / "tools" / "engel_super_swarm_hive_3d_scaffold.py"
VERIFIER = ROOT / "tools" / "verify_engel_low_risk_self_fix_gui_visibility.py"

REQUIRED_LABELS = [
    "DRY RUN VISIBILITY ONLY",
    "READ ONLY",
    "LOW RISK ONLY",
    "HIGH RISK STOPS",
    "NO APPLY BUTTON",
    "NO PACKAGE REFRESH",
    "NO TRUSTED MEMORY WRITE",
    "NO PROVIDER NETWORK BROWSER",
    "NO BACKGROUND WORKER",
]

REQUIRED_SELF_FIX_TEXT = [
    "Engel Low-Risk Self-Fix GUI Dry-Run Visibility",
    "Low-risk self-fix runner status",
    "Implemented V2 low-risk classes visible here",
    "Future/dry-run-only classes visible here",
    "High-risk stop classes",
    "Receipt status",
    "receipt count",
    "last receipt summary if available",
    "Dry-run boundary",
    "Verification-before-commit boundary",
    "no apply button exists in this GUI step",
    "no self-fix apply action exists in this GUI step",
    "no high-risk behavior",
    "no package refresh action",
    "no provider/network/browser behavior",
    "no model runtime",
    "no trusted memory write",
    "no route/startup mutation",
    "no background worker",
]

REQUIRED_CLASSES = [
    "stale_pid_cleanup",
    "report_hash_refresh",
    "generated_report_metadata_update",
    "generated_artifact_cleanup",
    "docs_drift_alignment",
    "core_continuity_missing_verified_node",
    "verifier_expectation_update_for_existing_committed_contract",
    "read_only_status_surface_reference_update",
    "codex_bridge_report_reference_update",
    "known_safe_path_label_or_status_correction",
    "provider_api_network_browser_activation",
    "model_loading_or_inference",
    "trusted_memory_write",
    "route_startup_source_behavior_mutation",
    "background_worker_or_autonomous_loop",
    "package_refresh_or_live_exe_promotion",
    "file_import_copy_move_sync",
    "queue_runtime_or_worker_activation",
    "security_authority_hierarchy_change",
    "deletion_of_unknown_or_unclassified_files",
    "arbitrary_source_refactor",
    "external_drive_access",
    "package_manager_change",
]

FORBIDDEN_ACTIVE_PATTERNS = [
    r"\bQPushButton\b",
    r"\.clicked\.connect",
    r"\bsubprocess\b",
    r"\brequests\b",
    r"\burllib\b",
    r"\bsocket\b",
    r"\bwebbrowser\b",
    r"\bopenai\b",
    r"\bQDesktopServices\b",
    r"\bQTimer\b",
    r"\bPopen\b",
    r"\bstartDetached\b",
    r"\bwrite_receipt\b",
    r"\brun_issue\b",
    r"\brun_post_apply_verification\b",
    r"\b--apply\b",
    r"\.write_text\s*\(",
    r"\.write_bytes\s*\(",
    r"\.unlink\s*\(",
    r"\.remove\s*\(",
    r"\.rename\s*\(",
    r"\.replace\s*\(",
    r"\.rglob\s*\(",
    r"\.glob\s*\(",
    r"\.walk\s*\(",
]

FORBIDDEN_ACTION_LABELS = [
    "Run Self-Fix",
    "Apply Self-Fix",
    "Apply Fix",
    "Commit Fix",
    "Package Refresh",
    "Refresh Package",
    "Start Provider",
    "Open Browser",
    "Start Model Runtime",
    "Write Trusted Memory",
]


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def marked_blocks(text: str) -> str:
    pattern = re.compile(
        r"# ENGEL_AI_GROWTH_GUI_TABS_V1[^\n]*_START(?P<body>.*?)"
        r"# ENGEL_AI_GROWTH_GUI_TABS_V1[^\n]*_END",
        re.DOTALL,
    )
    return "\n\n".join(match.group("body") for match in pattern.finditer(text))


def load_module(module_name: str, path: Path):
    root_text = str(ROOT)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    spec = importlib.util.spec_from_file_location(module_name, path)
    require(spec is not None and spec.loader is not None, "could not load module spec: " + module_name)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def check_files_exist() -> None:
    for path in [COMPANION, RESEARCH_OFFICE, SCAFFOLD, VERIFIER]:
        require(path.exists() and path.is_file(), "required file missing: " + str(path))


def check_source_labels_and_references() -> None:
    companion = read(COMPANION)
    research_office = read(RESEARCH_OFFICE)
    combined = companion + "\n" + research_office
    for label in REQUIRED_LABELS:
        require(label in companion, "companion missing low-risk self-fix GUI label: " + label)
        require(label in research_office, "research office missing low-risk self-fix GUI label: " + label)
    for needle in [
        "Self-Fix",
        "_render_ai_growth_gui_low_risk_self_fix_dry_run_visibility",
        "low_risk_self_fix_status_surface.render_status()",
        "self_fix_receipt_viewer.render_receipt_list()",
        "ENGEL_LOW_RISK_SELF_FIX_STATUS_SURFACE_V1.md",
        "ENGEL_LOW_RISK_SELF_FIX_RUNNER_V2.md",
    ]:
        require(needle in combined, "GUI source missing self-fix visibility reference: " + needle)


def check_rendered_self_fix_surface() -> None:
    research_office = load_module("engel_research_office", RESEARCH_OFFICE)
    rendered = research_office.render_ai_growth_gui_tab_text("Self-Fix")
    for label in REQUIRED_LABELS:
        require(label in rendered, "rendered Self-Fix tab missing label: " + label)
    for needle in REQUIRED_SELF_FIX_TEXT + REQUIRED_CLASSES:
        require(needle in rendered, "rendered Self-Fix tab missing text: " + needle)


def check_no_unsafe_gui_actions() -> None:
    for path in [COMPANION, RESEARCH_OFFICE]:
        blocks = marked_blocks(read(path))
        require(blocks.strip(), "no marked AI growth GUI block found in " + str(path))
        for pattern in FORBIDDEN_ACTIVE_PATTERNS:
            require(
                re.search(pattern, blocks) is None,
                "AI growth GUI block contains forbidden active pattern "
                + pattern
                + " in "
                + str(path),
            )
        for label in FORBIDDEN_ACTION_LABELS:
            require(label not in blocks, "AI growth GUI block contains unsafe action label: " + label)


def main() -> int:
    try:
        check_files_exist()
        check_source_labels_and_references()
        check_rendered_self_fix_surface()
        check_no_unsafe_gui_actions()
    except CheckFailure as exc:
        print("[FAIL]", exc)
        return 1
    print("[PASS] Engel low-risk self-fix GUI visibility verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
