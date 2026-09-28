#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import engel_chat_humanization_slm as slm  # noqa: E402


def main() -> int:
    checks: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str) -> None:
        checks.append((name, ok, detail))

    empty, empty_meta = slm.humanize_chat_reply("hi", "", source="unit")
    check("empty_draft_stays_empty", empty == "" and empty_meta.get("reason") == "empty_draft", str(empty_meta))

    json_in = '{"ok": true}'
    json_out, json_meta = slm.humanize_chat_reply("return json only", json_in, source="unit")
    check(
        "machine_json_is_untouched",
        json_out == json_in and json_meta.get("reason") == "machine_protocol_turn",
        str(json_meta),
    )

    test_out, test_meta = slm.humanize_chat_reply("hi", "Hello there.", source="identity_guard_verifier")
    check(
        "verifier_source_skips_model",
        test_out == "Hello there." and test_meta.get("reason") == "test_source",
        str(test_meta),
    )

    robotic = (
        "As an AI language model, I am functioning within normal parameters. "
        "How can I assist you today?"
    )
    spoken, spoken_meta = slm.humanize_chat_reply("how are you", robotic, source="unit")
    fail_card = (
        "The local model hit a bounded timeout after 86.1 seconds. No provider was called "
        "because Engel chat is local-first -- pass allow_provider_fallback, or set "
        "ENGEL_LOCAL_CHAT_AUTO_BRIDGE_FALLBACK=1, to permit one."
    )
    fail_out, fail_meta = slm.humanize_chat_reply("hello", fail_card, source="unit")
    check(
        "fast_fail_card_is_spoken",
        "allow_provider_fallback" not in fail_out.casefold()
        and "bounded timeout" not in fail_out.casefold()
        and fail_meta.get("reply_changed") is True,
        fail_out[:160],
    )
    check(
        "robotic_draft_is_spoken",
        "as an ai" not in spoken.casefold()
        and "how can i assist" not in spoken.casefold()
        and spoken_meta.get("reply_changed") is True,
        spoken[:180] + " :: " + str(spoken_meta.get("reason")),
    )
    gguf_reason = str((spoken_meta.get("gguf") or {}).get("reason") or "")
    check(
        "robotic_kernel_does_not_require_gguf",
        spoken_meta.get("used") is True
        and gguf_reason
        in {
            "already_spoken",
            "not_needed",
            "model_missing",
            "source_skips_gguf",
            "timeout",
            "call_failed",
            "rewrite_rejected",
            "model_failed",
            "rewritten",
            "slm_kept_draft",
        },
        gguf_reason,
    )

    human = "I'm here and in a good working mood. What do you want to tackle?"
    kept, kept_meta = slm.humanize_chat_reply("how are you", human, source="unit")
    check(
        "already_spoken_is_kept",
        kept == human and kept_meta.get("reply_changed") is False,
        kept[:120] + " :: " + str(kept_meta.get("reason")),
    )

    report = (
        "Verifier PASS 8/8. Files changed: tools/engel_chat_humanization_slm.py. "
        "SHA256 abcdef. Deployed /opt/engel/tools/engel_chat_humanization_slm.py."
    )
    work_out, work_meta = slm.humanize_chat_reply("status of the job", report, source="unit")
    check(
        "work_report_is_not_crushed",
        "Verifier PASS 8/8" in work_out and "SHA256" in work_out,
        work_out[:160] + " :: " + str(work_meta.get("reason")),
    )

    public, public_meta = slm.humanize_chat_reply(
        "hello",
        "Hello! I'm Engel AI Main, your local AI companion. Feel free to ask me anything!",
        source="discord_public",
    )
    check(
        "discord_public_skips_gguf",
        str((public_meta.get("gguf") or {}).get("reason")) == "source_skips_gguf",
        str(public_meta.get("gguf")),
    )
    check(
        "discord_public_still_strips_filler",
        "feel free to ask" not in public.casefold() and public_meta.get("reply_changed") is True,
        public[:160],
    )

    check(
        "system_prompt_forbids_template_cards",
        "Joshua asks" in slm.SYSTEM and "canned examples" in slm.SYSTEM,
        slm.SYSTEM[:120],
    )
    template_card = (
        "Joshua asks how Engel AI Main and Sub-Engel relate in Discord. "
        "Engel explains: Engel runs on the Engel server container, and Sub-Engel "
        "is the live worker on DESKTOP-UE5A6GG."
    )
    wiki_out, wiki_meta = slm.humanize_chat_reply(
        "https://en.wikipedia.org/wiki/Laniakea_Supercluster",
        template_card,
        source="unit",
    )
    check(
        "wikipedia_template_card_is_spoken_off_topic",
        "laniakea" in wiki_out.casefold()
        and "joshua asks" not in wiki_out.casefold()
        and wiki_meta.get("reply_changed") is True,
        wiki_out[:180] + " :: " + str(wiki_meta.get("reason")),
    )
    check("examples_file_exists", slm.EXAMPLES_PATH.is_file(), str(slm.EXAMPLES_PATH))
    rows = []
    if slm.EXAMPLES_PATH.is_file():
        for line in slm.EXAMPLES_PATH.read_text(encoding="utf-8").splitlines():
            rows.append(json.loads(line))
    check(
        "examples_include_tesseract_pair",
        any("Tesseract" in str(row.get("spoken") or "") for row in rows),
        str(len(rows)),
    )
    check(
        "examples_include_robotic_drafts",
        any("as an ai" in str(row.get("draft") or "").casefold() for row in rows),
        str(len(rows)),
    )
    check(
        "leaked_rewrite_is_rejected",
        slm._usable_rewrite("hello", "REWRITE: USER SAID: nope") is False,
        "leak",
    )
    form_prompt = (
        "Training depth: Fellow (fellow_depth).\n"
        "Training task:\n"
        "Walk me through the wait.\n"
        "Answer ONLY in this filled-in form, grounded in Engel's real system:\n"
        "Confirmed: <claim>\nProof: <verifier>\nStill open: None"
    )
    form_draft = (
        "Confirmed: the runner waits for the backend.\n"
        "Proof: tools/run_engel_flutter_main_ui_prompt_training.py\n"
        "Still open: None."
    )
    form_out, form_meta = slm.humanize_chat_reply(form_prompt, form_draft, source="unit")
    check(
        "form_graded_training_is_not_spoken",
        form_out == form_draft and form_meta.get("reason") == "form_graded_training_turn",
        str(form_meta.get("reason")),
    )
    check(
        "form_graded_detector_accepts_engineering",
        slm.is_form_graded_training_prompt(form_prompt) is True,
        "engineering form",
    )
    comm_prompt = (
        "Training depth: Fellow (fellow_depth).\n"
        "Training task:\n"
        "Say the next step.\n"
        "Answer the way you would answer Joshua in the main Engel chat: first person."
    )
    check(
        "form_graded_detector_rejects_communication",
        slm.is_form_graded_training_prompt(comm_prompt) is False,
        "communication voice",
    )
    check(
        "form_graded_detector_rejects_live_chat",
        slm.is_form_graded_training_prompt("How are you today?") is False,
        "live chat",
    )
    check(
        "robotic_gguf_copy_is_rejected",
        slm._usable_rewrite(robotic, robotic) is False,
        "robotic copy",
    )
    check(
        "short_human_sentence_is_usable",
        slm._usable_rewrite("draft", "I'm here and ready to talk.") is True,
        "usable",
    )
    check("looks_robotic_detects_assist_closer", slm.looks_robotic(robotic) is True, "robotic")
    check("looks_robotic_rejects_spoken", slm.looks_robotic(human) is False, "spoken")

    chat_src = (ROOT / "tools" / "engel_main_server_chat_http_service.py").read_text(encoding="utf-8")
    check(
        "chat_service_calls_humanize_chat_reply",
        "from engel_chat_humanization_slm import humanize_chat_reply" in chat_src
        and "humanize_chat_reply(prompt, final" in chat_src,
        "chat wiring",
    )
    check(
        "chat_service_skips_form_graded_voice_bank",
        "form_graded_training_turn" in chat_src
        and "if not form_graded:" in chat_src,
        "form-graded training must not enter the spoken voice bank",
    )
    check(
        "chat_service_raises_model_cache",
        "enable_side_by_side_model_cache" in chat_src,
        "cache wiring",
    )
    discord_src = (ROOT / "tools" / "engel_discord_bridge.py").read_text(encoding="utf-8")
    check(
        "discord_bridge_runs_spoken_pass",
        'source="discord_public"' in discord_src and "humanize_chat_reply" in discord_src,
        "discord wiring",
    )
    dropin = ROOT / "scripts" / "systemd" / "engel-main-chat.service.d" / "90-chat-humanization-slm.conf"
    dropin_text = dropin.read_text(encoding="utf-8") if dropin.is_file() else ""
    check("systemd_dropin_exists", dropin.is_file(), str(dropin))
    check(
        "systemd_dropin_keeps_0.5b_on_cpu",
        "[Service]" in dropin_text
        and "Environment=ENGEL_HUMANIZATION_SLM=1" in dropin_text
        and "Environment=ENGEL_HUMANIZATION_SLM_N_GPU_LAYERS=0" in dropin_text
        and "Environment=ENGEL_LOCAL_MODEL_CACHE_MAX_MODELS=2" in dropin_text,
        dropin_text[:240],
    )
    catalog = json.loads((ROOT / "runtime" / "next_stage" / "models_brains" / "CATALOG.json").read_text(encoding="utf-8"))
    lanes = [row.get("lane") for row in catalog.get("ct246_llm_and_brain_lanes") or []]
    check("catalog_has_chat_humanization_slm_lane", "chat_humanization_slm" in lanes, str(lanes[:8]))

    failed = [name for name, ok, _ in checks if not ok]
    for name, ok, detail in checks:
        print(("PASS" if ok else "FAIL"), name, "::", detail)
    print(f"{sum(1 for _, ok, _ in checks if ok)}/{len(checks)} checks passed")
    print("verify_engel_chat_humanization_slm: " + ("GREEN" if not failed else "RED"))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
