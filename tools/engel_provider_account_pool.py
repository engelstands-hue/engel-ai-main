#!/usr/bin/env python3
"""Multi-account pool for Engel AI Main and bots.

Accounts are home/profile slots, never secret values. Chat memory stays on
CT246 / Engel memory regardless of which account is active.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parents[1]
POOL_PATH = ROOT / "memory" / "personality" / "ENGEL_PROVIDER_ACCOUNT_POOL.json"
SCHEMA = "engel_provider_account_pool_v1"
USAGE_HOLD_HOURS = 6
MAIN_PROVIDERS = ("grok", "codex", "chatgpt", "gemini", "nvidia", "openai", "xai")
PROVIDER_ALIASES = {
    "xai": "grok",
    "openai": "chatgpt",
}
USAGE_MARKERS = (
    "rate limit",
    "ratelimit",
    "quota",
    "usage limit",
    "usage_limit",
    "too many requests",
    "429",
    "resource exhausted",
    "insufficient_quota",
    "you've reached",
    "you have reached",
    "limit exceeded",
    "out of credits",
    "credit limit",
    "try again later",
    "temporarily rate-limited",
)


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_utc(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def canonical_provider(name: str) -> str:
    key = str(name or "").strip().lower()
    return PROVIDER_ALIASES.get(key, key)


def error_is_usage_exhausted(text: str) -> bool:
    low = " ".join(str(text or "").casefold().split())
    if not low:
        return False
    if re.search(r"\b429\b", low):
        return True
    return any(marker in low for marker in USAGE_MARKERS)


def _empty_pool() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "authority": "Josh > Guardian > Engel/runtime",
        "memory_core": "CT246 /opt/engel plus Engel memory/ — not owned by a provider account",
        "providers": {},
        "updated_at_utc": _iso_now(),
    }


def load_pool() -> dict[str, Any]:
    try:
        data = json.loads(POOL_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty_pool()
    if not isinstance(data, dict):
        return _empty_pool()
    providers = data.get("providers")
    if not isinstance(providers, dict):
        data["providers"] = {}
    return data


def save_pool(pool: dict[str, Any]) -> None:
    pool["schema"] = SCHEMA
    pool["updated_at_utc"] = _iso_now()
    POOL_PATH.parent.mkdir(parents=True, exist_ok=True)
    POOL_PATH.write_text(json.dumps(pool, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _accounts(pool: dict[str, Any], provider: str) -> list[dict[str, Any]]:
    key = canonical_provider(provider)
    row = pool.get("providers", {}).get(key)
    if not isinstance(row, dict):
        return []
    accounts = row.get("accounts")
    if not isinstance(accounts, list):
        return []
    return [item for item in accounts if isinstance(item, dict)]


def _ensure_provider(pool: dict[str, Any], provider: str) -> dict[str, Any]:
    key = canonical_provider(provider)
    providers = pool.setdefault("providers", {})
    row = providers.get(key)
    if not isinstance(row, dict):
        row = {"accounts": [], "active_account_id": ""}
        providers[key] = row
    if not isinstance(row.get("accounts"), list):
        row["accounts"] = []
    return row


def _account_ready(account: dict[str, Any]) -> bool:
    if str(account.get("status") or "") == "needs_login":
        return False
    until = _parse_utc(str(account.get("exhausted_until_utc") or ""))
    if until and until > datetime.now(timezone.utc):
        return False
    if until and until <= datetime.now(timezone.utc):
        account["status"] = "ready"
        account["exhausted_until_utc"] = ""
    return str(account.get("status") or "ready") != "disabled"


def iter_ready_accounts(provider: str) -> Iterator[dict[str, Any]]:
    pool = load_pool()
    row = _ensure_provider(pool, provider)
    accounts = _accounts(pool, provider)
    if not accounts:
        return
    active = str(row.get("active_account_id") or "")
    ordered = accounts
    if active:
        idx = next((i for i, acc in enumerate(accounts) if str(acc.get("id")) == active), -1)
        if idx >= 0:
            ordered = accounts[idx + 1 :] + accounts[: idx + 1]
    for acc in ordered:
        if _account_ready(acc):
            yield acc


def pick_account(provider: str) -> dict[str, Any] | None:
    for acc in iter_ready_accounts(provider):
        return acc
    return None


def mark_used(provider: str, account_id: str) -> None:
    pool = load_pool()
    row = _ensure_provider(pool, provider)
    aid = str(account_id or "")
    for acc in _accounts(pool, provider):
        if str(acc.get("id")) == aid:
            acc["last_used_utc"] = _iso_now()
            acc["status"] = "ready"
            row["active_account_id"] = aid
            save_pool(pool)
            return


def mark_exhausted(provider: str, account_id: str, reason: str = "") -> None:
    pool = load_pool()
    aid = str(account_id or "")
    until = (datetime.now(timezone.utc) + timedelta(hours=USAGE_HOLD_HOURS)).replace(microsecond=0)
    for acc in _accounts(pool, provider):
        if str(acc.get("id")) == aid:
            acc["status"] = "exhausted"
            acc["exhausted_until_utc"] = until.isoformat().replace("+00:00", "Z")
            acc["exhausted_reason"] = str(reason or "usage")[:160]
            save_pool(pool)
            return


def home_dir_for(provider: str, account_id: str) -> Path:
    key = canonical_provider(provider)
    aid = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(account_id or "primary").strip()) or "primary"
    if key == "grok":
        if aid in {"primary", "default", "super"}:
            return ROOT
        return ROOT / "runtime" / "xai_grok_cli" / "accounts" / aid
    if key == "codex":
        if aid in {"primary", "default"}:
            return ROOT / "runtime" / "cli_accounts" / "codex" / "home"
        return ROOT / "runtime" / "cli_accounts" / "codex" / "accounts" / aid / "home"
    return ROOT / "run" / "secrets" / "provider_accounts" / key / aid


def add_account(provider: str, *, label: str = "", kind: str = "cli") -> dict[str, Any]:
    pool = load_pool()
    key = canonical_provider(provider)
    row = _ensure_provider(pool, key)
    existing = _accounts(pool, key)
    n = len(existing) + 1
    aid = f"{key}-{n}"
    while any(str(acc.get("id")) == aid for acc in existing):
        n += 1
        aid = f"{key}-{n}"
    home = home_dir_for(key, aid)
    home.mkdir(parents=True, exist_ok=True)
    account = {
        "id": aid,
        "provider": key,
        "label": str(label or f"{key} account {n}")[:80],
        "kind": kind if kind in {"cli", "api_slot"} else "cli",
        "home_dir": str(home),
        "status": "needs_login",
        "exhausted_until_utc": "",
        "last_used_utc": "",
        "secrets_in_registry": False,
    }
    row["accounts"].append(account)
    save_pool(pool)
    return account


def public_snapshot() -> dict[str, Any]:
    pool = load_pool()
    out: dict[str, Any] = {
        "schema": SCHEMA,
        "memory_core": pool.get("memory_core"),
        "providers": {},
        "secrets_visible": False,
    }
    for key in MAIN_PROVIDERS:
        accounts = []
        for acc in _accounts(pool, key):
            accounts.append(
                {
                    "id": acc.get("id"),
                    "label": acc.get("label"),
                    "kind": acc.get("kind"),
                    "status": acc.get("status"),
                    "exhausted": bool(acc.get("status") == "exhausted"),
                    "home_dir": acc.get("home_dir"),
                }
            )
        if accounts:
            out["providers"][canonical_provider(key)] = {"accounts": accounts}
    return out


def seed_primary_accounts() -> dict[str, Any]:
    pool = load_pool()
    seeds = [
        ("grok", "primary", "Grok Super CLI", "cli", str(ROOT)),
        ("codex", "primary", "Codex / ChatGPT CLI", "cli", str(ROOT / "runtime" / "cli_accounts" / "codex" / "home")),
        ("nvidia", "primary", "NVIDIA NIM", "api_slot", str(ROOT / "run" / "secrets" / "nvidia.env")),
        ("gemini", "primary", "Gemini API", "api_slot", str(ROOT / "run" / "secrets" / "provider_bridges.env")),
        ("chatgpt", "primary", "ChatGPT browser / OpenAI", "cli", str(ROOT / "browser_profile" / "chatgpt")),
    ]
    for provider, aid, label, kind, home in seeds:
        row = _ensure_provider(pool, provider)
        if any(str(acc.get("id")) == aid for acc in _accounts(pool, provider)):
            continue
        row["accounts"].append(
            {
                "id": aid,
                "provider": canonical_provider(provider),
                "label": label,
                "kind": kind,
                "home_dir": home,
                "status": "ready",
                "exhausted_until_utc": "",
                "last_used_utc": "",
                "secrets_in_registry": False,
            }
        )
        if not row.get("active_account_id"):
            row["active_account_id"] = aid
    save_pool(pool)
    return pool


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Engel provider account pool")
    parser.add_argument("--seed", action="store_true")
    parser.add_argument("--add", default="")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args(argv)
    if args.seed:
        seed_primary_accounts()
    if args.add:
        acc = add_account(args.add)
        print(json.dumps({"ok": True, "id": acc.get("id"), "home_dir": acc.get("home_dir")}, sort_keys=True))
        return 0
    if args.list or args.seed:
        print(json.dumps(public_snapshot(), indent=2, sort_keys=True))
        return 0
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
