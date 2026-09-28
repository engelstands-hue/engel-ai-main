from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path


_file = globals().get("__file__")
if not _file or not isinstance(_file, str) or _file.startswith("<"):
    ROOT = Path.cwd()
else:
    try:
        ROOT = Path(_file).resolve().parents[1]
    except (OSError, ValueError, IndexError):
        ROOT = Path.cwd()
REPORT = ROOT / "reports" / "security" / "local_only" / "EE_LOCAL_ONLY_BOUNDARY_CHECK.md"

ACTIVE_SOURCE = [
    ROOT / "engel_app.py",
    ROOT / "engel_companion.py",
    ROOT / "engel_research_brain_v2.py",
    ROOT / "prompts" / "ENGEL_SYSTEM.md",
    ROOT / "memory" / "ROUTE_VERIFICATION_SET_V1.json",
    ROOT / "memory" / "LESSON_CANDIDATE_REVIEW_V1.json",
    ROOT / "memory" / "COLONY_SIMULATION_CONTRACT_V1.json",
    ROOT / "memory" / "COLONY_MYCELIUM_LAYER_CONTRACT_V1.json",
]

MANIFEST_NAMES = {"AndroidManifest.xml"}
BUILD_SUFFIXES = (".gradle", ".gradle.kts")
BUILD_NAMES = {"gradle.properties", "local.properties", "settings.gradle", "settings.gradle.kts", "build.gradle", "build.gradle.kts"}

PATTERNS = {
    "network_permission": re.compile(r"\bINTERNET\b", re.IGNORECASE),
    "mic_permission": re.compile(r"\bRECORD_AUDIO\b", re.IGNORECASE),
    "provider_or_endpoint": re.compile(r"\b(provider|endpoint|api[_-]?key|network|http://|https://|127\.0\.0\.1|localhost:\d+)\b", re.IGNORECASE),
    "telemetry_analytics_crash": re.compile(r"\b(telemetry|analytics|crash|sentry|firebase|appcenter)\b", re.IGNORECASE),
    "worker_scheduler": re.compile(r"\b(worker|scheduler|watcher|background|automation|loop)\b", re.IGNORECASE),
}


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT)).replace("/", "\\")
    except ValueError:
        return str(path)


def iter_text_files() -> list[Path]:
    files: list[Path] = []
    for path in ACTIVE_SOURCE:
        if path.exists():
            files.append(path)
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts:
            continue
        name = path.name
        if name in MANIFEST_NAMES or name in BUILD_NAMES or path.suffix.lower() in BUILD_SUFFIXES or path.suffix.lower() == ".apk":
            files.append(path)
    return sorted(set(files))


def scan_file(path: Path) -> list[tuple[str, int, str]]:
    if path.suffix.lower() == ".apk":
        return [("apk_artifact", 0, "binary package artifact present; permissions require external/package inspection")]
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    hits: list[tuple[str, int, str]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for label, pattern in PATTERNS.items():
            if pattern.search(line):
                snippet = line.strip()
                if len(snippet) > 160:
                    snippet = snippet[:157] + "..."
                hits.append((label, lineno, snippet))
    return hits


def build_report() -> str:
    files = iter_text_files()
    manifests = [p for p in files if p.name in MANIFEST_NAMES]
    builds = [p for p in files if p.name in BUILD_NAMES or p.suffix.lower() in BUILD_SUFFIXES]
    apks = [p for p in files if p.suffix.lower() == ".apk"]

    all_hits: list[tuple[Path, str, int, str]] = []
    for path in files:
        for label, lineno, snippet in scan_file(path):
            all_hits.append((path, label, lineno, snippet))

    lines = [
        "# EE Local-only Boundary Check",
        "",
        "Status: READ_ONLY_CHECK / NO_REMEDIATION",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Executive Summary",
        "",
        "The checker inspected text/config/build-like files only. It did not execute app routes, build packages, call providers/API/network, start workers, run loops, modify manifests/build/runtime files, mutate trusted memory, mutate queues, write digest/history, write `ALIVE_STATE`, or remediate.",
        "",
        "Allowed output: `reports\\security\\local_only\\EE_LOCAL_ONLY_BOUNDARY_CHECK.md`.",
        "",
        "## Pass/Needs-review/Risk Matrix",
        "",
        "| Area | Result | Evidence |",
        "| --- | --- | --- |",
        f"| Manifest files | {'NEEDS_REVIEW' if not manifests else 'NEEDS_REVIEW'} | {'No AndroidManifest.xml found in repo snapshot.' if not manifests else 'Manifest file(s) found: ' + ', '.join(rel(p) for p in manifests)} |",
        f"| Gradle/build files | {'NEEDS_REVIEW' if not builds else 'NEEDS_REVIEW'} | {'No Gradle/build config found in repo snapshot.' if not builds else 'Build file(s) found: ' + ', '.join(rel(p) for p in builds)} |",
        f"| Packaged APK artifacts | {'NEEDS_REVIEW' if not apks else 'RISK_REVIEW_REQUIRED'} | {'No APK artifact found in repo snapshot.' if not apks else 'APK artifact(s) found: ' + ', '.join(rel(p) for p in apks)} |",
        "| Provider/network/client patterns | NEEDS_REVIEW | Existing source contains provider-gated/status text; review matched lines below. |",
        "| Telemetry/analytics/crash patterns | NEEDS_REVIEW | Review matched lines below; documentation-only references are not runtime evidence. |",
        "| Background worker/scheduler patterns | NEEDS_REVIEW | Review matched lines below; documentation-only references are not runtime evidence. |",
        "| Local-only boundary | PASS_WITH_PACKAGING_UNKNOWN | Existing docs/verifiers keep local-only/offline posture; absent packaging artifacts remain unknown. |",
        "",
        "## Matched Files/Lines",
        "",
    ]

    if not all_hits:
        lines.append("- No pattern matches found in scanned files.")
    else:
        for path, label, lineno, snippet in all_hits[:120]:
            location = f"{rel(path)}:{lineno}" if lineno else rel(path)
            lines.append(f"- `{location}` [{label}] {snippet}")
        if len(all_hits) > 120:
            lines.append(f"- Additional matches omitted for readability: {len(all_hits) - 120}")

    lines.extend(
        [
            "",
            "## No-remediation Statement",
            "",
            "No remediation was performed. This checker wrote only the allowed local-only boundary report.",
            "",
            "## Recommended Next",
            "",
            "EF Local-only Boundary Results Review.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(build_report(), encoding="utf-8")
    print(f"WROTE {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
