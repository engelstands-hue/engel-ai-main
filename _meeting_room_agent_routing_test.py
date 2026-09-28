"""Meeting Room — Agent auto-routing test harness.

Simulates Engel (the orchestrator) submitting one job per agent through the
sanctioned intake path `submit_order_from_engel_main_ui()` and verifies that
the Meeting Room auto-selects the matching skill->agent station.

Two passes:
  PASS 1 — local routing.  Per-agent crafted prompt, verify station_labels
           include the expected "<agent> / <skill>" entry.
  PASS 2 — Android-worker dispatch coercion.  Append Android-worker keywords
           to coerce equipment onto an Android device; verify dispatch runs
           through `dispatch_station_work` and reports either a packet
           success or an expected "Needs Review" with the ADB-not-found
           failure (this is the expected outcome on this PC, which has no
           Android device attached and intentionally does not invoke C:-
           installed adb.exe per project memory).

Engel is the orchestrator: every call here goes through the official intake;
no station is created or mutated directly.  No provider calls are made; no
autonomous loops; no source edits outside this test file.

Run:
    python _meeting_room_agent_routing_test.py
"""
from __future__ import annotations

import json
import shutil
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import engel_agent_meeting_room as mr


# ─── Per-agent test prompts ────────────────────────────────────────────────
# Each entry: agent_label -> (skill_label_expected, prompt_text)
# Prompts use the most distinctive keywords from the skill's needles in
# _infer_skills_for_order, so a correct router picks the targeted skill.
PROMPTS: dict[str, tuple[str, str]] = {
    # ── Defaults (already present in legacy meeting room) ──
    "Architect Agent": ("Architect Workflow Skill", "Run the architect blueprint and advance to founder approval."),
    "Math Agent": ("Math Skill", "Solve this probability equation for the training pipeline."),
    "Code Agent": ("Coding Skill", "Refactor the route handler and wire the new API function."),
    "UI Agent": ("UI Skill", "Polish the meeting-room card layout and translucent header."),
    "Verifier Agent": ("Verification Skill", "Verify the smoke test compiles and produces a screenshot."),
    "Memory Agent": ("Memory Skill", "Write a long term memory handoff receipt for this session."),
    "File Structure Agent": ("File Structure Skill", "Organize the archive folder and cleanup stray project files."),
    "Research Agent": ("Research Skill", "Research and compare options to diagnose the slow build."),

    # ── Finance & Markets ──
    "Financial Strategist Agent": ("Financial Strategy Skill", "Model Q3 budget, runway, burn rate, and LTV against CAC."),
    "Stocks Historian Agent": ("Stocks History Skill", "Pull AAPL ticker OHLCV history, dividend stream, and any stock split."),
    "Market Impact Analyst Agent": ("Market Impact Skill", "Run an event study on the last Fed announcement market reaction."),
    "Macro Economist Agent": ("Macro Economics Skill", "Classify the current macro regime against CPI and GDP and fed policy."),
    "Crypto Analyst Agent": ("Crypto Analysis Skill", "Compare BTC halving cycles and current on-chain DeFi flow."),
    "Portfolio Strategist Agent": ("Portfolio Strategy Skill", "Plan a portfolio rebalance with diversification across asset allocation buckets."),
    "Quant Modeler Agent": ("Quant Modeling Skill", "Run a walk-forward backtest with Monte Carlo and report Sharpe ratio."),
    "News Event Correlator Agent": ("News Correlation Skill", "Build a news correlation timeline tied to the last earnings call."),
    "Sentiment Analysis Agent": ("Sentiment Analysis Skill", "Track sentiment and tone shift in the latest narrative around the brand."),

    # ── Web & Design ──
    "Web App Designer Agent": ("Web App Design Skill", "Sketch the web app design with wireframe, user flow, and information architecture."),
    "Design System Architect Agent": ("Design System Skill", "Audit the design system, design tokens, and component library variants."),
    "Accessibility Auditor Agent": ("Accessibility Audit Skill", "Run an accessibility audit against WCAG and screen reader behavior."),
    "UX Research Lead Agent": ("UX Research Skill", "Plan UX research with a usability test, user interview, and persona synthesis."),
    "Mobile Web Designer Agent": ("Mobile Web Skill", "Redesign for mobile web with responsive layout, PWA support, and touch target hygiene."),

    # ── Graph & Data Viz ──
    "Graph Visualization Designer Agent": ("Graph Visualization Skill", "Build a force-directed node-link graph viz with a sankey and dependency graph view."),
    "Data Viz Storyteller Agent": ("Data Viz Storytelling Skill", "Produce an explanatory chart for the editorial chart series and improve the data viz framing."),
    "Chart Engineer Agent": ("Chart Engineering Skill", "Pick between Recharts, D3.js, Plotly, and ECharts as the chart library."),
    "Dashboard Architect Agent": ("Dashboard Architecture Skill", "Design the dashboard with KPI tiles and Grafana operational panels."),

    # ── Deep Research ──
    "Deep Research Agent": ("Deep Research Skill", "Do deep research and synthesize a multi-source cited research summary."),
    "Literature Review Agent": ("Literature Review Skill", "Write a literature review with an academic paper survey of the field."),
    "Competitive Intelligence Agent": ("Competitive Intelligence Skill", "Map the competitive landscape with a market scan of every competitor."),
    "Historical Context Agent": ("Historical Context Skill", "Give long view historical context on the history of this trade route."),

    # ── Approved-Library reference (28) ──
    "AI Safety Reference Agent": ("AI Safety Reference Skill", "Apply NIST AI RMF and OWASP Agentic threat catalog for AI safety review."),
    "Algorithms DS Reference Agent": ("Algorithms DS Reference Skill", "Pick an algorithm and data structure for sliding-window max with complexity bound from CP-Algorithm."),
    "Android Worker Reference Agent": ("Android Worker Reference Skill", "Use Android architecture, WorkManager background, and Android permission docs for the worker."),
    "Architecture Reference Agent": ("Architecture Reference Skill", "Design system architecture using event log, local first, plugin system, and verifier system patterns."),
    "Patch Planning Agent": ("Patch Planning Skill", "Plan the patch plan and split this PR review into a small pull request and code review."),
    "Language Reference Agent": ("Language Reference Skill", "Settle the bash syntax, c language, css reference, and commonmark question."),
    "Polyglot Coding Agent": ("Polyglot Coding Skill", "Resolve language choice between csharp and bash for this glue, plus a data format pick."),
    "Download Failure Triage Agent": ("Download Failure Triage Skill", "Triage the last download failure logs from the library intake failure batch."),
    "Library Receipts Auditor Agent": ("Library Receipts Audit Skill", "Audit library receipt provenance and verify the intake receipt hash."),
    "Offline Seed LLM Agent": ("Offline Seed LLM Skill", "Validate the offline seed loop with llama-cpp-python and the Qwen seed LLM contract."),
    "Code Companion Agent": ("Code Companion Skill", "Use the code companion contract with ast module, difflib, and inspect module for the refactor."),
    "Engel Manuals Agent": ("Engel Manuals Skill", "Look up the engel manual command map and continuity map for this dispatch."),
    "Engel Receipts Agent": ("Engel Receipts Skill", "Reconcile the engel report against the engel plan and the latest engel receipt."),
    "LLM Reference Agent": ("LLM Reference Skill", "Check GGUF quantization compatibility and llama.cpp build flags."),
    "Math Reference Agent": ("Math Reference Skill", "Walk the calculus reference and the discrete math reference for this derivation."),
    "Logic Reasoning Reference Agent": ("Logic Reasoning Reference Skill", "Use linear algebra, introductory statistics, and a proof technique for this argument."),
    "Memory Systems Reference Agent": ("Memory Systems Reference Skill", "Apply MemGPT and event sourcing to the agent memory architecture."),
    "Offline Docs Agent": ("Offline Docs Skill", "Walk the offline doc folders for the cross-tool packaging question."),
    "PyInstaller Packaging Agent": ("PyInstaller Packaging Skill", "Fix the PyInstaller spec file and the frozen build hidden imports."),
    "PySide6 Qt Agent": ("PySide6 Qt Skill", "Debug the PySide6 QWidget and signal slot connection."),
    "Python Reference Agent": ("Python Reference Skill", "Walk the Python standard library and the Python tutorial section."),
    "Research Papers Agent": ("Research Papers Skill", "Find the canonical research paper and the arxiv paper on this topic."),
    "RAG Retrieval Agent": ("RAG Retrieval Skill", "Design the RAG retrieval pipeline with a vector store and an embedding index."),
    "Prompt Injection Defense Agent": ("Prompt Injection Defense Skill", "Apply OWASP LLM defenses for prompt injection and llm security hardening."),
    "SQLite Reference Agent": ("SQLite Reference Skill", "Configure SQLite WAL mode for this Engel local store."),
    "Static Analysis Agent": ("Static Analysis Skill", "Run mypy and Ruff plus Pylint for the static analysis sweep."),
    "Pytest Testing Agent": ("Pytest Testing Skill", "Write the pytest fixture and parametrize the suite across all inputs."),
    "WSL Ubuntu Runtime Agent": ("WSL Ubuntu Runtime Skill", "Configure the WSL Ubuntu server runtime and the /mnt/ filesystem perf workaround."),

    # ── Previously-manual-only agents, now auto-selectable via unique skills ──
    "Engel Core": ("Engel Orchestration Skill", "Engel orchestrate the room and coordinate the team for this dispatch."),
    "Safety Agent": ("Safety Review Skill", "Run a safety review and guardian check before this action ships."),
    "Skill Builder Agent": ("Skill Building Skill", "Build a new skill candidate and scaffold it into the meeting-room roster."),
    "Custom Agent": ("Custom Skill", "Spin up a custom skill bespoke role for this ad-hoc agent."),

    # ── Per-phone Android worker routing targets ──
    "Android Phone Alpha Agent": ("Android Worker Alpha Skill", "Run this on worker alpha (moto g power) via adb usb queue."),
    "Android Phone Beta Agent": ("Android Worker Beta Skill", "Run this on worker beta (moto g fast) via adb usb queue."),
}

