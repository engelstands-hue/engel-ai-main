#!/usr/bin/env python3
"""Fail-closed, source-only launch gate for Engel's five named curricula.

The gate never opens Flutter, sends a prompt, trains a model, contacts CT246, or
changes a service. It proves that the Training page would launch exactly five named
eight-hour curricula from current, hash-bound, historically novel material.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
for candidate in (ROOT, TOOLS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import engel_construction_corpus as construction_corpus  # noqa: E402
import run_engel_flutter_main_ui_prompt_training as ui_runner  # noqa: E402
import sync_engel_training_assets as assets  # noqa: E402
from engel_prompt_novelty import (  # noqa: E402
    DEFAULT_PACKS_DIR,
    canonical_base_prompt_sha256,
    evaluate_scheduled_prompt_novelty,
    load_prompt_history,
    material_card_sha256,
)


CANONICAL_ROOT = ROOT / "memory" / "training" / "engel_main"
TEMPLATES_ROOT = CANONICAL_ROOT / "templates"
INDEX_PATH = TEMPLATES_ROOT / "curricula_index.json"
ASSET_MANIFEST_PATH = CANONICAL_ROOT / "training_assets_manifest.json"
GENERATED_WRAPPER_PATH = CANONICAL_ROOT / "run_hour_prompt_training.ps1"
CORPUS_ROOT = ROOT / "memory" / "training" / "construction_env"

EXPECTED_CURRICULA: tuple[dict[str, str], ...] = (
    {
        "id": "capabilities",
        "title": "Engel Capabilities",
        "discipline": "engineering",
        "template": "ENGEL_TEMPLATE_CAPABILITIES.json",
    },
    {
        "id": "math_school",
        "title": "Math School",
        "discipline": "math",
        "template": "ENGEL_TEMPLATE_MATH_SCHOOL.json",
    },
    {
        "id": "self_build",
        "title": "Self-Build",
        "discipline": "engineering",
        "template": "ENGEL_TEMPLATE_SELF_BUILD.json",
    },
    {
        "id": "construction",
        "title": "Construction Coordination",
        "discipline": "aec",
        "template": "ENGEL_TEMPLATE_CONSTRUCTION.json",
    },
    {
        "id": "chat_communication",
        "title": "Chat Communication",
        "discipline": "communication",
        "template": "ENGEL_TEMPLATE_CHAT_COMMUNICATION.json",
    },
)

checks: list[dict[str, Any]] = []


def check(name: str, ok: bool, detail: Any) -> None:
    checks.append(
        {
            "name": name,
            "status": "PASS" if ok else "FAIL",
            "detail": detail
            if isinstance(detail, str)
            else json.dumps(detail, sort_keys=True, default=str),
        }
    )


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def repo_file(path: Path) -> bool:
    """True only for a regular, non-symlink file contained by this checkout."""
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(ROOT.resolve(strict=True))
    except (OSError, ValueError):
        return False
    return path.is_file() and not path.is_symlink()


def record_value(argv: list[str], name: str) -> str:
    try:
        position = argv.index(name)
    except ValueError:
        return ""
    return argv[position + 1] if position + 1 < len(argv) else ""


def run_wrapper_capture_harness(templates: dict[str, Path]) -> dict[str, Any]:
    """Execute the launcher against a harmless temporary capture runner."""
    temp_parent = ROOT / "runtime" / "temp"
    temp_parent.mkdir(parents=True, exist_ok=True)
    result: dict[str, Any] = {
        "ok": False,
        "launches": [],
        "missing_template_exit_code": None,
        "problems": [],
    }
    with tempfile.TemporaryDirectory(
        prefix="all_five_training_readiness_", dir=temp_parent
    ) as raw_temp:
        sandbox_root = Path(raw_temp)
        sandbox_canonical = sandbox_root / "memory" / "training" / "engel_main"
        sandbox_templates = sandbox_canonical / "templates"
        sandbox_tools = sandbox_root / "tools"
        sandbox_runtime = sandbox_root / "runtime" / "python310"
        for directory in (sandbox_templates, sandbox_tools, sandbox_runtime):
            directory.mkdir(parents=True, exist_ok=True)

        # The generated wrapper requires AppRoot/runtime/python310/python.exe.
        # Copy only its loaders and point PYTHONHOME at the reviewed local runtime.
        runtime_source = ROOT / "runtime" / "python310"
        for name in (
            "python.exe",
            "python3.dll",
            "python310.dll",
            "vcruntime140.dll",
            "vcruntime140_1.dll",
        ):
            source = runtime_source / name
            if not source.is_file():
                result["problems"].append(f"missing local Python runtime file: {name}")
                return result
            shutil.copy2(source, sandbox_runtime / name)

        capture_path = sandbox_root / "launch_capture.jsonl"
        stub_path = sandbox_tools / "run_engel_flutter_main_ui_prompt_training.py"
        stub_path.write_text(
            """from __future__ import annotations
