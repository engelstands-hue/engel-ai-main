#!/usr/bin/env python3
"""Run repeated Engel UI creation-training hours with cleanup between cycles."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "tools" / "run_engel_ui_input_creation_training_hour.py"
REPORT_DIR = ROOT / "reports" / "meeting_rooms"
MEMORY_DIR = ROOT / "memory"
LOG_DIR = ROOT / "reports" / "meeting_rooms" / "training_loop_logs"
TRAINING_MEMORY = MEMORY_DIR / "project_engel_ui_input_creation_training_20260526.md"
TEMP_CLEAN_DIRS = (
    ROOT / "runtime" / "tmp",
    ROOT / "runtime" / "pyinstaller_tmp",
)


def local_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%dT%H%M%S")


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def latest_next_prompt_start() -> int:
    next_start = 1
    for path in REPORT_DIR.glob("ENGEL_UI_INPUT_CREATION_TRAINING_HOUR_*.json"):
        payload = load_json(path)
        try:
            start = int(payload.get("prompt_start_index") or 1)
            count = int(payload.get("target_jobs") or 0)
        except Exception:
            continue
        if count >= 60:
            next_start = max(next_start, start + count)
    return next_start


def assert_inside_root(path: Path) -> Path:
    resolved = path.resolve()
    root = ROOT.resolve()
    if resolved == root or root not in resolved.parents:
        raise RuntimeError(f"refusing to clean outside Engel App root: {resolved}")
    return resolved


def _remove_path(child: Path) -> tuple[bool, str | None]:
    try:
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child, onerror=_rmtree_onerror)
        else:
            child.unlink(missing_ok=True)
        return True, None
    except OSError as exc:
        return False, f"{type(exc).__name__}: {exc}"


def _rmtree_onerror(func, path, exc_info) -> None:
    try:
        import os
        import stat

        os.chmod(path, stat.S_IWRITE)
        func(path)
    except OSError:
        pass


def clean_training_transients(cycle: int, phase: str, loop_stamp: str) -> dict[str, Any]:
    removed: list[str] = []
    kept: list[str] = []
    skipped: list[str] = []
    for folder in TEMP_CLEAN_DIRS:
        folder.mkdir(parents=True, exist_ok=True)
        resolved_folder = assert_inside_root(folder)
        for child in resolved_folder.iterdir():
            if child.name == ".gitkeep":
                kept.append(str(child))
                continue
            ok, reason = _remove_path(child)
            if ok:
                removed.append(str(child))
            else:
                skipped.append(f"{child} ({reason})")
    receipt = {
        "loop_stamp": loop_stamp,
        "cycle": cycle,
        "phase": phase,
        "timestamp": dt.datetime.now().isoformat(timespec="seconds"),
        "cleaned_dirs": [str(path) for path in TEMP_CLEAN_DIRS],
        "removed_count": len(removed),
        "removed": removed,
        "skipped_count": len(skipped),
        "skipped": skipped,
        "kept": kept,
        "safety": {
            "only_runtime_tmp_dirs": True,
            "artifacts_preserved": True,
            "reports_preserved": True,
            "source_preserved": True,
        },
    }
    path = REPORT_DIR / f"ENGEL_UI_INPUT_CREATION_TRAINING_LOOP_{loop_stamp}_cleanup_cycle_{cycle}_{phase}.json"
    path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    return {"path": str(path), "removed_count": len(removed)}


def new_receipts_since(before: set[str]) -> list[Path]:
    paths = sorted(REPORT_DIR.glob("ENGEL_UI_INPUT_CREATION_TRAINING_HOUR_*.json"), key=lambda item: item.stat().st_mtime)
    return [path for path in paths if str(path) not in before]


def strict_summary_ok(summary: dict[str, Any]) -> bool:
    required = (
        "all_ui_finished",
        "all_jobs_have_orders",
        "all_jobs_have_returns",
        "all_jobs_have_artifacts",
        "all_expected_kinds_matched",
        "all_expected_job_types_matched",
        "all_expected_workers_matched",
    )
    return all(bool(summary.get(key)) for key in required)


def receipt_artifact_files_exist(receipt: dict[str, Any]) -> tuple[bool, list[str]]:
    missing: list[str] = []
    for record in receipt.get("records", []):
        if not isinstance(record, dict):
            continue
        for artifact in record.get("new_artifacts", []):
            if not isinstance(artifact, dict):
                continue
            for file_name in artifact.get("files", []):
                if not Path(str(file_name)).exists():
                    missing.append(str(file_name))
    return not missing, missing


def run_command(command: list[str], log_path: Path, env: dict[str, str]) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as log:
        proc = subprocess.Popen(
            command,
            cwd=str(ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        assert proc.stdout is not None
        for line in proc.stdout:
            log.write(line)
            log.flush()
            print(line, end="", flush=True)
        return proc.wait()


def append_memory(loop_report: Path, cycle_reports: list[Path], loop_receipt: Path) -> None:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        "",
        "## Four-Cycle Build-On Training Loop",
        "",
        f"Saved: {dt.datetime.now().isoformat(timespec='seconds')}",
        "",
        "Josh requested four one-hour UI creation-training cycles, each building on the previous prompt bank and cleaning scratch state between each 60-job pass.",
        "",
        f"- Loop receipt: `{loop_receipt.relative_to(ROOT).as_posix()}`",
        f"- Loop report: `{loop_report.relative_to(ROOT).as_posix()}`",
        *[f"- Cycle report: `{path.relative_to(ROOT).as_posix()}`" for path in cycle_reports],
        "",
        "Memory rule preserved:",
        "- Prompts 121+ add build-on lesson layers instead of replaying older prompt text.",
        "- Keep explicit output format first, then use topic words to refine content.",
        "- Clean only Engel runtime scratch folders between cycles; artifacts, reports, memory, source, and worker receipts stay preserved.",
    ]
    with TRAINING_MEMORY.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(lines).rstrip() + "\n")


def run_loop(args: argparse.Namespace) -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    loop_stamp = local_stamp()
    start_index = args.prompt_start_index or latest_next_prompt_start()
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", str(ROOT))
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    env.setdefault("ENGEL_MEETING_ROOM_ANDROID_RETURN_WAIT_SECONDS", "90")
    env.setdefault("ENGEL_TRAINING_RETURN_GRACE_SECONDS", "60")

    cycle_reports: list[Path] = []
    loop_records: list[dict[str, Any]] = []

    for cycle in range(1, args.cycles + 1):
        cycle_start_index = start_index + ((cycle - 1) * args.target_jobs)
        pre_cleanup = clean_training_transients(cycle, "before", loop_stamp)
        before = {str(path) for path in REPORT_DIR.glob("ENGEL_UI_INPUT_CREATION_TRAINING_HOUR_*.json")}
        log_path = LOG_DIR / f"ENGEL_UI_INPUT_CREATION_TRAINING_LOOP_{loop_stamp}_cycle_{cycle}.log"
        command = [
            sys.executable,
            str(RUNNER),
            "--minutes",
            str(args.minutes),
            "--target-jobs",
            str(args.target_jobs),
            "--prompt-start-index",
            str(cycle_start_index),
            "--per-job-timeout",
            str(args.per_job_timeout),
        ]
        if args.skip_final_wait:
            command.append("--skip-final-wait")

        print(
            json.dumps(
                {
                    "event": "loop_cycle_start",
                    "loop_stamp": loop_stamp,
                    "cycle": cycle,
                    "cycles": args.cycles,
                    "prompt_start_index": cycle_start_index,
                    "target_jobs": args.target_jobs,
                    "minutes": args.minutes,
                    "pre_cleanup": pre_cleanup,
                },
                sort_keys=True,
            ),
            flush=True,
        )
        started = time.time()
        return_code = run_command(command, log_path, env)
        elapsed = round(time.time() - started, 3)
        receipts = new_receipts_since(before)
        if not receipts:
            raise RuntimeError(f"cycle {cycle} did not create a training receipt")
        receipt_path = receipts[-1]
        receipt = load_json(receipt_path)
        summary = receipt.get("summary") if isinstance(receipt.get("summary"), dict) else {}
        artifact_files_ok, missing_files = receipt_artifact_files_exist(receipt)
        post_cleanup = clean_training_transients(cycle, "after", loop_stamp)

        cycle_ok = return_code == 0 and strict_summary_ok(summary) and artifact_files_ok
        cycle_report = REPORT_DIR / f"ENGEL_UI_INPUT_CREATION_TRAINING_LOOP_{loop_stamp}_cycle_{cycle}.md"
        cycle_report.write_text(
            "\n".join(
                [
                    f"# Engel UI Input Creation Training Loop Cycle {cycle}",
                    "",
                    f"loop_stamp: {loop_stamp}",
                    f"cycle: {cycle}/{args.cycles}",
                    f"prompt_start_index: {cycle_start_index}",
                    f"target_jobs: {args.target_jobs}",
                    f"requested_minutes: {args.minutes}",
                    f"elapsed_seconds: {elapsed}",
                    f"return_code: {return_code}",
                    f"strict_ok: {strict_summary_ok(summary)}",
                    f"artifact_files_ok: {artifact_files_ok}",
                    f"cycle_ok: {cycle_ok}",
                    "",
                    "Files:",
                    f"- receipt: `{receipt_path.relative_to(ROOT).as_posix()}`",
                    f"- summary: `{Path(str(receipt.get('summary_path', ''))).relative_to(ROOT).as_posix() if receipt.get('summary_path') else ''}`",
                    f"- transcript: `{Path(str(receipt.get('transcript', ''))).relative_to(ROOT).as_posix() if receipt.get('transcript') else ''}`",
                    f"- log: `{log_path.relative_to(ROOT).as_posix()}`",
                    f"- cleanup before: `{Path(pre_cleanup['path']).relative_to(ROOT).as_posix()}`",
                    f"- cleanup after: `{Path(post_cleanup['path']).relative_to(ROOT).as_posix()}`",
                    "",
                    "Summary:",
                    f"- jobs: {summary.get('jobs')}",
                    f"- workers: {summary.get('workers')}",
                    f"- artifacts: {summary.get('artifacts')}",
                    f"- job_types: {summary.get('job_types')}",
                    f"- expected_artifact_kind_matches: {summary.get('expected_artifact_kind_matches')}",
                    f"- expected_job_type_matches: {summary.get('expected_job_type_matches')}",
                    f"- expected_worker_matches: {summary.get('expected_worker_matches')}",
                    "",
                    "Missing artifact files:",
                    *[f"- {path}" for path in missing_files],
                    "",
                ]
            ).rstrip()
            + "\n",
            encoding="utf-8",
        )
        cycle_reports.append(cycle_report)
        loop_records.append(
            {
                "cycle": cycle,
                "prompt_start_index": cycle_start_index,
                "receipt": str(receipt_path),
                "cycle_report": str(cycle_report),
                "log": str(log_path),
                "return_code": return_code,
                "elapsed_seconds": elapsed,
                "summary": summary,
                "artifact_files_ok": artifact_files_ok,
                "missing_files": missing_files,
                "pre_cleanup": pre_cleanup,
                "post_cleanup": post_cleanup,
                "cycle_ok": cycle_ok,
            }
        )
        print(
            json.dumps(
                {
                    "event": "loop_cycle_complete",
                    "loop_stamp": loop_stamp,
                    "cycle": cycle,
                    "cycle_ok": cycle_ok,
                    "receipt": str(receipt_path),
                    "summary": summary,
                },
                sort_keys=True,
            ),
            flush=True,
        )
        if not cycle_ok:
            break

    all_ok = len(loop_records) == args.cycles and all(record.get("cycle_ok") for record in loop_records)
    loop_receipt = REPORT_DIR / f"ENGEL_UI_INPUT_CREATION_TRAINING_LOOP_{loop_stamp}.json"
    loop_report = REPORT_DIR / f"ENGEL_UI_INPUT_CREATION_TRAINING_LOOP_{loop_stamp}.md"
    loop_payload = {
        "loop_stamp": loop_stamp,
        "started_prompt_index": start_index,
        "cycles_requested": args.cycles,
        "cycles_completed": len(loop_records),
        "target_jobs_per_cycle": args.target_jobs,
        "minutes_per_cycle": args.minutes,
        "all_ok": all_ok,
        "records": loop_records,
    }
    loop_receipt.write_text(json.dumps(loop_payload, indent=2), encoding="utf-8")
    loop_report.write_text(
        "\n".join(
            [
                "# Engel UI Input Creation Training Loop",
                "",
                f"loop_stamp: {loop_stamp}",
                f"started_prompt_index: {start_index}",
                f"cycles_requested: {args.cycles}",
                f"cycles_completed: {len(loop_records)}",
                f"target_jobs_per_cycle: {args.target_jobs}",
                f"minutes_per_cycle: {args.minutes}",
                f"all_ok: {all_ok}",
                "",
                "Cycle reports:",
                *[f"- `{path.relative_to(ROOT).as_posix()}`" for path in cycle_reports],
                "",
                "Receipts:",
                *[f"- cycle {record['cycle']}: `{Path(record['receipt']).relative_to(ROOT).as_posix()}`" for record in loop_records],
                "",
                "Cleanup:",
                "- Cleaned only `runtime/tmp` and `runtime/pyinstaller_tmp` before and after each cycle.",
                "- Artifacts, reports, memory, source, and remote-worker receipts were preserved.",
            ]
        ).rstrip()
        + "\n",
        encoding="utf-8",
    )
    append_memory(loop_report, cycle_reports, loop_receipt)
    print(json.dumps({"event": "loop_complete", "all_ok": all_ok, "loop_receipt": str(loop_receipt), "loop_report": str(loop_report)}, indent=2), flush=True)
    return 0 if all_ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cycles", type=int, default=4)
    parser.add_argument("--minutes", type=float, default=60.0)
    parser.add_argument("--target-jobs", type=int, default=60)
    parser.add_argument("--per-job-timeout", type=float, default=180.0)
    parser.add_argument("--prompt-start-index", type=int, default=0, help="0 means continue after latest completed full receipt")
    parser.add_argument("--skip-final-wait", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.cycles < 1:
        raise SystemExit("--cycles must be at least 1")
    if args.target_jobs < 1:
        raise SystemExit("--target-jobs must be at least 1")
    return run_loop(args)


if __name__ == "__main__":
    raise SystemExit(main())
