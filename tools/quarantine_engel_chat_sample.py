#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import engel_main_server_chat_http_service as service  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Append matching Engel chat pairs to the rejected-sample registry."
    )
    parser.add_argument("--prompt-sha256", required=True)
    parser.add_argument("--provider", default="")
    parser.add_argument("--reason", default="")
    parser.add_argument("--source", default="engel-ai-main verified manual quality quarantine")
    parser.add_argument(
        "--restore-currently-safe",
        action="store_true",
        help="append active=false records for matching samples that pass the current semantic gate",
    )
    parser.add_argument(
        "--only-currently-failing",
        action="store_true",
        help="quarantine only matching replies that fail the current semantic quality gate",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    target_hash = str(args.prompt_sha256 or "").strip().casefold()
    if len(target_hash) != 64 or any(ch not in "0123456789abcdef" for ch in target_hash):
        raise SystemExit("--prompt-sha256 must be a 64-character hexadecimal SHA-256 value")
    provider_filter = str(args.provider or "").strip().casefold()
    if not args.restore_currently_safe and not str(args.reason or "").strip():
        raise SystemExit("--reason is required when quarantining samples")

    if args.restore_currently_safe:
        active: dict[str, dict[str, Any]] = {}
        rejected_path = service.REJECTED_CHAT_SAMPLES_PATH
        if not rejected_path.is_file():
            raise SystemExit(f"rejected-sample registry is missing: {rejected_path}")
        for line in rejected_path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            sample_key = str(row.get("sample_key") or "")
            if not sample_key:
                continue
            if row.get("active") is False:
                active.pop(sample_key, None)
            else:
                active[sample_key] = row
        restored: list[dict[str, Any]] = []
        for sample_key, row in active.items():
            if str(row.get("prompt_sha256") or "").casefold() != target_hash:
                continue
            source_text = str(row.get("source") or "").casefold()
            if provider_filter and provider_filter not in source_text:
                continue
            prompt = str(row.get("prompt") or "")
            reply = str(row.get("assistant_reply") or "")
            quality = service._incomplete_input_quality_report(prompt, reply)
            if quality.get("ok") is not True:
                continue
            deactivation = {
                "schema": "engel_chat_rejected_sample_v1",
                "active": False,
                "rejected_at_utc": service._iso_now(),
                "sample_key": sample_key,
                "prompt_sha256": target_hash,
                "assistant_reply_sha256": str(row.get("assistant_reply_sha256") or ""),
                "reason": str(args.reason or "sample passes the current repaired semantic quality gate"),
                "source": str(args.source or "engel-ai-main verified quality restoration"),
            }
            service._append_jsonl(rejected_path, deactivation)
            restored.append(
                {
                    "sample_key": sample_key,
                    "assistant_reply_sha256": deactivation["assistant_reply_sha256"],
                    "restored": True,
                }
            )
        receipt = {
            "schema": "engel_chat_sample_quality_restoration_v1",
            "ok": bool(restored),
            "prompt_sha256": target_hash,
            "provider_filter": provider_filter,
            "restored_sample_count": len(restored),
            "results": restored,
            "memory_rewritten": False,
            "rejection_registry": str(rejected_path),
        }
        print(json.dumps(receipt, ensure_ascii=False, indent=2))
        return 0 if receipt["ok"] else 1

    memory_path = service.PERSISTENT_CHAT_MEMORY_PATH
    if not memory_path.is_file():
        raise SystemExit(f"persistent chat memory is missing: {memory_path}")

    matches: dict[str, dict[str, Any]] = {}
    for line in memory_path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        prompt = str(row.get("prompt") or "")
        prompt_hash = str(row.get("prompt_sha256") or "").casefold()
        if not prompt_hash and prompt:
            prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        if prompt_hash != target_hash:
            continue
        provider_text = " ".join(
            str(row.get(key) or "")
            for key in ("selected_provider", "provider", "runtime_provider")
        ).casefold()
        if provider_filter and provider_filter not in provider_text:
            continue
        reply = str(row.get("assistant_reply") or row.get("assistant_output_text") or "").strip()
        if not prompt or not reply:
            continue
        if args.only_currently_failing:
            quality = service._incomplete_input_quality_report(prompt, reply)
            if quality.get("ok") is True:
                continue
        matches[service._chat_sample_key(prompt, reply)] = row

    results: list[dict[str, Any]] = []
    for sample_key, row in matches.items():
        prompt = str(row.get("prompt") or "")
        reply = str(row.get("assistant_reply") or row.get("assistant_output_text") or "")
        rejection = service._append_chat_sample_rejection(
            prompt,
            reply,
            row,
            args.reason,
            source=args.source,
        )
        results.append(
            {
                "sample_key": sample_key,
                "assistant_reply_sha256": hashlib.sha256(reply.encode("utf-8")).hexdigest(),
                "quarantined": rejection.get("ok") is True,
            }
        )

    receipt = {
        "schema": "engel_chat_sample_quarantine_command_v1",
        "ok": bool(results) and all(row.get("quarantined") is True for row in results),
        "prompt_sha256": target_hash,
        "provider_filter": provider_filter,
        "matched_unique_samples": len(results),
        "results": results,
        "memory_rewritten": False,
        "rejection_registry": str(service.REJECTED_CHAT_SAMPLES_PATH),
    }
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0 if receipt["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
