#!/usr/bin/env python3
"""Deterministic verifier for Engel MIPL/2 and its low-resource boundary."""
from __future__ import annotations

import ast
import base64
import copy
import json
import sys
import time
import tracemalloc
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import engel_lifted_intent as intent  # noqa: E402
import engel_mipl as mipl  # noqa: E402


class Checks:
    def __init__(self) -> None:
        self.passed = 0
        self.failures: list[str] = []

    def check(self, condition: bool, name: str, detail: str = "") -> None:
        if condition:
            self.passed += 1
            print(f"PASS {name}" + (f" -- {detail}" if detail else ""))
        else:
            failure = name + (f": {detail}" if detail else "")
            self.failures.append(failure)
            print(f"FAIL {failure}")


def _request(*, action: bool = False) -> dict:
    return mipl.compile_intent_ir(
        expression_hash="a" * 64,
        lifted_intent_hash="b" * 64,
        effect="create" if action else "inspect",
        targets=("engel-ai-main",),
        criteria=("Return a verifier receipt.", "Preserve failures."),
        approval_required=action,
    )


def main() -> int:
    checks = Checks()
    print("ENGEL_MIPL_V2_VERIFIER")
    print("Mode: deterministic/local; no model, provider, network, package, or execution")

    plain = _request()
    repeated = _request()
    profile = mipl.runtime_profile(plain)
    checks.check(
        plain == repeated and mipl.validate_ir(plain)["ok"],
        "compiler determinism and validation",
    )
    checks.check(
        plain["schema"] == mipl.IR_SCHEMA
        and plain["version"] == 2
        and plain["profile"] == "mipl2-low-resource"
        and plain["execution_authorized"] is False,
        "language identity and non-authorizing boundary",
    )
    checks.check(
        profile["model_required"] is False
        and profile["provider_required"] is False
        and profile["network_required"] is False
        and profile["third_party_packages_required"] is False
        and profile["executor_included"] is False,
        "low-resource profile has no hidden heavy runtime",
    )
    checks.check(
        profile["packet_count"] == 9
        and 0 < profile["encoded_bytes"] <= mipl.MAX_WIRE_BYTES
        and profile["payload_bytes"] <= mipl.MAX_PAYLOAD_BYTES,
        "request stream stays inside fixed packet and byte budgets",
        f"{profile['packet_count']} packets / {profile['encoded_bytes']} encoded bytes",
    )

    source = mipl.disassemble(plain)
    rebuilt = mipl.assemble(source)
    checks.check(
        rebuilt["wire"]["sha256"] == plain["wire"]["sha256"]
        and rebuilt["wire"]["body"] == plain["wire"]["body"],
        "assembler/disassembler wire round trip",
    )
    records = mipl.packet_records(plain)
    checks.check(
        [record["opcode"] for record in records]
        == ["BEGIN", "INTENT", "BUDGET", "RESOLVE", "GATE", "DISPATCH", "VERIFY", "RETURN", "END"],
        "complete request packet grammar",
    )
    dispatch = next(record for record in records if record["opcode"] == "DISPATCH")
    checks.check(
        dispatch["args"]["engine"] == "existing_engel_engine"
        and dispatch["args"]["authorization"] == "external_gate_required",
        "dispatch defers to Engel's existing authority and executor",
    )

    action = _request(action=True)
    action_gate = next(
        record for record in mipl.packet_records(action) if record["opcode"] == "GATE"
    )
    safe_gate = next(
        record for record in records if record["opcode"] == "GATE"
    )
    checks.check(
        action_gate["args"] == {
            "policy": "approval_and_governor",
            "failure": "closed",
        }
        and safe_gate["args"] == {
            "policy": "governor_route",
            "failure": "safe_default",
        },
        "action requests fail closed while inspection keeps a safe default",
    )

    tampered = copy.deepcopy(plain)
    container = bytearray(base64.b64decode(tampered["wire"]["body"]))
    container[-1] ^= 0x01
    tampered["wire"]["body"] = base64.b64encode(container).decode("ascii")
    checks.check(
        mipl.validate_ir(tampered)["ok"] is False,
        "tampered wire fails integrity validation",
    )

    outcome_ok = mipl.compile_outcome_ir(
        request_hash="c" * 64,
        ok=True,
        status="verified",
        result_hash="d" * 64,
        proof_paths=("reports/proof.json",),
    )
    outcome_fail = mipl.compile_outcome_ir(
        request_hash="c" * 64,
        ok=False,
        status="denied by Governor",
        result_hash="e" * 64,
        error="existing approval gate denied the action",
    )
    success_ops = [record["opcode"] for record in mipl.packet_records(outcome_ok)]
    failure_ops = [record["opcode"] for record in mipl.packet_records(outcome_fail)]
    checks.check(
        mipl.validate_ir(outcome_ok)["ok"]
        and success_ops == ["BEGIN", "RESULT", "PROOF", "RETURN", "END"],
        "successful outcome returns proof to HIPL",
    )
    checks.check(
        mipl.validate_ir(outcome_fail)["ok"]
        and failure_ops == ["BEGIN", "RESULT", "ERROR", "RETURN", "END"],
        "failed outcome returns an explicit error to HIPL",
    )

    too_large_source = source.replace(
        '"max_wire_bytes":32768', '"max_wire_bytes":999999'
    )
    try:
        mipl.assemble(too_large_source)
        oversized_rejected = False
    except mipl.MiplError:
        oversized_rejected = True
    checks.check(oversized_rejected, "assembler rejects a declared budget above profile")

    many_criteria = mipl.compile_intent_ir(
        expression_hash="1" * 64,
        lifted_intent_hash="2" * 64,
        effect="inspect",
        targets=(f"target-{index}" for index in range(50)),
        criteria=(f"criterion {index}" for index in range(50)),
        approval_required=False,
    )
    bounded_records = mipl.packet_records(many_criteria)
    bounded_targets = next(
        record["args"]["targets"] for record in bounded_records if record["opcode"] == "RESOLVE"
    )
    bounded_criteria = next(
        record["args"]["criteria"] for record in bounded_records if record["opcode"] == "VERIFY"
    )
    checks.check(
        len(bounded_targets) == mipl.MAX_TARGETS
        and len(bounded_criteria) == mipl.MAX_CRITERIA,
        "compiler bounds excessive targets and criteria",
    )

    module_source = (ROOT / "engel_mipl.py").read_text(encoding="utf-8")
    tree = ast.parse(module_source)
    imports = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    checks.check(
        not imports.intersection(
            {"requests", "httpx", "urllib", "socket", "subprocess", "threading", "asyncio"}
        )
        and not calls.intersection({"eval", "exec", "open", "system"}),
        "module contains no network, process, thread, dynamic-code, or file executor",
    )

    tracemalloc.start()
    started = time.perf_counter()
    benchmark_ir = plain
    benchmark_ok = True
    for _ in range(1_000):
        benchmark_ir = _request()
        benchmark_ok = benchmark_ok and mipl.validate_ir(benchmark_ir)["ok"]
    elapsed = time.perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    checks.check(
        benchmark_ok and elapsed < 5.0 and peak < 16 * 1024 * 1024,
        "bounded compiler/validator resource proof",
        f"1000 cycles in {elapsed:.3f}s / peak {peak / 1024:.1f} KiB",
    )

    contract = intent.create_intent_contract(
        "Inspect Engel AI Main and return verifier receipts.", caller="mipl-verifier"
    )
    receipt = intent.complete_intent_receipt(
        contract,
        {"ok": True, "status": "verified", "receipt_path": "reports/proof.json"},
        write_receipt=False,
    )
    checks.check(
        contract["mipl"]["version"] == 2
        and intent.validate_contract(contract)["ok"]
        and receipt["verification"]["mipl_outcome_valid"] is True
        and receipt["verification"]["audit_complete"] is True,
        "lifted-intent request and receipt use MIPL in both directions",
    )

    worker = (ROOT / "tools" / "engel_main_local_model_worker.py").read_text(encoding="utf-8")
    ui = (ROOT / "engel_flutter_main" / "lib" / "main.dart").read_text(encoding="utf-8")
    docs = (ROOT / "docs" / "ENGEL_HIPL_MIPL_INTENT_BRIDGE.md").read_text(encoding="utf-8")
    intercept = worker[
        worker.index("def _engel_intent_bridge_chat_intercept") : worker.index(
            "def _engel_capability_chat_intercept"
        )
    ]
    checks.check(
        "compile mipl" in worker
        and intercept.find("if low.startswith(") < intercept.find('elif "status" in low:')
        and "mipl-low-resource-profile" in ui
        and "MIPL/2 Language" in docs
        and "Intent classification is not" in docs,
        "Engel Main worker, UI, and language reference are wired",
    )

    summary = {
        "schema": "engel_mipl_v2_verification_v1",
        "status": "PASS" if not checks.failures else "FAIL",
        "passed": checks.passed,
        "failures": checks.failures,
        "benchmark": {
            "cycles": 1_000,
            "elapsed_seconds": round(elapsed, 6),
            "peak_kib": round(peak / 1024, 3),
            "sample_wire_bytes": benchmark_ir["wire"]["encoded_bytes"],
        },
    }
    print(json.dumps(summary, indent=2))
    return 0 if not checks.failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
