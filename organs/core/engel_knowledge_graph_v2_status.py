"""Engel Knowledge Graph V2 — status and discovery views for engel_graphify.

All render_* functions are read-only. render_kg_install() runs pip install
and is the only mutating route; it must be user-confirmed in the GUI.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

_GRAPH_CACHE: dict[str, Any] = {}  # path → networkx DiGraph

_APP_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
_KG_DIR = _APP_ROOT / "engel_knowledge_graph_main"
_GLOBAL_DIR = Path.home() / ".engel_graphify"
_GLOBAL_MANIFEST = _GLOBAL_DIR / "global-manifest.json"
_GLOBAL_GRAPH = _GLOBAL_DIR / "global-graph.json"

# Scan these roots for engel_graphify-out directories
_SCAN_ROOTS = [_APP_ROOT, _APP_ROOT.parent]
_SCAN_EXCLUDE_DIRS = frozenset({
    ".git",
    ".idea",
    ".vscode",
    "__pycache__",
    "venv",
    ".venv",
    "node_modules",
    "site-packages",
    "build",
    "dist",
    "lib",
    "external",
    "flutter_windows_3.41.9-stable",
    "New folder",
})


def _is_installed() -> bool:
    try:
        import importlib.util
        return importlib.util.find_spec("engel_graphify") is not None
    except Exception:
        return False


def _pkg_version() -> str:
    try:
        from importlib.metadata import version
        return version("engel_graphifyy")
    except Exception:
        return "unknown"


def _find_graph_outputs() -> list[dict[str, object]]:
    """Find all engel_graphify-out/graph.json files under scan roots."""
    results: list[dict[str, object]] = []
    candidates: list[Path] = []
    for root in _SCAN_ROOTS:
        if not root.exists():
            continue
        candidates.append(root / "engel_graphify-out" / "graph.json")
        try:
            children = [p for p in root.iterdir() if p.is_dir()]
        except OSError:
            children = []
        for child in children:
            if child.name in _SCAN_EXCLUDE_DIRS or child.name.endswith(".egg-info"):
                continue
            candidates.append(child / "engel_graphify-out" / "graph.json")
    for gj in dict.fromkeys(candidates):
        if not gj.exists():
            continue
        try:
            data = json.loads(gj.read_text(encoding="utf-8"))
            nodes = len(data.get("nodes", []))
            links = len(data.get("links", data.get("edges", [])))
            results.append({
                "path": str(gj),
                "project": gj.parent.parent.name,
                "nodes": nodes,
                "links": links,
                "size_kb": round(gj.stat().st_size / 1024, 1),
            })
        except Exception:
            pass
    # Also include worked examples from the KG source
    for gj in (_KG_DIR / "worked").rglob("graph.json") if _KG_DIR.exists() else []:
        try:
            data = json.loads(gj.read_text(encoding="utf-8"))
            nodes = len(data.get("nodes", []))
            links = len(data.get("links", data.get("edges", [])))
            results.append({
                "path": str(gj),
                "project": f"[example] {gj.parent.name}",
                "nodes": nodes,
                "links": links,
                "size_kb": round(gj.stat().st_size / 1024, 1),
            })
        except Exception:
            pass
    return sorted(results, key=lambda r: str(r.get("project", "")))


def render_kg_status() -> str:
    installed = _is_installed()
    version = _pkg_version() if installed else "not installed"
    global_present = _GLOBAL_DIR.exists()
    kg_source_present = _KG_DIR.exists()

    graphs = _find_graph_outputs()

    lines = [
        "# Engel Knowledge Graph V2 — Status",
        "",
        f"Package installed:   {'YES (' + version + ')' if installed else 'NO'}",
        f"Source directory:    {'present — ' + str(_KG_DIR) if kg_source_present else 'not found'}",
        f"Global graph dir:    {'present — ' + str(_GLOBAL_DIR) if global_present else 'absent (~/.engel_graphify)'}",
        "",
        f"Graph outputs found: {len(graphs)}",
    ]
    if graphs:
        for g in graphs:
            lines.append(
                f"  {g['project']}: {g['nodes']} nodes, {g['links']} links"
                f" ({g['size_kb']} KB)  {g['path']}"
            )
    lines += [
        "",
        "To install:   engel graphify install",
        "To build:     cd <project> && python -m engel_graphify build .",
        "To query:     python -m engel_graphify query <graph.json> 'find god nodes'",
    ]
    return "\n".join(lines)


def render_kg_global_graph() -> str:
    if not _GLOBAL_MANIFEST.exists():
        return (
            "# Engel Knowledge Graph V2 — Global Graph\n\n"
            "No global graph found. Run 'python -m engel_graphify global add <graph.json> --repo <name>' "
            "after building a project graph."
        )
    try:
        manifest = json.loads(_GLOBAL_MANIFEST.read_text(encoding="utf-8"))
    except Exception as exc:
        return f"# Engel Knowledge Graph V2 — Global Graph\n\nManifest read error: {exc}"

    repos = manifest.get("repos", {})
    lines = [
        "# Engel Knowledge Graph V2 — Global Graph",
        "",
        f"Repos in global graph: {len(repos)}",
    ]
    for tag, info in sorted(repos.items()):
        lines.append(f"  [{tag}]  source: {info.get('source_path', '?')}")
    if _GLOBAL_GRAPH.exists():
        lines += ["", f"Global graph file: {_GLOBAL_GRAPH} ({round(_GLOBAL_GRAPH.stat().st_size / 1024, 1)} KB)"]
    return "\n".join(lines)


def render_kg_scan_workspace() -> str:
    graphs = _find_graph_outputs()
    lines = [
        "# Engel Knowledge Graph V2 — Workspace Scan",
        "",
        f"Found {len(graphs)} graph output(s) in workspace:",
        "",
    ]
    if graphs:
        for g in graphs:
            lines += [
                f"## {g['project']}",
                f"  Nodes:  {g['nodes']}",
                f"  Links:  {g['links']}",
                f"  Size:   {g['size_kb']} KB",
                f"  Path:   {g['path']}",
                "",
            ]
    else:
        lines += [
            "No engel_graphify-out/graph.json files found.",
            "Build a graph: cd <project> && python -m engel_graphify build .",
        ]
    return "\n".join(lines)


def render_kg_help() -> str:
    return "\n".join([
        "# Engel Knowledge Graph V2 — Usage",
        "",
        "engel_graphify turns any folder of code, docs, or papers into a queryable",
        "knowledge graph. It extracts symbols, builds a graph, clusters communities,",
        "and generates AI-readable reports.",
        "",
        "## Quick Start",
        "",
        "1. Install:  engel graphify install",
        "2. Build:    cd D:\\b.WorkSpace\\Engel App",
        "             python -m engel_graphify build .",
        "3. View:     open engel_graphify-out/report.md",
        "4. Export:   python -m engel_graphify export graph.json --format html",
        "",
        "## Available Commands",
        "",
        "  python -m engel_graphify build <path>     Extract & build graph",
        "  python -m engel_graphify analyze graph.json  Find god nodes, surprises",
        "  python -m engel_graphify cluster graph.json  Community detection",
        "  python -m engel_graphify export graph.json   Export to HTML/SVG/Wiki",
        "  python -m engel_graphify global add ...       Add to cross-project graph",
        "  python -m engel_graphify serve graph.json     Start local web server",
        "",
        "## Source",
        "",
        f"  {_KG_DIR}",
        "",
        "Run 'engel graphify install' to install as a Python package.",
    ])


def render_kg_install() -> str:
    """Install engel_graphify and core deps via pip (action route)."""
    if _is_installed():
        v = _pkg_version()
        return (
            f"# Engel Knowledge Graph V2 — Install\n\n"
            f"Already installed (version {v}). Nothing to do.\n\n"
            f"To build a graph of the Engel App core modules:\n"
            f"  engel graphify build engel app core\n\n"
            f"To verify deps: networkx, datasketch, rapidfuzz, tree-sitter must all be installed.\n"
            f"Run: pip show networkx datasketch rapidfuzz tree-sitter"
        )
    if not _KG_DIR.exists():
        return (
            "# Engel Knowledge Graph V2 — Install\n\n"
            f"Source directory not found: {_KG_DIR}\n"
            "Cannot install."
        )
    lines = ["# Engel Knowledge Graph V2 — Install", ""]
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-e", str(_KG_DIR),
             "--no-deps", "--quiet"],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0:
            lines += ["Install succeeded (no-deps mode).", "",
                      "To install full deps including networkx and tree-sitter:",
                      f"  pip install -e \"{_KG_DIR}\"",
                      "",
                      "Or just the core graph deps:",
                      "  pip install networkx datasketch rapidfuzz"]
        else:
            lines += ["Install failed:", "", result.stderr[:1000]]
    except Exception as exc:
        lines += [f"Install error: {exc}"]
    return "\n".join(lines)


# Dirs to exclude from scoped build (too large / not Engel source)
_EXCLUDE_DIRS = frozenset({
    "node_modules", "venv", ".venv", "__pycache__", ".git",
    "tests", "test", "dist", "build", ".tox", "site-packages",
    "engel_octogent_main", "engel_knowledge_graph_main",
    "engel_jarvis_main", "engel_git_nexus_main",
    "engel_agent_main", "engel_evolution_lab_main",
    "engel_evolution_engine_main", "engel_main",
    "engel_lan_main", "engel_ide_companion_main",
    "reports", "memory", "models", "worked",
})


def _collect_core_py_files(root: Path) -> list[Path]:
    """Walk root, skip excluded dirs, return .py files under 300KB."""
    found: list[Path] = []
    for path in root.rglob("*.py"):
        if any(part in _EXCLUDE_DIRS for part in path.parts):
            continue
        try:
            if path.stat().st_size < 300 * 1024:
                found.append(path)
        except OSError:
            pass
    return found


def render_kg_build_core() -> str:
    """Build a knowledge graph of the core Engel App Python modules."""
    if not _is_installed():
        return (
            "# Knowledge Graph V2 — Build\n\n"
            "engel_graphify not installed. Run: engel graphify install"
        )
    import sys as _sys
    _sys.path.insert(0, str(_KG_DIR))
    try:
        from engel_graphify.extract import collect_files, extract
        from engel_graphify.build import build_from_json
        import json as _json
    except ImportError as exc:
        return f"# Knowledge Graph V2 — Build\n\nImport failed: {exc}"

    out_dir = _APP_ROOT / "engel_graphify-out"
    out_dir.mkdir(exist_ok=True)
    graph_path = out_dir / "graph.json"

    paths = _collect_core_py_files(_APP_ROOT)
    if not paths:
        return "# Knowledge Graph V2 — Build\n\nNo .py files found in Engel App core."

    try:
        raw = extract(paths)
        G = build_from_json(raw)
        # Serialize
        from networkx.readwrite import json_graph as _jg
        try:
            data = _jg.node_link_data(G, edges="links")
        except TypeError:
            data = _jg.node_link_data(G)
        graph_path.write_text(_json.dumps(data, indent=2), encoding="utf-8")
        size_kb = round(graph_path.stat().st_size / 1024, 1)
        return "\n".join([
            "# Knowledge Graph V2 — Build Complete",
            "",
            f"Files processed:  {len(paths)}",
            f"Nodes extracted:  {G.number_of_nodes()}",
            f"Edges built:      {G.number_of_edges()}",
            f"Graph saved:      {graph_path} ({size_kb} KB)",
            "",
            "Next steps:",
            "  engel graphify scan workspace",
            "  engel graphify analyze workspace graph",
        ])
    except Exception as exc:
        return f"# Knowledge Graph V2 — Build Failed\n\n{exc}"


def render_kg_analyze_core() -> str:
    """Analyze the built Engel App core knowledge graph."""
    if not _is_installed():
        return "# Knowledge Graph V2 — Analyze\n\nengel_graphify not installed."

    graph_path = _APP_ROOT / "engel_graphify-out" / "graph.json"
    if not graph_path.exists():
        return (
            "# Knowledge Graph V2 — Analyze\n\n"
            "No graph found. Run: engel graphify build engel app core"
        )
    import sys as _sys
    _sys.path.insert(0, str(_KG_DIR))
    try:
        import json as _json
        from engel_graphify.build import build_from_json
        from engel_graphify.analyze import god_nodes, surprising_connections, suggest_questions
        from networkx.readwrite import json_graph as _jg

        data = _json.loads(graph_path.read_text(encoding="utf-8"))
        if "links" not in data and "edges" in data:
            data = dict(data, links=data["edges"])
        try:
            G = _jg.node_link_graph(data, edges="links")
        except TypeError:
            G = _jg.node_link_graph(data)

        lines = [
            "# Knowledge Graph V2 — Analysis",
            "",
            f"Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges",
            "",
        ]

        try:
            gods = god_nodes(G)[:8]
            lines += ["## God Nodes (highest connectivity)", ""]
            for node in gods:
                nid = node.get("id", "?") if isinstance(node, dict) else str(node)
                deg = node.get("degree", "?") if isinstance(node, dict) else "?"
                lines.append(f"  {nid}  (degree {deg})")
        except Exception as exc:
            lines.append(f"God nodes: {exc}")

        lines.append("")
        try:
            surprises = surprising_connections(G)[:5]
            lines += ["## Surprising Connections", ""]
            for conn in surprises:
                lines.append(f"  {conn}" if isinstance(conn, str) else f"  {conn}")
        except Exception as exc:
            lines.append(f"Surprising connections: {exc}")

        lines.append("")
        try:
            from engel_graphify.cluster import cluster, score_all
            communities, labels = cluster(G)
            questions = suggest_questions(G, communities, labels)[:5]
            lines += ["## Suggested Questions", ""]
            for q in questions:
                lines.append(f"  - {q}")
        except Exception as exc:
            lines.append(f"Questions (needs cluster data): {exc}")

        return "\n".join(lines)
    except Exception as exc:
        return f"# Knowledge Graph V2 — Analyze Failed\n\n{exc}"


def _load_graph_nx(graph_path: Path) -> "Any":
    """Load graph.json into a networkx graph, cached by path string."""
    import sys as _sys
    _sys.path.insert(0, str(_KG_DIR))
    import json as _json
    from networkx.readwrite import json_graph as _jg

    key = str(graph_path)
    if key in _GRAPH_CACHE:
        return _GRAPH_CACHE[key]

    data = _json.loads(graph_path.read_text(encoding="utf-8"))
    if "links" not in data and "edges" in data:
        data = dict(data, links=data["edges"])
    try:
        G = _jg.node_link_graph(data, edges="links")
    except TypeError:
        G = _jg.node_link_graph(data)
    _GRAPH_CACHE[key] = G
    return G


def render_kg_communities(payload: str = "") -> str:
    """Show community clusters in the knowledge graph.

    Payload: optional integer N — show top N communities (default 10).
    Uses the engel_graphify.cluster module for community detection.
    """
    graph_path = _APP_ROOT / "engel_graphify-out" / "graph.json"
    if not graph_path.exists():
        return (
            "# Knowledge Graph V2 — Communities\n\n"
            "No graph found. Run: engel graphify build engel app core"
        )

    try:
        G = _load_graph_nx(graph_path)
    except Exception as exc:
        return f"# Knowledge Graph V2 — Communities\n\nFailed to load graph: {exc}"

    try:
        n_top = int(payload.strip()) if payload.strip().isdigit() else 10
    except Exception:
        n_top = 10

    import sys as _sys
    _sys.path.insert(0, str(_KG_DIR))

    try:
        from engel_graphify.cluster import cluster
        communities = cluster(G)  # dict[int, list[str]]
    except Exception as exc:
        return f"# Knowledge Graph V2 — Communities\n\nCluster failed: {exc}"

    sorted_coms = sorted(communities.items(), key=lambda x: -len(x[1]))
    total_coms = len(sorted_coms)
    top = sorted_coms[:n_top]

    lines = [
        "# Knowledge Graph V2 — Communities",
        "",
        f"Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges",
        f"Communities detected: {total_coms}  (showing top {min(n_top, total_coms)})",
        "",
    ]
    for rank, (com_id, members) in enumerate(top, 1):
        unique_members = list(dict.fromkeys(members))
        top_members = sorted(unique_members, key=lambda n: -G.degree(n))[:3]
        lines.append(f"  #{rank}  size={len(unique_members)}")
        for m in top_members:
            lines.append(f"    [{G.degree(m):>3}] {str(m)[:70]}")

    lines += [
        "",
        "Search within a community:",
        "  engel graphify search <keyword>",
        "  engel graphify neighbors <node_id>",
    ]
    return "\n".join(lines)


def render_kg_search(payload: str = "") -> str:
    """Search graph nodes by keyword and return top matches sorted by degree.

    Payload: keyword to search in node IDs (case-insensitive substring).
    Returns top 20 matches with degree and file info.
    """
    query = payload.strip()
    if not query:
        return (
            "# Knowledge Graph V2 — Search\n\n"
            "Provide a keyword to search for.\n"
            "Usage: engel graphify search <keyword>\n"
            "Example: engel graphify search route"
        )

    graph_path = _APP_ROOT / "engel_graphify-out" / "graph.json"
    if not graph_path.exists():
        return (
            "# Knowledge Graph V2 — Search\n\n"
            "No graph found. Run: engel graphify build engel app core"
        )

    try:
        G = _load_graph_nx(graph_path)
    except Exception as exc:
        return f"# Knowledge Graph V2 — Search\n\nFailed to load graph: {exc}"

    q = query.lower()
    matches = [(n, G.degree(n)) for n in G.nodes() if q in str(n).lower()]

    if not matches:
        return (
            f"# Knowledge Graph V2 — Search: {query!r}\n\n"
            f"No nodes found matching {query!r} in {G.number_of_nodes()} nodes.\n\n"
            "Try a shorter or different keyword."
        )

    matches.sort(key=lambda x: -x[1])
    top = matches[:20]

    lines = [
        f"# Knowledge Graph V2 — Search: {query!r}",
        "",
        f"Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges",
        f"Matches: {len(matches)} (showing top {len(top)})",
        "",
        f"  {'Node ID':<60} {'Degree':>6}",
        "  " + "-" * 68,
    ]
    for node_id, deg in top:
        display = str(node_id)
        if len(display) > 60:
            display = "..." + display[-57:]
        lines.append(f"  {display:<60} {deg:>6}")

    if len(matches) > 20:
        lines += ["", f"  ... and {len(matches) - 20} more matches."]

    lines += [
        "",
        "To explore neighbors of a node:",
        f"  engel graphify neighbors <node_id>",
    ]
    return "\n".join(lines)


def render_kg_neighbors(payload: str = "") -> str:
    """Show neighbors of a node in the knowledge graph.

    Payload: exact node ID (or prefix) to look up.
    """
    target = payload.strip()
    if not target:
        return (
            "# Knowledge Graph V2 — Neighbors\n\n"
            "Provide a node ID to look up.\n"
            "Usage: engel graphify neighbors <node_id>"
        )

    graph_path = _APP_ROOT / "engel_graphify-out" / "graph.json"
    if not graph_path.exists():
        return (
            "# Knowledge Graph V2 — Neighbors\n\n"
            "No graph found. Run: engel graphify build engel app core"
        )

    try:
        G = _load_graph_nx(graph_path)
    except Exception as exc:
        return f"# Knowledge Graph V2 — Neighbors\n\nFailed to load graph: {exc}"

    # Exact match first, then prefix match
    node = None
    if target in G:
        node = target
    else:
        t_lower = target.lower()
        candidates = [n for n in G.nodes() if str(n).lower().startswith(t_lower)]
        if len(candidates) == 1:
            node = candidates[0]
        elif len(candidates) > 1:
            opts = "\n".join(f"  {c}" for c in sorted(candidates)[:10])
            return (
                f"# Knowledge Graph V2 — Neighbors\n\n"
                f"Ambiguous prefix {target!r}. Matches:\n{opts}"
            )

    if node is None:
        return (
            f"# Knowledge Graph V2 — Neighbors\n\n"
            f"Node {target!r} not found.\n\n"
            "Use 'engel graphify search <keyword>' to find node IDs."
        )

    neighbors = sorted(G.neighbors(node), key=lambda n: -G.degree(n))
    preds = sorted(G.predecessors(node), key=lambda n: -G.degree(n)) if G.is_directed() else []

    lines = [
        f"# Knowledge Graph V2 — Neighbors: {node}",
        "",
        f"Degree: {G.degree(node)}",
        f"Out-neighbors: {len(neighbors)}",
    ]
    if preds:
        lines.append(f"In-neighbors:  {len(preds)}")

    lines += ["", f"  {'Neighbor':<60} {'Degree':>6}", "  " + "-" * 68]
    for n in neighbors[:20]:
        display = str(n)
        if len(display) > 60:
            display = "..." + display[-57:]
        lines.append(f"  {display:<60} {G.degree(n):>6}")
    if len(neighbors) > 20:
        lines.append(f"  ... and {len(neighbors) - 20} more.")

    if preds:
        lines += ["", "In-neighbors (top 10):"]
        for n in preds[:10]:
            lines.append(f"  {str(n)[:60]}")

    return "\n".join(lines)
