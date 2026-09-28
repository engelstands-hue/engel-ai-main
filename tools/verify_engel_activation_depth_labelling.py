#!/usr/bin/env python3
"""NT-1 verifier — activation-depth labelling.

Read-only. Emits a receipt. ok=True iff the pure _activation_depth() mapping asserts pass
(coverage of existing records is forward-looking/informational, since old records predate
the field). Loads NO model runtime and makes NO provider/network calls.

  python tools/verify_engel_activation_depth_labelling.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

RECEIPT_DIR = ROOT / "reports" / "engel_activation_depth_labelling"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


# (source, receipt-fields, expected_depth, expected_label)
CASES = [
    ("ct_provider_bridge_chat", {}, 3, "provider-bridge"),
    ("ct_model_chat", {}, 2, "big-lane"),
    ("ct_quick_local_chat", {}, 1, "quick-lane"),
    ("ct_default_fast_local_chat", {}, 1, "quick-lane"),
    ("ct_short_casual_fast_model", {}, 1, "quick-lane"),
    ("ct_quick_casual_chat", {}, 1, "quick-lane"),
    ("ct_mode_gate_reflex_chat", {}, 1, "quick-lane"),
    ("ct_sparse_moe_specialist", {}, 2, "big-lane"),
    ("ct_nemotron_lightning", {}, 2, "big-lane"),
    ("ct_mode_gate_memory_chat", {}, 0, "router-only"),
    ("ct_status_answer", {}, 0, "router-only"),
    # unknown source -> fall back to runtime_provider signal
    ("something_new", {"runtime_provider": "anthropic-claude-bridge"}, 3, "provider-bridge"),
    ("something_new", {"selected_provider": "gemini"}, 3, "provider-bridge"),
    ("something_new", {"runtime_provider": "rog-rtx2070-llama-cpp-gpu-stream"}, 2, "big-lane"),
    ("something_new", {"provider": "local-llama-cpp-large-chat-gguf"}, 2, "big-lane"),
    ("something_new", {"runtime_provider": "llama-cpp-qwen3-sparse-moe-selective-experts-local"}, 2, "big-lane"),
    ("something_new", {"runtime_provider": "llama-cpp-python-local-gguf-fast-casual"}, 1, "quick-lane"),
    ("something_new", {"runtime_provider": "llama-cpp-python-local-gguf"}, 1, "quick-lane"),  # quick lane's OWN record (no -fast suffix)
    ("something_new", {"quick_casual_model_used": True}, 1, "quick-lane"),
    ("something_new", {"quick_local_front_lane_used": True}, 1, "quick-lane"),
    # big lane's gguf provider must still map to 2 (big-lane check precedes the gguf fallback)
    ("something_new", {"provider": "local-llama-cpp-large-chat-gguf-stream"}, 2, "big-lane"),
    ("something_new", {}, 0, "router-only"),
    # escalation passthrough
    ("ct_provider_bridge_chat", {}, 3, "provider-bridge"),  # esc handled separately below
    # ---- 2026-07-26 neuro audit: REAL production strings that were mislabelled ----
    # CPU-LoRA big lane (the merged aligned GGUF) must be depth 2, not the gguf fallback
    ("something_new", {"runtime_provider": "local-llama-cpp-lora",
                       "provider": "local-llama-cpp-qwen2.5-7b-lora-gguf"}, 2, "big-lane"),
    # zero-inference template/fast responders must NEVER claim a model lane
    ("something_new", {"runtime_provider": "engel-main-server-fast-responder",
                       "runs_inference": False}, 0, "router-only"),
    ("something_new", {"runtime_provider": "engel-main-server-fast-route-check",
                       "runs_inference": False}, 0, "router-only"),
    # deterministic template routes are mapped-0 AUTHORITATIVELY (no heuristic fallthrough)
    ("ct_reps_template_chat", {"runtime_provider": "engel-main-server-fast-responder"}, 0, "router-only"),
    ("ct_fast_route_check", {}, 0, "router-only"),
    ("ct_fast_help_next", {}, 0, "router-only"),
    ("ct_fast_build_status", {}, 0, "router-only"),
    ("ct_fast_template_loop_repair", {}, 0, "router-only"),
    ("ct_fast_chat_fault_repair", {}, 0, "router-only"),
    ("ct_help_next_chat", {}, 0, "router-only"),
    ("ct_deterministic_visible_chat", {}, 0, "router-only"),
    ("ct_instant_desktop_chat", {}, 0, "router-only"),
    ("ct_fast_visible_chat", {}, 0, "router-only"),
    # the quick lane's deterministic-arithmetic bypass declares runs_inference=False
    ("something_new", {"runtime_provider": "llama-cpp-python-local-gguf",
                       "runs_inference": False, "deterministic_answer": True}, 0, "router-only"),
]


def main() -> int:
    failures: list[str] = []
    import_ok = False
    try:
        import engel_main_server_chat_http_service as svc  # noqa: E402
        import_ok = True
    except Exception as exc:
        failures.append(f"import engel_main_server_chat_http_service failed: {exc}")

    if import_ok:
        fn = getattr(svc, "_activation_depth", None)
        if fn is None:
            failures.append("_activation_depth not found in module")
        else:
            for source, fields, exp_d, exp_lbl in CASES:
                try:
                    d, lbl, esc = fn(dict(fields), source)
                except Exception as exc:
                    failures.append(f"_activation_depth raised for source={source!r}: {exc}")
                    continue
                if d != exp_d or lbl != exp_lbl:
                    failures.append(f"source={source!r} fields={fields} -> ({d},{lbl}) expected ({exp_d},{exp_lbl})")
            # escalation passthrough
            try:
                d, lbl, esc = fn({}, "ct_provider_bridge_chat", 2)
                if esc != 2:
                    failures.append(f"escalated_from passthrough broken: got {esc} expected 2")
            except Exception as exc:
                failures.append(f"escalated_from case raised: {exc}")
            # A provider receipt can arrive with escalated_from=None already
            # present. Finalization must replace that placeholder with the real
            # local-to-provider depth instead of preserving None via setdefault.
            originals = {
                "_apply_global_chat_safety": svc._apply_global_chat_safety,
                "_meeting_room_skipped": svc._meeting_room_skipped,
                "_ensure_final_chat_memory": svc._ensure_final_chat_memory,
            }
            try:
                svc._apply_global_chat_safety = lambda _p, receipt, _s: receipt
                svc._meeting_room_skipped = lambda reason: {"ok": False, "reason": reason}
                svc._ensure_final_chat_memory = lambda receipt, _p, _r, _s: receipt
                finalized = svc._finalize_chat_receipt(
                    {"ok": True, "assistant_reply": "ok", "escalated_from": None},
                    "prompt",
                    "ok",
                    "ct_provider_bridge_chat",
                    0.0,
                    allow_room=False,
                    allow_reps=False,
                    escalated_from=2,
                )
                if finalized.get("escalated_from") != 2:
                    failures.append("finalization preserved escalated_from=None instead of replacing it with 2")
            except Exception as exc:
                failures.append(f"finalize escalated_from case raised: {exc}")
            finally:
                for name, value in originals.items():
                    setattr(svc, name, value)

    # (b) coverage scan of local records (informational; old records predate the field)
    coverage = {"scanned": 0, "labelled": 0, "histogram": {}, "unmapped_sources": []}
    try:
        mem_path = getattr(svc, "PERSISTENT_CHAT_MEMORY_PATH", None) if import_ok else None
        if mem_path and Path(mem_path).is_file():
            lines = Path(mem_path).read_text(encoding="utf-8", errors="replace").splitlines()[-500:]
            known = set(getattr(svc, "_SOURCE_ACTIVATION_DEPTH", {}).keys())
            seen_src = set()
            for ln in lines:
                try:
                    o = json.loads(ln)
                except Exception:
                    continue
                coverage["scanned"] += 1
                if o.get("activation_depth") is not None:
                    coverage["labelled"] += 1
                    k = str(o.get("activation_depth_label") or o.get("activation_depth"))
                    coverage["histogram"][k] = coverage["histogram"].get(k, 0) + 1
    except Exception as exc:
        coverage["scan_error"] = str(exc)

    ok = not failures
    receipt = {
        "schema": "engel_activation_depth_labelling_receipt_v1",
        "task": "NT-1 activation-depth labelling",
        "created_at_utc": _now(),
        "ok": ok,
        "import_ok": import_ok,
        "cases_total": len(CASES) + 1,
        "cases_failed": len(failures),
        "failures": failures,
        "coverage": coverage,
        "read_only": True,
        "model_runtime_loaded": False,
        "provider_calls_made": False,
    }
    RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    rp = RECEIPT_DIR / f"ENGEL_ACTIVATION_DEPTH_LABELLING_{_now()}.json"
    rp.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"NT-1 verifier: {'PASS' if ok else 'FAIL'}  ({len(failures)} failures)")
    for f in failures:
        print("  !!", f)
    cov = coverage
    print(f"  coverage: {cov.get('labelled',0)}/{cov.get('scanned',0)} local records labelled; hist={cov.get('histogram',{})}")
    print(f"  receipt: {rp}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
