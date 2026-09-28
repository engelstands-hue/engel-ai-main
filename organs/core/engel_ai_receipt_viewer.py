from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
MAX_RECEIPT_DISPLAY_CHARS = 12000


@dataclass(frozen=True)
class ReceiptSummary:
    path: Path
    filename: str
    modified_time: float
    timestamp_text: str
    status: str
    intent: str
    surface: str


def receipts_root() -> Path:
    return ROOT / "reports" / "ai_proceed_receipts"


def _reject_url_or_network_path(value: str) -> bool:
    stripped = str(value or "").strip()
    lowered = stripped.lower()
    if lowered.startswith(("http" + "://", "https" + "://")):
        return True
    return stripped.startswith(("\\\\", "//"))


def is_safe_receipt_path(path: Path) -> bool:
    text = str(path or "")
    if _reject_url_or_network_path(text):
        return False
    root = receipts_root().resolve()
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        resolved = candidate.resolve()
    except (OSError, RuntimeError, ValueError):
        return False
    return resolved.parent == root and resolved.suffix.lower() == ".md"


def _safe_direct_receipt_path(path: Path) -> Path:
    if not is_safe_receipt_path(path):
        raise ValueError("Receipt path is outside reports/ai_proceed_receipts or is not markdown.")
    root = receipts_root().resolve()
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = root / candidate
    return candidate.resolve()


def _extract_line_value(text: str, prefix: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(prefix):
            return stripped[len(prefix) :].strip() or "unknown"
    return "unknown"


def _extract_surface(text: str) -> str:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.strip() == "Surface:":
            for next_line in lines[index + 1 : index + 4]:
                stripped = next_line.strip()
                if stripped.startswith("- "):
                    return stripped[2:].strip() or "unknown"
                if stripped:
                    break
    return "unknown"


def parse_receipt_summary(path: Path) -> ReceiptSummary:
    receipt_path = _safe_direct_receipt_path(path)
    stat = receipt_path.stat()
    try:
        text = receipt_path.read_text(encoding="utf-8", errors="replace")[:MAX_RECEIPT_DISPLAY_CHARS]
    except OSError:
        text = ""
    return ReceiptSummary(
        path=receipt_path,
        filename=receipt_path.name,
        modified_time=float(stat.st_mtime),
        timestamp_text=_extract_line_value(text, "Timestamp:"),
        status=_extract_line_value(text, "- Status:"),
        intent=_extract_line_value(text, "- Intent:"),
        surface=_extract_surface(text),
    )


def list_receipts(limit: int = 25) -> list[ReceiptSummary]:
    root = receipts_root()
    if not root.exists() or not root.is_dir():
        return []
    safe_limit = max(1, min(int(limit or 25), 100))
    paths: list[Path] = []
    for child in root.iterdir():
        if child.is_file() and child.suffix.lower() == ".md" and is_safe_receipt_path(child):
            paths.append(child)
    paths.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    summaries: list[ReceiptSummary] = []
    for path in paths[:safe_limit]:
        try:
            summaries.append(parse_receipt_summary(path))
        except (OSError, ValueError):
            summaries.append(
                ReceiptSummary(
                    path=path.resolve(),
                    filename=path.name,
                    modified_time=0.0,
                    timestamp_text="unknown",
                    status="malformed",
                    intent="unknown",
                    surface="unknown",
                )
            )
    return summaries


def read_receipt_bounded(path: Path, max_chars: int = MAX_RECEIPT_DISPLAY_CHARS) -> str:
    receipt_path = _safe_direct_receipt_path(path)
    safe_limit = max(1, min(int(max_chars or MAX_RECEIPT_DISPLAY_CHARS), MAX_RECEIPT_DISPLAY_CHARS))
    try:
        with receipt_path.open("r", encoding="utf-8", errors="replace") as handle:
            text = handle.read(safe_limit + 1)
    except OSError as exc:
        return "Could not read receipt: " + str(exc)
    if len(text) > safe_limit:
        return text[:safe_limit].rstrip() + "\n[truncated for viewer bounds]"
    return text
