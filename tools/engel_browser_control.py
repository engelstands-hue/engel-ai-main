#!/usr/bin/env python3
"""General full browser control for Engel AI Main (Playwright).

When the operator asks Engel (in chat) to use the internet, Engel drives a real
Chromium with this engine: navigate, read/extract a page, screenshot, and detect
sign-in walls. Runs HEADLESS by default; opens visible only for a one-time
sign-in (then the per-domain persistent profile keeps the session for headless
runs). Engel-owned state stays on D: (never C:). Credentials are never read or
printed here.

Subcommands:
  open   <url> [--task T] [--visible|--interactive|--headless] [--hold-seconds S]
  login  <url> [--timeout S]      (always visible)
  search <query...> [--visible|--interactive|--headless] [--hold-seconds S]

Headless operation remains the default for a plain ``open URL`` call.
``--visible``/``--interactive`` are explicit operator modes: they open a real,
headed Chromium window and keep it available until the operator closes it or a
bounded hold expires.  Legacy Engel AI Main invocations (``search`` without a
visibility flag, or ``open`` with a non-empty ``--task``) also open a headed
window, but hold it only when a login/human check is detected.  Use
``--headless`` to force a direct call back to headless mode.  This module never
attempts to solve CAPTCHA or other human checks.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, quote_plus

ROOT = Path(__file__).resolve().parents[1]
PROFILE_ROOT = ROOT / "browser_profile" / "sites"
OUTPUT_DIR = ROOT / "runtime" / "browser_control" / "outputs"
BROWSER_CACHE_DIR = ROOT / "runtime" / "ms-playwright"
TEMP_DIR = ROOT / "runtime" / "temp"
LOGIN_MARKERS = [
    "sign in",
    "log in",
    "sign up",
    "create account",
    "continue with google",
    "log in to continue",
    "sign in to continue",
]

# These phrases are deliberately limited to human-verification interstitials
# and challenge widgets.  We report them to the caller, but never click,
# submit, or otherwise attempt to bypass the challenge.
HUMAN_CHALLENGE_MARKERS = (
    "captcha",
    "recaptcha",
    "hcaptcha",
    "turnstile",
    "verify you are human",
    "verify you're human",
    "confirm this search was made by a human",
    "are you a robot",
    "are you human",
    "i'm not a robot",
    "im not a robot",
    "select all squares",
    "select all images",
    "human verification",
    "security check",
    "checking your browser",
    "browser challenge",
    "bot check",
    "bot-check",
    "images not loading?",
)
HUMAN_CHALLENGE_URL_MARKERS = (
    "/captcha",
    "captcha.",
    "/challenge",
    "challenge.",
    "challenge-platform",
    "cf-chl-",
    "turnstile",
    "recaptcha",
    "hcaptcha",
    "/verify",
)

# Explicit operator windows must always have a finite upper bound.  The
# default is long enough for a human to complete a sign-in or challenge while
# still allowing the caller to choose a shorter hold for smoke tests.
DEFAULT_INTERACTIVE_HOLD_SECONDS = 120
MAX_VISIBLE_HOLD_SECONDS = 900


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_c(p: Path) -> bool:
    return str(p.drive).lower() == "c:"


def normalize_url(u: str) -> str:
    u = (u or "").strip()
    if not re.match(r"^https?://", u, re.I):
        u = "https://" + u
    return u


def domain_key(u: str) -> str:
    try:
        host = urlparse(u).netloc.lower()
    except Exception:
        host = "site"
    host = re.sub(r"[^a-z0-9.]+", "_", host) or "site"
    return host


def ensure() -> None:
    for p in (PROFILE_ROOT, OUTPUT_DIR, BROWSER_CACHE_DIR, TEMP_DIR):
        if is_c(p):
            raise RuntimeError(f"refusing C: path for Engel browser control: {p}")
        p.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(BROWSER_CACHE_DIR))
    os.environ["ENGEL_APP_ROOT"] = str(ROOT)
    for k in ("TEMP", "TMP", "TMPDIR"):
        os.environ[k] = str(TEMP_DIR)


def _persist_receipt(d: dict) -> None:
    """Leave a durable receipt in Engel's memory/reports (never break stdout)."""
    try:
        from engel_receipts import write_action_receipt
    except Exception:
        return
    schema = str(d.get("schema") or "")
    if "login" in schema:
        action = "login"
    elif str(d.get("task") or "").lower().startswith("web search"):
        action = "search"
    else:
        action = "open"
    arts = [a for a in [d.get("screenshot")] if a]
    write_action_receipt(
        "browser_control", action, bool(d.get("ok")),
        str(d.get("status") or ""), payload=d,
        summary=str(d.get("status") or ""), artifacts=arts,
    )


