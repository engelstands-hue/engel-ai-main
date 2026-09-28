#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLUSTER_JSON = ROOT / "memory" / "ENGEL_AI_MAIN_CLUSTER_BUILD_STATE_V1.json"
CLUSTER_MD = ROOT / "memory" / "ENGEL_AI_MAIN_CLUSTER_BUILD_STATE_V1.md"
TRUSTED_VAULT_JSON = ROOT / "memory" / "ENGEL_MAIN_TRUSTED_VAULT_STORAGE_V1.json"
REGISTRY_JSON = ROOT / "memory" / "ENGEL_STORAGE_LOCATION_REGISTRY_V1.json"
OFFLINE_MARKER_JSON = ROOT / "memory" / "ENGEL_VAULT_OFFLINE_INTENTIONAL_SSD_ONLY_20260630.json"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_AI_MAIN_CLUSTER_BUILD_STATE_20260628.md"


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    require(path.exists() and path.is_file(), "missing required file: " + str(path.relative_to(ROOT)))
    return path.read_text(encoding="utf-8", errors="replace")


def load_json(path: Path) -> dict:
    data = json.loads(read(path))
    require(isinstance(data, dict), "JSON must be an object: " + str(path.relative_to(ROOT)))
    return data


def _require_all_false(flags: dict, allowed_true: set[str] | None = None) -> None:
    allowed_true = allowed_true or set()
    for key, value in flags.items():
        if key in allowed_true:
            require(value is True, "safety flag must be true: " + key)
        else:
            require(value is False, "safety flag must be false: " + key)


