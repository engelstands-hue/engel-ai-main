import sys
import math
import threading
import os
import engel_temp_policy  # noqa: F401
import ctypes
import signal
import json
import subprocess
import shutil
import time
import wave
import numpy as np

# Keep Playwright browser cache project-owned when Engel launches it.
os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH', os.path.join(os.path.dirname(__file__), 'runtime', 'playwright-browsers'))
try:
    import sounddevice as sd
except ImportError:
    sd = None
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QPointF, QRectF
from PySide6.QtGui import (
    QColor, QPainter, QPen, QBrush, QRadialGradient, QFont,
    QAction, QPixmap, QIcon, QCursor, QPainterPath, QKeySequence, QShortcut
)
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QWidget, QTextEdit, QLineEdit, QMenu,
    QSystemTrayIcon, QMessageBox, QPushButton, QFrame, QInputDialog,
    QGridLayout, QHBoxLayout, QHeaderView, QTabWidget, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QSizePolicy, QLabel, QScrollArea, QComboBox
)

def _resolve_engel_root():
    if getattr(sys, "frozen", False):
        exe_path = Path(sys.executable).resolve()
        if (
            exe_path.name.lower() == "engel.exe"
            and exe_path.parent.name.lower() == "app"
            and exe_path.parent.parent.name.lower() == "live"
        ):
            return str(exe_path.parent.parent.parent)
        return str(exe_path.parent)
    return str(Path(__file__).resolve().parent)

ROOT = _resolve_engel_root()
sys.path.insert(0, ROOT)

import engel_app as core
import engel_ai_intent_planner as ai_planner
import engel_ai_proceed_receipts as proceed_receipts
import engel_ai_receipt_viewer as receipt_viewer
import engel_ai_body_status as ai_body_status
import engel_ui_theme as ui_theme
try:
    from engel_hive_data_services import build_companion_hive_summary
except Exception:
    build_companion_hive_summary = None
from engel_prompt_injection_guard import check_prompt_injection

# Auto-enable offline seed LLM if model file is present and env var not already set
def _auto_enable_offline_seed_llm():
    if os.environ.get("ENGEL_OFFLINE_SEED_LLM_ENABLED", "") == "1":
        return
    try:
        _model = Path(ROOT) / "models" / "qwen2.5-0.5b-instruct" / "qwen2.5-0.5b-instruct-q4_k_m.gguf"
        if _model.exists():
            os.environ["ENGEL_OFFLINE_SEED_LLM_ENABLED"] = "1"
    except Exception:
        pass
_auto_enable_offline_seed_llm()


def engel_chat_pipeline(text: str) -> str:
    """Shared chat-response chain used by the desktop chat *and* the Discord
    bot. Tries browser-AI bridge first, then brain provider, then local LLM,
    then identity-sensitive fallback. Returns the first non-empty reply.
    """
    try:
        import engel_browser_ai_bridge
        reply = engel_browser_ai_bridge.browser_ai_chat_if_connected(text)
        if reply:
            return reply
    except Exception:
        pass
    try:
        import engel_app as _core
        if hasattr(_core, "ask_brain_provider"):
            ctx = (
                _core.identity_sensitive_extra_context_v2identity_d2(text)
                if hasattr(_core, "identity_sensitive_extra_context_v2identity_d2")
                else ""
            )
            reply = _core.ask_brain_provider(text, ctx)
            if reply:
                return reply
        if hasattr(_core, "local_communication_response_for_unrouted_text_v2comm_sanity"):
            reply = _core.local_communication_response_for_unrouted_text_v2comm_sanity(text)
            if reply:
                return reply
        if hasattr(_core, "identity_sensitive_direct_response_v2identity_d2"):
            reply = _core.identity_sensitive_direct_response_v2identity_d2(text)
            if reply:
                return reply
    except Exception:
        pass
    return "I'm here. Connect me to an AI for conversation: browser ai connect claude"


try:
    import engel_discord_bridge as _engel_discord_bridge
    _engel_discord_bridge.set_engel_chat_hook(engel_chat_pipeline)
    # Production Discord is CT 246 tools/engel_discord_bridge.py. A laptop
    # autostart would steal the gateway and answer from this companion hook
    # instead of Engel AI Main. Opt in only: ENGEL_DISCORD_AUTOSTART=1.
    if (
        os.environ.get("DISCORD_BOT_TOKEN", "").strip()
        and os.environ.get("ENGEL_DISCORD_AUTOSTART", "0") == "1"
    ):
        try:
            _engel_discord_bridge.discord_start()
        except Exception:
            pass
except Exception:
    pass


def _auto_detect_speech_ready() -> None:
    """If a Whisper model + a Piper voice are already on disk, log that the
    speech bridge is ready so the user doesn't have to discover it. Does not
    start any inference or open the mic — just marks the bridge as primed."""
    try:
        import engel_speech_bridge as _speech
        whisper_ok = bool(_speech._installed_whisper_models())  # type: ignore[attr-defined]
        piper_ok   = bool(_speech._installed_piper_voices())    # type: ignore[attr-defined]
        if whisper_ok and piper_ok:
            # Preload references but don't load model weights into RAM yet.
            os.environ.setdefault("ENGEL_SPEECH_READY", "1")
    except Exception:
        pass


_auto_detect_speech_ready()


# ENGEL_AI_GROWTH_GUI_TABS_V1_IMPORTS_START
import engel_ai_growth_dashboard as ai_growth_dashboard
import engel_candidate_review_dashboard as candidate_review_dashboard
# ENGEL_CODE_COMPANION_CANDIDATE_REVIEW_GUI_V1_IMPORT_START
import engel_code_companion_candidate_review_status as code_companion_candidate_review_status
# ENGEL_CODE_COMPANION_CANDIDATE_REVIEW_GUI_V1_IMPORT_END
import engel_code_companion_patch_status_surface as code_companion_patch_status_surface
import engel_global_password_gate as global_password_gate
import engel_low_risk_self_fix_status_surface as low_risk_self_fix_status_surface
import engel_memory_promotion_writer as memory_promotion_writer
import engel_protected_action_registry as protected_action_registry
import engel_research_toggle_status as research_toggle_status
import engel_research_toggle_worker as research_toggle_worker
import engel_research_to_fix_loop as research_to_fix_loop
import engel_self_fix_receipt_viewer as self_fix_receipt_viewer
import engel_self_learning_status_surface as self_learning_status_surface
import engel_system_integration_status as system_integration_status
# ENGEL_AI_GROWTH_GUI_TABS_V1_IMPORTS_END


# ENGEL_AI_GROWTH_GUI_TABS_V1_COMPANION_CONSTANTS_START
AI_GROWTH_GUI_TAB_NAMES = [
    "AI Growth",
    "Self-Learning",
    "Candidate Review",
    "Code Companion Review",
    "Global Safety",
    "System Integration",
    "Self-Fix",
    "Memory Promotion",
    "Research-to-Fix",
]

AI_GROWTH_GUI_STATUS_LABELS = [
    "AI_GROWTH_DASHBOARD",
    "READ_ONLY_VIEW",
    "READ ONLY",
    "LOCAL_ONLY",
    "SELF_RESEARCH_VISIBLE",
    "CANDIDATE_LEARNING_VISIBLE",
    "MEMORY_PROMOTION_VISIBLE",
    "VERIFIER_IMPROVEMENT_VISIBLE",
    "SELF_FIX_IMPROVEMENT_VISIBLE",
    "LOW_RISK_SELF_FIX_VISIBLE",
    "RESEARCH_TO_FIX_VISIBLE",
    "NO_ACTION_EXECUTION",
    "NO_MEMORY_WRITE",
    "NO_SOURCE_MUTATION",
    "NO_VERIFIER_UPDATE",
    "NO_SELF_FIX_POLICY_UPDATE",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "DRY RUN VISIBILITY ONLY",
    "LOW RISK ONLY",
    "HIGH RISK STOPS",
    "NO APPLY BUTTON",
    "NO_MODEL_RUNTIME",
    "NO_PACKAGE_REFRESH",
    "NO TRUSTED MEMORY WRITE",
    "NO PROVIDER NETWORK BROWSER",
    "NO_TRUSTED_MEMORY_WRITE_BUTTON",
    "NO_SOURCE_MUTATION_BUTTON",
    "NO_SELF_FIX_APPLY_BUTTON",
    "NO_BACKGROUND_WORKER",
    "NO_STARTUP_AUTORUN",
    "NO_RUNTIME_TRIGGER",
]
# ENGEL_AI_GROWTH_GUI_TABS_V1_COMPANION_CONSTANTS_END

# ENGEL_COMPANION_MINIMAL_TECH_THEME_V1_START
COMPANION_MINIMAL_TECH_THEME_MARKER = "Engel Minimal Tech Console"
COMPANION_BG_PRIMARY = "rgba(7, 9, 12, 245)"
COMPANION_BG_PANEL = "rgba(13, 17, 23, 236)"
COMPANION_BG_CARD = "rgba(18, 24, 33, 232)"
COMPANION_BG_CARD_SUBTLE = "rgba(22, 28, 37, 214)"
COMPANION_BORDER_SUBTLE = "rgba(91, 200, 255, 48)"
COMPANION_BORDER_FOCUS = "rgba(91, 200, 255, 92)"
COMPANION_TEXT_PRIMARY = "rgba(232, 244, 255, 242)"
COMPANION_TEXT_SECONDARY = "rgba(169, 183, 197, 226)"
COMPANION_TEXT_MUTED = "rgba(117, 133, 150, 214)"
COMPANION_BADGE_DISABLED = "rgba(101, 115, 134, 214)"
COMPANION_BADGE_ACTIVE = "rgba(115, 209, 139, 232)"
COMPANION_BADGE_WARNING = "rgba(230, 201, 106, 232)"
COMPANION_ACCENT_SAFE = "rgba(115, 209, 139, 232)"
COMPANION_ACCENT_INFO = "rgba(91, 200, 255, 232)"
# ENGEL_COMPANION_MINIMAL_TECH_THEME_V1_END


# ENGEL_MOBILE_CONNECTION_COMPANION_READONLY_TAB_V1_CONSTANTS_START
MOBILE_ENGEL_REMOTE_WORKERS_LABEL = "Engel Remote Workers"
MOBILE_REMOTE_QUEENS_LABEL = MOBILE_ENGEL_REMOTE_WORKERS_LABEL

MOBILE_CONNECTION_PACKET_TYPES = [
    "mobile_status_snapshot",
    "mobile_note",
    "mobile_request",
    "mobile_receipt_view_request",
    "mobile_report_view_request",
    "mobile_approval_request",
    "mobile_remote_queen_task_request",
    "mobile_health_ping",
    "mobile_device_profile",
    "mobile_sync_summary",
    "mobile_error_report",
    "mobile_permission_request",
]

MOBILE_CONNECTION_DISABLED_ACTIONS = [
    "Refresh Local Mobile Status",
    "View Mobile Contract",
    "View Mobile Display Design",
    "Open Mobile Inbox",
    "Open Mobile Receipts",
    "Review Pending Mobile Request",
    "Pair Device",
    "Enable Mobile Runtime",
    "Start Engel Remote Worker",
    "Export Mobile Status Report",
]

MOBILE_CONNECTION_APPROVED_DOCS = [
    ("memory\\ENGEL_MOBILE_CONNECTION_CONTRACT_V1.json", "Mobile pillar contract"),
    ("memory\\ENGEL_MOBILE_CONNECTION_PLAN_V1.md", "Human-readable Mobile plan"),
    ("memory\\MOBILE_CONNECTION_STATUS_DISPLAY_DESIGN_V1.json", "Machine-readable status display design"),
    ("memory\\ENGEL_MOBILE_CONNECTION_STATUS_DISPLAY_DESIGN_V1.md", "Human-readable status display design"),
    ("memory\\MOBILE_CONNECTION_DESKTOP_STATUS_SURFACE_CONTRACT_V1.json", "Desktop status surface contract"),
    ("memory\\ENGEL_MOBILE_CONNECTION_DESKTOP_STATUS_SURFACE_CONTRACT_V1.md", "Human-readable desktop status surface contract"),
    ("memory\\MIXED_COLONY_ARCHITECTURE_CONTRACT_V1.json", "Mixed-colony architecture contract"),
    ("reports\\codex_bridge\\ENGEL_MOBILE_CONNECTION_CONTRACT.md", "Mobile contract completion report"),
    ("reports\\codex_bridge\\MOBILE_CONNECTION_STATUS_DISPLAY_DESIGN.md", "Status display design completion report"),
    ("reports\\codex_bridge\\MOBILE_CONNECTION_DESKTOP_STATUS_SURFACE_CONTRACT.md", "Desktop status surface contract report"),
]
# ENGEL_MOBILE_CONNECTION_COMPANION_READONLY_TAB_V1_CONSTANTS_END



# ----------------------------------------------------------------------
# Engel Window Icon Repair V2
# ----------------------------------------------------------------------
def _apply_engel_window_icon_repair_v2(window):
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Engel.Desktop.Companion")
    except Exception:
        pass
    try:
        import os
        from PySide6.QtGui import QIcon
        from PySide6.QtWidgets import QApplication
        icon_path = os.path.join(ROOT, "assets", "branding", "engel_icon.ico")
        if os.path.exists(icon_path):
            icon = QIcon(icon_path)
            app = QApplication.instance()
            if app:
                app.setWindowIcon(icon)
            window.setWindowIcon(icon)
    except Exception:
        pass


# ----------------------------------------------------------------------
# Engel Alive State Visual V2
# Visual-only state reactions. No process launching or research/mobile logic.
# ----------------------------------------------------------------------
def _apply_engel_alive_state_visual_v2(window):
    try:
        import math
        from PySide6.QtCore import QTimer, Qt
        from PySide6.QtGui import QColor
        from PySide6.QtWidgets import QLabel, QGraphicsDropShadowEffect

        if getattr(window, "_engel_alive_state_visual_v2_ready", False):
            return
        window._engel_alive_state_visual_v2_ready = True
        window._engel_alive_state_visual_v2_phase = 0

        def _ensure_label(name, text, x, y, w, h):
            try:
                if not hasattr(window, name):
                    lab = QLabel(text, window)
                    lab.setAlignment(Qt.AlignCenter)
                    lab.setGeometry(x, y, w, h)
                    lab.show()
                    lab.raise_()
                    setattr(window, name, lab)
                return getattr(window, name)
            except Exception:
                return None

        state_label = _ensure_label("alive_state_visual_v2_label", "SAFE / IDLE", 392, 24, 176, 30)
        sub_label = _ensure_label("alive_state_visual_v2_sub", "watching", 392, 224, 176, 22)

        def _chat_text_tail():
            try:
                widgets = [
                    getattr(window, "output", None),
                    getattr(window, "chat", None),
                    getattr(window, "log", None),
                    getattr(window, "text", None),
                    getattr(window, "conversation", None),
                    getattr(window, "textbox", None),
                ]
                for w in widgets:
                    if w is None:
                        continue
                    try:
                        if hasattr(w, "toPlainText"):
                            return w.toPlainText()[-2500:].lower()
                        if hasattr(w, "get"):
                            return str(w.get("1.0", "end"))[-2500:].lower()
                    except Exception:
                        pass
            except Exception:
                pass
            return ""

        def _state():
            try:
                mobile_on = bool(getattr(window, "mobile_toggle").isChecked()) if hasattr(window, "mobile_toggle") else False
            except Exception:
                mobile_on = False
            try:
                research_on = bool(getattr(window, "overnight_toggle").isChecked()) if hasattr(window, "overnight_toggle") else False
            except Exception:
                research_on = False

            tail = _chat_text_tail()

            if "traceback" in tail or "error" in tail or "failed" in tail:
                return ("ERROR", "needs review", "#ff4444")
            if "caution" in tail or "approve" in tail or "blocked" in tail:
                return ("CAUTION", "approval gate", "#ffaa00")
            if research_on or "stage: running_research" in tail or "research on" in tail:
                return ("RESEARCHING", "learning safely", "#44aaff")
            if mobile_on or "mobile bridge: online" in tail:
                return ("MOBILE ON", "local bridge", "#00ff88")
            if "you:" in tail and "engel:" in tail:
                return ("SPEAKING", "responding", "#00ff88")
            return ("IDLE", "watching", "#666666")

        def _tick():
            try:
                label, sub, color_hex = _state()

                state_style = (
                    "QLabel {"
                    "background: #111111;"
                    "color: " + color_hex + ";"
                    "border: 1px solid #333333;"
                    "border-radius: 0px;"
                    "font: 700 8pt Consolas;"
                    "letter-spacing: 1px;"
                    "padding: 2px 4px;"
                    "}"
                )
                sub_style = (
                    "QLabel {"
                    "background: #0a0a0a;"
                    "color: #666666;"
                    "border: 0px;"
                    "font: 400 8pt Consolas;"
                    "padding: 1px 4px;"
                    "}"
                )

                if state_label:
                    state_label.setText(label)
                    state_label.setStyleSheet(state_style)
                    state_label.raise_()

                if sub_label:
                    sub_label.setText(sub)
                    sub_label.setStyleSheet(sub_style)
                    sub_label.raise_()

                button_style = (
                    "QPushButton {"
                    "background: #111111;"
                    "color: #44aaff;"
                    "border: 1px solid #333333;"
                    "border-radius: 0px;"
                    "font: 700 8pt Consolas;"
                    "padding: 3px 7px;"
                    "}"
                    "QPushButton:hover {"
                    "background: #161616;"
                    "color: #ffffff;"
                    "border-color: #00ff88;"
                    "}"
                    "QPushButton:checked {"
                    "background: #1a2a1a;"
                    "color: #00ff88;"
                    "border-color: #00ff88;"
                    "}"
                )

                for name, x, y, w, h in [
                    ("mobile_toggle", 392, 64, 176, 34),
                    ("overnight_toggle", 392, 104, 176, 34),
                    ("mind_connections_button", 392, 144, 176, 34),
                    ("thinking_screen_button", 392, 184, 176, 34),
                    ("research_office_button", 392, 224, 176, 34),
                    ("code_companion_button", 392, 264, 176, 34),
                ]:
                    try:
                        if hasattr(window, name):
                            btn = getattr(window, name)
                            if not getattr(window, "chat_open", False):
                                btn.setGeometry(x, y, w, h)
                            btn.setStyleSheet(button_style)
                            btn.raise_()
                    except Exception:
                        pass
            except Exception:
                pass

        window._engel_alive_state_visual_v2_timer = QTimer(window)
        window._engel_alive_state_visual_v2_timer.timeout.connect(_tick)
        window._engel_alive_state_visual_v2_timer.start(650)
        _tick()
    except Exception:
        pass