# After the routing-coverage extension, every registered agent has a unique
# auto-routable skill. NOT_AUTO_SELECTABLE is intentionally empty.
NOT_AUTO_SELECTABLE: set[str] = set()


def _reset_room_state() -> Path:
    """Back up the current room_state.json and start with a clean slate."""
    state_path = mr.ROOM_STATE_FILE
    backup = state_path.with_suffix(".json.test_backup")
    if state_path.exists():
        shutil.copy2(state_path, backup)
        state_path.unlink()
    return backup


def _restore_room_state(backup: Path) -> None:
    if backup.exists():
        shutil.copy2(backup, mr.ROOM_STATE_FILE)
        backup.unlink()


def _submit_and_inspect(prompt: str) -> dict:
    """Fresh state per case so we observe the new station the router creates."""
    if mr.ROOM_STATE_FILE.exists():
        mr.ROOM_STATE_FILE.unlink()
    return mr.submit_order_from_engel_main_ui(prompt, source="meeting_room_routing_test")


def _expected_label(agent: str, skill: str) -> str:
    return f"{agent} / {skill}"


def _pass_1_local_routing(report: list[dict]) -> tuple[int, int]:
    print("\n====== PASS 1 — Local agent auto-selection ======")
    ok, fail = 0, 0
    for agent, (skill, prompt) in PROMPTS.items():
        result = _submit_and_inspect(prompt)
        labels = result.get("station_labels", []) or []
        expected = _expected_label(agent, skill)
        passed = expected in labels
        if passed:
            ok += 1
            mark = "PASS"
        else:
            fail += 1
            mark = "FAIL"
        report.append({
            "pass": 1,
            "agent": agent,
            "expected_skill": skill,
            "prompt": prompt,
            "station_labels": labels,
            "result": mark,
        })
        print(f"  {mark}  {agent:<42} skill={skill}")
        if not passed:
            print(f"         expected:  {expected}")
            print(f"         actual:    {labels}")
    return ok, fail


