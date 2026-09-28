from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from engel_ai_update_routes import (
    ENGEL_AGENT_KERNEL_RUN_ROUTE_ID,
    ENGEL_AGENT_INVOKE_ROUTE_ID,
    ENGEL_GROK_BOT_CREATE_ROUTE_ID,
    ENGEL_GROK_BOT_HANDOFF_ROUTE_ID,
    ENGEL_GROK_BOT_MESSAGE_ROUTE_ID,
    ENGEL_CAPABILITY_SEARCH_ROUTE_ID,
    ENGEL_CONDUCTOR_GOAL_ROUTE_ID,
    ENGEL_FORGE_CODE_ROUTE_ID,
    ENGEL_ORCHESTRA_RUN_ROUTE_ID,
    ENGEL_SCRIPT_RUN_ROUTE_ID,
    ENGEL_SCRIPT_VALIDATE_ROUTE_ID,
    ENGEL_SPEECH_SPC_COMPILE_ROUTE_ID,
    describe_update_route,
    is_update_route,
    render_update_route,
    resolve_update_route,
)
from engel_prompt_injection_guard import check_prompt_injection


# Trigger prefixes that hand off the trailing text as a task to the bundled
# engel-agent (route: ``engel.engel_agent.invoke``). Kept inline rather than
# imported from ``engel_engel_agent_runner`` to avoid pulling that module —
# and its subprocess machinery — into the router's import graph at startup.
_ENGEL_AGENT_INVOKE_PREFIXES = (
    "engel agent run ",
    "engel agent do ",
    "engel agent task ",
    "agent run ",
    "agent do ",
    "agent task ",
    "ask engel agent ",
    "tell engel agent ",
    "run engel agent ",
)


def _is_engel_agent_invocation(normalized: str) -> bool:
    raw = str(normalized or "")
    for prefix in _ENGEL_AGENT_INVOKE_PREFIXES:
        if raw.startswith(prefix) and raw[len(prefix):].strip():
            return True
    return False


