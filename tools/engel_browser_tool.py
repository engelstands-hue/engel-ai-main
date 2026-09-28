#!/usr/bin/env python3
"""
Engel AI Main — general browser / computer-use tool.

Ported concept from OpenClaw (MIT) browser extension (dist/browser-cli-*:
navigate/click/type/drag/screenshot/snapshot/tabs/cookies). A real Playwright-
driven Chromium the agent can operate: navigate a page, read its text, take an
accessibility SNAPSHOT of interactive elements (so it can click by index or
selector), click/type/press, run JS, follow links, manage cookies and tabs.

Runs on Engel's existing browser_ai_venv (Playwright + Chromium already
installed for the ChatGPT bridge). Two modes:
  * daemon  — holds a live browser; reads {cmd,...} JSON lines on stdin, writes
              {ok,...} on stdout. This is how the agent drives multi-step work.
  * one-shot CLI — do a small action sequence in one launch (navigate/text/shot).

MIT-attributed. Must be run with runtime/browser_ai_venv/Scripts/python.exe.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
PROFILE_DIR = ROOT / "runtime" / "browser_control" / "general"
SHOT_DIR = ROOT / "runtime" / "browser_control" / "shots"

# Selectors considered "interactive" for the accessibility snapshot.
_INTERACTIVE = "a[href], button, input, textarea, select, [role=button], [role=link], [onclick]"


class BrowserSession:
    def __init__(self, headless: bool = True, profile: bool = True):
        from playwright.sync_api import sync_playwright  # noqa: E402
        PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        self._pw = sync_playwright().start()
        if profile:
            self.ctx = self._pw.chromium.launch_persistent_context(
                str(PROFILE_DIR), headless=headless,
                args=["--no-first-run", "--no-default-browser-check"])
            self.page = self.ctx.pages[0] if self.ctx.pages else self.ctx.new_page()
            self.browser = None
        else:
            self.browser = self._pw.chromium.launch(headless=headless)
            self.ctx = self.browser.new_context()
            self.page = self.ctx.new_page()
        self.page.set_default_timeout(15000)

    # --- navigation ---
    def navigate(self, url: str, wait_until: str = "domcontentloaded") -> dict:
        if "://" not in url:
            url = "https://" + url
        resp = self.page.goto(url, wait_until=wait_until, timeout=30000)
        return {"ok": True, "url": self.page.url, "title": self.page.title(),
                "status": resp.status if resp else None}

    def back(self) -> dict:
        self.page.go_back()
        return {"ok": True, "url": self.page.url, "title": self.page.title()}

    def reload(self) -> dict:
        self.page.reload()
        return {"ok": True, "url": self.page.url, "title": self.page.title()}

    # --- reading ---
    def title(self) -> dict:
        return {"ok": True, "title": self.page.title(), "url": self.page.url}

    def text(self, selector: str = "body", max_chars: int = 8000) -> dict:
        try:
            t = self.page.inner_text(selector)
        except Exception:
            t = self.page.evaluate("() => document.body ? document.body.innerText : ''")
        clipped = t[:max_chars]
        return {"ok": True, "chars": len(t), "text": clipped + ("\n…[clipped]" if len(t) > max_chars else "")}

    def snapshot(self, limit: int = 60) -> dict:
        """Compact accessibility snapshot: enumerated interactive elements the
        agent can click by index. Mirrors OpenClaw's snapshot-then-act flow."""
        js = """(opts) => {
          const els = Array.from(document.querySelectorAll(opts.sel)).slice(0, opts.limit);
          return els.map((e, i) => {
            const r = e.getBoundingClientRect();
            const visible = r.width > 0 && r.height > 0 && r.top < (window.innerHeight+200) && r.bottom > -200;
            return { index: i, tag: e.tagName.toLowerCase(),
                     text: (e.innerText || e.value || e.getAttribute('aria-label') || e.getAttribute('placeholder') || '').trim().slice(0,80),
                     href: e.getAttribute('href') || '', role: e.getAttribute('role') || '',
                     id: e.id || '', name: e.getAttribute('name') || '', visible };
          });
        }"""
        items = self.page.evaluate(js, {"sel": _INTERACTIVE, "limit": limit})
        self._snapshot_cache = items
        return {"ok": True, "url": self.page.url, "count": len(items),
                "elements": [it for it in items if it.get("visible")] or items}

    def links(self, limit: int = 40) -> dict:
        js = """(limit) => Array.from(document.querySelectorAll('a[href]')).slice(0,limit)
                 .map(a => ({text:(a.innerText||'').trim().slice(0,80), href:a.href}))
                 .filter(l => l.href && !l.href.startsWith('javascript'))"""
        return {"ok": True, "links": self.page.evaluate(js, limit)}

    def screenshot(self, path: Optional[str] = None, full_page: bool = False, as_base64: bool = False) -> dict:
        SHOT_DIR.mkdir(parents=True, exist_ok=True)
        if not path:
            path = str(SHOT_DIR / f"shot_{int(time.time()*1000)}.png")
        self.page.screenshot(path=path, full_page=full_page)
        out = {"ok": True, "path": path, "bytes": os.path.getsize(path)}
        if as_base64:
            out["base64"] = base64.b64encode(Path(path).read_bytes()).decode("ascii")
        return out

    # --- acting ---
    def click(self, selector: str) -> dict:
        self.page.click(selector, timeout=10000)
        return {"ok": True, "clicked": selector, "url": self.page.url}

    def click_index(self, index: int) -> dict:
        items = getattr(self, "_snapshot_cache", None)
        if not items or index < 0 or index >= len(items):
            return {"ok": False, "error": "no snapshot or index out of range; call snapshot first"}
        el = items[index]
        sel = f"#{el['id']}" if el.get("id") else (f"a[href='{el['href']}']" if el.get("href") else el["tag"])
        try:
            self.page.locator(sel).nth(0).click(timeout=10000)
            return {"ok": True, "clicked_index": index, "selector": sel, "url": self.page.url}
        except Exception as exc:
            return {"ok": False, "error": str(exc)[:120]}

    def fill(self, selector: str, value: str) -> dict:
        self.page.fill(selector, value, timeout=10000)
        return {"ok": True, "filled": selector}

    def type(self, selector: str, text: str, delay: int = 20) -> dict:
        self.page.type(selector, text, delay=delay, timeout=10000)
        return {"ok": True, "typed_into": selector}

    def press(self, key: str) -> dict:
        self.page.keyboard.press(key)
        return {"ok": True, "pressed": key}

    def eval_js(self, expr: str) -> dict:
        return {"ok": True, "result": self.page.evaluate(expr)}

    # --- tabs / cookies ---
    def new_tab(self, url: str = "") -> dict:
        self.page = self.ctx.new_page()
        if url:
            return self.navigate(url)
        return {"ok": True, "tabs": len(self.ctx.pages)}

    def cookies(self) -> dict:
        return {"ok": True, "cookies": self.ctx.cookies()}

    def close(self) -> None:
        try:
            (self.ctx or self.browser).close()
        except Exception:
            pass
        try:
            self._pw.stop()
        except Exception:
            pass


