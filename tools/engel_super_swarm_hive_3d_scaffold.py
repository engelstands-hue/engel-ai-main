from __future__ import annotations

import json
import math
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QPoint, QPointF, QRectF, Qt, QTimer, Signal as pyqtSignal
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDockWidget,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QToolButton,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

try:
    from OpenGL.GL import (
        GL_BLEND,
        GL_COLOR_BUFFER_BIT,
        GL_DEPTH_BUFFER_BIT,
        GL_DEPTH_TEST,
        GL_LINE_LOOP,
        GL_LINE_SMOOTH,
        GL_LINES,
        GL_MODELVIEW,
        GL_MODELVIEW_MATRIX,
        GL_ONE_MINUS_SRC_ALPHA,
        GL_POINTS,
        GL_PROJECTION,
        GL_PROJECTION_MATRIX,
        GL_SRC_ALPHA,
        GL_TRIANGLE_STRIP,
        GL_VIEWPORT,
        glBegin,
        glBlendFunc,
        glClear,
        glClearColor,
        glColor4f,
        glEnable,
        glEnd,
        glGetDoublev,
        glGetIntegerv,
        glLineWidth,
        glLoadIdentity,
        glMatrixMode,
        glPointSize,
        glPopMatrix,
        glPushMatrix,
        glRotatef,
        glShadeModel,
        glTranslatef,
        glVertex3f,
        glViewport,
        GL_SMOOTH,
    )
    from OpenGL.GLU import gluPerspective, gluProject

    OPENGL_READY = True
except Exception:
    OPENGL_READY = False

import os

APP_TITLE = "ENGEL COLONY HIVE - SUPER SWARM VIEW"
DISPLAY_TITLE = "ENGEL COLONY HIVE \u2014 SUPER SWARM VIEW"
SESSION_ID = "LOCAL-GUI"
if getattr(sys, "frozen", False):
    exe_path = Path(sys.executable).resolve()
    if (
        exe_path.name.lower() == "engelsuperswarmhive3d.exe"
        and exe_path.parent.name.lower() == "app"
        and exe_path.parent.parent.name.lower() == "live"
    ):
        ROOT = exe_path.parent.parent.parent
    else:
        ROOT = exe_path.parent
else:
    _file = globals().get("__file__")
    if not _file or not isinstance(_file, str) or _file.startswith("<"):
        ROOT = Path.cwd()
    else:
        try:
            ROOT = Path(_file).resolve().parents[1]
        except (OSError, ValueError, IndexError):
            ROOT = Path.cwd()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import engel_temp_policy  # noqa: F401
import engel_ui_theme

os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(ROOT / "runtime" / "playwright-browsers"))

try:
    from engel_hive_data_services import build_hive_snapshot
except Exception:
    build_hive_snapshot = None  # type: ignore[assignment]

try:
    from engel_communication_router import route_companion_text_or_command
except Exception:
    route_companion_text_or_command = None  # type: ignore[assignment]

try:
    import engel_ai_intent_planner as ai_planner
except Exception:
    ai_planner = None  # type: ignore[assignment]

try:
    import engel_ai_proceed_receipts as proceed_receipts
except Exception:
    proceed_receipts = None  # type: ignore[assignment]

try:
    import engel_ai_receipt_viewer as receipt_viewer
except Exception:
    receipt_viewer = None  # type: ignore[assignment]

try:
    import engel_ai_body_status as ai_body_status
except Exception:
    ai_body_status = None  # type: ignore[assignment]

try:
    from engel_offline_seed_llm import (
        offline_seed_llm_gate_enabled,
        render_offline_seed_llm_status,
        run_offline_seed_llm_for_companion_chat,
    )
except Exception:
    offline_seed_llm_gate_enabled = None  # type: ignore[assignment]
    render_offline_seed_llm_status = None  # type: ignore[assignment]
    run_offline_seed_llm_for_companion_chat = None  # type: ignore[assignment]

Point3 = tuple[float, float, float]
ColorTuple = tuple[float, float, float, float]

# ENGEL_SUPER_SWARM_MINIMAL_TECH_THEME_V1_START
SUPER_SWARM_MINIMAL_TECH_THEME_MARKER = "Engel Minimal Tech Console"
SWARM_BG_PRIMARY = "#07090C"
SWARM_BG_PANEL = "#0D1117"
SWARM_BG_CARD = "#121821"
SWARM_BG_CARD_ALT = "#161C25"
SWARM_BORDER_SUBTLE = "#26313D"
SWARM_BORDER_FOCUS = "#5BC8FF"
SWARM_TEXT_PRIMARY = "#E8F4FF"
SWARM_TEXT_SECONDARY = "#A9B7C5"
SWARM_TEXT_MUTED = "#758596"
SWARM_ACCENT_INFO = "#5BC8FF"
SWARM_ACCENT_SAFE = "#73D18B"
SWARM_BADGE_DISABLED = "#657386"
SWARM_BADGE_WARNING = "#E6C96A"
SWARM_BADGE_ACTIVE = "#73D18B"
SWARM_BADGE_BLOCKED = "#FF6B6B"
SWARM_EDGE_SUBTLE = "#315567"
SWARM_NODE_FOCUS = "#5BC8FF"
SWARM_NODE_IDLE = "#A9B7C5"
SWARM_THEME_TRUE_DATA_ONLY = "true-local-data-only"
GRAPHIFY_SAMPLE_LIMIT = 420
GRAPHIFY_LINK_LIMIT = 900
GRAPHIFY_GRAPH_RELATIVE_PATH = Path("engel_graphify-out") / "graph.json"
GRAPHIFY_GROUP_COLORS = {
    "Core": "#5BC8FF",
    "Routes": "#73D18B",
    "UI Screens": "#7DD3FC",
    "Long Term Memory": "#E6C96A",
    "Reports Receipts": "#FF9F6E",
    "Workers": "#5EEAD4",
    "Models Runtime": "#A78BFA",
    "Verifiers Tools": "#F97316",
    "Vendored Modules": "#94A3B8",
    "Graphify": "#F472B6",
}
# ENGEL_SUPER_SWARM_MINIMAL_TECH_THEME_V1_END


def resolve_graphify_graph_path() -> Path:
    candidates = [ROOT / GRAPHIFY_GRAPH_RELATIVE_PATH]
    bundle_root = getattr(sys, "_MEIPASS", "")
    if bundle_root:
        candidates.append(Path(str(bundle_root)) / GRAPHIFY_GRAPH_RELATIVE_PATH)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]

# ENGEL_MOBILE_CONNECTION_SUPER_SWARM_READONLY_TAB_V1_CONSTANTS_START
MOBILE_SWARM_REMOTE_QUEENS_LABEL = "Engel Remote Workers"

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
# ENGEL_MOBILE_CONNECTION_SUPER_SWARM_READONLY_TAB_V1_CONSTANTS_END


@dataclass
class SuperColony:
    id: str
    label: str
    center: Point3
    color: ColorTuple
    radius: float
    active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SwarmNode:
    id: str
    colony_id: str
    label: str
    position: Point3
    kind: str
    health: float = 1.0
    protocol: str = "local-view"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SwarmTrail:
    id: str
    source: str
    target: str
    kind: str
    colony_id: str = ""
    inter_colony: bool = False
    points: list[Point3] = field(default_factory=list)
    status: str = "LOCAL_VIEW"
    evidence: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SwarmWorker:
    id: str
    colony_id: str
    trail_id: str
    speed: float
    progress: float
    phase: float
    lane_offset: float


@dataclass
class GrowthPathRecord:
    id: str
    source: str
    target: str
    status: str
    progress: float = 0.0
    evidence: str = ""


@dataclass
class RemoteQueenRecord:
    id: str
    label: str
    status: str
    disabled_reason: str
    source: str = "local-registry"


@dataclass
class TelemetryEvent:
    id: str
    label: str
    status: str
    source: str
    detail: str = ""


@dataclass
class PermissionUserRecord:
    id: str
    role: str
    access_level: str
    assigned_colonies: list[str] = field(default_factory=list)
    last_activity: str = "session local"
    status: str = "Pending"
    activity_log: list[str] = field(default_factory=list)
    source: str = "session-local-gui-store"


class HiveSectionAdapter:
    """Read-only adapter for one Super Swarm Hive local store section.

    Adapters expose existing local records, summaries, details, and GUI focus.
    They never run gameplay-style plugin behavior, select records on their own, create
    records, call providers, start workers, or mutate Hive stores.
    """

    section_id = "base"
    label = "Base"
    button_detail = "Focus local section"

    def records(self, view_model: Any) -> list[Any]:
        _ = view_model
        return []

    def summary(self, view_model: Any) -> str:
        _ = view_model
        return "No records."

    def detail(self, view_model: Any, selected_id: str = "") -> str:
        _ = selected_id
        return self.summary(view_model)

    def focus(self, window: Any) -> None:
        focus = getattr(window, "focus_local_section", None)
        if callable(focus):
            focus(self.section_id)


class HiveOverviewAdapter(HiveSectionAdapter):
    section_id = "hive_overview"
    label = "Hive Overview"
    button_detail = "Focus true local Hive overview"

    def records(self, view_model: Any) -> list[Any]:
        return list(view_model.colonies.values())

    def summary(self, view_model: Any) -> str:
        metrics = view_model.metrics()
        return (
            "Hive overview.\n"
            f"Local colonies: {metrics['colonies']}.\n"
            f"Queens: {metrics['queens']}.\n"
            f"Worker cells: {metrics['worker_cells']}.\n"
            f"Worker events: {metrics['worker_events']}.\n"
            f"Nests: {metrics['nests']}.\n"
            "All values come from the true local Hive snapshot or empty stores."
        )

    def detail(self, view_model: Any, selected_id: str = "") -> str:
        _ = selected_id
        metrics = view_model.metrics()
        return (
            "Hive overview\n\n"
            f"Status: {view_model.local_status_label()}\n"
            f"Local colonies: {metrics['colonies']}\n"
            f"Queens: {metrics['queens']}\n"
            f"Worker cells: {metrics['worker_cells']}\n"
            f"Worker events: {metrics['worker_events']}\n"
            f"Nests: {metrics['nests']}\n"
            f"Mycelium signal links: {metrics['signals']}\n"
            f"Local artifact readiness: {metrics['ready_records']} / {metrics['total_records']}\n\n"
            "All values are derived from the true local Engel Hive snapshot or empty local stores."
        )


class ResearchSignalsAdapter(HiveSectionAdapter):
    section_id = "research"
    label = "Research"
    button_detail = "Focus local research signal counts"

    def records(self, view_model: Any) -> list[Any]:
        return list(view_model.signal_snapshot.get("recent_local_paths", []))

    def summary(self, view_model: Any) -> str:
        metrics = view_model.metrics()
        return (
            "Local research view only.\n"
            f"Report signals: {metrics['report_count']}.\n"
            f"Files inspected by local signal snapshot: {metrics['files_inspected']}.\n"
            "No live research, browser, provider, API, network, or background action starts here."
        )


class ThinkingSignalsAdapter(HiveSectionAdapter):
    section_id = "think"
    label = "Think"
    button_detail = "Focus local proposal/verifier signals"

    def records(self, view_model: Any) -> list[Any]:
        return list(view_model.lane_state.values())

    def summary(self, view_model: Any) -> str:
        metrics = view_model.metrics()
        return (
            "Local thinking view only.\n"
            f"Proposal candidates observed: {metrics['proposal_candidate_count']}.\n"
            f"Verifier signals observed: {metrics['verifier_signal_count']}.\n"
            "No LLM inference, autonomous loop, queue mutation, route mutation, or file write starts here."
        )


class CommunicationQueenAdapter(HiveSectionAdapter):
    section_id = "communication_queen"
    label = "Communication Queen"
    button_detail = "Focus local contract status"

    def records(self, view_model: Any) -> list[Any]:
        node = view_model.nodes.get(view_model.communication_queen_id)
        return [node] if node else []

    def summary(self, view_model: Any) -> str:
        node = view_model.nodes.get(view_model.communication_queen_id)
        status = node.metadata.get("status", "unavailable") if node else "unavailable"
        return (
            "Communication Queen local contract view.\n"
            f"Status: {status}.\n"
            "Runtime, WiFi, discovery, remote execution, background worker, provider, and network paths are disabled.\n"
            "Future chat/status input must pass through the shared deterministic communication membrane first."
        )

    def detail(self, view_model: Any, selected_id: str = "") -> str:
        _ = selected_id
        return self.summary(view_model) + "\n\nSource: memory/COMMUNICATION_QUEEN_REMOTE_QUEEN_CONTRACT_V1.json"


class RemoteQueenRegistryAdapter(HiveSectionAdapter):
    section_id = "remote_queens"
    label = "Remote Queens"
    button_detail = "Focus true empty remote registry"

    def records(self, view_model: Any) -> list[Any]:
        return list(view_model.remote_queen_registry.values())

    def summary(self, view_model: Any) -> str:
        metrics = view_model.metrics()
        return (
            "Remote Queen registry.\n"
            f"Registered Remote Queens: {metrics['remote_queens']}.\n"
            "No remote queens are registered yet; candidate-only contract entries are not treated as true devices."
        )

    def detail(self, view_model: Any, selected_id: str = "") -> str:
        _ = selected_id
        return self.summary(view_model) + "\n\nDisabled reason: Remote Queen runtime and discovery remain disabled by contract."


class GrowthPathStoreAdapter(HiveSectionAdapter):
    section_id = "growth_paths"
    label = "Growth Paths"
    button_detail = "Focus true empty growth-path store"

    def records(self, view_model: Any) -> list[Any]:
        return list(view_model.growth_paths.values())

    def summary(self, view_model: Any) -> str:
        metrics = view_model.metrics()
        return (
            "Growth path store.\n"
            f"Active growth paths: {metrics['growth_paths']}.\n"
            "No actual Engel Hive growth events have populated this store yet."
        )

    def detail(self, view_model: Any, selected_id: str = "") -> str:
        _ = selected_id
        lines = [self.summary(view_model), "", "Growth/proposal records:"]
        if not view_model.growth_paths:
            lines.append("No actual Engel Hive growth events have populated growth paths yet.")
        else:
            for item in view_model.growth_paths.values():
                lines.append(f"- {item.id}: {item.source} -> {item.target} | {item.status}")
        lines.extend(["", f"Local proposal lane records: {len(view_model.lane_state)}"])
        if view_model.lane_state:
            for item in view_model.lane_state.values():
                lines.append("- " + str(item.get("cell_name", item.get("id", "proposal"))))
        else:
            lines.append("No local proposal lane records are available.")
        lines.extend(
            [
                "",
                "Future population contract: approved local Hive events may add records with source, target, status, and evidence.",
                "Proposal outputs remain untrusted until review, verifier coverage, and human approval.",
            ]
        )
        return "\n".join(lines)


class SignalAnalyzerAdapter(HiveSectionAdapter):
    section_id = "signal_analyzer"
    label = "Signal Analyzer"
    button_detail = "Focus local signal snapshot"

    def records(self, view_model: Any) -> list[Any]:
        return list(view_model.signal_snapshot.get("memory_colony_signals", []))

    def summary(self, view_model: Any) -> str:
        metrics = view_model.metrics()
        return (
            "Signal analyzer.\n"
            f"Local signal strength: {metrics['local_signal_strength']}.\n"
            f"Telemetry events: {metrics['telemetry_events']}.\n"
            "Signal counts come from local files; no generated telemetry stream is present."
        )

    def detail(self, view_model: Any, selected_id: str = "") -> str:
        _ = selected_id
        metrics = view_model.metrics()
        lines = [
            "Signal analyzer",
            "",
            f"Files inspected by local snapshot: {metrics['files_inspected']}",
            f"Total local signal strength: {metrics['local_signal_strength']}",
            f"Reports observed: {metrics['report_count']}",
            f"Guardian warning markers: {metrics['guardian_warning_count']}",
            f"Proposal candidate markers: {metrics['proposal_candidate_count']}",
            f"Verifier signal markers: {metrics['verifier_signal_count']}",
            f"Telemetry events: {metrics['telemetry_events']}",
            "",
            "Telemetry store: No telemetry events recorded yet." if not view_model.telemetry_events else "Telemetry store records are populated.",
            "No generated telemetry, latency, bandwidth, or signal feed is shown.",
        ]
        return "\n".join(lines)


class TelemetryEventStoreAdapter(HiveSectionAdapter):
    section_id = "telemetry_events"
    label = "Telemetry Events"
    button_detail = "Focus true telemetry event store"

    def records(self, view_model: Any) -> list[Any]:
        return list(view_model.telemetry_events)

    def summary(self, view_model: Any) -> str:
        metrics = view_model.metrics()
        return (
            "True local telemetry store.\n"
            f"Telemetry events: {metrics['telemetry_events']}.\n"
            "No generated latency, throughput, traffic, or live-looking telemetry is shown."
        )

    def detail(self, view_model: Any, selected_id: str = "") -> str:
        _ = selected_id
        metrics = view_model.metrics()
        lines = [
            "True local telemetry store",
            "",
            f"Telemetry events: {metrics['telemetry_events']}",
            f"Files inspected by local snapshot: {metrics['files_inspected']}",
            f"Total local signal strength: {metrics['local_signal_strength']}",
            "",
        ]
        if not view_model.telemetry_events:
            lines.append("No telemetry events recorded yet.")
            lines.append("No latency, throughput, traffic, or live-looking telemetry is generated.")
        else:
            for item in view_model.telemetry_events[:12]:
                lines.append(f"- {item.id}: {item.label} | {item.status} | {item.source}")
                if item.detail:
                    lines.append(f"  {item.detail}")
        return "\n".join(lines)


class ActivitySourceAdapter(HiveSectionAdapter):
    section_id = "activity_sources"
    label = "Activity Sources"
    button_detail = "Focus local activity source list"

    def records(self, view_model: Any) -> list[Any]:
        return list(view_model.activity_feed)

    def summary(self, view_model: Any) -> str:
        return f"Local activity source records: {len(view_model.activity_feed)}."

    def detail(self, view_model: Any, selected_id: str = "") -> str:
        _ = selected_id
        if not view_model.activity_feed:
            return "Swarm activity feed\n\nNo local Hive activity records are available yet."
        return "Swarm activity feed\n\n" + "\n".join(view_model.activity_feed)


class WorkerEventStoreAdapter(HiveSectionAdapter):
    section_id = "worker_events"
    label = "Worker Events"
    button_detail = "Focus true worker-event store"

    def records(self, view_model: Any) -> list[Any]:
        return list(view_model.worker_event_store.values())

    def summary(self, view_model: Any) -> str:
        metrics = view_model.metrics()
        return (
            "Worker event store.\n"
            f"Worker events: {metrics['worker_events']}.\n"
            "Workers are shown only when true local worker-event records exist."
        )


