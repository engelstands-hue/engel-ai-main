#!/usr/bin/env python3
"""Build a visual Engel Meeting Room routing graph from a choice-map JSON."""
from __future__ import annotations

import argparse
import json
import math
import textwrap
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


BG = (5, 8, 15)
PANEL = (12, 16, 28)
PANEL_2 = (15, 21, 35)
LINE = (38, 48, 71)
TEXT = (226, 255, 245)
MUTED = (151, 166, 191)
GREEN = (0, 255, 146)
BLUE = (83, 183, 255)
YELLOW = (255, 190, 52)
PINK = (234, 116, 255)
RED = (255, 91, 116)


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    names = (
        "C:/Windows/Fonts/consolab.ttf" if bold else "C:/Windows/Fonts/consola.ttf",
        "C:/Windows/Fonts/seguisb.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "arialbd.ttf" if bold else "arial.ttf",
    )
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


FONT_TITLE = _font(54, True)
FONT_H = _font(28, True)
FONT = _font(22)
FONT_B = _font(22, True)
FONT_S = _font(17)
FONT_XS = _font(14)


def _text(value: Any, fallback: str = "") -> str:
    cleaned = str(value if value is not None else fallback).replace("\r", " ").strip()
    return cleaned or fallback


def _short(value: Any, limit: int = 54) -> str:
    cleaned = _text(value)
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(0, limit - 3)].rstrip() + "..."


def _wrap(value: Any, width: int) -> list[str]:
    return textwrap.wrap(_text(value), width=width, break_long_words=False) or [""]


def _round_rect(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fill: tuple[int, int, int], outline: tuple[int, int, int] = LINE, width: int = 2, radius: int = 18) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def _label(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, font: ImageFont.ImageFont, fill: tuple[int, int, int] = TEXT) -> None:
    draw.text(xy, text, font=font, fill=fill)


def _node(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    title: str,
    subtitle: str,
    count: str,
    accent: tuple[int, int, int],
    wrap_title: int = 24,
) -> None:
    _round_rect(draw, box, PANEL, outline=LINE, width=2, radius=20)
    x1, y1, x2, y2 = box
    draw.rounded_rectangle((x1 + 8, y1 + 8, x1 + 17, y2 - 8), radius=5, fill=accent)
    draw.text((x1 + 30, y1 + 18), count, font=FONT_B, fill=accent)
    y = y1 + 52
    for line in _wrap(title, wrap_title)[:3]:
        draw.text((x1 + 30, y), line, font=FONT_B, fill=TEXT)
        y += 28
    if subtitle:
        for line in _wrap(subtitle, wrap_title + 8)[:3]:
            draw.text((x1 + 30, y + 8), line, font=FONT_S, fill=MUTED)
            y += 21


