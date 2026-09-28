#!/usr/bin/env python3
"""Offline simulation for the Discord ENGAGED-channel + GIF-war gating.

Stubs the discord/aiohttp modules, imports the real bridge, and drives
should_answer / _engaged_reason / discord_guest_can_only_chat through every
scenario. No network, no token, safe to run anywhere.
"""

from __future__ import annotations

import os
import sys
import time
import types

# ---- env BEFORE import (module reads these at import time) ------------------
PEER_BOT = "1483970038804385952"      # Tel
ENGAGED_CH = "1489749597365600390"    # peer/GIF-war channel
HOME_CH = "1148755186752430163"
OTHER_CH = "555000111222333444"
ENGEL_BOT = "1506157762785312808"
HUMAN_A = "DISCORD_OWNER_USER_ID"        # Joshua
HUMAN_B = "189914577100603392"        # Chase

os.environ.update(
    {
        "ENGEL_DISCORD_PEER_BOT_IDS": PEER_BOT,
        "ENGEL_DISCORD_PEER_CHANNEL_IDS": ENGAGED_CH,
        "ENGEL_DISCORD_ENGAGED_CHANNEL_IDS": ENGAGED_CH,
        "ENGEL_DISCORD_GIF_OPEN_CHANNEL_IDS": ENGAGED_CH,
        "ENGEL_DISCORD_CHANNEL_ID": HOME_CH,
        "ENGEL_DISCORD_REPLY_MODE": "all",
        "ENGEL_DISCORD_PEER_MAX_TURNS": "6",
        "ENGEL_DISCORD_GIF_WAR_MIN_GIFS": "2",
        "ENGEL_DISCORD_GIF_WAR_WINDOW_SECONDS": "120",
        "ENGEL_DISCORD_GIF_WAR_COOLDOWN_SECONDS": "6",
        "ENGEL_DISCORD_ENGAGE_WINDOW_SECONDS": "180",
    }
)

# ---- stub discord / aiohttp so the bridge imports without them ---------------
fake_discord = types.ModuleType("discord")


class _FakeDMChannel:  # isinstance target
    pass


class _FakeMessage:
    pass


class _FakeClientUser:
    pass


fake_discord.DMChannel = _FakeDMChannel
fake_discord.Message = _FakeMessage
fake_discord.ClientUser = _FakeClientUser
fake_discord.Client = object
fake_discord.Intents = object
sys.modules.setdefault("discord", fake_discord)
try:
    import aiohttp  # noqa: F401
except Exception:
    sys.modules.setdefault("aiohttp", types.ModuleType("aiohttp"))

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engel_discord_bridge as bridge  # noqa: E402


# ---- fakes -------------------------------------------------------------------
class Obj:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class BotUser:
    def __init__(self, uid):
        self.id = uid

    def mentioned_in(self, message):
        return bool(getattr(message, "mentions_engel", False))


BOT = BotUser(ENGEL_BOT)


def msg(channel_id, author_id, content="", *, bot=False, gif=False,
        mentions_engel=False, reply_to_engel=False, dm=False, attachments=None):
    channel = _FakeDMChannel() if dm else Obj(id=channel_id)
    if not dm:
        channel.id = channel_id
    atts = attachments if attachments is not None else []
    if gif and not atts:
        atts = [Obj(filename="battle.gif", content_type="image/gif")]
    reference = None
    if reply_to_engel:
        reference = Obj(resolved=Obj(author=Obj(id=ENGEL_BOT)), cached_message=None)
    return Obj(
        channel=channel,
        author=Obj(id=author_id, bot=bot),
        content=content,
        attachments=atts,
        embeds=[],
        reference=reference,
        mentions_engel=mentions_engel,
        id="m1",
    )


def reset_state():
    bridge._PEER_TURNS.clear()
    bridge._ENGAGED_PARTNERS.clear()
    bridge._GIF_SIGHTINGS.clear()
    bridge._LAST_WAR_REPLY.clear()


PASS = 0
FAIL = 0


def check(label, actual, expected):
    global PASS, FAIL
    ok = actual == expected
    PASS += ok
    FAIL += not ok
    print(f"{'PASS' if ok else 'FAIL'}  {label}  (got {actual!r}, want {expected!r})")


