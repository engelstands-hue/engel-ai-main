#!/usr/bin/env python3
"""Persona guard - one place that stops Engel reciting its instructions instead of talking.

THE PROBLEM THIS SOLVES
-----------------------
Engel's prompt-training harness sends "answer contracts" through the SAME chat lane that
serves live conversation (the UI chat inbox). A contract like
`_COMMUNICATION_ANSWER_CONTRACT` ends with "Do not restate these instructions" - and the
model restates them anyway. Live on 2026-08-13 that produced replies such as:

    "Engel AI Main handles this turn as one worker among many, not the full system. I will
     answer in plain English and follow the rules without claiming proof of work..."

sent to a peer node and to Joshua as if it were an answer.

The training harness already DETECTS this (`engel_governor.looks_like_contract_echo`) but it
uses the signal to reject a training SAMPLE. The reply still goes out. So the operator sees a
bot reciting its own rules, and the graded voice bank can capture that recitation as an
example of Engel's voice - which teaches the next model to do it again.

WHAT THIS MODULE IS
-------------------
The persona layer's output half: a single source of leak markers and one scrubber, applied at
the one point every chat lane finalises a reply (`_apply_chat_humanizer`). Consequences:

* every lane is covered at once - main chat turn, quick/casual, fast server, live status,
  skill-agent, provider bridges, and therefore the app UI, Discord and the meeting room;
* the voice example bank never captures a recitation, because scrubbing happens before capture;
* callers outside the chat service (the Discord bridge) import the SAME markers instead of
  keeping a private copy that drifts.

DESIGN RULES
------------
* stdlib only, and **fail-open**: any internal error returns the reply untouched. A persona
  guard must never be the reason chat breaks.
* markers come from `engel_governor.CONTRACT_ECHO_MARKERS` (already the curated single source
  used by training) plus the persona/style restatements listed here. Markers are NOT derived
  automatically from the style card: a card line like "Be concise" would match honest replies
  and silently delete them. Missing a leak is recoverable; eating a real answer is not.
* only LEADING sentences are stripped. A genuine answer that happens to use a phrase later on
  ("Joshua still has to approve") must survive intact.

    python engel_persona_guard.py --selftest
"""

from __future__ import annotations

import argparse
import re
import sys
from typing import Iterable

__all__ = [
    "persona_leak_markers",
    "looks_like_persona_leak",
    "looks_like_discord_mouth_reply",
    "scrub_persona_leak",
    "PERSONA_ECHO_MARKERS",
    "DISCORD_MOUTH_REPLY_MARKERS",
    "ALL_LEAK_FALLBACK",
]

