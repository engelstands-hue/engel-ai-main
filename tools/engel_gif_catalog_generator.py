#!/usr/bin/env python3
"""
Engel GIF Catalog Generator — pure local procedural GIF creation for Engel AI Main.

Purpose:
- Give Engel AI Main (running on Dell 730xd server, Proxmox CT 246) the **CODE** (not just prompts) + data to *create*
  distinct, fully CUSTOMIZABLE GIFs for **ALL Star Wars ones** (~178 categories: 80 realistic Vader, 72 funny memes, 26 general).
- Pure local Pillow code in _render_star_wars creates high-quality realistic-style (Vader helmet layers, Yoda, ships, sabers, funny meme elements).
- No external prompts/providers needed at runtime for any Star Wars category.
- Every GIF customizable at runtime by Engel.
- 100% D: drive only. No network. No providers. No background workers.
- Engel (or operator) can import and call directly.

Usage from Engel AI Main (on Dell 730xd):
  from tools.engel_gif_catalog_generator import create_gif_for_category, create_funny_star_wars_meme
  # Code creates for ANY Star Wars id (Vader realistic, memes, lightsaber, Yoda, Falcon, etc.)
  gif_path = create_gif_for_category("darth_vader_realistic_042", custom_label="Vader realistic")
  gif_path = create_funny_star_wars_meme("vader_lack_of_faith_coffee_meme")

All Star Wars use local code.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
CATALOG_JSON = ROOT / "memory" / "engel_gif_categories.json"
DEFAULT_OUT_DIR = ROOT / "runtime" / "gifs" / "catalog_samples"
LIBRARY_DIR = ROOT / "runtime" / "gifs" / "engel_gif_library"  # The official customizable GIF library for Engel AI Main on server

# Ensure we never touch C:
def _assert_d_drive(path: Path) -> None:
    if str(path.resolve()).lower().startswith("c:"):
        raise RuntimeError(f"REFUSING C: path for Engel GIF catalog: {path}")


def _ensure_dir(p: Path) -> None:
    _assert_d_drive(p)
    p.mkdir(parents=True, exist_ok=True)


def load_catalog() -> dict:
    _assert_d_drive(CATALOG_JSON)
    with open(CATALOG_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    if data.get("total_categories", 0) < 300:
        raise ValueError("Catalog must contain at least 300 categories for the expanded customizable library")
    return data


def _hash_seed(s: str) -> int:
    return int(hashlib.sha256(s.encode("utf-8")).hexdigest()[:8], 16)


def _get_palette_for_group(group: str, seed: int) -> List[str]:
    """Themed color palettes per group. Different groups feel different."""
    base = {
        "Core Reactions": ["#ff6b6b", "#4ecdc4", "#ffe66d", "#95e1d3", "#f38181"],
        "System & Status": ["#00d9ff", "#8f5cff", "#ffd166", "#00ff99", "#2d3436"],
        "Faith & Bible": ["#f4d03f", "#f5b041", "#d4ac0d", "#b7950b", "#f9e79f"],
        "Agentic & Swarm": ["#00b894", "#00cec9", "#0984e3", "#6c5ce7", "#fdcb6e"],
        "Nature & Creatures": ["#27ae60", "#2ecc71", "#1abc9c", "#16a085", "#f39c12"],
        "Creative & Tech": ["#e84393", "#6c5ce7", "#00cec9", "#fd79a8", "#a29bfe"],
    }
    pal = base.get(group, ["#3498db", "#9b59b6", "#e74c3c", "#f1c40f", "#2ecc71"])
    # Slight rotation by seed so same group categories still vary
    rot = seed % len(pal)
    return pal[rot:] + pal[:rot]


def _normalize_custom(custom: dict) -> dict:
    """Merge user custom params with safe defaults. Engel AI Main on server can pass these to customize every GIF."""
    c = dict(custom or {})
    return {
        "width": int(c.get("width", 480)),
        "height": int(c.get("height", 270)),
        "frames": int(c.get("frames", 18)),  # fewer frames = faster generation for library
        "duration_ms": int(c.get("duration_ms", 70)),
        "bg_color": c.get("bg_color"),
        "colors": c.get("colors"),  # list of hex or None
        "custom_label": c.get("custom_label"),  # override main label e.g. Bible verse or agent name
        "overlay_text": c.get("overlay_text"),  # extra line of text
        "style": c.get("style", "default"),  # "faith", "swarm", "minimal", "vibrant", "tech"
        "intensity": float(c.get("intensity", 1.0)),  # motion amount
        "add_border": c.get("add_border", True),
        "funny": bool(c.get("funny", False)),
    }


def _get_funny_caption(category_id: str, name: str, group: str) -> str:
    """Generate Engel-flavored funny captions. 100% local humor, zero provider vibes."""
    import hashlib
    seed = int(hashlib.sha256(category_id.encode()).hexdigest()[:6], 16)
    jokes = [
        f"{name}? Engel's version has 47% more hive drama LOL",
        "D: drive powered. No C: allowed. Fight me.",
        "Made with 100% local electrons (and mild sarcasm)",
        "Engel: 'I made this. No internet. You're welcome.'",
        "AI companion with more personality than your group chat",
        "Local only. Like grandma's WiFi password.",
    ]
    group_jokes = {
        "Faith & Bible": [
            f"{name} - even burning bushes deserve a good GIF",
            "Holy spirit approved. (No spirits harmed in production)",
            "For the Sunday school kids who secretly wanted memes",
            "Tiny rock, giant problem. Classic Engel W.",
        ],
        "Agent Roles": [
            f"{name} reporting for duty... with snacks",
            "Agent activated. Brain cell borrowed from the colony.",
            "Sub-agent actually did the thing this time!",
            "When the guardian watchdog barks at C: drives only",
        ],
        "System & Status": [
            f"{name}... still loading since Windows 95",
            "Error 418: I'm a teapot (Engel is a full espresso machine)",
            "99 bugs in the code... patch one, 127 more appear",
        ],
        "Abstract Motion": [
            "Abstract? Engel calls it 'modern art on a budget'",
            "Spinning for no reason. Just like the last meeting.",
        ],
        "Custom Library": [
            "Custom for you. Engel asked Josh... eventually.",
        ],
    }
    pool = group_jokes.get(group, jokes) + jokes
    return pool[seed % len(pool)]


def _render_star_wars(category_id: str, name: str, group: str, width: int = 480, height: int = 270, frames: int = 18, **custom) -> List[Any]:
    """Procedural code to CREATE high-quality realistic-style Star Wars GIFs for ALL Star Wars categories (178+).
    Pure local Pillow — no prompts, no providers. Covers Realistic Vader (80), Funny Memes (72), general Star Wars (26).
    Engel AI Main calls create_gif_for_category or create_funny... — code auto-routes.
    Customizable. "Realistic" via layered drawing (helmet, ships, sabers, funny meme elements).
    Enhanced with more details: multi-layer helmet, saber glows, ship details, animations, backgrounds.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont, ImageFilter
        import math
    except Exception as e:
        raise RuntimeError("Pillow required for Engel Star Wars generator") from e

    p = _normalize_custom(custom)
    width, height, frames = p["width"], p["height"], p["frames"]
    intensity = p["intensity"]
    label = p["custom_label"] or name
    overlay = p.get("overlay_text", "")

    mid = (category_id + " " + name + " " + group).lower()
    imgs = []
    for fi in range(frames):
        # More detailed "realistic" bg
        bg = (10, 8, 15) if "vader" in mid else (20, 25, 35)
        im = Image.new("RGB", (width, height), bg)
        draw = ImageDraw.Draw(im)

        # Subtle starfield or room bg for realism
        for i in range(20):
            sx = (i * 37 + fi * 2) % width
            sy = (i * 23 + fi) % (height - 50)
            draw.ellipse([sx, sy, sx+1, sy+1], fill=(40, 40, 50))

        cx, cy = width // 2, height // 2 - 20

        # Enhanced realistic drawing with more details
        if "vader" in mid or "darth" in mid:
            # Multi-layer helmet for "high quality realistic"
            # Outer helmet
            draw.ellipse([cx-95, cy-115, cx+95, cy+75], fill=(8,8,8), outline=(100,100,100), width=4)
            # Inner mask
            draw.ellipse([cx-75, cy-85, cx+75, cy+35], fill=(20,20,20))
            # Eye slits with glow animation
            glow = int(120 + 60 * abs(math.sin(fi * 0.25 * intensity)))
            draw.rectangle([cx-48, cy-38, cx-18, cy-18], fill=(glow, 10, 10))
            draw.rectangle([cx+18, cy-38, cx+48, cy-18], fill=(glow, 10, 10))
            # More vents/details
            for yy in range(-15, 45, 10):
                draw.line([(cx-38, cy+yy), (cx+38, cy+yy)], fill=(50,50,50), width=2)
            # Chest plate detail
            draw.rectangle([cx-25, cy+45, cx+25, cy+70], fill=(30,30,30), outline=(70,70,70))
            # Cape flow (animated)
            cape_off = int(3 * math.sin(fi * 0.4 * intensity))
            draw.polygon([(cx-30, cy+50), (cx+30, cy+50), (cx+50+cape_off, height-10), (cx-50+cape_off, height-10)], fill=(5,5,5))
            # Red saber with glow layers
            sx = cx + 60 + int(5*math.sin(fi*0.5))
            draw.line([(cx+20, cy+30), (sx, cy-20)], fill=(150,0,0), width=12)
            draw.line([(cx+20, cy+30), (sx, cy-20)], fill=(255,50,50), width=6)
            draw.line([(cx+20, cy+30), (sx, cy-20)], fill=(255,200,200), width=2)
        elif "yoda" in mid:
            # More detailed Yoda
            draw.ellipse([cx-55, cy-65, cx+55, cy+25], fill=(70,130,70), outline=(40,80,40))
            draw.ellipse([cx-70, cy-75, cx-35, cy-35], fill=(70,130,70))  # ear
            draw.ellipse([cx+35, cy-75, cx+70, cy-35], fill=(70,130,70))
            draw.ellipse([cx-12, cy-35, cx+12, cy-10], fill=(20,20,20))  # eyes
            draw.arc([cx-30, cy-5, cx+30, cy+25], 0, 180, fill=(30,60,30), width=2)  # mouth
            # Robe
            draw.polygon([(cx-40, cy+20), (cx+40, cy+20), (cx+30, height), (cx-30, height)], fill=(40,60,40))
        elif "falcon" in mid or "ship" in mid:
            # Detailed Falcon
            draw.polygon([(cx-110, cy+5), (cx+110, cy-25), (cx+110, cy+25), (cx-110, cy+15)], fill=(70,75,85), outline=(180,180,190))
            # Windows, guns
            draw.ellipse([cx-20, cy-15, cx+20, cy+5], fill=(40,40,50))
            draw.rectangle([cx+80, cy-30, cx+95, cy-10], fill=(50,50,60))
            draw.rectangle([cx+80, cy+10, cx+95, cy+30], fill=(50,50,60))
        else:
            # Enhanced saber
            draw.line([(cx-70, cy-35), (cx+70, cy+35)], fill=(30,100,200), width=10)
            draw.line([(cx-70, cy-35), (cx+70, cy+35)], fill=(80,180,255), width=5)
            draw.line([(cx-70, cy-35), (cx+70, cy+35)], fill=(200,230,255), width=2)
            # Sparks
            for s in range(3):
                sx = cx + int(30 * math.cos(fi*0.8 + s))
                sy = cy + int(20 * math.sin(fi*0.8 + s))
                draw.ellipse([sx-2, sy-2, sx+2, sy+2], fill=(255,255,200))
            # Extra high quality details: particle effects, more glows
            for s in range(5):
                sx = (cx + fi * 4 + s * 15) % (width - 10)
                sy = cy + int(15 * math.sin(fi * 0.5 + s))
                draw.ellipse([sx-1, sy-1, sx+1, sy+1], fill=(255,255,150))
            # Add subtle vignette for cinematic realistic feel
            draw.rectangle([0, 0, width, 5], fill=(5,5,10))
            draw.rectangle([0, height-5, width, height], fill=(5,5,10))

        # Text / meme logic (enhanced)
        text = label[:50]
        if "coffee" in mid or "lack" in mid:
            draw.ellipse([cx+55, cy-5, cx+105, cy+45], fill=(100,70,40), outline=(220,200,180))
            text = "I FIND YOUR LACK OF FAITH DISTURBING"
        elif "fine" in mid or "death" in mid:
            for ii in range(10):
                x = (cx - 90 + ii*18 + fi*3) % (width-20)
                draw.rectangle([x, cy+50, x+12, height-5], fill=(220+int(30*math.sin(fi*0.5)), 80, 20))
            text = "THIS IS FINE (Death Star)"
        elif "father" in mid:
            text = "NO... I AM YOUR FATHER"
        else:
            text += " (Star Wars)"

        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
        except:
            font = ImageFont.load_default()
        draw.text((20, height-52), text, fill=(0,0,0), font=font)
        draw.text((18, height-50), text, fill=(255,210,80), font=font)
        if overlay:
            draw.text((18, 8), overlay, fill=(200,220,255), font=font)

        # More animation for details
        if fi % 3 == 0:
            im = im.filter(ImageFilter.SMOOTH_MORE if "vader" in mid else ImageFilter.SMOOTH)
        imgs.append(im)

    return imgs