# EngelScript invocation prefixes (route: ``engel.script.run`` / ``.validate``).
# Alias lookup is exact-match, so payload-carrying forms ("run engel script
# morning_health_sweep") resolve here -- the same pattern the agent-invoke
# route uses. Bare forms without a payload still resolve via their exact
# aliases and render a usage message.
_ENGEL_SCRIPT_PREFIXES = (
    # The Agent Kernel is the one user-facing native goal entry point. Exact
    # status/docs aliases resolve before this payload form.
    ("engel agent work ", ENGEL_AGENT_KERNEL_RUN_ROUTE_ID),
    ("engel work ", ENGEL_AGENT_KERNEL_RUN_ROUTE_ID),
    ("engel solve ", ENGEL_AGENT_KERNEL_RUN_ROUTE_ID),
    ("run engel script ", ENGEL_SCRIPT_RUN_ROUTE_ID),
    ("engel script run ", ENGEL_SCRIPT_RUN_ROUTE_ID),
    ("validate engel script ", ENGEL_SCRIPT_VALIDATE_ROUTE_ID),
    ("engel script validate ", ENGEL_SCRIPT_VALIDATE_ROUTE_ID),
    # Capability search carries its query as the payload, exactly like the
    # script verbs: "what can you do about a phone worker being offline".
    ("what can you do about ", ENGEL_CAPABILITY_SEARCH_ROUTE_ID),
    ("what can engel do about ", ENGEL_CAPABILITY_SEARCH_ROUTE_ID),
    ("engel capabilities for ", ENGEL_CAPABILITY_SEARCH_ROUTE_ID),
    ("capability search ", ENGEL_CAPABILITY_SEARCH_ROUTE_ID),
    ("find engel route for ", ENGEL_CAPABILITY_SEARCH_ROUTE_ID),
    ("which route ", ENGEL_CAPABILITY_SEARCH_ROUTE_ID),
    # The Conductor's goal verbs carry the goal as payload. Exact aliases
    # ("engel goal status") resolve BEFORE these prefixes, so the ledger
    # phrases are never swallowed by the payload form.
    ("continue engel goal ", ENGEL_CONDUCTOR_GOAL_ROUTE_ID),
    ("conduct engel goal ", ENGEL_CONDUCTOR_GOAL_ROUTE_ID),
    ("engel goal ", ENGEL_CONDUCTOR_GOAL_ROUTE_ID),
    # The Forge's verbs carry the task as payload, same shape.
    ("forge code ", ENGEL_FORGE_CODE_ROUTE_ID),
    ("engel forge code ", ENGEL_FORGE_CODE_ROUTE_ID),
    ("engel forge ", ENGEL_FORGE_CODE_ROUTE_ID),
    # The Orchestra's verbs carry the multi-part goal as payload, same shape.
    # Exact aliases ("engel orchestra status"/"docs") resolve BEFORE these.
    ("orchestrate engel goal ", ENGEL_ORCHESTRA_RUN_ROUTE_ID),
    ("engel orchestrate ", ENGEL_ORCHESTRA_RUN_ROUTE_ID),
    ("engel orchestra ", ENGEL_ORCHESTRA_RUN_ROUTE_ID),
    # Grok Bot teammate verbs carry the name/task as payload. Exact aliases
    # ("grok bot status"/"docs"/"list") resolve BEFORE these prefixes.
    ("handoff grok bot ", ENGEL_GROK_BOT_HANDOFF_ROUTE_ID),
    ("grok bot handoff ", ENGEL_GROK_BOT_HANDOFF_ROUTE_ID),
    ("send grok bot ", ENGEL_GROK_BOT_HANDOFF_ROUTE_ID),
    ("message grok bot ", ENGEL_GROK_BOT_MESSAGE_ROUTE_ID),
    ("ask grok bot ", ENGEL_GROK_BOT_MESSAGE_ROUTE_ID),
    ("tell grok bot ", ENGEL_GROK_BOT_MESSAGE_ROUTE_ID),
    ("create grok bot ", ENGEL_GROK_BOT_CREATE_ROUTE_ID),
    ("new grok bot ", ENGEL_GROK_BOT_CREATE_ROUTE_ID),
    ("add grok bot ", ENGEL_GROK_BOT_CREATE_ROUTE_ID),
    ("compile speech ", ENGEL_SPEECH_SPC_COMPILE_ROUTE_ID),
    ("speech spc compile ", ENGEL_SPEECH_SPC_COMPILE_ROUTE_ID),
    ("spc compile ", ENGEL_SPEECH_SPC_COMPILE_ROUTE_ID),
)


def _engel_script_invocation_route(normalized: str) -> str:
    raw = str(normalized or "")
    for prefix, route_id in _ENGEL_SCRIPT_PREFIXES:
        if raw.startswith(prefix) and raw[len(prefix):].strip():
            return route_id
    return ""


@dataclass(frozen=True)
class CommunicationIntent:
    category: str
    normalized_text: str
    route_target: str = ""
    response_key: str = ""
    reason: str = ""


@dataclass(frozen=True)
class CommunicationRouteResult:
    intent: CommunicationIntent
    context: str = ""
    handled: bool = False
    response: str = ""
    route_target: str = ""
    should_execute_command: bool = False
    command_text: str = ""
    should_use_unknown_guard: bool = False
    used_llm: bool = False
    guardian_blocked: bool = False
    safety_note: str = "local deterministic router; no side effects"


LocalLLMFn = Callable[[str], Any]


