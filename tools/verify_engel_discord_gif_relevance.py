#!/usr/bin/env python3
"""Verify Discord GIF choices are relevant and Discord GIF captions are honest (20260801).

THE INCIDENT this guards against, from the live log on CT246:
a guest pasted https://klipy.com/gifs/dental-orthodontics into VantaMoth #CHAT during an
active GIF war. Engel tokenized the URL slug into the query "dental orthodontics", asked
Giphy, and posted the file it got back under the caption:  Here you go — "dental
orthodontics".  The file was the August trending GIF: a beach umbrella captioned "happy
august". Nothing in the lane had ever compared a downloaded GIF to the ask -- acceptance
was byte-level only (magic bytes, >=30KB, >=160x100) -- and the same two minutes of
traffic show one file returned for five different queries and the dental file re-served
87 seconds later for "celestial showdown incoming". Search providers do not answer "no
results"; they answer with whatever is trending, so a result set proves nothing.

The caption is what made it a lie rather than a miss: it asserted the search string as a
description of a file nobody had checked.

Gates:
  1. Relevance    - an off-topic candidate is refused; a real match is accepted; an
                    unlabelled or generically-labelled candidate is refused as unprovable.
  2. Search lane  - a provider whose whole result set is off topic counts as finding
                    nothing, and the search moves to the next provider instead of
                    serving filler.
  3. Query        - URL/meta noise is stripped BEFORE the token budget is spent, so the
                    words that describe the picture survive.
  4. Captions     - no caption quotes the internal search string, names a vendor, or
                    leaks an internal status token.
  5. GIF war      - a war volley is answered with a GIF, not narrated.
  6. Scoping      - an inherited topic is per channel and is never spoken as this
                    person's request.
  7. Training     - a media turn is training-eligible only when relevance was verified.

The bridge cannot be imported here (it needs the `discord` package, which lives on
CT246), so the pure functions are lifted out of the source with ast and exercised for
real -- the same approach verify_engel_training_schedule.py uses.
"""
from __future__ import annotations

import ast
import asyncio
import importlib.util
import inspect
import logging
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "tools" / "engel_discord_bridge.py"

checks: list[dict[str, Any]] = []


def check(name: str, ok: bool, detail: str) -> None:
    checks.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": detail})


SOURCE = BRIDGE.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)
CHAT_SOURCE = (ROOT / "tools" / "engel_main_server_chat_http_service.py").read_text(encoding="utf-8")
GROK_SOURCE = (ROOT / "tools" / "engel_grok_cli_bridge_http_service.py").read_text(encoding="utf-8")

WANTED = {
    "GIF_QUERY_STOPWORDS",
    "META_QUERY_WORDS",
    "GIF_MATCH_STOPWORDS",
    "_URL_RE",
    "_looks_like_asset_id",
    "_readable_url_topic",
    "_urls_to_topics",
    "gif_query_terms",
    "gif_candidate_matches",
    "gif_text_is_blocked_gay",
    "_GIF_ALLOWED_LESBIAN_RE",
    "_GIF_BLOCKED_GAY_RE",
    "_RAIDERS_RE",
    "_RAIDERS_FALSE_RE",
    "gif_text_is_raiders_team",
    "extract_gif_query",
    "fetch_real_gifs",
    "_GIF_BLOCKED_DEMOCRAT_RE",
    "gif_text_is_blocked_democrat",
    "gif_text_is_house_blocked",
}
LIFT_ORDER = (
    "GIF_QUERY_STOPWORDS",
    "META_QUERY_WORDS",
    "GIF_MATCH_STOPWORDS",
    "_URL_RE",
    "_looks_like_asset_id",
    "_readable_url_topic",
    "_urls_to_topics",
    "gif_query_terms",
    "_GIF_ALLOWED_LESBIAN_RE",
    "_GIF_BLOCKED_GAY_RE",
    "gif_text_is_blocked_gay",
    "_RAIDERS_RE",
    "_RAIDERS_FALSE_RE",
    "gif_text_is_raiders_team",
    "gif_candidate_matches",
    "extract_gif_query",
    "_GIF_BLOCKED_DEMOCRAT_RE",
    "gif_text_is_blocked_democrat",
    "gif_text_is_house_blocked",
    "fetch_real_gifs",
)
lifted: dict[str, ast.stmt] = {}
for node in TREE.body:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in WANTED:
        lifted[node.name] = node
    elif isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in WANTED:
                lifted[target.id] = node

