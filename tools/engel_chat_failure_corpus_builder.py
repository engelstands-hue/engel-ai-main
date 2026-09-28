#!/usr/bin/env python3
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import threading
from typing import Any


ROOT = Path(os.environ.get("ENGEL_ROOT") or Path(__file__).resolve().parents[1])
DEFAULT_CORPUS_PATH = ROOT / "run" / "self_update" / "training" / "chat_failures.jsonl"

_LOCK = threading.RLock()
_MAX_TEXT_CHARS = 12_000
_SECRET_FIELD_NAMES = {
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "credential",
    "credentials",
    "password",
    "private_key",
    "secret",
    "session_token",
    "token",
}
_TEXT_REDACTIONS = (
    re.compile(r"<think\b[^>]*>.*?</think\s*>", re.IGNORECASE | re.DOTALL),
    re.compile(
        r"(?im)^\s*(?:thinking process|chain of thought|internal reasoning)\s*:\s*.*(?:\n(?:[ \t].*|[-*]\s.*))*"
    ),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}"),
    re.compile(r"\b(?:sk|xai)-[A-Za-z0-9_-]{8,}\b", re.IGNORECASE),
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
    re.compile(r"\b(?:ghp|github_pat)_[A-Za-z0-9_]{12,}\b", re.IGNORECASE),
    re.compile(
        r"(?i)\b(api[_ -]?key|token|password|secret|authorization|cookie|credential)s?\b"
        r"\s*[:=]\s*(?:['\"])?[^\s,'\";}]{4,}(?:['\"])?"
    ),
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _clip(value: Any, limit: int = 500) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def redact_text(value: Any, *, limit: int = _MAX_TEXT_CHARS) -> tuple[str, int]:
    text = str(value or "")
    redactions = 0
    for pattern in _TEXT_REDACTIONS:
        text, count = pattern.subn("[REDACTED]", text)
        redactions += count
    if len(text) > limit:
        text = text[: max(0, limit - 15)].rstrip() + "...[TRUNCATED]"
    return text, redactions


def redact_value(value: Any) -> tuple[Any, int]:
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        redactions = 0
        for raw_key, item in value.items():
            key = str(raw_key)
            normalized = re.sub(r"[^a-z0-9]+", "_", key.casefold()).strip("_")
            if normalized in _SECRET_FIELD_NAMES or any(
                marker in normalized for marker in ("password", "private_key", "session_token", "api_key")
            ):
                output[key] = "[REDACTED]"
                redactions += 1
                continue
            output[key], count = redact_value(item)
            redactions += count
        return output, redactions
    if isinstance(value, list):
        output_list: list[Any] = []
        redactions = 0
        for item in value:
            cleaned, count = redact_value(item)
            output_list.append(cleaned)
            redactions += count
        return output_list, redactions
    if isinstance(value, tuple):
        return redact_value(list(value))
    if isinstance(value, str):
        return redact_text(value)
    return value, 0


def _style_scores(receipt: dict[str, Any]) -> list[dict[str, Any]]:
    scores: list[dict[str, Any]] = []
    for key in ("first_style_score", "style_score", "quality_score"):
        value = receipt.get(key)
        if isinstance(value, dict):
            scores.append(value)
    return scores


def _provider_family(value: Any) -> str:
    text = str(value or "").strip().casefold().replace("_", "-")
    if not text or text in {"auto", "engel", "default"}:
        return "auto"
    if any(term in text for term in ("local", "llama", "gguf", "qwen", "mistral", "ornith", "ct-mode")):
        return "local"
    if any(term in text for term in ("openai", "chatgpt", "gpt-")):
        return "openai"
    if any(term in text for term in ("anthropic", "claude")):
        return "anthropic"
    if any(term in text for term in ("xai", "grok")):
        return "xai"
    if "gemini" in text or "google" in text:
        return "gemini"
    if "codex" in text:
        return "codex"
    return text