class DataManager(QObject):
    """Owns true local Hive view-model stores for the Super Swarm surface.

    Data is derived from existing local Engel snapshot builders and explicit
    in-memory stores. Missing layers start empty and remain honest zero states
    until a future approved local event passes records to apply_local_hive_payload().
    """

    data_updated = pyqtSignal()
    selection_requested = pyqtSignal(str)
    section_focus_requested = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self.colonies: dict[str, SuperColony] = {}
        self.nodes: dict[str, SwarmNode] = {}
        self.trails: dict[str, SwarmTrail] = {}
        self.workers: dict[str, SwarmWorker] = {}
        self.growth_paths: dict[str, GrowthPathRecord] = {}
        self.remote_queen_registry: dict[str, RemoteQueenRecord] = {}
        self.telemetry_events: list[TelemetryEvent] = []
        self.colony_registry = self.colonies
        self.nest_registry: dict[str, SwarmNode] = {}
        self.queen_registry: dict[str, SwarmNode] = {}
        self.worker_cell_registry: dict[str, SwarmNode] = {}
        self.worker_event_store = self.workers
        self.growth_path_store = self.growth_paths
        self.telemetry_event_store = self.telemetry_events
        self.protocol_state: dict[str, Any] = {}
        self.lane_state: dict[str, dict[str, Any]] = {}
        self.growth_queue: list[dict[str, Any]] = []
        self.activity_feed: list[str] = []
        self.messages: list[dict[str, str]] = []
        self.source_snapshot: dict[str, Any] = {}
        self.signal_snapshot: dict[str, Any] = {}
        self.communication_snapshot: dict[str, Any] = {}
        self.permission_store: list[dict[str, Any]] = []
        self.permission_user_store: dict[str, PermissionUserRecord] = {}
        self.source_error = ""
        self.current_section = "hive_overview"
        self.selected_entity_id = ""
        self.communication_queen_id = "communication_queen"
        self.section_adapters: dict[str, HiveSectionAdapter] = {}
        self._register_default_section_adapters()
        self.last_update_label = "true local view model not loaded"
        self.refresh_local_view(emit=False)

    def _timestamp(self) -> str:
        return time.strftime("%H:%M", time.localtime())

    def _register_default_section_adapters(self) -> None:
        for adapter in [
            HiveOverviewAdapter(),
            ResearchSignalsAdapter(),
            ThinkingSignalsAdapter(),
            CommunicationQueenAdapter(),
            RemoteQueenRegistryAdapter(),
            GrowthPathStoreAdapter(),
            SignalAnalyzerAdapter(),
            TelemetryEventStoreAdapter(),
            ActivitySourceAdapter(),
            WorkerEventStoreAdapter(),
        ]:
            self.register_section_adapter(adapter)

    def register_section_adapter(self, adapter: HiveSectionAdapter) -> None:
        if not isinstance(adapter, HiveSectionAdapter):
            raise TypeError("Super Swarm Hive adapters must inherit HiveSectionAdapter.")
        if hasattr(adapter, "run"):
            raise ValueError("Super Swarm Hive adapters must not implement run(engine) behavior.")
        self.section_adapters[adapter.section_id] = adapter

    def section_adapter(self, section: str) -> HiveSectionAdapter | None:
        return self.section_adapters.get(section)

    def section_records(self, section: str) -> list[Any]:
        adapter = self.section_adapter(section)
        return adapter.records(self) if adapter else []

    def focus_section(self, section: str) -> None:
        adapter = self.section_adapter(section)
        self.current_section = adapter.section_id if adapter else section
        self.section_focus_requested.emit(self.current_section)

    @staticmethod
    def _title_from_id(value: str) -> str:
        return value.replace("_", " ").replace("-", " ").title()

    @staticmethod
    def _hex_to_color(value: str, alpha: float = 0.72) -> ColorTuple:
        cleaned = str(value or "#44aaff").strip().lstrip("#")
        if len(cleaned) != 6:
            return (0.20, 0.84, 1.0, alpha)
        try:
            return (
                int(cleaned[0:2], 16) / 255.0,
                int(cleaned[2:4], 16) / 255.0,
                int(cleaned[4:6], 16) / 255.0,
                alpha,
            )
        except ValueError:
            return (0.20, 0.84, 1.0, alpha)

    def _empty_snapshot(self, reason: str) -> dict[str, Any]:
        return {
            "title": "Engel Colony Hive",
            "status": "LOCAL_VISUAL_HIVE / EMPTY_VIEW_MODEL",
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
            "root": str(ROOT),
            "mind_summary": {
                "identity": "One cooperative Engel Mind",
                "posture": "Local-only, Guardian-gated, proposal-first",
                "safe_mode": "ON",
                "brain_provider_state": "No provider call from Super Swarm Hive",
                "guardian_posture": "Guardian layer present; source unavailable",
            },
            "cells": [],
            "grouped_cells": {},
            "queens": [],
            "workers": [],
            "memory_nests": [],
            "guardian_cards": [],
            "proposal_lanes": [],
            "permissions": [],
            "mycelium_signals": [],
            "guardian_layer": {"visible": True, "monitors": [], "blocks": []},
            "super_swarm_hive_live": {
                "files_inspected": 0,
                "memory_colony_signals": [],
                "total_signal_strength": 0,
                "report_count": 0,
                "guardian_warning_count": 0,
                "proposal_candidate_count": 0,
                "verifier_signal_count": 0,
                "recent_local_paths": [],
            },
            "communication_queen": {
                "status": {
                    "status_label": "Unavailable local snapshot",
                    "runtime_remote_queen_network_enabled": False,
                    "remote_queen_runtime_enabled": False,
                    "provider_or_api_calls_enabled": False,
                    "internet_behavior_enabled": False,
                    "background_worker_enabled": False,
                },
                "remote_queen_candidates": [],
            },
            "source_error": reason,
        }

    def refresh_local_view(self, emit: bool = True) -> None:
        previous_session_messages = [
            item for item in self.messages if item.get("source") == "session"
        ]
        self.source_error = ""
        if build_hive_snapshot is None:
            self.source_error = "engel_hive_data_services.build_hive_snapshot is unavailable."
            snapshot = self._empty_snapshot(self.source_error)
        else:
            try:
                snapshot = build_hive_snapshot(ROOT)  # type: ignore[misc]
            except Exception as exc:
                self.source_error = str(exc)
                snapshot = self._empty_snapshot(self.source_error)

        self.source_snapshot = dict(snapshot)
        self.signal_snapshot = dict(snapshot.get("super_swarm_hive_live", {}))
        self.communication_snapshot = dict(snapshot.get("communication_queen", {}))
        self.permission_store = [dict(item) for item in snapshot.get("permissions", [])]
        self._build_true_local_stores()
        self._rebuild_messages_from_state()
        for item in reversed(previous_session_messages):
            self.messages.insert(0, item)
        self.last_update_label = "true local Engel Hive view model"
        if emit:
            self.data_updated.emit()

    def _build_true_local_stores(self) -> None:
        self.colonies.clear()
        self.nodes.clear()
        self.trails.clear()
        self.workers.clear()
        self.growth_paths.clear()
        self.remote_queen_registry.clear()
        self.telemetry_events.clear()
        self.nest_registry.clear()
        self.queen_registry.clear()
        self.worker_cell_registry.clear()
        self.protocol_state.clear()
        self.lane_state.clear()
        self.growth_queue.clear()

        cells = [dict(item) for item in self.source_snapshot.get("cells", [])]
        signal_records = [
            dict(item) for item in self.signal_snapshot.get("memory_colony_signals", [])
        ]
        signals_by_colony = {str(item.get("colony_id", "")): item for item in signal_records}
        grouped: dict[str, list[dict[str, Any]]] = {}
        for cell in cells:
            grouped.setdefault(str(cell.get("colony_id", "local-hive")), []).append(cell)
        colony_ids = sorted(set(grouped) | set(signals_by_colony))

        non_core = [item for item in colony_ids if item != "engel-core"]
        for index, colony_id in enumerate(colony_ids):
            if colony_id == "engel-core":
                center = (0.0, 0.0, 0.08)
            else:
                non_core_index = non_core.index(colony_id)
                ring = non_core_index // 8
                slot = non_core_index % 8
                remaining = len(non_core) - ring * 8
                slots = min(8, max(1, remaining))
                angle = math.tau * slot / slots + ring * 0.24
                radius = 3.05 + ring * 2.05
                center = (math.cos(angle) * radius, math.sin(angle) * radius * 0.72, 0.0)

            records = grouped.get(colony_id, [])
            signal = signals_by_colony.get(colony_id, {})
            first = records[0] if records else {}
            label_text = str(signal.get("label") or first.get("nest_name") or self._title_from_id(colony_id))
            ready = sum(1 for item in records if bool(item.get("exists")))
            total = len(records)
            signal_count = int(signal.get("count", 0) or 0)
            self.colonies[colony_id] = SuperColony(
                id=colony_id,
                label=label_text,
                center=center,
                color=self._hex_to_color(str(first.get("accent", "#44aaff"))),
                radius=0.82 + min(0.64, max(1, total) * 0.06),
                active=True,
                metadata={
                    "ready_records": ready,
                    "total_records": total,
                    "signal_count": signal_count,
                    "signal_type": signal.get("signal_type", "local hive record"),
                    "safety_state": signal.get("safety_state", first.get("safety_state", "local-only")),
                },
            )

        self._build_communication_queen_from_contract()
        for colony_id, records in grouped.items():
            self._build_cell_nodes(colony_id, records)
        self._build_local_colony_trails()
        self._build_mycelium_signal_trails()
        self._build_lane_state_from_snapshot()
        self._build_activity_feed_from_local_paths()

    def _build_communication_queen_from_contract(self) -> None:
        status = dict(self.communication_snapshot.get("status", {}))
        status_label = str(status.get("status_label", "Scaffold only / offline / no network"))
        self.protocol_state.update(
            {
                "source": "memory/COMMUNICATION_QUEEN_REMOTE_QUEEN_CONTRACT_V1.json",
                "status_label": status_label,
                "runtime_remote_queen_network_enabled": bool(status.get("runtime_remote_queen_network_enabled")),
                "remote_queen_runtime_enabled": bool(status.get("remote_queen_runtime_enabled")),
                "provider_or_api_calls_enabled": bool(status.get("provider_or_api_calls_enabled")),
                "internet_behavior_enabled": bool(status.get("internet_behavior_enabled")),
                "background_worker_enabled": bool(status.get("background_worker_enabled")),
                "queue_mutation_enabled": bool(status.get("queue_mutation_enabled")),
                "trusted_memory_write_enabled": bool(status.get("trusted_memory_write_enabled")),
            }
        )
        node = SwarmNode(
            id=self.communication_queen_id,
            colony_id="communication-queen",
            label="COMMUNICATION QUEEN",
            position=(0.0, 0.0, 1.28),
            kind="communication_queen",
            health=1.0 if status else 0.0,
            protocol="COMMUNICATION_QUEEN_REMOTE_QUEEN_CONTRACT_V1",
            metadata={
                "status": status_label,
                "runtime_enabled": bool(status.get("remote_queen_runtime_enabled")),
                "network_enabled": bool(status.get("runtime_remote_queen_network_enabled")),
                "provider_enabled": bool(status.get("provider_or_api_calls_enabled")),
                "source": "memory/COMMUNICATION_QUEEN_REMOTE_QUEEN_CONTRACT_V1.json",
            },
        )
        self.nodes[self.communication_queen_id] = node
        self.queen_registry[self.communication_queen_id] = node

    def _build_cell_nodes(self, colony_id: str, records: list[dict[str, Any]]) -> None:
        colony = self.colonies.get(colony_id)
        if not colony:
            return
        count = max(1, len(records))
        role_to_kind = {
            "queen": "queen",
            "worker": "worker",
            "nest": "nest",
            "guardian": "guardian",
            "proposal": "proposal",
            "verifier": "verifier",
            "heart": "heart",
            "mycelium_signal": "signal_node",
        }
        for index, cell in enumerate(records):
            angle = math.tau * index / count + (0.18 if colony_id != "engel-core" else 0.0)
            ring = 0.48 + 0.15 * (index % 3)
            position = (
                colony.center[0] + math.cos(angle) * ring,
                colony.center[1] + math.sin(angle) * ring * 0.74,
                colony.center[2] + 0.14 + 0.08 * (index % 4),
            )
            role = str(cell.get("role", "nest"))
            node_id = str(cell.get("id", f"{colony_id}-node-{index + 1}"))
            exists = bool(cell.get("exists"))
            node = SwarmNode(
                id=node_id,
                colony_id=colony_id,
                label=str(cell.get("cell_name") or cell.get("actor") or self._title_from_id(node_id)),
                position=position,
                kind=role_to_kind.get(role, "nest"),
                health=1.0 if exists else 0.0,
                protocol=str(cell.get("command") or cell.get("signal_type") or "local-view"),
                metadata={
                    "role": role,
                    "status": str(cell.get("status", "LOCAL_VIEW")),
                    "local_link": str(cell.get("local_link", "")),
                    "exists": exists,
                    "kind": str(cell.get("kind", "unknown")),
                    "safety_state": str(cell.get("safety_state", "")),
                    "proposal_only": bool(cell.get("proposal_only")),
                    "confidence_marker": str(cell.get("confidence_marker", "")),
                    "current_task": str(cell.get("current_task", "")),
                },
            )
            self.nodes[node_id] = node
            if node.kind == "nest":
                self.nest_registry[node.id] = node
            elif node.kind == "queen":
                self.queen_registry[node.id] = node
            elif node.kind == "worker":
                self.worker_cell_registry[node.id] = node

    def _build_lane_state_from_snapshot(self) -> None:
        for item in self.source_snapshot.get("proposal_lanes", []):
            if isinstance(item, dict) and item.get("id"):
                self.lane_state[str(item["id"])] = dict(item)

    def _build_local_colony_trails(self) -> None:
        for colony_id in sorted(self.colonies):
            local_nodes = [node for node in self.nodes.values() if node.colony_id == colony_id]
            if len(local_nodes) < 2:
                continue
            anchor = self.primary_queen(colony_id) or sorted(local_nodes, key=lambda item: item.id)[0]
            for index, node in enumerate(sorted(local_nodes, key=lambda item: item.id)):
                if node.id == anchor.id:
                    continue
                trail_id = f"local_view_{colony_id}_{index:02d}"
                self.trails[trail_id] = SwarmTrail(
                    id=trail_id,
                    source=anchor.id,
                    target=node.id,
                    kind="local",
                    colony_id=colony_id,
                    points=self._curved_points(anchor.position, node.position, 0.18),
                    status="LOCAL_RECORD_LINK",
                    evidence="Same local Engel Hive colony_id in build_colony_hive_snapshot().",
                )

    def _build_mycelium_signal_trails(self) -> None:
        mappings = {
            "memory colonies": "chat-memories",
            "proposal candidates": "proposal-candidates",
            "guardian layer": "guardian-layer",
            "verifiers": "verifier-results",
            "colony heart": "engel-core",
            "route status": "route-status",
            "candidate lessons": "lesson-candidates",
            "proposal growth lane": "proposal-growth",
            "safety contracts": "safety-contracts",
            "engel permissions": "guardian-layer",
        }
        for index, signal in enumerate(self.source_snapshot.get("mycelium_signals", []), start=1):
            source_name = str(signal.get("from", "")).lower()
            target_name = str(signal.get("to", "")).lower()
            source_colony = mappings.get(source_name)
            target_colony = mappings.get(target_name)
            source_node = self._anchor_node_for_colony(source_colony or "")
            target_node = self._anchor_node_for_colony(target_colony or "")
            if not source_node or not target_node:
                continue
            trail_id = f"mycelium_signal_{index:02d}"
            self.trails[trail_id] = SwarmTrail(
                id=trail_id,
                source=source_node.id,
                target=target_node.id,
                kind="signal",
                colony_id=source_colony or "",
                inter_colony=source_node.colony_id != target_node.colony_id,
                points=self._curved_points(source_node.position, target_node.position, 0.42),
                status="READ_ONLY_SIGNAL",
                evidence=str(signal.get("signal_type", "local mycelium signal")),
                metadata={"runtime": str(signal.get("runtime", "read-only display"))},
            )

    def _build_activity_feed_from_local_paths(self) -> None:
        paths = [str(item) for item in self.signal_snapshot.get("recent_local_paths", [])]
        self.activity_feed = [f"Local signal source: {path}" for path in paths[:16]]

    def _anchor_node_for_colony(self, colony_id: str) -> SwarmNode | None:
        if not colony_id:
            return None
        return (
            self.primary_queen(colony_id)
            or next((node for node in self.nodes.values() if node.colony_id == colony_id), None)
        )

    def _curved_points(self, source: Point3, target: Point3, lift: float) -> list[Point3]:
        points: list[Point3] = []
        for step in range(30):
            t = step / 29.0
            arch = math.sin(t * math.pi) * lift
            x = source[0] * (1.0 - t) + target[0] * t
            y = source[1] * (1.0 - t) + target[1] * t
            z = source[2] * (1.0 - t) + target[2] * t + arch
            points.append((x, y, z))
        return points

    def primary_queen(self, colony_id: str) -> SwarmNode | None:
        queens = [node for node in self.nodes.values() if node.colony_id == colony_id and node.kind == "queen"]
        return sorted(queens, key=lambda node: node.id)[0] if queens else None

    def colony_nodes(self, colony_id: str) -> list[SwarmNode]:
        return [node for node in self.nodes.values() if node.colony_id == colony_id]

    def colony_workers(self, colony_id: str) -> list[SwarmNode]:
        return [node for node in self.nodes.values() if node.colony_id == colony_id and node.kind == "worker"]

    def selectable_nodes(self) -> list[SwarmNode]:
        return [
            node
            for node in self.nodes.values()
            if node.kind in {"queen", "communication_queen", "worker", "nest", "guardian", "proposal", "verifier", "heart", "signal_node"}
        ]

    def tick(self, dt_seconds: float) -> None:
        _ = dt_seconds

    def worker_position(self, worker: SwarmWorker) -> Point3:
        trail = self.trails.get(worker.trail_id)
        if not trail or len(trail.points) < 2:
            return (0.0, 0.0, 0.0)
        return interpolate_polyline(trail.points, worker.progress, worker.lane_offset, worker.phase)

    def metrics(self) -> dict[str, int]:
        nests = len(self.nest_registry)
        queens = len(self.queen_registry)
        worker_cells = len(self.worker_cell_registry)
        signals = sum(1 for trail in self.trails.values() if trail.kind == "signal")
        inter = sum(1 for trail in self.trails.values() if trail.inter_colony)
        ready = sum(int(colony.metadata.get("ready_records", 0)) for colony in self.colonies.values())
        total = sum(int(colony.metadata.get("total_records", 0)) for colony in self.colonies.values())
        readiness = int(round((ready / total) * 100)) if total else 0
        return {
            "colonies": len(self.colonies),
            "nests": nests,
            "queens": queens,
            "worker_cells": worker_cells,
            "workers": worker_cells,
            "worker_events": len(self.worker_event_store),
            "signals": signals,
            "inter": inter,
            "remote_queens": len(self.remote_queen_registry),
            "communication_nodes": 1 if self.communication_queen_id in self.nodes else 0,
            "growth_queue": len(self.growth_queue),
            "growth_paths": len(self.growth_paths),
            "guardian_layers": sum(1 for node in self.nodes.values() if node.kind == "guardian"),
            "telemetry_events": len(self.telemetry_events),
            "local_signal_strength": int(self.signal_snapshot.get("total_signal_strength", 0) or 0),
            "files_inspected": int(self.signal_snapshot.get("files_inspected", 0) or 0),
            "report_count": int(self.signal_snapshot.get("report_count", 0) or 0),
            "proposal_candidate_count": int(self.signal_snapshot.get("proposal_candidate_count", 0) or 0),
            "lane_records": len(self.lane_state),
            "verifier_signal_count": int(self.signal_snapshot.get("verifier_signal_count", 0) or 0),
            "guardian_warning_count": int(self.signal_snapshot.get("guardian_warning_count", 0) or 0),
            "local_readiness": readiness,
            "ready_records": ready,
            "total_records": total,
        }

    def local_status_label(self) -> str:
        unsafe_flags = [
            "runtime_remote_queen_network_enabled",
            "remote_queen_runtime_enabled",
            "provider_or_api_calls_enabled",
            "internet_behavior_enabled",
            "background_worker_enabled",
            "queue_mutation_enabled",
            "trusted_memory_write_enabled",
        ]
        safe = "SAFE" if not any(bool(self.protocol_state.get(flag)) for flag in unsafe_flags) else "CHECK"
        idle = "IDLE" if not self.growth_paths and not self.remote_queen_registry else "LOCAL VIEW"
        monitor = "MONITORING" if self.permission_store or self.metrics()["guardian_layers"] else "LOCAL VIEW"
        return f"{safe} + {idle} + {monitor}"

    def assistant_summary(self) -> str:
        metrics = self.metrics()
        cq_status = self.nodes.get(self.communication_queen_id)
        cq_text = cq_status.metadata.get("status", "unavailable") if cq_status else "unavailable"
        return (
            f"True local view model loaded from Engel Research Office snapshot.\n"
            f"{metrics['colonies']} local colonies, {metrics['queens']} queens, "
            f"{metrics['worker_cells']} worker cells, {metrics['worker_events']} worker events, {metrics['nests']} nests.\n"
            f"Communication Queen: {cq_text}.\n"
            f"Remote Queen registry: {metrics['remote_queens']} registered.\n"
            f"Growth paths: {metrics['growth_paths']} active.\n"
            f"Telemetry events: {metrics['telemetry_events']} recorded.\n"
            f"Proposal/lane records: {metrics['lane_records']}.\n"
            f"Provider, network, runtime, queue, and trusted-memory actions are disabled."
        )

    def section_summary(self, section: str) -> str:
        adapter = self.section_adapter(section)
        if adapter is not None:
            return adapter.summary(self)
        return self.assistant_summary()

    def section_detail(self, section: str, selected_id: str = "") -> str:
        adapter = self.section_adapter(section)
        if adapter is not None:
            return adapter.detail(self, selected_id)
        return self.selected_detail_text(selected_id)

    def selected_detail_text(self, selected_id: str) -> str:
        if selected_id in self.nodes:
            node = self.node_summary(selected_id)
            return (
                f"Selected: {node['label']}\n\n"
                f"Node type: {node['kind']}\n"
                f"Status: {node['status']}\n"
                f"Protocol/source: {node['protocol']}\n"
                f"Readiness: {node['health']}\n"
                f"Local link: {node.get('local_link', 'unavailable')}\n"
                f"Safety state: {node.get('safety_state', 'unavailable')}\n\n"
                "Selection updates this local view only. No route, memory, queue, provider, network, or worker-service action starts here."
            )
        if selected_id in self.colonies:
            summary = self.colony_summary(selected_id)
            return (
                f"{summary['label']}\n\n"
                f"Status: {summary['status']}\n"
                f"Queens: {summary['queens']}\n"
                f"Nests: {summary['nests']}\n"
                f"Worker cells: {summary['workers']}\n"
                f"Local record links: {summary['local_trails']}\n"
                f"Mycelium links: {summary['signals']}\n"
                f"Local signal count: {summary['signal_count']}\n"
                f"Readiness: {summary['ready_records']} / {summary['total_records']}\n\n"
                "Selection updates this local view only. No route, memory, queue, provider, network, or worker-service action starts here."
            )
        return self.section_detail("hive_overview")

    def signal_analyzer_text(self) -> str:
        return self.section_detail("signal_analyzer")

    def telemetry_store_text(self) -> str:
        return self.section_detail("telemetry_events")

    def proposal_lanes_text(self) -> str:
        return self.section_detail("growth_paths")

    def activity_text(self) -> str:
        return self.section_detail("activity_sources")

    def short_entity_text(self, entity_id: str) -> str:
        if entity_id in self.nodes:
            node = self.node_summary(entity_id)
            return (
                f"{node['label']}\n"
                f"{node['kind']} | {node['status']}\n"
                f"{node['health']}\n"
                "Local view only"
            )
        if entity_id in self.colonies:
            summary = self.colony_summary(entity_id)
            return (
                f"{summary['label']}\n"
                f"Queens {summary['queens']} | Nests {summary['nests']} | Worker cells {summary['worker_cells']}\n"
                f"Readiness {summary['ready_records']} / {summary['total_records']}\n"
                "Local snapshot record"
            )
        if entity_id == "hive_overview":
            metrics = self.metrics()
            return f"Hive Overview\n{metrics['colonies']} colonies | {metrics['telemetry_events']} telemetry events\nTrue local view model"
        return "No local Hive entity selected."

    def colony_summary(self, colony_id: str) -> dict[str, Any]:
        colony = self.colonies[colony_id]
        nodes = self.colony_nodes(colony_id)
        nests = sum(1 for node in nodes if node.kind == "nest")
        queens = sum(1 for node in nodes if node.kind == "queen")
        worker_cells = sum(1 for node in nodes if node.kind == "worker")
        worker_events = sum(1 for event in self.worker_event_store.values() if event.colony_id == colony_id)
        local_trails = sum(1 for trail in self.trails.values() if trail.colony_id == colony_id and trail.kind == "local")
        signals = sum(1 for trail in self.trails.values() if trail.colony_id == colony_id and trail.kind == "signal")
        return {
            "label": colony.label,
            "nests": nests,
            "queens": queens,
            "worker_cells": worker_cells,
            "workers": worker_events,
            "local_trails": local_trails,
            "signals": signals,
            "signal_count": int(colony.metadata.get("signal_count", 0)),
            "ready_records": int(colony.metadata.get("ready_records", 0)),
            "total_records": int(colony.metadata.get("total_records", 0)),
            "status": "VISIBLE" if colony.active else "HIDDEN IN VIEW",
        }

    def node_summary(self, node_id: str) -> dict[str, Any]:
        node = self.nodes.get(node_id)
        if not node:
            return {"label": "Unknown", "kind": "unknown", "status": "UNKNOWN"}
        readiness = "local artifact ready" if bool(node.metadata.get("exists")) else "local artifact unavailable"
        if node.kind == "communication_queen":
            readiness = "local contract loaded" if node.health > 0 else "local contract unavailable"
        return {
            "label": node.label,
            "kind": node.kind.replace("_", " ").title(),
            "status": str(node.metadata.get("status", "LOCAL_VIEW")),
            "protocol": node.protocol,
            "health": readiness,
            "local_link": str(node.metadata.get("local_link", node.metadata.get("source", "unavailable"))),
            "safety_state": str(node.metadata.get("safety_state", node.metadata.get("status", "unavailable"))),
        }

    def colony_table_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for colony in self.colonies.values():
            summary = self.colony_summary(colony.id)
            queen = self.primary_queen(colony.id)
            total = max(1, summary["total_records"])
            readiness = int(round((summary["ready_records"] / total) * 100)) if summary["total_records"] else 0
            rows.append(
                {
                    "colony_id": colony.id,
                    "label": colony.label,
                    "assigned_queen": queen.label if queen else "No queen record",
                    "worker_count": summary["worker_cells"],
                    "health": readiness,
                    "status": "Visible" if colony.active else "Hidden",
                    "sector": f"Local records {summary['ready_records']}/{summary['total_records']}",
                    "nests": summary["nests"],
                    "signals": summary["signals"],
                }
            )
        return rows

    def queen_records(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for node in sorted(self.queen_registry.values(), key=lambda item: item.id):
            status = str(node.metadata.get("status", "LOCAL_VIEW"))
            assigned = self.colonies.get(node.colony_id).label if node.colony_id in self.colonies else "Communication Queen contract"
            readiness = 100 if node.health > 0 else 0
            records.append(
                {
                    "id": node.id,
                    "label": node.label,
                    "status": status,
                    "age": "unavailable",
                    "health": readiness,
                    "assigned_hive": assigned,
                    "readiness_progress": readiness,
                    "protocol": node.protocol,
                }
            )
        return records

    def connection_records(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for trail in self.trails.values():
            if trail.kind not in {"local", "signal"}:
                continue
            source_node = self.nodes.get(trail.source)
            target_node = self.nodes.get(trail.target)
            records.append(
                {
                    "id": trail.id,
                    "source": source_node.label if source_node else trail.source,
                    "target": target_node.label if target_node else trail.target,
                    "type": trail.kind.replace("_", " ").title(),
                    "status": trail.status,
                    "evidence": trail.evidence or "local view-model relationship",
                    "source_path": str(trail.metadata.get("runtime", "local snapshot")),
                }
            )
        return records

    def message_records(self) -> list[dict[str, str]]:
        if not self.messages:
            self._rebuild_messages_from_state()
        return list(self.messages)

    def expansion_rows(self) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for item in self.growth_paths.values():
            rows.append(
                {
                    "id": item.id,
                    "source": item.source,
                    "target": item.target,
                    "evidence": item.evidence or "local growth-path record",
                    "status": item.status,
                }
            )
        return rows

    def permission_rows(self) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for item in self.permission_store:
            role = "Permission Gate" if bool(item.get("requires_approval")) else "Read Only Signal"
            rows.append(
                {
                    "id": str(item.get("permission_id", "")),
                    "role": role,
                    "access": str(item.get("gate_status") or item.get("status_badge") or item.get("current_state", "")),
                    "last": "LOCAL STATE",
                    "colonies": str(item.get("label", item.get("name", ""))),
                }
            )
        return rows

    def permission_user_records(self) -> list[PermissionUserRecord]:
        return sorted(self.permission_user_store.values(), key=lambda item: item.id.lower())

    def permission_user_colonies(self) -> list[str]:
        return sorted({colony for user in self.permission_user_store.values() for colony in user.assigned_colonies})

    def upsert_permission_user(self, user: PermissionUserRecord, original_id: str = "") -> None:
        valid_roles = {"Admin", "Moderator", "Operator", "Viewer"}
        valid_access = {"Full", "Limited", "Read-Only"}
        valid_status = {"Active", "Pending", "Revoked"}
        cleaned_id = " ".join(user.id.strip().split())
        if not cleaned_id:
            raise ValueError("User/Agent ID is required.")
        if user.role not in valid_roles:
            raise ValueError("Role must be Admin, Moderator, Operator, or Viewer.")
        if user.access_level not in valid_access:
            raise ValueError("Access level must be Full, Limited, or Read-Only.")
        if user.status not in valid_status:
            raise ValueError("Status must be Active, Pending, or Revoked.")
        if cleaned_id != original_id and cleaned_id in self.permission_user_store:
            raise ValueError("User/Agent ID must be unique in the session-local store.")
        if original_id and original_id != cleaned_id:
            self.permission_user_store.pop(original_id, None)
        user.id = cleaned_id
        user.assigned_colonies = sorted({" ".join(item.strip().split()) for item in user.assigned_colonies if item.strip()})
        user.last_activity = self._full_timestamp()
        if not user.activity_log:
            user.activity_log.append(f"{user.last_activity} - Session-local permission record created.")
        self.permission_user_store[user.id] = user
        self.data_updated.emit()

    def remove_permission_user(self, user_id: str) -> None:
        self.permission_user_store.pop(user_id, None)
        self.data_updated.emit()

    def set_permission_user_status(self, user_ids: list[str], status: str) -> None:
        if status not in {"Active", "Pending", "Revoked"}:
            return
        timestamp = self._full_timestamp()
        for user_id in user_ids:
            user = self.permission_user_store.get(user_id)
            if not user:
                continue
            user.status = status
            user.last_activity = timestamp
            user.activity_log.insert(0, f"{timestamp} - Session-local status changed to {status}.")
        self.data_updated.emit()

    def assign_permission_user_colonies(self, user_ids: list[str], colonies: list[str]) -> None:
        cleaned = sorted({" ".join(item.strip().split()) for item in colonies if item.strip()})
        if not cleaned:
            return
        timestamp = self._full_timestamp()
        for user_id in user_ids:
            user = self.permission_user_store.get(user_id)
            if not user:
                continue
            user.assigned_colonies = sorted(set(user.assigned_colonies) | set(cleaned))
            user.last_activity = timestamp
            user.activity_log.insert(0, f"{timestamp} - Session-local colonies assigned: {', '.join(cleaned)}.")
        self.data_updated.emit()

    def update_permission_user_field(self, user_id: str, field_name: str, value: str) -> None:
        user = self.permission_user_store.get(user_id)
        if not user:
            return
        if field_name == "role" and value in {"Admin", "Moderator", "Operator", "Viewer"}:
            user.role = value
        elif field_name == "access_level" and value in {"Full", "Limited", "Read-Only"}:
            user.access_level = value
        else:
            return
        user.last_activity = self._full_timestamp()
        user.activity_log.insert(0, f"{user.last_activity} - Session-local {field_name.replace('_', ' ')} changed to {value}.")
        self.data_updated.emit()

    def _full_timestamp(self) -> str:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    def _rebuild_messages_from_state(self) -> None:
        metrics = self.metrics()
        generated_at = str(self.source_snapshot.get("generated_at", self._timestamp()))
        self.messages = [
            {
                "time": self._timestamp(),
                "channel": "Reports",
                "message": f"Local Hive view model loaded from snapshot generated {generated_at}",
                "status": "Active",
                "source": "local-view",
            },
            {
                "time": self._timestamp(),
                "channel": "Reports",
                "message": f"{metrics['colonies']} colonies / {metrics['queens']} queens / {metrics['worker_cells']} worker cells / {metrics['nests']} nests",
                "status": "Active",
                "source": "local-view",
            },
            {
                "time": self._timestamp(),
                "channel": "Alerts",
                "message": "Remote Queen registry empty; candidate-only contract entries are not shown as registered devices",
                "status": "Active",
                "source": "local-view",
            },
            {
                "time": self._timestamp(),
                "channel": "Reports",
                "message": "Growth path and telemetry stores are true local stores with zero records",
                "status": "Active",
                "source": "local-view",
            },
        ]
        if self.source_error:
            self.messages.insert(
                0,
                {
                    "time": self._timestamp(),
                    "channel": "Alerts",
                    "message": "Local snapshot unavailable: " + self.source_error,
                    "status": "Warning",
                    "source": "local-view",
                },
            )

    def request_selection(self, entity_id: str) -> None:
        self.selection_requested.emit(entity_id)

    def request_section_focus(self, section: str) -> None:
        self.focus_section(section)

    def toggle_colony_active(self, colony_id: str) -> None:
        colony = self.colonies.get(colony_id)
        if not colony:
            return
        colony.active = not colony.active
        self._append_message(
            "Commands",
            f"{colony.label} visibility changed to {'Visible' if colony.active else 'Hidden'} in local GUI state",
            "Active",
        )
        self.data_updated.emit()

    def add_visual_colony(self) -> None:
        self._append_message(
            "Alerts",
            "No growth colony was added: the true local growth-path store has no approved records.",
            "Warning",
        )
        self.data_updated.emit()

    def assign_queen(self, queen_id: str) -> None:
        _ = queen_id
        self._append_message(
            "Alerts",
            "Queen assignment is disabled here; no runtime authority or true assignment store is enabled.",
            "Warning",
        )
        self.data_updated.emit()

    def retire_queen(self, queen_id: str) -> None:
        _ = queen_id
        self._append_message(
            "Alerts",
            "Queen retirement is disabled here; this screen does not mutate queen registry state.",
            "Warning",
        )
        self.data_updated.emit()

    def hatch_queen(self, queen_id: str) -> None:
        _ = queen_id
        self._append_message(
            "Alerts",
            "Queen hatching is disabled because no true local growth event store has records to hatch.",
            "Warning",
        )
        self.data_updated.emit()

    def add_communication_message(self, text: str, channel: str = "Requests", status: str = "Pending") -> None:
        cleaned = " ".join(text.strip().split())
        if not cleaned:
            return
        self._append_message(channel, cleaned[:180], status)
        self.data_updated.emit()

    def _append_message(self, channel: str, message: str, status: str = "Active") -> None:
        self.messages.insert(
            0,
            {
                "time": self._timestamp(),
                "channel": channel,
                "message": message,
                "status": status,
                "source": "session",
            },
        )
        self.messages = self.messages[:48]

    def acknowledge_messages(self) -> int:
        count = 0
        for item in self.messages:
            if item["status"] in {"Pending", "Warning"}:
                item["status"] = "Active"
                count += 1
        self._append_message("Reports", f"Acknowledged {count} local GUI message item(s)", "Active")
        self.data_updated.emit()
        return count

    def route_messages(self) -> None:
        self._append_message(
            "Alerts",
            "Routing action disabled: Communication Queen runtime/network paths are not enabled.",
            "Warning",
        )
        self.data_updated.emit()

    def companion_response(self, user_text: str) -> str:
        cleaned = " ".join(user_text.strip().split()).lower()
        if not cleaned:
            return self.assistant_summary()
        if route_companion_text_or_command is not None:
            llm_enabled = bool(offline_seed_llm_gate_enabled()) if offline_seed_llm_gate_enabled is not None else False
            routed = route_companion_text_or_command(
                user_text,
                context="Super Swarm Hive",
                local_llm_fn=run_offline_seed_llm_for_companion_chat,
                llm_enabled=llm_enabled,
            )
            if routed.route_target == "colony_hive_status":
                return self.section_summary("hive_overview")
            if routed.route_target == "offline_seed_llm_status":
                if render_offline_seed_llm_status is not None:
                    return render_offline_seed_llm_status()
                return routed.response
            if routed.route_target == "human_command_mode":
                return routed.response + "\n\nUse the Engel CLI or Companion command box for guarded Human Command Mode execution."
            if routed.intent.category in {"companion_greeting", "companion_question", "unsafe_or_requires_approval", "unknown_command_candidate", "human_command_candidate"}:
                return routed.response
            if routed.intent.category == "companion_chat" and routed.intent.response_key == "general_chat":
                section_response = self._section_response_for_companion_text(cleaned)
                if section_response:
                    return section_response
                return routed.response
            if routed.intent.category == "companion_chat":
                return routed.response
        section_response = self._section_response_for_companion_text(cleaned)
        if section_response:
            return section_response
        return self.assistant_summary()

    def _section_response_for_companion_text(self, cleaned: str) -> str:
        if "research" in cleaned:
            return self.section_summary("research")
        if "think" in cleaned or "proposal" in cleaned:
            return self.section_summary("think")
        if "remote" in cleaned:
            return self.section_summary("remote_queens")
        if "growth" in cleaned:
            return self.section_summary("growth_paths")
        if "signal" in cleaned or "telemetry" in cleaned:
            return self.section_summary("signal_analyzer")
        if "communication" in cleaned or "queen" in cleaned:
            return self.section_summary("communication_queen")
        return ""

    def apply_local_hive_payload(self, payload: dict[str, Any]) -> None:
        """Apply a future approved in-memory local Hive payload without file, network, or provider behavior."""
        self.growth_paths.clear()
        self.growth_paths.update({
            str(item["id"]): GrowthPathRecord(
                id=str(item["id"]),
                source=str(item.get("source", "")),
                target=str(item.get("target", "")),
                status=str(item.get("status", "LOCAL_RECORD")),
                progress=float(item.get("progress", 0.0)),
                evidence=str(item.get("evidence", "")),
            )
            for item in payload.get("growth_paths", [])
            if "id" in item
        })
        self.remote_queen_registry.clear()
        self.remote_queen_registry.update({
            str(item["id"]): RemoteQueenRecord(
                id=str(item["id"]),
                label=str(item.get("label", item["id"])),
                status=str(item.get("status", "LOCAL_RECORD")),
                disabled_reason=str(item.get("disabled_reason", "")),
                source=str(item.get("source", "local-registry")),
            )
            for item in payload.get("remote_queens", [])
            if "id" in item
        })
        self.telemetry_events.clear()
        self.telemetry_events.extend([
            TelemetryEvent(
                id=str(item["id"]),
                label=str(item.get("label", "Telemetry event")),
                status=str(item.get("status", "LOCAL_RECORD")),
                source=str(item.get("source", "local-event")),
                detail=str(item.get("detail", "")),
            )
            for item in payload.get("telemetry_events", [])
            if "id" in item
        ])
        self.workers.clear()
        self.workers.update(
            {
                str(item["id"]): SwarmWorker(
                    id=str(item["id"]),
                    colony_id=str(item.get("colony_id", "")),
                    trail_id=str(item.get("trail_id", "")),
                    speed=float(item.get("speed", 0.0)),
                    progress=float(item.get("progress", 0.0)) % 1.0,
                    phase=float(item.get("phase", 0.0)),
                    lane_offset=float(item.get("lane_offset", 0.0)),
                )
                for item in payload.get("worker_events", [])
                if "id" in item
            }
        )
        self.lane_state.clear()
        self.lane_state.update(
            {
                str(item["id"]): dict(item)
                for item in payload.get("lane_records", [])
                if isinstance(item, dict) and "id" in item
            }
        )
        self.growth_queue = [
            {
                "id": item.id,
                "source": item.source,
                "target": item.target,
                "progress": item.progress,
                "status": item.status,
            }
            for item in self.growth_paths.values()
        ]
        self.data_updated.emit()

    def apply_payload(self, payload: dict[str, Any]) -> None:
        self.apply_local_hive_payload(payload)


class SuperSwarmMap3DWidget(QOpenGLWidget):
    colony_selected = pyqtSignal(str)

    def __init__(self, data_manager: DataManager) -> None:
        super().__init__()
        self.data_manager = data_manager
        self.layers = {
            "workers": True,
            "colony_links": True,
            "queens": True,
            "guardian": True,
            "inter_colony": True,
            "remote_queens": True,
            "growth_paths": True,
        }
        self.rotation_x = -58.0
        self.rotation_z = -4.0
        self.zoom = 16.5
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.selected_colony_id = next(iter(self.data_manager.colonies), "")
        self.hovered_entity_id = ""
        self.readable_labels = True
        self.show_minor_labels = False
        self.last_mouse = QPoint()
        self._drag_mode = "pan"
        self._last_frame = time.perf_counter()
        self._projection: Any = None
        self._modelview: Any = None
        self._viewport: Any = None
        self._projected_colonies: dict[str, tuple[float, float]] = {}
        self._projected_nodes: dict[str, tuple[float, float]] = {}

        self.setMinimumHeight(560)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.data_manager.data_updated.connect(self.update)

        self.animation_timer = QTimer(self)
        self.animation_timer.setInterval(24)
        self.animation_timer.timeout.connect(self._animate_frame)
        self.animation_timer.start()

    def set_layer_enabled(self, layer: str, enabled: bool) -> None:
        if layer in self.layers:
            self.layers[layer] = enabled
            self.update()

    def set_readable_labels(self, enabled: bool) -> None:
        self.readable_labels = enabled
        self.update()

    def set_minor_labels(self, enabled: bool) -> None:
        self.show_minor_labels = enabled
        self.update()

    def reset_camera(self) -> None:
        self.rotation_x = -58.0
        self.rotation_z = -4.0
        self.zoom = 16.5
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.update()

    def fit_to_data(self) -> None:
        points = [colony.center for colony in self.data_manager.colonies.values()]
        points.extend(node.position for node in self.data_manager.nodes.values())
        if not points:
            self.reset_camera()
            return
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        span = max(max(xs) - min(xs), max(ys) - min(ys), 1.0)
        center_x = (min(xs) + max(xs)) / 2.0
        center_y = (min(ys) + max(ys)) / 2.0
        self.rotation_x = -58.0
        self.rotation_z = -4.0
        self.zoom = max(10.0, min(30.0, span * 1.28 + 7.5))
        self.pan_x = -center_x * 0.08
        self.pan_y = -center_y * 0.08
        self.update()

    def zoom_in(self) -> None:
        self.zoom = max(9.0, self.zoom - 0.85)
        self.update()

    def zoom_out(self) -> None:
        self.zoom = min(28.0, self.zoom + 0.85)
        self.update()

    def pan_left(self) -> None:
        self.pan_x -= 0.32
        self.update()

    def pan_right(self) -> None:
        self.pan_x += 0.32
        self.update()

    def pan_up(self) -> None:
        self.pan_y += 0.32
        self.update()

    def pan_down(self) -> None:
        self.pan_y -= 0.32
        self.update()

    def center_selected(self) -> None:
        selected = str(self.selected_colony_id or "").strip()
        if not selected:
            return
        if selected in self.data_manager.colonies:
            point = self.data_manager.colonies[selected].center
            self.pan_x = -point[0] * 0.08
            self.pan_y = -point[1] * 0.08
            self.update()
            return
        node = self.data_manager.nodes.get(selected)
        if node is not None:
            self.pan_x = -node.position[0] * 0.08
            self.pan_y = -node.position[1] * 0.08
            self.update()

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
            self.reset_camera()
            event.accept()
            return
        if key == Qt.Key_F:
            self.fit_to_data()
            event.accept()
            return
        super().keyPressEvent(event)

    def initializeGL(self) -> None:
        if not OPENGL_READY:
            return
        glClearColor(0.027, 0.035, 0.047, 1.0)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glEnable(GL_LINE_SMOOTH)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glShadeModel(GL_SMOOTH)

    def resizeGL(self, width: int, height: int) -> None:
        if OPENGL_READY:
            glViewport(0, 0, max(1, width), max(1, height))

    def paintGL(self) -> None:
        if not OPENGL_READY:
            self._paint_fallback_message()
            return

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        width = max(1, self.width())
        height = max(1, self.height())

        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(44.0, width / height, 0.1, 120.0)

        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        glTranslatef(self.pan_x, self.pan_y, -self.zoom)
        glRotatef(self.rotation_x, 1.0, 0.0, 0.0)
        glRotatef(self.rotation_z, 0.0, 0.0, 1.0)

        self._draw_starfield()
        self._draw_floor_grid()
        if self.layers["guardian"]:
            self._draw_global_swarm_perimeter()
            self._draw_colony_guardian_halos()
        if self.layers["inter_colony"]:
            self._draw_inter_colony_links()
        if self.layers["growth_paths"]:
            self._draw_growth_paths()
        if self.layers["remote_queens"]:
            self._draw_remote_links()
        if self.layers["colony_links"]:
            self._draw_local_trails()
        if self.layers["inter_colony"]:
            self._draw_signal_trails()
        self._draw_colony_nodes()
        self._draw_communication_queen()
        if self.layers["remote_queens"]:
            self._draw_remote_queens()
        if self.layers["workers"]:
            self._draw_workers()

        self._modelview = glGetDoublev(GL_MODELVIEW_MATRIX)
        self._projection = glGetDoublev(GL_PROJECTION_MATRIX)
        self._viewport = glGetIntegerv(GL_VIEWPORT)
        self._draw_overlay_labels()

    def _paint_fallback_message(self) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(SWARM_BG_PRIMARY))
        painter.setPen(QColor(SWARM_ACCENT_INFO))
        painter.setFont(QFont("Consolas", 10, QFont.Weight.Normal))
        painter.drawText(
            self.rect(),
            Qt.AlignmentFlag.AlignCenter,
            "PyOpenGL required for 3D Super Swarm view",
        )
        painter.end()

    def _animate_frame(self) -> None:
        now = time.perf_counter()
        self._last_frame = now
        self.update()

    def _draw_starfield(self) -> None:
        glPointSize(1.1)
        glBegin(GL_POINTS)
        for index in range(120):
            angle = index * 2.399
            radius = 4.0 + (index % 23) * 0.42
            x = math.cos(angle) * radius
            y = math.sin(angle) * radius * 0.68
            z = -1.7 - (index % 11) * 0.05
            glColor4f(0.08, 0.42, 0.54, 0.035)
            glVertex3f(x, y, z)
        glEnd()

    def _draw_floor_grid(self) -> None:
        glLineWidth(1.0)
        glBegin(GL_LINES)
        for line in range(-11, 12):
            alpha = 0.07 if line else 0.16
            glColor4f(0.0, 0.38, 0.46, alpha)
            glVertex3f(float(line), -7.0, -0.72)
            glVertex3f(float(line), 7.0, -0.72)
            glVertex3f(-8.3, float(line) * 0.65, -0.72)
            glVertex3f(8.3, float(line) * 0.65, -0.72)
        glEnd()

    def _draw_global_swarm_perimeter(self) -> None:
        t = time.perf_counter() * 1.15
        for ring_index, scale in enumerate([1.0, 1.035]):
            glLineWidth(2.0 - ring_index * 0.45)
            glBegin(GL_LINES)
            for index in range(180):
                if index % 5 in {0, 1}:
                    continue
                a0 = index / 180.0 * math.tau
                a1 = (index + 0.68) / 180.0 * math.tau
                pulse = 0.62 + 0.38 * math.sin(a0 * 6.0 + t)
                glColor4f(0.16, 0.66, 0.62, (0.07 - ring_index * 0.02) * pulse)
                glVertex3f(math.cos(a0) * 7.4 * scale, math.sin(a0) * 5.25 * scale, -0.33)
                glVertex3f(math.cos(a1) * 7.4 * scale, math.sin(a1) * 5.25 * scale, -0.33)
            glEnd()

    def _draw_colony_guardian_halos(self) -> None:
        t = time.perf_counter() * 1.7
        for colony in self.data_manager.colonies.values():
            for ring_index, scale in enumerate([1.0, 1.08]):
                glLineWidth(1.65 - ring_index * 0.35)
                glBegin(GL_LINES)
                for index in range(96):
                    if index % 4 == 0:
                        continue
                    a0 = index / 96.0 * math.tau
                    a1 = (index + 0.65) / 96.0 * math.tau
                    pulse = 0.55 + 0.45 * math.sin(a0 * 4.0 + t)
                    glColor4f(colony.color[0], colony.color[1], colony.color[2], (0.055 - ring_index * 0.014) * pulse)
                    glVertex3f(
                        colony.center[0] + math.cos(a0) * colony.radius * scale,
                        colony.center[1] + math.sin(a0) * colony.radius * 0.75 * scale,
                        colony.center[2] - 0.25,
                    )
                    glVertex3f(
                        colony.center[0] + math.cos(a1) * colony.radius * scale,
                        colony.center[1] + math.sin(a1) * colony.radius * 0.75 * scale,
                        colony.center[2] - 0.25,
                    )
                glEnd()

    def _draw_communication_queen(self) -> None:
        node = self.data_manager.nodes.get(self.data_manager.communication_queen_id)
        if not node:
            return
        t = time.perf_counter()
        pulse = 0.5 + 0.5 * math.sin(t * 3.8)
        glPushMatrix()
        glTranslatef(*node.position)
        self._draw_sphere(0.55 + pulse * 0.05, (0.08, 0.62, 0.68, 0.045), 22, 14)
        self._draw_sphere(0.24, (0.38, 0.72, 0.76, 0.76), 20, 14)
        for ring_index, radius in enumerate([0.55, 0.82, 1.08]):
            glPushMatrix()
            glRotatef((t * 35.0 + ring_index * 35.0) % 360.0, 0.0, 0.0, 1.0)
            self._draw_hex_ring(radius, (0.10, 0.58, 0.68, 0.12 - ring_index * 0.025))
            glPopMatrix()
        glPopMatrix()

    def _draw_remote_queens(self) -> None:
        for node in self.data_manager.nodes.values():
            if node.kind != "remote_queen":
                continue
            pulse = 0.5 + 0.5 * math.sin(time.perf_counter() * 3.1 + len(node.id))
            glPushMatrix()
            glTranslatef(*node.position)
            self._draw_sphere(0.2 + pulse * 0.015, (0.16, 0.62, 0.58, 0.66), 15, 10)
            self._draw_sphere(0.48, (0.16, 0.62, 0.58, 0.026), 14, 8)
            self._draw_hex_ring(0.46, (0.16, 0.62, 0.58, 0.16))
            glPopMatrix()

    def _draw_local_trails(self) -> None:
        for trail in self.data_manager.trails.values():
            if trail.kind != "local":
                continue
            colony = self.data_manager.colonies.get(trail.colony_id)
            color = colony.color if colony else (1.0, 0.62, 0.06, 1.0)
            self._draw_polyline(trail.points, (color[0], color[1], color[2], 0.28), 1.45, True)

    def _draw_signal_trails(self) -> None:
        for trail in self.data_manager.trails.values():
            if trail.kind != "signal":
                continue
            self._draw_dotted_polyline(trail.points, (0.10, 0.46, 0.58, 0.32), 1.8)

    def _draw_inter_colony_links(self) -> None:
        for trail in self.data_manager.trails.values():
            if trail.kind not in {"inter", "comm"}:
                continue
            self._draw_dotted_polyline(trail.points, (0.10, 0.48, 0.60, 0.34), 2.4)

    def _draw_remote_links(self) -> None:
        for trail in self.data_manager.trails.values():
            if trail.kind != "remote":
                continue
            self._draw_dotted_polyline(trail.points, (0.13, 0.48, 0.46, 0.30), 2.1)

    def _draw_growth_paths(self) -> None:
        for trail in self.data_manager.trails.values():
            if trail.kind != "growth":
                continue
            self._draw_dotted_polyline(trail.points, (0.38, 0.28, 0.54, 0.30), 2.0)

    def _draw_polyline(self, points: list[Point3], color: ColorTuple, width: float, glow: bool) -> None:
        if len(points) < 2:
            return
        if glow:
            glLineWidth(width + 2.0)
            glBegin(GL_LINES)
            for a, b in zip(points, points[1:]):
                glColor4f(color[0], color[1], color[2], 0.014)
                glVertex3f(*a)
                glVertex3f(*b)
            glEnd()
        glLineWidth(width)
        glBegin(GL_LINES)
        for a, b in zip(points, points[1:]):
            glColor4f(*color)
            glVertex3f(*a)
            glVertex3f(*b)
        glEnd()

    def _draw_dotted_polyline(self, points: list[Point3], color: ColorTuple, width: float) -> None:
        if len(points) < 2:
            return
        glLineWidth(width + 2.2)
        glBegin(GL_LINES)
        for index, (a, b) in enumerate(zip(points, points[1:])):
            if index % 3 == 1:
                glColor4f(color[0], color[1], color[2], 0.014)
                glVertex3f(*a)
                glVertex3f(*b)
        glEnd()
        glLineWidth(width)
        glBegin(GL_LINES)
        for index, (a, b) in enumerate(zip(points, points[1:])):
            if index % 3 == 1:
                glColor4f(*color)
                glVertex3f(*a)
                glVertex3f(*b)
        glEnd()

    def _draw_colony_nodes(self) -> None:
        for node in self.data_manager.nodes.values():
            if node.kind in {"communication_queen", "remote_queen"}:
                continue
            if node.kind == "worker" and not self.layers["workers"]:
                continue
            if node.kind == "queen" and not self.layers["queens"]:
                continue
            colony = self.data_manager.colonies.get(node.colony_id)
            colony_color = colony.color if colony else (0.0, 0.58, 0.75, 1.0)
            color_map: dict[str, ColorTuple] = {
                "queen": (0.74, 0.58, 0.20, 0.76),
                "worker": (0.13, 0.58, 0.78, 0.70),
                "nest": (0.22, 0.74, 0.38, 0.68),
                "guardian": (0.62, 0.45, 0.86, 0.72),
                "proposal": (0.94, 0.52, 0.20, 0.70),
                "verifier": (0.58, 0.68, 0.94, 0.70),
                "heart": (0.48, 0.88, 0.82, 0.74),
                "signal_node": (0.60, 0.46, 0.84, 0.66),
            }
            color = color_map.get(node.kind, (0.09, 0.36, 0.52, 0.66))
            radius = 0.17 if node.kind in {"queen", "heart", "guardian"} else 0.12
            selected = (
                node.id == self.selected_colony_id
                or node.colony_id == self.selected_colony_id
                or node.id == self.hovered_entity_id
                or node.colony_id == self.hovered_entity_id
            )
            self._draw_node(node, color, colony_color, radius, selected)

    def _draw_node(
        self,
        node: SwarmNode,
        color: ColorTuple,
        colony_color: ColorTuple,
        radius: float,
        selected: bool,
    ) -> None:
        pulse = 0.5 + 0.5 * math.sin(time.perf_counter() * 3.0)
        glPushMatrix()
        glTranslatef(*node.position)
        glow_radius = radius * (3.0 if selected else 2.05)
        self._draw_sphere(glow_radius, (colony_color[0], colony_color[1], colony_color[2], 0.024 + pulse * 0.016), 12, 8)
        self._draw_sphere(radius, color, 14, 9)
        if node.kind == "queen":
            self._draw_hex_ring(radius * 2.25, (0.56, 0.38, 0.72, 0.38))
        else:
            self._draw_hex_ring(radius * 1.95, (0.12, 0.50, 0.64, 0.28))
        glPopMatrix()

    def _draw_workers(self) -> None:
        for worker in self.data_manager.workers.values():
            trail = self.data_manager.trails.get(worker.trail_id)
            if not trail:
                continue
            if trail.kind in {"inter", "comm"} and not self.layers["inter_colony"]:
                continue
            if trail.kind == "remote" and not self.layers["remote_queens"]:
                continue
            if trail.kind == "growth" and not self.layers["growth_paths"]:
                continue
            point = self.data_manager.worker_position(worker)
            bob = 0.3 + 0.25 * math.sin(worker.phase)
            color = (0.62, 0.40, 0.16, 0.56)
            if trail.kind in {"inter", "comm", "remote"}:
                color = (0.12, 0.46, 0.58, 0.52)
            if trail.kind == "growth":
                color = (0.40, 0.30, 0.58, 0.50)
            glPushMatrix()
            glTranslatef(point[0], point[1], point[2] + 0.08 + bob * 0.06)
            self._draw_sphere(0.065, color, 10, 7)
            self._draw_sphere(0.145, (color[0], color[1], color[2], 0.036), 10, 7)
            glPopMatrix()

    def _draw_sphere(self, radius: float, color: ColorTuple, slices: int, stacks: int) -> None:
        glColor4f(*color)
        for stack in range(stacks):
            lat0 = math.pi * (-0.5 + stack / stacks)
            lat1 = math.pi * (-0.5 + (stack + 1) / stacks)
            z0 = math.sin(lat0) * radius
            zr0 = math.cos(lat0) * radius
            z1 = math.sin(lat1) * radius
            zr1 = math.cos(lat1) * radius
            glBegin(GL_TRIANGLE_STRIP)
            for slice_index in range(slices + 1):
                lng = math.tau * slice_index / slices
                x = math.cos(lng)
                y = math.sin(lng)
                glVertex3f(x * zr0, y * zr0, z0)
                glVertex3f(x * zr1, y * zr1, z1)
            glEnd()

    def _draw_hex_ring(self, radius: float, color: ColorTuple) -> None:
        glLineWidth(1.9)
        glColor4f(*color)
        glBegin(GL_LINE_LOOP)
        for index in range(6):
            angle = math.tau * index / 6.0 + math.pi / 6.0
            glVertex3f(math.cos(angle) * radius, math.sin(angle) * radius, 0.02)
        glEnd()

    def _draw_overlay_labels(self) -> None:
        if self._projection is None or self._modelview is None or self._viewport is None:
            return
        self._projected_colonies.clear()
        projected_nodes: dict[str, tuple[float, float]] = {}
        occupied: list[QRectF] = []
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setFont(QFont("Consolas", 9, QFont.Weight.Bold))

        if not self.data_manager.colonies and not self.data_manager.nodes:
            painter.setPen(QColor("#666666"))
            painter.setFont(QFont("Consolas", 9, QFont.Weight.Normal))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "no local hive records available\ntrue stores are empty",
            )
            painter.end()
            return

        colony_count = len(self.data_manager.colonies)
        for colony in self.data_manager.colonies.values():
            if self.readable_labels and not self.show_minor_labels and colony_count > 10 and colony.id != self.selected_colony_id:
                screen = self._world_to_screen((colony.center[0], colony.center[1], colony.center[2] + 1.2))
                if screen:
                    self._projected_colonies[colony.id] = screen
                continue
            screen = self._world_to_screen((colony.center[0], colony.center[1], colony.center[2] + 1.2))
            if not screen:
                continue
            x, y = screen
            self._projected_colonies[colony.id] = (x, y)
            color = QColor.fromRgbF(colony.color[0], colony.color[1], colony.color[2], 1.0)
            if colony.id == self.selected_colony_id:
                color = QColor("#ffaa00")
            summary = self.data_manager.colony_summary(colony.id)
            text = f"{colony.label}\nNests: {summary['nests']}  Cells: {summary['worker_cells']}"
            occupied.append(
                self._draw_label_box(
                    painter,
                    text,
                    x,
                    y,
                    color,
                    QFont("Consolas", 9 if colony.id == self.selected_colony_id else 8, QFont.Weight.Bold),
                    occupied,
                )
            )

        node_font = QFont("Consolas", 8, QFont.Weight.Bold)
        for node in self.data_manager.selectable_nodes():
            if node.kind == "remote_queen" and not self.layers["remote_queens"]:
                continue
            if self.readable_labels:
                is_selected = node.id == self.selected_colony_id
                in_selected_colony = node.colony_id == self.selected_colony_id
                if node.kind == "remote_queen" and not (is_selected or self.show_minor_labels):
                    continue
                if node.kind == "queen" and not (in_selected_colony or is_selected or self.show_minor_labels):
                    continue
                if node.kind in {"worker", "nest", "guardian", "proposal", "verifier", "heart", "signal_node"} and not (
                    in_selected_colony or is_selected or self.show_minor_labels
                ):
                    continue
            screen = self._world_to_screen((node.position[0], node.position[1], node.position[2] + 0.45))
            if not screen:
                continue
            projected_nodes[node.id] = screen
            if node.kind == "communication_queen":
                color = QColor("#44aaff")
                text = "COMM QUEEN\nLocal Contract"
            elif node.kind == "remote_queen":
                color = QColor("#00ff88")
                text = node.label
            elif node.kind == "worker":
                color = QColor("#ffaa00")
                text = node.label if self.show_minor_labels else "WORKER"
            elif node.kind == "nest":
                color = QColor("#44aaff")
                text = node.label if self.show_minor_labels else "NEST"
            else:
                color = QColor("#44aaff")
                text = node.label
            if node.id == self.selected_colony_id:
                color = QColor("#ffaa00")
            x, y = screen
            occupied.append(self._draw_label_box(painter, text, x, y, color, node_font, occupied))
        self._projected_nodes = projected_nodes

        painter.setFont(QFont("Consolas", 8, QFont.Weight.Normal))
        painter.setPen(QColor("#666666"))
        painter.drawText(
            18,
            self.height() - 18,
            "Drag pan | Right-drag rotate | Wheel zoom | Click local Hive records | Fit/Reset camera available",
        )
        painter.end()

    def _draw_label_box(
        self,
        painter: QPainter,
        text: str,
        anchor_x: float,
        anchor_y: float,
        color: QColor,
        font: QFont,
        occupied: list[QRectF],
    ) -> QRectF:
        painter.setFont(font)
        metrics = QFontMetrics(font)
        lines = text.splitlines() or [text]
        pad_x = 8
        pad_y = 6
        width = max(metrics.horizontalAdvance(line) for line in lines) + pad_x * 2
        height = metrics.lineSpacing() * len(lines) + pad_y * 2
        candidates = [
            QRectF(anchor_x + 10, anchor_y - height - 8, width, height),
            QRectF(anchor_x + 10, anchor_y + 10, width, height),
            QRectF(anchor_x - width - 10, anchor_y - height - 8, width, height),
            QRectF(anchor_x - width - 10, anchor_y + 10, width, height),
            QRectF(anchor_x - width / 2, anchor_y - height - 18, width, height),
        ]
        chosen = candidates[0]
        bounds = QRectF(6, 6, max(1, self.width() - 12), max(1, self.height() - 30))
        for candidate in candidates:
            candidate = QRectF(
                max(bounds.left(), min(candidate.left(), bounds.right() - candidate.width())),
                max(bounds.top(), min(candidate.top(), bounds.bottom() - candidate.height())),
                candidate.width(),
                candidate.height(),
            )
            if not any(candidate.adjusted(-6, -6, 6, 6).intersects(existing) for existing in occupied):
                chosen = candidate
                break
        bg = QColor(1, 7, 16, 218 if self.readable_labels else 150)
        border = QColor(color)
        border.setAlpha(165)
        painter.setBrush(QBrush(bg))
        painter.setPen(QPen(border, 1))
        painter.drawRoundedRect(chosen, 5, 5)
        text_x = int(chosen.left() + pad_x)
        text_y = int(chosen.top() + pad_y + metrics.ascent())
        for line in lines:
            painter.setPen(QPen(QColor(0, 0, 0, 210), 2))
            painter.drawText(text_x + 1, text_y + 1, line)
            painter.setPen(color)
            painter.drawText(text_x, text_y, line)
            text_y += metrics.lineSpacing()
        return chosen

    def _world_to_screen(self, point: Point3) -> tuple[float, float] | None:
        try:
            x, y, z = gluProject(
                point[0],
                point[1],
                point[2],
                self._modelview,
                self._projection,
                self._viewport,
            )
        except Exception:
            return None
        if z < 0.0 or z > 1.0:
            return None
        return float(x), float(self.height() - y)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        self.last_mouse = event.position().toPoint()
        if event.button() == Qt.MouseButton.LeftButton:
            entity_id = self._pick_entity(self.last_mouse)
            if entity_id:
                self.selected_colony_id = entity_id
                self.colony_selected.emit(entity_id)
                self.update()
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self._drag_mode = "rotate"
            else:
                self._drag_mode = "pan"
        elif event.button() == Qt.MouseButton.RightButton:
            self._drag_mode = "rotate"

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        current = event.position().toPoint()
        delta = current - self.last_mouse
        if event.buttons() & Qt.MouseButton.LeftButton:
            if self._drag_mode == "rotate":
                self.rotation_z += delta.x() * 0.32
                self.rotation_x += delta.y() * 0.20
                self.rotation_x = max(-82.0, min(-25.0, self.rotation_x))
            else:
                self.pan_x += delta.x() * 0.014
                self.pan_y -= delta.y() * 0.014
            self.update()
        elif event.buttons() & Qt.MouseButton.RightButton:
            self.rotation_z += delta.x() * 0.32
            self.rotation_x += delta.y() * 0.20
            self.rotation_x = max(-82.0, min(-25.0, self.rotation_x))
            self.update()
        else:
            entity_id = self._pick_entity(current)
            if entity_id != self.hovered_entity_id:
                self.hovered_entity_id = entity_id
                self.update()
            if entity_id:
                QToolTip.showText(event.globalPosition().toPoint(), self.data_manager.short_entity_text(entity_id), self)
            else:
                QToolTip.hideText()
        self.last_mouse = current

    def wheelEvent(self, event) -> None:  # type: ignore[override]
        amount = event.angleDelta().y() / 120.0
        self.zoom = max(9.0, min(28.0, self.zoom - amount * 0.75))
        self.update()

    def _pick_entity(self, point: QPoint) -> str:
        best: tuple[float, str] | None = None
        candidates = dict(self._projected_colonies)
        candidates.update(getattr(self, "_projected_nodes", {}))
        for colony in self.data_manager.colonies.values():
            if colony.id not in candidates:
                screen = self._world_to_screen((colony.center[0], colony.center[1], colony.center[2] + 0.5))
                if screen:
                    candidates[colony.id] = screen
        for node in self.data_manager.selectable_nodes():
            if node.id not in candidates:
                screen = self._world_to_screen((node.position[0], node.position[1], node.position[2] + 0.4))
                if screen:
                    candidates[node.id] = screen
        for colony_id, screen in candidates.items():
            distance = math.hypot(screen[0] - point.x(), screen[1] - point.y())
            if distance <= 90.0 and (best is None or distance < best[0]):
                best = (distance, colony_id)
        return best[1] if best else ""

    def _pick_colony(self, point: QPoint) -> str:
        return self._pick_entity(point)