# ---- scenarios ----------------------------------------------------------------
reset_state()
check("home channel: short smalltalk stays silent",
      bridge.should_answer(msg(HOME_CH, HUMAN_A, "sup"), BOT), False)
check("home channel: a real question is answered",
      bridge.should_answer(msg(HOME_CH, HUMAN_A, "what do you think about this"), BOT), True)
check("home channel: room intro is for Engel",
      bridge.should_answer(msg(HOME_CH, HUMAN_A, "Every introduce your self's and your role"), BOT), True)
old_desk = bridge.DESK_NAME
old_reply = bridge.REPLY_MODE
bridge.DESK_NAME = "research"
bridge.REPLY_MODE = "mention"
bridge._HOUSE_CHANNEL_IDS.add(OTHER_CH)
try:
    check("house roll call is for a desk even without @mention",
          bridge.should_answer(msg(OTHER_CH, HUMAN_A, "Every introduce your self's and your role"), BOT), True)
    check("desk still ignores ordinary house chatter",
          bridge.should_answer(msg(OTHER_CH, HUMAN_A, "sup"), BOT), False)
    check("research ask is owner desk work, not smalltalk",
          bridge.discord_owner_prompt_is_task(
              "Start researching cost saving options and ram for the Dell r730xd"
          ), True)
    check("desk work instruction leads with the ask, not identity",
          (
              "concrete findings" in bridge.discord_desk_work_instruction(
                  "Start researching cost saving options and ram for the Dell r730xd",
                  "research",
              ).casefold()
              and "joshua vs chase" in bridge.discord_desk_work_instruction(
                  "x", "research"
              ).casefold()
          ),
          True)
    thread_msg = msg(OTHER_CH, HUMAN_A, "dig into competitor pricing")
    thread_msg.channel.name = "Cost saving"
    thread_msg.channel.category = None
    thread_msg.channel.parent = Obj(name="research", category=Obj(name="RESEARCH"))
    check("Discord threads inherit RESEARCH ownership from parent channel",
          bridge.discord_matching_desk_for_chat(thread_msg), "research")
    check("mention-mode desk still answers a roll call in its home channel",
          bridge.should_answer(msg(HOME_CH, HUMAN_A, "Every introduce your self's and your role"), BOT), True)
    nim = bridge.apply_discord_mouth_nvidia_brain(
        {"prompt": "x", "metadata": {}},
        desk_name="research",
        prompt="Start researching cost saving options and ram for the Dell r730xd",
    )
    check("Research mouth forces NVIDIA brain",
          bool(nim.get("force_provider") is True and nim.get("provider") == "nvidia"), True)
    bridge._WORK_COLLAB.clear()
    bridge.open_work_collab(OTHER_CH, prompt="research Dell", reason="owner_task")
    check("open work collab raises peer ceiling",
          bridge.peer_max_turns_for(OTHER_CH) >= 1000, True)
    bridge.close_work_collab(OTHER_CH)
    check("closed work restores normal ceiling",
          bridge.peer_max_turns_for(OTHER_CH), bridge.PEER_MAX_TURNS)
    check("research charter owns Dell RAM cost ask",
          bridge.best_desk_for_prompt(
              "Start researching cost saving options and ram for the Dell r730xd"
          ), "research")
    check("product charter owns roadmap ask",
          bridge.best_desk_for_prompt("update the product roadmap and feature priority"), "product")
    check("support charter owns broken-error ask",
          bridge.best_desk_for_prompt("help me this is broken with an error ticket"), "support")
    check("ops charter owns CT246 service ask",
          bridge.best_desk_for_prompt("check the CT246 systemd service health and mount"), "ops")
    check("sales charter owns pitch/pricing ask",
          bridge.best_desk_for_prompt("draft a sales pitch and pricing offer for the lead"), "sales")
    check("community charter owns welcome vibe ask",
          bridge.best_desk_for_prompt("welcome guests and set the community vibe for the event"), "community")
    bridge.DESK_NAME = "research"
    bridge.REPLY_MODE = "mention"
    bridge._HOUSE_CHANNEL_IDS.add(HOME_CH)
    check("Research claims charter work in #general without @mention",
          bridge.should_answer(
              msg(HOME_CH, HUMAN_A, "Start researching cost saving options and ram for the Dell r730xd"),
              BOT,
          ), True)
    bridge.DESK_NAME = "sales"
    check("Sales does not steal a Research charter ask",
          bridge.should_answer(
              msg(HOME_CH, HUMAN_A, "Start researching cost saving options and ram for the Dell r730xd"),
              BOT,
          ), False)
    bridge.DESK_NAME = ""
    check("Main yields Research charter ask in #general",
          bridge.should_answer(
              msg(HOME_CH, HUMAN_A, "Start researching cost saving options and ram for the Dell r730xd"),
              BOT,
          ), False)
    check("desk work instruction carries charter duty",
          (
              "Deep research" in bridge.discord_desk_work_instruction("x", "research")
              or "research" in bridge.discord_desk_work_instruction("x", "research").casefold()
          ), True)
