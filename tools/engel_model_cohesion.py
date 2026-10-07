#!/usr/bin/env python3
"""Cross-modal model cohesion for Engel AI Main.

The Flutter pickers (chat + creation) list local CT246 GGUFs and provider
lanes. Apply must actually route those ids. This map is the single translation
from picker id -> provider / local lane / modalities.

Auto Best stays local-first. An explicit picker choice is Josh selecting a
lane. Provider calls still require the existing bridge/force contract.
"""
from __future__ import annotations

from typing import Any


# Picker rows from Engel AI Main Models / Choose a creation model.
MODELS: dict[str, dict[str, Any]] = {
    "auto-best": {
        "name": "Auto Best",
        "provider": "auto",
        "force_provider": False,
        "local_lane": "",
        "api_model": "",
        "modalities": ("chat", "vision", "code", "reasoning"),
        "live": True,
    },
    "grok-4.6": {
        "name": "Grok 4.6",
        "provider": "xai",
        "force_provider": True,
        "local_lane": "",
        "api_model": "grok-4.6",
        "modalities": ("chat", "vision", "code", "image", "reasoning"),
        "live": True,
    },
    "grok-build-0-1": {
        "name": "Grok Build 0.1",
        "provider": "xai",
        "force_provider": True,
        "local_lane": "",
        "api_model": "grok-4.6",
        "modalities": ("chat", "code", "reasoning"),
        "live": True,
    },
    "ct-qwen25-7b-instruct": {
        "name": "CT Qwen 2.5 7B Instruct",
        "provider": "local",
        "force_provider": False,
        "local_lane": "7b",
        "api_model": "ct-qwen25-7b-instruct",
        "modalities": ("chat", "code", "reasoning"),
        "live": True,
    },
    "ct-qwen25-14b-instruct": {
        "name": "CT Qwen 2.5 14B Instruct",
        "provider": "local",
        "force_provider": False,
        "local_lane": "14b",
        "api_model": "ct-qwen25-14b-instruct",
        "modalities": ("chat", "code", "reasoning"),
        "live": True,
    },
    "ct-qwen3-30b-a3b": {
        "name": "CT Qwen3 30B-A3B MoE",
        "provider": "local",
        "force_provider": False,
        "local_lane": "moe",
        "api_model": "ct-qwen3-30b-a3b",
        "modalities": ("chat", "reasoning"),
        "live": True,
    },
    "ct-nemotron-35-lightning-30b": {
        "name": "CT Nemotron 3.5 Lightning 30B",
        "provider": "local",
        "force_provider": False,
        "local_lane": "nemotron",
        "api_model": "ct-nemotron-35-lightning-30b",
        "modalities": ("chat", "reasoning"),
        "live": True,
    },
    "ct-qwen25-1p5b-deepreason": {
        "name": "CT Qwen 1.5B DeepReason",
        "provider": "local",
        "force_provider": False,
        "local_lane": "1.5b",
        "api_model": "ct-qwen25-1p5b-deepreason",
        "modalities": ("chat",),
        "live": True,
    },
    "local-cuda-qwen-coder": {
        "name": "Engel Local CUDA Coder",
        "provider": "local",
        "force_provider": False,
        "local_lane": "code",
        "api_model": "local-cuda-qwen-coder",
        "modalities": ("code", "chat"),
        "live": True,
    },
    "chatgpt-browser": {
        "name": "ChatGPT Browser Voice",
        "provider": "openai",
        "force_provider": True,
        "local_lane": "",
        "api_model": "gpt-5.5",
        "modalities": ("chat", "vision", "code"),
        "live": True,
        "browser": True,
    },
    "openai-api-gpt-5-5": {
        "name": "GPT-5.5",
        "provider": "openai",
        "force_provider": True,
        "local_lane": "",
        "api_model": "gpt-5.5",
        "modalities": ("chat", "code", "reasoning"),
        "live": True,
    },
    "gpt-5-5-vision": {
        "name": "GPT-5.5 Vision",
        "provider": "openai",
        "force_provider": True,
        "local_lane": "",
        "api_model": "gpt-5.5",
        "modalities": ("chat", "vision"),
        "live": True,
    },
    "nvidia-nemotron-3-super-120b": {
        "name": "NVIDIA Nemotron 3 Super 120B",
        "provider": "nvidia",
        "force_provider": True,
        "local_lane": "",
        "api_model": "nvidia/nemotron-3-super-120b-a12b",
        "modalities": ("chat", "code", "reasoning"),
        "live": True,
    },
    "nvidia-nemotron-3-ultra-550b": {
        "name": "NVIDIA Nemotron 3 Ultra 550B",
        "provider": "nvidia",
        "force_provider": True,
        "local_lane": "",
        "api_model": "nvidia/nemotron-3-ultra-550b-a55b",
        "modalities": ("chat", "code", "reasoning"),
        "live": True,
    },
    "nvidia-nemotron-3-nano-omni-30b": {
        "name": "NVIDIA Nemotron 3 Nano Omni 30B",
        "provider": "nvidia",
        "force_provider": True,
        "local_lane": "",
        "api_model": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
        "modalities": ("chat", "reasoning"),
        "live": True,
    },
    "nvidia-nemotron-3-nano-30b": {
        "name": "NVIDIA Nemotron 3 Nano 30B",
        "provider": "nvidia",
        "force_provider": True,
        "local_lane": "",
        "api_model": "nvidia/nemotron-3-nano-30b-a3b",
        "modalities": ("chat",),
        "live": True,
    },
    "nvidia-nemotron-35-lightning-nim": {
        "name": "NVIDIA Nemotron 3.5 Lightning 30B",
        "provider": "nvidia",
        "force_provider": True,
        "local_lane": "",
        "api_model": "nvidia/nemotron-3.5-lightning-30b-a3b",
        "modalities": ("chat", "reasoning"),
        "live": True,
    },
    "jev-latest": {
        "name": "Jev",
        "provider": "jev",
        "force_provider": False,
        "local_lane": "",
        "api_model": "jev-latest",
        "modalities": ("decision",),
        "live": True,
        "github": "https://github.com/typesafe-ai/typesafe-sdk-python",
    },
}

