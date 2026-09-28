#!/usr/bin/env python3
"""Full browser control of Grok Imagine (grok.com/imagine) for Engel AI Main.

Drives a real Chromium (Playwright) with a persistent Engel-owned profile so
the operator signs in once and Engel can then generate images/videos on demand:
navigate -> pick Image/Video -> type prompt -> submit -> wait -> download media.

Engel-owned state stays on D: (never C:). Subcommands:
  status                      JSON: installed/logged-in/title
  login   [--timeout S]       open a visible browser to sign in to grok.com
  imagine "<prompt>" [opts]   generate and download the result

imagine options:
  --type image|video   (default image)
  --aspect 2:3|1:1|16:9|9:16
  --mode speed|quality (default speed)
  --headless           run hidden (default: visible so you can watch/intervene)
  --timeout S          generation wait budget (default 240)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PROFILE_DIR = ROOT / "browser_profile" / "grok"
OUTPUT_DIR = ROOT / "runtime" / "grok_imagine" / "outputs"
RUNTIME_DIR = ROOT / "runtime" / "grok_imagine"
BROWSER_CACHE_DIR = ROOT / "runtime" / "ms-playwright"
TEMP_DIR = ROOT / "runtime" / "temp"
IMAGINE_URL = "https://grok.com/imagine"
PROMPT_PLACEHOLDER = "Type to imagine"

# Things that only appear when NOT signed in.
LOGGED_OUT_MARKERS = ["Sign in", "Log in", "Sign up", "Continue with Google", "Welcome back"]
# CDN hosts Grok serves generated media from.
MEDIA_HOST_HINTS = ("assets.grok.com", "imgen", "grok.com/imagine/api", "ai-cdn", "blob:")


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_os_drive(path: Path) -> bool:
    return str(path.drive).lower() == "c:"


def ensure_dirs() -> None:
    for p in (RUNTIME_DIR, OUTPUT_DIR, BROWSER_CACHE_DIR, TEMP_DIR, PROFILE_DIR):
        if is_os_drive(p):
            raise RuntimeError(f"refusing to use C: path for Engel Grok Imagine: {p}")
        p.mkdir(parents=True, exist_ok=True)


def browser_env() -> None:
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(BROWSER_CACHE_DIR))
    os.environ["ENGEL_APP_ROOT"] = str(ROOT)
    for key in ("TEMP", "TMP", "TMPDIR"):
        os.environ[key] = str(TEMP_DIR)


def _persist_receipt(payload: dict[str, Any]) -> None:
    """Leave a durable receipt in Engel's memory/reports (never break stdout)."""
    try:
        from engel_receipts import write_action_receipt
    except Exception:
        return
    schema = str(payload.get("schema") or "")
    if "status" in schema:
        action = "status"
    elif "login" in schema:
        action = "login"
    else:
        action = "imagine"
    arts = []
    if payload.get("screenshot"):
        arts.append(payload["screenshot"])
    for dl in (payload.get("downloads") or []):
        if isinstance(dl, dict) and dl.get("path"):
            arts.append(dl["path"])
    write_action_receipt(
        "grok_imagine", action, bool(payload.get("ok")),
        str(payload.get("status") or ""), payload=payload,
        summary=str(payload.get("status") or ""), artifacts=arts,
    )


def emit(payload: dict[str, Any], ok_exit: bool = True) -> int:
    payload.setdefault("updated_at_utc", iso_now())
    payload.setdefault("profile_dir", str(PROFILE_DIR))
    payload.setdefault("output_dir", str(OUTPUT_DIR))
    _persist_receipt(payload)
    print(json.dumps(payload, indent=2))
    return 0 if payload.get("ok") and ok_exit else (0 if not ok_exit else 1)


def _ensure_playwright():
    try:
        from playwright.sync_api import sync_playwright  # noqa
        return sync_playwright
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "Playwright not available in the Engel browser venv. "
            f"Expected runtime/browser_ai_venv with playwright. ({exc})"
        )


def _launch(pw, headless: bool):
    ensure_dirs()
    args = ["--disable-blink-features=AutomationControlled", "--start-maximized"]
    ctx = pw.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE_DIR),
        headless=headless,
        args=args,
        viewport=None if not headless else {"width": 1366, "height": 900},
        accept_downloads=True,
    )
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    return ctx, page


