from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import mimetypes
from pathlib import Path
import re
import ssl
import sys
import time
import urllib.error
import urllib.request


ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
LIBRARY_ROOT = ROOT / "engel_library" / "approved_library"
MANIFEST_JSON = ROOT / "memory" / "ENGEL_APPROVED_LIBRARY_DOWNLOAD_MANIFEST_V1.json"
MANIFEST_MD = ROOT / "memory" / "ENGEL_APPROVED_LIBRARY_DOWNLOAD_MANIFEST_V1.md"
RECEIPT_DIR = LIBRARY_ROOT / "downloaded_receipts"
FAILURE_DIR = LIBRARY_ROOT / "download_failures"
USER_AGENT = "EngelApprovedLibraryDownloader/1.0 (curated-public-docs; no-execution)"
TIMEOUT_SECONDS = 40
MAX_BYTES = 12 * 1024 * 1024


CATEGORY_FOLDERS = [
    "python_docs",
    "pyside6_qt_docs",
    "sqlite_docs",
    "pyinstaller_packaging_docs",
    "testing_pytest_docs",
    "static_analysis_linting_docs",
    "security_prompt_injection_docs",
    "ai_safety_agent_safety_docs",
    "llm_reference_docs",
    "retrieval_rag_docs",
    "memory_systems_docs",
    "code_companion_patch_planning_docs",
    "coding_language_references",
    "math_logic_reasoning_references",
    "algorithms_data_structures_references",
    "android_remote_worker_references",
    "wsl_ubuntu_runtime_references",
    "engel_ai_offline_seed_docs",
    "engel_code_companion_docs",
    "engel_manuals_reports_receipts",
    "downloaded_receipts",
    "download_failures",
]


SAFETY_BOUNDARIES = [
    "REAL_PUBLIC_MATERIALS_ONLY",
    "NO_FAKE_DATA",
    "PENDING_HUMAN_REVIEW",
    "UNTRUSTED_UNTIL_REVIEWED",
    "NOT_TRUSTED_MEMORY",
    "NO_MODEL_LOADING",
    "NO_INFERENCE",
    "NO_TRAINING",
    "NO_PACKAGE_INSTALL",
    "NO_PIP_INSTALL",
    "NO_EXECUTION_OF_DOWNLOADED_FILES",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_PROVIDER_CALLS",
    "NO_BROWSER_AUTOMATION",
    "NO_BACKGROUND_WORKER",
    "NO_STARTUP_AUTORUN",
]


