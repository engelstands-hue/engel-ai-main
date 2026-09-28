"""Engel AI — Agent Meeting Room (Qt window).

A real Qt GUI for the Agent Meeting Room. This is the live workspace where:
  • Agent stations (device + agent + skill + bridge) are configured.
  • Orders from the Engel AI Main UI arrive via the
    ``submit_order_from_engel_main_ui()`` API and auto-select the best
    matching stations by skill.
  • The Main UI's reply is fanned back to each station through the
    ``complete_order_from_engel_main_ui()`` API. Per-equipment dispatch:
      - Local Engel AI                  → routed reply, chat record only
      - Android (USB or WiFi/LAN)       → real worker packet via
                                          engel_adb_worker_manager
      - Sub-Engel OS (WiFi or hardwire) → staged job packet (node processes with local gate; enables additional computers for AI)
      - Windows Sub-Engel Node          → staged job packet / LAN check-in (additional computers for bounded AI work)
  • Station activity and order flow are shown as agent cards and a
    timestamped log.
  • Room state is exportable as a Markdown summary.

Hard rules — this module:
  • Has NO prompt/job input box inside the window. Intake is API-only,
    coming from the main UI.
  • Never spawns ADB / SSH / browser automation directly. Real work
    runs through existing approved Engel surfaces.
  • Never claims Sub-Engel or Android are connected unless the local
    probe reports them (see ``_probe_android_status``).
  • Never writes trusted memory or mutates routes/queues.
  • Never reads or writes anything on C:\\ — runtime files live under
    D:\\b.WorkSpace\\Engel App\\runtime\\meeting_room\\, exported
    summaries land under D:\\b.WorkSpace\\Engel App\\reports\\meeting_rooms\\.
    See [[feedback-no-c-drive]] in project memory.

Launch (standalone):
    python engel_agent_meeting_room.py
    (or use the launch_engel_meeting_room.bat helper which pins the
    D:-local Python interpreter)

Or open from Engel AI Desktop V2 via the  ⌬ Meeting Room  button,
or the chat phrase "meeting room" / "open meeting room" /
"where is the meeting room" (intercepted locally — never reaches the
provider bridge).
"""
from __future__ import annotations

import engel_temp_policy  # noqa: F401
import datetime
import re
import html
import json
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

from engel_project_paths import resolve_engel_app_root


def _inline_prefer_workspace_modules(*names: str, caller_file: object | None = None) -> None:
    """Fallback for stale PyInstaller bundles whose engel_project_paths.py
    predates prefer_workspace_modules. Forces the workspace D: copy to win
    over the bundled _MEI / pyinstaller_tmp extract."""
    import os
    import sys as _sys

    candidate = None
    if caller_file is not None:
        directory = os.path.dirname(os.path.abspath(str(caller_file)))
        while directory and directory != os.path.dirname(directory):
            marker = os.path.join(directory, "engel_project_paths.py")
            lowered = directory.replace("\\", "/").lower()
            if os.path.isfile(marker) and "pyinstaller_tmp" not in lowered and "/_mei" not in lowered:
                candidate = directory
                break
            directory = os.path.dirname(directory)
    if not candidate:
        candidate = r"D:\b.WorkSpace\Engel App"
    if os.path.isdir(candidate):
        if candidate in _sys.path:
            _sys.path.remove(candidate)
        _sys.path.insert(0, candidate)
    for name in names:
        module = _sys.modules.get(name)
        if module is None:
            continue
        path_text = (getattr(module, "__file__", "") or "").replace("\\", "/").lower()
        if "pyinstaller_tmp" in path_text or "/_mei" in path_text:
            _sys.modules.pop(name, None)


try:
    from engel_project_paths import prefer_workspace_modules  # type: ignore
except ImportError:
    # Stale PyInstaller bundle predates prefer_workspace_modules. Use the
    # inline fallback so module import does not crash the Meeting Room and
    # order-handoff flow. Workspace copies will load after the exe rebuild.
    prefer_workspace_modules = _inline_prefer_workspace_modules
from engel_android_worker_prompt_signals import is_android_lan_pairing_request
from engel_prompt_bridge_selection import (
    build_prompt_route_decision,
    build_route_prompt_packet,
    format_prompt_route_summary,
)

ENGEL_APP_ROOT = resolve_engel_app_root(__file__)
RUNTIME_ROOM_DIR = ENGEL_APP_ROOT / "runtime" / "meeting_room"
ORDER_DIR = RUNTIME_ROOM_DIR / "main_ui_orders"
REPORTS_DIR = ENGEL_APP_ROOT / "reports" / "meeting_rooms"
ROOM_STATE_FILE = RUNTIME_ROOM_DIR / "room_state.json"
SHIP_TEAM_COLLAB_CHARTER = (
    "Collaboration room for EngelAIMain.exe. "
    "Foreman stages. Guardian gates. Clerk proofs claims vs receipts. "
    "Graphwright maps what is real. Shipwright grades LIVE/PARTIAL/PARKED/FAKE. "
    "Engel Labs hears public-claim rules only — no extra speech. "
    "Path: D:\\b.WorkSpace\\Engel App\\engel_flutter_main\\build\\windows\\x64\\runner\\Release. "
    "No public posts from this room. No fix until Josh. No receipt = it did not happen."
)
RETURNED_ASSIGNMENTS_DIR = ENGEL_APP_ROOT / "remote_workers" / "communication_queen_assignments" / "returned"
SELF_UPGRADE_WORK_ORDER_DIR = ENGEL_APP_ROOT / "memory" / "meeting_room" / "work_orders"
SELF_UPGRADE_RUNTIME_WORK_ORDER_DIR = RUNTIME_ROOM_DIR / "self_upgrade_work_orders"


def _ensure_dirs() -> None:
    RUNTIME_ROOM_DIR.mkdir(parents=True, exist_ok=True)
    ORDER_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    SELF_UPGRADE_WORK_ORDER_DIR.mkdir(parents=True, exist_ok=True)
    SELF_UPGRADE_RUNTIME_WORK_ORDER_DIR.mkdir(parents=True, exist_ok=True)


def _prefer_workspace_android_modules() -> None:
    prefer_workspace_modules(
        "engel_project_paths",
        "engel_remote_worker_lan_pairing",
        "engel_remote_worker_link_manager",
        "engel_device_capability_registry",
        caller_file=__file__,
    )


# ─── Qt import (PyQt6 preferred, PySide6 fallback) ────────────────────────────
try:
    from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
    from PyQt6.QtWidgets import (
        QApplication, QWidget, QMainWindow,
        QVBoxLayout, QHBoxLayout, QGridLayout,
        QLabel, QPushButton, QTextEdit,
        QFrame, QComboBox, QListWidget, QListWidgetItem,
        QSplitter, QScrollArea,
    )
    HAS_QT = True
except ImportError:
    try:
        from PySide6.QtCore import Qt, QTimer, QThread
        from PySide6.QtCore import Signal as pyqtSignal  # type: ignore[assignment]
        from PySide6.QtWidgets import (
            QApplication, QWidget, QMainWindow,
            QVBoxLayout, QHBoxLayout, QGridLayout,
            QLabel, QPushButton, QTextEdit,
            QFrame, QComboBox, QListWidget, QListWidgetItem,
            QSplitter, QScrollArea,
        )
        HAS_QT = True
    except ImportError:
        HAS_QT = False

if not HAS_QT:
    class _NoQtEnum:
        def __getattr__(self, _name):
            return self

    class _NoQtSignal:
        def connect(self, *_args, **_kwargs):
            return None

        def emit(self, *_args, **_kwargs):
            return None

    def pyqtSignal(*_args, **_kwargs):  # type: ignore[no-redef]
        return _NoQtSignal()

    class _NoQtObject:
        Shape = _NoQtEnum()
        ItemDataRole = _NoQtEnum()
        WidgetAttribute = _NoQtEnum()
        Orientation = _NoQtEnum()

        def __init__(self, *_args, **_kwargs):
            pass

        def __getattr__(self, _name):
            def _noop(*_args, **_kwargs):
                return None
            return _noop

    class _NoQtThread(_NoQtObject):
        def start(self):
            return self.run()

        def run(self):
            return None

    class _NoQtApplication(_NoQtObject):
        @staticmethod
        def instance():
            return None

        def exec(self):
            return 1

    Qt = _NoQtEnum()  # type: ignore[assignment]
    QTimer = _NoQtObject  # type: ignore[assignment]
    QThread = _NoQtThread  # type: ignore[assignment]
    QApplication = _NoQtApplication  # type: ignore[assignment]
    QWidget = QMainWindow = QVBoxLayout = QHBoxLayout = QGridLayout = _NoQtObject  # type: ignore[assignment]
    QLabel = QPushButton = QTextEdit = QFrame = QComboBox = _NoQtObject  # type: ignore[assignment]
    QListWidget = QListWidgetItem = QSplitter = QScrollArea = _NoQtObject  # type: ignore[assignment]


# ─── Palette (mirrors Desktop V2) ─────────────────────────────────────────────
BG       = "#0d0d14"
BG_GLASS = "rgba(13, 13, 20, 168)"
CARD     = "#12121c"
CARD_GLASS = "rgba(18, 18, 28, 176)"
CARD2    = "#16162a"
CARD2_GLASS = "rgba(22, 22, 42, 184)"
BORDER   = "#1e1e30"
BORDER2  = "#2a2a45"
TEXT     = "#c8c8e8"
DIM      = "#5a5a7a"
GREEN    = "#00e87a"
AMBER    = "#ffaa00"
RED      = "#ff4455"
BLUE     = "#44aaff"
PURPLE   = "#aa77ff"
FONT     = "Consolas, 'Cascadia Mono', 'Courier New', monospace"
DEFAULT_WINDOW_OPACITY = 0.94


def _ui_opacity(*names: str, default: float = DEFAULT_WINDOW_OPACITY) -> float:
    """Read a clamped window opacity from the environment."""
    for name in names:
        raw = os.environ.get(name)
        if not raw:
            continue
        try:
            return max(0.55, min(1.0, float(raw)))
        except ValueError:
            return default
    return default

STYLESHEET = f"""
QMainWindow, QWidget {{
    background: {BG_GLASS};
    color: {TEXT};
    font-family: {FONT};
    font-size: 9pt;
}}
QFrame#card {{
    background: {CARD_GLASS};
    border: 1px solid {BORDER};
    border-radius: 6px;
}}
QFrame#card2 {{
    background: {CARD2_GLASS};
    border: 1px solid {BORDER2};
    border-radius: 5px;
}}
QComboBox {{
    background: {CARD2_GLASS};
    border: 1px solid {BORDER2};
    border-radius: 4px;
    color: {TEXT};
    padding: 4px 8px;
    font-family: {FONT};
    font-size: 9pt;
}}
QComboBox:focus {{
    border-color: {GREEN};
}}
QComboBox::drop-down {{ border: none; }}
QPushButton {{
    background: {CARD_GLASS};
    color: {GREEN};
    border: 1px solid {BORDER2};
    border-radius: 4px;
    padding: 4px 12px;
    font-weight: 700;
    font-size: 9pt;
    min-height: 24px;
}}
QPushButton:hover {{
    background: {CARD2};
    border-color: {GREEN};
    color: #ffffff;
}}
QPushButton:pressed {{
    background: #0d1f15;
}}
QPushButton#primary {{
    background: {GREEN};
    color: {BG};
    border: none;
    font-weight: 900;
}}
QPushButton#primary:hover {{
    background: #00ff88;
    color: {BG};
}}
QPushButton#purple {{
    color: {PURPLE};
}}
QPushButton#blue {{
    color: {BLUE};
}}
QTextEdit {{
    background: {BG_GLASS};
    border: 1px solid {BORDER};
    border-radius: 4px;
    color: {TEXT};
    font-family: {FONT};
    font-size: 9pt;
    padding: 6px;
    selection-background-color: #1a3a2a;
}}
QListWidget {{
    background: {BG_GLASS};
    border: 1px solid {BORDER};
    border-radius: 4px;
    color: {TEXT};
    font-size: 8pt;
}}
QListWidget::item {{ padding: 3px 6px; }}
QListWidget::item:selected {{ background: #1a2a1a; color: {GREEN}; }}
QScrollBar:vertical {{ background: transparent; width: 6px; border: none; }}
QScrollBar::handle:vertical {{ background: {BORDER2}; border-radius: 3px; min-height: 20px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
"""


# ─── Domain types ─────────────────────────────────────────────────────────────

AGENT_TYPES = (
    "Engel Core",
    "Architect Agent",
    "Grok Bot",
    "Research Agent",
    "Math Agent",
    "Code Agent",
    "Code Factory Scout Agent",
    "Game Factory Scout Agent",
    "Game Developer Agent",
    "Game Art Director Agent",
    "UI Agent",
    "Verifier Agent",
    "Memory Agent",
    "Safety Agent",
    "Prompt Engineer Agent",
    "File Structure Agent",
    "Skill Builder Agent",
    # ── Hermes-Agent framework (bundled engel_agent_main via engel_agent_bridge) ──
    "Hermes Agent",
    # ── Finance & Markets roster (md profiles in agents/) ──
    "Financial Strategist Agent",
    "Stocks Historian Agent",
    "Market Impact Analyst Agent",
    "Macro Economist Agent",
    "Crypto Analyst Agent",
    "Portfolio Strategist Agent",
    "Quant Modeler Agent",
    "News Event Correlator Agent",
    "Sentiment Analysis Agent",
    "Trading Dashboard Bridge Agent",
    "Engel OS Bridge Agent",
    # ── Web & Design roster ──
    "Web App Designer Agent",
    "Design System Architect Agent",
    "Accessibility Auditor Agent",
    "UX Research Lead Agent",
    "Mobile Web Designer Agent",
    # ── Graph & Data Viz roster ──
    "Graph Visualization Designer Agent",
    "Data Viz Storyteller Agent",
    "Chart Engineer Agent",
    "Dashboard Architect Agent",
    # ── Deep Research roster ──
    "Deep Research Agent",
    "Literature Review Agent",
    "Competitive Intelligence Agent",
    "Historical Context Agent",
    "Android Phone Agent",
    # ── Per-phone Android worker targets (deterministic routing) ──
    "Android Phone Alpha Agent",   # Moto G Power 2025 (ANDROID_WORKER_ALPHA) -> android_worker_alpha
    "Android Phone Beta Agent",    # Moto G Fast (ANDROID_WORKER_BETA)       -> android_worker_beta
    "Android Phone Gamma Agent",   # Samsung Galaxy A14 5G (ANDROID_WORKER_GAMMA) -> android_worker_gamma
    # ── Approved-Library reference roster (engel_library/approved_library/) ──
    "AI Safety Reference Agent",
    "Algorithms DS Reference Agent",
    "Android Worker Reference Agent",
    "Architecture Reference Agent",
    "Patch Planning Agent",
    "Language Reference Agent",
    "Polyglot Coding Agent",
    "Download Failure Triage Agent",
    "Library Receipts Auditor Agent",
    "Offline Seed LLM Agent",
    "Code Companion Agent",
    "Engel Manuals Agent",
    "Engel Receipts Agent",
    "LLM Reference Agent",
    "Math Reference Agent",
    "Logic Reasoning Reference Agent",
    "Memory Systems Reference Agent",
    "Offline Docs Agent",
    "PyInstaller Packaging Agent",
    "PySide6 Qt Agent",
    "Python Reference Agent",
    "Research Papers Agent",
    "RAG Retrieval Agent",
    "Prompt Injection Defense Agent",
    "SQLite Reference Agent",
    "Static Analysis Agent",
    "Pytest Testing Agent",
    "WSL Ubuntu Runtime Agent",
    "Agency Specialist Agent",
    # ── Catch-all ──
    "Custom Agent",
)

SKILL_TYPES = (
    "Architect Workflow Skill",
    "Grok Bot Teammate Skill",
    "Math Skill",
    "Research Skill",
    "Coding Skill",
    "Hermes Agent Skill",
    "Code Factory Scout Skill",
    "Game Factory Refinement Skill",
    "Game Development Skill",
    "Game Art Skill",
    "UI Skill",
    "Verification Skill",
    "Memory Skill",
    "File Structure Skill",
    "Android Worker Skill",
    "Engel OS Bridge Skill",
    "Sub-Engel Worker Skill",
    "Windows Sub-Engel Worker Skill",
    # ── Unique skills for the four previously-manual-only agents ──
    "Safety Review Skill",
    "Skill Building Skill",
    "Engel Orchestration Skill",
    "Prompt Engineering Skill",
    # ── Per-phone Android worker skills (deterministic per-phone routing) ──
    "Android Worker Alpha Skill",
    "Android Worker Beta Skill",
    "Android Worker Gamma Skill",
    # ── Finance & Markets skills ──
    "Financial Strategy Skill",
    "Stocks History Skill",
    "Market Impact Skill",
    "Macro Economics Skill",
    "Crypto Analysis Skill",
    "Portfolio Strategy Skill",
    "Quant Modeling Skill",
    "News Correlation Skill",
    "Sentiment Analysis Skill",
    "Trading Dashboard Bridge Skill",
    # ── Web & Design skills ──
    "Web App Design Skill",
    "Design System Skill",
    "Accessibility Audit Skill",
    "UX Research Skill",
    "Mobile Web Skill",
    # ── Graph & Data Viz skills ──
    "Graph Visualization Skill",
    "Data Viz Storytelling Skill",
    "Chart Engineering Skill",
    "Dashboard Architecture Skill",
    # ── Deep Research skills ──
    "Deep Research Skill",
    "Literature Review Skill",
    "Competitive Intelligence Skill",
    "Historical Context Skill",
    # ── Approved-Library reference skills ──
    "AI Safety Reference Skill",
    "Algorithms DS Reference Skill",
    "Android Worker Reference Skill",
    "Architecture Reference Skill",
    "Patch Planning Skill",
    "Language Reference Skill",
    "Polyglot Coding Skill",
    "Download Failure Triage Skill",
    "Library Receipts Audit Skill",
    "Offline Seed LLM Skill",
    "Code Companion Skill",
    "Engel Manuals Skill",
    "Engel Receipts Skill",
    "LLM Reference Skill",
    "Math Reference Skill",
    "Logic Reasoning Reference Skill",
    "Memory Systems Reference Skill",
    "Offline Docs Skill",
    "PyInstaller Packaging Skill",
    "PySide6 Qt Skill",
    "Python Reference Skill",
    "Research Papers Skill",
    "RAG Retrieval Skill",
    "Prompt Injection Defense Skill",
    "SQLite Reference Skill",
    "Static Analysis Skill",
    "Pytest Testing Skill",
    "WSL Ubuntu Runtime Skill",
    "Agency Specialist Skill",
    # ── Catch-all ──
    "Custom Skill",
)

