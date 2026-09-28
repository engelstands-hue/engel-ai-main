#!/usr/bin/env python3
"""Build and package the canonical Engel AI Main Flutter desktop app.

The historical packaging scripts target the retired PyInstaller/Tauri app.
This script targets only the Flutter Windows runner (``EngelAIMain.exe``) and
creates a relocatable, server-first bundle. It never starts providers,
servers, background workers, or network requests.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FLUTTER_PROJECT = ROOT / "engel_flutter_main"
RELEASE_DIR = FLUTTER_PROJECT / "build" / "windows" / "x64" / "runner" / "Release"
DIST = ROOT / "dist"
DEFAULT_FLUTTER = ROOT.parent / "flutter_windows_3.41.9-stable" / "flutter" / "bin" / "flutter.bat"
PROVENANCE_NAME = "BUILD_PROVENANCE.json"
TOKEN_WARNING_SOURCE = FLUTTER_PROJECT / "lib" / "token_usage_warning.dart"
BROWSER_CONTROL_SOURCE = ROOT / "tools" / "engel_browser_control.py"
BROWSER_CONTROL_SCRIPT_NAME = "engel_browser_control.py"
BROWSER_CONTROL_CMD_NAME = "engel_browser_control.cmd"
BROWSER_CONTROL_PS1_NAME = "engel_browser_control.ps1"
BROWSER_RUNTIME_POLICY_NAME = "runtime_policy.json"
BROWSER_RUNTIME_README_NAME = "README.md"
BROWSER_RUNTIME_POLICY_SCHEMA = "engel_browser_runtime_policy_v1"
BROWSER_RUNTIME_MODE = "external_optional_with_manual_fallback"
PORTABLE_TERMINAL_FILES_SCHEMA = "engel_portable_terminal_files_v1"
PORTABLE_TERMINAL_FILES_MODE = "bounded_read_only_dart_fallback"
PORTABLE_TERMINAL_FILES_MAX_ENTRIES = 240
PORTABLE_TERMINAL_FILES_MAX_DEPTH = 3


def _portable_terminal_files_contract() -> dict[str, object]:
    """Describe the local fallback used by Terminal & Files in a flash copy.

    The Flutter release intentionally does not carry the development Rust
    helper.  When that helper is absent, Main still exposes the everyday
    Terminal & Files routes through a bounded Dart filesystem scan.  Keeping
    this contract in the manifest makes the limitation and safety boundary
    visible to a verifier and to anyone moving the ZIP to another desktop.
    """
    return {
        "schema": PORTABLE_TERMINAL_FILES_SCHEMA,
        "mode": PORTABLE_TERMINAL_FILES_MODE,
        "implementation": "engel_flutter_main/lib/main.dart",
        "activation": "relative ENGEL_APP_ROOT plus missing Rust helper",
        "actions": [
            "feature_search_terminal",
            "feature_search_files",
            "feature_search_preview",
            "feature_search_logs",
            "workspace_inventory_short",
            "workspace_inventory_report",
            "runtime_wsl_status",
            "runtime_sandbox_status",
            "patch_plan_preview",
        ],
        "recursive": True,
        "max_entries": PORTABLE_TERMINAL_FILES_MAX_ENTRIES,
        "max_depth": PORTABLE_TERMINAL_FILES_MAX_DEPTH,
        "scan_read_only": True,
        "shell_execution": False,
        "source_mutation": False,
        "explicit_report_write": (
            "workspace/reports/codex_bridge/"
            "ENGEL_PORTABLE_WORKSPACE_INVENTORY.json"
        ),
        "preserves_unfinished_work": True,
        "skipped_directories": [
            ".git",
            ".dart_tool",
            "build",
            "dist",
            "target",
            "node_modules",
            "ms-playwright",
            "browser_ai_venv",
            "browser_python",
        ],
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def source_entry(path: Path, package_path: str) -> dict[str, object]:
    """Return the auditable source binding used by the release manifests."""
    return {
        "path": package_path,
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
    }


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def json_dump(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_flutter_build(flutter: Path, build_name: str, build_number: str) -> None:
    if not flutter.exists() and not shutil.which(str(flutter)):
        raise FileNotFoundError(
            f"Flutter SDK not found at {flutter}; set FLUTTER_BIN to a Flutter executable."
        )
    command = [
        str(flutter),
        "build",
        "windows",
        "--release",
        f"--build-name={build_name}",
        f"--build-number={build_number}",
        "--dart-define=ENGEL_APP_ROOT=workspace",
    ]
    completed = subprocess.run(command, cwd=FLUTTER_PROJECT, check=False, text=True)
    if completed.returncode:
        raise RuntimeError(f"Flutter Windows release build failed (exit {completed.returncode}).")


def _browser_control_cmd_text() -> str:
    """Return a local-only launcher for the optional browser runtime.

    The Flutter release deliberately does not carry a Python distribution or
    Chromium (those add hundreds of megabytes and a venv is not relocatable
    when its ``pyvenv.cfg`` points at the build machine).  This launcher finds
    an operator-provided Python/Playwright installation and emits a structured
    handoff when none is available.  It never installs packages or makes a
    network call by itself.
    """
    return r'''@echo off
setlocal EnableExtensions
set "ENGEL_BROWSER_WORKSPACE=%~dp0.."
for %%I in ("%ENGEL_BROWSER_WORKSPACE%") do set "ENGEL_BROWSER_WORKSPACE=%%~fI"
set "ENGEL_BROWSER_SCRIPT=%~dp0engel_browser_control.py"
set "ENGEL_BROWSER_PYTHON_EXE="

if defined ENGEL_BROWSER_PYTHON if exist "%ENGEL_BROWSER_PYTHON%" set "ENGEL_BROWSER_PYTHON_EXE=%ENGEL_BROWSER_PYTHON%"
if not defined ENGEL_BROWSER_PYTHON_EXE if exist "%ENGEL_BROWSER_WORKSPACE%\runtime\browser_ai_venv\Scripts\python.exe" set "ENGEL_BROWSER_PYTHON_EXE=%ENGEL_BROWSER_WORKSPACE%\runtime\browser_ai_venv\Scripts\python.exe"
if not defined ENGEL_BROWSER_PYTHON_EXE if exist "%ENGEL_BROWSER_WORKSPACE%\runtime\browser_python\python.exe" set "ENGEL_BROWSER_PYTHON_EXE=%ENGEL_BROWSER_WORKSPACE%\runtime\browser_python\python.exe"
if not defined ENGEL_BROWSER_PYTHON_EXE for /f "delims=" %%P in ('where python.exe 2^>nul') do if not defined ENGEL_BROWSER_PYTHON_EXE set "ENGEL_BROWSER_PYTHON_EXE=%%P"

if not defined ENGEL_BROWSER_PYTHON_EXE (
  echo {"ok":false,"status":"Browser automation is not configured on this desktop.","browser_runtime_available":false,"fallback":"manual_browser_handoff","detail":"Set ENGEL_BROWSER_PYTHON to a Python interpreter with Playwright, then retry; no install was attempted."}
  exit /b 2
)
if not exist "%ENGEL_BROWSER_SCRIPT%" (
  echo {"ok":false,"status":"The Engel browser control script is missing from this portable copy.","browser_runtime_available":false,"fallback":"manual_browser_handoff"}
  exit /b 2
)

"%ENGEL_BROWSER_PYTHON_EXE%" -c "import playwright" >nul 2>&1
if errorlevel 1 (
  echo {"ok":false,"status":"Browser automation needs Python with the Playwright module.","browser_runtime_available":false,"fallback":"manual_browser_handoff","detail":"Install or select a prepared local runtime and set ENGEL_BROWSER_PYTHON; Engel does not install packages automatically."}
  exit /b 3
)

set "ENGEL_APP_ROOT=%ENGEL_BROWSER_WORKSPACE%"
set "PLAYWRIGHT_BROWSERS_PATH=%ENGEL_BROWSER_WORKSPACE%\runtime\ms-playwright"
"%ENGEL_BROWSER_PYTHON_EXE%" "%ENGEL_BROWSER_SCRIPT%" %*
exit /b %ERRORLEVEL%
'''


def _browser_control_ps1_text() -> str:
    """Return the PowerShell equivalent of the optional browser launcher."""
    return r'''$ErrorActionPreference = 'Stop'
$workspace = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$script = Join-Path $PSScriptRoot 'engel_browser_control.py'
$candidates = New-Object System.Collections.Generic.List[string]
if ($env:ENGEL_BROWSER_PYTHON) { $candidates.Add($env:ENGEL_BROWSER_PYTHON) }
$candidates.Add((Join-Path $workspace 'runtime\browser_ai_venv\Scripts\python.exe'))
$candidates.Add((Join-Path $workspace 'runtime\browser_python\python.exe'))
try {
    $pathPython = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
    if ($pathPython) { $candidates.Add($pathPython) }
} catch { }
$python = $candidates | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } | Select-Object -First 1
if (-not $python) {
    [ordered]@{ ok = $false; status = 'Browser automation is not configured on this desktop.'; browser_runtime_available = $false; fallback = 'manual_browser_handoff'; detail = 'Set ENGEL_BROWSER_PYTHON to a Python interpreter with Playwright, then retry; no install was attempted.' } | ConvertTo-Json -Compress
    exit 2
}
if (-not (Test-Path -LiteralPath $script -PathType Leaf)) {
    [ordered]@{ ok = $false; status = 'The Engel browser control script is missing from this portable copy.'; browser_runtime_available = $false; fallback = 'manual_browser_handoff' } | ConvertTo-Json -Compress
    exit 2
}
& $python -c 'import playwright' 2>$null
if ($LASTEXITCODE -ne 0) {
    [ordered]@{ ok = $false; status = 'Browser automation needs Python with the Playwright module.'; browser_runtime_available = $false; fallback = 'manual_browser_handoff'; detail = 'Install or select a prepared local runtime and set ENGEL_BROWSER_PYTHON; Engel does not install packages automatically.' } | ConvertTo-Json -Compress
    exit 3
}
$env:ENGEL_APP_ROOT = $workspace
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $workspace 'runtime\ms-playwright'
& $python $script @args
exit $LASTEXITCODE
'''


def _browser_runtime_policy() -> dict[str, object]:
    """Describe the portable browser contract in a machine-readable form."""
    return {
        "schema": BROWSER_RUNTIME_POLICY_SCHEMA,
        "mode": BROWSER_RUNTIME_MODE,
        "runtime_bundled": False,
        "runtime_required_for_automation": True,
        "control_script": "workspace/tools/engel_browser_control.py",
        "runtime_policy": "workspace/runtime/browser_control/runtime_policy.json",
        "launcher_cmd": "workspace/tools/engel_browser_control.cmd",
        "launcher_ps1": "workspace/tools/engel_browser_control.ps1",
        "python_environment_variable": "ENGEL_BROWSER_PYTHON",
        "python_candidates": [
            "workspace/runtime/browser_ai_venv/Scripts/python.exe",
            "workspace/runtime/browser_python/python.exe",
            "python.exe on PATH",
        ],
        "required_python_module": "playwright",
        "browser_cache_environment_variable": "PLAYWRIGHT_BROWSERS_PATH",
        "browser_cache_path": "workspace/runtime/ms-playwright",
        "network_install_allowed": False,
        "credentials_embedded": False,
        "human_checks": "operator_only",
        "manual_fallback": True,
        "manual_fallback_message": (
            "If no compatible Python/Playwright runtime is available, Main must "
            "provide a manual browser handoff: tell the operator to open the "
            "requested URL manually or configure a local runtime; chat drafts "
            "and unfinished work remain intact."
        ),
    }


def _browser_runtime_readme() -> str:
    """Human-facing setup and fallback instructions shipped with the bundle."""
    return """# Engel AI Main browser handoff

