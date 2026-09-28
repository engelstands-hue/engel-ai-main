from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
REGISTRY_JSON = ROOT / "memory" / "ENGEL_STORAGE_LOCATION_REGISTRY_V1.json"


def load_registry() -> dict[str, Any]:
    data = json.loads(REGISTRY_JSON.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Engel storage registry must be a JSON object")
    return data


def trusted_vault_status_payload() -> dict[str, Any]:
    """Compatibility entrypoint that exposes only the current CT246 allowlist."""
    registry = load_registry()
    active = registry.get("active_runtime", {})
    archive = registry.get("dell_poweredge_hdd_vault", {})
    exclusions = registry.get("permanent_exclusions", {})
    excluded = isinstance(exclusions, dict) and all(
        exclusions.get(field) is False
        for field in (
            "discovery_allowed",
            "probe_allowed",
            "mount_allowed",
            "runtime_route_allowed",
            "archive_route_allowed",
            "fallback_route_allowed",
        )
    )
    return {
        "schema": "engel_ct246_storage_status_v1",
        "ok": bool(
            isinstance(active, dict)
            and active.get("ct_id") == 246
            and active.get("ct_mount") == "/opt/engel"
            and isinstance(archive, dict)
            and archive.get("container_mount") == "/mnt/engel-hdd-vault"
            and archive.get("archive_copy_allowed_only_after_mount_verified") is True
            and excluded
        ),
        "source_of_truth": registry.get("source_of_truth"),
        "active_runtime_root": active.get("ct_mount") if isinstance(active, dict) else "",
        "active_runtime_storage": active.get("name") if isinstance(active, dict) else "",
        "archive_root": archive.get("container_mount") if isinstance(archive, dict) else "",
        "archive_backend": archive.get("backend") if isinstance(archive, dict) else "",
        "archive_requires_exact_mount_proof": (
            archive.get("archive_copy_allowed_only_after_mount_verified") is True
            if isinstance(archive, dict)
            else False
        ),
        "external_storage_permanently_excluded": excluded,
        "automatic_storage_mutation_allowed": False,
    }


def render_status() -> str:
    status = trusted_vault_status_payload()
    return "\n".join(
        [
            "# Engel AI Main CT246 Storage",
            "",
            f"- Policy valid: {'YES' if status['ok'] else 'NO'}",
            f"- Active runtime: {status['active_runtime_root']} on {status['active_runtime_storage']}",
            f"- Internal HDD archive: {status['archive_root']}",
            f"- Archive backend: {status['archive_backend']}",
            "- Archive writes require exact mount proof: YES",
            "- External and undeclared storage is permanently excluded.",
            "- Automatic storage mutation: NO",
        ]
    ) + "\n"


def render_profile() -> str:
    return render_status()


def render_health_commands() -> str:
    return "\n".join(
        [
            "# CT246 Storage Health Commands",
            "",
            "Run on CT246 when read-only proof is required:",
            "- findmnt -T /opt/engel",
            "- findmnt -no TARGET,SOURCE,FSTYPE /mnt/engel-hdd-vault",
            "- df -h /opt/engel /mnt/engel-hdd-vault",
            "",
            "No discovery, mount, storage creation, or mutation command is included.",
        ]
    ) + "\n"
