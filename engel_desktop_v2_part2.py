class RouteBrowserPanel(QFrame):
    """Searchable browse of all Engel AI routes, grouped."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {CARD}; border: 1px solid {BORDER}; border-radius: 6px;")
        self._catalog: list[dict] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        hdr = QHBoxLayout()
        hdr.addWidget(make_label("Routes", bold=True, size=10))
        hdr.addStretch()
        self.count_lbl = make_label("", color=DIM, size=8)
        hdr.addWidget(self.count_lbl)
        layout.addLayout(hdr)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search routes...")
        self.search.textChanged.connect(self._filter)
        layout.addWidget(self.search)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(
            f"QListWidget {{ background: {BG}; border: 1px solid {BORDER}; border-radius: 4px; }}"
            f"QListWidget::item {{ padding: 3px 5px; color: {TEXT}; font-size: 8pt; }}"
            f"QListWidget::item:selected {{ background: #1a2a1a; }}"
        )
        self.list_widget.itemDoubleClicked.connect(self._copy_alias)
        layout.addWidget(self.list_widget, 1)

        self.hint_lbl = make_label("Double-click to copy alias to chat", color=DIM, size=7)
        layout.addWidget(self.hint_lbl)

        self._load_catalog()

    def _load_catalog(self):
        try:
            _ensure_project_on_path()
            from engel_route_explorer import route_catalog_for_gui
            self._catalog = route_catalog_for_gui()
        except Exception:
            self._catalog = []
        self._filter("")
        self.count_lbl.setText(f"{len(self._catalog)} routes")

    def _filter(self, text: str):
        needle = text.strip().casefold()
        self.list_widget.clear()
        last_group = ""
        for entry in self._catalog:
            label = str(entry.get("label", entry.get("route_id", "")))
            group = str(entry.get("group", ""))
            alias = str(entry.get("primary_alias", ""))
            haystack = (label + " " + alias + " " + group).casefold()
            if needle and needle not in haystack:
                continue
            if group != last_group:
                sep = QListWidgetItem(f"-- {group} --")
                sep.setForeground(QColor(PURPLE))
                sep.setFlags(Qt.ItemFlag(0))  # not selectable, not enabled
                self.list_widget.addItem(sep)
                last_group = group
            item = QListWidgetItem(f"  {alias or label}")
            item.setToolTip(f"{entry.get('route_id', '')}  |  {label}")
            item.setData(Qt.ItemDataRole.UserRole, alias or label)
            self.list_widget.addItem(item)

    def _copy_alias(self, item: QListWidgetItem):
        alias = item.data(Qt.ItemDataRole.UserRole)
        if alias:
            try:
                QApplication.clipboard().setText(str(alias))
            except Exception:
                pass


# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ Main Window Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
class _RustMeshWorker(QThread):
    result_ready = pyqtSignal(str, str)

    def __init__(self, task: str):
        super().__init__()
        self._task = task

    def run(self):
        try:
            self.result_ready.emit(self._task, _run_rust_mesh_task(self._task))
        except Exception as exc:
            self.result_ready.emit(self._task, f"ERROR: {type(exc).__name__}: {exc}")


def _run_rust_mesh_task(task: str) -> str:
    if task == "all":
        chunks = [
            ("Rust runtime", _rust_runtime_summary()),
            ("Device cluster", _run_engel_rs(["device-cluster", "status"], timeout=45)),
            ("Phones LAN link", _run_engel_rs(["lan-link", "status"], timeout=45)),
            ("Shared room", _run_engel_rs(["shared-room", "status"], timeout=45)),
            ("Remote workers", _run_engel_rs(["remote-workers", "assignment-status"], timeout=45)),
            ("Meeting room", _run_engel_rs(["meeting-room", "status"], timeout=45)),
            ("Sub-Engels", _sub_engel_status_report()),
            ("Hermes bridge", _hermes_bridge_report()),
            ("Hermes desktop", _hermes_desktop_report()),
        ]
        return "\n\n".join(f"=== {title} ===\n{body}" for title, body in chunks)
    if task == "devices":
        return _run_engel_rs(["device-cluster", "status"], timeout=60)
    if task == "phones":
        return _run_engel_rs(["lan-link", "status"], timeout=60)
    if task == "shared":
        return _run_engel_rs(["shared-room", "status"], timeout=60) + "\n\n" + _run_engel_rs(
            ["shared-room", "tail", "--limit", "8"], timeout=60
        )
    if task == "remote":
        return _run_engel_rs(["remote-workers", "state-machine-verify"], timeout=90)
    if task == "meeting":
        return _run_engel_rs(["meeting-room", "status"], timeout=60)
    if task == "sub_engels":
        return _sub_engel_status_report()
    if task == "hermes":
        return _hermes_bridge_report()
    if task == "open_hermes":
        return _launch_hermes_desktop()
    if task == "rewrite_verify":
        return _run_engel_rs(["rewrite-audit", "verify"], timeout=90)
    return f"Unknown task: {task}"


def _rust_runtime_summary() -> str:
    exe = _find_engel_rs_exe()
    lines = [f"Engel app root: {ENGEL_APP_ROOT}"]
    if exe is None:
        lines.append("Rust exe: not found")
    else:
        try:
            stat = exe.stat()
            lines.append(f"Rust exe: {exe}")
            lines.append(f"Size: {stat.st_size} bytes")
            lines.append(f"Modified: {datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(timespec='seconds')}")
        except Exception:
            lines.append(f"Rust exe: {exe}")
    return "\n".join(lines)


def _hermes_desktop_candidates() -> list[Path]:
    return [
        ENGEL_APP_ROOT / "engel_agent_main" / "apps" / "desktop" / "release" / "win-unpacked" / "Hermes.exe",
        Path(r"D:\Hermes\hermes-agent\apps\desktop\release\win-unpacked\Hermes.exe"),
        Path(r"D:\Hermes\apps\desktop\release\win-unpacked\Hermes.exe"),
    ]


def _find_hermes_desktop_exe() -> Path | None:
    for path in _hermes_desktop_candidates():
        if path.exists():
            return path
    return None


def _hermes_desktop_report() -> str:
    exe = _find_hermes_desktop_exe()
    if exe is None:
        searched = "\n".join(f"  - {path}" for path in _hermes_desktop_candidates())
        return "Hermes Sub-Engel desktop exe not found. Searched:\n" + searched
    lines = [f"Hermes Sub-Engel desktop exe: {exe}"]
    try:
        stat = exe.stat()
        lines.append(f"Size: {stat.st_size} bytes")
        lines.append(f"Modified: {datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(timespec='seconds')}")
    except Exception:
        pass
    proc = _run_short_command(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "Get-Process Hermes -ErrorAction SilentlyContinue | Select-Object Id,ProcessName,Path,MainWindowTitle | ConvertTo-Json -Compress",
        ],
        timeout=3.0,
    )
    if proc is not None and proc.returncode == 0 and proc.stdout.strip():
        lines.append("Running process: " + proc.stdout.strip())
    else:
        lines.append("Running process: not currently running")
        lines.append("Launch mode: interactive desktop click expected; headless agent launches may not persist.")
    return "\n".join(lines)


def _launch_hermes_desktop() -> str:
    exe = _find_hermes_desktop_exe()
    if exe is None:
        return _hermes_desktop_report()
    try:
        if os.name == "nt":
            old_cwd = os.getcwd()
            try:
                os.chdir(str(exe.parent))
                os.startfile(str(exe))  # type: ignore[attr-defined]
            finally:
                os.chdir(old_cwd)
        else:
            subprocess.Popen([str(exe)], cwd=str(exe.parent))
    except Exception as exc:
        return f"Hermes Sub-Engel desktop launch failed: {type(exc).__name__}: {exc}\n" + _hermes_desktop_report()
    time.sleep(1.0)
    return "Hermes Sub-Engel interactive desktop launch requested.\n" + _hermes_desktop_report()


def _sub_engel_status_report() -> str:
    try:
        _ensure_project_on_path()
        from engel_sub_node_meeting_bridge import render_meeting_node_status

        return str(render_meeting_node_status())
    except Exception as exc:
        return f"Sub-Engel status unavailable: {type(exc).__name__}: {exc}"


def _hermes_bridge_report() -> str:
    try:
        _ensure_project_on_path()
        from engel_agent_bridge import bridge_available, bridge_missing_reason

        available = bool(bridge_available())
        lines = [
            "Hermes-Agent is merged into the Agent Meeting Room as a read-only bridge.",
            f"bridge_available: {available}",
        ]
        if not available:
            lines.append("missing_reason: " + bridge_missing_reason())
        lines.append("Meeting Room station: Hermes-Agent (engel_agent_bridge)")
        lines.append("Autonomous Hermes invocation remains gated; this panel reports the real bridge state.")
        lines.append("Sub-Engel UI launch is an interactive desktop action; headless agent launches may exit without a visible window.")
        lines.append("")
        lines.append(_hermes_desktop_report())
        return "\n".join(lines)
    except Exception as exc:
        return f"Hermes bridge status unavailable: {type(exc).__name__}: {exc}"


class EngelRustMeshPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {CARD}; border: 1px solid {BORDER}; border-radius: 6px;")
        self._worker: Optional[_RustMeshWorker] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 9, 10, 9)
        layout.setSpacing(6)

        hdr = QHBoxLayout()
        hdr.addWidget(make_label("Engel Mesh", bold=True, size=10))
        hdr.addStretch()
        self.state_lbl = make_label("ready", color=DIM, size=8)
        hdr.addWidget(self.state_lbl)
        layout.addLayout(hdr)

        summary = _rust_runtime_summary()
        self.runtime_lbl = make_label(summary.replace("\n", " | "), color=DIM, size=7)
        self.runtime_lbl.setWordWrap(True)
        layout.addWidget(self.runtime_lbl)

        grid = QGridLayout()
        grid.setSpacing(4)
        buttons = [
            ("Refresh All", "all"),
            ("Devices", "devices"),
            ("Phones", "phones"),
            ("Shared", "shared"),
            ("Remote", "remote"),
            ("Meeting", "meeting"),
            ("Sub-Engels", "sub_engels"),
            ("Hermes", "hermes"),
            ("Open Hermes", "open_hermes"),
            ("Rewrite Verify", "rewrite_verify"),
        ]
        for index, (label, task) in enumerate(buttons):
            btn = QPushButton(label)
            btn.setFixedHeight(23)
            btn.setToolTip(f"Run real Engel proof: {label}")
            btn.clicked.connect(lambda _checked=False, task=task: self._run_task(task))
            grid.addWidget(btn, index // 3, index % 3)
        layout.addLayout(grid)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setStyleSheet(
            f"QTextEdit {{ background: {BG}; border: 1px solid {BORDER}; border-radius: 4px; "
            f"color: {TEXT}; padding: 6px; font-size: 7.5pt; }}"
        )
        self.output.setPlainText(
            "Click Refresh All to prove Rust, phones, shared room, remote workers, "
            "Sub-Engels, and Hermes bridge from Engel AI."
        )
        layout.addWidget(self.output, 1)

    def _run_task(self, task: str):
        if self._worker and self._worker.isRunning():
            return
        self.state_lbl.setText("running")
        self.state_lbl.setStyleSheet(f"color: {AMBER}; font-size: 8pt;")
        self.output.setPlainText(f"Running {task}...")
        self._worker = _RustMeshWorker(task)
        self._worker.result_ready.connect(self._on_result)
        self._worker.start()

    def _on_result(self, task: str, result: str):
        self.state_lbl.setText("done")
        self.state_lbl.setStyleSheet(f"color: {GREEN}; font-size: 8pt;")
        self.runtime_lbl.setText(_rust_runtime_summary().replace("\n", " | "))
        self.output.setPlainText(result)


class EngelDesktopV2(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowTitle("Engel AI")
        self.setWindowIcon(_engel_icon())
        self.setWindowOpacity(_ui_opacity("ENGEL_DESKTOP_V2_OPACITY", "ENGEL_UI_OPACITY"))
        self.resize(1200, 740)
        self.setMinimumSize(900, 600)

        central = QWidget()
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        # Ã¢â€â‚¬Ã¢â€â‚¬ Top status bar Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
        top = QHBoxLayout()
        top.addWidget(make_label("ENGEL AI", bold=True, color=GREEN, size=11))
        top.addWidget(make_label("   local-first", color=DIM, size=8))
        top.addStretch()
        self.clock_lbl = make_label("", color=DIM, size=8)
        top.addWidget(self.clock_lbl)

        # Agent Meeting Room launcher
        meeting_btn = QPushButton("Meeting Room")
        meeting_btn.setFixedHeight(22)
        meeting_btn.setToolTip("Open the Agent Meeting Room window")
        meeting_btn.setStyleSheet(
            f"background: {CARD}; color: {GREEN}; border: 1px solid {BORDER2};"
            f"border-radius: 4px; padding: 2px 8px; font-size: 8pt;"
        )
        meeting_btn.clicked.connect(self._launch_meeting_room)
        top.addWidget(meeting_btn)

        hermes_btn = QPushButton("Hermes")
        hermes_btn.setFixedHeight(22)
        hermes_btn.setToolTip("Launch the Hermes Sub-Engel desktop UI")
        hermes_btn.setStyleSheet(
            f"background: {CARD}; color: {BLUE}; border: 1px solid {BORDER2};"
            f"border-radius: 4px; padding: 2px 8px; font-size: 8pt;"
        )
        hermes_btn.clicked.connect(self._launch_hermes_desktop)
        top.addWidget(hermes_btn)

        # Octogent quick-launch
        octogent_btn = QPushButton("Octogent")
        octogent_btn.setFixedHeight(22)
        octogent_btn.setToolTip("Launch Octogent multi-agent swarm UI")
        octogent_btn.setStyleSheet(
            f"background: {CARD}; color: {PURPLE}; border: 1px solid {BORDER2};"
            f"border-radius: 4px; padding: 2px 8px; font-size: 8pt;"
        )
        octogent_btn.clicked.connect(self._launch_octogent)
        top.addWidget(octogent_btn)

        top.addWidget(make_label("  Win11", color=DIM, size=8))
        root.addLayout(top)

        # Ã¢â€â‚¬Ã¢â€â‚¬ Main grid: 3 columns Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
        grid = QHBoxLayout()
        grid.setSpacing(8)

        # System Monitor is hidden by default because its GPU probe can flash
        # a Windows console/pop-up on some machines. Opt in with
        # ENGEL_SHOW_SYSTEM_MONITOR=1.
        self.sys_panel = None
        if _env_enabled("ENGEL_SHOW_SYSTEM_MONITOR", default=False):
            self.sys_panel = SystemMonitorPanel()
            self.sys_panel.setFixedWidth(240)
            grid.addWidget(self.sys_panel)

        # Center: Agent Chat (larger, takes remaining space)
        self.chat_panel = AgentChatPanel()
        grid.addWidget(self.chat_panel, 2)

        # Right: tabbed panel (Goals / Models / Routes)
        self.right_tabs = QTabWidget()
        self.right_tabs.setMinimumWidth(300)
        self.right_tabs.setMaximumWidth(360)
        self.right_tabs.setStyleSheet(
            f"QTabWidget::pane {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 6px; }}"
            f"QTabBar::tab {{ background: {CARD}; color: {DIM}; padding: 4px 10px; font-size: 8pt; border: none; }}"
            f"QTabBar::tab:selected {{ color: {GREEN}; border-bottom: 2px solid {GREEN}; }}"
        )
        self.goal_panel = GoalQueuePanel()
        self.model_panel = ModelRoutePanel()
        self.route_panel = RouteBrowserPanel()
        self.mesh_panel = EngelRustMeshPanel()
        self.right_tabs.addTab(self.goal_panel, "Goals")
        self.right_tabs.addTab(self.model_panel, "Models")
        self.right_tabs.addTab(self.route_panel, "Routes")
        self.right_tabs.addTab(self.mesh_panel, "Engel Mesh")
        grid.addWidget(self.right_tabs)

        root.addLayout(grid, 1)

        # Ã¢â€â‚¬Ã¢â€â‚¬ Bottom status strip Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
        try:
            from engel_ai_update_routes import UPDATE_ROUTES as _ur
            _rc = len(_ur)
            _route_smoke = f"* {_rc} routes loaded"
        except Exception:
            _route_smoke = "* routes loading..."
        bottom = QHBoxLayout()
        bottom.addWidget(make_label(_route_smoke, color=GREEN, size=8, bold=True))
        bottom.addWidget(make_label("  |  ", color=DIM, size=8))
        bottom.addWidget(make_label("* SAFE MODE", color=AMBER, size=8, bold=True))
        bottom.addWidget(make_label("  |  ", color=DIM, size=8))
        bottom.addWidget(make_label("no provider | no network | no background worker",
                                    color=DIM, size=8))
        bottom.addStretch()
        bottom.addWidget(make_label("D:\\b.WorkSpace\\Engel App", color=DIM, size=8))
        root.addLayout(bottom)

        # Clock refresh
        self._clock = QTimer(self)
        self._clock.timeout.connect(self._tick)
        self._clock.start(1000)
        self._tick()
        _sanitize_widget_texts(self)

    def _tick(self):
        now = datetime.datetime.now().strftime("%H:%M:%S  %Y-%m-%d")
        self.clock_lbl.setText(now)

    def _launch_octogent(self):
        try:
            _ensure_project_on_path()
            from engel_octogent_runner import render_octogent_start, render_octogent_status, _server_pid, _web_url

            if _server_pid() is None and not _is_port_open(port=5173):
                start_result = render_octogent_start()
            else:
                start_result = render_octogent_status()

            target_url = _web_url()
            for _ in range(24):
                if _is_port_open(port=5173):
                    break
                time.sleep(0.5)

            if _is_port_open(port=5173):
                import webbrowser
                webbrowser.open(target_url)
                self.chat_panel.transcript.append(
                    f"\nOctogent: web dashboard is running at {target_url}.\n"
                    "Use: multi-agent swarm dashboard. API backend is http://localhost:8787 and is not the UI."
                )
            elif _is_port_open(port=8787):
                self.chat_panel.transcript.append(
                    "\nOctogent: API backend is up, but the web dashboard is not ready yet. "
                    "Wait a few seconds and click Octogent again.\n"
                    + str(start_result or render_octogent_status())
                )
            else:
                self.chat_panel.transcript.append(
                    "\nOctogent: server is not reachable yet. Status/logs:\n"
                    + str(start_result or render_octogent_status())
                )
        except Exception as exc:
            self.chat_panel.transcript.append(f"\nOctogent: launch/status failed ({type(exc).__name__}: {exc})")

    def _launch_hermes_desktop(self):
        try:
            result = _launch_hermes_desktop()
            self.chat_panel.transcript.append("\nHermes: " + result)
            if getattr(self, "mesh_panel", None) is not None:
                self.mesh_panel.output.setPlainText(result)
        except Exception as exc:
            self.chat_panel.transcript.append(f"\nHermes: launch failed ({type(exc).__name__}: {exc})")

    def _launch_meeting_room(self):
        """Open the Agent Meeting Room as a child window."""
        try:
            _ensure_project_on_path()
            from engel_agent_meeting_room import AgentMeetingRoomWindow
            # Keep a reference so the window is not garbage-collected
            if getattr(self, "_meeting_room_win", None) is None:
                self._meeting_room_win = AgentMeetingRoomWindow()
            self._meeting_room_win.show()
            self._meeting_room_win.raise_()
            self._meeting_room_win.activateWindow()
        except Exception as exc:
            # Surface error in chat panel so user sees it
            self.chat_panel.transcript.append(
                f"\nEngel: (Meeting Room failed to open: {exc})"
            )


# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ Launcher Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
def launch_desktop_v2():
    if not HAS_QT:
        print("PyQt6 not installed. Install with:  pip install PyQt6")
        return
    if not _claim_desktop_single_instance():
        print("Engel Desktop V2 is already running; not opening a second window.")
        return
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)
    app.setWindowIcon(_engel_icon())
    win = EngelDesktopV2()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    launch_desktop_v2()
