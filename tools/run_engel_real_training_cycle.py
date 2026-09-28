#!/usr/bin/env python3
"""Turn prompt-training sessions into real trained models, in one command.

Until now the Flutter "Prompt Training" panel graded 40 prompts per run and then
threw the result away: the SFT dataset builder admitted only external real-provider
turns, and the SLM roster was trained by hand from receipts. The material Engel
produced about itself never reached a weight or a classifier, so "training" was a
report, not a change.

This orchestrator is the transport that closes that loop. It takes the training
packs a session emitted (CONTRACT 1), ships them plus the CT-side tools to CT246,
rebuilds the SFT dataset there (which now has a stamp-gated admit path for packs),
rebuilds and retrains the selected SLM roster and/or the guarded CT246 local LLM
adapter, runs their evidence gates, mirrors verified SLM artifacts back to the ROG,
and writes the cycle receipt the UI reads (CONTRACT 2).

Two rules shape every decision in here:

* Fail-CLOSED on eligibility. A pack row whose contract fields are missing, or whose
  own `admit` verdict disagrees with the contract's admit rule, is NOT counted as
  admitted and raises a blocker. A broken emitter that over-admits would push
  ineligible text straight into a fine-tune, and that is unrecoverable once trained.
* Never claim a cycle that did not happen. Zero admitted rows, a short tool copy, a
  dataset build that admitted none of the pushed packs - each of those is a blocker
  with a plain reason, not a warning buried in a PASS.
* One mutating cycle at a time. The CLI holds an OS-released exclusive lock from before
  SSH resolution through the final receipt, while SLM packs, datasets, and candidates
  remain under the unique run directory. A second run fails before shared SFT/LoRA
  dataset state can be rewritten.

Where a failed step stops the run (documented per step in `run_cycle`):
  collect_packs / verify_construction_corpus / push_tools / push_packs /
  push_construction_corpus / slm_datasets -> STOP. Continuing would train on nothing,
    on truncated remote code, on material that never arrived, on mixed corpus evidence,
    or on stale SLM datasets - and would then report green metrics for all of it.
  build_dataset -> CONTINUE. The SLM lane reads receipts and packs directly, not the
    SFT split, so its result is still real information; the cycle can never be PASS.
  slm_train -> STOP the SLM release lane unless every requested task selected one
    gate-passing artifact in this cycle's isolated candidate directory.
  slm_verify failed -> mirror_back REFUSES to run. runtime/slm_models is the local
    chat hot path; a candidate is copied to a sibling staging directory, checked in
    full, and installed by one atomic directory swap with a unique rollback backup.
    That changes filesystem state only; serving activation remains a separate,
    hash-bound in-process acknowledgement and this cycle stays PARTIAL until it exists.

The weight-training lane is opt-in and operator-approved by exact phrase. The trainer
creates and evaluates a new adapter but never deploys or promotes it. Canary and
production promotion remain separate approval-gated operations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import stat
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Sequence

import engel_slm_roster as slm_roster
import engel_construction_corpus as construction_corpus
import engel_prompt_training_quarantine as prompt_quarantine
from engel_prompt_novelty import (
    CANONICALIZATION as BASE_PROMPT_CANONICALIZATION,
    canonical_base_prompt_sha256,
)
import engel_build_training_dataset as training_dataset
import engel_training_cycle_runtime_contract as runtime_budget


ROOT = Path(__file__).resolve().parents[1]
PACK_DIR = ROOT / "memory" / "training" / "packs"
QUARANTINE_DIR = ROOT / "memory" / "training" / "prompt_row_quarantines"
PACK_GLOB = "ENGEL_PROMPT_TRAINING_PACK_*.jsonl"
PACK_LATEST_NAME = "ENGEL_PROMPT_TRAINING_PACK_LATEST.json"
TRAINING_ASSET_MANIFEST_PATH = (
    ROOT / "memory" / "training" / "engel_main" / "training_assets_manifest.json"
)
CURRICULA_INDEX_PATH = (
    ROOT / "memory" / "training" / "engel_main" / "templates" / "curricula_index.json"
)
CANONICAL_TEMPLATES_DIR = CURRICULA_INDEX_PATH.parent
CURRICULUM_BINDING_SCHEMA = "engel_training_curriculum_binding_v1"
CANONICAL_CURRICULA = (
    ("capabilities", "Engel Capabilities", "engineering"),
    ("math_school", "Math School", "math"),
    ("self_build", "Self-Build", "engineering"),
    ("construction", "Construction Coordination", "aec"),
    ("chat_communication", "Chat Communication", "communication"),
)
CURRICULUM_BINDING_FIELDS = (
    "id",
    "title",
    "discipline",
    "version",
    "template_path",
    "template_sha256",
    "prompt_count",
    "maximum_hours",
)
REPORT_DIR = ROOT / "reports" / "real_training"
SLM_MIRROR_DIR = ROOT / "runtime" / "slm_models"
CYCLE_LOCK_PATH = ROOT / "runtime" / "locks" / "engel_real_training_cycle.lock"
LORA_PROOF_TOOL = ROOT / "tools" / "run_engel_ct246_local_lora_proof.py"
LORA_CANARY_TOOL = ROOT / "tools" / "run_engel_ct246_lora_canary_gate.py"
LORA_CONVERSION_TOOL = ROOT / "tools" / "run_engel_ct246_gguf_conversion.py"

CT_ROOT = "/opt/engel"
CT_TOOLS_DIR = f"{CT_ROOT}/tools"
CT_PACK_DIR = f"{CT_ROOT}/memory/training/packs"
CT_CYCLE_RUN_DIR = f"{CT_ROOT}/run/training_cycle"
CT_SLM_DIR = f"{CT_ROOT}/models-active/slm"
CT_DATASET_RECEIPT = f"{CT_ROOT}/reports/llm_training/ENGEL_TRAINING_DATASET_LATEST.json"
CT_LORA_PREFLIGHT_RECEIPT = f"{CT_ROOT}/reports/llm_training/ENGEL_CT246_LORA_PREFLIGHT_LATEST.json"
CT_LORA_PROOF_RECEIPT = f"{CT_ROOT}/reports/llm_training/ENGEL_CT246_LORA_PROOF_LATEST.json"
CT_VENV_PYTHON = f"{CT_ROOT}/.venv/bin/python"

# Pinned by exact string, the same way the dataset builder pins it: a row that does not
# declare this schema is a stranger, and a stranger is not trained on.
PACK_ROW_SCHEMA = "engel_prompt_training_pack_row_v1"
PACK_STAMPED_RECEIPT_SCHEMA = "engel_prompt_training_pack_receipt_v2"
PACK_SESSION_EVIDENCE_SCHEMA = "engel_prompt_training_session_evidence_v1"
PACK_WRITER_IDENTITY_SCHEMA = "engel_prompt_training_pack_writer_identity_v1"
PACK_RECEIPT_SUFFIX = ".receipt.json"
PACK_SESSION_PREFIX = "ENGEL_PROMPT_TRAINING_SESSION_"
PACK_SEGMENT_CHAIN_SCHEMA = "engel_prompt_training_pack_segment_chain_v1"
# The write-ahead prompt-use ledger. A position with a reservation but no pack row
# was consumed-but-unserved (a transport failure burned it); such positions can
# never be re-run (the novelty judge refuses replays), so without void tolerance a
# single failed prompt would permanently lock its curriculum out of model training
# (live 2026-08-15: capabilities completed 77/80 with prompts 1-3 unserved and its
# 4..80 pack could never chain from 1).
RESERVATIONS_DIR = ROOT / "memory" / "training" / "prompt_use_reservations"
PROMPT_PACK_WRITER_SOURCE = ROOT / "tools" / "run_engel_flutter_main_ui_prompt_training.py"
PROMPT_PACK_WRITER_RELATIVE_PATH = "tools/run_engel_flutter_main_ui_prompt_training.py"
SAFE_PROMPT_TRAINING_CHAT_PROVIDERS = {"local", "ct_sparse_moe_specialist"}

# The fields the admit verdict and the trained text actually depend on, plus the two
# provenance fields that make a row auditable. A row missing any of these cannot be
# verified, and an unverifiable sample is not admitted.
REQUIRED_ROW_FIELDS = (
    "schema",
    "run_id",
    "created_at_utc",
    "session_receipt",
    "session_receipt_sha256",
    "pack_receipt",
    "pack_writer_source_sha256",
    "prompt_index",
    "discipline",
    "base_prompt",
    "delivered_prompt",
    "assistant_reply",
    "prompt_sha256",
    "status",
    "admit",
    "admit_reason",
    "training_sample_eligible",
    "discipline_eligibility_ok",
    "contract_echo",
    "selected_provider",
    "local_only_training",
)
# Audit metadata: recorded when absent, but its absence does not disqualify a row.
# Killing a whole training cycle over a missing `material_topic` would be theatre.
OPTIONAL_ROW_FIELDS = (
    "curriculum_template",
    "material_topic",
    "training_level",
    "scheduled_hour",
    "activation_depth",
    "wrapper_receipt_path",
    "slm_admit_prediction",
)
MIN_REPLY_CHARS = 80

# The CT-side tools this cycle executes. verify_engel_slm.py is pushed with the
# trainer on purpose: the gate imports the trainer's own thresholds and leakage
# detector, so a new trainer paired with a stale gate would be graded by rules that
# no longer exist.
CT_TOOL_FILES = (
    "engel_build_training_dataset.py",
    "engel_construction_corpus.py",
    "engel_ct246_train_lora.py",
    "engel_slm_dataset_builder.py",
    "engel_slm_roster.py",
    "engel_slm_trainer.py",
    "engel_slm_runtime.py",
    "engel_training_capture_filter.py",
    "engel_training_cycle_runtime_contract.py",
    "engel_training_cycle_runtime_contract.contract",
    "engel_prompt_training_quarantine.py",
    "verify_engel_slm.py",
    "run_engel_ct246_local_lora_proof.py",
    "run_engel_ct246_lora_canary_gate.py",
    "run_engel_ct246_gguf_conversion.py",
    "run_engel_ct246_gguf_canary.py",
)
DEFAULT_SLM_TASKS = slm_roster.default_training_csv()
TRAINING_TARGETS = ("slm", "llm")
LLM_APPROVAL_PHRASE = "APPROVE_ENGEL_LOCAL_LLM_LORA_TRAINING_RUN_V1"

SSH_BASE_OPTIONS = ("-o", "BatchMode=yes", "-o", "ConnectTimeout=8")
# A dataset rebuild runs a bounded backlog-driver pre-step and can sit quiet for many
# minutes. Without keepalives an idle NAT/firewall drops the session and the step dies
# with an empty error that looks like a build failure.
SSH_LONG_RUN_OPTIONS = ("-o", "ServerAliveInterval=30", "-o", "ServerAliveCountMax=40")

TIMEOUT_PROBE = 45
TIMEOUT_SCP = 600
TIMEOUT_SHORT = 120
TIMEOUT_DATASET_BUILD = runtime_budget.step_timeout_seconds("llm", "dataset")
TIMEOUT_SLM_DATASETS = runtime_budget.step_timeout_seconds("slm", "dataset")
TIMEOUT_SLM_TRAIN = runtime_budget.step_timeout_seconds("slm", "train")
TIMEOUT_SLM_VERIFY = runtime_budget.step_timeout_seconds("slm", "verify")
TIMEOUT_LLM_PREFLIGHT = runtime_budget.step_timeout_seconds("llm", "preflight")
# budget 10800 + eval 7200 + dataset/build headroom; must exceed the sum or ssh kills a
# healthy training run from the outside.
TIMEOUT_LLM_TRAIN = runtime_budget.step_timeout_seconds(
    "llm", "train_and_evaluate"
)
_ACTIVE_CYCLE_DEADLINE_MONOTONIC: float | None = None


def _bounded_cycle_timeout(requested_seconds: float) -> float:
    """Clamp every child process to the orchestrator-owned whole-cycle deadline."""

    requested = max(0.0, float(requested_seconds))
    if _ACTIVE_CYCLE_DEADLINE_MONOTONIC is None:
        return requested
    remaining = _ACTIVE_CYCLE_DEADLINE_MONOTONIC - time.monotonic()
    return max(0.0, min(requested, remaining))


def normalize_training_targets(value: Any) -> tuple[str, ...]:
    """Normalize the only model families this orchestrator can truly train."""
    if isinstance(value, (list, tuple, set)):
        raw = [str(item).strip().casefold() for item in value]
    else:
        raw = [item.strip().casefold() for item in str(value or "").split(",")]
    selected = {item for item in raw if item}
    unsupported = sorted(selected - set(TRAINING_TARGETS))
    if unsupported:
        raise ValueError("unsupported training target(s): " + ", ".join(unsupported))
    if not selected:
        raise ValueError("at least one training target is required: slm or llm")
    return tuple(item for item in TRAINING_TARGETS if item in selected)


def normalize_slm_task_csv(value: Any) -> str:
    """Argparse adapter around the canonical roster's strict task validation."""
    try:
        return ",".join(slm_roster.normalize_tasks(str(value or "")))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def llm_training_approval_valid(targets: Any, approval: Any) -> bool:
    """Return true unless a selected LLM mutation lacks its exact approval."""
    selected = normalize_training_targets(targets)
    return "llm" not in selected or str(approval or "") == LLM_APPROVAL_PHRASE


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def unique_cycle_run_id() -> str:
    """Return a filesystem-safe per-process run id with sub-second uniqueness.

    SLM candidates live under a run-id directory.  The historical second-resolution
    stamp was sufficient for report display, but two starts in one second could reuse
    the same remote candidate directory and make a new receipt authenticate old bytes.
    """
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"realtrain_{now}_p{os.getpid()}"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_sha256(value: Any) -> str:
    """Hash one JSON value with a stable, whitespace-free representation."""

    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def evidence_int(value: Any, default: int = -1) -> int:
    """Parse receipt integers without letting malformed evidence crash an audit."""

    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def immutable_regular_file(path: Path) -> bool:
    """Return true only for a non-symlink regular file with no write bits."""

    try:
        info = os.lstat(path)
    except OSError:
        return False
    return (
        stat.S_ISREG(info.st_mode)
        and not path.is_symlink()
        and not bool(info.st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
    )


def read_immutable_json_evidence(
    path: Path,
    label: str,
) -> tuple[dict[str, Any] | None, dict[str, Any], list[str]]:
    """Read immutable JSON once and return the exact bytes' transfer binding."""

    binding: dict[str, Any] = {
        "path": str(path),
        "name": path.name,
        "sha256": "",
        "bytes": 0,
        "mode": "",
    }
    if not immutable_regular_file(path):
        return None, binding, [f"{label} is not an immutable regular read-only file"]
    try:
        resolved = path.resolve(strict=True)
        raw = resolved.read_bytes()
        payload = json.loads(raw.decode("utf-8-sig"))
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        return None, binding, [f"{label} is unreadable or invalid: {exc}"]
    binding = {
        "path": str(resolved),
        "name": resolved.name,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "mode": "0444",
    }
    if not isinstance(payload, dict):
        return None, binding, [f"{label} is not a JSON object"]
    return payload, binding, []


def require_repo_path(path: Path) -> None:
    """Refuse to write anywhere but this repo on D:.

    The no-C rule is a standing house rule, and an orchestrator that mirrors remote
    artifacts is exactly the kind of tool that would quietly drop them somewhere else.
    """
    resolved = Path(path).expanduser().resolve()
    if resolved != ROOT and ROOT not in resolved.parents:
        raise RuntimeError(f"refusing to write outside the repo: {resolved}")


class CycleLockBusy(RuntimeError):
    """Another non-dry training cycle owns the OS lock."""


@contextmanager
def exclusive_cycle_lock(path: Path | None = None):
    """Hold one cross-platform, nonblocking process lock for the whole real cycle.

    The file is only a stable byte on which the OS places a lock; its existence never
    means "busy".  Windows byte-range locks and POSIX ``flock`` are released by the OS
    when the process or descriptor exits, so a crash cannot leave a stale logical lock.
    """
    lock_path = Path(path) if path is not None else CYCLE_LOCK_PATH
    require_repo_path(lock_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+b")
    if handle.seek(0, os.SEEK_END) == 0:
        handle.write(b"\0")
        handle.flush()
    handle.seek(0)
    locked = False
    try:
        if os.name == "nt":
            import msvcrt

            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise CycleLockBusy(f"another real training cycle owns {lock_path}") from exc
        else:
            import fcntl

            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise CycleLockBusy(f"another real training cycle owns {lock_path}") from exc
        locked = True
        yield lock_path
    finally:
        if locked:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            finally:
                handle.close()
        else:
            handle.close()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    require_repo_path(path.parent)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def event(kind: str, **fields: Any) -> None:
    """Print one structured JSON line so a UI or log tail can follow a long cycle."""
    payload = {"event": kind, "at_utc": iso_now()}
    payload.update(fields)
    print(json.dumps(payload, sort_keys=True), flush=True)


def tail(text: str, limit: int = 1200) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return "..." + text[-limit:]


def as_int(value: Any) -> int:
    """Coerce a remote-reported count to int; a missing count is honestly 0, not None.

    CONTRACT 2 declares these as ints and the UI renders them directly, so a None from a
    build that never printed its summary must not land in the receipt as a row count.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def last_json_object(text: str) -> dict[str, Any]:
    """Parse the last JSON object printed on stdout, ignoring log chatter above it."""
    stripped = (text or "").strip()
    for line in reversed(stripped.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            parsed = json.loads(line)
        except ValueError:
            continue
        if isinstance(parsed, dict):
            return parsed
    # Some CT tools print their final receipt with indentation.  Walk candidate object
    # starts from the end and accept only one that consumes the remaining output, so a
    # nested object or a brace in prior log chatter cannot masquerade as the receipt.
    decoder = json.JSONDecoder()
    for start in reversed([index for index, char in enumerate(stripped) if char == "{"]):
        try:
            parsed, consumed = decoder.raw_decode(stripped[start:])
        except ValueError:
            continue
        if isinstance(parsed, dict) and not stripped[start + consumed :].strip():
            return parsed
    return {}


def run_local(command: Sequence[str], timeout_s: float) -> dict[str, Any]:
    started = time.perf_counter()
    argv = [str(item) for item in command]
    requested_timeout = float(timeout_s)
    timeout_s = _bounded_cycle_timeout(requested_timeout)
    if timeout_s <= 0:
        return {
            "ok": False,
            "returncode": None,
            "stdout": "",
            "stderr": "whole-cycle runtime deadline was exhausted before process start",
            "seconds": 0.0,
        }
    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "returncode": None,
            "stdout": "",
            "stderr": (
                f"timed out after {timeout_s:.0f}s"
                + (
                    " at the whole-cycle deadline"
                    if timeout_s + 0.001 < requested_timeout
                    else ""
                )
            ),
            "seconds": round(time.perf_counter() - started, 2),
        }
    except OSError as exc:
        return {
            "ok": False,
            "returncode": None,
            "stdout": "",
            "stderr": f"{type(exc).__name__}: {exc}",
            "seconds": round(time.perf_counter() - started, 2),
        }
    return {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout": completed.stdout or "",
        "stderr": completed.stderr or "",
        "seconds": round(time.perf_counter() - started, 2),
    }


def resolve_ssh() -> dict[str, Any]:
    """Resolve the CT246 SSH identity exactly the way the training runner already does.

    Copied deliberately rather than re-invented: the runner's resolution is what the
    operator's environment is already configured for, and a second dialect of the same
    lookup is how one of them silently stops matching.
    """
    target = os.environ.get("ENGEL_CT_SSH_TARGET", "").strip()
    if not target:
        host = os.environ.get("ENGEL_MAIN_SERVER_HOST", "192.0.2.50").strip()
        user = os.environ.get("ENGEL_MAIN_SERVER_USER", "root").strip() or "root"
        target = f"{user}@{host}" if host else ""
    key = os.environ.get("ENGEL_CT_SSH_KEY", "").strip()
    if not key:
        default_key = Path.home() / ".ssh" / "engel_ai_main_ct246_ed25519"
        if default_key.is_file():
            key = str(default_key)
    port = os.environ.get(
        "ENGEL_CT_SSH_PORT",
        os.environ.get("ENGEL_MAIN_SERVER_SSH_PORT", "24622"),
    ).strip()
    return {"target": target, "key": key, "port": port}


def ssh_argv(cfg: dict[str, Any], *, long_run: bool = False) -> list[str]:
    argv = ["ssh", *SSH_BASE_OPTIONS]
    if long_run:
        argv.extend(SSH_LONG_RUN_OPTIONS)
    if cfg.get("key"):
        argv.extend(["-i", str(cfg["key"])])
    if cfg.get("port"):
        argv.extend(["-p", str(cfg["port"])])  # ssh takes lowercase -p
    return argv


def scp_argv(cfg: dict[str, Any]) -> list[str]:
    argv = ["scp", *SSH_BASE_OPTIONS]
    if cfg.get("key"):
        argv.extend(["-i", str(cfg["key"])])
    if cfg.get("port"):
        argv.extend(["-P", str(cfg["port"])])  # scp takes uppercase -P
    return argv


def ssh_run(cfg: dict[str, Any], remote_command: str, timeout_s: float, *, long_run: bool = False) -> dict[str, Any]:
    result = run_local(
        [*ssh_argv(cfg, long_run=long_run), str(cfg["target"]), remote_command],
        timeout_s,
    )
    result["remote_command"] = remote_command
    return result


def remote_python(ct_python: str, script: str, *args: str) -> str:
    return " ".join(shlex.quote(part) for part in (ct_python, script, *args))


def read_remote_json(
    cfg: dict[str, Any], path: str, timeout_s: float = TIMEOUT_SHORT
) -> dict[str, Any]:
    """Read one known CT receipt without trusting command chatter as JSON."""
    result = ssh_run(cfg, f"cat {shlex.quote(path)}", timeout_s)
    if not result.get("ok"):
        return {}
    try:
        parsed = json.loads(result.get("stdout") or "{}")
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def planned_python(script: str, *args: str) -> str:
    """Render a planned remote command with the interpreter still unresolved.

    A dry run has not probed CT, so it must not print an interpreter path as if it had
    been confirmed - the placeholder makes the difference obvious at a glance.
    """
    return "<ctpython> " + " ".join(shlex.quote(part) for part in (script, *args))


def remote_sha256(cfg: dict[str, Any], paths: Sequence[str]) -> dict[str, Any]:
    """Hash a known list of remote files. No globs: the caller must name what it expects.

    A glob here would silently 'succeed' against an empty directory, which is precisely
    the failure this check exists to catch.
    """
    if not paths:
        return {"ok": True, "hashes": {}, "stderr": ""}
    command = "sha256sum " + " ".join(shlex.quote(p) for p in paths)
    result = ssh_run(cfg, command, TIMEOUT_SHORT)
    hashes: dict[str, str] = {}
    for line in (result.get("stdout") or "").splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) == 2:
            hashes[parts[1].strip().lstrip("*")] = parts[0].strip().casefold()
    result["hashes"] = hashes
    return result


def ct_slm_candidate_dir(run_id: str) -> str:
    """Canonical, per-cycle CT directory for a non-serving SLM candidate."""
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", str(run_id or ""))
    if not safe or safe != run_id:
        raise ValueError(f"unsafe SLM cycle run id: {run_id!r}")
    return f"{CT_CYCLE_RUN_DIR}/{safe}/slm_candidate"


def ct_slm_dataset_dir(run_id: str) -> str:
    """Canonical, per-cycle CT input directory for the SLM trainer."""
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", str(run_id or ""))
    if not safe or safe != run_id:
        raise ValueError(f"unsafe SLM cycle run id: {run_id!r}")
    return f"{CT_CYCLE_RUN_DIR}/{safe}/slm_datasets"


def ct_construction_corpus_dir(run_id: str) -> str:
    """Return the immutable corpus root owned by one training cycle.

    Corpus evidence must never be read from a shared mutable directory.  A failed
    transfer may leave a partial directory behind, but no later cycle can select it
    because every dataset command receives its own run-scoped root explicitly.
    """
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", str(run_id or ""))
    if not safe or safe != run_id:
        raise ValueError(f"unsafe training cycle run id: {run_id!r}")
    return f"{CT_CYCLE_RUN_DIR}/{safe}/construction_corpus"


def _parse_utc(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def validate_slm_training_report(
    report: dict[str, Any],
    *,
    run_id: str,
    candidate_dir: str,
    dataset_dir: str,
    requested_tasks: Sequence[str],
    cycle_started_at_utc: str,
) -> tuple[list[str], list[str], dict[str, str]]:
    """Bind an SLM report to this run and enumerate its complete selected roster.

    The report is untrusted remote data.  Only canonical artifact names inside the
    run-specific candidate directory are accepted, and every requested task must have
    one selected, gate-passing, hash-bound artifact.  Partial rosters are evidence, not
    releases, so this function deliberately returns problems instead of a subset to ship.
    """
    problems: list[str] = []
    requested = list(slm_roster.normalize_tasks(requested_tasks))
    expected_dir = str(PurePosixPath(candidate_dir))
    if expected_dir == str(PurePosixPath(CT_SLM_DIR)):
        problems.append("candidate directory resolves to the serving directory")
    if report.get("schema") != slm_roster.TRAINING_REPORT_SCHEMA:
        problems.append(
            f"report schema is {report.get('schema')!r}, expected {slm_roster.TRAINING_REPORT_SCHEMA}"
        )
    if str(report.get("run_id") or "") != run_id:
        problems.append("report run_id does not match this cycle")
    if report.get("staged") is not True:
        problems.append("report does not declare staged=true")
    reported_dir = str(PurePosixPath(str(report.get("output_dir") or ".")))
    if reported_dir != expected_dir:
        problems.append(
            f"report output_dir {reported_dir!r} is not the candidate directory {expected_dir!r}"
        )
    reported_incumbent = str(PurePosixPath(str(report.get("incumbent_dir") or ".")))
    if reported_incumbent != str(PurePosixPath(CT_SLM_DIR)):
        problems.append("report incumbent_dir is not the read-only serving roster")
    expected_data_dir = str(PurePosixPath(dataset_dir))
    reported_data_dir = str(PurePosixPath(str(report.get("data_dir") or ".")))
    if reported_data_dir != expected_data_dir:
        problems.append(
            f"report data_dir {reported_data_dir!r} is not this cycle's dataset directory "
            f"{expected_data_dir!r}"
        )
    generated = _parse_utc(report.get("generated_at_utc"))
    started = _parse_utc(cycle_started_at_utc)
    now = datetime.now(timezone.utc)
    if generated is None or started is None:
        problems.append("report freshness timestamps are missing or invalid")
    elif generated < started - timedelta(minutes=5) or generated > now + timedelta(minutes=5):
        problems.append("report generated_at_utc is outside this cycle's time window")

    report_requested = report.get("requested_tasks")
    if not isinstance(report_requested, list) or report_requested != requested:
        problems.append(
            f"report requested_tasks {report_requested!r} do not exactly match {requested!r}"
        )
    results = report.get("results")
    if not isinstance(results, list):
        results = []
        problems.append("report results is not a list")
    by_task: dict[str, dict[str, Any]] = {}
    for entry in results:
        if not isinstance(entry, dict):
            problems.append("report contains a non-object result")
            continue
        task = str(entry.get("task") or "")
        if task in by_task:
            problems.append(f"report contains duplicate result for {task!r}")
            continue
        by_task[task] = entry
    if list(by_task) != requested:
        problems.append(
            f"report result order/tasks {list(by_task)!r} do not exactly match {requested!r}"
        )

    selected = report.get("selected_ok")
    trained = report.get("trained_ok")
    if selected != requested or trained != requested:
        problems.append(
            "report does not select every requested task "
            f"(selected_ok={selected!r}, trained_ok={trained!r})"
        )

    artifacts: dict[str, str] = {}
    for task in requested:
        entry = by_task.get(task)
        if not entry:
            continue
        if entry.get("selected_ok") is not True or entry.get("ok") is not True:
            problems.append(f"{task}: selected artifact is not gate-eligible")
        expected_name = f"engel_slm_{task}.joblib"
        artifact = PurePosixPath(str(entry.get("artifact") or ""))
        if str(artifact.parent) != expected_dir or artifact.name != expected_name:
            problems.append(f"{task}: artifact path is not canonical inside the candidate directory")
        digest = str(entry.get("artifact_sha256") or "").strip().casefold()
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            problems.append(f"{task}: artifact_sha256 is missing or invalid")
        else:
            artifacts[str(artifact)] = digest
    return problems, requested, artifacts


def verify_local_slm_release(
    directory: Path, expected_hashes: dict[str, str]
) -> list[str]:
    """Verify an exact local release without deserializing pickle-capable artifacts."""
    problems: list[str] = []
    if not directory.is_dir():
        return [f"release directory is missing: {directory}"]
    expected_names = set(expected_hashes)
    try:
        present = {path.name for path in directory.iterdir() if path.is_file()}
        non_files = [path.name for path in directory.iterdir() if not path.is_file()]
    except OSError as exc:
        return [f"release directory is unreadable: {type(exc).__name__}: {exc}"]
    if non_files:
        problems.append("release contains non-file entries: " + ", ".join(sorted(non_files)))
    missing = sorted(expected_names - present)
    extra = sorted(present - expected_names)
    if missing:
        problems.append("release is missing: " + ", ".join(missing))
    if extra:
        problems.append("release has unexpected files: " + ", ".join(extra))
    for name, expected in expected_hashes.items():
        path = directory / name
        if not path.is_file():
            continue
        try:
            got = sha256_file(path)
        except OSError as exc:
            problems.append(f"{name}: hash failed: {type(exc).__name__}: {exc}")
            continue
        if got.casefold() != expected.casefold():
            problems.append(f"{name}: sha256 mismatch")
    return problems


def atomic_promote_slm_release(
    stage_dir: Path,
    live_dir: Path,
    *,
    run_id: str,
    expected_hashes: dict[str, str],
) -> dict[str, Any]:
    """Atomically swap a fully verified release into the local mirror.

    Both directories are siblings on the same volume, so directory renames are atomic.
    The previous release is kept under a unique run-bound backup.  If the post-swap
    integrity check fails, the old release is restored before this function returns.
    """
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", str(run_id or ""))
    if not safe or safe != run_id:
        return {"ok": False, "problems": ["unsafe run id"], "rolled_back": False}
    stage_dir = stage_dir.resolve()
    live_dir = live_dir.resolve()
    require_repo_path(stage_dir)
    require_repo_path(live_dir)
    if stage_dir.parent != live_dir.parent:
        return {
            "ok": False,
            "problems": ["stage and live directories are not same-volume siblings"],
            "rolled_back": False,
        }
    problems = verify_local_slm_release(stage_dir, expected_hashes)
    if problems:
        return {"ok": False, "problems": problems, "rolled_back": False}

    backup = live_dir.with_name(f"{live_dir.name}_previous_{safe}")
    failed = live_dir.with_name(f"{live_dir.name}_failed_{safe}")
    for reserved in (backup, failed):
        if reserved.exists():
            return {
                "ok": False,
                "problems": [f"unique promotion path already exists: {reserved}"],
                "rolled_back": False,
            }

    had_live = live_dir.exists()
    moved_live = False
    try:
        if had_live:
            os.replace(live_dir, backup)
            moved_live = True
        os.replace(stage_dir, live_dir)
    except OSError as exc:
        rollback_problem = ""
        if moved_live and backup.exists() and not live_dir.exists():
            try:
                os.replace(backup, live_dir)
            except OSError as rollback_exc:
                rollback_problem = (
                    f"; rollback failed: {type(rollback_exc).__name__}: {rollback_exc}"
                )
        return {
            "ok": False,
            "problems": [f"atomic directory swap failed: {type(exc).__name__}: {exc}{rollback_problem}"],
            "rolled_back": moved_live and live_dir.exists() and not backup.exists(),
            "backup": str(backup) if backup.exists() else None,
        }

    post_problems = verify_local_slm_release(live_dir, expected_hashes)
    if post_problems:
        rolled_back = False
        try:
            os.replace(live_dir, failed)
            if moved_live:
                os.replace(backup, live_dir)
            rolled_back = (not moved_live) or live_dir.is_dir()
        except OSError as exc:
            post_problems.append(f"post-swap rollback failed: {type(exc).__name__}: {exc}")
        return {
            "ok": False,
            "problems": post_problems,
            "rolled_back": rolled_back,
            "failed_release": str(failed) if failed.exists() else None,
            "backup": str(backup) if backup.exists() else None,
        }
    return {
        "ok": True,
        "problems": [],
        "rolled_back": False,
        "backup": str(backup) if moved_live else None,
        "live": str(live_dir),
    }


# --------------------------------------------------------------------------------------
# CONTRACT 1 validation
# --------------------------------------------------------------------------------------


def load_current_curriculum_contract(
    index_path: Path = CURRICULA_INDEX_PATH,
    manifest_path: Path = TRAINING_ASSET_MANIFEST_PATH,
) -> dict[str, Any]:
    """Verify the exact five current curriculum templates and their manifest binding."""

    result: dict[str, Any] = {
        "ok": False,
        "errors": [],
        "index_path": str(index_path),
        "manifest_path": str(manifest_path),
        "index_sha256": "",
        "manifest_sha256": "",
        "bindings": [],
        "bindings_by_id": {},
    }

    def load_object(path: Path, label: str) -> dict[str, Any] | None:
        try:
            if path.is_symlink() or not path.is_file():
                raise ValueError("not a regular file")
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            result["errors"].append(f"{label} is unreadable or invalid: {exc}")
            return None
        if not isinstance(payload, dict):
            result["errors"].append(f"{label} is not a JSON object")
            return None
        return payload

    index = load_object(index_path, "curricula index")
    manifest = load_object(manifest_path, "training assets manifest")
    if index is None or manifest is None:
        return result
    result["index_sha256"] = sha256_file(index_path)
    result["manifest_sha256"] = sha256_file(manifest_path)
    if index.get("schema") != "engel_training_curricula_index_v1":
        result["errors"].append("curricula index schema is invalid")
    if manifest.get("schema") != "engel_main_training_assets_manifest_v1":
        result["errors"].append("training assets manifest schema is invalid")
    if manifest.get("asset_integrity_ok") is not True:
        result["errors"].append("five-curriculum asset integrity is not ready")
    curricula = index.get("curricula")
    manifest_bindings = manifest.get("curriculum_bindings")
    if not isinstance(curricula, list) or not isinstance(manifest_bindings, list):
        result["errors"].append("curriculum bindings are absent from index or manifest")
        return result
    expected_identity = list(CANONICAL_CURRICULA)
    actual_identity = [
        (
            str(item.get("id") or ""),
            str(item.get("title") or ""),
            str(item.get("discipline") or ""),
        )
        for item in curricula
        if isinstance(item, dict)
    ]
    if (
        len(curricula) != 5
        or int(index.get("curriculum_count") or 0) != 5
        or int(index.get("total_prompts") or 0) != 400
        or actual_identity != expected_identity
    ):
        result["errors"].append("curricula index is not the exact ordered five/400 contract")

    def normalized(item: Any) -> dict[str, Any]:
        if not isinstance(item, dict):
            return {}
        return {field: item.get(field) for field in CURRICULUM_BINDING_FIELDS}

    index_bindings = [normalized(item) for item in curricula]
    manifest_normalized = [normalized(item) for item in manifest_bindings]
    if index_bindings != manifest_normalized:
        result["errors"].append("manifest curriculum bindings differ from the index")
        return result
    template_root = index_path.parent.resolve()
    for position, binding in enumerate(index_bindings, start=1):
        problems: list[str] = []
        ordered_prompt_hashes: list[str] = []
        expected_id, expected_title, expected_discipline = expected_identity[position - 1]
        if (
            binding.get("id") != expected_id
            or binding.get("title") != expected_title
            or binding.get("discipline") != expected_discipline
        ):
            problems.append("identity differs from canonical order")
        if (
            not str(binding.get("version") or "").strip()
            or int(binding.get("prompt_count") or 0) != 80
            or int(binding.get("maximum_hours") or 0) != 8
        ):
            problems.append("version or 8-hour/80-prompt shape is invalid")
        expected_sha = str(binding.get("template_sha256") or "").strip().casefold()
        if not re.fullmatch(r"[a-f0-9]{64}", expected_sha):
            problems.append("template SHA-256 binding is invalid")
        try:
            template_path = Path(str(binding.get("template_path") or "")).resolve(strict=True)
            template_path.relative_to(template_root)
            if template_path.is_symlink() or not template_path.is_file():
                raise ValueError("not a regular template file")
            # Hash and parse one captured buffer. A replace between separate hash/read
            # calls must not let the contract authenticate bytes it did not inspect.
            template_bytes = template_path.read_bytes()
            actual_sha = hashlib.sha256(template_bytes).hexdigest()
            if actual_sha != expected_sha:
                problems.append("template bytes do not match the bound SHA-256")
            payload = json.loads(template_bytes.decode("utf-8-sig"))
            cycles = payload.get("cycle_prompt_sets") if isinstance(payload, dict) else None
            if (
                not isinstance(payload, dict)
                or str(payload.get("material_version") or "") != str(binding.get("version") or "")
                or int(payload.get("maximum_scheduled_prompt_count") or 0) != 80
                or not isinstance(cycles, list)
                or len(cycles) != 8
                or any(
                    not isinstance(cycle, dict)
                    or not isinstance(cycle.get("prompts"), list)
                    or len(cycle["prompts"]) != 10
                    for cycle in cycles
                )
            ):
                problems.append("template content does not match its binding")
            else:
                ordered_prompts = [
                    prompt
                    for cycle in cycles
                    for prompt in cycle["prompts"]
                ]
                try:
                    ordered_prompt_hashes = [
                        canonical_base_prompt_sha256(prompt)
                        for prompt in ordered_prompts
                    ]
                except (TypeError, ValueError) as exc:
                    problems.append(f"template has an invalid base prompt: {exc}")
                if (
                    len(ordered_prompt_hashes) != 80
                    or len(set(ordered_prompt_hashes)) != 80
                ):
                    problems.append(
                        "template prompts are not 80 distinct canonical identities"
                    )
        except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
            template_path = Path(str(binding.get("template_path") or ""))
            problems.append(f"template path/content is invalid: {exc}")
        if problems:
            result["errors"].extend(f"{expected_id}: {problem}" for problem in problems)
            continue
        exact = dict(binding)
        exact["template_path"] = str(template_path)
        exact["template_sha256"] = expected_sha
        exact["base_prompt_hash_canonicalization"] = BASE_PROMPT_CANONICALIZATION
        exact["base_prompt_sha256_by_index"] = ordered_prompt_hashes
        result["bindings"].append(exact)
        result["bindings_by_id"][expected_id] = exact
    result["ok"] = not result["errors"] and len(result["bindings"]) == 5
    return result


def contract_admit(row: dict[str, Any]) -> tuple[bool, str]:
    """Use the dataset builder's exact current policy as the single admission authority."""

    assessment = training_dataset.assess_prompt_training_pack_row(
        row,
        corpus_root=ROOT / "memory" / "training" / "construction_env",
    )
    return (
        assessment.get("disposition") == "admit",
        str(assessment.get("reason") or "current dataset policy returned no reason"),
    )


def row_uses_current_admission_policy(row: dict[str, Any]) -> bool:
    """Distinguish current emitter failures from pre-policy audit claims.

    Old v1 rows legitimately lack the action/provenance fields added with the
    downstream re-derivation gate.  They are still regraded and unsafe rows are
    excluded, but a stale historical admit bit must not block every future cycle.
    A row emitted with the current evidence surface remains a hard disagreement.
    """

    common = {
        "action_lane_used",
        "response_kind",
        "base_prompt_sha256",
        "base_prompt_hash_canonicalization",
    }
    if not common.issubset(row):
        return False
    if str(row.get("discipline") or "").strip().casefold() != "aec":
        return True
    return {
        "aec_claim_support_verified",
        "aec_corpus_bundle_sha256",
        "aec_document_scope",
        "aec_support",
    }.issubset(row)


def validate_pack_writer_evidence(
    path: Path,
    rows: Sequence[dict[str, Any]],
    selected_targets: Sequence[str],
    curriculum_binding: dict[str, Any],
    pack_sha256: str,
) -> dict[str, Any]:
    """Authenticate the immutable session -> pack -> reviewed-writer receipt chain."""

    result: dict[str, Any] = {
        "ok": False,
        "problems": [],
        "run_id": "",
        "pack_receipt_path": "",
        "pack_receipt_sha256": "",
        "pack_receipt_bytes": 0,
        "session_evidence_path": "",
        "session_evidence_sha256": "",
        "session_evidence_bytes": 0,
        "writer_source_path": "",
        "writer_source_sha256": "",
        "writer_source_bytes": 0,
        "schedule_identity": {},
        "schedule_identity_sha256": "",
        "training_targets": [],
        "training_level": "",
        "template_cycle": 0,
        "exact_template_cycle": False,
    }
    problems: list[str] = result["problems"]
    if not rows:
        problems.append("pack has no valid rows to bind to writer evidence")
        return result
    run_ids = {str(row.get("run_id") or "").strip() for row in rows}
    if len(run_ids) != 1 or "" in run_ids:
        problems.append("pack rows do not have one non-empty run id")
        return result
    run_id = next(iter(run_ids))
    result["run_id"] = run_id
    expected_pack_name = f"ENGEL_PROMPT_TRAINING_PACK_{run_id}.jsonl"
    if path.name != expected_pack_name:
        problems.append("pack filename does not bind its exact run id")

    receipt_path = path.with_suffix(PACK_RECEIPT_SUFFIX)
    receipt, receipt_file, receipt_problems = read_immutable_json_evidence(
        receipt_path,
        "stamped pack receipt",
    )
    problems.extend(receipt_problems)
    result["pack_receipt_path"] = receipt_file["path"]
    result["pack_receipt_sha256"] = receipt_file["sha256"]
    result["pack_receipt_bytes"] = receipt_file["bytes"]
    if receipt is None:
        return result

    expected_receipt_path = str(receipt_path.resolve())
    if (
        receipt.get("schema") != PACK_STAMPED_RECEIPT_SCHEMA
        or receipt.get("run_id") != run_id
        or receipt.get("receipt_path") != expected_receipt_path
    ):
        problems.append("stamped pack receipt schema/path/run binding differs")

    pack = receipt.get("pack") if isinstance(receipt.get("pack"), dict) else {}
    try:
        pack_bytes = path.stat().st_size
    except OSError:
        pack_bytes = -1
    if (
        pack.get("path") != str(path.resolve())
        or pack.get("name") != path.name
        or str(pack.get("sha256") or "").casefold() != pack_sha256.casefold()
        or evidence_int(pack.get("bytes")) != pack_bytes
        or evidence_int(pack.get("rows")) != len(rows)
        or pack.get("mode") != "0444"
    ):
        problems.append("stamped receipt does not bind the exact pack bytes/path/rows")

    expected_writer_binding = {
        "schema": CURRICULUM_BINDING_SCHEMA,
        "curriculum_id": curriculum_binding.get("id"),
        "curriculum_title": curriculum_binding.get("title"),
        "discipline": curriculum_binding.get("discipline"),
        "material_version": curriculum_binding.get("version"),
        "template_path": curriculum_binding.get("template_path"),
        "template_sha256": curriculum_binding.get("template_sha256"),
    }
    stamped_binding = receipt.get("curriculum_binding")
    # The runner also stamps novelty fields (status, hours left, start cycle).
    # Those describe the session window. They are not part of the curriculum
    # identity, and requiring the dicts to be equal rejected every current pack.
    if not isinstance(stamped_binding, dict) or any(
        stamped_binding.get(key) != value
        for key, value in expected_writer_binding.items()
    ):
        problems.append("stamped receipt curriculum binding is not current")

    writer = receipt.get("writer") if isinstance(receipt.get("writer"), dict) else {}
    try:
        writer_source = PROMPT_PACK_WRITER_SOURCE.resolve(strict=True)
        if writer_source.is_symlink() or not writer_source.is_file():
            raise ValueError("not a regular canonical source file")
        writer_bytes = writer_source.read_bytes()
        writer_sha256 = hashlib.sha256(writer_bytes).hexdigest()
    except (OSError, ValueError) as exc:
        problems.append(f"reviewed pack writer source is unavailable: {exc}")
        writer_source = PROMPT_PACK_WRITER_SOURCE
        writer_bytes = b""
        writer_sha256 = ""
    result["writer_source_path"] = str(writer_source)
    result["writer_source_sha256"] = writer_sha256
    result["writer_source_bytes"] = len(writer_bytes)
    if (
        writer.get("schema") != PACK_WRITER_IDENTITY_SCHEMA
        or writer.get("run_id") != run_id
        or writer.get("entrypoint") != "write_training_pack"
        or writer.get("captured_at") != "module_import"
        or writer.get("completion_reverified") is not True
        or writer.get("source_relative_path") != PROMPT_PACK_WRITER_RELATIVE_PATH
        or writer.get("source_path") != str(writer_source)
        or writer.get("source_sha256") != writer_sha256
        or evidence_int(writer.get("source_bytes")) != len(writer_bytes)
    ):
        problems.append("pack writer identity does not match the reviewed local emitter")

    schedule = (
        receipt.get("schedule") if isinstance(receipt.get("schedule"), dict) else {}
    )
    actual_indexes = [
        evidence_int(row.get("prompt_index"), 0) for row in rows
    ]
    try:
        receipt_targets = normalize_training_targets(
            schedule.get("training_targets")
        )
    except ValueError:
        receipt_targets = ()
        problems.append("stamped receipt training targets are missing or malformed")
    if any(target not in receipt_targets for target in selected_targets):
        problems.append("stamped receipt does not include every selected model lane")
    result["training_targets"] = list(receipt_targets)
    result["training_level"] = str(schedule.get("training_level") or "")
    result["template_cycle"] = evidence_int(schedule.get("template_cycle"), 0)
    result["exact_template_cycle"] = schedule.get("exact_template_cycle") is True
    hourly_cycles = schedule.get("hourly_cycles")
    session_hours = evidence_int(schedule.get("scheduled_hours"), 0)
    if (
        schedule.get("mode") != "scheduled"
        or session_hours < 1
        or session_hours > 8
        or evidence_int(schedule.get("trainings_per_hour"), 0) != 10
        or evidence_int(schedule.get("expected_plan_prompt_count"), 0)
        != session_hours * 10
        or evidence_int(schedule.get("row_count")) != len(rows)
        or evidence_int(schedule.get("prompt_index_count")) != len(actual_indexes)
        or schedule.get("prompt_index_min") != min(actual_indexes)
        or schedule.get("prompt_index_max") != max(actual_indexes)
        or schedule.get("global_prompt_indexes") != actual_indexes
        or not result["training_level"]
        or not isinstance(hourly_cycles, list)
        or len(hourly_cycles) != session_hours
    ):
        problems.append("stamped receipt schedule/index binding is incomplete or inconsistent")
    else:
        for scheduled_hour, hourly in enumerate(hourly_cycles, start=1):
            if (
                not isinstance(hourly, dict)
                or evidence_int(hourly.get("scheduled_hour"), 0) != scheduled_hour
                or evidence_int(hourly.get("selected_prompt_count"), 0) != 10
            ):
                problems.append("stamped receipt hourly schedule drifted from 8 x 10")
                break
    # Identity is the curriculum plan, not this session's length. A 2-hour
    # slice and a later 6-hour slice of the same 80 prompts must chain.
    schedule_identity = {
        "curriculum_id": curriculum_binding.get("id"),
        "curriculum_template_sha256": curriculum_binding.get("template_sha256"),
        "mode": "scheduled",
        "curriculum_hours": 8,
        "trainings_per_hour": 10,
        "training_targets": list(receipt_targets),
        "training_level": result["training_level"],
        "template_cycle": result["template_cycle"],
        "exact_template_cycle": result["exact_template_cycle"],
    }
    result["schedule_identity"] = schedule_identity
    result["schedule_identity_sha256"] = canonical_json_sha256(schedule_identity)

    expected_session_path = path.parent / f"{PACK_SESSION_PREFIX}{run_id}.json"
    bound_session = (
        receipt.get("session") if isinstance(receipt.get("session"), dict) else {}
    )
    session, session_file, session_problems = read_immutable_json_evidence(
        expected_session_path,
        "immutable session evidence",
    )
    problems.extend(session_problems)
    result["session_evidence_path"] = session_file["path"]
    result["session_evidence_sha256"] = session_file["sha256"]
    result["session_evidence_bytes"] = session_file["bytes"]
    if (
        bound_session.get("path") != str(expected_session_path.resolve())
        or bound_session.get("name") != expected_session_path.name
        or bound_session.get("sha256") != session_file["sha256"]
        or evidence_int(bound_session.get("bytes")) != session_file["bytes"]
        or bound_session.get("mode") != "0444"
        or bound_session.get("schema") != PACK_SESSION_EVIDENCE_SCHEMA
        or bound_session.get("run_id") != run_id
    ):
        problems.append("stamped receipt session evidence binding differs")
    if session is None:
        return result
    session_body = (
        session.get("session") if isinstance(session.get("session"), dict) else {}
    )
    if (
        session.get("schema") != PACK_SESSION_EVIDENCE_SCHEMA
        or session.get("run_id") != run_id
        or session.get("writer") != writer
        or session_body.get("schema") != "engel_ui_prompt_training_session_v1"
        or session_body.get("run_id") != run_id
        or session_body.get("mode") != schedule.get("mode")
        or session_body.get("curriculum_binding") != expected_writer_binding
        or session_body.get("template_path") != curriculum_binding.get("template_path")
        or evidence_int(session_body.get("scheduled_hours"), 0)
        != evidence_int(schedule.get("scheduled_hours"), 0)
        or evidence_int(session_body.get("trainings_per_hour"), 0)
        != evidence_int(schedule.get("trainings_per_hour"), 0)
        or evidence_int(session_body.get("start_index"), 0)
        != evidence_int(schedule.get("session_start_index"), 0)
        or session_body.get("training_targets") != schedule.get("training_targets")
        or session_body.get("training_level") != schedule.get("training_level")
        or evidence_int(session_body.get("template_cycle"), 0)
        != evidence_int(schedule.get("template_cycle"), 0)
        or bool(session_body.get("exact_template_cycle"))
        != bool(schedule.get("exact_template_cycle"))
        or session_body.get("hourly_cycles") != hourly_cycles
        or session_body.get("status") != "PASS"
        or bool(session_body.get("blockers"))
    ):
        problems.append("immutable session does not reproduce the stamped run/schedule")

    expected_session_resolved = str(expected_session_path.resolve())
    for row in rows:
        try:
            row_targets = normalize_training_targets(row.get("training_targets"))
        except ValueError:
            row_targets = ()
        if (
            row.get("session_receipt") != expected_session_resolved
            or row.get("session_receipt_sha256") != session_file["sha256"]
            or row.get("pack_receipt") != expected_receipt_path
            or row.get("pack_writer_source_sha256") != writer_sha256
            or row_targets != receipt_targets
            or row.get("training_level") != result["training_level"]
        ):
            problems.append("a pack row differs from its immutable evidence binding")
            break
    result["ok"] = not problems
    return result


def validate_pack(
    path: Path,
    targets: Any = TRAINING_TARGETS,
    curriculum_binding: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate one pack file against CONTRACT 1 and count what is genuinely trainable."""
    selected_targets = normalize_training_targets(targets)
    summary: dict[str, Any] = {
        "path": str(path),
        "name": path.name,
        "pack_sha256": "",
        "pack_read_only": False,
        "curriculum_id": "",
        "curriculum_binding": {},
        "segment_eligible": False,
        "segment_problems": [],
        "segment_run_id": "",
        "segment_start_index": 0,
        "segment_end_index": 0,
        "segment_prompt_indexes": [],
        "schedule_identity": {},
        "schedule_identity_sha256": "",
        "training_targets": [],
        "training_level": "",
        "pack_receipt_path": "",
        "pack_receipt_sha256": "",
        "pack_receipt_bytes": 0,
        "session_evidence_path": "",
        "session_evidence_sha256": "",
        "session_evidence_bytes": 0,
        "writer_source_path": "",
        "writer_source_sha256": "",
        "writer_source_bytes": 0,
        "coverage_eligible": False,
        "coverage_problems": [],
        "physical_rows": 0,
        "logical_rows": 0,
        "rows": 0,
        "admitted": 0,
        "rejected": 0,
        "invalid_rows": 0,
        "admit_disagreements": 0,
        "legacy_admit_disagreements": 0,
        "current_admit_disagreements": 0,
        "quarantined": 0,
        "quarantine_receipts": [],
        "quarantine_receipt_sha256": {},
        "quarantine_blockers": [],
        "selected_targets": list(selected_targets),
        "explicit_rows_by_target": {target: 0 for target in selected_targets},
        "admitted_by_target": {target: 0 for target in selected_targets},
        "target_exclusions": {
            "missing_or_malformed": 0,
            "not_selected": 0,
        },
        "missing_optional_fields": [],
        "by_discipline": {},
        "by_status": {},
        "errors": [],
    }
    try:
        info = os.lstat(path)
        summary["pack_read_only"] = (
            stat.S_ISREG(info.st_mode)
            and not path.is_symlink()
            and not bool(info.st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
        )
        summary["pack_sha256"] = sha256_file(path)
    except OSError as exc:
        summary["errors"].append(f"pack metadata unavailable: {type(exc).__name__}: {exc}")
        return summary
    try:
        loaded = prompt_quarantine.load_pack(path, QUARANTINE_DIR)
    except OSError as exc:
        summary["errors"].append(f"unreadable: {type(exc).__name__}: {exc}")
        return summary
    summary["quarantine_receipts"] = loaded.get("receipt_paths") or []
    summary["quarantine_receipt_sha256"] = dict(
        loaded.get("receipt_sha256") or {}
    )
    summary["quarantine_blockers"] = list(loaded.get("blockers") or [])
    if loaded.get("pack_sha256") != summary["pack_sha256"]:
        summary["errors"].append("pack bytes changed while they were being validated")
        summary["quarantine_blockers"].append(
            "pack bytes changed while they were being validated"
        )
    summary["errors"].extend(
        f"quarantine ledger: {item}" for item in summary["quarantine_blockers"]
    )
    summary["physical_rows"] = len(loaded.get("rows") or [])
    missing_optional: set[str] = set()
    valid_rows: list[dict[str, Any]] = []
    for parsed in loaded.get("rows") or []:
        lineno = int(parsed.get("line_number") or 0)
        line = str(parsed.get("raw_line") or "").strip()
        if not line:
            continue
        row = parsed.get("row")
        if not isinstance(row, dict):
            summary["invalid_rows"] += 1
            if len(summary["errors"]) < 8:
                summary["errors"].append(f"line {lineno}: row is not a JSON object")
            continue
        summary["rows"] += 1
        status = str(row.get("status") or "UNKNOWN")
        summary["by_status"][status] = summary["by_status"].get(status, 0) + 1
        discipline = str(row.get("discipline") or "unknown")
        summary["by_discipline"][discipline] = summary["by_discipline"].get(discipline, 0) + 1
        if str(row.get("schema") or "") != PACK_ROW_SCHEMA:
            summary["invalid_rows"] += 1
            if len(summary["errors"]) < 8:
                summary["errors"].append(
                    f"line {lineno}: schema {row.get('schema')!r} is not {PACK_ROW_SCHEMA}"
                )
            continue
        missing = [field for field in REQUIRED_ROW_FIELDS if field not in row]
        if missing:
            summary["invalid_rows"] += 1
            if len(summary["errors"]) < 8:
                summary["errors"].append(f"line {lineno}: missing required fields {missing}")
            continue
        if parsed.get("quarantined") is True:
            summary["quarantined"] += 1
            summary["rejected"] += 1
            continue
        try:
            row_targets = normalize_training_targets(row.get("training_targets"))
        except ValueError:
            summary["target_exclusions"]["missing_or_malformed"] += 1
            continue
        matched_targets = tuple(
            target for target in selected_targets if target in row_targets
        )
        if not matched_targets:
            summary["target_exclusions"]["not_selected"] += 1
            continue
        for target in matched_targets:
            summary["explicit_rows_by_target"][target] += 1
        missing_optional.update(field for field in OPTIONAL_ROW_FIELDS if field not in row)
        valid_rows.append(row)
        derived_ok, derived_reason = contract_admit(row)
        claimed = row.get("admit") is True
        if claimed and not derived_ok:
            summary["admit_disagreements"] += 1
            if row_uses_current_admission_policy(row):
                summary["current_admit_disagreements"] += 1
                disagreement_kind = "current"
            else:
                summary["legacy_admit_disagreements"] += 1
                disagreement_kind = "legacy"
            summary["rejected"] += 1
            if len(summary["errors"]) < 8:
                summary["errors"].append(
                    f"line {lineno}: {disagreement_kind} row claims admit=true but "
                    f"{derived_reason}"
                )
            continue
        if claimed:
            summary["admitted"] += 1
            for target in matched_targets:
                summary["admitted_by_target"][target] += 1
        else:
            summary["rejected"] += 1
    summary["logical_rows"] = len(valid_rows)
    summary["missing_optional_fields"] = sorted(missing_optional)
    claimed_curriculum_ids = {
        str(row.get("curriculum_id") or "").strip() for row in valid_rows
    }
    claimed_curriculum_ids.discard("")
    if len(claimed_curriculum_ids) == 1:
        summary["curriculum_id"] = next(iter(claimed_curriculum_ids))
    if curriculum_binding is not None:
        expected = {
            "curriculum_id": curriculum_binding.get("id"),
            "curriculum_title": curriculum_binding.get("title"),
            "curriculum_material_version": curriculum_binding.get("version"),
            "curriculum_template_path": curriculum_binding.get("template_path"),
            "curriculum_template_sha256": curriculum_binding.get("template_sha256"),
            "discipline": curriculum_binding.get("discipline"),
        }
        segment_problems: list[str] = []
        if not summary["pack_read_only"]:
            segment_problems.append("pack is not an immutable regular read-only file")
        if (
            not valid_rows
            or summary["physical_rows"] != summary["rows"]
            or summary["rows"] != len(valid_rows)
        ):
            segment_problems.append(
                "pack segment contains blank, invalid, quarantined, or target-excluded rows"
            )
        if (
            summary["invalid_rows"]
            or summary["current_admit_disagreements"]
            or summary["quarantined"]
            or summary["quarantine_blockers"]
        ):
            segment_problems.append(
                "pack has invalid, current-disagreement, or quarantined evidence"
            )
        run_ids = {str(row.get("run_id") or "").strip() for row in valid_rows}
        prompt_indexes = [
            evidence_int(row.get("prompt_index"), 0) for row in valid_rows
        ]
        if len(run_ids) != 1 or "" in run_ids:
            segment_problems.append("pack rows do not have one non-empty run id")
        # (2026-08-15) Void tolerance, pack level: a position reserved by THIS run
        # but never served (transport failure) leaves a hole no future run may
        # fill (novelty refuses replays). The hole is repaired for contiguity and
        # session-start purposes ONLY when the run's own reservation receipt
        # proves the position was consumed - hash-bound to this exact material.
        pack_run_id = next(iter(run_ids)) if len(run_ids) == 1 else ""
        own_voids = proven_void_positions(
            curriculum_binding.get("base_prompt_sha256_by_index") or [],
            set(prompt_indexes),
            run_id=pack_run_id,
        )
        coverage_indexes = sorted(set(prompt_indexes) | set(own_voids))
        if (
            not prompt_indexes
            or prompt_indexes != sorted(prompt_indexes)
            or len(set(prompt_indexes)) != len(prompt_indexes)
            or coverage_indexes
            != list(range(coverage_indexes[0], coverage_indexes[-1] + 1))
            or coverage_indexes[0] < 1
            or coverage_indexes[-1] > 80
        ):
            segment_problems.append(
                "pack prompt indexes are not one ordered contiguous segment within 1 through 80"
            )
        segment_start = coverage_indexes[0] if coverage_indexes else 0
        segment_end = coverage_indexes[-1] if coverage_indexes else 0
        session_starts = {
            evidence_int(row.get("session_start_index"), 0) for row in valid_rows
        }
        if session_starts != {segment_start}:
            segment_problems.append(
                "pack session start does not equal the segment's first prompt index"
            )
        summary["segment_void_positions"] = {
            str(pos): own_voids[pos] for pos in sorted(own_voids)
        }
        expected_prompt_hashes = curriculum_binding.get(
            "base_prompt_sha256_by_index"
        )
        if (
            not isinstance(expected_prompt_hashes, list)
            or len(expected_prompt_hashes) != 80
        ):
            segment_problems.append(
                "curriculum contract lacks 80 ordered base-prompt hashes"
            )
            expected_prompt_hashes = []
        for row in valid_rows:
            for field, expected_value in expected.items():
                if row.get(field) != expected_value:
                    segment_problems.append(f"row binding differs at {field}")
                    break
            session_hours = evidence_int(row.get("scheduled_hours"), 0)
            if (
                session_hours < 1
                or session_hours > 8
                or evidence_int(row.get("trainings_per_hour"), 0) != 10
                or evidence_int(row.get("session_start_index"), 0)
                != segment_start
            ):
                segment_problems.append(
                    "row schedule is not a 1-to-8 hour slice at 10 prompts per hour"
                )
                break
            prompt_index = evidence_int(row.get("prompt_index"), 0)
            expected_hour = ((prompt_index - 1) // 10) + 1
            base_prompt = str(row.get("base_prompt") or "").strip()
            delivered_prompt = str(row.get("delivered_prompt") or "")
            try:
                actual_base_hash = canonical_base_prompt_sha256(base_prompt)
            except (TypeError, ValueError):
                actual_base_hash = ""
            expected_base_hash = (
                str(expected_prompt_hashes[prompt_index - 1])
                if expected_prompt_hashes and 1 <= prompt_index <= 80
                else ""
            )
            if (
                row.get("base_prompt_hash_canonicalization")
                != BASE_PROMPT_CANONICALIZATION
                or row.get("base_prompt_sha256") != actual_base_hash
                or actual_base_hash != expected_base_hash
            ):
                segment_problems.append(
                    f"row {prompt_index} base prompt is not its bound curriculum prompt"
                )
            if (
                evidence_int(row.get("scheduled_hour"), 0) != expected_hour
                or f"Training task:\n{base_prompt}" not in delivered_prompt
                or row.get("prompt_sha256")
                != hashlib.sha256(delivered_prompt.encode("utf-8")).hexdigest()
            ):
                segment_problems.append(
                    f"row {prompt_index} delivered prompt/hour provenance is invalid"
                )
        evidence = validate_pack_writer_evidence(
            path,
            valid_rows,
            selected_targets,
            curriculum_binding,
            summary["pack_sha256"],
        )
        segment_problems.extend(evidence["problems"])
        summary.update(
            {
                "segment_run_id": evidence["run_id"],
                "segment_start_index": segment_start,
                "segment_end_index": segment_end,
                "segment_prompt_indexes": prompt_indexes,
                "schedule_identity": evidence["schedule_identity"],
                "schedule_identity_sha256": evidence[
                    "schedule_identity_sha256"
                ],
                "training_targets": evidence["training_targets"],
                "training_level": evidence["training_level"],
                "pack_receipt_path": evidence["pack_receipt_path"],
                "pack_receipt_sha256": evidence["pack_receipt_sha256"],
                "pack_receipt_bytes": evidence["pack_receipt_bytes"],
                "session_evidence_path": evidence["session_evidence_path"],
                "session_evidence_sha256": evidence["session_evidence_sha256"],
                "session_evidence_bytes": evidence["session_evidence_bytes"],
                "writer_source_path": evidence["writer_source_path"],
                "writer_source_sha256": evidence["writer_source_sha256"],
                "writer_source_bytes": evidence["writer_source_bytes"],
            }
        )
        summary["segment_problems"] = list(dict.fromkeys(segment_problems))
        summary["segment_eligible"] = not summary["segment_problems"]

        coverage_problems = list(summary["segment_problems"])
        if prompt_indexes != list(range(1, 81)):
            coverage_problems.append(
                "pack alone is not the complete prompt-index range 1 through 80"
            )
        missing_lanes = [
            target
            for target in selected_targets
            if int(summary["admitted_by_target"].get(target) or 0) < 1
        ]
        if missing_lanes:
            coverage_problems.append(
                "pack has no currently admitted row for selected lane(s): "
                + ", ".join(missing_lanes)
            )
        summary["coverage_problems"] = list(dict.fromkeys(coverage_problems))
        summary["coverage_eligible"] = not summary["coverage_problems"]
        summary["curriculum_id"] = str(curriculum_binding.get("id") or "")
        summary["curriculum_binding"] = dict(curriculum_binding)
    return summary


def collect_packs(
    since_hours: float,
    use_all: bool,
    targets: Any = TRAINING_TARGETS,
) -> dict[str, Any]:
    selected_targets = normalize_training_targets(targets)
    result: dict[str, Any] = {
        "pack_dir": str(PACK_DIR),
        "selected": [],
        "skipped_stale": 0,
        "files": 0,
        "physical_rows": 0,
        "logical_rows": 0,
        "rows": 0,
        "admitted": 0,
        "rejected": 0,
        "invalid_rows": 0,
        "admit_disagreements": 0,
        "legacy_admit_disagreements": 0,
        "current_admit_disagreements": 0,
        "quarantined": 0,
        "quarantine_files": [],
        "quarantine_blockers": [],
        "selected_targets": list(selected_targets),
        "explicit_rows_by_target": {target: 0 for target in selected_targets},
        "admitted_by_target": {target: 0 for target in selected_targets},
        "target_exclusions": {
            "missing_or_malformed": 0,
            "not_selected": 0,
        },
        "by_discipline": {},
        "by_status": {},
        "errors": [],
    }
    if not PACK_DIR.is_dir():
        result["errors"].append(f"pack directory does not exist: {PACK_DIR}")
        return result
    cutoff = 0.0 if use_all else time.time() - (since_hours * 3600.0)
    for path in sorted(PACK_DIR.glob(PACK_GLOB)):
        if path.name == PACK_LATEST_NAME:
            continue
        try:
            modified = path.stat().st_mtime
        except OSError:
            modified = 0.0
        if modified < cutoff:
            result["skipped_stale"] += 1
            continue
        summary = validate_pack(path, selected_targets)
        summary["modified_at_utc"] = datetime.fromtimestamp(modified, timezone.utc).isoformat()
        result["selected"].append(summary)
        result["files"] += 1
        result["physical_rows"] += summary["physical_rows"]
        result["logical_rows"] += summary["logical_rows"]
        result["rows"] += summary["rows"]
        result["admitted"] += summary["admitted"]
        result["rejected"] += summary["rejected"]
        result["invalid_rows"] += summary["invalid_rows"]
        result["admit_disagreements"] += summary["admit_disagreements"]
        result["legacy_admit_disagreements"] += summary[
            "legacy_admit_disagreements"
        ]
        result["current_admit_disagreements"] += summary[
            "current_admit_disagreements"
        ]
        result["quarantined"] += summary["quarantined"]
        for target, count in summary["explicit_rows_by_target"].items():
            result["explicit_rows_by_target"][target] += count
        for target, count in summary["admitted_by_target"].items():
            result["admitted_by_target"][target] += count
        for reason, count in summary["target_exclusions"].items():
            result["target_exclusions"][reason] += count
        result["quarantine_files"].extend(summary["quarantine_receipts"])
        result["quarantine_blockers"].extend(summary["quarantine_blockers"])
        for key, count in summary["by_discipline"].items():
            result["by_discipline"][key] = result["by_discipline"].get(key, 0) + count
        for key, count in summary["by_status"].items():
            result["by_status"][key] = result["by_status"].get(key, 0) + count
        result["errors"].extend(f"{path.name}: {item}" for item in summary["errors"][:4])
    result["quarantine_files"] = sorted(set(result["quarantine_files"]))
    result["quarantine_blockers"] = sorted(set(result["quarantine_blockers"]))
    return result


def pack_segment_evidence(segment: dict[str, Any]) -> dict[str, Any]:
    """Return the immutable, transfer-complete evidence descriptor for one segment."""

    quarantine = [
        {"path": str(path), "sha256": str(digest)}
        for path, digest in sorted(
            (segment.get("quarantine_receipt_sha256") or {}).items()
        )
    ]
    return {
        "run_id": segment.get("segment_run_id"),
        "path": segment.get("path"),
        "name": segment.get("name"),
        "sha256": segment.get("pack_sha256"),
        "rows": segment.get("rows"),
        "start_index": segment.get("segment_start_index"),
        "end_index": segment.get("segment_end_index"),
        "prompt_indexes": list(segment.get("segment_prompt_indexes") or []),
        "modified_at_utc": segment.get("modified_at_utc"),
        "pack_receipt": {
            "path": segment.get("pack_receipt_path"),
            "sha256": segment.get("pack_receipt_sha256"),
            "bytes": segment.get("pack_receipt_bytes"),
        },
        "session_evidence": {
            "path": segment.get("session_evidence_path"),
            "sha256": segment.get("session_evidence_sha256"),
            "bytes": segment.get("session_evidence_bytes"),
        },
        "writer_source": {
            "path": segment.get("writer_source_path"),
            "sha256": segment.get("writer_source_sha256"),
            "bytes": segment.get("writer_source_bytes"),
        },
        "quarantine_receipts": quarantine,
    }


def proven_void_positions(
    expected_prompt_hashes: Sequence[Any],
    exclude_positions: set[int],
    reservations_dir: Path = RESERVATIONS_DIR,
    run_id: str = "",
) -> dict[int, str]:
    """Positions proven consumed-but-unserved by the write-ahead ledger.

    Fail-closed on every axis: a hole counts ONLY when a reservation exists whose
    canonical base-prompt hash equals the curriculum contract's hash for exactly
    that position (so a reservation from different material can never cover a
    hole), optionally restricted to one run_id (pack-level repair uses the pack's
    own run; chain-level bridging accepts any run of the same material). A pack
    with missing rows and NO matching reservation stays exactly as refused as it
    always was.
    """
    voids: dict[int, str] = {}
    hashes = [str(item or "") for item in (expected_prompt_hashes or [])]
    if len(hashes) != 80:
        return voids
    try:
        for path in reservations_dir.glob("ENGEL_PROMPT_USE_RESERVATION_*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError, ValueError):
                continue
            if not isinstance(payload, dict):
                continue
            if run_id and str(payload.get("run_id") or "") != run_id:
                continue
            position = evidence_int(payload.get("prompt_position"), 0)
            if not (1 <= position <= 80) or position in exclude_positions or position in voids:
                continue
            reserved_hash = str(payload.get("base_prompt_sha256") or "")
            if reserved_hash and reserved_hash == hashes[position - 1]:
                voids[position] = str(payload.get("reservation_id") or path.name)
    except OSError:
        return {}
    return voids


def complete_segment_chains(
    segments: Sequence[dict[str, Any]],
    void_positions: set[int] | frozenset[int] = frozenset(),
) -> list[list[dict[str, Any]]]:
    """Return the newest exact 1..80 chain per schedule identity.

    Dynamic selection avoids an exponential search when years of compatible resume
    segments accumulate. Partial files, overlaps, and gaps still never count alone.
    void_positions may bridge a gap ONLY where no eligible segment covers the
    position - each void is backed by a reservation receipt proving the position
    was consumed and unserved, so nothing trainable is being skipped.
    """

    by_start: dict[int, list[dict[str, Any]]] = {}
    for segment in segments:
        if segment.get("segment_eligible") is not True:
            continue
        start = evidence_int(segment.get("segment_start_index"), 0)
        end = evidence_int(segment.get("segment_end_index"), 0)
        if not (1 <= start <= end <= 80):
            continue
        by_start.setdefault(start, []).append(segment)
    for start in by_start:
        by_start[start].sort(
            key=lambda item: (
                str(item.get("modified_at_utc") or ""),
                str(item.get("name") or ""),
                str(item.get("pack_sha256") or ""),
            ),
            reverse=True,
        )

    def segment_key(item: dict[str, Any]) -> tuple[str, str, str]:
        return (
            str(item.get("modified_at_utc") or ""),
            str(item.get("name") or ""),
            str(item.get("pack_sha256") or ""),
        )

    def chain_key(
        chain: Sequence[dict[str, Any]],
    ) -> tuple[tuple[str, str, str], tuple[tuple[str, str, str], ...]]:
        return segment_key(chain[-1]), tuple(segment_key(item) for item in chain)

    schedules = sorted(
        {
            str(segment.get("schedule_identity_sha256") or "")
            for segment in segments
            if segment.get("segment_eligible") is True
            and str(segment.get("schedule_identity_sha256") or "")
        }
    )
    chains: list[list[dict[str, Any]]] = []
    for schedule_sha256 in schedules:
        memo: dict[int, list[dict[str, Any]] | None] = {}

        def newest_from(next_index: int) -> list[dict[str, Any]] | None:
            if next_index >= 81:
                return []
            if next_index in memo:
                return memo[next_index]
            possibilities: list[list[dict[str, Any]]] = []
            for candidate in by_start.get(next_index, []):
                if (
                    str(candidate.get("schedule_identity_sha256") or "")
                    != schedule_sha256
                ):
                    continue
                suffix = newest_from(
                    evidence_int(candidate.get("segment_end_index"), 0) + 1
                )
                if suffix is not None:
                    possibilities.append([candidate, *suffix])
            selected_chain = max(possibilities, key=chain_key) if possibilities else None
            if selected_chain is None and next_index in void_positions:
                # No segment covers this position and its reservation proves it was
                # consumed-but-unserved: bridge it. Segments always win over voids.
                selected_chain = newest_from(next_index + 1)
            memo[next_index] = selected_chain
            return memo[next_index]

        selected = newest_from(1)
        if selected:
            chains.append(selected)
    return chains


def combine_segment_chain(
    curriculum_binding: dict[str, Any],
    segments: Sequence[dict[str, Any]],
    selected_targets: Sequence[str],
    void_positions: dict[int, str] | None = None,
) -> dict[str, Any] | None:
    """Combine one already-contiguous chain into an exact logical curriculum pack.

    (2026-08-15) Rows plus reservation-proven voids must cover exactly 1..80; a
    void contributes consumption evidence, never a trainable row, and is recorded
    in the chain descriptor with its reservation id so the coverage is auditable.
    """

    if not segments:
        return None
    voids = dict(void_positions or {})
    prompt_indexes = [
        index
        for segment in segments
        for index in (segment.get("segment_prompt_indexes") or [])
    ]
    covered = sorted(set(prompt_indexes) | set(voids))
    schedule_hashes = {
        str(segment.get("schedule_identity_sha256") or "") for segment in segments
    }
    target_sets = {
        tuple(segment.get("training_targets") or []) for segment in segments
    }
    levels = {str(segment.get("training_level") or "") for segment in segments}
    if (
        not prompt_indexes
        or prompt_indexes != sorted(set(prompt_indexes))
        or covered != list(range(1, 81))
        or len(schedule_hashes) != 1
        or "" in schedule_hashes
        or len(target_sets) != 1
        or len(levels) != 1
        or "" in levels
    ):
        return None

    descriptor = {
        "schema": PACK_SEGMENT_CHAIN_SCHEMA,
        "curriculum_id": curriculum_binding.get("id"),
        "curriculum_template_sha256": curriculum_binding.get("template_sha256"),
        "schedule_identity_sha256": next(iter(schedule_hashes)),
        "selected_targets": list(selected_targets),
        "segments": [pack_segment_evidence(segment) for segment in segments],
        "void_positions": {
            str(position): voids[position]
            for position in sorted(voids)
            if position not in set(prompt_indexes)
        },
    }
    chain_sha256 = canonical_json_sha256(descriptor)
    single = len(segments) == 1
    combined: dict[str, Any] = {
        "path": segments[0]["path"] if single else "",
        "name": (
            segments[0]["name"]
            if single
            else f"{curriculum_binding.get('id')}:"
            f"{len(segments)}-segment-chain"
        ),
        "pack_sha256": segments[0]["pack_sha256"] if single else "",
        "pack_read_only": all(
            segment.get("pack_read_only") is True for segment in segments
        ),
        "curriculum_id": str(curriculum_binding.get("id") or ""),
        "curriculum_binding": dict(curriculum_binding),
        "segment_eligible": True,
        "segment_problems": [],
        "segment_run_id": "",
        "segment_start_index": 1,
        "segment_end_index": 80,
        # Actual row indexes only: a void has no row, and downstream consumers
        # compare these against the rows they really receive.
        "segment_prompt_indexes": sorted(set(prompt_indexes)),
        "schedule_identity": dict(segments[0].get("schedule_identity") or {}),
        "schedule_identity_sha256": next(iter(schedule_hashes)),
        "training_targets": list(next(iter(target_sets))),
        "training_level": next(iter(levels)),
        "coverage_eligible": True,
        "coverage_problems": [],
        "segment_chain": descriptor,
        "segment_chain_sha256": chain_sha256,
        "segments": list(segments),
        "segment_count": len(segments),
        "modified_at_utc": str(segments[-1].get("modified_at_utc") or ""),
        "physical_rows": 0,
        "logical_rows": 0,
        "rows": 0,
        "admitted": 0,
        "rejected": 0,
        "invalid_rows": 0,
        "admit_disagreements": 0,
        "legacy_admit_disagreements": 0,
        "current_admit_disagreements": 0,
        "quarantined": 0,
        "quarantine_receipts": [],
        "quarantine_receipt_sha256": {},
        "quarantine_blockers": [],
        "selected_targets": list(selected_targets),
        "explicit_rows_by_target": {target: 0 for target in selected_targets},
        "admitted_by_target": {target: 0 for target in selected_targets},
        "target_exclusions": {"missing_or_malformed": 0, "not_selected": 0},
        "missing_optional_fields": [],
        "by_discipline": {},
        "by_status": {},
        "errors": [],
    }
    missing_optional: set[str] = set()
    for segment in segments:
        combined["physical_rows"] += evidence_int(segment.get("physical_rows"), 0)
        combined["logical_rows"] += evidence_int(segment.get("logical_rows"), 0)
        for field in (
            "rows",
            "admitted",
            "rejected",
            "invalid_rows",
            "admit_disagreements",
            "legacy_admit_disagreements",
            "current_admit_disagreements",
            "quarantined",
        ):
            combined[field] += evidence_int(segment.get(field), 0)
        for target in selected_targets:
            combined["explicit_rows_by_target"][target] += evidence_int(
                (segment.get("explicit_rows_by_target") or {}).get(target),
                0,
            )
            combined["admitted_by_target"][target] += evidence_int(
                (segment.get("admitted_by_target") or {}).get(target),
                0,
            )
        for reason in combined["target_exclusions"]:
            combined["target_exclusions"][reason] += evidence_int(
                (segment.get("target_exclusions") or {}).get(reason),
                0,
            )
        combined["quarantine_receipts"].extend(
            segment.get("quarantine_receipts") or []
        )
        combined["quarantine_receipt_sha256"].update(
            segment.get("quarantine_receipt_sha256") or {}
        )
        combined["quarantine_blockers"].extend(
            segment.get("quarantine_blockers") or []
        )
        for key, count in (segment.get("by_discipline") or {}).items():
            combined["by_discipline"][key] = (
                combined["by_discipline"].get(key, 0) + evidence_int(count, 0)
            )
        for key, count in (segment.get("by_status") or {}).items():
            combined["by_status"][key] = (
                combined["by_status"].get(key, 0) + evidence_int(count, 0)
            )
        missing_optional.update(segment.get("missing_optional_fields") or [])
        combined["errors"].extend(segment.get("errors") or [])
    combined["quarantine_receipts"] = sorted(
        set(combined["quarantine_receipts"])
    )
    combined["quarantine_blockers"] = sorted(
        set(combined["quarantine_blockers"])
    )
    combined["missing_optional_fields"] = sorted(missing_optional)
    missing_lanes = [
        target
        for target in selected_targets
        if combined["admitted_by_target"].get(target, 0) < 1
    ]
    if (
        combined["physical_rows"] != 80
        or combined["logical_rows"] != 80
        or combined["rows"] != 80
        or missing_lanes
    ):
        return None
    return combined


def selected_pack_transfer_plan(packs: dict[str, Any]) -> dict[str, Any]:
    """Flatten selected logical chains into one exact physical evidence roster."""

    expected_hashes: dict[str, str] = {}
    paths: list[Path] = []
    kinds: dict[str, str] = {}
    errors: list[str] = []
    segment_count = 0

    def add(raw_path: Any, raw_digest: Any, kind: str) -> None:
        path_text = str(raw_path or "").strip()
        digest = str(raw_digest or "").strip().casefold()
        if not path_text or not re.fullmatch(r"[a-f0-9]{64}", digest):
            errors.append(f"{kind}: missing path or valid SHA-256")
            return
        try:
            resolved = Path(path_text).resolve(strict=True)
        except OSError as exc:
            errors.append(f"{kind}: evidence path is unavailable ({exc})")
            return
        key = os.path.normcase(str(resolved))
        previous = expected_hashes.get(key)
        if previous is not None:
            if previous != digest:
                errors.append(f"{kind}: one path has conflicting expected hashes")
            return
        expected_hashes[key] = digest
        kinds[key] = kind
        paths.append(resolved)

    for chain in packs.get("selected") or []:
        for segment in chain.get("segments") or []:
            segment_count += 1
            add(segment.get("path"), segment.get("pack_sha256"), "pack segment")
            add(
                segment.get("pack_receipt_path"),
                segment.get("pack_receipt_sha256"),
                "stamped pack receipt",
            )
            add(
                segment.get("session_evidence_path"),
                segment.get("session_evidence_sha256"),
                "immutable session evidence",
            )
            for sidecar_path, sidecar_sha256 in (
                segment.get("quarantine_receipt_sha256") or {}
            ).items():
                add(sidecar_path, sidecar_sha256, "quarantine sidecar")
    return {
        "ok": not errors,
        "paths": paths,
        "expected_hashes": expected_hashes,
        "kinds": kinds,
        "errors": errors,
        "segment_count": segment_count,
        "evidence_file_count": len(paths) - segment_count,
        "receipt": [
            {
                "path": str(path),
                "sha256": expected_hashes[os.path.normcase(str(path))],
                "kind": kinds[os.path.normcase(str(path))],
            }
            for path in paths
        ],
    }


def collect_current_five_packs(
    since_hours: float,
    use_all: bool,
    targets: Any = TRAINING_TARGETS,
    *,
    index_path: Path = CURRICULA_INDEX_PATH,
    manifest_path: Path = TRAINING_ASSET_MANIFEST_PATH,
) -> dict[str, Any]:
    """Select one newest exact immutable 1..80 segment chain per curriculum."""

    selected_targets = normalize_training_targets(targets)
    audit = collect_packs(since_hours, use_all, selected_targets)
    contract = load_current_curriculum_contract(index_path, manifest_path)
    candidates: dict[str, list[dict[str, Any]]] = {
        curriculum_id: [] for curriculum_id, _, _ in CANONICAL_CURRICULA
    }
    examined: dict[str, list[dict[str, Any]]] = {
        curriculum_id: [] for curriculum_id in candidates
    }
    if contract.get("ok") is True:
        for audit_item in audit["selected"]:
            curriculum_id = str(audit_item.get("curriculum_id") or "")
            binding = (contract.get("bindings_by_id") or {}).get(curriculum_id)
            if not isinstance(binding, dict):
                continue
            strict = validate_pack(Path(audit_item["path"]), selected_targets, binding)
            strict["modified_at_utc"] = audit_item.get("modified_at_utc")
            examined[curriculum_id].append(
                {
                    "name": strict["name"],
                    "pack_sha256": strict["pack_sha256"],
                    "segment_eligible": strict["segment_eligible"],
                    "segment_start_index": strict["segment_start_index"],
                    "segment_end_index": strict["segment_end_index"],
                    "schedule_identity_sha256": strict[
                        "schedule_identity_sha256"
                    ],
                    "coverage_eligible": strict["coverage_eligible"],
                    "problems": strict["segment_problems"],
                }
            )
            if strict["segment_eligible"]:
                candidates[curriculum_id].append(strict)

    chosen: list[dict[str, Any]] = []
    coverage_items: list[dict[str, Any]] = []
    for curriculum_id, title, discipline in CANONICAL_CURRICULA:
        binding = dict(
            (contract.get("bindings_by_id") or {}).get(curriculum_id) or {}
        )
        # Reservation-proven voids for this curriculum's exact material: positions
        # consumed-but-unserved that no segment can cover and no run may replay.
        binding_voids = proven_void_positions(
            binding.get("base_prompt_sha256_by_index") or [], set()
        )
        complete = [
            combined
            for chain in complete_segment_chains(
                candidates[curriculum_id], void_positions=set(binding_voids)
            )
            if (
                combined := combine_segment_chain(
                    binding,
                    chain,
                    selected_targets,
                    void_positions=binding_voids,
                )
            )
            is not None
        ]
        complete.sort(
            key=lambda item: (
                str(item.get("modified_at_utc") or ""),
                str((item.get("segments") or [{}])[-1].get("name") or ""),
                str(item.get("segment_chain_sha256") or ""),
            ),
            reverse=True,
        )
        selected = complete[0] if complete else None
        if selected is not None:
            chosen.append(selected)
        coverage_items.append(
            {
                "curriculum_id": curriculum_id,
                "curriculum_title": title,
                "discipline": discipline,
                "covered": selected is not None,
                "selected_pack": selected["path"] if selected else "",
                "selected_pack_sha256": selected["pack_sha256"] if selected else "",
                "selected_segment_count": selected["segment_count"] if selected else 0,
                "selected_segments": (
                    list((selected.get("segment_chain") or {}).get("segments") or [])
                    if selected
                    else []
                ),
                "selected_segment_chain_sha256": (
                    selected["segment_chain_sha256"] if selected else ""
                ),
                "physical_rows": selected["physical_rows"] if selected else 0,
                "logical_rows": selected["logical_rows"] if selected else 0,
                "rows": selected["rows"] if selected else 0,
                "admitted": selected["admitted"] if selected else 0,
                "rejected": selected["rejected"] if selected else 0,
                "explicit_rows_by_target": (
                    dict(selected["explicit_rows_by_target"]) if selected else {}
                ),
                "admitted_by_target": (
                    dict(selected["admitted_by_target"]) if selected else {}
                ),
                "binding": dict(
                    (contract.get("bindings_by_id") or {}).get(curriculum_id) or {}
                ),
                "examined_current_candidates": examined[curriculum_id],
            }
        )

    result: dict[str, Any] = {
        "pack_dir": audit["pack_dir"],
        "selected": chosen,
        "skipped_stale": audit["skipped_stale"],
        "files": 0,
        "physical_rows": 0,
        "logical_rows": 0,
        "rows": 0,
        "admitted": 0,
        "rejected": 0,
        "invalid_rows": 0,
        "admit_disagreements": 0,
        "legacy_admit_disagreements": 0,
        "current_admit_disagreements": 0,
        "quarantined": 0,
        "quarantine_files": [],
        "quarantine_blockers": [],
        "selected_targets": list(selected_targets),
        "explicit_rows_by_target": {target: 0 for target in selected_targets},
        "admitted_by_target": {target: 0 for target in selected_targets},
        "target_exclusions": {"missing_or_malformed": 0, "not_selected": 0},
        "by_discipline": {},
        "by_status": {},
        "errors": [],
        "audit": {
            "files": audit["files"],
            "physical_rows": audit["physical_rows"],
            "logical_rows": audit["logical_rows"],
            "rows": audit["rows"],
            "admitted": audit["admitted"],
            "rejected": audit["rejected"],
            "legacy_admit_disagreements": audit["legacy_admit_disagreements"],
            "current_admit_disagreements": audit["current_admit_disagreements"],
            "quarantined": audit["quarantined"],
            "errors": audit["errors"][:20],
        },
        "curriculum_contract": contract,
        "curriculum_coverage": {
            "schema": "engel_five_curriculum_model_handoff_v1",
            "ok": contract.get("ok") is True
            and len(chosen) == len(CANONICAL_CURRICULA),
            "required_curriculum_ids": [
                curriculum_id for curriculum_id, _, _ in CANONICAL_CURRICULA
            ],
            "covered_curriculum_ids": [
                item["curriculum_id"] for item in coverage_items if item["covered"]
            ],
            "items": coverage_items,
        },
    }
    for item in chosen:
        result["files"] += evidence_int(item.get("segment_count"), 0)
        result["physical_rows"] += evidence_int(item.get("physical_rows"), 0)
        result["logical_rows"] += evidence_int(item.get("logical_rows"), 0)
        for field in (
            "rows",
            "admitted",
            "rejected",
            "invalid_rows",
            "admit_disagreements",
            "legacy_admit_disagreements",
            "current_admit_disagreements",
            "quarantined",
        ):
            result[field] += int(item.get(field) or 0)
        for target, count in item["explicit_rows_by_target"].items():
            result["explicit_rows_by_target"][target] += int(count)
        for target, count in item["admitted_by_target"].items():
            result["admitted_by_target"][target] += int(count)
        for reason, count in item["target_exclusions"].items():
            result["target_exclusions"][reason] += int(count)
        result["quarantine_files"].extend(item["quarantine_receipts"])
        result["quarantine_blockers"].extend(item["quarantine_blockers"])
        for key, count in item["by_discipline"].items():
            result["by_discipline"][key] = result["by_discipline"].get(key, 0) + count
        for key, count in item["by_status"].items():
            result["by_status"][key] = result["by_status"].get(key, 0) + count
        result["errors"].extend(
            f"{item['name']}: {problem}" for problem in item["errors"][:4]
        )
    result["quarantine_files"] = sorted(set(result["quarantine_files"]))
    result["quarantine_blockers"] = sorted(set(result["quarantine_blockers"]))
    if contract.get("ok") is not True:
        result["errors"].extend(
            "curriculum contract: " + str(problem)
            for problem in contract.get("errors") or []
        )
    missing = [
        item["curriculum_id"] for item in coverage_items if not item["covered"]
    ]
    if missing:
        result["errors"].append(
            "missing complete current curriculum segment chains: "
            + ", ".join(missing)
        )
    return result


# --------------------------------------------------------------------------------------
# LoRA hand-off (never executed here)
# --------------------------------------------------------------------------------------


def approval_phrase(path: Path, name: str, fallback: str) -> str:
    """Read an approval phrase out of the real tool so this receipt cannot drift from it."""
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return fallback
    match = re.search(rf"^{re.escape(name)}\s*=\s*\"([^\"]+)\"", text, re.MULTILINE)
    return match.group(1) if match else fallback


def lora_next_steps(cfg: dict[str, Any]) -> list[str]:
    """Emit auditable manual fallback and post-training canary commands.

    A LoRA proof run rewrites weights and a canary decides whether they are fit to serve.
    Both require an exact approval phrase. This cycle may perform the proof only when
    the operator explicitly selects ``llm`` and supplies its phrase; canary, conversion,
    and promotion remain separate operations and are never inferred from training success.
    """
    train_phrase = approval_phrase(
        LORA_PROOF_TOOL, "APPROVAL_PHRASE", "APPROVE_ENGEL_LOCAL_LLM_LORA_TRAINING_RUN_V1"
    )
    canary_phrase = approval_phrase(
        LORA_CANARY_TOOL,
        "CANARY_APPROVAL_PHRASE",
        "APPROVE_ENGEL_LOCAL_LLM_LORA_CANARY_RUN_V1",
    )
    prefix_parts = ["ssh"]
    if cfg.get("key"):
        prefix_parts.append(f'-i "{cfg["key"]}"')
    if cfg.get("port"):
        prefix_parts.append(f'-p {cfg["port"]}')
    prefix_parts.append(str(cfg.get("target") or "root@192.0.2.50"))
    prefix = " ".join(prefix_parts)
    proof = f"{CT_TOOLS_DIR}/run_engel_ct246_local_lora_proof.py"
    canary = f"{CT_TOOLS_DIR}/run_engel_ct246_lora_canary_gate.py"
    conversion = f"{CT_TOOLS_DIR}/run_engel_ct246_gguf_conversion.py"
    return [
        "# LLM weight training runs only when target=llm and its exact approval is supplied.",
        "# 1. Preflight the LoRA proof (no approval needed, no weights written):",
        f'{prefix} "python3 {proof} --preflight-only"',
        "# 2. Manual fallback: OPERATOR-APPROVED CT246 adapter training/evaluation:",
        f'{prefix} "python3 {proof} --approval {train_phrase}'
        ' --origin engel_real_training_cycle --training-budget-seconds 10800'
        ' --eval-timeout-seconds 7200"',
        "# 3. After training, read the separate canary gate status:",
        f'{prefix} "python3 {canary} --status"',
        "# 4. OPERATOR-APPROVED canary on the new adapter (does not promote to production chat):",
        f'{prefix} "python3 {canary} --approval {canary_phrase} --origin engel_real_training_cycle"',
        "# 5. Only after a passed canary: copy its immutable stamped path and exact minted",
        "#    promotion phrase from status. LATEST is status-only and is refused as input.",
        f'{prefix} "python3 {conversion}'
        ' --canary-receipt /opt/engel/reports/llm_training/ENGEL_CT246_LORA_CANARY_<STAMP>.json'
        ' --approval <EXACT_MINTED_PROMOTION_PHRASE>'
        ' --converter /opt/engel/tools/llama.cpp/convert_hf_to_gguf.py'
        ' --validator /opt/engel/tools/run_engel_ct246_gguf_canary.py'
        ' --validator-python /opt/engel/.venv/bin/python'
        ' --output-dir /opt/engel/models-active/llm/<PROVEN_ENGEL_MODEL_NAME>'
        ' --quantization q8_0 --origin engel_real_training_cycle"',
    ]


# --------------------------------------------------------------------------------------
# The cycle
# --------------------------------------------------------------------------------------


def record(
    receipt: dict[str, Any],
    step: str,
    ok: bool,
    detail: str,
    seconds: float,
    command: str | None = None,
) -> bool:
    entry: dict[str, Any] = {
        "step": step,
        "ok": bool(ok),
        "detail": detail,
        "seconds": round(float(seconds), 2),
    }
    if command:
        entry["command"] = command
    receipt["steps"].append(entry)
    event("step", step=step, ok=bool(ok), seconds=entry["seconds"], detail=detail[:400])
    return bool(ok)


def step_collect_packs(receipt: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    started = time.perf_counter()
    selected_targets = normalize_training_targets(getattr(args, "targets", "slm"))
    packs = collect_current_five_packs(
        args.since_hours,
        args.all,
        selected_targets,
        index_path=CURRICULA_INDEX_PATH,
        manifest_path=TRAINING_ASSET_MANIFEST_PATH,
    )
    window = "all packs on disk" if args.all else f"modified within {args.since_hours:g}h"
    detail_bits = [
        f"{packs['files']} current curriculum pack file(s) ({window})",
        f"{packs['rows']} rows",
        f"{packs['admitted']} admitted",
        f"{packs['rejected']} rejected",
    ]
    coverage = packs["curriculum_coverage"]
    detail_bits.append(
        "curriculum coverage="
        f"{len(coverage['covered_curriculum_ids'])}/"
        f"{len(coverage['required_curriculum_ids'])}"
    )
    if packs["invalid_rows"]:
        detail_bits.append(f"{packs['invalid_rows']} INVALID rows")
    if packs["legacy_admit_disagreements"]:
        detail_bits.append(
            f"{packs['legacy_admit_disagreements']} legacy admit claims quarantined"
        )
    if packs["current_admit_disagreements"]:
        detail_bits.append(
            f"{packs['current_admit_disagreements']} current admit DISAGREEMENTS"
        )
    if packs["quarantined"]:
        detail_bits.append(f"{packs['quarantined']} sidecar-quarantined rows")
    target_exclusions = packs["target_exclusions"]
    if any(target_exclusions.values()):
        detail_bits.append(
            "target exclusions="
            f"{target_exclusions['missing_or_malformed']} missing/malformed + "
            f"{target_exclusions['not_selected']} not selected"
        )
    detail_bits.append(
        "admitted by target="
        + ", ".join(
            f"{target}:{packs['admitted_by_target'].get(target, 0)}"
            for target in selected_targets
        )
    )
    if packs["skipped_stale"]:
        detail_bits.append(f"{packs['skipped_stale']} outside the window")
    if packs["errors"]:
        detail_bits.append("first errors: " + " | ".join(packs["errors"][:3]))
    missing_selected_targets = [
        target
        for target in selected_targets
        if packs["admitted_by_target"].get(target, 0) <= 0
    ]
    ok = (
        packs["files"] > 0
        and packs["admitted"] > 0
        and not missing_selected_targets
        and packs["current_admit_disagreements"] == 0
        and not packs["quarantine_blockers"]
        and coverage.get("ok") is True
    )
    if not PACK_DIR.is_dir():
        receipt["blockers"].append(
            f"no pack directory at {PACK_DIR}: run a prompt-training session first "
            "(it emits the packs this cycle trains on)"
        )
    elif packs["curriculum_contract"].get("ok") is not True:
        receipt["blockers"].append(
            "current five-curriculum asset contract is invalid: "
            + " | ".join(packs["curriculum_contract"].get("errors")[:5])
        )
    elif coverage.get("ok") is not True:
        missing_curricula = sorted(
            set(coverage["required_curriculum_ids"])
            - set(coverage["covered_curriculum_ids"])
        )
        receipt["blockers"].append(
            "model training requires one exact immutable current 1-through-80 pack "
            "segment chain for every curriculum; missing: "
            + ", ".join(missing_curricula)
        )
    elif packs["files"] == 0:
        receipt["blockers"].append(
            f"no pack files matched {PACK_GLOB} in {PACK_DIR} ({window}); "
            "nothing to train on, so no cycle was run"
        )
    elif packs["admitted"] == 0:
        receipt["blockers"].append(
            f"{packs['rows']} pack rows collected but 0 target-matched rows are admitted; "
            "a cycle over zero admitted rows would train on nothing"
        )
    elif missing_selected_targets:
        receipt["blockers"].append(
            "no admitted prompt rows explicitly target selected model lane(s): "
            + ", ".join(missing_selected_targets)
            + "; target metadata is never inferred from another lane"
        )
    if target_exclusions["missing_or_malformed"]:
        receipt.setdefault("warnings", []).append(
            f"{target_exclusions['missing_or_malformed']} pack row(s) had missing or "
            "malformed training_targets and were excluded from every model lane"
        )
    if packs["legacy_admit_disagreements"]:
        receipt.setdefault("warnings", []).append(
            f"{packs['legacy_admit_disagreements']} pre-policy row(s) claimed admit=true "
            "but fail the current CONTRACT 1 rule; they were excluded from every positive "
            "training count and retained as historical audit evidence"
        )
    if packs["current_admit_disagreements"]:
        receipt["blockers"].append(
            f"{packs['current_admit_disagreements']} current-policy row(s) claim admit=true "
            "but fail the CONTRACT 1 admit rule; the emitter is over-admitting and those "
            "rows were NOT counted"
        )
    if packs["quarantine_blockers"]:
        receipt["blockers"].append(
            "prompt-row quarantine ledger is invalid: "
            + " | ".join(packs["quarantine_blockers"][:3])
        )
    record(receipt, "collect_packs", ok, "; ".join(detail_bits), time.perf_counter() - started)
    return packs


def step_resolve_ct_python(receipt: dict[str, Any], cfg: dict[str, Any]) -> str:
    started = time.perf_counter()
    probe = (
        f"if [ -x {shlex.quote(CT_VENV_PYTHON)} ]; then echo {shlex.quote(CT_VENV_PYTHON)}; "
        "else command -v python3 || echo python3; fi"
    )
    result = ssh_run(cfg, probe, TIMEOUT_PROBE)
    chosen = ""
    for line in (result.get("stdout") or "").splitlines():
        line = line.strip()
        if line.startswith("/") or line == "python3":
            chosen = line
    ok = bool(result["ok"] and chosen)
    detail = (
        f"CT python = {chosen}"
        if ok
        else f"ssh probe failed: {tail(result.get('stderr') or result.get('stdout') or '', 400)}"
    )
    if not ok:
        receipt["blockers"].append(
            f"cannot reach CT246 over ssh ({cfg.get('target')}): {tail(result.get('stderr') or '', 200)}"
        )
    record(receipt, "resolve_ct_python", ok, detail, time.perf_counter() - started, probe)
    return chosen if ok else ""


def push_files(
    receipt: dict[str, Any],
    cfg: dict[str, Any],
    step: str,
    files: Sequence[Path],
    remote_dir: str,
    expected_hashes: dict[str, str] | None = None,
    *,
    batch_copy: bool = False,
) -> bool:
    """scp a named set of files and prove the remote bytes match, file by file.

    A short or truncated copy is the dangerous failure here: the remote build would run
    against half a tool or half a pack and report a perfectly healthy-looking result.
    """
    started = time.perf_counter()
    if not files:
        record(receipt, step, True, "nothing to push", time.perf_counter() - started)
        return True
    local_hashes: dict[str, str] = {}
    copy_errors: list[str] = []
    copy_plan: list[tuple[Path, str]] = []
    remote_names: dict[str, Path] = {}
    normalized_expected = (
        {
            os.path.normcase(str(Path(path).resolve())): str(digest).casefold()
            for path, digest in expected_hashes.items()
        }
        if expected_hashes is not None
        else None
    )
    for path in files:
        try:
            resolved = path.resolve(strict=True)
            info = os.lstat(resolved)
        except OSError as exc:
            copy_errors.append(f"{path.name}: local metadata failed ({exc})")
            continue
        local_key = os.path.normcase(str(resolved))
        if (
            not stat.S_ISREG(info.st_mode)
            or path.is_symlink()
            or (
                normalized_expected is not None
                and bool(info.st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
            )
        ):
            copy_errors.append(f"{path.name}: local file type/mode is not immutable")
            continue
        digest = sha256_file(resolved).casefold()
        if normalized_expected is not None:
            expected_digest = normalized_expected.get(local_key)
            if expected_digest is None:
                copy_errors.append(f"{path.name}: no validated SHA-256 was supplied")
                continue
            if digest != expected_digest:
                copy_errors.append(
                    f"{path.name}: bytes changed after local validation"
                )
                continue
        remote_path = f"{remote_dir}/{path.name}"
        previous_source = remote_names.get(path.name)
        if previous_source is not None and previous_source != resolved:
            copy_errors.append(
                f"{path.name}: two local evidence files would overwrite one remote name"
            )
            continue
        remote_names[path.name] = resolved
        local_hashes[remote_path] = digest
        copy_plan.append((resolved, remote_path))
    if normalized_expected is not None and len(normalized_expected) != len(files):
        copy_errors.append("validated SHA-256 roster does not match the transfer roster")
    if copy_errors:
        receipt["blockers"].append(
            f"{step}: local validated transfer preflight failed; no remote copy was attempted"
        )
        record(
            receipt,
            step,
            False,
            "local preflight failed: " + " | ".join(copy_errors[:6]),
            time.perf_counter() - started,
        )
        return False

    mkdir = f"mkdir -p {shlex.quote(remote_dir)}"
    mkdir_result = ssh_run(cfg, mkdir, TIMEOUT_SHORT)
    if not mkdir_result["ok"]:
        detail = f"mkdir failed: {tail(mkdir_result.get('stderr') or '', 400)}"
        receipt["blockers"].append(f"{step}: could not create {remote_dir} on CT246")
        record(receipt, step, False, detail, time.perf_counter() - started, mkdir)
        return False

    if batch_copy:
        # Pack, stamped receipt, and session evidence are one hand-off. Copying the
        # already preflighted roster in one bounded SCP keeps resume segment counts from
        # silently exceeding the whole-cycle deadline.
        copy = run_local(
            [
                *scp_argv(cfg),
                *(str(path) for path, _ in copy_plan),
                f"{cfg['target']}:{shlex.quote(remote_dir)}",
            ],
            TIMEOUT_SCP,
        )
        if not copy["ok"]:
            copy_errors.append(
                "batched evidence scp failed "
                f"({tail(copy.get('stderr') or '', 200)})"
            )
    else:
        for path, remote_path in copy_plan:
            # The remote half of an scp spec is expanded by the remote shell, and pack
            # names carry a run_id this tool does not control, so quote rather than trust.
            copy = run_local(
                [
                    *scp_argv(cfg),
                    str(path),
                    f"{cfg['target']}:{shlex.quote(remote_path)}",
                ],
                TIMEOUT_SCP,
            )
            if not copy["ok"]:
                copy_errors.append(
                    f"{path.name}: scp failed "
                    f"({tail(copy.get('stderr') or '', 200)})"
                )

    verify = remote_sha256(cfg, sorted(local_hashes))
    mismatched = [
        name
        for name, digest in sorted(local_hashes.items())
        if verify.get("hashes", {}).get(name) != digest
    ]
    ok = not copy_errors and verify["ok"] and not mismatched
    detail_bits = [f"{len(local_hashes)} file(s) -> {remote_dir}", "sha256 verified" if ok else "sha256 MISMATCH"]
    if copy_errors:
        detail_bits.append("copy errors: " + " | ".join(copy_errors[:4]))
    if mismatched:
        detail_bits.append("bytes differ after copy: " + ", ".join(Path(m).name for m in mismatched[:6]))
    if not verify["ok"]:
        detail_bits.append(f"remote sha256sum failed: {tail(verify.get('stderr') or '', 200)}")
    if not ok:
        receipt["blockers"].append(
            f"{step}: remote copy is not byte-identical to the local file(s); "
            "the CT-side run would have used truncated or missing material"
        )
    record(
        receipt,
        step,
        ok,
        "; ".join(detail_bits),
        time.perf_counter() - started,
        f"scp -> {cfg['target']}:{remote_dir}",
    )
    return ok


def inspect_construction_corpus_bundle(local_root: Path, run_id: str) -> dict[str, Any]:
    """Build a fail-closed, serializable plan for one cycle's corpus evidence.

    ``verify_corpus_bundle`` owns the bundle schema and exact file allowlist.  This
    transport independently rechecks each declared file before trusting that allowlist,
    then later checks the same hashes on CT.  A genuinely absent local corpus is a valid
    empty mode; any artifact at all makes an incomplete bundle a hard error.
    """
    requested_root = Path(local_root)
    root = requested_root.resolve()
    ct_root = ct_construction_corpus_dir(run_id)
    base: dict[str, Any] = {
        "ok": False,
        "mode": "invalid",
        "local_root": str(root),
        "ct_root": ct_root,
        "bundle_sha256": "",
        "files": [],
        "blockers": [],
        "local_verified": False,
        "remote_verified": False,
    }
    if requested_root.is_symlink():
        base["blockers"] = ["local construction corpus root must not be a symlink"]
        return base
    if root.exists() and not root.is_dir():
        base["blockers"] = ["local construction corpus root is not a directory"]
        return base
    try:
        first_artifact = next(
            (path for path in root.rglob("*") if path.is_file() or path.is_symlink()),
            None,
        ) if root.is_dir() else None
    except OSError as exc:
        base["blockers"] = [f"cannot inspect local construction corpus: {exc}"]
        return base
    if first_artifact is None:
        base.update({"ok": True, "mode": "empty", "local_verified": True})
        return base

    try:
        verified = construction_corpus.verify_corpus_bundle(root)
    except Exception as exc:  # noqa: BLE001 - a broken verifier must fail closed
        base["blockers"] = [
            f"construction corpus verifier raised {type(exc).__name__}: {exc}"
        ]
        return base
    if not isinstance(verified, dict):
        base["blockers"] = ["construction corpus verifier returned no structured result"]
        return base

    verifier_blockers = [
        str(item) for item in (verified.get("blockers") or []) if str(item).strip()
    ]
    if verified.get("ok") is not True:
        base["blockers"] = verifier_blockers or [
            "local construction corpus is partial or failed bundle verification"
        ]
        return base

    bundle_sha = str(verified.get("bundle_sha256") or "").strip().casefold()
    if not re.fullmatch(r"[0-9a-f]{64}", bundle_sha):
        base["blockers"] = ["verified construction bundle has no valid bundle_sha256"]
        return base
    raw_files = verified.get("files")
    if not isinstance(raw_files, list) or not raw_files:
        base["blockers"] = ["verified construction bundle has an empty file allowlist"]
        return base

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    blockers: list[str] = []
    for index, item in enumerate(raw_files):
        if not isinstance(item, dict):
            blockers.append(f"bundle file record {index} is not an object")
            continue
        relative_text = str(item.get("relative_path") or "").strip().replace("\\", "/")
        relative = PurePosixPath(relative_text)
        if (
            not relative_text
            or relative.is_absolute()
            or relative_text.startswith("/")
            or any(part in {"", ".", ".."} for part in relative.parts)
        ):
            blockers.append(f"unsafe bundle relative_path: {relative_text!r}")
            continue
        canonical_relative = relative.as_posix()
        if canonical_relative in seen:
            blockers.append(f"duplicate bundle relative_path: {canonical_relative}")
            continue
        seen.add(canonical_relative)
        local_path = root.joinpath(*relative.parts)
        try:
            resolved = local_path.resolve(strict=True)
            resolved.relative_to(root)
        except (OSError, ValueError):
            blockers.append(f"bundle file escapes or is missing: {canonical_relative}")
            continue
        if local_path.is_symlink() or not resolved.is_file():
            blockers.append(f"bundle file is not a regular non-symlink file: {canonical_relative}")
            continue
        expected_sha = str(item.get("sha256") or "").strip().casefold()
        raw_bytes = item.get("bytes")
        try:
            expected_bytes = -1 if isinstance(raw_bytes, bool) else int(raw_bytes)
        except (TypeError, ValueError):
            expected_bytes = -1
        actual_bytes = resolved.stat().st_size
        actual_sha = sha256_file(resolved).casefold()
        if not re.fullmatch(r"[0-9a-f]{64}", expected_sha):
            blockers.append(f"bundle file has invalid sha256: {canonical_relative}")
        elif actual_sha != expected_sha:
            blockers.append(f"bundle file hash changed after verification: {canonical_relative}")
        if expected_bytes < 0 or actual_bytes != expected_bytes:
            blockers.append(f"bundle file size changed after verification: {canonical_relative}")
        normalized.append(
            {
                "relative_path": canonical_relative,
                "local_path": str(resolved),
                "bytes": actual_bytes,
                "sha256": actual_sha,
                "remote_path": f"{ct_root}/{canonical_relative}",
            }
        )

    if blockers or len(normalized) != len(raw_files):
        base["files"] = normalized
        base["blockers"] = blockers or ["construction bundle file set is incomplete"]
        return base
    normalized.sort(key=lambda item: item["relative_path"])
    base.update(
        {
            "ok": True,
            "mode": "complete",
            "bundle_sha256": bundle_sha,
            "files": normalized,
            "blockers": [],
            "local_verified": True,
        }
    )
    return base


def construction_corpus_receipt(plan: dict[str, Any]) -> dict[str, Any]:
    """Strip transport-only fields while retaining exact provenance evidence."""
    return {
        "mode": str(plan.get("mode") or "invalid"),
        "local_root": str(plan.get("local_root") or ""),
        "ct_root": str(plan.get("ct_root") or ""),
        "bundle_sha256": str(plan.get("bundle_sha256") or ""),
        "local_verified": plan.get("local_verified") is True,
        "remote_verified": plan.get("remote_verified") is True,
        "files": [
            {
                "relative_path": str(item.get("relative_path") or ""),
                "bytes": as_int(item.get("bytes")),
                "sha256": str(item.get("sha256") or ""),
                "remote_path": str(item.get("remote_path") or ""),
                **(
                    {"remote_sha256": str(item.get("remote_sha256") or "")}
                    if item.get("remote_sha256")
                    else {}
                ),
            }
            for item in (plan.get("files") or [])
            if isinstance(item, dict)
        ],
        "blockers": [str(item) for item in (plan.get("blockers") or [])],
    }


def remote_file_set(cfg: dict[str, Any], root: str) -> dict[str, Any]:
    """List regular files below one known run-scoped directory without globs."""
    command = f"find {shlex.quote(root)} -type f -print"
    result = ssh_run(cfg, command, TIMEOUT_SHORT)
    result["paths"] = sorted(
        line.strip() for line in str(result.get("stdout") or "").splitlines() if line.strip()
    )
    return result


def push_construction_corpus(
    receipt: dict[str, Any],
    cfg: dict[str, Any],
    plan: dict[str, Any],
) -> bool:
    """Copy one verified corpus bundle into a fresh cycle-owned CT directory.

    The destination must not exist.  This turns a failed direct copy into an isolated,
    unreachable staging failure instead of corrupting the corpus used by another cycle.
    Dataset builders receive this root only after the exact file set and every hash pass.
    """
    started = time.perf_counter()
    step = "push_construction_corpus"
    ct_root = str(plan.get("ct_root") or "")
    mode = str(plan.get("mode") or "invalid")
    plan["remote_verified"] = False
    for item in plan.get("files") or []:
        if isinstance(item, dict):
            item.pop("remote_sha256", None)
    if plan.get("ok") is not True or mode not in {"complete", "empty"} or not ct_root:
        detail = "REFUSED: local construction corpus plan is incomplete or invalid"
        receipt["blockers"].append(detail)
        receipt["construction_corpus"] = construction_corpus_receipt(plan)
        record(receipt, step, False, detail, time.perf_counter() - started)
        return False

    # Plain mkdir is the atomic freshness gate: unlike ``test`` followed by
    # ``mkdir -p``, two actors cannot both observe absence and then reuse one root.
    # push_packs has already created this cycle's parent directory.
    reserve = f"mkdir {shlex.quote(ct_root)}"
    reserve_result = ssh_run(cfg, reserve, TIMEOUT_SHORT)
    if not reserve_result["ok"]:
        detail = "could not reserve a fresh run-scoped CT corpus root: " + tail(
            reserve_result.get("stderr") or reserve_result.get("stdout") or "", 300
        )
        plan["blockers"] = [detail]
        receipt["blockers"].append(f"{step}: {detail}")
        receipt["construction_corpus"] = construction_corpus_receipt(plan)
        record(receipt, step, False, detail, time.perf_counter() - started, reserve)
        return False

    files = [item for item in (plan.get("files") or []) if isinstance(item, dict)]
    copy_errors: list[str] = []
    if files:
        parent_dirs = sorted(
            {str(PurePosixPath(str(item["remote_path"])).parent) for item in files}
        )
        mkdir = "mkdir -p " + " ".join(shlex.quote(path) for path in parent_dirs)
        mkdir_result = ssh_run(cfg, mkdir, TIMEOUT_SHORT)
        if not mkdir_result["ok"]:
            copy_errors.append(
                "could not create bundle subdirectories: "
                + tail(mkdir_result.get("stderr") or "", 240)
            )
        else:
            for item in files:
                local_path = Path(str(item.get("local_path") or ""))
                relative = str(item.get("relative_path") or "")
                if (
                    not local_path.is_file()
                    or local_path.is_symlink()
                    or local_path.stat().st_size != as_int(item.get("bytes"))
                    or sha256_file(local_path).casefold()
                    != str(item.get("sha256") or "").casefold()
                ):
                    copy_errors.append(f"{relative}: local bytes changed before transfer")
                    continue
                remote_path = str(item["remote_path"])
                copy = run_local(
                    [
                        *scp_argv(cfg),
                        str(local_path),
                        f"{cfg['target']}:{shlex.quote(remote_path)}",
                    ],
                    TIMEOUT_SCP,
                )
                if not copy["ok"]:
                    copy_errors.append(
                        f"{relative}: scp failed ({tail(copy.get('stderr') or '', 200)})"
                    )

    expected_paths = sorted(str(item.get("remote_path") or "") for item in files)
    remote_hashes = remote_sha256(cfg, expected_paths)
    remote_set = remote_file_set(cfg, ct_root)
    actual_paths = remote_set.get("paths") if isinstance(remote_set.get("paths"), list) else []
    set_ok = remote_set.get("ok") is True and actual_paths == expected_paths
    hash_mismatches: list[str] = []
    for item in files:
        remote_path = str(item.get("remote_path") or "")
        actual = str(remote_hashes.get("hashes", {}).get(remote_path) or "").casefold()
        item["remote_sha256"] = actual
        if actual != str(item.get("sha256") or "").casefold():
            hash_mismatches.append(str(item.get("relative_path") or remote_path))

    ok = (
        not copy_errors
        and remote_hashes.get("ok") is True
        and not hash_mismatches
        and set_ok
    )
    plan["remote_verified"] = ok
    if not ok:
        problems = list(copy_errors)
        if hash_mismatches:
            problems.append("remote hash mismatch: " + ", ".join(hash_mismatches[:6]))
        if not set_ok:
            missing = sorted(set(expected_paths) - set(actual_paths))
            extra = sorted(set(actual_paths) - set(expected_paths))
            problems.append(
                f"remote file set mismatch (missing={len(missing)}, extra={len(extra)})"
            )
            if remote_set.get("ok") is not True:
                problems.append(
                    "remote file-set query failed: "
                    + tail(remote_set.get("stderr") or "", 200)
                )
        if remote_hashes.get("ok") is not True:
            problems.append(
                "remote sha256sum failed: "
                + tail(remote_hashes.get("stderr") or "", 200)
            )
        plan["blockers"] = problems or ["construction corpus transfer verification failed"]
        receipt["blockers"].append(
            f"{step}: run-scoped corpus transfer failed; dataset builders were not started"
        )
    else:
        plan["blockers"] = []

    receipt["construction_corpus"] = construction_corpus_receipt(plan)
    detail = (
        f"{mode} run-scoped corpus; {len(files)} exact file(s) -> {ct_root}; "
        + ("sha256 + file set verified" if ok else "REFUSED: transfer evidence incomplete")
    )
    record(
        receipt,
        step,
        ok,
        detail,
        time.perf_counter() - started,
        f"fresh corpus root + scp -> {cfg.get('target')}:{ct_root}",
    )
    return ok


def corpus_binding_verdict(
    receipt: dict[str, Any], payload: dict[str, Any]
) -> tuple[bool, str]:
    """Prove a builder reports the exact corpus root and digest it was assigned."""
    expected = receipt.get("construction_corpus")
    if not isinstance(expected, dict):
        return False, "cycle receipt has no construction corpus contract"
    expected_root = str(expected.get("ct_root") or "")
    expected_mode = str(expected.get("mode") or "invalid")
    expected_digest = str(expected.get("bundle_sha256") or "").casefold()
    actual_root = str(payload.get("construction_corpus_root") or "")
    actual_digest = str(payload.get("construction_corpus_bundle_sha256") or "").casefold()
    actual_verified = payload.get("construction_corpus_verified")
    if not expected_root or actual_root != expected_root:
        return False, f"reported corpus root {actual_root!r} != assigned {expected_root!r}"
    if expected_mode == "complete":
        if actual_verified is not True:
            return False, "builder did not verify the assigned complete corpus bundle"
        if not expected_digest or actual_digest != expected_digest:
            return False, "builder corpus bundle digest does not match the cycle contract"
        return True, f"complete bundle {expected_digest} bound to {expected_root}"
    if expected_mode == "empty":
        if actual_verified is not False or actual_digest:
            return False, "builder did not preserve the assigned empty-corpus contract"
        return True, f"explicit empty corpus bound to {expected_root}"
    return False, f"unsupported cycle corpus mode {expected_mode!r}"


def step_build_dataset(
    receipt: dict[str, Any], cfg: dict[str, Any], ct_python: str, admitted: int,
    pack_dir: str,
    *,
    expected_rows_seen: int,
    expected_explicit_rows: int,
) -> bool:
    started = time.perf_counter()
    corpus_root = str((receipt.get("construction_corpus") or {}).get("ct_root") or "")
    if not corpus_root:
        receipt["blockers"].append("dataset build has no run-scoped construction corpus root")
        record(
            receipt,
            "build_dataset",
            False,
            "REFUSED: run-scoped construction corpus root is missing",
            time.perf_counter() - started,
        )
        return False
    command = remote_python(
        ct_python,
        f"{CT_TOOLS_DIR}/engel_build_training_dataset.py",
        "--packs-dir",
        pack_dir,
        "--quarantine-dir",
        pack_dir,
        "--training-target",
        "llm",
        "--corpus-root",
        corpus_root,
    )
    event("remote_step_started", step="build_dataset", command=command, timeout_seconds=TIMEOUT_DATASET_BUILD)
    result = ssh_run(cfg, command, TIMEOUT_DATASET_BUILD, long_run=True)
    summary = last_json_object(result.get("stdout") or "")
    raw_counts = summary.get("raw_counts") if isinstance(summary.get("raw_counts"), dict) else {}
    prompt_training_rows = raw_counts.get("prompt_training")

    dataset_receipt: dict[str, Any] = {}
    cat = ssh_run(cfg, f"cat {shlex.quote(CT_DATASET_RECEIPT)}", TIMEOUT_SHORT)
    if cat["ok"]:
        try:
            parsed = json.loads(cat.get("stdout") or "{}")
            if isinstance(parsed, dict):
                dataset_receipt = parsed
        except ValueError:
            dataset_receipt = {}
    if not raw_counts and isinstance(dataset_receipt.get("raw_counts"), dict):
        raw_counts = dataset_receipt["raw_counts"]
        prompt_training_rows = raw_counts.get("prompt_training")

    target_filter = summary.get("prompt_training_target_filter")
    if not isinstance(target_filter, dict):
        target_filter = dataset_receipt.get("prompt_training_target_filter")
    if not isinstance(target_filter, dict):
        target_filter = {}
    reported_target = str(
        summary.get("training_target", dataset_receipt.get("training_target")) or ""
    )
    target_bound = (
        reported_target == "llm"
        and target_filter.get("training_target") == "llm"
    )
    reported_rows_seen = as_int(target_filter.get("rows_seen"))
    explicitly_targeting = as_int(target_filter.get("rows_explicitly_targeting"))
    exact_pack_consumption = (
        int(expected_rows_seen) > 0
        and int(expected_explicit_rows) > 0
        and reported_rows_seen == int(expected_rows_seen)
        and explicitly_targeting == int(expected_explicit_rows)
    )

    corpus_payload = {
        key: summary.get(key, dataset_receipt.get(key))
        for key in (
            "construction_corpus_root",
            "construction_corpus_verified",
            "construction_corpus_bundle_sha256",
        )
    }
    corpus_bound, corpus_detail = corpus_binding_verdict(receipt, corpus_payload)

    prompt_training_consumed = not (admitted > 0 and not prompt_training_rows)
    receipt["dataset"] = {
        "built_at_utc": dataset_receipt.get("built_at_utc"),
        "train": as_int(summary.get("train", dataset_receipt.get("train"))),
        "val": as_int(summary.get("val", dataset_receipt.get("val"))),
        "prompt_training_rows": as_int(prompt_training_rows),
        "prompt_training_consumed": prompt_training_consumed,
        "expected_rows_seen": int(expected_rows_seen),
        "rows_seen": reported_rows_seen,
        "expected_rows_explicitly_targeting": int(expected_explicit_rows),
        "rows_explicitly_targeting": explicitly_targeting,
        "exact_pack_consumption": exact_pack_consumption,
        "training_target": reported_target,
        "prompt_training_target_filter": target_filter,
        "dataset_dir": str(summary.get("dataset", dataset_receipt.get("dataset_dir")) or ""),
        "construction_corpus_root": str(corpus_payload.get("construction_corpus_root") or ""),
        "construction_corpus_verified": corpus_payload.get("construction_corpus_verified") is True,
        "construction_corpus_bundle_sha256": str(
            corpus_payload.get("construction_corpus_bundle_sha256") or ""
        ),
    }

    ok = (
        bool(result["ok"])
        and corpus_bound
        and target_bound
        and exact_pack_consumption
        and prompt_training_consumed
    )
    detail_bits = [
        f"exit={result.get('returncode')}",
        f"train={receipt['dataset']['train']}",
        f"val={receipt['dataset']['val']}",
        f"prompt_training={prompt_training_rows}",
        f"rows_seen={reported_rows_seen}/{int(expected_rows_seen)}",
        f"rows_explicitly_targeting={explicitly_targeting}/{int(expected_explicit_rows)}",
        f"training_target={reported_target or '<missing>'}",
        f"corpus_binding={'verified' if corpus_bound else 'MISMATCH'}",
    ]
    if not result["ok"]:
        # The builder exits 1 when the training split is under 60 rows, so a nonzero exit
        # is a real refusal to ship a dataset, not a warning to step past.
        receipt["blockers"].append(
            f"CT dataset build failed (exit {result.get('returncode')}): "
            f"{tail(result.get('stderr') or result.get('stdout') or '', 300)}"
        )
    elif not corpus_bound:
        receipt["blockers"].append(
            "CT dataset build did not bind the assigned construction corpus: "
            + corpus_detail
        )
    elif not target_bound:
        receipt["blockers"].append(
            "CT SFT builder did not prove the required llm training-target filter"
        )
    elif not exact_pack_consumption:
        receipt["blockers"].append(
            "CT SFT builder did not consume the exact validated pack roster: "
            f"rows_seen={reported_rows_seen}/{int(expected_rows_seen)}, "
            "rows_explicitly_targeting="
            f"{explicitly_targeting}/{int(expected_explicit_rows)}"
        )
    elif not prompt_training_consumed:
        receipt["blockers"].append(
            f"{admitted} admitted pack rows were pushed but the rebuilt dataset reports "
            f"prompt_training={prompt_training_rows!r}: the builder's pack admit path did not "
            "consume them; LLM adapter training was refused"
        )
    detail_bits.append("stdout tail: " + tail(result.get("stdout") or result.get("stderr") or "", 900))
    record(receipt, "build_dataset", ok, "; ".join(detail_bits), time.perf_counter() - started, command)
    return ok


def step_slm_datasets(
    receipt: dict[str, Any],
    cfg: dict[str, Any],
    ct_python: str,
    pack_dir: str,
    dataset_dir: str,
    admitted: int,
    *,
    expected_rows_seen: int,
    expected_explicit_rows: int,
) -> bool:
    started = time.perf_counter()
    corpus_root = str((receipt.get("construction_corpus") or {}).get("ct_root") or "")
    if not corpus_root:
        receipt["blockers"].append("SLM dataset build has no run-scoped construction corpus root")
        record(
            receipt,
            "slm_datasets",
            False,
            "REFUSED: run-scoped construction corpus root is missing",
            time.perf_counter() - started,
        )
        return False
    command = remote_python(
        ct_python,
        f"{CT_TOOLS_DIR}/engel_slm_dataset_builder.py",
        "--root",
        CT_ROOT,
        "--packs-dir",
        pack_dir,
        "--quarantine-dir",
        pack_dir,
        "--training-target",
        "slm",
        "--out",
        dataset_dir,
        "--corpus-root",
        corpus_root,
    )
    event("remote_step_started", step="slm_datasets", command=command, timeout_seconds=TIMEOUT_SLM_DATASETS)
    result = ssh_run(cfg, command, TIMEOUT_SLM_DATASETS, long_run=True)
    summary = last_json_object(result.get("stdout") or "")
    corpus_bound, corpus_detail = corpus_binding_verdict(receipt, summary)
    target_filter = summary.get("prompt_training_target_filter")
    if not isinstance(target_filter, dict):
        target_filter = {}
    reported_target = str(summary.get("training_target") or "")
    target_bound = (
        reported_target == "slm"
        and target_filter.get("training_target") == "slm"
    )
    reported_rows_seen = as_int(target_filter.get("rows_seen"))
    explicitly_targeting = as_int(target_filter.get("rows_explicitly_targeting"))
    exact_pack_consumption = (
        int(expected_rows_seen) > 0
        and int(expected_explicit_rows) > 0
        and reported_rows_seen == int(expected_rows_seen)
        and explicitly_targeting == int(expected_explicit_rows)
    )
    datasets = summary.get("datasets") if isinstance(summary.get("datasets"), dict) else {}
    train_admit = datasets.get("train_admit") if isinstance(datasets.get("train_admit"), dict) else {}
    balance = train_admit.get("balance") if isinstance(train_admit.get("balance"), dict) else {}
    admitted_labels = as_int(balance.get("admit"))
    prompt_training_consumed = not (admitted > 0 and admitted_labels <= 0)
    receipt["slm"]["training_target"] = reported_target
    receipt["slm"]["prompt_training_target_filter"] = target_filter
    receipt["slm"]["prompt_training_consumed"] = prompt_training_consumed
    receipt["slm"]["expected_rows_seen"] = int(expected_rows_seen)
    receipt["slm"]["rows_seen"] = reported_rows_seen
    receipt["slm"]["expected_rows_explicitly_targeting"] = int(
        expected_explicit_rows
    )
    receipt["slm"]["rows_explicitly_targeting"] = explicitly_targeting
    receipt["slm"]["exact_pack_consumption"] = exact_pack_consumption
    receipt["slm"]["construction_corpus_root"] = str(
        summary.get("construction_corpus_root") or ""
    )
    receipt["slm"]["construction_corpus_verified"] = (
        summary.get("construction_corpus_verified") is True
    )
    receipt["slm"]["construction_corpus_bundle_sha256"] = str(
        summary.get("construction_corpus_bundle_sha256") or ""
    )
    ok = (
        bool(result["ok"])
        and corpus_bound
        and target_bound
        and exact_pack_consumption
        and prompt_training_consumed
    )
    if not result["ok"]:
        receipt["blockers"].append(
            f"SLM dataset build failed (exit {result.get('returncode')}): "
            f"{tail(result.get('stderr') or result.get('stdout') or '', 300)}"
        )
    elif not corpus_bound:
        receipt["blockers"].append(
            "SLM dataset build did not bind the assigned construction corpus: "
            + corpus_detail
        )
    elif not target_bound:
        receipt["blockers"].append(
            "CT SLM dataset builder did not prove the required slm training-target filter"
        )
    elif not exact_pack_consumption:
        receipt["blockers"].append(
            "CT SLM dataset builder did not consume the exact validated pack roster: "
            f"rows_seen={reported_rows_seen}/{int(expected_rows_seen)}, "
            "rows_explicitly_targeting="
            f"{explicitly_targeting}/{int(expected_explicit_rows)}"
        )
    elif not prompt_training_consumed:
        receipt["blockers"].append(
            f"{admitted} admitted slm-targeted pack row(s) were staged but the SLM "
            "builder did not emit any admitted train_admit label"
        )
    detail = (
        f"exit={result.get('returncode')}; isolated_output={dataset_dir}; "
        f"training_target={reported_target or '<missing>'}; "
        f"rows_seen={reported_rows_seen}/{int(expected_rows_seen)}; "
        f"explicit_target_rows={explicitly_targeting}/{int(expected_explicit_rows)}; "
        f"admitted_labels={admitted_labels}; "
        f"corpus_binding={'verified' if corpus_bound else 'MISMATCH'}; stdout tail: "
    ) + tail(
        result.get("stdout") or result.get("stderr") or "", 700
    )
    record(receipt, "slm_datasets", ok, detail, time.perf_counter() - started, command)
    return ok


def step_slm_train(
    receipt: dict[str, Any],
    cfg: dict[str, Any],
    ct_python: str,
    tasks: str,
    candidate_dir: str,
    dataset_dir: str,
) -> bool:
    started = time.perf_counter()
    run_id = str(receipt.get("run_id") or "")
    candidate_report_path = f"{candidate_dir}/LATEST_TRAINING.json"
    command = remote_python(
        ct_python,
        f"{CT_TOOLS_DIR}/engel_slm_trainer.py",
        "--root",
        CT_ROOT,
        "--tasks",
        tasks,
        "--data-dir",
        dataset_dir,
        "--out-dir",
        candidate_dir,
        "--incumbent-dir",
        CT_SLM_DIR,
        "--run-id",
        run_id,
    )
    event("remote_step_started", step="slm_train", command=command, timeout_seconds=TIMEOUT_SLM_TRAIN)
    result = ssh_run(cfg, command, TIMEOUT_SLM_TRAIN, long_run=True)

    report = read_remote_json(cfg, candidate_report_path)
    requested = list(slm_roster.normalize_tasks(tasks))
    report_problems, _, artifacts = validate_slm_training_report(
        report,
        run_id=run_id,
        candidate_dir=candidate_dir,
        dataset_dir=dataset_dir,
        requested_tasks=requested,
        cycle_started_at_utc=str(receipt.get("started_at_utc") or ""),
    )
    tasks_map: dict[str, Any] = {}
    for entry in report.get("results") or []:
        if not isinstance(entry, dict):
            continue
        metrics = entry.get("metrics") if isinstance(entry.get("metrics"), dict) else {}
        # `accuracy` is carried alongside macro_f1 because the baseline is a majority-class
        # ACCURACY and the lift is measured against it. Reporting macro_f1 next to that
        # baseline alone reads as "worse than guessing" on a model that in fact beat the
        # baseline by 6.6 points (intent_router, 20260801: F1 0.908, accuracy 0.984 vs
        # baseline 0.917). A number presented against the wrong reference is a false alarm,
        # and this receipt is what the Training panel shows.
        tasks_map[str(entry.get("task") or "unknown")] = {
            "ok": entry.get("selected_ok") is True and entry.get("ok") is True,
            "candidate_ok": entry.get("candidate_ok") is True,
            "selected_ok": entry.get("selected_ok") is True,
            "selected_head": entry.get("selected_head"),
            "macro_f1": metrics.get("macro_f1"),
            "accuracy": metrics.get("accuracy"),
            "baseline": metrics.get("majority_baseline_accuracy"),
            "lift": metrics.get("lift_over_baseline"),
            "rows": entry.get("train_rows"),
            "class_counts": entry.get("class_counts"),
            "min_per_class": entry.get("min_per_class"),
            "status": entry.get("status"),
            "previous": entry.get("previous"),
            "delta_vs_previous": entry.get("delta_vs_previous"),
        }
    receipt["slm"]["tasks"] = tasks_map
    receipt["slm"]["roster"] = report.get("roster") or []
    receipt["slm"]["candidate_dir"] = candidate_dir
    receipt["slm"]["dataset_dir"] = dataset_dir
    receipt["slm"]["candidate_report_path"] = candidate_report_path
    receipt["slm"]["candidate_artifacts"] = sorted(artifacts)
    receipt["slm"]["requested_tasks"] = requested
    receipt["slm"]["report_binding_problems"] = report_problems
    # (2026-08-07 review) Incumbent regressions must be VISIBLE where the operator reads,
    # not buried in the CT receipt: the first instrumented run shipped 5 of 7 style-check
    # heads measurably worse (>0.05 macro_f1) than the artifacts they replaced, and only
    # an ssh session could see it. Advisory, never a blocker -- the deltas are one eval
    # split and the capability gate owns rollback -- but a shipped head that measures
    # worse than what it replaced belongs in the cycle receipt and the step detail.
    incumbent_regressions: list[dict[str, Any]] = []
    for entry in report.get("results") or []:
        if not isinstance(entry, dict):
            continue
        task_name = str(entry.get("task") or "unknown")
        delta = (entry.get("delta_vs_previous") or {}) if isinstance(entry.get("delta_vs_previous"), dict) else {}
        macro_delta = delta.get("macro_f1")
        if (
            entry.get("selected_head") == "candidate"
            and entry.get("selected_ok") is True
            and isinstance(macro_delta, (int, float))
            and macro_delta < -0.05
        ):
            incumbent_regressions.append(
                {"task": task_name, "delta_macro_f1": macro_delta}
            )
        for check_name, check in (entry.get("per_check") or {}).items():
            if (
                not isinstance(check, dict)
                or check.get("selected_head") != "candidate"
                or not check.get("shipped")
            ):
                continue
            check_delta = check.get("delta_vs_previous_macro_f1")
            if isinstance(check_delta, (int, float)) and check_delta < -0.05:
                incumbent_regressions.append(
                    {"task": f"{task_name}:{check_name}", "delta_macro_f1": check_delta}
                )
    receipt["slm"]["incumbent_regressions"] = incumbent_regressions
    missing = [task for task in requested if task not in tasks_map]
    below_gate = [
        task for task in requested if task in tasks_map and tasks_map[task].get("ok") is not True
    ]
    trained_ok = sorted(name for name, value in tasks_map.items() if value.get("ok"))

    ok = bool(
        result["ok"]
        and tasks_map
        and not missing
        and not below_gate
        and not report_problems
        and len(artifacts) == len(requested)
    )
    if not result["ok"]:
        receipt["blockers"].append(
            f"SLM training failed (exit {result.get('returncode')}): "
            f"{tail(result.get('stderr') or result.get('stdout') or '', 300)}"
        )
    if missing:
        receipt["blockers"].append(
            f"SLM training receipt has no entry for requested task(s) {missing}: "
            "the roster did not train what this cycle asked for"
        )
    if below_gate:
        receipt["blockers"].append(
            f"SLM task(s) stayed below their selected-artifact gate: {below_gate}; "
            "the staged roster is partial and will not be promoted"
        )
    if report_problems:
        receipt["blockers"].append(
            "SLM staged report is not bound to this cycle: "
            + "; ".join(report_problems[:5])
        )
    detail = (
        f"exit={result.get('returncode')}; staged={candidate_dir}; trained_ok={trained_ok}; "
        f"below_gate={report.get('below_gate')}; tasks_reported={sorted(tasks_map)}; "
        f"binding_problems={len(report_problems)}"
    )
    if incumbent_regressions:
        worst = min(incumbent_regressions, key=lambda item: item["delta_macro_f1"])
        detail += (
            f"; WARNING {len(incumbent_regressions)} shipped head(s) measure worse than "
            f"the incumbent they replaced (worst {worst['task']} {worst['delta_macro_f1']})"
        )
    record(receipt, "slm_train", ok, detail, time.perf_counter() - started, command)
    return ok


def step_slm_verify(
    receipt: dict[str, Any], cfg: dict[str, Any], ct_python: str, candidate_dir: str
) -> bool:
    started = time.perf_counter()
    report_path = f"{candidate_dir}/LATEST_TRAINING.json"
    before = remote_sha256(cfg, [report_path])
    verify_command = remote_python(
        ct_python, f"{CT_TOOLS_DIR}/verify_engel_slm.py", "--root", CT_ROOT
    )
    # The verifier resolves the same ENGEL_SLM_MODEL_DIR contract as the serving
    # runtime. Point it at this cycle's candidate, never the live CT roster.
    command = "env " + shlex.quote(f"ENGEL_SLM_MODEL_DIR={candidate_dir}") + " " + verify_command
    event("remote_step_started", step="slm_verify", command=command, timeout_seconds=TIMEOUT_SLM_VERIFY)
    result = ssh_run(cfg, command, TIMEOUT_SLM_VERIFY, long_run=True)
    after = remote_sha256(cfg, [report_path])
    before_hash = str(before.get("hashes", {}).get(report_path) or "")
    after_hash = str(after.get("hashes", {}).get(report_path) or "")
    skipped = "SKIPPED (not runnable here)" in str(result.get("stdout") or "")
    stable_report = bool(
        before.get("ok")
        and after.get("ok")
        and before_hash
        and before_hash == after_hash
    )
    ok = bool(result["ok"] and stable_report and not skipped)
    if ok:
        receipt.setdefault("slm", {})["verified_report_sha256"] = after_hash
    if not ok:
        receipt["blockers"].append(
            "SLM candidate gate FAILED: the staged roster is not trustworthy and was not "
            "promoted to the ROG mirror. "
            + (
                "the report changed during verification"
                if not stable_report
                else "artifact checks were skipped on CT"
                if skipped
                else tail(result.get("stdout") or result.get("stderr") or "", 300)
            )
        )
    detail = (
        f"exit={result.get('returncode')}; candidate={candidate_dir}; "
        f"report_stable={stable_report}; skipped={skipped}; "
        + tail(result.get("stdout") or result.get("stderr") or "", 900)
    )
    record(receipt, "slm_verify", ok, detail, time.perf_counter() - started, command)
    return ok


def step_capability_gate(receipt: dict[str, Any], snapshot_taken: bool) -> bool:
    """Observe end-to-end chat capability without attributing it to advisory SLM heads.

    Every number the cycle produced before this one is blind to skill: LoRA `val_loss` is
    likelihood on the training distribution, and each SLM head's macro_f1 is scored on a
    split of the corpus it was fitted from. A model can improve both and still ground
    fewer claims, so promotion needed an outside measurement.

    The generic chat response is produced by the routed LLM; SLM roster outputs are
    advisory and do not causally determine that response.  This monitor can block a
    cycle on end-to-end health, but it must never claim that an SLM promotion caused the
    change or roll SLM bytes back on that basis."""
    started = time.perf_counter()
    try:
        sys.path.insert(0, str(ROOT / "tools"))
        import engel_capability_eval as cap
    except Exception as exc:  # pragma: no cover - import shape only
        record(receipt, "capability_gate", False,
               f"capability eval unavailable: {type(exc).__name__}: {exc}",
               time.perf_counter() - started)
        receipt["blockers"].append("capability gate could not run; promotion is unverified")
        return False

    result = cap.run_eval()
    baseline = cap._load(cap.BASELINE)
    comparison = cap.compare(result, baseline)
    result["comparison"] = comparison

    cap.REPORT_DIR.mkdir(parents=True, exist_ok=True)
    cap.LATEST.write_text(json.dumps(result, indent=2), encoding="utf-8")
    receipt["capability"] = {
        "overall": result.get("overall"),
        "skills": result.get("skills"),
        "comparison": comparison,
        "receipt": str(cap.LATEST),
        "causal_to_slm_promotion": False,
        "rolled_back": False,
        "snapshot_available": bool(snapshot_taken),
    }

    generation_dead = all(
        str(row.get("why", "")).startswith("generation failed") for row in result.get("rows") or []
    ) and bool(result.get("rows"))
    regressions = comparison.get("regressions") or []

    if regressions and not generation_dead:
        # (2026-08-07) CONFIRM BEFORE ROLLBACK. Each skill is measured on ~3 prompts, and
        # the first live run reversed a whole roster promotion over a single wobbly answer
        # (grounded_citation 2/3 -> 1/3) in a lane where every promoted head is advisory.
        # A rollback is an ACTION; noise must not trigger it. One immediate re-measure:
        # only a skill that regresses in BOTH runs is treated as real. A genuine
        # regression is deterministic enough to show twice; a wobble is not.
        rerun = cap.run_eval()
        rerun_comparison = cap.compare(rerun, baseline)
        first_run = {str(entry.get("skill")) for entry in regressions}
        second_run = {
            str(entry.get("skill")) for entry in rerun_comparison.get("regressions") or []
        }
        confirmed = sorted(first_run & second_run)
        receipt["capability"]["confirmation_run"] = {
            "overall": rerun.get("overall"),
            "regressions": sorted(second_run),
        }
        receipt["capability"]["regressions_first_run"] = sorted(first_run)
        receipt["capability"]["regressions_confirmed"] = confirmed
        if confirmed:
            regressions = [
                entry for entry in regressions if str(entry.get("skill")) in confirmed
            ]
        else:
            receipt["capability"]["regression_dismissed_as_noise"] = True
            regressions = []

    if generation_dead:
        detail = "INCONCLUSIVE: the chat lane answered nothing, so capability could not be measured"
        receipt["blockers"].append(
            "chat capability could not be measured (the routed LLM returned nothing); "
            "SLM selection was left to its direct artifact gate"
        )
    elif regressions:
        names = ", ".join(f"{r['skill']} {r['before']}->{r['after']}" for r in regressions[:3])
        detail = f"ROUTED CHAT REGRESSION (not causally attributable to advisory SLM): {names}"
        receipt["blockers"].append(
            f"routed chat capability regressed ({names}); SLM bytes were not changed by this monitor"
        )
    else:
        detail = (
            f"capability held: overall={result.get('overall')} "
            f"delta={comparison.get('overall_delta')}"
        )
        record(receipt, "capability_gate", True, detail, time.perf_counter() - started)
        return True

    detail += "; no SLM rollback attempted because this measurement is not causal"
    record(receipt, "capability_gate", False, detail, time.perf_counter() - started)
    return False


def step_mirror_back(
    receipt: dict[str, Any],
    cfg: dict[str, Any],
    gate_passed: bool,
    candidate_dir: str,
) -> bool:
    started = time.perf_counter()
    if not gate_passed:
        # runtime/slm_models is read by engel_slm_runtime in the live chat hot path, so an
        # ungated roster must not be copied into it just because it exists on CT.
        detail = (
            "REFUSED: the roster gate did not pass, so the live ROG mirror "
            f"({SLM_MIRROR_DIR}) was left on its previous verified artifacts"
        )
        record(receipt, "mirror_back", False, detail, time.perf_counter() - started)
        return False
    run_id = str(receipt.get("run_id") or "")
    requested = receipt.get("slm", {}).get("requested_tasks") or []
    report_path = f"{candidate_dir}/LATEST_TRAINING.json"
    report = read_remote_json(cfg, report_path)
    dataset_dir = str(receipt.get("slm", {}).get("dataset_dir") or "")
    problems, eligible_tasks, artifact_hashes = validate_slm_training_report(
        report,
        run_id=run_id,
        candidate_dir=candidate_dir,
        dataset_dir=dataset_dir,
        requested_tasks=requested,
        cycle_started_at_utc=str(receipt.get("started_at_utc") or ""),
    )
    remote_files = [*artifact_hashes, report_path]
    remote_hashes = remote_sha256(cfg, remote_files)
    if not remote_hashes.get("ok"):
        problems.append("remote sha256 enumeration failed")
    hashes = remote_hashes.get("hashes") if isinstance(remote_hashes.get("hashes"), dict) else {}
    missing_remote_hashes = [path for path in remote_files if path not in hashes]
    if missing_remote_hashes:
        problems.append(
            "remote sha256 omitted: "
            + ", ".join(PurePosixPath(path).name for path in missing_remote_hashes)
        )
    for remote, report_digest in artifact_hashes.items():
        if str(hashes.get(remote) or "").casefold() != report_digest:
            problems.append(f"{PurePosixPath(remote).name}: remote bytes do not match the report")
    verified_report_hash = str(receipt.get("slm", {}).get("verified_report_sha256") or "")
    current_report_hash = str(hashes.get(report_path) or "")
    if not verified_report_hash or current_report_hash != verified_report_hash:
        problems.append("candidate report changed after the CT artifact gate")

    require_repo_path(SLM_MIRROR_DIR)
    local_stage = SLM_MIRROR_DIR.with_name(f"{SLM_MIRROR_DIR.name}_candidate_{run_id}")
    require_repo_path(local_stage)
    if local_stage.exists():
        problems.append(f"unique local candidate directory already exists: {local_stage}")
    if problems:
        receipt["blockers"].append("mirror_back: " + "; ".join(problems[:6]))
        record(
            receipt,
            "mirror_back",
            False,
            "REFUSED before local mutation: " + "; ".join(problems[:6]),
            time.perf_counter() - started,
        )
        return False

    local_stage.mkdir(parents=False, exist_ok=False)
    downloaded: list[Path] = []
    for remote in remote_files:
        local = local_stage / PurePosixPath(remote).name
        copy = run_local(
            [*scp_argv(cfg), f"{cfg['target']}:{shlex.quote(remote)}", str(local)],
            TIMEOUT_SCP,
        )
        if not copy.get("ok") or not local.is_file():
            problems.append(
                f"{local.name}: scp failed ({tail(copy.get('stderr') or '', 160)})"
            )
            continue
        want = str(hashes.get(remote) or "").casefold()
        got = sha256_file(local).casefold()
        if not want or got != want:
            problems.append(f"{local.name}: sha256 mismatch after copy")
            continue
        downloaded.append(local)

    expected_local_hashes = {
        PurePosixPath(remote).name: str(hashes[remote]).casefold()
        for remote in remote_files
        if remote in hashes
    }
    problems.extend(verify_local_slm_release(local_stage, expected_local_hashes))
    try:
        local_report = json.loads(
            (local_stage / "LATEST_TRAINING.json").read_text(encoding="utf-8")
        )
    except (OSError, ValueError) as exc:
        local_report = {}
        problems.append(f"downloaded report is unreadable: {type(exc).__name__}: {exc}")
    if isinstance(local_report, dict):
        local_problems, local_tasks, local_artifacts = validate_slm_training_report(
            local_report,
            run_id=run_id,
            candidate_dir=candidate_dir,
            dataset_dir=dataset_dir,
            requested_tasks=requested,
            cycle_started_at_utc=str(receipt.get("started_at_utc") or ""),
        )
        problems.extend("downloaded " + item for item in local_problems)
        if local_tasks != eligible_tasks or local_artifacts != artifact_hashes:
            problems.append("downloaded report roster differs from the gated remote roster")
    else:
        problems.append("downloaded report is not a JSON object")

    if problems:
        receipt["blockers"].append("mirror_back: " + "; ".join(problems[:6]))
        receipt["slm"]["candidate_local_dir"] = str(local_stage)
        record(
            receipt,
            "mirror_back",
            False,
            f"downloaded {len(downloaded)}/{len(remote_files)} files; live mirror unchanged; "
            + "; ".join(problems[:6]),
            time.perf_counter() - started,
            f"scp exact staged roster from {candidate_dir}",
        )
        return False

    promotion = atomic_promote_slm_release(
        local_stage,
        SLM_MIRROR_DIR,
        run_id=run_id,
        expected_hashes=expected_local_hashes,
    )
    ok = promotion.get("ok") is True
    receipt["slm"].update(
        {
            "mirrored": [str(SLM_MIRROR_DIR / name) for name in sorted(expected_local_hashes)],
            "mirrored_eligible_tasks": eligible_tasks,
            "candidate_local_dir": str(local_stage),
            "backup": promotion.get("backup"),
            "snapshot": promotion.get("backup"),
            "rolled_back": promotion.get("rolled_back") is True,
            "release_report_sha256": expected_local_hashes.get("LATEST_TRAINING.json"),
            "reload_required": ok,
            "reload_acknowledged": False,
        }
    )
    if not ok:
        promotion_problems = [str(item) for item in promotion.get("problems") or []]
        receipt["blockers"].append(
            "mirror_back atomic promotion failed: " + "; ".join(promotion_problems[:6])
        )
        detail = "atomic promotion failed; " + "; ".join(promotion_problems[:6])
    else:
        detail = (
            f"atomically installed {len(expected_local_hashes)} verified file(s) -> "
            f"{SLM_MIRROR_DIR}; backup={promotion.get('backup') or 'none'}; "
            "this is an on-disk mirror update, not an in-process serving activation"
        )
    record(
        receipt,
        "mirror_back",
        ok,
        detail,
        time.perf_counter() - started,
        f"scp exact staged roster from {candidate_dir}; atomic directory swap",
    )
    return ok


def step_slm_reload_pending(receipt: dict[str, Any]) -> bool:
    """Record the boundary between an on-disk release and in-process serving.

    ``EngelSlmRuntime.reload`` is hash-bound, but this batch orchestrator does not own the
    long-lived app runtime object and has no authenticated in-process control channel.
    Restarting a service to approximate reload would be a separate operator action.  The
    cycle therefore stays PARTIAL until the owning process acknowledges the exact report
    hash; swapping a directory is never reported as a serving activation.
    """
    started = time.perf_counter()
    report_hash = str(receipt.get("slm", {}).get("release_report_sha256") or "")
    receipt.setdefault("slm", {}).update(
        {
            "reload_required": True,
            "reload_acknowledged": False,
            "serving_report_sha256": None,
        }
    )
    detail = (
        "PENDING: verified SLM bytes are installed in the local mirror directory, but "
        "the owning serving process has not acknowledged a hash-bound reload"
        + (f" of report {report_hash}" if report_hash else "")
        + "; no service restart or runtime mutation was attempted"
    )
    receipt["blockers"].append(
        "SLM serving reload pending: filesystem integrity is proven, but the active "
        "process may still hold the previous in-memory roster"
    )
    record(receipt, "slm_reload", False, detail, time.perf_counter() - started)
    return False


def step_llm_preflight(
    receipt: dict[str, Any], cfg: dict[str, Any], ct_python: str
) -> bool:
    """Prove the fixed CT246 Qwen source, dataset, and LoRA environment are ready."""
    started = time.perf_counter()
    command = remote_python(
        ct_python,
        f"{CT_TOOLS_DIR}/{LORA_PROOF_TOOL.name}",
        "--preflight-only",
        "--origin",
        "engel_real_training_cycle",
    )
    event(
        "remote_step_started",
        step="llm_preflight",
        command=command,
        timeout_seconds=TIMEOUT_LLM_PREFLIGHT,
    )
    result = ssh_run(cfg, command, TIMEOUT_LLM_PREFLIGHT, long_run=True)
    proof = read_remote_json(cfg, CT_LORA_PREFLIGHT_RECEIPT)
    blockers = proof.get("blockers") if isinstance(proof.get("blockers"), list) else []
    receipt["llm"]["preflight"] = {
        "ok": proof.get("ok") is True,
        "model": str(proof.get("model") or ""),
        "train_records": as_int(proof.get("train_records")),
        "val_records": as_int(proof.get("val_records")),
        "blockers": [str(item) for item in blockers],
        "receipt_path": str(proof.get("receipt_path") or CT_LORA_PREFLIGHT_RECEIPT),
    }
    ok = bool(result.get("ok") and proof.get("ok") is True)
    if not ok:
        detail = "; ".join(str(item) for item in blockers) or tail(
            result.get("stderr") or result.get("stdout") or "", 400
        )
        receipt["blockers"].append(
            "local LLM preflight failed; no adapter weights were trained: "
            + (detail or "the CT receipt was missing or invalid")
        )
    record(
        receipt,
        "llm_preflight",
        ok,
        (
            f"model={proof.get('model') or 'not recorded'}; "
            f"train={as_int(proof.get('train_records'))}; "
            f"val={as_int(proof.get('val_records'))}; blockers={len(blockers)}"
        ),
        time.perf_counter() - started,
        command,
    )
    return ok


def step_llm_train(
    receipt: dict[str, Any], cfg: dict[str, Any], ct_python: str, approval: str
) -> bool:
    """Train and evaluate one new adapter; never deploy or promote it."""
    started = time.perf_counter()
    command = remote_python(
        ct_python,
        f"{CT_TOOLS_DIR}/{LORA_PROOF_TOOL.name}",
        "--approval",
        approval,
        "--origin",
        "engel_real_training_cycle",
        # (2026-08-07) 3600s at seq 1536 on CT CPU buys ~15 optimizer steps (~120 samples,
        # <0.1 epoch) -- real movement needs more, and with adapter-lineage resume each
        # budget now ACCUMULATES instead of re-learning from zero. 10800s ≈ 0.2-0.3 epoch
        # per cycle; TIMEOUT_LLM_TRAIN covers budget + eval + dataset with headroom.
        "--training-budget-seconds",
        "10800",
        "--eval-timeout-seconds",
        "7200",
    )
    event(
        "remote_step_started",
        step="llm_train",
        command="<approval redacted>",
        timeout_seconds=TIMEOUT_LLM_TRAIN,
    )
    result = ssh_run(cfg, command, TIMEOUT_LLM_TRAIN, long_run=True)
    proof = read_remote_json(cfg, CT_LORA_PROOF_RECEIPT)
    adapter_files = (
        proof.get("adapter_files") if isinstance(proof.get("adapter_files"), list) else []
    )
    adapter_weight_present = any(
        isinstance(item, dict)
        and item.get("relative_path") == "adapter_model.safetensors"
        and as_int(item.get("bytes")) > 0
        for item in adapter_files
    )
    llm_summary = {
        "ok": proof.get("ok") is True,
        "base_model": str(proof.get("base_model") or ""),
        "new_adapter_trained": proof.get("new_adapter_trained") is True,
        "new_adapter_path": str(proof.get("new_adapter_path") or ""),
        "adapter_weight_present": adapter_weight_present,
        "validation_loss_before": proof.get("validation_loss_before"),
        "validation_loss_after": proof.get("validation_loss_after"),
        "validation_loss_delta": proof.get("validation_loss_delta"),
        "model_weight_improvement_claimed": proof.get("model_weight_improvement_claimed")
        is True,
        "auto_deployed": proof.get("auto_deployed") is True,
        "receipt_path": CT_LORA_PROOF_RECEIPT,
        "error": str(proof.get("error") or ""),
        # (2026-08-07 review) Mirror the honesty instrumentation into THIS receipt: the
        # UI and the operator read the cycle receipt on ROG, and the coverage/contrast/
        # lineage numbers lived only in the CT proof receipt -- judging a run without
        # them means judging a delta with no idea how much corpus bought it.
        "coverage": proof.get("coverage"),
        "negative_loss_delta": proof.get("negative_loss_delta"),
        "val_minus_negative_delta": proof.get("val_minus_negative_delta"),
        "adapter_weight_norm_after": proof.get("adapter_weight_norm_after"),
        "resumed_from": proof.get("resumed_from"),
        "adapter_lineage": proof.get("adapter_lineage"),
        "adapter_pointer": proof.get("adapter_pointer"),
    }
    receipt["llm"].update(llm_summary)
    ok = bool(
        result.get("ok")
        and llm_summary["ok"]
        and llm_summary["new_adapter_trained"]
        and adapter_weight_present
        and not llm_summary["auto_deployed"]
    )
    if not ok:
        reason = llm_summary["error"] or tail(
            result.get("stderr") or result.get("stdout") or "", 400
        )
        receipt["blockers"].append(
            "local LLM adapter training/evaluation did not pass: "
            + (reason or "the CT proof receipt was missing or incomplete")
        )
    detail = (
        f"exit={result.get('returncode')}; trained={llm_summary['new_adapter_trained']}; "
        f"adapter_weight={adapter_weight_present}; "
        f"val_delta={llm_summary['validation_loss_delta']}; "
        f"auto_deployed={llm_summary['auto_deployed']}"
    )
    record(
        receipt,
        "llm_train",
        ok,
        detail,
        time.perf_counter() - started,
        command.replace(approval, "<APPROVAL_REDACTED>"),
    )
    return ok


def plan_remote_steps(receipt: dict[str, Any], cfg: dict[str, Any], args: argparse.Namespace, packs: dict[str, Any]) -> None:
    """Record what a real run WOULD do, plainly labelled so nobody reads it as a result."""
    planned: list[tuple[str, str]] = []
    if not args.no_push_tools:
        planned.append(
            ("push_tools", f"scp {len(CT_TOOL_FILES)} tool(s) -> {cfg['target']}:{CT_TOOLS_DIR} + sha256 verify")
        )
    pack_stage = str(receipt["packs"]["ct_stage_dir"])
    planned.append(
        (
            "push_packs",
            f"one batched scp of {packs['files']} pack segment(s) + "
            f"{int(receipt['packs'].get('transfer_evidence_file_count') or 0)} "
            "immutable receipt/sidecar file(s) -> "
            f"{cfg['target']}:{pack_stage} + sha256 verify",
        )
    )
    corpus = receipt.get("construction_corpus") if isinstance(receipt.get("construction_corpus"), dict) else {}
    corpus_root = str(corpus.get("ct_root") or ct_construction_corpus_dir(str(receipt["run_id"])))
    corpus_mode = str(corpus.get("mode") or "empty")
    corpus_files = corpus.get("files") if isinstance(corpus.get("files"), list) else []
    corpus_digest = str(corpus.get("bundle_sha256") or "<empty>")
    planned.append(
        (
            "push_construction_corpus",
            f"reserve fresh {corpus_root}; {corpus_mode} bundle with {len(corpus_files)} "
            f"exact file(s); bundle_sha256={corpus_digest}; sha256 + remote file-set verify",
        )
    )
    targets = normalize_training_targets(getattr(args, "targets", "slm"))
    if "llm" in targets:
        planned.append(("build_dataset", planned_python(
            f"{CT_TOOLS_DIR}/engel_build_training_dataset.py", "--packs-dir", pack_stage,
            "--quarantine-dir", pack_stage,
            "--training-target", "llm",
            "--corpus-root", corpus_root,
        )))
    if "slm" in targets:
        candidate_dir = ct_slm_candidate_dir(str(receipt["run_id"]))
        slm_dataset_dir = ct_slm_dataset_dir(str(receipt["run_id"]))
        planned.append(
            ("slm_datasets", planned_python(
                f"{CT_TOOLS_DIR}/engel_slm_dataset_builder.py", "--root", CT_ROOT,
                "--packs-dir", pack_stage,
                "--quarantine-dir", pack_stage,
                "--training-target", "slm",
                "--out", slm_dataset_dir,
                "--corpus-root", corpus_root,
            ))
        )
        planned.append(
            (
                "slm_train",
                planned_python(
                    f"{CT_TOOLS_DIR}/engel_slm_trainer.py",
                    "--root",
                    CT_ROOT,
                    "--tasks",
                    args.slm_tasks,
                    "--data-dir",
                    slm_dataset_dir,
                    "--out-dir",
                    candidate_dir,
                    "--incumbent-dir",
                    CT_SLM_DIR,
                    "--run-id",
                    str(receipt["run_id"]),
                ),
            )
        )
        planned.append(
            (
                "slm_verify",
                f"ENGEL_SLM_MODEL_DIR={candidate_dir} "
                + planned_python(f"{CT_TOOLS_DIR}/verify_engel_slm.py", "--root", CT_ROOT),
            )
        )
        planned.append(
            (
                "mirror_back",
                f"scp exact hash-bound files from {cfg['target']}:{candidate_dir} -> "
                f"local staging; atomic directory swap -> {SLM_MIRROR_DIR}",
            )
        )
        planned.append(
            (
                "slm_reload",
                "PENDING external in-process EngelSlmRuntime.reload(expected_report_sha256); "
                "no service restart is inferred",
            )
        )
    if "llm" in targets:
        planned.append(
            (
                "llm_preflight",
                planned_python(
                    f"{CT_TOOLS_DIR}/{LORA_PROOF_TOOL.name}",
                    "--preflight-only",
                    "--origin",
                    "engel_real_training_cycle",
                ),
            )
        )
        planned.append(
            (
                "llm_train",
                planned_python(
                    f"{CT_TOOLS_DIR}/{LORA_PROOF_TOOL.name}",
                    "--approval",
                    "<EXACT_APPROVAL_REQUIRED>",
                    "--origin",
                    "engel_real_training_cycle",
                ),
            )
        )
    for step, command in planned:
        record(receipt, step, True, "PLANNED (--dry-run, not executed)", 0.0, command)


def run_cycle(args: argparse.Namespace) -> dict[str, Any]:
    global _ACTIVE_CYCLE_DEADLINE_MONOTONIC
    run_id = unique_cycle_run_id()
    cfg = resolve_ssh()
    targets = normalize_training_targets(getattr(args, "targets", "slm"))
    runtime_contract = runtime_budget.load_contract()
    cycle_runtime_seconds = runtime_budget.deadline_seconds(
        targets, runtime_contract
    )
    cycle_started_monotonic = time.monotonic()
    _ACTIVE_CYCLE_DEADLINE_MONOTONIC = (
        cycle_started_monotonic + cycle_runtime_seconds
    )
    receipt: dict[str, Any] = {
        "schema": "engel_real_training_cycle_v1",
        "run_id": run_id,
        "started_at_utc": iso_now(),
        "finished_at_utc": None,
        "status": "FAIL",
        "dry_run": bool(args.dry_run),
        "mode": "dry_run" if args.dry_run else ("no_ct" if args.no_ct else "full"),
        "ct_target": cfg.get("target"),
        "targets": list(targets),
        "runtime_contract": {
            "schema": runtime_contract["schema"],
            "contract_path": str(runtime_budget.CONTRACT_PATH.resolve()),
            "contract_sha256": sha256_file(runtime_budget.CONTRACT_PATH),
            "whole_cycle_deadline_seconds": cycle_runtime_seconds,
            "termination_grace_seconds": runtime_budget.termination_grace_seconds(
                runtime_contract
            ),
            "deadline_at_utc": (
                datetime.now(timezone.utc)
                + timedelta(seconds=cycle_runtime_seconds)
            ).isoformat(),
            "child_timeouts_clamped_to_deadline": True,
        },
        "steps": [],
        "packs": {
            "files": 0,
            "physical_rows": 0,
            "logical_rows": 0,
            "rows": 0,
            "admitted": 0,
            "explicit_rows_by_target": {target: 0 for target in targets},
            "admitted_by_target": {target: 0 for target in targets},
            "target_exclusions": {
                "missing_or_malformed": 0,
                "not_selected": 0,
            },
            "pushed": 0,
            "ct_stage_dir": f"{CT_CYCLE_RUN_DIR}/{run_id}/packs",
        },
        "construction_corpus": {
            "mode": "unverified",
            "local_root": str(ROOT / "memory" / "training" / "construction_env"),
            "ct_root": ct_construction_corpus_dir(run_id),
            "bundle_sha256": "",
            "local_verified": False,
            "remote_verified": False,
            "files": [],
            "blockers": [],
        },
        "dataset": {
            "status": "not_selected" if "llm" not in targets else "pending",
            "training_target": "llm" if "llm" in targets else "",
            "built_at_utc": None,
            "train": 0,
            "val": 0,
            "prompt_training_rows": 0,
            "expected_rows_seen": 0,
            "rows_seen": 0,
            "expected_rows_explicitly_targeting": 0,
            "rows_explicitly_targeting": 0,
            "exact_pack_consumption": False,
            "dataset_dir": "",
        },
        "slm": {
            "tasks": {},
            "mirrored": [],
            "candidate_dir": ct_slm_candidate_dir(run_id),
            "dataset_dir": ct_slm_dataset_dir(run_id),
            "serving_dir_written_during_training": False,
        },
        "llm": {
            "target_name": "Engel local LLM adapter (Qwen2.5 1.5B source)",
            "preflight": {},
            "new_adapter_trained": False,
            "auto_deployed": False,
        },
        "lora_next_steps": lora_next_steps(cfg),
        "blockers": [],
        "warnings": [],
    }
    event(
        "cycle_started",
        run_id=run_id,
        mode=receipt["mode"],
        target=cfg.get("target"),
        training_targets=list(targets),
    )

    packs = step_collect_packs(receipt, args)
    pack_transfer = selected_pack_transfer_plan(packs)
    pack_stage = f"{CT_CYCLE_RUN_DIR}/{run_id}/packs"
    receipt["packs"] = {
        "files": packs["files"],
        "curricula": len(packs["selected"]),
        "physical_rows": packs["physical_rows"],
        "logical_rows": packs["logical_rows"],
        "rows": packs["rows"],
        "admitted": packs["admitted"],
        "explicit_rows_by_target": packs["explicit_rows_by_target"],
        "admitted_by_target": packs["admitted_by_target"],
        "target_exclusions": packs["target_exclusions"],
        "curriculum_contract": packs["curriculum_contract"],
        "curriculum_coverage": packs["curriculum_coverage"],
        "segment_chains": [
            {
                "curriculum_id": item["curriculum_id"],
                "segment_count": item["segment_count"],
                "segment_chain_sha256": item["segment_chain_sha256"],
                "segments": list(
                    (item.get("segment_chain") or {}).get("segments") or []
                ),
            }
            for item in packs["selected"]
        ],
        "transfer_evidence": pack_transfer["receipt"],
        "transfer_evidence_file_count": pack_transfer["evidence_file_count"],
        "pushed": 0,
        "ct_stage_dir": pack_stage,
    }
    receipt["pack_detail"] = {
        "pack_dir": packs["pack_dir"],
        "rejected": packs["rejected"],
        "invalid_rows": packs["invalid_rows"],
        "admit_disagreements": packs["admit_disagreements"],
        "legacy_admit_disagreements": packs["legacy_admit_disagreements"],
        "current_admit_disagreements": packs["current_admit_disagreements"],
        "quarantined": packs["quarantined"],
        "quarantine_files": packs["quarantine_files"],
        "quarantine_blockers": packs["quarantine_blockers"],
        "selected_targets": packs["selected_targets"],
        "physical_rows": packs["physical_rows"],
        "logical_rows": packs["logical_rows"],
        "explicit_rows_by_target": packs["explicit_rows_by_target"],
        "admitted_by_target": packs["admitted_by_target"],
        "target_exclusions": packs["target_exclusions"],
        "skipped_outside_window": packs["skipped_stale"],
        "by_discipline": packs["by_discipline"],
        "by_status": packs["by_status"],
        "audit_only_history": packs["audit"],
        "files": [
            {
                "name": item["name"],
                "pack_sha256": item["pack_sha256"],
                "pack_read_only": item["pack_read_only"],
                "curriculum_id": item["curriculum_id"],
                "curriculum_binding": item["curriculum_binding"],
                "coverage_eligible": item["coverage_eligible"],
                "segment_count": item["segment_count"],
                "segment_chain_sha256": item["segment_chain_sha256"],
                "segments": list(
                    (item.get("segment_chain") or {}).get("segments") or []
                ),
                "physical_rows": item["physical_rows"],
                "logical_rows": item["logical_rows"],
                "rows": item["rows"],
                "admitted": item["admitted"],
                "rejected": item["rejected"],
                "invalid_rows": item["invalid_rows"],
                "admit_disagreements": item["admit_disagreements"],
                "legacy_admit_disagreements": item[
                    "legacy_admit_disagreements"
                ],
                "current_admit_disagreements": item[
                    "current_admit_disagreements"
                ],
                "quarantined": item["quarantined"],
                "selected_targets": item["selected_targets"],
                "explicit_rows_by_target": item["explicit_rows_by_target"],
                "admitted_by_target": item["admitted_by_target"],
                "target_exclusions": item["target_exclusions"],
                "quarantine_receipts": item["quarantine_receipts"],
                "modified_at_utc": item.get("modified_at_utc"),
                "missing_optional_fields": item.get("missing_optional_fields") or [],
            }
            for item in packs["selected"]
        ],
        "transfer_evidence": pack_transfer["receipt"],
        "transfer_errors": pack_transfer["errors"],
        "errors": packs["errors"][:20],
    }
    collect_packs_ok = receipt["steps"][-1]["ok"]
    if not pack_transfer["ok"]:
        receipt["blockers"].append(
            "selected pack evidence transfer roster is incomplete or conflicting: "
            + " | ".join(pack_transfer["errors"][:5])
        )
    record(
        receipt,
        "verify_pack_transfer_roster",
        pack_transfer["ok"],
        (
            f"{pack_transfer['segment_count']} immutable pack segment(s) + "
            f"{pack_transfer['evidence_file_count']} receipt/sidecar file(s) hash-bound"
            if pack_transfer["ok"]
            else "REFUSED: " + " | ".join(pack_transfer["errors"][:5])
        ),
        0.0,
    )
    packs_ok = collect_packs_ok and pack_transfer["ok"]

    corpus_plan = inspect_construction_corpus_bundle(
        ROOT / "memory" / "training" / "construction_env",
        run_id,
    )
    receipt["construction_corpus"] = construction_corpus_receipt(corpus_plan)
    corpus_ok = corpus_plan.get("ok") is True
    if not corpus_ok:
        corpus_detail = "; ".join(str(item) for item in corpus_plan.get("blockers") or [])
        receipt["blockers"].append(
            "construction corpus is partial or invalid; remote work was refused: "
            + (corpus_detail or "bundle verification failed")
        )
    record(
        receipt,
        "verify_construction_corpus",
        corpus_ok,
        (
            f"{corpus_plan.get('mode')} corpus; "
            f"{len(corpus_plan.get('files') or [])} exact file(s); "
            f"bundle_sha256={corpus_plan.get('bundle_sha256') or '<empty>'}"
            if corpus_ok
            else "REFUSED: " + (corpus_detail or "bundle verification failed")
        ),
        0.0,
    )

    if not corpus_ok:
        return finish(receipt)

    if args.no_ct:
        record(
            receipt,
            "ct_skipped",
            True,
            "--no-ct: local pack validation only, no remote push, build, training, or mirror",
            0.0,
        )
        return finish(receipt)

    if not packs_ok:
        # Coverage/admission failed locally. Remote resolution itself is a side effect and
        # must not begin until all five current packs are causally present.
        record(
            receipt,
            "remote_cycle_aborted",
            False,
            "aborted before any remote step: complete current all-five curriculum "
            "coverage was not proven",
            0.0,
        )
        return finish(receipt)

    if args.dry_run:
        plan_remote_steps(receipt, cfg, args, packs)
        return finish(receipt)

    if "llm" in targets:
        approval = str(getattr(args, "llm_approval", "") or "")
        if not llm_training_approval_valid(targets, approval):
            receipt["blockers"].append(
                "local LLM training was selected but the exact operator approval phrase "
                "was not supplied; no remote work was started"
            )
            record(
                receipt,
                "llm_approval_gate",
                False,
                "REFUSED before remote mutation: exact local LLM training approval missing",
                0.0,
            )
            return finish(receipt)
        record(
            receipt,
            "llm_approval_gate",
            True,
            "exact operator approval accepted; phrase not retained in this cycle receipt",
            0.0,
        )

    if not cfg.get("target"):
        receipt["blockers"].append(
            "CT SSH target is not configured (set ENGEL_CT_SSH_TARGET or ENGEL_MAIN_SERVER_HOST)"
        )
        record(receipt, "resolve_ct_python", False, "no CT ssh target configured", 0.0)
        return finish(receipt)

    ct_python = step_resolve_ct_python(receipt, cfg)
    if not ct_python:
        return finish(receipt)

    if args.no_push_tools:
        record(
            receipt,
            "push_tools",
            True,
            "--no-push-tools: CT tools left as they are (the cycle runs whatever is deployed)",
            0.0,
        )
    elif not push_files(
        receipt, cfg, "push_tools", [ROOT / "tools" / name for name in CT_TOOL_FILES], CT_TOOLS_DIR
    ):
        return finish(receipt)

    pack_stage = str(receipt["packs"]["ct_stage_dir"])
    if not push_files(
        receipt,
        cfg,
        "push_packs",
        pack_transfer["paths"],
        pack_stage,
        expected_hashes=pack_transfer["expected_hashes"],
        batch_copy=True,
    ):
        return finish(receipt)
    receipt["packs"]["pushed"] = pack_transfer["segment_count"]
    receipt["packs"]["evidence_files_pushed"] = pack_transfer[
        "evidence_file_count"
    ]

    # AEC admission is grounded in a complete, hash-bound construction corpus. The
    # transfer owns a fresh directory for this run and publishes that root to builders
    # only after its exact remote file set passes, so a previous or partial corpus can
    # never be selected by accident.
    if not push_construction_corpus(receipt, cfg, corpus_plan):
        return finish(receipt)

    # SFT is an LLM artifact. An SLM-only cycle must never rebuild it from SLM-only
    # rows; the SLM lane proves its own staged-pack hand-off below.
    dataset_ok = "llm" not in targets
    if "llm" in targets:
        dataset_ok = step_build_dataset(
            receipt,
            cfg,
            ct_python,
            packs["admitted_by_target"]["llm"],
            pack_stage,
            expected_rows_seen=packs["logical_rows"],
            expected_explicit_rows=packs["explicit_rows_by_target"]["llm"],
        )
    else:
        record(
            receipt,
            "build_dataset",
            True,
            "SKIPPED: llm was not selected; no SFT dataset was written",
            0.0,
        )

    if "slm" in targets:
        slm_dataset_dir = str(receipt["slm"]["dataset_dir"])
        slm_datasets_ok = step_slm_datasets(
            receipt,
            cfg,
            ct_python,
            pack_stage,
            slm_dataset_dir,
            packs["admitted_by_target"]["slm"],
            expected_rows_seen=packs["logical_rows"],
            expected_explicit_rows=packs["explicit_rows_by_target"]["slm"],
        )
        if slm_datasets_ok:
            candidate_dir = str(receipt["slm"]["candidate_dir"])
            train_ok = step_slm_train(
                receipt,
                cfg,
                ct_python,
                args.slm_tasks,
                candidate_dir,
                slm_dataset_dir,
            )
            if train_ok:
                gate_ok = step_slm_verify(receipt, cfg, ct_python, candidate_dir)
                mirrored = step_mirror_back(receipt, cfg, gate_ok, candidate_dir)
            else:
                gate_ok = False
                mirrored = False
                record(
                    receipt,
                    "slm_verify",
                    False,
                    "REFUSED: the full requested roster was not selected in this cycle's "
                    "staged report; no candidate bytes were verified or promoted",
                    0.0,
                )
            # A directory swap cannot prove the long-lived app has reloaded its in-memory
            # roster.  This process has no authenticated handle to that runtime object, so
            # it records the boundary and stays PARTIAL instead of restarting a service or
            # measuring old in-memory bytes as though they were the new release.
            if mirrored:
                step_slm_reload_pending(receipt)
                if not getattr(args, "no_capability_gate", False):
                    record(
                        receipt,
                        "capability_gate",
                        False,
                        "NOT RUN: the serving process has not acknowledged the new "
                        "report hash, so an end-to-end measurement would still exercise "
                        "the previous in-memory roster",
                        0.0,
                    )
        else:
            record(
                receipt,
                "slm_training_aborted",
                False,
                "SLM datasets failed; training on stale labels was refused",
                0.0,
            )

    if "llm" in targets:
        if not dataset_ok:
            receipt["blockers"].append(
                "local LLM training was refused because the SFT dataset build did not pass"
            )
            record(
                receipt,
                "llm_training_aborted",
                False,
                "SFT dataset did not pass; adapter training was not started",
                0.0,
            )
        elif step_llm_preflight(receipt, cfg, ct_python):
            step_llm_train(
                receipt,
                cfg,
                ct_python,
                str(getattr(args, "llm_approval", "")),
            )
    return finish(receipt, dataset_ok=dataset_ok)


def finish(receipt: dict[str, Any], dataset_ok: bool = False) -> dict[str, Any]:
    global _ACTIVE_CYCLE_DEADLINE_MONOTONIC
    receipt["finished_at_utc"] = iso_now()
    failed = [entry["step"] for entry in receipt["steps"] if not entry["ok"]]
    if not failed and not receipt["blockers"]:
        receipt["status"] = "PASS"
    elif dataset_ok:
        receipt["status"] = "PARTIAL"
    else:
        receipt["status"] = "FAIL"
    receipt["failed_steps"] = failed
    # The stamp only resolves to the second, so two cycles finishing inside the same
    # second would silently overwrite each other's history file. The LATEST copy is
    # meant to be replaced; a stamped run record is not.
    run_stamp = receipt["run_id"].split("_", 1)[-1] or stamp()
    stamped = REPORT_DIR / f"ENGEL_REAL_TRAINING_CYCLE_{run_stamp}.json"
    suffix = 2
    while stamped.exists():
        stamped = REPORT_DIR / f"ENGEL_REAL_TRAINING_CYCLE_{run_stamp}_{suffix}.json"
        suffix += 1
    latest = REPORT_DIR / "ENGEL_REAL_TRAINING_CYCLE_LATEST.json"
    write_json(stamped, receipt)
    # (2026-08-08) A dry run is a PLAN, not a result. It keeps its timestamped receipt but
    # must never replace LATEST -- the Training panel reads LATEST as "latest model
    # results", and a dry-run "PASS" there displaces the real run's verdict.
    if receipt.get("dry_run"):
        receipt["receipt_paths"] = [str(stamped)]
    else:
        write_json(latest, receipt)
        receipt["receipt_paths"] = [str(latest), str(stamped)]
    event(
        "cycle_finished",
        run_id=receipt["run_id"],
        status=receipt["status"],
        failed_steps=failed,
        blockers=len(receipt["blockers"]),
        receipt=str(latest),
    )
    _ACTIVE_CYCLE_DEADLINE_MONOTONIC = None
    return receipt


def compact_summary(receipt: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "engel_real_training_cycle_summary_v1",
        "run_id": receipt["run_id"],
        "status": receipt["status"],
        "mode": receipt["mode"],
        "dry_run": receipt["dry_run"],
        "targets": receipt.get("targets") or [],
        "packs": receipt["packs"],
        "construction_corpus": receipt.get("construction_corpus") or {},
        "dataset": receipt["dataset"],
        "slm_tasks_ok": sorted(
            name for name, value in (receipt["slm"]["tasks"] or {}).items() if value.get("ok")
        ),
        "slm_mirrored": len(receipt["slm"]["mirrored"]),
        "slm_filesystem_installed": bool(receipt["slm"].get("mirrored")),
        "slm_reload_required": receipt["slm"].get("reload_required") is True,
        "slm_reload_acknowledged": receipt["slm"].get("reload_acknowledged") is True,
        "slm_release_report_sha256": receipt["slm"].get("release_report_sha256", ""),
        "llm_adapter_trained": receipt.get("llm", {}).get("new_adapter_trained") is True,
        "llm_adapter_path": receipt.get("llm", {}).get("new_adapter_path", ""),
        "llm_auto_deployed": receipt.get("llm", {}).get("auto_deployed") is True,
        "failed_steps": receipt.get("failed_steps") or [],
        "blockers": receipt["blockers"],
        "receipt": (receipt.get("receipt_paths") or [""])[0],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--since-hours",
        type=float,
        default=48.0,
        help="only use packs modified within this many hours (default 48)",
    )
    parser.add_argument("--all", action="store_true", help="use every pack on disk")
    parser.add_argument(
        "--no-push-tools",
        action="store_true",
        help="run against the CT tools already deployed instead of pushing this repo's copies",
    )
    parser.add_argument(
        "--no-ct",
        action="store_true",
        help="local validation only: collect and validate packs, write a receipt, skip all remote work",
    )
    parser.add_argument(
        "--slm-tasks",
        type=normalize_slm_task_csv,
        default=DEFAULT_SLM_TASKS,
        help="comma separated canonical SLM tasks; use 'all' for data-collection candidates",
    )
    parser.add_argument(
        "--targets",
        type=normalize_training_targets,
        default=normalize_training_targets("slm"),
        help="model families to train: slm, llm, or slm,llm (default: slm)",
    )
    parser.add_argument(
        "--llm-approval",
        default="",
        help="exact operator approval required only when --targets includes llm",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="plan only: no remote mutation, receipt is marked dry_run",
    )
    parser.add_argument(
        "--no-capability-gate",
        action="store_true",
        help=(
            "skip recording the deferred capability step. Capability cannot run until the "
            "serving process acknowledges the exact filesystem release hash"
        ),
    )
    parser.add_argument("--summary", action="store_true", help="print a compact JSON summary")
    args = parser.parse_args()

    if args.dry_run:
        receipt = run_cycle(args)
    else:
        try:
            with exclusive_cycle_lock():
                receipt = run_cycle(args)
        except CycleLockBusy as exc:
            # The lock is acquired before run_cycle resolves SSH or writes any dataset,
            # receipt, model, or mirror path.  Do not fabricate a run id for work that
            # never began.
            print(
                json.dumps(
                    {
                        "status": "FAIL",
                        "run_id": None,
                        "receipt": "",
                        "blockers": [str(exc)],
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 1
    if args.summary:
        print(json.dumps(compact_summary(receipt), indent=2, sort_keys=True))
    else:
        print(
            json.dumps(
                {
                    "status": receipt["status"],
                    "run_id": receipt["run_id"],
                    "receipt": (receipt.get("receipt_paths") or [""])[0],
                    "blockers": receipt["blockers"],
                },
                indent=2,
                sort_keys=True,
            )
        )
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
