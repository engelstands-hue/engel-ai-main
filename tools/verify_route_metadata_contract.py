from __future__ import annotations

import ast
import json
import sys
from pathlib import Path


_file = globals().get("__file__")
if not _file or not isinstance(_file, str) or _file.startswith("<"):
    ROOT = Path.cwd()
else:
    try:
        ROOT = Path(_file).resolve().parents[1]
    except (OSError, ValueError, IndexError):
        ROOT = Path.cwd()

DOCS = {
    "contract": ROOT / "memory" / "ROUTE_METADATA_VERIFIER_CONTRACT_V1.md",
    "ey2_report": ROOT / "reports" / "app" / "V2APP_EY2_ROUTE_AND_COMMAND_METADATA_INVENTORY.md",
    "ey2_checkpoint": ROOT / "memory" / "V2APP_EY2_ROUTE_AND_COMMAND_METADATA_INVENTORY.json",
    "ey3_report": ROOT
    / "reports"
    / "app"
    / "V2APP_EY3_ROUTE_AND_COMMAND_METADATA_DOCUMENTATION_NORMALIZATION.md",
    "ey3_checkpoint": ROOT
    / "memory"
    / "V2APP_EY3_ROUTE_AND_COMMAND_METADATA_DOCUMENTATION_NORMALIZATION.json",
    "commands": ROOT / "memory" / "ENGEL_COMMANDS.md",
    "standard_checklist": ROOT / "memory" / "STANDARD_VERIFIER_CHECKLIST_V1.md",
    "route_matrix": ROOT / "memory" / "ROUTE_VERIFICATION_SET_V1.json",
    "refactor_contract": ROOT / "memory" / "ENGEL_REFACTOR_SAFETY_CONTRACT_V1.md",
    "constitution": ROOT / "memory" / "ENGEL_CORE_DIRECTION_AND_SAFETY_CONSTITUTION_V1.md",
}

GUIDING_SENTENCE = "Route metadata must never make a command look safer than it actually is."

REQUIRED_CATEGORIES = [
    "pure read-only status",
    "status-like with known report/log side effects",
    "preview-only",
    "report-only",
    "APPROVE_REPORT",
    "APPROVE / approval-required",
    "proposal-only",
    "trusted-write",
    "source-edit",
    "disabled/future",
    "unknown / needs review",
]

STATUS_LIKE_ROUTES = [
    "health",
    "router status",
    "tool registry status",
]

WRITE_CLASSES = [
    "no-write",
    "known CLI log only",
    "report-only write",
    "report/log side effect",
    "proposal-only write",
    "trusted-memory write",
    "queue mutation",
    "source edit",
    "unknown",
]


class CheckFailure(Exception):
    pass


def _normalize(text: str) -> str:
    cleaned = text.lower().replace("\\", "/").replace("`", "")
    return " ".join(cleaned.split())


def _read_text(path: Path) -> str:
    if not path.exists():
        raise CheckFailure(f"missing required file: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8", errors="replace")


def _load_docs() -> dict[str, str]:
    return {name: _read_text(path) for name, path in DOCS.items()}


def _require_text(text: str, needle: str, label: str) -> None:
    if _normalize(needle) not in _normalize(text):
        raise CheckFailure(f"{label} missing expected text: {needle}")


def _require_json(path: Path) -> object:
    try:
        return json.loads(_read_text(path))
    except json.JSONDecodeError as exc:
        raise CheckFailure(f"invalid JSON in {path.relative_to(ROOT)}: {exc}") from exc


def _assert_categories_documented(combined: str) -> None:
    for category in REQUIRED_CATEGORIES:
        _require_text(combined, category, "route category documentation")


def _assert_write_classes_documented(combined: str) -> None:
    for write_class in WRITE_CLASSES:
        _require_text(combined, write_class, "write behavior documentation")


