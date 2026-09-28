from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACTIVE_WORKSPACE = r"D:\b.WorkSpace\Engel App"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_COMPLETE_NAME_PATH_REFERENCE_REFACTOR_V1.md"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"

TEXT_SUFFIXES = {
    ".bat",
    ".cmd",
    ".html",
    ".json",
    ".md",
    ".ps1",
    ".py",
    ".spec",
    ".txt",
    ".toml",
    ".yaml",
    ".yml",
}

EXCLUDED_PARTS = {
    ".git",
    "__pycache__",
    "backups",
    "browser_profile",
    "build",
    "build_engel",
    "build_hive",
    "dist",
    "external",
    "lib",
    "node_modules",
    "sandbox",
    "venv",
    ".venv",
}

HISTORICAL_PATH_FILES = {
    Path("memory") / "MAIN_AGENT_LOG.md",
    Path("memory") / "PROJECT_MEMORY_INDEX_V2V.md",
    Path("memory") / "ENGEL_MARKDOWN_KNOWLEDGE_INDEX_V1.json",
    Path("memory") / "ENGEL_MARKDOWN_KNOWLEDGE_INDEX_V1.md",
    Path("memory") / "ENGEL_STABLE_RELEASE_CHECKPOINT_V2APPAN2.md",
    Path("memory") / "ENGEL_COMMANDS.md",
    Path("engel_app_d_drive_build_plan.md"),
}

ALLOWED_STALE_PATH_LINES = (
    "Historical reports may still mention",
    "old `D:\\Engel App`",
    "old paths",
    "Do not use old paths",
    "Do not use `D:\\Engel App` as the active workspace",
    "historical only",
    "D:\\Engel App Bible",
)

FORBIDDEN_TRUE_PATTERNS = (
    r'"server_enabled"\s*:\s*true',
    r'"provider_api_enabled"\s*:\s*true',
    r'"startup_auto_load_enabled"\s*:\s*true',
    r'"background_daemon_enabled"\s*:\s*true',
    r'"trusted_memory_write_enabled"\s*:\s*true',
    r'"approved_memory_write_enabled"\s*:\s*true',
    r'"persistent_chat_enabled"\s*:\s*true',
    r'"persistent_runtime_enabled"\s*:\s*true',
    r'"true_long_lived_model_process_enabled"\s*:\s*true',
    r'"source_route_queue_mutation"\s*:\s*true',
    r"\bserver_enabled\s*=\s*True\b",
    r"\bprovider_api_enabled\s*=\s*True\b",
    r"\bstartup_auto_load_enabled\s*=\s*True\b",
    r"\bbackground_daemon_enabled\s*=\s*True\b",
    r"\btrusted_memory_write_enabled\s*=\s*True\b",
    r"\bapproved_memory_write_enabled\s*=\s*True\b",
)

KEY_VERIFIERS = [
    "tools\\verify_engel_core_continuity_map.py",
    "tools\\verify_engel_system_integration_status.py",
    "tools\\verify_engel_outside_ai_boundary.py",
    "tools\\verify_engel_remote_worker_lan_pairing.py",
    "tools\\verify_engel_wsl_ubuntu_runtime_dependency.py",
    "tools\\verify_engel_ai_runtime_readiness.py",
    "tools\\verify_engel_memory_roots_storage_layout.py",
]


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(rel: str | Path) -> str:
    path = ROOT / rel
    return path.read_text(encoding="utf-8", errors="replace")


def project_relative(path: Path) -> Path:
    return path.relative_to(ROOT)


def git_executable() -> str:
    """Resolve Git even when Visual Studio's bundled copy is not on PATH."""
    on_path = shutil.which("git")
    if on_path:
        return on_path
    candidates = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        / "Git"
        / "cmd"
        / "git.exe",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        / "Microsoft Visual Studio"
        / "2022"
        / "Community"
        / "Common7"
        / "IDE"
        / "CommonExtensions"
        / "Microsoft"
        / "TeamFoundation"
        / "Team Explorer"
        / "Git"
        / "cmd"
        / "git.exe",
        Path(os.environ.get("LOCALAPPDATA", ""))
        / "Programs"
        / "Git"
        / "cmd"
        / "git.exe",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    raise CheckFailure("Git executable not found on PATH or in supported bundled locations")


