#!/usr/bin/env python3
"""Independently audit an Engel one-day local-first chat campaign."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = ROOT / "runtime" / "one_day_local_first_chat_training"
ACTIVE_PATH = RUNTIME_ROOT / "ACTIVE.json"
REPORT_DIR = ROOT / "reports" / "codex_bridge"
EXPECTED_EPOCHS = 24
EXPECTED_DESKTOP_PROMPTS = 10
EXPECTED_DISCORD_PROMPTS = 6
EXPECTED_TOTAL_PROMPTS = EXPECTED_EPOCHS * (
    EXPECTED_DESKTOP_PROMPTS + EXPECTED_DISCORD_PROMPTS
)
EXPECTED_MATERIAL_VERSION = "fresh_work_material_v17_20260721"
EXPECTED_PHONE_IDS = {
    "android_worker_alpha",
    "android_worker_beta",
    "android_worker_gamma",
}
CT_HOST = os.environ.get("ENGEL_MAIN_SERVER_HOST", "192.0.2.50")
CT_PORT = os.environ.get("ENGEL_MAIN_SERVER_SSH_PORT", "24622")
CT_USER = os.environ.get("ENGEL_MAIN_SERVER_SSH_USER", "root")
CT_KEY = Path(
    os.environ.get(
        "ENGEL_MAIN_SERVER_SSH_KEY",
        str(Path.home() / ".ssh" / "engel_ai_main_ct246_ed25519"),
    )
)
CT_PERSISTENT_CHAT_MEMORY = (
    "/opt/engel/memory/persistent_chat/ENGEL_AI_MAIN_LLM_CHAT_MEMORY.jsonl"
)
PROVIDER_NAMES = re.compile(
    r"\b(chatgpt|openai|claude|anthropic|grok|xai|x\.ai|gemini|codex|sonnet|opus|haiku)\b",
    re.IGNORECASE,
)
ROUTING_WORDS = re.compile(
    r"\b(provider|bridge|lane|backend|runtime|api|route|routing)\b",
    re.IGNORECASE,
)


def load_json(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temp.replace(path)


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_iso(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text).astimezone(timezone.utc)
    except Exception:
        return None


def find_run_dir(value: str) -> Path | None:
    if value:
        candidate = Path(value).resolve()
        return candidate if candidate.is_dir() else None
    active = load_json(ACTIVE_PATH)
    candidate = Path(str(active.get("run_dir") or ""))
    if candidate.is_dir():
        return candidate.resolve()
    runs = [path for path in RUNTIME_ROOT.glob("engel_one_day_local_first_*") if path.is_dir()]
    return max(runs, key=lambda path: path.stat().st_mtime).resolve() if runs else None


def route_disclosure_requested(prompt: str) -> bool:
    text = " ".join(str(prompt or "").casefold().split())
    return bool(
        re.search(
            r"\b(which|what|whose|name|identify|show|tell|explain|report|check)\b.{0,64}"
            r"\b(provider|bridge|lane|model|backend|runtime|api|route|routing)\b",
            text,
        )
        or re.search(
            r"\b(use|ask|route through|send to|hand to)\s+(the\s+)?"
            r"(chatgpt|openai|claude|anthropic|grok|xai|x\.ai|gemini|codex)\b",
            text,
        )
    )


def public_identity_leak(prompt: str, reply: str) -> bool:
    if route_disclosure_requested(prompt):
        return False
    text = str(reply or "")
    if not PROVIDER_NAMES.search(text):
        return False
    return bool(
        ROUTING_WORDS.search(text)
        or re.search(
            r"\b(i am|i'm|this is|using|through|via|powered by|running on)\b.{0,48}"
            r"\b(chatgpt|openai|claude|anthropic|grok|xai|x\.ai|gemini|codex|sonnet|opus|haiku)\b",
            text,
            flags=re.IGNORECASE,
        )
    )


def load_ct_persistent_rows() -> tuple[list[dict[str, Any]], str]:
    if not CT_KEY.is_file():
        return [], f"CT246 SSH key is missing: {CT_KEY}"
    command = [
        "ssh",
        "-i",
        str(CT_KEY),
        "-p",
        str(CT_PORT),
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=8",
        f"{CT_USER}@{CT_HOST}",
        "cat",
        CT_PERSISTENT_CHAT_MEMORY,
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=90,
            check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError) as exc:
        return [], str(exc)
    if result.returncode != 0:
        return [], (result.stderr or result.stdout or "CT246 memory read failed").strip()[:1000]
    rows: list[dict[str, Any]] = []
    for line in result.stdout.splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows, ""


def persistent_route_row_ok(row: dict[str, Any]) -> tuple[bool, list[str]]:
    issues: list[str] = []
    provider = " ".join(
        str(row.get(key) or "")
        for key in ("provider", "runtime_provider", "selected_provider")
    )
    remote_provider = bool(PROVIDER_NAMES.search(provider))
    provider_used = row.get("provider_api_enabled") is True or remote_provider
    model = str(row.get("model") or row.get("local_gguf_model_path") or "")
    local_model = bool(model) and (
        model.casefold().endswith(".gguf") or "llama" in provider.casefold()
    )
    if row.get("training_sample_eligible") is not True:
        issues.append("training_sample_eligible is not true")
    if row.get("persistent_chat_memory_training_eligible") is not True:
        issues.append("persistent_chat_memory_training_eligible is not true")
    if row.get("quality_gate_degraded") is True:
        issues.append("quality_gate_degraded is true")
    if provider_used:
        if row.get("local_ct_lora_first_attempted") is not True:
            issues.append("provider row lacks local-first attempt proof")
        if row.get("local_ct_lora_first_failed") is not True:
            issues.append("provider row lacks local failure proof")
        if str(row.get("escalated_from") or "") != "2":
            issues.append("provider row is not stamped escalated_from=2")
        if row.get("provider_reply_quality_gate_passed") is not True:
            issues.append("provider pre-persistence quality gate did not pass")
        final_quality = row.get("provider_final_semantic_quality")
        if not isinstance(final_quality, dict) or final_quality.get("ok") is not True:
            issues.append("provider final semantic quality did not pass")
    else:
        if row.get("provider_api_enabled") is not False:
            issues.append("local row does not explicitly disable provider API use")
        if row.get("network_enabled") is not False:
            issues.append("local row does not explicitly disable network use")
        if not local_model:
            issues.append("local row does not identify a GGUF model")
        semantic = row.get("local_semantic_quality")
        if isinstance(semantic, dict) and semantic.get("ok") is not True:
            issues.append("local semantic quality did not pass")
    return not issues, issues


def route_row_ok(row: dict[str, Any]) -> tuple[bool, list[str]]:
    issues: list[str] = []
    local = row.get("local_model_verified") is True or row.get("verified") is True
    pipeline = row.get("provider_pipeline_used") is True
    escalation = row.get("verified_local_first_escalation") is True
    if not local and not escalation:
        issues.append("turn lacks a verified local model or post-local-failure escalation")
    if pipeline and not escalation:
        issues.append("provider pipeline lacks verified local-first escalation")
    if escalation and str(row.get("escalated_from") or "") != "2":
        issues.append("provider escalation is not stamped escalated_from=2")
    if row.get("routing_policy_verified") is not True:
        issues.append("routing_policy_verified is not true")
    quality_ok = bool(
        row.get("quality_or_verified_escalation") is True
        or (local and row.get("quality_verified") is True)
        or escalation
    )
    if not quality_ok:
        issues.append("quality_or_verified_escalation is not true")
    return not issues, issues


def audit_visible(
    report: dict[str, Any],
    template: dict[str, Any],
) -> tuple[dict[str, Any], list[str], list[str]]:
    prompts = template.get("active_prompts") if isinstance(template.get("active_prompts"), list) else []
    issues: list[str] = []
    leaks: list[str] = []
    hits = ((report.get("ct_persistent_memory") or {}).get("hits") or {})
    if report.get("ok") is not True or report.get("status") != "PASS":
        issues.append("visible UI report did not pass")
    if len(prompts) != EXPECTED_DESKTOP_PROMPTS:
        issues.append(f"visible template has {len(prompts)} prompts, expected {EXPECTED_DESKTOP_PROMPTS}")
    if int(report.get("prompt_count") or 0) != len(prompts):
        issues.append("visible report prompt_count does not match template")
    if int(report.get("driver_prompts_submitted") or 0) < len(prompts):
        issues.append("visible UI did not submit every prompt")
    if int(report.get("driver_replies_finished") or 0) < len(prompts):
        issues.append("visible UI did not finish every reply")
    if float(report.get("elapsed_seconds") or 0) < float(report.get("requested_minutes") or 0) * 60:
        issues.append("visible UI duration was shorter than requested")
    if report.get("ct_persistent_memory_ok") is not True:
        issues.append("visible CT persistent-memory proof failed")
    if report.get("ct_single_write_ok") is not True:
        issues.append("visible CT single-writer proof failed")
    if report.get("ct_training_eligible_ok") is not True:
        issues.append("visible CT training-eligibility proof failed")
    if report.get("local_first_or_verified_escalation_ok") is not True:
        issues.append("visible local-first route proof failed")
    if report.get("quality_or_verified_escalation_ok") is not True:
        issues.append("visible quality or escalation proof failed")
    if report.get("meeting_room_events_ok") is not True:
        issues.append("visible meeting-room event mirror failed")
    if report.get("phones_live") is not True:
        issues.append("visible phone requirement failed")
    for prompt in prompts:
        row = hits.get(prompt) if isinstance(hits.get(prompt), dict) else {}
        if not row:
            issues.append(f"visible persistent receipt missing: {prompt[:100]}")
            continue
        ok, row_issues = route_row_ok(row)
        if not ok:
            issues.extend(f"visible {prompt[:70]}: {item}" for item in row_issues)
        reply = str(row.get("assistant_reply_preview") or "")
        if public_identity_leak(prompt, reply):
            leaks.append(prompt)
    return {
        "prompt_count": len(prompts),
        "submitted": int(report.get("driver_prompts_submitted") or 0),
        "finished": int(report.get("driver_replies_finished") or 0),
        "elapsed_seconds": float(report.get("elapsed_seconds") or 0),
        "receipt_hit_count": len(hits),
    }, issues, leaks


def audit_discord(
    report: dict[str, Any],
    template: dict[str, Any],
) -> tuple[dict[str, Any], list[str], list[str]]:
    prompts = template.get("prompts") if isinstance(template.get("prompts"), list) else []
    results = report.get("results") if isinstance(report.get("results"), list) else []
    issues: list[str] = []
    leaks: list[str] = []
    if report.get("ok") is not True or report.get("status") != "PASS":
        issues.append("Discord owner UI report did not pass")
    if report.get("real_logged_in_owner_ui") is not True:
        issues.append("Discord report lacks real logged-in owner UI proof")
    if len(prompts) != EXPECTED_DISCORD_PROMPTS:
        issues.append(f"Discord template has {len(prompts)} prompts, expected {EXPECTED_DISCORD_PROMPTS}")
    if len(results) != len(prompts):
        issues.append("Discord result count does not match template")
    if int(report.get("passed_prompt_count") or 0) != len(prompts):
        issues.append("Discord did not pass every prompt")
    if float(report.get("actual_duration_seconds") or 0) < float(report.get("requested_minutes") or 0) * 60:
        issues.append("Discord duration was shorter than requested")
    if int(report.get("training_lines_after") or 0) < int(report.get("training_lines_before") or 0) + len(prompts):
        issues.append("Discord training log did not grow once per prompt")
    if int(report.get("persistent_lines_after") or 0) <= int(report.get("persistent_lines_before") or 0):
        issues.append("Discord persistent memory did not grow")
    by_prompt = {
        str(row.get("prompt") or ""): row for row in results if isinstance(row, dict)
    }
    for prompt in prompts:
        row = by_prompt.get(prompt, {})
        if not row:
            issues.append(f"Discord result missing: {prompt[:100]}")
            continue
        if row.get("ok") is not True or row.get("receipt_found") is not True:
            issues.append(f"Discord failed or lacks receipt: {prompt[:100]}")
        if row.get("owner_id_verified") is not True:
            issues.append(f"Discord owner identity was not verified: {prompt[:100]}")
        if row.get("training_sample_eligible") is not True:
            issues.append(f"Discord turn was not training eligible: {prompt[:100]}")
        proof = row.get("local_model_proof") if isinstance(row.get("local_model_proof"), dict) else {}
        ok, row_issues = route_row_ok(proof)
        if not ok:
            issues.extend(f"Discord {prompt[:70]}: {item}" for item in row_issues)
        reply = str(row.get("assistant_reply") or "")
        if not reply:
            issues.append(f"Discord reply is empty: {prompt[:100]}")
        if public_identity_leak(prompt, reply):
            leaks.append(prompt)
    return {
        "prompt_count": len(prompts),
        "result_count": len(results),
        "passed_prompt_count": int(report.get("passed_prompt_count") or 0),
        "elapsed_seconds": float(report.get("actual_duration_seconds") or 0),
    }, issues, leaks


def render_markdown(audit: dict[str, Any]) -> str:
    lines = [
        f"# Engel One-Day Independent Audit {audit.get('status', 'UNKNOWN')}",
        "",
        f"- Run: `{audit.get('run_id', '')}`",
        f"- Material: `{audit.get('material_version', '')}`",
        f"- Epochs audited: `{audit.get('epochs_audited', 0)}/{EXPECTED_EPOCHS}`",
        f"- Unique prompts: `{audit.get('unique_prompt_count', 0)}/{EXPECTED_TOTAL_PROMPTS}`",
        f"- Wall seconds: `{audit.get('wall_duration_seconds', 0)}`",
        f"- Issues: `{len(audit.get('issues') or [])}`",
        f"- Provider identity leaks: `{len(audit.get('provider_identity_leaks') or [])}`",
        "",
    ]
    for issue in audit.get("issues") or []:
        lines.append(f"- FAIL: {issue}")
    if not audit.get("issues"):
        lines.append("- All independently checked requirements passed.")
    lines.append("")
    return "\n".join(lines)


def audit(run_dir: Path) -> dict[str, Any]:
    run_id = run_dir.name
    final_path = REPORT_DIR / f"ENGEL_ONE_DAY_LOCAL_FIRST_CHAT_TRAINING_{run_id}.json"
    final = load_json(final_path)
    epoch_paths = sorted(run_dir.glob("epoch_*/epoch_report.json"))
    if not final:
        state = load_json(run_dir / "state.json")
        prompt_surfaces: dict[str, str] = {}
        for path in sorted((run_dir / "templates").glob("epoch_*_desktop.json")):
            template = load_json(path)
            for prompt in template.get("active_prompts") or []:
                prompt_surfaces[str(prompt)] = "desktop"
        for path in sorted((run_dir / "templates").glob("epoch_*_discord.json")):
            template = load_json(path)
            for prompt in template.get("prompts") or []:
                prompt_surfaces[str(prompt)] = "discord"
        live_rows, live_error = load_ct_persistent_rows()
        observed: list[dict[str, Any]] = []
        live_issues: list[str] = []
        if live_error:
            live_issues.append("could not read CT246 persistent memory: " + live_error)
        else:
            by_prompt: dict[str, list[dict[str, Any]]] = {
                prompt: [] for prompt in prompt_surfaces
            }
            for row in live_rows:
                prompt = str(row.get("prompt") or "")
                if prompt in by_prompt:
                    by_prompt[prompt].append(row)
            for prompt, rows in by_prompt.items():
                if not rows:
                    continue
                surface = prompt_surfaces[prompt]
                entry = {
                    "surface": surface,
                    "prompt": prompt,
                    "row_count": len(rows),
                    "ok": False,
                    "issues": [],
                }
                if len(rows) != 1:
                    entry["issues"].append(
                        f"CT persistent memory contains {len(rows)} rows for this prompt"
                    )
                else:
                    row = rows[0]
                    row_ok, row_issues = persistent_route_row_ok(row)
                    entry["issues"].extend(row_issues)
                    scope = str(row.get("chat_context_scope") or "")
                    expected_scope = (
                        scope.startswith("engel_ai_main_desktop")
                        if surface == "desktop"
                        else scope.startswith("discord:")
                    )
                    if not expected_scope:
                        entry["issues"].append("chat_context_scope does not match the real UI surface")
                    reply = str(row.get("assistant_reply") or row.get("assistant_output_text") or "")
                    if not reply:
                        entry["issues"].append("assistant reply is empty")
                    if public_identity_leak(prompt, reply):
                        entry["issues"].append("public reply leaks provider identity")
                entry["ok"] = not entry["issues"]
                observed.append(entry)
                live_issues.extend(
                    f"{surface} {prompt[:80]}: {item}" for item in entry["issues"]
                )
        for path in sorted(run_dir.glob("epoch_*/discord.log")):
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for line in lines:
                if '"event": "discord_owner_turn"' in line and '"ok": false' in line:
                    live_issues.append(f"{path.parent.name} contains a failed Discord owner turn")
        return {
            "schema": "engel_one_day_local_first_chat_independent_audit_v1",
            "ok": False,
            "status": "IN_PROGRESS_FAILED" if live_issues else "IN_PROGRESS",
            "run_id": run_id,
            "run_dir": str(run_dir),
            "material_version": str(state.get("material_version") or ""),
            "epochs_completed": len(epoch_paths),
            "current_epoch": state.get("epoch"),
            "supervisor_status": state.get("status"),
            "observed_turn_count": len(observed),
            "observed_turns_ok": bool(observed) and not live_issues,
            "in_progress_issues": live_issues,
            "observed_turns": observed,
            "ct_persistent_rows_read": len(live_rows),
            "updated_at_utc": iso_now(),
        }

    issues: list[str] = []
    leaks: list[dict[str, Any]] = []
    epoch_audits: list[dict[str, Any]] = []
    all_prompts: list[str] = []
    if final.get("ok") is not True or final.get("status") != "PASS":
        issues.append("supervisor final report did not pass")
    if final.get("initial_preflight", {}).get("ok") is not True:
        issues.append("campaign preflight did not pass")
    material_scan = final.get("initial_preflight", {}).get("fresh_material_scan")
    if not isinstance(material_scan, dict) or material_scan.get("ok") is not True:
        issues.append("campaign preflight lacks a passing live-memory collision scan")
    elif int(material_scan.get("collision_count") or 0) != 0:
        issues.append("campaign material collided with prompts already in live CT memory")
    if final.get("material_version") != EXPECTED_MATERIAL_VERSION:
        issues.append("campaign material version is not the required fresh material")
    if final.get("fresh_material_only") is not True:
        issues.append("campaign is not stamped fresh_material_only")
    if int(final.get("epoch_count") or 0) != EXPECTED_EPOCHS:
        issues.append("final report epoch count is not 24")
    if len(epoch_paths) != EXPECTED_EPOCHS:
        issues.append(f"found {len(epoch_paths)} epoch reports, expected {EXPECTED_EPOCHS}")

    for epoch_number in range(1, EXPECTED_EPOCHS + 1):
        epoch_dir = run_dir / f"epoch_{epoch_number:02d}"
        epoch = load_json(epoch_dir / "epoch_report.json")
        desktop_template = load_json(run_dir / "templates" / f"epoch_{epoch_number:02d}_desktop.json")
        discord_template = load_json(run_dir / "templates" / f"epoch_{epoch_number:02d}_discord.json")
        desktop_prompts = desktop_template.get("active_prompts") if isinstance(desktop_template.get("active_prompts"), list) else []
        discord_prompts = discord_template.get("prompts") if isinstance(discord_template.get("prompts"), list) else []
        all_prompts.extend(str(item) for item in desktop_prompts + discord_prompts)
        epoch_issues: list[str] = []
        if not epoch:
            epoch_issues.append("epoch report missing")
            visible = {}
            discord = {}
        else:
            visible = load_json(Path(str(epoch.get("visible_report") or "")))
            discord = load_json(Path(str(epoch.get("discord_report") or "")))
            if int(epoch.get("visible_exit_code") or 0) != 0:
                epoch_issues.append("visible runner exit code was nonzero")
            if int(epoch.get("discord_exit_code") or 0) != 0:
                epoch_issues.append("Discord runner exit code was nonzero")
            if epoch.get("route_policy_ok") is not True:
                epoch_issues.append("epoch route policy failed")
            if epoch.get("persistent_memory_ok") is not True:
                epoch_issues.append("epoch persistent-memory check failed")
            device = epoch.get("device_snapshot") if isinstance(epoch.get("device_snapshot"), dict) else {}
            if device.get("ct_local_model_present") is not True:
                epoch_issues.append("CT local GGUF was not present")
            if device.get("ct_lora_ready") is not True:
                epoch_issues.append("CT LoRA runtime was not ready")
            if device.get("active_runtime_storage") != "engel-fast-ssd":
                epoch_issues.append("active runtime was not on engel-fast-ssd")
            if device.get("vault_used_for_active_runtime") is not False:
                epoch_issues.append("vault active-runtime policy was not false")
            phones = device.get("phones") if isinstance(device.get("phones"), dict) else {}
            if set(phones) != EXPECTED_PHONE_IDS:
                epoch_issues.append(
                    "epoch does not contain exactly the three required phone worker identities"
                )
            epoch_finished = parse_iso(epoch.get("finished_at_utc"))
            for phone_id in sorted(EXPECTED_PHONE_IDS):
                phone = phones.get(phone_id) if isinstance(phones.get(phone_id), dict) else {}
                last_seen = parse_iso(phone.get("last_seen_utc"))
                if epoch_finished is None or last_seen is None:
                    epoch_issues.append(f"{phone_id} lacks a parseable epoch heartbeat")
                elif abs((epoch_finished - last_seen).total_seconds()) > 600:
                    epoch_issues.append(f"{phone_id} heartbeat is stale at epoch completion")
        visible_stats, visible_issues, visible_leaks = audit_visible(visible, desktop_template)
        discord_stats, discord_issues, discord_leaks = audit_discord(discord, discord_template)
        epoch_issues.extend(visible_issues)
        epoch_issues.extend(discord_issues)
        leaks.extend({"epoch": epoch_number, "surface": "desktop", "prompt": item} for item in visible_leaks)
        leaks.extend({"epoch": epoch_number, "surface": "discord", "prompt": item} for item in discord_leaks)
        issues.extend(f"epoch {epoch_number}: {item}" for item in epoch_issues)
        epoch_audits.append(
            {
                "epoch": epoch_number,
                "ok": not epoch_issues and not visible_leaks and not discord_leaks,
                "issues": epoch_issues,
                "provider_identity_leak_count": len(visible_leaks) + len(discord_leaks),
                "visible": visible_stats,
                "discord": discord_stats,
            }
        )

    unique_prompts = set(all_prompts)
    if len(all_prompts) != EXPECTED_TOTAL_PROMPTS:
        issues.append(f"found {len(all_prompts)} prompts, expected {EXPECTED_TOTAL_PROMPTS}")
    if len(unique_prompts) != EXPECTED_TOTAL_PROMPTS:
        issues.append(f"only {len(unique_prompts)} prompts are unique, expected {EXPECTED_TOTAL_PROMPTS}")

    ct_rows, ct_memory_error = load_ct_persistent_rows()
    ct_prompt_rows: dict[str, list[dict[str, Any]]] = {prompt: [] for prompt in unique_prompts}
    if ct_memory_error:
        issues.append("could not independently read CT246 persistent chat memory: " + ct_memory_error)
    else:
        for row in ct_rows:
            prompt = str(row.get("prompt") or "")
            if prompt in ct_prompt_rows:
                ct_prompt_rows[prompt].append(row)
        for prompt in sorted(unique_prompts):
            rows = ct_prompt_rows[prompt]
            if len(rows) != 1:
                issues.append(
                    f"CT persistent memory has {len(rows)} rows for campaign prompt: {prompt[:100]}"
                )
                continue
            row = rows[0]
            row_ok, row_issues = persistent_route_row_ok(row)
            issues.extend(
                f"CT memory {prompt[:70]}: {item}" for item in row_issues
            )
            scope = str(row.get("chat_context_scope") or "")
            if not (scope.startswith("engel_ai_main_desktop") or scope.startswith("discord:")):
                issues.append(f"CT memory prompt lacks a valid UI scope: {prompt[:100]}")
            reply = str(row.get("assistant_reply") or row.get("assistant_output_text") or "")
            if not reply:
                issues.append(f"CT memory prompt has an empty assistant reply: {prompt[:100]}")
            if public_identity_leak(prompt, reply):
                leaks.append({"epoch": None, "surface": "ct_memory", "prompt": prompt})
    started = parse_iso(final.get("started_at_utc"))
    finished = parse_iso(final.get("finished_at_utc"))
    wall_seconds = (finished - started).total_seconds() if started and finished else 0.0
    if wall_seconds < 24 * 60 * 60:
        issues.append("campaign wall duration was shorter than 24 hours")
    summary = final.get("summary") if isinstance(final.get("summary"), dict) else {}
    if int(summary.get("epochs_completed") or 0) != EXPECTED_EPOCHS:
        issues.append("summary does not prove 24 completed epochs")
    if int(summary.get("route_policy_epoch_count") or 0) != EXPECTED_EPOCHS:
        issues.append("summary does not prove local-first routing for every epoch")
    if int(summary.get("persistent_memory_epoch_count") or 0) != EXPECTED_EPOCHS:
        issues.append("summary does not prove persistent memory for every epoch")
    if int(summary.get("unauthorized_provider_turn_count") or 0) != 0:
        issues.append("summary contains unauthorized provider turns")
    if leaks:
        issues.append(f"public replies contain {len(leaks)} provider identity leak(s)")
    return {
        "schema": "engel_one_day_local_first_chat_independent_audit_v1",
        "ok": not issues,
        "status": "PASS" if not issues else "FAIL",
        "run_id": run_id,
        "run_dir": str(run_dir),
        "supervisor_report": str(final_path),
        "material_version": str(final.get("material_version") or ""),
        "epochs_audited": len(epoch_audits),
        "prompt_count": len(all_prompts),
        "unique_prompt_count": len(unique_prompts),
        "wall_duration_seconds": round(wall_seconds, 3),
        "provider_identity_leaks": leaks,
        "ct_persistent_memory": {
            "path": CT_PERSISTENT_CHAT_MEMORY,
            "read_error": ct_memory_error,
            "rows_read": len(ct_rows),
            "campaign_prompt_count": len(ct_prompt_rows),
            "campaign_prompt_rows_found": sum(
                1 for rows in ct_prompt_rows.values() if len(rows) == 1
            ),
            "duplicate_or_missing_prompt_count": sum(
                1 for rows in ct_prompt_rows.values() if len(rows) != 1
            ),
        },
        "issues": issues,
        "epochs": epoch_audits,
        "updated_at_utc": iso_now(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", default="")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    run_dir = find_run_dir(args.run_dir)
    if run_dir is None:
        print(json.dumps({"ok": False, "status": "MISSING", "error": "campaign run directory not found"}, indent=2))
        return 2
    result = audit(run_dir)
    if args.write and not str(result.get("status") or "").startswith("IN_PROGRESS"):
        json_path = REPORT_DIR / f"ENGEL_ONE_DAY_LOCAL_FIRST_INDEPENDENT_AUDIT_{run_dir.name}.json"
        md_path = json_path.with_suffix(".md")
        result["audit_json_path"] = str(json_path)
        result["audit_markdown_path"] = str(md_path)
        write_json(json_path, result)
        md_path.write_text(render_markdown(result), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    if str(result.get("status") or "").startswith("IN_PROGRESS"):
        return 2
    return 0 if result.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
