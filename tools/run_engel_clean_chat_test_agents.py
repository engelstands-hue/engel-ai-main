from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = ROOT / "reports" / "engel_clean_chat_test_agents"
RECEIPT_DIR = REPORT_ROOT / "receipts"
RUNPOD_WORK_ORDER_DIR = REPORT_ROOT / "runpod_work_orders"
LATEST_RECEIPT = ROOT / "runtime" / "engel_clean_chat_test_agents_latest.json"
LATEST_REPORT = REPORT_ROOT / "ENGEL_CLEAN_CHAT_TEST_AGENTS_LATEST.md"
MANIFEST = ROOT / "dist" / "ENGEL_CURRENT_RELEASE_MANIFEST_20260607.json"
ACTIVE_SESSION = ROOT / "reports" / "ai_local_open_chat_supervised_run" / "sessions" / "LOCAL_OPEN_CHAT_SUPERVISED_SESSION_ACTIVE.json"
RUST_EXE = ROOT / "runtime" / "temp" / "engel-rust-rewrite" / "cargo-target" / "debug" / "engel-ai-rs.exe"
RUNPOD_CONFIG = ROOT / "runtime" / "runpod" / "engel_runpod_config.json"
RUNPOD_SECRET = ROOT / "runtime" / "secrets" / "runpod_api_key.txt"
RUNPOD_EXTERNAL_WORK_ORDER_DIR = ROOT / "runtime" / "runpod" / "test_agent_work_orders"

BAD_TERMS = [
    "Say this is Engel session draft turn one",
    "APPROVED LOCAL CHAT MEMORY CONTEXT",
    "UNTRUSTED LOCAL SESSION TRANSCRIPT",
    "available commands",
    "Loading model",
]