missing = sorted(WANTED - set(lifted))
check("bridge_exposes_the_relevance_api", not missing, f"missing from the bridge: {missing or 'none'}")


# --- exercise the lifted code for real -------------------------------------------------
class _FakeResponse:
    async def __aenter__(self) -> "_FakeResponse":
        return self

    async def __aexit__(self, *exc: Any) -> bool:
        return False


class _FakeSession:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.args = args
        self.kwargs = kwargs

    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, *exc: Any) -> bool:
        return False

    def get(self, *args: Any, **kwargs: Any) -> _FakeResponse:
        return _FakeResponse()


class _FakeAiohttp:
    ClientSession = _FakeSession

    @staticmethod
    def ClientTimeout(**kwargs: Any) -> dict[str, Any]:
        return kwargs


ns: dict[str, Any] = {
    "re": re,
    "logging": logging,
    "asyncio": asyncio,
    "aiohttp": _FakeAiohttp,
    "Path": Path,
    "Any": Any,
    "__builtins__": __builtins__,
}
for name in LIFT_ORDER:
    node = lifted.get(name)
    if node is not None:
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(BRIDGE), "exec"), ns)

matches = ns["gif_candidate_matches"]
extract = ns["extract_gif_query"]
blocked_gay = ns["gif_text_is_blocked_gay"]
raiders_team = ns["gif_text_is_raiders_team"]

# 1. relevance --------------------------------------------------------------------------
check(
    "refuses_the_happy_august_gif_for_a_dental_ask",
    matches("dental orthodontics", "happy august beach umbrella cats flamingo") is False,
    "THE regression: the exact file and query from the live incident must not count as a match",
)
check(
    "accepts_a_genuine_match",
    matches("dental orthodontics", "dentist chair orthodontics braces smile") is True,
    "a result the provider itself describes with the asked-for words is a match",
)
check(
    "accepts_an_inflected_match",
    matches("orthodontic braces", "orthodontics brace tightening") is True,
    "prefix matching so 'orthodontic' matches 'orthodontics' without demanding exact forms",
)
check(
    "refuses_an_unlabelled_candidate",
    matches("dental orthodontics", "") is False,
    "a candidate the provider will not describe is unprovable, so it is refused",
)
check(
    "refuses_a_generically_labelled_candidate",
    matches("dental orthodontics", "funny reaction gif trending animated best") is False,
    "generic filler words must not be able to satisfy any query",
)
check(
    "refuses_a_substring_coincidence",
    matches("war comeback", "beachwear summer") is False,
    "'war' must not match 'beachwear' -- prefix, not substring",
)
check(
    "empty_query_matches_nothing",
    matches("", "anything at all") is False,
    "with no meaningful ask there is nothing to prove a match against",
)

# 2. the search lane --------------------------------------------------------------------
fetch = ns["fetch_real_gifs"]
downloaded: list[str] = []


async def _fake_download(session: Any, url: str, tag: str) -> Path | None:
    downloaded.append(f"{tag}:{url}")
    return Path(f"/tmp/{tag}.gif")


ns["_download_gif"] = _fake_download


async def _tenor_all_off_topic(session: Any, query: str, limit: int) -> list[dict[str, str]]:
    return [
        {"url": "https://t/1.gif", "label": "happy august beach umbrella"},
        {"url": "https://t/2.gif", "label": "celestial showdown incoming"},
    ]


async def _giphy_has_a_match(session: Any, query: str, limit: int) -> list[dict[str, str]]:
    return [
        {"url": "https://g/filler.gif", "label": "happy august trending"},
        {"url": "https://g/real.gif", "label": "dentist orthodontics braces"},
    ]


async def _empty(session: Any, query: str, limit: int) -> list[dict[str, str]]:
    return []


ns["_gif_urls_tenor"] = _tenor_all_off_topic
ns["_gif_urls_giphy"] = _giphy_has_a_match
ns["_gif_urls_klipy"] = _empty
ns["_gif_urls_duckduckgo"] = _empty

paths, source = asyncio.run(fetch("dental orthodontics", 1))
check(
    "skips_a_provider_whose_results_are_all_off_topic",
    source == "giphy" and len(paths) == 1,
    f"tenor returned only filler and must be skipped; served from {source!r} with {len(paths)} file(s)",
)
check(
    "never_downloads_an_off_topic_candidate",
    all("filler" not in item and "/t/" not in item for item in downloaded),
    f"only on-topic candidates may be fetched; downloaded={downloaded}",
)