class EngelCompanion(QWidget):
    def __init__(self):
        super().__init__()

        self.phase = 0.0
        self.state = "idle"

        for icon_path in [
            os.path.join(core.ROOT, "assets", "branding", "final", "engel_icon_final.ico"),
            os.path.join(core.ROOT, "assets", "branding", "engel_icon.ico"),
        ]:
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
                break
        self.drag_pos = None
        self.chat_open = False
        self.is_recording = False
        self.audio_frames = []
        self.audio_stream = None
        self.sample_rate = 16000
        self._engel_close_requested = False
        self._shutdown_complete = False

        self.setWindowTitle("Engel Companion")
        _apply_engel_window_icon_repair_v2(self)
        _apply_engel_alive_state_visual_v2(self)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAcceptDrops(True)
        self.resize(260, 250)

        self.chat = QTextEdit(self)
        self.chat.setReadOnly(True)
        self.chat.setLineWrapMode(QTextEdit.WidgetWidth)
        self.chat.setMinimumHeight(280)
        self.chat.setGeometry(14, 220, 520, 300)
        self.chat.hide()
        self.chat.setStyleSheet(ui_theme.companion_chat_stylesheet())

        self.input = QLineEdit(self)
        self.input.setMinimumHeight(44)
        self.input.setGeometry(14, 530, 520, 40)
        self.input.hide()
        self.input.setPlaceholderText("Talk to Engel...")
        self.input.returnPressed.connect(self.send_message)
        self.input.setStyleSheet(ui_theme.companion_input_stylesheet())

        self.dashboard_title = QLabel("ENGEL COMPANION", self)
        self.dashboard_title.setStyleSheet(ui_theme.companion_dashboard_title_stylesheet())
        self.dashboard_title.hide()

        self.dashboard_subtitle = QLabel(
            "Drop files to summarize · type to talk",
            self,
        )
        self.dashboard_subtitle.setWordWrap(True)
        self.dashboard_subtitle.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.dashboard_subtitle.setStyleSheet(ui_theme.companion_dashboard_subtitle_stylesheet())
        self.dashboard_subtitle.hide()

        self.status_rail = QLabel(self)
        self.status_rail.setWordWrap(True)
        self.status_rail.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.status_rail.setStyleSheet(ui_theme.companion_status_rail_stylesheet())
        _seed_llm_active = os.environ.get("ENGEL_OFFLINE_SEED_LLM_ENABLED", "") == "1"
        _provider_label = "LOCAL LLM" if _seed_llm_active else "PROVIDER OFF"
        self.status_rail.setText(f"LOCAL · GUARDS ON · {_provider_label}")
        self.status_rail.hide()

        self.engel_voice_mode = "Local Engel"
        self.engel_voice_mode_panel = self._build_engel_voice_mode_panel()

        # Session Toggle Buttons V1ee
        # Limited scope: start/stop local mobile bridge and overnight research runner only.
        self.mobile_toggle = QPushButton("Mobile OFF", self)
        self.mobile_toggle.setCheckable(True)
        self.mobile_toggle.setGeometry(392, 64, 176, 34)
        self.mobile_toggle.setToolTip("Start or end Engel mobile bridge session")
        self.mobile_toggle.toggled.connect(self.toggle_mobile_session_button)
        self.mobile_toggle.hide()

        self.overnight_toggle = QPushButton("Research OFF", self)
        self.overnight_toggle.setCheckable(True)
        self.overnight_toggle.setGeometry(392, 104, 176, 34)
        self.overnight_toggle.setToolTip("Enable or disable bounded candidate-only research worker mode. Does not start a loop.")
        self.overnight_toggle.toggled.connect(self.toggle_overnight_research_button)
        self.overnight_toggle.hide()

        toggle_style = self._companion_minimal_toggle_stylesheet()
        self.mobile_toggle.setStyleSheet(toggle_style)
        self.overnight_toggle.setStyleSheet(toggle_style)
        self.research_office_button = QPushButton("Hive", self)
        self.research_office_button.setGeometry(392, 144, 176, 34)
        self.research_office_button.setToolTip("Open the local Hive hub")
        self.research_office_button.clicked.connect(self.open_colony_hive_gui)
        self.research_office_button.hide()
        try:
            self.research_office_button.setStyleSheet(toggle_style)
        except Exception:
            pass

        self.code_companion_button = QPushButton("Code", self)
        self.code_companion_button.setGeometry(392, 184, 176, 34)
        self.code_companion_button.setToolTip("Open standalone ENGEL CODE COMPANION")
        self.code_companion_button.clicked.connect(self.open_code_companion)
        self.code_companion_button.hide()
        try:
            self.code_companion_button.setStyleSheet(toggle_style)
        except Exception:
            pass

        self.ai_plan_panel = self._build_ai_plan_panel(toggle_style)
        self.ai_body_panel = self._build_ai_body_panel(toggle_style)
        self.ai_receipt_viewer_panel = self._build_ai_receipt_viewer_panel(toggle_style)
        self.mobile_connection_panel = self._build_mobile_connection_panel(toggle_style)

        self._build_companion_open_layout()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(30)

        self.setup_tray()
        self.say_system("Engel is awake. Double-click me to talk. Drop approved files or folders onto me and I'll summarize them.")

    def _layout_companion_widgets(self):
        """Layout-managed expanded mode to avoid geometry collisions."""
        try:
            if not self.chat_open:
                return
            outer_margin = 14
            host_w = max(520, self.width() - (outer_margin * 2))
            host_h = max(480, self.height() - (outer_margin * 2))
            if hasattr(self, "_companion_open_host"):
                self._companion_open_host.setGeometry(outer_margin, outer_margin, host_w, host_h)
            if hasattr(self, "_companion_right_col"):
                right_width = min(320, max(290, int(host_w * 0.27)))
                self._companion_right_col.setFixedWidth(right_width)
            if hasattr(self, "alive_visual_badge"):
                try:
                    self.alive_visual_badge.hide()
                except Exception:
                    pass
        except Exception:
            pass

    def _companion_minimal_toggle_stylesheet(self):
        return (
            "QPushButton {"
            f"background: {COMPANION_BG_CARD_SUBTLE};"
            f"color: {COMPANION_TEXT_PRIMARY};"
            f"border: 1px solid {COMPANION_BORDER_SUBTLE};"
            "border-radius: 6px;"
            "padding: 4px 8px;"
            "font: 700 8pt 'Segoe UI';"
            "min-height: 22px;"
            "}"
            "QPushButton:hover {"
            f"border-color: {COMPANION_BORDER_FOCUS};"
            f"background: {COMPANION_BG_CARD};"
            "}"
            "QPushButton:checked {"
            f"color: {COMPANION_ACCENT_SAFE};"
            f"border-color: {COMPANION_ACCENT_SAFE};"
            "}"
            "QPushButton:disabled {"
            f"color: {COMPANION_BADGE_DISABLED};"
            f"border-color: {COMPANION_BADGE_DISABLED};"
            "}"
        )

    def _companion_minimal_open_host_stylesheet(self):
        return (
            "QFrame#CompanionOpenHost {"
            f"background: {COMPANION_BG_PRIMARY};"
            f"border: 1px solid {COMPANION_BORDER_SUBTLE};"
            "border-radius: 8px;"
            "}"
        )

    def _companion_minimal_right_col_stylesheet(self):
        return (
            "QWidget#CompanionRightCol {"
            f"background: {COMPANION_BG_PANEL};"
            f"border: 1px solid {COMPANION_BORDER_SUBTLE};"
            "border-radius: 7px;"
            "}"
        )

    def _companion_minimal_tab_stylesheet(self):
        return (
            "QTabWidget::pane {"
            f"border: 1px solid {COMPANION_BORDER_SUBTLE};"
            f"background: {COMPANION_BG_PANEL};"
            "border-radius: 6px;"
            "}"
            "QTabBar::tab {"
            f"background: {COMPANION_BG_CARD_SUBTLE};"
            f"color: {COMPANION_TEXT_MUTED};"
            f"border: 1px solid {COMPANION_BORDER_SUBTLE};"
            "border-bottom: 0;"
            "padding: 4px 8px;"
            "font: 700 8pt Consolas;"
            "border-top-left-radius: 5px;"
            "border-top-right-radius: 5px;"
            "}"
            "QTabBar::tab:selected {"
            f"color: {COMPANION_ACCENT_SAFE};"
            f"border-color: {COMPANION_BORDER_FOCUS};"
            f"background: {COMPANION_BG_PANEL};"
            "}"
            "QTabBar::tab:hover {"
            f"color: {COMPANION_TEXT_PRIMARY};"
            f"border-color: {COMPANION_BORDER_FOCUS};"
            "}"
        )

    def _companion_minimal_panel_stylesheet(self, object_name):
        return (
            f"QFrame#{object_name} {{"
            f"background: {COMPANION_BG_PANEL};"
            f"border: 1px solid {COMPANION_BORDER_SUBTLE};"
            "border-radius: 7px;"
            "}"
            "QLabel {"
            f"color: {COMPANION_TEXT_PRIMARY};"
            "background: transparent;"
            "border: 0;"
            "}"
            "QTextEdit, QTableWidget {"
            f"background: {COMPANION_BG_PRIMARY};"
            f"border: 1px solid {COMPANION_BORDER_SUBTLE};"
            "border-radius: 6px;"
            f"color: {COMPANION_TEXT_PRIMARY};"
            "padding: 6px;"
            "font: 9px 'Consolas';"
            "}"
            "QLineEdit {"
            f"background: {COMPANION_BG_PRIMARY};"
            f"border: 1px solid {COMPANION_BORDER_FOCUS};"
            "border-radius: 6px;"
            f"color: {COMPANION_TEXT_PRIMARY};"
            "padding: 6px;"
            "font: 9px 'Segoe UI';"
            "}"
            "QHeaderView::section {"
            f"background: {COMPANION_BG_CARD_SUBTLE};"
            f"color: {COMPANION_BADGE_WARNING};"
            "border: 0;"
            "padding: 4px;"
            "font: 800 8px 'Segoe UI';"
            "}"
        )

    def _compact_hive_status_value(self, value, limit=64):
        text = str(value or "unknown").replace("\n", " ").strip()
        if len(text) <= limit:
            return text
        return text[: max(0, limit - 3)].rstrip() + "..."

    def _format_hive_summary_status_text(self):
        if build_companion_hive_summary is None:
            return "\n".join([
                "Hive: unavailable",
                "Colonies: 0  |  Queens: 0  |  Workers: 0",
                "Communication: unavailable",
                "Guardian: unavailable",
                "Safe mode: REVIEW  |  Runtime: provider/network/workers off",
                "Source: local read-only snapshot",
            ])
        try:
            summary = build_companion_hive_summary(ROOT)
        except Exception as exc:
            summary = {
                "hive_available": False,
                "colony_count": 0,
                "queen_count": 0,
                "worker_count": 0,
                "communication_queen_status": "unavailable",
                "guardian_status": "unavailable",
                "mind_summary_safe_mode": False,
                "disabled_runtime_flags": [],
                "last_error": str(exc)[:120],
            }
        hive_state = "available" if summary.get("hive_available") else "unavailable"
        safe_mode = "ON" if summary.get("mind_summary_safe_mode") else "REVIEW"
        flags = summary.get("disabled_runtime_flags", [])
        runtime_bits = []
        if "provider_or_api_calls_enabled" in flags or not summary.get("provider_api_enabled", False):
            runtime_bits.append("provider off")
        if "internet_behavior_enabled" in flags or not summary.get("internet_enabled", False):
            runtime_bits.append("network off")
        if "background_worker_enabled" in flags or not summary.get("background_workers_enabled", False):
            runtime_bits.append("workers off")
        if "remote_queen_runtime_enabled" in flags:
            runtime_bits.append("remote off")
        runtime_text = "/".join(runtime_bits[:4]) if runtime_bits else "read-only"
        return "\n".join([
            "Hive: " + hive_state,
            "Colonies: " + str(summary.get("colony_count", 0))
            + "  |  Queens: " + str(summary.get("queen_count", 0))
            + "  |  Workers: " + str(summary.get("worker_count", 0)),
            "Communication: " + self._compact_hive_status_value(summary.get("communication_queen_status"), 52),
            "Guardian: " + self._compact_hive_status_value(summary.get("guardian_status"), 52),
            "Safe mode: " + safe_mode + "  |  Runtime: " + runtime_text,
            "Source: " + self._compact_hive_status_value(summary.get("source_trust", "local_readonly_snapshot"), 52),
        ])

    def _refresh_hive_summary_card(self):
        if hasattr(self, "hive_summary_status"):
            try:
                self.hive_summary_status.setText(self._format_hive_summary_status_text())
            except Exception:
                self.hive_summary_status.setText(
                    "Hive: unavailable\n"
                    "Colonies: 0  |  Queens: 0  |  Workers: 0\n"
                    "Communication: unavailable\n"
                    "Guardian: unavailable\n"
                    "Safe mode: REVIEW  |  Runtime: provider/network/workers off\n"
                    "Source: local read-only snapshot"
                )

    def _build_hive_summary_card(self):
        card = QFrame(self._companion_right_col)
        card.setObjectName("CompanionHiveStatusCard")
        card.setStyleSheet(
            "QFrame#CompanionHiveStatusCard {"
            f"background: {COMPANION_BG_CARD};"
            f"border: 1px solid {COMPANION_BORDER_FOCUS};"
            "border-radius: 6px;"
            "padding: 6px;"
            "}"
            "QLabel {"
            f"color: {COMPANION_TEXT_PRIMARY};"
            "background: transparent;"
            "border: 0;"
            "}"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(8, 7, 8, 7)
        layout.setSpacing(4)
        title = QLabel("HIVE STATUS", card)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"font: 800 9px 'Segoe UI'; color: {COMPANION_ACCENT_INFO};")
        layout.addWidget(title)
        self.hive_summary_status = QLabel(card)
        self.hive_summary_status.setObjectName("CompanionHiveSummaryStatus")
        self.hive_summary_status.setWordWrap(True)
        self.hive_summary_status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.hive_summary_status.setStyleSheet(
            f"font: 700 8px 'Consolas'; color: {COMPANION_TEXT_SECONDARY}; line-height: 120%;"
        )
        layout.addWidget(self.hive_summary_status)
        self._refresh_hive_summary_card()
        return card

    # ENGEL_LOCAL_LLM_AGENT_HYBRID_MODE_V1_START
    def _build_engel_voice_mode_panel(self):
        panel = QFrame(self)
        panel.setObjectName("EngelVoiceModeHybridPanel")
        panel.setStyleSheet(
            "QFrame#EngelVoiceModeHybridPanel {"
            f"background: {COMPANION_BG_CARD};"
            f"border: 1px solid {COMPANION_BORDER_SUBTLE};"
            "border-radius: 6px;"
            "padding: 6px;"
            "}"
            "QLabel {"
            f"color: {COMPANION_TEXT_PRIMARY};"
            "background: transparent;"
            "border: 0;"
            "}"
            "QComboBox {"
            f"background: {COMPANION_BG_PRIMARY};"
            f"color: {COMPANION_TEXT_PRIMARY};"
            f"border: 1px solid {COMPANION_BORDER_FOCUS};"
            "border-radius: 5px;"
            "padding: 4px 6px;"
            "font: 800 8px 'Segoe UI';"
            "}"
            "QComboBox::drop-down {"
            "border: 0;"
            "}"
        )
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 7, 8, 7)
        layout.setSpacing(5)

        title = QLabel("Engel Voice Mode", panel)
        title.setObjectName("EngelVoiceModeLabel")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"font: 900 9px 'Segoe UI'; color: {COMPANION_ACCENT_INFO};")
        layout.addWidget(title)

        self.engel_voice_mode_selector = QComboBox(panel)
        self.engel_voice_mode_selector.setObjectName("EngelVoiceModeSelector")
        self.engel_voice_mode_selector.addItems(["Local Engel", "Agent Relay", "Hybrid"])
        self.engel_voice_mode_selector.setToolTip(
            "Choose Local Engel, Agent Relay, or Hybrid. No online fallback is enabled."
        )
        self.engel_voice_mode_selector.currentTextChanged.connect(self._on_engel_voice_mode_changed)
        layout.addWidget(self.engel_voice_mode_selector)

        self.engel_voice_mode_status = QLabel(panel)
        self.engel_voice_mode_status.setObjectName("EngelVoiceModeStatus")
        self.engel_voice_mode_status.setWordWrap(True)
        self.engel_voice_mode_status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.engel_voice_mode_status.setStyleSheet(
            f"font: 700 8px 'Consolas'; color: {COMPANION_TEXT_SECONDARY}; line-height: 120%;"
        )
        layout.addWidget(self.engel_voice_mode_status)
        self._refresh_engel_voice_mode_status()
        return panel

    def _local_engel_runtime_status(self):
        try:
            import engel_offline_seed_llm as seed
            status = seed.offline_seed_llm_status_dict()
        except Exception:
            return "unavailable"
        if not status.get("env_gated_runtime_adapter_available", False):
            return "unavailable"
        if not status.get("model_file_present", False):
            return "unavailable"
        if not status.get("offline_llm_enabled", False):
            return "disabled"
        if status.get("provider_fallback_enabled", True):
            return "unavailable"
        return "available"

    def _agent_relay_status(self):
        try:
            agent_root = Path(core.ROOT) / "engel_agent_main"
            if agent_root.exists():
                return "idle"
        except Exception:
            pass
        return "unavailable"

    def _refresh_engel_voice_mode_status(self):
        mode = str(getattr(self, "engel_voice_mode", "Local Engel") or "Local Engel")
        local_runtime = self._local_engel_runtime_status()
        agent_relay = self._agent_relay_status()
        lines = [
            "Current voice: " + mode,
            "Local runtime: " + local_runtime,
            "Agent Relay: " + agent_relay,
            "Online fallback: OFF",
            "Command execution: OFF",
            "Trusted memory write: OFF",
            "Source mutation: OFF",
            "Agent output trust: untrusted until reviewed",
            "Local conversation output — commands require approval.",
            "Untrusted builder output — review before use.",
        ]
        if mode == "Agent Relay":
            lines.append("Agent Relay: builder/handoff mode, not local Engel mind.")
        elif mode == "Hybrid":
            lines.append("Hybrid handoff boundary: Send to Agent Relay / Keep Local / Cancel.")
            lines.append("Hybrid mode available as UI/status scaffold. Agent handoff requires separate implementation.")
        self.engel_voice_mode_status.setText("\n".join(lines))
        try:
            self.status_rail.setText("LOCAL · GUARDS ON · VOICE " + mode.upper() + " · FALLBACK OFF")
        except Exception:
            pass

    def _on_engel_voice_mode_changed(self, mode):
        self.engel_voice_mode = str(mode or "Local Engel")
        self._refresh_engel_voice_mode_status()

    def _local_engel_unavailable_blocker(self):
        return (
            "Local Engel is selected, but no approved local model runtime is active. "
            "I will not fall back to Agent Relay or online models.\n\n"
            "Online fallback: OFF\n"
            "Command execution: OFF\n"
            "Trusted memory write: OFF\n"
            "Source mutation: OFF"
        )

    def _run_local_engel_conversation(self, text):
        if self._local_engel_runtime_status() != "available":
            return self._local_engel_unavailable_blocker()
        try:
            import engel_offline_seed_llm as seed
            result = seed.run_offline_seed_llm_for_companion_chat(str(text or ""))
        except Exception as exc:
            return self._local_engel_unavailable_blocker() + "\n\nLocal runtime error: " + str(exc)
        body = getattr(result, "response", "") or ""
        if getattr(result, "guardian_blocked", False):
            body = "Guardian blocked unsafe local model output.\n\n" + body
        if getattr(result, "error", ""):
            body = (body + "\n\nLocal runtime note: " + str(getattr(result, "error", ""))).strip()
        if not body:
            body = "Local Engel returned no text."
        return "Local conversation output — commands require approval.\n\n" + body

    def _run_agent_relay_scaffold(self, text):
        _ = text
        return (
            "Agent Relay: builder/handoff mode, not local Engel mind.\n\n"
            "Untrusted builder output — review before use.\n\n"
            "Agent Relay is idle from this free-form chat lane. No Codex, Claude, browser, provider, "
            "or online fallback was called. Use an explicit approved handoff path for builder work.\n\n"
            "Command execution: OFF\n"
            "Trusted memory write: OFF\n"
            "Source mutation: OFF"
        )

    def _run_hybrid_conversation(self, text):
        local_text = self._run_local_engel_conversation(text)
        return (
            local_text
            + "\n\nHybrid mode available as UI/status scaffold. Agent handoff requires separate implementation.\n"
            + "Handoff boundary: Send to Agent Relay / Keep Local / Cancel.\n"
            + "Agent Relay output is untrusted builder output — review before use."
        )

    def _run_chat_for_current_voice_mode(self, text):
        mode = str(getattr(self, "engel_voice_mode", "Local Engel") or "Local Engel")
        if mode == "Agent Relay":
            return self._run_agent_relay_scaffold(text)
        if mode == "Hybrid":
            return self._run_hybrid_conversation(text)
        return self._run_local_engel_conversation(text)
    # ENGEL_LOCAL_LLM_AGENT_HYBRID_MODE_V1_END

    def _build_companion_open_layout(self):
        self._companion_open_host = QFrame(self)
        self._companion_open_host.setObjectName("CompanionOpenHost")
        self._companion_open_host.setStyleSheet(self._companion_minimal_open_host_stylesheet())
        self._companion_open_host.hide()

        root = QHBoxLayout(self._companion_open_host)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(10)

        left_col = QWidget(self._companion_open_host)
        left_layout = QVBoxLayout(left_col)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(7)
        left_layout.addWidget(self.dashboard_title)
        left_layout.addWidget(self.dashboard_subtitle)
        left_layout.addWidget(self.status_rail)
        left_layout.addWidget(self.engel_voice_mode_panel)
        left_layout.addWidget(self.chat, 1)
        left_layout.addWidget(self.input, 0)
        left_col.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._companion_right_col = QWidget(self._companion_open_host)
        self._companion_right_col.setObjectName("CompanionRightCol")
        self._companion_right_col.setStyleSheet(self._companion_minimal_right_col_stylesheet())
        right_layout = QVBoxLayout(self._companion_right_col)
        right_layout.setContentsMargins(7, 7, 7, 7)
        right_layout.setSpacing(7)
        if hasattr(self, "alive_state_visual_v2_label"):
            right_layout.addWidget(self.alive_state_visual_v2_label)
        right_layout.addWidget(self.overnight_toggle)
        right_layout.addWidget(self.research_office_button)
        self.hive_summary_card = self._build_hive_summary_card()
        right_layout.addWidget(self.hive_summary_card)
        right_layout.addWidget(self.code_companion_button)
        self.ai_audit_tabs = QTabWidget(self._companion_right_col)
        self.ai_audit_tabs.setObjectName("AIAuditTabs")
        self.ai_audit_tabs.setStyleSheet(self._companion_minimal_tab_stylesheet())
        self.ai_audit_tabs.addTab(self.ai_plan_panel, "PLAN")
        self.ai_audit_tabs.addTab(self.ai_body_panel, "BODY")
        self.ai_audit_tabs.addTab(self.ai_receipt_viewer_panel, "RECEIPTS")
        self.ai_audit_tabs.addTab(self.mobile_connection_panel, "MOBILE")
        self.ai_audit_tabs.tabBar().setUsesScrollButtons(True)
        right_layout.addWidget(self.ai_audit_tabs, 1)
        if hasattr(self, "alive_state_visual_v2_sub"):
            right_layout.addWidget(self.alive_state_visual_v2_sub)
        right_layout.addStretch(1)
        self._companion_right_col.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self._companion_right_col.setFixedWidth(300)

        root.addWidget(left_col, 1)
        root.addWidget(self._companion_right_col, 0)

    # ENGEL_AI_GROWTH_GUI_TABS_V1_COMPANION_START
    def _render_ai_growth_gui_memory_promotion_status(self):
        lines = [
            "Engel Memory Promotion",
            "",
            "Approved memory promotion contract and writer status:",
            *[f"- {status}" for status in memory_promotion_writer.WRITER_STATUS],
            "",
            "Approval boundary:",
            f"- approval token required: {memory_promotion_writer.APPROVAL_TOKEN}",
            f"- trusted memory target status: {memory_promotion_writer.TRUSTED_MEMORY_TARGET_STATUS}",
            f"- trusted memory target: {memory_promotion_writer.TRUSTED_MEMORY_TARGET}",
            "- no automatic memory promotion",
            "- no trusted memory write button in this GUI tab",
            "- no source mutation button in this GUI tab",
            "",
            "Writer safety boundary:",
            *[f"- {item}" for item in memory_promotion_writer.BOUNDARY_TEXT],
            "",
            "GUI safety labels:",
            *[f"- {label}" for label in AI_GROWTH_GUI_STATUS_LABELS],
        ]
        return "\n".join(lines) + "\n"

    def _render_ai_growth_gui_low_risk_self_fix_dry_run_visibility(self):
        names = self_fix_receipt_viewer.list_receipt_names()
        last_receipt_lines = ["- no self-fix receipts found"]
        if names:
            last_name = names[-1]
            try:
                receipt_path = self_fix_receipt_viewer.resolve_receipt_path(last_name)
                receipt_text = receipt_path.read_text(encoding="utf-8", errors="replace")
                sections = self_fix_receipt_viewer.parse_receipt_sections(receipt_text)
                last_receipt_lines = [
                    f"- file: {last_name}",
                    f"- self_fix_run_id: {sections.get('self_fix_run_id', '(not present)')}",
                    f"- issue_detected: {sections.get('issue_detected', '(not present)')}",
                    f"- mode: {sections.get('mode', '(not present)')}",
                    f"- stopped: {sections.get('stopped', '(not present)')}",
                    f"- stop_reason: {sections.get('stop_reason', '(not present)')}",
                ]
            except Exception as exc:
                last_receipt_lines = [
                    f"- latest receipt could not be summarized: {last_name}",
                    f"- read-only error: {exc}",
                ]

        lines = [
            "Engel Low-Risk Self-Fix GUI Dry-Run Visibility",
            "",
            "GUI labels:",
            "- DRY RUN VISIBILITY ONLY",
            "- READ ONLY",
            "- LOW RISK ONLY",
            "- HIGH RISK STOPS",
            "- NO APPLY BUTTON",
            "- NO PACKAGE REFRESH",
            "- NO TRUSTED MEMORY WRITE",
            "- NO PROVIDER NETWORK BROWSER",
            "- NO BACKGROUND WORKER",
            "",
            "Low-risk self-fix runner status:",
            *[f"- {status}" for status in low_risk_self_fix_status_surface.RUNNER_STATUS],
            "",
            "Implemented V2 low-risk classes visible here:",
            *[f"- {class_name}" for class_name in low_risk_self_fix_status_surface.IMPLEMENTED_V1_CLASSES],
            "",
            "Future/dry-run-only classes visible here:",
            *[f"- {class_name}" for class_name in low_risk_self_fix_status_surface.FUTURE_LOW_RISK_CLASSES],
            "",
            "High-risk stop classes:",
            *[f"- {class_name}" for class_name in low_risk_self_fix_status_surface.HIGH_RISK_STOP_CLASSES],
            "",
            "Receipt status:",
            "- receipt folder: reports\\self_fix_receipts\\",
            f"- receipt count: {low_risk_self_fix_status_surface.receipt_count()}",
            "- last receipt summary if available:",
            *last_receipt_lines,
            "",
            "Dry-run boundary:",
            "- this GUI tab shows what Engel could safely check; it does not run dry-run commands.",
            "- dry-run remains an explicit CLI action outside this GUI surface.",
            "- no apply button exists in this GUI step.",
            "- no self-fix apply action exists in this GUI step.",
            "",
            "Verification-before-commit boundary:",
            "- verification-before-commit boundary is active in the low-risk runner contract.",
            "- this GUI does not commit changes.",
            "- this GUI does not write receipts.",
            "",
            "Safety boundary:",
            "- no high-risk behavior",
            "- no package refresh action",
            "- no provider/network/browser behavior",
            "- no model runtime",
            "- no trusted memory write",
            "- no route/startup mutation",
            "- no background worker",
            "",
            "Report paths:",
            "- reports\\codex_bridge\\ENGEL_LOW_RISK_SELF_FIX_STATUS_SURFACE_V1.md",
            "- reports\\codex_bridge\\ENGEL_LOW_RISK_SELF_FIX_RUNNER_V2.md (expected Core Continuity slot; may be absent)",
            "- reports\\codex_bridge\\ENGEL_AI_GROWTH_GUI_TABS_V1.md",
        ]
        return "\n".join(lines) + "\n"

    def _render_global_password_action_status(self):
        gate = global_password_gate.global_password_gate_status()
        registry = protected_action_registry.registry_summary()
        actions = protected_action_registry.list_actions()
        engel_ai_actions = [str(action["action_id"]) for action in actions if action.get("category") == "Engel AI / Learning"]
        code_companion_actions = [str(action["action_id"]) for action in actions if action.get("category") == "Code Companion"]
        blocked_actions = [str(action["action_id"]) for action in actions if action.get("risk_level") == "blocked"]
        configured = "CONFIGURED" if gate.get("configured") else "NOT CONFIGURED"
        lines = [
            "Engel Global Password-Gated Action Layer V1",
            "",
            "Global Password Gate Status",
            "GLOBAL PASSWORD GATE",
            f"- configured: {configured}",
            "- password storage: hash metadata only",
            "- setup command: python engel_global_password_gate.py --setup",
            "- verify command: python engel_global_password_gate.py --verify",
            "- change command: python engel_global_password_gate.py --change",
            "- CLI-only password setup/verify/change in V1",
            "",
            "Human Testing Panel:",
            "- HUMAN TESTING READY",
            "- PASSWORD REQUIRED FOR PROTECTED ACTIONS",
            "- LOCAL ONLY",
            "- HASH ONLY",
            "- NO PLAINTEXT PASSWORD",
            "- STRICT ACTION ALLOWLIST",
            "- BLOCKED ACTIONS REMAIN BLOCKED",
            "- CONTRACTS STILL REQUIRED",
            "- VERIFIERS STILL REQUIRED",
            "- AUTHORITY STILL REQUIRED",
            "- GUARDS STILL REQUIRED",
            "- Human testing is allowed for local password setup/status/verify and protected action visibility.",
            "- Protected non-research write/apply/run actions still require password plus action-specific contracts.",
            "- Blocked actions remain blocked even with password.",
            "- Password does not bypass contracts, verifiers, guards, or authority hierarchy.",
            "",
            "Protected Action Registry Summary:",
            f"- view-only: {gate['view_only_count']}",
            f"- low-risk gated: {gate['low_risk_gated_count']}",
            f"- medium-risk gated: {gate['medium_risk_gated_count']}",
            f"- high-risk gated: {gate['high_risk_gated_count']}",
            f"- blocked: {gate['blocked_count']}",
            f"- total registered actions: {registry['action_count']}",
            "",
            "Safe Test Commands:",
            "- python engel_global_password_gate.py --status",
            "- python engel_global_password_gate.py --setup",
            "- python engel_global_password_gate.py --verify",
            "- python engel_protected_action_registry.py --list",
            "- python engel_protected_action_registry.py --show run_code_companion_low_risk_patch_apply",
            "- python engel_protected_action_registry.py --show promote_memory_candidate",
            "",
            "Safe Refusal Tests:",
            "- protected apply/write commands refuse without password gate",
            "- protected apply/write commands refuse without --password-prompt",
            "- blocked actions remain blocked",
            "- blocked actions show a blocked reason and require a future explicit contract before they can change state",
            "",
            "Engel AI protected actions:",
            *[f"- {action_id}" for action_id in engel_ai_actions],
            "",
            "Code Companion protected actions:",
            *[f"- {action_id}" for action_id in code_companion_actions],
            "",
            "Blocked actions:",
            *[f"- {action_id}" for action_id in blocked_actions],
            "",
            "Safety:",
            "- Password protects actions; it does not bypass safety.",
            "- Password does not approve high-risk actions by itself.",
            "- Contracts, verifiers, receipts, and authority hierarchy still apply.",
            "- Blocked actions remain blocked even with password.",
            "- Action IDs use strict allowlists and canonicalization.",
            "- SQL-injection-style, Unicode, encoding, whitespace, and prompt-injection bypass attempts are rejected.",
            "",
            "GUI boundary:",
            "- status only",
            "- no protected action execution from this panel",
            "- no provider/network/browser/model runtime",
            "- no background worker",
            "- no startup autorun",
            "",
            "Research Toggle Overnight Worker:",
            research_toggle_status.render_status().rstrip(),
        ]
        return "\n".join(lines) + "\n"

    def _render_ai_growth_gui_tab_text(self, tab_name):
        try:
            if tab_name == "AI Growth":
                return ai_growth_dashboard.render_dashboard()
            if tab_name == "Self-Learning":
                return self_learning_status_surface.render_status_surface()
            if tab_name == "Candidate Review":
                return candidate_review_dashboard.render_dashboard()
            if tab_name == "Code Companion Review":
                return (
                    code_companion_candidate_review_status.render_status()
                    + "\n\n"
                    + code_companion_patch_status_surface.render_status()
                )
            if tab_name == "Global Safety":
                return self._render_global_password_action_status()
            if tab_name == "System Integration":
                return system_integration_status.render_status()
            if tab_name == "Self-Fix":
                return (
                    self._render_ai_growth_gui_low_risk_self_fix_dry_run_visibility()
                    + "\n\n"
                    + low_risk_self_fix_status_surface.render_status()
                    + "\n\n"
                    + self_fix_receipt_viewer.render_receipt_list()
                )
            if tab_name == "Memory Promotion":
                return self._render_ai_growth_gui_memory_promotion_status()
            if tab_name == "Research-to-Fix":
                return research_to_fix_loop.render_status()
        except Exception as exc:
            return (
                "Engel AI growth status tab could not render local status text.\n\n"
                f"Tab: {tab_name}\n"
                f"Error: {exc}\n\n"
                "READ_ONLY_VIEW\n"
                "NO_ACTION_EXECUTION\n"
                "NO_MEMORY_WRITE\n"
                "NO_SOURCE_MUTATION\n"
                "NO_PROVIDER_CALLS\n"
                "NO_NETWORK\n"
                "NO_BROWSER\n"
                "NO_BACKGROUND_WORKER\n"
            )
        return "Unknown Engel AI growth status tab.\nREAD_ONLY_VIEW\nNO_ACTION_EXECUTION\n"

    def _build_ai_growth_combo_panel(self):
        """Single GROWTH tab replacing 9 separate status tabs.
        Dropdown selects which read-only status surface to display.
        """
        from PySide6.QtWidgets import QComboBox

        panel = QFrame(self)
        panel.setObjectName("AIGrowthGuiStatusPanel")
        panel.setMinimumWidth(280)
        panel.setStyleSheet(
            "QFrame#AIGrowthGuiStatusPanel { background: #0a0a0a; "
            "border: 1px solid #333333; border-radius: 0px; } "
            "QTextEdit { background: #0a0a0a; border: 1px solid #333333; "
            "color: #cccccc; padding: 6px; font: 9pt Consolas; } "
            "QComboBox { background: #111111; color: #00ff88; "
            "border: 1px solid #333333; padding: 3px 6px; font: 700 9pt Consolas; }"
        )
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        self._ai_growth_selector = QComboBox(panel)
        self._ai_growth_selector.addItems(AI_GROWTH_GUI_TAB_NAMES)
        self._ai_growth_selector.currentTextChanged.connect(self._refresh_ai_growth_status)
        layout.addWidget(self._ai_growth_selector)

        self._ai_growth_status_text = QTextEdit(panel)
        self._ai_growth_status_text.setReadOnly(True)
        self._ai_growth_status_text.setMinimumHeight(300)
        self._ai_growth_status_text.setLineWrapMode(QTextEdit.WidgetWidth)
        layout.addWidget(self._ai_growth_status_text, 1)
        self._refresh_ai_growth_status(self._ai_growth_selector.currentText())
        return panel

    def _refresh_ai_growth_status(self, tab_name):
        if hasattr(self, "_ai_growth_status_text"):
            self._ai_growth_status_text.setPlainText(self._render_ai_growth_gui_tab_text(tab_name))
    # ENGEL_AI_GROWTH_GUI_TABS_V1_COMPANION_END

    # ENGEL_MOBILE_CONNECTION_COMPANION_READONLY_TAB_V1_PANEL_START
    def _mobile_readonly_item(self, text):
        item = QTableWidgetItem(str(text or ""))
        try:
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        except Exception:
            pass
        return item

    def _mobile_doc_status_item(self, relative_path):
        path = Path(ROOT) / str(relative_path)
        if not path.exists():
            return "Missing"
        try:
            modified = time.strftime("%Y-%m-%d %H:%M", time.localtime(path.stat().st_mtime))
            return "Found / " + modified
        except Exception:
            return "Found"

    def _add_mobile_section(self, layout, parent, title, body):
        section = QFrame(parent)
        section.setObjectName("MobileConnectionSection")
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(7, 6, 7, 6)
        section_layout.setSpacing(4)

        title_label = QLabel(title, section)
        title_label.setWordWrap(True)
        title_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        title_label.setStyleSheet("font: 800 9px 'Segoe UI'; color: #5bc8ff;")
        section_layout.addWidget(title_label)

        body_label = QLabel(body, section)
        body_label.setWordWrap(True)
        body_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        body_label.setStyleSheet("font: 8px 'Segoe UI'; color: #8ab8d8;")
        section_layout.addWidget(body_label)

        layout.addWidget(section)
        return section

    def _build_mobile_connection_panel(self, button_style):
        panel = QFrame(self)
        panel.setObjectName("MobileConnectionReadOnlyPanel")
        panel.setMinimumWidth(280)
        panel.setStyleSheet(
            """
            QFrame#MobileConnectionReadOnlyPanel {
                background: rgba(1, 5, 16, 220);
                border: 1px solid rgba(212, 168, 32, 70);
                border-radius: 8px;
            }
            QFrame#MobileConnectionSection {
                background: rgba(2, 8, 22, 160);
                border: 1px solid rgba(91, 200, 255, 50);
                border-radius: 6px;
            }
            QLabel {
                color: rgba(232, 244, 255, 245);
                background: transparent;
                border: 0;
            }
            QPushButton {
                background: rgba(2, 8, 22, 180);
                color: rgba(138, 184, 216, 220);
                border: 1px solid rgba(91, 200, 255, 60);
                border-radius: 5px;
                padding: 4px;
                font: 700 8px 'Segoe UI';
            }
            QPushButton:disabled {
                color: rgba(100, 140, 165, 140);
                border-color: rgba(91, 200, 255, 35);
                background: rgba(1, 5, 16, 160);
            }
            QTableWidget {
                background: rgba(0, 0, 0, 130);
                border: 1px solid rgba(91, 200, 255, 55);
                border-radius: 6px;
                color: rgba(232, 244, 255, 245);
                font: 8px 'Consolas';
            }
            QHeaderView::section {
                background: rgba(2, 8, 22, 240);
                color: rgba(212, 168, 32, 230);
                border: 0;
                padding: 4px;
                font: 800 8px 'Segoe UI';
            }
            QScrollArea {
                border: 0;
                background: transparent;
            }
            """
        )

        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(9, 8, 9, 8)
        panel_layout.setSpacing(6)

        title = QLabel("Engel Mobile Connection", panel)
        title.setAlignment(Qt.AlignCenter)
        title.setTextInteractionFlags(Qt.TextSelectableByMouse)
        title.setStyleSheet("font: 800 10px 'Segoe UI'; color: #5bc8ff; letter-spacing: 1px;")
        panel_layout.addWidget(title)

        status = QLabel("Contract installed; runtime not enabled", panel)
        status.setAlignment(Qt.AlignCenter)
        status.setWordWrap(True)
        status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        status.setStyleSheet(
            "background: rgba(2, 8, 22, 180); border: 1px solid rgba(212, 168, 32, 110); "
            "border-radius: 5px; color: rgba(212, 168, 32, 235); font: 800 8px 'Segoe UI'; padding: 5px;"
        )
        panel_layout.addWidget(status)

        badge_text = (
            "Mobile: Planned  |  Runtime: Disabled  |  Networking: Not implemented  |  "
            "Pairing: Not implemented  |  Packets: Untrusted  |  Commands: Blocked  |  "
            "Human approval: Required  |  Engel Remote Workers: Blocked"
        )
        badges = QLabel(badge_text, panel)
        badges.setWordWrap(True)
        badges.setAlignment(Qt.AlignCenter)
        badges.setTextInteractionFlags(Qt.TextSelectableByMouse)
        badges.setStyleSheet(
            "background: rgba(2, 8, 22, 180); border: 1px solid rgba(91, 200, 255, 50); "
            "border-radius: 5px; color: #8ab8d8; font: 700 7px 'Segoe UI'; padding: 5px;"
        )
        panel_layout.addWidget(badges)

        scroll = QScrollArea(panel)
        scroll.setWidgetResizable(True)
        scroll_content = QWidget(scroll)
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(7)

        self._add_mobile_section(
            scroll_layout,
            scroll_content,
            "Mobile Overview",
            "Mobile is a first-class Engel pillar. Current state is read-only display only. "
            "No mobile runtime, networking, or pairing is enabled.",
        )

        self._add_mobile_section(
            scroll_layout,
            scroll_content,
            "Safety Boundaries",
            "Mobile packets are untrusted.\n"
            "Mobile cannot directly write trusted memory.\n"
            "Mobile cannot directly edit source.\n"
            "Mobile cannot directly mutate queues/routes.\n"
            "Mobile cannot trigger autonomy.\n"
            "Mobile cannot execute commands.\n"
            "Mobile cannot activate Engel Remote Workers.\n"
            "Human approval is required before any trusted action.",
        )

        packet_lines = [
            packet + " - Untrusted / Planned / Non-actioning"
            for packet in MOBILE_CONNECTION_PACKET_TYPES
        ]
        self._add_mobile_section(
            scroll_layout,
            scroll_content,
            "Planned Packet Types",
            "\n".join(packet_lines),
        )

        metrics = [
            "paired_devices_count: 0",
            "pending_mobile_packets_count: 0",
            "pending_mobile_requests_count: 0",
            "pending_mobile_approval_requests_count: 0",
            "mobile_runtime_enabled: false",
            "mobile_networking_enabled: false",
            "mobile_pairing_enabled: false",
            "remote_queen_mobile_handoff_enabled: false",
        ]
        self._add_mobile_section(
            scroll_layout,
            scroll_content,
            "Display-only Metrics",
            "\n".join(metrics),
        )

        self._add_mobile_section(
            scroll_layout,
            scroll_content,
            "Empty Inbox / Requests",
            "No mobile inbox is active. No mobile packets are being received. "
            "This is expected because networking, pairing, and runtime are not implemented.",
        )

        self._add_mobile_section(
            scroll_layout,
            scroll_content,
            "Receipts & Reports Placeholder",
            "Future mobile-visible receipts and reports will follow the existing receipt/report review pattern. "
            "Current tab does not create, modify, delete, trust, or execute receipts.",
        )

        self._add_mobile_section(
            scroll_layout,
            scroll_content,
            "Engel Remote Worker Handoff Placeholder",
            "Mobile-to-Engel-Remote-Worker handoff is planned only. "
            "Mobile cannot activate Engel Remote Workers or assign Engel Remote Worker work.",
        )

        actions_section = self._add_mobile_section(
            scroll_layout,
            scroll_content,
            "Future Disabled Actions",
            "Planned/not enabled. This read-only Mobile tab does not execute actions.",
        )
        actions_layout = actions_section.layout()
        for action in MOBILE_CONNECTION_DISABLED_ACTIONS:
            button = QPushButton(action, actions_section)
            button.setEnabled(False)
            actions_layout.addWidget(button)

        docs_section = self._add_mobile_section(
            scroll_layout,
            scroll_content,
            "Local Documents / Contracts",
            "Approved local docs/config presence only. No arbitrary path expansion, folder browsing, network links, or file execution.",
        )
        docs_layout = docs_section.layout()
        self.mobile_docs_table = QTableWidget(docs_section)
        self.mobile_docs_table.setColumnCount(3)
        self.mobile_docs_table.setHorizontalHeaderLabels(["File", "Status", "Description"])
        self.mobile_docs_table.setRowCount(len(MOBILE_CONNECTION_APPROVED_DOCS))
        self.mobile_docs_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.mobile_docs_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.mobile_docs_table.verticalHeader().setVisible(False)
        self.mobile_docs_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.mobile_docs_table.setMinimumHeight(190)
        self.mobile_docs_table.setWordWrap(True)
        for row, (relative_path, description) in enumerate(MOBILE_CONNECTION_APPROVED_DOCS):
            self.mobile_docs_table.setItem(row, 0, self._mobile_readonly_item(Path(relative_path).name))
            self.mobile_docs_table.setItem(row, 1, self._mobile_readonly_item(self._mobile_doc_status_item(relative_path)))
            self.mobile_docs_table.setItem(row, 2, self._mobile_readonly_item(description))
        docs_layout.addWidget(self.mobile_docs_table)

        scroll_layout.addStretch(1)
        scroll.setWidget(scroll_content)
        panel_layout.addWidget(scroll, 1)
        return panel
    # ENGEL_MOBILE_CONNECTION_COMPANION_READONLY_TAB_V1_PANEL_END

    # ENGEL_AI_BODY_COMPANION_PANEL_START
    def _add_ai_body_card(self, grid, parent, card, index):
        frame = QFrame(parent)
        frame.setObjectName("AIBodyOrganCard")
        frame.setMinimumHeight(160)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(8, 7, 8, 7)
        frame_layout.setSpacing(4)

        title = QLabel(str(card.get("name", "")), frame)
        title.setWordWrap(True)
        title.setTextInteractionFlags(Qt.TextSelectableByMouse)
        title.setStyleSheet("font: 900 9px 'Segoe UI'; color: #5bc8ff;")
        frame_layout.addWidget(title)

        purpose = QLabel(str(card.get("purpose", "")), frame)
        purpose.setWordWrap(True)
        purpose.setTextInteractionFlags(Qt.TextSelectableByMouse)
        purpose.setStyleSheet("font: 700 8px 'Segoe UI'; color: #8ab8d8;")
        frame_layout.addWidget(purpose)

        status = QLabel(str(card.get("status", "READ_ONLY")), frame)
        status.setWordWrap(True)
        status.setAlignment(Qt.AlignCenter)
        status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        status.setStyleSheet(
            "background: rgba(2, 8, 22, 180); border: 1px solid rgba(212, 168, 32, 110); "
            "border-radius: 5px; color: rgba(212, 168, 32, 235); font: 900 8px 'Segoe UI'; padding: 4px;"
        )
        frame_layout.addWidget(status)

        indicators = [str(item) for item in card.get("health_indicators", card.get("badges", []))[:3]]
        if indicators:
            health = QLabel("  |  ".join(indicators), frame)
            health.setWordWrap(True)
            health.setAlignment(Qt.AlignCenter)
            health.setTextInteractionFlags(Qt.TextSelectableByMouse)
            health.setStyleSheet(
                "background: rgba(91, 200, 255, 18); border: 1px solid rgba(91, 200, 255, 70); "
                "border-radius: 5px; color: #5bc8ff; font: 900 7px 'Segoe UI'; padding: 3px;"
            )
            frame_layout.addWidget(health)

        modules = QLabel("\n".join(str(item) for item in card.get("mapped_modules", [])), frame)
        modules.setWordWrap(True)
        modules.setTextInteractionFlags(Qt.TextSelectableByMouse)
        modules.setStyleSheet("font: 8px 'Consolas'; color: #e8f4ff;")
        frame_layout.addWidget(modules)

        safety = QLabel("Safety: " + str(card.get("safety_boundary", "")), frame)
        safety.setWordWrap(True)
        safety.setTextInteractionFlags(Qt.TextSelectableByMouse)
        safety.setStyleSheet("font: 700 7px 'Segoe UI'; color: rgba(212, 168, 32, 220);")
        frame_layout.addWidget(safety)
        frame_layout.addStretch(1)

        grid.addWidget(frame, index, 0)
        return frame

    def _add_markdown_knowledge_card(self, grid, parent, summary):
        frame = QFrame(parent)
        frame.setObjectName("AIBodyOrganCard")
        frame.setMinimumHeight(110)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(8, 7, 8, 7)
        frame_layout.setSpacing(4)

        title = QLabel("MARKDOWN KNOWLEDGE", frame)
        title.setWordWrap(True)
        title.setTextInteractionFlags(Qt.TextSelectableByMouse)
        title.setStyleSheet("font: 900 9px 'Segoe UI'; color: #5bc8ff;")
        frame_layout.addWidget(title)

        markdown_badges = summary.get(
            "badges",
            ["DOCUMENTATION ONLY", "FLUID MAP", "NOT AUTOMATIC AUTHORITY", "NO EXECUTION", "NO FILE MOVES"],
        )
        badges = QLabel("  |  ".join(str(item) for item in markdown_badges), frame)
        badges.setWordWrap(True)
        badges.setAlignment(Qt.AlignCenter)
        badges.setTextInteractionFlags(Qt.TextSelectableByMouse)
        badges.setStyleSheet(
            "background: rgba(91, 200, 255, 18); border: 1px solid rgba(91, 200, 255, 70); "
            "border-radius: 5px; color: #5bc8ff; font: 900 7px 'Segoe UI'; padding: 3px;"
        )
        frame_layout.addWidget(badges)

        details = QLabel(
            "Files found: " + str(summary.get("files_found", "UNKNOWN")) + "  |  "
            "Indexed: " + str(summary.get("indexed", "UNKNOWN")) + "\n"
            "Summarized/excluded: " + str(summary.get("summarized_excluded", "UNKNOWN")) + "  |  "
            "Critical files: " + str(summary.get("critical_files", "UNKNOWN")) + "\n"
            "Unknown / Needs Review: " + str(summary.get("unknown_needs_review", "UNKNOWN")) + "  |  "
            "JSON companion: " + str(summary.get("json_companion", "UNKNOWN")) + "\n"
            "Status: " + str(summary.get("status", "INDEX UNAVAILABLE")) + "\n"
            "Authority: " + str(summary.get("authority", "context, not automatic authority")),
            frame,
        )
        details.setWordWrap(True)
        details.setTextInteractionFlags(Qt.TextSelectableByMouse)
        details.setStyleSheet("font: 800 8px 'Segoe UI'; color: #e8f4ff;")
        frame_layout.addWidget(details)

        boundary = QLabel("Safety: " + str(summary.get("safety_boundary", "")), frame)
        boundary.setWordWrap(True)
        boundary.setTextInteractionFlags(Qt.TextSelectableByMouse)
        boundary.setStyleSheet("font: 700 7px 'Segoe UI'; color: rgba(212, 168, 32, 220);")
        frame_layout.addWidget(boundary)

        grid.addWidget(frame, 0, 0)
        return frame

    def _add_file_structure_card(self, grid, parent, summary):
        frame = QFrame(parent)
        frame.setObjectName("AIBodyOrganCard")
        frame.setMinimumHeight(120)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(8, 7, 8, 7)
        frame_layout.setSpacing(4)

        title = QLabel("FILE STRUCTURE", frame)
        title.setWordWrap(True)
        title.setTextInteractionFlags(Qt.TextSelectableByMouse)
        title.setStyleSheet("font: 900 9px 'Segoe UI'; color: #5bc8ff;")
        frame_layout.addWidget(title)

        structure_badges = summary.get(
            "badges",
            ["PLAN ONLY", "NO FILE MOVES", "JOSH APPROVAL REQUIRED"],
        )
        badges = QLabel("  |  ".join(str(item) for item in structure_badges), frame)
        badges.setWordWrap(True)
        badges.setAlignment(Qt.AlignCenter)
        badges.setTextInteractionFlags(Qt.TextSelectableByMouse)
        badges.setStyleSheet(
            "background: rgba(2, 8, 22, 180); border: 1px solid rgba(212, 168, 32, 100); "
            "border-radius: 5px; color: rgba(212, 168, 32, 230); font: 900 7px 'Segoe UI'; padding: 3px;"
        )
        frame_layout.addWidget(badges)

        details = QLabel(
            "Current layout: " + str(summary.get("current_layout", "UNKNOWN")) + "  |  "
            "Future layout: " + str(summary.get("future_layout", "UNKNOWN")) + "\n"
            "Migration status: " + str(summary.get("migration_status", "UNKNOWN")) + "  |  "
            "Next slice: " + str(summary.get("next_slice", "UNKNOWN")) + "\n"
            "Policy: " + str(summary.get("policy", "JOSH-APPROVED SLICES ONLY")) + "\n"
            "Live imports changed: " + str(summary.get("live_imports_changed", "UNKNOWN")) + "  |  "
            "Files moved/renamed: " + str(summary.get("files_moved_renamed", "UNKNOWN")) + "  |  "
            "Packaging required: " + str(summary.get("packaging_required", "UNKNOWN")) + "\n"
            "Status: " + str(summary.get("status", "PLAN UNAVAILABLE")) + "  |  "
            "JSON companion: " + str(summary.get("json_companion", "UNKNOWN")),
            frame,
        )
        details.setWordWrap(True)
        details.setTextInteractionFlags(Qt.TextSelectableByMouse)
        details.setStyleSheet("font: 800 8px 'Segoe UI'; color: #e8f4ff;")
        frame_layout.addWidget(details)

        boundary = QLabel("Safety: " + str(summary.get("safety_boundary", "")), frame)
        boundary.setWordWrap(True)
        boundary.setTextInteractionFlags(Qt.TextSelectableByMouse)
        boundary.setStyleSheet("font: 700 7px 'Segoe UI'; color: rgba(212, 168, 32, 220);")
        frame_layout.addWidget(boundary)

        grid.addWidget(frame, 1, 0)
        return frame

    def _add_code_companion_card(self, grid, parent, summary):
        frame = QFrame(parent)
        frame.setObjectName("AIBodyOrganCard")
        frame.setMinimumHeight(140)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(8, 7, 8, 7)
        frame_layout.setSpacing(4)

        title = QLabel("CODE COMPANION", frame)
        title.setWordWrap(True)
        title.setTextInteractionFlags(Qt.TextSelectableByMouse)
        title.setStyleSheet("font: 900 9px 'Segoe UI'; color: #5bc8ff;")
        frame_layout.addWidget(title)

        code_badges = summary.get(
            "badges",
            [
                "SCRIPT CREATOR",
                "PRODUCT TEMPLATES",
                "PY / JAVA / HTML",
                "READ ONLY PREVIEW",
                "APPROVAL GATED",
            ],
        )
        badges = QLabel("  |  ".join(str(item) for item in code_badges), frame)
        badges.setWordWrap(True)
        badges.setAlignment(Qt.AlignCenter)
        badges.setTextInteractionFlags(Qt.TextSelectableByMouse)
        badges.setStyleSheet(
            "background: rgba(91, 200, 255, 18); border: 1px solid rgba(91, 200, 255, 70); "
            "border-radius: 5px; color: #5bc8ff; font: 900 7px 'Segoe UI'; padding: 3px;"
        )
        frame_layout.addWidget(badges)

        details = QLabel(
            "Script creator: " + str(summary.get("script_creator", "Python / Java / HTML")) + "\n"
            "Product templates: "
            + str(summary.get("product_templates", "Python CLI, Python GUI, Java Console, HTML Dashboard, HTML Mini App"))
            + "\n"
            "Products root: " + str(summary.get("products_root", "products\\")) + "  |  "
            "Examples root: " + str(summary.get("examples_root", summary.get("save_root", "examples\\code_companion"))) + "\n"
            "Product preview: " + str(summary.get("product_preview", "read-only")) + "  |  "
            "Open folder: " + str(summary.get("open_folder", "user-clicked / bounded to products\\")) + "\n"
            "Runtime source edits: " + str(summary.get("runtime_source_edits", "BLOCKED")) + "  |  "
            "Apply to Engel: " + str(summary.get("apply_to_engel", summary.get("apply", "NOT ENABLED"))) + "\n"
            "Overwrite: " + str(summary.get("overwrite", "APPROVE_CHANGE required")) + "\n"
            "Python validation: " + str(summary.get("python_validation", "ast / py_compile")) + "\n"
            "Java toolchain: " + str(summary.get("java_toolchain", "proposal-only unless present")) + "\n"
            "HTML: " + str(summary.get("html", "local-only / no remote deps")) + "\n"
            "Dependencies: " + str(summary.get("dependencies", "APPROVE_INSTALL required")) + "\n"
            "Status: " + str(summary.get("status", "SCRIPT CREATOR / PRODUCT TEMPLATES / PRODUCT ONLY")),
            frame,
        )
        details.setWordWrap(True)
        details.setTextInteractionFlags(Qt.TextSelectableByMouse)
        details.setStyleSheet("font: 800 8px 'Segoe UI'; color: #e8f4ff;")
        frame_layout.addWidget(details)

        boundary = QLabel("Safety: " + str(summary.get("safety_boundary", "")), frame)
        boundary.setWordWrap(True)
        boundary.setTextInteractionFlags(Qt.TextSelectableByMouse)
        boundary.setStyleSheet("font: 700 7px 'Segoe UI'; color: rgba(212, 168, 32, 220);")
        frame_layout.addWidget(boundary)

        grid.addWidget(frame, 2, 0)
        return frame

    def _add_core_v1_dashboard_card(self, grid, parent, summary):
        frame = QFrame(parent)
        frame.setObjectName("AIBodyOrganCard")
        frame.setMinimumHeight(110)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(8, 7, 8, 7)
        frame_layout.setSpacing(4)

        title = QLabel("ENGEL CORE V1 COMMAND CENTER", frame)
        title.setWordWrap(True)
        title.setTextInteractionFlags(Qt.TextSelectableByMouse)
        title.setStyleSheet("font: 900 9px 'Segoe UI'; color: #5bc8ff;")
        frame_layout.addWidget(title)

        dashboard_badges = summary.get(
            "badges",
            ["JOSH FIRST", "GUARDIAN ACTIVE", "READ ONLY"],
        )
        badges = QLabel("  |  ".join(str(item) for item in dashboard_badges), frame)
        badges.setWordWrap(True)
        badges.setAlignment(Qt.AlignCenter)
        badges.setTextInteractionFlags(Qt.TextSelectableByMouse)
        badges.setStyleSheet(
            "background: rgba(2, 8, 22, 180); border: 1px solid rgba(212, 168, 32, 100); "
            "border-radius: 5px; color: rgba(212, 168, 32, 230); font: 900 7px 'Segoe UI'; padding: 3px;"
        )
        frame_layout.addWidget(badges)

        details = QLabel(
            "Core: " + str(summary.get("core_status", "LIVE BASELINE")) + "  |  "
            "Trusted Memory: " + str(summary.get("trusted_memory_status", "BLOCKED / NOT_PERFORMED")) + "\n"
            "Products "
            + str(summary.get("products_count", "UNKNOWN"))
            + "  |  Research "
            + str(summary.get("research_intake_receipts_count", "UNKNOWN"))
            + "/"
            + str(summary.get("research_summary_proposals_count", "UNKNOWN"))
            + "  |  Lessons "
            + str(summary.get("lesson_candidates_count", "UNKNOWN"))
            + "/"
            + str(summary.get("research_lesson_candidates_count", "UNKNOWN"))
            + "\n"
            "Memory candidates: " + str(summary.get("memory_candidate_proposals_count", "UNKNOWN")) + "  |  "
            "Engel Browser Research: " + str(summary.get("browser_queen_status", "DISABLED")) + " \u2192 Research Intake\n"
            "Guards: Untrusted Content Guard "
            + str(summary.get("untrusted_content_guard", "ACTIVE"))
            + " / Prompt Injection Guard "
            + str(summary.get("prompt_injection_guard", "ACTIVE"))
            + "\n"
            "Status: " + str(summary.get("dashboard_mode", "READ ONLY / NOT TRUSTED MEMORY / NOT APPLIED")),
            frame,
        )
        details.setWordWrap(True)
        details.setTextInteractionFlags(Qt.TextSelectableByMouse)
        details.setStyleSheet("font: 800 8px 'Segoe UI'; color: #e8f4ff;")
        frame_layout.addWidget(details)

        boundary = QLabel("Safety: " + str(summary.get("safety_boundary", "")), frame)
        boundary.setWordWrap(True)
        boundary.setTextInteractionFlags(Qt.TextSelectableByMouse)
        boundary.setStyleSheet("font: 700 7px 'Segoe UI'; color: rgba(212, 168, 32, 220);")
        frame_layout.addWidget(boundary)

        grid.addWidget(frame, 3, 0)
        return frame

    def _add_core_continuity_card(self, grid, parent, summary):
        frame = QFrame(parent)
        frame.setObjectName("AIBodyOrganCard")
        frame.setMinimumHeight(110)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(8, 7, 8, 7)
        frame_layout.setSpacing(4)

        title = QLabel("ENGEL CORE CONTINUITY", frame)
        title.setWordWrap(True)
        title.setTextInteractionFlags(Qt.TextSelectableByMouse)
        title.setStyleSheet("font: 900 9px 'Segoe UI'; color: #5bc8ff;")
        frame_layout.addWidget(title)

        continuity_badges = summary.get(
            "badges",
            ["READ ONLY INDEX", "JOSH FIRST"],
        )
        badges = QLabel("  |  ".join(str(item) for item in continuity_badges), frame)
        badges.setWordWrap(True)
        badges.setAlignment(Qt.AlignCenter)
        badges.setTextInteractionFlags(Qt.TextSelectableByMouse)
        badges.setStyleSheet(
            "background: rgba(2, 8, 22, 180); border: 1px solid rgba(212, 168, 32, 100); "
            "border-radius: 5px; color: rgba(212, 168, 32, 230); font: 900 7px 'Segoe UI'; padding: 3px;"
        )
        frame_layout.addWidget(badges)

        details = QLabel(
            "Products: " + str(summary.get("products", "UNKNOWN")) + "  |  "
            "Research: " + str(summary.get("research_reports", "UNKNOWN")) + "  |  "
            "Lessons: "
            + str(summary.get("lesson_candidates", "UNKNOWN"))
            + " / "
            + str(summary.get("lesson_reviews", "UNKNOWN"))
            + "\n"
            "Engel Browser Research: " + str(summary.get("browser_queen", "research input to Overnight Research, not separate memory")) + "\n"
            "Trusted memory: " + str(summary.get("trusted_memory", "BLOCKED")) + "  |  "
            "Status: " + str(summary.get("status", "READ ONLY INDEX")),
            frame,
        )
        details.setWordWrap(True)
        details.setTextInteractionFlags(Qt.TextSelectableByMouse)
        details.setStyleSheet("font: 800 8px 'Segoe UI'; color: #e8f4ff;")
        frame_layout.addWidget(details)

        boundary = QLabel("Safety: " + str(summary.get("safety_boundary", "")), frame)
        boundary.setWordWrap(True)
        boundary.setTextInteractionFlags(Qt.TextSelectableByMouse)
        boundary.setStyleSheet("font: 700 7px 'Segoe UI'; color: rgba(212, 168, 32, 220);")
        frame_layout.addWidget(boundary)

        grid.addWidget(frame, 4, 0)
        return frame

    def _add_browser_queen_card(self, grid, parent, summary):
        frame = QFrame(parent)
        frame.setObjectName("AIBodyOrganCard")
        frame.setMinimumHeight(100)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(8, 7, 8, 7)
        frame_layout.setSpacing(4)

        title = QLabel("BROWSER QUEEN", frame)
        title.setWordWrap(True)
        title.setTextInteractionFlags(Qt.TextSelectableByMouse)
        title.setStyleSheet("font: 900 9px 'Segoe UI'; color: #5bc8ff;")
        frame_layout.addWidget(title)

        queen_badges = summary.get(
            "badges",
            ["DISABLED", "VISIBLE ONLY"],
        )
        badges = QLabel("  |  ".join(str(item) for item in queen_badges), frame)
        badges.setWordWrap(True)
        badges.setAlignment(Qt.AlignCenter)
        badges.setTextInteractionFlags(Qt.TextSelectableByMouse)
        badges.setStyleSheet(
            "background: rgba(91, 200, 255, 18); border: 1px solid rgba(91, 200, 255, 70); "
            "border-radius: 5px; color: #5bc8ff; font: 900 7px 'Segoe UI'; padding: 3px;"
        )
        frame_layout.addWidget(badges)

        details = QLabel(
            "Status: " + str(summary.get("status", "DISABLED")) + "  |  "
            "API: " + str(summary.get("api", "BLOCKED")) + "\n"
            "Research: " + str(summary.get("research_display", "Research Intake \u2192 Overnight Research")) + "  |  "
            "Page text: " + str(summary.get("page_display", "untrusted")) + "\n"
            "Receipts: " + str(summary.get("action_receipts", "REQUIRED")),
            frame,
        )
        details.setWordWrap(True)
        details.setTextInteractionFlags(Qt.TextSelectableByMouse)
        details.setStyleSheet("font: 800 8px 'Segoe UI'; color: #e8f4ff;")
        frame_layout.addWidget(details)

        boundary = QLabel("Safety: " + str(summary.get("safety_boundary", "")), frame)
        boundary.setWordWrap(True)
        boundary.setTextInteractionFlags(Qt.TextSelectableByMouse)
        boundary.setStyleSheet("font: 700 7px 'Segoe UI'; color: rgba(212, 168, 32, 220);")
        frame_layout.addWidget(boundary)

        grid.addWidget(frame, 5, 0)
        return frame

    def _build_ai_body_panel(self, button_style):
        panel = QFrame(self)
        panel.setObjectName("AIBodyReadOnlyPanel")
        panel.setMinimumWidth(280)
        panel.setStyleSheet(
            """
            QFrame#AIBodyReadOnlyPanel {
                background: rgba(1, 5, 16, 220);
                border: 1px solid rgba(212, 168, 32, 70);
                border-radius: 8px;
            }
            QFrame#AIBodyOrganCard {
                background: rgba(2, 8, 22, 180);
                border: 1px solid rgba(91, 200, 255, 50);
                border-radius: 6px;
            }
            QLabel {
                color: rgba(232, 244, 255, 245);
                background: transparent;
                border: 0;
            }
            QScrollArea {
                border: 0;
                background: transparent;
            }
            """
        )
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(9, 8, 9, 8)
        layout.setSpacing(5)

        status = ai_body_status.build_ai_body_status()

        title = QLabel("ENGEL AI BODY", panel)
        title.setAlignment(Qt.AlignCenter)
        title.setTextInteractionFlags(Qt.TextSelectableByMouse)
        title.setStyleSheet("font: 900 10px 'Segoe UI'; color: #5bc8ff; letter-spacing: 1px;")
        layout.addWidget(title)

        subtitle = QLabel(str(status.get("subtitle", "Local AI organs mapped under Josh-first authority.")), panel)
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)
        subtitle.setTextInteractionFlags(Qt.TextSelectableByMouse)
        subtitle.setStyleSheet("font: 700 7px 'Segoe UI'; color: #8ab8d8;")
        layout.addWidget(subtitle)

        body_badges = status.get(
            "badges",
            ["JOSH FIRST", "GUARDIAN SECOND", "LOCAL ONLY"],
        )
        badges = QLabel("  |  ".join(str(item) for item in body_badges), panel)
        badges.setWordWrap(True)
        badges.setAlignment(Qt.AlignCenter)
        badges.setTextInteractionFlags(Qt.TextSelectableByMouse)
        badges.setStyleSheet(
            "background: rgba(2, 8, 22, 180); border: 1px solid rgba(212, 168, 32, 110); "
            "border-radius: 5px; color: rgba(212, 168, 32, 235); font: 900 7px 'Segoe UI'; padding: 5px;"
        )
        layout.addWidget(badges)

        health_badges = status.get("health_badges", ["AI BODY HEALTH", "LOCAL", "GUARDED", "REPORT-ONLY MEMORY", "VERIFY TO CONFIRM"])
        health_summary = QLabel("  |  ".join(str(item) for item in health_badges), panel)
        health_summary.setWordWrap(True)
        health_summary.setAlignment(Qt.AlignCenter)
        health_summary.setTextInteractionFlags(Qt.TextSelectableByMouse)
        health_summary.setStyleSheet(
            "background: rgba(91, 200, 255, 18); border: 1px solid rgba(91, 200, 255, 70); "
            "border-radius: 5px; color: #5bc8ff; font: 900 7px 'Segoe UI'; padding: 4px;"
        )
        layout.addWidget(health_summary)

        authority = QLabel(
            "Authority: " + str(status.get("authority", "")) + "\n"
            "Workflow: " + str(status.get("workflow", "")) + "\n"
            "Map: " + ("present" if status.get("architecture_map_present") else "missing") + "  |  "
            "Wrappers: " + ("present" if status.get("wrapper_package_present") else "missing"),
            panel,
        )
        authority.setWordWrap(True)
        authority.setTextInteractionFlags(Qt.TextSelectableByMouse)
        authority.setStyleSheet(
            "background: rgba(0, 0, 0, 130); border: 1px solid rgba(91, 200, 255, 55); "
            "border-radius: 5px; color: #e8f4ff; font: 800 8px 'Segoe UI'; padding: 5px;"
        )
        layout.addWidget(authority)

        flow = QLabel("\n".join(str(item) for item in status.get("body_flow", [])), panel)
        flow.setAlignment(Qt.AlignCenter)
        flow.setTextInteractionFlags(Qt.TextSelectableByMouse)
        flow.setStyleSheet("font: 900 8px 'Consolas'; color: #5bc8ff;")
        layout.addWidget(flow)

        scroll = QScrollArea(panel)
        scroll.setWidgetResizable(True)
        scroll_content = QWidget(scroll)
        grid = QGridLayout(scroll_content)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(6)
        self._add_markdown_knowledge_card(grid, scroll_content, status.get("markdown_knowledge", {}))
        self._add_file_structure_card(grid, scroll_content, status.get("file_structure", {}))
        self._add_code_companion_card(grid, scroll_content, status.get("code_companion", {}))
        self._add_core_v1_dashboard_card(grid, scroll_content, status.get("core_v1_dashboard", {}))
        self._add_core_continuity_card(grid, scroll_content, status.get("core_continuity", {}))
        self._add_browser_queen_card(grid, scroll_content, status.get("browser_queen", {}))
        for index, card in enumerate(status.get("organ_cards", [])):
            self._add_ai_body_card(grid, scroll_content, card, index + 6)
        grid.setRowStretch(len(status.get("organ_cards", [])) + 6, 1)
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, 1)

        note = QLabel(str(status.get("runtime_note", "")), panel)
        note.setWordWrap(True)
        note.setTextInteractionFlags(Qt.TextSelectableByMouse)
        note.setStyleSheet("font: 700 7px 'Segoe UI'; color: rgba(212, 168, 32, 210);")
        layout.addWidget(note)
        return panel
    # ENGEL_AI_BODY_COMPANION_PANEL_END

    def _build_ai_plan_panel(self, button_style):
        panel = QFrame(self)
        panel.setObjectName("AIPlanPanel")
        panel.setMinimumWidth(280)
        panel.setStyleSheet(self._companion_minimal_panel_stylesheet("AIPlanPanel"))
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(9, 8, 9, 8)
        layout.setSpacing(6)
        self.ai_last_plan = None

        title = QLabel("ENGEL AI PLAN", panel)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"font: 800 10px 'Segoe UI'; color: {COMPANION_ACCENT_INFO};")
        layout.addWidget(title)

        execution_boundary = QLabel("MODEL CANNOT EXECUTE  ·  AUTONOMY BLOCKED", panel)
        execution_boundary.setAlignment(Qt.AlignCenter)
        execution_boundary.setStyleSheet(
            f"color: {COMPANION_BADGE_WARNING}; font: 800 7px 'Segoe UI';"
        )
        layout.addWidget(execution_boundary)

        badges = QLabel("JOSH FIRST  ·  GUARDIAN ACTIVE  ·  PLAN ONLY", panel)
        badges.setWordWrap(True)
        badges.setAlignment(Qt.AlignCenter)
        badges.setStyleSheet(
            f"background: {COMPANION_BG_CARD_SUBTLE}; border: 1px solid {COMPANION_BADGE_WARNING}; "
            f"border-radius: 5px; color: {COMPANION_BADGE_WARNING}; font: 800 7px 'Segoe UI'; padding: 5px;"
        )
        layout.addWidget(badges)

        self.ai_plan_input = QLineEdit(panel)
        self.ai_plan_input.setPlaceholderText("Request to plan (Proceed is gated)")
        self.ai_plan_input.returnPressed.connect(self.show_ai_plan)
        layout.addWidget(self.ai_plan_input)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(5)
        self.ai_plan_button = QPushButton("Plan", panel)
        self.ai_classify_button = QPushButton("Classify", panel)
        self.ai_planner_status_button = QPushButton("Planner Status", panel)
        for button in (self.ai_plan_button, self.ai_classify_button, self.ai_planner_status_button):
            button.setMinimumHeight(30)
            button.setToolTip("Plan-only. Shows deterministic planner output and executes nothing.")
            try:
                button.setStyleSheet(button_style)
            except Exception:
                pass
            button_row.addWidget(button)
        self.ai_plan_button.clicked.connect(self.show_ai_plan)
        self.ai_classify_button.clicked.connect(self.show_ai_classification)
        self.ai_planner_status_button.clicked.connect(self.show_ai_planner_status)
        layout.addLayout(button_row)

        proceed_row = QHBoxLayout()
        proceed_row.setContentsMargins(0, 0, 0, 0)
        proceed_row.setSpacing(6)
        self.ai_proceed_button = QPushButton("Proceed", panel)
        self.ai_proceed_button.setMinimumHeight(30)
        self.ai_proceed_button.setEnabled(False)
        self.ai_proceed_button.setToolTip("Disabled until a safe approval-free deterministic plan is ready.")
        try:
            self.ai_proceed_button.setStyleSheet(button_style)
        except Exception:
            pass
        self.ai_proceed_status = QLabel("Plan only", panel)
        self.ai_proceed_status.setWordWrap(True)
        self.ai_proceed_status.setStyleSheet(
            f"color: {COMPANION_BADGE_WARNING}; font: 800 8px 'Segoe UI'; padding-left: 4px;"
        )
        self.ai_proceed_button.clicked.connect(self.proceed_ai_plan)
        proceed_row.addWidget(self.ai_proceed_button, 0)
        proceed_row.addWidget(self.ai_proceed_status, 1)
        layout.addLayout(proceed_row)

        self.ai_plan_output = QTextEdit(panel)
        self.ai_plan_output.setReadOnly(True)
        self.ai_plan_output.setMinimumHeight(220)
        self.ai_plan_output.setLineWrapMode(QTextEdit.WidgetWidth)
        self.ai_plan_output.setPlainText(
            "Intent:\nRoute:\nRisk:\nApproval:\nGuardian:\nAuthority: Josh > Guardian > Engel/runtime\nSuggested command:\nNext step:\n\nPlan output appears here. Proceed only runs approval-free allowlisted deterministic routes."
        )
        layout.addWidget(self.ai_plan_output, 1)
        return panel

    def _receipt_table_item(self, text, path_text=""):
        item = QTableWidgetItem(str(text or ""))
        try:
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            if path_text:
                item.setData(Qt.UserRole, str(path_text))
        except Exception:
            pass
        return item

    def _build_ai_receipt_viewer_panel(self, button_style):
        panel = QFrame(self)
        panel.setObjectName("AIReceiptViewerPanel")
        panel.setMinimumWidth(280)
        panel.setStyleSheet(self._companion_minimal_panel_stylesheet("AIReceiptViewerPanel"))
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(9, 8, 9, 8)
        layout.setSpacing(6)

        title = QLabel("PROCEED RECEIPTS", panel)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"font: 800 10px 'Segoe UI'; color: {COMPANION_ACCENT_INFO};")
        layout.addWidget(title)

        badges = QLabel("REPORT ONLY  |  READ ONLY  |  NOT TRUSTED MEMORY  |  NO EXECUTION", panel)
        badges.setObjectName("ProceedReceiptViewerBadges")
        badges.setWordWrap(True)
        badges.setAlignment(Qt.AlignCenter)
        badges.setStyleSheet(
            f"background: {COMPANION_BG_CARD_SUBTLE}; border: 1px solid {COMPANION_BADGE_WARNING}; "
            f"border-radius: 5px; color: {COMPANION_BADGE_WARNING}; font: 800 7px 'Segoe UI'; padding: 5px;"
        )
        layout.addWidget(badges)

        self.ai_receipt_table = QTableWidget(panel)
        self.ai_receipt_table.setColumnCount(5)
        self.ai_receipt_table.setHorizontalHeaderLabels(["File", "Timestamp", "Status", "Intent", "Surface"])
        self.ai_receipt_table.setMinimumHeight(145)
        self.ai_receipt_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.ai_receipt_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.ai_receipt_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.ai_receipt_table.verticalHeader().setVisible(False)
        self.ai_receipt_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.ai_receipt_table.setWordWrap(False)
        layout.addWidget(self.ai_receipt_table, 1)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(5)
        self.ai_receipt_refresh_button = QPushButton("Refresh Receipts", panel)
        self.ai_receipt_open_button = QPushButton("Open Selected", panel)
        for button in (self.ai_receipt_refresh_button, self.ai_receipt_open_button):
            button.setMinimumHeight(30)
            button.setToolTip("Read-only receipt viewer. Does not execute receipt content.")
            try:
                button.setStyleSheet(button_style)
            except Exception:
                pass
            button_row.addWidget(button)
        self.ai_receipt_refresh_button.clicked.connect(self.refresh_ai_receipts)
        self.ai_receipt_open_button.clicked.connect(self.open_selected_ai_receipt)
        layout.addLayout(button_row)

        self.ai_receipt_status = QLabel("Receipts are report-only audit files, not trusted memory.", panel)
        self.ai_receipt_status.setWordWrap(True)
        self.ai_receipt_status.setStyleSheet("color: rgba(212, 168, 32, 220); font: 700 7px 'Segoe UI';")
        layout.addWidget(self.ai_receipt_status)

        self.ai_receipt_content = QTextEdit(panel)
        self.ai_receipt_content.setReadOnly(True)
        self.ai_receipt_content.setMinimumHeight(210)
        self.ai_receipt_content.setLineWrapMode(QTextEdit.WidgetWidth)
        self.ai_receipt_content.setPlainText("No receipt selected.")
        layout.addWidget(self.ai_receipt_content, 1)
        self.refresh_ai_receipts()
        return panel

    def refresh_ai_receipts(self):
        try:
            summaries = receipt_viewer.list_receipts(limit=25)
        except Exception as exc:
            summaries = []
            try:
                self.ai_receipt_status.setText("Receipt refresh error: " + str(exc))
            except Exception:
                pass
        try:
            self.ai_receipt_table.setSortingEnabled(False)
            self.ai_receipt_table.setRowCount(0)
            if not summaries:
                self.ai_receipt_table.setRowCount(1)
                item = self._receipt_table_item("No receipts yet.")
                self.ai_receipt_table.setItem(0, 0, item)
                for column in range(1, self.ai_receipt_table.columnCount()):
                    self.ai_receipt_table.setItem(0, column, self._receipt_table_item(""))
                self.ai_receipt_content.setPlainText("No receipts yet.")
                self.ai_receipt_status.setText("No receipts yet.")
                return
            self.ai_receipt_table.setRowCount(len(summaries))
            for row, summary in enumerate(summaries):
                path_text = str(summary.path)
                values = [
                    summary.filename,
                    summary.timestamp_text,
                    summary.status,
                    summary.intent,
                    summary.surface,
                ]
                for column, value in enumerate(values):
                    self.ai_receipt_table.setItem(row, column, self._receipt_table_item(value, path_text))
            self.ai_receipt_table.selectRow(0)
            self.ai_receipt_status.setText("Latest " + str(len(summaries)) + " receipt(s) listed. Open Selected only displays bounded text.")
        except Exception as exc:
            try:
                self.ai_receipt_status.setText("Receipt refresh error: " + str(exc))
            except Exception:
                pass

    def _selected_ai_receipt_path(self):
        try:
            row = self.ai_receipt_table.currentRow()
            if row < 0:
                return None
            item = self.ai_receipt_table.item(row, 0)
            if item is None:
                return None
            path_text = item.data(Qt.UserRole)
            if not path_text:
                return None
            path = Path(str(path_text))
            if not receipt_viewer.is_safe_receipt_path(path):
                return None
            return path
        except Exception:
            return None

    def open_selected_ai_receipt(self):
        path = self._selected_ai_receipt_path()
        if path is None:
            try:
                self.ai_receipt_content.setPlainText("Select a receipt markdown file under reports\\ai_proceed_receipts.")
                self.ai_receipt_status.setText("No safe receipt selected.")
            except Exception:
                pass
            return
        try:
            content = receipt_viewer.read_receipt_bounded(path, max_chars=12000)
            self.ai_receipt_content.setPlainText(content)
            self.ai_receipt_status.setText("Opened read-only receipt: " + Path(path).name)
        except Exception as exc:
            try:
                self.ai_receipt_content.setPlainText("Could not open receipt: " + str(exc))
                self.ai_receipt_status.setText("Receipt open error.")
            except Exception:
                pass

    def _ai_plan_request_text(self):
        text = ""
        try:
            text = self.ai_plan_input.text().strip()
        except Exception:
            text = ""
        if not text:
            try:
                text = self.input.text().strip()
            except Exception:
                text = ""
        return text

    def _set_ai_plan_output(self, text):
        try:
            self.ai_plan_output.setPlainText(str(text or ""))
        except Exception:
            pass

    def _append_ai_plan_output(self, text):
        try:
            current = self.ai_plan_output.toPlainText()
            self.ai_plan_output.setPlainText((current.rstrip() + "\n\n" + str(text or "")).strip())
        except Exception:
            pass

    def _set_ai_proceed_state(self, plan=None, status_text=None):
        try:
            self.ai_last_plan = plan
        except Exception:
            pass
        label = status_text or "Plan only"
        enabled = False
        tooltip = "Proceed writes an audit receipt; only safe approval-free deterministic plans execute."
        if plan is not None:
            enabled = True
            if ai_planner.can_proceed(plan):
                label = "Ready to proceed"
                tooltip = "Runs the suggested deterministic command through Human Command Mode."
            else:
                reason = ai_planner.proceed_block_reason(plan)
                if getattr(plan, "blocked", False):
                    label = "Blocked"
                    tooltip = reason + " Click Proceed to record a blocked receipt; no command will run."
                elif getattr(plan, "approval_required", False):
                    label = "Approval required"
                    tooltip = reason + " Click Proceed to record an approval-required receipt; no command will run."
                else:
                    label = "Plan only"
                    tooltip = reason + " Click Proceed to record a no-run receipt; no command will run."
        try:
            self.ai_proceed_button.setEnabled(enabled)
            self.ai_proceed_button.setToolTip(tooltip)
            self.ai_proceed_status.setText(label)
            self.ai_proceed_status.setToolTip(tooltip)
        except Exception:
            pass

    def _record_ai_proceed_receipt(self, plan, status, command_run="", result_summary="", output_excerpt="", reason=""):
        try:
            receipt_path = proceed_receipts.write_proceed_receipt(
                plan,
                {
                    "status": status,
                    "command_run": command_run,
                    "result_summary": result_summary,
                    "output_excerpt": output_excerpt,
                    "reason": reason,
                },
                "Companion",
            )
            try:
                shown_path = Path(receipt_path).resolve().relative_to(Path(ROOT).resolve())
            except Exception:
                shown_path = receipt_path
            return "\n\nReceipt written:\n" + str(shown_path)
        except Exception as exc:
            return "\n\nReceipt error:\n" + str(exc)

    def show_ai_plan(self):
        text = self._ai_plan_request_text()
        if not text:
            self._set_ai_plan_output("Enter a request first. Planning is local/read-only and executes nothing.")
            self._set_ai_proceed_state(None, "Plan only")
            return
        plan = ai_planner.build_plan(text)
        self._set_ai_proceed_state(plan)
        self._set_ai_plan_output(ai_planner.render_plan(plan))

    def show_ai_classification(self):
        text = self._ai_plan_request_text()
        if not text:
            self._set_ai_plan_output("Enter a request first. Classification is local/read-only and executes nothing.")
            self._set_ai_proceed_state(None, "Plan only")
            return
        plan = ai_planner.classify_intent(text)
        self._set_ai_proceed_state(plan)
        self._set_ai_plan_output(ai_planner.render_classification(plan))

    def show_ai_planner_status(self):
        self._set_ai_proceed_state(None, "Plan only")
        self._set_ai_plan_output(ai_planner.render_status())

    def proceed_ai_plan(self):
        plan = getattr(self, "ai_last_plan", None)
        if plan is None:
            self._set_ai_proceed_state(None, "Plan only")
            self._append_ai_plan_output("# Proceed Result\nStatus: Plan only\nNo generated plan is available.")
            return
        checked_plan = ai_planner.build_plan(getattr(plan, "user_text", ""))
        self._set_ai_proceed_state(checked_plan)
        if not ai_planner.can_proceed(checked_plan):
            reason = ai_planner.proceed_block_reason(checked_plan)
            status = "BLOCKED" if getattr(checked_plan, "blocked", False) else "REQUIRES_APPROVAL" if getattr(checked_plan, "approval_required", False) else "BLOCKED"
            receipt_note = self._record_ai_proceed_receipt(
                checked_plan,
                status,
                result_summary=reason,
                output_excerpt=reason,
                reason=reason,
            )
            self._append_ai_plan_output(
                "# Proceed Result\n"
                + ("Status: Blocked" if getattr(checked_plan, "blocked", False) else "Status: Approval required" if getattr(checked_plan, "approval_required", False) else "Status: Plan only")
                + "\n"
                + "Reason: "
                + reason
                + receipt_note
            )
            return
        command = str(getattr(checked_plan, "executable_command", "") or "").strip()
        if not command:
            self._set_ai_proceed_state(checked_plan, "Error")
            reason = "No executable command was available."
            receipt_note = self._record_ai_proceed_receipt(
                checked_plan,
                "ERROR",
                result_summary=reason,
                output_excerpt=reason,
                reason=reason,
            )
            self._append_ai_plan_output("# Proceed Result\nStatus: Error\nReason: " + reason + receipt_note)
            return
        try:
            result = core.handle_human_command_mode_cli(command)
        except Exception as exc:
            self._set_ai_proceed_state(checked_plan, "Error")
            reason = str(exc)
            receipt_note = self._record_ai_proceed_receipt(
                checked_plan,
                "ERROR",
                command_run=command,
                result_summary=reason,
                output_excerpt=reason,
                reason=reason,
            )
            self._append_ai_plan_output("# Proceed Result\nStatus: Error\nCommand: " + command + "\nReason: " + reason + receipt_note)
            return
        if not result:
            self._set_ai_proceed_state(checked_plan, "Error")
            reason = "Human Command Mode did not return a result."
            receipt_note = self._record_ai_proceed_receipt(
                checked_plan,
                "ERROR",
                command_run=command,
                result_summary=reason,
                output_excerpt=reason,
                reason=reason,
            )
            self._append_ai_plan_output(
                "# Proceed Result\nStatus: Error\nCommand: "
                + command
                + "\nReason: "
                + reason
                + receipt_note
            )
            return
        try:
            self.ai_proceed_button.setEnabled(False)
            self.ai_proceed_status.setText("Executed")
        except Exception:
            pass
        receipt_note = self._record_ai_proceed_receipt(
            checked_plan,
            "EXECUTED",
            command_run=command,
            result_summary="Deterministic Human Command Mode route returned a result.",
            output_excerpt=str(result),
        )
        self._append_ai_plan_output("# Proceed Result\nStatus: Executed\nCommand: " + command + "\n\n" + str(result) + receipt_note)

    def setup_tray(self):
        pix = QPixmap(64, 64)
        pix.fill(Qt.transparent)

        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)

        grad = QRadialGradient(QPointF(32, 32), 26)
        grad.setColorAt(0.0, QColor(255, 255, 255))
        grad.setColorAt(0.45, QColor(215, 225, 255))
        grad.setColorAt(1.0, QColor(90, 130, 220))
        p.setBrush(QBrush(grad))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(32, 32), 18, 18)

        p.setPen(QPen(QColor(255, 235, 150), 3))
        p.drawEllipse(QPointF(32, 12), 16, 5)
        p.end()

        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(QIcon(pix))
        self.tray.setToolTip("Engel Companion")

        menu = QMenu()
        act_restore = QAction("Restore Engel", self)
        act_toggle = QAction("Toggle Chat", self)
        act_min = QAction("Minimize to Tray", self)
        act_quit = QAction("Quit Engel", self)

        act_restore.triggered.connect(self.restore_companion)
        act_toggle.triggered.connect(self.toggle_chat)
        act_min.triggered.connect(self.minimize_to_tray)
        act_quit.triggered.connect(self.request_exit)

        menu.addAction(act_restore)
        menu.addAction(act_toggle)
        menu.addSeparator()
        menu.addAction(act_min)
        menu.addAction(act_quit)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.on_tray_activated)
        self.tray.show()

    def open_colony_hive_gui(self, tab_name=""):
        try:
            window = getattr(self, "_colony_hive_window", None)
            if window is None:
                from engel_research_office import EngelColonyHiveWindow
                window = EngelColonyHiveWindow()
                self._colony_hive_window = window
            if tab_name and hasattr(window, "tabs"):
                for index in range(window.tabs.count()):
                    if window.tabs.tabText(index).strip().lower() == str(tab_name).strip().lower():
                        window.tabs.setCurrentIndex(index)
                        break
            window.show()
            window.raise_()
            window.activateWindow()
        except Exception as exc:
            QMessageBox.warning(self, "Engel Mind / Colony Hive", "Could not open Engel Hive surface:\n" + str(exc))

    def open_engel_mind_gui(self):
        self.open_colony_hive_gui("Engel Mind")
        command = "upgrade connections status"
        self.say_user(command)
        route = core.handle_human_command_mode_cli if hasattr(core, "handle_human_command_mode_cli") else None
        status = route(command) if route else ""
        if status:
            self.run_threaded(lambda text=status: text)
            return
        self.run_threaded(lambda: "Engel Mind / Hive Connections status route is unavailable in this build.")

    def open_code_companion(self):
        script_path = os.path.join(core.ROOT, "engel_code_companion.py")
        if not os.path.exists(script_path):
            QMessageBox.warning(self, "ENGEL CODE COMPANION", "Missing standalone companion:\n" + script_path)
            return

        flags = 0
        try:
            flags = subprocess.CREATE_NO_WINDOW
        except Exception:
            flags = 0

        try:
            launch_kwargs = {"cwd": core.ROOT}
            if flags:
                launch_kwargs["creationflags"] = flags
            subprocess.Popen(
                [self._engel_pythonw(), script_path],
                **launch_kwargs
            )
            self.say_system("Standalone ENGEL CODE COMPANION launched. No route, provider, memory, queue, or autonomous apply path was enabled.")
        except Exception as exc:
            QMessageBox.warning(self, "ENGEL CODE COMPANION", "Could not launch standalone companion:\n" + str(exc))

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.restore_companion()

    def minimize_to_tray(self):
        self.hide()
        self.tray.showMessage("Engel", "Engel is still awake in the tray.", QSystemTrayIcon.Information, 2000)

    def restore_companion(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def request_exit(self):
        self._engel_close_requested = True
        self.close()

    def _stop_gui_shutdown_items(self):
        if self._shutdown_complete:
            return
        self._shutdown_complete = True
        for timer_name in [
            "timer",
            "_engel_alive_visual_timer",
            "_engel_alive_state_visual_v2_timer",
            "_engel_alive_state_visual_v2b_timer",
            "_engel_alive_state_visual_v2c_timer",
            "_engel_alive_visual_settings_v1_timer",
        ]:
            try:
                timer = getattr(self, timer_name, None)
                if timer is not None:
                    timer.stop()
            except Exception:
                pass

        try:
            if self.audio_stream:
                self.audio_stream.stop()
                self.audio_stream.close()
                self.audio_stream = None
        except Exception:
            pass

        try:
            child = getattr(self, "_colony_hive_window", None)
            if child is not None:
                child.close()
        except Exception:
            pass

        try:
            if hasattr(self, "tray"):
                self.tray.hide()
                self.tray.setVisible(False)
        except Exception:
            pass

    def closeEvent(self, event):  # noqa: N802
        self._engel_close_requested = True
        self._stop_gui_shutdown_items()
        event.accept()
        app = QApplication.instance()
        if app is not None:
            QTimer.singleShot(0, app.quit)

    def tick(self):
        self.phase += 0.045
        self.update()

    def set_state(self, state):
        self.state = state
        self.update()

    def toggle_chat(self):
        self.chat_open = not self.chat_open

        if self.chat_open:
            self.setMinimumSize(1080, 760)
            self.resize(max(self.width(), 1200), max(self.height(), 860))
            self._companion_open_host.show()
            self.chat.show()
            self.input.show()
            # Repair V2 button placement reinforcement

            try:
                self._layout_companion_widgets()
            except Exception:
                pass
            self.overnight_toggle.show()
            self.research_office_button.show()
            self.research_office_button.raise_()
            if hasattr(self, "hive_summary_card"):
                self.hive_summary_card.show()
                self.hive_summary_card.raise_()
                self._refresh_hive_summary_card()
            self.code_companion_button.show()
            self.code_companion_button.raise_()
            self.overnight_toggle.raise_()
            self.refresh_session_toggle_labels()
            self.dashboard_title.show()
            self.dashboard_subtitle.hide()
            self.status_rail.show()
            if hasattr(self, "engel_voice_mode_panel"):
                self._refresh_engel_voice_mode_status()
            self._companion_open_host.raise_()
            self.dashboard_title.raise_()
            self.dashboard_subtitle.raise_()
            self.status_rail.raise_()
            self.input.setFocus()
        else:
            self._companion_open_host.hide()
            self.chat.hide()
            self.input.hide()
            self.overnight_toggle.hide()
            self.research_office_button.hide()
            if hasattr(self, "hive_summary_card"):
                self.hive_summary_card.hide()
            self.code_companion_button.hide()
            self.dashboard_title.hide()
            self.dashboard_subtitle.hide()
            self.status_rail.hide()
            self.setMinimumSize(260, 250)
            self.resize(260, 250)

        self.update()

    def resizeEvent(self, event):
        try:
            self._layout_companion_widgets()
        except Exception:
            pass
        super().resizeEvent(event)

    def say_system(self, text):
        self.chat.append("<span style='color:#9fbfff;'>System:</span> " + str(text))

    def say_user(self, text):
        self.chat.append("<br><span style='color:#d7e7ff;'>You:</span> " + str(text))

    def say_engel(self, text):
        try:
            text = core.spell_check_response(text)
        except Exception:
            pass
        display = str(text)
        if display.startswith("[UNTRUSTED_MODEL_OUTPUT]\n"):
            display = display[len("[UNTRUSTED_MODEL_OUTPUT]\n"):]
        display = display.replace("[UNTRUSTED_MODEL_OUTPUT_EMPTY]", "[no response from model]")
        clean = display.replace("\n", "<br>")
        self.chat.append("<br><span style='color:#ffe6a0;'>Engel:</span><br>" + clean)

    def run_threaded(self, task):
        def worker():
            try:
                self.set_state("thinking")
                result = task()
                self.set_state("speaking")
                self.say_engel(result)
            except Exception as e:
                self.set_state("warning")
                self.say_engel("Error: " + str(e))
            finally:
                QTimer.singleShot(1400, lambda: self.set_state("idle"))

        threading.Thread(target=worker, daemon=True).start()

    def prompt_approve_readonly(self, folder):
        box = QMessageBox(self)
        box.setWindowTitle("Engel Approval")
        box.setIcon(QMessageBox.Question)
        box.setText("This folder is not approved yet.")

        info = (
            "Approve SAFE read-only access?\n\n"
            + folder
            + "\n\nEngel will only scan/read. It will not edit files."
        )

        box.setInformativeText(info)
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        box.setDefaultButton(QMessageBox.No)

        result = box.exec()

        if result == QMessageBox.Yes:
            approval_result = core.approve_folder(folder)
            self.say_system(approval_result)
            return "Approved read-only folder" in approval_result or "already approved" in approval_result.lower()

        self.say_system("Approval canceled.")
        return False

    def read_and_summarize_drop(self, path):
        report = core.safe_read_text_file(path)

        if report.startswith("# Read Blocked") or report.startswith("# Read Failed"):
            return report

        try:
            summary = core.summarize_report("last_read")
            return (
                "Read-only file received:\n"
                + path
                + "\n\nSummary:\n"
                + summary
                + "\n\nFull read report saved to reports\\LAST_READ_REPORT.md"
            )
        except Exception as e:
            return report + "\n\nSummary failed: " + str(e)

    def scan_and_summarize_drop(self, path):
        report = core.scan_folder(path)

        if report.startswith("# Scan Blocked") or report.startswith("# Scan Failed"):
            return report

        try:
            summary = core.summarize_report("last_scan")
            return (
                "Read-only folder received:\n"
                + path
                + "\n\nSummary:\n"
                + summary
                + "\n\nFull scan report saved to reports\\LAST_SCAN_REPORT.md"
            )
        except Exception as e:
            return report + "\n\nSummary failed: " + str(e)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.set_state("thinking")
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        paths = [url.toLocalFile() for url in urls if url.isLocalFile()]

        if not paths:
            self.set_state("idle")
            return

        for path in paths:
            if os.path.isdir(path):
                if core.is_path_approved(path):
                    self.say_system("Folder dropped; read-only approval already exists: " + path)
                    self.run_threaded(lambda p=path: self.scan_and_summarize_drop(p))
                else:
                    approved = self.prompt_approve_readonly(path)
                    if approved:
                        self.say_system("Folder read-only approval granted; scanning: " + path)
                        self.run_threaded(lambda p=path: self.scan_and_summarize_drop(p))
                    else:
                        self.say_engel("Folder was not approved:\n" + path)

            elif os.path.isfile(path):
                folder = os.path.dirname(path)

                if core.is_path_approved(path):
                    self.say_system("File dropped; read-only approval already covers it: " + path)
                    self.run_threaded(lambda p=path: self.read_and_summarize_drop(p))
                else:
                    approved = self.prompt_approve_readonly(folder)
                    if approved:
                        self.say_system("Folder read-only approval granted; reading file: " + path)
                        self.run_threaded(lambda p=path: self.read_and_summarize_drop(p))
                    else:
                        self.say_engel("File was not approved:\n" + path)

            else:
                self.say_engel("Dropped item could not be recognized:\n" + path)

        self.set_state("idle")


    def toggle_listening_state(self):
        if self.state == "listening":
            self.set_state("idle")
            self.say_system("Listening visual mode off.")
        else:
            self.set_state("listening")
            self.say_system("Listening visual mode on. Microphone is not active yet.")


    def toggle_recording(self):
        if self.is_recording:
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self):
        if self.is_recording:
            return
        if sd is None:
            self.set_state("warning")
            self.say_engel("Microphone recording is unavailable in this runtime. The Engel Companion GUI remains open.")
            return

        self.audio_frames = []
        self.is_recording = True
        self.set_state("listening")
        self.say_system("Recording voice note... Press Ctrl+Space again to stop.")

        def callback(indata, frames, time, status):
            if status:
                pass
            self.audio_frames.append(indata.copy())

        try:
            self.audio_stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="float32",
                callback=callback
            )
            self.audio_stream.start()
        except Exception as e:
            self.is_recording = False
            self.set_state("warning")
            self.say_engel("Microphone recording failed:\n" + str(e))

    def stop_recording(self):
        if not self.is_recording:
            return

        self.is_recording = False

        try:
            if self.audio_stream:
                self.audio_stream.stop()
                self.audio_stream.close()
                self.audio_stream = None

            if not self.audio_frames:
                self.set_state("idle")
                self.say_engel("No audio was captured.")
                return

            audio = np.concatenate(self.audio_frames, axis=0)
            audio_int16 = np.int16(audio * 32767)

            voice_dir = os.path.join(core.ROOT, "voice_notes")
            os.makedirs(voice_dir, exist_ok=True)

            filename = "voice_note_" + core.now().replace(":", "-").replace(" ", "_") + ".wav"
            path = os.path.join(voice_dir, filename)

            with wave.open(path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(self.sample_rate)
                wf.writeframes(audio_int16.tobytes())

            core.append_file(core.VOICE_NOTES if hasattr(core, "VOICE_NOTES") else os.path.join(core.MEMORY_DIR, "VOICE_NOTES.md"),
                             "\n\n## " + core.now() + "\nRecorded voice note:\n" + path + "\n")
            core.append_log("Voice note recorded from companion mode: " + path)

            self.set_state("speaking")

            # Try local speech-to-text. If a Whisper model is installed and
            # voice mode is on, transcribe + run through chat + speak reply.
            transcribed = ""
            try:
                import engel_speech_bridge
                transcribed = engel_speech_bridge.transcribe_for_companion(path)
            except Exception:
                transcribed = ""

            if transcribed:
                self.say_engel(
                    f"Voice note saved:\n{path}\n\nYou (transcribed): {transcribed}"
                )
                # In voice mode, run through chat pipeline and speak the reply.
                try:
                    import engel_speech_bridge
                    if engel_speech_bridge.voice_mode_active():
                        reply = self._run_chat_for_current_voice_mode(transcribed)
                        if reply:
                            self.say_engel(f"Engel:\n{reply}")
                            try:
                                engel_speech_bridge.say(reply)
                            except Exception:
                                pass
                except Exception:
                    pass
            else:
                self.say_engel(
                    "Voice note saved:\n"
                    + path
                    + "\n\nNo STT model installed. Run: models install whisper:base"
                )

        except Exception as e:
            self.set_state("warning")
            self.say_engel("Failed to save voice note:\n" + str(e))
        finally:
            self.audio_frames = []
            QTimer.singleShot(1400, lambda: self.set_state("idle"))




    # ------------------------------------------------------------------
    # Session Toggle Buttons V1e
    # ------------------------------------------------------------------
    def _engel_pythonw(self):
        candidates = [
            os.path.join(core.ROOT, ".venv", "Scripts", "pythonw.exe"),
            os.path.join(core.ROOT, ".venv", "Scripts", "python.exe"),
        ]
        for exe_name in ("pythonw.exe", "python.exe"):
            found = shutil.which(exe_name)
            if found:
                candidates.append(found)
        if not getattr(sys, "frozen", False):
            candidates.append(sys.executable)
        for item in candidates:
            if item and os.path.exists(item):
                return item
        return sys.executable

    def _pid_file_for_script(self, script_name):
        safe = script_name.replace(".py", "").replace("\\", "_").replace("/", "_")
        return os.path.join(core.MEMORY_DIR, safe + ".pid")

    def _read_pid_file(self, script_name):
        try:
            path = self._pid_file_for_script(script_name)
            if not os.path.exists(path):
                return None
            txt = core.read_file(path).strip()
            return int(txt) if txt.isdigit() else None
        except Exception:
            return None

    def _write_pid_file(self, script_name, pid):
        try:
            core.write_file(self._pid_file_for_script(script_name), str(pid))
        except Exception:
            pass

    def _clear_pid_file(self, script_name):
        try:
            path = self._pid_file_for_script(script_name)
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass

    def _pid_is_alive_no_window(self, pid):
        try:
            if not pid:
                return False

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            STILL_ACTIVE = 259

            handle = ctypes.windll.kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION,
                False,
                int(pid)
            )

            if not handle:
                return False

            exit_code = ctypes.c_ulong()
            ok = ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
            ctypes.windll.kernel32.CloseHandle(handle)

            return bool(ok) and exit_code.value == STILL_ACTIVE
        except Exception:
            return False

    def _pid_matches_script(self, pid, script_name):
        # No-flash V2:
        # Trust only Engel's PID file and use WinAPI to check if that PID is alive.
        # No PowerShell, no WMI popup, no broad Python scan.
        return self._pid_is_alive_no_window(pid)

    def _script_pids(self, script_name):
        pid = self._read_pid_file(script_name)
        if self._pid_matches_script(pid, script_name):
            return [pid]

        self._clear_pid_file(script_name)
        return []

    def _start_script_process(self, script_name, extra_env=None, fresh=False):
        script_path = os.path.join(core.ROOT, script_name)
        if not os.path.exists(script_path):
            return False, "Missing script: " + script_path

        if script_name in ["engel_mobile_bridge.py", "engel_alive_loop.py"] and hasattr(core, "process_launch_guard_v2process_b"):
            guard = core.process_launch_guard_v2process_b(script_name)
            status = guard.get("status", "")
            if status == "ONE_LIVE_CHAIN":
                return True, "Launch guard: " + guard.get("message", "")
            if status != "CLEAR_TO_LAUNCH":
                return False, core.process_launch_guard_report_v2process_b(script_name)

        if fresh:
            self._stop_script_processes(script_name)

        running = self._script_pids(script_name)
        if running:
            return True, script_name + " already running. PID: " + str(running[0])

        env = os.environ.copy()
        if extra_env:
            env.update(extra_env)

        flags = 0
        try:
            flags = subprocess.CREATE_NO_WINDOW
        except Exception:
            flags = 0

        proc = subprocess.Popen(
            [self._engel_pythonw(), script_path],
            cwd=core.ROOT,
            env=env,
            creationflags=flags
        )
        self._write_pid_file(script_name, proc.pid)
        time.sleep(1.4)
        return True, script_name + " started. PID: " + str(proc.pid)

    def _stop_script_processes(self, script_name):
        pids = self._script_pids(script_name)
        stopped = 0

        for pid in pids:
            try:
                # No-popup stop: terminate tracked Python process directly.
                os.kill(pid, signal.SIGTERM)
                stopped += 1
            except Exception:
                try:
                    os.kill(pid, 9)
                    stopped += 1
                except Exception:
                    pass

        self._clear_pid_file(script_name)
        time.sleep(0.4)
        return stopped

    def _mobile_session_json_path(self):
        return os.path.join(core.MEMORY_DIR, "MOBILE_SESSION.json")

    def _mobile_session_md_path(self):
        return os.path.join(core.MEMORY_DIR, "MOBILE_SESSION.md")

    def _clear_mobile_session_files(self):
        for path in [self._mobile_session_json_path(), self._mobile_session_md_path()]:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass

    def _mobile_report_from_session_file(self):
        json_path = self._mobile_session_json_path()
        md_path = self._mobile_session_md_path()

        if os.path.exists(json_path):
            try:
                data = json.loads(core.read_file(json_path))
                pin = data.get("pin", "")
                pc_url = data.get("pc_url", "http://127.0.0.1:8787")
                iphone_url = data.get("iphone_url", "")
                report = (
                    "# Engel Mobile Session\n\n"
                    "Time: " + core.now() + "\n"
                    "Mobile bridge: ONLINE\n"
                    "Temporary PIN: " + str(pin) + "\n"
                    "PC URL: " + str(pc_url) + "\n"
                    "iPhone URL: " + str(iphone_url) + "\n\n"
                    "Safety:\n"
                    "- Temporary local session PIN only.\n"
                    "- Not a password.\n"
                    "- Do not use this as a real account password.\n"
                    "- Close/restart bridge to rotate PIN.\n"
                    "- No port forwarding.\n"
                )
                core.write_file(md_path, report)
                return report
            except Exception:
                pass

        if os.path.exists(md_path):
            return core.read_file(md_path)

        return (
            "# Engel Mobile Session\n\n"
            "Time: " + core.now() + "\n"
            "Mobile bridge: STARTING\n\n"
            "If this stays here, use Start Mobile Bridge DEBUG.bat once to see the error.\n"
        )

    def refresh_session_toggle_labels(self):
        try:
            mobile_on = bool(self._script_pids("engel_mobile_bridge.py"))
            research_on = bool(research_toggle_worker.worker_status().get("enabled"))

            self.mobile_toggle.blockSignals(True)
            self.mobile_toggle.setChecked(mobile_on)
            self.mobile_toggle.setText("Mobile ON" if mobile_on else "Mobile OFF")
            self.mobile_toggle.blockSignals(False)

            self.overnight_toggle.blockSignals(True)
            self.overnight_toggle.setChecked(research_on)
            self.overnight_toggle.setText("Research ON" if research_on else "Research OFF")
            self.overnight_toggle.blockSignals(False)
        except Exception:
            pass

    def toggle_mobile_session_button(self, checked):
        self.mobile_toggle.setText("Mobile ON" if checked else "Mobile OFF")

        def task():
            if checked:
                if hasattr(core, "process_launch_guard_v2process_b"):
                    guard = core.process_launch_guard_v2process_b("engel_mobile_bridge.py")
                    status = guard.get("status", "")
                    if status == "ONE_LIVE_CHAIN":
                        report = self._mobile_report_from_session_file()
                        return "# Mobile Session ON\n\n" + guard.get("message", "") + "\n\n" + report
                    if status != "CLEAR_TO_LAUNCH":
                        return core.process_launch_guard_report_v2process_b("engel_mobile_bridge.py")

                self._clear_mobile_session_files()
                ok, msg = self._start_script_process(
                    "engel_mobile_bridge.py",
                    {"ENGEL_MOBILE_AUTO_PIN": "1"},
                    fresh=False
                )
                if not ok:
                    return "# Mobile Session ON\n\n" + msg

                for _ in range(16):
                    if os.path.exists(self._mobile_session_json_path()) or os.path.exists(self._mobile_session_md_path()):
                        break
                    time.sleep(0.35)

                report = self._mobile_report_from_session_file()
                return "# Mobile Session ON\n\n" + msg + "\n\n" + report

            stopped = self._stop_script_processes("engel_mobile_bridge.py")
            report = (
                "# Engel Mobile Session\n\n"
                "Time: " + core.now() + "\n"
                "Mobile bridge: OFF\n\n"
                "Ended from Engel desktop toggle.\n\n"
                "Safety:\n"
                "- Local bridge stopped only.\n"
                "- No browsing.\n"
                "- No clicking.\n"
                "- No sending.\n"
                "- No deleting user files.\n"
            )
            try:
                core.write_file(self._mobile_session_md_path(), report)
            except Exception:
                pass
            return "# Mobile Session OFF\n\nStopped tracked mobile bridge process count: " + str(stopped)

        self.run_threaded(task)

    def toggle_overnight_research_button(self, checked):
        previous = bool(research_toggle_worker.worker_status().get("enabled"))
        self.overnight_toggle.setText("Research ON" if checked else "Research OFF")
        try:
            if checked:
                research_toggle_worker.set_worker_enabled(True)
                message = "# Research Toggle ON\n\nBounded candidate-only research worker mode enabled.\n\n"
            else:
                research_toggle_worker.set_worker_enabled(False)
                message = "# Research Toggle OFF\n\nBounded candidate-only research worker mode disabled.\n\n"
        except Exception as exc:
            QMessageBox.warning(self, "Research Toggle", "Research toggle could not be changed.")
            self.overnight_toggle.blockSignals(True)
            self.overnight_toggle.setChecked(previous)
            self.overnight_toggle.setText("Research ON" if previous else "Research OFF")
            self.overnight_toggle.blockSignals(False)
            self.run_threaded(lambda text=str(exc): "# Research Toggle Refused\n\n" + text + "\n\n" + research_toggle_status.render_status())
            return
        self.run_threaded(lambda prefix=message: prefix + research_toggle_status.render_status())

    def open_python_learning_path(self):
        command = "python learning path"
        self.say_user(command)
        route = core.handle_human_command_mode_cli if hasattr(core, "handle_human_command_mode_cli") else None
        learning = route(command) if route else ""
        growth = route("mind growth status") if route else ""
        if learning or growth:
            payload = "\n\n---\n\n".join([part for part in [growth, learning] if part])
            self.run_threaded(lambda text=payload: text)
            return
        self.run_threaded(lambda: "Python learning path route is unavailable in this build.")


    def send_message(self):
        msg = self.input.text().strip()
        if not msg:
            return

        self.input.clear()
        self.say_user(msg)
        lower = msg.lower()

        prompt_check = check_prompt_injection(msg)
        diagnostic_allowed = (
            core.guardian_allows_prompt_guard_diagnostic(msg)
            if hasattr(core, "guardian_allows_prompt_guard_diagnostic")
            else (
                lower.strip() == "prompt injection status"
                or lower.startswith("prompt injection check ")
                or lower.startswith("prompt injection scan file ")
                or lower.startswith("prompt injection scan folder ")
            )
        )
        if prompt_check.verdict in {"block", "review"} and not diagnostic_allowed:
            warning = (
                "Guardian blocked this request due to prompt-injection risk.\n\n"
                f"Verdict: {prompt_check.verdict.upper()}\n"
                f"Score: {prompt_check.score:.2f}\n\n"
                "Use `prompt injection check <text>` for a safe diagnostic route."
            )
            self.run_threaded(lambda response=warning: response)
            return

        # Research ON Debounce V2M
        # Run gateway once. Update toggle without firing its toggled callback.
        if lower.strip() in ["research on", "research start", "start research", "overnight loop on", "research loop on", "overnight research on", "research gateway on", "research durable on"]:
            research_toggle_worker.set_worker_enabled(True)
            self.run_threaded(lambda: (
                "# Research Toggle ON\n\n"
                "Bounded candidate-only research worker mode enabled without a password prompt.\n\n"
                "This enables bounded candidate-only research worker mode only. It does not start provider/network/browser/model runtime, trusted memory writes, source mutation, patch apply, startup autorun, or an endless loop.\n\n"
                + research_toggle_status.render_status()
            ))
            try:
                self.overnight_toggle.blockSignals(True)
                enabled = bool(research_toggle_worker.worker_status().get("enabled"))
                self.overnight_toggle.setChecked(enabled)
                self.overnight_toggle.setText("Research ON" if enabled else "Research OFF")
            finally:
                try:
                    self.overnight_toggle.blockSignals(False)
                except Exception:
                    pass
            return

        if lower.strip() in ["research off", "research stop", "stop research", "overnight loop off", "research loop off", "overnight research off", "research gateway off", "research durable off"]:
            research_toggle_worker.set_worker_enabled(False)
            self.run_threaded(lambda: (
                "# Research Toggle OFF\n\n"
                "Bounded candidate-only research worker mode disabled without a password prompt.\n\n"
                "No legacy overnight loop or broad process cleanup was started from this text route.\n\n"
                + research_toggle_status.render_status()
            ))
            try:
                self.overnight_toggle.blockSignals(True)
                enabled = bool(research_toggle_worker.worker_status().get("enabled"))
                self.overnight_toggle.setChecked(enabled)
                self.overnight_toggle.setText("Research ON" if enabled else "Research OFF")
            finally:
                try:
                    self.overnight_toggle.blockSignals(False)
                except Exception:
                    pass
            return

        human_command_reply = core.handle_human_command_mode_cli(msg) if hasattr(core, "handle_human_command_mode_cli") else ""
        if human_command_reply:
            self.run_threaded(lambda response=human_command_reply: response)
            return

        # Disabled duplicate Research ON/OFF routes kept as historical guardrails.
        # Authoritative Research ON/OFF routes live above and must not fall through to chat/model response.
        if False and lower.strip() in ["research off", "research stop", "stop research", "overnight loop off", "research loop off", "overnight research off"]:  # V2M-F2 duplicate research OFF route disabled
            def stop_task():
                result = core.overnight_loop_off()
                try:
                    stopped_runner = self._stop_script_processes("engel_overnight_runner.py")
                except Exception:
                    stopped_runner = 0
                if stopped_runner:
                    result += "\n\nOrphan runner cleanup: stopped " + str(stopped_runner) + " runner process(es)."
                return result
            self.run_threaded(stop_task)
            try:
                self.overnight_toggle.blockSignals(True)
                self.overnight_toggle.setChecked(False)
                self.overnight_toggle.setText("Research OFF")
            except Exception:
                pass
            finally:
                try:
                    self.overnight_toggle.blockSignals(False)
                except Exception:
                    pass
            return

        if False and lower.strip() in ["research on", "research start", "start research", "overnight loop on", "research loop on", "overnight research on"]:  # V2M-F2 duplicate research ON route disabled
            self.run_threaded(core.overnight_loop_on)
            try:
                self.overnight_toggle.blockSignals(True)
                self.overnight_toggle.setChecked(True)
                self.overnight_toggle.setText("Research ON")
            except Exception:
                pass
            finally:
                try:
                    self.overnight_toggle.blockSignals(False)
                except Exception:
                    pass
            return
















        # Research status and topic-rotation status routes.
        if lower.strip() in ["overnight topic rotation status", "topic rotation status", "overnight rotation status", "research rotation status"]:
            self.run_threaded(core.overnight_topic_rotation_status)
            return

        if False and lower.strip() in ["research on", "research start", "research gateway on"]:  # Disabled duplicate Research ON route; authoritative route is above.
            self.run_threaded(core.overnight_loop_on)
            return

        if False and lower.strip() in ["research off", "research stop", "research gateway off"]:  # Disabled duplicate Research OFF route; authoritative route is above.
            self.overnight_toggle.setChecked(False)
            return

        # Offline Conversation Memory Archive V2MIND-B
        if lower.strip() == "offline memory status":
            self.run_threaded(core.offline_conversation_archive_status_v2mind_b)
            return

        if lower.strip() == "offline memory review":
            self.run_threaded(core.offline_conversation_archive_review_v2mind_b)
            return

        if msg.strip() == "offline memory archive latest APPROVE":
            self.run_threaded(lambda: core.offline_conversation_archive_latest_v2mind_b("APPROVE"))
            return

        if lower.strip().startswith("offline memory archive latest"):
            self.run_threaded(lambda: core.offline_conversation_archive_latest_v2mind_b(""))
            return

        if lower.strip() == "offline memory export report":
            self.run_threaded(core.offline_conversation_archive_export_report_v2mind_b)
            return

        offline_note_source_v2mind_b = core._offline_conversation_source_command_v2mind_b(msg) if hasattr(core, "_offline_conversation_source_command_v2mind_b") else ""
        if offline_note_source_v2mind_b:
            offline_note_text_v2mind_b = core._offline_conversation_extract_note_v2mind_b(msg, offline_note_source_v2mind_b)
            self.run_threaded(lambda text=offline_note_text_v2mind_b, source=offline_note_source_v2mind_b: core.offline_conversation_archive_note_v2mind_b(text, source))
            return

        # Offline Memory Distillation Proposals V2MIND-C
        if lower.strip() == "offline memory distillation status":
            self.run_threaded(core.offline_memory_distillation_status_v2mind_c)
            return

        if lower.strip() == "offline memory distillation preview":
            self.run_threaded(core.offline_memory_distillation_preview_v2mind_c)
            return

        if msg.strip() == "offline memory distillation generate APPROVE":
            self.run_threaded(lambda: core.offline_memory_distillation_generate_v2mind_c("APPROVE"))
            return

        if lower.strip().startswith("offline memory distillation generate"):
            self.run_threaded(lambda: core.offline_memory_distillation_generate_v2mind_c(""))
            return

        if lower.strip() == "offline memory distillation review":
            self.run_threaded(core.offline_memory_distillation_review_v2mind_c)
            return

        # Offline Memory Proposal Routing V2MIND-D
        if lower.strip() == "offline memory proposal routing status":
            self.run_threaded(core.offline_memory_proposal_routing_status_v2mind_d)
            return

        if lower.strip() == "offline memory proposal routing preview":
            self.run_threaded(core.offline_memory_proposal_routing_preview_v2mind_d)
            return

        if msg.strip() == "offline memory proposal routing generate APPROVE":
            self.run_threaded(lambda: core.offline_memory_proposal_routing_generate_v2mind_d("APPROVE"))
            return

        if lower.strip().startswith("offline memory proposal routing generate"):
            self.run_threaded(lambda: core.offline_memory_proposal_routing_generate_v2mind_d(""))
            return

        if lower.strip() == "offline memory proposal routing review":
            self.run_threaded(core.offline_memory_proposal_routing_review_v2mind_d)
            return

        # Offline Memory Action Gates V2MIND-E
        if lower.strip() == "offline memory action gates status":
            self.run_threaded(core.offline_memory_action_gates_status_v2mind_e)
            return

        if lower.strip() == "offline memory action gates preview":
            self.run_threaded(core.offline_memory_action_gates_preview_v2mind_e)
            return

        if msg.strip() == "offline memory action gates generate APPROVE":
            self.run_threaded(lambda: core.offline_memory_action_gates_generate_v2mind_e("APPROVE"))
            return

        if lower.strip().startswith("offline memory action gates generate"):
            self.run_threaded(lambda: core.offline_memory_action_gates_generate_v2mind_e(""))
            return

        if lower.strip() == "offline memory action gates review":
            self.run_threaded(core.offline_memory_action_gates_review_v2mind_e)
            return

        # Companion Thought Intake V2MIND-A
        if lower.strip() == "companion language status":
            self.run_threaded(core.companion_conversation_patterns_status_v2mind_a2)
            return

        if lower.strip() == "companion language review":
            self.run_threaded(core.companion_conversation_patterns_review_v2mind_a2)
            return

        if lower.strip() == "idea queue status":
            self.run_threaded(core.companion_thought_inbox_status_v2mind_a)
            return

        if lower.strip() == "idea queue review":
            self.run_threaded(core.companion_thought_inbox_review_v2mind_a)
            return

        if lower.strip() == "idea queue promote preview":
            self.run_threaded(core.companion_thought_promote_preview_v2mind_a)
            return

        if msg.strip() == "idea queue promote APPROVE":
            self.run_threaded(lambda: core.companion_thought_promote_v2mind_a("APPROVE"))
            return

        if lower.strip().startswith("idea queue promote"):
            self.run_threaded(lambda: core.companion_thought_promote_v2mind_a(""))
            return

        thought_source_v2mind_a = core._companion_thought_source_command_v2mind_a(msg) if hasattr(core, "_companion_thought_source_command_v2mind_a") else ""
        if thought_source_v2mind_a:
            self.run_threaded(lambda text=msg, source=thought_source_v2mind_a: core.companion_thought_capture_v2mind_a(text, source))
            return

        thought_source_v2mind_a2 = core.companion_conversation_intake_match_v2mind_a2(msg) if hasattr(core, "companion_conversation_intake_match_v2mind_a2") else {}
        if thought_source_v2mind_a2.get("matched") or thought_source_v2mind_a2.get("clarify"):
            self.run_threaded(lambda text=msg: core.companion_conversation_capture_v2mind_a2(text))
            return

        if lower.strip() in ["research status", "research gateway status", "research overnight status", "overnight loop status", "overnight research loop status"]:
            def status_task():
                out = core.overnight_loop_status()
                try:
                    out += "\n\n---\n\n" + core.research_runner_status()
                except Exception as e:
                    out += "\n\nResearch runner status error: " + str(e)
                return out
            self.run_threaded(status_task)
            return

        if lower.strip() in ["mas roles", "agent roles"]:
            self.run_threaded(core.mas_roles)
            return

        if lower.strip() in ["mas bus status", "message bus status", "agent bus"]:
            self.run_threaded(core.mas_bus_status)
            return

        if lower.strip() in ["mas bus latest", "mas latest", "agent bus latest"]:
            self.run_threaded(core.mas_bus_latest)
            return

        if lower.startswith("mas propose "):
            rest = msg[len("mas propose "):].strip()
            parts = rest.split(maxsplit=1)
            role = parts[0].strip() if parts else ""
            task = parts[1].strip() if len(parts) > 1 else ""
            self.run_threaded(lambda r=role, t=task: core.mas_propose(r, t))
            return

        if lower.startswith("mas research "):
            task = msg[len("mas research "):].strip()
            self.run_threaded(lambda t=task: core.mas_propose_researcher(t))
            return

        if lower.startswith("mas drafting "):
            task = msg[len("mas drafting "):].strip()
            self.run_threaded(lambda t=task: core.mas_propose_drafting(t))
            return

        if lower.startswith("mas critic "):
            task = msg[len("mas critic "):].strip()
            self.run_threaded(lambda t=task: core.mas_propose_critic(t))
            return

        if lower.startswith("mas memory "):
            task = msg[len("mas memory "):].strip()
            self.run_threaded(lambda t=task: core.mas_propose_memory(t))
            return

        if lower.startswith("mas guardian "):
            task = msg[len("mas guardian "):].strip()
            self.run_threaded(lambda t=task: core.mas_propose_guardian(t))
            return

        # Brain Backend Layer V1 routes
        if lower.strip() in ["brain backend status", "backend status", "brain backends", "backend"]:
            self.run_threaded(core.brain_backend_status)
            return

        if lower.strip() in ["brain backend list", "backend list"]:
            self.run_threaded(core.brain_backend_list)
            return

        if lower.strip() in ["brain backend use local", "backend use local", "use local backend"]:
            self.run_threaded(core.brain_backend_use_local)
            return

        if lower.strip() in ["brain provider status", "provider status", "online llm status"]:
            self.run_threaded(core.brain_provider_status)
            return

        if lower.strip() in ["offline seed llm status", "offline llm status", "engel mind seed status"]:
            self.run_threaded(core.offline_seed_llm_status)
            return

        if lower.strip() in ["research search status", "gemini search status"]:
            self.run_threaded(core.research_search_status)
            return

        if lower.strip() in ["spell check status", "spell status"]:
            self.run_threaded(core.spell_check_status)
            return

        if lower.strip() in ["mas status", "agent bus status", "multi agent status"]:
            self.run_threaded(core.mas_status)
            return

        # Supercolony Hive-Mind Strategy V2SWARM-C
        if lower.strip() in ["swarm supercolony status", "swarm supercolony preview", "swarm supercolony review"]:
            self.run_threaded(lambda text=msg: core.swarm_command_v2swarm_a(text))
            return

        if msg.strip() == "swarm supercolony generate APPROVE":
            self.run_threaded(lambda: core.swarm_command_v2swarm_a("swarm supercolony generate APPROVE"))
            return

        if lower.strip().startswith("swarm supercolony generate"):
            self.run_threaded(lambda: core.swarm_command_v2swarm_a("swarm supercolony generate"))
            return

        if lower.startswith("swarm "):
            self.run_threaded(lambda text=msg: core.swarm_command_v2swarm_a(text))
            return

        if lower.strip() in ["mas protocol", "agent protocol", "multi agent protocol"]:
            self.run_threaded(core.mas_protocol)
            return

        # Offline Brain Guard V1 routes
        if lower.strip() in ["brain status", "model status", "runner status"]:
            self.run_threaded(core.engel_brain_status_v2um)
            return

        # Alive Visual Settings V1 command routes
        if lower.strip() in ["visual status", "visual settings", "visual"]:
            self.run_threaded(core.visual_status)
            return

        if lower.strip() == "visual calm":
            self.run_threaded(core.visual_calm)
            return

        if lower.strip() == "visual alive":
            self.run_threaded(core.visual_alive)
            return

        if lower.strip() == "visual bright":
            self.run_threaded(core.visual_bright)
            return

        # V4: early thinking screen route; PID-only runtime.
        if lower.strip() in ["research thinking screen", "thinking screen", "research live screen"]:
            self.run_threaded(core.research_thinking_screen_safe if hasattr(core, "research_thinking_screen_safe") else core.research_thinking_screen_safe)
            return

        if lower.strip() in ["colony hive", "colony hive screen", "engel hive", "engel colony hive", "hive", "research office", "research office screen", "research workers view", "research worker desks"]:
            self.run_threaded(core.colony_hive_safe if hasattr(core, "colony_hive_safe") else core.research_office_safe)
            return

        if lower.strip() in ["colony hive status", "engel hive status", "research office status", "research worker desks status"]:
            self.run_threaded(core.colony_hive_status if hasattr(core, "colony_hive_status") else core.research_office_status)
            return

        if lower.strip() in ["colony hive map", "engel hive map", "research office map"]:
            self.run_threaded(core.colony_hive_map if hasattr(core, "colony_hive_map") else core.research_office_map)
            return

        if lower.strip() in ["colony hive queen links", "colony hive queen links status", "research office queen links"]:
            self.run_threaded(core.colony_hive_queen_links if hasattr(core, "colony_hive_queen_links") else core.research_office_queen_links)
            return

        if lower.strip() in ["colony hive snapshot", "engel hive snapshot", "research office snapshot"]:
            self.run_threaded(core.colony_hive_snapshot if hasattr(core, "colony_hive_snapshot") else core.research_office_snapshot)
            return

        if lower.strip() in ["colony hive permissions", "engel hive permissions", "research office permissions"]:
            self.run_threaded(core.colony_hive_permissions if hasattr(core, "colony_hive_permissions") else core.research_office_permissions)
            return

        if lower.strip() in ["colony hive off", "close colony hive", "research office off", "close research office"]:
            self.run_threaded(core.colony_hive_off if hasattr(core, "colony_hive_off") else core.research_office_off)
            return

        # Remote Worker LAN Pairing routes
        if lower.strip() == "remote worker lan pairing status":
            self.run_threaded(core.remote_worker_lan_pairing_status)
            return

        if lower.strip() == "remote worker lan pairing token":
            self.run_threaded(core.remote_worker_lan_pairing_token)
            return

        if lower.strip() == "remote worker link manager status":
            self.run_threaded(core.remote_worker_link_manager_status)
            return

        if msg.strip() == "remote worker link manager enable auto worker APPROVE":
            self.run_threaded(lambda: core.remote_worker_link_manager_enable_auto_worker("APPROVE"))
            return

        if lower.strip().startswith("remote worker link manager enable auto worker"):
            self.run_threaded(lambda: core.remote_worker_link_manager_enable_auto_worker(""))
            return

        if lower.strip() == "remote worker link manager disable auto worker":
            self.run_threaded(core.remote_worker_link_manager_disable_auto_worker)
            return

        # LAN Background Auto-Run routes
        if lower.strip() in ["remote worker start", "lan server start", "start lan server", "worker start"]:
            self.run_threaded(lambda: core.remote_worker_lan_autorun_start("APPROVE"))
            return
        if msg.strip() == "remote worker lan autorun start APPROVE":
            self.run_threaded(lambda: core.remote_worker_lan_autorun_start("APPROVE"))
            return
        if lower.strip().startswith("remote worker lan autorun start"):
            self.run_threaded(lambda: core.remote_worker_lan_autorun_start("APPROVE"))
            return
        if lower.strip() == "remote worker lan autorun stop":
            self.run_threaded(core.remote_worker_lan_autorun_stop)
            return
        if lower.strip() == "remote worker lan autorun status":
            self.run_threaded(core.remote_worker_lan_autorun_status)
            return

        # FA — Level 1 Colony Sensing Preview (read-only)
        if lower.strip() == "colony sensing status":
            self.run_threaded(core.colony_sensing_status)
            return

        if lower.strip() == "colony sensing preview":
            self.run_threaded(lambda: core.colony_sensing_preview())
            return

        # FB — Sensing Preview APPROVE_REPORT (writes one report-only markdown)
        if msg.strip() == "colony sensing preview APPROVE_REPORT":
            self.run_threaded(lambda: core.colony_sensing_preview("APPROVE_REPORT"))
            return

        if lower.strip().startswith("colony sensing preview"):
            self.run_threaded(lambda: core.colony_sensing_preview())
            return

        # V2U-B: duplicate thinking status/off routes removed; V4 early routes above are authoritative.

        # V2U-B: duplicate thinking-screen route block removed; V4 early route above is authoritative.


        # Read-before-write + Diff-before-apply Guard V2R
        if lower.strip() in ["patch diff status", "patch apply status", "read before write status"]:
            self.run_threaded(core.patch_diff_guard_status_v2r)
            return

        if lower.startswith("patch diff guard "):
            import shlex
            rest = msg[len("patch diff guard "):].strip()
            parts = shlex.split(rest, posix=False)
            if len(parts) < 2:
                self.say_engel("Usage: patch diff guard <target-file> <staged-file>")
            else:
                self.run_threaded(lambda a=parts[0], b=parts[1]: core.patch_diff_guard_v2r(a, b))
            return

        if lower.startswith("patch apply staged "):
            import shlex
            rest = msg[len("patch apply staged "):].strip()
            parts = shlex.split(rest, posix=False)
            if len(parts) < 3:
                self.say_engel("Usage: patch apply staged <target-file> <staged-file> APPROVE")
            else:
                self.run_threaded(lambda a=parts[0], b=parts[1], c=parts[2]: core.patch_apply_staged_v2r(a, b, c))
            return

        if lower.strip() in ["patch guard status", "mistake guard status"]:
            if hasattr(core, "patch_guard_v2_status"):
                self.run_threaded(core.patch_guard_v2_status)
            else:
                self.run_threaded(core.patch_guard_status)
            return

        if lower.strip() in ["patch guard last check", "patch last check"]:
            self.run_threaded(core.patch_guard_last_check)
            return

        if lower.strip().startswith("patch guard check"):
            plan = msg[len("patch guard check"):].strip()
            self.run_threaded(lambda: core.patch_guard_check(plan))
            return

        if lower.strip() in ["mistake log", "mistake latest", "mistake review"]:
            self.run_threaded(core.mistake_log_latest)
            return

        # V2U-B: duplicate patch guard status route removed; safer hasattr route above is authoritative.

        if lower.strip() in ["install mistake lesson", "add mistake lesson"]:
            self.run_threaded(core.mistake_guard_install_note)
            return

        if lower.strip().startswith("mistake note "):
            note = msg[len("mistake note "):].strip()
            self.run_threaded(lambda: core.mistake_note(note))
            return

        if lower.strip() in ["research thinking status", "thinking screen status"]:
            self.run_threaded(core.research_thinking_status)
            return

        if lower.strip() in ["research thinking off", "thinking screen off", "close thinking screen"]:
            self.run_threaded(core.research_thinking_off)
            return

        if lower.strip() in ["commands open", "open commands", "open command list"]:
            self.run_threaded(core.commands_file_open)
            return

        if lower.strip() in ["research live status", "live research status", "thinking status"]:
            self.run_threaded(core.research_live_status)
            return

        # V2U-B: duplicate thinking screen route removed; V4 early route above is authoritative.

        if lower.strip() in ["commands", "command list", "engel commands", "help commands"]:
            self.run_threaded(core.engel_commands)
            return

        if lower.strip() in ["research completion digest", "research digest", "digest research run"]:
            self.run_threaded(core.research_completion_digest)
            return

        if lower.strip() in ["research digest latest", "latest research digest", "research completion status"]:
            self.run_threaded(core.research_digest_latest)
            return

        if lower.strip() in ["research runner status", "runner status", "research run status"]:
            self.run_threaded(core.research_runner_status)
            return

        if lower.strip() in ["research queue status", "queue status"]:
            self.run_threaded(core.research_queue_status)
            return

        if lower.strip() in ["research queue cleanup", "queue cleanup"]:
            self.run_threaded(core.research_queue_cleanup)
            return

        if lower.strip() in ["research next best topic", "next best research", "best research topic"]:
            self.run_threaded(core.research_next_best_topic)
            return

        if lower.strip() in ["mobile on", "start mobile session", "mobile start"]:
            self.mobile_toggle.setChecked(True)
            return

        if lower.strip() in ["mobile off", "end mobile session", "stop mobile session", "mobile stop"]:
            self.mobile_toggle.setChecked(False)
            return

        if lower.strip() in ["overnight on", "start overnight research", "research overnight on", "research durable on"]:
            self.overnight_toggle.setChecked(True)
            return

        if lower.strip() in ["overnight off", "stop overnight research", "research overnight off", "research durable off"]:
            self.overnight_toggle.setChecked(False)
            return



        if lower in ["listen", "listening"]:
            self.set_state("listening")
            self.say_system("Listening visual mode on. Microphone is not active yet.")
            return

        if lower in ["stop listening", "stop listen", "idle"]:
            self.set_state("idle")
            self.say_system("Listening visual mode off.")
            return


        if lower in ["record", "voice", "mic"]:
            self.toggle_recording()
            return






        # Permission Result System V2Q
        if lower.strip() in ["permission status", "permissions status", "permission result status", "permission system status"]:
            self.run_threaded(core.permission_status_v2q)
            return

        if lower.startswith("permission check "):
            action = msg[len("permission check "):].strip()
            self.run_threaded(lambda a=action: core.permission_render_v2q(core.permission_check_v2q(a)))
            return

        if lower.startswith("control approve-plan "):
            action = msg[len("control approve-plan "):].strip()
            self.run_threaded(lambda: core.desktop_control_approve_plan(action))
            return

        if lower.startswith("control request "):
            action = msg[len("control request "):].strip()
            self.run_threaded(lambda: core.desktop_control_request(action))
            return




        if lower == "reflect hard":
            self.run_threaded(core.self_reflect_hard)
            return

        if lower == "reflect":
            self.run_threaded(core.self_reflect)
            return

        if lower == "kernel status":
            self.run_threaded(core.kernel_status)
            return

        if lower.startswith("kernel run "):
            task = msg[len("kernel run "):].strip()
            self.run_threaded(lambda: core.kernel_run(task))
            return

        if lower.startswith("kernel result"):
            parts = msg.split(maxsplit=2)
            job_id = parts[2].strip() if len(parts) > 2 else "latest"
            self.run_threaded(lambda: core.kernel_result(job_id))
            return






        if lower.startswith("control paste latest"):
            parts = msg.split()
            approval = parts[3] if len(parts) >= 4 else ""
            self.run_threaded(lambda: core.desktop_control_paste_latest(approval))
            return

        if lower.startswith("control paste-plan "):
            target = msg[len("control paste-plan "):].strip()
            self.run_threaded(lambda: core.desktop_control_paste_plan(target))
            return

        if lower.startswith("control type-plan "):
            text = msg[len("control type-plan "):].strip()
            self.run_threaded(lambda: core.desktop_control_type_plan(text))
            return

        if lower.startswith("control click-plan "):
            parts = msg.split()
            if len(parts) != 4:
                self.say_engel("Usage: control click-plan <x> <y>\nExample: control click-plan 500 400")
                return
            self.run_threaded(lambda: core.desktop_control_click_plan(parts[2], parts[3]))
            return

        if lower.startswith("control click "):
            parts = msg.split()
            if len(parts) != 5:
                self.say_engel("Usage: control click <x> <y> APPROVE\nExample: control click 500 400 APPROVE")
                return
            self.run_threaded(lambda: core.desktop_control_single_click(parts[2], parts[3], parts[4]))
            return





        if lower.startswith("notepad new-write "):
            rest = msg[len("notepad new-write "):].strip()
            parts = rest.split(maxsplit=1)
            approval = parts[0] if len(parts) >= 1 else ""
            message = parts[1] if len(parts) >= 2 else ""
            self.run_threaded(lambda: core.desktop_notepad_new_write_approved(approval, message))
            return

        if lower.startswith("notepad write "):
            rest = msg[len("notepad write "):].strip()
            parts = rest.split(maxsplit=1)
            approval = parts[0] if len(parts) >= 1 else ""
            message = parts[1] if len(parts) >= 2 else ""
            self.run_threaded(lambda: core.desktop_notepad_write_approved(approval, message))
            return

        if lower == "notepad status":
            self.run_threaded(core.desktop_notepad_status)
            return

        if lower == "notepad open":
            self.run_threaded(core.desktop_notepad_open)
            return

        if lower.startswith("notepad paste latest"):
            parts = msg.split()
            approval = parts[3] if len(parts) >= 4 else ""
            self.run_threaded(lambda: core.desktop_notepad_paste_latest(approval))
            return

        if lower == "window status":
            self.run_threaded(core.desktop_window_status)
            return

        if lower == "control position":
            self.run_threaded(core.desktop_control_position)
            return

        if lower.startswith("control move "):
            parts = msg.split()
            if len(parts) != 4:
                self.say_engel("Usage: control move <x> <y>\nExample: control move 500 400")
                return
            self.run_threaded(lambda: core.desktop_control_move_mouse(parts[2], parts[3]))
            return

        if lower == "control status":
            self.run_threaded(core.desktop_control_status)
            return

        if lower == "desktop status":
            self.run_threaded(core.desktop_status)
            return

        # Browser AI Bridge — must be checked before generic "browser <url>" route below
        if lower.strip() in ["browser ai status", "browser ai", "ai browser status"]:
            try:
                import engel_browser_ai_bridge
                self.run_threaded(engel_browser_ai_bridge.browser_ai_status)
            except Exception as exc:
                self.run_threaded(lambda e=str(exc): f"Browser AI bridge error: {e}")
            return

        if lower.strip().startswith("browser ai connect "):
            provider = msg.strip()[len("browser ai connect "):].strip()
            try:
                import engel_browser_ai_bridge
                self.run_threaded(lambda p=provider: engel_browser_ai_bridge.browser_ai_connect(p))
            except Exception as exc:
                self.run_threaded(lambda e=str(exc): f"Browser AI bridge error: {e}")
            return

        if lower.strip() in ["browser ai disconnect", "browser ai close", "ai browser disconnect"]:
            try:
                import engel_browser_ai_bridge
                self.run_threaded(engel_browser_ai_bridge.browser_ai_disconnect)
            except Exception as exc:
                self.run_threaded(lambda e=str(exc): f"Browser AI bridge error: {e}")
            return

        if lower.strip().startswith("browser ai switch "):
            provider = msg.strip()[len("browser ai switch "):].strip()
            try:
                import engel_browser_ai_bridge
                self.run_threaded(lambda p=provider: engel_browser_ai_bridge.browser_ai_switch(p))
            except Exception as exc:
                self.run_threaded(lambda e=str(exc): f"Browser AI bridge error: {e}")
            return

        if lower.strip() == "evolve" or lower.strip().startswith("evolve "):
            sub = msg.strip()[6:].strip() if len(msg.strip()) > 6 else ""
            try:
                import engel_evolver_bridge
                self.run_threaded(lambda s=sub: engel_evolver_bridge.handle_evolve_command(s))
            except Exception as exc:
                self.run_threaded(lambda e=str(exc): f"Evolver bridge error: {e}")
            return

        if lower.strip() == "ephify" or lower.strip().startswith("ephify "):
            sub = msg.strip()[6:].strip() if len(msg.strip()) > 6 else ""
            try:
                import engel_ephify_bridge
                self.run_threaded(lambda s=sub: engel_ephify_bridge.handle_ephify_command(s))
            except Exception as exc:
                self.run_threaded(lambda e=str(exc): f"Ephify bridge error: {e}")
            return

        if lower.strip() == "sandbox" or lower.strip().startswith("sandbox "):
            sub = msg.strip()[7:].strip() if len(msg.strip()) > 7 else ""
            try:
                import engel_sandbox_bridge
                self.run_threaded(lambda s=sub: engel_sandbox_bridge.handle_sandbox_command(s))
            except Exception as exc:
                self.run_threaded(lambda e=str(exc): f"Sandbox bridge error: {e}")
            return

        if lower.strip() == "jcode" or lower.strip().startswith("jcode "):
            sub = msg.strip()[5:].strip() if len(msg.strip()) > 5 else ""
            try:
                import engel_jcode_bridge
                self.run_threaded(lambda s=sub: engel_jcode_bridge.handle_jcode_command(s))
            except Exception as exc:
                self.run_threaded(lambda e=str(exc): f"jcode bridge error: {e}")
            return

        if lower.strip() == "ensor" or lower.strip().startswith("ensor "):
            sub = msg.strip()[5:].strip() if len(msg.strip()) > 5 else ""
            try:
                import engel_ensor_bridge
                self.run_threaded(lambda s=sub: engel_ensor_bridge.handle_ensor_command(s))
            except Exception as exc:
                self.run_threaded(lambda e=str(exc): f"Ensor kit bridge error: {e}")
            return

        if lower.strip() == "ehuman" or lower.strip().startswith("ehuman "):
            sub = msg.strip()[6:].strip() if len(msg.strip()) > 6 else ""
            try:
                import engel_ehuman_bridge
                self.run_threaded(lambda s=sub: engel_ehuman_bridge.handle_ehuman_command(s))
            except Exception as exc:
                self.run_threaded(lambda e=str(exc): f"Ehuman bridge error: {e}")
            return

        if lower.strip() == "engize" or lower.strip().startswith("engize "):
            sub = msg.strip()[6:].strip() if len(msg.strip()) > 6 else ""
            try:
                import engel_engize_bridge
                self.run_threaded(lambda s=sub: engel_engize_bridge.handle_engize_command(s))
            except Exception as exc:
                self.run_threaded(lambda e=str(exc): f"Engize bridge error: {e}")
            return

        if lower.strip() == "lokalz" or lower.strip().startswith("lokalz "):
            sub = msg.strip()[6:].strip() if len(msg.strip()) > 6 else ""
            try:
                import engel_lokalz_bridge
                self.run_threaded(lambda s=sub: engel_lokalz_bridge.handle_lokalz_command(s))
            except Exception as exc:
                self.run_threaded(lambda e=str(exc): f"Lokalz bridge error: {e}")
            return

        if lower.strip() == "models" or lower.strip().startswith("models "):
            sub = msg.strip()[6:].strip() if len(msg.strip()) > 6 else ""
            try:
                import engel_speech_bridge
                self.run_threaded(lambda s=sub: engel_speech_bridge.handle_models_command(s))
            except Exception as exc:
                self.run_threaded(lambda e=str(exc): f"Speech bridge error: {e}")
            return

        if lower.strip() == "stt" or lower.strip().startswith("stt "):
            sub = msg.strip()[3:].strip() if len(msg.strip()) > 3 else ""
            try:
                import engel_speech_bridge
                self.run_threaded(lambda s=sub: engel_speech_bridge.handle_stt_command(s))
            except Exception as exc:
                self.run_threaded(lambda e=str(exc): f"STT bridge error: {e}")
            return

        if lower.strip() == "tts" or lower.strip().startswith("tts "):
            sub = msg.strip()[3:].strip() if len(msg.strip()) > 3 else ""
            try:
                import engel_speech_bridge
                self.run_threaded(lambda s=sub: engel_speech_bridge.handle_tts_command(s))
            except Exception as exc:
                self.run_threaded(lambda e=str(exc): f"TTS bridge error: {e}")
            return

        if lower.strip() == "voice" or lower.strip().startswith("voice "):
            sub = msg.strip()[5:].strip() if len(msg.strip()) > 5 else ""
            try:
                import engel_speech_bridge
                self.run_threaded(lambda s=sub: engel_speech_bridge.handle_voice_command(s))
            except Exception as exc:
                self.run_threaded(lambda e=str(exc): f"Voice bridge error: {e}")
            return

        if lower.strip().startswith("say "):
            sub = msg.strip()[4:].strip()
            try:
                import engel_speech_bridge
                self.run_threaded(lambda s=sub: engel_speech_bridge.handle_say_command(s))
            except Exception as exc:
                self.run_threaded(lambda e=str(exc): f"Say bridge error: {e}")
            return

        if lower.strip() == "eng3d" or lower.strip().startswith("eng3d "):
            sub = msg.strip()[5:].strip() if len(msg.strip()) > 5 else ""
            try:
                import engel_eng3d_bridge
                self.run_threaded(lambda s=sub: engel_eng3d_bridge.handle_eng3d_command(s))
            except Exception as exc:
                self.run_threaded(lambda e=str(exc): f"Eng3d bridge error: {e}")
            return

        if lower.strip() == "local llm" or lower.strip().startswith("local llm "):
            sub = msg.strip()[9:].strip() if len(msg.strip()) > 9 else ""
            try:
                import engel_local_llm_bridge
                self.run_threaded(lambda s=sub: engel_local_llm_bridge.handle_local_llm_command(s))
            except Exception as exc:
                self.run_threaded(lambda e=str(exc): f"Local LLM bridge error: {e}")
            return

        if lower.strip() == "discord" or lower.strip().startswith("discord "):
            sub = msg.strip()[7:].strip() if len(msg.strip()) > 7 else ""
            try:
                import engel_discord_bridge
                self.run_threaded(lambda s=sub: engel_discord_bridge.handle_discord_command(s))
            except Exception as exc:
                self.run_threaded(lambda e=str(exc): f"Discord bridge error: {e}")
            return

        if lower.startswith("browser "):
            target = msg[8:].strip()
            self.run_threaded(lambda: core.desktop_open_browser(target))
            return

        if lower == "discord":
            self.run_threaded(core.desktop_open_discord)
            return

        if lower.startswith("open "):
            folder = msg[5:].strip()
            self.run_threaded(lambda: core.desktop_open_approved_folder(folder))
            return





        if lower == "look task":
            self.run_threaded(core.desktop_look_task)
            return

        if lower == "look focused":
            self.run_threaded(core.desktop_look_focused)
            return

        if lower == "look":
            self.run_threaded(core.desktop_look_latest_screenshot)
            return

        if lower == "screenshot report":
            self.run_threaded(core.desktop_screenshot_report)
            return

        if lower == "screenshot":
            self.run_threaded(core.desktop_screenshot)
            return


        if lower == "health repair":
            self.run_threaded(core.health_repair)
            return



        if lower == "draft latest":
            self.run_threaded(core.draft_latest)
            return

        if lower.startswith("draft copy latest"):
            parts = msg.split()
            approval = parts[3] if len(parts) >= 4 else ""
            self.run_threaded(lambda: core.draft_copy_latest(approval))
            return

        if lower.startswith("draft"):
            draft_text = msg[len("draft"):].strip()
            self.run_threaded(lambda: core.create_local_draft(draft_text))
            return




        if lower == "restore plan latest":
            self.run_threaded(core.restore_plan_latest)
            return

        if lower == "backup list":
            self.run_threaded(core.backup_list)
            return

        if lower.startswith("backup stable"):
            parts = msg.split()
            approval = parts[2] if len(parts) >= 3 else ""
            self.run_threaded(lambda: core.backup_stable(approval))
            return


        if lower.startswith("source fetch "):
            url = msg[len("source fetch "):].strip()
            self.run_threaded(lambda: core.source_fetch(url))
            return


        if lower == "source quality latest":
            self.run_threaded(core.source_quality_latest)
            return

        if lower == "source list":
            self.run_threaded(core.source_list)
            return

        if lower == "source read latest":
            self.run_threaded(core.source_read_latest)
            return

        if lower == "research brief latest":
            self.run_threaded(core.research_brief_latest)
            return



        if lower.startswith("account open-login "):
            parts = msg.split()
            service = parts[2] if len(parts) >= 3 else ""
            approval = parts[3] if len(parts) >= 4 else ""
            self.run_threaded(lambda: core.account_open_login(service, approval))
            return

        if lower.startswith("account login-plan "):
            service = msg[len("account login-plan "):].strip()
            self.run_threaded(lambda: core.account_login_plan(service))
            return

        if lower == "private input mode plan":
            self.run_threaded(core.private_input_mode_plan)
            return


        if lower.startswith("research discover "):
            topic = msg[len("research discover "):].strip()
            self.run_threaded(lambda: core.research_discover(topic))
            return

        if lower == "research candidates latest":
            self.run_threaded(core.research_candidates_latest)
            return

        if lower.startswith("overnight add topic "):
            topic = msg[len("overnight add topic "):].strip()
            self.run_threaded(lambda: core.overnight_add_topic(topic))
            return

        if lower == "overnight status":
            self.run_threaded(core.overnight_status)
            return

        if lower.startswith("overnight auto-research"):
            parts = msg.split()
            approval = parts[2] if len(parts) >= 3 else ""
            self.run_threaded(lambda: core.overnight_auto_research(approval))
            return




        if lower.startswith("research memory-extract latest"):
            parts = msg.split()
            approval = parts[3] if len(parts) >= 4 else ""
            self.run_threaded(lambda: core.research_memory_extract_latest(approval))
            return



        if lower == "research full-cycle status":
            self.run_threaded(core.research_full_cycle_status)
            return

        if lower.startswith("research full-cycle"):
            parts = msg.split()
            approval = parts[2] if len(parts) >= 3 else ""
            self.run_threaded(lambda: core.research_full_cycle(approval))
            return

        if lower == "research summary latest":
            self.run_threaded(core.research_summary_latest)
            return



        if lower.strip().startswith("research queue build latest"):
            parts = msg.split()
            approval = parts[4] if len(parts) >= 5 else ""
            self.run_threaded(lambda: core.research_queue_build_latest(approval))
            return

        if lower.strip() in ["research learning plan", "research learning-plan", "learning plan", "self research plan"]:
            self.run_threaded(core.research_learning_plan)
            return




        if lower.strip() in ["research brain status", "self learning status", "research brain"]:
            self.run_threaded(core.research_brain_status)
            return

        if lower.strip() in ["learning proposals build", "research proposals build"]:
            self.run_threaded(core.learning_proposals_build)
            return

        if lower.strip() in ["learning proposals review", "research proposals review"]:
            self.run_threaded(core.learning_proposals_review)
            return

        if lower.strip() in ["learning proposals archive", "research proposals archive"]:
            self.run_threaded(core.learning_proposals_archive)
            return

        if lower.strip() in ["learning proposals reject", "research proposals reject"]:
            self.run_threaded(core.learning_proposals_reject)
            return

        if lower.strip() == "morning learning apply status":
            self.run_threaded(core.morning_learning_apply_status_v2night_d)
            return

        if lower.strip().startswith("morning learning apply"):
            parts = msg.split()
            approval = parts[3] if len(parts) >= 4 else ""
            self.run_threaded(lambda: core.morning_learning_apply_v2night_d(approval))
            return

        if lower.strip().startswith("learning proposals apply"):
            parts = msg.split()
            approval = parts[3] if len(parts) >= 4 else ""
            self.run_threaded(lambda: core.learning_proposals_apply(approval))
            return


        if lower == "research status":
            self.run_threaded(core.research_status)
            return


        if lower == "learning review latest":
            self.run_threaded(core.learning_review_latest)
            return





        if lower.strip() in ["mobile session", "mobile pin", "iphone url", "phone url"]:
            self.run_threaded(core.mobile_session_status)
            return

        if lower.strip() in ["alive", "alive status", "engel alive", "presence", "heartbeat status"]:
            self.run_threaded(core.alive_status)
            return

        if lower.strip() in ["health", "check health", "status health"]:
            self.run_threaded(core.health_repair)
            return

        # Identity routes — only fire on explicit identity questions, not casual
        # greetings. Greetings like "hi"/"hello" should flow to whatever brain
        # provider (browser AI / local LLM) is currently connected.
        if lower.strip() in [
            "who are you", "what are you", "what can you do", "see what you can do",
            "where is your brain", "what is your brain", "are you alive",
            "are you just code", "engel identity", "mind status", "engel mind status",
            "identity",
        ]:
            self.run_threaded(core.engel_identity_response_v2um)
            return














        # Overnight Loop Once Companion Route V2BRIDGE-B1
        if lower.strip() in ["overnight loop once", "research loop once", "run overnight once"]:
            self.run_threaded(core.overnight_loop_once)
            return

        # Batch Input Preview V2BATCH-A
        if lower.strip() == "batch preview status":
            self.run_threaded(core.batch_preview_status_v2batch_a)
            return

        if lower.startswith("batch preview"):
            self.run_threaded(lambda text=msg: core.batch_preview_v2batch_a(text))
            return

        if lower.strip() in ["bridge status", "chatgpt bridge status"]:
            self.run_threaded(lambda: core.chatgpt_bridge_safe_v2bridgea("status"))
            return

        if lower.strip() in ["bridge score board", "bridge scoreboard", "chatgpt bridge score board"]:
            self.run_threaded(lambda: core.chatgpt_bridge_safe_v2bridgea("score"))
            return

        if lower.strip() in ["bridge packet", "chatgpt bridge packet", "bridge handoff packet"]:
            self.run_threaded(lambda: core.chatgpt_bridge_safe_v2bridgea("packet"))
            return

        if lower.strip() in ["bridge outbox latest", "bridge latest", "chatgpt outbox latest"]:
            self.run_threaded(lambda: core.chatgpt_bridge_safe_v2bridgea("outbox"))
            return

        # Project Task Board / Next-Step Planner V2W
        if lower.strip() in ["project task board", "task board", "project roadmap"]:
            self.run_threaded(core.project_task_board_v2w)
            return

        if lower.strip() in ["project task board status", "task board status", "project roadmap status"]:
            self.run_threaded(core.project_task_board_status_v2w)
            return

        if lower.strip() in ["project next step", "next build step", "engel next step"]:
            self.run_threaded(core.project_next_step_v2w)
            return

        # Research Goals Queue V1 routes
        if lower.strip() in ["research goals queue", "research goals", "body mind research", "research goals balanced"]:
            self.run_threaded(lambda: core.research_goals_queue_v1("balanced"))
            return

        if lower.strip() in ["research goals status", "body mind research status"]:
            self.run_threaded(core.research_goals_status_v1)
            return

        if lower.strip() in ["research goals hook status", "body mind research hook status"]:
            self.run_threaded(core.research_goals_hook_status_v1)
            return

        if lower.strip() in ["research goals body", "body research goals"]:
            self.run_threaded(lambda: core.research_goals_queue_v1("body"))
            return

        if lower.strip() in ["research goals mind", "mind research goals"]:
            self.run_threaded(lambda: core.research_goals_queue_v1("mind"))
            return

        # Morning Review Bundle V2NIGHT-C
        if lower.strip() in ["morning research review", "morning review"]:
            self.run_threaded(core.morning_review_v2night_c)
            return

        if lower.strip() in ["morning research review status", "morning review status"]:
            self.run_threaded(core.morning_research_review_status_v2night_a)
            return

        # Overnight Proposal Harvest V2NIGHT-B
        if lower.strip() in ["overnight proposal harvest status", "proposal harvest status"]:
            self.run_threaded(core.overnight_proposal_harvest_status_v2night_b)
            return

        if lower.strip() in ["overnight proposal harvest review", "proposal harvest review"]:
            self.run_threaded(core.overnight_proposal_harvest_review_v2night_b)
            return

        # Session Snapshot / Rolling Summary V2V-B
        if lower.strip() in ["session snapshot", "project latest state", "latest project state"]:
            self.run_threaded(core.session_snapshot_v2vb)
            return

        if lower.strip() in ["session snapshot status", "project latest state status"]:
            self.run_threaded(core.session_snapshot_status_v2vb)
            return

        # Session / Project Memory Index V2V
        if lower.strip() in ["project memory status", "current project status"]:
            self.run_threaded(core.project_memory_status_v2v)
            return

        if lower.strip() in ["project memory index", "project index", "memory index"]:
            self.run_threaded(core.project_memory_index_v2v)
            return

        if lower.strip() in ["what are we working on", "what are we working on?", "what is engel working on"]:
            self.run_threaded(core.what_are_we_working_on_v2v)
            return

        # Guard Dry-Run Review Set / Test Matrix V2U-K
        if lower.strip() in ["unknown command guard test matrix", "guard test matrix", "router guard test matrix"]:
            self.run_threaded(core.unknown_command_guard_test_matrix_v2uk)
            return

        if lower.strip() in ["unknown command guard test matrix status", "guard test matrix status", "router guard test matrix status"]:
            self.run_threaded(core.unknown_command_guard_test_matrix_status_v2uk)
            return

        # Guarded Fallback Config / Design Report V2U-J
        if lower.strip() in ["unknown command guard config design", "guard config design", "router guard config design"]:
            self.run_threaded(core.unknown_command_guard_config_design_v2uj)
            return

        if lower.strip() in ["unknown command guard config status", "guard config status", "router guard config status"]:
            self.run_threaded(core.unknown_command_guard_config_status_v2uj)
            return

        # Guard Mode Enable Plan V2U-I
        if lower.strip() in ["unknown command guard enable plan", "guard enable plan", "router guard enable plan"]:
            self.run_threaded(core.unknown_command_guard_enable_plan_v2ui)
            return

        # Dry-Run Unknown-Command Guard Evaluator V2U-H
        if lower.startswith("unknown command guard dry-run "):
            text = msg[len("unknown command guard dry-run "):].strip()
            self.run_threaded(lambda t=text: core.unknown_command_guard_dry_run_v2uh(t))
            return

        if lower.startswith("guard dry-run "):
            text = msg[len("guard dry-run "):].strip()
            self.run_threaded(lambda t=text: core.unknown_command_guard_dry_run_v2uh(t))
            return

        # Optional Unknown-Command Guard Mode V2U-G
        if lower.strip() in ["unknown command guard status", "unknown guard status", "router guard status"]:
            self.run_threaded(core.unknown_command_guard_status_v2ug)
            return

        if lower.strip() in ["unknown command guard plan", "unknown guard plan", "router guard plan"]:
            self.run_threaded(core.unknown_command_guard_plan_v2ug)
            return

        # Closest-Command Suggestions V2U-F
        if lower.startswith("command suggest "):
            text = msg[len("command suggest "):].strip()
            self.run_threaded(lambda t=text: core.command_suggest_v2uf(t))
            return

        if lower.startswith("closest command "):
            text = msg[len("closest command "):].strip()
            self.run_threaded(lambda t=text: core.command_suggest_v2uf(t))
            return

        # Unknown-Command Safety Planning V2U-E
        if lower.strip() in ["unknown command safety plan", "unknown command plan", "router unknown plan"]:
            self.run_threaded(core.unknown_command_safety_plan_v2ue)
            return

        if lower.startswith("unknown command check "):
            text = msg[len("unknown command check "):].strip()
            self.run_threaded(lambda t=text: core.unknown_command_check_v2ue(t))
            return

        # V2CODE-A Code Read/Write Workbench
        if lower.strip() == "code workbench status":
            self.run_threaded(core.code_workbench_status_v2code_a)
            return

        if lower.strip() == "code workbench latest":
            self.run_threaded(core.code_workbench_latest_v2code_a)
            return

        if lower.startswith("code inspect "):
            path = msg[len("code inspect "):].strip()
            self.run_threaded(lambda p=path: core.code_inspect_v2code_a(p))
            return

        if lower.startswith("code search "):
            term = msg[len("code search "):].strip()
            self.run_threaded(lambda t=term: core.code_search_v2code_a(t))
            return

        if lower.startswith("code stage copy "):
            rest = msg[len("code stage copy "):].strip()
            target, staged = core._code_workbench_parse_two_paths_v2code_a(rest)
            self.run_threaded(lambda t=target, s=staged: core.code_stage_copy_v2code_a(t, s))
            return

        if lower.startswith("code compile staged "):
            staged = msg[len("code compile staged "):].strip()
            self.run_threaded(lambda s=staged: core.code_compile_staged_v2code_a(s))
            return

        # Safe Command Router Cleanup V2U-A
        if lower.strip() == "route duplicate review":
            self.run_threaded(core.route_duplicate_review_v2cleanup_b)
            return

        if lower.strip() == "route cleanup status":
            self.run_threaded(core.route_cleanup_status_v2cleanup_b)
            return

        if lower.strip() == "process truth status":
            self.run_threaded(core.process_truth_status_v2process_a)
            return

        if lower.strip() == "process duplicate report":
            self.run_threaded(core.process_duplicate_report_v2process_a)
            return

        if lower.strip() == "process cleanup plan":
            self.run_threaded(core.process_cleanup_plan_v2process_a)
            return

        if lower.strip() == "process cleanup stale dry-run":
            self.run_threaded(core.process_cleanup_stale_dry_run_v2process_b)
            return

        if lower.strip() == "process cleanup stale plan":
            self.run_threaded(core.process_cleanup_stale_plan_v2process_b)
            return

        if msg.strip() == "process cleanup stale APPROVE":
            self.run_threaded(lambda: core.process_cleanup_stale_v2process_b("APPROVE"))
            return

        if lower.strip().startswith("process cleanup stale"):
            self.run_threaded(lambda: core.process_cleanup_stale_v2process_b(""))
            return

        if lower.strip() == "app branding plan":
            self.run_threaded(core.app_branding_plan_v2process_a)
            return

        if lower.strip() == "app launcher plan":
            self.run_threaded(lambda: core.app_launcher_plan_v2app_a("app launcher plan"))
            return

        if lower.strip() == "branded launcher plan":
            self.run_threaded(core.branded_launcher_plan_v2app_a)
            return

        if lower.strip() == "exe plan":
            self.run_threaded(core.exe_plan_v2app_a)
            return

        if lower.strip() == "app launcher status":
            self.run_threaded(core.app_launcher_status_v2app_a)
            return

        if lower.strip() == "app launcher assets plan":
            self.run_threaded(lambda: core.app_launcher_assets_plan_v2app_b("app launcher assets plan"))
            return

        if lower.strip() == "app shortcut script plan":
            self.run_threaded(core.app_shortcut_script_plan_v2app_b)
            return

        if lower.strip() == "app shortcut create plan":
            self.run_threaded(core.app_shortcut_create_plan_v2app_c)
            return

        if lower.strip() == "app shortcut status":
            self.run_threaded(core.app_shortcut_status_v2app_c)
            return

        if msg.strip() == "app shortcut create APPROVE":
            self.run_threaded(lambda: core.app_shortcut_create_v2app_c("APPROVE"))
            return

        if lower.strip().startswith("app shortcut create"):
            self.run_threaded(lambda: core.app_shortcut_create_v2app_c(""))
            return

        if lower.strip() == "app exe spec plan":
            self.run_threaded(core.app_exe_spec_plan_v2app_b)
            return

        if lower.strip() == "app exe build plan":
            self.run_threaded(core.app_exe_build_plan_v2app_d)
            return

        if lower.strip() == "app packaging status":
            self.run_threaded(core.app_packaging_status_v2app_d)
            return

        if lower.strip() == "app exe safety checklist":
            self.run_threaded(core.app_exe_safety_checklist_v2app_d)
            return

        if lower.strip() == "app exe build staged plan":
            self.run_threaded(core.app_exe_build_staged_plan_v2app_e)
            return

        if lower.strip() == "app exe dependency status":
            self.run_threaded(core.app_exe_dependency_status_v2app_e)
            return

        if lower.strip() == "app exe dependency plan":
            self.run_threaded(core.app_exe_dependency_plan_v2app_f)
            return

        if lower.strip() == "app exe dependency install checklist":
            self.run_threaded(core.app_exe_dependency_install_checklist_v2app_f)
            return

        if msg.strip() == "app exe dependency install APPROVE":
            self.run_threaded(lambda: core.app_exe_dependency_install_v2app_f("APPROVE"))
            return

        if lower.strip().startswith("app exe dependency install"):
            self.run_threaded(lambda: core.app_exe_dependency_install_v2app_f(""))
            return

        if lower.strip() == "app exe build staged status":
            self.run_threaded(core.app_exe_build_staged_status_v2app_e)
            return

        if msg.strip() == "app exe build staged APPROVE":
            self.run_threaded(lambda: core.app_exe_build_staged_v2app_e("APPROVE"))
            return

        if lower.strip().startswith("app exe build staged"):
            self.run_threaded(lambda: core.app_exe_build_staged_v2app_e(""))
            return

        if lower.strip() == "app exe smoke test plan":
            self.run_threaded(core.app_exe_smoke_test_plan_v2app_i)
            return

        if lower.strip() == "app exe smoke test status":
            self.run_threaded(core.app_exe_smoke_test_status_v2app_i)
            return

        if msg.strip() == "app exe smoke test staged APPROVE":
            self.run_threaded(lambda: core.app_exe_smoke_test_staged_v2app_i("APPROVE"))
            return

        if lower.strip().startswith("app exe smoke test staged"):
            self.run_threaded(lambda: core.app_exe_smoke_test_staged_v2app_i(""))
            return

        if lower.strip() == "app exe smoke test review":
            self.run_threaded(core.app_exe_smoke_test_review_v2app_j)
            return

        if lower.strip() == "app exe functional test plan":
            self.run_threaded(core.app_exe_functional_test_plan_v2app_j)
            return

        if lower.strip() == "app exe functional test status":
            self.run_threaded(core.app_exe_functional_test_status_v2app_j)
            return

        if lower.strip() == "app exe functional test staged plan":
            self.run_threaded(core.app_exe_functional_test_staged_plan_v2app_k)
            return

        if lower.strip() == "app exe functional test staged status":
            self.run_threaded(core.app_exe_functional_test_staged_status_v2app_k)
            return

        if msg.strip() == "app exe functional test staged APPROVE":
            self.run_threaded(lambda: core.app_exe_functional_test_staged_v2app_k("APPROVE"))
            return

        if lower.strip().startswith("app exe functional test staged"):
            self.run_threaded(lambda: core.app_exe_functional_test_staged_v2app_k(""))
            return

        if lower.strip() == "app exe functional test review":
            self.run_threaded(core.app_exe_functional_test_review_v2app_l)
            return

        if lower.strip() == "app exe staged readiness status":
            self.run_threaded(core.app_exe_staged_readiness_status_v2app_l)
            return

        if lower.strip() == "app exe next phase plan":
            self.run_threaded(core.app_exe_next_phase_plan_v2app_l)
            return

        if lower.strip() == "app setup status":
            self.run_threaded(core.app_setup_status_v2app_m)
            return

        if lower.strip() == "app setup plan":
            self.run_threaded(core.app_setup_plan_v2app_m)
            return

        if lower.strip() == "app setup checklist":
            self.run_threaded(core.app_setup_checklist_v2app_m)
            return

        if lower.strip() == "app staged launch status":
            self.run_threaded(core.app_staged_launch_status_v2app_n)
            return

        if lower.strip() == "app staged launch checklist":
            self.run_threaded(core.app_staged_launch_checklist_v2app_n)
            return

        if lower.strip() == "app staged launch notes":
            self.run_threaded(core.app_staged_launch_notes_v2app_n)
            return

        if lower.strip() == "app staged launch result review":
            self.run_threaded(core.app_staged_launch_result_review_v2app_o)
            return

        if lower.strip() == "app staged route gap diagnosis":
            self.run_threaded(core.app_staged_route_gap_diagnosis_v2app_o)
            return

        if lower.strip() == "app staged exe freshness status":
            self.run_threaded(core.app_staged_exe_freshness_status_v2app_o)
            return

        if lower.strip() == "app exe rebuild staged plan":
            self.run_threaded(core.app_exe_rebuild_staged_plan_v2app_p)
            return

        if lower.strip() == "app exe rebuild staged status":
            self.run_threaded(core.app_exe_rebuild_staged_status_v2app_p)
            return

        if msg.strip() == "app exe rebuild staged APPROVE":
            self.run_threaded(lambda: core.app_exe_rebuild_staged_v2app_p("APPROVE"))
            return

        if lower.strip().startswith("app exe rebuild staged"):
            self.run_threaded(lambda: core.app_exe_rebuild_staged_v2app_p(""))
            return

        if lower.strip() == "app staged rebuild current status":
            self.run_threaded(core.app_staged_rebuild_current_status_v2app_u)
            return

        if lower.strip() == "app promotion review":
            self.run_threaded(core.app_promotion_review_v2app_r)
            return

        if lower.strip() == "app promotion plan":
            self.run_threaded(core.app_promotion_plan_v2app_r)
            return

        if lower.strip() == "app promotion status":
            self.run_threaded(core.app_promotion_status_v2app_r)
            return

        if lower.strip() == "app promotion approve":
            self.run_threaded(core.app_promotion_approve_v2app_r)
            return

        if lower.strip() == "app live destination discovery":
            self.run_threaded(core.app_live_destination_discovery_v2app_s0)
            return

        if lower.strip() == "app live destination status":
            self.run_threaded(core.app_live_destination_status_v2app_s0)
            return

        if lower.strip() == "app live destination contract":
            self.run_threaded(core.app_live_destination_contract_v2app_t)
            return

        if lower.strip() == "app live destination contract status":
            self.run_threaded(core.app_live_destination_contract_status_v2app_t)
            return

        if lower.strip() == "identity instruction status":
            self.run_threaded(core.identity_instruction_status_v2identity_a)
            return

        if lower.strip() == "identity instruction plan":
            self.run_threaded(core.identity_instruction_plan_v2identity_a)
            return

        if lower.strip() == "identity instruction staged review":
            self.run_threaded(core.identity_instruction_staged_review_v2identity_a)
            return

        if lower.strip() == "identity live prompt preflight":
            self.run_threaded(core.identity_live_prompt_preflight_v2identity_b1)
            return

        if lower.strip() == "identity live prompt patch preview":
            self.run_threaded(core.identity_live_prompt_patch_preview_v2identity_b1)
            return

        if lower.strip() == "identity live prompt update plan":
            self.run_threaded(core.identity_live_prompt_update_plan_v2identity_b1)
            return

        if lower.strip() == "route regression matrix":
            self.run_threaded(core.route_regression_matrix_v2test_a)
            return

        if lower.strip() == "route regression status":
            self.run_threaded(core.route_regression_status_v2test_a)
            return

        if lower.strip() in ["router status", "command router status", "safe router status"]:
            self.run_threaded(core.router_status_v2u)
            return

        if lower.startswith("router check "):
            command = msg[len("router check "):].strip()
            self.run_threaded(lambda c=command: core.router_check_v2u(c))
            return

        # Tool Registry Labels V2S
        if lower.strip() in ["tool registry status", "tool status", "tools status", "tool registry"]:
            self.run_threaded(core.tool_registry_status_v2s)
            return

        if lower.startswith("tool check "):
            command = msg[len("tool check "):].strip()
            self.run_threaded(lambda c=command: core.tool_check_v2s(c))
            return

        if lower in ["help", "commands"]:
            self.run_threaded(core.engel_help)
            return

        if lower == "status":
            self.run_threaded(self.status_text)
            return

        if lower == "guardian":
            self.run_threaded(core.guardian_check)
            return

        if lower == "morning":
            self.run_threaded(core.morning_report)
            return


        # Approved Projects Folder Hygiene V2T
        if lower.strip() in ["approved projects hygiene", "approved hygiene", "approved folder hygiene", "approved security status"]:
            self.run_threaded(core.approved_projects_hygiene_v2t)
            return

        if lower.strip().startswith("approved cleanup stale"):
            parts = msg.split()
            approval = parts[3] if len(parts) >= 4 else ""
            self.run_threaded(lambda a=approval: core.approved_cleanup_stale_v2t(a))
            return

        if lower == "approved":
            self.run_threaded(lambda: "Approved read-only folders:\n- " + "\n- ".join(core.load_approved_folders()))
            return

        if lower in ["minimize", "hide"]:
            self.minimize_to_tray()
            return

        if lower.startswith("approve "):
            folder = msg[8:].strip()
            self.run_threaded(lambda: core.approve_folder(folder))
            return

        if lower.startswith("unapprove "):
            folder = msg[10:].strip()
            self.run_threaded(lambda: core.unapprove_folder(folder))
            return

        if lower.startswith("scan "):
            folder = msg[5:].strip()
            self.run_threaded(lambda: core.scan_folder(folder))
            return

        if lower.startswith("read "):
            file_path = msg[5:].strip()
            self.run_threaded(lambda: core.safe_read_text_file(file_path))
            return

        if lower.startswith("summarize "):
            target = msg[10:].strip()
            self.run_threaded(lambda: core.summarize_report(target))
            return



        # External Code Ideas Proposal V2P
        if lower.strip() in ["external code ideas proposal", "external ideas proposal", "code ideas proposal"]:
            self.run_threaded(core.external_code_ideas_proposal_v2p)
            return

        # External Code Intake Guard V2O
        if lower.startswith("external code intake ") or lower.startswith("external code audit ") or lower.startswith("code intake "):
            if lower.startswith("external code intake "):
                path = msg[len("external code intake "):].strip()
            elif lower.startswith("external code audit "):
                path = msg[len("external code audit "):].strip()
            else:
                path = msg[len("code intake "):].strip()
            self.run_threaded(lambda p=path: core.external_code_intake_v2o(p))
            return

        if lower.startswith("notes "):
            rest = msg[6:].strip()
            if " " not in rest:
                self.say_engel("Usage: notes <memory_file.md> <message>")
                return
            target, message = rest.split(" ", 1)
            self.run_threaded(lambda: core.add_memory_note(target, message))
            return

        if lower.startswith("remember "):
            lesson = msg[9:].strip()

            def remember():
                core.append_file(core.LEARNING_LOG, "\n\n## " + core.now() + "\n" + lesson + "\n")
                core.append_log("Lesson remembered from companion mode: " + lesson)
                return "Lesson saved."

            self.run_threaded(remember)
            return

        def _general_chat(text=msg):
            return self._run_chat_for_current_voice_mode(text)

        self.run_threaded(_general_chat)

    def status_text(self):
        return (
            "Workspace: " + core.ROOT + "\n"
            + "Mode: " + core.MODE + "\n"
            + "Engel Voice Mode: " + str(getattr(self, "engel_voice_mode", "Local Engel")) + "\n"
            + "Local runtime: " + self._local_engel_runtime_status() + "\n"
            + "Agent Relay: " + self._agent_relay_status() + "\n"
            + "Online fallback: OFF\n"
            + "Command execution: OFF\n"
            + "Trusted memory write: OFF\n"
            + "Source mutation: OFF\n"
            + "Agent output trust: untrusted until reviewed\n"
            + "Provider-gated brain\n"
            + "Brain provider: " + (core._select_brain_provider_v2provider().get("provider") or "none") + "\n\n"
            + "Approved read-only folders:\n- "
            + "\n- ".join(core.load_approved_folders())
        )

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self.drag_pos and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_pos)

    def mouseReleaseEvent(self, event):
        self.drag_pos = None

    def mouseDoubleClickEvent(self, event):
        self.toggle_chat()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background: #111111;
                color: #cccccc;
                border: 1px solid #333333;
                font-family: Consolas, monospace;
                font-size: 9pt;
            }
            QMenu::item:selected {
                background: #1a3a1a;
                color: #00ff88;
            }
            QMenu::separator {
                height: 1px;
                background: #222222;
                margin: 2px 6px;
            }
        """)
        menu.addAction("Restore / Show").triggered.connect(self.restore_companion)
        menu.addAction("Toggle Chat").triggered.connect(self.toggle_chat)
        menu.addAction("Toggle Listening State").triggered.connect(self.toggle_listening_state)
        menu.addAction("Record Voice Note").triggered.connect(self.toggle_recording)
        menu.addAction("Minimize to Tray").triggered.connect(self.minimize_to_tray)
        menu.addSeparator()
        menu.addAction("Exit Engel").triggered.connect(self.request_exit)
        menu.exec(QCursor.pos())

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            if self.chat_open:
                self.toggle_chat()
            else:
                self.minimize_to_tray()
        elif event.key() == Qt.Key_M and event.modifiers() & Qt.ControlModifier:
            self.minimize_to_tray()
        elif event.key() == Qt.Key_L and event.modifiers() & Qt.ControlModifier:
            self.toggle_listening_state()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)

        # Terminal-style flat panel — near-black fill, dim border
        panel_rect = QRectF(4, 4, self.width() - 8, self.height() - 8)
        painter.setPen(QPen(QColor(51, 51, 51), 1))
        painter.setBrush(QColor(10, 10, 10, 220 if self.chat_open else 200))
        painter.drawRect(panel_rect)

        # Determine visual state
        visual_state = self.state
        try:
            if self.state == "speaking" and hasattr(self, "alive_state_visual_v2_label"):
                badge_text = self.alive_state_visual_v2_label.text().upper()
                if "SAFE / IDLE" in badge_text or "IDLE" in badge_text:
                    visual_state = "idle"
        except Exception:
            visual_state = self.state

        # State indicator color (terminal color coding)
        state_colors = {
            "thinking":  QColor(68, 170, 255),   # blue
            "speaking":  QColor(0, 255, 136),     # green
            "listening": QColor(0, 255, 136),     # green
            "warning":   QColor(255, 68, 68),     # red
        }
        indicator = state_colors.get(visual_state, QColor(68, 68, 68))  # dim for idle

        # Blinking indicator dot (simple, no glow)
        dot_on = int(self.phase * 2) % 2 == 0 if visual_state in ("thinking", "listening") else True
        if dot_on:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(indicator))
            painter.drawRect(12, 14, 8, 8)

        # Top border line (accent color)
        painter.setPen(QPen(indicator, 1))
        painter.drawLine(4, 4, self.width() - 4, 4)

        # ENGEL label
        painter.setPen(QColor(0, 255, 136))
        painter.setFont(QFont("Consolas", 13, QFont.Bold))
        painter.drawText(0, 10, self.width(), 26, Qt.AlignCenter, "ENGEL")

        # Mode / state line
        painter.setPen(QColor(102, 102, 102))
        painter.setFont(QFont("Consolas", 8))
        painter.drawText(0, 34, self.width(), 18, Qt.AlignCenter,
                         core.MODE + "  " + visual_state.upper())

        # Separator
        painter.setPen(QPen(QColor(34, 34, 34), 1))
        painter.drawLine(12, 54, self.width() - 12, 54)

        # Status lines
        painter.setFont(QFont("Consolas", 8))
        painter.setPen(QColor(85, 85, 85))
        painter.drawText(12, 58, self.width(), 16, Qt.AlignLeft, "dbl-click  open chat")
        painter.drawText(12, 72, self.width(), 16, Qt.AlignLeft, "right-click  menu")

        if self.chat_open:
            # Bottom separator when expanded
            painter.setPen(QPen(QColor(34, 34, 34), 1))
            painter.drawLine(4, self.height() - 4, self.width() - 4, self.height() - 4)





# ----------------------------------------------------------------------
# Engel Alive State Visual V2B
# Visual-only fix: avoid false CAUTION/ERROR from old chat text/stage guide.
# ----------------------------------------------------------------------
def _apply_engel_alive_state_visual_v2(window):
    try:
        import math
        from PySide6.QtCore import QTimer, Qt
        from PySide6.QtGui import QColor
        from PySide6.QtWidgets import QLabel, QGraphicsDropShadowEffect

        # V2B intentionally uses a new ready flag so it can supersede V2 after restart.
        if getattr(window, "_engel_alive_state_visual_v2b_ready", False):
            return
        window._engel_alive_state_visual_v2b_ready = True
        window._engel_alive_state_visual_v2b_phase = 0

        def _ensure_label(name, text, x, y, w, h):
            try:
                if not hasattr(window, name):
                    lab = QLabel(text, window)
                    lab.setAlignment(Qt.AlignCenter)
                    lab.setGeometry(x, y, w, h)
                    lab.show()
                    lab.raise_()
                    setattr(window, name, lab)
                return getattr(window, name)
            except Exception:
                return None

        # Reuse the same label names so V2B replaces V2 on-screen.
        state_label = _ensure_label("alive_state_visual_v2_label", "SAFE / IDLE", 392, 24, 176, 30)
        sub_label = _ensure_label("alive_state_visual_v2_sub", "watching", 392, 224, 176, 22)

        def _chat_tail():
            try:
                widgets = [
                    getattr(window, "output", None),
                    getattr(window, "chat", None),
                    getattr(window, "log", None),
                    getattr(window, "text", None),
                    getattr(window, "conversation", None),
                    getattr(window, "textbox", None),
                ]
                for w in widgets:
                    if w is None:
                        continue
                    try:
                        if hasattr(w, "toPlainText"):
                            return w.toPlainText()[-3500:].lower()
                        if hasattr(w, "get"):
                            return str(w.get("1.0", "end"))[-3500:].lower()
                    except Exception:
                        pass
            except Exception:
                pass
            return ""

        def _latest_engel_block(tail):
            try:
                idx = tail.rfind("engel:")
                if idx >= 0:
                    return tail[idx:][-1200:]
            except Exception:
                pass
            return tail[-1200:]

        def _clean_for_state_scan(text):
            # Remove common informational stage-guide lines that contain words like ERROR by design.
            cleaned = []
            skip = False
            for raw in text.splitlines():
                line = raw.strip().lower()
                if line.startswith("stage guide"):
                    skip = True
                    continue
                if skip and line.startswith("safety"):
                    skip = False
                if skip:
                    continue
                if "error: research runner hit an error" in line:
                    continue
                if "if engel fails to open" in line:
                    continue
                if "not allowed yet" in line:
                    continue
                cleaned.append(raw)
            return "\n".join(cleaned).lower()

        def _state():
            try:
                mobile_on = bool(getattr(window, "mobile_toggle").isChecked()) if hasattr(window, "mobile_toggle") else False
            except Exception:
                mobile_on = False
            try:
                research_on = bool(getattr(window, "overnight_toggle").isChecked()) if hasattr(window, "overnight_toggle") else False
            except Exception:
                research_on = False

            tail = _chat_tail()
            latest = _clean_for_state_scan(_latest_engel_block(tail))

            # Strong states from actual toggles first.
            if research_on:
                return ("RESEARCHING", "learning safely", QColor(125, 235, 255), "rgba(14, 58, 86, 225)")
            if mobile_on:
                return ("MOBILE ON", "local bridge", QColor(140, 255, 210), "rgba(20, 78, 60, 225)")

            # ERROR only from strong current indicators, not old stage guide text.
            strong_error = (
                "traceback" in latest or
                "\n# error" in latest or
                "status: error" in latest or
                "compile check failed" in latest or
                "health repair status: failed" in latest or
                "exception in tkinter callback" in latest
            )
            if strong_error:
                return ("ERROR", "needs review", QColor(255, 95, 95), "rgba(90, 18, 28, 215)")

            # CAUTION only from current blocked/approval messages.
            strong_caution = (
                "access blocked" in latest or
                "approval required" in latest or
                "blocked" in latest or
                "approve required" in latest
            )
            if strong_caution:
                return ("CAUTION", "approval gate", QColor(255, 220, 110), "rgba(82, 62, 20, 215)")

            # Research complete is a calm safe state.
            if "complete_digested" in latest or "research digest and proposal build completed" in latest:
                return ("SAFE / IDLE", "research complete", QColor(140, 255, 210), "rgba(12, 45, 42, 210)")

            if "you:" in tail and "engel:" in tail:
                return ("SAFE / SPEAKING", "responding", QColor(150, 220, 255), "rgba(20, 48, 82, 220)")

            return ("SAFE / IDLE", "watching", QColor(215, 235, 255), "rgba(8, 20, 38, 205)")

        def _tick():
            try:
                window._engel_alive_state_visual_v2b_phase = (window._engel_alive_state_visual_v2b_phase + 1) % 100000
                phase = window._engel_alive_state_visual_v2b_phase
                label, sub, color, bg = _state()

                pulse = 120 + int(85 * (0.5 + 0.5 * math.sin(phase / 4.5)))
                soft = 35 + int(45 * (0.5 + 0.5 * math.sin(phase / 7.0)))

                state_style = (
                    "QLabel {"
                    "background: " + bg + ";"
                    "color: rgba(245, 252, 255, 245);"
                    "border: 1px solid rgba(" + str(color.red()) + "," + str(color.green()) + "," + str(color.blue()) + "," + str(pulse) + ");"
                    "border-radius: 12px;"
                    "font: 800 10px 'Segoe UI';"
                    "letter-spacing: 1.5px;"
                    "}"
                )
                sub_style = (
                    "QLabel {"
                    "background: rgba(4, 10, 22, 100);"
                    "color: rgba(" + str(color.red()) + "," + str(color.green()) + "," + str(color.blue()) + ",210);"
                    "border: 0px;"
                    "font: 600 9px 'Segoe UI';"
                    "}"
                )

                if state_label:
                    state_label.setText(label)
                    state_label.setStyleSheet(state_style)
                    state_label.raise_()
                    try:
                        effect = state_label.graphicsEffect()
                        if effect is None:
                            effect = QGraphicsDropShadowEffect(state_label)
                            effect.setBlurRadius(24)
                            effect.setOffset(0, 0)
                            state_label.setGraphicsEffect(effect)
                        effect.setColor(QColor(color.red(), color.green(), color.blue(), soft))
                    except Exception:
                        pass

                if sub_label:
                    sub_label.setText(sub)
                    sub_label.setStyleSheet(sub_style)
                    sub_label.raise_()

                button_style = (
                    "QPushButton {"
                    "background: rgba(8, 20, 38, 210);"
                    "color: rgba(245, 252, 255, 245);"
                    "border: 1px solid rgba(" + str(color.red()) + "," + str(color.green()) + "," + str(color.blue()) + "," + str(pulse) + ");"
                    "border-radius: 12px;"
                    "font: 700 10px 'Segoe UI';"
                    "padding: 4px;"
                    "}"
                    "QPushButton:hover {"
                    "background: rgba(22, 58, 90, 240);"
                    "}"
                    "QPushButton:checked {"
                    "background: rgba(18, 72, 66, 235);"
                    "}"
                )

                for name, x, y, w, h in [
                    ("mobile_toggle", 392, 64, 176, 34),
                    ("overnight_toggle", 392, 104, 176, 34),
                    ("mind_connections_button", 392, 144, 176, 34),
                    ("thinking_screen_button", 392, 184, 176, 34),
                    ("research_office_button", 392, 224, 176, 34),
                    ("code_companion_button", 392, 264, 176, 34),
                ]:
                    try:
                        if hasattr(window, name):
                            btn = getattr(window, name)
                            if not getattr(window, "chat_open", False):
                                btn.setGeometry(x, y, w, h)
                            btn.setStyleSheet(button_style)
                            btn.raise_()
                            effect = btn.graphicsEffect()
                            if effect is None:
                                effect = QGraphicsDropShadowEffect(btn)
                                effect.setBlurRadius(16)
                                effect.setOffset(0, 0)
                                btn.setGraphicsEffect(effect)
                            effect.setColor(QColor(color.red(), color.green(), color.blue(), max(25, soft - 10)))
                    except Exception:
                        pass
            except Exception:
                pass

        window._engel_alive_state_visual_v2b_timer = QTimer(window)
        window._engel_alive_state_visual_v2b_timer.timeout.connect(_tick)
        window._engel_alive_state_visual_v2b_timer.start(750)
        _tick()
    except Exception:
        pass





# ----------------------------------------------------------------------
# Engel Alive State Visual V2C
# Visual-only fix: stop V1 ALIVE badge flicker and stabilize state label.
# ----------------------------------------------------------------------
def _apply_engel_alive_state_visual_v2(window):
    try:
        import math
        from PySide6.QtCore import QTimer, Qt
        from PySide6.QtGui import QColor
        from PySide6.QtWidgets import QLabel, QGraphicsDropShadowEffect

        if getattr(window, "_engel_alive_state_visual_v2c_ready", False):
            return
        window._engel_alive_state_visual_v2c_ready = True
        window._engel_alive_state_visual_v2c_phase = 0

        try:
            if hasattr(window, "_engel_alive_visual_timer"):
                window._engel_alive_visual_timer.stop()
        except Exception:
            pass
        try:
            if hasattr(window, "alive_visual_badge"):
                window.alive_visual_badge.hide()
        except Exception:
            pass

        def _ensure_label(name, text, x, y, w, h):
            try:
                if not hasattr(window, name):
                    lab = QLabel(text, window)
                    lab.setAlignment(Qt.AlignCenter)
                    lab.setGeometry(x, y, w, h)
                    lab.show()
                    lab.raise_()
                    setattr(window, name, lab)
                return getattr(window, name)
            except Exception:
                return None

        state_label = _ensure_label("alive_state_visual_v2_label", "SAFE / IDLE", 392, 24, 176, 30)
        sub_label = _ensure_label("alive_state_visual_v2_sub", "ready", 392, 224, 176, 22)

        def _chat_tail():
            try:
                widgets = [
                    getattr(window, "output", None),
                    getattr(window, "chat", None),
                    getattr(window, "log", None),
                    getattr(window, "text", None),
                    getattr(window, "conversation", None),
                    getattr(window, "textbox", None),
                ]
                for w in widgets:
                    if w is None:
                        continue
                    try:
                        if hasattr(w, "toPlainText"):
                            return w.toPlainText()[-3500:].lower()
                        if hasattr(w, "get"):
                            return str(w.get("1.0", "end"))[-3500:].lower()
                    except Exception:
                        pass
            except Exception:
                pass
            return ""

        def _latest_engel_block(tail):
            try:
                idx = tail.rfind("engel:")
                if idx >= 0:
                    return tail[idx:][-1200:]
            except Exception:
                pass
            return tail[-1200:]

        def _clean_for_state_scan(text):
            cleaned = []
            skip = False
            for raw in text.splitlines():
                line = raw.strip().lower()
                if line.startswith("stage guide"):
                    skip = True
                    continue
                if skip and line.startswith("safety"):
                    skip = False
                if skip:
                    continue
                if "error: research runner hit an error" in line:
                    continue
                if "if engel fails to open" in line:
                    continue
                if "not allowed yet" in line:
                    continue
                cleaned.append(raw)
            return "\n".join(cleaned).lower()

        def _state():
            try:
                mobile_on = bool(getattr(window, "mobile_toggle").isChecked()) if hasattr(window, "mobile_toggle") else False
            except Exception:
                mobile_on = False
            try:
                research_on = bool(getattr(window, "overnight_toggle").isChecked()) if hasattr(window, "overnight_toggle") else False
            except Exception:
                research_on = False

            tail = _chat_tail()
            latest = _clean_for_state_scan(_latest_engel_block(tail))

            if research_on:
                return ("RESEARCHING", "learning safely", QColor(125, 235, 255), "rgba(14, 58, 86, 225)")
            if mobile_on:
                return ("MOBILE ON", "local bridge", QColor(140, 255, 210), "rgba(20, 78, 60, 225)")

            strong_error = (
                "traceback" in latest or
                "\n# error" in latest or
                "status: error" in latest or
                "compile check failed" in latest or
                "health repair status: failed" in latest or
                "exception in tkinter callback" in latest
            )
            if strong_error:
                return ("ERROR", "needs review", QColor(255, 95, 95), "rgba(90, 18, 28, 215)")

            strong_caution = (
                "access blocked" in latest or
                "approval required" in latest or
                "blocked by guard" in latest or
                "approve required" in latest
            )
            if strong_caution:
                return ("CAUTION", "approval gate", QColor(255, 220, 110), "rgba(82, 62, 20, 215)")

            if "complete_digested" in latest or "research digest and proposal build completed" in latest:
                return ("SAFE / IDLE", "research complete", QColor(140, 255, 210), "rgba(12, 45, 42, 210)")

            return ("SAFE / IDLE", "ready", QColor(215, 235, 255), "rgba(8, 20, 38, 205)")

        def _tick():
            try:
                try:
                    if hasattr(window, "_engel_alive_visual_timer"):
                        window._engel_alive_visual_timer.stop()
                    if hasattr(window, "alive_visual_badge"):
                        window.alive_visual_badge.hide()
                except Exception:
                    pass

                window._engel_alive_state_visual_v2c_phase = (window._engel_alive_state_visual_v2c_phase + 1) % 100000
                phase = window._engel_alive_state_visual_v2c_phase
                label, sub, color, bg = _state()

                pulse = 130 + int(55 * (0.5 + 0.5 * math.sin(phase / 5.5)))
                soft = 35 + int(35 * (0.5 + 0.5 * math.sin(phase / 8.0)))

                state_style = (
                    "QLabel {"
                    "background: " + bg + ";"
                    "color: rgba(245, 252, 255, 245);"
                    "border: 1px solid rgba(" + str(color.red()) + "," + str(color.green()) + "," + str(color.blue()) + "," + str(pulse) + ");"
                    "border-radius: 12px;"
                    "font: 800 10px 'Segoe UI';"
                    "letter-spacing: 1.5px;"
                    "}"
                )
                sub_style = (
                    "QLabel {"
                    "background: rgba(4, 10, 22, 70);"
                    "color: rgba(" + str(color.red()) + "," + str(color.green()) + "," + str(color.blue()) + ",195);"
                    "border: 0px;"
                    "font: 600 9px 'Segoe UI';"
                    "}"
                )

                if state_label:
                    state_label.setText(label)
                    state_label.setStyleSheet(state_style)
                    state_label.raise_()
                    try:
                        effect = state_label.graphicsEffect()
                        if effect is None:
                            effect = QGraphicsDropShadowEffect(state_label)
                            effect.setBlurRadius(22)
                            effect.setOffset(0, 0)
                            state_label.setGraphicsEffect(effect)
                        effect.setColor(QColor(color.red(), color.green(), color.blue(), soft))
                    except Exception:
                        pass

                if sub_label:
                    sub_label.setText(sub)
                    sub_label.setStyleSheet(sub_style)
                    sub_label.raise_()

                button_style = (
                    "QPushButton {"
                    "background: rgba(8, 20, 38, 210);"
                    "color: rgba(245, 252, 255, 245);"
                    "border: 1px solid rgba(" + str(color.red()) + "," + str(color.green()) + "," + str(color.blue()) + "," + str(pulse) + ");"
                    "border-radius: 12px;"
                    "font: 700 10px 'Segoe UI';"
                    "padding: 4px;"
                    "}"
                    "QPushButton:hover {"
                    "background: rgba(22, 58, 90, 240);"
                    "}"
                    "QPushButton:checked {"
                    "background: rgba(18, 72, 66, 235);"
                    "}"
                )

                for name, x, y, w, h in [
                    ("mobile_toggle", 392, 64, 176, 34),
                    ("overnight_toggle", 392, 104, 176, 34),
                    ("mind_connections_button", 392, 144, 176, 34),
                    ("thinking_screen_button", 392, 184, 176, 34),
                    ("research_office_button", 392, 224, 176, 34),
                    ("code_companion_button", 392, 264, 176, 34),
                ]:
                    try:
                        if hasattr(window, name):
                            btn = getattr(window, name)
                            if not getattr(window, "chat_open", False):
                                btn.setGeometry(x, y, w, h)
                            btn.setStyleSheet(button_style)
                            btn.raise_()
                            effect = btn.graphicsEffect()
                            if effect is None:
                                effect = QGraphicsDropShadowEffect(btn)
                                effect.setBlurRadius(14)
                                effect.setOffset(0, 0)
                                btn.setGraphicsEffect(effect)
                            effect.setColor(QColor(color.red(), color.green(), color.blue(), max(20, soft - 12)))
                    except Exception:
                        pass
            except Exception:
                pass

        window._engel_alive_state_visual_v2c_timer = QTimer(window)
        window._engel_alive_state_visual_v2c_timer.timeout.connect(_tick)
        window._engel_alive_state_visual_v2c_timer.start(850)
        _tick()
    except Exception:
        pass





# ----------------------------------------------------------------------
# Alive Visual Settings V1
# Final visual-state override with persistent calm/alive/bright settings.
# Visual only. No process launching, no mobile bridge, no research runner.
# ----------------------------------------------------------------------
def _apply_engel_alive_state_visual_v2(window):
    try:
        import json
        import math
        import os

        if getattr(window, "_engel_alive_visual_settings_v1_ready", False):
            return
        window._engel_alive_visual_settings_v1_ready = True
        window._engel_alive_visual_settings_v1_phase = 0

        try:
            if hasattr(window, "_engel_alive_visual_timer"):
                window._engel_alive_visual_timer.stop()
            if hasattr(window, "alive_visual_badge"):
                window.alive_visual_badge.hide()
        except Exception:
            pass

        settings_path = os.path.join(core.MEMORY_DIR, "ALIVE_VISUAL_SETTINGS.json")

        def _settings():
            data = {"mode": "alive", "intensity": 1.0, "pulse_ms": 850, "show_subtext": True}
            try:
                if os.path.exists(settings_path):
                    with open(settings_path, "r", encoding="utf-8", errors="replace") as f:
                        loaded = json.load(f)
                    if isinstance(loaded, dict):
                        data.update(loaded)
            except Exception:
                pass
            try:
                data["intensity"] = max(0.35, min(1.75, float(data.get("intensity", 1.0))))
            except Exception:
                data["intensity"] = 1.0
            try:
                data["pulse_ms"] = max(400, min(1600, int(data.get("pulse_ms", 850))))
            except Exception:
                data["pulse_ms"] = 850
            return data

        def _ensure_label(name, text, x, y, w, h):
            try:
                if not hasattr(window, name):
                    lab = QLabel(text, window)
                    lab.setAlignment(Qt.AlignCenter)
                    lab.setGeometry(x, y, w, h)
                    lab.show()
                    lab.raise_()
                    setattr(window, name, lab)
                return getattr(window, name)
            except Exception:
                return None

        state_label = _ensure_label("alive_state_visual_v2_label", "SAFE / IDLE", 392, 24, 176, 30)
        sub_label = _ensure_label("alive_state_visual_v2_sub", "ready", 392, 224, 176, 22)

        def _state():
            try:
                mobile_on = bool(getattr(window, "mobile_toggle").isChecked()) if hasattr(window, "mobile_toggle") else False
            except Exception:
                mobile_on = False
            try:
                research_on = bool(getattr(window, "overnight_toggle").isChecked()) if hasattr(window, "overnight_toggle") else False
            except Exception:
                research_on = False

            if research_on:
                return ("RESEARCHING", "learning safely", QColor(125, 235, 255), "rgba(14, 58, 86, 225)")
            if mobile_on:
                return ("MOBILE ON", "local bridge", QColor(140, 255, 210), "rgba(20, 78, 60, 225)")

            # Keep the default calm and stable. Error/caution detection remains handled by text/output itself.
            return ("SAFE / IDLE", "ready", QColor(215, 235, 255), "rgba(8, 20, 38, 205)")

        def _scaled_color(color, intensity):
            try:
                r = min(255, int(color.red() * intensity))
                g = min(255, int(color.green() * intensity))
                b = min(255, int(color.blue() * intensity))
                return QColor(r, g, b)
            except Exception:
                return color

        def _tick():
            try:
                try:
                    if hasattr(window, "_engel_alive_visual_timer"):
                        window._engel_alive_visual_timer.stop()
                    if hasattr(window, "alive_visual_badge"):
                        window.alive_visual_badge.hide()
                except Exception:
                    pass

                s = _settings()
                intensity = s.get("intensity", 1.0)
                mode = str(s.get("mode", "alive")).upper()
                pulse_ms = int(s.get("pulse_ms", 850))

                try:
                    if window._engel_alive_visual_settings_v1_timer.interval() != pulse_ms:
                        window._engel_alive_visual_settings_v1_timer.setInterval(pulse_ms)
                except Exception:
                    pass

                window._engel_alive_visual_settings_v1_phase = (window._engel_alive_visual_settings_v1_phase + 1) % 100000
                phase = window._engel_alive_visual_settings_v1_phase
                label, sub, color, bg = _state()
                color = _scaled_color(color, intensity)

                pulse = int((120 + 65 * (0.5 + 0.5 * math.sin(phase / 4.8))) * intensity)
                pulse = max(40, min(240, pulse))
                soft = int((30 + 42 * (0.5 + 0.5 * math.sin(phase / 7.0))) * intensity)
                soft = max(10, min(130, soft))

                display_sub = sub
                if mode in ["CALM", "BRIGHT"]:
                    display_sub = (sub + " / " + mode.lower()).strip()

                state_style = (
                    "QLabel {"
                    "background: " + bg + ";"
                    "color: rgba(245, 252, 255, 245);"
                    "border: 1px solid rgba(" + str(color.red()) + "," + str(color.green()) + "," + str(color.blue()) + "," + str(pulse) + ");"
                    "border-radius: 12px;"
                    "font: 800 10px 'Segoe UI';"
                    "letter-spacing: 1.5px;"
                    "}"
                )
                sub_style = (
                    "QLabel {"
                    "background: rgba(4, 10, 22, 70);"
                    "color: rgba(" + str(color.red()) + "," + str(color.green()) + "," + str(color.blue()) + ",195);"
                    "border: 0px;"
                    "font: 600 9px 'Segoe UI';"
                    "}"
                )

                if state_label:
                    state_label.setText(label)
                    state_label.setStyleSheet(state_style)
                    state_label.raise_()
                    try:
                        effect = state_label.graphicsEffect()
                        if effect is None:
                            effect = QGraphicsDropShadowEffect(state_label)
                            effect.setBlurRadius(20)
                            effect.setOffset(0, 0)
                            state_label.setGraphicsEffect(effect)
                        effect.setColor(QColor(color.red(), color.green(), color.blue(), soft))
                    except Exception:
                        pass

                if sub_label:
                    if bool(s.get("show_subtext", True)):
                        sub_label.setText(display_sub)
                        sub_label.show()
                    else:
                        sub_label.hide()
                    sub_label.setStyleSheet(sub_style)
                    sub_label.raise_()

                button_style = (
                    "QPushButton {"
                    "background: rgba(8, 20, 38, 210);"
                    "color: rgba(245, 252, 255, 245);"
                    "border: 1px solid rgba(" + str(color.red()) + "," + str(color.green()) + "," + str(color.blue()) + "," + str(pulse) + ");"
                    "border-radius: 12px;"
                    "font: 700 10px 'Segoe UI';"
                    "padding: 4px;"
                    "}"
                    "QPushButton:hover {"
                    "background: rgba(22, 58, 90, 240);"
                    "}"
                    "QPushButton:checked {"
                    "background: rgba(18, 72, 66, 235);"
                    "}"
                )

                for name, x, y, w, h in [
                    ("mobile_toggle", 392, 64, 176, 34),
                    ("overnight_toggle", 392, 104, 176, 34),
                    ("mind_connections_button", 392, 144, 176, 34),
                    ("thinking_screen_button", 392, 184, 176, 34),
                    ("research_office_button", 392, 224, 176, 34),
                    ("code_companion_button", 392, 264, 176, 34),
                ]:
                    try:
                        if hasattr(window, name):
                            btn = getattr(window, name)
                            btn.setGeometry(x, y, w, h)
                            btn.setStyleSheet(button_style)
                            btn.raise_()
                            effect = btn.graphicsEffect()
                            if effect is None:
                                effect = QGraphicsDropShadowEffect(btn)
                                effect.setBlurRadius(12 + int(4 * intensity))
                                effect.setOffset(0, 0)
                                btn.setGraphicsEffect(effect)
                            effect.setColor(QColor(color.red(), color.green(), color.blue(), max(15, soft - 10)))
                    except Exception:
                        pass
            except Exception:
                pass

        window._engel_alive_visual_settings_v1_timer = QTimer(window)
        window._engel_alive_visual_settings_v1_timer.timeout.connect(_tick)
        window._engel_alive_visual_settings_v1_timer.start(850)
        _tick()
    except Exception:
        pass


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    win = EngelCompanion()
    win.show()
    sys.exit(app.exec())