This portable copy includes Engel's browser-control script, but it intentionally
does **not** embed Python, Playwright, Chromium, provider credentials, or a
machine-specific virtual environment. Those dependencies are large and a
normal Python venv records the build computer's absolute path, which would
break when this folder is moved to a flash drive or another desktop.

## Optional local runtime

To enable browser automation on a destination desktop, prepare a Python
interpreter with the `playwright` module and point Engel at it:

```text
ENGEL_BROWSER_PYTHON=C:\\path\\to\\python.exe
```

The runtime must be prepared by the operator (including a compatible Chromium
installation or Playwright browser cache). Engel does not install packages,
download browsers, or make a network request during this handoff. The supplied
`engel_browser_control.cmd` and `engel_browser_control.ps1` launchers probe the
runtime locally and return a structured error if it is unavailable.

## No runtime is still a supported state

If the probe cannot find Python/Playwright, Main should show a clear **manual browser handoff**:
open the requested URL in the desktop browser and continue the work there.
Main preserves the chat draft, attachments, and unfinished work; this is not a
fabricated completion.

Human checks such as CAPTCHA, sign-in, and “verify you are human” prompts are
always completed by the operator. Engel only opens and observes the page.
"""


def write_portable_support_tree(workspace: Path) -> None:
    """Create the small writable workspace shipped on removable media."""
    support_dirs = (
        "memory/personality",
        "memory/models",
        "memory/training",
        "reports",
        "run/secrets",
        "runtime/ui",
        "runtime/chat_attachments",
        "runtime/connector_profiles",
        "runtime/browser_control",
        "tools",
    )
    for relative in support_dirs:
        directory = workspace / relative
        directory.mkdir(parents=True, exist_ok=True)
        # ZIP archives do not preserve empty directories.  A harmless marker
        # keeps the portable tree intact after extraction on another desktop.
        (directory / ".keep").write_text(
            "Directory reserved for this portable copy of Engel AI Main.\n",
            encoding="utf-8",
        )

    (workspace / "README.md").write_text(
        """# Engel AI Main portable workspace

