#!/usr/bin/env python3
"""Generate an Engel true-local-data score chart.

This module treats project files as untrusted data. It extracts only explicit
numeric counts/scores from bounded local reports and memory files, then renders
a report-only PNG chart. It never executes file contents.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import struct
import sys
import time
import zlib
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MAX_FILES_INSPECTED = 500
MAX_BYTES_PER_FILE = 2 * 1024 * 1024
MIN_RECORDS_FOR_FULL_CHART = 20
MAX_RECORDS_PER_FILE = 50
ALLOWED_EXTENSIONS = {".json", ".jsonl", ".md"}
ALLOWED_TOP_LEVEL_DIRS = ("reports", "memory")
SKIP_DIR_NAMES = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    "live",
    "staging",
    "backups",
    "build",
    "dist",
    ".dart_tool",
    ".idea",
    ".vscode",
}
REPORT_PATH = Path("reports") / "codex_bridge" / "ENGEL_TRUE_DATA_SCORE_CHART.md"
CHART_DIR = Path("reports") / "charts"
PNG_PATH = CHART_DIR / "engel_true_data_score_chart.png"
DATA_JSON_PATH = CHART_DIR / "engel_true_data_score_chart_data.json"
RECEIPT_PATH = CHART_DIR / "engel_true_data_score_chart_receipt.md"
GENERATOR_PATH = Path("tools") / "engel_true_data_score_chart.py"
ARTIFACT_NAME = "engel_true_data_score_chart.png"
METRIC_NAME = "normalized observed sum score vs expected sum score over normalized arc length"
RUN_STATUS = "generated from true-data-only run"

SCORE_FIELD_NAMES = {
    "score",
    "sum_score",
    "quality_score",
    "safety_score",
    "observed_score",
    "normalized_score",
}
COUNT_FIELD_NAMES = {
    "pass_count",
    "passed",
    "failed",
    "failure_count",
    "risk_count",
    "finding_count",
    "candidate_count",
    "lesson_candidate_count",
    "memory_candidate_count",
    "files_inspected",
    "true_numeric_records",
}


@dataclass
class TrueNumericRecord:
    source_path: str
    source_kind: str
    timestamp: str
    score_value: float
    extraction_kind: str
    status_flags: list[str]
    details: dict[str, Any]


@dataclass
class ChartRunSummary:
    project_root: str
    files_inspected: int
    true_numeric_records_found: int
    source_categories_used: dict[str, int]
    arc_length_mode: str
    chart_created: bool
    insufficient_data: bool
    chart_path: str
    data_json_path: str
    report_path: str
    receipt_path: str
    renderer: str
    artifact: str
    source_data: str
    generator: str
    build_hash_sha256: str
    chart_hash_sha256: str
    data_hash_sha256: str
    generator_hash_sha256: str
    receipt_hash_sha256: str
    timestamp_utc: str
    metric: str
    status: str
    safety_boundaries: list[str]


def resolve_project_root(root_arg: str | None) -> Path:
    if root_arg:
        return Path(root_arg).resolve()
    return Path(__file__).resolve().parents[1]


def is_within(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def discover_candidate_files(project_root: Path) -> list[Path]:
    files: list[Path] = []
    stack = [project_root / name for name in ALLOWED_TOP_LEVEL_DIRS]
    while stack and len(files) < MAX_FILES_INSPECTED:
        directory = stack.pop()
        if not directory.exists() or not directory.is_dir():
            continue
        try:
            entries = sorted(os.scandir(directory), key=lambda item: item.name.lower())
        except OSError:
            continue
        for entry in entries:
            path = Path(entry.path)
            if entry.is_dir(follow_symlinks=False):
                if entry.name.lower() in SKIP_DIR_NAMES:
                    continue
                stack.append(path)
                continue
            if not entry.is_file(follow_symlinks=False):
                continue
            if path.suffix.lower() not in ALLOWED_EXTENSIONS:
                continue
            try:
                if path.stat().st_size > MAX_BYTES_PER_FILE:
                    continue
            except OSError:
                continue
            files.append(path)
            if len(files) >= MAX_FILES_INSPECTED:
                break
    return files


def read_text_bounded(path: Path) -> str | None:
    try:
        if path.stat().st_size > MAX_BYTES_PER_FILE:
            return None
        raw = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in raw[:4096]:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return raw.decode("utf-8", errors="replace")
        except Exception:
            return None


def file_timestamp(path: Path, text: str | None = None) -> datetime:
    if text:
        parsed = timestamp_from_text(text)
        if parsed is not None:
            return parsed
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    except OSError:
        return datetime.fromtimestamp(0, tz=timezone.utc)


def timestamp_from_text(text: str) -> datetime | None:
    patterns = [
        r"(20\d{6}T\d{6}Z)",
        r"(20\d{2}-\d{2}-\d{2}[T ][0-2]\d:[0-5]\d:[0-5]\dZ?)",
        r"(20\d{2}-\d{2}-\d{2})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        value = match.group(1)
        for fmt in ("%Y%m%dT%H%M%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(value.rstrip("Z"), fmt.rstrip("Z")).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
    return None


def source_kind(path: Path, project_root: Path) -> str:
    rel = path.resolve().relative_to(project_root.resolve())
    if len(rel.parts) >= 2:
        return f"{rel.parts[0]}/{rel.parts[1]}"
    return rel.parts[0] if rel.parts else "unknown"


def extract_records_from_file(path: Path, project_root: Path) -> list[TrueNumericRecord]:
    text = read_text_bounded(path)
    if text is None:
        return []
    timestamp = file_timestamp(path, text)
    kind = source_kind(path, project_root)
    if path.suffix.lower() == ".json":
        return extract_json_records(path, project_root, text, timestamp, kind)
    if path.suffix.lower() == ".jsonl":
        return extract_jsonl_records(path, project_root, text, timestamp, kind)
    return extract_markdown_records(path, project_root, text, timestamp, kind)


def record(
    path: Path,
    project_root: Path,
    kind: str,
    timestamp: datetime,
    score_value: float,
    extraction_kind: str,
    details: dict[str, Any],
    status_flags: list[str] | None = None,
) -> TrueNumericRecord | None:
    if not math.isfinite(score_value):
        return None
    if score_value < 0:
        score_value = 0.0
    rel = str(path.resolve().relative_to(project_root.resolve()))
    return TrueNumericRecord(
        source_path=rel,
        source_kind=kind,
        timestamp=timestamp.isoformat(),
        score_value=float(score_value),
        extraction_kind=extraction_kind,
        status_flags=status_flags or [],
        details=details,
    )


def extract_json_records(
    path: Path,
    project_root: Path,
    text: str,
    timestamp: datetime,
    kind: str,
) -> list[TrueNumericRecord]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return extract_markdown_records(path, project_root, text, timestamp, kind)
    records: list[TrueNumericRecord] = []
    for index, item in enumerate(iter_dicts(payload)):
        if len(records) >= MAX_RECORDS_PER_FILE:
            break
        records.extend(records_from_mapping(path, project_root, item, timestamp, kind, index))
    return records[:MAX_RECORDS_PER_FILE]


def extract_jsonl_records(
    path: Path,
    project_root: Path,
    text: str,
    timestamp: datetime,
    kind: str,
) -> list[TrueNumericRecord]:
    records: list[TrueNumericRecord] = []
    for index, line in enumerate(text.splitlines()):
        if len(records) >= MAX_RECORDS_PER_FILE:
            break
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            records.extend(records_from_mapping(path, project_root, payload, timestamp, kind, index))
    return records[:MAX_RECORDS_PER_FILE]


def iter_dicts(value: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []

    def visit(node: Any) -> None:
        if len(found) >= MAX_RECORDS_PER_FILE:
            return
        if isinstance(node, dict):
            found.append(node)
            for child in node.values():
                visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)

    visit(value)
    return found


def records_from_mapping(
    path: Path,
    project_root: Path,
    mapping: dict[str, Any],
    timestamp: datetime,
    kind: str,
    index: int,
) -> list[TrueNumericRecord]:
    records: list[TrueNumericRecord] = []
    lower_map = {str(key).lower(): value for key, value in mapping.items()}

    passed = numeric_value(lower_map.get("passed") or lower_map.get("pass_count"))
    failed = numeric_value(lower_map.get("failed") or lower_map.get("failure_count"))
    total = numeric_value(lower_map.get("total") or lower_map.get("run") or lower_map.get("runs"))
    if total is None and passed is not None and failed is not None:
        total = passed + failed
    if passed is not None and total and total > 0:
        score = max(0.0, 100.0 * (passed / total) - (failed or 0.0) * 2.0)
        item = record(
            path,
            project_root,
            kind,
            timestamp,
            score,
            "json_verifier_pass_ratio",
            {"passed": passed, "failed": failed, "total": total, "record_index": index},
            ["explicit_counts"],
        )
        if item:
            records.append(item)

    for name, value in lower_map.items():
        number = numeric_value(value)
        if number is None:
            continue
        if name in SCORE_FIELD_NAMES:
            item = record(
                path,
                project_root,
                kind,
                timestamp,
                number,
                f"json_numeric_field:{name}",
                {"field": name, "value": number, "record_index": index},
                ["explicit_numeric_field"],
            )
            if item:
                records.append(item)
        elif name in COUNT_FIELD_NAMES:
            score = count_to_score(name, number)
            item = record(
                path,
                project_root,
                kind,
                timestamp,
                score,
                f"json_count_field:{name}",
                {"field": name, "value": number, "record_index": index},
                ["explicit_count_field"],
            )
            if item:
                records.append(item)
    return records[:MAX_RECORDS_PER_FILE]


def extract_markdown_records(
    path: Path,
    project_root: Path,
    text: str,
    timestamp: datetime,
    kind: str,
) -> list[TrueNumericRecord]:
    records: list[TrueNumericRecord] = []
    normalized = text.replace("\r\n", "\n")

    for match in re.finditer(r"(?i)(\d+)\s+run,\s+(\d+)\s+passed,\s+(\d+)\s+failed", normalized):
        total, passed, failed = (float(match.group(i)) for i in range(1, 4))
        score = max(0.0, 100.0 * (passed / max(total, 1.0)) - failed * 2.0)
        item = record(
            path,
            project_root,
            kind,
            timestamp,
            score,
            "markdown_inline_verifier_counts",
            {"run": total, "passed": passed, "failed": failed},
            ["explicit_counts"],
        )
        if item:
            records.append(item)
        if len(records) >= MAX_RECORDS_PER_FILE:
            return records

    run = find_labeled_number(normalized, "Run")
    passed = find_labeled_number(normalized, "Passed")
    failed = find_labeled_number(normalized, "Failed")
    if run is not None and passed is not None:
        score = max(0.0, 100.0 * (passed / max(run, 1.0)) - (failed or 0.0) * 2.0)
        item = record(
            path,
            project_root,
            kind,
            timestamp,
            score,
            "markdown_labeled_verifier_counts",
            {"run": run, "passed": passed, "failed": failed},
            ["explicit_counts"],
        )
        if item:
            records.append(item)

    count_patterns = [
        ("files_inspected", r"(?i)(?:files inspected|files read first|files changed):?\s*(\d+)"),
        ("true_numeric_records", r"(?i)(?:true numeric records|numeric records found):?\s*(\d+)"),
        ("candidate_count", r"(?i)(?:candidate(?:s)?|lesson candidate(?:s)?|memory candidate(?:s)?):?\s*(\d+)"),
        ("risk_count", r"(?i)(?:risk(?:s)?|finding(?:s)?|warning(?:s)?):?\s*(\d+)"),
    ]
    for field, pattern in count_patterns:
        for match in re.finditer(pattern, normalized):
            number = float(match.group(1))
            item = record(
                path,
                project_root,
                kind,
                timestamp,
                count_to_score(field, number),
                f"markdown_count:{field}",
                {"field": field, "value": number},
                ["explicit_count"],
            )
            if item:
                records.append(item)
            if len(records) >= MAX_RECORDS_PER_FILE:
                return records
    return records[:MAX_RECORDS_PER_FILE]


def find_labeled_number(text: str, label: str) -> float | None:
    match = re.search(rf"(?im)^\s*[-*]?\s*{re.escape(label)}\s*:\s*(\d+(?:\.\d+)?)\s*$", text)
    if match:
        return float(match.group(1))
    return None


def numeric_value(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, str) and re.fullmatch(r"-?\d+(?:\.\d+)?", value.strip()):
        number = float(value)
        return number if math.isfinite(number) else None
    return None


def count_to_score(field_name: str, value: float) -> float:
    if "fail" in field_name or "risk" in field_name or "finding" in field_name:
        return max(0.0, 100.0 - min(value, 100.0))
    return min(150.0, max(0.0, value))


def collect_true_records(project_root: Path) -> tuple[list[TrueNumericRecord], int]:
    files = discover_candidate_files(project_root)
    records: list[TrueNumericRecord] = []
    for path in files:
        records.extend(extract_records_from_file(path, project_root))
    records.sort(key=lambda item: (item.timestamp, item.source_path, item.extraction_kind))
    return records, len(files)


def calculate_chart_series(records: list[TrueNumericRecord]) -> dict[str, list[float]]:
    count = len(records)
    if count == 1:
        x_values = [0.0]
    else:
        x_values = [100.0 * i / (count - 1) for i in range(count)]

    raw_scores = [max(0.0, item.score_value) for item in records]
    cumulative: list[float] = []
    total = 0.0
    for score in raw_scores:
        total += score
        cumulative.append(total)
    observed = normalize_to_range(cumulative, 0.0, 145.0)
    percentile = empirical_percentiles(observed)
    expected = rolling_median_curve(observed, window=max(5, min(31, count // 8 or 5)))
    return {
        "x": x_values,
        "raw_score_values": raw_scores,
        "observed": observed,
        "percentile": percentile,
        "expected": expected,
    }


def normalize_to_range(values: list[float], low: float, high: float) -> list[float]:
    if not values:
        return []
    minimum = min(values)
    maximum = max(values)
    if math.isclose(minimum, maximum):
        midpoint = (low + high) / 2.0
        return [midpoint for _ in values]
    scale = (high - low) / (maximum - minimum)
    return [low + (value - minimum) * scale for value in values]


def empirical_percentiles(values: list[float]) -> list[float]:
    if not values:
        return []
    if len(values) == 1:
        return [100.0]
    order = sorted(range(len(values)), key=lambda index: (values[index], index))
    percentiles = [0.0] * len(values)
    for rank, index in enumerate(order):
        percentiles[index] = 100.0 * rank / (len(values) - 1)
    return percentiles


def rolling_median_curve(values: list[float], window: int) -> list[float]:
    if not values:
        return []
    radius = max(1, window // 2)
    medians: list[float] = []
    for index in range(len(values)):
        start = max(0, index - radius)
        end = min(len(values), index + radius + 1)
        chunk = sorted(values[start:end])
        mid = len(chunk) // 2
        if len(chunk) % 2:
            medians.append(chunk[mid])
        else:
            medians.append((chunk[mid - 1] + chunk[mid]) / 2.0)
    return smooth_line(medians, passes=2)


def smooth_line(values: list[float], passes: int = 1) -> list[float]:
    current = values[:]
    for _ in range(passes):
        if len(current) < 3:
            return current
        next_values = current[:]
        for index in range(1, len(current) - 1):
            next_values[index] = (current[index - 1] + current[index] * 2.0 + current[index + 1]) / 4.0
        current = next_values
    return current


class PngCanvas:
    def __init__(self, width: int, height: int, background: tuple[int, int, int] = (255, 255, 255)):
        self.width = width
        self.height = height
        self.pixels = bytearray(background * (width * height))

    def set_pixel(self, x: int, y: int, color: tuple[int, int, int]) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            offset = (y * self.width + x) * 3
            self.pixels[offset : offset + 3] = bytes(color)

    def line(self, x1: float, y1: float, x2: float, y2: float, color: tuple[int, int, int], width: int = 1) -> None:
        steps = max(abs(int(x2 - x1)), abs(int(y2 - y1)), 1)
        for step in range(steps + 1):
            t = step / steps
            x = int(round(x1 + (x2 - x1) * t))
            y = int(round(y1 + (y2 - y1) * t))
            self.disk(x, y, max(0, width // 2), color)

    def dashed_line(self, x1: float, y1: float, x2: float, y2: float, color: tuple[int, int, int], width: int = 1) -> None:
        steps = max(abs(int(x2 - x1)), abs(int(y2 - y1)), 1)
        for step in range(steps + 1):
            if (step // 14) % 2:
                continue
            t = step / steps
            x = int(round(x1 + (x2 - x1) * t))
            y = int(round(y1 + (y2 - y1) * t))
            self.disk(x, y, max(0, width // 2), color)

    def rect(self, x: int, y: int, w: int, h: int, color: tuple[int, int, int], fill: bool = False) -> None:
        if fill:
            for yy in range(y, y + h):
                for xx in range(x, x + w):
                    self.set_pixel(xx, yy, color)
            return
        self.line(x, y, x + w, y, color)
        self.line(x + w, y, x + w, y + h, color)
        self.line(x + w, y + h, x, y + h, color)
        self.line(x, y + h, x, y, color)

    def disk(self, cx: int, cy: int, radius: int, color: tuple[int, int, int]) -> None:
        if radius <= 0:
            self.set_pixel(cx, cy, color)
            return
        for y in range(cy - radius, cy + radius + 1):
            for x in range(cx - radius, cx + radius + 1):
                if (x - cx) ** 2 + (y - cy) ** 2 <= radius**2:
                    self.set_pixel(x, y, color)

    def circle(self, cx: int, cy: int, radius: int, color: tuple[int, int, int], width: int = 2) -> None:
        for angle in range(360):
            radians = math.radians(angle)
            for offset in range(width):
                r = radius - offset
                x = int(round(cx + math.cos(radians) * r))
                y = int(round(cy + math.sin(radians) * r))
                self.set_pixel(x, y, color)

    def text(self, x: int, y: int, text: str, color: tuple[int, int, int], scale: int = 3) -> None:
        cursor = x
        for char in text.upper():
            if char == "\n":
                y += 8 * scale
                cursor = x
                continue
            glyph = FONT.get(char, FONT.get("?"))
            if glyph is None:
                cursor += 4 * scale
                continue
            for gy, row in enumerate(glyph):
                for gx, bit in enumerate(row):
                    if bit == "1":
                        self.rect(cursor + gx * scale, y + gy * scale, scale, scale, color, fill=True)
            cursor += 6 * scale

    def text_vertical(self, x: int, y: int, text: str, color: tuple[int, int, int], scale: int = 3) -> None:
        image = text_bitmap(text.upper(), scale)
        if not image:
            return
        height = len(image)
        width = len(image[0])
        for yy in range(height):
            for xx in range(width):
                if image[yy][xx]:
                    self.set_pixel(x + yy, y + (width - xx), color)

    def save(self, path: Path) -> None:
        raw = bytearray()
        for y in range(self.height):
            raw.append(0)
            start = y * self.width * 3
            raw.extend(self.pixels[start : start + self.width * 3])
        png = bytearray()
        png.extend(b"\x89PNG\r\n\x1a\n")
        png.extend(png_chunk(b"IHDR", struct.pack(">IIBBBBB", self.width, self.height, 8, 2, 0, 0, 0)))
        png.extend(png_chunk(b"IDAT", zlib.compress(bytes(raw), level=9)))
        png.extend(png_chunk(b"IEND", b""))
        path.write_bytes(png)


def png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def text_bitmap(text: str, scale: int) -> list[list[int]]:
    width = max(1, len(text) * 6 * scale)
    height = 7 * scale
    bitmap = [[0 for _ in range(width)] for _ in range(height)]
    cursor = 0
    for char in text:
        glyph = FONT.get(char, FONT.get("?"))
        if glyph is None:
            cursor += 4 * scale
            continue
        for gy, row in enumerate(glyph):
            for gx, bit in enumerate(row):
                if bit == "1":
                    for sy in range(scale):
                        for sx in range(scale):
                            bitmap[gy * scale + sy][cursor + gx * scale + sx] = 1
        cursor += 6 * scale
    return bitmap


FONT = {
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "B": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    "C": ["01111", "10000", "10000", "10000", "10000", "10000", "01111"],
    "D": ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "F": ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
    "G": ["01111", "10000", "10000", "10011", "10001", "10001", "01111"],
    "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "I": ["11111", "00100", "00100", "00100", "00100", "00100", "11111"],
    "J": ["00111", "00010", "00010", "00010", "10010", "10010", "01100"],
    "K": ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    "N": ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "Q": ["01110", "10001", "10001", "10001", "10101", "10010", "01101"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    "V": ["10001", "10001", "10001", "10001", "10001", "01010", "00100"],
    "W": ["10001", "10001", "10001", "10101", "10101", "11011", "10001"],
    "X": ["10001", "10001", "01010", "00100", "01010", "10001", "10001"],
    "Y": ["10001", "10001", "01010", "00100", "00100", "00100", "00100"],
    "Z": ["11111", "00001", "00010", "00100", "01000", "10000", "11111"],
    "0": ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
    "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    "2": ["01110", "10001", "00001", "00010", "00100", "01000", "11111"],
    "3": ["11110", "00001", "00001", "01110", "00001", "00001", "11110"],
    "4": ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
    "5": ["11111", "10000", "10000", "11110", "00001", "00001", "11110"],
    "6": ["01110", "10000", "10000", "11110", "10001", "10001", "01110"],
    "7": ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
    "8": ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
    "9": ["01110", "10001", "10001", "01111", "00001", "00001", "01110"],
    " ": ["00000", "00000", "00000", "00000", "00000", "00000", "00000"],
    ".": ["00000", "00000", "00000", "00000", "00000", "01100", "01100"],
    ",": ["00000", "00000", "00000", "00000", "00000", "01100", "01000"],
    ":": ["00000", "01100", "01100", "00000", "01100", "01100", "00000"],
    "-": ["00000", "00000", "00000", "11111", "00000", "00000", "00000"],
    "/": ["00001", "00010", "00010", "00100", "01000", "01000", "10000"],
    "?": ["01110", "10001", "00001", "00010", "00100", "00000", "00100"],
}


def render_chart_png(
    path: Path,
    records: list[TrueNumericRecord],
    series: dict[str, list[float]] | None,
    insufficient: bool,
) -> str:
    canvas = PngCanvas(1400, 1050)
    left, top, right, bottom = 150, 70, 80, 150
    plot_w = canvas.width - left - right
    plot_h = canvas.height - top - bottom
    x0, y0 = left, canvas.height - bottom
    x1, y1 = canvas.width - right, top

    axis = (40, 40, 40)
    gray = (180, 180, 180)
    green = (25, 238, 55)
    blue = (0, 40, 230)
    red = (235, 20, 20)

    canvas.rect(x0, y1, plot_w, plot_h, (255, 255, 255), fill=True)
    canvas.rect(x0, y1, plot_w, plot_h, gray, fill=False)

    def px(x: float) -> int:
        return int(round(x0 + (x / 100.0) * plot_w))

    def py(y: float) -> int:
        return int(round(y0 - (y / 150.0) * plot_h))

    for tick in range(0, 101, 20):
        x = px(tick)
        canvas.line(x, y0, x, y0 + 10, axis, 2)
        canvas.line(x, y1, x, y1 - 10, gray, 1)
        canvas.text(x - 15, y0 + 25, str(tick), axis, 4)
    for tick in (0, 50, 100, 150):
        y = py(tick)
        canvas.line(x0 - 10, y, x0, y, axis, 2)
        canvas.line(x0, y, x1, y, (232, 232, 232), 1)
        canvas.text(x0 - 80, y - 15, str(tick), axis, 4)

    canvas.dashed_line(x0, py(100), x1, py(100), (0, 0, 0), 4)
    canvas.line(x0, y0, x1, y0, axis, 3)
    canvas.line(x0, y0, x0, y1, axis, 3)

    canvas.text(455, 965, "NORMALIZED ARC LENGTH", axis, 5)
    canvas.text_vertical(18, 295, "NORMALIZED SCORES", axis, 5)

    if insufficient or not series:
        canvas.text(330, 430, "INSUFFICIENT TRUE DATA", (140, 0, 0), 6)
        canvas.text(300, 500, f"TRUE NUMERIC RECORDS FOUND: {len(records)}", axis, 4)
        canvas.text(245, 555, "NO FAKE SCATTER OR CURVES WERE GENERATED", axis, 4)
    else:
        x_values = series["x"]
        observed = series["observed"]
        percentile = series["percentile"]
        expected = series["expected"]
        for x, y in zip(x_values, observed):
            canvas.circle(px(x), py(y), 8, green, 3)
        draw_polyline(canvas, x_values, percentile, px, py, blue, 4)
        draw_polyline(canvas, x_values, expected, px, py, red, 4)

    legend_x, legend_y = 365, 95
    canvas.rect(legend_x, legend_y, 610, 160, (160, 160, 160), fill=False)
    canvas.circle(legend_x + 45, legend_y + 37, 8, green, 3)
    canvas.text(legend_x + 85, legend_y + 22, "NORMALIZED OBSERVED SUM SCORE", axis, 3)
    canvas.line(legend_x + 20, legend_y + 78, legend_x + 70, legend_y + 78, blue, 4)
    canvas.text(legend_x + 85, legend_y + 63, "PERCENTILE INDEX", axis, 3)
    canvas.line(legend_x + 20, legend_y + 119, legend_x + 70, legend_y + 119, red, 4)
    canvas.text(legend_x + 85, legend_y + 104, "NORMALIZED EXPECTED SUM SCORE", axis, 3)

    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path)
    return "standard_library_png_renderer"


def draw_polyline(
    canvas: PngCanvas,
    xs: list[float],
    ys: list[float],
    px: Any,
    py: Any,
    color: tuple[int, int, int],
    width: int,
) -> None:
    for index in range(1, len(xs)):
        canvas.line(px(xs[index - 1]), py(ys[index - 1]), px(xs[index]), py(ys[index]), color, width)


def timestamp_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def relative_posix(path: Path) -> str:
    return path.as_posix()


def write_outputs(project_root: Path, records: list[TrueNumericRecord], files_inspected: int) -> ChartRunSummary:
    insufficient = len(records) < MIN_RECORDS_FOR_FULL_CHART
    series = None if insufficient else calculate_chart_series(records)
    chart_path = project_root / PNG_PATH
    data_path = project_root / DATA_JSON_PATH
    report_path = project_root / REPORT_PATH
    receipt_path = project_root / RECEIPT_PATH
    generator_path = project_root / GENERATOR_PATH
    generated_at = timestamp_utc()
    renderer = render_chart_png(chart_path, records, series, insufficient)
    chart_hash = sha256_file(chart_path)
    generator_hash = sha256_file(generator_path)

    categories: dict[str, int] = {}
    for item in records:
        categories[item.source_kind] = categories.get(item.source_kind, 0) + 1

    payload = {
        "summary": {
            "files_inspected": files_inspected,
            "true_numeric_records_found": len(records),
            "source_categories_used": categories,
            "arc_length_mode": "chronological_local_record_position",
            "chart_created": True,
            "insufficient_data": insufficient,
            "renderer": renderer,
        },
        "series": series,
        "records": [asdict(item) for item in records],
    }
    canonical_data_hash = sha256_bytes(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    payload.update(
        {
            "artifact": ARTIFACT_NAME,
            "source_data": relative_posix(DATA_JSON_PATH),
            "generator": relative_posix(GENERATOR_PATH),
            "timestamp_utc": generated_at,
            "source_file_count": files_inspected,
            "true_numeric_record_count": len(records),
            "arc_length_mode": "chronological_local_record_position",
            "chart_hash_sha256": chart_hash,
            "data_hash_sha256": canonical_data_hash,
            "data_hash_scope": "canonical chart data payload before embedded metadata hash fields",
            "generator_hash_sha256": generator_hash,
            "receipt_hash_sha256": None,
            "status": RUN_STATUS,
            "metric": METRIC_NAME,
            "truth_boundary": truth_boundary(),
        }
    )
    data_path.parent.mkdir(parents=True, exist_ok=True)
    data_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    data_hash = sha256_file(data_path)
    build_hash = sha256_bytes((generator_hash + data_hash).encode("ascii"))
    receipt_hash = write_receipt(
        receipt_path=receipt_path,
        timestamp=generated_at,
        chart_hash=chart_hash,
        data_hash=data_hash,
        generator_hash=generator_hash,
        build_hash=build_hash,
        files_inspected=files_inspected,
        record_count=len(records),
        insufficient=insufficient,
    )

    summary = ChartRunSummary(
        project_root=str(project_root),
        files_inspected=files_inspected,
        true_numeric_records_found=len(records),
        source_categories_used=categories,
        arc_length_mode="chronological local-record position",
        chart_created=True,
        insufficient_data=insufficient,
        chart_path=str(chart_path),
        data_json_path=str(data_path),
        report_path=str(report_path),
        receipt_path=str(receipt_path),
        renderer=renderer,
        artifact=ARTIFACT_NAME,
        source_data=relative_posix(DATA_JSON_PATH),
        generator=relative_posix(GENERATOR_PATH),
        build_hash_sha256=build_hash,
        chart_hash_sha256=chart_hash,
        data_hash_sha256=data_hash,
        generator_hash_sha256=generator_hash,
        receipt_hash_sha256=receipt_hash,
        timestamp_utc=generated_at,
        metric=METRIC_NAME,
        status=RUN_STATUS,
        safety_boundaries=truth_boundary(),
    )
    write_report(report_path, summary)
    return summary


def truth_boundary() -> list[str]:
    return [
        "source files were bounded local Engel project files only",
        "no fake, random, mock, seeded, synthetic, or demo data",
        "no package install or download behavior",
        "no provider/network/browser/API calls",
        "no WSL/Android/Flutter runtime calls",
        "Hermes/Hermes-style runtimes rejected / blocked / do not install on this computer; no outside-AI behavior",
        "no trusted-memory write",
        "no queue/source/route mutation",
        "no queue, route, or source mutation",
        "chart/report artifacts only",
        "file contents treated as untrusted data",
    ]


def write_receipt(
    receipt_path: Path,
    timestamp: str,
    chart_hash: str,
    data_hash: str,
    generator_hash: str,
    build_hash: str,
    files_inspected: int,
    record_count: int,
    insufficient: bool,
) -> str:
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    boundaries = "\n".join(f"- {item}" for item in truth_boundary())
    text = f"""# Engel True Data Score Chart Receipt