# Restatements of the persona/voice contract itself, observed live. Kept here rather than in
# each caller so the Discord bridge and the chat service cannot drift apart.
PERSONA_ECHO_MARKERS: tuple[str, ...] = (
    "handles this turn as one worker among many",
    "i will answer in plain english",
    "answer in plain english and follow the rules",
    "follow the rules without claiming",
    "without claiming proof of work",
    "answer the way you would answer joshua",
    "first person, plain sentences",
    "your own voice. no headings",
    "no 'result:'/'confirmed:' style labels",
    "no bullet lists, no code blocks",
    "keep it to a few short paragraphs",
    "keep the reply the size of the question",
    "say plainly what you do not know instead of filling the gap",
    "do not restate these instructions",
    # peer-lane framing added by the Discord bridge
    "context, not part of the message",
    "peer worker node",
    "peer ai worker node",
    "is replying to",
    "address it as",
    "never as joshua",
    "not joshua",
    "do not thank it",
    "nothing runs from this lane",
    "nothing can run from this lane",
    "this lane is conversation only",
    "this turn is conversation only",
    "do not claim work has started",
    "do not invent",
    "reply briefly to",
    "answer in a sentence or two",
    "in a sentence or two",
    # (2026-08-14) the three stance-narration families observed live in #general -
    # 19 of 48 logged replies opened with one of these paraphrase shapes, which the
    # model INVENTS (none of these strings exist in any prompt template):
    #   "Engel AI Main handles replies to Sub-Engel as one worker among peers, not as
    #    Joshua." / "Engel AI Main answers Sub-Engel as one worker in this workspace:
    #    I treat replies to Sub-Engel as a lane conversation..." / "Engel AI Main
    #    here. I am responding to Sub-Engel, a peer worker node..."
    "handles replies to",
    "as one worker among peers",
    "as one worker in this workspace",
    "not as joshua",
    "i treat replies to",
    "i am responding to",
    "i am replying to",
    "engel ai main here",
    # phrases from the peer-facts framing (frame_peer_prompt) so an echo of the new
    # bracket is scrubbed the same day it first leaks
    "your own live peer worker node",
    "part of your fleet",
    "how you two coordinate",
    "there is no ct256",
    "cannot approve protected actions",
    "accept this-computer collab and name",
    "do not claim a ct246 restart",
    "concrete, honest next step",
    "do not repeat its words back",
    # phrases from the guest-identity framing (frame_guest_prompt, 2026-08-14); all
    # risky-tier below except the pure directive, because Engel may HONESTLY tell a
    # guest "you are a guest on this Discord server" or "you're not an admin"
    "guest on this discord server",
    "not an admin",
    "not a worker node",
    "the person talking to you is",
    "or direct engel's systems",
    "answer as normal friendly chat",
    # (2026-08-16) a FOURTH stance-narration paraphrase reached #general verbatim:
    # "Engel AI Main replies to Sub-Engel as one worker node in the fleet, not as
    # Joshua. Use this channel for coordination and relay honest next steps; do not
    # claim proof or approval from Engel AI Main." It carried no colon (so the label
    # regex missed it) and none of its wording was a marker. All four are risky-tier
    # below - each is sayable in an honest sentence, only a chain of them is recitation.
    "replies to sub-engel as",
    "use this channel for coordination",
    "relay honest next steps",
    "do not claim proof",
    # (2026-08-17) desktop chat recited a NEW two-sentence stance instead of
    # answering "Build this with Engel...":
    # "Engel AI Main will treat this as part of the ongoing conversation and
    # answer directly. I will not claim proof or action unless a worker reports it."
    # Variants swapped the first clause for "route this turn to the active brain
    # lane as part of normal turn handling." None of that is an answer.
    "will not claim proof",
    "unless a worker reports",
    "active brain lane",
    "part of the ongoing conversation and answer directly",
    "part of normal turn handling",
    # (2026-08-18) live #general screenshot: Engel answered Sub-Engel's
    # "Fresh one" GIF with this identity-theater paragraph instead of a GIF.
    "acknowledges receipt of the message",
    "stands ready to assist",
    "as one worker node",
    "one worker node in your fleet",
    "never call joshua",
    "describe him as the system",
    "describe joshua as the",
    "i will follow the rule",
    "treat this as part of the ongoing conversation",
    "treat this reply as part of the ongoing conversation",
    "route this turn to the active brain lane",
    "this discord channel is an 18+ adult room",
    "adult language and adult gifs are allowed",
    "do not refuse, lecture, or sanitize for pg",
    # (2026-09-10) catastrophic Discord leak: mouth posted the full internal
    # Discord conversation / sender / GIF-favicon instruction stack.
    "we are in a discord conversation",
    "the sender is engel",
    "current discord sender",
    "rotate the favicon",
    "one library favicon",
    "gif and one library favicon",
    "visible picture notes are in this turn",
    "answer as engel ai main in one real discord",
    # Engel AI Main desktop must never ship Discord-guest policy as an answer.
    # Live 2026-09-24 Chat Communication turn: laptop llama.cpp replied with the
    # old guest-tool card instead of answering Joshua as Engel.
    "only engelz can use engel tools",
    "only engelz can run admin",
    "diagnostics from discord",
    "i can chat here, but only engelz",
    "i can talk and throw gifs with everyone",
    "that's the guest chat gate",
    "guest chat gate, not admin",
)

# Whole-reply Discord-mouth cards. Distinctive enough that one hit is enough.
DISCORD_MOUTH_REPLY_MARKERS: tuple[str, ...] = (
    "only engelz can use engel tools",
    "only engelz can run admin",
    "diagnostics from discord",
    "i can chat here, but only engelz",
    "i can talk and throw gifs with everyone",
    "that's the guest chat gate",
    "guest chat gate, not admin",
)