def tracked_text_files() -> list[Path]:
    completed = subprocess.run(
        [git_executable(), "ls-files"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    require(completed.returncode == 0, "git ls-files failed")
    paths: list[Path] = []
    for raw in completed.stdout.splitlines():
        rel = Path(raw)
        if any(part in EXCLUDED_PARTS for part in rel.parts):
            continue
        if rel.suffix.lower() not in TEXT_SUFFIXES:
            continue
        candidate = ROOT / rel
        # Sparse/archived worktrees can retain index entries for intentionally
        # absent generated artifacts. Only inspect files present in this checkout.
        if candidate.is_file():
            paths.append(candidate)
    return paths


def stale_workspace_occurrences() -> list[str]:
    failures: list[str] = []
    exact_old_root = re.compile(r"D:\\Engel App(?! Bible)(?=$|[\\`'\"\s])")
    stale_patterns = (
        re.compile(r"D:\\a\.WorkSpace\\Engel App"),
        re.compile(r"D:/a\.WorkSpace/Engel App"),
        exact_old_root,
        re.compile(r"E:\\Engel App(?=$|[\\`'\"\s])"),
    )
    for path in tracked_text_files():
        rel = project_relative(path)
        text = path.read_text(encoding="utf-8", errors="replace")
        for line_no, line in enumerate(text.splitlines(), start=1):
            for pattern in stale_patterns:
                if not pattern.search(line):
                    continue
                if rel in HISTORICAL_PATH_FILES:
                    continue
                if rel.parts and rel.parts[0] == "reports":
                    continue
                if any(marker in line for marker in ALLOWED_STALE_PATH_LINES):
                    continue
                if rel == Path("tools") / "verify_engel_code_companion.py" and "a.WorkSpace" in line:
                    continue
                failures.append(f"{rel}:{line_no}: {line.strip()}")
    return failures


def check_workspace_path_references() -> None:
    require(str(ROOT) == ACTIVE_WORKSPACE, "active workspace mismatch: " + str(ROOT))
    required_current_refs = [
        "CODEX_JOB.md",
        "CODEX_HANDOFF.md",
        "ENGEL_LAUNCH_SAFETY_GUARD_HANDOFF.md",
        "engel_app_d_drive_build_plan.md",
        "memory/ENGEL_REFACTOR_SAFETY_CONTRACT_V1.md",
        "memory/GUARDIAN_STATUS.md",
        "memory/STANDARD_VERIFIER_CHECKLIST_V1.md",
        "models/qwen2.5-0.5b-instruct/EXPECTED_MODEL_FILE.txt",
    ]
    for rel in required_current_refs:
        require(ACTIVE_WORKSPACE in read(rel), rel + " missing active B workspace reference")
    require("Path(__file__).resolve().parent" in read("start_engel.py"), "start_engel.py must resolve from current file")
    require('ROOT = Path(__file__).resolve().parent' in read("decode_codex_usage_coffee.py"), "decode helper must be root-relative")
    failures = stale_workspace_occurrences()
    require(not failures, "stale active workspace references remain: " + "; ".join(failures[:20]))


def check_branding_names() -> None:
    manual_html = read("docs/manual/_manual.html")
    require("4.10 Eng3d" in manual_html, "manual HTML must use Eng3d branding")
    require("claw3d status" not in manual_html.lower(), "manual HTML still advertises claw3d command")
    ephify = read("engel_ephify_bridge.py")
    require('EPHIFY_DISPLAY_NAME = "Ephify"' in ephify, "Ephify display name missing")
    require('EPHIFY_COMMAND = "ephify"' in ephify, "ephify command missing")
    require("sandboxed upstream package still" in ephify, "Ephify upstream-module compatibility comment missing")
    require((ROOT / "engel_eng3d_bridge.py").exists(), "Eng3d bridge missing")
    require((ROOT / "engel_ephify_bridge.py").exists(), "Ephify bridge missing")
    require((ROOT / "sandbox" / "Eng3d").exists(), "Eng3d sandbox missing")
    require((ROOT / "sandbox" / "Ephify").exists(), "Ephify sandbox missing")


def check_engel_bible_separation() -> None:
    promotion = read("engel_approved_memory_promotion.py")
    trusted = read("engel_trusted_memory_target.py")
    require("Engel Bible App" in promotion and "not Engel App" in promotion, "Approved Memory Promotion must separate Engel Bible App scope")
    require("engel_bible_app_scope" in trusted, "Trusted Memory Target must retain Engel Bible App separation warning")
    handoff = read("CODEX_HANDOFF.md") + "\n" + read("CODEX_JOB.md")
    require("Engel Bible App" not in handoff, "active Codex handoff/job must not confuse Engel App with Engel Bible App")


def check_ai_phase_names_and_runtime_flags() -> None:
    plan = json.loads(read("memory/ENGEL_AI_PERSISTENT_CHAT_SUPERVISED_RUNTIME_PLAN_V1.json"))
    for key in [
        "persistent_chat_enabled",
        "persistent_runtime_enabled",
        "true_long_lived_model_process_enabled",
        "server_enabled",
        "provider_api_enabled",
        "startup_auto_load_enabled",
        "background_daemon_enabled",
        "trusted_memory_write_enabled",
        "approved_memory_write_enabled",
        "source_route_queue_mutation",
    ]:
        require(plan.get(key) is False, "persistent plan must keep " + key + " false")
    require(
        plan.get("recommended_next_mode") == "supervised_persistent_gui_session_repeated_bounded_calls",
        "persistent plan recommended next mode mismatch",
    )
    phase_text = "\n".join(
        [
            read("engel_ai_persistent_chat_supervised_runtime_plan.py"),
            read("engel_ai_runtime_readiness.py"),
            read("tools/verify_engel_ai_persistent_chat_supervised_runtime_plan.py"),
        ]
    )
    for phase in [
        "ENGEL_AI_LOCAL_OPEN_CHAT_SUPERVISED_RUN_V1",
        "ENGEL_AI_PERSISTENT_CHAT_SUPERVISED_RUNTIME_PLAN_V1",
        "ENGEL_AI_PERSISTENT_CHAT_SUPERVISED_SESSION_V1",
    ]:
        require(phase in phase_text, "AI phase name missing: " + phase)


def check_no_runtime_enablement_added() -> None:
    failures: list[str] = []
    combined_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in FORBIDDEN_TRUE_PATTERNS]
    for path in tracked_text_files():
        rel = project_relative(path)
        if rel.parts and rel.parts[0] in {"reports", "memory"} and rel.name in {
            "MAIN_AGENT_LOG.md",
            "PROJECT_MEMORY_INDEX_V2V.md",
        }:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern in combined_patterns:
            match = pattern.search(text)
            if match:
                failures.append(f"{rel}: {match.group(0)}")
    require(not failures, "runtime/provider/server/trusted-write enablement appears active: " + "; ".join(failures[:20]))


def check_hermes_reference_only() -> None:
    outside = json.loads(read("memory/ENGEL_OUTSIDE_AI_BOUNDARY_RULE_V1.json"))
    hermes = outside.get("hermes_policy", {})
    # Hermes is now APPROVED for local install + human-driven testing per
    # ENGEL_HERMES_POLICY_CHANGE_V1. The verifier accepts either status for
    # back-compat with audit snapshots.
    accepted_statuses = {
        "REJECTED / DO NOT INSTALL ON THIS COMPUTER",
        "APPROVED FOR LOCAL INSTALL AND HUMAN-DRIVEN TESTING",
    }
    require(hermes.get("status") in accepted_statuses, "Hermes policy status missing or unrecognised")
    require("external research references" in read("memory/ENGEL_LLM_AND_PYTHON_LIBRARY_INTAKE_PLAN_V1.md"), "Hermes external-reference wording missing")
    hermes_verifier = read("tools/verify_engel_hermes_rejection.py")
    require(r"sandbox\\eng3d\\" in hermes_verifier.lower(), "Hermes verifier must classify Eng3d sandbox as external/reference")
    require(r"sandbox\\ephify\\" in hermes_verifier.lower(), "Hermes verifier must classify Ephify sandbox as external/reference")


def check_remote_worker_lan_support() -> None:
    lan = read("engel_remote_worker_lan_pairing.py")
    for needle in [
        "UDP_DISCOVERY_PORT_OFFSET",
        "start_udp_broadcaster",
        "HTTPServer",
        "--allow-lan",
        '"packet_transfer": False',
        '"result_upload": False',
        '"trusted_memory_write": False',
        '"auto_apply": False',
    ]:
        require(needle in lan, "LAN route missing safe support marker: " + needle)
    commands = read("memory/ENGEL_COMMANDS.md")
    for command in [
        "remote worker lan pairing status",
        "remote worker lan pairing token",
        "remote worker lan pairing serve localhost",
        "remote worker lan pairing serve lan",
    ]:
        require(command in commands, "ENGEL_COMMANDS missing LAN command: " + command)
    require("tools\\verify_engel_remote_worker_lan_pairing.py" in read("scripts/codex_verify.ps1"), "LAN verifier missing from Codex verifier")


def check_report_and_registration() -> None:
    require(REPORT.exists(), "bridge report missing")
    report = REPORT.read_text(encoding="utf-8", errors="replace")
    for needle in [
        "ENGEL_COMPLETE_NAME_PATH_REFERENCE_REFACTOR_V1",
        ACTIVE_WORKSPACE,
        "Remote Worker LAN",
        "Hermes",
        "Engel App vs Engel Bible",
    ]:
        require(needle in report, "report missing: " + needle)
    require("packaging skipped" in report.lower(), "report missing: packaging skipped")
    require("tools\\verify_engel_complete_name_path_reference_refactor.py" in read(CODEX_VERIFY), "new verifier missing from scripts\\codex_verify.ps1")


def check_no_package_artifacts_staged() -> None:
    completed = subprocess.run(
        [git_executable(), "diff", "--cached", "--name-only"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    require(completed.returncode == 0, "git diff --cached failed")
    blocked_suffixes = (".exe", ".dll", ".gguf", ".bin", ".pyd", ".so", ".dylib")
    blocked_roots = ("build/", "build_engel/", "build_hive/", "dist/", "live/", "staging/")
    bad = []
    for raw in completed.stdout.splitlines():
        lower = raw.replace("\\", "/").lower()
        if lower.endswith(blocked_suffixes) or lower.startswith(blocked_roots):
            bad.append(raw)
    require(not bad, "package/model/runtime artifacts staged: " + ", ".join(bad[:20]))


def run_existing_verifier(rel: str) -> None:
    path = ROOT / rel
    require(path.exists(), "required existing verifier missing: " + rel)
    completed = subprocess.run(
        [sys.executable, str(path)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        errors="replace",
        timeout=180,
        check=False,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if completed.returncode != 0:
        detail = (completed.stdout + "\n" + completed.stderr).strip()
        raise CheckFailure(rel + " failed: " + detail[-2000:])


def check_existing_verifiers_still_pass() -> None:
    for verifier in KEY_VERIFIERS:
        run_existing_verifier(verifier)


def main() -> int:
    checks = [
        ("workspace_path_references", check_workspace_path_references),
        ("branding_names", check_branding_names),
        ("engel_bible_separation", check_engel_bible_separation),
        ("ai_phase_names_and_runtime_flags", check_ai_phase_names_and_runtime_flags),
        ("no_runtime_enablement_added", check_no_runtime_enablement_added),
        ("hermes_reference_only", check_hermes_reference_only),
        ("remote_worker_lan_support", check_remote_worker_lan_support),
        ("report_and_registration", check_report_and_registration),
        ("no_package_artifacts_staged", check_no_package_artifacts_staged),
        ("existing_verifiers", check_existing_verifiers_still_pass),
    ]
    failures: list[str] = []
    for name, check in checks:
        try:
            check()
            print("PASS " + name)
        except CheckFailure as exc:
            failures.append(f"{name}: {exc}")
            print("FAIL " + name + ": " + str(exc))
        except Exception as exc:
            failures.append(f"{name}: unexpected error: {exc}")
            print("FAIL " + name + ": unexpected error: " + str(exc))
    if failures:
        print("\nENGEL_COMPLETE_NAME_PATH_REFERENCE_REFACTOR_VERIFY_FAIL")
        for failure in failures:
            print("- " + failure)
        return 1
    print("\nENGEL_COMPLETE_NAME_PATH_REFERENCE_REFACTOR_VERIFY_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
