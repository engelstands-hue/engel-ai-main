from __future__ import annotations

import ast
import json
import os
import py_compile
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
AUTHORITY = "Josh > Guardian > Engel/runtime"
APPROVAL_TOKEN = "APPROVE_CHANGE"
PRODUCT_STATUS = "PRODUCT_ONLY / NOT_RUNTIME / NOT_APPLIED"
PREVIEW_EXTENSIONS = {".md", ".json", ".py", ".java", ".html", ".css", ".js", ".txt"}
DEFAULT_PREVIEW_MAX_CHARS = 12_000
PREVIEW_FILE_ORDER = (
    "README.md",
    "product_manifest.json",
    "src/main.py",
    "src/app.py",
    "src/Main.java",
    "index.html",
    "assets/style.css",
    "assets/app.js",
)
GENERATED_PRODUCT_DIRS = {
    "receipts",
    ".engel_receipts",
    ".engel_backups",
    ".engel_lesson_candidates",
    ".engel_lesson_reviews",
    "dist",
}

TEMPLATE_PYTHON_CLI = "python_cli_starter"
TEMPLATE_PYTHON_GUI = "python_gui_starter"
TEMPLATE_JAVA_CONSOLE = "java_console_starter"
TEMPLATE_HTML_DASHBOARD = "html_dashboard_starter"
TEMPLATE_HTML_MINI_APP = "html_mini_app"

TEMPLATES = (
    {"id": TEMPLATE_PYTHON_CLI, "name": "Python CLI Starter"},
    {"id": TEMPLATE_PYTHON_GUI, "name": "Python GUI Starter"},
    {"id": TEMPLATE_JAVA_CONSOLE, "name": "Java Console Starter"},
    {"id": TEMPLATE_HTML_DASHBOARD, "name": "HTML Dashboard Starter"},
    {"id": TEMPLATE_HTML_MINI_APP, "name": "HTML/CSS/JS Mini App"},
)

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
    "localStorage",
    "password",
    "token",
    "api_key",
    "secret",
)


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    status: str
    message: str
    details: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProductBuildResult:
    template_id: str
    product_slug: str
    files: dict[str, str]
    status: str
    validation: ValidationResult
    safety_notes: list[str] = field(default_factory=list)
    not_runtime: bool = True
    not_applied: bool = True


@dataclass(frozen=True)
class ProductWriteResult:
    ok: bool
    status: str
    product_path: Path | None = None
    files_written: tuple[Path, ...] = ()
    receipt_path: Path | None = None
    backup_path: Path | None = None
    validation: ValidationResult | None = None
    message: str = ""


@dataclass(frozen=True)
class ProductSummary:
    slug: str
    name: str
    path: Path
    exists: bool
    status: str = "UNKNOWN"
    template_id: str = "UNKNOWN"
    file_count: int = 0


@dataclass(frozen=True)
class PreviewResult:
    ok: bool
    status: str
    product_slug: str
    product_path: Path | None = None
    relative_path: str = ""
    file_path: Path | None = None
    content: str = ""
    truncated: bool = False
    message: str = ""


@dataclass(frozen=True)
class OpenFolderResult:
    ok: bool
    status: str
    product_slug: str
    product_path: Path | None = None
    message: str = ""


@dataclass(frozen=True)
class ProductHealthItem:
    name: str
    status: str
    message: str
    detail: str = ""


@dataclass(frozen=True)
class ProductHealthResult:
    ok: bool
    status: str
    product_slug: str
    product_path: Path | None = None
    message: str = ""
    items: tuple[ProductHealthItem, ...] = ()
    profile: dict[str, object] | None = None
    manifest: dict[str, object] | None = None
    receipts: tuple[Path, ...] = ()


@dataclass(frozen=True)
class ProductImprovementProposal:
    ok: bool
    status: str
    product_slug: str
    product_path: Path | None = None
    health_status: str = "UNKNOWN"
    recommended_steps: tuple[str, ...] = ()
    guardian_review: tuple[str, ...] = ()
    safety_notes: tuple[str, ...] = ()
    message: str = ""


def products_root() -> Path:
    return ROOT / "products"


def backups_root() -> Path:
    return ROOT / "backups" / "code_companion"


