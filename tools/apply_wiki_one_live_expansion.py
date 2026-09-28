#!/usr/bin/env python3
"""Mark Engel AI Main organs ALIVE and add missing Cosmic Swarm desks."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engel_wiki_one import load_catalog, save_catalog, write_one_markdown  # noqa: E402

NEW_ORGANS = [
    {
        "id": "chat_runtime",
        "name": "Chat",
        "cluster": "cosmic_swarm",
        "home": "windows",
        "universe": "live",
        "life": "alive",
        "does": "Cosmic Swarm Chat / Ask Engel. Operator console to standing brain, Gemini lane, and local intercepts (wiki one, meeting room).",
        "talks_to": ["cosmic_swarm", "chat_llm", "humanization_slm", "persistent_link", "wiki_one", "governor"],
        "sources": ["engel_flutter_main/lib/main.dart"],
        "hits": "What Josh asks Engel in Cosmic Swarm Chat.",
        "does_not_hit": "Does not host model weights. Live 7B stays on CT246.",
    },
    {
        "id": "notes_colony",
        "name": "Notes",
        "cluster": "cosmic_swarm",
        "home": "windows",
        "universe": "live",
        "life": "alive",
        "does": "Cosmic Swarm Notes tab. Working notes under memory/notes. Not Wiki One and not trusted memory.",
        "talks_to": ["cosmic_swarm", "wiki_one", "memory_colonies"],
        "sources": ["engel_flutter_main/lib/main.dart", "memory/notes"],
        "hits": "Scratch notes and reminders.",
        "does_not_hit": "Does not replace Wiki One. Does not write trusted memory.",
    },
    {
        "id": "tasks_desk",
        "name": "Tasks",
        "cluster": "cosmic_swarm",
        "home": "windows",
        "universe": "live",
        "life": "alive",
        "does": "Cosmic Swarm Tasks: Meeting Room orders, worker tasks, Sub-Engel work, build/proof tasks.",
        "talks_to": ["cosmic_swarm", "meeting_room", "sub_engel", "android_limbs", "proof_desk"],
        "sources": ["engel_flutter_main/lib/main.dart"],
        "hits": "Task drafts and send-to-room flow.",
        "does_not_hit": "Does not start extra background workers.",
    },
    {
        "id": "models_desk",
        "name": "Models",
        "cluster": "cosmic_swarm",
        "home": "windows",
        "universe": "live",
        "life": "alive",
        "does": "Cosmic Swarm Models tab: local LLM status, model picker, runtime path. Default model home remains CT246.",
        "talks_to": ["cosmic_swarm", "chat_llm", "ct246_body", "local_gpu_helper"],
        "sources": ["engel_flutter_main/lib/main.dart"],
        "hits": "Which model Chat shows as selected.",
        "does_not_hit": "Does not download models. Does not make ROG the model home.",
    },
    {
        "id": "training_desk",
        "name": "Training",
        "cluster": "cosmic_swarm",
        "home": "windows",
        "universe": "live",
        "life": "alive",
        "does": "Cosmic Swarm Training plus AI Terms, RAG Lab, and Agent Loops tabs.",
        "talks_to": ["cosmic_swarm", "chat_llm", "governor", "verifiers"],
        "sources": ["engel_flutter_main/lib/main.dart", "engel_flutter_main/lib/training_section.dart"],
        "hits": "Training UI and RAG/terms surfaces.",
        "does_not_hit": "Does not launch unbounded training without Josh budget.",
    },
    {
        "id": "settings_desk",
        "name": "Settings",
        "cluster": "cosmic_swarm",
        "home": "windows",
        "universe": "live",
        "life": "alive",
        "does": "Cosmic Swarm Settings: appearance, accounts, profiles, gates.",
        "talks_to": ["cosmic_swarm", "guardian", "chat_runtime"],
        "sources": ["engel_flutter_main/lib/main.dart"],
        "hits": "How Cosmic Swarm looks and which account Chat uses.",
        "does_not_hit": "Does not store secrets in Wiki One.",
    },
    {
        "id": "devices_desk",
        "name": "Devices",
        "cluster": "cosmic_swarm",
        "home": "windows",
        "universe": "live",
        "life": "alive",
        "does": "Cosmic Swarm Devices: phone/Sub-Engel readiness, Swarm 3D, Nmap recon, Connection Help, worker dispatch.",
        "talks_to": ["cosmic_swarm", "eyes", "adb_hands", "android_limbs", "sub_engel", "meeting_room"],
        "sources": ["engel_flutter_main/lib/main.dart", "engel_flutter_main/lib/device_status.dart"],
        "hits": "Live device counts Josh sees on Home.",
        "does_not_hit": "Observation is not a new worker start.",
    },
    {
        "id": "system_desk",
        "name": "System",
        "cluster": "cosmic_swarm",
        "home": "windows",
        "universe": "live",
        "life": "alive",
        "does": "Cosmic Swarm System / Command Center: intent bridge, launch center, connection status.",
        "talks_to": ["cosmic_swarm", "persistent_link", "governor", "proof_desk"],
        "sources": ["engel_flutter_main/lib/main.dart"],
        "hits": "System/Command Center pages.",
        "does_not_hit": "Does not add startup autorun.",
    },
    {
        "id": "proof_desk",
        "name": "Proof",
        "cluster": "cosmic_swarm",
        "home": "windows",
        "universe": "live",
        "life": "alive",
        "does": "Cosmic Swarm Proof tab: hashes, screenshots, verifier output Josh can see.",
        "talks_to": ["cosmic_swarm", "verifiers", "wiki_one"],
        "sources": ["engel_flutter_main/lib/main.dart", "reports/codex_bridge"],
        "hits": "Visible proof of work.",
        "does_not_hit": "A screenshot is not a verifier pass by itself.",
    },
    {
        "id": "agents_desk",
        "name": "Agents",
        "cluster": "cosmic_swarm",
        "home": "windows",
        "universe": "live",
        "life": "alive",
        "does": "Cosmic Swarm Agents: roster, tool library, skills, messaging.",
        "talks_to": ["cosmic_swarm", "skills", "agent_kernel", "meeting_room"],
        "sources": ["engel_flutter_main/lib/main.dart"],
        "hits": "Which agents appear in Cosmic Swarm.",
        "does_not_hit": "Does not grant Level 2 autonomy.",
    },
    {
        "id": "goals_desk",
        "name": "Goals",
        "cluster": "cosmic_swarm",
        "home": "windows",
        "universe": "live",
        "life": "alive",
        "does": "Cosmic Swarm Goals: meters, month planner, projected finish.",
        "talks_to": ["cosmic_swarm", "architect", "tasks_desk"],
        "sources": ["engel_flutter_main/lib/main.dart"],
        "hits": "Goal meters Josh sees.",
        "does_not_hit": "Goals do not auto-apply CODE.",
    },
    {
        "id": "memory_guard_desk",
        "name": "Memory guard",
        "cluster": "cosmic_swarm",
        "home": "windows",
        "universe": "live",
        "life": "alive",
        "does": "Cosmic Swarm Memory page: guard rails over memory colonies. Trusted writes stay blocked.",
        "talks_to": ["cosmic_swarm", "memory_colonies", "guardian", "reps"],
        "sources": ["engel_flutter_main/lib/main.dart"],
        "hits": "Memory-guard UI.",
        "does_not_hit": "Does not write trusted memory or ALIVE_STATE.",
    },
    {
        "id": "build_desk",
        "name": "Build",
        "cluster": "cosmic_swarm",
        "home": "windows",
        "universe": "live",
        "life": "alive",
        "does": "Cosmic Swarm Build: pipeline, terminal/files, sandbox, artifacts, code languages.",
        "talks_to": ["cosmic_swarm", "packaging", "python_runtime", "verifiers"],
        "sources": ["engel_flutter_main/lib/main.dart"],
        "hits": "Build/workspace pages.",
        "does_not_hit": "Does not silently promote dist/ artifacts.",
    },
    {
        "id": "chat_llm",
        "name": "Live chat LLM",
        "cluster": "brain",
        "home": "ct246",
        "universe": "live",
        "life": "alive",
        "does": "CT246 live chat brain: Qwen2.5-7B GGUF + LoRA on /opt/engel, reached at 127.0.0.1:24680 through the persistent link.",
        "talks_to": ["ct246_body", "persistent_link", "chat_runtime", "humanization_slm", "governor"],
        "sources": ["scripts/Start-EngelMainOneSystem.ps1", "tools/engel_main_server_chat_http_service.py"],
        "hits": "Spoken Engel replies in Chat.",
        "does_not_hit": "Does not live on this laptop disk by default.",
    },
    {
        "id": "humanization_slm",
        "name": "Humanization SLM",
        "cluster": "brain",
        "home": "ct246",
        "universe": "live",
        "life": "alive",
        "does": "Rewrites chat-LLM drafts into first-person spoken replies. Communication lane, not live 7B.",
        "talks_to": ["chat_llm", "chat_runtime", "ct246_body"],
        "sources": [".agents/skills/engel-chat-humanization-slm/SKILL.md"],
        "hits": "How Chat sounds.",
        "does_not_hit": "Fail-open: a miss does not block Chat.",
    },
    {
        "id": "governor",
        "name": "Governor",
        "cluster": "brain",
        "home": "windows",
        "universe": "live",
        "life": "alive",
        "does": "Decision plane and lane routing: operator work vs chat, Discord jobs, reasoning lanes. Below Josh and Guardian.",
        "talks_to": ["guardian", "chat_runtime", "chat_llm", "system_desk"],
        "sources": ["docs/ENGEL_GOVERNOR_DESIGN.md", "tools/verify_engel_governor.py"],
        "hits": "Which lane a prompt takes.",
        "does_not_hit": "Does not outrank Josh or Guardian.",
    },
]


def main() -> int:
    catalog = load_catalog()
    catalog["title"] = "Wiki One — Engel AI Main canonical second brain"
    catalog["role"] = "Engel AI Main is LIVE. Cosmic Swarm OS is the face. CT246 is the runtime body."
    catalog["life"] = "alive"
    catalog["status"] = "LIVE"
    organs = [item for item in catalog.get("organs", []) if isinstance(item, dict)]
    by_id = {str(item.get("id")): item for item in organs}
    for item in organs:
        item["life"] = "alive"
        if str(item.get("universe") or "") != "ghost":
            item["universe"] = "live"
    swarm = by_id.get("cosmic_swarm")
    extra_talks = [
        "chat_runtime",
        "notes_colony",
        "tasks_desk",
        "models_desk",
        "training_desk",
        "settings_desk",
        "devices_desk",
        "system_desk",
        "proof_desk",
        "agents_desk",
        "goals_desk",
        "memory_guard_desk",
        "build_desk",
        "wiki_one",
        "meeting_room",
        "persistent_link",
        "chat_llm",
    ]
    if swarm:
        talks = [str(x) for x in (swarm.get("talks_to") or [])]
        for oid in extra_talks:
            if oid not in talks:
                talks.append(oid)
        swarm["talks_to"] = talks
        swarm["does"] = (
            "EngelAIMain.exe Cosmic Swarm OS — LIVE Home, Chat, Notes, Wiki, Tasks, Models, "
            "Training, Settings, Devices, System, Proof, Agents, Goals. Hosts Wiki One as the canonical second brain."
        )
    added = []
    for item in NEW_ORGANS:
        oid = str(item["id"])
        if oid in by_id:
            continue
        organs.append(item)
        by_id[oid] = item
        added.append(oid)
    catalog["organs"] = organs
    save_catalog(catalog)
    write_one_markdown(catalog)
    print("organs=" + str(len(organs)))
    print("added=" + ",".join(added) if added else "added=")
    print("wrote wiki/ONE.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