# These may hide behind a greeting. They are never an honest later sentence.
# Broader distinctive markers stay leading-only so "I will answer in plain
# English about the result" is not eaten mid-reply.
MID_REPLY_STANCE_MARKERS: frozenset[str] = frozenset(
    marker.casefold()
    for marker in (
        "will not claim proof",
        "unless a worker reports",
        "active brain lane",
        "part of the ongoing conversation and answer directly",
        "part of normal turn handling",
        "treat this as part of the ongoing conversation",
        "treat this reply as part of the ongoing conversation",
        "route this turn to the active brain lane",
    )
)

# Markers that are ORDINARY ENGLISH as well as contract text. Adversarial fuzzing
# (2026-08-14, 33 must-survive cases) showed a single one of these in a one-sentence
# honest reply deleted the whole answer: "Do not invent new worker ids", "That
# decision is the operator's call, not Joshua's", "I can explain the whole pipeline
# in a sentence or two", "The DNS entry is stale; address it as 192.0.2.40". So a
# risky marker only counts when a sentence carries TWO distinct ones (or one
# distinctive marker) - real recitations string contract phrases together, honest
# sentences brush one at most. Governor-imported contract markers are all treated as
# risky for the same reason ("one line with the answer", "the key steps.").
RISKY_ECHO_MARKERS: frozenset[str] = frozenset(
    marker.casefold()
    for marker in (
        "is replying to",
        "address it as",
        "not joshua",
        "not as joshua",
        "do not thank it",
        "do not invent",
        "reply briefly to",
        "answer in a sentence or two",
        "in a sentence or two",
        "i am responding to",
        "i am replying to",
        "part of your fleet",
        "cannot approve protected actions",
        "concrete, honest next step",
        # guest-frame vocabulary Engel may honestly use when EXPLAINING someone's
        # role to them; only a chain of them is recitation
        "guest on this discord server",
        "not an admin",
        "not a worker node",
        "the person talking to you is",
        "or direct engel's systems",
        # (2026-08-16) A NEW paraphrase of the peer frame reached the live channel
        # verbatim: "Engel AI Main replies to Sub-Engel as one worker node in the fleet,
        # not as Joshua. Use this channel for coordination and relay honest next steps;
        # do not claim proof or approval from Engel AI Main." No colon, so the label
        # regex did not catch it, and none of its wording was a marker. These four
        # phrases are instructions ABOUT the channel, which an answer never needs;
        # risky-tier, so a single incidental hit still cannot eat an honest reply.
        "use this channel for coordination",
        "relay honest next steps",
        "do not claim proof",
        "replies to sub-engel as",
    )
)

# A reply-label the model invents in front of its answer ("Engel AI Main replies to
# Sub-Engel: <answer>"). It must be removed WITHOUT the sentence machinery: the colon
# fuses the label to the first real sentence, so a marker hit would delete the answer
# too. Anchored, one removal. Guards against honest text (all fuzz-proven live):
# addressee tokens are LETTERS ONLY, so "responds to pings on 8787 — ..." can never
# read "8787" as an addressee; a dash separator REQUIRES an addressee ("Engel
# responds — the SSE stream is separate" survives) while a colon does not ("Engel AI
# Main responds: ..." is a label); a genuine sentence like "Engel AI Main replies to
# every whitelisted peer in the home channel." has no separator and never matches;
# Sub-Engel's internal hyphen is not a separator (only a SPACED hyphen counts).
_LEADING_REPLY_LABEL = re.compile(
    r"^[\s\[\(\"'*_>]*"
    r"engel(?:\s+ai(?:\s+main)?)?(?:\s*\[bot\])?"
    r"\s+(?:(?:is\s+|now\s+)?repl(?:ies|y|ying)(?:\s+to)?"
    r"|respond(?:s|ing)(?:\s+to)?"
    r"|answer(?:s|ing)(?:\s+to)?"
    r"|says?\s+to)"
    r"(?:"
    r"(?:\s+[A-Za-z][A-Za-z.'\-]{0,31}){0,3}?\s*:"
    r"|(?:\s+[A-Za-z][A-Za-z.'\-]{0,31}){1,3}?\s*(?:—|–|\s-\s)"
    r")\s*",
    re.IGNORECASE,
)