def check_cluster_record() -> None:
    data = load_json(CLUSTER_JSON)
    text = read(CLUSTER_MD)
    require(data.get("schema") == "ENGEL_AI_MAIN_CLUSTER_BUILD_STATE_V1", "schema mismatch")
    require("SSD_ONLY_RUNTIME" in str(data.get("status")), "status missing SSD_ONLY_RUNTIME")
    require("POWEREDGE_HDD_ARCHIVE_ACTIVE_VERIFIED" in str(data.get("status")), "status missing PowerEdge HDD active verified")
    require("VAULT_OFFLINE_INTENTIONAL" in str(data.get("status")), "status missing Vault offline marker")
    require(data.get("runtime_effect") == "REFERENCE_ONLY / SSD_ONLY_RUNTIME / POWEREDGE_HDD_ARCHIVE_ACTIVE_VERIFIED / NO_POWERVAULT_USE / NO_AUTOMATIC_ACTION", "runtime effect mismatch")
    require(data.get("vault_availability") == "VAULT_OFFLINE_INTENTIONAL / DO_NOT_USE_UNTIL_JOSH_REENABLES", "vault availability mismatch")

    host = data.get("proxmox_host")
    require(isinstance(host, dict), "proxmox_host missing")
    require(host.get("hostname") == "engel-spine-01", "Proxmox hostname mismatch")
    require(host.get("lan_ip") == "192.0.2.50", "Proxmox LAN IP mismatch")
    require(host.get("web_ui") == "https://192.0.2.50:8006/", "Proxmox web UI mismatch")
    require(host.get("direct_ssh") == "ssh root@192.0.2.50", "Proxmox SSH route mismatch")

    queen = data.get("queen_controller")
    require(isinstance(queen, dict), "queen_controller missing")
    require(queen.get("ssh_to_engel_ai_main") == "ssh root@192.0.2.50 -p 24622", "ROG CT SSH route mismatch")

    ct = data.get("engel_ai_main_ct")
    require(isinstance(ct, dict), "engel_ai_main_ct missing")
    require(ct.get("ct_id") == 246, "CT ID mismatch")
    require(ct.get("hostname") == "engel-ai-main", "CT hostname mismatch")
    require(ct.get("internal_ip_cidr") == "10.246.0.2/24", "CT internal IP mismatch")
    require(ct.get("runtime_storage") == "engel-fast-ssd", "runtime storage mismatch")
    require(ct.get("python_virtual_environment") == "/opt/engel/.venv", "venv mismatch")

    layout = data.get("runtime_layout")
    require(isinstance(layout, dict), "runtime layout missing")
    for path in [
        "/opt/engel",
        "/opt/engel/.venv",
        "/opt/engel/core",
        "/opt/engel/memory",
        "/opt/engel/models-active",
        "/opt/engel/cache",
        "/opt/engel/logs",
        "/opt/engel/run",
        "/opt/engel/scripts",
    ]:
        require(path in layout, "runtime layout missing: " + path)
    require("OFFLINE_INTENTIONAL_BY_JOSH" in str(layout.get("/mnt/engel-vault")), "vault mount must be marked offline")
    require("ACTIVE_MOUNT_VERIFIED" in str(layout.get("/mnt/engel-hdd-vault")), "PowerEdge HDD vault must be active verified")

    hdd = data.get("dell_poweredge_hdd_vault")
    require(isinstance(hdd, dict), "Dell PowerEdge HDD vault record missing")
    require(hdd.get("name") == "engel-hdd-vault", "Dell PowerEdge HDD vault name mismatch")
    require(hdd.get("container_mount") == "/mnt/engel-hdd-vault", "Dell PowerEdge HDD mount mismatch")
    require("ACTIVE_MOUNT_VERIFIED" in str(hdd.get("status")), "Dell PowerEdge HDD active status mismatch")
    verified = hdd.get("verified_findmnt")
    require(isinstance(verified, dict), "Dell PowerEdge verified findmnt missing")
    require(verified.get("target") == "/mnt/engel-hdd-vault", "Dell PowerEdge verified target mismatch")
    require(verified.get("source") == "engel-hdd-vault", "Dell PowerEdge verified source mismatch")
    require(verified.get("fstype") == "zfs", "Dell PowerEdge verified fstype mismatch")
    require(verified.get("safe_for_archive_writes") is True, "Dell PowerEdge archive safety mismatch")
    require(hdd.get("ct_id") == 246, "Dell PowerEdge HDD target CT mismatch")
    require(hdd.get("backup_flag_required") == "backup=0", "Dell PowerEdge backup flag mismatch")
    require(hdd.get("normal_proxmox_ct_backups_include_mount") is False, "Dell PowerEdge backup policy mismatch")
    require("CT 245" in hdd.get("must_not_use", []), "Dell PowerEdge must forbid CT 245")
    require("/mnt/engel-vault" in hdd.get("must_not_use", []), "Dell PowerEdge must forbid offline PowerVault mountpoint")

    storage = data.get("powervault_storage")
    require(isinstance(storage, dict), "powervault_storage missing")
    require(storage.get("status") == "OFFLINE_INTENTIONAL_BY_JOSH / DO_NOT_PROBE_OR_USE", "PowerVault status mismatch")
    require(storage.get("use_allowed_now") is False, "PowerVault use must be disabled")
    require(storage.get("mount_allowed_now") is False, "PowerVault mount must be disabled")
    require(storage.get("health_probe_required") is False, "PowerVault probe must not be required")
    require(storage.get("do_not_use_mountpoint") == "/mnt/engel-vault", "PowerVault mountpoint mismatch")
    historical = storage.get("last_confirmed_before_offline")
    require(isinstance(historical, dict), "historical PowerVault record missing")
    require(historical.get("device") == "/dev/sdc", "historical device mismatch")
    require(historical.get("proxmox_storage_id") == "engel-vault-main", "historical storage ID mismatch")
    require(historical.get("vg") == "engel-vault-vg", "historical VG mismatch")
    require(historical.get("thinpool") == "engel-vault-thin", "historical thinpool mismatch")
    path = historical.get("confirmed_iscsi_path")
    require(isinstance(path, dict), "historical iSCSI path missing")
    require(path.get("proxmox_ip_cidr") == "192.168.130.10/24", "historical iSCSI source IP mismatch")
    require(path.get("target") == "192.168.130.101:3260", "historical iSCSI target mismatch")

    suspended = data.get("suspended_storage_task")
    require(isinstance(suspended, dict), "suspended_storage_task missing")
    require(suspended.get("status") == "SUSPENDED_BY_JOSH_VAULT_OFFLINE_FOR_MONTHS", "suspended status mismatch")
    require(suspended.get("preferred_operator_command_plan") == [], "suspended command plan must be empty")

    commands = data.get("ssd_only_health_checks")
    require(isinstance(commands, list), "SSD-only health checks missing")
    require("pct exec 246 -- df -h /opt/engel" in commands, "SSD df check missing")
    require("pct exec 246 -- findmnt -T /mnt/engel-hdd-vault" in commands, "PowerEdge HDD findmnt check missing")
    require("pct exec 246 -- df -hT /mnt/engel-hdd-vault" in commands, "PowerEdge HDD df check missing")
    require("ssh root@192.0.2.50 -p 24622" in commands, "ROG CT SSH check missing")

    joined_commands = "\n".join(str(item) for item in commands)
    for forbidden in ["iscsiadm", "/dev/sdc", "vgs ", "lvs ", "multipath", "engel-vault-main:15000"]:
        require(forbidden not in joined_commands, "SSD health checks must not probe Vault: " + forbidden)

    safety = data.get("safety")
    require(isinstance(safety, dict), "safety missing")
    _require_all_false(safety, {"server_ssd_only_runtime"})

    for needle in [
        "SSD_ONLY_RUNTIME",
        "VAULT_OFFLINE_INTENTIONAL",
        "CT ID: `246`",
        "engel-ai-main",
        "ssh root@192.0.2.50 -p 24622",
        "/opt/engel",
        "/opt/engel/models-active",
        "/mnt/engel-vault",
        "/mnt/engel-hdd-vault",
        "SUSPENDED_BY_JOSH_VAULT_OFFLINE_FOR_MONTHS",
        "Do not use",
    ]:
        require(needle in text, "cluster markdown missing: " + needle)


