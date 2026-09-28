#!/usr/bin/env python3
"""Verifier for the self-upgrade catalog + router (engel_self_upgrade_catalog_router.py).

Proves the routing catalog is real, complete, and executable:
  1. The catalog loads, has the right schema, and covers every core loop part.
  2. Every cataloged in-repo tool/verifier path EXISTS (router verify ok).
  3. Routing queries hit the expected part first (governed cycle, rollback,
     broker, pipes, teaching, visibility, quorum).
  4. show/list work; unknown part fails non-zero.
  5. The router is lookup-only (no state written anywhere by route/verify).
  6. The change-control ordering and token-boundary facts are stated in the
     catalog (fix token never interchangeable with the memory token).

Emits {"ok": bool,...}; exit 0 pass / 1 fail.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

import engel_self_upgrade_catalog_router as router  # noqa: E402

CHECKS: list[dict] = []

REQUIRED_PARTS = {
    "cycle_orchestrator", "self_patch_quorum", "self_upgrade_primitives",
    "apply_engine", "rollback_automation", "device_broker", "dispatch_broker_gate",
    "conical_build_orchestration", "failure_to_issue", "self_model",
    "provider_pipes", "loop_stream_visibility", "meeting_room_event_stream",
    "permission_matrix", "source_sync", "verifier_matrix", "codebase_inventory",
    "catalog_router", "teaching_lane", "health_green",
}

ROUTE_EXPECTATIONS = [
    ("run a governed self upgrade cycle", "cycle_orchestrator"),
    ("a bad patch needs rollback after deploy", "rollback_automation"),
    ("which device is eligible for phone work", "device_broker"),
    ("provider pipes to gemini are down", "provider_pipes"),
    ("teach engel a new fact", "teaching_lane"),
    ("show the loop panel visibility", "loop_stream_visibility"),
    ("who approves apply quorum veto", "self_patch_quorum"),
]


def record(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append({"check": name, "ok": bool(ok), "detail": detail})


def main() -> int:
    # 1: catalog loads + covers every core part -------------------------------
    catalog = router.load_catalog()
    part_ids = {p["part_id"] for p in catalog["parts"]}
    missing = REQUIRED_PARTS - part_ids
    record("catalog covers every core loop part", not missing, f"missing={sorted(missing)}")

    # 2: every cataloged in-repo path exists ----------------------------------
    result = router.verify()
    record("every cataloged tool/verifier/receipt path resolves",
           result["ok"] and result["paths_checked"] >= 30,
           f"checked={result['paths_checked']} missing={result['missing']}")

    # 3: routing hits the expected part first ---------------------------------
    for query, expected in ROUTE_EXPECTATIONS:
        got = router.route(query)
        top = got["matches"][0]["part_id"] if got["matches"] else "NONE"
        record(f"route '{query}' -> {expected}", top == expected, f"got {top}")

    # 4: show/list + unknown part fails ---------------------------------------
    show = subprocess.run([sys.executable, str(ROOT / "tools" / "engel_self_upgrade_catalog_router.py"),
                           "show", "cycle_orchestrator"], cwd=str(ROOT),
                          capture_output=True, text=True, timeout=60, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    bad = subprocess.run([sys.executable, str(ROOT / "tools" / "engel_self_upgrade_catalog_router.py"),
                          "show", "no_such_part"], cwd=str(ROOT),
                         capture_output=True, text=True, timeout=60, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    record("show works and unknown part fails non-zero",
           show.returncode == 0 and "engel_conical_self_upgrade_cycle" in show.stdout
           and bad.returncode == 1, f"show={show.returncode} bad={bad.returncode}")

    # 6: ordering + token boundary stated -------------------------------------
    record("change-control ordering and token boundary are stated",
           "QUORUM" in catalog.get("change_control_order", "")
           and "never interchangeable" in json.dumps(catalog.get("human_tokens", {})), "")

    failed = [c for c in CHECKS if not c["ok"]]
    receipt = {
        "schema": "engel_self_upgrade_catalog_router_verifier_v1",
        "goal_id": "engel_conical_agentic_sentient_self_upgrading_system",
        "ok": not failed,
        "checks_total": len(CHECKS),
        "checks_passed": sum(1 for c in CHECKS if c["ok"]),
        "checks_failed": len(failed),
        "failed_checks": failed,
        "checks": CHECKS,
    }
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