finally:
    bridge.DESK_NAME = old_desk
    bridge.REPLY_MODE = old_reply
    bridge._HOUSE_CHANNEL_IDS.discard(OTHER_CH)
    bridge._HOUSE_CHANNEL_IDS.discard(HOME_CH)

check("engaged channel: random human chatter -> silent",
      bridge.should_answer(msg(ENGAGED_CH, HUMAN_B, "tel you there?"), BOT), False)

check("engaged channel: 'engel' prefix summon -> answered",
      bridge.should_answer(msg(ENGAGED_CH, HUMAN_B, "engel what do you think"), BOT), True)

check("engaged channel: @mention summon -> answered",
      bridge.should_answer(msg(ENGAGED_CH, HUMAN_B, "yo", mentions_engel=True), BOT), True)

check("engaged channel: discord-reply to Engel -> answered",
      bridge.should_answer(msg(ENGAGED_CH, HUMAN_B, "haha nice", reply_to_engel=True), BOT), True)

# continuation window
reset_state()
bridge._note_engel_engaged(ENGAGED_CH, HUMAN_B)
check("engaged channel: same author within window -> continuation answered",
      bridge.should_answer(msg(ENGAGED_CH, HUMAN_B, "and another thing"), BOT), True)
check("engaged channel: DIFFERENT author within window -> silent",
      bridge.should_answer(msg(ENGAGED_CH, HUMAN_A, "unrelated"), BOT), False)
bridge._ENGAGED_PARTNERS[ENGAGED_CH][HUMAN_B] = time.monotonic() - (bridge.ENGAGE_WINDOW_SECONDS + 5)
check("engaged channel: same author after window expiry -> silent",
      bridge.should_answer(msg(ENGAGED_CH, HUMAN_B, "hello again"), BOT), False)

# GIF war
reset_state()
check("engaged channel: lone gif (no war, not addressed) -> silent",
      bridge.should_answer(msg(ENGAGED_CH, HUMAN_B, gif=True), BOT), False)
bridge._note_gif_sighting(msg(ENGAGED_CH, HUMAN_B, gif=True))
check("one gif from one author: war not active",
      bridge._gif_war_active(ENGAGED_CH), False)
bridge._note_gif_sighting(msg(ENGAGED_CH, ENGEL_BOT, bot=True, gif=True))  # Engel fired back (via summon)
check("two gifs from two authors: WAR ACTIVE",
      bridge._gif_war_active(ENGAGED_CH), True)
check("engaged channel: gif during war -> answered (gif_war)",
      bridge._engaged_reason(msg(ENGAGED_CH, HUMAN_B, gif=True), BOT), "gif_war")
check("engaged channel: tenor LINK during war -> answered",
      bridge.should_answer(msg(ENGAGED_CH, HUMAN_B, "https://tenor.com/view/vader-no"), BOT), True)
check("engaged channel: plain TEXT during war (not addressed) -> silent",
      bridge.should_answer(msg(ENGAGED_CH, HUMAN_A, "lol this war"), BOT), False)
