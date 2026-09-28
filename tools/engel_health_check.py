#!/usr/bin/env python3
"""Engel AI Main - health check / self-state mirror.

One command that tells the operator (and Engel itself, right after a context
handoff) exactly what state the build is in. It answers, in plain language:

  - current version    release manifest identity + built-artifact timestamps
  - last GREEN verify  when the full release verifier last passed (durable)
  - build integrity    deployed Release files vs the pinned manifest hashes
  - dirty files        rebuild pending / pinned-hash drift / recent edits
  - recent failures    ok:false receipts under reports\\ in the last N days
  - active tools       EngelAIMain process + Meeting Room server health
  - next safe action   one concrete instruction for what to do now

Design rules (handoff reliability):
  - Read-only EXCEPT for its own receipts under reports\\health_checks\\.
  - Every run leaves a plain receipt (JSON + Markdown) so nothing has to be
    guessed after a compaction. The newest is always at a STABLE path:
        reports\\health_checks\\ENGEL_HEALTH_LATEST.json
        reports\\health_checks\\ENGEL_HEALTH_LATEST.md
  - Engel-owned state stays on D:/F: (never C:). Credentials are never read
    or printed.

Usage:
  python tools\\engel_health_check.py             fast local mirror (no network)
  python tools\\engel_health_check.py --full       also run the full release verifier
  python tools\\engel_health_check.py --json       print machine JSON only
  python tools\\engel_health_check.py --failures-days 7
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "dist" / "ENGEL_CURRENT_RELEASE_MANIFEST_20260607.json"
VERIFIER = ROOT / "tools" / "verify_engel_current_release_manifest.py"
OUT_DIR = ROOT / "reports" / "health_checks"
LATEST_JSON = OUT_DIR / "ENGEL_HEALTH_LATEST.json"
LATEST_MD = OUT_DIR / "ENGEL_HEALTH_LATEST.md"
LAST_GREEN = OUT_DIR / "ENGEL_HEALTH_LAST_GREEN.json"
MEETING_ROOM_HEALTH = "http://127.0.0.1:8790/health"
RELEASE_DIR = ROOT / "engel_flutter_main" / "build" / "windows" / "x64" / "runner" / "Release"

# Files whose drift means the deployed build is no longer the verified build.
CORE_BUILD_BASES = {"staged_app_bundle", "source", "widget_test", "executable"}
# Pinned files the running app legitimately rewrites on launch -> drift is
# expected, reported as informational, never a hard failure.
SOFT_DRIFT_HINTS = ("ENGEL_CHAT_PROVIDER_CONFIG.json",)
# Source areas whose recent edits signal "work in flight, may need a rebuild".
WATCH_DIRS = (
    ROOT / "engel_flutter_main" / "lib",
    ROOT / "engel_flutter_main" / "test",
    ROOT / "tools",
)


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_c(p: Path) -> bool:
    return str(p.drive).lower() == "c:"


def sha256_file(p: Path):
    try:
        h = hashlib.sha256()
        with p.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest().upper()
    except Exception:
        return None


def mtime(p: Path):
    try:
        return datetime.fromtimestamp(p.stat().st_mtime, timezone.utc)
    except Exception:
        return None


def fmt(dt) -> str:
    return dt.isoformat() if dt else "?"


def ensure_out() -> None:
    if is_c(OUT_DIR):
        raise RuntimeError(f"refusing C: path for Engel health receipts: {OUT_DIR}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------- #
# manifest + pinned-file integrity
# --------------------------------------------------------------------------- #
def load_manifest():
    try:
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_load_error": str(exc)}


def walk_pinned(obj, out):
    """Collect (base, path, expected_sha) for every *_sha256 paired with a
    sibling path field anywhere in the manifest tree."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str) and k.endswith("_sha256"):
                base = k[: -len("_sha256")]
                sib = obj.get(base)
                if isinstance(sib, str) and ("\\" in sib or "/" in sib):
                    out.append((base, sib, v.upper()))
            else:
                walk_pinned(v, out)
    elif isinstance(obj, list):
        for v in obj:
            walk_pinned(v, out)


