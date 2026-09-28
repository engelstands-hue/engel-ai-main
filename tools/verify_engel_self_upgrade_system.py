from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
TOPOLOGY = ROOT / "memory" / "ENGEL_SYSTEM_TOPOLOGY_REGISTRY_V1.json"
MATRIX = ROOT / "memory" / "ENGEL_SELF_UPGRADE_VERIFIER_MATRIX_V1.json"
CONTRACT = ROOT / "memory" / "ENGEL_SELF_UPGRADE_SYSTEM_CONTRACT_V1.md"
MODULE = ROOT / "engel_self_upgrade_system.py"
ROUTER = ROOT / "tools" / "engel_self_upgrade_router.py"
APPLY_GATE = ROOT / "tools" / "engel_self_upgrade_apply_gate.py"
APPLY_ENGINE = ROOT / "tools" / "engel_self_upgrade_apply_engine.py"
LEARNING_PROMOTER = ROOT / "tools" / "engel_self_upgrade_learning_promoter.py"
CHAT_PROBE = ROOT / "tools" / "engel_chat_self_heal_probe.py"
STORAGE_REGISTRY = ROOT / "memory" / "ENGEL_STORAGE_LOCATION_REGISTRY_V1.json"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"

HDD_ARCHIVE_MOUNT = "/mnt/engel-hdd-vault"
ACTIVE_RUNTIME_ROOT = "/opt/engel"
ALLOWED_STORAGE_ROOTS = [ACTIVE_RUNTIME_ROOT, HDD_ARCHIVE_MOUNT]
RETIRED_DESKTOP_NODE_ID = "DESKTOP-" + "FIB17O7"

FORBIDDEN_IMPORTS = {
    "subprocess",
    "webbrowser",
    "openai",
    "anthropic",
    "google",
    "socket",
    "ftplib",
    "smtplib",
    "multiprocessing",
    "threading",
}

FORBIDDEN_CALLS = {
    "eval",
    "exec",
    "__import__",
    "compile",
    "Popen",
    "system",
    "startfile",
    "unlink",
    "remove",
    "rename",
    "rmdir",
}


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    require(path.exists(), "missing required path: " + str(path.relative_to(ROOT)))
    return path.read_text(encoding="utf-8", errors="replace")


def load_json(path: Path) -> dict:
    data = json.loads(read(path))
    require(isinstance(data, dict), "JSON must be object: " + str(path.relative_to(ROOT)))
    return data


def load_module():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("engel_self_upgrade_system", MODULE)
    require(spec is not None and spec.loader is not None, "could not load self-upgrade module")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_self_upgrade_system"] = module
    spec.loader.exec_module(module)
    return module


def check_files() -> None:
    for path in [TOPOLOGY, MATRIX, CONTRACT, MODULE, ROUTER, APPLY_GATE, APPLY_ENGINE, LEARNING_PROMOTER, CHAT_PROBE]:
        require(path.exists(), "missing required path: " + str(path.relative_to(ROOT)))


def check_topology_and_storage() -> None:
    topology = load_json(TOPOLOGY)
    storage = load_json(STORAGE_REGISTRY)
    require(topology.get("schema") == "ENGEL_SYSTEM_TOPOLOGY_REGISTRY_V1", "topology schema mismatch")
    nodes = topology.get("nodes", {})
    for node in ["ct246_engel_ai_main", "rog_controller", "sub_desktop", "android_worker_alpha", "android_worker_beta", "android_worker_gamma"]:
        require(node in nodes, "topology missing node: " + node)
    ct = nodes["ct246_engel_ai_main"]
    require(ct.get("ct_id") == 246, "CT246 id missing")
    require(ct.get("host") == "engel-spine-01", "CT host mismatch")
    sub = nodes["sub_desktop"]
    require(sub.get("current_node_url") == "http://198.51.100.227:8776", "Sub desktop node URL mismatch")
    disabled = topology.get("disabled_nodes", [])
    require(all(not (isinstance(item, dict) and item.get("node_id") == RETIRED_DESKTOP_NODE_ID) for item in disabled), "retired desktop must not appear in active topology lists")
    archive = topology.get("storage", {}).get("archive", {})
    require(archive.get("name") == "engel-hdd-vault", "topology missing engel-hdd-vault")
    require(archive.get("node") == "engel-spine-01", "hdd vault node mismatch")
    require(archive.get("ct_mount") == HDD_ARCHIVE_MOUNT, "hdd vault mount mismatch")
    hdd = storage.get("dell_poweredge_hdd_vault", {})
    require(hdd.get("name") == "engel-hdd-vault", "storage registry missing hdd vault")
    require(hdd.get("proxmox_host") == "engel-spine-01", "storage registry hdd vault host mismatch")
    require(hdd.get("container_mount") == HDD_ARCHIVE_MOUNT, "storage registry hdd vault mount mismatch")
    require(storage.get("allowed_storage_roots") == ALLOWED_STORAGE_ROOTS, "storage registry allowlist mismatch")