EQUIPMENT_TARGETS = (
    "Local Engel AI (main PC)",
    "Android App Worker — USB / hardwire ADB",
    "Android App Worker — WiFi / LAN pairing",
    "Sub-Engel OS Worker — WiFi / LAN diagnostics",
    "Sub-Engel OS Worker — hardwire / future",
    "Windows Sub-Engel Node - LAN check-in",
    "Windows Sub-Engel Node - service / outbound",
    "Unassigned",
)

# Bridge / backend options — each participant may use a different one.
# The Meeting Room records the selection as metadata only; activating a
# bridge for real work is the job of the relevant runner/bridge module
# and remains gated by Engel's existing approval flow.
BRIDGE_OPTIONS = (
    "Engel Chat Auto Route",
    "ChatGPT Bridge (Engel no-API handoff)",
    "Code Factory Scout (Engel Meeting Room)",
    "Game Factory Scout (Engel Meeting Room)",
    "Trading Dashboard Bridge (Engel Dashboard)",
    "Engel OS Bridge (read-only)",
    "Codex API / Codex Bridge (Engel Agent)",
    "Claude API / Claude Bridge (Engel provider)",
    "Local LLM (offline seed / GGUF)",
    "Local Multi-Model Code Gen",
    "Local Code Translate (multi-model)",
    "Local Best Auto Code (smart model)",
    "Local Multi-Model Candidates",
    "Stage to Sub-Engel (code gen job)",
    "Local Code Stage to Fleet",
    "Android Worker Job Packet",
    "Sub-Engel Job Packet",
    "Windows Sub-Engel Job Packet",
    "Sub-Engel Results",
    "Hermes-Agent (engel_agent_bridge)",
    "Cursor (engel_cursor_bridge)",
    "GStack (engel_gstack_bridge)",
    "Jarvis (engel_jarvis_bridge)",
    "Engel Architect Agent (engel_architect_agent)",
    "Grok Bot (cluster teammate)",
    "Custom Bridge",
    "None (local-only)",
)


@dataclass
class Participant:
    name: str
    kind: str            # "agent" | "skill"
    type_label: str      # AGENT_TYPES or SKILL_TYPES value
    equipment: str = "Unassigned"
    status: str = "Idle"  # Idle | Assigned | Waiting | Needs Review
    bridge: str = "Engel Chat Auto Route"  # BRIDGE_OPTIONS value
    skill_label: str = "Unassigned Skill"


@dataclass
class RoomState:
    room_name: str = "Engel Default Room"
    created_at: str = ""
    goal: str = "Coordinate agents and skills to advance the active project."
    project: str = "(unset)"
    open_task: str = "(unset)"
    safety_state: str = "LOCAL ONLY — no remote control"
    last_export: str = ""
    participants: list[Participant] = field(default_factory=list)
    messages: list[dict] = field(default_factory=list)  # {role, name, text, time}


def _now_iso() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def _now_pretty() -> str:
    return datetime.datetime.now().strftime("%H:%M:%S")


def _stamp_filename() -> str:
    return datetime.datetime.now().strftime("ROOM-%Y%m%d-%H%M%S.md")


def _agent_for_skill(skill: str) -> str:
    mapping = {
        "Architect Workflow Skill": "Architect Agent",
        "Grok Bot Teammate Skill": "Grok Bot",
        "Math Skill": "Math Agent",
        "Research Skill": "Research Agent",
        "Coding Skill": "Code Agent",
        "Hermes Agent Skill": "Hermes Agent",
        "Code Factory Scout Skill": "Code Factory Scout Agent",
        "Game Factory Refinement Skill": "Game Factory Scout Agent",
        "Game Development Skill": "Game Developer Agent",
        "Game Art Skill": "Game Art Director Agent",
        "UI Skill": "UI Agent",
        "Verification Skill": "Verifier Agent",
        "Memory Skill": "Memory Agent",
        "File Structure Skill": "File Structure Agent",
        "Android Worker Skill": "Android Phone Agent",
        "Engel OS Bridge Skill": "Engel OS Bridge Agent",
        "Sub-Engel Worker Skill": "Sub-Engel OS Agent",
        "Windows Sub-Engel Worker Skill": "Windows Sub-Engel Agent",
        # Unique routes for previously-manual-only agents
        "Safety Review Skill": "Safety Agent",
        "Skill Building Skill": "Skill Builder Agent",
        "Engel Orchestration Skill": "Engel Core",
        "Prompt Engineering Skill": "Prompt Engineer Agent",
        # Per-phone Android worker routes
        "Android Worker Alpha Skill": "Android Phone Alpha Agent",
        "Android Worker Beta Skill": "Android Phone Beta Agent",
        "Android Worker Gamma Skill": "Android Phone Gamma Agent",
        # Finance & Markets
        "Financial Strategy Skill": "Financial Strategist Agent",
        "Stocks History Skill": "Stocks Historian Agent",
        "Market Impact Skill": "Market Impact Analyst Agent",
        "Macro Economics Skill": "Macro Economist Agent",
        "Crypto Analysis Skill": "Crypto Analyst Agent",
        "Portfolio Strategy Skill": "Portfolio Strategist Agent",
        "Quant Modeling Skill": "Quant Modeler Agent",
        "News Correlation Skill": "News Event Correlator Agent",
        "Sentiment Analysis Skill": "Sentiment Analysis Agent",
        "Trading Dashboard Bridge Skill": "Trading Dashboard Bridge Agent",
        # Web & Design
        "Web App Design Skill": "Web App Designer Agent",
        "Design System Skill": "Design System Architect Agent",
        "Accessibility Audit Skill": "Accessibility Auditor Agent",
        "UX Research Skill": "UX Research Lead Agent",
        "Mobile Web Skill": "Mobile Web Designer Agent",
        # Graph & Data Viz
        "Graph Visualization Skill": "Graph Visualization Designer Agent",
        "Data Viz Storytelling Skill": "Data Viz Storyteller Agent",
        "Chart Engineering Skill": "Chart Engineer Agent",
        "Dashboard Architecture Skill": "Dashboard Architect Agent",
        # Deep Research
        "Deep Research Skill": "Deep Research Agent",
        "Literature Review Skill": "Literature Review Agent",
        "Competitive Intelligence Skill": "Competitive Intelligence Agent",
        "Historical Context Skill": "Historical Context Agent",
        # Approved-Library reference
        "AI Safety Reference Skill": "AI Safety Reference Agent",
        "Algorithms DS Reference Skill": "Algorithms DS Reference Agent",
        "Android Worker Reference Skill": "Android Worker Reference Agent",
        "Architecture Reference Skill": "Architecture Reference Agent",
        "Patch Planning Skill": "Patch Planning Agent",
        "Language Reference Skill": "Language Reference Agent",
        "Polyglot Coding Skill": "Polyglot Coding Agent",
        "Download Failure Triage Skill": "Download Failure Triage Agent",
        "Library Receipts Audit Skill": "Library Receipts Auditor Agent",
        "Offline Seed LLM Skill": "Offline Seed LLM Agent",
        "Code Companion Skill": "Code Companion Agent",
        "Engel Manuals Skill": "Engel Manuals Agent",
        "Engel Receipts Skill": "Engel Receipts Agent",
        "LLM Reference Skill": "LLM Reference Agent",
        "Math Reference Skill": "Math Reference Agent",
        "Logic Reasoning Reference Skill": "Logic Reasoning Reference Agent",
        "Memory Systems Reference Skill": "Memory Systems Reference Agent",
        "Offline Docs Skill": "Offline Docs Agent",
        "PyInstaller Packaging Skill": "PyInstaller Packaging Agent",
        "PySide6 Qt Skill": "PySide6 Qt Agent",
        "Python Reference Skill": "Python Reference Agent",
        "Research Papers Skill": "Research Papers Agent",
        "RAG Retrieval Skill": "RAG Retrieval Agent",
        "Prompt Injection Defense Skill": "Prompt Injection Defense Agent",
        "SQLite Reference Skill": "SQLite Reference Agent",
        "Static Analysis Skill": "Static Analysis Agent",
        "Pytest Testing Skill": "Pytest Testing Agent",
        "WSL Ubuntu Runtime Skill": "WSL Ubuntu Runtime Agent",
        "Agency Specialist Skill": "Agency Specialist Agent",
        "Custom Skill": "Custom Agent",
    }
    return mapping.get(skill, "Engel Core")


def _skill_for_agent(agent: str) -> str:
    mapping = {
        "Architect Agent": "Architect Workflow Skill",
        "Grok Bot": "Grok Bot Teammate Skill",
        "Math Agent": "Math Skill",
        "Research Agent": "Research Skill",
        "Code Agent": "Coding Skill",
        "Hermes Agent": "Hermes Agent Skill",
        "Code Factory Scout Agent": "Code Factory Scout Skill",
        "Game Factory Scout Agent": "Game Factory Refinement Skill",
        "Game Developer Agent": "Game Development Skill",
        "Game Art Director Agent": "Game Art Skill",
        "UI Agent": "UI Skill",
        "Verifier Agent": "Verification Skill",
        "Memory Agent": "Memory Skill",
        "File Structure Agent": "File Structure Skill",
        "Skill Builder Agent": "Skill Building Skill",
        "Safety Agent": "Safety Review Skill",
        "Prompt Engineer Agent": "Prompt Engineering Skill",
        "Engel Core": "Engel Orchestration Skill",
        # Per-phone Android worker agents
        "Android Phone Alpha Agent": "Android Worker Alpha Skill",
        "Android Phone Beta Agent": "Android Worker Beta Skill",
        "Android Phone Gamma Agent": "Android Worker Gamma Skill",
        # Finance & Markets
        "Financial Strategist Agent": "Financial Strategy Skill",
        "Stocks Historian Agent": "Stocks History Skill",
        "Market Impact Analyst Agent": "Market Impact Skill",
        "Macro Economist Agent": "Macro Economics Skill",
        "Crypto Analyst Agent": "Crypto Analysis Skill",
        "Portfolio Strategist Agent": "Portfolio Strategy Skill",
        "Quant Modeler Agent": "Quant Modeling Skill",
        "News Event Correlator Agent": "News Correlation Skill",
        "Sentiment Analysis Agent": "Sentiment Analysis Skill",
        "Trading Dashboard Bridge Agent": "Trading Dashboard Bridge Skill",
        "Engel OS Bridge Agent": "Engel OS Bridge Skill",
        # Web & Design
        "Web App Designer Agent": "Web App Design Skill",
        "Design System Architect Agent": "Design System Skill",
        "Accessibility Auditor Agent": "Accessibility Audit Skill",
        "UX Research Lead Agent": "UX Research Skill",
        "Mobile Web Designer Agent": "Mobile Web Skill",
        # Graph & Data Viz
        "Graph Visualization Designer Agent": "Graph Visualization Skill",
        "Data Viz Storyteller Agent": "Data Viz Storytelling Skill",
        "Chart Engineer Agent": "Chart Engineering Skill",
        "Dashboard Architect Agent": "Dashboard Architecture Skill",
        # Deep Research
        "Deep Research Agent": "Deep Research Skill",
        "Literature Review Agent": "Literature Review Skill",
        "Competitive Intelligence Agent": "Competitive Intelligence Skill",
        "Historical Context Agent": "Historical Context Skill",
        # Approved-Library reference
        "AI Safety Reference Agent": "AI Safety Reference Skill",
        "Algorithms DS Reference Agent": "Algorithms DS Reference Skill",
        "Android Worker Reference Agent": "Android Worker Reference Skill",
        "Architecture Reference Agent": "Architecture Reference Skill",
        "Patch Planning Agent": "Patch Planning Skill",
        "Language Reference Agent": "Language Reference Skill",
        "Polyglot Coding Agent": "Polyglot Coding Skill",
        "Download Failure Triage Agent": "Download Failure Triage Skill",
        "Library Receipts Auditor Agent": "Library Receipts Audit Skill",
        "Offline Seed LLM Agent": "Offline Seed LLM Skill",
        "Code Companion Agent": "Code Companion Skill",
        "Engel Manuals Agent": "Engel Manuals Skill",
        "Engel Receipts Agent": "Engel Receipts Skill",
        "LLM Reference Agent": "LLM Reference Skill",
        "Math Reference Agent": "Math Reference Skill",
        "Logic Reasoning Reference Agent": "Logic Reasoning Reference Skill",
        "Memory Systems Reference Agent": "Memory Systems Reference Skill",
        "Offline Docs Agent": "Offline Docs Skill",
        "PyInstaller Packaging Agent": "PyInstaller Packaging Skill",
        "PySide6 Qt Agent": "PySide6 Qt Skill",
        "Python Reference Agent": "Python Reference Skill",
        "Research Papers Agent": "Research Papers Skill",
        "RAG Retrieval Agent": "RAG Retrieval Skill",
        "Prompt Injection Defense Agent": "Prompt Injection Defense Skill",
        "SQLite Reference Agent": "SQLite Reference Skill",
        "Static Analysis Agent": "Static Analysis Skill",
        "Pytest Testing Agent": "Pytest Testing Skill",
        "WSL Ubuntu Runtime Agent": "WSL Ubuntu Runtime Skill",
        "Agency Specialist Agent": "Agency Specialist Skill",
        "Custom Agent": "Custom Skill",
    }
    return mapping.get(agent, "Custom Skill")


def _normalize_bridge(bridge: str) -> str:
    raw = str(bridge or "").strip()
    if not raw:
        return "Engel Chat Auto Route"
    if raw in BRIDGE_OPTIONS:
        return raw
    low = raw.lower()
    if "engel os" in low or "engel-os" in low or "ready to flash" in low or "usb flashing" in low or "packet 016" in low:
        return "Engel OS Bridge (read-only)"
    if "trading dashboard" in low or "engel-dashboard" in low or "snaptrade" in low or "robinhood" in low:
        return "Trading Dashboard Bridge (Engel Dashboard)"
    if "grok bot" in low or "cluster teammate" in low:
        return "Grok Bot (cluster teammate)"
    if "architect" in low:
        return "Engel Architect Agent (engel_architect_agent)"
    if "codex" in low:
        return "Codex API / Codex Bridge (Engel Agent)"
    if "game factory" in low:
        return "Game Factory Scout (Engel Meeting Room)"
    if "code factory" in low or "scout" in low:
        return "Code Factory Scout (Engel Meeting Room)"
    if "claude" in low:
        return "Claude API / Claude Bridge (Engel provider)"
    if "openai" in low or "chatgpt" in low:
        return "ChatGPT Bridge (Engel no-API handoff)"
    if "lfm" in low or "airllm" in low or "local" in low:
        return "Local LLM (offline seed / GGUF)"
    if "multi" in low and "model" in low or "code gen" in low or "polyglot" in low:
        return "Local Multi-Model Code Gen"
    if "translate" in low or "port to" in low or "convert to" in low:
        return "Local Code Translate (multi-model)"
    if "best" in low and "code" in low or "auto code" in low:
        return "Local Best Auto Code (smart model)"
    if "candidates" in low or "multi model" in low:
        return "Local Multi-Model Candidates"
    if "stage" in low and "sub" in low or "fleet code" in low:
        return "Stage to Sub-Engel (code gen job)"
    if "android" in low:
        return "Android Worker Job Packet"
    if "windows" in low and "sub" in low:
        return "Windows Sub-Engel Job Packet"
    if "sub-engel" in low:
        return "Sub-Engel Job Packet"
    if "none" in low:
        return "None (local-only)"
    return raw


def _target_is_local(target: str) -> bool:
    return "Local Engel AI" in str(target or "")


def _target_is_android(target: str) -> bool:
    return "Android App Worker" in str(target or "")


def _target_is_sub_engel(target: str) -> bool:
    return "Sub-Engel OS Worker" in str(target or "")


def _target_is_windows_sub_engel(target: str) -> bool:
    return "Windows Sub-Engel Node" in str(target or "")


def _target_is_wifi(target: str) -> bool:
    low = str(target or "").lower()
    return "wifi" in low or "lan" in low


def _target_is_hardwire(target: str) -> bool:
    low = str(target or "").lower()
    return "usb" in low or "hardwire" in low


def _participant_from_raw(raw: dict) -> Participant:
    data = dict(raw or {})
    if "skill_label" not in data or not str(data.get("skill_label") or "").strip():
        type_label = str(data.get("type_label") or "")
        kind = str(data.get("kind") or "agent")
        if kind == "skill" or type_label in SKILL_TYPES:
            data["skill_label"] = type_label if type_label in SKILL_TYPES else "Custom Skill"
            data["type_label"] = _agent_for_skill(data["skill_label"])
            data["kind"] = "agent"
        else:
            data["skill_label"] = _skill_for_agent(type_label)
    data["bridge"] = _normalize_bridge(str(data.get("bridge") or ""))
    equipment = str(data.get("equipment") or "")
    # Legacy short-form normalisation
    if equipment == "Local Engel AI":
        data["equipment"] = "Local Engel AI (main PC)"
    elif equipment == "Android App Worker":
        data["equipment"] = "Android App Worker — USB / hardwire ADB"
    elif equipment == "Sub-Engel OS Worker":
        data["equipment"] = "Sub-Engel OS Worker — WiFi / LAN diagnostics"
    elif equipment == "Windows Sub-Engel Node":
        data["equipment"] = "Windows Sub-Engel Node - LAN check-in"
    # Hyphen → em-dash migration so old room_state.json values stay readable.
    elif " - " in equipment and any(
        equipment.startswith(p) for p in (
            "Android App Worker",
            "Sub-Engel OS Worker",
            "Windows Sub-Engel Node",
        )
    ):
        data["equipment"] = equipment.replace(" - ", " — ", 1)
    data["name"] = f"{data.get('type_label', 'Agent')} / {data.get('skill_label', 'Skill')}"
    allowed = {field.name for field in Participant.__dataclass_fields__.values()}
    return Participant(**{k: v for k, v in data.items() if k in allowed})


