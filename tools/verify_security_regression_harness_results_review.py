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
REPORT = ROOT / "reports" / "security" / "DR_SECURITY_REGRESSION_HARNESS_RESULTS_REVIEW.md"
APP_REPORT = ROOT / "reports" / "app" / "V2APP_DR_SECURITY_REGRESSION_HARNESS_RESULTS_REVIEW.md"
CHECKPOINT = ROOT / "memory" / "V2APP_DR_SECURITY_REGRESSION_HARNESS_RESULTS_REVIEW.json"
DN_REPORT = ROOT / "reports" / "security" / "regression" / "DN_SECURITY_REGRESSION_DRY_RUN.md"
DQ_REPORT = ROOT / "reports" / "security" / "regression" / "DQ_SECURITY_REGRESSION_EXPANDED_DRY_RUN.md"
PROJECT_MEMORY = ROOT / "memory" / "PROJECT_MEMORY_INDEX_V2V.md"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
LIVING_INDEX = ROOT / "memory" / "LIVING_SYSTEMS_INDEX_V1.md"
BATON = ROOT / "memory" / "NEXT_WORK_BATON_V1.md"
CHECKLIST = ROOT / "memory" / "STANDARD_VERIFIER_CHECKLIST_V1.md"


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
        report = read(REPORT)
        app_report = read(APP_REPORT)
        dn_report = read(DN_REPORT)
        dq_report = read(DQ_REPORT)
        project_memory = read(PROJECT_MEMORY)
        commands = read(COMMANDS)
        living_index = read(LIVING_INDEX)
        baton = read(BATON)
        checklist = read(CHECKLIST)
        with CHECKPOINT.open("r", encoding="utf-8") as f:
            checkpoint = json.load(f)
        pass_check("read_required_docs_only")

        require(
            report,
            [
                "DR Security Regression Harness Results Review",
                "RESULTS_REVIEW_ONLY / NO_REMEDIATION",
                "DN vs DQ Comparison",
                "Coverage Improved",
                "Remaining Gaps",
                "Updated Remediation Queue",
                "First Approved Low-Risk Hardening Candidate",
                "No remediation was performed in DR",
                "DS First Approved Low-Risk Security Hardening Patch",
                "DU Security Docs and Command Navigation Refresh",
            ],
            "DR report",
        )
        for label in ["DR-Q1", "DR-Q2", "DR-Q3", "DR-Q4", "DR-Q5"]:
            require(
                report,
                [
                    label,
                    "Severity:",
                    "Evidence:",
                    "Proposed future test:",
                    "Proposed remediation direction:",
                    "Human approval required:",
                ],
                "DR queue item",
            )
        pass_check("review_report_shape")

        require(
            app_report,
            [
                "V2APP-DR Security Regression Harness Results Review",
                "DR performs no remediation",
                "DU Security Docs and Command Navigation Refresh",
            ],
            "DR app report",
        )
        require(dn_report, ["DN Security Regression Harness Dry Run"], "DN report")
        require(dq_report, ["DQ Security Regression Expanded Dry Run", "DN vs DQ Coverage Comparison"], "DQ report")
        pass_check("source_reports_present")

        if checkpoint.get("checkpoint_id") != "V2APP-DR":
            raise CheckFailure("checkpoint_id must be V2APP-DR")
        if checkpoint.get("remediation_performed") is not False:
            raise CheckFailure("remediation_performed must be false")
        if checkpoint.get("standard_verifier_sequence_count_changed") is not False:
            raise CheckFailure("standard verifier count must remain unchanged")
        pass_check("checkpoint_schema")

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
                    "DR",
                    "Results Review",
                    "DU",
                    "Security Docs",
                    "eight verifiers",
                ],
                label,
            )
        pass_check("docs_reference_DR_and_DU")

        print("\nSECURITY_REGRESSION_HARNESS_RESULTS_REVIEW_VERIFICATION_PASS")
        return 0
    except Exception as exc:
        print("SECURITY_REGRESSION_HARNESS_RESULTS_REVIEW_VERIFICATION_FAIL")
        print(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