ALL_LEAK_FALLBACK = (
    "I read your message, but what came back was my own instructions rather than an answer, "
    "so I am not going to pass it off as one. Ask me again and I will answer it properly."
)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_LEAD_TRIM = "[]()\"'*_>-— \t"

_CACHED_MARKERS: tuple[str, ...] | None = None


_GOV_CACHE: tuple[str, ...] | None = None


def _governor_markers() -> tuple[str, ...]:
    """Canonical contract markers. Fail-open: an import problem must not disable chat."""
    global _GOV_CACHE
    if _GOV_CACHE is not None:
        return _GOV_CACHE
    collected: list[str] = []
    try:
        from engel_governor import CONTRACT_ECHO_MARKERS  # type: ignore

        collected.extend(str(marker) for marker in CONTRACT_ECHO_MARKERS)
    except Exception:
        pass
    try:
        # The delivery wrapper itself ("Training depth: ... / Training task:"), so a reply
        # that recites the scaffolding is scrubbed the same as one reciting the contract.
        from engel_governor import TRAINING_WRAPPER_MARKERS  # type: ignore

        collected.extend(str(marker) for marker in TRAINING_WRAPPER_MARKERS)
    except Exception:
        pass
    _GOV_CACHE = tuple(marker.casefold() for marker in collected if marker.strip())
    return _GOV_CACHE


def persona_leak_markers(extra: Iterable[str] | None = None) -> tuple[str, ...]:
    """Every phrase that marks a reply as recitation rather than an answer."""
    global _CACHED_MARKERS
    if _CACHED_MARKERS is None:
        merged = {marker.casefold() for marker in PERSONA_ECHO_MARKERS if marker.strip()}
        merged.update(_governor_markers())
        _CACHED_MARKERS = tuple(sorted(merged))
    if not extra:
        return _CACHED_MARKERS
    combined = set(_CACHED_MARKERS)
    combined.update(str(item).casefold() for item in extra if str(item).strip())
    return tuple(sorted(combined))


def _marker_hits(probe: str, markers: tuple[str, ...]) -> list[tuple[int, int, str]]:
    """Non-nested marker matches in probe as (start, end, marker).

    Overlapping markers ("answer in a sentence or two" contains "in a sentence or
    two") must count as ONE hit or the two-hit rule for risky markers is trivially
    satisfied by a single phrase.
    """
    raw: list[tuple[int, int, str]] = []
    for marker in markers:
        start = probe.find(marker)
        while start >= 0:
            raw.append((start, start + len(marker), marker))
            start = probe.find(marker, start + 1)
    raw.sort(key=lambda hit: (hit[0], -(hit[1] - hit[0])))
    kept: list[tuple[int, int, str]] = []
    for start, end, marker in raw:
        if any(start >= k_start and end <= k_end for k_start, k_end, _ in kept):
            continue
        kept.append((start, end, marker))
    return kept


def _is_recitation(sentence: str, markers: tuple[str, ...]) -> bool:
    """A sentence is recitation on one DISTINCTIVE marker, or two distinct RISKY ones.

    Risky markers are ordinary English; a lone one in an honest reply must never
    delete it (fuzz-proven 2026-08-14: 12 honest one-liners were replaced by the
    fallback under the old any-marker rule). Real recitations chain phrases, so the
    two-hit rule still catches them.
    """
    probe = sentence.strip().casefold().lstrip(_LEAD_TRIM)
    if not probe:
        return False
    hits = _marker_hits(probe, markers)
    if not hits:
        return False
    risky_count = 0
    for _, _, marker in hits:
        if marker in RISKY_ECHO_MARKERS or marker in _governor_markers():
            risky_count += 1
        else:
            return True
    return risky_count >= 2


def looks_like_discord_mouth_reply(text: str) -> bool:
    """True when the model answered as a Discord guest gate instead of Engel AI Main."""
    try:
        low = " ".join(str(text or "").casefold().split())
        if not low:
            return False
        return any(marker in low for marker in DISCORD_MOUTH_REPLY_MARKERS)
    except Exception:
        return False


