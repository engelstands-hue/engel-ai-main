from __future__ import annotations

import ast
import datetime
import py_compile
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
LESSONS_ROOT = ROOT / "lessons"
PYTHON_LESSONS_ROOT = LESSONS_ROOT / "python"
REPORTS_ROOT = ROOT / "reports" / "codex_bridge"
APPROVED_PROJECTS_ROOT = ROOT / "workspace" / "approved_projects"
APPROVAL_TOKEN = "APPROVE_RUN"
LOCAL_RESOURCE_SUFFIXES = {".pdf", ".txt", ".md", ".zip"}

UNSAFE_LESSON_PATTERNS = [
    "os.system",
    "subprocess",
    "popen",
    "shell=true",
    "requests",
    "socket",
    "http://",
    "https://",
    "shutil.rmtree",
    "remove(",
    "unlink(",
    "while true",
    "start-process",
    "taskkill",
]

TOPIC_OVERRIDES = {
    "pathlib": "pathlib",
    "json": "json",
    "classes": "classes",
    "functions": "functions",
    "decorators": "decorators",
    "async": "async",
    "testing": "testing",
}

LEARNING_PATH_TOPICS = [
    "variables",
    "strings",
    "numbers",
    "lists dicts sets tuples",
    "functions",
    "classes",
    "modules imports",
    "pathlib",
    "json",
    "exceptions",
    "testing",
    "type hints",
    "dataclasses",
    "decorators",
    "generators",
    "context managers",
    "file i/o",
    "gui basics",
    "pyside pyqt concepts",
    "packaging concepts",
    "subprocess concepts theory",
    "async concepts safe practice",
    "security sandboxing concepts",
    "engel architecture",
    "numpy pandas xarray",
    "cython and numba",
    "profiling bottlenecks",
    "jax optimization basics",
    "multithreading multiprocessing async",
    "concurrency deadlocks and safety",
    "design patterns in python",
    "subprocess timeout guards and process groups",
    "json protocol parsing and robust decoding",
    "pathlib and workspace-safe file guards",
    "dependency boundary checks and architecture hygiene",
    "benchmarking profiling and budget checks",
    "socket debug protocol concepts theory",
    "defensive test scripts and injection safety",
]

BOOK_CURRICULUM_HINTS = (
    (
        ("numpy", "pandas", "xarray"),
        "- Book-aligned advanced track: numerical/scientific data workflows with NumPy, pandas, and Xarray.",
    ),
    (
        ("cython", "numba"),
        "- Book-aligned advanced track: acceleration with Cython/Numba for native-like performance.",
    ),
    (
        ("profile", "profiler", "bottleneck"),
        "- Book-aligned advanced track: bottleneck analysis and profiling-first optimization.",
    ),
    (
        ("jax",),
        "- Book-aligned advanced track: JAX-based model optimization and compiled numerical pipelines.",
    ),
    (
        ("thread", "process", "async", "concurr"),
        "- Book-aligned advanced track: multithreading, multiprocessing, async design, and concurrency trade-offs.",
    ),
    (
        ("deadlock", "lock"),
        "- Book-aligned advanced track: deadlock patterns, prevention, and safe synchronization.",
    ),
    (
        ("design pattern", "architecture"),
        "- Book-aligned advanced track: Python design patterns for robust architecture decisions.",
    ),
    (
        ("timeout", "process group", "sigterm", "sigkill"),
        "- JCode-inspired operations track: subprocess timeout handling, process-group shutdown, and safe termination escalation.",
    ),
    (
        ("json protocol", "json decode", "socket message"),
        "- JCode-inspired reliability track: robust JSON message parsing and defensive protocol decoding patterns.",
    ),
    (
        ("dependency boundary", "boundary check", "architecture hygiene"),
        "- JCode-inspired architecture track: lightweight dependency-boundary checks to keep contracts isolated from runtime-heavy modules.",
    ),
    (
        ("benchmark", "budget", "profile"),
        "- JCode-inspired performance track: profiling, startup/runtime benchmarking, and budget-guard scripting for regressions.",
    ),
    (
        ("injection test", "tool result order", "soft interrupt"),
        "- JCode-inspired safety track: deterministic test strategies for injection safety and message-order contracts.",
    ),
)


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    message: str
    path: Path | None = None


def _ensure_roots() -> None:
    LESSONS_ROOT.mkdir(parents=True, exist_ok=True)
    PYTHON_LESSONS_ROOT.mkdir(parents=True, exist_ok=True)
    REPORTS_ROOT.mkdir(parents=True, exist_ok=True)