def _pass_2_android_dispatch(report: list[dict], staged_packets: list[Path]) -> tuple[int, int]:
    print("\n====== PASS 2 — Android-worker dispatch coercion (ALL agents) ======")
    print("  Each prompt has Android-worker keywords appended; the router")
    print("  auto-creates an Android worker station alongside the")
    print("  agent-specific station; per-phone prompts keep their exact")
    print("  Alpha/Beta worker skill instead of the generic worker skill.")
    print("  complete_order calls dispatch_station_work")
    print("  which stages a job packet under remote_workers/android_worker_alpha/.")
    print("  No ADB binary is invoked here — packets are filesystem-only and")
    print("  cleaned up at end of test.")
    ok, fail = 0, 0
    for agent, (skill, base_prompt) in PROMPTS.items():
        # Mark Pass-2 prompts so the cleanup pass can identify and remove the
        # staged-assignment artifacts they produce in approved/.
        prompt = f"pass2-routing-noise: {base_prompt} (run on android worker via adb worker queue)"
        result = _submit_and_inspect(prompt)
        labels = result.get("station_labels", []) or []
        order_id = result.get("order_id")
        android_label_present = any("Android Worker" in lbl for lbl in labels)

        dispatch_summary = None
        if order_id and android_label_present:
            complete = mr.complete_order_from_engel_main_ui(
                order_id,
                main_reply="(test) main-ui routed answer",
                source="meeting_room_routing_test",
            )
            dispatch_summary = complete.get("summary", "")
            # Track the packet that just got staged for cleanup.
            _track_recent_packets(staged_packets)

        dispatch_engaged = bool(
            dispatch_summary and (
                "Android" in dispatch_summary
                or "Needs Review" in dispatch_summary
                or "Assigned" in dispatch_summary
            )
        )

        passed = android_label_present and dispatch_engaged
        if passed:
            ok += 1
            mark = "PASS"
        else:
            fail += 1
            mark = "FAIL"
        report.append({
            "pass": 2,
            "agent": agent,
            "android_label_present": android_label_present,
            "dispatch_summary": dispatch_summary,
            "station_labels": labels,
            "result": mark,
        })
        print(f"  {mark}  {agent:<42} android_route={android_label_present}")
    return ok, fail


