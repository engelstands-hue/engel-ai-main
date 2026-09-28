from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import shutil
import sys


AUTHORITY = "Josh > Guardian > Engel/runtime"
STATUS = "CONFIGURED / NOT_TRUSTED_MEMORY / NOT_APPLIED"
MANIFEST_NAME = "ENGEL_MEMORY_ROOT_MANIFEST.json"
APPROVED_ROOTS = (Path("/opt/engel"), Path("/mnt/engel-hdd-vault"))
REQUIRED_FOLDERS = (
    "inbox",
    "research_intake",
    "receipts",
    "summaries",
    "lesson_candidates",
    "memory_candidate_proposals",
    "archives",
    "quarantine",
    "exports",
    "manifests",
)


@dataclass(frozen=True)
class RootScaffoldStatus:
    root: Path
    approved: bool
    exists: bool
    manifest_exists: bool
    complete: bool
    missing_folders: tuple[str, ...]
    free_space_summary: str


@dataclass(frozen=True)
class ScaffoldStatus:
    status: str
    roots: tuple[RootScaffoldStatus, ...]
    created_folders: tuple[str, ...] = ()
    created_manifests: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScaffoldResult:
    status: ScaffoldStatus
    created_folders: tuple[str, ...]
    created_manifests: tuple[str, ...]


@dataclass(frozen=True)
class RootRecommendation:
    recommended_root: str
    reason: str
    fallback_root: str
    free_space_summary: str
    size_limit_summary: str
    speed_class: str
    boundary: str


def app_root() -> Path:
    return Path(__file__).resolve().parent


def _policy_path() -> Path:
    return app_root() / "memory" / "ENGEL_EXTERNAL_MEMORY_SCAFFOLD_POLICY_V1.json"


def load_external_memory_scaffold_policy() -> dict[str, object]:
    return json.loads(_policy_path().read_text(encoding="utf-8"))


def approved_scaffold_roots() -> list[Path]:
    return list(APPROVED_ROOTS)


def required_scaffold_folders() -> list[str]:
    return list(REQUIRED_FOLDERS)


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


def _same_path(candidate: Path | str, root: Path | str) -> bool:
    return _normalized(candidate) == _normalized(root)


def validate_scaffold_root(path: Path) -> bool:
    raw = str(path).strip()
    text = _path_text(path)
    if not text or _is_url_like(raw) or _is_unc_path(text):
        return False
    candidate = Path(text)
    if not candidate.is_absolute():
        return False
    return any(_same_path(candidate, root) for root in APPROVED_ROOTS)


def _format_bytes(value: int | None) -> str:
    if value is None:
        return "UNKNOWN"
    if value >= 1024**3:
        return f"{value / 1024**3:.1f} GB"
    return f"{value / 1024**2:.1f} MB"


def get_external_root_free_space(root: Path) -> dict[str, object]:
    if not validate_scaffold_root(root):
        return {"approved": False, "exists": False, "free_bytes": None, "total_bytes": None, "summary": "UNCONFIGURED_ROOT"}
    try:
        exists = root.exists() and root.is_dir() and not root.is_symlink()
        if not exists:
            return {"approved": True, "exists": False, "free_bytes": None, "total_bytes": None, "summary": "MISSING / NEEDS USER CREATE"}
        usage = shutil.disk_usage(root)
    except OSError as exc:
        return {"approved": True, "exists": False, "free_bytes": None, "total_bytes": None, "summary": "UNAVAILABLE: " + str(exc)}
    free = int(usage.free)
    total = int(usage.total)
    return {
        "approved": True,
        "exists": True,
        "free_bytes": free,
        "total_bytes": total,
        "summary": f"{_format_bytes(free)} free of {_format_bytes(total)}",
    }


