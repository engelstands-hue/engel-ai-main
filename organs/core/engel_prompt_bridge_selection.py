"""Deterministic prompt-style and bridge-selection guidance for Engel.

This module merges the Meeting Room prompt-engineering guide into a local,
no-provider decision layer. It does not call models, start bridges, start
workers, or touch network/device control. It only describes the route Engel
should use when a user request arrives from the main UI.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re


PROMPT_ROUTE_VERSION = "ENGEL_MEETING_ROOM_ROUTE_PROMPT_V1"
BRIDGE_MATRIX_VERSION = "ENGEL_AGENT_BRIDGE_SELECTION_MATRIX_V1"
PROMPT_ENGINEERING_VERSION = "ENGEL_AGENT_MEETING_ROOM_BRIDGE_SELECTION_PROMPT_ENGINEERING_V1"


@dataclass(frozen=True)
class AgentBridgeProfile:
    key: str
    name: str
    role: str
    best_for: tuple[str, ...]
    meeting_bridge: str
    route_status: str
    safety_notes: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class PromptRouteDecision:
    task_type: str
    prompt_type: str
    primary_agent: str
    support_agents: tuple[str, ...]
    preferred_bridge: str
    bridge_key: str
    meeting_bridge: str
    bridge_status: str
    equipment_target: str
    output_format: str
    reason: str
    safety_limits: tuple[str, ...]
    prompt_notes: tuple[str, ...]
    required_output: tuple[str, ...]
    verifier_required: bool
    prompt_version: str = PROMPT_ROUTE_VERSION
    bridge_matrix_version: str = BRIDGE_MATRIX_VERSION
    source_spec: str = PROMPT_ENGINEERING_VERSION

    def to_dict(self) -> dict:
        return asdict(self)

    def summary(self) -> str:
        supports = ", ".join(self.support_agents) if self.support_agents else "none"
        return (
            f"{self.prompt_type} / {self.task_type} -> {self.primary_agent} "
            f"(support: {supports}) -> {self.preferred_bridge} "
            f"[{self.bridge_status}] -> {self.equipment_target}"
        )


BRIDGE_PROFILES: dict[str, AgentBridgeProfile] = {
    "chatgpt": AgentBridgeProfile(
        key="chatgpt",
        name="ChatGPT / GPT-style",
        role="Swiss Army Knife bridge",
        best_for=("complex reasoning", "backend code", "math", "general tasks", "everyday tasks"),
        meeting_bridge="ChatGPT Bridge (Engel no-API handoff)",
        route_status="recommendation only until an approved ChatGPT route is connected",
        safety_notes=("No API key in source.", "Do not call provider automatically."),
    ),
    "claude": AgentBridgeProfile(
        key="claude",
        name="Claude-style",
        role="Surgeon's Scalpel bridge",
        best_for=("writing quality", "long documents", "frontend code", "UI/UX", "nuanced analysis"),
        meeting_bridge="Claude API / Claude Bridge (Engel provider)",
        route_status="recommendation only until an approved Claude route is connected",
        safety_notes=("No automatic provider call.", "Use for writing/UI when configured."),
    ),
    "gemini": AgentBridgeProfile(
        key="gemini",
        name="Gemini-style",
        role="Google ecosystem / long-context bridge",
        best_for=("Google ecosystem", "massive documents", "search integration", "large context"),
        meeting_bridge="Engel Chat Auto Route",
        route_status="not configured in Meeting Room; recommendation metadata only",
        safety_notes=("Do not claim Gemini is live unless a route reports connected.",),
    ),
    "grok": AgentBridgeProfile(
        key="grok",
        name="Grok-style",
        role="Social pulse bridge",
        best_for=("real-time X data", "current events", "social trends"),
        meeting_bridge="Engel Chat Auto Route",
        route_status="not configured in Meeting Room; recommendation metadata only",
        safety_notes=("Requires approved live social-data route before use.",),
    ),
    "deepseek": AgentBridgeProfile(
        key="deepseek",
        name="DeepSeek-style",
        role="Budget/API-scale bridge",
        best_for=("cost efficiency", "API at scale", "open source", "budget coding"),
        meeting_bridge="Engel Chat Auto Route",
        route_status="not configured in Meeting Room; recommendation metadata only",
        safety_notes=("Use only through an approved provider/runtime route.",),
    ),
    "llama": AgentBridgeProfile(
        key="llama",
        name="LLaMA/local model",
        role="Local privacy bridge",
        best_for=("privacy", "offline work", "local-only tasks", "no-provider mode"),
        meeting_bridge="Local LLM (offline seed / GGUF)",
        route_status="local route only when local LLM gate is enabled",
        safety_notes=("Do not start local model runtime automatically.",),
    ),
    "perplexity": AgentBridgeProfile(
        key="perplexity",
        name="Perplexity-style",
        role="Research bridge",
        best_for=("source discovery", "research", "citations", "web answers"),
        meeting_bridge="Engel Chat Auto Route",
        route_status="not configured in Meeting Room; recommendation metadata only",
        safety_notes=("Network research requires an approved route.",),
    ),
    "image": AgentBridgeProfile(
        key="image",
        name="Image-generation bridge",
        role="Image creation bridge",
        best_for=("images", "visual assets", "illustrations", "brand graphics"),
        meeting_bridge="Custom Bridge",
        route_status="recommendation only; local artifact executor may handle simple SVG/HTML outputs",
        safety_notes=("Do not call an image provider automatically.",),
    ),
    "video": AgentBridgeProfile(
        key="video",
        name="Veo/Kling-style",
        role="Video bridge",
        best_for=("video", "motion", "animation"),
        meeting_bridge="Custom Bridge",
        route_status="not configured in Meeting Room; recommendation metadata only",
        safety_notes=("Video generation requires a separate approved route.",),
    ),
    "music": AgentBridgeProfile(
        key="music",
        name="Suno-style",
        role="Music bridge",
        best_for=("music", "song", "jingle", "soundtrack"),
        meeting_bridge="Custom Bridge",
        route_status="not configured in Meeting Room; recommendation metadata only",
        safety_notes=("Audio/music generation requires a separate approved route.",),
    ),
    "voice": AgentBridgeProfile(
        key="voice",
        name="ElevenLabs-style",
        role="Voice bridge",
        best_for=("voice", "narration", "speech"),
        meeting_bridge="Custom Bridge",
        route_status="not configured in Meeting Room; recommendation metadata only",
        safety_notes=("Voice generation requires a separate approved route.",),
    ),
    "cursor": AgentBridgeProfile(
        key="cursor",
        name="Cursor-style",
        role="Editor coding bridge",
        best_for=("editor coding", "inline IDE fixes"),
        meeting_bridge="Cursor (engel_cursor_bridge)",
        route_status="recommendation only until the editor bridge reports ready",
        safety_notes=("Do not mutate files without the existing Engel edit/verifier path.",),
    ),
    "claude_code": AgentBridgeProfile(
        key="claude_code",
        name="Claude Code-style",
        role="Terminal coding bridge",
        best_for=("terminal coding", "app builds", "frontend implementation"),
        meeting_bridge="Claude API / Claude Bridge (Engel provider)",
        route_status="recommendation only; terminal work remains approval-gated",
        safety_notes=("No raw shell target from Meeting Room.",),
    ),
    "codex": AgentBridgeProfile(
        key="codex",
        name="Codex-style",
        role="Cloud coding bridge",
        best_for=("cloud coding", "repo work", "code review", "patches"),
        meeting_bridge="Codex API / Codex Bridge (Engel Agent)",
        route_status="recommendation only until the Codex route reports connected",
        safety_notes=("Use existing Engel/Codex route; do not create a second router.",),
    ),
    "game_factory": AgentBridgeProfile(
        key="game_factory",
        name="Game Factory multi-bridge",
        role="Agent Meeting Room game-production bridge",
        best_for=(
            "playable game production",
            "gameplay code",
            "art direction",
            "UI controls",
            "device-worker load sharing",
            "browser verification",
        ),
        meeting_bridge="Game Factory Scout (Engel Meeting Room)",
        route_status=(
            "multi-agent route: phone worker + Game Factory Scout + Codex/code + "
            "Claude/UI + ChatGPT/art + local verifier; live providers are used only when connected"
        ),
        safety_notes=(
            "No copied franchise assets.",
            "No provider claim unless a bridge reports connected.",
            "Local artifact finalizer remains bounded.",
        ),
    ),
    "trading_dashboard": AgentBridgeProfile(
        key="trading_dashboard",
        name="Trading Dashboard bridge",
        role="Engel Dashboard paper-trading and broker-safety bridge",
        best_for=(
            "Engel dashboard integration",
            "paper trading",
            "portfolio safety",
            "SnapTrade setup review",
            "risk/circuit-breaker audit",
        ),
        meeting_bridge="Trading Dashboard Bridge (Engel Dashboard)",
        route_status=(
            "available read-only route: reviews dashboard docs and stages safety "
            "packets; helper startup, secrets, and live trading remain manual"
        ),
        safety_notes=(
            "No broker secrets or session tokens in Engel AI.",
            "Paper-only by default; live trading requires explicit manual approval.",
            "No hidden trades and no raw broker order from Meeting Room.",
        ),
    ),
    "engel_os": AgentBridgeProfile(
        key="engel_os",
        name="Engel OS read-only bridge",
        role="Sub-Engel OS build and safety-status bridge",
        best_for=(
            "Engel OS project hookup",
            "Sub-Engel ISO verification",
            "remote-control allowlist review",
            "USB flashing readiness review",
            "safety gate reporting",
        ),
        meeting_bridge="Engel OS Bridge (read-only)",
        route_status=(
            "available read-only route: reviews D:\\Engel OS docs, current ISO, "
            "checksum, and Sub-Engel allowlist; flashing, install, runtime, SSH, "
            "and shell remain blocked"
        ),
        safety_notes=(
            "No USB flashing from Engel AI.",
            "No raw shell, SSH, disk install, provider/model runtime, or background worker startup.",
            "No pairing codes, session tokens, Wi-Fi credentials, or secrets in reports.",
        ),
    ),
    "engel_local": AgentBridgeProfile(
        key="engel_local",
        name="Local Engel AI",
        role="Local-first deterministic route",
        best_for=("bounded local execution", "safe artifact assembly", "meeting-room dispatch"),
        meeting_bridge="Engel Chat Auto Route",
        route_status="available local route metadata; execution still goes through existing gates",
        safety_notes=("No provider call.", "No fake device connection claims."),
    ),
}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").lower()).strip()


def _has(text: str, *needles: str) -> bool:
    return any(needle in text for needle in needles)


def _word(text: str, *words: str) -> bool:
    return any(re.search(rf"\b{re.escape(word)}\b", text) for word in words)


def _strip_conical_dispatch_wrapper(text: str) -> str:
    """Drop Engel's conical assemble prefix so routing uses the operator request."""
    stripped = re.sub(
        r"(?is)^conical\s+(?:small|medium|large|expert)\s+build:\s+"
        r"split work across .*?assemble on ct246\.\s*",
        "",
        str(text or "").strip(),
        count=1,
    ).strip()
    return stripped or str(text or "").strip()


