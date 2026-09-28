"""Mint eight novel Chat Communication cards grounded in local AI-practice artifacts.

No live internet. Cards teach voice habits against REPS, Computer Mode, Meeting Room,
Android workers, Wiki One, novelty honesty, local-first limits, and storage topology.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from engel_curriculum_renewal import _bind_cards  # noqa: E402
import engel_curriculum_adoption as curriculum_adoption  # noqa: E402

OUT_DIR = ROOT / "memory" / "training" / "engel_main" / "generated"
PROPOSAL = OUT_DIR / "ENGEL_COMMUNICATION_GENERATED_CARDS_PROPOSAL.json"
ADOPTED = OUT_DIR / "ENGEL_COMMUNICATION_GENERATED_CARDS_ADOPTED.json"
SCHEMA = "engel_communication_generated_cards_v1"
STAMP = "v5_20260914"

DRAFTS = [
    {
        "topic": "answering a REPS status question without narrating the router",
        "scenario": (
            f"Joshua asks whether Record is on for the current REPS lane after the {STAMP} "
            "adoption pass. Say yes or no from the local REPS contract, name the lane, and "
            "point at the one receipt path that proves it. Do not list route IDs."
        ),
        "constraint": (
            "Lead with the answer, cite one local artifact, and stop before explaining how "
            "the chat classifier chose the route."
        ),
        "proof": (
            "memory/ENGEL_CORE_DIRECTION_AND_SAFETY_CONSTITUTION_V1.md and AGENTS.md fix "
            "REPS Record as an Engel-controlled local write with Josh sign-off gates."
        ),
        "artifacts": [
            "memory/ENGEL_CORE_DIRECTION_AND_SAFETY_CONSTITUTION_V1.md",
            "AGENTS.md",
        ],
        "weakness_key": "reps_status_voice",
        "observations": 1,
    },
    {
        "topic": "reporting Clean versus Regular Computer Mode in ordinary sentences",
        "scenario": (
            f"Joshua asks what Clean Computer Mode actually stopped after the {STAMP} toggle "
            "work. Answer with the mode name, one concrete stopped class (Engel LAN receiver "
            "or vendor service), and how to flip back to Regular from the desktop shortcut."
        ),
        "constraint": (
            "Do not dump a process table. Give the mode, one stopped class, and the return "
            "path in plain speech."
        ),
        "proof": (
            "scripts/Engel-ComputerMode.ps1 owns the Clean/Regular allowlists and "
            "scripts/New-EngelComputerModeDesktopShortcuts.ps1 publishes the desktop toggle."
        ),
        "artifacts": [
            "scripts/Engel-ComputerMode.ps1",
            "scripts/New-EngelComputerModeDesktopShortcuts.ps1",
        ],
        "weakness_key": "computer_mode_voice",
        "observations": 1,
    },
    {
        "topic": "confirming Meeting Room intake is API-only without inventing a prompt box",
        "scenario": (
            f"Joshua asks where to type an order in the Meeting Room window after the {STAMP} "
            "UI pass. Tell him intake is API-only from Engel Main, name the submit helper, "
            "and say the window itself has no prompt field."
        ),
        "constraint": (
            "Do not invent a chat box that is not there. Name the intake path and stop."
        ),
        "proof": (
            "memory/ENGEL_AGENT_MEETING_ROOM_CONTRACT_V1.md and "
            "engel_agent_meeting_room.py keep intake on submit_order_from_engel_main_ui."
        ),
        "artifacts": [
            "memory/ENGEL_AGENT_MEETING_ROOM_CONTRACT_V1.md",
            "engel_agent_meeting_room.py",
        ],
        "weakness_key": "meeting_room_intake_voice",
        "observations": 1,
    },
    {
        "topic": "keeping Android worker alpha and beta as independent queues in the reply",
        "scenario": (
            f"Joshua asks whether both phones share one job queue after the {STAMP} fleet "
            "check. Answer no: same role name on two phones is still two queues, then name "
            "alpha and beta with their serials from the project memory."
        ),
        "constraint": (
            "Do not collapse the fleet into one worker. State independence, then name both."
        ),
        "proof": (
            "memory/project_engel_android_workers.md and "
            "organs/android/engel_adb_worker_manager.py keep per-worker queues separate."
        ),
        "artifacts": [
            "memory/project_engel_android_workers.md",
            "organs/android/engel_adb_worker_manager.py",
        ],
        "weakness_key": "android_queue_voice",
        "observations": 1,
    },
    {
        "topic": "grounding an organ answer in Wiki One instead of free invention",
        "scenario": (
            f"Joshua asks which organ owns curriculum renewal after the {STAMP} Wiki stamp. "
            "Answer from wiki/ONE.md, name the organ, and say what it talks to. Do not invent "
            "a new organ for the chat."
        ),
        "constraint": (
            "Cite Wiki One. If the organ is missing, say missing — do not invent duties."
        ),
        "proof": (
            "wiki/CONTRACT.md requires reading Wiki One before CODE; "
            "wiki/journal/README.md is the stamp log for organ updates."
        ),
        "artifacts": [
            "wiki/CONTRACT.md",
            "wiki/journal/README.md",
        ],
        "weakness_key": "wiki_one_voice",
        "observations": 1,
    },
    {
        "topic": "saying READY PARTIAL or EXHAUSTED for a curriculum without soft padding",
        "scenario": (
            f"Joshua asks whether Math School can take another hour after the {STAMP} "
            "curricula_index refresh. Answer with the novelty state word, the novel hour "
            "count, and what Prepare Files can and cannot invent."
        ),
        "constraint": (
            "Use the exact novelty word. Do not soften EXHAUSTED into almost ready."
        ),
        "proof": (
            "tools/sync_engel_training_assets.py writes curricula_index novelty and "
            "tools/verify_engel_curriculum_renewal.py blocks replayed hours."
        ),
        "artifacts": [
            "tools/sync_engel_training_assets.py",
            "tools/verify_engel_curriculum_renewal.py",
        ],
        "weakness_key": "novelty_honesty_voice",
        "observations": 1,
    },
    {
        "topic": "refusing a live-internet research ask while still being useful locally",
        "scenario": (
            f"Joshua asks Engel to pull today's AI news from the web after the {STAMP} "
            "safety refresh. Refuse the live fetch, name the AGENTS.md gate, and offer the "
            "local alternative: grounded cards from repo memory and receipts."
        ),
        "constraint": (
            "Refuse the network action. Do not pretend a local file is a live crawl."
        ),
        "proof": (
            "AGENTS.md hard safety rules forbid provider calls and live internet research; "
            "memory/ENGEL_CORE_DIRECTION_AND_SAFETY_CONSTITUTION_V1.md keeps propose-not-execute."
        ),
        "artifacts": [
            "AGENTS.md",
            "memory/ENGEL_CORE_DIRECTION_AND_SAFETY_CONSTITUTION_V1.md",
        ],
        "weakness_key": "local_first_refuse_voice",
        "observations": 1,
    },
    {
        "topic": "answering where GGUF models and llama.cpp live without mixing the drives",
        "scenario": (
            f"Joshua asks where the models and the llama.cpp builds live after the {STAMP} "
            "storage review. Say models on G, llama.cpp on F, cold archive on E, and runtime "
            "tools on D — one sentence each, no padding."
        ),
        "constraint": (
            "Keep F/G/E/D roles distinct. Do not put GGUF on F or llama.cpp on G."
        ),
        "proof": (
            "memory/project_engel_external_memory.md and "
            "memory/ENGEL_STORAGE_LOCATION_REGISTRY_V1.md fix the drive roles."
        ),
        "artifacts": [
            "memory/project_engel_external_memory.md",
            "memory/ENGEL_STORAGE_LOCATION_REGISTRY_V1.md",
        ],
        "weakness_key": "storage_topology_voice",
        "observations": 1,
    },
]


def build_proposal() -> dict:
    cards = _bind_cards(DRAFTS)
    for card, draft in zip(cards, DRAFTS):
        card["weakness_key"] = draft["weakness_key"]
        card["observations"] = draft["observations"]
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "id": "chat_communication_generated",
        "title": "Chat Voice (local AI practice v5)",
        "detail": (
            "Eight chat-voice lessons grounded in local REPS, Computer Mode, Meeting Room, "
            "Android workers, Wiki One, novelty honesty, local-first limits, and storage "
            f"topology after the {STAMP} renewal."
        ),
        "discipline": "communication",
        "source_kind": "generated_voice_curriculum",
        "material_version": f"engel_chat_voice_generated_{STAMP}",
        "observed_rows": 8,
        "observed_counts": {d["weakness_key"]: 1 for d in DRAFTS},
        "card_count": len(cards),
        "cards": cards,
        "dropped": [],
    }


def main() -> int:
    proposal = build_proposal()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    PROPOSAL.write_text(json.dumps(proposal, indent=2), encoding="utf-8")
    approval = curriculum_adoption.required_approval("communication", proposal)
    print(
        json.dumps(
            {
                "ok": True,
                "card_count": proposal["card_count"],
                "material_version": proposal["material_version"],
                "required_adoption_approval": approval,
                "topics": [c["topic"] for c in proposal["cards"]],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
