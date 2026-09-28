from __future__ import annotations

import os
import queue
import threading
import time
from pathlib import Path

_LOCK = threading.Lock()
_SESSION: dict = {
    "provider": None,
    "ready": False,
    "context": None,
    "page": None,
    "playwright": None,
    "error": "",
}

ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
PROFILE_DIR = ROOT / "browser_profile"

# Playwright's sync API is thread-affinity bound — anything that touches the
# browser/page/context MUST run on the same thread that called start(). The
# Engel companion's `run_threaded` spawns a fresh thread per call, so we route
# all browser-AI work through a single dedicated owner thread.
_OWNER_QUEUE: "queue.Queue[object]" = queue.Queue()
_OWNER_THREAD: "threading.Thread | None" = None
_OWNER_LOCK = threading.Lock()


def _owner_loop() -> None:
    while True:
        job = _OWNER_QUEUE.get()
        if job is None:
            return
        try:
            job()
        except Exception:
            pass


def _ensure_owner() -> None:
    global _OWNER_THREAD
    with _OWNER_LOCK:
        if _OWNER_THREAD is None or not _OWNER_THREAD.is_alive():
            _OWNER_THREAD = threading.Thread(
                target=_owner_loop, name="EngelBrowserAIOwner", daemon=True
            )
            _OWNER_THREAD.start()


def _on_owner(fn):
    """Run `fn()` on the dedicated Playwright owner thread, return its result.
    Blocks the calling thread until done."""
    _ensure_owner()
    done = threading.Event()
    box: dict = {}

    def wrapper():
        try:
            box["value"] = fn()
        except Exception as exc:
            box["error"] = exc
        finally:
            done.set()

    _OWNER_QUEUE.put(wrapper)
    done.wait()
    if "error" in box:
        raise box["error"]
    return box["value"]

# Per-provider config
# input_selectors: tried in order, first visible one wins
# type_method: "fill" for textarea/input, "type" for contenteditable
# send_method: "enter" or "button"
# send_button: CSS selector for send button (used when send_method="button")
# response_selectors: tried in order for extracting last response text
# streaming_done: selector that appears/changes when streaming ends
# streaming_timeout: seconds to wait for done

PROVIDERS: dict[str, dict] = {
    "claude": {
        "name": "Claude (Anthropic)",
        "url": "https://claude.ai/new",
        "input_selectors": [
            'div[contenteditable="true"].ProseMirror',
            '.ProseMirror',
            'div[contenteditable="true"]',
            'div[role="textbox"]',
        ],
        "type_method": "type",
        "send_method": "enter",
        "response_selectors": [
            '.font-claude-message .contents',
            '.font-claude-message',
            '[data-is-streaming] .contents',
            '[data-is-streaming]',
        ],
        "streaming_done_selector": '[data-is-streaming="false"]',
        "streaming_timeout": 90,
    },
    "chatgpt": {
        "name": "ChatGPT (OpenAI)",
        "url": "https://chatgpt.com",
        "input_selectors": [
            '#prompt-textarea',
            'div#prompt-textarea[contenteditable="true"]',
            'div[contenteditable="true"]',
        ],
        "type_method": "type",
        "type_delay_ms": 1,
        "send_method": "button",
        "send_button": 'button[data-testid="send-button"], button[aria-label="Send prompt"]',
        "send_button_timeout_ms": 1200,
        "response_selectors": [
            '[data-message-author-role="assistant"] .markdown',
            '.agent-turn .markdown',
            '.markdown',
        ],
        "streaming_done_selector": 'button[data-testid="send-button"]:not([disabled]), button[aria-label="Send prompt"]:not([disabled])',
        "streaming_timeout": 20,
        "response_poll_timeout": 18,
        "response_idle_seconds": 1.1,
    },
    "google": {
        "name": "Gemini (Google)",
        "url": "https://gemini.google.com/app",
        "input_selectors": [
            'div.ql-editor[contenteditable="true"]',
            'rich-textarea .ql-editor',
            'div[contenteditable="true"]',
            'textarea',
        ],
        "type_method": "type",
        "send_method": "button",
        "send_button": 'button[aria-label="Send message"], mat-icon-button.send-button, button.send-button',
        "response_selectors": [
            'model-response .markdown',
            'model-response',
            '.model-response-text p',
            '.model-response-text',
            'message-content .markdown',
        ],
        "streaming_done_selector": 'button[aria-label="Send message"]:not([disabled])',
        "streaming_timeout": 60,
    },
    "gemini": {
        "name": "Gemini (Google)",
        "url": "https://gemini.google.com/app",
        "input_selectors": [
            'div.ql-editor[contenteditable="true"]',
            'rich-textarea .ql-editor',
            'div[contenteditable="true"]',
            'textarea',
        ],
        "type_method": "type",
        "send_method": "button",
        "send_button": 'button[aria-label="Send message"], mat-icon-button.send-button, button.send-button',
        "response_selectors": [
            'model-response .markdown',
            'model-response',
            '.model-response-text p',
            '.model-response-text',
            'message-content .markdown',
        ],
        "streaming_done_selector": 'button[aria-label="Send message"]:not([disabled])',
        "streaming_timeout": 60,
    },
    "duck": {
        "name": "DuckDuckGo AI Chat",
        "url": "https://duck.ai",
        "input_selectors": [
            'textarea[placeholder]',
            '#chat-input',
            'textarea',
        ],
        "type_method": "fill",
        "send_method": "enter",
        "response_selectors": [
            '[data-role="assistant"] .prose',
            '.duck-ai-message .prose',
            '.assistant-message',
            '.message-content',
            'article.prose',
        ],
        "streaming_done_selector": 'button[aria-label="Send"]:not([disabled]), button[type="submit"]:not([disabled])',
        "streaming_timeout": 60,
    },
    "copilot": {
        "name": "Copilot (Microsoft)",
        "url": "https://copilot.microsoft.com",
        "input_selectors": [
            'textarea#userInput',
            'textarea[placeholder]',
        ],
        "type_method": "fill",
        "send_method": "enter",
        "response_selectors": [
            '.ac-textBlock',
            '.cib-chat-turn-main',
        ],
        "streaming_done_selector": 'button[aria-label="Submit"]:not([disabled])',
        "streaming_timeout": 60,
    },
    "perplexity": {
        "name": "Perplexity AI",
        "url": "https://perplexity.ai",
        "input_selectors": [
            'textarea[placeholder]',
        ],
        "type_method": "fill",
        "send_method": "enter",
        "response_selectors": [
            '.prose',
            '.answer-content',
        ],
        "streaming_done_selector": 'button[aria-label="Submit"]:not([disabled])',
        "streaming_timeout": 60,
    },
}


