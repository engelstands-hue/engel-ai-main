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
REPORT = ROOT / "reports" / "security" / "DO_SECURITY_REGRESSION_RESULTS_REVIEW_AND_REMEDIATION_QUEUE.md"
APP_REPORT = ROOT / "reports" / "app" / "V2APP_DO_SECURITY_REGRESSION_RESULTS_REVIEW_AND_REMEDIATION_QUEUE.md"
CHECKPOINT = ROOT / "memory" / "V2APP_DO_SECURITY_REGRESSION_RESULTS_REVIEW_AND_REMEDIATION_QUEUE.json"
DN_REPORT = ROOT / "reports" / "security" / "regression" / "DN_SECURITY_REGRESSION_DRY_RUN.md"
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
                "DO Security Regression Results Review and Remediation Queue",
                "REVIEW_ONLY / NO_REMEDIATION / REMEDIATION_QUEUE_ONLY",
                "DN Result Classification",
                "Prioritized Remediation Queue",
                "Confirmed Results",
                "Needs Review",
                "Unknown Or Not Covered",
                "No remediation was performed in DO",
                "DP Security Regression Harness Coverage Expansion Contract",
            ],
            "DO report",
        )
        for label in ["DO-Q1", "DO-Q2", "DO-Q3", "DO-Q4", "DO-Q5"]:
            require(
                report,
                [
                    label,
                    "Severity:",
                    "Evidence:",
                    "Affected surfaces/files:",
                    "Prompt-injection relevance:",
                    "User-data relevance:",
                    "Unsafe-agency relevance:",
                    "Proposed remediation direction:",
                    "Proposed verification test:",
                    "Human approval required:",
                ],
                "DO queue item",
            )
        pass_check("review_report_shape")

        require(
            app_report,
            [
                "V2APP-DO Security Regression Results Review and Remediation Queue",
                "DO performs no remediation",
                "DP Security Regression Harness Coverage Expansion Contract",
            ],
            "DO app report",
        )
        require(
            dn_report,
            [
                "Overall status: PASS_WITH_NEEDS_REVIEW_NOTES",
                "Permission/manifest expectations",
            ],
            "DN source report",
        )
        pass_check("source_report_and_app_summary")

        if checkpoint.get("checkpoint_id") != "V2APP-DO":
            raise CheckFailure("checkpoint_id must be V2APP-DO")
        if checkpoint.get("remediation_performed") is not False:
            raise CheckFailure("remediation_performed must be false")
        if checkpoint.get("runtime_behavior_changed") is not False:
            raise CheckFailure("runtime_behavior_changed must be false")
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
                    "DO",
                    "Results Review",
                    "DP",
                    "Coverage Expansion",
                    "no remediation",
                    "eight verifiers",
                ],
                label,
            )
        pass_check("docs_reference_DO_and_DP")

        print("\nSECURITY_REGRESSION_RESULTS_REVIEW_VERIFICATION_PASS")
        return 0
    except Exception as exc:
        print("SECURITY_REGRESSION_RESULTS_REVIEW_VERIFICATION_FAIL")
        print(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
