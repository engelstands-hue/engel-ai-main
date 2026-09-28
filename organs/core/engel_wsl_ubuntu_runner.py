"""Engel AI surface for the WSL Ubuntu Runtime Dependency contract (Stage 2).

Backs the ``engel.wsl_ubuntu.*`` routes registered in
``engel_ai_update_routes``. Reads the authoritative contract at
``memory/ENGEL_WSL_UBUNTU_RUNTIME_DEPENDENCY_V1.json`` so any future
amendment (Stage 3, etc.) surfaces here without code changes.

This module performs no subprocess work, no network calls, no
installs, and no source mutation. It only renders the recorded
contract — Stage 2 authorizes Engel to auto-run inside the
distro; the WSL bridge (``engel_wsl_bridge``) remains the
allowlisted execution surface.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT: Path = Path(__file__).resolve().parent
CONTRACT_JSON: Path = ROOT / "memory" / "ENGEL_WSL_UBUNTU_RUNTIME_DEPENDENCY_V1.json"
CONTRACT_MD: Path = ROOT / "memory" / "ENGEL_WSL_UBUNTU_RUNTIME_DEPENDENCY_V1.md"
REPORT_MD: Path = ROOT / "reports" / "codex_bridge" / "ENGEL_WSL_UBUNTU_RUNTIME_DEPENDENCY_V1.md"


def _load_contract() -> dict[str, Any]:
    return json.loads(CONTRACT_JSON.read_text(encoding="utf-8"))


def _safety_footer(stage2_present: bool) -> str:
    lines = [
        "Safety:",
        f"- Contract: {CONTRACT_JSON.name} (single source of truth)",
        "- Execution surface: engel_wsl_bridge (allowlisted, read-only by default).",
        "- Sandbox bring-up: ask 'engel sandbox bring up'.",
    ]
    if stage2_present:
        lines.append(
            "- Stage 2 (2026-05-20): auto-run + background workers authorized inside the distro."
        )
    else:
        lines.append("- Stage 2 block missing from contract — investigate before activation.")
    try:
        data = _load_contract()
        stage3 = data.get("stage_3_autonomy_authorization") or {}
        if stage3.get("auto_install_authorized") and stage3.get("model_loading_authorized"):
            lines.append(
                "- Stage 3 (2026-05-20): auto-install + package refresh + model hosting + model loading + inference + training "
                "authorized inside the distro. Still gated: NO_BROWSER, NO_PROVIDER_CALLS, NO_ARBITRARY_OUTBOUND_NETWORK, NO_SOURCE_MUTATION."
            )
    except Exception:
        pass
    return "\n".join(lines)


def _wrap(title: str, body: str, *, stage2_present: bool = True) -> str:
    return f"{title}\n\n{body}\n\n{_safety_footer(stage2_present)}"


def _bullet(prefix: str, value: Any) -> str:
    return f"- {prefix}: {value}"


def render_wsl_ubuntu_runtime_status(_payload: str = "") -> str:
    """Top-level status: highest authorized stage, recorded distro, current gated boundaries.

    Mirrors `engel.progress_dashboard.status` style — one-screen
    summary anyone can read to know what Engel may do in WSL Ubuntu.
    """
    data = _load_contract()
    stage2 = data.get("stage_2_autonomy_authorization") or {}
    stage3 = data.get("stage_3_autonomy_authorization") or {}
    stage2_present = bool(stage2.get("auto_run_authorized"))
    stage3_present = bool(stage3.get("auto_install_authorized"))
    highest_stage = 3 if stage3_present else (2 if stage2_present else 1)
    current_preserved = (
        stage3.get("preserved_boundaries") if stage3_present
        else stage2.get("preserved_boundaries") if stage2_present
        else []
    ) or []
    lines: list[str] = []
    lines.append(_bullet("Contract", data.get("name", "Engel WSL Ubuntu Runtime Dependency V1")))
    lines.append(_bullet("Type", data.get("type")))
    lines.append(_bullet("Highest authorized stage", highest_stage))
    if stage2_present:
        lines.append(_bullet("Stage 2 — auto-run / background workers", "AUTHORIZED"))
    if stage3_present:
        lines.append(_bullet("Stage 3 — auto-install / model hosting / inference / training", "AUTHORIZED"))
        lines.append(_bullet("Stage 3 title", stage3.get("title", "(unspecified)")))
    if stage3.get("authorized_on") or stage2.get("authorized_on"):
        lines.append(_bullet("Latest amendment date", stage3.get("authorized_on") or stage2.get("authorized_on")))
    if stage3.get("authorized_by") or stage2.get("authorized_by"):
        lines.append(_bullet("Authorized by", stage3.get("authorized_by") or stage2.get("authorized_by")))
    lines.append("")
    lines.append("Recorded distro:")
    lines.append(_bullet("Name", data.get("distro_name")))
    lines.append(_bullet("WSL version", data.get("wsl_version")))
    lines.append(_bullet("Linux user", data.get("linux_user")))
    lines.append(_bullet("Distro folder", data.get("distro_folder")))
    lines.append(_bullet("Export tar", data.get("export_tar")))
    lines.append("")
    lines.append("Still gated (require protected action gate):")
    for boundary in current_preserved:
        lines.append(f"- {boundary}")
    return _wrap("Engel WSL Ubuntu Runtime — status", "\n".join(lines), stage2_present=stage2_present)


def render_wsl_ubuntu_runtime_facts(_payload: str = "") -> str:
    """Recorded migration facts — distro name, paths, user, classification."""
    data = _load_contract()
    lines = [
        _bullet("Distro name", data.get("distro_name")),
        _bullet("WSL version", data.get("wsl_version")),
        _bullet("Linux user", data.get("linux_user")),
        _bullet("Distro folder", data.get("distro_folder")),
        _bullet("Export tar", data.get("export_tar")),
        _bullet("Runtime category", data.get("runtime_category")),
        _bullet("Engel classification", data.get("engel_classification")),
        _bullet("Not-model reason", data.get("not_model_reason")),
        "",
        "Safe future uses:",
    ]
    for use in data.get("safe_future_uses", []) or []:
        lines.append(f"- {use}")
    lines.append("")
    lines.append("Safety notes:")
    for note in data.get("safety_notes", []) or []:
        lines.append(f"- {note}")
    stage2 = data.get("stage_2_autonomy_authorization") or {}
    return _wrap(
        "Engel WSL Ubuntu Runtime — recorded facts",
        "\n".join(lines),
        stage2_present=bool(stage2.get("auto_run_authorized")),
    )


def render_wsl_ubuntu_runtime_safety(_payload: str = "") -> str:
    """Boundaries view: what Engel may do, what still needs approval."""
    data = _load_contract()
    stage2 = data.get("stage_2_autonomy_authorization") or {}
    stage3 = data.get("stage_3_autonomy_authorization") or {}
    stage2_present = bool(stage2.get("auto_run_authorized"))
    stage3_present = bool(stage3.get("auto_install_authorized"))

    lines: list[str] = []
    if stage2_present:
        lines.append("Authorized under Stage 2 (no per-invocation approval inside the distro):")
        lines.append("- auto-run (foreground processes inside the distro)")
        lines.append("- background workers inside the distro")
        lines.append("")
    if stage3_present:
        lines.append("Authorized under Stage 3 (no per-invocation approval inside the distro):")
        lines.append("- package install via apt / pip / cargo / npm / uv / pipx / rustup")
        lines.append("- package refresh")
        lines.append("- network fetch from package-manager registries and model-weight registries")
        lines.append("- AI model hosting (loading weights into local frameworks)")
        lines.append("- inference (running loaded models locally)")
        lines.append("- training / fine-tuning (LoRA / QLoRA / SFT)")
        lines.append("")
    if not (stage2_present or stage3_present):
        lines.append("(no stage authorization blocks present — contract is at baseline.)")
        lines.append("")
    current_preserved = (
        stage3.get("preserved_boundaries") if stage3_present
        else stage2.get("preserved_boundaries") if stage2_present
        else []
    ) or []
    lines.append("Still gated (require protected action gate):")
    for boundary in current_preserved:
        lines.append(f"- {boundary}")
    lines.append("")
    lines.append("Forbidden (no contract path):")
    for forbidden in data.get("forbidden_uses", []) or []:
        lines.append(f"- {forbidden}")
    lines.append("")
    lines.append("Contract status sentinels:")
    for status in data.get("status", []) or []:
        lines.append(f"- {status}")
    if stage3_present and stage3.get("scope"):
        lines.append("")
        lines.append("Stage 3 scope: " + str(stage3["scope"]))
    elif stage2_present and stage2.get("scope"):
        lines.append("")
        lines.append("Stage 2 scope: " + str(stage2["scope"]))
    return _wrap("Engel WSL Ubuntu Runtime — safety boundaries", "\n".join(lines), stage2_present=stage2_present)


def render_wsl_ubuntu_runtime_stage_2(_payload: str = "") -> str:
    """Focused Stage 2 amendment view — what changed on 2026-05-20."""
    data = _load_contract()
    stage2 = data.get("stage_2_autonomy_authorization") or {}
    stage2_present = bool(stage2.get("auto_run_authorized"))
    if not stage2_present:
        return _wrap(
            "Engel WSL Ubuntu Runtime — Stage 2 amendment (NOT FOUND)",
            "The contract does not currently declare Stage 2 autonomy. Either the JSON was reverted "
            "or the contract is pre-amendment. Read memory/ENGEL_WSL_UBUNTU_RUNTIME_DEPENDENCY_V1.json "
            "and confirm with Josh before assuming auto-run is authorized.",
            stage2_present=False,
        )
    lines = [
        _bullet("Stage", stage2.get("stage")),
        _bullet("Authorized on", stage2.get("authorized_on")),
        _bullet("Authorized by", stage2.get("authorized_by")),
        _bullet("Auto-run authorized", stage2.get("auto_run_authorized", False)),
        _bullet("Background worker authorized", stage2.get("background_worker_authorized", False)),
        "",
        "Supersedes:",
        f"- {stage2.get('supersedes', '(unspecified)')}",
        "",
        "Scope:",
        f"- {stage2.get('scope', '(unspecified)')}",
        "",
        "Preserved boundaries (still gated):",
    ]
    for boundary in stage2.get("preserved_boundaries", []) or []:
        lines.append(f"- {boundary}")
    lines.append("")
    lines.append("Related surfaces (one Engel, not scattered tools):")
    lines.append("- engel.wsl.* — allowlisted bridge for actual WSL commands.")
    lines.append("- engel.engel_sandbox.bring_up — Linux/KVM sandbox bring-up guide that depends on this distro.")
    lines.append("- engel.progress_dashboard.status — top-level Engel status.")
    return _wrap("Engel WSL Ubuntu Runtime — Stage 2 amendment", "\n".join(lines), stage2_present=True)


def render_wsl_ubuntu_runtime_stage_3(_payload: str = "") -> str:
    """Focused Stage 3 amendment view — full local AI dev environment."""
    data = _load_contract()
    stage3 = data.get("stage_3_autonomy_authorization") or {}
    stage3_present = bool(stage3.get("auto_install_authorized"))
    if not stage3_present:
        return _wrap(
            "Engel WSL Ubuntu Runtime — Stage 3 amendment (NOT FOUND)",
            "The contract does not currently declare Stage 3 autonomy. Either the JSON was reverted "
            "or the contract has not yet been amended past Stage 2. Read "
            "memory/ENGEL_WSL_UBUNTU_RUNTIME_DEPENDENCY_V1.json and confirm with Josh before assuming "
            "auto-install / model loading / inference / training is authorized.",
            stage2_present=False,
        )
    lines = [
        _bullet("Stage", stage3.get("stage")),
        _bullet("Title", stage3.get("title", "(unspecified)")),
        _bullet("Authorized on", stage3.get("authorized_on")),
        _bullet("Authorized by", stage3.get("authorized_by")),
        "",
        "Authorized capabilities (no per-invocation approval inside the distro):",
        _bullet("  - auto-install", stage3.get("auto_install_authorized", False)),
        _bullet("  - package refresh", stage3.get("package_refresh_authorized", False)),
        _bullet("  - package-manager network", stage3.get("package_manager_network_authorized", False)),
        _bullet("  - model hosting", stage3.get("model_hosting_authorized", False)),
        _bullet("  - model loading", stage3.get("model_loading_authorized", False)),
        _bullet("  - inference", stage3.get("inference_authorized", False)),
        _bullet("  - training", stage3.get("training_authorized", False)),
        "",
        "Supersedes:",
        f"- {stage3.get('supersedes', '(unspecified)')}",
        "",
        "Scope:",
        f"- {stage3.get('scope', '(unspecified)')}",
        "",
        "Package managers explicitly authorized:",
    ]
    for pm in stage3.get("package_managers_allowed", []) or []:
        lines.append(f"  - {pm}")
    lines.append("")
    lines.append("Model runtimes explicitly authorized inside the distro:")
    for runtime in stage3.get("model_runtimes_allowed_inside_distro", []) or []:
        lines.append(f"  - {runtime}")
    lines.append("")
    lines.append("Still gated inside the distro:")
    for gated in stage3.get("still_gated_in_distro", []) or []:
        lines.append(f"  - {gated}")
    lines.append("")
    lines.append("Preserved boundaries:")
    for boundary in stage3.get("preserved_boundaries", []) or []:
        lines.append(f"  - {boundary}")
    lines.append("")
    lines.append("Related surfaces (one Engel, not scattered tools):")
    lines.append("- engel.wsl.* — allowlisted bridge for actual WSL commands.")
    lines.append("- engel.engel_sandbox.bring_up — Linux/KVM sandbox bring-up guide that depends on this distro.")
    lines.append("- engel.wsl_ubuntu.stage_2 — Stage 2 amendment (auto-run authorization).")
    lines.append("- engel.progress_dashboard.status — top-level Engel status.")
    return _wrap("Engel WSL Ubuntu Runtime — Stage 3 amendment", "\n".join(lines), stage2_present=True)
