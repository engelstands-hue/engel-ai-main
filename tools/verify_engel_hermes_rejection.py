from __future__ import annotations

import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_HERMES_REMOVAL_AND_REJECTION_ENFORCEMENT_V1.md"
OUTSIDE_AI_JSON = ROOT / "memory" / "ENGEL_OUTSIDE_AI_BOUNDARY_RULE_V1.json"
MODEL_PLAN_JSON = ROOT / "memory" / "ENGEL_MODEL_LIBRARY_PLAN_V1.json"
NON_MODEL_PLAN_JSON = ROOT / "memory" / "ENGEL_NON_MODEL_LIBRARY_PLAN_V1.json"
LLM_INTAKE_JSON = ROOT / "memory" / "ENGEL_LLM_AND_PYTHON_LIBRARY_INTAKE_PLAN_V1.json"
WSL_JSON = ROOT / "memory" / "ENGEL_WSL_UBUNTU_RUNTIME_DEPENDENCY_V1.json"

HERMES_PATTERN = re.compile(
    r"Hermes|Nous\s*Hermes|NousResearch\s*Hermes|Hermes\s*3|Hermes-style|function-calling\s+Hermes",
    re.IGNORECASE,
)

EXCLUDED_DIRS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    "live",
    "staging",
    "node_modules",
    "backups",
}

EXCLUDED_FILES = {
    "tools\\verify_engel_hermes_rejection.py",
    "reports\\codex_bridge\\ENGEL_HERMES_REMOVAL_AND_REJECTION_ENFORCEMENT_V1.md",
}

EXTERNAL_REFERENCE_ROOTS = {
    "external\\",
    "sandbox\\eng3d\\",
    "sandbox\\ephify\\",
}

TEXT_SUFFIXES = {
    ".py",
    ".ps1",
    ".json",
    ".md",
    ".txt",
    ".toml",
    ".cfg",
    ".ini",
    ".yml",
    ".yaml",
    ".html",
    ".css",
    ".js",
    ".bat",
    ".cmd",
    ".spec",
}

DEPENDENCY_FILES = {
    "requirements.txt",
    "requirements-dev.txt",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "pipfile",
    "poetry.lock",
    "package.json",
    "package-lock.json",
    "engeldebug.spec",
}

SAFE_CONTEXT_TERMS = [
    "rejected",
    "do not install",
    "blocked",
    "forbidden",
    "not approved",
    "outside-ai boundary",
    "boundary risk",
    "quarantine",
    "no_hermes_execution",
    "no hermes execution",
    "no hermes run",
    "did not run hermes",
    "no hermes command",
    "hermes execution",
    "wsl execution, hermes execution",
    "hermes_command",
    "blocked_entry_fields",
    "no_hermes",
    "must not be used to install",
    "not an approved hermes",
    "not a hermes",
    "remains rejected",
    "run hermes automatically",
    "warning_patterns",
    "warning flags",
    "status_labels",
    "safety_boundary",
    "false",
    "no_",
    "does not",
    "without starting",
    "without running",
    "not run",
    "not start",
    "not load",
    "not install",
    "no wsl/hermes",
    "wsl/hermes",
    "wsl, hermes",
    "wsl_hermes",
    "wsl_android_hermes",
    "risk_patterns",
    "hermes_policy",
    "outside_ai_boundary_rule_hermes_policy",
    "no model loading, inference, training",
]

UNSAFE_PHRASES = [
    "Hermes Runtime Notes if installed later",
    "future Hermes runtime environment if installed",
    "future Hermes runtime use if installed",
    "Hermes-related environment work later",
    "WSL/Hermes may support future tooling",
    "approved Hermes",
    "Hermes approved",
    "pending Hermes",
    "Hermes pending",
    "recommended Hermes",
    "approved research worker",
    "approved function-calling runtime",
    "approved agent runtime",
    "Hermes integration candidate",
    "Hermes startup/load option",
    "Hermes fallback model",
]

