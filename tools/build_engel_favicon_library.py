#!/usr/bin/env python3
"""Build Engel AI Main's local Discord favicon library. No network."""
from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "runtime" / "favicons" / "library"
SIZE = 128

# Topic id, filename stem, trigger words, accent, glyph kind.
TOPICS: list[tuple[str, str, tuple[str, ...], str, str]] = [
    ("hello", "hello", ("hello", "hi", "hey", "chat", "talk"), "#00d9ff", "smile"),
    ("thanks", "thanks", ("thanks", "thank", "cheers"), "#ffd166", "heart"),
    ("ok", "ok", ("ok", "okay", "yes", "good", "ready"), "#00ff99", "check"),
    ("work", "work", ("work", "job", "task", "order"), "#8f5cff", "gear"),
    ("build", "build", ("build", "make", "create", "wire"), "#00d9ff", "hammer"),
    ("fix", "fix", ("fix", "repair", "broken", "bug"), "#ff5c8a", "wrench"),
    ("code", "code", ("code", "python", "script", "dev"), "#7cf7ff", "terminal"),
    ("image", "image", ("image", "picture", "screenshot", "photo", "ocr"), "#ffd166", "eye"),
    ("gif", "gif", ("gif", "meme", "funny"), "#ff5c8a", "spark"),
    ("discord", "discord", ("discord", "channel", "server"), "#8f5cff", "chat"),
    ("niners", "niners", ("49ers", "niners", "sf", "football"), "#aa0000", "football"),
    ("win", "win", ("win", "won", "touchdown", "score"), "#ffd166", "trophy"),
    ("hive", "hive", ("hive", "ant", "swarm", "colony"), "#ffd166", "hex"),
    ("brain", "brain", ("brain", "think", "idea", "mind"), "#8f5cff", "brain"),
    ("bible", "bible", ("bible", "gospel", "prayer", "faith"), "#ffd166", "book"),
    ("phone", "phone", ("phone", "android", "mobile"), "#00ff99", "phone"),
    ("computer", "computer", ("computer", "laptop", "pc", "server"), "#00d9ff", "cpu"),
    ("memory", "memory", ("memory", "remember", "recall", "save"), "#8f5cff", "disk"),
    ("lock", "lock", ("lock", "safe", "secure", "key"), "#00ff99", "lock"),
    ("warn", "warn", ("warn", "error", "fail", "down"), "#ff5c8a", "warn"),
    ("fire", "fire", ("fire", "hot", "lit"), "#ff6b35", "fire"),
    ("heart", "heart", ("love", "heart", "like"), "#ff5c8a", "heart"),
    ("star", "star", ("star", "night", "wish"), "#ffd166", "star"),
    ("moon", "moon", ("moon", "night", "sleep"), "#8f5cff", "moon"),
    ("sun", "sun", ("sun", "day", "morning"), "#ffd166", "sun"),
    ("coffee", "coffee", ("coffee", "tea", "drink"), "#c48a3a", "mug"),
    ("music", "music", ("music", "song", "beat"), "#8f5cff", "note"),
    ("rocket", "rocket", ("rocket", "launch", "ship"), "#00d9ff", "rocket"),
    ("home", "home", ("home", "house", "room"), "#00ff99", "home"),
    ("gift", "gift", ("gift", "present", "party"), "#ff5c8a", "gift"),
    ("clock", "clock", ("time", "clock", "wait", "later"), "#ffd166", "clock"),
    ("mail", "mail", ("mail", "email", "message"), "#00d9ff", "mail"),
    ("search", "search", ("search", "find", "look"), "#00ff99", "search"),
    ("link", "link", ("link", "url", "connect"), "#8f5cff", "link"),
    ("node", "node", ("node", "graph", "map"), "#00d9ff", "node"),
    ("loop", "loop", ("loop", "cycle", "repeat"), "#8f5cff", "loop"),
    ("water", "water", ("water", "rain", "wave"), "#3da9fc", "wave"),
    ("leaf", "leaf", ("leaf", "plant", "grow"), "#00ff99", "leaf"),
    ("game", "game", ("game", "play", "fun"), "#ff5c8a", "dice"),
    ("robot", "robot", ("robot", "bot", "ai", "engel"), "#00d9ff", "robot"),
    ("question", "question", ("what", "why", "how", "huh"), "#ffd166", "question"),
    ("plus", "plus", ("more", "add", "plus", "new"), "#00ff99", "plus"),
    ("arrow", "arrow", ("next", "go", "forward"), "#00d9ff", "arrow"),
    ("bell", "bell", ("alert", "ping", "notify"), "#ffd166", "bell"),
    ("folder", "folder", ("folder", "file", "path"), "#ffd166", "folder"),
    ("globe", "globe", ("world", "web", "site"), "#3da9fc", "globe"),
    ("wifi", "wifi", ("wifi", "online", "net"), "#00d9ff", "wifi"),
    ("paint", "paint", ("art", "paint", "draw", "color"), "#ff5c8a", "brush"),
    ("camera", "camera", ("camera", "shot", "capture"), "#8f5cff", "camera"),
    ("mic", "mic", ("mic", "voice", "speak"), "#ff5c8a", "mic"),
    ("shield", "shield", ("guard", "shield", "protect"), "#00ff99", "shield"),
]


