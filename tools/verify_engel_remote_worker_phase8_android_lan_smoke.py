from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_REMOTE_WORKER_PHASE_8_REAL_ANDROID_LAN_SMOKE.md"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"

ASSIGNMENT_ID = "20260517T045824Z_android_worker_alpha_draft_notes_first_real_android_remote_worker_lan_smoke_assignment"
ASSIGNMENT_ID_FILE = "20260517t045824z_android_worker_alpha_draft_notes_first_real_android_remote_worker_lan_smoke_assignment"
ASSIGNMENT_ROOT = ROOT / "remote_workers" / "communication_queen_assignments"
APPROVED_DIR = ASSIGNMENT_ROOT / "approved"
CLAIMED_DIR = ASSIGNMENT_ROOT / "claimed"
RETURNED_DIR = ASSIGNMENT_ROOT / "returned"
RETIRED_PACKET = ASSIGNMENT_ROOT / "retired" / f"{ASSIGNMENT_ID_FILE}.json"
LATEST_RETURNED_RESULT = RETURNED_DIR / "20260517T050123Z_20260517t045824z_android_worker_alpha_draft_notes_first_real_and_result.json"
INTAKE_RECEIPT = ROOT / "reports" / "remote_worker_results" / "REMOTE_WORKER_RESULT_INTAKE_20260517T050436Z_20260517T045824Z_android_worker_alpha_draft_notes_first_real_android_remote_work.md"
LAN_PAIRING_RECEIPT = ROOT / "reports" / "remote_worker_lan_pairing" / "REMOTE_WORKER_LAN_PAIRING_20260517T045541Z_paired.md"

CREATION_RECEIPT = ROOT / "reports" / "communication_queen_assignments" / "COMMUNICATION_QUEEN_ASSIGNMENT_20260517T045824Z_20260517t045824z_android_worker_alpha_draft_notes_first_real_android_remote_worker_lan_smoke_assignment.md"
RETIRE_RECEIPT = ROOT / "reports" / "communication_queen_assignments" / "COMMUNICATION_QUEEN_ASSIGNMENT_20260517T050212Z_20260517t045824z_android_worker_alpha_draft_notes_first_real_android_remote_worker_lan_smoke_assignment.md"
AUTO_REPORT_DIR = ROOT / "reports" / "remote_worker_auto_assignment"

EXPECTED_CLAIM_TIMES = ["20260517T045834Z", "20260517T045908Z", "20260517T045953Z", "20260517T050038Z", "20260517T050123Z"]
REQUIRED_BLOCKED_ACTIONS = [
    "execute_commands",
    "write_trusted_memory",
    "mutate_queue",
    "mutate_routes",
    "mutate_source",
    "control_engel",
    "auto_apply_fixes",
    "provider_call",
    "browser_task",
    "download",
    "install_package",
]


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def load_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(payload, dict), "JSON root must be object: " + str(path.relative_to(ROOT)))
    return payload


def matching_files(directory: Path, suffix: str) -> list[Path]:
    pattern = f"*{ASSIGNMENT_ID_FILE[:22]}*{suffix}"
    return sorted(path for path in directory.glob(pattern) if path.is_file())


def check_required_files() -> None:
    for path in [
        REPORT,
        COMMANDS,
        CODEX_VERIFY,
        RETIRED_PACKET,
        LATEST_RETURNED_RESULT,
        INTAKE_RECEIPT,
        LAN_PAIRING_RECEIPT,
        CREATION_RECEIPT,
        RETIRE_RECEIPT,
    ]:
        require(path.exists(), "missing Phase 8 artifact: " + str(path.relative_to(ROOT)))


def check_report_honesty() -> None:
    report = read(REPORT)
    required_phrases = [
        "real Android phone LAN smoke succeeded",
        "moto g power 2025 / ANDROID_WORKER_ALPHA / Android 16",
        "192.0.2.40",
        "Port: 8765",
        "Pairing: succeeded",
        ASSIGNMENT_ID,
        str(RETIRED_PACKET.relative_to(ROOT)),
        "Claim records: 5",
        "Returned result records: 5",
        str(LATEST_RETURNED_RESULT.relative_to(ROOT)),
        str(INTAKE_RECEIPT.relative_to(ROOT)),
        "approved folder contains only `.gitkeep`",
        "Duplicate claim observation",
        "Phase 9 should add assignment claim lock / duplicate return guard",
        "The phone received and returned an assignment over LAN",
        "nothing was executed, applied, promoted, written to trusted memory",
    ]
    for phrase in required_phrases:
        require(phrase in report, "Phase 8 report missing phrase: " + phrase)
    forbidden_false_claims = [
        "protocol-only fallback was used",
        "fake phone success",
        "trusted memory written",
        "auto-applied",
    ]
    lower = report.lower()
    for phrase in forbidden_false_claims:
        require(phrase not in lower, "Phase 8 report contains unsafe/false claim: " + phrase)


