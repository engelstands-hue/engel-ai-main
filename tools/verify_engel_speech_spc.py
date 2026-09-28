#!/usr/bin/env python3
"""Prove Engel AI Main's Speech Packet Compiler stays non-authorizing."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import engel_speech_spc as spc  # noqa: E402


def main() -> int:
    checks: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, bool(ok), detail))

    a = spc.compile_speech_packet(kind="speak", text="hello Engel", caller="unit")
    b = spc.compile_speech_packet(kind="speak", text="hello Engel", caller="unit")
    check("compiler_is_deterministic", a["packet_hash"] == b["packet_hash"], a["packet_hash"][:16])
    check("never_authorizes_execution", a.get("execution_authorized") is False, str(a.get("execution_authorized")))
    check("never_authorizes_playback", a.get("playback_authorized") is False, str(a.get("playback_authorized")))
    check("never_authorizes_capture", a.get("capture_authorized") is False, str(a.get("capture_authorized")))
    check("no_cloud", a.get("does_not_call_cloud") is True, "local")
    check("sub_engel_is_not_chase", a.get("sub_engel_is_not_chase") is True, "peer")
    mmap = spc.inspect_sub_engel_mmap()
    check(
        "sub_engel_mmap_is_not_ct246_resident",
        mmap.get("preferred_uses_gguf_mmap") is False
        and mmap.get("not_ct246_resident_mmap") is True
        and mmap.get("sub_engel_is_not_chase") is True,
        str(mmap.get("preferred_runtime")),
    )
    check(
        "legacy_llama_cli_mmap_defaults_on",
        (mmap.get("legacy_llama_cpp") or {}).get("mmap", "").startswith("llama.cpp default enabled"),
        str((mmap.get("legacy_llama_cpp") or {}).get("mmap")),
    )

    hear = spc.compile_speech_packet(kind="hear", text="hello Engel", caller="unit")
    check("hear_and_speak_are_distinct_kinds", hear.get("kind") == "hear" and a.get("kind") == "speak", hear.get("kind"))

    discord = spc.compile_speech_packet(
        kind="speak",
        text="hello Engel",
        source="discord_public",
        caller="unit",
    )
    check("discord_stays_text_only", discord.get("lane") == "speak_skip", str(discord.get("lane")))

    wrapped = spc.attach_speech_spc(
        "hello Engel",
        "I'm here.",
        {"ok": True, "humanization_slm_used": True, "lnt": {"effect": "converse", "contract_id": "x"}},
        source="ct_main_chat_turn",
        caller="unit",
    )
    check(
        "bind_exposes_spc",
        wrapped.get("speech_spc", {}).get("name") == "speech_packet_compiler",
        str(wrapped.get("speech_spc")),
    )
    check(
        "bind_keeps_playback_unsigned",
        wrapped.get("speech_spc", {}).get("playback_authorized") is False,
        "unsigned",
    )

    chat_src = (ROOT / "tools" / "engel_main_server_chat_http_service.py").read_text(encoding="utf-8")
    check(
        "ct_chat_binds_speech_spc",
        "def _attach_speech_spc(" in chat_src and "_attach_speech_spc(receipt, prompt, source)" in chat_src,
        "chat service",
    )
    worker_src = (ROOT / "tools" / "engel_main_local_model_worker.py").read_text(encoding="utf-8")
    check("worker_intercepts_spc", "speech_spc" in worker_src or "engel_speech_spc" in worker_src, "worker")
    routes_src = (ROOT / "engel_ai_update_routes.py").read_text(encoding="utf-8")
    check(
        "routes_register_spc",
        "engel.speech_spc.status" in routes_src and "engel.speech_spc.compile" in routes_src,
        "routes",
    )
    explorer_src = (ROOT / "engel_route_explorer.py").read_text(encoding="utf-8")
    check("explorer_groups_spc", "engel.speech_spc" in explorer_src, "explorer")
    check("no_network_imports", "requests" not in Path(spc.__file__).read_text(encoding="utf-8"), "stdlib")

    failed = [name for name, ok, _ in checks if not ok]
    for name, ok, detail in checks:
        print(("PASS" if ok else "FAIL"), name, "::", str(detail)[:160])
    print(f"{sum(1 for _, ok, _ in checks if ok)}/{len(checks)} checks passed")
    print("verify_engel_speech_spc: " + ("GREEN" if not failed else "RED"))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
