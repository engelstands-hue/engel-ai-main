from __future__ import annotations

import ctypes
import json
import subprocess
import sys
import threading
import time
import tkinter as tk
import urllib.request
from pathlib import Path
from tkinter import messagebox, scrolledtext

from PIL import Image, ImageEnhance, ImageOps, ImageTk

import engel_connection_loop_doctor as doctor


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports" / "connection_loop_doctor"
CHAT_RUNNER = ROOT / "tools" / "run_engel_ui_chat_meeting_room_llm.py"
REPAIR_TERMINAL = ROOT / "scripts" / "Open-EngelCt246RepairTerminal.cmd"
PERSISTENT_FORWARD = ROOT / "scripts" / "Install-EngelCt246PersistentForward.cmd"
BRAND_BG = ROOT / "assets" / "branding" / "final" / "engel_desktop_bg_final.png"
BRAND_ICON = ROOT / "assets" / "branding" / "final" / "engel_icon_final.ico"
APP_ICON_PNG = ROOT / "assets" / "branding" / "final" / "engel_connection_doctor_icon.png"
APP_ICON_ICO = ROOT / "assets" / "branding" / "final" / "engel_connection_doctor_icon.ico"


COLORS = {
    "bg": "#070d1c",
    "chrome": "#091326",
    "sidebar": "#101626",
    "panel": "#1a2030",
    "panel2": "#111827",
    "line": "#263653",
    "text": "#f7f7fb",
    "muted": "#9fb0c6",
    "dim": "#61718d",
    "cyan": "#00e5ff",
    "green": "#18f28f",
    "yellow": "#ffc857",
    "red": "#ff5f78",
    "orange": "#ffbd4a",
    "button_text": "#07111d",
}


def _short_check_name(name: str) -> str:
    return {
        "ct_ssh_tcp": "CT SSH",
        "proxmox_host_ssh_tcp": "Proxmox SSH",
        "proxmox_web_ui_tcp": "Proxmox UI",
        "rog_ssh_key": "ROG key",
        "windows_persistent_link_task": "Win task",
        "local_chat_tunnel_tcp": "Chat port",
        "local_chat_health": "Chat health",
        "local_meeting_room_tunnel_tcp": "Room port",
        "local_meeting_room_health": "Room health",
        "local_office_tcp": "Office",
        "known_language_stubs": "Languages",
    }.get(name, name.replace("_", " "))


