#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import tempfile

from engel_chat_failure_corpus_builder import capture_failure, classify_failure, status_snapshot
import engel_main_server_chat_http_service as chat_service


ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def main() -> int:
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="engel-chat-failures-") as temp:
        corpus_path = Path(temp) / "run" / "self_update" / "training" / "chat_failures.jsonl"
        fixtures = [
            (
                "timeout",
                {"ok": False, "status": "local LLM timeout", "local_llm_fast_fail": {"timed_out": True}},
                {},
                {},
            ),
            (
                "repeat",
                {"ok": True, "status": "reply replaced by repeat guard", "repeat_guard_triggered": True, "repeat_guard_original_reply": "Same answer again."},
                {},
                {},
            ),
            (
                "generic_reply",
                {"ok": True, "status": "fallback reply", "fallback_guard_triggered": True, "first_style_score": {"generic_bootstrap_hits": ["ready to help"]}, "raw_first_reply": "I am ready to help."},
                {},
                {},
            ),
            (
                "route_mismatch",
                {"ok": True, "status": "local replied", "selected_provider": "local_rog_gpu"},
                {},
                {"provider": "claude"},
            ),
            (
                "identity_mixup",
                {"ok": False, "status": "style failed", "style_score": {"banned_hits": ["I am Claude"], "checks": {"no_wrong_identity": False}}},
                {},
                {},
            ),
            (
                "attachment_miss",
                {"ok": True, "status": "local replied"},
                {"requested_count": 1, "count": 0, "stored_count": 0, "errors": [{"error": "bad base64", "token": "secret-value"}]},
                {},
            ),
        ]
        for index, (kind, receipt, attachments, request) in enumerate(fixtures):
            receipt = dict(receipt)
            receipt["run_id"] = f"fixture-{index}"
            prompt = f"fixture {kind}; api_key=sk-supersecret123456"
            reply = "<think>private hidden reasoning</think> visible answer"
            result = capture_failure(
                prompt=prompt,
                reply=reply,
                receipt=receipt,
                attachment_intake=attachments,
                request=request,
                source="verifier",
                corpus_path=corpus_path,
                root=temp,
            )
            require(result.get("captured") is True, f"{kind} fixture was not captured", failures)
            require(kind in (result.get("failure_types") or []), f"{kind} was not classified", failures)
            require(result.get("trusted_memory_write") is False, f"{kind} claimed trusted-memory write", failures)

        valid = capture_failure(
            prompt="normal prompt",
            reply="normal answer",
            receipt={"ok": True, "status": "local replied", "selected_provider": "local"},
            corpus_path=corpus_path,
            root=temp,
        )
        require(valid.get("captured") is False, "valid chat was added to the failure corpus", failures)

        duplicate_receipt = {
            "ok": False,
            "status": "local LLM timeout",
            "local_llm_fast_fail": {"timed_out": True},
            "run_id": "fixture-0",
        }
        duplicate = capture_failure(
            prompt="fixture timeout; api_key=sk-supersecret123456",
            reply="<think>private hidden reasoning</think> visible answer",
            receipt=duplicate_receipt,
            corpus_path=corpus_path,
            root=temp,
        )
        require(duplicate.get("deduplicated") is True, "identical failure was appended twice", failures)

        rows = []
        if corpus_path.is_file():
            rows = [json.loads(line) for line in corpus_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        require(len(rows) == 6, f"expected 6 corpus rows, found {len(rows)}", failures)
        serialized = json.dumps(rows, ensure_ascii=False)
        for forbidden in ("sk-supersecret", "secret-value", "private hidden reasoning", "<think>"):
            require(forbidden not in serialized, f"corpus leaked forbidden text: {forbidden}", failures)
        require(all(row.get("eval_candidate") is True for row in rows), "an event is not an eval candidate", failures)
        require(all(row.get("training_candidate") is False for row in rows), "an event was auto-promoted to training", failures)
        require(all(row.get("trusted_memory_write") is False for row in rows), "an event claimed trusted-memory write", failures)
        require(all(row.get("external_array_used") is False for row in rows), "an event used an external array", failures)

        status = status_snapshot(corpus_path)
        require(status.get("ok") is True, "corpus status is not healthy", failures)
        require(status.get("event_count") == 6, "status event count is wrong", failures)
        for kind, *_ in fixtures:
            require(status.get("counts_by_failure_type", {}).get(kind, 0) >= 1, f"status omitted {kind}", failures)

        intake = chat_service._prepare_chat_attachments(
            [{"name": "broken.txt", "inline_base64": "not-valid-base64"}]
        )
        attached = chat_service._attach_intake_to_receipt({"ok": True}, intake)
        require(intake.get("requested_count") == 1, "attachment requested count is missing", failures)
        require(bool(attached.get("chat_attachment_errors")), "attachment errors did not reach the receipt", failures)
        require(
            "contents are unavailable because upload processing failed" in str(intake.get("prompt_context") or ""),
            "attachment decode failure did not reach safe model context",
            failures,
        )
        require(
            "0 bytes" not in str(intake.get("prompt_context") or ""),
            "failed attachment context still described the upload as an empty file",
            failures,
        )
        require(
            "attachment_miss" in classify_failure(attached, intake, {}),
            "invalid attachment did not classify as attachment_miss",
            failures,
        )
        require(
            "identity_mixup"
            in classify_failure(
                {"ok": True, "chat_safety_operator_address_repaired": True},
                {},
                {},
            ),
            "repaired operator-address drift did not classify as identity_mixup",
            failures,
        )

    service_source = (ROOT / "tools" / "engel_main_server_chat_http_service.py").read_text(encoding="utf-8")
    require("capture_chat_failure(" in service_source, "chat service does not call the corpus builder", failures)
    require("/chat-failures/status" in service_source, "chat failure status endpoint is missing", failures)
    require("chat-failure-corpus" in service_source, "runtime registry capability is missing", failures)

    result = {
        "schema": "ENGEL_CHAT_FAILURE_CORPUS_BUILDER_VERIFIER_V1",
        "ok": not failures,
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "failure_classes_verified": [
            "timeout",
            "repeat",
            "generic_reply",
            "route_mismatch",
            "identity_mixup",
            "attachment_miss",
        ],
        "trusted_memory_write": False,
        "provider_calls_made": False,
        "storage_mutation": False,
        "external_array_used": False,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
