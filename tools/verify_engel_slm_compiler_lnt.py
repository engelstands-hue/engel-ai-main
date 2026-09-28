#!/usr/bin/env python3
"""Prove SLM router, MIPL compiler, and Lifted iNTent (LNT) stay cohesive."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import engel_lifted_intent as intent  # noqa: E402
import engel_mipl  # noqa: E402


def main() -> int:
    checks: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str) -> None:
        checks.append((name, ok, detail))

    a = intent.create_intent_contract("hello Engel, how are you", caller="unit")
    b = intent.create_intent_contract("hello Engel, how are you", caller="unit")
    check(
        "compiler_is_deterministic",
        a["hash_chain"]["mipl_hash"] == b["hash_chain"]["mipl_hash"]
        and a["hash_chain"]["lifted_intent_hash"] == b["hash_chain"]["lifted_intent_hash"],
        a["hash_chain"]["mipl_hash"][:16],
    )
    check(
        "mipl_never_authorizes_execution",
        a["mipl"].get("execution_authorized") is False,
        str(a["mipl"].get("execution_authorized")),
    )
    check("lnt_is_lifted_intent", "effect" in a["lifted_intent"] and "objective" in a["lifted_intent"], str(a["lifted_intent"].get("effect")))

    fake_slm = {"ready": True, "intent": {"label": "build", "confidence": 0.91}}
    wrapped = intent.attach_slm_compiler_lnt(
        "hello Engel, how are you",
        {"ok": True, "assistant_reply": "I'm here."},
        caller="unit",
        slm_advisory=fake_slm,
    )
    check("bind_exposes_slm_router", wrapped.get("slm_router_advisory", {}).get("authority") == "advisory_only", str(wrapped.get("slm_router_advisory")))
    check("bind_exposes_compiler", wrapped.get("mipl_compiler", {}).get("execution_authorized") is False, str(wrapped.get("mipl_compiler")))
    check("bind_exposes_lnt", wrapped.get("lnt", {}).get("name") == "lifted_intent", str(wrapped.get("lnt")))
    check(
        "slm_does_not_authorize_mipl",
        wrapped.get("slm_router_advisory", {}).get("does_not_authorize_mipl") is True
        and wrapped.get("slm_router_advisory", {}).get("does_not_select_model") is True,
        "advisory",
    )
    check(
        "compiler_never_authorizes_dispatch",
        wrapped.get("mipl_compiler", {}).get("execution_authorized") is False
        and wrapped.get("mipl_compiler", {}).get("dispatch_authorization") == "external_gate_required",
        str(wrapped.get("mipl_compiler")),
    )
    vs = wrapped.get("slm_router_advisory", {}).get("slm_vs_lnt") or {}
    check(
        "slm_vs_lnt_is_observation_only",
        vs.get("does_not_mutate_hashes") is True
        and vs.get("does_not_authorize_execution") is True
        and vs.get("slm_label") == "build",
        str(vs),
    )

    other = intent.attach_slm_compiler_lnt(
        "hello Engel, how are you",
        {"ok": True, "assistant_reply": "I'm here."},
        caller="unit",
        slm_advisory={"ready": True, "intent": {"label": "chat", "confidence": 0.2}},
    )
    check(
        "slm_label_does_not_change_lnt_audit_head",
        wrapped.get("lnt", {}).get("audit_head") == other.get("lnt", {}).get("audit_head"),
        str(wrapped.get("lnt", {}).get("audit_head")),
    )

    preexisting = {
        "ok": True,
        "assistant_reply": "I'm here.",
        "lifted_intent": wrapped.get("lifted_intent"),
        "lifted_intent_receipt_path": wrapped.get("lifted_intent_receipt_path"),
    }
    stamped = intent.stamp_slm_compiler_lnt(
        preexisting,
        slm_advisory={"ready": True, "intent": {"label": "chat", "confidence": 0.4}},
    )
    check(
        "existing_compile_still_gets_lnt_stamp",
        stamped.get("lnt", {}).get("name") == "lifted_intent"
        and stamped.get("lifted_intent") == wrapped.get("lifted_intent"),
        str(stamped.get("lnt")),
    )
    ir = a.get("mipl") or {}
    check(
        "mipl_dispatch_requires_external_gate",
        ir.get("execution_authorized") is False and bool(ir.get("wire")),
        str(ir.get("execution_authorized")),
    )

    chat_src = (ROOT / "tools" / "engel_main_server_chat_http_service.py").read_text(encoding="utf-8")
    check(
        "ct_chat_binds_slm_compiler_lnt",
        "def _attach_slm_compiler_lnt(" in chat_src
        and "_attach_slm_compiler_lnt(receipt, prompt, source)" in chat_src
        and "stamp_slm_compiler_lnt" in chat_src,
        "chat service",
    )
    worker_src = (ROOT / "tools" / "engel_main_local_model_worker.py").read_text(encoding="utf-8")
    check(
        "worker_still_attaches_intent",
        "attach_slm_compiler_lnt" in worker_src,
        "worker",
    )
    kernel_src = (ROOT / "engel_agent_kernel.py").read_text(encoding="utf-8")
    check(
        "kernel_stamps_slm_compiler_lnt",
        "stamp_slm_compiler_lnt" in kernel_src,
        "kernel",
    )
    check("mipl_module_present", hasattr(engel_mipl, "compile_intent_ir"), "engel_mipl")

    failed = [name for name, ok, _ in checks if not ok]
    for name, ok, detail in checks:
        print(("PASS" if ok else "FAIL"), name, "::", str(detail)[:160])
    print(f"{sum(1 for _, ok, _ in checks if ok)}/{len(checks)} checks passed")
    print("verify_engel_slm_compiler_lnt: " + ("GREEN" if not failed else "RED"))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