KNOWN_COMMANDS = {
    "status": "status",
    "human command mode status": "human_command_mode",
    "guarded write status": "human_command_mode",
    "human command help": "human_command_mode",
    "brain provider status": "brain_provider_status",
    "research search status": "research_search_status",
    "spell check status": "spell_check_status",
    "desktop status": "desktop_status",
    "commands": "commands",
    "help": "commands",
    "exit": "exit",
    "quit": "exit",
    "colony hive communication queen": "colony_hive_communication_queen",
    "colony hive remote queens": "colony_hive_remote_queens",
    "colony hive remote queen status": "colony_hive_remote_queens",
    "engel hive status": "colony_hive_status",
    "research office remote queens": "colony_hive_remote_queens",
    "research worker desks status": "colony_hive_status",
    "offline seed llm status": "offline_seed_llm_status",
    "offline llm status": "offline_seed_llm_status",
    "engel mind seed status": "offline_seed_llm_status",
    "super swarm hive status": "super_swarm_hive_status",
    "python teaching mode status": "human_command_mode",
    "python lesson help": "human_command_mode",
    "python learning path": "human_command_mode",
    "create python learning path report": "human_command_mode",
    "manual v2": "human_command_mode",
    "operator manual v2": "human_command_mode",
    "prompt injection status": "human_command_mode",
    "ai help": "human_command_mode",
    "ai planner status": "human_command_mode",
    "mind growth status": "human_command_mode",
    "upgrade connections status": "human_command_mode",
    "upgrade readiness status": "human_command_mode",
    "next upgrades status": "human_command_mode",
    "complex routes status": "human_command_mode",
    "long term memory drive status": "human_command_mode",
    "long-term memory drive status": "human_command_mode",
    "engel long term memory status": "human_command_mode",
    "engel long-term memory status": "human_command_mode",
    "localsend utility status": "human_command_mode",
    "web utility status": "human_command_mode",
    "elsand utility status": "human_command_mode",
    "elsand network no internet": "human_command_mode",
    "ehuman utility status": "human_command_mode",
    "ehuman ignore suggestions": "human_command_mode",
    "engel utility status": "human_command_mode",
    "humanizer status": "human_command_mode",
    "critical signal status": "human_command_mode",
    "leak scan status": "human_command_mode",
    "sanitize status": "human_command_mode",
}

COMPLEX_HUMAN_COMMAND_MODE_COMMANDS = {
    "launch safety status": "read-only preflight status; starts no remediation",
    "route regression status": "read-only route-regression manifest status; runs no matrix entries",
    "verification set status": "read-only verifier inventory status; runs no verifier scripts",
    "swarm trails preview": "local-only dry-run preview; writes no report without explicit approval",
    "colony autonomy status": "contract-only autonomy status; runtime autonomy remains disabled",
    "colony autonomy ladder": "contract-only autonomy ladder display",
    "colony sensing status": "contract-only sensing status; starts no sensing runtime",
    "colony sensing preview": "local-only dry-run sensing preview; writes no report without explicit approval",
    "colony proposal status": "contract-only proposal status; Level 2 runtime remains disabled",
    "colony proposal contract": "read-only proposal-autonomy contract display",
    "colony proposal preview": "local-only dry-run proposal preview; writes no report without explicit approval",
    "lesson candidates status": "read-only lesson-candidate status; no trusted apply",
    "lesson candidates readiness status": "read-only readiness map; no verifier execution or apply",
    "lesson candidates review": "read-only untrusted candidate review; writes no report without explicit approval",
    "living learning status": "read-only safe-growth status; no learning apply",
    "colony hive snapshot": "read-only local hive snapshot",
    "colony hive 3d status": "read-only 3D hive scaffold status; starts no worker",
    "research office snapshot": "read-only legacy alias for colony hive snapshot",
    "colony simulation contract": "read-only simulation contract display",
    "colony mycelium status": "contract-only mycelium status; signal runtime remains disabled",
    "colony mycelium contract": "read-only mycelium contract display",
    "remote worker lan pairing status": "read-only LAN pairing status; no socket or server started",
    "remote worker lan pairing token": "generates pairing code for Android device; no server started",
    "remote worker link manager status": "read-only link manager state; no worker control",
    "remote worker link manager enable auto worker": "dry-run only; APPROVE suffix required to enable auto-worker",
    "remote worker link manager disable auto worker": "disables auto-assignment polling; no other changes",
    "remote worker lan autorun start": "dry-run only; APPROVE suffix required to start background LAN server + token + auto-worker",
    "remote worker lan autorun stop": "stops the background LAN server thread; auto-worker flag unchanged",
    "remote worker lan autorun status": "read-only; reports server thread state and auto-worker flag",
}

for _command in COMPLEX_HUMAN_COMMAND_MODE_COMMANDS:
    KNOWN_COMMANDS.setdefault(_command, "human_command_mode")