ns["_gif_urls_giphy"] = _tenor_all_off_topic
paths_none, source_none = asyncio.run(fetch("dental orthodontics", 1))
check(
    "returns_nothing_when_no_provider_is_on_topic",
    paths_none == [] and source_none == "",
    "with every provider off topic the lane reports finding nothing instead of serving filler",
)

# 3. query extraction -------------------------------------------------------------------
tenor_paste = extract("https://tenor.com/view/happy-august-beach-umbrella-gif-25839112")
check(
    "url_noise_is_stripped_before_the_token_budget",
    "view" not in tenor_paste.split() and "https" not in tenor_paste.split(),
    f"a pasted link must not spend the query budget on url words; got {tenor_paste!r}",
)
check(
    "the_slug_subject_survives_a_pasted_link",
    "umbrella" in tenor_paste or "beach" in tenor_paste,
    f"the words describing the picture must reach the query; got {tenor_paste!r}",
)
check(
    "klipy_slug_still_reads_cleanly",
    extract("https://klipy.com/gifs/dental-orthodontics") == "dental orthodontics",
    "the incident's own input still extracts the same topic -- the fix is the gate, not the parse",
)

# The "static GIFs, not the ones needed" report: a direct CDN file URL carries no topic,
# and tokenizing it produced the query "static ii <hash>" -- which DuckDuckGo then matched
# on the hash itself, so even the relevance gate passed the garbage.
cdn = extract("https://static.klipy.com/ii/c3a19a0b747a76e98651f2b9a3cca5ff/75/68/5o4dzsWM.gif")
check(
    "a_cdn_file_url_yields_no_topic",
    cdn == "",
    f"a bare CDN path is addressing, not a subject; got {cdn!r}",
)
check(
    "the_word_static_never_becomes_a_query",
    "static" not in cdn.split(),
    "the operator's report was literally the first token of the derived query",
)
check(
    "a_hash_never_becomes_a_query",
    not any(
        term in cdn for term in ("c3a19a0b747a76e98651f2b9a3cca5ff", "5o4dzswm")
    ),
    "searching the web for a checksum returns pages that echo the checksum back",
)
slug_url = extract("https://tenor.com/view/helicopter-boat-speedboat-party-like-a-boss-gif-14613144")
check(
    "a_share_url_still_yields_its_subject",
    "helicopter" in slug_url and "speedboat" in slug_url,
    f"slug links must keep working -- they are how a GIF war carries a topic; got {slug_url!r}",
)
mixed = extract("Haha thanks Lokal! https://tenor.com/view/wow-cool-kyle-broflovski-gif-21611432")
check(
    "human_text_beside_a_link_survives",
    "thanks" in mixed or "lokal" in mixed or "wow" in mixed,
    f"a person's own words must not be discarded with the url; got {mixed!r}",
)
check(
    "asset_ids_are_recognised",
    ns["_looks_like_asset_id"]("5o4dzswm") is True
    and ns["_looks_like_asset_id"]("krxagxvz") is True
    and ns["_looks_like_asset_id"]("c3a19a0b747a76e98651f2b9a3cca5ff") is True
    and ns["_looks_like_asset_id"]("orthodontics") is False
    and ns["_looks_like_asset_id"]("helicopter") is False,
    "hashes and CDN ids are refused while ordinary words are kept",
)
check(
    "duckduckgo_requires_an_actual_gif_file",
    'endswith(".gif")' in SOURCE,
    "the type:gif filter is an unverified positional string, so the file itself is checked",
)
check(
    "repeat_pictures_are_suppressed",
    "_drop_recently_sent" in SOURCE and "recent_media_digests" in SOURCE,
    "one file went out SIX times in a 60-turn stretch; a channel reads that as Engel being stuck",
)

# 4/5/6/7. source-level contracts --------------------------------------------------------
def _slice(start_marker: str, end_marker: str) -> str:
    start = SOURCE.find(start_marker)
    end = SOURCE.find(end_marker, start + 1) if start >= 0 else -1
    return SOURCE[start:end] if start >= 0 and end > start else ""


