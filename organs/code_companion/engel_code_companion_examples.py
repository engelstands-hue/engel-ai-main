from __future__ import annotations

import ast
import py_compile
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path


ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
APPROVAL_TOKEN = "APPROVE_INSTALL"
SUPPORTED_LANGUAGES = {"python", "java", "html"}

LANGUAGE_EXTENSIONS = {
    "python": (".py",),
    "java": (".java",),
    "html": (".html", ".css", ".js"),
}

LANGUAGE_FOLDERS = {
    "python": "python",
    "java": "java",
    "html": "html",
}

UNSAFE_CONTENT_PATTERNS = (
    "os.system",
    "subprocess",
    "Popen",
    "shell=True",
    "requests",
    "socket",
    "http://",
    "https://",
    "Start-Process",
    "taskkill",
    "shutil.rmtree",
    "unlink(",
    "remove(",
    "while True",
    "Runtime.getRuntime",
    "ProcessBuilder",
    "java.net.Socket",
    "fetch(",
    "XMLHttpRequest",
    "eval(",
    "document.cookie",
)

UNSAFE_REGEX_PATTERNS = (
    re.compile(r"localStorage\s*.*\b(secret|token|password|api[_-]?key)\b", re.IGNORECASE),
    re.compile(r"\b(password|token|api[_-]?key|secret)\b.*\b(exfiltrate|steal|send|upload)\b", re.IGNORECASE),
)


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    status: str
    message: str
    details: tuple[str, ...] = ()


@dataclass(frozen=True)
class DependencyPlan:
    dependencies_detected: list[str] = field(default_factory=list)
    install_supported: bool = False
    approval_required: bool = False
    approval_token: str = APPROVAL_TOKEN
    install_command_preview: str = ""
    install_status: str = "NOT_RUN"
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ScriptBuildResult:
    language: str
    filename: str
    content: str
    status: str
    safety_notes: list[str]
    dependency_plan: DependencyPlan
    not_runtime: bool = True
    not_applied: bool = True