def classify_failure(
    receipt: dict[str, Any] | None,
    attachment_intake: dict[str, Any] | None = None,
    request: dict[str, Any] | None = None,
) -> list[str]:
    receipt = receipt if isinstance(receipt, dict) else {}
    attachment_intake = attachment_intake if isinstance(attachment_intake, dict) else {}
    request = request if isinstance(request, dict) else {}
    failures: set[str] = set()
    status = str(receipt.get("status") or receipt.get("error") or "").casefold()
    fast_fail = receipt.get("local_llm_fast_fail")
    if not isinstance(fast_fail, dict):
        fast_fail = {}

    if (
        fast_fail.get("timed_out") is True
        or str(fast_fail.get("failure_kind") or "").casefold() == "timeout"
        or (receipt.get("ok") is False and "timeout" in status)
    ):
        failures.add("timeout")

    if receipt.get("repeat_guard_triggered") is True or "repeat guard" in status:
        failures.add("repeat")

    scores = _style_scores(receipt)
    generic_hits = any(bool(score.get("generic_bootstrap_hits")) for score in scores)
    if (
        generic_hits
        or receipt.get("fallback_guard_triggered") is True
        or receipt.get("fast_server_fallback_used") is True
        or "generic bootstrap" in status
    ):
        failures.add("generic_reply")

    identity_failed = False
    for score in scores:
        checks = score.get("checks") if isinstance(score.get("checks"), dict) else {}
        identity_failed = identity_failed or bool(score.get("banned_hits"))
        identity_failed = identity_failed or checks.get("no_wrong_identity") is False
        identity_failed = identity_failed or checks.get("does_not_address_joshua_as_engel") is False
    if (
        identity_failed
        or receipt.get("identity_mixup") is True
        or receipt.get("chat_safety_operator_address_repaired") is True
    ):
        failures.add("identity_mixup")

    requested_raw = (
        request.get("provider")
        or receipt.get("requested_provider_arg")
        or receipt.get("requested_provider")
        or ""
    )
    selected_raw = receipt.get("selected_provider") or receipt.get("provider") or ""
    requested_family = _provider_family(requested_raw)
    selected_family = _provider_family(selected_raw)
    documented_fallback = any(
        receipt.get(key) is True
        for key in (
            "provider_fallback_allowed",
            "provider_fallback_used",
            "explicit_provider_fallback_used",
            "local_fallback_used",
        )
    )
    if receipt.get("route_mismatch") is True or (
        requested_family not in {"", "auto"}
        and selected_family not in {"", requested_family}
        and not documented_fallback
    ):
        failures.add("route_mismatch")

    attachment_errors = attachment_intake.get("errors")
    if not isinstance(attachment_errors, list):
        attachment_errors = receipt.get("chat_attachment_errors")
    attachment_errors = attachment_errors if isinstance(attachment_errors, list) else []
    requested_count = int(
        attachment_intake.get("requested_count")
        or receipt.get("chat_attachment_requested_count")
        or 0
    )
    accepted_count = int(
        attachment_intake.get("count")
        or receipt.get("chat_attachment_count")
        or 0
    )
    if attachment_errors or requested_count > accepted_count:
        failures.add("attachment_miss")

    if receipt.get("ok") is False and not failures:
        failures.add("chat_error")
    return sorted(failures)


def _source_receipt_path(receipt: dict[str, Any]) -> str:
    return str(
        receipt.get("workspace_receipt_path")
        or receipt.get("local_chat_receipt_path")
        or receipt.get("receipt_path")
        or ""
    ).strip()


def _safe_receipt_hash(path_text: str, root: Path) -> str:
    if not path_text:
        return ""
    try:
        path = Path(path_text).resolve()
        allowed_root = root.resolve()
        if not path.is_relative_to(allowed_root) or not path.is_file():
            return ""
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except Exception:
        return ""


def _existing_event_ids(path: Path, *, tail_bytes: int = 1_000_000) -> set[str]:
    if not path.is_file():
        return set()
    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - tail_bytes))
            text = handle.read().decode("utf-8", errors="replace")
    except OSError:
        return set()
    ids: set[str] = set()
    for line in text.splitlines():
        try:
            item = json.loads(line)
        except Exception:
            continue
        if isinstance(item, dict) and item.get("event_id"):
            ids.add(str(item["event_id"]))
    return ids


