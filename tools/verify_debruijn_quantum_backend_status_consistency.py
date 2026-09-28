#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import py_compile
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports" / "debruijn_quantum_file_structure"
HELPER = ROOT / "engel_debruijn_quantum_structure_status.py"
CORE_SOURCE = ROOT / "engel_debruijn_quantum_automation_file_structure.py"
CONTRACT_JSON = ROOT / "memory" / "ENGEL_DEBRUIJN_QUANTUM_AUTOMATION_FILE_STRUCTURE_CONTRACT_V1.json"
LATEST_STATUS = REPORT_DIR / "latest_status.json"
LATEST_STATUS_MD = REPORT_DIR / "latest_status.md"
PASS_MARKER = "DEBRUIJN_QUANTUM_BACKEND_STATUS_CONSISTENCY_VERIFICATION_PASS"


RELEVANT_SOURCE_FILES = [
    ROOT / "engel_debruijn_quantum_structure_status.py",
    ROOT / "engel_debruijn_quantum_automation_file_structure.py",
    ROOT / "tools" / "verify_debruijn_quantum_structure_status_helper.py",
    ROOT / "tools" / "verify_debruijn_quantum_backend_status_command.py",
    ROOT / "tools" / "verify_debruijn_quantum_candidate_proposals.py",
    ROOT / "tools" / "verify_debruijn_quantum_entanglement_groups.py",
]

FALSE_FIELDS = [
    "ui_enabled",
    "companion_card_enabled",
    "viewer_enabled",
    "manual_scan_button_enabled",
    "real_quantum_enabled",
    "provider_api_enabled",
    "network_enabled",
    "model_inference_enabled",
    "background_worker_enabled",
    "startup_autorun_enabled",
    "apply_enabled",
    "file_mutation_enabled",
    "trusted_memory_write_enabled",
    "route_mutation_enabled",
    "queue_mutation_enabled",
]

TRUE_FIELDS = [
    "backend_only",
    "human_review_required",
]

TRUE_SAFETY_FLAGS = [
    "quantum_inspired_only",
    "real_quantum_off",
    "provider_api_off",
    "network_off",
    "model_inference_off",
    "background_worker_off",
    "startup_autorun_off",
    "apply_off",
    "file_move_delete_rewrite_off",
    "trusted_memory_write_off",
    "route_queue_mutation_off",
    "candidate_execution_off",
]

FALSE_PROPOSAL_FIELDS = [
    "runtime_enabled",
    "autorun_enabled",
    "source_mutation_allowed",
    "file_mutation_allowed",
    "route_mutation_allowed",
    "queue_mutation_allowed",
    "trusted_memory_write_allowed",
    "memory_promotion_allowed",
    "candidate_execution_allowed",
    "provider_api_allowed",
    "network_allowed",
    "model_inference_allowed",
    "real_quantum_allowed",
    "background_worker_allowed",
    "startup_autorun_allowed",
    "package_install_allowed",
    "mobile_runtime_allowed",
    "remote_queen_runtime_allowed",
]

ACTIVE_RISK_PATTERNS = [
    "apply_proposal",
    "apply_candidate_proposal",
    "trust_proposal",
    "promote_proposal",
    "execute_proposal",
    "run_proposal",
    "write_trusted_memory_from_proposal",
    "mutate_routes_from_proposal",
    "mutate_queues_from_proposal",
    "move_files_from_proposal",
    "delete_files_from_proposal",
    "rewrite_source_from_proposal",
    "run_scan_report_from_status_helper",
    "run_propose_fixes_from_status_helper",
]


class CheckFailure(Exception):
    pass


def print_result(status: str, label: str, detail: str = "") -> None:
    suffix = f" {detail}" if detail else ""
    print(f"{status} {label}{suffix}")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def rel(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve(strict=False).relative_to(ROOT.resolve(strict=False))).replace("/", "\\")
    except ValueError:
        return str(path)