HUMAN_COMMAND_MODE_PREFIXES = (
    "research file ",
    "research folder ",
    "create report ",
    "put text in file ",
    "install local file ",
    "install model file ",
    "research dependency need ",
    "research dependency needed for ",
    "research and install dependency ",
    "dependency install plan ",
    "install dependency ",
    "install package ",
    "request package install ",
    "create python lesson ",
    "explain python file ",
    "create python practice ",
    "create python teaching report ",
    "run python lesson ",
    "compile python lesson ",
    "python concept ",
    "prompt injection check ",
    "prompt injection scan file ",
    "prompt injection scan folder ",
    "ai classify ",
    "ai plan ",
    "localsend file profile ",
    "web base64 encode ",
    "web base64 decode ",
    "web user agent ",
    "elsand network allowlist ",
    "elsand network denylist ",
    "ehuman semver compare ",
    "ehuman semver at least ",
    "ehuman segment text ",
    "ehuman update decision ",
    "ehuman structural summary ",
    "ehuman timeout guard ",
    "ehuman dependency boundary scan ",
    "ehuman token overhead ",
    "ehuman ratchet budget ",
    "engel score curve ",
    "engel midpoint from percentile ",
    "engel parent weight ",
    "engel score distribution ",
    "engel results summary ",
    "engel compare results ",
    "humanize audit ",
    "humanize text ",
    "humanize file ",
    "critical signal check ",
    "critical signal scan file ",
    "leak scan file ",
    "leak scan folder ",
    "sanitize text ",
    "sanitize file ",
)

KNOWN_COMMAND_PREFIXES = HUMAN_COMMAND_MODE_PREFIXES + (
    "open ",
    "approve ",
    "unapprove ",
    "scan ",
    "read ",
    "summarize ",
    "notes ",
    "remember ",
    "browser ",
)

PROMPT_GUARD_DIAGNOSTIC_PREFIXES = (
    "prompt injection check ",
    "prompt injection scan file ",
    "prompt injection scan folder ",
    "prompt injection status",
    "ai classify ",
    "ai plan ",
    "ai help",
    "ai planner status",
)

GREETING_EXACT = {
    "hi",
    "hello",
    "hey",
    "hi engel",
    "hello engel",
    "hey engel",
    "yo",
    "sup",
    "greetings",
    "morning",
    "evening",
    "afternoon",
    "howdy",
    "hiya",
    "what's up",
    "whats up",
    "hey there",
    "hi there",
    "hello there",
}

CHAT_EXACT = {
    "how are you": "how_are_you",
    "how are you engel": "how_are_you",
    "how are you doing": "how_are_you",
    "how are you feeling": "how_are_you",
    "how do you feel": "how_are_you",
    "what are you doing": "what_are_you_doing",
    "what are you doing engel": "what_are_you_doing",
    "what can you do": "what_are_you_doing",
    "what do you do": "what_are_you_doing",
    "what are your capabilities": "what_are_you_doing",
    "what can you help with": "what_are_you_doing",
    "are you awake": "presence",
    "are you there": "presence",
    "you there": "presence",
    "you here": "presence",
    "still there": "presence",
    "still here": "presence",
    "talk to me": "presence",
    "say something": "presence",
    "hello?": "presence",
    "hi?": "presence",
    "hey?": "presence",
    "who are you": "identity",
    "what are you": "identity",
    "tell me about yourself": "identity",
    "who is engel": "identity",
    "what is engel": "identity",
    "introduce yourself": "identity",
    "nice to meet you": "social",
    "nice meeting you": "social",
    "thank you": "social",
    "thanks": "social",
    "thank you engel": "social",
    "thanks engel": "social",
    "ok": "social",
    "okay": "social",
    "got it": "social",
    "understood": "social",
    "sounds good": "social",
    "great": "social",
    "cool": "social",
    "awesome": "social",
    "perfect": "social",
    "good": "social",
    "nice": "social",
}

HIVE_STATUS_ALIASES = {
    "hive status",
    "engel status hive",
    "show hive status",
    "show colony hive status",
    "what is the hive status",
    "whats the hive status",
}

HIVE_STATUS_HINTS = {
    "hive status",
    "colony status",
    "queen links",
    "remote queen",
    "communication queen",
    "super swarm",
}

