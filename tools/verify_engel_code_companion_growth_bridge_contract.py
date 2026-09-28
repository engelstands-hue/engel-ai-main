#!/usr/bin/env python3
"""Verify Engel Code Companion Growth Bridge Contract V1."""

import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_JSON = ROOT / "memory" / "ENGEL_CODE_COMPANION_GROWTH_BRIDGE_CONTRACT_V1.json"
CONTRACT_MD = ROOT / "memory" / "ENGEL_CODE_COMPANION_GROWTH_BRIDGE_CONTRACT_V1.md"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_CODE_COMPANION_GROWTH_BRIDGE_CONTRACT_V1.md"

REQUIRED_STATUSES = [
    "CONTRACT_ONLY",
    "CODE_COMPANION_GROWTH_BRIDGE_POLICY",
    "BRIDGE_TO_AI_GROWTH",
    "CANDIDATE_PLANNING_ONLY",
    "NO_CODE_MUTATION",
    "NO_AUTO_PATCH",
    "NO_PATCH_APPLY",
    "NO_COMMIT",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_MODEL_RUNTIME",
    "NO_BACKGROUND_WORKER",
    "NO_STARTUP_AUTORUN",
]

REQUIRED_CONNECTIONS = [
    "Engel AI Growth Dashboard",
    "Self-Learning Mini Runner",
    "Bounded Self-Learning Scheduler",
    "Candidate Review Dashboard",
    "Research-to-Fix Loop",
    "Verifier Improvement Candidate",
    "Self-Fix Improvement Candidate",
    "Low-Risk Self-Fix Runner V2",
    "Daily Cycle Runner",
    "Core Continuity Map",
    "Untrusted Content Guard",
    "Prompt Injection Guard",
    "Authority Hierarchy",
]

REQUIRED_BOUNDARIES = [
    "does not mutate code",
    "does not apply patches",
    "does not commit",
    "does not run provider/network/browser",
    "does not write trusted memory",
    "does not activate model runtime",
    "does not bypass guards or authority hierarchy",
    "require review",
]

REQUIRED_BOUNDARY_KEYS = [
    "does_not_mutate_code",
    "does_not_apply_patches",
    "does_not_commit",
    "does_not_run_provider_network_browser",
    "does_not_write_trusted_memory",
    "does_not_activate_model_runtime",
    "does_not_bypass_guards_or_authority_hierarchy",
    "patch_candidates_require_review_or_later_approved_runner",
]

FORBIDDEN_ACTIVE_PATTERNS = [
    r"(?m)^\s*import\s+(requests|urllib|socket|webbrowser|openai|subprocess|os|glob|shutil|threading|multiprocessing)\b",
    r"(?m)^\s*from\s+(requests|urllib|socket|webbrowser|openai|subprocess|os|glob|shutil|threading|multiprocessing)\b",
    r"\.rglob\s*\(",
    r"os\.walk\s*\(",
    r"subprocess\.",
    r"eval\s*\(",
    r"exec\s*\(",
]


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    require(path.exists(), "missing required file: " + str(path))
    return path.read_text(encoding="utf-8")


def check_files() -> None:
    for path in [CONTRACT_JSON, CONTRACT_MD, REPORT]:
        require(path.exists(), "missing required file: " + str(path))


def check_contract_json() -> None:
    data = json.loads(read(CONTRACT_JSON))
    require(data.get("type") == "code_companion_growth_bridge_contract", "contract JSON has wrong type")
    statuses = data.get("status", [])
    for status in REQUIRED_STATUSES:
        require(status in statuses, "contract JSON missing status: " + status)
    connections = "\n".join(data.get("bridge_connections", []))
    for connection in REQUIRED_CONNECTIONS:
        require(connection in connections, "contract JSON missing bridge connection: " + connection)
    boundaries = data.get("boundaries", {})
    for boundary_key in REQUIRED_BOUNDARY_KEYS:
        require(boundaries.get(boundary_key) is True, "contract JSON missing/false boundary: " + boundary_key)


def check_markdown_and_report() -> None:
    text = read(CONTRACT_MD) + "\n" + read(REPORT)
    for status in REQUIRED_STATUSES:
        require(status in text, "contract markdown/report missing status: " + status)
    for connection in REQUIRED_CONNECTIONS:
        require(connection in text, "contract markdown/report missing connection: " + connection)
    for boundary in REQUIRED_BOUNDARIES:
        require(boundary in text, "contract markdown/report missing boundary: " + boundary)
    for phrase in [
        "observe project/code-health signals",
        "find code companion candidates",
        "create patch candidates",
        "create verifier plans",
        "classify risk",
        "prepare future low-risk patch workflows",
        "preserve safety boundaries",
    ]:
        require(phrase in text, "contract markdown/report missing purpose phrase: " + phrase)


def check_no_active_behavior() -> None:
    text = read(CONTRACT_MD) + "\n" + read(REPORT)
    for pattern in FORBIDDEN_ACTIVE_PATTERNS:
        require(not re.search(pattern, text), "contract/report contains active forbidden pattern: " + pattern)


def main() -> int:
    try:
        check_files()
        check_contract_json()
        check_markdown_and_report()
        check_no_active_behavior()
    except CheckFailure as exc:
        print("FAIL: " + str(exc))
        return 1
    print("OK: Engel Code Companion Growth Bridge Contract V1 verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