INSTALL_OR_RUNTIME_PATTERNS = [
    re.compile(r"\b(pip|uv|conda|npm|winget|choco)\s+install\b.*\bHermes\b", re.IGNORECASE),
    re.compile(r"\bdownload\b.*\bHermes\b", re.IGNORECASE),
    re.compile(r"\bload\b.*\bHermes\b", re.IGNORECASE),
    re.compile(r"\brun\b.*\bHermes\b", re.IGNORECASE),
    re.compile(r"\bstart\b.*\bHermes\b", re.IGNORECASE),
]


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def project_relative(path: Path) -> str:
    return str(path.resolve(strict=False).relative_to(ROOT.resolve(strict=False))).replace("/", "\\")


def iter_project_files(root: Path = ROOT):
    stack = [root]
    while stack:
        folder = stack.pop()
        try:
            children = sorted(folder.iterdir(), key=lambda item: item.name.lower())
        except OSError:
            continue
        for child in children:
            if child.is_dir():
                if child.name.lower() in EXCLUDED_DIRS:
                    continue
                stack.append(child)
            elif child.is_file() and child.suffix.lower() in TEXT_SUFFIXES:
                if project_relative(child) in EXCLUDED_FILES:
                    continue
                yield child


def read_lines(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []


def is_historical_path(path: Path) -> bool:
    rel = project_relative(path).lower()
    return (
        rel.startswith("reports\\codex_bridge\\")
        or rel.startswith("reports\\candidate_set_approvals\\")
        or rel.startswith("engel_library\\approved_library\\")
        or (rel.startswith("remote_workers\\android_worker_") and "\\inbox\\assigned_inputs\\" in rel)
    )


def is_external_reference_path(path: Path) -> bool:
    rel = project_relative(path).lower()
    return any(rel.startswith(root) for root in EXTERNAL_REFERENCE_ROOTS)


def dependency_surface_files() -> list[Path]:
    return [
        path
        for path in iter_project_files()
        if not is_external_reference_path(path)
        and (path.name.lower() in DEPENDENCY_FILES or path.suffix.lower() in {".spec", ".ps1", ".bat", ".cmd"})
    ]


def classify_reference(path: Path, line_number: int, line: str, lines: list[str]) -> str:
    lowered = line.lower()
    context = "\n".join(lines[max(0, line_number - 3):line_number + 2]).lower()
    rel = project_relative(path).lower()
    if is_external_reference_path(path):
        return "external_reference_import_not_engel_runtime"
    if rel.startswith("tools\\verify_"):
        return "safe_rejection_reference"
    if any(phrase.lower() in context for phrase in UNSAFE_PHRASES):
        if is_historical_path(path):
            return "historical_report_reference"
        return "unsafe_pending_reference"
    if any(term in context for term in SAFE_CONTEXT_TERMS):
        return "safe_rejection_reference"
    if any(pattern.search(line) for pattern in INSTALL_OR_RUNTIME_PATTERNS):
        if any(term in context for term in ["no ", "not ", "did not", "blocked", "rejected", "forbidden", "must not"]):
            return "safe_rejection_reference"
        if is_historical_path(path):
            return "historical_report_reference"
        return "unsafe_runtime_reference"
    if is_historical_path(path):
        return "historical_report_reference"
    if "warning" in lowered or "flag" in lowered or "reference" in lowered:
        return "safe_rejection_reference"
    return "unknown_needs_review"


def collect_references() -> list[dict[str, object]]:
    references: list[dict[str, object]] = []
    for path in iter_project_files():
        lines = read_lines(path)
        for index, line in enumerate(lines, start=1):
            if not HERMES_PATTERN.search(line):
                continue
            category = classify_reference(path, index, line, lines)
            references.append({
                "path": project_relative(path),
                "line": index,
                "category": category,
                "text": line.strip()[:240],
            })
    return references


def check_core_contracts() -> None:
    outside = json.loads(OUTSIDE_AI_JSON.read_text(encoding="utf-8"))
    hermes = outside.get("hermes_policy", {})
    require(hermes.get("status") == "REJECTED / DO NOT INSTALL ON THIS COMPUTER", "Outside-AI boundary must reject Hermes")
    for blocked in [
        "installation",
        "runtime_loading",
        "tool_execution",
        "Engel_integration",
        "Remote_Queen_integration",
        "memory_integration",
        "route_integration",
        "provider_network_integration",
        "startup_integration",
    ]:
        require(blocked in hermes.get("blocked_use", []), "Hermes blocked use missing: " + blocked)
    model = json.loads(MODEL_PLAN_JSON.read_text(encoding="utf-8"))
    non_model = json.loads(NON_MODEL_PLAN_JSON.read_text(encoding="utf-8"))
    llm = json.loads(LLM_INTAKE_JSON.read_text(encoding="utf-8"))
    wsl = json.loads(WSL_JSON.read_text(encoding="utf-8"))
    require(model.get("outside_ai_boundary", {}).get("hermes_policy") == "REJECTED / DO NOT INSTALL ON THIS COMPUTER", "Model library Hermes policy missing rejection")
    require(non_model.get("outside_ai_boundary", {}).get("hermes_policy") == "REJECTED / DO NOT INSTALL ON THIS COMPUTER", "Non-model library Hermes policy missing rejection")
    full_llm = json.dumps(llm, sort_keys=True)
    for required in [
        "Hermes Rejection / Do Not Install Boundary Notes",
        "must_not_be_used_for_hermes_runtime_work",
        "REJECTED / DO NOT INSTALL ON THIS COMPUTER",
    ]:
        require(required in full_llm, "LLM/Python intake missing Hermes rejection boundary: " + required)
    full_wsl = json.dumps(wsl, sort_keys=True)
    require("future Hermes runtime environment if installed" not in full_wsl, "WSL contract still lists future Hermes runtime as safe")
    require("REJECTED / DO NOT INSTALL ON THIS COMPUTER" in full_wsl, "WSL contract missing Hermes rejection boundary")


def check_no_dependency_or_source_folder() -> None:
    hermes_named_paths: list[str] = []
    for path in iter_project_files():
        rel = project_relative(path)
        if "hermes" in rel.lower() and project_relative(path) not in {
            "tools\\verify_engel_hermes_rejection.py",
            "reports\\codex_bridge\\ENGEL_HERMES_REMOVAL_AND_REJECTION_ENFORCEMENT_V1.md",
        }:
            if is_external_reference_path(path):
                continue
            hermes_named_paths.append(rel)
    require(not hermes_named_paths, "Hermes-named source/dependency/report paths remain: " + ", ".join(hermes_named_paths[:10]))
    for path in dependency_surface_files():
        text = "\n".join(read_lines(path))
        if HERMES_PATTERN.search(text):
            if path.name.lower() == "codex_verify.ps1" and "verify_engel_hermes_rejection.py" in text:
                continue
            safe = all(
                term in text.lower()
                for term in ["rejected", "do not install"]
            )
            require(safe, "Hermes appears in dependency/script surface without rejection boundary: " + project_relative(path))


def check_reference_categories() -> dict[str, int]:
    references = collect_references()
    counts: dict[str, int] = {}
    unsafe: list[dict[str, object]] = []
    for item in references:
        category = str(item["category"])
        counts[category] = counts.get(category, 0) + 1
        if category.startswith("unsafe") or category == "unknown_needs_review":
            unsafe.append(item)
    require(not unsafe, "unsafe/unknown Hermes references remain: " + "; ".join(f"{item['path']}:{item['line']} {item['category']}" for item in unsafe[:12]))
    require(counts, "Hermes rejection verifier expected at least boundary references")
    return counts


def check_report() -> None:
    require(REPORT.exists(), "Hermes enforcement report missing")
    text = REPORT.read_text(encoding="utf-8", errors="replace")
    for required in [
        "Engel Hermes Removal and Rejection Enforcement V1",
        "Hermes remains rejected / do not install",
        "No Hermes install/runtime/dependency exists",
        "Packaging skipped",
    ]:
        require(required in text, "report missing required text: " + required)


def main() -> int:
    try:
        check_core_contracts()
        check_no_dependency_or_source_folder()
        counts = check_reference_categories()
        if REPORT.exists():
            check_report()
    except CheckFailure as exc:
        print("[FAIL] Engel Hermes rejection verifier failed.")
        print("- " + str(exc))
        return 1
    print("[PASS] Engel Hermes rejection verifier passed.")
    print("Reference categories:")
    for category, count in sorted(counts.items()):
        print(f"- {category}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
