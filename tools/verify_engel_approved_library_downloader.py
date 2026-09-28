from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
DOWNLOADER = ROOT / "engel_approved_library_downloader.py"
MANIFEST = ROOT / "memory" / "ENGEL_APPROVED_LIBRARY_DOWNLOAD_MANIFEST_V1.json"
MANIFEST_MD = ROOT / "memory" / "ENGEL_APPROVED_LIBRARY_DOWNLOAD_MANIFEST_V1.md"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_APPROVED_LIBRARY_REAL_DOWNLOADS_V1.md"
LIBRARY_ROOT = ROOT / "engel_library" / "approved_library"

REQUIRED_CATEGORIES = [
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
    "engel_manuals_reports_receipts",
    "downloaded_receipts",
    "download_failures",
]

REQUIRED_CLI = [
    "--plan",
    "--download",
    "--category",
    "--verify-library",
    "--summary",
]

REQUIRED_REVIEW_STATES = [
    "PENDING_HUMAN_REVIEW",
    "UNTRUSTED_UNTIL_REVIEWED",
    "NOT_TRUSTED_MEMORY",
]

REQUIRED_RECORD_FIELDS = [
    "material_id",
    "category",
    "title",
    "source_url",
    "local_path",
    "sha256",
    "size_bytes",
    "downloaded_at",
    "source_type",
    "license_note",
    "review_state",
    "trusted_memory_allowed",
    "execution_allowed",
    "model_loading_allowed",
    "package_install_allowed",
]

FORBIDDEN_IMPORTS = {
    "openai",
    "requests",
    "subprocess",
    "webbrowser",
    "socket",
    "threading",
    "multiprocessing",
}

FORBIDDEN_ACTIVE_SNIPPETS = [
    "pip install",
    "package install command",
    "load_model(",
    "run_inference",
    "trusted_memory.write",
    "Start-Process",
    "Popen(",
    "system(",
    "exec(",
    "eval(",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    raise SystemExit(1)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        fail(f"could not read {path}: {exc}")


def verify_downloader_source() -> None:
    if not DOWNLOADER.exists():
        fail("engel_approved_library_downloader.py is missing")
    text = read_text(DOWNLOADER)
    for option in REQUIRED_CLI:
        if option not in text:
            fail(f"missing CLI option {option}")
    for category in REQUIRED_CATEGORIES:
        if category not in text:
            fail(f"missing category reference {category}")
    for required in [
        "no fake success",
        "NO_MODEL_LOADING",
        "NO_INFERENCE",
        "NO_TRAINING",
        "NO_PACKAGE_INSTALL",
        "NO_EXECUTION_OF_DOWNLOADED_FILES",
        "NO_TRUSTED_MEMORY_WRITE",
        "urllib.request",
    ]:
        if required not in text:
            fail(f"missing required downloader boundary/source text: {required}")
    tree = ast.parse(text)
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".", 1)[0])
    forbidden = sorted(FORBIDDEN_IMPORTS & imports)
    if forbidden:
        fail(f"forbidden imports present: {forbidden}")
    for snippet in FORBIDDEN_ACTIVE_SNIPPETS:
        if snippet in text:
            fail(f"forbidden active snippet present: {snippet}")


def verify_manifest_if_present() -> None:
    if not MANIFEST.exists():
        print("WARN: manifest does not exist yet; run downloader --download before final verification")
        return
    if not MANIFEST_MD.exists():
        fail("manifest markdown is missing")
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"manifest JSON invalid: {exc}")
    for field in [
        "schema_version",
        "target_library_root",
        "generated_at",
        "categories",
        "sources_attempted",
        "downloads_successful",
        "downloads_failed",
        "downloaded_files",
        "hash_algorithm",
        "safety_boundaries",
    ]:
        if field not in manifest:
            fail(f"manifest missing {field}")
    for bool_field in [
        "no_fake_data",
        "no_model_loading",
        "no_inference",
        "no_package_install",
        "no_trusted_memory_write",
    ]:
        if manifest.get(bool_field) is not True:
            fail(f"manifest {bool_field} is not true")
    if manifest.get("hash_algorithm") != "SHA256":
        fail("manifest hash algorithm is not SHA256")
    categories = manifest.get("categories", {})
    for category in REQUIRED_CATEGORIES:
        if category not in categories:
            fail(f"manifest missing category {category}")
    success_count = int(manifest.get("downloads_successful", -1))
    failure_count = int(manifest.get("downloads_failed", -1))
    records = manifest.get("downloaded_files", [])
    failures = manifest.get("failure_records", [])
    if success_count != len(records):
        fail("downloads_successful does not match downloaded_files length")
    if failure_count != len(failures):
        fail("downloads_failed does not match failure_records length")
    if success_count <= 0:
        fail("manifest has no successful real materials")
    for record in records:
        if not isinstance(record, dict):
            fail("downloaded file record is not an object")
        for field in REQUIRED_RECORD_FIELDS:
            if field not in record:
                fail(f"downloaded record missing {field}")
        local_path = ROOT / str(record["local_path"])
        if not local_path.exists() or not local_path.is_file():
            fail(f"successful record missing file: {record['material_id']}")
        if local_path.stat().st_size <= 0:
            fail(f"successful record has empty file: {record['material_id']}")
        if sha256(local_path) != str(record["sha256"]).upper():
            fail(f"hash mismatch for {record['material_id']}")
        if int(record["size_bytes"]) != local_path.stat().st_size:
            fail(f"size mismatch for {record['material_id']}")
        if not str(record["source_url"]):
            fail(f"missing source URL for {record['material_id']}")
        states = record.get("review_state", [])
        for state in REQUIRED_REVIEW_STATES:
            if state not in states:
                fail(f"{record['material_id']} missing review state {state}")
        for flag in [
            "trusted_memory_allowed",
            "execution_allowed",
            "model_loading_allowed",
            "package_install_allowed",
        ]:
            if record.get(flag) is not False:
                fail(f"{record['material_id']} has unsafe {flag}")
    for failure in failures:
        if "failure_reason" not in failure:
            fail("failure record missing failure_reason")
        states = failure.get("review_state", [])
        if "NO_FAKE_SUCCESS" not in states:
            fail("failure record missing NO_FAKE_SUCCESS")


def verify_library_folder_if_present() -> None:
    if not LIBRARY_ROOT.exists():
        print("WARN: approved library root does not exist yet; downloader creates it during --download")
        return
    for category in REQUIRED_CATEGORIES:
        path = LIBRARY_ROOT / category
        if not path.exists() or not path.is_dir():
            fail(f"category folder missing: {category}")


def main() -> int:
    verify_downloader_source()
    verify_library_folder_if_present()
    verify_manifest_if_present()
    if REPORT.exists():
        text = read_text(REPORT)
        for required in [
            "no fake data",
            "no model loading",
            "no inference",
            "no pip/package install",
            "no downloaded instructions were executed",
            "no trusted-memory write",
        ]:
            if required not in text.lower():
                fail(f"report missing safety statement: {required}")
    print("PASS: Engel approved library downloader verifier")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
