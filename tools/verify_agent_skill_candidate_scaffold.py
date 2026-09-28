#!/usr/bin/env python3
from __future__ import annotations

import ast
import importlib.util
import json
import os
import py_compile
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "engel_agent_skill_candidate_scaffold.py"
SELF = Path(__file__).resolve()
STORAGE_ROOT = ROOT / "reports" / "agent_skill_candidates"
PIPELINE_VERIFIER = ROOT / "tools" / "verify_agent_skill_candidate_pipeline.py"

ALLOWED_HELPER_IMPORTS = {
    "__future__",
    "json",
    "re",
    "datetime",
    "pathlib",
    "typing",
}

FORBIDDEN_HELPER_TEXT = [
    "openai",
    "anthropic",
    "google.generativeai",
    "llama_cpp",
    "ollama",
    "torch",
    "transformers",
    "create_live_agent(",
    "enable_live_agent(",
    "start_live_agent(",
    "create_live_skill(",
    "enable_live_skill(",
    "install_live_skill(",
    "auto_register_agent(",
    "auto_register_skill(",
    "self_activate_agent(",
    "self_activate_skill(",
]

FALSE_FIELDS = [
    "runtime_enabled",
    "autorun_enabled",
    "trusted_memory_write_allowed",
    "source_mutation_allowed",
    "route_mutation_allowed",
    "queue_mutation_allowed",
    "network_allowed",
    "provider_api_allowed",
    "package_install_allowed",
    "mobile_runtime_allowed",
    "remote_queen_runtime_allowed",
]

EXECUTABLE_SUFFIXES = {
    ".py",
    ".ps1",
    ".bat",
    ".cmd",
    ".exe",
    ".dll",
    ".sh",
    ".pyd",
    ".pyc",
    ".zip",
}

EXCLUDE_DIRS = {
    ".git",
    "build",
    "dist",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
}


class CheckFailure(Exception):
    pass


def rel(path: Path) -> str:
    try:
        return str(path.resolve(strict=False).relative_to(ROOT.resolve(strict=False))).replace("/", "\\")
    except ValueError:
        return str(path)


def print_result(label: str, status: str, detail: str = "") -> None:
    suffix = f" {detail}" if detail else ""
    print(f"{status} {label}{suffix}")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def compile_sources() -> None:
    for path in [HELPER, SELF]:
        require(path.exists(), f"missing source file: {rel(path)}")
        py_compile.compile(str(path), doraise=True)
        print_result("py_compile", "PASS", rel(path))


