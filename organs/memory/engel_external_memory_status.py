"""Read-only CT246 SSD and Dell HDD storage status surfaces."""

from __future__ import annotations

import json
from pathlib import Path

from engel_vault_paths import engel_memory_path, engel_memory_root


ROOTS: dict[str, Path] = {
    "CT246_SSD": engel_memory_root("F"),
    "CT246_MODELS": engel_memory_root("G"),
    "DELL_HDD": engel_memory_root("E"),
}

COMPAT_ALIAS = {
    "E": "DELL_HDD",
    "F": "CT246_SSD",
    "G": "CT246_MODELS",
}


def _llama_candidates() -> Path:
    return engel_memory_path("F", "runtime", "llama.cpp", "candidates")


def _root_status(name: str, root: Path) -> dict[str, object]:
    if not root.exists():
        return {"name": name, "root": str(root), "present": False}
    manifest_path = root / "ENGEL_MEMORY_ROOT_MANIFEST.json"
    manifest: dict[str, object] = {}
    if manifest_path.exists():
        try:
            loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                manifest = loaded
        except Exception:
            manifest = {}
    folders = sorted(
        child.name for child in root.iterdir() if child.is_dir() and not child.name.startswith(".")
    )
    gguf_count = sum(1 for _ in root.rglob("*.gguf"))
    return {
        "name": name,
        "root": str(root),
        "present": True,
        "role": manifest.get("role", "unknown"),
        "scan_policy": manifest.get("scan_policy", "NO_BROAD_SCAN"),
        "trusted_memory_write": manifest.get("trusted_memory_write", "disabled"),
        "folders": folders,
        "gguf_count": gguf_count,
    }


def _size_mb(path: Path) -> float:
    try:
        return round(path.stat().st_size / (1024 * 1024), 1)
    except OSError:
        return 0.0


def render_external_memory_status() -> str:
    lines = ["# Engel CT246 / Dell Storage Status", ""]
    present: list[str] = []
    missing: list[str] = []
    for name, root in ROOTS.items():
        status = _root_status(name, root)
        if status["present"]:
            present.append(name)
            folders = status.get("folders", [])
            folder_text = ", ".join(str(item) for item in list(folders)[:10]) if isinstance(folders, list) else ""
            lines.extend(
                [
                    f"## {name} {root} [PRESENT]",
                    f"  Role:          {status['role']}",
                    f"  Scan policy:   {status['scan_policy']}",
                    f"  Trusted write: {status['trusted_memory_write']}",
                    f"  GGUF models:   {status['gguf_count']}",
                    f"  Folders:       {folder_text}",
                    "",
                ]
            )
        else:
            missing.append(name)
            lines.extend([f"## {name} {root} [NOT FOUND]", ""])
    lines.extend(
        [
            f"Roots present:  {', '.join(present) or 'none'}",
            f"Roots missing:  {', '.join(missing) or 'none'}",
        ]
    )
    return "\n".join(lines)


def render_external_memory_models() -> str:
    lines = ["# Engel CT246 / Dell GGUF Models", ""]
    total = 0
    for name, root in ROOTS.items():
        if not root.exists():
            continue
        ggufs = sorted(root.rglob("*.gguf"))
        if not ggufs:
            continue
        lines.extend([f"## {name} {root} ({len(ggufs)} models)", ""])
        for model in ggufs:
            lines.append(f"  {model.relative_to(root)}  ({_size_mb(model)} MB)")
            total += 1
        lines.append("")
    if total == 0:
        lines.extend(
            [
                "No GGUF models found on approved CT246/Dell roots.",
                "Expected active models under /opt/engel/models-active.",
            ]
        )
    else:
        lines.append(f"Total GGUF files: {total}")
    lines.extend(["", "To load a model:  engel models load <slug>", "To list slugs:    engel models list"])
    return "\n".join(lines)


def render_external_memory_runtimes() -> str:
    lines = ["# Engel CT246 Runtime Candidates", ""]
    candidates_root = _llama_candidates()
    if not candidates_root.exists():
        lines.extend(
            [
                f"{candidates_root} not found.",
                "",
                "Expected CT246 path:",
                "  /opt/engel/runtime/llama.cpp/candidates/llama-b9198-bin-win-cpu-x64/llama-cli",
            ]
        )
        return "\n".join(lines)
    candidates = sorted(child for child in candidates_root.iterdir() if child.is_dir())
    lines.extend([f"Found {len(candidates)} runtime candidate(s) in {candidates_root}:", ""])
    for candidate in candidates:
        exes = sorted(candidate.glob("*.exe"))
        dlls = sorted(candidate.glob("*.dll"))
        has_cli = (candidate / "llama-cli.exe").exists() or (candidate / "llama-cli").exists()
        lines.append(f"  [{candidate.name}]")
        lines.append(f"    exe: {len(exes)}  dll: {len(dlls)}  llama-cli: {'YES' if has_cli else 'NO'}")
        if has_cli:
            cli = candidate / "llama-cli.exe"
            lines.append(f"    path: {cli if cli.exists() else candidate / 'llama-cli'}")
        lines.append("")
    return "\n".join(lines)


def render_external_memory_archive_shelf(drive: str) -> str:
    alias = COMPAT_ALIAS.get(drive.upper(), drive.upper())
    root = ROOTS.get(alias)
    if root is None:
        return f"Unknown storage alias: {drive}. Expected E/F/G compatibility alias or CT246_SSD/CT246_MODELS/DELL_HDD."
    if not root.exists():
        return f"# {alias} {root} - NOT FOUND"
    lines = [f"# {alias} {root}", ""]
    numbered = sorted(child for child in root.iterdir() if child.is_dir() and child.name[:2].isdigit())
    other = sorted(
        child for child in root.iterdir() if child.is_dir() and not child.name[:2].isdigit() and not child.name.startswith(".")
    )
    for child in numbered:
        files = list(child.glob("*"))
        subdirs = [item for item in files if item.is_dir()]
        filecount = len([item for item in files if item.is_file()])
        lines.append(f"  {child.name}/  ({filecount} files, {len(subdirs)} subdirs)")
    if other:
        lines.extend(["", "  Other folders:"])
        for child in other:
            lines.append(f"    {child.name}/")
    return "\n".join(lines)


def render_e_drive_status() -> str:
    return render_external_memory_archive_shelf("E")


def render_f_drive_status() -> str:
    return render_external_memory_archive_shelf("F")


def render_g_drive_status() -> str:
    return render_external_memory_archive_shelf("G")
