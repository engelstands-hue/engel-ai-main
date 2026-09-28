from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
TOPOLOGY_PATH = ROOT / "memory" / "ENGEL_SYSTEM_TOPOLOGY_REGISTRY_V1.json"
MATRIX_PATH = ROOT / "memory" / "ENGEL_SELF_UPGRADE_VERIFIER_MATRIX_V1.json"
STORAGE_REGISTRY_PATH = ROOT / "memory" / "ENGEL_STORAGE_LOCATION_REGISTRY_V1.json"
REPORT_ROOT = ROOT / "reports" / "self_upgrade"
ISSUE_DIR = REPORT_ROOT / "issues"
ROUTE_DIR = REPORT_ROOT / "routes"
PATCH_CANDIDATE_DIR = REPORT_ROOT / "patch_candidates"
GATE_RECEIPT_DIR = REPORT_ROOT / "gate_receipts"
APPLY_RECEIPT_DIR = REPORT_ROOT / "apply_receipts"
MEMORY_CANDIDATE_DIR = REPORT_ROOT / "memory_candidates"
ROLLBACK_DIR = REPORT_ROOT / "rollback"
MEETING_ROOM_WORK_ORDER_DIR = ROOT / "memory" / "meeting_room" / "work_orders"
MEETING_ROOM_RUNTIME_WORK_ORDER_DIR = ROOT / "runtime" / "meeting_room" / "self_upgrade_work_orders"
ACTIVE_RUNTIME_ROOT = "/opt/engel"
HDD_ARCHIVE_ROOT = "/mnt/engel-hdd-vault"
ALLOWED_STORAGE_ROOTS = [ACTIVE_RUNTIME_ROOT, HDD_ARCHIVE_ROOT]
RETIRED_DESKTOP_NODE_ID = "DESKTOP-" + "FIB17O7"

STATUS_LABELS = [
    "SELF_UPGRADE_SYSTEM",
    "SUPERVISED_REPAIR_LOOP",
    "ISSUE_LEDGER",
    "ROUTE_PACKET",
    "PATCH_CANDIDATE_BUNDLE",
    "VERIFIER_MATRIX",
    "APPROVAL_GATE",
    "CANDIDATE_MEMORY_ONLY",
    "CT246_AUTHORITY",
    "SUB_DESKTOP_WORKER_LANE",
    "ANDROID_WORKERS_BOUNDED",
    "ENGEL_HDD_VAULT_ARCHIVE_AWARE",
    "EXTERNAL_STORAGE_PERMANENTLY_EXCLUDED",
    "NO_SILENT_SOURCE_MUTATION",
    "NO_TRUSTED_MEMORY_WRITE_WITHOUT_APPROVAL",
]