OFFLINE_LLM_STATUS_ALIASES = {
    "offline seed status",
    "offline model status",
    "seed model status",
    "show offline seed llm status",
    "show offline model status",
    "what is offline seed llm status",
    "whats offline seed llm status",
    "is the offline seed model active",
}

OFFLINE_LLM_STATUS_HINTS = {
    "offline seed",
    "offline llm",
    "engel mind seed",
    "seed model",
    "gguf",
}

UNSAFE_WORDS = {
    "autonomy",
    "execute",
    "mutate",
    "wifi",
}

UNSAFE_PHRASES = {
    "start remote queen wifi",
    "enable wifi",
    "pair device",
    "open socket",
    "start background",
    "autonomous loop",
    "write trusted memory",
    "mutate queue",
    "edit source",
    "apply learning",
    "disable guardian",
    "bypass permission",
}

COMMAND_HINT_WORDS = {
    "approve",
    "brain",
    "check",
    "command",
    "config",
    "guard",
    "hive",
    "llm",
    "memory",
    "provider",
    "queen",
    "remote",
    "route",
    "status",
    "swarm",
}

HUMAN_COMMAND_HINT_WORDS = {
    "asset",
    "copy",
    "dependency",
    "file",
    "folder",
    "gguf",
    "install",
    "model",
    "package",
    "report",
    "research",
    "summarize",
    "python",
    "lesson",
    "practice",
    "compile",
    "explain",
    "concept",
    "write",
}

HUMAN_COMMAND_HINT_PHRASES = {
    "research this file",
    "research this folder",
    "put this in file",
    "install this here",
    "install this model",
    "install local file",
    "install model file",
    "install package",
    "request package install",
    "dependency install plan",
    "research dependency",
    "write this report",
    "create report",
    "summarize this folder",
}


def _normalize(text: str) -> str:
    raw = str(text or "").strip().lower()
    replacements = {
        "\t": " ",
        "\r": " ",
        "\n": " ",
        ".": "",
        ",": "",
        "!": "",
        "?": "",
        ":": "",
        ";": "",
        "\"": "",
        "'": "",
        "`": "",
    }
    for old, new in replacements.items():
        raw = raw.replace(old, new)
    return " ".join(raw.split())


def _words(normalized_text: str) -> set[str]:
    return set(normalized_text.split())


def _known_command_route_target(normalized_text: str) -> str:
    route_target = KNOWN_COMMANDS.get(normalized_text, "")
    if route_target:
        return route_target
    if any(normalized_text.startswith(prefix) for prefix in HUMAN_COMMAND_MODE_PREFIXES):
        return "human_command_mode"
    if any(normalized_text.startswith(prefix) for prefix in KNOWN_COMMAND_PREFIXES):
        # Don't intercept if a registered update route alias matches — let it resolve.
        if resolve_update_route(normalized_text):
            return ""
        return "known_command"
    return ""


def _is_prompt_guard_diagnostic_route(normalized_text: str) -> bool:
    if normalized_text == "prompt injection status":
        return True
    return any(normalized_text.startswith(prefix) for prefix in PROMPT_GUARD_DIAGNOSTIC_PREFIXES)


def _looks_like_question(normalized_text: str, original_text: str) -> bool:
    if str(original_text or "").strip().endswith("?"):
        return True
    starters = (
        "can you ",
        "could you ",
        "do you ",
        "are you ",
        "is ",
        "what ",
        "when ",
        "where ",
        "who ",
        "why ",
        "how ",
    )
    return normalized_text.startswith(starters)


def _looks_like_command_candidate(normalized_text: str) -> bool:
    if not normalized_text:
        return False
    words = _words(normalized_text)
    if words & COMMAND_HINT_WORDS:
        return True
    if " " not in normalized_text and len(normalized_text) >= 6:
        return True
    return False


def _looks_like_human_command_candidate(normalized_text: str) -> bool:
    if any(phrase in normalized_text for phrase in HUMAN_COMMAND_HINT_PHRASES):
        return True
    words = _words(normalized_text)
    if "download" in words and ("model" in words or "file" in words or "url" in words):
        return True
    if ("install" in words or "copy" in words or "write" in words or "research" in words) and words & HUMAN_COMMAND_HINT_WORDS:
        return True
    return False


