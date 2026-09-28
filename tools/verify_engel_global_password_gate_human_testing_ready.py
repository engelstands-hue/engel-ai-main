from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
COMPANION = ROOT / "engel_companion.py"
RESEARCH_OFFICE = ROOT / "engel_research_office.py"

REQUIRED_GUI_TEXT = [
    "Global Password Gate Status",
    "Protected Action Registry Summary",
    "Human Testing Panel",
    "HUMAN TESTING READY",
    "PASSWORD REQUIRED FOR PROTECTED ACTIONS",
    "LOCAL ONLY",
    "HASH ONLY",
    "NO PLAINTEXT PASSWORD",
    "STRICT ACTION ALLOWLIST",
    "BLOCKED ACTIONS REMAIN BLOCKED",
    "CONTRACTS STILL REQUIRED",
    "VERIFIERS STILL REQUIRED",
    "AUTHORITY STILL REQUIRED",
    "GUARDS STILL REQUIRED",
    "Human testing is allowed for local password setup/status/verify and protected action visibility.",
    "Write/apply/run actions still require password plus action-specific contracts.",
    "Blocked actions remain blocked even with password.",
    "Password does not bypass contracts, verifiers, guards, or authority hierarchy.",
    "Safe Test Commands",
    "python engel_global_password_gate.py --status",
    "python engel_global_password_gate.py --setup",
    "python engel_global_password_gate.py --verify",
    "python engel_global_password_gate.py --change",
    "python engel_protected_action_registry.py --list",
    "python engel_protected_action_registry.py --show run_code_companion_low_risk_patch_apply",
    "python engel_protected_action_registry.py --show promote_memory_candidate",
    "Safe Refusal Tests",
    "protected apply/write commands refuse without password gate",
    "protected apply/write commands refuse without --password-prompt",
    "blocked actions remain blocked",
    "Password protects actions; it does not bypass safety.",
    "Action IDs use strict allowlists and canonicalization.",
    "SQL-injection-style, Unicode, encoding, whitespace, and prompt-injection bypass attempts are rejected.",
]

FORBIDDEN_ACTIVE_LABELS = [
    "Enable All",
    "Approve All",
    "Unlock All Actions",
    "Bypass Safety",
    "Disable Safety",
    "Grant Full Access",
    "Run All",
    "Apply All",
    "Promote All",
    "Start All",
    "Enable Network",
    "Start Browser",
    "Start Model",
    "Start Worker",
    "Package Refresh",
    "Commit All",
    "Apply Patch",
    "Run Verifier",
    "Execute",
]


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def load_module(name: str, path: Path):
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, "could not load " + name)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def check_source_text() -> None:
    for path in [COMPANION, RESEARCH_OFFICE]:
        text = read(path)
        require("Global Safety" in text, "Global Safety tab missing from " + path.name)
        for needle in REQUIRED_GUI_TEXT:
            require(needle in text, "human testing text missing from " + path.name + ": " + needle)


def check_rendered_status_text() -> None:
    companion = load_module("engel_companion", COMPANION)
    research = load_module("engel_research_office", RESEARCH_OFFICE)
    companion_text = companion.EngelCompanion._render_global_password_action_status(object())
    research_text = research.render_ai_growth_gui_tab_text("Global Safety")
    for label, text in [("Companion", companion_text), ("Research Office", research_text)]:
        for needle in REQUIRED_GUI_TEXT:
            require(needle in text, label + " rendered text missing: " + needle)
        require("Engel AI protected actions" in text, label + " missing Engel AI protected actions")
        require("Code Companion protected actions" in text, label + " missing Code Companion protected actions")
        require("Blocked actions" in text, label + " missing blocked actions")
        for forbidden in FORBIDDEN_ACTIVE_LABELS:
            require(forbidden not in text, label + " rendered unsafe action label: " + forbidden)


def main() -> int:
    try:
        check_source_text()
        check_rendered_status_text()
    except CheckFailure as exc:
        print("[FAIL]", exc)
        return 1
    print("[PASS] Engel global password gate human testing readiness verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
