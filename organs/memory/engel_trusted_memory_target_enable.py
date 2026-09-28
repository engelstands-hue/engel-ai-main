from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

import engel_global_password_gate as global_password_gate


ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
TARGET_CONTRACT_JSON = ROOT / "memory" / "ENGEL_TRUSTED_MEMORY_TARGET_CONTRACT_V1.json"
TARGET_CONTRACT_MD = ROOT / "memory" / "ENGEL_TRUSTED_MEMORY_TARGET_CONTRACT_V1.md"
ENABLE_CONTRACT_JSON = ROOT / "memory" / "ENGEL_TRUSTED_MEMORY_TARGET_ENABLE_CONTRACT_V1.json"
RECEIPT_DIR = ROOT / "reports" / "memory_promotion_receipts"

CONTRACT_ID = "ENGEL_TRUSTED_MEMORY_TARGET_ENABLE_CONTRACT_V1"
APPROVAL_PHRASE = "APPROVE_TRUSTED_MEMORY_TARGET_ENABLE_V1"
PASSWORD_ACTION_ID = "enable_trusted_memory_target"
TARGET_PATH = "memory\\ENGEL_TRUSTED_MEMORY_V1.jsonl"
DISABLED_STATUS = "disabled_until_human_target_approval"
ENABLED_STATUS = "enabled_for_password_gated_candidate_promotion"
PASS_STATUS = "TRUSTED_MEMORY_TARGET_ENABLE_PASS_REVIEW_REQUIRED"


class TrustedMemoryTargetEnableError(ValueError):
    pass


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def compact_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except ValueError:
        return False


def project_relative(path: Path) -> str:
    return str(path.resolve(strict=False).relative_to(ROOT.resolve(strict=False))).replace("/", "\\")


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TrustedMemoryTargetEnableError(f"required JSON is missing or invalid: {path.name}") from exc
    if not isinstance(data, dict):
        raise TrustedMemoryTargetEnableError(f"required JSON must be an object: {path.name}")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    resolved = path.resolve(strict=False)
    if not is_relative_to(resolved, ROOT.resolve(strict=False)):
        raise TrustedMemoryTargetEnableError("write path escaped workspace")
    path.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def safe_receipt_stem() -> str:
    return "trusted_memory_target_enable_" + compact_timestamp()


def validate_approval_phrase(phrase: str) -> None:
    if phrase != APPROVAL_PHRASE:
        raise TrustedMemoryTargetEnableError("exact target-enable approval phrase required")
    if any(marker in phrase for marker in (" ", "\t", "\n", "\r", "/", "\\", ":", "*", "?", "[", "]", ";", "&", "|")):
        raise TrustedMemoryTargetEnableError("approval phrase rejected")


def validate_contracts_for_enable() -> dict[str, Any]:
    enable_contract = read_json(ENABLE_CONTRACT_JSON)
    if enable_contract.get("contract_id") != CONTRACT_ID:
        raise TrustedMemoryTargetEnableError("target-enable contract id mismatch")
    approval = enable_contract.get("future_target_enable_approval", {})
    if not isinstance(approval, dict):
        raise TrustedMemoryTargetEnableError("target-enable approval model missing")
    if approval.get("approval_phrase") != APPROVAL_PHRASE:
        raise TrustedMemoryTargetEnableError("target-enable approval phrase mismatch")
    if approval.get("password_gate_action") != PASSWORD_ACTION_ID:
        raise TrustedMemoryTargetEnableError("target-enable password action mismatch")

    target_contract = read_json(TARGET_CONTRACT_JSON)
    target = target_contract.get("target", {})
    if not isinstance(target, dict):
        raise TrustedMemoryTargetEnableError("target contract missing target object")
    if target.get("target_path") != TARGET_PATH:
        raise TrustedMemoryTargetEnableError("target path mismatch")
    if target.get("target_format") != "jsonl":
        raise TrustedMemoryTargetEnableError("target format must be jsonl")
    if target.get("allowed_write_mode") != "append_only" or target.get("append_only") is not True:
        raise TrustedMemoryTargetEnableError("target must remain append-only")
    if target.get("max_entry_size") != 8192:
        raise TrustedMemoryTargetEnableError("target max_entry_size mismatch")
    if target.get("enabled") is True:
        if target.get("status") != ENABLED_STATUS:
            raise TrustedMemoryTargetEnableError("enabled target status mismatch")
        return {
            "target_contract": target_contract,
            "target_status_before": ENABLED_STATUS,
            "already_enabled": True,
        }
    if target.get("enabled") is not False or target.get("status") != DISABLED_STATUS:
        raise TrustedMemoryTargetEnableError("target is not in an enableable disabled state")
    return {
        "target_contract": target_contract,
        "target_status_before": DISABLED_STATUS,
        "already_enabled": False,
    }