This workspace belongs to this copy of Engel AI Main. It contains no
provider keys or model weights. Configure the CT246/server connection through
the app or environment variables before using server features.

The app was built with `ENGEL_APP_ROOT=workspace`; keep this folder beside the
portable launcher so each copy has its own writable state.

Still images attached in chat are copied into `runtime/chat_attachments` and
sent to Engel AI Main. On the live one-system (ROG + CT246), Joshua's pictures
and Discord stills are viewed through the Grok vision lane. Discord
fix/complete/build orders use the operator work lane instead of chat-only.
Browser control is an optional local capability; see runtime/browser_control/README.md.
This copy includes the Engel browser-control script and operator launchers, but
does not embed Python, Playwright, Chromium, or provider credentials. Set
ENGEL_BROWSER_PYTHON to a prepared Python/Playwright interpreter when one is
available. Without it, Main presents a manual browser handoff and preserves
the chat draft; it never installs packages or claims an unverified result.

## Terminal & Files on a flash drive

Common Terminal & Files routes remain available even when the development Rust
helper is not present. Main uses a bounded Dart fallback for feature searches,
workspace inventory, WSL/sandbox status, and patch preview: at most 240 entries
through depth 3, with build/dist/target and other runtime caches skipped. The
scan is read-only and never executes a shell command or mutates source. An
explicit **Full workspace report** action may write its receipt to
`reports/codex_bridge/ENGEL_PORTABLE_WORKSPACE_INVENTORY.json`; chat drafts and
unfinished work remain intact when the media is read-only.
""",
        encoding="utf-8",
    )
    reports_dir = workspace / "reports" / "codex_bridge"
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "ENGEL_AI_MAIN_VISION_AND_JOBS.md").write_text(
        """# Engel AI Main vision and Discord jobs

