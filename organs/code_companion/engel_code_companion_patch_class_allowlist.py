from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
MAX_PLAN_BYTES = 1024 * 1024

POLICY_VERSION = "1"
POLICY_CREATED_BY = "Engel Code Companion"

REQUIRED_GATES = {
    "auto_apply_allowed": False,
    "requires_human_review": True,
    "requires_approval_token": True,
    "requires_password_gate": True,
    "requires_verifier_pass": True,
}

ALLOWED_CLASSES = [
    "docs_only",
    "report_only_tools",
    "verifier_only",
    "isolated_code_companion_module",
    "flutter_ui_only",
]

DENIED_CLASSES = [
    "core_runtime",
    "prompts",
    "trusted_memory",
    "route_metadata",
    "live_packaging",
    "staging_packaging",
    "secrets_config",
    "startup_autorun",
    "provider_network",
    "password_gate_core",
    "approval_token_core",
]

PROTECTED_PATHS = [
    "prompts\\",
    "memory\\",
    "routes\\",
    "live\\",
    "staging\\",
    "scripts\\",
    "tools\\build",
    "tools\\package",
    "engel_global_password_gate.py",
    "engel_protected_action_registry.py",
]

COMMON_REQUIRED_CONSTRAINTS = [
    "human_review_required",
    "approval_token_required",
    "password_gate_required",
    "verifier_pass_required",
    "safe_to_auto_apply_false",
    "auto_apply_false",
]

CLASS_CONSTRAINTS = {
    "docs_only": [
        "markdown_only",
        "reports_or_docs_path_only",
        "no_prompts_memory_scripts_tools_live_staging",
    ],
    "report_only_tools": [
        "tools_report_or_status_module_only",
        "no_provider_api_cloud_browser",
        "no_subprocess_shell_execution_from_untrusted_content",
        "no_source_mutation",
        "no_route_queue_trusted_memory_mutation",
    ],
    "verifier_only": [
        "tools_verify_module_only",
        "local_read_only_or_bounded_fixture_only",
        "no_verifier_weakening",
        "no_fake_pass_behavior",
        "no_provider_api_cloud_browser",
        "no_broad_source_mutation",
    ],
    "isolated_code_companion_module": [
        "engel_code_companion_module_only",
        "no_provider_api_cloud",
        "no_wsl_hermes_docker",
        "no_background_worker",
        "no_auto_apply",
        "no_trusted_memory_write",
        "no_route_or_external_source_mutation",
        "password_token_collection_only_for_protected_gate_refusal_modules",
    ],
    "flutter_ui_only": [
        "flutter_lib_or_test_dart_only",
        "ui_or_test_only",
        "no_android_background_service",
        "no_boot_receiver",
        "no_wake_lock",
        "no_provider_cloud",
        "no_unapproved_auto_sync",
        "no_direct_engel_control",
    ],
}

SAFETY_RULES = [
    "default_deny_unknown_paths",
    "no_auto_apply",
    "human_review_required",
    "approval_token_required",
    "password_gate_required",
    "verifier_pass_required",
    "path_traversal_denied",
    "absolute_paths_outside_repo_denied",
    "provider_api_cloud_browser_denied",
    "wsl_hermes_docker_denied",
    "protected_paths_denied_by_default",
]

POLICY = {
    "policy_version": POLICY_VERSION,
    "created_by": POLICY_CREATED_BY,
    "default_policy": "deny",
    **REQUIRED_GATES,
    "allowed_classes": ALLOWED_CLASSES,
    "denied_classes": DENIED_CLASSES,
    "protected_paths": PROTECTED_PATHS,
    "safety_rules": SAFETY_RULES,
}


@dataclass(frozen=True)
class Classification:
    input_path: str
    normalized_path: str
    allowed: bool
    patch_class: str
    denied_class: str | None
    reason: str
    required_constraints: list[str]
    protected_path: bool


@dataclass(frozen=True)
class PlanValidation:
    input_path: str
    valid: bool
    target_count: int
    allowed_targets: list[dict[str, Any]]
    denied_targets: list[dict[str, Any]]
    errors: list[str]
    policy: dict[str, Any]


class PatchClassAllowlistError(ValueError):
    pass


def is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except ValueError:
        return False


def project_relative(path: Path) -> str:
    try:
        return str(path.resolve(strict=False).relative_to(PROJECT_ROOT.resolve(strict=False))).replace("/", "\\")
    except ValueError:
        return str(path.resolve(strict=False))