artifact:
{ARTIFACT_NAME}

source_data:
{relative_posix(DATA_JSON_PATH)}

generator:
{relative_posix(GENERATOR_PATH)}

build_hash:
{build_hash}

chart_hash:
{chart_hash}

data_hash:
{data_hash}

generator_hash:
{generator_hash}

timestamp_utc:
{timestamp}

metric:
{METRIC_NAME}

status:
{RUN_STATUS}

source_file_count:
{files_inspected}

true_numeric_record_count:
{record_count}

insufficient_data:
{str(insufficient).lower()}

truth_boundary:
{boundaries}

approval_status:
report-only artifact; not approval, not promotion, not trusted memory
"""
    receipt_path.write_text(text, encoding="utf-8")
    return sha256_file(receipt_path)


def write_report(path: Path, summary: ChartRunSummary) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if summary.insufficient_data:
        chart_note = (
            "Fewer than 20 true numeric records were found. The tool refused to "
            "create fake scatter data and produced an insufficient-data diagnostic PNG."
        )
    else:
        chart_note = (
            "The chart uses true numeric records extracted from local Engel files. "
            "Arc length is approximated by chronological local-record position."
        )
    categories = "\n".join(
        f"- `{name}`: {count}" for name, count in sorted(summary.source_categories_used.items())
    ) or "- none"
    boundaries = "\n".join(f"- {item}" for item in summary.safety_boundaries)
    text = f"""# Engel True Data Score Chart

