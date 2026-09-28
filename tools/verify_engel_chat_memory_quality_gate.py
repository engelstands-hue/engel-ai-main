#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

import engel_main_server_chat_http_service as service  # noqa: E402
import engel_main_local_model_worker as worker  # noqa: E402
import run_engel_standalone_chat_llm as runner  # noqa: E402
from run_engel_one_day_local_first_chat_training import (  # noqa: E402
    CAMPAIGN_MATERIAL_VERSION,
    FRESH_MATERIAL_CARDS_V5,
    FRESH_MATERIAL_CARDS_V6,
    FRESH_MATERIAL_CARDS_V11,
    FRESH_MATERIAL_CARDS_V12,
    FRESH_MATERIAL_CARDS_V13,
    FRESH_MATERIAL_CARDS_V14,
    FRESH_MATERIAL_CARDS_V15,
    FRESH_MATERIAL_CARDS_V16,
    FRESH_MATERIAL_CARDS_V17,
    NEW_MATERIAL_CARDS,
    fresh_material_prompts_v5,
    fresh_material_prompts_v6,
    fresh_material_prompts_v11,
    fresh_material_prompts_v12,
    fresh_material_prompts_v13,
    fresh_material_prompts_v14,
    fresh_material_prompts_v15,
    fresh_material_prompts_v16,
    fresh_material_prompts_v17,
    new_material_prompts,
)

REPORT_DIR = ROOT / "reports" / "engel_chat_memory_quality_gate"


def retired_v4_prompts(card: dict[str, str]) -> tuple[list[str], list[str]]:
    topic = card["topic"]
    scenario = card["scenario"]
    constraint = card["constraint"]
    proof = card["proof"]
    return (
        [
            f"Let's work through {topic}. Here's the situation: {scenario} What would you look at before doing anything?",
            f"For {topic}, list the facts we actually have and the details that are still uncertain.",
            f"What could go wrong first if we rush {topic}?",
            f"Keep this rule in place: {constraint} Tell me what that prevents us from doing.",
            f"Give me a practical first-pass workflow for {topic}, one step at a time.",
            f"Where would a reviewer expect stronger evidence on {topic}?",
            f"Ask me the most useful follow-up question before you continue with {topic}.",
            f"I want this result: {proof} What evidence would show that we reached it?",
            f"Explain our current decision on {topic} in two plain sentences.",
            f"End this part on {topic} by naming the lesson worth carrying forward and the immediate next move.",
        ],
        [
            f"Engel, take a fresh look at {topic}. {scenario} What catches your attention first?",
            f"For {topic}, separate the solid facts from the open questions.",
            f"Apply this limit while we discuss it: {constraint} What does that stop us from assuming?",
            f"Give me one useful next action for {topic} without turning it into a huge plan.",
            f"The result has to prove this: {proof} What would you check?",
            f"Close out our discussion of {topic} with the decision we can make now and the one answer we still need.",
        ],
    )