def emit(d: dict) -> int:
    d.setdefault("updated_at_utc", iso_now())
    d.setdefault("output_dir", str(OUTPUT_DIR))
    _persist_receipt(d)
    print(json.dumps(d, indent=2))
    return 0 if d.get("ok") else 1


def _launch(pw, url: str, headless: bool):
    prof = PROFILE_ROOT / domain_key(url)
    prof.mkdir(parents=True, exist_ok=True)
    launch_args = ["--disable-blink-features=AutomationControlled"]
    if not headless:
        # Headed/operator mode must be on-screen and easy to find.  The
        # persistent worker used by ChatGPT has its own hidden/off-screen
        # policy; this general browser control path never inherits that mode.
        launch_args.append("--start-maximized")
    ctx = pw.chromium.launch_persistent_context(
        user_data_dir=str(prof),
        headless=headless,
        args=launch_args,
        viewport=None if not headless else {"width": 1366, "height": 900},
        accept_downloads=True,
    )
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    return ctx, page


def _login_required(page) -> bool:
    try:
        body = (page.inner_text("body") or "")[:6000].lower()
    except Exception:
        body = ""
    if any(m in body for m in LOGIN_MARKERS) and len(body) < 1500:
        return True
    u = (page.url or "").lower()
    if any(t in u for t in ("/login", "/signin", "/sign-in", "/auth", "accounts.google.com", "oauth")):
        return True
    return False


def _human_challenge_reason(page) -> str:
    """Return a stable, non-sensitive reason when a page needs a human check.

    The browser is intentionally observed only.  No challenge controls are
    clicked and no attempt is made to defeat CAPTCHA/bot protections.
    """
    try:
        body = (page.inner_text("body") or "")[:12000].lower()
    except Exception:
        body = ""
    # Collapse whitespace so phrases split across line breaks still match.
    body = re.sub(r"\s+", " ", body)
    for marker in HUMAN_CHALLENGE_MARKERS:
        if marker in body:
            if "captcha" in marker or marker in {"recaptcha", "hcaptcha", "turnstile"}:
                return "captcha"
            if "security" in marker or "checking your browser" in marker:
                return "security check"
            return "human verification"
    try:
        current_url = (page.url or "").lower()
    except Exception:
        current_url = ""
    if any(marker in current_url for marker in HUMAN_CHALLENGE_URL_MARKERS):
        return "human verification"
    return ""


def _human_challenge_required(page) -> bool:
    """Whether the current page appears to require operator verification."""
    return bool(_human_challenge_reason(page))


def _bounded_seconds(value, default: int, *, minimum: int = 1) -> int:
    """Normalize a user-provided hold/timeout without allowing an unbounded wait."""
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        seconds = int(default)
    if seconds <= 0:
        seconds = int(default)
    return max(minimum, min(seconds, MAX_VISIBLE_HOLD_SECONDS))


def _legacy_main_operator_mode(args) -> bool:
    """Recognize the pre-operator CLI shape emitted by older Engel Main builds.

    Older release binaries did not yet append ``--visible --interactive`` to
    browser commands.  Their search command has no task/visibility flags, and
    their URL command carries the chat request in ``--task``.  Keep those
    calls usable while leaving a plain direct ``open URL`` headless.  An
    explicit ``--headless`` always wins.
    """
    if bool(getattr(args, "headless", False)):
        return False
    if bool(getattr(args, "visible", False)) or bool(getattr(args, "interactive", False)):
        return False
    try:
        if int(getattr(args, "hold_seconds", 0) or 0) > 0:
            return False
    except (TypeError, ValueError):
        pass
    command = str(
        getattr(args, "command", "") or getattr(args, "_engel_command", "") or ""
    ).lower()
    if command == "search":
        return True
    return command == "open" and bool(str(getattr(args, "task", "") or "").strip())


