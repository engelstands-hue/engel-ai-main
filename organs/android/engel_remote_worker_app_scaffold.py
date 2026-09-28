from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from engel_android_remote_worker_protocol import WORKER_DEFINITIONS, WORKER_IDS, worker_package_path


ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)

REQUIRED_PACKAGE_FILES = [
    "config/worker_identity.json",
    "config/worker_capabilities.json",
    "config/worker_autonomy_policy.json",
    "jobs/.gitkeep",
    "inbox/.gitkeep",
    "outbox/.gitkeep",
    "logs/.gitkeep",
    "receipts/.gitkeep",
    "status/.gitkeep",
    "README_ANDROID_SETUP.md",
    "remote_worker_status.py",
    "remote_worker_job_view.py",
    "remote_worker_runner.py",
    "remote_worker_local_executor.py",
    "run_worker_status.py",
    "run_assigned_job.py",
]


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def package_manifest() -> dict[str, object]:
    packages = []
    for worker_id in WORKER_IDS:
        package = worker_package_path(worker_id)
        missing = [name for name in REQUIRED_PACKAGE_FILES if not (package / name).exists()]
        worker = WORKER_DEFINITIONS[worker_id]
        packages.append(
            {
                "worker_id": worker_id,
                "worker_name": worker["worker_name"],
                "role": worker["role"],
                "package_folder": rel(package),
                "required_files": list(REQUIRED_PACKAGE_FILES),
                "missing_files": missing,
                "ready_for_manual_transfer": not missing,
                "manual_transfer_only": True,
                "real_package_not_fake_status": True,
                "does_not_include_model_files": True,
                "does_not_include_rejected_agentic_runtime_stack": True,
                "does_not_include_network_server": True,
                "does_not_include_startup_autorun": True,
            }
        )
    return {
        "scaffold_name": "Engel Android Remote Worker App Scaffold V1",
        "package_count": len(packages),
        "packages": packages,
        "android_side_ui_scaffold": [
            "remote_worker_status.py",
            "remote_worker_job_view.py",
        ],
        "local_runner_files": [
            "remote_worker_runner.py",
            "remote_worker_local_executor.py",
            "run_worker_status.py",
            "run_assigned_job.py",
        ],
        "safety_boundary": [
            "manual_transfer_mode_only",
            "real_worker_packages_not_fake_live_data",
            "no_phone_connection",
            "no_android_runtime_execution_from_engel",
            "no_network_server",
            "no_ssh",
            "no_adb_automation",
            "no_cloud_sync",
            "no_model_runtime",
            "hermes_rejected_do_not_install",
            "no_ollama",
            "no_llama_cpp",
            "no_startup_autorun",
        ],
    }


def render_status() -> str:
    manifest = package_manifest()
    lines = [
        str(manifest["scaffold_name"]),
        "",
        "These are real uploadable manual-transfer worker packages, not fake live data.",
        "Android Studio/runtime launch is not required for V1; phone setup uses manual Termux transfer.",
        "",
    ]
    for package in manifest["packages"]:
        lines.extend(
            [
                f"- {package['worker_name']} ({package['worker_id']})",
                f"  role: {package['role']}",
                f"  folder: {package['package_folder']}",
                f"  ready for manual transfer: {package['ready_for_manual_transfer']}",
                f"  missing files: {', '.join(package['missing_files']) if package['missing_files'] else '(none)'}",
            ]
        )
    lines.extend(
        [
            "",
            "Boundary:",
            "- Manual transfer only.",
            "- No phone connection, network server, ADB automation, SSH, cloud sync, Ollama, llama.cpp, model runtime, startup autorun, or fake job data; Hermes remains rejected / do not install on this computer.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only Android Remote Worker app scaffold manifest.")
    parser.add_argument("--status", action="store_true", help="Print scaffold status.")
    parser.add_argument("--json", action="store_true", help="Print scaffold manifest JSON.")
    return parser


def main(argv: list[str] | None = None, stdout=None, stderr=None) -> int:
    out = stdout if stdout is not None else sys.stdout
    args = build_parser().parse_args(argv)
    manifest = package_manifest()
    if args.json:
        out.write(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    else:
        out.write(render_status())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

