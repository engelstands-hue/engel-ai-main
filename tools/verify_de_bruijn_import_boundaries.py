from __future__ import annotations

import ast
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "memory" / "ENGEL_DE_BRUIJN_IMPORT_BOUNDARY_CONTRACT_V1.json"

SKIP_DIRS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "build",
    "dist",
    "live",
    "backups",
}

TRUSTED_MEMORY_WRITER_MODULES = {
    "engel_training_trusted_memory",
    "engel_trusted_memory_target",
}

MEMORY_PROMOTION_REVIEW_MODULES = {
    "engel_approved_memory_promotion",
    "engel_memory_promotion_writer",
}

SOURCE_MUTATION_MODULES = {
    "engel_code_companion_patch_apply",
    "engel_code_companion_protected_patch_apply",
    "engel_code_companion_low_risk_patch_runner",
    "engel_low_risk_self_fix_runner",
}

ROUTE_MUTATION_MODULES = {
    "engel_ai_update_routes",
}

FORBIDDEN_LOADER_TEXT = {
    "register_trusted_memory(",
    "TRUSTED_MEMORY =",
    "TRUSTED_MEMORY=",
}


class CheckFailure(Exception):
    pass


def project_relative(path: Path) -> str:
    return str(path.resolve(strict=False).relative_to(ROOT.resolve(strict=False))).replace("/", "\\")


def load_contract() -> dict[str, Any]:
    if not CONTRACT.exists():
        raise CheckFailure("missing contract: " + project_relative(CONTRACT))
    data = json.loads(CONTRACT.read_text(encoding="utf-8"))
    if data.get("contract_id") != "ENGEL_DE_BRUIJN_IMPORT_BOUNDARY_CONTRACT_V1":
        raise CheckFailure("unexpected contract_id")
    return data


def should_skip(path: Path) -> bool:
    rel_parts = path.relative_to(ROOT).parts
    return any(part in SKIP_DIRS for part in rel_parts)


def python_files() -> list[Path]:
    return sorted(path for path in ROOT.rglob("*.py") if not should_skip(path))


def module_from_import(name: str) -> str:
    return str(name or "").split(".")[0]


def local_module_names(files: list[Path]) -> set[str]:
    names: set[str] = set()
    for path in files:
        if path.name == "__init__.py":
            continue
        names.add(path.stem)
    return names


def classify_name(name: str) -> str:
    lower = name.lower()
    if lower in {"engel_app", "start_engel"} or lower.startswith("engel_core_"):
        return "core"
    if lower in TRUSTED_MEMORY_WRITER_MODULES:
        return "trusted_memory"
    if lower in MEMORY_PROMOTION_REVIEW_MODULES:
        return "memory"
    if lower in {"engel_hive_data_services"}:
        return "hive_data"
    if lower in {"engel_research_office_data"}:
        return "research_office_data"
    if lower in {"engel_research_office"}:
        return "research_office"
    if lower in {"engel_companion"}:
        return "companion"
    if lower.startswith("engel_code_companion"):
        return "code_companion"
    if lower in {"engel_route_explorer"} or lower in ROUTE_MUTATION_MODULES or "route" in lower:
        return "routes"
    if lower.startswith("engel_remote_worker") or "remote_queen" in lower:
        return "remote_queen"
    if lower.startswith("engel_mobile") or "android" in lower:
        return "mobile"
    if "local_llm" in lower or "llama" in lower or "model_runtime" in lower or "model_review" in lower:
        return "local_llm"
    if "prompt_injection" in lower or "protected_action" in lower or "global_password_gate" in lower or "untrusted" in lower:
        return "safety_guardian"
    if "candidate" in lower or "lesson" in lower or "memory_candidate" in lower:
        return "candidate_memory"
    if lower.startswith("engel_ai") or "research_brain" in lower:
        return "brain"
    if "build" in lower or "packag" in lower:
        return "build_packaging"
    if "memory" in lower:
        return "memory"
    return "tools"