def check_matrix() -> None:
    matrix = load_json(MATRIX)
    require(matrix.get("schema") == "ENGEL_SELF_UPGRADE_VERIFIER_MATRIX_V1", "matrix schema mismatch")
    surfaces = matrix.get("surfaces", {})
    for surface in ["chat", "discord", "training", "meeting_room", "sub_desktop", "android_worker", "provider_bridge", "storage", "source_patch", "memory_promotion"]:
        require(surface in surfaces, "matrix missing surface: " + surface)
        entry = surfaces[surface]
        require(entry.get("required_verifiers"), "surface missing required verifiers: " + surface)
    require("tools\\verify_engel_discord_identity_guard.py" in surfaces["chat"].get("required_verifiers", []), "chat surface missing Discord identity guard")
    require("tools\\verify_engel_discord_identity_guard.py" in surfaces["discord"].get("required_verifiers", []), "discord surface missing Discord identity guard")
    require("tools\\verify_engel_training_capture_filter.py" in surfaces["training"].get("required_verifiers", []), "training surface missing capture filter verifier")
    require("tools\\verify_engel_model_promotion_gate.py" in surfaces["training"].get("required_verifiers", []), "training surface missing model promotion verifier")
    rules = matrix.get("global_rules", {})
    require(rules.get("hdd_archive_target") == HDD_ARCHIVE_MOUNT, "matrix hdd target mismatch")
    require(rules.get("hdd_archive_node") == "engel-spine-01", "matrix hdd node mismatch")
    require(rules.get("allowed_storage_roots") == ALLOWED_STORAGE_ROOTS, "matrix storage allowlist mismatch")
    require(rules.get("external_storage_permanently_excluded") is True, "matrix must exclude external storage")


