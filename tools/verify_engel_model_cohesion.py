#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import engel_model_cohesion as cohesion  # noqa: E402


SCREENSHOT_MODELS = (
    "auto-best",
    "grok-4.6",
    "ct-qwen25-7b-instruct",
    "ct-qwen25-14b-instruct",
    "ct-qwen3-30b-a3b",
    "ct-nemotron-35-lightning-30b",
    "ct-qwen25-1p5b-deepreason",
    "local-cuda-qwen-coder",
    "chatgpt-browser",
    "openai-api-gpt-5-5",
)


def main() -> int:
    checks: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str) -> None:
        checks.append((name, ok, detail))

    for mid in SCREENSHOT_MODELS:
        spec = cohesion.MODELS.get(mid)
        check(f"catalog_has_{mid}", isinstance(spec, dict) and spec.get("live") is True, mid)

    auto = cohesion.resolve_turn({"selected_model_id": "auto-best"}, "hello")
    check("auto_best_does_not_force_provider", auto.get("force_provider") is False, str(auto))
    check(
        "auto_best_fallback_chain",
        auto.get("fallback_ids") == [
            "ct-qwen25-7b-instruct",
            "ct-qwen25-1p5b-deepreason",
            "ct-qwen25-14b-instruct",
            "nvidia-nemotron-3-super-120b",
            "nvidia-nemotron-3-ultra-550b",
            "grok-4.6",
        ],
        str(auto.get("fallback_ids")),
    )
    opus = cohesion.resolve_turn({"selected_model_id": "opus-4-8"}, "hello")
    check(
        "opus_routes_to_anthropic",
        opus.get("provider") == "anthropic" and opus.get("force_provider") is True,
        str(opus),
    )
    gemini = cohesion.resolve_turn({"selected_model_id": "gemini-3-pro"}, "hello")
    check("gemini_routes_to_gemini", gemini.get("provider") == "gemini", str(gemini))
    nvidia = cohesion.resolve_turn({"selected_model_id": "nvidia-nemotron-3-super-120b"}, "hello")
    check(
        "nvidia_super_keeps_large_model",
        nvidia.get("provider") == "nvidia"
        and nvidia.get("api_model") == "nvidia/nemotron-3-super-120b-a12b"
        and nvidia.get("force_provider") is True,
        str(nvidia),
    )
    check("auto_best_has_vision_and_code", "vision" in auto.get("modalities", ()) and "code" in auto.get("modalities", ()), str(auto.get("modalities")))

    grok = cohesion.resolve_turn({"selected_model_id": "grok-4.6"}, "hello")
    check("grok_forces_xai", grok.get("provider") == "xai" and grok.get("force_provider") is True, str(grok))
    check("grok_has_vision", "vision" in grok.get("modalities", ()), str(grok.get("modalities")))

    seven = cohesion.resolve_turn({"selected_model_id": "ct-qwen25-7b-instruct"}, "hello")
    check("ct_7b_is_local_lane", seven.get("local_lane") == "7b", str(seven))
    req = {"selected_model_id": "ct-qwen25-7b-instruct"}
    cohesion.apply_to_request(req, "hello")
    check("ct_7b_skips_specialists", req.get("_skip_specialist_auto") is True and req.get("_skip_quick_casual") is True, str(req))

    vision_7b = cohesion.resolve_turn(
        {
            "selected_model_id": "ct-qwen25-7b-instruct",
            "attachments": [{"kind": "image", "content_type": "image/png"}],
        },
        "look at this",
    )
    check(
        "text_model_falls_back_to_grok_for_vision",
        vision_7b.get("vision_fallback") == "grok-4.6",
        str(vision_7b),
    )

    gpt = cohesion.resolve_turn({"selected_model_id": "openai-api-gpt-5-5"}, "hello")
    check("gpt55_forces_openai", gpt.get("provider") == "openai" and gpt.get("force_provider") is True, str(gpt))

    creation = cohesion.resolve_turn(
        {
            "selected_model_id": "auto-best",
            "selected_creation_model_id": "grok-4.6",
            "engel_task_kind": "creation",
        },
        "draw a logo",
    )
    check("creation_uses_creation_picker", creation.get("catalog_id") == "grok-4.6", str(creation))

    chat_not_creation = cohesion.resolve_turn(
        {
            "selected_model_id": "auto-best",
            "selected_creation_model_id": "grok-4.6",
        },
        "hello",
    )
    check(
        "chat_does_not_bleed_creation_grok",
        chat_not_creation.get("catalog_id") == "auto-best" and chat_not_creation.get("force_provider") is False,
        str(chat_not_creation),
    )

    build = cohesion.canonical_id("grok-build-0-1")
    check("legacy_grok_build_id_stays", build == "grok-build-0-1", build)

    chat_src = (ROOT / "tools" / "engel_main_server_chat_http_service.py").read_text(encoding="utf-8")
    check("chat_service_applies_cohesion", "apply_model_cohesion(request, prompt)" in chat_src, "chat")
    worker_src = (ROOT / "tools" / "engel_main_local_model_worker.py").read_text(encoding="utf-8")
    check("worker_forwards_catalog_ids", "def _stamp_catalog_selection(" in worker_src, "worker")
    flutter = (ROOT / "engel_flutter_main" / "lib" / "main.dart").read_text(encoding="utf-8")
    check(
        "flutter_sends_selected_model_id",
        "selectedModelId: _activeModelId" in flutter and "selected_model_id" in flutter,
        "flutter",
    )
    check(
        "flutter_chat_provider_follows_picker",
        "Creation picker does not bleed into chat" in flutter,
        "provider",
    )

    failed = [name for name, ok, _ in checks if not ok]
    for name, ok, detail in checks:
        print(("PASS" if ok else "FAIL"), name, "::", detail[:180])
    print(f"{sum(1 for _, ok, _ in checks if ok)}/{len(checks)} checks passed")
    print("verify_engel_model_cohesion: " + ("GREEN" if not failed else "RED"))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