def _is_operator_app_build(low: str) -> bool:
    """True for create/make/build me an app — not copy like 'improve the app language'."""
    if re.search(r"\b(?:app language|language for this app|improve the app)\b", low):
        return False
    if re.search(r"\b(?:recreate|rebuild|port|convert|rewrite)\b", low) and re.search(
        r"\bflutter\b",
        low,
    ):
        return True
    return bool(
        re.search(
            r"\b(?:create|make|build|generate|develop)\s+(?:me\s+)?"
            r"(?:an?\s+)?(?:[a-z0-9_-]+\s+){0,6}"
            r"(?:web\s*apps?|web\s*pages?|websites?|webpages?|applications?|apps?)\b",
            low,
        )
    )


def classify_prompt_type(user_request: str) -> str:
    """Return Enterprise, Research, or General Chat."""
    low = _norm(_strip_conical_dispatch_wrapper(user_request))
    if not low:
        return "General Chat"
    mutates_or_creates = (
        "build", "fix", "refactor", "update", "merge", "wire", "connect",
        "install", "create", "make", "generate", "write", "save", "put",
        "pdf", "file", "code", "script", "app", "game", "artifact",
        "verifier", "test", "cleanup", "clean up", "organize", "move",
        "review", "audit", "safety rules", "paper trading", "snaptrade",
    )
    research_words = (
        "research", "search", "look up", "compare", "investigate",
        "sources", "current", "trend", "market scan",
    )
    safety_or_privacy_words = (
        "local only", "no provider", "offline", "private", "privacy", "do not call provider",
    )
    if _has(low, *research_words):
        return "Research"
    if _has(low, *safety_or_privacy_words):
        return "Enterprise"
    if _has(low, *mutates_or_creates) or _word(low, "run", "test", "verify"):
        return "Enterprise"
    return "General Chat"