class AgentFailure(RuntimeError):
    pass


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_c_drive(path: Path) -> bool:
    text = str(path).replace("/", "\\").lower()
    return text.startswith("c:\\") or text.startswith("\\\\?\\c:\\")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    if is_c_drive(path):
        raise AgentFailure(f"refusing to write to C: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    if is_c_drive(path):
        raise AgentFailure(f"refusing to write to C: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def run_command(args: list[str], *, cwd: Path = ROOT, timeout: int = 300) -> dict[str, Any]:
    started = time.perf_counter()
    completed = subprocess.run(
        args,
        cwd=str(cwd),
        text=True,
        capture_output=True,
        timeout=timeout,
        shell=False,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return {
        "args": args,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "elapsed_ms": int((time.perf_counter() - started) * 1000),
    }


def agent_result(name: str, purpose: str) -> dict[str, Any]:
    return {
        "agent": name,
        "purpose": purpose,
        "ok": False,
        "started_at_utc": iso_now(),
        "finished_at_utc": "",
        "checks": [],
        "artifacts": [],
        "errors": [],
    }


def add_check(result: dict[str, Any], name: str, ok: bool, detail: str = "", **extra: Any) -> None:
    item: dict[str, Any] = {"name": name, "ok": bool(ok)}
    if detail:
        item["detail"] = detail
    item.update(extra)
    result["checks"].append(item)
    if not ok:
        result["errors"].append(f"{name}: {detail}" if detail else name)


def finish_agent(result: dict[str, Any]) -> dict[str, Any]:
    result["finished_at_utc"] = iso_now()
    result["ok"] = not result["errors"]
    return result


def text_has_bad_terms(text: str) -> list[str]:
    lowered = text.lower()
    return [term for term in BAD_TERMS if term.lower() in lowered]


def resolve_manifest_path(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else ROOT / path


def load_manifest() -> dict[str, Any]:
    if not MANIFEST.exists():
        raise AgentFailure(f"missing manifest: {MANIFEST}")
    return read_json(MANIFEST)


def release_verifier_agent(timeout: int) -> dict[str, Any]:
    result = agent_result(
        "release_verifier_agent",
        "Runs the current release verifier exactly as a release gate.",
    )
    command = [sys.executable, str(ROOT / "tools" / "verify_engel_current_release_manifest.py")]
    run = run_command(command, timeout=timeout)
    result["command"] = {k: v for k, v in run.items() if k not in {"stdout", "stderr"}}
    result["stdout_preview"] = run["stdout"][:2000]
    result["stderr_preview"] = run["stderr"][:2000]
    add_check(result, "verifier_return_code_zero", run["returncode"] == 0, f"returncode={run['returncode']}")
    parsed: dict[str, Any] = {}
    if run["stdout"].strip():
        try:
            parsed = json.loads(run["stdout"])
        except json.JSONDecodeError as exc:
            add_check(result, "verifier_stdout_json", False, str(exc))
        else:
            add_check(result, "verifier_stdout_json", True)
            add_check(result, "verifier_ok_true", parsed.get("ok") is True, str(parsed.get("ok")))
            result["manifest_sha256"] = parsed.get("manifest_sha256")
            result["local_chat_real_output"] = parsed.get("local_chat_real_output")
    else:
        add_check(result, "verifier_stdout_json", False, "empty stdout")
    return finish_agent(result)



def standalone_chat_agent(timeout: int) -> dict[str, Any]:
    result = agent_result(
        "standalone_chat_agent",
        "Runs the strict Engel standalone chat verifier against the same chat path used by the UI.",
    )
    command = [sys.executable, str(ROOT / "tools" / "verify_engel_standalone_chat_llm.py")]
    run = run_command(command, timeout=timeout)
    result["command"] = {k: v for k, v in run.items() if k not in {"stdout", "stderr"}}
    result["stdout_preview"] = run["stdout"][:2000]
    result["stderr_preview"] = run["stderr"][:2000]
    add_check(result, "standalone_verifier_return_code_zero", run["returncode"] == 0, f"returncode={run['returncode']}")
    if run["stdout"].strip():
        try:
            parsed = json.loads(run["stdout"])
        except json.JSONDecodeError as exc:
            add_check(result, "standalone_verifier_stdout_json", False, str(exc))
        else:
            result["chat_receipt_path"] = parsed.get("chat_receipt_path")
            result["external_chat_receipt_path"] = parsed.get("external_chat_receipt_path")
            result["reply_preview"] = parsed.get("reply_preview")
            add_check(result, "standalone_verifier_stdout_json", True)
            add_check(result, "standalone_verifier_ok_true", parsed.get("ok") is True, str(parsed.get("ok")))
            check_names = {check.get("name") for check in parsed.get("checks") or []}
            for required in [
                "live_chat_style_score_ok",
                "live_chat_reply_mentions_engel_ai_main",
                "live_chat_reply_mentions_sub_engel_or_shared_room",
                "live_chat_reply_mentions_receipts",
                "live_chat_no_training_drift",
                "live_chat_no_fake_proof_location",
            ]:
                add_check(result, f"standalone_has_{required}", required in check_names, required)
    else:
        add_check(result, "standalone_verifier_stdout_json", False, "empty stdout")
    return finish_agent(result)
def check_prompt_file(path_text: str, result: dict[str, Any], label: str) -> None:
    path = resolve_manifest_path(path_text)
    add_check(result, f"{label}_constructed_prompt_exists", path.exists(), str(path))
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8", errors="replace")
    add_check(result, f"{label}_prompt_uses_chatml_system", "<|im_start|>system" in text, str(path))
    bad = text_has_bad_terms(text)
    add_check(result, f"{label}_prompt_has_no_pollution_terms", not bad, ", ".join(bad), path=str(path))


def prompt_cleanliness_agent() -> dict[str, Any]:
    result = agent_result(
        "prompt_cleanliness_agent",
        "Audits release receipts, constructed prompts, and active session for prompt pollution.",
    )
    manifest = load_manifest()
    local_chat = manifest.get("local_chat_real_output") or {}
    add_check(result, "manifest_local_chat_real_output_flag", local_chat.get("real_output_verified") is True)
    first = read_json(resolve_manifest_path(str(local_chat.get("first_receipt") or "")))
    second = read_json(resolve_manifest_path(str(local_chat.get("second_receipt") or "")))
    session = read_json(resolve_manifest_path(str(local_chat.get("active_session") or str(ACTIVE_SESSION))))

    for label, receipt in [("first", first), ("second", second)]:
        add_check(result, f"{label}_receipt_ok", receipt.get("ok") is True)
        add_check(result, f"{label}_receipt_readable", receipt.get("readable_output_captured") is True)
        add_check(result, f"{label}_approved_context_not_injected", receipt.get("approved_memory_context_path") is None)
        reply = str(receipt.get("assistant_reply") or "")
        add_check(result, f"{label}_reply_nonempty", bool(reply.strip()), reply)
        add_check(result, f"{label}_reply_not_old_ready_loop", reply.strip() != "Ready.", reply)
        bad_reply = text_has_bad_terms(reply)
        add_check(result, f"{label}_reply_has_no_pollution_terms", not bad_reply, ", ".join(bad_reply))
        check_prompt_file(str(receipt.get("constructed_prompt_path") or ""), result, label)

    add_check(result, "first_reset_for_prompt_pollution", first.get("session_reset_for_prompt_pollution") is True)
    add_check(result, "second_continued_fresh_session", second.get("session_reset_for_prompt_pollution") is False)
    turns = session.get("turns") if isinstance(session, dict) else []
    add_check(result, "active_session_has_turns", isinstance(turns, list) and len(turns) >= 2, f"turns={len(turns) if isinstance(turns, list) else 'not-list'}")
    session_text = json.dumps(turns, ensure_ascii=False)
    bad_session = text_has_bad_terms(session_text)
    add_check(result, "active_session_has_no_pollution_terms", not bad_session, ", ".join(bad_session))
    return finish_agent(result)


def run_rust_chat(prompt: str, timeout: int) -> dict[str, Any]:
    command = [
        str(RUST_EXE),
        "local-chat",
        "bounded-run-execute",
        "--approve",
        "APPROVE_LOCAL_CHAT_BOUNDED_RUN_EXECUTION",
        "--",
        prompt,
    ]
    run = run_command(command, timeout=timeout)
    if run["returncode"] != 0:
        raise AgentFailure(f"Rust chat command failed returncode={run['returncode']} stderr={run['stderr'][:1000]}")
    try:
        data = json.loads(run["stdout"])
    except json.JSONDecodeError as exc:
        raise AgentFailure(f"Rust chat stdout was not JSON: {exc}: {run['stdout'][:1000]}") from exc
    data["agent_command_elapsed_ms"] = run["elapsed_ms"]
    return data


def live_local_probe_agent(timeout: int, restore_session: bool) -> dict[str, Any]:
    result = agent_result(
        "live_local_probe_agent",
        "Runs real local Rust bounded chat probes and verifies clean prompts/replies.",
    )
    add_check(result, "rust_executable_exists", RUST_EXE.exists(), str(RUST_EXE))
    if not RUST_EXE.exists():
        return finish_agent(result)

    before_bytes = ACTIVE_SESSION.read_bytes() if ACTIVE_SESSION.exists() else None
    before_hash = hashlib.sha256(before_bytes).hexdigest().upper() if before_bytes is not None else ""
    result["active_session_before_sha256"] = before_hash
    probes = [
        "Engel test agent: answer in one short sentence, what can you help test?",
        "Engel test agent: reply with one short sentence and do not say Ready.",
    ]
    probe_results: list[dict[str, Any]] = []
    try:
        for index, prompt in enumerate(probes, start=1):
            data = run_rust_chat(prompt, timeout)
            receipt_path = resolve_manifest_path(str(data.get("receipt_path") or ""))
            constructed_prompt_path = resolve_manifest_path(str(data.get("constructed_prompt_path") or ""))
            reply = str(data.get("assistant_reply") or "")
            item = {
                "index": index,
                "prompt": prompt,
                "ok": data.get("ok") is True,
                "assistant_reply": reply,
                "readable_output_captured": data.get("readable_output_captured") is True,
                "receipt_path": str(receipt_path),
                "constructed_prompt_path": str(constructed_prompt_path),
                "elapsed_ms": data.get("agent_command_elapsed_ms"),
            }
            probe_results.append(item)
            add_check(result, f"probe_{index}_ok", data.get("ok") is True, reply)
            add_check(result, f"probe_{index}_readable", data.get("readable_output_captured") is True, reply)
            add_check(result, f"probe_{index}_receipt_exists", receipt_path.exists(), str(receipt_path))
            add_check(result, f"probe_{index}_constructed_prompt_exists", constructed_prompt_path.exists(), str(constructed_prompt_path))
            add_check(result, f"probe_{index}_approved_context_not_injected", (data.get("receipt") or data).get("approved_memory_context_path") is None)
            add_check(result, f"probe_{index}_reply_nonempty", bool(reply.strip()), reply)
            add_check(result, f"probe_{index}_reply_not_ready_loop", reply.strip() != "Ready.", reply)
            bad_reply = text_has_bad_terms(reply)
            add_check(result, f"probe_{index}_reply_has_no_pollution_terms", not bad_reply, ", ".join(bad_reply))
            if constructed_prompt_path.exists():
                prompt_text = constructed_prompt_path.read_text(encoding="utf-8", errors="replace")
                add_check(result, f"probe_{index}_prompt_current_message_present", prompt in prompt_text, str(constructed_prompt_path))
                add_check(result, f"probe_{index}_prompt_chatml", "<|im_start|>system" in prompt_text, str(constructed_prompt_path))
                bad_prompt = text_has_bad_terms(prompt_text)
                add_check(result, f"probe_{index}_prompt_has_no_pollution_terms", not bad_prompt, ", ".join(bad_prompt))
    finally:
        if restore_session:
            if before_bytes is None:
                if ACTIVE_SESSION.exists():
                    ACTIVE_SESSION.unlink()
            else:
                ACTIVE_SESSION.parent.mkdir(parents=True, exist_ok=True)
                ACTIVE_SESSION.write_bytes(before_bytes)
            result["active_session_restored"] = True
        else:
            result["active_session_restored"] = False
    if restore_session and before_bytes is not None and ACTIVE_SESSION.exists():
        after_hash = sha256_file(ACTIVE_SESSION)
        add_check(result, "active_session_restore_hash_match", after_hash == before_hash, after_hash)
    result["probes"] = probe_results
    return finish_agent(result)


def latest_file(directory: Path, pattern: str) -> Path | None:
    try:
        files = [path for path in directory.glob(pattern) if path.is_file()]
    except OSError:
        return None
    if not files:
        return None
    files.sort(key=lambda path: path.stat().st_mtime)
    return files[-1]


def attach_latest_runpod_receipts(result: dict[str, Any], *, live_required: bool) -> None:
    receipt_dir = ROOT / "runtime" / "runpod" / "receipts"
    preflight_path = latest_file(receipt_dir, "RUNPOD_PREFLIGHT_*.json")
    stretch_path = latest_file(receipt_dir, "RUNPOD_ENGEL_STRETCH_*.json")
    if preflight_path is None:
        add_check(result, "latest_runpod_preflight_receipt_present", False, str(receipt_dir))
    else:
        try:
            preflight = read_json(preflight_path)
        except Exception as exc:
            add_check(result, "latest_runpod_preflight_receipt_json", False, str(exc))
        else:
            result["latest_runpod_preflight"] = {
                "path": str(preflight_path),
                "ok": preflight.get("ok"),
                "endpoint_count": preflight.get("endpoint_count"),
                "pod_count": preflight.get("pod_count"),
                "endpoints": preflight.get("endpoints"),
            }
            add_check(result, "latest_runpod_preflight_receipt_present", True, str(preflight_path))
            add_check(result, "latest_runpod_preflight_ok", preflight.get("ok") is True, str(preflight.get("ok")))
    if stretch_path is None:
        add_check(result, "latest_runpod_stretch_receipt_present", False, str(receipt_dir))
    else:
        try:
            stretch = read_json(stretch_path)
        except Exception as exc:
            add_check(result, "latest_runpod_stretch_receipt_json", False, str(exc))
        else:
            result["latest_runpod_stretch"] = {
                "path": str(stretch_path),
                "ok": stretch.get("ok"),
                "model": stretch.get("model"),
                "models_probe": stretch.get("models_probe"),
                "task_count": stretch.get("task_count"),
                "passed_task_count": stretch.get("passed_task_count"),
                "tasks": stretch.get("tasks"),
            }
            add_check(result, "latest_runpod_stretch_receipt_present", True, str(stretch_path))
            if live_required:
                add_check(result, "latest_runpod_stretch_ok", stretch.get("ok") is True, str(stretch.get("ok")))
            else:
                add_check(result, "latest_runpod_stretch_recorded", True, "not required for non-live agent run")

def runpod_handoff_agent(write_external: bool, run_live: bool, timeout: int, max_tasks: int) -> dict[str, Any]:
    result = agent_result(
        "runpod_live_agent",
        "Runs the guarded RunPod live stretch verifier when requested; work-order output is optional only.",
    )
    config_present = RUNPOD_CONFIG.exists()
    secret_present = RUNPOD_SECRET.exists()
    add_check(result, "runpod_config_path_off_c", not is_c_drive(RUNPOD_CONFIG), str(RUNPOD_CONFIG))
    add_check(result, "runpod_secret_path_off_c", not is_c_drive(RUNPOD_SECRET), str(RUNPOD_SECRET))
    add_check(result, "runpod_config_present", config_present, str(RUNPOD_CONFIG))
    add_check(result, "runpod_secret_present", secret_present, str(RUNPOD_SECRET))
    config: dict[str, Any] = {}
    if config_present:
        try:
            config = read_json(RUNPOD_CONFIG)
        except Exception as exc:
            add_check(result, "runpod_config_json", False, str(exc))
        else:
            add_check(result, "runpod_config_json", True)
    attach_latest_runpod_receipts(result, live_required=run_live)

    if write_external:
        work_order = {
            "schema": "engel_runpod_clean_chat_test_agent_work_order_v1",
            "created_at_utc": iso_now(),
            "created_by": "Engel Main clean-chat test agents",
            "purpose": "Optional RunPod remote checker work order for Engel Main clean local-chat proof artifacts.",
            "spend_guard": {
                "live_run_default": False,
                "requires_explicit_flag": "--runpod-live",
                "api_key_value_visible": False,
            },
            "runpod": {
                "config_path": str(RUNPOD_CONFIG),
                "secret_path": str(RUNPOD_SECRET),
                "config_present": config_present,
                "secret_present": secret_present,
                "endpoint_id": config.get("endpoint_id"),
                "openai_base_url": config.get("openai_base_url"),
                "model": config.get("openai_model_id") or config.get("model") or config.get("huggingface_model_id"),
            },
            "local_commands_for_remote_checker": [
                "python tools/verify_engel_current_release_manifest.py",
                "python tools/verify_engel_clean_chat_test_agents.py",
                "python tools/run_engel_clean_chat_test_agents.py --skip-live-local --runpod-live",
            ],
            "live_runpod_command_when_approved": f"python tools/run_engel_runpod_stretch.py --max-tasks {max_tasks} --timeout {timeout}",
            "must_check": [
                "release verifier ok true",
                "local chat constructed prompts contain no approved-memory or transcript pollution",
                "active session has no loader or old draft-memory terms",
                "RunPod stretch tasks pass only when explicitly approved",
            ],
        }
        work_order_path = RUNPOD_WORK_ORDER_DIR / f"ENGEL_RUNPOD_CLEAN_CHAT_TEST_AGENT_{utc_stamp()}.json"
        write_json(work_order_path, work_order)
        result["work_order_path"] = str(work_order_path)
        result["artifacts"].append(str(work_order_path))
        add_check(result, "local_runpod_work_order_written", work_order_path.exists(), str(work_order_path))
        try:
            RUNPOD_EXTERNAL_WORK_ORDER_DIR.mkdir(parents=True, exist_ok=True)
            external_path = RUNPOD_EXTERNAL_WORK_ORDER_DIR / work_order_path.name
            write_json(external_path, work_order)
        except Exception as exc:
            add_check(result, "external_runpod_work_order_written", False, str(exc))
        else:
            result["external_work_order_path"] = str(external_path)
            result["artifacts"].append(str(external_path))
            add_check(result, "external_runpod_work_order_written", True, str(external_path))
    else:
        result["work_order_path"] = "not written; RunPod is direct-live when --runpod-live is used"
        add_check(result, "no_runpod_packet_written", True, "no packet/work-order written")
    if run_live:
        command = [sys.executable, str(ROOT / "tools" / "run_engel_runpod_stretch.py"), "--timeout", str(timeout), "--max-tasks", str(max_tasks)]
        run = run_command(command, timeout=timeout * max(2, max_tasks + 1))
        result["runpod_live_command"] = {k: v for k, v in run.items() if k not in {"stdout", "stderr"}}
        result["runpod_live_stdout_preview"] = run["stdout"][:2000]
        result["runpod_live_stderr_preview"] = run["stderr"][:2000]
        add_check(result, "runpod_live_return_code_zero", run["returncode"] == 0, f"returncode={run['returncode']}")
        try:
            live_data = json.loads(run["stdout"])
        except json.JSONDecodeError as exc:
            add_check(result, "runpod_live_stdout_json", False, str(exc))
        else:
            result["runpod_live_receipt"] = live_data
            add_check(result, "runpod_live_ok", live_data.get("ok") is True, str(live_data.get("ok")))
    else:
        result["runpod_live_skipped"] = True
    return finish_agent(result)


def render_report(receipt: dict[str, Any]) -> str:
    lines = [
        "# Engel Clean Chat Test Agents",
        "",
        f"created_at_utc: {receipt['created_at_utc']}",
        f"ok: {str(receipt['ok']).lower()}",
        f"receipt: {receipt['receipt_path']}",
        "",
        "## Agents",
    ]
    for agent in receipt.get("agents", []):
        lines.extend([
            "",
            f"### {agent['agent']}",
            f"ok: {str(agent.get('ok') is True).lower()}",
            f"purpose: {agent.get('purpose', '')}",
        ])
        for check in agent.get("checks", []):
            status = "PASS" if check.get("ok") is True else "FAIL"
            detail = check.get("detail") or ""
            lines.append(f"- {status} {check.get('name')}: {detail}")
    lines.append("")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Engel clean-chat test agents.")
    parser.add_argument("--skip-live-local", action="store_true", help="Skip real local Rust model probes.")
    parser.add_argument("--no-restore-session", action="store_true", help="Do not restore active local-chat session after live probes.")
    parser.add_argument("--runpod-live", action="store_true", help="Run the guarded RunPod stretch verifier. This may spend RunPod credits.")
    parser.add_argument("--write-runpod-work-order", action="store_true", help="Also write the RunPod work order to runtime/runpod/test_agent_work_orders.")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--runpod-max-tasks", type=int, default=5)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = utc_stamp()
    receipt_path = RECEIPT_DIR / f"ENGEL_CLEAN_CHAT_TEST_AGENTS_{stamp}.json"
    receipt: dict[str, Any] = {
        "schema": "engel_clean_chat_test_agents_v1",
        "created_at_utc": iso_now(),
        "ok": False,
        "receipt_path": str(receipt_path),
        "agents": [],
        "bad_terms_guarded": BAD_TERMS,
        "c_drive_writes_allowed": False,
        "runpod_live_requested": bool(args.runpod_live),
    }
    agents: list[dict[str, Any]] = []
    try:
        agents.append(release_verifier_agent(args.timeout))
        agents.append(standalone_chat_agent(args.timeout))
        agents.append(prompt_cleanliness_agent())
        if args.skip_live_local:
            skipped = agent_result("live_local_probe_agent", "Skipped by --skip-live-local.")
            skipped["skipped"] = True
            skipped["ok"] = True
            skipped["finished_at_utc"] = iso_now()
            agents.append(skipped)
        else:
            agents.append(live_local_probe_agent(args.timeout, restore_session=not args.no_restore_session))
        agents.append(runpod_handoff_agent(args.write_runpod_work_order, args.runpod_live, args.timeout, max(1, args.runpod_max_tasks)))
    except Exception as exc:
        failure = agent_result("test_agent_runner", "Top-level runner failure.")
        failure["errors"].append(str(exc))
        agents.append(finish_agent(failure))
    receipt["agents"] = agents
    receipt["ok"] = all(agent.get("ok") is True for agent in agents)
    receipt["agent_count"] = len(agents)
    receipt["passed_agent_count"] = sum(1 for agent in agents if agent.get("ok") is True)
    write_json(receipt_path, receipt)
    LATEST_RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(receipt_path, LATEST_RECEIPT)
    write_text(LATEST_REPORT, render_report(receipt))
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