captions = _slice("# (20260801) Captions rewritten", "content = sanitize_discord_public_reply")
check(
    "caption_block_located",
    len(captions) > 200,
    "the caption block must stay findable for this gate to mean anything",
)
check(
    "no_caption_quotes_the_search_string",
    "{query}" not in captions,
    "quoting a scraped/inherited query is what turned a bad match into a false statement",
)
VENDOR_WORDS = ("grok", "giphy", "tenor", "klipy", "duckduckgo")
leaked_vendor = [word for word in VENDOR_WORDS if word in captions.casefold()]
check(
    "no_caption_names_a_vendor",
    not leaked_vendor,
    f"the style card forbids presenting as a vendor and the guest gate blocks the word: {leaked_vendor or 'clean'}",
)
STATUS_TOKENS = ("imagine_note", "needs_login", "imagine_busy", "no_media")
leaked_status = [token for token in STATUS_TOKENS if token in captions]
check(
    "no_caption_leaks_an_internal_status_token",
    not leaked_status,
    f"internal status strings must not be interpolated into public chat: {leaked_status or 'clean'}",
)

war = _slice('if _engage_reason == "gif_war":', "_note_engel_engaged")
check(
    "gif_war_answers_with_a_gif_not_a_sentence",
    "silent=True" in war,
    "the war branch's own note says no chat detour; it must call the media lane silently",
)