def classify_path(path: Path) -> str:
    rel = path.relative_to(ROOT)
    rel_text = str(rel).replace("/", "\\").lower()
    name = path.stem.lower()
    parts = [part.lower() for part in rel.parts]

    if parts and parts[0] == "reports":
        return "reports"
    if parts and parts[0] == "memory":
        return "memory"
    if "quarantine" in parts or "quarantine" in name:
        return "quarantine"
    if parts and parts[0] in {"test", "tests"}:
        return "tests"
    if name.startswith("test_") or name.endswith("_test"):
        return "tests"
    if parts and parts[0] == "tools":
        if name.startswith("verify_"):
            return "verifiers"
        if name == "engel_super_swarm_hive_3d_scaffold":
            return "super_swarm"
        return "tools"
    if "local_llm_training" in rel_text:
        return "local_llm"
    if parts and parts[0] == "mobile":
        return "mobile"
    if parts and parts[0] == "remote_workers":
        return "remote_queen"
    if parts and parts[0] in {"external", "sandbox"}:
        return "knowledge"
    return classify_name(path.stem)


def read_source(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def imports_from_source(source: str) -> list[tuple[str, int]]:
    tree = ast.parse(source)
    imports: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((module_from_import(alias.name), int(getattr(node, "lineno", 0))))
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append((module_from_import(node.module), int(getattr(node, "lineno", 0))))
    return imports


def is_de_bruijn_loader_candidate(path: Path) -> bool:
    lower = str(path.relative_to(ROOT)).replace("\\", "/").lower()
    return "de_bruijn" in lower and "loader" in lower


def add_finding(bucket: list[dict[str, Any]], path: Path, line: int, source_node: str, dest_node: str, module: str, reason: str) -> None:
    bucket.append(
        {
            "file": project_relative(path),
            "line": line,
            "source_node": source_node,
            "destination_node": dest_node,
            "module": module,
            "reason": reason,
        }
    )


def analyze_file(path: Path, local_modules: set[str], findings: dict[str, list[dict[str, Any]]]) -> None:
    source_node = classify_path(path)
    try:
        source = read_source(path)
        imports = imports_from_source(source)
    except SyntaxError as exc:
        add_finding(findings["review_required"], path, int(getattr(exc, "lineno", 0) or 0), source_node, "unknown", "", "Python syntax parse failed; import boundary unknown")
        return
    except Exception as exc:
        add_finding(findings["review_required"], path, 0, source_node, "unknown", "", "Could not read/parse file: " + type(exc).__name__)
        return

    if is_de_bruijn_loader_candidate(path):
        for needle in FORBIDDEN_LOADER_TEXT:
            if needle in source:
                add_finding(
                    findings["forbidden"],
                    path,
                    0,
                    "de_bruijn_loader",
                    "trusted_memory",
                    needle,
                    "De Bruijn loader candidate contains forbidden trusted-memory auto-registration pattern",
                )

    for module, line in imports:
        if module not in local_modules:
            continue
        dest_node = classify_name(module)

        if source_node in {"candidate_memory", "quarantine", "mobile", "remote_queen"} and dest_node == "trusted_memory":
            add_finding(findings["forbidden"], path, line, source_node, dest_node, module, source_node + " must not import trusted-memory writer modules")
            continue
        if source_node in {"local_llm"} and module in TRUSTED_MEMORY_WRITER_MODULES:
            add_finding(findings["forbidden"], path, line, source_node, "trusted_memory", module, "local LLM output/path must not import trusted-memory writer modules")
            continue
        if source_node in {"local_llm"} and module in SOURCE_MUTATION_MODULES:
            add_finding(findings["forbidden"], path, line, source_node, "source", module, "local LLM path must not import production source mutation tools")
            continue
        if source_node in {"local_llm"} and module in ROUTE_MUTATION_MODULES:
            add_finding(findings["forbidden"], path, line, source_node, "routes", module, "local LLM path must not import route mutation tools")
            continue
        if source_node == "reports":
            add_finding(findings["forbidden"], path, line, source_node, dest_node, module, "reports must not import runtime/source modules as authority")
            continue
        if source_node == "quarantine" and dest_node in {"trusted_memory", "routes", "code_companion"}:
            add_finding(findings["forbidden"], path, line, source_node, dest_node, module, "quarantine must not import trust, route, or source mutation modules")
            continue

        if path.name == "engel_hive_data_services.py" and module == "engel_research_office_data":
            add_finding(findings["temporary_allowed"], path, line, "hive_data", "research_office_data", module, "Hive data wrapper calls current Research Office snapshot builder during transition")
        elif path.name == "engel_companion.py" and module == "engel_hive_data_services":
            add_finding(findings["allowed"], path, line, "companion", "hive_data", module, "Companion imports compact read-only Hive summary helper")
        elif path.name == "engel_companion.py" and module == "engel_research_office":
            add_finding(findings["temporary_allowed"], path, line, "companion", "research_office", module, "Companion lazy Hive launcher import remains temporary allowed")
        elif path.name == "engel_super_swarm_hive_3d_scaffold.py" and module == "engel_hive_data_services":
            add_finding(findings["allowed"], path, line, "super_swarm", "hive_data", module, "Super Swarm imports read-only Hive snapshot wrapper")
        elif path.name == "engel_research_office.py" and module == "engel_research_office_data":
            add_finding(findings["temporary_allowed"], path, line, "research_office", "research_office_data", module, "Research Office uses current data layer until extraction")
        elif path.name == "engel_research_office.py" and module == "engel_route_explorer":
            add_finding(findings["temporary_allowed"], path, line, "research_office", "routes", module, "Research Office route/status view remains temporary allowed")
        elif source_node == "verifiers":
            add_finding(findings["allowed"], path, line, source_node, dest_node, module, "Verifier local import allowed if static/safe and no GUI launch")
        elif source_node == "tests":
            add_finding(findings["allowed"], path, line, source_node, dest_node, module, "Test/smoke import allowed within bounded test scope")
        elif module in MEMORY_PROMOTION_REVIEW_MODULES and source_node in {"candidate_memory", "companion", "research_office", "core"}:
            add_finding(findings["review_required"], path, line, source_node, "memory", module, "Memory promotion helper import requires review; current known uses are report/status oriented")
        elif module in TRUSTED_MEMORY_WRITER_MODULES and source_node in {"core", "trusted_memory", "verifiers"}:
            add_finding(findings["review_required"], path, line, source_node, "trusted_memory", module, "Trusted-memory writer/target import is permitted only under explicit contract and approval")
        elif module in SOURCE_MUTATION_MODULES and source_node not in {"code_companion", "verifiers", "tests"}:
            add_finding(findings["review_required"], path, line, source_node, "source", module, "Source mutation tooling import needs review")
        elif module in ROUTE_MUTATION_MODULES and source_node not in {"core", "routes", "verifiers", "tests"}:
            add_finding(findings["review_required"], path, line, source_node, "routes", module, "Route mutation tooling import needs review")


def summarize(label: str, items: list[dict[str, Any]], limit: int = 30) -> None:
    print(f"{label}: {len(items)}")
    for item in items[:limit]:
        line = item.get("line", 0)
        suffix = f":{line}" if line else ""
        print(
            "  - {file}{suffix} {source_node}->{destination_node} import {module}: {reason}".format(
                suffix=suffix,
                **item,
            )
        )
    if len(items) > limit:
        print(f"  ... {len(items) - limit} more")


def main() -> int:
    try:
        contract = load_contract()
        required_nodes = set(contract.get("nodes", []))
        for node in ["candidate_memory", "trusted_memory", "quarantine", "local_llm", "remote_queen", "reports"]:
            if node not in required_nodes:
                raise CheckFailure("contract missing node: " + node)

        files = python_files()
        local_modules = local_module_names(files)
        findings: dict[str, list[dict[str, Any]]] = {
            "allowed": [],
            "temporary_allowed": [],
            "review_required": [],
            "forbidden": [],
        }
        for path in files:
            analyze_file(path, local_modules, findings)

        print("DE_BRUIJN_IMPORT_BOUNDARY_SCAN")
        print("scanned_python_files:", len(files))
        summarize("allowed_findings", findings["allowed"])
        summarize("temporary_allowed_findings", findings["temporary_allowed"])
        summarize("review_required_findings", findings["review_required"])
        summarize("forbidden_findings", findings["forbidden"])

        if findings["forbidden"]:
            print("DE_BRUIJN_IMPORT_BOUNDARY_VERIFICATION_FAIL")
            return 1
        print("DE_BRUIJN_IMPORT_BOUNDARY_VERIFICATION_PASS")
        return 0
    except CheckFailure as exc:
        print("FAIL", str(exc))
        print("DE_BRUIJN_IMPORT_BOUNDARY_VERIFICATION_FAIL")
        return 1


if __name__ == "__main__":
    sys.exit(main())