ALIASES = {
    "grok-4-6": "grok-4.6",
    "grok46": "grok-4.6",
    "grok-4-3-max": "grok-4.6",
    "grok-4-3-fast": "grok-4.6",
    "grok-4-3-reasoning": "grok-4.6",
    "grok-4-3-vision": "grok-4.6",
    "grok-build": "grok-build-0-1",
    "grok-build-0.1": "grok-build-0-1",
    "auto": "auto-best",
    "best": "auto-best",
    "qwen2.5-7b": "ct-qwen25-7b-instruct",
    "qwen2.5-14b": "ct-qwen25-14b-instruct",
    "qwen2.5-14b-instruct": "ct-qwen25-14b-instruct",
    "14b": "ct-qwen25-14b-instruct",
    "qwen3-30b-a3b": "ct-qwen3-30b-a3b",
    "30b-a3b": "ct-qwen3-30b-a3b",
    "sparse_moe": "ct-qwen3-30b-a3b",
    "moe": "ct-qwen3-30b-a3b",
    "nemotron": "ct-nemotron-35-lightning-30b",
    "nemotron-3.5": "ct-nemotron-35-lightning-30b",
    "lightning": "ct-nemotron-35-lightning-30b",
    "deepreason": "ct-qwen25-1p5b-deepreason",
    "1.5b": "ct-qwen25-1p5b-deepreason",
    "coder": "local-cuda-qwen-coder",
    "gpt-5.5": "openai-api-gpt-5-5",
    "chatgpt": "chatgpt-browser",
    "qwen2-5-7b-local": "ct-qwen25-7b-instruct",
    "qwen2-5-coder-7b-local": "local-cuda-qwen-coder",
    "qwen2-5-coder-14b-local": "ct-qwen25-14b-instruct",
    "qwen2-5-coder-32b-local": "ct-qwen25-14b-instruct",
    "qwen2-5-3b-local": "ct-qwen25-1p5b-deepreason",
    "deepseek-r1-distill-qwen-14b-local": "ct-qwen25-14b-instruct",
    "mistral-7b-instruct-local": "ct-qwen25-7b-instruct",
    "llama-3-1-8b-local": "ct-qwen25-7b-instruct",
    "llama-3-2-3b-local": "ct-qwen25-1p5b-deepreason",
    "local-any-gguf": "ct-qwen25-7b-instruct",
    "sub-engel-local-best": "auto-best",
    "android-worker-local-best": "auto-best",
    "nvidia/nemotron-3-super-120b-a12b": "nvidia-nemotron-3-super-120b",
    "nemotron-3-super-120b-a12b": "nvidia-nemotron-3-super-120b",
    "nvidia/nemotron-3-ultra-550b-a55b": "nvidia-nemotron-3-ultra-550b",
    "nemotron-3-ultra-550b-a55b": "nvidia-nemotron-3-ultra-550b",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning": "nvidia-nemotron-3-nano-omni-30b",
    "nvidia/nemotron-3-nano-30b-a3b": "nvidia-nemotron-3-nano-30b",
    "nvidia/nemotron-3.5-lightning-30b-a3b": "nvidia-nemotron-35-lightning-nim",
    "jev": "jev-latest",
}