check(
    "media_topic_is_scoped_per_channel",
    "_channel_media_query" in SOURCE and "last_media_query_by_channel" in SOURCE,
    "one global last_media_query let another server's topic be quoted at a guest as their own ask",
)
check(
    "an_inherited_topic_is_not_re_saved",
    "if not query_is_inherited:" in SOURCE,
    "re-saving a fallback as the remembered topic is why a stale query never aged out",
)
check(
    "media_turns_train_only_when_relevance_was_verified",
    "media_relevance_verified" in SOURCE
    and "training_sample_eligible=media_relevance_verified" in SOURCE,
    "a wrong GIF and its caption must not enter the training corpus as a good example",
)
check(
    "caption_banks_rotate",
    "pick_varied_line(LIBRARY_CAPTIONS" in SOURCE and "pick_varied_line(FOUND_CAPTIONS" in SOURCE,
    "GIF captions must rotate instead of repeating one stock line",
)
check(
    "favicon_lane_exists",
    "def prompt_requests_favicon(" in SOURCE and "async def send_favicon_response(" in SOURCE,
    "Discord must have a local favicon send path",
)
check(
    "talk_favicon_query_casefolds_a_string",
    'query = " ".join((str(reply or ""), str(prompt or ""))).casefold()' in SOURCE
    and '(str(reply or ""), str(prompt or "")).casefold()' not in SOURCE,
    "favicon query must casefold the joined string, not the (reply, prompt) tuple",
)
check(
    "talk_replies_attach_gif_and_library_favicon",
    "async def collect_talk_reply_files(" in SOURCE
    and "def pick_talk_reply_favicon(" in SOURCE
    and "icon = pick_talk_reply_favicon(" in SOURCE
    and "await send_chunks(message, reply, files=talk_files or None)" in SOURCE
    and "TALK_STYLE_RULE" in SOURCE
    and "Do not repeat the same Engel star every turn" in SOURCE
    and "not a template" in SOURCE
    and "Joshua-asks" in SOURCE
    and "repair_template_talk_reply" in SOURCE
    and "talk_icon = talk_reply_favicon_path()" not in SOURCE,
    "Talk replies attach a GIF plus a rotated library favicon, not the same Engel star",
)
check(
    "talk_replies_do_not_paste_gif_urls",
    "Do not paste GIF URLs, klipy/tenor/giphy links" in SOURCE
    and "attaches one relevant GIF and one library favicon" in SOURCE,
    "Talk style must attach files instead of dumping vendor GIF URLs",
)
check(
    "engel_owns_a_favicon_library",
    "def favicon_catalog_dir(" in SOURCE
    and 'favicon_library_dir() / "library"' in SOURCE
    and "def pick_talk_reply_favicon(" in SOURCE,
    "Engel AI Main must keep its own favicon catalog for Discord chat",
)
_lib = ROOT / "runtime" / "favicons" / "library"
_lib_pngs = list(_lib.glob("*.png")) if _lib.is_dir() else []
_lib_manifest = _lib / "MANIFEST.json"
check(
    "favicon_library_has_a_big_local_set",
    len(_lib_pngs) >= 80 and _lib_manifest.is_file(),
    f"Engel favicon library should hold 80+ local PNGs; have {len(_lib_pngs)}",
)
check(
    "discord_turns_persist_for_recall",
    "recall_eligible" in SOURCE
    and "ensure_standing_recall_facts" in SOURCE
    and "STANDING_RECALL_FACTS" in SOURCE
    and 'if route != "discord_chat_model":' not in SOURCE
    and "persistent_memory_mirror" in SOURCE,
    "Every Discord turn must be appended to persistent chat memory for recall",
)
check(
    "owner_stills_go_to_chat_and_tasks_use_build_lane",
    "def discord_owner_prompt_is_task(" in SOURCE
    and "def describe_image_bytes(" in SOURCE
    and 'payload["lane"] = "build"' in SOURCE
    and 'payload["discord_owner_vision"] = True' in SOURCE
    and "Joshua attaching a PNG/JPG is an order to look" in SOURCE
    and "Still PNG/JPG from Josh, Sub-Engel" in SOURCE
    and "own first-person thoughts" in SOURCE
    and "http_timeout_default" in SOURCE,
    "Josh Discord screenshots must be viewed and Josh Discord orders must use the work lane",
)
check(
    "peer_stills_are_looked_at_not_cannot_see",
    "include what is on the picture in the brainstorm" in SOURCE
    and "cannot see - acknowledge it in passing" not in SOURCE
    and 'payload["discord_vision"] = True' in SOURCE
    and "Look at the image and talk about what is on it" in SOURCE,
    "Sub-Engel stills must be looked at during Discord brainstorm, not told cannot see",
)
check(
    "chat_service_views_images_and_runs_owner_discord_tasks",
    "def _describe_stored_chat_image(" in CHAT_SOURCE
    and "ct_discord_owner_task" in CHAT_SOURCE
    and "ct_discord_owner_vision" in CHAT_SOURCE
    and "ct_main_ui_vision" in CHAT_SOURCE
    and "def _request_needs_vision_lane(" in CHAT_SOURCE
    and "discord_vision" in CHAT_SOURCE
    and "def _vision_lane_local_reply(" in CHAT_SOURCE
    and "ct_vision_notes_fallback" in CHAT_SOURCE
    and "def _grok_inline_image_attachments(" in CHAT_SOURCE
    and "Visible image notes:" in CHAT_SOURCE,
    "CT246 chat must add image notes and send Josh Discord work/vision turns to Grok first",
)
check(
    "grok_cli_ingests_discord_image_bytes",
    "def ingest_inline_images(" in GROK_SOURCE
    and "def pull_ct246_stored_images(" in GROK_SOURCE
    and "def _image_prompt_block(" in GROK_SOURCE
    and "CHAT_ATTACHMENTS_DIR" in GROK_SOURCE
    and "JSON body exceeds image ingest cap" in GROK_SOURCE,
    "ROG Grok CLI must write Discord image bytes into runtime/chat_attachments and look at them",
)
check(
    "library_picks_category_siblings",
    "def _library_assets_for_entry(" in SOURCE and "variant_seed" in SOURCE,
    "the local GIF library must be able to rotate same-category assets",
)
check(
    "posted_gifs_do_not_enter_chat",
    "def posted_gif_should_skip_chat(" in SOURCE
    and "incoming gif ignored for chat" in SOURCE
    and "skip_gif_media" in SOURCE,
    "a posted GIF must not be forwarded to /chat as a test/review attachment",
)
check(
    "gif_share_is_joined_silently",
    "def incoming_gif_share_should_reply(" in SOURCE
    and 'send_gif_response(' in SOURCE
    and '"gif share comeback"' in SOURCE
    and "silent=True" in SOURCE,
    "Engel must join a GIF share with a silent GIF, not a chat paragraph",
)
check(
    "share_comeback_uses_unused_library",
    "def unused_share_library_gifs(" in SOURCE
    and "def build_fresh_made_gifs(" in SOURCE
    and "is_comeback = _is_gif_share_or_war_comeback(prompt)" in SOURCE
    and "unused_share_library_gifs(" in SOURCE,
    "GIF share/war comeback must rotate unused library files and must not draw homemade cards",
)
check(
    "repeat_drop_refills_without_same_made_gif",
    "variant_seed + 41" not in SOURCE
    and "build_fresh_made_gifs(" in SOURCE
    and "Keep posting" in SOURCE,
    "A repeat drop must refill from unused library or a fresh card, not the same +41 homemade GIF",
)
check(
    "named_library_gifs_beat_homemade",
    "def library_gifs_by_filename(" in SOURCE
    and "return library_gifs_by_filename(" in SOURCE,
    "A named library file must be used before Engel draws a homemade card",
)
check(
    "unused_library_before_homemade_on_miss",
    "unused_share_library_gifs(" in SOURCE
    and "build_fresh_made_gifs(" in SOURCE,
    "When search misses, an unused real library GIF must be posted before a homemade card",
)
check(
    "gif_provider_api_keys_accepted",
    "def gif_provider_api_key(" in SOURCE
    and 'gif_provider_api_key("ENGEL_TENOR_API_KEY", "TENOR_API_KEY")' in SOURCE
    and 'gif_provider_api_key("ENGEL_GIPHY_API_KEY", "GIPHY_API_KEY")' in SOURCE
    and 'gif_provider_api_key("ENGEL_KLIPY_API_KEY", "KLIPY_API_KEY")' in SOURCE,
    "Tenor/Giphy/Klipy must accept Engel env names and standard provider API key names",
)
check(
    "share_and_ask_use_gif_provider_api",
    "fetch_real_gifs(" in SOURCE
    and "adult=discord_adult_room_enabled(message)" in SOURCE
    and "Standard GIF APIs first" in SOURCE
    and "Follow the incoming GIF's theme" in SOURCE,
    "Share joins and GIF asks must call Tenor/Giphy/Klipy before homemade cards",
)
check(
    "share_join_never_posts_homemade_card",
    "Share joins stay on provider GIFs" in SOURCE
    and "Discord share join skipped: no real GIF" in SOURCE
    and "engel_gif_library" in SOURCE,
    "A GIF share join must not post a homemade Custom for Engel / Server Runtime card",
)
check(
    "share_join_retries_after_repeat",
    "want = max(count, 8)" in SOURCE
    and "queries[:4]" in SOURCE
    and "def _remember_sent_media(" in SOURCE
    and "if posted:" in SOURCE
    and "media_variant_seed" in SOURCE,
    "A share join must fetch unused provider GIFs and not stay silent on the first repeat",
)
check(
    "home_discord_allows_adult_gifs",
    'rating": "r" if adult else "pg-13"' in SOURCE
    and 'contentfilter": "off" if adult else "medium"' in SOURCE
    and "18+ adult room" in SOURCE
    and "Never involve anyone under 18" in SOURCE,
    "The home Discord room must request adult provider GIFs and still forbid anyone under 18",
)
check(
    "share_defaults_to_49ers_not_star_wars_cards",
    '"49ers"' in SOURCE
    and "star_wars_meme_realistic" in SOURCE
    and "def _library_gif_is_blocked(" in SOURCE,
    "Share/generic GIFs must search 49ers and must not serve primitive Star Wars meme cards",
)
check(
    "adult_room_uses_vulgar_gif_likes",
    "ENGEL_ADULT_LIKED_GIF_THEMES" in SOURCE
    and "middle finger" in SOURCE
    and "_liked_gif_themes" in SOURCE
    and "adult=discord_adult_room_enabled(message)" in SOURCE,
    "The 18+ home room must search vulgar provider GIFs, not only clean 49ers clips",
)
check(
    "share_join_follows_theme_or_engel_like",
    "def share_theme_from_message(" in SOURCE
    and "def share_join_search_query(" in SOURCE
    and "ENGEL_LIKED_GIF_THEMES" in SOURCE
    and "offset = abs(hash(str(query))) % len(relevant)" in SOURCE,
    "Share joins must follow the incoming theme or pick one of Engel's likes, and rotate provider hits",
)
check(
    "raiders_gifs_are_roasted",
    "def incoming_is_raiders_gif(" in SOURCE
    and "async def roast_raiders_gif(" in SOURCE
    and "incoming_is_raiders_gif(message)" in SOURCE
    and "RAIDERS_ROASTS" in SOURCE
    and "RAIDERS_ROAST_GIFS" in SOURCE
    and "adult=True" in SOURCE,
    "A posted Raiders GIF must get a vulgar roast and a vulgar adult GIF",
)
check(
    "gay_themed_gifs_are_blocked",
    "def gif_text_is_blocked_gay(" in SOURCE
    and "not gif_text_is_house_blocked" in SOURCE
    and "_GIF_ALLOWED_LESBIAN_RE" in SOURCE
    and blocked_gay("gay pride two men kissing") is True
    and blocked_gay("yaoi twink bara") is True
    and blocked_gay("male couple guys kissing") is True
    and blocked_gay("gay_pride.gif") is True,
    "Provider GIF results must drop gay/male-male labels/URLs",
)
check(
    "lesbian_gifs_are_kept",
    blocked_gay("lesbian kiss girls kissing") is False
    and blocked_gay("lesbian pride parade") is False
    and blocked_gay("wlw sapphic girl on girl") is False
    and blocked_gay("two women kissing") is False,
    "Lesbian GIFs stay — house rule is no gay/male-male, not no women",
)
check(
    "clean_adult_gifs_are_not_blocked_as_gay",
    blocked_gay("middle finger fuck you 49ers") is False
    and blocked_gay("nsfw reaction dirty laugh") is False,
    "Vulgar 18+ GIFs that are not gay/male-male must still pass",
)
check(
    "nfl_raiders_gifs_are_blocked",
    raiders_team("lv raiders nation") is True
    and raiders_team("las vegas raiders.gif") is True
    and raiders_team("silver and black") is True
    and raiders_team("just win baby") is True,
    "NFL Raiders labels must never be posted",
)
check(
    "tomb_raider_is_not_nfl_raiders",
    raiders_team("tomb raider lara") is False
    and raiders_team("raiders of the lost ark") is False,
    "Tomb Raider and Raiders of the Lost Ark are not the NFL team",
)
check(
    "49ers_gifs_are_not_raiders",
    raiders_team("sf 49ers celebration") is False
    and raiders_team("niners faithful") is False,
    "49ers GIFs must still be allowed",
)
check(
    "fetch_real_gifs_drops_raiders_results",
    "if gif_text_is_house_blocked(query):" in SOURCE
    and 'not gif_text_is_house_blocked(item.get("label", ""), item.get("url", ""))' in SOURCE
    and "gif_text_is_raiders_team" in SOURCE
    and '    "49ers fuck the raiders"' not in SOURCE,
    "Provider search must refuse NFL Raiders queries and result labels; roast search must not ask for raiders",
)
check(
    "raiders_house_rule_is_in_chat_memory",
    "RAIDERS_HOUSE_RULE" in SOURCE
    and "Never post a Las Vegas or Oakland Raiders GIF" in SOURCE,
    "Chat prompt memory must carry the 49ers/Raiders house rule",
)

