"""Visible Grok Bot computer: browser, filesystem, terminal, and chat.

This is the Bot screen on the shared Engel computer. It references the
current Engel AI Main face (Flutter Cosmic Swarm OS / EngelAIMain.exe)
and the live CT 246 local URLs. It does not create a cloud VM, open the
public internet, or start a hidden worker.
"""
from __future__ import annotations

import json
import os
import socket
from html import escape
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import unquote, urlparse

from engel_project_paths import resolve_engel_app_root


ROOT = resolve_engel_app_root(__file__)
BOT_HOME = ROOT / "runtime" / "grok_bots"
COMPUTER_DIR = BOT_HOME / "computer"
HOME_HTML = COMPUTER_DIR / "home.html"
CURRENT_ENGEL_MAIN_EXE = (
    ROOT / "engel_flutter_main" / "build" / "windows" / "x64" / "runner" / "Release" / "EngelAIMain.exe"
)
LOCAL_CHAT = "http://127.0.0.1:24680"
LOCAL_MEETING = "http://127.0.0.1:8790"
LOCAL_OFFICE = "http://127.0.0.1:3000"
SUB_ENGEL_HOST = "198.51.100.227"
SUB_ENGEL_PORT = 8776
SUB_ENGEL_LAND = Path(r"D:\EngelWindowsSubNode\incoming_catalog")

ALLOWED_LOCAL_HOSTS = {
    ("127.0.0.1", 24680),
    ("localhost", 24680),
    ("127.0.0.1", 8790),
    ("localhost", 8790),
    ("127.0.0.1", 3000),
    ("localhost", 3000),
}

FILE_ROOTS: tuple[tuple[str, Path], ...] = (
    ("Engel App", ROOT),
    ("Grok home", BOT_HOME),
    ("Android workers", ROOT / "remote_workers"),
    ("Meeting Room state", ROOT / "runtime" / "meeting_room"),
    ("Sub-Engel land", SUB_ENGEL_LAND),
    ("Sub-Engel node", Path(r"D:\EngelWindowsSubNode")),
    ("ICM on Engel workspace", ROOT / "memory" / "icm" / "engel-ai-main"),
    ("ICM Architect pack", Path(r"D:\b.WorkSpace\icm-architect-main\icm-architect-main")),
    ("Grok receipts", ROOT / "reports" / "grok_bots"),
    ("Engel AI Main source", ROOT / "engel_flutter_main" / "lib"),
)


def current_engel_main_exe() -> Path:
    return CURRENT_ENGEL_MAIN_EXE


def _tcp_up(host: str, port: int, timeout: float = 0.7) -> bool:
    sock = socket.socket()
    sock.settimeout(timeout)
    try:
        sock.connect((host, port))
        sock.close()
        return True
    except Exception:
        return False


def _local_http_json(url: str, timeout: float = 2.5) -> dict[str, Any]:
    import urllib.error
    import urllib.request

    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8", "replace"))
        return payload if isinstance(payload, dict) else {"ok": False, "error": "not_object"}
    except Exception as exc:
        return {"ok": False, "error": type(exc).__name__, "detail": str(exc)[:160]}


def live_computer_status() -> dict[str, Any]:
    exe = current_engel_main_exe()
    chat_up = _tcp_up("127.0.0.1", 24680)
    meet_up = _tcp_up("127.0.0.1", 8790)
    office_up = _tcp_up("127.0.0.1", 3000)
    sub_up = _tcp_up(SUB_ENGEL_HOST, SUB_ENGEL_PORT)
    chat = _local_http_json(LOCAL_CHAT + "/health") if chat_up else {"ok": False, "error": "tcp_down"}
    meet = _local_http_json(LOCAL_MEETING + "/health") if meet_up else {"ok": False, "error": "tcp_down"}
    return {
        "exe_present": exe.is_file(),
        "exe_path": str(exe),
        "chat_up": chat_up and bool(chat.get("ok") is True),
        "meeting_up": meet_up and bool(meet.get("ok") is True),
        "office_up": office_up,
        "sub_engel_up": sub_up,
        "chat_status": str(chat.get("status") or chat.get("error") or ""),
        "meeting_status": str(meet.get("status") or meet.get("error") or ""),
        "land_present": SUB_ENGEL_LAND.exists(),
        "workspace": str(ROOT),
    }


