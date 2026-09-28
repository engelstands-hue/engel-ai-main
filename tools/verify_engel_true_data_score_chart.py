from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "tools" / "engel_true_data_score_chart.py"
VERIFIER = ROOT / "tools" / "verify_engel_true_data_score_chart.py"
CHART = ROOT / "reports" / "charts" / "engel_true_data_score_chart.png"
DATA_JSON = ROOT / "reports" / "charts" / "engel_true_data_score_chart_data.json"
RECEIPT = ROOT / "reports" / "charts" / "engel_true_data_score_chart_receipt.md"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_TRUE_DATA_SCORE_CHART.md"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
UTC_RE = re.compile(r"^20\d{2}-\d{2}-\d{2}T[0-2]\d:[0-5]\d:[0-5]\dZ$")

REQUIRED_CONSTANTS = {
    "MAX_FILES_INSPECTED": 500,
    "MAX_BYTES_PER_FILE": 2 * 1024 * 1024,
    "MIN_RECORDS_FOR_FULL_CHART": 20,
}

FORBIDDEN_IMPORTS = {
    "random",
    "secrets",
    "requests",
    "urllib",
    "socket",
    "webbrowser",
    "subprocess",
    "threading",
    "multiprocessing",
    "openai",
}

FORBIDDEN_CALL_NAMES = {
    "eval",
    "exec",
    "__import__",
    "system",
    "popen",
    "Popen",
    "check_call",
    "check_output",
    "startfile",
}

FORBIDDEN_SOURCE_SNIPPETS = [
    "random.",
    "seed(",
    "synthetic_data",
    "mock_data",
    "demo_data",
    "fake_data",
    "pip install",
    "uv pip",
    "winget",
    "choco install",
    "Invoke-WebRequest",
    "Start-BitsTransfer",
    "adb ",
    "wsl ",
    "ollama",
    "llama.cpp",
]

REQUIRED_SOURCE_SNIPPETS = [
    "MAX_FILES_INSPECTED = 500",
    "MAX_BYTES_PER_FILE = 2 * 1024 * 1024",
    "ALLOWED_TOP_LEVEL_DIRS = (\"reports\", \"memory\")",
    "SKIP_DIR_NAMES",
    "reports\") / \"charts\"",
    "reports\") / \"codex_bridge\"",
    "insufficient",
    "Fewer than 20 true numeric records",
    "file contents treated as untrusted data",
    "standard_library_png_renderer",
    "chronological_local_record_position",
    "engel_true_data_score_chart_receipt.md",
    "build_hash_sha256",
    "chart_hash_sha256",
    "data_hash_sha256",
    "generator_hash_sha256",
    "report-only artifact; not approval, not promotion, not trusted memory",
]


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def project_relative(path: Path) -> str:
    return str(path.resolve(strict=False).relative_to(ROOT.resolve(strict=False))).replace("/", "\\")


def load_module():
    spec = importlib.util.spec_from_file_location("engel_true_data_score_chart", MODULE)
    require(spec is not None and spec.loader is not None, "could not load chart module")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_true_data_score_chart"] = module
    spec.loader.exec_module(module)
    return module


def check_files() -> None:
    for path in [MODULE, VERIFIER]:
        require(path.exists() and path.is_file(), "missing required file: " + project_relative(path))