def _extract(page) -> str:
    try:
        txt = page.evaluate("() => document.body ? document.body.innerText : ''") or ""
    except Exception:
        txt = ""
    txt = re.sub(r"\n{3,}", "\n\n", txt).strip()
    return txt[:6000]


# OAuth / provider sign-in hosts where we must NOT conclude "signed in" yet.
AUTH_HOSTS = (
    "accounts.google.com",
    "appleid.apple.com",
    "login.microsoftonline.com",
    "github.com/login",
    "auth.",
    "oauth",
    "/login",
    "/signin",
    "/sign-in",
)
# Hold a VISIBLE window open at least this long so a one-time sign-in (or an
# error) is always readable before the window can close.
MIN_VISIBLE_SECONDS = 20


def _capture_page(out: dict, page, requested_url: str) -> None:
    """Capture the current page state into an output receipt.

    This helper is deliberately tolerant of a page that was closed by the
    operator while an interactive hold was running.
    """
    out["login_required"] = _login_required(page)
    out["human_check_required"] = _human_challenge_required(page)
    out["human_intervention_required"] = bool(out["human_check_required"])
    out["human_check_reason"] = _human_challenge_reason(page)
    out["operator_action_required"] = bool(
        out["login_required"] or out["human_check_required"]
    )
    try:
        out["title"] = page.title()
    except Exception:
        out["title"] = ""
    try:
        out["url"] = page.url
    except Exception:
        out["url"] = requested_url
    out["text"] = _extract(page)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    shot = OUTPUT_DIR / f"browse_{domain_key(requested_url)}_{stamp}.png"
    try:
        page.screenshot(path=str(shot), full_page=False)
        out["screenshot"] = str(shot)
    except Exception:
        out["screenshot"] = out.get("screenshot", "")


def _hold_visible_context(ctx, page, hold_seconds: int) -> dict:
    """Keep a headed context available for bounded operator intervention.

    The loop does not interact with the page.  It only observes whether a
    login/human-check wall remains and exits when the operator closes the
    window or the finite hold expires.
    """
    requested = _bounded_seconds(hold_seconds, DEFAULT_INTERACTIVE_HOLD_SECONDS)
    started = time.monotonic()
    deadline = started + requested
    operator_closed = False
    timed_out = False
    saw_human_check = False
    saw_login = False
    # Capture the state before the first wait.  If the operator closes the
    # window immediately, the receipt should still say that the check was
    # present rather than implying it had already been cleared.
    try:
        current_human_check = _human_challenge_required(page)
    except Exception:
        current_human_check = False
    try:
        current_login = _login_required(page)
    except Exception:
        current_login = False
    saw_human_check = current_human_check
    saw_login = current_login

    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        try:
            is_closed = getattr(page, "is_closed", None)
            if callable(is_closed) and is_closed():
                operator_closed = True
                break
            # Playwright raises when the operator closes the context/window.
            page.wait_for_timeout(max(100, min(1000, int(remaining * 1000))))
            current_human_check = _human_challenge_required(page)
            current_login = _login_required(page)
            saw_human_check = saw_human_check or current_human_check
            saw_login = saw_login or current_login
        except Exception:
            operator_closed = True
            break

    if not operator_closed and time.monotonic() >= deadline:
        timed_out = True
    elapsed = max(0.0, time.monotonic() - started)

    if operator_closed:
        if current_human_check or current_login:
            status = "operator closed browser before the human check was completed"
        elif saw_human_check or saw_login:
            status = "human check completed; operator closed browser window"
        else:
            status = "operator closed browser window"
    elif current_human_check or current_login:
        status = "human check still required when the browser hold expired"
    elif saw_human_check or saw_login:
        status = "human check completed; browser hold expired"
    else:
        status = "interactive browser hold expired"

    return {
        "hold_seconds_requested": requested,
        "hold_seconds_elapsed": round(elapsed, 1),
        "operator_closed": bool(operator_closed),
        "hold_timed_out": bool(timed_out),
        "human_check_required": bool(current_human_check),
        "human_intervention_required": bool(current_human_check),
        "login_required": bool(current_login),
        "operator_action_required": bool(current_human_check or current_login),
        "intervention_status": status,
    }


