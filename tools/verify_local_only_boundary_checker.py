from __future__ import annotations

import ast
import json
import re
from pathlib import Path


_file = globals().get("__file__")
if not _file or not isinstance(_file, str) or _file.startswith("<"):
    ROOT = Path.cwd()
else:
    try:
        ROOT = Path(_file).resolve().parents[1]
    except (OSError, ValueError, IndexError):
        ROOT = Path.cwd()
CHECKER = ROOT / "tools" / "check_local_only_boundary.py"
REPORT = ROOT / "reports" / "security" / "local_only" / "EE_LOCAL_ONLY_BOUNDARY_CHECK.md"
APP_REPORT = ROOT / "reports" / "app" / "V2APP_EE_LOCAL_ONLY_BOUNDARY_CHECKER.md"
CHECKPOINT = ROOT / "memory" / "V2APP_EE_LOCAL_ONLY_BOUNDARY_CHECKER.json"
CONTRACT = ROOT / "memory" / "LOCAL_ONLY_BOUNDARY_REGRESSION_CONTRACT_V1.md"


class CheckFailure(Exception):
    pass


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().replace("/", "\\"))


def read(path: Path) -> str:
    if not path.exists():
        raise CheckFailure(f"missing required file: {path}")
    return path.read_text(encoding="utf-8")


def require(text: str, needles: list[str], label: str) -> None:
    haystack = normalize(text)
    missing = [needle for needle in needles if normalize(needle) not in haystack]
    if missing:
        raise CheckFailure(label + " missing: " + ", ".join(missing))


def verify_source(source: str) -> None:
    tree = ast.parse(source)
    forbidden_imports = {"requests", "urllib", "httpx", "socket", "subprocess", "threading", "multiprocessing", "asyncio", "sched", "webbrowser", "smtplib"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in forbidden_imports:
                    raise CheckFailure(f"checker imports forbidden module: {alias.name}")
        if isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] in forbidden_imports:
                raise CheckFailure(f"checker imports forbidden module: {node.module}")
    if "while True" in source or "exec(" in source or "eval(" in source:
        raise CheckFailure("checker contains forbidden execution/loop pattern")
    if 'REPORT.write_text(build_report(), encoding="utf-8")' not in source:
        raise CheckFailure("checker must write only the expected report via build_report")


def pass_check(name: str) -> None:
    print(f"PASS {name}")


def main() -> int:
    try:
        source = read(CHECKER)
        report = read(REPORT)
        app_report = read(APP_REPORT)
        contract = read(CONTRACT)
        with CHECKPOINT.open("r", encoding="utf-8") as f:
            checkpoint = json.load(f)
        pass_check("read_required_files")

        verify_source(source)
        pass_check("checker_source_safety")

        require(
            report,
            [
                "EE Local-only Boundary Check",
                "READ_ONLY_CHECK / NO_REMEDIATION",
                "Pass/Needs-review/Risk Matrix",
                "Matched Files/Lines",
                "No-remediation Statement",
                "EF Local-only Boundary Results Review",
            ],
            "EE report",
        )
        require(
            app_report,
            [
                "V2APP-EE Local-only Boundary Checker",
                "read-only local-only boundary checker",
                "EF Local-only Boundary Results Review",
            ],
            "EE app report",
        )
        require(contract, ["EE Implement Read-only Local-only Boundary Checker"], "ED contract")
        if checkpoint.get("checkpoint_id") != "V2APP-EE":
            raise CheckFailure("checkpoint_id must be V2APP-EE")
        if checkpoint.get("remediation_performed") is not False:
            raise CheckFailure("remediation_performed must be false")
        if checkpoint.get("checker_output") != "reports\\security\\local_only\\EE_LOCAL_ONLY_BOUNDARY_CHECK.md":
            raise CheckFailure("unexpected checker output")
        pass_check("checkpoint_schema")

        print("\nLOCAL_ONLY_BOUNDARY_CHECKER_VERIFICATION_PASS")
        return 0
    except Exception as exc:
        print("LOCAL_ONLY_BOUNDARY_CHECKER_VERIFICATION_FAIL")
        print(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
