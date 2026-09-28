from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
BRAND_DIR = ROOT / "assets" / "branding" / "final"
SOURCE_ICON = BRAND_DIR / "engel_icon_final.ico"
PNG_PATH = BRAND_DIR / "engel_connection_doctor_icon.png"
ICO_PATH = BRAND_DIR / "engel_connection_doctor_icon.ico"


def draw_cross(draw: ImageDraw.ImageDraw, cx: int, cy: int, arm: int, thick: int, fill: str) -> None:
    radius = max(1, thick // 2)
    draw.rounded_rectangle((cx - thick, cy - arm, cx + thick, cy + arm), radius=radius, fill=fill)
    draw.rounded_rectangle((cx - arm, cy - thick, cx + arm, cy + thick), radius=radius, fill=fill)


def base_icon(size: int) -> Image.Image:
    source = Image.open(SOURCE_ICON).convert("RGBA")
    return source.resize((size, size), Image.Resampling.LANCZOS)


def make_icon(size: int) -> Image.Image:
    scale = size / 256
    image = base_icon(size)

    badge_box = tuple(int(v * scale) for v in (126, 124, 238, 236))
    shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.ellipse(badge_box, fill=(0, 0, 0, 180))
    shadow = shadow.filter(ImageFilter.GaussianBlur(max(2, int(7 * scale))))
    image.alpha_composite(shadow)

    draw = ImageDraw.Draw(image)
    draw.ellipse(badge_box, fill="#061321", outline="#18f28f", width=max(2, int(6 * scale)))
    draw_cross(draw, int(182 * scale), int(180 * scale), int(34 * scale), int(12 * scale), "#18f28f")

    small_box = tuple(int(v * scale) for v in (188, 36, 232, 80))
    draw.ellipse(small_box, fill="#00e5ff", outline="#d8fbff", width=max(1, int(2 * scale)))
    draw_cross(draw, int(210 * scale), int(58 * scale), int(12 * scale), int(4 * scale), "#071326")

    return image


def main() -> int:
    if not SOURCE_ICON.is_file():
        raise FileNotFoundError(f"Missing Engel final icon: {SOURCE_ICON}")
    BRAND_DIR.mkdir(parents=True, exist_ok=True)
    base = make_icon(256)
    base.save(PNG_PATH)
    sizes = [make_icon(size) for size in (256, 128, 64, 48, 32, 16)]
    sizes[0].save(ICO_PATH, sizes=[(img.width, img.height) for img in sizes])
    print(PNG_PATH)
    print(ICO_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
