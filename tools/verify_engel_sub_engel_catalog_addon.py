#!/usr/bin/env python3
"""Verify the Sub-Engel catalog add-on package merges, not replaces."""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ZIP_PATH = ROOT / "dist" / "EngelAI-SubEngel-Catalog-Addon-20260825.zip"
BUILD = ROOT / "runtime" / "package_build" / "EngelAI-SubEngel-Catalog-Addon-20260825"
CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""))


def main() -> int:
    check("zip_exists", ZIP_PATH.is_file(), str(ZIP_PATH))
    check("build_exists", BUILD.is_dir())
    manifest = json.loads((BUILD / "package_manifest.json").read_text(encoding="utf-8"))
    check("addon_flag", manifest.get("addon") is True)
    check("merge_flag", manifest.get("merge_into_existing") is True)
    check("no_replace_runtime", manifest.get("replace_existing_runtime") is False)
    check("no_c_drive", manifest.get("safety", {}).get("c_drive_node_root") is False)
    check("no_live_7b", manifest.get("safety", {}).get("live_7b_swap") is False)
    check("skills_178_or_more", int(manifest.get("skill_count") or 0) >= 178, str(manifest.get("skill_count")))
    check("agents_61_or_more", int(manifest.get("agent_count") or 0) >= 61, str(manifest.get("agent_count")))
    apply = (BUILD / "Apply-EngelSubEngelCatalogAddon.ps1").read_text(encoding="utf-8")
    check("apply_refuses_c", "Refusing Sub-Engel NodeRoot on C:" in apply)
    check("apply_merges", "Copy-Item" in apply and "Merge-JsonMap" in apply)
    check("readme_addon", "Add-on only" in (BUILD / "README.md").read_text(encoding="utf-8"))
    with zipfile.ZipFile(ZIP_PATH) as zf:
        names = zf.namelist()
    check("zip_has_apply", "Apply-EngelSubEngelCatalogAddon.ps1" in names)
    check("zip_no_gguf", not any(n.lower().endswith(".gguf") for n in names))
    check("zip_no_gateway", not any("gateway.json" in n.lower() for n in names))
    hermes = [n for n in names if n.startswith("skills/engel-hermes-") and n.endswith("SKILL.md")]
    check("zip_hermes_170", len(hermes) == 170, str(len(hermes)))
    check("zip_optional_hyperliquid", "skills/engel-hermes-hyperliquid/SKILL.md" in names)
    check("zip_optional_unsloth", "skills/engel-hermes-unsloth/SKILL.md" in names)
    check("zip_playwright", "skills/engel-playwright-mcp/SKILL.md" in names)
    check("zip_prototyper", "agents/engel-prototyper.md" in names)
    check("zip_backend_agent", "agents/engel-backend-architect.md" in names)
    standalone = ROOT / "dist" / "EngelAI-SubEngel-Standalone-20260607.zip"
    check("did_not_replace_standalone_zip", standalone.is_file() or not ZIP_PATH.samefile(standalone) if standalone.exists() else True)
    failed = [name for name, ok, _ in CHECKS if not ok]
    print("RESULT " + ("PASS" if not failed else "FAIL") + f" {len(CHECKS) - len(failed)}/{len(CHECKS)}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