def _is_url_or_unc(text: str) -> bool:
    lower = str(text or "").strip().lower()
    return lower.startswith(("http://", "https://", "\\\\"))


def _normalize_input_path(path_text: str) -> Path:
    raw = str(path_text or "").strip().strip('"').strip("'")
    if not raw:
        return ROOT
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    return candidate.resolve()


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root.resolve())
        return True
    except Exception:
        return False


def _format_bytes(size: int) -> str:
    value = float(max(0, int(size)))
    for unit in ["bytes", "KB", "MB", "GB"]:
        if value < 1024 or unit == "GB":
            if unit == "bytes":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def _local_python_resource_records(limit: int = 12) -> list[tuple[str, str]]:
    if not APPROVED_PROJECTS_ROOT.exists() or not APPROVED_PROJECTS_ROOT.is_dir():
        return []
    records: list[tuple[str, str]] = []
    for path in sorted(APPROVED_PROJECTS_ROOT.iterdir(), key=lambda p: p.name.lower()):
        if not path.is_file() or path.suffix.lower() not in LOCAL_RESOURCE_SUFFIXES:
            continue
        name = path.name
        lower = name.lower()
        if "python" not in lower and "py" not in lower and "quantecon" not in lower and "fluent" not in lower:
            continue
        try:
            size = _format_bytes(path.stat().st_size)
        except OSError:
            size = "unknown size"
        records.append((name, size))
        if len(records) >= limit:
            break
    return records


def _local_resource_lines(limit: int = 12) -> list[str]:
    records = _local_python_resource_records(limit=limit)
    if not records:
        return ["- none found under workspace\\approved_projects"]
    return [f"- {name} ({size})" for name, size in records]


def _topic_resource_lines(topic: str, limit: int = 5) -> list[str]:
    topic_words = [
        word
        for word in sanitize_lesson_topic(topic).split("_")
        if len(word) >= 3 and word not in {"and", "the", "for", "with"}
    ]
    records = _local_python_resource_records(limit=40)
    if not records:
        return ["- Local resource note: no approved Python resources found under workspace\\approved_projects."]
    matched = [
        (name, size)
        for name, size in records
        if any(word in name.lower() for word in topic_words)
    ]
    if not matched:
        matched = records[:limit]
    return [f"- Local approved resource: {name} ({size})" for name, size in matched[:limit]]


def sanitize_lesson_topic(topic: str) -> str:
    raw = str(topic or "").strip().lower()
    raw = raw.replace("-", "_")
    raw = re.sub(r"[^a-z0-9_ ]+", "", raw)
    raw = "_".join(part for part in raw.split() if part)
    raw = raw[:64].strip("_")
    if not raw:
        return "python_topic"
    return TOPIC_OVERRIDES.get(raw, raw)


def lesson_path_for_topic(topic: str) -> Path:
    _ensure_roots()
    slug = sanitize_lesson_topic(topic)
    return PYTHON_LESSONS_ROOT / f"{slug}_lesson.md"


def _practice_path_for_topic(topic: str) -> Path:
    _ensure_roots()
    slug = sanitize_lesson_topic(topic)
    return PYTHON_LESSONS_ROOT / f"{slug}_practice.py"


def build_python_teaching_status() -> str:
    _ensure_roots()
    return "\n".join(
        [
            "# Python Teaching Mode Status",
            "",
            "Python Teaching Mode: ENABLED",
            "Scope: beginner_to_advanced",
            "Lesson write: enabled (bounded to lessons and lessons\\python)",
            "Practice write: enabled (bounded to lessons\\python)",
            "Lesson run: enabled only for approved lessons\\python files with APPROVE_RUN",
            "py_compile: enabled for lessons\\python files",
            "Verifier execution: enabled",
            "",
            "Connected local Python resources:",
            *_local_resource_lines(),
            "",
            "Blocked behavior remains blocked:",
            "- No arbitrary shell execution",
            "- No autonomous execution or background loops",
            "- No model-command execution",
            "- No provider/API/network behavior",
            "- No package/system install route changes",
            "- No trusted-memory writes without explicit approval",
            "- No source edits without explicit approval",
            "",
            "Safety wording:",
            "Python Teaching Mode means Engel can learn and teach Python.",
            "It does not mean Engel can run arbitrary code or act autonomously.",
        ]
    )


def build_python_lesson_help() -> str:
    return "\n".join(
        [
            "# Python Lesson Help",
            "",
            "Available deterministic commands:",
            "- python teaching mode status",
            "- python lesson help",
            "- create python lesson <topic>",
            "- create python practice <topic>",
            "- python concept <topic>",
            "- explain python file <path>",
            "- compile python lesson <lesson_file.py>",
            "- run python lesson <lesson_file.py> APPROVE_RUN",
            "",
            "Safety:",
            "- Lesson/practice scripts are bounded to lessons\\python.",
            "- Running lessons requires APPROVE_RUN and unsafe-pattern checks.",
            "- Explaining files is read-only.",
        ]
    )