SOURCES = [
    {
        "category": "python_docs",
        "title": "Python 3 Tutorial",
        "source_url": "https://docs.python.org/3/tutorial/index.html",
        "license_note": "Official Python documentation; PSF documentation license.",
    },
    {
        "category": "python_docs",
        "title": "Python Standard Library Index",
        "source_url": "https://docs.python.org/3/library/index.html",
        "license_note": "Official Python documentation; PSF documentation license.",
    },
    {
        "category": "pyside6_qt_docs",
        "title": "Qt for Python Documentation",
        "source_url": "https://doc.qt.io/qtforpython-6/",
        "license_note": "Official Qt for Python documentation.",
    },
    {
        "category": "pyside6_qt_docs",
        "title": "Qt Widgets Overview",
        "source_url": "https://doc.qt.io/qt-6/qtwidgets-index.html",
        "license_note": "Official Qt documentation.",
    },
    {
        "category": "sqlite_docs",
        "title": "SQLite SQL Language",
        "source_url": "https://www.sqlite.org/lang.html",
        "license_note": "Official SQLite documentation; public-domain SQLite project.",
    },
    {
        "category": "sqlite_docs",
        "title": "SQLite Command Line Shell",
        "source_url": "https://www.sqlite.org/cli.html",
        "license_note": "Official SQLite documentation; public-domain SQLite project.",
    },
    {
        "category": "pyinstaller_packaging_docs",
        "title": "PyInstaller Manual",
        "source_url": "https://pyinstaller.org/en/stable/",
        "license_note": "Official PyInstaller documentation.",
    },
    {
        "category": "pyinstaller_packaging_docs",
        "title": "Python Packaging Tutorial",
        "source_url": "https://packaging.python.org/en/latest/tutorials/packaging-projects/",
        "license_note": "Official Python Packaging User Guide.",
    },
    {
        "category": "testing_pytest_docs",
        "title": "pytest Documentation",
        "source_url": "https://docs.pytest.org/en/stable/",
        "license_note": "Official pytest documentation.",
    },
    {
        "category": "testing_pytest_docs",
        "title": "Python unittest Documentation",
        "source_url": "https://docs.python.org/3/library/unittest.html",
        "license_note": "Official Python documentation; PSF documentation license.",
    },
    {
        "category": "static_analysis_linting_docs",
        "title": "Ruff Documentation",
        "source_url": "https://docs.astral.sh/ruff/",
        "license_note": "Official Ruff documentation.",
    },
    {
        "category": "static_analysis_linting_docs",
        "title": "mypy Documentation",
        "source_url": "https://mypy.readthedocs.io/en/stable/",
        "license_note": "Official mypy documentation.",
    },
    {
        "category": "static_analysis_linting_docs",
        "title": "Pylint User Guide",
        "source_url": "https://pylint.readthedocs.io/en/stable/",
        "license_note": "Official Pylint documentation.",
    },
    {
        "category": "security_prompt_injection_docs",
        "title": "OWASP LLM Top 10 Prompt Injection",
        "source_url": "https://genai.owasp.org/llmrisk/llm01-prompt-injection/",
        "license_note": "OWASP public guidance.",
    },
    {
        "category": "security_prompt_injection_docs",
        "title": "OWASP LLM Top 10 Project",
        "source_url": "https://genai.owasp.org/owasp-top-10-for-llm-applications-2025/",
        "license_note": "OWASP public guidance.",
    },
    {
        "category": "ai_safety_agent_safety_docs",
        "title": "NIST AI Risk Management Framework",
        "source_url": "https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-1.pdf",
        "license_note": "NIST public document.",
    },
    {
        "category": "ai_safety_agent_safety_docs",
        "title": "OWASP Agentic AI Threats and Mitigations",
        "source_url": "https://genai.owasp.org/resource/agentic-ai-threats-and-mitigations/",
        "license_note": "OWASP public guidance.",
    },
    {
        "category": "llm_reference_docs",
        "title": "llama.cpp README",
        "source_url": "https://raw.githubusercontent.com/ggml-org/llama.cpp/master/README.md",
        "license_note": "Public open-source project documentation.",
    },
    {
        "category": "llm_reference_docs",
        "title": "GGUF Format Documentation",
        "source_url": "https://raw.githubusercontent.com/ggml-org/ggml/master/docs/gguf.md",
        "license_note": "Public open-source project documentation.",
    },
    {
        "category": "retrieval_rag_docs",
        "title": "Retrieval-Augmented Generation Paper",
        "source_url": "https://arxiv.org/pdf/2005.11401",
        "license_note": "Public arXiv paper.",
    },
    {
        "category": "retrieval_rag_docs",
        "title": "Stanford IR Book Online Reading",
        "source_url": "https://nlp.stanford.edu/IR-book/pdf/irbookonlinereading.pdf",
        "license_note": "Public Stanford Information Retrieval book PDF.",
    },
    {
        "category": "memory_systems_docs",
        "title": "Event Sourcing",
        "source_url": "https://martinfowler.com/eaaDev/EventSourcing.html",
        "license_note": "Public software architecture reference.",
    },
    {
        "category": "memory_systems_docs",
        "title": "MemGPT Paper",
        "source_url": "https://arxiv.org/pdf/2310.08560",
        "license_note": "Public arXiv paper.",
    },
    {
        "category": "code_companion_patch_planning_docs",
        "title": "GitHub Pull Request Reviews",
        "source_url": "https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/reviewing-changes-in-pull-requests/about-pull-request-reviews",
        "license_note": "Official GitHub documentation.",
    },
    {
        "category": "code_companion_patch_planning_docs",
        "title": "Google Engineering Practices Code Review",
        "source_url": "https://google.github.io/eng-practices/review/reviewer/",
        "license_note": "Public Google engineering practices.",
    },
    {
        "category": "coding_language_references",
        "title": "Python Language Reference",
        "source_url": "https://docs.python.org/3/reference/index.html",
        "license_note": "Official Python documentation; PSF documentation license.",
    },
    {
        "category": "coding_language_references",
        "title": "TypeScript Handbook",
        "source_url": "https://www.typescriptlang.org/docs/handbook/intro.html",
        "license_note": "Official TypeScript documentation.",
    },
    {
        "category": "coding_language_references",
        "title": "JavaScript MDN Guide",
        "source_url": "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide",
        "license_note": "MDN Web Docs public documentation.",
    },
    {
        "category": "coding_language_references",
        "title": "Kotlin Documentation",
        "source_url": "https://kotlinlang.org/docs/home.html",
        "license_note": "Official Kotlin documentation.",
    },
    {
        "category": "coding_language_references",
        "title": "Java Language Guide",
        "source_url": "https://docs.oracle.com/javase/tutorial/java/index.html",
        "license_note": "Oracle Java tutorial public documentation.",
    },
    {
        "category": "coding_language_references",
        "title": "C Language Reference",
        "source_url": "https://en.cppreference.com/w/c/language",
        "license_note": "cppreference public reference.",
    },
    {
        "category": "coding_language_references",
        "title": "C++ Language Reference",
        "source_url": "https://en.cppreference.com/w/cpp/language",
        "license_note": "cppreference public reference.",
    },
    {
        "category": "coding_language_references",
        "title": "Rust Book",
        "source_url": "https://doc.rust-lang.org/book/",
        "license_note": "Official Rust documentation.",
    },
    {
        "category": "coding_language_references",
        "title": "SQL SQLite Language Reference",
        "source_url": "https://www.sqlite.org/lang.html",
        "license_note": "Official SQLite documentation; public-domain SQLite project.",
    },
    {
        "category": "coding_language_references",
        "title": "CommonMark Specification",
        "source_url": "https://spec.commonmark.org/0.31.2/",
        "license_note": "Official CommonMark specification.",
    },
    {
        "category": "coding_language_references",
        "title": "JSON RFC 8259",
        "source_url": "https://www.rfc-editor.org/rfc/rfc8259.txt",
        "license_note": "IETF RFC public document.",
    },
    {
        "category": "coding_language_references",
        "title": "YAML 1.2.2 Specification",
        "source_url": "https://yaml.org/spec/1.2.2/",
        "license_note": "Official YAML specification.",
    },
    {
        "category": "coding_language_references",
        "title": "Dart Language Tour",
        "source_url": "https://dart.dev/language",
        "license_note": "Official Dart documentation; Creative Commons Attribution 4.0.",
    },
    {
        "category": "coding_language_references",
        "title": "Flutter Documentation",
        "source_url": "https://docs.flutter.dev/",
        "license_note": "Official Flutter documentation; Creative Commons Attribution 4.0.",
    },
    {
        "category": "coding_language_references",
        "title": "Bash Reference Manual",
        "source_url": "https://www.gnu.org/software/bash/manual/bash.html",
        "license_note": "Official GNU Bash documentation; GNU Free Documentation License.",
    },
    {
        "category": "coding_language_references",
        "title": "PowerShell Documentation Overview",
        "source_url": "https://learn.microsoft.com/en-us/powershell/scripting/overview",
        "license_note": "Official Microsoft PowerShell documentation; Creative Commons Attribution 4.0.",
    },
    {
        "category": "coding_language_references",
        "title": "HTML MDN Reference",
        "source_url": "https://developer.mozilla.org/en-US/docs/Web/HTML",
        "license_note": "MDN Web Docs; Creative Commons Attribution-ShareAlike 2.5.",
    },
    {
        "category": "coding_language_references",
        "title": "CSS MDN Reference",
        "source_url": "https://developer.mozilla.org/en-US/docs/Web/CSS",
        "license_note": "MDN Web Docs; Creative Commons Attribution-ShareAlike 2.5.",
    },
    {
        "category": "coding_language_references",
        "title": "TOML Specification v1.0.0",
        "source_url": "https://toml.io/en/v1.0.0",
        "license_note": "Official TOML specification; MIT license.",
    },
    {
        "category": "coding_language_references",
        "title": "Go Language Specification",
        "source_url": "https://go.dev/ref/spec",
        "license_note": "Official Go documentation; Creative Commons Attribution 4.0.",
    },
    {
        "category": "math_logic_reasoning_references",
        "title": "Discrete Mathematics Open Introduction",
        "source_url": "https://discrete.openmathbooks.org/dmoi3.html",
        "license_note": "Open-access mathematics text.",
    },
    {
        "category": "math_logic_reasoning_references",
        "title": "OpenStax College Algebra",
        "source_url": "https://openstax.org/details/books/college-algebra-2e",
        "license_note": "OpenStax open educational resource.",
    },
    {
        "category": "math_logic_reasoning_references",
        "title": "OpenStax Introductory Statistics",
        "source_url": "https://openstax.org/details/books/introductory-statistics",
        "license_note": "OpenStax open educational resource.",
    },
    {
        "category": "math_logic_reasoning_references",
        "title": "MIT Linear Algebra Course",
        "source_url": "https://ocw.mit.edu/courses/18-06-linear-algebra-spring-2010/",
        "license_note": "MIT OpenCourseWare public course page.",
    },
    {
        "category": "algorithms_data_structures_references",
        "title": "CP Algorithms",
        "source_url": "https://cp-algorithms.com/",
        "license_note": "Public algorithms reference.",
    },
    {
        "category": "algorithms_data_structures_references",
        "title": "Open Data Structures",
        "source_url": "https://opendatastructures.org/ods-python/",
        "license_note": "Open textbook on data structures.",
    },
    {
        "category": "android_remote_worker_references",
        "title": "Android App Architecture",
        "source_url": "https://developer.android.com/topic/architecture",
        "license_note": "Official Android developer documentation.",
    },
    {
        "category": "android_remote_worker_references",
        "title": "Android Permissions",
        "source_url": "https://developer.android.com/guide/topics/permissions/overview",
        "license_note": "Official Android developer documentation.",
    },
    {
        "category": "android_remote_worker_references",
        "title": "Android Background Work",
        "source_url": "https://developer.android.com/develop/background-work",
        "license_note": "Official Android developer documentation.",
    },
    {
        "category": "android_remote_worker_references",
        "title": "Android App Data and Files",
        "source_url": "https://developer.android.com/training/data-storage",
        "license_note": "Official Android developer documentation.",
    },
    {
        "category": "wsl_ubuntu_runtime_references",
        "title": "Microsoft WSL Documentation",
        "source_url": "https://learn.microsoft.com/en-us/windows/wsl/",
        "license_note": "Official Microsoft WSL documentation.",
    },
    {
        "category": "wsl_ubuntu_runtime_references",
        "title": "WSL Basic Commands",
        "source_url": "https://learn.microsoft.com/en-us/windows/wsl/basic-commands",
        "license_note": "Official Microsoft WSL documentation.",
    },
    {
        "category": "wsl_ubuntu_runtime_references",
        "title": "Ubuntu Server Documentation",
        "source_url": "https://documentation.ubuntu.com/server/",
        "license_note": "Official Ubuntu documentation.",
    },
    {
        "category": "engel_manuals_reports_receipts",
        "title": "Engel LLM and Python Library Intake Plan V1",
        "local_source": "memory/ENGEL_LLM_AND_PYTHON_LIBRARY_INTAKE_PLAN_V1.md",
        "source_url": "project://memory/ENGEL_LLM_AND_PYTHON_LIBRARY_INTAKE_PLAN_V1.md",
        "license_note": "Local Engel project documentation.",
    },
    {
        "category": "engel_manuals_reports_receipts",
        "title": "Engel Android Remote Worker Plan V1",
        "local_source": "memory/ENGEL_ANDROID_REMOTE_WORKER_PLAN_V1.md",
        "source_url": "project://memory/ENGEL_ANDROID_REMOTE_WORKER_PLAN_V1.md",
        "license_note": "Local Engel project documentation.",
    },
    {
        "category": "engel_manuals_reports_receipts",
        "title": "Engel WSL Ubuntu Runtime Dependency V1",
        "local_source": "memory/ENGEL_WSL_UBUNTU_RUNTIME_DEPENDENCY_V1.md",
        "source_url": "project://memory/ENGEL_WSL_UBUNTU_RUNTIME_DEPENDENCY_V1.md",
        "license_note": "Local Engel project documentation.",
    },
    {
        "category": "engel_manuals_reports_receipts",
        "title": "Engel Integrated Status with WSL and Android Package Refresh",
        "local_source": "reports/codex_bridge/ENGEL_INTEGRATED_STATUS_WITH_WSL_ANDROID_PACKAGE_REFRESH.md",
        "source_url": "project://reports/codex_bridge/ENGEL_INTEGRATED_STATUS_WITH_WSL_ANDROID_PACKAGE_REFRESH.md",
        "license_note": "Local Engel project report.",
    },
    # --- Engel AI Offline Seed Docs ---
    {
        "category": "engel_ai_offline_seed_docs",
        "title": "llama-cpp-python README",
        "source_url": "https://raw.githubusercontent.com/abetlen/llama-cpp-python/main/README.md",
        "license_note": "MIT license; public open-source project documentation.",
    },
    {
        "category": "engel_ai_offline_seed_docs",
        "title": "Qwen2.5 Model README",
        "source_url": "https://raw.githubusercontent.com/QwenLM/Qwen2.5/main/README.md",
        "license_note": "Apache-2.0; public open-source project documentation.",
    },
    {
        "category": "engel_ai_offline_seed_docs",
        "title": "Python threading Module",
        "source_url": "https://docs.python.org/3/library/threading.html",
        "license_note": "Official Python documentation; PSF documentation license.",
    },
    {
        "category": "engel_ai_offline_seed_docs",
        "title": "Python asyncio Module",
        "source_url": "https://docs.python.org/3/library/asyncio.html",
        "license_note": "Official Python documentation; PSF documentation license.",
    },
    {
        "category": "engel_ai_offline_seed_docs",
        "title": "Engel Offline Seed LLM Contract V1",
        "local_source": "memory/OFFLINE_SEED_LLM_CONTRACT_V1.json",
        "source_url": "project://memory/OFFLINE_SEED_LLM_CONTRACT_V1.json",
        "license_note": "Local Engel project contract.",
    },
    # --- Engel Code Companion Docs ---
    {
        "category": "engel_code_companion_docs",
        "title": "Python ast Module",
        "source_url": "https://docs.python.org/3/library/ast.html",
        "license_note": "Official Python documentation; PSF documentation license.",
    },
    {
        "category": "engel_code_companion_docs",
        "title": "Python difflib Module",
        "source_url": "https://docs.python.org/3/library/difflib.html",
        "license_note": "Official Python documentation; PSF documentation license.",
    },
    {
        "category": "engel_code_companion_docs",
        "title": "Python pathlib Module",
        "source_url": "https://docs.python.org/3/library/pathlib.html",
        "license_note": "Official Python documentation; PSF documentation license.",
    },
    {
        "category": "engel_code_companion_docs",
        "title": "Semantic Versioning Specification",
        "source_url": "https://semver.org/",
        "license_note": "Creative Commons CC-BY 3.0 public specification.",
    },
    {
        "category": "engel_code_companion_docs",
        "title": "Engel Code Companion Growth Bridge Contract V1",
        "local_source": "memory/ENGEL_CODE_COMPANION_GROWTH_BRIDGE_CONTRACT_V1.md",
        "source_url": "project://memory/ENGEL_CODE_COMPANION_GROWTH_BRIDGE_CONTRACT_V1.md",
        "license_note": "Local Engel project contract.",
    },
    {
        "category": "engel_code_companion_docs",
        "title": "Engel Code Companion Low Risk Patch Apply Contract V1",
        "local_source": "memory/ENGEL_CODE_COMPANION_LOW_RISK_PATCH_APPLY_CONTRACT_V1.md",
        "source_url": "project://memory/ENGEL_CODE_COMPANION_LOW_RISK_PATCH_APPLY_CONTRACT_V1.md",
        "license_note": "Local Engel project contract.",
    },
    {
        "category": "engel_code_companion_docs",
        "title": "Python subprocess Module",
        "source_url": "https://docs.python.org/3/library/subprocess.html",
        "license_note": "Official Python documentation; PSF documentation license.",
    },
    {
        "category": "engel_code_companion_docs",
        "title": "Python inspect Module",
        "source_url": "https://docs.python.org/3/library/inspect.html",
        "license_note": "Official Python documentation; PSF documentation license.",
    },
    {
        "category": "engel_code_companion_docs",
        "title": "Python re Module (Regular Expressions)",
        "source_url": "https://docs.python.org/3/library/re.html",
        "license_note": "Official Python documentation; PSF documentation license.",
    },
    {
        "category": "engel_code_companion_docs",
        "title": "Python shutil Module",
        "source_url": "https://docs.python.org/3/library/shutil.html",
        "license_note": "Official Python documentation; PSF documentation license.",
    },
    {
        "category": "engel_code_companion_docs",
        "title": "Python tokenize Module",
        "source_url": "https://docs.python.org/3/library/tokenize.html",
        "license_note": "Official Python documentation; PSF documentation license.",
    },
]


