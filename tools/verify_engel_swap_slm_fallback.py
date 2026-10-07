#!/usr/bin/env python3
"""The small SLM answers ordinary chat while the container is paging."""

from __future__ import annotations

import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import engel_swap_slm_fallback as slm  # noqa: E402


CHAT = ROOT / "tools" / "engel_main_server_chat_http_service.py"
CLEAR = "SwapTotal: 2097152 kB\nSwapFree: 2097152 kB\n"
PAGING = "SwapTotal: 2097152 kB\nSwapFree: 446872 kB\n"


def main() -> int:
    failures: list[str] = []

    def require(ok: bool, message: str) -> None:
        if ok:
            print("[PASS]", message)
        else:
            failures.append(message)
            print("[FAIL]", message)

    prior = os.environ.get("ENGEL_SWAP_SLM_FALLBACK")
    try:
        os.environ.pop("ENGEL_SWAP_SLM_FALLBACK", None)
        clear = slm.big_lane_blocked(meminfo=CLEAR, cgroup={})
        require(clear.get("blocked") is False and clear.get("automatic") is True, "clear memory keeps the big lane")
        paging = slm.big_lane_blocked(meminfo=PAGING, cgroup={})
        require(paging.get("blocked") is True and paging.get("reason") == "host_paging", "paging selects the SLM")
        require(paging.get("automatic") is True, "the route is automatic")
        require(paging.get("model_id") == "qwen2.5-0.5b-instruct", "fallback model is the 0.5B SLM")
        cgroup_swap = slm.big_lane_blocked(
            meminfo=CLEAR,
            cgroup={"memory.swap.current": 1689886720, "memory.current": 100},
        )
        require(cgroup_swap.get("reason") == "cgroup_swap", "cgroup swap selects the SLM")
        near = slm.big_lane_blocked(
            meminfo=CLEAR,
            cgroup={"memory.current": 90, "memory.high": 100, "memory.swap.current": 0},
        )
        require(near.get("reason") == "near_memory_cap", "near the memory cap selects the SLM")
        require(
            slm.big_lane_blocked.__code__.co_varnames[:2] == ("meminfo", "cgroup"),
            "the router takes memory only",
        )
        os.environ["ENGEL_SWAP_SLM_FALLBACK"] = "0"
        disabled = slm.big_lane_blocked(meminfo=PAGING, cgroup={})
        require(disabled.get("reason") == "disabled", "env off leaves the big lane alone")
    finally:
        if prior is None:
            os.environ.pop("ENGEL_SWAP_SLM_FALLBACK", None)
        else:
            os.environ["ENGEL_SWAP_SLM_FALLBACK"] = prior

    chat = CHAT.read_text(encoding="utf-8")
    route = chat.split("def _nemotron_lightning_route_decision(", 1)[1].split("\ndef ", 1)[0]
    require("big_lane_blocked()" in route, "Nemotron route consults memory with no request")
    require("operator selected Nemotron" not in route, "a named model does not override the automatic route")
    require(route.find("big_lane_blocked()") < route.find('request.get("_force_nemotron")'), "paging is decided before the internal force flag")
    require("selected_model_id" not in Path(slm.__file__).read_text(encoding="utf-8"), "the router does not read a requested model id")
    first_slm = chat.find("_swap_pressure_slm_receipt(")
    first_nemo = chat.find("_nemotron_lightning_local_model_receipt(")
    require(0 < first_slm < first_nemo, "the SLM fallback runs before Nemotron")
    require('"ct_swap_slm_fallback": 1' in chat, "the SLM fallback is a quick-lane depth")
    require("qwen2.5-0.5b-instruct-q5_k_m.gguf" in chat, "the quick lane already points at the 0.5B GGUF")
    swap_fn = chat.split("def _swap_pressure_slm_receipt(", 1)[1].split("\ndef ", 1)[0]
    require('local["_quick_model_path"] = slm_path' in swap_fn, "paging uses the 0.5B file, not the quick-chat env model")
    require("llama-server" not in Path(slm.__file__).read_text(encoding="utf-8"), "the fallback does not start or stop llama-server")
    if failures:
        print("ENGEL_SWAP_SLM_FALLBACK_VERIFIER_FAILED")
        return 1
    print("ENGEL_SWAP_SLM_FALLBACK_VERIFIER_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
