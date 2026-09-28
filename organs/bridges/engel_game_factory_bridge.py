"""Engel Agent Meeting Room bridge for Game Factory refinement.

Game Factory mirrors the local Code Factory pattern, but it is scoped to
playable game artifacts that Engel already creates. It stages a refinement
packet for the Meeting Room, records the latest playable target, and returns a
bounded builder-ready report. It does not fetch third-party game assets, call a
provider API, or mutate source by itself.
"""

from __future__ import annotations

import datetime as _dt
import json
import re
from pathlib import Path
from typing import Any


ENGEL_APP_ROOT = Path(__file__).resolve().parent
ARTIFACT_ROOT = ENGEL_APP_ROOT / "artifacts" / "engel_ui_results"
BRIDGE_RUNTIME = ENGEL_APP_ROOT / "runtime" / "meeting_room" / "game_factory"
BRIDGE_LABEL = "Game Factory Scout (Engel Meeting Room)"


def _safe_id(text: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(text or "").strip())
    return cleaned.strip("_")[:90] or "game_factory_refinement"


def _title_from_prompt(prompt: str) -> str:
    for line in str(prompt or "").splitlines():
        clean = line.strip().strip("#").strip()
        if clean:
            return clean[:110]
    return "Game Factory refinement order"


def is_game_factory_refinement_request(prompt: str) -> bool:
    low = str(prompt or "").lower()
    return (
        "game factory" in low
        or "refine game" in low
        or "game refinement" in low
        or "longer stages" in low
        or "better controls" in low
        or "polish controls" in low
        or "weapon cycling" in low
    )


def _latest_game_artifact() -> Path | None:
    if not ARTIFACT_ROOT.exists():
        return None
    candidates: list[Path] = []
    for path in ARTIFACT_ROOT.iterdir():
        if not path.is_dir():
            continue
        if (path / "index.html").is_file() and (path / "game.js").is_file():
            candidates.append(path)
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: item.stat().st_mtime)[-1]


def _extract_game_metrics(game_js: str) -> dict[str, Any]:
    def number(name: str, fallback: int) -> int:
        match = re.search(rf"const\s+{re.escape(name)}\s*=\s*(\d+)", game_js)
        return int(match.group(1)) if match else fallback

    return {
        "stage_count": number("STAGE_COUNT", 0),
        "parts_per_stage": number("PARTS_PER_STAGE", 0),
        "part_width": number("PART_WIDTH", 0),
        "has_dash": "dashCd" in game_js and "dash" in game_js,
        "has_jump_buffer": "jumpBufferMs" in game_js or "jumpBuffer" in game_js,
        "has_coyote_time": "coyoteMs" in game_js or "coyote" in game_js,
        "has_weapon_cycle": "cycleWeapon" in game_js,
        "has_touch_dash": 'data-control="dash"' in game_js or '"dash"' in game_js,
    }