def _read_into(
    out: dict,
    url: str,
    headless: bool,
    hold_seconds: int = 0,
    interactive: bool = False,
    hold_on_challenge: bool = False,
) -> None:
    """Open ``url`` and read title/text/screenshot/login/challenge state.

    ``headless=True`` remains the default for existing callers.  A headed
    context is held when the caller explicitly requests ``interactive`` (or a
    positive ``hold_seconds``), and can optionally be held only when a
    challenge/login wall is detected via ``hold_on_challenge``.
    """
    from playwright.sync_api import sync_playwright

    visible = not headless
    explicit_hold = bool(interactive or hold_seconds > 0)
    out.setdefault("visible", visible)
    out["visible"] = bool(visible)
    out["interactive"] = bool(explicit_hold)
    out.setdefault("operator_action_required", False)
    out.setdefault("operator_closed", False)
    out.setdefault("human_check_required", False)
    out.setdefault("human_intervention_required", False)
    out.setdefault("human_check_reason", "")
    out.setdefault("visible_window_opened", False)
    if explicit_hold:
        out["hold_seconds_requested"] = _bounded_seconds(
            hold_seconds, DEFAULT_INTERACTIVE_HOLD_SECONDS
        )

    with sync_playwright() as pw:
        try:
            ctx, page = _launch(pw, url, headless=headless)
        except Exception as exc:
            # Keep failures machine-readable for the UI instead of allowing a
            # headed-launch error to escape as a generic "browser crashed"
            # response with none of the operator-state fields.
            out["ok"] = False
            out["visible_window_opened"] = False
            out["status"] = f"browser launch error: {exc}"
            out["error"] = str(exc)
            return
        # Preserve evidence that an earlier intervention window was opened
        # when this helper is used for the post-intervention hidden retry.
        out["visible_window_opened"] = bool(out.get("visible_window_opened") or visible)
        navigation_error = ""
        try:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(2500)
            except Exception as exc:
                navigation_error = str(exc)
                out["ok"] = False
                out["status"] = f"browser open error: {exc}"
                out["error"] = str(exc)

            # A partially loaded challenge page is still useful to the
            # operator, so capture it even when navigation reported a timeout.
            try:
                _capture_page(out, page, url)
            except Exception:
                pass
            if not navigation_error:
                out["ok"] = True
                out.pop("error", None)

            # Legacy Main mode opens a headed page immediately, but only
            # enters the longer operator hold when the page actually needs a
            # human action.  Explicit --interactive always holds.
            challenge_hold = bool(
                hold_on_challenge
                and (
                    out.get("login_required")
                    or out.get("human_check_required")
                )
            )
            should_hold = bool(visible and (explicit_hold or challenge_hold))
            if should_hold:
                if not explicit_hold:
                    out["hold_seconds_requested"] = _bounded_seconds(
                        0, DEFAULT_INTERACTIVE_HOLD_SECONDS
                    )
                out["interactive"] = True
                hold = _hold_visible_context(
                    ctx, page, out["hold_seconds_requested"]
                )
                out.update(hold)
                # Refresh the receipt after a human interaction when the page
                # is still open.  If it was closed, retain the last observed
                # challenge state from the hold result.
                if not hold.get("operator_closed"):
                    try:
                        _capture_page(out, page, url)
                    except Exception:
                        pass
                out["visible"] = True
                out["interactive"] = True
                out["visible_window_opened"] = True
        except Exception as exc:
            out["ok"] = False
            out["status"] = f"browser open error: {exc}"
            out["error"] = str(exc)
        finally:
            try:
                ctx.close()
            except Exception:
                pass


