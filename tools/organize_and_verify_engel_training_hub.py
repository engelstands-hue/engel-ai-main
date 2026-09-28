#!/usr/bin/env python3
"""Organize Engel Main training assets and verify every safe entrypoint.

This does not start paid RunPod work or multi-hour training by default. It
checks every copied training script with py_compile and, when a script exposes a
CLI, a --help entrypoint run. Known local/dry-run/verifier commands are also
executed. Optional flags can run the visible Engel Main chat UI as a real user.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import py_compile
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_ROOT = ROOT / "memory" / "training" / "engel_main"
MANIFEST = CANONICAL_ROOT / "training_assets_manifest.json"
ORGANIZED_ROOT = CANONICAL_ROOT / "organized"
RUNS_ROOT = CANONICAL_ROOT / "runs" / "verification"
LATEST_RECEIPT = ROOT / "memory" / "training" / "ENGEL_TRAINING_HUB_VERIFY_LATEST.json"


CATEGORIES: dict[str, dict[str, Any]] = {
    "01_visible_ui_real_user": {
        "title": "Visible UI real-user prompt training",
        "policy": "Use Engel AI Main UI; normal chat stays chat-only, creation work routes through Meeting Room.",
        "scripts": [
            "run_engel_flutter_main_ui_prompt_training.py",
            "run_engel_ui_prompt_training.py",
            "run_engel_ui_input_creation_training_hour.py",
            "run_engel_ui_input_creation_training_loop.py",
            "run_engel_code_creation_ui_training.py",
            "engel_ui_prompt_training_support.py",
        ],
    },
    "02_local_llm_memory_dataset": {
        "title": "Local LLM, memory, and candidate dataset",
        "policy": "Local D-drive preparation/verification only; no model-weight update unless launched separately.",
        "scripts": [
            "run_engel_local_llm_prompt_training_template.py",
            "prepare_local_llm_training_dataset.py",
            "verify_local_llm_training_prep.py",
            "verify_engel_training_trusted_memory.py",
        ],
    },
    "03_sub_engel_and_cluster": {
        "title": "Sub-Engel and cluster prompt routes",
        "policy": "Device/worker work must use Meeting Room or review-only return packets.",
        "scripts": [
            "run_engel_sub_engel_prompt_training_companion.py",
            "run_engel_four_hour_prompt_training.py",
            "run_engel_four_hour_cluster_prompt_training.py",
        ],
    },
    "04_personality_runs": {
        "title": "Personality and humanizer training",
        "policy": "Receipt-based local/remote personality sessions; long runs stay operator-launched.",
        "scripts": [
            "run_engel_local_personality_training_sessions.py",
            "verify_engel_local_personality_training.py",
            "run_engel_personality_training_sessions.py",
            "verify_engel_personality_training.py",
        ],
    },
    "05_runpod_lora_external": {
        "title": "RunPod and LoRA external work",
        "policy": "Do not start paid pods or GPU training from verification; help/status only.",
        "scripts": [
            "run_engel_runpod_parallel_personality_training.py",
            "run_engel_lora_training_on_runpod.py",
            "build_engel_lora_training_package.py",
            "create_engel_runpod_training_pod.py",
        ],
    },
    "06_prompt_sources": {
        "title": "Prompt and personality source files",
        "policy": "Canonical copies only; used by runners and Engel persistent memory.",
        "scripts": [],
    },
}


SAFE_COMMANDS: dict[str, list[str]] = {
    "run_engel_four_hour_prompt_training.py": [
        "--dry-run",
        "--cycles",
        "1",
        "--minutes",
        "0.01",
        "--target-jobs",
        "1",
        "--per-job-timeout",
        "10",
        "--skip-final-wait",
    ],
    "prepare_local_llm_training_dataset.py": [],
    "verify_local_llm_training_prep.py": [],
    "verify_engel_training_trusted_memory.py": [],
    "verify_engel_local_personality_training.py": [],
    "verify_engel_personality_training.py": [],
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def safe_write_text(path: Path, text: str) -> None:
    if path.drive.lower() == "c:":
        raise RuntimeError(f"refusing to write training verification output on C: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def safe_write_json(path: Path, payload: Any) -> None:
    safe_write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def run_command(name: str, args: list[str], run_dir: Path, timeout: int = 60) -> dict[str, Any]:
    started = time.monotonic()
    log_path = run_dir / f"{name}.log"
    try:
        completed = subprocess.run(
            args,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        safe_write_text(
            log_path,
            "\n".join(
                [
                    "$ " + " ".join(str(item) for item in args),
                    "",
                    "STDOUT:",
                    stdout,
                    "",
                    "STDERR:",
                    stderr,
                ]
            ),
        )
        return {
            "name": name,
            "ok": completed.returncode == 0,
            "exit_code": completed.returncode,
            "duration_seconds": round(time.monotonic() - started, 3),
            "log": str(log_path),
            "stdout_tail": stdout[-1200:],
            "stderr_tail": stderr[-1200:],
            "timeout_seconds": timeout,
        }
    except subprocess.TimeoutExpired as exc:
        stdout = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        stderr = (exc.stderr or "") if isinstance(exc.stderr, str) else ""
        safe_write_text(
            log_path,
            "\n".join(
                [
                    "$ " + " ".join(str(item) for item in args),
                    "",
                    f"TIMEOUT after {timeout}s",
                    "",
                    "STDOUT:",
                    stdout,
                    "",
                    "STDERR:",
                    stderr,
                ]
            ),
        )
        return {
            "name": name,
            "ok": False,
            "exit_code": "timeout",
            "duration_seconds": round(time.monotonic() - started, 3),
            "log": str(log_path),
            "stdout_tail": stdout[-1200:],
            "stderr_tail": stderr[-1200:],
            "timeout_seconds": timeout,
        }


def categorize(script_name: str) -> str:
    for category, spec in CATEGORIES.items():
        if script_name in spec["scripts"]:
            return category
    return "99_uncategorized"


def script_has_cli(path: Path) -> bool:
    text = path.read_text(encoding="utf-8", errors="replace")
    return "argparse.ArgumentParser" in text or "ArgumentParser(" in text


def organize_assets(manifest: dict[str, Any]) -> dict[str, Any]:
    ORGANIZED_ROOT.mkdir(parents=True, exist_ok=True)
    script_records = []
    for item in manifest.get("scripts", []):
        source = Path(str(item.get("source", "")))
        canonical = Path(str(item.get("canonical_copy", "")))
        name = source.name or canonical.name
        script_records.append(
            {
                "name": name,
                "category": categorize(name),
                "source": str(source),
                "canonical_copy": str(canonical),
                "exists": bool(item.get("exists")),
                "bytes": item.get("bytes"),
                "sha256": item.get("sha256"),
                "safe_command": SAFE_COMMANDS.get(name),
                "cli_help_check": source.is_file() and script_has_cli(source),
            }
        )

    prompt_records = []
    for item in manifest.get("prompt_sources", []):
        canonical = Path(str(item.get("canonical_copy", "")))
        prompt_records.append(
            {
                "name": canonical.name,
                "category": "06_prompt_sources",
                "source": item.get("source"),
                "canonical_copy": item.get("canonical_copy"),
                "exists": item.get("exists"),
                "bytes": item.get("bytes"),
                "sha256": item.get("sha256"),
            }
        )

    categories = []
    for key, spec in CATEGORIES.items():
        members = [item for item in script_records if item["category"] == key]
        categories.append(
            {
                "id": key,
                "title": spec["title"],
                "policy": spec["policy"],
                "script_count": len(members),
                "scripts": [item["name"] for item in members],
            }
        )
        lines = [
            f"# {spec['title']}",
            "",
            spec["policy"],
            "",
            "## Scripts",
            "",
        ]
        if members:
            for member in members:
                mode = "safe run" if member["safe_command"] is not None else "CLI help" if member["cli_help_check"] else "compile only"
                lines.append(f"- `{member['name']}` - {mode}")
        else:
            lines.append("- Prompt/source files only.")
        safe_write_text(ORGANIZED_ROOT / key / "README.md", "\n".join(lines) + "\n")

    run_order = [
        "# Engel Training Hub Run Order",
        "",
        "1. Sync training assets.",
        "2. Compile every Python training script.",
        "3. Run CLI help checks for every script with a command line interface.",
        "4. Run safe local verifiers/dry-runs.",
        "5. Run visible Engel AI Main UI smoke or full-template prompt pass.",
        "6. Append the receipt to persistent Engel memory.",
        "",
        "Paid RunPod and long multi-hour jobs are not launched by verification. Their CLI entrypoints are checked and their full commands remain operator-launched.",
        "",
    ]
    safe_write_text(ORGANIZED_ROOT / "RUN_ORDER.md", "\n".join(run_order))

    catalog = {
        "schema": "engel_training_hub_catalog_v1",
        "ok": True,
        "updated_at_utc": utc_now(),
        "canonical_root": str(CANONICAL_ROOT),
        "organized_root": str(ORGANIZED_ROOT),
        "categories": categories,
        "scripts": script_records,
        "prompt_sources": prompt_records,
        "template": manifest.get("template_path"),
        "template_prompt_count": manifest.get("template_prompt_count"),
        "wrappers": manifest.get("wrappers"),
        "c_drive_used": False,
    }
    safe_write_json(ORGANIZED_ROOT / "catalog.json", catalog)
    return catalog


def verify_scripts(manifest: dict[str, Any], run_dir: Path) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for item in manifest.get("scripts", []):
        source = Path(str(item.get("source", "")))
        name = source.name
        record: dict[str, Any] = {
            "name": name,
            "category": categorize(name),
            "source": str(source),
            "exists": source.is_file(),
            "compile_ok": False,
            "entrypoint_checked": False,
            "entrypoint_ok": None,
            "safe_run_checked": False,
            "safe_run_ok": None,
        }
        if not source.is_file():
            record["ok"] = False
            record["error"] = "missing source"
            results.append(record)
            continue
        try:
            py_compile.compile(str(source), doraise=True)
            record["compile_ok"] = True
        except py_compile.PyCompileError as exc:
            record["compile_error"] = str(exc)
        if record["compile_ok"] and script_has_cli(source):
            command = [sys.executable, str(source), "--help"]
            check = run_command(f"{name}.help", command, run_dir, timeout=45)
            record["entrypoint_checked"] = True
            record["entrypoint_ok"] = check["ok"]
            record["entrypoint_log"] = check["log"]
        safe_args = SAFE_COMMANDS.get(name)
        if record["compile_ok"] and safe_args is not None:
            command = [sys.executable, str(source), *safe_args]
            check = run_command(f"{name}.safe", command, run_dir, timeout=180)
            record["safe_run_checked"] = True
            record["safe_run_ok"] = check["ok"]
            record["safe_run_log"] = check["log"]
            record["safe_run_stdout_tail"] = check.get("stdout_tail", "")
            record["safe_run_stderr_tail"] = check.get("stderr_tail", "")
        record["ok"] = bool(
            record["compile_ok"]
            and (not record["entrypoint_checked"] or record["entrypoint_ok"] is True)
            and (not record["safe_run_checked"] or record["safe_run_ok"] is True)
        )
        results.append(record)
    return results


def verify_prompt_sources(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for item in manifest.get("prompt_sources", []):
        canonical = Path(str(item.get("canonical_copy", "")))
        result = {
            "name": canonical.name,
            "path": str(canonical),
            "exists": canonical.is_file(),
            "bytes": canonical.stat().st_size if canonical.is_file() else 0,
            "sha256": sha256_file(canonical) if canonical.is_file() else "",
        }
        result["ok"] = result["exists"] and result["bytes"] > 0 and result["sha256"] == item.get("sha256")
        results.append(result)
    return results


def run_ui_smoke(run_dir: Path, minutes: float, timeout: int) -> dict[str, Any]:
    script = CANONICAL_ROOT / "run_smoke_prompt_training.ps1"
    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script),
        "-Minutes",
        str(minutes),
        "-PerPromptTimeout",
        str(timeout),
    ]
    return run_command("visible_ui_smoke_wrapper", command, run_dir, timeout=max(900, int(minutes * 60) + timeout * 4))


def run_ui_full_template(run_dir: Path, minutes: float, timeout: int) -> dict[str, Any]:
    template = CANONICAL_ROOT / "templates" / "ENGEL_HOUR_PROMPT_TRAINING_MIXED.json"
    command = [
        sys.executable,
        str(ROOT / "tools" / "run_engel_flutter_main_ui_prompt_training.py"),
        "--mode",
        "one-hour",
        "--minutes",
        str(minutes),
        "--per-prompt-timeout",
        str(timeout),
        "--skip-final-wait",
        "--template",
        str(template),
    ]
    return run_command("visible_ui_full_template", command, run_dir, timeout=max(1800, int(minutes * 60) + timeout * 4))


def write_markdown(receipt: dict[str, Any], path: Path) -> None:
    summary = receipt["summary"]
    lines = [
        "# Engel Training Hub Verification",
        "",
        f"- status: `{receipt['status']}`",
        f"- scripts checked: `{summary['scripts_checked']}`",
        f"- scripts passed: `{summary['scripts_passed']}`",
        f"- prompt sources checked: `{summary['prompt_sources_checked']}`",
        f"- prompt sources passed: `{summary['prompt_sources_passed']}`",
        f"- UI smoke run: `{summary['ui_smoke_status']}`",
        f"- UI full-template run: `{summary['ui_full_template_status']}`",
        f"- c_drive_used: `{summary['c_drive_used']}`",
        "",
        "## Failed Items",
        "",
    ]
    failures = receipt.get("failures", [])
    if not failures:
        lines.append("- none")
    else:
        for failure in failures:
            lines.append(f"- `{failure}`")
    lines.extend(
        [
            "",
            "## Output",
            "",
            f"- receipt: `{receipt['receipt_path']}`",
            f"- catalog: `{receipt['catalog_path']}`",
            f"- run directory: `{receipt['run_dir']}`",
            "",
        ]
    )
    safe_write_text(path, "\n".join(lines))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ui-smoke", action="store_true", help="Run the visible Engel Main smoke wrapper.")
    parser.add_argument("--ui-smoke-minutes", type=float, default=3.0)
    parser.add_argument("--ui-full-template-minutes", type=float, default=0.0, help="Run all 12 template prompts through visible Engel Main UI when > 0.")
    parser.add_argument("--per-prompt-timeout", type=int, default=760)
    args = parser.parse_args()

    manifest = load_json(MANIFEST)
    run_id = "training_hub_verify_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = RUNS_ROOT / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    catalog = organize_assets(manifest)
    script_results = verify_scripts(manifest, run_dir)
    prompt_results = verify_prompt_sources(manifest)
    ui_smoke_result: dict[str, Any] | None = None
    if args.ui_smoke:
        ui_smoke_result = run_ui_smoke(run_dir, args.ui_smoke_minutes, args.per_prompt_timeout)
    ui_full_result: dict[str, Any] | None = None
    if args.ui_full_template_minutes and args.ui_full_template_minutes > 0:
        ui_full_result = run_ui_full_template(run_dir, args.ui_full_template_minutes, args.per_prompt_timeout)

    failures = []
    for item in script_results:
        if not item.get("ok"):
            failures.append(f"script:{item.get('name')}")
    for item in prompt_results:
        if not item.get("ok"):
            failures.append(f"prompt_source:{item.get('name')}")
    if ui_smoke_result is not None and not ui_smoke_result.get("ok"):
        failures.append("visible_ui_smoke_wrapper")
    if ui_full_result is not None and not ui_full_result.get("ok"):
        failures.append("visible_ui_full_template")

    output_paths = [str(run_dir), str(ORGANIZED_ROOT), str(LATEST_RECEIPT)]
    output_paths.extend(str(path) for path in run_dir.glob("*.log"))
    c_drive_used = any(Path(path).drive.lower() == "c:" for path in output_paths if path)
    summary = {
        "scripts_checked": len(script_results),
        "scripts_passed": sum(1 for item in script_results if item.get("ok")),
        "prompt_sources_checked": len(prompt_results),
        "prompt_sources_passed": sum(1 for item in prompt_results if item.get("ok")),
        "ui_smoke_status": "not_run" if ui_smoke_result is None else "PASS" if ui_smoke_result.get("ok") else "FAIL",
        "ui_full_template_status": "not_run" if ui_full_result is None else "PASS" if ui_full_result.get("ok") else "FAIL",
        "c_drive_used": c_drive_used,
    }
    receipt = {
        "schema": "engel_training_hub_verify_v1",
        "run_id": run_id,
        "status": "PASS" if not failures and not c_drive_used else "FAIL",
        "updated_at_utc": utc_now(),
        "canonical_root": str(CANONICAL_ROOT),
        "catalog_path": str(ORGANIZED_ROOT / "catalog.json"),
        "run_dir": str(run_dir),
        "script_results": script_results,
        "prompt_source_results": prompt_results,
        "ui_smoke_result": ui_smoke_result,
        "ui_full_template_result": ui_full_result,
        "summary": summary,
        "failures": failures,
        "receipt_path": str(LATEST_RECEIPT),
    }
    safe_write_json(LATEST_RECEIPT, receipt)
    safe_write_json(run_dir / "receipt.json", receipt)
    write_markdown(receipt, run_dir / "README.md")
    print(json.dumps({"event": "engel_training_hub_verify_complete", "status": receipt["status"], "summary": summary, "receipt": str(LATEST_RECEIPT)}, indent=2))
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
