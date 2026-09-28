#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEGACY_PS = ROOT / "scripts" / "Run-EngelProxmoxVaultShareSetup.ps1"
LEGACY_SH = ROOT / "scripts" / "proxmox" / "setup_engel_vault_smb_share.sh"
POWEREDGE_PS = ROOT / "scripts" / "Install-EngelPowerEdgeHddVaultBind.ps1"
POWEREDGE_SH = ROOT / "scripts" / "proxmox" / "bind_engel_hdd_vault_to_ct246.sh"


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    require(path.exists() and path.is_file(), f"missing file: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8", errors="replace")


def main() -> int:
    try:
        legacy_ps = read(LEGACY_PS)
        legacy_sh = read(LEGACY_SH)
        poweredge_ps = read(POWEREDGE_PS)
        poweredge_sh = read(POWEREDGE_SH)

        legacy_token = "CREATE_ENGEL" + "_VAULT_SHARE"
        for label, text in [("legacy PowerShell", legacy_ps), ("legacy shell", legacy_sh)]:
            require("BLOCKED PERMANENTLY: CT245" in text, f"{label} must permanently hard-stop CT245")
            require("has no reactivation route" in text, f"{label} must remove reactivation language")
            require("/mnt/engel-hdd-vault" in text, f"{label} must point to Dell PowerEdge mount")
            require("/mnt/engel-vault" in text, f"{label} must name forbidden PowerVault mount")
            require("engel-vault-main:15000" not in text, f"{label} must not keep old 15 TB mount command")
            require(legacy_token not in text, f"{label} must not keep legacy approval token")

        for label, text in [("PowerEdge PowerShell", poweredge_ps), ("PowerEdge shell", poweredge_sh)]:
            require("/mnt/engel-hdd-vault" in text, f"{label} must target Dell PowerEdge mount")
            require("backup=0" in text, f"{label} must enforce backup=0")
            require("CT 245" in text or "245" in text, f"{label} must forbid CT245")
            require("/mnt/engel-vault" in text or ("/mnt/" in text and "engel-vault" in text), f"{label} must forbid retired mount")
            require("engel-vault-main" in text or ("engel-" in text and "vault-main" in text), f"{label} must forbid retired storage ID")
            require("/dev/sdc" in text or ("/dev/" in text and "sdc" in text), f"{label} must forbid retired device")

    except CheckFailure as exc:
        print("[FAIL]", exc)
        return 1

    print("PASS: legacy PowerVault migration route is blocked")
    print("- CT245 / engel-vault-share setup scripts hard-stop")
    print("- Dell PowerEdge engel-hdd-vault bind scripts remain the only staged archive route")
    print("- /mnt/engel-vault is permanently excluded with no reactivation route")
    return 0


if __name__ == "__main__":
    sys.exit(main())
