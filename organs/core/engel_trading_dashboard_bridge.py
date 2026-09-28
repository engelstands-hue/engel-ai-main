"""Read-only Engel Dashboard bridge for Agent Meeting Room routing.

The dashboard project lives beside Engel App at ``D:\b.WorkSpace\engel-dashboard``.
This bridge makes its design, safety, and SnapTrade setup visible to Engel AI
without importing dashboard runtime code, reading secrets, starting helpers, or
executing trades.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import re
from pathlib import Path
from typing import Any


ENGEL_APP_ROOT = Path(__file__).resolve().parent
WORKSPACE_ROOT = ENGEL_APP_ROOT.parent
DASHBOARD_ROOT = WORKSPACE_ROOT / "engel-dashboard"
DOCS_ROOT = DASHBOARD_ROOT / "docs"
BRIDGE_RUNTIME = ENGEL_APP_ROOT / "runtime" / "meeting_room" / "trading_dashboard"
BRIDGE_LABEL = "Trading Dashboard Bridge (Engel Dashboard)"
MERGE_VERSION = "ENGEL_TRADING_DASHBOARD_BRIDGE_V1"

DOC_PATHS = {
    "agent_design": DOCS_ROOT / "agent_design.md",
    "safety_rules": DOCS_ROOT / "safety_rules.md",
    "snaptrade_setup": DOCS_ROOT / "snaptrade_setup.md",
    "work_log": DOCS_ROOT / "WORK_LOG_2026-05-28.md",
    "handoff": DASHBOARD_ROOT / "HANDOFF.md",
}

DOC_REQUIRED_MARKERS = {
    "agent_design": (
        "Signal Agent",
        "Risk Agent",
        "Trader Agent",
        "Portfolio Agent",
        "The Risk Agent is a hard gate",
    ),
    "safety_rules": (
        "manual approval before switching from paper trading to live trading",
        "circuit breaker",
        "Never allow hidden trades",
        "AI cost usage",
        "manual reset is required",
    ),
    "snaptrade_setup": (
        "127.0.0.1 only",
        "CORS pinned",
        "Random 32-byte session token",
        "Consumer Key lives in",
        "Robinhood password never touches",
    ),
    "work_log": (
        "never touched the existing `Engel App/` folder",
        "Paper-only autonomy",
        "Deterministic-only research agents",
        "Smoke tests against real data",
        "C: drive audit",
    ),
    "handoff": (
        "Functional end-to-end",
        "Paper-only autonomy",
        "Integration with the larger Engel App",
        "No memory writes",
        "Nothing on C: drive",
    ),
}

AGENT_MERGE_MAP = (
    {
        "dashboard_agent": "Signal Agent",
        "engel_agent": "Financial Strategist Agent",
        "skill": "Financial Strategy Skill",
        "purpose": "Convert market data into buy/sell/hold research context.",
    },
    {
        "dashboard_agent": "Risk Agent",
        "engel_agent": "Safety Agent",
        "skill": "Safety Review Skill",
        "purpose": "Hard gate live actions, budgets, position limits, and circuit breakers.",
    },
    {
        "dashboard_agent": "Portfolio Agent",
        "engel_agent": "Portfolio Strategist Agent",
        "skill": "Portfolio Strategy Skill",
        "purpose": "Track account value, holdings, P/L, and exposure.",
    },
    {
        "dashboard_agent": "DCA Agent / Trail Agent",
        "engel_agent": "Quant Modeler Agent",
        "skill": "Quant Modeling Skill",
        "purpose": "Analyze staged entries, stops, thresholds, and backtest-ready rules.",
    },
    {
        "dashboard_agent": "Logging Agent / Backup Agent",
        "engel_agent": "Verifier Agent",
        "skill": "Verification Skill",
        "purpose": "Require audit trails, backups, and reviewer-visible receipts.",
    },
    {
        "dashboard_agent": "Dashboard UI / helper boundary",
        "engel_agent": "Dashboard Architect Agent",
        "skill": "Dashboard Architecture Skill",
        "purpose": "Keep helper, frontend, CORS, and token flow understandable.",
    },
)

SAFETY_GATES = {
    "paper_only_default": True,
    "live_trading_requires_manual_approval": True,
    "risk_agent_is_hard_gate": True,
    "circuit_breakers_always_active": True,
    "training_separate_from_trading": True,
    "snaptrade_helper_localhost_only": True,
    "no_secret_ingest_by_engel_ai": True,
    "no_raw_broker_order_from_meeting_room": True,
    "no_c_project_storage": True,
}

BLOCKED_BY_DESIGN = (
    "Engel AI does not read backend/.env or snaptrade_user_secret.json.",
    "Engel AI does not submit live broker orders from Meeting Room routing.",
    "Engel AI does not start the SnapTrade helper or frontend automatically.",
    "Engel AI does not store pairing tokens, session tokens, passwords, or keys in reports.",
    "Paper-to-live switching remains a manual approval event outside this bridge.",
)


def _safe_id(text: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(text or "").strip())
    return cleaned.strip("_")[:90] or "trading_dashboard_merge"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _fingerprint(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "path": str(path)}
    data = path.read_bytes()
    return {
        "exists": True,
        "path": str(path),
        "size_bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "modified_utc": _dt.datetime.utcfromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds") + "Z",
    }


def _marker_status(key: str, text: str) -> dict[str, bool]:
    lowered = text.lower()
    return {
        marker: marker.lower() in lowered
        for marker in DOC_REQUIRED_MARKERS.get(key, ())
    }


def review_dashboard_docs() -> dict[str, Any]:
    """Review dashboard docs and return a bounded merge/audit packet."""
    documents: dict[str, Any] = {}
    missing: list[str] = []
    marker_failures: list[str] = []

    for key, path in DOC_PATHS.items():
        info = _fingerprint(path)
        if not path.exists():
            missing.append(key)
            info["markers"] = {}
        else:
            text = _read(path)
            markers = _marker_status(key, text)
            info["markers"] = markers
            for marker, ok in markers.items():
                if not ok:
                    marker_failures.append(f"{key}: {marker}")
        documents[key] = info

    ok = not missing and not marker_failures
    return {
        "ok": ok,
        "version": MERGE_VERSION,
        "bridge": BRIDGE_LABEL,
        "dashboard_root": str(DASHBOARD_ROOT),
        "reviewed_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "documents": documents,
        "missing_docs": missing,
        "marker_failures": marker_failures,
        "merge_scope": (
            "Read-only Engel AI awareness and Meeting Room routing for the standalone "
            "dashboard project. Runtime helpers, credentials, and trading remain in "
            "the dashboard project boundary."
        ),
        "merged_agent_map": list(AGENT_MERGE_MAP),
        "safety_gates": dict(SAFETY_GATES),
        "blocked_by_design": list(BLOCKED_BY_DESIGN),
        "allowed_engel_actions": (
            "review dashboard docs",
            "route dashboard or SnapTrade planning through finance/safety/dashboard agents",
            "stage paper-trading design/audit reports",
            "summarize helper status expectations",
        ),
    }


def _write_report(path: Path, result: dict[str, Any]) -> None:
    docs = result.get("review", {}).get("documents", {})
    lines = [
        "# Engel Trading Dashboard Bridge Merge",
        "",
        f"- Version: {MERGE_VERSION}",
        f"- Bridge: {BRIDGE_LABEL}",
        f"- Source: {result.get('source')}",
        f"- Prompt: {result.get('prompt')}",
        f"- Result: {'PASS' if result.get('ok') else 'NEEDS REVIEW'}",
        f"- Dashboard root: {DASHBOARD_ROOT}",
        "",
        "## Merge Scope",
        "",
        result.get("review", {}).get("merge_scope", ""),
        "",
        "## Documents Reviewed",
        "",
    ]
    for key, info in docs.items():
        exists = "yes" if info.get("exists") else "no"
        lines.append(f"- {key}: exists={exists}; size={info.get('size_bytes', 0)}; sha256={str(info.get('sha256', ''))[:16]}")

    lines += [
        "",
        "## Agent Mapping",
        "",
    ]
    for item in result.get("review", {}).get("merged_agent_map", []):
        lines.append(
            "- {dashboard_agent} -> {engel_agent} / {skill}: {purpose}".format(**item)
        )

    lines += [
        "",
        "## Safety Gates",
        "",
    ]
    for key, value in result.get("review", {}).get("safety_gates", {}).items():
        lines.append(f"- {key}: {value}")

    lines += [
        "",
        "## Blocked By Design",
        "",
    ]
    for item in result.get("review", {}).get("blocked_by_design", []):
        lines.append(f"- {item}")

    lines += [
        "",
        "## Merge Notes",
        "",
        "- Engel Meeting Room can route dashboard/SnapTrade/paper-trader prompts to the new bridge.",
        "- The dashboard remains standalone until the helper and frontend are started by the user.",
        "- No key, token, password, or broker session is copied into Engel AI.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def stage_dashboard_merge_packet(prompt: str, *, source: str = "Agent Meeting Room") -> dict[str, Any]:
    """Stage a real merge review packet under Engel App runtime."""
    stamp = _dt.datetime.now().strftime("%Y%m%dT%H%M%S%f")
    run_id = f"engel-trading-dashboard-{stamp}"
    run_root = BRIDGE_RUNTIME / "merge" / _safe_id(run_id)
    run_root.mkdir(parents=True, exist_ok=True)

    review = review_dashboard_docs()
    result: dict[str, Any] = {
        "ok": bool(review.get("ok")),
        "bridge": BRIDGE_LABEL,
        "version": MERGE_VERSION,
        "mode": "read_only_dashboard_doc_merge",
        "source": source,
        "run_id": run_id,
        "prompt": str(prompt or "").strip(),
        "run_root": str(run_root),
        "review": review,
    }
    status_path = run_root / "status.json"
    report_path = run_root / "TRADING_DASHBOARD_MERGE_REPORT.md"
    result["status_path"] = str(status_path)
    result["report_path"] = str(report_path)
    _write_report(report_path, result)
    status_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def summarize_dashboard_bridge_result(result: dict[str, Any]) -> str:
    review = result.get("review") if isinstance(result, dict) else {}
    review = review if isinstance(review, dict) else {}
    docs = review.get("documents") if isinstance(review.get("documents"), dict) else {}
    mapped = review.get("merged_agent_map") or []
    lines = [
        "Trading Dashboard bridge returned a merge packet.",
        f"Bridge: {result.get('bridge')}",
        f"Run: {result.get('run_id')}",
        f"Report: {result.get('report_path')}",
        f"Docs reviewed: {len(docs)}",
        f"Agent mappings: {len(mapped)}",
        "Safety: paper-only default, live trading blocked until manual approval, no secrets imported.",
    ]
    if review.get("missing_docs"):
        lines.append("Missing docs: " + ", ".join(review.get("missing_docs") or []))
    if review.get("marker_failures"):
        lines.append("Needs review: " + "; ".join(review.get("marker_failures") or []))
    return "\n".join(lines)


def render_trading_dashboard_bridge_status() -> str:
    result = stage_dashboard_merge_packet(
        "Review Engel dashboard docs and report current merge status.",
        source="Engel AI route status",
    )
    return summarize_dashboard_bridge_result(result)


if __name__ == "__main__":
    print(render_trading_dashboard_bridge_status())
