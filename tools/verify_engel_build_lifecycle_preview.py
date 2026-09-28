#!/usr/bin/env python3
"""Verify Engel's medium/large build, repair, package, and preview contract."""

from __future__ import annotations

import json
import sys
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import engel_build_lane as lane  # noqa: E402
import engel_main_server_chat_http_service as service  # noqa: E402
import engel_main_local_model_worker as worker  # noqa: E402
import engel_workspace_scaffold as scaffold  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    require(
        lane.classify_build_size("Build me a medium responsive dashboard") == "medium",
        "explicit medium build size was overridden by dashboard heuristics",
    )
    require(
        lane.classify_build_size("Build me a large utility") == "large",
        "explicit large build size was not honored",
    )
    require(
        lane.classify_build_size("Build me an expert multi-service system") == "expert",
        "explicit expert build size was not honored",
    )
    lane_source = (TOOLS / "engel_build_lane.py").read_text(encoding="utf-8")
    require(
        'if provider_review.get("ok") is not True or hard_issues:' in lane_source,
        "unresolved deterministic failures would skip review-guided repair",
    )
    require(
        'residual_limit = 4 if build_size == "expert" else 3 if build_size == "large" else 2' in lane_source,
        "expert builds do not have bounded residual verification repair passes",
    )
    require(
        "Do not use npm packages, bare module imports, CDNs" in lane_source,
        "static web generation does not enforce self-contained runtime dependencies",
    )
    require(
        'for item in workspace.rglob("*.py")' in lane_source,
        "nested Python test suites are not discovered",
    )
    require(
        '"verification_kind": "web_static_runtime"' in lane_source,
        "static web builds do not produce JavaScript syntax evidence",
    )
    require(
        '(/opt/engel/workspaces/[A-Za-z0-9_.-]+)' in lane_source,
        "existing CT246 workspace repair route is missing",
    )
    require(
        "repaired {len(changed_files)} file(s) in existing workspace" in lane_source,
        "existing workspace repair does not report changed-file proof",
    )
    require(
        "repair_context_files = priority_files" in lane_source
        and "name == existing_entry_actual" in lane_source
        and "_files_for_review(repair_context_files, limit=8000)" in lane_source,
        "existing workspace repairs do not include bounded entry-and-test context",
    )
    require(
        lane_source.count("exact_name=existing_workspace is not None") == 4,
        "an existing-workspace repair pass can still be redirected by scaffold slugging",
    )
    require(
        '"build an html website"' in lane_source,
        "an existing web app can be misclassified as plain JavaScript",
    )
    original_workspaces = scaffold.WORKSPACES_DIR
    try:
        with tempfile.TemporaryDirectory(prefix="engel-exact-workspace-") as temp:
            scaffold.WORKSPACES_DIR = Path(temp)
            exact = scaffold.WORKSPACES_DIR / "dependency_"
            exact.mkdir(parents=True)
            (exact / "main.py").write_text("print('old')\n", encoding="utf-8")
            exact_result = scaffold.write_project(
                "repair exact workspace",
                {"main.py": "print('new')\n"},
                name="dependency_",
                overwrite=True,
                exact_name=True,
            )
            require(exact_result.get("ok") is True, "exact-name overwrite failed")
            require(
                Path(str(exact_result.get("path"))).name == "dependency_",
                "exact workspace name changed",
            )
            require(
                (exact / "main.py").read_text(encoding="utf-8") == "print('new')\n",
                "exact workspace was not replaced",
            )
    finally:
        scaffold.WORKSPACES_DIR = original_workspaces
    truncated = worker._extract_project_files(
        "FILE: main.py\n```python\nprint('partial but parseable')\n",
        "main.py",
    )
    require(
        truncated.get("main.py") == "print('partial but parseable')\n",
        "unclosed opening fence leaked into generated source",
    )
    javascript_property = worker._extract_project_files(
        "FILE: sw.js\n```javascript\nconst fallback = {\n"
        "  file: './__offline__/file.txt'\n};\n```\n\n"
        "FILE: icons/icon.svg\n```svg\n<svg></svg>\n```",
        "index.html",
    )
    require(
        "file: './__offline__/file.txt'" in javascript_property.get("sw.js", ""),
        "lowercase JavaScript file property truncated the FILE protocol block",
    )
    require(
        "./__offline__/file.txt" not in javascript_property,
        "lowercase JavaScript file property fabricated a project file",
    )
    json_bundle = worker._extract_project_files(
        "```json\n"
        '{"files":['
        '{"path":"main.py","content":"print(\\\"local json\\\")\\n"},'
        '{"path":"test_main.py","content":"def test_local():\\n    assert True\\n"}'
        "]}\n```",
        "main.py",
    )
    require(
        sorted(json_bundle) == ["main.py", "test_main.py"],
        "structured local-model JSON file bundle was not extracted",
    )
    require(
        json_bundle["main.py"] == 'print("local json")\n',
        "structured JSON file content changed during extraction",
    )
    nested_json_bundle = worker._extract_project_files(
        "```json\n"
        '{"files":{'
        '"main.py":{"content":"print(\\\"nested local json\\\")\\n"},'
        '"test_main.py":{"content":"def test_nested():\\n    assert True\\n"}'
        "}}\n```",
        "main.py",
    )
    require(
        sorted(nested_json_bundle) == ["main.py", "test_main.py"],
        "nested structured local-model JSON file bundle was not extracted",
    )
    require(
        nested_json_bundle["main.py"] == 'print("nested local json")\n',
        "nested structured JSON file content changed during extraction",
    )
    raw_single_target = worker._extract_project_files(
        "```python\n"
        "from __future__ import annotations\n\n"
        "def load_receipts(paths):\n"
        "    return list(paths), []\n"
        "```",
        "conical_proof_viewer.py",
    )
    require(
        sorted(raw_single_target) == ["conical_proof_viewer.py"],
        "single-target raw local repair was assigned to the wrong project file",
    )
    require(
        "ENGEL_SINGLE_FILE_TARGET:" in lane_source
        and "_extract_project_files(repaired_text, entry_actual)" in lane_source
        and "_files_for_review(files, limit=9000)" in lane_source,
        "existing-workspace local repair lacks a bounded actual-entry target",
    )
    collision_files, collision_relocations = lane._resolve_file_directory_collisions(
        {
            "receipts": "receipt1.json\n",
            "receipts/receipt1.json": '{"ok": true}\n',
        }
    )
    require("receipts" not in collision_files, "file/directory collision was not removed")
    require(
        collision_files.get("receipts/README.generated.txt") == "receipt1.json\n",
        "colliding file content was not preserved",
    )
    require(
        collision_files.get("receipts/receipt1.json") == '{"ok": true}\n',
        "child file was lost during collision normalization",
    )
    require(
        len(collision_relocations) == 1,
        "file/directory collision relocation was not recorded",
    )
    strict_review = lane._static_review(
        {"main.py": "def broken(:\n    pass\n"},
        "python",
        "main.py",
        "Build a multi-file Python app with automated tests and sample data",
    )
    strict_issues = "\n".join(strict_review.get("issues") or [])
    for expected in (
        "Python syntax error",
        "multi-file implementation",
        "automated tests",
        "sample-data artifact",
    ):
        require(expected in strict_issues, f"strict build review missed: {expected}")
    temp_root = ROOT / "runtime" / "temp"
    temp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="engel-build-lifecycle-", dir=temp_root) as raw:
        root = Path(raw)
        test_root = root / "requested-tests"
        test_root.mkdir()
        (test_root / "test_build.py").write_text(
            "import unittest\n\n"
            "class BuildTest(unittest.TestCase):\n"
            "    def test_failure_is_visible(self):\n"
            "        self.assertEqual(1, 2)\n",
            encoding="utf-8",
        )
        test_run = lane._run_requested_python_tests(
            str(test_root), "Build an app with automated tests"
        )
        require(test_run is not None, "requested Python tests were not executed")
        require(test_run.get("exit_code") != 0, "failing requested test reported success")
        test_issues = lane._verification_issues(
            {"issues": []}, test_run
        )
        require(
            any("automated tests failed" in issue for issue in test_issues),
            "requested test failure was not promoted to verification failure",
        )
        suffix_test_root = root / "suffix-tests"
        suffix_test_root.mkdir()
        (suffix_test_root / "build_test.py").write_text(
            "import unittest\n\n"
            "class BuildTest(unittest.TestCase):\n"
            "    def test_suffix_file_is_collected(self):\n"
            "        self.assertTrue(True)\n",
            encoding="utf-8",
        )
        suffix_test_run = lane._run_requested_python_tests(
            str(suffix_test_root), "Build an app with automated tests"
        )
        require(suffix_test_run is not None, "suffix-named Python test was not executed")
        require(suffix_test_run.get("exit_code") == 0, "suffix-named Python test failed")
        require(suffix_test_run.get("test_count") == 1, "suffix-named Python test was not collected")

        zero_test_root = root / "zero-tests"
        zero_test_root.mkdir()
        (zero_test_root / "empty_test.py").write_text(
            "import unittest\n",
            encoding="utf-8",
        )
        zero_test_run = lane._run_requested_python_tests(
            str(zero_test_root), "Build an app with automated tests"
        )
        require(zero_test_run is not None, "zero-test verification did not run")
        require(zero_test_run.get("exit_code") != 0, "zero collected tests reported success")
        require(zero_test_run.get("zero_tests_collected") is True, "zero-test failure lacked proof")

        missing_test_root = root / "missing-tests"
        missing_test_root.mkdir()
        (missing_test_root / "main.py").write_text("print('no tests')\n", encoding="utf-8")
        missing_test_run = lane._run_requested_python_tests(
            str(missing_test_root), "Build an app with automated tests"
        )
        require(missing_test_run is not None, "missing requested tests fell through to app execution")
        require(missing_test_run.get("exit_code") != 0, "missing requested tests reported success")
        old_workspaces = scaffold.WORKSPACES_DIR
        old_packages = lane.PACKAGE_ROOT
        scaffold.WORKSPACES_DIR = root / "workspaces"
        lane.PACKAGE_ROOT = root / "packages"
        calls: list[str] = []

        rejected_collision = scaffold.write_project(
            "atomic collision rejection proof",
            {
                "receipts": "receipt1.json\n",
                "receipts/receipt1.json": '{"ok": true}\n',
            },
            overwrite=True,
        )
        require(
            rejected_collision.get("ok") is False,
            "workspace scaffold accepted a file/directory path collision",
        )
        require(
            rejected_collision.get("path_collisions"),
            "workspace scaffold did not explain the path collision",
        )
        require(
            not (scaffold.WORKSPACES_DIR / "atomic_collision_rejection_proof").exists(),
            "failed staged workspace left a partial destination",
        )

        first_overwrite = scaffold.write_project(
            "atomic overwrite proof",
            {"old.py": "print('old')\n"},
            overwrite=True,
        )
        second_overwrite = scaffold.write_project(
            "atomic overwrite proof",
            {"new.py": "print('new')\n"},
            overwrite=True,
        )
        overwrite_path = Path(str(second_overwrite.get("path") or ""))
        require((overwrite_path / "new.py").is_file(), "overwrite lost new project file")
        require(not (overwrite_path / "old.py").exists(), "overwrite retained stale project file")
        require(
            Path(str(second_overwrite.get("replaced_workspace_backup") or "")).is_dir(),
            "overwrite did not preserve the replaced workspace backup",
        )
        restore_result = scaffold.restore_workspace_backup(
            str(overwrite_path),
            str(second_overwrite.get("replaced_workspace_backup") or ""),
        )
        require(restore_result.get("ok") is True, "verified workspace rollback failed")
        require((overwrite_path / "old.py").is_file(), "rollback did not restore prior workspace")
        require(not (overwrite_path / "new.py").exists(), "rollback retained failed candidate file")
        require(
            Path(str(restore_result.get("failed_candidate_backup") or "")).is_dir(),
            "rollback did not preserve the failed candidate",
        )
        require(
            "restore_workspace_backup(" in lane_source
            and '"failed candidate preserved and pre-build workspace restored"' in lane_source,
            "build lane does not automatically restore a failed existing-workspace candidate",
        )

        def generate(prompt: str, _timeout: int, _tokens: int) -> str:
            calls.append(prompt)
            if prompt.startswith("Repair this Engel build"):
                return """FILE: index.html
```
<!doctype html><html><head><meta charset="utf-8"><title>Proof</title></head>
<body><main><h1>Engel proof</h1><button id="run">Run</button></main>
<script>document.querySelector('#run').onclick=()=>document.body.dataset.ran='true';</script>
</body></html>
```
FILE: README.md
```
# Engel proof web app
```
"""
            if prompt.startswith("Review this completed Engel build"):
                return json.dumps(
                    {
                        "verdict": "pass",
                        "summary": "Complete runnable web artifact.",
                        "issues": [],
                    }
                )
            return """FILE: index.html
```
<main>broken first pass</main>
```
"""

        try:
            receipt = lane.run_build(
                "Build me a medium web app called lifecycle proof, overwrite.",
                generate,
                request_id="verify-lifecycle",
            )
        finally:
            scaffold.WORKSPACES_DIR = old_workspaces
            lane.PACKAGE_ROOT = old_packages

        require(isinstance(receipt, dict), "build receipt missing")
        require(receipt.get("ok") is True, "repaired build did not verify")
        require(receipt.get("build_size") == "medium", "build size mismatch")
        require(receipt.get("build_verified") is True, "verified marker missing")
        lifecycle = receipt.get("build_lifecycle") or []
        stages = [(row.get("stage"), row.get("status")) for row in lifecycle]
        for expected in [
            ("plan", "passed"),
            ("generate", "passed"),
            ("workspace", "passed"),
            ("verify", "failed"),
            ("repair", "passed"),
            ("review", "passed"),
            ("package", "passed"),
            ("open_proof", "ready"),
        ]:
            require(expected in stages, f"lifecycle stage missing: {expected}")
        require(len(calls) == 2, f"expected generate and repair calls; got {len(calls)}")
        evidence_review = (receipt.get("build_review") or {}).get("provider") or {}
        require(
            evidence_review.get("reviewer") == "engel-evidence-build-review",
            f"final review was not verifier-backed: {evidence_review}",
        )
        require(
            evidence_review.get("model_review_used") is False,
            "default build path spent a redundant model review turn",
        )

        package = receipt.get("build_package") or {}
        package_path = Path(str(package.get("path") or ""))
        require(package_path.is_file(), "package ZIP missing")
        with zipfile.ZipFile(package_path) as archive:
            require("index.html" in archive.namelist(), "package does not include index.html")

        preview = receipt.get("build_preview") or {}
        require(preview.get("kind") == "web", "web preview kind missing")
        require(str(preview.get("url") or "").endswith("/index.html"), "preview URL missing")
        require("<html" in (Path(str(preview["workspace_path"])) / "index.html").read_text(encoding="utf-8"), "repair was not saved")

        failed = lane.run_build(
            "Build me a medium Python app called visible failure, overwrite.",
            lambda _prompt, _timeout, _tokens: "",
            request_id="verify-visible-failure",
        )
        require(isinstance(failed, dict), "generation failure fell through to normal chat")
        require(failed.get("build_lane_used") is True, "failed build receipt lost its lane marker")
        require(failed.get("build_verified") is False, "failed generation claimed verification")
        require(
            (failed.get("build_lifecycle") or [])[-1].get("stage") == "generate",
            "failed generation lifecycle is not visible",
        )

        approved = service._path_below(root, "workspaces")
        require(approved == (root / "workspaces").resolve(), "approved path resolution failed")
        try:
            service._path_below(root, "../outside")
        except ValueError:
            pass
        else:
            raise AssertionError("path traversal was accepted")

        print(
            json.dumps(
                {
                    "ok": True,
                    "schema": "engel_build_lifecycle_preview_verifier_v1",
                    "stages": stages,
                    "package_files": package.get("files"),
                    "preview": preview,
                },
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
