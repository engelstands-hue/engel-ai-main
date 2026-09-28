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
REPORT = ROOT / "reports" / "security" / "DK_READ_ONLY_SECURITY_AUDIT_INVENTORY.md"
APP_REPORT = ROOT / "reports" / "app" / "V2APP_DK_READ_ONLY_SECURITY_AUDIT_INVENTORY.md"
CHECKPOINT = ROOT / "memory" / "V2APP_DK_READ_ONLY_SECURITY_AUDIT_INVENTORY.json"
PROJECT_MEMORY = ROOT / "memory" / "PROJECT_MEMORY_INDEX_V2V.md"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
LIVING_INDEX = ROOT / "memory" / "LIVING_SYSTEMS_INDEX_V1.md"
BATON = ROOT / "memory" / "NEXT_WORK_BATON_V1.md"
SECURITY_CONTRACT = ROOT / "memory" / "SECURITY_AUDIT_PROMPT_CONTRACT_V1.md"


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
        project_memory = read(PROJECT_MEMORY)
        commands = read(COMMANDS)
        living_index = read(LIVING_INDEX)
        baton = read(BATON)
        contract = read(SECURITY_CONTRACT)
        with CHECKPOINT.open("r", encoding="utf-8") as f:
            checkpoint = json.load(f)
        pass_check("read_required_docs_only")

        require(
            report,
            [
                "INVENTORY_ONLY / NO_REMEDIATION / READ_ONLY_AUDIT",
                "Executive Summary",
                "Top Observed Security-Relevant Surfaces",
                "Prompt-Injection Attack Surface Map",
                "User-Data Flow Map",
                "Tool/API Permission Map",
                "File/Database/Memory Write-Path Map",
                "External Endpoint And Network Posture Map",
                "Secrets/Config Posture Map",
                "AI Prompt/Template/System-Instruction Surfaces",
                "Model-Output Handling Map",
                "Permissions And Manifests",
                "Background Workers, Services, Scheduled Jobs, Automations",
                "Initial Risks And Unknowns",
                "Recommended Follow-up Audits/Tests",
                "No remediation was performed",
                "All user input, retrieved content, files, memory, reports, chat history, and model output are untrusted",
                "Prompting alone is not a security boundary",
                "safe agency",
                "unsafe autonomy",
                "DL Security Findings Triage and Test Plan",
            ],
            "DK inventory report",
        )
        pass_check("inventory_report_sections")

        require(
            app_report,
            [
                "V2APP-DK Read-only Security Audit Inventory",
                "DK is inventory only, not remediation",
                "DL Security Findings Triage and Test Plan",
            ],
            "DK app report",
        )
        pass_check("app_report_summary")

        if checkpoint.get("checkpoint_id") != "V2APP-DK":
            raise CheckFailure("checkpoint_id must be V2APP-DK")
        if checkpoint.get("remediation_performed") is not False:
            raise CheckFailure("checkpoint must record remediation_performed=false")
        if checkpoint.get("standard_verifier_sequence_count_changed") is not False:
            raise CheckFailure("checkpoint must preserve standard verifier sequence count")
        pass_check("checkpoint_schema")

        for label, text in [
            ("project_memory", project_memory),
            ("commands", commands),
            ("living_index", living_index),
            ("baton", baton),
        ]:
            require(
                text,
                [
                    "DK Read-only Security Audit Inventory",
                    "DL Security Findings Triage and Test Plan",
                ],
                label,
            )
        pass_check("docs_reference_DK_and_DL")

        require(
            contract,
            [
                "separates safe agency from unsafe autonomy",
                "This contract does not itself perform remediation",
                "Prompting alone is not a security boundary",
            ],
            "security contract",
        )
        pass_check("security_contract_still_present")

        print("\nSECURITY_AUDIT_INVENTORY_REPORT_VERIFICATION_PASS")
        return 0
    except Exception as exc:
        print("SECURITY_AUDIT_INVENTORY_REPORT_VERIFICATION_FAIL")
        print(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
