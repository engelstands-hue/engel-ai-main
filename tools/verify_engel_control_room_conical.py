#!/usr/bin/env python3
"""Control Room is conically wired to Engel AI Main parts, not the demo Llama catalogue."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engel_control_room.ai.provider import EngelConicalProvider, build_provider
from engel_control_room.config import Config
from engel_control_room.conical_parts import extra_workers, list_models, parse_df_line, storage_from_health
from engel_control_room.state import AppState


def check(name: str, cond: bool, failures: list[str]) -> None:
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        failures.append(name)


def main() -> int:
    failures: list[str] = []
    cfg_paths = [
        ROOT / "data" / "config.json",
        Path(r"D:\EngelControlRoom_build\dist\data\config.json"),
    ]
    for path in cfg_paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        check(path.name + " provider is engel_conical", data.get("ai_provider") == "engel_conical", failures)
        enabled_workers = [n["name"] for n in data.get("nodes") or [] if n.get("enabled") and n.get("kind") == "worker"]
        check(path.name + " one Sub-Engel worker", enabled_workers.count("Sub-Engel") == 1, failures)
        check(path.name + " no duplicate nest worker", "DESKTOP-UE5A6GG" not in enabled_workers and "Sub-Engel Beta" not in enabled_workers, failures)
        check(path.name + " CT246 enabled", any(n.get("enabled") and n.get("kind") == "ai_core" for n in data.get("nodes") or []), failures)
        check(path.name + " conical enabled", any(n.get("enabled") and n.get("kind") == "conical" for n in data.get("nodes") or []), failures)
        check(path.name + " meeting room enabled", any(n.get("enabled") and n.get("kind") == "meeting_room" for n in data.get("nodes") or []), failures)
        check(path.name + " Proxmox stays off without token", not any(n.get("enabled") and n.get("connector") == "proxmox" for n in data.get("nodes") or []), failures)

    bat = (ROOT / "launch_engel_control_room.bat").read_text(encoding="utf-8", errors="replace")
    check("repo bat uses wscript or quoted pythonw", "wscript.exe" in bat and "Start-Conical-ControlRoom.vbs" in bat, failures)
    dist_bat = Path(r"D:\EngelControlRoom_build\dist\Start-Conical-ControlRoom.bat")
    dist_vbs = Path(r"D:\EngelControlRoom_build\dist\Start-Conical-ControlRoom.vbs")
    check("no-space dist bat exists", dist_bat.is_file(), failures)
    check("no-space dist vbs exists", dist_vbs.is_file(), failures)
    if dist_vbs.is_file():
        vtxt = dist_vbs.read_text(encoding="utf-8", errors="replace")
        check("vbs launches pythonw", "pythonw.exe" in vtxt and "run_engel_control_room.py" in vtxt, failures)
    launch_py = (ROOT / "run_engel_control_room.py").read_text(encoding="utf-8", errors="replace")
    check("launcher reuses a live window", "FindWindowW" in launch_py and "_already_running" in launch_py, failures)
    ps1 = (ROOT / "scripts" / "Start-EngelControlRoom.ps1").read_text(encoding="utf-8", errors="replace")
    check("shortcut target is pythonw", "TargetPath = $PythonW" in ps1, failures)

    src = (ROOT / "engel_control_room" / "ai" / "provider.py").read_text(encoding="utf-8")
    check("generate is chat_only", '"chat_only": True' in src, failures)
    check("no Llama 70B in conical provider", "Llama 3 70B" not in src.split("class EngelConicalProvider", 1)[-1], failures)

    df = parse_df_line("984G  382G  552G  41%")
    check("df parser total", abs(df["total_gb"] - 984) < 1, failures)
    df2 = parse_df_line("/dev/mapper/engel--fast--ssd-vm--246--disk--0  984G  382G  552G  41% /")
    check("df parser ignores device suffix", abs(df2["used_gb"] - 382) < 1 and abs(df2["total_gb"] - 984) < 1, failures)

    fake_health = {
        "ok": True,
        "status": "ready",
        "model_runtime": {
            "lora_runtime_ready": True,
            "lora_runtime_status": {"ready": True},
            "active_model_inventory": {
                "inventory_present": True,
                "model_file_count": 84,
                "model_total_gib": 279.29,
                "df_opt_engel": "/dev/mapper/x  984G  382G  552G  41% /",
            },
        },
        "chat_route_parity": {"discord_seen": True},
        "phone_bridge": {
            "workers": {
                "android_worker_alpha": {"live": False, "observed_ip": "192.168.7.196", "reason": "stale"},
                "android_worker_beta": {"live": True, "observed_ip": "192.168.7.195", "reason": "fresh authenticated phone heartbeat"},
                "android_worker_gamma": {"live": True, "observed_ip": "192.168.7.190", "reason": "fresh authenticated phone heartbeat"},
            }
        },
    }
    swarm = extra_workers(fake_health, overlay_local=False)
    swarm_names = [row[0] for row in swarm]
    check("swarm includes Discord mouths", "Discord mouths" in swarm_names, failures)
    check("swarm includes Android Alpha", "Android Alpha" in swarm_names, failures)
    check("swarm includes Android Beta", "Android Beta" in swarm_names, failures)
    check("swarm includes Android Gamma", "Android Gamma" in swarm_names, failures)
    check("swarm does not use truncated worker ids", "android_worker_alpha" not in swarm_names, failures)
    gamma_row = next((row for row in swarm if row[0] == "Android Gamma"), None)
    check("gamma keeps observed Wi-Fi IP", bool(gamma_row) and gamma_row[1] == "192.168.7.190", failures)
    alpha_row = next((row for row in swarm if row[0] == "Android Alpha"), None)
    check("stale alpha still listed", bool(alpha_row) and str(alpha_row[2].name) == "OFFLINE", failures)
    names = [m.name for m in list_models(fake_health, {"ok": True, "status": "ready"})]
    check("live models include ct246 chat", "engel-ct246-chat" in names, failures)
    check("live models include conical", "engel-conical-cycle" in names, failures)
    check("live models exclude Llama 70B", "Llama 3 70B" not in names, failures)
    storage = storage_from_health(fake_health, {"archive_mounted": True})
    check("storage is CT246 SSD not 20TB demo", storage.total_tb < 2, failures)

    try:
        cfg = Config.load()
        state = AppState(cfg)
        check("state does not seed demo Llama", not any(getattr(m, "name", "") == "Llama 3 70B" for m in state.models), failures)
        check("state does not seed Train Dataset Alpha", not any("Train Dataset" in getattr(t, "name", "") for t in state.tasks), failures)
        provider = build_provider(cfg)
        check("build_provider is engel_conical", provider.name == "engel_conical", failures)
        check("generate stays chat_only", '"chat_only": True' in (ROOT / "engel_control_room" / "ai" / "provider.py").read_text(encoding="utf-8"), failures)
    except Exception as exc:  # noqa: BLE001
        check("AppState loads config (" + type(exc).__name__ + ")", False, failures)

    print(("PASS " if not failures else "FAIL ") + str(len(failures)) + " failures")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