def _pass_3_real_device(report: list[dict]) -> tuple[int, int]:
    """If an ADB-USB phone is physically attached, surface it.

    This pass does not push or pull data — it only confirms the device
    enumeration path works without invoking C:-installed adb.
    """
    print("\n====== PASS 3 — Real Android device presence (read-only) ======")
    try:
        from engel_adb_worker_manager import _ADB, _connected_serials, _DEVICE_LABELS
    except Exception as exc:
        print(f"  SKIP   adb worker manager import failed: {exc}")
        return 0, 0

    adb_anchor = str(_ADB).lower()
    is_c_drive = adb_anchor.startswith("c:")
    print(f"  ADB binary resolved to: {_ADB}")
    if is_c_drive:
        print("  SKIP   adb resolved to C: — refusing per project memory ([[feedback-no-c-drive]])")
        report.append({"pass": 3, "result": "SKIP", "reason": "adb on C:"})
        return 0, 0
    if not Path(_ADB).is_file():
        print("  SKIP   adb binary not present on D: — install under tools/platform-tools/ to enable")
        report.append({"pass": 3, "result": "SKIP", "reason": "adb missing on D:"})
        return 0, 0
    try:
        serials = _connected_serials()
    except Exception as exc:
        print(f"  SKIP   adb devices call failed: {exc}")
        report.append({"pass": 3, "result": "SKIP", "reason": f"adb devices failed: {exc}"})
        return 0, 0
    if not serials:
        print("  SKIP   no Android worker phone connected over USB right now")
        print("         (Plug in a known phone and re-run to exercise the real device path.)")
        report.append({"pass": 3, "result": "SKIP", "reason": "no phones attached"})
        return 0, 0
    for serial in serials:
        label = _DEVICE_LABELS.get(serial, "(unknown device)")
        print(f"  PASS   device {serial} present: {label}")
        report.append({"pass": 3, "result": "PASS", "serial": serial, "label": label})
    return len(serials), 0


def _pass_4_real_adb_push(report: list[dict]) -> tuple[int, int, list[str]]:
    """End-to-end push: for each connected phone, submit an order through
    Engel's official intake whose prompt deterministically routes to that
    phone's per-phone skill (Android Worker Alpha/Beta Skill), then push
    via real ADB and verify the packet landed on the device. Packet stays
    on the phone so the user can SEE it in the Engel Remote Worker app."""
    print("\n====== PASS 4 — Real ADB push to phones ======")
    print("  Submits a clearly-labeled test order via submit_order_from_engel_main_ui")
    print("  whose prompt matches the per-phone Android Worker Alpha/Beta Skill;")
    print("  the auto-router creates a station with type=Android Phone <X> Agent")
    print("  whose name contains the phone tag so _android_worker_id_for routes")
    print("  to the matching worker_id; render_adb_workers_push_jobs() then")
    print("  pushes via real ADB. Packet stays visible on the phone for the user.")

    try:
        from engel_adb_worker_manager import (
            _ADB, _connected_serials, _DEVICE_WORKERS, _DEVICE_LABELS,
            _list_remote_dir, _SDCARD_ROOT,
            render_adb_workers_push_jobs,
            render_adb_provision_worker,
        )
    except Exception as exc:
        print(f"  SKIP   adb worker manager import failed: {exc}")
        report.append({"pass": 4, "result": "SKIP", "reason": str(exc)})
        return 0, 0, []

    if str(_ADB).lower().startswith("c:"):
        print("  SKIP   adb resolved to C: — refusing per project memory")
        return 0, 0, []
    if not Path(_ADB).is_file():
        print("  SKIP   adb binary not present on D:")
        return 0, 0, []
    serials = _connected_serials()
    if not serials:
        print("  SKIP   no phone connected over USB right now")
        return 0, 0, []

    print(f"\n  Connected devices: {len(serials)}")
    for s in serials:
        print(f"    {s}  ->  {_DEVICE_LABELS.get(s, '(unknown)')}  workers={_DEVICE_WORKERS.get(s, [])}")

    # ── 0. Auto-provision any unprovisioned workers (idempotent — skips
    #      already-provisioned). This is the documented next-step before
    #      first push per render_adb_provision_worker.__doc__.
    print("\n  Provisioning workers on connected phones (idempotent)...")
    unprovisioned_phones: list[str] = []
    for serial in serials:
        for worker_id in _DEVICE_WORKERS.get(serial, []):
            existing = _list_remote_dir(serial, _SDCARD_ROOT)
            if worker_id not in existing:
                unprovisioned_phones.append(f"{_DEVICE_LABELS.get(serial, serial)} ({worker_id})")
    if unprovisioned_phones:
        print(f"  Needs provisioning: {unprovisioned_phones}")
        prov_output = render_adb_provision_worker("")
        # Print abbreviated provision output
        for line in prov_output.splitlines()[:30]:
            print(f"  {line}")
    else:
        print("  All phones already provisioned.")

    test_label = "MeetingRoomTest"
    # Map worker_id -> the per-phone skill keyword that auto-routes there.
    skill_phrase_for_worker = {
        "android_worker_alpha": "worker alpha moto g power",
        "android_worker_beta":  "worker beta moto g fast",
    }

    # ── 1. Stage one packet per connected phone via Engel's intake.
    for serial in serials:
        for worker_id in _DEVICE_WORKERS.get(serial, []):
            phrase = skill_phrase_for_worker.get(worker_id)
            if not phrase:
                print(f"  SKIP   {worker_id} — no per-phone skill phrase mapped")
                continue
            label = _DEVICE_LABELS.get(serial, serial)
            prompt = f"{test_label} — run on {phrase} via adb usb queue (targeted phone: {label})"

            # Fresh state per stage so we observe the new station the router
            # creates and don't reuse an alpha station from the prior loop.
            if mr.ROOM_STATE_FILE.exists():
                mr.ROOM_STATE_FILE.unlink()
            submit = mr.submit_order_from_engel_main_ui(prompt, source="meeting_room_routing_test_pass4")
            order_id = submit.get("order_id")
            station_labels = submit.get("station_labels", [])
            print(f"  STAGE   {worker_id}: station_labels={station_labels}")
            if not order_id:
                print(f"  FAIL   intake refused for {worker_id}: {submit}")
                report.append({"pass": 4, "result": "FAIL", "worker": worker_id, "reason": "intake refused"})
                continue

            complete = mr.complete_order_from_engel_main_ui(
                order_id, main_reply="(test) main-ui routed answer", source="meeting_room_routing_test_pass4"
            )
            pc_jobs = mr.ENGEL_APP_ROOT / "remote_workers" / worker_id / "jobs"
            if pc_jobs.exists():
                latest = max(pc_jobs.glob("*.json"), key=lambda p: p.stat().st_mtime, default=None)
                if latest:
                    print(f"          staged at: {latest.relative_to(mr.ENGEL_APP_ROOT)}")
                else:
                    print(f"          no packet found under {pc_jobs}")
            else:
                print(f"          jobs dir not created: {pc_jobs}")

    # ── 2. Push via Engel's real ADB-push code path
    print("\n  Pushing staged packets via render_adb_workers_push_jobs()...")
    push_output = render_adb_workers_push_jobs()
    for line in push_output.splitlines()[:60]:
        print(f"  {line}")
    print("  ...")

    # ── 3. Verify each phone's remote queue has the test packet
    ok, fail = 0, 0
    pushed_remotes: list[str] = []
    for serial in serials:
        for worker_id in _DEVICE_WORKERS.get(serial, []):
            remote_base = f"{_SDCARD_ROOT}/{worker_id}/jobs"
            remote_files = _list_remote_dir(serial, remote_base)
            label = _DEVICE_LABELS.get(serial, serial)
            test_present = [f for f in remote_files if "meetingroomtest" in f.lower()]
            if test_present:
                ok += 1
                for f in test_present:
                    pushed_remotes.append(f"{label}: {remote_base}/{f}")
                print(f"  PASS    {label} ({worker_id}) -> test packet(s) on device: {test_present}")
                report.append({"pass": 4, "result": "PASS", "serial": serial, "worker": worker_id,
                               "remote_files": test_present})
            else:
                fail += 1
                # Determine if the failure is provisioning-related so the user
                # gets actionable guidance rather than a bare FAIL.
                provisioned = bool(remote_files) or any(
                    rf.lower().startswith("android_worker_") for rf in remote_files
                )
                reason = ("phone not provisioned — run 'engel adb provision worker' on this device first"
                          if not provisioned else "push happened but no MeetingRoomTest packet found")
                print(f"  FAIL    {label} ({worker_id}) -> {reason}")
                print(f"          remote listing: {remote_files}")
                report.append({"pass": 4, "result": "FAIL", "serial": serial, "worker": worker_id,
                               "remote_files": remote_files, "reason": reason})

    return ok, fail, pushed_remotes