def _default_renderer(
    category_id: str,
    name: str,
    group: str,
    width: int = 480,
    height: int = 270,
    frames: int = 18,
    **custom,
) -> List[Any]:
    """General procedural renderer. FULLY CUSTOMIZABLE for Engel AI Main.
    Pass custom_label, colors, overlay_text, style, intensity, bg_color etc. from server code.
    """
    try:
        from PIL import Image, ImageDraw
    except Exception as e:
        raise RuntimeError("Pillow is required for Engel GIF catalog generator") from e

    p = _normalize_custom(custom)
    width, height, frames = p["width"], p["height"], p["frames"]
    intensity = max(0.5, min(2.5, p["intensity"]))

    seed = _hash_seed(category_id)
    palette = p["colors"] or _get_palette_for_group(group, seed)
    bg = p["bg_color"] or ("#0a0f1e" if "Faith" not in group else "#0f0a05")

    label = p["custom_label"] or name
    overlay = p["overlay_text"]
    style = p["style"]

    imgs = []
    for fi in range(frames):
        im = Image.new("RGB", (width, height), bg)
        draw = ImageDraw.Draw(im)

        # Border (customizable)
        if p["add_border"]:
            border_col = palette[fi % len(palette)]
            bw = max(1, int(2 + ((fi // 3) % 3) * intensity))
            draw.rectangle((6, 6, width - 6, height - 6), outline=border_col, width=bw)

        # Apply style modifiers
        motion = int(4 * intensity)
        if style == "faith":
            # Stronger crosses / light
            cx, cy = width // 2, height // 2 - 8
            arm = int(30 + (fi % 9) * intensity)
            draw.line([(cx, cy - arm), (cx, cy + arm)], fill=palette[(fi + 1) % len(palette)], width=6)
            draw.line([(cx - arm, cy), (cx + arm, cy)], fill=palette[(fi + 2) % len(palette)], width=6)
        elif style == "swarm":
            for i in range(9):
                x = 50 + ((i * 47 + fi * motion) % (width - 100))
                y = 60 + ((i * 23 + (fi * motion // 2)) % (height - 120))
                r = max(2, int(3 + ((i + fi) % 4) * intensity))
                draw.ellipse((x - r, y - r, x + r, y + r), fill=palette[i % len(palette)])
        elif style == "minimal":
            # Clean fewer elements
            for i in range(3):
                x = (width // 4) * (i + 1)
                y = height // 2 + int(10 * ((fi + i) % 5 - 2) * intensity)
                draw.ellipse((x-6, y-6, x+6, y+6), fill=palette[i % len(palette)])
        else:
            # Default + intensity scaling
            for i in range(5):
                import math
                ang = (fi * (9 + int(intensity)) + i * 19) % 360
                r = 14 + i * 2
                x = width // 2 + int(r * math.cos(math.radians(ang + i * 27)))
                y = height // 2 - 18 + int(r * 0.55 * math.sin(math.radians(ang * 1.1)))
                draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill=palette[(i + fi) % len(palette)])

        # Labels - customizable
        draw.text((18, height - 42), label[:38], fill="#ffffff")
        if overlay:
            draw.text((18, height - 24), str(overlay)[:42], fill="#ffdd88")
        else:
            draw.text((18, height - 24), f"{group} • {category_id}", fill="#aaaaaa")

        # FUNNY MODE - Engel humor injection (bounce the joke)
        if p.get("funny"):
            joke = _get_funny_caption(category_id, name, group)
            # silly bouncing y
            y_bounce = height - 68 + int(3 * ((fi % 6) - 3))
            draw.text((18, max(10, y_bounce)), joke[:52], fill="#ffcc00")
            # extra silly touch: little "lol" dots
            for dx in range(3):
                draw.ellipse((width-40+dx*6, 20 + (fi+dx)%4 , width-36+dx*6, 24 + (fi+dx)%4), fill="#ffaa00")

        imgs.append(im)

    return imgs


# A few hand-crafted special renderers for high-signal categories (so they feel unique)
SPECIAL_RENDERERS: Dict[str, Callable] = {}


def _register_special(cat_id: str):
    def deco(fn):
        SPECIAL_RENDERERS[cat_id] = fn
        return fn
    return deco


@_register_special("joyful_celebration")
def _render_joyful(width=480, height=270, frames=18, **custom):
    from PIL import Image, ImageDraw
    p = _normalize_custom(custom)
    width, height, frames = p["width"], p["height"], p["frames"]
    colors = p["colors"] or ["#ff2d55", "#ffd60a", "#30d158", "#00e0ff", "#bf5af2"]
    label = p["custom_label"] or "JOYFUL CELEBRATION"
    imgs = []
    for fi in range(frames):
        im = Image.new("RGB", (width, height), "#05070f")
        draw = ImageDraw.Draw(im)
        for i in range(42):
            x = (i * 19 + fi * 6) % (width - 20)
            y = 30 + ((i * 13 + fi * 4) % (height - 90))
            r = max(2, int(3 + (i % 3) * p["intensity"]))
            c = colors[(i + fi) % len(colors)]
            draw.ellipse((x - r, y - r, x + r, y + r), fill=c)
        draw.text((18, height - 42), label[:36], fill="#ffffff")
        if p["overlay_text"]:
            draw.text((18, height - 24), str(p["overlay_text"])[:40], fill="#ffdd88")
        if p.get("funny"):
            joke = _get_funny_caption("joyful_celebration", "Joyful Celebration", "Core Reactions")
            yb = height - 68 + int(2 * ((fi % 5)-2))
            draw.text((18, max(8, yb)), joke[:48], fill="#ffcc00")
        imgs.append(im)
    return imgs


@_register_special("open_bible_glow")
def _render_bible(width=480, height=270, frames=18, **custom):
    from PIL import Image, ImageDraw
    p = _normalize_custom(custom)
    width, height, frames = p["width"], p["height"], p["frames"]
    label = p["custom_label"] or "OPEN BIBLE GLOW"
    imgs = []
    for fi in range(frames):
        im = Image.new("RGB", (width, height), "#0c0803")
        draw = ImageDraw.Draw(im)
        draw.rectangle((80, 60, width-80, 170), fill="#3a2f1f", outline="#d4af37", width=3)
        draw.line([(width//2, 60), (width//2, 170)], fill="#d4af37", width=2)
        draw.ellipse((width//2-30, 30, width//2+30, 90), fill="#f4d03f")
        draw.text((60, height-42), label[:36], fill="#f4d03f")
        if p.get("overlay_text"):
            draw.text((60, height-24), str(p["overlay_text"])[:42], fill="#ffdd88")
        if p.get("funny"):
            joke = _get_funny_caption("open_bible_glow", "Open Bible Glow", "Faith & Bible")
            draw.text((60, height-68), joke[:48], fill="#ffcc00")
        imgs.append(im)
    return imgs


@_register_special("hive_mind_colony")
def _render_hive(width=480, height=270, frames=18, **custom):
    from PIL import Image, ImageDraw
    import math
    p = _normalize_custom(custom)
    width, height, frames = p["width"], p["height"], p["frames"]
    label = p["custom_label"] or "HIVE MIND COLONY"
    imgs = []
    for fi in range(frames):
        im = Image.new("RGB", (width, height), "#050d0a")
        draw = ImageDraw.Draw(im)
        cx, cy = width // 2, height // 2 - 12
        draw.ellipse((cx - 12, cy - 12, cx + 12, cy + 12), fill="#ffd700")
        for i in range(9):
            ang = (fi * 7 + i * 40) % 360
            r = 45 + (i % 3) * 7
            x = cx + int(r * math.cos(math.radians(ang)))
            y = cy + int(r * 0.65 * math.sin(math.radians(ang)))
            draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill="#00ff9f")
            draw.line([(cx, cy), (x, y)], fill="#00aa77", width=1)
        draw.text((18, height - 42), label[:36], fill="#00ff9f")
        if p.get("overlay_text"):
            draw.text((18, height - 24), str(p["overlay_text"])[:40], fill="#aaffdd")
        if p.get("funny"):
            joke = _get_funny_caption("hive_mind_colony", "Hive Mind Colony", "Agentic & Swarm")
            draw.text((18, height-68), joke[:48], fill="#ffcc00")
        imgs.append(im)
    return imgs


@_register_special("praying_hands")
def _render_prayer(width=480, height=270, frames=18, **custom):
    from PIL import Image, ImageDraw
    p = _normalize_custom(custom)
    width, height, frames = p["width"], p["height"], p["frames"]
    label = p["custom_label"] or "PRAYING HANDS"
    imgs = []
    for fi in range(frames):
        im = Image.new("RGB", (width, height), "#0a0804")
        draw = ImageDraw.Draw(im)
        y_off = int(3 * ((fi % 7) - 3) * p["intensity"])
        draw.ellipse((width//2-70, 55 + y_off, width//2+70, 155 + y_off), fill="#3a2f1f")
        draw.ellipse((width//2-55, 50 + y_off, width//2+55, 125 + y_off), fill="#d4af37")
        draw.text((width//2-80, height-42), label[:36], fill="#f4d03f")
        if p.get("overlay_text"):
            draw.text((width//2-80, height-24), str(p["overlay_text"])[:38], fill="#ffdd88")
        imgs.append(im)
    return imgs


def _make_frames(
    category_id: str,
    name: str,
    group: str,
    width: int = 480,
    height: int = 270,
    frames: int = 18,
    **custom,
) -> List[Any]:
    if category_id in SPECIAL_RENDERERS:
        return SPECIAL_RENDERERS[category_id](width=width, height=height, frames=frames, **custom)
    if 'star wars' in group.lower() or 'star wars' in category_id.lower() or 'vader' in category_id.lower() or 'jedi' in category_id.lower() or 'falcon' in category_id.lower():
        return _render_star_wars(category_id, name, group, width, height, frames, **custom)
    return _default_renderer(category_id, name, group, width, height, frames, **custom)


def create_gif_for_category(
    category_id: str,
    out_path: Optional[str | Path] = None,
    **custom: Any,
) -> Optional[Path]:
    """MAIN ENTRY FOR ENGEL AI MAIN (Dell 730xd server).

    Fully customizable: pass width, height, custom_label (e.g. scripture or agent name),
    colors, overlay_text, style, intensity, bg_color etc.

    Example for Engel on server:
        create_gif_for_category("praying_hands", custom_label="Psalm 23", overlay_text="The Lord is my shepherd")
    """
    catalog = load_catalog()
    cats = {c["id"]: c for c in catalog["categories"]}
    if category_id not in cats:
        raise KeyError(f"Unknown category id: {category_id}. See memory/engel_gif_categories.json")

    cat = cats[category_id]
    name = cat["name"]
    group = cat["group"]

    p = _normalize_custom(custom)

    _ensure_dir(DEFAULT_OUT_DIR)
    if out_path:
        out = Path(out_path)
    else:
        if group == "Star Wars Funny Memes":
            _ensure_dir(LIBRARY_DIR / "funny_memes")
            out = LIBRARY_DIR / "funny_memes" / f"{category_id}.gif"
        else:
            out = DEFAULT_OUT_DIR / f"{category_id}.gif"
    _assert_d_drive(out)

    frames_list = _make_frames(
        category_id, name, group,
        **custom
    )

    frames_list[0].save(
        out,
        save_all=True,
        append_images=frames_list[1:],
        duration=p["duration_ms"],
        loop=0,
        optimize=False,
    )
    return out if out.exists() else None


def generate_catalog_samples(
    category_ids: Optional[List[str]] = None,
    out_dir: Optional[str | Path] = None,
    limit: int = 9999,
) -> List[Path]:
    """Batch generate GIFs. Engel can call this for a learning set or full catalog."""
    catalog = load_catalog()
    out_root = Path(out_dir) if out_dir else DEFAULT_OUT_DIR
    _ensure_dir(out_root)

    all_cats = catalog["categories"]
    if category_ids:
        selected = [c for c in all_cats if c["id"] in category_ids]
    else:
        selected = all_cats

    selected = selected[:limit]
    results: List[Path] = []

    for c in selected:
        try:
            p = create_gif_for_category(c["id"], out_path=out_root / f"{c['id']}.gif")
            if p:
                results.append(p)
                print(f"  created {p.name}  ({c['group']})")
        except Exception as e:
            print(f"  FAILED {c['id']}: {e}")

    print(f"\nGenerated {len(results)} GIFs into {out_root}")
    return results


def create_funny_star_wars_meme(meme_id: str, out_path: Optional[str | Path] = None, **custom) -> Optional[Path]:
    """Convenience for Engel AI Main: create a funny realistic Star Wars meme GIF using embedded code.
    Example: create_funny_star_wars_meme('vader_coffee_meme')
    """
    return create_gif_for_category(meme_id, out_path=out_path, funny=True, **custom)


def build_gif_library(count: int = 200, out_dir: Optional[str | Path] = None, seed_variants: bool = True) -> dict:
    """Build the official customizable GIF library for Engel AI Main on the Dell 730xd server.
    Generates up to `count` distinct customizable GIFs (using varied custom params for diversity).
    Returns manifest with paths and the params used so Engel can learn/reproduce.
    """
    catalog = load_catalog()
    out_root = Path(out_dir) if out_dir else LIBRARY_DIR
    _ensure_dir(out_root)

    all_cats = catalog["categories"]
    manifest = {
        "schema": "engel_gif_library_v1",
        "generated_utc": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "target": "Engel AI Main - Dell 730xd (CT 246)",
        "total_gifs": 0,
        "entries": [],
    }

    custom_variants = [
        {"custom_label": "The Lord is my Shepherd", "overlay_text": "Psalm 23", "style": "faith"},
        {"custom_label": "Hive Connected", "overlay_text": "Agent Colony", "style": "swarm", "intensity": 1.4},
        {"custom_label": "", "style": "minimal", "colors": ["#222222", "#aaaaaa"]},
        {"custom_label": "Engel AI Main", "overlay_text": "Local on 730xd", "style": "tech"},
        {"intensity": 1.8, "style": "vibrant"},
        {"custom_label": "Custom for Engel", "overlay_text": "Server Runtime", "bg_color": "#111111"},
    ]

    created = 0
    idx = 0
    while created < count and idx < len(all_cats) * 3:
        cat = all_cats[idx % len(all_cats)]
        cid = cat["id"]
        try:
            variant = custom_variants[created % len(custom_variants)].copy()
            if seed_variants:
                variant["custom_label"] = variant.get("custom_label") or cat["name"][:28]
            fname = f"{cid}_lib_{created:04d}.gif"
            outp = out_root / fname
            p = create_gif_for_category(cid, out_path=outp, **variant)
            if p:
                try:
                    rel = str(p.relative_to(ROOT))
                except ValueError:
                    rel = str(p)
                entry = {
                    "id": cid,
                    "path": rel,
                    "params": variant,
                    "name": cat["name"],
                    "group": cat["group"],
                }
                manifest["entries"].append(entry)
                created += 1
                print(f"  library[{created}] {fname} ({cat['group']})")
        except Exception as e:
            print(f"  skip {cid}: {e}")
        idx += 1

    manifest["total_gifs"] = created
    man_path = out_root / "library_manifest.json"
    man_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\nBuilt Engel GIF library with {created} customizable GIFs -> {out_root}")
    print(f"Manifest: {man_path}")
    return manifest


def create_high_quality_gif_from_image(base_image_path: str, out_path: Optional[str | Path] = None, width: int = 480, duration: int = 6, fps: int = 12) -> Optional[Path]:
    """Create an animated GIF from a high quality Grok-generated image using pan/zoom loop.
    This allows high quality images created with Grok Imagine to become smooth GIFs for the catalog.
    Uses similar logic to engel_media_to_gif for stills.
    """
    try:
        from PIL import Image
    except Exception:
        print("Pillow required")
        return None
    src = Path(base_image_path)
    if not src.exists():
        print("Base image not found")
        return None
    if out_path is None:
        out_path = src.with_suffix('.gif')
    out = Path(out_path)
    _assert_d_drive(out)
    try:
        img = Image.open(src).convert('RGB')
        w, h = img.size
        if w < 100 or h < 100:
            return None
        frames_list = []
        total = 24
        for i in range(total):
            zoom = 1.0 + 0.12 * (i / (total - 1))
            cw, ch = int(w / zoom), int(h / zoom)
            x = int((w - cw) * (i / (total - 1)) * 0.5)
            y = int((h - ch) * 0.4)
            frame = img.crop((x, y, x + cw, y + ch)).resize((width, int(width * h / w)))
            frames_list.append(frame)
        frames_list += frames_list[::-1]
        frames_list[0].save(out, save_all=True, append_images=frames_list[1:], duration=1000//fps, loop=0, optimize=True)
        return out
    except Exception as e:
        print('Error animating high quality image:', e)
        return None


def fill_all_categories_funny_library(out_dir: Optional[str | Path] = None, frames: int = 12) -> dict:
    """Fill the library with one FUNNY customizable GIF per category.
    This 'fills all categories' with humorous Engel-flavored animations.
    Funny captions, bouncing jokes, silly extras. Perfect for Engel AI Main on Dell 730xd.
    """
    catalog = load_catalog()
    out_root = Path(out_dir) if out_dir else LIBRARY_DIR
    _ensure_dir(out_root)

    all_cats = catalog["categories"]
    manifest_path = out_root / "funny_all_categories_manifest.json"
    manifest = {
        "schema": "engel_gif_funny_library_v1",
        "generated_utc": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "target": "Engel AI Main on Dell 730xd (CT 246) - ALL CATEGORIES FILLED + FUNNY",
        "total_gifs": 0,
        "note": "Every category has a funny version. Humor level: maximum local snark.",
        "entries": [],
    }

    created = 0
    for cat in all_cats:
        cid = cat["id"]
        name = cat["name"]
        group = cat["group"]
        try:
            # Force funny + some random flavor per category
            variant = {
                "funny": True,
                "frames": frames,
                "custom_label": name[:32],
                "style": "faith" if "Bible" in group or "Faith" in group else ("swarm" if "Agent" in group or "Swarm" in group else "vibrant"),
            }
            # extra funny overlay
            variant["overlay_text"] = "😂 Engel Local Only"

            fname = f"{cid}_FUNNY.gif"
            outp = out_root / fname
            if outp.exists():
                print(f"  skip existing funny: {fname}")
                created += 1
                continue

            p = create_gif_for_category(cid, out_path=outp, **variant)
            if p:
                rel = str(p) if not str(p).startswith(str(ROOT)) else str(p.relative_to(ROOT))
                entry = {
                    "id": cid,
                    "name": name,
                    "group": group,
                    "path": rel,
                    "params": variant,
                    "funny_caption": _get_funny_caption(cid, name, group),
                }
                manifest["entries"].append(entry)
                created += 1
                if created % 25 == 0:
                    print(f"  funny[{created}] {fname}")
        except Exception as e:
            print(f"  failed funny for {cid}: {e}")

    manifest["total_gifs"] = created
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\n✅ FILLED ALL CATEGORIES with FUNNY GIFs: {created} files")
    print(f"Library: {out_root}")
    print(f"Manifest: {manifest_path}")
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser(description="Engel GIF Catalog Generator — fully customizable GIFs + 300+ category library for Engel AI Main (Dell 730xd)")
    ap.add_argument("--all", action="store_true", help="Generate one per category")
    ap.add_argument("--category", help="Single category id")
    ap.add_argument("--categories", help="Comma list of ids")
    ap.add_argument("--build-library", action="store_true", help="Build the official customizable engel_gif_library with many variants")
    ap.add_argument("--fill-all-funny", action="store_true", help="Generate ONE FUNNY GIF per EVERY category (fills all 322). Remember to be funny!")
    ap.add_argument("--count", type=int, default=200, help="How many GIFs to produce for --build-library")
    ap.add_argument("--out-dir", default=None, help="Output directory (defaults to catalog_samples or library)")
    ap.add_argument("--limit", type=int, default=9999)
    args = ap.parse_args()

    if args.build_library:
        out = args.out_dir or str(LIBRARY_DIR)
        build_gif_library(count=args.count, out_dir=out)
        return 0

    if args.fill_all_funny:
        out = args.out_dir or str(LIBRARY_DIR)
        fill_all_categories_funny_library(out_dir=out)
        return 0

    target_dir = args.out_dir or str(DEFAULT_OUT_DIR)
    _ensure_dir(Path(target_dir))

    if args.category:
        p = create_gif_for_category(args.category, out_path=Path(target_dir) / f"{args.category}.gif")
        print(f"Generated: {p}")
        return 0

    if args.categories:
        ids = [x.strip() for x in args.categories.split(",") if x.strip()]
        generate_catalog_samples(category_ids=ids, out_dir=target_dir)
        return 0

    if args.all:
        generate_catalog_samples(out_dir=target_dir, limit=args.limit)
        return 0

    print("Usage examples for Engel AI Main on Dell 730xd:")
    print("  python tools/engel_gif_catalog_generator.py --category open_bible_glow --custom_label 'Psalm 23'")
    print("  (via code): create_gif_for_category('hive_mind_colony', custom_label='Engel Main', style='swarm', funny=True)")
    print("  python tools/engel_gif_catalog_generator.py --build-library --count 200")
    print("  python tools/engel_gif_catalog_generator.py --fill-all-funny   # ONE funny GIF for EVERY category 😂")
    return 1


if __name__ == "__main__":
    sys.exit(main())