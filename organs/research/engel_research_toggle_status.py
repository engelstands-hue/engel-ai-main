from __future__ import annotations

import argparse
import sys

import engel_research_toggle_worker as worker


STATUS_LABELS = [
    "RESEARCH_TOGGLE_OVERNIGHT_WORKER",
    "BOUNDED_RESEARCH_WORKER",
    "NO_PASSWORD_GATE_REQUIRED",
    "PROTECTED_ACTION_REGISTRY_REQUIRED",
    "HUMAN_ENABLE_REQUIRED",
    "DISABLED_BY_DEFAULT",
    "CANDIDATE_OUTPUTS_ONLY",
    "LOCAL_ONLY_BY_DEFAULT",
    "APPROVED_LOCAL_SOURCES_ONLY",
    "EXPLICIT_JOB_LIST_ONLY",
    "RECEIPT_REQUIRED",
    "RESOURCE_LIMITS_REQUIRED",
    "TIME_LIMIT_REQUIRED",
    "MAX_JOB_LIMIT_REQUIRED",
    "KILL_SWITCH_REQUIRED",
    "STOP_ON_HIGH_RISK",
    "STOP_ON_UNCLEAR_RISK",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_SOURCE_MUTATION",
    "NO_PATCH_APPLY",
    "NO_VERIFIER_UPDATE",
    "NO_PROVIDER_CALLS_BY_DEFAULT",
    "NO_NETWORK_BY_DEFAULT",
    "NO_BROWSER_BY_DEFAULT",
    "NO_MODEL_RUNTIME_BY_DEFAULT",
    "NO_PACKAGE_REFRESH",
    "NO_STARTUP_AUTORUN_INSTALL",
    "NO_ENDLESS_LOOP",
    "NO_HIDDEN_AUTONOMY",
]


def render_status() -> str:
    return worker.render_status()


def render_explain() -> str:
    return worker.explain_text() + "\n\n" + worker.render_status()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Show Engel Research toggle worker status.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--status", action="store_true", help="Show current worker status.")
    mode.add_argument("--explain", action="store_true", help="Explain Research toggle worker meaning and limits.")
    return parser


def main(argv: list[str] | None = None, stdout=None, stderr=None) -> int:
    out = stdout if stdout is not None else sys.stdout
    args = build_parser().parse_args(argv)
    if args.explain:
        out.write(render_explain())
        return 0
    out.write(render_status())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