class SingleColonyMapWidget(QFrame):
    node_selected = pyqtSignal(str)

    def __init__(self, data_manager: DataManager) -> None:
        super().__init__()
        self.data_manager = data_manager
        self.colony_id = next(iter(data_manager.colonies), "")
        self.selected_node_id = ""
        self.layers = {
            "workers": True,
            "trails": True,
            "queens": True,
            "signals": True,
            "guardian": True,
        }
        self._positions: dict[str, QPoint] = {}
        self.setMinimumHeight(430)
        self.setMouseTracking(True)
        self.setStyleSheet(
            f"QFrame {{ background: {SWARM_BG_PRIMARY}; border:1px solid {SWARM_BORDER_SUBTLE}; border-radius:6px; }}"
        )

    def set_colony(self, colony_id: str) -> None:
        self.colony_id = colony_id
        self.selected_node_id = ""
        self.update()

    def set_layer_enabled(self, layer: str, enabled: bool) -> None:
        self.layers[layer] = enabled
        self.update()

    def focus_primary_queen(self) -> None:
        queen = self.data_manager.primary_queen(self.colony_id)
        self.selected_node_id = queen.id if queen else ""
        if self.selected_node_id:
            self.node_selected.emit(self.selected_node_id)
        self.update()

    def fit_colony(self) -> None:
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor(SWARM_BG_PRIMARY))
        body = self.rect().adjusted(12, 12, -12, -12)
        colony = self.data_manager.colonies.get(self.colony_id)
        if not colony:
            painter.setPen(QColor(SWARM_TEXT_MUTED))
            painter.setFont(QFont("Consolas", 9, QFont.Weight.Normal))
            painter.drawText(body, Qt.AlignmentFlag.AlignCenter, "no local colony records available")
            painter.end()
            return

        painter.setPen(QColor(SWARM_ACCENT_INFO))
        painter.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
        painter.drawText(body.left(), body.top() + 14, f"COLONY MAP  {colony.label}")

        map_rect = body.adjusted(4, 22, -4, -4)
        nodes = [
            node
            for node in self.data_manager.colony_nodes(self.colony_id)
            if node.kind not in {"communication_queen", "remote_queen"}
        ]
        if not nodes:
            painter.setPen(QColor(SWARM_TEXT_MUTED))
            painter.setFont(QFont("Consolas", 9, QFont.Weight.Normal))
            painter.drawText(
                map_rect,
                Qt.AlignmentFlag.AlignCenter,
                "no local node records yet",
            )
            painter.end()
            return

        positions = self._node_positions(nodes, map_rect)
        self._positions = positions
        if self.layers["guardian"]:
            self._draw_guardian_boundary(painter, map_rect)
        if self.layers["trails"]:
            self._draw_colony_trails(painter, positions, "local", QColor("#ffaa00"))
        if self.layers["signals"]:
            self._draw_colony_trails(painter, positions, "signal", QColor("#44aaff"), dashed=True)
        for node in nodes:
            if node.kind == "worker" and not self.layers["workers"]:
                continue
            if node.kind == "queen" and not self.layers["queens"]:
                continue
            point = positions.get(node.id)
            if point is None:
                continue
            self._draw_node(painter, node, point)
        painter.end()

    def _node_positions(self, nodes: list[SwarmNode], rect: QRectF) -> dict[str, QPoint]:
        xs = [node.position[0] for node in nodes]
        ys = [node.position[1] for node in nodes]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        span_x = max(1.0, max_x - min_x)
        span_y = max(1.0, max_y - min_y)
        positions: dict[str, QPoint] = {}
        for node in nodes:
            x = rect.left() + ((node.position[0] - min_x) / span_x) * rect.width()
            y = rect.top() + ((node.position[1] - min_y) / span_y) * rect.height()
            positions[node.id] = QPoint(int(x), int(y))
        return positions

    def _draw_guardian_boundary(self, painter: QPainter, rect: QRectF) -> None:
        pen = QPen(QColor(SWARM_ACCENT_SAFE), 1, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(rect.adjusted(4, 4, -4, -4))

    def _draw_colony_trails(self, painter: QPainter, positions: dict[str, QPoint], kind: str, color: QColor, dashed: bool = False) -> None:
        style = Qt.PenStyle.DashLine if dashed else Qt.PenStyle.SolidLine
        color.setAlpha(190)
        painter.setPen(QPen(color, 2, style))
        for trail in self.data_manager.trails.values():
            if trail.colony_id != self.colony_id or trail.kind != kind:
                continue
            source = positions.get(trail.source)
            target = positions.get(trail.target)
            if source is not None and target is not None:
                painter.drawLine(source, target)

    def _draw_node(self, painter: QPainter, node: SwarmNode, point: QPoint) -> None:
        colors = {
            "queen": "#00ff88",
            "nest": "#44aaff",
            "worker": "#ffaa00",
            "guardian": "#00ff88",
            "proposal": "#ffaa00",
            "verifier": "#44aaff",
            "heart": "#00ff88",
            "signal_node": "#44aaff",
        }
        color = QColor(colors.get(node.kind, "#44aaff"))
        r = 6 if node.kind == "queen" else 4
        if node.id == self.selected_node_id:
            painter.setBrush(QBrush(QColor(115, 209, 139, 34)))
            painter.setPen(QPen(QColor(SWARM_ACCENT_SAFE), 1))
            painter.drawRect(point.x() - r - 4, point.y() - r - 4, (r + 4) * 2, (r + 4) * 2)
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(QColor(SWARM_BORDER_SUBTLE), 1))
        painter.drawRect(point.x() - r, point.y() - r, r * 2, r * 2)
        painter.setPen(QColor(SWARM_TEXT_PRIMARY))
        painter.setFont(QFont("Consolas", 7, QFont.Weight.Bold))
        painter.drawText(point.x() + r + 4, point.y() + 4, node.label)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        point = event.position().toPoint()
        best: tuple[float, str] | None = None
        for node_id, node_point in self._positions.items():
            distance = math.hypot(point.x() - node_point.x(), point.y() - node_point.y())
            if distance <= 34.0 and (best is None or distance < best[0]):
                best = (distance, node_id)
        if best:
            self.selected_node_id = best[1]
            self.node_selected.emit(best[1])
            self.update()