def _lesson_markdown(topic: str, slug: str, practice_name: str) -> str:
    return "\n".join(
        [
            f"# Python Lesson: {topic.strip() or slug}",
            "",
            "Status: DRAFT",
            "Mode: deterministic local teaching",
            "",
            "## Learning Goals",
            "- Understand the core idea.",
            "- Practice with safe local examples.",
            "- Build from beginner to advanced use.",
            "",
            "## Concept",
            f"- Topic key: `{slug}`",
            "- Explain the concept in plain language.",
            "- Show how it connects to real Engel Python modules.",
            "",
            "## Safe Practice",
            f"- Practice script: `{practice_name}`",
            "- Keep practice local and deterministic.",
            "- Avoid network, shell, and destructive file operations.",
            "",
            "## Next Step",
            f"- Run: `compile python lesson {str(PYTHON_LESSONS_ROOT / practice_name)}`",
            f"- Run: `run python lesson {str(PYTHON_LESSONS_ROOT / practice_name)} APPROVE_RUN`",
        ]
    )


def _practice_script(topic: str, slug: str) -> str:
    banner = topic.strip() or slug.replace("_", " ")
    return "\n".join(
        [
            '"""',
            f"Safe Python practice for: {banner}",
            "Bounded local lesson script for Engel Python Teaching Mode.",
            '"""',
            "",
            "from pathlib import Path",
            "import json",
            "",
            "",
            "def main() -> None:",
            f"    topic = {banner!r}",
            "    lesson_root = Path(__file__).resolve().parent",
            "    sample = {",
            '        "topic": topic,',
            '        "files_in_lesson_root": len(list(lesson_root.glob("*"))),',
            '        "message": "Practice completed safely.",',
            "    }",
            "    print(json.dumps(sample, indent=2))",
            "",
            "",
            'if __name__ == "__main__":',
            "    main()",
            "",
        ]
    )


def create_python_lesson(topic: str) -> str:
    _ensure_roots()
    slug = sanitize_lesson_topic(topic)
    lesson_path = lesson_path_for_topic(slug)
    practice_path = _practice_path_for_topic(slug)
    lesson_path.write_text(_lesson_markdown(topic, slug, practice_path.name), encoding="utf-8")
    if not practice_path.exists():
        practice_path.write_text(_practice_script(topic, slug), encoding="utf-8")
    return "\n".join(
        [
            "# Python Lesson Created",
            "",
            f"Topic: {topic.strip() or slug}",
            f"Lesson file: {lesson_path}",
            f"Practice file: {practice_path}",
            "",
            "Safety:",
            "- Files were written only under lessons\\python.",
            "- No shell/network/provider behavior was used.",
        ]
    )


def create_python_practice(topic: str) -> str:
    _ensure_roots()
    slug = sanitize_lesson_topic(topic)
    practice_path = _practice_path_for_topic(slug)
    practice_path.write_text(_practice_script(topic, slug), encoding="utf-8")
    return "\n".join(
        [
            "# Python Practice Created",
            "",
            f"Topic: {topic.strip() or slug}",
            f"Practice file: {practice_path}",
            "",
            "Safety:",
            "- Practice script is bounded to lessons\\python.",
            "- Script template excludes shell/network/destructive patterns.",
        ]
    )


def _validate_python_file_for_explain(path_text: str) -> ValidationResult:
    if _is_url_or_unc(path_text):
        return ValidationResult(False, "Path is blocked: URL and UNC paths are not allowed.")
    path = _normalize_input_path(path_text)
    if not path.exists() or not path.is_file():
        return ValidationResult(False, f"File not found: {path}")
    if path.suffix.lower() != ".py":
        return ValidationResult(False, "Explain route supports .py files only.")
    if not _is_under(path, ROOT):
        return ValidationResult(False, "File must remain under the Engel workspace root.")
    return ValidationResult(True, "ok", path)