BACKS = ("#06101d", "#101828", "#1a0f24")


def _draw_glyph(draw: ImageDraw.ImageDraw, kind: str, accent: str) -> None:
    c = accent
    if kind == "smile":
        draw.ellipse((36, 36, 92, 92), outline=c, width=6)
        draw.ellipse((50, 54, 58, 62), fill=c)
        draw.ellipse((70, 54, 78, 62), fill=c)
        draw.arc((48, 50, 80, 86), 20, 160, fill=c, width=5)
    elif kind == "heart":
        draw.ellipse((38, 40, 68, 70), fill=c)
        draw.ellipse((60, 40, 90, 70), fill=c)
        draw.polygon([(40, 58), (64, 96), (88, 58)], fill=c)
    elif kind == "check":
        draw.line((38, 68, 56, 88), fill=c, width=10)
        draw.line((56, 88, 94, 40), fill=c, width=10)
    elif kind == "gear":
        draw.ellipse((44, 44, 84, 84), outline=c, width=8)
        for ang in range(0, 360, 45):
            rad = math.radians(ang)
            x1, y1 = 64 + 28 * math.cos(rad), 64 + 28 * math.sin(rad)
            x2, y2 = 64 + 40 * math.cos(rad), 64 + 40 * math.sin(rad)
            draw.line((x1, y1, x2, y2), fill=c, width=8)
    elif kind == "hammer":
        draw.rectangle((34, 40, 92, 54), fill=c)
        draw.rectangle((58, 50, 72, 96), fill=c)
    elif kind == "wrench":
        draw.line((40, 88, 88, 40), fill=c, width=10)
        draw.ellipse((30, 78, 52, 100), outline=c, width=6)
        draw.ellipse((76, 28, 98, 50), outline=c, width=6)
    elif kind == "terminal":
        draw.rounded_rectangle((28, 36, 100, 92), radius=8, outline=c, width=6)
        draw.line((40, 56, 56, 70), fill=c, width=5)
        draw.line((56, 70, 40, 84), fill=c, width=5)
        draw.line((62, 84, 88, 84), fill=c, width=5)
    elif kind == "eye":
        draw.ellipse((28, 48, 100, 80), outline=c, width=6)
        draw.ellipse((54, 52, 74, 76), fill=c)
        draw.ellipse((60, 58, 68, 66), fill="#06101d")
    elif kind == "spark":
        draw.polygon([(64, 24), (72, 56), (104, 64), (72, 72), (64, 104), (56, 72), (24, 64), (56, 56)], fill=c)
    elif kind == "chat":
        draw.rounded_rectangle((30, 36, 98, 80), radius=12, outline=c, width=6)
        draw.polygon([(48, 78), (44, 100), (68, 80)], fill=c)
    elif kind == "football":
        draw.ellipse((34, 44, 94, 84), fill=c)
        draw.line((64, 48, 64, 80), fill="#06101d", width=4)
        draw.line((54, 64, 74, 64), fill="#06101d", width=4)
    elif kind == "trophy":
        draw.ellipse((44, 32, 84, 72), outline=c, width=8)
        draw.rectangle((56, 70, 72, 88), fill=c)
        draw.rectangle((44, 88, 84, 98), fill=c)
    elif kind == "hex":
        pts = [(64 + 36 * math.cos(math.radians(a)), 64 + 36 * math.sin(math.radians(a))) for a in range(0, 360, 60)]
        draw.polygon(pts, outline=c, width=6)
        draw.ellipse((56, 56, 72, 72), fill=c)
    elif kind == "brain":
        draw.ellipse((36, 40, 92, 88), outline=c, width=6)
        draw.line((64, 42, 64, 86), fill=c, width=4)
        draw.arc((40, 48, 64, 80), 200, 340, fill=c, width=4)
        draw.arc((64, 48, 88, 80), 200, 340, fill=c, width=4)
    elif kind == "book":
        draw.rectangle((36, 36, 92, 96), outline=c, width=6)
        draw.line((64, 36, 64, 96), fill=c, width=5)
        draw.line((44, 52, 58, 52), fill=c, width=3)
        draw.line((70, 52, 84, 52), fill=c, width=3)
    elif kind == "phone":
        draw.rounded_rectangle((48, 28, 80, 100), radius=10, outline=c, width=6)
        draw.ellipse((58, 84, 70, 96), outline=c, width=3)
    elif kind == "cpu":
        draw.rounded_rectangle((40, 40, 88, 88), radius=6, outline=c, width=6)
        for x in (48, 64, 80):
            draw.line((x, 28, x, 40), fill=c, width=4)
            draw.line((x, 88, x, 100), fill=c, width=4)
            draw.line((28, x, 40, x), fill=c, width=4)
            draw.line((88, x, 100, x), fill=c, width=4)
    elif kind == "disk":
        draw.ellipse((36, 36, 92, 92), outline=c, width=8)
        draw.ellipse((56, 56, 72, 72), fill=c)
    elif kind == "lock":
        draw.arc((44, 32, 84, 72), 180, 0, fill=c, width=8)
        draw.rounded_rectangle((40, 56, 88, 100), radius=8, fill=c)
    elif kind == "warn":
        draw.polygon([(64, 28), (100, 96), (28, 96)], outline=c, width=6)
        draw.rectangle((60, 52, 68, 72), fill=c)
        draw.ellipse((58, 78, 70, 90), fill=c)
    elif kind == "fire":
        draw.polygon([(64, 24), (88, 72), (72, 72), (80, 100), (48, 100), (56, 72), (40, 72)], fill=c)
    elif kind == "star":
        pts = []
        for i in range(10):
            ang = math.radians(-90 + i * 36)
            r = 40 if i % 2 == 0 else 16
            pts.append((64 + r * math.cos(ang), 64 + r * math.sin(ang)))
        draw.polygon(pts, fill=c)
    elif kind == "moon":
        draw.ellipse((40, 36, 92, 88), fill=c)
        draw.ellipse((54, 36, 106, 88), fill="#06101d")
    elif kind == "sun":
        draw.ellipse((48, 48, 80, 80), fill=c)
        for ang in range(0, 360, 45):
            rad = math.radians(ang)
            draw.line(
                (64 + 22 * math.cos(rad), 64 + 22 * math.sin(rad), 64 + 44 * math.cos(rad), 64 + 44 * math.sin(rad)),
                fill=c,
                width=5,
            )
    elif kind == "mug":
        draw.rounded_rectangle((36, 40, 80, 96), radius=8, outline=c, width=6)
        draw.arc((72, 48, 100, 80), 270, 90, fill=c, width=6)
    elif kind == "note":
        draw.ellipse((40, 72, 64, 96), fill=c)
        draw.ellipse((68, 64, 92, 88), fill=c)
        draw.line((62, 36, 62, 80), fill=c, width=6)
        draw.line((90, 28, 90, 72), fill=c, width=6)
        draw.line((62, 36, 90, 28), fill=c, width=6)
    elif kind == "rocket":
        draw.polygon([(64, 24), (84, 72), (64, 60), (44, 72)], fill=c)
        draw.polygon([(52, 72), (64, 104), (76, 72)], fill=c)
    elif kind == "home":
        draw.polygon([(64, 28), (100, 64), (28, 64)], fill=c)
        draw.rectangle((44, 64, 84, 100), fill=c)
    elif kind == "gift":
        draw.rectangle((36, 56, 92, 100), outline=c, width=6)
        draw.rectangle((36, 40, 92, 58), fill=c)
        draw.line((64, 40, 64, 100), fill=c, width=6)
    elif kind == "clock":
        draw.ellipse((32, 32, 96, 96), outline=c, width=6)
        draw.line((64, 64, 64, 44), fill=c, width=5)
        draw.line((64, 64, 82, 64), fill=c, width=5)
    elif kind == "mail":
        draw.rectangle((28, 44, 100, 88), outline=c, width=6)
        draw.polygon([(28, 44), (64, 72), (100, 44)], outline=c, width=5)
    elif kind == "search":
        draw.ellipse((32, 32, 84, 84), outline=c, width=8)
        draw.line((76, 76, 100, 100), fill=c, width=10)
    elif kind == "link":
        draw.arc((28, 44, 76, 84), 200, 340, fill=c, width=8)
        draw.arc((52, 44, 100, 84), 20, 160, fill=c, width=8)
    elif kind == "node":
        draw.ellipse((24, 24, 52, 52), fill=c)
        draw.ellipse((76, 24, 104, 52), fill=c)
        draw.ellipse((50, 76, 78, 104), fill=c)
        draw.line((38, 38, 90, 38), fill=c, width=5)
        draw.line((38, 38, 64, 90), fill=c, width=5)
        draw.line((90, 38, 64, 90), fill=c, width=5)
    elif kind == "loop":
        draw.arc((32, 32, 96, 96), 30, 300, fill=c, width=10)
        draw.polygon([(92, 36), (108, 52), (80, 56)], fill=c)
    elif kind == "wave":
        draw.arc((20, 48, 68, 80), 200, 340, fill=c, width=8)
        draw.arc((60, 48, 108, 80), 200, 340, fill=c, width=8)
    elif kind == "leaf":
        draw.ellipse((40, 28, 88, 100), fill=c)
        draw.line((64, 36, 64, 96), fill="#06101d", width=4)
    elif kind == "dice":
        draw.rounded_rectangle((36, 36, 92, 92), radius=12, outline=c, width=6)
        for cx, cy in ((52, 52), (76, 52), (64, 64), (52, 76), (76, 76)):
            draw.ellipse((cx - 5, cy - 5, cx + 5, cy + 5), fill=c)
    elif kind == "robot":
        draw.rounded_rectangle((36, 44, 92, 96), radius=10, outline=c, width=6)
        draw.rectangle((52, 28, 76, 44), fill=c)
        draw.ellipse((48, 56, 60, 68), fill=c)
        draw.ellipse((68, 56, 80, 68), fill=c)
    elif kind == "question":
        draw.ellipse((44, 28, 84, 68), outline=c, width=8)
        draw.line((64, 64, 64, 80), fill=c, width=8)
        draw.ellipse((58, 88, 70, 100), fill=c)
    elif kind == "plus":
        draw.rectangle((56, 32, 72, 96), fill=c)
        draw.rectangle((32, 56, 96, 72), fill=c)
    elif kind == "arrow":
        draw.polygon([(28, 64), (76, 36), (76, 52), (108, 52), (108, 76), (76, 76), (76, 92)], fill=c)
    elif kind == "bell":
        draw.pieslice((36, 32, 92, 92), 200, 340, fill=c)
        draw.ellipse((56, 88, 72, 104), fill=c)
    elif kind == "folder":
        draw.polygon([(28, 48), (28, 40),  (56, 40), (64, 48), (100, 48), (100, 96), (28, 96)], fill=c)
    elif kind == "globe":
        draw.ellipse((32, 32, 96, 96), outline=c, width=6)
        draw.ellipse((52, 32, 76, 96), outline=c, width=4)
        draw.arc((32, 48, 96, 80), 0, 180, fill=c, width=4)
    elif kind == "wifi":
        draw.arc((28, 40, 100, 100), 200, 340, fill=c, width=8)
        draw.arc((44, 56, 84, 96), 200, 340, fill=c, width=8)
        draw.ellipse((58, 80, 70, 92), fill=c)
    elif kind == "brush":
        draw.polygon([(40, 88), (56, 40), (72, 44), (56, 96)], fill=c)
        draw.ellipse((32, 80, 56, 104), fill=c)
    elif kind == "camera":
        draw.rounded_rectangle((28, 48, 100, 96), radius=8, fill=c)
        draw.ellipse((52, 56, 76, 80), fill="#06101d")
        draw.rectangle((48, 36, 68, 48), fill=c)
    elif kind == "mic":
        draw.rounded_rectangle((52, 28, 76, 72), radius=12, fill=c)
        draw.arc((40, 48, 88, 96), 0, 180, fill=c, width=8)
        draw.line((64, 96, 64, 108), fill=c, width=6)
    elif kind == "shield":
        draw.polygon([(64, 24), (100, 44), (92, 92), (64, 108), (36, 92), (28, 44)], fill=c)
    else:
        draw.ellipse((44, 44, 84, 84), fill=c)


