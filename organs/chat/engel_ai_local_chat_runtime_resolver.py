from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
RUNTIME_PATH_CONFIG_MANIFEST = PROJECT_ROOT / "reports" / "ai_runtime_path_config" / "manifests" / "engel_ai_local_runtime_path_config_manifest.json"
MAX_READ_CHARS = 80_000


WINDOWS_RUNTIME_CANDIDATES = [
    Path("D:/b.WorkSpace/Engel App/runtime/llama.cpp/candidates/llama-b9198-bin-win-cpu-x64/llama-cli.exe"),
    Path("D:/b.WorkSpace/Engel App/runtime/package_build/EngelAI-SubEngel-Windows-App/EngelAI-SubEngel/_internal/runtimes/llama.cpp/cuda/llama-cli.exe"),
    Path("D:/b.WorkSpace/Engel App/runtime/package_build/EngelAI-SubEngel-Windows-App/EngelAI-SubEngel/_internal/runtimes/llama.cpp/llama-cpp/llama-cli.exe"),
]

WINDOWS_MODEL_CANDIDATES = [
    Path("D:/b.WorkSpace/Engel App/models/qwen2.5-0.5b-instruct/qwen2.5-0.5b-instruct-q5_k_m.gguf"),
    Path("D:/b.WorkSpace/Engel App/models/qwen2.5-0.5b-instruct/qwen2.5-0.5b-instruct-q4_k_m.gguf"),
    Path("D:/b.WorkSpace/Engel App/models-active/qwen2.5-0.5b-instruct/qwen2.5-0.5b-instruct-q5_k_m.gguf"),
    Path("D:/b.WorkSpace/Engel App/models-active/qwen2.5-0.5b-instruct/qwen2.5-0.5b-instruct-q4_k_m.gguf"),
    Path("D:/b.WorkSpace/Engel App/models-active/llm/qwen2.5-0.5b-instruct/qwen2.5-0.5b-instruct-q5_k_m.gguf"),
    Path("D:/b.WorkSpace/Engel App/models-active/llm/qwen2.5-0.5b-instruct/qwen2.5-0.5b-instruct-q4_k_m.gguf"),
]

LINUX_RUNTIME_CANDIDATES = [
    Path("/opt/engel/runtime/llama.cpp/candidates/llama-b9198-bin-linux-x64/llama-cli"),
    Path("/opt/engel/runtime/llama.cpp/candidates/llama-b9198-bin-linux-x64-avx/llama-cli"),
    Path("/opt/engel/runtime/llama.cpp/candidates/llama-b9198-bin-linux-x86/llama-cli"),
    Path("/opt/engel/runtime/llama.cpp/candidates/llama-b9198-bin-linux/llama-cli"),
    Path("/opt/engel/runtime/llama.cpp/llama-cli"),
    Path("/usr/local/bin/llama-cli"),
    Path("/usr/bin/llama-cli"),
]

LINUX_MODEL_CANDIDATES = [
    Path("/opt/engel/models-active/llm/qwen2.5-0.5b-instruct/qwen2.5-0.5b-instruct-q5_k_m.gguf"),
    Path("/opt/engel/models-active/llm/qwen2.5-0.5b-instruct/qwen2.5-0.5b-instruct-q4_k_m.gguf"),
    Path("/opt/engel/models-active/qwen2.5-0.5b-instruct/qwen2.5-0.5b-instruct-q5_k_m.gguf"),
    Path("/opt/engel/models-active/qwen2.5-0.5b-instruct/qwen2.5-0.5b-instruct-q4_k_m.gguf"),
]


_FORBIDDEN_WINDOWS_LEGACY_DRIVES = {"e", "f", "g"}


def _is_forbidden_legacy_windows_path(path: Path) -> bool:
    if os.name != "nt":
        return False
    text = str(path).replace("\\", "/").lower()
    drive = path.drive.lower().rstrip(":")
    if drive not in _FORBIDDEN_WINDOWS_LEGACY_DRIVES:
        return False
    return "engel_app_memory" in text


def native_path_text(path: Path) -> str:
    resolved = path.resolve(strict=False)
    if os.name == "nt":
        return str(resolved).replace("/", "\\")
    return str(resolved)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace")[:MAX_READ_CHARS])
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _looks_windows_drive_path(value: str) -> bool:
    if not value:
        return False
    text = value.replace("\\\\", "\\")
    return len(text) >= 2 and text[1] == ":" and text[0].isalpha()


def _normalize_path_candidate(value: Any) -> Path | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    candidate = Path(text.replace("\\", "/"))
    if _is_forbidden_legacy_windows_path(candidate):
        return None
    if os.name != "nt" and _looks_windows_drive_path(text):
        return None
    if candidate.is_absolute():
        return candidate
    return candidate