def _run_subprocess(command: list[str], timeout: int) -> dict[str, object]:
    try:
        completed = subprocess.run(
            command,
            cwd=str(ROOT),
            text=True,
            capture_output=True,
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return {
            "ok": completed.returncode == 0,
            "exit_code": completed.returncode,
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip(),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "exit_code": 124,
            "stdout": (exc.stdout or "").strip() if isinstance(exc.stdout, str) else "",
            "stderr": "timeout",
        }
    except OSError as exc:
        return {"ok": False, "exit_code": 127, "stdout": "", "stderr": str(exc)}


def _branded_strip(width: int, height: int, brightness: float = 0.44) -> ImageTk.PhotoImage | None:
    if not BRAND_BG.is_file():
        return None
    try:
        image = Image.open(BRAND_BG).convert("RGBA")
        image = ImageOps.fit(image, (width, height), method=Image.Resampling.LANCZOS, centering=(0.5, 0.45))
        image = ImageEnhance.Brightness(image).enhance(brightness)
        overlay = Image.new("RGBA", (width, height), (6, 13, 28, 108))
        image.alpha_composite(overlay)
        return ImageTk.PhotoImage(image)
    except Exception:
        return None


class EngelConnectionDoctorApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Engel Connection Doctor")
        self.geometry("1180x780")
        self.minsize(980, 640)
        self.configure(bg=COLORS["bg"])
        self._running = False
        self._last_payload: dict[str, object] = {}
        self._app_icon_image: tk.PhotoImage | None = None
        self._header_icon_image: tk.PhotoImage | None = None
        self._title_icon_image: tk.PhotoImage | None = None
        self._brand_strip_image: ImageTk.PhotoImage | None = None
        self._brand_hero_image: ImageTk.PhotoImage | None = None
        self._status_var = tk.StringVar(value="starting")
        self._apply_window_icon()
        self.after(50, self._enable_dark_title_bar)
        self._build()
        self.after(300, lambda: self._start_worker("Checking Engel chat link", self._check_worker))

    def _enable_dark_title_bar(self) -> None:
        if not sys.platform.startswith("win"):
            return
        try:
            root_hwnd = self.winfo_id()
            parent_hwnd = ctypes.windll.user32.GetParent(root_hwnd)
            value = ctypes.c_int(1)
            for hwnd in {root_hwnd, parent_hwnd}:
                if not hwnd:
                    continue
                for attribute in (20, 19):
                    ctypes.windll.dwmapi.DwmSetWindowAttribute(
                        hwnd,
                        attribute,
                        ctypes.byref(value),
                        ctypes.sizeof(value),
                    )
        except Exception:
            return

    def _apply_window_icon(self) -> None:
        if APP_ICON_ICO.is_file():
            try:
                self.iconbitmap(str(APP_ICON_ICO))
            except tk.TclError:
                pass
        elif BRAND_ICON.is_file():
            try:
                self.iconbitmap(str(BRAND_ICON))
            except tk.TclError:
                pass
        if APP_ICON_PNG.is_file():
            try:
                self._app_icon_image = tk.PhotoImage(file=str(APP_ICON_PNG))
                self.iconphoto(True, self._app_icon_image)
            except tk.TclError:
                self._app_icon_image = None

    def _build(self) -> None:
        root = tk.Frame(self, bg=COLORS["bg"])
        root.pack(fill="both", expand=True, padx=18, pady=16)

        chrome = tk.Frame(root, bg=COLORS["chrome"], highlightthickness=1, highlightbackground="#12213b")
        chrome.pack(fill="x", pady=(0, 0))

        dots = tk.Canvas(chrome, width=56, height=18, bg=COLORS["chrome"], bd=0, highlightthickness=0)
        dots.pack(side="left", padx=14, pady=9)
        for color in ("#ff5f57", "#ffbd2e", "#28c840"):
            index = ("#ff5f57", "#ffbd2e", "#28c840").index(color)
            x = 7 + index * 18
            dots.create_oval(x, 4, x + 11, 15, fill=color, outline=color)

        logo = tk.Frame(chrome, bg=COLORS["chrome"])
        logo.pack(side="left", pady=8)
        tk.Label(
            logo,
            text="ENGEL",
            bg=COLORS["chrome"],
            fg=COLORS["text"],
            font=("Segoe UI", 13, "bold"),
        ).pack(side="left")
        tk.Label(
            chrome,
            text="  COSMIC SWARM OS",
            bg=COLORS["chrome"],
            fg=COLORS["dim"],
            font=("Segoe UI", 7, "bold"),
        ).pack(side="left", pady=10)
        tk.Label(
            chrome,
            text="REAL DEVICES",
            bg="#0d2434",
            fg=COLORS["cyan"],
            padx=8,
            pady=2,
            font=("Segoe UI", 7, "bold"),
        ).pack(side="right", padx=14, pady=8)

        tk.Frame(root, bg=COLORS["cyan"], height=2).pack(fill="x")

        shell = tk.Frame(root, bg=COLORS["bg"])
        shell.pack(fill="both", expand=True, pady=(12, 0))

        sidebar = tk.Frame(shell, bg=COLORS["sidebar"], width=208, highlightthickness=1, highlightbackground="#1d2b44")
        sidebar.pack(side="left", fill="y", padx=(0, 12))
        sidebar.pack_propagate(False)

        self._brand_strip_image = _branded_strip(178, 92)
        if self._brand_strip_image is not None:
            tk.Label(
                sidebar,
                image=self._brand_strip_image,
                bg=COLORS["sidebar"],
                highlightthickness=1,
                highlightbackground=COLORS["line"],
            ).pack(fill="x", padx=14, pady=(14, 12))

        if APP_ICON_PNG.is_file():
            try:
                self._header_icon_image = tk.PhotoImage(file=str(APP_ICON_PNG)).subsample(5, 5)
                tk.Label(
                    sidebar,
                    image=self._header_icon_image,
                    bg=COLORS["sidebar"],
                ).pack(anchor="w", padx=18, pady=(18, 8))
            except tk.TclError:
                self._header_icon_image = None

        title_top_pad = 0 if self._header_icon_image or self._brand_strip_image else 18
        tk.Label(
            sidebar,
            text="Connection",
            bg=COLORS["sidebar"],
            fg=COLORS["text"],
            anchor="w",
            font=("Segoe UI", 12, "bold"),
        ).pack(fill="x", padx=18, pady=(title_top_pad, 2))
        tk.Label(
            sidebar,
            text="Doctor App",
            bg=COLORS["sidebar"],
            fg=COLORS["muted"],
            anchor="w",
            font=("Segoe UI", 9),
        ).pack(fill="x", padx=18, pady=(0, 18))
        for label, value in [
            ("Server", "CT 246"),
            ("Chat", "127.0.0.1:24680"),
            ("Room", "127.0.0.1:8790"),
            ("Office", "127.0.0.1:3000"),
            ("Storage", "SSD-only"),
        ]:
            box = tk.Frame(sidebar, bg="#0d1424", highlightthickness=1, highlightbackground="#213451")
            box.pack(fill="x", padx=14, pady=(0, 10))
            tk.Label(box, text=label, bg="#0d1424", fg=COLORS["dim"], anchor="w", font=("Segoe UI", 8, "bold")).pack(
                fill="x", padx=10, pady=(7, 0)
            )
            tk.Label(box, text=value, bg="#0d1424", fg=COLORS["text"], anchor="w", font=("Consolas", 9, "bold")).pack(
                fill="x", padx=10, pady=(1, 8)
            )

        main = tk.Frame(shell, bg=COLORS["bg"])
        main.pack(side="left", fill="both", expand=True)

        header = tk.Canvas(
            main,
            height=116,
            bg=COLORS["panel2"],
            highlightthickness=1,
            highlightbackground=COLORS["line"],
            bd=0,
        )
        header.pack(fill="x")
        self._brand_hero_image = _branded_strip(960, 116, brightness=0.52)
        if self._brand_hero_image is not None:
            header.create_image(0, 0, image=self._brand_hero_image, anchor="nw")
        header.create_rectangle(0, 0, 980, 116, outline=COLORS["line"], width=1)

        title_x = 24
        if self._app_icon_image is not None:
            try:
                title_icon = tk.PhotoImage(file=str(APP_ICON_PNG)).subsample(8, 8)
                self._title_icon_image = title_icon
                header.create_image(title_x, 27, image=title_icon, anchor="nw")
                title_x = 72
            except tk.TclError:
                pass
        header.create_text(
            title_x,
            29,
            text="Engel Connection Doctor",
            fill=COLORS["text"],
            anchor="nw",
            font=("Segoe UI", 24, "bold"),
        )
        header.create_text(
            title_x,
            72,
            text="Server chat, Agent Meeting Room, office, and phone route repair for Engel AI Main.",
            fill="#b9c8dc",
            anchor="nw",
            font=("Segoe UI", 10),
        )

        self.status_pill = tk.Label(
            header,
            textvariable=self._status_var,
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            padx=14,
            pady=6,
            font=("Segoe UI", 10, "bold"),
        )
        header.create_window(936, 30, window=self.status_pill, anchor="ne")

        actions = tk.Frame(main, bg=COLORS["bg"])
        actions.pack(fill="x", pady=(12, 12))

        self._button(
            actions,
            "Check connection",
            lambda: self._start_worker("Checking Engel connection", self._check_worker),
        )
        self._button(actions, "Repair connection", self._confirm_fix)
        self._button(actions, "Real chat test", lambda: self._start_worker("Running real chat test", self._chat_worker))
        self._button(actions, "Repair terminal", self._open_repair_terminal, style="outline")
        self._button(actions, "Persistent host forward", self._open_persistent_forward, style="outline")
        self._button(actions, "Open reports", self._open_reports, style="outline")

        body = tk.PanedWindow(main, orient=tk.HORIZONTAL, bg=COLORS["bg"], sashwidth=6, bd=0)
        body.pack(fill="both", expand=True)

        left = tk.Frame(body, bg=COLORS["bg"])
        right = tk.Frame(body, bg=COLORS["bg"])
        body.add(left, minsize=430)
        body.add(right, minsize=480)

        self.summary = tk.Label(
            left,
            text="Waiting for first check...",
            bg=COLORS["panel"],
            fg=COLORS["text"],
            justify="left",
            anchor="nw",
            padx=16,
            pady=14,
            font=("Segoe UI", 11, "bold"),
            highlightthickness=1,
            highlightbackground=COLORS["line"],
        )
        self.summary.pack(fill="x", pady=(0, 12))

        self.check_grid = tk.Frame(left, bg=COLORS["bg"])
        self.check_grid.pack(fill="both", expand=True)
        self.check_labels: dict[str, tk.Label] = {}

        right_top = tk.Frame(right, bg=COLORS["panel"], highlightthickness=1, highlightbackground=COLORS["line"])
        right_top.pack(fill="x", pady=(0, 12))
        tk.Label(
            right_top,
            text="Live Route",
            bg=COLORS["panel"],
            fg=COLORS["text"],
            font=("Segoe UI", 14, "bold"),
        ).pack(anchor="w", padx=14, pady=(12, 4))
        route_text = (
            "Chat: http://127.0.0.1:24680/health\n"
            "Meeting Room: http://127.0.0.1:8790/health\n"
            "Office: http://127.0.0.1:3000/office\n"
            "Server: ssh root@192.0.2.50 -p 24622\n"
            "Storage: SSD-only runtime; Vault intentionally unused"
        )
        tk.Label(
            right_top,
            text=route_text,
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            justify="left",
            anchor="w",
            font=("Consolas", 10),
        ).pack(fill="x", padx=14, pady=(0, 12))

        self.output = scrolledtext.ScrolledText(
            right,
            wrap="word",
            bg=COLORS["panel2"],
            fg="#dce9f6",
            insertbackground="#dce9f6",
            relief="flat",
            font=("Consolas", 10),
            highlightthickness=1,
            highlightbackground=COLORS["line"],
        )
        self.output.pack(fill="both", expand=True)
        self._write_output("Engel Connection Doctor App ready.\n")

    def _button(self, parent: tk.Frame, text: str, command, style: str = "solid") -> None:
        if style == "outline":
            bg = COLORS["panel"]
            fg = COLORS["text"]
            active = COLORS["line"]
        else:
            bg = COLORS["cyan"]
            fg = COLORS["button_text"]
            active = COLORS["green"]
        button = tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            activebackground=active,
            activeforeground=fg,
            relief="flat",
            padx=14,
            pady=9,
            cursor="hand2",
            font=("Segoe UI", 10, "bold"),
        )
        button.pack(side="left", padx=(0, 8), pady=(0, 4))

    def _start_worker(self, status: str, target) -> None:
        if self._running:
            return
        self._running = True
        self._status_var.set(status)
        self.status_pill.configure(fg=COLORS["yellow"])
        threading.Thread(target=self._worker_wrapper, args=(target,), daemon=True).start()

    def _worker_wrapper(self, target) -> None:
        try:
            result = target()
            self.after(0, lambda: self._apply_result(result))
        except Exception as exc:
            self.after(0, lambda: self._apply_error(exc))

    def _check_worker(self) -> dict[str, object]:
        args = doctor.parse_args(["--json"])
        return doctor.run_doctor(args)

    def _confirm_fix(self) -> None:
        if self._running:
            return
        confirmed = messagebox.askokcancel(
            "Repair connection?",
            "This starts EngelChatLinkSvc and the local SSH tunnel, then checks Chat and Meeting Room again.\n\n"
            "It will not start providers or training.",
            parent=self,
            default=messagebox.CANCEL,
        )
        if confirmed:
            self._start_worker("Repairing Engel connection", self._fix_worker)

    def _fix_worker(self) -> dict[str, object]:
        args = doctor.parse_args(["--json", "--fix"])
        return doctor.run_doctor(args)

    def _chat_worker(self) -> dict[str, object]:
        command = [
            sys.executable,
            str(CHAT_RUNNER),
            "--prompt",
            "quick check: can Engel talk through the server and save memory?",
            "--timeout",
            "60",
            "--max-tokens",
            "120",
        ]
        run = _run_subprocess(command, timeout=90)
        payload: dict[str, object] = {
            "schema": "engel_connection_doctor_chat_test_v1",
            "ok": False,
            "status": "chat test failed",
            "checks": [],
            "actions": [{"name": "real_chat_test", **run}],
            "receipt_path": "",
        }
        stdout = str(run.get("stdout") or "")
        if stdout:
            try:
                parsed = json.loads(stdout)
            except json.JSONDecodeError:
                parsed = {}
            if isinstance(parsed, dict):
                payload.update(
                    {
                        "ok": bool(parsed.get("ok")),
                        "status": str(parsed.get("status") or "chat test returned"),
                        "reply": parsed.get("assistant_reply") or parsed.get("reply"),
                        "main_server_chat_used": parsed.get("main_server_chat_used"),
                        "meeting_room_server_used": parsed.get("meeting_room_server_used"),
                        "persistent_chat_memory_appended": parsed.get("persistent_chat_memory_appended"),
                        "receipt_path": parsed.get("ui_meeting_room_receipt_path") or parsed.get("receipt_path") or "",
                    }
                )
        return payload

    def _apply_result(self, payload: dict[str, object]) -> None:
        self._running = False
        self._last_payload = payload
        ok = bool(payload.get("ok"))
        status = str(payload.get("status") or ("healthy" if ok else "needs attention"))
        self._status_var.set(status)
        self.status_pill.configure(fg=COLORS["green"] if ok else COLORS["red"])
        self._render_summary(payload)
        self._render_checks(payload)
        self._write_output(self._format_payload(payload))

    def _apply_error(self, exc: Exception) -> None:
        self._running = False
        self._status_var.set("doctor app error")
        self.status_pill.configure(fg=COLORS["red"])
        self._write_output(f"Doctor app error:\n{exc!r}")

    def _render_summary(self, payload: dict[str, object]) -> None:
        ok = bool(payload.get("ok"))
        lines = [
            f"Status: {payload.get('status')}",
            f"OK: {ok}",
            f"Diagnosis: {payload.get('diagnosis', '')}",
            f"Receipt: {payload.get('receipt_path', '')}",
        ]
        if payload.get("reply"):
            lines.extend(["", "Chat reply:", str(payload.get("reply"))])
        self.summary.configure(
            text="\n".join(lines),
            fg=COLORS["green"] if ok else COLORS["red"],
        )

    def _render_checks(self, payload: dict[str, object]) -> None:
        for widget in self.check_grid.winfo_children():
            widget.destroy()
        checks = payload.get("checks")
        if not isinstance(checks, list):
            checks = []
        if not checks and payload.get("main_server_chat_used") is not None:
            checks = [
                {
                    "name": "main_server_chat_used",
                    "ok": bool(payload.get("main_server_chat_used")),
                    "status": str(payload.get("main_server_chat_used")),
                },
                {
                    "name": "meeting_room_server_used",
                    "ok": bool(payload.get("meeting_room_server_used")),
                    "status": str(payload.get("meeting_room_server_used")),
                },
                {
                    "name": "persistent_chat_memory_appended",
                    "ok": bool(payload.get("persistent_chat_memory_appended")),
                    "status": str(payload.get("persistent_chat_memory_appended")),
                },
            ]
        for index, check in enumerate(checks):
            if not isinstance(check, dict):
                continue
            row = index // 2
            col = index % 2
            ok = bool(check.get("ok"))
            card = tk.Frame(
                self.check_grid,
                bg=COLORS["panel"],
                highlightthickness=1,
                highlightbackground=COLORS["green"] if ok else COLORS["red"],
            )
            card.grid(row=row, column=col, sticky="nsew", padx=4, pady=4)
            self.check_grid.grid_columnconfigure(col, weight=1)
            tk.Label(
                card,
                text=("PASS  " if ok else "FAIL  ") + _short_check_name(str(check.get("name", ""))),
                bg=COLORS["panel"],
                fg=COLORS["green"] if ok else COLORS["red"],
                anchor="w",
                font=("Segoe UI", 10, "bold"),
            ).pack(fill="x", padx=10, pady=(8, 2))
            tk.Label(
                card,
                text=str(check.get("status", ""))[:220],
                bg=COLORS["panel"],
                fg=COLORS["muted"],
                justify="left",
                anchor="nw",
                wraplength=245,
                font=("Consolas", 9),
            ).pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def _format_payload(self, payload: dict[str, object]) -> str:
        lines = [
            f"Status: {payload.get('status')}",
            f"OK: {payload.get('ok')}",
            f"Receipt: {payload.get('receipt_path', '')}",
        ]
        actions = payload.get("actions")
        if isinstance(actions, list) and actions:
            lines.append("")
            lines.append("Actions:")
            for action in actions:
                if isinstance(action, dict):
                    detail = action.get("reason") or action.get("status") or action.get("stderr") or action.get("stdout")
                    lines.append(f"- {action.get('name')}: {detail}")
        lines.append("")
        lines.append(json.dumps(payload, indent=2))
        return "\n".join(lines)

    def _write_output(self, text: str) -> None:
        self.output.delete("1.0", "end")
        self.output.insert("end", text)
        self.output.see("1.0")

    def _open_reports(self) -> None:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(["explorer.exe", str(REPORT_DIR)])

    def _open_repair_terminal(self) -> None:
        if REPAIR_TERMINAL.is_file():
            subprocess.Popen(["cmd.exe", "/c", "start", "", str(REPAIR_TERMINAL)], cwd=str(ROOT))
            self._write_output("Opened the CT 246 repair terminal. Enter the Proxmox password there if it asks.")
        else:
            self._write_output(f"Repair terminal script missing:\n{REPAIR_TERMINAL}")

    def _open_persistent_forward(self) -> None:
        if PERSISTENT_FORWARD.is_file():
            subprocess.Popen(["cmd.exe", "/c", "start", "", str(PERSISTENT_FORWARD)], cwd=str(ROOT))
            self._write_output("Opened the persistent host forward installer. Enter the Proxmox password there if it asks.")
        else:
            self._write_output(f"Persistent forward script missing:\n{PERSISTENT_FORWARD}")


if __name__ == "__main__":
    EngelConnectionDoctorApp().mainloop()
