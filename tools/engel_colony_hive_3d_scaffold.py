from __future__ import annotations

import csv
import json
import math
import random
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QPoint, Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDockWidget,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QToolBox,
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
        GL_ONE,
        GL_ONE_MINUS_SRC_ALPHA,
        GL_POINTS,
        GL_PROJECTION,
        GL_PROJECTION_MATRIX,
        GL_QUAD_STRIP,
        GL_SRC_ALPHA,
        GL_TRIANGLE_FAN,
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
        glScalef,
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


APP_TITLE = "ENGEL COLONY HIVE"
SESSION_ID = "HIVE-LOCAL-042"


ColorTuple = tuple[float, float, float, float]
Point3 = tuple[float, float, float]


@dataclass
class HiveNode:
    id: str
    label: str
    position: Point3
    kind: str = "nest"
    health: float = 1.0


@dataclass
class HiveTrail:
    id: str
    source: str
    target: str
    kind: str = "worker"
    active: bool = True
    points: list[Point3] = field(default_factory=list)


@dataclass
class HiveWorker:
    id: str
    trail_id: str
    speed: float
    progress: float
    phase: float
    lane_offset: float = 0.0


class DataManager(QObject):
    """Feeds validated local payloads into the visual hive.

    This class intentionally performs no network, provider, queue, memory, or
    background-worker activity. To connect future live data safely, pass an
    already-approved local JSON-like payload into apply_payload().
    """

    data_updated = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.nests: dict[str, HiveNode] = {}
        self.queens: dict[str, HiveNode] = {}
        self.trails: dict[str, HiveTrail] = {}
        self.workers: dict[str, HiveWorker] = {}
        self.last_update_label = "simulation ready"
        self.simulation_mode = True
        self._node_index: dict[str, HiveNode] = {}
        self.build_simulation_data()

    def all_nodes(self) -> list[HiveNode]:
        return list(self.nests.values()) + list(self.queens.values())

    def build_simulation_data(self) -> None:
        random.seed(42)
        self.nests.clear()
        self.queens.clear()
        self.trails.clear()
        self.workers.clear()

        nest_positions = [
            ("nest_1", "NEST 1", (-4.4, 1.9, 0.2)),
            ("nest_2", "NEST 2", (-2.2, 3.0, 0.0)),
            ("nest_3", "NEST 3", (0.7, 3.1, -0.15)),
            ("nest_4", "NEST 4", (3.0, 2.3, 0.1)),
            ("nest_5", "NEST 5", (4.6, 0.8, -0.05)),
            ("nest_6", "NEST 6", (3.5, -1.7, 0.15)),
            ("nest_7", "NEST 7", (0.9, -2.7, -0.05)),
            ("nest_8", "NEST 8", (-2.2, -2.4, 0.1)),
            ("nest_9", "NEST 9", (-4.5, -1.2, -0.1)),
        ]
        queen_positions = [
            ("queen_alpha", "Q1", (-2.7, 0.4, 0.55)),
            ("queen_beta", "Q2", (0.6, 0.1, 0.7)),
            ("queen_gamma", "Q3", (2.7, -0.1, 0.55)),
        ]
        for node_id, label, pos in nest_positions:
            self.nests[node_id] = HiveNode(node_id, label, pos, "nest")
        for node_id, label, pos in queen_positions:
            self.queens[node_id] = HiveNode(node_id, label, pos, "queen")

        self._reindex_nodes()
        trail_pairs = [
            ("trail_01", "nest_1", "queen_alpha"),
            ("trail_02", "nest_2", "queen_alpha"),
            ("trail_03", "nest_3", "queen_beta"),
            ("trail_04", "nest_4", "queen_beta"),
            ("trail_05", "nest_5", "queen_gamma"),
            ("trail_06", "nest_6", "queen_gamma"),
            ("trail_07", "nest_7", "queen_beta"),
            ("trail_08", "nest_8", "queen_alpha"),
            ("trail_09", "nest_9", "queen_alpha"),
            ("trail_10", "queen_alpha", "queen_beta"),
            ("trail_11", "queen_beta", "queen_gamma"),
            ("trail_12", "nest_2", "nest_4"),
            ("trail_13", "nest_8", "nest_6"),
            ("trail_14", "nest_1", "nest_9"),
            ("trail_15", "nest_5", "nest_3"),
        ]
        for index, (trail_id, source, target) in enumerate(trail_pairs):
            kind = "signal" if index in {9, 10, 11, 12} else "worker"
            points = self._curved_points(source, target, lift=0.35 + (index % 3) * 0.09)
            self.trails[trail_id] = HiveTrail(trail_id, source, target, kind, True, points)

        worker_count = 74
        worker_trails = [trail.id for trail in self.trails.values() if trail.kind == "worker"]
        for index in range(worker_count):
            trail_id = worker_trails[index % len(worker_trails)]
            self.workers[f"worker_{index + 1:03d}"] = HiveWorker(
                id=f"worker_{index + 1:03d}",
                trail_id=trail_id,
                speed=0.055 + random.random() * 0.08,
                progress=random.random(),
                phase=random.random() * math.tau,
                lane_offset=(random.random() - 0.5) * 0.1,
            )
        self.last_update_label = "placeholder simulation"
        self.simulation_mode = True
        self.data_updated.emit()

    def _reindex_nodes(self) -> None:
        self._node_index = {}
        self._node_index.update(self.nests)
        self._node_index.update(self.queens)

    def _curved_points(self, source_id: str, target_id: str, lift: float) -> list[Point3]:
        source = self._node_index[source_id].position
        target = self._node_index[target_id].position
        points: list[Point3] = []
        for step in range(28):
            t = step / 27.0
            wiggle = math.sin(t * math.pi) * lift
            side = math.sin(t * math.pi * 2.0) * 0.12
            x = source[0] * (1 - t) + target[0] * t + side
            y = source[1] * (1 - t) + target[1] * t - side * 0.4
            z = source[2] * (1 - t) + target[2] * t + wiggle
            points.append((x, y, z))
        return points

    def tick(self, dt_seconds: float) -> None:
        if not self.simulation_mode:
            return
        for worker in self.workers.values():
            worker.progress = (worker.progress + worker.speed * dt_seconds) % 1.0
            worker.phase = (worker.phase + dt_seconds * 2.1) % math.tau

    def worker_position(self, worker: HiveWorker) -> Point3:
        trail = self.trails.get(worker.trail_id)
        if not trail or len(trail.points) < 2:
            return (0.0, 0.0, 0.0)
        return interpolate_polyline(trail.points, worker.progress, worker.lane_offset, worker.phase)

    def apply_payload(self, payload: dict[str, Any]) -> None:
        """Replace the visual data with a local, already-authorized payload."""
        self.nests = {
            item["id"]: HiveNode(
                id=str(item["id"]),
                label=str(item.get("label", item["id"])),
                position=to_point3(item.get("position", [0, 0, 0])),
                kind="nest",
                health=float(item.get("health", 1.0)),
            )
            for item in payload.get("nests", [])
        }
        self.queens = {
            item["id"]: HiveNode(
                id=str(item["id"]),
                label=str(item.get("label", item["id"])),
                position=to_point3(item.get("position", [0, 0, 0])),
                kind="queen",
                health=float(item.get("health", 1.0)),
            )
            for item in payload.get("queens", [])
        }
        self._reindex_nodes()
        self.trails = {}
        for item in payload.get("trails", []):
            trail_id = str(item["id"])
            source = str(item["source"])
            target = str(item["target"])
            points = [to_point3(point) for point in item.get("points", [])]
            if not points and source in self._node_index and target in self._node_index:
                points = self._curved_points(source, target, 0.25)
            self.trails[trail_id] = HiveTrail(
                id=trail_id,
                source=source,
                target=target,
                kind=str(item.get("kind", "worker")),
                active=bool(item.get("active", True)),
                points=points,
            )
        self.workers = {}
        for item in payload.get("workers", []):
            worker_id = str(item["id"])
            self.workers[worker_id] = HiveWorker(
                id=worker_id,
                trail_id=str(item["trail_id"]),
                speed=float(item.get("speed", 0.08)),
                progress=float(item.get("progress", 0.0)) % 1.0,
                phase=float(item.get("phase", 0.0)),
                lane_offset=float(item.get("lane_offset", 0.0)),
            )
        self.last_update_label = "local payload loaded"
        self.simulation_mode = bool(payload.get("simulation_mode", True))
        self.data_updated.emit()

    def load_json_file(self, path: str | Path) -> None:
        with Path(path).open("r", encoding="utf-8") as handle:
            self.apply_payload(json.load(handle))

    def load_csv_file(self, path: str | Path) -> None:
        """Load a compact local CSV format.

        Supported rows:
        node,nest_id,Nest Label,x,y,z,nest
        node,queen_id,Q1,x,y,z,queen
        trail,trail_id,source_id,target_id,worker
        worker,worker_id,trail_id,speed,progress
        """
        payload: dict[str, list[dict[str, Any]]] = {
            "nests": [],
            "queens": [],
            "trails": [],
            "workers": [],
        }
        with Path(path).open("r", encoding="utf-8", newline="") as handle:
            for row in csv.reader(handle):
                if not row or row[0].strip().startswith("#"):
                    continue
                row_type = row[0].strip().lower()
                if row_type == "node" and len(row) >= 7:
                    item = {
                        "id": row[1].strip(),
                        "label": row[2].strip(),
                        "position": [float(row[3]), float(row[4]), float(row[5])],
                    }
                    if row[6].strip().lower() == "queen":
                        payload["queens"].append(item)
                    else:
                        payload["nests"].append(item)
                elif row_type == "trail" and len(row) >= 5:
                    payload["trails"].append(
                        {
                            "id": row[1].strip(),
                            "source": row[2].strip(),
                            "target": row[3].strip(),
                            "kind": row[4].strip() or "worker",
                        }
                    )
                elif row_type == "worker" and len(row) >= 5:
                    payload["workers"].append(
                        {
                            "id": row[1].strip(),
                            "trail_id": row[2].strip(),
                            "speed": float(row[3]),
                            "progress": float(row[4]),
                        }
                    )
        self.apply_payload(payload)