def normalize_path(value: Any) -> str | None:
    if value is None:
        return None
    return str(value).replace("/", "\\")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_helper_module() -> Any:
    spec = importlib.util.spec_from_file_location("engel_debruijn_quantum_structure_status", HELPER)
    require(spec is not None and spec.loader is not None, "could not load backend status helper module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def snapshot_report_dir() -> dict[str, tuple[int, int]]:
    snapshot: dict[str, tuple[int, int]] = {}
    if not REPORT_DIR.exists():
        return snapshot
    for path in sorted(REPORT_DIR.iterdir(), key=lambda item: item.name):
        if path.is_file():
            stat = path.stat()
            snapshot[path.name] = (stat.st_size, stat.st_mtime_ns)
    return snapshot


def latest_file(pattern: str) -> Path | None:
    if not REPORT_DIR.exists():
        return None
    files = [path for path in REPORT_DIR.glob(pattern) if path.is_file()]
    if not files:
        return None
    return sorted(files, key=lambda path: (path.stat().st_mtime_ns, path.name))[-1]


def proposal_items(data: Any) -> list[Any] | None:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("proposals", "candidate_proposals", "fixes"):
            value = data.get(key)
            if isinstance(value, list):
                return value
    return None


def count_transition_codes(records: list[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        for code in record.get("transition_codes") or []:
            key = str(code)
            counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def count_candidates(records: list[Any]) -> int:
    return sum(
        1
        for record in records
        if isinstance(record, dict) and isinstance(record.get("candidate_nodes"), list) and record.get("candidate_nodes")
    )


def count_reports(records: list[Any]) -> int:
    count = 0
    for record in records:
        if not isinstance(record, dict):
            continue
        path = str(record.get("path", "")).replace("/", "\\").lower()
        if record.get("debruijn_node") == "110" or path.startswith("reports\\"):
            count += 1
    return count


def count_incomplete_groups(groups: list[Any]) -> int:
    count = 0
    for group in groups:
        if not isinstance(group, dict):
            continue
        missing = group.get("missing_files")
        status = str(group.get("status", "")).lower()
        if (isinstance(missing, list) and missing) or (status and status not in {"complete", "ok", "passed"}):
            count += 1
    return count


def compare_field(label: str, expected: Any, actual: Any, failures: list[str], infos: list[str]) -> None:
    if expected is None:
        infos.append(f"{label}: skipped; source value absent")
        return
    if expected != actual:
        failures.append(f"{label}: expected {expected!r}, helper returned {actual!r}")
    else:
        print_result("PASS", f"{label} consistency", repr(actual))


def check_latest_status(status: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    if not LATEST_STATUS.exists():
        require(status.get("available") is False, "latest_status.json absent but helper did not return unavailable state")
        missing = status.get("missing_outputs") or []
        require(any("latest_status.json" in str(item) for item in missing), "helper missing_outputs did not mention latest_status.json")
        require(status.get("status_source") == "existing_reports_only", "helper status_source is not existing_reports_only")
        print_result("PASS", "empty state consistency", "latest_status.json absent and helper returned honest empty state")
        return "empty", {"latest_status_present": False}

    latest = load_json(LATEST_STATUS)
    require(isinstance(latest, dict), "latest_status.json top-level value is not an object")
    require(status.get("available") is True, "latest_status.json present but helper did not return available true")
    require(normalize_path(status.get("latest_status_path")) == rel(LATEST_STATUS), "helper latest_status_path mismatch")
    if LATEST_STATUS_MD.exists():
        require(normalize_path(status.get("latest_status_md_path")) == rel(LATEST_STATUS_MD), "helper latest_status_md_path mismatch")

    records = latest.get("records")
    if not isinstance(records, list):
        records = []
    node_counts = latest.get("node_counts")
    if not isinstance(node_counts, dict):
        node_counts = {}
    groups = latest.get("entanglement_groups")
    if not isinstance(groups, list):
        groups = []

    failures: list[str] = []
    infos: list[str] = []
    compare_field("file_count", int(latest.get("files_reported_count") or len(records)), status.get("file_count"), failures, infos)
    compare_field("unknown_count", int(node_counts.get("unknown", 0)), status.get("unknown_count"), failures, infos)
    compare_field("candidate_count", count_candidates(records), status.get("candidate_count"), failures, infos)
    compare_field("report_count", count_reports(records), status.get("report_count"), failures, infos)
    compare_field("scan_truncated", bool(latest.get("scan_truncated", False)), status.get("scan_truncated"), failures, infos)
    compare_field("node_counts", node_counts, status.get("node_counts"), failures, infos)
    compare_field("transition_counts", count_transition_codes(records), status.get("transition_counts"), failures, infos)
    compare_field("incomplete_entanglement_count", count_incomplete_groups(groups), status.get("incomplete_entanglement_count"), failures, infos)

    if "proposal_count" in latest:
        compare_field("latest_status.proposal_count", latest.get("proposal_count"), status.get("proposal_count"), failures, infos)
    else:
        infos.append("latest_status.proposal_count: skipped; latest_status.json does not carry proposal_count")

    for info in infos:
        print_result("INFO", info)
    require(not failures, "; ".join(failures))
    print_result("PASS", "latest_status consistency result", "existing latest_status.json matches helper output")
    return "present", {
        "latest_status_present": True,
        "file_count": status.get("file_count"),
        "unknown_count": status.get("unknown_count"),
        "candidate_count": status.get("candidate_count"),
        "report_count": status.get("report_count"),
    }


def check_proposals(status: dict[str, Any]) -> dict[str, Any]:
    latest = latest_file("candidate_fix_proposals_*.json")
    if latest is None:
        require(status.get("proposal_count") in (0, None), "no proposal file exists but helper proposal_count is nonzero")
        require(status.get("latest_proposal_path") in (None, ""), "no proposal file exists but helper latest_proposal_path is set")
        print_result("PASS", "proposal consistency result", "no proposal files; helper returned honest empty proposal state")
        return {"proposal_files_present": False, "proposal_count": 0}

    data = load_json(latest)
    items = proposal_items(data)
    require(items is not None, f"latest proposal file has unsupported shape: {rel(latest)}")
    require(normalize_path(status.get("latest_proposal_path")) == rel(latest), "helper latest_proposal_path does not match independently selected latest proposal")
    require(status.get("proposal_count") == len(items), "helper proposal_count does not match latest proposal file")

    safety_ok = True
    failures: list[str] = []
    if isinstance(data, dict):
        if data.get("status") not in (None, "untrusted_candidate"):
            failures.append("top-level status is not untrusted_candidate")
            safety_ok = False
        if data.get("apply_allowed") is not False:
            failures.append("top-level apply_allowed is not false")
            safety_ok = False
        if data.get("human_review_required") is not True:
            failures.append("top-level human_review_required is not true")
            safety_ok = False
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            failures.append(f"proposal {index} is not an object")
            safety_ok = False
            continue
        if item.get("trust_status") != "untrusted_candidate":
            failures.append(f"proposal {index} trust_status is not untrusted_candidate")
            safety_ok = False
        if item.get("apply_allowed") is not False:
            failures.append(f"proposal {index} apply_allowed is not false")
            safety_ok = False
        if item.get("human_review_required") is not True:
            failures.append(f"proposal {index} human_review_required is not true")
            safety_ok = False
        for field in FALSE_PROPOSAL_FIELDS:
            if item.get(field) is True:
                failures.append(f"proposal {index} has {field}=true")
                safety_ok = False

    if status.get("proposal_safety_ok") is not None:
        require(status.get("proposal_safety_ok") is safety_ok, "helper proposal_safety_ok disagrees with verifier safety result")
    require(not failures, "; ".join(failures))
    print_result("PASS", "proposal consistency result", f"{rel(latest)} proposals={len(items)} safety_ok={safety_ok}")
    return {"proposal_files_present": True, "latest_proposal_path": rel(latest), "proposal_count": len(items)}


def check_receipt(status: dict[str, Any]) -> dict[str, Any]:
    latest = latest_file("automation_receipt_*.md")
    if latest is None:
        require(status.get("latest_receipt_path") in (None, ""), "no receipt exists but helper latest_receipt_path is set")
        print_result("PASS", "receipt consistency result", "no receipt files; helper returned null/empty receipt state")
        return {"receipt_files_present": False}
    require(normalize_path(status.get("latest_receipt_path")) == rel(latest), "helper latest_receipt_path does not match independently selected latest receipt")
    print_result("PASS", "receipt consistency result", rel(latest) or "")
    return {"receipt_files_present": True, "latest_receipt_path": rel(latest)}


def check_safety_flags(status: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    for field in TRUE_FIELDS:
        if status.get(field) is not True:
            failures.append(f"{field} is not true")
    for field in FALSE_FIELDS:
        if status.get(field) is not False:
            failures.append(f"{field} is not false")
    flags = status.get("safety_flags")
    if not isinstance(flags, dict):
        failures.append("safety_flags is not an object")
        flags = {}
    for field in TRUE_SAFETY_FLAGS:
        if flags.get(field) is not True:
            failures.append(f"safety_flags.{field} is not true")
    require(not failures, "; ".join(failures))
    print_result("PASS", "safety flag consistency result", "backend-only and unsafe capabilities remain disabled")
    return {"unsafe_capabilities_disabled": True, "safety_flags_ok": True}


def check_active_source_scan() -> dict[str, Any]:
    failures: list[str] = []
    scanned = 0
    for path in RELEVANT_SOURCE_FILES:
        if not path.exists():
            print_result("INFO", "optional active source missing", rel(path) or str(path))
            continue
        scanned += 1
        text = path.read_text(encoding="utf-8", errors="replace")
        lowered = text.lower()
        if path == HELPER:
            helper_forbidden = [
                "subprocess",
                "os.system",
                "write_text",
                "write_bytes",
                "scan-report",
                "propose-fixes",
                "apply_proposal",
            ]
            for token in helper_forbidden:
                if token in lowered:
                    failures.append(f"{rel(path)} contains helper-forbidden token {token}")
        if path.name.startswith("verify_"):
            print_result("INFO", "verifier-only active source reference", rel(path) or str(path))
            continue
        for token in ACTIVE_RISK_PATTERNS:
            if token in lowered:
                failures.append(f"{rel(path)} contains active risk token {token}")
    require(not failures, "; ".join(failures))
    print_result("PASS", "active source scan result", f"scanned={scanned}")
    return {"active_source_files_scanned": scanned}


def main() -> int:
    print("ENGEL_DEBRUIJN_QUANTUM_BACKEND_STATUS_CONSISTENCY_VERIFIER")
    print(f"ROOT {ROOT}")
    print("Mode: local consistency verification only; no scans, reports, proposals, apply, provider, model, UI, or mutation")
    results: dict[str, Any] = {}
    try:
        require(HELPER.exists(), f"missing helper: {rel(HELPER)}")
        require(CORE_SOURCE.exists(), f"missing core source: {rel(CORE_SOURCE)}")
        require(CONTRACT_JSON.exists(), f"missing contract JSON: {rel(CONTRACT_JSON)}")
        py_compile.compile(str(HELPER), doraise=True)
        py_compile.compile(str(Path(__file__)), doraise=True)
        print_result("PASS", "py_compile helper and consistency verifier")

        before = snapshot_report_dir()
        helper = load_helper_module()
        status = helper.build_debruijn_quantum_structure_status(ROOT)
        require(isinstance(status, dict), "helper did not return a dict")
        after = snapshot_report_dir()
        require(before == after, "helper invocation created, modified, or deleted report output files")
        print_result("PASS", "helper invocation/no-write result", "report folder snapshot unchanged")
        results["helper_invocation"] = {"report_folder_unchanged": True}

        latest_status_mode, latest_result = check_latest_status(status)
        results["latest_status"] = {"mode": latest_status_mode, **latest_result}
        results["proposal"] = check_proposals(status)
        results["receipt"] = check_receipt(status)
        results["safety_flags"] = check_safety_flags(status)
        results["active_source_scan"] = check_active_source_scan()

        print_result("PASS", "latest file selection result")
        print_result("PASS", "no-write/no-mutation result")
        print_result("PASS", "safety preserved")
        print(PASS_MARKER)
        return 0
    except Exception as exc:
        print_result("FAIL", "backend status consistency verifier", str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
