from __future__ import annotations

import ast
import io
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
GENERATOR_PATH = ROOT / "engel_untrusted_research_note_generator.py"
TOPIC_LIBRARY_PATH = ROOT / "memory" / "ENGEL_SELF_RESEARCH_TOPIC_LIBRARY_V1.json"
OUTPUT_DIR = ROOT / "reports" / "self_research_notes"

REQUIRED_STATUSES = [
    "UNTRUSTED_RESEARCH_NOTE_GENERATOR",
    "LOCAL_ONLY",
    "SOURCE_BOUNDED",
    "TOPIC_LIBRARY_GUIDED",
    "EXPLICIT_TOPIC_REQUIRED",
    "EXPLICIT_SOURCE_REQUIRED_FOR_REAL_NOTE",
    "RESEARCH_NOT_MEMORY",
    "RESEARCH_NOT_EXECUTION",
    "RESEARCH_NOT_TRAINING",
    "NOT_APPROVED_LESSON",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_SOURCE_MUTATION",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_AUTO_DOWNLOADS",
    "NO_AUTO_INDEXING",
    "NO_EMBEDDING",
    "NO_RUNTIME_TRIGGER",
    "NO_BACKGROUND_WORKER",
    "NO_AUTO_RESEARCH_LOOP",
]

REQUIRED_NOTE_LABELS = [
    "UNTRUSTED_RESEARCH_NOTE",
    "RESEARCH_NOT_MEMORY",
    "RESEARCH_NOT_EXECUTION",
    "RESEARCH_NOT_TRAINING",
    "NOT_VERIFIED_FACT",
    "NOT_APPROVED_LESSON",
    "NOT_TRUSTED_MEMORY",
    "NO_AUTOMATION_TRIGGERED",
    "HUMAN_REVIEW_REQUIRED_FOR_MEMORY",
]

REQUIRED_NOTE_FIELDS = [
    "research_note_id",
    "topic_id",
    "topic_title",
    "topic_category",
    "source_paths_or_references",
    "source_type",
    "generated_at",
    "generator_version",
    "trust_status",
    "research_question",
    "short_summary",
    "key_observations",
    "uncertainty_notes",
    "source_risk_notes",
    "prompt_injection_risk_notes",
    "possible_lesson_candidates",
    "possible_verifier_improvement_candidates",
    "possible_self_fix_improvement_candidates",
    "possible_memory_candidate_summary",
    "memory_boundary",
    "execution_boundary",
    "training_boundary",
    "next_safe_manual_step",
    "required_review_before_use",
    "no_trusted_memory_write",
]

REQUIRED_RESTRICTIONS = [
    "reject URLs",
    "reject UNC paths",
    "reject paths outside project root",
    "reject wildcard scans",
    "reject recursive folder scans",
    "reject folders as source input",
    r"reject G:\\ENGEL_APP_MEMORY",
    r"reject E:\\ENGEL_APP_MEMORY",
    r"reject live\\app",
    "reject staging",
]

REQUIRED_OPTIONS = ["--demo", "--topic-id", "--source", "--dry-run", "--write"]

FORBIDDEN_IMPORT_ROOTS = {
    "requests",
    "urllib",
    "socket",
    "webbrowser",
    "openai",
    "chromadb",
    "faiss",
    "llama",
    "ollama",
    "subprocess",
    "glob",
    "shutil",
    "threading",
    "multiprocessing",
}

FORBIDDEN_CALLS = {
    "os.walk",
    "Path.rglob",
    "rglob",
    "glob",
    "copytree",
    "download",
    "browser",
    "provider_call",
    "index_documents",
    "embed",
    "train",
    "fine_tune",
    "load_model",
    "inference",
    "trusted_memory_write",
    "start_background_worker",
    "start_auto_research_loop",
}


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_generator_module():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import engel_untrusted_research_note_generator as generator

    return generator


def check_required_files() -> None:
    require(GENERATOR_PATH.exists(), "required generator source missing")
    require(TOPIC_LIBRARY_PATH.exists(), "topic library missing")
    require(OUTPUT_DIR.exists(), "safe output path reports\\self_research_notes missing")


def check_required_text() -> None:
    text = read_text(GENERATOR_PATH)
    for status in REQUIRED_STATUSES:
        require(status in text, f"required status missing: {status}")
    for label in REQUIRED_NOTE_LABELS:
        require(label in text, f"required note label missing: {label}")
    for field in REQUIRED_NOTE_FIELDS:
        require(field in text, f"required note field missing: {field}")
    for restriction in REQUIRED_RESTRICTIONS:
        require(restriction in text, f"required source restriction missing: {restriction}")
    for option in REQUIRED_OPTIONS:
        require(option in text, f"required CLI option missing: {option}")
    require(r"reports\\self_research_notes" in text, "safe output path text missing")
    require("MAX_SOURCE_CHARS = 20000" in text, "source read cap missing")