## Summary

Generated a local/offline chart in the requested reference style using only true local Engel numeric records.

{chart_note}

## Files Inspected

- files inspected: `{summary.files_inspected}`
- true numeric records found: `{summary.true_numeric_records_found}`
- max files inspected setting: `{MAX_FILES_INSPECTED}`
- max bytes per file setting: `{MAX_BYTES_PER_FILE}`

## Source Categories Used

{categories}

## Arc Length

- mode: `{summary.arc_length_mode}`
- note: arc length approximated by chronological local-record position unless true arc/path/progress values are present.

## Output Paths

- chart PNG: `{summary.chart_path}`
- chart data JSON: `{summary.data_json_path}`
- receipt: `{summary.receipt_path}`
- report: `{summary.report_path}`
- renderer: `{summary.renderer}`

## Receipt Metadata

- artifact: `{summary.artifact}`
- source data: `{summary.source_data}`
- generator: `{summary.generator}`
- timestamp UTC: `{summary.timestamp_utc}`
- metric: `{summary.metric}`
- status: `{summary.status}`
- build hash: `{summary.build_hash_sha256}`
- chart hash: `{summary.chart_hash_sha256}`
- data hash: `{summary.data_hash_sha256}`
- generator hash: `{summary.generator_hash_sha256}`
- receipt hash: `{summary.receipt_hash_sha256}`