# After the selected lane misses, try these in order. Auto Best starts here.
_FALLBACK_ORDER = (
    "ct-qwen25-7b-instruct",
    "ct-qwen25-1p5b-deepreason",
    "ct-qwen25-14b-instruct",
    "nvidia-nemotron-3-super-120b",
    "nvidia-nemotron-3-ultra-550b",
    "grok-4.6",
)


def fallback_ids_for(catalog_id: str) -> list[str]:
    """Next lanes after the one the picker already asked for."""
    cid = canonical_id(catalog_id) or str(catalog_id or "").strip().casefold() or "auto-best"
    if cid in {"", "auto-best"}:
        return list(_FALLBACK_ORDER)
    return [item for item in _FALLBACK_ORDER if item != cid]


def _family_spec(raw: str) -> tuple[str, dict[str, Any]] | None:
    """Route a catalog id that is not a resident GGUF row to its provider lane."""
    low = str(raw or "").strip().casefold()
    if not low:
        return None
    if low.startswith("nvidia/") or low.startswith("nemotron-3-"):
        spec = dict(MODELS["nvidia-nemotron-3-super-120b"])
        if "ultra" in low or "550b" in low:
            spec = dict(MODELS["nvidia-nemotron-3-ultra-550b"])
        if low.startswith("nvidia/"):
            spec["api_model"] = str(raw).strip()
            spec["name"] = str(raw).strip()
        return str(spec["api_model"]), spec
    if low.startswith("grok"):
        return "grok-4.6", dict(MODELS["grok-4.6"])
    if low.startswith(("gpt", "chatgpt", "o3", "o4")):
        return "openai-api-gpt-5-5", dict(MODELS["openai-api-gpt-5-5"])
    if any(token in low for token in ("claude", "opus", "sonnet", "haiku")):
        return low, {
            "name": raw,
            "provider": "anthropic",
            "force_provider": True,
            "local_lane": "",
            "api_model": low,
            "modalities": ("chat", "code", "reasoning"),
            "live": True,
        }
    if low.startswith(("gemini", "imagen", "veo")):
        return low, {
            "name": raw,
            "provider": "gemini",
            "force_provider": True,
            "local_lane": "",
            "api_model": low,
            "modalities": ("chat", "vision", "reasoning"),
            "live": True,
        }
    if low.startswith("deepseek") or low.startswith(("qwen3", "kimi", "glm", "mistral", "llama-4", "openrouter", "groq", "perplexity", "cohere", "moonshot", "minimax", "codestral", "qwq")):
        return "ct-qwen25-7b-instruct", dict(MODELS["ct-qwen25-7b-instruct"])
    if low.endswith("-local") or "local" in low:
        return "ct-qwen25-7b-instruct", dict(MODELS["ct-qwen25-7b-instruct"])
    return None

