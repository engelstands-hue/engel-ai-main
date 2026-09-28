"""System stats and limp-mode control for the Engel LAN monitor endpoint.

CPU load uses psutil (reliable cross-platform).
CPU temp requires OpenHardwareMonitor or LibreHardwareMonitor running on the
host and exposing the WMI root\\OpenHardwareMonitor namespace — otherwise None.
GPU stats use pynvml (NVIDIA) or GPUtil as fallback — otherwise None.
Limp mode switches the Windows power plan to Power Saver and back.
"""
from __future__ import annotations

import base64
import os
import subprocess
import threading
from pathlib import Path

import psutil

_lock = threading.Lock()
_limp_active = False

_POWER_SAVER_GUID = "a1841308-3541-4fab-bc81-f71556f20b4a"
_BALANCED_GUID = "381b4222-f694-41f0-9685-ff5bb260df2e"

_MEDIA_EXT = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
_MEDIA_DIRS = [
    Path.home() / "Desktop",
    Path.home() / "Downloads",
    Path.home() / "Pictures",
]


def cpu_load() -> float:
    return psutil.cpu_percent(interval=0.2)


def cpu_temp() -> float | None:
    try:
        import wmi  # type: ignore
        for ns in ("root\\OpenHardwareMonitor", "root\\LibreHardwareMonitor"):
            try:
                w = wmi.WMI(namespace=ns)
                for s in w.Sensor():
                    if s.SensorType == "Temperature" and "CPU" in (s.Name or ""):
                        return round(float(s.Value), 1)
            except Exception:
                continue
    except Exception:
        pass
    return None


def gpu_stats() -> dict[str, object]:
    try:
        import pynvml  # type: ignore
        pynvml.nvmlInit()
        h = pynvml.nvmlDeviceGetHandleByIndex(0)
        u = pynvml.nvmlDeviceGetUtilizationRates(h)
        t = pynvml.nvmlDeviceGetTemperature(h, pynvml.NVML_TEMPERATURE_GPU)
        n = pynvml.nvmlDeviceGetName(h)
        if isinstance(n, bytes):
            n = n.decode()
        return {"load": int(u.gpu), "temp": int(t), "name": n}
    except Exception:
        pass
    try:
        import GPUtil  # type: ignore
        gpus = GPUtil.getGPUs()
        if gpus:
            g = gpus[0]
            return {
                "load": round(g.load * 100, 1),
                "temp": g.temperature,
                "name": g.name,
            }
    except Exception:
        pass
    return {"load": None, "temp": None, "name": None}


def system_stats() -> dict[str, object]:
    g = gpu_stats()
    return {
        "cpu_load": cpu_load(),
        "cpu_temp": cpu_temp(),
        "gpu_load": g["load"],
        "gpu_temp": g["temp"],
        "gpu_name": g["name"],
        "limp_mode": limp_active(),
    }


def limp_active() -> bool:
    with _lock:
        return _limp_active


def set_limp(enabled: bool) -> dict[str, object]:
    global _limp_active
    guid = _POWER_SAVER_GUID if enabled else _BALANCED_GUID
    try:
        subprocess.run(
            ["powercfg", "/setactive", guid],
            capture_output=True,
            timeout=10,
        )
    except Exception:
        pass
    with _lock:
        _limp_active = enabled
    msg = (
        "LIMP MODE ON — Power Saver plan active. Performance reduced."
        if enabled
        else "Limp mode OFF — Balanced plan restored."
    )
    return {"ok": True, "limp_mode": enabled, "message": msg}


def latest_media() -> dict[str, object] | None:
    best: Path | None = None
    best_mtime = -1.0
    for d in _MEDIA_DIRS:
        if not d.is_dir():
            continue
        for f in d.iterdir():
            if f.suffix.lower() not in _MEDIA_EXT:
                continue
            try:
                mt = f.stat().st_mtime
                if mt > best_mtime:
                    best_mtime = mt
                    best = f
            except OSError:
                continue
    if best is None:
        return None
    try:
        data = base64.b64encode(best.read_bytes()).decode()
    except OSError:
        return None
    ext = best.suffix.lower().lstrip(".")
    mime = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"
    return {"filename": best.name, "mime": mime, "image_base64": data}