def target_status() -> dict[str, Any]:
    try:
        state = validate_contracts_for_enable()
        target = state["target_contract"]["target"]
        return {
            "ok": True,
            "target_path": target.get("target_path"),
            "target_status": target.get("status"),
            "target_enabled": target.get("enabled"),
            "already_enabled": state["already_enabled"],
            "approval_phrase": APPROVAL_PHRASE,
            "password_action_id": PASSWORD_ACTION_ID,
            "writes_memory_entries": False,
        }
    except TrustedMemoryTargetEnableError as exc:
        return {"ok": False, "reason": str(exc), "writes_memory_entries": False}


def render_target_contract_md(data: dict[str, Any]) -> str:
    target = data["target"]
    return (
        "# Engel Trusted Memory Target Contract V1\n\n"
        "Status:\n"
        + " / ".join(str(item) for item in data.get("status", []))
        + "\n\n"
        "## Principle\n\n"
        "Memory candidates are not memory. Approved candidates are not trusted memory until written by an Engel-controlled, human-approved, verifier-checked, receipt-logged promotion flow.\n\n"
        "Engel uses Tools/AI. Tools/AI do not use Engel.\n\n"
        "## Target Decision\n\n"
        "The explicit trusted-memory target is:\n\n"
        f"- target_id: `{target.get('target_id')}`\n"
        f"- target_path: `{target.get('target_path')}`\n"
        f"- target_format: `{target.get('target_format')}`\n"
        f"- allowed_write_mode: `{target.get('allowed_write_mode')}`\n"
        f"- append_only: `{str(target.get('append_only')).lower()}`\n"
        f"- status: `{target.get('status')}`\n"
        f"- enabled: `{str(target.get('enabled')).lower()}`\n"
        f"- enabled_by_contract: `{target.get('enabled_by_contract', '')}`\n"
        f"- enablement_receipt_path: `{target.get('enablement_receipt_path', '')}`\n\n"
        "The target enablement only makes the append-only destination explicit and enabled for a later password-gated candidate promotion flow. It does not approve any memory candidate.\n\n"
        "## Direct Training Memory Exception\n\n"
        "The narrow direct training memory writer remains separate. General candidate promotion remains separately gated.\n\n"
        "## Entry Schema\n\n"
        "Allowed entry fields:\n\n"
        + "".join(f"- `{field}`\n" for field in data.get("allowed_entry_fields", []))
        + "\nBlocked entry fields:\n\n"
        + "".join(f"- `{field}`\n" for field in data.get("blocked_entry_fields", []))
        + "\n## Promotion Requirements\n\n"
        + "".join(f"- {item}\n" for item in data.get("promotion_source_requirements", []))
        + "- exact `APPROVE_PROMOTE_MEMORY_CANDIDATE` token is still required per candidate\n"
        "- Global Password Gate action `promote_memory_candidate` is still required per candidate\n\n"
        "## Safety Boundary\n\n"
        "No candidate is trusted by target enablement alone. No provider, network, model, source, route, queue, background, startup, bulk import, overwrite, truncate, delete, or git action is authorized.\n"
    )


def build_receipt(
    *,
    receipt_json_path: Path,
    receipt_md_path: Path,
    target_status_before: str,
    target_status_after: str,
    files_changed: list[str],
    already_enabled: bool,
) -> dict[str, Any]:
    timestamp = now_utc()
    seed = f"{CONTRACT_ID}|{timestamp}|{receipt_json_path.name}".encode("utf-8")
    return {
        "receipt_id": "trusted_memory_target_enable_" + hashlib.sha256(seed).hexdigest()[:16],
        "contract_id": CONTRACT_ID,
        "action_type": "trusted_memory_target_enable",
        "started_at": timestamp,
        "ended_at": timestamp,
        "target_path": TARGET_PATH,
        "target_status_before": target_status_before,
        "target_status_after": target_status_after,
        "approval_detected": True,
        "approval_phrase_name": APPROVAL_PHRASE,
        "password_gate_result": "redacted_pass",
        "verifier_results": {
            "internal_target_enable_preflight": "PASS",
            "target_enable_contract_verifier": "PASS_REQUIRED_BEFORE_ENABLE",
            "global_password_gate": "PASS_REDACTED",
        },
        "files_changed": files_changed,
        "already_enabled": already_enabled,
        "forbidden_actions_not_performed": [
            "no memory candidate promoted",
            "no trusted-memory entry appended",
            "no source mutation beyond target contract/receipt",
            "no route mutation",
            "no queue mutation",
            "no provider/network/model/local LLM",
            "no background/autorun/scheduler",
            "no git staging or commit",
            "no password/salt/hash values recorded",
        ],
        "final_status": PASS_STATUS,
        "human_review_required": True,
    }


