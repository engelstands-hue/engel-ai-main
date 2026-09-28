#!/usr/bin/env python3
"""Focused, isolated checks for downstream prompt-training pack safety."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

import engel_build_training_dataset as sft  # noqa: E402
import engel_construction_corpus as construction  # noqa: E402
import engel_slm_dataset_builder as slm  # noqa: E402

checks: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str) -> None:
    checks.append((name, bool(ok), detail))


def reply(tag: str) -> str:
    return (
        f"{tag}: I checked the supplied evidence and kept unsupported facts open. "
        "This completed local chat answer names what was verified, what remains unknown, "
        "and which concrete receipt must settle the open point before anyone proceeds."
    )


def pack_row(index: int, **overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "schema": sft.PACK_ROW_SCHEMA,
        "run_id": "isolated_downstream_safety",
        "created_at_utc": "2026-08-10T00:00:00Z",
        "session_receipt": "isolated",
        "prompt_index": index,
        "discipline": "communication",
        "base_prompt": f"Explain the verified state for isolated case {index}.",
        "delivered_prompt": f"Training task: isolated case {index}",
        "assistant_reply": reply(f"CASE_{index}"),
        "prompt_sha256": f"fixture-{index}",
        "status": "DONE",
        "admit": True,
        "admit_reason": "fixture audit claim",
        "training_sample_eligible": True,
        "discipline_eligibility_ok": True,
        "local_only_training": True,
        "selected_provider": "local",
        "contract_echo": False,
        "training_targets": "slm,llm",
    }
    row.update(overrides)
    return row


work = Path(
    tempfile.mkdtemp(
        prefix="engel_pack_downstream_safety_", dir=str(ROOT / "runtime" / "temp")
    )
)
packs = work / "isolated-packs"
packs.mkdir(parents=True)
original_grade = construction.grade_reply
original_override = sft.PACKS_DIR_OVERRIDE
original_env = os.environ.get(sft.PACKS_DIR_ENV)
original_corpus_env = os.environ.get(sft.CORPUS_ROOT_ENV)

try:
    def fake_grade(answer: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
        if "[AEC_EXACT_NO_CLAIM_RESULT]" in str(answer):
            return {"verdict": "verified", "exactly_verified": True, "refuted": False}
        supported = "[AEC_CLAIM_SUPPORTED]" in str(answer)
        return {
            "verdict": "verified" if supported else "undecidable",
            "exactly_verified": supported,
            "claim_support_verified": supported,
            "refuted": False,
        }

    construction.grade_reply = fake_grade
    conflict_reply = reply("CONFLICT_PAIR")
    stable_reply = reply("STABLE_PAIR")
    missing_required = pack_row(13)
    missing_required.pop("session_receipt")
    fixture_rows = [
        pack_row(1),
        pack_row(2, selected_provider="ct_sparse_moe_specialist"),
        pack_row(3, selected_provider="ct_workspace_setup_lane"),
        pack_row(
            4,
            workspace_path="/opt/engel/workspaces/unsafe-action",
            response_kind="action",
            action_lane_used=True,
        ),
        pack_row(5, duplicate_of_prompt_index=1),
        pack_row(
            6,
            discipline="aec",
            discipline_eligibility_ok=None,
            assistant_reply=reply("AEC_NO_SUPPORT"),
        ),
        pack_row(
            7,
            discipline="aec",
            discipline_eligibility_ok=None,
            assistant_reply=reply("[AEC_CLAIM_SUPPORTED]"),
        ),
        pack_row(8, schema=""),
        pack_row(9, base_prompt="Exact conflict prompt.", assistant_reply=conflict_reply),
        pack_row(
            10,
            base_prompt="Exact conflict prompt.",
            assistant_reply=conflict_reply,
            admit=False,
            admit_reason="historical conflicting audit claim",
        ),
        pack_row(11, base_prompt="Stable repeated prompt.", assistant_reply=stable_reply),
        pack_row(12, base_prompt="Stable repeated prompt.", assistant_reply=stable_reply),
        missing_required,
        pack_row(
            14,
            discipline="aec",
            discipline_eligibility_ok=None,
            assistant_reply=reply("[AEC_EXACT_NO_CLAIM_RESULT]"),
        ),
        pack_row(15, action_lane_used=1),
    ]
    fixture = packs / "ENGEL_PROMPT_TRAINING_PACK_isolated.jsonl"
    fixture.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in fixture_rows),
        encoding="utf-8",
    )
    os.chmod(fixture, 0o444)

    empty_corpus = work / "empty-corpus"
    empty_corpus.mkdir()
    partial_corpus = work / "partial-corpus"
    partial_corpus.mkdir()
    (partial_corpus / construction.MANIFEST_NAME).write_text(
        json.dumps({"schema": "engel_construction_corpus_manifest_v1", "docs": []}),
        encoding="utf-8",
    )

    os.environ[sft.CORPUS_ROOT_ENV] = str(empty_corpus)
    resolved_empty, empty_verification, empty_has_state = sft.verify_training_corpus_root()
    check(
        "corpus_environment_override_and_empty_fail_closed_state",
        resolved_empty == empty_corpus
        and empty_verification.get("ok") is False
        and empty_has_state is False,
        f"root={resolved_empty}; verification={empty_verification}; has_state={empty_has_state}",
    )
    _, partial_verification, partial_has_state = sft.verify_training_corpus_root(partial_corpus)
    check(
        "nonempty_partial_corpus_is_a_hard_preflight_failure",
        partial_has_state is True
        and partial_verification.get("ok") is False
        and any("schema" in item for item in partial_verification.get("blockers") or []),
        f"verification={partial_verification}; has_state={partial_has_state}",
    )

    original_for_empty = construction.grade_reply
    construction.grade_reply = original_grade
    empty_assessment = sft.assess_prompt_training_pack_row(
        pack_row(
            90,
            discipline="aec",
            discipline_eligibility_ok=None,
            assistant_reply=(
                'Section 1607.12 states live loads on decks. '
                'Source excerpt: "SECTION 1607.12 Live loads on decks."'
            ),
        ),
        corpus_root=empty_corpus,
    )
    construction.grade_reply = original_for_empty
    check(
        "explicit_empty_corpus_produces_zero_positive_aec",
        empty_assessment.get("disposition") == "reject"
        and "AEC claims" in str(empty_assessment.get("reason") or ""),
        json.dumps(empty_assessment, sort_keys=True),
    )

    sft_partial = subprocess.run(
        [
            sys.executable,
            str(TOOLS / "engel_build_training_dataset.py"),
            "--packs-dir",
            str(packs),
            "--corpus-root",
            str(partial_corpus),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    slm_out = work / "slm-partial-out"
    slm_partial = subprocess.run(
        [
            sys.executable,
            str(TOOLS / "engel_slm_dataset_builder.py"),
            "--root",
            str(work),
            "--out",
            str(slm_out),
            "--packs-dir",
            str(packs),
            "--corpus-root",
            str(partial_corpus),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    check(
        "both_builder_clis_refuse_nonempty_invalid_bundle_before_output",
        sft_partial.returncode == 2
        and slm_partial.returncode == 2
        and not slm_out.exists()
        and "did not verify" in sft_partial.stdout
        and "did not verify" in slm_partial.stdout,
        f"sft={sft_partial.returncode}:{sft_partial.stdout[-300:]}; "
        f"slm={slm_partial.returncode}:{slm_partial.stdout[-300:]}",
    )

    os.environ[sft.PACKS_DIR_ENV] = str(packs)
    sft.PACKS_DIR_OVERRIDE = None
    check(
        "sft_environment_pack_override",
        sft._packs_dir() == packs,
        f"resolved {sft._packs_dir()}",
    )

    loaded = list(slm._iter_training_packs(work, 0))
    check(
        "slm_environment_pack_override_and_strict_schema",
        len(loaded) == len(fixture_rows) - 2
        and all(
            row.get("schema") == sft.PACK_ROW_SCHEMA
            and sft.PACK_REQUIRED_FIELDS.issubset(row)
            for row in loaded
        ),
        f"loaded {len(loaded)} of {len(fixture_rows)} rows",
    )

    sft_rows = sft.from_prompt_training()
    sft_users = {row["user"] for row in sft_rows}
    check(
        "sft_allows_only_rederived_chat_rows",
        "Explain the verified state for isolated case 1." in sft_users
        and "Explain the verified state for isolated case 2." in sft_users
        and "Explain the verified state for isolated case 7." in sft_users
        and "Explain the verified state for isolated case 3." not in sft_users
        and "Explain the verified state for isolated case 4." not in sft_users
        and "Explain the verified state for isolated case 5." not in sft_users
        and "Explain the verified state for isolated case 6." not in sft_users
        and "Explain the verified state for isolated case 14." not in sft_users
        and "Explain the verified state for isolated case 15." not in sft_users,
        f"SFT users: {sorted(sft_users)}",
    )
    check(
        "sft_contains_no_action_workspace_reply",
        all("/opt/engel/workspaces" not in row["assistant"] for row in sft_rows),
        f"rows={len(sft_rows)}",
    )

    train_admit = slm.build_train_admit(loaded)
    by_prompt = {row["prompt"]: row["label"] for row in train_admit}
    check(
        "train_admit_rederives_policy_and_excludes_disagreements",
        "Explain the verified state for isolated case 6." not in by_prompt
        and by_prompt.get("Explain the verified state for isolated case 7.") == "admit"
        and "Explain the verified state for isolated case 3." not in by_prompt
        and "Explain the verified state for isolated case 4." not in by_prompt
        and "Explain the verified state for isolated case 5." not in by_prompt
        and "Explain the verified state for isolated case 14." not in by_prompt
        and "Explain the verified state for isolated case 15." not in by_prompt,
        json.dumps(by_prompt, sort_keys=True),
    )
    check(
        "train_admit_quarantines_exact_label_conflict",
        "Exact conflict prompt." not in by_prompt
        and any(
            item["claimed_labels"] == ["admit", "reject"]
            for item in slm.TRAIN_ADMIT_QUARANTINE
        )
        and len(slm.TRAIN_ADMIT_QUARANTINE) == 3,
        json.dumps(slm.TRAIN_ADMIT_QUARANTINE, sort_keys=True),
    )
    check(
        "train_admit_collapses_stable_exact_pair",
        sum(row["prompt"] == "Stable repeated prompt." for row in train_admit) == 1,
        f"train_admit rows={len(train_admit)}",
    )

    selected = sft.dedupe_sft_examples(
        {
            "prompt_training": [
                {
                    "source": "prompt_training",
                    "user": "One repeated user prompt.",
                    "assistant": "short verified answer",
                    "_selection_quality": (1, 4),
                },
                {
                    "source": "prompt_training",
                    "user": "One repeated user prompt.",
                    "assistant": "much longer but less verified answer " * 10,
                    "_selection_quality": (1, 2),
                },
                {
                    "source": "prompt_training",
                    "user": "One repeated user prompt.",
                    "assistant": "later and longer equal-quality answer " * 10,
                    "_selection_quality": (1, 4),
                },
            ]
        }
    )
    check(
        "sft_dedupe_uses_quality_and_stable_first_not_length",
        len(selected) == 1 and selected[0]["assistant"] == "short verified answer",
        repr(selected),
    )
finally:
    construction.grade_reply = original_grade
    sft.PACKS_DIR_OVERRIDE = original_override
    if original_env is None:
        os.environ.pop(sft.PACKS_DIR_ENV, None)
    else:
        os.environ[sft.PACKS_DIR_ENV] = original_env
    if original_corpus_env is None:
        os.environ.pop(sft.CORPUS_ROOT_ENV, None)
    else:
        os.environ[sft.CORPUS_ROOT_ENV] = original_corpus_env
    shutil.rmtree(work, ignore_errors=True)

for name, ok, detail in checks:
    print(f"{'PASS' if ok else 'FAIL'} {name} :: {detail}")
failed = [name for name, ok, _ in checks if not ok]
print(f"\n{len(checks) - len(failed)}/{len(checks)} checks passed")
print("verify_engel_training_pack_downstream_safety: " + ("GREEN" if not failed else "RED"))
raise SystemExit(1 if failed else 0)