This portable copy includes the 2026-08-27 vision and job-completion wiring:

- PNG/JPG chat attachments are stored under `runtime/chat_attachments`.
- The Flutter UI gives image turns 180 seconds so the vision lane can finish.
- Live Engel AI Main (CT246 + ROG Grok CLI) looks at those pixels and answers
  what is on the picture.
- Discord orders such as fix / complete / build are work orders, not chat.

Provider keys, Discord tokens, and model weights are not in this ZIP.

Browser handoff: `workspace/tools/engel_browser_control.py` is included for an
operator-provided Python/Playwright runtime. If that runtime is absent, use
the manual browser handoff shown by Main; no automated completion is claimed.

Terminal & Files remain usable without the development Rust checkout. The
portable Main build falls back to a bounded Dart scan (up to 240 entries,
depth 3) for common searches and inventory. It is read-only, does not execute
shell commands, and does not apply source patches. The explicit inventory
report route writes only its receipt under `workspace/reports/codex_bridge`.
""",
        encoding="utf-8",
    )
    (workspace / "run" / "secrets" / ".keep").write_text(
        "Credentials are intentionally not included in portable releases.\n",
        encoding="utf-8",
    )
    (workspace / "runtime" / "ui" / ".keep").write_text(
        "Portable UI preferences and receipts are written here.\n",
        encoding="utf-8",
    )

    # Browser automation is an optional local capability.  Ship the exact
    # control script and a documented, non-networking launcher so a portable
    # copy can use an operator-provided runtime without silently failing with
    # FileNotFoundError.  The Python/Playwright runtime itself is intentionally
    # external (see runtime_policy.json).
    if not BROWSER_CONTROL_SOURCE.is_file():
        raise FileNotFoundError(
            f"Browser control source is required for the portable handoff: {BROWSER_CONTROL_SOURCE}"
        )
    browser_tools = workspace / "tools"
    shutil.copy2(BROWSER_CONTROL_SOURCE, browser_tools / BROWSER_CONTROL_SCRIPT_NAME)
    browser_tools.joinpath(BROWSER_CONTROL_CMD_NAME).write_text(
        _browser_control_cmd_text(), encoding="utf-8"
    )
    browser_tools.joinpath(BROWSER_CONTROL_PS1_NAME).write_text(
        _browser_control_ps1_text(), encoding="utf-8"
    )
    browser_runtime = workspace / "runtime" / "browser_control"
    browser_runtime.joinpath(BROWSER_RUNTIME_POLICY_NAME).write_text(
        json.dumps(_browser_runtime_policy(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    browser_runtime.joinpath(BROWSER_RUNTIME_README_NAME).write_text(
        _browser_runtime_readme(), encoding="utf-8"
    )


def write_launchers(stage: Path) -> None:
    (stage / "Launch-Engel-AI-Main.cmd").write_text(
        """@echo off