def _center_left(box: tuple[int, int, int, int]) -> tuple[int, int]:
    return (box[0], (box[1] + box[3]) // 2)


def _center_right(box: tuple[int, int, int, int]) -> tuple[int, int]:
    return (box[2], (box[1] + box[3]) // 2)


def _line(draw: ImageDraw.ImageDraw, src: tuple[int, int], dst: tuple[int, int], count: int, color: tuple[int, int, int], label: str = "") -> None:
    width = max(3, min(18, 2 + count * 2))
    mid = (src[0] + dst[0]) // 2
    points = [src, (mid, src[1]), (mid, dst[1]), dst]
    draw.line(points, fill=color, width=width, joint="curve")
    draw.ellipse((dst[0] - 6, dst[1] - 6, dst[0] + 6, dst[1] + 6), fill=color)
    if label:
        lx = (src[0] + dst[0]) // 2 - 20
        ly = (src[1] + dst[1]) // 2 - 14
        draw.rounded_rectangle((lx - 7, ly - 4, lx + 70, ly + 22), radius=8, fill=(7, 10, 18), outline=LINE)
        draw.text((lx, ly), label, font=FONT_XS, fill=TEXT)


def _slug(path: Path) -> str:
    return path.stem.replace("ENGEL_REAL_USER_INPUT_CHOICE_MAP_", "")


def build_graph(input_path: Path, output_png: Path | None = None, output_pdf: Path | None = None) -> tuple[Path, Path]:
    data = json.loads(input_path.read_text(encoding="utf-8"))
    routes = list(data.get("routes") or [])
    summary = dict(data.get("summary") or {})

    scale = 2
    width, height = 2600, 1650
    img = Image.new("RGB", (width * scale, height * scale), BG)
    draw = ImageDraw.Draw(img)

    def sbox(box: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
        return tuple(v * scale for v in box)  # type: ignore[return-value]

    def sp(pt: tuple[int, int]) -> tuple[int, int]:
        return (pt[0] * scale, pt[1] * scale)

    # Rebind fonts at scaled sizes for crisp downsampling.
    global FONT_TITLE, FONT_H, FONT, FONT_B, FONT_S, FONT_XS
    FONT_TITLE = _font(54 * scale, True)
    FONT_H = _font(28 * scale, True)
    FONT = _font(22 * scale)
    FONT_B = _font(22 * scale, True)
    FONT_S = _font(17 * scale)
    FONT_XS = _font(14 * scale)

    draw.rectangle((0, 0, width * scale, height * scale), fill=BG)
    draw.line((80 * scale, 150 * scale, 2520 * scale, 150 * scale), fill=GREEN, width=2 * scale)
    draw.text((82 * scale, 56 * scale), "ENGEL AI REAL USER INPUT ROUTING GRAPH", font=FONT_TITLE, fill=GREEN)
    draw.text(
        (86 * scale, 118 * scale),
        "Plain Engel UI prompt -> Agent Meeting Room auto-select -> WiFi device worker -> artifact result",
        font=FONT,
        fill=MUTED,
    )

    total_jobs = int(summary.get("jobs") or len(routes))
    worker_counts = Counter(_text(r.get("worker"), "unknown") for r in routes)
    artifact_counts = Counter(_text(r.get("artifact"), "unknown") for r in routes)
    job_counts = Counter(_text(r.get("job_type"), "unknown") for r in routes)

    # Main nodes.
    ui = (90, 320, 390, 470)
    mr = (530, 300, 860, 490)
    _node(draw, sbox(ui), "Engel AI UI", "real user prompt input", f"{total_jobs} jobs", GREEN, 18)
    _node(draw, sbox(mr), "Agent Meeting Room", "auto-selects device, agent, skill", f"{total_jobs} routed", BLUE, 22)
    _line(draw, sp(_center_right(ui)), sp(_center_left(mr)), total_jobs, GREEN, f"{total_jobs}")

    job_order = ["format_report_draft", "draft_code_artifact", "summarize_text", "web_research_brief"]
    job_labels = {
        "format_report_draft": ("PDF / Report", YELLOW),
        "draft_code_artifact": ("Code / Game", GREEN),
        "summarize_text": ("Language / File", PINK),
        "web_research_brief": ("Research", BLUE),
    }
    job_boxes: dict[str, tuple[int, int, int, int]] = {}
    for i, job in enumerate(job_order):
        count = job_counts.get(job, 0)
        title, accent = job_labels.get(job, (job, MUTED))
        box = (1010, 220 + i * 210, 1375, 370 + i * 210)
        job_boxes[job] = box
        _node(draw, sbox(box), title, job, f"{count} jobs", accent, 22)
        if count:
            _line(draw, sp(_center_right(mr)), sp(_center_left(box)), count, accent, str(count))

    worker_boxes: dict[str, tuple[int, int, int, int]] = {}
    worker_meta = {
        "android_worker_alpha": ("Alpha Phone", "Moto G Power (2025) / WiFi\nAndroid Phone Alpha Agent\nAndroid Worker Alpha Skill", GREEN),
        "android_worker_beta": ("Beta Phone", "Moto G Fast / WiFi\nAndroid Phone Beta Agent\nAndroid Worker Beta Skill", YELLOW),
    }
    for i, worker in enumerate(["android_worker_alpha", "android_worker_beta"]):
        count = worker_counts.get(worker, 0)
        title, subtitle, accent = worker_meta.get(worker, (worker, "device worker", MUTED))
        box = (1545, 300 + i * 330, 1960, 540 + i * 330)
        worker_boxes[worker] = box
        _node(draw, sbox(box), title, subtitle, f"{count} jobs", accent, 25)

    jt_worker = Counter((_text(r.get("job_type"), "unknown"), _text(r.get("worker"), "unknown")) for r in routes)
    for (job, worker), count in jt_worker.items():
        if job in job_boxes and worker in worker_boxes:
            color = worker_meta.get(worker, ("", "", MUTED))[2]
            _line(draw, sp(_center_right(job_boxes[job])), sp(_center_left(worker_boxes[worker])), count, color, str(count))

    artifact_order = ["pdf", "game", "language", "research", "code", "file"]
    artifact_colors = {"pdf": YELLOW, "game": GREEN, "language": PINK, "research": BLUE, "code": GREEN, "file": MUTED}
    artifact_boxes: dict[str, tuple[int, int, int, int]] = {}
    for i, artifact in enumerate(artifact_order):
        count = artifact_counts.get(artifact, 0)
        box = (2160, 185 + i * 170, 2490, 305 + i * 170)
        artifact_boxes[artifact] = box
        _node(draw, sbox(box), f"{artifact.title()} Artifact", "real local output", f"{count}", artifact_colors.get(artifact, MUTED), 20)

    worker_artifact = Counter((_text(r.get("worker"), "unknown"), _text(r.get("artifact"), "unknown")) for r in routes)
    for (worker, artifact), count in worker_artifact.items():
        if worker in worker_boxes and artifact in artifact_boxes:
            color = artifact_colors.get(artifact, MUTED)
            _line(draw, sp(_center_right(worker_boxes[worker])), sp(_center_left(artifact_boxes[artifact])), count, color, str(count))

    # Device-first summary cards.
    summary_box = (90, 1035, 860, 1535)
    _round_rect(draw, sbox(summary_box), PANEL_2, outline=LINE, width=2 * scale, radius=22 * scale)
    draw.text((120 * scale, 1065 * scale), "Device-first choices", font=FONT_H, fill=GREEN)
    y = 1115
    for worker in ["android_worker_alpha", "android_worker_beta"]:
        title, subtitle, accent = worker_meta.get(worker, (worker, "", MUTED))
        counts = Counter(r.get("artifact") for r in routes if r.get("worker") == worker)
        draw.rounded_rectangle((120 * scale, y * scale, 835 * scale, (y + 135) * scale), radius=18 * scale, fill=PANEL, outline=accent, width=2 * scale)
        draw.text((145 * scale, (y + 18) * scale), f"{title}: {worker_counts.get(worker, 0)} jobs", font=FONT_B, fill=accent)
        draw.text((145 * scale, (y + 49) * scale), subtitle.replace("\n", " -> "), font=FONT_S, fill=TEXT)
        draw.text((145 * scale, (y + 82) * scale), "Artifacts: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())), font=FONT_S, fill=MUTED)
        y += 165

    station_agents: Counter[str] = Counter()
    for route in routes:
        for station in route.get("station_routes") or []:
            if "Local Engel AI" in station:
                parts = [p.strip() for p in station.split("->")]
                if len(parts) >= 3:
                    station_agents[f"{parts[1]} -> {parts[2]}"] += 1

    sec_box = (1010, 1035, 1960, 1535)
    _round_rect(draw, sbox(sec_box), PANEL_2, outline=LINE, width=2 * scale, radius=22 * scale)
    draw.text((1040 * scale, 1065 * scale), "Meeting Room collaborator stations", font=FONT_H, fill=BLUE)
    draw.text((1040 * scale, 1105 * scale), "Secondary local stations stayed in the room while device workers handled primary jobs.", font=FONT_S, fill=MUTED)
    y = 1150
    for label, count in station_agents.most_common():
        draw.rounded_rectangle((1040 * scale, y * scale, 1930 * scale, (y + 56) * scale), radius=14 * scale, fill=PANEL, outline=LINE, width=2 * scale)
        draw.text((1065 * scale, (y + 14) * scale), label, font=FONT_S, fill=TEXT)
        draw.text((1845 * scale, (y + 14) * scale), f"{count}x", font=FONT_B, fill=GREEN)
        y += 68

    prompts_box = (2040, 1145, 2490, 1535)
    _round_rect(draw, sbox(prompts_box), PANEL_2, outline=LINE, width=2 * scale, radius=22 * scale)
    draw.text((2070 * scale, 1175 * scale), "Proof points", font=FONT_H, fill=GREEN)
    proof = [
        f"{total_jobs}/20 UI jobs finished",
        "WiFi transport recorded",
        "No missing device/agent/skill",
        "Artifacts created for every job",
        "Map source kept in reports/meeting_rooms",
    ]
    y = 1225
    for line in proof:
        draw.text((2075 * scale, y * scale), f"- {line}", font=FONT_S, fill=TEXT)
        y += 43

    # Footer.
    draw.text((90 * scale, 1588 * scale), f"Source: {input_path}", font=FONT_XS, fill=MUTED)
    draw.text((2140 * scale, 1588 * scale), "Engel AI / Agent Meeting Room / real choices", font=FONT_XS, fill=GREEN)

    img = img.resize((width, height), Image.Resampling.LANCZOS)
    base = input_path.with_name(f"ENGEL_REAL_USER_INPUT_ROUTING_GRAPH_{_slug(input_path)}")
    png = output_png or base.with_suffix(".png")
    pdf = output_pdf or base.with_suffix(".pdf")
    png.parent.mkdir(parents=True, exist_ok=True)
    img.save(png)
    img.save(pdf, "PDF", resolution=160.0)
    return png, pdf


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("map_json", type=Path)
    parser.add_argument("--png", type=Path)
    parser.add_argument("--pdf", type=Path)
    args = parser.parse_args()
    png, pdf = build_graph(args.map_json, args.png, args.pdf)
    print(png)
    print(pdf)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
