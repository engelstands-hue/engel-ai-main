"""Engel Code Workshop — multi-language create / edit / implement surface.

A clean backend for the new Engel Code Companion GUI: real file create,
read, overwrite, run, and LLM-assisted generation across many languages.
Operates inside a single sandbox folder (``code_workspace/``) under the
app root so destructive writes can never escape into project sources.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import textwrap
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
WORKSPACE = ROOT / "code_workspace"


@dataclass(frozen=True)
class Language:
    key: str
    label: str
    extension: str
    aliases: tuple[str, ...]
    comment_prefix: str
    run_argv: tuple[str, ...] = ()
    template: str = ""


def _py_template() -> str:
    return (
        "def main() -> None:\n"
        "    print(\"Hello from Engel — Python\")\n"
        "\n\n"
        "if __name__ == \"__main__\":\n"
        "    main()\n"
    )


def _js_template() -> str:
    return (
        "function main() {\n"
        "    console.log(\"Hello from Engel — JavaScript\");\n"
        "}\n\n"
        "main();\n"
    )


def _ts_template() -> str:
    return (
        "function main(): void {\n"
        "    console.log(\"Hello from Engel — TypeScript\");\n"
        "}\n\n"
        "main();\n"
    )


def _java_template(name: str = "HelloEngel") -> str:
    return (
        f"public class {name} {{\n"
        "    public static void main(String[] args) {\n"
        "        System.out.println(\"Hello from Engel — Java\");\n"
        "    }\n"
        "}\n"
    )


def _c_template() -> str:
    return (
        "#include <stdio.h>\n\n"
        "int main(void) {\n"
        "    printf(\"Hello from Engel — C\\n\");\n"
        "    return 0;\n"
        "}\n"
    )


def _cpp_template() -> str:
    return (
        "#include <iostream>\n\n"
        "int main() {\n"
        "    std::cout << \"Hello from Engel — C++\" << std::endl;\n"
        "    return 0;\n"
        "}\n"
    )


def _csharp_template() -> str:
    return (
        "using System;\n\n"
        "class Program {\n"
        "    static void Main() {\n"
        "        Console.WriteLine(\"Hello from Engel — C#\");\n"
        "    }\n"
        "}\n"
    )


def _go_template() -> str:
    return (
        "package main\n\n"
        "import \"fmt\"\n\n"
        "func main() {\n"
        "    fmt.Println(\"Hello from Engel — Go\")\n"
        "}\n"
    )


def _rust_template() -> str:
    return (
        "fn main() {\n"
        "    println!(\"Hello from Engel — Rust\");\n"
        "}\n"
    )


def _ruby_template() -> str:
    return "puts \"Hello from Engel — Ruby\"\n"


def _php_template() -> str:
    return (
        "<?php\n"
        "echo \"Hello from Engel — PHP\" . PHP_EOL;\n"
    )


def _shell_template() -> str:
    return (
        "#!/usr/bin/env bash\n"
        "echo \"Hello from Engel — Shell\"\n"
    )


def _ps1_template() -> str:
    return "Write-Host \"Hello from Engel — PowerShell\"\n"


def _html_template() -> str:
    return (
        "<!doctype html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "  <meta charset=\"utf-8\">\n"
        "  <title>Hello Engel</title>\n"
        "  <style>\n"
        "    body { font-family: Segoe UI, Arial, sans-serif; background: #0b1517; color: #eefbf4; margin: 2rem; }\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        "  <h1>Hello from Engel — HTML</h1>\n"
        "  <p>Edit this page in the workshop.</p>\n"
        "</body>\n"
        "</html>\n"
    )


def _css_template() -> str:
    return (
        "body {\n"
        "    font-family: Segoe UI, Arial, sans-serif;\n"
        "    background: #0b1517;\n"
        "    color: #eefbf4;\n"
        "    margin: 2rem;\n"
        "}\n"
    )


def _sql_template() -> str:
    return (
        "-- Engel SQL example\n"
        "SELECT 'Hello from Engel — SQL' AS greeting;\n"
    )


def _json_template() -> str:
    return (
        "{\n"
        "  \"greeting\": \"Hello from Engel — JSON\",\n"
        "  \"made_by\": \"engel-code-workshop\"\n"
        "}\n"
    )


def _yaml_template() -> str:
    return (
        "greeting: Hello from Engel — YAML\n"
        "made_by: engel-code-workshop\n"
    )


def _md_template() -> str:
    return (
        "# Hello from Engel — Markdown\n\n"
        "This is a Markdown note. Edit it in the workshop.\n"
    )


def _lua_template() -> str:
    return "print(\"Hello from Engel — Lua\")\n"


def _kotlin_template() -> str:
    return (
        "fun main() {\n"
        "    println(\"Hello from Engel — Kotlin\")\n"
        "}\n"
    )


def _swift_template() -> str:
    return "print(\"Hello from Engel — Swift\")\n"


def _r_template() -> str:
    return "cat(\"Hello from Engel — R\\n\")\n"


LANGUAGES: tuple[Language, ...] = (
    Language("python", "Python", ".py", ("py", "python3"), "#", ("python",), _py_template()),
    Language("javascript", "JavaScript", ".js", ("js", "node"), "//", ("node",), _js_template()),
    Language("typescript", "TypeScript", ".ts", ("ts",), "//", (), _ts_template()),
    Language("java", "Java", ".java", (), "//", (), _java_template()),
    Language("c", "C", ".c", (), "//", (), _c_template()),
    Language("cpp", "C++", ".cpp", ("c++", "cxx"), "//", (), _cpp_template()),
    Language("csharp", "C#", ".cs", ("cs", "c#"), "//", (), _csharp_template()),
    Language("go", "Go", ".go", (), "//", ("go", "run"), _go_template()),
    Language("rust", "Rust", ".rs", ("rs",), "//", (), _rust_template()),
    Language("ruby", "Ruby", ".rb", ("rb",), "#", ("ruby",), _ruby_template()),
    Language("php", "PHP", ".php", (), "//", ("php",), _php_template()),
    Language("shell", "Shell", ".sh", ("bash", "sh"), "#", ("bash",), _shell_template()),
    Language("powershell", "PowerShell", ".ps1", ("ps1", "pwsh"), "#", ("powershell", "-File"), _ps1_template()),
    Language("html", "HTML", ".html", ("htm",), "<!--", (), _html_template()),
    Language("css", "CSS", ".css", (), "/*", (), _css_template()),
    Language("sql", "SQL", ".sql", (), "--", (), _sql_template()),
    Language("json", "JSON", ".json", (), "//", (), _json_template()),
    Language("yaml", "YAML", ".yaml", ("yml",), "#", (), _yaml_template()),
    Language("markdown", "Markdown", ".md", ("md",), "<!--", (), _md_template()),
    Language("lua", "Lua", ".lua", (), "--", ("lua",), _lua_template()),
    Language("kotlin", "Kotlin", ".kt", ("kt",), "//", (), _kotlin_template()),
    Language("swift", "Swift", ".swift", (), "//", ("swift",), _swift_template()),
    Language("r", "R", ".r", (), "#", ("Rscript",), _r_template()),
)


def list_languages() -> list[Language]:
    return list(LANGUAGES)


def language_for_key(key: str) -> Language:
    lowered = (key or "").strip().lower()
    for lang in LANGUAGES:
        if lang.key == lowered or lowered in lang.aliases or lang.label.lower() == lowered:
            return lang
    raise ValueError(f"Unknown language: {key}")


def language_for_extension(ext: str) -> Language | None:
    ext_norm = (ext or "").strip().lower()
    if not ext_norm.startswith("."):
        ext_norm = "." + ext_norm
    for lang in LANGUAGES:
        if lang.extension == ext_norm:
            return lang
    return None


def ensure_workspace() -> Path:
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    return WORKSPACE


def safe_path(name: str) -> Path:
    raw = (name or "").strip()
    if not raw:
        raise ValueError("File name is empty.")
    if any(ch in raw for ch in ("..", "\x00")):
        raise ValueError("File name contains forbidden characters.")
    candidate = (ensure_workspace() / raw).resolve()
    workspace_resolved = WORKSPACE.resolve()
    try:
        candidate.relative_to(workspace_resolved)
    except ValueError:
        raise ValueError("File path escapes the workshop workspace.")
    return candidate


@dataclass(frozen=True)
class FileEntry:
    name: str
    relpath: str
    size: int
    modified: str
    language: str


def list_files() -> list[FileEntry]:
    ensure_workspace()
    entries: list[FileEntry] = []
    for child in sorted(WORKSPACE.rglob("*")):
        if not child.is_file():
            continue
        rel = child.relative_to(WORKSPACE).as_posix()
        stat = child.stat()
        lang = language_for_extension(child.suffix)
        entries.append(
            FileEntry(
                name=child.name,
                relpath=rel,
                size=stat.st_size,
                modified=datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                language=lang.label if lang else child.suffix.lstrip(".").upper() or "TEXT",
            )
        )
    return entries


def read_file(relpath: str) -> str:
    path = safe_path(relpath)
    if not path.exists():
        raise FileNotFoundError(f"No such file: {relpath}")
    return path.read_text(encoding="utf-8")


def write_file(relpath: str, content: str) -> Path:
    path = safe_path(relpath)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    return path


def delete_file(relpath: str) -> Path:
    path = safe_path(relpath)
    if not path.exists():
        raise FileNotFoundError(f"No such file: {relpath}")
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
    return path


def suggest_filename(language_key: str, hint: str = "") -> str:
    lang = language_for_key(language_key)
    stem = (hint or "").strip()
    if not stem:
        stem = "hello_engel"
    import re

    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", stem).strip("_") or "hello_engel"
    if lang.key == "java":
        camel = "".join(word.capitalize() for word in stem.split("_")) or "HelloEngel"
        return camel + lang.extension
    if lang.key == "kotlin":
        camel = "".join(word.capitalize() for word in stem.split("_")) or "HelloEngel"
        return camel + lang.extension
    return stem.lower() + lang.extension


def template_for(language_key: str, filename: str = "") -> str:
    lang = language_for_key(language_key)
    if lang.key == "java" and filename:
        stem = Path(filename).stem or "HelloEngel"
        return _java_template(stem)
    return lang.template


def create_file_from_template(language_key: str, hint: str = "") -> tuple[Path, str]:
    lang = language_for_key(language_key)
    name = suggest_filename(lang.key, hint)
    body = template_for(lang.key, name)
    path = write_file(name, body)
    return path, body


@dataclass
class RunResult:
    ok: bool
    status: str
    command: str
    stdout: str
    stderr: str
    returncode: int = 0


def _resolve_interpreter(lang: Language) -> tuple[list[str], str]:
    """Return (argv_prefix, status) — argv_prefix may be empty if interpreter missing."""
    if not lang.run_argv:
        return [], f"{lang.label} run not supported in workshop (build/compile required)"

    exe = lang.run_argv[0]
    if exe == "python":
        return [sys.executable], "ok"

    found = shutil.which(exe)
    if not found:
        return [], f"{lang.label} interpreter not found on PATH: {exe}"
    return list(lang.run_argv[:1]) + [found] + list(lang.run_argv[1:]) if False else (
        [found] + list(lang.run_argv[1:])
    ), "ok"


def run_file(relpath: str, timeout_seconds: int = 20) -> RunResult:
    path = safe_path(relpath)
    if not path.exists():
        return RunResult(False, "MISSING_FILE", "", "", f"No such file: {relpath}", 1)

    lang = language_for_extension(path.suffix)
    if lang is None:
        return RunResult(False, "UNKNOWN_LANGUAGE", "", "", f"Unknown file type: {path.suffix}", 1)

    argv_prefix, status = _resolve_interpreter(lang)
    if not argv_prefix:
        return RunResult(False, "NO_INTERPRETER", "", "", status, 1)

    argv = list(argv_prefix) + [str(path)]
    command = " ".join(argv)

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(WORKSPACE),
            timeout=timeout_seconds,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        return RunResult(False, "TIMEOUT", command, exc.stdout or "", exc.stderr or "", 124)
    except FileNotFoundError as exc:
        return RunResult(False, "INTERPRETER_MISSING", command, "", str(exc), 127)
    except Exception as exc:
        return RunResult(False, "RUN_ERROR", command, "", str(exc), 1)

    ok = completed.returncode == 0
    status_text = "PASS" if ok else "FAIL"
    return RunResult(ok, status_text, command, completed.stdout or "", completed.stderr or "", completed.returncode)


# --- LLM bridge ----------------------------------------------------------


def _try_local_llm(text: str) -> tuple[bool, str]:
    """Returns (ok, reply). ok=False means the LLM is not available; reply has a note."""
    try:
        import engel_offline_seed_llm as seed
    except Exception as exc:  # pragma: no cover
        return False, f"Local LLM not loadable: {exc}"
    if not seed.offline_seed_llm_gate_enabled():
        return False, "Local LLM gate is OFF. Enable: 'local llm on' from Engel chat."
    try:
        result = seed.run_offline_seed_llm_for_companion_chat(text)
    except Exception as exc:  # pragma: no cover
        return False, f"Local LLM error: {exc}"
    body = (getattr(result, "response", "") or "").strip()
    if getattr(result, "guardian_blocked", False) or not body:
        return False, "(local LLM returned no usable text)"
    return True, body


def _try_brain_provider(text: str) -> tuple[bool, str]:
    try:
        import engel_companion_core as core
    except Exception:
        return False, ""
    fn = getattr(core, "ask_brain_provider", None)
    if not callable(fn):
        return False, ""
    try:
        ctx = {"source": "code_workshop"}
        reply = fn(text, ctx)
    except Exception as exc:  # pragma: no cover
        return False, f"Brain provider error: {exc}"
    if isinstance(reply, dict):
        if not reply.get("ok"):
            return False, ""
        body = (reply.get("text") or reply.get("response") or "").strip()
    else:
        body = (str(reply or "")).strip()
    if not body:
        return False, ""
    return True, body


@dataclass
class AssistResult:
    ok: bool
    source: str
    body: str
    notes: list[str] = field(default_factory=list)


def _strip_code_fence(text: str) -> str:
    if "```" not in text:
        return text
    parts = text.split("```")
    for i, chunk in enumerate(parts):
        if i % 2 == 1:
            cleaned = chunk
            first_nl = cleaned.find("\n")
            if first_nl != -1:
                first_line = cleaned[:first_nl].strip().lower()
                if first_line and not any(ch.isspace() for ch in first_line) and len(first_line) <= 16:
                    cleaned = cleaned[first_nl + 1 :]
            return cleaned.rstrip() + "\n"
    return text


def ask_engel_to_write(language_key: str, intent: str, current_content: str = "") -> AssistResult:
    lang = language_for_key(language_key)
    intent_clean = (intent or "").strip() or f"a small {lang.label} program"
    prompt_parts = [
        f"You are Engel, a careful local coding assistant. Write {lang.label} code only.",
        "Respond ONLY with the code body (no commentary, no markdown fences).",
        f"Target language: {lang.label} (extension {lang.extension}).",
        f"Task: {intent_clean}",
    ]
    if current_content.strip():
        prompt_parts.append("Existing file content (edit instead of replace if reasonable):\n" + current_content)
    prompt = "\n\n".join(prompt_parts)

    ok, body = _try_brain_provider(prompt)
    if ok:
        return AssistResult(True, "brain_provider", _strip_code_fence(body))

    ok, body = _try_local_llm(prompt)
    if ok:
        return AssistResult(True, "local_llm", _strip_code_fence(body))

    template = template_for(lang.key)
    note = body if body else "no provider/local LLM available"
    return AssistResult(
        False,
        "fallback_template",
        template,
        notes=[
            f"Provider unavailable: {note}",
            "Returned starter template — edit freely.",
        ],
    )


def ask_engel_to_edit(language_key: str, instruction: str, current_content: str) -> AssistResult:
    lang = language_for_key(language_key)
    inst_clean = (instruction or "").strip() or "improve readability"
    prompt = (
        f"You are Engel, editing a {lang.label} file. Apply this change: {inst_clean}\n"
        "Respond ONLY with the full updated file content. No commentary, no fences.\n"
        "Current file:\n"
        f"{current_content}"
    )

    ok, body = _try_brain_provider(prompt)
    if ok:
        return AssistResult(True, "brain_provider", _strip_code_fence(body))

    ok, body = _try_local_llm(prompt)
    if ok:
        return AssistResult(True, "local_llm", _strip_code_fence(body))

    return AssistResult(
        False,
        "no_change",
        current_content,
        notes=["No LLM provider available — kept current content unchanged."],
    )


def ask_engel_to_explain(language_key: str, content: str, question: str = "") -> AssistResult:
    lang = language_for_key(language_key)
    question_clean = (question or "").strip() or "Explain what this code does."
    prompt = (
        f"You are Engel, explaining {lang.label} code clearly and briefly.\n"
        f"Question: {question_clean}\n\n"
        f"Code:\n{content}"
    )
    ok, body = _try_brain_provider(prompt)
    if ok:
        return AssistResult(True, "brain_provider", body)
    ok, body = _try_local_llm(prompt)
    if ok:
        return AssistResult(True, "local_llm", body)
    return AssistResult(
        False,
        "static_explain",
        _static_explanation(content, lang),
        notes=["No LLM provider available — showed a static summary instead."],
    )


def _static_explanation(content: str, lang: Language) -> str:
    lines = [ln for ln in content.splitlines() if ln.strip()]
    out = [
        f"Static {lang.label} summary:",
        f"  Lines: {len(lines)}",
        f"  Size: {len(content)} chars",
    ]
    interesting = []
    for ln in lines[:60]:
        stripped = ln.strip()
        if any(stripped.startswith(prefix) for prefix in ("def ", "class ", "function ", "fn ", "public ", "private ", "package ", "import ", "fun ", "module ", "func ")):
            interesting.append(stripped[:120])
        if len(interesting) >= 12:
            break
    if interesting:
        out.append("  Definitions/imports:")
        out.extend(f"    - {item}" for item in interesting)
    return "\n".join(out)


def workshop_status() -> str:
    ensure_workspace()
    files = list_files()
    try:
        import engel_offline_seed_llm as seed

        gate = "ON" if seed.offline_seed_llm_gate_enabled() else "OFF"
    except Exception:
        gate = "UNKNOWN"
    return (
        f"workspace: {WORKSPACE}\n"
        f"files: {len(files)}\n"
        f"languages_registered: {len(LANGUAGES)}\n"
        f"local_llm_gate: {gate}\n"
    )


if __name__ == "__main__":  # pragma: no cover
    print(workshop_status())
    for lang in LANGUAGES:
        print(f"  - {lang.label:12s} {lang.extension}")
