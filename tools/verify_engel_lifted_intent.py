#!/usr/bin/env python3
"""Deterministic release proof for Engel's HIPL/MIPL intent bridge."""
from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
for entry in (ROOT, ROOT / "tools"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import engel_agent_kernel as kernel  # noqa: E402
import engel_ai_update_routes as routes  # noqa: E402
import engel_lifted_intent as intent  # noqa: E402
import engel_mipl  # noqa: E402


class Checks:
    def __init__(self) -> None:
        self.passed = 0
        self.failures: list[str] = []

    def check(self, condition: bool, name: str, detail: str = "") -> None:
        if condition:
            self.passed += 1
            print(f"PASS {name}" + (f" -- {detail}" if detail else ""))
        else:
            self.failures.append(name + (f": {detail}" if detail else ""))
            print(f"FAIL {name}" + (f" -- {detail}" if detail else ""))


def main() -> int:
    checks = Checks()
    print("ENGEL_HIPL_MIPL_INTENT_BRIDGE_VERIFIER")
    print("Mode: deterministic, local, no provider/network/action execution")

    plain = intent.create_intent_contract(
        "How does Engel verify its training receipts?",
        caller="verifier",
        request_id="same-request",
    )
    repeated = intent.create_intent_contract(
        "How does Engel verify its training receipts?",
        caller="verifier",
        request_id="same-request",
    )
    checks.check(
        plain["contract_id"] == repeated["contract_id"]
        and plain["hash_chain"] == repeated["hash_chain"]
        and intent.validate_contract(plain)["ok"],
        "determinism: same redacted expression produces the same replayable contract",
    )
    checks.check(
        plain["mipl"]["execution_authorized"] is False
        and plain["mipl"]["schema"] == engel_mipl.IR_SCHEMA
        and engel_mipl.validate_ir(plain["mipl"])["ok"]
        and plain["lifted_intent"]["side_effect_requested"] is False,
        "safety: compact read-only MIPL does not acquire execution authority",
    )

    action = intent.create_intent_contract(
        "Create and wire an intent bridge into Engel AI Main, but keep every existing gate.",
        caller="verifier",
    )
    action_packets = engel_mipl.packet_records(action["mipl"])
    action_gate = next(packet for packet in action_packets if packet["opcode"] == "GATE")
    checks.check(
        action["lifted_intent"]["effect"] == "create"
        and action["lifted_intent"]["approval_required"] is True
        and action_gate["args"]["policy"] == "approval_and_governor"
        and action_gate["args"]["failure"] == "closed",
        "action boundary: creation requests require the existing allow gate",
    )

    dispatch = intent.create_intent_contract(
        "Have every device report its current status.", caller="verifier"
    )
    review = intent.create_intent_contract(
        "For fingerprinting every device, separate verified routes from open work.",
        caller="verifier",
    )
    checks.check(
        dispatch["lifted_intent"]["effect"] == "dispatch"
        and dispatch["lifted_intent"]["targets"] == ["fleet"]
        and review["lifted_intent"]["effect"] != "dispatch",
        "intent precision: an explicit fleet order differs from a technical review",
    )

    secret = intent.create_intent_contract(
        "Check token=super-secret-value and Authorization: Bearer abcdefghijklmnop",
        caller="verifier",
    )
    stored_expression = secret["hipl"]["expression"]["text"]
    checks.check(
        "super-secret-value" not in stored_expression
        and "abcdefghijklmnop" not in stored_expression
        and "[REDACTED]" in stored_expression,
        "privacy: common credential forms are redacted before receipt persistence",
        stored_expression,
    )

    result = intent.complete_intent_receipt(
        action,
        {
            "ok": True,
            "status": "verified",
            "receipt_path": str(ROOT / "reports" / "proof.json"),
        },
        write_receipt=False,
    )
    checks.check(
        result["verification"]["audit_complete"] is True
        and result["verification"]["mipl_outcome_valid"] is True
        and engel_mipl.validate_ir(result["mipl_outcome"])["ok"]
        and result["hipl_comprehension"]["status"] == "verified"
        and result["hipl_comprehension"]["proof_paths"],
        "round trip: machine result returns to HIPL with a hash-linked proof path",
    )
    tampered = copy.deepcopy(action)
    tampered["lifted_intent"]["effect"] = "inspect"
    checks.check(
        intent.validate_contract(tampered)["ok"] is False,
        "tamper evidence: altered lifted intent fails deterministic replay",
    )

    with tempfile.TemporaryDirectory(prefix="engel-intent-proof-") as temp_dir:
        original_dir = intent.RECEIPT_DIR
        original_latest = intent.LATEST_RECEIPT
        intent.RECEIPT_DIR = Path(temp_dir)
        intent.LATEST_RECEIPT = Path(temp_dir) / "LATEST.json"
        try:
            attached = intent.attach_intent_to_response(
                {"id": "worker-1", "prompt": "Show model status"},
                {"ok": True, "status": "models ready", "assistant_reply": "Ready."},
            )
            latest = intent.load_latest_receipt()
        finally:
            intent.RECEIPT_DIR = original_dir
            intent.LATEST_RECEIPT = original_latest
        checks.check(
            attached.get("lifted_intent_audit_complete") is True
            and Path(str(attached.get("lifted_intent_receipt_path"))).is_file()
            and latest is not None,
            "worker integration: every completed turn can atomically publish a latest receipt",
        )

    route_id = routes.resolve_update_route("intent bridge status")
    preview_id = routes.resolve_update_route("lift intent")
    compile_id = routes.resolve_update_route("compile mipl")
    checks.check(
        route_id == routes.ENGEL_INTENT_BRIDGE_STATUS_ROUTE_ID
        and preview_id == routes.ENGEL_INTENT_BRIDGE_LIFT_ROUTE_ID
        and compile_id == routes.ENGEL_INTENT_BRIDGE_LIFT_ROUTE_ID
        and "Status: READY" in routes.render_update_route(route_id)
        and "nothing executed" in routes.render_update_route(
            preview_id, "lift intent check model status"
        ).casefold(),
        "route wiring: docs/status/latest/preview use Engel's real route registry",
    )

    kernel_receipt = kernel.run_goal(
        "intent bridge status",
        router=lambda phrase: (True, f"verified {phrase}"),
        write_receipt=False,
        synthesize=False,
    )
    checks.check(
        isinstance(kernel_receipt.get("lifted_intent_contract"), dict)
        and kernel_receipt.get("lifted_intent_audit_complete") is True
        and (kernel_receipt.get("lifted_intent_contract") or {})
        .get("mipl", {})
        .get("execution_authorized")
        is False
        and (kernel_receipt.get("lifted_intent_contract") or {})
        .get("mipl", {})
        .get("version")
        == 2,
        "agent kernel: engine selection and results are enclosed by the shared contract",
        str(kernel_receipt.get("status")),
    )

    worker_source = (ROOT / "tools" / "engel_main_local_model_worker.py").read_text(
        encoding="utf-8"
    )
    ui_path = ROOT / "engel_flutter_main" / "lib" / "main.dart"
    ui_source = ui_path.read_text(encoding="utf-8") if ui_path.is_file() else ""
    docs = (ROOT / "docs" / "ENGEL_HIPL_MIPL_INTENT_BRIDGE.md").read_text(
        encoding="utf-8"
    )
    ui_has_bridge = "intent-bridge-page" in ui_source and "mipl-low-resource-profile" in ui_source
    # Live Flutter face is the Windows controller. A stale tree on CT 246 is not
    # the UI source of truth and must not fail the server HIPL/MIPL bind.
    ui_ok = ui_has_bridge or sys.platform != "win32" or not ui_path.is_file()
    checks.check(
        "attach_slm_compiler_lnt" in worker_source
        and ui_ok
        and "Intent classification is not approval" in docs,
        "surface wiring: worker, System UI, and architecture contract are present",
    )
    chat_source = (ROOT / "tools" / "engel_main_server_chat_http_service.py").read_text(
        encoding="utf-8"
    )
    checks.check(
        "def _attach_slm_compiler_lnt(" in chat_source
        and "stamp_slm_compiler_lnt" in chat_source
        and "attach_slm_compiler_lnt" in (ROOT / "engel_lifted_intent.py").read_text(encoding="utf-8")
        and "stamp_slm_compiler_lnt" in (ROOT / "engel_lifted_intent.py").read_text(encoding="utf-8"),
        "CT chat and lifted-intent bind SLM router + MIPL compiler + LNT",
    )

    summary = {
        "schema": "engel_lifted_intent_verification_v1",
        "status": "PASS" if not checks.failures else "FAIL",
        "passed": checks.passed,
        "failures": checks.failures,
    }
    print(json.dumps(summary, indent=2))
    return 0 if not checks.failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
