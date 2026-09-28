#!/usr/bin/env python3
from __future__ import annotations

from engel_chat_humanizer import improve_visible_reply
from engel_main_server_chat_http_service import _sanitize_automatic_provider_identity


def main() -> int:
    fixed, meta = improve_visible_reply(
        "Hey Engel, I'm Joshua. Talk with me normally and keep things direct.",
        "Joshua here. Normal chat, phone links, or agent work?",
        source="identity_guard_verifier",
    )
    assert fixed == "I'm here, Joshua. Normal chat, phone links, or agent work?", fixed
    assert meta.get("user_identity_inversion_repaired") is True, meta
    untouched, untouched_meta = improve_visible_reply(
        "Joshua, are you there?",
        "Joshua here. This is a quoted role-play line.",
        source="identity_guard_verifier",
    )
    assert untouched == "Joshua here. This is a quoted role-play line.", untouched
    assert untouched_meta.get("user_identity_inversion_repaired") is False, untouched_meta
    deduped, deduped_meta = improve_visible_reply(
        "Help me keep this answer concise.",
        "Efficiency matters. **What's the next actionable step?** - **What's the next actionable step?**",
        source="identity_guard_verifier",
    )
    assert deduped.count("What's the next actionable step?") == 1, deduped
    assert deduped_meta.get("duplicate_sentence_repaired") is True, deduped_meta
    specific, specific_meta = improve_visible_reply(
        "My drafting business is about precision, faster turnaround, and preventing problems before work reaches the job site.",
        "I agree. I will assess the gaps and prioritize next steps.",
        source="identity_guard_verifier",
    )
    assert "precise drawings" in specific and "field" in specific, specific
    assert specific_meta.get("drafting_context_repaired") is True, specific_meta
    profile, profile_meta = improve_visible_reply(
        "My public profile says I'm self-driven and serious about reaching big goals. Keep that context when you help me.",
        "My profile says I'm self-driven.",
        source="identity_guard_verifier",
    )
    assert "tied to you" in profile and "my profile" not in profile.casefold(), profile
    assert profile_meta.get("drafting_context_repaired") is True, profile_meta
    bilingual, bilingual_meta = improve_visible_reply(
        "Write a brief client update in English and then Spanish saying the drawing review is underway and we will flag build conflicts early.",
        "I will translate that later.",
        source="identity_guard_verifier",
    )
    assert "English:" in bilingual and "Español:" in bilingual, bilingual
    assert bilingual_meta.get("drafting_context_repaired") is True, bilingual_meta
    workflow, workflow_meta = improve_visible_reply(
        "Help me outline a realistic plan for turning a rough client idea into coordinated 2D drawings and a 3D model.",
        "Start with wireframes in Adobe XD.",
        source="identity_guard_verifier",
    )
    assert "coordinated 3D model" in workflow and "Adobe" not in workflow, workflow
    assert workflow_meta.get("drafting_context_repaired") is True, workflow_meta
    safe_profile, _ = improve_visible_reply(
        "End with a short profile of how you understand me, what is confirmed, and what you should still ask me directly.",
        "Your favorite color is teal and the project is Bluefin.",
        source="identity_guard_verifier",
    )
    assert "favorite color" not in safe_profile and "Bluefin" not in safe_profile, safe_profile
    assert "should still ask" in safe_profile, safe_profile
    guarded = _sanitize_automatic_provider_identity(
        "Hey Engel, how is everything running today?",
        {
            "assistant_reply": "Running well. Claude lane is up, and I am ready to work.",
            "assistant_output_text": "Running well. Claude lane is up, and I am ready to work.",
            "explicit_provider_requested": False,
        },
        "anthropic",
    )
    guarded_reply = str(guarded.get("assistant_reply") or "")
    assert "claude" not in guarded_reply.casefold(), guarded_reply
    assert "lane" not in guarded_reply.casefold(), guarded_reply
    assert (guarded.get("automatic_provider_identity_guard") or {}).get("reply_changed") is True, guarded
    disclosed = _sanitize_automatic_provider_identity(
        "Which provider lane handled this turn?",
        {
            "assistant_reply": "This turn used the Claude lane.",
            "assistant_output_text": "This turn used the Claude lane.",
            "explicit_provider_requested": False,
        },
        "anthropic",
    )
    assert disclosed.get("assistant_reply") == "This turn used the Claude lane.", disclosed
    assert (disclosed.get("automatic_provider_identity_guard") or {}).get("provider_disclosure_requested") is True, disclosed
    print("VERIFY_ENGEL_CHAT_IDENTITY_GUARD: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
