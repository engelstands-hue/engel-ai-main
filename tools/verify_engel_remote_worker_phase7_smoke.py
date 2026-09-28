from __future__ import annotations

import json
from pathlib import Path
import sys
import importlib.util


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_REMOTE_WORKER_PHASE_7_FIRST_REAL_ASSIGNMENT_SMOKE.md"
PRODUCER = ROOT / "engel_communication_queen_assignment_producer.py"
LAN_MODULE = ROOT / "engel_remote_worker_lan_pairing.py"
RESULT_INTAKE = ROOT / "engel_remote_worker_result_intake.py"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"

PACKET_ID = "20260517T043215Z_android_worker_alpha_draft_notes_first_real_remote_worker_smoke_assignment"
RETIRED_PACKET = ROOT / "remote_workers" / "communication_queen_assignments" / "retired" / "20260517t043215z_android_worker_alpha_draft_notes_first_real_remote_worker_smoke_assignment.json"
APPROVED_DIR = ROOT / "remote_workers" / "communication_queen_assignments" / "approved"
CLAIM_RECORD = ROOT / "remote_workers" / "communication_queen_assignments" / "claimed" / "20260517T043241Z_20260517t043215z_android_worker_alpha_draft_notes_first_real_rem_claim.json"
RETURNED_RESULT = ROOT / "remote_workers" / "communication_queen_assignments" / "returned" / "20260517T043241Z_20260517t043215z_android_worker_alpha_draft_notes_first_real_rem_result.json"
CREATION_RECEIPT = ROOT / "reports" / "communication_queen_assignments" / "COMMUNICATION_QUEEN_ASSIGNMENT_20260517T043215Z_20260517t043215z_android_worker_alpha_draft_notes_first_real_remote_worker_smoke_assignment.md"
RETIRE_RECEIPT = ROOT / "reports" / "communication_queen_assignments" / "COMMUNICATION_QUEEN_ASSIGNMENT_20260517T043300Z_20260517t043215z_android_worker_alpha_draft_notes_first_real_remote_worker_smoke_assignment.md"
RETURN_RECEIPT = ROOT / "reports" / "remote_worker_auto_assignment" / "REMOTE_WORKER_AUTO_ASSIGNMENT_20260517T043241Z_20260517t043215z_android_worker_alpha_draft_notes_first_real_rem.md"
INTAKE_RECEIPT = ROOT / "reports" / "remote_worker_results" / "REMOTE_WORKER_RESULT_INTAKE_20260517T043249Z_20260517T043215Z_android_worker_alpha_draft_notes_first_real_remote_worker_smoke.md"

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

