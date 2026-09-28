"""Let Engel AI Main START a Discord conversation instead of only answering one.

The bridge (tools/engel_discord_bridge.py) is entirely reply-driven: every path needs a
triggering message. So Engel could never open a thread with its own peer node - it could
only wait to be spoken to. This is the missing outbound half: one message, posted as
Engel, through Discord's REST API (no second gateway session).

Deliberate limits, because an outbound post is an outward-facing action:
  * ALLOWED CHANNELS ONLY - by default the peer channels the bridge already knows
    (ENGEL_DISCORD_PEER_CHANNEL_IDS). Anything else needs --allow-any-channel, which
    exists so the operator can override on purpose, not so a lane can wander.
  * OPERATOR/OPS TOOL - nothing in the chat or action lanes calls this. It is not wired
    into the model's tool surface; a human or a human-run script invokes it.
  * ONE MESSAGE PER RUN, chunked only to respect Discord's 2000-char limit.
  * A RECEIPT for every send (or failure), so an outbound post is as auditable as a reply.

Usage:
  python3 tools/engel_discord_say.py --channel 1148755186752430163 --text "..."
  python3 tools/engel_discord_say.py --channel <id> --file note.md --mention 1537474262242168842
  python3 tools/engel_discord_say.py --channel <id> --file note.md --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "engel_discord_outbound_message_v1"
ROOT = Path(__file__).resolve().parents[1]
RECEIPT_DIR = ROOT / "reports" / "discord_outbound"
SECRETS_CANDIDATES = (
    Path(os.environ.get("ENGEL_DISCORD_SECRETS_FILE", "") or "/opt/engel/run/secrets/discord.env"),
    Path("/opt/engel/run/engel_discord_peers.env"),
)
MAX_CHARS = 1900
API = "https://discord.com/api/v10"


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            out[key.strip()] = value.strip().strip('"').strip("'")
    except OSError:
        return {}
    return out


def _bot_token() -> str:
    token = str(os.environ.get("ENGEL_DISCORD_BOT_TOKEN", "") or "").strip()
    if token:
        return token
    for candidate in SECRETS_CANDIDATES:
        env = _read_env_file(candidate)
        for key in ("ENGEL_DISCORD_BOT_TOKEN", "DISCORD_BOT_TOKEN", "DISCORD_TOKEN"):
            if env.get(key):
                return env[key]
    return ""


def allowed_channels() -> set[str]:
    ids: set[str] = set()
    for candidate in SECRETS_CANDIDATES:
        env = _read_env_file(candidate)
        for key in ("ENGEL_DISCORD_PEER_CHANNEL_IDS", "ENGEL_DISCORD_CHANNEL_ID"):
            for part in str(env.get(key, "") or "").replace(";", ",").split(","):
                part = part.strip()
                if part.isdigit():
                    ids.add(part)
    for key in ("ENGEL_DISCORD_PEER_CHANNEL_IDS", "ENGEL_DISCORD_CHANNEL_ID"):
        for part in str(os.environ.get(key, "") or "").replace(";", ",").split(","):
            part = part.strip()
            if part.isdigit():
                ids.add(part)
    return ids


def split_message(text: str, limit: int = MAX_CHARS) -> list[str]:
    """Paragraph-first split that keeps ``` fences balanced across chunks."""
    body = str(text or "").strip()
    if not body:
        return []
    chunks: list[str] = []
    while len(body) > limit:
        window = body[:limit]
        cut = window.rfind("\n\n")
        if cut < limit // 3:
            cut = window.rfind("\n")
        if cut < limit // 3:
            cut = window.rfind(" ")
        if cut <= 0:
            cut = limit
        piece = body[:cut].rstrip()
        if piece.count("```") % 2:
            piece += "\n```"
            body = "```\n" + body[cut:].lstrip()
        else:
            body = body[cut:].lstrip()
        chunks.append(piece)
    if body:
        chunks.append(body)
    return chunks


def send(channel_id: str, text: str, *, mention: str = "", dry_run: bool = False,
         allow_any_channel: bool = False) -> dict[str, Any]:
    channel_id = str(channel_id).strip()
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "created_at_utc": _iso_now(),
        "channel_id": channel_id,
        "mention": mention,
        "dry_run": bool(dry_run),
    }
    if not re.fullmatch(r"\d{5,25}", channel_id):
        receipt.update(ok=False, error="channel id must be a numeric Discord snowflake")
        return _write_receipt(receipt)
    permitted = allowed_channels()
    if not allow_any_channel and permitted and channel_id not in permitted:
        receipt.update(ok=False, error=(
            "channel is not in the allowed peer-channel list; pass --allow-any-channel "
            "to post somewhere else on purpose"), allowed=sorted(permitted))
        return _write_receipt(receipt)

    body = str(text or "").strip()
    if mention:
        body = f"<@{mention}> {body}"
    chunks = split_message(body)
    if not chunks:
        receipt.update(ok=False, error="refusing to post an empty message")
        return _write_receipt(receipt)
    receipt["chunk_count"] = len(chunks)
    receipt["preview"] = chunks[0][:300]
    if dry_run:
        receipt.update(ok=True, status="dry run - nothing was posted",
                       chars=sum(len(c) for c in chunks))
        return _write_receipt(receipt)

    token = _bot_token()
    if not token:
        receipt.update(ok=False, error="no Discord bot token available on this host")
        return _write_receipt(receipt)

    sent: list[str] = []
    for index, chunk in enumerate(chunks):
        payload = json.dumps({"content": chunk}).encode("utf-8")
        request = urllib.request.Request(
            f"{API}/channels/{channel_id}/messages", data=payload,
            headers={"Authorization": f"Bot {token}",
                     "Content-Type": "application/json",
                     "User-Agent": "EngelAIMain (engel_discord_say, v1)"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8", "replace"))
            sent.append(str(data.get("id") or ""))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            receipt.update(ok=False, error=f"HTTP {exc.code}: {detail}",
                           sent_message_ids=sent, failed_chunk=index)
            return _write_receipt(receipt)
        except Exception as exc:  # noqa: BLE001
            receipt.update(ok=False, error=f"{type(exc).__name__}: {exc}",
                           sent_message_ids=sent, failed_chunk=index)
            return _write_receipt(receipt)
        if index + 1 < len(chunks):
            time.sleep(1.0)  # stay well inside the per-channel rate limit
    receipt.update(ok=True, status="posted", sent_message_ids=sent)
    return _write_receipt(receipt)


def _write_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    try:
        RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path = RECEIPT_DIR / f"ENGEL_DISCORD_OUTBOUND_{stamp}.json"
        path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
        receipt["receipt_path"] = str(path)
    except Exception:  # noqa: BLE001 - a receipt miss must not lose the send result
        pass
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--channel", required=True)
    parser.add_argument("--text", default="")
    parser.add_argument("--file", default="")
    parser.add_argument("--mention", default="",
                        help="peer bot id to @mention (a peer only hears a mention)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-any-channel", action="store_true")
    args = parser.parse_args(argv)

    text = args.text
    if args.file:
        text = Path(args.file).read_text(encoding="utf-8-sig")
    receipt = send(args.channel, text, mention=args.mention, dry_run=args.dry_run,
                   allow_any_channel=args.allow_any_channel)
    printable = {k: v for k, v in receipt.items() if k != "preview"}
    print(json.dumps(printable, indent=2, ensure_ascii=False))
    return 0 if receipt.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
