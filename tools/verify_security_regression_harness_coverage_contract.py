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
CONTRACT = ROOT / "memory" / "SECURITY_REGRESSION_HARNESS_COVERAGE_EXPANSION_CONTRACT_V1.md"
REPORT = ROOT / "reports" / "security" / "DP_SECURITY_REGRESSION_HARNESS_COVERAGE_EXPANSION_CONTRACT.md"
APP_REPORT = ROOT / "reports" / "app" / "V2APP_DP_SECURITY_REGRESSION_HARNESS_COVERAGE_EXPANSION_CONTRACT.md"
CHECKPOINT = ROOT / "memory" / "V2APP_DP_SECURITY_REGRESSION_HARNESS_COVERAGE_EXPANSION_CONTRACT.json"
DO_REPORT = ROOT / "reports" / "security" / "DO_SECURITY_REGRESSION_RESULTS_REVIEW_AND_REMEDIATION_QUEUE.md"
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
        contract = read(CONTRACT)
        report = read(REPORT)
        app_report = read(APP_REPORT)
        do_report = read(DO_REPORT)
        project_memory = read(PROJECT_MEMORY)
        commands = read(COMMANDS)
        living_index = read(LIVING_INDEX)
        baton = read(BATON)
        checklist = read(CHECKLIST)
        with CHECKPOINT.open("r", encoding="utf-8") as f:
            checkpoint = json.load(f)
        pass_check("read_required_docs_only")

        required_coverage = [
            "prompt injection via memory docs",
            "prompt injection via generated reports",
            "malicious markdown links/images",
            "fake tool-call text",
            "malicious file paths",
            "suspicious URLs",
            "command-like model output",
            "attempts to request env vars/secrets/logs",
            "attempts to trigger provider/network behavior",
            "attempts to trigger trusted writes",
            "attempts to mutate queues/digest/history/ALIVE_STATE",
            "attempts to bypass local-only/offline posture",
        ]
        require(
            contract,
            [
                "Security Regression Harness Coverage Expansion Contract V1",
                "CONTRACT_ONLY / DOCS_CONFIG_ONLY / NO_HARNESS_EXPANSION_IN_DP",
                "synthetic fixtures only",
                "reports\\security\\regression\\",
                "Do not modify the harness runner in DP",
                "DQ Implement Expanded Security Regression Harness Dry Run",
            ]
            + required_coverage,
            "DP coverage contract",
        )
        pass_check("contract_required_content")

        require(
            report,
            [
                "DP Security Regression Harness Coverage Expansion Contract",
                "contract-only",
                "No harness expansion was implemented in DP",
                "DQ Implement Expanded Security Regression Harness Dry Run",
            ]
            + required_coverage,
            "DP report",
        )
        require(
            app_report,
            [
                "V2APP-DP Security Regression Harness Coverage Expansion Contract",
                "DP is contract-only",
                "DQ Implement Expanded Security Regression Harness Dry Run",
            ],
            "DP app report",
        )
        require(
            do_report,
            [
                "DO Security Regression Results Review and Remediation Queue",
                "DP Security Regression Harness Coverage Expansion Contract",
            ],
            "DO source report",
        )
        pass_check("reports_summarize_contract")

        if checkpoint.get("checkpoint_id") != "V2APP-DP":
            raise CheckFailure("checkpoint_id must be V2APP-DP")
        if checkpoint.get("harness_expansion_implemented") is not False:
            raise CheckFailure("harness_expansion_implemented must be false for DP")
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
                    "DP",
                    "Coverage Expansion",
                    "DQ",
                    "expanded",
                    "eight verifiers",
                ],
                label,
            )
        pass_check("docs_reference_DP_and_DQ")

        print("\nSECURITY_REGRESSION_HARNESS_COVERAGE_CONTRACT_VERIFICATION_PASS")
        return 0
    except Exception as exc:
        print("SECURITY_REGRESSION_HARNESS_COVERAGE_CONTRACT_VERIFICATION_FAIL")
        print(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
