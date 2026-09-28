#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import threading
import time
from typing import Any
from unittest.mock import patch

from engel_local_llm_fast_fail import (
    finalize_fallback_proof,
    run_with_deadline,
    status_snapshot,
)
import engel_main_server_chat_http_service as chat_service
import run_engel_standalone_chat_llm as standalone_chat


ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def main() -> int:
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="engel-fast-fail-") as temp:
        state_root = Path(temp)

        success = run_with_deadline(
            "verifier-success",
            lambda: {"ok": True, "assistant_reply": "local answer"},
            requested_timeout=1,
            fallback_allowed=False,
            state_root=state_root,
            hard_cap=1,
            cooldown_seconds=0,
        )
        require(success.get("ok") is True, "bounded success did not pass", failures)
        require(success.get("result", {}).get("assistant_reply") == "local answer", "success result missing", failures)
        require(success.get("provider_called") is False, "success claimed a provider call", failures)

        hold_results: dict[str, Any] = {}

        def _hold() -> dict[str, Any]:
            time.sleep(0.3)
            return {"ok": True, "assistant_reply": "held"}

        def _run_hold() -> None:
            hold_results["first"] = run_with_deadline(
                "verifier-busy-hold",
                _hold,
                requested_timeout=1,
                fallback_allowed=False,
                state_root=state_root,
                hard_cap=1,
                cooldown_seconds=0,
                busy_wait_seconds=0,
            )

        holder = threading.Thread(target=_run_hold)
        holder.start()
        time.sleep(0.05)
        instant_busy = run_with_deadline(
            "verifier-busy-instant",
            lambda: {"ok": True},
            requested_timeout=1,
            fallback_allowed=False,
            state_root=state_root,
            hard_cap=1,
            cooldown_seconds=0,
            busy_wait_seconds=0,
        )
        require(instant_busy.get("busy") is True, "in-flight slot did not report busy", failures)
        waited = run_with_deadline(
            "verifier-busy-wait",
            lambda: {"ok": True, "assistant_reply": "after wait"},
            requested_timeout=1,
            fallback_allowed=False,
            state_root=state_root,
            hard_cap=1,
            cooldown_seconds=0,
            busy_wait_seconds=0.6,
        )
        require(waited.get("ok") is True, "busy wait did not take the freed slot", failures)
        holder.join(timeout=2)

        started = time.perf_counter()
        timed_out = run_with_deadline(
            "verifier-timeout",
            lambda: time.sleep(0.35),
            requested_timeout=0.05,
            fallback_allowed=True,
            state_root=state_root,
            hard_cap=0.05,
            cooldown_seconds=0.25,
        )
        elapsed = time.perf_counter() - started
        require(timed_out.get("timed_out") is True, "slow task did not time out", failures)
        require(elapsed < 0.25, f"slow task was not failed fast ({elapsed:.3f}s)", failures)
        issue_path = Path(str(timed_out.get("issue_receipt_path") or ""))
        fallback_path = Path(str(timed_out.get("fallback_proof_path") or ""))
        require(issue_path.is_file(), "timeout issue receipt missing", failures)
        require(fallback_path.is_file(), "timeout fallback proof missing", failures)

        circuit = run_with_deadline(
            "verifier-circuit",
            lambda: {"ok": True},
            requested_timeout=1,
            fallback_allowed=True,
            state_root=state_root,
            hard_cap=1,
            cooldown_seconds=0,
        )
        require(circuit.get("circuit_open") is True, "timeout did not open the bounded circuit", failures)

        final = finalize_fallback_proof(
            fallback_path,
            fallback_attempted=True,
            fallback_completed=True,
            provider_id="verified-provider",
            reason="verifier fallback completed",
        )
        final_path = Path(str(final.get("final_receipt_path") or ""))
        require(final.get("ok") is True and final_path.is_file(), "final fallback receipt missing", failures)
        require(final.get("provider_called") is True, "fallback completion did not record provider attempt", failures)

        status = status_snapshot(probe_warm=False, state_root=state_root)
        require(status.get("ok") is True, "status snapshot not ready", failures)
        require(status.get("warm_service", {}).get("status") == "warm service probe skipped", "warm status not visible", failures)
        require(status.get("external_array_used") is False, "external array appeared in status", failures)

        issue = json.loads(issue_path.read_text(encoding="utf-8")) if issue_path.is_file() else {}
        require(issue.get("prompt_or_reply_stored") is False, "timeout issue stored prompt/reply", failures)
        require(issue.get("credential_metadata_stored") is False, "timeout issue stored credential metadata", failures)
        require(issue.get("storage_mutation") is False, "timeout verifier mutated storage", failures)

    service_source = (ROOT / "tools" / "engel_main_server_chat_http_service.py").read_text(encoding="utf-8")
    require("run_with_deadline(" in service_source, "chat service does not use deadline controller", failures)
    require("/local-llm/status" in service_source, "chat service does not expose local LLM status", failures)
    require("finalize_fallback_proof(" in service_source, "chat service does not finalize fallback proof", failures)
    require(
        chat_service._prompt_requests_chat_fault_repair(
            "Hey Engel, give me a concise explanation of why a circuit breaker and a hard timeout solve different failure modes in a local chat system."
        ) is False,
        "conceptual timeout question was misrouted to chat repair",
        failures,
    )
    require(
        chat_service._prompt_requests_chat_fault_repair("Engel chat keeps timing out; fix it.") is True,
        "real chat timeout report did not enter repair lane",
        failures,
    )
    require(
        chat_service._prompt_requests_computer_memory(
            "Trying to have you look at this computers memory."
        )
        is True,
        "computer RAM look was not intercepted",
        failures,
    )
    require(
        chat_service._prompt_requests_computer_memory("where is chat memory stored") is False,
        "chat-memory question was stolen by RAM intercept",
        failures,
    )
    worker_src = (ROOT / "tools" / "engel_main_local_model_worker.py").read_text(encoding="utf-8")
    require(
        "def _apply_main_ui_local_failure_fallback(" in worker_src,
        "Cosmic Swarm worker missing local-failure NVIDIA fallback",
        failures,
    )
    require(
        "else (1800 if action_request else 90)" in worker_src,
        "ordinary Cosmic Swarm chat still caps the server turn at 45s",
        failures,
    )
    require(
        "_ACTIVE.pop(attempt_id, None)" in (ROOT / "tools" / "engel_local_llm_fast_fail.py").read_text(encoding="utf-8"),
        "timed-out local turns still occupy the in-flight slot",
        failures,
    )

    class FakeGpuResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps(
                {
                    "model": "D:/runtime/gpu_models/verified-model.gguf",
                    "choices": [{"message": {"content": "A real local answer."}}],
                }
            ).encode("utf-8")

    with patch.object(standalone_chat.urllib.request, "urlopen", return_value=FakeGpuResponse()):
        gpu_result = standalone_chat._try_rog_gpu_chat(
            prompt="Explain the result.",
            system_prompt="Be direct.",
            timeout=5,
            max_tokens=96,
        )
    require(isinstance(gpu_result, dict) and gpu_result.get("ok") is True, "mock GPU route did not reply", failures)
    require(
        (gpu_result or {}).get("model") == "D:/runtime/gpu_models/verified-model.gguf",
        "GPU route did not preserve the served model ID",
        failures,
    )
    require(
        ((gpu_result or {}).get("receipt") or {}).get("served_model") == "D:/runtime/gpu_models/verified-model.gguf",
        "GPU receipt did not preserve the served model ID",
        failures,
    )
    constrained, changes = standalone_chat.normalize_local_conversation_reply(
        "Keep it to three sentences.",
        "First point. Second point. Third point. Fourth point. Fifth point.",
    )
    constrained_count = len(
        [part for part in standalone_chat.re.split(r"(?<=[.!?])(?:\s+|$)", constrained) if part.strip()]
    )
    require(constrained_count == 3, "three-sentence limit was not enforced", failures)
    require("requested_sentence_limit_enforced" in changes, "sentence-limit normalization was not recorded", failures)
    require(
        "Vault is offline intentionally" not in service_source,
        "live chat still describes retired storage as temporarily offline",
        failures,
    )

    result = {
        "schema": "ENGEL_LOCAL_LLM_FAST_FAIL_VERIFIER_V1",
        "ok": not failures,
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "provider_calls_made": False,
        "storage_mutation": False,
        "external_array_used": False,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