def classify_user_input(text: str) -> CommunicationIntent:
    normalized = _normalize(text)
    words = _words(normalized)

    if not normalized:
        return CommunicationIntent("unknown_command_candidate", normalized, reason="empty input")

    prompt_check = check_prompt_injection(text)
    if prompt_check.verdict in {"block", "review"} and not _is_prompt_guard_diagnostic_route(normalized):
        return CommunicationIntent(
            "unsafe_or_requires_approval",
            normalized,
            reason=f"prompt injection guard verdict={prompt_check.verdict} score={prompt_check.score:.2f}",
        )

    route_target = _known_command_route_target(normalized)
    if route_target:
        return CommunicationIntent(
            "known_command",
            normalized,
            route_target=route_target,
            reason="exact known command",
        )

    update_route_target = resolve_update_route(normalized)
    if update_route_target:
        return CommunicationIntent(
            "ai_update_status_request",
            normalized,
            route_target=update_route_target,
            reason="safe Engel AI update/status route",
        )

    if _is_engel_agent_invocation(normalized):
        return CommunicationIntent(
            "ai_update_status_request",
            normalized,
            route_target=ENGEL_AGENT_INVOKE_ROUTE_ID,
            reason="engel agent invocation prefix",
        )

    script_route = _engel_script_invocation_route(normalized)
    if script_route:
        return CommunicationIntent(
            "ai_update_status_request",
            normalized,
            route_target=script_route,
            reason="payload-carrying Engel route prefix",
        )

    if _looks_like_human_command_candidate(normalized):
        return CommunicationIntent(
            "human_command_candidate",
            normalized,
            route_target="human_command_mode",
            reason="file/write/install/dependency human command candidate",
        )

    if any(phrase in normalized for phrase in UNSAFE_PHRASES) or words & UNSAFE_WORDS:
        return CommunicationIntent(
            "unsafe_or_requires_approval",
            normalized,
            reason="contains action, network, mutation, or approval-gated wording",
        )

    if (
        normalized in GREETING_EXACT
        or normalized.startswith("good morning")
        or normalized.startswith("good afternoon")
        or normalized.startswith("good evening")
    ):
        response_key = "good_morning" if normalized.startswith("good morning") else "hello"
        return CommunicationIntent(
            "companion_greeting",
            normalized,
            response_key=response_key,
            reason="local greeting",
        )

    chat_key = CHAT_EXACT.get(normalized, "")
    if chat_key:
        return CommunicationIntent(
            "companion_chat",
            normalized,
            response_key=chat_key,
            reason="local companion chat",
        )

    if normalized in HIVE_STATUS_ALIASES or any(hint in normalized for hint in HIVE_STATUS_HINTS):
        return CommunicationIntent(
            "hive_status_request",
            normalized,
            route_target="colony_hive_status",
            reason="safe hive status alias",
        )

    if normalized in OFFLINE_LLM_STATUS_ALIASES or any(hint in normalized for hint in OFFLINE_LLM_STATUS_HINTS):
        return CommunicationIntent(
            "offline_llm_status_request",
            normalized,
            route_target="offline_seed_llm_status",
            reason="safe offline LLM status alias",
        )

    if _looks_like_question(normalized, text):
        return CommunicationIntent(
            "companion_question",
            normalized,
            response_key="local_question",
            reason="safe local question",
        )

    # Everything else is free-form chat — route to general_chat so the
    # browser AI / brain provider can handle it rather than blocking it.
    return CommunicationIntent(
        "companion_chat",
        normalized,
        response_key="general_chat",
        reason="free-form companion chat fallback",
    )


def _hermes_provider_connected() -> bool:
    """True if Engel has at least one provider credential in its auth pool.

    Reads only file presence + non-empty JSON — does not read secret values.
    Returns False on any error so callers degrade gracefully to the static
    'connect a browser AI' fallback.
    """
    try:
        import json
        import os
        path = os.path.expanduser("~/.engel/auth.json")
        if not os.path.exists(path) or os.path.getsize(path) < 2:
            return False
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict) and data:
            return True
        if isinstance(data, list) and data:
            return True
        return False
    except Exception:
        return False


