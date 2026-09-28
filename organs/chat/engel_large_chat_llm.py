"""Engel large local chat LLM lane.

This module does not download models, call providers, start servers, or write
trusted memory. It detects staged GGUF model sets and, when a model is present, runs one bounded llama.cpp chat turn against it.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
MANIFEST_PATH = ROOT / "memory" / "models" / "ENGEL_LARGE_CHAT_LLM_MANIFEST.json"

MINIMUM_MODEL_BYTES = 0
DEFAULT_MODEL_ROOT = Path(os.environ.get("ENGEL_LARGE_CHAT_LLM_MODEL_ROOT", str(ROOT / "models-active" / "llm")))
DEFAULT_RUNPOD_HANDOFF_ROOT = Path(
    os.environ.get("ENGEL_LARGE_CHAT_LLM_RUNPOD_HANDOFF_ROOT", str(ROOT / "run" / "runpod" / "large_chat_llm"))
)
DEFAULT_APPROVED_EXTRA_ROOTS = [
    ROOT / "models-active" / "llm",
    ROOT / "models-active",
]
DEFAULT_PREFERRED_CHAT_MODEL_PATHS = [
    ROOT / "models-active" / "llm" / "ornith-1.0-9b" / "ornith-1.0-9b-Q4_K_M.gguf",
    ROOT / "models-active" / "llm" / "qwen2.5-7b-instruct" / "qwen2.5-7b-instruct-q5_k_m.gguf",
]

DEFAULT_CTX = 8192
DEFAULT_N_PREDICT = 512
DEFAULT_THREADS = 8
DEFAULT_NGL = 99
DEFAULT_TIMEOUT_SECONDS = 900

_SHARD_RE = re.compile(r"^(?P<prefix>.+)-(?P<index>\d{5})-of-(?P<count>\d{5})\.gguf$", re.IGNORECASE)


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _env_int(name: str, default: int) -> int:
    """Tolerant env int: falls back to default on empty/garbage rather than
    raising (a bad ENGEL_LARGE_CHAT_LLM_* value must not crash the lane)."""
    try:
        return int(str(os.environ.get(name, "")).strip() or default)
    except (TypeError, ValueError):
        return int(default)


def _env_float(name: str, default: float) -> float:
    try:
        return float(str(os.environ.get(name, "")).strip() or default)
    except (TypeError, ValueError):
        return float(default)


def _reply_is_greeting_stall(reply: str) -> bool:
    low = " ".join(str(reply or "").casefold().split())
    if not low:
        return False
    if "what should we work on next" in low:
        return True
    return len(low) < 220 and (
        low.startswith("i am here with you")
        or low.startswith("i'm here with you")
        or low.startswith("engel ai main is here with you")
    )


def _clean_text(text: Any) -> str:
    value = str(text or "").replace("\x00", "")
    return "".join(ch for ch in value if ch in "\t\r\n" or ord(ch) >= 32).strip()


def _as_path(value: Any) -> Path | None:
    text = str(value or "").strip()
    if not text:
        return None
    return Path(text)


def _is_forbidden_runtime_path(path: Path | None) -> bool:
    if path is None:
        return False
    text = str(path).replace("\\", "/")
    offline_ct245_mount = "/mnt/" + "engel-vault"
    if text.startswith(offline_ct245_mount):
        return True
    if re.match(r"^[EFG]:/", text, re.IGNORECASE):
        return True
    return False


def _is_os_drive(path: Path) -> bool:
    return path.drive.lower() == "c:"


def _path_key(path: Path) -> str:
    try:
        return str(path.resolve(strict=False)).lower()
    except OSError:
        return str(path.absolute()).lower()


def _is_under(path: Path, root: Path) -> bool:
    path_key = _path_key(path)
    root_key = _path_key(root).rstrip("\\/")
    return path_key == root_key or path_key.startswith(root_key + os.sep.lower()) or path_key.startswith(root_key + "/")


def _drive_free_bytes(path: Path) -> int | None:
    drive = path.drive
    target = Path(f"{drive}/") if drive else path
    try:
        return int(shutil.disk_usage(str(target)).free)
    except OSError:
        return None


def _bytes_to_gib(value: int | None) -> float | None:
    if value is None:
        return None
    return round(value / (1024**3), 2)


def load_manifest() -> dict[str, Any]:
    if not MANIFEST_PATH.exists():
        return {
            "schema": "engel_large_chat_llm_manifest_v1",
            "enabled_for_local_chat_when_present": True,
            "minimum_model_store_gib": 0,
            "minimum_model_bytes": MINIMUM_MODEL_BYTES,
            "model_store_root": str(DEFAULT_MODEL_ROOT),
            "active_model_path": "",
            "preferred_model_paths": [str(path) for path in DEFAULT_PREFERRED_CHAT_MODEL_PATHS],
            "extra_model_roots": [str(path) for path in DEFAULT_APPROVED_EXTRA_ROOTS],
            "runpod_handoff_root": str(DEFAULT_RUNPOD_HANDOFF_ROOT),
            "download_enabled": False,
            "provider_calls_enabled": False,
            "runpod_api_enabled": False,
        }
    try:
        data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    data.setdefault("schema", "engel_large_chat_llm_manifest_v1")
    data.setdefault("enabled_for_local_chat_when_present", True)
    data.setdefault("minimum_model_store_gib", 0)
    data.setdefault("minimum_model_bytes", MINIMUM_MODEL_BYTES)
    data.setdefault("model_store_root", str(DEFAULT_MODEL_ROOT))
    data.setdefault("active_model_path", "")
    data.setdefault("preferred_model_paths", [str(path) for path in DEFAULT_PREFERRED_CHAT_MODEL_PATHS])
    data.setdefault("extra_model_roots", [str(path) for path in DEFAULT_APPROVED_EXTRA_ROOTS])
    data.setdefault("runpod_handoff_root", str(DEFAULT_RUNPOD_HANDOFF_ROOT))
    data.setdefault("download_enabled", False)
    data.setdefault("provider_calls_enabled", False)
    data.setdefault("runpod_api_enabled", False)
    if _is_forbidden_runtime_path(_as_path(data.get("runpod_handoff_root"))):
        data["runpod_handoff_root"] = str(DEFAULT_RUNPOD_HANDOFF_ROOT)
    if _is_forbidden_runtime_path(_as_path(data.get("model_store_root"))):
        data["model_store_root"] = str(DEFAULT_MODEL_ROOT)
    if _is_forbidden_runtime_path(_as_path(data.get("active_model_path"))):
        data["active_model_path"] = ""
    data["preferred_model_paths"] = [
        str(path)
        for path in (_as_path(value) for value in data.get("preferred_model_paths") or [])
        if path is not None and not _is_forbidden_runtime_path(path)
    ] or [str(path) for path in DEFAULT_PREFERRED_CHAT_MODEL_PATHS]
    data["extra_model_roots"] = [
        str(path)
        for path in (_as_path(value) for value in data.get("extra_model_roots") or [])
        if path is not None and not _is_forbidden_runtime_path(path)
    ] or [str(path) for path in DEFAULT_APPROVED_EXTRA_ROOTS]
    return data




def minimum_model_bytes(manifest: dict[str, Any] | None = None) -> int:
    manifest = manifest or load_manifest()
    try:
        gib = float(manifest.get("minimum_model_store_gib") or 0)
    except (TypeError, ValueError):
        gib = 0
    explicit = manifest.get("minimum_model_bytes")
    try:
        explicit_bytes = int(explicit)
    except (TypeError, ValueError):
        explicit_bytes = 0
    return max(0, int(gib * 1024**3), explicit_bytes)


def approved_model_roots(manifest: dict[str, Any] | None = None) -> list[Path]:
    manifest = manifest or load_manifest()
    roots: list[Path] = []
    for value in [manifest.get("model_store_root"), *(manifest.get("extra_model_roots") or [])]:
        path = _as_path(value)
        if path is not None and not _is_os_drive(path) and not _is_forbidden_runtime_path(path):
            roots.append(path)
    for env_value in str(os.environ.get("ENGEL_LARGE_CHAT_LLM_ROOTS", "")).split(os.pathsep):
        path = _as_path(env_value)
        if path is not None and not _is_os_drive(path) and not _is_forbidden_runtime_path(path):
            roots.append(path)
    seen: set[str] = set()
    unique: list[Path] = []
    for root in roots:
        key = _path_key(root)
        if key not in seen:
            seen.add(key)
            unique.append(root)
    return unique


def _is_approved_model_path(path: Path, roots: list[Path]) -> bool:
    if _is_os_drive(path) or _is_forbidden_runtime_path(path):
        return False
    return any(_is_under(path, root) for root in roots)


def _gguf_files(roots: list[Path]) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        if not root.exists() or not root.is_dir():
            continue
        try:
            files.extend(p for p in root.rglob("*.gguf") if p.is_file() and not _is_os_drive(p))
        except OSError:
            continue
    return files


def _candidate_from_single(path: Path) -> dict[str, Any]:
    try:
        size = path.stat().st_size
    except OSError:
        size = 0
    return {
        "entry_model_path": path,
        "total_bytes": int(size),
        "file_count": 1,
        "sharded": False,
        "shard_paths": [path],
    }


def installed_model_candidates(manifest: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    manifest = manifest or load_manifest()
    roots = approved_model_roots(manifest)
    files = _gguf_files(roots)
    groups: dict[tuple[str, str, str], list[Path]] = {}
    singles: list[Path] = []
    for path in files:
        match = _SHARD_RE.match(path.name)
        if match:
            key = (_path_key(path.parent), match.group("prefix").lower(), match.group("count"))
            groups.setdefault(key, []).append(path)
        else:
            singles.append(path)

    candidates: list[dict[str, Any]] = [_candidate_from_single(path) for path in singles]
    for shard_paths in groups.values():
        sorted_paths = sorted(shard_paths, key=lambda p: p.name.lower())
        entry = next((p for p in sorted_paths if "-00001-of-" in p.name.lower()), sorted_paths[0])
        total = 0
        for path in sorted_paths:
            try:
                total += path.stat().st_size
            except OSError:
                pass
        candidates.append(
            {
                "entry_model_path": entry,
                "total_bytes": int(total),
                "file_count": len(sorted_paths),
                "sharded": True,
                "shard_paths": sorted_paths,
            }
        )
    candidates.sort(key=lambda item: int(item.get("total_bytes") or 0), reverse=True)
    return candidates


def _candidate_for_path(path: Path, candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    target = _path_key(path)
    for candidate in candidates:
        entry = candidate.get("entry_model_path")
        if isinstance(entry, Path) and _path_key(entry) == target:
            return candidate
        for shard in candidate.get("shard_paths") or []:
            if isinstance(shard, Path) and _path_key(shard) == target:
                return candidate
    return None


def select_large_chat_model_info(manifest: dict[str, Any] | None = None) -> dict[str, Any] | None:
    manifest = manifest or load_manifest()
    if manifest.get("enabled_for_local_chat_when_present") is False:
        return None
    roots = approved_model_roots(manifest)
    min_bytes = minimum_model_bytes(manifest)
    candidates = installed_model_candidates(manifest)

    env_path = _as_path(os.environ.get("ENGEL_LARGE_CHAT_LLM_MODEL"))
    active_path = _as_path(manifest.get("active_model_path"))
    preferred_paths = [_as_path(value) for value in manifest.get("preferred_model_paths") or []]
    for path in [env_path, *preferred_paths, active_path]:
        if path is None or not path.exists() or not _is_approved_model_path(path, roots):
            continue
        candidate = _candidate_for_path(path, candidates) or _candidate_from_single(path)
        if int(candidate.get("total_bytes") or 0) > 0 and int(candidate.get("total_bytes") or 0) >= min_bytes:
            return candidate

    for candidate in candidates:
        if int(candidate.get("total_bytes") or 0) > 0 and int(candidate.get("total_bytes") or 0) >= min_bytes:
            return candidate
    return None


def select_large_chat_model(manifest: dict[str, Any] | None = None) -> Path | None:
    candidate = select_large_chat_model_info(manifest)
    if not candidate:
        return None
    path = candidate.get("entry_model_path")
    return path if isinstance(path, Path) else None


def large_chat_model_available(manifest: dict[str, Any] | None = None) -> bool:
    return select_large_chat_model(manifest) is not None


def large_chat_model_status() -> dict[str, Any]:
    manifest = load_manifest()
    roots = approved_model_roots(manifest)
    candidates = installed_model_candidates(manifest)
    selected = select_large_chat_model_info(manifest)
    store_root = _as_path(manifest.get("model_store_root")) or DEFAULT_MODEL_ROOT
    free_bytes = _drive_free_bytes(store_root)
    largest = candidates[0] if candidates else None
    selected_path = selected.get("entry_model_path") if selected else None
    status = {
        "schema": "engel_large_chat_llm_status_v1",
        "ok": True,
        "updated_at_utc": iso_now(),
        "manifest_path": str(MANIFEST_PATH),
        "manifest_present": MANIFEST_PATH.exists(),
        "enabled_for_local_chat_when_present": manifest.get("enabled_for_local_chat_when_present") is not False,
        "minimum_model_store_gib": 0,
        "minimum_model_bytes": minimum_model_bytes(manifest),
        "model_store_root": str(store_root),
        "model_store_root_os_drive": _is_os_drive(store_root),
        "model_store_free_bytes": free_bytes,
        "model_store_free_gib": _bytes_to_gib(free_bytes),
        "model_store_has_required_free": bool(
            minimum_model_bytes(manifest) == 0 or (free_bytes is not None and free_bytes >= minimum_model_bytes(manifest))
        ),
        "approved_model_roots": [str(path) for path in roots],
        "candidate_count": len(candidates),
        "largest_installed_gguf_path": str(largest.get("entry_model_path")) if largest else "",
        "largest_installed_gguf_total_bytes": int(largest.get("total_bytes") or 0) if largest else 0,
        "largest_installed_gguf_total_gib": _bytes_to_gib(int(largest.get("total_bytes") or 0)) if largest else 0,
        "selected_model_present": selected is not None,
        "selected_model_path": str(selected_path) if isinstance(selected_path, Path) else "",
        "selected_model_total_bytes": int(selected.get("total_bytes") or 0) if selected else 0,
        "selected_model_total_gib": _bytes_to_gib(int(selected.get("total_bytes") or 0)) if selected else 0,
        "selected_model_file_count": int(selected.get("file_count") or 0) if selected else 0,
        "selected_model_sharded": bool(selected.get("sharded")) if selected else False,
        "download_enabled": bool(manifest.get("download_enabled") is True),
        "provider_calls_enabled": bool(manifest.get("provider_calls_enabled") is True),
        "runpod_api_enabled": bool(manifest.get("runpod_api_enabled") is True),
        "runpod_handoff_root": str(manifest.get("runpod_handoff_root") or DEFAULT_RUNPOD_HANDOFF_ROOT),
        "server_enabled": False,
        "network_enabled": False,
        "trusted_memory_write_enabled": False,
    }
    if not status["selected_model_present"]:
        status["status"] = "large chat model not installed yet"
    else:
        status["status"] = "large chat model ready"
    return status


def render_large_chat_llm_status() -> str:
    status = large_chat_model_status()
    lines = [
        "# Engel Large Chat LLM Status",
        "",
        f"Status: {status['status']}",
        f"Model store: {status['model_store_root']}",
        f"Model store free GiB: {status['model_store_free_gib']}",
        f"Selected model present: {status['selected_model_present']}",
        f"Selected model: {status['selected_model_path'] or '(none)'}",
        f"Selected model total GiB: {status['selected_model_total_gib']}",
        f"Installed GGUF candidate count: {status['candidate_count']}",
        f"Largest installed GGUF total GiB: {status['largest_installed_gguf_total_gib']}",
        "",
        "Safety: no downloads, no provider calls, no server, no trusted-memory writes.",
    ]
    return "\n".join(lines) + "\n"


def _resolve_large_chat_lora(model: Path | None) -> str:
    """Aligned-persona LoRA for the large-chat lane (opt-in via env).

    Returns the adapter GGUF path ONLY when ENGEL_LARGE_CHAT_LLM_LORA is set,
    the file exists on an allowed root, and the selected base model is the one
    the adapter was trained/converted against (ENGEL_TRAINED_LORA_BASE_GGUF_MODEL).
    Any mismatch or doubt returns "" so the lane serves the plain base instead of
    applying a LoRA over the wrong weights. Unset env == today's behavior.
    """
    if model is None:
        return ""
    lora = _as_path(os.environ.get("ENGEL_LARGE_CHAT_LLM_LORA"))
    if lora is None or _is_forbidden_runtime_path(lora) or _is_os_drive(lora):
        return ""
    try:
        if not lora.is_file() or lora.stat().st_size <= 0:
            return ""
    except OSError:
        return ""
    trained_base = _as_path(os.environ.get("ENGEL_TRAINED_LORA_BASE_GGUF_MODEL"))
    if trained_base is None or _path_key(trained_base) != _path_key(model):
        return ""
    return str(lora)


def run_large_chat_with_llama_cli(
    user_text: str,
    system_prompt: str = "",
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    max_tokens: int = DEFAULT_N_PREDICT,
) -> dict[str, Any]:
    status = large_chat_model_status()
    model = select_large_chat_model()
    if model is None:
        return {
            "ok": False,
            "status": status.get("status", "large chat model not installed yet"),
            "large_chat_llm": status,
            "network_enabled": False,
            "provider_api_enabled": False,
            "server_enabled": False,
            "trusted_memory_write_enabled": False,
        }

    service_error = ""
    try:
        try:
            from engel_local_model_service import run_llama_cpp_lora_text_with_model
        except ModuleNotFoundError:
            tools_path = ROOT / "tools"
            if str(tools_path) not in sys.path:
                sys.path.insert(0, str(tools_path))
            from engel_local_model_service import run_llama_cpp_lora_text_with_model

        service_prompt_parts = []
        cleaned_system = _clean_text(system_prompt)
        if cleaned_system:
            service_prompt_parts.append(cleaned_system)
        service_prompt_parts.append("User request:\n" + (_clean_text(user_text) or "Say hello in one short sentence."))
        requested_ngl = _env_int(
            "ENGEL_LARGE_CHAT_LLM_NGL",
            _env_int("ENGEL_MAIN_LOCAL_MODEL_N_GPU_LAYERS", 0 if os.name != "nt" else DEFAULT_NGL),
        )
        aligned_lora = _resolve_large_chat_lora(model)
        started = time.perf_counter()
        service_result = run_llama_cpp_lora_text_with_model(
            model_path=str(model),
            lora_path=aligned_lora,
            prompt="\n\n".join(service_prompt_parts),
            n_predict=max(1, int(max_tokens or DEFAULT_N_PREDICT)),
            ctx=_env_int("ENGEL_LARGE_CHAT_LLM_CTX", DEFAULT_CTX),
            n_gpu_layers=max(0, requested_ngl),
            temperature=_env_float("ENGEL_LARGE_CHAT_LLM_TEMPERATURE", 0.72),  # higher for natural chat feel (SSD/local LLM)
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        reply = _clean_text(service_result.get("text") or service_result.get("stdout") or "")
        if reply:
            try:
                from engel_persona_guard import looks_like_discord_mouth_reply

                if looks_like_discord_mouth_reply(reply) or _reply_is_greeting_stall(reply):
                    reply = ""
                    service_error = "laptop draft was a greeting stall or Discord guest gate, not an answer"
            except Exception:
                if "only engelz" in reply.casefold():
                    reply = ""
                    service_error = "laptop draft answered as a Discord guest gate, not Engel AI Main"
        if service_result.get("ok") is True and reply:
            gpu_layers = int(service_result.get("n_gpu_layers") or 0)
            return {
                "ok": True,
                "status": "large local chat model replied",
                "assistant_reply": reply,
                "assistant_output_text": reply,
                "text": reply,
                "receipt": {
                    "large_chat_llm": status,
                    "large_chat_llm_used": True,
                    "local_gguf_model_path": str(model),
                    "large_chat_llm_lora_path": aligned_lora,
                    "large_chat_llm_lora_applied": bool(aligned_lora),
                    "runtime_provider": "local-llama-cpp-python-in-process",
                    "local_command_elapsed_ms": elapsed_ms,
                    "long_lived_local_model_service_used": True,
                },
                "large_chat_llm": status,
                "large_chat_llm_used": True,
                "local_command_elapsed_ms": elapsed_ms,
                "runtime_process_started": True,
                "model_process_started": True,
                "runtime_process_exited": True,
                "runs_inference": True,
                "loads_model": True,
                "gpu_enabled": gpu_layers > 0,
                "gpu_device": "CUDA0" if gpu_layers > 0 else "CPU",
                "gpu_layers": gpu_layers,
                "network_enabled": False,
                "provider_api_enabled": False,
                "server_enabled": False,
                "trusted_memory_write_enabled": False,
                "approved_memory_write_enabled": False,
                "model_output_trusted": False,
                "model": str(model),
                "long_lived_local_model_service_enabled": True,
                "long_lived_local_model_service_used": True,
                "long_lived_local_model_service_fallback_used": False,
                "model_loaded_in_current_process": bool(service_result.get("model_loaded_in_current_process") is True),
                "model_load_count": service_result.get("model_load_count"),
                "model_load_ms": service_result.get("model_load_ms"),
                "generation_ms": service_result.get("generation_ms"),
            }
        service_error = str(service_result.get("error") or "large model service returned no readable answer")
    except Exception as exc:
        service_error = str(exc)

    # (20260711 fix) the whole CLI fallback branch used to run unguarded, so the
    # same bad env value that tripped the in-process branch (caught above into
    # service_error) would re-raise here and escape — defeating the fallback that
    # exists precisely to rescue such failures. Guard import + cli lookup + command
    # build so any failure returns the ok=False dict with service_error attached.
    try:
        import engel_llama_cli_runner as runner

        cli, is_cuda = runner._find_cli()
    except Exception as exc:
        return {
            "ok": False,
            "status": "llama-cli fallback unavailable",
            "error": f"{service_error} | fallback: {exc}",
            "large_chat_llm": status,
            "network_enabled": False,
            "provider_api_enabled": False,
            "server_enabled": False,
            "trusted_memory_write_enabled": False,
        }
    if cli is None:
        return {
            "ok": False,
            "status": "llama-cli executable not found",
            "error": service_error,
            "large_chat_llm": status,
            "network_enabled": False,
            "provider_api_enabled": False,
            "server_enabled": False,
            "trusted_memory_write_enabled": False,
        }

    n_predict = max(1, int(max_tokens or DEFAULT_N_PREDICT))
    cli_lora = _resolve_large_chat_lora(model)
    command = runner._build_chat_cmd(
        cli=cli,
        model=model,
        user_text=_clean_text(user_text) or "Say hello in one short sentence.",
        system_prompt=_clean_text(system_prompt),
        is_cuda=is_cuda,
        lora=Path(cli_lora) if cli_lora else None,
        n_predict=n_predict,
        ctx=_env_int("ENGEL_LARGE_CHAT_LLM_CTX", DEFAULT_CTX),
        threads=_env_int("ENGEL_LARGE_CHAT_LLM_THREADS", DEFAULT_THREADS),
        ngl=_env_int("ENGEL_LARGE_CHAT_LLM_NGL", DEFAULT_NGL),
        temperature=_env_float("ENGEL_LARGE_CHAT_LLM_TEMPERATURE", 0.72),
    )
    # honest receipt: --lora may be silently dropped by _build_chat_cmd when the
    # binary lacks --lora support — report what the command actually contains.
    cli_lora_applied = "--lora" in command
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=max(1, int(timeout or DEFAULT_TIMEOUT_SECONDS)),
            stdin=subprocess.DEVNULL,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "status": f"large chat model inference exceeded {timeout}s",
            "large_chat_llm": status,
            "network_enabled": False,
            "provider_api_enabled": False,
            "server_enabled": False,
            "trusted_memory_write_enabled": False,
        }
    except OSError as exc:
        return {
            "ok": False,
            "status": "large chat model launch failed",
            "error": str(exc),
            "large_chat_llm": status,
            "network_enabled": False,
            "provider_api_enabled": False,
            "server_enabled": False,
            "trusted_memory_write_enabled": False,
        }

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    lowered = (stdout + stderr).lower()
    if any(marker in lowered for marker in ("server listening", "listening on", "http server")):
        return {
            "ok": False,
            "status": "server startup detected and blocked",
            "large_chat_llm": status,
            "network_enabled": False,
            "provider_api_enabled": False,
            "server_enabled": False,
            "trusted_memory_write_enabled": False,
        }
    if completed.returncode != 0:
        return {
            "ok": False,
            "status": f"large chat model exited {completed.returncode}",
            "error": stderr[:1000] or stdout[:1000],
            "large_chat_llm": status,
            "local_command_elapsed_ms": elapsed_ms,
            "network_enabled": False,
            "provider_api_enabled": False,
            "server_enabled": False,
            "trusted_memory_write_enabled": False,
        }

    reply = runner._extract_response_from_stdout(stdout, _clean_text(user_text))
    try:
        from engel_persona_guard import looks_like_discord_mouth_reply

        if looks_like_discord_mouth_reply(reply) or _reply_is_greeting_stall(reply):
            reply = ""
    except Exception:
        if "only engelz" in str(reply or "").casefold():
            reply = ""
    return {
        "ok": bool(reply),
        "status": "large local chat model replied" if reply else "large local chat model returned no readable answer",
        "assistant_reply": reply,
        "assistant_output_text": reply,
        "text": reply,
        "receipt": {
            "large_chat_llm": status,
            "large_chat_llm_used": True,
            "local_gguf_model_path": str(model),
            "large_chat_llm_lora_path": cli_lora,
            "large_chat_llm_lora_applied": cli_lora_applied,
            "large_chat_llm_lora_skipped_reason": (
                "" if cli_lora_applied else ("binary lacks --lora support" if cli_lora else "")
            ),
            "llama_cli_path": str(cli),
            "runtime_provider": "local-llama-cpp-cuda" if is_cuda else "local-llama-cpp-cpu",
            "local_command_elapsed_ms": elapsed_ms,
        },
        "large_chat_llm": status,
        "large_chat_llm_used": True,
        "local_command_elapsed_ms": elapsed_ms,
        "local_command_returncode": completed.returncode,
        "local_command_stderr_preview": stderr[:1000],
        "runtime_process_started": True,
        "model_process_started": True,
        "runtime_process_exited": True,
        "runs_inference": True,
        "loads_model": True,
        "gpu_enabled": bool(is_cuda),
        "gpu_device": "CUDA0" if is_cuda else "CPU",
        "gpu_layers": DEFAULT_NGL if is_cuda else 0,
        "network_enabled": False,
        "provider_api_enabled": False,
        "server_enabled": False,
        "trusted_memory_write_enabled": False,
        "approved_memory_write_enabled": False,
        "model_output_trusted": False,
        "model": str(model),
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Inspect or run Engel's large local chat LLM lane.")
    parser.add_argument("command", choices=["status", "run"], nargs="?", default="status")
    parser.add_argument("--prompt", default="")
    parser.add_argument("--system-prompt", default="")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_N_PREDICT)
    args = parser.parse_args(argv)
    if args.command == "status":
        print(json.dumps(large_chat_model_status(), indent=2, sort_keys=True))
        return 0
    result = run_large_chat_with_llama_cli(
        user_text=args.prompt,
        system_prompt=args.system_prompt,
        timeout=args.timeout,
        max_tokens=args.max_tokens,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
