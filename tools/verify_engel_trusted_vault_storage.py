#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "engel_trusted_vault_storage.py"
ROUTES = ROOT / "engel_ai_update_routes.py"
EXPLORER = ROOT / "engel_route_explorer.py"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    spec = importlib.util.spec_from_file_location("engel_storage_compat_verify", MODULE)
    require(spec is not None and spec.loader is not None, "storage compatibility module could not load")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_storage_compat_verify"] = module
    spec.loader.exec_module(module)

    status = module.trusted_vault_status_payload()
    require(status.get("ok") is True, "CT246 storage policy is invalid")
    require(status.get("active_runtime_root") == "/opt/engel", "active runtime is not CT246 SSD")
    require(status.get("archive_root") == "/mnt/engel-hdd-vault", "internal HDD archive root mismatch")
    require(status.get("archive_requires_exact_mount_proof") is True, "archive mount-proof gate missing")
    require(status.get("external_storage_permanently_excluded") is True, "permanent exclusion missing")
    require(status.get("automatic_storage_mutation_allowed") is False, "automatic storage mutation enabled")

    routes = ROUTES.read_text(encoding="utf-8", errors="replace")
    explorer = EXPLORER.read_text(encoding="utf-8", errors="replace")
    require("engel.trusted_vault" not in routes, "legacy storage route remains active")
    require("engel_trusted_vault_storage" not in routes, "compatibility module remains actively routed")
    require("engel.trusted_vault" not in explorer, "legacy storage group remains visible")

    print("ENGEL_CT246_STORAGE_COMPAT_VERIFY_PASS")
    print("- compatibility module exposes only CT246 SSD and PowerEdge internal HDD policy")
    print("- no legacy storage route is active")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
