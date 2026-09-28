"""File Engel AI Main job outputs into the ICM workspace.

Does not move Engel source. Historical reports stay in reports/.
New job product is filed once under memory/icm/engel-ai-main/.

Layout (ICM paper):
  jobs/<id>/              record library — one home per job
  stages/<nn>_<name>/output/   pipeline scan points (pointer files)
  _shared/output-routing.md    factory rules
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from engel_project_paths import resolve_engel_app_root


ROOT = resolve_engel_app_root(__file__)
WORKSPACE = ROOT / "memory" / "icm" / "engel-ai-main"
JOBS_DIR = WORKSPACE / "jobs"
INDEX_PATH = JOBS_DIR / "INDEX.md"
KIND_STAGE = {
    "audit": "01_inventory",
    "proposal": "02_propose",
    "walk": "03_walk_test",
    "intake": "04_intake",
    "work": "05_work",
    "teammate": "05_work",
    "receipt": "06_receipt",
    "handoff": "06_receipt",
    "report": "06_receipt",
}
_SLUG = re.compile(r"[^a-z0-9]+")


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _slug(value: str) -> str:
    text = _SLUG.sub("-", str(value or "").casefold()).strip("-")
    return (text[:40] or "job")


def stage_for_kind(kind: str) -> str:
    return KIND_STAGE.get(str(kind or "").strip().casefold(), "06_receipt")


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _append_index(row: dict[str, str]) -> None:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    if not INDEX_PATH.is_file():
        INDEX_PATH.write_text(
            "# Engel AI Main job index\n\n"
            "Status is this table plus `stages/*/output/`.\n\n"
            "| id | kind | stage | title | path | at |\n"
            "|---|---|---|---|---|---|\n",
            encoding="utf-8",
        )
    line = (
        f"| `{row['id']}` | {row['kind']} | {row['stage']} | "
        f"{row['title']} | `{row['rel']}` | {row['at']} |\n"
    )
    with INDEX_PATH.open("a", encoding="utf-8") as handle:
        handle.write(line)


def file_engel_output(
    kind: str,
    title: str,
    body: Any,
    source: str = "",
    extra: dict[str, Any] | None = None,
) -> dict[str, str]:
    """File one Engel AI Main output. Returns paths. Never raises to callers."""
    try:
        kind_key = str(kind or "receipt").strip().casefold()
        stage = stage_for_kind(kind_key)
        stamp = _stamp()
        job_id = f"{stamp}_{kind_key}_{_slug(title)}"
        job_dir = JOBS_DIR / job_id
        output_dir = job_dir / "output"
        stage_dir = WORKSPACE / "stages" / stage / "output"

        if isinstance(body, (dict, list)):
            payload = json.dumps(body, indent=2, ensure_ascii=False)
            suffix = ".json"
        else:
            payload = str(body or "")
            suffix = ".md"

        contract = "\n".join(
            [
                f"# Job {job_id}",
                "",
                "## Inputs",
                f"- kind: {kind_key}",
                f"- source: {source or 'engel-ai-main'}",
                f"- title: {title}",
                "",
                "## Process",
                "File this output into the Engel AI Main ICM workspace.",
                "Do not move Engel source. Do not write trusted memory.",
                "",
                "## Outputs",
                f"- `output/work{suffix}`",
                "- `output/receipt.json`",
                "",
                "## Human check",
                "Open the output files. Next stage reads whatever is left here.",
                "",
            ]
        )
        _write(job_dir / "CONTEXT.md", contract)
        work_path = _write(output_dir / f"work{suffix}", payload + ("\n" if not payload.endswith("\n") else ""))
        receipt = {
            "schema": "engel_icm_job_receipt_v1",
            "id": job_id,
            "kind": kind_key,
            "stage": stage,
            "title": str(title or ""),
            "source": source or "engel-ai-main",
            "work_path": str(work_path),
            "written_at_utc": _now(),
        }
        if extra:
            receipt["extra"] = extra
        receipt_path = _write(
            output_dir / "receipt.json",
            json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
        )
        pointer = "\n".join(
            [
                f"# {title or job_id}",
                "",
                f"kind: {kind_key}",
                f"job: `jobs/{job_id}/`",
                f"work: `jobs/{job_id}/output/work{suffix}`",
                f"receipt: `jobs/{job_id}/output/receipt.json`",
                "",
                "One home: the job folder. This file is the stage scan point.",
                "",
            ]
        )
        pointer_path = _write(stage_dir / f"{job_id}.md", pointer)
        rel = f"jobs/{job_id}/"
        _append_index(
            {
                "id": job_id,
                "kind": kind_key,
                "stage": stage,
                "title": str(title or job_id).replace("|", "/"),
                "rel": rel,
                "at": _now(),
            }
        )
        return {
            "ok": "true",
            "id": job_id,
            "stage": stage,
            "job_dir": str(job_dir),
            "work_path": str(work_path),
            "receipt_path": str(receipt_path),
            "pointer_path": str(pointer_path),
        }
    except Exception as exc:
        return {"ok": "false", "error": f"{type(exc).__name__}: {exc}"}


def list_recent_jobs(limit: int = 12) -> list[dict[str, str]]:
    if not JOBS_DIR.is_dir():
        return []
    rows: list[dict[str, str]] = []
    for path in sorted(JOBS_DIR.iterdir(), reverse=True):
        if not path.is_dir() or path.name.startswith("_"):
            continue
        receipt = path / "output" / "receipt.json"
        data: dict[str, Any] = {}
        if receipt.is_file():
            try:
                loaded = json.loads(receipt.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    data = loaded
            except (OSError, ValueError):
                data = {}
        rows.append(
            {
                "id": path.name,
                "kind": str(data.get("kind") or ""),
                "stage": str(data.get("stage") or ""),
                "title": str(data.get("title") or path.name),
                "path": str(path),
            }
        )
        if len(rows) >= limit:
            break
    return rows


def render_icm_outputs(payload: str = "") -> str:
    del payload
    jobs = list_recent_jobs(16)
    lines = [
        "Engel AI Main ICM outputs",
        "",
        f"Workspace: {WORKSPACE}",
        "New job product is filed under jobs/<id>/ (one home).",
        "Stage folders hold pointers so status is a folder scan.",
        "Historical reports/ stays put. Source is not moved.",
        "",
        "Kind → stage:",
    ]
    for kind, stage in KIND_STAGE.items():
        lines.append(f"- {kind} → stages/{stage}/output/")
    lines.extend(["", "Recent jobs:"])
    if not jobs:
        lines.append("- none yet")
    for job in jobs:
        lines.append(f"- {job['id']}  [{job['kind']}/{job['stage']}]  {job['title']}")
    if INDEX_PATH.is_file():
        lines.extend(["", f"Index: {INDEX_PATH}"])
    return "\n".join(lines)


def render_icm_routing(payload: str = "") -> str:
    del payload
    return "\n".join(
        [
            "Engel AI Main output routing",
            "",
            "Catalog: memory/icm/engel-ai-main/CLAUDE.md",
            "Factory: memory/icm/engel-ai-main/_shared/output-routing.md",
            "Product: memory/icm/engel-ai-main/jobs/<id>/output/",
            "",
            "If a Grok Bot, ICM, or job report writes, it calls file_engel_output().",
            "That creates a job record + a stage pointer. It does not rewrite Engel source.",
            "",
            "Scan status:",
            "- stages/01_inventory/output/",
            "- stages/02_propose/output/",
            "- stages/03_walk_test/output/",
            "- stages/04_intake/output/",
            "- stages/05_work/output/",
            "- stages/06_receipt/output/",
            "- jobs/INDEX.md",
        ]
    )
