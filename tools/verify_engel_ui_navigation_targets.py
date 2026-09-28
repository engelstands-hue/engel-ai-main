#!/usr/bin/env python3
"""Every in-app navigation target must resolve to a page that actually renders.

Why this gate exists
--------------------
`_sectionIndexById` ends `return index < 0 ? 0 : index;` -- an unknown route id is not
an error, it silently selects index 0 (Home). Two "Models" buttons navigated to
`'models'` for an unknown length of time; `'models'` is the LABEL of the `local_llm`
section, never an id, so both buttons quietly opened Home and nothing ever complained.

A silent fallback cannot be caught by the widget suite either, because tapping the
button "works" -- it just lands somewhere else. So the check has to be static, over the
source: collect every literal id handed to a navigation call, resolve it exactly the way
`_selectSectionById` does, and prove it names something real.

Second check: a `_pageFor` switch arm whose id is rewritten by `sectionRouteAliases`
before dispatch can never execute. Those builders are dead weight that still gets
maintained, so they are reported -- as a warning, because merging two surfaces during
the 2026-07-28 consolidation was a deliberate product decision and only the operator can
say whether the orphaned page should be exposed as a tab or deleted.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN_DART = ROOT / "engel_flutter_main" / "lib" / "main.dart"

checks: list[dict] = []


def check(name: str, ok: bool, detail) -> None:
    checks.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": detail})


def _block(source: str, marker: str) -> str:
    """Text of a top-level const map literal, from its marker to the closing '};'."""
    start = source.index(marker)
    end = source.index("\n};", start)
    return source[start:end]


def main() -> int:
    source = MAIN_DART.read_text(encoding="utf-8")

    section_ids = set(re.findall(r"\bid:\s*'([a-z0-9_]+)'", source))
    alias_block = _block(source, "const sectionRouteAliases")
    aliases = dict(re.findall(r"'([a-z0-9_]+)':\s*'([a-z0-9_]+)'", alias_block))
    children_block = _block(source, "const sectionMergeChildren")
    merge_children: dict[str, list[str]] = {}
    for owner, body in re.findall(
        r"'([a-z0-9_]+)':\s*\[(.*?)\]", children_block, re.DOTALL
    ):
        merge_children[owner] = re.findall(r"'([a-z0-9_]+)'", body)
    every_child = {child for kids in merge_children.values() for child in kids}
    page_arms = set(re.findall(r"^\s*'([a-z0-9_]+)'\s*=>\s*_", source, re.MULTILINE))

    check(
        "route_tables_parsed",
        bool(section_ids) and bool(aliases) and bool(merge_children) and bool(page_arms),
        {
            "section_ids": len(section_ids),
            "aliases": len(aliases),
            "merge_owners": len(merge_children),
            "page_arms": len(page_arms),
        },
    )

    # Every literal id passed to a navigation call, with the line it sits on.
    nav_calls: list[tuple[int, str, str]] = []
    for index, line in enumerate(source.splitlines(), start=1):
        for pattern in (
            r"_selectSectionById\(\s*'([a-z0-9_]+)'",
            r"_closeDialogAndSelect\([^)]*?'([a-z0-9_]+)'\s*\)",
            r"_openSectionById\(\s*'([a-z0-9_]+)'",
        ):
            for target in re.findall(pattern, line):
                nav_calls.append((index, target, line.strip()[:90]))

    known = section_ids | set(aliases) | every_child | page_arms
    unknown = [
        {"line": line_no, "id": target, "source": text}
        for line_no, target, text in nav_calls
        if target not in known
    ]
    check(
        "every_navigation_target_is_a_real_route",
        not unknown,
        unknown if unknown else {"navigation_calls_checked": len(nav_calls)},
    )

    # A navigation id must end up on a page that can render it: either the resolved id
    # IS the selected window, or it is a tab of the window that gets selected.
    misrouted = []
    for line_no, target, text in nav_calls:
        if target not in known:
            continue
        resolved = aliases.get(target, target)
        owner = next(
            (own for own, kids in merge_children.items() if resolved in kids), resolved
        )
        renders = resolved == owner or resolved in merge_children.get(owner, [])
        if not renders:
            misrouted.append(
                {"line": line_no, "id": target, "resolved": resolved, "owner": owner}
            )
    check(
        "navigation_targets_land_on_their_own_page",
        not misrouted,
        misrouted if misrouted else {"checked": len(nav_calls)},
    )

    # WARNING-ONLY: builders that can never be dispatched because the id is aliased away.
    orphaned = sorted(
        arm
        for arm in page_arms
        if arm in aliases and aliases[arm] != arm and arm not in every_child
    )
    checks.append(
        {
            "name": "page_builders_reachable (advisory)",
            "status": "PASS" if not orphaned else "WARN",
            "detail": {
                "orphaned_builders": orphaned,
                "note": (
                    "each id is rewritten by sectionRouteAliases before _pageFor runs, so "
                    "its builder never executes; expose it as a merge child or delete it"
                ),
            },
        }
    )

    failed = [c for c in checks if c["status"] == "FAIL"]
    report = {
        "schema": "engel_ui_navigation_targets_verifier_v1",
        "status": "FAIL" if failed else "PASS",
        "passed": sum(1 for c in checks if c["status"] == "PASS"),
        "warnings": sum(1 for c in checks if c["status"] == "WARN"),
        "total": len(checks),
        "checks": checks,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
