from __future__ import annotations

import datetime
import math
import sys
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, QUrl
from PySide6.QtGui import QBrush, QColor, QDesktopServices, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QCheckBox,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QInputDialog,
    QComboBox,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from engel_ui_theme import COLONY_HIVE_ROOT_OBJECT_NAME, colony_hive_application_stylesheet
from engel_route_explorer import (
    filter_route_catalog,
    render_route_details,
    render_route_explorer,
    route_catalog_for_gui,
    route_catalog_groups,
    route_catalog_summary,
)

from engel_research_office_data import (
    ROLE_ORDER,
    ROLE_TITLES,
    SUPER_SWARM_LIVE_COPY,
    build_engel_mind_connections_snapshot,
    build_communication_queen_snapshot,
    build_colony_hive_snapshot,
    build_queen_research_link_templates,
    build_local_hive_signal_snapshot,
    is_hive_permission_password_configured,
    render_engel_mind_connections_status,
    render_future_upgrades_status,
    request_permission_unlock,
    summarize_queen_research_folder,
    validate_queen_research_folder,
    verify_hive_permission_password,
)

# ENGEL_GUIDED_LIBRARY_REVIEW_UI_TAB_V1_IMPORTS_START
from engel_guided_library_review_draft_report import render_draft_report
from engel_guided_library_review_surface import (
    CATEGORIES as GUIDED_LIBRARY_REVIEW_CATEGORIES,
    DRAFT_LABELS as GUIDED_LIBRARY_REVIEW_DRAFT_LABELS,
    REQUIRED_METADATA_FIELDS as GUIDED_LIBRARY_REVIEW_REQUIRED_METADATA_FIELDS,
    RISK_CHECKS as GUIDED_LIBRARY_REVIEW_RISK_CHECKS,
    SAFE_OUTCOMES as GUIDED_LIBRARY_REVIEW_SAFE_OUTCOMES,
)
# ENGEL_GUIDED_LIBRARY_REVIEW_UI_TAB_V1_IMPORTS_END

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
import engel_research_to_fix_loop as research_to_fix_loop
import engel_self_fix_receipt_viewer as self_fix_receipt_viewer
import engel_self_learning_status_surface as self_learning_status_surface
import engel_system_integration_status as system_integration_status
# ENGEL_AI_GROWTH_GUI_TABS_V1_IMPORTS_END


def _resolve_engel_root() -> Path:
    if getattr(sys, "frozen", False):
        exe_path = Path(sys.executable).resolve()
        if (
            exe_path.name.lower() == "engel.exe"
            and exe_path.parent.name.lower() == "app"
            and exe_path.parent.parent.name.lower() == "live"
        ):
            return exe_path.parent.parent.parent
        return exe_path.parent
    return Path(__file__).resolve().parent


ROOT = _resolve_engel_root()
HIVE_ARTWORK_PATH = ROOT / "Engel art work.png"
HIVE_ICON_PATH = ROOT / "assets" / "branding" / "engel_colony_hive_icon.ico"
FALLBACK_ICON_PATH = ROOT / "assets" / "branding" / "engel_icon.ico"
SUPER_SWARM_3D_SCRIPT_PATH = ROOT / "tools" / "engel_super_swarm_hive_3d_scaffold.py"
SUPER_SWARM_3D_EXE_PATH = ROOT / "live" / "app" / "EngelSuperSwarmHive3D.exe"
SUPER_SWARM_3D_PID_PATH = ROOT / "memory" / "engel_super_swarm_hive_3d.pid"
SUPERCOLONY_DISPLAY_ROLES = ["heart", "queen", "worker", "nest", "guardian"]


def _super_swarm_3d_pid_alive(pid: int | None) -> bool:
    try:
        import ctypes
        if not pid:
            return False
        process_query_limited_information = 0x1000
        still_active = 259
        handle = ctypes.windll.kernel32.OpenProcess(process_query_limited_information, False, int(pid))
        if not handle:
            return False
        exit_code = ctypes.c_ulong()
        ok = ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
        ctypes.windll.kernel32.CloseHandle(handle)
        return bool(ok) and exit_code.value == still_active
    except Exception:
        return False


def _read_super_swarm_3d_pid() -> int | None:
    try:
        if SUPER_SWARM_3D_PID_PATH.exists():
            text = SUPER_SWARM_3D_PID_PATH.read_text(encoding="utf-8", errors="replace").strip()
            if text.isdigit():
                return int(text)
    except Exception:
        pass
    return None


def _write_super_swarm_3d_pid(pid: int) -> None:
    try:
        SUPER_SWARM_3D_PID_PATH.parent.mkdir(parents=True, exist_ok=True)
        SUPER_SWARM_3D_PID_PATH.write_text(str(pid), encoding="utf-8")
    except Exception:
        pass


def _clear_super_swarm_3d_pid() -> None:
    try:
        if SUPER_SWARM_3D_PID_PATH.exists():
            SUPER_SWARM_3D_PID_PATH.unlink()
    except Exception:
        pass


def _super_swarm_3d_launch_command() -> tuple[list[str] | None, str]:
    if SUPER_SWARM_3D_EXE_PATH.exists():
        return [str(SUPER_SWARM_3D_EXE_PATH)], "packaged visual executable"

    if not SUPER_SWARM_3D_SCRIPT_PATH.exists():
        return None, "missing visual script"

    pyw = ROOT / ".venv" / "Scripts" / "pythonw.exe"
    py = ROOT / ".venv" / "Scripts" / "python.exe"
    if pyw.exists():
        return [str(pyw), str(SUPER_SWARM_3D_SCRIPT_PATH)], "project pythonw source launcher"
    if py.exists():
        return [str(py), str(SUPER_SWARM_3D_SCRIPT_PATH)], "project python source launcher"
    if not getattr(sys, "frozen", False):
        return [sys.executable, str(SUPER_SWARM_3D_SCRIPT_PATH)], "current Python source launcher"
    return None, "packaged visual executable unavailable"


def _launch_super_swarm_3d_visual() -> tuple[bool, str]:
    pid = _read_super_swarm_3d_pid()
    if _super_swarm_3d_pid_alive(pid):
        return True, "3D Super Swarm Hive is already open.\n\nTracked PID: " + str(pid)

    _clear_super_swarm_3d_pid()
    command, method = _super_swarm_3d_launch_command()
    if not command:
        return False, (
            "The 3D Super Swarm Hive launcher is unavailable.\n\n"
            "Launch method: "
            + method
            + "\n\nScript:\n"
            + str(SUPER_SWARM_3D_SCRIPT_PATH)
            + "\nScript exists: "
            + str(SUPER_SWARM_3D_SCRIPT_PATH.exists())
            + "\n\nPackaged visual executable:\n"
            + str(SUPER_SWARM_3D_EXE_PATH)
            + "\nPackaged visual executable exists: "
            + str(SUPER_SWARM_3D_EXE_PATH.exists())
            + "\n\nStable Colony Hive remains available."
        )

    import subprocess

    flags = 0
    try:
        flags = subprocess.CREATE_NO_WINDOW
    except Exception:
        flags = 0

    proc = subprocess.Popen(command, cwd=str(ROOT), creationflags=flags)
    _write_super_swarm_3d_pid(proc.pid)
    return True, (
        "Opened approved 3D Super Swarm Hive visual mode.\n\n"
        "Tracked PID: "
        + str(proc.pid)
        + "\nLaunch method: "
        + method
        + "\n\nStable Colony Hive remains the default until bundled-runtime smoke passes."
    )


def _label(text: str, size: int = 10, weight: int = 500, color: str = "#eaf5ff") -> QLabel:
    item = QLabel(text)
    item.setWordWrap(True)
    item.setTextInteractionFlags(Qt.TextSelectableByMouse)
    item.setStyleSheet(
        "QLabel {"
        f"color: {color};"
        "background: transparent;"
        "border: 0;"
        "}"
    )
    font = QFont("Segoe UI", size)
    font.setWeight(QFont.Weight(weight))
    item.setFont(font)
    return item


def _pill(text: str, color: str) -> QLabel:
    item = _label(text, 8, 800, color)
    item.setAlignment(Qt.AlignCenter)
    item.setStyleSheet(
        "QLabel {"
        "background: rgba(255, 255, 255, 22);"
        f"border: 1px solid {color};"
        "border-radius: 7px;"
        "padding: 3px 7px;"
        f"color: {color};"
        "}"
    )
    return item


def make_scroll_text(title: str, text: str, min_height: int = 180) -> QFrame:
    frame = QFrame()
    frame.setStyleSheet(
        "QFrame {"
        "background: rgba(4, 14, 20, 210);"
        "border: 1px solid rgba(158, 231, 208, 70);"
        "border-radius: 8px;"
        "}"
    )
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(10, 9, 10, 10)
    layout.setSpacing(7)
    layout.addWidget(_label(title, 9, 900, "#b7ffed"))
    box = QTextEdit()
    box.setReadOnly(True)
    box.setMinimumHeight(min_height)
    box.setMaximumHeight(max(min_height + 34, int(min_height * 1.4)))
    box.setLineWrapMode(QTextEdit.WidgetWidth)
    box.setPlainText(str(text))
    layout.addWidget(box, 1)
    return frame


def make_badge_row(items: list[tuple[str, str]]) -> QWidget:
    host = QWidget()
    layout = QHBoxLayout(host)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(7)
    for text, color in items:
        layout.addWidget(_pill(text, color))
    layout.addStretch(1)
    return host


# ENGEL_AI_GROWTH_GUI_TABS_V1_RESEARCH_OFFICE_START
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


def _render_ai_growth_gui_memory_promotion_status() -> str:
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


def _render_ai_growth_gui_low_risk_self_fix_dry_run_visibility() -> str:
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


def _render_global_password_action_status() -> str:
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
        "- Write/apply/run actions still require password plus action-specific contracts.",
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


def render_ai_growth_gui_tab_text(tab_name: str) -> str:
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
            return _render_global_password_action_status()
        if tab_name == "System Integration":
            return system_integration_status.render_status()
        if tab_name == "Self-Fix":
            return (
                _render_ai_growth_gui_low_risk_self_fix_dry_run_visibility()
                + "\n\n"
                + low_risk_self_fix_status_surface.render_status()
                + "\n\n"
                + self_fix_receipt_viewer.render_receipt_list()
            )
        if tab_name == "Memory Promotion":
            return _render_ai_growth_gui_memory_promotion_status()
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
# ENGEL_AI_GROWTH_GUI_TABS_V1_RESEARCH_OFFICE_END


def _short_session_folder_label(folder: str) -> str:
    value = str(folder).strip()
    if not value:
        return "none"
    try:
        path = Path(value)
        if path.is_absolute():
            try:
                return path.resolve().relative_to(ROOT.resolve()).as_posix()
            except Exception:
                return str(path)
    except Exception:
        pass
    return value


def _queen_link_status_meta(link: dict) -> dict:
    folder = str(link.get("linked_folder", "")).strip()
    folder_status = str(link.get("folder_status", "NO_SESSION_LINK"))
    workers = [str(group) for group in link.get("assigned_worker_groups", [])]
    worker_text = ", ".join(workers) if workers else "none assigned"
    has_session_folder = bool(folder) and folder_status == "LOCAL_FOLDER_READY"
    sent_to_workers = bool(link.get("sent_to_workers"))

    if has_session_folder:
        folder_badge = "SESSION LINKED"
        folder_color = "#86efac"
        folder_text = _short_session_folder_label(folder)
    elif "REQUIRES_APPROVAL" in folder_status:
        folder_badge = "REQUIRES APPROVAL"
        folder_color = "#fbbf24"
        folder_text = "not linked by latest action"
    elif folder_status.startswith("BLOCKED"):
        folder_badge = "BLOCKED"
        folder_color = "#fca5a5"
        folder_text = "blocked"
    else:
        folder_badge = "NO SESSION LINK"
        folder_color = "#cbd5e1"
        folder_text = "none"

    if has_session_folder and sent_to_workers:
        handoff_badge = "WORKERS RECEIVED"
        handoff_color = "#7dd3fc"
        worker_line = "Received by: " + worker_text
    elif has_session_folder:
        handoff_badge = "WORKERS WAITING"
        handoff_color = "#facc15"
        worker_line = "Waiting worker group: " + worker_text
    else:
        handoff_badge = "NOT SENT"
        handoff_color = "#cbd5e1"
        worker_line = "Assigned worker group: " + worker_text

    return {
        "queen_label": str(link.get("queen_label", "Queen")),
        "folder_badge": folder_badge,
        "folder_color": folder_color,
        "folder_text": folder_text,
        "folder_status": folder_status,
        "handoff_badge": handoff_badge,
        "handoff_color": handoff_color,
        "worker_line": worker_line,
    }