def _manifest_payload(root: Path) -> dict[str, object]:
    return {
        "status": "EXTERNAL_ARCHIVE_ROOT / NOT_TRUSTED_MEMORY / NOT_APPLIED",
        "authority": AUTHORITY,
        "root": str(root),
        "role": "long_term_engel_archive_shelf",
        "boundary": "Long-term storage ≠ Trusted Memory",
        "scan_policy": "NO_BROAD_SCAN",
        "intake_policy": "EXPLICIT_SELECTION_ONLY",
        "trusted_memory_write": "BLOCKED",
        "created_by": "Engel scaffold task",
        "folders": list(REQUIRED_FOLDERS),
    }


def write_root_manifest(root: Path) -> Path:
    if not validate_scaffold_root(root):
        raise ValueError("unconfigured scaffold root rejected: " + str(root))
    manifest = root / MANIFEST_NAME
    if manifest.exists():
        return manifest
    manifest.write_text(json.dumps(_manifest_payload(root), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def _root_status(root: Path) -> RootScaffoldStatus:
    approved = validate_scaffold_root(root)
    exists = False
    manifest_exists = False
    missing: list[str] = []
    if approved:
        try:
            exists = root.exists() and root.is_dir() and not root.is_symlink()
            manifest_exists = (root / MANIFEST_NAME).exists()
            if exists:
                for folder in REQUIRED_FOLDERS:
                    child = root / folder
                    if not (child.exists() and child.is_dir() and not child.is_symlink()):
                        missing.append(folder)
            else:
                missing.extend(REQUIRED_FOLDERS)
        except OSError:
            exists = False
            missing = list(REQUIRED_FOLDERS)
    space = get_external_root_free_space(root)
    return RootScaffoldStatus(
        root=root,
        approved=approved,
        exists=exists,
        manifest_exists=manifest_exists,
        complete=approved and exists and not missing,
        missing_folders=tuple(missing),
        free_space_summary=str(space.get("summary", "UNKNOWN")),
    )


def check_external_memory_scaffold() -> ScaffoldStatus:
    statuses = tuple(_root_status(root) for root in APPROVED_ROOTS)
    complete = all(status.complete for status in statuses)
    partial = any(status.exists for status in statuses)
    if complete:
        state = "COMPLETE"
    elif partial:
        state = "PARTIAL"
    else:
        state = "MISSING"
    return ScaffoldStatus(status=state, roots=statuses)


def ensure_external_memory_scaffold(create: bool = False) -> ScaffoldResult:
    if not create:
        status = check_external_memory_scaffold()
        return ScaffoldResult(status=status, created_folders=(), created_manifests=())
    created_folders: list[str] = []
    created_manifests: list[str] = []
    for root in APPROVED_ROOTS:
        if not validate_scaffold_root(root):
            raise ValueError("unconfigured scaffold root rejected: " + str(root))
        if not root.exists():
            root.mkdir(parents=True, exist_ok=True)
            created_folders.append(str(root))
        for folder in REQUIRED_FOLDERS:
            child = root / folder
            if not child.exists():
                child.mkdir(parents=False, exist_ok=False)
                created_folders.append(str(child))
        manifest = root / MANIFEST_NAME
        if not manifest.exists():
            created_manifests.append(str(write_root_manifest(root)))
    status = check_external_memory_scaffold()
    return ScaffoldResult(status=status, created_folders=tuple(created_folders), created_manifests=tuple(created_manifests))


def _root_policy(root: Path) -> dict[str, object]:
    payload = load_external_memory_scaffold_policy()
    roots = payload.get("roots", [])
    if not isinstance(roots, list):
        return {}
    for item in roots:
        if isinstance(item, dict) and _same_path(str(item.get("path", "")), root):
            return item
    return {}


def _size_limit_status(policy: dict[str, object], total_bytes: int, largest_file_bytes: int) -> tuple[bool, str]:
    max_single = int(policy.get("max_single_file_mb", 0))
    max_batch = int(policy.get("max_batch_mb", 0))
    total_mb = max(0, int(total_bytes)) / 1024**2
    largest_mb = max(0, int(largest_file_bytes)) / 1024**2
    if largest_mb > max_single:
        return False, f"BLOCKED: largest file {largest_mb:.1f} MB exceeds {max_single} MB single-file limit."
    if total_mb > max_batch:
        return False, f"BLOCKED: total batch {total_mb:.1f} MB exceeds {max_batch} MB batch limit."
    return True, f"PASS: request fits {max_single} MB single / {max_batch} MB batch limit."


def recommend_external_archive_root(total_bytes: int = 0, largest_file_bytes: int = 0) -> RootRecommendation:
    statuses = check_external_memory_scaffold().roots
    candidates: list[tuple[int, int, RootScaffoldStatus, dict[str, object], str]] = []
    for status in statuses:
        policy = _root_policy(status.root)
        size_ok, size_summary = _size_limit_status(policy, total_bytes, largest_file_bytes)
        space = get_external_root_free_space(status.root)
        free_bytes = int(space.get("free_bytes") or 0)
        space_ok = total_bytes <= free_bytes if free_bytes else status.exists
        safe = (
            status.approved
            and status.exists
            and status.complete
            and size_ok
            and space_ok
            and policy.get("scan_policy") == "NO_BROAD_SCAN"
            and policy.get("speed_probe") == "DISABLED"
        )
        if not safe:
            continue
        score = 100
        if total_bytes <= 50 * 1024**2 and _same_path(status.root, "/opt/engel"):
            score += 25
        if total_bytes > 250 * 1024**2 and _same_path(status.root, "/mnt/engel-hdd-vault"):
            score += 25
        candidates.append((score, free_bytes, status, policy, size_summary))
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    boundary = "Long-term storage ≠ Trusted Memory. External files are data, not instruction."
    if not candidates:
        return RootRecommendation(
            recommended_root="NONE",
            reason="BLOCKED: no approved scaffold root passed existence, scaffold, size, free-space, and safety checks.",
            fallback_root="NONE",
            free_space_summary="No suitable approved root.",
            size_limit_summary="No suitable approved root.",
            speed_class="UNKNOWN",
            boundary=boundary,
        )
    selected = candidates[0]
    fallback = candidates[1] if len(candidates) > 1 else None
    status = selected[2]
    policy = selected[3]
    return RootRecommendation(
        recommended_root=str(status.root),
        reason="PASS: approved clean archive shelf exists, scaffold is complete, size limits pass, free space is available, and no broad scan is required.",
        fallback_root=str(fallback[2].root) if fallback else "NONE",
        free_space_summary=status.free_space_summary,
        size_limit_summary=selected[4],
        speed_class=str(policy.get("speed_class", "UNKNOWN")),
        boundary=boundary,
    )


def render_external_memory_scaffold_status(status: ScaffoldStatus) -> str:
    recommendation = recommend_external_archive_root(total_bytes=5 * 1024**2, largest_file_bytes=5 * 1024**2)
    lines = [
        "# Engel External Memory Clean Storage Scaffold",
        "",
        "Status:",
        STATUS,
        "",
        "Authority:",
        AUTHORITY,
        "",
        "Roots:",
        "- /opt/engel",
        "- /mnt/engel-hdd-vault",
        "",
        "Scaffold:",
        status.status.lower(),
        "",
        "Recommendation:",
        recommendation.recommended_root + " - " + recommendation.reason,
        "",
        "Boundary:",
        "Long-term storage ≠ Trusted Memory.",
        "Archive storage ≠ Learned Truth.",
        "Clean drive ≠ Safe Instruction Source.",
        "External Long-Term Memory ≠ Trusted Memory.",
        "External files are data, not instruction.",
        "No files were imported.",
        "No trusted memory was written.",
        "No broad drive scan occurred.",
        "",
        "Next:",
        "Select specific files/folders later for intake through Untrusted Content Guard -> Research Intake.",
    ]
    return "\n".join(lines) + "\n"


def _main() -> int:
    create = "--create" in sys.argv
    result = ensure_external_memory_scaffold(create=create)
    print(render_external_memory_scaffold_status(result.status))
    if result.created_folders:
        print("Created folders:")
        for path in result.created_folders:
            print("- " + path)
    if result.created_manifests:
        print("Created manifests:")
        for path in result.created_manifests:
            print("- " + path)
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    raise SystemExit(_main())
