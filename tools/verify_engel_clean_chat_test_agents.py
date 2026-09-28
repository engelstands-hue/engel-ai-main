from __future__ import annotations

import json
import py_compile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "tools" / "run_engel_clean_chat_test_agents.py"
LATEST = ROOT / "runtime" / "engel_clean_chat_test_agents_latest.json"
RECEIPT_DIR = ROOT / "reports" / "engel_clean_chat_test_agents" / "receipts"

REQUIRED_AGENTS = {
    "release_verifier_agent",
    "standalone_chat_agent",
    "prompt_cleanliness_agent",
    "live_local_probe_agent",
    "runpod_live_agent",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_latest() -> dict[str, Any]:
    if LATEST.exists():
        return json.loads(LATEST.read_text(encoding="utf-8-sig"))
    receipts = sorted(RECEIPT_DIR.glob("ENGEL_CLEAN_CHAT_TEST_AGENTS_*.json"))
    require(bool(receipts), "no clean chat test-agent receipts found")
    return json.loads(receipts[-1].read_text(encoding="utf-8-sig"))


def main() -> int:
    require(RUNNER.exists(), f"missing runner: {RUNNER}")
    py_compile.compile(str(RUNNER), doraise=True)
    receipt = load_latest()
    require(receipt.get("schema") == "engel_clean_chat_test_agents_v1", "schema mismatch")
    require(receipt.get("ok") is True, "latest test-agent receipt is not ok")
    agents = receipt.get("agents") or []
    names = {agent.get("agent") for agent in agents}
    missing = REQUIRED_AGENTS - names
    require(not missing, f"missing agents: {sorted(missing)}")
    for agent in agents:
        require(agent.get("ok") is True, f"agent failed: {agent.get('agent')}")
        require(agent.get("checks") or agent.get("skipped") is True, f"agent has no checks: {agent.get('agent')}")
    standalone_agent = next(agent for agent in agents if agent.get("agent") == "standalone_chat_agent")
    standalone_check_names = {check.get("name") for check in standalone_agent.get("checks") or []}
    for required in [
        "standalone_has_live_chat_style_score_ok",
        "standalone_has_live_chat_reply_mentions_engel_ai_main",
        "standalone_has_live_chat_reply_mentions_sub_engel_or_shared_room",
        "standalone_has_live_chat_reply_mentions_receipts",
        "standalone_has_live_chat_no_training_drift",
        "standalone_has_live_chat_no_fake_proof_location",
    ]:
        require(required in standalone_check_names, f"standalone agent missing check: {required}")
    prompt_agent = next(agent for agent in agents if agent.get("agent") == "prompt_cleanliness_agent")
    check_names = {check.get("name") for check in prompt_agent.get("checks") or []}
    for required in [
        "first_prompt_has_no_pollution_terms",
        "second_prompt_has_no_pollution_terms",
        "active_session_has_no_pollution_terms",
    ]:
        require(required in check_names, f"prompt agent missing check: {required}")
    runpod_agent = next(agent for agent in agents if agent.get("agent") == "runpod_live_agent")
    if receipt.get("runpod_live_requested") is True:
        runpod_check_names = {check.get("name") for check in runpod_agent.get("checks") or []}
        require("runpod_live_return_code_zero" in runpod_check_names, "RunPod live was requested but not checked")
    print(json.dumps({
        "ok": True,
        "receipt_path": receipt.get("receipt_path"),
        "agent_count": len(agents),
        "runpod_live_requested": receipt.get("runpod_live_requested"),
    }, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        raise SystemExit(1)
