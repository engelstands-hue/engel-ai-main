#!/usr/bin/env python3
"""Verify large CT246 builds use explicit-language, bounded per-file assembly."""

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
import engel_workspace_scaffold as scaffold  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    language = lane._infer_build_language_for_request(
        "build a local python web app with tests"
    )
    require(language[0] == "python", "explicit Python lost to generic web-app detection")

    prompt = (
        "This is a large job. Build me a local Python web app called Bounded "
        "Worker Proof. It loads conical receipt JSON and shows final status. "
        "Include automated tests and a runnable package."
    )
    calls: list[dict[str, object]] = []

    def generate(gen_prompt: str, timeout_s: int, max_tokens: int) -> str:
        calls.append(
            {
                "prompt": gen_prompt,
                "timeout_s": timeout_s,
                "max_tokens": max_tokens,
            }
        )
        if gen_prompt.startswith("Plan this Engel build"):
            return json.dumps(
                {
                    "entry_file": "main.py",
                    "files": [
                        {
                            "path": "main.py",
                            "purpose": "CLI entry and HTML rendering boundary.",
                            "depends_on": ["receipt_loader.py"],
                        },
                        {
                            "path": "receipt_loader.py",
                            "purpose": "Validate and summarize conical receipt JSON.",
                            "depends_on": [],
                        },
                        {
                            "path": "tests/test_receipt_loader.py",
                            "purpose": "Automated malformed and valid receipt coverage.",
                            "depends_on": ["receipt_loader.py"],
                        },
                    ],
                }
            )
        if "TARGET FILE: main.py" in gen_prompt:
            return (
                "FILE: main.py\n```python\n"
                "from receipt_loader import summarize_receipt\n\n"
                "def render_status(receipt: dict) -> str:\n"
                "    summary = summarize_receipt(receipt)\n"
                "    return f\"<h1>{summary['job_id']}</h1><p>{summary['status']}</p>\"\n\n"
                "def main() -> int:\n"
                "    print('Bounded Worker Proof is ready')\n"
                "    return 0\n\n"
                "if __name__ == '__main__':\n"
                "    raise SystemExit(main())\n"
                "```\n"
            )
        if "TARGET FILE: receipt_loader.py" in gen_prompt:
            return (
                "FILE: receipt_loader.py\n```python\n"
                "from __future__ import annotations\n\n"
                "def summarize_receipt(receipt: dict) -> dict[str, str]:\n"
                "    if not isinstance(receipt, dict):\n"
                "        raise ValueError('receipt must be an object')\n"
                "    return {\n"
                "        'job_id': str(receipt.get('job_id') or 'unknown'),\n"
                "        'status': str(receipt.get('final_status') or receipt.get('status') or 'unknown'),\n"
                "    }\n"
                "```\n"
            )
        if "TARGET FILE: tests/test_receipt_loader.py" in gen_prompt:
            return (
                "FILE: tests/test_receipt_loader.py\n```python\n"
                "import unittest\n\n"
                "from receipt_loader import summarize_receipt\n\n"
                "class ReceiptLoaderTests(unittest.TestCase):\n"
                "    def test_summarizes_final_status(self):\n"
                "        value = summarize_receipt({'job_id': 'job-1', 'final_status': 'finished'})\n"
                "        self.assertEqual(value, {'job_id': 'job-1', 'status': 'finished'})\n\n"
                "    def test_rejects_non_object(self):\n"
                "        with self.assertRaises(ValueError):\n"
                "            summarize_receipt([])\n"
                "```\n"
            )
        return ""

    original_workspaces = scaffold.WORKSPACES_DIR
    original_packages = lane.PACKAGE_ROOT
    try:
        with tempfile.TemporaryDirectory(
            prefix="engel-bounded-file-build-",
            dir=ROOT / "runtime" / "temp",
        ) as raw:
            fixture = Path(raw)
            scaffold.WORKSPACES_DIR = fixture / "workspaces"
            lane.PACKAGE_ROOT = fixture / "packages"
            receipt = lane.run_build(
                prompt,
                generate,
                request_id="verify-bounded-file-build",
                worker_context={
                    "schema": "engel_conical_build_orchestration_v1",
                    "required": True,
                    "ok": True,
                    "job_id": "verify-conical-workers",
                    "expected_worker_count": 4,
                    "returned_worker_count": 4,
                    "build_context": "Four exact candidate-only worker returns verified.",
                },
            )
            require(isinstance(receipt, dict), "large build returned no receipt")
            require(receipt.get("build_verified") is True, "bounded build did not verify")
            require(
                ((receipt.get("action") or {}).get("language")) == "python",
                "large Python web app was built in the wrong language",
            )
            generation = receipt.get("build_generation") or {}
            require(generation.get("mode") == "bounded_per_file", "whole-project generation was used")
            require(
                generation.get("whole_project_generation_used") is False,
                "receipt claimed a whole-project generation call",
            )
            require(generation.get("planned_file_count") == 3, "file plan count mismatch")
            require(generation.get("generated_file_count") == 3, "not every planned file was generated")
            require(len(calls) == 4, f"expected one plan plus three file calls, got {len(calls)}")
            require(
                all(int(call["timeout_s"]) <= 150 for call in calls),
                "a bounded generation call exceeded 150 seconds",
            )
            require(
                all(int(call["max_tokens"]) <= 4096 for call in calls),
                "a bounded generation call exceeded 4096 tokens",
            )
            lifecycle = receipt.get("build_lifecycle") or []
            require(
                any(row.get("stage") == "generate_plan" for row in lifecycle),
                "bounded plan stage missing",
            )
            require(
                sum(row.get("stage") == "generate_file" for row in lifecycle) == 3,
                "per-file lifecycle evidence is incomplete",
            )
            workspace = Path(str(((receipt.get("action") or {}).get("result") or {}).get("path") or ""))
            for relative in ("main.py", "receipt_loader.py", "tests/test_receipt_loader.py", "README.md"):
                require((workspace / relative).is_file(), f"workspace file missing: {relative}")
            package = Path(str((receipt.get("build_package") or {}).get("path") or ""))
            require(package.is_file(), "verified build package missing")
            with zipfile.ZipFile(package) as archive:
                names = set(archive.namelist())
            require("main.py" in names, "package missing entry file")
            require("tests/test_receipt_loader.py" in names, "package missing tests")
            print(
                json.dumps(
                    {
                        "ok": True,
                        "schema": "engel_bounded_file_build_generation_verifier_v1",
                        "language": "python",
                        "generation": generation,
                        "package": str(package),
                    },
                    indent=2,
                )
            )
    finally:
        scaffold.WORKSPACES_DIR = original_workspaces
        lane.PACKAGE_ROOT = original_packages
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