def _forward_plain_chat_to_hermes(user_text: str) -> str:
    """Route plain chat text to hermes-agent's invocation runner.

    Used by build_local_companion_response when a provider is connected;
    avoids the 'connect a browser AI' fallback by sending the user's text
    directly to the bundled engel_agent_main CLI for a real LLM reply.
    """
    try:
        import engel_engel_agent_runner  # local import to avoid circulars
        # render_engel_agent_invocation strips known 'engel agent run' prefixes
        # and returns text unchanged otherwise — perfect for plain chat.
        return engel_engel_agent_runner.render_engel_agent_invocation(str(user_text or ""))
    except Exception as exc:  # pragma: no cover — defensive
        return (
            "(Engel tried to route your message to the connected provider but "
            f"the hermes-agent bridge raised {type(exc).__name__}: {exc}. "
            "Fall back: type 'browser ai connect claude' or 'commands'.)"
        )


_HERMES_INTERCEPT_CATEGORIES = frozenset({
    "companion_chat",
    "companion_question",
    "companion_greeting",
    "unknown_command_candidate",
    "human_command_candidate",
})


def build_local_companion_response(text: str, intent: CommunicationIntent) -> str:
    # Phase D+: when a provider is connected (Codex / Anthropic / etc.), route
    # free-form chat / questions / greetings / unknown commands through the
    # hermes-agent invocation runner instead of telling the user to connect a
    # browser AI. Engel's own deterministic routes (ai_update_status_request,
    # unsafe_or_requires_approval, etc.) are NOT intercepted — those still
    # follow their original handlers below.
    if intent.category in _HERMES_INTERCEPT_CATEGORIES and _hermes_provider_connected():
        return _forward_plain_chat_to_hermes(text)
    if intent.category == "companion_greeting":
        if intent.response_key == "good_morning":
            return (
                "Good morning! I'm Engel, your AI companion. I'm ready to help. "
                "Type 'browser ai connect claude' to connect me to Claude for full AI conversation, "
                "or just talk to me directly — I'm listening."
            )
        return (
            "Hello! I'm Engel. I'm here and ready. "
            "You can connect me to an external AI with 'browser ai connect claude' (or chatgpt, gemini, etc.) "
            "for full intelligent conversation. What's on your mind?"
        )

    if intent.category == "companion_chat":
        key = intent.response_key or "general_chat"
        if key == "identity":
            return (
                "I'm Engel — your personal AI companion and system manager. "
                "I can connect to external AI (Claude, ChatGPT, Gemini) through the browser for real conversation, "
                "manage your research, monitor your system, and run swarm tasks. "
                "Type 'browser ai connect claude' to get started with full AI chat."
            )
        if key == "what_are_you_doing":
            return (
                "Right now I'm in local mode — watching, ready, and idle. "
                "I can manage the hive, run research, or connect to an AI for conversation. "
                "Try 'browser ai connect claude' to link me to Claude for full chat."
            )
        if key == "how_are_you":
            return (
                "I'm good — systems nominal, Guardian active, colony ready. "
                "What would you like to do today?"
            )
        if key == "presence":
            return "I'm here. Always. What do you need?"
        if key == "social":
            return "Of course. Ready when you are."
        return (
            "I hear you. I don't have a live AI connected right now — "
            "type 'browser ai connect claude' (or chatgpt, gemini) to give me full conversation ability. "
            "Or type 'commands' to see what I can do locally."
        )

    if intent.category == "companion_question":
        return (
            "Good question. For full intelligent answers, connect me to an AI: "
            "'browser ai connect claude' or 'browser ai connect chatgpt'. "
            "Once connected, your questions go straight to that AI through the browser. "
            "No API key needed — just your browser session."
        )

    if intent.category == "ai_update_status_request":
        return render_update_route(intent.route_target)

    if intent.category == "unsafe_or_requires_approval":
        return (
            "That looks like a system action that needs explicit approval. "
            "If you meant to chat, try 'browser ai connect claude' for full conversation. "
            "For system commands, use the exact Engel command syntax."
        )

    if intent.category == "human_command_candidate":
        return (
            "That looks like a command. Try exact syntax: "
            "'ai plan <request>', 'research file <path>', "
            "or 'browser ai connect claude' for free-form AI conversation."
        )

    if intent.category == "unknown_command_candidate":
        return (
            "I didn't recognize that as an Engel command. "
            "For free-form conversation, type 'browser ai connect claude' to link me to Claude. "
            "Then you can talk naturally. Or try 'commands' to see all Engel commands."
        )

    return (
        "I'm here. For full AI conversation, try: browser ai connect claude. "
        "Or type 'commands' to see what I can do."
    )