## Chart Interpretation

- Green open circles: normalized observed cumulative score from explicit true local numeric records.
- Blue line: empirical percentile/rank index computed from observed scores.
- Red line: deterministic rolling-median expected score curve computed from observed true data only.
- Black dashed line: normalized reference line at `100`.

## Insufficient Data Behavior

If fewer than `{MIN_RECORDS_FOR_FULL_CHART}` true numeric records are found, the tool creates an honest diagnostic chart and does not draw fake scatter points or fake curves.

## Safety Boundaries

{boundaries}

## Verification Results

Verification is recorded by running:

```text
python -m py_compile tools\\engel_true_data_score_chart.py tools\\verify_engel_true_data_score_chart.py
python tools\\verify_engel_true_data_score_chart.py
python tools\\engel_true_data_score_chart.py --json
scripts\\codex_verify.ps1
```
"""
    path.write_text(text, encoding="utf-8")


def run(project_root: Path) -> ChartRunSummary:
    records, files_inspected = collect_true_records(project_root)
    return write_outputs(project_root, records, files_inspected)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Engel true-data score chart.")
    parser.add_argument("--project-root", default=None)
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args(argv)

    project_root = resolve_project_root(args.project_root)
    if not project_root.exists() or not project_root.is_dir():
        print(f"Project root not found: {project_root}", file=sys.stderr)
        return 2
    summary = run(project_root)
    if args.json_output:
        print(json.dumps(asdict(summary), indent=2))
    else:
        print(f"Chart output: {summary.chart_path}")
        print(f"Data output: {summary.data_json_path}")
        print(f"Report output: {summary.report_path}")
        print(f"True numeric records: {summary.true_numeric_records_found}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
