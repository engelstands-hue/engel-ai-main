#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = ROOT / "memory" / "ENGEL_STORAGE_LOCATION_REGISTRY_V1.json"
MD_PATH = ROOT / "memory" / "ENGEL_STORAGE_LOCATION_REGISTRY_V1.md"
ROUTES_PATH = ROOT / "engel_ai_update_routes.py"
ROUTE_EXPLORER_PATH = ROOT / "engel_route_explorer.py"
STORAGE_STATUS_PATH = ROOT / "engel_vault_paths.py"
CHAT_TRAINING_PATH = ROOT / "tools" / "run_engel_one_day_local_first_chat_training.py"
CHAT_RUNNER_PATH = ROOT / "tools" / "run_engel_standalone_chat_llm.py"
SUB_UPDATE_PATH = ROOT / "tools" / "update_sub_engel_desktop_from_main.py"
LEGACY_SETUP_PATHS = [
    ROOT / "scripts" / "Run-EngelProxmoxVaultShareSetup.ps1",
    ROOT / "scripts" / "proxmox" / "setup_engel_vault_smb_share.sh",
]
ACTIVE_ROOT = "/opt/engel"
ARCHIVE_ROOT = "/mnt/engel-hdd-vault"
ALLOWED_ROOTS = [ACTIVE_ROOT, ARCHIVE_ROOT]


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def main() -> int:
    try:
        require(JSON_PATH.is_file(), "registry JSON missing")
        require(MD_PATH.is_file(), "registry Markdown missing")
        data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
        markdown = MD_PATH.read_text(encoding="utf-8", errors="replace")

        require(data.get("schema") == "ENGEL_STORAGE_LOCATION_REGISTRY_V1", "schema mismatch")
        require(data.get("source_of_truth") == "Dell PowerEdge R730xd / engel-spine-01 / CT246 engel-ai-main", "source of truth mismatch")
        require(data.get("allowed_storage_roots") == ALLOWED_ROOTS, "storage allowlist mismatch")
        require(data.get("external_storage_permanently_excluded") is True, "external storage exclusion missing")
        require(data.get("reactivation_route_exists") is False, "external storage reactivation must not exist")
        exclusions = data.get("permanent_exclusions", {})
        require(
            exclusions.get("identifiers") == ["PowerVault", "CT245", "/mnt/engel-vault", "engel-vault-main"],
            "permanent external-array exclusion identifiers mismatch",
        )
        for field in [
            "discovery_allowed",
            "probe_allowed",
            "mount_allowed",
            "runtime_route_allowed",
            "archive_route_allowed",
            "fallback_route_allowed",
        ]:
            require(exclusions.get(field) is False, f"permanent exclusion field must be false: {field}")

        active = data.get("active_runtime", {})
        require(active.get("name") == "engel-fast-ssd", "active SSD name mismatch")
        require(active.get("ct_id") == 246, "active runtime CT mismatch")
        require(active.get("ct_mount") == ACTIVE_ROOT, "active runtime root mismatch")

        archive = data.get("dell_poweredge_hdd_vault", {})
        require(archive.get("backend") == "Dell PowerEdge internal HDD RAIDZ2 ZFS pool", "archive backend mismatch")
        require(archive.get("container_mount") == ARCHIVE_ROOT, "archive root mismatch")
        require(archive.get("active_inference_surface") is False, "archive cannot be active inference")
        require(archive.get("archive_copy_allowed_only_after_mount_verified") is True, "mount-proof gate missing")
        proof = archive.get("verified_findmnt", {})
        require(proof.get("target") == ARCHIVE_ROOT, "findmnt target mismatch")
        require(proof.get("source") == "engel-hdd-vault", "findmnt source mismatch")
        require(proof.get("fstype") == "zfs", "findmnt filesystem mismatch")

        training = data.get("training_storage_layout", {})
        require(training.get("active_training_root") == ACTIVE_ROOT, "training root must be CT246 SSD")
        require(str(training.get("archive_training_root", "")).startswith(ARCHIVE_ROOT + "/"), "training archive root mismatch")
        require(training.get("active_models_stay_on_ssd") is True, "active model SSD rule missing")

        safety = data.get("safety", {})
        for field in [
            "disk_format_allowed",
            "partition_mutation_allowed",
            "zfs_mutation_allowed",
            "proxmox_storage_mutation_allowed",
            "automatic_copy_move_delete_allowed",
            "external_storage_discovery_allowed",
            "undeclared_mount_allowed",
        ]:
            require(safety.get(field) is False, f"safety field must be false: {field}")
        require(safety.get("archive_write_requires_mount_proof") is True, "archive proof safety missing")

        for root in ALLOWED_ROOTS:
            require(root in markdown, f"Markdown missing allowed root: {root}")
        require("permanently outside" in markdown, "Markdown missing permanent exclusion")
        require("no reactivation route" in markdown.lower(), "Markdown missing no-reactivation rule")
        require("must not discover, probe, mount, route, archive, or fall back" in markdown, "Markdown missing permanent action ban")

        serialized = json.dumps(data, sort_keys=True).lower() + "\n" + markdown.lower()
        for forbidden in ["do_not_use_until", "reenable", "future archive candidate"]:
            require(forbidden not in serialized, f"stale reactivation language present: {forbidden}")

        routes = ROUTES_PATH.read_text(encoding="utf-8", errors="replace")
        route_explorer = ROUTE_EXPLORER_PATH.read_text(encoding="utf-8", errors="replace")
        storage_status = STORAGE_STATUS_PATH.read_text(encoding="utf-8", errors="replace")
        chat_training = CHAT_TRAINING_PATH.read_text(encoding="utf-8", errors="replace")
        chat_runner = CHAT_RUNNER_PATH.read_text(encoding="utf-8", errors="replace")
        sub_update = SUB_UPDATE_PATH.read_text(encoding="utf-8", errors="replace")

        require("engel.trusted_vault" not in routes, "retired trusted-vault route remains active")
        require("engel_trusted_vault_storage" not in routes, "retired trusted-vault module remains routed")
        require("engel.trusted_vault" not in route_explorer, "retired trusted-vault route remains visible")
        require("ENGEL_MAIN_TRUSTED_VAULT_STORAGE_V1" not in storage_status, "storage status reads retired profile")
        require("ENGEL_VAULT_OFFLINE_INTENTIONAL" not in storage_status, "storage status reads retired offline marker")
        require("PowerVault" not in storage_status, "storage status still exposes retired array")
        require("CT245" not in storage_status, "storage status still exposes retired container")
        require("PowerVault" not in chat_training, "active chat training still teaches retired array context")
        require("ENGEL_WRITE_EXTERNAL_CHAT_RECEIPTS" not in chat_runner, "chat runner still permits external receipt override")
        require("external receipt mirrors are permanently disabled" in chat_runner, "chat receipt mirror lock missing")
        require('"active_training": "/opt/engel/training"' in sub_update, "Sub-Engel training root is not on CT246 SSD")
        require('"permanently_excluded_storage"' in sub_update, "Sub-Engel permanent exclusion contract missing")
        require("forbidden_until_josh_reenables" not in sub_update, "Sub-Engel contract still has reactivation language")

        for path in LEGACY_SETUP_PATHS:
            legacy = path.read_text(encoding="utf-8", errors="replace")
            require("BLOCKED PERMANENTLY" in legacy, f"legacy setup does not fail permanently: {path.name}")
            require("has no reactivation route" in legacy, f"legacy setup retains a reactivation route: {path.name}")
    except (CheckFailure, json.JSONDecodeError) as exc:
        print("ENGEL_STORAGE_LOCATION_REGISTRY_VERIFY_FAIL")
        print(str(exc))
        return 1

    print("ENGEL_STORAGE_LOCATION_REGISTRY_VERIFY_PASS")
    print("- CT246 SSD is the only active runtime root")
    print("- Dell PowerEdge internal HDD is archive-only after exact mount proof")
    print("- external and undeclared storage is permanently excluded")
    print("- retired array routes are absent from live routing and training")
    return 0


if __name__ == "__main__":
    sys.exit(main())