FORBIDDEN_TRUE_FIELDS = [
    "safe_to_auto_apply",
    "trusted",
    "write_trusted_memory",
    "execute_commands",
    "mutate_source",
    "mutate_routes",
    "mutate_queue",
    "control_engel",
    "auto_apply",
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


def load_module(path: Path, name: str):
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, "could not load module: " + str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def check_files() -> None:
    for path in [
        REPORT,
        PRODUCER,
        LAN_MODULE,
        RESULT_INTAKE,
        COMMANDS,
        CODEX_VERIFY,
        RETIRED_PACKET,
        CLAIM_RECORD,
        RETURNED_RESULT,
        CREATION_RECEIPT,
        RETIRE_RECEIPT,
        RETURN_RECEIPT,
        INTAKE_RECEIPT,
    ]:
        require(path.exists(), "missing Phase 7 artifact: " + str(path.relative_to(ROOT)))


def check_report_honesty() -> None:
    report = read(REPORT)
    for phrase in [
        "Protocol-only fallback.",
        "The Android phone was not used for this smoke.",
        "No Flutter phone run was claimed.",
        "This first real assignment smoke proves Communication Queen can assign work",
        "UNTRUSTED REVIEW ONLY",
        "remote_workers\\communication_queen_assignments\\approved\\` contains only `.gitkeep`",
    ]:
        require(phrase in report, "Phase 7 report missing phrase: " + phrase)
    for forbidden in [
        "real Android phone smoke",
        "phone was used",
        "Android was tested",
        "auto-applied",
        "trusted memory written",
    ]:
        require(forbidden.lower() not in report.lower(), "Phase 7 report makes unsafe/false claim: " + forbidden)


def check_assignment_packet() -> None:
    producer = load_module(PRODUCER, "phase7_producer")
    lan = load_module(LAN_MODULE, "phase7_lan")
    packet = load_json(RETIRED_PACKET)
    require(packet.get("packet_id") == PACKET_ID, "packet id mismatch")
    require(packet.get("created_by") == "Communication Queen", "created_by mismatch")
    require(packet.get("approved_by") == "Engel Core", "approved_by mismatch")
    require(packet.get("approval_scope") == "remote_worker_assignment_only", "approval_scope mismatch")
    require(packet.get("assignment_mode") == "remote_worker_auto", "assignment_mode mismatch")
    require(packet.get("task_type") == "draft_notes", "task type mismatch")
    require(packet.get("worker_target") == "android_worker_alpha", "worker target mismatch")
    require(packet.get("requires_review") is True, "assignment requires_review must be true")
    require(packet.get("safe_to_auto_apply") is False, "assignment safe_to_auto_apply must be false")
    require(packet.get("not_trusted_memory") is True, "assignment not_trusted_memory must be true")
    require(packet.get("no_direct_control") is True, "assignment no_direct_control must be true")
    for action in REQUIRED_BLOCKED_ACTIONS:
        require(action in packet.get("blocked_actions", []), "assignment missing blocked action: " + action)
    require(not producer.validate_assignment_packet(packet), "producer validation failed for smoke packet")
    require(not lan.validate_assignment_packet(packet), "Phase 5 validation failed for smoke packet")


def check_claim_and_returned_result() -> None:
    claim = load_json(CLAIM_RECORD)
    result = load_json(RETURNED_RESULT)
    require(claim.get("packet_id") == PACKET_ID, "claim packet_id mismatch")
    require(claim.get("worker_id") == "android_worker_alpha", "claim worker id mismatch")
    require(claim.get("worker_device") == "engel_remote_worker_flutter", "claim worker device mismatch")
    require(claim.get("claim_type") == "append_only_protocol_record", "claim type mismatch")
    require(claim.get("direct_control") is False, "claim direct_control must be false")
    require(claim.get("trusted_memory_write") is False, "claim trusted_memory_write must be false")
    require(claim.get("auto_apply") is False, "claim auto_apply must be false")

    require(result.get("packet_id") == PACKET_ID, "result packet_id mismatch")
    require(result.get("worker_device") == "engel_remote_worker_flutter", "result worker_device mismatch")
    require(result.get("worker_id") == "android_worker_alpha", "result worker_id mismatch")
    require(result.get("trust_level") == "untrusted_until_engel_review", "result trust level mismatch")
    require(result.get("result_type") in {"auto_worker_acknowledgement", "draft_notes"}, "result_type mismatch")
    require(result.get("requires_review") is True, "result requires_review must be true")
    require(result.get("safe_to_auto_apply") is False, "result safe_to_auto_apply must be false")
    require(result.get("auto_generated") is True, "result auto_generated must be true")
    require(result.get("smoke_mode") == "protocol_only", "result must be labeled protocol_only")
    require(result.get("storage_decision") == "UNTRUSTED REVIEW ONLY - NOT APPLIED", "storage decision mismatch")
    for field in FORBIDDEN_TRUE_FIELDS:
        require(result.get(field) is not True, "forbidden true field in result: " + field)


def check_receipts_and_approved_state() -> None:
    for receipt in [CREATION_RECEIPT, RETIRE_RECEIPT]:
        text = read(receipt)
        require("APPROVED FOR REMOTE WORKER ASSIGNMENT ONLY - UNTRUSTED RESULT REQUIRED" in text, "assignment receipt missing final decision")
        require("This assignment is not trusted memory." in text, "assignment receipt missing memory boundary")
        require("does not authorize command execution" in text, "assignment receipt missing command boundary")
        require(PACKET_ID in text, "assignment receipt missing packet id")
    return_text = read(RETURN_RECEIPT)
    require("UNTRUSTED REVIEW ONLY - NOT APPLIED" in return_text, "return receipt missing untrusted decision")
    require("does not execute, apply, promote, route, queue, trust, or write trusted memory" in return_text, "return receipt missing safety boundary")
    intake_text = read(INTAKE_RECEIPT)
    require("UNTRUSTED REVIEW ONLY" in intake_text and "NOT APPLIED" in intake_text, "intake receipt missing untrusted not-applied decision")
    require("does not promote, execute, or trust Remote Worker output" in intake_text, "intake receipt missing trust boundary")

    # approved/ may contain real producer-created assignments after the
    # producer was generalized to multi-worker. Verify nothing fake is
    # left over: each .json file must validate against the producer schema.
    approved_files = [path for path in APPROVED_DIR.iterdir() if path.is_file()]
    json_files = [path for path in approved_files if path.suffix.lower() == ".json"]
    other_files = [path for path in approved_files if path.suffix.lower() != ".json" and path.name != ".gitkeep"]
    require(not other_files, "approved folder must only contain .json assignment packets and .gitkeep, found: " + ", ".join(p.name for p in other_files))
    if json_files:
        producer = load_module(PRODUCER, "phase7_producer_validator")
        for path in json_files:
            payload = json.loads(path.read_text(encoding="utf-8"))
            errors = producer.validate_assignment_packet(payload)
            require(not errors, f"approved assignment {path.name} failed validation: {errors}")


def check_docs_and_registration() -> None:
    commands = read(COMMANDS)
    codex = read(CODEX_VERIFY)
    require("remote worker first assignment smoke" in commands, "commands doc missing first assignment smoke")
    require("remote worker smoke status" in commands, "commands doc missing smoke status")
    require("tools\\verify_engel_remote_worker_phase7_smoke.py" in codex, "codex verifier missing Phase 7 verifier")


def main() -> int:
    checks = [
        check_files,
        check_report_honesty,
        check_assignment_packet,
        check_claim_and_returned_result,
        check_receipts_and_approved_state,
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
        print("ENGEL_REMOTE_WORKER_PHASE7_SMOKE_VERIFY_FAIL")
        return 1
    print("ENGEL_REMOTE_WORKER_PHASE7_SMOKE_VERIFY_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