def _first_existing(paths: list[Path]) -> Path | None:
    for candidate in paths:
        try:
            if candidate.exists() and candidate.is_file():
                return candidate
        except OSError:
            continue
    return None


def _resolve_runtime_fallback(runtime_default: Path) -> Path | None:
    runtime_scan_roots = [PROJECT_ROOT / "runtime"]
    model_default_drive = Path("D:/b.WorkSpace/Engel App/runtime")
    if model_default_drive.exists() and model_default_drive.is_dir():
        runtime_scan_roots.append(model_default_drive)

    candidates: list[Path] = []
    try:
        for root in runtime_scan_roots:
            if not root.exists() or not root.is_dir():
                continue
            for candidate in root.rglob("**/llama-cli.exe"):
                if candidate.is_file():
                    candidates.append(candidate)
    except OSError:
        candidates = []

    if candidates:
        def rank(candidate: Path) -> tuple[int, int, str]:
            text = str(candidate).lower()
            if "llama-b9198-bin-win-cpu-x64" in text:
                tier = 0
            elif "llama-b9198" in text:
                tier = 1
            elif "/runtimes/" in text.replace("\\", "/"):
                tier = 2
            else:
                tier = 3
            return (tier, len(text), text)

        candidates.sort(key=rank)
        return candidates[0]

    return runtime_default


def _resolve_model_fallback(model_default: Path) -> Path | None:
    try:
        if model_default.exists() and model_default.is_file():
            return model_default
    except OSError:
        pass

    if os.name == "nt":
        candidate_roots = WINDOWS_MODEL_CANDIDATES
    else:
        candidate_roots = LINUX_MODEL_CANDIDATES

    for candidate in candidate_roots:
        try:
            if candidate.exists() and candidate.is_file():
                return candidate
        except OSError:
            continue

    model_root = Path("/opt/engel/models-active") if os.name != "nt" else PROJECT_ROOT / "models-active"
    if model_root.exists() and model_root.is_dir():
        candidate_roots_for_scan = [model_root]
    else:
        candidate_roots_for_scan = [model_default.parent, PROJECT_ROOT / "models"]

    preferred: list[Path] = []
    try:
        for root in candidate_roots_for_scan:
            if root is None or not root.exists() or not root.is_dir():
                continue
            for candidate in root.rglob("**/qwen2.5-0.5b-instruct*.gguf"):
                preferred.append(candidate)
    except OSError:
        preferred = []

    if preferred:
        preferred.sort(key=lambda p: (0 if "q5" in p.name.lower() else 1, str(p).lower()))
        for candidate in preferred:
            if candidate.exists() and candidate.is_file():
                return candidate

    fallback_roots = [root for root in candidate_roots_for_scan if root and root.exists() and root.is_dir()]
    fallback_candidates: list[Path] = []
    try:
        for root in fallback_roots:
            if not root.exists() or not root.is_dir():
                continue
            fallback_candidates.extend(root.rglob("*.gguf"))
    except OSError:
        fallback_candidates = []

    if not fallback_candidates:
        return None
    fallback_candidates.sort(key=lambda p: (str(p).lower()))
    return fallback_candidates[0]


def resolve_runtime_and_model_paths(
    *,
    project_root: Path,
    default_runtime: Path,
    default_model: Path,
    runtime_env_var: str,
    model_env_var: str,
) -> tuple[Path, Path]:
    """Return validated runtime/model paths with host-aware defaults and safe fallbacks."""

    # Environment explicit overrides first.
    env_runtime = os.getenv(runtime_env_var, "").strip()
    env_model = os.getenv(model_env_var, "").strip()
    if env_runtime:
        candidate = _normalize_path_candidate(env_runtime)
        if candidate is not None and candidate.exists() and candidate.is_file():
            runtime_path = candidate
        else:
            runtime_path = None
    else:
        runtime_path = None

    if env_model:
        candidate = _normalize_path_candidate(env_model)
        if candidate is not None and candidate.exists() and candidate.is_file():
            model_path = candidate
        else:
            model_path = None
    else:
        model_path = None

    if runtime_path is None:
        config = read_json(project_root / "reports" / "ai_runtime_path_config" / "manifests" / "engel_ai_local_runtime_path_config_manifest.json")
        configured = _normalize_path_candidate(config.get("runtime_binary_path"))
        if configured and configured.exists() and configured.is_file():
            runtime_path = configured

    if runtime_path is None:
        candidates = WINDOWS_RUNTIME_CANDIDATES + [default_runtime] if os.name == "nt" else LINUX_RUNTIME_CANDIDATES + [default_runtime]
        runtime_path = _first_existing(candidates)
        if runtime_path is None:
            runtime_path = _resolve_runtime_fallback(default_runtime)

    if model_path is None:
        model_path = _resolve_model_fallback(default_model)
        if model_path is None:
            model_path = default_model

    return runtime_path, model_path