def check_cross_records() -> None:
    cluster = load_json(CLUSTER_JSON)
    trusted = load_json(TRUSTED_VAULT_JSON)
    registry = load_json(REGISTRY_JSON)
    marker = load_json(OFFLINE_MARKER_JSON)

    require("VAULT_OFFLINE_INTENTIONAL" in str(marker.get("status")), "offline marker status mismatch")
    require(marker.get("vault", {}).get("use_allowed_now") is False, "offline marker must disable Vault use")

    trusted_ct = trusted.get("engel_ai_main_ct")
    require(isinstance(trusted_ct, dict), "trusted vault CT record missing")
    require(trusted_ct.get("ct_id") == cluster["engel_ai_main_ct"]["ct_id"], "trusted vault CT ID mismatch")
    require("VAULT_OFFLINE_INTENTIONAL" in str(trusted.get("status")), "trusted vault status mismatch")
    require(trusted.get("storage", {}).get("availability_status") == "OFFLINE_INTENTIONAL_BY_JOSH", "trusted vault availability mismatch")
    require(trusted.get("suspended_vault_mount", {}).get("status") == "SUSPENDED_BY_JOSH_VAULT_OFFLINE", "trusted vault suspended mount mismatch")

    registry_ct = registry.get("confirmed_engel_ai_main_server_build")
    require(isinstance(registry_ct, dict), "registry cluster record missing")
    require(registry_ct.get("ct_id") == 246, "registry CT ID mismatch")
    require(registry_ct.get("runtime_storage") == "engel-fast-ssd", "registry CT storage mismatch")
    require(registry_ct.get("rog_ssh_to_ct") == "ssh root@192.0.2.50 -p 24622", "registry ROG SSH mismatch")
    require("VAULT_OFFLINE_INTENTIONAL" in str(registry_ct.get("status")), "registry CT status mismatch")
    require("ACTIVE_MOUNT_VERIFIED" in str(registry_ct.get("runtime_layout", {}).get("/mnt/engel-hdd-vault")), "registry PowerEdge HDD active mount mismatch")


def check_report() -> None:
    text = read(REPORT)
    for needle in [
        "Engel AI Main Cluster Build State",
        "SSD_ONLY_RUNTIME",
        "POWEREDGE_HDD_ARCHIVE_ACTIVE_VERIFIED",
        "VAULT_OFFLINE_INTENTIONAL",
        "CT `246`",
        "engel-ai-main",
        "ssh root@192.0.2.50 -p 24622",
        "/opt/engel",
        "/mnt/engel-vault",
        "/mnt/engel-hdd-vault",
        "backup=0",
        "No storage mutation",
        "Verification",
    ]:
        require(needle in text, "report missing: " + needle)


def main() -> int:
    checks = [
        ("cluster_record", check_cluster_record),
        ("cross_records", check_cross_records),
        ("report", check_report),
    ]
    failures: list[str] = []
    for name, fn in checks:
        try:
            fn()
            print("PASS", name)
        except CheckFailure as exc:
            failures.append(f"{name}: {exc}")
            print("FAIL", name, exc)
    if failures:
        print("ENGEL_AI_MAIN_CLUSTER_BUILD_STATE_VERIFY_FAIL")
        for failure in failures:
            print("-", failure)
        return 1
    print("ENGEL_AI_MAIN_CLUSTER_BUILD_STATE_VERIFY_PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
