from __future__ import annotations

import json
import re
from pathlib import Path


_file = globals().get("__file__")
if not _file or not isinstance(_file, str) or _file.startswith("<"):
    ROOT = Path.cwd()
else:
    try:
        ROOT = Path(_file).resolve().parents[1]
    except (OSError, ValueError, IndexError):
        ROOT = Path.cwd()
CONTRACT = ROOT / "memory" / "SECURITY_REGRESSION_HARNESS_CONTRACT_V1.md"
REPORT = ROOT / "reports" / "security" / "DM_SECURITY_REGRESSION_HARNESS_CONTRACT.md"
APP_REPORT = ROOT / "reports" / "app" / "V2APP_DM_SECURITY_REGRESSION_HARNESS_CONTRACT.md"
CHECKPOINT = ROOT / "memory" / "V2APP_DM_SECURITY_REGRESSION_HARNESS_CONTRACT.json"
PROJECT_MEMORY = ROOT / "memory" / "PROJECT_MEMORY_INDEX_V2V.md"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
LIVING_INDEX = ROOT / "memory" / "LIVING_SYSTEMS_INDEX_V1.md"
BATON = ROOT / "memory" / "NEXT_WORK_BATON_V1.md"
CHECKLIST = ROOT / "memory" / "STANDARD_VERIFIER_CHECKLIST_V1.md"
SECURITY_CONTRACT = ROOT / "memory" / "SECURITY_AUDIT_PROMPT_CONTRACT_V1.md"
DK_INVENTORY = ROOT / "reports" / "security" / "DK_READ_ONLY_SECURITY_AUDIT_INVENTORY.md"
DL_TRIAGE = ROOT / "reports" / "security" / "DL_SECURITY_FINDINGS_TRIAGE_AND_TEST_PLAN.md"
FUTURE_RUNNER = ROOT / "tools" / "run_security_regression_harness.py"
DN_CHECKPOINT = ROOT / "memory" / "V2APP_DN_SECURITY_REGRESSION_HARNESS_DRY_RUN.json"


class CheckFailure(Exception):
    pass


def normalize(text: str) -> str:
    lowered = text.lower().replace("/", "\\")
    return re.sub(r"\s+", " ", lowered)


def read(path: Path) -> str:
    if not path.exists():
        raise CheckFailure(f"missing required file: {path}")
    return path.read_text(encoding="utf-8")


def require(text: str, needles: list[str], label: str) -> None:
    haystack = normalize(text)
    missing = [needle for needle in needles if normalize(needle) not in haystack]
    if missing:
        raise CheckFailure(label + " missing: " + ", ".join(missing))


def pass_check(name: str) -> None:
    print(f"PASS {name}")