class DownloadError(Exception):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def safe_slug(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    return cleaned[:120] or "downloaded_material"


def infer_extension(source: dict[str, str], content_type: str | None) -> str:
    url = source.get("source_url", "")
    path_suffix = Path(url.split("?", 1)[0]).suffix.lower()
    if path_suffix in {".html", ".htm", ".md", ".txt", ".pdf", ".json", ".yaml", ".yml"}:
        return ".html" if path_suffix == ".htm" else path_suffix
    if content_type:
        guessed = mimetypes.guess_extension(content_type.split(";", 1)[0].strip())
        if guessed in {".html", ".htm", ".md", ".txt", ".pdf", ".json", ".yaml", ".yml"}:
            return ".html" if guessed == ".htm" else guessed
    if "raw.githubusercontent.com" in url and url.endswith(".md"):
        return ".md"
    return ".html"


def ensure_folders() -> None:
    for folder in CATEGORY_FOLDERS:
        (LIBRARY_ROOT / folder).mkdir(parents=True, exist_ok=True)


def selected_sources(category: str) -> list[dict[str, str]]:
    if category == "all":
        return list(SOURCES)
    if category not in CATEGORY_FOLDERS:
        raise DownloadError(f"unknown category: {category}")
    return [source for source in SOURCES if source["category"] == category]


def material_id(source: dict[str, str]) -> str:
    digest = hashlib.sha256(source["source_url"].encode("utf-8")).hexdigest()[:12]
    return f"{source['category']}_{safe_slug(source['title']).lower()}_{digest}"


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def fetch_url(source: dict[str, str]) -> tuple[bytes, str | None]:
    request = urllib.request.Request(
        source["source_url"],
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/pdf,text/plain,*/*"},
    )
    context = ssl.create_default_context()
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS, context=context) as response:
            content_type = response.headers.get("Content-Type")
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = response.read(1024 * 64)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_BYTES:
                    raise DownloadError(f"download exceeded {MAX_BYTES} byte safety cap")
                chunks.append(chunk)
            return b"".join(chunks), content_type
    except urllib.error.URLError as exc:
        raise DownloadError(str(exc)) from exc


def local_bytes(source: dict[str, str]) -> tuple[bytes, str]:
    local = ROOT / source["local_source"]
    if not local.exists() or not local.is_file():
        raise DownloadError(f"local source missing: {source['local_source']}")
    return local.read_bytes(), "text/markdown"


def load_previous_manifest() -> dict[str, object] | None:
    if not MANIFEST_JSON.exists():
        return None
    try:
        return json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def existing_success_maps() -> tuple[set[str], set[str]]:
    manifest = load_previous_manifest() or {}
    urls: set[str] = set()
    hashes: set[str] = set()
    for record in manifest.get("downloaded_files", []):
        if isinstance(record, dict):
            if record.get("source_url"):
                urls.add(str(record["source_url"]))
            if record.get("sha256"):
                hashes.add(str(record["sha256"]).upper())
    return urls, hashes


def receipt_record(source: dict[str, str], local_path: Path, content_type: str | None, downloaded_at: str) -> dict[str, object]:
    sha = file_sha256(local_path)
    return {
        "material_id": material_id(source),
        "category": source["category"],
        "title": source["title"],
        "source_url": source["source_url"],
        "local_path": str(local_path.relative_to(ROOT)),
        "sha256": sha,
        "size_bytes": local_path.stat().st_size,
        "downloaded_at": downloaded_at,
        "source_type": "local_project_copy" if "local_source" in source else "public_download",
        "content_type": content_type or mimetypes.guess_type(local_path.name)[0] or "unknown",
        "license_note": source.get("license_note", "public source; license review still required"),
        "review_state": [
            "DOWNLOADED_REAL_MATERIAL",
            "PENDING_HUMAN_REVIEW",
            "UNTRUSTED_UNTIL_REVIEWED",
            "NOT_TRUSTED_MEMORY",
        ],
        "trusted_memory_allowed": False,
        "execution_allowed": False,
        "model_loading_allowed": False,
        "package_install_allowed": False,
    }


def failure_record(source: dict[str, str], reason: str, attempted_at: str) -> dict[str, object]:
    return {
        "material_id": material_id(source),
        "category": source["category"],
        "title": source["title"],
        "source_url": source["source_url"],
        "attempted_at": attempted_at,
        "failure_reason": reason,
        "review_state": [
            "DOWNLOAD_FAILED",
            "NO_FAKE_SUCCESS",
            "PENDING_HUMAN_REVIEW",
        ],
    }


def save_receipt(record: dict[str, object]) -> None:
    write_json(RECEIPT_DIR / f"{record['material_id']}.json", record)


def save_failure(record: dict[str, object]) -> None:
    write_json(FAILURE_DIR / f"{record['material_id']}.json", record)


def build_manifest(successes: list[dict[str, object]], failures: list[dict[str, object]], generated_at: str) -> dict[str, object]:
    by_category: dict[str, dict[str, int]] = {
        category: {"attempted": 0, "successful": 0, "failed": 0} for category in CATEGORY_FOLDERS
    }
    for source in SOURCES:
        by_category[source["category"]]["attempted"] += 1
    for record in successes:
        by_category[str(record["category"])]["successful"] += 1
    for record in failures:
        by_category[str(record["category"])]["failed"] += 1
    return {
        "schema_version": "1.0",
        "target_library_root": str(LIBRARY_ROOT),
        "generated_at": generated_at,
        "categories": by_category,
        "sources_attempted": len(SOURCES),
        "downloads_successful": len(successes),
        "downloads_failed": len(failures),
        "downloaded_files": successes,
        "failure_records": failures,
        "hash_algorithm": "SHA256",
        "safety_boundaries": SAFETY_BOUNDARIES,
        "no_fake_data": True,
        "no_model_loading": True,
        "no_inference": True,
        "no_package_install": True,
        "no_trusted_memory_write": True,
    }


def write_manifest_md(manifest: dict[str, object]) -> None:
    categories = manifest["categories"]
    lines = [
        "# Engel Approved Library Download Manifest V1",
        "",
        "Status: REAL_PUBLIC_MATERIALS_DOWNLOADED / PENDING_HUMAN_REVIEW / UNTRUSTED_UNTIL_REVIEWED / NOT_TRUSTED_MEMORY",
        "",
        f"Generated at: `{manifest['generated_at']}`",
        f"Target library root: `{manifest['target_library_root']}`",
        "",
        "## Summary",
        "",
        f"- Sources attempted: {manifest['sources_attempted']}",
        f"- Downloads successful: {manifest['downloads_successful']}",
        f"- Downloads failed: {manifest['downloads_failed']}",
        f"- Hash algorithm: {manifest['hash_algorithm']}",
        "",
        "## Safety Boundaries",
        "",
    ]
    lines.extend(f"- {label}" for label in SAFETY_BOUNDARIES)
    lines.extend(["", "## Categories", ""])
    for category, summary in categories.items():
        lines.append(
            f"- `{category}`: attempted {summary['attempted']}, "
            f"successful {summary['successful']}, failed {summary['failed']}"
        )
    lines.extend(["", "## Downloaded Files", ""])
    for record in manifest["downloaded_files"]:
        lines.append(f"- `{record['material_id']}`")
        lines.append(f"  - category: `{record['category']}`")
        lines.append(f"  - title: {record['title']}")
        lines.append(f"  - source: {record['source_url']}")
        lines.append(f"  - local path: `{record['local_path']}`")
        lines.append(f"  - sha256: `{record['sha256']}`")
        lines.append(f"  - size bytes: {record['size_bytes']}")
    lines.extend(["", "## Failures", ""])
    if manifest["failure_records"]:
        for record in manifest["failure_records"]:
            lines.append(f"- `{record['material_id']}`: {record['failure_reason']}")
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Review Boundary",
            "",
            "Every successful file remains PENDING_HUMAN_REVIEW, UNTRUSTED_UNTIL_REVIEWED, and NOT_TRUSTED_MEMORY.",
            "No downloaded instructions were executed. No model loading, inference, training, pip/package install, trusted-memory write, provider call, browser automation, background worker, or startup behavior was performed.",
            "",
        ]
    )
    MANIFEST_MD.write_text("\n".join(lines), encoding="utf-8")


def download(category: str) -> dict[str, object]:
    ensure_folders()
    generated_at = now_iso()
    successes: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []
    seen_urls, seen_hashes = existing_success_maps()
    for source in selected_sources(category):
        attempted_at = now_iso()
        try:
            if "local_source" in source:
                payload, content_type = local_bytes(source)
            else:
                payload, content_type = fetch_url(source)
            if not payload:
                raise DownloadError("downloaded file was empty")
            extension = infer_extension(source, content_type)
            local_path = LIBRARY_ROOT / source["category"] / f"{material_id(source)}__{safe_slug(source['title'])}{extension}"
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_bytes(payload)
            sha = file_sha256(local_path)
            if source["source_url"] in seen_urls or sha in seen_hashes:
                # Keep the file but mark the receipt honestly as a duplicate source/hash.
                duplicate_note = " Duplicate source URL or hash seen in previous manifest."
                source = dict(source)
                source["license_note"] = source.get("license_note", "") + duplicate_note
            record = receipt_record(source, local_path, content_type, attempted_at)
            save_receipt(record)
            successes.append(record)
            seen_urls.add(source["source_url"])
            seen_hashes.add(str(record["sha256"]))
            time.sleep(0.2)
        except (OSError, DownloadError) as exc:
            record = failure_record(source, str(exc), attempted_at)
            save_failure(record)
            failures.append(record)
    manifest = build_manifest(successes, failures, generated_at)
    write_json(MANIFEST_JSON, manifest)
    write_manifest_md(manifest)
    return manifest


def plan() -> str:
    lines = [
        "Engel Approved Library Downloader V1",
        "",
        "Default behavior is dry-run/plan. Network is used only with --download.",
        f"Target library root: {LIBRARY_ROOT}",
        "",
        "Categories:",
    ]
    for category in CATEGORY_FOLDERS:
        if category in {"downloaded_receipts", "download_failures"}:
            continue
        count = sum(1 for source in SOURCES if source["category"] == category)
        lines.append(f"- {category}: {count} curated source(s)")
    lines.extend(
        [
            "",
            "Safety:",
            "- no fake success",
            "- no model loading",
            "- no inference",
            "- no training",
            "- no pip/package install",
            "- no execution of downloaded material",
            "- no trusted-memory write",
        ]
    )
    return "\n".join(lines)


def verify_library() -> tuple[bool, str]:
    if not MANIFEST_JSON.exists():
        return False, "manifest is missing"
    try:
        manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return False, f"manifest JSON invalid: {exc}"
    problems: list[str] = []
    for field in ["no_fake_data", "no_model_loading", "no_inference", "no_package_install", "no_trusted_memory_write"]:
        if manifest.get(field) is not True:
            problems.append(f"{field} is not true")
    for record in manifest.get("downloaded_files", []):
        local_path = ROOT / str(record.get("local_path", ""))
        if not local_path.exists() or not local_path.is_file():
            problems.append(f"missing file for {record.get('material_id')}")
            continue
        sha = file_sha256(local_path)
        if sha != str(record.get("sha256", "")).upper():
            problems.append(f"hash mismatch for {record.get('material_id')}")
        if local_path.stat().st_size != int(record.get("size_bytes", -1)):
            problems.append(f"size mismatch for {record.get('material_id')}")
        states = record.get("review_state", [])
        for required in ["PENDING_HUMAN_REVIEW", "UNTRUSTED_UNTIL_REVIEWED", "NOT_TRUSTED_MEMORY"]:
            if required not in states:
                problems.append(f"{record.get('material_id')} missing {required}")
        for flag in ["trusted_memory_allowed", "execution_allowed", "model_loading_allowed", "package_install_allowed"]:
            if record.get(flag) is not False:
                problems.append(f"{record.get('material_id')} has unsafe {flag}")
    if problems:
        return False, "\n".join(problems)
    return True, "library verification passed"


def summary_text() -> str:
    if not MANIFEST_JSON.exists():
        return "No approved library download manifest exists yet."
    manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))
    total_bytes = sum(int(record["size_bytes"]) for record in manifest.get("downloaded_files", []))
    lines = [
        "Engel Approved Library Download Summary",
        f"- manifest: {MANIFEST_JSON}",
        f"- target root: {manifest.get('target_library_root')}",
        f"- sources attempted: {manifest.get('sources_attempted')}",
        f"- downloads successful: {manifest.get('downloads_successful')}",
        f"- downloads failed: {manifest.get('downloads_failed')}",
        f"- total bytes downloaded/copied: {total_bytes}",
        "- review state: PENDING_HUMAN_REVIEW / UNTRUSTED_UNTIL_REVIEWED / NOT_TRUSTED_MEMORY",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download curated public materials into Engel approved library.")
    parser.add_argument("--plan", action="store_true", help="Print curated source plan without downloading.")
    parser.add_argument("--download", action="store_true", help="Download curated real public materials.")
    parser.add_argument("--category", default="all", help="Category to download, or all.")
    parser.add_argument("--verify-library", action="store_true", help="Verify downloaded manifest and files.")
    parser.add_argument("--summary", action="store_true", help="Print manifest summary.")
    args = parser.parse_args(argv)

    if args.plan:
        print(plan())
    if args.download:
        manifest = download(args.category)
        print(f"downloads_successful={manifest['downloads_successful']}")
        print(f"downloads_failed={manifest['downloads_failed']}")
        print(f"manifest={MANIFEST_JSON}")
    if args.verify_library:
        ok, message = verify_library()
        print(message)
        if not ok:
            return 1
    if args.summary:
        print(summary_text())
    if not any([args.plan, args.download, args.verify_library, args.summary]):
        print(plan())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