def check_assignment_packet() -> None:
    packet = load_json(RETIRED_PACKET)
    require(packet.get("packet_id") == ASSIGNMENT_ID, "retired assignment packet id mismatch")
    require(packet.get("created_by") == "Communication Queen", "created_by mismatch")
    require(packet.get("approved_by") == "Engel Core", "approved_by mismatch")
    require(packet.get("approval_scope") == "remote_worker_assignment_only", "approval scope mismatch")
    require(packet.get("assignment_mode") == "remote_worker_auto", "assignment mode mismatch")
    require(packet.get("task_type") == "draft_notes", "task type mismatch")
    require(packet.get("worker_target") == "android_worker_alpha", "worker target mismatch")
    require(packet.get("requires_review") is True, "assignment requires_review must be true")
    require(packet.get("safe_to_auto_apply") is False, "assignment safe_to_auto_apply must be false")
    require(packet.get("not_trusted_memory") is True, "assignment not_trusted_memory must be true")
    require(packet.get("no_direct_control") is True, "assignment no_direct_control must be true")
    blocked = packet.get("blocked_actions", [])
    require(isinstance(blocked, list), "blocked_actions must be a list")
    for action in REQUIRED_BLOCKED_ACTIONS:
        require(action in blocked, "assignment missing blocked action: " + action)


def check_approved_folder_clean() -> None:
    # approved/ may contain real producer-created assignments after the
    # producer was generalized to multi-worker. Verify every .json is
    # a producer-validated packet; non-.json/non-.gitkeep files are noise
    # and still flagged.
    files = sorted(path for path in APPROVED_DIR.iterdir() if path.is_file())
    json_files = [p for p in files if p.suffix.lower() == ".json"]
    other = [p for p in files if p.suffix.lower() != ".json" and p.name != ".gitkeep"]
    require(not other, "approved folder must only contain .json assignment packets and .gitkeep, found: " + ", ".join(p.name for p in other))
    if json_files:
        import sys as _sys
        if str(ROOT) not in _sys.path:
            _sys.path.insert(0, str(ROOT))
        import importlib.util as _ilu
        _name = "phase8_producer_validator"
        spec = _ilu.spec_from_file_location(_name, str(ROOT / "engel_communication_queen_assignment_producer.py"))
        producer = _ilu.module_from_spec(spec)
        _sys.modules[_name] = producer  # dataclass uses sys.modules during class def
        spec.loader.exec_module(producer)
        for path in json_files:
            payload = json.loads(path.read_text(encoding="utf-8"))
            errors = producer.validate_assignment_packet(payload)
            require(not errors, f"approved assignment {path.name} failed validation: {errors}")


def check_claims_and_returns() -> None:
    claim_files = matching_files(CLAIMED_DIR, "_claim.json")
    result_files = matching_files(RETURNED_DIR, "_result.json")
    require(len(claim_files) == 5, f"expected 5 duplicate claim records, found {len(claim_files)}")
    require(len(result_files) == 5, f"expected 5 duplicate returned result records, found {len(result_files)}")
    for timestamp in EXPECTED_CLAIM_TIMES:
        require(any(path.name.startswith(timestamp) for path in claim_files), "missing claim record for " + timestamp)
        require(any(path.name.startswith(timestamp) for path in result_files), "missing returned result for " + timestamp)

    for claim_path in claim_files:
        claim = load_json(claim_path)
        require(claim.get("packet_id") == ASSIGNMENT_ID, "claim packet_id mismatch: " + claim_path.name)
        require(claim.get("worker_id") == "android_worker_alpha", "claim worker_id mismatch: " + claim_path.name)
        require(claim.get("worker_device") == "engel_remote_worker_flutter", "claim worker_device mismatch: " + claim_path.name)
        require(claim.get("claim_type") == "append_only_protocol_record", "claim type mismatch: " + claim_path.name)
        require(claim.get("direct_control") is False, "claim direct_control must be false: " + claim_path.name)
        require(claim.get("trusted_memory_write") is False, "claim trusted_memory_write must be false: " + claim_path.name)
        require(claim.get("auto_apply") is False, "claim auto_apply must be false: " + claim_path.name)

    for result_path in result_files:
        result = load_json(result_path)
        require("pairing_code" not in result, "returned result must not commit pairing code: " + result_path.name)
        require(result.get("packet_id") == ASSIGNMENT_ID, "result packet_id mismatch: " + result_path.name)
        require(result.get("worker_device") == "engel_remote_worker_flutter", "result worker_device mismatch: " + result_path.name)
        require(result.get("worker_id") == "android_worker_alpha", "result worker_id mismatch: " + result_path.name)
        require(result.get("trust_level") == "untrusted_until_engel_review", "result trust level mismatch: " + result_path.name)
        require(result.get("result_type") in {"auto_worker_acknowledgement", "draft_notes"}, "result_type mismatch: " + result_path.name)
        require(result.get("requires_review") is True, "result requires_review must be true: " + result_path.name)
        require(result.get("safe_to_auto_apply") is False, "result safe_to_auto_apply must be false: " + result_path.name)
        require(result.get("direct_control") is False, "result direct_control must be false: " + result_path.name)
        require(result.get("trusted_memory_write") is False, "result trusted_memory_write must be false: " + result_path.name)
        require(result.get("auto_apply") is False, "result auto_apply must be false: " + result_path.name)
        require(result.get("storage_decision") == "UNTRUSTED REVIEW ONLY - NOT APPLIED", "storage decision mismatch: " + result_path.name)


