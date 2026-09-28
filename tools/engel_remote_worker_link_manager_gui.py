"""Visible local GUI for Engel's dedicated Android Remote Worker link."""

from __future__ import annotations

import json
import sys
import tkinter as tk
from tkinter import messagebox, scrolledtext

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import engel_remote_worker_link_manager as link_manager


class LinkManagerGui(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Engel Dedicated Phone Link")
        self.geometry("980x720")
        self.host_var = tk.StringVar(value="0.0.0.0")
        self.port_var = tk.StringVar(value="8765")
        self.allow_lan_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="Stopped")
        self.auto_var = tk.StringVar(value="Disabled")
        self.claim_lock_var = tk.StringVar(value="Unknown")
        self.last_seen_var = tk.StringVar(value="No phone seen")
        self.token_var = tk.StringVar(value="No token rotated")
        self._build()
        self.refresh_status()

    def _build(self) -> None:
        header = tk.Frame(self, padx=12, pady=10)
        header.pack(fill=tk.X)
        tk.Label(header, text="Engel Dedicated Phone Link", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        tk.Label(header, text="Phone role: Dedicated Engel Remote Worker").pack(anchor="w")
        tk.Label(header, text="Control direction: Engel controls phone").pack(anchor="w")
        tk.Label(header, text="Phone does not control Engel").pack(anchor="w")

        badges = tk.Frame(self, padx=12)
        badges.pack(fill=tk.X)
        for badge in [
            "LAN ONLY",
            "ENGEL -> PHONE CONTROL ONLY",
            "PHONE CANNOT CONTROL ENGEL",
            "NO AUTO-APPLY",
            "RESULTS UNTRUSTED UNTIL REVIEW",
        ]:
            tk.Label(badges, text=badge, relief=tk.RIDGE, padx=8, pady=4).pack(side=tk.LEFT, padx=4, pady=4)

        settings = tk.Frame(self, padx=12, pady=8)
        settings.pack(fill=tk.X)
        tk.Label(settings, text="Host/IP").grid(row=0, column=0, sticky="w")
        tk.Entry(settings, textvariable=self.host_var, width=22).grid(row=1, column=0, sticky="w", padx=(0, 8))
        tk.Label(settings, text="Port").grid(row=0, column=1, sticky="w")
        tk.Entry(settings, textvariable=self.port_var, width=10).grid(row=1, column=1, sticky="w", padx=(0, 8))
        tk.Checkbutton(settings, text="Allow LAN bind", variable=self.allow_lan_var).grid(row=1, column=2, sticky="w")

        status = tk.Frame(self, padx=12, pady=8)
        status.pack(fill=tk.X)
        for row, (label, var) in enumerate(
            [
                ("Link status", self.status_var),
                ("Auto Worker status", self.auto_var),
                ("Claim-lock status", self.claim_lock_var),
                ("Paired phone identity / last seen", self.last_seen_var),
                ("Pairing token", self.token_var),
            ]
        ):
            tk.Label(status, text=label + ":", width=26, anchor="w").grid(row=row, column=0, sticky="w")
            tk.Label(status, textvariable=var, anchor="w").grid(row=row, column=1, sticky="w")

        buttons = tk.Frame(self, padx=12, pady=8)
        buttons.pack(fill=tk.X)
        for label, command in [
            ("Start Link", self.start_link),
            ("Stop Link", self.stop_link),
            ("Restart Link", self.restart_link),
            ("Rotate Token", self.rotate_token),
            ("Copy Pairing Info", self.copy_pairing_info),
            ("Refresh Status", self.refresh_status),
            ("Check Phone Now", self.check_now),
            ("Enable Auto Worker", self.enable_auto_worker),
            ("Disable Auto Worker", self.disable_auto_worker),
            ("Pause Worker", self.disable_auto_worker),
        ]:
            tk.Button(buttons, text=label, command=command).pack(side=tk.LEFT, padx=4, pady=4)

        self.output = scrolledtext.ScrolledText(self, height=18, wrap=tk.WORD)
        self.output.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)

    def _write(self, payload: object) -> None:
        self.output.delete("1.0", tk.END)
        self.output.insert(tk.END, json.dumps(payload, indent=2, sort_keys=True) if isinstance(payload, dict) else str(payload))

    def _host_port(self) -> tuple[str, int]:
        return self.host_var.get().strip(), int(self.port_var.get().strip())

    def _run(self, action) -> None:
        try:
            payload = action()
            self._write(payload)
            self._update_summary(payload if isinstance(payload, dict) else link_manager.link_status())
        except Exception as exc:  # GUI boundary: show bounded local errors only.
            messagebox.showwarning("Engel Dedicated Phone Link", str(exc))
            self._write({"ok": False, "error": str(exc), "auto_apply": False})

    def _update_summary(self, payload: dict[str, object]) -> None:
        self.status_var.set(str(payload.get("link_status", payload.get("status_truth", "Unknown"))))
        self.auto_var.set("Enabled" if payload.get("auto_worker_enabled") else "Disabled")
        self.claim_lock_var.set(str(payload.get("claim_lock_status", "unknown")))
        identity = payload.get("paired_phone_identity")
        last_seen = payload.get("last_seen_utc")
        self.last_seen_var.set(f"{identity or 'No phone identity'} / {last_seen or 'not seen'}")
        hint = payload.get("pairing_token_hint")
        expires = payload.get("pairing_token_expires_at_utc")
        if hint:
            self.token_var.set(f"{hint}, expires {expires}")

    def refresh_status(self) -> None:
        self._run(link_manager.link_status)

    def start_link(self) -> None:
        self._run(lambda: link_manager.start_link(*self._host_port(), self.allow_lan_var.get()))

    def stop_link(self) -> None:
        self._run(link_manager.stop_link)

    def restart_link(self) -> None:
        self._run(lambda: link_manager.restart_link(*self._host_port(), self.allow_lan_var.get()))

    def rotate_token(self) -> None:
        self._run(link_manager.rotate_token)

    def copy_pairing_info(self) -> None:
        status = link_manager.link_status()
        token = status.get("pairing_token_hint") or "rotate token first"
        text = f"Host: {status.get('host')}\nPort: {status.get('port')}\nToken hint: {token}\nRole: Dedicated Engel Remote Worker"
        self.clipboard_clear()
        self.clipboard_append(text)
        self._write({"copied": "pairing info without full token", "auto_apply": False})

    def check_now(self) -> None:
        self._run(link_manager.check_now)

    def enable_auto_worker(self) -> None:
        self._run(link_manager.enable_auto_worker)

    def disable_auto_worker(self) -> None:
        self._run(link_manager.disable_auto_worker)


def main() -> None:
    app = LinkManagerGui()
    app.mainloop()


if __name__ == "__main__":
    main()