def _visible_login(url: str, timeout: int) -> dict:
    """Open a VISIBLE keep-open window so the operator can sign in once.

    Stability rules (so the window never vanishes too soon): never auto-close in
    the first MIN_VISIBLE_SECONDS; ignore OAuth/provider pages; only conclude
    "signed in" when back on the target host with a stable signed-in state. If
    navigation fails, the window is held open long enough to read the error.
    Returns a result dict; does not emit."""
    from playwright.sync_api import sync_playwright

    target_host = (urlparse(url).netloc or "").lower()
    login_timeout = _bounded_seconds(max(120, timeout), 120)
    deadline = time.monotonic() + login_timeout
    min_open_until = time.monotonic() + MIN_VISIBLE_SECONDS
    stable = 0
    ok = False
    err = ""
    operator_closed = False
    human_check_required = False
    login_required = True
    with sync_playwright() as pw:
        ctx, page = _launch(pw, url, headless=False)
        try:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
            except Exception as exc:
                err = str(exc)
                # Hold the window open so the operator can read the failed page.
                while time.monotonic() < min_open_until:
                    try:
                        page.wait_for_timeout(1000)
                    except Exception:
                        operator_closed = True
                        break
            while not err and time.monotonic() < deadline:
                try:
                    page.wait_for_timeout(2000)
                    cur = (page.url or "").lower()
                    on_auth = any(a in cur for a in AUTH_HOSTS)
                    on_target = bool(target_host) and target_host in cur
                    login_required = _login_required(page)
                    human_check_required = _human_challenge_required(page)
                    signed = on_target and not on_auth and not login_required and not human_check_required
                except Exception:
                    operator_closed = True
                    break  # operator closed the window; persistent profile keeps the session
                stable = stable + 1 if signed else 0
                if stable >= 3 and time.monotonic() > min_open_until:
                    ok = True
                    break
            try:
                page.wait_for_timeout(2000)
            except Exception:
                operator_closed = True
            try:
                login_required = _login_required(page)
                human_check_required = _human_challenge_required(page)
            except Exception:
                pass
        finally:
            try:
                ctx.close()
            except Exception:
                pass
    result = {
        "schema": "engel_browser_login_v1",
        "ok": bool(ok),
        "url": url,
        "logged_in": bool(ok),
        "visible": True,
        "interactive": True,
        "visible_window_opened": True,
        "operator_closed": bool(operator_closed),
        "human_check_required": bool(human_check_required),
        "human_intervention_required": bool(human_check_required),
        "login_required": bool(login_required),
        "operator_action_required": bool(human_check_required or login_required or not ok),
        "intervention_status": (
            "operator closed browser before sign-in completed" if operator_closed and not ok
            else "human check still required" if human_check_required
            else "signed in; session saved to the Engel site profile" if ok
            else "login window timed out"
        ),
        "status": (
            "signed in; session saved to the Engel site profile" if ok
            else (f"sign-in window could not open the page: {err}" if err
                  else "login window closed before sign-in completed")
        ),
    }
    if err:
        result["error"] = err
    return result


def _visible_challenge(url: str, timeout: int, reason: str = "human verification") -> dict:
    """Open a headed page for an operator-only human verification step.

    The page is held for a finite period and is never clicked or submitted by
    this module.  The caller can inspect ``human_check_required`` after the
    hold to decide whether it is safe to retry a hidden read.
    """
    hold_seconds = _bounded_seconds(max(1, timeout), DEFAULT_INTERACTIVE_HOLD_SECONDS)
    out: dict = {
        "schema": "engel_browser_intervention_v1",
        "ok": False,
        "requested_url": url,
        "url": url,
        "task": "human verification",
        "visible": True,
        "interactive": True,
        "visible_window_opened": False,
        "operator_action_required": True,
        "operator_closed": False,
        "human_check_required": True,
        "human_intervention_required": True,
        "human_check_reason": reason or "human verification",
        "hold_seconds_requested": hold_seconds,
    }
    _read_into(
        out,
        url,
        headless=False,
        hold_seconds=hold_seconds,
        interactive=True,
    )
    # Keep the stable intervention schema while retaining title/text/screenshot
    # and the final challenge state captured by _read_into.
    out["schema"] = "engel_browser_intervention_v1"
    out["intervention_reason"] = reason or out.get("human_check_reason") or "human verification"
    if out.get("operator_closed"):
        out["intervention_status"] = out.get(
            "intervention_status", "operator closed browser window"
        )
    elif out.get("human_check_required"):
        out["intervention_status"] = out.get(
            "intervention_status", "human check still required when the browser hold expired"
        )
    else:
        out["intervention_status"] = out.get(
            "intervention_status", "human check completed; browser hold expired"
        )
    out["status"] = out["intervention_status"]
    return out


