"""Automatic small-SLM route while the container is paging.

The router reads memory. It does not read the chat request, the picker id,
or the prompt. Nemotron Lightning stays loaded. Prompt-training is not
decided here; the chat service keeps those turns on the 7B lane.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any


SLM_MODEL_ID = "qwen2.5-0.5b-instruct"
SLM_GGUF = (
    "/opt/engel/models-active/llm/qwen2.5-0.5b-instruct/"
    "qwen2.5-0.5b-instruct-q5_k_m.gguf"
)


def enabled() -> bool:
    raw = os.environ.get("ENGEL_SWAP_SLM_FALLBACK", "1").strip().casefold()
    return raw not in {"0", "false", "off", "no"}


def _parse_byte_field(raw: str) -> int | None:
    text = str(raw or "").strip()
    if not text or text == "max":
        return None
    try:
        value = int(text)
    except ValueError:
        return None
    if value < 0:
        return None
    return value


def read_cgroup(root: Path | None = None) -> dict[str, int]:
    base = root or Path("/sys/fs/cgroup")
    found: dict[str, int] = {}
    for name in ("memory.current", "memory.high", "memory.max", "memory.swap.current"):
        try:
            raw = (base / name).read_text(encoding="utf-8")
        except OSError:
            continue
        value = _parse_byte_field(raw)
        if value is not None:
            found[name] = value
    return found


def pressure_reason(
    meminfo: str | None = None,
    cgroup: dict[str, int] | None = None,
) -> str:
    """Why the big lane should stand down. Empty when it may run."""
    from engel_conversation_work_memory import swap_in_use

    if swap_in_use(meminfo):
        return "host_paging"
    stats = read_cgroup() if cgroup is None else cgroup
    swap_current = int(stats.get("memory.swap.current") or 0)
    if swap_current > 0:
        return "cgroup_swap"
    high = int(stats.get("memory.high") or 0)
    current = int(stats.get("memory.current") or 0)
    if high > 0 and current > 0:
        try:
            ratio = float(os.environ.get("ENGEL_SWAP_SLM_HEADROOM_RATIO", "0.85") or "0.85")
        except ValueError:
            ratio = 0.85
        ratio = min(0.99, max(0.5, ratio))
        if current >= int(high * ratio):
            return "near_memory_cap"
    return ""


def big_lane_blocked(
    meminfo: str | None = None,
    cgroup: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Automatic route. Memory only. A model name on the request cannot override it."""
    if not enabled():
        return {"blocked": False, "reason": "disabled", "model_id": SLM_MODEL_ID, "automatic": True}
    reason = pressure_reason(meminfo, cgroup)
    if reason:
        return {
            "blocked": True,
            "reason": reason,
            "model_id": SLM_MODEL_ID,
            "model_path": SLM_GGUF,
            "automatic": True,
        }
    return {"blocked": False, "reason": "clear", "model_id": SLM_MODEL_ID, "automatic": True}