_png_b64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
_ingest_ok = False
_ingest_detail = "grok ingest not exercised"
try:
    grok_path = ROOT / "tools" / "engel_grok_cli_bridge_http_service.py"
    spec = importlib.util.spec_from_file_location("engel_grok_cli_bridge_http_service", grok_path)
    grok_mod = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(grok_mod)
    ingested = grok_mod.ingest_inline_images(
        {
            "attachments": [
                {
                    "name": "discord_vision_selftest.png",
                    "kind": "image",
                    "mime_type": "image/png",
                    "inline_base64": _png_b64,
                }
            ]
        }
    )
    _ingest_ok = (
        bool(ingested)
        and ingested[0].is_file()
        and ingested[0].read_bytes().startswith(b"\x89PNG")
        and "chat_attachments" in str(ingested[0])
    )
    _ingest_detail = str(ingested[0]) if ingested else "no file written"
    for path in ingested:
        try:
            path.unlink()
        except OSError:
            pass
except Exception as exc:
    _ingest_ok = False
    _ingest_detail = str(exc)
check(
    "grok_ingest_writes_png_into_chat_attachments",
    _ingest_ok,
    "Discord PNG bytes must land under runtime/chat_attachments: " + _ingest_detail,
)

passed = sum(1 for item in checks if item["status"] == "PASS")
failed = [item for item in checks if item["status"] != "PASS"]
for item in checks:
    print(f"{item['status']} {item['name']} :: {item['detail']}")
print(f"\n{passed}/{len(checks)} checks passed")
print("verify_engel_discord_gif_relevance: " + ("GREEN" if not failed else "RED"))
raise SystemExit(0 if not failed else 1)