class HiveMap3DWidget(QOpenGLWidget):
    node_selected = pyqtSignal(str, str)

    def __init__(self, data_manager: DataManager) -> None:
        super().__init__()
        self.data_manager = data_manager
        self.layers = {
            "workers": True,
            "trails": True,
            "queens": True,
            "signals": True,
            "guardian": True,
        }
        self.rotation_x = -58.0
        self.rotation_z = 0.0
        self.zoom = 12.5
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.selected_node_id = ""
        self.last_mouse = QPoint()
        self._last_frame = time.perf_counter()
        self._projection: Any = None
        self._modelview: Any = None
        self._viewport: Any = None
        self._projected_nodes: dict[str, tuple[float, float]] = {}

        self.setMinimumHeight(520)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.data_manager.data_updated.connect(self.update)

        self.animation_timer = QTimer(self)
        self.animation_timer.setInterval(16)
        self.animation_timer.timeout.connect(self._animate_frame)
        self.animation_timer.start()

    def set_layer_enabled(self, layer: str, enabled: bool) -> None:
        if layer in self.layers:
            self.layers[layer] = enabled
            self.update()

    def reset_camera(self) -> None:
        self.rotation_x = -58.0
        self.rotation_z = 0.0
        self.zoom = 12.5
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.update()

    def zoom_in(self) -> None:
        self.zoom = max(6.5, self.zoom - 0.8)
        self.update()

    def zoom_out(self) -> None:
        self.zoom = min(22.0, self.zoom + 0.8)
        self.update()

    def initializeGL(self) -> None:
        if not OPENGL_READY:
            return
        glClearColor(0.006, 0.012, 0.03, 1.0)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glEnable(GL_LINE_SMOOTH)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glShadeModel(GL_SMOOTH)

    def resizeGL(self, width: int, height: int) -> None:
        if not OPENGL_READY:
            return
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
        gluPerspective(45.0, width / height, 0.1, 100.0)

        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        glTranslatef(self.pan_x, self.pan_y, -self.zoom)
        glRotatef(self.rotation_x, 1.0, 0.0, 0.0)
        glRotatef(self.rotation_z, 0.0, 0.0, 1.0)

        self._draw_starfield()
        self._draw_floor_grid()
        if self.layers["guardian"]:
            self._draw_guardian_halo()
        if self.layers["trails"]:
            self._draw_worker_trails()
        if self.layers["signals"]:
            self._draw_signal_trails()
        self._draw_nodes()
        if self.layers["workers"]:
            self._draw_workers()

        self._modelview = glGetDoublev(GL_MODELVIEW_MATRIX)
        self._projection = glGetDoublev(GL_PROJECTION_MATRIX)
        self._viewport = glGetIntegerv(GL_VIEWPORT)
        self._draw_overlay_labels()

    def _paint_fallback_message(self) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#030814"))
        painter.setPen(QColor("#35d6ff"))
        painter.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "PyOpenGL is required for the 3D hive map")
        painter.end()

    def _animate_frame(self) -> None:
        now = time.perf_counter()
        dt = min(0.05, now - self._last_frame)
        self._last_frame = now
        self.data_manager.tick(dt)
        self.update()

    def _draw_starfield(self) -> None:
        glPointSize(1.5)
        glBegin(GL_POINTS)
        for index in range(80):
            angle = index * 2.399
            radius = 3.0 + (index % 17) * 0.42
            x = math.cos(angle) * radius
            y = math.sin(angle) * radius * 0.62
            z = -1.2 - (index % 9) * 0.06
            glColor4f(0.12, 0.85, 1.0, 0.18)
            glVertex3f(x, y, z)
        glEnd()

    def _draw_floor_grid(self) -> None:
        glLineWidth(1.0)
        glBegin(GL_LINES)
        for line in range(-7, 8):
            alpha = 0.16 if line else 0.32
            glColor4f(0.0, 0.7, 0.85, alpha)
            glVertex3f(float(line), -4.2, -0.7)
            glVertex3f(float(line), 4.2, -0.7)
            glVertex3f(-6.2, float(line) * 0.6, -0.7)
            glVertex3f(6.2, float(line) * 0.6, -0.7)
        glEnd()

    def _draw_guardian_halo(self) -> None:
        t = time.perf_counter() * 1.4
        for ring, scale in enumerate([1.0, 1.045, 1.09]):
            glLineWidth(2.6 - ring * 0.55)
            glBegin(GL_LINES)
            for index in range(144):
                if index % 5 in {0, 1}:
                    continue
                a0 = index / 144.0 * math.tau
                a1 = (index + 0.72) / 144.0 * math.tau
                pulse = 0.55 + 0.45 * math.sin(a0 * 5.0 + t)
                glColor4f(0.52, 1.0, 0.16, (0.38 - ring * 0.08) * pulse)
                glVertex3f(math.cos(a0) * 6.0 * scale, math.sin(a0) * 3.65 * scale, -0.36)
                glVertex3f(math.cos(a1) * 6.0 * scale, math.sin(a1) * 3.65 * scale, -0.36)
            glEnd()

    def _draw_worker_trails(self) -> None:
        for trail in self.data_manager.trails.values():
            if trail.kind == "signal":
                continue
            self._draw_polyline(trail.points, (1.0, 0.58, 0.08, 0.92), width=2.0, glow=True)

    def _draw_signal_trails(self) -> None:
        for trail in self.data_manager.trails.values():
            if trail.kind != "signal":
                continue
            self._draw_dotted_polyline(trail.points, (0.0, 0.72, 1.0, 0.9), width=2.2)

    def _draw_polyline(self, points: list[Point3], color: ColorTuple, width: float, glow: bool) -> None:
        if len(points) < 2:
            return
        if glow:
            glLineWidth(width + 5.0)
            glBegin(GL_LINES)
            for a, b in zip(points, points[1:]):
                glColor4f(color[0], color[1], color[2], 0.12)
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
        glLineWidth(width + 4.0)
        glBegin(GL_LINES)
        for index, (a, b) in enumerate(zip(points, points[1:])):
            if index % 3 == 1:
                glColor4f(color[0], color[1], color[2], 0.12)
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

    def _draw_nodes(self) -> None:
        for node in self.data_manager.nests.values():
            self._draw_node(node, (0.0, 0.62, 1.0, 1.0), 0.18)
        if not self.layers["queens"]:
            return
        for node in self.data_manager.queens.values():
            self._draw_node(node, (0.72, 0.31, 1.0, 1.0), 0.26)

    def _draw_node(self, node: HiveNode, color: ColorTuple, radius: float) -> None:
        selected = node.id == self.selected_node_id
        pulse = 0.5 + 0.5 * math.sin(time.perf_counter() * 3.0)
        glow_radius = radius * (2.5 if selected else 1.85)
        glPushMatrix()
        glTranslatef(*node.position)
        self._draw_sphere(glow_radius, (color[0], color[1], color[2], 0.10 + pulse * 0.08), 14, 10)
        self._draw_sphere(radius, color, 18, 12)
        if node.kind == "nest":
            self._draw_hex_ring(radius * 1.85, (0.1, 0.82, 1.0, 0.72))
        else:
            self._draw_hex_ring(radius * 1.95, (0.88, 0.45, 1.0, 0.75))
            self._draw_hex_ring(radius * 2.55, (0.88, 0.45, 1.0, 0.22))
        glPopMatrix()

    def _draw_workers(self) -> None:
        for worker in self.data_manager.workers.values():
            point = self.data_manager.worker_position(worker)
            glow = 0.3 + 0.25 * math.sin(worker.phase)
            glPushMatrix()
            glTranslatef(point[0], point[1], point[2] + 0.08 + glow * 0.06)
            self._draw_sphere(0.075, (1.0, 0.58, 0.08, 0.95), 10, 7)
            self._draw_sphere(0.16, (1.0, 0.39, 0.0, 0.14), 10, 7)
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
        glLineWidth(2.0)
        glColor4f(*color)
        glBegin(GL_LINE_LOOP)
        for index in range(6):
            angle = math.tau * index / 6.0 + math.pi / 6.0
            glVertex3f(math.cos(angle) * radius, math.sin(angle) * radius, 0.02)
        glEnd()

    def _draw_overlay_labels(self) -> None:
        if self._projection is None or self._modelview is None or self._viewport is None:
            return
        self._projected_nodes.clear()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        font = QFont("Segoe UI", 9, QFont.Weight.Bold)
        painter.setFont(font)
        for node in self.data_manager.all_nodes():
            screen = self._world_to_screen(node.position)
            if not screen:
                continue
            x, y = screen
            self._projected_nodes[node.id] = (x, y)
            label_color = QColor("#b7f7ff") if node.kind == "nest" else QColor("#e8c5ff")
            if node.id == self.selected_node_id:
                label_color = QColor("#fff2a6")
            painter.setPen(QPen(QColor(0, 0, 0, 180), 4))
            painter.drawText(int(x + 8), int(y - 8), node.label)
            painter.setPen(label_color)
            painter.drawText(int(x + 8), int(y - 8), node.label)

        painter.setPen(QColor("#8deaff"))
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Medium))
        painter.drawText(18, self.height() - 18, "Mouse: drag rotate | Shift+drag pan | Wheel zoom | Click node")
        painter.end()

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
            clicked = self._pick_node(self.last_mouse)
            if clicked:
                self.selected_node_id = clicked.id
                self.node_selected.emit(clicked.id, clicked.label)
                self.update()

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        current = event.position().toPoint()
        delta = current - self.last_mouse
        buttons = event.buttons()
        if buttons & Qt.MouseButton.LeftButton:
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self.pan_x += delta.x() * 0.012
                self.pan_y -= delta.y() * 0.012
            else:
                self.rotation_z += delta.x() * 0.35
                self.rotation_x += delta.y() * 0.22
                self.rotation_x = max(-82.0, min(-25.0, self.rotation_x))
            self.update()
        self.last_mouse = current

    def wheelEvent(self, event) -> None:  # type: ignore[override]
        amount = event.angleDelta().y() / 120.0
        self.zoom = max(6.5, min(22.0, self.zoom - amount * 0.7))
        self.update()

    def _pick_node(self, point: QPoint) -> HiveNode | None:
        if not self._projected_nodes:
            return None
        best: tuple[float, HiveNode] | None = None
        for node in self.data_manager.all_nodes():
            screen = self._projected_nodes.get(node.id)
            if not screen:
                continue
            dx = screen[0] - point.x()
            dy = screen[1] - point.y()
            distance = math.hypot(dx, dy)
            if distance <= 26.0 and (best is None or distance < best[0]):
                best = (distance, node)
        return best[1] if best else None