def infer_task_type(user_request: str) -> str:
    low = _norm(_strip_conical_dispatch_wrapper(user_request))
    if _has(low, "prompt engineering", "prompt route", "bridge selection", "which bridge"):
        return "prompt-route-analysis"
    if _has(low, "engel os", "engel-os", "d:\\engel os", "ready_to_flash", "ready to flash", "usb flashing guide", "sub-node live iso", "packet 016", "packet_016"):
        return "engel-os"
    if _is_operator_app_build(low):
        return "artifact-creation"
    if _has(low, "phone", "android worker", "adb", "wifi worker", "remote worker"):
        return "android-worker-routing"
    if _has(low, "sub-engel", "sub engel", "cluster node", "firmware", "iso"):
        return "sub-engel-diagnostics"
    if _has(low, "c:", "appdata", "temp", "cleanup", "clean up", "organize folder", "archive"):
        return "workspace-migration"
    if _has(low, "engel-dashboard", "engel dashboard", "trading dashboard", "trade dashboard", "snaptrade", "robinhood", "paper trader", "paper trading", "auto trader", "autonomous paper", "portfolio dashboard", "market dashboard", "circuit breaker", "agent_design.md", "safety_rules.md", "snaptrade_setup.md"):
        return "trading-dashboard"
    if _has(low, "game factory", "refine game", "game refinement", "longer stages", "better controls", "video game", "browser game", "playable game", "game development", "create a game", "make a game", "build a game", "arcade", "run-and-gun", "run and gun", "side-scrolling", "side scrolling", "platformer", "phaser", "weapon upgrades", "boss at end", "stage boss"):
        return "game-development"
    if _has(low, "video", "animation", "movie"):
        return "video-creation"
    if _has(low, "music", "song", "jingle", "soundtrack"):
        return "music-creation"
    if _has(low, "voice", "narration", "speech", "tts"):
        return "voice-creation"
    if _has(low, "image", "picture", "logo", "icon", "visual", "happy face", "face yellow"):
        return "image-creation"
    if _has(low, "google docs", "google drive", "gmail", "sheets", "massive document", "2 million"):
        return "google-long-context"
    if _has(low, "x/twitter", "twitter", "social trend", "social data", "current event", "right now"):
        return "social-current-events"
    if _has(low, "budget api", "cheap api", "cost efficient", "api at scale", "open source model"):
        return "budget-api-scale"
    if _has(low, "private", "privacy", "local only", "offline", "no provider"):
        return "privacy-local"
    if _has(low, "research", "sources", "citations", "look online", "search internet", "search online"):
        return "research"
    if _has(low, "terminal", "command line", "shell", "pyinstaller", "build exe"):
        return "terminal-coding"
    if _has(low, "cloud coding", "repo work", "pull request", "code review", "codex"):
        return "cloud-coding"
    if _has(low, "cursor", "editor"):
        return "editor-coding"
    if _has(low, "frontend", "ui", "ux", "window", "screen", "layout", "translucent", "button"):
        return "ui-frontend"
    if _has(low, "long document", "contract", "manual", "markdown", "language for this app", "copy", "microcopy"):
        return "long-document-writing"
    if _has(low, "code", "python", "bug", "function", "refactor", "script", "api", "game"):
        return "coding"
    if _has(low, "math", "algebra", "equation", "statistics", "probability"):
        return "math-reasoning"
    if _has(low, "pdf", "report", "file", "artifact"):
        return "artifact-creation"
    return "general"


