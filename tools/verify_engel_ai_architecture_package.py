#!/usr/bin/env python3
from __future__ import annotations

import ast
import importlib
import re
import sys
from pathlib import Path


sys.dont_write_bytecode = True

_file = globals().get("__file__")
if not _file or not isinstance(_file, str) or _file.startswith("<"):
    ROOT = Path.cwd()
else:
    try:
        ROOT = Path(_file).resolve().parents[1]
    except (OSError, ValueError, IndexError):
        ROOT = Path.cwd()

AUTHORITY = "Josh > Guardian > Engel/runtime"
WORKFLOW = "Ask \u2192 Plan \u2192 Proceed \u2192 Receipt \u2192 Review"

PACKAGE_DIRS = [
    ROOT / "engel",
    ROOT / "engel" / "mind",
    ROOT / "engel" / "guardian",
    ROOT / "engel" / "action",
    ROOT / "engel" / "memory",
    ROOT / "engel" / "hive",
    ROOT / "engel" / "gui",
    ROOT / "engel" / "verifiers",
]

ARCHITECTURE_MAP = ROOT / "engel" / "ENGEL_AI_ARCHITECTURE.md"

WRAPPERS = {
    ROOT / "engel" / "mind" / "intent_planner.py": ("engel.mind.intent_planner", "engel_ai_intent_planner"),
    ROOT / "engel" / "memory" / "proceed_receipts.py": ("engel.memory.proceed_receipts", "engel_ai_proceed_receipts"),
    ROOT / "engel" / "memory" / "receipt_viewer.py": ("engel.memory.receipt_viewer", "engel_ai_receipt_viewer"),
    ROOT / "engel" / "action" / "human_command_mode.py": ("engel.action.human_command_mode", "engel_human_command_mode"),
    ROOT / "engel" / "mind" / "offline_seed_llm.py": ("engel.mind.offline_seed_llm", "engel_offline_seed_llm"),
    ROOT / "engel" / "mind" / "communication_router.py": ("engel.mind.communication_router", "engel_communication_router"),
    ROOT / "engel" / "guardian" / "prompt_injection_guard.py": (
        "engel.guardian.prompt_injection_guard",
        "engel_prompt_injection_guard",
    ),
}

ROOT_MODULES = [
    ROOT / "engel_app.py",
    ROOT / "engel_companion.py",
    ROOT / "engel_ai_intent_planner.py",
    ROOT / "engel_ai_proceed_receipts.py",
    ROOT / "engel_human_command_mode.py",
    ROOT / "engel_offline_seed_llm.py",
    ROOT / "engel_communication_router.py",
    ROOT / "engel_prompt_injection_guard.py",
    ROOT / "tools" / "engel_super_swarm_hive_3d_scaffold.py",
]

RECEIPT_VIEWER = ROOT / "engel_ai_receipt_viewer.py"
if RECEIPT_VIEWER.exists():
    ROOT_MODULES.append(RECEIPT_VIEWER)

LIVE_RUNTIME_FILES = list(ROOT_MODULES)


class CheckFailure(Exception):
    pass


def _term(*parts: str) -> str:
    return "".join(parts)


def _forbidden_terms() -> list[str]:
    return [
        _term("op", "enai"),
        _term("anth", "ropic"),
        _term("api", "_", "key"),
        _term("requests", "."),
        _term("http", "://"),
        _term("https", "://"),
        _term("sock", "et"),
        _term("web", "sock", "et"),
        _term("u", "dp"),
        _term("t", "cp"),
        _term("blue", "tooth"),
        _term("md", "ns"),
        _term("zero", "conf"),
        _term("thread", "ing"),
        _term("multi", "processing"),
        _term("watch", "dog"),
        _term("sche", "dule"),
        _term("while", " True"),
        _term("Start", "-", "Process"),
        _term("os", ".", "system"),
        _term("P", "open"),
        _term("shell", "=", "True"),
        _term("local", "host", ":", "11434"),
        _term("ol", "lama"),
    ]


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _read(path: Path) -> str:
    if not path.exists():
        raise CheckFailure("missing required file: " + _rel(path))
    return path.read_text(encoding="utf-8", errors="replace")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def _compile_source(path: Path) -> None:
    source = path.read_text(encoding="utf-8-sig", errors="replace")
    try:
        compile(source, str(path), "exec")
    except SyntaxError as exc:
        raise CheckFailure("compile failed for " + _rel(path) + ": " + str(exc)) from exc


def _snapshot(paths: list[Path]) -> dict[str, tuple[int, int]]:
    state: dict[str, tuple[int, int]] = {}
    for path in paths:
        if path.is_file():
            stat = path.stat()
            state[_rel(path)] = (int(stat.st_size), int(stat.st_mtime_ns))
        elif path.is_dir():
            for child in path.rglob("*"):
                if child.is_file():
                    stat = child.stat()
                    state[_rel(child)] = (int(stat.st_size), int(stat.st_mtime_ns))
    return state


def _import_references_new_package(path: Path) -> bool:
    source = _read(path)
    return re.search(r"^\s*(from\s+engel\.|import\s+engel\.)", source, flags=re.MULTILINE) is not None


