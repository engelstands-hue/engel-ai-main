#!/usr/bin/env python3
"""App builds use Engel local LLMs first. Grok must not 240s-stall FILE generates."""
from __future__ import annotations

import inspect
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
for entry in (str(ROOT), str(TOOLS)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import engel_main_server_chat_http_service as chat


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    source = inspect.getsource(chat._build_lane_grok46_enabled)
    require(
        'get("ENGEL_BUILD_GROK46_FIRST", "0")' in source,
        "Grok-first is still the default build route",
    )
    require(
        chat._build_lane_grok46_enabled(local_only=False) is False
        or os.environ.get("ENGEL_BUILD_GROK46_FIRST", "").strip().casefold()
        in {"1", "true", "yes", "on"},
        "Grok-first is still enabled without an explicit env opt-in",
    )
    generate_src = inspect.getsource(chat._build_lane_generate)
    require(
        "Engel local LLMs first" in generate_src,
        "build generate docstring still says Grok 4.6 Super CLI first",
    )
    grok_first = generate_src.find("if grok_first:")
    local_at = generate_src.find('"ct246_local_coder_gguf"')
    require(grok_first != -1 and local_at != -1 and grok_first < local_at, "route construction lost")
    huge = "FILE: lib/main.dart\n```dart\n" + ("void main() {}\n" * 600)
    skipped = chat._call_grok46_build_bridge(huge, {"model": "grok-4.6"}, time.perf_counter())
    require(skipped.get("ok") is not True, "oversized Grok build prompt was still sent to the CLI")
    require(
        "240s" in str(skipped.get("error") or "")
        or "local LLMs" in str(skipped.get("error") or "").casefold(),
        f"Grok skip did not name the timeout/local fallback: {skipped.get('error')}",
    )
    gpu_src = inspect.getsource(chat._build_lane_rog_gpu_local_generate)
    require("else 2500" in gpu_src, "ROG GPU local generate cap is still 1800 tokens")
    import engel_build_lane as build_lane

    require(
        build_lane._should_split_build_into_hive_packages(
            bounded_enabled=True,
            existing_files={},
            lang="flutter",
            desc="Recreate this using Flutter",
            build_size="medium",
            conical_required=True,
        )
        is True,
        "medium Flutter hive builds still dump the whole project on one model",
    )
    require(
        build_lane._should_split_build_into_hive_packages(
            bounded_enabled=True,
            existing_files={"lib/main.dart": "void main() {}"},
            lang="flutter",
            desc="Recreate this using Flutter",
            build_size="medium",
            conical_required=True,
        )
        is False,
        "complete-project repair was forced into a new hive split",
    )
    print("ENGEL_LOCAL_LLM_BUILD_FIRST_VERIFY_PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"FAIL verify_engel_local_llm_build_first: {exc}")
        raise SystemExit(2) from exc
