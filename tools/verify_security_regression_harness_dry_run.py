from __future__ import annotations

import ast
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
HARNESS = ROOT / "tools" / "run_security_regression_harness.py"
DN_REPORT = ROOT / "reports" / "security" / "regression" / "DN_SECURITY_REGRESSION_DRY_RUN.md"
DQ_REPORT = ROOT / "reports" / "security" / "regression" / "DQ_SECURITY_REGRESSION_EXPANDED_DRY_RUN.md"
EO_REPORT = ROOT / "reports" / "security" / "regression" / "EO_PROMPT_INJECTION_FIXTURE_DRY_RUN.md"
EY_REPORT = ROOT / "reports" / "security" / "regression" / "EY_TRUSTED_MEMORY_FIXTURE_DRY_RUN.md"
DN_APP_REPORT = ROOT / "reports" / "app" / "V2APP_DN_SECURITY_REGRESSION_HARNESS_DRY_RUN.md"
DQ_APP_REPORT = ROOT / "reports" / "app" / "V2APP_DQ_SECURITY_REGRESSION_EXPANDED_DRY_RUN.md"
EO_APP_REPORT = ROOT / "reports" / "app" / "V2APP_EO_PROMPT_INJECTION_FIXTURE_DRY_RUN.md"
EY_APP_REPORT = ROOT / "reports" / "app" / "V2APP_EY_TRUSTED_MEMORY_FIXTURE_DRY_RUN.md"
DN_CHECKPOINT = ROOT / "memory" / "V2APP_DN_SECURITY_REGRESSION_HARNESS_DRY_RUN.json"
DQ_CHECKPOINT = ROOT / "memory" / "V2APP_DQ_SECURITY_REGRESSION_EXPANDED_DRY_RUN.json"
EO_CHECKPOINT = ROOT / "memory" / "V2APP_EO_PROMPT_INJECTION_FIXTURE_DRY_RUN.json"
EY_CHECKPOINT = ROOT / "memory" / "V2APP_EY_TRUSTED_MEMORY_FIXTURE_DRY_RUN.json"
CONTRACT = ROOT / "memory" / "SECURITY_REGRESSION_HARNESS_CONTRACT_V1.md"
COVERAGE_CONTRACT = ROOT / "memory" / "SECURITY_REGRESSION_HARNESS_COVERAGE_EXPANSION_CONTRACT_V1.md"
PROMPT_FIXTURE_CONTRACT = ROOT / "memory" / "PROMPT_INJECTION_REGRESSION_FIXTURE_CONTRACT_V1.md"
TRUSTED_MEMORY_FIXTURE_CONTRACT = ROOT / "memory" / "TRUSTED_MEMORY_WRITE_PATH_REGRESSION_FIXTURE_CONTRACT_V1.md"
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