def capture_failure(
    *,
    prompt: str,
    reply: str,
    receipt: dict[str, Any] | None,
    attachment_intake: dict[str, Any] | None = None,
    request: dict[str, Any] | None = None,
    source: str = "engel-ai-main-chat",
    corpus_path: str | Path | None = None,
    root: str | Path | None = None,
) -> dict[str, Any]:
    receipt = receipt if isinstance(receipt, dict) else {}
    attachment_intake = attachment_intake if isinstance(attachment_intake, dict) else {}
    request = request if isinstance(request, dict) else {}
    failures = classify_failure(receipt, attachment_intake, request)
    path = Path(corpus_path or os.environ.get("ENGEL_CHAT_FAILURE_CORPUS_PATH") or DEFAULT_CORPUS_PATH)
    if not failures:
        return {
            "schema": "ENGEL_CHAT_FAILURE_CORPUS_CAPTURE_V1",
            "ok": True,
            "captured": False,
            "status": "chat turn did not match a failure class",
            "failure_types": [],
            "corpus_path": str(path),
            "trusted_memory_write": False,
        }

    failed_reply = str(
        receipt.get("repeat_guard_original_reply")
        or receipt.get("raw_first_reply")
        or receipt.get("raw_model_reply")
        or reply
        or ""
    )
    prompt_text = str(prompt or "")
    visible_reply = str(reply or receipt.get("assistant_reply") or receipt.get("assistant_output_text") or "")
    prompt_redacted, prompt_redactions = redact_text(prompt_text)
    failed_redacted, failed_redactions = redact_text(failed_reply)
    visible_redacted, visible_redactions = redact_text(visible_reply)
    errors_value, error_redactions = redact_value(
        attachment_intake.get("errors") or receipt.get("chat_attachment_errors") or []
    )
    source_path = _source_receipt_path(receipt)
    prompt_hash = _sha256_text(prompt_text)
    failed_hash = _sha256_text(failed_reply)
    identity = "|".join(
        [
            source_path,
            str(receipt.get("run_id") or receipt.get("request_id") or receipt.get("updated_at_utc") or ""),
            prompt_hash,
            failed_hash,
            ",".join(failures),
            _sha256_text(json.dumps(errors_value, ensure_ascii=False, sort_keys=True)),
        ]
    )
    event_id = "chat_failure_" + _sha256_text(identity)[:20]
    provider_called = any(
        receipt.get(key) is True
        for key in ("provider_called", "provider_bridge_used", "provider_completion_proven")
    )
    root_path = Path(root or ROOT)
    record = {
        "schema": "ENGEL_CHAT_FAILURE_CORPUS_EVENT_V1",
        "event_id": event_id,
        "captured_at_utc": _now_iso(),
        "source": _clip(source, 160),
        "failure_types": failures,
        "primary_failure": failures[0],
        "eval_candidate": True,
        "training_candidate": False,
        "trusted_memory_write": False,
        "approved_memory_write": False,
        "provider_called": provider_called,
        "prompt_sha256": prompt_hash,
        "failed_reply_sha256": failed_hash,
        "prompt_redacted": prompt_redacted,
        "failed_reply_redacted": failed_redacted,
        "visible_reply_redacted": visible_redacted,
        "redaction_count": prompt_redactions + failed_redactions + visible_redactions + error_redactions,
        "route": {
            "requested_provider": _clip(request.get("provider") or receipt.get("requested_provider_arg") or receipt.get("requested_provider"), 120),
            "selected_provider": _clip(receipt.get("selected_provider") or receipt.get("provider"), 120),
            "runtime_provider": _clip(receipt.get("runtime_provider"), 160),
            "model": _clip(receipt.get("model"), 300),
        },
        "outcome": {
            "ok": receipt.get("ok") is True,
            "status": _clip(receipt.get("status") or receipt.get("error"), 500),
            "repeat_guard_triggered": receipt.get("repeat_guard_triggered") is True,
            "fallback_guard_triggered": receipt.get("fallback_guard_triggered") is True,
            "fast_server_fallback_used": receipt.get("fast_server_fallback_used") is True,
        },
        "attachments": {
            "requested_count": int(attachment_intake.get("requested_count") or receipt.get("chat_attachment_requested_count") or 0),
            "accepted_count": int(attachment_intake.get("count") or receipt.get("chat_attachment_count") or 0),
            "stored_count": int(attachment_intake.get("stored_count") or receipt.get("chat_attachment_stored_count") or 0),
            "errors": errors_value,
        },
        "source_receipt_path": source_path,
        "source_receipt_sha256_at_capture": _safe_receipt_hash(source_path, root_path),
        "active_runtime_root": str(root_path),
        "storage_mutation": False,
        "external_array_used": False,
    }

    with _LOCK:
        if event_id in _existing_event_ids(path):
            return {
                "schema": "ENGEL_CHAT_FAILURE_CORPUS_CAPTURE_V1",
                "ok": True,
                "captured": False,
                "deduplicated": True,
                "status": "failure event already present",
                "event_id": event_id,
                "failure_types": failures,
                "corpus_path": str(path),
                "trusted_memory_write": False,
            }
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return {
        "schema": "ENGEL_CHAT_FAILURE_CORPUS_CAPTURE_V1",
        "ok": True,
        "captured": True,
        "deduplicated": False,
        "status": "chat failure added as an untrusted eval candidate",
        "event_id": event_id,
        "failure_types": failures,
        "redaction_count": record["redaction_count"],
        "corpus_path": str(path),
        "trusted_memory_write": False,
        "training_candidate": False,
    }


def status_snapshot(corpus_path: str | Path | None = None) -> dict[str, Any]:
    path = Path(corpus_path or os.environ.get("ENGEL_CHAT_FAILURE_CORPUS_PATH") or DEFAULT_CORPUS_PATH)
    counts: Counter[str] = Counter()
    total = 0
    malformed = 0
    newest = ""
    if path.is_file():
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            lines = []
        for line in lines:
            try:
                item = json.loads(line)
            except Exception:
                malformed += 1
                continue
            if not isinstance(item, dict):
                malformed += 1
                continue
            total += 1
            for kind in item.get("failure_types") or []:
                counts[str(kind)] += 1
            newest = max(newest, str(item.get("captured_at_utc") or ""))
    return {
        "schema": "ENGEL_CHAT_FAILURE_CORPUS_STATUS_V1",
        "ok": malformed == 0,
        "status": "chat failure corpus ready" if malformed == 0 else "chat failure corpus contains malformed rows",
        "corpus_path": str(path),
        "exists": path.is_file(),
        "event_count": total,
        "counts_by_failure_type": dict(sorted(counts.items())),
        "malformed_row_count": malformed,
        "newest_event_at_utc": newest,
        "eval_candidates_only": True,
        "training_candidate_default": False,
        "trusted_memory_write": False,
        "active_runtime_root": str(ROOT),
        "external_array_used": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect Engel's redacted chat failure corpus.")
    parser.add_argument("command", nargs="?", choices=("status",), default="status")
    parser.add_argument("--corpus-path", default="")
    args = parser.parse_args()
    result = status_snapshot(args.corpus_path or None)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
