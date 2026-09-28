from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "tools" / "engel_code_companion_review_surface.py"
VERIFIER = ROOT / "tools" / "verify_engel_code_companion_review_surface.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_CODE_COMPANION_PATCH_APPLY_UI_REVIEW_SURFACE_V1.md"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"

REQUIRED_SECTIONS = [
    "Overview",
    "Candidates",
    "Patch Plans",
    "Patch Bundles",
    "Gates",
    "Dry Runs",
    "Approvals",
    "Applies",
    "Backups / Rollback",
    "Verifier Results",
]

REQUIRED_BADGES = [
    "READ ONLY",
    "NO APPLY",
    "NO ROLLBACK",
    "NO PASSWORD COLLECTION",
    "NO TOKEN COLLECTION",
]

REQUIRED_BUTTON_LABELS = [
    "Refresh",
    "Open Preview",
    "Copy Path",
    "Show Folder Path",
    "Close",
]

FORBIDDEN_BUTTON_LABELS = [
    "Apply",
    "Execute",
    "Run Patch",
    "Rollback Now",
    "Trust",
    "Write Memory",
    "Promote",
    "Bypass",
    "Verify and Apply",
]

FORBIDDEN_IMPORTS = {
    "requests",
    "urllib",
    "socket",
    "webbrowser",
    "subprocess",
    "threading",
    "multiprocessing",
    "asyncio",
    "http",
    "ftplib",
    "smtplib",
    "openai",
    "anthropic",
}

FORBIDDEN_CALLS = {
    "eval",
    "__import__",
    "compile",
    "Popen",
    "system",
    "startfile",
    "run",
    "call",
    "check_call",
    "check_output",
    "mkdir",
    "write_text",
    "write_bytes",
    "unlink",
    "rename",
}

REQUIRED_COMMANDS = [
    "code companion review surface",
]


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def load_module():
    spec = importlib.util.spec_from_file_location("engel_code_companion_review_surface", MODULE)
    require(spec is not None and spec.loader is not None, "could not load review surface module")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_code_companion_review_surface"] = module
    spec.loader.exec_module(module)
    return module


def check_files_exist() -> None:
    for path in [MODULE, VERIFIER, REPORT, COMMANDS, CODEX_VERIFY]:
        require(path.exists() and path.is_file(), "missing required file: " + str(path.relative_to(ROOT)))


def check_static_source_safety() -> None:
    source = read(MODULE)
    lowered = source.lower()
    tree = ast.parse(source)

    for needle in REQUIRED_SECTIONS + REQUIRED_BADGES + REQUIRED_BUTTON_LABELS:
        require(needle in source, "review surface missing required UI text: " + needle)
    for needle in [
        "MAX_PREVIEW_BYTES = 20 * 1024",
        "ALLOWED_PREVIEW_SUFFIXES",
        "UNTRUSTED READ-ONLY PREVIEW",
        "Rollback section not available",
        "Displayed content is untrusted text; links and commands are not executed.",
        "Folder path shown. No external file browser was launched.",
    ]:
        require(needle in source, "review surface missing safety/bounded text: " + needle)

    require("QLineEdit" not in source, "review surface must not include password/token input widgets")
    for forbidden in [
        "enter password",
        "approval token:",
        "password:",
        "token input",
        "approval-token input",
        "filewatcher",
        "watchdog",
        "qfilesystemwatcher",
        "os.startfile",
        "webbrowser.",
        "requests.",
        "subprocess.",
        "openai.",
        "anthropic.",
    ]:
        require(forbidden not in lowered, "review surface contains forbidden text/behavior: " + forbidden)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                require(alias.name.split(".")[0] not in FORBIDDEN_IMPORTS, "forbidden import: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            require(node.module.split(".")[0] not in FORBIDDEN_IMPORTS, "forbidden import: " + node.module)
        elif isinstance(node, (ast.While, ast.AsyncFunctionDef)):
            raise CheckFailure("review surface contains forbidden background-worker shape")
        elif isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
            if isinstance(func, ast.Name) and name == "exec":
                raise CheckFailure("review surface contains forbidden call: exec")
            if name in FORBIDDEN_CALLS:
                if name == "open":
                    continue
                raise CheckFailure("review surface contains forbidden call: " + name)


def check_button_contract() -> None:
    module = load_module()
    require(list(module.BUTTON_LABELS) == REQUIRED_BUTTON_LABELS, "button labels must be the allowed review-only set")
    for label in FORBIDDEN_BUTTON_LABELS:
        require(label not in module.BUTTON_LABELS, "forbidden action button label exposed: " + label)


def check_runtime_helpers() -> None:
    module = load_module()
    sections = module.build_sections()
    titles = [section.title for section in sections]
    for title in REQUIRED_SECTIONS:
        require(title in titles, "missing review section: " + title)
    counts = module.section_counts()
    require(isinstance(counts, dict), "section_counts must return a dict")
    for title in REQUIRED_SECTIONS:
        if title != "Overview":
            require(title in counts, "section_counts missing: " + title)
    require(module.MAX_PREVIEW_BYTES == 20 * 1024, "preview limit changed")
    require(module.ALLOWED_PREVIEW_SUFFIXES == {".md", ".json", ".txt"}, "preview suffix allowlist changed")

    commands_preview = module.preview_file(COMMANDS)
    require(commands_preview.supported is True, "markdown preview should be supported")
    require("UNTRUSTED READ-ONLY PREVIEW" in commands_preview.text, "preview missing untrusted banner")

    unsupported = module.preview_file(MODULE)
    require(unsupported.supported is False, "source preview should not be supported by the GUI")
    require("markdown, JSON, and text files only" in unsupported.text, "unsupported preview message missing")

    outside = module.preview_file(Path("C:/Windows/System32/notepad.exe"))
    require(outside.supported is False, "outside or unsupported files must not preview")

    status = module.render_cli_status()
    for needle in REQUIRED_BADGES + ["Preview types: markdown, JSON, and text only.", "links and commands are not executed"]:
        require(needle in status, "CLI status missing: " + needle)
    require("Rollback" in module.rollback_status_text(), "rollback state must be explicit")


def check_docs_and_registration() -> None:
    report = read(REPORT)
    for needle in [
        "Engel Code Companion Patch Apply UI Review Surface V1",
        "Read-only GUI",
        "No apply or rollback controls",
        "Preview Limit",
        "Missing Phase 9 rollback data",
        "Packaging skipped",
        "Code Companion Phase 10",
        "It does not apply patches, rollback patches, collect passwords, collect approval tokens, mutate source, execute commands, or call providers.",
    ]:
        require(needle in report, "Phase 10 report missing required text: " + needle)
    commands = read(COMMANDS)
    for command in REQUIRED_COMMANDS:
        require(command in commands, "ENGEL_COMMANDS missing command doc: " + command)
    codex_verify = read(CODEX_VERIFY)
    require(
        "tools\\verify_engel_code_companion_review_surface.py" in codex_verify,
        "codex verifier does not include review surface verifier",
    )


def main() -> int:
    try:
        check_files_exist()
        check_static_source_safety()
        check_button_contract()
        check_runtime_helpers()
        check_docs_and_registration()
    except CheckFailure as exc:
        print("[FAIL]", exc)
        return 1
    print("[PASS] Engel Code Companion review surface verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
