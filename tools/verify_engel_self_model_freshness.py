#!/usr/bin/env python3
"""Verifier: the sentient self-model stays FRESH and honest about its age.

Closes the gap where the persisted self-model was a frozen snapshot nothing
refreshed (goal: introspection must rest on CURRENT evidence; criterion 10:
never claim current state without current proof).

Checks:
  1. A real observe run persists a validated state and increments the revision.
  2. The state's observed_at age computes sanely (fresh after observe).
  3. The chat service renders an honest age label into the injected context.
  4. The chat service wires fresh-observe-on-stale into the introspection
     path (rate-limited, bounded, out-of-process) and records the evidence in
     the chat receipt (source-level wiring assertions).
  5. render_context still refuses to claim without evidence (truth rule line).

Emits {"ok": bool, ...}; exit 0 pass / 1 fail.
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

import engel_self_model_runtime as runtime  # noqa: E402

CHECKS: list[dict] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append({"check": name, "ok": bool(ok), "detail": detail})


def _age_seconds(state: dict) -> "float | None":
    try:
        from datetime import datetime, timezone

        observed = str(state.get("observed_at_utc") or "").replace("Z", "+00:00")
        return (datetime.now(timezone.utc) - datetime.fromisoformat(observed)).total_seconds()
    except (ValueError, TypeError):
        return None


def main() -> int:
    # 1 + 2: real observe increments revision and produces a fresh state ------
    before_rev = 0
    if runtime.STATE_PATH.is_file():
        try:
            before_rev = int(json.loads(
                runtime.STATE_PATH.read_text(encoding="utf-8")).get("state_revision") or 0)
        except Exception:
            before_rev = 0
    proc = subprocess.run([sys.executable, str(ROOT / "tools" / "engel_self_model_runtime.py"),
                           "observe"], cwd=str(ROOT), capture_output=True, text=True, timeout=120, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    state = json.loads(runtime.STATE_PATH.read_text(encoding="utf-8"))
    valid, errors = runtime.validate_state(state)
    age = _age_seconds(state)
    record("observe persists a validated state and increments the revision",
           proc.returncode == 0 and valid and int(state.get("state_revision") or 0) == before_rev + 1,
           f"rc={proc.returncode} rev={state.get('state_revision')} errors={errors}")
    record("freshly observed state has a sane age", age is not None and 0 <= age < 300,
           f"age={age}")

    # 3: honest age label in the injected context -----------------------------
    context = runtime.render_context(state)
    service_src = (ROOT / "tools" / "engel_main_server_chat_http_service.py").read_text(
        encoding="utf-8", errors="replace")
    record("chat service annotates the injected context with observation age",
           "Self-observation age:" in service_src
           and "_self_model_state_age_seconds" in service_src, "")

    # 4: fresh-observe-on-stale wired into the introspection path -------------
    wired = ("_self_model_fresh_observe_if_stale" in service_src
             and 'request["_self_model_freshness"] = _self_model_fresh_observe_if_stale()' in service_src
             and 'receipt["self_model_freshness"]' in service_src
             and "SELF_MODEL_REFRESH_MIN_INTERVAL_SECONDS" in service_src
             and "SELF_MODEL_OBSERVE_TIMEOUT_SECONDS" in service_src)
    record("introspection queries trigger a rate-limited bounded fresh observe "
           "and the receipt records the freshness evidence", wired, "")

    # 5: the truth rule survives ----------------------------------------------
    record("rendered context keeps the no-claim-without-evidence truth rule",
           "Truth rule: do not claim" in context, "")

    failed = [c for c in CHECKS if not c["ok"]]
    receipt = {
        "schema": "engel_self_model_freshness_verifier_v1",
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