def cmd_open(args) -> int:
    ensure()
    url = normalize_url(args.url)
    requested_hold = getattr(args, "hold_seconds", 0) or 0
    forced_headless = bool(getattr(args, "headless", False))
    # ``--visible`` is an operator-facing request too.  Treat it like
    # ``--interactive`` so a caller that only knows the older flag never gets
    # a headed window that flashes and disappears before it can be directed.
    explicit_interactive = bool(
        getattr(args, "visible", False)
        or getattr(args, "interactive", False)
        or requested_hold > 0
    )
    compatibility_mode = bool(
        not forced_headless and _legacy_main_operator_mode(args)
    )
    # Explicit operator flags take precedence over the legacy compatibility
    # path.  Compatibility mode is headed immediately, then holds only if the
    # first page snapshot shows a login/human-check wall.
    interactive = bool(explicit_interactive)
    visible = bool(
        not forced_headless
        and (getattr(args, "visible", False) or explicit_interactive or compatibility_mode)
    )
    hold_seconds = (
        _bounded_seconds(requested_hold, DEFAULT_INTERACTIVE_HOLD_SECONDS)
        if explicit_interactive
        else 0
    )
    out: dict = {
        "schema": "engel_browser_open_v1",
        "ok": False,
        "requested_url": url,
        "task": getattr(args, "task", ""),
        "visible": visible,
        "interactive": interactive,
        "visible_window_opened": False,
        "compatibility_mode": compatibility_mode,
        "operator_action_required": False,
        "operator_closed": False,
        "human_check_required": False,
        "human_intervention_required": False,
        "human_check_reason": "",
    }

    _read_into(
        out,
        url,
        headless=not visible,
        hold_seconds=hold_seconds,
        interactive=interactive,
        hold_on_challenge=compatibility_mode,
    )

    # Hidden-after-first-sign-in/check: if a HEADLESS browse hit a wall and the
    # caller allows it, escalate to a visible operator window, then retry hidden
    # only after the operator has cleared the wall.
    signin_if_needed = bool(getattr(args, "signin_if_needed", False))
    if (out.get("ok")
            and (out.get("login_required") or out.get("human_check_required"))
            and signin_if_needed
            and not visible):
        if out.get("human_check_required"):
            intervention = _visible_challenge(
                url,
                max(getattr(args, "timeout", 60), 180),
                out.get("human_check_reason") or "human verification",
            )
            out["intervention_attempted"] = True
            out["intervention_status"] = intervention.get("intervention_status")
            out["intervention_reason"] = intervention.get("intervention_reason")
            out["operator_closed"] = bool(intervention.get("operator_closed"))
            out["visible_window_opened"] = bool(
                out.get("visible_window_opened") or intervention.get("visible_window_opened")
            )
            out["visible"] = bool(
                intervention.get("human_check_required")
                or intervention.get("operator_action_required")
            )
            out["interactive"] = out["visible"]
            out["human_check_required"] = bool(intervention.get("human_check_required", True))
            out["human_intervention_required"] = out["human_check_required"]
            out["operator_action_required"] = bool(
                intervention.get("operator_action_required", out["human_check_required"])
            )
            out["human_check_resolved"] = not out["human_check_required"]
            if out["human_check_resolved"]:
                _read_into(out, url, headless=True)
                out["visible"] = False
                out["interactive"] = False
                out["human_check_resolved"] = not out.get("human_check_required", True)
        else:
            login = _visible_login(url, max(getattr(args, "timeout", 60), 180))
            out["signin_attempted"] = True
            out["signed_in_during_open"] = bool(login.get("ok"))
            out["signin_status"] = login.get("status")
            out["intervention_status"] = login.get("intervention_status")
            out["operator_closed"] = bool(login.get("operator_closed"))
            out["visible_window_opened"] = bool(
                out.get("visible_window_opened") or login.get("visible_window_opened")
            )
            out["visible"] = bool(
                login.get("human_check_required")
                or login.get("operator_action_required")
            )
            out["interactive"] = out["visible"]
            out["human_check_required"] = bool(login.get("human_check_required"))
            out["human_intervention_required"] = out["human_check_required"]
            out["operator_action_required"] = bool(
                login.get("operator_action_required", login.get("login_required", True))
            )
            if login.get("ok"):
                _read_into(out, url, headless=True)  # re-read after sign-in
                out["visible"] = False
                out["interactive"] = False
                out["human_check_resolved"] = not out.get("human_check_required", True)

    if not out.get("status"):
        title = (out.get("title") or "").strip()
        if out.get("human_check_required"):
            detail = (out.get("intervention_status") or "").strip()
            out["status"] = (
                (detail or f"{title} needs a human verification check").strip()
                + " (use --interactive or --signin-if-needed to open a visible browser)"
            )
        elif not out.get("login_required"):
            out["status"] = f"opened {title}".strip()
        elif out.get("signed_in_during_open"):
            out["status"] = f"signed in and opened {title}".strip()
        else:
            out["status"] = (
                f"{title} needs a one-time sign-in".strip()
                + " (re-run with --signin-if-needed, or use 'login')"
            )
    return emit(out)


