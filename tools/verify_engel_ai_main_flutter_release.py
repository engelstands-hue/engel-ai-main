#!/usr/bin/env python3
"""Verify a relocatable Engel AI Main Flutter release package.

This verifier is intentionally local-only. It checks the staged bundle,
manifest, launcher, source binding, and checksum without starting the app or
contacting a provider/server.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LATEST = ROOT / "dist" / "ENGEL_AI_MAIN_FLUTTER_PORTABLE_LATEST.json"
PROVENANCE_NAME = "BUILD_PROVENANCE.json"
BROWSER_RUNTIME_POLICY_SCHEMA = "engel_browser_runtime_policy_v1"
BROWSER_RUNTIME_MODE = "external_optional_with_manual_fallback"
PORTABLE_TERMINAL_FILES_SCHEMA = "engel_portable_terminal_files_v1"
PORTABLE_TERMINAL_FILES_MODE = "bounded_read_only_dart_fallback"
PORTABLE_TERMINAL_FILES_MAX_ENTRIES = 240
PORTABLE_TERMINAL_FILES_MAX_DEPTH = 3
BROWSER_CONTROL_SCRIPT = "workspace/tools/engel_browser_control.py"
BROWSER_CONTROL_CMD = "workspace/tools/engel_browser_control.cmd"
BROWSER_CONTROL_PS1 = "workspace/tools/engel_browser_control.ps1"
BROWSER_RUNTIME_POLICY = "workspace/runtime/browser_control/runtime_policy.json"
BROWSER_RUNTIME_README = "workspace/runtime/browser_control/README.md"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def fail(message: str) -> None:
    raise SystemExit(f"ENGEL_AI_MAIN_FLUTTER_RELEASE_VERIFY_FAIL: {message}")


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def source_checkout_for(manifest: dict[str, object]) -> Path:
    checkout_value = str(manifest.get("source_checkout", ""))
    return (
        Path(checkout_value)
        if checkout_value and checkout_value != "not_embedded"
        else ROOT
    )


def resolve_manifest_file(
    stage: Path,
    manifest: dict[str, object],
    relative: str,
) -> Path:
    """Resolve a staged member or source binding without guessing its scope."""
    if relative == PROVENANCE_NAME or relative.startswith(("app/", "workspace/")):
        return stage / relative
    return source_checkout_for(manifest) / relative.removeprefix("source/")


def verify_build_provenance(stage: Path, manifest: dict[str, object]) -> dict[str, object]:
    """Require the package's source/integration and local-execution receipt."""
    provenance_path = stage / PROVENANCE_NAME
    require(provenance_path.is_file(), f"build provenance missing: {provenance_path}")
    try:
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"build provenance is not valid JSON: {exc}")
    require(isinstance(provenance, dict), "build provenance must be an object")
    require(
        provenance.get("schema") == "engel_ai_main_flutter_build_provenance_v1",
        "build provenance schema mismatch",
    )
    require(provenance.get("product") == "Engel AI Main", "build provenance product mismatch")
    require(provenance.get("source_checkout") == "not_embedded", "build provenance source checkout mismatch")

    pointer = manifest.get("build_provenance")
    require(isinstance(pointer, dict), "manifest build_provenance pointer missing")
    require(pointer.get("path") == PROVENANCE_NAME, "manifest build_provenance path mismatch")
    require(
        str(pointer.get("sha256", "")).upper() == sha256_file(provenance_path),
        "manifest build_provenance hash mismatch",
    )
    require(pointer.get("bytes") == provenance_path.stat().st_size, "manifest build_provenance byte count mismatch")

    files = manifest.get("files") or {}
    file_pointer = files.get("build_provenance") if isinstance(files, dict) else None
    require(isinstance(file_pointer, dict), "manifest files build_provenance binding missing")
    require(file_pointer.get("path") == PROVENANCE_NAME, "manifest files build_provenance path mismatch")
    require(
        str(file_pointer.get("sha256", "")).upper() == sha256_file(provenance_path),
        "manifest files build_provenance hash mismatch",
    )

    boundary = provenance.get("execution_boundary")
    require(isinstance(boundary, dict), "build provenance execution boundary missing")
    require(boundary.get("scope") == "build_and_package_commands_only", "build provenance boundary scope mismatch")
    for key in (
        "local_only",
        "network_access",
        "network_calls",
        "provider_calls",
        "remote_execution",
        "secrets_access",
        "secrets_read",
        "secrets_embedded",
    ):
        expected = key == "local_only"
        require(boundary.get(key) is expected, f"build provenance boundary flag invalid: {key}")

    build_command = boundary.get("build_command")
    require(isinstance(build_command, list), "build provenance build command missing")
    for required_part in (
        "flutter",
        "build",
        "windows",
        "--release",
        "--dart-define=ENGEL_APP_ROOT=workspace",
    ):
        require(required_part in build_command, f"build provenance command missing: {required_part}")
    launcher_commands = boundary.get("launcher_commands")
    require(
        isinstance(launcher_commands, list)
        and launcher_commands == ["app/EngelAIMain.exe"],
        "build provenance launcher command boundary mismatch",
    )

    source_hashes = provenance.get("source_hashes")
    require(isinstance(source_hashes, dict), "build provenance source hashes missing")
    expected_sources = {
        "main.dart": "source/engel_flutter_main/lib/main.dart",
        "token_usage_warning.dart": "source/engel_flutter_main/lib/token_usage_warning.dart",
        "browser_control.py": "source/tools/engel_browser_control.py",
    }
    for key, expected_path in expected_sources.items():
        entry = source_hashes.get(key)
        require(isinstance(entry, dict), f"build provenance source hash missing: {key}")
        require(entry.get("path") == expected_path, f"build provenance source path mismatch: {key}")
        path = resolve_manifest_file(stage, manifest, expected_path)
        require(path.is_file(), f"build provenance source missing ({key}): {path}")
        actual_hash = sha256_file(path)
        require(
            actual_hash == str(entry.get("sha256", "")).upper(),
            f"build provenance source hash mismatch: {key}",
        )
        require(entry.get("bytes") == path.stat().st_size, f"build provenance source byte count mismatch: {key}")
        manifest_key = {
            "main.dart": "source",
            "token_usage_warning.dart": "token_warning_source",
            "browser_control.py": "browser_control_source",
        }[key]
        manifest_entry = files.get(manifest_key) if isinstance(files, dict) else None
        require(isinstance(manifest_entry, dict), f"manifest token/source binding missing: {manifest_key}")
        require(
            str(manifest_entry.get("sha256", "")).upper() == actual_hash,
            f"manifest/source provenance mismatch: {key}",
        )

    integration = provenance.get("token_warning_integration")
    require(isinstance(integration, dict), "token warning integration provenance missing")
    require(integration.get("main_source") == expected_sources["main.dart"], "token warning main source binding mismatch")
    require(
        integration.get("warning_source") == expected_sources["token_usage_warning.dart"],
        "token warning source binding mismatch",
    )
    markers = integration.get("required_markers")
    require(isinstance(markers, list) and markers, "token warning integration markers missing")
    main_source = resolve_manifest_file(stage, manifest, expected_sources["main.dart"]).read_text(encoding="utf-8")
    warning_source = resolve_manifest_file(stage, manifest, expected_sources["token_usage_warning.dart"]).read_text(encoding="utf-8")
    for marker in markers:
        require(isinstance(marker, str) and marker in main_source, f"token warning integration marker missing: {marker}")
    for marker in ("class TokenUsageSnapshot", "class TokenUsageWarning", "engel_token_usage_v1"):
        require(marker in warning_source, f"token warning source contract missing: {marker}")
    return provenance


