#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_ROOT = Path(r"D:\b.WorkSpace\Engel App")
CONTRACT_RELATIVE = Path("memory") / "ENGEL_DEBRUIJN_QUANTUM_AUTOMATION_FILE_STRUCTURE_CONTRACT_V1.json"
REPORT_ROOT_RELATIVE = Path("reports") / "debruijn_quantum_file_structure"
LATEST_STATUS_JSON_NAME = "latest_status.json"
LATEST_STATUS_MD_NAME = "latest_status.md"


SAFETY_FLAGS = {
    "backend_only": True,
    "ui_off": True,
    "companion_card_off": True,
    "viewer_off": True,
    "quantum_inspired_only": True,
    "real_quantum_off": True,
    "provider_api_off": True,
    "network_off": True,
    "model_inference_off": True,
    "background_worker_off": True,
    "startup_autorun_off": True,
    "apply_off": True,
    "file_move_delete_rewrite_off": True,
    "trusted_memory_write_off": True,
    "route_queue_mutation_off": True,
    "candidate_execution_off": True,
    "human_review_required_for_apply": True,
}


FALSE_CAPABILITY_FIELDS = {
    "ui_enabled": False,
    "companion_card_enabled": False,
    "viewer_enabled": False,
    "manual_scan_button_enabled": False,
    "real_quantum_enabled": False,
    "provider_api_enabled": False,
    "network_enabled": False,
    "model_inference_enabled": False,
    "background_worker_enabled": False,
    "startup_autorun_enabled": False,
    "apply_enabled": False,
    "file_mutation_enabled": False,
    "trusted_memory_write_enabled": False,
    "route_mutation_enabled": False,
    "queue_mutation_enabled": False,
}


def _utc_mtime(path: Path) -> str | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat().replace("+00:00", "Z")
    except OSError:
        return None


def _relative_path(root: Path, path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve(strict=False).relative_to(root.resolve(strict=False))).replace("/", "\\")
    except (OSError, ValueError):
        return str(path)


def _safe_root(root: Path | str | None) -> tuple[Path | None, list[str]]:
    warnings: list[str] = []
    raw_root = str(DEFAULT_ROOT if root is None else root)
    if raw_root.startswith("\\\\") or raw_root.startswith("//") or "://" in raw_root:
        return None, ["Network, URI, or provider-style roots are not allowed for the status helper."]
    try:
        resolved = Path(raw_root).resolve(strict=False)
    except OSError as exc:
        return None, [f"Root could not be resolved safely: {exc}"]
    if str(resolved).startswith("\\\\") or str(resolved).startswith("//"):
        return None, ["Resolved root is a network path; no files were read."]
    if not resolved.exists() or not resolved.is_dir():
        warnings.append("Root is missing or is not a directory; no files were read.")
    return resolved, warnings


def _load_json(path: Path, label: str, warnings: list[str]) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as exc:
        warnings.append(f"{label} contains invalid JSON: {exc}")
    except OSError as exc:
        warnings.append(f"{label} could not be read: {exc}")
    return None


def _latest_file(folder: Path, pattern: str, warnings: list[str]) -> Path | None:
    try:
        candidates = [path for path in folder.glob(pattern) if path.is_file()]
    except OSError as exc:
        warnings.append(f"Could not list {pattern}: {exc}")
        return None
    if not candidates:
        return None
    return sorted(candidates, key=lambda path: (_mtime_sort_value(path), path.name))[-1]


def load_debruijn_quantum_contract(root: Path | str | None = None) -> dict[str, Any]:
    resolved_root, warnings = _safe_root(root)
    if resolved_root is None or not resolved_root.exists() or not resolved_root.is_dir():
        return {}
    contract = _load_json(resolved_root / CONTRACT_RELATIVE, "contract JSON", warnings)
    return contract if isinstance(contract, dict) else {}


def find_latest_debruijn_receipt(root: Path | str | None = None) -> Path | None:
    resolved_root, warnings = _safe_root(root)
    if resolved_root is None or not resolved_root.exists() or not resolved_root.is_dir():
        return None
    return _latest_file(resolved_root / REPORT_ROOT_RELATIVE, "automation_receipt_*.md", warnings)


def find_latest_debruijn_proposal(root: Path | str | None = None) -> Path | None:
    resolved_root, warnings = _safe_root(root)
    if resolved_root is None or not resolved_root.exists() or not resolved_root.is_dir():
        return None
    return _latest_file(resolved_root / REPORT_ROOT_RELATIVE, "candidate_fix_proposals_*.json", warnings)


