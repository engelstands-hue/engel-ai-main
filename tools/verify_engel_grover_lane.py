#!/usr/bin/env python3
"""Gate for Engel's verified Grover lane."""
from __future__ import annotations

import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import engel_grover_lane as grover  # noqa: E402

SERVICE = ROOT / "tools" / "engel_main_server_chat_http_service.py"
ROUTES = ROOT / "engel_ai_update_routes.py"
EXPLORER = ROOT / "engel_route_explorer.py"

CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""))


def main() -> int:
    sim = grover.grover_simulate(4, 0)
    check("n4_one_iteration", sim.get("iterations") == 1)
    check("n4_success_is_one", abs(float(sim.get("success_probability") or 0) - 1.0) < 1e-9)
    check("n4_verified", sim.get("verified") is True)
    check(
        "query_count_formula",
        grover.grover_iterations(16) == int(math.pi / 4 * math.sqrt(16)),
    )
    theory = grover.grover_theory_success(16, grover.grover_iterations(16))
    sim16 = grover.grover_simulate(16, 3)
    check("n16_matches_theory", abs(float(sim16["success_probability"]) - theory) < 1e-9)
    check("n16_picks_marked", sim16.get("best_index") == 3)

    crypto = grover.grover_crypto_bits(128)
    check("aes128_heuristic_64", crypto.get("grover_heuristic_bits") == 64)
    caveat = str(crypto.get("caveat") or "")
    check("crypto_mentions_sequential", "sequential" in caveat.casefold())
    check("crypto_mentions_pqc", "pqc" in caveat.casefold() or "ml-kem" in caveat.casefold())
    check("crypto_mentions_shor", "shor" in caveat.casefold())

    facts = grover.grover_facts()
    check("quadratic_not_exponential", "quadratic" in facts["not_exponential"].casefold())
    check("overshoot_named", "overshoot" in facts["success"].casefold())

    check("detects_explain", grover.detect_grover_request("Explain Grover's algorithm speedup") is True)
    check("detects_quantum_search", grover.detect_grover_request("how does quantum unstructured search work") is True)
    check("ignores_grok", grover.detect_grover_request("search the grok bot list") is False)
    check("ignores_workspace_search", grover.detect_grover_request("search the workspace for AES-256-GCM at rest") is False)
    check("ignores_shor_only", grover.detect_grover_request("explain Shor's algorithm for RSA") is False)
    vs = grover.answer_grover_prompt("Grover vs Shor, which one breaks RSA?")
    check("grover_vs_shor_is_grover", vs.get("grover_request") is True)
    check("vs_says_shor_breaks_rsa", "shor" in str(vs.get("result_text") or "").casefold())

    explained = grover.answer_grover_prompt("what is grover's algorithm")
    check("explain_ok", explained.get("ok") is True and explained.get("verified") is True)
    check("explain_has_pi_over_4", "pi/4" in str(explained.get("result_text") or "").casefold() or "π" in str(explained.get("result_text") or ""))

    demo = grover.answer_grover_prompt("simulate grover n=4 marked=0")
    check("simulate_ok", demo.get("ok") is True and demo.get("mode") == "simulate")

    service = SERVICE.read_text(encoding="utf-8")
    routes = ROUTES.read_text(encoding="utf-8")
    explorer = EXPLORER.read_text(encoding="utf-8")
    check("service_has_grover_turn", "def _grover_lane_turn(" in service)
    check("service_depth_map_has_ct_grover_lane", bool(re.search(r'"ct_grover_lane":\s*0', service)))
    check("service_calls_grover_after_math", service.find("_math_lane_turn(prompt, started)") < service.find("_grover_lane_turn(prompt, started)"))
    check("routes_have_explain", "engel.grover.explain" in routes)
    check("routes_have_search", "engel.grover.search" in routes)
    check("explorer_groups_grover", 'startswith("engel.grover")' in explorer)
    check("status_renderer", "Verified Grover" in grover.render_grover_search("simulate grover n=4 marked=0") or "N=4" in grover.render_grover_search("n=4 marked=0"))

    failed = [name for name, ok, _ in CHECKS if not ok]
    print("")
    print(f"{len(CHECKS) - len(failed)}/{len(CHECKS)} checks passed")
    if failed:
        print("FAILED: " + ", ".join(failed))
        return 1
    print("ENGEL_GROVER_LANE_VERIFIER_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