def normalize_language(language: str) -> str:
    normalized = str(language or "").strip().lower()
    aliases = {
        "py": "python",
        "python3": "python",
        "java": "java",
        "html5": "html",
        "web": "html",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in SUPPORTED_LANGUAGES:
        raise ValueError("Unsupported language. Use Python, Java, or HTML.")
    return normalized


def examples_root() -> Path:
    return ROOT / "examples" / "code_companion"


def language_root(language: str) -> Path:
    return examples_root() / LANGUAGE_FOLDERS[normalize_language(language)]


def _resolve_without_existing(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _slug_words(value: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9]+", str(value or ""))


def _safe_slug(value: str, fallback: str = "engel_example") -> str:
    words = _slug_words(value)
    if not words:
        return fallback
    return "_".join(word.lower() for word in words)[:80] or fallback


def _java_class_name(value: str) -> str:
    words = _slug_words(Path(str(value or "")).stem)
    if not words:
        words = ["Hello", "Engel", "Example"]
    class_name = "".join(word[:1].upper() + word[1:] for word in words)
    class_name = re.sub(r"[^A-Za-z0-9]", "", class_name)
    if not class_name or not class_name[0].isalpha():
        class_name = "Engel" + class_name
    return class_name[:80]


def safe_script_name(name: str, language: str) -> str:
    lang = normalize_language(language)
    original = str(name or "").strip()
    if lang == "java":
        return _java_class_name(original) + ".java"
    if lang == "python":
        return _safe_slug(Path(original).stem if original else original, "hello_engel_example") + ".py"
    return _safe_slug(Path(original).stem if original else original, "hello_engel_example") + ".html"


def example_path_for_name(name: str, language: str) -> Path:
    lang = normalize_language(language)
    filename = safe_script_name(name, lang)
    return language_root(lang) / filename


def is_safe_example_path(path: Path, language: str) -> bool:
    lang = normalize_language(language)
    root = _resolve_without_existing(language_root(lang))
    candidate = _resolve_without_existing(path)
    if not _is_relative_to(candidate, root):
        return False
    if candidate.name in {"", ".", ".."}:
        return False
    if any(part in {"..", ""} for part in candidate.relative_to(root).parts):
        return False
    suffix = candidate.suffix.lower()
    return suffix in LANGUAGE_EXTENSIONS[lang]


def _required_header(language: str) -> str:
    lang = normalize_language(language)
    if lang == "python":
        return (
            "# Engel Code Companion Example\n"
            "# Status: EXAMPLE_ONLY / NOT_RUNTIME / NOT_APPLIED\n"
            "# Authority: Josh > Guardian > Engel/runtime"
        )
    if lang == "java":
        return (
            "// Engel Code Companion Example\n"
            "// Status: EXAMPLE_ONLY / NOT_RUNTIME / NOT_APPLIED\n"
            "// Authority: Josh > Guardian > Engel/runtime"
        )
    return (
        "<!-- Engel Code Companion Example -->\n"
        "<!-- Status: EXAMPLE_ONLY / NOT_RUNTIME / NOT_APPLIED -->\n"
        "<!-- Authority: Josh > Guardian > Engel/runtime -->"
    )


def _unsafe_hits(content: str) -> list[str]:
    text = str(content or "")
    lowered = text.lower()
    hits = [pattern for pattern in UNSAFE_CONTENT_PATTERNS if pattern.lower() in lowered]
    hits.extend(regex.pattern for regex in UNSAFE_REGEX_PATTERNS if regex.search(text))
    return sorted(set(hits))


def _prompt_mentions(prompt: str, *needles: str) -> bool:
    lowered = str(prompt or "").lower()
    return any(needle.lower() in lowered for needle in needles)


def _python_content(prompt: str) -> str:
    if _prompt_mentions(prompt, "dashboard", "table", "status"):
        body = (
            "def build_status_rows():\n"
            "    return [\n"
            "        (\"Mode\", \"example only\"),\n"
            "        (\"Runtime\", \"not applied\"),\n"
            "        (\"Authority\", \"Josh > Guardian > Engel/runtime\"),\n"
            "    ]\n\n"
            "def main():\n"
            "    for label, value in build_status_rows():\n"
            "        print(f\"{label}: {value}\")\n"
        )
    else:
        body = (
            "def main():\n"
            "    message = \"Hello from Engel Code Companion.\"\n"
            "    status = \"EXAMPLE_ONLY / NOT_RUNTIME / NOT_APPLIED\"\n"
            "    print(message)\n"
            "    print(status)\n"
        )
    return _required_header("python") + "\n\n" + body + "\nif __name__ == \"__main__\":\n    main()\n"


def _java_content(prompt: str, class_name: str) -> str:
    if _prompt_mentions(prompt, "class", "hello", "example"):
        message = "Hello from Engel Code Companion."
    else:
        message = "Engel Java example created safely."
    return (
        _required_header("java")
        + "\n\n"
        + f"public class {class_name} {{\n"
        + "    public static void main(String[] args) {\n"
        + f"        System.out.println(\"{message}\");\n"
        + "        System.out.println(\"EXAMPLE_ONLY / NOT_RUNTIME / NOT_APPLIED\");\n"
        + "    }\n"
        + "}\n"
    )


def _html_content(prompt: str) -> str:
    title = "Hello Engel Dashboard" if _prompt_mentions(prompt, "dashboard") else "Hello Engel Example"
    return (
        _required_header("html")
        + "\n<!doctype html>\n"
        + "<html lang=\"en\">\n"
        + "<head>\n"
        + "  <meta charset=\"utf-8\">\n"
        + "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        + f"  <title>{title}</title>\n"
        + "  <style>\n"
        + "    body { font-family: Segoe UI, Arial, sans-serif; margin: 2rem; background: #0b1517; color: #eefbf4; }\n"
        + "    main { max-width: 780px; }\n"
        + "    .badge { display: inline-block; margin: .25rem .4rem .25rem 0; padding: .35rem .55rem; border: 1px solid #77e6d1; }\n"
        + "  </style>\n"
        + "</head>\n"
        + "<body>\n"
        + "  <main>\n"
        + "    <h1>Hello Engel</h1>\n"
        + "    <p>This page was created as a local Code Companion example.</p>\n"
        + "    <p><span class=\"badge\">EXAMPLE ONLY</span><span class=\"badge\">NOT RUNTIME</span><span class=\"badge\">NOT APPLIED</span></p>\n"
        + "  </main>\n"
        + "</body>\n"
        + "</html>\n"
    )


def detect_dependency_needs(language: str, prompt: str, content: str) -> DependencyPlan:
    lang = normalize_language(language)
    text = (str(prompt or "") + "\n" + str(content or "")).lower()
    detected: list[str] = []
    if lang == "python":
        for package in ("requests", "flask", "django", "fastapi", "pandas", "numpy", "pygame"):
            if package in text and package not in detected:
                detected.append(package)
    elif lang == "java":
        if any(term in text for term in ("jdk", "javac", "maven", "gradle", "spring")):
            detected.append("java toolchain")
    elif lang == "html":
        if any(term in text for term in ("cdn", "bootstrap", "tailwind", "react", "vue", "external")):
            detected.append("blocked remote html dependency")

    if not detected:
        return DependencyPlan(notes=["No external dependency request detected."])

    if lang == "python":
        return DependencyPlan(
            dependencies_detected=detected,
            install_supported=False,
            approval_required=True,
            approval_token=APPROVAL_TOKEN,
            install_command_preview="python -m pip install " + " ".join(detected),
            install_status="REQUIRES_APPROVAL",
            notes=[
                "No install was run.",
                "Code Companion does not auto-install packages.",
                "Use a separate Josh-approved dependency task or existing guarded install route before enabling package use.",
            ],
        )
    if lang == "java":
        return DependencyPlan(
            dependencies_detected=detected,
            install_supported=False,
            approval_required=True,
            approval_token=APPROVAL_TOKEN,
            install_command_preview="JDK/toolchain installer requires a separate Josh-approved task.",
            install_status="BLOCKED",
            notes=["Java system/toolchain installs are proposal-only in Code Companion."],
        )
    return DependencyPlan(
        dependencies_detected=detected,
        install_supported=False,
        approval_required=True,
        approval_token=APPROVAL_TOKEN,
        install_command_preview="Remote HTML dependencies are blocked; use inline/local assets under examples/code_companion/html.",
        install_status="BLOCKED",
        notes=["HTML examples are local-only by default and do not fetch remote resources."],
    )


def build_script_from_prompt(language: str, prompt: str, name: str) -> ScriptBuildResult:
    lang = normalize_language(language)
    filename = safe_script_name(name, lang)
    if lang == "python":
        content = _python_content(prompt)
    elif lang == "java":
        content = _java_content(prompt, Path(filename).stem)
    else:
        content = _html_content(prompt)

    validation = validate_script_content(lang, content)
    dependency_plan = detect_dependency_needs(lang, prompt, content)
    status = "READY_TO_SAVE" if validation.ok else validation.status
    notes = [
        "Example-only file target under examples/code_companion.",
        "Not runtime.",
        "Not applied to Engel.",
        "Runtime source edits remain blocked.",
    ]
    if dependency_plan.dependencies_detected:
        notes.append("Dependency request detected; install requires explicit approval and is not run automatically.")
    return ScriptBuildResult(lang, filename, content, status, notes, dependency_plan)


def validate_script_content(language: str, content: str) -> ValidationResult:
    lang = normalize_language(language)
    text = str(content or "")
    if _required_header(lang) not in text:
        return ValidationResult(False, "MISSING_HEADER", "Generated file header is missing.")
    hits = _unsafe_hits(text)
    if hits:
        return ValidationResult(False, "UNSAFE_CONTENT_BLOCKED", "Unsafe generated content pattern found.", tuple(hits))
    if "EXAMPLE_ONLY / NOT_RUNTIME / NOT_APPLIED" not in text:
        return ValidationResult(False, "MISSING_EXAMPLE_BOUNDARY", "Example-only boundary is missing.")

    if lang == "python":
        try:
            ast.parse(text)
        except SyntaxError as exc:
            return ValidationResult(False, "PYTHON_AST_FAILED", str(exc))
        return ValidationResult(True, "PYTHON_AST_OK", "Python AST parse passed.")

    if lang == "java":
        class_matches = re.findall(r"\bpublic\s+class\s+([A-Za-z][A-Za-z0-9_]*)\b", text)
        if len(class_matches) != 1:
            return ValidationResult(False, "JAVA_CLASS_MISMATCH", "Java example must contain exactly one public class.")
        if "public static void main(String[] args)" not in text:
            return ValidationResult(False, "JAVA_MAIN_MISSING", "Java example main method is missing.")
        if text.count("{") != text.count("}"):
            return ValidationResult(False, "JAVA_BRACE_MISMATCH", "Java braces are not balanced.")
        return ValidationResult(True, "JAVA_BASIC_STRUCTURE_OK", "Java basic structure passed.")

    lowered = text.lower()
    required = ("<!doctype html>", "<html", "<head", "<body")
    missing = [item for item in required if item not in lowered]
    if missing:
        return ValidationResult(False, "HTML_STRUCTURE_FAILED", "HTML structure is missing required tags.", tuple(missing))
    return ValidationResult(True, "HTML_BASIC_STRUCTURE_OK", "HTML basic structure passed.")


def save_script(language: str, name: str, content: str) -> Path:
    lang = normalize_language(language)
    path = example_path_for_name(name, lang)
    if not is_safe_example_path(path, lang):
        raise ValueError("Refusing to write outside examples/code_companion.")
    validation = validate_script_content(lang, content)
    if not validation.ok:
        detail = ", ".join(validation.details) if validation.details else validation.message
        raise ValueError(f"Refusing to save unsafe or invalid example: {validation.status} - {detail}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def compile_or_validate_example(path: Path, language: str) -> ValidationResult:
    lang = normalize_language(language)
    candidate = _resolve_without_existing(Path(path))
    if not is_safe_example_path(candidate, lang):
        return ValidationResult(False, "UNSAFE_PATH_BLOCKED", "Example path is outside the approved language root.")
    if not candidate.exists() or not candidate.is_file():
        return ValidationResult(False, "EXAMPLE_MISSING", "Example file does not exist.")
    try:
        content = candidate.read_text(encoding="utf-8")
    except OSError as exc:
        return ValidationResult(False, "READ_FAILED", str(exc))
    validation = validate_script_content(lang, content)
    if not validation.ok:
        return validation

    if lang == "python":
        compile_path = candidate.with_name(candidate.stem + "_compile_check.pyc")
        try:
            py_compile.compile(str(candidate), cfile=str(compile_path), doraise=True)
        except py_compile.PyCompileError as exc:
            return ValidationResult(False, "PY_COMPILE_FAILED", str(exc))
        finally:
            try:
                compile_path.unlink(missing_ok=True)
            except OSError:
                pass
        return ValidationResult(True, "PY_COMPILE_OK", "Python ast.parse and py_compile passed.")

    if lang == "java":
        javac = shutil.which("javac")
        if javac:
            return ValidationResult(
                True,
                "JAVA_COMPILE_NOT_RUN",
                "javac was found, but Code Companion does not invoke external compilers in this bounded task.",
                (str(javac),),
            )
        return ValidationResult(
            True,
            "JAVA_COMPILE_NOT_RUN",
            "javac not verified; Java example saved as standard-library source only.",
        )

    return ValidationResult(True, "HTML_BASIC_STRUCTURE_OK", "HTML basic structure validated; browser was not opened.")


def render_dependency_plan(plan: DependencyPlan) -> str:
    deps = ", ".join(plan.dependencies_detected) if plan.dependencies_detected else "none"
    notes = "\n".join("- " + note for note in plan.notes) if plan.notes else "- none"
    return "\n".join(
        [
            "# Dependency Plan",
            "Status: " + plan.install_status,
            "Dependencies detected: " + deps,
            "Install supported here: " + str(plan.install_supported),
            "Approval required: " + str(plan.approval_required),
            "Approval token: " + plan.approval_token,
            "Install command preview: " + (plan.install_command_preview or "none"),
            "",
            "Notes:",
            notes,
            "",
            "No dependency install was run automatically.",
        ]
    )
