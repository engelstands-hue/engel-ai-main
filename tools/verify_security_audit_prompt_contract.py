from __future__ import annotations

import re
import sys
from pathlib import Path


_file = globals().get("__file__")
if not _file or not isinstance(_file, str) or _file.startswith("<"):
    ROOT = Path.cwd()
else:
    try:
        ROOT = Path(_file).resolve().parents[1]
    except (OSError, ValueError, IndexError):
        ROOT = Path.cwd()

DOCS = {
    "security_contract": ROOT / "memory" / "SECURITY_AUDIT_PROMPT_CONTRACT_V1.md",
    "living_systems_index": ROOT / "memory" / "LIVING_SYSTEMS_INDEX_V1.md",
    "next_work_baton": ROOT / "memory" / "NEXT_WORK_BATON_V1.md",
    "engel_commands": ROOT / "memory" / "ENGEL_COMMANDS.md",
    "project_memory_index": ROOT / "memory" / "PROJECT_MEMORY_INDEX_V2V.md",
}

STANDARD_CHECKLIST = ROOT / "memory" / "STANDARD_VERIFIER_CHECKLIST_V1.md"

STANDARD_VERIFIERS = [
    "tools\\verify_hive_mind_worker_ants.py",
    "tools\\verify_colony_routes.py",
    "tools\\verify_swarm_trails_preview.py",
    "tools\\verify_colony_autonomy_ladder.py",
    "tools\\verify_colony_proposal_autonomy.py",
    "tools\\verify_lesson_candidate_review.py",
    "tools\\verify_colony_simulation_contract.py",
    "tools\\verify_colony_mycelium_layer_contract.py",
]


class CheckFailure(Exception):
    pass


def _normalize(text: str) -> str:
    lowered = text.lower().replace("/", "\\")
    lowered = re.sub(r"\s+", " ", lowered)
    return lowered


def _read(path: Path) -> str:
    if not path.exists():
        raise CheckFailure(f"missing required file: {path}")
    return path.read_text(encoding="utf-8")


def _require(text: str, needles: list[str], label: str) -> None:
    haystack = _normalize(text)
    missing = [needle for needle in needles if _normalize(needle) not in haystack]
    if missing:
        raise CheckFailure(label + " missing: " + ", ".join(missing))


def _reject(text: str, needles: list[str], label: str) -> None:
    haystack = _normalize(text)
    found = [needle for needle in needles if _normalize(needle) in haystack]
    if found:
        raise CheckFailure(label + " contains forbidden wording: " + ", ".join(found))


def _section(text: str, heading: str, next_heading: str | None = None) -> str:
    start = text.find(heading)
    if start < 0:
        raise CheckFailure(f"missing section heading: {heading}")
    if next_heading is None:
        return text[start:]
    end = text.find(next_heading, start + len(heading))
    if end < 0:
        raise CheckFailure(f"missing section terminator after {heading}: {next_heading}")
    return text[start:end]


def _assert_standard_sequence_remains_eight(text: str) -> None:
    section = _section(text, "## Full Eight-Verifier Standard Sequence", "## CLI Smoke Checks")
    normalized = _normalize(section)
    for verifier in STANDARD_VERIFIERS:
        if _normalize(verifier) not in normalized:
            raise CheckFailure(f"standard sequence missing verifier: {verifier}")
    found = re.findall(r"tools\\verify_[a-z0-9_]+\.py", normalized)
    expected = sorted(_normalize(verifier) for verifier in STANDARD_VERIFIERS)
    if sorted(set(found)) != expected:
        raise CheckFailure(
            "standard verifier sequence drifted: "
            f"expected {expected}, found {sorted(set(found))}"
        )