def normalize_path(raw_path: str | Path) -> tuple[str, str | None]:
    raw = str(raw_path or "").strip()
    if not raw:
        return "", "empty path denied"
    if raw.startswith(("http://", "https://", "\\\\")):
        return raw, "non-local path denied"
    if any(marker in raw for marker in ("*", "?", "[")):
        return raw, "wildcards denied"
    candidate = Path(raw)
    if ".." in candidate.parts:
        return raw.replace("/", "\\"), "path traversal denied"
    resolved = candidate.resolve(strict=False) if candidate.is_absolute() else (PROJECT_ROOT / candidate).resolve(strict=False)
    if not is_relative_to(resolved, PROJECT_ROOT):
        return str(resolved), "absolute path outside repo denied"
    return project_relative(resolved), None


def lower_path(normalized_path: str) -> str:
    return normalized_path.replace("/", "\\").lower()


def is_secret_or_config_path(path: str) -> bool:
    name = Path(path).name.lower()
    sensitive_names = {
        ".env",
        ".env.local",
        "config.json",
        "local_config.json",
        "secrets.json",
        "secret.json",
        "tokens.json",
        "passwords.json",
    }
    sensitive_suffixes = {".key", ".pem", ".pfx", ".p12", ".crt", ".cer"}
    if name in sensitive_names or Path(name).suffix in sensitive_suffixes:
        return True
    return any(word in name for word in ["secret", "token", "password", "credential", "api_key"])


def classify_path(raw_path: str | Path) -> dict[str, Any]:
    normalized, error = normalize_path(raw_path)
    if error:
        result = Classification(str(raw_path), normalized, False, "default_deny", None, error, [], True)
        return result.__dict__.copy()

    lower = lower_path(normalized)
    suffix = Path(lower).suffix
    protected = any(lower.startswith(prefix.lower()) for prefix in PROTECTED_PATHS) or lower in {
        "engel_global_password_gate.py",
        "engel_protected_action_registry.py",
    }

    denied_class: str | None = None
    reason = ""

    if is_secret_or_config_path(normalized):
        denied_class = "secrets_config"
        reason = "secret/config-like path denied"
    elif lower.startswith("prompts\\"):
        denied_class = "prompts"
        reason = "prompts are denied by default"
    elif lower.startswith("memory\\"):
        denied_class = "trusted_memory"
        reason = "memory/trusted-memory paths are denied by default"
    elif lower.startswith("routes\\") or "route_metadata" in lower:
        denied_class = "route_metadata"
        reason = "route metadata is denied by default"
    elif lower.startswith("live\\"):
        denied_class = "live_packaging"
        reason = "live packaging paths are denied by default"
    elif lower.startswith("staging\\"):
        denied_class = "staging_packaging"
        reason = "staging packaging paths are denied by default"
    elif lower.startswith("scripts\\"):
        denied_class = "startup_autorun"
        reason = "scripts are denied by default"
    elif lower in {"engel_global_password_gate.py", "engel_protected_action_registry.py"}:
        denied_class = "password_gate_core"
        reason = "password/protected-action core is denied by default"

    if denied_class:
        result = Classification(
            str(raw_path),
            normalized,
            False,
            "default_deny",
            denied_class,
            reason,
            COMMON_REQUIRED_CONSTRAINTS,
            True,
        )
        return result.__dict__.copy()

    patch_class = "default_deny"
    allowed = False
    constraints: list[str] = []

    if lower.startswith("reports\\") and suffix == ".md":
        patch_class = "docs_only"
        allowed = True
    elif lower.startswith("docs\\") and suffix == ".md" and (PROJECT_ROOT / "docs").exists():
        patch_class = "docs_only"
        allowed = True
    elif lower.startswith("tools\\verify_") and suffix == ".py":
        patch_class = "verifier_only"
        allowed = True
    elif lower.startswith("tools\\") and suffix == ".py" and ("report" in lower or "status" in lower):
        patch_class = "report_only_tools"
        allowed = True
    elif lower.startswith("engel_code_companion_") and suffix == ".py":
        patch_class = "isolated_code_companion_module"
        allowed = True
    elif (lower.startswith("mobile\\engel_remote_worker\\lib\\") or lower.startswith("mobile\\engel_remote_worker\\test\\")) and suffix == ".dart":
        patch_class = "flutter_ui_only"
        allowed = True

    if allowed:
        constraints = COMMON_REQUIRED_CONSTRAINTS + CLASS_CONSTRAINTS[patch_class]
        result = Classification(
            str(raw_path),
            normalized,
            True,
            patch_class,
            None,
            "allowed only when all class constraints and protected apply gates pass",
            constraints,
            protected,
        )
        return result.__dict__.copy()

    if "\\" not in lower and suffix == ".py":
        denied_class = "core_runtime"
        reason = "root runtime/source modules are denied unless isolated Code Companion modules"
    elif lower.startswith("mobile\\engel_remote_worker\\android\\"):
        denied_class = "startup_autorun"
        reason = "native Android service/manifest paths denied in this phase"
    else:
        denied_class = "core_runtime"
        reason = "unknown path denied by default"
    result = Classification(
        str(raw_path),
        normalized,
        False,
        "default_deny",
        denied_class,
        reason,
        COMMON_REQUIRED_CONSTRAINTS,
        protected,
    )
    return result.__dict__.copy()


