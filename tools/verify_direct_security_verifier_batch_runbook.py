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
RUNBOOK = ROOT / "memory" / "DIRECT_SECURITY_VERIFIER_BATCH_RUNBOOK_V1.md"
APP_REPORT = ROOT / "reports" / "app" / "V2APP_DY_DIRECT_SECURITY_VERIFIER_BATCH_RUNBOOK_CONTRACT.md"
CHECKPOINT = ROOT / "memory" / "V2APP_DY_DIRECT_SECURITY_VERIFIER_BATCH_RUNBOOK_CONTRACT.json"
PROJECT_MEMORY = ROOT / "memory" / "PROJECT_MEMORY_INDEX_V2V.md"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
LIVING_INDEX = ROOT / "memory" / "LIVING_SYSTEMS_INDEX_V1.md"
BATON = ROOT / "memory" / "NEXT_WORK_BATON_V1.md"
CHECKLIST = ROOT / "memory" / "STANDARD_VERIFIER_CHECKLIST_V1.md"
ROUTE_MATRIX = ROOT / "memory" / "ROUTE_VERIFICATION_SET_V1.json"

EXPECTED_BATCH = [
    "python .\\tools\\verify_living_systems_documentation_drift.py",
    "python .\\tools\\verify_security_audit_prompt_contract.py",
    "python .\\tools\\verify_security_audit_inventory_report.py",
    "python .\\tools\\verify_security_findings_triage_plan.py",
    "python .\\tools\\verify_security_regression_harness_contract.py",
    "python .\\tools\\verify_security_regression_harness_dry_run.py",
    "python .\\tools\\verify_security_regression_results_review.py",
    "python .\\tools\\verify_security_regression_harness_coverage_contract.py",
    "python .\\tools\\verify_security_regression_harness_results_review.py",
    "python .\\tools\\verify_direct_security_verifier_batch_runbook.py",
]


class CheckFailure(Exception):
    pass


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().replace("/", "\\"))


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
        runbook = read(RUNBOOK)
        app_report = read(APP_REPORT)
        project_memory = read(PROJECT_MEMORY)
        commands = read(COMMANDS)
        living_index = read(LIVING_INDEX)
        baton = read(BATON)
        checklist = read(CHECKLIST)
        route_matrix = read(ROUTE_MATRIX)
        with CHECKPOINT.open("r", encoding="utf-8") as f:
            checkpoint = json.load(f)
        pass_check("read_required_docs_only")

        require(
            runbook,
            [
                "DOCS_CONFIG_ONLY / RUNBOOK_CONTRACT_ONLY / DIRECT_ONLY / NO_PROMOTION",
                "does not create a batch runner script",
                "does not promote security verifiers into the standard eight-verifier sequence",
                "Direct-only Security Verifier Batch",
                "human-invoked runbook guidance only",
                "Direct-only security verifiers should create no files or reports",
                "security harness may create only its approved regression report",
                "baton may create only its approved next-work packet",
                "Stop on first failure",
                "Do not patch automatically",
                "Do not remediate without explicit human approval",
                "EA Permission/Manifest Posture Review Contract",
            ] + EXPECTED_BATCH,
            "DY runbook",
        )
        pass_check("runbook_required_content")

        require(
            app_report,
            [
                "V2APP-DY Direct Security Verifier Batch Runbook Contract",
                "no batch runner script",
                "EA Permission/Manifest Posture Review Contract",
            ],
            "DY app report",
        )
        if checkpoint.get("checkpoint_id") != "V2APP-DY":
            raise CheckFailure("checkpoint_id must be V2APP-DY")
        if checkpoint.get("batch_runner_created") is not False:
            raise CheckFailure("batch_runner_created must be false")
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
            require(text, ["Direct Security Verifier Batch", "EA Permission/Manifest Posture Review Contract"], label)
        pass_check("docs_reference_DY_EA")

        require(route_matrix, ["verify_colony_mycelium_layer_contract.py"], "route matrix")
        if "verify_direct_security_verifier_batch_runbook.py" in route_matrix:
            raise CheckFailure("DY verifier must not be promoted into route matrix standard sequence")
        pass_check("not_promoted_to_standard_sequence")

        print("\nDIRECT_SECURITY_VERIFIER_BATCH_RUNBOOK_VERIFICATION_PASS")
        return 0
    except Exception as exc:
        print("DIRECT_SECURITY_VERIFIER_BATCH_RUNBOOK_VERIFICATION_FAIL")
        print(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