def select_bridge_key(user_request: str, task_type: str | None = None) -> str:
    low = _norm(user_request)
    task = task_type or infer_task_type(user_request)
    if task == "privacy-local":
        return "llama"
    if task == "image-creation":
        return "image"
    if task == "video-creation":
        return "video"
    if task == "music-creation":
        return "music"
    if task == "voice-creation":
        return "voice"
    if task == "google-long-context":
        return "gemini"
    if task == "social-current-events":
        return "grok"
    if task == "budget-api-scale":
        return "deepseek"
    if task == "research":
        return "perplexity"
    if task == "editor-coding":
        return "cursor"
    if task == "terminal-coding":
        return "claude_code"
    if task == "cloud-coding":
        return "codex"
    if task in {"ui-frontend", "long-document-writing"}:
        return "claude"
    if task == "game-development":
        return "game_factory"
    if task == "trading-dashboard":
        return "trading_dashboard"
    if task == "engel-os":
        return "engel_os"
    if task in {"coding", "math-reasoning"}:
        return "chatgpt"
    if task in {"android-worker-routing", "sub-engel-diagnostics", "workspace-migration", "artifact-creation"}:
        return "engel_local"
    if _has(low, "chatgpt", "gpt"):
        return "chatgpt"
    if _has(low, "claude"):
        return "claude"
    if _has(low, "gemini"):
        return "gemini"
    if _has(low, "grok"):
        return "grok"
    if _has(low, "deepseek"):
        return "deepseek"
    if _has(low, "llama", "local model"):
        return "llama"
    return "chatgpt" if classify_prompt_type(user_request) == "General Chat" else "engel_local"