def check_static_source() -> None:
    source = read(MODULE)
    tree = ast.parse(source)
    for name in REQUIRED_CONSTANTS:
        require(name in source, f"missing bounded constant: {name}")
    for snippet in REQUIRED_SOURCE_SNIPPETS:
        require(snippet in source, "chart module missing required source snippet: " + snippet)
    for forbidden in FORBIDDEN_SOURCE_SNIPPETS:
        require(forbidden.lower() not in source.lower(), "chart module contains forbidden snippet: " + forbidden)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_name = alias.name.split(".")[0]
                require(root_name not in FORBIDDEN_IMPORTS, "chart module imports forbidden package: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            root_name = node.module.split(".")[0]
            require(root_name not in FORBIDDEN_IMPORTS, "chart module imports forbidden package: " + node.module)
        elif isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
            require(name not in FORBIDDEN_CALL_NAMES, "chart module contains forbidden call: " + name)


def check_runtime_import_and_bounds() -> None:
    module = load_module()
    for name, expected in REQUIRED_CONSTANTS.items():
        require(getattr(module, name) == expected, "runtime constant mismatch: " + name)
    files = module.discover_candidate_files(ROOT)
    require(len(files) <= module.MAX_FILES_INSPECTED, "discovery exceeded max files")
    allowed_roots = [ROOT / "reports", ROOT / "memory"]
    for path in files:
        require(any(module.is_within(path, root) for root in allowed_roots), "discovered file outside allowed roots: " + project_relative(path))
        require(path.suffix.lower() in module.ALLOWED_EXTENSIONS, "discovered file has unsupported extension: " + project_relative(path))
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        require(size <= module.MAX_BYTES_PER_FILE, "discovered file exceeds byte limit: " + project_relative(path))

    records, inspected = module.collect_true_records(ROOT)
    require(inspected <= module.MAX_FILES_INSPECTED, "runtime inspected too many files")
    if records:
        first = records[0]
        require(first.source_path, "record missing source path")
        require(first.source_kind, "record missing source kind")
        require(isinstance(first.score_value, float), "record score value is not float")
        require("synthetic" not in first.extraction_kind.lower(), "record extraction kind must not be synthetic")


def check_outputs() -> None:
    for path in [CHART, DATA_JSON, RECEIPT, REPORT]:
        require(path.exists() and path.is_file(), "missing generated output: " + project_relative(path))
    require(CHART.parent == ROOT / "reports" / "charts", "chart output folder mismatch")
    require(DATA_JSON.parent == ROOT / "reports" / "charts", "data output folder mismatch")
    require(RECEIPT.parent == ROOT / "reports" / "charts", "receipt output folder mismatch")
    require(REPORT.parent == ROOT / "reports" / "codex_bridge", "report output folder mismatch")
    require(CHART.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"), "chart is not a PNG")
    data = json.loads(read(DATA_JSON))
    for field in [
        "artifact",
        "generator",
        "timestamp_utc",
        "source_file_count",
        "true_numeric_record_count",
        "arc_length_mode",
        "chart_hash_sha256",
        "data_hash_sha256",
        "generator_hash_sha256",
        "receipt_hash_sha256",
        "status",
    ]:
        require(field in data, "data JSON missing receipt metadata field: " + field)
    require(data["artifact"] == "engel_true_data_score_chart.png", "data JSON artifact mismatch")
    require(data["generator"] == "tools/engel_true_data_score_chart.py", "data JSON generator mismatch")
    require(data["status"] == "generated from true-data-only run", "data JSON status mismatch")
    require(data["arc_length_mode"] == "chronological_local_record_position", "data JSON arc length mismatch")
    require(isinstance(data["source_file_count"], int), "data JSON source_file_count must be int")
    require(isinstance(data["true_numeric_record_count"], int), "data JSON true_numeric_record_count must be int")
    require(SHA256_RE.fullmatch(data["chart_hash_sha256"]) is not None, "chart hash is not SHA-256-looking")
    require(SHA256_RE.fullmatch(data["data_hash_sha256"]) is not None, "data hash is not SHA-256-looking")
    require(SHA256_RE.fullmatch(data["generator_hash_sha256"]) is not None, "generator hash is not SHA-256-looking")
    if data["receipt_hash_sha256"] is not None:
        require(SHA256_RE.fullmatch(data["receipt_hash_sha256"]) is not None, "receipt hash is not SHA-256-looking")
    require(UTC_RE.fullmatch(data["timestamp_utc"]) is not None, "timestamp is not UTC-style")
    require(data["chart_hash_sha256"] == sha256_file(CHART), "data JSON chart hash does not match chart")
    require(data["generator_hash_sha256"] == sha256_file(MODULE), "data JSON generator hash does not match module")
    summary = data.get("summary", {})
    require(isinstance(summary, dict), "data JSON missing summary")
    require(summary.get("files_inspected", 999999) <= 500, "data JSON files_inspected exceeds bound")
    require("true_numeric_records_found" in summary, "data JSON missing true numeric record count")
    if summary.get("insufficient_data") is True:
        require(not data.get("series"), "insufficient data output must not include fake series")
    else:
        series = data.get("series", {})
        require(isinstance(series, dict), "full chart output missing series")
        for key in ["x", "observed", "percentile", "expected"]:
            require(key in series and isinstance(series[key], list), "series missing: " + key)
    report = read(REPORT)
    for phrase in [
        "Generated a local/offline chart",
        "true numeric records found",
        "Arc Length",
        "Insufficient Data Behavior",
        "no package install",
        "no provider/network/browser/API calls",
        "no trusted-memory write",
        "no queue/source/route mutation",
        "Receipt Metadata",
        "receipt hash",
    ]:
        require(phrase in report, "report missing phrase: " + phrase)
    receipt = read(RECEIPT)
    for phrase in [
        "artifact:",
        "engel_true_data_score_chart.png",
        "source_data:",
        "reports/charts/engel_true_data_score_chart_data.json",
        "generator:",
        "tools/engel_true_data_score_chart.py",
        "build_hash:",
        "chart_hash:",
        "data_hash:",
        "timestamp_utc:",
        "metric:",
        "normalized observed sum score vs expected sum score over normalized arc length",
        "status:",
        "generated from true-data-only run",
        "truth_boundary:",
        "no fake, random, mock, seeded, synthetic, or demo data",
        "not approval, not promotion, not trusted memory",
    ]:
        require(phrase in receipt, "receipt missing phrase: " + phrase)
    for label in ["build_hash", "chart_hash", "data_hash", "generator_hash"]:
        match = re.search(rf"(?m)^{label}:\s*\n([0-9a-f]{{64}})\s*$", receipt)
        require(match is not None, "receipt missing SHA-256-looking " + label)
    timestamp_match = re.search(r"(?m)^timestamp_utc:\s*\n(.+)\s*$", receipt)
    require(timestamp_match is not None, "receipt missing timestamp value")
    require(UTC_RE.fullmatch(timestamp_match.group(1).strip()) is not None, "receipt timestamp is not UTC-style")
    chart_hash_match = re.search(r"(?m)^chart_hash:\s*\n([0-9a-f]{64})\s*$", receipt)
    data_hash_match = re.search(r"(?m)^data_hash:\s*\n([0-9a-f]{64})\s*$", receipt)
    generator_hash_match = re.search(r"(?m)^generator_hash:\s*\n([0-9a-f]{64})\s*$", receipt)
    require(chart_hash_match is not None and chart_hash_match.group(1) == sha256_file(CHART), "receipt chart hash mismatch")
    require(data_hash_match is not None and data_hash_match.group(1) == sha256_file(DATA_JSON), "receipt data hash mismatch")
    require(generator_hash_match is not None and generator_hash_match.group(1) == sha256_file(MODULE), "receipt generator hash mismatch")


def main() -> int:
    checks = [
        ("files", check_files),
        ("static_source", check_static_source),
        ("runtime_import_and_bounds", check_runtime_import_and_bounds),
        ("outputs", check_outputs),
    ]
    failures: list[str] = []
    for name, check in checks:
        try:
            check()
            print("PASS " + name)
        except CheckFailure as exc:
            failures.append(f"{name}: {exc}")
            print("FAIL " + name + ": " + str(exc))
        except Exception as exc:
            failures.append(f"{name}: unexpected error: {exc}")
            print("FAIL " + name + ": unexpected error: " + str(exc))
    if failures:
        print("\nEngel true data score chart verifier FAILED")
        for failure in failures:
            print("- " + failure)
        return 1
    print("\nEngel true data score chart verifier PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