SEVERITIES = {"low", "medium", "high", "critical"}
ISSUE_SOURCES = {"chat_ui", "discord", "ct_log", "sub_desktop", "android_worker", "verifier", "meeting_room", "chat_self_heal_probe", "manual"}
SURFACES = {"chat", "meeting_room", "discord", "models", "workers", "storage", "sub_desktop", "android_worker", "provider_bridge", "source_patch", "memory_promotion", "local_llm"}
ISSUE_STATUSES = {"open", "routed", "diagnosing", "candidate_ready", "verifying", "needs_approval", "approved", "applied", "rejected", "blocked"}
HIGH_RISK_SURFACES = {"storage", "provider_bridge", "source_patch", "memory_promotion", "sub_desktop"}
HIGH_RISK_KEYWORDS = {
    "trusted memory",
    "route authority",
    "provider key",
    "api key",
    "model control",
    "startup",
    "autorun",
    "service",
    "main.shell",
    "disk.control",
    "delete",
    "move",
    "sync",
    "mount",
    "format",
    "partition",
}
LOW_RISK_GATE_TOKEN = "APPROVE_ENGEL_SELF_UPGRADE_LOW_RISK_V1"
LOW_RISK_APPLY_TOKEN = "APPLY_ENGEL_SELF_UPGRADE_LOW_RISK_V1"
ELEVATED_RISK_GATE_TOKEN = "APPROVE_ENGEL_SELF_UPGRADE_ELEVATED_RISK_V1"
ELEVATED_RISK_APPLY_TOKEN = "APPLY_ENGEL_SELF_UPGRADE_ELEVATED_RISK_V1"
PATCHABLE_EXTENSIONS = {
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
PROTECTED_TARGET_PARTS = {
    ".git",
    ".venv",
    "cache",
    "logs",
    "models",
    "models-active",
    "node_modules",
    "runtime\\python310",
    "secrets",
}
PROTECTED_TARGET_MARKERS = {
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
MAX_PATCHABLE_FILE_BYTES = 2 * 1024 * 1024


class SelfUpgradeError(ValueError):
    pass


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SelfUpgradeError(f"could not read JSON: {path}") from exc
    if not isinstance(data, dict):
        raise SelfUpgradeError(f"JSON must be an object: {path}")
    return data


def write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def safe_slug(value: str, limit: int = 90) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(value or "")).strip("_").lower()
    return (cleaned or "engel")[:limit]


def short_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()[:16]


def is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except ValueError:
        return False


def project_relative(path: Path) -> str:
    rel = str(path.resolve(strict=False).relative_to(ROOT.resolve(strict=False)))
    if os.name == "nt":
        return rel.replace("/", "\\")
    return rel.replace("\\", "/")


def project_path_from_relative(raw_path: str) -> Path:
    if not raw_path:
        raise SelfUpgradeError("project-relative path required")
    if Path(raw_path).is_absolute():
        candidate = Path(raw_path)
    else:
        candidate = ROOT / raw_path.replace("\\", "/")
    resolved = candidate.resolve(strict=False)
    if not is_relative_to(resolved, ROOT):
        raise SelfUpgradeError("path escaped Engel App")
    return resolved


def canonical_project_path(raw_path: str) -> str:
    return project_relative(project_path_from_relative(raw_path))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_backup_name(project_path: str) -> str:
    return safe_slug(project_path.replace("\\", "__").replace("/", "__"), limit=180)


def validate_patch_target(raw_path: str, allowed_targets: set[str]) -> Path:
    target = project_path_from_relative(raw_path)
    canonical = canonical_project_path(raw_path)
    canonical_key = canonical.lower().replace("/", "\\")
    if canonical_key not in allowed_targets:
        raise SelfUpgradeError(f"patch target is not listed in candidate files_to_change: {canonical}")
    lowered = canonical_key
    if any(part in lowered for part in PROTECTED_TARGET_PARTS):
        raise SelfUpgradeError(f"protected target path refused: {canonical}")
    if any(marker in lowered for marker in PROTECTED_TARGET_MARKERS):
        raise SelfUpgradeError(f"protected target marker refused: {canonical}")
    if target.suffix.lower() not in PATCHABLE_EXTENSIONS:
        raise SelfUpgradeError(f"unsupported patch target extension: {canonical}")
    if not target.exists() or not target.is_file():
        raise SelfUpgradeError(f"patch target must be an existing file: {canonical}")
    if target.stat().st_size > MAX_PATCHABLE_FILE_BYTES:
        raise SelfUpgradeError(f"patch target too large for self-upgrade apply lane: {canonical}")
    return target


def load_topology() -> dict[str, Any]:
    data = read_json(TOPOLOGY_PATH)
    if data.get("schema") != "ENGEL_SYSTEM_TOPOLOGY_REGISTRY_V1":
        raise SelfUpgradeError("topology registry schema mismatch")
    return data


def load_matrix() -> dict[str, Any]:
    data = read_json(MATRIX_PATH)
    if data.get("schema") != "ENGEL_SELF_UPGRADE_VERIFIER_MATRIX_V1":
        raise SelfUpgradeError("verifier matrix schema mismatch")
    return data


def load_storage_registry() -> dict[str, Any]:
    data = read_json(STORAGE_REGISTRY_PATH)
    if data.get("schema") != "ENGEL_STORAGE_LOCATION_REGISTRY_V1":
        raise SelfUpgradeError("storage registry schema mismatch")
    return data


def assert_hdd_vault_registered() -> None:
    topology = load_topology()
    storage = load_storage_registry()
    archive = topology.get("storage", {}).get("archive", {})
    if archive.get("name") != "engel-hdd-vault":
        raise SelfUpgradeError("topology archive storage must be engel-hdd-vault")
    if archive.get("node") != "engel-spine-01":
        raise SelfUpgradeError("engel-hdd-vault must be on engel-spine-01")
    if archive.get("ct_mount") != HDD_ARCHIVE_ROOT:
        raise SelfUpgradeError("engel-hdd-vault CT mount mismatch")
    hdd = storage.get("dell_poweredge_hdd_vault", {})
    if hdd.get("name") != "engel-hdd-vault" or hdd.get("proxmox_host") != "engel-spine-01":
        raise SelfUpgradeError("storage registry does not confirm engel-hdd-vault on engel-spine-01")
    if hdd.get("container_mount") != HDD_ARCHIVE_ROOT:
        raise SelfUpgradeError("storage registry hdd vault mount mismatch")
    if storage.get("allowed_storage_roots") != ALLOWED_STORAGE_ROOTS:
        raise SelfUpgradeError("storage registry CT246 allowlist mismatch")


def resolve_report_path(raw_path: str) -> Path:
    if not raw_path:
        raise SelfUpgradeError("path required")
    if os.name != "nt":
        raw_path = raw_path.replace("\\", "/")
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    resolved = candidate.resolve(strict=False)
    if not is_relative_to(resolved, ROOT):
        raise SelfUpgradeError("path must stay inside Engel App")
    if not resolved.exists() or not resolved.is_file():
        raise SelfUpgradeError("path must be an existing file")
    rel = project_relative(resolved).lower()
    allowed_roots = ("reports\\", "memory\\", "reports/", "memory/")
    if not rel.startswith(allowed_roots):
        raise SelfUpgradeError("evidence/candidate path must be under reports or memory")
    return resolved


def normalize_paths(raw_paths: list[str] | None) -> list[str]:
    normalized: list[str] = []
    for raw in raw_paths or []:
        path = resolve_report_path(raw)
        normalized.append(project_relative(path))
    return normalized


def issue_id_for(source: str, symptom: str, created_at: str) -> str:
    return "engel_issue_" + short_hash(f"{source}|{symptom}|{created_at}")


def build_issue(
    *,
    source: str,
    symptom: str,
    severity: str,
    affected_surface: str,
    evidence_paths: list[str] | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    if source not in ISSUE_SOURCES:
        raise SelfUpgradeError(f"unknown issue source: {source}")
    if severity not in SEVERITIES:
        raise SelfUpgradeError(f"unknown severity: {severity}")
    if affected_surface not in SURFACES:
        raise SelfUpgradeError(f"unknown affected surface: {affected_surface}")
    if not symptom.strip():
        raise SelfUpgradeError("symptom is required")
    created = created_at or now_utc()
    requires_approval = severity in {"high", "critical"} or affected_surface in HIGH_RISK_SURFACES
    return {
        "schema": "ENGEL_SELF_UPGRADE_ISSUE_V1",
        "issue_id": issue_id_for(source, symptom, created),
        "source": source,
        "symptom": symptom.strip(),
        "first_seen_utc": created,
        "severity": severity,
        "affected_surface": affected_surface,
        "evidence_paths": normalize_paths(evidence_paths),
        "owner": owner_for_surface(affected_surface),
        "status": "open",
        "approval_required": requires_approval,
        "candidate_only": True,
        "trusted_memory_write": False,
        "source_mutation": False,
    }


def owner_for_surface(surface: str) -> str:
    if surface == "sub_desktop":
        return "sub_desktop"
    if surface in {"discord", "provider_bridge"}:
        return "rog_controller"
    if surface == "android_worker":
        return "ct246_engel_ai_main"
    return "ct246_engel_ai_main"


def surface_matrix(surface: str) -> dict[str, Any]:
    matrix = load_matrix()
    surfaces = matrix.get("surfaces", {})
    if surface in surfaces and isinstance(surfaces[surface], dict):
        return surfaces[surface]
    if surface == "workers":
        return surfaces.get("android_worker", {})
    if surface == "discord":
        return surfaces.get("provider_bridge", {})
    if surface == "models" or surface == "local_llm":
        return surfaces.get("chat", {})
    return {}


def write_issue(issue: dict[str, Any], report_root: Path = REPORT_ROOT) -> Path:
    validate_issue(issue)
    return write_json(report_root / "issues" / f"{safe_slug(issue['issue_id'])}.json", issue)


def validate_issue(issue: dict[str, Any]) -> None:
    if issue.get("schema") != "ENGEL_SELF_UPGRADE_ISSUE_V1":
        raise SelfUpgradeError("issue schema mismatch")
    if issue.get("source") not in ISSUE_SOURCES:
        raise SelfUpgradeError("issue source invalid")
    if issue.get("severity") not in SEVERITIES:
        raise SelfUpgradeError("issue severity invalid")
    if issue.get("affected_surface") not in SURFACES:
        raise SelfUpgradeError("issue surface invalid")
    if issue.get("status") not in ISSUE_STATUSES:
        raise SelfUpgradeError("issue status invalid")
    if issue.get("trusted_memory_write") is not False or issue.get("source_mutation") is not False:
        raise SelfUpgradeError("issue record cannot mutate source or trusted memory")


def load_issue(path: str) -> dict[str, Any]:
    issue = read_json(resolve_report_path(path))
    validate_issue(issue)
    return issue


def route_id_for(issue_id: str, created_at: str) -> str:
    return "engel_route_" + short_hash(f"{issue_id}|{created_at}")


def route_issue(issue: dict[str, Any], *, created_at: str | None = None) -> dict[str, Any]:
    validate_issue(issue)
    created = created_at or now_utc()
    surface = str(issue["affected_surface"])
    matrix = surface_matrix(surface)
    supporting_workers = list(matrix.get("supporting_workers", [])) if isinstance(matrix, dict) else []
    topology = load_topology()
    disabled = {str(item.get("node_id")) for item in topology.get("disabled_nodes", []) if isinstance(item, dict)}
    supporting_workers = [worker for worker in supporting_workers if worker not in disabled and worker != RETIRED_DESKTOP_NODE_ID]
    risk = classify_risk(issue.get("symptom", ""), surface, issue.get("severity", "medium"))
    route = {
        "schema": "ENGEL_SELF_UPGRADE_ROUTE_V1",
        "route_id": route_id_for(str(issue["issue_id"]), created),
        "issue_id": issue["issue_id"],
        "created_at_utc": created,
        "owner": matrix.get("owner") or issue.get("owner") or owner_for_surface(surface),
        "supporting_workers": supporting_workers,
        "preferred_model_route": matrix.get("preferred_model_route", "local_llm_first"),
        "equipment_target": choose_equipment_target(surface, supporting_workers),
        "required_verifiers": list(matrix.get("required_verifiers", ["tools\\verify_engel_self_upgrade_system.py"])),
        "runtime_checks": list(matrix.get("runtime_checks", [])),
        "approval_required": bool(issue.get("approval_required")) or risk != "low",
        "risk_level": risk,
        "meeting_room_card": build_meeting_room_card(issue, supporting_workers, risk),
        "candidate_only": True,
        "safe_to_auto_apply": False,
        "trusted_memory_write": False,
        "source_mutation": False,
        "storage_context": {
            "active_runtime": ACTIVE_RUNTIME_ROOT,
            "archive": HDD_ARCHIVE_ROOT,
            "archive_node": "engel-spine-01",
            "allowed_roots": list(ALLOWED_STORAGE_ROOTS),
            "external_storage_permanently_excluded": True,
        },
    }
    return route


def classify_risk(text: str, surface: str, severity: str) -> str:
    lowered = text.lower()
    if severity == "critical" or surface in HIGH_RISK_SURFACES:
        return "high"
    if severity == "high" or any(keyword in lowered for keyword in HIGH_RISK_KEYWORDS):
        return "high"
    if severity == "medium":
        return "medium"
    return "low"


def choose_equipment_target(surface: str, supporting_workers: list[str]) -> str:
    if surface == "sub_desktop":
        return "sub_desktop"
    if surface == "android_worker":
        return "android_worker_fleet"
    if "sub_desktop" in supporting_workers:
        return "ct246_plus_sub_desktop"
    return "ct246_engel_ai_main"


def build_meeting_room_card(issue: dict[str, Any], supporting_workers: list[str], risk: str) -> dict[str, Any]:
    return {
        "card_type": "self_upgrade_issue",
        "title": f"Self-upgrade: {issue['affected_surface']}",
        "summary": issue["symptom"],
        "state": "assigned",
        "states": [
            "idle",
            "assigned",
            "claimed",
            "working",
            "returned",
            "verifying",
            "blocked",
            "needs approval",
            "approved",
            "applied",
            "failed",
        ],
        "primary_owner": issue.get("owner") or owner_for_surface(str(issue["affected_surface"])),
        "supporting_workers": supporting_workers,
        "risk_level": risk,
        "approval_required": bool(issue.get("approval_required")) or risk != "low",
    }


def write_route(route: dict[str, Any], report_root: Path = REPORT_ROOT) -> Path:
    validate_route(route)
    return write_json(report_root / "routes" / f"{safe_slug(route['route_id'])}.json", route)


def meeting_room_work_order_id(route: dict[str, Any]) -> str:
    return "engel_work_order_" + short_hash(str(route.get("route_id", "")))


def build_meeting_room_work_order(issue: dict[str, Any], route: dict[str, Any]) -> dict[str, Any]:
    validate_issue(issue)
    validate_route(route)
    if route.get("issue_id") != issue.get("issue_id"):
        raise SelfUpgradeError("work order issue_id mismatch")
    card = route.get("meeting_room_card", {})
    workers = list(route.get("supporting_workers", []) or [])
    return {
        "schema": "ENGEL_MEETING_ROOM_SELF_UPGRADE_WORK_ORDER_V1",
        "work_order_id": meeting_room_work_order_id(route),
        "issue_id": issue["issue_id"],
        "route_id": route["route_id"],
        "created_at_utc": route.get("created_at_utc") or now_utc(),
        "title": card.get("title") or f"Self-upgrade: {issue['affected_surface']}",
        "summary": issue["symptom"],
        "state": card.get("state") or "assigned",
        "allowed_states": card.get("states", []),
        "owner_lane": route.get("owner"),
        "worker_lanes": workers,
        "equipment_target": route.get("equipment_target"),
        "preferred_model_route": route.get("preferred_model_route"),
        "risk_level": route.get("risk_level"),
        "approval_required": route.get("approval_required"),
        "required_verifiers": route.get("required_verifiers", []),
        "runtime_checks": route.get("runtime_checks", []),
        "expected_receipts": [
            "route_receipt",
            "candidate_patch_receipt",
            "verifier_receipt",
            "approval_gate_receipt",
            "memory_candidate_receipt",
        ],
        "storage_context": route.get("storage_context", {}),
        "visible_in_meeting_room": True,
        "candidate_only": True,
        "safe_to_auto_apply": False,
        "trusted_memory_write": False,
        "source_mutation": False,
        "forbidden_actions": [
            "auto_apply",
            "write_trusted_memory",
            "mutate_routes",
            "provider_key_change",
            "storage_mutation",
            "sub_desktop_shell_or_disk_without_approval",
            "use_undeclared_storage_root",
        ],
    }


def validate_meeting_room_work_order(work_order: dict[str, Any]) -> None:
    if work_order.get("schema") != "ENGEL_MEETING_ROOM_SELF_UPGRADE_WORK_ORDER_V1":
        raise SelfUpgradeError("work order schema mismatch")
    if work_order.get("visible_in_meeting_room") is not True:
        raise SelfUpgradeError("work order must be visible in meeting room")
    if work_order.get("candidate_only") is not True:
        raise SelfUpgradeError("work order must be candidate_only")
    if work_order.get("safe_to_auto_apply") is not False:
        raise SelfUpgradeError("work order cannot auto-apply")
    if work_order.get("trusted_memory_write") is not False:
        raise SelfUpgradeError("work order cannot write trusted memory")
    if work_order.get("source_mutation") is not False:
        raise SelfUpgradeError("work order cannot mutate source")
    if RETIRED_DESKTOP_NODE_ID in list(work_order.get("worker_lanes", []) or []):
        raise SelfUpgradeError("work order must not route the retired desktop node")
    storage = work_order.get("storage_context", {})
    if storage.get("archive") != HDD_ARCHIVE_ROOT:
        raise SelfUpgradeError("work order must reference engel-hdd-vault")
    if storage.get("allowed_roots") != ALLOWED_STORAGE_ROOTS:
        raise SelfUpgradeError("work order storage allowlist mismatch")
    if storage.get("external_storage_permanently_excluded") is not True:
        raise SelfUpgradeError("work order must permanently exclude external storage")


def write_meeting_room_work_order(
    work_order: dict[str, Any],
    *,
    memory_dir: Path = MEETING_ROOM_WORK_ORDER_DIR,
    runtime_dir: Path = MEETING_ROOM_RUNTIME_WORK_ORDER_DIR,
) -> list[Path]:
    validate_meeting_room_work_order(work_order)
    filename = f"{safe_slug(work_order['work_order_id'])}.json"
    return [
        write_json(memory_dir / filename, work_order),
        write_json(runtime_dir / filename, work_order),
    ]


def validate_route(route: dict[str, Any]) -> None:
    if route.get("schema") != "ENGEL_SELF_UPGRADE_ROUTE_V1":
        raise SelfUpgradeError("route schema mismatch")
    if route.get("safe_to_auto_apply") is not False:
        raise SelfUpgradeError("route cannot be safe_to_auto_apply")
    if route.get("trusted_memory_write") is not False or route.get("source_mutation") is not False:
        raise SelfUpgradeError("route cannot mutate source or trusted memory")
    workers = route.get("supporting_workers", [])
    if RETIRED_DESKTOP_NODE_ID in workers:
        raise SelfUpgradeError("retired desktop node must not be routed")
    storage = route.get("storage_context", {})
    if storage.get("archive") != HDD_ARCHIVE_ROOT:
        raise SelfUpgradeError("route must use engel-hdd-vault archive context")
    if storage.get("allowed_roots") != ALLOWED_STORAGE_ROOTS:
        raise SelfUpgradeError("route storage allowlist mismatch")
    if storage.get("external_storage_permanently_excluded") is not True:
        raise SelfUpgradeError("route must permanently exclude external storage")


def load_route(path: str) -> dict[str, Any]:
    route = read_json(resolve_report_path(path))
    validate_route(route)
    return route


def normalize_target_files(raw_files: list[str]) -> list[str]:
    if not raw_files:
        raise SelfUpgradeError("at least one target file is required")
    out: list[str] = []
    for raw in raw_files:
        if not raw or any(marker in raw for marker in ["*", "?", "[", "]"]):
            raise SelfUpgradeError("target files must be explicit")
        path = Path(raw)
        if path.is_absolute():
            resolved = path.resolve(strict=False)
            if not is_relative_to(resolved, ROOT):
                raise SelfUpgradeError("target file escaped Engel App")
            out.append(project_relative(resolved))
        else:
            out.append(str(path).replace("/", "\\"))
    return out


def candidate_id_for(issue_id: str, created_at: str) -> str:
    return "engel_patch_candidate_" + short_hash(f"{issue_id}|{created_at}")


def build_patch_candidate(
    issue: dict[str, Any],
    route: dict[str, Any],
    *,
    diagnosis: str,
    files_to_change: list[str],
    patch_plan: str,
    patch_file: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    validate_issue(issue)
    validate_route(route)
    if route.get("issue_id") != issue.get("issue_id"):
        raise SelfUpgradeError("route issue_id mismatch")
    if not diagnosis.strip() or not patch_plan.strip():
        raise SelfUpgradeError("diagnosis and patch_plan are required")
    created = created_at or now_utc()
    risk = str(route.get("risk_level") or "high")
    if any(keyword in (" ".join(files_to_change) + " " + patch_plan + " " + diagnosis).lower() for keyword in HIGH_RISK_KEYWORDS):
        risk = "high"
    candidate = {
        "schema": "ENGEL_SELF_UPGRADE_PATCH_CANDIDATE_V1",
        "candidate_id": candidate_id_for(str(issue["issue_id"]), created),
        "issue_id": issue["issue_id"],
        "route_id": route["route_id"],
        "created_at_utc": created,
        "diagnosis": diagnosis.strip(),
        "files_to_change": normalize_target_files(files_to_change),
        "risk_level": risk,
        "patch_plan": patch_plan.strip(),
        "patch_file": project_relative(resolve_report_path(patch_file)) if patch_file else None,
        "rollback_plan": "Before apply: save hashes and backup copies for every touched file under reports\\self_upgrade\\rollback; after failure, restore those backups and write rollback receipt.",
        "required_verifiers": list(route.get("required_verifiers", [])),
        "sub_desktop_review_required": "sub_desktop" in route.get("supporting_workers", []) or risk != "low",
        "android_worker_review_required": any(str(worker).startswith("android_worker") for worker in route.get("supporting_workers", [])),
        "human_approval_required": bool(route.get("approval_required")) or risk != "low",
        "status": "draft",
        "candidate_only": True,
        "safe_to_auto_apply": False,
        "patch_applied": False,
        "trusted_memory_write": False,
        "source_mutation": False,
        "storage_context": route.get("storage_context"),
        "blocked_actions": [
            "auto_apply",
            "write_trusted_memory",
            "mutate_routes",
            "mutate_source_without_gate",
            "provider_key_change",
            "storage_mutation",
            "sub_desktop_shell_or_disk_without_approval",
            "startup_autorun",
        ],
    }
    return candidate


def validate_patch_candidate(candidate: dict[str, Any]) -> None:
    if candidate.get("schema") != "ENGEL_SELF_UPGRADE_PATCH_CANDIDATE_V1":
        raise SelfUpgradeError("patch candidate schema mismatch")
    if candidate.get("status") not in {"draft", "verified", "blocked", "approved", "applied", "rejected"}:
        raise SelfUpgradeError("patch candidate status invalid")
    if candidate.get("candidate_only") is not True:
        raise SelfUpgradeError("patch candidate must remain candidate_only")
    if candidate.get("safe_to_auto_apply") is not False:
        raise SelfUpgradeError("patch candidate must not be safe_to_auto_apply")
    if candidate.get("patch_applied") is not False and candidate.get("status") != "applied":
        raise SelfUpgradeError("patch_applied cannot be true before applied status")
    if candidate.get("trusted_memory_write") is not False:
        raise SelfUpgradeError("patch candidate cannot write trusted memory")
    if not candidate.get("required_verifiers"):
        raise SelfUpgradeError("patch candidate requires verifiers")
    patch_file = candidate.get("patch_file")
    if patch_file is not None:
        path = resolve_report_path(str(patch_file))
        if not is_relative_to(path, PATCH_CANDIDATE_DIR):
            raise SelfUpgradeError("patch_file must be under reports/self_upgrade/patch_candidates")
    storage = candidate.get("storage_context", {})
    if storage.get("archive") != HDD_ARCHIVE_ROOT:
        raise SelfUpgradeError("patch candidate must reference engel-hdd-vault archive context")
    if storage.get("allowed_roots") != ALLOWED_STORAGE_ROOTS:
        raise SelfUpgradeError("patch candidate storage allowlist mismatch")
    if storage.get("external_storage_permanently_excluded") is not True:
        raise SelfUpgradeError("patch candidate must permanently exclude external storage")


def write_patch_candidate(candidate: dict[str, Any], report_root: Path = REPORT_ROOT) -> Path:
    validate_patch_candidate(candidate)
    return write_json(report_root / "patch_candidates" / f"{safe_slug(candidate['candidate_id'])}.json", candidate)


def load_patch_candidate(path: str) -> dict[str, Any]:
    candidate = read_json(resolve_report_path(path))
    validate_patch_candidate(candidate)
    return candidate


def gate_receipt_id(candidate_id: str, created_at: str) -> str:
    return "engel_gate_receipt_" + short_hash(f"{candidate_id}|{created_at}")


def gate_candidate(candidate: dict[str, Any], *, verifier_results: list[str] | None = None, approval_token: str = "", created_at: str | None = None) -> dict[str, Any]:
    validate_patch_candidate(candidate)
    created = created_at or now_utc()
    verifier_results = normalize_paths(verifier_results)
    risk = str(candidate.get("risk_level", "high"))
    approval_required = True
    expected_token = (
        LOW_RISK_GATE_TOKEN
        if risk == "low"
        else ELEVATED_RISK_GATE_TOKEN
    )
    approval_ok = bool(approval_token and approval_token == expected_token)
    apply_allowed = bool(verifier_results) and approval_ok
    return {
        "schema": "ENGEL_SELF_UPGRADE_GATE_RECEIPT_V1",
        "receipt_id": gate_receipt_id(str(candidate["candidate_id"]), created),
        "candidate_id": candidate["candidate_id"],
        "issue_id": candidate["issue_id"],
        "created_at_utc": created,
        "risk_level": risk,
        "verifier_results": verifier_results,
        "required_verifiers": candidate.get("required_verifiers", []),
        "approval_required": approval_required,
        "approval_class": "low_risk" if risk == "low" else "elevated_risk",
        "approval_token_accepted": approval_ok,
        "apply_allowed": apply_allowed,
        "apply_performed": False,
        "reason": gate_reason(risk, verifier_results, approval_required, approval_ok, apply_allowed),
        "rollback_required_before_apply": True,
        "rollback_root": "reports\\self_upgrade\\rollback",
        "trusted_memory_write": False,
        "source_mutation": False,
        "candidate_memory_only": True,
    }


def gate_reason(risk: str, verifier_results: list[str], approval_required: bool, approval_ok: bool, apply_allowed: bool) -> str:
    if apply_allowed:
        return (
            f"{risk.title()}-risk candidate has verifier evidence and the "
            "risk-matched owner approval; the apply lane may proceed with backups."
        )
    if not verifier_results:
        return "Verifier evidence is missing; apply remains blocked."
    if approval_required and not approval_ok:
        return "Approval token missing or invalid; apply remains blocked."
    return "Apply remains blocked by default fail-closed policy."


def write_gate_receipt(receipt: dict[str, Any], report_root: Path = REPORT_ROOT) -> Path:
    if receipt.get("schema") != "ENGEL_SELF_UPGRADE_GATE_RECEIPT_V1":
        raise SelfUpgradeError("gate receipt schema mismatch")
    return write_json(report_root / "gate_receipts" / f"{safe_slug(receipt['receipt_id'])}.json", receipt)


def validate_gate_receipt(receipt: dict[str, Any]) -> None:
    if receipt.get("schema") != "ENGEL_SELF_UPGRADE_GATE_RECEIPT_V1":
        raise SelfUpgradeError("gate receipt schema mismatch")
    if receipt.get("trusted_memory_write") is not False:
        raise SelfUpgradeError("gate receipt cannot write trusted memory")
    if receipt.get("source_mutation") is not False:
        raise SelfUpgradeError("gate receipt cannot perform source mutation")
    if receipt.get("candidate_memory_only") is not True:
        raise SelfUpgradeError("gate receipt must remain candidate-memory-only")


def load_gate_receipt(path: str) -> dict[str, Any]:
    receipt = read_json(resolve_report_path(path))
    validate_gate_receipt(receipt)
    return receipt


def file_patch_id(candidate_id: str, created_at: str) -> str:
    return "engel_file_patch_" + short_hash(f"{candidate_id}|{created_at}")


def build_file_patch(
    candidate: dict[str, Any],
    *,
    operations: list[dict[str, Any]],
    created_at: str | None = None,
) -> dict[str, Any]:
    validate_patch_candidate(candidate)
    if not operations:
        raise SelfUpgradeError("at least one patch operation is required")
    created = created_at or now_utc()
    patch = {
        "schema": "ENGEL_SELF_UPGRADE_FILE_PATCH_V1",
        "patch_id": file_patch_id(str(candidate["candidate_id"]), created),
        "candidate_id": candidate["candidate_id"],
        "issue_id": candidate["issue_id"],
        "route_id": candidate["route_id"],
        "created_at_utc": created,
        "operations": operations,
        "requires_gate_receipt": True,
        "source_mutation_planned": True,
        "trusted_memory_write": False,
        "provider_generated_direct_apply": False,
    }
    validate_file_patch(patch, candidate)
    return patch


def validate_file_patch(patch: dict[str, Any], candidate: dict[str, Any]) -> None:
    validate_patch_candidate(candidate)
    if patch.get("schema") != "ENGEL_SELF_UPGRADE_FILE_PATCH_V1":
        raise SelfUpgradeError("file patch schema mismatch")
    if patch.get("candidate_id") != candidate.get("candidate_id"):
        raise SelfUpgradeError("file patch candidate_id mismatch")
    if patch.get("trusted_memory_write") is not False:
        raise SelfUpgradeError("file patch cannot write trusted memory")
    if patch.get("provider_generated_direct_apply") is not False:
        raise SelfUpgradeError("provider-generated direct apply is forbidden")
    operations = patch.get("operations")
    if not isinstance(operations, list) or not operations:
        raise SelfUpgradeError("file patch requires operations")
    if len(operations) > 20:
        raise SelfUpgradeError("file patch has too many operations")
    allowed_targets = {canonical_project_path(str(item)).lower().replace("/", "\\") for item in candidate.get("files_to_change", [])}
    for index, operation in enumerate(operations, start=1):
        if not isinstance(operation, dict):
            raise SelfUpgradeError(f"patch operation {index} must be an object")
        if operation.get("op") != "replace_text":
            raise SelfUpgradeError(f"patch operation {index} unsupported op")
        target = validate_patch_target(str(operation.get("file", "")), allowed_targets)
        old_text = operation.get("old_text")
        new_text = operation.get("new_text")
        if not isinstance(old_text, str) or not old_text:
            raise SelfUpgradeError(f"patch operation {index} old_text required")
        if not isinstance(new_text, str):
            raise SelfUpgradeError(f"patch operation {index} new_text required")
        # Byte-faithful read (no newline translation) so this check agrees with
        # the byte-exact apply lane.
        current = target.read_bytes().decode("utf-8")
        if current.count(old_text) != 1:
            raise SelfUpgradeError(f"patch operation {index} old_text must occur exactly once in {project_relative(target)}")


def write_file_patch(patch: dict[str, Any], candidate: dict[str, Any], report_root: Path = REPORT_ROOT) -> Path:
    validate_file_patch(patch, candidate)
    return write_json(report_root / "patch_candidates" / f"{safe_slug(patch['patch_id'])}.patch.json", patch)


def load_file_patch(path: str, candidate: dict[str, Any]) -> dict[str, Any]:
    patch_path = resolve_report_path(path)
    if not is_relative_to(patch_path, PATCH_CANDIDATE_DIR):
        raise SelfUpgradeError("file patch must be under reports/self_upgrade/patch_candidates")
    patch = read_json(patch_path)
    validate_file_patch(patch, candidate)
    return patch


def apply_receipt_id(candidate_id: str, created_at: str) -> str:
    return "engel_apply_receipt_" + short_hash(f"{candidate_id}|{created_at}")


def _rollback_payload(
    *,
    apply_id: str,
    candidate: dict[str, Any],
    gate_receipt: dict[str, Any],
    patch: dict[str, Any],
    files: list[dict[str, Any]],
    created_at: str,
    state: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "schema": "ENGEL_SELF_UPGRADE_ROLLBACK_SNAPSHOT_V1",
        "rollback_id": "engel_rollback_" + short_hash(f"{apply_id}|{created_at}"),
        "apply_receipt_id": apply_id,
        "candidate_id": candidate.get("candidate_id"),
        "gate_receipt_id": gate_receipt.get("receipt_id"),
        "patch_id": patch.get("patch_id"),
        "created_at_utc": created_at,
        "state": state,
        "reason": reason,
        "files": files,
        "restore_rule": "Copy each backup_path over its target_file, then rerun required verifiers.",
        "trusted_memory_write": False,
    }


def _apply_failure_receipt(
    *,
    apply_id: str,
    candidate: dict[str, Any],
    gate_receipt: dict[str, Any],
    patch: dict[str, Any],
    rollback_path: Path | None,
    created_at: str,
    reason: str,
    restored: bool,
) -> dict[str, Any]:
    return {
        "schema": "ENGEL_SELF_UPGRADE_APPLY_RECEIPT_V1",
        "receipt_id": apply_id,
        "candidate_id": candidate.get("candidate_id"),
        "gate_receipt_id": gate_receipt.get("receipt_id"),
        "patch_id": patch.get("patch_id"),
        "created_at_utc": created_at,
        "status": "rolled_back" if restored else "blocked",
        "apply_allowed_by_gate": bool(gate_receipt.get("apply_allowed")),
        "apply_performed": False,
        "rollback_performed": restored,
        "rollback_snapshot": project_relative(rollback_path) if rollback_path else None,
        "reason": reason,
        "trusted_memory_write": False,
        "source_mutation": False,
        "candidate_memory_only": True,
    }


def apply_candidate_patch(
    candidate: dict[str, Any],
    gate_receipt: dict[str, Any],
    patch: dict[str, Any],
    *,
    approval_token: str,
    created_at: str | None = None,
    report_root: Path = REPORT_ROOT,
) -> dict[str, Any]:
    validate_patch_candidate(candidate)
    validate_gate_receipt(gate_receipt)
    validate_file_patch(patch, candidate)
    created = created_at or now_utc()
    apply_id = apply_receipt_id(str(candidate["candidate_id"]), created)
    rollback_root = report_root / "rollback" / safe_slug(apply_id)
    rollback_root.mkdir(parents=True, exist_ok=True)
    rollback_path: Path | None = None
    if gate_receipt.get("candidate_id") != candidate.get("candidate_id"):
        raise SelfUpgradeError("gate receipt candidate_id mismatch")
    if patch.get("candidate_id") != candidate.get("candidate_id"):
        raise SelfUpgradeError("patch candidate_id mismatch")
    if gate_receipt.get("apply_allowed") is not True:
        raise SelfUpgradeError("gate receipt does not allow apply")
    if gate_receipt.get("apply_performed") is not False:
        raise SelfUpgradeError("gate receipt already indicates apply_performed")
    risk = str(candidate.get("risk_level") or "high")
    expected_apply_token = (
        LOW_RISK_APPLY_TOKEN
        if risk == "low"
        else ELEVATED_RISK_APPLY_TOKEN
    )
    if approval_token != expected_apply_token:
        raise SelfUpgradeError(f"{risk}-risk apply token missing or invalid")

    files: list[dict[str, Any]] = []
    originals: dict[str, str] = {}
    targets: dict[str, Path] = {}
    try:
        for operation in patch["operations"]:
            target = project_path_from_relative(str(operation["file"]))
            rel = project_relative(target)
            if rel not in originals:
                # Byte-faithful read (no newline translation): before_sha256 and
                # the backup must match the on-disk bytes exactly, or the
                # post-deploy rollback gate cannot hash-prove a restore.
                originals[rel] = target.read_bytes().decode("utf-8")
                targets[rel] = target
                backup_path = rollback_root / (safe_backup_name(rel) + ".bak")
                backup_path.write_bytes(originals[rel].encode("utf-8"))
                files.append({
                    "target_file": rel,
                    "backup_path": project_relative(backup_path),
                    "before_sha256": hashlib.sha256(originals[rel].encode("utf-8")).hexdigest(),
                    "backup_sha256": sha256_file(backup_path),
                })
        rollback = _rollback_payload(
            apply_id=apply_id,
            candidate=candidate,
            gate_receipt=gate_receipt,
            patch=patch,
            files=files,
            created_at=created,
            state="ready",
            reason="backup captured before apply",
        )
        rollback_path = write_json(report_root / "rollback" / f"{safe_slug(rollback['rollback_id'])}.json", rollback)

        updated = dict(originals)
        for operation in patch["operations"]:
            rel = project_relative(project_path_from_relative(str(operation["file"])))
            old_text = str(operation["old_text"])
            new_text = str(operation["new_text"])
            if updated[rel].count(old_text) != 1:
                raise SelfUpgradeError(f"stale patch while applying {rel}")
            updated[rel] = updated[rel].replace(old_text, new_text, 1)
        for rel, text in updated.items():
            targets[rel].write_bytes(text.encode("utf-8"))
        for file_info in files:
            target = project_path_from_relative(str(file_info["target_file"]))
            file_info["after_sha256"] = sha256_file(target)
        write_json(rollback_path, {**rollback, "files": files, "state": "applied_backup_ready"})
    except Exception as exc:
        restored = False
        for rel, original in originals.items():
            targets[rel].write_bytes(original.encode("utf-8"))
            restored = True
        if rollback_path:
            rollback = read_json(rollback_path)
            rollback["state"] = "restored_after_apply_failure" if restored else "failed_before_write"
            rollback["reason"] = str(exc)
            write_json(rollback_path, rollback)
        return _apply_failure_receipt(
            apply_id=apply_id,
            candidate=candidate,
            gate_receipt=gate_receipt,
            patch=patch,
            rollback_path=rollback_path,
            created_at=created,
            reason=str(exc),
            restored=restored,
        )

    receipt = {
        "schema": "ENGEL_SELF_UPGRADE_APPLY_RECEIPT_V1",
        "receipt_id": apply_id,
        "candidate_id": candidate["candidate_id"],
        "gate_receipt_id": gate_receipt["receipt_id"],
        "patch_id": patch["patch_id"],
        "created_at_utc": created,
        "status": "applied",
        "apply_allowed_by_gate": True,
        "apply_performed": True,
        "rollback_performed": False,
        "rollback_snapshot": project_relative(rollback_path) if rollback_path else None,
        "changed_files": files,
        "post_apply_verifier_required": True,
        "post_apply_verifier_note": "Run required verifiers after this receipt; failure requires restoring from rollback_snapshot.",
        "trusted_memory_write": False,
        "source_mutation": True,
        "candidate_memory_only": True,
        "storage_context": candidate.get("storage_context"),
    }
    return receipt


def validate_apply_receipt(receipt: dict[str, Any]) -> None:
    if receipt.get("schema") != "ENGEL_SELF_UPGRADE_APPLY_RECEIPT_V1":
        raise SelfUpgradeError("apply receipt schema mismatch")
    if receipt.get("trusted_memory_write") is not False:
        raise SelfUpgradeError("apply receipt cannot write trusted memory")
    if receipt.get("status") not in {"applied", "blocked", "rolled_back"}:
        raise SelfUpgradeError("apply receipt status invalid")
    if receipt.get("status") == "applied" and receipt.get("apply_performed") is not True:
        raise SelfUpgradeError("applied receipt must mark apply_performed")
    if receipt.get("status") != "applied" and receipt.get("source_mutation") is not False:
        raise SelfUpgradeError("non-applied receipt cannot claim source mutation")


def write_apply_receipt(receipt: dict[str, Any], report_root: Path = REPORT_ROOT) -> Path:
    validate_apply_receipt(receipt)
    return write_json(report_root / "apply_receipts" / f"{safe_slug(receipt['receipt_id'])}.json", receipt)


def build_memory_candidate_from_gate(receipt: dict[str, Any], *, lesson: str, created_at: str | None = None) -> dict[str, Any]:
    if receipt.get("schema") != "ENGEL_SELF_UPGRADE_GATE_RECEIPT_V1":
        raise SelfUpgradeError("gate receipt schema mismatch")
    if not lesson.strip():
        raise SelfUpgradeError("lesson is required")
    created = created_at or now_utc()
    return {
        "schema": "ENGEL_SELF_UPGRADE_MEMORY_CANDIDATE_V1",
        "memory_candidate_id": "engel_memory_candidate_" + short_hash(f"{receipt.get('receipt_id')}|{created}"),
        "created_at_utc": created,
        "source_gate_receipt": receipt.get("receipt_id"),
        "source_candidate_id": receipt.get("candidate_id"),
        "lesson": lesson.strip(),
        "trust_level": "candidate_only_untrusted_until_human_review",
        "trusted_memory_write": False,
        "requires_human_review": True,
        "safe_to_auto_promote": False,
    }


def write_memory_candidate(candidate: dict[str, Any], report_root: Path = REPORT_ROOT) -> Path:
    if candidate.get("schema") != "ENGEL_SELF_UPGRADE_MEMORY_CANDIDATE_V1":
        raise SelfUpgradeError("memory candidate schema mismatch")
    if candidate.get("trusted_memory_write") is not False or candidate.get("safe_to_auto_promote") is not False:
        raise SelfUpgradeError("memory candidate cannot be trusted or auto-promoted")
    return write_json(report_root / "memory_candidates" / f"{safe_slug(candidate['memory_candidate_id'])}.json", candidate)


def count_json_files(path: Path) -> int:
    return len(list(path.glob("*.json"))) if path.exists() else 0


def render_status() -> str:
    assert_hdd_vault_registered()
    lines = [
        "Engel Self-Upgrade System V1",
        "",
        "Status:",
        *[f"- {label}" for label in STATUS_LABELS],
        "",
        "Roots:",
        f"- issues: {project_relative(ISSUE_DIR)} ({count_json_files(ISSUE_DIR)})",
        f"- routes: {project_relative(ROUTE_DIR)} ({count_json_files(ROUTE_DIR)})",
        f"- patch candidates: {project_relative(PATCH_CANDIDATE_DIR)} ({count_json_files(PATCH_CANDIDATE_DIR)})",
        f"- gate receipts: {project_relative(GATE_RECEIPT_DIR)} ({count_json_files(GATE_RECEIPT_DIR)})",
        f"- apply receipts: {project_relative(APPLY_RECEIPT_DIR)} ({count_json_files(APPLY_RECEIPT_DIR)})",
        f"- memory candidates: {project_relative(MEMORY_CANDIDATE_DIR)} ({count_json_files(MEMORY_CANDIDATE_DIR)})",
        "",
        "Storage:",
        "- active runtime: /opt/engel on engel-fast-ssd",
        "- archive: /mnt/engel-hdd-vault from engel-hdd-vault on engel-spine-01",
        "- external storage: permanently excluded; all roots outside the CT246 allowlist are rejected",
        "",
        "Boundary: candidates and receipts only until verifier and approval gates pass.",
    ]
    return "\n".join(lines) + "\n"


def command_status(_args: argparse.Namespace) -> int:
    print(render_status(), end="")
    return 0


def command_create_issue(args: argparse.Namespace) -> int:
    issue = build_issue(
        source=args.source,
        symptom=args.symptom,
        severity=args.severity,
        affected_surface=args.surface,
        evidence_paths=args.evidence,
    )
    path = write_issue(issue)
    print(json.dumps({"ok": True, "issue_path": project_relative(path), "issue": issue}, indent=2, sort_keys=True))
    return 0


def command_route_issue(args: argparse.Namespace) -> int:
    issue = load_issue(args.issue)
    route = route_issue(issue)
    path = write_route(route)
    work_order = build_meeting_room_work_order(issue, route)
    work_order_paths = write_meeting_room_work_order(work_order)
    print(json.dumps({
        "ok": True,
        "route_path": project_relative(path),
        "meeting_room_work_order_paths": [project_relative(p) for p in work_order_paths],
        "route": route,
        "meeting_room_work_order": work_order,
    }, indent=2, sort_keys=True))
    return 0


def command_emit_work_order(args: argparse.Namespace) -> int:
    issue = load_issue(args.issue)
    route = load_route(args.route)
    work_order = build_meeting_room_work_order(issue, route)
    paths = write_meeting_room_work_order(work_order)
    print(json.dumps({
        "ok": True,
        "meeting_room_work_order_paths": [project_relative(p) for p in paths],
        "meeting_room_work_order": work_order,
    }, indent=2, sort_keys=True))
    return 0


def command_create_patch_candidate(args: argparse.Namespace) -> int:
    issue = load_issue(args.issue)
    route = load_route(args.route)
    candidate = build_patch_candidate(
        issue,
        route,
        diagnosis=args.diagnosis,
        files_to_change=args.file,
        patch_plan=args.patch_plan,
        patch_file=args.patch_file,
    )
    path = write_patch_candidate(candidate)
    print(json.dumps({"ok": True, "candidate_path": project_relative(path), "candidate": candidate}, indent=2, sort_keys=True))
    return 0


def command_gate_candidate(args: argparse.Namespace) -> int:
    candidate = load_patch_candidate(args.candidate)
    receipt = gate_candidate(candidate, verifier_results=args.verifier_result, approval_token=args.approval_token)
    path = write_gate_receipt(receipt)
    print(json.dumps({"ok": True, "gate_receipt_path": project_relative(path), "gate_receipt": receipt}, indent=2, sort_keys=True))
    return 0


def command_apply_candidate(args: argparse.Namespace) -> int:
    candidate = load_patch_candidate(args.candidate)
    gate_receipt = load_gate_receipt(args.gate_receipt)
    patch_file = args.patch_file or candidate.get("patch_file")
    if not patch_file:
        raise SelfUpgradeError("patch file required by --patch-file or candidate.patch_file")
    patch = load_file_patch(str(patch_file), candidate)
    receipt = apply_candidate_patch(
        candidate,
        gate_receipt,
        patch,
        approval_token=args.approval_token,
    )
    path = write_apply_receipt(receipt)
    print(json.dumps({"ok": receipt.get("status") == "applied", "apply_receipt_path": project_relative(path), "apply_receipt": receipt}, indent=2, sort_keys=True))
    return 0 if receipt.get("status") == "applied" else 1


def command_memory_candidate(args: argparse.Namespace) -> int:
    receipt = read_json(resolve_report_path(args.gate_receipt))
    candidate = build_memory_candidate_from_gate(receipt, lesson=args.lesson)
    path = write_memory_candidate(candidate)
    print(json.dumps({"ok": True, "memory_candidate_path": project_relative(path), "memory_candidate": candidate}, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Engel supervised self-upgrade system.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status").set_defaults(func=command_status)
    issue = sub.add_parser("create-issue")
    issue.add_argument("--source", required=True, choices=sorted(ISSUE_SOURCES))
    issue.add_argument("--surface", required=True, choices=sorted(SURFACES))
    issue.add_argument("--severity", default="medium", choices=sorted(SEVERITIES))
    issue.add_argument("--symptom", required=True)
    issue.add_argument("--evidence", action="append", default=[])
    issue.set_defaults(func=command_create_issue)
    route = sub.add_parser("route-issue")
    route.add_argument("--issue", required=True)
    route.set_defaults(func=command_route_issue)
    work_order = sub.add_parser("emit-work-order")
    work_order.add_argument("--issue", required=True)
    work_order.add_argument("--route", required=True)
    work_order.set_defaults(func=command_emit_work_order)
    patch = sub.add_parser("create-patch-candidate")
    patch.add_argument("--issue", required=True)
    patch.add_argument("--route", required=True)
    patch.add_argument("--diagnosis", required=True)
    patch.add_argument("--patch-plan", required=True)
    patch.add_argument("--file", action="append", required=True)
    patch.add_argument("--patch-file", default=None)
    patch.set_defaults(func=command_create_patch_candidate)
    gate = sub.add_parser("gate-candidate")
    gate.add_argument("--candidate", required=True)
    gate.add_argument("--verifier-result", action="append", default=[])
    gate.add_argument("--approval-token", default="")
    gate.set_defaults(func=command_gate_candidate)
    apply = sub.add_parser("apply-candidate")
    apply.add_argument("--candidate", required=True)
    apply.add_argument("--gate-receipt", required=True)
    apply.add_argument("--patch-file", default=None)
    apply.add_argument("--approval-token", default="")
    apply.set_defaults(func=command_apply_candidate)
    memory = sub.add_parser("memory-candidate")
    memory.add_argument("--gate-receipt", required=True)
    memory.add_argument("--lesson", required=True)
    memory.set_defaults(func=command_memory_candidate)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except SelfUpgradeError as exc:
        print(f"ENGEL_SELF_UPGRADE_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
