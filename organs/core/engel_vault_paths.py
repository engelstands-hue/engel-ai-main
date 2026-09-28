from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable


ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
STORAGE_REGISTRY = ROOT / "memory" / "ENGEL_STORAGE_LOCATION_REGISTRY_V1.json"
VAULT_ENV_VAR = "ENGEL_HDD_VAULT_ROOT"
ACTIVE_RUNTIME_ROOT = Path("/opt/engel")
ARCHIVE_ROOT = Path("/mnt/engel-hdd-vault")
SOURCE_DRIVES = ("E", "F", "G")
MODEL_SCAN_ORDER = ("F", "G", "E")
ACTIVE_ROOT_ALIASES = {
    "E": ARCHIVE_ROOT,
    "F": ACTIVE_RUNTIME_ROOT,
    "G": ACTIVE_RUNTIME_ROOT / "models-active",
}


def _load_profile() -> dict:
    if not STORAGE_REGISTRY.exists():
        return {}
    try:
        data = json.loads(STORAGE_REGISTRY.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _clean_path_text(value: object) -> str:
    return str(value or "").strip().strip('"')


def configured_vault_root() -> Path | None:
    env_value = _clean_path_text(os.environ.get(VAULT_ENV_VAR))
    if env_value:
        configured = Path(env_value)
        if str(configured).replace("\\", "/").rstrip("/") != str(ARCHIVE_ROOT):
            return None
        return configured
    return ARCHIVE_ROOT


def vault_root_ready() -> bool:
    root = configured_vault_root()
    return bool(root is not None and root.exists() and root.is_dir())


def raw_external_memory_root(drive: str) -> Path:
    letter = str(drive or "").strip().upper()[:1]
    if letter not in ACTIVE_ROOT_ALIASES:
        raise ValueError(f"unknown Engel external memory drive: {drive!r}")
    return ACTIVE_ROOT_ALIASES[letter]


def vault_memory_root_for_drive(drive: str) -> Path | None:
    root = configured_vault_root()
    if root is None:
        return None
    letter = str(drive or "").strip().upper()[:1]
    if letter not in SOURCE_DRIVES:
        raise ValueError(f"unknown Engel external memory drive: {drive!r}")
    if letter == "E":
        return root
    if letter == "F":
        return Path("/opt/engel")
    return Path("/opt/engel/models-active")


def engel_memory_root(drive: str) -> Path:
    vault_root = vault_memory_root_for_drive(drive)
    if vault_root is not None and vault_root.exists() and vault_root.is_dir():
        return vault_root
    return raw_external_memory_root(drive)


def engel_memory_path(drive: str, *parts: str) -> Path:
    path = engel_memory_root(drive)
    for part in parts:
        path = path / part
    return path


def _dedupe_paths(paths: Iterable[Path]) -> list[Path]:
    seen: set[str] = set()
    result: list[Path] = []
    for path in paths:
        key = str(path).casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return result


def model_scan_roots() -> list[Path]:
    roots: list[Path] = [ROOT / "models"]
    roots.append(Path("/opt/engel/models-active/llm"))
    roots.append(Path("/opt/engel/models-active"))
    roots.append(Path("/mnt/engel-hdd-vault/models-archive/llm"))
    return _dedupe_paths(roots)


def migration_status_payload() -> dict[str, object]:
    root = configured_vault_root()
    profile = _load_profile()
    active = profile.get("active_runtime", {})
    archive = profile.get("dell_poweredge_hdd_vault", {})
    exclusions = profile.get("permanent_exclusions", {})
    if not isinstance(active, dict):
        active = {}
    if not isinstance(archive, dict):
        archive = {}
    if not isinstance(exclusions, dict):
        exclusions = {}
    source_rows: list[dict[str, object]] = []
    vault_rows: list[dict[str, object]] = []
    for drive in SOURCE_DRIVES:
        source = raw_external_memory_root(drive)
        source_rows.append(
            {
                "drive": drive,
                "external_path": str(source),
                "external_present": source.exists() and source.is_dir(),
            }
        )
        vault_source = vault_memory_root_for_drive(drive)
        vault_rows.append(
            {
                "drive": drive,
                "vault_path": str(vault_source) if vault_source is not None else "",
                "vault_present": bool(vault_source is not None and vault_source.exists() and vault_source.is_dir()),
            }
        )
    return {
        "schema": "engel_main_vault_migration_status_v1",
        "current_runtime_mode": "CT246_SSD_ACTIVE_POWEREDGE_INTERNAL_HDD_ARCHIVE_AFTER_PROOF",
        "active_runtime_root": str(active.get("ct_mount") or ACTIVE_RUNTIME_ROOT),
        "archive_root": str(archive.get("container_mount") or ARCHIVE_ROOT),
        "archive_backend": str(archive.get("backend") or "Dell PowerEdge internal HDD RAIDZ2 ZFS pool"),
        "archive_requires_mount_proof": archive.get("archive_copy_allowed_only_after_mount_verified") is True,
        "permanent_exclusions_enforced": all(
            exclusions.get(field) is False
            for field in (
                "discovery_allowed",
                "probe_allowed",
                "mount_allowed",
                "runtime_route_allowed",
                "archive_route_allowed",
                "fallback_route_allowed",
            )
        ),
        "vault_env_var": VAULT_ENV_VAR,
        "vault_root_configured": root is not None,
        "vault_root": str(root) if root is not None else "",
        "vault_root_ready": vault_root_ready(),
        "external_sources": source_rows,
        "vault_sources": vault_rows,
        "copy_script": str(ROOT / "scripts" / "Sync-EngelModelsToCtFastSsd.ps1"),
        "set_root_script": "ENGEL_HDD_VAULT_ROOT=/mnt/engel-hdd-vault",
        "model_scan_roots": [str(path) for path in model_scan_roots()],
        "delete_source_allowed": False,
        "mirror_delete_allowed": False,
        "direct_block_device_write_allowed": False,
    }


def render_vault_migration_status() -> str:
    status = migration_status_payload()
    lines = [
        "# Engel Main CT246 Storage",
        "",
        "Status:",
        "- Current runtime mode: " + str(status["current_runtime_mode"]),
        "- Active runtime root: " + str(status["active_runtime_root"]),
        "- Internal HDD archive root configured: " + ("YES" if status["vault_root_configured"] else "NO"),
        "- Internal HDD archive root visible here: " + ("YES" if status["vault_root_ready"] else "NO"),
        "- Internal HDD archive root: " + (str(status["vault_root"]) or "rejected by allowlist"),
        "- Archive requires exact mount proof: " + ("YES" if status["archive_requires_mount_proof"] else "NO"),
        "- Permanent storage exclusions enforced: " + ("YES" if status["permanent_exclusions_enforced"] else "NO"),
        "- Runtime env var: " + VAULT_ENV_VAR,
        "",
        "Current rule:",
        "- Engel AI Main runs active services, models, memory, and training from /opt/engel.",
        "- /mnt/engel-hdd-vault is archive-only after exact mount proof.",
        "- Every undeclared or external storage route is rejected without discovery or fallback.",
    ]
    lines.extend(
        [
            "",
        "CT246 storage aliases:",
        ]
    )
    for row in status["external_sources"]:  # type: ignore[index]
        lines.append(
            f"- {row['drive']}: {row['external_path']} "
            + ("[present]" if row["external_present"] else "[missing]")
        )
    lines.extend(["", "Resolved storage roots:"])
    for row in status["vault_sources"]:  # type: ignore[index]
        lines.append(
            f"- {row['drive']}: {row['vault_path'] or 'not configured'} "
            + ("[present]" if row["vault_present"] else "[missing]")
        )
    lines.extend(
        [
            "",
            "Safety:",
            "- Copy-first only.",
            "- No source delete.",
            "- No robocopy mirror purge.",
            "- No direct block-device write.",
            "- Retired E/F/G external drives are not fallback runtime paths.",
            "",
            "Scripts:",
            "- Set root: " + str(status["set_root_script"]),
            "- Copy: " + str(status["copy_script"]),
        ]
    )
    return "\n".join(lines) + "\n"


def render_vault_migration_plan() -> str:
    return "\n".join(
        [
            "# Engel Main Vault Migration Plan",
            "",
            "Current state: use CT246 SSD and the Dell PowerEdge internal HDD only.",
            "",
            "Current SSD-only runtime:",
            "1. Keep Engel AI Main on /opt/engel.",
            "2. Keep active models under /opt/engel/models-active.",
            "3. Reject every undeclared or external storage root.",
            "",
            "Dell HDD archive plan:",
            "1. Keep active chat/runtime/model files on /opt/engel.",
            "2. Keep cold models, datasets, training outputs, and backups on /mnt/engel-hdd-vault.",
            "3. Use scripts\\Sync-EngelModelsToCtFastSsd.ps1 to copy archive models onto SSD before serving.",
            "4. Do not use retired laptop external drives as live roots.",
            "",
            "Required target shape:",
            "- /opt/engel/models-active",
            "- /mnt/engel-hdd-vault/models-archive",
            "- /mnt/engel-hdd-vault/training-outputs",
            "",
            "No retired external-array route is part of Engel AI Main.",
        ]
    ) + "\n"


if __name__ == "__main__":
    print(render_vault_migration_status())