class ENGELPanel(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("ENGELPanel")
        self.setMinimumWidth(295)
        self.setStyleSheet(
            """
            QFrame#ENGELPanel {
                background: rgba(5, 13, 28, 245);
                border: 1px solid rgba(53, 214, 255, 150);
                border-radius: 8px;
            }
            QPushButton {
                background: rgba(4, 22, 42, 235);
                border: 1px solid rgba(53, 214, 255, 115);
                border-radius: 7px;
                color: #dbf7ff;
                padding: 8px 10px;
                font-weight: 700;
            }
            QPushButton:hover {
                border-color: #a3ff12;
                color: #ffffff;
            }
            QLineEdit {
                background: rgba(0, 0, 0, 120);
                border: 1px solid rgba(104, 224, 255, 120);
                border-radius: 6px;
                color: #e9fbff;
                padding: 8px;
            }
            """
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        top = QHBoxLayout()
        top.addWidget(label("ENGEL ASSISTANT", 12, 900, "#f2fbff"))
        top.addStretch(1)
        top.addWidget(label("SINGLE DOCKED", 8, 800, "#a78bfa"))
        layout.addLayout(top)

        orb = QLabel("ENGEL\nCORE")
        orb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        orb.setFixedHeight(120)
        orb.setStyleSheet(
            """
            QLabel {
                color: #e9fbff;
                font-weight: 900;
                letter-spacing: 0px;
                background: qradialgradient(cx:0.5, cy:0.48, radius:0.62,
                    stop:0 rgba(255,255,255,235),
                    stop:0.18 rgba(77,210,255,220),
                    stop:0.42 rgba(28,80,255,145),
                    stop:0.75 rgba(0,0,0,30),
                    stop:1 rgba(0,0,0,0));
                border: 1px solid rgba(53, 214, 255, 100);
                border-radius: 8px;
            }
            """
        )
        layout.addWidget(orb)
        layout.addWidget(center_label("SAFE + IDLE  |  LOCAL ONLY", 10, 900, "#a3ff12"))

        copy = QTextEdit()
        copy.setReadOnly(True)
        copy.setFixedHeight(94)
        copy.setText("Good morning. The hive is stable.\nAll signals are local visual data.\n\nHow can I assist?")
        copy.setStyleSheet(text_box_style())
        layout.addWidget(copy)

        button_row = QHBoxLayout()
        for name in ("Research", "Think", "Hive"):
            button = QPushButton(name)
            button_row.addWidget(button)
        layout.addLayout(button_row)

        entry = QLineEdit()
        entry.setPlaceholderText("Ask Engel...")
        layout.addWidget(entry)

        layout.addWidget(label("ENGEL TOOLS", 9, 900, "#35d6ff"))
        for title, detail, badge in [
            ("Research", "Open local research panel", ">"),
            ("Think", "Stable mode (async)", "STABLE"),
            ("Hive", "Colony overview", ">"),
        ]:
            layout.addWidget(tool_button(title, detail, badge))

        layout.addStretch(1)
        layout.addWidget(center_label("PANEL: SINGLE DOCKED    v3D.0", 8, 800, "#c4b5fd"))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.data_manager = DataManager()
        self.setWindowTitle(APP_TITLE + " - 3D Super Colony Map")
        self.resize(1680, 980)
        self.setMinimumSize(1180, 760)
        self.setStyleSheet(global_stylesheet())

        self.hive_map = HiveMap3DWidget(self.data_manager)
        self.hive_map.node_selected.connect(self._select_node)
        self.selected_label = QLabel("No node selected")
        self.status_time = QLabel()
        self.footer_health = QLabel("HEALTH 100%")
        self.footer_mode = QLabel("MODE PROTECTED ASYNC")
        self.signal_summary = QTextEdit()
        self.signal_summary.setReadOnly(True)
        self.signal_summary.setStyleSheet(text_box_style())

        self.setCentralWidget(self._build_central())
        self._build_engel_dock()
        self._update_signal_summary("Simulation scaffold loaded")

        self.clock_timer = QTimer(self)
        self.clock_timer.setInterval(1000)
        self.clock_timer.timeout.connect(self._tick_clock)
        self.clock_timer.start()
        self._tick_clock()

    def _build_central(self) -> QWidget:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(14, 12, 14, 10)
        layout.setSpacing(10)
        layout.addLayout(self._build_header())
        layout.addWidget(self._build_safety_banner())

        tabs = QTabWidget()
        tabs.addTab(self._build_colony_hive_tab(), "Colony Hive")
        tabs.addTab(self._build_static_tab("SUPER SWARM HIVE", "Visual overview only. No worker service, no autonomous loop, no runtime activation."), "Super Swarm Hive")
        tabs.addTab(self._build_static_tab("QUEEN RESEARCH LINKS", "Local placeholder cards for future approved research handoffs."), "Queen Research Links")
        tabs.addTab(self._build_static_tab("COMMUNICATION QUEEN", "Bridge concept panel only. No network discovery, no remote execution, no provider call."), "Communication Queen")
        layout.addWidget(tabs, 1)
        layout.addWidget(self._build_footer())
        return root

    def _build_header(self) -> QHBoxLayout:
        row = QHBoxLayout()
        mark = QLabel("H")
        mark.setFixedSize(64, 64)
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark.setStyleSheet(
            "color:#35d6ff; font-size:34px; font-weight:900; border:1px solid rgba(53,214,255,160); border-radius:8px; background:#06111f;"
        )
        row.addWidget(mark)

        title_block = QVBoxLayout()
        title_block.addWidget(label(APP_TITLE, 27, 900, "#ffffff"))
        title_block.addWidget(label("One local companion identity. Many memory colonies, visible proposal-stage workers, and Guardian-gated paths.", 10, 600, "#bad7e8"))
        row.addLayout(title_block, 1)

        guardian = QPushButton("Guardian Watching")
        guardian.setObjectName("GuardianButton")
        row.addWidget(guardian)
        refresh = QPushButton("Refresh Local Signals")
        refresh.clicked.connect(self._refresh_simulation)
        row.addWidget(refresh)
        return row

    def _build_safety_banner(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("SafetyBanner")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(14, 10, 14, 10)
        icon = QLabel("G")
        icon.setFixedWidth(46)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("font-size:32px; color:#a3ff12;")
        layout.addWidget(icon)
        copy = QVBoxLayout()
        copy.addWidget(label("SAFETY MEMBRANE / GUARDIAN LAYER", 14, 900, "#a3ff12"))
        copy.addWidget(label("Local visual scaffold only. No browsing, provider call, network call, background worker service, queue mutation, trusted-memory write, or source edit from the app.", 9, 700, "#dfffe6"))
        copy.addWidget(label("Mycelium signals are read-only-first. Colony outputs remain proposal candidates until human approval.", 9, 800, "#b8ff5f"))
        layout.addLayout(copy, 1)
        layout.addWidget(pill("LOCAL ONLY", "#a3ff12"))
        return frame

    def _build_colony_hive_tab(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(10)

        title_row = QHBoxLayout()
        title = QVBoxLayout()
        title.addWidget(label("SUPER COLONY VIEW", 14, 900, "#ffffff"))
        title.addWidget(label("Argentine ant model: many nests, many workers, many queens, one cooperative colony identity.", 9, 600, "#b9d9e6"))
        title_row.addLayout(title, 1)
        title_row.addWidget(label("VIEW LAYERS", 8, 900, "#a8d9ee"))
        for key, text in [
            ("workers", "Workers"),
            ("trails", "Trails"),
            ("queens", "Queens"),
            ("signals", "Signals"),
            ("guardian", "Guardian Layer"),
        ]:
            checkbox = QCheckBox(text)
            checkbox.setChecked(True)
            checkbox.toggled.connect(lambda checked, layer=key: self.hive_map.set_layer_enabled(layer, checked))
            title_row.addWidget(checkbox)
        outer.addLayout(title_row)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_left_controls())
        splitter.addWidget(self.hive_map)
        splitter.setSizes([230, 990])
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        outer.addWidget(splitter, 1)

        outer.addLayout(self._build_summary_cards())
        outer.addWidget(self._build_lower_panels())
        return page

    def _build_left_controls(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("Panel")
        panel.setMinimumWidth(215)
        panel.setMaximumWidth(270)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        layout.addWidget(label("LEGEND", 9, 900, "#cfefff"))
        for name, color in [
            ("Nest", "#35d6ff"),
            ("Queen", "#c084fc"),
            ("Worker", "#ff980a"),
            ("Trail Active", "#ffb020"),
            ("Mycelium Signal", "#0ac8ff"),
            ("Guardian Boundary", "#a3ff12"),
        ]:
            layout.addWidget(legend_item(name, color))

        controls = QGroupBox("MAP CONTROLS")
        controls_layout = QGridLayout(controls)
        actions = [
            ("+", self.hive_map.zoom_in),
            ("-", self.hive_map.zoom_out),
            ("Reset", self.hive_map.reset_camera),
        ]
        for index, (text, callback) in enumerate(actions):
            button = QPushButton(text)
            button.clicked.connect(callback)
            controls_layout.addWidget(button, index // 2, index % 2)
        layout.addWidget(controls)

        self.selected_label.setStyleSheet("color:#eaf6ff; padding:8px; border:1px solid rgba(53,214,255,90); border-radius:6px;")
        layout.addWidget(label("SELECTION", 9, 900, "#cfefff"))
        layout.addWidget(self.selected_label)
        layout.addStretch(1)
        return panel

    def _build_summary_cards(self) -> QHBoxLayout:
        row = QHBoxLayout()
        cards = [
            ("QUEENS", "3", "Active Queens", "#c084fc"),
            ("MEMORY COLONIES", "9", "Active Nests", "#35d6ff"),
            ("COLONY WORKERS", str(len(self.data_manager.workers)), "Observed Workers", "#2dd4bf"),
            ("MYCELIUM SIGNAL PATHS", str(sum(1 for t in self.data_manager.trails.values() if t.kind == "signal")), "Active Links", "#c084fc"),
            ("GUARDIAN LAYER", "ENCLOSED", "Boundary Intact", "#a3ff12"),
            ("PROPOSAL LANE", "644", "Awaiting Approval", "#ffb020"),
        ]
        for title, value, detail, color in cards:
            row.addWidget(summary_card(title, value, detail, color))
        return row

    def _build_lower_panels(self) -> QToolBox:
        toolbox = QToolBox()
        toolbox.setMinimumHeight(165)
        toolbox.addItem(info_panel("QUEEN OVERVIEW", "Q1 Queen Alpha  Active\nQ2 Queen Beta   Active\nQ3 Queen Gamma  Active"), "Queen Overview")
        toolbox.addItem(info_panel("NEST DETAILS", "Nest 8 - Core Memory Colony\nWorkers Observed: 481\nSignal Strength: 96%\nLast Signal: 8s ago"), "Nest Details")
        toolbox.addItem(self.signal_summary, "Signal Activity (Live)")
        toolbox.addItem(info_panel("PROPOSAL LANE", "P-042 Memory Expansion    Stage 2\nP-043 Signal Optimization Stage 1\nP-044 Worker Routing AI   Stage 2"), "Proposal Lane")
        toolbox.addItem(info_panel("ACTIVITY FEED", "10:24 Worker surge to Nest 3\n10:22 Signal path stabilized\n10:19 Proposal P-042 advanced\n10:17 Guardian layer verified"), "Activity Feed")
        return toolbox

    def _build_static_tab(self, title: str, subtitle: str) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)
        layout.addWidget(label(title, 19, 900, "#ffffff"))
        layout.addWidget(label(subtitle, 10, 700, "#d7fff3"))
        grid = QGridLayout()
        items = [
            ("Local Scope", "No network or provider path"),
            ("Guardian Gate", "Human approval above action gates"),
            ("Proposal Only", "Suggestions do not apply themselves"),
            ("Visibility", "All future integration points stay inspectable"),
        ]
        for index, (name, detail) in enumerate(items):
            grid.addWidget(summary_card(name, "SAFE", detail, ["#35d6ff", "#a3ff12", "#ffb020", "#c084fc"][index]), index // 2, index % 2)
        layout.addLayout(grid)
        layout.addStretch(1)
        return page

    def _build_footer(self) -> QFrame:
        footer = QFrame()
        footer.setObjectName("Footer")
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(18)
        for widget in [
            label("SESSION", 8, 900, "#a8d9ee"),
            self.status_time,
            divider(),
            self.footer_mode,
            divider(),
            label("DATA SCOPE LOCAL ONLY", 9, 900, "#a3ff12"),
            divider(),
            pill("READ-ONLY-FIRST", "#ffb020"),
            pill("GUARDIAN WATCHING", "#a3ff12"),
            pill("PROPOSAL ONLY", "#c084fc"),
        ]:
            layout.addWidget(widget)
        layout.addStretch(1)
        self.footer_health.setStyleSheet("color:#a3ff12; font-size:18px; font-weight:900;")
        layout.addWidget(self.footer_health)
        return footer

    def _build_engel_dock(self) -> None:
        dock = QDockWidget("ENGEL Panel", self)
        dock.setObjectName("EngelDock")
        dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)
        dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable)
        dock.setWidget(ENGELPanel())
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)

    def _refresh_simulation(self) -> None:
        self.data_manager.build_simulation_data()
        self._update_signal_summary("Simulation refreshed from local placeholder data")

    def _select_node(self, node_id: str, label_text: str) -> None:
        self.selected_label.setText(f"{label_text}\n{node_id}\nClick placeholder: selection only")
        self._update_signal_summary(f"Selected {label_text} ({node_id})")

    def _update_signal_summary(self, event: str) -> None:
        signal_count = sum(1 for trail in self.data_manager.trails.values() if trail.kind == "signal")
        worker_count = len(self.data_manager.workers)
        self.signal_summary.setText(
            "Active Trails: 26\n"
            f"Mycelium Links: {signal_count}\n"
            "Signal Stability: 98%\n"
            f"Observed Workers: {worker_count}\n"
            f"Latest: {event}\n\n"
            "Integration note:\n"
            "Use DataManager.apply_payload(), load_json_file(), or load_csv_file() with approved local data."
        )

    def _tick_clock(self) -> None:
        now = time.localtime()
        self.status_time.setText(f"{SESSION_ID}  {time.strftime('%H:%M:%S', now)}")


def interpolate_polyline(points: list[Point3], progress: float, lane_offset: float, phase: float) -> Point3:
    if len(points) == 1:
        return points[0]
    clamped = progress % 1.0
    segment_float = clamped * (len(points) - 1)
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


def label(text: str, size: int = 10, weight: int = 600, color: str = "#eaf5ff") -> QLabel:
    item = QLabel(text)
    item.setWordWrap(True)
    item.setStyleSheet(f"color:{color}; background:transparent; border:0;")
    font = QFont("Segoe UI", size)
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
    item.setStyleSheet(
        f"color:{color}; background:rgba(255,255,255,18); border:1px solid {color}; border-radius:7px; padding:5px 9px;"
    )
    return item


def divider() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.VLine)
    line.setStyleSheet("color:rgba(141,234,255,80);")
    return line


def legend_item(name: str, color: str) -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    dot = QLabel("*")
    dot.setFixedWidth(18)
    dot.setStyleSheet(f"color:{color}; font-size:16px;")
    layout.addWidget(dot)
    layout.addWidget(label(name, 9, 600, "#d8e9f2"), 1)
    return row


def summary_card(title: str, value: str, detail: str, color: str) -> QFrame:
    card = QFrame()
    card.setObjectName("SummaryCard")
    card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    card.setMinimumHeight(92)
    card.setStyleSheet(
        f"""
        QFrame#SummaryCard {{
            background: rgba(4, 17, 33, 238);
            border: 1px solid {color};
            border-radius: 8px;
        }}
        """
    )
    layout = QVBoxLayout(card)
    layout.setContentsMargins(12, 10, 12, 10)
    layout.setSpacing(4)
    layout.addWidget(label(title, 8, 900, color))
    value_label = label(value, 21 if len(value) < 5 else 15, 900, "#ffffff")
    value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(value_label)
    detail_label = center_label(detail, 8, 600, "#b9d9e6")
    layout.addWidget(detail_label)
    return card


def tool_button(title: str, detail: str, badge: str) -> QFrame:
    frame = QFrame()
    frame.setStyleSheet("QFrame { border:1px solid rgba(53,214,255,80); border-radius:7px; background:rgba(0,0,0,55); }")
    row = QHBoxLayout(frame)
    row.setContentsMargins(10, 6, 10, 6)
    text = QVBoxLayout()
    text.addWidget(label(title, 9, 900, "#eafbff"))
    text.addWidget(label(detail, 8, 600, "#a7c8d7"))
    row.addLayout(text, 1)
    row.addWidget(label(badge, 8, 900, "#c4b5fd"))
    return frame


def info_panel(title: str, content: str) -> QTextEdit:
    box = QTextEdit()
    box.setReadOnly(True)
    box.setText(f"{title}\n\n{content}")
    box.setStyleSheet(text_box_style())
    return box


def text_box_style() -> str:
    return """
        QTextEdit {
            background: rgba(2, 10, 22, 220);
            border: 1px solid rgba(87, 186, 255, 90);
            border-radius: 8px;
            color: #e9fbff;
            padding: 8px;
            selection-background-color: #165a74;
        }
    """


def global_stylesheet() -> str:
    return """
        QMainWindow, QWidget {
            background: #030814;
            color: #eaf5ff;
            font-family: Segoe UI;
            letter-spacing: 0px;
        }
        QPushButton {
            background: rgba(4, 22, 42, 235);
            border: 1px solid rgba(53, 214, 255, 130);
            border-radius: 7px;
            color: #dbf7ff;
            padding: 8px 12px;
            font-weight: 800;
        }
        QPushButton:hover {
            border-color: #a3ff12;
            color: #ffffff;
        }
        QPushButton#GuardianButton {
            border-color: #a3ff12;
            color: #a3ff12;
        }
        QTabWidget::pane {
            border: 1px solid rgba(53, 214, 255, 100);
            border-radius: 8px;
            background: rgba(3, 10, 24, 230);
        }
        QTabBar::tab {
            background: rgba(2, 12, 26, 240);
            color: #c6d9e6;
            border: 1px solid rgba(53, 214, 255, 80);
            border-bottom: 0;
            border-top-left-radius: 7px;
            border-top-right-radius: 7px;
            padding: 9px 16px;
            font-weight: 700;
        }
        QTabBar::tab:selected {
            background: rgba(5, 48, 70, 245);
            color: #35d6ff;
        }
        QFrame#SafetyBanner {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 rgba(11, 38, 27, 235),
                stop:0.7 rgba(2, 18, 26, 235),
                stop:1 rgba(3, 10, 24, 245));
            border: 1px solid rgba(163,255,18,130);
            border-radius: 8px;
        }
        QFrame#Footer, QFrame#Panel {
            background: rgba(3, 13, 29, 238);
            border: 1px solid rgba(53, 214, 255, 95);
            border-radius: 8px;
        }
        QGroupBox {
            border: 1px solid rgba(141,234,255,80);
            border-radius: 8px;
            margin-top: 10px;
            color: #a8d9ee;
            font-weight: 900;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px;
        }
        QCheckBox {
            color: #e9fbff;
            spacing: 7px;
            font-weight: 700;
        }
        QCheckBox::indicator {
            width: 14px;
            height: 14px;
        }
        QToolBox::tab {
            background: rgba(4, 22, 42, 235);
            border: 1px solid rgba(53, 214, 255, 90);
            border-radius: 6px;
            color: #dff7ff;
            padding: 7px;
            font-weight: 800;
        }
        QDockWidget {
            titlebar-close-icon: none;
            titlebar-normal-icon: none;
            color: #dff7ff;
        }
        QDockWidget::title {
            background: #06111f;
            border: 1px solid rgba(53,214,255,110);
            padding: 8px;
            text-align: left;
        }
    """


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