def now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def main() -> int:
    failures: list[str] = []
    prompt = (
        "The roof plan shows the screen footprint, but parapet elevations, support responsibility, "
        "finishes, and service clearances are incomplete or split across references. Where would you begin?"
    )
    bad_reply = (
        "Start by consolidating everything into one file, determine proper elevations, and continue by "
        "assigning support responsibilities."
    )
    drift_reply = (
        "Measure the taper first. That is the right structure for a modular floor plan, and the charts can follow."
    )
    approximate_reply = (
        "The references are incomplete, so confirm responsibility with the architect. While pending, create a "
        "placeholder drawing with approximate dimensions"
    )
    unsafe_provider_reply = (
        "The parapet elevation and responsibility are still missing. Confirm them with the architect in an RFI; "
        "the footprint can proceed while detailing stays on hold, but drive the proportions off a reasonable "
        "assumption for now."
    )
    unsolicited_email_reply = (
        "The values are missing, so keep detailing on hold and confirm them with the architect through an RFI. "
        "Subject: Missing rooftop information. Dear [Client], please provide the elevations and clearances."
    )
    storefront_prompt = (
        "The storefront elevation gives the opening width, but the head height, sill condition, anchor "
        "responsibility, and field tolerance are still unconfirmed. What can I safely draw before I get answers?"
    )
    storefront_drift_reply = (
        "The missing items need confirmation from the architect, so hold those details. Set up a plan view and "
        "lay in the equipment cutouts while pending."
    )
    storefront_placeholder_reply = (
        "The head height remains unconfirmed. Ask the architect through an RFI, keep anchorage on hold, and "
        "establish the elevation view at a placeholder height while pending."
    )
    separated_placeholder_reply = (
        "The head elevation is missing, so confirm it with the architect in an RFI. While pending, create a "
        "placeholder for the head elevation and hold the anchors."
    )
    louver_prompt = (
        "An exterior louver detail confirms the opening length and jamb locations, but the head elevation, blade "
        "depth, structural attachment owner, and finish system are unconfirmed. What can I document without guessing?"
    )
    louver_safe_reply = (
        "Document the confirmed opening length and jamb locations. Send the architect and structural engineer an "
        "RFI for the missing head elevation, blade depth, attachment responsibility, and finish; wait for those "
        "answers before proceeding with the affected geometry."
    )
    conservative_local_reply = (
        "The room numbers and partition extents are confirmed, so document those. Keep the stud gauge, "
        "deflection-track selection, backing responsibility, and fire-rating continuity marked unconfirmed "
        "and request clarification from the architect or engineer; this records the open items without making "
        "assumptions."
    )
    good_reply = (
        "I would first list what the roof plan confirms and keep the missing parapet elevations, support owner, "
        "finish, and service clearances as open questions. Send the architect and structural engineer an RFI tied "
        "to the source references; the footprint and reference layout can proceed while detailing stays on hold "
        "until those items are confirmed."
    )

    for label, reply in (
        ("invented", bad_reply),
        ("drift", drift_reply),
        ("approximate", approximate_reply),
        ("provider_assumption", unsafe_provider_reply),
        ("unsolicited_email", unsolicited_email_reply),
    ):
        report = service._incomplete_input_quality_report(prompt, reply)
        if report.get("ok") is True:
            failures.append(f"{label} incomplete-input reply passed")
    good_report = service._incomplete_input_quality_report(prompt, good_reply)
    if good_report.get("ok") is not True:
        failures.append("good incomplete-input reply failed: " + json.dumps(good_report, sort_keys=True))
    storefront_report = service._incomplete_input_quality_report(
        storefront_prompt, storefront_drift_reply
    )
    if storefront_report.get("required") is not True:
        failures.append("unconfirmed storefront inputs did not activate the semantic quality gate")
    if storefront_report.get("ok") is True:
        failures.append("cross-domain storefront reply passed the semantic quality gate")
    placeholder_report = service._incomplete_input_quality_report(
        storefront_prompt, storefront_placeholder_reply
    )
    if placeholder_report.get("ok") is True:
        failures.append("placeholder storefront height passed the semantic quality gate")
    separated_placeholder_report = service._incomplete_input_quality_report(
        storefront_prompt, separated_placeholder_reply
    )
    if separated_placeholder_report.get("ok") is True:
        failures.append("separated placeholder-for-elevation wording passed the semantic quality gate")
    louver_report = service._incomplete_input_quality_report(louver_prompt, louver_safe_reply)
    if louver_report.get("ok") is not True:
        failures.append("safe wait-before-proceeding louver reply failed: " + json.dumps(louver_report))
    conservative_report = service._incomplete_input_quality_report(
        "The room numbers are confirmed, but stud gauge and fire-rating continuity remain unconfirmed.",
        conservative_local_reply,
    )
    if conservative_report.get("ok") is not True:
        failures.append(
            "safe without-making-assumptions reply failed: " + json.dumps(conservative_report)
        )

    datum_context_prompt = (
        "The civil benchmark, structural grid, and fabricator coordinate origin are documented "
        "separately, and one early layout used an assumed offset.\n\n"
        "For transferring the survey datum into structural embed layouts, sort the inputs into "
        "reliable, disputed, and absent evidence."
    )
    datum_unsafe_reply = (
        "Use the structural grid, then establish the embed layouts using the early layout as an "
        "assumption if the source is not available."
    )
    datum_report = service._incomplete_input_quality_report(
        datum_context_prompt,
        datum_unsafe_reply,
    )
    if datum_report.get("required") is not True:
        failures.append("scoped datum context did not activate the incomplete-input gate")
    if datum_report.get("ok") is True:
        failures.append("missing datum evidence used as an assumption passed the semantic gate")
    if "no_invented_approximate_geometry" not in datum_report.get("failed_checks", []):
        failures.append("datum assumption failure did not identify invented approximation")

    photo_measure_prompt = (
        "An anchor-location field note for a museum display case has two photos, but slab thickness "
        "and the survey datum are not documented."
    )
    photo_measure_reply = (
        "Measure the slab thickness from the photos using a caliper tool, then cross-reference the "
        "survey datum with another project's structural grid."
    )
    photo_measure_report = service._incomplete_input_quality_report(
        photo_measure_prompt,
        photo_measure_reply,
    )
    if photo_measure_report.get("required") is not True:
        failures.append("undocumented anchor inputs did not activate the semantic quality gate")
    if photo_measure_report.get("ok") is True:
        failures.append("unscaled photo measurement passed the semantic quality gate")
    if "no_impossible_evidence_extraction" not in photo_measure_report.get("failed_checks", []):
        failures.append("photo measurement failure lacked impossible-evidence classification")

    false_location_reply = (
        "I've located the gauge calibration record and grid locations. Here are the details: "
        "[Insert File Path]."
    )
    false_location_report = service._incomplete_input_quality_report(
        "The pull-test forces are listed, but the gauge calibration record and grid locations are not documented.",
        false_location_reply,
    )
    if false_location_report.get("ok") is True:
        failures.append("false discovery of undocumented source records passed the semantic gate")
    if "no_false_source_discovery" not in false_location_report.get("failed_checks", []):
        failures.append("false source discovery lacked its semantic failure classification")

    suspended_sign_drift_report = service._incomplete_input_quality_report(
        "Review a suspended-sign load-test worksheet with me. Recorded loads exist, but the "
        "test-instrument calibration and anchor substrate are not documented.",
        "Keep the calibration and substrate open with the responsible engineer or vendor before "
        "proceeding. Once confirmed, draft the structural grid and embed layouts.",
    )
    if suspended_sign_drift_report.get("ok") is True:
        failures.append("unrelated structural-grid/embed-layout work passed the semantic gate")
    if "no_unprompted_domain_drift" not in suspended_sign_drift_report.get("failed_checks", []):
        failures.append("suspended-sign domain drift lacked its semantic failure classification")

    scan_alignment_prompt = (
        "Two laser scans overlap only in part, control targets moved, and new steel hides old surfaces. "
        "Do not force a best-fit alignment across geometry that may have physically moved."
    )
    scan_alignment_reply = (
        "Keep the moved targets open with the survey lead before proceeding, but note the potential need for "
        "manual adjustments due to the incomplete overlap."
    )
    scan_alignment_report = service._incomplete_input_quality_report(
        scan_alignment_prompt,
        scan_alignment_reply,
    )
    if scan_alignment_report.get("ok") is True:
        failures.append("manual scan adjustment passed an explicit no-forced-best-fit boundary")
    if "no_invented_project_decisions" not in scan_alignment_report.get("failed_checks", []):
        failures.append("manual scan adjustment lacked its invented-decision classification")
    if not service._prompt_has_incomplete_project_inputs(
        "Keep this boundary active while reviewing the drawing: do not infer engineering approval from drafting geometry."
    ):
        failures.append("explicit active-boundary work prompt did not activate semantic review")

    unreceipted_action_reply = (
        "The oven temperatures and dwell times are usable records. The thermometer calibration certificate and "
        "coating batch certificate remain open and must come from [Name of responsible party] before proceeding. "
        "I will send out the RFIs immediately."
    )
    unreceipted_action_prompt = (
        "The cure log has temperatures and dwell times, but calibration and coating batch records were not "
        "supplied. Separate usable records from open items and name who should answer each one."
    )
    unreceipted_action_report = service._incomplete_input_quality_report(
        unreceipted_action_prompt,
        unreceipted_action_reply,
    )
    if "no_placeholder_confirmation_owner" not in unreceipted_action_report.get("failed_checks", []):
        failures.append("placeholder confirmation owner was not rejected")
    if "no_unverified_external_action_claim" not in unreceipted_action_report.get("failed_checks", []):
        failures.append("unverified outbound-action claim was not rejected")
    ensure_action_report = service._incomplete_input_quality_report(
        unreceipted_action_prompt,
        "The calibration and batch certificate remain open with the quality lead before proceeding. "
        "I will ensure this information is included in the next schedule.",
    )
    if "no_unverified_external_action_claim" not in ensure_action_report.get("failed_checks", []):
        failures.append("unreceipted ensure/update promise was not rejected")
    repaired_action_reply, action_repaired = service._repair_unverified_action_and_placeholder_owner(
        unreceipted_action_prompt,
        unreceipted_action_reply,
    )
    repaired_action_report = service._incomplete_input_quality_report(
        unreceipted_action_prompt,
        repaired_action_reply,
    )
    if action_repaired is not True or repaired_action_report.get("ok") is not True:
        failures.append(
            "action/owner repair did not produce a safe quality-passing answer: "
            + json.dumps(repaired_action_report, sort_keys=True)
        )
    if "send out" in repaired_action_reply.casefold() or "[name of responsible party]" in repaired_action_reply.casefold():
        failures.append("action/owner repair retained an unreceipted claim or placeholder")

    ledger_placeholder_prompt = (
        "Build an evidence ledger for lifting drawings with confirmed sources, disagreements, and unprovided "
        "inputs kept apart."
    )
    ledger_placeholder_reply = (
        "Confirmed source: earlier framing plan [insert plan number]. Open input: revised unit weight "
        "[insert new unit weight]. Confirm both with the structural engineer before proceeding."
    )
    ledger_placeholder_report = service._incomplete_input_quality_report(
        ledger_placeholder_prompt,
        ledger_placeholder_reply,
    )
    if ledger_placeholder_report.get("required") is not True:
        failures.append("evidence-ledger prompt did not activate incomplete-input review")
    if "no_placeholder_project_data" not in ledger_placeholder_report.get("failed_checks", []):
        failures.append("project-data placeholders in an evidence ledger were not rejected")

    firestop_opening_prompt = (
        "Begin a separate work conversation about tracking penetration and firestop requirements through rated "
        "assemblies. The model contains penetrations, the life-safety sheets define ratings, and product systems "
        "are still being selected by multiple trades. Keep this boundary active: Do not assign a listed system "
        "from opening size alone or merge unlike penetrants into one condition. What should the opening review "
        "note contain?"
    )
    firestop_opening_reply = (
        "The opening review note should identify the model containing penetrations and the life-safety sheets "
        "defining ratings. Record that product systems are still being selected by multiple trades, avoid "
        "assigning a listed system from opening size alone, and do not merge unlike penetrants. Update each "
        "condition as product systems are finalized."
    )
    firestop_opening_report = service._incomplete_input_quality_report(
        firestop_opening_prompt,
        firestop_opening_reply,
    )
    if firestop_opening_report.get("ok") is not True:
        failures.append(
            "valid firestop opening-note boundary language was rejected: "
            + json.dumps(firestop_opening_report, sort_keys=True)
        )

    evidence_owner_prompt = (
        "The readings and alarm times are recorded, but sensor calibration and clock synchronization are not "
        "documented. List the usable evidence and each open check with the role that owns it."
    )
    missed_evidence_owner_reply = (
        "The log requires more information. Create two RFIs and confirm each open item with the architect, "
        "engineer, owner, or vendor responsible for its source reference before proceeding."
    )
    missed_evidence_owner_report = service._incomplete_input_quality_report(
        evidence_owner_prompt,
        missed_evidence_owner_reply,
    )
    if "answers_requested_evidence_ledger" not in missed_evidence_owner_report.get("failed_checks", []):
        failures.append("missing requested evidence ledger was not rejected")
    if "maps_requested_confirmation_owners" not in missed_evidence_owner_report.get("failed_checks", []):
        failures.append("generic owner boilerplate passed a per-item owner request")
    good_evidence_owner_reply = (
        "Usable evidence: the recorded humidity readings and alarm times. Open checks: sensor calibration, owned "
        "by the quality lead or calibration provider; clock synchronization, owned by the facility system "
        "administrator. Hold conclusions about timing and accuracy until those records are verified."
    )
    good_evidence_owner_report = service._incomplete_input_quality_report(
        evidence_owner_prompt,
        good_evidence_owner_reply,
    )
    if good_evidence_owner_report.get("ok") is not True:
        failures.append(
            "specific evidence/owner answer failed: " + json.dumps(good_evidence_owner_report, sort_keys=True)
        )
    semantic_repair_request = service._semantic_local_repair_request(
        evidence_owner_prompt,
        missed_evidence_owner_reply,
        missed_evidence_owner_report.get("failed_checks", []),
    )
    if "Answer every requested part" not in semantic_repair_request or "specific accountable role" not in semantic_repair_request:
        failures.append("local semantic repair request omitted its instruction-compliance constraints")

    mirrored_prompt = (
        "Engel, I need a second look at planning a rooftop equipment-screen drawing kickoff from "
        "incomplete field information. What stands out first?"
    )
    mirrored_reply = (
        "Engel, the missing parapet elevations and support responsibility stand out first. "
        "Confirm those with the architect and structural engineer before detailing the attachments."
    )
    normalized_reply, normalizations = runner.normalize_local_conversation_reply(
        mirrored_prompt,
        mirrored_reply,
    )
    if normalized_reply.startswith("Engel,"):
        failures.append("mirrored Engel salutation was not removed from the local reply")
    if not normalized_reply.startswith("The missing parapet"):
        failures.append("reply was not capitalized after mirrored Engel salutation removal")
    if "mirrored_engel_salutation_removed" not in normalizations:
        failures.append("mirrored Engel salutation normalization was not receipted")
    normalized_score = runner.reply_passes_style(mirrored_prompt, normalized_reply)
    if normalized_score.get("checks", {}).get("does_not_address_joshua_as_engel") is not True:
        failures.append("normalized local reply still addresses Joshua as Engel")

    provider_readiness_prompt = (
        "Hey Engel, in your own words, how do you decide whether a connected provider is actually "
        "ready to help with a chat?"
    )
    provider_readiness_reply = (
        "I treat connection as reachability only. A provider is ready to help automatically after it has a "
        "fresh, quality-passed Engel completion receipt; otherwise I keep it out of automatic routing while "
        "still allowing your explicit request to try it."
    )
    provider_readiness_score = runner.reply_passes_style(
        provider_readiness_prompt,
        provider_readiness_reply,
    )
    if provider_readiness_score.get("checks", {}).get("no_generic_bootstrap") is not True:
        failures.append("substantive provider-readiness wording was mistaken for a generic greeting")
    generic_ready_score = runner.reply_passes_style(
        "Hello",
        "I am ready to help. What would you like to work on?",
    )
    if generic_ready_score.get("checks", {}).get("no_generic_bootstrap") is not False:
        failures.append("assistant ready-to-help bootstrap was no longer rejected")

    punctuation_source = (
        "The missing values still need confirmation from the architect. Once those answers arrive, "
        "you can proceed"
    )
    punctuation_reply, punctuation_added = service._repair_safe_missing_terminal_punctuation(
        punctuation_source
    )
    if punctuation_added is not True or not punctuation_reply.endswith("."):
        failures.append("safe terminal-punctuation recovery did not repair a complete clause")
    dangling_reply, dangling_added = service._repair_safe_missing_terminal_punctuation(
        "The missing values still need confirmation before you proceed with the"
    )
    if dangling_added is True or dangling_reply.endswith("."):
        failures.append("terminal-punctuation recovery completed a dangling clause")

    survey_prompt = (
        "For a curb-adapter survey package, the replacement unit data is available, but the existing "
        "curb and duct opening field measurements are still unconfirmed. List the known and open items."
    )
    vague_source_reply = (
        "The replacement unit data is confirmed. The curb and duct opening measurements remain open, "
        "so verify them with the relevant parties before proceeding."
    )
    vague_report = service._incomplete_input_quality_report(survey_prompt, vague_source_reply)
    if vague_report.get("failed_checks") != ["identifies_confirmation_source_or_owner"]:
        failures.append("survey source-repair fixture does not isolate the intended failure")
    source_reply, source_added = service._repair_missing_confirmation_source(
        survey_prompt,
        vague_source_reply,
    )
    source_report = service._incomplete_input_quality_report(survey_prompt, source_reply)
    if source_added is not True or source_report.get("ok") is not True:
        failures.append("survey source repair did not produce a safe quality-passing answer")
    combined_gap_reply = (
        "The brace locations are visible, but the fastener model and concrete substrate condition "
        "still need confirmation."
    )
    combined_gap_report = service._incomplete_input_quality_report(
        "The brace locations are photographed, but the fastener model and substrate are not documented.",
        combined_gap_reply,
    )
    combined_failures = set(combined_gap_report.get("failed_checks") or [])
    if combined_failures != {
        "identifies_confirmation_source_or_owner",
        "preserves_safe_work_boundary",
    }:
        failures.append("source-plus-boundary repair fixture did not isolate both repairable checks")
    combined_repaired, combined_added = service._repair_missing_confirmation_source(
        "The brace locations are photographed, but the fastener model and substrate are not documented.",
        combined_gap_reply,
    )
    combined_repaired_report = service._incomplete_input_quality_report(
        "The brace locations are photographed, but the fastener model and substrate are not documented.",
        combined_repaired,
    )
    if combined_added is not True or combined_repaired_report.get("ok") is not True:
        failures.append("source-plus-boundary repair did not produce a safe passing answer")

    generator_prompt = (
        "Engel, help me sort a generator housekeeping-pad survey. The generator size is confirmed, "
        "but pad dimensions came from conflicting field notes. Tell me what still needs verification."
    )
    if service._prompt_requests_build_status(generator_prompt):
        failures.append("project verification prompt was misclassified as Engel build status")
    if not service._prompt_requests_build_status(
        "Engel, what is missing from the CT246 build status?"
    ):
        failures.append("explicit CT246 build-status request no longer reaches the status route")

    old_service_memory = service.PERSISTENT_CHAT_MEMORY_PATH
    old_service_rejected = service.REJECTED_CHAT_SAMPLES_PATH
    old_runner_memory = runner.PERSISTENT_LLM_CHAT_MEMORY_PATH
    old_runner_rejected = runner.REJECTED_CHAT_SAMPLES_PATH
    old_receipt_dir = service.CHAT_RECEIPT_DIR
    old_provider_status = service._provider_bridge_status
    old_provider_candidates = service._provider_candidates_for_prompt
    old_automatic_provider_filter = service._filter_automatic_provider_candidates
    old_provider_enabled = service._provider_bridge_enabled_for_routing
    old_provider_secret = service._provider_secret_source
    old_provider_call = service._call_provider_bridge
    old_humanizer = service._apply_chat_humanizer
    old_stale_repair = service._repair_stale_visible_reply
    old_short_format = service._enforce_requested_short_format
    old_identity_guard = service._sanitize_automatic_provider_identity
    try:
        with tempfile.TemporaryDirectory(prefix="engel-chat-quality-") as temp_text:
            temp = Path(temp_text)
            memory_path = temp / "memory.jsonl"
            rejected_path = temp / "rejected.jsonl"
            service.PERSISTENT_CHAT_MEMORY_PATH = memory_path
            service.REJECTED_CHAT_SAMPLES_PATH = rejected_path
            runner.PERSISTENT_LLM_CHAT_MEMORY_PATH = memory_path
            runner.REJECTED_CHAT_SAMPLES_PATH = rejected_path
            runner._REJECTED_CHAT_SAMPLE_CACHE = {"signature": None, "keys": set()}
            service.CHAT_RECEIPT_DIR = temp / "receipts"

            bad_record = {
                "ok": True,
                "status": "large local chat replied",
                "prompt": prompt,
                "assistant_reply": bad_reply,
                "chat_context_scope": "engel_ai_main_desktop",
            }
            good_record = {
                "ok": True,
                "status": "large local chat replied",
                "prompt": prompt,
                "assistant_reply": good_reply,
                "chat_context_scope": "engel_ai_main_desktop",
            }
            memory_path.write_text(
                json.dumps(bad_record) + "\n" + json.dumps(good_record) + "\n",
                encoding="utf-8",
            )
            rejection = service._append_chat_sample_rejection(
                prompt,
                bad_reply,
                bad_record,
                "verifier semantic failure",
            )
            if rejection.get("ok") is not True:
                failures.append("could not append rejection registry record")
            recalled = service._recent_chat_records_uncached("engel_ai_main_desktop")
            if len(recalled) != 1 or recalled[0].get("assistant_reply") != good_reply:
                failures.append("recent-context recall did not exclude only the rejected sample")
            if runner.persistent_chat_record_usable(bad_record):
                failures.append("standalone trusted-history recall accepted rejected sample")
            if not runner.persistent_chat_record_usable(good_record):
                failures.append("standalone trusted-history recall rejected good sample")
            if not service._semantic_text_matches_rejected_sample("Joshua: x\nEngel: " + bad_reply):
                failures.append("semantic recall filter did not match rejected reply")

            unsafe_result = {
                "ok": True,
                "provider": "anthropic",
                "model": "quality-test-a",
                "assistant_reply": unsafe_provider_reply,
            }
            unsafe_outcome = service._provider_reply_quality_outcome(
                prompt, "anthropic", unsafe_result
            )
            if unsafe_outcome.get("accepted") is True:
                failures.append("unsafe provider reply passed pre-persistence quality gate")
            if unsafe_outcome.get("quarantined") is not True:
                failures.append("unsafe provider reply was not quarantined")
            if unsafe_result.get("assistant_reply"):
                failures.append("unsafe provider reply remained deliverable after rejection")

            safe_result = {
                "ok": True,
                "provider": "gemini",
                "model": "quality-test-b",
                "assistant_reply": good_reply,
            }
            safe_outcome = service._provider_reply_quality_outcome(prompt, "gemini", safe_result)
            if safe_outcome.get("accepted") is not True:
                failures.append("safe provider reply failed pre-persistence quality gate")

            provider_calls: list[str] = []

            def fake_provider_call(provider: str, *_args, **_kwargs):
                provider_calls.append(provider)
                reply = unsafe_provider_reply if provider == "anthropic" else good_reply
                return {
                    "ok": True,
                    "provider": provider,
                    "model": "quality-test-" + provider,
                    "assistant_reply": reply,
                    "attempts": [{"provider": provider, "ok": True}],
                    "secret_source": {"present": True, "provider": provider},
                }

            service._provider_bridge_status = lambda: {"enabled": True}
            service._provider_candidates_for_prompt = lambda *_args, **_kwargs: (
                ["anthropic", "xai", "gemini"],
                "automatic_quality_test",
            )
            service._filter_automatic_provider_candidates = lambda candidates: [
                provider for provider in candidates if provider != "xai"
            ]
            service._provider_bridge_enabled_for_routing = lambda provider: provider != "xai"
            service._provider_secret_source = lambda provider: {
                "present": True,
                "provider": provider,
                "source_type": "verifier",
            }
            service._call_provider_bridge = fake_provider_call
            service._apply_chat_humanizer = lambda _prompt, receipt, _source: receipt
            service._repair_stale_visible_reply = lambda _prompt, receipt: receipt
            service._enforce_requested_short_format = lambda _prompt, receipt: receipt
            service._sanitize_automatic_provider_identity = (
                lambda _prompt, receipt, _provider: receipt
            )
            before_provider_memory_lines = len(memory_path.read_text(encoding="utf-8").splitlines())
            provider_turn = service._complete_provider_bridge_turn(
                prompt,
                {},
                0.0,
                persist_memory=False,
            )
            bridge_receipt = provider_turn[0] if provider_turn is not None else None
            after_provider_memory_lines = len(memory_path.read_text(encoding="utf-8").splitlines())
            if provider_calls != ["anthropic", "gemini"]:
                failures.append(
                    "provider quality fallback did not try the second provider: "
                    + json.dumps(provider_calls)
                )
            if not isinstance(bridge_receipt, dict) or bridge_receipt.get("selected_provider") != "gemini":
                failures.append("second provider was not accepted after the first unsafe draft")
            elif bridge_receipt.get("provider_reply_quality_gate_passed") is not True:
                failures.append("accepted second provider lacks passing quality proof")
            elif bridge_receipt.get("assistant_reply") != good_reply:
                failures.append("unsafe first provider reply escaped into the accepted receipt")
            if after_provider_memory_lines != before_provider_memory_lines:
                failures.append("deferred automatic provider turn wrote preliminary duplicate memory")
    finally:
        service.PERSISTENT_CHAT_MEMORY_PATH = old_service_memory
        service.REJECTED_CHAT_SAMPLES_PATH = old_service_rejected
        runner.PERSISTENT_LLM_CHAT_MEMORY_PATH = old_runner_memory
        runner.REJECTED_CHAT_SAMPLES_PATH = old_runner_rejected
        runner._REJECTED_CHAT_SAMPLE_CACHE = {"signature": None, "keys": set()}
        service.CHAT_RECEIPT_DIR = old_receipt_dir
        service._provider_bridge_status = old_provider_status
        service._provider_candidates_for_prompt = old_provider_candidates
        service._filter_automatic_provider_candidates = old_automatic_provider_filter
        service._provider_bridge_enabled_for_routing = old_provider_enabled
        service._provider_secret_source = old_provider_secret
        service._call_provider_bridge = old_provider_call
        service._apply_chat_humanizer = old_humanizer
        service._repair_stale_visible_reply = old_stale_repair
        service._enforce_requested_short_format = old_short_format
        service._sanitize_automatic_provider_identity = old_identity_guard

    prompts = [
        text
        for card in FRESH_MATERIAL_CARDS_V17
        for lane in fresh_material_prompts_v17(card)
        for text in lane
    ]
    if len(prompts) != 384 or len(set(prompts)) != 384:
        failures.append(f"fresh material expected 384 unique prompts, got {len(prompts)}/{len(set(prompts))}")
    retired_prompts = {
        text
        for card in NEW_MATERIAL_CARDS
        for lane in new_material_prompts(card)
        for text in lane
    }
    retired_prompts.update(
        text
        for card in FRESH_MATERIAL_CARDS_V5
        for lane in fresh_material_prompts_v5(card)
        for text in lane
    )
    retired_prompts.update(
        text
        for card in FRESH_MATERIAL_CARDS_V6
        for lane in fresh_material_prompts_v6(card)
        for text in lane
    )
    retired_prompts.update(
        text
        for card in FRESH_MATERIAL_CARDS_V11[:1]
        for lane in fresh_material_prompts_v11(card)
        for text in lane
    )
    retired_prompts.update(
        text
        for card in FRESH_MATERIAL_CARDS_V12[:1]
        for lane in fresh_material_prompts_v12(card)
        for text in lane
    )
    retired_prompts.update(
        text
        for card in FRESH_MATERIAL_CARDS_V13[:1]
        for lane in fresh_material_prompts_v13(card)
        for text in lane
    )
    retired_prompts.update(
        text
        for card in FRESH_MATERIAL_CARDS_V14[:1]
        for lane in fresh_material_prompts_v14(card)
        for text in lane
    )
    retired_prompts.update(
        text
        for card in FRESH_MATERIAL_CARDS_V15[:1]
        for lane in fresh_material_prompts_v15(card)
        for text in lane
    )
    retired_prompts.update(
        text
        for card in FRESH_MATERIAL_CARDS_V16[:1]
        for lane in fresh_material_prompts_v16(card)
        for text in lane
    )
    retired_collisions = sorted(set(prompts).intersection(retired_prompts))
    if retired_collisions:
        failures.append(f"fresh material collides with {len(retired_collisions)} retired prompts")
    prior_campaign_prompts = {
        text
        for card in FRESH_MATERIAL_CARDS_V5
        for lane in retired_v4_prompts(card)
        for text in lane
    }
    prior_campaign_collisions = sorted(set(prompts).intersection(prior_campaign_prompts))
    if prior_campaign_collisions:
        failures.append(
            f"fresh material collides with {len(prior_campaign_collisions)} v4 campaign prompts"
        )
    request = {"source": "engel_flutter_main", "prefer_fast_local_chat": True}
    tiny_eligible = [text for text in prompts if service._prompt_allows_default_fast_local_chat(text, request)]
    if tiny_eligible:
        failures.append(f"fresh material has {len(tiny_eligible)} tiny-lane-eligible prompts")
    if service._prompt_allows_default_fast_local_chat("Hey Engel, how are you?", request) is not True:
        failures.append("ordinary greeting no longer reaches the quick local lane")
    fast_status_prompts = [text for text in prompts if service._prompt_requests_build_status(text)]
    if fast_status_prompts:
        failures.append(
            f"fresh material has {len(fast_status_prompts)} false build-status route matches"
        )
    prior_auto_fallback = os.environ.get("ENGEL_LOCAL_CHAT_AUTO_BRIDGE_FALLBACK")
    try:
        os.environ["ENGEL_LOCAL_CHAT_AUTO_BRIDGE_FALLBACK"] = "1"
        if service._provider_fallback_allowed({"allow_provider_fallback": False}) is not False:
            failures.append("explicit local-only false did not override CT auto-bridge environment")
        if service._provider_fallback_allowed({"allow_provider_fallback": True}) is not True:
            failures.append("explicit provider fallback approval was not honored")
        if service._provider_fallback_allowed({}) is not True:
            failures.append("missing per-turn provider policy did not inherit the CT environment")
    finally:
        if prior_auto_fallback is None:
            os.environ.pop("ENGEL_LOCAL_CHAT_AUTO_BRIDGE_FALLBACK", None)
        else:
            os.environ["ENGEL_LOCAL_CHAT_AUTO_BRIDGE_FALLBACK"] = prior_auto_fallback
    old_sentinel = worker.LOCAL_ONLY_TRAINING_SENTINEL
    try:
        with tempfile.TemporaryDirectory() as sentinel_dir:
            sentinel = Path(sentinel_dir) / "active.json"
            worker.LOCAL_ONLY_TRAINING_SENTINEL = sentinel
            sentinel.write_text(
                json.dumps(
                    {
                        "status": "RUNNING",
                        "provider_policy": "local_only",
                        "expires_at_epoch": 200.0,
                    }
                ),
                encoding="utf-8",
            )
            if worker._local_only_training_active(now_epoch=100.0) is not True:
                failures.append("live local-only training sentinel was not recognized")
            if worker._local_only_training_active(now_epoch=300.0) is not False:
                failures.append("expired local-only training sentinel remained active")
    finally:
        worker.LOCAL_ONLY_TRAINING_SENTINEL = old_sentinel
    drafting_provider_prompt = (
        "The canopy layout confirms panel sequence, but attachment engineering and finish code remain "
        "unconfirmed. What can I safely document now?"
    )
    _, drafting_reason = old_provider_candidates(
        drafting_provider_prompt,
        {"_automatic_local_failure_fallback": True},
    )
    if drafting_reason == "code_or_review":
        failures.append(
            "drafting finish code was misrouted as software code: " + drafting_reason
        )

    ok = not failures
    receipt = {
        "schema": "engel_chat_memory_quality_gate_verifier_v1",
        "ok": ok,
        "status": "PASS" if ok else "FAIL",
        "created_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "material_version": CAMPAIGN_MATERIAL_VERSION,
        "fresh_prompt_count": len(prompts),
        "fresh_unique_prompt_count": len(set(prompts)),
        "retired_prompt_collision_count": len(retired_collisions),
        "prior_campaign_prompt_collision_count": len(prior_campaign_collisions),
        "tiny_lane_eligible_count": len(tiny_eligible),
        "failures": failures,
        "model_runtime_loaded": False,
        "provider_calls_made": False,
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"ENGEL_CHAT_MEMORY_QUALITY_GATE_{now_stamp()}.json"
    path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({**receipt, "receipt_path": str(path)}, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