def check_integrity(manifest):
    pinned = []
    walk_pinned(manifest, pinned)
    core, soft = [], []
    for base, path_s, expected in pinned:
        p = Path(path_s)
        actual = sha256_file(p)
        is_soft = any(hint in path_s for hint in SOFT_DRIFT_HINTS)
        row = {
            "base": base,
            "path": path_s,
            "exists": p.exists(),
            "match": (actual == expected) if actual else False,
            "expected": expected,
            "actual": actual,
        }
        if base in CORE_BUILD_BASES and not is_soft:
            core.append(row)
        else:
            soft.append(row)
    return core, soft


# --------------------------------------------------------------------------- #
# active tools
# --------------------------------------------------------------------------- #
def tasklist_pids(image: str):
    try:
        out = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH", "/FI", f"IMAGENAME eq {image}"],
            capture_output=True, text=True, timeout=15,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    except Exception:
        return []
    pids = []
    for line in out.splitlines():
        line = line.strip()
        if not line or line.startswith('"INFO'):
            continue
        cells = [c.strip('"') for c in line.split('","')]
        if len(cells) >= 2 and cells[0].lower() == image.lower():
            try:
                pids.append(int(cells[1]))
            except ValueError:
                pass
    return pids


def probe_meeting_room():
    try:
        with urllib.request.urlopen(MEETING_ROOM_HEALTH, timeout=4) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return {
            "reachable": True,
            "ok": bool(data.get("ok")),
            "status": data.get("status"),
            "updated_at_utc": data.get("updated_at_utc"),
            "c_drive_used": data.get("c_drive_used"),
        }
    except Exception as exc:
        return {"reachable": False, "ok": False, "error": str(exc)[:160]}


# --------------------------------------------------------------------------- #
# recent failures
# --------------------------------------------------------------------------- #
def _classify_receipt(data: dict):
    """Return (category, signature) where category is 'error' (real breakage),
    'quality' (soft/expected flag like a humanizer style retry), or None (fine).

    A receipt is a HARD error when it carries a populated `error` exception text
    or `ok is False` with a non-style status. Style checks and ok:true status
    notes that merely mention trouble are SOFT quality flags, not breakage."""
    err = str(data.get("error") or "").strip()
    ok = data.get("ok")
    status = str(data.get("status") or "").strip()
    low = status.lower()
    if err:
        return "error", err[:160]
    if ok is False:
        if "style" in low:
            return "quality", (status[:160] or "style check")
        return "error", (status[:160] or "ok:false")
    if any(w in low for w in ("error", "failed", "crash", "timeout", "incomplete")):
        return "quality", (status[:160] or "note")
    return None, None


# Deliberate negative tests -- rollback fixtures, synthetic apply receipts, a
# fail_verifier planted to prove the gate trips -- are EVIDENCE THE GUARDS WORK,
# not breakage. Counting them put "ok:false" x13 in the headline and pointed the
# verdict at a passing test.
SYNTHETIC_RECEIPT_MARKERS = (
    "rollback_verify",
    "verify_synthetic",
    "synthetic_apply",
    "fail_verifier",
    "_negative_test",
)
# A signature nothing has reproduced for this long is a past incident, not the
# current state. Reporting a resolved 6-hour-old incident as the most frequent
# "hard error" sent a live triage down the wrong path.
STALE_ERROR_AFTER_HOURS = 12.0


def _is_synthetic_receipt(data: dict, path_s: str) -> bool:
    blob = str(path_s).replace("\\", "/").casefold()
    if any(marker in blob for marker in SYNTHETIC_RECEIPT_MARKERS):
        return True
    for key in ("apply_receipt_id", "apply_receipt_path", "required_verifiers", "reason"):
        value = str(data.get(key) or "").casefold()
        if any(marker in value for marker in SYNTHETIC_RECEIPT_MARKERS):
            return True
    return False


