#!/usr/bin/env python3
"""Verify Engel's ModelExpress control plane and its honesty about the data plane.

The point of most of these checks is that MX must never CLAIM a transport it cannot
perform. Peer GPUDirect RDMA needs >=2 GPUs plus NIXL plus an RDMA fabric; GPUDirect
Storage needs a cuFile/kvikio binding. On hardware missing those, a plan that quietly
said "RDMA" would send a caller down a path that cannot move a byte, so every refusal
has to carry its reason.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for candidate in (str(ROOT), str(ROOT / "tools")):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

import engel_model_express as mx  # noqa: E402

CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""))


def main() -> int:
    caps = mx.mx_capabilities()
    transports = caps.get("transports", {})

    check("capabilities_report_schema", caps.get("schema") == mx.SCHEMA_CAPS)
    check(
        "posix_transport_always_available",
        transports.get(mx.TRANSPORT_POSIX, {}).get("available") is True,
        "POSIX is the documented default and must never be reported unavailable",
    )

    # Honesty: an unavailable transport must say WHY; an available one must not.
    for name, info in transports.items():
        if info.get("available") is True:
            check(
                f"available_transport_has_no_excuses[{name}]",
                not info.get("reasons_unavailable"),
            )
        else:
            check(
                f"unavailable_transport_states_reason[{name}]",
                bool(info.get("reasons_unavailable")),
            )

    # Prerequisites: never advertise a transport whose hardware/library is absent.
    if transports.get(mx.TRANSPORT_P2P_RDMA, {}).get("available") is True:
        check(
            "p2p_claim_backed_by_prerequisites",
            int(caps.get("gpu_count") or 0) >= 2
            and caps.get("nixl_present") is True
            and caps.get("rdma_fabric_present") is True,
            "claimed peer RDMA without >=2 GPUs + NIXL + RDMA fabric",
        )
    else:
        check("p2p_claim_backed_by_prerequisites", True, "not claimed")
    if transports.get(mx.TRANSPORT_GDS, {}).get("available") is True:
        check(
            "gds_claim_backed_by_prerequisites",
            caps.get("nixl_present") is True and caps.get("gds_binding_present") is True,
            "claimed GPUDirect Storage without NIXL + a cuFile/kvikio binding",
        )
    else:
        check("gds_claim_backed_by_prerequisites", True, "not claimed")

    check(
        "metadata_store_backend_declared",
        bool(caps.get("metadata_store_backend")) and bool(caps.get("metadata_store_note")),
        "the Redis/K8s substitution must be stated, not hidden",
    )

    # Registry round-trip on a throwaway model id.
    with tempfile.TemporaryDirectory() as tmp:
        fake = Path(tmp) / "verify_mx_weights.bin"
        fake.write_bytes(b"\x00" * (3 * 1024 * 1024))
        model_id = "__verify_mx__.gguf"
        mx.forget(model_id=model_id)
        mx.register_resident_weights(
            model_id=model_id,
            weights_path=str(fake),
            holder="verifier:file-storage",
            device=f"file:{fake.parent.name}",
            bytes_total=fake.stat().st_size,
            lane="verifier",
            resident=False,
        )
        holders = mx.locate(model_id)
        check("registry_register_then_locate", len(holders) == 1, f"{len(holders)} holders")

        plan = mx.plan_load(model_id, requesting_holder="verifier:new-engine")
        check("plan_schema", plan.get("schema") == mx.SCHEMA_PLAN)
        check("plan_found_a_transport", plan.get("ok") is True, str(plan.get("status")))
        check(
            "plan_records_every_transport_considered",
            len(plan.get("transports_considered") or []) >= 1
            and all(item.get("why") for item in plan["transports_considered"]),
            "each considered transport needs a reason",
        )
        check(
            "plan_chose_an_available_transport",
            transports.get(plan.get("transport"), {}).get("available") is True,
            f"chose {plan.get('transport')}",
        )
        check(
            "plan_exactly_one_chosen",
            sum(1 for i in plan["transports_considered"] if i.get("chosen")) == 1,
        )

        streamed = mx.stream_weights(str(fake), verify_sha256=True)
        check("streamer_reads_all_bytes", streamed.get("bytes_read") == fake.stat().st_size)
        check("streamer_reports_throughput", float(streamed.get("throughput_mib_s") or 0) > 0)
        check("streamer_verifies_digest", len(str(streamed.get("sha256") or "")) == 64)

        missing = mx.stream_weights(str(fake.parent / "does_not_exist.bin"))
        check("streamer_fails_loudly_on_missing", missing.get("ok") is False)

        # A holder that unloads must be forgettable, or the broker keeps recommending it.
        dropped = mx.forget(model_id=model_id)
        check("registry_forget_removes_entry", dropped == 1, f"dropped {dropped}")
        check("registry_forget_is_effective", mx.locate(model_id) == [])

    # Unknown models must not invent a source.
    empty = mx.plan_load("__definitely_not_registered__.gguf")
    check("unknown_model_yields_no_plan", empty.get("ok") is False, str(empty.get("status")))

    # ---- placement audit: best hardware per model, with reasons -------------
    placement = mx.placement_report()
    check("placement_report_ok", placement.get("ok") is True)
    roles = placement.get("roles") or []
    check("placement_covers_all_serving_lanes", len(roles) >= 8, f"{len(roles)} roles")
    unreasoned = [r["role"] for r in roles if not str(r.get("why") or "").strip()]
    check("every_placement_has_a_reason", not unreasoned, str(unreasoned))
    gpu_roles = [r for r in roles if "cuda" in str(r.get("device", ""))]
    check("gpu_hosts_latency_critical_chat",
          any(r["role"] == "general_chat_big_lane" for r in gpu_roles),
          "the fastest device must carry the highest-traffic role")
    tradeoffs = [r for r in roles if r.get("placement") == "documented_tradeoff"]
    check("tradeoffs_are_explicit_not_silent",
          all(len(str(r.get("why"))) > 60 for r in tradeoffs),
          "a tradeoff placement needs a real justification, not a shrug")
    check("throughput_measurements_are_dated",
          all(m.get("measured_at") for m in placement.get("measured_throughput", {}).values()),
          "undated benchmarks rot into fiction")

    # Loopback-only policy is enforced in code, not just documented.
    server_src = (ROOT / "tools" / "engel_model_express_server.py").read_text(
        encoding="utf-8", errors="replace"
    )
    check(
        "broker_refuses_non_loopback_bind",
        "refusing to bind a non-loopback address" in server_src,
    )

    failed = [name for name, ok, _ in CHECKS if not ok]
    print(f"\n{len(CHECKS) - len(failed)}/{len(CHECKS)} checks passed")
    if failed:
        print("FAILED: " + ", ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