def main() -> int:
    try:
        contract = read(CONTRACT)
        report = read(REPORT)
        app_report = read(APP_REPORT)
        project_memory = read(PROJECT_MEMORY)
        commands = read(COMMANDS)
        living_index = read(LIVING_INDEX)
        baton = read(BATON)
        checklist = read(CHECKLIST)
        security_contract = read(SECURITY_CONTRACT)
        dk_inventory = read(DK_INVENTORY)
        dl_triage = read(DL_TRIAGE)
        with CHECKPOINT.open("r", encoding="utf-8") as f:
            checkpoint = json.load(f)
        pass_check("read_required_docs_only")

        require(
            contract,
            [
                "DOCS_CONFIG_ONLY / HARNESS_CONTRACT_ONLY / NO_REMEDIATION / NO_RUNTIME_BEHAVIOR",
                "The security regression harness is not implemented in DM",
                "python .\\tools\\run_security_regression_harness.py --dry-run",
                "The runner above must not be created in DM",
                "Direct prompt-injection tests",
                "Indirect prompt-injection tests",
                "Second-order prompt-injection tests",
                "User-data access/exfiltration tests",
                "Unsafe tool/agency tests",
                "Secrets/config/logging tests",
                "Network/offline-mode boundary tests",
                "Model-output rendering/storage/tool-argument tests",
                "Permission/manifest tests",
                "Background worker/loop/automation tests",
                "use synthetic data only",
                "use no real user secrets",
                "use no real credentials",
                "make no external network calls",
                "perform no destructive file operations",
                "reports\\security\\regression\\",
                "untrusted input must never become trusted instructions",
                "model output must be treated as untrusted",
                "sensitive actions require explicit human approval",
                "read-only/status routes must create no files or reports",
                "report-only paths may create only approved report artifacts",
                "local-only/offline mode must not be bypassed",
                "no hidden provider/API/network calls",
                "no background workers, loops, queues, or self-advancing baton behavior",
                "DI, DJ, DK, DL, and DM verifiers remain direct-only",
                "The standard verifier sequence remains at eight verifiers",
                "DN Implement Read-only Security Regression Harness Dry Run",
            ],
            "DM contract",
        )
        pass_check("contract_required_content")

        require(
            report,
            [
                "DM Security Regression Harness Contract",
                "CONTRACT_ONLY / DOCS_CONFIG_ONLY / NO_REMEDIATION / NO_HARNESS_RUNNER",
                "DM does not create that runner",
                "DN Implement Read-only Security Regression Harness Dry Run",
            ],
            "DM security report",
        )
        require(
            app_report,
            [
                "V2APP-DM Security Regression Harness Contract",
                "DM is contract and planning only",
                "DN Implement Read-only Security Regression Harness Dry Run",
            ],
            "DM app report",
        )
        pass_check("reports_summarize_contract")

        if FUTURE_RUNNER.exists() and not DN_CHECKPOINT.exists():
            raise CheckFailure("future harness runner must not exist before a later DN checkpoint")
        if checkpoint.get("checkpoint_id") != "V2APP-DM":
            raise CheckFailure("checkpoint_id must be V2APP-DM")
        if checkpoint.get("future_harness_implemented") is not False:
            raise CheckFailure("future_harness_implemented must be false")
        if checkpoint.get("future_harness_runner_created") is not False:
            raise CheckFailure("future_harness_runner_created must be false")
        if checkpoint.get("remediation_performed") is not False:
            raise CheckFailure("remediation_performed must be false")
        if checkpoint.get("standard_verifier_sequence_count_changed") is not False:
            raise CheckFailure("standard verifier count must remain unchanged")
        if checkpoint.get("route_matrix_modified") is not False:
            raise CheckFailure("route matrix must not be modified in DM")
        pass_check("checkpoint_schema_and_runner_absent_or_later_DN")

        for label, text in [
            ("project_memory", project_memory),
            ("commands", commands),
            ("living_index", living_index),
            ("baton", baton),
            ("checklist", checklist),
        ]:
            require(
                text,
                [
                    "DM Security Regression Harness Contract",
                    "DN Implement Read-only Security Regression Harness Dry Run",
                    "standard verifier sequence",
                    "eight verifiers",
                ],
                label,
            )
        pass_check("docs_reference_DM_and_DN")

        require(
            security_contract,
            [
                "separates safe agency from unsafe autonomy",
                "This contract does not itself perform remediation",
                "Prompting alone is not a security boundary",
            ],
            "DJ security contract",
        )
        require(
            dk_inventory,
            [
                "DK Read-only Security Audit Inventory",
                "No remediation was performed",
            ],
            "DK inventory",
        )
        require(
            dl_triage,
            [
                "DL Security Findings Triage and Test Plan",
                "DM Security Regression Harness Contract",
            ],
            "DL triage",
        )
        pass_check("source_inputs_still_present")

        print("\nSECURITY_REGRESSION_HARNESS_CONTRACT_VERIFICATION_PASS")
        return 0
    except Exception as exc:
        print("SECURITY_REGRESSION_HARNESS_CONTRACT_VERIFICATION_FAIL")
        print(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