def check_ast_forbidden_behavior() -> None:
    tree = ast.parse(read_text(GENERATOR_PATH))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_name = alias.name.split(".")[0]
                require(root_name not in FORBIDDEN_IMPORT_ROOTS, f"forbidden import in generator: {alias.name}")
        if isinstance(node, ast.ImportFrom) and node.module:
            root_name = node.module.split(".")[0]
            require(root_name not in FORBIDDEN_IMPORT_ROOTS, f"forbidden import-from in generator: {node.module}")
        if isinstance(node, ast.Call):
            call_name = ""
            if isinstance(node.func, ast.Name):
                call_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                parts = [node.func.attr]
                value = node.func.value
                while isinstance(value, ast.Attribute):
                    parts.append(value.attr)
                    value = value.value
                if isinstance(value, ast.Name):
                    parts.append(value.id)
                call_name = ".".join(reversed(parts))
            require(call_name not in FORBIDDEN_CALLS, f"forbidden active call in generator: {call_name}")
            require(not call_name.endswith(".rglob"), "forbidden rglob call in generator")
            require(not call_name.endswith(".walk"), "forbidden walk call in generator")


def check_demo(generator) -> None:
    stdout = io.StringIO()
    stderr = io.StringIO()
    code = generator.main(["--demo"], stdout=stdout, stderr=stderr)
    output = stdout.getvalue()
    require(code == 0, f"demo returned nonzero: {stderr.getvalue()}")
    for needle in [
        "UNTRUSTED_RESEARCH_NOTE",
        "RESEARCH_NOT_MEMORY",
        "NOT_TRUSTED_MEMORY",
        "HUMAN_REVIEW_REQUIRED_FOR_MEMORY",
        "no automation triggered",
    ]:
        require(needle in output, f"demo output missing: {needle}")


def check_dry_run(generator) -> None:
    payload = json.loads(TOPIC_LIBRARY_PATH.read_text(encoding="utf-8"))
    topic_id = payload["topics"][0]["topic_id"]
    before = sorted(path.name for path in OUTPUT_DIR.iterdir())
    stdout = io.StringIO()
    stderr = io.StringIO()
    code = generator.main(
        [
            "--topic-id",
            topic_id,
            "--source",
            "memory\\ENGEL_SELF_RESEARCH_CONTRACT_V1.md",
            "--dry-run",
        ],
        stdout=stdout,
        stderr=stderr,
    )
    after = sorted(path.name for path in OUTPUT_DIR.iterdir())
    output = stdout.getvalue()
    require(code == 0, f"dry-run returned nonzero: {stderr.getvalue()}")
    require(before == after, "dry-run wrote or removed files in reports\\self_research_notes")
    for needle in REQUIRED_NOTE_LABELS:
        require(needle in output, f"dry-run output missing note label: {needle}")
    require("memory\\ENGEL_SELF_RESEARCH_CONTRACT_V1.md" in output, "dry-run output missing explicit source reference")


def check_unsafe_rejections(generator) -> None:
    unsafe_sources = [
        "https://example.com/file.md",
        "G:\\ENGEL_APP_MEMORY\\example.md",
        "E:\\ENGEL_APP_MEMORY\\example.md",
        "..\\outside.md",
        "memory\\*.md",
        "live\\app\\Engel.exe",
    ]
    for source in unsafe_sources:
        try:
            generator.validate_source_path(source)
        except generator.ResearchNoteError:
            continue
        raise CheckFailure(f"unsafe source was not rejected: {source}")


def check_usage_no_auto_run(generator) -> None:
    stdout = io.StringIO()
    stderr = io.StringIO()
    code = generator.main([], stdout=stdout, stderr=stderr)
    output = stdout.getvalue()
    require(code == 0, "no-argument usage should return zero")
    require("--demo" in output and "--topic-id" in output, "usage output missing safe CLI options")
    require("No scan" in output or "No scan".lower() in output.lower(), "usage output missing no-scan boundary")


def main() -> int:
    try:
        check_required_files()
        check_required_text()
        check_ast_forbidden_behavior()
        generator = load_generator_module()
        check_usage_no_auto_run(generator)
        check_demo(generator)
        check_dry_run(generator)
        check_unsafe_rejections(generator)
    except CheckFailure as exc:
        print(f"FAIL: {exc}")
        return 1
    print("PASS: Engel Untrusted Research Note Generator V1 verifier")
    print("- generator source exists and uses required statuses, labels, fields, CLI options, and source restrictions")
    print("- demo and dry-run produce untrusted notes without writing files")
    print("- unsafe URL, external drive, outside-project, wildcard, and live\\app paths are rejected")
    print("- no active browser/network/provider/download/indexing/training/source-mutation/trusted-memory behavior is enabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