import json
from pathlib import Path
import sys

capture = Path(__file__).resolve().parents[1] / "launch_capture.jsonl"
with capture.open("a", encoding="utf-8") as stream:
    stream.write(json.dumps({"script": str(Path(__file__).resolve()), "argv": sys.argv[1:]}) + "\\n")
""",
            encoding="utf-8",
        )

        sandbox_template_paths: dict[str, Path] = {}
        for curriculum_id, source in templates.items():
            target = sandbox_templates / source.name
            shutil.copy2(source, target)
            sandbox_template_paths[curriculum_id] = target

        original_root = assets.ROOT
        original_canonical_root = assets.CANONICAL_ROOT
        try:
            assets.ROOT = sandbox_root
            assets.CANONICAL_ROOT = sandbox_canonical
            wrapper_text = assets.wrapper_script(1, "scheduled")
        finally:
            assets.ROOT = original_root
            assets.CANONICAL_ROOT = original_canonical_root
        wrapper_path = sandbox_canonical / "run_hour_prompt_training.ps1"
        wrapper_path.parent.mkdir(parents=True, exist_ok=True)
        wrapper_path.write_text(wrapper_text, encoding="utf-8")

        child_env = dict(os.environ)
        child_env["PYTHONHOME"] = str(runtime_source)
        powershell = "powershell.exe" if os.name == "nt" else "powershell"
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        for expected in EXPECTED_CURRICULA:
            curriculum_id = expected["id"]
            template_path = sandbox_template_paths.get(curriculum_id)
            if template_path is None:
                result["problems"].append(
                    f"capture harness has no template for {curriculum_id}"
                )
                continue
            completed = subprocess.run(
                [
                    powershell,
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(wrapper_path),
                    "-Hours",
                    "8",
                    "-TrainingLevel",
                    "fellow",
                    "-TrainingTargets",
                    "slm,llm",
                    "-TrainingsPerHour",
                    "10",
                    "-StartIndex",
                    "1",
                    "-PerPromptTimeout",
                    "17",
                    "-Template",
                    str(template_path),
                ],
                cwd=sandbox_root,
                env=child_env,
                capture_output=True,
                text=True,
                timeout=30,
                creationflags=creationflags,
            )
            result["launches"].append(
                {
                    "curriculum": curriculum_id,
                    "template": str(template_path),
                    "exit_code": completed.returncode,
                    "stderr": (completed.stderr or "")[-1000:],
                }
            )

        captures = []
        if capture_path.is_file():
            for line in capture_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    captures.append(json.loads(line))
        problems: list[str] = []
        if len(captures) != len(EXPECTED_CURRICULA):
            problems.append(
                f"expected {len(EXPECTED_CURRICULA)} captured launches, "
                f"got {len(captures)}"
            )
        for expected, captured in zip(EXPECTED_CURRICULA, captures):
            argv = list(captured.get("argv") or [])
            curriculum_id = expected["id"]
            expected_template = sandbox_template_paths.get(curriculum_id)
            exact = {
                "--mode": "scheduled",
                "--hours": "8",
                "--training-level": "fellow",
                "--training-targets": "slm,llm",
                "--trainings-per-hour": "10",
                "--start-index": "1",
                "--per-prompt-timeout": "17",
                "--template": str(expected_template or ""),
            }
            for flag, expected_value in exact.items():
                actual = record_value(argv, flag)
                if actual != expected_value:
                    problems.append(
                        f"{curriculum_id}: {flag} expected {expected_value!r}, "
                        f"got {actual!r}"
                    )
            try:
                minutes = float(record_value(argv, "--minutes"))
            except ValueError:
                minutes = -1.0
            if minutes != 480.0:
                problems.append(
                    f"{curriculum_id}: expected derived 480 minutes, got {minutes}"
                )
            for switch in ("--local-only", "--fresh-chat"):
                if switch not in argv:
                    problems.append(f"{curriculum_id}: missing {switch}")
            if "--freshen-gpu-server" in argv:
                problems.append(
                    f"{curriculum_id}: launcher unexpectedly requested a service restart"
                )
            lifecycle_raw = record_value(argv, "--lifecycle-receipt")
            lifecycle_path = Path(lifecycle_raw) if lifecycle_raw else None
            if lifecycle_path is None or not lifecycle_path.is_file():
                problems.append(f"{curriculum_id}: lifecycle receipt was not produced")
                continue
            try:
                lifecycle = load_json(lifecycle_path)
            except (OSError, json.JSONDecodeError) as exc:
                problems.append(
                    f"{curriculum_id}: unreadable lifecycle receipt: {exc}"
                )
                continue
            controls = lifecycle.get("controls") or {}
            if not (
                lifecycle.get("status") == "COMPLETE"
                and lifecycle.get("exit_code") == 0
                and lifecycle.get("template") == str(expected_template)
                and controls.get("scheduled_hours") == 8
                and controls.get("plan_prompts") == 80
                and controls.get("requested_prompts") == 80
                and controls.get("distinct_hourly_cycles") == 8
                and controls.get("trainings_per_hour") == 10
                and controls.get("training_level") == "fellow"
                and controls.get("training_targets") == "slm,llm"
                and lifecycle.get("provider_policy") == "local_only"
                and lifecycle.get("prompt_run_claim_owner")
                == "python_runner_os_lock"
            ):
                problems.append(
                    f"{curriculum_id}: lifecycle controls do not bind the plan"
                )

        before_invalid = len(captures)
        missing_path = sandbox_templates / "DOES_NOT_EXIST.json"
        invalid = subprocess.run(
            [
                powershell,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(wrapper_path),
                "-Hours",
                "8",
                "-TrainingLevel",
                "fellow",
                "-TrainingTargets",
                "slm,llm",
                "-TrainingsPerHour",
                "10",
                "-Template",
                str(missing_path),
            ],
            cwd=sandbox_root,
            env=child_env,
            capture_output=True,
            text=True,
            timeout=30,
            creationflags=creationflags,
        )
        result["missing_template_exit_code"] = invalid.returncode
        after_invalid = (
            len(capture_path.read_text(encoding="utf-8").splitlines())
            if capture_path.is_file()
            else 0
        )
        if invalid.returncode == 0:
            problems.append("missing template unexpectedly returned success")
        if after_invalid != before_invalid:
            problems.append(
                "missing template reached Python instead of failing closed"
            )
        if "Selected curriculum template no longer exists" not in (
            (invalid.stdout or "") + (invalid.stderr or "")
        ):
            problems.append(
                "missing-template refusal did not identify the selected template"
            )

        result["problems"].extend(problems)
        result["capture_count"] = len(captures)
        result["ok"] = (
            not result["problems"]
            and len(result["launches"]) == len(EXPECTED_CURRICULA)
            and all(item["exit_code"] == 0 for item in result["launches"])
            and invalid.returncode != 0
        )
    return result


# Canonical registry and generated index.
expected_ids = [item["id"] for item in EXPECTED_CURRICULA]
expected_titles = {item["id"]: item["title"] for item in EXPECTED_CURRICULA}
source_entries = list(getattr(assets, "ALL_CURRICULA", []))
source_ids = [str(item.get("id") or "") for item in source_entries]
check(
    "source_registry_is_exactly_the_five_named_curricula",
    source_ids == expected_ids
    and {
        str(item.get("id")): str(item.get("title")) for item in source_entries
    }
    == expected_titles,
    {"expected": expected_ids, "actual": source_ids},
)

try:
    index = load_json(INDEX_PATH)
except (OSError, json.JSONDecodeError) as exc:
    index = {}
    check("generated_curricula_index_is_readable", False, str(exc))
else:
    check(
        "generated_curricula_index_is_readable",
        isinstance(index, dict)
        and index.get("schema") == "engel_training_curricula_index_v1",
        {"path": str(INDEX_PATH), "schema": index.get("schema")},
    )

index_entries = index.get("curricula") if isinstance(index, dict) else []
if not isinstance(index_entries, list):
    index_entries = []
index_ids = [
    str(item.get("id") or "")
    for item in index_entries
    if isinstance(item, dict)
]
check(
    "generated_index_contains_exactly_five_named_curricula",
    index_ids == expected_ids
    and index.get("curriculum_count") == 5
    and index.get("total_topics") == 40
    and index.get("total_prompts") == 400,
    {
        "expected": expected_ids,
        "actual": index_ids,
        "curriculum_count": index.get("curriculum_count"),
        "total_topics": index.get("total_topics"),
        "total_prompts": index.get("total_prompts"),
    },
)
index_by_id = {
    str(item.get("id")): item
    for item in index_entries
    if isinstance(item, dict) and item.get("id")
}


# Manifest source/copy bindings.
try:
    asset_manifest = load_json(ASSET_MANIFEST_PATH)
except (OSError, json.JSONDecodeError) as exc:
    asset_manifest = {}
    check("training_asset_manifest_is_readable_and_ready", False, str(exc))
else:
    check(
        "training_asset_manifest_is_readable_and_ready",
        asset_manifest.get("schema") == "engel_main_training_assets_manifest_v1"
        and asset_manifest.get("ok") is True
        and asset_manifest.get("asset_integrity_ok") is True
        and asset_manifest.get("missing") == []
        and asset_manifest.get("provider_policy") == "local_only"
        and Path(str(asset_manifest.get("canonical_root") or ""))
        == CANONICAL_ROOT,
        {
            "schema": asset_manifest.get("schema"),
            "ok": asset_manifest.get("ok"),
            "asset_integrity_ok": asset_manifest.get("asset_integrity_ok"),
            "missing": asset_manifest.get("missing"),
            "canonical_root": asset_manifest.get("canonical_root"),
        },
    )

asset_binding_problems: list[str] = []
asset_binding_count = 0
for group_name in ("scripts", "prompt_sources"):
    rows = asset_manifest.get(group_name) or []
    if not isinstance(rows, list):
        asset_binding_problems.append(f"manifest {group_name} is not a list")
        continue
    for ordinal, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            asset_binding_problems.append(
                f"{group_name}[{ordinal}] is not an object"
            )
            continue
        source = Path(str(row.get("source") or ""))
        copied = Path(str(row.get("canonical_copy") or ""))
        expected_bytes = row.get("bytes")
        expected_sha = str(row.get("sha256") or "").upper()
        if not (repo_file(source) and repo_file(copied)):
            asset_binding_problems.append(
                f"{group_name}[{ordinal}] source/copy is absent, linked, "
                "or outside the repo"
            )
            continue
        try:
            copied.resolve(strict=True).relative_to(
                CANONICAL_ROOT.resolve(strict=True)
            )
        except (OSError, ValueError):
            asset_binding_problems.append(
                f"{group_name}[{ordinal}] canonical copy is outside its root"
            )
            continue
        actual_source_sha = sha256_file(source)
        actual_copy_sha = sha256_file(copied)
        if not (
            isinstance(expected_bytes, int)
            and expected_bytes > 0
            and source.stat().st_size == expected_bytes
            and copied.stat().st_size == expected_bytes
            and actual_source_sha == expected_sha
            and actual_copy_sha == expected_sha
        ):
            asset_binding_problems.append(
                f"{group_name}[{ordinal}] bytes/SHA binding drifted"
            )
            continue
        asset_binding_count += 1
check(
    "training_source_and_canonical_copy_hash_bindings_match",
    asset_binding_count > 0 and not asset_binding_problems,
    {"verified": asset_binding_count, "problems": asset_binding_problems},
)


# Real v2 construction corpus.
corpus_bundle = construction_corpus.verify_corpus_bundle(CORPUS_ROOT)
corpus_files = corpus_bundle.get("files") or []
corpus_file_by_relative = {
    str(item.get("relative_path") or ""): item
    for item in corpus_files
    if isinstance(item, dict)
}
check(
    "real_construction_corpus_is_a_verified_v2_bundle",
    corpus_bundle.get("schema") == construction_corpus.BUNDLE_VERIFY_SCHEMA
    and corpus_bundle.get("ok") is True
    and bool(corpus_bundle.get("bundle_sha256"))
    and any(item.get("role") == "manifest" for item in corpus_files)
    and any(item.get("role") == "index" for item in corpus_files)
    and len(
        [item for item in corpus_files if item.get("role") == "extracted"]
    )
    >= 1,
    {
        "root": corpus_bundle.get("root"),
        "schema": corpus_bundle.get("schema"),
        "bundle_sha256": corpus_bundle.get("bundle_sha256"),
        "files": len(corpus_files),
        "blockers": corpus_bundle.get("blockers"),
    },
)


history = load_prompt_history(DEFAULT_PACKS_DIR)
check(
    "immutable_prompt_history_is_valid",
    history.get("ok") is True,
    {
        "packs": history.get("history_pack_count"),
        "reservations": history.get("history_valid_reservation_count"),
        "unique_prompts": history.get("history_unique_prompt_count"),
        "problems": history.get("problems"),
    },
)


# Template generation, material binding, novelty, and production scheduling.
source_by_id = {
    str(item.get("id")): item
    for item in source_entries
    if isinstance(item, dict)
}
all_prompt_hashes: set[str] = set()
all_material_hashes: set[str] = set()
canonical_templates: dict[str, Path] = {}
template_summaries: dict[str, Any] = {}
template_problems: list[str] = []
binding_problems: list[str] = []
schedule_problems: list[str] = []
aec_anchor_count = 0
aec_documents: set[str] = set()
aec_hours_with_multiple_documents = 0

previous_corpus_override = os.environ.get(construction_corpus.CORPUS_ROOT_ENV)
os.environ[construction_corpus.CORPUS_ROOT_ENV] = str(CORPUS_ROOT)
try:
    for expected in EXPECTED_CURRICULA:
        curriculum_id = expected["id"]
        index_entry = index_by_id.get(curriculum_id)
        source_entry = source_by_id.get(curriculum_id)
        expected_path = TEMPLATES_ROOT / expected["template"]
        canonical_templates[curriculum_id] = expected_path
        if not isinstance(index_entry, dict):
            template_problems.append(
                f"{curriculum_id}: missing from generated index"
            )
            continue
        if not isinstance(source_entry, dict):
            template_problems.append(
                f"{curriculum_id}: missing from source registry"
            )
            continue
        try:
            actual_path = Path(str(index_entry.get("template_path") or ""))
            actual_resolved = actual_path.resolve(strict=True)
            expected_resolved = expected_path.resolve(strict=True)
        except OSError as exc:
            template_problems.append(
                f"{curriculum_id}: template is unavailable: {exc}"
            )
            continue
        if actual_resolved != expected_resolved or not repo_file(actual_path):
            template_problems.append(
                f"{curriculum_id}: index does not select its exact template"
            )
            continue
        try:
            template = load_json(actual_path)
        except (OSError, json.JSONDecodeError) as exc:
            template_problems.append(
                f"{curriculum_id}: unreadable template: {exc}"
            )
            continue
        try:
            expected_template = assets.build_template(
                cards=source_entry["cards"],
                version=source_entry["version"],
                template_id=f"engel_template_{curriculum_id}",
                discipline=source_entry["discipline"],
                generated_grounding=(
                    source_entry.get("generated_grounding")
                    if source_entry.get("material_source")
                    == "adopted_generated"
                    else None
                ),
            )
        except Exception as exc:  # noqa: BLE001
            template_problems.append(
                f"{curriculum_id}: source build failed: "
                f"{type(exc).__name__}: {exc}"
            )
            continue
        # The generator intentionally stamps wall-clock publication time.  That
        # field cannot participate in a deterministic source/material equality
        # check; every honest rebuild would otherwise look stale immediately.
        comparable_template = dict(template)
        comparable_expected = dict(expected_template)
        comparable_template.pop("updated_at_utc", None)
        comparable_expected.pop("updated_at_utc", None)
        if comparable_template != comparable_expected:
            template_problems.append(
                f"{curriculum_id}: template differs from source/material bindings"
            )

        cycles = template.get("cycle_prompt_sets") or []
        prompts = [
            str(prompt)
            for cycle in cycles
            if isinstance(cycle, dict)
            for prompt in (cycle.get("prompts") or [])
        ]
        prompt_hashes = [
            canonical_base_prompt_sha256(prompt) for prompt in prompts
        ]
        cross_duplicates = sorted(
            set(prompt_hashes).intersection(all_prompt_hashes)
        )
        all_prompt_hashes.update(prompt_hashes)
        controls = template.get("scheduled_controls") or {}
        metadata_ok = (
            template.get("schema")
            == "engel_main_scheduled_prompt_training_template_v2"
            and template.get("template_id")
            == f"engel_template_{curriculum_id}"
            and template.get("training_discipline") == expected["discipline"]
            and template.get("material_version") == source_entry.get("version")
            and index_entry.get("title") == expected["title"]
            and index_entry.get("discipline") == expected["discipline"]
            and index_entry.get("version") == source_entry.get("version")
            and index_entry.get("material_source")
            == source_entry.get("material_source")
            and index_entry.get("generated_source_id")
            == source_entry.get("generated_source_id")
            and assets.generated_grounding_metadata(index_entry)
            == assets.generated_grounding_metadata(source_entry)
            and index_entry.get("maximum_hours") == 8
            and index_entry.get("topic_count") == 8
            and index_entry.get("prompt_count") == 80
            and index_entry.get("topics") == template.get("material_topics")
            and index_entry.get("novelty_ready") is True
            and index_entry.get("novelty_fully_ready") is True
            and index_entry.get("novelty_status") == "READY"
            and index_entry.get("novel_hours_available") == 8
            and index_entry.get("novel_complete_cycle_count") == 8
            and index_entry.get("replayed_prompt_count") == 0
            and index_entry.get("history_snapshot_sha256")
            == history.get("history_snapshot_sha256")
            and controls.get("maximum_hours") == 8
            and template.get("maximum_scheduled_prompt_count") == 80
            and len(cycles) == 8
            and [
                cycle.get("cycle")
                for cycle in cycles
                if isinstance(cycle, dict)
            ]
            == list(range(1, 9))
            and all(
                isinstance(cycle, dict)
                and cycle.get("fresh_material") is True
                and cycle.get("prompt_count") == 10
                and len(cycle.get("prompts") or []) == 10
                and cycle.get("material_topic")
                for cycle in cycles
            )
            and len(prompts) == 80
            and len(set(prompt_hashes)) == 80
            and not cross_duplicates
        )
        if not metadata_ok:
            template_problems.append(
                f"{curriculum_id}: not a complete distinct 8h/80 READY plan"
            )

        novelty = evaluate_scheduled_prompt_novelty(
            prompts, DEFAULT_PACKS_DIR
        )
        if not (
            novelty.get("ok") is True
            and novelty.get("decision") == "PASS"
            and novelty.get("planned_prompt_count") == 80
            and novelty.get("planned_unique_prompt_count") == 80
            and novelty.get("novel_prompt_count") == 80
            and novelty.get("replayed_prompt_count") == 0
        ):
            template_problems.append(
                f"{curriculum_id}: current history does not prove 80 novel prompts"
            )

        for hour, cycle in enumerate(cycles, start=1):
            if not isinstance(cycle, dict):
                binding_problems.append(
                    f"{curriculum_id} hour {hour}: cycle is not an object"
                )
                continue
            card = cycle.get("material_card")
            if not isinstance(card, dict):
                binding_problems.append(
                    f"{curriculum_id} hour {hour}: no material card"
                )
                continue
            try:
                card_hash = material_card_sha256(card)
            except (TypeError, ValueError) as exc:
                binding_problems.append(
                    f"{curriculum_id} hour {hour}: invalid material: {exc}"
                )
                continue
            if card_hash in all_material_hashes:
                binding_problems.append(
                    f"{curriculum_id} hour {hour}: duplicate material identity"
                )
            all_material_hashes.add(card_hash)
            artifacts = card.get("artifacts")
            if not isinstance(artifacts, list) or not artifacts:
                binding_problems.append(
                    f"{curriculum_id} hour {hour}: no grounding artifacts"
                )
                continue
            if expected["discipline"] == "aec":
                for raw_path in artifacts:
                    path = ROOT / str(raw_path)
                    if not repo_file(path):
                        binding_problems.append(
                            f"{curriculum_id} hour {hour}: "
                            f"missing/unsafe corpus artifact {raw_path}"
                        )
                        continue
                    try:
                        relative = path.resolve(strict=True).relative_to(
                            CORPUS_ROOT.resolve(strict=True)
                        ).as_posix()
                    except (OSError, ValueError):
                        binding_problems.append(
                            f"{curriculum_id} hour {hour}: "
                            "artifact is outside the v2 corpus"
                        )
                        continue
                    bound = corpus_file_by_relative.get(relative)
                    if not isinstance(bound, dict) or not (
                        bound.get("bytes") == path.stat().st_size
                        and str(bound.get("sha256") or "").upper()
                        == sha256_file(path)
                    ):
                        binding_problems.append(
                            f"{curriculum_id} hour {hour}: "
                            "artifact lacks a valid v2 binding"
                        )
                anchors = card.get("evidence_anchors")
                packet = construction_corpus.build_prompt_evidence_context(
                    anchors if isinstance(anchors, list) else [],
                    CORPUS_ROOT,
                )
                records = packet.get("records") or []
                identities = {
                    (
                        str(item.get("document") or ""),
                        str(item.get("section") or ""),
                    )
                    for item in records
                    if isinstance(item, dict)
                }
                expected_identities = {
                    (
                        str(item.get("document") or ""),
                        str(item.get("section") or ""),
                    )
                    for item in (anchors or [])
                    if isinstance(item, dict)
                }
                if not (
                    packet.get("ok") is True
                    and packet.get("corpus_bundle_sha256")
                    == corpus_bundle.get("bundle_sha256")
                    and len(records) == len(anchors or [])
                    and identities == expected_identities
                    and all(
                        int(item.get("page") or 0) > 0
                        and len(str(item.get("quote") or "").split()) >= 5
                        for item in records
                        if isinstance(item, dict)
                    )
                ):
                    binding_problems.append(
                        f"{curriculum_id} hour {hour}: "
                        "evidence anchors do not resolve exactly"
                    )
                aec_anchor_count += len(records)
                packet_documents = set(packet.get("documents") or [])
                aec_documents.update(packet_documents)
                if len(packet_documents) > 1:
                    aec_hours_with_multiple_documents += 1
            else:
                records = card.get("_grounding_artifact_records")
                if not isinstance(records, list) or len(records) != len(
                    artifacts
                ):
                    binding_problems.append(
                        f"{curriculum_id} hour {hour}: "
                        "artifact binding count differs"
                    )
                    continue
                for raw_path, record in zip(artifacts, records):
                    path = ROOT / str(raw_path)
                    if not isinstance(record, dict) or not repo_file(path):
                        binding_problems.append(
                            f"{curriculum_id} hour {hour}: "
                            f"missing/unsafe artifact {raw_path}"
                        )
                        continue
                    if not (
                        record.get("path")
                        == Path(str(raw_path)).as_posix()
                        and record.get("resolved_path")
                        == str(path.resolve(strict=True))
                        and record.get("bytes") == path.stat().st_size
                        and str(record.get("sha256") or "").upper()
                        == sha256_file(path)
                    ):
                        binding_problems.append(
                            f"{curriculum_id} hour {hour}: "
                            f"byte/SHA binding drifted for {raw_path}"
                        )

        try:
            preflight = ui_runner._prepare_session_preflight(
                mode="scheduled",
                template_path=str(actual_path),
                template_cycle=1,
                scheduled_hours=8,
                training_level="fellow",
                trainings_per_hour=10,
                start_index=1,
            )
            ui_runner._require_session_preflight(preflight)
        except Exception as exc:  # noqa: BLE001
            schedule_problems.append(
                f"{curriculum_id}: {type(exc).__name__}: {exc}"
            )
        else:
            schedule = preflight.get("schedule") or {}
            schedule_entries = preflight.get("schedule_entries") or []
            hourly_cycles = schedule.get("hourly_cycles") or []
            if not (
                preflight.get("template_cycle_effective") == 1
                and not preflight.get("prompt_novelty_auto_advance")
                and (preflight.get("prompt_novelty") or {}).get("decision")
                == "PASS"
                and schedule.get("discipline") == expected["discipline"]
                and schedule.get("trainings_per_hour") == 10
                and len(schedule_entries) == 80
                and len(hourly_cycles) == 8
                and len(
                    {
                        item.get("material_topic")
                        for item in hourly_cycles
                    }
                )
                == 8
                and all(
                    item.get("selected_prompt_count") == 10
                    for item in hourly_cycles
                )
                and all(
                    item.get("discipline") == expected["discipline"]
                    for item in schedule_entries
                )
            ):
                schedule_problems.append(
                    f"{curriculum_id}: preflight did not compose exact 8h/80"
                )
            if expected["discipline"] == "aec" and not (
                len(preflight.get("aec_evidence_preflight") or []) == 8
                and all(
                    entry.get("aec_evidence_bundle_sha256")
                    == corpus_bundle.get("bundle_sha256")
                    and entry.get("aec_expected_documents")
                    and entry.get("aec_evidence_records")
                    and "Verified local evidence packet"
                    in str(entry.get("prompt") or "")
                    for entry in schedule_entries
                )
            ):
                schedule_problems.append(
                    f"{curriculum_id}: verified evidence missing from prompts"
                )
        template_summaries[curriculum_id] = {
            "hours": len(cycles),
            "prompts": len(prompts),
            "unique_prompts": len(set(prompt_hashes)),
            "novel_prompts": novelty.get("novel_prompt_count"),
            "discipline": template.get("training_discipline"),
            "material_source": source_entry.get("material_source"),
            "generated_source_id": source_entry.get("generated_source_id"),
        }
finally:
    if previous_corpus_override is None:
        os.environ.pop(construction_corpus.CORPUS_ROOT_ENV, None)
    else:
        os.environ[
            construction_corpus.CORPUS_ROOT_ENV
        ] = previous_corpus_override

check(
    "five_templates_match_source_and_ready_index_metadata",
    not template_problems and len(template_summaries) == 5,
    {"templates": template_summaries, "problems": template_problems},
)
check(
    "all_400_base_prompts_are_distinct_and_history_novel",
    len(all_prompt_hashes) == 400
    and not template_problems
    and history.get("ok") is True,
    {
        "expected": 400,
        "actual": len(all_prompt_hashes),
        "history_unique": history.get("history_unique_prompt_count"),
    },
)
check(
    "all_40_material_cards_have_valid_hash_bindings",
    len(all_material_hashes) == 40 and not binding_problems,
    {
        "material_cards": len(all_material_hashes),
        "aec_anchors": aec_anchor_count,
        "aec_documents": sorted(aec_documents),
        "aec_multi_document_hours": aec_hours_with_multiple_documents,
        "problems": binding_problems,
    },
)
check(
    "production_preflight_composes_all_five_eight_hour_plans",
    not schedule_problems and len(template_summaries) == 5,
    schedule_problems,
)


# Scheduled mode must never fall back to a prompt bank or another template.
selection_problems: list[str] = []
for missing in (None, str(TEMPLATES_ROOT / "DOES_NOT_EXIST.json")):
    try:
        ui_runner._load_training_schedule(
            missing,
            "scheduled",
            1,
            8,
            "fellow",
            10,
        )
    except Exception:
        pass
    else:
        selection_problems.append(
            f"scheduled loader accepted missing selection {missing!r}"
        )
check(
    "scheduled_runner_requires_exact_template_without_fallback",
    not selection_problems,
    selection_problems,
)

try:
    generated_wrapper = GENERATED_WRAPPER_PATH.read_text(
        encoding="utf-8-sig"
    )
except OSError as exc:
    generated_wrapper = ""
    check("generated_wrapper_matches_reviewed_generator", False, str(exc))
else:
    expected_wrapper = assets.wrapper_script(1, "scheduled")
    check(
        "generated_wrapper_matches_reviewed_generator",
        generated_wrapper == expected_wrapper,
        {
            "path": str(GENERATED_WRAPPER_PATH),
            "generated_sha256": hashlib.sha256(
                generated_wrapper.encode("utf-8")
            ).hexdigest(),
            "expected_sha256": hashlib.sha256(
                expected_wrapper.encode("utf-8")
            ).hexdigest(),
        },
    )

try:
    wrapper_harness = run_wrapper_capture_harness(canonical_templates)
except Exception as exc:  # noqa: BLE001
    wrapper_harness = {
        "ok": False,
        "problems": [f"{type(exc).__name__}: {exc}"],
    }
check(
    "wrapper_launches_all_five_controls_into_non_ui_capture_stub",
    wrapper_harness.get("ok") is True,
    wrapper_harness,
)


failed = [item for item in checks if item["status"] != "PASS"]
print(
    json.dumps(
        {
            "schema": "engel_all_five_training_readiness_verifier_v1",
            "status": "FAIL" if failed else "PASS",
            "passed": len(checks) - len(failed),
            "total": len(checks),
            "failed": [item["name"] for item in failed],
            "checks": checks,
        },
        indent=2,
        sort_keys=True,
    )
)
raise SystemExit(1 if failed else 0)