def _read_json(path: Path, label: str) -> dict[str, object]:
    """Read a package JSON document and fail with a verifier-specific error."""
    require(path.is_file(), f"{label} missing: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"{label} is not valid JSON: {exc}")
    require(isinstance(value, dict), f"{label} must be an object")
    return value


def verify_browser_support(
    stage: Path,
    manifest: dict[str, object],
    provenance: dict[str, object],
) -> None:
    """Verify the portable browser handoff and its honest fallback contract.

    The release intentionally does not ship a Python/Playwright/Chromium
    runtime.  This check makes that limitation explicit, requires the control
    script and local launchers to be present, and prevents a package from
    claiming automated browser completion when it can only offer manual
    handoff.
    """
    browser_manifest = manifest.get("browser_control")
    require(isinstance(browser_manifest, dict), "manifest browser_control contract missing")
    require(
        browser_manifest.get("mode") == BROWSER_RUNTIME_MODE,
        "manifest browser_control mode mismatch",
    )
    require(browser_manifest.get("runtime_bundled") is False, "browser runtime bundling flag invalid")
    require(browser_manifest.get("runtime_required_for_automation") is True,
            "browser runtime requirement flag invalid")
    require(browser_manifest.get("control_script") == BROWSER_CONTROL_SCRIPT,
            "manifest browser control script path mismatch")
    require(browser_manifest.get("runtime_policy") == BROWSER_RUNTIME_POLICY,
            "manifest browser runtime policy path mismatch")
    require(browser_manifest.get("manual_fallback") is True,
            "manifest browser manual fallback flag missing")
    require(browser_manifest.get("network_install_allowed") is False,
            "manifest browser network-install boundary invalid")
    require(browser_manifest.get("human_checks") == "operator_only",
            "manifest browser human-check boundary invalid")

    policy_path = stage / BROWSER_RUNTIME_POLICY
    policy = _read_json(policy_path, "browser runtime policy")
    require(policy.get("schema") == BROWSER_RUNTIME_POLICY_SCHEMA,
            "browser runtime policy schema mismatch")
    require(policy.get("mode") == BROWSER_RUNTIME_MODE,
            "browser runtime policy mode mismatch")
    require(policy.get("runtime_bundled") is False,
            "browser runtime policy must declare runtime_bundled=false")
    require(policy.get("runtime_required_for_automation") is True,
            "browser runtime policy must declare runtime_required_for_automation=true")
    require(policy.get("control_script") == BROWSER_CONTROL_SCRIPT,
            "browser runtime policy script path mismatch")
    require(policy.get("launcher_cmd") == BROWSER_CONTROL_CMD,
            "browser runtime policy cmd launcher path mismatch")
    require(policy.get("launcher_ps1") == BROWSER_CONTROL_PS1,
            "browser runtime policy PowerShell launcher path mismatch")
    require(policy.get("python_environment_variable") == "ENGEL_BROWSER_PYTHON",
            "browser runtime policy Python override mismatch")
    require(policy.get("required_python_module") == "playwright",
            "browser runtime policy module mismatch")
    require(policy.get("network_install_allowed") is False,
            "browser runtime policy permits network installation")
    require(policy.get("credentials_embedded") is False,
            "browser runtime policy credential boundary invalid")
    require(policy.get("human_checks") == "operator_only",
            "browser runtime policy human-check boundary invalid")
    require(policy.get("manual_fallback") is True,
            "browser runtime policy manual fallback flag missing")
    fallback = str(policy.get("manual_fallback_message", ""))
    require("manual browser handoff" in fallback.lower(),
            "browser runtime policy has no manual browser fallback")
    require("unfinished" in fallback.lower() and "intact" in fallback.lower(),
            "browser runtime policy does not preserve unfinished work")

    browser_files = manifest.get("files")
    require(isinstance(browser_files, dict), "manifest files binding missing for browser support")
    expected_package_files = {
        "browser_control_script": BROWSER_CONTROL_SCRIPT,
        "browser_control_cmd": BROWSER_CONTROL_CMD,
        "browser_control_ps1": BROWSER_CONTROL_PS1,
        "browser_runtime_policy": BROWSER_RUNTIME_POLICY,
        "browser_runtime_readme": BROWSER_RUNTIME_README,
        "browser_control_source": "source/tools/engel_browser_control.py",
    }
    for key, expected_path in expected_package_files.items():
        entry = browser_files.get(key)
        require(isinstance(entry, dict), f"manifest browser file binding missing: {key}")
        require(entry.get("path") == expected_path,
                f"manifest browser file path mismatch: {key}")
        resolved = resolve_manifest_file(stage, manifest, expected_path)
        require(resolved.is_file(), f"manifest browser file missing: {key}")
        require(entry.get("bytes") == resolved.stat().st_size,
                f"manifest browser file byte count mismatch: {key}")
        require(str(entry.get("sha256", "")).upper() == sha256_file(resolved),
                f"manifest browser file hash mismatch: {key}")

    script_path = stage / BROWSER_CONTROL_SCRIPT
    script_text = script_path.read_text(encoding="utf-8")
    require("Path(__file__).resolve().parents[1]" in script_text,
            "portable browser script does not derive its root from its own location")
    require("HUMAN_CHALLENGE" in script_text and "operator" in script_text.lower(),
            "portable browser script lacks operator-only human-check handling")
    require("D:\\b.WorkSpace\\Engel App" not in script_text,
            "portable browser script leaks the developer absolute path")
    require("C:\\Users\\" not in script_text,
            "portable browser script leaks a user profile path")

    readme_text = (stage / BROWSER_RUNTIME_README).read_text(encoding="utf-8")
    readme_lower = readme_text.lower()
    for marker in ("engel_browser_python", "manual browser handoff", "embed python",
                   "captcha", "preserves the chat draft"):
        require(marker in readme_lower, f"browser runtime README missing marker: {marker}")
    require("D:\\b.WorkSpace\\Engel App" not in readme_text,
            "browser runtime README leaks the developer absolute path")

    for relative in (BROWSER_CONTROL_CMD, BROWSER_CONTROL_PS1):
        text = (stage / relative).read_text(encoding="utf-8")
        lowered = text.casefold()
        require("engel_browser_control.py" in lowered,
                f"browser launcher does not call the bundled control script: {relative}")
        require("engel_browser_python" in lowered,
                f"browser launcher omits the external Python override: {relative}")
        require("manual_browser_handoff" in lowered,
                f"browser launcher has no structured fallback: {relative}")
        for forbidden in (
            "invoke-webrequest",
            "invoke-restmethod",
            "curl",
            "wget",
            "pip install",
            "playwright install",
            "http://",
            "https://",
            "ssh ",
        ):
            require(forbidden not in lowered,
                    f"browser launcher crosses local-only boundary ({relative}): {forbidden}")

    provenance_browser = provenance.get("browser_control")
    require(isinstance(provenance_browser, dict),
            "build provenance browser_control contract missing")
    require(provenance_browser.get("mode") == BROWSER_RUNTIME_MODE,
            "build provenance browser mode mismatch")
    require(provenance_browser.get("runtime_bundled") is False,
            "build provenance browser bundling flag invalid")
    require(provenance_browser.get("manual_fallback") is True,
            "build provenance browser manual fallback flag missing")
    require(provenance_browser.get("network_install_allowed") is False,
            "build provenance browser network-install boundary invalid")
    require(provenance_browser.get("human_checks") == "operator_only",
            "build provenance browser human-check boundary invalid")


def verify_portable_terminal_files(
    stage: Path,
    manifest: dict[str, object],
    provenance: dict[str, object],
) -> None:
    """Verify the flash-drive Terminal & Files fallback contract.

    A portable release deliberately omits the development Rust checkout.  The
    Flutter shell therefore has to keep common file/terminal routes useful with
    its bounded Dart reader.  This check guards the documented limits and the
    source markers so a future package cannot silently regress to a dead
    ``Rust executable not found`` surface or to unrestricted shell execution.
    """

    expected_actions = [
        "feature_search_terminal",
        "feature_search_files",
        "feature_search_preview",
        "feature_search_logs",
        "workspace_inventory_short",
        "workspace_inventory_report",
        "runtime_wsl_status",
        "runtime_sandbox_status",
        "patch_plan_preview",
    ]
    expected_skips = [
        ".git",
        ".dart_tool",
        "build",
        "dist",
        "target",
        "node_modules",
        "ms-playwright",
        "browser_ai_venv",
        "browser_python",
    ]

    contract = manifest.get("portable_terminal_files")
    require(isinstance(contract, dict),
            "manifest portable Terminal & Files contract missing")
    require(contract.get("schema") == PORTABLE_TERMINAL_FILES_SCHEMA,
            "manifest portable Terminal & Files schema mismatch")
    require(contract.get("mode") == PORTABLE_TERMINAL_FILES_MODE,
            "manifest portable Terminal & Files mode mismatch")
    require(contract.get("implementation") == "engel_flutter_main/lib/main.dart",
            "manifest portable Terminal & Files implementation mismatch")
    require(contract.get("activation") ==
            "relative ENGEL_APP_ROOT plus missing Rust helper",
            "manifest portable Terminal & Files activation mismatch")
    require(contract.get("actions") == expected_actions,
            "manifest portable Terminal & Files action roster mismatch")
    require(contract.get("recursive") is True,
            "portable Terminal & Files scan must be recursive")
    require(contract.get("max_entries") == PORTABLE_TERMINAL_FILES_MAX_ENTRIES,
            "portable Terminal & Files entry bound mismatch")
    require(contract.get("max_depth") == PORTABLE_TERMINAL_FILES_MAX_DEPTH,
            "portable Terminal & Files depth bound mismatch")
    require(contract.get("scan_read_only") is True,
            "portable Terminal & Files scan is not read-only")
    require(contract.get("shell_execution") is False,
            "portable Terminal & Files fallback permits shell execution")
    require(contract.get("source_mutation") is False,
            "portable Terminal & Files fallback permits source mutation")
    require(contract.get("preserves_unfinished_work") is True,
            "portable Terminal & Files fallback does not preserve unfinished work")
    require(contract.get("explicit_report_write") ==
            "workspace/reports/codex_bridge/ENGEL_PORTABLE_WORKSPACE_INVENTORY.json",
            "portable Terminal & Files receipt path mismatch")
    skips = contract.get("skipped_directories")
    require(isinstance(skips, list) and skips == expected_skips,
            "portable Terminal & Files skipped-directory contract mismatch")

    provenance_contract = provenance.get("portable_terminal_files")
    require(isinstance(provenance_contract, dict),
            "build provenance portable Terminal & Files contract missing")
    require(provenance_contract == contract,
            "manifest/provenance portable Terminal & Files contract mismatch")

    source_path = resolve_manifest_file(
        stage,
        manifest,
        "source/engel_flutter_main/lib/main.dart",
    )
    require(source_path.is_file(),
            f"portable Terminal & Files source missing: {source_path}")
    source_text = source_path.read_text(encoding="utf-8")
    source_markers = (
        "Future<bool> _runPortableTerminalFilesFallback",
        "_isPortableWorkspaceBuild",
        "_portableScanSkipDirectories",
        "'ENGEL_WORKSPACE_ROOT': appRoot",
        "'feature_search_files'",
        """'feature_search_logs'""",
        "maxDepth:",
        "limit: recursiveScan ? 240 : 80",
        "no shell command was executed",
        "No patch was applied",
        "if (await _runPortableTerminalFilesFallback(command, text)) return;",
    )
    for marker in source_markers:
        require(marker in source_text,
                f"portable Terminal & Files source marker missing: {marker}")

    # The stage README is the handoff a flash-drive user actually sees.  Keep
    # its claims aligned with the machine-readable contract above.
    stage_readme = (stage / "README.md").read_text(encoding="utf-8").casefold()
    for marker in (
        "terminal & files",
        "bounded dart fallback",
        "240 entries",
        "depth 3",
        "read-only",
        "shell command",
        "unfinished work",
    ):
        require(marker in stage_readme,
                f"portable README missing Terminal & Files marker: {marker}")
    workspace_readme_path = stage / "workspace" / "README.md"
    require(workspace_readme_path.is_file(),
            "portable workspace README missing")
    workspace_readme = workspace_readme_path.read_text(encoding="utf-8").casefold()
    for marker in (
        "terminal & files",
        "bounded dart fallback",
        "240 entries",
        "depth 3",
        "read-only",
        "shell command",
        "unfinished work",
    ):
        require(marker in workspace_readme,
                f"portable workspace README missing Terminal & Files marker: {marker}")


def load_target(argument: str | None) -> tuple[Path, Path | None]:
    if argument:
        target = Path(argument).resolve()
        if target.is_dir():
            # A staging directory is normally accompanied by a same-stem
            # archive.  Keep archive verification optional for an explicitly
            # copied stage, but verify it whenever the sibling exists.
            sibling = target.with_suffix(".zip")
            return target, sibling if sibling.is_file() else None
        if target.is_file() and target.suffix.casefold() == ".zip":
            # The caller may have only the distributable archive.  ``main``
            # extracts it into a temporary, traversal-checked directory before
            # running the same manifest/file checks used for a staged bundle.
            return target, target
        fail(f"package target must be a staging directory or .zip: {target}")
    require(LATEST.is_file(), f"latest pointer missing: {LATEST}")
    pointer = json.loads(LATEST.read_text(encoding="utf-8"))
    stage = Path(str(pointer.get("stage", ""))).resolve()
    archive = Path(str(pointer.get("zip", ""))).resolve()
    require(stage.is_dir(), f"staged package missing: {stage}")
    return stage, archive if archive.is_file() else None


def verify_zip(archive: Path, stage: Path) -> None:
    checksum_file = archive.with_suffix(archive.suffix + ".sha256")
    require(checksum_file.is_file(), f"checksum sidecar missing: {checksum_file}")
    expected = checksum_file.read_text(encoding="ascii").split()[0].upper()
    require(sha256_file(archive) == expected, "archive checksum mismatch")
    with zipfile.ZipFile(archive) as zf:
        names = set(zf.namelist())
    for required_name in (
        "RELEASE_MANIFEST.json",
        PROVENANCE_NAME,
        "PACKAGE_RECEIPT.json",
        "Launch-Engel-AI-Main.cmd",
        "Launch-Engel-AI-Main.ps1",
        "app/EngelAIMain.exe",
        "app/data/app.so",
        "workspace/README.md",
        "workspace/reports/codex_bridge/ENGEL_AI_MAIN_VISION_AND_JOBS.md",
        BROWSER_CONTROL_SCRIPT,
        BROWSER_CONTROL_CMD,
        BROWSER_CONTROL_PS1,
        BROWSER_RUNTIME_POLICY,
        BROWSER_RUNTIME_README,
    ):
        require(required_name in names, f"archive entry missing: {required_name}")


def _extract_archive_safely(archive: Path, destination: Path) -> None:
    """Extract a package without allowing an archive member to escape root."""
    with zipfile.ZipFile(archive) as zf:
        for info in zf.infolist():
            member = Path(info.filename)
            if member.is_absolute() or ".." in member.parts:
                fail(f"archive contains an unsafe member path: {info.filename}")
        zf.extractall(destination)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", help="staging directory or zip to verify")
    args = parser.parse_args()
    stage, archive = load_target(args.package)
    temporary_stage: tempfile.TemporaryDirectory[str] | None = None
    if archive is not None and stage.is_file():
        temporary_stage = tempfile.TemporaryDirectory(prefix="engel-ai-main-release-")
        extracted = Path(temporary_stage.name)
        _extract_archive_safely(archive, extracted)
        stage = extracted
    manifest_path = stage / "RELEASE_MANIFEST.json"
    require(manifest_path.is_file(), f"manifest missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    require(manifest.get("schema") == "engel_ai_main_flutter_portable_release_v1", "manifest schema mismatch")
    require(manifest.get("product") == "Engel AI Main", "product mismatch")
    require(manifest.get("portable") is True, "portable flag missing")
    require(manifest.get("portable_app_root") == "workspace", "portable app root mismatch")
    require(manifest.get("server_first") is True, "server-first flag missing")
    require(
        manifest.get("network_or_provider_calls_during_packaging") is False,
        "manifest packaging network/provider boundary invalid",
    )
    require(manifest.get("secrets_embedded") is False, "secret embedding flag invalid")

    for relative in ("app/EngelAIMain.exe", "app/data/app.so"):
        require((stage / relative).is_file(), f"required app file missing: {relative}")
    for relative in ("Launch-Engel-AI-Main.cmd", "Launch-Engel-AI-Main.ps1", "README.md"):
        require((stage / relative).is_file(), f"required launcher/document missing: {relative}")
    for relative in (
        "memory",
        "reports",
        "run/secrets",
        "runtime/ui",
        "runtime/browser_control",
        "tools",
    ):
        require((stage / "workspace" / relative).is_dir(), f"workspace directory missing: {relative}")

    provenance = verify_build_provenance(stage, manifest)
    verify_browser_support(stage, manifest, provenance)
    verify_portable_terminal_files(stage, manifest, provenance)
    files = manifest.get("files") or {}
    require(isinstance(files, dict), "manifest files binding missing")
    for key, entry in files.items():
        require(isinstance(entry, dict), f"manifest file binding must be an object ({key})")
        relative = str(entry.get("path", ""))
        require(relative, f"manifest file path missing ({key})")
        path = resolve_manifest_file(stage, manifest, relative)
        require(path.is_file(), f"manifest file missing ({key}): {path}")
        require(sha256_file(path) == str(entry.get("sha256", "")).upper(), f"manifest hash mismatch ({key})")

    source_text = resolve_manifest_file(
        stage,
        manifest,
        "source/engel_flutter_main/lib/main.dart",
    ).read_text(encoding="utf-8")
    require("String.fromEnvironment" in source_text and "ENGEL_APP_ROOT" in source_text,
            "Flutter source has no relocatable ENGEL_APP_ROOT contract")
    require(
        "engelLocalVisionChatTimeoutSeconds" in source_text
        and "isStillImage" in source_text,
        "Flutter source is missing the still-image vision timeout wiring",
    )
    require(
        (stage / "workspace" / "reports" / "codex_bridge" / "ENGEL_AI_MAIN_VISION_AND_JOBS.md").is_file(),
        "portable workspace is missing the vision/jobs receipt",
    )

    cmd = (stage / "Launch-Engel-AI-Main.cmd").read_text(encoding="utf-8")
    ps1 = (stage / "Launch-Engel-AI-Main.ps1").read_text(encoding="utf-8")
    require("ENGEL_APP_ROOT=workspace" in cmd, "cmd launcher does not select workspace root")
    require("ENGEL_APP_ROOT = 'workspace'" in ps1, "PowerShell launcher does not select workspace root")
    require("EngelAIMain.exe" in cmd and "EngelAIMain.exe" in ps1, "launcher target missing")
    for launcher_name, launcher_text in (("cmd", cmd), ("ps1", ps1)):
        lowered = launcher_text.casefold()
        for forbidden in (
            "invoke-webrequest",
            "invoke-restmethod",
            "curl",
            "wget",
            "ssh ",
            "http://",
            "https://",
        ):
            require(forbidden not in lowered, f"{launcher_name} launcher crosses local-only boundary: {forbidden}")

    # Operational text shipped in the package must not smuggle the developer's
    # absolute workspace or a user credential path into the portable copy.
    for relative in (
        "Launch-Engel-AI-Main.cmd",
        "Launch-Engel-AI-Main.ps1",
        "README.md",
        "workspace/README.md",
        BROWSER_RUNTIME_README,
    ):
        text = (stage / relative).read_text(encoding="utf-8")
        require("D:\\b.WorkSpace\\Engel App" not in text, f"absolute developer path leaked into {relative}")
        require("provider_bridges.env" not in text, f"credential bridge reference leaked into {relative}")

    if archive is not None:
        verify_zip(archive, stage)
    print("ENGEL_AI_MAIN_FLUTTER_RELEASE_VERIFY_PASS")
    if temporary_stage is not None:
        temporary_stage.cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
