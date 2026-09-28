#!/usr/bin/env python3
"""Build a readable map of real user UI input routing choices."""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports" / "meeting_rooms"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _clip(text: str, limit: int = 80) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 3)].rstrip() + "..."


def _table_escape(text: str) -> str:
    return str(text or "").replace("|", "\\|").replace("\n", " ")


def _mermaid_label(text: str) -> str:
    value = _clip(text, 54)
    return value.replace('"', "'").replace("[", "(").replace("]", ")")


def _node(prefix: str, idx: int) -> str:
    return f"{prefix}{idx}"


def _primary(record: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    order = (record.get("new_orders") or [{}])[0] or {}
    detail = (order.get("station_details") or [{}])[0] or {}
    ret = (record.get("new_returns") or [{}])[0] or {}
    artifact = (record.get("new_artifacts") or [{}])[0] or {}
    return order, detail, ret, artifact


def build_map(receipt_path: Path) -> tuple[Path, Path]:
    receipt = _load_json(receipt_path)
    records = list(receipt.get("records") or [])
    map_stamp = receipt_path.stem.replace("ENGEL_SIMPLE_USER_UI_INPUT_JOBS_", "")
    md_path = REPORT_DIR / f"ENGEL_REAL_USER_INPUT_CHOICE_MAP_{map_stamp}.md"
    json_path = REPORT_DIR / f"ENGEL_REAL_USER_INPUT_CHOICE_MAP_{map_stamp}.json"

    summary_rows: list[dict[str, Any]] = []
    for record in records:
        order, detail, ret, artifact = _primary(record)
        summary_rows.append(
            {
                "index": record.get("index"),
                "label": record.get("label"),
                "prompt": record.get("prompt"),
                "job_type": order.get("job_type"),
                "device": detail.get("device"),
                "agent": detail.get("agent"),
                "skill": detail.get("skill"),
                "bridge": detail.get("bridge"),
                "worker": ret.get("worker_id"),
                "transport": ",".join(str(item) for item in (ret.get("transports") or [])),
                "artifact": artifact.get("kind"),
                "artifact_dir": artifact.get("artifact_dir"),
                "station_routes": order.get("station_routes") or [],
                "station_results": order.get("station_results") or [],
            }
        )

    worker_counts = Counter(str(row.get("worker") or "none") for row in summary_rows)
    artifact_counts = Counter(str(row.get("artifact") or "none") for row in summary_rows)
    job_counts = Counter(str(row.get("job_type") or "none") for row in summary_rows)

    lines: list[str] = [
        "# Engel Real User Input Choice Map",
        "",
        f"Source receipt: `{receipt_path}`",
        f"Source transcript: `{receipt.get('transcript')}`",
        "",
        "Route tested: plain Engel AI UI input -> Meeting Room auto-select -> device worker -> artifact.",
        "",
        "## Summary",
        "",
        f"- Jobs: {len(summary_rows)}",
        "- Workers: " + ", ".join(f"{key}={value}" for key, value in sorted(worker_counts.items())),
        "- Artifact kinds: " + ", ".join(f"{key}={value}" for key, value in sorted(artifact_counts.items())),
        "- Job types: " + ", ".join(f"{key}={value}" for key, value in sorted(job_counts.items())),
        "",
        "## Choice Table",
        "",
        "| # | User prompt | Job type | Device | Agent | Skill | Result |",
        "| ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for row in summary_rows:
        lines.append(
            "| {idx} | {prompt} | `{job}` | {device} | {agent} | {skill} | {artifact} / {worker} / {transport} |".format(
                idx=row.get("index"),
                prompt=_table_escape(_clip(str(row.get("prompt") or ""), 72)),
                job=_table_escape(str(row.get("job_type") or "")),
                device=_table_escape(str(row.get("device") or "")),
                agent=_table_escape(str(row.get("agent") or "")),
                skill=_table_escape(str(row.get("skill") or "")),
                artifact=_table_escape(str(row.get("artifact") or "")),
                worker=_table_escape(str(row.get("worker") or "")),
                transport=_table_escape(str(row.get("transport") or "")),
            )
        )

    lines += [
        "",
        "## Route Graph",
        "",
        "```mermaid",
        "flowchart LR",
        "  UI[Engel AI UI input]",
        "  MR[Agent Meeting Room auto-select]",
    ]
    for row in summary_rows:
        idx = int(row.get("index") or 0)
        prompt_node = _node("P", idx)
        job_node = _node("J", idx)
        device_node = _node("D", idx)
        agent_node = _node("A", idx)
        result_node = _node("R", idx)
        lines += [
            f'  {prompt_node}["{idx}. {_mermaid_label(str(row.get("prompt") or ""))}"]',
            f'  {job_node}["{_mermaid_label(str(row.get("job_type") or ""))}"]',
            f'  {device_node}["{_mermaid_label(str(row.get("device") or ""))}"]',
            f'  {agent_node}["{_mermaid_label(str(row.get("agent") or ""))}<br/>{_mermaid_label(str(row.get("skill") or ""))}"]',
            f'  {result_node}["{_mermaid_label(str(row.get("artifact") or ""))} artifact"]',
            f"  UI --> {prompt_node} --> MR --> {job_node} --> {device_node} --> {agent_node} --> {result_node}",
        ]
    lines += [
        "```",
        "",
        "## Full Station Routes",
        "",
    ]
    for row in summary_rows:
        lines += [
            f"### {row.get('index')}. {_clip(str(row.get('prompt') or ''), 100)}",
            "",
        ]
        routes = row.get("station_routes") or []
        results = row.get("station_results") or []
        if not routes:
            lines.append("- No station route captured.")
        for route, result in zip(routes, results or [""] * len(routes)):
            suffix = f" [{result}]" if result else ""
            lines.append(f"- {route}{suffix}")
        lines.append("")

    payload = {
        "source_receipt": str(receipt_path),
        "source_transcript": receipt.get("transcript"),
        "summary": {
            "jobs": len(summary_rows),
            "workers": dict(sorted(worker_counts.items())),
            "artifacts": dict(sorted(artifact_counts.items())),
            "job_types": dict(sorted(job_counts.items())),
        },
        "routes": summary_rows,
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    md_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return md_path, json_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    md_path, json_path = build_map(args.receipt)
    print(json.dumps({"map": str(md_path), "json": str(json_path)}, indent=2))


if __name__ == "__main__":
    main()