def _find_prompt(page):
    # Logged-out UI: textarea with placeholder "Type to imagine".
    # Signed-in UI (2026-07): a TipTap/ProseMirror contenteditable DIV with
    # aria-label "Ask Grok anything" in the bottom bar; the visible "Type to
    # imagine" text is decorative, not an attribute. Try both generations.
    for getter in (
        lambda: page.get_by_placeholder(PROMPT_PLACEHOLDER, exact=False),
        lambda: page.locator('textarea[placeholder*="magine" i]'),
        lambda: page.locator('div[contenteditable="true"][data-placeholder*="magine" i]'),
        lambda: page.locator('div[contenteditable="true"][aria-label*="Ask Grok" i]'),
        lambda: page.locator('div.tiptap[contenteditable="true"]'),
        lambda: page.get_by_role("textbox"),
    ):
        try:
            loc = getter().last
            loc.wait_for(state="visible", timeout=6000)
            return loc
        except Exception:
            continue
    return None


def _is_logged_in(page) -> bool:
    # Logged-out grok.com/imagine shows "Sign in" + "Sign up" CTAs; the signed-in
    # page replaces them with the account + "New Project". The prompt box is
    # present in BOTH states, so it is not a reliable signal on its own.
    try:
        body = (page.inner_text("body") or "")[:8000].lower()
    except Exception:
        body = ""
    if "sign up" in body or "log in" in body:
        return False
    if "sign in" in body and "new project" not in body:
        return False
    return True


def _select_media_type(page, media_type: str) -> bool:
    label = "Video" if media_type.lower().startswith("v") else "Image"
    for getter in (
        lambda: page.get_by_role("button", name=label, exact=True),
        lambda: page.get_by_text(label, exact=True),
    ):
        try:
            el = getter().first
            el.wait_for(state="visible", timeout=4000)
            el.click(timeout=4000)
            return True
        except Exception:
            continue
    return False


def _existing_media(page) -> set[str]:
    # The signed-in Imagine UI renders result tiles via srcset and CSS
    # background-image, not just <img src> - harvest all three forms.
    srcs: set[str] = set()
    try:
        urls = page.evaluate(
            """() => {
                const out = new Set();
                for (const el of document.querySelectorAll('img, video, source')) {
                    for (const a of ['src', 'currentSrc']) {
                        const v = el[a] || el.getAttribute(a);
                        if (v) out.add(v);
                    }
                    const ss = el.getAttribute('srcset');
                    if (ss) {
                        for (const part of ss.split(',')) {
                            const u = part.trim().split(' ')[0];
                            if (u) out.add(u);
                        }
                    }
                }
                for (const el of document.querySelectorAll('*')) {
                    const bg = getComputedStyle(el).backgroundImage;
                    if (bg && bg.includes('url(')) {
                        for (const m of bg.matchAll(/url\\((['\"]?)([^'\")]+)\\1\\)/g)) {
                            out.add(m[2]);
                        }
                    }
                }
                return Array.from(out);
            }"""
        )
        srcs.update(str(u) for u in urls if u)
    except Exception:
        try:
            for el in page.locator("img, video, source").all():
                for attr in ("src", "currentSrc"):
                    try:
                        v = el.get_attribute(attr)
                    except Exception:
                        v = None
                    if v:
                        srcs.add(v)
        except Exception:
            pass
    return srcs


def _looks_generated(url: str) -> bool:
    u = url.lower()
    if u.startswith("data:image/"):
        # The signed-in Imagine grid inlines finished images as data: URIs.
        # Big payloads are real generations; small ones are UI placeholders.
        return len(url) > 60_000
    if u.startswith("data:"):
        return False
    return any(h in u for h in MEDIA_HOST_HINTS) or u.startswith("blob:")


