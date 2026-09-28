from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_JSON = ROOT / "memory" / "ENGEL_BACKGROUND_WORKER_STARTUP_AUTORUN_CONTRACT_V1.json"
CONTRACT_MD = ROOT / "memory" / "ENGEL_BACKGROUND_WORKER_STARTUP_AUTORUN_CONTRACT_V1.md"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_BACKGROUND_WORKER_STARTUP_AUTORUN_CONTRACT_V1.md"

REQUIRED_STATUSES = [
    "CONTRACT_ONLY",
    "BACKGROUND_WORKER_POLICY",
    "STARTUP_AUTORUN_POLICY",
    "DISABLED_BY_DEFAULT",
    "HUMAN_ENABLE_REQUIRED",
    "PASSWORD_GATE_REQUIRED",
    "PROTECTED_ACTION_REGISTRY_REQUIRED",
    "BOUNDED_WORKERS_ONLY",
    "RECEIPT_REQUIRED",
    "TIME_LIMIT_REQUIRED",
    "RESOURCE_LIMITS_REQUIRED",
    "KILL_SWITCH_REQUIRED",
    "STARTUP_AUTORUN_DISABLED_BY_DEFAULT",
    "NO_STARTUP_AUTORUN_INSTALL",
    "NO_STARTUP_AUTORUN_INSTALL_BY_DEFAULT",
    "NO_ENDLESS_LOOP",
    "NO_HIDDEN_AUTONOMY",
    "NO_PROVIDER_CALLS_BY_DEFAULT",
    "NO_NETWORK_BY_DEFAULT",
    "NO_BROWSER_BY_DEFAULT",
    "NO_MODEL_RUNTIME_BY_DEFAULT",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_SOURCE_MUTATION",
    "NO_PATCH_APPLY",
    "NO_CODE_COMPANION_PATCH_APPLY_BY_DEFAULT",
    "NO_PACKAGE_REFRESH",
]

REQUIRED_TEXT = [
    "Workers are disabled by default.",
    "Startup autorun is disabled by default.",
    "Startup autorun install is not allowed in V1.",
    "Global Password Gate verification is required",
    "Protected Action Registry entries are required.",
    "receipts",
    "kill switch",
    "endless loops",
    "hidden autonomy",
    "provider calls by default",
    "network by default",
    "browser by default",
    "model runtime by default",
    "trusted-memory write",
    "source mutation",
    "patch apply",
    "Code Companion patch apply by default",
    "package refresh",
    "Research Toggle Overnight Worker V1 is governed by this contract",
    "does not install startup autorun",
]


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def check_files() -> None:
    for path in [CONTRACT_JSON, CONTRACT_MD]:
        require(path.exists() and path.is_file(), "required contract file missing: " + str(path.relative_to(ROOT)))


def check_contract() -> None:
    data = json.loads(read(CONTRACT_JSON))
    md = read(CONTRACT_MD)
    combined = md + "\n" + json.dumps(data, sort_keys=True)
    require(data.get("type") == "background_worker_startup_autorun_contract", "contract type mismatch")
    for status in REQUIRED_STATUSES:
        require(status in combined, "required background/startup status missing: " + status)
    for needle in REQUIRED_TEXT:
        require(needle in combined, "required background/startup text missing: " + needle)
    policy = data.get("policy", {})
    require(policy.get("workers_disabled_by_default") is True, "workers_disabled_by_default must be true")
    require(policy.get("startup_autorun_disabled_by_default") is True, "startup_autorun_disabled_by_default must be true")
    require(policy.get("startup_autorun_install_allowed_v1") is False, "startup autorun install must be disallowed")
    require(policy.get("password_gate_required_for_enable") is True, "password gate required for enable missing")
    require(policy.get("protected_action_registry_required") is True, "protected registry requirement missing")
    require(policy.get("receipts_required_for_worker_runs") is True, "receipt requirement missing")
    require(policy.get("kill_switch_required") is True, "kill switch requirement missing")
    require(policy.get("endless_loop_allowed") is False, "endless loop must be disallowed")
    require(policy.get("hidden_autonomy_allowed") is False, "hidden autonomy must be disallowed")


def check_report_if_present() -> None:
    if not REPORT.exists():
        return
    text = read(REPORT)
    for needle in [
        "Engel Background Worker and Startup Autorun Contract V1",
        "contract summary",
        "disabled by default",
        "password gate required",
        "kill switch required",
        "no actual startup autorun was installed",
        "no unbounded background loop was started",
        "packaging skipped",
    ]:
        require(needle in text, "background/startup report missing text: " + needle)


def main() -> int:
    try:
        check_files()
        check_contract()
        check_report_if_present()
    except CheckFailure as exc:
        print("[FAIL]", exc)
        return 1
    print("[PASS] Engel Background Worker and Startup Autorun Contract verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