def render_icon(kind: str, accent: str, back: str, frame: str) -> Image.Image:
    image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    if frame == "round":
        draw.rounded_rectangle((4, 4, SIZE - 5, SIZE - 5), radius=36, fill=back)
    elif frame == "hex":
        pts = [
            (SIZE / 2 + 60 * math.cos(math.radians(a)), SIZE / 2 + 60 * math.sin(math.radians(a)))
            for a in range(30, 360, 60)
        ]
        draw.polygon(pts, fill=back)
    else:
        draw.rounded_rectangle((4, 4, SIZE - 5, SIZE - 5), radius=28, fill=back, outline=accent, width=5)
    _draw_glyph(draw, kind, accent)
    return image


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    items: list[dict[str, object]] = []
    frames = ("square", "round", "hex")
    for topic, stem, triggers, accent, kind in TOPICS:
        for index, frame in enumerate(frames):
            back = BACKS[index % len(BACKS)]
            name = f"{stem}_{frame}.png"
            path = OUT / name
            render_icon(kind, accent, back, frame).save(path, format="PNG")
            items.append(
                {
                    "id": f"{topic}_{frame}",
                    "topic": topic,
                    "path": f"runtime/favicons/library/{name}",
                    "file": name,
                    "triggers": list(triggers) + [stem, topic, frame],
                    "kind": kind,
                }
            )
    manifest = {
        "schema": "engel_favicon_library_v1",
        "count": len(items),
        "size_px": SIZE,
        "network": False,
        "items": items,
    }
    (OUT / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(items)} favicons to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
