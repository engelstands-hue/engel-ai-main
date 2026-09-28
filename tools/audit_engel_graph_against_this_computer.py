#!/usr/bin/env python3
"""Deep audit: graph claims vs folders/files on THIS computer.

This laptop is Engel's face. CT246 and E/F/G shelves are other places.
A node that names a path must say whether it lives here, elsewhere, or is gone.
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT_DIR = ROOT / "reports" / "engel_graphs" / "audits"
MAIN_RE = re.compile(r"engel_[a-z0-9_]+_main")
PATH_RE = re.compile(
    r"(?:[A-Za-z]:\\[^\s\"']+)|(?:/(?:opt|mnt|usr|home|var)[^\s\"']*)"
)

VENDORED_FOLDER_HINTS = {
    "Engel IDE": "engel_ide_companion_main",
    "Engel Knowledge Graph": "engel_knowledge_graph_main",
    "Knowledge Graph V2": "engel_knowledge_graph_v2_main",
    "CLI Anything": "engel_cli_anything_main",
    "GitNexus": "engel_git_nexus_main",
    "Octogent Swarm": "engel_octogent_main",
    "Open Agents": "engel_open_agents_main",
    "OpenJarvis": "engel_jarvis_main",
    "AI Gallery": "engel_ai_gallery_main",
    "Hermes Agent": "engel_hermes_agent_main",
    "CubeSandbox Agent Sandbox": "engel_cubesandbox_main",
    "Darwinian Evolver": "engel_darwinian_evolver_main",
    "LocalSend": "engel_localsend_main",
    "GStack Agent Framework": "engel_gstack_main",
    "LFM2 SDK": "engel_lfm2_main",
    "LFM2 Code Review": "engel_lfm2_code_review_main",
    "LFM2.5 Mobile": "engel_lfm2_mobile_main",
    "LFM2 Vision": "engel_lfm2_vision_main",
    "Claw3D 3D Agent Office": "engel_claw3d_main",
    "EngelCode": "engelcode_main",
    "Engel Sandbox": "engelsandbox_main",
    "Engel Evolution Lab": "engel_evolution_lab_main",
    "Engel Evolution Engine": "engel_evolution_engine_main",
    "Cluster": "engel_cluster_main",
}


def _iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _place(path: Path) -> str:
    text = str(path)
    low = text.replace("/", "\\").casefold()
    if low.startswith("d:\\b.workspace\\engel app"):
        return "this_computer"
    if low.startswith("e:\\") or low.startswith("f:\\") or low.startswith("g:\\"):
        return "external_shelf"
    if "\\opt\\engel" in low or text.startswith("/opt/engel"):
        return "ct246"
    if "engel-hdd-vault" in low:
        return "ct246_archive"
    return "other"


def classify_path(raw: str) -> dict[str, Any]:
    text = str(raw or "").strip()
    if not text:
        return {"path": text, "exists": False, "place": "none", "kind": "empty"}
    # Windows turns "/opt/engel" into "\opt\engel" on the current drive.
    if text.startswith("/opt/") or text.startswith("/mnt/"):
        posix = text
        exists = False
        return {
            "path": posix,
            "exists": exists,
            "place": "ct246" if posix.startswith("/opt/") else "ct246_archive",
            "kind": "server_path",
            "on_this_computer": False,
        }
    path = Path(text)
    exists = path.exists()
    place = _place(path)
    on_here = exists and place == "this_computer"
    return {
        "path": text,
        "exists": exists,
        "place": place,
        "kind": "file" if exists and path.is_file() else "folder" if exists and path.is_dir() else "missing",
        "on_this_computer": on_here,
    }


def runner_folder_refs() -> list[dict[str, Any]]:
    rows = []
    files = list(ROOT.glob("engel_*runner.py")) + list((ROOT / "tools").glob("engel_*runner.py"))
    files.append(ROOT / "engel_minor_tools_runner.py")
    seen = set()
    for py in files:
        if not py.is_file():
            continue
        text = py.read_text(encoding="utf-8", errors="replace")
        for name in sorted(set(MAIN_RE.findall(text))):
            key = (py.name, name)
            if key in seen:
                continue
            seen.add(key)
            folder = ROOT / name
            rows.append(
                {
                    "runner": py.name,
                    "folder": name,
                    "exists": folder.is_dir(),
                    "on_this_computer": folder.is_dir(),
                }
            )
    return rows


def route_module_audit() -> list[dict[str, Any]]:
    import engel_ai_update_routes as routes

    rows = []
    for route in routes.UPDATE_ROUTES:
        mod = str(route.target_module)
        cands = [ROOT / f"{mod}.py", ROOT / "tools" / f"{mod}.py"]
        found = next((str(c) for c in cands if c.is_file()), "")
        rows.append(
            {
                "route_id": route.route_id,
                "module": mod,
                "exists": bool(found),
                "path": found,
            }
        )
    return rows


def folder_graph_audit() -> dict[str, Any]:
    # Studio moved to D:\Graph_&_Loop_Studio (loaded via the root shim); its old
    # build_folder_graph() was replaced by scan_project(), which reports each
    # entry's project-relative path in "relative_path" and names the root node
    # "flagship" instead of "folder_root".
    from engel_graph_loop_studio import scan_project

    scan = scan_project(ROOT, max_nodes=360)
    missing = []
    present = 0
    for node in scan.get("nodes") or []:
        rel = str(node.get("relative_path") or "")
        if node.get("id") == "flagship" or rel in ("", "."):
            present += 1
            continue
        path = ROOT / rel.replace("/", "\\")
        if path.exists():
            present += 1
        else:
            missing.append({"id": node.get("id"), "label": node.get("label"), "detail": rel})
    return {
        "node_count": len(scan.get("nodes") or []),
        "present": present,
        "missing": missing,
    }


def saved_graph_folder_audit() -> list[dict[str, Any]]:
    save_dir = ROOT / "reports" / "engel_graphs" / "studio_graphs"
    out = []
    if not save_dir.is_dir():
        return out
    for path in sorted(save_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        missing = []
        checked = 0
        for node in data.get("nodes") or []:
            if node.get("kind") not in {"folder", "file"}:
                continue
            detail = str(node.get("detail") or "")
            if not detail or detail.startswith("/") or ":\\" in detail:
                continue
            checked += 1
            if not (ROOT / detail.replace("/", "\\")).exists():
                missing.append({"label": node.get("label"), "detail": detail})
        out.append({"file": path.name, "checked": checked, "missing": missing})
    return out


def vendored_group_audit() -> list[dict[str, Any]]:
    rows = []
    for label, folder in sorted(VENDORED_FOLDER_HINTS.items()):
        path = ROOT / folder
        rows.append(
            {
                "graph_label": label,
                "folder": folder,
                "exists": path.is_dir(),
                "on_this_computer": path.is_dir(),
            }
        )
    return rows


def storage_shelf_audit() -> list[dict[str, Any]]:
    shelves = [
        (r"D:\b.WorkSpace\Engel App", "this_computer"),
        (r"E:\ENGEL_APP_MEMORY", "external_shelf"),
        (r"F:\ENGEL_APP_MEMORY", "external_shelf"),
        (r"G:\ENGEL_APP_MEMORY", "external_shelf"),
        ("/opt/engel", "ct246"),
        ("/mnt/engel-hdd-vault", "ct246_archive"),
    ]
    rows = []
    for raw, place in shelves:
        info = classify_path(raw)
        info["claimed_place"] = place
        info["on_this_computer"] = bool(info.get("exists") and place == "this_computer")
        if place != "this_computer":
            info["on_this_computer"] = False
            if place.startswith("ct246"):
                # Do not treat D:\opt\engel as the Dell CT.
                info["exists_here_as_windows_quirk"] = Path(raw).exists() if not raw.startswith("/") else False
                info["exists"] = False
        rows.append(info)
    return rows


def run_audit() -> dict[str, Any]:
    runners = runner_folder_refs()
    modules = route_module_audit()
    folders = folder_graph_audit()
    saved = saved_graph_folder_audit()
    vendored = vendored_group_audit()
    shelves = storage_shelf_audit()
    gone_runners = [row for row in runners if not row["exists"]]
    gone_modules = [row for row in modules if not row["exists"]]
    gone_vendored = [row for row in vendored if not row["exists"]]
    gone_shelves = [row for row in shelves if not row.get("on_this_computer")]
    return {
        "schema": "engel_graph_this_computer_audit_v1",
        "ok": True,
        "updated_at_utc": _iso(),
        "computer": str(ROOT),
        "honest": (
            "This computer is the ROG face. Missing E/F/G and CT246 paths are other places, "
            "not deleted Engel App folders. Gone *_main folders are deleted local trees "
            "that still have Engel phrases."
        ),
        "shelves": shelves,
        "gone_shelves_not_this_computer": gone_shelves,
        "live_folder_graph": folders,
        "saved_graphs": saved,
        "runner_folder_refs": runners,
        "gone_runner_folders": gone_runners,
        "route_modules_missing": gone_modules,
        "route_module_count": len(modules),
        "vendored_groups": vendored,
        "gone_vendored_trees": gone_vendored,
        "counts": {
            "gone_runner_folders": len(gone_runners),
            "gone_vendored_trees": len(gone_vendored),
            "missing_route_modules": len(gone_modules),
            "live_folder_nodes_missing": len(folders.get("missing") or []),
            "shelves_not_here": len(gone_shelves),
        },
    }


def write_audit() -> Path:
    payload = run_audit()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / "ENGEL_GRAPH_THIS_COMPUTER_AUDIT.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def main() -> int:
    path = write_audit()
    data = json.loads(path.read_text(encoding="utf-8"))
    print(json.dumps({"ok": True, "path": str(path), "counts": data.get("counts"), "gone_vendored_trees": data.get("gone_vendored_trees"), "gone_runner_folders": data.get("gone_runner_folders"), "shelves": data.get("shelves")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