def cmd_login(args) -> int:
    ensure()
    return emit(_visible_login(normalize_url(args.url), args.timeout))


def cmd_search(args) -> int:
    query = " ".join(args.query).strip()
    args.url = f"https://duckduckgo.com/html/?q={quote_plus(query)}"
    args.task = f"web search: {query}"
    # Keep the command identity available when cmd_search is called directly
    # with a lightweight Namespace rather than argparse's full result.
    setattr(args, "_engel_command", "search")
    # Preserve explicit --visible/--interactive/--hold-seconds choices.  The
    # previous implementation unconditionally forced search back to headless,
    # which made a DuckDuckGo human check impossible for the operator to clear.
    return cmd_open(args)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Engel general browser control")
    sub = p.add_subparsers(dest="command", required=True)
    op = sub.add_parser("open")
    op.add_argument("url")
    op.add_argument("--task", default="")
    op.add_argument("--visible", action="store_true")
    op.add_argument("--interactive", action="store_true",
                    help="open a visible browser and hold it for operator action")
    op.add_argument("--headless", action="store_true",
                    help="force headless mode (overrides legacy Main compatibility mode)")
    op.add_argument("--hold-seconds", type=int, default=0, metavar="S",
                    help=f"bound the visible operator hold (default {DEFAULT_INTERACTIVE_HOLD_SECONDS}s; max {MAX_VISIBLE_HOLD_SECONDS}s)")
    op.add_argument("--signin-if-needed", dest="signin_if_needed", action="store_true",
                    help="if a hidden browse hits a login/check wall, open a visible operator window then retry")
    op.add_argument("--timeout", type=int, default=60)
    lg = sub.add_parser("login")
    lg.add_argument("url")
    lg.add_argument("--timeout", type=int, default=300)
    se = sub.add_parser("search")
    se.add_argument("query", nargs="+")
    se.add_argument("--task", default="")
    se.add_argument("--visible", action="store_true")
    se.add_argument("--interactive", action="store_true",
                    help="open a visible browser and hold it for operator action")
    se.add_argument("--headless", action="store_true",
                    help="force headless mode instead of the legacy Main compatibility mode")
    se.add_argument("--hold-seconds", type=int, default=0, metavar="S",
                    help=f"bound the visible operator hold (default {DEFAULT_INTERACTIVE_HOLD_SECONDS}s; max {MAX_VISIBLE_HOLD_SECONDS}s)")
    se.add_argument("--signin-if-needed", dest="signin_if_needed", action="store_true",
                    help="if a hidden search hits a login/check wall, open a visible operator window then retry")
    se.add_argument("--timeout", type=int, default=60)
    return p


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "open":
        return cmd_open(args)
    if args.command == "login":
        return cmd_login(args)
    if args.command == "search":
        return cmd_search(args)
    return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover
        print(json.dumps({"ok": False, "status": "browser control crashed", "error": str(exc)}, indent=2))
        raise SystemExit(1)
