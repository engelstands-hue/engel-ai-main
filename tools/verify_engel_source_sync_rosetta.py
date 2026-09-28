#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil
import sys


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "engel_source_sync_rosetta.py"
TEST_ROOT = ROOT / "runtime" / "tests" / "engel_source_sync_rosetta"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_module():
    spec = importlib.util.spec_from_file_location("engel_source_sync_rosetta", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load source sync module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    module = load_module()
    if TEST_ROOT.exists():
        shutil.rmtree(TEST_ROOT)
    source_root = TEST_ROOT / "rog"
    target_root = TEST_ROOT / "ct"
    for root in (source_root, target_root):
        (root / "tools").mkdir(parents=True)
    try:
        paths = ["tools/example_a.py", "tools/example_b.py"]
        (source_root / paths[0]).write_text("new a\n", encoding="utf-8")
        (source_root / paths[1]).write_text("new b\n", encoding="utf-8")
        (target_root / paths[0]).write_text("old a\n", encoding="utf-8")

        source = module.build_manifest(source_root, paths, role="rog_source")
        expected = module.build_manifest(target_root, paths, role="ct_target_preflight")
        require(source["all_present"] is True, "source manifest should require all source files")
        require(expected["all_present"] is False, "target fixture should include a new file")

        preflight = module.build_preflight(source, expected, target_root)
        require(preflight["ok"] is True and preflight["sync_allowed"] is True, "clean preflight blocked")
        states = {item["relative_path"]: item["state"] for item in preflight["files"]}
        require(states[paths[0]] == "update_candidate", "changed target classification mismatch")
        require(states[paths[1]] == "new_file", "new target classification mismatch")
        require((target_root / paths[0]).read_text(encoding="utf-8") == "old a\n", "preflight mutated target")
        require(not (target_root / paths[1]).exists(), "preflight created target")

        (target_root / paths[0]).write_text("concurrent edit\n", encoding="utf-8")
        drift = module.build_preflight(source, expected, target_root)
        require(drift["ok"] is False and drift["sync_allowed"] is False, "concurrent target drift was not blocked")
        require(any(item["state"] == "target_drift" for item in drift["files"]), "target drift state missing")

        (target_root / paths[0]).write_text("old a\n", encoding="utf-8")
        preflight = module.build_preflight(source, expected, target_root)
        shutil.copy2(source_root / paths[0], target_root / paths[0])
        shutil.copy2(source_root / paths[1], target_root / paths[1])
        post = module.verify_post_deploy(source, preflight, target_root)
        require(post["ok"] is True and post["matched_count"] == 2, "post-deploy proof failed")

        (target_root / paths[1]).write_text("regressed\n", encoding="utf-8")
        mismatch = module.verify_post_deploy(source, preflight, target_root)
        require(mismatch["ok"] is False, "post-deploy mismatch passed")

        for invalid in ("../escape.py", "runtime/secret.py", "tools/.env", "C:/secret.py"):
            try:
                module.canonical_relative(invalid)
            except module.SourceSyncError:
                pass
            else:
                raise AssertionError(f"unsafe path accepted: {invalid}")

        print("PASS explicit_manifest")
        print("PASS preflight_no_mutation")
        print("PASS concurrent_drift_block")
        print("PASS post_deploy_hash_proof")
        print("PASS unsafe_path_refusal")
        print("ENGEL_SOURCE_SYNC_ROSETTA_VERIFY_PASS")
        return 0
    finally:
        if TEST_ROOT.exists():
            shutil.rmtree(TEST_ROOT)


if __name__ == "__main__":
    raise SystemExit(main())

