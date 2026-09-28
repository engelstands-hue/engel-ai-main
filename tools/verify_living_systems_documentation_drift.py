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
    "living_systems_index": ROOT / "memory" / "LIVING_SYSTEMS_INDEX_V1.md",
    "next_work_baton": ROOT / "memory" / "NEXT_WORK_BATON_V1.md",
    "standard_verifier_checklist": ROOT / "memory" / "STANDARD_VERIFIER_CHECKLIST_V1.md",
    "engel_commands": ROOT / "memory" / "ENGEL_COMMANDS.md",
    "project_memory_index": ROOT / "memory" / "PROJECT_MEMORY_INDEX_V2V.md",
}

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

THIS_VERIFIER = "tools\\verify_living_systems_documentation_drift.py"


class CheckFailure(Exception):
    pass


def _normalize(text: str) -> str:
    lowered = text.lower().replace("/", "\\")
    lowered = re.sub(r"\s+", " ", lowered)
    return lowered


def _load_docs() -> dict[str, str]:
    docs: dict[str, str] = {}
    for name, path in DOCS.items():
        if not path.exists():
            raise CheckFailure(f"missing required document: {path}")
        docs[name] = path.read_text(encoding="utf-8")
    return docs


def _require(text: str, needles: list[str], label: str) -> None:
    haystack = _normalize(text)
    missing = [needle for needle in needles if _normalize(needle) not in haystack]
    if missing:
        raise CheckFailure(label + " missing: " + ", ".join(missing))


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


def _assert_standard_sequence_is_eight(text: str, label: str) -> None:
    section = _section(text, "## Full Eight-Verifier Standard Sequence", "## CLI Smoke Checks")
    normalized = _normalize(section)
    for verifier in STANDARD_VERIFIERS:
        if _normalize(verifier) not in normalized:
            raise CheckFailure(f"{label} missing standard verifier: {verifier}")
    found = re.findall(r"tools\\verify_[a-z0-9_]+\.py", normalized)
    unique_found = sorted(set(found))
    expected = sorted(_normalize(v) for v in STANDARD_VERIFIERS)
    if unique_found != expected:
        raise CheckFailure(
            f"{label} standard verifier sequence drifted: expected {expected}, found {unique_found}"
        )
    if _normalize(THIS_VERIFIER) in normalized:
        raise CheckFailure(f"{label} incorrectly promoted DI verifier into the standard sequence")


def _assert_living_index(text: str) -> None:
    _require(
        text,
        [
            "`living learning status` is the primary user-facing heartbeat route",
            "proposal autonomy",
            "Dry-run/report-only guarded",
            "Lesson candidate learning",
            "Untrusted/review-only/report-only",
            "Trusted lesson apply, rollback, and candidate creation remain absent",
            "Colony simulation",
            "Status/contract-only",
            "Mycelium layer",
            "Read-only/status-contract-only",
            "No signal propagation runtime",
            "human-invoked and generate-packet-only",
            "does not auto-run",
            "The standard verifier sequence currently has eight verifiers",
            "readable runbook is `memory\\STANDARD_VERIFIER_CHECKLIST_V1.md`",
            "Old-provider, Ollama, and local-endpoint safeguards remain active",
            "Default next work remains docs/config/verifier-first",
            "DI Living Systems Documentation Drift Guard",
            "DJ Decide whether to promote living-systems documentation drift guard into the standard verifier sequence",
        ],
        "living systems index",
    )


def _assert_baton_contract(text: str) -> None:
    _require(
        text,
        [
            "HUMAN_INVOKED",
            "NO_AUTONOMY",
            "generate next packet",
            "not a background loop",
            "automatic verifier runner",
            "auto-refresh or self-advance",
            "auto-detect next steps by executing project routes",
            "docs/config/verifier-first",
            "all eight standard verifiers",
            "trusted apply",
            "rollback",
            "lesson candidate creation route",
            "simulation runtime",
            "mycelium signal propagation",
            "provider/API/network behavior",
            "queue mutation",
            "`ALIVE_STATE` write",
            "DI Living Systems Documentation Drift Guard",
            "DJ Decide whether to promote living-systems documentation drift guard into the standard verifier sequence",
        ],
        "next work baton contract",
    )