def _download(page, ctx, url: str, index: int, media_type: str) -> dict[str, Any] | None:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    if url.startswith("data:"):
        # Inlined generated image: decode straight from the URI.
        try:
            header, b64_payload = url.split(",", 1)
            import base64

            data = base64.b64decode(b64_payload)
        except Exception:
            return None
        if len(data) < 20_000:
            return None
        ext = ".png" if "png" in header else (".webp" if "webp" in header else ".jpg")
        out = OUTPUT_DIR / f"grok_imagine_{stamp}_{index}{ext}"
        out.write_bytes(data)
        return {"url": "data:inline-image", "path": str(out), "bytes": len(data)}
    if url.startswith("blob:"):
        # Pull blob bytes out of the page as base64 and decode here.
        try:
            b64 = page.evaluate(
                """async (u) => {
                    const r = await fetch(u);
                    const b = await r.blob();
                    const buf = await b.arrayBuffer();
                    let s = ''; const bytes = new Uint8Array(buf);
                    for (let i=0;i<bytes.length;i++){ s += String.fromCharCode(bytes[i]); }
                    return btoa(s);
                }""",
                url,
            )
            import base64
            data = base64.b64decode(b64)
        except Exception:
            return None
    else:
        try:
            resp = ctx.request.get(url, timeout=60000)
            if not resp.ok:
                return None
            data = resp.body()
        except Exception:
            return None
    ext = ".mp4" if media_type.lower().startswith("v") else ".png"
    if "." in url.split("?")[0].split("/")[-1]:
        cand = "." + url.split("?")[0].rsplit(".", 1)[-1]
        if 2 <= len(cand) <= 5:
            ext = cand
    out = OUTPUT_DIR / f"grok_imagine_{stamp}_{index}{ext}"
    out.write_bytes(data)
    return {"url": url, "path": str(out), "bytes": len(data)}


