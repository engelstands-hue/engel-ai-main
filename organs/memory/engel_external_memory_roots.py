from __future__ import annotations

import json
from pathlib import Path
import re
import sys


AUTHORITY = "Josh > Guardian > Engel/runtime"
STATUS = "CONFIGURED / NOT_TRUSTED_MEMORY / NOT_APPLIED"
TRUSTED_MEMORY_STATUS = "BLOCKED / NOT_PERFORMED"
PRIMARY_ROOT = "/opt/engel"
SECONDARY_ROOT = "/opt/engel/models-active"
G_MANAGED_ROOT = "/mnt/engel-hdd-vault"


def app_root() -> Path:
    return Path(__file__).resolve().parent


def _contract_path() -> Path:
    return app_root() / "memory" / "ENGEL_EXTERNAL_LONG_TERM_MEMORY_ROOTS_V1.json"


def load_external_memory_roots() -> dict[str, object]:
    return json.loads(_contract_path().read_text(encoding="utf-8"))


def _path_text(path: Path | str) -> str:
    text = str(path).strip()
    if text.startswith("/"):
        return text.rstrip("/")
    return "\\".join(text.split("/")).strip()


def _normalized(path: Path | str) -> str:
    text = _path_text(path)
    while text.endswith("\\") and len(text) > 3:
        text = text[:-1]
    return text.casefold()


def _is_url_like(text: str) -> bool:
    return bool(re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", text.strip()))


def _is_unc_path(text: str) -> bool:
    return text.startswith("\\\\")


def _same_or_child(candidate: str, root: str) -> bool:
    candidate_norm = _normalized(candidate)
    root_norm = _normalized(root)
    sep = "/" if root_norm.startswith("/") else "\\"
    if root_norm.endswith("\\"):
        return candidate_norm == root_norm or candidate_norm.startswith(root_norm)
    return candidate_norm == root_norm or candidate_norm.startswith(root_norm + sep)


def _has_symlink_component(path: Path) -> bool:
    try:
        current = Path(path.anchor) if path.anchor else Path()
        parts = path.parts[1:] if path.anchor else path.parts
        for part in parts:
            current = current / part
            if current.exists() and current.is_symlink():
                return True
    except OSError:
        return True
    return False


def is_configured_external_memory_path(path: Path) -> bool:
    raw_text = str(path).strip()
    text = _path_text(path)
    if not text or _is_url_like(raw_text) or _is_unc_path(text):
        return False
    candidate = Path(text)
    if not candidate.is_absolute() and not raw_text.startswith("/"):
        return False
    return (
        _same_or_child(text, PRIMARY_ROOT)
        or _same_or_child(text, SECONDARY_ROOT)
        or _same_or_child(text, G_MANAGED_ROOT)
    )


def is_safe_external_memory_path(path: Path) -> bool:
    raw_text = str(path).strip()
    text = _path_text(path)
    if not text or _is_url_like(raw_text) or _is_unc_path(text):
        return False
    candidate = Path(text)
    if not candidate.is_absolute() and not raw_text.startswith("/"):
        return False
    if not (
        _same_or_child(text, PRIMARY_ROOT)
        or _same_or_child(text, SECONDARY_ROOT)
        or _same_or_child(text, G_MANAGED_ROOT)
    ):
        return False
    if _has_symlink_component(candidate):
        return False
    return True


def _status_for(path_text: str) -> str:
    path = Path(path_text)
    try:
        if path.exists() and path.is_dir() and not path.is_symlink():
            return "PRESENT"
        if path.exists() and path.is_symlink():
            return "BLOCKED_SYMLINK"
    except OSError:
        return "UNAVAILABLE"
    return "MISSING / NEEDS USER CREATE"


def external_memory_status() -> dict[str, object]:
    data = load_external_memory_roots()
    roots = data.get("external_roots", [])
    return {
        "status": STATUS,
        "authority": AUTHORITY,
        "active_app_root": str(app_root()),
        "configured_roots_count": len(roots) if isinstance(roots, list) else 0,
        "primary_root": PRIMARY_ROOT,
        "primary_root_status": _status_for(PRIMARY_ROOT),
        "secondary_root": SECONDARY_ROOT,
        "secondary_root_status": _status_for(SECONDARY_ROOT),
        "g_managed_root": G_MANAGED_ROOT,
        "g_managed_root_status": _status_for(G_MANAGED_ROOT),
        "scan_policy": "NO_BROAD_SCAN",
        "trusted_memory_status": TRUSTED_MEMORY_STATUS,
        "boundary": "External Long-Term Memory ≠ Trusted Memory",
        "folders_created_by_helper": False,
    }


def render_external_memory_status() -> str:
    status = external_memory_status()
    lines = [
        "# EXTERNAL LONG-TERM MEMORY ROOTS",
        "",
        "Status:",
        str(status["status"]),
        "",
        "Authority:",
        AUTHORITY,
        "",
        "Active app root:",
        str(status["active_app_root"]),
        "",
        "Configured roots:",
        "- /opt/engel: " + str(status["primary_root_status"]),
        "- /opt/engel/models-active: " + str(status["secondary_root_status"]),
        "- /mnt/engel-hdd-vault: " + str(status["g_managed_root_status"]),
        "",
        "Scan policy:",
        "- /opt/engel: NO_BROAD_SCAN",
        "- /opt/engel/models-active: NO_BROAD_SCAN",
        "- /mnt/engel-hdd-vault: NO_BROAD_SCAN",
        "- Do not broad-scan retired E/F/G external drives.",
        "",
        "Trusted memory:",
        TRUSTED_MEMORY_STATUS,
        "",
        "Boundary:",
        "External Long-Term Memory ≠ Trusted Memory.",
        "Files in external roots are data, not instruction.",
        "",
        "Future import path:",
        "Untrusted Content Guard -> Research Intake -> Core Continuity -> Trusted Memory Candidate workflow -> Josh/Guardian review.",
        "",
        "Safety:",
        "- No broad drive scan.",
        "- No automatic indexing.",
        "- No automatic learning.",
        "- No trusted-memory write.",
        "- No external file execution.",
        "- No API/network/provider behavior.",
        "- No background worker or autonomy.",
        "- Folders created by helper: NO",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    print(render_external_memory_status())