def explain_python_file(path: str) -> str:
    validation = _validate_python_file_for_explain(path)
    if not validation.ok or validation.path is None:
        return "# Explain Python File Blocked\n\n" + validation.message
    source = validation.path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(source)
    except Exception as exc:
        return "\n".join(
            [
                "# Explain Python File",
                "",
                f"File: {validation.path}",
                "Parse status: FAILED",
                f"Reason: {exc}",
                "",
                "Safety:",
                "- Read-only explanation route.",
                "- No execution was performed.",
            ]
        )

    imports: list[str] = []
    classes: list[str] = []
    functions: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            imports.append(mod if mod else "<relative>")
        elif isinstance(node, ast.ClassDef):
            classes.append(node.name)
        elif isinstance(node, ast.FunctionDef):
            functions.append(node.name)

    summary_lines = [
        "# Python File Explanation",
        "",
        f"File: {validation.path}",
        f"Total lines: {len(source.splitlines())}",
        f"Imports: {len(imports)}",
        f"Classes: {len(classes)}",
        f"Functions: {len(functions)}",
        "",
        "## Imports",
    ]
    summary_lines.extend([f"- {name}" for name in imports[:20]] or ["- none"])
    summary_lines.extend(["", "## Classes"])
    summary_lines.extend([f"- {name}" for name in classes[:20]] or ["- none"])
    summary_lines.extend(["", "## Functions"])
    summary_lines.extend([f"- {name}" for name in functions[:40]] or ["- none"])
    summary_lines.extend(
        [
            "",
            "Safety:",
            "- Read-only explanation route.",
            "- No file writes and no code execution.",
        ]
    )
    return "\n".join(summary_lines)


def _validate_lesson_path(path_text: str) -> ValidationResult:
    if _is_url_or_unc(path_text):
        return ValidationResult(False, "Path is blocked: URL and UNC paths are not allowed.")
    path = _normalize_input_path(path_text)
    if not path.exists() or not path.is_file():
        return ValidationResult(False, f"Lesson file not found: {path}")
    if path.suffix.lower() != ".py":
        return ValidationResult(False, "Lesson file must be a .py script.")
    if not _is_under(path, PYTHON_LESSONS_ROOT):
        return ValidationResult(False, "Lesson path is blocked: file must stay under lessons\\python.")
    return ValidationResult(True, "ok", path)


def _unsafe_matches(source: str) -> list[str]:
    lowered = source.lower()
    normalized = re.sub(r"\s+", " ", lowered)
    matches = [pattern for pattern in UNSAFE_LESSON_PATTERNS if pattern in normalized]
    return sorted(set(matches))


def compile_python_lesson(path: str) -> str:
    validation = _validate_lesson_path(path)
    if not validation.ok or validation.path is None:
        return "# Compile Python Lesson Blocked\n\n" + validation.message
    try:
        py_compile.compile(str(validation.path), doraise=True)
    except Exception as exc:
        return "\n".join(
            [
                "# Compile Python Lesson Failed",
                "",
                f"Lesson file: {validation.path}",
                f"Error: {exc}",
                "",
                "Safety:",
                "- Compile checks syntax only.",
                "- No execution was performed.",
            ]
        )
    return "\n".join(
        [
            "# Compile Python Lesson",
            "",
            f"Lesson file: {validation.path}",
            "Result: PASS",
            "",
            "Safety:",
            "- py_compile route only.",
            "- No script execution was performed.",
        ]
    )


