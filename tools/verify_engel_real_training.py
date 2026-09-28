#!/usr/bin/env python3
"""Verify that prompt training actually TRAINS something (2026-08-01).

Before this loop existed, the Prompt Training window was practice with no student:
sessions ran 40 graded turns through Engel's own chat and every one of them was thrown
away, because the daily SFT build admits external-provider rows only and the SLM roster
was trained by hand from chat receipts. The gap was invisible -- the UI said PASS, the
receipts looked healthy, and no model ever changed.

These checks are the regression guard for the loop that closed it. They are written
against the JOIN POINTS, because that is where a four-file chain silently breaks: the
runner emits a pack, the SFT dataset builder admits rows from it, the SLM dataset
builder labels rows from it, and the cycle orchestrator re-derives the same verdict --
four independent readers of one contract. A rename or a type drift in any one of them
does not raise; it just quietly trains on nothing again.

So the pack under test is not a fixture. It is produced by the REAL runner from a
synthetic session receipt and then fed to the real consumers, which is the only way to
catch the class of bug where every component passes its own unit test and the chain
still carries no data.

Gates:
  1. Pack contract      - schema, required fields, atomic write, no C: writes.
  2. Admit rule         - each condition refuses on its own; a rejected turn is still
                          recorded (the SLM needs the negative class).
  3. Communication gate - chat prose accepted; scaffolded/filler/bot text refused.
  4. Discipline wiring  - contract, level text, and template discipline all resolve to
                          "communication" (a silent downgrade to aec trains the wrong voice).
  5. SFT admit path     - only stamped rows enter, base_prompt is the trained text, and
                          the delivered wrapper never becomes training input.
  6. Identity           - ordinary chat prose addressing Joshua survives the identity
                          filter on this lane, while a Chase-confusion reply still does not.
  7. SLM corpus         - the same pack yields labelled train_admit rows, both classes.
  8. Orchestrator       - its independent re-derivation agrees with the runner's verdict;
                          LLM training is opt-in, exact-approval gated, and never deploys.
  9. Governor           - "communication" survives the metadata clamp and has an admit branch.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
for _p in (ROOT, TOOLS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import engel_build_training_dataset as sft  # noqa: E402
import engel_prompt_training_quarantine as pack_quarantine  # noqa: E402
import engel_governor as gov  # noqa: E402
import engel_slm_dataset_builder as slmds  # noqa: E402
import engel_slm_roster as slm_roster  # noqa: E402
import engel_ui_prompt_training_support as support  # noqa: E402
import run_engel_flutter_main_ui_prompt_training as runner  # noqa: E402
import run_engel_real_training_cycle as cycle  # noqa: E402
import sync_engel_training_assets as sync  # noqa: E402

checks: list[dict[str, Any]] = []

# A reply in Engel's real chat voice: first person, plain sentences, no scaffolding,
# and it addresses Joshua by name the way the actual chat does.
GOOD_REPLY = (
    "Joshua, I checked before answering. The overnight sweep finished, but the second stage "
    "never started, so what you are looking at on that page is still yesterday's number. I "
    "do not yet know whether it stopped on an error or simply had nothing to do, because "
    "that stage records its exit code and not its output. I would rather tell you that "
    "plainly than guess at a cause and send you looking in the wrong place. The next thing I "
    "would do is rerun that one stage and keep what it prints, which takes about a minute."
)
# A second, equally clean chat-voice reply. Same shape and quality as GOOD_REPLY, different
# words -- so the "two clean turns are both admitted" check tests the admit rule and not the
# duplicate-reply rule.
SECOND_GOOD_REPLY = (
    "Joshua, I looked before answering. The phone finished its queue about an hour ago, but "
    "it never sent the return packet, so the page still shows the job as running. I cannot "
    "tell yet whether the packet failed to send or was sent and dropped, because that hop is "
    "the one place we keep no receipt. I would rather say that than invent a cause. The next "
    "step I would take is asking the phone to resend the last return, which costs nothing if "
    "it already arrived."
)
SCAFFOLDED_REPLY = (
    "Result: the dataset build finished and the roster is stale.\n"
    "Work: I read the cycle receipt and compared the timestamps on both artifacts.\n"
    "Check: the mirrored report is dated a week before the dataset manifest, which confirms it.\n"
    "Still open: whether the trainer failed or simply had too few rows to fit a model."
)
BOT_REPLY = (
    "Certainly! As an AI language model, I would be happy to help you with your training "
    "cycle question. Here is what I can tell you about the situation you have described, "
    "and please let me know if you need anything else at all about this topic today."
)


def check(name: str, ok: bool, detail: str) -> None:
    checks.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": detail})


def _raises_value_error(function: Any, value: Any) -> bool:
    try:
        function(value)
    except ValueError:
        return True
    return False


def _turn(index: int, reply: str, **overrides: Any) -> dict[str, Any]:
    """One prompt_results entry shaped the way run_training builds it."""
    base = f"Tell me where the training cycle actually stopped, number {index}."
    turn: dict[str, Any] = {
        "prompt_index": index,
        "status": "DONE",
        "discipline": "communication",
        "base_prompt": base,
        "delivered_prompt": runner._leveled_training_prompt(base, "expert", "communication"),
        "prompt": base,
        "material_topic": "answering the current message directly",
        "training_level": "expert",
        "scheduled_hour": 1,
        "training_sample_eligible": True,
        "discipline_eligibility_ok": True,
        "local_only_training": True,
        "selected_provider": "ct_sparse_moe_specialist",
        "creation_job": False,
        "chat_only_no_android_or_sub_engel": True,
        "agent_meeting_room_used": False,
        "workspace_path": "",
        "wrapper_receipt_path": "",
        "wrapper_receipt": {"assistant_reply": reply, "ok": True},
    }
    turn.update(overrides)
    return turn


def _session_receipt(turns: list[dict[str, Any]]) -> dict[str, Any]:
    template_path = str(
        ROOT / "memory" / "training" / "engel_main" / "templates"
        / "ENGEL_TEMPLATE_CHAT_COMMUNICATION.json"
    )
    binding = runner._load_canonical_curriculum_binding(template_path)
    return {
        "schema": "engel_ui_prompt_training_session_v1",
        "run_id": "engel_verify_real_training_fixture",
        "mode": "scheduled",
        "training_level": "expert",
        "training_targets": "slm,llm",
        "template_path": template_path,
        "curriculum_binding": binding,
        "scheduled_hours": 8,
        "trainings_per_hour": 10,
        "start_index": 1,
        "prompt_results": turns,
        "summary": {"training_discipline": "communication"},
    }


def _read_pack(pack_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(pack_dir.glob("ENGEL_PROMPT_TRAINING_PACK_*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


work = Path(tempfile.mkdtemp(prefix="engel_real_training_verify_", dir=str(ROOT / "runtime" / "temp")))
# The real on-disk layout, not a flat scratch dir: the SLM dataset builder resolves packs
# from <root>/memory/training/packs, so a fixture that flattens it would test a path that
# does not exist in production and pass while the live builder reads an empty directory.
pack_dir = work / "memory" / "training" / "packs"
original_packs_dir = runner.PACKS_DIR
original_sft_packs = sft.PACKS
try:
    # ---------------------------------------------------------------- 1 + 2: the pack
    runner.PACKS_DIR = pack_dir
    turns = [
        _turn(1, GOOD_REPLY),
        # (2026-08-06) Distinct text on purpose. Rows here reuse GOOD_REPLY so each varies
        # exactly ONE field, which is right for the other cases -- but rows 1 and 2 are the
        # two fully-clean turns, and since a run's own duplicate replies are now demoted
        # (a degraded lane repeats one canned answer), two clean turns sharing byte-identical
        # text would be testing the dedupe rule rather than the admit rule. Real clean turns
        # differ; the fixture now does too.
        _turn(2, SECOND_GOOD_REPLY, prompt_index=2),
        _turn(3, SCAFFOLDED_REPLY, prompt_index=3, discipline_eligibility_ok=False),
        _turn(4, GOOD_REPLY, prompt_index=4, status="FAIL"),
        _turn(5, GOOD_REPLY, prompt_index=5, local_only_training=False),
        _turn(6, GOOD_REPLY, prompt_index=6, training_sample_eligible=False),
        _turn(7, "too short to learn anything from", prompt_index=7),
        _turn(8, GOOD_REPLY, prompt_index=8, base_prompt=""),
        # a reply-less turn is absent from the pack entirely, not a rejected sample
        _turn(9, "", prompt_index=9),
    ]
    latest = runner.write_training_pack(_session_receipt(turns))
    rows = _read_pack(pack_dir)

    check(
        "pack_written_with_expected_rows",
        len(rows) == 8 and latest.get("rows") == 8,
        f"8 replying turns -> {len(rows)} rows, receipt says {latest.get('rows')} (turn 9 has no reply)",
    )
    check(
        "pack_row_schema_pinned",
        all(row.get("schema") == "engel_prompt_training_pack_row_v1" for row in rows),
        "every row declares engel_prompt_training_pack_row_v1",
    )
    required = {
        "run_id", "created_at_utc", "session_receipt", "prompt_index", "discipline",
        "base_prompt", "delivered_prompt", "assistant_reply", "prompt_sha256", "status",
        "admit", "admit_reason", "training_sample_eligible", "discipline_eligibility_ok",
        "local_only_training", "selected_provider", "contract_echo", "training_targets",
        "curriculum_id", "curriculum_title", "curriculum_material_version",
        "curriculum_template_path", "curriculum_template_sha256", "scheduled_hours",
        "trainings_per_hour", "session_start_index",
    }
    missing = sorted(required - set(rows[0])) if rows else sorted(required)
    check("pack_row_carries_contract_fields", not missing, f"missing fields: {missing or 'none'}")
    pack_path = Path(latest["pack_path"])
    immutable_bytes = pack_path.read_bytes()
    check(
        "pack_receipt_hashes_exact_raw_bytes",
        hashlib.sha256(immutable_bytes).hexdigest() == latest.get("pack_sha256")
        and b"\r\n" not in immutable_bytes,
        "receipt SHA-256 binds the exact LF bytes stored on disk",
    )
    try:
        runner._publish_immutable_training_pack(pack_path, "replacement\n")
        overwrite_refused = False
    except RuntimeError:
        overwrite_refused = pack_path.read_bytes() == immutable_bytes
    check(
        "stamped_pack_refuses_in_place_rewrite",
        overwrite_refused,
        "a stamped pack cannot be overwritten and its raw bytes remain unchanged",
    )
    quarantine_dir = work / "memory" / "training" / "prompt_row_quarantines"
    first_line = immutable_bytes.splitlines()[0].strip()
    sidecar = pack_quarantine.write_sidecar(
        pack_path=pack_path,
        entries=[{
            "line_number": 1,
            "row_sha256": hashlib.sha256(first_line).hexdigest(),
            "reason": "verification fixture",
        }],
        source_gate="verify_engel_real_training",
        quarantine_dir=quarantine_dir,
    )
    quarantine_view = pack_quarantine.load_pack(pack_path, quarantine_dir)
    check(
        "quarantine_is_append_only_sidecar",
        sidecar.is_file()
        and pack_path.read_bytes() == immutable_bytes
        and quarantine_view.get("ok") is True
        and quarantine_view.get("quarantined") == 1,
        "one hash-bound sidecar excludes one row without changing the source pack",
    )

    admitted = {row["prompt_index"] for row in rows if row["admit"] is True}
    check(
        "admit_rule_admits_only_clean_turns",
        admitted == {1, 2},
        f"admitted prompt indexes {sorted(admitted)}, expected [1, 2]",
    )
    # (2026-08-06) A run's own repeated reply must be captured ONCE. A degraded lane emits
    # the same canned text prompt after prompt, and the CT-side builder cannot absorb it
    # because it keys on the base prompt -- identical replies to different prompts have
    # different keys by construction, so every copy would reach training.
    dup_turns = [_turn(1, GOOD_REPLY), _turn(2, GOOD_REPLY, prompt_index=2)]
    # Write this probe pack into an ISOLATED directory. The SFT and SLM builders below scan
    # the whole pack dir, so leaving a second fixture pack beside the main one silently
    # changes their row counts -- which is exactly what happened on the first attempt.
    dup_dir = work / "memory" / "training" / "packs_dupe_probe"
    dup_dir.mkdir(parents=True, exist_ok=True)
    runner.PACKS_DIR = dup_dir
    try:
        dup_latest = runner.write_training_pack(_session_receipt(dup_turns))
    finally:
        runner.PACKS_DIR = pack_dir
    dup_rows = [
        json.loads(line)
        for line in Path(dup_latest["pack_path"]).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    dup_admitted = {r["prompt_index"] for r in dup_rows if r["admit"] is True}
    check(
        "duplicate_replies_are_captured_once",
        dup_admitted == {1},
        f"two turns with byte-identical replies must admit exactly one; admitted {sorted(dup_admitted)}",
    )
    check(
        "duplicate_row_is_kept_as_evidence",
        len(dup_rows) == 2
        and any(r.get("duplicate_of_prompt_index") == 1 for r in dup_rows),
        "the demoted duplicate must stay in the pack and name the row it duplicates",
    )
    # (2026-08-08) Byte-identity proved too narrow: live construction run 5188cd2f repeated
    # one answer across three prompts at 0.90-0.96 similarity and every copy passed the
    # hash check. A lightly-reworded echo must demote exactly like a byte-identical one.
    NEAR_GOOD_REPLY = GOOD_REPLY.replace(
        "which takes about a minute.",
        "which should take about two minutes tonight.",
    )
    near_dir = work / "memory" / "training" / "packs_near_dupe_probe"
    near_dir.mkdir(parents=True, exist_ok=True)
    runner.PACKS_DIR = near_dir
    try:
        near_latest = runner.write_training_pack(
            _session_receipt([_turn(1, GOOD_REPLY), _turn(2, NEAR_GOOD_REPLY, prompt_index=2)])
        )
    finally:
        runner.PACKS_DIR = pack_dir
    near_rows = [
        json.loads(line)
        for line in Path(near_latest["pack_path"]).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    near_admitted = {r["prompt_index"] for r in near_rows if r["admit"] is True}
    check(
        "near_duplicate_replies_are_demoted",
        near_admitted == {1}
        and any("near-duplicate" in str(r.get("admit_reason")) for r in near_rows),
        f"a >=0.90-similar echo must demote like a byte-identical one; admitted {sorted(near_admitted)}",
    )
    # ...and the SFT builder must catch near-echoes in packs written BEFORE the demotion
    # existed, or echoing ACROSS runs -- two stamped-admitted rows with near-identical
    # replies to different prompts must reach training once.
    legacy_dir = work / "memory" / "training" / "packs_legacy_near_dupe"
    legacy_dir.mkdir(parents=True, exist_ok=True)
    legacy_rows = []
    for row in near_rows:
        row = dict(row)
        row["admit"] = True
        row["training_sample_eligible"] = True
        row["discipline_eligibility_ok"] = True
        row.pop("duplicate_of_prompt_index", None)
        legacy_rows.append(row)
    legacy_pack = legacy_dir / "ENGEL_PROMPT_TRAINING_PACK_legacy_near_dupe_probe.jsonl"
    legacy_pack.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in legacy_rows) + "\n",
        encoding="utf-8",
    )
    legacy_pack.chmod(0o444)
    sft.PACKS = legacy_dir
    try:
        legacy_sft_rows = sft.from_prompt_training()
    finally:
        sft.PACKS = pack_dir
    check(
        "sft_builder_drops_near_duplicate_echoes",
        len(legacy_sft_rows) == 1,
        f"two admitted near-identical replies must reach SFT once; got {len(legacy_sft_rows)}",
    )

    refusals = {row["prompt_index"]: row["admit_reason"] for row in rows if row["admit"] is not True}
    check(
        "admit_rule_refuses_each_condition",
        set(refusals) == {3, 4, 5, 6, 7, 8} and all(str(r).strip() for r in refusals.values()),
        "one refusal each for domain-gate/status/non-local/not-eligible/short-reply/no-base-prompt: "
        + json.dumps({k: v[:60] for k, v in sorted(refusals.items())}),
    )
    check(
        "rejected_turns_stay_in_the_pack",
        len([row for row in rows if row["admit"] is not True]) == 6,
        "the SLM negative class is kept in the same file, not dropped",
    )
    check(
        "pack_writes_stay_off_c_drive",
        Path(latest["pack_path"]).drive.lower() != "c:" and not list(pack_dir.glob("*.tmp")),
        f"pack at {latest['pack_path']}, no .tmp left behind",
    )

    # ---------------------------------------------------------------- 3: voice gate
    # Called the way the runner calls it -- with the base prompt -- because the optional
    # served style grader judges a reply against the ask it answered, and grading it against
    # an empty prompt is a different (and wrongly harsher) test than production runs.
    voice_ask = "Tell me where the overnight sweep actually stopped."
    ok_good, why_good = runner._communication_answer_is_conversational(GOOD_REPLY, voice_ask)
    ok_scaffold, why_scaffold = runner._communication_answer_is_conversational(SCAFFOLDED_REPLY, voice_ask)
    ok_bot, why_bot = runner._communication_answer_is_conversational(BOT_REPLY, voice_ask)
    check("voice_gate_accepts_chat_prose", ok_good is True, why_good)
    check("voice_gate_refuses_scaffolding", ok_scaffold is False, why_scaffold)
    check("voice_gate_refuses_assistant_filler", ok_bot is False, why_bot)

    # Brevity floor (2026-08-05). 44 of this curriculum's 80 prompts ASK for a short reply
    # ("Keep the reply the size of the question", "one line that owns it"), and the flat
    # 200-char floor rejected the model for obeying them -- the 20260803 smoke admitted
    # 0 of 3 at 147/194/147 chars, so the curriculum trained nothing. A shorter floor
    # applies only when the prompt asked; it must not become a way in for a bare
    # acknowledgement or for scaffolding.
    brief_ask = (
        "Quick one, and I want it quick. Honest answer: is that already how you talk to "
        "me day to day? Keep the reply the size of the question."
    )
    concise = (
        "I have not looked at it yet. First thing I would check is the wrapper receipt "
        "for that prompt, because that says whether the turn was served or never reached "
        "the model."
    )
    ok_brief, why_brief = runner._communication_answer_is_conversational(concise, brief_ask)
    ok_same, _ = runner._communication_answer_is_conversational(concise, voice_ask)
    ok_ack, why_ack = runner._communication_answer_is_conversational("Got it.", brief_ask)
    ok_short_scaffold, _ = runner._communication_answer_is_conversational(
        "Result: the sweep stopped at prompt 38. Check: the wrapper receipt confirms it.",
        brief_ask,
    )
    check("voice_gate_accepts_concise_when_prompt_asked", ok_brief is True, why_brief)
    check(
        "voice_gate_keeps_full_floor_when_brevity_not_asked",
        ok_same is False,
        "the same concise reply must still fail an ordinary voice ask, or the floor is gone",
    )
    check("voice_gate_still_refuses_bare_acknowledgement", ok_ack is False, why_ack)
    check(
        "voice_gate_still_refuses_scaffolding_under_brevity",
        ok_short_scaffold is False,
        "a lower floor must not admit labelled scaffolding",
    )

    # ---------------------------------------------------------------- 4: discipline wiring
    contract = runner._training_answer_contract("communication")
    check(
        "communication_contract_is_voice_preserving",
        "no bullet lists" in contract.casefold() and "result:" in contract.casefold(),
        "the contract must forbid the labelled form, not impose one",
    )
    check(
        "communication_known_to_the_runner",
        "communication" in runner._KNOWN_DISCIPLINES,
        "an unknown discipline is silently downgraded to aec, which trains the wrong voice",
    )
    level_texts = {
        level: support.discipline_prompt_instruction(level, "communication")
        for level in ("low", "medium", "high", "expert")
    }
    aec_texts = {
        level: support.discipline_prompt_instruction(level, "aec")
        for level in ("low", "medium", "high", "expert")
    }
    check(
        "communication_has_its_own_level_text",
        all(level_texts[k] != aec_texts[k] for k in level_texts),
        "all four levels resolve to communication-specific depth guidance",
    )
    registry = {c["id"]: c["discipline"] for c in sync.ALL_CURRICULA}
    template = ROOT / "memory" / "training" / "engel_main" / "templates" / "ENGEL_TEMPLATE_CHAT_COMMUNICATION.json"
    tpl = json.loads(template.read_text(encoding="utf-8").lstrip("﻿")) if template.is_file() else {}
    check(
        "chat_communication_curriculum_materialized",
        registry.get("chat_communication") == "communication"
        and tpl.get("training_discipline") == "communication"
        and tpl.get("maximum_scheduled_prompt_count") == 80,
        f"registry={registry.get('chat_communication')}, template discipline="
        f"{tpl.get('training_discipline')}, prompts={tpl.get('maximum_scheduled_prompt_count')}",
    )

    # ---------------------------------------------------------------- 5 + 6: the SFT admit path
    sft.PACKS = pack_dir
    sft_rows = sft.from_prompt_training()
    check(
        "sft_admits_only_stamped_rows",
        len(sft_rows) == 2,
        f"from_prompt_training() returned {len(sft_rows)} rows from a pack with 2 admitted",
    )
    check(
        "sft_trains_on_the_unwrapped_ask",
        all(row["source"] == "prompt_training" for row in sft_rows)
        and all("Training depth:" not in row["user"] for row in sft_rows)
        and all("Training task:" not in row["user"] for row in sft_rows),
        "the level wrapper and answer contract must never become training input",
    )
    check(
        "sft_keeps_the_reply_intact",
        # Compare against the fixture replies EXACTLY rather than a prefix: the contract is
        # that the graded reply reaches training byte-for-byte, and an equality test proves
        # that where a prefix check would miss truncation or trailing mangling.
        {row["assistant"] for row in sft_rows} <= {GOOD_REPLY, SECOND_GOOD_REPLY}
        and bool(sft_rows),
        "the graded reply is what gets trained on, unmodified",
    )
    check(
        "identity_gate_allows_owner_chat_prose",
        len(sft_rows) == 2,
        "a reply addressing Joshua on this lane is owner speech, not guest-answered-as-Joshua",
    )
    # ... and the gate is still armed: the same lane must refuse a Chase-confusion reply.
    chase_decision = sft.classify_training_pair(
        source="prompt_training",
        user="Tell me where the sweep stopped.",
        assistant=(
            "Hello, Chase. You are Chase, so I will keep this short: the second stage never "
            "started and nothing downstream of it has fresh numbers to report yet today."
        ),
        record={},
        root=ROOT,
    )
    check(
        "identity_gate_still_refuses_actor_confusion",
        chase_decision.accept is False,
        f"a reply answering AS Chase on the owner lane must not train: {chase_decision.reasons}",
    )

    # ---------------------------------------------------------------- 7: the SLM corpus
    slm_rows = slmds.build_train_admit(list(slmds._iter_training_packs(work, 0)))
    labels = {row["label"] for row in slm_rows}
    # Only reply-quality verdicts are learnable. A non-local/action/duplicate row depends
    # on hidden provenance or session history, so treating it as a textual "reject" would
    # teach the classifier a boundary that cannot be inferred from (prompt, reply).
    teachable = [
        row
        for row in rows
        if sft.assess_prompt_training_pack_row(row).get("disposition") in {"admit", "reject"}
    ]
    check(
        "slm_labels_both_classes_from_the_pack",
        labels == {"admit", "reject"} and len(slm_rows) == len(teachable),
        f"{len(slm_rows)} labelled rows from {len(teachable)} teachable pack rows, "
        f"classes {sorted(labels)}",
    )
    check(
        "slm_learns_from_the_unwrapped_ask",
        all("Training depth:" not in row["prompt"] for row in slm_rows),
        "serving skew: the head is asked about base prompts, so it must be trained on them",
    )

    # Target provenance is a per-row contract, not a cycle-wide guess. Exercise a real
    # mixed pack so each builder must ignore the other model family's clean admitted row,
    # while malformed/missing metadata fails closed before either training lane sees it.
    mixed_target_dir = work / "memory" / "training" / "packs_mixed_targets"
    mixed_target_dir.mkdir(parents=True, exist_ok=True)
    slm_only = dict(rows[0])
    slm_only["training_targets"] = "slm"
    llm_only = dict(rows[1])
    llm_only["training_targets"] = ["llm"]
    missing_target = dict(rows[0])
    missing_target.pop("training_targets", None)
    malformed_target = dict(rows[1])
    malformed_target["training_targets"] = "slm,gpu"
    mixed_rows = [slm_only, llm_only, missing_target, malformed_target]
    mixed_pack = mixed_target_dir / "ENGEL_PROMPT_TRAINING_PACK_mixed_targets.jsonl"
    mixed_pack.write_bytes(
        "".join(
            json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
            for row in mixed_rows
        ).encode("utf-8")
    )
    mixed_pack.chmod(0o444)

    sft_target_stats: dict[str, Any] = {}
    sft.PACKS = mixed_target_dir
    try:
        mixed_sft_rows = sft.from_prompt_training(target_stats=sft_target_stats)
    finally:
        sft.PACKS = pack_dir
    slm_target_stats: dict[str, Any] = {}
    mixed_slm_rows = slmds.build_train_admit(
        mixed_rows,
        target_stats=slm_target_stats,
    )
    check(
        "sft_consumes_only_explicit_llm_targets",
        len(mixed_sft_rows) == 1
        and mixed_sft_rows[0]["assistant"] == SECOND_GOOD_REPLY
        and sft_target_stats.get("rows_explicitly_targeting") == 1
        and sft_target_stats.get("rows_excluded_other_target") == 1
        and sft_target_stats.get("rows_excluded_missing_or_malformed") == 2,
        json.dumps(sft_target_stats, sort_keys=True),
    )
    check(
        "slm_consumes_only_explicit_slm_targets",
        len(mixed_slm_rows) == 1
        and mixed_slm_rows[0]["reply"] == GOOD_REPLY
        and slm_target_stats.get("rows_explicitly_targeting") == 1
        and slm_target_stats.get("rows_excluded_other_target") == 1
        and slm_target_stats.get("rows_excluded_missing_or_malformed") == 2,
        json.dumps(slm_target_stats, sort_keys=True),
    )
    check(
        "target_normalizer_fails_closed",
        sft.normalize_training_targets(" LLM,slm,llm ") == ("slm", "llm")
        and all(
            _target_rejected
            for _target_rejected in [
                (lambda value: (
                    False
                    if not _raises_value_error(sft.normalize_training_targets, value)
                    else True
                ))(value)
                for value in (None, "", "slm,gpu", {"slm": True}, ["slm", 4])
            ]
        ),
        "only an explicit slm/llm string or string list is accepted",
    )

    # ---------------------------------------------------------------- 8: the orchestrator
    original_cycle_dir = cycle.PACK_DIR
    try:
        cycle.PACK_DIR = pack_dir
        collected = cycle.collect_packs(48.0, True)
    finally:
        cycle.PACK_DIR = original_cycle_dir
    check(
        "orchestrator_agrees_with_the_runner_verdict",
        collected.get("admitted") == 2
        and not collected.get("admit_disagreements"),
        f"orchestrator counted {collected.get('admitted')} admitted, "
        f"admit_disagreements={collected.get('admit_disagreements')}",
    )
    original_cycle_quarantine = cycle.QUARANTINE_DIR
    try:
        cycle.PACK_DIR = mixed_target_dir
        cycle.QUARANTINE_DIR = mixed_target_dir / "quarantines"
        collected_slm = cycle.collect_packs(48.0, True, "slm")
        collected_llm = cycle.collect_packs(48.0, True, "llm")
        collected_both = cycle.collect_packs(48.0, True, "slm,llm")
    finally:
        cycle.PACK_DIR = original_cycle_dir
        cycle.QUARANTINE_DIR = original_cycle_quarantine
    check(
        "orchestrator_counts_admission_per_explicit_target",
        collected_slm.get("admitted") == 1
        and collected_slm.get("admitted_by_target") == {"slm": 1}
        and collected_llm.get("admitted") == 1
        and collected_llm.get("admitted_by_target") == {"llm": 1}
        and collected_both.get("admitted") == 2
        and collected_both.get("admitted_by_target") == {"slm": 1, "llm": 1}
        and collected_both.get("target_exclusions", {}).get(
            "missing_or_malformed"
        ) == 2,
        "slm=" + json.dumps(collected_slm.get("admitted_by_target"), sort_keys=True)
        + "; llm=" + json.dumps(collected_llm.get("admitted_by_target"), sort_keys=True)
        + "; both=" + json.dumps(collected_both.get("admitted_by_target"), sort_keys=True),
    )

    def _planned_commands(targets: tuple[str, ...]) -> dict[str, str]:
        plan_receipt = {
            "run_id": "target_contract_probe",
            "steps": [],
            "packs": {"ct_stage_dir": "/opt/engel/run/target_contract_probe/packs"},
            "construction_corpus": {
                "ct_root": "/opt/engel/run/target_contract_probe/corpus",
                "mode": "complete",
                "files": [],
                "bundle_sha256": "f" * 64,
            },
        }
        plan_args = type(
            "PlanArgs",
            (),
            {
                "no_push_tools": True,
                "targets": targets,
                "slm_tasks": cycle.DEFAULT_SLM_TASKS,
            },
        )()
        original_event = cycle.event
        try:
            cycle.event = lambda *_args, **_kwargs: None
            cycle.plan_remote_steps(
                plan_receipt,
                {"target": "root@example.invalid"},
                plan_args,
                {"files": 1, "quarantine_files": []},
            )
        finally:
            cycle.event = original_event
        return {str(item["step"]): str(item.get("command") or "") for item in plan_receipt["steps"]}

    slm_plan = _planned_commands(("slm",))
    llm_plan = _planned_commands(("llm",))
    check(
        "cycle_plans_only_target_specific_builders",
        "build_dataset" not in slm_plan
        and "--training-target slm" in slm_plan.get("slm_datasets", "")
        and "slm_datasets" not in llm_plan
        and "--training-target llm" in llm_plan.get("build_dataset", ""),
        "slm steps=" + ",".join(slm_plan) + "; llm steps=" + ",".join(llm_plan),
    )
    disagreement_root = work / "disagreement_probes"
    legacy_disagreement_dir = disagreement_root / "legacy"
    current_disagreement_dir = disagreement_root / "current"
    probe_quarantine_dir = disagreement_root / "quarantines"
    legacy_disagreement_dir.mkdir(parents=True, exist_ok=True)
    current_disagreement_dir.mkdir(parents=True, exist_ok=True)
    safe_row = dict(rows[0])
    legacy_bad = dict(rows[0])
    legacy_bad.update({
        "prompt_index": 901,
        "base_prompt": "Explain why this historical quality claim must be regraded.",
        "admit": True,
        "discipline_eligibility_ok": False,
    })
    for field in (
        "action_lane_used",
        "response_kind",
        "base_prompt_sha256",
        "base_prompt_hash_canonicalization",
    ):
        legacy_bad.pop(field, None)
    current_bad = dict(legacy_bad)
    current_bad.update({
        "prompt_index": 902,
        "base_prompt": "Explain why a current emitter disagreement must block.",
        "action_lane_used": False,
        "response_kind": "chat",
        "base_prompt_sha256": "0" * 64,
        "base_prompt_hash_canonicalization": (
            "unicode_nfkc_casefold_collapsed_whitespace_v1"
        ),
    })

    def _write_disagreement_probe(
        directory: Path, name: str, probe_row: dict[str, Any]
    ) -> None:
        body = "".join(
            json.dumps(item, sort_keys=True, separators=(",", ":")) + "\n"
            for item in (safe_row, probe_row)
        )
        probe_path = directory / name
        probe_path.write_bytes(body.encode("utf-8"))
        probe_path.chmod(0o444)

    _write_disagreement_probe(
        legacy_disagreement_dir,
        "ENGEL_PROMPT_TRAINING_PACK_legacy_disagreement_probe.jsonl",
        legacy_bad,
    )
    _write_disagreement_probe(
        current_disagreement_dir,
        "ENGEL_PROMPT_TRAINING_PACK_current_disagreement_probe.jsonl",
        current_bad,
    )
    original_cycle_quarantine = cycle.QUARANTINE_DIR
    try:
        cycle.QUARANTINE_DIR = probe_quarantine_dir
        cycle.PACK_DIR = legacy_disagreement_dir
        legacy_collected = cycle.collect_packs(48.0, True)
        cycle.PACK_DIR = current_disagreement_dir
        current_collected = cycle.collect_packs(48.0, True)
    finally:
        cycle.PACK_DIR = original_cycle_dir
        cycle.QUARANTINE_DIR = original_cycle_quarantine
    check(
        "legacy_disagreement_is_excluded_and_warned",
        legacy_collected.get("admitted") == 1
        and legacy_collected.get("legacy_admit_disagreements") == 1
        and legacy_collected.get("current_admit_disagreements") == 0
        and legacy_collected.get("admit_disagreements"),
        "the audit collector keeps one safe row and identifies one stale legacy claim; "
        "strict all-five step behavior is exercised by verify_engel_five_curriculum_model_handoff",
    )
    check(
        "current_disagreement_blocks_the_cycle",
        current_collected.get("admitted") == 1
        and current_collected.get("current_admit_disagreements") == 1
        and current_collected.get("admit_disagreements"),
        "the audit collector exposes the current emitter disagreement; the strict all-five "
        "step rejects it before remote work in the dedicated handoff verifier",
    )
    slm_legacy_rows = slmds.build_train_admit([legacy_bad])
    check(
        "slm_quarantines_claimed_vs_current_disagreement",
        not slm_legacy_rows and len(slmds.TRAIN_ADMIT_QUARANTINE) == 1,
        "a stale claimed-admit/current-reject pair cannot become a negative SLM example",
    )
    check(
        "orchestrator_llm_lane_is_exact_approval_gated",
        cycle.normalize_training_targets("slm") == ("slm",)
        and cycle.llm_training_approval_valid(("slm",), "") is True
        and cycle.llm_training_approval_valid(("llm",), "") is False
        and cycle.llm_training_approval_valid(
            ("llm",), cycle.LLM_APPROVAL_PHRASE
        )
        is True,
        "SLM remains the compatible default; LLM refuses without the exact phrase",
    )
    check(
        "orchestrator_slm_defaults_come_from_the_canonical_roster",
        cycle.DEFAULT_SLM_TASKS == slm_roster.default_training_csv()
        and cycle.normalize_slm_task_csv("all") == ",".join(slm_roster.KNOWN_TASKS),
        cycle.DEFAULT_SLM_TASKS,
    )
    try:
        cycle.normalize_slm_task_csv("intent_router,unknown_head")
        unknown_task_rejected = False
    except Exception:
        unknown_task_rejected = True
    cycle_source = (TOOLS / "run_engel_real_training_cycle.py").read_text(
        encoding="utf-8"
    )
    check(
        "orchestrator_rejects_unknown_slm_heads",
        unknown_task_rejected,
        "an operator typo cannot silently produce a partial roster",
    )
    check(
        "orchestrator_pushes_the_roster_contract_to_ct",
        "engel_slm_roster.py" in cycle.CT_TOOL_FILES,
        str(cycle.CT_TOOL_FILES),
    )
    check(
        "orchestrator_isolates_selected_pack_files_per_cycle",
        '"--packs-dir"' in cycle_source
        and "CT_CYCLE_RUN_DIR" in cycle_source
        and 'receipt["packs"]["ct_stage_dir"]' in cycle_source,
        "dataset builders must not rescan an uncleared shared directory of historical packs",
    )
    check(
        "orchestrator_mirrors_only_gate_passing_slm_artifacts",
        'report.get("trained_ok")' in cycle_source
        and 'glob("*.joblib")' not in cycle_source,
        "stale or rejected files are not selected by wildcard",
    )
    check(
        "orchestrator_preserves_data_floor_evidence_for_the_ui",
        '"class_counts": entry.get("class_counts")' in cycle_source
        and '"min_per_class": entry.get("min_per_class")' in cycle_source,
        "the desktop can explain exactly why a head needs more examples",
    )
    source = (TOOLS / "run_engel_ct246_local_lora_proof.py").read_text(
        encoding="utf-8"
    )
    check(
        "llm_trainer_never_auto_deploys",
        '"auto_deployed": False' in source and "No auto-deploy" in source,
        "the selected LLM lane creates/evaluates an adapter but cannot promote it",
    )
    # (2026-08-07) The first live cycle crashed the capability gate on NameError: sys --
    # the step used sys.path but the module never imported sys, and no gate had ever
    # EXECUTED the step. The promotion went live unverified. Assert the name resolves in
    # the module the step actually runs in.
    check(
        "capability_gate_imports_resolve",
        hasattr(cycle, "sys") and callable(getattr(cycle, "step_capability_gate", None)),
        "step_capability_gate's module must resolve every name the step uses",
    )
    # (2026-08-07) seq=768 silently kept 108/1661 train and 0/43 val examples (Engel's SFT
    # prompts median ~796 tokens), so the adapter trained on 6.5% of the corpus and val
    # loss was 0.0 from an EMPTY set. The default window must fit the corpus it feeds.
    import re as _re
    _seq = _re.search(r'"--seq",\s*type=int,\s*default=(\d+)', source)
    check(
        "lora_seq_window_fits_the_corpus",
        bool(_seq) and int(_seq.group(1)) >= 1536,
        f"proof runner --seq default is {_seq.group(1) if _seq else 'MISSING'}; "
        "measured: 1536 keeps 1661/1661 train and 43/43 val rows",
    )
    # (2026-08-07) Budget-capped runs must ACCUMULATE: without lineage resume, every proof
    # run re-inits LoRA and serial budgets throw away each other's progress forever.
    check(
        "lora_runs_accumulate_through_lineage",
        "ADAPTER_POINTER" in source
        and '"--resume-adapter", resume_adapter' in source
        and '"--fresh"' in source,
        "the proof runner must resume the pointed-at adapter by default, --fresh to opt out",
    )
    check(
        "lora_measures_negative_contrast",
        '"--negative"' in source and '"val_minus_negative_delta"' in source,
        "loss on gate-rejected examples must be measured beside val loss: dropping both "
        "equally is style absorption, not learning of standards",
    )
    # (2026-08-08, operator-directed after the lineage-2 contrast went positive) The
    # trainer must RECEIVE the negative-aware weight, and the receipt must show how much
    # rejected-behavior signal entered training and at what weight -- with the eval half
    # held out, or the contrast metric would be echoing its own training set.
    check(
        "lora_trains_negative_aware",
        '"--negative-train-weight"' in source
        and '"negative_train_kept"' in source
        and '"negative_train_weight"' in source
        and "held out" in source,
        "bounded unlikelihood on a train half + held-out eval half, both in the receipt",
    )
    check(
        "lora_budget_buys_real_coverage",
        '"10800"' in cycle_source and cycle.TIMEOUT_LLM_TRAIN >= 21600,
        "3600s at seq 1536 is <0.1 epoch; the cycle budget must be 10800 with an ssh "
        f"timeout covering budget+eval (TIMEOUT_LLM_TRAIN={cycle.TIMEOUT_LLM_TRAIN})",
    )
    # Routed chat is still re-measured to suppress noise, but the SLM is advisory and
    # cannot causally change that reply. The monitor must never roll SLM bytes back.
    capability_body = cycle_source.split("def step_capability_gate", 1)[1].split(
        "def step_mirror_back", 1
    )[0]
    check(
        "capability_monitor_is_noise_checked_and_noncausal",
        "regressions_confirmed" in cycle_source
        and "regression_dismissed_as_noise" in cycle_source
        and "first_run & second_run" in cycle_source
        and "restore_mirror(" not in capability_body
        and "not causal" in capability_body,
        "generic routed-chat output cannot authorize rollback of advisory SLM artifacts",
    )
    # (2026-08-07 first-instrumented-run review) The operator reads the ROG cycle receipt;
    # the honesty numbers must live THERE, not only on CT. First run shipped 5 of 7 style
    # heads measurably worse than their incumbents and only an ssh session could see it.
    check(
        "cycle_receipt_mirrors_llm_honesty_numbers",
        '"coverage": proof.get("coverage")' in cycle_source
        and '"val_minus_negative_delta"' in cycle_source
        and '"adapter_lineage"' in cycle_source,
        "coverage, contrast, and lineage must be readable without CT access",
    )
    check(
        "cycle_receipt_surfaces_incumbent_regressions",
        '"incumbent_regressions"' in cycle_source
        and "measure worse than" in cycle_source,
        "a shipped head worse than the artifact it replaced must be visible in the step "
        "detail (direct selected-vs-incumbent gates own SLM selection)",
    )

    # ---------------------------------------------------------------- 9: the Governor
    clamped = gov.clamp_inbox_metadata(
        {"training_discipline": "communication", "persist_policy": "training", "base_prompt": "x"}
    )
    check(
        "governor_trusts_the_communication_discipline",
        clamped.get("training_discipline") == "communication",
        "a dropped discipline makes CT246 grade a chat-voice turn as construction",
    )
    verdict_ok = gov.govern("admit", {"discipline": "communication", "served": True,
                                      "local_only_turn": True, "contract_echo": False,
                                      "conversational_voice_ok": True})
    verdict_bad = gov.govern("admit", {"discipline": "communication", "served": True,
                                       "local_only_turn": True, "contract_echo": False,
                                       "conversational_voice_ok": False})
    check(
        "governor_admit_has_a_communication_branch",
        verdict_ok.get("outcome") is True and verdict_bad.get("outcome") is False,
        f"rule ids {verdict_ok.get('rule_id')} / {verdict_bad.get('rule_id')}",
    )
finally:
    runner.PACKS_DIR = original_packs_dir
    sft.PACKS = original_sft_packs
    shutil.rmtree(work, ignore_errors=True)

passed = sum(1 for item in checks if item["status"] == "PASS")
failed = [item for item in checks if item["status"] != "PASS"]
for item in checks:
    print(f"{item['status']} {item['name']} :: {item['detail']}")
print(f"\n{passed}/{len(checks)} checks passed")
print("verify_engel_real_training: " + ("GREEN" if not failed else "RED"))
raise SystemExit(0 if not failed else 1)