def _resolve_without_existing(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _has_path_escape(value: str) -> bool:
    text = str(value or "").strip()
    lowered = text.lower()
    if not text:
        return True
    if lowered.startswith(("http://", "https://")):
        return True
    if text.startswith(("\\\\", "//", "\\", "/")):
        return True
    if re.match(r"^[A-Za-z]:", text):
        return True
    parts = re.split(r"[\\/]+", text)
    return any(part in {"", ".", ".."} for part in parts) if len(parts) > 1 else text in {".", ".."}


def safe_product_slug(name: str) -> str:
    original = str(name or "").strip()
    if _has_path_escape(original):
        raise ValueError("Unsafe product name. Use a plain product name, not a path.")
    if original.startswith("."):
        raise ValueError("Unsafe product name. Hidden product names are blocked.")
    words = re.findall(r"[A-Za-z0-9]+", original)
    if not words:
        raise ValueError("Unsafe product name. Use letters or numbers.")
    slug = "_".join(word.lower() for word in words)[:80].strip("_")
    if not slug or slug in {".", ".."}:
        raise ValueError("Unsafe product name produced an empty slug.")
    return slug


def product_path_for_slug(slug: str) -> Path:
    safe_slug = safe_product_slug(slug)
    return products_root() / safe_slug


def _safe_product_dir_for_slug(slug: str) -> Path:
    product_path = product_path_for_slug(slug)
    if not is_safe_product_path(product_path):
        raise ValueError("Product path is outside APP_ROOT/products.")
    return product_path


def is_safe_product_path(path: Path) -> bool:
    root = _resolve_without_existing(products_root())
    candidate = _resolve_without_existing(Path(path))
    if candidate == root:
        return False
    if candidate.parent != root:
        return False
    if candidate.exists() and candidate.is_symlink():
        return False
    try:
        return candidate.name == safe_product_slug(candidate.name)
    except ValueError:
        return False


def list_product_templates() -> list[dict[str, str]]:
    return [dict(template) for template in TEMPLATES]


def product_summary(slug: str) -> ProductSummary:
    safe_slug = safe_product_slug(slug)
    product_path = _safe_product_dir_for_slug(safe_slug)
    exists = product_path.exists() and product_path.is_dir()
    name = safe_slug.replace("_", " ").title()
    status = "MISSING"
    template_id = "UNKNOWN"
    file_count = 0
    if exists:
        for child in product_path.rglob("*"):
            if child.is_file():
                file_count += 1
        manifest_path = product_path / "product_manifest.json"
        if manifest_path.exists() and manifest_path.is_file():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                status = "MANIFEST_UNREADABLE"
            else:
                name = str(manifest.get("name") or name)
                status = str(manifest.get("status") or "UNKNOWN")
                template_id = str(manifest.get("template_id") or "UNKNOWN")
        else:
            status = "NO_MANIFEST"
    return ProductSummary(
        slug=safe_slug,
        name=name,
        path=product_path,
        exists=exists,
        status=status,
        template_id=template_id,
        file_count=file_count,
    )


def list_products() -> list[ProductSummary]:
    root = products_root()
    if not root.exists() or not root.is_dir():
        return []
    summaries: list[ProductSummary] = []
    for child in sorted(root.iterdir(), key=lambda item: item.name.lower()):
        if not child.is_dir() or child.is_symlink():
            continue
        if not is_safe_product_path(child):
            continue
        try:
            summaries.append(product_summary(child.name))
        except ValueError:
            continue
    return summaries


def _template_name(template_id: str) -> str:
    for template in TEMPLATES:
        if template["id"] == template_id:
            return template["name"]
    raise ValueError("Unsupported product template.")


def _normalize_template_id(template_id: str) -> str:
    normalized = str(template_id or "").strip().lower().replace(" ", "_").replace("/", "_")
    aliases = {
        "python_cli": TEMPLATE_PYTHON_CLI,
        "python_gui": TEMPLATE_PYTHON_GUI,
        "java_console": TEMPLATE_JAVA_CONSOLE,
        "html_dashboard": TEMPLATE_HTML_DASHBOARD,
        "html_css_js_mini_app": TEMPLATE_HTML_MINI_APP,
        "html_mini": TEMPLATE_HTML_MINI_APP,
    }
    normalized = aliases.get(normalized, normalized)
    _template_name(normalized)
    return normalized


def _safe_title(product_name: str, slug: str) -> str:
    text = " ".join(re.findall(r"[A-Za-z0-9]+", str(product_name or ""))).strip()
    return text or slug.replace("_", " ").title()


def _manifest(product_name: str, slug: str, template_id: str, files: list[str]) -> str:
    payload = {
        "name": _safe_title(product_name, slug),
        "slug": slug,
        "template_id": template_id,
        "created_by": "Engel Code Companion",
        "status": PRODUCT_STATUS,
        "authority": AUTHORITY,
        "root_policy": "APP_ROOT/products only",
        "generated_files": files,
        "dependencies": [],
        "install_required": False,
    }
    return json.dumps(payload, indent=2) + "\n"


def _readme(product_name: str, slug: str, template_name: str) -> str:
    title = _safe_title(product_name, slug)
    return (
        f"# {title}\n\n"
        f"Status: {PRODUCT_STATUS}\n\n"
        f"Authority: {AUTHORITY}\n\n"
        f"Template: {template_name}\n\n"
        "This starter product is bounded to APP_ROOT/products. It is product-only example code, not Engel runtime source.\n\n"
        "Safety:\n"
        "- No runtime source edits.\n"
        "- No automatic execution.\n"
        "- No external dependencies.\n"
        "- No provider or network calls.\n"
    )


def _python_header() -> str:
    return (
        "# Engel Code Companion Product Template\n"
        f"# Status: {PRODUCT_STATUS}\n"
        f"# Authority: {AUTHORITY}\n"
    )


def _java_header() -> str:
    return (
        "// Engel Code Companion Product Template\n"
        f"// Status: {PRODUCT_STATUS}\n"
        f"// Authority: {AUTHORITY}\n"
    )


def _html_header() -> str:
    return (
        "<!-- Engel Code Companion Product Template -->\n"
        f"<!-- Status: {PRODUCT_STATUS} -->\n"
        f"<!-- Authority: {AUTHORITY} -->\n"
    )


def _css_header() -> str:
    return (
        "/* Engel Code Companion Product Template\n"
        f"   Status: {PRODUCT_STATUS}\n"
        f"   Authority: {AUTHORITY}\n"
        "*/\n"
    )


def _js_header() -> str:
    return (
        "/* Engel Code Companion Product Template\n"
        f"   Status: {PRODUCT_STATUS}\n"
        f"   Authority: {AUTHORITY}\n"
        "*/\n"
    )


def _python_cli_files(product_name: str, slug: str) -> dict[str, str]:
    files = {
        "README.md": _readme(product_name, slug, "Python CLI Starter"),
        "src/main.py": (
            _python_header()
            + "\n"
            + "def main():\n"
            + "    message = \"Hello from an Engel product-only CLI starter.\"\n"
            + f"    product_slug = \"{slug}\"\n"
            + "    print(message)\n"
            + "    print(\"Product:\", product_slug)\n"
            + f"    print(\"Status: {PRODUCT_STATUS}\")\n\n"
            + "\nif __name__ == \"__main__\":\n"
            + "    main()\n"
        ),
        "tests/test_smoke.py": (
            _python_header()
            + "\n"
            + "from pathlib import Path\n\n"
            + "\n"
            + "def test_cli_source_exists():\n"
            + "    root = Path(__file__).resolve().parents[1]\n"
            + "    source = root / \"src\" / \"main.py\"\n"
            + "    assert source.exists()\n"
            + "    assert \"PRODUCT_ONLY / NOT_RUNTIME / NOT_APPLIED\" in source.read_text(encoding=\"utf-8\")\n"
        ),
    }
    files["product_manifest.json"] = _manifest(product_name, slug, TEMPLATE_PYTHON_CLI, sorted([*files, "product_manifest.json"]))
    return files


def _python_gui_files(product_name: str, slug: str) -> dict[str, str]:
    files = {
        "README.md": _readme(product_name, slug, "Python GUI Starter"),
        "src/app.py": (
            _python_header()
            + "\n"
            + "import tkinter as tk\n\n"
            + "\n"
            + "def build_window():\n"
            + "    window = tk.Tk()\n"
            + "    window.title(\"Engel Product Starter\")\n"
            + "    label = tk.Label(window, text=\"Hello from an Engel product-only GUI starter.\", padx=18, pady=18)\n"
            + "    label.pack()\n"
            + "    status = tk.Label(window, text=\"PRODUCT_ONLY / NOT_RUNTIME / NOT_APPLIED\")\n"
            + "    status.pack()\n"
            + "    return window\n\n"
            + "\n"
            + "def main():\n"
            + "    window = build_window()\n"
            + "    window.mainloop()\n"
        ),
        "tests/test_smoke.py": (
            _python_header()
            + "\n"
            + "from pathlib import Path\n\n"
            + "\n"
            + "def test_gui_source_exists():\n"
            + "    root = Path(__file__).resolve().parents[1]\n"
            + "    assert (root / \"src\" / \"app.py\").exists()\n"
        ),
    }
    files["product_manifest.json"] = _manifest(product_name, slug, TEMPLATE_PYTHON_GUI, sorted([*files, "product_manifest.json"]))
    return files


def _java_console_files(product_name: str, slug: str) -> dict[str, str]:
    files = {
        "README.md": _readme(product_name, slug, "Java Console Starter"),
        "src/Main.java": (
            _java_header()
            + "\n"
            + "public class Main {\n"
            + "    public static void main(String[] args) {\n"
            + "        System.out.println(\"Hello from an Engel product-only Java starter.\");\n"
            + f"        System.out.println(\"Product: {slug}\");\n"
            + f"        System.out.println(\"Status: {PRODUCT_STATUS}\");\n"
            + "    }\n"
            + "}\n"
        ),
    }
    files["product_manifest.json"] = _manifest(product_name, slug, TEMPLATE_JAVA_CONSOLE, sorted([*files, "product_manifest.json"]))
    return files


def _html_dashboard_files(product_name: str, slug: str) -> dict[str, str]:
    title = _safe_title(product_name, slug)
    files = {
        "README.md": _readme(product_name, slug, "HTML Dashboard Starter"),
        "index.html": (
            _html_header()
            + "<!doctype html>\n"
            + "<html lang=\"en\">\n"
            + "<head>\n"
            + "  <meta charset=\"utf-8\">\n"
            + "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
            + f"  <title>{title}</title>\n"
            + "  <style>\n"
            + "    body { margin: 0; font-family: Arial, sans-serif; background: #111827; color: #f8fafc; }\n"
            + "    main { max-width: 860px; margin: 0 auto; padding: 32px; }\n"
            + "    section { border: 1px solid #334155; border-radius: 8px; padding: 16px; background: #1f2937; }\n"
            + "    .badge { display: inline-block; margin: 4px 6px 4px 0; padding: 5px 8px; border-radius: 999px; background: #0f766e; }\n"
            + "  </style>\n"
            + "</head>\n"
            + "<body>\n"
            + "  <main>\n"
            + f"    <h1>{title}</h1>\n"
            + "    <section>\n"
            + "      <h2>Product Status</h2>\n"
            + "      <span class=\"badge\">PRODUCT ONLY</span>\n"
            + "      <span class=\"badge\">NOT RUNTIME</span>\n"
            + "      <span class=\"badge\">NOT APPLIED</span>\n"
            + "      <p id=\"statusText\">Local dashboard starter created safely.</p>\n"
            + "    </section>\n"
            + "  </main>\n"
            + "  <script>\n"
            + "    const statusText = document.getElementById('statusText');\n"
            + "    statusText.textContent = 'Local dashboard starter created safely.';\n"
            + "  </script>\n"
            + "</body>\n"
            + "</html>\n"
        ),
    }
    files["product_manifest.json"] = _manifest(product_name, slug, TEMPLATE_HTML_DASHBOARD, sorted([*files, "product_manifest.json"]))
    return files


def _html_mini_app_files(product_name: str, slug: str) -> dict[str, str]:
    title = _safe_title(product_name, slug)
    files = {
        "README.md": _readme(product_name, slug, "HTML/CSS/JS Mini App"),
        "index.html": (
            _html_header()
            + "<!doctype html>\n"
            + "<html lang=\"en\">\n"
            + "<head>\n"
            + "  <meta charset=\"utf-8\">\n"
            + "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
            + f"  <title>{title}</title>\n"
            + "  <link rel=\"stylesheet\" href=\"assets/style.css\">\n"
            + "</head>\n"
            + "<body>\n"
            + "  <main>\n"
            + f"    <h1>{title}</h1>\n"
            + "    <button id=\"countButton\" type=\"button\">Count</button>\n"
            + "    <p id=\"countLabel\">Count: 0</p>\n"
            + "  </main>\n"
            + "  <script src=\"assets/app.js\"></script>\n"
            + "</body>\n"
            + "</html>\n"
        ),
        "assets/style.css": (
            _css_header()
            + "body { margin: 0; font-family: Arial, sans-serif; background: #f8fafc; color: #111827; }\n"
            + "main { max-width: 720px; margin: 0 auto; padding: 32px; }\n"
            + "button { padding: 8px 12px; border: 1px solid #0f766e; background: #0f766e; color: white; border-radius: 6px; }\n"
        ),
        "assets/app.js": (
            _js_header()
            + "const countButton = document.getElementById('countButton');\n"
            + "const countLabel = document.getElementById('countLabel');\n"
            + "let count = 0;\n"
            + "countButton.addEventListener('click', () => {\n"
            + "  count += 1;\n"
            + "  countLabel.textContent = `Count: ${count}`;\n"
            + "});\n"
        ),
    }
    files["product_manifest.json"] = _manifest(product_name, slug, TEMPLATE_HTML_MINI_APP, sorted([*files, "product_manifest.json"]))
    return files


def build_product_template(template_id: str, product_name: str, prompt: str = "") -> ProductBuildResult:
    normalized_template = _normalize_template_id(template_id)
    slug = safe_product_slug(product_name)
    builders = {
        TEMPLATE_PYTHON_CLI: _python_cli_files,
        TEMPLATE_PYTHON_GUI: _python_gui_files,
        TEMPLATE_JAVA_CONSOLE: _java_console_files,
        TEMPLATE_HTML_DASHBOARD: _html_dashboard_files,
        TEMPLATE_HTML_MINI_APP: _html_mini_app_files,
    }
    files = builders[normalized_template](product_name, slug)
    validation = validate_product_files(files)
    notes = [
        "Products are bounded to APP_ROOT/products.",
        "Generated files are PRODUCT_ONLY / NOT_RUNTIME / NOT_APPLIED.",
        "No Engel runtime source edits are generated.",
        "Generated product code is not executed automatically.",
    ]
    if prompt and re.search(r"\binstall\b|\bdependency\b|\bpackage\b", prompt, re.IGNORECASE):
        notes.append("Install or dependency requests remain proposal-only and require separate approval.")
    return ProductBuildResult(
        template_id=normalized_template,
        product_slug=slug,
        files=files,
        status="PRODUCT_TEMPLATE_BUILT" if validation.ok else "PRODUCT_TEMPLATE_BLOCKED",
        validation=validation,
        safety_notes=notes,
    )


def _relative_file_path(path_text: str) -> Path:
    raw = str(path_text or "").strip().replace("\\", "/")
    if _has_path_escape(raw):
        raise ValueError("Unsafe product file path: " + str(path_text))
    relative = Path(raw)
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        raise ValueError("Unsafe product file path: " + str(path_text))
    if any(part.startswith(".") for part in relative.parts):
        raise ValueError("Hidden product file paths are blocked: " + str(path_text))
    return relative


def _unsafe_hits(content: str) -> list[str]:
    lowered = str(content or "").lower()
    return sorted({pattern for pattern in UNSAFE_CONTENT_PATTERNS if pattern.lower() in lowered})


def validate_product_files(files: dict[str, str]) -> ValidationResult:
    if not isinstance(files, dict) or not files:
        return ValidationResult(False, "PRODUCT_FILES_INVALID", "No product files were provided.")
    if "README.md" not in files or "product_manifest.json" not in files:
        return ValidationResult(False, "PRODUCT_FILES_INVALID", "README.md and product_manifest.json are required.")

    details: list[str] = []
    for relative_text, content in files.items():
        try:
            relative = _relative_file_path(relative_text)
        except ValueError as exc:
            return ValidationResult(False, "PRODUCT_PATH_BLOCKED", str(exc))
        text = str(content or "")
        unsafe = _unsafe_hits(text)
        if unsafe:
            return ValidationResult(False, "UNSAFE_PRODUCT_CONTENT", "Unsafe product content in " + relative_text, tuple(unsafe))
        if PRODUCT_STATUS not in text:
            return ValidationResult(False, "PRODUCT_BOUNDARY_MISSING", "Missing product-only status in " + relative_text)
        if AUTHORITY not in text:
            return ValidationResult(False, "AUTHORITY_MISSING", "Missing authority text in " + relative_text)

        suffix = relative.suffix.lower()
        if suffix == ".py":
            try:
                ast.parse(text, filename=str(relative))
            except SyntaxError as exc:
                return ValidationResult(False, "PYTHON_AST_FAILED", f"{relative_text}: {exc}")
            details.append(f"{relative_text}: PYTHON_AST_OK")
        elif suffix == ".java":
            if relative.name == "Main.java" and "public class Main" not in text:
                return ValidationResult(False, "JAVA_CLASS_MISMATCH", "Main.java must contain public class Main.")
            details.append(f"{relative_text}: JAVA_TEXT_OK")
        elif suffix == ".html":
            lowered = text.lower()
            for tag in ("<!doctype html>", "<html", "<head", "<body"):
                if tag not in lowered:
                    return ValidationResult(False, "HTML_BASIC_STRUCTURE_FAILED", f"{relative_text} missing {tag}")
            details.append(f"{relative_text}: HTML_BASIC_STRUCTURE_OK")
        elif suffix not in {".md", ".json", ".css", ".js"}:
            return ValidationResult(False, "PRODUCT_EXTENSION_BLOCKED", "Unsupported product file type: " + relative_text)

    try:
        manifest = json.loads(files["product_manifest.json"])
    except json.JSONDecodeError as exc:
        return ValidationResult(False, "MANIFEST_INVALID", "Manifest JSON failed: " + str(exc))
    expected_manifest = {
        "created_by": "Engel Code Companion",
        "status": PRODUCT_STATUS,
        "authority": AUTHORITY,
        "root_policy": "APP_ROOT/products only",
        "dependencies": [],
        "install_required": False,
    }
    for key, expected in expected_manifest.items():
        if manifest.get(key) != expected:
            return ValidationResult(False, "MANIFEST_INVALID", "Manifest field mismatch: " + key)
    generated_files = manifest.get("generated_files")
    if not isinstance(generated_files, list) or not generated_files:
        return ValidationResult(False, "MANIFEST_INVALID", "Manifest generated_files must list product files.")
    return ValidationResult(True, "PRODUCT_FILES_VALID", "Product files passed bounded validation.", tuple(details))


def _target_for_relative(product_path: Path, relative_text: str) -> Path:
    relative = _relative_file_path(relative_text)
    target = _resolve_without_existing(product_path / relative)
    product_root = _resolve_without_existing(product_path)
    if not _is_relative_to(target, product_root):
        raise ValueError("Product file escaped product root: " + relative_text)
    return target


def _relative_preview_path(path_text: str) -> Path:
    relative = _relative_file_path(path_text)
    if relative.suffix.lower() not in PREVIEW_EXTENSIONS:
        raise ValueError("Preview blocked for unsupported file type: " + str(path_text))
    return relative


def _relative_text(product_path: Path, path: Path) -> str:
    return str(path.relative_to(product_path)).replace("\\", "/")


def _is_generated_product_relative(relative: Path) -> bool:
    return bool(relative.parts and relative.parts[0] in GENERATED_PRODUCT_DIRS)


def _preview_sort_key(product_path: Path, path: Path) -> tuple[int, str]:
    relative = _relative_text(product_path, path)
    preferred = {item.lower(): index for index, item in enumerate(PREVIEW_FILE_ORDER)}
    return (preferred.get(relative.lower(), len(PREVIEW_FILE_ORDER)), relative.lower())


def safe_product_file_candidates(slug: str) -> list[Path]:
    safe_slug = safe_product_slug(slug)
    product_path = _safe_product_dir_for_slug(safe_slug)
    if not product_path.exists() or not product_path.is_dir():
        return []
    candidates: list[Path] = []
    product_root = _resolve_without_existing(product_path)
    for path in product_path.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(product_path)
        if _is_generated_product_relative(relative):
            continue
        if path.suffix.lower() not in PREVIEW_EXTENSIONS:
            continue
        resolved = _resolve_without_existing(path)
        if not _is_relative_to(resolved, product_root):
            continue
        candidates.append(path)
    return sorted(candidates, key=lambda path: _preview_sort_key(product_path, path))


def safe_product_file_choices(slug: str) -> list[str]:
    safe_slug = safe_product_slug(slug)
    product_path = _safe_product_dir_for_slug(safe_slug)
    return [_relative_text(product_path, path) for path in safe_product_file_candidates(safe_slug)]


def _default_preview_relative(product_path: Path, candidates: list[Path]) -> str:
    preferred = ("README.md", "product_manifest.json")
    by_relative = {str(path.relative_to(product_path)).replace("\\", "/"): path for path in candidates}
    for relative in preferred:
        if relative in by_relative:
            return relative
    if candidates:
        return str(candidates[0].relative_to(product_path)).replace("\\", "/")
    return ""


def preview_product_file(slug: str, relative_path: str | None = "", max_chars: int = DEFAULT_PREVIEW_MAX_CHARS) -> PreviewResult:
    try:
        safe_slug = safe_product_slug(slug)
        product_path = _safe_product_dir_for_slug(safe_slug)
    except ValueError as exc:
        return PreviewResult(False, "PRODUCT_PREVIEW_BLOCKED", str(slug or ""), message=str(exc))
    if not product_path.exists() or not product_path.is_dir():
        return PreviewResult(False, "PRODUCT_MISSING", safe_slug, product_path=product_path, message="Product folder does not exist.")

    candidates = safe_product_file_candidates(safe_slug)
    selected_relative = str(relative_path or "").strip().replace("\\", "/")
    if not selected_relative:
        selected_relative = _default_preview_relative(product_path, candidates)
    if not selected_relative:
        return PreviewResult(False, "NO_PREVIEWABLE_PRODUCT_FILES", safe_slug, product_path=product_path, message="No safe text product file is available.")

    try:
        relative = _relative_preview_path(selected_relative)
        target = _target_for_relative(product_path, str(relative).replace("\\", "/"))
    except ValueError as exc:
        return PreviewResult(False, "PRODUCT_PREVIEW_BLOCKED", safe_slug, product_path=product_path, relative_path=selected_relative, message=str(exc))
    if not target.exists() or not target.is_file():
        return PreviewResult(False, "PRODUCT_FILE_MISSING", safe_slug, product_path=product_path, relative_path=selected_relative, file_path=target, message="Preview file does not exist.")

    try:
        with target.open("rb") as raw:
            sample = raw.read(4096)
        if b"\0" in sample:
            return PreviewResult(False, "BINARY_PREVIEW_BLOCKED", safe_slug, product_path=product_path, relative_path=selected_relative, file_path=target, message="Binary preview is blocked.")
        limit = max(1, int(max_chars))
        with target.open("r", encoding="utf-8", errors="replace") as handle:
            content = handle.read(limit + 1)
    except (OSError, UnicodeError, ValueError) as exc:
        return PreviewResult(False, "PRODUCT_PREVIEW_FAILED", safe_slug, product_path=product_path, relative_path=selected_relative, file_path=target, message=str(exc))

    truncated = len(content) > max(1, int(max_chars))
    if truncated:
        content = content[: max(1, int(max_chars))]
    status = "TRUNCATED_PREVIEW" if truncated else "PRODUCT_PREVIEW_OK"
    return PreviewResult(
        True,
        status,
        safe_slug,
        product_path=product_path,
        relative_path=str(relative).replace("\\", "/"),
        file_path=target,
        content=content,
        truncated=truncated,
        message="Read-only preview. Product content was not executed or applied.",
    )


def open_product_folder(slug: str) -> OpenFolderResult:
    try:
        safe_slug = safe_product_slug(slug)
        product_path = _safe_product_dir_for_slug(safe_slug)
    except ValueError as exc:
        return OpenFolderResult(False, "OPEN_FOLDER_BLOCKED", str(slug or ""), message=str(exc))
    if not product_path.exists() or not product_path.is_dir():
        return OpenFolderResult(False, "PRODUCT_MISSING", safe_slug, product_path=product_path, message="Product folder does not exist.")
    startfile = getattr(os, "startfile", None)
    if startfile is None:
        return OpenFolderResult(False, "OPEN_FOLDER_UNAVAILABLE", safe_slug, product_path=product_path, message="Opening folders is unavailable on this platform.")
    try:
        startfile(str(product_path))
    except OSError as exc:
        return OpenFolderResult(False, "OPEN_FOLDER_FAILED", safe_slug, product_path=product_path, message=str(exc))
    return OpenFolderResult(True, "OPEN_FOLDER_OK", safe_slug, product_path=product_path, message=str(product_path))


def _relative_health_json_path(path_text: str) -> Path:
    raw = str(path_text or "").strip().replace("\\", "/")
    if _has_path_escape(raw):
        raise ValueError("Unsafe product JSON path: " + str(path_text))
    relative = Path(raw)
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        raise ValueError("Unsafe product JSON path: " + str(path_text))
    normalized = str(relative).replace("\\", "/")
    allowed = {
        ".engel_product_profile.json",
        "product_manifest.json",
        "dist/ENGEL_PACKAGE_MANIFEST.json",
    }
    if normalized not in allowed:
        raise ValueError("Product health JSON read is limited to known product metadata files.")
    return relative


def safe_read_product_json(slug: str, relative_path: str) -> dict[str, object]:
    safe_slug = safe_product_slug(slug)
    product_path = _safe_product_dir_for_slug(safe_slug)
    relative = _relative_health_json_path(relative_path)
    target = _resolve_without_existing(product_path / relative)
    product_root = _resolve_without_existing(product_path)
    if not _is_relative_to(target, product_root):
        raise ValueError("Product JSON escaped product root: " + str(relative_path))
    if not target.exists() or not target.is_file() or target.is_symlink():
        raise FileNotFoundError("Product JSON file is missing: " + str(relative_path))
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Product JSON file could not be read: " + str(exc)) from exc
    if not isinstance(payload, dict):
        raise ValueError("Product JSON root must be an object: " + str(relative_path))
    return payload


def latest_product_receipts(slug: str) -> list[Path]:
    safe_slug = safe_product_slug(slug)
    product_path = _safe_product_dir_for_slug(safe_slug)
    if not product_path.exists() or not product_path.is_dir():
        return []
    receipts: list[Path] = []
    product_root = _resolve_without_existing(product_path)
    for folder_name in (".engel_receipts", "receipts"):
        receipt_dir = product_path / folder_name
        if not receipt_dir.exists() or not receipt_dir.is_dir() or receipt_dir.is_symlink():
            continue
        for path in receipt_dir.iterdir():
            if not path.is_file() or path.is_symlink() or path.suffix.lower() != ".md":
                continue
            resolved = _resolve_without_existing(path)
            if _is_relative_to(resolved, product_root):
                receipts.append(path)
    return sorted(receipts, key=lambda path: (path.stat().st_mtime, path.name.lower()), reverse=True)


def _health_item(name: str, status: str, message: str, detail: str = "") -> ProductHealthItem:
    normalized = status if status in {"PASS", "WARN", "BLOCKED", "INFO"} else "INFO"
    return ProductHealthItem(name, normalized, message, detail)


def _profile_list(profile: dict[str, object] | None, key: str) -> list[dict[str, object]]:
    if not profile:
        return []
    value = profile.get(key)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _command_text(profile: dict[str, object]) -> str:
    command = profile.get("command")
    if not isinstance(command, list):
        return ""
    return " ".join(str(part) for part in command)


def _source_file_relatives(slug: str, product_path: Path) -> list[str]:
    source_suffixes = {".py", ".java", ".html", ".css", ".js"}
    source_files: list[str] = []
    for path in safe_product_file_candidates(slug):
        relative = _relative_text(product_path, path)
        if relative.startswith(("receipts/", ".engel_receipts/", ".engel_backups/", "dist/")):
            continue
        if path.suffix.lower() in source_suffixes:
            source_files.append(relative)
    return source_files


def _profile_product_type(profile: dict[str, object] | None, manifest: dict[str, object] | None) -> str:
    if profile:
        product_type = profile.get("product_type")
        if product_type:
            return str(product_type)
    if manifest:
        template_id = str(manifest.get("template_id") or "").lower()
        template_type_map = {
            TEMPLATE_PYTHON_CLI: "python_script",
            TEMPLATE_PYTHON_GUI: "python_app",
            TEMPLATE_JAVA_CONSOLE: "java_app",
            TEMPLATE_HTML_DASHBOARD: "html_website",
            TEMPLATE_HTML_MINI_APP: "html_website",
        }
        return template_type_map.get(template_id, template_id or "unknown")
    return "unknown"


def _launch_health(profile: dict[str, object] | None, manifest: dict[str, object] | None) -> ProductHealthItem:
    product_type = _profile_product_type(profile, manifest)
    if profile is None:
        return _health_item("Launch profile", "WARN", "No product profile is available to confirm launch readiness.")
    launch_profiles = _profile_list(profile, "allowed_launch_profiles")
    if not launch_profiles:
        if product_type in {"html_website", "java_app", "engel_module", "custom_project"}:
            return _health_item("Launch profile", "INFO", "Launch is unsupported or instructions-only by design for this product type.")
        return _health_item("Launch profile", "WARN", "No launch profile is present.")
    blocked: list[str] = []
    approved: list[str] = []
    disabled: list[str] = []
    for item in launch_profiles:
        name = str(item.get("name") or "Launch Profile")
        command = _command_text(item)
        if not command:
            disabled.append(name)
            continue
        if item.get("requires_approval") is not True:
            blocked.append(name + " lacks APPROVE_LAUNCH gate")
            continue
        if product_type == "java_app":
            approved.append(name + " is explicitly profiled; Java launch remains proposal-only/disabled unless supported by profile")
        elif product_type in {"python_script", "python_app", "utility_tool"} and not command.startswith("python "):
            blocked.append(name + " is not a fixed python launch command")
        else:
            approved.append(name + " / APPROVE_LAUNCH required")
    if blocked:
        return _health_item("Launch profile", "BLOCKED", "Unsafe or ungated launch profile found.", "; ".join(blocked))
    if approved:
        return _health_item("Launch profile", "PASS", "Fixed launch profile is approval-gated.", "; ".join(approved))
    return _health_item("Launch profile", "INFO", "Launch profiles are present but disabled/instructions-only.", "; ".join(disabled))


def _package_health(profile: dict[str, object] | None) -> ProductHealthItem:
    if profile is None:
        return _health_item("Package profile", "WARN", "No product profile is available to confirm package readiness.")
    package_profiles = _profile_list(profile, "allowed_package_profiles")
    if not package_profiles:
        return _health_item("Package profile", "WARN", "No package profile is present.")
    blocked: list[str] = []
    approved: list[str] = []
    for item in package_profiles:
        name = str(item.get("name") or "Package Profile")
        mode = str(item.get("mode") or "")
        if item.get("requires_approval") is not True:
            blocked.append(name + " lacks APPROVE_PACKAGE gate")
        elif mode != "source_zip":
            blocked.append(name + " is not source_zip")
        else:
            approved.append(name + " / APPROVE_PACKAGE required")
    if blocked:
        return _health_item("Package profile", "BLOCKED", "Unsafe or ungated package profile found.", "; ".join(blocked))
    return _health_item("Package profile", "PASS", "Source zip package profile is approval-gated.", "; ".join(approved))


def product_health_check(slug: str) -> ProductHealthResult:
    try:
        safe_slug = safe_product_slug(slug)
        product_path = _safe_product_dir_for_slug(safe_slug)
    except ValueError as exc:
        return ProductHealthResult(False, "BLOCKED", str(slug or ""), message=str(exc))

    items: list[ProductHealthItem] = []
    profile: dict[str, object] | None = None
    manifest: dict[str, object] | None = None
    receipts: list[Path] = []

    if not product_path.exists() or not product_path.is_dir():
        items.append(_health_item("Product folder", "BLOCKED", "Product folder does not exist."))
        return ProductHealthResult(False, "BLOCKED", safe_slug, product_path=product_path, items=tuple(items))
    items.append(_health_item("Product folder", "PASS", "Product path is a direct child of APP_ROOT/products."))

    try:
        profile = safe_read_product_json(safe_slug, ".engel_product_profile.json")
    except FileNotFoundError:
        items.append(_health_item("Profile", "WARN", ".engel_product_profile.json is not present."))
    except ValueError as exc:
        items.append(_health_item("Profile", "WARN", ".engel_product_profile.json could not be parsed.", str(exc)))
    else:
        schema = str(profile.get("schema") or "")
        status = "PASS" if schema == "engel_product_profile_v1" else "WARN"
        message = "Product profile parsed." if status == "PASS" else "Product profile schema is unexpected."
        items.append(_health_item("Profile", status, message, "schema=" + (schema or "missing")))

    try:
        manifest = safe_read_product_json(safe_slug, "product_manifest.json")
    except FileNotFoundError:
        items.append(_health_item("Manifest", "WARN", "product_manifest.json is not present."))
    except ValueError as exc:
        items.append(_health_item("Manifest", "WARN", "product_manifest.json could not be parsed.", str(exc)))
    else:
        status_text = str(manifest.get("status") or "")
        status = "PASS" if PRODUCT_STATUS in status_text else "WARN"
        message = "Manifest parsed." if status == "PASS" else "Manifest is missing product-only status."
        items.append(_health_item("Manifest", status, message, "status=" + (status_text or "missing")))

    readme = product_path / "README.md"
    if readme.exists() and readme.is_file() and not readme.is_symlink():
        items.append(_health_item("README", "PASS", "README.md is present."))
    else:
        items.append(_health_item("README", "WARN", "README.md is recommended but missing."))

    sources = _source_file_relatives(safe_slug, product_path)
    if sources:
        items.append(_health_item("Source files", "PASS", "Previewable source files are present.", ", ".join(sources[:8])))
    else:
        items.append(_health_item("Source files", "WARN", "No previewable source files were found."))

    items.append(_launch_health(profile, manifest))
    items.append(_package_health(profile))

    receipts = latest_product_receipts(safe_slug)
    if receipts:
        latest = receipts[0]
        items.append(_health_item("Receipts", "INFO", f"{len(receipts)} receipt file(s) found.", _relative_text(product_path, latest)))
    else:
        items.append(_health_item("Receipts", "INFO", "No product receipts found yet."))

    launch_receipts = [path for path in receipts if path.name.startswith("launch_receipt_")]
    package_receipts = [path for path in receipts if path.name.startswith("package_receipt_")]
    items.append(
        _health_item(
            "Last launch receipt",
            "INFO",
            "found" if launch_receipts else "none",
            _relative_text(product_path, launch_receipts[0]) if launch_receipts else "",
        )
    )
    items.append(
        _health_item(
            "Last package receipt",
            "INFO",
            "found" if package_receipts else "none",
            _relative_text(product_path, package_receipts[0]) if package_receipts else "",
        )
    )

    dist = product_path / "dist"
    dist_zips = sorted(dist.glob("*.zip"), key=lambda path: (path.stat().st_mtime, path.name.lower()), reverse=True) if dist.exists() and dist.is_dir() else []
    if dist_zips:
        items.append(_health_item("Dist package", "INFO", "source zip found", _relative_text(product_path, dist_zips[0])))
    else:
        items.append(_health_item("Dist package", "INFO", "none"))
    package_manifest: dict[str, object] | None = None
    try:
        package_manifest = safe_read_product_json(safe_slug, "dist/ENGEL_PACKAGE_MANIFEST.json")
    except FileNotFoundError:
        package_manifest = None
    except ValueError as exc:
        package_manifest = None
        items.append(_health_item("Package manifest", "WARN", "ENGEL_PACKAGE_MANIFEST.json could not be parsed.", str(exc)))
    else:
        schema = str(package_manifest.get("schema") or "")
        status = "PASS" if schema == "engel_package_manifest_v1" else "WARN"
        items.append(_health_item("Package manifest", status, "ENGEL_PACKAGE_MANIFEST.json found.", "schema=" + (schema or "missing")))
    if package_manifest is None:
        items.append(_health_item("Package manifest", "INFO", "none"))

    items.append(
        _health_item(
            "Package exclusions",
            "INFO",
            "V3 source packages exclude dist, receipts, backups, env files, and credential-looking files before writing.",
        )
    )

    statuses = {item.status for item in items}
    overall = "BLOCKED" if "BLOCKED" in statuses else "PASS_WITH_WARNINGS" if "WARN" in statuses else "PASS"
    return ProductHealthResult(
        overall != "BLOCKED",
        overall,
        safe_slug,
        product_path=product_path,
        items=tuple(items),
        profile=profile,
        manifest=manifest,
        receipts=tuple(receipts),
    )


def render_product_health(result: ProductHealthResult) -> str:
    root_text = "blocked"
    if result.product_path is not None:
        try:
            root_text = str(result.product_path.relative_to(ROOT)).replace("\\", "/")
        except ValueError:
            root_text = str(result.product_path)
    lines = [
        "# PRODUCT HEALTH CHECK",
        "",
        "Product: " + result.product_slug,
        "Root: " + root_text,
        "Status: " + result.status,
        "",
    ]
    for item in result.items:
        line = f"{item.name}: {item.status} / {item.message}"
        if item.detail:
            line += " / " + item.detail
        lines.append(line)
    lines.extend(
        [
            "",
            "Safety:",
            "- Read-only health check.",
            "- No product code executed.",
            "- No launch, package, install, or apply action ran.",
            "- Product remains PRODUCT_ONLY / NOT_RUNTIME / NOT_APPLIED.",
        ]
    )
    return "\n".join(lines)


def _health_status_by_name(result: ProductHealthResult) -> dict[str, ProductHealthItem]:
    return {item.name.lower(): item for item in result.items}


def _has_tests(slug: str, product_path: Path) -> bool:
    for path in safe_product_file_candidates(slug):
        relative = _relative_text(product_path, path).lower()
        if relative.startswith("tests/") or Path(relative).name.startswith("test_"):
            return True
    return False


def _proposal_product_type(result: ProductHealthResult) -> str:
    return _profile_product_type(result.profile, result.manifest)


def _append_unique(items: list[str], text: str) -> None:
    if text not in items:
        items.append(text)


def build_product_improvement_proposal(slug: str) -> ProductImprovementProposal:
    health = product_health_check(slug)
    if not health.ok or health.product_path is None:
        return ProductImprovementProposal(
            False,
            "PROPOSAL_BLOCKED",
            health.product_slug,
            product_path=health.product_path,
            health_status=health.status,
            message=health.message or "Product health check blocked improvement proposal.",
            safety_notes=(
                "PROPOSAL_ONLY",
                "NOT_APPLIED",
                "PRODUCT_ONLY",
                "NOT_RUNTIME",
                "No files were changed.",
            ),
        )

    by_name = _health_status_by_name(health)
    product_type = _proposal_product_type(health)
    steps: list[str] = []

    if by_name.get("readme") and by_name["readme"].status != "PASS":
        _append_unique(steps, "Add README usage examples and bounded verification notes.")
    elif by_name.get("readme") and by_name["readme"].status == "PASS":
        _append_unique(steps, "Review README usage examples for current launch/package approval wording.")

    if by_name.get("manifest") and by_name["manifest"].status != "PASS":
        _append_unique(steps, "Add or refresh product_manifest.json as product-only metadata.")
    if by_name.get("profile") and by_name["profile"].status != "PASS":
        _append_unique(steps, "Add .engel_product_profile.json before launch or package work.")
    if by_name.get("source files") and by_name["source files"].status != "PASS":
        _append_unique(steps, "Add a safe product entrypoint/source file proposal inside the product folder.")
    if not _has_tests(health.product_slug, health.product_path):
        _append_unique(steps, "Add or refresh a smoke test that can be validated without network, shell, or package install.")

    launch_item = by_name.get("launch profile")
    if launch_item and launch_item.status == "WARN":
        _append_unique(steps, "Create or refresh launch profile metadata; run only after APPROVE_LAUNCH.")
    elif launch_item and "unsupported" in launch_item.message.lower():
        _append_unique(steps, "Keep launch disabled or instructions-only unless Josh approves a fixed bounded profile.")
    elif launch_item and launch_item.status == "PASS":
        _append_unique(steps, "Launch only after previewing the fixed command and entering APPROVE_LAUNCH.")

    package_item = by_name.get("package profile")
    if package_item and package_item.status == "WARN":
        _append_unique(steps, "Create or refresh a source_zip package profile before packaging.")
    elif package_item and package_item.status == "PASS":
        _append_unique(steps, "Package only after previewing source_zip output and entering APPROVE_PACKAGE.")

    last_launch = by_name.get("last launch receipt")
    if last_launch and last_launch.message == "none":
        _append_unique(steps, "Run approved launch later only if the fixed profile is safe and APPROVE_LAUNCH is entered.")
    last_package = by_name.get("last package receipt")
    if last_package and last_package.message == "none":
        _append_unique(steps, "Create package receipt later only through APPROVE_PACKAGE-gated packaging.")
    dist_package = by_name.get("dist package")
    package_manifest = by_name.get("package manifest")
    if (dist_package and dist_package.message == "none") or (package_manifest and package_manifest.message == "none"):
        _append_unique(steps, "Create a source zip under dist only after APPROVE_PACKAGE; keep sensitive files excluded.")

    if product_type == "java_app":
        _append_unique(steps, "Keep Java launch disabled/proposal-only unless a future approved compiled-output profile exists.")
    elif product_type in {"html_website", "html_dashboard_starter", "html_mini_app"}:
        _append_unique(steps, "Keep HTML local-only with no remote resources, fetch, or browser automation.")
    elif product_type in {"python_script", "python_app", "utility_tool", TEMPLATE_PYTHON_CLI, TEMPLATE_PYTHON_GUI}:
        _append_unique(steps, "Keep Python standard-library-only by default; no network, shell, or package install.")

    receipts_item = by_name.get("receipts")
    if receipts_item and receipts_item.message.startswith("No product receipts"):
        _append_unique(steps, "Save receipts after approved verification, launch, or package actions.")

    if not steps:
        steps.append("No urgent gaps detected; keep using Health, Preview, and approval-gated launch/package checks before changes.")

    guardian_review = (
        "Authority: " + AUTHORITY,
        "Runtime source edit: NO",
        "Product-only change: YES",
        "Network/package install: NO",
        "Launch/package action now: NO",
        "Approval required before apply: YES",
        "Guardian review required before applying any future product change: YES",
    )
    safety_notes = (
        "PROPOSAL_ONLY",
        "NOT_APPLIED",
        "JOSH_APPROVAL_REQUIRED",
        "GUARDIAN_REVIEW_REQUIRED",
        "PRODUCT_ONLY",
        "NOT_RUNTIME",
        "No files were changed.",
        "Product code was not executed.",
        "Proposal is not trusted memory.",
    )
    return ProductImprovementProposal(
        True,
        "PROPOSAL_ONLY / NOT_APPLIED",
        health.product_slug,
        product_path=health.product_path,
        health_status=health.status,
        recommended_steps=tuple(steps),
        guardian_review=guardian_review,
        safety_notes=safety_notes,
        message="Deterministic product improvement proposal generated from bounded health data.",
    )


def render_product_improvement_proposal(proposal: ProductImprovementProposal) -> str:
    root_text = "blocked"
    if proposal.product_path is not None:
        try:
            root_text = str(proposal.product_path.relative_to(ROOT)).replace("\\", "/")
        except ValueError:
            root_text = str(proposal.product_path)
    lines = [
        "# PRODUCT IMPROVEMENT PROPOSAL",
        "",
        "Product: " + proposal.product_slug,
        "Root: " + root_text,
        "Status: " + proposal.status,
        "Health status: " + proposal.health_status,
        "Authority: " + AUTHORITY,
        "",
        "Recommended next steps:",
    ]
    if proposal.recommended_steps:
        for index, step in enumerate(proposal.recommended_steps, start=1):
            lines.append(f"{index}. {step}")
    else:
        lines.append("1. No proposal steps are available for this product.")
    lines.extend(["", "Guardian Review:"])
    if proposal.guardian_review:
        lines.extend("- " + item for item in proposal.guardian_review)
    else:
        lines.extend(
            [
                "- Runtime source edit: NO",
                "- Product-only change: YES",
                "- Network/package install: NO",
                "- Launch/package action now: NO",
                "- Approval required before apply: YES",
            ]
        )
    lines.extend(["", "Safety:"])
    if proposal.safety_notes:
        lines.extend("- " + item for item in proposal.safety_notes)
    lines.extend(
        [
            "- No files were changed.",
            "- Product code was not executed.",
            "- Proposal is not trusted memory.",
        ]
    )
    if proposal.message:
        lines.extend(["", "Message: " + proposal.message])
    return "\n".join(lines)


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def backup_existing_product(product_path: Path) -> Path:
    product_path = _resolve_without_existing(Path(product_path))
    if not is_safe_product_path(product_path):
        raise ValueError("Backup blocked for unsafe product path.")
    if not product_path.exists():
        raise FileNotFoundError("Product path does not exist: " + str(product_path))
    if not product_path.is_dir():
        raise ValueError("Product path is not a directory: " + str(product_path))
    backup_root = backups_root()
    backup_root.mkdir(parents=True, exist_ok=True)
    base = backup_root / f"{_timestamp()}_{product_path.name}"
    destination = base
    index = 1
    while destination.exists():
        index += 1
        destination = backup_root / f"{base.name}_{index}"
    shutil.copytree(product_path, destination)
    return destination


def write_product_receipt(
    product_path: Path,
    template_id: str,
    files_written: list[Path],
    validation: ValidationResult,
    approval_used: bool,
    backup_path: Path | None,
) -> Path:
    product_path = _resolve_without_existing(product_path)
    if not is_safe_product_path(product_path):
        raise ValueError("Receipt blocked for unsafe product path.")
    receipt_dir = product_path / "receipts"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = receipt_dir / f"{_timestamp()}_product_created.md"
    index = 1
    while receipt_path.exists():
        index += 1
        receipt_path = receipt_dir / f"{_timestamp()}_product_created_{index}.md"
    relative_files = []
    for path in files_written:
        try:
            relative_files.append(str(path.relative_to(product_path)))
        except ValueError:
            relative_files.append(str(path))
    content = "\n".join(
        [
            "# Engel Code Companion Product Template Receipt",
            "",
            f"Authority: {AUTHORITY}",
            f"Product template: {_template_name(template_id)}",
            f"Product root: {product_path}",
            "Files written:",
            *["- " + item for item in relative_files],
            f"Validation result: {validation.status} - {validation.message}",
            f"Safety status: {PRODUCT_STATUS}",
            "Approval token used: " + ("yes" if approval_used else "not used"),
            "Backup path: " + (str(backup_path) if backup_path else "none"),
            "No runtime source edits: yes",
            "No generated code execution: yes",
            "No package install: yes",
            "",
        ]
    )
    receipt_path.write_text(content, encoding="utf-8")
    return receipt_path


def write_product(product_name: str, template_id: str, prompt: str, approval_token: str | None = None) -> ProductWriteResult:
    try:
        build = build_product_template(template_id, product_name, prompt)
        product_path = product_path_for_slug(build.product_slug)
    except Exception as exc:
        return ProductWriteResult(False, "BLOCKED_UNSAFE_PRODUCT", validation=None, message=str(exc))

    if not build.validation.ok:
        return ProductWriteResult(
            False,
            build.validation.status,
            product_path=product_path,
            validation=build.validation,
            message=build.validation.message,
        )
    if not is_safe_product_path(product_path):
        return ProductWriteResult(False, "BLOCKED_PRODUCT_PATH", product_path=product_path, validation=build.validation)
    if product_path.exists() and not product_path.is_dir():
        return ProductWriteResult(False, "BLOCKED_PRODUCT_PATH", product_path=product_path, validation=build.validation)

    backup_path: Path | None = None
    approval_used = False
    if product_path.exists():
        if str(approval_token or "").strip() != APPROVAL_TOKEN:
            return ProductWriteResult(
                False,
                "BLOCKED_EXISTING_PRODUCT / APPROVE_CHANGE_REQUIRED",
                product_path=product_path,
                validation=build.validation,
                message="Existing product overwrite requires exact APPROVE_CHANGE.",
            )
        backup_path = backup_existing_product(product_path)
        approval_used = True

    products_root().mkdir(parents=True, exist_ok=True)
    product_path.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for relative_text, content in build.files.items():
        target = _target_for_relative(product_path, relative_text)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        written.append(target)

    receipt = write_product_receipt(product_path, build.template_id, written, build.validation, approval_used, backup_path)
    status = "PRODUCT_CREATED" if not approval_used else "PRODUCT_OVERWRITTEN_WITH_APPROVE_CHANGE"
    return ProductWriteResult(
        True,
        status,
        product_path=product_path,
        files_written=tuple(written),
        receipt_path=receipt,
        backup_path=backup_path,
        validation=build.validation,
        message="Product template written under APP_ROOT/products.",
    )


def validate_existing_product(product_path: Path) -> ValidationResult:
    candidate = _resolve_without_existing(Path(product_path))
    if not is_safe_product_path(candidate):
        return ValidationResult(False, "PRODUCT_PATH_BLOCKED", "Product path is outside APP_ROOT/products.")
    if not candidate.exists() or not candidate.is_dir():
        return ValidationResult(False, "PRODUCT_MISSING", "Product path does not exist.")
    files: dict[str, str] = {}
    for path in sorted(candidate.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(candidate)
        if str(relative).replace("\\", "/") == ".engel_product_profile.json":
            continue
        if _is_generated_product_relative(relative):
            continue
        if relative.suffix.lower() not in {".md", ".json", ".py", ".java", ".html", ".css", ".js"}:
            continue
        files[str(relative).replace("\\", "/")] = path.read_text(encoding="utf-8", errors="replace")
    validation = validate_product_files(files)
    if not validation.ok:
        return validation

    details = list(validation.details)
    for path in sorted(candidate.rglob("*.py")):
        compile_path = path.with_suffix(path.suffix + ".compile_check.pyc")
        try:
            py_compile.compile(str(path), cfile=str(compile_path), doraise=True)
        except py_compile.PyCompileError as exc:
            return ValidationResult(False, "PY_COMPILE_FAILED", str(exc), tuple(details))
        finally:
            if compile_path.exists():
                compile_path.unlink()
        details.append(str(path.relative_to(candidate)) + ": PY_COMPILE_OK")
    return ValidationResult(True, "PRODUCT_VALIDATION_OK", "Product folder passed bounded validation.", tuple(details))
