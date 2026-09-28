#!/usr/bin/env python3
"""NVIDIA NIM mouths use NVIDIA Nemotron transformers. Discover skills linked locally. No live API. No secrets."""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

NVIDIA_TRANSFORMERS = {
    "nvidia/nemotron-3-super-120b-a12b",
    "nvidia/nemotron-3-ultra-550b-a55b",
    "nvidia/llama-3.3-nemotron-super-49b-v1.5",
    "nvidia/nemotron-3.5-lightning-30b-a3b",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
    "nvidia/nemotron-3-nano-30b-a3b",
}
REJECTED_DEFAULTS = {
    "moonshotai/kimi-k3",
    "deepseek-ai/deepseek-v4-pro-0813",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    lane_map = json.loads((ROOT / "memory" / "ENGEL_NVIDIA_NIM_LANE_MAP_V1.json").read_text(encoding="utf-8"))
    require(lane_map.get("schema") == "ENGEL_NVIDIA_NIM_LANE_MAP_V1", "lane map schema")
    mouths = lane_map.get("mouths") or {}
    require(mouths["main"]["model"] == "nvidia/nemotron-3-super-120b-a12b", "main is Nemotron 3 Super 120B-A12B")
    require(mouths["research"]["model"] == "nvidia/nemotron-3-super-120b-a12b", "research is Nemotron 3 Super")
    require(mouths["product"]["model"] == "nvidia/nemotron-3-ultra-550b-a55b", "product is Nemotron 3 Ultra 550B agent")
    require(mouths["community"]["model"].startswith("nvidia/nemotron-3-nano-omni"), "community is Nemotron 3 Nano Omni")
    require(mouths["support"]["model"] == "nvidia/nemotron-3.5-lightning-30b-a3b", "support is Nemotron 3.5 Lightning")
    require(mouths["sales"]["model"] == "nvidia/nemotron-3-nano-30b-a3b", "sales is Nemotron 3 Nano")
    require(mouths["ops"]["model"] == "nvidia/llama-3.3-nemotron-super-49b-v1.5", "ops is Llama-Nemotron Super 49B")
    for name, row in mouths.items():
        model = str((row or {}).get("model") or "")
        require(model.startswith("nvidia/"), f"{name} mouth must be an NVIDIA transformer, got {model}")
        require(model in NVIDIA_TRANSFORMERS, f"{name} mouth {model} is not a chosen NVIDIA transformer")
        require(model not in REJECTED_DEFAULTS, f"{name} must not default to third-party NIM host")
        require(isinstance((row or {}).get("skill_categories"), list) and (row or {}).get("skill_categories"), f"{name} must link skill categories")
    require("NVIDIA_API_KEY" in (lane_map.get("secret_names") or []), "secret names include NVIDIA_API_KEY")
    review = lane_map.get("review") or {}
    require(review.get("discord_nvidia_first") is False, "review marks Discord local-first (not NVIDIA-first)")
    require(review.get("local_first") is True, "Discord mouths are local-first; NIM is preferred fallback")
    require(review.get("discord_local_first") is True, "review marks discord_local_first")
    require(review.get("live_7b_untouched") is True, "review does not promote over live 7B")
    endpoints = {str(item.get("id")): item for item in (lane_map.get("discover_endpoints") or []) if isinstance(item, dict)}
    require("nvidia/nemotron-3-ultra-550b-a55b" in endpoints, "Discover Ultra agent endpoint is linked")
    require("nvidia/nemotron-3.5-lightning-30b-a3b" in endpoints, "Discover Lightning customization endpoint is linked")
    require(endpoints["moonshotai/kimi-k3"].get("default_mouth") is False, "kimi-k3 stays optional")
    require(endpoints["deepseek-ai/deepseek-v4-pro-0813"].get("default_mouth") is False, "deepseek-v4 stays optional")

    skills = json.loads((ROOT / "memory" / "ENGEL_NVIDIA_DISCOVER_SKILLS_V1.json").read_text(encoding="utf-8"))
    require(skills.get("schema") == "ENGEL_NVIDIA_DISCOVER_SKILLS_V1", "discover skills schema")
    require(skills.get("nvidia_hosted_skill_bodies_downloaded") is False, "must not claim NVIDIA skill bodies were downloaded")
    categories = skills.get("categories") or {}
    require(int((categories.get("ai_ml") or {}).get("nvidia_count") or 0) == 169, "AI/ML count from Discover")
    require(int((categories.get("accelerated_computing") or {}).get("nvidia_count") or 0) == 31, "Accelerated Computing count")
    require(int((categories.get("physical_ai") or {}).get("nvidia_count") or 0) == 69, "Physical AI count")
    require(int((categories.get("developer_tools") or {}).get("nvidia_count") or 0) == 30, "Developer Tools count")
    for cat_id, row in categories.items():
        local = (row or {}).get("engel_local_skills") or []
        require(len(local) >= 4, f"{cat_id} must map real Engel local skills")
        for skill in local:
            path = ROOT / ".agents" / "skills" / str(skill) / "SKILL.md"
            require(path.is_file(), f"missing local skill {skill}")

    from engel_nvidia_discover import model_for_mouth, skill_brief_for_mouth

    require(model_for_mouth("product") == "nvidia/nemotron-3-ultra-550b-a55b", "discover helper product model")
    brief = skill_brief_for_mouth("research")
    require("AI and Machine Learning" in brief, "research skill brief names AI/ML")
    require("engel-hermes-axolotl" in brief, "research skill brief names a real Engel skill")

    chat = (ROOT / "tools" / "engel_main_server_chat_http_service.py").read_text(encoding="utf-8")
    require("def _call_nvidia_nim_bridge(" in chat, "chat service has NVIDIA NIM caller")
    require("integrate.api.nvidia.com/v1/chat/completions" in chat, "NVIDIA NIM URL")
    require('"nvidia": ["ENGEL_NVIDIA_API_KEY"' in chat, "NVIDIA secret names")
    require("preferred_fallback_provider" in chat, "local-failure prefers NVIDIA")
    require("force_provider" in chat, "force_provider still exists for other providers")
    require("nvidia/nemotron-3-super-120b-a12b" in chat, "Super 120B is a fallback candidate")
    require("nvidia/nemotron-3-ultra-550b-a55b" in chat, "Ultra 550B is a fallback candidate")
    require("nvidia/nemotron-3.5-lightning-30b-a3b" in chat, "Lightning 30B NIM is a fallback candidate")
    require("nvidia/llama-3.3-nemotron-super-49b-v1.5" in chat, "Llama-Nemotron Super 49B is a fallback candidate")
    require("nvidia/nemotron-3-nano-30b-a3b" in chat, "Nano 30B-A3B is a fallback candidate")
    require("skill_brief_from_request" in chat, "NVIDIA turns get the Discover skill brief")
    require("moonshotai/kimi-k3" not in chat.split("PROVIDER_MODEL_FALLBACKS", 1)[-1].split("def _load_json_file", 1)[0], "kimi-k3 is not a NVIDIA fallback")
    require("deepseek-ai/deepseek-v4-pro-0813" not in chat.split("PROVIDER_MODEL_FALLBACKS", 1)[-1].split("def _load_json_file", 1)[0], "deepseek-v4 is not a NVIDIA fallback")

    bridge = (ROOT / "tools" / "engel_discord_bridge.py").read_text(encoding="utf-8")
    require("def nvidia_nim_model_for_mouth(" in bridge, "discord mouths pick a NIM model")
    require("nvidia/nemotron-3-super-120b-a12b" in bridge, "Super 120B mapped")
    require("nvidia/nemotron-3-ultra-550b-a55b" in bridge, "Ultra 550B mapped")
    require("nvidia/nemotron-3-nano-30b-a3b" in bridge, "Nano 30B mapped")
    require("nvidia/nemotron-3-nano-omni-30b-a3b-reasoning" in bridge, "Nano Omni mapped")
    require("moonshotai/kimi-k3" not in bridge, "kimi-k3 is not a discord default")
    require("deepseek-ai/deepseek-v4-pro-0813" not in bridge, "deepseek-v4 is not a discord default")
    require('payload["preferred_fallback_provider"]' in bridge, "discord prefers NVIDIA only after local failure")
    require("nvidia_nim_model" in bridge, "discord sends the per-mouth NIM model")
    require("nvidia_discover_skill_brief" in bridge, "discord mouths attach Discover skill packs")
    require('metadata["discord_nvidia_first"] = False' in bridge, "discord does not force NVIDIA-first")
    require('metadata["discord_local_first"] = True' in bridge, "discord marks local-first brain")
    require("force_provider\"] = False" in bridge or 'payload["force_provider"] = False' in bridge, "discord does not force_provider")
    require("build_desk_colony_status_pack" in bridge, "desks get read-only Main+device status pack")
    require("read_only_device_status_lines" in bridge, "desks can see android worker status read-only")
    require("desks cannot control phones" in bridge or "cannot control phones" in bridge, "device access stays read-only")

    dropins = {
        ROOT / "scripts" / "systemd" / "engel-main-chat.service.d" / "92-nvidia-nim.conf": "nvidia/nemotron-3-super-120b-a12b",
        ROOT / "scripts" / "systemd" / "engel-discord-bridge.service.d" / "30-nvidia-nim.conf": "nvidia/nemotron-3-super-120b-a12b",
        ROOT / "scripts" / "systemd" / "engel-discord-desk-research.service.d" / "30-nvidia-nim.conf": "nvidia/nemotron-3-super-120b-a12b",
        ROOT / "scripts" / "systemd" / "engel-discord-desk-product.service.d" / "30-nvidia-nim.conf": "nvidia/nemotron-3-ultra-550b-a55b",
        ROOT / "scripts" / "systemd" / "engel-discord-desk-community.service.d" / "30-nvidia-nim.conf": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
        ROOT / "scripts" / "systemd" / "engel-discord-desk-support.service.d" / "30-nvidia-nim.conf": "nvidia/nemotron-3.5-lightning-30b-a3b",
        ROOT / "scripts" / "systemd" / "engel-discord-desk-sales.service.d" / "30-nvidia-nim.conf": "nvidia/nemotron-3-nano-30b-a3b",
        ROOT / "scripts" / "systemd" / "engel-discord-desk-ops.service.d" / "30-nvidia-nim.conf": "nvidia/llama-3.3-nemotron-super-49b-v1.5",
    }
    for path, model in dropins.items():
        text = path.read_text(encoding="utf-8")
        require(model in text, f"{path.name} uses {model}")
        require("ENGEL_NVIDIA_CHAT_MODEL=" in text, f"{path} sets ENGEL_NVIDIA_CHAT_MODEL")

    require((ROOT / "scripts" / "Install-EngelNvidiaNimApiBridgeKey.ps1").is_file(), "hidden-paste installer exists")
    require((ROOT / "run" / "secrets" / "nvidia.env.example").is_file(), "example env exists")
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    require("run/secrets/*.env" in gitignore, "secret env files are gitignored")
    example = (ROOT / "run" / "secrets" / "nvidia.env.example").read_text(encoding="utf-8")
    require("NVIDIA_API_KEY=" in example, "example names NVIDIA_API_KEY")
    require("nvapi-" not in example, "example must not contain a live key")

    print("verify_engel_nvidia_nim: GREEN")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print("FAIL", exc)
        print("verify_engel_nvidia_nim: RED")
        raise SystemExit(1)