def canonical_id(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    low = text.casefold()
    if text in MODELS:
        return text
    if low in MODELS:
        return low
    return ALIASES.get(low, "")


def _metadata(request: dict[str, Any]) -> dict[str, Any]:
    raw = request.get("metadata")
    return raw if isinstance(raw, dict) else {}


def _looks_like_creation(request: dict[str, Any], prompt: str) -> bool:
    kind = str(
        request.get("engel_task_kind")
        or _metadata(request).get("engel_task_kind")
        or ""
    ).casefold()
    return kind in {"creation", "code", "image", "video"}


def _needs_vision(request: dict[str, Any]) -> bool:
    if request.get("main_ui_vision") is True or request.get("discord_owner_vision") is True:
        return True
    attachments = request.get("attachments")
    if not isinstance(attachments, list):
        return False
    for item in attachments:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "").casefold()
        ctype = str(item.get("content_type") or item.get("mime") or "").casefold()
        if kind == "image" or ctype.startswith("image/"):
            return True
    return False


def lookup_catalog(raw_id: str) -> dict[str, Any]:
    """Describe one catalog row. This does not select it for a turn."""
    raw = str(raw_id or "").strip()
    catalog_id = canonical_id(raw) or ("auto-best" if not raw else "")
    spec = dict(MODELS.get(catalog_id) or {})
    if catalog_id not in MODELS:
        family = _family_spec(raw)
        if family is not None:
            catalog_id, spec = family
            spec = dict(spec)
        else:
            spec = dict(MODELS["auto-best"])
            catalog_id = "auto-best"
    spec["catalog_id"] = catalog_id
    return spec


def _resolve_requested_catalog(request: dict[str, Any], prompt: str) -> dict[str, Any]:
    """The automatic router's own next lane after a miss. Not a user pin."""
    meta = _metadata(request)
    creation = _looks_like_creation(request, prompt)
    raw_id = ""
    if creation:
        raw_id = str(
            request.get("selected_creation_model_id")
            or meta.get("selected_creation_model_id")
            or ""
        ).strip()
    if not raw_id:
        raw_id = str(
            request.get("selected_model_id")
            or meta.get("selected_model_id")
            or request.get("model")
            or request.get("provider_model")
            or ""
        ).strip()
    spec = lookup_catalog(raw_id)
    catalog_id = str(spec.pop("catalog_id"))
    modalities = tuple(spec.get("modalities") or ("chat",))
    vision = _needs_vision(request)
    vision_fallback = ""
    if vision and "vision" not in modalities and catalog_id not in {"auto-best", ""}:
        vision_fallback = "grok-4.6"
    return {
        "schema": "engel_model_cohesion_v1",
        "catalog_id": catalog_id,
        "name": spec.get("name") or catalog_id,
        "provider": spec.get("provider") or "auto",
        "force_provider": bool(spec.get("force_provider")),
        "automatic": True,
        "automatic_router_lane": True,
        "local_lane": str(spec.get("local_lane") or ""),
        "api_model": str(spec.get("api_model") or ""),
        "modalities": modalities,
        "live": spec.get("live") is True,
        "vision": vision,
        "creation": creation,
        "vision_fallback": vision_fallback,
        "browser": spec.get("browser") is True,
        "fallback_ids": fallback_ids_for(catalog_id),
        "requested_catalog_id": raw_id,
    }