class HiveLaneCard(QFrame):
    def __init__(self, lane: dict, count: int, on_select_role) -> None:
        super().__init__()
        accent = lane.get("accent", "#9ee7d0")
        self.setObjectName("HiveLaneCard")
        self.setMinimumHeight(112)
        self.setStyleSheet(
            "QFrame#HiveLaneCard {"
            "background: rgba(5, 16, 22, 232);"
            f"border: 1px solid {accent};"
            "border-radius: 8px;"
            "}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(11, 9, 11, 9)
        layout.setSpacing(6)

        top = QHBoxLayout()
        top.addWidget(_label(str(lane.get("number", "")) + " " + str(lane.get("title", "")).upper(), 9, 900, accent), 1)
        top.addWidget(_pill(str(count) + " CARDS", accent))
        layout.addLayout(top)
        layout.addWidget(_label(str(lane.get("summary", "")), 9, 550, "#d4e6ee"))
        badges = QHBoxLayout()
        badges.addWidget(_pill(str(lane.get("badge", "LOCAL ONLY")), accent))
        inspect = QPushButton("Inspect")
        inspect.clicked.connect(lambda: on_select_role(str(lane.get("role", ""))))
        badges.addWidget(inspect)
        badges.addStretch(1)
        layout.addLayout(badges)


class HiveMindMapPanel(QFrame):
    def __init__(self, snapshot: dict, on_select_role, queen_links: list[dict] | None = None) -> None:
        super().__init__()
        queen_links = list(queen_links or [])
        self.setObjectName("HiveMindMapPanel")
        self.setMinimumHeight(420)
        self.setStyleSheet(
            "QFrame#HiveMindMapPanel {"
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #06131a, stop:0.55 #092329, stop:1 #150f24);"
            "border: 1px solid rgba(133, 238, 224, 110);"
            "border-radius: 10px;"
            "}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QVBoxLayout()
        title.addWidget(_label("ENGEL COLONY HIVE MAP", 17, 900, "#ffffff"))
        title.addWidget(_label("Read-only local colony signal snapshot, inspired by supercolony structure only.", 10, 550, "#b9d9e6"))
        header.addLayout(title, 1)
        for text, color in [
            ("LOCAL ONLY", "#84f48c"),
            ("READ-ONLY-FIRST", "#87cefa"),
            ("GUARDIAN WATCHING", "#c084fc"),
            ("PROPOSAL ONLY", "#fbbf24"),
        ]:
            header.addWidget(_pill(text, color))
        layout.addLayout(header)

        body = QHBoxLayout()
        body.setSpacing(14)

        left = QVBoxLayout()
        left.setSpacing(10)
        mind = snapshot.get("mind_summary", {})
        heart = QFrame()
        heart.setObjectName("ColonyHeart")
        heart.setStyleSheet(
            "QFrame#ColonyHeart {"
            "background: rgba(6, 22, 32, 238);"
            "border: 2px solid rgba(126, 230, 255, 180);"
            "border-radius: 10px;"
            "}"
        )
        heart_layout = QVBoxLayout(heart)
        heart_layout.setContentsMargins(15, 13, 15, 13)
        heart_layout.setSpacing(8)
        heart_layout.addWidget(_label("ENGEL MIND / COLONY HEART", 10, 900, "#a7f3d0"))
        heart_layout.addWidget(_label(str(mind.get("identity", "One cooperative Engel Mind")), 18, 900, "#ffffff"))
        heart_layout.addWidget(_label(str(mind.get("posture", "Local-only, Guardian-gated, proposal-first")), 10, 600, "#d9edf4"))
        heart_badges = QHBoxLayout()
        heart_badges.addWidget(_pill("SAFE MODE ON", "#86efac"))
        heart_badges.addWidget(_pill("NO PROVIDER CALL", "#fca5a5"))
        heart_badges.addWidget(_pill("NO RUNTIME POWER", "#fbbf24"))
        heart_badges.addStretch(1)
        heart_layout.addLayout(heart_badges)
        left.addWidget(heart)

        lanes_grid = QGridLayout()
        lanes_grid.setHorizontalSpacing(10)
        lanes_grid.setVerticalSpacing(10)
        grouped = snapshot.get("grouped_cells", {})
        for index, lane in enumerate(snapshot.get("hive_map_lanes", [])):
            count = len(grouped.get(lane.get("role", ""), []))
            lanes_grid.addWidget(HiveLaneCard(lane, count, on_select_role), index // 2, index % 2)
        left.addLayout(lanes_grid)
        body.addLayout(left, 2)

        right = QVBoxLayout()
        right.setSpacing(10)
        artwork = QLabel()
        artwork.setObjectName("HiveArtwork")
        artwork.setAlignment(Qt.AlignCenter)
        artwork.setMinimumHeight(215)
        artwork.setStyleSheet(
            "QLabel#HiveArtwork {"
            "background: rgba(4, 12, 18, 210);"
            "border: 1px solid rgba(126, 230, 255, 95);"
            "border-radius: 8px;"
            "}"
        )
        if HIVE_ARTWORK_PATH.exists():
            pixmap = QPixmap(str(HIVE_ARTWORK_PATH))
            if not pixmap.isNull():
                artwork.setPixmap(pixmap.scaled(430, 260, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                artwork.setText("Engel artwork could not be loaded.")
        else:
            artwork.setText("Engel artwork is not present.")
        right.addWidget(artwork)

        legend = QFrame()
        legend.setStyleSheet(
            "QFrame {"
            "background: rgba(12, 26, 34, 225);"
            "border: 1px solid rgba(158, 231, 208, 80);"
            "border-radius: 8px;"
            "}"
        )
        legend_layout = QVBoxLayout(legend)
        legend_layout.setContentsMargins(12, 10, 12, 10)
        legend_layout.setSpacing(7)
        legend_layout.addWidget(_label("HIVE SUMMARY", 10, 900, "#e6fff4"))
        legend_layout.addWidget(_label("Colony Identity: One Cooperative Engel Mind", 9, 700, "#d5e8ef"))
        legend_layout.addWidget(_label("Snapshot Mode: READ-ONLY", 9, 700, "#d5e8ef"))
        legend_layout.addWidget(_label("Autonomy: No autonomous loop", 9, 700, "#d5e8ef"))
        legend_layout.addWidget(_label("Network: No network call", 9, 700, "#d5e8ef"))
        legend_layout.addWidget(_label("Provider Calls: None from this screen", 9, 700, "#d5e8ef"))
        legend_layout.addWidget(_label("All outputs are proposal candidates until human-approved.", 9, 800, "#ffe3b3"))
        if queen_links:
            legend_layout.addWidget(_label("QUEEN RESEARCH LINK BADGES", 9, 900, "#b7ffed"))
            for link in queen_links:
                meta = _queen_link_status_meta(link)
                row = QHBoxLayout()
                row.setSpacing(5)
                row.addWidget(_label(str(meta["queen_label"]), 8, 850, "#ffffff"), 1)
                row.addWidget(_pill(str(meta["folder_badge"]), str(meta["folder_color"])))
                row.addWidget(_pill(str(meta["handoff_badge"]), str(meta["handoff_color"])))
                legend_layout.addLayout(row)
                legend_layout.addWidget(_label(str(meta["worker_line"]), 8, 550, "#cbd5e1"))
        right.addWidget(legend)
        body.addLayout(right, 1)

        layout.addLayout(body)


class SuperSwarmHiveCanvas(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.signal_snapshot: dict = {}
        self.hive_snapshot: dict = {}
        self.live_enabled = False
        self.motion_paused = False
        self.reduced_motion = False
        self.phase = 0.0
        self.view_pan_x = 0.0
        self.view_pan_y = 0.0
        self.view_zoom = 1.0
        self._dragging = False
        self._last_drag_pos: QPointF | None = None
        self.layers = {
            "workers": True,
            "nests": True,
            "queens": True,
            "signals": True,
            "guardian": True,
            "proposals": True,
        }
        self.setMinimumHeight(480)
        self.setFocusPolicy(Qt.StrongFocus)
        self.animation_timer = QTimer(self)
        self.animation_timer.setInterval(42)
        self.animation_timer.timeout.connect(self._tick)
        self.setStyleSheet(
            "QWidget {"
            "background: qradialgradient(cx:0.5, cy:0.48, radius:0.9, stop:0 #102e36, stop:0.48 #07151b, stop:1 #120d1c);"
            "border: 1px solid rgba(133, 238, 224, 95);"
            "border-radius: 10px;"
            "}"
        )

    def set_signal_snapshot(self, signal_snapshot: dict) -> None:
        self.signal_snapshot = signal_snapshot
        self.update()

    def set_hive_snapshot(self, hive_snapshot: dict) -> None:
        self.hive_snapshot = hive_snapshot
        self.update()

    def set_layer_enabled(self, layer: str, enabled: bool) -> None:
        self.layers[layer] = enabled
        self.update()

    def set_live_enabled(self, enabled: bool) -> None:
        self.live_enabled = enabled
        self._sync_timer()
        self.update()

    def set_motion_paused(self, paused: bool) -> None:
        self.motion_paused = paused
        self._sync_timer()
        self.update()

    def set_reduced_motion(self, reduced: bool) -> None:
        self.reduced_motion = reduced
        self._sync_timer()
        self.update()

    def stop_motion(self) -> None:
        self.live_enabled = False
        self.animation_timer.stop()
        self.update()

    def pan_left(self) -> None:
        self.view_pan_x -= 24.0
        self.update()

    def pan_right(self) -> None:
        self.view_pan_x += 24.0
        self.update()

    def pan_up(self) -> None:
        self.view_pan_y -= 24.0
        self.update()

    def pan_down(self) -> None:
        self.view_pan_y += 24.0
        self.update()

    def zoom_in(self) -> None:
        self.view_zoom = min(2.1, self.view_zoom + 0.12)
        self.update()

    def zoom_out(self) -> None:
        self.view_zoom = max(0.65, self.view_zoom - 0.12)
        self.update()

    def reset_view(self) -> None:
        self.view_pan_x = 0.0
        self.view_pan_y = 0.0
        self.view_zoom = 1.0
        self.update()

    def fit_to_hive(self) -> None:
        # This 2D canvas already renders to the current bounds;
        # fit keeps default center/scale for the true local snapshot.
        self.reset_view()

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        key = event.key()
        mods = event.modifiers()
        if key == Qt.Key_Left:
            self.pan_left()
            event.accept()
            return
        if key == Qt.Key_Right:
            self.pan_right()
            event.accept()
            return
        if key == Qt.Key_Up:
            self.pan_up()
            event.accept()
            return
        if key == Qt.Key_Down:
            self.pan_down()
            event.accept()
            return
        if key in (Qt.Key_Plus, Qt.Key_Equal) and (mods & Qt.ControlModifier):
            self.zoom_in()
            event.accept()
            return
        if key == Qt.Key_Minus and (mods & Qt.ControlModifier):
            self.zoom_out()
            event.accept()
            return
        if key == Qt.Key_R:
            self.reset_view()
            event.accept()
            return
        if key == Qt.Key_F:
            self.fit_to_hive()
            event.accept()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._last_drag_pos = event.position()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._dragging and self._last_drag_pos is not None:
            delta = event.position() - self._last_drag_pos
            self.view_pan_x += float(delta.x())
            self.view_pan_y += float(delta.y())
            self._last_drag_pos = event.position()
            self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.LeftButton and self._dragging:
            self._dragging = False
            self._last_drag_pos = None
            self.unsetCursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.LeftButton:
            self.fit_to_hive()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event) -> None:  # type: ignore[override]
        delta = event.angleDelta().y()
        if delta > 0:
            self.zoom_in()
            event.accept()
            return
        if delta < 0:
            self.zoom_out()
            event.accept()
            return
        super().wheelEvent(event)

    def _sync_timer(self) -> None:
        should_move = self.live_enabled and not self.motion_paused and not self.reduced_motion
        if should_move and not self.animation_timer.isActive():
            self.animation_timer.start()
        if not should_move and self.animation_timer.isActive():
            self.animation_timer.stop()

    def _tick(self) -> None:
        self.phase = (self.phase + 0.035) % 1.0
        self.update()

    def _color(self, value: str, alpha: int = 255) -> QColor:
        color = QColor(value)
        color.setAlpha(alpha)
        return color

    def _draw_node(self, painter: QPainter, point: QPointF, radius: float, color: str, label: str, alpha: int = 210) -> None:
        painter.setPen(QPen(self._color(color, min(255, alpha + 35)), 1.5))
        painter.setBrush(QBrush(self._color(color, alpha)))
        painter.drawEllipse(point, radius, radius)
        painter.setPen(QPen(self._color("#ecfeff", 235), 1))
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.drawText(QRectF(point.x() - 72, point.y() + radius + 4, 144, 30), Qt.AlignCenter, label)

    def _draw_signal_line(self, painter: QPainter, start: QPointF, end: QPointF, color: str, offset: float = 0.0, dashed: bool = False) -> None:
        pulse = 0.5 + 0.5 * math.sin((self.phase + offset) * math.tau)
        alpha = 70 if not self.live_enabled else int(80 + pulse * 130)
        width = 1.1 if not self.live_enabled else 1.4 + pulse * 1.4
        style = Qt.DashLine if dashed else Qt.SolidLine
        painter.setPen(QPen(self._color(color, alpha), width, style))
        painter.drawLine(start, end)

    def _cell_color(self, cell: dict) -> str:
        role = str(cell.get("role", "nest"))
        if role == "queen":
            return "#c084fc"
        if role == "worker":
            return "#ffb020"
        if role == "guardian":
            return "#a3ff12"
        if role == "proposal":
            return "#fb923c"
        if role == "verifier":
            return "#7dd3fc"
        if role == "heart":
            return "#5eead4"
        return str(cell.get("accent", "#35d6ff"))

    def _role_visible(self, cell: dict) -> bool:
        role = str(cell.get("role", "nest"))
        if role == "worker" and not self.layers.get("workers", True):
            return False
        if role == "nest" and not self.layers.get("nests", True):
            return False
        if role == "queen" and not self.layers.get("queens", True):
            return False
        if role == "guardian" and not self.layers.get("guardian", True):
            return False
        if role == "proposal" and not self.layers.get("proposals", True):
            return False
        return True

    def _group_cells(self) -> dict[str, list[dict]]:
        grouped: dict[str, list[dict]] = {}
        for cell in self.hive_snapshot.get("cells", []):
            colony_id = str(cell.get("colony_id", "local-hive")) or "local-hive"
            grouped.setdefault(colony_id, []).append(cell)
        return grouped

    def _colony_label(self, colony_id: str, cells: list[dict]) -> str:
        for cell in cells:
            value = str(cell.get("nest_name") or cell.get("cell_name") or "").strip()
            if value:
                return value
        return colony_id.replace("-", " ").title()

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        width = max(1, self.width())
        height = max(1, self.height())
        center = QPointF(width * 0.50, height * 0.50)
        signal_snapshot = self.signal_snapshot or {}
        hive_snapshot = self.hive_snapshot or {}
        grouped = self._group_cells()
        cells = list(hive_snapshot.get("cells", []))
        signals = list(signal_snapshot.get("memory_colony_signals", []))
        total = int(signal_snapshot.get("total_signal_strength", 0) or 0)
        warnings = int(signal_snapshot.get("guardian_warning_count", 0) or 0)
        proposals = int(signal_snapshot.get("proposal_candidate_count", 0) or 0)
        verifiers = int(signal_snapshot.get("verifier_signal_count", 0) or 0)
        pulse = 0.0 if not self.live_enabled else math.sin(self.phase * math.tau)

        painter.setPen(QPen(self._color("#0d3b45", 110), 1))
        for x in range(0, width, 58):
            painter.drawLine(x, 0, x, height)
        for y in range(0, height, 42):
            painter.drawLine(0, y, width, y)

        if not cells:
            painter.setPen(QPen(self._color("#dff7ff", 235), 1))
            painter.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
            painter.drawText(
                QRectF(20, 40, width - 40, height - 80),
                Qt.AlignCenter,
                "No local Hive cells are available yet.\nThe true local data structure is empty; no demo colonies are drawn.",
            )
            painter.end()
            return

        colony_ids = sorted(grouped)
        rx = width * 0.32
        ry = height * 0.29
        colony_positions: dict[str, QPointF] = {}
        painter.save()
        painter.translate(center.x(), center.y())
        painter.scale(self.view_zoom, self.view_zoom)
        painter.translate(-center.x(), -center.y())
        painter.translate(self.view_pan_x, self.view_pan_y)
        for index, colony_id in enumerate(colony_ids):
            angle = -math.pi / 2 + (index / max(1, len(colony_ids))) * math.tau
            colony_positions[colony_id] = QPointF(center.x() + math.cos(angle) * rx, center.y() + math.sin(angle) * ry)

        if self.layers.get("signals", True):
            for index, signal in enumerate(hive_snapshot.get("mycelium_signals", [])):
                source = colony_positions.get(str(signal.get("from", "")))
                target = colony_positions.get(str(signal.get("to", "")))
                if source and target:
                    self._draw_signal_line(painter, source, target, "#22d3ee", index * 0.04, dashed=True)

        if self.layers.get("signals", True):
            for index, colony_id in enumerate(colony_ids):
                self._draw_signal_line(painter, center, colony_positions[colony_id], "#35d6ff", index * 0.025)

        heart_radius = 48 + (4 * pulse if self.live_enabled and not self.reduced_motion else 0)
        painter.setPen(QPen(self._color("#7dd3fc", 235), 2.2))
        painter.setBrush(QBrush(self._color("#0e7490", 170)))
        painter.drawEllipse(center, heart_radius, heart_radius)
        painter.setPen(QPen(self._color("#ffffff", 245), 1))
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.drawText(QRectF(center.x() - 86, center.y() - 30, 172, 62), Qt.AlignCenter, "COMMUNICATION QUEEN\nLOCAL CONTRACT")

        for index, colony_id in enumerate(colony_ids):
            colony_cells = grouped[colony_id]
            colony_center = colony_positions[colony_id]
            accent = self._cell_color(colony_cells[0])
            visible_cells = [cell for cell in colony_cells if self._role_visible(cell)]
            if self.layers.get("guardian", True):
                painter.setPen(QPen(self._color("#a3ff12", 90), 1.2, Qt.DashLine))
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(colony_center, 58, 42)
            painter.setPen(QPen(self._color(accent, 170), 1.4))
            painter.setBrush(QBrush(self._color(accent, 42)))
            painter.drawEllipse(colony_center, 42, 30)
            painter.setPen(QPen(self._color("#e9fbff", 235), 1))
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            painter.drawText(QRectF(colony_center.x() - 84, colony_center.y() + 35, 168, 32), Qt.AlignCenter, self._colony_label(colony_id, colony_cells))
            for cell_index, cell in enumerate(visible_cells[:8]):
                node_angle = -math.pi / 2 + (cell_index / max(1, len(visible_cells[:8]))) * math.tau
                node_point = QPointF(colony_center.x() + math.cos(node_angle) * 44, colony_center.y() + math.sin(node_angle) * 31)
                role = str(cell.get("role", "nest"))
                radius = 13 if role == "queen" else 10
                if role == "worker":
                    radius = 8
                if self.layers.get("signals", True):
                    self._draw_signal_line(painter, colony_center, node_point, self._cell_color(cell), cell_index * 0.03)
                label = str(cell.get("cell_name") or ROLE_TITLES.get(role, role)).replace(" Colony", "")
                self._draw_node(painter, node_point, radius, self._cell_color(cell), label[:18], 185)

        if self.layers.get("signals", True) and signals:
            signal_origin = QPointF(width * 0.88, height * 0.50)
            painter.setPen(QPen(self._color("#84cc16", 90), 1.1, Qt.DashLine))
            painter.drawLine(center, signal_origin)
            for index, signal in enumerate(signals[:10]):
                angle = -1.25 + (index / max(1, min(9, len(signals) - 1))) * 2.5
                point = QPointF(signal_origin.x() + math.cos(angle) * width * 0.075, signal_origin.y() + math.sin(angle) * height * 0.28)
                count = int(signal.get("count", 0) or 0)
                growth = int(signal.get("growth_level", 0) or 0)
                self._draw_signal_line(painter, center, point, "#84cc16", index * 0.05)
                self._draw_node(painter, point, 9 + min(10, growth * 2), "#84cc16", str(count), 135 + min(80, growth * 20))

        if self.layers.get("proposals", True) and proposals:
            proposal_point = QPointF(width * 0.78, height * 0.82)
            self._draw_signal_line(painter, center, proposal_point, "#f59e0b", 0.22)
            self._draw_node(painter, proposal_point, 18, "#f59e0b", "PROPOSALS", 185)
            painter.setPen(QPen(self._color("#fed7aa", 235), 1))
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            painter.drawText(
                QRectF(width * 0.66, height * 0.86, width * 0.26, 42),
                Qt.AlignCenter,
                "UNTRUSTED / PROPOSAL ONLY\nHUMAN APPROVAL REQUIRED",
            )

        if self.layers.get("guardian", True):
            guardian_point = QPointF(width * 0.50, height * 0.85)
            warning_pulse = 0.5 + 0.5 * math.sin((self.phase + 0.25) * math.tau)
            guardian_alpha = 130 + (int(warning_pulse * 85) if self.live_enabled and warnings else 0)
            self._draw_node(painter, guardian_point, 18, "#a3ff12", "GUARDIAN", guardian_alpha)

        painter.restore()

        painter.setPen(QPen(self._color("#d1fae5", 235), 1))
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        state = "LIVE ON" if self.live_enabled else "STATIC OFF"
        if self.motion_paused:
            state += " / PAUSED"
        if self.reduced_motion:
            state += " / REDUCED MOTION"
        painter.drawText(
            QRectF(18, 16, width - 36, 36),
            Qt.AlignLeft | Qt.AlignVCenter,
            state
            + " | colonies="
            + str(len(colony_ids))
            + " | cells="
            + str(len(cells))
            + " | signals="
            + str(total)
            + " | warnings="
            + str(warnings)
            + " | verifiers="
            + str(verifiers),
        )


class HiveCellCard(QFrame):
    def __init__(self, cell: dict, on_select, on_open) -> None:
        super().__init__()
        self.cell = cell
        accent = cell.get("accent", "#9ee7d0")
        queen_link_status = cell.get("queen_link_status", {})
        self.setObjectName("HiveCellCard")
        self.setMinimumHeight(292 if queen_link_status else 230)
        self.setStyleSheet(
            "QFrame#HiveCellCard {"
            "background: rgba(8, 20, 24, 232);"
            f"border: 1px solid {accent};"
            "border-radius: 8px;"
            "}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(13, 11, 13, 11)
        layout.setSpacing(7)

        top = QHBoxLayout()
        top.addWidget(_label(str(cell.get("cell_name", "Hive Cell")).upper(), 8, 800, accent), 1)
        status_color = "#c9f7d4" if cell.get("exists") else "#ffdca8"
        status = _label(str(cell.get("status", "UNKNOWN")).replace("_", " "), 8, 800, status_color)
        status.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        top.addWidget(status, 1)
        layout.addLayout(top)

        layout.addWidget(_label(str(cell.get("actor", "Colony Worker")), 14, 850, "#ffffff"))
        layout.addWidget(_label(str(cell.get("nest_name", "")), 9, 750, "#b8d9ff"))
        layout.addWidget(_label(str(cell.get("current_task", "")), 10, 500, "#d2dfed"))

        badges = QHBoxLayout()
        for badge in cell.get("badges", [])[:3]:
            badges.addWidget(_pill(str(badge).replace("_", " "), accent))
        badges.addStretch(1)
        layout.addLayout(badges)

        if queen_link_status:
            layout.addWidget(_label("Queen Research Link", 8, 850, "#b7ffed"))
            queen_badges = QHBoxLayout()
            queen_badges.setSpacing(5)
            queen_badges.addWidget(
                _pill(
                    str(queen_link_status.get("folder_badge", "NO SESSION LINK")),
                    str(queen_link_status.get("folder_color", "#cbd5e1")),
                )
            )
            queen_badges.addWidget(
                _pill(
                    str(queen_link_status.get("handoff_badge", "NOT SENT")),
                    str(queen_link_status.get("handoff_color", "#cbd5e1")),
                )
            )
            queen_badges.addStretch(1)
            layout.addLayout(queen_badges)
            layout.addWidget(_label("Folder: " + str(queen_link_status.get("folder_text", "none")), 8, 600, "#dbeafe"))
            layout.addWidget(_label(str(queen_link_status.get("worker_line", "")), 8, 600, "#cbd5e1"))

        layout.addWidget(_label("Trail: " + str(cell.get("linked_local_artifact", "")), 9, 500, "#aebbd0"))
        layout.addWidget(_label("Signal: " + str(cell.get("signal_type", "")), 9, 600, "#b8f2e6"))
        layout.addWidget(_label("Confidence: " + str(cell.get("confidence_marker", "")), 9, 500, "#f6d6ad"))

        buttons = QHBoxLayout()
        details_button = QPushButton("Details")
        details_button.clicked.connect(lambda: on_select(self.cell))
        open_button = QPushButton("Open Trail")
        open_button.setEnabled(bool(cell.get("exists")))
        open_button.clicked.connect(lambda: on_open(self.cell))
        buttons.addWidget(details_button)
        buttons.addWidget(open_button)
        layout.addStretch(1)
        layout.addLayout(buttons)


class PermissionToggleRow(QFrame):
    def __init__(self, permission: dict) -> None:
        super().__init__()
        self.permission = permission
        self.base_badge = str(permission.get("status_badge", "OFF / BLOCKED"))
        self.requested = False
        self.setObjectName("PermissionToggleRow")
        self.setMinimumHeight(104)
        self.setStyleSheet(
            "QFrame#PermissionToggleRow {"
            "background: rgba(8, 20, 24, 226);"
            "border: 1px solid rgba(158, 231, 208, 70);"
            "border-radius: 8px;"
            "}"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        self.toggle = QPushButton()
        self.toggle.setCheckable(False)
        self.toggle.setMinimumWidth(104)
        self.toggle.setToolTip("Session request/proposal control only. It does not grant runtime permission.")
        self.toggle.clicked.connect(self._request_toggle)
        layout.addWidget(self.toggle)

        text = QVBoxLayout()
        text.setSpacing(4)
        text.addWidget(_label(str(permission.get("label", "")), 11, 850, "#ffffff"))
        text.addWidget(_label(str(permission.get("description", "")), 9, 500, "#c7d8dc"))
        footer = (
            str(permission.get("gate_status", "UNKNOWN"))
            + " | can_execute_from_hive=NO"
        )
        text.addWidget(_label(footer, 8, 700, "#ffe3b3"))
        layout.addLayout(text, 1)

        self.badge = _pill(self.base_badge, self._badge_color(self.base_badge))
        self.badge.setMinimumWidth(190)
        self.badge.setWordWrap(True)
        self.badge.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.badge)
        self._refresh_state()

    def _badge_color(self, text: str) -> str:
        if "READ" in text:
            return "#cdb4db"
        if "PROPOSAL" in text:
            return "#f4a261"
        return "#82e0c2"

    def _request_toggle(self) -> None:
        if self.permission.get("permission_id") == "mycelium_signals":
            return
        if self.requested:
            self.requested = False
            self._refresh_state()
            return
        if not self.permission.get("password_gate_configured"):
            QMessageBox.information(
                self,
                "Hive Safety Permissions",
                "Global password gate is not configured.\n\nSet up a local password gate before protected actions can be enabled.\n\nRun: python engel_global_password_gate.py --setup",
            )
            return
        entered_text, accepted = QInputDialog.getText(
            self,
            "Hive Safety Permissions",
            "Enter the local hive permission password:",
            QLineEdit.Password,
        )
        if not accepted:
            return
        result = request_permission_unlock(str(self.permission.get("permission_id", "")), entered_text)
        if not result.get("ok"):
            QMessageBox.warning(self, "Hive Safety Permissions", "Password rejected. Permission request unchanged.")
            return
        self.requested = True
        self._refresh_state()
        QMessageBox.information(
            self,
            "Hive Safety Permissions",
            "Password unlock only changes this session's request state. It does not enable runtime power.",
        )

    def _refresh_state(self) -> None:
        if self.permission.get("permission_id") == "mycelium_signals":
            text = "READ-ONLY-FIRST"
            button_text = "Read-only"
            self.toggle.setEnabled(False)
        elif self.requested:
            text = "REQUESTED / PROPOSAL ONLY"
            button_text = "Requested"
        else:
            text = self.base_badge
            button_text = "Request"
        self.badge.setText(text)
        self.toggle.setText(button_text)
        color = self._badge_color(text)
        self.badge.setStyleSheet(
            "QLabel {"
            "background: rgba(255, 255, 255, 22);"
            f"border: 1px solid {color};"
            "border-radius: 7px;"
            "padding: 3px 7px;"
            f"color: {color};"
            "}"
        )


class EngelColonyHiveWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.snapshot = {}
        self.mind_connections = build_engel_mind_connections_snapshot(ROOT)
        self.current_cell: dict | None = None
        self.live_signal_snapshot = build_local_hive_signal_snapshot(ROOT)
        self.route_catalog = route_catalog_for_gui()
        self.route_catalog_by_id = {str(entry.get("route_id")): dict(entry) for entry in self.route_catalog}
        self.super_swarm_live_enabled = False
        self.queen_links = {
            link["queen_id"]: dict(link) for link in build_queen_research_link_templates(ROOT)
        }
        self.setWindowTitle("Engel Mind / Colony Hive")
        self.resize(1600, 900)
        self.setMinimumSize(1080, 720)
        icon_path = HIVE_ICON_PATH if HIVE_ICON_PATH.exists() else FALLBACK_ICON_PATH
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.setObjectName(COLONY_HIVE_ROOT_OBJECT_NAME)
        self.setStyleSheet(colony_hive_application_stylesheet())

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 8, 10, 8)
        outer.setSpacing(6)

        header = QHBoxLayout()
        title_block = QVBoxLayout()
        title_block.addWidget(_label("ENGEL MIND / LOCAL SUPERCOLONY", 18, 900, "#ffffff"))
        title_block.addWidget(
            _label(
                "One local companion identity supported by many safe memory colonies, Guardian checks, and Josh's action gates.",
                8,
                500,
                "#a9c9d8",
            )
        )
        header.addLayout(title_block, 1)
        header.addWidget(_pill("GUARDIAN WATCHING", "#a3ff12"))
        header.addWidget(_pill("LOCAL ONLY", "#35d6ff"))
        header.addWidget(_pill("HUMAN COMMANDS ON", "#5eead4"))
        header.addWidget(_pill("PROVIDER OFF", "#c084fc"))
        header.addWidget(_pill("AUTONOMY BLOCKED", "#fbbf24"))
        refresh = QPushButton("Refresh Local Signals")
        refresh.setToolTip("Refreshes local visual/signal snapshots only.")
        refresh.clicked.connect(self.refresh_local_signals)
        header.addWidget(refresh)
        outer.addLayout(header)

        outer.addWidget(self._make_safety_strip())

        self.tabs = QTabWidget()
        hive_tab = QWidget()
        hive_layout = QVBoxLayout(hive_tab)
        self.hive_layout = hive_layout
        hive_layout.setContentsMargins(12, 12, 12, 12)
        hive_layout.setSpacing(14)

        map_snapshot = self._snapshot_with_queen_link_badges(build_colony_hive_snapshot(ROOT))
        self.snapshot = map_snapshot
        self.map_panel = HiveMindMapPanel(map_snapshot, self.show_first_role, list(self.queen_links.values()))
        hive_layout.addWidget(self.map_panel)

        body = QHBoxLayout()
        body.setSpacing(14)

        self.cards_host = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_host)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(14)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.cards_host)
        body.addWidget(scroll, 2)

        details_box = QVBoxLayout()
        details_box.addWidget(_label("SUPERCOLONY CELL DETAILS", 11, 850, "#c8f4e5"))
        self.details = QTextEdit()
        self.details.setReadOnly(True)
        details_box.addWidget(self.details, 1)
        open_selected = QPushButton("Open Selected Local Trail")
        open_selected.clicked.connect(self.open_selected_link)
        details_box.addWidget(open_selected)
        body.addLayout(details_box, 1)
        hive_layout.addLayout(body, 1)

        self.tabs.addTab(self._make_engel_mind_tab(), "Engel Mind")
        self.tabs.addTab(hive_tab, "Hive")
        self.tabs.addTab(self._make_super_swarm_tab(), "Swarm")
        self.tabs.addTab(self._make_route_explorer_tab(), "Routes")
        self.tabs.addTab(self._make_queen_links_tab(), "Queen Links")
        self.tabs.addTab(self._make_guided_library_review_tab(), "Guided Library Review")
        self.tabs.addTab(self._make_permissions_tab(), "Permissions")
        self.tabs.tabBar().setUsesScrollButtons(True)
        try:
            self.tabs.tabBar().setElideMode(Qt.TextElideMode.ElideRight)
        except AttributeError:
            self.tabs.tabBar().setElideMode(Qt.ElideRight)
        for index in range(self.tabs.count()):
            self.tabs.setTabToolTip(index, self.tabs.tabText(index))
        outer.addWidget(self.tabs, 1)
        outer.addWidget(self._make_status_rail())
        self.tabs.currentChanged.connect(self._sync_status_rail_tab)
        self._sync_status_rail_tab(self.tabs.currentIndex())

        self.load_snapshot()

    # ENGEL_AI_GROWTH_GUI_TABS_V1_RESEARCH_OFFICE_WIDGET_START
    def _make_ai_growth_gui_status_tab(self, tab_name: str) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        layout.addWidget(_label(tab_name, 14, 900, "#eafcff"))
        layout.addWidget(
            make_badge_row(
                [
                    ("READ_ONLY_VIEW", "#a3ff12"),
                    ("STATUS_SURFACE_ONLY", "#35d6ff"),
                    ("DRY RUN VISIBILITY ONLY", "#a3ff12"),
                    ("NO APPLY BUTTON", "#fbbf24"),
                    ("NO_ACTION_EXECUTION", "#fbbf24"),
                    ("NO_MEMORY_WRITE", "#fca5a5"),
                    ("NO_SOURCE_MUTATION", "#fca5a5"),
                    ("NO_BACKGROUND_WORKER", "#c084fc"),
                ]
            )
        )
        layout.addWidget(
            _label(
                "Local status text only. No learning run, self-fix apply, memory promotion, provider, network, "
                "browser, model runtime, package refresh, source mutation, verifier update, self-fix policy update, "
                "startup autorun, or background-worker controls are present in this tab.",
                9,
                750,
                "#ffd98a",
            )
        )
        layout.addWidget(make_scroll_text("Local status surface", render_ai_growth_gui_tab_text(tab_name), 430), 1)
        layout.addStretch(1)
        scroll.setWidget(content)
        return scroll
    # ENGEL_AI_GROWTH_GUI_TABS_V1_RESEARCH_OFFICE_WIDGET_END

    def _queen_link_for_cell(self, cell: dict) -> dict | None:
        cell_label = str(cell.get("cell_name", "")).strip().lower()
        for link in self.queen_links.values():
            if str(link.get("queen_label", "")).strip().lower() == cell_label:
                return link
        return None

    def _snapshot_with_queen_link_badges(self, snapshot: dict) -> dict:
        seen: set[int] = set()

        def apply_badge(cell: dict) -> None:
            marker = id(cell)
            if marker in seen:
                return
            seen.add(marker)
            if str(cell.get("role", "")) != "queen":
                return
            link = self._queen_link_for_cell(cell)
            if link:
                cell["queen_link_status"] = _queen_link_status_meta(link)

        for cell in snapshot.get("cells", []):
            apply_badge(cell)
        for cell in snapshot.get("queens", []):
            apply_badge(cell)
        for group in snapshot.get("grouped_cells", {}).values():
            for cell in group:
                apply_badge(cell)
        return snapshot

    def _refresh_map_panel(self) -> None:
        if not hasattr(self, "hive_layout") or not hasattr(self, "map_panel"):
            return
        old_panel = self.map_panel
        index = self.hive_layout.indexOf(old_panel)
        self.hive_layout.removeWidget(old_panel)
        old_panel.deleteLater()
        self.map_panel = HiveMindMapPanel(self.snapshot, self.show_first_role, list(self.queen_links.values()))
        self.hive_layout.insertWidget(index if index >= 0 else 0, self.map_panel)

    def refresh_colony_hive_queen_badges(self) -> None:
        if not hasattr(self, "cards_layout"):
            return
        preferred_cell_id = ""
        if self.current_cell:
            preferred_cell_id = str(self.current_cell.get("id", ""))
        self.load_snapshot(preferred_cell_id=preferred_cell_id)

    def _make_safety_strip(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame {"
            "background: rgba(15, 42, 40, 225);"
            "border: 1px solid rgba(158, 231, 208, 110);"
            "border-radius: 8px;"
            "}"
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(5)
        layout.addWidget(_label("SAFETY MEMBRANE / GUARDIAN LAYER", 7, 900, "#b7ffed"))
        layout.addWidget(
            make_badge_row(
                [
                    ("LOCAL ONLY", "#35d6ff"),
                    ("READ-ONLY FIRST", "#a3ff12"),
                    ("HIVE SUPERCOLONY", "#5eead4"),
                    ("AUTONOMY BLOCKED", "#fbbf24"),
                    ("GUARDIAN ACTIVE", "#c084fc"),
                ]
            )
        )
        return frame

    def _make_status_rail(self) -> QFrame:
        frame = QFrame()
        frame.setMinimumHeight(64)
        frame.setStyleSheet(
            "QFrame {"
            "background: rgba(4, 15, 24, 232);"
            "border: 1px solid rgba(158, 231, 208, 75);"
            "border-radius: 8px;"
            "}"
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(5)
        self.active_tab_badge = _pill("TAB: Engel Mind", "#35d6ff")
        self.snapshot_count_badge = _pill("CELLS: --", "#a3ff12")
        self.signal_count_badge = _pill("SIGNALS: --", "#ffb020")
        self.report_count_badge = _pill("REPORTS: --", "#c084fc")
        top = QHBoxLayout()
        top.setSpacing(8)
        for widget in [_label("SESSION", 8, 900, "#a9c9d8"), _pill("LOCAL GUI", "#35d6ff"), self.active_tab_badge]:
            top.addWidget(widget)
        top.addStretch(1)
        layout.addLayout(top)
        bottom = QHBoxLayout()
        bottom.setSpacing(8)
        for widget in [
            self.snapshot_count_badge,
            self.signal_count_badge,
            _pill("LOCAL SNAPSHOT", "#a3ff12"),
            _pill("SUPERCOLONY", "#5eead4"),
            _pill("AUTONOMY BLOCKED", "#fbbf24"),
        ]:
            bottom.addWidget(widget)
        bottom.addStretch(1)
        layout.addLayout(bottom)
        return frame

    def _sync_status_rail_tab(self, index: int) -> None:
        if not hasattr(self, "active_tab_badge") or not hasattr(self, "tabs"):
            return
        tab_name = self.tabs.tabText(index) if index >= 0 else "Unknown"
        self.active_tab_badge.setText("TAB: " + tab_name)

    def _sync_status_rail_counts(self) -> None:
        if not hasattr(self, "snapshot_count_badge"):
            return
        snapshot = self.snapshot if isinstance(self.snapshot, dict) else {}
        live = self.live_signal_snapshot if isinstance(self.live_signal_snapshot, dict) else {}
        cells = len(snapshot.get("cells", []))
        signals = len(snapshot.get("mycelium_signals", []))
        reports = int(live.get("report_count", 0) or 0)
        self.snapshot_count_badge.setText(f"CELLS: {cells}")
        self.signal_count_badge.setText(f"SIGNALS: {signals}")
        self.report_count_badge.setText(f"REPORTS: {reports}")
        self.snapshot_count_badge.setToolTip("True local Hive cell records currently loaded in the GUI snapshot.")
        self.signal_count_badge.setToolTip("True local mycelium signal records currently loaded in the GUI snapshot.")
        self.report_count_badge.setToolTip("True local report count from the bounded local signal snapshot.")

    def _mind_badge_color(self, state: str) -> str:
        text = str(state).upper()
        if "CONNECTED" in text:
            return "#86efac"
        if "LOCAL" in text:
            return "#35d6ff"
        if "READ" in text:
            return "#5eead4"
        if "DISABLED" in text or "BLOCKED" in text:
            return "#fb7185"
        if "SCAFFOLD" in text or "CONTRACT" in text:
            return "#c084fc"
        if "REPORT" in text:
            return "#fbbf24"
        if "APPROVAL" in text or "REVIEW" in text:
            return "#fdba74"
        return "#d8fff2"

    def _make_mind_panel(self, title: str, lines: list[str], accent: str = "#35d6ff") -> QFrame:
        panel = QFrame()
        panel.setStyleSheet(
            "QFrame {"
            "background: rgba(4, 15, 24, 232);"
            f"border: 1px solid {accent};"
            "border-radius: 8px;"
            "}"
        )
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(7)
        layout.addWidget(_label(title, 10, 900, accent))
        for line in lines:
            layout.addWidget(_label(line, 9, 600, "#e6f7ff"))
        return panel

    def _make_colony_status_row(self, colony: dict) -> QFrame:
        row = QFrame()
        row.setStyleSheet(
            "QFrame {"
            "background: rgba(5, 16, 22, 230);"
            "border: 1px solid rgba(158, 231, 208, 75);"
            "border-radius: 8px;"
            "}"
        )
        layout = QVBoxLayout(row)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(5)

        top = QHBoxLayout()
        top.setSpacing(7)
        top.addWidget(_label(str(colony.get("name", "Local Colony")), 10, 900, "#ffffff"), 1)
        for state in colony.get("states", []):
            top.addWidget(_pill(str(state), self._mind_badge_color(str(state))))
        path_state = str(colony.get("path_state", "unknown")).upper()
        top.addWidget(_pill(path_state, self._mind_badge_color(path_state)))
        layout.addLayout(top)

        layout.addWidget(_label("Role: " + str(colony.get("role", "")), 8, 650, "#d8fff2"))
        layout.addWidget(_label("Guardrail: " + str(colony.get("guardrail", "")), 8, 650, "#f4e6ff"))
        layout.addWidget(_label("Command hint: " + str(colony.get("command", "")), 8, 700, "#b7ffed"))
        return row

    def _make_future_upgrade_row(self, upgrade: dict) -> QFrame:
        row = QFrame()
        row.setStyleSheet(
            "QFrame {"
            "background: rgba(11, 16, 28, 232);"
            "border: 1px solid rgba(251, 191, 36, 90);"
            "border-radius: 8px;"
            "}"
        )
        layout = QVBoxLayout(row)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(5)

        top = QHBoxLayout()
        top.setSpacing(7)
        top.addWidget(_label(str(upgrade.get("name", "Future Upgrade")), 10, 900, "#ffffff"), 1)
        for state in str(upgrade.get("states", "")).split(","):
            state = state.strip()
            if state:
                top.addWidget(_pill(state, self._mind_badge_color(state)))
        layout.addLayout(top)

        layout.addWidget(_label("Surface: " + str(upgrade.get("surface", "")), 8, 700, "#b7ffed"))
        layout.addWidget(_label("Ready: " + str(upgrade.get("readiness", "")), 8, 650, "#d8fff2"))
        layout.addWidget(_label("Next: " + str(upgrade.get("next_step", "")), 8, 650, "#fef3c7"))
        layout.addWidget(_label("Guardrail: " + str(upgrade.get("guardrail", "")), 8, 650, "#f4e6ff"))
        return row

    def _set_mind_status_text(self, text: str) -> None:
        if hasattr(self, "mind_status_box"):
            self.mind_status_box.setPlainText(str(text))

    def _show_mind_overview(self) -> None:
        self._set_mind_status_text(render_engel_mind_connections_status(ROOT))

    def _show_mind_command_hints(self) -> None:
        snapshot = self.mind_connections if isinstance(self.mind_connections, dict) else {}
        lines = [
            "# Engel Mind Command Hints",
            "",
            "These are existing local/status surfaces. Use them from Companion chat or Human Command Mode.",
            "",
        ]
        for surface in snapshot.get("command_surfaces", []):
            lines.append(
                "- "
                + str(surface.get("label", ""))
                + " | "
                + str(surface.get("state", ""))
                + " | "
                + str(surface.get("command", ""))
                + " | "
                + str(surface.get("note", ""))
            )
        lines.extend(
            [
                "",
                "Gate reminder:",
                "- Engel may observe, summarize, compare, and propose.",
                "- Josh is highest approval authority.",
                "- Guardian reviews and blocks unsafe paths below Josh.",
                "- Engel/runtime systems remain below both before anything crosses a gate.",
            ]
        )
        self._set_mind_status_text("\n".join(lines))

    def _show_future_upgrades(self) -> None:
        self._set_mind_status_text(render_future_upgrades_status(ROOT))

    def _refresh_engel_mind_connections(self) -> None:
        self.mind_connections = build_engel_mind_connections_snapshot(ROOT)
        self._show_mind_overview()

    def _make_engel_mind_tab(self) -> QWidget:
        tab = QScrollArea()
        tab.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        snapshot = self.mind_connections if isinstance(self.mind_connections, dict) else build_engel_mind_connections_snapshot(ROOT)
        identity = snapshot.get("identity", {})

        hero = QFrame()
        hero.setStyleSheet(
            "QFrame {"
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #092329, stop:0.62 #06131a, stop:1 #1b1024);"
            "border: 1px solid rgba(133, 238, 224, 120);"
            "border-radius: 8px;"
            "}"
        )
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(16, 14, 16, 14)
        hero_layout.setSpacing(9)
        hero_layout.addWidget(_label("ENGEL MIND", 20, 900, "#ffffff"))
        hero_layout.addWidget(
            _label(
                "Local Supercolony: one companion identity, many safe local memory colonies, authority order fixed as Josh first, Guardian second, Engel below gates.",
                11,
                700,
                "#d8fff2",
            )
        )
        hero_layout.addWidget(
            make_badge_row(
                [
                    ("ONE COMPANION IDENTITY", "#86efac"),
                    ("MANY LOCAL COLONIES", "#35d6ff"),
                    ("READ-ONLY FIRST", "#5eead4"),
                    ("GUARDIAN GATED", "#c084fc"),
                    ("JOSH APPROVES ACTIONS", "#fbbf24"),
                ]
            )
        )
        hero_layout.addWidget(_label(str(identity.get("analogy", "")), 9, 550, "#b9d9e6"))
        layout.addWidget(hero)

        top_grid = QGridLayout()
        top_grid.setHorizontalSpacing(10)
        top_grid.setVerticalSpacing(10)
        top_grid.addWidget(
            self._make_mind_panel(
                "Colony Identity",
                [
                    str(identity.get("name", "Engel Mind")),
                    str(identity.get("frame", "Local Supercolony")),
                    str(identity.get("one_identity", "One Companion Identity")),
                    str(identity.get("many_colonies", "Many Safe Local Memory Colonies")),
                    str(identity.get("gate_hierarchy", "Josh First / Guardian Safety / Engel Gated")),
                ],
                "#86efac",
            ),
            0,
            0,
        )
        top_grid.addWidget(
            self._make_mind_panel(
                "Cooperative Intelligence",
                [
                    item["capability"] + ": " + item["state"]
                    for item in snapshot.get("safe_capabilities", [])[:5]
                ],
                "#35d6ff",
            ),
            0,
            1,
        )
        top_grid.addWidget(
            self._make_mind_panel(
                "Guardian Safety",
                [boundary for boundary in snapshot.get("guardian_boundaries", [])[:6]],
                "#fb7185",
            ),
            1,
            0,
        )
        top_grid.addWidget(
            self._make_mind_panel(
                "Action Gates",
                [
                    gate["level"] + ": " + gate["state"]
                    for gate in snapshot.get("action_gates", [])
                ],
                "#fbbf24",
            ),
            1,
            1,
        )
        layout.addLayout(top_grid)

        colonies_panel = QFrame()
        colonies_panel.setStyleSheet(
            "QFrame {"
            "background: rgba(3, 13, 24, 235);"
            "border: 1px solid rgba(94, 234, 212, 100);"
            "border-radius: 8px;"
            "}"
        )
        colonies_layout = QVBoxLayout(colonies_panel)
        colonies_layout.setContentsMargins(12, 10, 12, 12)
        colonies_layout.setSpacing(10)
        colonies_layout.addWidget(_label("LOCAL MEMORY COLONIES", 13, 900, "#ffffff"))
        colonies_layout.addWidget(
            _label(
                "Honest connection states for the local nests, workers, queens, trails, and status-only surfaces that support Engel.",
                9,
                600,
                "#d8fff2",
            )
        )
        colony_grid = QGridLayout()
        colony_grid.setHorizontalSpacing(8)
        colony_grid.setVerticalSpacing(8)
        for index, colony in enumerate(snapshot.get("colonies", [])):
            colony_grid.addWidget(self._make_colony_status_row(colony), index // 2, index % 2)
        colonies_layout.addLayout(colony_grid)
        layout.addWidget(colonies_panel)

        future_panel = QFrame()
        future_panel.setStyleSheet(
            "QFrame {"
            "background: rgba(12, 14, 28, 235);"
            "border: 1px solid rgba(251, 191, 36, 105);"
            "border-radius: 8px;"
            "}"
        )
        future_layout = QVBoxLayout(future_panel)
        future_layout.setContentsMargins(12, 10, 12, 12)
        future_layout.setSpacing(10)
        future_layout.addWidget(_label("FUTURE UPGRADE READINESS", 13, 900, "#ffffff"))
        future_layout.addWidget(
            _label(
                "Future upgrades are connected for review and next-step planning only. Nothing here auto-enables a future system.",
                9,
                600,
                "#fef3c7",
            )
        )
        future_grid = QGridLayout()
        future_grid.setHorizontalSpacing(8)
        future_grid.setVerticalSpacing(8)
        for index, upgrade in enumerate(snapshot.get("future_upgrades", [])):
            future_grid.addWidget(self._make_future_upgrade_row(upgrade), index // 2, index % 2)
        future_layout.addLayout(future_grid)
        layout.addWidget(future_panel)

        command_panel = QFrame()
        command_panel.setStyleSheet(
            "QFrame {"
            "background: rgba(6, 18, 30, 232);"
            "border: 1px solid rgba(53, 214, 255, 95);"
            "border-radius: 8px;"
            "}"
        )
        command_layout = QVBoxLayout(command_panel)
        command_layout.setContentsMargins(12, 10, 12, 12)
        command_layout.setSpacing(8)
        command_layout.addWidget(_label("HIVE CONNECTIONS / UPGRADE CONNECTIONS", 12, 900, "#ffffff"))
        actions = QHBoxLayout()
        actions.setSpacing(8)
        refresh = QPushButton("Refresh Mind Status")
        refresh.setToolTip("Refresh this read-only local connection snapshot")
        refresh.clicked.connect(self._refresh_engel_mind_connections)
        actions.addWidget(refresh)
        overview = QPushButton("Show Upgrade Status")
        overview.setToolTip("Show the same read-only connection map as `upgrade connections status`")
        overview.clicked.connect(self._show_mind_overview)
        actions.addWidget(overview)
        future = QPushButton("Show Future Upgrades")
        future.setToolTip("Show future upgrade readiness without enabling future systems")
        future.clicked.connect(self._show_future_upgrades)
        actions.addWidget(future)
        hints = QPushButton("Show Command Hints")
        hints.setToolTip("Show existing local-only/status command hints")
        hints.clicked.connect(self._show_mind_command_hints)
        actions.addWidget(hints)
        actions.addStretch(1)
        command_layout.addLayout(actions)
        self.mind_status_box = QTextEdit()
        self.mind_status_box.setReadOnly(True)
        self.mind_status_box.setMinimumHeight(260)
        self.mind_status_box.setLineWrapMode(QTextEdit.WidgetWidth)
        command_layout.addWidget(self.mind_status_box)
        layout.addWidget(command_panel)

        tab.setWidget(content)
        self._show_mind_overview()
        return tab

    def _make_super_swarm_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        header = QHBoxLayout()
        title = QVBoxLayout()
        title.addWidget(_label("SUPER SWARM HIVE LIVE", 14, 900, "#ffffff"))
        title.addWidget(_label(SUPER_SWARM_LIVE_COPY, 9, 650, "#d8fff2"))
        header.addLayout(title, 1)

        self.super_swarm_live_button = QPushButton("Super Swarm Hive Live: OFF")
        self.super_swarm_live_button.setMinimumHeight(30)
        self.super_swarm_live_button.setCheckable(True)
        self.super_swarm_live_button.clicked.connect(self.toggle_super_swarm_live)
        header.addWidget(self.super_swarm_live_button)
        self.open_super_swarm_3d_button = QPushButton("Open 3D Super Swarm")
        self.open_super_swarm_3d_button.setMinimumHeight(30)
        self.open_super_swarm_3d_button.setToolTip("Open the approved local PyQt6/OpenGL visual mode in a separate process")
        self.open_super_swarm_3d_button.clicked.connect(self.open_super_swarm_3d_visual)
        header.addWidget(self.open_super_swarm_3d_button)
        layout.addLayout(header)

        controls = QHBoxLayout()
        self.refresh_live_button = QPushButton("Refresh Local Signals")
        self.refresh_live_button.setMinimumHeight(30)
        self.refresh_live_button.clicked.connect(self.refresh_local_signals)
        controls.addWidget(self.refresh_live_button)
        self.pause_motion_button = QPushButton("Pause Motion")
        self.pause_motion_button.setMinimumHeight(30)
        self.pause_motion_button.setCheckable(True)
        self.pause_motion_button.clicked.connect(self.toggle_pause_motion)
        controls.addWidget(self.pause_motion_button)
        self.reduced_motion_button = QPushButton("Reduced Motion")
        self.reduced_motion_button.setMinimumHeight(30)
        self.reduced_motion_button.setCheckable(True)
        self.reduced_motion_button.clicked.connect(self.toggle_reduced_motion)
        controls.addWidget(self.reduced_motion_button)
        controls.addStretch(1)
        layout.addLayout(controls)

        self.live_canvas = SuperSwarmHiveCanvas()
        self.live_canvas.set_signal_snapshot(self.live_signal_snapshot)
        self.live_canvas.set_hive_snapshot(self.snapshot)

        map_row = QHBoxLayout()
        map_row.setSpacing(10)
        map_row.addWidget(self.live_canvas, 1)
        side_host = QWidget()
        side_host.setMaximumWidth(240)
        side_layout = QVBoxLayout(side_host)
        side_layout.setContentsMargins(0, 0, 0, 0)
        side_layout.setSpacing(10)
        side_layout.addWidget(self._make_super_swarm_layer_panel())
        side_layout.addWidget(self._make_super_swarm_safety_panel())
        side_layout.addStretch(1)
        map_row.addWidget(side_host)
        layout.addLayout(map_row, 1)
        layout.addWidget(
            _label(
                "View controls: drag map to pan, mouse wheel to zoom, double-click to fit, arrow keys to pan, Ctrl +/- to zoom, R reset, F fit.",
                8,
                650,
                "#9ec7d7",
            )
        )

        bottom = QHBoxLayout()
        self.live_summary = QTextEdit()
        self.live_summary.setReadOnly(True)
        self.live_summary.setMinimumHeight(120)
        self.live_summary.setStyleSheet("font-size:9.5pt;")
        self.live_summary.setLineWrapMode(QTextEdit.WidgetWidth)
        bottom.addWidget(self.live_summary, 1)
        layout.addLayout(bottom)
        self._update_live_summary()
        return tab

    def _make_route_explorer_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        summary = route_catalog_summary(self.route_catalog)
        header = QHBoxLayout()
        title = QVBoxLayout()
        title.addWidget(_label("ENGEL ROUTE EXPLORER", 15, 900, "#ffffff"))
        title.addWidget(
            _label(
                "All Engel AI routes from the live registry. Search, choose, and run without memorizing command phrases.",
                9,
                650,
                "#d8fff2",
            )
        )
        header.addLayout(title, 1)
        header.addWidget(_pill("ROUTES: " + str(summary.get("route_count", 0)), "#35d6ff"))
        header.addWidget(_pill("ALIASES: " + str(summary.get("alias_count", 0)), "#a3ff12"))
        header.addWidget(_pill("ONE ROUTER", "#5eead4"))
        layout.addLayout(header)

        layout.addWidget(
            make_badge_row(
                [
                    ("ENGEL_AI_UPDATE_ROUTES", "#35d6ff"),
                    ("SEARCHABLE", "#a3ff12"),
                    ("STATUS ROUTES SAFE", "#5eead4"),
                    ("ACTION ROUTES CONFIRM FIRST", "#fbbf24"),
                    ("NO SECOND ROUTER", "#c084fc"),
                ]
            )
        )

        controls = QGridLayout()
        controls.setHorizontalSpacing(8)
        controls.setVerticalSpacing(8)
        controls.addWidget(_label("Search", 8, 850, "#b7ffed"), 0, 0)
        self.route_search = QLineEdit()
        self.route_search.setPlaceholderText("Type status, WSL, graph, memory, agent...")
        self.route_search.textChanged.connect(self._refresh_route_explorer_options)
        controls.addWidget(self.route_search, 0, 1, 1, 3)

        controls.addWidget(_label("Group", 8, 850, "#b7ffed"), 1, 0)
        self.route_group_filter = QComboBox()
        self.route_group_filter.addItem("All")
        for group in route_catalog_groups(self.route_catalog):
            self.route_group_filter.addItem(group)
        self.route_group_filter.currentTextChanged.connect(self._refresh_route_explorer_options)
        controls.addWidget(self.route_group_filter, 1, 1)

        controls.addWidget(_label("Route", 8, 850, "#b7ffed"), 1, 2)
        self.route_select = QComboBox()
        self.route_select.setMinimumWidth(520)
        self.route_select.currentIndexChanged.connect(self._show_selected_route_details)
        controls.addWidget(self.route_select, 1, 3)
        layout.addLayout(controls)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        details = QPushButton("Show Details")
        details.setToolTip("Show route ID, target, mode, safety, and accepted phrases")
        details.clicked.connect(self._show_selected_route_details)
        actions.addWidget(details)
        run = QPushButton("Run Selected Route")
        run.setToolTip("Run the selected route through Engel's existing router")
        run.clicked.connect(self._run_selected_route)
        actions.addWidget(run)
        all_routes = QPushButton("Show All Routes")
        all_routes.setToolTip("Render the full Engel Route Explorer catalog")
        all_routes.clicked.connect(self._show_all_route_explorer)
        actions.addWidget(all_routes)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.route_output = QTextEdit()
        self.route_output.setReadOnly(True)
        self.route_output.setMinimumHeight(360)
        self.route_output.setLineWrapMode(QTextEdit.WidgetWidth)
        layout.addWidget(self.route_output, 1)

        self._refresh_route_explorer_options()
        return tab

    def _route_filter_state(self) -> tuple[str, str]:
        search = self.route_search.text() if hasattr(self, "route_search") else ""
        group = self.route_group_filter.currentText() if hasattr(self, "route_group_filter") else "All"
        return search, group

    def _refresh_route_explorer_options(self) -> None:
        if not hasattr(self, "route_select"):
            return
        current_route = str(self.route_select.currentData() or "")
        search, group = self._route_filter_state()
        rows = filter_route_catalog(search, group)
        self.route_select.blockSignals(True)
        self.route_select.clear()
        for entry in rows:
            mode = str(entry.get("mode", "")).upper()
            text = mode + " | " + str(entry.get("group", "")) + " | " + str(entry.get("label", ""))
            self.route_select.addItem(text[:180], str(entry.get("route_id", "")))
        if current_route:
            index = self.route_select.findData(current_route)
            if index >= 0:
                self.route_select.setCurrentIndex(index)
        self.route_select.blockSignals(False)
        if rows:
            self._show_selected_route_details()
        elif hasattr(self, "route_output"):
            self.route_output.setPlainText(
                "# Engel Route Explorer\n\nNo routes matched this search. Clear the search box or choose All groups."
            )

    def _selected_route_entry(self) -> dict | None:
        if not hasattr(self, "route_select"):
            return None
        route_id = str(self.route_select.currentData() or "")
        if not route_id:
            return None
        return self.route_catalog_by_id.get(route_id)

    def _show_selected_route_details(self) -> None:
        if not hasattr(self, "route_output"):
            return
        entry = self._selected_route_entry()
        if not entry:
            self.route_output.setPlainText("# Engel Route Explorer\n\nSelect a route to inspect it.")
            return
        self.route_output.setPlainText(render_route_details(str(entry.get("route_id", ""))))

    def _show_all_route_explorer(self) -> None:
        if hasattr(self, "route_output"):
            self.route_output.setPlainText(render_route_explorer())

    def _run_selected_route(self) -> None:
        entry = self._selected_route_entry()
        if not entry or not hasattr(self, "route_output"):
            return
        phrase = str(entry.get("primary_alias", "") or entry.get("route_id", ""))
        if str(entry.get("mode", "")) == "action":
            answer = QMessageBox.question(
                self,
                "Run Engel Action Route",
                "This selected route is an explicit action route. It may start a bounded process, copy approved config, or run a fixed WSL command through Engel AI.\n\nRun it now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                self.route_output.setPlainText(
                    "# Engel Route Explorer\n\nAction route was not run.\n\nSelected: " + str(entry.get("label", ""))
                )
                return
        try:
            from engel_communication_router import route_companion_text_or_command

            routed = route_companion_text_or_command(phrase, context="ENGEL_SUPER_SWARM_ROUTE_EXPLORER")
            response = routed.response or "Engel did not produce a response for this route."
            self.route_output.setPlainText(
                "\n".join(
                    [
                        "# Engel Route Result",
                        "",
                        "Phrase: " + phrase,
                        "Route ID: " + str(routed.route_target or entry.get("route_id", "")),
                        "Handled: " + str(bool(routed.handled)),
                        "Mode: " + str(entry.get("mode", "")),
                        "",
                        response,
                    ]
                )
            )
        except Exception as exc:
            self.route_output.setPlainText(
                "# Engel Route Explorer\n\nRoute execution failed safely.\n\nError: " + type(exc).__name__ + ": " + str(exc)
            )

    def _make_super_swarm_layer_panel(self) -> QFrame:
        panel = QFrame()
        panel.setMinimumWidth(168)
        panel.setMaximumWidth(210)
        panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        panel.setStyleSheet(
            "QFrame {"
            "background: rgba(4, 15, 24, 232);"
            "border: 1px solid rgba(53, 214, 255, 95);"
            "border-radius: 8px;"
            "}"
        )
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(11, 11, 11, 11)
        layout.setSpacing(8)
        layout.addWidget(_label("SUPERCOLONY LAYERS", 9, 900, "#35d6ff"))
        self.super_swarm_layer_boxes = {}
        for key, text in [
            ("workers", "Worker Cells"),
            ("nests", "Nests"),
            ("queens", "Queens"),
            ("signals", "Signals"),
            ("guardian", "Guardian Layer"),
        ]:
            checkbox = QCheckBox(text)
            checkbox.setChecked(True)
            checkbox.toggled.connect(lambda checked, layer=key: self._set_super_swarm_layer(layer, checked))
            layout.addWidget(checkbox)
            self.super_swarm_layer_boxes[key] = checkbox
        layout.addWidget(_label("LEGEND", 9, 900, "#cfefff"))
        for name, color in [
            ("Nest", "#35d6ff"),
            ("Queen", "#c084fc"),
            ("Worker Ant", "#ffb020"),
            ("Signal", "#35d6ff"),
            ("Guardian", "#a3ff12"),
        ]:
            layout.addWidget(_label(name, 8, 700, color))
        layout.addStretch(1)
        return panel

    def _make_super_swarm_safety_panel(self) -> QFrame:
        safety = QFrame()
        safety.setMinimumWidth(188)
        safety.setMaximumWidth(230)
        safety.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        safety.setStyleSheet(
            "QFrame {"
            "background: rgba(37, 18, 30, 225);"
            "border: 1px solid rgba(251, 113, 133, 120);"
            "border-radius: 8px;"
            "}"
        )
        layout = QVBoxLayout(safety)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(9)
        layout.addWidget(_label("ENGEL ASSISTANT", 11, 900, "#ffffff"))
        layout.addWidget(make_badge_row([("SAFE + IDLE", "#a3ff12"), ("MONITORING", "#35d6ff")]))
        layout.addWidget(
            _label(
                "2D Super Swarm map reads the true local Hive snapshot. Empty layers stay empty.",
                9,
                650,
                "#dff7ff",
            )
        )
        layout.addWidget(_label("GUARDIAN LIVE BOUNDARY", 10, 900, "#fecdd3"))
        layout.addWidget(
            make_scroll_text(
                "Boundary details",
                "\n".join(
                    [
                        "Hive Live ON means GUI animation + bounded local read-only signal refresh.",
                        "No background service.",
                        "No autonomous loop.",
                        "No queue, route, trusted-memory, source, or learning mutation.",
                        "No browsing, provider call, or network call.",
                        "Proposals remain untrusted until human-approved.",
                    ]
                ),
                96,
            ),
            1,
        )
        return safety

    def _make_super_swarm_view_controls_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(
            "QFrame {"
            "background: rgba(8, 20, 24, 228);"
            "border: 1px solid rgba(53, 214, 255, 95);"
            "border-radius: 8px;"
            "}"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)
        layout.addWidget(_label("VIEW CONTROLS", 9, 900, "#35d6ff"))

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)

        up = QPushButton("PAN ↑")
        up.setToolTip("Pan map up")
        up.clicked.connect(lambda: self.live_canvas.pan_up())
        grid.addWidget(up, 0, 0)

        fit = QPushButton("FIT")
        fit.setToolTip("Fit map to default local Hive framing")
        fit.clicked.connect(lambda: self.live_canvas.fit_to_hive())
        grid.addWidget(fit, 0, 1)

        left = QPushButton("PAN ←")
        left.setToolTip("Pan map left")
        left.clicked.connect(lambda: self.live_canvas.pan_left())
        grid.addWidget(left, 1, 0)

        reset = QPushButton("RESET")
        reset.setToolTip("Reset map pan and zoom")
        reset.clicked.connect(lambda: self.live_canvas.reset_view())
        grid.addWidget(reset, 1, 1)

        right = QPushButton("PAN →")
        right.setToolTip("Pan map right")
        right.clicked.connect(lambda: self.live_canvas.pan_right())
        grid.addWidget(right, 1, 2)

        down = QPushButton("PAN ↓")
        down.setToolTip("Pan map down")
        down.clicked.connect(lambda: self.live_canvas.pan_down())
        grid.addWidget(down, 2, 0)

        zoom_in = QPushButton("ZOOM +")
        zoom_in.setToolTip("Zoom in")
        zoom_in.clicked.connect(lambda: self.live_canvas.zoom_in())
        grid.addWidget(zoom_in, 2, 1)

        zoom_out = QPushButton("ZOOM -")
        zoom_out.setToolTip("Zoom out")
        zoom_out.clicked.connect(lambda: self.live_canvas.zoom_out())
        grid.addWidget(zoom_out, 2, 2)

        layout.addLayout(grid)

        center = QPushButton("CENTER SELECTED")
        center.setEnabled(False)
        center.setToolTip("Not available in this 2D panel: no selected-node camera target is tracked here.")
        layout.addWidget(center)
        return card

    def _set_super_swarm_layer(self, layer: str, checked: bool) -> None:
        if hasattr(self, "live_canvas"):
            self.live_canvas.set_layer_enabled(layer, checked)

    def _make_queen_links_tab(self) -> QWidget:
        tab = QScrollArea()
        tab.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        layout.addWidget(_label("QUEEN RESEARCH LINKS", 16, 900, "#ffffff"))
        layout.addWidget(
            _label(
                "Session-only local folder links for Queen-to-worker visual handoffs. Workers receive read-only context paths, not jobs.",
                10,
                700,
                "#d8fff2",
            )
        )

        ribbon = QFrame()
        ribbon.setMinimumHeight(130)
        ribbon.setStyleSheet(
            "QFrame {"
            "background: rgba(13, 31, 34, 230);"
            "border: 1px solid rgba(158, 231, 208, 90);"
            "border-radius: 8px;"
            "}"
        )
        ribbon_layout = QVBoxLayout(ribbon)
        ribbon_layout.setContentsMargins(12, 10, 12, 10)
        ribbon_layout.setSpacing(8)
        select_row = QHBoxLayout()
        select_row.setSpacing(8)
        select_row.addWidget(_label("Select Queen", 9, 850, "#b7ffed"))
        self.queen_select = QComboBox()
        self.queen_select.setMinimumWidth(200)
        for link in self.queen_links.values():
            self.queen_select.addItem(str(link["queen_label"]), str(link["queen_id"]))
        self.queen_select.currentIndexChanged.connect(self.update_queen_links_view)
        select_row.addWidget(self.queen_select)
        select_row.addStretch(1)
        ribbon_layout.addLayout(select_row)

        action_grid = QGridLayout()
        action_grid.setHorizontalSpacing(8)
        action_grid.setVerticalSpacing(8)
        for index, (text, callback) in enumerate([
            ("Link Research Folder", self.link_queen_research_folder),
            ("View Linked Folder", self.view_queen_linked_folder),
            ("Clear Session Link", self.clear_queen_session_link),
            ("Send to Workers", self.send_queen_folder_to_workers),
            ("Refresh Folder Summary", self.refresh_queen_folder_summary),
            ("Permission / Safety Info", self.show_queen_link_safety_info),
        ]):
            button = QPushButton(text)
            button.clicked.connect(callback)
            button.setMinimumHeight(30)
            action_grid.addWidget(button, index, 0)
        ribbon_layout.addLayout(action_grid)
        layout.addWidget(ribbon)

        body = QSplitter(Qt.Orientation.Horizontal)
        body.setChildrenCollapsible(False)
        left_panel = QFrame()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(7)
        left_layout.addWidget(_label("QUEEN CARD", 9, 900, "#e6fff4"))
        self.queen_link_card = QTextEdit()
        self.queen_link_card.setReadOnly(True)
        self.queen_link_card.setMinimumHeight(180)
        self.queen_link_card.setStyleSheet("font-size:10pt;")
        self.queen_link_card.setLineWrapMode(QTextEdit.WidgetWidth)
        left_layout.addWidget(self.queen_link_card, 1)

        right_panel = QFrame()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(7)
        right_layout.addWidget(_label("WORKER HANDOFF PANEL", 9, 900, "#e6fff4"))
        self.worker_handoff_panel = QTextEdit()
        self.worker_handoff_panel.setReadOnly(True)
        self.worker_handoff_panel.setMinimumHeight(180)
        self.worker_handoff_panel.setStyleSheet("font-size:10pt;")
        self.worker_handoff_panel.setLineWrapMode(QTextEdit.WidgetWidth)
        right_layout.addWidget(self.worker_handoff_panel, 1)

        body.addWidget(left_panel)
        body.addWidget(right_panel)
        body.setSizes([560, 560])
        layout.addWidget(body, 1)

        safety = QFrame()
        safety.setStyleSheet(
            "QFrame {"
            "background: rgba(37, 18, 30, 225);"
            "border: 1px solid rgba(251, 113, 133, 120);"
            "border-radius: 8px;"
            "}"
        )
        safety_layout = QVBoxLayout(safety)
        safety_layout.setContentsMargins(12, 10, 12, 10)
        safety_layout.addWidget(_label("SAFETY", 10, 900, "#fecdd3"))
        safety_layout.addWidget(
            make_scroll_text(
                "Queen link safety details",
                "Links are local GUI session state only. Handoffs are visual/read-only context. "
                "No provider, browsing, network, background worker, autonomous loop, mutation, source edit, queue change, route change, or applied learning starts here.",
                86,
            )
        )
        layout.addWidget(safety)
        self.update_queen_links_view()
        tab.setWidget(content)
        return tab

    def open_super_swarm_3d_visual(self) -> None:
        ok, message = _launch_super_swarm_3d_visual()
        title = "3D Super Swarm Hive" if ok else "3D Super Swarm Hive Unavailable"
        if ok:
            QMessageBox.information(self, title, message)
            return
        QMessageBox.warning(self, title, message)

    def _selected_queen_id(self) -> str:
        if not hasattr(self, "queen_select"):
            return "memory_queen"
        return str(self.queen_select.currentData() or "memory_queen")

    def _selected_queen_link(self) -> dict:
        return self.queen_links.get(self._selected_queen_id(), {})

    def _summary_lines(self, summary: dict) -> list[str]:
        return [
            "file_count: " + str(summary.get("file_count", 0)),
            "markdown_count: " + str(summary.get("markdown_count", 0)),
            "json_count: " + str(summary.get("json_count", 0)),
            "python_count: " + str(summary.get("python_count", 0)),
            "report_count: " + str(summary.get("report_count", 0)),
            "proposal_count: " + str(summary.get("proposal_count", 0)),
            "verifier_count: " + str(summary.get("verifier_count", 0)),
            "warning_count: " + str(summary.get("warning_count", 0)),
            "partial: " + str(bool(summary.get("partial", False))),
            "note: " + str(summary.get("bounded_scan_note", "")),
        ]

    def update_queen_links_view(self) -> None:
        if not hasattr(self, "queen_link_card"):
            return
        link = self._selected_queen_link()
        summary = link.get("summary_counts", {})
        card_lines = [
            "Queen: " + str(link.get("queen_label", "")),
            "Role: " + str(link.get("role", "")),
            "Linked research folder: " + (str(link.get("linked_folder", "")) or "none"),
            "Folder status: " + str(link.get("folder_status", "UNKNOWN")),
            "Worker group receiving folder: " + ", ".join(link.get("assigned_worker_groups", [])),
            "Last local refresh time: " + str(link.get("last_refresh_time", "not refreshed")),
            "Safety badge: " + str(link.get("safety_state", "")),
            "Session only: " + str(bool(link.get("session_only", True))),
            "Proposal only: " + str(bool(link.get("proposal_only", True))),
            "",
            "Folder Summary:",
            *self._summary_lines(summary),
        ]
        self.queen_link_card.setPlainText("\n".join(card_lines))

        handoff_lines = [
            "Queen-to-worker handoff:",
            "Queen: " + str(link.get("queen_label", "")),
            "Folder: " + (str(link.get("linked_folder", "")) or "none"),
            "Handoff status: " + str(link.get("handoff_status", "NOT_SENT")),
            "",
            "Workers receiving context:",
        ]
        for group in link.get("assigned_worker_groups", []):
            marker = "RECEIVED LOCAL SESSION CONTEXT" if link.get("sent_to_workers") else "WAITING"
            handoff_lines.append("- " + str(group) + ": " + marker)
        handoff_lines.extend(
            [
                "",
                "Worker rules:",
                "- Observe, organize, map, prioritize, summarize, and build proposal candidates only.",
                "- Do not modify files, trusted memory, source, queues, routes, autonomy state, or applied lessons.",
                "- Do not start background jobs.",
                "- Do not call providers, browse, or use network behavior.",
            ]
        )
        self.worker_handoff_panel.setPlainText("\n".join(handoff_lines))
        self.refresh_colony_hive_queen_badges()

    def link_queen_research_folder(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self,
            "Link Research Folder",
            str(ROOT),
            QFileDialog.Option.ShowDirsOnly,
        )
        if not chosen:
            return
        validation = validate_queen_research_folder(ROOT, chosen)
        if not validation.get("ok"):
            QMessageBox.warning(self, "Queen Research Links", str(validation.get("message", "Folder was blocked.")))
            link = self._selected_queen_link()
            link["folder_status"] = str(validation.get("folder_status", "BLOCKED"))
            link["safety_state"] = str(validation.get("safety_state", "BLOCKED"))
            self.update_queen_links_view()
            return
        summary = summarize_queen_research_folder(ROOT, str(validation["path"]))
        link = self._selected_queen_link()
        link["linked_folder"] = str(validation["path"])
        link["folder_status"] = str(validation["folder_status"])
        link["safety_state"] = str(validation["safety_state"])
        link["last_refresh_time"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        link["summary_counts"] = summary
        link["sent_to_workers"] = False
        link["handoff_status"] = "LINKED_NOT_SENT"
        self.update_queen_links_view()

    def view_queen_linked_folder(self) -> None:
        link = self._selected_queen_link()
        folder = str(link.get("linked_folder", "")).strip()
        validation = validate_queen_research_folder(ROOT, folder)
        if not validation.get("ok"):
            QMessageBox.information(self, "Queen Research Links", "No valid linked local folder is available to open.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(validation["path"])))

    def clear_queen_session_link(self) -> None:
        queen_id = self._selected_queen_id()
        for template in build_queen_research_link_templates(ROOT):
            if template.get("queen_id") == queen_id:
                self.queen_links[queen_id] = dict(template)
                break
        self.update_queen_links_view()

    def send_queen_folder_to_workers(self) -> None:
        link = self._selected_queen_link()
        folder = str(link.get("linked_folder", "")).strip()
        validation = validate_queen_research_folder(ROOT, folder)
        if not validation.get("ok"):
            QMessageBox.warning(self, "Queen Research Links", "Link a valid local safe-scope folder before sending to workers.")
            return
        link["sent_to_workers"] = True
        link["handoff_status"] = "SENT_TO_WORKERS_AS_READ_ONLY_CONTEXT"
        link["safety_state"] = "LOCAL SESSION / READ-ONLY / PROPOSAL CONTEXT"
        self.update_queen_links_view()
        self._update_live_summary()
        if hasattr(self, "live_canvas"):
            self.live_canvas.update()

    def refresh_queen_folder_summary(self) -> None:
        link = self._selected_queen_link()
        folder = str(link.get("linked_folder", "")).strip()
        validation = validate_queen_research_folder(ROOT, folder)
        if not validation.get("ok"):
            QMessageBox.warning(self, "Queen Research Links", "No valid linked local safe-scope folder is available to summarize.")
            return
        link["summary_counts"] = summarize_queen_research_folder(ROOT, folder)
        link["last_refresh_time"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.update_queen_links_view()

    def show_queen_link_safety_info(self) -> None:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle("Queen Research Links Safety")
        box.setText(
            "Queen research links are session-only local GUI state.\n\n"
            "Safe folders under Engel memory/reports/assets scopes may be linked as read-only context.\n"
            "External folders are blocked or require a separate approved workflow.\n\n"
            "Sending to workers is a visual handoff only and starts no background job, provider call, "
            "network behavior, mutation, source edit, queue change, route change, autonomy change, or applied learning."
        )
        box.setStyleSheet("QLabel{min-width:520px;}")
        box.exec()

    # ENGEL_GUIDED_LIBRARY_REVIEW_UI_TAB_V1_PANEL_START
    def _make_guided_review_panel(self, title: str, accent: str = "#35d6ff") -> tuple[QFrame, QVBoxLayout]:
        panel = QFrame()
        panel.setStyleSheet(
            "QFrame {"
            "background: rgba(4, 15, 24, 232);"
            f"border: 1px solid {accent};"
            "border-radius: 8px;"
            "}"
        )
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)
        layout.addWidget(_label(title, 10, 900, accent))
        return panel, layout

    def _make_guided_library_review_tab(self) -> QWidget:
        tab = QScrollArea()
        tab.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        header = QFrame()
        header.setStyleSheet(
            "QFrame {"
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #092329, stop:0.62 #06131a, stop:1 #1b1024);"
            "border: 1px solid rgba(133, 238, 224, 120);"
            "border-radius: 8px;"
            "}"
        )
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(16, 14, 16, 14)
        header_layout.setSpacing(8)
        header_layout.addWidget(_label("Guided Library Review", 20, 900, "#ffffff"))
        header_layout.addWidget(
            _label(
                "Local draft-only helper for preparing approved-library review metadata. It creates no real queue records, approvals, receipts, imports, memory writes, or automation.",
                10,
                650,
                "#d8fff2",
            )
        )
        header_layout.addWidget(
            make_badge_row([(label, "#86efac") for label in GUIDED_LIBRARY_REVIEW_DRAFT_LABELS])
        )
        layout.addWidget(header)

        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        gate_panel, gate_layout = self._make_guided_review_panel("Fast Safety Gate", "#86efac")
        self.guided_library_review_gate_checks: list[QCheckBox] = []
        for text in [
            "I know what this material is.",
            "I know where it came from.",
            "I know which category it belongs to.",
            "I see no obvious unsafe instruction.",
            "I understand this is not trusted memory.",
            "I understand no automation is triggered.",
        ]:
            check = QCheckBox(text)
            check.stateChanged.connect(lambda _state: self._refresh_guided_library_review_preview())
            self.guided_library_review_gate_checks.append(check)
            gate_layout.addWidget(check)
        top_row.addWidget(gate_panel, 1)

        stop_panel, stop_layout = self._make_guided_review_panel("Stop Conditions", "#fb7185")
        stop_layout.addWidget(
            _label(
                "STOP if source, category, safety, or receipt readiness is unclear. Choose needs_source_clarification, hold_for_later, or unsafe_or_untrusted_content.",
                10,
                750,
                "#fecdd3",
            )
        )
        for item in [
            "Suspicious instructions or hidden prompt text",
            "Unknown source, unclear license, or weak provenance",
            "Commands, package installs, downloads, secrets, or malware-like code",
            "Receipt missing while approval is implied",
        ]:
            stop_layout.addWidget(_label("- " + item, 9, 600, "#f8d6dc"))
        top_row.addWidget(stop_panel, 1)
        layout.addLayout(top_row)

        picker_panel, picker_layout = self._make_guided_review_panel("Category Picker", "#35d6ff")
        picker_row = QHBoxLayout()
        picker_row.addWidget(_label("Category", 9, 850, "#b7ffed"))
        self.guided_library_review_category = QComboBox()
        self.guided_library_review_category.addItem("Choose category", "not_selected")
        for category in GUIDED_LIBRARY_REVIEW_CATEGORIES:
            self.guided_library_review_category.addItem(category, category)
        self.guided_library_review_category.currentIndexChanged.connect(lambda _index: self._refresh_guided_library_review_preview())
        picker_row.addWidget(self.guided_library_review_category, 1)
        picker_row.addWidget(_pill("ORGANIZATION ONLY", "#fbbf24"))
        picker_layout.addLayout(picker_row)
        picker_layout.addWidget(
            _label(
                "Category selection is not permission to execute, index, train, import, approve, or remember anything.",
                9,
                650,
                "#d8fff2",
            )
        )
        layout.addWidget(picker_panel)

        risk_panel, risk_layout = self._make_guided_review_panel("Risk Checks", "#fbbf24")
        self.guided_library_review_risk_checks: dict[str, QCheckBox] = {}
        risk_grid = QGridLayout()
        risk_grid.setHorizontalSpacing(10)
        risk_grid.setVerticalSpacing(6)
        for index, risk in enumerate(GUIDED_LIBRARY_REVIEW_RISK_CHECKS):
            check = QCheckBox(risk)
            check.stateChanged.connect(lambda _state: self._refresh_guided_library_review_preview())
            self.guided_library_review_risk_checks[risk] = check
            risk_grid.addWidget(check, index // 2, index % 2)
        risk_layout.addLayout(risk_grid)
        layout.addWidget(risk_panel)

        decision_panel, decision_layout = self._make_guided_review_panel("Decision Helper", "#c084fc")
        decision_row = QHBoxLayout()
        decision_row.addWidget(_label("Safe outcome", 9, 850, "#e9d5ff"))
        self.guided_library_review_decision = QComboBox()
        for outcome in GUIDED_LIBRARY_REVIEW_SAFE_OUTCOMES:
            label = "metadata_ready_for_human_queue_record_draft" if outcome == "metadata_draft_ready" else outcome
            self.guided_library_review_decision.addItem(label, label)
        self.guided_library_review_decision.currentIndexChanged.connect(lambda _index: self._refresh_guided_library_review_preview())
        decision_row.addWidget(self.guided_library_review_decision, 1)
        decision_layout.addLayout(decision_row)
        decision_layout.addWidget(
            _label(
                "Approved-for-reference still requires separate human review and a human review receipt. This tab only drafts metadata.",
                9,
                650,
                "#f4e6ff",
            )
        )
        layout.addWidget(decision_panel)

        metadata_panel, metadata_layout = self._make_guided_review_panel("Required Metadata", "#5eead4")
        self.guided_library_review_fields: dict[str, QLineEdit] = {}
        metadata_grid = QGridLayout()
        metadata_grid.setHorizontalSpacing(10)
        metadata_grid.setVerticalSpacing(7)
        defaults = {
            "title": "",
            "subcategory": "",
            "source_type": "manual_review_candidate",
            "source_notes": "",
            "original_location_reference": "",
            "intended_reference_location_reference": "",
            "receipt_reference": "NOT_RECEIPT",
            "next_manual_action": "Human reviewer decides the next manual step.",
        }
        editable_fields = [
            "title",
            "subcategory",
            "source_type",
            "source_notes",
            "original_location_reference",
            "intended_reference_location_reference",
            "receipt_reference",
            "next_manual_action",
        ]
        for index, field in enumerate(editable_fields):
            metadata_grid.addWidget(_label(field, 8, 850, "#d8fff2"), index, 0)
            editor = QLineEdit()
            editor.setText(defaults.get(field, ""))
            editor.setPlaceholderText(field)
            editor.textChanged.connect(lambda _text: self._refresh_guided_library_review_preview())
            self.guided_library_review_fields[field] = editor
            metadata_grid.addWidget(editor, index, 1)
        metadata_layout.addLayout(metadata_grid)
        metadata_layout.addWidget(
            _label(
                "Required fields are metadata only. Queue records, approvals, receipts, imports, and memory writes remain unavailable here.",
                9,
                650,
                "#d8fff2",
            )
        )
        layout.addWidget(metadata_panel)

        confirm_panel, confirm_layout = self._make_guided_review_panel("Final Human Confirmation", "#fdba74")
        self.guided_library_review_confirmation_checks: list[QCheckBox] = []
        for text in [
            "I am only preparing metadata.",
            "I am not importing, copying, moving, scanning, indexing, or embedding content.",
            "I am not executing commands or installing packages.",
            "I am not training, fine-tuning, loading runtime/model content, or writing trusted memory.",
            "I understand human authority remains required.",
        ]:
            check = QCheckBox(text)
            check.stateChanged.connect(lambda _state: self._refresh_guided_library_review_preview())
            self.guided_library_review_confirmation_checks.append(check)
            confirm_layout.addWidget(check)
        layout.addWidget(confirm_panel)

        preview_panel, preview_layout = self._make_guided_review_panel("Draft Preview", "#b7ffed")
        preview_layout.addWidget(
            _label(
                "Draft preview is separated from real records. It is DRAFT_ONLY and does not trigger automation.",
                9,
                700,
                "#d8fff2",
            )
        )
        self.guided_library_review_preview = QTextEdit()
        self.guided_library_review_preview.setReadOnly(True)
        self.guided_library_review_preview.setMinimumHeight(260)
        self.guided_library_review_preview.setLineWrapMode(QTextEdit.WidgetWidth)
        preview_layout.addWidget(self.guided_library_review_preview, 1)
        action_row = QHBoxLayout()
        refresh_button = QPushButton("Refresh Draft Preview")
        refresh_button.clicked.connect(self._refresh_guided_library_review_preview)
        action_row.addWidget(refresh_button)
        copy_button = QPushButton("Copy Draft Report")
        copy_button.setToolTip("Copies the dry-run draft preview to the clipboard only.")
        copy_button.clicked.connect(self._copy_guided_library_review_draft_report)
        action_row.addWidget(copy_button)
        action_row.addWidget(_pill("NO REAL QUEUE WRITER", "#fb7185"))
        action_row.addStretch(1)
        preview_layout.addLayout(action_row)
        preview_layout.addWidget(
            _label(
                "Still Disabled: no real queue creation, no import, no scanning, no indexing, no memory writes, no background workers, no route/startup changes, no provider/network/browser calls, no package installs, no model/runtime loading.",
                9,
                700,
                "#fecdd3",
            )
        )
        preview_layout.addWidget(
            _label(
                "Draft boundary: no approvals, no receipts, no automation, and no trusted-memory writes.",
                9,
                700,
                "#fecdd3",
            )
        )
        layout.addWidget(preview_panel, 1)

        layout.addStretch(1)
        tab.setWidget(content)
        self._refresh_guided_library_review_preview()
        return tab

    def _guided_library_review_metadata(self) -> dict:
        fields = getattr(self, "guided_library_review_fields", {})
        category_box = getattr(self, "guided_library_review_category", None)
        decision_box = getattr(self, "guided_library_review_decision", None)
        category = category_box.currentData() if category_box is not None else "not_selected"
        review_state = decision_box.currentData() if decision_box is not None else "not_ready"
        safety_flags = [
            name
            for name, check in getattr(self, "guided_library_review_risk_checks", {}).items()
            if check.isChecked()
        ]
        return {
            "title": fields.get("title").text().strip() if fields.get("title") else "",
            "category": str(category or "not_selected"),
            "subcategory": fields.get("subcategory").text().strip() if fields.get("subcategory") else "",
            "source_type": fields.get("source_type").text().strip() if fields.get("source_type") else "",
            "source_notes": fields.get("source_notes").text().strip() if fields.get("source_notes") else "",
            "original_location_reference": fields.get("original_location_reference").text().strip() if fields.get("original_location_reference") else "",
            "intended_reference_location_reference": fields.get("intended_reference_location_reference").text().strip() if fields.get("intended_reference_location_reference") else "",
            "review_state": str(review_state or "not_ready"),
            "safety_flags": safety_flags,
            "receipt_reference": fields.get("receipt_reference").text().strip() if fields.get("receipt_reference") else "NOT_RECEIPT",
            "next_manual_action": fields.get("next_manual_action").text().strip() if fields.get("next_manual_action") else "Human reviewer decides the next manual step.",
        }

    def _refresh_guided_library_review_preview(self) -> None:
        if not hasattr(self, "guided_library_review_preview"):
            return
        metadata = self._guided_library_review_metadata()
        report = render_draft_report(metadata)
        gate_ready = all(check.isChecked() for check in getattr(self, "guided_library_review_gate_checks", []))
        confirmations_ready = all(check.isChecked() for check in getattr(self, "guided_library_review_confirmation_checks", []))
        lines = [
            "UI status:",
            "- Guided Library Review tab",
            "- DRAFT_ONLY",
            "- NOT_REAL_QUEUE_RECORD",
            "- NOT_APPROVAL",
            "- NOT_RECEIPT",
            "- NOT_TRUSTED_MEMORY",
            "- NO_AUTOMATION_TRIGGERED",
            "",
            "Readiness:",
            "- Fast Safety Gate complete: " + str(gate_ready),
            "- Final Human Confirmation complete: " + str(confirmations_ready),
            "",
            report,
        ]
        self.guided_library_review_preview.setPlainText("\n".join(lines))

    def _copy_guided_library_review_draft_report(self) -> None:
        if not hasattr(self, "guided_library_review_preview"):
            return
        QApplication.clipboard().setText(self.guided_library_review_preview.toPlainText())
        QMessageBox.information(
            self,
            "Guided Library Review",
            "Copied the DRAFT_ONLY dry-run report preview to the clipboard.\n\nNo queue record, approval, receipt, import, memory write, or automation was created.",
        )
    # ENGEL_GUIDED_LIBRARY_REVIEW_UI_TAB_V1_PANEL_END

    def _queen_assignment_lines(self) -> list[str]:
        lines: list[str] = []
        for link in self.queen_links.values():
            if not link.get("sent_to_workers"):
                continue
            lines.append(
                "- "
                + str(link.get("queen_label", "Queen"))
                + " -> "
                + ", ".join(link.get("assigned_worker_groups", []))
                + " | "
                + str(link.get("linked_folder", ""))
            )
        return lines

    def _make_communication_queen_tab(self) -> QWidget:
        snapshot = build_communication_queen_snapshot(ROOT)

        def make_panel(title_text: str, title_color: str, border_color: str, background: str) -> tuple[QFrame, QVBoxLayout]:
            frame = QFrame()
            frame.setStyleSheet(
                "QFrame {"
                f"background: {background};"
                f"border: 1px solid {border_color};"
                "border-radius: 8px;"
                "}"
            )
            frame_layout = QVBoxLayout(frame)
            frame_layout.setContentsMargins(12, 10, 12, 10)
            frame_layout.setSpacing(9)
            title_label = _label(title_text, 10, 900, title_color)
            title_label.setMinimumHeight(24)
            frame_layout.addWidget(title_label)
            return frame, frame_layout

        tab = QScrollArea()
        tab.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(14, 14, 18, 14)
        layout.setSpacing(14)

        header = QHBoxLayout()
        header.setSpacing(18)
        title = QVBoxLayout()
        title.setSpacing(6)
        title.addWidget(_label("Communication Queen", 17, 900, "#ffffff"))
        title.addWidget(
            _label(
                "Future trusted-WiFi coordinator for Remote Queens and small project hives.",
                10,
                700,
                "#d8fff2",
            )
        )
        title.addWidget(
            _label(
                "Communication Queen watches the future bridge between the Main Hive and trusted Remote Queens.",
                9,
                650,
                "#b9d8d4",
            )
        )
        header.addLayout(title, 1)
        badge_text = str(snapshot["status"].get("safety_badge", "OFFLINE SCAFFOLD")).replace(" - ", "\n")
        badge = _label(badge_text, 8, 900, "#facc15")
        badge.setAlignment(Qt.AlignCenter)
        badge.setMinimumWidth(178)
        badge.setMaximumWidth(210)
        badge.setMinimumHeight(62)
        badge.setStyleSheet(
            "QLabel {"
            "background: rgba(69, 26, 3, 210);"
            "border: 1px solid #facc15;"
            "border-radius: 8px;"
            "padding: 9px 11px;"
            "color: #facc15;"
            "}"
        )
        header.addWidget(badge)
        layout.addLayout(header)

        safety, safety_layout = make_panel(
            "RUNTIME SAFETY",
            "#fde68a",
            "rgba(251, 191, 36, 125)",
            "rgba(37, 18, 30, 225)",
        )
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        for index, card in enumerate(snapshot.get("runtime_safety_cards", [])):
            card_box = QFrame()
            card_box.setMinimumHeight(68)
            card_box.setStyleSheet(
                "QFrame {"
                "background: rgba(13, 31, 34, 225);"
                "border: 1px solid rgba(251, 113, 133, 110);"
                "border-radius: 8px;"
                "}"
            )
            card_layout = QVBoxLayout(card_box)
            card_layout.setContentsMargins(10, 8, 10, 8)
            card_layout.setSpacing(5)
            card_layout.addWidget(_label(str(card.get("label", "")), 9, 850, "#e6fff4"))
            status_row = QHBoxLayout()
            status_row.addWidget(_pill(str(card.get("value", "Disabled")).upper(), "#fca5a5"))
            status_row.addStretch(1)
            card_layout.addLayout(status_row)
            grid.addWidget(card_box, index // 4, index % 4)
        safety_layout.addLayout(grid)
        layout.addWidget(safety)

        architecture, architecture_layout = make_panel(
            "ARCHITECTURE",
            "#b7ffed",
            "rgba(158, 231, 208, 95)",
            "rgba(13, 31, 34, 230)",
        )
        architecture_layout.addWidget(make_scroll_text("Architecture details", str(snapshot.get("architecture_copy", "")), 120))
        layout.addWidget(architecture)

        candidates, candidates_layout = make_panel(
            "REMOTE QUEEN CANDIDATES",
            "#bae6fd",
            "rgba(125, 211, 252, 95)",
            "rgba(10, 24, 30, 235)",
        )

        for candidate in snapshot.get("remote_queen_candidates", []):
            allowed = "; ".join(str(item) for item in candidate.get("allowed_future_work", []))
            forbidden = "; ".join(str(item) for item in candidate.get("forbidden_actions", []))
            candidate_box = QFrame()
            candidate_box.setStyleSheet(
                "QFrame {"
                "background: rgba(4, 19, 27, 210);"
                "border: 1px solid rgba(125, 211, 252, 100);"
                "border-radius: 8px;"
                "}"
            )
            candidate_layout = QVBoxLayout(candidate_box)
            candidate_layout.setContentsMargins(11, 9, 11, 9)
            candidate_layout.setSpacing(7)
            candidate_header = QHBoxLayout()
            candidate_header.addWidget(_label(str(candidate.get("display_name", "")), 10, 900, "#ffffff"), 1)
            candidate_header.addWidget(_pill(str(candidate.get("trust_state", "Placeholder only")).upper(), "#7dd3fc"))
            candidate_header.addWidget(_pill("NOT CONNECTED", "#fbbf24"))
            candidate_layout.addLayout(candidate_header)
            candidate_layout.addWidget(_label(str(candidate.get("role", "")), 9, 700, "#bae6fd"))

            candidate_grid = QGridLayout()
            candidate_grid.setHorizontalSpacing(12)
            candidate_grid.setVerticalSpacing(8)
            candidate_grid.addWidget(make_scroll_text("Allowed future work", allowed, 96), 0, 0)
            candidate_grid.addWidget(make_scroll_text("Forbidden actions", forbidden, 96), 0, 1)
            candidate_layout.addLayout(candidate_grid)
            candidates_layout.addWidget(candidate_box)
        candidates_layout.addWidget(
            _label(
                "No device discovery has run. No remote device is connected. No remote task can be assigned.",
                9,
                800,
                "#fde68a",
            )
        )
        layout.addWidget(candidates)

        lower = QHBoxLayout()
        lower.setSpacing(14)
        workflow, workflow_layout = make_panel(
            "FUTURE SAFE WORKFLOW",
            "#b7ffed",
            "rgba(158, 231, 208, 90)",
            "rgba(15, 42, 40, 225)",
        )
        workflow_lines = ["Future safe path:"]
        for index, item in enumerate(snapshot.get("future_workflow", []), start=1):
            workflow_lines.append(str(index) + ". " + str(item))
        workflow_layout.addWidget(make_scroll_text("Workflow details", "\n".join(workflow_lines), 120))
        lower.addWidget(workflow, 2)

        routes, routes_layout = make_panel(
            "FUTURE ROUTES",
            "#ddd6fe",
            "rgba(196, 181, 253, 95)",
            "rgba(20, 20, 38, 230)",
        )
        route_lines = []
        for route in snapshot.get("future_routes", []):
            route_lines.append(str(route.get("route", "")) + "\n  " + str(route.get("status", "")))
        routes_layout.addWidget(make_scroll_text("Route details", "\n\n".join(route_lines), 120))
        lower.addWidget(routes, 1)
        layout.addLayout(lower)

        layout.addStretch(1)
        tab.setWidget(content)
        return tab

    def _make_permissions_tab(self) -> QWidget:
        tab = QScrollArea()
        tab.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)
        layout.addWidget(_label("ENGEL PERMISSIONS", 15, 900, "#ffffff"))
        layout.addWidget(
            _label(
                "Local permission indicators for the Hive screen. These controls show intent and safety posture only.",
                10,
                600,
                "#b9d8d4",
            )
        )

        snapshot = build_colony_hive_snapshot(ROOT)
        layout.addLayout(self._make_permissions_summary_row(snapshot))

        self.permissions_dropdown = QPushButton("Hive Safety Permissions")
        self.permissions_dropdown.setCheckable(True)
        self.permissions_dropdown.setChecked(True)
        self.permissions_dropdown.clicked.connect(self._toggle_permissions_panel)
        layout.addWidget(self.permissions_dropdown)

        self.permissions_panel = QFrame()
        self.permissions_panel.setStyleSheet(
            "QFrame {"
            "background: rgba(13, 31, 34, 230);"
            "border: 1px solid rgba(158, 231, 208, 90);"
            "border-radius: 8px;"
            "}"
        )
        panel_layout = QVBoxLayout(self.permissions_panel)
        panel_layout.setContentsMargins(12, 12, 12, 12)
        panel_layout.setSpacing(10)

        panel_layout.addWidget(
            make_scroll_text(
                "Permission guard details",
                str(snapshot.get("permissions_guard_text", ""))
                + "\n\n"
                + "Dangerous toggles can be clicked only as local request/proposal intent. "
                "They do not call execution functions and reset on app restart.\n\n"
                + str(snapshot.get("password_gate_copy", "")),
                120,
            )
        )
        gate_status = global_password_gate.global_password_gate_status()
        registry_summary = protected_action_registry.registry_summary()
        panel_layout.addWidget(
            make_scroll_text(
                "Global password and protected actions",
                "\n".join(
                    [
                        "Global Password Gate: " + ("CONFIGURED" if gate_status.get("configured") else "NOT CONFIGURED"),
                        "Setup: python engel_global_password_gate.py --setup",
                        "Verify: python engel_global_password_gate.py --verify",
                        "Change: python engel_global_password_gate.py --change",
                        "HUMAN TESTING READY",
                        "PASSWORD REQUIRED FOR PROTECTED ACTIONS",
                        "LOCAL ONLY",
                        "HASH ONLY",
                        "NO PLAINTEXT PASSWORD",
                        "STRICT ACTION ALLOWLIST",
                        "BLOCKED ACTIONS REMAIN BLOCKED",
                        "CONTRACTS STILL REQUIRED",
                        "VERIFIERS STILL REQUIRED",
                        "AUTHORITY STILL REQUIRED",
                        "GUARDS STILL REQUIRED",
                        "Protected Action Registry summary:",
                        "- view-only: " + str(gate_status.get("view_only_count")),
                        "- low-risk gated: " + str(gate_status.get("low_risk_gated_count")),
                        "- medium-risk gated: " + str(gate_status.get("medium_risk_gated_count")),
                        "- high-risk gated: " + str(gate_status.get("high_risk_gated_count")),
                        "- blocked: " + str(gate_status.get("blocked_count")),
                        "- total registered actions: " + str(registry_summary.get("action_count")),
                        "",
                        "Human testing is allowed for local password setup/status/verify and protected action visibility.",
                        "Write/apply/run actions still require password plus action-specific contracts.",
                        "Password protects actions; it does not bypass safety.",
                        "Password does not approve high-risk actions by itself.",
                        "Contracts, verifiers, receipts, and authority hierarchy still apply.",
                        "Blocked actions remain blocked even with password.",
                        "Action IDs use strict allowlists and canonicalization.",
                        "SQL-injection-style, Unicode, encoding, whitespace, and prompt-injection bypass attempts are rejected.",
                        "",
                        "Safe test commands:",
                        "python engel_global_password_gate.py --status",
                        "python engel_global_password_gate.py --setup",
                        "python engel_global_password_gate.py --verify",
                        "python engel_protected_action_registry.py --list",
                        "python engel_protected_action_registry.py --show run_code_companion_low_risk_patch_apply",
                        "python engel_protected_action_registry.py --show promote_memory_candidate",
                        "",
                        "Safe refusal tests:",
                        "protected apply/write commands refuse without password gate",
                        "protected apply/write commands refuse without --password-prompt",
                        "blocked actions remain blocked",
                        "",
                        "Research Toggle Overnight Worker:",
                        research_toggle_status.render_status().rstrip(),
                    ]
                ),
                300,
            )
        )
        for permission in snapshot.get("permissions", []):
            panel_layout.addWidget(PermissionToggleRow(permission))
        layout.addWidget(self.permissions_panel)
        layout.addStretch(1)
        tab.setWidget(content)
        self._toggle_permissions_panel()
        return tab

    def _make_permissions_summary_row(self, snapshot: dict) -> QHBoxLayout:
        permissions = list(snapshot.get("permissions", []))
        blocked = sum(1 for item in permissions if str(item.get("current_state", "")).upper() == "OFF")
        read_only = sum(1 for item in permissions if "READ" in str(item.get("current_state", "")).upper())
        executable = sum(1 for item in permissions if bool(item.get("can_execute_from_hive")))
        password_text = "CONFIGURED" if is_hive_permission_password_configured() else "NOT CONFIGURED"
        items = [
            ("PERMISSION GATES", str(len(permissions)), "Local safety rows", "#35d6ff"),
            ("BLOCKED UNSAFE", str(blocked), "Runtime paths off", "#fb7185"),
            ("READ-ONLY FIRST", str(read_only), "Display-only signals", "#a3ff12"),
            ("EXECUTABLE HERE", str(executable), "Must stay 0", "#ffb020"),
            ("PASSWORD GATE", password_text, "Session request only", "#c084fc"),
        ]
        row = QHBoxLayout()
        row.setSpacing(10)
        for title, value, detail, color in items:
            card = QFrame()
            card.setStyleSheet(
                "QFrame {"
                "background: rgba(4, 17, 28, 230);"
                f"border: 1px solid {color};"
                "border-radius: 8px;"
                "}"
            )
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(10, 8, 10, 8)
            card_layout.setSpacing(3)
            card_layout.addWidget(_label(title, 8, 900, color))
            value_label = _label(value, 13 if len(value) < 12 else 9, 900, "#ffffff")
            value_label.setAlignment(Qt.AlignCenter)
            card_layout.addWidget(value_label)
            detail_label = _label(detail, 8, 650, "#b9d8d4")
            detail_label.setAlignment(Qt.AlignCenter)
            card_layout.addWidget(detail_label)
            row.addWidget(card)
        return row

    def _password_gate_live_toggle(self) -> bool:
        if not is_hive_permission_password_configured():
            QMessageBox.information(
                self,
                "Super Swarm Hive Live",
                "Global password gate is not configured. Hive Live can show static local signals, but Live ON remains locked.\n\nRun: python engel_global_password_gate.py --setup",
            )
            return False
        entered_text, accepted = QInputDialog.getText(
            self,
            "Super Swarm Hive Live",
            "Enter the local hive permission password:",
            QLineEdit.Password,
        )
        if not accepted:
            return False
        if not verify_hive_permission_password(entered_text):
            QMessageBox.warning(self, "Super Swarm Hive Live", "Password rejected. Hive Live remains OFF.")
            return False
        QMessageBox.information(
            self,
            "Super Swarm Hive Live",
            "Hive Live is visual animation plus bounded local read-only signal refresh only. No runtime power is granted.",
        )
        return True

    def toggle_super_swarm_live(self) -> None:
        requested = self.super_swarm_live_button.isChecked()
        if requested:
            if not self._password_gate_live_toggle():
                self.super_swarm_live_button.setChecked(False)
                self.super_swarm_live_enabled = False
                self.live_canvas.set_live_enabled(False)
                self._update_live_summary()
                return
            self.super_swarm_live_enabled = True
            self.refresh_local_signals()
            self.live_canvas.set_live_enabled(True)
            self.super_swarm_live_button.setText("Super Swarm Hive Live: ON")
        else:
            self.super_swarm_live_enabled = False
            self.live_canvas.set_live_enabled(False)
            self.super_swarm_live_button.setText("Super Swarm Hive Live: OFF")
        self._update_live_summary()

    def toggle_pause_motion(self) -> None:
        paused = self.pause_motion_button.isChecked()
        self.pause_motion_button.setText("Resume Motion" if paused else "Pause Motion")
        self.live_canvas.set_motion_paused(paused)
        self._update_live_summary()

    def toggle_reduced_motion(self) -> None:
        reduced = self.reduced_motion_button.isChecked()
        self.live_canvas.set_reduced_motion(reduced)
        self._update_live_summary()

    def refresh_local_signals(self) -> None:
        self.live_signal_snapshot = build_local_hive_signal_snapshot(ROOT)
        if hasattr(self, "live_canvas"):
            self.live_canvas.set_signal_snapshot(self.live_signal_snapshot)
        self.load_snapshot()
        self._update_live_summary()

    def _update_live_summary(self) -> None:
        if not hasattr(self, "live_summary"):
            return
        live = self.live_signal_snapshot or {}
        lines = [
            "Super Swarm Hive Live: " + ("ON" if self.super_swarm_live_enabled else "OFF"),
            "Motion paused: " + str(bool(getattr(self, "pause_motion_button", None) and self.pause_motion_button.isChecked())),
            "Reduced motion: " + str(bool(getattr(self, "reduced_motion_button", None) and self.reduced_motion_button.isChecked())),
            "Live mode means: visual animation + bounded local read-only signal refresh only.",
            "No runtime power granted.",
            "",
            "Last local refresh: " + str(live.get("last_local_refresh_time", "not refreshed")),
            "Files inspected: " + str(live.get("files_inspected", 0)) + " / " + str(live.get("max_files", 0)),
            "Total signal strength: " + str(live.get("total_signal_strength", 0)),
            "Reports: " + str(live.get("report_count", 0)),
            "Proposal candidates: " + str(live.get("proposal_candidate_count", 0)),
            "Verifier signals: " + str(live.get("verifier_signal_count", 0)),
            "Guardian warnings/safety markers: " + str(live.get("guardian_warning_count", 0)),
            "Project-history markers: " + str(live.get("recent_project_history_markers", 0)),
            "",
            "Nest growth:",
        ]
        for signal in live.get("memory_colony_signals", []):
            lines.append(
                "- "
                + str(signal.get("label", "Nest"))
                + ": count="
                + str(signal.get("count", 0))
                + " | growth="
                + str(signal.get("growth_level", 0))
                + " | "
                + str(signal.get("signal_type", "signal"))
            )
        lines.extend(
            [
                "",
                "Queen handoffs:",
                *(self._queen_assignment_lines() or ["- No Queen folder handoff has been sent to workers in this GUI session."]),
                "",
                "Recent local paths:",
                *["- " + str(path) for path in live.get("recent_local_paths", [])],
            ]
        )
        self.live_summary.setPlainText("\n".join(lines))

    def _toggle_permissions_panel(self) -> None:
        open_panel = self.permissions_dropdown.isChecked()
        self.permissions_panel.setVisible(open_panel)
        prefix = "v " if open_panel else "> "
        self.permissions_dropdown.setText(prefix + "Hive Safety Permissions")

    def _make_group_frame(self, title: str, cells: list[dict], columns: int = 2) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame {"
            "background: rgba(255, 255, 255, 10);"
            "border: 1px solid rgba(220, 246, 235, 45);"
            "border-radius: 8px;"
            "}"
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(10)
        layout.addWidget(_label(title.upper(), 10, 900, "#f3fff9"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        for index, cell in enumerate(cells):
            grid.addWidget(HiveCellCard(cell, self.show_details, self.open_link), index // columns, index % columns)
        layout.addLayout(grid)
        return frame

    def _make_mycelium_panel(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame {"
            "background: rgba(35, 22, 46, 215);"
            "border: 1px solid rgba(205, 180, 219, 120);"
            "border-radius: 8px;"
            "}"
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.addWidget(_label("ENGEL MYCELIUM LAYER", 10, 900, "#f2dcff"))
        layout.addWidget(
            _label(
                "Hidden coordination lines are displayed here as read-only local signal paths, not as runtime signal propagation.",
                9,
                600,
                "#e8cfff",
            )
        )
        for signal in self.snapshot.get("mycelium_signals", []):
            layout.addWidget(
                _label(
                    str(signal.get("from", ""))
                    + " -> "
                    + str(signal.get("to", ""))
                    + " | "
                    + str(signal.get("signal_type", "")),
                    9,
                    700,
                    "#f9eaff",
                )
            )
        if not self.snapshot.get("mycelium_signals", []):
            layout.addWidget(_label("No mycelium signals are recorded in the local Hive snapshot.", 9, 650, "#f9eaff"))
        return frame

    def show_first_role(self, role: str) -> None:
        for cell in self.snapshot.get("grouped_cells", {}).get(role, []):
            self.show_details(cell)
            return

    def load_snapshot(self, preferred_cell_id: str = "") -> None:
        self.snapshot = self._snapshot_with_queen_link_badges(build_colony_hive_snapshot(ROOT))
        if hasattr(self, "live_canvas"):
            self.live_canvas.set_hive_snapshot(self.snapshot)
        self._refresh_map_panel()
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        grouped = self.snapshot.get("grouped_cells", {})
        for role in ROLE_ORDER:
            if role not in SUPERCOLONY_DISPLAY_ROLES and role != "mycelium_signal":
                continue
            cells = grouped.get(role, [])
            if not cells:
                continue
            if role == "mycelium_signal":
                self.cards_layout.addWidget(self._make_mycelium_panel())
            self.cards_layout.addWidget(self._make_group_frame(ROLE_TITLES.get(role, role), cells))
        self.cards_layout.addStretch(1)

        cells = self.snapshot.get("cells", [])
        preferred = None
        if preferred_cell_id:
            for cell in cells:
                if str(cell.get("id", "")) == preferred_cell_id:
                    preferred = cell
                    break
        if preferred:
            self.show_details(preferred)
        elif cells:
            self.show_details(cells[0])
        else:
            self.current_cell = None
            self.details.setPlainText(
                "No local Hive cells are currently available.\n\n"
                "The visual tabs are connected to the local Engel Hive snapshot and will show records when true local state exists.\n"
                "No placeholder or fake colony records are injected."
            )
        self._sync_status_rail_counts()

    def show_details(self, cell: dict) -> None:
        self.current_cell = cell
        lines = [
            "Actor: " + str(cell.get("actor", "")),
            "Role: " + str(cell.get("role", "")),
            "Colony id: " + str(cell.get("colony_id", "")),
            "Nest: " + str(cell.get("nest_name", "")),
            "Cell: " + str(cell.get("cell_name", "")),
            "Current task: " + str(cell.get("current_task", "")),
            "Command: " + str(cell.get("command", "")),
            "Local trail: " + str(cell.get("linked_local_artifact", "")),
            "Absolute path: " + str(cell.get("absolute_path", "")),
            "Signal type: " + str(cell.get("signal_type", "")),
            "Confidence marker: " + str(cell.get("confidence_marker", "")),
            "Safety state: " + str(cell.get("safety_state", "")),
            "Proposal only: " + str(bool(cell.get("proposal_only"))),
            "Status: " + str(cell.get("status", "")),
            "Kind: " + str(cell.get("kind", "")),
            "Last updated: " + str(cell.get("last_updated", "")),
        ]
        queen_link_status = cell.get("queen_link_status", {})
        if queen_link_status:
            lines.extend(
                [
                    "",
                    "Queen Research Link Badge:",
                    "- Folder badge: " + str(queen_link_status.get("folder_badge", "NO SESSION LINK")),
                    "- Folder: " + str(queen_link_status.get("folder_text", "none")),
                    "- Handoff badge: " + str(queen_link_status.get("handoff_badge", "NOT SENT")),
                    "- " + str(queen_link_status.get("worker_line", "")),
                ]
            )
        lines.extend(
            [
            "",
            "Preview:",
            str(cell.get("preview", "")),
            "",
            "Queen Research Links:",
            *(self._queen_assignment_lines() or ["- No Queen folder handoff has been sent to workers in this GUI session."]),
            "",
            "Safety:",
            "- Local hive map only.",
            "- Local visual hive only.",
            "- Opening a trail opens only a local file or folder under the Engel root.",
            "- Mycelium signals are read-only-first.",
            "- Colony outputs are proposal candidates until human-approved.",
            "- Password unlock changes only session request/proposal state and grants no runtime power.",
            "- No browsing, provider call, network call, queue mutation, trusted-memory write, source edit, worker service, or autonomous loop starts from this card.",
            ]
        )
        self.details.setPlainText("\n".join(lines))

    def _safe_path_for(self, cell: dict | None) -> Path | None:
        if not cell:
            return None
        raw = str(cell.get("absolute_path", "")).strip()
        if not raw:
            return None
        path = Path(raw).resolve()
        root = ROOT.resolve()
        try:
            path.relative_to(root)
        except ValueError:
            return None
        if not path.exists():
            return None
        return path

    def open_link(self, cell: dict) -> None:
        path = self._safe_path_for(cell)
        if not path:
            self.show_details(cell)
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def open_selected_link(self) -> None:
        self.open_link(self.current_cell or {})

    def _shutdown_owned_resources(self) -> None:
        try:
            if hasattr(self, "live_canvas") and self.live_canvas is not None:
                self.live_canvas.stop_motion()
                timer = getattr(self.live_canvas, "animation_timer", None)
                if timer is not None:
                    timer.stop()
        except Exception:
            pass

        try:
            children = list(self.findChildren(QWidget))
            for child in children:
                if child is self:
                    continue
                if child.isWindow():
                    child.close()
        except Exception:
            pass

    def closeEvent(self, event) -> None:  # noqa: N802
        self._shutdown_owned_resources()
        event.accept()
        app = QApplication.instance()
        if app is not None:
            QTimer.singleShot(0, app.quit)
        super().closeEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    app.setFont(QFont("Segoe UI", 10))
    window = EngelColonyHiveWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