def scan_recent_failures(days: int, cap: int = 12):
    """Group recent receipts by failure signature so 8 identical retries read as
    one line with a count, and real exceptions surface their actual message."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, days))
    reports = ROOT / "reports"
    errors: dict = {}
    quality: dict = {}
    examined = 0
    if not reports.exists():
        return [], [], 0

    def bump(bucket: dict, sig: str, when_iso: str, path_s: str, data: dict):
        row = bucket.setdefault(sig, {
            "signature": sig, "count": 0, "newest_when_utc": "",
            "newest_path": "", "example_status": str(data.get("status") or "")[:160],
            "example_ok": data.get("ok"),
        })
        row["count"] += 1
        if when_iso > row["newest_when_utc"]:
            row["newest_when_utc"] = when_iso
            row["newest_path"] = path_s
            row["example_status"] = str(data.get("status") or "")[:160]
            row["example_ok"] = data.get("ok")

    for dirpath, dirnames, filenames in os.walk(reports):
        if "health_checks" in Path(dirpath).parts:  # never scan our own receipts
            dirnames[:] = []
            continue
        for name in filenames:
            if not name.lower().endswith(".json"):
                continue
            fp = Path(dirpath) / name
            try:
                st = fp.stat()
            except Exception:
                continue
            if st.st_size > 200_000 or st.st_size == 0:
                continue
            when = datetime.fromtimestamp(st.st_mtime, timezone.utc)
            if when < cutoff:
                continue
            examined += 1
            if examined > 6000:
                break
            try:
                data = json.loads(fp.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(data, dict):
                continue
            if _is_synthetic_receipt(data, str(fp)):
                continue
            cat, sig = _classify_receipt(data)
            if cat == "error":
                bump(errors, sig, when.isoformat(), str(fp), data)
            elif cat == "quality":
                bump(quality, sig, when.isoformat(), str(fp), data)

    def top(bucket: dict):
        return sorted(bucket.values(), key=lambda r: (r["count"], r["newest_when_utc"]), reverse=True)[:cap]

    stale_cutoff = datetime.now(timezone.utc) - timedelta(hours=STALE_ERROR_AFTER_HOURS)
    live: dict = {}
    stale: dict = {}
    for sig, row in errors.items():
        try:
            newest = datetime.fromisoformat(row["newest_when_utc"])
        except ValueError:
            newest = None
        (stale if newest is not None and newest < stale_cutoff else live)[sig] = row

    return top(live), top(quality), examined, top(stale)


def scan_recent_edits(days: int = 1, cap: int = 25):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    edits = []
    for base in WATCH_DIRS:
        if not base.exists():
            continue
        for dirpath, dirs, filenames in os.walk(base):
            dirs[:] = [d for d in dirs if d not in ("__pycache__", ".dart_tool", "build")]
            for name in filenames:
                if name.endswith((".pyc", ".pyo")):
                    continue
                fp = Path(dirpath) / name
                m = mtime(fp)
                if m and m >= cutoff:
                    edits.append({"path": str(fp), "when_utc": m.isoformat()})
    edits.sort(key=lambda e: e["when_utc"], reverse=True)
    return edits[:cap]


# --------------------------------------------------------------------------- #
# full verifier (durable GREEN stamp)
# --------------------------------------------------------------------------- #
def run_full_verifier():
    py = ROOT / "runtime" / "python310" / "python.exe"
    exe = str(py) if py.exists() else sys.executable
    try:
        proc = subprocess.run(
            [exe, str(VERIFIER)], capture_output=True, text=True,
            timeout=240, cwd=str(ROOT),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        data = json.loads(proc.stdout)
        return {
            "ran": True,
            "ok": bool(data.get("ok")),
            "pid": (data.get("running_process") or {}).get("Id"),
            "manifest_sha256": data.get("manifest_sha256"),
        }
    except Exception as exc:
        return {"ran": True, "ok": False, "error": str(exc)[:300]}


def read_last_green():
    try:
        return json.loads(LAST_GREEN.read_text(encoding="utf-8"))
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# assemble
# --------------------------------------------------------------------------- #
def build_report(args) -> dict:
    manifest = load_manifest()
    main_block = manifest.get("main", {}) if isinstance(manifest, dict) else {}

    app_so = RELEASE_DIR / "data" / "app.so"
    exe = RELEASE_DIR / "EngelAIMain.exe"
    main_dart = ROOT / "engel_flutter_main" / "lib" / "main.dart"

    app_so_m = mtime(app_so)
    main_dart_m = mtime(main_dart)
    rebuild_pending = bool(app_so_m and main_dart_m and main_dart_m > app_so_m)

    core, soft = check_integrity(manifest)
    core_drift = [r for r in core if r["exists"] and not r["match"]]
    core_missing = [r for r in core if not r["exists"]]
    soft_drift = [r for r in soft if r["exists"] and not r["match"]]

    engel_pids = tasklist_pids("EngelAIMain.exe")
    meeting = probe_meeting_room()

    errors, quality_flags, examined, stale_errors = scan_recent_failures(args.failures_days)
    recent_edits = scan_recent_edits()
    try:
        from engel_receipts import read_recent_actions
        recent_actions = read_recent_actions(10)
    except Exception:
        recent_actions = []

    full = run_full_verifier() if args.full else None
    last_green = read_last_green()
    if full and full.get("ok"):
        last_green = {
            "ok": True,
            "verified_at_utc": iso_now(),
            "pid": full.get("pid"),
            "manifest_sha256": full.get("manifest_sha256"),
        }

    # ---- next safe action decision tree ----
    if core_missing:
        action = ("A pinned build file is MISSING: "
                  + ", ".join(r["path"] for r in core_missing)
                  + ". Restore or rebuild before using the release.")
        health = "broken"
    elif core_drift or rebuild_pending:
        bits = []
        if rebuild_pending:
            bits.append("main.dart is newer than the built app.so")
        if core_drift:
            bits.append("pinned core hashes drifted (" + ", ".join(r["base"] for r in core_drift) + ")")
        action = ("Rebuild + re-verify (" + "; ".join(bits) + "): "
                  "flutter analyze/test -> flutter build windows --release -> "
                  "restart EngelAIMain.exe -> re-pin app.so/main.dart/widget_test "
                  "hashes + PID in the manifest -> python tools\\verify_engel_current_release_manifest.py. "
                  "See engel-build-verify-loop.")
        health = "dirty"
    elif not engel_pids:
        action = ("Build is consistent but EngelAIMain.exe is NOT running. "
                  "Launch it from the Release folder to use the app.")
        health = "idle"
    elif not meeting.get("ok"):
        action = ("App running but Meeting Room server is down/unreachable. "
                  "Start it: powershell tools\\start_engel_meeting_room_lan_server.ps1 "
                  "(health http://127.0.0.1:8790/health).")
        health = "degraded"
    elif errors:
        top = errors[0]
        action = (f"Build GREEN-consistent, but {len(errors)} distinct hard-error "
                  f"signature(s) in the last {args.failures_days}d. Most frequent: "
                  f"\"{top['signature']}\" x{top['count']}. Newest receipt: "
                  f"{top['newest_path']}")
        health = "attention"
    else:
        action = ("GREEN + clean. Deployed Release matches the verified manifest, "
                  "app + Meeting Room are up, no recent failures. Safe to continue "
                  "feature work or use the app. Run --full before declaring a release.")
        health = "green"

    pinned_pid = None
    if last_green:
        pinned_pid = last_green.get("pid")

    report = {
        "schema": "engel_health_check_v1",
        "generated_at_utc": iso_now(),
        "app_root": str(ROOT),
        "c_drive_used": False,
        "health": health,
        "current_version": {
            "manifest_schema": manifest.get("schema") if isinstance(manifest, dict) else None,
            "manifest_generated_at_utc": manifest.get("generated_at_utc") if isinstance(manifest, dict) else None,
            "goal_state": manifest.get("goal_state") if isinstance(manifest, dict) else None,
            "app_so_built_utc": fmt(app_so_m),
            "app_so_bytes": (app_so.stat().st_size if app_so.exists() else None),
            "exe_built_utc": fmt(mtime(exe)),
            "main_dart_modified_utc": fmt(main_dart_m),
            "main_dart_bytes": (main_dart.stat().st_size if main_dart.exists() else None),
        },
        "last_green_verify": last_green or {"ok": None, "note": "no durable GREEN stamp yet; run --full to record one"},
        "build_integrity": {
            "core_ok": (not core_drift and not core_missing),
            "core_files": core,
            "core_drift": core_drift,
            "core_missing": core_missing,
            "soft_drift": soft_drift,
            "rebuild_pending": rebuild_pending,
        },
        "dirty_files": {
            "rebuild_pending": rebuild_pending,
            "core_hash_drift": [r["path"] for r in core_drift],
            "soft_hash_drift": [r["path"] for r in soft_drift],
            "recent_edits_24h": recent_edits,
        },
        "recent_failures": {
            "window_days": args.failures_days,
            "files_examined": examined,
            "hard_error_signatures": len(errors),
            "errors": errors,
            "stale_error_signatures": len(stale_errors),
            "stale_errors": stale_errors,
            "stale_after_hours": STALE_ERROR_AFTER_HOURS,
            "soft_quality_signatures": len(quality_flags),
            "quality_flags": quality_flags,
        },
        "recent_engel_actions": {
            "log": str(ROOT / "memory" / "engel_action_log.jsonl"),
            "count": len(recent_actions),
            "items": recent_actions,
        },
        "active_tools": {
            "engel_ai_main_pids": engel_pids,
            "engel_running": bool(engel_pids),
            "running_pid_vs_last_green_pid": {
                "running": engel_pids,
                "last_green": pinned_pid,
                "restarted_since_green": bool(engel_pids and pinned_pid and pinned_pid not in engel_pids),
            },
            "meeting_room": meeting,
        },
        "next_safe_action": action,
        "full_verifier": full,
        "receipt_paths": {
            "latest_json": str(LATEST_JSON),
            "latest_md": str(LATEST_MD),
            "last_green_stamp": str(LAST_GREEN),
        },
    }
    return report


def render_md(r: dict) -> str:
    cv = r["current_version"]
    lg = r["last_green_verify"]
    at = r["active_tools"]
    L = []
    L.append(f"# Engel AI Main - Health Check ({r['health'].upper()})")
    L.append("")
    L.append(f"Generated: {r['generated_at_utc']}")
    L.append(f"App root: {r['app_root']}  (C-drive used: {r['c_drive_used']})")
    L.append("")
    L.append("## Current version")
    L.append(f"- Manifest: {cv['manifest_schema']} generated {cv['manifest_generated_at_utc']}")
    L.append(f"- Goal state: {cv['goal_state']}")
    L.append(f"- Built app.so: {cv['app_so_built_utc']} ({cv['app_so_bytes']} bytes)")
    L.append(f"- EngelAIMain.exe: {cv['exe_built_utc']}")
    L.append(f"- main.dart: {cv['main_dart_modified_utc']} ({cv['main_dart_bytes']} bytes)")
    L.append("")
    L.append("## Last GREEN verify")
    if lg and lg.get("ok"):
        L.append(f"- Verified GREEN at {lg.get('verified_at_utc')} (PID {lg.get('pid')})")
    else:
        L.append(f"- {lg.get('note', 'unknown')}")
    L.append("")
    L.append("## Build integrity")
    bi = r["build_integrity"]
    L.append(f"- Core build matches manifest: {bi['core_ok']}")
    L.append(f"- Rebuild pending (main.dart newer than app.so): {bi['rebuild_pending']}")
    if bi["core_drift"]:
        L.append(f"- CORE DRIFT: {', '.join(x['base'] for x in bi['core_drift'])}")
    if bi["soft_drift"]:
        L.append(f"- soft drift (expected/informational): {len(bi['soft_drift'])} file(s)")
    L.append("")
    L.append("## Dirty files")
    df = r["dirty_files"]
    L.append(f"- Core hash drift: {df['core_hash_drift'] or 'none'}")
    L.append(f"- Recent source edits (24h): {len(df['recent_edits_24h'])}")
    for e in df["recent_edits_24h"][:8]:
        L.append(f"    - {e['when_utc']}  {e['path']}")
    L.append("")
    L.append("## Recent failures")
    rf = r["recent_failures"]
    L.append(f"- Window: last {rf['window_days']} day(s); {rf['files_examined']} receipts examined")
    L.append(f"- Hard errors (LIVE, seen in the last {rf.get('stale_after_hours')}h): "
             f"{rf['hard_error_signatures']} distinct signature(s); "
             f"stale/resolved: {rf.get('stale_error_signatures', 0)}; "
             f"soft quality flags: {rf['soft_quality_signatures']}")
    if rf["errors"]:
        L.append("- HARD ERRORS (real breakage):")
        for e in rf["errors"][:6]:
            L.append(f"    - x{e['count']}  \"{e['signature']}\"")
            L.append(f"        newest {e['newest_when_utc']}  [{e['newest_path']}]")
    if rf.get("stale_errors"):
        L.append(f"- stale (nothing reproduced them in {rf.get('stale_after_hours')}h; "
                 "likely already fixed -- check the timeline before acting):")
        for e in rf["stale_errors"][:5]:
            L.append(f"    - x{e['count']}  \"{e['signature']}\"  newest {e['newest_when_utc']}")
    if rf["quality_flags"]:
        L.append("- soft quality flags (expected retries, not breakage):")
        for q in rf["quality_flags"][:5]:
            L.append(f"    - x{q['count']}  \"{q['signature']}\"")
    L.append("")
    ra = r.get("recent_engel_actions", {})
    L.append("## Recent Engel actions")
    L.append(f"- Tape: {ra.get('log')}")
    if ra.get("items"):
        for a in ra["items"][-8:]:
            mark = "ok" if a.get("ok") else "FAIL"
            L.append(f"    - {a.get('ts_utc')}  [{mark}] {a.get('category')}/{a.get('action')}  {a.get('summary')}")
    else:
        L.append("    - (no actions logged yet)")
    L.append("")
    L.append("## Active tools")
    L.append(f"- EngelAIMain running: {at['engel_running']} (PIDs {at['engel_ai_main_pids'] or 'none'})")
    L.append(f"- Restarted since last GREEN: {at['running_pid_vs_last_green_pid']['restarted_since_green']}")
    mr = at["meeting_room"]
    L.append(f"- Meeting Room: reachable={mr.get('reachable')} ok={mr.get('ok')} status={mr.get('status')}")
    L.append("")
    L.append("## Next safe action")
    L.append(f"{r['next_safe_action']}")
    L.append("")
    return "\n".join(L)


def render_text(r: dict) -> str:
    return render_md(r)


def write_receipts(r: dict) -> None:
    ensure_out()
    stamp = r["generated_at_utc"].replace(":", "").replace("-", "").replace(".", "")
    hist = OUT_DIR / f"ENGEL_HEALTH_CHECK_{stamp}.json"
    payload = json.dumps(r, indent=2)
    hist.write_text(payload, encoding="utf-8")
    LATEST_JSON.write_text(payload, encoding="utf-8")
    LATEST_MD.write_text(render_md(r), encoding="utf-8")
    if r.get("last_green_verify", {}).get("ok") and r.get("full_verifier", {}) and r["full_verifier"].get("ok"):
        LAST_GREEN.write_text(json.dumps(r["last_green_verify"], indent=2), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Engel AI Main health check / self-state mirror")
    ap.add_argument("--full", action="store_true", help="also run the full release verifier and record a durable GREEN stamp")
    ap.add_argument("--json", action="store_true", help="print machine JSON only")
    ap.add_argument("--failures-days", type=int, default=3, help="how many days back to scan for failure receipts")
    args = ap.parse_args()

    report = build_report(args)
    write_receipts(report)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(render_text(report))
        print(f"\nReceipt: {LATEST_MD}")
    # exit code: 0 only when health is green or attention(non-broken); non-zero on broken/dirty
    return 0 if report["health"] in ("green", "attention", "idle", "degraded") else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover
        print(json.dumps({"ok": False, "status": "health check crashed", "error": str(exc)}, indent=2))
        raise SystemExit(2)