def browser_ai_status() -> str:
    with _LOCK:
        ready = _SESSION["ready"]
        provider = _SESSION["provider"]
        error = _SESSION["error"]

    lines = ["# Browser AI Bridge Status", ""]
    if ready and provider:
        info = PROVIDERS.get(provider, {})
        lines += [
            "Status: CONNECTED",
            f"Provider: {info.get('name', provider)}",
            f"URL: {info.get('url', '')}",
            "",
            "Type any message in Engel chat and it goes to this AI.",
            "",
            "Commands:",
            "  browser ai disconnect",
            "  browser ai switch <provider>",
        ]
    else:
        if error:
            lines += [f"Last error: {error}", ""]
        seen = set()
        unique_providers = []
        for k, v in PROVIDERS.items():
            if v["name"] not in seen:
                seen.add(v["name"])
                unique_providers.append((k, v))

        lines += [
            "Status: DISCONNECTED",
            "",
            "Available providers:",
        ]
        for k, v in unique_providers:
            lines.append(f"  {k}: {v['name']} — {v['url']}")
        lines += [
            "",
            "Connect (type in Engel chat):",
            "  browser ai connect google     ← Google Gemini (needs Google login)",
            "  browser ai connect duck       ← DuckDuckGo AI (FREE, no login needed)",
            "  browser ai connect claude     ← Claude by Anthropic",
            "  browser ai connect chatgpt    ← ChatGPT by OpenAI",
            "  browser ai connect copilot    ← Copilot by Microsoft",
            "  browser ai connect perplexity ← Perplexity AI",
            "",
            "Tip: 'duck' is free and needs no account.",
        ]
    return "\n".join(lines)


def _ensure_playwright():
    try:
        from playwright.sync_api import sync_playwright
        return sync_playwright
    except ImportError:
        raise RuntimeError(
            "Playwright not installed. Run: pip install playwright && python -m playwright install chromium"
        )


def _browsers_installed() -> bool:
    """Check if Playwright browsers are installed."""
    try:
        from playwright.sync_api import sync_playwright
        pw = sync_playwright().start()
        try:
            # Try to get browser path — if it doesn't exist, browsers aren't installed
            pw.chromium.executable_path
            pw.stop()
            return True
        except Exception:
            pw.stop()
            return False
    except Exception:
        return False