def check_static_safety() -> None:
    for path in [MODULE, ROUTER, APPLY_GATE, APPLY_ENGINE, LEARNING_PROMOTER]:
        source = read(path)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    require(alias.name.split(".")[0] not in FORBIDDEN_IMPORTS, f"{path.name} forbidden import: {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                require(node.module.split(".")[0] not in FORBIDDEN_IMPORTS, f"{path.name} forbidden import: {node.module}")
            elif isinstance(node, ast.Call):
                func = node.func
                name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
                require(name not in FORBIDDEN_CALLS, f"{path.name} forbidden call: {name}")
        if path == MODULE:
            for marker in ["safe_to_auto_apply", "trusted_memory_write", HDD_ARCHIVE_MOUNT, "ALLOWED_STORAGE_ROOTS", "RETIRED_DESKTOP_NODE_ID"]:
                require(marker in source, f"{path.name} missing marker: {marker}")
    probe = read(CHAT_PROBE)
    require("127.0.0.1" in probe and "local_only_url" in probe, "chat probe must be local-only")
    require("openai" not in probe.lower() and "anthropic" not in probe.lower(), "chat probe must not call providers")


def check_runtime_flow() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmp:
        report_root = Path(tmp) / "self_upgrade"
        issue = module.build_issue(
            source="chat_ui",
            symptom="chat timed out after 300 seconds",
            severity="medium",
            affected_surface="chat",
            created_at="2026-07-04T20:00:00Z",
        )
        issue_path = module.write_issue(issue, report_root=report_root)
        require(issue_path.exists(), "issue write failed")
        route = module.route_issue(issue, created_at="2026-07-04T20:01:00Z")
        route_path = module.write_route(route, report_root=report_root)
        require(route_path.exists(), "route write failed")
        require(route["storage_context"]["archive"] == HDD_ARCHIVE_MOUNT, "route archive mismatch")
        require(route["storage_context"]["allowed_roots"] == ALLOWED_STORAGE_ROOTS, "route storage allowlist mismatch")
        require(route["storage_context"]["external_storage_permanently_excluded"] is True, "route external storage policy mismatch")
        work_order = module.build_meeting_room_work_order(issue, route)
        work_order_paths = module.write_meeting_room_work_order(
            work_order,
            memory_dir=report_root / "meeting_room" / "work_orders",
            runtime_dir=report_root / "runtime" / "meeting_room" / "self_upgrade_work_orders",
        )
        require(len(work_order_paths) == 2 and all(path.exists() for path in work_order_paths), "meeting-room work order write failed")
        require(work_order["schema"] == "ENGEL_MEETING_ROOM_SELF_UPGRADE_WORK_ORDER_V1", "work order schema mismatch")
        require(work_order["storage_context"]["archive"] == HDD_ARCHIVE_MOUNT, "work order archive mismatch")
        require(work_order["storage_context"]["allowed_roots"] == ALLOWED_STORAGE_ROOTS, "work order storage allowlist mismatch")
        require(work_order["storage_context"]["external_storage_permanently_excluded"] is True, "work order external storage policy mismatch")
        require(RETIRED_DESKTOP_NODE_ID not in work_order.get("worker_lanes", []), "work order routed disabled desktop")
        candidate = module.build_patch_candidate(
            issue,
            route,
            diagnosis="The chat request timed out and needs routing/verifier review.",
            files_to_change=["tools\\engel_chat_self_heal_probe.py"],
            patch_plan="Update the bounded local chat probe and verifier coverage before any live routing change.",
            created_at="2026-07-04T20:02:00Z",
        )
        candidate_path = module.write_patch_candidate(candidate, report_root=report_root)
        require(candidate_path.exists(), "candidate write failed")
        receipt = module.gate_candidate(candidate, verifier_results=[str(CONTRACT)], created_at="2026-07-04T20:03:00Z")
        receipt_path = module.write_gate_receipt(receipt, report_root=report_root)
        require(receipt_path.exists(), "gate receipt write failed")
        require(receipt["apply_performed"] is False, "gate must not apply")
        require(receipt["apply_allowed"] is False, "medium-risk gate must require elevated approval")
        elevated_receipt = module.gate_candidate(
            candidate,
            verifier_results=[str(CONTRACT)],
            approval_token=module.ELEVATED_RISK_GATE_TOKEN,
            created_at="2026-07-04T20:03:30Z",
        )
        require(
            elevated_receipt["apply_allowed"] is True
            and elevated_receipt["approval_class"] == "elevated_risk",
            "approved medium-risk gate did not allow the protected apply lane",
        )
        wrong_risk_receipt = module.gate_candidate(
            candidate,
            verifier_results=[str(CONTRACT)],
            approval_token=module.LOW_RISK_GATE_TOKEN,
            created_at="2026-07-04T20:03:45Z",
        )
        require(
            wrong_risk_receipt["apply_allowed"] is False,
            "low-risk token was accepted for an elevated-risk candidate",
        )
        memory = module.build_memory_candidate_from_gate(receipt, lesson="Chat timeout repairs must route through verifier-backed candidates.", created_at="2026-07-04T20:04:00Z")
        memory_path = module.write_memory_candidate(memory, report_root=report_root)
        require(memory_path.exists(), "memory candidate write failed")
        require(memory["trusted_memory_write"] is False, "memory candidate must not write trusted memory")

        target = ROOT / "reports" / "self_upgrade" / "verifier_results" / "apply_probe_target.txt"
        target.parent.mkdir(parents=True, exist_ok=True)
        # write_bytes: the apply lane is byte-exact (no newline translation), so
        # the fixture must be too or old_text will not match on Windows.
        target.write_bytes("apply-probe-before\n".encode("utf-8"))
        try:
            low_issue = module.build_issue(
                source="manual",
                symptom="low-risk apply probe",
                severity="low",
                affected_surface="chat",
                created_at="2026-07-04T20:05:00Z",
            )
            low_route = module.route_issue(low_issue, created_at="2026-07-04T20:06:00Z")
            low_candidate = module.build_patch_candidate(
                low_issue,
                low_route,
                diagnosis="A low-risk exact-text patch should apply only through the protected apply engine.",
                files_to_change=[module.project_relative(target)],
                patch_plan="Replace one probe marker after gate approval and rollback backup capture.",
                created_at="2026-07-04T20:07:00Z",
            )
            blocked_low_gate = module.gate_candidate(low_candidate, verifier_results=[str(CONTRACT)], created_at="2026-07-04T20:08:00Z")
            require(blocked_low_gate["apply_allowed"] is False, "low-risk gate must require approval token")
            low_gate = module.gate_candidate(
                low_candidate,
                verifier_results=[str(CONTRACT)],
                approval_token=module.LOW_RISK_GATE_TOKEN,
                created_at="2026-07-04T20:09:00Z",
            )
            require(low_gate["apply_allowed"] is True, "approved low-risk gate should allow apply")
            file_patch = module.build_file_patch(
                low_candidate,
                operations=[
                    {
                        "op": "replace_text",
                        "file": module.project_relative(target),
                        "old_text": "apply-probe-before\n",
                        "new_text": "apply-probe-after\n",
                    }
                ],
                created_at="2026-07-04T20:10:00Z",
            )
            apply_receipt = module.apply_candidate_patch(
                low_candidate,
                low_gate,
                file_patch,
                approval_token=module.LOW_RISK_APPLY_TOKEN,
                created_at="2026-07-04T20:11:00Z",
            )
            apply_path = module.write_apply_receipt(apply_receipt)
            require(apply_path.exists(), "apply receipt write failed")
            require(apply_receipt["status"] == "applied" and apply_receipt["apply_performed"] is True, "approved low-risk apply did not apply")
            require(target.read_text(encoding="utf-8") == "apply-probe-after\n", "apply target did not change")
            rollback_snapshot = ROOT / apply_receipt["rollback_snapshot"].replace("\\", "/")
            require(rollback_snapshot.exists(), "rollback snapshot missing")
            require(apply_receipt["trusted_memory_write"] is False, "apply receipt must not write trusted memory")

            medium_issue = module.build_issue(
                source="manual",
                symptom="medium-risk approved apply probe",
                severity="medium",
                affected_surface="chat",
                created_at="2026-07-04T20:12:00Z",
            )
            medium_route = module.route_issue(
                medium_issue,
                created_at="2026-07-04T20:13:00Z",
            )
            medium_candidate = module.build_patch_candidate(
                medium_issue,
                medium_route,
                diagnosis="The reviewed fixture needs one elevated-risk exact replacement.",
                files_to_change=[module.project_relative(target)],
                patch_plan="Replace one reviewed marker through the elevated approval lane.",
                created_at="2026-07-04T20:14:00Z",
            )
            medium_gate = module.gate_candidate(
                medium_candidate,
                verifier_results=[str(CONTRACT)],
                approval_token=module.ELEVATED_RISK_GATE_TOKEN,
                created_at="2026-07-04T20:15:00Z",
            )
            medium_patch = module.build_file_patch(
                medium_candidate,
                operations=[
                    {
                        "op": "replace_text",
                        "file": module.project_relative(target),
                        "old_text": "apply-probe-after\n",
                        "new_text": "apply-probe-elevated\n",
                    }
                ],
                created_at="2026-07-04T20:16:00Z",
            )
            medium_apply = module.apply_candidate_patch(
                medium_candidate,
                medium_gate,
                medium_patch,
                approval_token=module.ELEVATED_RISK_APPLY_TOKEN,
                created_at="2026-07-04T20:17:00Z",
            )
            require(
                medium_apply["status"] == "applied"
                and target.read_text(encoding="utf-8") == "apply-probe-elevated\n",
                "approved elevated-risk apply did not mutate the fixture",
            )
        finally:
            if target.exists():
                target.unlink()

        status = module.render_status()
        require("engel-hdd-vault" in status and "external storage: permanently excluded" in status, "status missing CT246 storage boundary")


def check_docs_and_registration() -> None:
    commands = read(COMMANDS)
    for command in [
        "self upgrade status",
        "self upgrade create issue",
        "self upgrade route issue",
        "self upgrade emit work order",
        "self upgrade patch candidate",
        "self upgrade gate candidate",
        "self upgrade apply candidate",
        "chat self-heal probe",
    ]:
        require(command in commands, "ENGEL_COMMANDS missing command: " + command)
    verify = read(CODEX_VERIFY)
    require("tools\\verify_engel_self_upgrade_system.py" in verify, "codex verifier missing self-upgrade verifier")
    require("tools\\verify_engel_discord_identity_guard.py" in verify, "codex verifier missing Discord identity verifier")
    require("tools\\verify_engel_training_capture_filter.py" in verify, "codex verifier missing training capture verifier")
    require("tools\\verify_engel_model_promotion_gate.py" in verify, "codex verifier missing model promotion verifier")
    contract = read(CONTRACT)
    for marker in ["CT246", "Sub desktop", "Android workers", "engel-hdd-vault", "external arrays", "issue -> route", "apply_receipts", "APPLY_ENGEL_SELF_UPGRADE_LOW_RISK_V1"]:
        require(marker in contract, "contract missing marker: " + marker)


def main() -> int:
    checks = [
        ("files", check_files),
        ("topology_and_storage", check_topology_and_storage),
        ("matrix", check_matrix),
        ("static_safety", check_static_safety),
        ("runtime_flow", check_runtime_flow),
        ("docs_and_registration", check_docs_and_registration),
    ]
    failures: list[str] = []
    for name, check in checks:
        try:
            check()
            print("PASS", name)
        except CheckFailure as exc:
            print("FAIL", name, "-", exc)
            failures.append(f"{name}: {exc}")
    if failures:
        print("\nENGEL_SELF_UPGRADE_SYSTEM_VERIFY_FAIL")
        for failure in failures:
            print("-", failure)
        return 1
    print("\nENGEL_SELF_UPGRADE_SYSTEM_VERIFY_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