def _default_primary_agent(task_type: str) -> str:
    if task_type in {"ui-frontend", "image-creation", "video-creation", "music-creation", "voice-creation"}:
        return "UI Agent" if task_type == "ui-frontend" else "Creative Agent"
    if task_type == "game-development":
        return "Game Developer Agent"
    if task_type in {"coding", "terminal-coding", "cloud-coding", "editor-coding"}:
        return "Code Agent"
    if task_type in {"long-document-writing", "artifact-creation"}:
        return "Documentation Agent"
    if task_type in {"research", "social-current-events", "google-long-context", "budget-api-scale"}:
        return "Research Agent"
    if task_type == "android-worker-routing":
        return "Android Phone Agent"
    if task_type == "sub-engel-diagnostics":
        return "Sub-Engel Agent"
    if task_type == "workspace-migration":
        return "File Structure Agent"
    if task_type == "math-reasoning":
        return "Math Agent"
    if task_type == "prompt-route-analysis":
        return "Prompt Engineer Agent"
    if task_type == "trading-dashboard":
        return "Trading Dashboard Bridge Agent"
    if task_type == "engel-os":
        return "Engel OS Bridge Agent"
    return "Engel Core"


def _support_agents(task_type: str, existing: tuple[str, ...]) -> tuple[str, ...]:
    support: list[str] = list(existing)
    if task_type == "game-development":
        support.extend(["Game Factory Scout Agent", "Game Art Director Agent", "UI Agent", "Verifier Agent", "Safety Agent"])
    elif task_type == "trading-dashboard":
        support.extend(["Safety Agent", "Portfolio Strategist Agent", "Quant Modeler Agent", "Dashboard Architect Agent", "Verifier Agent"])
    elif task_type == "engel-os":
        support.extend(["Sub-Engel Agent", "Safety Agent", "Verifier Agent"])
    elif task_type in {"coding", "terminal-coding", "cloud-coding", "editor-coding", "ui-frontend"}:
        support.extend(["Verifier Agent", "Safety Agent"])
    elif task_type in {"research", "social-current-events", "google-long-context", "budget-api-scale"}:
        support.extend(["Safety Agent", "Verifier Agent"])
    elif task_type in {"android-worker-routing", "sub-engel-diagnostics"}:
        support.extend(["Safety Agent", "Verifier Agent"])
    elif task_type in {"workspace-migration", "artifact-creation", "long-document-writing"}:
        support.extend(["Verifier Agent", "Safety Agent"])
    else:
        support.append("Verifier Agent")
    seen: set[str] = set()
    result: list[str] = []
    for agent in support:
        if agent and agent not in seen:
            seen.add(agent)
            result.append(agent)
    limit = 5 if task_type in {"game-development", "trading-dashboard"} else 4
    return tuple(result[:limit])


