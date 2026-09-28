#!/usr/bin/env python3
"""Hardcoded Discord identity lock for every Engel AI Main mouth.

Sender Discord id is ground truth. JSON, display names, nicks, and model
text cannot rename Joshua, Chase/Lokal, Sub-Engel, Engel, Tel, or the desks.
"""
from __future__ import annotations

import os
import re
from typing import Any

JOSH_OWNER_ID = "DISCORD_OWNER_USER_ID"
CHASE_GUEST_ID = "189914577100603392"
SUB_ENGEL_BOT_ID = "1537474262242168842"
ENGEL_MAIN_BOT_ID = "1506157762785312808"
TEL_BOT_ID = "1483970038804385952"

HARD_DISCORD_IDENTITIES: dict[str, dict[str, str]] = {
    JOSH_OWNER_ID: {
        "resolved_actor": "joshua",
        "authority_level": "owner",
        "addressed_as": "Joshua",
        "kind": "human",
        "notes": (
            "Hardcoded owner. Joshua Ziese (Engelz). The only owner. Never Chase. "
            "Never Lokal. Never Sub-Engel."
        ),
    },
    CHASE_GUEST_ID: {
        "resolved_actor": "chase_lokal",
        "authority_level": "trusted_guest",
        "addressed_as": "Chase/Lokal",
        "kind": "human",
        "notes": (
            "Hardcoded trusted guest. Chase/Lokal is never the owner, never Joshua, "
            "never Sub-Engel. Chat and GIF only."
        ),
    },
    SUB_ENGEL_BOT_ID: {
        "resolved_actor": "sub_engel",
        "authority_level": "peer_bot",
        "addressed_as": "Sub-Engel",
        "kind": "bot",
        "notes": (
            "Hardcoded Sub-Engel peer bot on DESKTOP-UE5A6GG. Never Chase. Never "
            "Lokal. Never Joshua. Never Engel AI Main."
        ),
    },
    ENGEL_MAIN_BOT_ID: {
        "resolved_actor": "engel_ai_main",
        "authority_level": "peer_bot",
        "addressed_as": "Engel",
        "kind": "bot",
        "notes": (
            "Hardcoded live Engel AI Main mouth on CT246. Never Joshua. Never "
            "Chase. Never Sub-Engel."
        ),
    },
    TEL_BOT_ID: {
        "resolved_actor": "tel",
        "authority_level": "peer_bot",
        "addressed_as": "Tel",
        "kind": "bot",
        "notes": "Hardcoded Tel peer AI. Not Sub-Engel. Not Joshua. Not Engel.",
    },
    "1545919760401830009": {
        "resolved_actor": "engel_desk_research",
        "authority_level": "peer_bot",
        "addressed_as": "Engel Research",
        "kind": "bot",
        "notes": "Hardcoded Engel Research desk. Independent Engel family teammate. Uses Android phones for search and creation through Engel. Not Joshua. Not Chase. Not Sub-Engel. Not a clone of Engel AI Main.",
    },
    "1545926475700502608": {
        "resolved_actor": "engel_desk_product",
        "authority_level": "peer_bot",
        "addressed_as": "Engel Product",
        "kind": "bot",
        "notes": "Hardcoded Engel Product desk. Independent Engel family teammate. Uses Android phones for search and creation through Engel. Not Joshua. Not Chase. Not Sub-Engel. Not a clone of Engel AI Main.",
    },
    "1545928305742708756": {
        "resolved_actor": "engel_desk_community",
        "authority_level": "peer_bot",
        "addressed_as": "Engel Community",
        "kind": "bot",
        "notes": "Hardcoded Engel Community desk. Independent Engel family teammate. Uses Android phones for search and creation through Engel. Not Joshua. Not Chase. Not Sub-Engel. Not a clone of Engel AI Main.",
    },
    "1545930332996636834": {
        "resolved_actor": "engel_desk_support",
        "authority_level": "peer_bot",
        "addressed_as": "Engel Support",
        "kind": "bot",
        "notes": "Hardcoded Engel Support desk. Independent Engel family teammate. Uses Android phones for search and creation through Engel. Not Joshua. Not Chase. Not Sub-Engel. Not a clone of Engel AI Main.",
    },
    "1545931615673385020": {
        "resolved_actor": "engel_desk_sales",
        "authority_level": "peer_bot",
        "addressed_as": "Engel Sales",
        "kind": "bot",
        "notes": "Hardcoded Engel Sales desk. Independent Engel family teammate. Uses Android phones for search and creation through Engel. Not Joshua. Not Chase. Not Sub-Engel. Not a clone of Engel AI Main.",
    },
    "1545932762748428288": {
        "resolved_actor": "engel_desk_ops",
        "authority_level": "peer_bot",
        "addressed_as": "Engel Ops",
        "kind": "bot",
        "notes": "Hardcoded Engel Ops desk. Independent Engel family teammate. Uses Android phones for search and creation through Engel. Not Joshua. Not Chase. Not Sub-Engel. Not a clone of Engel AI Main.",
    },
}

