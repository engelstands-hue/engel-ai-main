#!/usr/bin/env python3
"""Export an Engel real-user input choice map JSON to a readable PDF."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ENGEL_GREEN = colors.HexColor("#00ff92")
ENGEL_BLUE = colors.HexColor("#53b7ff")
ENGEL_BG = colors.HexColor("#060910")
ENGEL_PANEL = colors.HexColor("#0f1320")
ENGEL_LINE = colors.HexColor("#263045")
ENGEL_TEXT = colors.HexColor("#e8fff6")
ENGEL_MUTED = colors.HexColor("#9aa6bb")


def _text(value: Any, fallback: str = "") -> str:
    cleaned = str(value if value is not None else fallback).replace("\r", " ").strip()
    return cleaned or fallback


def _short(value: Any, limit: int = 76) -> str:
    cleaned = _text(value)
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(0, limit - 3)].rstrip() + "..."


def _kv_counts(value: dict[str, Any] | None) -> str:
    if not value:
        return "none"
    return ", ".join(f"{key}={val}" for key, val in sorted(value.items()))


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "EngelTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=26,
            textColor=ENGEL_GREEN,
            spaceAfter=10,
        ),
        "h2": ParagraphStyle(
            "EngelH2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=ENGEL_GREEN,
            spaceBefore=10,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "EngelBody",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            textColor=ENGEL_TEXT,
            alignment=TA_LEFT,
        ),
        "small": ParagraphStyle(
            "EngelSmall",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=9.5,
            textColor=ENGEL_MUTED,
        ),
        "cell": ParagraphStyle(
            "EngelCell",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=6.7,
            leading=8.2,
            textColor=ENGEL_TEXT,
        ),
        "head": ParagraphStyle(
            "EngelHead",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=6.9,
            leading=8.5,
            textColor=ENGEL_GREEN,
        ),
        "mono": ParagraphStyle(
            "EngelMono",
            parent=base["BodyText"],
            fontName="Courier",
            fontSize=6.7,
            leading=8.5,
            textColor=ENGEL_TEXT,
        ),
    }


def _p(text: Any, style: ParagraphStyle) -> Paragraph:
    escaped = (
        _text(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br/>")
    )
    return Paragraph(escaped, style)


def _summary_table(summary: dict[str, Any], styles: dict[str, ParagraphStyle]) -> Table:
    rows = [
        [_p("Metric", styles["head"]), _p("Value", styles["head"])],
        [_p("Jobs", styles["cell"]), _p(summary.get("jobs", 0), styles["cell"])],
        [_p("Workers", styles["cell"]), _p(_kv_counts(summary.get("workers")), styles["cell"])],
        [_p("Artifacts", styles["cell"]), _p(_kv_counts(summary.get("artifacts")), styles["cell"])],
        [_p("Job types", styles["cell"]), _p(_kv_counts(summary.get("job_types")), styles["cell"])],
    ]
    table = Table(rows, colWidths=[1.3 * inch, 7.6 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
                ("BACKGROUND", (0, 1), (-1, -1), ENGEL_PANEL),
                ("BOX", (0, 0), (-1, -1), 0.6, ENGEL_LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, ENGEL_LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def _selection_map(routes: list[dict[str, Any]], styles: dict[str, ParagraphStyle]) -> Table:
    by_worker: dict[str, dict[str, Any]] = {}
    for route in routes:
        worker = _text(route.get("worker"), "unknown")
        bucket = by_worker.setdefault(
            worker,
            {
                "device": _text(route.get("device"), "unknown device"),
                "agent": _text(route.get("agent"), "unknown agent"),
                "skill": _text(route.get("skill"), "unknown skill"),
                "artifacts": {},
                "count": 0,
            },
        )
        bucket["count"] += 1
        artifact = _text(route.get("artifact"), "unknown")
        bucket["artifacts"][artifact] = bucket["artifacts"].get(artifact, 0) + 1

    rows = [[_p("Worker", styles["head"]), _p("Device -> agent -> skill", styles["head"]), _p("Chosen for", styles["head"])]]
    for worker, bucket in sorted(by_worker.items()):
        route_line = f"{bucket['device']} -> {bucket['agent']} -> {bucket['skill']}"
        rows.append(
            [
                _p(f"{worker}\n{bucket['count']} jobs", styles["cell"]),
                _p(route_line, styles["cell"]),
                _p(_kv_counts(bucket["artifacts"]), styles["cell"]),
            ]
        )
    table = Table(rows, colWidths=[1.55 * inch, 5.1 * inch, 2.25 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
                ("BACKGROUND", (0, 1), (-1, -1), ENGEL_PANEL),
                ("BOX", (0, 0), (-1, -1), 0.6, ENGEL_LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, ENGEL_LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def _route_table(routes: list[dict[str, Any]], styles: dict[str, ParagraphStyle]) -> Table:
    rows = [
        [
            _p("#", styles["head"]),
            _p("User prompt", styles["head"]),
            _p("Job type", styles["head"]),
            _p("Device", styles["head"]),
            _p("Agent / skill", styles["head"]),
            _p("Result", styles["head"]),
        ]
    ]
    for route in routes:
        result = f"{_text(route.get('artifact'), 'unknown')} / {_text(route.get('worker'), 'unknown')} / {_text(route.get('transport'), 'unknown')}"
        rows.append(
            [
                _p(route.get("index", ""), styles["cell"]),
                _p(_short(route.get("prompt"), 100), styles["cell"]),
                _p(route.get("job_type", ""), styles["cell"]),
                _p(route.get("device", ""), styles["cell"]),
                _p(f"{route.get('agent', '')}\n{route.get('skill', '')}", styles["cell"]),
                _p(result, styles["cell"]),
            ]
        )
    table = Table(rows, repeatRows=1, colWidths=[0.35 * inch, 2.55 * inch, 1.05 * inch, 2.05 * inch, 1.75 * inch, 1.15 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
                ("BACKGROUND", (0, 1), (-1, -1), ENGEL_PANEL),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#0c101b"), ENGEL_PANEL]),
                ("BOX", (0, 0), (-1, -1), 0.6, ENGEL_LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, ENGEL_LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _station_details(routes: list[dict[str, Any]], styles: dict[str, ParagraphStyle]) -> list[Any]:
    story: list[Any] = []
    story.append(_p("Full Station Routes", styles["h2"]))
    for route in routes:
        lines = list(route.get("station_routes") or [])
        results = list(route.get("station_results") or [])
        body = [
            f"{route.get('index')}. {_short(route.get('prompt'), 120)}",
            f"Primary: {_text(route.get('device'))} -> {_text(route.get('agent'))} -> {_text(route.get('skill'))}",
        ]
        if lines:
            body.append("Station routes:")
            body.extend(f"- {line}" for line in lines)
        if results:
            body.append("Station results:")
            body.extend(f"- {line}" for line in results)
        story.append(_p("\n".join(body), styles["mono"]))
        story.append(Spacer(1, 0.08 * inch))
    return story


def _draw_page(canvas: Any, doc: SimpleDocTemplate) -> None:
    canvas.saveState()
    canvas.setFillColor(ENGEL_BG)
    canvas.rect(0, 0, doc.pagesize[0], doc.pagesize[1], fill=1, stroke=0)
    canvas.setStrokeColor(ENGEL_GREEN)
    canvas.setLineWidth(1)
    canvas.line(doc.leftMargin, doc.pagesize[1] - 0.42 * inch, doc.pagesize[0] - doc.rightMargin, doc.pagesize[1] - 0.42 * inch)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(ENGEL_MUTED)
    canvas.drawRightString(doc.pagesize[0] - doc.rightMargin, 0.28 * inch, f"Engel AI choice map | page {doc.page}")
    canvas.restoreState()


def export_pdf(input_path: Path, output_path: Path | None = None) -> Path:
    data = json.loads(input_path.read_text(encoding="utf-8"))
    routes = list(data.get("routes") or [])
    output = output_path or input_path.with_suffix(".pdf")
    styles = _styles()

    doc = SimpleDocTemplate(
        str(output),
        pagesize=landscape(letter),
        rightMargin=0.45 * inch,
        leftMargin=0.45 * inch,
        topMargin=0.58 * inch,
        bottomMargin=0.45 * inch,
        title="Engel Real User Input Choice Map",
        author="Engel AI",
    )

    story: list[Any] = [
        _p("Engel Real User Input Choice Map", styles["title"]),
        _p(
            "Plain Engel AI UI input -> Agent Meeting Room auto-select -> device worker -> artifact result.",
            styles["body"],
        ),
        Spacer(1, 0.08 * inch),
        _p(f"Source receipt: {data.get('source_receipt', '')}", styles["small"]),
        _p(f"Source transcript: {data.get('source_transcript', '')}", styles["small"]),
        Spacer(1, 0.12 * inch),
        _p("Summary", styles["h2"]),
        _summary_table(dict(data.get("summary") or {}), styles),
        Spacer(1, 0.12 * inch),
        _p("Device Choice Map", styles["h2"]),
        _selection_map(routes, styles),
        Spacer(1, 0.12 * inch),
        _p("Real Choices By Prompt", styles["h2"]),
        _route_table(routes, styles),
        PageBreak(),
    ]
    story.extend(_station_details(routes, styles))

    doc.build(story, onFirstPage=_draw_page, onLaterPages=_draw_page)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("map_json", type=Path)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    output = export_pdf(args.map_json, args.output)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
