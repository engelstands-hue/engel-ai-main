#!/usr/bin/env python3
"""Build an add-on catalog package for existing Windows Sub-Engel nodes.

Merges saved Engel skills/agents onto what Sub-Engel already has.
Does not replace the standalone Sub-Engel runtime or live 7B chat.
"""
from __future__ import annotations

import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_REG = ROOT / "memory" / "skills" / "ENGEL_SAVED_SKILL_REGISTRY.json"
AGENT_REG = ROOT / "memory" / "agents" / "ENGEL_SAVED_AGENT_REGISTRY.json"
CORE_SUMMARY = ROOT / "runtime" / "next_stage" / "hermes_agent_catalog" / "IMPORT_SUMMARY.json"
OPT_SUMMARY = ROOT / "runtime" / "next_stage" / "hermes_agent_catalog" / "OPTIONAL_IMPORT_SUMMARY.json"
BUILD = ROOT / "runtime" / "package_build" / "EngelAI-SubEngel-Catalog-Addon-20260825"
ZIP_PATH = ROOT / "dist" / "EngelAI-SubEngel-Catalog-Addon-20260825.zip"
WORKFLOW_COPY = ROOT / "workflows" / "sub_engel_nodes" / "catalog_addon"
NEXT_STAGE_SKILLS = (
    "engel-playwright-mcp",
    "engel-sub-engel-reconnect",
    "engel-market-regimes",
    "engel-learn-from-demonstration",
    "engel-training-agents-factory",
    "engel-companion-3b-lane",
    "engel-local-speech-whisper-piper",
    "engel-trading-desk-disarmed",
)


def utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def copy_tree_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def main() -> int:
    skills = load_json(SKILL_REG).get("skills") or {}
    agents = load_json(AGENT_REG).get("agents") or {}
    core = load_json(CORE_SUMMARY)
    optional = load_json(OPT_SUMMARY)
    hermes_keys = sorted(k for k in skills if str(k).startswith("engel-hermes-"))
    extra_keys = [k for k in NEXT_STAGE_SKILLS if k in skills]
    skill_keys = hermes_keys + extra_keys
    agent_keys = sorted(
        k
        for k in agents
        if k not in {"skill-creator-agent"}
    )
    if BUILD.exists():
        shutil.rmtree(BUILD)
    BUILD.mkdir(parents=True)
    (BUILD / "skills").mkdir()
    (BUILD / "agents").mkdir()
    (BUILD / "memory" / "skills").mkdir(parents=True)
    (BUILD / "memory" / "agents" / "definitions").mkdir(parents=True)

    addon_skills: dict[str, object] = {}
    for key in skill_keys:
        src = ROOT / "skills" / key / "SKILL.md"
        js = ROOT / "skills" / key / "skill.json"
        if not src.is_file():
            continue
        copy_tree_file(src, BUILD / "skills" / key / "SKILL.md")
        if js.is_file():
            copy_tree_file(js, BUILD / "skills" / key / "skill.json")
        addon_skills[key] = {
            "skillKey": key,
            "name": (skills.get(key) or {}).get("name"),
            "description": (skills.get(key) or {}).get("description"),
            "created_by": (skills.get(key) or {}).get("created_by"),
        }

    addon_agents: dict[str, object] = {}
    for key in agent_keys:
        src = ROOT / "agents" / f"{key}.md"
        definition = ROOT / "memory" / "agents" / "definitions" / f"{key}.json"
        if not src.is_file():
            continue
        copy_tree_file(src, BUILD / "agents" / f"{key}.md")
        if definition.is_file():
            copy_tree_file(definition, BUILD / "memory" / "agents" / "definitions" / f"{key}.json")
        addon_agents[key] = {
            "agentKey": key,
            "name": (agents.get(key) or {}).get("name"),
            "role": (agents.get(key) or {}).get("role"),
            "created_by": (agents.get(key) or {}).get("created_by"),
        }

    (BUILD / "memory" / "skills" / "addon_skill_registry.json").write_text(
        json.dumps({"schema": "engel_sub_engel_addon_skill_registry_v1", "skills": addon_skills}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    (BUILD / "memory" / "agents" / "addon_agent_registry.json").write_text(
        json.dumps({"schema": "engel_sub_engel_addon_agent_registry_v1", "agents": addon_agents}, indent=2)
        + "\n",
        encoding="utf-8",
    )

    manifest = {
        "schema": "engel_sub_engel_catalog_addon_v1",
        "name": "Engel AI Sub-Engel Catalog Addon",
        "version": "2026.08.25",
        "branding": "Engel AI",
        "addon": True,
        "replace_existing_runtime": False,
        "merge_into_existing": True,
        "built_at_utc": utc(),
        "skill_count": len(addon_skills),
        "agent_count": len(addon_agents),
        "hermes_core_skills": len(core.get("skills_saved") or []),
        "hermes_optional_skills": len(optional.get("skills_saved") or []),
        "next_stage_skills": extra_keys,
        "safety": {
            "raw_shell": False,
            "c_drive_node_root": False,
            "provider_runtime": False,
            "live_7b_swap": False,
            "clob_posting": False,
            "background_worker_default": False,
            "trusted_memory_write": False,
        },
    }
    (BUILD / "package_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (BUILD / "README.md").write_text(
        "# Engel AI Sub-Engel Catalog Addon\n\n"
        "Add-on only. Merge these Engel-recreated skills and agents into an existing "
        "Windows Sub-Engel node. Do not replace the standalone Sub-Engel runtime, "
        "helper GGUF, or live Engel AI Main 7B chat.\n\n"
        f"- Skills in this pack: {len(addon_skills)}\n"
        f"- Agents in this pack: {len(addon_agents)}\n"
        "- Includes 89 core Hermes cards + 81 optional Hermes cards recreated for Engel, "
        "plus next-stage storage-pull skills and saved root agents.\n\n"
        "Run `Apply-EngelSubEngelCatalogAddon.cmd` on the Sub-Engel machine. "
        "It refuses C: node roots and never deletes existing skills/agents that are not in this pack.\n",
        encoding="utf-8",
    )
    apply_ps1 = r'''[CmdletBinding()]
param(
    [string]$NodeRoot = "",
    [switch]$WhatIf
)
$ErrorActionPreference = "Stop"
$AddonRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

function Test-OsDrivePath([string]$Path) {
    if (-not $Path) { return $false }
    try { $full = [System.IO.Path]::GetFullPath($Path) } catch { $full = $Path }
    return $full.StartsWith("C:\", [StringComparison]::OrdinalIgnoreCase) -or
        $full.StartsWith("\\?\C:\", [StringComparison]::OrdinalIgnoreCase)
}

function Resolve-NodeRoot([string]$Candidate) {
    foreach ($choice in @($Candidate, $env:ENGEL_WINDOWS_SUB_NODE_ROOT)) {
        if (-not $choice) { continue }
        if (Test-OsDrivePath $choice) { throw "Refusing Sub-Engel NodeRoot on C:. Use a non-C path." }
        return $choice
    }
    foreach ($drive in (Get-PSDrive -PSProvider FileSystem | Where-Object { $_.Name -ne "C" } | Sort-Object Name)) {
        $guess = Join-Path $drive.Root "EngelWindowsSubNode"
        if (Test-Path -LiteralPath $guess) { return $guess }
    }
    foreach ($drive in (Get-PSDrive -PSProvider FileSystem | Where-Object { $_.Name -ne "C" } | Sort-Object Name)) {
        if ($drive.Root) { return (Join-Path $drive.Root "EngelWindowsSubNode") }
    }
    throw "No non-C filesystem drive found for Sub-Engel."
}

$root = Resolve-NodeRoot $NodeRoot
$skillsDest = Join-Path $root "skills"
$agentsDest = Join-Path $root "agents"
$receiptsDest = Join-Path $root "receipts"
$memoryDest = Join-Path $root "memory"
New-Item -ItemType Directory -Force -Path $skillsDest, $agentsDest, $receiptsDest, (Join-Path $memoryDest "skills"), (Join-Path $memoryDest "agents") | Out-Null

$copiedSkills = 0
$copiedAgents = 0
Get-ChildItem -LiteralPath (Join-Path $AddonRoot "skills") -Directory | ForEach-Object {
    $dest = Join-Path $skillsDest $_.Name
    if ($WhatIf) { Write-Output "WOULD merge skill $($_.Name)"; return }
    Copy-Item -LiteralPath $_.FullName -Destination $dest -Recurse -Force
    $copiedSkills++
}
Get-ChildItem -LiteralPath (Join-Path $AddonRoot "agents") -Filter "*.md" | ForEach-Object {
    $dest = Join-Path $agentsDest $_.Name
    if ($WhatIf) { Write-Output "WOULD merge agent $($_.Name)"; return }
    Copy-Item -LiteralPath $_.FullName -Destination $dest -Force
    $copiedAgents++
}

function Merge-JsonMap([string]$SrcFile, [string]$DestFile, [string]$MapKey) {
    $src = Get-Content -LiteralPath $SrcFile -Raw | ConvertFrom-Json
    $destObj = @{ schema = $src.schema; $MapKey = @{} }
    if (Test-Path -LiteralPath $DestFile) {
        $existing = Get-Content -LiteralPath $DestFile -Raw | ConvertFrom-Json
        if ($existing.$MapKey) {
            $existing.$MapKey.PSObject.Properties | ForEach-Object { $destObj[$MapKey][$_.Name] = $_.Value }
        }
    }
    if ($src.$MapKey) {
        $src.$MapKey.PSObject.Properties | ForEach-Object { $destObj[$MapKey][$_.Name] = $_.Value }
    }
    ($destObj | ConvertTo-Json -Depth 12) | Set-Content -LiteralPath $DestFile -Encoding UTF8
}

if (-not $WhatIf) {
    Merge-JsonMap (Join-Path $AddonRoot "memory\skills\addon_skill_registry.json") (Join-Path $memoryDest "skills\ENGEL_SAVED_SKILL_REGISTRY.json") "skills"
    Merge-JsonMap (Join-Path $AddonRoot "memory\agents\addon_agent_registry.json") (Join-Path $memoryDest "agents\ENGEL_SAVED_AGENT_REGISTRY.json") "agents"
    $stamp = Get-Date -Format "yyyyMMddTHHmmssZ"
    $receipt = [ordered]@{
        schema = "engel_sub_engel_catalog_addon_apply_v1"
        ok = $true
        node_root = $root
        copied_skills = $copiedSkills
        copied_agents = $copiedAgents
        replace_existing_runtime = $false
        applied_at_local = $stamp
    }
    $receiptPath = Join-Path $receiptsDest "ENGEL_SUB_ENGEL_CATALOG_ADDON_APPLIED_$stamp.json"
    ($receipt | ConvertTo-Json -Depth 6) | Set-Content -LiteralPath $receiptPath -Encoding UTF8
    Write-Output "Merged $copiedSkills skills and $copiedAgents agents into $root"
    Write-Output "Receipt $receiptPath"
}
'''
    (BUILD / "Apply-EngelSubEngelCatalogAddon.ps1").write_text(apply_ps1, encoding="utf-8")
    (BUILD / "Apply-EngelSubEngelCatalogAddon.cmd").write_text(
        "@echo off\r\n"
        "powershell -NoProfile -ExecutionPolicy Bypass -File \"%~dp0Apply-EngelSubEngelCatalogAddon.ps1\" %*\r\n",
        encoding="utf-8",
    )

    ROOT.joinpath("dist").mkdir(parents=True, exist_ok=True)
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(BUILD.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(BUILD).as_posix())

    if WORKFLOW_COPY.exists():
        shutil.rmtree(WORKFLOW_COPY)
    shutil.copytree(BUILD, WORKFLOW_COPY)
    print(json.dumps({
        "ok": True,
        "zip": str(ZIP_PATH),
        "zip_bytes": ZIP_PATH.stat().st_size,
        "skill_count": len(addon_skills),
        "agent_count": len(addon_agents),
        "workflow_copy": str(WORKFLOW_COPY),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
