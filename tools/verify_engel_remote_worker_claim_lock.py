from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "engel_remote_worker_lan_pairing.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_REMOTE_WORKER_PHASE_9_ASSIGNMENT_CLAIM_LOCK.md"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"
PHASE8_REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_REMOTE_WORKER_PHASE_8_REAL_ANDROID_LAN_SMOKE.md"
APPROVED_DIR = ROOT / "remote_workers" / "communication_queen_assignments" / "approved"
CLAIM_LOCKS_DIR = ROOT / "remote_workers" / "communication_queen_assignments" / "claim_locks"
DUPLICATE_RETURNS_DIR = ROOT / "remote_workers" / "communication_queen_assignments" / "duplicate_returns"
DUPLICATE_REPORT_DIR = ROOT / "reports" / "remote_worker_duplicate_guards"
MAIN_DART = ROOT / "mobile" / "engel_remote_worker" / "lib" / "main.dart"
LAN_CLIENT_DART = ROOT / "mobile" / "engel_remote_worker" / "lib" / "lan_pairing_client.dart"
ANDROID_MANIFEST = ROOT / "mobile" / "engel_remote_worker" / "android" / "app" / "src" / "main" / "AndroidManifest.xml"

FORBIDDEN_IMPORTS = {
    "requests",
    "urllib",
    "webbrowser",
    "subprocess",
    "multiprocessing",
    "asyncio",
    "watchdog",
    "smtplib",
    "openai",
}

FORBIDDEN_CALLS = {
    "eval",
    "exec",
    "__import__",
    "system",
    "popen",
    "Popen",
    "run",
    "call",
    "check_call",
    "check_output",
    "startfile",
}

REQUIRED_BLOCKED_ACTIONS = [
    "execute_commands",
    "write_trusted_memory",
    "mutate_queue",
    "mutate_routes",
    "mutate_source",
    "control_engel",
    "auto_apply_fixes",
]


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def load_module():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("engel_remote_worker_lan_pairing_phase9", MODULE)
    require(spec is not None and spec.loader is not None, "could not load LAN pairing module")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_remote_worker_lan_pairing_phase9"] = module
    spec.loader.exec_module(module)
    return module


def safe_assignment(packet_id: str = "phase9-claim-lock-001") -> dict[str, object]:
    return {
        "packet_version": "1",
        "packet_id": packet_id,
        "created_by": "Engel Communication Router",
        "approved_by": "Engel Core",
        "approval_scope": "remote_worker_assignment_only",
        "assignment_mode": "remote_worker_auto",
        "trust_level": "untrusted_until_reviewed",
        "worker_target": "android_worker_alpha",
        "task_type": "draft_notes",
        "title": "Claim lock verifier assignment",
        "instructions": "Acknowledge once only. Do not execute commands.",
        "allowed_outputs": ["draft_result_json"],
        "blocked_actions": list(REQUIRED_BLOCKED_ACTIONS),
        "requires_review": True,
        "safe_to_auto_apply": False,
        "not_trusted_memory": True,
        "no_direct_control": True,
    }


def safe_result(packet_id: str = "phase9-claim-lock-001") -> dict[str, object]:
    return {
        "result_version": "1",
        "packet_id": packet_id,
        "worker_device": "engel_remote_worker_flutter",
        "worker_id": "android_worker_alpha",
        "trust_level": "untrusted_until_engel_review",
        "result_type": "auto_worker_acknowledgement",
        "draft_text": "Acknowledged once for review only. No commands executed.",
        "requires_review": True,
        "safe_to_auto_apply": False,
        "auto_generated": True,
        "pairing_code": "SHOULD_NOT_BE_STORED",
    }


