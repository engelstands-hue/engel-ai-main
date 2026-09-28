#!/usr/bin/env python3
"""Verify the chat-box provider picker chain (Flutter -> worker -> CT246 body).

Offline: the worker's CT246 POST is captured with a patched urlopen; the
Flutter side is checked at source level (the widget suite runs separately).
"""
from __future__ import annotations

import io
import json
import sys
import urllib.request
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
ROOT = TOOLS_DIR.parent
for entry in (str(ROOT), str(TOOLS_DIR)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import engel_main_local_model_worker as worker  # noqa: E402

CHECKS: list[tuple[str, bool]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail and not ok else ""))


class _FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def main() -> int:
    # 1. dropdown force contract normalization
    check("force_required",
          worker._ui_forced_provider({"provider": "anthropic"}) == "")
    check("valid_choice_honored",
          worker._ui_forced_provider(
              {"provider": "Anthropic", "force_provider": True}) == "anthropic")
    check("selected_provider_fallback",
          worker._ui_forced_provider(
              {"selected_provider": "gemini", "force_provider": True}) == "gemini")
    check("invalid_choice_dropped",
          worker._ui_forced_provider(
              {"provider": "not-a-provider", "force_provider": True}) == "")

    # 2. fast-lane CT246 body carries the forced provider
    captured: dict = {}
    real_urlopen = urllib.request.urlopen
    real_training_guard = worker._local_only_training_active

    def fake_urlopen(req, timeout=0):
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _FakeResponse(json.dumps(
            {"ok": True, "assistant_reply": "hi", "status": "chat replied"}
        ).encode("utf-8"))

    urllib.request.urlopen = fake_urlopen
    try:
        # This assertion owns the normal chat contract. A real training run may
        # be active while the suite runs, so isolate the picker case instead of
        # letting mutable environment state make the verifier nondeterministic.
        worker._local_only_training_active = lambda now_epoch=None: False
        worker._main_server_fast_chat(
            "hello there", 30, 64, 0.1, conversation_id="verify",
            ui_provider="anthropic")
        body = captured.get("body") or {}
        check("fast_lane_forces_provider",
              body.get("provider") == "anthropic"
              and body.get("selected_provider") == "anthropic"
              and body.get("force_provider") is True)
        captured.clear()
        worker._main_server_fast_chat(
            "hello there", 30, 64, 0.1, conversation_id="verify")
        body = captured.get("body") or {}
        check("fast_lane_auto_stays_local_first",
              body.get("provider") == "local" and "force_provider" not in body)

        # The opposite contract is equally important: active local-only
        # training outranks the UI picker and disables provider fallback.
        captured.clear()
        worker._local_only_training_active = lambda now_epoch=None: True
        worker._main_server_fast_chat(
            "hello there", 30, 64, 0.1, conversation_id="verify",
            ui_provider="anthropic")
        body = captured.get("body") or {}
        check("training_guard_overrides_picker",
              body.get("provider") == "local"
              and body.get("selected_provider") == "local"
              and body.get("allow_provider_fallback") is False
              and body.get("local_only_training") is True)
    finally:
        worker._local_only_training_active = real_training_guard
        urllib.request.urlopen = real_urlopen

    # 3. stream lane wired identically (source-level)
    source = (ROOT / "tools" / "engel_main_local_model_worker.py").read_text(
        encoding="utf-8")
    stream_src = source.split("def _stream_server_chat(", 1)[1].split("\ndef ", 1)[0]
    check("stream_lane_has_ui_provider",
          'ui_provider: str = ""' in stream_src
          and '"force_provider"' in stream_src)
    handler_src = source.split("def _ui_forced_provider(", 1)[1]
    check("build_lane_forwards_picker",
          'ui_provider = _ui_forced_provider(payload)' in source
          and 'ui_model = _ui_requested_model(payload) if ui_provider else ""' in source
          and 'ui_provider = "" if server_action_request else' not in source)

    # 4. Flutter side (source-level; widget suite runs separately)
    dart = (ROOT / "engel_flutter_main" / "lib" / "main.dart").read_text(
        encoding="utf-8")
    check("dart_dropdown_present", "engel-chat-provider" in dart
          and "_chatProviderChoice" in dart)
    # (2026-07-31, refreshed 2026-08-27) The submit path captures the effective
    # dropdown choice into a local BEFORE the async gap.  The getter normalizes
    # Automatic to the local-first sentinel while preserving an intentional
    # one-shot override.  Assert that captured-local handoff (rather than a
    # direct field read later in the async method) so a mid-turn dropdown change
    # cannot mutate an in-flight request.
    check("dart_payload_force_contract",
          "'force_provider': true" in dart
          and "final providerChoice = _effectiveChatProvider;" in dart
          and "provider: providerChoice," in dart)
    check("dart_auto_default", "var _chatProviderChoice = 'auto';" in dart)

    failed = [name for name, ok in CHECKS if not ok]
    print(f"\n{len(CHECKS) - len(failed)}/{len(CHECKS)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