def import_helper() -> Any:
    spec = importlib.util.spec_from_file_location("engel_agent_skill_candidate_scaffold", HELPER)
    require(spec is not None and spec.loader is not None, "could not load scaffold helper spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    print_result("helper import", "PASS", "standard-library helper imported without Engel runtime")
    return module


def check_helper_static_safety() -> None:
    source = read_text(HELPER)
    tree = ast.parse(source)
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add((node.module or "").split(".")[0])
    forbidden_imports = sorted(name for name in imports if name and name not in ALLOWED_HELPER_IMPORTS)
    require(not forbidden_imports, f"helper imports forbidden modules: {forbidden_imports}")

    lower_source = source.lower()
    hits = [needle for needle in FORBIDDEN_HELPER_TEXT if needle.lower() in lower_source]
    require(not hits, f"helper contains forbidden runtime/provider/live patterns: {hits}")

    for field in FALSE_FIELDS:
        true_pattern = re.compile(rf"['\"]?{re.escape(field)}['\"]?\s*[:=]\s*(?:True|true|\$true)\b")
        require(not true_pattern.search(source), f"helper sets {field} true")
    print_result("helper static safety", "PASS")


def check_storage_root_exists() -> None:
    require(STORAGE_ROOT.exists() and STORAGE_ROOT.is_dir(), "approved storage root missing: " + rel(STORAGE_ROOT))
    print_result("approved storage root", "PASS", rel(STORAGE_ROOT))


def validate_candidate_json(helper: Any, path: Path) -> None:
    data = json.loads(read_text(path))
    helper.validate_candidate_schema(data)
    for field in FALSE_FIELDS:
        require(data.get(field) is False, f"{rel(path)} {field} must be false")
    if data.get("candidate_type") == "skill":
        require(data.get("install_enabled") is False, f"{rel(path)} install_enabled must be false")
    if data.get("candidate_type") == "agent":
        require(data.get("collaboration_room_allowed") is False, f"{rel(path)} collaboration_room_allowed must be false")


def markdown_says_false(text: str, field: str) -> bool:
    return re.search(rf"`?{re.escape(field)}`?\s*[:=]\s*(?:`?false`?|`?no`?)", text, re.I) is not None


def validate_candidate_markdown(path: Path) -> None:
    text = read_text(path)
    lower = text.lower()
    require("candidate_only" in lower, f"{rel(path)} missing candidate_only")
    require("untrusted_candidate" in lower, f"{rel(path)} missing untrusted_candidate")
    for field in FALSE_FIELDS:
        require(markdown_says_false(text, field), f"{rel(path)} missing {field}: false")


def scan_candidate_storage(helper: Any) -> tuple[int, int]:
    json_count = 0
    md_count = 0
    for path in sorted(STORAGE_ROOT.rglob("*")):
        if path.is_dir():
            raise CheckFailure(f"candidate storage must stay flat; nested directory found: {rel(path)}")
        suffix = path.suffix.lower()
        if suffix in EXECUTABLE_SUFFIXES:
            raise CheckFailure(f"executable file in candidate storage: {rel(path)}")
        if suffix not in {".json", ".md"}:
            raise CheckFailure(f"candidate storage may contain only JSON/MD files: {rel(path)}")
        if suffix == ".json":
            validate_candidate_json(helper, path)
            json_count += 1
        else:
            validate_candidate_markdown(path)
            md_count += 1
    print_result("candidate storage scan", "PASS", f"json={json_count} md={md_count}")
    return json_count, md_count


def storage_snapshot() -> list[str]:
    if not STORAGE_ROOT.exists():
        return []
    return sorted(rel(path) for path in STORAGE_ROOT.rglob("*"))


def live_registry_paths() -> list[Path]:
    paths: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        current = Path(dirpath)
        parts = {part.lower() for part in current.relative_to(ROOT).parts} if current != ROOT else set()
        dirnames[:] = [dirname for dirname in dirnames if dirname.lower() not in EXCLUDE_DIRS]
        if parts & EXCLUDE_DIRS:
            continue
        for filename in filenames:
            lower = filename.lower()
            if "registry" in lower and ("agent" in lower or "skill" in lower or "live" in lower):
                paths.append(current / filename)
    return sorted(paths)


def file_mtime_snapshot(paths: list[Path]) -> dict[str, float]:
    snapshot: dict[str, float] = {}
    for path in paths:
        if path.exists():
            snapshot[rel(path)] = path.stat().st_mtime
    return snapshot


def run_self_test(helper: Any) -> None:
    before_storage = storage_snapshot()
    registry_paths = live_registry_paths()
    before_registry = file_mtime_snapshot(registry_paths)

    reports_root = ROOT / "reports"
    with tempfile.TemporaryDirectory(prefix="agent_skill_candidate_scaffold_selftest_", dir=str(reports_root)) as temp_name:
        temp_root = Path(temp_name)
        temp_storage = temp_root / "agent_skill_candidates"
        temp_receipts = temp_root / "codex_bridge"
        agent = helper.build_agent_candidate(
            candidate_id="selftest_agent_candidate",
            name="Selftest Agent Candidate",
            purpose="Verifier-only temporary agent scaffold test",
            description="Temporary self-test candidate; deleted automatically.",
            allowed_inputs=["local explicit test input"],
            allowed_outputs=["temporary report-only scaffold"],
        )
        skill = helper.build_skill_candidate(
            candidate_id="selftest_skill_candidate",
            skill_name="selftest_skill_candidate",
            description="Verifier-only temporary skill scaffold test",
            trigger_conditions=["explicit verifier self-test only"],
            input_schema={"type": "object", "properties": {}},
            output_schema={"type": "object", "properties": {}},
        )
        for candidate in [agent, skill]:
            result = helper.write_candidate_scaffold(
                candidate,
                storage_root=temp_storage,
                receipt_root=temp_receipts,
                approved_storage_roots=(temp_storage,),
                verifier_result="self_test_pass",
            )
            json_path = result["json_path"]
            md_path = result["markdown_path"]
            receipt_path = result["receipt_path"]
            require(json_path.exists() and md_path.exists() and receipt_path.exists(), "self-test output missing")
            validate_candidate_json(helper, json_path)
            validate_candidate_markdown(md_path)
            receipt = read_text(receipt_path).lower()
            for phrase in [
                "candidate_only",
                "untrusted_candidate",
                "schema_validation_result",
                "self_test_pass",
                "not live",
                "not installed",
                "not active",
                "not runnable",
                "no trusted-memory write",
                "runtime enablement",
                "autorun enablement",
            ]:
                require(phrase in receipt, f"receipt missing phrase: {phrase}")

    after_storage = storage_snapshot()
    after_registry = file_mtime_snapshot(registry_paths)
    require(after_storage == before_storage, "self-test modified actual candidate storage")
    require(after_registry == before_registry, "self-test modified live registry-like files")
    print_result("temp-dir self-test", "PASS", "agent and skill scaffold outputs deleted automatically")
    print_result("actual candidate storage unchanged by self-test", "PASS")
    print_result("live registry modification check", "PASS", str(len(registry_paths)))


def run_pipeline_verifier() -> None:
    result = subprocess.run(
        [sys.executable, str(PIPELINE_VERIFIER)],
        cwd=str(ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    require(result.returncode == 0, "candidate pipeline verifier failed:\n" + result.stdout)
    require("AGENT_SKILL_CANDIDATE_PIPELINE_VERIFICATION_PASS" in result.stdout, "candidate pipeline pass marker missing")
    print_result("candidate pipeline verifier", "PASS")


def main() -> int:
    failures: list[str] = []
    print("ENGEL_AGENT_SKILL_CANDIDATE_SCAFFOLD_VERIFIER")
    print(f"ROOT {ROOT}")
    print("Mode: local static/self-test verification only; no live agent/skill/runtime/provider/model launch")
    try:
        compile_sources()
        helper = import_helper()
        check_helper_static_safety()
        check_storage_root_exists()
        scan_candidate_storage(helper)
        run_self_test(helper)
        run_pipeline_verifier()
    except (CheckFailure, py_compile.PyCompileError, SyntaxError, json.JSONDecodeError, OSError) as exc:
        failures.append(str(exc))

    if failures:
        print_result("agent/skill candidate scaffold checks", "FAIL", f"failures={len(failures)}")
        for failure in failures:
            print_result("agent/skill candidate scaffold check", "FAIL", failure)
        print("AGENT_SKILL_CANDIDATE_SCAFFOLD_VERIFICATION_FAIL")
        return 1

    print_result("helper compile checks", "PASS")
    print_result("helper static safety checks", "PASS")
    print_result("candidate storage checks", "PASS")
    print_result("temp scaffold self-test", "PASS")
    print_result("actual storage persistence check", "PASS")
    print_result("pipeline verifier compatibility", "PASS")
    print("AGENT_SKILL_CANDIDATE_SCAFFOLD_VERIFICATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