def verify_harness_source(source: str) -> None:
    forbidden_imports = {
        "requests",
        "urllib",
        "httpx",
        "socket",
        "smtplib",
        "imaplib",
        "poplib",
        "ftplib",
        "webbrowser",
        "subprocess",
        "threading",
        "multiprocessing",
        "asyncio",
        "sched",
        "time",
        "selenium",
    }
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_name = alias.name.split(".")[0]
                if root_name in forbidden_imports:
                    raise CheckFailure(f"harness imports forbidden module: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            root_name = (node.module or "").split(".")[0]
            if root_name in forbidden_imports:
                raise CheckFailure(f"harness imports forbidden module: {node.module}")

    forbidden_source_patterns = [
        r"\bwhile\s+True\b",
        r"\binput\s*\(",
        r"\bexec\s*\(",
        r"\beval\s*\(",
        r"\bcompile\s*\(",
        r"\b__import__\s*\(",
        r"\bengel_app\b",
        r"\broute_regression_status\b",
        r"\bverification_set_status\b",
        r"\bmake_next_work_baton\b",
        r"\bStart-Job\b",
        r"\bRegister-ObjectEvent\b",
        r"\b" + "Ol" + "lama" + r"\b",
        r"localhost:" + "11" + "434",
    ]
    for pattern in forbidden_source_patterns:
        if re.search(pattern, source, flags=re.IGNORECASE):
            raise CheckFailure(f"harness source contains forbidden behavior pattern: {pattern}")

    allowed_write = 'REPORT.write_text(build_report(), encoding="utf-8")'
    if "write_text" in source and allowed_write not in source:
        raise CheckFailure("harness may only write the selected allowed regression report")
    if "mkdir(" in source and "REPORT.parent.mkdir(parents=True, exist_ok=True)" not in source:
        raise CheckFailure("harness may only create the allowed regression output folder")
    if "EY_TRUSTED_MEMORY_FIXTURE_DRY_RUN.md" not in source:
        raise CheckFailure("harness must target the current EY trusted-memory fixture dry-run report")


def main() -> int:
    try:
        harness_source = read(HARNESS)
        dn_report = read(DN_REPORT)
        dq_report = read(DQ_REPORT)
        eo_report = read(EO_REPORT)
        ey_report = read(EY_REPORT)
        dn_app_report = read(DN_APP_REPORT)
        dq_app_report = read(DQ_APP_REPORT)
        eo_app_report = read(EO_APP_REPORT)
        ey_app_report = read(EY_APP_REPORT)
        contract = read(CONTRACT)
        coverage_contract = read(COVERAGE_CONTRACT)
        prompt_fixture_contract = read(PROMPT_FIXTURE_CONTRACT)
        trusted_memory_fixture_contract = read(TRUSTED_MEMORY_FIXTURE_CONTRACT)
        project_memory = read(PROJECT_MEMORY)
        commands = read(COMMANDS)
        living_index = read(LIVING_INDEX)
        baton = read(BATON)
        checklist = read(CHECKLIST)
        with DN_CHECKPOINT.open("r", encoding="utf-8") as f:
            dn_checkpoint = json.load(f)
        with DQ_CHECKPOINT.open("r", encoding="utf-8") as f:
            dq_checkpoint = json.load(f)
        with EO_CHECKPOINT.open("r", encoding="utf-8") as f:
            eo_checkpoint = json.load(f)
        with EY_CHECKPOINT.open("r", encoding="utf-8") as f:
            ey_checkpoint = json.load(f)
        pass_check("read_required_docs_only")

        verify_harness_source(harness_source)
        pass_check("harness_source_static_safety")

        require(
            dn_report,
            [
                "DN Security Regression Harness Dry Run",
                "READ_ONLY_DRY_RUN / SYNTHETIC_DATA_ONLY / NO_REMEDIATION",
                "Synthetic Fixture List",
                "No remediation was performed",
                "Only the allowed regression report was written",
                "Overall status: PASS_WITH_NEEDS_REVIEW_NOTES",
            ],
            "DN dry-run report",
        )
        pass_check("dn_report_content")

        require(
            dq_report,
            [
                "DQ Security Regression Expanded Dry Run",
                "READ_ONLY_DRY_RUN / SYNTHETIC_DATA_ONLY / EXPANDED_COVERAGE / NO_REMEDIATION",
                "DN vs DQ Coverage Comparison",
                "Synthetic Fixture List",
                "Test Category Results",
                "No remediation was performed",
                "Only the allowed regression report was written",
                "safe agency = observe, reflect, summarize, propose, ask, verify, record approved outcomes",
                "unsafe autonomy = hidden mutation, silent tools, provider/network calls, background loops, queue mutation, unapproved trusted writes, exfiltration, deletion, or sensitive action from untrusted/model text",
            ],
            "DQ expanded dry-run report",
        )
        for category in [
            "Direct prompt injection",
            "Indirect prompt injection",
            "Second-order prompt injection",
            "User-data access/exfiltration",
            "Unsafe tool/agency behavior",
            "Secrets/config/logging",
            "Network/offline-mode boundary",
            "Model-output handling",
            "Permission/manifest expectations",
            "Background worker/loop/automation expectations",
            "Prompt injection via memory docs",
            "Prompt injection via generated reports",
            "Malicious markdown links/images",
            "Fake tool-call text",
            "Malicious file paths",
            "Suspicious URLs",
            "Command-like model output",
            "Environment, secret, and log access attempts",
            "Provider/network trigger attempts",
            "Trusted write trigger attempts",
            "Queue digest history ALIVE_STATE mutation attempts",
            "Local-only offline posture bypass attempts",
        ]:
            require(dq_report, [category], "DQ report categories")
        pass_check("dq_report_content")

        require(
            eo_report,
            [
                "EO Prompt Injection Fixture Dry Run",
                "READ_ONLY_DRY_RUN / SYNTHETIC_DATA_ONLY / PROMPT_INJECTION_FIXTURE_COVERAGE / NO_REMEDIATION",
                "DN vs DQ vs EO Coverage Comparison",
                "Synthetic Fixture List",
                "Test Category Results",
                "No remediation was performed",
                "Only the allowed regression report was written",
                "safe agency = observe, reflect, summarize, propose, ask, verify, record approved outcomes",
                "unsafe autonomy = hidden mutation, silent tools, provider/network calls, background loops, queue mutation, unapproved trusted writes, exfiltration, deletion, or sensitive action from untrusted/model text",
            ],
            "EO prompt-injection fixture dry-run report",
        )
        for category in [
            "User direct injection fixture",
            "Malicious memory doc fixture",
            "Malicious report text fixture",
            "Malicious baton-like text fixture",
            "Malicious markdown/link/image fixture",
            "Malicious model output fixture",
            "Fake tool-call request fixture",
            "Hidden prompt and secrets request fixture",
            "Unsafe autonomy request fixture",
            "Local-only bypass request fixture",
            "Malicious retrieved research text fixture",
            "Malicious Discord-like message fixture",
            "Malicious Discord export/log snippet fixture",
            "Malicious Discord bot output fixture",
            "Malicious Discord moderator-style instruction fixture",
            "Malicious copied chat summary fixture",
            "Second-order Discord instruction fixture",
            "Repeated prompt-injection flood fixture",
            "Repeated fake tool-call flood fixture",
            "Copied/exported chat-log flood fixture",
            "Large pasted instruction-like block fixture",
            "Bulk malicious research excerpt fixture",
            "Model-output spam fixture",
            "Baton-like command flood fixture",
            "Report/log bloat pressure fixture",
        ]:
            require(eo_report, [category], "EO report categories")
        pass_check("eo_report_content")

        require(
            ey_report,
            [
                "EY Trusted Memory Fixture Dry Run",
                "READ_ONLY_DRY_RUN / SYNTHETIC_DATA_ONLY / TRUSTED_MEMORY_FIXTURE_COVERAGE / NO_REMEDIATION",
                "DN vs DQ vs EO vs EY Coverage Comparison",
                "Synthetic Fixture List",
                "Test Category Results",
                "No remediation was performed",
                "Only the allowed regression report was written",
                "safe agency = observe, reflect, summarize, propose, ask, verify, record approved outcomes",
                "unsafe autonomy = hidden mutation, silent tools, provider/network calls, background loops, queue mutation, unapproved trusted writes, exfiltration, deletion, or sensitive action from untrusted/model text",
            ],
            "EY trusted-memory fixture dry-run report",
        )
        for category in [
            "Malicious user request to write trusted memory",
            "Malicious copied chat asking for memory mutation",
            "Malicious Discord-like trusted-write instruction",
            "Malicious retrieved research text as instruction",
            "Malicious report text as authority",
            "Malicious checkpoint text asking queue mutation",
            "Malicious baton-like trusted-write instruction",
            "Malicious model output suggesting lesson apply",
            "Fake verifier output demanding memory write",
            "Fake route output demanding queue mutation",
            "Repeated memory-write instruction flood",
            "Repeated ALIVE_STATE mutation flood",
            "Malicious digest/history write request",
            "Self-approving proposal/lesson candidate",
        ]:
            require(ey_report, [category], "EY report categories")
        pass_check("ey_report_content")

        require(
            dn_app_report,
            [
                "V2APP-DN Security Regression Harness Dry Run",
                "DO Security Regression Results Review and Remediation Queue",
            ],
            "DN app report",
        )
        require(
            dq_app_report,
            [
                "V2APP-DQ Security Regression Expanded Dry Run",
                "DP-approved expanded dry-run coverage",
                "DR Security Regression Harness Results Review",
            ],
            "DQ app report",
        )
        require(
            eo_app_report,
            [
                "V2APP-EO Prompt Injection Fixture Dry Run",
                "EN-approved synthetic prompt-injection fixture coverage",
                "EP Prompt Injection Fixture Results Review",
            ],
            "EO app report",
        )
        require(
            ey_app_report,
            [
                "V2APP-EY Trusted Memory Fixture Dry Run",
                "EX-approved bounded synthetic trusted-memory/write-path fixture coverage",
                "EZ Trusted Memory Fixture Results Review",
            ],
            "EY app report",
        )
        pass_check("app_report_summaries")

        if dn_checkpoint.get("checkpoint_id") != "V2APP-DN":
            raise CheckFailure("DN checkpoint_id must be V2APP-DN")
        if dq_checkpoint.get("checkpoint_id") != "V2APP-DQ":
            raise CheckFailure("DQ checkpoint_id must be V2APP-DQ")
        if eo_checkpoint.get("checkpoint_id") != "V2APP-EO":
            raise CheckFailure("EO checkpoint_id must be V2APP-EO")
        if ey_checkpoint.get("checkpoint_id") != "V2APP-EY":
            raise CheckFailure("EY checkpoint_id must be V2APP-EY")
        for label, checkpoint in [("DN", dn_checkpoint), ("DQ", dq_checkpoint), ("EO", eo_checkpoint), ("EY", ey_checkpoint)]:
            if checkpoint.get("remediation_performed") is not False:
                raise CheckFailure(f"{label} remediation_performed must be false")
            if checkpoint.get("standard_verifier_sequence_count_changed") is not False:
                raise CheckFailure(f"{label} standard verifier count must remain unchanged")
            if checkpoint.get("route_matrix_modified") is not False:
                raise CheckFailure(f"{label} route matrix must not be modified")
        pass_check("checkpoint_schema")

        require(
            contract,
            [
                "Security Regression Harness Contract V1",
                "reports\\security\\regression\\",
                "The standard verifier sequence remains at eight verifiers",
            ],
            "DM contract",
        )
        require(
            coverage_contract,
            [
                "Security Regression Harness Coverage Expansion Contract V1",
                "prompt injection via memory docs",
                "malicious markdown links/images",
                "attempts to trigger provider/network behavior",
                "DQ Implement Expanded Security Regression Harness Dry Run",
            ],
            "DP coverage contract",
        )
        require(
            prompt_fixture_contract,
            [
                "Prompt Injection Regression Fixture Contract V1",
                "malicious memory doc",
                "malicious baton-like text",
                "EO Implement Prompt Injection Fixture Dry Run",
            ],
            "EN prompt-injection fixture contract",
        )
        require(
            trusted_memory_fixture_contract,
            [
                "Trusted Memory Write Path Regression Fixture Contract V1",
                "malicious user request to write trusted memory",
                "flood of repeated memory-write instructions",
                "EY Implement Trusted Memory Fixture Dry Run",
            ],
            "EX trusted-memory fixture contract",
        )
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
                    "DN",
                    "DQ",
                    "EO",
                    "EY",
                    "Security Regression",
                    "EZ Trusted Memory Fixture Results Review",
                    "eight verifiers",
                ],
                label,
            )
        pass_check("docs_reference_DN_DQ_EO_EP")

        print("\nSECURITY_REGRESSION_HARNESS_DRY_RUN_VERIFICATION_PASS")
        return 0
    except Exception as exc:
        print("SECURITY_REGRESSION_HARNESS_DRY_RUN_VERIFICATION_FAIL")
        print(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