class SingleColonyHiveTab(QWidget):
    def __init__(self, data_manager: DataManager) -> None:
        super().__init__()
        self.data_manager = data_manager
        self.selected_colony_id = next(iter(data_manager.colonies), "")
        self.selected_node_id = ""
        self.colony_picker = QComboBox()
        self.map_widget = SingleColonyMapWidget(data_manager)
        self.metric_cards: dict[str, QFrame] = {}
        self.detail_box = QTextEdit()
        self.signal_box = QTextEdit()
        self.activity_box = QTextEdit()
        self.data_manager.data_updated.connect(self.refresh)
        self.data_manager.selection_requested.connect(self.set_selected_colony)
        self.map_widget.node_selected.connect(self._select_node)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        layout.addLayout(self._build_top_controls())

        body = QHBoxLayout()
        body.setSpacing(6)
        body.addWidget(self._build_left_controls())
        body.addWidget(self.map_widget, 1)
        layout.addLayout(body, 1)
        layout.addWidget(self._build_metric_bar())
        layout.addWidget(self._build_bottom_panels())
        self.refresh()

    def _build_top_controls(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(label("COLONY HIVE", 12, 900, "#00ff88"))
        row.addStretch(1)
        self.colony_picker.currentTextChanged.connect(self._picker_changed)
        self.colony_picker.setMaximumWidth(200)
        row.addWidget(self.colony_picker)
        focus_queen = QPushButton("FOCUS")
        focus_queen.setToolTip("Center on the primary queen node")
        focus_queen.clicked.connect(self.map_widget.focus_primary_queen)
        row.addWidget(focus_queen)
        fit = QPushButton("FIT")
        fit.setToolTip("Fit colony to view")
        fit.clicked.connect(self.map_widget.fit_colony)
        row.addWidget(fit)
        return row

    def _build_left_controls(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("SidePanel")
        frame.setFixedWidth(170)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)
        layout.addWidget(label("LAYERS", 8, 700, "#ffaa00"))
        for key, text in [
            ("workers", "Workers"),
            ("trails", "Trails"),
            ("queens", "Queens"),
            ("signals", "Signals"),
            ("guardian", "Guardian"),
        ]:
            cb = QCheckBox(text)
            cb.setChecked(True)
            cb.toggled.connect(lambda checked, layer=key: self.map_widget.set_layer_enabled(layer, checked))
            layout.addWidget(cb)
        layout.addSpacing(4)
        layout.addWidget(label("LEGEND", 8, 700, "#ffaa00"))
        for text, color in [
            ("Nest", "#44aaff"),
            ("Queen", "#00ff88"),
            ("Worker", "#ffaa00"),
            ("Signal", "#44aaff"),
            ("Guardian", "#00ff88"),
        ]:
            layout.addWidget(legend_item(text, color))
        layout.addStretch(1)
        return frame

    def _build_metric_bar(self) -> QWidget:
        host, cards = mini_metric_row([
            ("QUEENS",    "0",  "#00ff88"),
            ("NESTS",     "0",  "#44aaff"),
            ("WORKERS",   "0",  "#ffaa00"),
            ("SIGNALS",   "0",  "#44aaff"),
            ("READINESS", "0%", "#00ff88"),
        ])
        self.metric_cards = cards
        return host

    def _build_bottom_panels(self) -> QWidget:
        row = QSplitter(Qt.Orientation.Horizontal)
        row.setMinimumHeight(180)
        for widget, title, color in [
            (self.detail_box,   "DETAILS",  "#44aaff"),
            (self.signal_box,   "SIGNALS",  "#ffaa00"),
            (self.activity_box, "ACTIVITY", "#00ff88"),
        ]:
            widget.setReadOnly(True)
            widget.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
            widget.setStyleSheet(text_box_style())
            wrapper = QFrame()
            wrapper.setObjectName("BottomPanel")
            wl = QVBoxLayout(wrapper)
            wl.setContentsMargins(7, 6, 7, 6)
            wl.setSpacing(4)
            wl.addWidget(label(title, 8, 900, color))
            wl.addWidget(widget)
            row.addWidget(wrapper)
        row.setSizes([340, 340, 340])
        return row

    def set_selected_colony(self, colony_id: str) -> None:
        if colony_id in self.data_manager.nodes:
            node = self.data_manager.nodes[colony_id]
            colony_id = node.colony_id
        if colony_id not in self.data_manager.colonies:
            return
        self.selected_colony_id = colony_id
        self.map_widget.set_colony(colony_id)
        index = self.colony_picker.findData(colony_id)
        if index >= 0 and self.colony_picker.currentIndex() != index:
            self.colony_picker.setCurrentIndex(index)
        self.refresh()

    def _picker_changed(self) -> None:
        colony_id = str(self.colony_picker.currentData() or "")
        if colony_id and colony_id != self.selected_colony_id:
            self.set_selected_colony(colony_id)

    def _select_node(self, node_id: str) -> None:
        self.selected_node_id = node_id
        self._refresh_text()

    def refresh(self) -> None:
        current = self.selected_colony_id
        self.colony_picker.blockSignals(True)
        self.colony_picker.clear()
        for colony in self.data_manager.colonies.values():
            self.colony_picker.addItem(colony.label, colony.id)
        index = self.colony_picker.findData(current)
        if index < 0 and self.data_manager.colonies:
            current = next(iter(self.data_manager.colonies))
            index = self.colony_picker.findData(current)
        if index >= 0:
            self.colony_picker.setCurrentIndex(index)
            self.selected_colony_id = current
        self.colony_picker.blockSignals(False)
        self.map_widget.set_colony(self.selected_colony_id)
        self._refresh_metrics()
        self._refresh_text()

    def _refresh_metrics(self) -> None:
        if self.selected_colony_id not in self.data_manager.colonies:
            values = {title: "0" for title in self.metric_cards}
        else:
            summary = self.data_manager.colony_summary(self.selected_colony_id)
            total = summary["total_records"]
            readiness = int(round((summary["ready_records"] / total) * 100)) if total else 0
            values = {
                "QUEENS":    str(summary["queens"]),
                "NESTS":     str(summary["nests"]),
                "WORKERS":   str(summary["worker_cells"]),
                "SIGNALS":   str(summary["signals"]),
                "READINESS": f"{readiness}%",
            }
        for title, value in values.items():
            card = self.metric_cards.get(title)
            if card is not None and hasattr(card, "value_label"):
                card.value_label.setText(value)  # type: ignore[attr-defined]

    def _refresh_text(self) -> None:
        if self.selected_colony_id not in self.data_manager.colonies:
            empty = "No local colony selected.\nTrue colony registry is empty."
            self.detail_box.setPlainText(empty)
            self.signal_box.setPlainText("No signal records available.")
            self.activity_box.setPlainText("No activity records available.")
            return
        colony = self.data_manager.colonies[self.selected_colony_id]
        summary = self.data_manager.colony_summary(self.selected_colony_id)
        selected = self.data_manager.node_summary(self.selected_node_id) if self.selected_node_id else None
        detail_lines = [
            f"Colony: {colony.label}",
            f"Status: {summary['status']}",
            f"Queens: {summary['queens']}",
            f"Nests: {summary['nests']}",
            f"Worker cells: {summary['worker_cells']}",
            f"Worker events: {summary['workers']}",
            f"Local records ready: {summary['ready_records']} / {summary['total_records']}",
        ]
        if selected:
            detail_lines.extend(["", f"Selected node: {selected['label']}", f"Type: {selected['kind']}", f"Source: {selected.get('local_link', 'unavailable')}"])
        else:
            detail_lines.extend(["", "Select a rendered node to inspect its true local source."])
        self.detail_box.setPlainText("\n".join(detail_lines))
        self.signal_box.setPlainText(
            "\n".join(
                [
                    f"Signal paths: {summary['signals']}",
                    f"Local trails: {summary['local_trails']}",
                    f"Signal markers in local snapshot: {summary['signal_count']}",
                    "No generated traffic, latency, bandwidth, or fake live feed is shown.",
                ]
            )
        )
        activity = [line for line in self.data_manager.activity_feed if self.selected_colony_id in line]
        if not activity:
            activity = ["No local activity records are tied to this colony yet."]
        self.activity_box.setPlainText("\n".join(activity[:8]))


class ColoniesTab(QWidget):
    def __init__(self, data_manager: DataManager) -> None:
        super().__init__()
        self.data_manager = data_manager
        self.search = QLineEdit()
        self.status_filter = QComboBox()
        self.table = QTableWidget()
        self.data_manager.data_updated.connect(self.refresh)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # ── header + controls ─────────────────────────────────────────────
        top = QHBoxLayout()
        top.setSpacing(8)
        top.addWidget(label("COLONIES", 12, 900, "#00ff88"))
        self.search.setPlaceholderText("Search colonies, queens, records…")
        self.search.textChanged.connect(self.refresh)
        top.addWidget(self.search, 2)
        self.status_filter.addItems(["All Statuses", "Visible", "Hidden"])
        self.status_filter.currentTextChanged.connect(self.refresh)
        top.addWidget(self.status_filter)
        layout.addLayout(top)

        # ── metric bar ────────────────────────────────────────────────────
        metrics = data_manager.metrics()
        self.metric_cards: dict[str, QFrame] = {}
        bar_host, self.metric_cards = mini_metric_row([
            ("TOTAL COLONIES", str(metrics["colonies"]), "#44aaff"),
            ("LOCAL QUEENS",   str(metrics["queens"]),   "#00ff88"),
            ("WORKER CELLS",   str(metrics["workers"]),  "#ffaa00"),
        ])
        layout.addWidget(bar_host)

        # ── table ─────────────────────────────────────────────────────────
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(
            ["Colony", "Queen", "Workers", "Health %", "Status", "Sector", "Signals", "Actions"]
        )
        configure_table(self.table)
        layout.addWidget(self.table, 1)
        self.refresh()

    def refresh(self) -> None:
        metrics = self.data_manager.metrics()
        for title, value in {
            "TOTAL COLONIES": str(metrics["colonies"]),
            "LOCAL QUEENS": str(metrics["queens"]),
            "WORKER CELLS": str(metrics["workers"]),
        }.items():
            card = self.metric_cards.get(title)
            if card is not None and hasattr(card, "value_label"):
                card.value_label.setText(value)  # type: ignore[attr-defined]
        query = self.search.text().strip().lower()
        status_filter = self.status_filter.currentText()
        rows = []
        for row in self.data_manager.colony_table_rows():
            haystack = " ".join(str(value) for value in row.values()).lower()
            if query and query not in haystack:
                continue
            if status_filter != "All Statuses" and row["status"] != status_filter:
                continue
            rows.append(row)
        self.table.setRowCount(len(rows))
        if not rows:
            set_empty_table_row(self.table, "No local colony records match the current filters.")
            return
        for row_index, row in enumerate(rows):
            values = [
                row["label"],
                row["assigned_queen"],
                row["worker_count"],
                row["health"],
                row["status"],
                row["sector"],
                row["signals"],
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setToolTip(f"{row['colony_id']} | nests {row['nests']} | health {row['health']}%")
                if col in {2, 3, 6}:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row_index, col, item)
            self.table.setCellWidget(
                row_index,
                7,
                action_pair(
                    "View",
                    "Edit",
                    lambda checked=False, colony_id=row["colony_id"]: self.data_manager.request_selection(colony_id),
                    lambda checked=False, colony_id=row["colony_id"]: self.data_manager.toggle_colony_active(colony_id),
                ),
            )


class QueensTab(QWidget):
    def __init__(self, data_manager: DataManager) -> None:
        super().__init__()
        self.data_manager = data_manager
        self.filter_box = QComboBox()
        self.card_host = QWidget()
        self.card_grid = QGridLayout(self.card_host)
        self.data_manager.data_updated.connect(self.refresh)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        records = self.data_manager.queen_records()
        ready = sum(1 for item in records if int(item["health"]) > 0)
        missing = max(0, len(records) - ready)

        # ── header ────────────────────────────────────────────────────────
        top = QHBoxLayout()
        top.setSpacing(8)
        top.addWidget(label("QUEENS", 12, 900, "#00ff88"))
        self.metric_cards: dict[str, QFrame] = {}
        bar_host, self.metric_cards = mini_metric_row([
            ("TOTAL",       str(len(records)), "#44aaff"),
            ("READY",       str(ready),        "#00ff88"),
            ("UNAVAILABLE", str(missing),      "#ffaa00"),
        ])
        top.addWidget(bar_host)
        top.addStretch(1)
        self.filter_box.addItems(["All Queens", "Local Artifact Ready", "Local Artifact Unavailable"])
        self.filter_box.currentTextChanged.connect(self.refresh)
        top.addWidget(self.filter_box)
        layout.addLayout(top)

        # ── queen card grid ───────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.card_grid.setContentsMargins(4, 4, 4, 4)
        self.card_grid.setSpacing(8)
        scroll.setWidget(self.card_host)
        layout.addWidget(scroll, 1)
        self.refresh()

    def refresh(self) -> None:
        clear_layout(self.card_grid)
        all_records = self.data_manager.queen_records()
        ready = sum(1 for item in all_records if int(item["health"]) > 0)
        missing = max(0, len(all_records) - ready)
        for title, value in {
            "TOTAL QUEENS": str(len(all_records)),
            "READY LINKS": str(ready),
            "UNAVAILABLE": str(missing),
        }.items():
            card = self.metric_cards.get(title)
            if card is not None and hasattr(card, "value_label"):
                card.value_label.setText(value)  # type: ignore[attr-defined]
        selected = self.filter_box.currentText()
        records = [
            item
            for item in all_records
            if selected == "All Queens"
            or (selected == "Local Artifact Ready" and int(item["health"]) > 0)
            or (selected == "Local Artifact Unavailable" and int(item["health"]) <= 0)
        ]
        if not records:
            message = "No local queen records match this filter." if all_records else "No local queen records exist yet."
            self.card_grid.addWidget(info_panel("QUEEN STORE EMPTY", message), 0, 0)
            self.card_grid.setColumnStretch(0, 1)
            self.card_grid.setRowStretch(1, 1)
            return
        for index, record in enumerate(records):
            self.card_grid.addWidget(self._queen_card(record), index // 4, index % 4)
        self.card_grid.setRowStretch(max(1, (len(records) + 3) // 4), 1)

    def _queen_card(self, record: dict[str, Any]) -> QFrame:
        ready = int(record["health"]) > 0
        accent = "#00ff88" if ready else "#ffaa00"
        card = QFrame()
        card.setObjectName("QueenCard")
        card.setStyleSheet(
            f"QFrame#QueenCard {{ background: #111111; border:1px solid #333333; border-radius:0px; }}"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(3)
        # Name + status pill in one row
        name_row = QHBoxLayout()
        name_row.setSpacing(6)
        name_row.addWidget(label(record["label"], 9, 700, accent), 1)
        name_row.addWidget(pill(record["status"], accent))
        layout.addLayout(name_row)
        # Key metrics inline
        for key, lbl in [("age", "Age"), ("health", "Health"), ("protocol", "Protocol")]:
            layout.addWidget(label(f"{lbl}: {record[key]}", 8, 400, "#666666"))
        # Readiness bar
        progress = QProgressBar()
        progress.setRange(0, 100)
        progress.setValue(int(record["readiness_progress"]))
        progress.setFormat("%p%")
        progress.setMaximumHeight(12)
        layout.addWidget(progress)
        return card


class ConnectionsGraphWidget(QFrame):
    def __init__(self, data_manager: DataManager) -> None:
        super().__init__()
        self.data_manager = data_manager
        self.show_inactive = True
        self.hover_node = ""
        self.setMouseTracking(True)
        self.setMinimumHeight(320)
        self.setStyleSheet(
            "QFrame { background: #0a0a0a; border:1px solid #333333; border-radius:0px; }"
        )

    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.fillRect(self.rect(), QColor(10, 10, 10))
        positions = self._positions()
        rows = self.data_manager.connection_records()[:18]
        for index, row in enumerate(rows):
            if not self.show_inactive and row["status"] not in {"LOCAL_RECORD_LINK", "READ_ONLY_SIGNAL"}:
                continue
            if not positions:
                continue
            source_key = row["source"] if row["source"] in positions else list(positions)[index % len(positions)]
            target_key = row["target"] if row["target"] in positions else list(positions)[(index * 3 + 2) % len(positions)]
            color = QColor(255, 170, 0, 140) if row["status"] == "LOCAL_RECORD_LINK" else QColor(68, 170, 255, 120)
            painter.setPen(QPen(color, 1))
            painter.drawLine(positions[source_key], positions[target_key])
        for name, point in positions.items():
            active = name == self.hover_node
            node_color = QColor(255, 170, 0, 220) if active else QColor(0, 255, 136, 180)
            painter.setBrush(QBrush(node_color))
            painter.setPen(QPen(QColor(51, 51, 51), 1))
            r = 5 if not active else 7
            painter.drawRect(point.x() - r, point.y() - r, r * 2, r * 2)
            painter.setPen(QColor(204, 204, 204))
            painter.setFont(QFont("Consolas", 7, QFont.Weight.Bold))
            painter.drawText(point.x() + r + 3, point.y() + 4, name)
        painter.end()

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        positions = self._positions()
        point = event.position().toPoint()
        self.hover_node = ""
        for name, node_point in positions.items():
            if math.hypot(point.x() - node_point.x(), point.y() - node_point.y()) < 26:
                self.hover_node = name
                related = next((row for row in self.data_manager.connection_records() if name in {row["source"], row["target"]}), None)
                if related:
                    self.setToolTip(f"{name}\nStatus: {related['status']}\nEvidence: {related['evidence']}\nSource: {related['source_path']}")
                else:
                    self.setToolTip(f"{name}\nLocal Hive view-model node")
                break
        self.update()

    def _positions(self) -> dict[str, QPoint]:
        w = max(1, self.width())
        h = max(1, self.height())
        world: dict[str, Point3] = {}
        core = self.data_manager.nodes.get(self.data_manager.communication_queen_id)
        if core:
            world[core.label] = core.position
        for colony in self.data_manager.colonies.values():
            queen = self.data_manager.primary_queen(colony.id)
            if queen:
                world[queen.label] = queen.position
            world[colony.label] = colony.center
        for node in self.data_manager.nodes.values():
            if node.kind == "remote_queen":
                world[node.label] = node.position
        if not world:
            return {}
        xs = [point[0] for point in world.values()]
        ys = [point[1] for point in world.values()]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        span_x = max(1.0, max_x - min_x)
        span_y = max(1.0, max_y - min_y)
        positions: dict[str, QPoint] = {}
        for name, point in world.items():
            x = int(40 + ((point[0] - min_x) / span_x) * max(1, w - 80))
            y = int(36 + ((point[1] - min_y) / span_y) * max(1, h - 72))
            positions[name] = QPoint(x, y)
        return positions


class ConnectionsTab(QWidget):
    def __init__(self, data_manager: DataManager) -> None:
        super().__init__()
        self.data_manager = data_manager
        self.graph = ConnectionsGraphWidget(data_manager)
        self.table = QTableWidget()
        self.active_only = QCheckBox("Active connections only")
        self.data_manager.data_updated.connect(self.refresh)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        metrics = data_manager.metrics()

        # ── header bar ────────────────────────────────────────────────────
        top = QHBoxLayout()
        top.setSpacing(8)
        top.addWidget(label("CONNECTIONS", 12, 900, "#00ff88"))
        _bar, _cards = mini_metric_row([
            ("LINKS",   str(metrics["inter"]),         "#44aaff"),
            ("SIGNALS", str(metrics["signals"]),       "#44aaff"),
            ("REMOTE",  str(metrics["remote_queens"]), "#ffaa00"),
        ])
        top.addWidget(_bar)
        top.addStretch(1)
        self.active_only.toggled.connect(self._toggle_active)
        top.addWidget(self.active_only)
        snap = button_stub("Refresh")
        snap.setToolTip("Reloads the true local Hive snapshot.")
        snap.clicked.connect(self.data_manager.refresh_local_view)
        top.addWidget(snap)
        layout.addLayout(top)

        # ── graph + table splitter ────────────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.graph)
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            ["Route", "From", "To", "Type", "Status", "Evidence", "Source"]
        )
        configure_table(self.table)
        splitter.addWidget(self.table)
        splitter.setSizes([620, 580])
        layout.addWidget(splitter, 1)
        self.refresh()

    def _toggle_active(self, checked: bool) -> None:
        self.graph.show_inactive = not checked
        self.graph.update()
        self.refresh()

    def refresh(self) -> None:
        rows = [row for row in self.data_manager.connection_records() if not self.active_only.isChecked() or row["status"] in {"LOCAL_RECORD_LINK", "READ_ONLY_SIGNAL"}]
        self.table.setRowCount(len(rows))
        if not rows:
            set_empty_table_row(self.table, "No true local connection records match the current filter.")
            self.graph.update()
            return
        for row_index, row in enumerate(rows):
            for col, key in enumerate(["id", "source", "target", "type", "status", "evidence", "source_path"]):
                item = QTableWidgetItem(str(row[key]))
                if key == "status":
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row_index, col, item)


class CommunicationTab(QWidget):
    def __init__(self, data_manager: DataManager) -> None:
        super().__init__()
        self.data_manager = data_manager
        self.section_tabs = QTabWidget()
        self.message_table = QTableWidget()
        self.alert_table = QTableWidget()
        self.command_table = QTableWidget()
        self.status_details = QTextEdit()
        self.signal_details = QTextEdit()
        self.data_manager.data_updated.connect(self.refresh)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # ── compact header bar ────────────────────────────────────────────
        top = QHBoxLayout()
        top.setSpacing(8)
        top.addWidget(label("COMM QUEEN", 12, 900, "#00ff88"))
        self.metric_cards: dict[str, QFrame] = {}
        bar_items = [(t, v, c) for t, v, _, c in self._metric_items()]
        bar_host, self.metric_cards = mini_metric_row(bar_items)
        top.addWidget(bar_host)
        top.addStretch(1)
        top.addWidget(pill("GUARDIAN", "#00ff88"))
        top.addWidget(pill("LOCAL", "#44aaff"))
        sync = QPushButton("Sync ↻")
        sync.setToolTip("Reloads true local Hive snapshot.")
        sync.clicked.connect(self.data_manager.refresh_local_view)
        top.addWidget(sync)
        layout.addLayout(top)

        # ── section tabs ──────────────────────────────────────────────────
        self.section_tabs.addTab(self._build_overview_page(), "Overview")
        self.section_tabs.addTab(self._build_signals_page(), "Signals")
        self.section_tabs.addTab(self._table_page(self.message_table, "MESSAGES"), "Messages")
        self.section_tabs.addTab(self._table_page(self.command_table, "COMMANDS"), "Commands")
        self.section_tabs.addTab(self._table_page(self.alert_table, "ALERTS"), "Alerts")
        self.section_tabs.tabBar().setUsesScrollButtons(True)
        self.section_tabs.tabBar().setElideMode(Qt.TextElideMode.ElideRight)
        layout.addWidget(self.section_tabs, 1)

        # ── status + signal bottom strip ──────────────────────────────────
        lower = QSplitter(Qt.Orientation.Horizontal)
        lower.setMaximumHeight(180)
        self.status_details.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.signal_details.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        lower.addWidget(detail_panel("QUEEN STATUS", self.status_details))
        lower.addWidget(detail_panel("SIGNAL ANALYZER", self.signal_details))
        lower.setSizes([620, 580])
        layout.addWidget(lower)
        self.refresh()

    def _metric_items(self) -> list[tuple[str, str, str, str]]:
        metrics = self.data_manager.metrics()
        messages = self.data_manager.message_records()
        alerts = sum(1 for item in messages if item["channel"] == "Alerts" or item["status"] == "Warning")
        commands = sum(1 for item in messages if item["channel"] == "Commands")
        return [
            ("COMM QUEEN", str(metrics["communication_nodes"]), "Local contract node", "#44aaff"),
            ("SIGNAL LINKS", str(metrics["signals"]), "True local trails", "#44aaff"),
            ("MESSAGES", str(len(messages)), "Local status feed", "#cccccc"),
            ("COMMANDS", str(commands), "No runtime queue", "#ffaa00"),
            ("ALERTS", str(alerts), "Local warnings", "#ff4444"),
            ("REMOTE QUEENS", str(metrics["remote_queens"]), "Registered devices", "#00ff88"),
        ]

    def _build_overview_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Signal map panel
        map_panel = QFrame()
        map_panel.setObjectName("Panel")
        ml = QVBoxLayout(map_panel)
        ml.setContentsMargins(8, 8, 8, 8)
        ml.setSpacing(4)
        ml.addWidget(label("SIGNAL MAP", 9, 700, "#44aaff"))
        ml.addWidget(ConnectionsGraphWidget(self.data_manager), 1)
        splitter.addWidget(map_panel)

        # Status dock
        dock = QFrame()
        dock.setObjectName("CardPanel")
        dock.setMaximumWidth(280)
        dl = QVBoxLayout(dock)
        dl.setContentsMargins(10, 10, 10, 10)
        dl.setSpacing(6)
        dl.addWidget(center_label("ENGEL", 12, 900, "#00ff88"))
        dl.addWidget(center_label(self.data_manager.local_status_label(), 8, 700, "#666666"))
        status_box = QTextEdit()
        status_box.setReadOnly(True)
        status_box.setStyleSheet(text_box_style())
        status_box.setPlainText(self.data_manager.section_detail("communication_queen"))
        dl.addWidget(status_box, 1)
        dl.addWidget(self._communication_actions())
        splitter.addWidget(dock)
        splitter.setSizes([860, 280])
        layout.addWidget(splitter, 1)
        return page

    def _build_signals_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        table = QTableWidget()
        table.setColumnCount(7)
        table.setHorizontalHeaderLabels(["Route", "From", "To", "Type", "Status", "Evidence", "Source"])
        configure_table(table)
        self.signal_table = table
        layout.addWidget(table, 1)
        return page

    def _table_page(self, table: QTableWidget, title: str) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)
        layout.addWidget(label(title, 9, 700, "#44aaff"))
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["Time", "Channel", "Message", "Status"])
        configure_table(table)
        layout.addWidget(table, 1)
        return page

    def _communication_actions(self) -> QWidget:
        host = QFrame()
        host.setObjectName("Panel")
        layout = QHBoxLayout(host)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)
        analyze = QPushButton("Analyze ↗")
        analyze.setToolTip("Go to Signal Analyzer")
        analyze.clicked.connect(self._focus_signal_tab)
        layout.addWidget(analyze)
        return host

    def _focus_signal_tab(self) -> None:
        index = self.section_tabs.indexOf(self.findChild(QWidget, "Signals"))
        self.section_tabs.setCurrentIndex(1 if index < 0 else index)
        self.data_manager.focus_section("signal_analyzer")

    def refresh(self) -> None:
        messages = self.data_manager.message_records()
        for title, value, _detail, _color in self._metric_items():
            card = self.metric_cards.get(title)
            if card is not None and hasattr(card, "value_label"):
                card.value_label.setText(value)  # type: ignore[attr-defined]
        self._fill_message_table(self.message_table, messages)
        self._fill_message_table(self.alert_table, [item for item in messages if item["channel"] == "Alerts" or item["status"] == "Warning"])
        self._fill_message_table(self.command_table, [item for item in messages if item["channel"] == "Commands"])
        if hasattr(self, "signal_table"):
            rows = self.data_manager.connection_records()
            self.signal_table.setRowCount(len(rows))
            if not rows:
                set_empty_table_row(self.signal_table, "No true local signal route records are available.")
            else:
                self.signal_table.setSortingEnabled(False)
                self.signal_table.setRowCount(len(rows))
                for row_index, row in enumerate(rows):
                    for col, key in enumerate(["id", "source", "target", "type", "status", "evidence", "source_path"]):
                        item = QTableWidgetItem(str(row[key]))
                        if key == "status":
                            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                        self.signal_table.setItem(row_index, col, item)
                self.signal_table.setSortingEnabled(True)
        self.status_details.setPlainText(self.data_manager.section_detail("communication_queen"))
        self.signal_details.setPlainText(self.data_manager.signal_analyzer_text())

    def _fill_message_table(self, table: QTableWidget, rows: list[dict[str, str]]) -> None:
        if not rows:
            set_empty_table_row(table, "No local communication records are available for this section.")
            return
        table.setSortingEnabled(False)
        table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for col, key in enumerate(["time", "channel", "message", "status"]):
                item = QTableWidgetItem(row.get(key, ""))
                if key == "status":
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row_index, col, item)
        table.setSortingEnabled(True)


class GrowthChartWidget(QFrame):
    def __init__(self, data_manager: DataManager) -> None:
        super().__init__()
        self.data_manager = data_manager
        self.setMinimumHeight(200)
        self.setStyleSheet(
            "QFrame { background: #0a0a0a; border:1px solid #333333; border-radius:0px; }"
        )

    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        rect = self.rect().adjusted(28, 20, -12, -20)
        # Grid lines
        painter.setPen(QPen(QColor(34, 34, 34), 1))
        for index in range(5):
            y = rect.top() + index * rect.height() // 4
            painter.drawLine(rect.left(), y, rect.right(), y)
        rows = list(self.data_manager.growth_paths.values())
        if rows:
            bar_width = max(10, rect.width() // max(1, len(rows)) - 4)
            for index, item in enumerate(rows):
                progress = max(0.0, min(1.0, item.progress))
                x = rect.left() + index * rect.width() // max(1, len(rows))
                h = int(rect.height() * progress)
                color = QColor(0, 255, 136, 180) if progress > 0.5 else QColor(255, 170, 0, 160)
                painter.fillRect(x, rect.bottom() - h, bar_width, h, color)
        else:
            painter.setPen(QColor(102, 102, 102))
            painter.setFont(QFont("Consolas", 8, QFont.Weight.Normal))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "no active growth paths")
        # Title
        painter.setPen(QColor(102, 102, 102))
        painter.setFont(QFont("Consolas", 7, QFont.Weight.Bold))
        painter.drawText(8, 14, "GROWTH PATHS")
        painter.end()


class ExpansionTab(QWidget):
    def __init__(self, data_manager: DataManager) -> None:
        super().__init__()
        self.data_manager = data_manager
        self.queue_table = QTableWidget()
        self.data_manager.data_updated.connect(self.refresh)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        metrics = data_manager.metrics()

        # ── header bar ────────────────────────────────────────────────────
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)
        top_bar.addWidget(label("EXPANSION", 12, 900, "#00ff88"))
        self.metric_cards: dict[str, QFrame] = {}
        bar_host, self.metric_cards = mini_metric_row([
            ("GROWTH PATHS",    str(metrics["growth_paths"]),    "#44aaff"),
            ("REMOTE REGISTRY", str(metrics["remote_queens"]),   "#ffaa00"),
            ("TELEMETRY",       str(metrics["telemetry_events"]), "#00ff88"),
        ])
        top_bar.addWidget(bar_host)
        top_bar.addStretch(1)
        layout.addLayout(top_bar)

        # ── chart + queue table ───────────────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(GrowthChartWidget(data_manager))
        self.queue_table.setColumnCount(5)
        self.queue_table.setHorizontalHeaderLabels(["ID", "Source", "Target", "Evidence", "Status"])
        configure_table(self.queue_table)
        splitter.addWidget(self.queue_table)
        splitter.setSizes([560, 640])
        layout.addWidget(splitter, 1)
        self.refresh()

    def refresh(self) -> None:
        metrics = self.data_manager.metrics()
        for title, value in {
            "GROWTH PATHS": str(metrics["growth_paths"]),
            "REMOTE REGISTRY": str(metrics["remote_queens"]),
            "TELEMETRY EVENTS": str(metrics["telemetry_events"]),
        }.items():
            card = self.metric_cards.get(title)
            if card is not None and hasattr(card, "value_label"):
                card.value_label.setText(value)  # type: ignore[attr-defined]
        self.findChild(GrowthChartWidget).update() if self.findChild(GrowthChartWidget) else None
        rows = self.data_manager.expansion_rows()
        self.queue_table.setRowCount(len(rows))
        if not rows:
            set_empty_table_row(self.queue_table, "0 active growth paths. True local growth-path store is empty.")
            return
        for row_index, row in enumerate(rows):
            for col, key in enumerate(["id", "source", "target", "evidence", "status"]):
                self.queue_table.setItem(row_index, col, QTableWidgetItem(row[key]))


class PermissionUserDialog(QDialog):
    def __init__(self, parent: QWidget, existing_ids: list[str], current: PermissionUserRecord | None = None) -> None:
        super().__init__(parent)
        self.existing_ids = set(existing_ids)
        self.current = current
        self.setWindowTitle("Add User / Agent" if current is None else "Edit User / Agent")
        self.setMinimumWidth(430)
        self.setStyleSheet(global_stylesheet())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        layout.addWidget(label("SESSION-LOCAL PERMISSION RECORD", 11, 900, "#44aaff"))
        layout.addWidget(label("Records created here are GUI/session state only. They do not grant runtime authority.", 9, 400, "#666666"))

        form = QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        self.id_input = QLineEdit()
        self.id_input.setPlaceholderText("User/Agent ID")
        self.role_box = QComboBox()
        self.role_box.addItems(["Admin", "Moderator", "Operator", "Viewer"])
        self.access_box = QComboBox()
        self.access_box.addItems(["Full", "Limited", "Read-Only"])
        self.colonies_input = QLineEdit()
        self.colonies_input.setPlaceholderText("Comma-separated assigned colonies")
        form.addWidget(label("ID", 9, 800, "#eaf5ff"), 0, 0)
        form.addWidget(self.id_input, 0, 1)
        form.addWidget(label("Role", 9, 800, "#eaf5ff"), 1, 0)
        form.addWidget(self.role_box, 1, 1)
        form.addWidget(label("Access Level", 9, 800, "#eaf5ff"), 2, 0)
        form.addWidget(self.access_box, 2, 1)
        form.addWidget(label("Assigned Colonies", 9, 800, "#eaf5ff"), 3, 0)
        form.addWidget(self.colonies_input, 3, 1)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if current is not None:
            self.id_input.setText(current.id)
            self.role_box.setCurrentText(current.role)
            self.access_box.setCurrentText(current.access_level)
            self.colonies_input.setText(", ".join(current.assigned_colonies))

    def _accept_if_valid(self) -> None:
        user_id = " ".join(self.id_input.text().strip().split())
        original_id = self.current.id if self.current else ""
        if not user_id:
            QMessageBox.warning(self, "Validation", "User/Agent ID is required.")
            return
        if user_id in self.existing_ids and user_id != original_id:
            QMessageBox.warning(self, "Validation", "User/Agent ID must be unique.")
            return
        self.accept()

    def record(self) -> PermissionUserRecord:
        colonies = [item.strip() for item in self.colonies_input.text().split(",") if item.strip()]
        activity = list(self.current.activity_log) if self.current else []
        if self.current is not None:
            activity.insert(0, time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()) + " - Session-local permission record edited.")
        return PermissionUserRecord(
            id=" ".join(self.id_input.text().strip().split()),
            role=self.role_box.currentText(),
            access_level=self.access_box.currentText(),
            assigned_colonies=colonies,
            status=self.current.status if self.current else "Pending",
            activity_log=activity,
        )


