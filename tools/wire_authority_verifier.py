#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import subprocess
import sys

_file = globals().get("__file__")
if not _file or not isinstance(_file, str) or _file.startswith("<"):
    ROOT = Path.cwd()
else:
    try:
        ROOT = Path(_file).resolve().parents[1]
    except (OSError, ValueError, IndexError):
        ROOT = Path.cwd()

AUTHORITY_VERIFIER = ROOT / "tools" / "verify_authority_hierarchy.py"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"
REPORT = ROOT / "reports" / "codex_bridge" / "JOSH_GUARDIAN_ENGEL_AUTHORITY_HARDENING.md"

COMMAND_TO_ADD = r"python tools\verify_authority_hierarchy.py"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def ensure_authority_verifier_exists() -> None:
    if not AUTHORITY_VERIFIER.exists():
        raise FileNotFoundError(f"Missing verifier: {AUTHORITY_VERIFIER}")


def wire_into_codex_verify() -> str:
    if not CODEX_VERIFY.exists():
        raise FileNotFoundError(f"Missing script: {CODEX_VERIFY}")

    text = read_text(CODEX_VERIFY)

    if COMMAND_TO_ADD in text:
        return "already present"

    block = f"""

Write-Host "[codex_verify] Running authority hierarchy verifier..."
{COMMAND_TO_ADD}
if ($LASTEXITCODE -ne 0) {{
    exit $LASTEXITCODE
}}
"""

    write_text(CODEX_VERIFY, text.rstrip() + block + "\n")
    return "added"


def run_command(command: list[str]) -> tuple[int, str]:
    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        shell=False,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return result.returncode, result.stdout.strip()


def update_report(
    integration_status: str,
    direct_result: tuple[int, str],
    codex_result: tuple[int, str],
) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if REPORT.exists():
        existing = read_text(REPORT).rstrip()
    else:
        existing = "# Josh / Guardian / Engel Authority Hardening\n"

    direct_code, direct_output = direct_result
    codex_code, codex_output = codex_result

    section = f"""

## Authority Verifier Result

Timestamp: {timestamp}

Enforced hierarchy:

```text
Josh > Guardian > Engel/runtime
```

Integration status: `{integration_status}`

Direct verifier exit code: `{direct_code}`

```text
{direct_output}
```

Codex verifier exit code: `{codex_code}`

```text
{codex_output}
```
"""

    write_text(REPORT, existing + section)


def main() -> int:
    ensure_authority_verifier_exists()
    integration_status = wire_into_codex_verify()
    direct_result = run_command([sys.executable, str(AUTHORITY_VERIFIER)])
    codex_result = run_command(
        [
            "powershell",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(CODEX_VERIFY),
        ]
    )
    update_report(integration_status, direct_result, codex_result)
    print(f"authority verifier integration: {integration_status}")
    print(f"report: {REPORT}")
    return direct_result[0] or codex_result[0]


if __name__ == "__main__":
    raise SystemExit(main())