def url_is_allowed(url: str) -> bool:
    raw = str(url or "").strip()
    if not raw:
        return False
    low = raw.casefold()
    if low.startswith("about:blank") or low.startswith("data:text/html"):
        return True
    parsed = urlparse(raw)
    if parsed.scheme in {"", "file"}:
        if parsed.scheme != "file":
            try:
                Path(raw).resolve().relative_to(COMPUTER_DIR.resolve())
                return True
            except (OSError, ValueError):
                return False
        path_text = unquote(parsed.path or "")
        if os.name == "nt" and path_text.startswith("/") and len(path_text) > 2 and path_text[2] == ":":
            path_text = path_text[1:]
        try:
            resolved = Path(path_text).resolve()
            resolved.relative_to(COMPUTER_DIR.resolve())
            return True
        except (OSError, ValueError):
            return False
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.hostname or "").casefold()
    port = parsed.port
    if port is None:
        port = 443 if parsed.scheme == "https" else 80
    return (host, port) in ALLOWED_LOCAL_HOSTS


def _pill(ok: bool, yes: str, no: str) -> str:
    if ok:
        return f'<span class="pill ok">{escape(yes)}</span>'
    return f'<span class="pill bad">{escape(no)}</span>'


def computer_home_html(bot_name: str = "Grok") -> str:
    live = live_computer_status()
    exe_state = "present" if live["exe_present"] else "missing"
    try:
        from engel_grok_bot import probe_shared_computer

        rows = probe_shared_computer()
    except Exception:
        rows = [{"part": "ROG workspace", "path": str(ROOT), "state": "present"}]
    body_rows = "".join(
        (
            "<tr><td>"
            + escape(str(row.get("part") or ""))
            + "</td><td><code>"
            + escape(str(row.get("path") or ""))
            + "</code></td><td>"
            + escape(str(row.get("state") or ""))
            + "</td></tr>"
        )
        for row in rows
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{escape(bot_name)} Computer — Engel AI Main</title>
  <style>
    html, body {{ margin:0; height:100%; background:#070b16; color:#f0f4ff;
      font-family: Segoe UI, sans-serif; }}
    .wrap {{ min-height:100%; padding:22px 26px 36px;
      background: radial-gradient(1200px 600px at 70% 10%, #16305a 0%, transparent 55%),
                  radial-gradient(900px 500px at 20% 80%, #1a1040 0%, #070b16 70%); }}
    .eyebrow {{ color:#00e5ff; letter-spacing:2px; font-size:11px; font-weight:800; }}
    h1 {{ margin:6px 0 4px; font-size:28px; }}
    .sub {{ color:#8b95ad; margin-bottom:16px; }}
    .row {{ display:flex; gap:12px; flex-wrap:wrap; }}
    .card {{ background:rgba(12,18,34,.78); border:1px solid #24324f; border-radius:16px;
      padding:14px 16px; min-width:200px; flex:1; }}
    .card h2 {{ margin:0 0 8px; font-size:15px; color:#00e5ff; }}
    .pill {{ display:inline-block; border-radius:999px; padding:3px 10px;
      font-size:11px; font-weight:700; margin:0 6px 6px 0; }}
    .ok {{ background:#113a2a; color:#3dffb0; }}
    .bad {{ background:#3a1518; color:#ff8d97; }}
    a {{ color:#00e5ff; text-decoration:none; }}
    a:hover {{ text-decoration:underline; }}
    code {{ color:#c8d4ff; }}
    .warn {{ color:#ffb86b; font-size:12px; }}
    table {{ width:100%; border-collapse:collapse; font-size:12px; }}
    td, th {{ border-bottom:1px solid #24324f; padding:6px 4px; text-align:left; vertical-align:top; }}
    th {{ color:#8b95ad; font-weight:700; }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="eyebrow">ENGEL · COSMIC SWARM OS</div>
    <h1>{escape(bot_name)}'s computer</h1>
    <div class="sub">Persistent shared Engel computer — browser, files, terminal, and chat on this cluster.</div>
    {_pill(True, "Chat: Grok", "")}
    {_pill(live["chat_up"], "Chat :24680 live", "Chat :24680 down")}
    {_pill(live["meeting_up"], "Meeting Room live", "Meeting Room down")}
    {_pill(live["office_up"], "Office :3000 live", "Office :3000 down")}
    {_pill(live["sub_engel_up"], "Sub-Engel live", "Sub-Engel down")}
    {_pill(live["exe_present"], "EngelAIMain.exe present", "EngelAIMain.exe missing")}
    <div class="row" style="margin-top:16px">
      <div class="card">
        <h2>Current Engel AI Main</h2>
        <p>This Bot screen is wired to Cosmic Swarm OS, not a stub console.</p>
        <p>App: <code>EngelAIMain.exe</code> ({escape(exe_state)})</p>
        <p>Use <b>Open Engel AI Main</b> for the live Flutter window.</p>
        <p>Use <b>Ask Engel</b> below to talk to CT 246 through <code>{LOCAL_CHAT}</code>.</p>
      </div>
      <div class="card">
        <h2>Local faces</h2>
        <p><a href="{LOCAL_CHAT}/health">Chat body {LOCAL_CHAT}</a><br>{escape(live["chat_status"] or "tcp only")}</p>
        <p><a href="{LOCAL_MEETING}/health">Meeting Room {LOCAL_MEETING}</a><br>{escape(live["meeting_status"] or "tcp only")}</p>
        <p><a href="{LOCAL_OFFICE}">3D Office {LOCAL_OFFICE}</a></p>
        <p class="warn">Public internet is blocked in this browser.</p>
      </div>
      <div class="card">
        <h2>Filesystem + Terminal</h2>
        <p>Left: Engel App workspace, Grok home, workers, Sub-Engel land.</p>
        <p>Bottom-left: real cmd.exe in <code>{escape(str(ROOT))}</code>.</p>
        <p>Bottom-right: Grok teammate chat. Ask Engel uses the live CT body.</p>
        <p>CT 246 home remains <code>/opt/engel</code>.</p>
        <p>Sub-Engel land: <code>{escape(str(SUB_ENGEL_LAND))}</code> ({"present" if live["land_present"] else "missing"}).</p>
      </div>
    </div>
    <div class="card" style="margin-top:14px">
      <h2>Cluster map</h2>
      <table>
        <tr><th>Part</th><th>Path</th><th>State</th></tr>
        {body_rows}
      </table>
    </div>
  </div>
</body>
</html>
"""


def write_computer_home(bot_name: str = "Grok") -> Path:
    COMPUTER_DIR.mkdir(parents=True, exist_ok=True)
    HOME_HTML.write_text(computer_home_html(bot_name), encoding="utf-8")
    return HOME_HTML


def _engel_main_env() -> dict[str, str]:
    env = os.environ.copy()
    env["ENGEL_MAIN_SERVER_ENABLED"] = "1"
    env["ENGEL_MAIN_SERVER_CT_ID"] = "246"
    env["ENGEL_MAIN_SERVER_CT_HOSTNAME"] = "engel-ai-main"
    env["ENGEL_MAIN_SERVER_RUNTIME_ROOT"] = "/opt/engel"
    env["ENGEL_MAIN_SERVER_CHAT_URL"] = LOCAL_CHAT
    env["ENGEL_MAIN_SERVER_CHAT_REQUIRED"] = "1"
    env["ENGEL_MAIN_ALLOW_LAPTOP_LOCAL_FALLBACK"] = "0"
    env["ENGEL_MEETING_ROOM_SERVER_URL"] = LOCAL_MEETING
    env.setdefault("ENGEL_STANDALONE_CHAT_PROVIDER", "local")
    return env


def launch_current_engel_ai_main() -> str:
    exe = current_engel_main_exe()
    if not exe.is_file():
        return "Current Engel AI Main is missing: " + str(exe)
    try:
        import subprocess

        existing = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq EngelAIMain.exe", "/NH"],
            capture_output=True,
            text=True,
            check=False,
        )
        if "EngelAIMain.exe" in (existing.stdout or ""):
            return "Current Engel AI Main is already open (EngelAIMain.exe)."
        subprocess.Popen(
            [str(exe)],
            cwd=str(exe.parent),
            env=_engel_main_env(),
        )
        return "Opened current Engel AI Main (Cosmic Swarm OS) against " + LOCAL_CHAT
    except Exception as exc:
        return f"Could not open Engel AI Main ({type(exc).__name__}: {exc})"


def ask_engel_ai_main(prompt: str) -> str:
    """Talk to the live CT246 chat body through the local one-system tunnel."""
    text = str(prompt or "").strip()
    if not text:
        return ""
    import urllib.error
    import urllib.request

    payload = {
        "prompt": text,
        "source": "grok_bot_computer",
        "conversation_id": "grok-bot-computer:grok",
        "timeout": 70,
        "max_tokens": 900,
        "prefer_fast_local_chat": False,
    }
    request = urllib.request.Request(
        LOCAL_CHAT + "/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            data = json.loads(response.read().decode("utf-8", "replace"))
    except Exception as exc:
        return f"Engel AI Main chat tunnel did not answer ({type(exc).__name__}: {exc}). Is http://127.0.0.1:24680 up?"
    if not isinstance(data, dict):
        return "Engel AI Main returned a non-object chat body."
    reply = str(data.get("assistant_reply") or data.get("reply") or "").strip()
    if reply:
        return reply
    return str(data.get("status") or data.get("error") or "Empty Engel AI Main reply.")


def _try_qt():
    try:
        from PySide6.QtCore import Qt, QProcess, QProcessEnvironment, QUrl
        from PySide6.QtGui import QColor, QFont, QIcon
        from PySide6.QtWidgets import (
            QApplication,
            QFileSystemModel,
            QFrame,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QMainWindow,
            QPlainTextEdit,
            QPushButton,
            QSplitter,
            QTextBrowser,
            QTreeView,
            QVBoxLayout,
            QWidget,
            QComboBox,
        )
        web = None
        try:
            from PySide6.QtWebEngineWidgets import QWebEngineView
            from PySide6.QtWebEngineCore import QWebEnginePage

            web = (QWebEngineView, QWebEnginePage)
        except Exception:
            web = None
        return {
            "Qt": Qt,
            "QProcess": QProcess,
            "QProcessEnvironment": QProcessEnvironment,
            "QUrl": QUrl,
            "QColor": QColor,
            "QFont": QFont,
            "QIcon": QIcon,
            "QApplication": QApplication,
            "QFileSystemModel": QFileSystemModel,
            "QFrame": QFrame,
            "QHBoxLayout": QHBoxLayout,
            "QLabel": QLabel,
            "QLineEdit": QLineEdit,
            "QMainWindow": QMainWindow,
            "QPlainTextEdit": QPlainTextEdit,
            "QPushButton": QPushButton,
            "QSplitter": QSplitter,
            "QTextBrowser": QTextBrowser,
            "QTreeView": QTreeView,
            "QVBoxLayout": QVBoxLayout,
            "QWidget": QWidget,
            "QComboBox": QComboBox,
            "web": web,
        }
    except Exception:
        return None


STYLE = """
QMainWindow, QWidget { background: #070b16; color: #f0f4ff; font-family: 'Segoe UI'; }
QLabel#brand { color: #f0f4ff; font-size: 15px; font-weight: 800; letter-spacing: 1px; }
QLabel#os { color: #5e6a85; font-size: 9px; font-weight: 700; letter-spacing: 1.5px; }
QLabel#ready { background: #113a2a; color: #3dffb0; border-radius: 10px; padding: 3px 10px; font-weight: 700; }
QLabel#down { background: #3a1518; color: #ff8d97; border-radius: 10px; padding: 3px 10px; font-weight: 700; }
QLabel#chatlane { background: #18233a; color: #d7e0ff; border: 1px solid #2a3b5e; border-radius: 10px; padding: 4px 10px; }
QLabel#section { color: #8b95ad; font-size: 10px; font-weight: 700; letter-spacing: 1px; }
QPushButton { background: #121a2d; color: #00e5ff; border: 1px solid #2a3b5e; border-radius: 10px; padding: 6px 12px; font-weight: 700; }
QPushButton:hover { border-color: #00e5ff; }
QLineEdit { background: #101827; color: #f0f4ff; border: 1px solid #00e5ff; border-radius: 12px; padding: 8px 10px; }
QTreeView, QPlainTextEdit, QTextBrowser { background: #0b1220; color: #dce6ff; border: 1px solid #24324f; border-radius: 12px; }
QSplitter::handle { background: #18233a; }
"""


def launch_computer_window(bot_name: str = "Grok", smoke: bool = False) -> int:
    qt = _try_qt()
    if qt is None:
        print("Qt is not available. Current Engel Grok Bot computer window cannot open.")
        return 2

    Qt = qt["Qt"]
    QProcess = qt["QProcess"]
    QProcessEnvironment = qt["QProcessEnvironment"]
    QUrl = qt["QUrl"]
    QApplication = qt["QApplication"]
    QFileSystemModel = qt["QFileSystemModel"]
    QHBoxLayout = qt["QHBoxLayout"]
    QLabel = qt["QLabel"]
    QLineEdit = qt["QLineEdit"]
    QMainWindow = qt["QMainWindow"]
    QPlainTextEdit = qt["QPlainTextEdit"]
    QPushButton = qt["QPushButton"]
    QSplitter = qt["QSplitter"]
    QTextBrowser = qt["QTextBrowser"]
    QTreeView = qt["QTreeView"]
    QVBoxLayout = qt["QVBoxLayout"]
    QWidget = qt["QWidget"]
    QIcon = qt["QIcon"]
    web = qt["web"]

    home = write_computer_home(bot_name)
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(STYLE)

    window = QMainWindow()
    window.setWindowTitle("Engel AI Main — Grok Bot Computer")
    icon = ROOT / "assets" / "branding" / "final" / "engel_icon_final.ico"
    if icon.is_file():
        window.setWindowIcon(QIcon(str(icon)))
    window.resize(1380, 880)

    root = QWidget()
    window.setCentralWidget(root)
    layout = QVBoxLayout(root)
    layout.setContentsMargins(12, 10, 12, 10)
    layout.setSpacing(8)

    header = QHBoxLayout()
    brand_box = QVBoxLayout()
    brand = QLabel("ENGEL")
    brand.setObjectName("brand")
    os_name = QLabel("COSMIC SWARM OS")
    os_name.setObjectName("os")
    brand_box.addWidget(brand)
    brand_box.addWidget(os_name)
    header.addLayout(brand_box)
    header.addStretch(1)
    title = QLabel(bot_name + "'s computer")
    title.setObjectName("brand")
    header.addWidget(title)
    header.addStretch(1)
    live = live_computer_status()
    ready = QLabel("Chat ready" if live["chat_up"] else "Chat down")
    ready.setObjectName("ready" if live["chat_up"] else "down")
    lane = QLabel("Chat: Grok")
    lane.setObjectName("chatlane")
    header.addWidget(ready)
    header.addWidget(lane)
    layout.addLayout(header)

    split = QSplitter()
    split.setOrientation(Qt.Orientation.Horizontal)

    files_box = QWidget()
    files_layout = QVBoxLayout(files_box)
    files_layout.setContentsMargins(0, 0, 0, 0)
    files_label = QLabel("FILESYSTEM")
    files_label.setObjectName("section")
    files_layout.addWidget(files_label)
    root_pick = qt["QComboBox"]()
    usable_roots = [(label, path) for label, path in FILE_ROOTS if path.exists()]
    if not usable_roots:
        usable_roots = [("Engel App", ROOT)]
    for label, path in usable_roots:
        root_pick.addItem(label, str(path))
    files_layout.addWidget(root_pick)
    tree = QTreeView()
    model = QFileSystemModel()
    first_root = Path(str(usable_roots[0][1]))
    model.setRootPath(str(first_root))
    tree.setModel(model)
    tree.setRootIndex(model.index(str(first_root)))
    tree.setHeaderHidden(True)
    for column in range(1, 4):
        tree.hideColumn(column)
    files_layout.addWidget(tree)

    def _change_root(index: int) -> None:
        target = Path(str(root_pick.itemData(index) or first_root))
        if target.exists():
            model.setRootPath(str(target))
            tree.setRootIndex(model.index(str(target)))

    root_pick.currentIndexChanged.connect(_change_root)
    split.addWidget(files_box)

    right = QSplitter()
    right.setOrientation(Qt.Orientation.Vertical)

    browser_box = QWidget()
    browser_layout = QVBoxLayout(browser_box)
    browser_layout.setContentsMargins(0, 0, 0, 0)
    browser_head = QHBoxLayout()
    browser_label = QLabel("BROWSER")
    browser_label.setObjectName("section")
    browser_head.addWidget(browser_label)
    address = QLineEdit(home.resolve().as_uri())
    browser_head.addWidget(address, 1)
    home_btn = QPushButton("Home")
    go_btn = QPushButton("Go")
    open_main = QPushButton("Open Engel AI Main")
    chat_btn = QPushButton("Chat :24680")
    room_btn = QPushButton("Meeting Room")
    office_btn = QPushButton("Office :3000")
    browser_head.addWidget(home_btn)
    browser_head.addWidget(go_btn)
    browser_head.addWidget(open_main)
    browser_head.addWidget(chat_btn)
    browser_head.addWidget(room_btn)
    browser_head.addWidget(office_btn)
    browser_layout.addLayout(browser_head)

    status = QLabel("Screen is this Bot computer. Current Engel AI is Cosmic Swarm OS.")
    status.setObjectName("os")
    browser_layout.addWidget(status)

    if web is not None:
        view = web[0]()
        page_type = web[1]

        class GuardedPage(page_type):
            def acceptNavigationRequest(self, url, nav_type, is_main_frame):  # noqa: N802
                if url_is_allowed(url.toString()):
                    return True
                status.setText("Blocked off-computer URL: " + url.toString())
                return False

        page = GuardedPage(view)
        view.setPage(page)
        view.setUrl(QUrl.fromLocalFile(str(home)))
        browser_layout.addWidget(view, 1)
    else:
        view = QTextBrowser()
        view.setOpenExternalLinks(False)
        view.setHtml(computer_home_html(bot_name))
        browser_layout.addWidget(view, 1)

    def show_home() -> None:
        target = write_computer_home(bot_name)
        load_url(target.resolve().as_uri())

    def load_url(raw: str) -> None:
        target = str(raw or "").strip()
        if not url_is_allowed(target) and not target.startswith("file:"):
            if target == str(home) or target == home.resolve().as_uri():
                target = home.resolve().as_uri()
            else:
                status.setText("Only Engel local computer URLs are allowed.")
                return
        if not url_is_allowed(target):
            status.setText("Only Engel local computer URLs are allowed.")
            return
        address.setText(target)
        if web is not None:
            view.setUrl(QUrl(target))
        elif target.startswith("file:"):
            view.setHtml(computer_home_html(bot_name))
        else:
            view.setPlainText("WebEngine not installed. Local page only.\n" + target)
        status.setText("Browser: " + target)

    home_btn.clicked.connect(show_home)
    go_btn.clicked.connect(lambda: load_url(address.text()))
    address.returnPressed.connect(lambda: load_url(address.text()))
    chat_btn.clicked.connect(lambda: load_url(LOCAL_CHAT + "/health"))
    room_btn.clicked.connect(lambda: load_url(LOCAL_MEETING + "/health"))
    office_btn.clicked.connect(lambda: load_url(LOCAL_OFFICE))
    open_main.clicked.connect(lambda: status.setText(launch_current_engel_ai_main()))
    right.addWidget(browser_box)

    bottom = QSplitter()
    bottom.setOrientation(Qt.Orientation.Horizontal)

    term_box = QWidget()
    term_layout = QVBoxLayout(term_box)
    term_layout.setContentsMargins(0, 0, 0, 0)
    term_label = QLabel("TERMINAL")
    term_label.setObjectName("section")
    term_layout.addWidget(term_label)
    term_out = QPlainTextEdit()
    term_out.setReadOnly(True)
    term_out.setPlaceholderText("Terminal on the shared Engel computer.")
    term_in = QLineEdit()
    term_in.setPlaceholderText("Type a shell command in the Engel workspace")
    term_layout.addWidget(term_out, 1)
    term_layout.addWidget(term_in)
    bottom.addWidget(term_box)

    chat_box = QWidget()
    chat_layout = QVBoxLayout(chat_box)
    chat_layout.setContentsMargins(0, 0, 0, 0)
    chat_label = QLabel("CHAT")
    chat_label.setObjectName("section")
    chat_layout.addWidget(chat_label)
    chat_out = QPlainTextEdit()
    chat_out.setReadOnly(True)
    chat_out.setPlaceholderText("Grok teammate and Engel AI Main replies.")
    chat_layout.addWidget(chat_out, 1)
    bottom.addWidget(chat_box)
    bottom.setSizes([560, 560])

    right.addWidget(bottom)
    right.setSizes([480, 280])
    split.addWidget(right)
    split.setSizes([280, 1080])
    layout.addWidget(split, 1)

    chat_row = QHBoxLayout()
    chat_in = QLineEdit()
    chat_in.setPlaceholderText("Message Grok, or Ask Engel AI Main through :24680")
    send_btn = QPushButton("Send Grok")
    engel_btn = QPushButton("Ask Engel")
    chat_row.addWidget(chat_in, 1)
    chat_row.addWidget(send_btn)
    chat_row.addWidget(engel_btn)
    layout.addLayout(chat_row)

    def send_bot() -> None:
        text = chat_in.text().strip()
        if not text:
            return
        from engel_grok_bot import handle_console_line

        reply = handle_console_line(text)
        chat_in.clear()
        chat_out.appendPlainText("You: " + text + "\n" + bot_name + ":\n" + reply + "\n")

    def send_engel() -> None:
        text = chat_in.text().strip()
        if not text:
            return
        chat_in.clear()
        chat_out.appendPlainText("You → Engel AI Main: " + text)
        reply = ask_engel_ai_main(text)
        chat_out.appendPlainText("Engel AI Main:\n" + reply + "\n")

    send_btn.clicked.connect(send_bot)
    engel_btn.clicked.connect(send_engel)
    chat_in.returnPressed.connect(send_bot)

    process = QProcess(window)
    process.setWorkingDirectory(str(ROOT))
    comspec = os.environ.get("COMSPEC") or "cmd.exe"
    process.setProgram(comspec)
    if not smoke:
        def _append() -> None:
            data = bytes(process.readAllStandardOutput()).decode("utf-8", "replace")
            err = bytes(process.readAllStandardError()).decode("utf-8", "replace")
            if data:
                term_out.appendPlainText(data.rstrip())
            if err:
                term_out.appendPlainText(err.rstrip())

        process.readyReadStandardOutput.connect(_append)
        process.readyReadStandardError.connect(_append)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PROMPT", "GrokBot $P$G")
        process.setProcessEnvironment(env)
        # Working directory is already ROOT. Do not cd /d a quoted path: that is
        # what printed "The filename, directory name, or volume label syntax is incorrect."
        process.start(comspec, ["/K", "echo Engel Grok Bot terminal. Workspace is %CD%."])
        term_out.appendPlainText("Terminal attached to " + str(ROOT))

        def run_cmd() -> None:
            line = term_in.text()
            term_in.clear()
            if not line:
                return
            process.write((line + "\r\n").encode("utf-8"))

        term_in.returnPressed.connect(run_cmd)

        def _cleanup(*_args) -> None:
            if process.state() != QProcess.ProcessState.NotRunning:
                process.kill()
                process.waitForFinished(1500)

        window.destroyed.connect(_cleanup)
        app.aboutToQuit.connect(_cleanup)

    window.show()
    if smoke:
        window.close()
        return 0
    return int(app.exec())


def file_roots() -> Iterable[tuple[str, Path]]:
    return FILE_ROOTS