def looks_like_persona_leak(text: str, extra_markers: Iterable[str] | None = None) -> bool:
    """True when the text opens by reciting the persona/answer contract."""
    try:
        body = str(text or "").strip()
        if not body:
            return False
        if looks_like_discord_mouth_reply(body):
            return True
        if _LEADING_REPLY_LABEL.match(body):
            return True
        markers = persona_leak_markers(extra_markers)
        for sentence in _SENTENCE_SPLIT.split(body):
            if not sentence.strip():
                continue
            return _is_recitation(sentence, markers)
        return False
    except Exception:
        return False


def scrub_persona_leak(
    reply: str,
    *,
    extra_markers: Iterable[str] | None = None,
    fallback: str = ALL_LEAK_FALLBACK,
) -> tuple[str, bool, str]:
    """Remove recited instructions from the front of a reply.

    Returns ``(clean_reply, changed, reason)``. ``reason`` is "" when nothing changed,
    "stripped" when a preamble was removed and a real answer survived, and "all_recitation"
    when the whole reply was instructions and the honest fallback replaced it.

    Fail-open: on any internal error the original reply is returned unchanged.
    """
    try:
        body = str(reply or "").strip()
        if not body:
            return body, False, ""
        if looks_like_discord_mouth_reply(body):
            return fallback, True, "discord_mouth"
        markers = persona_leak_markers(extra_markers)
        dropped = False

        # An invented reply-label ("Engel AI Main replies to Sub-Engel: ...") fuses to
        # the first real sentence through its colon, so remove it BEFORE sentence work.
        # Whatever follows the separator is the answer BY CONSTRUCTION, so a short
        # remainder is kept ("...replies to Sub-Engel: Yes." must become "Yes.", not
        # the fallback) - but it still runs through the sentence loop below, because a
        # label can front recitation too.
        label_stripped = False
        unlabeled = _LEADING_REPLY_LABEL.sub("", body, count=1).strip()
        if unlabeled != body:
            dropped = True
            label_stripped = True
            if not unlabeled:
                return fallback, True, "all_recitation"
            body = unlabeled

        def _mid_reply_stance(sentence: str) -> bool:
            probe = sentence.casefold()
            return any(marker in probe for marker in MID_REPLY_STANCE_MARKERS)

        segments = _SENTENCE_SPLIT.split(body)
        kept: list[str] = []
        still_leading = True
        index = 0
        while index < len(segments):
            segment = segments[index]
            work = segment.strip()
            # Distinctive stance lines can hide behind "Hello, Joshua."
            # They are never an answer. Strip them in any position.
            if work and _mid_reply_stance(work) and not still_leading:
                dropped = True
                index += 1
                continue
            if still_leading and work:
                probe = work.casefold()
                if _is_recitation(work, markers):
                    dropped = True
                    head, colon, rest = work.partition(":")
                    colon_pos = probe.find(":")
                    hits = _marker_hits(probe.lstrip(_LEAD_TRIM), markers)
                    offset = len(probe) - len(probe.lstrip(_LEAD_TRIM))
                    starts_before_colon = colon_pos >= 0 and any(
                        start + offset < colon_pos for start, _, _ in hits
                    )
                    if colon and rest.strip() and starts_before_colon:
                        # Directive fused to content by its colon ("Reply in a
                        # sentence or two: That's an interesting idea!") loses the
                        # directive; the remainder is re-judged next pass, so chained
                        # directives cannot smuggle one through. Terminates because
                        # the remainder is strictly shorter each time.
                        segments[index] = rest.strip()
                        continue
                    if colon and rest.strip():
                        # Every marker sits AFTER the colon: the head is honest
                        # content ("Quick status on the pairing: nothing runs from
                        # this lane...") - keep the head, drop only the recited rest.
                        kept.append(head.rstrip() + ":")
                        still_leading = False
                        index += 1
                        continue
                    index += 1
                    continue
                # Not recitation by the two-hit rule, but a bare directive can still
                # front real content through a colon when the head IS a marker
                # ("Reply in a sentence or two: <answer>" - one risky hit only).
                head, colon, rest = work.partition(":")
                head_probe = head.strip(_LEAD_TRIM + ":").casefold()
                head_is_marker = colon and head_probe and any(
                    marker in head_probe and len(head_probe) <= len(marker) + 8
                    for marker in markers
                )
                if head_is_marker:
                    dropped = True
                    if rest.strip():
                        segments[index] = rest.strip()
                        continue
                    index += 1
                    continue
                still_leading = False
            kept.append(segment)
            index += 1

        if not dropped:
            return body, False, ""

        cleaned = " ".join(part.strip() for part in kept if part.strip()).strip()
        # A couple of stray words left behind by MARKER stripping is not an answer -
        # but a short answer that followed a removed label is ("Yes.").
        if not cleaned or (len(cleaned) < 15 and not label_stripped):
            return fallback, True, "all_recitation"
        return cleaned, True, "stripped"
    except Exception:
        return str(reply or ""), False, ""