def write_packet(directory: Path, payload: dict[str, object]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (str(payload["packet_id"]).lower() + ".json")
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def check_files() -> None:
    for path in [
        MODULE,
        REPORT,
        COMMANDS,
        CODEX_VERIFY,
        PHASE8_REPORT,
        CLAIM_LOCKS_DIR,
        DUPLICATE_RETURNS_DIR,
        DUPLICATE_REPORT_DIR,
        MAIN_DART,
        LAN_CLIENT_DART,
        ANDROID_MANIFEST,
    ]:
        require(path.exists(), "missing required Phase 9 path: " + str(path.relative_to(ROOT)))


def check_static_safety() -> None:
    source = read(MODULE)
    tree = ast.parse(source)
    for snippet in [
        "CLAIM_LOCKS_DIR",
        "DUPLICATE_RETURNS_DIR",
        "DUPLICATE_GUARD_REPORT_DIR",
        "claim_assignment",
        "no_unclaimed_approved_assignments",
        "return_result_response",
        "UDP_DISCOVERY_PORT_OFFSET = 1",
        "start_udp_broadcaster(port)",
        'sock.sendto(payload, ("255.255.255.255", udp_port))',
        'name="engel-udp-discovery"',
        "daemon=True",
        "DUPLICATE RETURN REJECTED - NOT APPLIED",
        "safe_payload.pop(\"pairing_code\", None)",
        '"direct_control": False',
        '"trusted_memory_write": False',
        '"auto_apply": False',
    ]:
        require(snippet in source, "LAN protocol missing Phase 9 snippet: " + snippet)
    for forbidden in [
        "trusted_memory.write",
        "apply_patch(",
        "watchdog.Observer",
        "provider_api",
        "BOOT_COMPLETED",
        "WAKE_LOCK",
        "ScheduledTask",
        "firewall",
        "UPnP",
        "port_forward",
    ]:
        require(forbidden not in source, "LAN protocol contains forbidden text: " + forbidden)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_name = alias.name.split(".")[0]
                require(root_name not in FORBIDDEN_IMPORTS, "forbidden import: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            root_name = node.module.split(".")[0]
            require(root_name not in FORBIDDEN_IMPORTS, "forbidden import: " + node.module)
        elif isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
            require(name not in FORBIDDEN_CALLS, "forbidden call: " + name)


def check_runtime_claim_lock_and_duplicate_guard() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as temp_name:
        temp = Path(temp_name)
        approved = temp / "approved"
        claimed = temp / "claimed"
        returned = temp / "returned"
        retired = temp / "retired"
        invalid = temp / "invalid"
        locks = temp / "claim_locks"
        reports = temp / "reports"
        duplicates = temp / "duplicate_returns"
        duplicate_reports = temp / "duplicate_reports"
        packet = safe_assignment()
        source_path = write_packet(approved, packet)

        status, response = module.next_assignment_response(
            approved_dir=approved,
            claimed_dir=claimed,
            returned_dir=returned,
            retired_dir=retired,
            invalid_dir=invalid,
            lock_dir=locks,
        )
        require(status == 200, "first next-assignment should return HTTP 200")
        require(response.get("status") == "assignment_ready", "first next-assignment should claim work")
        require(not source_path.exists(), "approved assignment must move out of approved after claim")
        claimed_assignment = Path(str(response.get("claimed_assignment_path", "")))
        claim_receipt = Path(str(response.get("claim_receipt_path", "")))
        lock_path = Path(str(response.get("claim_lock_path", "")))
        require(claimed_assignment.exists(), "claimed assignment file missing")
        require(claim_receipt.exists(), "claim record missing")
        require(lock_path.exists(), "claim lock missing")
        claim_payload = json.loads(claim_receipt.read_text(encoding="utf-8"))
        require(claim_payload.get("claim_mode") == "untrusted_assignment_claim", "claim mode mismatch")
        require(claim_payload.get("safe_to_auto_apply") is False, "claim safe_to_auto_apply must be false")
        for index in range(120):
            padding = dict(claim_payload)
            padding["packet_id"] = f"phase9-padding-{index:03d}"
            padding["worker_id"] = "android_worker_padding"
            (claimed / f"0000_padding_{index:03d}_claim.json").write_text(
                json.dumps(padding, indent=2),
                encoding="utf-8",
            )
        require(
            module.matching_claim(packet.get("packet_id"), "android_worker_alpha", "engel_remote_worker_flutter", claimed)
            is not None,
            "matching_claim must scan beyond the first 100 claim records",
        )

        status, no_work = module.next_assignment_response(
            approved_dir=approved,
            claimed_dir=claimed,
            returned_dir=returned,
            retired_dir=retired,
            invalid_dir=invalid,
            lock_dir=locks,
        )
        require(status == 200 and no_work.get("status") == "no_work", "second next-assignment must return no_work")
        require(no_work.get("reason") == "no_unclaimed_approved_assignments", "no_work reason mismatch")
        for field in ["direct_control", "trusted_memory_write", "auto_apply", "safe_to_auto_apply"]:
            require(no_work.get(field) is False, "no_work safety field must be false: " + field)

        first_status, first_return = module.return_result_response(
            safe_result(),
            remote_address="127.0.0.1",
            claimed_dir=claimed,
            returned_dir=returned,
            report_dir=reports,
            duplicate_dir=duplicates,
            duplicate_report_dir=duplicate_reports,
        )
        require(first_status == 200 and first_return.get("accepted") is True, "first return should be accepted")
        result_path = Path(str(first_return.get("returned_result_path", "")))
        stored_result = json.loads(result_path.read_text(encoding="utf-8"))
        require("pairing_code" not in stored_result, "stored result must not keep pairing code")
        require(stored_result.get("storage_decision") == module.AUTO_FINAL_DECISION, "stored result must be review-only")

        second_status, second_return = module.return_result_response(
            safe_result(),
            remote_address="127.0.0.1",
            claimed_dir=claimed,
            returned_dir=returned,
            report_dir=reports,
            duplicate_dir=duplicates,
            duplicate_report_dir=duplicate_reports,
        )
        require(second_status == 409, "duplicate return should be rejected with conflict")
        require(second_return.get("status") == "duplicate_return_rejected", "duplicate status mismatch")
        duplicate_receipt = Path(str(second_return.get("duplicate_receipt_path", "")))
        duplicate_record = Path(str(second_return.get("duplicate_record_path", "")))
        require(duplicate_receipt.exists(), "duplicate rejection receipt missing")
        require(duplicate_record.exists(), "duplicate rejection record missing")
        receipt_text = duplicate_receipt.read_text(encoding="utf-8")
        require("DUPLICATE RETURN REJECTED - NOT APPLIED" in receipt_text, "duplicate receipt missing decision")

        no_claim_status, no_claim = module.return_result_response(
            safe_result("phase9-never-claimed"),
            remote_address="127.0.0.1",
            claimed_dir=claimed,
            returned_dir=returned,
            report_dir=reports,
            duplicate_dir=duplicates,
            duplicate_report_dir=duplicate_reports,
        )
        require(no_claim_status == 409 and no_claim.get("status") == "return_rejected", "unclaimed result must be rejected")

        bad = safe_result("phase9-bad-safe")
        bad["safe_to_auto_apply"] = True
        bad_status, bad_response = module.return_result_response(bad, claimed_dir=claimed, returned_dir=returned)
        require(bad_status == 400 and bad_response.get("accepted") is False, "safe_to_auto_apply true result must be rejected")

        bad = safe_result("phase9-bad-review")
        bad["requires_review"] = False
        bad_status, bad_response = module.return_result_response(bad, claimed_dir=claimed, returned_dir=returned)
        require(bad_status == 400 and bad_response.get("accepted") is False, "requires_review false result must be rejected")


def check_runtime_assignment_rejections() -> None:
    module = load_module()
    invalid_safe = safe_assignment("phase9-invalid-safe")
    invalid_safe["safe_to_auto_apply"] = True
    require(
        any("safe_to_auto_apply" in error for error in module.validate_assignment_packet(invalid_safe)),
        "safe_to_auto_apply true assignment must be rejected",
    )
    invalid_review = safe_assignment("phase9-invalid-review")
    invalid_review["requires_review"] = False
    require(
        any("requires_review" in error for error in module.validate_assignment_packet(invalid_review)),
        "requires_review false assignment must be rejected",
    )
    invalid_task = safe_assignment("phase9-invalid-task")
    invalid_task["task_type"] = "execute_command"
    require(
        any("blocked task type" in error for error in module.validate_assignment_packet(invalid_task)),
        "blocked task type must be rejected",
    )
    missing_block = safe_assignment("phase9-missing-block")
    missing_block["blocked_actions"] = [action for action in REQUIRED_BLOCKED_ACTIONS if action != "control_engel"]
    require(
        any("control_engel" in error for error in module.validate_assignment_packet(missing_block)),
        "missing required blocked action must be rejected",
    )


def check_flutter_foreground_safety() -> None:
    main = read(MAIN_DART)
    client = read(LAN_CLIENT_DART)
    manifest = read(ANDROID_MANIFEST)
    require("Duplicate return rejected - review-only, not applied." in client, "Flutter client must display duplicate rejection")
    for forbidden in [
        "Isolate.spawn",
        "Workmanager",
        "android.permission.WAKE_LOCK",
        "BOOT_COMPLETED",
        "<service",
        "<receiver",
        "Apply Fix",
        "Execute",
        "Run Route",
        "Control Engel",
        "Write Memory",
    ]:
        require(forbidden not in main + client + manifest, "Flutter/Android contains forbidden behavior: " + forbidden)


def check_docs_and_phase8_evidence() -> None:
    report = read(REPORT)
    phase8 = read(PHASE8_REPORT)
    commands = read(COMMANDS)
    codex = read(CODEX_VERIFY)
    for phrase in [
        "same assignment claimed/returned multiple times",
        "claim locking",
        "move-on-claim",
        "duplicate return guard",
        "DUPLICATE RETURN REJECTED - NOT APPLIED",
        "Phase 9 prevents repeated claims/returns of the same assignment",
    ]:
        require(phrase in report, "Phase 9 report missing phrase: " + phrase)
    require("Duplicate claim observation" in phase8, "Phase 8 duplicate observation must remain documented")
    # approved/ may contain real producer-created assignments after the
    # producer was generalized to multi-worker. Verify each .json validates
    # against the producer schema; reject non-.json/non-.gitkeep noise.
    files = sorted(path for path in APPROVED_DIR.iterdir() if path.is_file())
    json_files = [p for p in files if p.suffix.lower() == ".json"]
    other = [p for p in files if p.suffix.lower() != ".json" and p.name != ".gitkeep"]
    require(not other, "approved folder must only contain .json assignment packets and .gitkeep, found: " + ", ".join(p.name for p in other))
    if json_files:
        import sys as _sys
        if str(ROOT) not in _sys.path:
            _sys.path.insert(0, str(ROOT))
        import importlib.util as _ilu
        _name = "claim_lock_producer_validator"
        spec = _ilu.spec_from_file_location(_name, str(ROOT / "engel_communication_queen_assignment_producer.py"))
        producer = _ilu.module_from_spec(spec)
        _sys.modules[_name] = producer
        spec.loader.exec_module(producer)
        for path in json_files:
            payload = json.loads(path.read_text(encoding="utf-8"))
            errors = producer.validate_assignment_packet(payload)
            require(not errors, f"approved assignment {path.name} failed validation: {errors}")
    require("remote worker assignment lock status" in commands, "commands doc missing assignment lock status")
    require("remote worker duplicate guard status" in commands, "commands doc missing duplicate guard status")
    require("tools\\verify_engel_remote_worker_claim_lock.py" in codex, "codex verifier missing claim-lock verifier")


def main() -> int:
    checks = [
        check_files,
        check_static_safety,
        check_runtime_claim_lock_and_duplicate_guard,
        check_runtime_assignment_rejections,
        check_flutter_foreground_safety,
        check_docs_and_phase8_evidence,
    ]
    failures: list[str] = []
    for check in checks:
        try:
            check()
            print(f"PASS {check.__name__}")
        except Exception as exc:  # noqa: BLE001 - verifier reports local failure details
            failures.append(f"{check.__name__}: {exc}")
            print(f"FAIL {check.__name__}: {exc}")
    if failures:
        print("ENGEL_REMOTE_WORKER_CLAIM_LOCK_VERIFY_FAIL")
        return 1
    print("ENGEL_REMOTE_WORKER_CLAIM_LOCK_VERIFY_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
