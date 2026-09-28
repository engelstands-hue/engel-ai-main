#!/usr/bin/env python3
"""
Engel AI Main — media generation (image), OpenClaw media-gen port.

Ported concept from OpenClaw (MIT) media tools (text-to-image / image editing).
Engel had only the narrow Grok-imagine lane; this adds real image generation via
Google Gemini's image models (gemini-2.5-flash-image, gemini-3-*-image), using
the same ENGEL_GEMINI_API_KEY that already powers the Gemini chat lane. Returns a
saved PNG. Reference-image editing is supported by passing an input image.

Reimplemented natively in Python (stdlib only); MIT-attributed.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
MEDIA_DIR = ROOT / "runtime" / "media_gen"
DEFAULT_IMAGE_MODEL = "gemini-2.5-flash-image"


def _read_gemini_key() -> str:
    k = os.environ.get("ENGEL_GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if k:
        return k
    try:
        import winreg  # Windows: keys are set at User scope, not always in this process env
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            for name in ("ENGEL_GEMINI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"):
                try:
                    v, _ = winreg.QueryValueEx(key, name)
                    if v:
                        return str(v)
                except FileNotFoundError:
                    continue
    except Exception:
        pass
    return ""


def _generate_image_gemini(prompt: str, *, model: str = DEFAULT_IMAGE_MODEL, out_path: Optional[str] = None,
                           input_image_path: Optional[str] = None, key: Optional[str] = None, timeout: int = 90) -> dict:
    """Gemini image backend. Returns {ok, path, bytes, model, mime} or {ok:false, error}."""
    key = key or _read_gemini_key()
    if not key:
        return {"ok": False, "error": "no Gemini API key (ENGEL_GEMINI_API_KEY)"}
    parts: list[dict] = [{"text": prompt}]
    if input_image_path and Path(input_image_path).exists():
        data = base64.b64encode(Path(input_image_path).read_bytes()).decode("ascii")
        mime = "image/png" if input_image_path.lower().endswith(".png") else "image/jpeg"
        parts.append({"inlineData": {"mimeType": mime, "data": data}})
    body = json.dumps({
        "contents": [{"parts": parts}],
        "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
    }).encode("utf-8")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    started = time.time()
    try:
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", errors="replace")[:300]
        except Exception:
            pass
        return {"ok": False, "error": f"HTTP {e.code}", "detail": detail}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:200]}

    # find the inline image data in the response parts
    img_b64 = None
    mime = "image/png"
    text_note = ""
    for cand in payload.get("candidates", []):
        for p in cand.get("content", {}).get("parts", []):
            inline = p.get("inlineData") or p.get("inline_data")
            if inline and inline.get("data"):
                img_b64 = inline["data"]
                mime = inline.get("mimeType") or inline.get("mime_type") or mime
            elif p.get("text"):
                text_note += p["text"]
    if not img_b64:
        return {"ok": False, "error": "no image in response", "text": text_note[:200],
                "raw_keys": list(payload.keys())}
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    ext = ".png" if "png" in mime else (".jpg" if "jpe" in mime or "jpg" in mime else ".png")
    if not out_path:
        out_path = str(MEDIA_DIR / f"img_{int(time.time()*1000)}{ext}")
    raw = base64.b64decode(img_b64)
    Path(out_path).write_bytes(raw)
    return {"ok": True, "path": out_path, "bytes": len(raw), "model": model, "mime": mime,
            "text": text_note[:160], "elapsed_ms": int((time.time() - started) * 1000)}


def generate_image_grok(prompt: str, *, media_type: str = "image", timeout: int = 240,
                        aspect: str = "", quality: str = "speed") -> dict:
    """Grok Imagine backend (grok.com via Engel's playwright worker). Needs a
    one-time sign-in (browser_profile/grok); currently signed in. Generates and
    downloads real media even when the Gemini image lane is quota-blocked."""
    import subprocess
    venv = ROOT / "runtime" / "browser_ai_venv" / "Scripts" / "python.exe"
    worker = ROOT / "tools" / "engel_grok_imagine_worker.py"
    if not venv.exists() or not worker.exists():
        return {"ok": False, "error": "grok imagine worker/venv missing", "provider": "grok"}
    # imagine defaults to hidden/headless already (--visible is the opt-in for a window).
    argv = [str(venv), str(worker), "imagine", prompt, "--type", media_type, "--timeout", str(timeout)]
    if aspect:
        argv += ["--aspect", aspect]
    if quality:
        argv += ["--mode", quality]
    try:
        cp = subprocess.run(argv, capture_output=True, text=True, timeout=timeout + 90, cwd=str(ROOT), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"grok imagine timed out (>{timeout+90}s)", "provider": "grok"}
    data = None
    try:
        data = json.loads(cp.stdout)
    except Exception:
        import re
        m = re.search(r"\{[\s\S]*\}\s*$", cp.stdout or "")
        if m:
            try:
                data = json.loads(m.group(0))
            except Exception:
                data = None
    if not data or not data.get("ok"):
        return {"ok": False, "provider": "grok",
                "error": (data or {}).get("status") or "grok imagine failed",
                "stderr": (cp.stderr or "")[-300:]}
    downloads = data.get("downloads") or []
    path = downloads[0].get("path") if downloads and isinstance(downloads[0], dict) else None
    if not path:
        return {"ok": False, "provider": "grok", "error": "grok returned no downloaded media", "data": data}
    b = Path(path).stat().st_size if Path(path).exists() else 0
    return {"ok": True, "path": path, "bytes": b, "provider": "grok", "model": "grok-imagine", "media_type": media_type}


def generate_image(prompt: str, *, provider: str = "auto", model: str = DEFAULT_IMAGE_MODEL,
                   out_path: Optional[str] = None, input_image_path: Optional[str] = None,
                   key: Optional[str] = None, timeout: int = 90) -> dict:
    """Generate an image. provider: auto (Gemini then Grok on failure) | gemini | grok.
    Grok is the reliable lane on this machine since the Gemini key has no free image quota."""
    if provider == "grok":
        return generate_image_grok(prompt, timeout=max(timeout, 180))
    gem = _generate_image_gemini(prompt, model=model, out_path=out_path,
                                 input_image_path=input_image_path, key=key, timeout=timeout)
    if gem.get("ok") or provider == "gemini":
        return gem
    # auto: Gemini failed (e.g. 429 no image quota) -> fall over to Grok
    grok = generate_image_grok(prompt, timeout=max(timeout, 180))
    grok["gemini_fallback_from"] = gem.get("error")
    return grok


def _cli(argv: Optional[list[str]] = None) -> int:
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="Engel media generation — image via Gemini (OpenClaw media-gen port).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    im = sub.add_parser("image")
    im.add_argument("--prompt", required=True)
    im.add_argument("--out", default="")
    im.add_argument("--model", default=DEFAULT_IMAGE_MODEL)
    im.add_argument("--input-image", default="", help="reference image to edit")
    im.add_argument("--provider", default="auto", choices=["auto", "gemini", "grok"])
    a = ap.parse_args(argv)
    if a.cmd == "image":
        res = generate_image(a.prompt, provider=a.provider, model=a.model, out_path=a.out or None,
                             input_image_path=a.input_image or None)
        print(json.dumps(res, indent=2))
        return 0 if res.get("ok") else 1
    return 0


if __name__ == "__main__":
    import urllib.error  # noqa: E402  (for the HTTPError handler above)
    raise SystemExit(_cli())