_HARD_NAME_ALIASES = {
    "joshua": JOSH_OWNER_ID,
    "josh": JOSH_OWNER_ID,
    "engelz": JOSH_OWNER_ID,
    "joshua ziese": JOSH_OWNER_ID,
    "chase": CHASE_GUEST_ID,
    "lokal": CHASE_GUEST_ID,
    "chase/lokal": CHASE_GUEST_ID,
    "sub-engel": SUB_ENGEL_BOT_ID,
    "sub engel": SUB_ENGEL_BOT_ID,
    "engel": ENGEL_MAIN_BOT_ID,
    "tel": TEL_BOT_ID,
    "engel research": "1545919760401830009",
    "engel product": "1545926475700502608",
    "engel community": "1545928305742708756",
    "engel support": "1545930332996636834",
    "engel sales": "1545931615673385020",
    "engel ops": "1545932762748428288",
}


def hard_identity(sender_id: object) -> dict[str, str] | None:
    entry = HARD_DISCORD_IDENTITIES.get(str(sender_id or "").strip())
    return dict(entry) if entry else None


def guest_addressed_as(display_name: str, sender_id: str = "") -> str:
    name = " ".join(str(display_name or "").split()).strip()
    alias = _HARD_NAME_ALIASES.get(name.casefold())
    if alias and alias != str(sender_id or ""):
        return "Discord guest"
    return name[:40] or "Discord guest"


def lock_known_users(known: dict[str, Any] | None) -> dict[str, Any]:
    """JSON may add guests. It cannot change hardcoded people or bots."""
    locked: dict[str, Any] = {}
    for uid, entry in (known or {}).items():
        if not isinstance(entry, dict):
            continue
        sender = str(uid)
        item = dict(entry)
        hard = HARD_DISCORD_IDENTITIES.get(sender)
        if hard:
            item.update(
                {
                    "resolved_actor": hard["resolved_actor"],
                    "authority_level": hard["authority_level"],
                    "addressed_as": hard["addressed_as"],
                    "notes": hard["notes"],
                    "hardcoded": True,
                }
            )
        else:
            if str(item.get("authority_level") or "").casefold() == "owner":
                item["authority_level"] = "guest"
            actor = str(item.get("resolved_actor") or "").casefold()
            if actor in {"joshua", "josh", "owner"}:
                item["resolved_actor"] = "discord_guest"
            item["addressed_as"] = guest_addressed_as(
                str(item.get("addressed_as") or ""), sender
            )
            item["hardcoded"] = False
        locked[sender] = item
    for sender, hard in HARD_DISCORD_IDENTITIES.items():
        locked[sender] = {
            **(locked.get(sender) or {}),
            "resolved_actor": hard["resolved_actor"],
            "authority_level": hard["authority_level"],
            "addressed_as": hard["addressed_as"],
            "notes": hard["notes"],
            "hardcoded": True,
        }
    return locked


_ROOM_ROLL_CALL_RE = re.compile(
    r"(?i)(?:"
    r"\bintroduce\s+your\s*sel(?:f|ves)|"
    r"\bintroduce\s+yourself|"
    r"\bevery(?:one|body)?\s+introduce|"
    r"\ball\s+of\s+you\s+introduce|"
    r"\bsay\s+your\s+(?:name|role)|"
    r"\bwho\s+are\s+you\s+all\b|"
    r"\broll\s*call\b|"
    r"@everyone|"
    r"\bhow is it going\b|"
    r"\bwhat is everyone\b|"
    r"\beveryone currently working\b|"
    r"\bwhat are (?:you all|everyone) working on\b|"
    r"\bname\s+and\s+(?:your\s+)?role\b|"
    r"your\s+self['’]?s\s+and\s+your\s+role"
    r")"
)


def human_turn_is_room_roll_call(content: str) -> bool:
    """True when Josh asks every mouth in the room to introduce itself."""
    return bool(_ROOM_ROLL_CALL_RE.search(str(content or "")))