class PermissionsTab(QWidget):
    ROLE_COLORS = {
        "Admin": "#ffaa00",
        "Moderator": "#44aaff",
        "Operator": "#00ff88",
        "Viewer": "#44aaff",
    }
    STATUS_COLORS = {
        "Active": "#00ff88",
        "Pending": "#ffaa00",
        "Revoked": "#ff4444",
    }
    ROLE_HELP = {
        "Admin": "Session-local admin view. Does not grant real runtime authority.",
        "Moderator": "Session-local review and moderation role.",
        "Operator": "Session-local operator role for assigned colonies.",
        "Viewer": "Session-local read-only role.",
    }

    def __init__(self, data_manager: DataManager) -> None:
        super().__init__()
        self.data_manager = data_manager
        self.search = QLineEdit()
        self.role_filter = QComboBox()
        self.access_filter = QComboBox()
        self.colony_filter = QComboBox()
        self.matrix = QTableWidget()
        self.detail_toggle = QToolButton()
        self.detail_body = QFrame()
        self.activity_log = QTextEdit()
        self.colony_details = QTextEdit()
        self.module_details = QTextEdit()
        self.edit_role = QComboBox()
        self.edit_access = QComboBox()
        self.footer_status = QLabel()
        self.metric_cards: dict[str, QFrame] = {}
        self.filtered_users: list[PermissionUserRecord] = []
        self.selected_user_id = ""
        self._refreshing = False
        self.data_manager.data_updated.connect(self.refresh)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # ── compact header + filters in one bar ───────────────────────────
        layout.addWidget(self._build_header())
        layout.addWidget(self._build_metrics())

        # ── user table ────────────────────────────────────────────────────
        layout.addWidget(self._build_user_table(), 1)

        # ── detail + edit bottom panel ────────────────────────────────────
        layout.addWidget(self._build_detail_panel())
        layout.addWidget(self._build_footer())
        self.refresh()

    def _build_header(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("Panel")
        row = QHBoxLayout(frame)
        row.setContentsMargins(8, 6, 8, 6)
        row.setSpacing(8)
        row.addWidget(label("PERMISSIONS", 12, 900, "#00ff88"))
        # search + filters inline
        self.search.setPlaceholderText("Search ID…")
        self.search.setMaximumWidth(180)
        self.search.textChanged.connect(self.refresh)
        row.addWidget(self.search)
        self.role_filter.addItems(["All Roles", "Admin", "Moderator", "Operator", "Viewer"])
        self.role_filter.currentTextChanged.connect(self.refresh)
        row.addWidget(self.role_filter)
        self.access_filter.addItems(["All Access", "Full", "Limited", "Read-Only"])
        self.access_filter.currentTextChanged.connect(self.refresh)
        row.addWidget(self.access_filter)
        self.colony_filter.addItems(["All Colonies"])
        self.colony_filter.currentTextChanged.connect(self.refresh)
        row.addWidget(self.colony_filter)
        row.addStretch(1)
        # action buttons
        for text, callback, tip in [
            ("Add", self._add_user, "Add a session-local record."),
            ("Enable", lambda: self._bulk_status("Active"), "Bulk enable."),
            ("Disable", lambda: self._bulk_status("Pending"), "Bulk disable."),
            ("Assign Colony", self._bulk_assign_colony, "Bulk assign colony."),
            ("Revoke", lambda: self._bulk_status("Revoked"), "Bulk revoke."),
        ]:
            b = QPushButton(text)
            b.setToolTip(tip)
            b.clicked.connect(callback)
            row.addWidget(b)
        row.addWidget(pill("GUARDIAN", "#00ff88"))
        return frame

    def _build_metrics(self) -> QWidget:
        host, cards = mini_metric_row([
            ("TOTAL",    "0", "#44aaff"),
            ("ACTIVE",   "0", "#00ff88"),
            ("ADMINS",   "0", "#ffaa00"),
            ("MODS",     "0", "#44aaff"),
            ("STANDARD", "0", "#00ff88"),
            ("PENDING",  "0", "#ffaa00"),
        ])
        key_map = {
            "TOTAL":    "TOTAL USERS/AGENTS",
            "ACTIVE":   "ACTIVE SESSIONS",
            "ADMINS":   "ADMINS",
            "MODS":     "MODERATORS",
            "STANDARD": "STANDARD USERS",
            "PENDING":  "PENDING INVITES",
        }
        self.metric_cards = {key_map[k]: v for k, v in cards.items()}
        return host

    def _build_filters(self) -> QFrame:
        # Filters are now inlined into _build_header
        return QFrame()

    def _build_actions_panel(self) -> QFrame:
        # Actions are now inlined into _build_header
        return QFrame()

    def _build_user_table(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("CardPanel")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)
        layout.addWidget(label("USER / AGENT ACCESS GRID", 9, 700, "#44aaff"))
        self.matrix.setColumnCount(7)
        self.matrix.setHorizontalHeaderLabels(
            ["ID", "Role", "Access", "Colonies", "Last Active", "Status", "Actions"]
        )
        configure_table(self.matrix)
        self.matrix.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.matrix.itemSelectionChanged.connect(self._on_selection_changed)
        self.matrix.cellClicked.connect(self._on_cell_clicked)
        layout.addWidget(self.matrix, 1)
        return frame

    def _build_detail_panel(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("Panel")
        frame.setMaximumHeight(200)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)
        self.detail_toggle.setText("▾ SELECTED USER")
        self.detail_toggle.setCheckable(True)
        self.detail_toggle.setChecked(True)
        self.detail_toggle.clicked.connect(lambda checked: self.detail_body.setVisible(bool(checked)))
        layout.addWidget(self.detail_toggle)

        body_layout = QGridLayout(self.detail_body)
        body_layout.setHorizontalSpacing(6)
        body_layout.setVerticalSpacing(6)
        body_layout.setContentsMargins(0, 0, 0, 0)
        for box in [self.activity_log, self.colony_details, self.module_details]:
            box.setReadOnly(True)
            box.setStyleSheet(text_box_style())
        body_layout.addWidget(detail_panel("ACTIVITY", self.activity_log), 0, 0)
        body_layout.addWidget(detail_panel("COLONY ACCESS", self.colony_details), 0, 1)
        body_layout.addWidget(detail_panel("MODULES", self.module_details), 0, 2)
        body_layout.addWidget(self._build_inline_edit_panel(), 0, 3)
        layout.addWidget(self.detail_body)
        return frame

    def _build_inline_edit_panel(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("Panel")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(5)
        layout.addWidget(label("EDIT", 9, 700, "#44aaff"))
        self.edit_role.addItems(["Admin", "Moderator", "Operator", "Viewer"])
        self.edit_access.addItems(["Full", "Limited", "Read-Only"])
        rl = QHBoxLayout()
        rl.addWidget(label("Role", 8, 600, "#666666"))
        rl.addWidget(self.edit_role, 1)
        al = QHBoxLayout()
        al.addWidget(label("Access", 8, 600, "#666666"))
        al.addWidget(self.edit_access, 1)
        layout.addLayout(rl)
        layout.addLayout(al)
        save = QPushButton("Save")
        save.clicked.connect(self._save_detail_edit)
        layout.addWidget(save)
        layout.addWidget(label("Session-local only.", 7, 400, "#666666"))
        return frame

    def _build_footer(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("Footer")
        frame.setMaximumHeight(38)
        row = QHBoxLayout(frame)
        row.setContentsMargins(10, 4, 10, 4)
        self.footer_status.setStyleSheet("color:#666666; font-weight:700; font-size:8pt; font-family:Consolas,monospace;")
        row.addWidget(self.footer_status, 1)
        sync = QPushButton("Sync")
        sync.setToolTip("Refreshes local GUI view only.")
        sync.clicked.connect(self._sync_permissions)
        row.addWidget(sync)
        return frame

    def _filtered_users(self) -> list[PermissionUserRecord]:
        query = self.search.text().strip().lower()
        role = self.role_filter.currentText()
        access = self.access_filter.currentText()
        colony = self.colony_filter.currentText()
        rows: list[PermissionUserRecord] = []
        for user in self.data_manager.permission_user_records():
            if query and query not in user.id.lower():
                continue
            if role != "All Roles" and user.role != role:
                continue
            if access != "All Access" and user.access_level != access:
                continue
            if colony != "All Colonies" and colony not in user.assigned_colonies:
                continue
            rows.append(user)
        return rows

    def refresh(self) -> None:
        if self._refreshing:
            return
        self._refreshing = True
        try:
            current_colony = self.colony_filter.currentText()
            colonies = self.data_manager.permission_user_colonies()
            self.colony_filter.blockSignals(True)
            self.colony_filter.clear()
            self.colony_filter.addItem("All Colonies")
            self.colony_filter.addItems(colonies)
            index = self.colony_filter.findText(current_colony)
            self.colony_filter.setCurrentIndex(index if index >= 0 else 0)
            self.colony_filter.blockSignals(False)

            self.filtered_users = self._filtered_users()
            self._refresh_metrics()
            self._populate_table()
            self._refresh_details()
            self._refresh_footer()
        finally:
            self._refreshing = False

    def _refresh_metrics(self) -> None:
        users = self.data_manager.permission_user_records()
        active = sum(1 for item in users if item.status == "Active")
        admins = sum(1 for item in users if item.role == "Admin")
        moderators = sum(1 for item in users if item.role == "Moderator")
        standard = sum(1 for item in users if item.role in {"Operator", "Viewer"})
        pending = sum(1 for item in users if item.status == "Pending")
        values = {
            "TOTAL USERS/AGENTS": str(len(users)),
            "ACTIVE SESSIONS": str(active),
            "ADMINS": str(admins),
            "MODERATORS": str(moderators),
            "STANDARD USERS": str(standard),
            "PENDING INVITES": str(pending),
        }
        for title, value in values.items():
            card = self.metric_cards.get(title)
            if card is not None and hasattr(card, "value_label"):
                card.value_label.setText(value)  # type: ignore[attr-defined]

    def _populate_table(self) -> None:
        self.matrix.setSortingEnabled(False)
        self.matrix.setRowCount(len(self.filtered_users))
        if not self.filtered_users:
            total = len(self.data_manager.permission_user_records())
            message = (
                "No session-local user/agent records added yet."
                if total == 0
                else "No session-local user/agent records match the current filters."
            )
            set_empty_table_row(self.matrix, message)
            return
        for row_index, user in enumerate(self.filtered_users):
            self._set_item(row_index, 0, user.id, "#44aaff", user.status, user.id)
            self.matrix.setCellWidget(row_index, 1, self._combo_for(user, "role", ["Admin", "Moderator", "Operator", "Viewer"], user.role))
            self._set_item(row_index, 1, user.role, self.ROLE_COLORS.get(user.role, "#eaf5ff"), user.status, user.id, self.ROLE_HELP.get(user.role, "Local role"))
            self.matrix.setCellWidget(row_index, 2, self._combo_for(user, "access_level", ["Full", "Limited", "Read-Only"], user.access_level))
            self._set_item(row_index, 2, user.access_level, self._access_color(user.access_level), user.status, user.id)
            colonies = ", ".join(user.assigned_colonies) if user.assigned_colonies else "0 assigned"
            self._set_item(row_index, 3, colonies, "#eaf5ff", user.status, user.id, colonies)
            self._set_item(row_index, 4, user.last_activity, "#666666", user.status, user.id)
            self._set_item(row_index, 5, user.status, self.STATUS_COLORS.get(user.status, "#eaf5ff"), user.status, user.id)
            self.matrix.setCellWidget(row_index, 6, self._row_actions(user.id))
        self.matrix.setSortingEnabled(True)

    def _set_item(self, row: int, column: int, text: str, color: str, status: str, user_id: str, tooltip: str = "") -> None:
        item = QTableWidgetItem(text)
        item.setData(Qt.ItemDataRole.UserRole, user_id)
        item.setForeground(QBrush(QColor(color)))
        item.setBackground(QBrush(QColor(self._status_background(status))))
        item.setToolTip(tooltip or text)
        if column in {1, 2, 5}:
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if column == 0:
            font = item.font()
            font.setUnderline(True)
            font.setBold(True)
            item.setFont(font)
        self.matrix.setItem(row, column, item)

    def _combo_for(self, user: PermissionUserRecord, field_name: str, values: list[str], selected: str) -> QComboBox:
        combo = QComboBox()
        combo.addItems(values)
        combo.setCurrentText(selected)
        combo.setToolTip("Inline session-local edit. Does not grant runtime authority.")
        combo.currentTextChanged.connect(lambda value, user_id=user.id, field=field_name: self._inline_edit(user_id, field, value))
        return combo

    def _row_actions(self, user_id: str) -> QWidget:
        host = QWidget()
        layout = QHBoxLayout(host)
        layout.setContentsMargins(4, 2, 4, 2)
        edit = QPushButton("Edit")
        edit.clicked.connect(lambda: self._edit_user(user_id))
        remove = QPushButton("Remove")
        remove.setToolTip("Removes only the session-local GUI record.")
        remove.clicked.connect(lambda: self._remove_user(user_id))
        layout.addWidget(edit)
        layout.addWidget(remove)
        return host

    def _inline_edit(self, user_id: str, field_name: str, value: str) -> None:
        if self._refreshing:
            return
        self.data_manager.update_permission_user_field(user_id, field_name, value)

    def _selected_ids(self) -> list[str]:
        ids: list[str] = []
        for item in self.matrix.selectedItems():
            user_id = str(item.data(Qt.ItemDataRole.UserRole) or "")
            if user_id and user_id not in ids:
                ids.append(user_id)
        return ids

    def _on_cell_clicked(self, row: int, _column: int) -> None:
        item = self.matrix.item(row, 0)
        if item is not None:
            self.selected_user_id = str(item.data(Qt.ItemDataRole.UserRole) or "")
            self._refresh_details()

    def _on_selection_changed(self) -> None:
        ids = self._selected_ids()
        if ids:
            self.selected_user_id = ids[0]
            self._refresh_details()

    def _add_user(self) -> None:
        dialog = PermissionUserDialog(self, list(self.data_manager.permission_user_store))
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            record = dialog.record()
            self.data_manager.upsert_permission_user(record)
            self.selected_user_id = record.id
            self.refresh()
        except ValueError as exc:
            QMessageBox.warning(self, "Add User/Agent", str(exc))

    def _edit_user(self, user_id: str) -> None:
        current = self.data_manager.permission_user_store.get(user_id)
        if current is None:
            return
        dialog = PermissionUserDialog(self, list(self.data_manager.permission_user_store), current)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            record = dialog.record()
            self.data_manager.upsert_permission_user(record, original_id=user_id)
            self.selected_user_id = record.id
            self.refresh()
        except ValueError as exc:
            QMessageBox.warning(self, "Edit User/Agent", str(exc))

    def _remove_user(self, user_id: str) -> None:
        answer = QMessageBox.question(self, "Remove User/Agent", f"Remove session-local permission record '{user_id}'?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.data_manager.remove_permission_user(user_id)
        if self.selected_user_id == user_id:
            self.selected_user_id = ""
        self.refresh()

    def _bulk_status(self, status: str) -> None:
        ids = self._selected_ids()
        if not ids:
            QMessageBox.information(self, "Bulk Action", "Select one or more session-local rows first.")
            return
        self.data_manager.set_permission_user_status(ids, status)

    def _bulk_assign_colony(self) -> None:
        ids = self._selected_ids()
        if not ids:
            QMessageBox.information(self, "Bulk Assign Colony", "Select one or more session-local rows first.")
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Bulk Assign Colony")
        dialog.setStyleSheet(global_stylesheet())
        layout = QVBoxLayout(dialog)
        layout.addWidget(label("Enter comma-separated colony IDs.", 10, 800, "#eaf5ff"))
        entry = QLineEdit()
        entry.setPlaceholderText("colony-alpha, colony-beta")
        layout.addWidget(entry)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        colonies = [item.strip() for item in entry.text().split(",") if item.strip()]
        self.data_manager.assign_permission_user_colonies(ids, colonies)

    def _save_detail_edit(self) -> None:
        user_id = self.selected_user_id
        if not user_id:
            QMessageBox.information(self, "Edit Permissions", "Select a session-local user/agent first.")
            return
        self.data_manager.update_permission_user_field(user_id, "role", self.edit_role.currentText())
        self.data_manager.update_permission_user_field(user_id, "access_level", self.edit_access.currentText())

    def _sync_permissions(self) -> None:
        self.refresh()
        QMessageBox.information(
            self,
            "Sync Permissions",
            "Session-local permission view refreshed. No route, queue, trusted-memory, provider, network, or runtime permission change was applied.",
        )

    def _refresh_details(self) -> None:
        user = self.data_manager.permission_user_store.get(self.selected_user_id)
        if user is None:
            self.activity_log.setPlainText("No selected user/agent.\nThe session-local permission store is empty until a record is added.")
            self.colony_details.setPlainText("No colony-specific access records selected.")
            self.module_details.setPlainText("No module role access details available.")
            return
        self.edit_role.setCurrentText(user.role)
        self.edit_access.setCurrentText(user.access_level)
        self.activity_log.setPlainText("\n".join(user.activity_log) if user.activity_log else "No session-local activity events yet.")
        self.colony_details.setPlainText(
            "\n".join(
                [
                    f"User/Agent ID: {user.id}",
                    f"Status: {user.status}",
                    f"Assigned colonies: {len(user.assigned_colonies)}",
                    "",
                    "\n".join(f"- {colony}: {user.access_level}" for colony in user.assigned_colonies) if user.assigned_colonies else "No assigned colonies.",
                ]
            )
        )
        self.module_details.setPlainText(self._module_access_text(user))

    def _module_access_text(self, user: PermissionUserRecord) -> str:
        modules = ["Hive Map", "Connections", "Communication", "Expansion"]
        lines = [
            f"Role: {user.role}",
            f"Access level: {user.access_level}",
            "Derived for display from the session-local record only.",
            "",
        ]
        for module in modules:
            lines.append(f"{module}: {self._module_permission(user, module)}")
        return "\n".join(lines)

    def _module_permission(self, user: PermissionUserRecord, module: str) -> str:
        if user.status == "Revoked":
            return "None"
        if user.access_level == "Read-Only":
            return "View"
        if user.role == "Admin" and user.access_level == "Full":
            return "Full"
        if user.role == "Moderator":
            return "Limited" if module in {"Communication", "Expansion"} else "View"
        if user.role == "Operator":
            return "Limited" if module in {"Hive Map", "Connections"} else "View"
        return "View"

    def _refresh_footer(self) -> None:
        users = self.data_manager.permission_user_records()
        active = sum(1 for item in users if item.status == "Active")
        pending = sum(1 for item in users if item.status == "Pending")
        self.footer_status.setText(
            f"Total users loaded: {len(users)}    Active sessions: {active}    Pending approvals: {pending}    Session-local GUI store"
        )

    def _access_color(self, access: str) -> str:
        return {"Full": "#00ff88", "Limited": "#ffaa00", "Read-Only": "#44aaff"}.get(access, "#cccccc")

    def _status_background(self, status: str) -> str:
        return {
            "Active":  "#0a1a0a",
            "Pending": "#1a1a0a",
            "Revoked": "#1a0a0a",
        }.get(status, "#0a0a0a")


class ENGELPanel(QFrame):
    def __init__(self, data_manager: DataManager) -> None:
        super().__init__()
        self.data_manager = data_manager
        self.setObjectName("ENGELPanel")
        self.setMinimumWidth(340)
        self.setStyleSheet(
            "QFrame#ENGELPanel {"
            "  background: #0a0a0a;"
            "  border: 1px solid #333333;"
            "  border-radius: 0px;"
            "}"
            "QPushButton {"
            "  background: #111111;"
            "  border: 1px solid #333333;"
            "  border-radius: 0px;"
            "  color: #44aaff;"
            "  padding: 3px 7px;"
            "  font-weight: 700;"
            "  font-size: 8.5pt;"
            "  font-family: Consolas, monospace;"
            "}"
            "QPushButton:hover { border-color: #00ff88; color:#ffffff; }"
            "QLineEdit {"
            "  background: #111111;"
            "  border: 1px solid #333333;"
            "  border-radius: 0px;"
            "  color: #cccccc;"
            "  padding: 3px 6px;"
            "  font-size: 9pt;"
            "  font-family: Consolas, monospace;"
            "}"
        )
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # ── identity block ────────────────────────────────────────────────
        orb = QLabel("ENGEL")
        orb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        orb.setFixedHeight(44)
        orb.setStyleSheet(
            "QLabel {"
            "  color: #00ff88;"
            "  font-weight: 900;"
            "  font-size: 14pt;"
            "  letter-spacing: 4px;"
            "  background: #111111;"
            "  border: 1px solid #333333;"
            "  border-radius: 0px;"
            "  font-family: Consolas, monospace;"
            "}"
        )
        layout.addWidget(orb)
        self.status_label = center_label(self.data_manager.local_status_label(), 8, 600, "#666666")
        layout.addWidget(self.status_label)

        # ── selected node box ─────────────────────────────────────────────
        layout.addWidget(label("SELECTED", 8, 700, "#ffaa00"))
        self.selected_box = QTextEdit()
        self.selected_box.setReadOnly(True)
        self.selected_box.setFixedHeight(90)
        self.selected_box.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.selected_box.setStyleSheet(text_box_style())
        self.selected_box.setPlainText("No entity selected.")
        layout.addWidget(self.selected_box)

        # ── compact metrics grid ──────────────────────────────────────────
        self.metric_labels: dict[str, QLabel] = {}
        mg = QGridLayout()
        mg.setSpacing(4)
        for index, (key, color) in enumerate([
            ("Colonies", "#44aaff"), ("Worker Events", "#ffaa00"),
            ("Remote Queens", "#44aaff"), ("Growth Paths", "#ffaa00"),
            ("Telemetry", "#00ff88"),
        ]):
            v = label("--", 11, 900, color)
            v.setAlignment(Qt.AlignmentFlag.AlignCenter)
            c = label(key, 7, 400, "#666666")
            c.setAlignment(Qt.AlignmentFlag.AlignCenter)
            box = QVBoxLayout()
            box.setSpacing(0)
            box.addWidget(v)
            box.addWidget(c)
            mg.addLayout(box, index // 2, index % 2)
            self.metric_labels[key] = v
        layout.addLayout(mg)

        # ── hive summary box ──────────────────────────────────────────────
        self.copy = QTextEdit()
        self.copy.setReadOnly(True)
        self.copy.setFixedHeight(110)
        self.copy.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.copy.setStyleSheet(text_box_style())
        self._write_panel(self.data_manager.section_summary("hive_overview"))
        layout.addWidget(self.copy)

        # ── AI audit tabs (compact) ───────────────────────────────────────
        self.ai_audit_tabs = QTabWidget()
        self.ai_audit_tabs.setObjectName("AIAuditTabs")
        self.ai_audit_tabs.setStyleSheet(
            "QTabWidget::pane { border: 1px solid #333333; border-radius:0px; background:#0a0a0a; } "
            "QTabBar::tab { background: #111111; color: #666666; "
            "padding: 3px 6px; border: 1px solid #222222; border-bottom: 0; "
            "font-size:8pt; font-family:Consolas,monospace; border-radius:0px; } "
            "QTabBar::tab:selected { color: #00ff88; border-color: #333333; background: #0a0a0a; } "
            "QTabBar::tab:hover { color: #cccccc; border-color: #333333; } "
        )
        self.ai_audit_tabs.addTab(self._build_ai_plan_panel(), "Plan")
        self.ai_audit_tabs.addTab(self._build_ai_body_panel(), "Body")
        self.ai_audit_tabs.addTab(self._build_receipt_viewer_panel(), "Receipts")
        self.ai_audit_tabs.addTab(self._build_mobile_connection_panel(), "Mobile")
        layout.addWidget(self.ai_audit_tabs)

        # ── quick-nav buttons ─────────────────────────────────────────────
        layout.addWidget(label("NAVIGATE", 8, 700, "#ffaa00"))
        nav_grid = QGridLayout()
        nav_grid.setSpacing(5)
        for index, (title, callback) in enumerate([
            ("Research",  lambda: self._focus_section("research")),
            ("Think",     lambda: self._focus_section("think")),
            ("Hive",      self._show_hive_status),
            ("Commands",  lambda: self._focus_section("signal_analyzer")),
            ("Seed Brain",lambda: self._focus_section("hive_overview")),
        ]):
            b = QPushButton(title)
            b.clicked.connect(callback)
            nav_grid.addWidget(b, index // 2, index % 2)
        layout.addLayout(nav_grid)

        # ── chat entry ────────────────────────────────────────────────────
        self.entry = QLineEdit()
        self.entry.setPlaceholderText("Ask Engel…")
        self.entry.returnPressed.connect(self._submit_companion_text)
        layout.addWidget(self.entry)

        # ── tool section links ────────────────────────────────────────────
        layout.addWidget(label("SECTIONS", 8, 700, "#44aaff"))
        self.tool_rows: list[QPushButton] = []
        for section in ["hive_overview", "communication_queen", "remote_queens", "growth_paths", "signal_analyzer"]:
            adapter = self.data_manager.section_adapter(section)
            title = adapter.label if adapter else section.replace("_", " ").title()
            detail = adapter.button_detail if adapter else "Focus local section"
            self._add_tool_row(layout, title, detail, section)

        self.data_manager.data_updated.connect(self._sync_from_data)
        layout.addStretch(1)
        layout.addWidget(center_label("LOCAL DATA  •  GUARDIAN FILTERED", 7, 400, "#666666"))
        scroll.setWidget(content)
        root_layout.addWidget(scroll)
        self._sync_from_data()

    def _add_tool_row(self, layout: QVBoxLayout, title: str, detail: str, section: str) -> None:
        button = QPushButton(title)
        button.setToolTip(f"{detail}\nFocuses local section only.")
        button.clicked.connect(lambda checked=False, section_name=section: self._focus_section(section_name))
        layout.addWidget(button)
        self.tool_rows.append(button)

    def _sync_from_data(self) -> None:
        self.status_label.setText(self.data_manager.local_status_label())
        metrics = self.data_manager.metrics()
        values = {
            "Colonies": metrics["colonies"],
            "Worker Events": metrics["worker_events"],
            "Remote Queens": metrics["remote_queens"],
            "Growth Paths": metrics["growth_paths"],
            "Telemetry": metrics["telemetry_events"],
        }
        for key, value in values.items():
            widget = self.metric_labels.get(key)
            if widget is not None:
                widget.setText(str(value))
        self.sync_selection(self.data_manager.selected_entity_id)

    def sync_selection(self, entity_id: str) -> None:
        self.selected_box.setPlainText(self.data_manager.short_entity_text(entity_id))

    def _write_panel(self, text: str) -> None:
        self.copy.setPlainText(text)

    # ENGEL_AI_BODY_SUPER_SWARM_PANEL_START
    def _ai_body_status_payload(self) -> dict[str, Any]:
        if ai_body_status is None:
            return {
                "title": "ENGEL AI BODY",
                "subtitle": "Local AI organs mapped under Josh-first authority.",
                "authority": "Josh > Guardian > Engel/runtime",
                "workflow": "Ask \u2192 Plan \u2192 Proceed \u2192 Receipt \u2192 Review",
                "badges": ["JOSH FIRST", "GUARDIAN SECOND", "LOCAL ONLY", "NO AUTONOMY", "NO MODEL COMMANDS"],
                "health_badges": ["AI BODY HEALTH", "LOCAL", "GUARDED", "REPORT-ONLY MEMORY", "VERIFY TO CONFIRM"],
                "body_flow": ["MIND \u2192 GUARDIAN \u2192 ACTION \u2192 MEMORY", "HIVE / GUI \u2192 VERIFIERS"],
                "architecture_map_present": False,
                "wrapper_package_present": False,
                "markdown_knowledge": {
                    "title": "MARKDOWN KNOWLEDGE",
                    "status": "INDEX UNAVAILABLE",
                    "json_companion": "MISSING",
                    "files_found": "UNKNOWN",
                    "indexed": "UNKNOWN",
                    "summarized_excluded": "UNKNOWN",
                    "critical_files": "UNKNOWN",
                    "unknown_needs_review": "UNKNOWN",
                    "authority": "context, not automatic authority",
                    "badges": [
                        "DOCUMENTATION ONLY",
                        "FLUID MAP",
                        "NOT AUTOMATIC AUTHORITY",
                        "NO EXECUTION",
                        "NO FILE MOVES",
                    ],
                    "safety_boundary": "AI Body helper unavailable; Markdown Knowledge index was not read.",
                },
                "file_structure": {
                    "title": "FILE STRUCTURE",
                    "status": "PLAN UNAVAILABLE",
                    "json_companion": "MISSING",
                    "current_layout": "UNKNOWN",
                    "future_layout": "UNKNOWN",
                    "migration_status": "UNKNOWN",
                    "next_slice": "UNKNOWN",
                    "policy": "JOSH-APPROVED SLICES ONLY",
                    "live_imports_changed": "UNKNOWN",
                    "files_moved_renamed": "UNKNOWN",
                    "packaging_required": "UNKNOWN",
                    "badges": [
                        "PLAN ONLY",
                        "FLUID STRUCTURE",
                        "NO FILE MOVES",
                        "NO IMPORT MIGRATION",
                        "JOSH APPROVAL REQUIRED",
                    ],
                    "safety_boundary": "AI Body helper unavailable; Fluid File Structure plan JSON was not read.",
                },
                "code_companion": {
                    "title": "CODE COMPANION",
                    "status": "SCRIPT CREATOR / PRODUCT TEMPLATES / PRODUCT ONLY",
                    "script_creator": "Python / Java / HTML",
                    "product_templates": "Python CLI, Python GUI, Java Console, HTML Dashboard, HTML Mini App",
                    "products_root": "products\\",
                    "examples_root": "examples\\code_companion",
                    "product_preview": "read-only",
                    "open_folder": "user-clicked / bounded to products\\",
                    "save_root": "examples\\code_companion",
                    "runtime_source_edits": "BLOCKED",
                    "apply": "NOT ENABLED",
                    "apply_to_engel": "NOT ENABLED",
                    "overwrite": "APPROVE_CHANGE required",
                    "python_validation": "ast / py_compile",
                    "java_toolchain": "proposal-only unless present",
                    "html": "local-only / no remote deps",
                    "dependencies": "APPROVE_INSTALL required",
                    "badges": [
                        "SCRIPT CREATOR",
                        "PRODUCT TEMPLATES",
                        "PY / JAVA / HTML",
                        "PRODUCT ONLY",
                        "NOT RUNTIME",
                        "READ ONLY PREVIEW",
                        "OPEN FOLDER",
                        "SOURCE EDITS BLOCKED",
                        "NO EXECUTION",
                        "APPROVAL GATED",
                    ],
                    "safety_boundary": "AI Body helper unavailable; Code Companion status was not read.",
                },
                "core_v1_dashboard": {
                    "title": "ENGEL CORE V1 COMMAND CENTER",
                    "core_status": "INDEX UNAVAILABLE",
                    "authority": "Josh > Guardian > Engel/runtime",
                    "flow": "Talk-to-Code \u2192 Products/Research \u2192 Lessons \u2192 Reviews \u2192 Memory Candidates",
                    "products_count": "UNKNOWN",
                    "research_intake_receipts_count": "UNKNOWN",
                    "research_summary_proposals_count": "UNKNOWN",
                    "lesson_candidates_count": "UNKNOWN",
                    "lesson_reviews_count": "UNKNOWN",
                    "research_lesson_candidates_count": "UNKNOWN",
                    "research_lesson_reviews_count": "UNKNOWN",
                    "memory_candidate_proposals_count": "UNKNOWN",
                    "browser_queen_status": "DISABLED",
                    "browser_queen_path": "Research Intake \u2192 Overnight Research",
                    "trusted_memory_status": "BLOCKED / NOT_PERFORMED",
                    "untrusted_content_guard": "ACTIVE",
                    "prompt_injection_guard": "ACTIVE",
                    "package_baseline": "Core Stabilization V1",
                    "dashboard_mode": "READ ONLY / NOT TRUSTED MEMORY / NOT APPLIED",
                    "badges": [
                        "CORE V1",
                        "READ ONLY",
                        "JOSH FIRST",
                        "GUARDIAN ACTIVE",
                        "NO TRUSTED MEMORY WRITE",
                        "BROWSER QUEEN DISABLED",
                    ],
                    "safety_boundary": "AI Body helper unavailable; Core V1 status remains read-only and not trusted memory.",
                },
                "core_continuity": {
                    "title": "ENGEL CORE CONTINUITY",
                    "status": "INDEX UNAVAILABLE",
                    "json_companion": "MISSING",
                    "products": "UNKNOWN",
                    "code_examples": "UNKNOWN",
                    "research_reports": "UNKNOWN",
                    "lesson_candidates": "UNKNOWN",
                    "lesson_reviews": "UNKNOWN",
                    "browser_queen_reviews": "UNKNOWN",
                    "proceed_receipts": "UNKNOWN",
                    "verifiers": "UNKNOWN",
                    "trusted_memory": "BLOCKED",
                    "learning_status": "candidates only",
                    "browser_queen": "research input to Overnight Research, not separate memory",
                    "authority": "Josh > Guardian > Engel/runtime",
                    "badges": ["READ ONLY INDEX", "NOT TRUSTED MEMORY", "RESEARCH SPINE", "JOSH FIRST"],
                    "safety_boundary": "AI Body helper unavailable; Core Continuity Map JSON was not read.",
                },
                "browser_queen": {
                    "title": "BROWSER QUEEN",
                    "status": "DISABLED",
                    "mode": "VISIBLE_BROWSER_ONLY_FUTURE",
                    "api": "BLOCKED",
                    "research_path": "RESEARCH_INTAKE_TO_OVERNIGHT_RESEARCH",
                    "research_display": "Research Intake \u2192 Overnight Research",
                    "page_content": "UNTRUSTED_DATA",
                    "page_display": "untrusted",
                    "action_receipts": "REQUIRED",
                    "trusted_memory": "BLOCKED",
                    "authority": "Josh > Guardian > Engel/runtime",
                    "badges": [
                        "DISABLED",
                        "NO API",
                        "VISIBLE ONLY FUTURE",
                        "RESEARCH INPUT",
                        "UNTRUSTED PAGES",
                    ],
                    "safety_boundary": "AI Body helper unavailable; Browser Queen remains disabled/status-only.",
                },
                "organ_cards": [],
                "runtime_note": "AI Body helper unavailable; no action was executed.",
            }
        return ai_body_status.build_ai_body_status()

    def _add_ai_body_card(self, grid: QGridLayout, parent: QWidget, card: dict[str, Any], index: int) -> QFrame:
        frame = QFrame(parent)
        frame.setObjectName("AIBodyOrganCard")
        frame.setMinimumHeight(182)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(9, 9, 9, 9)
        frame_layout.setSpacing(5)

        frame_layout.addWidget(label(str(card.get("name", "")), 9, 700, "#cccccc"))
        frame_layout.addWidget(label(str(card.get("purpose", "")), 8, 400, "#666666"))

        status = center_label(str(card.get("status", "READ_ONLY")), 8, 700, "#00ff88")
        status.setStyleSheet(
            "background: #111111; border: 1px solid #333333; "
            "border-radius: 0px; color: #00ff88; padding: 3px; font-family: Consolas, monospace;"
        )
        frame_layout.addWidget(status)

        indicators = [str(item) for item in card.get("health_indicators", card.get("badges", []))[:3]]
        if indicators:
            health = center_label("  |  ".join(indicators), 7, 600, "#666666")
            health.setStyleSheet(
                "background: #0a1a0a; border: 1px solid #333333; "
                "border-radius: 0px; color: #666666; padding: 3px; font-family: Consolas, monospace;"
            )
            frame_layout.addWidget(health)

        modules = label("\n".join(str(item) for item in card.get("mapped_modules", [])), 8, 400, "#666666")
        modules.setStyleSheet("font-family: Consolas, monospace; color: #666666;")
        frame_layout.addWidget(modules)

        safety = label("Safety: " + str(card.get("safety_boundary", "")), 8, 400, "#ffaa00")
        frame_layout.addWidget(safety)
        frame_layout.addStretch(1)

        grid.addWidget(frame, index, 0)
        return frame

    def _add_markdown_knowledge_card(self, grid: QGridLayout, parent: QWidget, summary: dict[str, Any]) -> QFrame:
        frame = QFrame(parent)
        frame.setObjectName("AIBodyOrganCard")
        frame.setMinimumHeight(128)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(9, 9, 9, 9)
        frame_layout.setSpacing(5)

        frame_layout.addWidget(label("MARKDOWN KNOWLEDGE", 10, 900, "#cccccc"))
        badge_items = [(str(badge), "#44aaff") for badge in summary.get("badges", [])]
        frame_layout.addWidget(make_badge_row(badge_items[:3]))
        frame_layout.addWidget(make_badge_row(badge_items[3:]))

        details = label(
            "Files found: " + str(summary.get("files_found", "UNKNOWN")) + "  |  "
            "Indexed: " + str(summary.get("indexed", "UNKNOWN")) + "\n"
            "Summarized/excluded: " + str(summary.get("summarized_excluded", "UNKNOWN")) + "  |  "
            "Critical files: " + str(summary.get("critical_files", "UNKNOWN")) + "\n"
            "Unknown / Needs Review: " + str(summary.get("unknown_needs_review", "UNKNOWN")) + "  |  "
            "JSON companion: " + str(summary.get("json_companion", "UNKNOWN")) + "\n"
            "Status: " + str(summary.get("status", "INDEX UNAVAILABLE")) + "\n"
            "Authority: " + str(summary.get("authority", "context, not automatic authority")),
            8,
            800,
            "#cccccc",
        )
        frame_layout.addWidget(details)

        safety = label("Safety: " + str(summary.get("safety_boundary", "")), 8, 700, "#ffaa00")
        frame_layout.addWidget(safety)
        grid.addWidget(frame, 0, 0)
        return frame

    def _add_file_structure_card(self, grid: QGridLayout, parent: QWidget, summary: dict[str, Any]) -> QFrame:
        frame = QFrame(parent)
        frame.setObjectName("AIBodyOrganCard")
        frame.setMinimumHeight(150)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(9, 9, 9, 9)
        frame_layout.setSpacing(5)

        frame_layout.addWidget(label("FILE STRUCTURE", 10, 900, "#cccccc"))
        badge_items = [(str(badge), "#00ff88") for badge in summary.get("badges", [])]
        frame_layout.addWidget(make_badge_row(badge_items[:3]))
        frame_layout.addWidget(make_badge_row(badge_items[3:]))

        details = label(
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
            8,
            800,
            "#cccccc",
        )
        frame_layout.addWidget(details)

        safety = label("Safety: " + str(summary.get("safety_boundary", "")), 8, 700, "#ffaa00")
        frame_layout.addWidget(safety)
        grid.addWidget(frame, 1, 0)
        return frame

    def _add_code_companion_card(self, grid: QGridLayout, parent: QWidget, summary: dict[str, Any]) -> QFrame:
        frame = QFrame(parent)
        frame.setObjectName("AIBodyOrganCard")
        frame.setMinimumHeight(170)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(9, 9, 9, 9)
        frame_layout.setSpacing(5)

        frame_layout.addWidget(label("CODE COMPANION", 10, 900, "#cccccc"))
        badge_items = [(str(badge), "#44aaff") for badge in summary.get("badges", [])]
        frame_layout.addWidget(make_badge_row(badge_items[:3]))
        frame_layout.addWidget(make_badge_row(badge_items[3:]))

        details = label(
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
            8,
            800,
            "#cccccc",
        )
        frame_layout.addWidget(details)

        safety = label("Safety: " + str(summary.get("safety_boundary", "")), 8, 700, "#ffaa00")
        frame_layout.addWidget(safety)
        grid.addWidget(frame, 2, 0)
        return frame

    def _add_core_v1_dashboard_card(self, grid: QGridLayout, parent: QWidget, summary: dict[str, Any]) -> QFrame:
        frame = QFrame(parent)
        frame.setObjectName("AIBodyOrganCard")
        frame.setMinimumHeight(128)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(9, 9, 9, 9)
        frame_layout.setSpacing(5)

        frame_layout.addWidget(label("ENGEL CORE V1 COMMAND CENTER", 10, 900, "#cccccc"))
        badges = summary.get(
            "badges",
            ["CORE V1", "READ ONLY", "JOSH FIRST", "GUARDIAN ACTIVE", "NO TRUSTED MEMORY WRITE", "BROWSER QUEEN DISABLED"],
        )
        badge_items = [(str(badge), "#00ff88" if index < 4 else "#44aaff") for index, badge in enumerate(badges)]
        frame_layout.addWidget(make_badge_row(badge_items[:3]))
        frame_layout.addWidget(make_badge_row(badge_items[3:]))

        details = label(
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
            "Browser Queen: " + str(summary.get("browser_queen_status", "DISABLED")) + " \u2192 Research Intake\n"
            "Guards: Untrusted Content Guard "
            + str(summary.get("untrusted_content_guard", "ACTIVE"))
            + " / Prompt Injection Guard "
            + str(summary.get("prompt_injection_guard", "ACTIVE"))
            + "\n"
            "Status: " + str(summary.get("dashboard_mode", "READ ONLY / NOT TRUSTED MEMORY / NOT APPLIED")),
            8,
            800,
            "#cccccc",
        )
        frame_layout.addWidget(details)

        safety = label("Safety: " + str(summary.get("safety_boundary", "")), 8, 700, "#ffaa00")
        frame_layout.addWidget(safety)
        grid.addWidget(frame, 3, 0)
        return frame

    def _add_core_continuity_card(self, grid: QGridLayout, parent: QWidget, summary: dict[str, Any]) -> QFrame:
        frame = QFrame(parent)
        frame.setObjectName("AIBodyOrganCard")
        frame.setMinimumHeight(138)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(9, 9, 9, 9)
        frame_layout.setSpacing(5)

        frame_layout.addWidget(label("ENGEL CORE CONTINUITY", 10, 900, "#cccccc"))
        badge_items = [(str(badge), "#00ff88") for badge in summary.get("badges", [])]
        frame_layout.addWidget(make_badge_row(badge_items[:2]))
        frame_layout.addWidget(make_badge_row(badge_items[2:]))

        details = label(
            "Products: " + str(summary.get("products", "UNKNOWN")) + "  |  "
            "Research: " + str(summary.get("research_reports", "UNKNOWN")) + "  |  "
            "Lessons: "
            + str(summary.get("lesson_candidates", "UNKNOWN"))
            + " / "
            + str(summary.get("lesson_reviews", "UNKNOWN"))
            + "\n"
            "Browser Queen: " + str(summary.get("browser_queen", "research input to Overnight Research, not separate memory")) + "\n"
            "Trusted memory: " + str(summary.get("trusted_memory", "BLOCKED")) + "  |  "
            "Status: " + str(summary.get("status", "READ ONLY INDEX")),
            8,
            800,
            "#cccccc",
        )
        frame_layout.addWidget(details)

        safety = label("Safety: " + str(summary.get("safety_boundary", "")), 8, 700, "#ffaa00")
        frame_layout.addWidget(safety)
        grid.addWidget(frame, 4, 0)
        return frame

    def _add_browser_queen_card(self, grid: QGridLayout, parent: QWidget, summary: dict[str, Any]) -> QFrame:
        frame = QFrame(parent)
        frame.setObjectName("AIBodyOrganCard")
        frame.setMinimumHeight(124)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(9, 9, 9, 9)
        frame_layout.setSpacing(5)

        frame_layout.addWidget(label("BROWSER QUEEN", 10, 900, "#cccccc"))
        badges = summary.get(
            "badges",
            ["DISABLED", "NO API", "VISIBLE ONLY FUTURE", "RESEARCH INPUT", "UNTRUSTED PAGES"],
        )
        badge_items = [(str(badge), "#44aaff") for badge in badges]
        frame_layout.addWidget(make_badge_row(badge_items[:3]))
        frame_layout.addWidget(make_badge_row(badge_items[3:]))

        details = label(
            "Status: " + str(summary.get("status", "DISABLED")) + "  |  "
            "API: " + str(summary.get("api", "BLOCKED")) + "\n"
            "Research: " + str(summary.get("research_display", "Research Intake \u2192 Overnight Research")) + "  |  "
            "Page text: " + str(summary.get("page_display", "untrusted")) + "\n"
            "Mode: " + str(summary.get("mode", "VISIBLE_BROWSER_ONLY_FUTURE")) + "  |  "
            "Receipts: " + str(summary.get("action_receipts", "REQUIRED")),
            8,
            800,
            "#cccccc",
        )
        frame_layout.addWidget(details)

        safety = label("Safety: " + str(summary.get("safety_boundary", "")), 8, 700, "#ffaa00")
        frame_layout.addWidget(safety)
        grid.addWidget(frame, 5, 0)
        return frame

    def _build_ai_body_panel(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("AIBodyReadOnlyPanel")
        frame.setMinimumWidth(280)
        frame.setStyleSheet(
            """
            QFrame#AIBodyReadOnlyPanel {
                background: #0a0a0a;
                border: 1px solid #333333;
                border-radius: 0px;
            }
            QFrame#AIBodyOrganCard {
                background: #111111;
                border: 1px solid #222222;
                border-radius: 0px;
            }
            QScrollArea {
                border: 0;
                background: transparent;
            }
            """
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        status = self._ai_body_status_payload()
        layout.addWidget(center_label("ENGEL AI BODY", 9, 700, "#44aaff"))
        layout.addWidget(center_label(str(status.get("subtitle", "Local AI organs mapped under Josh-first authority.")), 8, 800, "#00ff88"))
        badge_items = [(str(badge), "#00ff88" if index < 2 else "#44aaff") for index, badge in enumerate(status.get("badges", []))]
        layout.addWidget(make_badge_row(badge_items[:3]))
        layout.addWidget(make_badge_row(badge_items[3:]))
        health_badges = status.get("health_badges", ["AI BODY HEALTH", "LOCAL", "GUARDED", "REPORT-ONLY MEMORY", "VERIFY TO CONFIRM"])
        health_summary = center_label("  |  ".join(str(item) for item in health_badges), 8, 900, "#00ff88")
        health_summary.setStyleSheet(
            "background: #0a1a0a; border: 1px solid #333333; "
            "border-radius: 0px; color: #00ff88; padding: 4px; font-family: Consolas, monospace;"
        )
        layout.addWidget(health_summary)

        authority = QTextEdit()
        authority.setReadOnly(True)
        authority.setMaximumHeight(104)
        authority.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        authority.setStyleSheet(text_box_style())
        authority.setPlainText(
            "Authority: " + str(status.get("authority", "")) + "\n"
            "Workflow: " + str(status.get("workflow", "")) + "\n"
            "Architecture map: " + ("present" if status.get("architecture_map_present") else "missing") + "\n"
            "Wrapper package: " + ("present" if status.get("wrapper_package_present") else "missing") + "\n\n"
            + "\n".join(str(item) for item in status.get("body_flow", []))
        )
        layout.addWidget(authority)

        scroll = QScrollArea(frame)
        scroll.setWidgetResizable(True)
        scroll_content = QWidget(scroll)
        grid = QGridLayout(scroll_content)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(8)
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

        note = label(str(status.get("runtime_note", "")), 8, 700, "#ffaa00")
        layout.addWidget(note)
        return frame
    # ENGEL_AI_BODY_SUPER_SWARM_PANEL_END

    def _build_ai_plan_panel(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("Panel")
        frame.setStyleSheet(
            """
            QFrame#Panel {
                background: #0a0a0a;
                border: 1px solid #333333;
                border-radius: 0px;
            }
            QLineEdit {
                background: #111111;
                border: 1px solid #333333;
                border-radius: 0px;
                color: #cccccc;
                padding: 4px 6px;
                font-family: Consolas, monospace;
                font-size: 9pt;
            }
            QPushButton {
                background: #111111;
                border: 1px solid #333333;
                border-radius: 0px;
                color: #44aaff;
                padding: 3px 7px;
                font-weight: 700;
                font-family: Consolas, monospace;
            }
            QPushButton:hover {
                border-color: #00ff88;
                color: #ffffff;
            }
            QPushButton:disabled {
                border-color: #222222;
                color: #333333;
            }
            """
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        self.ai_last_plan = None
        layout.addWidget(center_label("ENGEL AI PLAN", 9, 700, "#44aaff"))
        layout.addWidget(
            make_badge_row(
                [
                    ("JOSH FIRST", "#00ff88"),
                    ("GUARDIAN ACTIVE", "#44aaff"),
                    ("PLAN ONLY", "#44aaff"),
                ]
            )
        )
        layout.addWidget(
            make_badge_row(
                [
                    ("MODEL CANNOT EXECUTE", "#ffaa00"),
                    ("AUTONOMY BLOCKED", "#ff6b8a"),
                ]
            )
        )
        self.ai_plan_entry = QLineEdit()
        self.ai_plan_entry.setPlaceholderText("Request to plan; Proceed is gated")
        self.ai_plan_entry.returnPressed.connect(self._show_ai_plan)
        layout.addWidget(self.ai_plan_entry)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        for title, callback in [
            ("Plan", self._show_ai_plan),
            ("Classify", self._show_ai_classification),
            ("Planner Status", self._show_ai_planner_status),
        ]:
            button = QPushButton(title)
            button.setMinimumHeight(32)
            button.setToolTip("Read-only planner output. Does not execute target actions.")
            button.clicked.connect(callback)
            row.addWidget(button)
        layout.addLayout(row)
        proceed_row = QHBoxLayout()
        proceed_row.setContentsMargins(0, 0, 0, 0)
        proceed_row.setSpacing(6)
        self.ai_proceed_button = QPushButton("Proceed")
        self.ai_proceed_button.setMinimumHeight(32)
        self.ai_proceed_button.setEnabled(False)
        self.ai_proceed_button.setToolTip("Disabled until a safe approval-free deterministic plan is ready.")
        self.ai_proceed_button.clicked.connect(self._proceed_ai_plan)
        self.ai_proceed_status = QLabel("Plan only")
        self.ai_proceed_status.setWordWrap(True)
        self.ai_proceed_status.setStyleSheet("color: #00ff88; font-size: 8pt; font-weight: 700; font-family: Consolas, monospace;")
        proceed_row.addWidget(self.ai_proceed_button)
        proceed_row.addWidget(self.ai_proceed_status, 1)
        layout.addLayout(proceed_row)
        self.ai_plan_output = QTextEdit()
        self.ai_plan_output.setReadOnly(True)
        self.ai_plan_output.setMinimumHeight(170)
        self.ai_plan_output.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.ai_plan_output.setStyleSheet(text_box_style())
        self.ai_plan_output.setPlainText(
            "Intent:\nRoute:\nRisk:\nApproval:\nGuardian:\nAuthority: Josh > Guardian > Engel/runtime\nSuggested command:\nNext step:\n\nPlan output appears here. Proceed only runs approval-free allowlisted deterministic routes."
        )
        layout.addWidget(self.ai_plan_output)
        return frame

    def _receipt_table_item(self, text: str, path_text: str = "") -> QTableWidgetItem:
        item = QTableWidgetItem(str(text or ""))
        try:
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if path_text:
                item.setData(Qt.ItemDataRole.UserRole, str(path_text))
        except Exception:
            pass
        return item

    def _build_receipt_viewer_panel(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("Panel")
        frame.setStyleSheet(
            """
            QFrame#Panel {
                background: #0a0a0a;
                border: 1px solid #333333;
                border-radius: 0px;
            }
            QTableWidget {
                background: #0a0a0a;
                border: 1px solid #333333;
                border-radius: 0px;
                color: #cccccc;
                font-size: 8pt;
                font-family: Consolas, monospace;
            }
            QHeaderView::section {
                background: #111111;
                color: #00ff88;
                border: 0;
                padding: 4px;
                font-size: 8pt;
                font-weight: 700;
                font-family: Consolas, monospace;
            }
            """
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        layout.addWidget(center_label("PROCEED RECEIPTS", 9, 700, "#44aaff"))
        layout.addWidget(
            make_badge_row(
                [
                    ("REPORT ONLY", "#00ff88"),
                    ("READ ONLY", "#44aaff"),
                ]
            )
        )
        layout.addWidget(
            make_badge_row(
                [
                    ("NOT TRUSTED MEMORY", "#ffaa00"),
                    ("NO EXECUTION", "#ff6b8a"),
                ]
            )
        )

        self.ai_receipt_table = QTableWidget()
        self.ai_receipt_table.setColumnCount(5)
        self.ai_receipt_table.setHorizontalHeaderLabels(["File", "Timestamp", "Status", "Intent", "Surface"])
        self.ai_receipt_table.setMinimumHeight(145)
        self.ai_receipt_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.ai_receipt_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.ai_receipt_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.ai_receipt_table.verticalHeader().setVisible(False)
        self.ai_receipt_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.ai_receipt_table.setWordWrap(False)
        layout.addWidget(self.ai_receipt_table)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(6)
        self.ai_receipt_refresh_button = QPushButton("Refresh Receipts")
        self.ai_receipt_open_button = QPushButton("Open Selected")
        for button in (self.ai_receipt_refresh_button, self.ai_receipt_open_button):
            button.setMinimumHeight(32)
            button.setToolTip("Read-only receipt viewer. Does not execute receipt content.")
            button_row.addWidget(button)
        self.ai_receipt_refresh_button.clicked.connect(self._refresh_ai_receipts)
        self.ai_receipt_open_button.clicked.connect(self._open_selected_ai_receipt)
        layout.addLayout(button_row)

        self.ai_receipt_status = QLabel("Receipts are report-only audit files, not trusted memory.")
        self.ai_receipt_status.setWordWrap(True)
        self.ai_receipt_status.setStyleSheet("color: #00ff88; font-size: 8px; font-weight: 800;")
        layout.addWidget(self.ai_receipt_status)

        self.ai_receipt_content = QTextEdit()
        self.ai_receipt_content.setReadOnly(True)
        self.ai_receipt_content.setMinimumHeight(190)
        self.ai_receipt_content.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.ai_receipt_content.setStyleSheet(text_box_style())
        self.ai_receipt_content.setPlainText("No receipt selected.")
        layout.addWidget(self.ai_receipt_content)
        self._refresh_ai_receipts()
        return frame

    def _refresh_ai_receipts(self) -> None:
        if receipt_viewer is None:
            self.ai_receipt_status.setText("Receipt viewer helper is unavailable.")
            self.ai_receipt_content.setPlainText("Receipt viewer helper is unavailable.")
            return
        try:
            summaries = receipt_viewer.list_receipts(limit=25)
        except Exception as exc:
            summaries = []
            self.ai_receipt_status.setText("Receipt refresh error: " + str(exc))
        try:
            self.ai_receipt_table.setSortingEnabled(False)
            self.ai_receipt_table.setRowCount(0)
            if not summaries:
                self.ai_receipt_table.setRowCount(1)
                self.ai_receipt_table.setItem(0, 0, self._receipt_table_item("No receipts yet."))
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
            self.ai_receipt_status.setText("Receipt refresh error: " + str(exc))

    def _selected_ai_receipt_path(self) -> Path | None:
        if receipt_viewer is None:
            return None
        try:
            row = self.ai_receipt_table.currentRow()
            if row < 0:
                return None
            item = self.ai_receipt_table.item(row, 0)
            if item is None:
                return None
            path_text = item.data(Qt.ItemDataRole.UserRole)
            if not path_text:
                return None
            path = Path(str(path_text))
            if not receipt_viewer.is_safe_receipt_path(path):
                return None
            return path
        except Exception:
            return None

    def _open_selected_ai_receipt(self) -> None:
        if receipt_viewer is None:
            self.ai_receipt_content.setPlainText("Receipt viewer helper is unavailable.")
            self.ai_receipt_status.setText("Receipt viewer helper is unavailable.")
            return
        path = self._selected_ai_receipt_path()
        if path is None:
            self.ai_receipt_content.setPlainText("Select a receipt markdown file under reports\\ai_proceed_receipts.")
            self.ai_receipt_status.setText("No safe receipt selected.")
            return
        try:
            content = receipt_viewer.read_receipt_bounded(path, max_chars=12000)
            self.ai_receipt_content.setPlainText(content)
            self.ai_receipt_status.setText("Opened read-only receipt: " + Path(path).name)
        except Exception as exc:
            self.ai_receipt_content.setPlainText("Could not open receipt: " + str(exc))
            self.ai_receipt_status.setText("Receipt open error.")

    # ENGEL_MOBILE_CONNECTION_SUPER_SWARM_READONLY_TAB_V1_PANEL_START
    def _mobile_readonly_item(self, text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(str(text or ""))
        try:
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        except Exception:
            pass
        return item

    def _mobile_doc_status_item(self, relative_path: str) -> str:
        path = ROOT / str(relative_path)
        if not path.exists():
            return "Missing"
        try:
            modified = time.strftime("%Y-%m-%d %H:%M", time.localtime(path.stat().st_mtime))
            return "Found / " + modified
        except Exception:
            return "Found"

    def _add_mobile_section(self, layout: QVBoxLayout, parent: QWidget, title: str, body: str) -> QFrame:
        section = QFrame(parent)
        section.setObjectName("MobileConnectionSection")
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(8, 8, 8, 8)
        section_layout.setSpacing(5)

        title_label = label(title, 9, 900, "#cccccc")
        title_label.setParent(section)
        section_layout.addWidget(title_label)

        body_label = label(body, 8, 600, "#666666")
        body_label.setParent(section)
        section_layout.addWidget(body_label)

        layout.addWidget(section)
        return section

    def _build_mobile_connection_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("MobileConnectionReadOnlyPanel")
        panel.setMinimumWidth(280)
        panel.setStyleSheet(
            """
            QFrame#MobileConnectionReadOnlyPanel {
                background: #0a0a0a;
                border: 1px solid #333333;
                border-radius: 0px;
            }
            QFrame#MobileConnectionSection {
                background: #111111;
                border: 1px solid #222222;
                border-radius: 0px;
            }
            QFrame#MobileConnectionCompactBadge {
                background: #0a0a0a;
                border: 1px solid #44aaff;
                border-radius: 0px;
            }
            QPushButton {
                background: #111111;
                color: #44aaff;
                border: 1px solid #333333;
                border-radius: 0px;
                padding: 3px 6px;
                font: 700 8pt Consolas;
            }
            QPushButton:disabled {
                color: #333333;
                border-color: #222222;
                background: #0a0a0a;
            }
            QTableWidget {
                background: #0a0a0a;
                border: 1px solid #333333;
                border-radius: 0px;
                color: #cccccc;
                font: 8pt Consolas;
            }
            QHeaderView::section {
                background: #111111;
                color: #00ff88;
                border: 0;
                padding: 4px;
                font: 700 8pt Consolas;
            }
            QScrollArea {
                border: 0;
                background: transparent;
            }
            """
        )

        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(10, 10, 10, 10)
        panel_layout.setSpacing(7)

        title = center_label("Engel Mobile Connection", 9, 700, "#44aaff")
        panel_layout.addWidget(title)

        status = center_label("Contract installed; runtime not enabled", 8, 600, "#758596")
        status.setStyleSheet(
            "background: #111111; border: 1px solid #333333; "
            "border-radius: 0px; color: #758596; padding: 4px; font-family: Consolas, monospace;"
        )
        panel_layout.addWidget(status)

        badge_text = "\n".join(
            [
                "Super Swarm compact Mobile badge",
                "Mobile: planned / disabled",
                "Mobile: Planned",
                "Runtime: OFF",
                "Runtime: Disabled",
                "Networking: Not implemented",
                "Pairing: OFF",
                "Pairing: Not implemented",
                "Packets: OFF",
                "Packets: Untrusted",
                "Command authority: OFF",
                "Commands: Blocked",
                MOBILE_SWARM_REMOTE_QUEENS_LABEL + ": Blocked",
                "Local-only / read-only",
                "Human approval: Required",
            ]
        )
        badges = QLabel(badge_text, panel)
        badges.setObjectName("MobileConnectionCompactBadge")
        badges.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        badges.setWordWrap(True)
        badges.setStyleSheet(
            "background: #0a0a0a; border: 1px solid #44aaff; "
            "border-radius: 0px; color: #e8f4ff; padding: 8px; font-family: Consolas, monospace; font-size: 8pt;"
        )
        panel_layout.addWidget(badges)

        self._add_mobile_section(
            panel_layout,
            panel,
            "Super Swarm role",
            "Secondary read-only Mobile summary only. Companion remains the full Mobile status owner.",
        )

        compact_metrics = "\n".join(
            [
                "paired_devices_count: 0",
                "pending_mobile_packets_count: 0",
                "mobile_runtime_enabled: false",
                "mobile_networking_enabled: false",
                "mobile_pairing_enabled: false",
                "mobile_packet_processing_enabled: false",
                "mobile_command_authority_enabled: false",
                "remote_queen_mobile_handoff_enabled: false",
            ]
        )
        self._add_mobile_section(
            panel_layout,
            panel,
            "Disabled state",
            compact_metrics,
        )

        self._add_mobile_section(
            panel_layout,
            panel,
            "Safety boundary",
            "No mobile runtime, pairing, packet receiver, command channel, trusted-memory write, "
            "source edit, queue/route mutation, network listener, or Remote Queen runtime is enabled here.",
        )

        self._add_mobile_section(
            panel_layout,
            panel,
            "Evidence source",
            "Contracts, reports, and verifiers remain evidence only. This compact Super Swarm badge does not "
            "create, modify, delete, trust, execute, or approve Mobile material.",
        )

        button = QPushButton("Mobile runtime controls unavailable", panel)
        button.setEnabled(False)
        button.hide()
        self.mobile_disabled_action_sentinel = button

        panel_layout.addStretch(1)
        return panel
    # ENGEL_MOBILE_CONNECTION_SUPER_SWARM_READONLY_TAB_V1_PANEL_END

    def _ai_plan_request_text(self) -> str:
        try:
            text = self.ai_plan_entry.text().strip()
        except Exception:
            text = ""
        if not text:
            try:
                text = self.entry.text().strip()
            except Exception:
                text = ""
        return text

    def _set_ai_plan_output(self, text: str) -> None:
        try:
            self.ai_plan_output.setPlainText(str(text or ""))
        except Exception:
            pass

    def _append_ai_plan_output(self, text: str) -> None:
        try:
            current = self.ai_plan_output.toPlainText()
            self.ai_plan_output.setPlainText((current.rstrip() + "\n\n" + str(text or "")).strip())
        except Exception:
            pass

    def _set_ai_proceed_state(self, plan=None, status_text: str | None = None) -> None:
        try:
            self.ai_last_plan = plan
        except Exception:
            pass
        label = status_text or "Plan only"
        enabled = False
        tooltip = "Proceed writes an audit receipt; only safe approval-free deterministic plans execute."
        if ai_planner is not None and plan is not None:
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

    def _record_ai_proceed_receipt(self, plan, status: str, command_run: str = "", result_summary: str = "", output_excerpt: str = "", reason: str = "") -> str:
        if proceed_receipts is None:
            return "\n\nReceipt error:\nProceed receipt helper is unavailable."
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
                "Super Swarm",
            )
            try:
                shown_path = Path(receipt_path).resolve().relative_to(ROOT.resolve())
            except Exception:
                shown_path = receipt_path
            return "\n\nReceipt written:\n" + str(shown_path)
        except Exception as exc:
            return "\n\nReceipt error:\n" + str(exc)

    def _show_ai_plan(self) -> None:
        if ai_planner is None:
            self._set_ai_plan_output("AI planner module is unavailable in this build.")
            self._set_ai_proceed_state(None, "Error")
            return
        text = self._ai_plan_request_text()
        if not text:
            self._set_ai_plan_output("Enter a request first. Planning is local/read-only and executes nothing.")
            self._set_ai_proceed_state(None, "Plan only")
            return
        plan = ai_planner.build_plan(text)
        self._set_ai_proceed_state(plan)
        self._set_ai_plan_output(ai_planner.render_plan(plan))

    def _show_ai_classification(self) -> None:
        if ai_planner is None:
            self._set_ai_plan_output("AI planner module is unavailable in this build.")
            self._set_ai_proceed_state(None, "Error")
            return
        text = self._ai_plan_request_text()
        if not text:
            self._set_ai_plan_output("Enter a request first. Classification is local/read-only and executes nothing.")
            self._set_ai_proceed_state(None, "Plan only")
            return
        plan = ai_planner.classify_intent(text)
        self._set_ai_proceed_state(plan)
        self._set_ai_plan_output(ai_planner.render_classification(plan))

    def _show_ai_planner_status(self) -> None:
        if ai_planner is None:
            self._set_ai_plan_output("AI planner module is unavailable in this build.")
            self._set_ai_proceed_state(None, "Error")
            return
        self._set_ai_proceed_state(None, "Plan only")
        self._set_ai_plan_output(ai_planner.render_status())

    def _proceed_ai_plan(self) -> None:
        if ai_planner is None:
            self._set_ai_proceed_state(None, "Error")
            self._append_ai_plan_output("# Proceed Result\nStatus: Error\nReason: AI planner module is unavailable.")
            return
        plan = getattr(self, "ai_last_plan", None)
        if plan is None:
            self._set_ai_proceed_state(None, "Plan only")
            self._append_ai_plan_output("# Proceed Result\nStatus: Plan only\nNo generated plan is available.")
            return
        checked_plan = ai_planner.build_plan(getattr(plan, "user_text", ""))
        self._set_ai_proceed_state(checked_plan)
        if not ai_planner.can_proceed(checked_plan):
            reason = ai_planner.proceed_block_reason(checked_plan)
            status = "Blocked" if getattr(checked_plan, "blocked", False) else "Approval required" if getattr(checked_plan, "approval_required", False) else "Plan only"
            receipt_status = "BLOCKED" if getattr(checked_plan, "blocked", False) else "REQUIRES_APPROVAL" if getattr(checked_plan, "approval_required", False) else "BLOCKED"
            receipt_note = self._record_ai_proceed_receipt(
                checked_plan,
                receipt_status,
                result_summary=reason,
                output_excerpt=reason,
                reason=reason,
            )
            self._append_ai_plan_output("# Proceed Result\nStatus: " + status + "\nReason: " + reason + receipt_note)
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
            import engel_app as core_app
            result = core_app.handle_human_command_mode_cli(command)
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

    def _focus_section(self, section: str) -> None:
        self.data_manager.focus_section(section)
        self._write_panel(self.data_manager.section_summary(section))

    def _show_hive_status(self) -> None:
        self._focus_section("hive_overview")

    def _submit_companion_text(self) -> None:
        text = self.entry.text().strip()
        if not text:
            return
        response = self.data_manager.companion_response(text)
        self.data_manager.add_communication_message(f"ENGEL panel question: {text}", "Requests", "Pending")
        self._write_panel(f"You: {text}\n\nENGEL: {response}")
        self.entry.clear()


class GraphifyKnowledgeMapWidget(QFrame):
    selection_changed = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("GraphifyMap")
        self.setMinimumHeight(520)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.graph_path = resolve_graphify_graph_path()
        self.full_node_count = 0
        self.full_link_count = 0
        self.sample_nodes: list[dict[str, Any]] = []
        self.sample_links: list[dict[str, str]] = []
        self.node_positions: dict[str, tuple[float, float]] = {}
        self.node_degrees: Counter[str] = Counter()
        self.relation_counts: Counter[str] = Counter()
        self.group_counts: Counter[str] = Counter()
        self.group_link_counts: Counter[tuple[str, str]] = Counter()
        self.node_adjacency: dict[str, set[str]] = {}
        self.selected_neighbors: set[str] = set()
        self.node_groups: dict[str, str] = {}
        self.selected_node_id = ""
        self.error_message = ""
        self._screen_positions: dict[str, QPointF] = {}
        self._group_centers = {
            "Core": (0.50, 0.50),
            "Routes": (0.22, 0.25),
            "UI Screens": (0.76, 0.25),
            "Long Term Memory": (0.18, 0.70),
            "Reports Receipts": (0.38, 0.84),
            "Workers": (0.50, 0.17),
            "Models Runtime": (0.78, 0.72),
            "Verifiers Tools": (0.54, 0.86),
            "Vendored Modules": (0.86, 0.49),
            "Graphify": (0.50, 0.36),
        }

    def reload_graph(self) -> None:
        self.load_graph(resolve_graphify_graph_path())

    def load_graph(self, graph_path: Path) -> None:
        self.graph_path = graph_path
        self.full_node_count = 0
        self.full_link_count = 0
        self.sample_nodes = []
        self.sample_links = []
        self.node_positions = {}
        self.node_degrees = Counter()
        self.relation_counts = Counter()
        self.group_counts = Counter()
        self.group_link_counts = Counter()
        self.node_adjacency = {}
        self.selected_neighbors = set()
        self.node_groups = {}
        self.selected_node_id = ""
        self.error_message = ""

        if not graph_path.exists():
            self.error_message = f"Graphify graph not found: {graph_path}"
            self.update()
            self.selection_changed.emit("")
            return

        try:
            raw_graph = json.loads(graph_path.read_text(encoding="utf-8"))
        except Exception as exc:
            self.error_message = f"Graphify graph read error: {exc}"
            self.update()
            self.selection_changed.emit("")
            return

        nodes_raw = raw_graph.get("nodes", [])
        links_raw = raw_graph.get("links", raw_graph.get("edges", []))
        if not isinstance(nodes_raw, list) or not isinstance(links_raw, list):
            self.error_message = "Graphify graph has no usable nodes/links arrays."
            self.update()
            self.selection_changed.emit("")
            return

        self.full_node_count = len(nodes_raw)
        self.full_link_count = len(links_raw)
        node_lookup: dict[str, dict[str, Any]] = {}
        for node in nodes_raw:
            if not isinstance(node, dict):
                continue
            node_id = str(node.get("id", "")).strip()
            if node_id:
                node_lookup[node_id] = node

        for link in links_raw:
            if not isinstance(link, dict):
                continue
            source_id = str(link.get("source") or link.get("_src") or "").strip()
            target_id = str(link.get("target") or link.get("_tgt") or "").strip()
            relation = str(link.get("relation") or "related").strip() or "related"
            if source_id:
                self.node_degrees[source_id] += 1
            if target_id:
                self.node_degrees[target_id] += 1
            self.relation_counts[relation] += 1

        scored: list[tuple[int, str, str, dict[str, Any]]] = []
        for node_id, node in node_lookup.items():
            group = self._group_for_node(node)
            scored.append((self._score_node(node_id, node), group, node_id, node))

        by_group: dict[str, list[tuple[int, str, str, dict[str, Any]]]] = {
            group: [] for group in GRAPHIFY_GROUP_COLORS
        }
        for item in scored:
            by_group.setdefault(item[1], []).append(item)
        for group_items in by_group.values():
            group_items.sort(key=lambda item: item[0], reverse=True)

        selected: dict[str, dict[str, Any]] = {}
        for group in GRAPHIFY_GROUP_COLORS:
            for _, _, node_id, node in by_group.get(group, [])[:34]:
                selected.setdefault(node_id, node)

        for _, _, node_id, node in sorted(scored, key=lambda item: item[0], reverse=True):
            if len(selected) >= GRAPHIFY_SAMPLE_LIMIT:
                break
            selected.setdefault(node_id, node)

        self.sample_nodes = [dict(node, id=node_id) for node_id, node in selected.items()]
        self.node_groups = {
            str(node.get("id")): self._group_for_node(node) for node in self.sample_nodes
        }
        self.group_counts = Counter(self.node_groups.values())
        self._layout_sample_nodes()

        selected_ids = set(selected)
        for link in links_raw:
            if len(self.sample_links) >= GRAPHIFY_LINK_LIMIT:
                break
            if not isinstance(link, dict):
                continue
            source_id = str(link.get("source") or link.get("_src") or "").strip()
            target_id = str(link.get("target") or link.get("_tgt") or "").strip()
            if source_id in selected_ids and target_id in selected_ids:
                self.sample_links.append(
                    {
                        "source": source_id,
                        "target": target_id,
                        "relation": str(link.get("relation") or "related"),
                    }
                )

        if self.sample_nodes:
            self.selected_node_id = str(max(
                self.sample_nodes,
                key=lambda node: self.node_degrees[str(node.get("id", ""))],
            ).get("id", ""))
        self._build_connection_indexes()
        self.update()
        self.selection_changed.emit(self.selected_node_id)

    def summary_text(self) -> str:
        if self.error_message:
            return self.error_message
        top_relations = ", ".join(
            f"{name} {count}" for name, count in self.relation_counts.most_common(6)
        ) or "none"
        groups = "\n".join(
            f"{group}: {self.group_counts.get(group, 0)}"
            for group in GRAPHIFY_GROUP_COLORS
            if self.group_counts.get(group, 0)
        ) or "No sampled groups."
        top_group_links = ", ".join(
            f"{a}->{b} {count}" for (a, b), count in self.group_link_counts.most_common(5)
        ) or "none"
        return (
            "Engel Graphify Knowledge Map\n\n"
            f"Source: {self.graph_path}\n"
            f"Full graph: {self.full_node_count:,} nodes / {self.full_link_count:,} links\n"
            f"Rendered sample: {len(self.sample_nodes):,} nodes / {len(self.sample_links):,} links\n"
            f"Top relations: {top_relations}\n\n"
            f"Top group connects: {top_group_links}\n\n"
            f"{groups}\n\n"
            f"{self.node_detail_text(self.selected_node_id)}"
        )

    def node_detail_text(self, node_id: str) -> str:
        node = self._node_by_id(node_id)
        if node is None:
            return "Select a node on the map to inspect its local Graphify metadata."
        group = self.node_groups.get(node_id, "Core")
        label_text = str(node.get("label") or node_id)
        details = [
            "Selected Graphify node",
            "",
            f"Label: {label_text}",
            f"ID: {node_id}",
            f"Group: {group}",
            f"Degree: {self.node_degrees.get(node_id, 0)}",
            f"Sample Neighbors: {len(self.node_adjacency.get(node_id, set()))}",
        ]
        for key in ("file_type", "source_file", "source_location"):
            value = str(node.get(key, "")).strip()
            if value:
                details.append(f"{key.replace('_', ' ').title()}: {value}")
        return "\n".join(details)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor(SWARM_BG_PRIMARY))
        canvas = QRectF(self.rect()).adjusted(16, 16, -16, -16)
        self._screen_positions = {}

        if self.error_message or not self.sample_nodes:
            painter.setPen(QColor(SWARM_ACCENT_INFO))
            painter.setFont(QFont("Consolas", 10, QFont.Weight.Normal))
            painter.drawText(canvas, Qt.AlignmentFlag.AlignCenter, self.error_message or "No Graphify sample nodes.")
            painter.end()
            return

        self._draw_group_regions(painter, canvas)
        self._draw_group_connections(painter, canvas)
        self._draw_links(painter, canvas)
        self._draw_nodes(painter, canvas)
        painter.end()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        node_id = self._nearest_node_id(event.position().toPoint())
        if node_id:
            self.selected_node_id = node_id
            self.selected_neighbors = set(self.node_adjacency.get(node_id, set()))
            self.selection_changed.emit(node_id)
            self.update()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        node_id = self._nearest_node_id(event.position().toPoint())
        if node_id:
            node = self._node_by_id(node_id)
            label_text = str(node.get("label") or node_id) if node else node_id
            QToolTip.showText(event.globalPosition().toPoint(), label_text, self)
        super().mouseMoveEvent(event)

    def _draw_group_regions(self, painter: QPainter, canvas: QRectF) -> None:
        painter.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
        for group, center in self._group_centers.items():
            count = self.group_counts.get(group, 0)
            if count <= 0:
                continue
            color = QColor(GRAPHIFY_GROUP_COLORS.get(group, SWARM_ACCENT_INFO))
            color.setAlpha(36)
            pen_color = QColor(GRAPHIFY_GROUP_COLORS.get(group, SWARM_ACCENT_INFO))
            pen_color.setAlpha(92)
            x = canvas.left() + center[0] * canvas.width()
            y = canvas.top() + center[1] * canvas.height()
            radius = 46 + min(86, count * 1.45)
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(pen_color, 1.2))
            painter.drawEllipse(QPointF(x, y), radius * 1.18, radius * 0.74)
            painter.setPen(QColor(SWARM_TEXT_SECONDARY))
            painter.drawText(QPointF(x - radius * 0.55, y - radius * 0.78), f"{group} ({count})")

    def _draw_group_connections(self, painter: QPainter, canvas: QRectF) -> None:
        if not self.group_link_counts:
            return
        top_links = self.group_link_counts.most_common(14)
        for (source_group, target_group), count in top_links:
            source_center = self._group_centers.get(source_group)
            target_center = self._group_centers.get(target_group)
            if source_center is None or target_center is None:
                continue
            source = QPointF(
                canvas.left() + source_center[0] * canvas.width(),
                canvas.top() + source_center[1] * canvas.height(),
            )
            target = QPointF(
                canvas.left() + target_center[0] * canvas.width(),
                canvas.top() + target_center[1] * canvas.height(),
            )
            source_color = QColor(GRAPHIFY_GROUP_COLORS.get(source_group, SWARM_ACCENT_INFO))
            source_color.setAlpha(38 + min(84, count * 2))
            width = 2.0 + min(9.0, math.log2(count + 1) * 1.45)
            painter.setPen(QPen(source_color, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(source, target)
            painter.setPen(QPen(QColor(SWARM_BG_PRIMARY), max(0.8, width * 0.22), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(source, target)

    def _draw_links(self, painter: QPainter, canvas: QRectF) -> None:
        for link in self.sample_links:
            source = self._project(link["source"], canvas)
            target = self._project(link["target"], canvas)
            if source is None or target is None:
                continue
            color = self._relation_color(link.get("relation", ""))
            relation = link.get("relation", "")
            connected_to_selection = (
                link["source"] == self.selected_node_id
                or link["target"] == self.selected_node_id
                or link["source"] in self.selected_neighbors
                or link["target"] in self.selected_neighbors
            )
            if connected_to_selection:
                color.setAlpha(190)
                width = 1.7
            else:
                color.setAlpha(88 if relation in {"calls", "uses", "imports_from", "contains"} else 56)
                width = 1.05
            painter.setPen(QPen(color, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(source, target)

    def _draw_nodes(self, painter: QPainter, canvas: QRectF) -> None:
        label_budget = 24
        sorted_nodes = sorted(
            self.sample_nodes,
            key=lambda node: self.node_degrees[str(node.get("id", ""))],
        )
        for node in sorted_nodes:
            node_id = str(node.get("id", ""))
            point = self._project(node_id, canvas)
            if point is None:
                continue
            self._screen_positions[node_id] = point
            degree = self.node_degrees.get(node_id, 0)
            group = self.node_groups.get(node_id, "Core")
            base = QColor(GRAPHIFY_GROUP_COLORS.get(group, SWARM_ACCENT_INFO))
            radius = 3.2 + min(8.8, math.sqrt(max(1, degree)) * 0.55)
            if node_id == self.selected_node_id or node_id in self.selected_neighbors:
                glow = QColor(base)
                glow.setAlpha(74 if node_id == self.selected_node_id else 42)
                painter.setBrush(QBrush(glow))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(point, radius + (9.0 if node_id == self.selected_node_id else 5.0), radius + (9.0 if node_id == self.selected_node_id else 5.0))
            fill = QColor(base)
            fill.setAlpha(235 if node_id == self.selected_node_id else 220 if node_id in self.selected_neighbors else 205 if degree > 1 else 150)
            painter.setBrush(QBrush(fill))
            painter.setPen(QPen(QColor(SWARM_BG_PRIMARY), 0.8))
            painter.drawEllipse(point, radius, radius)

        painter.setFont(QFont("Consolas", 7, QFont.Weight.Medium))
        for node in sorted(
            self.sample_nodes,
            key=lambda item: self.node_degrees[str(item.get("id", ""))],
            reverse=True,
        )[:label_budget]:
            node_id = str(node.get("id", ""))
            point = self._screen_positions.get(node_id)
            if point is None:
                continue
            painter.setPen(QColor(SWARM_TEXT_PRIMARY if node_id == self.selected_node_id else SWARM_TEXT_SECONDARY))
            painter.drawText(point + QPointF(7.0, -5.0), self._short_label(str(node.get("label") or node_id)))

    def _build_connection_indexes(self) -> None:
        self.group_link_counts = Counter()
        self.node_adjacency = {str(node.get("id", "")): set() for node in self.sample_nodes}
        for link in self.sample_links:
            source_id = link["source"]
            target_id = link["target"]
            source_group = self.node_groups.get(source_id, "Core")
            target_group = self.node_groups.get(target_id, "Core")
            if source_group != target_group:
                self.group_link_counts[(source_group, target_group)] += 1
            self.node_adjacency.setdefault(source_id, set()).add(target_id)
            self.node_adjacency.setdefault(target_id, set()).add(source_id)
        self.selected_neighbors = set(self.node_adjacency.get(self.selected_node_id, set()))

    def _layout_sample_nodes(self) -> None:
        by_group: dict[str, list[dict[str, Any]]] = {group: [] for group in GRAPHIFY_GROUP_COLORS}
        for node in self.sample_nodes:
            by_group.setdefault(self._group_for_node(node), []).append(node)
        for group, nodes in by_group.items():
            nodes.sort(key=lambda item: self.node_degrees[str(item.get("id", ""))], reverse=True)
            center = self._group_centers.get(group, (0.5, 0.5))
            count = max(1, len(nodes))
            for index, node in enumerate(nodes):
                node_id = str(node.get("id", ""))
                ring = index // 18
                slot = index % 18
                slots = min(18, max(1, count - ring * 18))
                angle = math.tau * slot / slots + ring * 0.31
                radius = 0.035 + ring * 0.024 + (index % 3) * 0.006
                x = center[0] + math.cos(angle) * radius
                y = center[1] + math.sin(angle) * radius * 0.72
                self.node_positions[node_id] = (
                    max(0.04, min(0.96, x)),
                    max(0.06, min(0.94, y)),
                )

    def _project(self, node_id: str, canvas: QRectF) -> QPointF | None:
        pos = self.node_positions.get(node_id)
        if pos is None:
            return None
        return QPointF(canvas.left() + pos[0] * canvas.width(), canvas.top() + pos[1] * canvas.height())

    def _relation_color(self, relation: str) -> QColor:
        relation = relation.lower()
        if relation == "calls":
            return QColor("#5BC8FF")
        if relation in {"uses", "imports_from"}:
            return QColor("#73D18B")
        if relation == "contains":
            return QColor("#7DD3FC")
        if relation == "inherits":
            return QColor("#A78BFA")
        if relation == "method":
            return QColor("#F472B6")
        return QColor(SWARM_EDGE_SUBTLE)

    def _nearest_node_id(self, point: QPoint) -> str:
        best_id = ""
        best_distance = 999999.0
        for node_id, node_point in self._screen_positions.items():
            dx = node_point.x() - point.x()
            dy = node_point.y() - point.y()
            distance = math.sqrt(dx * dx + dy * dy)
            if distance < best_distance:
                best_distance = distance
                best_id = node_id
        return best_id if best_distance <= 16.0 else ""

    def _node_by_id(self, node_id: str) -> dict[str, Any] | None:
        for node in self.sample_nodes:
            if str(node.get("id", "")) == node_id:
                return node
        return None

    def _score_node(self, node_id: str, node: dict[str, Any]) -> int:
        text = self._node_text(node_id, node)
        score = int(self.node_degrees.get(node_id, 0))
        weighted_terms = [
            ("tools_engel_super_swarm_hive_3d_scaffold", 240),
            ("super_swarm", 210),
            ("hive", 170),
            ("graphify", 160),
            ("knowledge_graph", 155),
            ("engel_ai_update_routes", 145),
            ("route", 115),
            ("desktop", 95),
            ("screen", 90),
            ("trusted_memory", 160),
            ("long_term_memory", 150),
            ("approved_memory", 132),
            ("memory_context", 124),
            ("memory", 92),
            ("receipt", 74),
            ("report", 68),
            ("worker", 68),
            ("model", 60),
            ("llm", 60),
            ("verify", 58),
            ("guard", 56),
            ("bridge", 48),
            ("runner", 42),
        ]
        for term, weight in weighted_terms:
            if term in text:
                score += weight
        return score

    def _group_for_node(self, node: dict[str, Any]) -> str:
        node_id = str(node.get("id", ""))
        text = self._node_text(node_id, node)
        if "graphify" in text or "knowledge_graph" in text:
            return "Graphify"
        if "route" in text or "engel_ai_update_routes" in text:
            return "Routes"
        if "desktop" in text or "screen" in text or "ui_" in text or "mainwindow" in text:
            return "UI Screens"
        if (
            "trusted_memory" in text
            or "long_term_memory" in text
            or "approved_memory" in text
            or "memory_context" in text
            or "engel_memory" in text
            or "memory/" in text
        ):
            return "Long Term Memory"
        if "report" in text or "receipt" in text or "codex_bridge" in text:
            return "Reports Receipts"
        if "memory" in text:
            return "Long Term Memory"
        if "worker" in text or "remote" in text or "lan_" in text:
            return "Workers"
        if "model" in text or "llm" in text or "lfm2" in text or "runtime" in text:
            return "Models Runtime"
        if "verify" in text or "test_" in text or "scanner" in text or "guard" in text:
            return "Verifiers Tools"
        if "external" in text or "main/" in text or "vendored" in text:
            return "Vendored Modules"
        return "Core"

    @staticmethod
    def _node_text(node_id: str, node: dict[str, Any]) -> str:
        return " ".join(
            str(node.get(key, "")) for key in ("id", "label", "source_file", "file_type")
        ).lower().replace("\\", "/") + " " + node_id.lower()

    @staticmethod
    def _short_label(value: str) -> str:
        clean = value.replace("\\", "/").split("/")[-1].replace("_", " ")
        if len(clean) > 32:
            return clean[:29] + "..."
        return clean


class GraphifyKnowledgeMapTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.map_widget = GraphifyKnowledgeMapWidget()
        self.details = QTextEdit()
        self.details.setReadOnly(True)
        self.details.setMinimumHeight(112)
        self.details.setMaximumHeight(156)
        self.details.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.details.setStyleSheet(text_box_style())
        self.selection_status = QLabel()
        self.selection_status.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.selection_status.setStyleSheet(
            f"color:{SWARM_TEXT_SECONDARY}; font-family:Consolas,monospace; font-size:8pt;"
            " background:transparent; border:0;"
        )
        self.metric_cards: dict[str, QFrame] = {}
        self.map_widget.selection_changed.connect(self._refresh_details)
        self._build()
        self.reload_graph()

    def reload_graph(self) -> None:
        self.map_widget.reload_graph()
        self._refresh_metrics()
        self._refresh_details(self.map_widget.selected_node_id)

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)

        title_row = QHBoxLayout()
        title_row.addWidget(label("GRAPHIFY KNOWLEDGE MAP", 12, 900, SWARM_ACCENT_INFO))
        title_row.addWidget(self.selection_status, 1)
        title_row.addWidget(pill("MERGED INTO SUPER SWARM", SWARM_ACCENT_SAFE))
        title_row.addWidget(pill("LOCAL JSON", SWARM_ACCENT_INFO))
        title_row.addWidget(pill("READ ONLY", SWARM_BADGE_WARNING))
        reload_button = QPushButton("RELOAD")
        reload_button.setMinimumHeight(26)
        reload_button.clicked.connect(self.reload_graph)
        title_row.addWidget(reload_button)
        outer.addLayout(title_row)

        outer.addWidget(self._build_metric_strip())

        outer.addWidget(self.map_widget, 1)

    def _build_metric_strip(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setMinimumHeight(52)
        scroll.setMaximumHeight(56)
        host = QWidget()
        row = QHBoxLayout(host)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        for title, color in [
            ("GRAPH NODES", SWARM_ACCENT_INFO),
            ("GRAPH LINKS", SWARM_ACCENT_SAFE),
            ("MAP SAMPLE", "#F472B6"),
            ("MAP CONNECTS", SWARM_BADGE_WARNING),
            ("LONG TERM MEMORY", "#E6C96A"),
        ]:
            card = summary_card(title, "0", "Graphify local output", color)
            card.setMinimumWidth(176)
            card.setMaximumHeight(50)
            self.metric_cards[title] = card
            row.addWidget(card)
        scroll.setWidget(host)
        return scroll

    def _refresh_metrics(self) -> None:
        values = {
            "GRAPH NODES": f"{self.map_widget.full_node_count:,}",
            "GRAPH LINKS": f"{self.map_widget.full_link_count:,}",
            "MAP SAMPLE": f"{len(self.map_widget.sample_nodes):,}",
            "MAP CONNECTS": f"{len(self.map_widget.sample_links):,}",
            "LONG TERM MEMORY": str(self.map_widget.group_counts.get("Long Term Memory", 0)),
        }
        for title, value in values.items():
            card = self.metric_cards.get(title)
            if card is not None and hasattr(card, "value_label"):
                card.value_label.setText(value)  # type: ignore[attr-defined]

    def _refresh_details(self, _node_id: str) -> None:
        summary = self.map_widget.summary_text()
        self.details.setPlainText(summary)
        self.selection_status.setToolTip(summary)
        if self.map_widget.error_message:
            self.selection_status.setText(self.map_widget.error_message)
            return
        node = self.map_widget._node_by_id(self.map_widget.selected_node_id)
        if node is None:
            self.selection_status.setText(
                f"{self.map_widget.full_node_count:,} nodes / {self.map_widget.full_link_count:,} links"
            )
            return
        node_id = str(node.get("id", ""))
        label_text = self.map_widget._short_label(str(node.get("label") or node_id))
        group = self.map_widget.node_groups.get(node_id, "Core")
        degree = self.map_widget.node_degrees.get(node_id, 0)
        connects = len(self.map_widget.node_adjacency.get(node_id, set()))
        self.selection_status.setText(
            f"{label_text} | {group} | degree {degree} | connects {connects} | "
            f"{self.map_widget.full_node_count:,} nodes / {self.map_widget.full_link_count:,} links"
        )


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.data_manager = DataManager()
        self.setWindowTitle(APP_TITLE)
        self.resize(1440, 860)
        self.setMinimumSize(1100, 680)
        self.setStyleSheet(global_stylesheet())

        self.swarm_map = SuperSwarmMap3DWidget(self.data_manager)
        self.swarm_map.colony_selected.connect(self._select_colony)
        self.graphify_map_tab = GraphifyKnowledgeMapTab()
        self.data_manager.data_updated.connect(self._refresh_lower_panels)
        self.data_manager.selection_requested.connect(self._select_colony)
        self.data_manager.section_focus_requested.connect(self._focus_local_section)
        self.selected_colony_id = next(iter(self.data_manager.colonies), self.data_manager.communication_queen_id)
        self.data_manager.selected_entity_id = self.selected_colony_id
        self.focus_section = "hive_overview"
        self.selected_details = QTextEdit()
        self.selected_details.setReadOnly(True)
        self.selected_details.setStyleSheet(text_box_style())
        self.signal_map = QTextEdit()
        self.signal_map.setReadOnly(True)
        self.signal_map.setStyleSheet(text_box_style())
        self.telemetry_store = QTextEdit()
        self.telemetry_store.setReadOnly(True)
        self.telemetry_store.setStyleSheet(text_box_style())
        self.activity_feed = QTextEdit()
        self.activity_feed.setReadOnly(True)
        self.activity_feed.setStyleSheet(text_box_style())
        self.proposal_lanes = QTextEdit()
        self.proposal_lanes.setReadOnly(True)
        self.proposal_lanes.setStyleSheet(text_box_style())
        self.status_time = QLabel()
        self.footer_status = QLabel()
        self.summary_card_widgets: dict[str, QFrame] = {}

        self.setCentralWidget(self._build_central())
        self._build_engel_dock()
        self._sync_graphify_workspace_mode()
        self.swarm_map.fit_to_data()
        self._refresh_lower_panels()

        self.clock_timer = QTimer(self)
        self.clock_timer.setInterval(1000)
        self.clock_timer.timeout.connect(self._tick_clock)
        self.clock_timer.start()
        self._tick_clock()

    def _build_central(self) -> QWidget:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(7)
        layout.addLayout(self._build_header())
        layout.addWidget(self._build_safety_banner())

        self.tabs = QTabWidget()
        self.tabs.addTab(SingleColonyHiveTab(self.data_manager), "Colony Hive")
        self.tabs.addTab(self._build_super_swarm_tab(), "Super Swarm Hive")
        self.tabs.addTab(ColoniesTab(self.data_manager), "Colonies")
        self.tabs.addTab(QueensTab(self.data_manager), "Queens")
        self.tabs.addTab(ConnectionsTab(self.data_manager), "Connections")
        self.tabs.addTab(CommunicationTab(self.data_manager), "Communication Queen")
        self.tabs.addTab(ExpansionTab(self.data_manager), "Expansion")
        self.tabs.addTab(PermissionsTab(self.data_manager), "Engel Permissions")
        self.tabs.setCurrentIndex(0)
        self.tabs.tabBar().setUsesScrollButtons(True)
        self.tabs.tabBar().setElideMode(Qt.TextElideMode.ElideRight)
        for index in range(self.tabs.count()):
            self.tabs.setTabToolTip(index, self.tabs.tabText(index))
        self.tabs.currentChanged.connect(self._sync_active_tab_badge)
        self.tabs.currentChanged.connect(self._sync_graphify_workspace_mode)
        layout.addWidget(self.tabs, 1)
        layout.addWidget(self._build_footer())
        self._sync_active_tab_badge(self.tabs.currentIndex())
        return root

    def _build_header(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)
        mark = QLabel("E")
        mark.setFixedSize(48, 48)
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark.setStyleSheet(
            f"color:{SWARM_ACCENT_SAFE}; font-size:22px; font-weight:900; font-family:Consolas,monospace;"
            f" border:1px solid {SWARM_BORDER_SUBTLE}; border-radius:6px;"
            f" background:{SWARM_BG_CARD};"
        )
        row.addWidget(mark)

        copy = QVBoxLayout()
        copy.setSpacing(2)
        copy.addWidget(label(DISPLAY_TITLE, 13, 900, SWARM_ACCENT_SAFE))
        copy.addWidget(
            label(
                "Local Hive — colonies, queens, signals, Guardian-gated paths. Read-only.",
                9,
                400,
                SWARM_TEXT_MUTED,
            )
        )
        row.addLayout(copy, 1)

        badge_col = QVBoxLayout()
        badge_col.setSpacing(3)
        badge_row_1 = QHBoxLayout()
        badge_row_1.setSpacing(4)
        badge_row_2 = QHBoxLayout()
        badge_row_2.setSpacing(4)
        for widget in [
            pill("GUARDIAN", SWARM_ACCENT_SAFE),
            pill("LOCAL ONLY", SWARM_ACCENT_INFO),
            pill("HUMAN CMD", SWARM_ACCENT_INFO),
        ]:
            badge_row_1.addWidget(widget)
        for widget in [
            pill("PROVIDER OFF", SWARM_BADGE_WARNING),
            pill("AUTONOMY BLOCKED", SWARM_BADGE_BLOCKED),
        ]:
            badge_row_2.addWidget(widget)
        badge_col.addLayout(badge_row_1)
        badge_col.addLayout(badge_row_2)
        row.addLayout(badge_col)

        refresh = QPushButton("Refresh")
        refresh.setToolTip("Reloads the true local Research Office/Hive snapshot.")
        refresh.clicked.connect(self._refresh_local_signals)
        row.addWidget(refresh)
        return row

    def _build_safety_banner(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("SafetyBanner")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(10, 6, 10, 6)
        icon = QLabel("G")
        icon.setFixedWidth(36)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet(f"font-size:18px; font-weight:900; color:{SWARM_ACCENT_SAFE}; background:transparent; border:0; font-family:Consolas,monospace;")
        layout.addWidget(icon)
        copy = QVBoxLayout()
        copy.setSpacing(2)
        copy.addWidget(label("GUARDIAN SAFETY LAYER — local view only, no network, no mutation", 9, 700, "#00ff88"))
        copy.addWidget(
            label(
                "No external calls · No provider · No memory write · No background worker · Human approval required for all actions.",
                8,
                400,
                SWARM_TEXT_MUTED,
            )
        )
        layout.addLayout(copy, 1)
        badges = QHBoxLayout()
        badges.setSpacing(4)
        badges.addWidget(pill("LOCAL ONLY", SWARM_ACCENT_SAFE))
        badges.addWidget(pill("PROVIDER OFF", SWARM_BADGE_WARNING))
        badges.addWidget(pill("NO MUTATION", SWARM_BADGE_BLOCKED))
        layout.addLayout(badges)
        return frame

    def _build_super_swarm_tab(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(10)

        title_row = QHBoxLayout()
        title_row.addWidget(label("SUPER SWARM HIVE", 12, 900, SWARM_ACCENT_SAFE), 1)
        for text, callback in [
            ("RESET", self.swarm_map.reset_camera),
            ("FIT", self.swarm_map.fit_to_data),
            ("FOCUS", self._focus_selected),
        ]:
            button = QPushButton(text)
            button.setMinimumHeight(26)
            button.setMinimumWidth(64)
            button.clicked.connect(callback)
            title_row.addWidget(button)
        title_row.addWidget(pill(self.data_manager.local_status_label(), SWARM_ACCENT_SAFE))
        title_row.addWidget(pill("GRAPHIFY MAP MERGED", "#F472B6"))
        outer.addLayout(title_row)

        self.super_swarm_inner_tabs = QTabWidget()
        self.super_swarm_inner_tabs.addTab(self._build_super_swarm_3d_page(), "3D Hive")
        self.super_swarm_inner_tabs.addTab(self.graphify_map_tab, "Graphify Map")
        self.super_swarm_inner_tabs.tabBar().setUsesScrollButtons(True)
        for index in range(self.super_swarm_inner_tabs.count()):
            self.super_swarm_inner_tabs.setTabToolTip(index, self.super_swarm_inner_tabs.tabText(index))
        self.super_swarm_inner_tabs.currentChanged.connect(self._sync_graphify_workspace_mode)
        outer.addWidget(self.super_swarm_inner_tabs, 1)
        return page

    def _build_super_swarm_3d_page(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(10)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_left_controls())
        splitter.addWidget(self.swarm_map)
        splitter.setSizes([170, 1130])
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        outer.addWidget(splitter, 1)

        outer.addWidget(self._build_summary_cards())
        outer.addWidget(self._build_lower_panels())
        return page

    def _build_left_controls(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(150)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        panel = QFrame()
        panel.setObjectName("Panel")
        panel.setMinimumWidth(140)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        layout.addWidget(label("LEGEND", 11, 900, SWARM_TEXT_PRIMARY))
        for name, color in [
            ("Queen", SWARM_ACCENT_INFO),
            ("Nest", SWARM_ACCENT_INFO),
            ("Worker Cell", "#7dd3fc"),
            ("Signal", "#4ade80"),
            ("Growth Path", "#a855f7"),
            ("Guardian", SWARM_ACCENT_SAFE),
        ]:
            layout.addWidget(legend_item(name, color))

        layer_group = QGroupBox("LAYER TOGGLES")
        layer_layout = QVBoxLayout(layer_group)
        for key, text in [
            ("workers", "Worker Cells"),
            ("queens", "Queens"),
            ("colony_links", "Local Record Links"),
            ("inter_colony", "Read-Only Signals"),
            ("remote_queens", "Remote Registry"),
            ("growth_paths", "Growth Paths"),
            ("guardian", "Guardian Layer"),
        ]:
            checkbox = QCheckBox(text)
            checkbox.setChecked(True)
            checkbox.toggled.connect(lambda checked, layer=key: self.swarm_map.set_layer_enabled(layer, checked))
            layer_layout.addWidget(checkbox)
        layout.addWidget(layer_group)

        label_options = QGroupBox("LABEL READABILITY")
        label_layout = QVBoxLayout(label_options)
        readable = QCheckBox("Readable Labels")
        readable.setChecked(True)
        readable.toggled.connect(self.swarm_map.set_readable_labels)
        minor = QCheckBox("Show Minor Labels")
        minor.setChecked(False)
        minor.toggled.connect(self.swarm_map.set_minor_labels)
        label_layout.addWidget(readable)
        label_layout.addWidget(minor)
        layout.addWidget(label_options)

        layout.addWidget(label("VIEW PRESETS", 9, 900, SWARM_TEXT_PRIMARY))
        for text in ("Overview", "Communication Queen", "Signal Flow"):
            button = QPushButton(text)
            button.clicked.connect(lambda checked=False, label_text=text: self._set_view_preset(label_text))
            layout.addWidget(button)
        layout.addStretch(1)
        scroll.setWidget(panel)
        return scroll

    def _build_summary_cards(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setMinimumHeight(56)
        host = QWidget()
        row = QHBoxLayout(host)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        metrics = self.data_manager.metrics()
        cards = [
            ("LOCAL COLONIES", str(metrics["colonies"]), "Snapshot records", SWARM_ACCENT_INFO),
            ("TOTAL NESTS", str(metrics["nests"]), "Snapshot records", SWARM_ACCENT_INFO),
            ("WORKER EVENTS", str(metrics["worker_events"]), "True local event store", SWARM_ACCENT_SAFE),
            ("REMOTE QUEENS", str(metrics["remote_queens"]), "Registered devices", "#5eead4"),
            ("COMMUNICATION QUEEN", str(metrics["communication_nodes"]), "Local contract", SWARM_ACCENT_SAFE),
            ("GROWTH PATHS", str(metrics["growth_paths"]), "True local store", SWARM_BADGE_WARNING),
            ("TELEMETRY EVENTS", str(metrics["telemetry_events"]), "True local store", SWARM_ACCENT_INFO),
            ("LOCAL READINESS", f"{metrics['local_readiness']}%", "Linked artifacts", SWARM_ACCENT_SAFE),
        ]
        for title, value, detail, color in cards:
            card = summary_card(title, value, detail, color)
            card.setMinimumWidth(176)
            self.summary_card_widgets[title] = card
            row.addWidget(card)
        scroll.setWidget(host)
        return scroll

    def _refresh_summary_cards(self) -> None:
        metrics = self.data_manager.metrics()
        values = {
            "LOCAL COLONIES": str(metrics["colonies"]),
            "TOTAL NESTS": str(metrics["nests"]),
            "WORKER EVENTS": str(metrics["worker_events"]),
            "REMOTE QUEENS": str(metrics["remote_queens"]),
            "COMMUNICATION QUEEN": str(metrics["communication_nodes"]),
            "GROWTH PATHS": str(metrics["growth_paths"]),
            "TELEMETRY EVENTS": str(metrics["telemetry_events"]),
            "LOCAL READINESS": f"{metrics['local_readiness']}%",
        }
        for title, value in values.items():
            card = self.summary_card_widgets.get(title)
            if card is not None and hasattr(card, "value_label"):
                card.value_label.setText(value)  # type: ignore[attr-defined]

    def _build_lower_panels(self) -> QWidget:
        panel = QSplitter(Qt.Orientation.Horizontal)
        panel.setChildrenCollapsible(False)
        panel.setMinimumHeight(182)
        for widget in [
            self.selected_details,
            self.signal_map,
            self.activity_feed,
            self.telemetry_store,
            self.proposal_lanes,
        ]:
            widget.setMinimumHeight(116)
            widget.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        panel.addWidget(detail_panel("SELECTED", self.selected_details))
        panel.addWidget(detail_panel("SIGNALS", self.signal_map))
        panel.addWidget(detail_panel("ACTIVITY", self.activity_feed))
        panel.setSizes([320, 320, 320])
        self.lower_panel = panel
        host = QScrollArea()
        host.setWidgetResizable(True)
        host.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        host.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        wrap = QWidget()
        wrap_layout = QVBoxLayout(wrap)
        wrap_layout.setContentsMargins(0, 0, 0, 0)
        wrap_layout.setSpacing(0)
        wrap_layout.addWidget(panel)
        host.setWidget(wrap)
        return host

    def _build_static_tab(self, title: str, subtitle: str) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)
        layout.addWidget(label(title, 19, 900, SWARM_TEXT_PRIMARY))
        layout.addWidget(label(subtitle, 10, 700, SWARM_TEXT_SECONDARY))
        grid = QGridLayout()
        items = [
            ("Local Scope", "No network or provider path"),
            ("Guardian Gate", "Human approval above action gates"),
            ("Proposal Only", "Suggestions do not apply themselves"),
            ("Visibility", "All future integration points stay inspectable"),
        ]
        colors = [SWARM_ACCENT_INFO, SWARM_ACCENT_SAFE, SWARM_BADGE_WARNING, SWARM_ACCENT_INFO]
        for index, (name, detail) in enumerate(items):
            grid.addWidget(summary_card(name, "SAFE", detail, colors[index]), index // 2, index % 2)
        layout.addLayout(grid)
        layout.addStretch(1)
        return page

    def _build_footer(self) -> QFrame:
        footer = QFrame()
        footer.setObjectName("Footer")
        footer.setMaximumHeight(26)
        row = QHBoxLayout(footer)
        row.setContentsMargins(12, 2, 12, 2)
        row.setSpacing(10)
        self.status_time.setStyleSheet(f"color:{SWARM_TEXT_SECONDARY}; font-size:9pt; font-weight:700;")
        row.addWidget(self.status_time)
        row.addStretch(1)
        self.footer_status.setStyleSheet(f"color:{SWARM_ACCENT_SAFE}; font-size:9pt; font-weight:800;")
        row.addWidget(self.footer_status)
        # active_tab_badge and record_counts_badge kept as hidden labels so
        # existing _update_* / _sync_active_tab_badge calls remain safe.
        self.active_tab_badge = QLabel()
        self.active_tab_badge.setVisible(False)
        self.record_counts_badge = QLabel()
        self.record_counts_badge.setVisible(False)
        return footer

    def _build_active_tab_badge(self) -> QLabel:
        self.active_tab_badge = pill("TAB COLONY HIVE", "#44aaff")
        return self.active_tab_badge

    def _build_record_counts_badge(self) -> QLabel:
        self.record_counts_badge = pill("RECORDS C0 N0 Q0 W0", "#5eead4")
        self.record_counts_badge.setToolTip(
            "True local records: colonies, nests, queens, and worker events. Empty stores stay zero."
        )
        return self.record_counts_badge

    def _sync_active_tab_badge(self, index: int) -> None:
        if not hasattr(self, "active_tab_badge") or not hasattr(self, "tabs"):
            return
        tab_name = self.tabs.tabText(index) if index >= 0 else "Unknown"
        self.active_tab_badge.setText("TAB " + tab_name.upper())

    def _sync_graphify_workspace_mode(self, *_args: Any) -> None:
        dock = getattr(self, "engel_dock", None)
        tabs = getattr(self, "tabs", None)
        inner_tabs = getattr(self, "super_swarm_inner_tabs", None)
        if dock is None or tabs is None or inner_tabs is None:
            return
        on_super_swarm = tabs.tabText(tabs.currentIndex()) == "Super Swarm Hive"
        on_graphify = inner_tabs.tabText(inner_tabs.currentIndex()) == "Graphify Map"
        dock.setVisible(not (on_super_swarm and on_graphify))

    def _build_engel_dock(self) -> None:
        dock = QDockWidget("ENGEL Panel", self)
        dock.setObjectName("EngelDock")
        dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)
        dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable)
        dock.setMinimumWidth(360)
        dock.setMaximumWidth(520)
        self.engel_panel = ENGELPanel(self.data_manager)
        dock.setWidget(self.engel_panel)
        self.engel_dock = dock
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)

    def _set_view_preset(self, preset: str) -> None:
        if preset == "Overview":
            self.swarm_map.rotation_x = -72.0
            self.swarm_map.rotation_z = 0.0
            self.swarm_map.zoom = 18.0
        elif preset == "Communication Queen":
            self.swarm_map.rotation_x = -54.0
            self.swarm_map.rotation_z = -10.0
            self.swarm_map.zoom = 14.0
        elif preset == "Signal Flow":
            self.swarm_map.rotation_x = -50.0
            self.swarm_map.rotation_z = 28.0
            self.swarm_map.zoom = 16.0
        else:
            self.swarm_map.reset_camera()
        self.swarm_map.update()

    def _refresh_local_signals(self) -> None:
        self.data_manager.refresh_local_view()
        self.swarm_map.fit_to_data()
        self._refresh_lower_panels()

    def _select_colony(self, colony_id: str) -> None:
        self.selected_colony_id = colony_id
        self.data_manager.selected_entity_id = colony_id
        self.focus_section = "selection"
        self.swarm_map.selected_colony_id = colony_id
        self.swarm_map.update()
        self._refresh_lower_panels()

    def _focus_selected(self) -> None:
        self.focus_section = "selection"
        if hasattr(self, "tabs"):
            self.tabs.setCurrentIndex(0)
        if self.selected_colony_id:
            self.swarm_map.selected_colony_id = self.selected_colony_id
            self.data_manager.selected_entity_id = self.selected_colony_id
        self.swarm_map.update()
        self._refresh_lower_panels()

    def _focus_local_section(self, section: str) -> None:
        self.focus_section = section
        if hasattr(self, "tabs"):
            self.tabs.setCurrentIndex(1)
        if section == "communication_queen":
            self.selected_colony_id = self.data_manager.communication_queen_id
            self.swarm_map.selected_colony_id = self.selected_colony_id
            self.data_manager.selected_entity_id = self.selected_colony_id
        self._refresh_lower_panels()

    def focus_local_section(self, section: str) -> None:
        self._focus_local_section(section)

    def _refresh_lower_panels(self) -> None:
        self._refresh_summary_cards()
        if self.focus_section in {
            "hive_overview",
            "communication_queen",
            "remote_queens",
            "growth_paths",
            "signal_analyzer",
            "telemetry_events",
            "activity_sources",
            "worker_events",
            "research",
            "think",
        }:
            self.selected_details.setText(self.data_manager.section_detail(self.focus_section, self.selected_colony_id))
        else:
            if self.selected_colony_id not in self.data_manager.nodes and self.selected_colony_id not in self.data_manager.colonies:
                self.selected_colony_id = next(iter(self.data_manager.colonies), "")
            self.selected_details.setText(self.data_manager.selected_detail_text(self.selected_colony_id))
        self.signal_map.setText(self.data_manager.signal_analyzer_text())
        self.telemetry_store.setText(self.data_manager.telemetry_store_text())
        self.activity_feed.setText(self.data_manager.activity_text())
        self.proposal_lanes.setText(self.data_manager.proposal_lanes_text())
        if hasattr(self, "engel_panel"):
            self.engel_panel.sync_selection(self.selected_colony_id)
        if hasattr(self, "footer_status"):
            metrics = self.data_manager.metrics()
            focus = self.focus_section.replace("_", " ").upper()
            self.footer_status.setText(f"READINESS {metrics['local_readiness']}% | FOCUS {focus}")
            self.footer_status.setToolTip("Readiness and focus are derived from the true local Super Swarm view model.")
        if hasattr(self, "record_counts_badge"):
            metrics = self.data_manager.metrics()
            self.record_counts_badge.setText(
                "RECORDS "
                f"C{metrics['colonies']} "
                f"N{metrics['nests']} "
                f"Q{metrics['queens']} "
                f"W{metrics['worker_events']}"
            )

    def _tick_clock(self) -> None:
        self.status_time.setText(f"{SESSION_ID}  {time.strftime('%H:%M:%S', time.localtime())}")

    def _shutdown_owned_resources(self) -> None:
        try:
            if hasattr(self, "clock_timer") and self.clock_timer is not None:
                self.clock_timer.stop()
        except Exception:
            pass

        try:
            if hasattr(self, "swarm_map") and self.swarm_map is not None:
                timer = getattr(self.swarm_map, "animation_timer", None)
                if timer is not None:
                    timer.stop()
        except Exception:
            pass

        try:
            if hasattr(self, "engel_dock") and self.engel_dock is not None:
                self.engel_dock.close()
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

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._shutdown_owned_resources()
        event.accept()
        app = QApplication.instance()
        if app is not None:
            QTimer.singleShot(0, app.quit)
        super().closeEvent(event)


def interpolate_polyline(points: list[Point3], progress: float, lane_offset: float, phase: float) -> Point3:
    if len(points) == 1:
        return points[0]
    segment_float = (progress % 1.0) * (len(points) - 1)
    index = min(len(points) - 2, int(segment_float))
    local = segment_float - index
    a = points[index]
    b = points[index + 1]
    x = a[0] * (1.0 - local) + b[0] * local
    y = a[1] * (1.0 - local) + b[1] * local
    z = a[2] * (1.0 - local) + b[2] * local
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    length = math.hypot(dx, dy) or 1.0
    nx = -dy / length
    ny = dx / length
    bob = math.sin(phase) * 0.035
    return (x + nx * lane_offset, y + ny * lane_offset, z + bob)


def to_point3(value: Any) -> Point3:
    if isinstance(value, dict):
        return (float(value.get("x", 0.0)), float(value.get("y", 0.0)), float(value.get("z", 0.0)))
    return (float(value[0]), float(value[1]), float(value[2] if len(value) > 2 else 0.0))


def to_color(value: Any) -> ColorTuple:
    if isinstance(value, dict):
        return (
            float(value.get("r", 0.0)),
            float(value.get("g", 0.8)),
            float(value.get("b", 1.0)),
            float(value.get("a", 1.0)),
        )
    alpha = float(value[3]) if len(value) > 3 else 1.0
    return (float(value[0]), float(value[1]), float(value[2]), alpha)


def label(text: str, size: int = 9, weight: int = 600, color: str = "#cccccc") -> QLabel:
    item = QLabel(text)
    item.setWordWrap(True)
    item.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    item.setStyleSheet(f"color:{color}; background:transparent; border:0; font-family:Consolas,'Courier New',monospace;")
    font = QFont("Consolas", size)
    font.setWeight(QFont.Weight(weight))
    item.setFont(font)
    return item


def center_label(text: str, size: int, weight: int, color: str) -> QLabel:
    item = label(text, size, weight, color)
    item.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return item


def pill(text: str, color: str) -> QLabel:
    item = label(text, 8, 900, color)
    item.setAlignment(Qt.AlignmentFlag.AlignCenter)
    item.setMinimumHeight(22)
    item.setStyleSheet(
        f"color:{color}; background:{SWARM_BG_CARD}; border:1px solid {SWARM_BORDER_SUBTLE}; "
        "border-radius:6px; padding:2px 7px; font-family:Consolas,monospace;"
    )
    return item


def make_badge_row(items: list[tuple[str, str]]) -> QWidget:
    host = QWidget()
    row = QHBoxLayout(host)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(7)
    for text, color in items:
        row.addWidget(pill(text, color))
    row.addStretch(1)
    return host


def make_scroll_text(title: str, text: str, min_height: int = 190) -> QFrame:
    frame = QFrame()
    frame.setObjectName("Panel")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(9, 8, 9, 9)
    layout.setSpacing(5)
    layout.addWidget(label(title, 9, 900, SWARM_ACCENT_INFO))
    box = QTextEdit()
    box.setReadOnly(True)
    box.setMinimumHeight(min_height)
    box.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
    box.setStyleSheet(text_box_style())
    box.setPlainText(str(text))
    layout.addWidget(box, 1)
    return frame


def divider() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.VLine)
    line.setStyleSheet(f"color:{SWARM_BORDER_SUBTLE};")
    return line


def legend_item(name: str, color: str) -> QWidget:
    row = QWidget()
    row.setMinimumHeight(18)
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 1, 0, 1)
    layout.setSpacing(6)
    dot = QLabel("■")
    dot.setFixedWidth(14)
    dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
    dot.setStyleSheet(f"color:{color}; font-size:9px; font-weight:900; background:transparent; border:0; font-family:Consolas,monospace;")
    layout.addWidget(dot)
    layout.addWidget(label(name, 8, 600, SWARM_TEXT_PRIMARY), 1)
    return row


def summary_card(title: str, value: str, detail: str, color: str) -> QFrame:
    # `detail` arg kept for call-site compatibility but no longer rendered —
    # title + value alone is more scannable.
    card = QFrame()
    card.setObjectName("SummaryCard")
    card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    card.setMinimumHeight(48)
    card.setStyleSheet(
        f"QFrame#SummaryCard {{ background: {SWARM_BG_CARD}; border: 1px solid {SWARM_BORDER_SUBTLE}; border-radius: 6px; }}"
    )
    layout = QVBoxLayout(card)
    layout.setContentsMargins(8, 6, 8, 6)
    layout.setSpacing(2)
    title_label = label(title, 7, 700, SWARM_TEXT_MUTED)
    layout.addWidget(title_label)
    value_label = label(value, 16 if len(value) < 5 else 11, 900, color)
    value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(value_label)
    card.title_label = title_label  # type: ignore[attr-defined]
    card.value_label = value_label  # type: ignore[attr-defined]
    return card


def metric_cards(items: list[tuple[str, str, str, str]]) -> QHBoxLayout:
    row = QHBoxLayout()
    row.setSpacing(10)
    for title, value, detail, color in items:
        row.addWidget(summary_card(title, value, detail, color))
    return row


def mini_metric(title: str, value: str, color: str) -> QFrame:
    """Compact inline metric tile — big coloured value, tiny label beneath."""
    frame = QFrame()
    frame.setObjectName("MiniMetric")
    frame.setStyleSheet(
        f"QFrame#MiniMetric {{ background: {SWARM_BG_CARD}; border: 1px solid {SWARM_BORDER_SUBTLE}; border-radius: 6px; }}"
    )
    frame.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(8, 3, 8, 3)
    layout.setSpacing(0)
    val_lbl = label(value, 13, 900, color)
    val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    ttl_lbl = label(title, 7, 400, SWARM_TEXT_MUTED)
    ttl_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(val_lbl)
    layout.addWidget(ttl_lbl)
    frame.value_label = val_lbl   # type: ignore[attr-defined]
    frame.title_label = ttl_lbl  # type: ignore[attr-defined]
    return frame


def mini_metric_row(items: list[tuple[str, str, str]]) -> tuple[QWidget, dict]:
    """Row of mini_metric tiles + {title: frame} dict for later value updates."""
    host = QWidget()
    host.setMaximumHeight(56)
    row = QHBoxLayout(host)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(6)
    cards: dict = {}
    for title, value, color in items:
        m = mini_metric(title, value, color)
        row.addWidget(m)
        cards[title] = m
    row.addStretch(1)
    return host, cards


def configure_table(table: QTableWidget) -> None:
    table.setAlternatingRowColors(True)
    table.setSortingEnabled(True)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setFont(QFont("Consolas", 9, QFont.Weight.Medium))
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(26)
    table.horizontalHeader().setStretchLastSection(True)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    table.horizontalHeader().setMinimumHeight(30)
    table.setShowGrid(False)
    table.setMouseTracking(True)
    table.setWordWrap(False)
    table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)


def set_empty_table_row(table: QTableWidget, message: str) -> None:
    """Render one honest empty-state row without creating fake records."""
    was_sorting = table.isSortingEnabled()
    table.setSortingEnabled(False)
    table.setRowCount(0)
    table.setRowCount(1)
    for column in range(table.columnCount()):
        item = QTableWidgetItem(message if column == 0 else "")
        item.setForeground(QBrush(QColor(SWARM_TEXT_SECONDARY if column == 0 else SWARM_TEXT_MUTED)))
        item.setBackground(QBrush(QColor(SWARM_BG_PRIMARY)))
        item.setToolTip(message)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        if column == 0:
            font = item.font()
            font.setItalic(True)
            item.setFont(font)
        table.setItem(0, column, item)
    table.setSortingEnabled(was_sorting)


def button_stub(text: str) -> QPushButton:
    button = QPushButton(text)
    button.setMinimumHeight(28)
    return button


def action_pair(first: str, second: str, first_callback: Any | None = None, second_callback: Any | None = None) -> QWidget:
    host = QWidget()
    layout = QHBoxLayout(host)
    layout.setContentsMargins(6, 4, 6, 4)
    layout.setSpacing(7)
    first_button = button_stub(first)
    second_button = button_stub(second)
    if first_callback is not None:
        first_button.clicked.connect(first_callback)
    else:
        first_button.setEnabled(False)
        first_button.setToolTip("Disabled: no safe local action is implemented for this row.")
    if second_callback is not None:
        second_button.clicked.connect(second_callback)
    else:
        second_button.setEnabled(False)
        second_button.setToolTip("Disabled: informational row only.")
    layout.addWidget(first_button)
    layout.addWidget(second_button)
    return host


def info_panel(title: str, content: str) -> QTextEdit:
    box = QTextEdit()
    box.setReadOnly(True)
    box.setMinimumHeight(190)
    box.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
    box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    box.setText(f"{title}\n\n{content}")
    box.setStyleSheet(text_box_style())
    return box


def detail_panel(title: str, content_widget: QTextEdit) -> QFrame:
    frame = QFrame()
    frame.setObjectName("Panel")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(9, 8, 9, 9)
    layout.setSpacing(5)
    layout.addWidget(label(title, 9, 900, SWARM_ACCENT_INFO))
    layout.addWidget(content_widget, 1)
    return frame


def clear_layout(layout: QGridLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()


def tool_button(title: str, detail: str, badge: str) -> QFrame:
    frame = QFrame()
    frame.setStyleSheet(
        f"QFrame {{ border:1px solid {SWARM_BORDER_SUBTLE}; border-radius:6px; background:{SWARM_BG_CARD}; }}"
    )
    row = QHBoxLayout(frame)
    row.setContentsMargins(8, 5, 8, 5)
    copy = QVBoxLayout()
    copy.setSpacing(1)
    copy.addWidget(label(title, 9, 700, SWARM_ACCENT_INFO))
    copy.addWidget(label(detail, 8, 400, SWARM_TEXT_MUTED))
    row.addLayout(copy, 1)
    row.addWidget(label(badge, 8, 700, "#ffaa00"))
    return frame


def text_box_style() -> str:
    return f"""
        QTextEdit {{
            background: {SWARM_BG_PRIMARY};
            border: 1px solid {SWARM_BORDER_SUBTLE};
            border-radius: 6px;
            color: {SWARM_TEXT_PRIMARY};
            padding: 7px;
            font-family: Consolas, 'Courier New', monospace;
            font-size: 9pt;
            selection-background-color: #1A3A1A;
            selection-color: #ffffff;
        }}
    """


def global_stylesheet() -> str:
    return engel_ui_theme.super_swarm_application_stylesheet() + f"""
        QMainWindow, QWidget {{
            background: {SWARM_BG_PRIMARY};
            color: {SWARM_TEXT_PRIMARY};
        }}
        QPushButton {{
            background: {SWARM_BG_CARD};
            border: 1px solid {SWARM_BORDER_SUBTLE};
            border-radius: 6px;
            color: {SWARM_ACCENT_INFO};
            padding: 4px 9px;
            font-weight: 700;
            min-height: 24px;
        }}
        QPushButton:hover {{
            border-color: {SWARM_BORDER_FOCUS};
            color: #ffffff;
            background: {SWARM_BG_CARD_ALT};
        }}
        QPushButton:disabled {{
            background: {SWARM_BG_PANEL};
            border-color: {SWARM_BORDER_SUBTLE};
            color: {SWARM_BADGE_DISABLED};
        }}
        QToolButton {{
            background: {SWARM_BG_CARD};
            border: 1px solid {SWARM_BORDER_SUBTLE};
            border-radius: 6px;
            color: {SWARM_TEXT_PRIMARY};
        }}
        QTabWidget::pane {{
            border: 1px solid {SWARM_BORDER_SUBTLE};
            border-top: 0;
            background: {SWARM_BG_PANEL};
        }}
        QTabBar::tab {{
            background: {SWARM_BG_CARD};
            color: {SWARM_TEXT_MUTED};
            border: 1px solid {SWARM_BORDER_SUBTLE};
            border-bottom: 0;
            border-top-left-radius: 6px;
            border-top-right-radius: 6px;
            padding: 5px 10px;
        }}
        QTabBar::tab:selected {{
            background: {SWARM_BG_PANEL};
            color: {SWARM_ACCENT_SAFE};
            border-color: {SWARM_BORDER_FOCUS};
        }}
        QFrame#SafetyBanner {{
            background: {SWARM_BG_PANEL};
            border: 1px solid {SWARM_ACCENT_SAFE};
            border-radius: 6px;
        }}
        QFrame#Footer, QFrame#Panel, QFrame#CardPanel,
        QFrame#BottomPanel, QFrame#SidePanel {{
            background: {SWARM_BG_PANEL};
            border: 1px solid {SWARM_BORDER_SUBTLE};
            border-radius: 6px;
        }}
        QGroupBox {{
            border: 1px solid {SWARM_BORDER_SUBTLE};
            border-radius: 6px;
            margin-top: 10px;
            color: {SWARM_TEXT_MUTED};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 7px;
            padding: 0 4px;
            color: {SWARM_ACCENT_SAFE};
        }}
        QLineEdit, QComboBox {{
            background: {SWARM_BG_CARD};
            border: 1px solid {SWARM_BORDER_SUBTLE};
            border-radius: 6px;
            color: {SWARM_TEXT_PRIMARY};
            padding: 4px 7px;
        }}
        QTableWidget {{
            background: {SWARM_BG_PRIMARY};
            alternate-background-color: {SWARM_BG_PANEL};
            border: 1px solid {SWARM_BORDER_SUBTLE};
            border-radius: 6px;
            color: {SWARM_TEXT_PRIMARY};
            gridline-color: {SWARM_BORDER_SUBTLE};
        }}
        QHeaderView::section {{
            background: {SWARM_BG_CARD_ALT};
            color: {SWARM_ACCENT_SAFE};
            border: 0;
            border-right: 1px solid {SWARM_BORDER_SUBTLE};
            border-bottom: 1px solid {SWARM_BORDER_SUBTLE};
            padding: 5px 7px;
            font-weight: 700;
        }}
        QDockWidget::title {{
            background: {SWARM_BG_CARD_ALT};
            border: 1px solid {SWARM_BORDER_SUBTLE};
            padding: 5px 7px;
            font-weight: 700;
        }}
        QSplitter::handle:horizontal, QSplitter::handle:vertical {{
            background: {SWARM_BORDER_SUBTLE};
        }}
        QSplitter::handle:hover {{
            background: {SWARM_BORDER_FOCUS};
        }}
    """


def main() -> int:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    app.setApplicationName(APP_TITLE)
    app.setFont(QFont("Consolas", 9))
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
