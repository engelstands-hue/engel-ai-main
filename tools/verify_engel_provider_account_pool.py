#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import engel_provider_account_pool as pool


def main() -> int:
    errors: list[str] = []
    if pool.canonical_provider("xai") != "grok":
        errors.append("xai should alias to grok")
    if "claude" in pool.MAIN_PROVIDERS or "anthropic" in pool.MAIN_PROVIDERS:
        errors.append("Claude/Anthropic must not be in the account pool")
    if not pool.error_is_usage_exhausted("HTTP 429 rate limit exceeded"):
        errors.append("429 rate limit should count as exhausted")
    if pool.error_is_usage_exhausted("hello"):
        errors.append("hello should not count as exhausted")
    original = pool.POOL_PATH
    with tempfile.TemporaryDirectory() as tmp:
        pool.POOL_PATH = Path(tmp) / "pool.json"
        seeded = pool.seed_primary_accounts()
        grok = seeded.get("providers", {}).get("grok", {})
        if not grok.get("accounts"):
            errors.append("seed missing grok primary")
        extra = pool.add_account("grok", label="Grok spare")
        if extra.get("id") == "primary":
            errors.append("extra grok account reused primary id")
        home = Path(str(extra.get("home_dir") or ""))
        if not str(home).replace("\\", "/").endswith(f"accounts/{extra.get('id')}") and extra.get("id") not in str(home):
            errors.append(f"extra home unexpected: {home}")
        picked = pool.pick_account("grok")
        if not picked:
            errors.append("pick_account grok failed")
        pool.mark_exhausted("grok", str(picked.get("id")), "429")
        nxt = pool.pick_account("grok")
        if nxt and str(nxt.get("id")) == str(picked.get("id")):
            errors.append("exhausted account was picked again")
        snap = pool.public_snapshot()
        if snap.get("secrets_visible") is True:
            errors.append("public snapshot must not show secrets")
        raw = json.dumps(snap)
        if "sk-" in raw or "Bearer" in raw:
            errors.append("snapshot looks like it contains a secret")
    pool.POOL_PATH = original
    if errors:
        for err in errors:
            print("FAIL:", err)
        return 1
    print("PASS: engel_provider_account_pool")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