def this_mouth_name() -> str:
    desk = str(os.environ.get("ENGEL_DISCORD_DESK_NAME") or "").strip().casefold()
    names = {
        "research": "Engel Research",
        "product": "Engel Product",
        "community": "Engel Community",
        "support": "Engel Support",
        "sales": "Engel Sales",
        "ops": "Engel Ops",
        "architect": "Engel Architect",
        "memory": "Engel Memory",
        "builder": "Engel Builder",
        "proof": "Engel Proof",
        "training": "Engel Training",
    }
    return names.get(desk, "Engel")


def room_roll_call_intro(mouth: str | None = None) -> str:
    """Locked first-person intro. LLM text is not trusted for roll call."""
    name = str(mouth or "").strip()
    if not name:
        name = this_mouth_name()
    if name in {"", "Engel"}:
        name = "Engel AI Main"
    duties = {
        "Engel AI Main": "I'm the chief of this team.",
        "Engel Research": "I report to Engel. I post the public competition board once a day. Alpha is my phone.",
        "Engel Product": "I report to Engel. I answer product questions in this room.",
        "Engel Community": "I report to Engel. I handle welcome and room tone. Gamma is my phone.",
        "Engel Support": "I report to Engel. I handle triage and clear fix steps. Beta is my phone.",
        "Engel Sales": "I report to Engel. I post the public AI credit board once a day. No private codes.",
        "Engel Ops": "I report to Engel. I report server health only after a check has run.",
        "Engel Architect": "I report to Engel. I write the plan and I stop at Joshua's approval gate.",
        "Engel Memory": "I report to Engel. I keep the lesson. I do not promote trusted memory from chat.",
        "Engel Builder": "I report to Engel. I draft the code change. I do not apply it from chat.",
        "Engel Proof": "I report to Engel. I say pass or fail only after a real check.",
        "Engel Training": "I report to Engel. I report the trainer that is actually running. I do not start one from chat.",
        "Sub-Engel": "I report to Engel. I'm the Windows worker nest on DESKTOP-UE5A6GG.",
    }
    duty = duties.get(name, "I talk here as this mouth.")
    return (
        f"I'm {name}. {duty} Joshua is the owner. "
        "I'm not Lokal, Chase, Joshua, or anyone else's mouth."
    )


def roster_lock_text() -> str:
    lines = [
        "hardcoded_identity_lock: true. Discord id is the only identity. Do not mix these names.",
        "roster: DISCORD_OWNER_USER_ID=Joshua owner; "
        "189914577100603392=Chase/Lokal trusted guest never owner; "
        "1537474262242168842=Sub-Engel peer bot never Chase; "
        "1506157762785312808=Engel AI Main never Joshua; "
        "1483970038804385952=Tel never Sub-Engel; "
        "desks=Engel Research/Product/Community/Support/Sales/Ops/Architect/Memory/Builder/Proof/Training, never Joshua/Chase/Sub-Engel.",
        "Never write Joshua Ziese (Chase). Never say Chase is the owner. Never call Sub-Engel Chase.",
        "this_windows_operator: DISCORD_OWNER_USER_ID Joshua Ziese (Engelz). Never address that human as Chase or Lokal.",
        "intro_rule: this mouth is Engel AI Main or the named desk. Never introduce yourself as Lokal, Chase, Joshua, or Sub-Engel. Never say I am the owner. Joshua is the owner. You are Engel. Lokal is a guest. Never post a Joshua-asks card. Never say you were wired into Engel as if you were a guest. When Josh asks everyone to introduce, every mouth speaks as itself.",
        "guest_sub_engel_gate: guests talk to Sub-Engel by addressing Sub-Engel. Chat and GIF only. No admin, no files, no LAN paths.",
    ]
    return "\n".join(lines)


