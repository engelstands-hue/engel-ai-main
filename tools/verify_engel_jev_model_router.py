#!/usr/bin/env python3
"""Jev from the GitHub SDK orders lanes. The updater writes the picker registry."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "organs" / "models"))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))

import engel_jev_decision as jev  # noqa: E402
import engel_model_catalog_updater as updater  # noqa: E402
import engel_model_cohesion as cohesion  # noqa: E402
from engel_ai_update_routes import (  # noqa: E402
    ENGEL_MODEL_CATALOG_UPDATE_ROUTE_ID,
    render_update_route,
    resolve_update_route,
)


def main() -> int:
    checks: list[tuple[bool, str]] = []

    def require(ok: bool, name: str) -> None:
        checks.append((ok, name))

    require(jev.GITHUB_SDK == "https://github.com/typesafe-ai/typesafe-sdk-python", "github_sdk")
    require(jev.DEFAULT_MODEL == "jev-latest", "default_model")
    require(jev.SYSTEM_ONE_PATH == "/v1/systemone", "system_one_path")
    require(jev.MODELS_PATH == "/v1/models", "models_path")
    require(jev.DEFAULT_BASE_URL == "https://api.typesafe.ai", "base_url")

    saved_key = os.environ.pop("TYPESAFE_API_KEY", None)
    saved_file = jev.SECRET_FILE
    jev.SECRET_FILE = ROOT / "run" / "secrets" / "typesafe.env.missing"
    try:
        require(jev.choose_lane("hello", {"a": "one", "b": "two"}) == "", "missing_key_does_not_choose")
        require(jev.jev_status()["key_present"] is False, "missing_key_status")
        require(jev.jev_status()["writes_chat"] is False, "jev_does_not_write_chat")
    finally:
        jev.SECRET_FILE = saved_file
        if saved_key is not None:
            os.environ["TYPESAFE_API_KEY"] = saved_key

    def transport(method: str, url: str, headers: dict[str, str], body: bytes | None) -> tuple[int, str]:
        require(method == "POST" and url.endswith("/v1/systemone"), "fake_transport_hits_systemone")
        require("Authorization" in headers and "Bearer " in headers["Authorization"], "fake_transport_sends_bearer")
        parsed = json.loads(body or b"{}")
        require(parsed.get("model") == "jev-latest", "request_model_is_jev_latest")
        require(parsed["questions"]["lane"]["type"] == "choice", "request_is_a_choice")
        return 200, json.dumps(
            {
                "model": "jev-1.13.0",
                "answers": {
                    "lane": {
                        "type": "choice",
                        "choice": "nvidia-nemotron-3-ultra-550b",
                        "confidence": 0.8,
                    }
                },
            }
        )

    ordered = jev.order_fallback_with_jev(
        "use the large nvidia model",
        [
            "ct-qwen25-7b-instruct",
            "ct-qwen25-1p5b-deepreason",
            "ct-qwen25-14b-instruct",
            "nvidia-nemotron-3-super-120b",
            "nvidia-nemotron-3-ultra-550b",
            "grok-4.6",
        ],
        transport=transport,
    )
    require(
        ordered[:3] == [
            "ct-qwen25-7b-instruct",
            "ct-qwen25-1p5b-deepreason",
            "ct-qwen25-14b-instruct",
        ],
        "local_lanes_stay_first",
    )
    require(ordered[3] == "nvidia-nemotron-3-ultra-550b", "jev_moves_the_chosen_lane_forward")

    jev_turn = cohesion.resolve_turn({"selected_model_id": "jev-latest"}, "hello")
    require(jev_turn.get("catalog_id") == "auto-best" and jev_turn.get("force_provider") is False, "jev_pin_stays_auto")
    require(cohesion.lookup_catalog("jev-latest").get("provider") == "jev", "jev_catalog_is_not_a_chat_provider_pin")
    nano = cohesion.lookup_catalog("nvidia-nemotron-3-nano-30b")
    require(nano.get("api_model") == "nvidia/nemotron-3-nano-30b-a3b", "nvidia_nano_routes")

    registry = ROOT / "memory" / "models" / "ENGEL_EXTERNAL_MODEL_REGISTRY.json"
    result = updater.update_available_models(fetch_live=False, path=registry)
    document = json.loads(registry.read_text(encoding="utf-8"))
    ids = {row["id"] for row in document["models"]}
    require(result["ok"] is True, "updater_ok")
    require(document["schema"] == "engel_external_model_registry_v1", "registry_schema")
    require("jev-latest" in ids, "registry_has_jev")
    require("nvidia-nemotron-3-super-120b" in ids, "registry_has_nvidia_super")
    require("nvidia-nemotron-3-ultra-550b" in ids, "registry_has_nvidia_ultra")
    require(len(document["provider_model_refresh_sources"]) >= 7, "refresh_sources")
    require("OpenRouter free" in document["baked_families"], "free_family_kept")
    require("Claude" in document["baked_families"] and "Gemini" in document["baked_families"], "big_name_families_kept")
    require("sk-" not in registry.read_text(encoding="utf-8"), "registry_has_no_secret_prefix")

    require(
        resolve_update_route("update available models") == ENGEL_MODEL_CATALOG_UPDATE_ROUTE_ID,
        "alias_resolves",
    )
    rendered = render_update_route(ENGEL_MODEL_CATALOG_UPDATE_ROUTE_ID, "update available models offline")
    require("Jev source: https://github.com/typesafe-ai/typesafe-sdk-python" in rendered, "route_names_github")
    require("does not write the chat reply" in rendered, "route_says_jev_is_not_the_reply")
    worker = (ROOT / "tools" / "engel_main_local_model_worker.py").read_text(encoding="utf-8")
    require("order_fallback_with_jev" in worker, "worker_asks_jev_on_fallback")
    flutter = (ROOT / "engel_flutter_main" / "lib" / "main.dart").read_text(encoding="utf-8")
    require("Update available models" in flutter, "picker_has_updater")
    require("provider == 'nvidia'" in flutter, "picker_can_select_nvidia")

    failed = [name for ok, name in checks if not ok]
    print(f"jev model router {len(checks) - len(failed)}/{len(checks)}")
    for name in failed:
        print("FAIL", name)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