def _mtime_sort_value(path: Path) -> int:
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return -1


def _count_transitions(records: list[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        for code in record.get("transition_codes", []) or []:
            key = str(code)
            counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _count_reports(records: list[Any]) -> int:
    count = 0
    for record in records:
        if not isinstance(record, dict):
            continue
        path = str(record.get("path", "")).replace("/", "\\").lower()
        if record.get("debruijn_node") == "110" or path.startswith("reports\\"):
            count += 1
    return count


def _count_candidates(records: list[Any]) -> int:
    count = 0
    for record in records:
        if not isinstance(record, dict):
            continue
        candidate_nodes = record.get("candidate_nodes")
        if isinstance(candidate_nodes, list) and candidate_nodes:
            count += 1
    return count


def _count_incomplete_entanglement(groups: list[Any]) -> int:
    count = 0
    for group in groups:
        if not isinstance(group, dict):
            continue
        missing = group.get("missing_files")
        status = str(group.get("status", "")).lower()
        if (isinstance(missing, list) and missing) or (status and status not in {"complete", "ok", "passed"}):
            count += 1
    return count


def _empty_status(root: Path | None, warnings: list[str], missing_outputs: list[str]) -> dict[str, Any]:
    return {
        "available": False,
        "status_source": "existing_reports_only",
        "backend_only": True,
        "message": "No existing De Bruijn scan/report status is available. The helper did not run a scan or write files.",
        "root": str(root) if root is not None else None,
        "contract_present": False,
        "contract_status": None,
        "automation_scope": None,
        "quantum_mode": None,
        **FALSE_CAPABILITY_FIELDS,
        "node_counts": {},
        "transition_counts": {},
        "file_count": 0,
        "unknown_count": 0,
        "candidate_count": 0,
        "report_count": 0,
        "proposal_count": 0,
        "proposal_type_counts": {},
        "proposal_safety_ok": True,
        "incomplete_entanglement_count": 0,
        "scan_truncated": False,
        "latest_status_path": None,
        "latest_status_md_path": None,
        "latest_receipt_path": None,
        "latest_proposal_path": None,
        "last_updated": None,
        "safety_flags": dict(SAFETY_FLAGS),
        "missing_outputs": sorted(set(missing_outputs)),
        "warnings": warnings,
        "human_review_required": True,
    }


def _apply_contract(status: dict[str, Any], contract: dict[str, Any] | None) -> None:
    if not contract:
        return
    status["contract_present"] = True
    status["contract_status"] = contract.get("status")
    status["automation_scope"] = contract.get("automation_scope")
    status["quantum_mode"] = contract.get("quantum_computation_mode") or "quantum_inspired_only_no_real_quantum_execution"
    status["real_quantum_enabled"] = bool(contract.get("real_quantum_execution_enabled", False))
    status["provider_api_enabled"] = bool(contract.get("provider_api_enabled", False))
    status["network_enabled"] = bool(contract.get("network_enabled", False))
    status["model_inference_enabled"] = bool(contract.get("model_inference_enabled", False))
    status["background_worker_enabled"] = bool(contract.get("background_worker_enabled", False))
    status["startup_autorun_enabled"] = bool(contract.get("startup_autorun_enabled", False))
    status["apply_enabled"] = bool(contract.get("apply_command_enabled", False))
    status["file_mutation_enabled"] = bool(contract.get("file_mutation_enabled", False))
    status["trusted_memory_write_enabled"] = bool(contract.get("trusted_memory_write_enabled", False))
    status["route_mutation_enabled"] = bool(contract.get("route_mutation_enabled", False))
    status["queue_mutation_enabled"] = bool(contract.get("queue_mutation_enabled", False))
    status["human_review_required"] = bool(contract.get("human_approval_required", True))
    status["safety_flags"] = {
        **SAFETY_FLAGS,
        "real_quantum_off": not status["real_quantum_enabled"],
        "provider_api_off": not status["provider_api_enabled"],
        "network_off": not status["network_enabled"],
        "model_inference_off": not status["model_inference_enabled"],
        "background_worker_off": not status["background_worker_enabled"],
        "startup_autorun_off": not status["startup_autorun_enabled"],
        "apply_off": not status["apply_enabled"],
        "file_move_delete_rewrite_off": not status["file_mutation_enabled"],
        "trusted_memory_write_off": not status["trusted_memory_write_enabled"],
        "route_queue_mutation_off": not (status["route_mutation_enabled"] or status["queue_mutation_enabled"]),
    }


def _apply_latest_status(status: dict[str, Any], latest: dict[str, Any], status_path: Path, root: Path) -> None:
    records = latest.get("records", [])
    if not isinstance(records, list):
        records = []
        status["warnings"].append("latest_status.json records field is malformed; record-derived counts are zero.")
    node_counts = latest.get("node_counts", {})
    if not isinstance(node_counts, dict):
        node_counts = {}
        status["warnings"].append("latest_status.json node_counts field is malformed.")
    groups = latest.get("entanglement_groups", [])
    if not isinstance(groups, list):
        groups = []
        status["warnings"].append("latest_status.json entanglement_groups field is malformed.")

    status["available"] = True
    status["message"] = "Existing De Bruijn report status loaded. No scan was run and no files were written."
    status["latest_status_path"] = _relative_path(root, status_path)
    status["node_counts"] = node_counts
    status["transition_counts"] = _count_transitions(records)
    status["file_count"] = int(latest.get("files_reported_count") or len(records))
    status["unknown_count"] = int(node_counts.get("unknown", 0) or sum(1 for record in records if isinstance(record, dict) and record.get("debruijn_node") == "unknown"))
    status["candidate_count"] = _count_candidates(records)
    status["report_count"] = _count_reports(records)
    status["incomplete_entanglement_count"] = _count_incomplete_entanglement(groups)
    status["scan_truncated"] = bool(latest.get("scan_truncated", False))
    status["last_updated"] = latest.get("scan_completed_at") or _utc_mtime(status_path)


def _apply_latest_proposal(status: dict[str, Any], proposal: dict[str, Any], proposal_path: Path, root: Path) -> None:
    status["latest_proposal_path"] = _relative_path(root, proposal_path)
    proposals = proposal.get("proposals", [])
    if not isinstance(proposals, list):
        status["warnings"].append("Latest candidate proposal JSON has malformed proposals field.")
        status["proposal_safety_ok"] = False
        proposals = []
    status["proposal_count"] = int(proposal.get("proposal_count") or len(proposals))
    proposal_type_counts: dict[str, int] = {}
    safety_ok = True

    if proposal.get("status") not in {None, "untrusted_candidate"}:
        status["warnings"].append("Latest candidate proposal top-level status is not untrusted_candidate.")
        safety_ok = False
    if proposal.get("apply_allowed") is not False:
        status["warnings"].append("Latest candidate proposal top-level apply_allowed is not false.")
        safety_ok = False
    if proposal.get("human_review_required") is not True:
        status["warnings"].append("Latest candidate proposal top-level human_review_required is not true.")
        safety_ok = False

    for index, item in enumerate(proposals):
        if not isinstance(item, dict):
            status["warnings"].append(f"Proposal item {index} is malformed.")
            safety_ok = False
            continue
        proposal_type = str(item.get("proposal_type") or "unknown")
        proposal_type_counts[proposal_type] = proposal_type_counts.get(proposal_type, 0) + 1
        if item.get("trust_status") != "untrusted_candidate":
            status["warnings"].append(f"Proposal item {index} trust_status is not untrusted_candidate.")
            safety_ok = False
        if item.get("apply_allowed") is not False:
            status["warnings"].append(f"Proposal item {index} apply_allowed is not false.")
            safety_ok = False
        if item.get("human_review_required") is not True:
            status["warnings"].append(f"Proposal item {index} human_review_required is not true.")
            safety_ok = False

    status["proposal_type_counts"] = dict(sorted(proposal_type_counts.items()))
    status["proposal_safety_ok"] = safety_ok


def build_debruijn_quantum_structure_status(root: Path | str | None = None) -> dict[str, Any]:
    resolved_root, root_warnings = _safe_root(root)
    missing_outputs: list[str] = []
    warnings = list(root_warnings)
    status = _empty_status(resolved_root, warnings, missing_outputs)
    if resolved_root is None or not resolved_root.exists() or not resolved_root.is_dir():
        status["warnings"] = warnings
        status["missing_outputs"] = sorted({"latest_status.json"})
        return status

    contract_path = resolved_root / CONTRACT_RELATIVE
    contract = _load_json(contract_path, "contract JSON", warnings)
    if contract is None:
        missing_outputs.append(str(CONTRACT_RELATIVE))
    _apply_contract(status, contract)

    report_root = resolved_root / REPORT_ROOT_RELATIVE
    latest_status_path = report_root / LATEST_STATUS_JSON_NAME
    latest_status_md_path = report_root / LATEST_STATUS_MD_NAME

    if not report_root.exists():
        warnings.append("De Bruijn report folder does not exist; no report status was loaded.")
        missing_outputs.append(str(REPORT_ROOT_RELATIVE / LATEST_STATUS_JSON_NAME))
        status["missing_outputs"] = sorted(set(missing_outputs))
        return status

    if latest_status_md_path.exists():
        status["latest_status_md_path"] = _relative_path(resolved_root, latest_status_md_path)
    else:
        missing_outputs.append(str(REPORT_ROOT_RELATIVE / LATEST_STATUS_MD_NAME))

    latest_status = _load_json(latest_status_path, "latest_status.json", warnings)
    if latest_status is None:
        missing_outputs.append(str(REPORT_ROOT_RELATIVE / LATEST_STATUS_JSON_NAME))
    else:
        _apply_latest_status(status, latest_status, latest_status_path, resolved_root)

    latest_receipt = _latest_file(report_root, "automation_receipt_*.md", warnings)
    if latest_receipt is None:
        warnings.append("No automation receipt exists yet; latest_receipt_path is null.")
    else:
        status["latest_receipt_path"] = _relative_path(resolved_root, latest_receipt)

    latest_proposal = _latest_file(report_root, "candidate_fix_proposals_*.json", warnings)
    if latest_proposal is not None:
        proposal = _load_json(latest_proposal, "latest candidate proposal JSON", warnings)
        if proposal is None:
            status["latest_proposal_path"] = _relative_path(resolved_root, latest_proposal)
            status["proposal_safety_ok"] = False
        else:
            _apply_latest_proposal(status, proposal, latest_proposal, resolved_root)

    status["warnings"] = warnings
    status["missing_outputs"] = sorted(set(missing_outputs))
    return status


def _print_text_status(status: dict[str, Any]) -> None:
    print("Engel De Bruijn Quantum Structure Status")
    print(f"backend_only: {str(status.get('backend_only')).lower()}")
    print(f"ui_enabled: {str(status.get('ui_enabled')).lower()}")
    print(f"companion_card_enabled: {str(status.get('companion_card_enabled')).lower()}")
    print(f"viewer_enabled: {str(status.get('viewer_enabled')).lower()}")
    print(f"manual_scan_button_enabled: {str(status.get('manual_scan_button_enabled')).lower()}")
    print(f"available: {str(status.get('available')).lower()}")
    print(f"status_source: {status.get('status_source')}")
    print(f"message: {status.get('message')}")
    print(f"contract_status: {status.get('contract_status')}")
    print(f"automation_scope: {status.get('automation_scope')}")
    print(f"quantum_mode: {status.get('quantum_mode')}")
    print(f"file_count: {status.get('file_count')}")
    print(f"unknown_count: {status.get('unknown_count')}")
    print(f"candidate_count: {status.get('candidate_count')}")
    print(f"proposal_count: {status.get('proposal_count')}")
    print(f"incomplete_entanglement_count: {status.get('incomplete_entanglement_count')}")
    print(f"latest_status_path: {status.get('latest_status_path')}")
    print(f"latest_receipt_path: {status.get('latest_receipt_path')}")
    print(f"latest_proposal_path: {status.get('latest_proposal_path')}")
    print("safety_flags:")
    for key, value in sorted((status.get("safety_flags") or {}).items()):
        print(f"  {key}: {str(value).lower()}")
    if status.get("warnings"):
        print("warnings:")
        for warning in status["warnings"]:
            print(f"  - {warning}")
    if status.get("missing_outputs"):
        print("missing_outputs:")
        for item in status["missing_outputs"]:
            print(f"  - {item}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read existing De Bruijn Quantum File Structure status outputs without scanning or writing files."
    )
    parser.add_argument("command", choices=["status", "json"], help="Print text status or JSON status.")
    parser.add_argument("--root", default=None, help="Optional explicit local Engel workspace root.")
    args = parser.parse_args(argv)

    status = build_debruijn_quantum_structure_status(args.root)
    if args.command == "json":
        print(json.dumps(status, indent=2, sort_keys=True))
    elif args.command == "status":
        _print_text_status(status)
    else:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
