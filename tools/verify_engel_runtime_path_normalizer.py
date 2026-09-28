#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import sys


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "engel_runtime_path_normalizer.py"
TEST_ROOT = ROOT / "runtime" / "tests" / "engel_runtime_path_normalizer"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_module():
    spec = importlib.util.spec_from_file_location("engel_runtime_path_normalizer", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load path normalizer")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    module = load_module()
    if TEST_ROOT.exists():
        shutil.rmtree(TEST_ROOT)
    runtime_root = TEST_ROOT / "opt" / "engel"
    state_root = TEST_ROOT / "state"
    runtime_root.mkdir(parents=True)
    try:
        allowed = module.check_path("/opt/engel/models-active/model.gguf")
        require(allowed["allowed"] is True, "CT246 SSD active path should be allowed")

        blocked_paths = [
            "/srv/unapproved/models/model.gguf",
            "/var/lib/unapproved/model.gguf",
            "F:\\models\\model.gguf",
            "/opt/engel/F:/models/model.gguf",
            "/opt/engel/unapproved-storage-alias/model.gguf",
        ]
        for raw in blocked_paths:
            result = module.check_path(raw)
            require(result["allowed"] is False, f"forbidden path passed: {raw}")

        archive_active = module.check_path("/mnt/engel-hdd-vault/models/model.gguf")
        require(archive_active["allowed"] is False, "HDD archive must be blocked for active runtime")
        archive_ok = module.check_path("/mnt/engel-hdd-vault/models/model.gguf", purpose="archive")
        require(archive_ok["allowed"] is True, "HDD archive path should be allowed for archive purpose")

        event_path = state_root / "blocked_path_events.jsonl"
        event = module.record_blocked_path(
            module.check_path("/srv/unapproved/test"),
            source="verifier",
            events_path=event_path,
        )
        require(event["event_type"] == "runtime.path.blocked", "blocked event type mismatch")
        require(event_path.is_file(), "blocked event ledger missing")
        saved = json.loads(event_path.read_text(encoding="utf-8").splitlines()[-1])
        require(saved["event_id"] == event["event_id"], "blocked event was not durably appended")

        leaked_root = runtime_root / "unapproved-storage-alias"
        leaked = leaked_root / "models"
        leaked.mkdir(parents=True)
        (leaked / "probe.txt").write_text("probe\n", encoding="utf-8")
        scan = module.scan_runtime_tree(runtime_root, state_root=state_root, max_entries=100)
        require(scan["ok"] is False and scan["blocked_count"] >= 1, "nested Windows path leak was not found")
        require(scan["scan_truncated"] is False, "small verifier scan should complete")
        require((state_root / "blocked_path_events.jsonl").is_file(), "scan did not write blocked event")

        try:
            module.quarantine_path(
                leaked_root,
                approval_token="wrong",
                runtime_root=runtime_root,
                state_root=state_root,
            )
        except module.PathBoundaryError:
            pass
        else:
            raise AssertionError("wrong token allowed quarantine")
        require(leaked_root.exists(), "wrong token mutated the path")

        receipt = module.quarantine_path(
            leaked_root,
            approval_token=module.QUARANTINE_TOKEN,
            runtime_root=runtime_root,
            state_root=state_root,
        )
        require(receipt["ok"] is True and receipt["deleted"] is False, "quarantine receipt mismatch")
        require(not leaked_root.exists(), "approved quarantine did not move the leak")
        require(Path(receipt["destination_path"]).exists(), "quarantined item missing")
        require(Path(receipt["receipt_path"]).is_file(), "quarantine receipt file missing")

        print("PASS allowed_active_ssd")
        print("PASS unapproved_storage_paths")
        print("PASS archive_role_boundary")
        print("PASS blocked_event_ledger")
        print("PASS bounded_scan")
        print("PASS approval_gated_quarantine")
        print("ENGEL_RUNTIME_PATH_NORMALIZER_VERIFY_PASS")
        return 0
    finally:
        if TEST_ROOT.exists():
            shutil.rmtree(TEST_ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
