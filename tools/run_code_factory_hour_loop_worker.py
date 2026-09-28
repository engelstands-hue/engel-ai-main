#!/usr/bin/env python3
"""Run the explicit Engel Code Factory one-hour loop.

This worker is started by Engel AI -> Agent Meeting Room, not by direct user
typing into the Meeting Room. It keeps all run artifacts under the supplied
run root and lets any in-flight Builder pass finish after the target duration.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ENGEL_APP_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = ENGEL_APP_ROOT.parent
CODE_FACTORY_ROOT = WORKSPACE_ROOT / "code-factory"
RETURNED_ASSIGNMENTS_DIR = ENGEL_APP_ROOT / "remote_workers" / "communication_queen_assignments" / "returned"
LINK_MANAGER_STATE_PATH = ENGEL_APP_ROOT / "remote_workers" / "lan_link_manager" / "session_state.json"

if str(CODE_FACTORY_ROOT) not in sys.path:
    sys.path.insert(0, str(CODE_FACTORY_ROOT))


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _clip(text: Any, limit: int = 900) -> str:
    value = "" if text is None else str(text)
    value = value.replace("\r", " ").strip()
    if len(value) > limit:
        return value[:limit] + "..."
    return value


def _run_git(args: list[str], cwd: Path = CODE_FACTORY_ROOT, timeout: int = 120) -> tuple[int, str, str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def _git_text(args: list[str]) -> str:
    rc, out, err = _run_git(args)
    return (out if rc == 0 else err).strip()


def _seed_issue(path: Path, *, issue_id: str, title: str, body: str, acceptance: list[str]) -> None:
    lines = [
        "---",
        f"id: {issue_id}",
        f"title: {title}",
        "labels: [ready-for-factory, code-factory-hour-loop]",
        "priority: P2",
        "size: small",
        "status: new",
        "acceptance_criteria:",
    ]
    lines.extend(f"  - {item}" for item in acceptance)
    lines.extend(["---", "", body.strip(), ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def _seed_set_name() -> str:
    return os.environ.get("ENGEL_CODE_FACTORY_SEED_SET", "default").strip() or "default"


def _default_issue_defs() -> list[dict[str, Any]]:
    return [
        {
            "slug": "show-runtime-paths",
            "title": "Add --show-runtime-paths flag in factory.py",
            "body": (
                "Add a CLI option that prints the active runtime directories "
                "for queue, specs, builds, reviews, and pull-request bundles, then exits."
            ),
            "acceptance": [
                "Running python factory.py --show-runtime-paths prints queue, specs, builds, reviews, and pull-requests paths",
                "The command exits 0 without running Intake, Scout, Builder, QA, or Ship",
                "Argparse help lists --show-runtime-paths",
            ],
        },
        {
            "slug": "event-log-tail",
            "title": "Add optional limit to load_events in lib/logging.py",
            "body": (
                "Let operators read only the latest N event records without loading "
                "or returning the entire JSONL history."
            ),
            "acceptance": [
                "load_events accepts an optional limit argument",
                "When limit is supplied, only the newest records are returned in original order",
                "Existing load_events(path) behavior remains unchanged",
            ],
        },
        {
            "slug": "frontmatter-tests",
            "title": "Add issue frontmatter parsing tests for local issues",
            "body": (
                "Add focused tests for local issue markdown frontmatter, including "
                "labels and acceptance criteria lists."
            ),
            "acceptance": [
                "Tests cover labels parsed from bracket list frontmatter",
                "Tests cover multiline acceptance criteria frontmatter",
                "Tests cover fallback id/title behavior when frontmatter is absent",
            ],
        },
        {
            "slug": "repo-grep-excludes-runtime",
            "title": "Make repo grep ignore factory runtime directories",
            "body": (
                "Factory code search should not let generated runtime logs, build "
                "reports, or pull-request bundles dominate Scout grep hits."
            ),
            "acceptance": [
                "grep excludes runtime directories when ripgrep is available",
                "The git grep fallback continues to work",
                "A focused test or documented smoke check covers the ignore behavior",
            ],
        },
        {
            "slug": "readme-runtime-paths",
            "title": "Document runtime paths and review bundles in README.md",
            "body": (
                "Document where operators can inspect queue, specs, builds, reviews, "
                "and local PR bundles after a Code Factory run."
            ),
            "acceptance": [
                "README includes the runtime queue path",
                "README includes the runtime specs/builds/reviews paths",
                "README includes the runtime pull-requests bundle path",
            ],
        },
    ]


def _fresh_issue_defs() -> list[dict[str, Any]]:
    return [
        {
            "slug": "doctor-command",
            "title": "Add a local --doctor preflight command",
            "body": (
                "Add a no-network doctor/preflight CLI command that checks core local prerequisites "
                "for Code Factory operators without running any station."
            ),
            "acceptance": [
                "Running python factory.py --doctor exits 0 and prints a concise local preflight report",
                "The report includes config path, target repo path, builder CLI availability, and JSONL log path",
                "The command does not run Intake, Scout, Builder, QA, or Ship",
            ],
        },
        {
            "slug": "event-log-summary",
            "title": "Add an event log summary CLI command",
            "body": (
                "Add a command that summarizes the configured JSONL event log by station and event "
                "so operators can quickly understand a long run."
            ),
            "acceptance": [
                "Running python factory.py --event-log-summary prints valid JSON",
                "The JSON includes total_events, stations, and events maps",
                "An empty or missing event log reports zero events instead of failing",
            ],
        },
        {
            "slug": "queue-status",
            "title": "Add a queue status command for station handoffs",
            "body": (
                "Add a CLI command that prints counts for each station handoff directory so Engel "
                "can quickly show Factory backlog health."
            ),
            "acceptance": [
                "Running python factory.py --queue-status prints valid JSON",
                "The JSON includes queue, specs, builds, reviews, pull_requests, and state counts",
                "The command exits 0 without running any station",
            ],
        },
        {
            "slug": "readme-operator-quickstart",
            "title": "Document the operator quickstart commands",
            "body": (
                "Update README.md with a compact operator quickstart that shows the safe local "
                "inspection commands before running the factory loop."
            ),
            "acceptance": [
                "README includes --doctor in the quickstart",
                "README includes --queue-status in the quickstart",
                "README includes --event-log-summary in the quickstart",
            ],
        },
        {
            "slug": "safety-test-no-station-side-effects",
            "title": "Add tests proving inspection commands do not run stations",
            "body": (
                "Add focused tests for new inspection commands so they remain safe status/read-only "
                "commands and do not trigger station execution."
            ),
            "acceptance": [
                "Tests cover --doctor without station side effects",
                "Tests cover --queue-status without station side effects",
                "Tests cover --event-log-summary with a missing or empty event log",
            ],
        },
    ]


def _ui_hour_issue_defs() -> list[dict[str, Any]]:
    return [
        {
            "slug": "issue-summary-command",
            "title": "Add a local issue summary command",
            "body": (
                "Add a read-only CLI command that summarizes parsed local issues by status, "
                "priority, size, and label so Engel can see Factory backlog shape before a run."
            ),
            "acceptance": [
                "Running python factory.py --issue-summary prints valid JSON and exits 0",
                "The JSON includes total_issues, status, priority, size, and labels maps",
                "The command does not run Intake, Scout, Builder, QA, or Ship",
            ],
        },
        {
            "slug": "config-check-command",
            "title": "Add a local config check command",
            "body": (
                "Add a no-network CLI command that reports whether the resolved config points "
                "to usable local Factory directories and target repo paths."
            ),
            "acceptance": [
                "Running python factory.py --config-check prints valid JSON and exits 0 for a valid config",
                "The JSON includes config_path, factory_root, target_repo, target_repo_exists, local_issues_dir, and jsonl_log",
                "The command exits without running any station",
            ],
        },
        {
            "slug": "event-tail-json-array",
            "title": "Add JSON array mode for event log tail",
            "body": (
                "The event tail command currently emits JSONL. Add an optional flag that prints "
                "the same limited events as a single JSON array for UI consumers."
            ),
            "acceptance": [
                "Running python factory.py --event-log-tail 5 --json-array prints a valid JSON array",
                "Without --json-array, --event-log-tail keeps the existing JSONL behavior",
                "Tests cover both output modes",
            ],
        },
        {
            "slug": "operator-command-tests",
            "title": "Add tests for operator inspection commands",
            "body": (
                "Add focused tests for the new issue-summary, config-check, and event-tail JSON "
                "array commands so they remain safe read-only operator commands."
            ),
            "acceptance": [
                "Tests cover --issue-summary with local markdown issues",
                "Tests cover --config-check with a temporary config",
                "Tests cover --event-log-tail with --json-array",
            ],
        },
        {
            "slug": "readme-inspection-commands",
            "title": "Document the new safe inspection commands",
            "body": (
                "Update README.md so an Engel operator can discover and run the new read-only "
                "inspection commands without starting Factory stations."
            ),
            "acceptance": [
                "README includes --issue-summary",
                "README includes --config-check",
                "README includes --event-log-tail N --json-array",
            ],
        },
        {
            "slug": "pull-request-index-command",
            "title": "Add a local pull-request bundle index command",
            "body": (
                "Add a read-only CLI command that lists local Ship bundles with issue id, "
                "branch, files changed, and bundle path so Engel can surface review work."
            ),
            "acceptance": [
                "Running python factory.py --pull-request-index prints valid JSON and exits 0",
                "The JSON includes bundle_count and bundles with issue_id, branch, files_changed, and path",
                "The command does not run Intake, Scout, Builder, QA, or Ship",
            ],
        },
        {
            "slug": "state-snapshot-command",
            "title": "Add a local state snapshot command",
            "body": (
                "Add a read-only CLI command that reports the current station handoff counts, "
                "last scheduler state, and configured sleep/scout timing."
            ),
            "acceptance": [
                "Running python factory.py --state-snapshot prints valid JSON and exits 0",
                "The JSON includes handoff_counts, scheduler_state, scout_interval_sec, and loop_sleep_sec",
                "The command exits without running any station",
            ],
        },
        {
            "slug": "readme-troubleshooting",
            "title": "Document local troubleshooting checks",
            "body": (
                "Add a concise troubleshooting section for local-only Factory runs, including "
                "where to inspect logs, bundles, and safe status commands."
            ),
            "acceptance": [
                "README includes a Troubleshooting section",
                "The section points to runtime/logs/events.jsonl",
                "The section mentions local review bundles under runtime/pull-requests",
            ],
        },
        {
            "slug": "command-output-contract-tests",
            "title": "Add tests for JSON inspection command output contracts",
            "body": (
                "Add tests that parse new inspection command output as JSON and verify key "
                "fields remain stable for Engel UI consumers."
            ),
            "acceptance": [
                "Tests parse --issue-summary output as JSON",
                "Tests parse --config-check output as JSON",
                "Tests parse --state-snapshot or --pull-request-index output as JSON",
            ],
        },
        {
            "slug": "event-log-level-filter",
            "title": "Add a level filter to event log tail",
            "body": (
                "Let operators request only events at a specific log level when tailing "
                "the event log, while keeping the existing default behavior unchanged."
            ),
            "acceptance": [
                "Running python factory.py --event-log-tail 20 --level ERROR returns only ERROR events",
                "Without --level, --event-log-tail keeps the existing behavior",
                "Tests cover the level filter with sample events",
            ],
        },
        {
            "slug": "local-issue-export-command",
            "title": "Add a local issue export command",
            "body": (
                "Add a read-only CLI command that exports parsed local issues as one JSON "
                "document with metadata for Engel UI ingestion."
            ),
            "acceptance": [
                "Running python factory.py --export-local-issues prints valid JSON and exits 0",
                "The JSON includes issue_count and issues",
                "The command does not run any station",
            ],
        },
        {
            "slug": "spec-status-command",
            "title": "Add a spec status command",
            "body": (
                "Add a read-only CLI command that summarizes Scout specs by status and lists "
                "ready, built, failed, and shipped issue ids."
            ),
            "acceptance": [
                "Running python factory.py --spec-status prints valid JSON and exits 0",
                "The JSON includes total_specs, statuses, and issue_ids_by_status",
                "The command does not run Builder or mutate spec files",
            ],
        },
        {
            "slug": "qa-review-summary-command",
            "title": "Add a QA review summary command",
            "body": (
                "Add a read-only CLI command that summarizes QA review results so Engel can "
                "quickly see pass/fail counts and failing criteria."
            ),
            "acceptance": [
                "Running python factory.py --qa-summary prints valid JSON and exits 0",
                "The JSON includes total_reviews, passed, failed, and failing_criteria",
                "Missing review directories return zero counts instead of failing",
            ],
        },
        {
            "slug": "readme-review-workflow",
            "title": "Document the local review workflow",
            "body": (
                "Update README.md with a short workflow for reviewing local PR bundles, "
                "checking diffs, and deciding whether to merge a Factory branch."
            ),
            "acceptance": [
                "README explains how to inspect runtime/pull-requests/<issue-id>/PR.md",
                "README explains how to inspect diff.patch",
                "README repeats that nothing is pushed automatically",
            ],
        },
        {
            "slug": "malformed-event-log-test",
            "title": "Add tests for malformed event log lines",
            "body": (
                "Add tests proving event log readers skip malformed lines safely while "
                "preserving valid events in original order."
            ),
            "acceptance": [
                "Tests include a malformed JSONL line",
                "Valid events before and after the malformed line are still returned",
                "The behavior is documented in the test name or assertion message",
            ],
        },
    ]


def _four_hour_acceptance(kind: str, slug: str) -> list[str]:
    flag = "--" + slug.replace("_", "-")
    if kind == "command":
        return [
            f"Running python factory.py {flag} prints valid JSON and exits 0",
            "The JSON includes stable fields useful to Engel AI or Agent Meeting Room UI consumers",
            "The command does not run Intake, Scout, Builder, QA, or Ship",
        ]
    if kind == "test":
        return [
            "Focused tests cover the behavior with temporary local Factory runtime data",
            "The tests do not require network, providers, phone USB, or external credentials",
            "Existing behavior remains compatible with current Code Factory commands",
        ]
    if kind == "doc":
        return [
            "README or local docs describe the workflow in operator-friendly language",
            "The docs point to the local runtime/report paths used by Engel AI",
            "The docs repeat that Code Factory does not push or mutate remote services automatically",
        ]
    return [
        "The implementation is local-only and safe for Engel AI orchestration",
        "Tests or a documented smoke check verify the new behavior",
        "The change keeps existing Code Factory commands backward compatible",
    ]


def _ui_four_hour_issue_defs() -> list[dict[str, Any]]:
    items = [
        ("command", "engel-order-receipts", "Add an Engel order receipt index command", "Summarize Engel UI order receipts that started Code Factory runs."),
        ("command", "meeting-room-routing-summary", "Add a Meeting Room routing summary command", "Report which agents and skills were selected for recent Factory runs."),
        ("command", "device-assist-summary", "Add a device assist summary command", "Summarize Alpha and Beta phone assist returns for Factory runs."),
        ("command", "bundle-risk-index", "Add a bundle risk index command", "List shipped bundles with review notes and changed file counts."),
        ("command", "qa-retry-history", "Add a QA retry history command", "Show issues that failed QA first and passed after retry."),
        ("command", "engel-run-timeline", "Add an Engel run timeline command", "Export intake, scout, builder, QA, and ship events as one JSON timeline."),
        ("command", "factory-health-json", "Add a Factory health JSON command", "Report local runtime health for Engel AI status views."),
        ("command", "agent-skill-coverage", "Add an agent skill coverage command", "Summarize which agent skills contributed to Factory runs."),
        ("command", "device-first-policy-check", "Add a device-first policy check command", "Report whether phone assist was attempted before main-PC fallback."),
        ("command", "engel-artifact-index", "Add an Engel artifact index command", "Index reports, screenshots, and bundle artifacts for a run id."),
        ("command", "safe-command-registry", "Add a safe command registry command", "List read-only Code Factory inspection commands for Engel UI menus."),
        ("command", "run-duration-audit", "Add a run duration audit command", "Compare target duration to elapsed duration for local Factory runs."),
        ("command", "seed-set-audit", "Add a seed set audit command", "Report seed set name and unique issue slug counts."),
        ("command", "issue-uniqueness-check", "Add an issue uniqueness check command", "Detect duplicate issue slugs and titles before a long run."),
        ("command", "bundle-manifest-json", "Add a bundle manifest JSON command", "Emit per-bundle PR path, patch path, branch, and issue id."),
        ("command", "report-link-check", "Add a local report link check command", "Verify that saved report paths still exist under the workspace."),
        ("command", "station-latency-summary", "Add a station latency summary command", "Summarize Builder and QA timing from event logs."),
        ("command", "builder-attempt-summary", "Add a builder attempt summary command", "Report attempts per issue and retry counts."),
        ("command", "qa-note-index", "Add a QA note index command", "Collect QA notes from review JSON files for Engel display."),
        ("command", "engagement-summary", "Add an Engel engagement summary command", "Summarize prompt, selected agents, device returns, and final result."),
        ("test", "malformed-status-json", "Add tests for malformed status JSON handling", "Status readers should skip malformed JSON and keep running."),
        ("test", "missing-report-paths", "Add tests for missing report paths", "Report index commands should return empty data instead of crashing."),
        ("test", "device-summary-empty-state", "Add tests for empty device summaries", "Device assist summary should work when no phones returned packets."),
        ("test", "agent-routing-empty-state", "Add tests for empty routing summaries", "Meeting Room routing summaries should handle missing room state."),
        ("test", "bundle-manifest-empty-state", "Add tests for empty bundle manifests", "Bundle manifest commands should handle an empty pull-request directory."),
        ("test", "qa-retry-history-empty-state", "Add tests for empty QA retry history", "QA retry history should report zero retries without failure."),
        ("test", "timeline-ordering", "Add tests for timeline ordering", "Run timelines should preserve chronological event order."),
        ("test", "issue-uniqueness", "Add tests for issue uniqueness checks", "Duplicate and unique issue sets should be detected clearly."),
        ("test", "seed-set-audit", "Add tests for seed set audit output", "Seed set audit output should be parseable JSON with unique counts."),
        ("test", "safe-command-registry", "Add tests for safe command registry output", "The safe command registry should include read-only flags only."),
        ("test", "station-latency-summary", "Add tests for station latency summary", "Latency summary should compute from sample Builder event pairs."),
        ("test", "builder-attempt-summary", "Add tests for builder attempt summary", "Builder attempt summary should count retries from sample events."),
        ("test", "qa-note-index", "Add tests for QA note index", "QA note index should collect notes without leaking full patches."),
        ("test", "run-duration-audit", "Add tests for run duration audit", "Duration audit should identify finished and in-progress statuses."),
        ("test", "report-link-check", "Add tests for report link checks", "Report link checks should separate existing and missing paths."),
        ("doc", "engel-ui-to-factory-flow", "Document the Engel UI to Factory flow", "Explain how user input becomes Meeting Room Factory work."),
        ("doc", "device-first-factory-policy", "Document the device-first Factory policy", "Describe phone assist before main-PC fallback for long runs."),
        ("doc", "qa-retry-operator-guide", "Document QA retry behavior", "Explain how failed QA blocks shipping and retries an issue."),
        ("doc", "four-hour-run-playbook", "Document the four-hour Factory playbook", "Give operators the exact local checks for long Factory runs."),
        ("doc", "bundle-review-checklist", "Document a bundle review checklist", "Show how to inspect PR.md, diff.patch, and review JSON."),
        ("doc", "engel-memory-save-process", "Document the Engel memory save process", "Explain what gets saved to memory after a Factory run."),
        ("doc", "phone-worker-evidence-guide", "Document phone worker evidence", "Explain where Alpha and Beta returned packet receipts live."),
        ("doc", "factory-report-cleanup-guide", "Document Factory report cleanup", "Explain which run files are evidence and which are transient."),
        ("doc", "operator-status-dashboard", "Document operator status dashboard fields", "Describe useful status fields for Engel UI panels."),
        ("doc", "safe-local-only-boundaries", "Document safe local-only boundaries", "Clarify that Factory does not push, install, or use secrets automatically."),
        ("hardening", "normalize-run-id-input", "Normalize run id input for inspection commands", "Run id arguments should reject path traversal and odd separators."),
        ("hardening", "stable-json-errors", "Return stable JSON errors for inspection commands", "Inspection commands should return predictable error JSON."),
        ("hardening", "workspace-path-guard", "Add a workspace path guard helper", "Helpers should keep report scans inside the workspace."),
        ("hardening", "redact-home-paths", "Redact personal home paths from generated summaries", "Operator summaries should avoid exposing personal directories."),
        ("hardening", "bounded-report-read", "Bound report file reads", "Report readers should avoid loading huge files fully."),
        ("hardening", "skip-binary-artifacts", "Skip binary artifacts in text indexes", "Artifact indexes should ignore binary files safely."),
        ("hardening", "jsonl-error-counter", "Count skipped JSONL parse errors", "Event readers should report malformed line counts."),
        ("hardening", "missing-runtime-root", "Handle missing runtime root gracefully", "Commands should report missing runtime roots without stack traces."),
        ("hardening", "case-insensitive-run-search", "Support case-insensitive run search", "Run lookup should work with case-insensitive user input."),
        ("hardening", "safe-relative-path-output", "Prefer safe relative paths in JSON output", "Inspection JSON should include workspace-relative paths when possible."),
        ("command", "engel-run-compare", "Add an Engel run compare command", "Compare two Factory runs by issues, bundles, devices, and test results."),
        ("command", "latest-run-status", "Add a latest run status command", "Find the newest local Factory status JSON and summarize it."),
        ("command", "failed-criteria-export", "Add a failed criteria export command", "Export failing QA criteria for issues that need another pass."),
        ("command", "prompt-to-issue-map", "Add a prompt to issue map command", "Map the original Engel prompt to seeded issue ids."),
        ("command", "factory-session-card", "Add a Factory session card command", "Emit a compact card summary for Engel UI display."),
        ("command", "agent-device-map", "Add an agent device map command", "Map selected agents to devices and skills for a run."),
        ("command", "main-pc-fallback-report", "Add a main-PC fallback report command", "Report when Factory had to use main PC instead of phones."),
        ("command", "artifact-size-summary", "Add an artifact size summary command", "Summarize report and bundle sizes by run."),
        ("command", "test-result-index", "Add a test result index command", "Index recorded test commands and pass/fail outcomes."),
        ("command", "memory-candidate-index", "Add a memory candidate index command", "List memory candidate files written for Factory runs."),
        ("test", "latest-run-status", "Add tests for latest run status", "Latest run status should choose the newest status file by timestamp."),
        ("test", "engel-run-compare", "Add tests for Engel run compare", "Run compare should report deltas for two sample statuses."),
        ("test", "prompt-to-issue-map", "Add tests for prompt to issue map", "Prompt map should include prompt text and seeded issue ids."),
        ("test", "agent-device-map", "Add tests for agent device map", "Agent device map should include agent, device, skill, and status fields."),
        ("test", "main-pc-fallback-report", "Add tests for main-PC fallback report", "Fallback report should distinguish phone returns from stale workers."),
        ("test", "artifact-size-summary", "Add tests for artifact size summary", "Artifact summary should compute sizes without reading file contents."),
        ("doc", "run-compare-guide", "Document comparing Factory runs", "Explain how to compare one-hour and four-hour Factory runs."),
        ("doc", "memory-candidate-review-guide", "Document memory candidate review", "Explain how to review and promote Factory memory candidates."),
        ("doc", "long-run-troubleshooting", "Document long-run troubleshooting", "List checks for stalled builders, stale devices, and failed QA."),
        ("doc", "factory-device-map-guide", "Document Factory device map output", "Explain how Engel UI can display device and skill routing."),
        ("doc", "test-result-index-guide", "Document test result indexing", "Describe how to store final test evidence for Engel memory."),
        ("hardening", "stable-command-exit-codes", "Stabilize inspection command exit codes", "Read-only command failures should use clear nonzero exit codes."),
        ("hardening", "atomic-report-write", "Use atomic writes for generated reports", "Report writers should avoid partially-written JSON files."),
        ("hardening", "status-schema-version", "Add status schema version field", "Status JSON should expose a schema version for Engel UI readers."),
        ("hardening", "bundle-schema-version", "Add bundle schema version field", "Bundle manifests should expose a schema version for future UI readers."),
        ("hardening", "validate-output-mode", "Validate output mode options", "Output mode flags should reject unsupported values cleanly."),
        ("hardening", "guard-large-jsonl-tail", "Guard large JSONL tail limits", "Tail commands should clamp huge limits to a safe maximum."),
        ("hardening", "sort-index-output", "Sort index command output", "Index commands should emit stable sorted lists for UI diffs."),
        ("hardening", "dedupe-qa-notes", "Deduplicate QA notes", "QA note summaries should avoid repeated identical notes."),
        ("hardening", "safe-missing-git", "Handle missing git executable", "Inspection commands should report missing git without crashing."),
        ("hardening", "safe-missing-ripgrep", "Handle missing ripgrep executable", "Search helpers should fall back safely when rg is unavailable."),
    ]
    result: list[dict[str, Any]] = []
    used: dict[str, int] = {}
    for kind, slug, title, body in items:
        unique_slug = slug
        if slug in used:
            used[slug] += 1
            unique_slug = f"{slug}-{kind}-{used[slug]}"
        else:
            used[slug] = 1
        result.append(
            {
                "slug": unique_slug,
                "title": title,
                "body": body,
                "acceptance": _four_hour_acceptance(kind, unique_slug),
            }
        )
    return result


def _issue_defs() -> list[dict[str, Any]]:
    seed_set = _seed_set_name().lower()
    if seed_set in {"ui-4hour", "ui-four-hour", "ui-4hour-20260528", "engel-ui-4hour"}:
        return _ui_four_hour_issue_defs()
    if seed_set in {"ui-hour", "ui-hour-v2", "ui-hour-20260528", "engel-ui-hour"}:
        return _ui_hour_issue_defs()
    if seed_set in {"fresh", "fresh-v2", "new", "new-items", "new-items-v2", "20260527-new"}:
        return _fresh_issue_defs()
    return _default_issue_defs()


def _seed_issues(issue_dir: Path, run_id: str) -> list[Path]:
    issue_dir.mkdir(parents=True, exist_ok=True)
    issue_defs = _issue_defs()
    written: list[Path] = []
    for idx, item in enumerate(issue_defs, start=1):
        issue_id = f"{run_id}-{idx:02d}-{item['slug']}"
        path = issue_dir / f"{issue_id}.md"
        _seed_issue(
            path,
            issue_id=issue_id,
            title=str(item["title"]),
            body=str(item["body"]),
            acceptance=[str(value) for value in item["acceptance"]],
        )
        written.append(path)
    return written


def _build_config(run_root: Path):
    from lib.config import Config

    runtime_root = run_root / "factory_runtime"
    return Config(
        factory_root=runtime_root,
        target_repo=CODE_FACTORY_ROOT,
        local_issues_dir=run_root / "issues",
        github_enabled=False,
        github_repo="",
        github_label="ready-for-factory",
        branch_prefix="factory/hour-loop/",
        open_pr_online=False,
        model_intake="engel-chatgpt-bridge",
        model_scout="engel-chatgpt-bridge",
        model_qa="engel-chatgpt-bridge",
        builder_cli="codex",
        builder_args=["--full-auto", "--ephemeral", "-m", "gpt-5.3-codex"],
        scout_interval_sec=60,
        builder_max_retries=1,
        loop_sleep_sec=45,
        max_issues_per_cycle=2,
        builder_timeout_sec=1800,
        log_level="INFO",
        jsonl_log=runtime_root / "logs" / "events.jsonl",
        raw={},
    )


def _count_files(path: Path, pattern: str) -> int:
    return len(list(path.glob(pattern))) if path.exists() else 0


def _load_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def _device_load_share_path(run_root: Path) -> Path:
    return run_root / "device_load_share.json"


def _load_device_load_share(run_root: Path) -> dict[str, Any]:
    payload = _read_json(_device_load_share_path(run_root))
    return payload if isinstance(payload, dict) else {}


def _worker_age_seconds(worker_id: str, now: dt.datetime | None = None) -> float | None:
    state = _read_json(LINK_MANAGER_STATE_PATH)
    if not isinstance(state, dict):
        return None
    workers = state.get("workers")
    if not isinstance(workers, dict):
        return None
    record = workers.get(worker_id)
    if not isinstance(record, dict):
        return None
    raw_seen = str(record.get("last_seen_utc") or "").strip()
    if not raw_seen:
        return None
    try:
        seen = dt.datetime.fromisoformat(raw_seen.replace("Z", "+00:00"))
    except ValueError:
        return None
    current = now or dt.datetime.now(dt.timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=dt.timezone.utc)
    return max(0.0, (current.astimezone(dt.timezone.utc) - seen.astimezone(dt.timezone.utc)).total_seconds())


def _find_worker_return(packet_id: str, worker_id: str) -> tuple[Path, dict[str, Any]] | None:
    if not packet_id or not RETURNED_ASSIGNMENTS_DIR.exists():
        return None
    matches: list[tuple[Path, dict[str, Any]]] = []
    for path in RETURNED_ASSIGNMENTS_DIR.glob("*.json"):
        payload = _read_json(path)
        if not isinstance(payload, dict):
            continue
        if str(payload.get("packet_id") or "") != packet_id:
            continue
        if str(payload.get("worker_id") or "") != worker_id:
            continue
        matches.append((path, payload))
    return sorted(matches, key=lambda item: item[0].name)[-1] if matches else None


def _returned_preview(payload: dict[str, Any]) -> dict[str, Any]:
    caps = payload.get("device_capabilities")
    caps = caps if isinstance(caps, dict) else {}
    connectivity = caps.get("connectivity") if isinstance(caps.get("connectivity"), dict) else {}
    android = caps.get("android") if isinstance(caps.get("android"), dict) else {}
    app_info = caps.get("app") if isinstance(caps.get("app"), dict) else {}
    draft_text = str(payload.get("draft_text") or "")
    return {
        "result_type": payload.get("result_type"),
        "trust_level": payload.get("trust_level"),
        "status": payload.get("status"),
        "safe_to_auto_apply": payload.get("safe_to_auto_apply"),
        "human_review_required": payload.get("human_review_required"),
        "preview": _clip(draft_text, 1200),
        "device": {
            "worker_id": caps.get("worker_id") or payload.get("worker_id"),
            "worker_name": caps.get("worker_name"),
            "model": android.get("model") or caps.get("configured_phone_model"),
            "android_release": android.get("release"),
            "cpu_cores": caps.get("cpu_cores"),
            "transports": connectivity.get("transports"),
            "app_version": app_info.get("version"),
            "app_build": app_info.get("build_number"),
        },
    }


def _run_device_load_share_assist(run_root: Path, run_id: str, log, *, wait_seconds: float | None = None) -> dict[str, Any]:
    """Stage bounded phone-worker assist tasks and collect WiFi returns.

    The phones never mutate Code Factory source. Their outputs are candidate
    drafts that help the Meeting Room share analysis/load across devices while
    Codex Builder remains the only source-editing lane.
    """
    wait = wait_seconds
    if wait is None:
        raw = os.environ.get("ENGEL_CODE_FACTORY_DEVICE_ASSIST_WAIT_SECONDS", "120")
        try:
            wait = max(0.0, min(300.0, float(raw)))
        except ValueError:
            wait = 120.0

    started_utc = dt.datetime.now(dt.timezone.utc)
    assist: dict[str, Any] = {
        "run_id": run_id,
        "started_at_utc": started_utc.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "wait_seconds": wait,
        "mode": "bounded_phone_assist_candidates_only",
        "required_workers": ["android_worker_alpha", "android_worker_beta"],
        "assignments": [],
        "safety": {
            "job_payload_over_usb": False,
            "wifi_lan_assignment_queue": True,
            "trusted_memory_write": False,
            "source_mutation_from_phone": False,
            "auto_apply": False,
            "human_review_required": True,
        },
    }
    _write_json(_device_load_share_path(run_root), assist)

    try:
        from engel_communication_queen_assignment_producer import create_assignment
    except Exception as exc:
        assist["status"] = "producer_unavailable"
        assist["error"] = f"{type(exc).__name__}: {exc}"
        _write_json(_device_load_share_path(run_root), assist)
        try:
            log.emit("devices", "assist_unavailable", error=assist["error"])
        except Exception:
            pass
        return assist

    assignment_defs = [
        {
            "worker": "android_worker_alpha",
            "task_type": "draft_code_artifact",
            "title": f"{run_id} Alpha code/research assist",
            "instructions": (
                "Code Factory assist packet for Engel AI. Review the seeded Factory issues and return "
                "a candidate-only code/test approach for runtime-path reporting and search/runtime ignores. "
                "Use your Android Worker capability snapshot in the result. Do not change source files."
            ),
        },
        {
            "worker": "android_worker_beta",
            "task_type": "draft_candidate_json",
            "title": f"{run_id} Beta QA/report assist",
            "instructions": (
                "Code Factory assist packet for Engel AI. Return structured JSON that maps the seeded "
                "Factory issue themes to the best station, device, skill, acceptance checks, and likely "
                "verification commands. Candidate-only output; no source changes."
            ),
        },
    ]

    for item in assignment_defs:
        worker_id = item["worker"]
        age = _worker_age_seconds(worker_id, started_utc)
        assignment: dict[str, Any] = {
            "worker_id": worker_id,
            "last_seen_age_seconds": age,
            "online_for_wifi": age is not None and age <= 900,
            "task_type": item["task_type"],
            "title": item["title"],
        }
        if not assignment["online_for_wifi"]:
            assignment["status"] = "offline_or_stale"
            assist["assignments"].append(assignment)
            try:
                log.emit("devices", "assist_worker_stale", worker_id=worker_id, age_seconds=age)
            except Exception:
                pass
            continue
        try:
            packet, packet_path, receipt_path = create_assignment(
                worker=worker_id,
                task_type=item["task_type"],
                title=item["title"],
                instructions=item["instructions"],
            )
            assignment.update(
                {
                    "status": "assigned",
                    "packet_id": packet.get("packet_id"),
                    "packet_path": str(packet_path),
                    "receipt_path": str(receipt_path),
                }
            )
            try:
                log.emit(
                    "devices",
                    "assist_assignment_created",
                    worker_id=worker_id,
                    task_type=item["task_type"],
                    packet_id=packet.get("packet_id"),
                )
            except Exception:
                pass
        except Exception as exc:
            assignment["status"] = "assignment_failed"
            assignment["error"] = f"{type(exc).__name__}: {exc}"
            try:
                log.emit("devices", "assist_assignment_failed", worker_id=worker_id, error=assignment["error"])
            except Exception:
                pass
        assist["assignments"].append(assignment)
        _write_json(_device_load_share_path(run_root), assist)

    deadline = time.time() + float(wait or 0.0)
    pending = {
        item.get("packet_id"): item
        for item in assist["assignments"]
        if item.get("packet_id") and item.get("status") == "assigned"
    }
    while pending and time.time() <= deadline:
        for packet_id, assignment in list(pending.items()):
            found = _find_worker_return(str(packet_id), str(assignment.get("worker_id") or ""))
            if found is None:
                continue
            result_path, result_payload = found
            assignment["status"] = "returned"
            assignment["returned_path"] = str(result_path)
            assignment["returned_at_seen_by_pc"] = _now()
            assignment["result"] = _returned_preview(result_payload)
            pending.pop(packet_id, None)
            try:
                log.emit(
                    "devices",
                    "assist_returned",
                    worker_id=assignment.get("worker_id"),
                    packet_id=packet_id,
                    result=str(result_payload.get("result_type") or ""),
                    returned_path=str(result_path),
                )
            except Exception:
                pass
        _write_json(_device_load_share_path(run_root), assist)
        if pending:
            time.sleep(2.0)

    for assignment in assist["assignments"]:
        if assignment.get("status") == "assigned":
            assignment["status"] = "waiting_for_return"
            try:
                log.emit(
                    "devices",
                    "assist_waiting_for_return",
                    worker_id=assignment.get("worker_id"),
                    packet_id=assignment.get("packet_id"),
                )
            except Exception:
                pass

    returned_count = sum(1 for item in assist["assignments"] if item.get("status") == "returned")
    assist["returned_count"] = returned_count
    assist["assigned_count"] = sum(1 for item in assist["assignments"] if item.get("packet_id"))
    assist["status"] = "returned" if returned_count >= 2 else ("partial" if returned_count else "no_returns_yet")
    assist["completed_at_utc"] = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    _write_json(_device_load_share_path(run_root), assist)
    return assist


def _snapshot(run_root: Path, cfg, *, run_id: str, state: str, cycle: int, started: float, duration_sec: int, note: str = "") -> dict[str, Any]:
    events = _load_events(cfg.jsonl_log)
    device_load_share = _load_device_load_share(run_root)
    return {
        "run_id": run_id,
        "state": state,
        "cycle": cycle,
        "note": note,
        "started_at": dt.datetime.fromtimestamp(started).isoformat(timespec="seconds"),
        "updated_at": _now(),
        "elapsed_sec": round(time.time() - started, 1),
        "duration_sec": duration_sec,
        "target_repo": str(CODE_FACTORY_ROOT),
        "run_root": str(run_root),
        "seed_set": _seed_set_name(),
        "issues": _count_files(run_root / "issues", "*.md"),
        "queue": _count_files(cfg.queue_dir, "*.json"),
        "specs": _count_files(cfg.specs_dir, "*.json"),
        "builds": _count_files(cfg.builds_dir, "*.json"),
        "reviews": _count_files(cfg.reviews_dir, "*.json"),
        "pull_request_bundles": _count_files(cfg.pr_dir, "*"),
        "git_branch": _git_text(["rev-parse", "--abbrev-ref", "HEAD"]),
        "git_status": _git_text(["status", "--porcelain"]),
        "last_events": events[-20:],
        "device_load_share": {
            "status": device_load_share.get("status"),
            "assigned_count": device_load_share.get("assigned_count", 0),
            "returned_count": device_load_share.get("returned_count", 0),
            "path": str(_device_load_share_path(run_root)),
            "assignments": [
                {
                    "worker_id": item.get("worker_id"),
                    "task_type": item.get("task_type"),
                    "status": item.get("status"),
                    "packet_id": item.get("packet_id"),
                    "returned_path": item.get("returned_path"),
                    "device": (item.get("result") or {}).get("device") if isinstance(item.get("result"), dict) else None,
                }
                for item in device_load_share.get("assignments", [])
                if isinstance(item, dict)
            ],
        },
        "event_log": str(cfg.jsonl_log),
        "report_path": str(run_root / "ENGEL_CODE_FACTORY_HOUR_LOOP_REPORT.md"),
    }


def _write_report(run_root: Path, status: dict[str, Any]) -> Path:
    report = run_root / "ENGEL_CODE_FACTORY_HOUR_LOOP_REPORT.md"
    events = status.get("last_events") or []
    lines = [
        "# Engel Code Factory Hour Loop",
        "",
        f"- Run: `{status.get('run_id')}`",
        f"- State: `{status.get('state')}`",
        f"- Elapsed seconds: `{status.get('elapsed_sec')}`",
        f"- Target repo: `{status.get('target_repo')}`",
        f"- Seed set: `{status.get('seed_set')}`",
        f"- Issues seeded: `{status.get('issues')}`",
        f"- Specs: `{status.get('specs')}`",
        f"- Builds: `{status.get('builds')}`",
        f"- Reviews: `{status.get('reviews')}`",
        f"- Pull-request bundles: `{status.get('pull_request_bundles')}`",
        f"- Device assist status: `{(status.get('device_load_share') or {}).get('status')}`",
        f"- Device assist returns: `{(status.get('device_load_share') or {}).get('returned_count')}`",
        f"- Git branch after run: `{status.get('git_branch')}`",
        f"- Device load-share map: `{(status.get('device_load_share') or {}).get('path')}`",
        "",
        "## Git Status",
        "",
        "```text",
        str(status.get("git_status") or "(clean)"),
        "```",
        "",
        "## Last Events",
        "",
        "```json",
        json.dumps(events, indent=2, default=str),
        "```",
        "",
        "## Device Load Share",
        "",
        "```json",
        json.dumps(status.get("device_load_share") or {}, indent=2, default=str),
        "```",
    ]
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--prompt-file", required=True)
    parser.add_argument("--duration-sec", type=int, default=3600)
    args = parser.parse_args(argv)

    os.chdir(ENGEL_APP_ROOT)

    run_root = Path(args.run_root).resolve()
    prompt_file = Path(args.prompt_file).resolve()
    duration_sec = max(1, int(args.duration_sec))
    run_id = run_root.name
    status_path = run_root / "status.json"
    started = time.time()

    temp_root = ENGEL_APP_ROOT / "runtime" / "tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    os.environ["TEMP"] = str(temp_root)
    os.environ["TMP"] = str(temp_root)
    os.environ["TMPDIR"] = str(temp_root)

    cfg = _build_config(run_root)
    status_payload = _snapshot(
        run_root, cfg, run_id=run_id, state="starting", cycle=0,
        started=started, duration_sec=duration_sec, note="preparing Code Factory run",
    )
    status_payload["prompt"] = prompt_file.read_text(encoding="utf-8", errors="replace") if prompt_file.exists() else ""
    _write_json(status_path, status_payload)

    try:
        from lib.logging import EventLog
        from lib.repo import ensure_git_repo, current_branch, status as repo_status
        from factory import run_cycle

        ensure_git_repo(CODE_FACTORY_ROOT)
        initial_branch = current_branch(CODE_FACTORY_ROOT)
        seeded = _seed_issues(run_root / "issues", run_id)
        log = EventLog(cfg.jsonl_log, level=cfg.log_level)
        log.emit(
            "factory",
            "hour_loop_started",
            run_id=run_id,
            duration_sec=duration_sec,
            seed_set=_seed_set_name(),
            seeded=len(seeded),
            temp=str(temp_root),
        )
        _run_device_load_share_assist(run_root, run_id, log)

        deadline = started + duration_sec
        cycle = 0
        while True:
            cycle += 1
            _write_json(
                status_path,
                _snapshot(
                    run_root, cfg, run_id=run_id, state="running", cycle=cycle,
                    started=started, duration_sec=duration_sec,
                    note="cycle started",
                ),
            )
            run_cycle(cfg, log, dry_run=False)
            _write_json(
                status_path,
                _snapshot(
                    run_root, cfg, run_id=run_id, state="running", cycle=cycle,
                    started=started, duration_sec=duration_sec,
                    note="cycle finished",
                ),
            )
            if time.time() >= deadline:
                break
            sleep_for = min(cfg.loop_sleep_sec, max(1, int(deadline - time.time())))
            time.sleep(sleep_for)

        if initial_branch and not repo_status(CODE_FACTORY_ROOT).strip():
            _run_git(["checkout", initial_branch], timeout=120)

        final_status = _snapshot(
            run_root, cfg, run_id=run_id, state="finished", cycle=cycle,
            started=started, duration_sec=duration_sec,
            note="duration reached; last in-flight cycle finished",
        )
        report_path = _write_report(run_root, final_status)
        final_status["report_path"] = str(report_path)
        _write_json(status_path, final_status)
        return 0
    except Exception as exc:
        failed = _snapshot(
            run_root, cfg, run_id=run_id, state="failed", cycle=0,
            started=started, duration_sec=duration_sec,
            note=f"{type(exc).__name__}: {exc}",
        )
        report_path = _write_report(run_root, failed)
        failed["report_path"] = str(report_path)
        _write_json(status_path, failed)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