def _assert_status_like_routes_honest(combined: str) -> None:
    normalized = _normalize(combined)
    for route in STATUS_LIKE_ROUTES:
        if route not in normalized:
            raise CheckFailure(f"status-like route missing from metadata docs: {route}")
        side_effect_phrase = f"{route}: status-like with known report/log side effects"
        if _normalize(side_effect_phrase) not in normalized:
            raise CheckFailure(
                f"{route} is not explicitly classified as status-like with known report/log side effects"
            )

    bad_patterns = [
        "`{route}` [read-only",
        "{route} [read-only",
        "`{route}`: pure read-only",
        "{route}: pure read-only",
        "`{route}` - pure read-only",
        "{route} - pure read-only",
    ]
    for route in STATUS_LIKE_ROUTES:
        for pattern in bad_patterns:
            rendered = pattern.format(route=route)
            if _normalize(rendered) in normalized:
                raise CheckFailure(
                    f"{route} appears to be documented as safer than its known side-effect class"
                )


def _assert_ey2_inventory(ey2_report: str, ey2_checkpoint_path: Path) -> None:
    checkpoint = _require_json(ey2_checkpoint_path)
    if not isinstance(checkpoint, dict):
        raise CheckFailure("EY2 checkpoint must be a JSON object")
    metadata_counts = checkpoint.get("metadata_counts")
    if not isinstance(metadata_counts, dict):
        raise CheckFailure("EY2 checkpoint missing metadata_counts")
    expected_counts = {
        "safe_router_registry_patterns": 205,
        "tool_registry_entries": 231,
        "route_verification_matrix_entries": 27,
    }
    for key, minimum in expected_counts.items():
        value = metadata_counts.get(key)
        if not isinstance(value, int) or value < minimum:
            raise CheckFailure(f"EY2 checkpoint missing expected inventory count {key}>={minimum}")
    for phrase in [
        "Safe router registry",
        "Tool registry",
        "Route verification matrix",
        "205 patterns",
        "231 entries",
        "27 entries",
    ]:
        _require_text(ey2_report, phrase, "EY2 inventory report")


def _assert_ey3_normalization(ey3_report: str, ey3_checkpoint_path: Path) -> None:
    checkpoint = _require_json(ey3_checkpoint_path)
    if not isinstance(checkpoint, dict):
        raise CheckFailure("EY3 checkpoint must be a JSON object")
    categories = checkpoint.get("normalized_route_categories")
    write_labels = checkpoint.get("honest_write_behavior_labels")
    status_like = checkpoint.get("status_like_with_known_side_effects")
    if not isinstance(categories, list):
        raise CheckFailure("EY3 checkpoint missing normalized_route_categories")
    if not isinstance(write_labels, list):
        raise CheckFailure("EY3 checkpoint missing honest_write_behavior_labels")
    if not isinstance(status_like, list):
        raise CheckFailure("EY3 checkpoint missing status_like_with_known_side_effects")
    for category in REQUIRED_CATEGORIES:
        if category not in categories:
            raise CheckFailure(f"EY3 checkpoint missing category: {category}")
    for write_class in WRITE_CLASSES:
        if write_class not in write_labels:
            raise CheckFailure(f"EY3 checkpoint missing write behavior label: {write_class}")
    for route in STATUS_LIKE_ROUTES:
        if route not in status_like:
            raise CheckFailure(f"EY3 checkpoint missing status-like side-effect route: {route}")
    _require_text(
        ey3_report,
        "EY3 changes documentation only. It does not change route behavior, command behavior, write behavior, runtime behavior, or verifier behavior.",
        "EY3 normalization report",
    )


def _assert_route_matrix_shape(path: Path) -> None:
    matrix = _require_json(path)
    if not isinstance(matrix, dict):
        raise CheckFailure("route matrix must be a JSON object")
    entries = matrix.get("route_regression_matrix_entries")
    if not isinstance(entries, list) or len(entries) < 27:
        raise CheckFailure("route matrix missing expected route_regression_matrix_entries")
    for entry in entries:
        if not isinstance(entry, dict):
            raise CheckFailure("route matrix contains a non-object entry")
        if "command" not in entry or "expected_behavior" not in entry:
            raise CheckFailure("route matrix entry missing command or expected_behavior")