def _dispatch(sess: BrowserSession, msg: dict) -> dict:
    cmd = msg.get("cmd")
    try:
        if cmd == "navigate":
            return sess.navigate(msg["url"], msg.get("wait_until", "domcontentloaded"))
        if cmd == "text":
            return sess.text(msg.get("selector", "body"), int(msg.get("max_chars", 8000)))
        if cmd == "snapshot":
            return sess.snapshot(int(msg.get("limit", 60)))
        if cmd == "links":
            return sess.links(int(msg.get("limit", 40)))
        if cmd == "screenshot":
            return sess.screenshot(msg.get("path"), bool(msg.get("full_page")), bool(msg.get("base64")))
        if cmd == "click":
            return sess.click(msg["selector"])
        if cmd == "click_index":
            return sess.click_index(int(msg["index"]))
        if cmd == "fill":
            return sess.fill(msg["selector"], msg.get("value", ""))
        if cmd == "type":
            return sess.type(msg["selector"], msg.get("text", ""))
        if cmd == "press":
            return sess.press(msg["key"])
        if cmd == "eval":
            return sess.eval_js(msg["expr"])
        if cmd in ("title", "url"):
            return sess.title()
        if cmd == "back":
            return sess.back()
        if cmd == "reload":
            return sess.reload()
        if cmd == "new_tab":
            return sess.new_tab(msg.get("url", ""))
        if cmd == "cookies":
            return sess.cookies()
        if cmd == "ping":
            return {"ok": True, "status": "browser tool ready"}
        return {"ok": False, "error": f"unknown cmd: {cmd}"}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:160]}"}


def _daemon(headless: bool) -> int:
    sess = BrowserSession(headless=headless)
    sys.stdout.write(json.dumps({"id": "startup", "ok": True, "status": "engel browser tool ready"}) + "\n")
    sys.stdout.flush()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if msg.get("cmd") == "stop":
            sys.stdout.write(json.dumps({"id": msg.get("id"), "ok": True, "stopped": True}) + "\n")
            sys.stdout.flush()
            break
        res = _dispatch(sess, msg)
        res["id"] = msg.get("id")
        sys.stdout.write(json.dumps(res) + "\n")
        sys.stdout.flush()
    sess.close()
    return 0


def _cli(argv: Optional[list[str]] = None) -> int:
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="Engel browser / computer-use tool (OpenClaw browser port).")
    ap.add_argument("--daemon", action="store_true", help="stdin/stdout JSON command loop (agent drives it)")
    ap.add_argument("--headed", action="store_true", help="show the browser window (default headless)")
    ap.add_argument("--navigate", default="", help="one-shot: URL to open")
    ap.add_argument("--text", action="store_true", help="one-shot: print page text")
    ap.add_argument("--snapshot", action="store_true", help="one-shot: print interactive-element snapshot")
    ap.add_argument("--screenshot", default="", help="one-shot: screenshot to this path")
    a = ap.parse_args(argv)
    if a.daemon:
        return _daemon(headless=not a.headed)
    if not a.navigate:
        ap.print_help()
        return 0
    sess = BrowserSession(headless=not a.headed)
    try:
        print(json.dumps(sess.navigate(a.navigate), indent=2))
        if a.text:
            print(json.dumps(sess.text(), indent=2)[:1500])
        if a.snapshot:
            print(json.dumps(sess.snapshot(), indent=2)[:2000])
        if a.screenshot:
            print(json.dumps(sess.screenshot(a.screenshot), indent=2))
    finally:
        sess.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
