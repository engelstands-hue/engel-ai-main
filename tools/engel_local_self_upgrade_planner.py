#!/usr/bin/env python3
"""Create a bounded self-upgrade request with CT246's local coder model.

The planner is candidate-only. It never applies source, calls a provider,
writes trusted memory, or accepts a target outside the codebase inventory.
Every proposed replace_text operation is validated against the current file
before it can enter the governed distributed-review and quorum cycle.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
for _path in (str(ROOT), str(ROOT / "tools")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import engel_codebase_inventory as inventory_runtime  # noqa: E402
import engel_self_upgrade_system as upgrade_system  # noqa: E402


PLAN_DIR = ROOT / "reports" / "self_upgrade" / "local_plans"
MAX_REQUEST_CHARS = 3000
MAX_TARGET_FILES = 3
MAX_OPERATIONS = 4
MAX_SOURCE_CONTEXT_CHARS = 14000
MAX_OPERATION_TEXT_CHARS = 16000
MAX_PLANNER_ATTEMPTS = 2
ALLOWED_SUFFIXES = {
    ".css",
    ".dart",
    ".html",
    ".json",
    ".md",
    ".ps1",
    ".py",
    ".rs",
    ".sh",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}
FORBIDDEN_PARTS = {
    ".git",
    ".venv",
    "archive",
    "cache",
    "logs",
    "models",
    "models-active",
    "node_modules",
    "reports",
    "runtime",
    "secrets",
}
FORBIDDEN_NAME_MARKERS = {
    ".env",
    "api_key",
    "bearer",
    "credential",
    "password",
    "provider_key",
    "secret",
    "token",
    "trusted_memory",
}
SURFACE_MAP = {
    "chat": "chat",
    "discord": "discord",
    "meeting_room": "meeting_room",
    "models": "models",
    "provider_bridges": "provider_bridge",
    "workers": "android_worker",
    "sub_engel": "sub_desktop",
    "storage": "storage",
    "desktop_ui": "source_patch",
    "self_upgrade": "source_patch",
}


class LocalPlannerError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _safe_relative_path(raw_path: str) -> tuple[str, Path]:
    relative = str(raw_path or "").strip().replace("\\", "/").lstrip("/")
    if not relative:
        raise LocalPlannerError("target file is empty")
    candidate = (ROOT / relative).resolve(strict=False)
    try:
        candidate.relative_to(ROOT.resolve(strict=False))
    except ValueError as exc:
        raise LocalPlannerError("target file escaped Engel root") from exc
    lowered_parts = {part.casefold() for part in Path(relative).parts}
    lowered_name = candidate.name.casefold()
    if lowered_parts & FORBIDDEN_PARTS:
        raise LocalPlannerError(f"target file is outside the source allowlist: {relative}")
    if any(marker in lowered_name for marker in FORBIDDEN_NAME_MARKERS):
        raise LocalPlannerError(f"protected target refused: {relative}")
    if candidate.suffix.casefold() not in ALLOWED_SUFFIXES:
        raise LocalPlannerError(f"unsupported source extension: {relative}")
    if not candidate.is_file():
        raise LocalPlannerError(f"target must be an existing source file: {relative}")
    if candidate.stat().st_size > upgrade_system.MAX_PATCHABLE_FILE_BYTES:
        raise LocalPlannerError(f"target is too large for the governed patch lane: {relative}")
    return relative, candidate


def _query_terms(text: str) -> list[str]:
    stop = {
        "about",
        "after",
        "again",
        "engel",
        "from",
        "have",
        "into",
        "main",
        "make",
        "should",
        "that",
        "this",
        "with",
    }
    terms = {
        token.casefold()
        for token in re.findall(r"[A-Za-z][A-Za-z0-9]{3,}", re.sub(r"[_-]+", " ", text))
        if token.casefold() not in stop
    }
    return sorted(terms, key=lambda value: (-len(value), value))[:16]


def _source_excerpt(path: Path, request_text: str, limit: int = 6000) -> str:
    text = path.read_bytes().decode("utf-8")
    if len(text) <= limit:
        return text
    lines = text.splitlines(keepends=True)
    terms = _query_terms(request_text)
    normalized_request = " ".join(
        part
        for part in re.split(r"[^a-z0-9]+", request_text.casefold())
        if part
    )
    resolution_target = "codebase" in normalized_request and "resolv" in normalized_request
    indexes = [
        index
        for index, line in enumerate(lines)
        if "codebase" in line.casefold() and "resolv" in line.casefold()
    ] if resolution_target else []
    radius = 5 if indexes else 14
    if not indexes:
        ranked_indexes: list[tuple[int, int]] = []
        for index, line in enumerate(lines):
            lowered = line.casefold()
            score = sum(max(1, len(term) // 4) for term in terms if term in lowered)
            if score:
                ranked_indexes.append((score, index))
        ranked_indexes.sort(key=lambda item: (-item[0], item[1]))
        indexes = sorted(index for _, index in ranked_indexes[:8])
    if not indexes:
        head = "".join(lines[:80])
        tail = "".join(lines[-80:])
        return (head + "\n[...middle omitted...]\n" + tail)[:limit]
    spans: list[tuple[int, int]] = []
    for index in indexes:
        start = max(0, index - radius)
        end = min(len(lines), index + radius + 1)
        if spans and start <= spans[-1][1]:
            spans[-1] = (spans[-1][0], max(spans[-1][1], end))
        else:
            spans.append((start, end))
    chunks = []
    for start, end in spans:
        chunks.append(f"[lines {start + 1}-{end}]\n" + "".join(lines[start:end]))
    return "\n[...]\n".join(chunks)[:limit]


def _human_message_literals(text: str) -> set[str]:
    messages: set[str] = set()
    patterns = (
        r'"((?:\\.|[^"\\])*)"',
        r"'((?:\\.|[^'\\])*)'",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.DOTALL):
            value = match.group(1).replace("\\n", " ").replace("\\t", " ")
            if len(re.findall(r"[A-Za-z]{3,}", value)) >= 4:
                messages.add(value)
    return messages


def _request_requires_human_message_change(request_text: str) -> bool:
    normalized = " ".join(
        part
        for part in re.split(r"[^a-z0-9]+", request_text.casefold())
        if part
    )
    return any(
        phrase in normalized
        for phrase in (
            "error message",
            "error text",
            "message when",
            "tell me",
            "tells me",
            "user facing message",
        )
    )


def _request_targets_codebase_resolution_failure(request_text: str) -> bool:
    normalized = " ".join(
        part
        for part in re.split(r"[^a-z0-9]+", request_text.casefold())
        if part
    )
    return "codebase" in normalized and "resolv" in normalized


def _canonical_old_text(current: str, proposed: str) -> str:
    if current.count(proposed) == 1:
        return proposed
    proposed_lines = proposed.splitlines()
    if not proposed_lines:
        raise LocalPlannerError("old_text is empty after line normalization")
    normalized_proposed = [line.strip() for line in proposed_lines]
    if any(not line for line in normalized_proposed):
        raise LocalPlannerError("old_text contains ambiguous blank lines")
    current_lines = current.splitlines(keepends=True)
    matches: list[str] = []
    width = len(normalized_proposed)
    for start in range(0, len(current_lines) - width + 1):
        candidate_lines = current_lines[start:start + width]
        if [line.strip() for line in candidate_lines] != normalized_proposed:
            continue
        exact = "".join(candidate_lines)
        if not proposed.endswith(("\n", "\r")):
            exact = exact.rstrip("\r\n")
        matches.append(exact)
    if len(matches) != 1:
        raise LocalPlannerError(
            "old_text does not resolve to exactly one current source block "
            f"after whitespace-only normalization (matches={len(matches)})"
        )
    return matches[0]


def _resolve_surface(
    request_text: str,
    requested_surface: str,
    inventory: dict[str, Any],
) -> tuple[str, str, dict[str, Any]]:
    explicit = str(requested_surface or "").strip()
    if explicit:
        if explicit in inventory.get("surfaces", {}):
            inventory_surface = explicit
        else:
            matches = [name for name, mapped in SURFACE_MAP.items() if mapped == explicit]
            if not matches:
                raise LocalPlannerError(f"unknown affected surface: {explicit}")
            inventory_surface = matches[0]
    else:
        resolution = inventory_runtime.resolve_failure(request_text, inventory)
        matches = resolution.get("matches")
        if not isinstance(matches, list) or not matches:
            # Keep the words "codebase" and "resolve" in this message: the
            # planner's own prompt rules target "the existing error block
            # containing both codebase and resolve" for self-upgrade requests
            # about this failure.
            raise LocalPlannerError(
                "the codebase inventory could not resolve this request to a "
                "source surface. Describe ONE specific failing surface and "
                "what it does wrong - for example: the chat quality gate, the "
                "meeting room feed, the build lane, or the device broker - "
                "and I can plan a bounded candidate for it."
            )
        inventory_surface = str(matches[0].get("surface") or "")
    cycle_surface = SURFACE_MAP.get(inventory_surface)
    if not cycle_surface:
        raise LocalPlannerError(f"surface has no governed cycle mapping: {inventory_surface}")
    surface_entry = inventory.get("surfaces", {}).get(inventory_surface)
    if not isinstance(surface_entry, dict):
        raise LocalPlannerError(f"inventory surface is missing: {inventory_surface}")
    return inventory_surface, cycle_surface, surface_entry


def _candidate_files(
    surface_entry: dict[str, Any],
    request_text: str,
    requested_files: list[Any],
) -> list[tuple[str, Path]]:
    declared = {
        str(item.get("relative_path") or "").replace("\\", "/")
        for item in surface_entry.get("files", [])
        if isinstance(item, dict)
    }
    raw_candidates = [str(value) for value in requested_files if str(value).strip()]
    if raw_candidates:
        undeclared = [
            value for value in raw_candidates if value.replace("\\", "/") not in declared
        ]
        if undeclared:
            raise LocalPlannerError(
                "requested target is not owned by the resolved surface: "
                + ", ".join(undeclared)
            )
    else:
        raw_candidates = sorted(declared)

    terms = _query_terms(request_text)
    scored: list[tuple[int, str, Path]] = []
    errors: list[str] = []
    for raw in raw_candidates:
        try:
            relative, path = _safe_relative_path(raw)
        except LocalPlannerError as exc:
            errors.append(str(exc))
            continue
        lowered = relative.casefold()
        normalized_path = " ".join(
            part
            for part in re.split(r"[^a-z0-9]+", lowered)
            if part
        )
        score = sum(8 for term in terms if term in normalized_path)
        try:
            sample = path.read_text(encoding="utf-8", errors="replace")[:120000].casefold()
            score += sum(1 for term in terms if term in sample)
        except OSError:
            pass
        scored.append((score, relative, path))
    if not scored:
        detail = errors[0] if errors else "no owned source file exists"
        raise LocalPlannerError(detail)
    scored.sort(key=lambda item: (-item[0], item[1]))
    if raw_candidates and requested_files:
        return [(relative, path) for _, relative, path in scored[:MAX_TARGET_FILES]]
    if scored[0][0] <= 0:
        raise LocalPlannerError(
            "no owned source file matched the request; describe one specific "
            "failing component or provide its target file"
        )
    # An inferred request is a one-file bounded candidate. Multiple targets
    # remain available only when the owner supplies them explicitly.
    return [(scored[0][1], scored[0][2])]


def _mentioned_declared_files(
    surface_entry: dict[str, Any],
    request_text: str,
) -> list[str]:
    """Resolve only exact inventory-owned paths named in operator text."""
    normalized_request = str(request_text or "").replace("\\", "/").casefold()
    declared = sorted(
        {
            str(item.get("relative_path") or "").strip().replace("\\", "/")
            for item in surface_entry.get("files", [])
            if isinstance(item, dict) and str(item.get("relative_path") or "").strip()
        }
    )
    return [
        relative
        for relative in declared
        if relative.casefold() in normalized_request
    ][:MAX_TARGET_FILES]


def _resolve_exact_inventory_targets(
    inventory: dict[str, Any],
    request_text: str,
    requested_files: list[Any],
) -> tuple[str, list[str]] | None:
    """Bind exact operator targets to one inventory surface before semantic routing."""
    path_owners: dict[str, dict[str, Any]] = {}
    for surface, entry in inventory.get("surfaces", {}).items():
        if not isinstance(entry, dict):
            continue
        for item in entry.get("files", []):
            if not isinstance(item, dict):
                continue
            relative = str(item.get("relative_path") or "").strip().replace("\\", "/")
            if not relative:
                continue
            key = relative.casefold()
            record = path_owners.setdefault(
                key,
                {"relative_path": relative, "surfaces": set()},
            )
            record["surfaces"].add(str(surface))

    explicit_targets = [
        str(value).strip().replace("\\", "/")
        for value in requested_files
        if str(value).strip()
    ]
    if explicit_targets:
        selected_keys: list[str] = []
        unknown: list[str] = []
        for raw in explicit_targets:
            normalized = raw[2:] if raw.startswith("./") else raw
            key = normalized.casefold()
            if key not in path_owners:
                unknown.append(raw)
                continue
            if key not in selected_keys:
                selected_keys.append(key)
        if unknown:
            raise LocalPlannerError(
                "requested target is not owned by the codebase inventory: "
                + ", ".join(unknown)
            )
    else:
        normalized_request = str(request_text or "").replace("\\", "/").casefold()
        selected_keys = sorted(
            key for key in path_owners if key in normalized_request
        )

    if not selected_keys:
        return None
    if len(selected_keys) > MAX_TARGET_FILES:
        raise LocalPlannerError(
            f"request names {len(selected_keys)} inventory files; "
            f"this bounded planner allows {MAX_TARGET_FILES}"
        )

    common_surfaces: set[str] | None = None
    for key in selected_keys:
        owners = set(path_owners[key]["surfaces"])
        common_surfaces = owners if common_surfaces is None else common_surfaces & owners
    if not common_surfaces:
        details = ", ".join(
            f"{path_owners[key]['relative_path']}="
            + "/".join(sorted(path_owners[key]["surfaces"]))
            for key in selected_keys
        )
        raise LocalPlannerError(
            "operator-named inventory files span different source surfaces: " + details
        )
    if len(common_surfaces) != 1:
        raise LocalPlannerError(
            "operator-named inventory file ownership is ambiguous across surfaces: "
            + ", ".join(sorted(common_surfaces))
            + "; provide one unambiguous target file"
        )
    inventory_surface = next(iter(common_surfaces))
    canonical_files = [
        str(path_owners[key]["relative_path"]) for key in selected_keys
    ]
    return inventory_surface, canonical_files


def _surface_verifiers(surface_entry: dict[str, Any]) -> set[str]:
    verifiers: set[str] = set()
    for item in surface_entry.get("verifiers", []):
        if not isinstance(item, dict):
            continue
        relative = str(item.get("relative_path") or "").strip().replace("\\", "/")
        if not relative.startswith("tools/verify_") or not relative.endswith(".py"):
            continue
        candidate = (ROOT / relative).resolve(strict=False)
        try:
            candidate.relative_to(ROOT.resolve(strict=False))
        except ValueError:
            continue
        if candidate.is_file():
            verifiers.add(relative)
    return verifiers


def _extract_json_object(text: str) -> dict[str, Any]:
    cleaned = str(text or "").strip()
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", cleaned):
        try:
            value, _ = decoder.raw_decode(cleaned[match.start() :])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise LocalPlannerError("local planner did not return a JSON object")


def _select_planner_model() -> tuple[str, str]:
    candidates = [
        (
            os.environ.get("ENGEL_SELF_UPGRADE_PLANNER_GGUF_MODEL", "").strip(),
            "explicit_self_upgrade_planner",
        ),
        (
            os.environ.get(
                "ENGEL_CODE_LANE_GGUF_MODEL",
                "/opt/engel/models-active/llm/qwen2.5-coder-3b-instruct/"
                "qwen2.5-coder-3b-instruct-q5_k_m.gguf",
            ).strip(),
            "structured_code_patch_planner",
        ),
        (
            os.environ.get(
                "ENGEL_MOE_REASON_GGUF_MODEL",
                "/opt/engel/models-active/llm/qwen3-30b-a3b/"
                "Qwen3-30B-A3B-Q4_K_M.gguf",
            ).strip(),
            "sparse_moe_self_upgrade_reasoning",
        ),
        (
            os.environ.get(
                "ENGEL_DEEP_REASON_GGUF_MODEL",
                "/opt/engel/models-active/llm/qwen2.5-14b-instruct/"
                "qwen2.5-14b-instruct-Q4_K_M.gguf",
            ).strip(),
            "dense_deep_reasoning_fallback",
        ),
    ]
    seen: set[str] = set()
    for model_path, reason in candidates:
        if not model_path or model_path in seen:
            continue
        seen.add(model_path)
        if Path(model_path).is_file():
            return model_path, reason
    raise LocalPlannerError("no CT246 local self-upgrade planner model is available")


def _default_model_generate(prompt: str) -> dict[str, Any]:
    model_path, selection_reason = _select_planner_model()
    from engel_local_model_service import run_llama_cpp_lora_text_with_model

    result = run_llama_cpp_lora_text_with_model(
        model_path=model_path,
        lora_path="",
        prompt="/no_think\n" + prompt,
        n_predict=1400,
        ctx=8192,
        n_gpu_layers=0,
        temperature=0.08,
        extra_system=(
            "You are Engel AI Main's local self-upgrade patch planner on CT246. "
            "Return one compact JSON object and nothing else. Never invent file "
            "content. Use only exact source excerpts supplied in the prompt. "
            "Create candidate replace_text operations only; never apply changes."
        ),
        response_format={"type": "json_object"},
    )
    reply = str(result.get("text") or result.get("stdout") or "").strip()
    if result.get("ok") is not True or not reply:
        raise LocalPlannerError(
            "local coder did not produce a plan: " + str(result.get("error") or "empty reply")[:240]
        )
    return {
        "text": reply,
        "model": model_path,
        "model_selection_reason": selection_reason,
        "model_result": {
            key: result.get(key)
            for key in (
                "adaptive_context",
                "compute_profile",
                "generation_ms",
                "model_cache_active_count",
                "model_cache_active_models",
                "model_cache_evicted",
                "model_load_ms",
            )
        } | {
            "model_selection_reason": selection_reason,
            "selective_activation": True,
            "single_resident_model": True,
            "sparse_moe_preferred": selection_reason
            == "sparse_moe_self_upgrade_reasoning",
        },
    }


def _validate_plan(
    raw_plan: dict[str, Any],
    *,
    request_text: str,
    cycle_surface: str,
    allowed_files: dict[str, Path],
    allowed_verifiers: set[str],
    severity: str,
    max_operations: int = MAX_OPERATIONS,
) -> dict[str, Any]:
    diagnosis = str(raw_plan.get("diagnosis") or "").strip()
    patch_plan = str(raw_plan.get("patch_plan") or "").strip()
    lesson = str(raw_plan.get("lesson") or "").strip()
    if not diagnosis or not patch_plan or not lesson:
        raise LocalPlannerError("local plan is missing diagnosis, patch_plan, or lesson")
    operations = raw_plan.get("operations")
    if not isinstance(operations, list) or not operations:
        raise LocalPlannerError("local plan contains no patch operations")
    if len(operations) > max_operations:
        raise LocalPlannerError(
            f"local plan contains {len(operations)} operations; "
            f"this bounded request allows {max_operations}"
        )

    validated_operations: list[dict[str, str]] = []
    changed_files: list[str] = []
    total_text = 0
    for index, operation in enumerate(operations, start=1):
        if not isinstance(operation, dict) or operation.get("op") != "replace_text":
            raise LocalPlannerError(f"operation {index} is not replace_text")
        relative = str(operation.get("file") or "").strip().replace("\\", "/")
        path = allowed_files.get(relative)
        if path is None:
            raise LocalPlannerError(f"operation {index} targets an unapproved file: {relative}")
        old_text = operation.get("old_text")
        new_text = operation.get("new_text")
        if not isinstance(old_text, str) or not old_text:
            raise LocalPlannerError(f"operation {index} old_text is empty")
        if not isinstance(new_text, str) or old_text == new_text:
            raise LocalPlannerError(f"operation {index} new_text is invalid")
        if _request_requires_human_message_change(request_text):
            old_messages = _human_message_literals(old_text)
            new_messages = _human_message_literals(new_text)
            if not (new_messages - old_messages):
                raise LocalPlannerError(
                    f"operation {index} does not add or revise a human-readable "
                    "message required by this request"
                )
        current = path.read_bytes().decode("utf-8")
        try:
            canonical_old_text = _canonical_old_text(current, old_text)
        except LocalPlannerError as exc:
            raise LocalPlannerError(
                f"operation {index} {exc} in {relative}"
            ) from exc
        if _request_targets_codebase_resolution_failure(request_text):
            normalized_old = " ".join(
                part
                for part in re.split(
                    r"[^a-z0-9]+",
                    canonical_old_text.casefold(),
                )
                if part
            )
            if "codebase" not in normalized_old or "resolv" not in normalized_old:
                raise LocalPlannerError(
                    f"operation {index} targets a nearby branch instead of the "
                    "named codebase-resolution failure"
                )
        total_text += len(canonical_old_text) + len(new_text)
        if total_text > MAX_OPERATION_TEXT_CHARS:
            raise LocalPlannerError("local plan exceeds the bounded patch text limit")
        validated_operations.append(
            {
                "op": "replace_text",
                "file": relative,
                "old_text": canonical_old_text,
                "new_text": new_text,
            }
        )
        if relative not in changed_files:
            changed_files.append(relative)

    evidence = raw_plan.get("evidence_paths")
    evidence_paths = [
        str(value)
        for value in evidence
        if isinstance(evidence, list) and isinstance(value, str) and value.strip()
    ] if isinstance(evidence, list) else []
    extra_verifiers = raw_plan.get("extra_required_verifiers")
    if extra_verifiers is not None and not isinstance(extra_verifiers, list):
        raise LocalPlannerError("extra_required_verifiers must be a list")
    extra_required_verifiers: list[str] = []
    for index, value in enumerate(extra_verifiers or [], start=1):
        relative = str(value or "").strip().replace("\\", "/")
        if relative not in allowed_verifiers:
            raise LocalPlannerError(
                f"extra verifier {index} is not an existing verifier owned by "
                f"the resolved surface: {relative}"
            )
        if relative not in extra_required_verifiers:
            extra_required_verifiers.append(relative)

    return {
        "source": "chat_ui",
        "symptom": request_text,
        "severity": severity,
        "affected_surface": cycle_surface,
        "diagnosis": diagnosis[:2400],
        "patch_plan": patch_plan[:3000],
        "files_to_change": changed_files,
        "operations": validated_operations,
        "lesson": lesson[:1600],
        "evidence_paths": evidence_paths[:12],
        "extra_required_verifiers": extra_required_verifiers[:12],
        "planner": {
            "schema": "ENGEL_LOCAL_SELF_UPGRADE_PLANNER_V1",
            "local_model_first": True,
            "provider_called": False,
            "candidate_only": True,
            "source_mutation_performed": False,
            "trusted_memory_write": False,
        },
    }


def plan_request(
    request: dict[str, Any],
    *,
    model_generate_fn: Callable[[str], dict[str, Any]] | None = None,
    inventory: dict[str, Any] | None = None,
) -> dict[str, Any]:
    request_text = str(
        request.get("request_text") or request.get("prompt") or request.get("symptom") or ""
    ).strip()
    if len(request_text) < 12:
        raise LocalPlannerError("self-upgrade request is too short to plan")
    if len(request_text) > MAX_REQUEST_CHARS:
        raise LocalPlannerError("self-upgrade request exceeds the bounded planner limit")
    severity = str(request.get("severity") or "medium").strip().casefold()
    if severity not in upgrade_system.SEVERITIES:
        raise LocalPlannerError(f"unknown severity: {severity}")

    requested_files = (
        request.get("target_files") if isinstance(request.get("target_files"), list) else []
    )
    inventory = inventory or inventory_runtime.build_inventory(ROOT)
    exact_targets = _resolve_exact_inventory_targets(
        inventory,
        request_text,
        requested_files,
    )
    requested_surface = str(request.get("affected_surface") or "")
    if exact_targets is not None:
        exact_surface, requested_files = exact_targets
        if requested_surface:
            _, requested_cycle_surface, _ = _resolve_surface(
                request_text,
                requested_surface,
                inventory,
            )
            exact_cycle_surface = SURFACE_MAP.get(exact_surface)
            if requested_cycle_surface != exact_cycle_surface:
                raise LocalPlannerError(
                    "operator-named target belongs to "
                    f"{exact_surface}, which conflicts with requested surface "
                    f"{requested_surface}"
                )
        inventory_surface, cycle_surface, surface_entry = _resolve_surface(
            request_text,
            exact_surface,
            inventory,
        )
    else:
        inventory_surface, cycle_surface, surface_entry = _resolve_surface(
            request_text,
            requested_surface,
            inventory,
        )
        requested_files = _mentioned_declared_files(surface_entry, request_text)
    selected_files = _candidate_files(surface_entry, request_text, requested_files)
    allowed_files = {relative: path for relative, path in selected_files}
    allowed_verifiers = _surface_verifiers(surface_entry)
    max_operations = (
        min(MAX_OPERATIONS, max(1, len(selected_files)))
        if requested_files
        else 1
    )

    source_sections = []
    source_chars = 0
    for relative, path in selected_files:
        remaining = MAX_SOURCE_CONTEXT_CHARS - source_chars
        if remaining <= 0:
            break
        excerpt = _source_excerpt(path, request_text, limit=min(6000, remaining))
        source_sections.append(f"FILE: {relative}\n<<<SOURCE\n{excerpt}\nSOURCE")
        source_chars += len(excerpt)

    prompt = (
        "Create one governed self-upgrade candidate for the request below.\n"
        f"REQUEST: {request_text}\n"
        f"RESOLVED_SURFACE: {cycle_surface}\n"
        f"SEVERITY: {severity}\n"
        "Return exactly this JSON shape:\n"
        '{"diagnosis":"...","patch_plan":"...","operations":['
        '{"op":"replace_text","file":"one supplied FILE path",'
        '"old_text":"exact text copied from SOURCE","new_text":"complete replacement"}],'
        '"lesson":"...","extra_required_verifiers":["tools/verify_....py"]}\n'
        f"Rules: use exactly {max_operations} replace_text operation"
        f"{'s' if max_operations != 1 else ''}; old_text must be copied exactly and "
        "must uniquely identify one current block; preserve unrelated behavior; "
        "do not alter credentials, authentication, storage, or trusted memory; "
        "when the request concerns an error or user-facing message, replace the "
        "exact message-producing block and include the complete revised message; "
        "when the request names automatic codebase resolution failure, patch the "
        "existing error block containing both codebase and resolve rather than "
        "the explicit unknown-surface branch; "
        "do not claim the patch was applied; extra_required_verifiers may use "
        "only these existing paths: "
        + json.dumps(sorted(allowed_verifiers))
        + ".\n\n"
        + "\n\n".join(source_sections)
    )
    generator = model_generate_fn or _default_model_generate
    model_result: dict[str, Any] = {}
    cycle_request: dict[str, Any] = {}
    validation_rejections: list[str] = []
    attempt_prompt = prompt
    for attempt in range(1, MAX_PLANNER_ATTEMPTS + 1):
        generated = generator(attempt_prompt)
        if not isinstance(generated, dict):
            raise LocalPlannerError("local planner adapter returned an invalid result")
        model_result = generated
        try:
            raw_plan = _extract_json_object(str(model_result.get("text") or ""))
            cycle_request = _validate_plan(
                raw_plan,
                request_text=request_text,
                cycle_surface=cycle_surface,
                allowed_files=allowed_files,
                allowed_verifiers=allowed_verifiers,
                severity=severity,
                max_operations=max_operations,
            )
            break
        except LocalPlannerError as exc:
            validation_rejections.append(str(exc)[:500])
            if attempt >= MAX_PLANNER_ATTEMPTS:
                raise
            attempt_prompt = (
                prompt
                + "\n\nThe previous candidate was rejected by the deterministic "
                "validator for this reason:\n"
                + str(exc)[:500]
                + "\nReturn a corrected JSON candidate. Copy old_text byte-for-byte "
                "from one supplied SOURCE block, keep it uniquely identifying, and "
                "address the requested behavior rather than a nearby mapping."
            )
    receipt = {
        "schema": "ENGEL_LOCAL_SELF_UPGRADE_PLAN_RECEIPT_V1",
        "ok": True,
        "status": "local candidate plan validated",
        "created_at_utc": _now(),
        "request_sha256": _sha256_text(request_text),
        "inventory_surface": inventory_surface,
        "affected_surface": cycle_surface,
        "candidate_files_considered": list(allowed_files),
        "planner_attempt_count": len(validation_rejections) + 1,
        "validation_rejections": validation_rejections,
        "cycle_request": cycle_request,
        "model": str(model_result.get("model") or "injected-local-verifier"),
        "model_result": model_result.get("model_result")
        if isinstance(model_result.get("model_result"), dict)
        else {},
        "model_selection_reason": str(
            model_result.get("model_selection_reason") or "injected-local-verifier"
        ),
        "local_model_first": True,
        "provider_called": False,
        "candidate_only": True,
        "source_mutation_performed": False,
        "trusted_memory_write": False,
    }
    PLAN_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    receipt_path = PLAN_DIR / f"ENGEL_LOCAL_SELF_UPGRADE_PLAN_{stamp}.json"
    receipt_path.write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    receipt["receipt_path"] = upgrade_system.project_relative(receipt_path)
    receipt["receipt_sha256"] = upgrade_system.sha256_file(receipt_path)
    return receipt


def _cli(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="CT246 local self-upgrade candidate planner")
    parser.add_argument("--request", required=True)
    parser.add_argument("--surface", default="")
    parser.add_argument("--severity", default="medium")
    parser.add_argument("--target-file", action="append", default=[])
    args = parser.parse_args(argv)
    try:
        result = plan_request(
            {
                "request_text": args.request,
                "affected_surface": args.surface,
                "severity": args.severity,
                "target_files": args.target_file,
            }
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except (LocalPlannerError, OSError, UnicodeDecodeError) as exc:
        print(
            json.dumps(
                {
                    "schema": "ENGEL_LOCAL_SELF_UPGRADE_PLAN_ERROR_V1",
                    "ok": False,
                    "error": str(exc),
                    "provider_called": False,
                    "source_mutation_performed": False,
                },
                indent=2,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(_cli())