def _assert_commands_alignment(commands: str) -> None:
    _require_text(commands, "Command type guide", "command docs")
    category_needles = [
        "pure read-only status routes",
        "status-like routes with known report/log side effects",
        "preview-only routes",
        "report-only routes",
        "APPROVE_REPORT",
        "APPROVE` / approval-required routes",
        "proposal-only routes",
        "trusted-write routes",
        "source-edit routes",
        "disabled/future routes",
        "unknown / needs-review routes",
    ]
    for category in category_needles:
        _require_text(commands, category, "command docs category alignment")
    for write_class in WRITE_CLASSES:
        _require_text(commands, write_class, "command docs write-class alignment")
    for route in STATUS_LIKE_ROUTES:
        _require_text(commands, route, "command docs status-like route alignment")
    _require_text(
        commands,
        "must not be treated as pure read-only/no-write smoke checks",
        "command docs side-effect warning",
    )


def _assert_contract_alignment(docs: dict[str, str]) -> None:
    _require_text(docs["contract"], GUIDING_SENTENCE, "EY4 route metadata contract")
    _require_text(
        docs["contract"],
        "EY4 is a verifier contract only. It does not implement a verifier, execute side-effecting routes, change route behavior, or perform a refactor.",
        "EY4 route metadata contract",
    )
    _require_text(docs["refactor_contract"], "Refactor only after safety is locked", "refactor contract")
    _require_text(
        docs["constitution"],
        "Engel may observe, organize, compare, research, summarize, propose, verify, and report.",
        "core direction constitution",
    )


def _assert_source_static_and_read_only() -> None:
    source_path = Path(__file__)
    source = source_path.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(source)

    blocked_import_roots = {
        "http",
        "requests",
        "socket",
        "subprocess",
        "urllib",
        "webbrowser",
    }
    blocked_calls = {
        "open",
        "exec",
        "eval",
    }
    blocked_methods = {
        "append",
        "mkdir",
        "rename",
        "rmdir",
        "touch",
        "unlink",
        "write",
        "write_bytes",
        "write_text",
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_name = alias.name.split(".")[0]
                if root_name in blocked_import_roots:
                    raise CheckFailure(f"verifier imports forbidden module: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            root_name = module.split(".")[0]
            if root_name in blocked_import_roots:
                raise CheckFailure(f"verifier imports from forbidden module: {module}")
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in blocked_calls:
                raise CheckFailure(f"verifier calls forbidden function: {func.id}")
            if isinstance(func, ast.Attribute) and func.attr in blocked_methods:
                raise CheckFailure(f"verifier calls forbidden method: {func.attr}")


def pass_check(name: str) -> None:
    print(f"PASS {name}")


def main() -> int:
    try:
        docs = _load_docs()
        pass_check("required_files_exist")

        _assert_contract_alignment(docs)
        pass_check("contract_and_constitution_alignment")

        combined = "\n".join(docs.values())
        _assert_categories_documented(combined)
        pass_check("route_category_definitions_documented")

        _assert_status_like_routes_honest(combined)
        pass_check("status_like_side_effect_routes_documented_honestly")

        _assert_write_classes_documented(combined)
        pass_check("write_behavior_classes_documented")

        _assert_ey2_inventory(docs["ey2_report"], DOCS["ey2_checkpoint"])
        pass_check("ey2_inventory_present_with_counts")

        _assert_ey3_normalization(docs["ey3_report"], DOCS["ey3_checkpoint"])
        pass_check("ey3_normalization_present")

        _assert_route_matrix_shape(DOCS["route_matrix"])
        pass_check("route_matrix_shape_read_static")

        _assert_commands_alignment(docs["commands"])
        pass_check("commands_documentation_alignment")

        _assert_source_static_and_read_only()
        pass_check("verifier_source_static_no_route_execution_or_writes")

        print("\nROUTE_METADATA_CONTRACT_VERIFICATION_PASS")
        return 0
    except CheckFailure as exc:
        print("ROUTE_METADATA_CONTRACT_VERIFICATION_FAIL")
        print(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
