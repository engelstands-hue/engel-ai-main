#!/usr/bin/env python3
"""Build Engel's owner-feedback preference dataset without changing weights.

An active rejected chat sample is useful for DPO/RLHF only when Engel also has
a successful answer to the exact same prompt.  This builder joins those two
ledgers, rejects secret-looking or malformed text, writes deterministic
train/validation JSONL files, and records hashes.  It never calls a provider,
starts a trainer, promotes a model, or writes trusted memory.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Iterable


DEFAULT_ROOT = Path(os.environ.get("ENGEL_APP_ROOT", "/opt/engel"))
PAIR_SCHEMA = "ENGEL_OWNER_PREFERENCE_PAIR_V1"
MANIFEST_SCHEMA = "ENGEL_PREFERENCE_DATASET_MANIFEST_V1"
APPROVAL_PHRASE = "APPROVE_ENGEL_LOCAL_ALIGNMENT_TRAINING_RUN_V1"
SECRET_PATTERNS = tuple(
    re.compile(pattern)
    for pattern in (
        r"sk-[A-Za-z0-9_-]{18,}",
        r"ghp_[A-Za-z0-9]{20,}",
        r"AIza[0-9A-Za-z_-]{30,}",
        r"xox[bap]-[A-Za-z0-9-]+",
        r"BEGIN [A-Z ]*PRIVATE KEY",
    )
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _normalize_prompt(value: Any) -> str:
    return " ".join(str(value or "").split()).casefold()


def _iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            item = json.loads(line)
        except Exception:
            continue
        if isinstance(item, dict):
            yield item


def _safe_pair(prompt: str, chosen: str, rejected: str) -> bool:
    if len(prompt) < 8 or len(chosen) < 80 or len(rejected) < 40:
        return False
    if chosen.strip() == rejected.strip():
        return False
    blob = "\n".join((prompt, chosen, rejected))
    return not any(pattern.search(blob) for pattern in SECRET_PATTERNS)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def _active_rejections(path: Path) -> list[dict[str, Any]]:
    state: dict[str, dict[str, Any]] = {}
    for item in _iter_jsonl(path):
        key = str(item.get("sample_key") or "").strip()
        if not key:
            key = hashlib.sha256(
                (
                    _normalize_prompt(item.get("prompt"))
                    + "\n"
                    + str(item.get("assistant_reply") or "").strip()
                ).encode("utf-8")
            ).hexdigest()
        if item.get("active") is False:
            state.pop(key, None)
        else:
            state[key] = item
    return list(state.values())


def build_dataset(root: Path = DEFAULT_ROOT, output_dir: Path | None = None) -> dict[str, Any]:
    root = Path(root).resolve()
    output_dir = Path(output_dir or root / "llm_training" / "datasets" / "preference" / "latest").resolve()
    memory_path = root / "memory" / "persistent_chat" / "ENGEL_AI_MAIN_LLM_CHAT_MEMORY.jsonl"
    rejected_path = root / "memory" / "persistent_chat" / "ENGEL_CHAT_REJECTED_SAMPLES.jsonl"

    accepted: dict[str, list[dict[str, Any]]] = {}
    for item in _iter_jsonl(memory_path):
        if item.get("ok") is not True or item.get("quality_gate_degraded") is True:
            continue
        status = str(item.get("status") or "").casefold()
        if "quality check failed" in status or "style check failed" in status:
            continue
        prompt = " ".join(str(item.get("prompt") or "").split())
        reply = str(item.get("assistant_reply") or item.get("assistant_output_text") or "").strip()
        normalized = _normalize_prompt(prompt)
        if len(normalized) < 8 or len(reply) < 80:
            continue
        accepted.setdefault(normalized, []).append(
            {
                "prompt": prompt,
                "reply": reply,
                "at": str(item.get("updated_at_utc") or item.get("completed_at_utc") or ""),
                "receipt": str(item.get("receipt_path") or ""),
                "provider": str(item.get("selected_provider") or item.get("runtime_provider") or "local"),
            }
        )

    pairs_by_prompt: dict[str, dict[str, Any]] = {}
    active = _active_rejections(rejected_path)
    for rejected_item in active:
        prompt = " ".join(str(rejected_item.get("prompt") or "").split())
        normalized = _normalize_prompt(prompt)
        rejected = str(rejected_item.get("assistant_reply") or "").strip()
        candidates = [
            item
            for item in accepted.get(normalized, [])
            if str(item.get("reply") or "").strip() != rejected
        ]
        if not candidates:
            continue
        chosen_item = max(candidates, key=lambda item: (str(item.get("at") or ""), len(str(item.get("reply") or ""))))
        chosen = str(chosen_item.get("reply") or "").strip()
        if not _safe_pair(prompt, chosen, rejected):
            continue
        pair_id = hashlib.sha256((normalized + "\n" + chosen + "\n" + rejected).encode("utf-8")).hexdigest()
        pairs_by_prompt[normalized] = {
            "schema": PAIR_SCHEMA,
            "pair_id": pair_id,
            "prompt": prompt,
            "chosen": chosen,
            "rejected": rejected,
            "owner_feedback": True,
            "training_candidate": True,
            "chosen_provider": chosen_item.get("provider"),
            "chosen_receipt_path": chosen_item.get("receipt"),
            "rejected_receipt_path": str(rejected_item.get("receipt_path") or ""),
            "rejection_reason": str(rejected_item.get("reason") or "owner rejection")[:300],
            "provider_called": False,
            "trusted_memory_write": False,
        }

    pairs = sorted(pairs_by_prompt.values(), key=lambda item: str(item["pair_id"]))
    if not pairs:
        raise RuntimeError("no exact-prompt chosen/rejected preference pairs were available")
    validation = [item for item in pairs if int(str(item["pair_id"])[:8], 16) % 10 == 0]
    training = [item for item in pairs if item not in validation]
    if not validation and len(training) > 1:
        validation = [training.pop()]

    train_path = output_dir / "preference_train.jsonl"
    val_path = output_dir / "preference_val.jsonl"
    _write_text_atomic(train_path, "".join(json.dumps(item, sort_keys=True) + "\n" for item in training))
    _write_text_atomic(val_path, "".join(json.dumps(item, sort_keys=True) + "\n" for item in validation))
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "ok": True,
        "built_at_utc": _now(),
        "pair_schema": PAIR_SCHEMA,
        "active_rejected_samples": len(active),
        "matched_pair_count": len(pairs),
        "train_pair_count": len(training),
        "validation_pair_count": len(validation),
        "train_path": str(train_path),
        "validation_path": str(val_path),
        "train_sha256": _sha256(train_path),
        "validation_sha256": _sha256(val_path),
        "join_rule": "exact normalized prompt with an owner-rejected and a later successful answer",
        "alignment_method": "DPO-compatible owner preference pairs",
        "approval_required_for_weight_training": APPROVAL_PHRASE,
        "weight_training_started": False,
        "model_promoted": False,
        "provider_called": False,
        "trusted_memory_write": False,
    }
    manifest_path = output_dir / "dataset_manifest.json"
    _write_text_atomic(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    receipt_path = root / "reports" / "llm_training" / "ENGEL_PREFERENCE_DATASET_LATEST.json"
    _write_text_atomic(receipt_path, json.dumps({**manifest, "manifest_path": str(manifest_path)}, indent=2, sort_keys=True) + "\n")
    return {**manifest, "manifest_path": str(manifest_path), "receipt_path": str(receipt_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Engel owner-feedback preference pairs.")
    parser.add_argument("--root", default=str(DEFAULT_ROOT))
    parser.add_argument("--output-dir", default="")
    args = parser.parse_args()
    try:
        payload = build_dataset(Path(args.root), Path(args.output_dir) if args.output_dir else None)
    except Exception as exc:
        payload = {
            "schema": MANIFEST_SCHEMA,
            "ok": False,
            "status": "preference dataset build failed",
            "error": str(exc)[:500],
            "weight_training_started": False,
            "provider_called": False,
            "trusted_memory_write": False,
        }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