def _load_state() -> RoomState:
    _ensure_dirs()
    if not ROOM_STATE_FILE.exists():
        state = RoomState(created_at=_now_iso())
        _save_state(state)
        return state
    try:
        raw = json.loads(ROOM_STATE_FILE.read_text(encoding="utf-8"))
        parts = [_participant_from_raw(p) for p in raw.get("participants", [])]
        msgs = list(raw.get("messages", []))
        return RoomState(
            room_name=raw.get("room_name", "Engel Default Room"),
            created_at=raw.get("created_at", _now_iso()),
            goal=raw.get("goal", "Coordinate agents and skills."),
            project=raw.get("project", "(unset)"),
            open_task=raw.get("open_task", "(unset)"),
            safety_state=raw.get("safety_state", "LOCAL ONLY — no remote control"),
            last_export=raw.get("last_export", ""),
            participants=parts,
            messages=msgs,
        )
    except Exception:
        return RoomState(created_at=_now_iso())


def _save_state(state: RoomState) -> None:
    _ensure_dirs()
    payload = asdict(state)
    ROOM_STATE_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _load_self_upgrade_work_orders(limit: int = 5) -> list[dict]:
    _ensure_dirs()
    found: dict[str, dict] = {}
    for root in (SELF_UPGRADE_WORK_ORDER_DIR, SELF_UPGRADE_RUNTIME_WORK_ORDER_DIR):
        for path in sorted(root.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                data = json.loads(path.read_text(encoding="utf-8-sig"))
            except Exception:
                continue
            if data.get("schema") != "ENGEL_MEETING_ROOM_SELF_UPGRADE_WORK_ORDER_V1":
                continue
            work_order_id = str(data.get("work_order_id") or path.stem)
            data["_path"] = str(path)
            found.setdefault(work_order_id, data)
    items = list(found.values())
    items.sort(key=lambda item: str(item.get("created_at_utc") or ""), reverse=True)
    return items[:limit]


def _latest_self_upgrade_work_order_ui_text() -> str:
    work_orders = _load_self_upgrade_work_orders(limit=3)
    if not work_orders:
        return "No self-upgrade work orders yet."
    rows: list[str] = []
    for item in work_orders:
        rows.append(
            f"{item.get('work_order_id', 'work-order')} | "
            f"{item.get('state', 'unknown')} | "
            f"{item.get('owner_lane', 'unknown')} | "
            f"risk {item.get('risk_level', 'unknown')} | "
            f"{item.get('summary', '')}"
        )
    return "\n".join(rows)


def export_room_summary(state: RoomState) -> Path:
    _ensure_dirs()
    fname = _stamp_filename()
    path = REPORTS_DIR / fname
    lines: list[str] = []
    lines.append(f"# Agent Meeting Room — {state.room_name}")
    lines.append("")
    lines.append("## Collaboration charter")
    lines.append("")
    lines.append(SHIP_TEAM_COLLAB_CHARTER)
    lines.append("")
    lines.append(f"- Created: {state.created_at}")
    lines.append(f"- Exported: {_now_iso()}")
    lines.append(f"- Project: {state.project}")
    lines.append(f"- Goal: {state.goal}")
    lines.append(f"- Open task: {state.open_task}")
    lines.append(f"- Safety: {state.safety_state}")
    lines.append("")
    lines.append("## Participants")
    if not state.participants:
        lines.append("(none)")
    else:
        for p in state.participants:
            lines.append(
                f"- **{p.name}** ({p.kind} / {p.type_label} / skill: {p.skill_label}) "
                f"-> {p.equipment} [{p.status}]  bridge: {p.bridge}"
            )
    lines.append("")
    lines.append("## Bridge Assignments")
    bridge_map: dict[str, list[str]] = {}
    for p in state.participants:
        bridge_map.setdefault(p.bridge, []).append(f"{p.name} / {p.skill_label} ({p.kind})")
    if not bridge_map:
        lines.append("(no participants)")
    else:
        for bridge_name, members in sorted(bridge_map.items()):
            lines.append(f"- **{bridge_name}** ({len(members)})")
            for m in members:
                lines.append(f"  - {m}")
    lines.append("")
    lines.append("## Self-Upgrade Work Orders")
    work_orders = _load_self_upgrade_work_orders(limit=8)
    if not work_orders:
        lines.append("(none)")
    else:
        for item in work_orders:
            lines.append(
                f"- `{item.get('work_order_id')}` state={item.get('state')} "
                f"owner={item.get('owner_lane')} risk={item.get('risk_level')} "
                f"issue={item.get('issue_id')}"
            )
            lines.append(f"  - {item.get('summary', '')}")
    lines.append("")
    latest_route = _latest_prompt_route_record()
    lines.append("## Latest Bridge Selection / Prompt Route")
    if latest_route:
        order_id = latest_route.get("_order_id", "(unknown)")
        lines.append(f"- Order: `{order_id}`")
        lines.append(f"- Task type: {latest_route.get('task_type')}")
        lines.append(f"- Prompt type: {latest_route.get('prompt_type')}")
        lines.append(f"- Primary agent: {latest_route.get('primary_agent')}")
        support = latest_route.get("support_agents") or []
        support_text = ", ".join(str(item) for item in support) if isinstance(support, list) else str(support)
        lines.append(f"- Support agents: {support_text or 'none'}")
        lines.append(f"- Preferred bridge: {latest_route.get('preferred_bridge')}")
        lines.append(f"- Meeting bridge: {latest_route.get('meeting_bridge')}")
        lines.append(f"- Bridge status: {latest_route.get('bridge_status')}")
        lines.append(f"- Equipment target: {latest_route.get('equipment_target')}")
        lines.append(f"- Output format: {latest_route.get('output_format')}")
    else:
        lines.append("(no prompt route recorded yet)")
    lines.append("")
    lines.append("## Equipment Assignments")
    eq_map: dict[str, list[str]] = {}
    for p in state.participants:
        eq_map.setdefault(p.equipment, []).append(f"{p.name} / {p.skill_label} ({p.kind})")
    for eq in EQUIPMENT_TARGETS:
        bucket = eq_map.get(eq, [])
        lines.append(f"- **{eq}** ({len(bucket)})")
        for b in bucket:
            lines.append(f"  - {b}")
    lines.append("")
    lines.append("## Messages")
    if not state.messages:
        lines.append("(no messages)")
    else:
        for m in state.messages:
            t = m.get("time", "?")
            role = m.get("role", "?")
            name = m.get("name", "?")
            text = m.get("text", "")
            lines.append(f"- {t} [{role}] {name}: {text}")
    lines.append("")
    lines.append("## Safety Notes")
    lines.append("- Work launches use existing Engel route/provider/device gates.")
    lines.append("- No raw shell, SSH, disk formatting, or secret capture is available here.")
    lines.append("- Sub-Engel receives staged job packets for bounded AI work on additional computers (local gate on node).")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _label(text: str, color: str = TEXT, size: int = 9, bold: bool = False):
    lbl = QLabel(text)
    style = f"color: {color}; font-size: {size}pt;"
    if bold:
        style += " font-weight: 700;"
    lbl.setStyleSheet(style)
    return lbl


def _card() -> QFrame:
    f = QFrame()
    f.setObjectName("card")
    return f


def _divider() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet(f"color: {BORDER2}; background: {BORDER2}; max-height: 1px;")
    return line


def _bridge_short(bridge: str) -> str:
    return str(bridge or "Engel Chat Auto Route").split(" (", 1)[0]


def _clip(text: str, limit: int = 900) -> str:
    clean = str(text or "").strip()
    if len(clean) <= limit:
        return clean
    return clean[: max(0, limit - 3)].rstrip() + "..."


def _append_state_message(state: RoomState, name: str, text: str, role: str = "system") -> None:
    state.messages.append({
        "role": role,
        "name": name,
        "text": str(text or "").strip(),
        "time": _now_pretty(),
    })


def _collaboration_reply_preview(text: str, limit: int = 180) -> str:
    clean = " ".join(str(text or "").split())
    return _clip(clean, limit)


def _build_collaboration_dialogue(
    order_text: str,
    job_type: str,
    station_outcomes: list[dict],
) -> list[dict]:
    """Build the visible agent-to-agent handoff transcript for an order."""
    if not station_outcomes:
        return []
    turns: list[dict] = [
        {
            "role": "system",
            "name": "Meeting Room Router",
            "text": (
                f"I split the {job_type} request into {len(station_outcomes)} station pass(es) "
                "so the selected agents can compare notes before Engel answers."
            ),
        }
    ]
    for outcome in station_outcomes:
        agent = str(outcome.get("agent") or "Agent")
        skill = str(outcome.get("skill") or "Unassigned Skill")
        device = str(outcome.get("equipment") or "Unassigned device")
        bridge = _bridge_short(str(outcome.get("bridge") or "Engel Chat Auto Route"))
        status = str(outcome.get("status") or "Assigned")
        preview = _collaboration_reply_preview(str(outcome.get("reply") or ""))
        if "Verification" in skill or agent == "Verifier Agent":
            text = (
                f"I am checking the room result after the worker/agent pass. "
                f"Status: {status}. Evidence: {preview or 'no returned preview'}"
            )
        elif _target_is_android(device):
            text = (
                f"I took the device-worker pass on {device} using {skill}. "
                f"Status: {status}. Candidate note: {preview or 'packet staged for phone worker'}"
            )
        else:
            text = (
                f"I handled the {skill} pass through {bridge} on {device}. "
                f"Status: {status}. Note for the team: {preview or 'main UI context received'}"
            )
        turns.append({"role": "agent", "name": agent, "text": text})
    turns.append({
        "role": "system",
        "name": "Meeting Room Router",
        "text": "I collected the station notes, kept phone outputs review-only, and returned the combined result to Engel AI Main UI.",
    })
    return turns


def _looks_like_main_order(text: str) -> bool:
    low = str(text or "").lower().strip()
    if not low:
        return False
    if is_android_lan_pairing_request(text):
        return False
    simple_chat = {
        "hi", "hello", "hey", "thanks", "thank you", "ok", "okay",
        "yes", "no", "status", "help",
    }
    if low in simple_chat:
        return False
    order_words = (
        "add", "build", "change", "check", "clean", "complete", "connect",
        "create", "debug", "draft", "fix", "generate", "install", "make", "mkae",
        "merge", "move", "organize", "polish", "refactor", "remove",
        "research", "rework", "route", "run", "search", "show", "solve",
        "test", "update", "verify", "wire", "write", "right",
    )
    if any(re.search(rf"\b{re.escape(word)}\b", low) for word in order_words):
        return True
    if any(needle in low for needle in ("pdf", "video game", " code", "internet", "web search")):
        return True
    return len(low.split()) >= 6


def _device_first_skill_for_order(text: str) -> str | None:
    """Prefer connected device workers before assigning work to the main PC.

    Android workers are bounded to candidate/report-style work packets. This
    keeps routine summarizing, JSON drafting, report formatting, and light
    classification off the main system when a paired phone can take the first
    pass. Explicit local/GPU/desktop work still stays on the main PC.
    """
    low = str(text or "").lower()
    local_required = (
        "use main pc",
        "run on main pc",
        "use main computer",
        "run on main computer",
        "local gpu",
        "use gpu",
        "desktop window",
        "engel os",
        "engel-os",
        "d:\\engel os",
        "sub-engel",
        "sub engel",
        "pyinstaller",
        "rebuild exe",
        "compile exe",
    )
    source_merge = bool(re.search(r"\b(?:merge|merging)\b", low)) and any(
        needle in low
        for needle in ("engel", "source", "module", "code", "meeting room", "bridge selection", "prompt engineering")
    )
    if source_merge:
        return None
    if any(needle in low for needle in local_required):
        return None
    try:
        from engel_device_capability_registry import infer_job_type_from_text, select_worker_for_job
        job_type = infer_job_type_from_text(text, _infer_job_type(text))
        selected = select_worker_for_job(job_type, text)
    except Exception:
        selected = None
    worker_id = str((selected or {}).get("worker_id") or "")
    if worker_id == "android_worker_alpha":
        return "Android Worker Alpha Skill"
    if worker_id == "android_worker_beta":
        return "Android Worker Beta Skill"
    if worker_id == "android_worker_gamma":
        return "Android Worker Gamma Skill"
    if worker_id.startswith("android_worker_"):
        return "Android Worker Skill"
    return None


def _infer_skills_for_order(text: str) -> list[str]:
    low = str(text or "").lower()
    multi_device_job_requested = (
        any(needle in low for needle in ("all devices", "all workers", "all connected devices", "whole room", "full room"))
        or (
            any(needle in low for needle in ("alpha", "worker alpha", "phone alpha"))
            and any(needle in low for needle in ("beta", "worker beta", "phone beta"))
            and any(needle in low for needle in ("sub-engel", "sub engel", "windows node", "desktop-ue5a6gg", "ue5a6gg"))
        )
        or (
            any(needle in low for needle in ("phone workers", "phones", "android workers"))
            and any(needle in low for needle in ("sub-engel", "sub engel", "windows node", "desktop-ue5a6gg", "ue5a6gg"))
        )
    )
    if multi_device_job_requested:
        return [
            "Engel Orchestration Skill",
            "Android Worker Alpha Skill",
            "Android Worker Beta Skill",
            "Android Worker Gamma Skill",
            "Windows Sub-Engel Worker Skill",
            "Verification Skill",
        ]
    pairing_request = is_android_lan_pairing_request(low)
    windows_sub_node_requested = any(
        needle in low
        for needle in (
            "sub-engel node",
            "sub engel node",
            "windows sub-engel",
            "windows sub engel",
            "windows node",
            "desktop-ue5a6gg",
            "ue5a6gg",
        )
    )
    scored: list[tuple[int, str]] = []
    rules = [
        ("Architect Workflow Skill", ("architect", "blueprint", "spec.md", "plan.md", "13-section", "13 section", "planner phase", "founder approval", "executor handoff")),
        ("Math Skill", ("math", "arithmetic", "algebra", "equation", "unit", "fraction", "logic", "graph theory", "math graph", "probability", "statistics", "train")),
        ("Code Factory Scout Skill", ("code factory", "factory scout", "scout spec", "builder-ready spec", "issue queue", "qa gate", "shipper station")),
        ("Game Factory Refinement Skill", ("game factory", "factory refine", "refine game", "game refinement", "longer stages", "long stage", "better controls", "control polish", "polish controls", "smoother jumping", "dash", "weapon cycling")),
        ("Game Development Skill", ("game development", "video game", "browser game", "create a game", "make a game", "build a game", "arcade", "run-and-gun", "run and gun", "side-scrolling", "side scrolling", "platformer", "playable game", "phaser", "gameplay", "weapon upgrade", "weapon upgrades", "boss fight", "boss at end", "stages", "stage parts")),
        ("Game Art Skill", ("game art", "sprite", "sprites", "asset", "assets", "animation", "high quality", "graphics", "visual polish", "not box", "not blocky", "pixel art", "background settings", "different background", "different backgrounds")),
        ("Coding Skill", ("code", "api", "function", "bug", "fix", "refactor", "wire", "route", "connect", "script", "game", "video game")),
        ("Hermes Agent Skill", ("hermes", "hermes agent", "hermes-agent", "agent toolset", "agent toolsets", "agent cli", "list agent tools", "agent inventory", "mini swe", "datagen", "acp adapter", "agent gateway")),
        ("UI Skill", ("ui", "screen", "window", "button", "card", "layout", "transparent", "translucent", "view", "app language", "microcopy", "wording", "error message", "error messages", "touch controls", "hud")),
        ("Verification Skill", ("verify", "test", "check", "compile", "screenshot", "safe", "safety")),
        ("Memory Skill", ("memory", "long term", "remember", "report", "handoff", "receipt")),
        ("File Structure Skill", ("folder", "organize", "archive", "cleanup", "file", "project", "put it here")),
        ("Android Worker Skill", ("android worker", "adb worker", "worker queue", "phone worker", "device worker")),
        ("Engel OS Bridge Skill", ("engel os", "engel-os", "d:\\engel os", "ready_to_flash", "ready to flash", "usb flashing guide", "engel_os_usb_flashing_guide", "sub-node live iso", "packet 016", "packet_016", "hooked up to engel ai")),
        ("Windows Sub-Engel Worker Skill", ("sub-engel node", "sub engel node", "windows sub-engel", "windows sub engel", "windows node", "laptop", "desktop", "fib17o7", "ue5a6gg")),
        ("Sub-Engel Worker Skill", ("sub-engel os", "sub engel os", "linux sub-engel", "linux sub engel", "iso", "cluster", "firmware")),
        ("Research Skill", ("research", "look up", "search internet", "search online", "web search", "internet", "explain", "plan", "compare", "diagnose")),
        # ── Previously-manual-only agents, now auto-selectable ──
        ("Safety Review Skill", ("safety review", "safety audit", "incident review", "near miss", "guardian check", "safety gate")),
        ("Skill Building Skill", ("build skill", "new skill", "skill candidate", "skill builder", "skill scaffold")),
        ("Engel Orchestration Skill", ("engel orchestrate", "orchestrate the room", "engel core route", "engel coordinate the team", "engel dispatch")),
        ("Prompt Engineering Skill", ("prompt engineering", "prompt route", "bridge selection", "which bridge", "model selection", "few-shot", "prompt template")),
        ("Custom Skill", ("custom skill", "bespoke role", "ad-hoc agent")),
        # ── Per-phone Android worker (deterministic per-phone routing) ──
        ("Android Worker Alpha Skill", ("worker alpha", "phone alpha", "alpha worker", "moto g power")),
        ("Android Worker Beta Skill", ("worker beta", "phone beta", "beta worker", "moto g fast")),
        ("Android Worker Gamma Skill", ("worker gamma", "phone gamma", "gamma worker", "galaxy a14", "samsung galaxy")),
        # ── Finance & Markets ──
        ("Trading Dashboard Bridge Skill", ("engel-dashboard", "engel dashboard", "trading dashboard", "trade dashboard", "snaptrade", "robinhood", "paper trader", "paper trading", "auto trader", "autonomous paper", "portfolio dashboard", "market dashboard", "circuit breaker", "agent_design.md", "safety_rules.md", "snaptrade_setup.md")),
        ("Financial Strategy Skill", ("budget", "monetization", "cash flow", "burn rate", "ltv", "cac", "runway", "p&l", "revenue forecast", "unit economics")),
        ("Stocks History Skill", ("stock history", "stock chart", "ticker", "ohlcv", "share price", "dividend", "stock split", "stock price")),
        ("Market Impact Skill", ("market reaction", "event study", "market impact", "fed announcement", "rate hike", "market shock")),
        ("Macro Economics Skill", ("gdp", "cpi", "inflation regime", "macro regime", "recession", "fed policy", "central bank")),
        ("Crypto Analysis Skill", ("btc", "ethereum", "crypto", "bitcoin", "on-chain", "halving", "defi")),
        ("Portfolio Strategy Skill", ("portfolio", "asset allocation", "rebalance", "diversif")),
        ("Quant Modeling Skill", ("backtest", "monte carlo", "quant model", "sharpe ratio", "factor model")),
        ("News Correlation Skill", ("news correlation", "earnings call", "news event")),
        ("Sentiment Analysis Skill", ("sentiment", "tone shift", "narrative")),
        # ── Web & Design ──
        ("Web App Design Skill", ("web app design", "wireframe", "user flow", "information architecture")),
        ("Design System Skill", ("design system", "design token", "component library")),
        ("Accessibility Audit Skill", ("accessibility", "a11y", "wcag", "screen reader")),
        ("UX Research Skill", ("ux research", "usability test", "user interview", "persona")),
        ("Mobile Web Skill", ("mobile web", "responsive", "pwa", "touch target")),
        # ── Graph & Data Viz ──
        ("Graph Visualization Skill", ("force-directed", "node-link", "graph viz", "sankey", "dependency graph", "network diagram")),
        ("Data Viz Storytelling Skill", ("data viz", "explanatory chart", "editorial chart")),
        ("Chart Engineering Skill", ("recharts", "d3.js", "plotly", "echarts", "chart library")),
        ("Dashboard Architecture Skill", ("dashboard", "kpi", "grafana")),
        # ── Deep Research ──
        ("Deep Research Skill", ("deep research", "multi-source", "synthesize", "cited research")),
        ("Literature Review Skill", ("literature review", "academic paper", "survey of the field")),
        ("Competitive Intelligence Skill", ("competitor", "competitive landscape", "market scan")),
        ("Historical Context Skill", ("historical context", "history of", "long view")),
        # ── Approved-Library reference ──
        ("AI Safety Reference Skill", ("ai safety", "nist ai rmf", "owasp agentic")),
        ("Algorithms DS Reference Skill", ("algorithm", "data structure", "complexity bound", "cp-algorithm")),
        ("Android Worker Reference Skill", ("android architecture", "android permission", "android background", "workmanager")),
        ("Architecture Reference Skill", ("event log", "local first", "plugin system", "verifier system", "system architecture")),
        ("Patch Planning Skill", ("patch plan", "code review", "pull request", "pr review")),
        ("Language Reference Skill", ("bash syntax", "c language", "commonmark", "css reference", "language for this app", "app language", "error message", "error messages")),
        ("Polyglot Coding Skill", ("language choice", "data format", "csharp")),
        ("Download Failure Triage Skill", ("download failure", "intake failure")),
        ("Library Receipts Audit Skill", ("library receipt", "provenance", "intake receipt")),
        ("Offline Seed LLM Skill", ("offline seed", "llama-cpp-python", "qwen", "seed llm")),
        ("Code Companion Skill", ("code companion", "ast module", "difflib", "inspect module")),
        ("Engel Manuals Skill", ("engel manual", "command map", "continuity map")),
        ("Engel Receipts Skill", ("engel report", "engel receipt", "engel plan")),
        ("LLM Reference Skill", ("gguf", "llama.cpp")),
        ("Math Reference Skill", ("calculus", "discrete math reference")),
        ("Logic Reasoning Reference Skill", ("linear algebra", "introductory statistics", "proof technique")),
        ("Memory Systems Reference Skill", ("memgpt", "event sourcing", "agent memory")),
        ("Offline Docs Skill", ("offline doc",)),
        ("PyInstaller Packaging Skill", ("pyinstaller", "spec file", "frozen build")),
        ("PySide6 Qt Skill", ("pyside6", "qwidget", "signal slot")),
        ("Python Reference Skill", ("python stdlib", "python tutorial", "standard library")),
        ("Research Papers Skill", ("research paper", "arxiv paper")),
        ("RAG Retrieval Skill", ("rag", "retrieval pipeline", "vector store", "embedding index")),
        ("Prompt Injection Defense Skill", ("prompt injection", "llm security", "owasp llm")),
        ("SQLite Reference Skill", ("sqlite", "wal mode")),
        ("Static Analysis Skill", ("mypy", "ruff", "pylint", "static analysis")),
        ("Pytest Testing Skill", ("pytest", "fixture", "parametrize")),
        ("WSL Ubuntu Runtime Skill", ("wsl", "ubuntu server", "/mnt/")),
    ]
    for skill, needles in rules:
        score = sum(1 for needle in needles if needle in low)
        if score:
            scored.append((score, skill))
    scored.sort(key=lambda item: (-item[0], item[1]))
    skills = [skill for _score, skill in scored[:6]]
    if windows_sub_node_requested:
        skills = [skill for skill in skills if skill != "Sub-Engel Worker Skill"]
        if "Windows Sub-Engel Worker Skill" not in skills:
            skills.insert(0, "Windows Sub-Engel Worker Skill")
    if pairing_request:
        skills = [skill for skill in skills if skill != "Coding Skill"]
        if "Android Worker Skill" not in skills:
            skills.insert(0, "Android Worker Skill")
    if "Game Factory Refinement Skill" in skills and "Game Development Skill" not in skills:
        skills.append("Game Development Skill")
    if "Game Development Skill" in skills:
        skills = [skill for skill in skills if skill != "Coding Skill"]
        for required in ("Game Art Skill", "UI Skill"):
            if required not in skills:
                skills.append(required)
    if "Trading Dashboard Bridge Skill" in skills:
        for required in (
            "Safety Review Skill",
            "Portfolio Strategy Skill",
            "Quant Modeling Skill",
            "Dashboard Architecture Skill",
        ):
            if required not in skills:
                skills.append(required)
    if "Engel OS Bridge Skill" in skills:
        for required in (
            "Sub-Engel Worker Skill",
            "Safety Review Skill",
            "Verification Skill",
        ):
            if required not in skills:
                skills.append(required)
    # If the user/Engel main UI names a specific phone worker, route to that
    # station instead of letting the generic Android Worker station claim it.
    # The generic skill is still useful for "any phone worker" jobs.
    if any(skill in skills for skill in ("Android Worker Alpha Skill", "Android Worker Beta Skill", "Android Worker Gamma Skill")):
        skills = [skill for skill in skills if skill != "Android Worker Skill"]
    if "Verification Skill" not in skills:
        skills.append("Verification Skill")
    if not skills:
        skills = ["Research Skill", "Verification Skill"]
    device_first = _device_first_skill_for_order(text)
    if device_first and device_first not in skills:
        skills.insert(0, device_first)
    if device_first in ("Android Worker Alpha Skill", "Android Worker Beta Skill", "Android Worker Gamma Skill"):
        skills = [skill for skill in skills if skill != "Android Worker Skill"]
    seen: set[str] = set()
    ordered: list[str] = []
    for skill in skills:
        if skill not in seen:
            ordered.append(skill)
            seen.add(skill)
    if "Game Development Skill" in ordered:
        priority: list[str] = []
        for skill in (
            "Android Worker Alpha Skill",
            "Android Worker Beta Skill",
            "Android Worker Gamma Skill",
            "Android Worker Skill",
            "Game Factory Refinement Skill",
            "Game Development Skill",
            "Game Art Skill",
            "UI Skill",
            "Verification Skill",
        ):
            if skill in ordered and skill not in priority:
                priority.append(skill)
        for skill in ordered:
            if skill not in priority:
                priority.append(skill)
        ordered = priority
    if "Trading Dashboard Bridge Skill" in ordered:
        priority = []
        for skill in (
            "Trading Dashboard Bridge Skill",
            "Safety Review Skill",
            "Portfolio Strategy Skill",
            "Quant Modeling Skill",
            "Dashboard Architecture Skill",
            "Verification Skill",
        ):
            if skill in ordered and skill not in priority:
                priority.append(skill)
        for skill in ordered:
            if skill not in priority:
                priority.append(skill)
        ordered = priority
        if len(ordered) > 6 and "Verification Skill" in ordered:
            return [skill for skill in ordered if skill != "Verification Skill"][:5] + ["Verification Skill"]
        return ordered[:6]
    if "Engel OS Bridge Skill" in ordered:
        priority = []
        for skill in (
            "Engel OS Bridge Skill",
            "Sub-Engel Worker Skill",
            "Safety Review Skill",
            "Verification Skill",
        ):
            if skill in ordered and skill not in priority:
                priority.append(skill)
        return priority
    if "Game Factory Refinement Skill" in ordered and len(ordered) > 6 and "Verification Skill" in ordered:
        return [skill for skill in ordered if skill != "Verification Skill"][:5] + ["Verification Skill"]
    if "Game Factory Refinement Skill" in ordered:
        return ordered[:6]
    if "Game Development Skill" in ordered and len(ordered) <= 6:
        return ordered[:6]
    if len(ordered) > 5 and "Verification Skill" in ordered:
        return [skill for skill in ordered if skill != "Verification Skill"][:4] + ["Verification Skill"]
    return ordered[:5]


def _infer_job_type(text: str) -> str:
    low = str(text or "").lower()
    try:
        from engel_device_capability_registry import infer_job_type_from_text
        routed = infer_job_type_from_text(text, "")
        if routed:
            return routed
    except Exception:
        pass
    if is_android_lan_pairing_request(low):
        return "return_status"
    if "search internet" in low or "search online" in low or "web search" in low or "look online" in low:
        return "web_research_brief"
    if any(needle in low for needle in ("make this file", "mkae this file", "create file", "write file", "put it here", "save file")):
        return "summarize_text"
    if "pdf" in low:
        return "format_report_draft"
    if "write code" in low or "code for" in low or "script" in low or "function" in low or "game" in low:
        return "draft_code_artifact"
    if "format report" in low or "report draft" in low or "artifact" in low:
        return "format_report_draft"
    if "summarize" in low or "summary" in low or "research note" in low:
        return "summarize_text"
    if "candidate json" in low or " json" in low or "json " in low:
        return "draft_candidate_json"
    if "classify" in low or "label" in low:
        return "classify_text"
    if "extract" in low or "field" in low:
        return "extract_fields"
    return "summarize_text"


def _android_worker_record_for_skill(skill: str, order_text: str) -> dict | None:
    requested_worker = None
    if skill == "Android Worker Alpha Skill":
        requested_worker = "android_worker_alpha"
    elif skill == "Android Worker Beta Skill":
        requested_worker = "android_worker_beta"
    elif skill == "Android Worker Gamma Skill":
        requested_worker = "android_worker_gamma"
    try:
        from engel_device_capability_registry import select_worker_for_job
        return select_worker_for_job(_infer_job_type(order_text), order_text, requested_worker=requested_worker)
    except Exception:
        return None


def _android_equipment_for_skill(skill: str, order_text: str) -> str:
    record = _android_worker_record_for_skill(skill, order_text)
    raw_worker = str((record or {}).get("worker_id") or "").replace("android_worker_", "").strip()
    worker_label = raw_worker.title() if raw_worker else "Any"
    device = str((record or {}).get("device_label") or (record or {}).get("model") or "paired phone")
    low = str(order_text or "").lower()
    if "usb" in low or "hardwire" in low:
        return f"Android App Worker / {worker_label} / {device} / USB / hardwire ADB"
    return f"Android App Worker / {worker_label} / {device} / WiFi / LAN pairing"


def _default_equipment_for_skill(skill: str, order_text: str) -> str:
    low = str(order_text or "").lower()
    if skill in ("Android Worker Skill", "Android Worker Alpha Skill", "Android Worker Beta Skill", "Android Worker Gamma Skill"):
        return _android_equipment_for_skill(skill, order_text)
        # WiFi / LAN pairing is the canonical equipment for the new minimal
        # Engel Remote Worker app (assignments served by the LAN HTTP server,
        # phone pairs over the local network). USB / hardwire ADB stays
        # available for explicit hardwire prompts but is no longer the
        # default.
        if "usb" in low or "hardwire" in low:
            return "Android App Worker — USB / hardwire ADB"
        return "Android App Worker — WiFi / LAN pairing"
    if skill == "Engel OS Bridge Skill":
        return "Local Engel AI (main PC)"
    if skill == "Sub-Engel Worker Skill":
        if "hardwire" in low:
            return "Sub-Engel OS Worker — hardwire / future"
        return "Sub-Engel OS Worker — WiFi / LAN diagnostics"
    if skill == "Windows Sub-Engel Worker Skill":
        if "service" in low or "outbound" in low or "checkin" in low or "check-in" in low:
            return "Windows Sub-Engel Node — service / outbound"
        return "Windows Sub-Engel Node - LAN check-in"
    return "Local Engel AI (main PC)"


def _default_bridge_for_skill(skill: str, equipment: str) -> str:
    if _target_is_android(equipment):
        return "Android Worker Job Packet"
    if _target_is_windows_sub_engel(equipment):
        return "Windows Sub-Engel Job Packet"
    if _target_is_sub_engel(equipment):
        return "Sub-Engel Job Packet"
    if skill == "Architect Workflow Skill":
        return "Engel Architect Agent (engel_architect_agent)"
    if skill == "Grok Bot Teammate Skill":
        return "Grok Bot (cluster teammate)"
    if skill == "Math Skill":
        return "None (local-only)"
    if skill == "Code Factory Scout Skill":
        return "Code Factory Scout (Engel Meeting Room)"
    if skill == "Game Factory Refinement Skill":
        return "Game Factory Scout (Engel Meeting Room)"
    if skill == "Trading Dashboard Bridge Skill":
        return "Trading Dashboard Bridge (Engel Dashboard)"
    if skill == "Engel OS Bridge Skill":
        return "Engel OS Bridge (read-only)"
    if skill == "Hermes Agent Skill":
        return "Hermes-Agent (engel_agent_bridge)"
    if skill in ("Coding Skill", "File Structure Skill", "Game Development Skill"):
        return "Codex API / Codex Bridge (Engel Agent)"
    if skill == "Game Art Skill":
        return "ChatGPT Bridge (Engel no-API handoff)"
    if skill == "UI Skill":
        return "Claude API / Claude Bridge (Engel provider)"
    if skill == "Research Skill":
        return "ChatGPT Bridge (Engel no-API handoff)"
    if skill == "Memory Skill":
        return "Local LLM (offline seed / GGUF)"
    if str(skill or "").startswith("Agency "):
        return "Engel Chat Auto Route"
    if "code" in skill.lower() or "polyglot" in skill.lower():
        if "best" in skill.lower() or "auto" in skill.lower():
            return "Local Best Auto Code (smart model)"
        if "candidates" in skill.lower() or "multi" in skill.lower():
            return "Local Multi-Model Candidates"
        if "stage" in skill.lower() and "sub" in skill.lower():
            return "Stage to Sub-Engel (code gen job)"
        return "Local Multi-Model Code Gen"
    return "Engel Chat Auto Route"


def _agency_agent_matches_for_order(order_text: str) -> list[dict]:
    try:
        from engel_agency_agents_registry import find_matching_agents
        limit = int(os.environ.get("ENGEL_MEETING_ROOM_AGENCY_AGENT_LIMIT", "4"))
        return find_matching_agents(order_text, limit=max(0, min(8, limit)))
    except Exception:
        return []


def _station_payload_for_agency_agent(agent: dict) -> dict[str, str]:
    try:
        from engel_agency_agents_registry import station_payload_for_agent
        return station_payload_for_agent(agent)
    except Exception:
        return {
            "agent": str(agent.get("agent_label") or "Agency Specialist Agent"),
            "skill": str(agent.get("skill_label") or "Agency Specialist Skill"),
            "equipment": "Local Engel AI (main PC)",
            "bridge": "Engel Chat Auto Route",
        }


def _agency_context_for_station(station: dict) -> str:
    try:
        from engel_agency_agents_registry import station_context_for_labels
        return station_context_for_labels(
            str(station.get("type_label") or station.get("name") or ""),
            str(station.get("skill_label") or ""),
        )
    except Exception:
        return ""


def _ensure_order_stations(state: RoomState, order_text: str) -> list[int]:
    rows: list[int] = []
    for participant in state.participants:
        if participant.skill_label in SKILL_TYPES:
            agent = _agent_for_skill(participant.skill_label)
            participant.kind = "agent"
            participant.type_label = agent
            participant.name = f"{agent} / {participant.skill_label}"
            if participant.skill_label == "Android Worker Skill":
                participant.equipment = _default_equipment_for_skill(participant.skill_label, order_text)
                participant.bridge = _default_bridge_for_skill(participant.skill_label, participant.equipment)
    for agency_agent in _agency_agent_matches_for_order(order_text):
        payload = _station_payload_for_agency_agent(agency_agent)
        agent = payload["agent"]
        skill = payload["skill"]
        equipment = payload["equipment"]
        bridge = payload["bridge"]
        existing = next(
            (
                idx for idx, p in enumerate(state.participants)
                if p.type_label == agent and p.skill_label == skill
            ),
            None,
        )
        if existing is not None:
            state.participants[existing].name = f"{agent} / {skill}"
            state.participants[existing].kind = "agent"
            state.participants[existing].type_label = agent
            state.participants[existing].skill_label = skill
            state.participants[existing].equipment = equipment
            state.participants[existing].bridge = bridge
            state.participants[existing].status = "Waiting" if not _target_is_local(equipment) else "Assigned"
            rows.append(existing)
            continue
        state.participants.append(Participant(
            name=f"{agent} / {skill}",
            kind="agent",
            type_label=agent,
            skill_label=skill,
            equipment=equipment,
            status="Waiting" if not _target_is_local(equipment) else "Assigned",
            bridge=bridge,
        ))
        rows.append(len(state.participants) - 1)
    for skill in _infer_skills_for_order(order_text):
        agent = _agent_for_skill(skill)
        existing = next(
            (idx for idx, p in enumerate(state.participants) if p.skill_label == skill),
            None,
        )
        if existing is not None:
            equipment = _default_equipment_for_skill(skill, order_text)
            state.participants[existing].name = f"{agent} / {skill}"
            state.participants[existing].kind = "agent"
            state.participants[existing].type_label = agent
            state.participants[existing].equipment = equipment
            state.participants[existing].bridge = _default_bridge_for_skill(skill, equipment)
            state.participants[existing].status = "Waiting" if not _target_is_local(equipment) else "Assigned"
            rows.append(existing)
            continue
        equipment = _default_equipment_for_skill(skill, order_text)
        state.participants.append(Participant(
            name=f"{agent} / {skill}",
            kind="agent",
            type_label=agent,
            skill_label=skill,
            equipment=equipment,
            status="Waiting" if not _target_is_local(equipment) else "Assigned",
            bridge=_default_bridge_for_skill(skill, equipment),
        ))
        rows.append(len(state.participants) - 1)
    device_first = _device_first_skill_for_order(order_text)
    if device_first:
        primary_rows = [row for row in rows if state.participants[row].skill_label == device_first]
        rows = primary_rows + [row for row in rows if row not in primary_rows]
    return rows


def _station_route_detail(participant: Participant) -> dict:
    return {
        "device": participant.equipment,
        "agent": participant.type_label,
        "skill": participant.skill_label,
        "bridge": participant.bridge,
        "status": participant.status,
    }


def _station_route_text(participant: Participant) -> str:
    return f"{participant.equipment} -> {participant.type_label} -> {participant.skill_label}"


def _order_path(order_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(order_id or "order"))[:90]
    return ORDER_DIR / f"{safe}.json"


def _latest_prompt_route_record() -> dict | None:
    if not ORDER_DIR.exists():
        return None
    order_files = sorted(
        ORDER_DIR.glob("MAIN-*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for path in order_files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        route = payload.get("prompt_route")
        if isinstance(route, dict):
            data = dict(route)
            data["_order_id"] = payload.get("order_id") or path.stem
            return data
    return None


def _latest_prompt_route_ui_text() -> str:
    route = _latest_prompt_route_record()
    if not route:
        return "No route yet. Main UI orders will classify task, prompt style, bridge, equipment, and verifier."
    return (
        f"{route.get('prompt_type')} / {route.get('task_type')}  |  "
        f"{route.get('primary_agent')}  |  "
        f"{route.get('preferred_bridge')}  |  "
        f"{route.get('equipment_target')}  |  "
        f"verifier={bool(route.get('verifier_required'))}"
    )


def _rust_meeting_room_runtime_requested() -> bool:
    runtime = os.environ.get("ENGEL_MEETING_ROOM_RUNTIME", "").strip().lower()
    use_rust = os.environ.get("ENGEL_MEETING_ROOM_USE_RUST", "").strip().lower()
    return runtime in {"rust", "rs", "engel-ai-rs", "engel_rs"} or use_rust in {
        "1",
        "true",
        "yes",
        "on",
    }


def _rust_meeting_room_strict() -> bool:
    return os.environ.get("ENGEL_MEETING_ROOM_RUST_STRICT", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _rust_meeting_room_fallback_payload(action: str, exc: Exception) -> dict:
    return {
        "accepted": False,
        "reason": f"Rust Meeting Room {action} bridge failed ({type(exc).__name__}: {exc})",
        "runtime": "engel-ai-rs",
        "routing_source": "rust-native meeting-room order flow v1",
    }


def submit_order_from_engel_main_ui(order_text: str, source: str = "Engel AI Main UI") -> dict:
    """Record a main-UI order and auto-select stations by skill.

    This is the only supported job intake path for the Meeting Room. The
    visible Meeting Room window has no prompt/job input; it only shows the
    team, station wiring, and order/result log.
    """
    if _rust_meeting_room_runtime_requested():
        try:
            from engel_rust_meeting_room_bridge import submit_order_via_rust

            rust_result = submit_order_via_rust(order_text, source=source)
            if rust_result.get("accepted") or _rust_meeting_room_strict():
                return rust_result
        except Exception as exc:
            if _rust_meeting_room_strict():
                return _rust_meeting_room_fallback_payload("submit", exc)
    if not _looks_like_main_order(order_text):
        return {"accepted": False, "reason": "not a work order"}
    state = _load_state()
    order_id = "MAIN-" + datetime.datetime.now().strftime("%Y%m%dT%H%M%S%f")
    rows = _ensure_order_stations(state, order_text)
    job_type = _infer_job_type(order_text)
    station_labels = [
        f"{state.participants[row].type_label} / {state.participants[row].skill_label}"
        for row in rows
        if 0 <= row < len(state.participants)
    ]
    station_routes = [
        _station_route_text(state.participants[row])
        for row in rows
        if 0 <= row < len(state.participants)
    ]
    station_details = [
        _station_route_detail(state.participants[row])
        for row in rows
        if 0 <= row < len(state.participants)
    ]
    prompt_route = build_prompt_route_decision(order_text, station_details)
    prompt_route_summary = format_prompt_route_summary(prompt_route)
    prompt_route_packet = build_route_prompt_packet(str(order_text or ""), prompt_route)
    _append_state_message(
        state,
        "Engel AI Main UI",
        f"Order {order_id} received from {source}: {_clip(order_text, 700)}",
        role="user",
    )
    _append_state_message(
        state,
        "Meeting Room Router",
        "Auto-selected by device, agent, and skill: " + (", ".join(station_routes) or "none"),
        role="system",
    )
    _append_state_message(
        state,
        "Prompt Route",
        prompt_route_summary,
        role="system",
    )
    _save_state(state)
    record = {
        "order_id": order_id,
        "source": source,
        "order_text": str(order_text or ""),
        "job_type": job_type,
        "station_rows": rows,
        "station_labels": station_labels,
        "station_routes": station_routes,
        "station_details": station_details,
        "prompt_route": prompt_route.to_dict(),
        "prompt_route_summary": prompt_route_summary,
        "prompt_route_packet": prompt_route_packet,
        "created_at": _now_iso(),
        "intake": "Engel AI Main UI only",
        "connection_modes": ["WiFi / LAN pairing", "USB / hardwire ADB", "Windows Sub-Engel outbound check-in"],
    }
    _order_path(order_id).write_text(json.dumps(record, indent=2), encoding="utf-8")
    return {
        "accepted": True,
        "order_id": order_id,
        "job_type": job_type,
        "station_labels": station_labels,
        "routes": station_routes,
        "prompt_route": prompt_route.to_dict(),
        "bridge_summary": prompt_route.summary(),
        "summary": (
            "Meeting Room selected: " + (", ".join(station_labels) or "none") +
            "\nBridge route: " + prompt_route.summary()
        ),
    }


_AUTHORITATIVE_CYCLE_WORKERS = {
    "android_worker_alpha",
    "android_worker_beta",
    "android_worker_gamma",
    "DESKTOP-UE5A6GG",
}
_AUTHORITATIVE_CYCLE_SUCCESS = {
    "dry_run_complete",
    "upgraded_verified",
    "applied_then_rolled_back",
}


def _authoritative_cycle_worker_for_station(station: dict) -> str:
    text = " ".join(
        str(station.get(key) or "")
        for key in ("name", "type_label", "skill_label", "equipment", "bridge")
    ).casefold()
    if "alpha" in text and ("android" in text or "phone" in text):
        return "android_worker_alpha"
    if "beta" in text and ("android" in text or "phone" in text):
        return "android_worker_beta"
    if "gamma" in text and ("android" in text or "phone" in text):
        return "android_worker_gamma"
    if "windows sub-engel" in text or "desktop-ue5a6gg" in text:
        return "DESKTOP-UE5A6GG"
    return ""


def _authoritative_cycle_results(
    worker_results: list[dict],
    final_status: str,
) -> tuple[dict[str, dict], str]:
    by_worker: dict[str, dict] = {}
    for item in worker_results:
        if not isinstance(item, dict):
            return {}, "authoritative worker result is not an object"
        worker_id = str(item.get("worker_id") or "").strip()
        if worker_id not in _AUTHORITATIVE_CYCLE_WORKERS:
            return {}, f"authoritative worker result has an unknown worker: {worker_id}"
        if worker_id in by_worker:
            return {}, f"authoritative worker result is duplicated: {worker_id}"
        by_worker[worker_id] = item
    if final_status in _AUTHORITATIVE_CYCLE_SUCCESS:
        missing = sorted(_AUTHORITATIVE_CYCLE_WORKERS - set(by_worker))
        unreturned = sorted(
            worker_id
            for worker_id, item in by_worker.items()
            if item.get("returned") is not True
        )
        if missing or unreturned:
            return {}, (
                "successful authoritative completion lacks exact worker returns; "
                f"missing={missing} unreturned={unreturned}"
            )
    return by_worker, ""


def complete_order_from_engel_main_ui(
    order_id: str,
    main_reply: str,
    source: str = "Engel AI Main UI",
    *,
    authoritative_worker_results: list[dict] | None = None,
    authoritative_final_status: str = "",
) -> dict:
    """Return Engel's main answer to the selected meeting-room stations.

    Local/provider-style agents receive the already-routed main UI reply so
    the room does not duplicate provider calls. Device workers get bounded
    job/staging packets through the existing Android/Sub-Engel gates.
    """
    authoritative_by_worker: dict[str, dict] | None = None
    if authoritative_worker_results is not None:
        if source != "Engel conical self-upgrade cycle":
            return {
                "accepted": False,
                "reason": "authoritative completion is restricted to the conical cycle",
            }
        final_status = str(authoritative_final_status or "").strip()
        if not final_status:
            return {
                "accepted": False,
                "reason": "authoritative completion requires a terminal cycle status",
            }
        authoritative_by_worker, validation_error = _authoritative_cycle_results(
            authoritative_worker_results,
            final_status,
        )
        if validation_error:
            return {"accepted": False, "reason": validation_error}
    if authoritative_by_worker is None and _rust_meeting_room_runtime_requested():
        try:
            from engel_rust_meeting_room_bridge import complete_order_via_rust

            rust_result = complete_order_via_rust(order_id, main_reply, source=source)
            if rust_result.get("accepted") or _rust_meeting_room_strict():
                return rust_result
        except Exception as exc:
            if _rust_meeting_room_strict():
                return _rust_meeting_room_fallback_payload("complete", exc)
    path = _order_path(order_id)
    if not path.exists():
        return {"accepted": False, "reason": "order record not found"}
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"accepted": False, "reason": "order record unreadable"}
    state = _load_state()
    rows = [int(row) for row in record.get("station_rows", []) if isinstance(row, int) or str(row).isdigit()]
    order_text = str(record.get("order_text") or "")
    job_type = str(record.get("job_type") or _infer_job_type(order_text))
    summaries: list[str] = []
    returned_previews: list[str] = []
    station_outcomes: list[dict] = []
    for row in rows:
        if row < 0 or row >= len(state.participants):
            continue
        station = asdict(state.participants[row])
        station["_row"] = row
        equipment = str(station.get("equipment") or "")
        bridge = str(station.get("bridge") or "")
        worker_id = _authoritative_cycle_worker_for_station(station)
        if authoritative_by_worker is not None and worker_id:
            result = authoritative_by_worker.get(worker_id)
            if result is None:
                status = "Needs Review"
                reply = (
                    f"Authoritative cycle {authoritative_final_status} did not receive "
                    f"a result from {worker_id}."
                )
            elif result.get("returned") is True:
                status = "Returned"
                reply = _clip(
                    result.get("contribution")
                    or result.get("worker_output")
                    or result.get("return_path")
                    or f"{worker_id} returned verified candidate-only work.",
                    1200,
                )
            else:
                status = "Needs Review"
                reply = _clip(
                    result.get("error")
                    or f"{worker_id} did not return valid bounded work.",
                    1200,
                )
        elif authoritative_by_worker is not None:
            is_verifier = "verifier" in " ".join(
                str(station.get(key) or "")
                for key in ("name", "type_label", "skill_label")
            ).casefold()
            status = (
                "Returned"
                if not is_verifier
                or authoritative_final_status in _AUTHORITATIVE_CYCLE_SUCCESS
                else "Needs Review"
            )
            reply = "Authoritative cycle result projected without redispatch: " + _clip(
                main_reply,
                650,
            )
        elif (
            _target_is_android(equipment)
            or "Android Worker Job Packet" in bridge
            or _target_is_sub_engel(equipment)
            or "Sub-Engel Diagnostics Preview" in bridge
            or _target_is_windows_sub_engel(equipment)
            or "Windows Sub-Engel Check-in Preview" in bridge
            or "Code Factory Scout" in bridge
            or "Game Factory Scout" in bridge
            or "Trading Dashboard Bridge" in bridge
            or "Engel OS Bridge" in bridge
            or "Hermes-Agent" in bridge
        ):
            status, reply = dispatch_station_work(station, job_type, order_text)
        else:
            status = "Assigned"
            reply = "Main UI routed answer returned to station: " + _clip(main_reply, 650)
        state.participants[row].status = status
        _append_state_message(state, str(station.get("name") or "Agent"), f"[{status}] {reply}", role="agent")
        summaries.append(f"{station.get('type_label', 'Agent')}: {status}")
        station_outcomes.append({
            "agent": station.get("type_label", "Agent"),
            "skill": station.get("skill_label", "Unassigned Skill"),
            "equipment": station.get("equipment", "Unassigned device"),
            "bridge": station.get("bridge", "Engel Chat Auto Route"),
            "status": status,
            "reply": reply,
        })
        if status in {"Returned", "Needs Review"} and reply:
            returned_previews.append(f"{station.get('type_label', 'Agent')}: {_clip(reply, 260)}")
    collaboration_dialogue = _build_collaboration_dialogue(order_text, job_type, station_outcomes)
    for turn in collaboration_dialogue:
        _append_state_message(
            state,
            str(turn.get("name") or "Agent"),
            str(turn.get("text") or ""),
            role=str(turn.get("role") or "agent"),
        )
    _append_state_message(
        state,
        "Meeting Room Router",
        f"Order {order_id} result returned from {source} to {len(summaries)} station(s).",
        role="system",
    )
    record["completed_at"] = _now_iso()
    record["main_reply_preview"] = _clip(main_reply, 900)
    record["station_results"] = summaries
    record["station_outcomes"] = station_outcomes
    record["returned_previews"] = returned_previews
    record["collaboration_dialogue"] = collaboration_dialogue
    if authoritative_by_worker is not None:
        record["authoritative_cycle_completion"] = {
            "source": source,
            "final_status": authoritative_final_status,
            "worker_ids": sorted(authoritative_by_worker),
            "returned_worker_count": sum(
                1
                for item in authoritative_by_worker.values()
                if item.get("returned") is True
            ),
            "dispatch_performed": False,
        }
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    _save_state(state)
    summary = "Meeting Room updated: " + (", ".join(summaries) or "no stations")
    if returned_previews:
        summary += "\nReturned results:\n- " + "\n- ".join(returned_previews[:4])
    if collaboration_dialogue:
        summary += "\nCollaboration dialogue:\n- " + "\n- ".join(
            f"{turn.get('name')}: {_clip(turn.get('text', ''), 220)}"
            for turn in collaboration_dialogue[:6]
        )
    return {
        "accepted": True,
        "order_id": order_id,
        "summary": summary,
        "station_results": summaries,
        "station_outcomes": station_outcomes,
        "returned_previews": returned_previews,
        "collaboration_dialogue": collaboration_dialogue,
        "order_path": str(path),
        "authoritative_cycle_completion": authoritative_by_worker is not None,
        "dispatch_performed": authoritative_by_worker is None,
    }


def _work_title(prompt: str, fallback: str = "Meeting room work") -> str:
    for line in str(prompt or "").splitlines():
        clean = line.strip().strip("#").strip()
        if clean:
            return clean[:72]
    return fallback


def _build_station_prompt(station: dict, job_type: str, prompt: str) -> str:
    agency_context = _agency_context_for_station(station)
    lines = [
        "Agent Meeting Room work packet",
        "",
        f"Device: {station.get('equipment', 'Unassigned')}",
        f"Agent: {station.get('type_label', station.get('name', 'Agent'))}",
        f"Skill: {station.get('skill_label', 'Unassigned Skill')}",
        f"Bridge preference: {station.get('bridge', 'Engel Chat Auto Route')}",
        f"Job type: {job_type}",
    ]
    if agency_context:
        lines.extend(["", agency_context])
    lines.extend([
        "",
        "Work:",
        str(prompt or "").strip(),
    ])
    return "\n".join(lines).strip()


def _android_return_wait_seconds() -> float:
    raw = os.environ.get("ENGEL_MEETING_ROOM_ANDROID_RETURN_WAIT_SECONDS", "45")
    try:
        return max(0.0, min(120.0, float(raw)))
    except ValueError:
        return 45.0


def _nonblocking_remote_dispatch_enabled() -> bool:
    raw = os.environ.get("ENGEL_MEETING_ROOM_NONBLOCKING_REMOTE_DISPATCH", "").strip().lower()
    return raw in {"1", "true", "yes", "on", "enabled"}


def _load_json_file(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def _sub_engel_return_wait_seconds() -> float:
    raw = os.environ.get("ENGEL_MEETING_ROOM_SUB_RETURN_WAIT_SECONDS", "75")
    try:
        return max(0.0, min(120.0, float(raw)))
    except ValueError:
        return 75.0


def _sub_engel_passive_return_wait_seconds() -> float:
    raw = os.environ.get("ENGEL_MEETING_ROOM_SUB_PASSIVE_WAIT_SECONDS", "75")
    try:
        return max(0.0, min(120.0, float(raw)))
    except ValueError:
        return 75.0


def _sub_engel_auto_return_attempts() -> int:
    raw = os.environ.get("ENGEL_MEETING_ROOM_SUB_AUTO_RETURN_ATTEMPTS", "3")
    try:
        return max(1, min(8, int(raw)))
    except ValueError:
        return 3


def _refresh_sub_engel_active_request(work_order: dict) -> bool:
    active_path = Path(str(work_order.get("active_request_path") or ""))
    order_path = Path(str(work_order.get("path") or ""))
    if not active_path:
        return False
    try:
        active_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": "engel_sub_engel_active_work_request_v1",
            "created_at_utc": datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "created_by": "Engel AI Main / Agent Meeting Room auto-return retry",
            "order_id": str(work_order.get("id") or order_path.stem),
            "work_order_name": order_path.name,
            "work_order_path": str(order_path),
            "expected_return_folder": str(work_order.get("expected_return_folder") or ""),
            "target": str(work_order.get("target") or ""),
            "selected_node": work_order.get("selected_node") if isinstance(work_order.get("selected_node"), dict) else {},
            "proof_required": True,
            "auto_return_retry": True,
            "auto_apply": False,
        }
        active_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return True
    except Exception:
        return False


def _sub_engel_selected_identity_candidates(selected_node: dict) -> set[str]:
    if not isinstance(selected_node, dict):
        return set()
    values = {
        selected_node.get("node_id", ""),
        selected_node.get("stable_id", ""),
        selected_node.get("stable_identity", ""),
        selected_node.get("hostname", ""),
        selected_node.get("computer_name", ""),
    }
    return {str(value).strip().lower() for value in values if str(value or "").strip()}


def _sub_engel_return_identity_candidates(path: Path, payload: dict) -> set[str]:
    values = {
        payload.get("hostname", "") if isinstance(payload, dict) else "",
        payload.get("node_id", "") if isinstance(payload, dict) else "",
        payload.get("computer_name", "") if isinstance(payload, dict) else "",
        path.name.split("__", 1)[0] if "__" in path.name else "",
    }
    return {str(value).strip().lower() for value in values if str(value or "").strip()}


def _sub_engel_return_matches_selected(path: Path, payload: dict, selected_node: dict | None) -> bool:
    selected_ids = _sub_engel_selected_identity_candidates(selected_node or {})
    if not selected_ids:
        return True
    return bool(selected_ids.intersection(_sub_engel_return_identity_candidates(path, payload)))


def _wait_for_sub_engel_sent_return(
    order_id: str,
    sent_folder: str,
    timeout_seconds: float,
    selected_node: dict | None = None,
) -> tuple[Path, dict] | None:
    target = str(order_id or "")
    folder = Path(str(sent_folder or ""))
    if not target or not folder.exists():
        return None
    deadline = time.time() + max(0.0, timeout_seconds)
    while True:
        matches: list[tuple[Path, dict]] = []
        try:
            candidates = list(folder.glob(f"*{target}*.json"))
        except OSError:
            candidates = []
        for path in candidates:
            payload = _load_json_file(path)
            if (
                isinstance(payload, dict)
                and str(payload.get("order_id") or "") == target
                and _sub_engel_return_matches_selected(path, payload, selected_node)
            ):
                matches.append((path, payload))
        if matches:
            return sorted(matches, key=lambda item: item[0].stat().st_mtime if item[0].exists() else 0)[-1]
        if time.time() >= deadline:
            return None
        time.sleep(1.0)


def _decode_remote_action_stdout(response: dict) -> dict:
    result = response.get("result") if isinstance(response, dict) else {}
    result = result if isinstance(result, dict) else {}
    stdout = result.get("stdout")
    if not isinstance(stdout, str) or not stdout.strip():
        return {}
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _summarize_sub_engel_return(path: Path, payload: dict, remote_payload: dict) -> str:
    return (
        f"Windows Sub-Engel return received from {payload.get('hostname') or remote_payload.get('hostname')}; "
        f"order={payload.get('order_id') or remote_payload.get('order_id')}; "
        f"status={payload.get('operator_status') or remote_payload.get('operator_status')}; "
        f"node_root={payload.get('node_root') or remote_payload.get('node_root')}; "
        f"state_dir={payload.get('state_dir') or remote_payload.get('state_dir')}; "
        f"file={path.name}. "
        f"Preview: {_clip(payload.get('order_text') or remote_payload.get('order_text') or '', 320)}"
    )


def _find_android_worker_return(packet_id: str, worker_id: str) -> tuple[Path, dict] | None:
    target_packet = str(packet_id or "")
    target_worker = str(worker_id or "")
    if not target_packet or not RETURNED_ASSIGNMENTS_DIR.exists():
        return None
    matches: list[tuple[Path, dict]] = []
    for path in RETURNED_ASSIGNMENTS_DIR.glob("*.json"):
        payload = _load_json_file(path)
        if not isinstance(payload, dict):
            continue
        if str(payload.get("packet_id") or "") != target_packet:
            continue
        if target_worker and str(payload.get("worker_id") or "") != target_worker:
            continue
        matches.append((path, payload))
    if not matches:
        return None
    return sorted(matches, key=lambda item: item[0].name)[-1]


def _wait_for_android_worker_return(packet_id: str, worker_id: str, timeout_seconds: float) -> tuple[Path, dict] | None:
    deadline = time.time() + max(0.0, timeout_seconds)
    while True:
        found = _find_android_worker_return(packet_id, worker_id)
        if found is not None:
            return found
        if time.time() >= deadline:
            return None
        time.sleep(1.0)


def _readable_android_output(payload: dict) -> str:
    """(2026-07-07) Extract the worker's actual output as PROSE, instead of dumping
    the raw candidate-draft packet. Phones are bounded workers: summarize_text
    returns a markdown 'Candidate Draft' (echoing the task), draft_candidate_json /
    classify_file return a JSON object. Present each in one readable clause."""
    rtype = str(payload.get("result_type") or "work")
    draft = str(payload.get("draft_text") or "").strip()
    d = draft.lstrip()
    if d.startswith("{"):
        try:
            obj = json.loads(d)
        except Exception:
            obj = {}
        if isinstance(obj, dict) and obj.get("classification"):
            wc = obj.get("word_count")
            return f'classified the input as "{obj.get("classification")}"' + (f" ({wc} words)" if wc else "")
        if isinstance(obj, dict) and (obj.get("title") or obj.get("candidate_type")):
            title = str(obj.get("title") or obj.get("candidate_type"))
            return f'drafted a JSON candidate: "{title[:100]}"'
        return f"returned a {rtype} result"
    task = ""
    for line in draft.splitlines():
        ls = line.strip()
        if ls.lower().startswith("task:"):
            task = ls[5:].strip()
            break
    if task:
        return f'drafted a {rtype} candidate for "{task[:100]}"'
    body = _clip(" ".join(draft.split()), 180)
    return f"returned: {body}" if body else f"returned a {rtype} result"


def _summarize_android_return(path: Path, payload: dict) -> str:
    caps = payload.get("device_capabilities") if isinstance(payload, dict) else {}
    caps = caps if isinstance(caps, dict) else {}
    andro = caps.get("android") if isinstance(caps.get("android"), dict) else {}
    model = str((andro.get("model") if andro else "") or caps.get("configured_phone_model") or "").strip()
    who = str(payload.get("worker_id") or "worker").replace("android_worker_", "").capitalize()
    if model:
        who += f" ({model})"
    review = " — flagged for review" if payload.get("requires_review") else ""
    return f"{who} {_readable_android_output(payload)}{review}."


def _android_worker_id_for(station: dict, prompt: str = "") -> str:
    station_text = " ".join(
        str(station.get(key) or "")
        for key in ("name", "type_label", "skill_label", "equipment", "bridge")
    )
    station_low = station_text.lower()
    if "beta" in station_low or "moto g fast" in station_low or "zy22bks7mp" in station_low:
        return "android_worker_beta"
    if "gamma" in station_low:
        return "android_worker_gamma"
    if "alpha" in station_low or "moto g power" in station_low or "zl8322r4vg" in station_low:
        return "android_worker_alpha"
    prompt_low = str(prompt or "").lower()
    if "beta" in prompt_low or "moto g fast" in prompt_low or "zy22bks7mp" in prompt_low:
        return "android_worker_beta"
    if "gamma" in prompt_low:
        return "android_worker_gamma"
    if "alpha" in prompt_low or "moto g power" in prompt_low or "zl8322r4vg" in prompt_low:
        return "android_worker_alpha"
    return "android_worker_alpha"


def _android_lan_presence_note(worker_id: str) -> str:
    try:
        _prefer_workspace_android_modules()
        from engel_remote_worker_link_manager import link_status
        state = link_status()
    except Exception as exc:
        return f"LAN status check skipped: {type(exc).__name__}: {exc}"
    workers = state.get("workers") if isinstance(state, dict) else None
    if isinstance(workers, dict):
        record = workers.get(worker_id)
        if isinstance(record, dict) and record.get("last_seen_utc"):
            identity = record.get("identity") if isinstance(record.get("identity"), dict) else {}
            remote = identity.get("remote_address") or state.get("host") or "LAN"
            return (
                f"LAN: {worker_id} seen from {remote} at {record.get('last_seen_utc')}; "
                "USB wake not required for the WiFi/LAN polling path."
            )
    if state.get("last_seen_utc"):
        return (
            f"LAN: worker link last seen at {state.get('last_seen_utc')}; "
            "USB wake not required for the WiFi/LAN polling path."
        )
    if state.get("receiver_running"):
        return "LAN receiver is running; assignment is staged for the next worker poll."
    return "LAN receiver status is not active; assignment is staged for the next worker check-in."


def dispatch_station_work(station: dict, job_type: str, prompt: str) -> tuple[str, str]:
    """Dispatch one station through its selected device/bridge.

    This function intentionally routes through existing Engel surfaces. It
    never starts raw shell/SSH/browser automation and never reads secrets.
    """
    equipment = str(station.get("equipment") or "Unassigned")
    bridge = str(station.get("bridge") or "Engel Chat Auto Route")
    work_prompt = _build_station_prompt(station, job_type, prompt)
    title = _work_title(prompt)

    if _target_is_android(equipment) or "Android Worker Job Packet" in bridge:
        worker_id = _android_worker_id_for(station, prompt)
        # The Engel Remote Worker Flutter app does not poll /sdcard. It pulls
        # assignments over HTTP from engel_remote_worker_lan_pairing.py which
        # reads remote_workers/communication_queen_assignments/approved/.
        # Stage the assignment there via the validated producer API so the
        # next /worker/next-assignment call from the phone picks it up.
        try:
            _prefer_workspace_android_modules()
            from engel_communication_queen_assignment_producer import (
                create_assignment, WORKER_ALLOWED_TASK_TYPES,
            )
            from engel_device_capability_registry import (
                infer_job_type_from_text,
                select_worker_for_job,
            )
            if str(station.get("skill_label") or "") == "Android Worker Skill":
                selected = select_worker_for_job(job_type, prompt)
                if selected and selected.get("worker_id"):
                    worker_id = str(selected["worker_id"])
            allowed_for_worker = WORKER_ALLOWED_TASK_TYPES.get(worker_id, set())
            # Coerce job_type into something this specific worker is allowed
            # to run. Default to summarize_text which alpha supports; beta
            # supports draft_candidate_json and format_report_draft.
            preferred = {
                "android_worker_alpha": "summarize_text",
                "android_worker_beta":  "draft_candidate_json",
                "android_worker_gamma": "classify_file",
            }.get(worker_id, "summarize_text")
            inferred = infer_job_type_from_text(prompt, preferred)
            task_type = job_type if job_type in allowed_for_worker else inferred
            if task_type not in allowed_for_worker:
                task_type = preferred
            wake_note = ""
            if _target_is_hardwire(equipment):
                try:
                    from engel_phone_wake_manager import wake_worker_if_stale
                    wake_result = wake_worker_if_stale(worker_id, apply=True)
                    if wake_result.attempted:
                        wake_note = f"Wake: {wake_result.detail}"
                    elif wake_result.stale and not wake_result.success:
                        wake_note = f"Wake: {wake_result.detail}"
                except Exception as exc:
                    wake_note = f"Wake check skipped: {type(exc).__name__}: {exc}"
            elif _target_is_wifi(equipment):
                wake_note = _android_lan_presence_note(worker_id)
            packet, packet_path, receipt_path = create_assignment(
                worker=worker_id,
                task_type=task_type,
                title=title or "Meeting Room dispatched assignment",
                instructions=work_prompt,
            )
            packet_id = str(packet.get("packet_id") or "")
            staged_reply = (
                (wake_note + "\n" if wake_note else "") +
                f"Engel staged assignment for {worker_id} at "
                f"{packet_path.name} (task={task_type}). The phone's Engel "
                f"Remote Worker app will pick it up via /worker/next-assignment "
                f"on the next Check Now. Packet id: {packet_id}"
            )
            if _nonblocking_remote_dispatch_enabled():
                return "Assigned", staged_reply
            returned = _wait_for_android_worker_return(packet_id, worker_id, _android_return_wait_seconds())
            if returned is not None:
                result_path, result_payload = returned
                summary = _summarize_android_return(result_path, result_payload)
                return "Returned", "\n".join(part for part in [wake_note, summary] if part)
            return "Assigned", staged_reply
        except Exception as exc:
            return "Needs Review", f"Android assignment staging failed: {type(exc).__name__}: {exc}"

    if station.get("skill_label") == "Trading Dashboard Bridge Skill" or "Trading Dashboard Bridge" in bridge:
        try:
            from engel_trading_dashboard_bridge import (
                stage_dashboard_merge_packet,
                summarize_dashboard_bridge_result,
            )
            result = stage_dashboard_merge_packet(work_prompt, source="Agent Meeting Room")
            return "Returned", summarize_dashboard_bridge_result(result)
        except Exception as exc:
            return "Needs Review", f"Trading Dashboard bridge dispatch failed: {type(exc).__name__}: {exc}"

    if station.get("skill_label") == "Engel OS Bridge Skill" or "Engel OS Bridge" in bridge:
        try:
            from engel_os_bridge import (
                stage_engel_os_hookup_packet,
                summarize_engel_os_bridge_result,
            )
            result = stage_engel_os_hookup_packet(work_prompt, source="Agent Meeting Room")
            return "Returned", summarize_engel_os_bridge_result(result)
        except Exception as exc:
            return "Needs Review", f"Engel OS bridge dispatch failed: {type(exc).__name__}: {exc}"

    if station.get("skill_label") == "Hermes Agent Skill" or "Hermes-Agent" in bridge:
        # Merge of the bundled Hermes-Agent (engel_agent_main) into the Meeting
        # Room. This pass is READ-ONLY: it surfaces the Hermes-Agent toolset /
        # skill inventory via engel_agent_bridge so the room knows what the
        # agent can bring to the task. No model/provider call and no tool
        # execution occur here — full autonomous Hermes invocation stays gated
        # behind explicit Engel approval, per the safety constitution.
        try:
            from engel_agent_bridge import bridge_available, bridge_missing_reason
            if not bridge_available():
                return "Needs Review", "Hermes-Agent bridge unavailable: " + bridge_missing_reason()
            from engel_engel_agent_runner import render_engel_agent_status
            inventory = render_engel_agent_status()
            return "Returned", (
                "Hermes-Agent (engel_agent_bridge) reviewed this order read-only.\n"
                "Task: " + _clip(prompt, 300) + "\n\n" + _clip(inventory, 1400) +
                "\n\nFull autonomous Hermes invocation (cli -q) stays gated behind "
                "explicit approval; this pass is inventory/preview only."
            )
        except Exception as exc:
            return "Needs Review", f"Hermes-Agent dispatch failed: {type(exc).__name__}: {exc}"

    if station.get("skill_label") == "Code Factory Scout Skill" or "Code Factory Scout" in bridge:
        try:
            from engel_code_factory_bridge import (
                is_code_factory_hour_loop_request,
                run_code_factory_scout_packet,
                start_code_factory_hour_loop_packet,
                summarize_bridge_result,
                summarize_hour_loop_result,
            )
            if is_code_factory_hour_loop_request(work_prompt):
                result = start_code_factory_hour_loop_packet(work_prompt, source="Agent Meeting Room")
                return "Returned", summarize_hour_loop_result(result)
            result = run_code_factory_scout_packet(work_prompt, source="Agent Meeting Room")
            return "Returned", summarize_bridge_result(result)
        except Exception as exc:
            return "Needs Review", f"Code Factory Scout dispatch failed: {type(exc).__name__}: {exc}"

    if station.get("skill_label") == "Game Factory Refinement Skill" or "Game Factory Scout" in bridge:
        try:
            from engel_game_factory_bridge import (
                run_game_factory_refinement_packet,
                summarize_game_factory_result,
            )
            result = run_game_factory_refinement_packet(work_prompt, source="Agent Meeting Room")
            return "Returned", summarize_game_factory_result(result)
        except Exception as exc:
            return "Needs Review", f"Game Factory dispatch failed: {type(exc).__name__}: {exc}"

    if "Grok Bot" in bridge or station.get("type_label") == "Grok Bot":
        # Named cluster teammate. Plan only. Meeting Room must not run the
        # explicit handoff route or any Android/provider action from here.
        try:
            from engel_grok_bot import render_grok_bot_message, render_grok_bot_status

            plan = render_grok_bot_message("message grok bot Grok | " + str(work_prompt or title or ""))
            status_text = render_grok_bot_status()
            reply = (
                "Grok Bot routing — order recorded for the cluster teammate.\n\n"
                f"Order title: {title}\n\n"
                f"{plan.strip()}\n\n"
                "--- Shared computer ---\n"
                f"{status_text.strip()[:800]}\n\n"
                "To stage this into the room as a formal handoff, use chat:\n"
                "  handoff grok bot Grok | <task>\n"
                "Send Job / Android packet / Architect actions stay explicit."
            )
            return "Assigned", reply.strip()
        except Exception as exc:
            return "Needs Review", f"Grok Bot dispatch failed: {type(exc).__name__}: {exc}"

    if "Engel Architect Agent" in bridge or station.get("type_label") == "Architect Agent":
        # Architect Agent station — read-only routing through engel_architect_agent.
        # We never mutate architect state from the Meeting Room (no auto
        # `start new`). The reply surfaces the architect's current overview +
        # status so the user can decide the next action via the existing
        # `engel.architect.*` action routes.
        try:
            from engel_architect_agent import (
                render_architect_overview,
                render_architect_status,
                render_architect_section_detail,
            )
            status_text = render_architect_status() or ""
            section_text = render_architect_section_detail() or ""
            overview = render_architect_overview() or ""
            reply = (
                f"Architect routing — order recorded for the Architect Agent.\n\n"
                f"Order title: {title}\n\n"
                f"{status_text.strip()}\n\n"
                f"--- Current section ---\n{section_text.strip()}\n\n"
                f"To advance the architect, use the existing actions in chat:\n"
                f"  architect start new   ·   architect run section   ·\n"
                f"  architect complete section   ·   architect approve gate\n\n"
                f"(Overview, for reference)\n{overview.strip()[:600]}"
            )
            return "Assigned", reply.strip()
        except Exception as exc:
            return "Needs Review", f"Architect dispatch failed: {type(exc).__name__}: {exc}"

    if (
        _target_is_sub_engel(equipment)
        or "Sub-Engel Diagnostics Preview" in bridge
        or _target_is_windows_sub_engel(equipment)
        or "Windows Sub-Engel Check-in Preview" in bridge
    ):
        if _target_is_windows_sub_engel(equipment) or "Windows Sub-Engel" in bridge:
            try:
                from tools.engel_sub_engel_training_safe_task_executor import meeting_room_training_gate

                training_gate = meeting_room_training_gate(work_prompt, job_type)
                if training_gate.get("handled"):
                    return str(training_gate.get("status") or "Needs Review"), str(training_gate.get("reply") or "")
            except Exception as exc:
                return (
                    "Needs Review",
                    "Sub-Engel training state could not be verified, so Engel did not assign work: "
                    f"{type(exc).__name__}: {exc}",
                )
        try:
            from engel_sub_node_meeting_bridge import (
                stage_meeting_packet_for_node,
                write_server_transport_work_order_for_node,
            )
            packet = stage_meeting_packet_for_node(station, job_type, work_prompt)
            work_order = write_server_transport_work_order_for_node(
                station,
                job_type,
                work_prompt,
                meeting_packet_path=str(packet.get("path") or ""),
            )
            base_reply = (
                f"{packet.get('node_label', 'Sub-Engel')} meeting packet staged for additional computer AI usage. "
                f"CT246 server transport work order written: {work_order.get('path')}. "
            )
            # Also produce standard job packet via assignment system when worker type supported.
            # This enables more computers (Engel OS / Windows Sub-Engel nodes) to receive bounded jobs.
            try:
                from engel_remote_worker_job_assignment import write_assignment
                worker_id = "sub_engel_os_worker" if _target_is_sub_engel(equipment) else "windows_sub_engel"
                # Use a small text marker file from the prompt for the assignment (safe bounded input)
                marker = RUNTIME_ROOM_DIR / "sub_engel_inputs" / f"{work_order.get('id','job')}.txt"
                marker.parent.mkdir(parents=True, exist_ok=True)
                marker.write_text(work_prompt[:2000], encoding="utf-8")
                asg = write_assignment(worker_id, job_type or "summarize_text", str(marker), title or "meeting order", work_prompt[:500])
                base_reply += f" Assignment packet: {asg.get('job_packet_path')}. "
            except Exception:
                pass
            if _target_is_windows_sub_engel(equipment) or "Windows Sub-Engel Check-in Preview" in bridge:
                try:
                    from tools.engel_ct246_sub_engel_direct_work import dispatch as dispatch_sub_direct

                    receipt = dispatch_sub_direct(Path(str(work_order.get("path") or "")))
                    if receipt.get("ok") is True:
                        return (
                            "Returned",
                            base_reply
                            + f"Sub-Engel completed the CT246 direct work order with "
                            f"{receipt.get('worker_engine') or 'its local worker'}. "
                            f"Receipt: {receipt.get('returned_file')}.",
                        )
                    return (
                        "Needs Review",
                        base_reply
                        + "CT246 direct Sub-Engel dispatch returned an honest failure. "
                        f"Receipt: {receipt.get('server_receipt_file')}.",
                    )
                except Exception as remote_exc:
                    return (
                        "Needs Review",
                        base_reply
                        + f"CT246 direct Sub-Engel dispatch was not available "
                        f"({type(remote_exc).__name__}: {remote_exc}); no fallback transport was used.",
                    )
            return (
                "Waiting",
                base_reply
                + f"Waiting for a real returned result in {work_order.get('expected_return_folder')}. "
                f"Remote runtime work stays blocked until the approved worker packet returns: {packet.get('path')}"
            )
        except Exception as exc:
            stage_dir = RUNTIME_ROOM_DIR / "sub_engel_prompts"
            stage_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%SZ")
            safe_name = str(station.get("name") or "sub_engel").lower().replace(" ", "_").replace("/", "_")
            path = stage_dir / f"{stamp}_{safe_name}.txt"
            path.write_text(work_prompt + "\n", encoding="utf-8")
            return (
                "Waiting",
                "Sub-Engel job packet staged for additional computer AI usage. "
                f"Node will process locally per its gate. Fallback staging: {path} "
                f"(after {type(exc).__name__})"
            )

    if "Local LLM" in bridge:
        try:
            from engel_offline_seed_llm import (
                offline_seed_llm_gate_enabled,
                run_offline_seed_llm_for_companion_chat,
            )
            if not offline_seed_llm_gate_enabled():
                return "Needs Review", "Local LLM gate is off. Set ENGEL_OFFLINE_SEED_LLM_ENABLED=1 to enable it."
            result = run_offline_seed_llm_for_companion_chat(work_prompt)
            return "Assigned", (getattr(result, "response", "") or "(empty local model response)").strip()
        except Exception as exc:
            return "Needs Review", f"Local LLM dispatch failed: {type(exc).__name__}: {exc}"

    if "Local Multi-Model Code Gen" in bridge:
        try:
            from engel_local_multi_model_code import render_code_generate, render_code_translate
            if "translate" in work_prompt.lower() or "port to" in work_prompt.lower() or "convert to" in work_prompt.lower():
                # very rough parse for translate
                payload = "auto|python|rust|" + work_prompt  # will be improved by user
                code = render_code_translate(payload)
            else:
                default_model = "qwen2.5-7b"
                lang = "python"
                if "rust" in work_prompt.lower(): lang = "rust"
                elif "go" in work_prompt.lower(): lang = "go"
                elif "javascript" in work_prompt.lower() or "js" in work_prompt.lower(): lang = "javascript_typescript"
                payload = f"{default_model}|{lang}|{work_prompt}"
                code = render_code_generate(payload)
            return "Assigned", f"Multi-model code:\n{code[:1500]}"
        except Exception as exc:
            return "Needs Review", f"Multi-model code gen failed: {type(exc).__name__}: {exc}"

    if "None (local-only)" in bridge:
        return "Assigned", "Local-only station recorded the prompt. Pick an API/local bridge to call a model."

    try:
        from engel_communication_router import route_companion_text_or_command
        routed_text = work_prompt
        if bridge != "Engel Chat Auto Route":
            routed_text = "engel agent task " + work_prompt
        result = route_companion_text_or_command(routed_text, context="AGENT_MEETING_ROOM")
        reply = getattr(result, "response", "") or "(no response)"
        return "Assigned", reply.strip()
    except Exception as exc:
        return "Needs Review", f"Engel route dispatch failed: {type(exc).__name__}: {exc}"


class MeetingRoomDispatchThread(QThread):
    progress = pyqtSignal(int, str, str, str)
    all_done = pyqtSignal()

    def __init__(self, stations: list[dict], job_type: str, prompt: str):
        super().__init__()
        self._stations = stations
        self._job_type = job_type
        self._prompt = prompt

    def run(self):
        for station in self._stations:
            row = int(station.get("_row", -1))
            name = str(station.get("name") or station.get("type_label") or "Agent")
            status, reply = dispatch_station_work(station, self._job_type, self._prompt)
            self.progress.emit(row, name, status, reply)
        self.all_done.emit()


# ─── Left panel — Agent / Skill / Equipment ───────────────────────────────────

class LeftPanel(QFrame):
    def __init__(self, window: "AgentMeetingRoomWindow"):
        super().__init__()
        self.window_ref = window
        self.setObjectName("card")
        self.setMinimumWidth(280)
        self.setMaximumWidth(360)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        layout.addWidget(_label("Agent Station", bold=True, size=11, color=GREEN))
        layout.addWidget(_divider())

        layout.addWidget(_label("1  Device", color=BLUE, size=9, bold=True))
        self.eq_target = QComboBox()
        self.eq_target.addItems(EQUIPMENT_TARGETS)
        layout.addWidget(self.eq_target)

        layout.addWidget(_label("2  Agent", color=GREEN, size=9, bold=True))
        self.agent_type = QComboBox()
        self.agent_type.addItems(AGENT_TYPES)
        layout.addWidget(self.agent_type)

        layout.addWidget(_label("3  Skill", color=PURPLE, size=9, bold=True))
        self.skill_type = QComboBox()
        self.skill_type.addItems(SKILL_TYPES)
        layout.addWidget(self.skill_type)

        layout.addWidget(_label("Bridge", color=DIM, size=8))
        self.bridge_target = QComboBox()
        self.bridge_target.addItems(BRIDGE_OPTIONS)
        layout.addWidget(self.bridge_target)

        save_btn = QPushButton("Save Agent Station")
        save_btn.setObjectName("primary")
        save_btn.clicked.connect(self._save_station)
        layout.addWidget(save_btn)

        new_btn = QPushButton("New Station")
        new_btn.clicked.connect(self._new_station)
        layout.addWidget(new_btn)

        layout.addWidget(_divider())

        self.selected_lbl = _label("Current station: none", color=AMBER, size=8, bold=True)
        self.selected_lbl.setWordWrap(True)
        self.selected_lbl.setStyleSheet(
            f"color: {AMBER}; font-size: 8pt; font-weight: 700;"
            f" background: {CARD2_GLASS}; border: 1px solid {BORDER2};"
            f" border-radius: 4px; padding: 5px 7px;"
        )
        layout.addWidget(self.selected_lbl)

        self.hint_banner = _label("", color=AMBER, size=9, bold=True)
        self.hint_banner.setWordWrap(True)
        self.hint_banner.setStyleSheet(
            f"color: {AMBER}; font-size: 9pt; font-weight: 700;"
            f" background: {CARD2_GLASS}; border: 1px solid {AMBER};"
            f" border-radius: 4px; padding: 4px;"
        )
        self.hint_banner.hide()
        layout.addWidget(self.hint_banner)

        layout.addWidget(_label("Room Agents", bold=True, size=10))
        self.part_list = QListWidget()
        self.part_list.setMinimumHeight(180)
        self.part_list.setStyleSheet(
            f"QListWidget {{ background: {BG_GLASS}; border: 1px solid {BORDER}; "
            f"border-radius: 4px; color: {TEXT}; font-size: 8pt; }}"
            f"QListWidget::item {{ padding: 6px 8px; border-bottom: 1px solid {BORDER}; }}"
            f"QListWidget::item:selected {{ background: #1a3a2a; color: {GREEN}; "
            f"border-left: 3px solid {GREEN}; }}"
        )
        self.part_list.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.part_list, 1)
        self._refresh_participants()

    def _refresh_participants(self, select_index: int | None = None):
        prev_row = self.part_list.currentRow() if select_index is None else select_index
        self.part_list.clear()
        for idx, p in enumerate(self.window_ref.state.participants):
            bridge_short = _bridge_short(p.bridge)
            text = (
                f"{p.equipment}\n"
                f"   {p.type_label}\n"
                f"   skill: {p.skill_label}\n"
                f"   {p.status} | {bridge_short}"
            )
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, idx)
            self.part_list.addItem(item)
        # Restore / set selection so the user can act on it.
        if self.part_list.count() > 0:
            target = prev_row if 0 <= (prev_row or 0) < self.part_list.count() else (self.part_list.count() - 1)
            self.part_list.setCurrentRow(target)
        self._on_selection_changed()

    def _on_selection_changed(self):
        if self.part_list.count() == 0:
            self._show_banner("Choose device, agent, skill, then save the station.")
        elif self.part_list.currentRow() < 0:
            self._hide_banner()
        else:
            self._hide_banner()
            self._load_station_from_row()
        self._refresh_selected_label()
        center = getattr(self.window_ref, "center_panel", None)
        if center is not None:
            center.refresh_target()

    def _show_banner(self, text: str):
        self.hint_banner.setText(text)
        self.hint_banner.show()

    def _hide_banner(self):
        self.hint_banner.hide()
        self.hint_banner.setText("")

    def _refresh_selected_label(self):
        row = self.part_list.currentRow()
        if row < 0 or row >= len(self.window_ref.state.participants):
            self.selected_lbl.setText("Current station: NEW — fill device / agent / skill below")
            self.selected_lbl.setStyleSheet(
                f"color: {DIM}; font-size: 8pt; font-weight: 700;"
                f" background: {CARD2_GLASS}; border: 1px solid {BORDER2};"
                f" border-radius: 4px; padding: 5px 7px;"
            )
            return
        p = self.window_ref.state.participants[row]
        bridge_short = _bridge_short(p.bridge)
        self.selected_lbl.setText(
            f"Current station\n"
            f"  ▸ {p.equipment}\n"
            f"  ▸ {p.type_label} → {p.skill_label}\n"
            f"  ▸ {p.status}  ·  {bridge_short}"
        )
        # Highlight border with the status color.
        status_color = {
            "Assigned": GREEN,
            "Idle": DIM,
            "Waiting": AMBER,
            "Needs Review": RED,
        }.get(p.status, AMBER)
        self.selected_lbl.setStyleSheet(
            f"color: {TEXT}; font-size: 8pt; font-weight: 700;"
            f" background: {CARD2_GLASS}; border: 1px solid {status_color};"
            f" border-left: 3px solid {status_color};"
            f" border-radius: 4px; padding: 5px 7px;"
        )

    def _load_station_from_row(self):
        row = self.part_list.currentRow()
        if row < 0 or row >= len(self.window_ref.state.participants):
            return
        p = self.window_ref.state.participants[row]
        self.eq_target.setCurrentText(p.equipment)
        self.agent_type.setCurrentText(p.type_label)
        self.skill_type.setCurrentText(p.skill_label)
        self.bridge_target.setCurrentText(p.bridge)

    def _status_for_target(self, target: str) -> str:
        if _target_is_sub_engel(target) or _target_is_android(target) or _target_is_windows_sub_engel(target):
            return "Waiting"
        if _target_is_local(target):
            return "Assigned"
        return "Idle"

    def _save_station(self):
        target = self.eq_target.currentText()
        agent = self.agent_type.currentText()
        skill = self.skill_type.currentText()
        bridge = self.bridge_target.currentText()
        status = self._status_for_target(target)
        row = self.part_list.currentRow()
        if row < 0 or row >= len(self.window_ref.state.participants):
            p = Participant(
                name=f"{agent} / {skill}",
                kind="agent",
                type_label=agent,
                skill_label=skill,
                equipment=target,
                status=status,
                bridge=bridge,
            )
            self.window_ref.state.participants.append(p)
            row = len(self.window_ref.state.participants) - 1
            action = "added"
        else:
            p = self.window_ref.state.participants[row]
            p.name = f"{agent} / {skill}"
            p.kind = "agent"
            p.type_label = agent
            p.skill_label = skill
            p.equipment = target
            p.status = status
            p.bridge = bridge
            action = "updated"
        note = (
            f"Agent station {action}: {target} -> {agent} -> {skill}. "
            "Work requests stay in Engel AI UI."
        )
        self.window_ref.system_note(note)
        self.window_ref.save_state()
        self._refresh_participants(select_index=row)
        self.window_ref.center_panel.refresh_cards()
        self._hide_banner()

    def _new_station(self):
        self.part_list.clearSelection()
        self.part_list.setCurrentRow(-1)
        self._refresh_selected_label()
        self._show_banner("New station selected.")


# ─── Center panel — Chat ──────────────────────────────────────────────────────

class CenterChatPanel(QFrame):
    """Active meeting room center: agent cards plus main-UI order flow."""

    def __init__(self, window: "AgentMeetingRoomWindow"):
        super().__init__()
        self.window_ref = window
        self.setObjectName("card")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        hdr = QHBoxLayout()
        hdr.addWidget(_label("Agent Cards", bold=True, size=11, color=GREEN))
        hdr.addStretch()
        self.status_lbl = QLabel("● READY")
        self.status_lbl.setStyleSheet(
            f"color: {GREEN}; background: {CARD2_GLASS}; font-size: 8pt; "
            f"font-weight: 800; border: 1px solid {GREEN}; "
            f"border-radius: 3px; padding: 1px 8px;"
        )
        hdr.addWidget(self.status_lbl)
        layout.addLayout(hdr)

        self.cards_scroll = QScrollArea()
        self.cards_scroll.setWidgetResizable(True)
        self.cards_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.cards_scroll.setMinimumHeight(210)
        self.cards_scroll.setMaximumHeight(290)
        self.cards_scroll.setStyleSheet(f"QScrollArea {{ background: transparent; border: none; }}")
        self.cards_wrap = QWidget()
        self.cards_wrap.setStyleSheet("background: transparent;")
        self.cards_grid = QGridLayout(self.cards_wrap)
        self.cards_grid.setContentsMargins(0, 0, 0, 0)
        self.cards_grid.setSpacing(8)
        self.cards_scroll.setWidget(self.cards_wrap)
        layout.addWidget(self.cards_scroll)

        layout.addWidget(_divider())

        intake_row = QHBoxLayout()
        intake_row.addWidget(_label("Main UI Order Intake", bold=True, size=10, color=BLUE))
        intake_row.addStretch()
        self.target_lbl = _label("Selected station: none", color=AMBER, size=8, bold=True)
        self.target_lbl.setWordWrap(True)
        intake_row.addWidget(self.target_lbl)
        layout.addLayout(intake_row)

        self.intake_note = _label(
            "Orders arrive from Engel AI Main UI. This room auto-selects the matching agent "
            "cards by skill, dispatches each through its chosen bridge / device, and records "
            "the result below. No prompt input box lives here — by design.",
            color=TEXT,
            size=8,
        )
        self.intake_note.setWordWrap(True)
        layout.addWidget(self.intake_note)

        prompt_route_row = QHBoxLayout()
        prompt_route_row.addWidget(_label("Bridge Selection / Prompt Route", bold=True, size=9, color=PURPLE))
        prompt_route_row.addStretch()
        self.prompt_route_lbl = _label(_latest_prompt_route_ui_text(), color=TEXT, size=8, bold=True)
        self.prompt_route_lbl.setWordWrap(True)
        prompt_route_row.addWidget(self.prompt_route_lbl, 1)
        layout.addLayout(prompt_route_row)

        work_order_row = QHBoxLayout()
        work_order_row.addWidget(_label("Self-Upgrade Work Orders", bold=True, size=9, color=AMBER))
        work_order_row.addStretch()
        self.work_order_lbl = _label(_latest_self_upgrade_work_order_ui_text(), color=TEXT, size=8, bold=True)
        self.work_order_lbl.setWordWrap(True)
        work_order_row.addWidget(self.work_order_lbl, 1)
        layout.addLayout(work_order_row)

        button_row = QHBoxLayout()
        export_btn = QPushButton("Export")
        export_btn.setObjectName("purple")
        export_btn.clicked.connect(self._export)
        button_row.addWidget(export_btn)

        clear_btn = QPushButton("Clear Log")
        clear_btn.clicked.connect(self._clear_view)
        button_row.addWidget(clear_btn)
        layout.addLayout(button_row)

        layout.addWidget(_divider())
        layout.addWidget(_label("Order Flow", bold=True, size=10, color=PURPLE))
        self.transcript = QTextEdit()
        self.transcript.setReadOnly(True)
        self.transcript.setMinimumHeight(160)
        layout.addWidget(self.transcript, 1)

        self.refresh_cards()
        self._reload_transcript()
        self.refresh_prompt_route()
        self.refresh_work_orders()
        self.refresh_target()

    def refresh_prompt_route(self):
        self.prompt_route_lbl.setText(_latest_prompt_route_ui_text())

    def refresh_work_orders(self):
        self.work_order_lbl.setText(_latest_self_upgrade_work_order_ui_text())

    def refresh_cards(self):
        while self.cards_grid.count():
            item = self.cards_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        participants = self.window_ref.state.participants
        if not participants:
            empty_card = QFrame()
            empty_card.setObjectName("card2")
            empty_card.setStyleSheet(
                f"QFrame#card2 {{ background: {CARD2_GLASS}; "
                f"border: 1px dashed {BORDER2}; border-radius: 6px; padding: 18px; }}"
            )
            empty_layout = QVBoxLayout(empty_card)
            empty_layout.setSpacing(6)
            empty_layout.addWidget(_label("◌  No agent stations yet",
                                          color=AMBER, size=11, bold=True))
            empty_layout.addWidget(_label(
                "Build one on the left:   1. Device   →   2. Agent   →   3. Skill   →   Bridge   →   Save Agent Station",
                color=TEXT, size=9,
            ))
            empty_layout.addWidget(_label(
                "Orders from Engel AI Main UI auto-create stations when one is missing.",
                color=DIM, size=8,
            ))
            self.cards_grid.addWidget(empty_card, 0, 0, 1, 3)
            return

        selected = self._selected_index()
        columns = 3 if len(participants) >= 3 else 2
        status_color_map = {
            "Assigned": GREEN,
            "Idle": DIM,
            "Waiting": AMBER,
            "Needs Review": RED,
        }
        for idx, p in enumerate(participants):
            card = QFrame()
            card.setObjectName("card2")
            card.setMinimumHeight(150)
            status_color = status_color_map.get(p.status, AMBER)
            is_selected = (idx == selected)
            outer = GREEN if is_selected else BORDER2
            card.setStyleSheet(
                f"QFrame#card2 {{ background: {CARD2_GLASS}; border: 1px solid {outer}; "
                f"border-left: 4px solid {status_color}; border-radius: 6px; }}"
            )
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(10, 8, 10, 8)
            card_layout.setSpacing(3)

            # Header row: Station N  ·  status pill
            hdr_row = QHBoxLayout()
            hdr_row.addWidget(_label(f"Station {idx + 1}", color=DIM, size=7, bold=True))
            hdr_row.addStretch()
            status_lbl = QLabel(p.status.upper())
            status_lbl.setStyleSheet(
                f"color: {BG}; background: {status_color};"
                f" font-size: 7pt; font-weight: 800;"
                f" border-radius: 3px; padding: 1px 6px;"
            )
            hdr_row.addWidget(status_lbl)
            card_layout.addLayout(hdr_row)

            agent_lbl = _label(p.type_label, color=GREEN, size=10, bold=True)
            agent_lbl.setWordWrap(True)
            card_layout.addWidget(agent_lbl)
            skill_lbl = _label(f"⌁ {p.skill_label}", color=PURPLE, size=8, bold=True)
            skill_lbl.setWordWrap(True)
            card_layout.addWidget(skill_lbl)
            eq_lbl = _label(f"▣ {p.equipment}", color=BLUE, size=8, bold=True)
            eq_lbl.setWordWrap(True)
            card_layout.addWidget(eq_lbl)
            bridge_lbl = _label(f"⇄ {_bridge_short(p.bridge)}", color=TEXT, size=8)
            bridge_lbl.setWordWrap(True)
            card_layout.addWidget(bridge_lbl)
            card_layout.addStretch()
            action_row = QHBoxLayout()
            select_btn = QPushButton("Select")
            if is_selected:
                select_btn.setObjectName("primary")
                select_btn.setText("● Selected")
            select_btn.clicked.connect(lambda _checked=False, row=idx: self._select_row(row))
            action_row.addWidget(select_btn)
            card_layout.addLayout(action_row)
            self.cards_grid.addWidget(card, idx // columns, idx % columns)

    def _selected_index(self) -> int:
        left = getattr(self.window_ref, "left_panel", None)
        if left is None:
            return -1
        return left.part_list.currentRow()

    def _select_row(self, row: int):
        left = self.window_ref.left_panel
        if 0 <= row < left.part_list.count():
            left.part_list.setCurrentRow(row)
        self.refresh_target()
        self.refresh_cards()

    def refresh_target(self):
        row = self._selected_index()
        if row < 0 or row >= len(self.window_ref.state.participants):
            self.target_lbl.setText("Selected station: none")
            self.target_lbl.setStyleSheet(
                f"color: {DIM}; font-size: 8pt; font-weight: 700;"
            )
            return
        p = self.window_ref.state.participants[row]
        self.target_lbl.setText(
            f"▸ {p.equipment}  →  {p.type_label}  →  {p.skill_label}  ·  {_bridge_short(p.bridge)}"
        )
        self.target_lbl.setStyleSheet(
            f"color: {GREEN}; font-size: 8pt; font-weight: 700;"
        )
        self.refresh_cards()

    def _reload_transcript(self):
        self.transcript.clear()
        if not self.window_ref.state.messages:
            self._append("Engel Core", "Meeting room ready. Orders arrive from Engel AI Main UI; stations auto-select by skill.", role="agent", record=False)
            return
        for m in self.window_ref.state.messages:
            self._append(
                m.get("name", "?"),
                m.get("text", ""),
                role=m.get("role", "user"),
                record=False,
                time_=m.get("time", _now_pretty()),
            )

    def _append(self, name: str, text: str, role: str = "user", record: bool = True, time_: Optional[str] = None):
        time_ = time_ or _now_pretty()
        color = {"agent": GREEN, "system": AMBER, "user": BLUE}.get(role, TEXT)
        html_text = html.escape(str(text)).replace("\n", "<br>")
        html_name = html.escape(str(name))
        block = (
            f"<span style='color:{DIM};'>[{html.escape(time_)}]</span> "
            f"<b style='color:{color};'>{html_name}:</b> "
            f"<span style='color:{TEXT};'>{html_text}</span>"
        )
        cursor = self.transcript.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        if cursor.position() > 0:
            cursor.insertBlock()
        cursor.insertHtml(block)
        self.transcript.setTextCursor(cursor)
        self.transcript.ensureCursorVisible()
        if record:
            self.window_ref.state.messages.append({
                "role": role, "name": name, "text": text, "time": time_,
            })
            self.window_ref.save_state()

    def system_note(self, text: str):
        self._append("System", text, role="system")

    def add_agent_message(self, name: str, text: str):
        self._append(name, text, role="agent")

    def _station_snapshot(self, row: int) -> dict:
        p = self.window_ref.state.participants[row]
        data = asdict(p)
        data["_row"] = row
        return data

    def _clear_view(self):
        self.transcript.clear()
        self._append("Engel Core", "View cleared. State and prior room log are still saved.", role="agent", record=False)

    def _export(self):
        path = export_room_summary(self.window_ref.state)
        self.window_ref.state.last_export = str(path)
        self.window_ref.save_state()
        self.system_note(f"Exported room summary -> {path}")


class AgentMeetingRoomWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.state: RoomState = _load_state()
        self.setWindowTitle("Engel AI — Agent Meeting Room — Ship Team")
        self.setWindowOpacity(_ui_opacity("ENGEL_MEETING_ROOM_OPACITY", "ENGEL_UI_OPACITY"))
        self.resize(1280, 760)
        self.setMinimumSize(960, 600)

        central = QWidget()
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        # Top bar
        top = QHBoxLayout()
        top.addWidget(_label("⌬  AGENT MEETING ROOM", bold=True, color=GREEN, size=11))
        top.addWidget(_label("   Ship team collab  ·  Agent Cards  ·  Main-UI Order Flow  ·  Local-first",
                             color=DIM, size=8))
        top.addStretch()
        self.clock_lbl = _label("--:--:--", color=DIM, size=8)
        top.addWidget(self.clock_lbl)
        root.addLayout(top)

        charter = _label(SHIP_TEAM_COLLAB_CHARTER, color=AMBER, size=8, bold=True)
        charter.setWordWrap(True)
        charter.setObjectName("ship-team-charter")
        root.addWidget(charter)

        # Body: station builder + agent cards/work launcher.
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.left_panel = LeftPanel(self)
        self.center_panel = CenterChatPanel(self)
        splitter.addWidget(self.left_panel)
        splitter.addWidget(self.center_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 5)
        splitter.setSizes([330, 930])
        root.addWidget(splitter, 1)

        # Bottom status bar — reflects actual local connectivity.
        bottom = QHBoxLayout()
        android_state, android_color = self._probe_android_status()
        bottom.addWidget(_label(f"● Android App Worker — {android_state}",
                                color=android_color, size=8, bold=True))
        bottom.addWidget(_label("  │  ", color=DIM, size=8))
        bottom.addWidget(_label(
            "● Sub-Engel OS Worker — preview-only job packets (more computers for AI)",
            color=AMBER, size=8, bold=True))
        bottom.addWidget(_label("  │  ", color=DIM, size=8))
        bottom.addWidget(_label("● Local Engel AI — available",
                                color=GREEN, size=8, bold=True))
        bottom.addWidget(_label("  │  ", color=DIM, size=8))
        sub_state, sub_color = self._probe_sub_engel_status()
        bottom.addWidget(_label(f"Sub-Engel registry: {sub_state}",
                                color=sub_color, size=8, bold=True))
        bottom.addWidget(_label("  │  ", color=DIM, size=8))
        win_state, win_color = self._probe_windows_sub_engel_status()
        bottom.addWidget(_label(f"Windows Sub-Engel Node: {win_state}",
                                color=win_color, size=8, bold=True))
        bottom.addWidget(_label("  |  ", color=DIM, size=8))
        transport_state, transport_color = self._probe_server_transport_status()
        bottom.addWidget(_label(f"CT246 Transport: {transport_state}",
                                color=transport_color, size=8, bold=True))
        bottom.addStretch()
        bottom.addWidget(_label("runtime/meeting_room  ·  reports/meeting_rooms",
                                color=DIM, size=8))
        root.addLayout(bottom)

        # Clock refresh
        self._clock = QTimer(self)
        self._clock.timeout.connect(self._tick)
        self._clock.start(1000)
        self._state_refresh = QTimer(self)
        self._state_refresh.timeout.connect(self._reload_state_from_disk)
        self._state_refresh.start(2500)
        self._tick()

    def _tick(self):
        self.clock_lbl.setText(datetime.datetime.now().strftime("%H:%M:%S  %Y-%m-%d"))

    def _reload_state_from_disk(self):
        try:
            latest = _load_state()
        except Exception:
            return
        if asdict(latest) == asdict(self.state):
            self.center_panel.refresh_work_orders()
            return
        selected = self.left_panel.part_list.currentRow()
        self.state = latest
        self.left_panel._refresh_participants(select_index=selected)
        self.center_panel.refresh_cards()
        self.center_panel._reload_transcript()
        self.center_panel.refresh_prompt_route()
        self.center_panel.refresh_work_orders()
        self.center_panel.refresh_target()

    def _probe_android_status(self) -> tuple[str, str]:
        """Detect whether a USB/hardwire or WiFi/LAN worker link is present."""
        parts: list[str] = []
        color = AMBER
        try:
            from engel_adb_worker_manager import render_adb_workers_status
            txt = render_adb_workers_status() or ""
            # Heuristic: the status output lists devices as 'Devices: N connected via USB'
            m = re.search(r"Devices:\s+(\d+)\s+connected", txt)
            n = int(m.group(1)) if m else 0
            if n > 0:
                parts.append(f"USB/hardwire ADB connected ({n})")
                color = GREEN
        except Exception:
            pass
        if not parts:
            parts.append("USB/hardwire ADB not connected")
        try:
            _prefer_workspace_android_modules()
            from engel_remote_worker_link_manager import link_status
            state = link_status()
            if state.get("receiver_running") or state.get("last_seen_utc"):
                host = state.get("host", "LAN")
                port = state.get("port", "")
                parts.append(f"WiFi/LAN pair ready ({host}:{port})")
                color = GREEN
            else:
                parts.append("WiFi/LAN pair not running")
        except Exception:
            parts.append("WiFi/LAN status unavailable")
        return (" | ".join(parts), color)

    def _probe_sub_engel_status(self) -> tuple[str, str]:
        """Read local Linux Sub-Engel registry state; no network call is made."""
        try:
            from engel_sub_node_meeting_bridge import meeting_node_statuses
            status = meeting_node_statuses()["linux_sub_engel"]
            text = str(status.get("status") or "Sub-Engel OS Worker — preview-only job packets enabled (additional computer usage for AI)")
            color = GREEN if status.get("paired") else AMBER
            return text, color
        except Exception:
            return "Sub-Engel OS Worker — preview-only job packets enabled; registry unavailable", AMBER

    def _probe_windows_sub_engel_status(self) -> tuple[str, str]:
        """Read local Windows Sub-Engel registry/check-in state; no listener is started."""
        try:
            from engel_sub_node_meeting_bridge import meeting_node_statuses
            statuses = meeting_node_statuses()
            status = statuses["windows_sub_engel"]
            text = str(status.get("status") or "not paired; outbound check-in slot ready")
            registered_count = len(statuses.get("windows_sub_engel_nodes", []) or [])
            planned_count = len(statuses.get("windows_sub_engel_planned_nodes", []) or [])
            if registered_count or planned_count:
                text = f"{text}; registered {registered_count}, planned {planned_count}"
            color = GREEN if status.get("meeting_ready") else AMBER
            return text, color
        except Exception:
            return "registry unavailable; outbound check-in slot ready", AMBER

    def _probe_server_transport_status(self) -> tuple[str, str]:
        """Read the CT246-owned direct transport status."""
        try:
            from engel_sub_node_meeting_bridge import SERVER_TRANSPORT_ROOT

            if SERVER_TRANSPORT_ROOT.is_dir():
                return "server-owned direct HTTP lane ready", GREEN
            return "server transport not initialized", AMBER
        except Exception:
            return "status unavailable", AMBER

    def add_participant(self, p: Participant):
        # Append, mark as idle / assigned local by default
        self.state.participants.append(p)
        self.center_panel.add_agent_message(p.name, f"joined as {p.kind} - {p.type_label}.")
        self.save_state()
        self.center_panel.refresh_cards()

    def system_note(self, text: str):
        self.center_panel.system_note(text)

    def save_state(self):
        _save_state(self.state)


# ─── Launchers ────────────────────────────────────────────────────────────────

def launch_meeting_room() -> int:
    """Open the Agent Meeting Room window. Returns exit code."""
    if not HAS_QT:
        print("Qt (PyQt6 or PySide6) is not installed. Install with:  pip install PySide6")
        return 1
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)
    win = AgentMeetingRoomWindow()
    win.show()
    return app.exec()


def open_meeting_room_non_blocking(parent=None) -> Optional["AgentMeetingRoomWindow"]:
    """Open Meeting Room within an existing Qt event loop (e.g. from Desktop V2)."""
    if not HAS_QT:
        return None
    win = AgentMeetingRoomWindow()
    win.show()
    return win


if __name__ == "__main__":
    sys.exit(launch_meeting_room())