def _pass_5_lan_flow(report: list[dict]) -> tuple[int, int, dict]:
    """The end-to-end LAN flow the new minimal worker app actually uses:

      1. Submit ONE order per phone through Engel intake -> per-phone skill
         routes to Android Phone Alpha/Beta Agent -> dispatch stages a
         validated assignment in remote_workers/communication_queen_assignments/approved/
         (the directory the LAN server reads).
      2. Push worker_identity.json to each phone at the app-scoped path the
         Engel Remote Worker app actually reads.
      3. Clean up old wrong-path /sdcard test packets (so the user isn't
         confused by stale junk in the old transport's directory).
      4. Generate a pairing code and start the LAN HTTP server in the
         background, bound to 0.0.0.0:8765, --allow-lan.
      5. Print PC LAN IP + port + pairing code + step-by-step phone
         instructions so the user can pair and tap Check Now.
    """
    print("\n====== PASS 5 — End-to-end LAN flow (the app's real protocol) ======")
    out: dict = {"assignments_staged": [], "identities_pushed": [], "lan_server": None,
                 "pairing_code": None, "pc_lan_ip": None}

    try:
        from engel_adb_worker_manager import (
            _ADB, _connected_serials, _DEVICE_WORKERS, _DEVICE_LABELS,
        )
        import engel_remote_worker_lan_pairing as lan_mod
    except Exception as exc:
        print(f"  SKIP   import failed: {exc}")
        return 0, 0, out

    serials = _connected_serials() if Path(_ADB).is_file() and not str(_ADB).lower().startswith("c:") else []
    if not serials:
        print("  SKIP   no phones connected (or adb resolved to C: / missing)")
        return 0, 0, out

    # ── 1. Submit via Engel intake -> Meeting Room -> per-phone station -> stage in approved/
    print("\n  [1/5] Submitting per-phone orders through Engel intake...")
    ok, fail = 0, 0
    skill_phrase_for_worker = {
        "android_worker_alpha": "worker alpha (moto g power)",
        "android_worker_beta":  "worker beta (moto g fast)",
    }
    for serial in serials:
        for worker_id in _DEVICE_WORKERS.get(serial, []):
            phrase = skill_phrase_for_worker.get(worker_id)
            if not phrase:
                continue
            label = _DEVICE_LABELS.get(serial, serial)
            prompt = (
                f"MeetingRoomTest LAN flow — Hello from Engel to {phrase}. "
                f"Please summarize this short message and return draft notes only."
            )
            if mr.ROOM_STATE_FILE.exists():
                mr.ROOM_STATE_FILE.unlink()
            submit = mr.submit_order_from_engel_main_ui(prompt, source="meeting_room_routing_test_pass5")
            order_id = submit.get("order_id")
            station_labels = submit.get("station_labels", [])
            if not order_id:
                print(f"    FAIL   intake refused for {worker_id}: {submit}")
                fail += 1
                continue
            complete = mr.complete_order_from_engel_main_ui(
                order_id, main_reply="(test) main-ui routed answer", source="meeting_room_routing_test_pass5"
            )
            summary = complete.get("summary", "")
            # Confirm an assignment file landed in approved/
            approved_dir = mr.ENGEL_APP_ROOT / "remote_workers" / "communication_queen_assignments" / "approved"
            recent = sorted(approved_dir.glob(f"*{worker_id}*meetingroomtest*"), key=lambda p: p.stat().st_mtime)
            if recent:
                ok += 1
                out["assignments_staged"].append({"worker": worker_id, "path": str(recent[-1])})
                print(f"    PASS   {label} ({worker_id}) -> staged {recent[-1].name}")
                report.append({"pass": 5, "step": "stage", "worker": worker_id, "path": str(recent[-1]), "result": "PASS"})
            else:
                fail += 1
                print(f"    FAIL   {label} ({worker_id}) -> no assignment in approved/")
                print(f"           submit_labels={station_labels}  complete_summary={summary}")
                report.append({"pass": 5, "step": "stage", "worker": worker_id, "result": "FAIL"})

    # ── 2. Push worker_identity.json to each phone at the app-scoped path
    print("\n  [2/5] Pushing worker_identity.json to each phone (app-scoped storage)...")
    APP_SCOPED_DIR = "/storage/emulated/0/Android/data/com.example.engel_remote_worker/files"
    import subprocess
    for serial in serials:
        for worker_id in _DEVICE_WORKERS.get(serial, []):
            identity = {
                "worker_id": worker_id,
                "worker_name": _DEVICE_LABELS.get(serial, worker_id),
                "phone_model": _DEVICE_LABELS.get(serial, "unknown"),
            }
            tmp_path = mr.ENGEL_APP_ROOT / "runtime" / "meeting_room" / f"{worker_id}_identity.json"
            tmp_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path.write_text(json.dumps(identity, indent=2), encoding="utf-8")

            mkdir = subprocess.run(
                [str(_ADB), "-s", serial, "shell", f"mkdir -p {APP_SCOPED_DIR}"],
                capture_output=True, text=True, timeout=10,
            )
            push = subprocess.run(
                [str(_ADB), "-s", serial, "push", str(tmp_path), f"{APP_SCOPED_DIR}/worker_identity.json"],
                capture_output=True, text=True, timeout=20,
            )
            if push.returncode == 0 and "pushed" in (push.stdout + push.stderr).lower():
                ok += 1
                out["identities_pushed"].append({"serial": serial, "worker": worker_id})
                print(f"    PASS   {_DEVICE_LABELS.get(serial, serial)} <- identity={worker_id}")
                report.append({"pass": 5, "step": "identity_push", "worker": worker_id, "result": "PASS"})
            else:
                fail += 1
                print(f"    FAIL   {_DEVICE_LABELS.get(serial, serial)} <- identity push: rc={push.returncode}")
                print(f"           stdout={push.stdout[:140]!r}  stderr={push.stderr[:140]!r}")
                report.append({"pass": 5, "step": "identity_push", "worker": worker_id, "result": "FAIL",
                               "stderr": push.stderr[:200]})

    # ── 2b. Force-stop the worker app on each phone so the next launch
    #       re-runs WorkerIdentity.load() and picks up the freshly-pushed
    #       worker_identity.json. Without this, an already-running app keeps
    #       its cached identity (defaults to alpha) and the LAN server
    #       refuses to serve work targeted at the other worker.
    print("\n  [2b/5] Force-stopping worker app so new identity takes effect...")
    for serial in serials:
        stop = subprocess.run(
            [str(_ADB), "-s", serial, "shell", "am", "force-stop", "com.example.engel_remote_worker"],
            capture_output=True, text=True, timeout=10,
        )
        label = _DEVICE_LABELS.get(serial, serial)
        if stop.returncode == 0:
            print(f"    OK     {label} — app force-stopped (re-open after pairing to load new identity)")
        else:
            print(f"    WARN   {label} — force-stop returned rc={stop.returncode}: {stop.stderr.strip()[:120]}")

    # ── 3. Clean up old wrong-path /sdcard test packets so user isn't confused
    print("\n  [3/5] Cleaning old wrong-path test packets from /sdcard...")
    for serial in serials:
        for worker_id in _DEVICE_WORKERS.get(serial, []):
            rm = subprocess.run(
                [str(_ADB), "-s", serial, "shell",
                 f"rm -f /sdcard/EngelRemoteWorker/{worker_id}/jobs/*meetingroomtest* 2>/dev/null; "
                 f"rm -f /sdcard/EngelRemoteWorker/{worker_id}/inbox/assigned_inputs/*meetingroomtest* 2>/dev/null; "
                 f"echo cleaned"],
                capture_output=True, text=True, timeout=10,
            )
            print(f"    {_DEVICE_LABELS.get(serial, serial)} ({worker_id}): {rm.stdout.strip() or '(nothing to clean)'}")

    # ── 4. Generate pairing code + start the LAN server in background
    print("\n  [4/5] Generating pairing code and starting LAN server...")
    session = lan_mod.create_pairing_session()
    out["pairing_code"] = session.pairing_code

    # Get PC's LAN IP (the one phones can reach over WiFi)
    import socket
    pc_ip = "127.0.0.1"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # doesn't actually send, just resolves a route
        pc_ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass
    out["pc_lan_ip"] = pc_ip

    # Check if server already running on port 8765 — if so don't try to bind again
    server_port = 8765
    already_running = False
    try:
        with socket.create_connection((pc_ip, server_port), timeout=1):
            already_running = True
    except OSError:
        already_running = False

    if already_running:
        print(f"    LAN server already listening on {pc_ip}:{server_port} — reusing")
        out["lan_server"] = "already_running"
        report.append({"pass": 5, "step": "lan_server", "result": "ALREADY_RUNNING"})
    else:
        # Start the server as a background subprocess
        log_path = mr.REPORTS_DIR / "lan_pairing_server.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_f = open(log_path, "a", encoding="utf-8")
        proc = subprocess.Popen(
            [sys.executable, str(mr.ENGEL_APP_ROOT / "engel_remote_worker_lan_pairing.py"),
             "serve", "--host", "0.0.0.0", "--port", str(server_port), "--allow-lan"],
            cwd=str(mr.ENGEL_APP_ROOT),
            stdout=log_f, stderr=log_f,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
        # Wait briefly for it to bind
        import time
        for _ in range(20):
            time.sleep(0.25)
            try:
                with socket.create_connection((pc_ip, server_port), timeout=0.5):
                    break
            except OSError:
                continue
        try:
            with socket.create_connection((pc_ip, server_port), timeout=1):
                out["lan_server"] = f"bound on 0.0.0.0:{server_port}"
                out["lan_server_pid"] = proc.pid
                ok += 1
                print(f"    PASS   LAN server bound on 0.0.0.0:{server_port}  pid={proc.pid}  log={log_path}")
                report.append({"pass": 5, "step": "lan_server", "result": "PASS", "pid": proc.pid})
        except OSError:
            fail += 1
            print(f"    FAIL   LAN server did not bind in time. Check {log_path}")
            report.append({"pass": 5, "step": "lan_server", "result": "FAIL", "log": str(log_path)})

    # ── 5. Print pairing instructions for the user
    print("\n" + "=" * 70)
    print("  HOW TO SEE THE JOB ON EACH PHONE — pair the Engel Remote Worker app:")
    print("=" * 70)
    print(f"    PC LAN address: {pc_ip}")
    print(f"    Port:           {server_port}")
    print(f"    Pairing code:   {session.pairing_code}   (valid {lan_mod.TOKEN_TTL_SECONDS // 60} min)")
    print()
    print("  On EACH phone (both should now be plugged in or on the same WiFi):")
    print("    1. Open the Engel Remote Worker app.")
    print(f"    2. PC host = {pc_ip}, port = {server_port}, code = {session.pairing_code}")
    print("    3. Tap Pair, then tap Check Now.")
    print("    4. The app transcript will show the assignment titled:")
    print("         'MeetingRoomTest LAN flow — Hello from Engel to ...'")
    print()
    server_pid = out.get("lan_server_pid")
    if server_pid:
        print(f"  To stop the LAN server later:  taskkill /PID {server_pid} /F")
    else:
        print(f"  LAN server status: {out.get('lan_server', '(unknown)')}")
    print("=" * 70)

    return ok, fail, out


def _track_recent_packets(staged_packets: list[Path]) -> None:
    """Append the most-recently staged job packets to a cleanup list."""
    workers_root = mr.ENGEL_APP_ROOT / "remote_workers" / "android_worker_alpha"
    jobs_dir = workers_root / "jobs"
    inbox_dir = workers_root / "inbox" / "assigned_inputs"
    if jobs_dir.exists():
        for job_file in jobs_dir.glob("*.json"):
            if job_file not in staged_packets:
                staged_packets.append(job_file)
    if inbox_dir.exists():
        for instr in inbox_dir.glob("*/instructions.txt"):
            if instr not in staged_packets:
                staged_packets.append(instr)


def _cleanup_packets(staged_packets: list[Path]) -> None:
    """Remove every job packet the test staged. Leaves Pass-5 (real LAN-flow)
    assignments alone — those are the ones the user wants to SEE on the
    phones. Only removes Pass-2 'pass2-routing-noise' artifacts and any
    legacy /sdcard-protocol packets from older runs."""
    removed = 0

    # 1. Legacy: any remaining manual-transfer packets tracked during the run.
    for path in staged_packets:
        try:
            if path.is_file():
                path.unlink()
                removed += 1
        except Exception:
            pass
    # Remove now-empty assigned_inputs/<job_id>/ subdirs we created.
    workers_root = mr.ENGEL_APP_ROOT / "remote_workers" / "android_worker_alpha"
    inbox_dir = workers_root / "inbox" / "assigned_inputs"
    if inbox_dir.exists():
        for sub in list(inbox_dir.iterdir()):
            try:
                if sub.is_dir() and not any(sub.iterdir()):
                    sub.rmdir()
            except Exception:
                pass

    # 2. Pass-2 noise: assignments in approved/ that came from the
    #    routing-coverage prompts (tagged 'pass2-routing-noise').
    approved_dir = mr.ENGEL_APP_ROOT / "remote_workers" / "communication_queen_assignments" / "approved"
    if approved_dir.exists():
        for path in approved_dir.glob("*pass2_routing_noise*"):
            try:
                path.unlink()
                removed += 1
            except Exception:
                pass
        # The slugify lowercases and may replace hyphens with underscores —
        # also match the underscore-only variant just in case.
        for path in approved_dir.glob("*pass2-routing-noise*"):
            try:
                path.unlink()
                removed += 1
            except Exception:
                pass

    print(f"\n  Cleanup: removed {removed} test-noise file(s); Pass-5 assignments kept on disk")


def _summary(p1, p2, p3, p5, report, lan_info) -> int:
    print("\n====== SUMMARY ======")
    p1_ok, p1_fail = p1
    p2_ok, p2_fail = p2
    p3_ok, p3_fail = p3
    p5_ok, p5_fail = p5
    total = p1_ok + p1_fail + p2_ok + p2_fail + p3_ok + p3_fail + p5_ok + p5_fail
    print(f"  Pass 1 (local routing):                 {p1_ok} pass / {p1_fail} fail / {p1_ok+p1_fail} total")
    print(f"  Pass 2 (android dispatch coercion):     {p2_ok} pass / {p2_fail} fail / {p2_ok+p2_fail} total")
    print(f"  Pass 3 (real device presence):          {p3_ok} pass / {p3_fail} fail / {p3_ok+p3_fail} total")
    print(f"  Pass 5 (end-to-end LAN flow):           {p5_ok} pass / {p5_fail} fail / {p5_ok+p5_fail} total")
    overall_ok = p1_ok+p2_ok+p3_ok+p5_ok
    overall_fail = p1_fail+p2_fail+p3_fail+p5_fail
    print(f"  Overall:                                {overall_ok} pass / {overall_fail} fail / {total} total")
    print(f"  Not auto-selectable: {sorted(NOT_AUTO_SELECTABLE) or '(none — every agent has a unique skill)'}")

    report_dir = mr.REPORTS_DIR
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "meeting_room_agent_routing_test.json"
    report_path.write_text(json.dumps({
        "pass_1_local": {"ok": p1_ok, "fail": p1_fail},
        "pass_2_android": {"ok": p2_ok, "fail": p2_fail},
        "pass_3_real_device": {"ok": p3_ok, "fail": p3_fail},
        "pass_5_lan_flow": {"ok": p5_ok, "fail": p5_fail, **(lan_info or {})},
        "not_auto_selectable": sorted(NOT_AUTO_SELECTABLE),
        "cases": report,
    }, indent=2), encoding="utf-8")
    print(f"\n  Report written to: {report_path}")
    return 0 if overall_fail == 0 else 1


def main() -> int:
    print("Meeting Room — Agent auto-routing test")
    print("  Engel-orchestrator simulation via submit_order_from_engel_main_ui()")
    print(f"  Total agents registered: {len(mr.AGENT_TYPES)}")
    print(f"  Total skills registered: {len(mr.SKILL_TYPES)}")
    print(f"  Test prompts:            {len(PROMPTS)}")

    backup = _reset_room_state()
    staged_packets: list[Path] = []
    try:
        report: list[dict] = []
        p1 = _pass_1_local_routing(report)
        p2 = _pass_2_android_dispatch(report, staged_packets)
        p3 = _pass_3_real_device(report)
        p5_ok, p5_fail, lan_info = _pass_5_lan_flow(report)
        return _summary(p1, p2, p3, (p5_ok, p5_fail), report, lan_info)
    finally:
        # Clean up Pass-2 simulation packets only (Pass-5 stages real
        # assignments in approved/ that should persist for the user).
        _cleanup_packets(staged_packets)
        _restore_room_state(backup)


if __name__ == "__main__":
    sys.exit(main())
