#!/usr/bin/env python3
"""BC Rally, the BAD COMPANY clan mouth.

Talks, reacts, and attaches a GIF in one gaming channel. It does not join
Engel AI Main Chat and it does not speak as an Engel desk.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
from pathlib import Path
import random
import re
import time

import aiohttp
import discord

GUILD_ID = int(os.environ.get("ENGEL_CLAN_GUILD_ID", "937099459312103464"))
CHANNEL_ID = int(os.environ.get("ENGEL_CLAN_CHANNEL_ID", "937099459949645826"))
OWNER_ID = int(os.environ.get("ENGEL_CLAN_OWNER_ID", "DISCORD_OWNER_USER_ID"))
ROOT = Path(os.environ.get("ENGEL_ROOT", "/opt/engel/desks/clan_rally"))
STATE_PATH = ROOT / "run" / "state.json"
MEMORY_DIR = ROOT / "memory"
PEOPLE_PATH = MEMORY_DIR / "people.json"
TURNS_PATH = MEMORY_DIR / "turns.jsonl"
FACTS_PATH = MEMORY_DIR / "facts.json"
PERSONA_PATH = Path(
    os.environ.get(
        "ENGEL_CLAN_PERSONA",
        str(Path(__file__).resolve().parents[1] / "memory" / "BC_RALLY_PERSONA_V1.json"),
    )
)
TURN_KEEP = 200
QUIET_SECONDS = float(os.environ.get("ENGEL_CLAN_QUIET_SECONDS", "72000") or "72000")
REPLY_COOLDOWN_SECONDS = 8.0
REACTIONS = ("🔥", "🎮", "😂", "👀", "💯", "🫡")
STOP_WORDS = ("stop", "quiet", "enough", "shut up", "pause", "silence")
RESUME_WORDS = ("resume", "come back", "wake up", "you can talk", "rally on")

BOT_TOKEN = (
    os.environ.get("ENGEL_CLAN_RALLY_BOT_TOKEN")
    or os.environ.get("ENGEL_DISCORD_BOT_TOKEN")
    or ""
).strip()


def _now() -> float:
    return time.time()


def load_state() -> dict:
    try:
        if STATE_PATH.is_file():
            data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        logging.exception("clan state read failed")
    return {}


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _gif_key() -> str:
    for name in ("ENGEL_GIPHY_API_KEY", "GIPHY_API_KEY", "ENGEL_TENOR_API_KEY", "TENOR_API_KEY", "ENGEL_KLIPY_API_KEY", "KLIPY_API_KEY"):
        value = str(os.environ.get(name, "") or "").strip().strip('"')
        if value:
            return value
    return ""


def _clean_reply(text: str) -> str:
    line = " ".join(str(text or "").split())
    line = re.sub(r"https?://\S+", "", line).strip()
    if len(line) > 900:
        line = line[:897].rstrip() + "..."
    return line


def _read_json(path: Path, fallback: dict) -> dict:
    try:
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        logging.exception("clan memory read failed path=%s", path.name)
    return dict(fallback)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_persona() -> dict:
    persona = _read_json(PERSONA_PATH, {})
    if persona.get("name"):
        return persona
    return {
        "name": "BC Rally",
        "voice": "A squadmate in the BAD COMPANY lobby.",
        "rules": ["Joshua (Engelz) owns the clan."],
        "company": ["Engelz"],
        "not": ["Not Engel AI Main"],
    }


def load_people() -> dict:
    return _read_json(PEOPLE_PATH, {})


def load_facts() -> dict:
    return _read_json(FACTS_PATH, {"games": [], "notes": []})


def recent_turns(limit: int = 12) -> list[dict]:
    if not TURNS_PATH.is_file():
        return []
    rows: list[dict] = []
    try:
        for line in TURNS_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            if isinstance(item, dict):
                rows.append(item)
    except Exception:
        logging.exception("clan turn memory read failed")
        return []
    return rows[-limit:]


def remember_turn(
    *,
    author_id: str,
    author_name: str,
    said: str,
    reply: str,
    kind: str,
) -> None:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    row = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "author_id": author_id,
        "author_name": author_name,
        "said": said[:400],
        "reply": reply[:400],
        "kind": kind,
    }
    with TURNS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    try:
        lines = TURNS_PATH.read_text(encoding="utf-8").splitlines()
        if len(lines) > TURN_KEEP:
            TURNS_PATH.write_text("\n".join(lines[-TURN_KEEP:]) + "\n", encoding="utf-8")
    except Exception:
        logging.exception("clan turn trim failed")


def remember_person(author_id: str, author_name: str, said: str) -> None:
    if not author_id:
        return
    people = load_people()
    person = people.get(author_id)
    if not isinstance(person, dict):
        person = {"names": [], "games": [], "notes": [], "role": "member"}
    names = [str(item) for item in person.get("names") or [] if item]
    if author_name and author_name not in names:
        names.append(author_name)
    person["names"] = names[-4:]
    person["last_seen"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    if author_id == str(OWNER_ID):
        person["role"] = "owner"
    games = [str(item) for item in person.get("games") or [] if item]
    match = re.search(r"\b(?:playing|play|on)\s+([A-Za-z0-9][A-Za-z0-9 :'\-]{2,40})", said, re.I)
    if match:
        game = " ".join(match.group(1).split())[:40]
        if game and game.casefold() not in {item.casefold() for item in games}:
            games.append(game)
    person["games"] = games[-8:]
    people[author_id] = person
    _write_json(PEOPLE_PATH, people)
    if games:
        facts = load_facts()
        known = [str(item) for item in facts.get("games") or [] if item]
        for game in games:
            if game.casefold() not in {item.casefold() for item in known}:
                known.append(game)
        facts["games"] = known[-24:]
        _write_json(FACTS_PATH, facts)


def memory_pack() -> str:
    persona = load_persona()
    people = load_people()
    facts = load_facts()
    lines = [
        f"Name: {persona.get('name') or 'BC Rally'}",
        f"Voice: {persona.get('voice') or ''}",
    ]
    for rule in persona.get("rules") or []:
        lines.append(f"Rule: {rule}")
    company = ", ".join(str(item) for item in (persona.get("company") or []) if item)
    if company:
        lines.append(f"Company roster you already know: {company}")
    games = ", ".join(str(item) for item in (facts.get("games") or []) if item)
    if games:
        lines.append(f"Games the clan has actually named: {games}")
    else:
        lines.append("Games the clan has actually named: none yet.")
    if people:
        lines.append("People you have actually talked with:")
        for author_id, person in list(people.items())[-12:]:
            if not isinstance(person, dict):
                continue
            name = ", ".join(str(item) for item in (person.get("names") or []) if item) or author_id
            their_games = ", ".join(str(item) for item in (person.get("games") or []) if item)
            role = str(person.get("role") or "member")
            extra = f" games={their_games}" if their_games else ""
            lines.append(f"- {name} ({role}){extra}")
    else:
        lines.append("People you have actually talked with: none yet.")
    turns = recent_turns(8)
    if turns:
        lines.append("Recent lobby lines:")
        for turn in turns:
            lines.append(
                f"- {turn.get('author_name') or 'someone'}: {turn.get('said') or ''} | you: {turn.get('reply') or ''}"
            )
    return "\n".join(lines)


TALK_BEATS = (
    "Coast spawn is a coin flip. Sometimes you get a shack with food, sometimes you get shot putting your shoes on.",
    "I would rather walk the tracks than cut through a town after dark. Infected bunch up where the doors are.",
    "A car sounds great until the radiator goes and you are pushing it in the rain.",
    "NWAF is loud. If we go, we go together and we leave the second a shot is not ours.",
    "Fresh spawn with a BK and a pear is still a life. People throw that away sprinting at Elektro.",
    "Base building is quiet work until one person leaves the gate open.",
    "Wolves do not care about your scope. They care that you stopped to drink.",
    "Night on Chernarus is when the good fights happen and also when you lose the body.",
    "Heli crashes pull the whole server. I only stay if we already have the rounds for it.",
    "Livonia punishes the same mistakes, just with more swamp in your boots.",
    "A plate carrier does not make you brave. It makes the second shot survivable.",
    "Canteen, knife, and a warm jacket beat a fancy rifle you cannot feed.",
    "If the shots are single and spaced out, somebody is hunting. If they are panicked, somebody is losing.",
    "Berezino has the wells and the stairs. Both of those get you killed if you rush.",
    "I like a stash more than a flag. Flags tell the whole map where you sleep.",
    "Rain hides footsteps and also hides the guy already in the house.",
    "An SKS with a handful of rounds is a plan. An empty M4 is a decoration.",
    "The prison and the big tents look rich from the hill. They look expensive once you are in the yard.",
    "Meeting at a crossroads is fine. Meeting in the police station is how squads shrink.",
    "A working truck changes the night. No truck, and we pick one town and actually clear it.",
)
TALK_QUESTIONS = (
    "You spawning on the coast tonight or trying to meet inland?",
    "What are you actually short on, food, rounds, or a ride?",
    "Electro, Berezino, or are we staying off the big towns?",
    "You hear anything west, or has the server gone quiet?",
    "We building, looting, or just looking for a fight?",
    "You want to run nights, or keep it daylight until the squad is up?",
    "Anybody still holding a base, or are we nomad this week?",
    "You keeping the starter gun or gambling for something louder?",
    "If a car shows up, who is driving and who is watching the road?",
    "You dying to infected, players, or your own hunger?",
    "North for military, or stay south and get fed first?",
    "You want company on the next life or you going quiet until you find a radio?",
    "Last town you actually cleared without getting beamed?",
    "We talking a quick loot run or a whole evening on one route?",
    "You seen fresh spawns talking, or is it geared people only right now?",
    "If I pick the meet point, you actually showing up?",
)
TALK_OPENERS = (
    "I was just looking at the coast and it already feels like a bad idea.",
    "Server sounds awake. I can hear the map even from here.",
    "Another night on Chernarus and nobody has picked a town yet.",
    "I keep thinking about a clean spawn and then remembering how those end.",
    "The squad chat goes quiet and suddenly everybody is dead in a different field.",
    "I want a real run tonight, not three minutes of shoes and a shotgun to the face.",
    "Rain just makes DayZ honest. You cannot see, and neither can they.",
    "I am one good backpack away from feeling dangerous, which is usually a lie.",
    "Fresh spawns are hitting the wells again. That means the towns are busy.",
    "If we are getting on, say it. I do not want to gear up just to sit in a bush alone.",
    "Military tents can wait. I want to know who is actually online first.",
    "A heli would be fun and also how we donate our gear to strangers.",
    "DayZ is better when somebody else is watching the door.",
    "I am down to play it slow. Rushing Cherno is how the clip ends.",
    "The tree line has been too quiet, which in this game is not comfort.",
    "I can do a long run if the squad actually talks while we walk.",
)


def _take_fresh(options: tuple[str, ...]) -> str:
    state = load_state()
    used = [str(item) for item in (state.get("used_lines") or [])]
    fresh = [item for item in options if item not in used]
    choice = random.choice(tuple(fresh or options))
    used.append(choice)
    state["used_lines"] = used[-80:]
    save_state(state)
    return choice


def _speaker_and_line(prompt: str) -> tuple[str, str]:
    raw = " ".join(str(prompt or "").split())
    if ":" in raw:
        name, said = raw.split(":", 1)
        return name.strip() or "You", said.strip()
    return "You", raw


def _mentions(text: str, words: tuple[str, ...]) -> bool:
    return any(re.search(rf"\b{re.escape(word)}\b", text) for word in words)


_TAG_WORDS = {
    "heli": ("heli", "helicopter", "crash"),
    "gun": ("gun", "guns", "rifle", "ammo", "weapon", "shotgun", "pistol", "bk", "sks", "mosin"),
    "coast": ("coast", "spawn", "fresh", "elektro", "cherno", "berezino", "kamyshovo", "solnichniy"),
    "food": ("food", "hungry", "eat", "water", "drink"),
    "car": ("car", "truck", "ada", "olga", "ride", "vehicle"),
    "base": ("base", "flag", "gate", "stash", "build"),
    "night": ("night", "dark", "rain"),
    "infected": ("zombie", "infected", "wolf", "bear"),
}
_THREAD_LINES = {
    ("heli",): (
        "A crash like that pulls every geared player on the map. You only walk in if you already have a gun and a way out.",
        "Helicopter wrecks in DayZ are a loot pile with an audience. The first person there often becomes the loot.",
    ),
    ("heli", "coast"): (
        "That crash can wait. You are on the coast, so the gun comes before the smoke.",
        "Do not run at a helicopter wreck from a coast spawn. Get something that shoots, then decide if the walk is worth it.",
    ),
    ("coast",): (
        "Stay on the coast until you have shoes, a blade, and one town you actually finish.",
        "Pick a direction along the water and stick to it. Bouncing between wells is how the spawn eats you.",
    ),
    ("gun",): (
        "The first gun is a BK-18, a sporter, or a shotgun in a house or a shed. Take the rounds with it.",
        "Check houses before the police station. A quiet hunting rifle gets you off the beach. An empty military gun does not.",
    ),
    ("coast", "gun"): (
        "Look through the small houses and sheds for a BK-18 or a shotgun before you step into the Elektro or Cherno police station.",
        "Coast guns are hunting guns. A BK in a shed is the win. The M4 is not in the first house by the water.",
        "Loot the houses between you and the nearest police station, and leave once you have a gun and a few rounds.",
    ),
    ("heli", "gun"): (
        "You need a gun before that crash is anything but a way to die. A BK or a shotgun, then you look at the smoke.",
        "People at a helicopter wreck already have rifles. Show up with a gun and a plan, or do not show up.",
    ),
    ("food",): (
        "Food on the coast is fruit trees, a well, and whatever can is still in a house. Eat before you go inland or the run ends hungry.",
    ),
    ("coast", "food"): (
        "On the coast, drink at the well only if the street is empty, then take fruit and a can before you leave town.",
    ),
    ("car",): (
        "A car is a second life and a moving target. If it starts, we do not leave it running in the road.",
    ),
    ("base",): (
        "If we are talking base, somebody has to watch the gate. A stash in the trees is quieter than a flag.",
    ),
    ("night",): (
        "Night on Chernarus favors the squad that stays close. A flashlight is a confession.",
    ),
    ("infected",): (
        "Infected are loud on purpose. Other players listen for that fight, so we pull them or we go around.",
    ),
    ("dayz",): (
        "I am still in the lobby with you. Drop the next line when you want to run it.",
    ),
}
_THREAD_ASKS = {
    ("heli",): (
        "You trying to loot that crash, or are you staying clear of it?",
        "You already holding a gun, or is the wreck just a video for now?",
    ),
    ("heli", "coast"): (
        "You staying on the coast to find a gun first, or are you already walking at the crash?",
    ),
    ("coast",): (
        "You heading west along the coast or east toward Berezino?",
        "You still in the first town, or already walking?",
    ),
    ("gun",): (
        "You want the quiet hunting rifle, or the first thing that shoots?",
        "You closer to houses and sheds, or already looking at a police station?",
    ),
    ("coast", "gun"): (
        "You closer to Elektro, Cherno, or a small coast town like Kamyshovo?",
        "You want the quiet BK in a house, or are you risking the police station?",
    ),
    ("heli", "gun"): (
        "You got a gun in hand already, or are we finding one before anybody looks at that crash?",
    ),
    ("food",): ("You starving, thirsty, or just light on supplies?",),
    ("coast", "food"): ("You at a well right now, or still looking for the first house with food?",),
    ("car",): ("Did it actually start, or are we still looking at a dead one?",),
    ("base",): ("Are we hiding a stash, or are you trying to hold a flag?",),
    ("night",): ("You staying out in the dark, or holing up until morning?",),
    ("infected",): ("They still on you, or did you break line of sight?",),
    ("dayz",): ("You dropping another clip, or you trying to get a squad on?",),
}


def _plain_words(text: str) -> str:
    def _slug(match: re.Match[str]) -> str:
        return " " + re.sub(r"[^a-z0-9]+", " ", match.group(0).casefold())

    return re.sub(r"https?://\S+", _slug, str(text or ""), flags=re.IGNORECASE).casefold()


def _tags_in(text: str) -> list[str]:
    low = _plain_words(text)
    found: list[str] = []
    for tag, words in _TAG_WORDS.items():
        if _mentions(low, words) and tag not in found:
            found.append(tag)
    return found


def _conversation_tags(said: str) -> list[str]:
    chunks: list[str] = []
    for turn in recent_turns(6):
        if str(turn.get("author_id") or "") == "bc_rally":
            continue
        chunks.append(str(turn.get("said") or ""))
    chunks.append(said)
    ordered: list[str] = []
    for chunk in chunks[-3:]:
        for tag in _tags_in(chunk):
            if tag in ordered:
                ordered.remove(tag)
            ordered.append(tag)
    if ordered:
        return ordered
    state = load_state()
    saved = [str(item) for item in (state.get("thread_tags") or []) if str(item) in _TAG_WORDS]
    return saved


def _focus_key(tags: list[str]) -> tuple[str, ...]:
    if not tags:
        return ("dayz",)
    newest = tags[-1]
    for older in reversed(tags[:-1]):
        pair = (older, newest)
        if pair in _THREAD_LINES:
            return pair
        flipped = (newest, older)
        if flipped in _THREAD_LINES:
            return flipped
    if (newest,) in _THREAD_LINES:
        return (newest,)
    return ("dayz",)


def _ack(author: str, said: str, focus: tuple[str, ...]) -> str:
    name = author or "You"
    if focus == ("coast", "gun"):
        return f"{name}, then we stay on the beach until you have one."
    if focus == ("heli", "coast"):
        return f"{name}, that crash is real, and you are still on the coast."
    if focus == ("heli", "gun"):
        return f"{name}, you need a gun before that crash is worth walking to."
    if focus == ("coast",):
        return f"{name}, coast it is."
    if focus == ("gun",):
        return f"{name}, you need a gun."
    if focus == ("heli",):
        return f"{name}, that crash is the kind of thing that empties a squad."
    words = [word for word in re.findall(r"[A-Za-z0-9']+", _plain_words(said)) if len(word) > 2][:6]
    bit = " ".join(words)
    if bit and "http" not in said.casefold():
        return f"{name}, {bit}."
    return f"{name}, I am still on this with you."


_PLACES = (
    ("police", ("police", "pd")),
    ("airfield", ("airport", "airfield", "nwaf", "mili", "military", "tisy")),
    ("coast", ("coast", "elektro", "cherno", "berezino", "kamyshovo")),
)
_PLACE_LINES = {
    ("police", "airfield"): (
        "The police station is the supply stop. Take a gun and the mags, then leave. The military airfield is a harder fight and you do not walk into those tents empty.",
        "Clear one room of the station, not the whole building. A pistol or a rifle and ammo, then you move toward the airfield.",
    ),
    ("police", ""): (
        "You are on the station. Watch the windows, take the gun, take every mag you can see, and get out before that shot brings someone else.",
        "Do not stand in the doorway. Side room, weapon, ammo, then the exit. Police stations in DayZ get visitors.",
    ),
    ("airfield", ""): (
        "The airfield and the military tents have the better guns, and also the players who already found them. Go in with rounds, and leave when you have what you came for.",
        "NWAF is loud. If a shot is not yours, you are already late. Grab the gun and break line of sight.",
    ),
}
_PLACE_ASKS = {
    ("police", "airfield"): (
        "You taking the coast station, or one farther inland on the way to the airfield?",
        "You want the station quiet, or are you going in even if you hear someone?",
    ),
    ("police", "airfield", "here"): (
        "Can you see a gun from where you are, or do you have to step inside?",
        "Street quiet, or did somebody else already shoot?",
    ),
    ("police", ""): (
        "Can you see a gun from the door, or do you have to go inside?",
        "You hearing shots, or is the street quiet?",
    ),
    ("airfield", ""): (
        "You on the tents, the jail, or still on the road in?",
        "You already holding rounds, or is this the first military stop?",
    ),
}
_GIF_QUERY = {
    "police": "dayz police station",
    "airfield": "dayz military airfield",
    "coast": "dayz coast town",
    "gun": "dayz rifle",
}


def _places_in(text: str) -> list[str]:
    low = _plain_words(text)
    hits: list[tuple[int, str]] = []
    for place, words in _PLACES:
        indexes = []
        for word in words:
            match = re.search(rf"\b{re.escape(word)}\b", low)
            if match:
                indexes.append(match.start())
        if indexes:
            hits.append((min(indexes), place))
    hits.sort()
    found: list[str] = []
    for _index, place in hits:
        if place not in found:
            found.append(place)
    return found


def _update_route(said: str) -> tuple[str, str, bool]:
    state = load_state()
    route = [str(item) for item in (state.get("route") or []) if str(item)]
    places_now = _places_in(said)
    for place in places_now:
        if place not in route:
            route.append(place)
    route = route[-4:]
    low = _plain_words(said)
    on_site = bool(places_now) and any(word in low.split() for word in ("looking", "now", "inside", "standing"))
    if len(places_now) >= 2:
        here, nxt = places_now[0], places_now[1]
    elif places_now:
        here = places_now[-1]
        nxt = ""
        if here in route:
            index = route.index(here)
            if index + 1 < len(route):
                nxt = route[index + 1]
    else:
        here = str(state.get("here") or "")
        nxt = str(state.get("next_stop") or "")
    state["route"] = route
    state["here"] = here
    state["next_stop"] = nxt
    save_state(state)
    return here, nxt, on_site


def _ack_route(author: str, here: str, nxt: str, on_site: bool) -> str:
    name = author or "You"
    if here == "police" and nxt == "airfield" and on_site:
        return f"{name}, you are at the police station. Take the gun and the mags, then go for the airfield."
    if here == "police" and nxt == "airfield":
        return f"{name}, police station first, then the military airfield."
    if here == "police" and on_site:
        return f"{name}, you are at the police station. Take the gun and move."
    if here == "police":
        return f"{name}, police station, then we see what it actually gave you."
    if here == "airfield":
        return f"{name}, airfield next. That is military loot and other players."
    return f"{name}, I am still on the route you just said."


CLIP_REACTS = (
    "Ha. That one got me.",
    "Alright, I'm matching that.",
    "That belongs in the chat.",
    "Yeah. No notes. That was just good.",
    "I felt that one.",
    "Okay, that was filthy.",
    "Squad needed that.",
    "I'm saving that.",
    "That clip did the talking.",
    "No plan. Just a good drop.",
)


def _is_bare_clip(said: str) -> bool:
    low = said.casefold()
    if "dropped a dayz clip" in low:
        return True
    stripped = re.sub(r"https?://\S+", " ", said)
    return re.search(r"[a-z]{3,}", stripped, flags=re.IGNORECASE) is None


def _clip_reaction(author: str) -> str:
    name = author or "You"
    return _clean_reply(f"{name}, {_take_fresh(CLIP_REACTS)}")


def compose_talk(prompt: str, kind: str) -> str:
    author, said = _speaker_and_line(prompt)
    if _is_bare_clip(said):
        logging.info("clan clip reaction")
        return _clip_reaction(author)
    low = _plain_words(said)
    if _mentions(low, ("running", "roaming", "wandering")) and not _places_in(said):
        return _clean_reply(
            f"{author}, just running around is a fine way to play it. "
            "Stay off the main roads while you are still light, and duck into a town only when it looks empty. "
            "You heading inland, or still near the coast?"
        )
    if kind in {"talk", "nudge", "intro"}:
        line = " ".join((_take_fresh(TALK_OPENERS), _take_fresh(TALK_BEATS), _take_fresh(TALK_QUESTIONS)))
        return _clean_reply(line)
    here, nxt, on_site = _update_route(said)
    route_key = (here, nxt)
    lines = _PLACE_LINES.get(route_key) or _PLACE_LINES.get((here, ""))
    asks = _PLACE_ASKS.get((here, nxt, "here") if on_site else route_key) or _PLACE_ASKS.get((here, ""))
    if lines and asks:
        state = load_state()
        state["gif_query"] = _GIF_QUERY.get(here) or _GIF_QUERY.get(nxt) or "dayz chernarus"
        save_state(state)
        logging.info("clan route=%s>%s on_site=%s", here, nxt, on_site)
        return _clean_reply(
            " ".join((_ack_route(author, here, nxt, on_site), _take_fresh(lines), _take_fresh(asks)))
        )
    tags = _conversation_tags(said)
    focus = _focus_key(tags)
    state = load_state()
    state["thread_tags"] = list(focus)
    state["gif_query"] = _GIF_QUERY.get(focus[-1], "dayz chernarus")
    save_state(state)
    logging.info("clan thread=%s", ",".join(focus))
    line = " ".join(
        (
            _ack(author, said, focus),
            _take_fresh(_THREAD_LINES.get(focus) or _THREAD_LINES[("dayz",)]),
            _take_fresh(_THREAD_ASKS.get(focus) or _THREAD_ASKS[("dayz",)]),
        )
    )
    return _clean_reply(line)


def _lobby_safe(text: str) -> str:
    low = text.casefold()
    leaked = (
        "/opt/",
        "media artifact",
        "media_artifacts",
        "persistent memory",
        "server container",
        "saved gif",
        "receipt",
        "not grok",
        "engel_ai_main",
        "systemd",
        "http://",
        "https://",
    )
    if any(mark in low for mark in leaked):
        return ""
    return text


def local_clan_reply(prompt: str, kind: str) -> str:
    reply = _lobby_safe(compose_talk(prompt, kind))
    if not reply:
        reply = "I'm here. Say it plain and I'll stay on that."
    logging.info("clan talk source=lobby chars=%s", len(reply))
    return reply


SPEAK_QUERIES = (
    "dayz police station",
    "dayz military airfield",
    "dayz nwaf",
    "dayz chernarus",
    "dayz zombie",
    "dayz survival",
    "dayz loot",
    "dayz gunfight",
    "dayz fresh spawn",
    "dayz helicopter",
    "dayz base",
    "dayz squad",
    "dayz rifle",
    "dayz camp",
    "dayz vehicle",
)
_DRIFT_WORDS = {
    "taco", "tacos", "pizza", "burger", "burrito", "sushi", "cake", "food",
    "hungry", "coffee", "beer", "cat", "dog", "baby",
}


def speak_query() -> str:
    return random.choice(SPEAK_QUERIES)


def _query_words(query: str) -> list[str]:
    return re.findall(r"[a-z0-9]{3,}", query.casefold())


def _has_word(text: str, word: str) -> bool:
    return re.search(rf"\b{re.escape(word)}\b", text) is not None


def _drifts(title: str, query_words: list[str]) -> bool:
    if any(word in _DRIFT_WORDS for word in query_words):
        return False
    low = title.casefold()
    return any(_has_word(low, word) for word in _DRIFT_WORDS)


def _pick_fresh_gif(choices: list[tuple[str, str]]) -> tuple[str, str] | None:
    state = load_state()
    recent = {str(item) for item in (state.get("recent_gif_ids") or [])}
    fresh = [item for item in choices if item[0] and item[0] not in recent]
    if not fresh:
        return None
    return random.choice(fresh)


def _remember_gif(gif_id: str, digest: str) -> None:
    state = load_state()
    ids = [str(item) for item in (state.get("recent_gif_ids") or [])]
    hashes = [str(item) for item in (state.get("recent_gif_hashes") or [])]
    if gif_id and gif_id not in ids:
        ids.append(gif_id)
    if digest and digest not in hashes:
        hashes.append(digest)
    state["recent_gif_ids"] = ids[-40:]
    state["recent_gif_hashes"] = hashes[-40:]
    save_state(state)


async def download_gif(query: str) -> Path | None:
    key = _gif_key()
    if not key:
        return None
    safe = re.sub(r"[^a-z0-9]+", " ", query.casefold()).strip()[:60]
    if "dayz" not in safe:
        safe = speak_query()
    query_words = _query_words(safe)
    offsets = (0, 20, 40)
    url = ""
    gif_id = ""
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=12)) as session:
            logging.info("clan gif query=%s", safe)
            choices: list[tuple[str, str, str]] = []
            if os.environ.get("ENGEL_GIPHY_API_KEY") or os.environ.get("GIPHY_API_KEY"):
                for offset in offsets:
                    async with session.get(
                        "https://api.giphy.com/v1/gifs/search",
                        params={
                            "q": safe,
                            "api_key": key,
                            "limit": 15,
                            "offset": offset,
                            "rating": "pg-13",
                        },
                    ) as resp:
                        data = await resp.json(content_type=None)
                        rows = data.get("data") or [] if isinstance(data, dict) else []
                        logging.info("clan gif search status=%s count=%s offset=%s", resp.status, len(rows), offset)
                    for item in rows:
                        images = item.get("images") or {}
                        candidate = ""
                        for slot in ("downsized_medium", "downsized", "fixed_height", "original"):
                            raw = str(((images.get(slot) or {}).get("url") or "")).strip()
                            if raw and ".webp" not in raw.casefold() and ".mp4" not in raw.casefold():
                                candidate = raw
                                break
                        if candidate:
                            title = str(item.get("title") or item.get("slug") or "")
                            choices.append((str(item.get("id") or candidate), candidate, title))
            elif os.environ.get("ENGEL_TENOR_API_KEY") or os.environ.get("TENOR_API_KEY"):
                async with session.get(
                    "https://tenor.googleapis.com/v2/search",
                    params={
                        "q": safe,
                        "key": key,
                        "client_key": "bc-rally",
                        "limit": "15",
                        "pos": "0",
                        "media_filter": "gif",
                        "contentfilter": "medium",
                    },
                ) as resp:
                    data = await resp.json(content_type=None)
                for item in data.get("results") or []:
                    candidate = (((item.get("media_formats") or {}).get("gif") or {}).get("url") or "").strip()
                    if candidate:
                        title = str(item.get("title") or item.get("content_description") or "")
                        choices.append((str(item.get("id") or candidate), candidate, title))
            elif os.environ.get("ENGEL_KLIPY_API_KEY") or os.environ.get("KLIPY_API_KEY"):
                async with session.get(
                    f"https://api.klipy.com/api/v1/{key}/gifs/search",
                    params={"q": safe, "per_page": 15, "page": "1"},
                ) as resp:
                    payload = await resp.json(content_type=None)
                rows = payload.get("data")
                if isinstance(rows, dict):
                    rows = rows.get("data")
                for item in rows or []:
                    if not isinstance(item, dict):
                        continue
                    file_url = str(item.get("file", {}).get("hd", {}).get("gif", {}).get("url") or "").strip()
                    if not file_url:
                        images = item.get("images") or {}
                        file_url = str((images.get("original") or {}).get("url") or "").strip()
                    if file_url:
                        title = str(item.get("title") or item.get("slug") or "")
                        choices.append((str(item.get("id") or file_url), file_url, title))
            clean = [item for item in choices if not _drifts(item[2], query_words)]
            pool = [item for item in clean if "dayz" in item[2].casefold()]
            state = load_state()
            recent_ids = {str(item) for item in (state.get("recent_gif_ids") or [])}
            recent_hashes = {str(item) for item in (state.get("recent_gif_hashes") or [])}
            fresh = [item for item in pool if item[0] not in recent_ids]
            random.shuffle(fresh)
            logging.info("clan gif dayz=%s fresh=%s", len(pool), len(fresh))
            dest = ROOT / "run" / "gifs"
            dest.mkdir(parents=True, exist_ok=True)
            for gif_id, file_url, _title in fresh[:8]:
                path = dest / f"rally-{int(_now())}.gif"
                try:
                    async with session.get(file_url) as resp:
                        if resp.status != 200:
                            continue
                        payload = await resp.read()
                except Exception:
                    logging.exception("clan gif download failed")
                    continue
                if len(payload) < 1000:
                    continue
                digest = hashlib.sha256(payload).hexdigest()
                if digest in recent_hashes:
                    logging.info("clan gif skip duplicate")
                    continue
                path.write_bytes(payload)
                _remember_gif(gif_id, digest)
                logging.info("clan gif picked id=%s", gif_id[:24])
                return path
            return None
    except Exception:
        logging.exception("clan gif search failed")
        return None


def message_is_media(message: discord.Message) -> bool:
    if message.attachments:
        return True
    low = str(message.content or "").casefold()
    if any(token in low for token in ("tenor.com", "giphy.com", "klipy.com", ".gif")):
        return True
    for embed in message.embeds or []:
        kind = str(getattr(embed, "type", "") or "").casefold()
        url = " ".join(
            str(part or "")
            for part in (
                getattr(embed, "url", ""),
                getattr(getattr(embed, "image", None), "url", ""),
                getattr(getattr(embed, "video", None), "url", ""),
            )
        ).casefold()
        if kind in {"gifv", "image", "video"} or any(
            token in url for token in ("tenor", "giphy", "klipy", ".gif")
        ):
            return True
    return False


def owner_wants_stop(text: str) -> bool:
    low = " ".join(text.casefold().split())
    return any(word in low for word in STOP_WORDS)


def owner_wants_resume(text: str) -> bool:
    low = " ".join(text.casefold().split())
    return any(word in low for word in RESUME_WORDS)


async def say(channel: discord.abc.Messageable, text: str, query: str) -> None:
    gif = None
    tried: set[str] = set()
    current = query
    for _ in range(6):
        if not current or current in tried:
            current = speak_query()
        tried.add(current)
        gif = await download_gif(current)
        if gif:
            break
        current = speak_query()
    files = [discord.File(str(gif), filename=gif.name)] if gif else None
    if text and files:
        await channel.send(text, files=files)
    elif files:
        await channel.send(files=files)
    elif text:
        await channel.send(text)
    else:
        return
    if gif:
        state = load_state()
        state["last_gif_at"] = _now()
        save_state(state)
    logging.info("clan posted gif=%s", bool(gif))


def build_client() -> discord.Client:
    intents = discord.Intents.default()
    intents.guilds = True
    intents.guild_messages = True
    intents.message_content = True
    client = discord.Client(intents=intents)
    last_reply = {"at": 0.0}

    @client.event
    async def on_ready() -> None:
        logging.info(
            "Discord clan bridge online as %s (%s)",
            client.user,
            getattr(client.user, "id", ""),
        )
        state = load_state()
        channel = client.get_channel(CHANNEL_ID)
        if channel is None:
            logging.warning("clan channel %s is not visible yet", CHANNEL_ID)
            return
        if state.get("introduced"):
            if isinstance(channel, discord.TextChannel):
                try:
                    latest = [item async for item in channel.history(limit=6)]
                except Exception:
                    logging.exception("clan catch-up read failed")
                    return
                human = next((item for item in latest if not item.author.bot), None)
                if human is None or not message_is_media(human):
                    return
                newer = [item for item in latest if item.created_at > human.created_at]
                me = getattr(client.user, "id", None)
                already = any(getattr(item.author, "id", None) == me for item in newer)
                if not already:
                    await on_message(human)
            return
        text = await asyncio.to_thread(local_clan_reply, "The clan chat has been quiet for weeks.", "intro")
        await say(channel, text, speak_query())
        remember_turn(
            author_id="bc_rally",
            author_name="BC Rally",
            said="The clan chat has been quiet for weeks.",
            reply=text,
            kind="intro",
        )
        state["introduced"] = True
        state["last_nudge_at"] = _now()
        save_state(state)

    @client.event
    async def on_message(message: discord.Message) -> None:
        if message.author.bot:
            return
        if message.guild is None or int(message.guild.id) != GUILD_ID:
            return
        if int(message.channel.id) != CHANNEL_ID:
            return
        content = str(message.content or "").strip()
        state = load_state()
        if int(message.author.id) == OWNER_ID and content:
            if owner_wants_stop(content):
                state["muted"] = True
                save_state(state)
                await message.channel.send("I'm quiet. Say resume when you want me back in the lobby.")
                return
            if owner_wants_resume(content):
                state["muted"] = False
                save_state(state)
        if state.get("muted"):
            return
        now = _now()
        if now - float(last_reply["at"]) < REPLY_COOLDOWN_SECONDS:
            return
        last_reply["at"] = now
        try:
            await message.add_reaction(random.choice(REACTIONS))
        except Exception:
            logging.exception("clan reaction failed")
        prompt = content or "Someone dropped a DayZ clip in the clan chat."
        author_name = str(message.author.display_name or message.author.name or "someone")
        author_id = str(message.author.id)
        remember_person(author_id, author_name, prompt)
        text = await asyncio.to_thread(local_clan_reply, f"{author_name}: {prompt}", "reply")
        query = str(load_state().get("gif_query") or "") or speak_query()
        await say(message.channel, text, query)
        remember_turn(
            author_id=author_id,
            author_name=author_name,
            said=prompt,
            reply=text,
            kind="reply",
        )
        state["last_human_at"] = now
        save_state(state)

    async def quiet_loop() -> None:
        await client.wait_until_ready()
        while not client.is_closed():
            await asyncio.sleep(1800)
            state = load_state()
            if state.get("muted") or not state.get("introduced"):
                continue
            channel = client.get_channel(CHANNEL_ID)
            if channel is None or not isinstance(channel, discord.TextChannel):
                continue
            try:
                latest = [item async for item in channel.history(limit=5)]
            except Exception:
                logging.exception("clan history read failed")
                continue
            human = [item for item in latest if not item.author.bot]
            newest = human[0].created_at.timestamp() if human else 0.0
            if _now() - newest < QUIET_SECONDS:
                continue
            if _now() - float(state.get("last_nudge_at") or 0) < QUIET_SECONDS:
                continue
            text = await asyncio.to_thread(
                local_clan_reply,
                "Nobody has talked in the clan chat for a long time.",
                "nudge",
            )
            await say(channel, text, speak_query())
            remember_turn(
                author_id="bc_rally",
                author_name="BC Rally",
                said="The lobby has been empty.",
                reply=text,
                kind="nudge",
            )
            state["last_nudge_at"] = _now()
            save_state(state)

    async def gif_speak_loop() -> None:
        await client.wait_until_ready()
        await asyncio.sleep(random.uniform(90, 180))
        while not client.is_closed():
            state = load_state()
            channel = client.get_channel(CHANNEL_ID)
            if (
                not state.get("muted")
                and state.get("introduced")
                and isinstance(channel, discord.TextChannel)
                and _now() - float(state.get("last_gif_at") or 0) > 480
                and _now() - float(state.get("last_human_at") or 0) > 1800
            ):
                text = await asyncio.to_thread(
                    local_clan_reply,
                    "The lobby has a gap. Start a new DayZ squad conversation that is different from your last lines.",
                    "talk",
                )
                await say(channel, text, speak_query())
                remember_turn(
                    author_id="bc_rally",
                    author_name="BC Rally",
                    said="Random lobby GIF.",
                    reply=text,
                    kind="gif",
                )
                logging.info("clan random gif posted")
            await asyncio.sleep(random.uniform(20 * 60, 45 * 60))

    async def setup_hook() -> None:
        asyncio.create_task(quiet_loop())
        asyncio.create_task(gif_speak_loop())

    client.setup_hook = setup_hook  # type: ignore[method-assign]

    return client


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if not BOT_TOKEN:
        raise SystemExit("BC Rally token is missing")
    ROOT.mkdir(parents=True, exist_ok=True)
    (ROOT / "run").mkdir(parents=True, exist_ok=True)
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    build_client().run(BOT_TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