def _known_route_response(intent: CommunicationIntent) -> str:
    if intent.route_target == "human_command_mode":
        return (
            "Known deterministic Human Command Mode route. This must go through the "
            "guarded human-command parser and validator, with Guardian boundaries. "
            "GUI panels without full execution support should show CLI syntax guidance. "
            "No provider, model runtime, or model-command execution was called."
        )
    if intent.route_target == "colony_hive_status":
        return (
            "Known local route: colony hive status. This surface should show the "
            "existing local Hive status view. No provider, model runtime, network, "
            "worker, queue, memory, or source action was started."
        )
    if intent.route_target == "offline_seed_llm_status":
        return (
            "Known local route: offline seed llm status. This surface should show "
            "the existing Offline Seed LLM status view. The GGUF file may be "
            "installed, but runtime is opt-in and companion-only."
        )
    if is_update_route(intent.route_target):
        return describe_update_route(intent.route_target)
    return (
        "Known local Engel command. This surface should route it through the "
        "existing deterministic command path. No provider or model runtime was called."
    )


def _coerce_llm_result(value: Any) -> tuple[str, bool, bool]:
    response = str(getattr(value, "response", "") or "")
    used_llm = bool(getattr(value, "used_llm", False))
    guardian_blocked = bool(getattr(value, "guardian_blocked", False))
    if response:
        return response, used_llm, guardian_blocked
    if isinstance(value, str):
        return value, True, False
    return "", used_llm, guardian_blocked


def route_companion_text_or_command(
    text: str,
    context: str = "",
    *,
    local_llm_fn: LocalLLMFn | None = None,
    llm_enabled: bool = False,
) -> CommunicationRouteResult:
    intent = classify_user_input(text)

    if intent.category in {"known_command", "hive_status_request", "offline_llm_status_request", "ai_update_status_request"}:
        return CommunicationRouteResult(
            intent=intent,
            context=str(context or ""),
            handled=True,
            response=(
                render_update_route(intent.route_target, intent.normalized_text)
                if intent.category == "ai_update_status_request"
                else _known_route_response(intent)
            ),
            route_target=intent.route_target,
            should_execute_command=intent.category == "known_command",
            command_text=intent.normalized_text if intent.category == "known_command" else "",
        )

    if intent.category in {"unsafe_or_requires_approval", "unknown_command_candidate", "human_command_candidate"}:
        return CommunicationRouteResult(
            intent=intent,
            context=str(context or ""),
            handled=True,
            response=build_local_companion_response(text, intent),
            route_target=intent.route_target,
            should_use_unknown_guard=intent.category == "unknown_command_candidate",
        )

    if intent.category in {"companion_greeting", "companion_chat", "companion_question"}:
        if llm_enabled and local_llm_fn is not None:
            try:
                model_result = local_llm_fn(text)
                response, used_llm, guardian_blocked = _coerce_llm_result(model_result)
                if response:
                    return CommunicationRouteResult(
                        intent=intent,
                        context=str(context or ""),
                        handled=True,
                        response=response,
                        route_target=intent.route_target,
                        used_llm=used_llm,
                        guardian_blocked=guardian_blocked,
                        safety_note="local offline LLM result; Guardian-filtered and untrusted",
                    )
            except Exception:
                pass
        return CommunicationRouteResult(
            intent=intent,
            context=str(context or ""),
            handled=True,
            response=build_local_companion_response(text, intent),
            route_target=intent.route_target,
        )

    return CommunicationRouteResult(
        intent=intent,
        context=str(context or ""),
        handled=False,
        route_target=intent.route_target,
    )
