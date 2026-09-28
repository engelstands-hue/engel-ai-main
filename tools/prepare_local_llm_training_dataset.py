from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "local_llm_training"
SOURCE_DATASET = DATA_DIR / "engel_customer_conversation_seed_v1.jsonl"
PREPARED_DIR = DATA_DIR / "prepared"
PREPARED_DATASET = PREPARED_DIR / "engel_customer_sft_candidate_v1.jsonl"
PREPARED_MANIFEST = PREPARED_DIR / "engel_customer_sft_candidate_v1_manifest.json"

REQUIRED_FIELDS = {
    "instruction",
    "input",
    "output",
    "tags",
    "source_category",
    "trust_status",
    "requires_human_review",
    "safe_for_training_candidate",
    "must_not_teach",
    "notes",
}

SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*[A-Za-z0-9_\-]{16,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9_\-\.]{20,}"),
    re.compile(r"(?i)-----BEGIN\s+(RSA|OPENSSH|PRIVATE)\s+KEY-----"),
]

FORBIDDEN_OUTPUT_PHRASES = [
    "as an ai language model",
    "certainly, i can assist",
]


class DatasetPrepError(Exception):
    pass


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise DatasetPrepError(f"Missing source dataset: {path}")
    records: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            value = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise DatasetPrepError(f"Invalid JSON on line {line_no}: {exc}") from exc
        if not isinstance(value, dict):
            raise DatasetPrepError(f"Line {line_no} is not a JSON object")
        records.append(value)
    return records


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\ufeff", " ")).strip()


def _validate_record(record: dict[str, Any], index: int) -> dict[str, Any]:
    missing = sorted(REQUIRED_FIELDS - set(record))
    if missing:
        raise DatasetPrepError(f"Record {index} missing fields: {', '.join(missing)}")

    normalized: dict[str, Any] = {}
    for field in ["instruction", "input", "output", "source_category", "trust_status", "notes"]:
        value = record.get(field)
        if not isinstance(value, str) or not value.strip():
            raise DatasetPrepError(f"Record {index} field {field!r} must be a non-empty string")
        normalized[field] = _normalize_text(value)

    tags = record.get("tags")
    if not isinstance(tags, list) or not all(isinstance(tag, str) and tag.strip() for tag in tags):
        raise DatasetPrepError(f"Record {index} tags must be a non-empty string list")
    normalized["tags"] = sorted(dict.fromkeys(_normalize_text(tag) for tag in tags))
    if "customer_ready" not in normalized["tags"] or "engel_style" not in normalized["tags"]:
        raise DatasetPrepError(f"Record {index} must include customer_ready and engel_style tags")

    if record.get("trust_status") != "candidate_training_example":
        raise DatasetPrepError(f"Record {index} trust_status must be candidate_training_example")
    if record.get("requires_human_review") is not True:
        raise DatasetPrepError(f"Record {index} requires_human_review must be true")
    if record.get("safe_for_training_candidate") is not True:
        raise DatasetPrepError(f"Record {index} safe_for_training_candidate must be true")

    must_not_teach = record.get("must_not_teach")
    if not isinstance(must_not_teach, list) or not all(isinstance(item, str) for item in must_not_teach):
        raise DatasetPrepError(f"Record {index} must_not_teach must be a string list")
    normalized["must_not_teach"] = [_normalize_text(item) for item in must_not_teach]
    normalized["requires_human_review"] = True
    normalized["safe_for_training_candidate"] = True

    combined = "\n".join(str(normalized.get(field, "")) for field in ["instruction", "input", "output", "notes"])
    for pattern in SECRET_PATTERNS:
        if pattern.search(combined):
            raise DatasetPrepError(f"Record {index} appears to contain a secret-like value")
    output_lower = normalized["output"].lower()
    for phrase in FORBIDDEN_OUTPUT_PHRASES:
        if phrase in output_lower:
            raise DatasetPrepError(f"Record {index} output contains forbidden robotic phrase: {phrase}")

    return normalized


def prepare_dataset() -> dict[str, Any]:
    records = _read_jsonl(SOURCE_DATASET)
    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    duplicate_count = 0

    for index, record in enumerate(records, start=1):
        item = _validate_record(record, index)
        key = (item["instruction"], item["input"], item["output"])
        if key in seen:
            duplicate_count += 1
            continue
        seen.add(key)
        normalized.append(item)

    PREPARED_DIR.mkdir(parents=True, exist_ok=True)
    with PREPARED_DATASET.open("w", encoding="utf-8", newline="\n") as handle:
        for item in normalized:
            handle.write(json.dumps(item, ensure_ascii=True, sort_keys=True) + "\n")

    manifest = {
        "manifest_id": "ENGEL_CUSTOMER_SFT_CANDIDATE_V1_MANIFEST",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": "prepare_local_llm_training_dataset.py",
        "source_dataset": str(SOURCE_DATASET.relative_to(ROOT)),
        "prepared_dataset": str(PREPARED_DATASET.relative_to(ROOT)),
        "record_count": len(normalized),
        "duplicates_removed": duplicate_count,
        "status": "candidate_training_dataset_only",
        "training_enabled": False,
        "model_weight_update_enabled": False,
        "provider_calls_enabled": False,
        "network_enabled": False,
        "trusted_memory_write_enabled": False,
        "human_review_required": True,
    }
    PREPARED_MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    try:
        manifest = prepare_dataset()
    except DatasetPrepError as exc:
        print("[FAIL]", exc)
        return 1
    print("[PASS] Prepared local LLM candidate SFT dataset")
    print("records:", manifest["record_count"])
    print("prepared_dataset:", manifest["prepared_dataset"])
    print("manifest:", str(PREPARED_MANIFEST.relative_to(ROOT)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