def _close_session_unsafe():
    try:
        if _SESSION["context"]:
            _SESSION["context"].close()
    except Exception:
        pass
    try:
        if _SESSION["playwright"]:
            _SESSION["playwright"].stop()
    except Exception:
        pass
    _SESSION.update({
        "provider": None, "ready": False,
        "context": None, "page": None,
        "playwright": None, "error": "",
    })


def browser_ai_connect(provider: str) -> str:
    provider = provider.strip().lower()
    if provider not in PROVIDERS:
        avail = ", ".join(PROVIDERS.keys())
        return f"Unknown provider '{provider}'. Available: {avail}"

    # Check if Playwright browsers are installed
    if not _browsers_installed():
        return "\n".join([
            "# Browser AI Setup Required",
            "",
            "Playwright browsers not found. First-time setup needed.",
            "",
            "Run this command in a terminal (one time only):",
            "  python -m playwright install chromium",
            "",
            "Then try again: browser ai connect " + provider,
            "",
            "If that fails, try the full install:",
            "  python -m playwright install",
        ])

    info = PROVIDERS[provider]
    hidden_browser = os.environ.get("ENGEL_BROWSER_AI_HEADLESS", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    hide_mode = os.environ.get("ENGEL_BROWSER_AI_HIDE_MODE", "offscreen").strip().lower()
    true_headless = hidden_browser and hide_mode == "headless"

    def _do_connect():
        with _LOCK:
            if _SESSION["ready"]:
                _close_session_unsafe()
            try:
                sync_playwright = _ensure_playwright()
                pw = sync_playwright().start()
                PROFILE_DIR.mkdir(parents=True, exist_ok=True)
                launch_args = ["--no-sandbox", "--disable-blink-features=AutomationControlled"]
                if hidden_browser and not true_headless:
                    launch_args.extend(["--window-position=-32000,-32000", "--window-size=1366,900"])
                elif not hidden_browser:
                    launch_args.append("--start-maximized")
                ctx = pw.chromium.launch_persistent_context(
                    user_data_dir=str(PROFILE_DIR / provider),
                    headless=true_headless,
                    args=launch_args,
                    viewport={"width": 1366, "height": 900} if true_headless else None,
                    accept_downloads=True,
                )
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
                page.goto(info["url"], timeout=30000, wait_until="domcontentloaded")
                _SESSION.update({
                    "provider": provider,
                    "ready": True,
                    "playwright": pw,
                    "context": ctx,
                    "page": page,
                    "error": "",
                })
                return "\n".join([
                    f"# Browser AI Connected — {info['name']}",
                    "",
                    "A hidden browser session is running." if hidden_browser else "A browser window opened.",
                    "Log in if prompted (session is saved for next time).",
                    "",
                    "IMPORTANT: Type your messages here in Engel — not in the browser.",
                    "Engel will send them to the AI and show the response here.",
                    "",
                    "Example: just type 'hello' and press Enter.",
                ])
            except Exception as exc:
                _SESSION["error"] = str(exc)
                return f"Browser AI connect failed: {exc}"

    return _on_owner(_do_connect)


def browser_ai_disconnect() -> str:
    def _do_disconnect():
        with _LOCK:
            if not _SESSION["ready"]:
                return "Browser AI is not connected."
            provider = _SESSION["provider"]
            _close_session_unsafe()
        return f"Browser AI disconnected (was: {provider})."

    return _on_owner(_do_disconnect)


def browser_ai_switch(provider: str) -> str:
    return browser_ai_connect(provider)


def _find_input(page, selectors: list[str]) -> object | None:
    for sel in selectors:
        try:
            el = page.wait_for_selector(sel, timeout=5000, state="visible")
            if el:
                return el
        except Exception:
            continue
    return None


def _get_response_count(page, selectors: list[str]) -> int:
    for sel in selectors:
        try:
            els = page.query_selector_all(sel)
            if els:
                return len(els)
        except Exception:
            continue
    return 0


def _extract_last_response(page, selectors: list[str]) -> str:
    for sel in selectors:
        try:
            els = page.query_selector_all(sel)
            if els:
                text = els[-1].inner_text().strip()
                # Accept ANY non-empty answer. The old `len > 3` gate silently
                # discarded legitimate short replies — a number like "391"
                # (17x23), "yes"/"no", "OK" — producing a false "text could not
                # be extracted". Response completion is guarded by the caller's
                # idle-stability loop (_wait_for_new_response_text), not length.
                if text:
                    return text
        except Exception:
            continue
    return ""


def _wait_for_new_response_text(page, info: dict, previous_count: int, previous_text: str) -> str:
    selectors = info["response_selectors"]
    deadline = time.time() + float(info.get("response_poll_timeout", 18))
    idle_seconds = float(info.get("response_idle_seconds", 1.1))
    last_text = ""
    last_change = time.time()
    while time.time() < deadline:
        count = _get_response_count(page, selectors)
        text = _extract_last_response(page, selectors)
        if text and count > previous_count:
            if text != last_text:
                last_text = text
                last_change = time.time()
            elif time.time() - last_change >= idle_seconds:
                return text
        elif text and previous_count == 0 and text != previous_text:
            if text != last_text:
                last_text = text
                last_change = time.time()
            elif time.time() - last_change >= idle_seconds:
                return text
        elif text and last_text and text != previous_text and time.time() - last_change >= idle_seconds:
            return text
        time.sleep(0.25)
    return last_text


def browser_ai_send(message: str) -> str:
    if not _SESSION["ready"]:
        return ""

    provider = _SESSION["provider"]
    info = PROVIDERS[provider]

    def _do_send():
        with _LOCK:
            try:
                page = _SESSION["page"]
                if not page:
                    return "[Browser AI] No page. Reconnect with: browser ai connect " + provider

                input_el = _find_input(page, info["input_selectors"])
                if not input_el:
                    page.goto(info["url"], timeout=15000, wait_until="domcontentloaded")
                    time.sleep(2)
                    input_el = _find_input(page, info["input_selectors"])

                if not input_el:
                    return (
                        f"[Browser AI — {info['name']}] Input not found.\n"
                        "Make sure you are logged in and the page is fully loaded.\n"
                        "Try: browser ai disconnect  then: browser ai connect " + provider
                    )

                previous_response_count = _get_response_count(page, info["response_selectors"])
                previous_response_text = _extract_last_response(page, info["response_selectors"])
                input_el.click()
                time.sleep(0.5)

                method = info.get("type_method", "fill")
                if method == "type":
                    try:
                        input_el.evaluate("el => { el.textContent = ''; }")
                    except Exception:
                        pass
                    try:
                        page.keyboard.insert_text(message)
                    except Exception:
                        page.keyboard.type(message, delay=int(info.get("type_delay_ms", 10)))
                else:
                    input_el.fill("")
                    input_el.type(message, delay=int(info.get("type_delay_ms", 10)))

                time.sleep(0.4)

                send_method = info.get("send_method", "enter")
                if send_method == "button":
                    send_btn_sel = info.get("send_button", "")
                    sent = False
                    if send_btn_sel:
                        for sel in [s.strip() for s in send_btn_sel.split(",")]:
                            try:
                                btn = page.wait_for_selector(
                                    sel,
                                    timeout=int(info.get("send_button_timeout_ms", 1200)),
                                    state="visible",
                                )
                                if btn and btn.is_enabled():
                                    btn.click()
                                    sent = True
                                    break
                            except Exception:
                                continue
                    if not sent:
                        page.keyboard.press("Enter")
                else:
                    page.keyboard.press("Enter")

                last_text = _wait_for_new_response_text(page, info, previous_response_count, previous_response_text)
                if last_text:
                    return f"[{info['name']}]\n\n{last_text}"

                deadline = time.time() + info.get("streaming_timeout", 20)
                time.sleep(0.5)

                done_sel = info.get("streaming_done_selector", "")
                if done_sel:
                    remaining = max(5000, int((deadline - time.time()) * 1000))
                    try:
                        page.wait_for_selector(done_sel, timeout=remaining)
                    except Exception:
                        pass

                time.sleep(0.5)

                last_text = _extract_last_response(page, info["response_selectors"])
                last_count = _get_response_count(page, info["response_selectors"])
                if last_text and (last_count > previous_response_count or last_text != previous_response_text):
                    return f"[{info['name']}]\n\n{last_text}"

                return (
                    f"[{info['name']}] Response received but text could not be extracted.\n"
                    "Check the browser window to read it directly."
                )

            except Exception as exc:
                return f"[Browser AI error — {provider}] {exc}"

    return _on_owner(_do_send)


def browser_ai_chat_if_connected(message: str) -> str:
    if not _SESSION["ready"]:
        return ""
    return browser_ai_send(message)
