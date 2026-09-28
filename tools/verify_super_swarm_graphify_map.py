from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUPER_SWARM_SOURCE = ROOT / "tools" / "engel_super_swarm_hive_3d_scaffold.py"
SUPER_SWARM_SPEC = ROOT / "EngelSuperSwarmHive3D.spec"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    source = SUPER_SWARM_SOURCE.read_text(encoding="utf-8")
    spec = SUPER_SWARM_SPEC.read_text(encoding="utf-8")
    ast.parse(source)

    markers = [
        "class GraphifyKnowledgeMapWidget",
        "class GraphifyKnowledgeMapTab",
        "GRAPHIFY_GRAPH_RELATIVE_PATH",
        "Graphify Map",
        "Long Term Memory",
        "MAP CONNECTS",
        "group_link_counts",
        "node_adjacency",
        "_draw_group_connections",
        "_relation_color",
        "dock.setVisible(not (on_super_swarm and on_graphify))",
    ]
    for marker in markers:
        require(marker in source, f"missing Super Swarm Graphify marker: {marker}")

    require(
        (
            "engel_graphify-out\\\\graph.json" in spec
            or "engel_graphify-out/graph.json" in spec
        )
        and "('engel_graphify-out', 'engel_graphify-out')" not in spec,
        "EngelSuperSwarmHive3D.spec must bundle only engel_graphify-out/graph.json, not the full Graphify cache.",
    )

    graph_path = ROOT / "engel_graphify-out" / "graph.json"
    require(graph_path.exists(), "local Graphify graph.json is missing.")
    require(graph_path.stat().st_size > 1024 * 1024, "local Graphify graph.json is unexpectedly small.")

    print("SUPER_SWARM_GRAPHIFY_MAP_VERIFICATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