def load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PatchClassAllowlistError(f"could not read JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise PatchClassAllowlistError("JSON root must be an object")
    return payload


def resolve_plan_input(raw_path: str | Path) -> Path:
    normalized, error = normalize_path(raw_path)
    if error:
        raise PatchClassAllowlistError(error)
    path = PROJECT_ROOT / normalized
    if path.is_dir():
        for name in ["bundle.json", "dry_run.json", "approval_receipt.json", "apply_receipt.json"]:
            candidate = path / name
            if candidate.exists():
                path = candidate
                break
    if not path.exists() or not path.is_file():
        raise PatchClassAllowlistError("plan input does not exist")
    if path.suffix.lower() != ".json":
        raise PatchClassAllowlistError("plan input must be JSON")
    if path.stat().st_size > MAX_PLAN_BYTES:
        raise PatchClassAllowlistError(f"plan input exceeds {MAX_PLAN_BYTES} bytes")
    return path


def extract_target_files(payload: dict[str, Any]) -> list[str]:
    targets: list[str] = []

    for key in ["target_files", "target_files_checked", "files_changed", "missing_target_files"]:
        value = payload.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    targets.append(item)
                elif isinstance(item, dict) and isinstance(item.get("target_file"), str):
                    targets.append(str(item["target_file"]))

    for key in ["proposed_file_drafts", "simulated_files", "target_file_hashes_before", "hashes_before", "hashes_after"]:
        value = payload.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict) and isinstance(item.get("target_file"), str):
                    targets.append(str(item["target_file"]))

    return sorted(set(target for target in targets if target.strip()))


def validate_plan(raw_path: str | Path) -> dict[str, Any]:
    try:
        path = resolve_plan_input(raw_path)
        payload = load_json_object(path)
    except PatchClassAllowlistError as exc:
        validation = PlanValidation(str(raw_path), False, 0, [], [], [str(exc)], POLICY.copy())
        return validation.__dict__.copy()

    target_files = extract_target_files(payload)
    allowed_targets: list[dict[str, Any]] = []
    denied_targets: list[dict[str, Any]] = []
    for target in target_files:
        classification = classify_path(target)
        if classification["allowed"]:
            allowed_targets.append(classification)
        else:
            denied_targets.append(classification)

    errors: list[str] = []
    if not target_files:
        errors.append("no target files found in plan input")
    for denied in denied_targets:
        errors.append(f"target denied: {denied['normalized_path']} / {denied['reason']}")

    validation = PlanValidation(
        project_relative(path),
        not errors,
        len(target_files),
        allowed_targets,
        denied_targets,
        errors,
        POLICY.copy(),
    )
    return validation.__dict__.copy()


def render_status() -> str:
    return json.dumps(POLICY, indent=2, sort_keys=True)


def render_classes() -> str:
    payload = {
        "allowed_classes": {name: CLASS_CONSTRAINTS[name] for name in ALLOWED_CLASSES},
        "denied_classes": DENIED_CLASSES,
        "default_policy": "deny",
        "auto_apply_allowed": False,
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Code Companion patch class allowlist policy.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="Show policy status.")
    classify = sub.add_parser("classify", help="Classify one local path.")
    classify.add_argument("path")
    validate = sub.add_parser("validate-plan", help="Validate target paths in a bundle or apply request JSON.")
    validate.add_argument("path")
    sub.add_parser("list-classes", help="List allowed and denied patch classes.")
    args = parser.parse_args(argv)

    if args.command == "status":
        print(render_status())
        return 0
    if args.command == "classify":
        print(json.dumps(classify_path(args.path), indent=2, sort_keys=True))
        return 0
    if args.command == "validate-plan":
        result = validate_plan(args.path)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["valid"] else 1
    if args.command == "list-classes":
        print(render_classes())
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