def resolve_turn(request: dict[str, Any] | None, prompt: str = "") -> dict[str, Any]:
    """Every turn is Auto Best unless the router itself is retrying the next lane."""
    request = request if isinstance(request, dict) else {}
    if request.get("automatic_router_lane") is True:
        return _resolve_requested_catalog(request, prompt)
    meta = _metadata(request)
    raw_id = str(
        request.get("selected_model_id")
        or meta.get("selected_model_id")
        or meta.get("standing_chat_model_id")
        or request.get("selected_creation_model_id")
        or request.get("model")
        or ""
    ).strip()
    spec = dict(MODELS["auto-best"])
    vision = _needs_vision(request)
    return {
        "schema": "engel_model_cohesion_v1",
        "catalog_id": "auto-best",
        "name": spec.get("name") or "Auto Best",
        "provider": "auto",
        "force_provider": False,
        "automatic": True,
        "local_lane": "",
        "api_model": "",
        "modalities": tuple(spec.get("modalities") or ("chat",)),
        "live": True,
        "vision": vision,
        "creation": _looks_like_creation(request, prompt),
        "vision_fallback": "grok-4.6" if vision else "",
        "browser": False,
        "fallback_ids": list(_FALLBACK_ORDER),
        "requested_catalog_id": canonical_id(raw_id) or raw_id,
    }


def apply_to_request(request: dict[str, Any], prompt: str = "") -> dict[str, Any]:
    """Stamp the automatic route. A picker id or force flag does not pin the turn."""
    if request.get("automatic_router_lane") is not True:
        meta = request.get("metadata") if isinstance(request.get("metadata"), dict) else {}
        requested = str(
            request.get("selected_model_id")
            or meta.get("selected_model_id")
            or meta.get("standing_chat_model_id")
            or ""
        ).strip()
        for key in (
            "force_provider",
            "explicit_provider",
            "provider_explicit",
            "force_bridge",
            "explicit_bridge",
        ):
            request.pop(key, None)
        request["selected_model_id"] = "auto-best"
        request["automatic_provider_after_local_failure_only"] = True
        if isinstance(request.get("metadata"), dict):
            if requested:
                request["metadata"]["requested_model_id"] = requested
            request["metadata"]["selected_model_id"] = "auto-best"
            request["metadata"]["automatic_model_route"] = True
            request["metadata"].pop("standing_chat_model_id", None)
        provider = str(request.get("provider") or "").strip().casefold()
        if provider and provider not in {"auto", "local"}:
            request.pop("provider", None)
            request.pop("selected_provider", None)
        model = str(request.get("model") or "").strip().casefold()
        if model and model not in {"auto", "auto-best"}:
            request.pop("model", None)
            request.pop("provider_model", None)
        if requested:
            request["_requested_model_id"] = requested
    sel = resolve_turn(request, prompt)
    if request.get("_requested_model_id") and sel.get("catalog_id") == "auto-best":
        sel["requested_catalog_id"] = request.get("_requested_model_id")
    request["_engel_cohesion"] = sel
    lane = str(sel.get("local_lane") or "")
    if sel.get("force_provider") and sel.get("provider") not in {"", "auto", "local"}:
        request["force_provider"] = True
        request["explicit_provider"] = True
        request["provider"] = sel["provider"]
        request["selected_provider"] = sel["provider"]
        if sel.get("api_model"):
            request["model"] = sel["api_model"]
            request["provider_model"] = sel["api_model"]
        request["_skip_specialist_auto"] = True
        request["_skip_quick_casual"] = True
        return sel
    if lane == "7b":
        request["_skip_specialist_auto"] = True
        request["_skip_quick_casual"] = True
    elif lane == "1.5b":
        request["_force_quick_casual"] = True
        request["_skip_specialist_auto"] = True
    elif lane == "nemotron":
        request["model_mode"] = "nemotron"
        request["_skip_quick_casual"] = True
    elif lane == "moe":
        request["model_mode"] = "sparse_moe"
        request["_skip_quick_casual"] = True
    elif lane == "14b":
        request["model_mode"] = "14b"
        request["_skip_quick_casual"] = True
    elif lane == "code":
        request["_force_code_lane"] = True
        request["_skip_quick_casual"] = True
        request["_skip_specialist_auto"] = True
    if sel.get("vision_fallback") == "grok-4.6":
        request["_vision_fallback_grok"] = True
    return sel