def cmd_status(args) -> int:
    ensure_dirs()
    browser_env()
    sync_playwright = _ensure_playwright()
    with sync_playwright() as pw:
        ctx, page = _launch(pw, headless=True)
        try:
            page.goto(IMAGINE_URL, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(2500)
            logged_in = _is_logged_in(page)
            title = page.title()
            url = page.url
        finally:
            ctx.close()
    return emit(
        {
            "schema": "engel_grok_imagine_status_v1",
            "ok": True,
            "installed": True,
            "logged_in": bool(logged_in),
            "title": title,
            "page_url": url,
            "status": "signed in to Grok Imagine"
            if logged_in
            else "Grok Imagine reachable; sign-in required (run login)",
        }
    )


def _check_logged_in_headless() -> bool:
    """Quick hidden probe of Grok sign-in state (used before auto-escalation)."""
    browser_env()
    sync_playwright = _ensure_playwright()
    with sync_playwright() as pw:
        ctx, page = _launch(pw, headless=True)
        try:
            page.goto(IMAGINE_URL, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(2000)
            return _is_logged_in(page)
        except Exception:
            return False
        finally:
            try:
                ctx.close()
            except Exception:
                pass


def _visible_grok_login(timeout: int) -> dict:
    """Visible keep-open sign-in to Grok Imagine. Never auto-closes in the first
    20s, ignores OAuth provider pages, and only concludes "signed in" when back
    on grok.com with a stable logged-in state. If navigation fails, the window
    is held open long enough to read the error. Returns a result dict."""
    browser_env()
    sync_playwright = _ensure_playwright()
    deadline = time.time() + max(120, timeout)
    min_open_until = time.time() + 20
    target_host = "grok.com"
    stable = 0
    logged_in = False
    err = ""
    with sync_playwright() as pw:
        ctx, page = _launch(pw, headless=False)
        try:
            try:
                page.goto(IMAGINE_URL, wait_until="domcontentloaded", timeout=45000)
            except Exception as exc:
                err = str(exc)
                while time.time() < min_open_until:
                    try:
                        page.wait_for_timeout(1000)
                    except Exception:
                        break
            while not err and time.time() < deadline:
                try:
                    page.wait_for_timeout(2000)
                    cur = (page.url or "").lower()
                    signed = (target_host in cur) and _is_logged_in(page)
                except Exception:
                    break  # operator closed the window; persistent profile keeps any session
                stable = stable + 1 if signed else 0
                if stable >= 3 and time.time() > min_open_until:
                    logged_in = True
                    break
            try:
                page.wait_for_timeout(2000)
            except Exception:
                pass
        finally:
            try:
                ctx.close()
            except Exception:
                pass
    result = {
        "schema": "engel_grok_imagine_login_v1",
        "ok": bool(logged_in),
        "logged_in": bool(logged_in),
        "status": (
            "signed in; session saved to Engel grok profile" if logged_in
            else (f"sign-in window could not open Grok: {err}" if err
                  else "login window closed before sign-in completed")
        ),
    }
    if err:
        result["error"] = err
    return result


def cmd_login(args) -> int:
    ensure_dirs()
    return emit(_visible_grok_login(args.timeout), ok_exit=True)


def cmd_imagine(args) -> int:
    prompt = (args.prompt or "").strip()
    if not prompt:
        return emit({"ok": False, "status": "empty prompt"})
    ensure_dirs()
    browser_env()
    sync_playwright = _ensure_playwright()
    headless = not bool(getattr(args, "visible", False))
    result: dict[str, Any] = {
        "schema": "engel_grok_imagine_result_v1",
        "ok": False,
        "prompt": prompt,
        "media_type": args.type,
        "headless": headless,
        "downloads": [],
    }
    # Hidden-after-first-sign-in: if we are not signed in and the caller allows
    # it, open a visible keep-open sign-in window first, then generate hidden.
    if getattr(args, "signin_if_needed", False) and not _check_logged_in_headless():
        login = _visible_grok_login(max(args.timeout, 180))
        result["signin_attempted"] = True
        result["signed_in_during_imagine"] = bool(login.get("ok"))
        if not login.get("ok"):
            result["needs_login"] = True
            result["status"] = "not signed in to Grok; sign-in window closed before completion"
            return emit(result)
    with sync_playwright() as pw:
        ctx, page = _launch(pw, headless=headless)
        try:
            page.goto(IMAGINE_URL, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(2500)
            if not _is_logged_in(page):
                result["status"] = "not signed in to Grok; run login first (or pass --signin-if-needed)"
                result["needs_login"] = True
                return emit(result)

            result["media_type_selected"] = _select_media_type(page, args.type)
            box = _find_prompt(page)
            if box is None:
                result["status"] = "could not find the Grok Imagine prompt box"
                return emit(result)

            before = _existing_media(page)
            box.click(timeout=5000)
            box.fill("")
            box.type(prompt, delay=12)
            # Submit: Enter first, fall back to a nearby submit button.
            submitted = False
            try:
                box.press("Enter")
                submitted = True
            except Exception:
                for getter in (
                    lambda: page.get_by_role("button", name="Submit"),
                    lambda: page.locator('button[type="submit"]'),
                    lambda: page.locator('button:has(svg)').last,
                ):
                    try:
                        getter().first.click(timeout=3000)
                        submitted = True
                        break
                    except Exception:
                        continue
            result["submitted"] = submitted

            # Wait for new generated media to appear and settle.
            deadline = time.time() + max(30, args.timeout)
            found: list[str] = []
            while time.time() < deadline:
                page.wait_for_timeout(2000)
                now = _existing_media(page)
                fresh = [u for u in (now - before) if _looks_generated(u)]
                if fresh:
                    # let it finish rendering / additional frames
                    page.wait_for_timeout(3000)
                    now2 = _existing_media(page)
                    found = [u for u in (now2 - before) if _looks_generated(u)]
                    break

            shot = OUTPUT_DIR / (
                "grok_imagine_"
                + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
                + "_page.png"
            )
            try:
                page.screenshot(path=str(shot), full_page=True)
                result["screenshot"] = str(shot)
            except Exception:
                pass

            downloads = []
            for i, url in enumerate(found[:8]):
                d = _download(page, ctx, url, i, args.type)
                if d:
                    downloads.append(d)
            result["downloads"] = downloads
            result["media_urls_found"] = found
            result["ok"] = bool(downloads) or bool(result.get("screenshot"))
            result["status"] = (
                f"generated {len(downloads)} file(s)"
                if downloads
                else "submitted; no downloadable media detected (see screenshot)"
            )
        except Exception as exc:
            result["status"] = f"grok imagine error: {exc}"
            result["error"] = str(exc)
        finally:
            ctx.close()
    return emit(result)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Engel Grok Imagine browser worker")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    lg = sub.add_parser("login")
    lg.add_argument("--timeout", type=int, default=300)
    im = sub.add_parser("imagine")
    im.add_argument("prompt", nargs="?", default="")
    im.add_argument("--prompt", dest="prompt_opt", default="")
    im.add_argument("--type", choices=["image", "video"], default="image")
    im.add_argument("--aspect", default="2:3")
    im.add_argument("--mode", choices=["speed", "quality"], default="speed")
    im.add_argument("--visible", action="store_true")
    im.add_argument("--signin-if-needed", dest="signin_if_needed", action="store_true",
                    help="if not signed in, open a visible keep-open sign-in window first, then generate hidden")
    im.add_argument("--timeout", type=int, default=240)
    return p


def main() -> int:
    args = build_parser().parse_args()
    if getattr(args, "prompt_opt", ""):
        args.prompt = args.prompt_opt
    if args.command == "status":
        return cmd_status(args)
    if args.command == "login":
        return cmd_login(args)
    if args.command == "imagine":
        return cmd_imagine(args)
    return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover
        print(json.dumps({"ok": False, "status": "worker crashed", "error": str(exc)}, indent=2))
        raise SystemExit(1)