# ---------------------------------------------------------------- selftest


def selftest() -> int:
    checks: list[tuple[str, bool]] = []

    def check(name: str, condition: bool) -> None:
        checks.append((name, bool(condition)))

    # The two live failures this module exists for.
    service_meta = (
        "Engel AI Main handles this turn as one worker among many, not the full system. "
        "I will answer in plain English and follow the rules without claiming proof of work "
        "on Sub-Engel's lane or inventing command names."
    )
    clean, changed, reason = scrub_persona_leak(service_meta)
    check("a pure recitation is caught", changed is True)
    check("a pure recitation becomes the honest fallback", reason == "all_recitation")
    check("the fallback admits what happened", "instructions" in clean.casefold())

    mixed = (
        "Engel AI Main handles this turn as one worker among many. "
        "Nothing on your side blocks it - re-pair from your machine and the 401s stop."
    )
    clean, changed, reason = scrub_persona_leak(mixed)
    check("a preamble in front of a real answer is stripped", reason == "stripped")
    check("the real answer survives", "re-pair from your machine" in clean)
    check("the recited preamble is gone", "one worker among many" not in clean)

    theater = (
        "Engel AI Main acknowledges receipt of the message and stands ready to assist "
        "Sub-Engel as one worker node in your fleet. I will follow the rule: never call "
        "Joshua Engel or describe him as the system."
    )
    clean, changed, reason = scrub_persona_leak(theater)
    check("the 2026-08-18 identity-theater paragraph is caught", changed is True)
    check("identity theater is not posted as an answer", "acknowledges receipt" not in clean.casefold())

    contract = (
        "Answer the way you would answer Joshua in the main Engel chat: first person, plain "
        "sentences, your own voice. The listener is back up."
    )
    clean, changed, _ = scrub_persona_leak(contract)
    check("the training answer-contract is caught", changed is True)
    check("its trailing content survives", "listener is back up" in clean)

    # (2026-08-14) the three invented-label families observed live in #general.
    label_cases = (
        (
            "Engel AI Main replies to Sub-Engel: The pairing session on your side expired; "
            "Joshua approves a fresh one on the node machine.",
            "Joshua approves a fresh one",
        ),
        (
            "Engel replying to Sub-Engel - the listener check looks good from here.",
            "listener check looks good",
        ),
        (
            "Engel AI Main responds: nothing is blocked on my side.",
            "nothing is blocked on my side",
        ),
    )
    for labeled, keep in label_cases:
        clean, changed, reason = scrub_persona_leak(labeled)
        check(f"invented reply-label removed: {labeled[:34]!r}",
              changed is True and keep in clean and "replies to" not in clean.casefold()
              and not clean.casefold().startswith("engel"))
    lone_label = scrub_persona_leak("Engel AI Main replies to Sub-Engel:")
    check("a bare label with no answer becomes the honest fallback",
          lone_label[2] == "all_recitation")
    fused = (
        "Engel AI Main handles replies to Sub-Engel as one worker among peers, not as "
        "Joshua. Nothing runs from this lane alone. Reply in a sentence or two: That's an "
        "interesting idea about engineered fields."
    )
    clean, changed, reason = scrub_persona_leak(fused)
    check("colon-fused directive loses the directive only",
          changed is True and "interesting idea about engineered fields" in clean)
    check("the stance narration around it is gone",
          "one worker among peers" not in clean.casefold()
          and "sentence or two" not in clean.casefold())
    stance = (
        "Engel AI Main here. I am responding to Sub-Engel, a peer worker node on another "
        "machine — not Joshua himself. Your milestone landed; take the retry queue next."
    )
    clean, changed, _ = scrub_persona_leak(stance)
    check("multi-sentence stance narration is stripped",
          changed is True and "take the retry queue next" in clean
          and "responding to" not in clean.casefold())

    # (2026-08-14b) guest-frame narration: a paraphrase of frame_guest_prompt chains
    # its risky phrases, so the two-hit rule catches it while honest role explanations
    # (single phrase) survive below.
    guest_leak = (
        "The person talking to you is Chase/Lokal, a guest on this Discord server. "
        "Not Joshua, not an admin, not a worker node. The alloy idea could work."
    )
    clean, changed, _ = scrub_persona_leak(guest_leak)
    check("guest-frame narration is stripped",
          changed is True and clean == "The alloy idea could work.")

    short_after_label = scrub_persona_leak("Engel AI Main replies to Sub-Engel: Yes.")
    check("a short real answer after a removed label is kept, not replaced",
          short_after_label[0] == "Yes." and short_after_label[2] == "stripped")
    honest_head = scrub_persona_leak(
        "Quick status on the pairing: nothing runs from this lane, so re-pair on the node. "
        "The 401s stop after that."
    )
    check("an honest head before a recited rest survives",
          honest_head[1] is True and honest_head[0].startswith("Quick status on the pairing:")
          and "401s stop after that" in honest_head[0])
    bare_directive = scrub_persona_leak(
        "Engel AI Main handles replies to Sub-Engel as one worker among peers, not as "
        "Joshua. Nothing runs from this lane alone. Reply in a sentence or two:"
    )
    check("a directive train with NO answer becomes the honest fallback",
          bare_directive[2] == "all_recitation")

    # (2026-08-17) live Engel AI Main desktop chat. The 7B invented this pair
    # instead of answering a build request. Distinctive markers, not risky-tier.
    live_desktop_leak = (
        "Engel AI Main will treat this as part of the ongoing conversation and answer directly. "
        "I will not claim proof or action unless a worker reports it."
    )
    clean, changed, reason = scrub_persona_leak(live_desktop_leak)
    check("2026-08-17 desktop stance recitation is caught", changed is True)
    check("2026-08-17 desktop stance becomes the honest fallback", reason == "all_recitation")
    check("the 2026-08-17 leak is not shipped as an answer", "worker reports" not in clean.casefold())
    live_brain_lane = (
        "Engel AI Main will route this turn to the active brain lane as part of normal turn handling. "
        "I will not claim proof or action unless a worker reports it."
    )
    clean, changed, reason = scrub_persona_leak(live_brain_lane)
    check("active-brain-lane paraphrase is also all recitation", reason == "all_recitation")
    honest_proof = scrub_persona_leak(
        "I can start the build. The next step is a one-screen Flutter check-in, then a receipt."
    )
    check("an honest build answer is left alone",
          honest_proof[1] is False and "Flutter check-in" in honest_proof[0])
    discord_mouth = (
        "I can chat here, but only Engelz can use Engel tools, files, media generation, "
        "attachments, devices, server controls, routes, models, memory, or diagnostics from Discord."
    )
    clean, changed, reason = scrub_persona_leak(discord_mouth)
    check("Discord guest-tool card is not shipped as Engel AI Main",
          changed is True and reason == "discord_mouth"
          and looks_like_discord_mouth_reply(discord_mouth) is True)
    check("Discord guest-tool card is not kept as the visible answer",
          "only engelz can use engel tools" not in clean.casefold())
    check("an honest REPS voice answer is not a Discord mouth",
          looks_like_discord_mouth_reply(
              "Yes. Record is on for this Engel AI Main lane. I would open the latest REPS receipt next."
          )
          is False)
    greeted_leak = (
        "Hello, Joshua. I am Engel AI Main and this turn is being routed through "
        "the active brain lane as part of normal handling. I will not claim proof "
        "or action unless a worker reports it."
    )
    clean, changed, reason = scrub_persona_leak(greeted_leak)
    check("greeting plus stance recitation is not shipped",
          changed is True and "worker reports" not in clean.casefold()
          and "brain lane" not in clean.casefold())
    mixed_build = (
        "I can start the Flutter check-in next. I will not claim proof or action "
        "unless a worker reports it."
    )
    clean, changed, reason = scrub_persona_leak(mixed_build)
    check("a real answer keeps; the worker-reports trailer is dropped",
          changed is True and "Flutter check-in" in clean
          and "worker reports" not in clean.casefold())

    # Honest replies must be untouched - eating a real answer is the worse failure.
    # The 2026-08-14 adversarial fuzz found 16 of these being eaten under the old
    # any-marker rule; the risky-marker two-hit rule is what keeps them alive.
    for good in (
        "DESKTOP-UE5A6GG. Listener is up. Blocker: finish the re-pair.",
        "I cannot execute device re-pairing from here; Joshua has to approve it on that machine.",
        "The July-29 bearer is gone from my stored session record.",
        "Joshua still has to approve the pairing, and I am not the approval path.",
        # a genuine sentence that merely STARTS like a label has no separator and survives
        "Engel AI Main replies to every whitelisted peer in the home channel and nowhere else.",
        # Sub-Engel's internal hyphen is not a label separator
        "Engel answers Sub-Engel questions faster when the node reports are short.",
        # fuzz-proven: one risky marker in an honest sentence must never delete it
        "Sub-Engel is replying to gamma right now, so give it a minute.",
        "Do not invent new worker ids; reuse the ones in the manifest.",
        "That decision is the operator's call, not Joshua's.",
        "I can explain the whole pipeline in a sentence or two if you want.",
        'Joshua said "answer in a sentence or two" so I kept it short.',
        "Joshua's rule is: answer in a sentence or two, then stop.",
        "The DNS entry is stale; address it as 192.0.2.40 instead.",
        "I cannot approve protected actions, so Joshua has to click it himself.",
        "Gamma is part of your fleet now; the pairing stuck.",
        "Reply briefly to gamma when it pings you, or it re-queues the job.",
        "The bot loops when you thank it, so do not thank it mid-run.",
        # digit addressees and dash-without-addressee never satisfy the label regex
        "Engel responds to pings on 8787 — the SSE stream is separate.",
        # one risky marker in sentence 1 must not delete the sentence
        "I am responding to your second question first. The keystore is backed up.",
        # Engel HONESTLY explaining a guest's role must survive (single risky hits)
        "You are a guest on this Discord server, so Joshua has to approve that.",
        "You're not an admin here, Chase, so I cannot run that for you.",
    ):
        clean, changed, _ = scrub_persona_leak(good)
        check(f"honest reply untouched: {good[:38]!r}", changed is False and clean == good)

    # Only LEADING recitation is removed.
    trailing = (
        "Re-pair from DESKTOP-UE5A6GG. After that I will answer in plain English about the "
        "result."
    )
    clean, changed, _ = scrub_persona_leak(trailing)
    check("mid-answer phrasing is not stripped", changed is False and clean == trailing)

    check("empty input is safe", scrub_persona_leak("") == ("", False, ""))
    check("None input is safe", scrub_persona_leak(None)[1] is False)

    # Single source: the governor's curated contract markers are included.
    markers = persona_leak_markers()
    check("markers include the persona set",
          "handles this turn as one worker among many" in markers)
    gov = _governor_markers()
    if gov:
        check("markers include the governor's contract set", gov[0] in markers)
    else:
        check("governor markers absent but guard still works (fail-open)", True)
    check("markers are deduplicated", len(markers) == len(set(markers)))

    check("detector agrees with the scrubber", looks_like_persona_leak(service_meta) is True)
    check("detector clears an honest reply",
          looks_like_persona_leak("Listener is up.") is False)

    passed = sum(1 for _, ok in checks if ok)
    for name, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    print(f"\n{passed}/{len(checks)} checks passed")
    return 0 if passed == len(checks) else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--markers", action="store_true", help="print every active marker")
    parser.add_argument("--check", help="scrub one string and show the result")
    args = parser.parse_args()

    if args.markers:
        for marker in persona_leak_markers():
            print(marker)
        return 0
    if args.check:
        clean, changed, reason = scrub_persona_leak(args.check)
        print(f"changed={changed} reason={reason!r}\n{clean}")
        return 0
    if args.selftest:
        return selftest()
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