def check_package_structure() -> None:
    for directory in PACKAGE_DIRS:
        _require(directory.exists() and directory.is_dir(), "missing package folder: " + _rel(directory))
        init_file = directory / "__init__.py"
        _require(init_file.exists() and init_file.is_file(), "missing package init: " + _rel(init_file))
        _compile_source(init_file)


def check_architecture_map() -> None:
    text = _read(ARCHITECTURE_MAP)
    for needle in [
        "mind",
        "guardian",
        "action",
        "memory",
        "hive",
        "gui",
        "verifiers",
        AUTHORITY,
        WORKFLOW,
    ]:
        _require(needle in text, "architecture map missing: " + needle)
    for forbidden in [
        "Guardian > Josh",
        "Engel/runtime > Guardian",
        "Engel/runtime > Josh",
    ]:
        _require(forbidden not in text, "architecture map has forbidden authority wording: " + forbidden)


def check_wrappers_static() -> None:
    for wrapper, (_module_name, root_module) in WRAPPERS.items():
        root_path = ROOT / (root_module + ".py")
        if not root_path.exists():
            _require(not wrapper.exists(), "wrapper exists for missing root module: " + _rel(wrapper))
            continue
        _require(wrapper.exists(), "missing wrapper for existing root module: " + _rel(wrapper))
        source = _read(wrapper)
        _compile_source(wrapper)
        lowered = source.lower()
        for term in _forbidden_terms():
            _require(term.lower() not in lowered, "wrapper contains forbidden pattern " + term + ": " + _rel(wrapper))

        tree = ast.parse(source)
        executable_nodes = [
            node
            for node in tree.body
            if not (isinstance(node, ast.Expr) and isinstance(getattr(node, "value", None), ast.Constant))
        ]
        _require(len(executable_nodes) == 1, "wrapper must contain only docstring plus one import: " + _rel(wrapper))
        node = executable_nodes[0]
        _require(isinstance(node, ast.ImportFrom), "wrapper import must be ImportFrom: " + _rel(wrapper))
        _require(node.module == root_module, "wrapper imports unexpected module: " + _rel(wrapper))
        _require(len(node.names) == 1 and node.names[0].name == "*", "wrapper must re-export with import star: " + _rel(wrapper))


def check_wrapper_imports_without_file_side_effects() -> None:
    sys.path.insert(0, str(ROOT))
    watch_paths = [
        ROOT / "engel",
        ROOT / "memory",
        ROOT / "reports" / "ai_proceed_receipts",
    ] + ROOT_MODULES
    before = _snapshot([path for path in watch_paths if path.exists()])
    for wrapper, (module_name, root_module) in WRAPPERS.items():
        root_path = ROOT / (root_module + ".py")
        if wrapper.exists() and root_path.exists():
            importlib.import_module(module_name)
    after = _snapshot([path for path in watch_paths if path.exists()])
    _require(before == after, "wrapper import changed watched files")


def check_root_modules_still_compile() -> None:
    for path in ROOT_MODULES:
        _compile_source(path)


def check_live_runtime_imports_unchanged() -> None:
    for path in LIVE_RUNTIME_FILES:
        _require(not _import_references_new_package(path), "live runtime file imports new package wrapper: " + _rel(path))


def check_no_behavior_added_by_new_sources() -> None:
    package_sources = list((ROOT / "engel").rglob("*.py")) + [ROOT / "tools" / "verify_engel_ai_architecture_package.py"]
    for path in package_sources:
        source = _read(path)
        lowered = source.lower()
        for term in _forbidden_terms():
            _require(term.lower() not in lowered, "new source contains forbidden pattern " + term + ": " + _rel(path))

    wrapper_names = "\n".join(_rel(path) for path in WRAPPERS)
    for behavior in [
        "route mutation",
        "queue mutation",
        "trusted-memory write",
        "model-command execution",
        "source-edit autonomy",
    ]:
        _require(behavior not in wrapper_names.lower(), "wrapper name unexpectedly describes behavior: " + behavior)


def main() -> int:
    checks = [
        ("package_structure", check_package_structure),
        ("architecture_map", check_architecture_map),
        ("wrappers_static", check_wrappers_static),
        ("wrapper_imports_no_file_side_effects", check_wrapper_imports_without_file_side_effects),
        ("root_modules_compile_in_memory", check_root_modules_still_compile),
        ("live_runtime_imports_unchanged", check_live_runtime_imports_unchanged),
        ("new_sources_forbidden_patterns", check_no_behavior_added_by_new_sources),
    ]
    failures: list[str] = []
    for name, fn in checks:
        try:
            fn()
            print("PASS " + name)
        except CheckFailure as exc:
            failures.append(name + ": " + str(exc))
            print("FAIL " + name + ": " + str(exc))
        except Exception as exc:
            failures.append(name + ": unexpected error: " + str(exc))
            print("FAIL " + name + ": unexpected error: " + str(exc))

    if failures:
        print()
        print("ENGEL_AI_ARCHITECTURE_PACKAGE_VERIFICATION_FAIL")
        for failure in failures:
            print("- " + failure)
        return 1

    print()
    print("ENGEL_AI_ARCHITECTURE_PACKAGE_VERIFICATION_PASS")
    print("Authority: " + AUTHORITY)
    print("Workflow: " + WORKFLOW.replace("\u2192", "->"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
