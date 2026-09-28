#!/usr/bin/env python3
"""NVIDIA Discover endpoints and skill packs for Engel AI Main and Discord mouths.

Local catalog only. No live NVIDIA API. No secrets.
Discover model ids and skill *categories* come from Josh's screenshot.
The work those categories claim is done by Engel local skills already on D:.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LANE_MAP_PATH = ROOT / "memory" / "ENGEL_NVIDIA_NIM_LANE_MAP_V1.json"
SKILLS_PATH = ROOT / "memory" / "ENGEL_NVIDIA_DISCOVER_SKILLS_V1.json"

CREATIVE_MAP_PATH = ROOT / "memory" / "ENGEL_CREATIVE_WORK_LANE_MAP_V1.json"

ALL_NVIDIA_MODELS = [
    "nvidia/nemotron-3-super-120b-a12b",
    "nvidia/nemotron-3-ultra-550b-a55b",
    "nvidia/llama-3.3-nemotron-super-49b-v1.5",
    "nvidia/nemotron-3.5-lightning-30b-a3b",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
    "nvidia/nemotron-3-nano-30b-a3b",
]

NVIDIA_BETTER_FOR_JOB = {
    "game_design": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
    "video_creation": "nvidia/nemotron-3-ultra-550b-a55b",
    "app_creation": "nvidia/nemotron-3-ultra-550b-a55b",
}

CREATIVE_JOB_MARKERS = {
    "game_design": (
        "game design",
        "sprite",
        "tileset",
        "character sheet",
        "pixel art",
        "blender",
        "godot",
        "unity",
        "unreal",
        "game ui",
        "favicon for a game",
    ),
    "video_creation": (
        "video",
        "mp4",
        "image to video",
        "image-to-video",
        "animate this",
        "cinematic",
        "manim",
        "caption the clip",
        "make a trailer",
    ),
    "app_creation": (
        "flutter",
        "apk",
        "build the app",
        "pyinstaller",
        "engel.exe",
        "package the app",
        "mobile app",
        "qt window",
    ),
}

DEFAULT_MOUTH_MODELS = {
    "": "nvidia/nemotron-3-super-120b-a12b",
    "main": "nvidia/nemotron-3-super-120b-a12b",
    "research": "nvidia/nemotron-3-super-120b-a12b",
    "product": "nvidia/nemotron-3-ultra-550b-a55b",
    "community": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
    "support": "nvidia/nemotron-3.5-lightning-30b-a3b",
    "sales": "nvidia/nemotron-3-nano-30b-a3b",
    "ops": "nvidia/llama-3.3-nemotron-super-49b-v1.5",
}


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def load_lane_map() -> dict[str, Any]:
    return _load_json(LANE_MAP_PATH)


def load_skills() -> dict[str, Any]:
    return _load_json(SKILLS_PATH)


def load_creative_map() -> dict[str, Any]:
    return _load_json(CREATIVE_MAP_PATH)


def creative_job_for_prompt(prompt: str) -> str:
    low = " ".join(str(prompt or "").casefold().split())
    if not low:
        return ""
    hits: list[tuple[int, str]] = []
    for job, markers in CREATIVE_JOB_MARKERS.items():
        score = sum(1 for marker in markers if marker in low)
        if score:
            hits.append((score, job))
    if not hits:
        return ""
    hits.sort(reverse=True)
    return hits[0][1]


def preferred_nvidia_model_for_prompt(prompt: str) -> str:
    """If the NVIDIA Discover link is the better match for this job, use it.

    A downloaded local weight does not lock the lane. Other NVIDIA models stay
    in the candidate list.
    """
    job = creative_job_for_prompt(prompt)
    if not job:
        return ""
    return str(NVIDIA_BETTER_FOR_JOB.get(job) or "")


def nvidia_candidates_for_prompt(prompt: str = "", desk_name: str = "") -> list[str]:
    ordered: list[str] = []
    better = preferred_nvidia_model_for_prompt(prompt)
    if better:
        ordered.append(better)
    mouth = model_for_mouth(desk_name)
    if mouth and mouth not in ordered:
        ordered.append(mouth)
    for model in ALL_NVIDIA_MODELS:
        if model not in ordered:
            ordered.append(model)
    return ordered


def model_for_mouth(desk_name: str = "") -> str:
    key = str(desk_name or "").strip().lower() or "main"
    mouths = load_lane_map().get("mouths") or {}
    row = mouths.get(key) if isinstance(mouths, dict) else None
    if isinstance(row, dict):
        model = str(row.get("model") or "").strip()
        if model:
            return model
    return DEFAULT_MOUTH_MODELS.get(key, DEFAULT_MOUTH_MODELS["main"])


def skill_categories_for_mouth(desk_name: str = "") -> list[str]:
    key = str(desk_name or "").strip().lower() or "main"
    mouths = load_lane_map().get("mouths") or {}
    row = mouths.get(key) if isinstance(mouths, dict) else None
    cats = (row or {}).get("skill_categories") if isinstance(row, dict) else None
    if isinstance(cats, list) and cats:
        return [str(item) for item in cats if str(item).strip()]
    packs = (load_skills().get("mouth_packs") or {}).get(key)
    if isinstance(packs, list):
        return [str(item) for item in packs if str(item).strip()]
    return ["ai_ml"]


def skill_brief_for_mouth(desk_name: str = "") -> str:
    skills = load_skills()
    categories = skills.get("categories") if isinstance(skills.get("categories"), dict) else {}
    wanted = skill_categories_for_mouth(desk_name)
    lines = [
        "Engel local skills this mouth can actually use (linked to Discover categories; "
        "do not claim a hosted skill body was downloaded; do not claim a skill ran unless this turn used it). "
        "A downloaded local weight does not lock the lane. Other local models and NVIDIA NIM stay available. "
        "If the NVIDIA link is the better match for game design, video, or app work, use it:"
    ]
    for cat_id in wanted:
        row = categories.get(cat_id) if isinstance(categories, dict) else None
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or cat_id)
        local = row.get("engel_local_skills") or []
        names = [str(item) for item in local if str(item).strip()][:8]
        if names:
            lines.append(f"- {title}: " + ", ".join(names))
        else:
            lines.append(f"- {title}")
    if len(lines) == 1:
        return ""
    return "\n".join(lines)


def skill_brief_from_request(request: dict[str, Any] | None) -> str:
    request = request if isinstance(request, dict) else {}
    metadata = request.get("metadata") if isinstance(request.get("metadata"), dict) else {}
    desk = str(
        metadata.get("discord_desk_name")
        or request.get("discord_desk_name")
        or ""
    ).strip()
    cached = str(metadata.get("nvidia_discover_skill_brief") or "").strip()
    if cached:
        return cached
    return skill_brief_for_mouth(desk or "main")
