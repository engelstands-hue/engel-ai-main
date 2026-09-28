#!/usr/bin/env python3
"""Verify Engel AI Main's UI surface has no structurally dead controls.

Born from the 2026-07-28 window/option audit ("dead end buttons, options that
don't work, going in circles"). Static guarantees enforced here:

  1. no duplicate section ids (a duplicate is UNREACHABLE navigation because
     _sectionIndexById returns the first match);
  2. every section id has a builder;
  3. every rustCommands.firstWhere(...) key exists in the catalog (a missing
     key throws StateError at runtime = a button that crashes the page);
  4. no button is wired with onPressed: null or an empty handler;
  5. commands whose subcommand requires operator input declare needsText;
  6. the everyday navigation stays intentionally small while every advanced
     owner remains searchable and can be revealed explicitly.
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "engel_flutter_main" / "lib" / "main.dart"

# Subcommands that read operator-supplied input; wiring them argument-less
# produces a cryptic parse failure instead of a result.
INPUT_REQUIRED_KEYS = {"remote_workers_return_result"}

CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail and not ok else ""))


def balanced_region(text: str, start: int, opening: str, closing: str) -> tuple[int, int] | None:
    """Return the balanced region beginning at *start*, including delimiters."""
    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                return start, index + 1
    return None


def main() -> int:
    text = MAIN.read_text(encoding="utf-8", errors="replace")

    sections = re.findall(
        r"SectionSpec\(\s*'([a-z0-9_]+)',\s*'([^']+)',\s*Icons\.[\w.]+,\s*'([^']+)'",
        text)
    ids = [s for s, _label, _group in sections]
    dupes = [s for s, count in Counter(ids).items() if count > 1]
    check("no_duplicate_section_ids", not dupes, str(dupes))
    # (2026-07-28 usability consolidation) 52 destinations now live inside a
    # deliberately small set of canonical windows. The band guards against
    # both accidental mass-deletion and a return to sidebar sprawl.
    check("canonical_sections_present", 8 <= len(sections) <= 16,
          f"{len(sections)} sections")

    essential_block = re.search(
        r"const essentialSectionIds = <String>\{(.*?)\n\};", text, re.S)
    essentials = (set(re.findall(r"'([a-z0-9_]+)'", essential_block.group(1)))
                  if essential_block else set())
    check("essential_navigation_present", bool(essential_block))
    check("essential_navigation_is_small", 4 <= len(essentials) <= 7,
          f"{len(essentials)} essentials")
    check("essentials_are_canonical_sections", essentials <= set(ids),
          str(sorted(essentials - set(ids))))
    check("advanced_navigation_has_explicit_toggle",
          "toggle-advanced-navigation" in text)

    builders = set()
    for pattern in (r"case\s+'([a-z0-9_]+)'\s*:\s*return\s+_\w+\(",
                    r"'([a-z0-9_]+)'\s*=>\s*_\w+\("):
        builders.update(re.findall(pattern, text))
    missing_builder = sorted(set(ids) - builders)
    check("every_section_has_builder", not missing_builder, str(missing_builder[:8]))

    catalog = dict(re.findall(r"RustCommand\(\s*'([a-z0-9_]+)',\s*'([^']*)'", text))
    referenced = set(re.findall(r"c\.key\s*==\s*'([a-z0-9_]+)'", text))
    missing_keys = sorted(referenced - set(catalog))
    check("no_missing_command_keys", not missing_keys, str(missing_keys[:8]))

    # A list can contain valid command keys and still crash when a later card
    # indexes past its end. This caught the active System -> Launch page, where
    # six cards referenced a three-command list even though every key resolved.
    indexed_command_overflows: list[str] = []
    widget_starts = re.finditer(
        r"\bWidget\s+(_[A-Za-z0-9_]+)\s*\([^)]*\)\s*\{", text
    )
    for widget_match in widget_starts:
        widget_name = widget_match.group(1)
        body_region = balanced_region(text, widget_match.end() - 1, "{", "}")
        if body_region is None:
            continue
        body = text[body_region[0]:body_region[1]]
        for list_match in re.finditer(
            r"\bfinal\s+([A-Za-z_]\w*)\s*=\s*\[", body
        ):
            list_name = list_match.group(1)
            list_region = balanced_region(body, list_match.end() - 1, "[", "]")
            if list_region is None:
                continue
            list_blob = body[list_region[0]:list_region[1]]
            command_count = len(
                re.findall(r"rustCommands\.firstWhere|RustCommand\s*\(", list_blob)
            )
            if command_count == 0:
                continue
            later_body = body[list_region[1]:]
            indexes = [
                int(value)
                for value in re.findall(
                    rf"\b{re.escape(list_name)}\s*\[\s*(\d+)\s*\]",
                    later_body,
                )
            ]
            if indexes and max(indexes) >= command_count:
                indexed_command_overflows.append(
                    f"{widget_name}.{list_name}: {command_count} commands, index {max(indexes)}"
                )
    check(
        "no_indexed_command_list_out_of_bounds",
        not indexed_command_overflows,
        "; ".join(indexed_command_overflows[:8]),
    )

    null_handlers = re.findall(r"onPressed:\s*null\s*,", text)
    check("no_null_onpressed", not null_handlers, f"{len(null_handlers)} found")
    empty_handlers = re.findall(r"on(?:Pressed|Tap):\s*\(\)\s*(?:async\s*)?\{\s*\}", text)
    check("no_empty_handlers", not empty_handlers, f"{len(empty_handlers)} found")

    # ---- 2026-07-28 window consolidation invariants ----------------------
    merge_block = re.search(
        r"const sectionMergeChildren = <String, List<String>>\{(.*?)\n\};",
        text, re.S)
    check("merge_map_present", bool(merge_block))
    merged_children: dict[str, list[str]] = {}
    if merge_block:
        for owner, body in re.findall(r"'([a-z0-9_]+)':\s*\[(.*?)\]",
                                      merge_block.group(1), re.S):
            merged_children[owner] = re.findall(r"'([a-z0-9_]+)'", body)

    labels = set()
    label_block = re.search(
        r"const sectionChildLabels = <String, String>\{(.*?)\n\};", text, re.S)
    if label_block:
        labels = set(re.findall(r"'([a-z0-9_]+)':", label_block.group(1)))

    pages = set(re.findall(r"'([a-z0-9_]+)'\s*=>\s*_\w+\(\)", text))

    all_children = [c for kids in merged_children.values() for c in kids]
    check("every_owner_is_a_section", set(merged_children) <= set(ids),
          str(sorted(set(merged_children) - set(ids))))
    check("owner_is_first_child",
          all(kids and kids[0] == owner for owner, kids in merged_children.items()))
    missing_labels = sorted(set(all_children) - labels)
    check("every_merged_page_has_a_tab_label", not missing_labels,
          str(missing_labels))
    missing_pages = sorted(set(all_children) - pages)
    check("every_merged_page_still_renders", not missing_pages,
          str(missing_pages))
    # A merged child must NOT keep its own sidebar entry (that was the old
    # 51-window sprawl); it is reachable through its owner's tab strip.
    leaked = sorted((set(all_children) - set(merged_children)) & set(ids))
    check("merged_children_have_no_duplicate_window", not leaked, str(leaked))
    # The original sidebar filter exposed an ``ownedMatch`` boolean. The
    # destination-level search now builds explicit hits so the visible result
    # can say "Connection Help" instead of only showing its Devices owner.
    search_indexes_children = (
        "List<_SectionSearchHit> _searchHits(String query)" in text
        and "for (final child in sectionMergeChildren[owner.id]" in text
        and "targetId: child" in text
        and "widget.onSelected(hit.targetId)" in text
    )
    check(
        "search_matches_merged_children",
        "ownedMatch" in text or search_indexes_children,
    )
    check("selection_maps_child_to_owner",
          "sectionMergeOwner[resolvedId] ?? resolvedId" in text)

    for key in sorted(INPUT_REQUIRED_KEYS):
        entry = re.search(
            r"RustCommand\(\s*'" + re.escape(key) + r"'.*?\)\s*,\s*\n",
            text, re.S)
        blob = entry.group(0) if entry else ""
        check(f"input_required_declares_needstext[{key}]",
              bool(blob) and "needsText: true" in blob)

    failed = [name for name, ok, _ in CHECKS if not ok]
    print(f"\n{len(CHECKS) - len(failed)}/{len(CHECKS)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
