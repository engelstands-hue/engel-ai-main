#!/usr/bin/env python3
"""
Engel AI Main — messaging channels (OpenClaw multi-channel gateway port).

Ported concept from OpenClaw (MIT): a channel receives a message on a platform
you already use, routes it through the agent, and replies on the same channel.
OpenClaw ships ~23 channels; this brings the pattern to Engel with a channel
abstraction + a full Telegram channel (HTTP long-poll getUpdates/sendMessage)
and a Discord channel (webhook send; inbound needs the gateway WS — noted).

Every inbound message is answered by Engel's multi-AI failover loop, so channel
replies "long-run using other AI" like the desktop chat. Verbose directives
(/verbose /trace /usage) are honored per chat.

LIVE USE needs a bot token (Telegram: BotFather; set ENGEL_TELEGRAM_BOT_TOKEN).
The routing is testable offline (see --self-test). MIT-attributed.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from typing import Any, Callable, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engel_agent_failover_loop as _fl  # noqa: E402
try:
    import engel_verbose as _ev  # noqa: E402
except Exception:
    _ev = None


class EngelChannel:
    """Base channel: route inbound text through the failover chat, reply via send_fn."""
    name = "base"

    def __init__(self, chain: Optional[list] = None, timeout_s: int = 60, max_tokens: int = 512):
        self.chain = chain
        self.timeout_s = timeout_s
        self.max_tokens = max_tokens
        self._verbose = _ev.SessionVerboseState() if _ev else None

    def handle_text(self, chat_id: Any, text: str, send_fn: Callable[[Any, str], None]) -> dict:
        text = (text or "").strip()
        if not text:
            return {"ok": False, "skipped": "empty"}
        # verbose directive support (per channel session)
        if _ev and self._verbose is not None:
            ack = _ev.apply_directive(self._verbose, text)
            if ack is not None:
                send_fn(chat_id, f"✓ {ack}")
                return {"ok": True, "directive": ack}
        result = _fl.run_with_failover(text, chain=self.chain, timeout_s=self.timeout_s, max_tokens=self.max_tokens)
        reply = result.reply if result.ok else "Engel couldn't reach any AI right now — please try again."
        if _ev and self._verbose is not None and self._verbose.usage != "off":
            reply += "\n\n" + _ev.format_usage_footer(len(text.split()), len(reply.split()),
                                                       level=self._verbose.usage, lane=result.provider,
                                                       latency_ms=result.elapsed_ms)
        send_fn(chat_id, reply)
        return {"ok": result.ok, "provider": result.provider, "lane": result.lane, "elapsed_ms": result.elapsed_ms}


def _http_get(url: str, timeout: int = 60) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _http_post(url: str, data: dict, timeout: int = 30) -> dict:
    body = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(url, data=body)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


class TelegramChannel(EngelChannel):
    """Telegram Bot API channel — HTTP long-poll getUpdates + sendMessage."""
    name = "telegram"

    def __init__(self, token: str, **kw):
        super().__init__(**kw)
        self.token = token
        self.base = f"https://api.telegram.org/bot{token}"

    def send(self, chat_id: Any, text: str) -> None:
        # Telegram messages cap at 4096 chars.
        _http_post(f"{self.base}/sendMessage", {"chat_id": chat_id, "text": text[:4096]})

    def poll_once(self, offset: int, poll_timeout: int = 25) -> list[dict]:
        data = _http_get(f"{self.base}/getUpdates?offset={offset}&timeout={poll_timeout}", timeout=poll_timeout + 10)
        return data.get("result", []) if data.get("ok") else []

    def run(self) -> None:
        print(f"[engel] Telegram channel live — long-polling. Replies route through the failover loop.", file=sys.stderr)
        offset = 0
        while True:
            try:
                for u in self.poll_once(offset):
                    offset = int(u["update_id"]) + 1
                    msg = u.get("message") or u.get("edited_message") or {}
                    text = msg.get("text") or ""
                    chat = (msg.get("chat") or {}).get("id")
                    if chat is not None and text:
                        self.handle_text(chat, text, self.send)
            except KeyboardInterrupt:
                print("[engel] Telegram channel stopped.", file=sys.stderr)
                return
            except Exception as exc:
                print(f"[engel] Telegram poll error: {exc}", file=sys.stderr)
                time.sleep(3)


class DiscordChannel(EngelChannel):
    """Discord channel — reply via an incoming webhook. NOTE: receiving messages
    requires the Discord Gateway WebSocket (a larger integration); this ships the
    outbound half + the routing so a bot host can wire inbound to handle_text."""
    name = "discord"

    def __init__(self, webhook_url: str = "", **kw):
        super().__init__(**kw)
        self.webhook_url = webhook_url

    def send(self, _chat_id: Any, text: str) -> None:
        if not self.webhook_url:
            raise RuntimeError("discord webhook_url not configured")
        req = urllib.request.Request(self.webhook_url, data=json.dumps({"content": text[:2000]}).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=15)


def _self_test() -> int:
    """Prove inbound routing without any token: a fake message -> failover -> captured reply."""
    print("=== channel routing self-test (no token needed) ===")
    ch = EngelChannel()
    captured = {}

    def mock_send(chat_id, text):
        captured[chat_id] = text

    r = ch.handle_text("chat-1", "In one short sentence, what are you?", mock_send)
    print(f"  routed ok={r.get('ok')} via {r.get('provider')} {r.get('elapsed_ms')}ms")
    print(f"  reply that would be sent to chat-1: {captured.get('chat-1', '')[:100]!r}")
    # directive routing
    ch.handle_text("chat-1", "/usage tokens", mock_send)
    print(f"  directive reply: {captured.get('chat-1', '')[:60]!r}")
    return 0 if captured else 1


def _cli(argv: Optional[list[str]] = None) -> int:
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="Engel messaging channels (OpenClaw port): Telegram + Discord.")
    ap.add_argument("--self-test", action="store_true", help="offline routing test (no token)")
    ap.add_argument("--telegram", action="store_true", help="run the Telegram channel (needs ENGEL_TELEGRAM_BOT_TOKEN)")
    ap.add_argument("--token", default="", help="Telegram bot token (else ENGEL_TELEGRAM_BOT_TOKEN)")
    a = ap.parse_args(argv)
    if a.self_test:
        return _self_test()
    if a.telegram:
        token = a.token or os.environ.get("ENGEL_TELEGRAM_BOT_TOKEN", "")
        if not token:
            print("No Telegram token. Set ENGEL_TELEGRAM_BOT_TOKEN or pass --token (get one from @BotFather).", file=sys.stderr)
            return 2
        TelegramChannel(token).run()
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