def run_python_lesson(path: str, approval_token: str) -> str:
    if str(approval_token or "").strip() != APPROVAL_TOKEN:
        return "\n".join(
            [
                "# Run Python Lesson Blocked",
                "",
                f"Missing required approval token: {APPROVAL_TOKEN}",
            ]
        )

    validation = _validate_lesson_path(path)
    if not validation.ok or validation.path is None:
        return "# Run Python Lesson Blocked\n\n" + validation.message

    source = validation.path.read_text(encoding="utf-8", errors="replace")
    matches = _unsafe_matches(source)
    if matches:
        return "\n".join(
            [
                "# Run Python Lesson Blocked",
                "",
                f"Lesson file: {validation.path}",
                "Unsafe patterns detected:",
                *[f"- {match}" for match in matches],
                "",
                "Safety:",
                "- Lesson run is blocked when unsafe patterns are present.",
            ]
        )

    try:
        completed = subprocess.run(
            [sys.executable, str(validation.path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
            shell=False,
            cwd=str(PYTHON_LESSONS_ROOT),
        )
    except subprocess.TimeoutExpired:
        return "\n".join(
            [
                "# Run Python Lesson Blocked",
                "",
                f"Lesson file: {validation.path}",
                "Execution timed out.",
                "",
                "Safety:",
                "- Timeout guard prevents uncontrolled runs.",
            ]
        )

    stdout = (completed.stdout or "").strip()
    stderr = (completed.stderr or "").strip()
    lines = [
        "# Run Python Lesson",
        "",
        f"Lesson file: {validation.path}",
        f"Exit code: {completed.returncode}",
        "",
        "Stdout:",
        stdout if stdout else "[no stdout]",
        "",
        "Stderr:",
        stderr if stderr else "[no stderr]",
        "",
        "Safety:",
        "- Deterministic subprocess.run with shell=False.",
        "- Path bounded to lessons\\python and approval-token gated.",
    ]
    return "\n".join(lines)


def python_concept(topic: str) -> str:
    key = sanitize_lesson_topic(topic).replace("_", " ")
    topic_text = (topic or key).lower()
    curriculum_lines = []
    for keywords, line in BOOK_CURRICULUM_HINTS:
        if any(word in topic_text for word in keywords):
            curriculum_lines.append(line)
    if not curriculum_lines:
        curriculum_lines.append(
            "- Curriculum note: beginner-to-advanced progression includes scientific computing, optimization, concurrency, and operational reliability scripting tracks."
        )
    return "\n".join(
        [
            f"# Python Concept: {topic.strip() or key}",
            "",
            "Teaching scope: beginner to advanced",
            "",
            "Core explanation:",
            f"- `{topic.strip() or key}` is taught in local deterministic teaching mode.",
            "- Start with syntax and mental model, then move to real design trade-offs.",
            "- Connect examples to Engel modules (routing, validation, reports, and guards).",
            "- Unsafe execution topics are theory-only unless an explicit approved route exists.",
            *curriculum_lines,
            "",
            "Local approved study resources:",
            *_topic_resource_lines(topic),
            "",
            "Safety:",
            "- Concept route is explanation-only.",
            "- No file write and no execution is performed.",
        ]
    )


def create_python_teaching_report(topic: str) -> str:
    _ensure_roots()
    slug = sanitize_lesson_topic(topic)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = REPORTS_ROOT / f"PYTHON_TEACHING_REPORT_{slug}_{stamp}.md"
    body = "\n".join(
        [
            "# Python Teaching Session Report",
            "",
            "Status: DRAFT",
            f"Topic: {topic.strip() or slug}",
            f"Topic key: {slug}",
            "",
            "## Scope",
            "- Beginner to advanced concept support in deterministic local mode.",
            "- Unsafe execution paths remain blocked by contract.",
            "",
            "## Suggested Session Flow",
            f"- `python concept {topic.strip() or slug}`",
            f"- `create python lesson {topic.strip() or slug}`",
            f"- `create python practice {topic.strip() or slug}`",
            "",
            "## Safety",
            "- Report-only write under reports\\codex_bridge.",
            "- No provider/network call.",
            "- No arbitrary shell execution.",
            "- No autonomous execution.",
        ]
    )
    out_path.write_text(body, encoding="utf-8")
    return "\n".join(
        [
            "# Python Teaching Report Created",
            "",
            f"Topic: {topic.strip() or slug}",
            f"Report file: {out_path}",
            "",
            "Safety:",
            "- Report written only under reports\\codex_bridge.",
            "- Deterministic route with no model/provider dependency.",
        ]
    )


def python_learning_path() -> str:
    _ensure_roots()
    lines = [
        "# Python Learning Path",
        "",
        "Mode: deterministic beginner_to_advanced roadmap",
        "Safety: learning/report-only guidance; no execution performed.",
        "",
        "## Stages",
    ]
    for idx, topic in enumerate(LEARNING_PATH_TOPICS, start=1):
        lines.append(f"{idx}. {topic}")
    lines.extend(
        [
            "",
            "## Suggested Command Rhythm",
            "- `python concept <topic>`",
            "- `create python lesson <topic>`",
            "- `create python practice <topic>`",
            "- `create python teaching report <topic>`",
            "",
            "## Example Next Three",
        ]
    )
    for topic in LEARNING_PATH_TOPICS[:3]:
        lines.append(f"- {topic}")
    lines.extend(
        [
            "",
            "## Connected Local Study Resources",
            "These are local approved-project resources by filename only; this route does not parse PDFs, unzip archives, execute code, or call providers.",
            *_local_resource_lines(limit=20),
        ]
    )
    return "\n".join(lines)


def create_python_learning_path_report() -> str:
    _ensure_roots()
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = REPORTS_ROOT / f"PYTHON_LEARNING_PATH_{stamp}.md"
    out_path.write_text(python_learning_path(), encoding="utf-8")
    return "\n".join(
        [
            "# Python Learning Path Report Created",
            "",
            f"Report file: {out_path}",
            "",
            "Safety:",
            "- Report-only write under reports\\codex_bridge.",
            "- No execution, provider/network, or autonomy behavior.",
        ]
    )
