#!/usr/bin/env python3
"""Game / video / app lanes use local skills and proved CT246 vault paths. No live download."""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / "memory" / "ENGEL_CREATIVE_WORK_LANE_MAP_V1.json"
SKILLS = ROOT / "memory" / "ENGEL_NVIDIA_DISCOVER_SKILLS_V1.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    data = json.loads(MAP.read_text(encoding="utf-8"))
    require(data.get("schema") == "ENGEL_CREATIVE_WORK_LANE_MAP_V1", "creative map schema")
    require(data.get("live_7b_untouched") is True, "live 7B stays")
    require(data.get("nvidia_hosted_skill_bodies_downloaded") is False, "must not claim NVIDIA skill download")
    storage = data.get("storage") or {}
    require(storage.get("active_ssd") == "/opt/engel", "active SSD root")
    require(storage.get("cold_hdd_vault") == "/mnt/engel-hdd-vault", "cold vault root")
    require(
        "engel-hdd-vault" in str(storage.get("vault_creative_root") or "")
        and "creative-archive" in str(storage.get("vault_creative_root") or ""),
        "creative archive path",
    )
    jobs = data.get("jobs") or {}
    for job in ("game_design", "video_creation", "app_creation"):
        row = jobs.get(job) or {}
        skills = row.get("engel_local_skills") or []
        require(len(skills) >= 4, job + " needs local skills")
        for skill in skills:
            path = ROOT / ".agents" / "skills" / str(skill) / "SKILL.md"
            require(path.is_file(), "missing skill " + str(skill))
        require(any("/opt/engel" in str(item) for item in (row.get("active_models") or [])), job + " needs an active SSD model")
        require(any("/mnt/engel-hdd-vault" in str(item) for item in (row.get("cold_models") or [])), job + " needs a vault model")
    require("Never Chase" in str(data.get("operator") or ""), "operator is Joshua not Chase")
    routing = data.get("routing") or {}
    require(routing.get("one_downloaded_model_does_not_lock_the_lane") is True, "one download must not lock the lane")
    require(routing.get("prefer_nvidia_link_when_better") is True, "prefer NVIDIA when it is the better link")
    require(routing.get("all_nvidia_candidates_stay_in_failover") is True, "other NVIDIA models stay usable")

    sys.path.insert(0, str(ROOT / "tools"))
    from engel_nvidia_discover import (
        creative_job_for_prompt,
        nvidia_candidates_for_prompt,
        preferred_nvidia_model_for_prompt,
    )

    require(creative_job_for_prompt("make a pixel art tileset") == "game_design", "game prompt maps")
    require(preferred_nvidia_model_for_prompt("make a pixel art tileset").endswith("omni-30b-a3b-reasoning"), "game prefers Omni")
    require(preferred_nvidia_model_for_prompt("build the flutter app").endswith("ultra-550b-a55b"), "app prefers Ultra")
    cands = nvidia_candidates_for_prompt("make a pixel art tileset", "main")
    require(len(cands) >= 6, "creative prompt still keeps every NVIDIA candidate")
    require(cands[0].endswith("omni-30b-a3b-reasoning"), "better NVIDIA link is first")
    require("nvidia/nemotron-3-super-120b-a12b" in cands, "downloaded or default Super stays usable")

    discover = json.loads(SKILLS.read_text(encoding="utf-8"))
    cats = discover.get("categories") or {}
    for job in ("game_design", "video_creation", "app_creation"):
        require(job in cats, "discover skills missing " + job)
    packs = discover.get("mouth_packs") or {}
    require("game_design" in (packs.get("main") or []), "main mouth gets game design")
    require("app_creation" in (packs.get("product") or []), "product mouth gets app creation")
    require("video_creation" in (packs.get("community") or []), "community mouth gets video")

    catalog = json.loads((ROOT / "runtime" / "next_stage" / "models_brains" / "CATALOG.json").read_text(encoding="utf-8"))
    require((catalog.get("creative_work") or {}).get("jobs") == ["game_design", "video_creation", "app_creation"], "brains catalog names creative jobs")

    print("verify_engel_creative_work_lanes: GREEN")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print("FAIL", exc)
        print("verify_engel_creative_work_lanes: RED")
        raise SystemExit(1)
