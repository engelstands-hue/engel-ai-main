#!/usr/bin/env python3
"""Convert Engel-generated media (Grok Imagine mp4/webm or a still image)
into a chat-displayable animated GIF. Prints one JSON line: {ok, gif_path,...}.

ffmpeg resolution order: imageio-ffmpeg bundled binary -> PATH. Stills get a
gentle pan-zoom loop via Pillow so they feel alive in the chat bubble.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

VIDEO_EXTS = {".mp4", ".webm", ".mov", ".mkv"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
MAX_GIF_BYTES = 24_000_000  # local display cap, not Discord's


def find_ffmpeg() -> str | None:
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    return shutil.which("ffmpeg")


def video_to_gif(src: Path, out: Path, seconds: int, width: int, fps: int) -> bool:
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        return False
    for w, f in ((width, fps), (360, 10), (280, 8)):
        filters = f"fps={f},scale={w}:-2:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse"
        proc = subprocess.run(
            [ffmpeg, "-y", "-t", str(seconds), "-i", str(src), "-vf", filters, "-loop", "0", str(out)],
            capture_output=True,
            timeout=300,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if proc.returncode == 0 and out.is_file() and 10_000 < out.stat().st_size <= MAX_GIF_BYTES:
            return True
    return False


def image_to_gif(src: Path, out: Path, width: int) -> bool:
    try:
        from PIL import Image
    except Exception:
        return False
    try:
        img = Image.open(src).convert("RGB")
    except Exception:
        return False
    w, h = img.size
    if w < 100 or h < 100:
        return False
    frames = []
    total = 26
    for i in range(total):
        zoom = 1.0 + 0.14 * (i / (total - 1))
        cw, ch = int(w / zoom), int(h / zoom)
        x = int((w - cw) * (i / (total - 1)) * 0.6)
        y = int((h - ch) * 0.5)
        frames.append(img.crop((x, y, x + cw, y + ch)).resize((width, int(width * h / w))))
    frames += frames[::-1]
    frames[0].save(out, save_all=True, append_images=frames[1:], duration=70, loop=0, optimize=True)
    return out.is_file() and out.stat().st_size > 10_000


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--out", default="")
    ap.add_argument("--seconds", type=int, default=6)
    ap.add_argument("--width", type=int, default=480)
    ap.add_argument("--fps", type=int, default=12)
    args = ap.parse_args()

    src = Path(args.input)
    if not src.is_file():
        print(json.dumps({"ok": False, "status": f"input not found: {src}"}))
        return 1
    out = Path(args.out) if args.out else src.with_suffix(".gif")
    ext = src.suffix.lower()
    if ext in VIDEO_EXTS:
        ok = video_to_gif(src, out, args.seconds, args.width, args.fps)
    elif ext in IMAGE_EXTS:
        ok = image_to_gif(src, out, args.width)
    else:
        print(json.dumps({"ok": False, "status": f"unsupported input type: {ext}"}))
        return 1
    payload = {
        "ok": bool(ok),
        "gif_path": str(out) if ok else "",
        "bytes": out.stat().st_size if ok and out.is_file() else 0,
        "source": str(src),
        "status": "converted" if ok else "conversion failed",
    }
    print(json.dumps(payload))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