setlocal
set "ENGEL_APP_ROOT=workspace"
set "ENGEL_BROWSER_RUNTIME_POLICY=%~dp0workspace\\runtime\\browser_control\\runtime_policy.json"
set "ENGEL_BROWSER_CONTROL_SCRIPT=%~dp0workspace\\tools\\engel_browser_control.py"
pushd "%~dp0"
"%~dp0app\\EngelAIMain.exe"
set "EXIT_CODE=%ERRORLEVEL%"
popd
exit /b %EXIT_CODE%
""",
        encoding="utf-8",
    )
    (stage / "Launch-Engel-AI-Main.ps1").write_text(
        """$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$env:ENGEL_APP_ROOT = 'workspace'
$env:ENGEL_BROWSER_RUNTIME_POLICY = Join-Path $root 'workspace\\runtime\\browser_control\\runtime_policy.json'
$env:ENGEL_BROWSER_CONTROL_SCRIPT = Join-Path $root 'workspace\\tools\\engel_browser_control.py'
Push-Location $root
try { & (Join-Path $root 'app\\EngelAIMain.exe') } finally { Pop-Location }
""",
        encoding="utf-8",
    )
    (stage / "README.md").write_text(
        """# Engel AI Main — portable Windows release

Start `Launch-Engel-AI-Main.cmd`. This release is relocatable: it uses the
bundled `workspace` directory and does not require the original build checkout.

The UI is server-first. Provider credentials, model weights, and CT246
runtime services are not embedded. Configure an approved server/account from
inside the app. No credentials are stored by this package.

`app/` is the Flutter Windows release bundle. `workspace/` is the per-copy
writable state area. The workspace also includes the Engel browser-control
script and a local-only runtime policy. Browser automation is optional on a
destination desktop; if Python/Playwright is not configured, Main presents a
manual browser handoff and preserves the chat draft.

## Terminal & Files