def _assert_standard_checklist(text: str) -> None:
    _assert_standard_sequence_is_eight(text, "standard verifier checklist")
    _require(
        text,
        [
            "read-only/status routes must not create files or reports",
            "Direct verifiers may generate their expected approved report-only artifacts",
            "Run commands externally",
            "human-invoked, generate-packet-only, and not autonomous",
            "direct-only living-system documentation drift guard",
            "does not change the full eight-verifier standard sequence",
            "DJ decision",
        ],
        "standard verifier checklist",
    )


def _assert_commands(text: str) -> None:
    _require(
        text,
        [
            "living learning status [read-only/status-only/no-write",
            "Primary heartbeat",
            "Proposal autonomy",
            "report-only approved routes",
            "Lesson candidates",
            "candidates remain untrusted",
            "trusted apply, rollback, candidate creation",
            "Colony simulation",
            "status-only/contract-only/no-write",
            "Mycelium layer",
            "no mycelium runtime, signal propagation",
            "human-invoked local packet generator",
            "generate-packet-only",
            "Standard verifier checklist",
            "Full eight-verifier standard sequence",
            "Standard verifiers may generate their expected approved report-only artifacts",
            "Read-only/status route smoke and snapshot checks must not create files or reports",
            "Direct-only documentation drift verifier",
            "not part of the eight-verifier standard sequence in DI",
        ],
        "command docs",
    )


def _assert_project_memory(text: str) -> None:
    _require(
        text,
        [
            "living learning status` is the primary heartbeat route",
            "Proposal autonomy remains dry-run/report-only guarded",
            "Lesson candidate review remains local-only, untrusted, review-only, and report-only",
            "trusted lesson apply, rollback, and candidate creation remain absent",
            "Colony simulation remains `colony simulation status` and `colony simulation contract` only",
            "Mycelium layer remains read-only/status-contract-only",
            "no signal propagation runtime",
            "The standard verifier sequence has eight verifiers",
            "Old-provider/Ollama/local-endpoint safeguards remain active",
            "docs/config/verifier-first",
            "V2APP-DI",
            "direct-only living systems documentation drift guard",
            "DJ Decide whether to promote living-systems documentation drift guard into the standard verifier sequence",
        ],
        "project memory index",
    )


def _assert_global_alignment(docs: dict[str, str]) -> None:
    combined = "\n".join(docs.values())
    _require(
        combined,
        [
            "living learning status",
            "primary heartbeat",
            "dry-run/report-only",
            "untrusted",
            "trusted lesson apply, rollback, and candidate creation remain absent",
            "status/contract-only",
            "read-only/status-contract-only",
            "no signal propagation runtime",
            "human-invoked",
            "generate-packet-only",
            "not autonomous",
            "eight verifiers",
            "read-only/status routes must not create files or reports",
            "approved report-only artifacts",
            "Old-provider/Ollama/local-endpoint safeguards remain active",
            "docs/config/verifier-first",
        ],
        "combined documentation alignment",
    )


def pass_check(name: str) -> None:
    print(f"PASS {name}")


def main() -> int:
    try:
        docs = _load_docs()
        pass_check("read_required_docs_only")

        _assert_living_index(docs["living_systems_index"])
        pass_check("living_systems_index_alignment")

        _assert_baton_contract(docs["next_work_baton"])
        pass_check("next_work_baton_alignment")

        _assert_standard_checklist(docs["standard_verifier_checklist"])
        pass_check("standard_verifier_checklist_alignment")

        _assert_commands(docs["engel_commands"])
        pass_check("engel_commands_alignment")

        _assert_project_memory(docs["project_memory_index"])
        pass_check("project_memory_index_alignment")

        _assert_global_alignment(docs)
        pass_check("global_living_systems_claim_alignment")

        print("\nLIVING_SYSTEMS_DOCUMENTATION_DRIFT_VERIFICATION_PASS")
        return 0
    except CheckFailure as exc:
        print("LIVING_SYSTEMS_DOCUMENTATION_DRIFT_VERIFICATION_FAIL")
        print(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