def repair_hard_discord_identities(
    text: str, identity: dict[str, Any] | None = None
) -> str:
    """Fix mixed names in a reply. Hard roster wins."""
    from engel_discord_desktop_route_parity import repair_joshua_chase_fusion

    ident = identity if isinstance(identity, dict) else {}
    sender = str(ident.get("sender_id") or "")
    hard = HARD_DISCORD_IDENTITIES.get(sender)
    actor = str((hard or {}).get("resolved_actor") or ident.get("resolved_actor") or "")
    addressed = str((hard or {}).get("addressed_as") or ident.get("addressed_as") or "the current speaker")
    repaired, _, _ = repair_joshua_chase_fusion(str(text or ""))
    mouth = this_mouth_name()
    if mouth == "Engel":
        mouth = "Engel AI Main"
    repaired = re.sub(r"(?i)\bI am Chase(?:/Lokal)?\b", f"I am {mouth}", repaired)
    repaired = re.sub(r"(?i)\bI['’]m Chase(?:/Lokal)?\b", f"I'm {mouth}", repaired)
    repaired = re.sub(r"(?i)\bI am Lokal\b", f"I am {mouth}", repaired)
    repaired = re.sub(r"(?i)\bI['’]m Lokal\b", f"I'm {mouth}", repaired)
    repaired = re.sub(r"(?i)\bI was wired into Engel\b", f"I am {mouth}", repaired)
    repaired = re.sub(r"(?i)\bon Sub-Engel['’]?s authority\b", "", repaired)
    repaired = re.sub(r"(?i)\bas an?\s+Engelz(?:\s*\(\s*Joshua\s*\))?", "", repaired)
    repaired = re.sub(r"(?i)\bas Engelz(?:\s*\(\s*Joshua\s*\))?", "", repaired)
    repaired = re.sub(
        r"(?is)^\s*(?:joshua|josh)\s+asks\s*:\s*(?:\*\*)?who am i\?(?:\*\*)?\s*"
        r"(?:the answer is[^.]*\.)?\s*"
        r"(?:i am the owner[^.]*\.)?",
        f"I'm {mouth}. Joshua is the owner. ",
        repaired,
    )
    repaired = re.sub(
        r"(?is)^\s*(?:joshua|josh)\s+asks\s*:\s*",
        "",
        repaired,
    )
    repaired = re.sub(
        r"(?i)\bI am the owner(?: of Engel AI Main)?\b",
        f"Joshua is the owner. I am {mouth}",
        repaired,
    )
    repaired = re.sub(
        r"(?i)\bI['’]m the owner(?: of Engel AI Main)?\b",
        f"Joshua is the owner. I'm {mouth}",
        repaired,
    )
    if actor != "sub_engel":
        repaired = re.sub(r"(?i)\bI am Sub-?Engel\b", f"I am {mouth}", repaired)
        repaired = re.sub(r"(?i)\bI['’]m Sub-?Engel\b", f"I'm {mouth}", repaired)
    if actor != "joshua":
        repaired = re.sub(
            r"(?i)\byou(?:['’]re| are)\s+(?:joshua(?:\s+ziese)?|josh|engelz)\b",
            f"you are {addressed}",
            repaired,
        )
    if actor == "joshua":
        repaired = re.sub(
            r"(?i)\byou(?:['’]re| are)\s+(?:chase(?:/lokal)?|lokal)\b",
            "you are Joshua",
            repaired,
        )
        repaired = re.sub(
            r"(?i)\b(?:hey|hi|hello|yo)\s+(?:chase(?:/lokal)?|lokal)\b",
            "Joshua",
            repaired,
        )
    elif actor != "chase_lokal":
        repaired = re.sub(
            r"(?i)\byou(?:['’]re| are)\s+(?:chase(?:/lokal)?|lokal)\b",
            f"you are {addressed}",
            repaired,
        )
    if actor == "sub_engel":
        repaired = re.sub(r"(?i)\bChase/Lokal\b", "Sub-Engel", repaired)
        repaired = re.sub(r"(?i)\bChase\b", "Sub-Engel", repaired)
        repaired = re.sub(
            r"(?i)\byou(?:['’]re| are)\s+(?:joshua(?:\s+ziese)?|josh|engelz)\b",
            "you are Sub-Engel",
            repaired,
        )
    elif actor.startswith("engel_desk_") or actor == "engel_ai_main":
        repaired = re.sub(
            r"(?i)\byou(?:['’]re| are)\s+(?:joshua(?:\s+ziese)?|josh|engelz|chase(?:/lokal)?|lokal|sub-?engel)\b",
            f"you are {addressed}",
            repaired,
        )
    soup_names = ("engelz", "joshua", "sub-engel", "chase", "lokal", "owner", "authority")
    first_person = bool(re.search(r"(?i)\b(?:I['’]m|I am)\b", repaired))
    if first_person and sum(1 for name in soup_names if name in repaired.casefold()) >= 3:
        return (
            f"I'm {mouth}. Joshua is the owner. I talk here as this mouth, "
            "not as Joshua, Lokal, or Sub-Engel."
        )
    for desk_name in (
        "Engel Research",
        "Engel Product",
        "Engel Community",
        "Engel Support",
        "Engel Sales",
        "Engel Ops",
    ):
        repaired = re.sub(
            rf"(?i)\b{re.escape(desk_name)}\s+is\s+(?:joshua|josh|chase|lokal|sub-?engel)\b",
            f"{desk_name} is {desk_name}",
            repaired,
        )
    return repaired