def render_receipt_md(receipt: dict[str, Any]) -> str:
    lines = [
        "# ENGEL_TRUSTED_MEMORY_TARGET_ENABLE_V1 Receipt",
        "",
        f"- receipt_id: `{receipt['receipt_id']}`",
        f"- contract_id: `{receipt['contract_id']}`",
        f"- action_type: `{receipt['action_type']}`",
        f"- target_path: `{receipt['target_path']}`",
        f"- target_status_before: `{receipt['target_status_before']}`",
        f"- target_status_after: `{receipt['target_status_after']}`",
        f"- approval_detected: `{str(receipt['approval_detected']).lower()}`",
        f"- approval_phrase_name: `{receipt['approval_phrase_name']}`",
        "- password_gate_result: `redacted_pass`",
        f"- final_status: `{receipt['final_status']}`",
        f"- human_review_required: `{str(receipt['human_review_required']).lower()}`",
        "",
        "## Files Changed",
        "",
        *[f"- `{path}`" for path in receipt["files_changed"]],
        "",
        "## Forbidden Actions Not Performed",
        "",
        *[f"- {item}" for item in receipt["forbidden_actions_not_performed"]],
    ]
    return "\n".join(lines).rstrip() + "\n"


def enable_target(approval_phrase: str, *, password_prompt: bool) -> dict[str, Any]:
    validate_approval_phrase(approval_phrase)
    if not password_prompt:
        raise TrustedMemoryTargetEnableError("protected target-enable action requires --password-prompt")
    state = validate_contracts_for_enable()
    global_password_gate.prompt_and_require_action(PASSWORD_ACTION_ID)

    RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    stem = safe_receipt_stem()
    receipt_json_path = (RECEIPT_DIR / f"{stem}.json").resolve(strict=False)
    receipt_md_path = (RECEIPT_DIR / f"{stem}.md").resolve(strict=False)
    if not is_relative_to(receipt_json_path, RECEIPT_DIR.resolve(strict=False)):
        raise TrustedMemoryTargetEnableError("receipt path escaped receipt folder")

    target_contract = state["target_contract"]
    target = target_contract["target"]
    files_changed: list[str] = []
    if not state["already_enabled"]:
        target["status"] = ENABLED_STATUS
        target["enabled"] = True
        target["enablement_receipt_path"] = project_relative(receipt_json_path)
        target["enabled_by_contract"] = CONTRACT_ID
        write_json(TARGET_CONTRACT_JSON, target_contract)
        TARGET_CONTRACT_MD.write_text(render_target_contract_md(target_contract), encoding="utf-8")
        files_changed.extend([project_relative(TARGET_CONTRACT_JSON), project_relative(TARGET_CONTRACT_MD)])

    files_changed.extend([project_relative(receipt_json_path), project_relative(receipt_md_path)])
    receipt = build_receipt(
        receipt_json_path=receipt_json_path,
        receipt_md_path=receipt_md_path,
        target_status_before=str(state["target_status_before"]),
        target_status_after=ENABLED_STATUS,
        files_changed=files_changed,
        already_enabled=bool(state["already_enabled"]),
    )
    write_json(receipt_json_path, receipt)
    receipt_md_path.write_text(render_receipt_md(receipt), encoding="utf-8")
    return receipt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Enable the Engel trusted-memory target through the password gate.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--status", action="store_true", help="Show target-enable readiness without writing.")
    mode.add_argument("--enable", metavar="APPROVAL_PHRASE", help="Enable target using exact approval phrase.")
    parser.add_argument("--password-prompt", action="store_true", help="Prompt for global password before target enablement.")
    return parser


def main(argv: list[str] | None = None, stdout=None, stderr=None) -> int:
    out = sys.stdout if stdout is None else stdout
    err = sys.stderr if stderr is None else stderr
    args = build_parser().parse_args(argv)
    try:
        if args.password_prompt and not args.enable:
            err.write("--password-prompt is only valid with --enable.\n")
            return 2
        if args.status or not args.enable:
            out.write(json.dumps(target_status(), indent=2, sort_keys=True) + "\n")
            return 0
        if not re.fullmatch(r"APPROVE_[A-Z0-9_]+", args.enable):
            raise TrustedMemoryTargetEnableError("exact target-enable approval phrase required")
        receipt = enable_target(args.enable, password_prompt=bool(args.password_prompt))
        out.write("TRUSTED_MEMORY_TARGET_ENABLE_REVIEW_REQUIRED\n")
        out.write("receipt_path: " + str(receipt["files_changed"][-2]) + "\n")
        out.write("trusted_memory_entry_written: false\n")
        return 0
    except TrustedMemoryTargetEnableError as exc:
        err.write(f"[STOPPED] {exc}\n")
        return 2
    except global_password_gate.PasswordGateError as exc:
        err.write(f"[STOPPED] {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