def _write_markdown(path: Path, result: dict[str, Any]) -> None:
    metrics = result.get("current_metrics") or {}
    lines = [
        "# Engel Game Factory Refinement Packet",
        "",
        f"- Run: {result.get('run_id')}",
        f"- Bridge: {result.get('bridge')}",
        f"- Source: {result.get('source')}",
        f"- Target artifact: {result.get('target_artifact') or '(latest game not found yet)'}",
        "",
        "## Request",
        "",
        str(result.get("prompt") or "").strip(),
        "",
        "## Current Metrics",
        "",
        f"- Stages: {metrics.get('stage_count')}",
        f"- Parts per stage: {metrics.get('parts_per_stage')}",
        f"- Part width: {metrics.get('part_width')}",
        f"- Dash: {metrics.get('has_dash')}",
        f"- Jump buffer: {metrics.get('has_jump_buffer')}",
        f"- Coyote time: {metrics.get('has_coyote_time')}",
        f"- Weapon cycle: {metrics.get('has_weapon_cycle')}",
        "",
        "## Refinement Contract",
        "",
        "- Keep the game original Engel IP; do not copy franchise assets, names, sprites, maps, or audio.",
        "- Keep Phaser bundled locally under the artifact folder; no CDN dependency at play time.",
        "- Preserve 10 stages and 5 parts per stage.",
        "- Make each part longer and more readable for real play.",
        "- Improve controls with dash/sprint, jump buffering, coyote time, weapon cycling, and touch controls.",
        "- Return a playable artifact path plus browser smoke verification.",
        "",
        "## Builder Checklist",
        "",
    ]
    for item in result.get("builder_checklist") or []:
        lines.append(f"- {item}")
    lines += [
        "",
        "## Safety",
        "",
        "- No provider API key required.",
        "- No shell target and no remote device control is opened by this bridge.",
        "- Phone worker output remains review context only.",
        "- Outputs stay under the Engel App workspace on D:.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def run_game_factory_refinement_packet(prompt: str, *, source: str = "Agent Meeting Room") -> dict[str, Any]:
    stamp = _dt.datetime.now().strftime("%Y%m%dT%H%M%S%f")
    run_id = f"engel-game-factory-{stamp}"
    run_root = BRIDGE_RUNTIME / "refinement" / run_id
    run_root.mkdir(parents=True, exist_ok=True)

    target = _latest_game_artifact()
    game_js = ""
    if target and (target / "game.js").is_file():
        game_js = (target / "game.js").read_text(encoding="utf-8", errors="replace")

    metrics = _extract_game_metrics(game_js)
    checklist = [
        "Use Agent Meeting Room device-first routing before local final assembly.",
        "Route Game Factory Scout with Game Developer, Game Art Director, UI, and Verifier stations.",
        "Increase PART_WIDTH to at least 1200 for longer stage parts.",
        "Add Shift/touch dash plus sprint feel while preserving keyboard movement.",
        "Add coyote time and jump buffering so platforming feels less stiff.",
        "Add Q/touch weapon cycling across all collected/upgraded weapons.",
        "Expose control upgrades in window.engelCampaignSpec for smoke tests.",
        "Run a browser smoke test and save screenshot/report under reports/meeting_rooms.",
    ]
    result: dict[str, Any] = {
        "ok": True,
        "bridge": BRIDGE_LABEL,
        "mode": "engel_game_factory_refinement",
        "source": source,
        "run_id": run_id,
        "prompt": str(prompt or "").strip(),
        "title": _title_from_prompt(prompt),
        "run_root": str(run_root),
        "target_artifact": str(target) if target else "",
        "current_metrics": metrics,
        "builder_checklist": checklist,
        "files_to_modify": ["engel_ui_executable_results.py"],
        "files_to_verify": [
            "tools/verify_engel_ui_executable_results.py",
            "tools/verify_engel_meeting_room_device_skill_routing.py",
            "tools/verify_engel_game_factory_bridge.py",
        ],
        "safety": {
            "no_provider_api_key_required": True,
            "no_external_asset_copy": True,
            "bridge_does_not_mutate_source": True,
            "outputs_under_d_workspace": True,
        },
    }
    status_path = run_root / "status.json"
    report_path = run_root / "GAME_FACTORY_REFINEMENT_REPORT.md"
    status_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    result["status_path"] = str(status_path)
    result["report_path"] = str(report_path)
    _write_markdown(report_path, result)
    status_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def summarize_game_factory_result(result: dict[str, Any]) -> str:
    metrics = result.get("current_metrics") if isinstance(result, dict) else {}
    metrics = metrics if isinstance(metrics, dict) else {}
    lines = [
        "Game Factory returned a refinement packet.",
        f"Bridge: {result.get('bridge')}",
        f"Run: {result.get('run_id')}",
        f"Target: {result.get('target_artifact') or 'latest game artifact will be created by Engel result finalizer'}",
        f"Report: {result.get('report_path')}",
        "Refine: longer stage parts, dash/sprint, jump buffering, coyote time, weapon cycling, expanded touch controls.",
    ]
    if metrics:
        lines.append(
            "Current metrics: "
            f"stages={metrics.get('stage_count')}, "
            f"parts={metrics.get('parts_per_stage')}, "
            f"part_width={metrics.get('part_width')}."
        )
    lines.append("Safety: local Game Factory packet only; no copied franchise assets and no provider key.")
    return "\n".join(lines)