The portable build keeps common Terminal & Files actions useful even when the
development Rust helper is not copied. Main uses a bounded Dart fallback for
feature searches, workspace inventory, WSL/sandbox status, and patch preview:
up to 240 entries through depth 3, while skipping build/dist/target and other
runtime caches. The scan is read-only, never executes a shell command, and does
not apply source patches. The explicit inventory-report action writes only its
receipt under `workspace/reports/codex_bridge`; drafts and unfinished work stay
intact when the flash drive is read-only.
""",
        encoding="utf-8",
    )


def _release_bundle_ignore(path: str, names: list[str]) -> set[str]:
    """Keep runtime state out of the copied Flutter ``app`` bundle.

    A previous portable-root launch can leave a ``workspace`` directory next
    to the Windows runner executable.  That directory belongs to the writable
    portable workspace, not to the immutable Flutter bundle; copying it would
    leak stale receipts/provider state into a new flash-drive package.  Apply
    the filter only at the Release root so a similarly named asset nested in
    Flutter's ``data`` tree is never hidden accidentally.
    """
    try:
        if Path(path).resolve() == RELEASE_DIR.resolve():
            return {
                name
                for name in names
                if name.casefold() in {"workspace", "memory", "reports", "runtime"}
            }
    except OSError:
        pass
    return set()


def stage_release(stage: Path, build_name: str, build_number: str) -> dict[str, object]:
    if not RELEASE_DIR.is_dir():
        raise FileNotFoundError(f"Flutter release directory missing: {RELEASE_DIR}")
    if not BROWSER_CONTROL_SOURCE.is_file():
        raise FileNotFoundError(
            f"Browser control source is required for the portable handoff: {BROWSER_CONTROL_SOURCE}"
        )
    exe = RELEASE_DIR / "EngelAIMain.exe"
    app_so = RELEASE_DIR / "data" / "app.so"
    if not exe.is_file() or not app_so.is_file():
        raise FileNotFoundError("Release bundle must contain EngelAIMain.exe and data/app.so")

    shutil.copytree(RELEASE_DIR, stage / "app", ignore=_release_bundle_ignore)
    write_portable_support_tree(stage / "workspace")
    write_launchers(stage)

    source = FLUTTER_PROJECT / "lib" / "main.dart"
    widget_test = FLUTTER_PROJECT / "test" / "widget_test.dart"
    if not TOKEN_WARNING_SOURCE.is_file():
        raise FileNotFoundError(
            "Flutter release source must contain the token warning integration: "
            f"{TOKEN_WARNING_SOURCE}"
        )
    browser_script = stage / "workspace" / "tools" / BROWSER_CONTROL_SCRIPT_NAME
    browser_cmd = stage / "workspace" / "tools" / BROWSER_CONTROL_CMD_NAME
    browser_ps1 = stage / "workspace" / "tools" / BROWSER_CONTROL_PS1_NAME
    browser_policy = (
        stage / "workspace" / "runtime" / "browser_control" / BROWSER_RUNTIME_POLICY_NAME
    )
    browser_readme = (
        stage / "workspace" / "runtime" / "browser_control" / BROWSER_RUNTIME_README_NAME
    )
    for browser_file in (
        browser_script,
        browser_cmd,
        browser_ps1,
        browser_policy,
        browser_readme,
    ):
        if not browser_file.is_file():
            raise FileNotFoundError(
                f"Portable browser handoff file was not produced: {browser_file}"
            )
    files = {
        "executable": source_entry(exe, "app/EngelAIMain.exe"),
        "app_bundle": source_entry(app_so, "app/data/app.so"),
        "source": source_entry(source, "source/engel_flutter_main/lib/main.dart"),
        "token_warning_source": source_entry(
            TOKEN_WARNING_SOURCE,
            "source/engel_flutter_main/lib/token_usage_warning.dart",
        ),
        "widget_test": source_entry(
            widget_test,
            "source/engel_flutter_main/test/widget_test.dart",
        ),
        "browser_control_script": source_entry(
            browser_script,
            "workspace/tools/engel_browser_control.py",
        ),
        "browser_control_cmd": source_entry(
            browser_cmd,
            "workspace/tools/engel_browser_control.cmd",
        ),
        "browser_control_ps1": source_entry(
            browser_ps1,
            "workspace/tools/engel_browser_control.ps1",
        ),
        "browser_runtime_policy": source_entry(
            browser_policy,
            "workspace/runtime/browser_control/runtime_policy.json",
        ),
        "browser_runtime_readme": source_entry(
            browser_readme,
            "workspace/runtime/browser_control/README.md",
        ),
        "browser_control_source": source_entry(
            BROWSER_CONTROL_SOURCE,
            "source/tools/engel_browser_control.py",
        ),
    }
    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    build_command = [
        "flutter",
        "build",
        "windows",
        "--release",
        f"--build-name={build_name}",
        f"--build-number={build_number}",
        "--dart-define=ENGEL_APP_ROOT=workspace",
    ]
    token_warning_markers = [
        "import 'token_usage_warning.dart';",
        "TokenUsageSnapshot.fromResponse",
        "TokenUsageWarning.fromSnapshot",
    ]
    provenance = {
        "schema": "engel_ai_main_flutter_build_provenance_v1",
        "product": "Engel AI Main",
        "generated_at_utc": generated_at,
        "source_checkout": "not_embedded",
        "source_hashes": {
            "main.dart": files["source"],
            "token_usage_warning.dart": files["token_warning_source"],
            "browser_control.py": files["browser_control_source"],
        },
        "token_warning_integration": {
            "main_source": files["source"]["path"],
            "warning_source": files["token_warning_source"]["path"],
            "required_markers": token_warning_markers,
        },
        "browser_control": {
            "mode": BROWSER_RUNTIME_MODE,
            "runtime_bundled": False,
            "control_script": "workspace/tools/engel_browser_control.py",
            "runtime_policy": "workspace/runtime/browser_control/runtime_policy.json",
            "manual_fallback": True,
            "network_install_allowed": False,
            "human_checks": "operator_only",
        },
        "portable_terminal_files": _portable_terminal_files_contract(),
        "execution_boundary": {
            "scope": "build_and_package_commands_only",
            "local_only": True,
            "remote_execution": False,
            "network_access": False,
            "network_calls": False,
            "provider_calls": False,
            "secrets_access": False,
            "secrets_read": False,
            "secrets_embedded": False,
            "build_command": build_command,
            "launcher_commands": [
                "app/EngelAIMain.exe",
            ],
        },
    }
    provenance_path = stage / PROVENANCE_NAME
    json_dump(provenance_path, provenance)
    provenance_entry = {
        "path": PROVENANCE_NAME,
        "sha256": sha256_file(provenance_path),
        "bytes": provenance_path.stat().st_size,
    }
    files["build_provenance"] = provenance_entry
    browser_contract = _browser_runtime_policy()
    # Keep the detailed explanation in the policy document, while exposing a
    # boolean capability flag in the top-level manifest for simple consumers.
    browser_contract["manual_fallback_description"] = browser_contract.get(
        "manual_fallback_message", ""
    )
    browser_contract["manual_fallback"] = True
    manifest = {
        "schema": "engel_ai_main_flutter_portable_release_v1",
        "generated_at_utc": generated_at,
        "product": "Engel AI Main",
        "version": build_name,
        "build_number": build_number,
        "portable": True,
        "portable_app_root": "workspace",
        "server_first": True,
        "network_or_provider_calls_during_packaging": False,
        "secrets_embedded": False,
        "files": files,
        "launchers": ["Launch-Engel-AI-Main.cmd", "Launch-Engel-AI-Main.ps1"],
        "build_provenance": provenance_entry,
        "browser_control": browser_contract,
        "portable_terminal_files": _portable_terminal_files_contract(),
        # Source is intentionally not embedded in the removable-media bundle;
        # the hash remains available for an external provenance check.
        "source_checkout": "not_embedded",
    }
    json_dump(stage / "RELEASE_MANIFEST.json", manifest)
    return manifest


def zip_stage(stage: Path, zip_path: Path) -> str:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(stage.rglob("*")):
            if path.is_file():
                archive.write(path, arcname=path.relative_to(stage).as_posix())
    digest = sha256_file(zip_path)
    zip_path.with_suffix(zip_path.suffix + ".sha256").write_text(
        f"{digest}  {zip_path.name}\n", encoding="ascii"
    )
    return digest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-build", action="store_true", help="package the existing Flutter Release directory")
    parser.add_argument("--build-name", default="1.1.0", help="Flutter product version")
    parser.add_argument("--build-number", default="3", help="Flutter build number")
    parser.add_argument("--output-root", type=Path, help="optional staging directory parent")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.skip_build:
        flutter_text = os.environ.get("FLUTTER_BIN", "").strip()
        run_flutter_build(Path(flutter_text) if flutter_text else DEFAULT_FLUTTER, args.build_name, args.build_number)

    parent = (args.output_root or DIST).resolve()
    parent.mkdir(parents=True, exist_ok=True)
    stamp = utc_stamp()
    stage = parent / f"EngelAI-Main-Flutter-Portable-{stamp}"
    stage.mkdir(parents=True, exist_ok=False)
    manifest = stage_release(stage, args.build_name, args.build_number)
    zip_path = parent / f"EngelAI-Main-Flutter-Portable-{stamp}.zip"
    # Put the receipt in the staged tree before archiving so the archive is
    # self-describing. The external receipt adds the final archive digest
    # after the archive has been closed (avoiding a self-referential hash).
    staged_receipt = {
        "schema": "engel_ai_main_flutter_portable_package_receipt_v1",
        "ok": True,
        "stage": str(stage),
        "zip": str(zip_path),
        "zip_sha256": None,
        "manifest": manifest,
        "created_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    json_dump(stage / "PACKAGE_RECEIPT.json", staged_receipt)
    zip_sha = zip_stage(stage, zip_path)
    receipt = {**staged_receipt, "zip_sha256": zip_sha}
    json_dump(parent / "ENGEL_AI_MAIN_FLUTTER_PORTABLE_LATEST.json", receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