def _required_output(prompt_type: str, task_type: str) -> tuple[str, ...]:
    if prompt_type == "Research":
        return (
            "short summary",
            "options and risks",
            "sources when an approved web/research route is used",
            "recommended next packet",
        )
    if prompt_type == "General Chat":
        return ("clear answer", "assumptions", "next safe step if useful")
    if task_type == "game-development":
        return (
            "playable game artifact path",
            "Game Factory refinement report when refinement is requested",
            "engine/runtime used",
            "campaign scope and feature list",
            "multi-bridge agent route summary",
            "browser smoke result",
            "meeting-room route summary",
            "IP safety notes",
        )
    if task_type == "trading-dashboard":
        return (
            "dashboard doc merge report path",
            "agent-to-agent mapping",
            "paper-only/live-blocked safety status",
            "SnapTrade credential boundary",
            "remaining manual startup steps",
        )
    if task_type == "engel-os":
        return (
            "Engel OS bridge report path",
            "current ISO path and checksum verification",
            "Sub-Engel remote-control allowlist",
            "paired/not-paired state without tokens",
            "blocked-by-design safety gates",
        )
    if task_type in {"coding", "terminal-coding", "cloud-coding", "editor-coding", "ui-frontend"}:
        return ("files changed", "commands/tests run", "verifier results", "remaining blockers")
    if task_type in {"image-creation", "video-creation", "music-creation", "voice-creation", "artifact-creation"}:
        return ("artifact path", "preview/check result", "meeting-room route summary", "verifier notes")
    return ("route summary", "files/reports touched", "verifier or smoke result", "safety notes")


def _output_format(prompt_type: str, task_type: str) -> str:
    if prompt_type == "Research":
        return "summary + options + risks + sources-if-approved"
    if prompt_type == "General Chat":
        return "concise answer"
    if task_type == "game-development":
        return "playable game path + multi-bridge route + campaign features + engine details + browser verification"
    if task_type == "trading-dashboard":
        return "dashboard bridge report + safety gates + agent mapping + manual-only live trading notes"
    if task_type == "engel-os":
        return "Engel OS hookup report + ISO checksum status + Sub-Engel allowlist + blocked-action gates"
    if task_type in {"coding", "terminal-coding", "cloud-coding", "editor-coding"}:
        return "patch/result report with tests"
    if task_type in {"image-creation", "video-creation", "music-creation", "voice-creation", "artifact-creation"}:
        return "real artifact path + verification notes"
    return "structured route packet + verifier result"


def _equipment_from_station_details(station_details: list[dict] | None) -> str:
    if station_details:
        for detail in station_details:
            equipment = str(detail.get("device") or "").strip()
            if equipment:
                return equipment
    return "Local Engel AI (main PC)"


def _agents_from_station_details(station_details: list[dict] | None, task_type: str) -> tuple[str, tuple[str, ...]]:
    if not station_details:
        return _default_primary_agent(task_type), ()
    agents = [str(detail.get("agent") or "").strip() for detail in station_details if str(detail.get("agent") or "").strip()]
    if not agents:
        return _default_primary_agent(task_type), ()
    return agents[0], tuple(agents[1:])