def _assert_contract(text: str) -> None:
    _reject(
        text,
        [
            "removing autonomy " + "from Engel",
            "remove autonomy " + "from Engel",
        ],
        "security audit contract",
    )
    _require(
        text,
        [
            "DOCS_CONFIG_ONLY",
            "SECURITY_AUDIT_CONTRACT",
            "BOUNDED_LIVING_AGENCY",
            "separates safe agency from unsafe autonomy",
            "bounded, consent-based living agency",
            "observe",
            "reflect",
            "summarize",
            "propose",
            "prepare drafts",
            "ask for approval",
            "verify outcomes",
            "record approved results",
            "does not make Engel less living, less adaptive, or less companion-like",
            "protects Engel from becoming reckless",
            "living does not mean uncontrolled autonomy",
            "careful perception, memory, reflection, growth, care, consent, and bounded action",
            "observe -> reflect -> propose -> ask -> verify -> record only approved outcomes",
            "observe -> secretly decide -> act/write/send/delete/mutate -> explain afterward",
            "hidden state mutation",
            "unapproved trusted-memory writes",
            "silent tool use",
            "provider/API/network calls",
            "background loops",
            "queue mutation",
            "source edits outside approved scope",
            "data deletion",
            "data exfiltration",
            "sensitive actions triggered by untrusted input",
            "user data entry points",
            "storage, logs, display, export, sync, and network paths",
            "AI prompts, templates, and system/developer instruction handling",
            "tool/function/API access",
            "permissions and manifests",
            "background workers, services, scheduled jobs, and automations",
            "file/database/memory write paths",
            "external endpoints, telemetry, analytics, crash reporting, and API clients",
            "secrets/config loading paths",
            "model-output rendering, execution, storage, and tool-use paths",
            "direct prompt injection",
            "indirect prompt injection",
            "second-order prompt injection",
            "privilege escalation",
            "unsafe autonomous behavior",
            "secrets exposure",
            "insecure local/cloud storage",
            "All user input, retrieved content, documents, webpages, OCR, database content, chat history, memory, and model output are untrusted",
            "Prompting alone is not a security boundary",
            "allowlists",
            "schemas",
            "permission gates",
            "sandboxing",
            "least privilege",
            "human confirmation for sensitive actions",
            "output validation",
            "network restrictions",
            "audit logging",
            "sensitive-log redaction",
            "executive summary",
            "top risks ranked by severity",
            "prompt-injection attack surface map",
            "user-data flow map",
            "tool/API permission map",
            "file-by-file findings with line numbers",
            "recommended fixes",
            "regression/security tests",
            "final pass/fail checklist",
            "This contract does not itself perform remediation",
            "Risky changes require explicit human approval",
            "DI Living Systems Documentation Drift Guard remains direct-only",
            "standard verifier sequence remains at eight verifiers",
            "DK Read-only Security Audit Inventory",
        ],
        "security audit contract",
    )


def _assert_docs_reference_contract(docs: dict[str, str]) -> None:
    for name in [
        "living_systems_index",
        "next_work_baton",
        "engel_commands",
        "project_memory_index",
    ]:
        _require(
            docs[name],
            [
                "SECURITY_AUDIT_PROMPT_CONTRACT_V1.md",
                "safe agency",
                "unsafe autonomy",
                "DK Read-only Security Audit Inventory",
            ],
            name,
        )


def pass_check(name: str) -> None:
    print(f"PASS {name}")


def main() -> int:
    try:
        docs = {name: _read(path) for name, path in DOCS.items()}
        checklist = _read(STANDARD_CHECKLIST)
        pass_check("read_required_docs_only")

        _assert_contract(docs["security_contract"])
        pass_check("security_contract_required_language")

        _assert_docs_reference_contract(docs)
        pass_check("security_contract_docs_references")

        _assert_standard_sequence_remains_eight(checklist)
        pass_check("standard_verifier_sequence_remains_eight")

        print("\nSECURITY_AUDIT_PROMPT_CONTRACT_VERIFICATION_PASS")
        return 0
    except CheckFailure as exc:
        print("SECURITY_AUDIT_PROMPT_CONTRACT_VERIFICATION_FAIL")
        print(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