def check_receipts() -> None:
    for receipt in [CREATION_RECEIPT, RETIRE_RECEIPT]:
        text = read(receipt)
        require(ASSIGNMENT_ID in text, "assignment receipt missing packet id: " + receipt.name)
        require("APPROVED FOR REMOTE WORKER ASSIGNMENT ONLY - UNTRUSTED RESULT REQUIRED" in text, "assignment receipt missing final decision")
        require("This assignment is not trusted memory." in text, "assignment receipt missing trusted-memory boundary")

    auto_receipts = sorted(
        path
        for path in AUTO_REPORT_DIR.glob(f"*{ASSIGNMENT_ID_FILE[:22]}*.md")
        if path.is_file()
    )
    require(len(auto_receipts) == 5, f"expected 5 auto-assignment return receipts, found {len(auto_receipts)}")
    for receipt in auto_receipts:
        text = read(receipt)
        require("UNTRUSTED REVIEW ONLY - NOT APPLIED" in text, "return receipt missing final decision: " + receipt.name)
        require("does not execute, apply, promote, route, queue, trust, or write trusted memory" in text, "return receipt missing safety boundary: " + receipt.name)

    intake = read(INTAKE_RECEIPT)
    require("UNTRUSTED REVIEW ONLY" in intake and "NOT APPLIED" in intake, "intake receipt missing untrusted not-applied decision")
    require("valid_for_review" in intake, "intake receipt missing validation status")
    require("safe_to_auto_apply" in intake and "False" in intake, "intake receipt missing safe_to_auto_apply false")

    pairing = read(LAN_PAIRING_RECEIPT)
    require("paired: `true`" in pairing or "paired: true" in pairing, "LAN pairing receipt missing paired true")
    require("engel_remote_worker_flutter" in pairing, "LAN pairing receipt missing worker device")
    require("PAIRING STATUS ONLY - NO CONTROL GRANTED" in pairing, "LAN pairing receipt missing no-control decision")
    require("pairing_code" not in pairing.lower(), "LAN pairing receipt must not include full pairing token")


def check_docs_and_registration() -> None:
    commands = read(COMMANDS)
    codex = read(CODEX_VERIFY)
    require("remote worker android lan smoke status" in commands, "commands doc missing Phase 8 smoke status")
    require("remote worker duplicate claim guard phase9" in commands, "commands doc missing Phase 9 duplicate guard note")
    require("tools\\verify_engel_remote_worker_phase8_android_lan_smoke.py" in codex, "codex verifier missing Phase 8 verifier")


def main() -> int:
    checks = [
        check_required_files,
        check_report_honesty,
        check_assignment_packet,
        check_approved_folder_clean,
        check_claims_and_returns,
        check_receipts,
        check_docs_and_registration,
    ]
    failures: list[str] = []
    for check in checks:
        try:
            check()
            print(f"PASS {check.__name__}")
        except Exception as exc:  # noqa: BLE001 - verifier reports exact local failure
            failures.append(f"{check.__name__}: {exc}")
            print(f"FAIL {check.__name__}: {exc}")
    if failures:
        print("ENGEL_REMOTE_WORKER_PHASE8_ANDROID_LAN_SMOKE_VERIFY_FAIL")
        return 1
    print("ENGEL_REMOTE_WORKER_PHASE8_ANDROID_LAN_SMOKE_VERIFY_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
