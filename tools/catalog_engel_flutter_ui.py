#!/usr/bin/env python3
"""Catalog Engel AI Main's active Flutter windows, tabs, and controls.

This is a source-of-truth usability inventory, not a feature-claim scraper. It
reads the canonical navigation and page switch from ``main.dart``, limits the
catalog to routes an operator can actually open, and records how each inline
control is backed: navigation, a registered Rust command, a local callback, or
an input/disclosure. The Markdown and JSON reports are intentionally stable so
future UI reviews can diff them.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "engel_flutter_main" / "lib" / "main.dart"
DEFAULT_REPORT_DIR = ROOT / "reports" / "codex_bridge"

CONTROL_CALLS = (
    "_ControlAction",
    "_quickActionCard",
    "_homeQuickControl",
    "_homeShortcutRow",
    "FilledButton.icon",
    "FilledButton",
    "OutlinedButton.icon",
    "OutlinedButton",
    "ElevatedButton.icon",
    "ElevatedButton",
    "TextButton.icon",
    "TextButton",
    "IconButton",
    "ActionChip",
    "ChoiceChip",
    "FilterChip",
    "SwitchListTile",
    "CheckboxListTile",
    "ExpansionTile",
    "TextField",
    "DropdownButton",
    "DropdownButtonFormField",
    "Slider",
    "InkWell",
    "GestureDetector",
    "ListTile",
)

COMPONENT_STATES = {
    "_aiTermsPage": "_AiTermsGridState",
    "_nmapReconPage": "_NmapReconGridState",
    "_ragLabPage": "_RagVisualLabState",
}

NON_PRIMARY_HELPERS = {"_outputPanel", "_catalogPanel", "_advancedCommandSearch"}


def balanced_region(
    text: str, start: int, opening: str = "{", closing: str = "}"
) -> tuple[int, int] | None:
    depth = 0
    quote = ""
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
            continue
        if char in ("'", '"'):
            quote = char
        elif char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                return start, index + 1
    return None


def constant_block(source: str, declaration: str) -> str:
    match = re.search(re.escape(declaration) + r"\s*\{", source)
    if not match:
        return ""
    region = balanced_region(source, match.end() - 1)
    return source[region[0] : region[1]] if region else ""


def method_body(source: str, method: str) -> tuple[str, int]:
    match = re.search(
        rf"\bWidget\s+{re.escape(method)}\s*\([^)]*\)\s*\{{", source
    )
    if not match:
        return "", 0
    region = balanced_region(source, match.end() - 1)
    if not region:
        return "", 0
    line = source.count("\n", 0, match.start()) + 1
    return source[region[0] : region[1]], line


def class_body(source: str, class_name: str) -> tuple[str, int]:
    match = re.search(rf"\bclass\s+{re.escape(class_name)}\b[^{{]*\{{", source)
    if not match:
        return "", 0
    region = balanced_region(source, match.end() - 1)
    if not region:
        return "", 0
    line = source.count("\n", 0, match.start()) + 1
    return source[region[0] : region[1]], line


def page_segments(source: str, builder: str) -> list[tuple[str, str, int]]:
    """Return the active builder plus reachable Widget helpers/components."""
    body, line = method_body(source, builder)
    if not body:
        return []
    segments = [(builder, body, line)]
    seen_methods = {builder}
    queue = [body]
    while queue:
        current = queue.pop(0)
        for helper in re.findall(r"(?<![A-Za-z0-9_])(_[a-z][A-Za-z0-9_]*)\s*\(", current):
            if helper in seen_methods:
                continue
            helper_body, helper_line = method_body(source, helper)
            if not helper_body:
                continue
            seen_methods.add(helper)
            segments.append((helper, helper_body, helper_line))
            queue.append(helper_body)

    root_state = COMPONENT_STATES.get(builder)
    if root_state:
        seen_classes: set[str] = set()
        class_queue = [root_state]
        while class_queue:
            name = class_queue.pop(0)
            if name in seen_classes:
                continue
            component_body, component_line = class_body(source, name)
            if not component_body:
                continue
            seen_classes.add(name)
            segments.append((name, component_body, component_line))
            for child in re.findall(
                r"(?<![A-Za-z0-9_])(_[A-Z][A-Za-z0-9_]*)\s*\(", component_body
            ):
                if child not in seen_classes:
                    class_queue.append(child)
    return segments


def invocation_regions(body: str, call: str) -> list[tuple[int, int, str]]:
    pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(call)}(?:<[^>]+>)?\s*\(")
    regions: list[tuple[int, int, str]] = []
    for match in pattern.finditer(body):
        open_index = body.find("(", match.start())
        region = balanced_region(body, open_index, "(", ")")
        if region:
            regions.append((match.start(), region[1], body[region[0] : region[1]]))
    return regions


def invocation_blocks(body: str, call: str) -> list[str]:
    return [block for _, _, block in invocation_regions(body, call)]


def first_literal(block: str, field: str) -> str:
    patterns = (
        rf"\b{re.escape(field)}\s*:\s*(?:const\s+)?['\"]([^'\"]+)['\"]",
        rf"\b{re.escape(field)}\s*:\s*(?:const\s+)?Text\(\s*['\"]([^'\"]+)['\"]",
    )
    for pattern in patterns:
        match = re.search(pattern, block, re.S)
        if match:
            return match.group(1).replace("\n", " ").strip()
    return ""


def control_label(call: str, block: str, key: str) -> str:
    fields = ["title", "label", "tooltip", "hintText", "semanticLabel"]
    if call in {
        "FilledButton.icon",
        "FilledButton",
        "OutlinedButton.icon",
        "OutlinedButton",
        "ElevatedButton.icon",
        "ElevatedButton",
        "TextButton.icon",
        "TextButton",
    }:
        fields = ["label", "tooltip"]
    for field in fields:
        value = first_literal(block, field)
        if value:
            return value
    text_match = re.search(r"\bText\(\s*['\"]([^'\"]+)['\"]", block, re.S)
    if text_match:
        return text_match.group(1).replace("\n", " ").strip()
    return key or "dynamic label"


def command_lists(body: str) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for match in re.finditer(r"\bfinal\s+([A-Za-z_]\w*)\s*=\s*\[", body):
        region = balanced_region(body, match.end() - 1, "[", "]")
        if not region:
            continue
        blob = body[region[0] : region[1]]
        keys = re.findall(r"c\.key\s*==\s*['\"]([a-z0-9_]+)['\"]", blob)
        if keys:
            result[match.group(1)] = keys
    return result


def parse_control(call: str, block: str, lists: dict[str, list[str]]) -> dict[str, Any]:
    key_match = re.search(r"(?:const\s+)?Key\(\s*['\"]([^'\"]+)['\"]", block)
    key = key_match.group(1) if key_match else ""
    label = control_label(call, block, key)
    command_keys = re.findall(r"_commandByKey\(\s*['\"]([a-z0-9_]+)['\"]", block)
    command_keys += re.findall(r"c\.key\s*==\s*['\"]([a-z0-9_]+)['\"]", block)
    command_keys += re.findall(
        r"\bcommands\s*\[\s*['\"]([a-z0-9_]+)['\"]\s*\]", block
    )
    for list_name, index_text in re.findall(r"\b([A-Za-z_]\w*)\s*\[\s*(\d+)\s*\]", block):
        index = int(index_text)
        if list_name in lists and index < len(lists[list_name]):
            command_keys.append(lists[list_name][index])
    navigation = re.findall(
        r"(?:_selectSectionById|(?:widget\.)?onOpenSurface)\(\s*['\"]([a-z0-9_]+)['\"]",
        block,
    )
    callbacks = [
        name
        for name in re.findall(r"\b(_[a-z][A-Za-z0-9_]*)\s*\(", block)
        if name
        not in {
            "_commandByKey",
            "_runRust",
            "_selectSectionById",
            "_ControlAction",
            "_quickActionCard",
        }
    ]
    callbacks += re.findall(
        r"on(?:Pressed|Tap|Changed|Submitted|Selected)\s*:\s*(_[A-Za-z0-9_]+)\b",
        block,
    )
    callback = callbacks[-1] if callbacks else ""
    has_handler = bool(
        re.search(
            r"on(?:Pressed|Tap|Changed|Submitted|Selected)\s*:\s*(?!null\b)",
            block,
        )
    )

    if call == "ExpansionTile":
        backing = "disclosure"
    elif call in {
        "TextField",
        "DropdownButton",
        "DropdownButtonFormField",
        "Slider",
        "SwitchListTile",
        "CheckboxListTile",
    }:
        backing = "input"
    elif command_keys:
        backing = "rust_command"
    elif navigation:
        backing = "navigation"
    elif callback:
        backing = "local_callback"
    elif has_handler:
        backing = "local_callback"
    else:
        backing = "unclear"

    literal_null = bool(
        re.search(r"on(?:Pressed|Tap|Changed|Submitted)\s*:\s*null\s*[,)]", block)
    )
    if call == "ExpansionTile":
        command_keys = []
        navigation = []
        callback = ""
    return {
        "type": call,
        "label": label,
        "key": key,
        "backing": backing,
        "command_keys": list(dict.fromkeys(command_keys)),
        "navigation_targets": list(dict.fromkeys(navigation)),
        "callback": callback,
        "has_handler": has_handler,
        "literal_null": literal_null,
    }


def parse_catalog(source: str) -> dict[str, Any]:
    sections_match = re.search(
        r"List<SectionSpec>\s+get\s+_sections\s*=>\s*const\s*\[(.*?)\n\s*\];",
        source,
        re.S,
    )
    sections_blob = sections_match.group(1) if sections_match else ""
    sections = [
        {"id": section_id, "label": label, "group": group}
        for section_id, label, group in re.findall(
            r"SectionSpec\(\s*['\"]([a-z0-9_]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*,\s*Icons\.[\w.]+\s*,\s*['\"]([^'\"]+)['\"]",
            sections_blob,
            re.S,
        )
    ]

    merge_blob = constant_block(source, "const sectionMergeChildren = <String, List<String>>")
    merge_children: dict[str, list[str]] = {}
    for owner, children_blob in re.findall(
        r"['\"]([a-z0-9_]+)['\"]\s*:\s*\[(.*?)\]", merge_blob, re.S
    ):
        merge_children[owner] = re.findall(r"['\"]([a-z0-9_]+)['\"]", children_blob)

    labels_blob = constant_block(source, "const sectionChildLabels = <String, String>")
    labels = dict(
        re.findall(
            r"['\"]([a-z0-9_]+)['\"]\s*:\s*['\"]([^'\"]+)['\"]",
            labels_blob,
        )
    )
    page_map = dict(
        re.findall(r"['\"]([a-z0-9_]+)['\"]\s*=>\s*(_[A-Za-z0-9_]+)\(\)", source)
    )
    command_keys = set(
        re.findall(r"RustCommand\(\s*['\"]([a-z0-9_]+)['\"]", source)
    )

    windows: list[dict[str, Any]] = []
    issues: list[dict[str, str]] = []
    backing_counts: Counter[str] = Counter()
    total_controls = 0
    for section in sections:
        owner = section["id"]
        page_ids = merge_children.get(owner, [owner])
        pages: list[dict[str, Any]] = []
        for page_id in page_ids:
            builder = page_map.get(page_id, "")
            segments = page_segments(source, builder) if builder else []
            body = segments[0][1] if segments else ""
            source_line = segments[0][2] if segments else 0
            controls: list[dict[str, Any]] = []
            for origin, segment, _origin_line in segments:
                lists = command_lists(segment)
                hidden_regions = [
                    (start, end)
                    for start, end, _ in invocation_regions(segment, "ExpansionTile")
                ]
                for call in CONTROL_CALLS:
                    for start, _end, block in invocation_regions(segment, call):
                        control = parse_control(call, block, lists)
                        if call in {"InkWell", "GestureDetector", "ListTile"} and not control[
                            "has_handler"
                        ]:
                            continue
                        control["origin"] = origin
                        control["initially_hidden"] = any(
                            hidden_start <= start < hidden_end
                            for hidden_start, hidden_end in hidden_regions
                        )
                        signature = (
                            control["type"],
                            control["key"],
                            control["label"],
                        )
                        if signature not in {
                            (row["type"], row["key"], row["label"])
                            for row in controls
                        }:
                            controls.append(control)
            for control in controls:
                backing_counts[control["backing"]] += 1
                total_controls += 1
                for command_key in control["command_keys"]:
                    if command_key not in command_keys:
                        issues.append(
                            {
                                "severity": "error",
                                "page": page_id,
                                "control": control["label"],
                                "issue": f"unregistered command key: {command_key}",
                            }
                        )
                if control["literal_null"]:
                    issues.append(
                        {
                            "severity": "error",
                            "page": page_id,
                            "control": control["label"],
                            "issue": "literal null interaction handler",
                        }
                    )
                if control["backing"] == "unclear":
                    issues.append(
                        {
                            "severity": "error",
                            "page": page_id,
                            "control": control["label"],
                            "issue": "interactive control has no identifiable backing",
                        }
                    )

            screenshot_count = sum(
                len(re.findall(r"_ScreenshotCard\s*\(", segment))
                for _, segment, _ in segments
            )
            reference_screenshot_count = sum(
                first_literal(block, "title").lower().startswith(("imported", "reference"))
                or " reference" in first_literal(block, "title").lower()
                for _, segment, _ in segments
                for block in invocation_blocks(segment, "_ScreenshotCard")
            )
            primary_action_count = sum(
                control["type"]
                in {
                    "_ControlAction",
                    "_quickActionCard",
                    "_homeQuickControl",
                    "_homeShortcutRow",
                    "FilledButton.icon",
                    "OutlinedButton.icon",
                    "ElevatedButton.icon",
                    "TextButton.icon",
                    "IconButton",
                    "ActionChip",
                }
                and control["origin"] not in NON_PRIMARY_HELPERS
                and not control["initially_hidden"]
                for control in controls
            )
            usability_flags: list[str] = []
            if reference_screenshot_count:
                usability_flags.append(
                    f"{reference_screenshot_count} imported/reference screenshot(s)"
                )
            if re.search(r"['\"][^'\"\r\n]*Workbench[^'\"\r\n]*['\"]", body):
                usability_flags.append("internal 'Workbench' wording")
            if primary_action_count > 12:
                usability_flags.append(f"dense: {primary_action_count} inline actions")
            if not body:
                usability_flags.append("builder source missing")

            pages.append(
                {
                    "id": page_id,
                    "label": labels.get(page_id, section["label"]),
                    "builder": builder,
                    "source_line": source_line,
                    "control_count": len(controls),
                    "primary_action_count": primary_action_count,
                    "screenshot_count": screenshot_count,
                    "reference_screenshot_count": reference_screenshot_count,
                    "usability_flags": usability_flags,
                    "controls": controls,
                }
            )
        windows.append({**section, "pages": pages})

    return {
        "schema": "engel_flutter_whole_ui_catalog_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": str(MAIN),
        "window_count": len(windows),
        "page_count": sum(len(window["pages"]) for window in windows),
        "inline_control_count": total_controls,
        "backing_counts": dict(sorted(backing_counts.items())),
        "registered_rust_command_count": len(command_keys),
        "issues": issues,
        "windows": windows,
        "scope_note": (
            "Controls declared in active page builders, reachable Widget helpers, and "
            "the component trees for AI Terms, Nmap, and RAG Lab are cataloged. Shared "
            "shell controls and controls created inside invoked dialogs remain covered "
            "by Flutter interaction tests and the UI surface integrity verifier."
        ),
    }


def markdown_report(catalog: dict[str, Any]) -> str:
    lines = [
        "# Engel AI Main Whole-UI Catalog",
        "",
        f"Generated: `{catalog['generated_at_utc']}`",
        "",
        "## Coverage",
        "",
        f"- Active windows: **{catalog['window_count']}**",
        f"- Active tabs/pages: **{catalog['page_count']}**",
        f"- Inline controls cataloged: **{catalog['inline_control_count']}**",
        f"- Registered Rust commands: **{catalog['registered_rust_command_count']}**",
        f"- Backing types: `{json.dumps(catalog['backing_counts'], sort_keys=True)}`",
        "",
        catalog["scope_note"],
        "",
        "## Active windows and pages",
        "",
        "| Window | Tab/page | Builder | Controls | Usability flags |",
        "|---|---|---|---:|---|",
    ]
    for window in catalog["windows"]:
        for page in window["pages"]:
            flags = "; ".join(page["usability_flags"]) or "none"
            lines.append(
                f"| {window['label']} | {page['label']} (`{page['id']}`) | "
                f"`{page['builder']}` L{page['source_line']} | {page['control_count']} | {flags} |"
            )

    lines += ["", "## Controls by page", ""]
    for window in catalog["windows"]:
        for page in window["pages"]:
            lines += [
                f"### {window['label']} → {page['label']}",
                "",
                f"Route: `{page['id']}` · Builder: `{page['builder']}` · "
                f"Source line: {page['source_line']}",
                "",
            ]
            if not page["controls"]:
                lines += ["No inline interactive controls detected.", ""]
                continue
            lines += [
                "| Control | Type | Initially visible | Source | Key | Backing | Target |",
                "|---|---|---|---|---|---|---|",
            ]
            for control in page["controls"]:
                target = ", ".join(control["command_keys"])
                target = target or ", ".join(control["navigation_targets"])
                target = target or control["callback"] or "—"
                label = control["label"].replace("|", "\\|")
                lines.append(
                    f"| {label} | `{control['type']}` | "
                    f"{'no' if control['initially_hidden'] else 'yes'} | "
                    f"`{control['origin']}` | "
                    f"`{control['key'] or '—'}` | {control['backing']} | `{target}` |"
                )
            lines.append("")

    lines += ["## Structural issues", ""]
    if catalog["issues"]:
        for issue in catalog["issues"]:
            lines.append(
                f"- **{issue['severity'].upper()}** `{issue['page']}` / "
                f"{issue['control']}: {issue['issue']}"
            )
    else:
        lines.append("No unresolved command keys or literal-null handlers were found.")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    args = parser.parse_args()

    source = MAIN.read_text(encoding="utf-8", errors="replace")
    catalog = parse_catalog(source)
    args.report_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.report_dir / "ENGEL_UI_WHOLE_CATALOG.json"
    markdown_path = args.report_dir / "ENGEL_UI_WHOLE_CATALOG.md"
    json_path.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(markdown_report(catalog), encoding="utf-8")
    print(
        "ENGEL_UI_WHOLE_CATALOG_PASS "
        f"windows={catalog['window_count']} pages={catalog['page_count']} "
        f"controls={catalog['inline_control_count']} issues={len(catalog['issues'])}"
    )
    print(markdown_path)
    print(json_path)
    return 1 if catalog["issues"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
