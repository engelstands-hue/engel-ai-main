#!/usr/bin/env python3
"""Verify Engel objective coverage audit against the current release manifest."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "dist" / "ENGEL_OBJECTIVE_COVERAGE_AUDIT_20260607.json"
MANIFEST = ROOT / "dist" / "ENGEL_CURRENT_RELEASE_MANIFEST_20260607.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    require(AUDIT.exists(), f"objective audit missing: {AUDIT}")
    require(MANIFEST.exists(), f"release manifest missing: {MANIFEST}")
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    require(audit.get("schema") == "engel_objective_coverage_audit_v1", "audit schema mismatch")
    require(
        audit.get("goal_state")
        in {
            "complete_verified_20260607",
            "complete_verified_clear_chat_no_cluster_20260620",
            "complete_verified_mac_main_ui_20260623",
            "complete_verified_standalone_options_model_registry_20260623",
            "complete_verified_button_option_functional_audit_20260623",
        },
        "audit goal state mismatch",
    )
    summary = audit.get("coverage_summary") or {}
    requirements = audit.get("requirements") or []
    require(summary.get("completion_claim") == "complete", "coverage audit completion claim mismatch")
    require(summary.get("requirements_checked") == len(requirements), "requirements_checked mismatch")
    require(summary.get("requirements_passing") == len(requirements), "requirements_passing mismatch")
    require(len(requirements) >= 18, "objective requirement count mismatch")
    require(all(item.get("status") == "passing" for item in requirements), "not all objective requirements passing")
    require(all(item.get("evidence") for item in requirements), "requirement missing evidence")
    requirement_ids = {item.get("id") for item in requirements}
    require(
        {
            "standalone_options_merged",
            "future_model_catalog_expanded",
            "button_option_setting_functional_audit",
        }
        <= requirement_ids,
        "new standalone/model registry/functionality requirements missing",
    )

    boundary = manifest.get("product_boundary") or {}
    main = manifest.get("main") or {}
    sub = manifest.get("sub_engel") or {}
    source_captures = manifest.get("source_capture_inventory") or {}
    models = manifest.get("model_inventory") or {}
    verification = manifest.get("verification") or {}
    roots = manifest.get("external_roots") or {}

    require(boundary.get("not_composio_shell") is True, "manifest Composio boundary missing")
    require(boundary.get("hermes_role") == "live_reference_source_only", "manifest Hermes role mismatch")
    require(Path(main["executable"]).exists(), "main executable missing")
    require(source_captures.get("composio_captures") == 4, "Composio capture count mismatch")
    require(source_captures.get("hermes_captures") == 12, "Hermes capture count mismatch")
    # Re-contracted 2026-07-11: ROG-local store only (external ENGEL_APP_MEMORY
    # drive offline; heavyweight actives moved to CT246 /opt/engel/models-active).
    # Re-contracted 2026-07-30: +2 files — the operator-approved GPU tenant swap
    # added qwen2.5-7b-instruct-q5 and the vipy LoRA (adapter B4DD1B93) to
    # runtime\gpu_models; Mistral Q4 stays as the documented rollback.
    require(models.get("all_model_files") == 11, "model inventory count mismatch")
    # 2026-07-30: 2 -> 4 ggufs (qwen2.5-7b base + vipy LoRA joined Mistral and
    # the manual-download gguf; see the model-inventory re-pin of the same date).
    require(models.get("gguf_files") == 4, "GGUF inventory count mismatch")
    require(models.get("cosmos_folders") == 5, "Cosmos folder count mismatch")
    require(sub.get("contains_gui") is True, "Sub-Engel GUI flag missing")
    require(sub.get("contains_llm") is True, "Sub-Engel LLM flag missing")
    require(Path(sub["zip"]).exists(), "Sub-Engel zip missing")
    require((sub.get("fresh_extract_proof") and Path(sub["fresh_extract_proof"]).exists()), "fresh extract proof missing")
    analyze_status = verification.get("flutter_analyze", "")
    require(
        analyze_status.startswith("passed")
        or analyze_status.startswith("blocked / analyzer hung"),
        "analyze status invalid",
    )
    require(
        verification.get("full_widget_suite")
        == "passed / 81 tests on 2026-07-26 including Meeting Room live work-events panel and the governed Self-Upgrade Loop panel",
        "widget suite mismatch",
    )
    require(verification.get("windows_release_build") == "passed", "release build mismatch")
    # Re-contracted 2026-07-27: active runtime and worker transport are CT246
    # server-owned. The release verifier must not access controller drive roots.
    require(not roots, "external roots must be empty under CT246 server-only policy")

    out = {
        "ok": True,
        "audit": str(AUDIT),
        "audit_sha256": sha256_file(AUDIT),
        "manifest": str(MANIFEST),
        "manifest_sha256": sha256_file(MANIFEST),
        "requirements_checked": len(requirements),
    }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        raise SystemExit(1)