bridge._LAST_WAR_REPLY[ENGAGED_CH] = time.monotonic()
check("war cooldown: immediate next gif -> silent",
      bridge.should_answer(msg(ENGAGED_CH, HUMAN_B, gif=True), BOT), False)
bridge._LAST_WAR_REPLY[ENGAGED_CH] = time.monotonic() - (bridge.GIF_WAR_COOLDOWN_SECONDS + 1)
check("war cooldown elapsed: next gif -> answered again",
      bridge.should_answer(msg(ENGAGED_CH, HUMAN_B, gif=True), BOT), True)

# peer bot (Tel) under the engagement gate
reset_state()
check("Tel random text (not talking to Engel, no war) -> silent  [NEW behavior]",
      bridge.should_answer(msg(ENGAGED_CH, PEER_BOT, "chase check this out", bot=True), BOT), False)
check("Tel says 'Engel ...' -> answered (peer + summon)",
      bridge.should_answer(msg(ENGAGED_CH, PEER_BOT, "engel you up?", bot=True), BOT), True)
check("Tel discord-replies to Engel -> answered",
      bridge.should_answer(msg(ENGAGED_CH, PEER_BOT, "good point", bot=True, reply_to_engel=True), BOT), True)
bridge._PEER_TURNS[ENGAGED_CH] = bridge.PEER_MAX_TURNS
bridge._WORK_COLLAB.clear()
check("Tel summon at peer-turn cap -> silent (cap still rules)",
      bridge.should_answer(msg(ENGAGED_CH, PEER_BOT, "engel again", bot=True), BOT), False)
bridge._PEER_TURNS[ENGAGED_CH] = 0
bridge._note_gif_sighting(msg(ENGAGED_CH, HUMAN_B, gif=True))
bridge._note_gif_sighting(msg(ENGAGED_CH, PEER_BOT, bot=True, gif=True))
check("Tel gif during war -> answered (bot gif war)",
      bridge.should_answer(msg(ENGAGED_CH, PEER_BOT, bot=True, gif=True), BOT), True)
check("unlisted bot in engaged channel -> always silent",
      bridge.should_answer(msg(ENGAGED_CH, "999888777", "hi", bot=True), BOT), False)

# other channels unchanged
reset_state()
check("other channel: random text -> silent",
      bridge.should_answer(msg(OTHER_CH, HUMAN_B, "hello"), BOT), False)
check("other channel: summon -> answered",
      bridge.should_answer(msg(OTHER_CH, HUMAN_B, "engel hi"), BOT), True)
check("DM -> always answered",
      bridge.should_answer(msg("dm", HUMAN_B, "hi", dm=True), BOT), True)

# guest gate: GIF lane opens in the gif-open channel only
GUEST = {"authority_level": "guest", "sender_id": HUMAN_B}
check("guest gif request in GIF-OPEN channel -> ALLOWED",
      bridge.discord_guest_can_only_chat("send me a vader gif", msg(ENGAGED_CH, HUMAN_B, "send me a vader gif"), GUEST), False)
check("guest gif request in other channel -> still blocked",
      bridge.discord_guest_can_only_chat("send me a vader gif", msg(OTHER_CH, HUMAN_B, "send me a vader gif"), GUEST), True)
check("guest gif ATTACHMENT in GIF-OPEN channel -> allowed",
      bridge.discord_guest_can_only_chat("", msg(ENGAGED_CH, HUMAN_B, gif=True), GUEST), False)
check("guest artifact request in GIF-OPEN channel -> still blocked",
      bridge.discord_guest_can_only_chat("create a python file", msg(ENGAGED_CH, HUMAN_B, "create a python file"), GUEST), True)
check("guest protected capability in GIF-OPEN channel -> still blocked",
      bridge.discord_guest_can_only_chat("restart the server", msg(ENGAGED_CH, HUMAN_B, "restart the server"), GUEST), True)
check("owner gif request anywhere -> allowed",
      bridge.discord_guest_can_only_chat("send me a gif", msg(OTHER_CH, HUMAN_A, "send me a gif"), {"authority_level": "owner"}), False)

print(f"\n{PASS} passed / {FAIL} failed")
sys.exit(1 if FAIL else 0)