def build_prompt_route_decision(
    user_request: str,
    station_details: list[dict] | None = None,
) -> PromptRouteDecision:
    task_type = infer_task_type(user_request)
    prompt_type = classify_prompt_type(user_request)
    primary_agent, existing_support = _agents_from_station_details(station_details, task_type)
    support_agents = _support_agents(task_type, existing_support)
    bridge_key = select_bridge_key(user_request, task_type)
    profile = BRIDGE_PROFILES[bridge_key]
    equipment_target = _equipment_from_station_details(station_details)
    verifier_required = prompt_type != "General Chat" or task_type not in {"general"}
    prompt_notes = (
        "Use clear, plain instructions a smart human could follow.",
        "Start simple, identify likely failures, add specificity, then structure.",
        "Use one or two examples for format-sensitive work.",
        "Use named sections or XML-like tags for build packets and schemas.",
        "Ask for a concise rationale/check summary, not hidden chain-of-thought.",
        "Version important prompts and learn from failed outputs.",
    )
    safety_limits = (
        "No fake connected workers or provider claims.",
        "No provider/model/network/device control unless an approved route is available.",
        "No raw shell, SSH, disk formatting, or unrestricted remote execution.",
        "No C: project storage for Engel-owned work.",
        "No deceptive pressure, threats, bribes, or bypass-the-verifier language.",
    )
    reason = (
        f"Task reads as {task_type}; {prompt_type} prompts need "
        f"{profile.role} because it is best for {', '.join(profile.best_for[:3])}."
    )
    return PromptRouteDecision(
        task_type=task_type,
        prompt_type=prompt_type,
        primary_agent=primary_agent,
        support_agents=support_agents,
        preferred_bridge=profile.name,
        bridge_key=profile.key,
        meeting_bridge=profile.meeting_bridge,
        bridge_status=profile.route_status,
        equipment_target=equipment_target,
        output_format=_output_format(prompt_type, task_type),
        reason=reason,
        safety_limits=safety_limits,
        prompt_notes=prompt_notes,
        required_output=_required_output(prompt_type, task_type),
        verifier_required=verifier_required,
    )


def format_prompt_route_summary(decision: PromptRouteDecision | dict) -> str:
    if isinstance(decision, dict):
        data = decision
    else:
        data = decision.to_dict()
    support = data.get("support_agents") or []
    if isinstance(support, (list, tuple)):
        support_text = ", ".join(str(item) for item in support) or "none"
    else:
        support_text = str(support)
    return "\n".join([
        f"Task type: {data.get('task_type')}",
        f"Prompt type: {data.get('prompt_type')}",
        f"Primary agent: {data.get('primary_agent')}",
        f"Support agents: {support_text}",
        f"Preferred bridge: {data.get('preferred_bridge')} ({data.get('bridge_status')})",
        f"Meeting bridge: {data.get('meeting_bridge')}",
        f"Equipment: {data.get('equipment_target')}",
        f"Output: {data.get('output_format')}",
        f"Verifier needed: {bool(data.get('verifier_required'))}",
    ])


def build_route_prompt_packet(user_request: str, decision: PromptRouteDecision) -> str:
    """Return the XML-like route packet described by the merge spec."""
    support = ", ".join(decision.support_agents) if decision.support_agents else "none"
    outputs = "; ".join(decision.required_output)
    limits = "\n    ".join(decision.safety_limits)
    return f"""<engel_meeting_room_route>
  <user_request>{user_request.strip()}</user_request>
  <task_type>{decision.task_type}</task_type>
  <primary_agent>{decision.primary_agent}</primary_agent>
  <support_agents>{support}</support_agents>
  <preferred_bridge>{decision.preferred_bridge}</preferred_bridge>
  <meeting_bridge>{decision.meeting_bridge}</meeting_bridge>
  <equipment_target>{decision.equipment_target}</equipment_target>
  <prompt_style>{decision.prompt_type}</prompt_style>
  <output_required>{outputs}</output_required>
  <safety_limits>
    {limits}
  </safety_limits>
  <acceptance_criteria>Real result path or verified answer returns to Engel AI Main UI.</acceptance_criteria>
</engel_meeting_room_route>"""
