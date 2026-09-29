#!/usr/bin/env python3
"""Verify the Engel feature map and the draft pull-request gate."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "organs" / "core"))
sys.path.insert(0, str(ROOT))

from engel_feature_map import (  # noqa: E402
    FEATURE_MAP_PATH,
    feature_sections,
    plan_draft_pr,
    render_feature_map,
)


REQUIRED = (
    "How a user gets there",
    "How the control adapter drives it",
    "Stable selectors",
    "States to exercise",
    "Preconditions and setup",
    "Evidence and cross-check",
    "Gotchas",
)


def main() -> int:
    failures: list[str] = []

    def require(ok: bool, message: str) -> None:
        print("[PASS]" if ok else "[FAIL]", message)
        if not ok:
            failures.append(message)

    text = FEATURE_MAP_PATH.read_text(encoding="utf-8") if FEATURE_MAP_PATH.is_file() else ""
    require(FEATURE_MAP_PATH.is_file(), "feature map file exists")
    sections = feature_sections(text)
    require(len(sections) >= 14, "feature map covers Engel and the surrounding parts")
    for title, body in sections:
        for heading in REQUIRED:
            require(f"#### {heading}" in body, f"{title} has {heading}")
    require("192.168." not in text, "feature map has no house LAN address")
    require("BEGIN PRIVATE KEY" not in text, "feature map has no private key")
    require("engelstands-hue/engel-ai-main" in text, "feature map names the public repository")
    index = render_feature_map("feature map")
    require("Engel AI Main desktop chat" in index, "index lists the desktop chat")
    one = render_feature_map("feature map Discord house")
    require(one.startswith("### Discord house"), "a named section is returned")
    missing = plan_draft_pr("")
    require(missing["ok"] == "false", "an empty title does not open a pull request")
    main_branch = plan_draft_pr("Add the map", "main")
    require(main_branch["ok"] == "false", "main is not a pull-request branch")
    planned = plan_draft_pr("Add the Engel feature map", "collab/20260929-feature-map")
    require(planned["ok"] == "true" and planned["branch"].startswith("collab/"), "a collab branch is accepted")
    config = ROOT / ".cursor" / "benny" / "configuration.yaml"
    config_text = config.read_text(encoding="utf-8") if config.is_file() else ""
    require("docs/ENGEL_FEATURE_MAP_V1.md" in config_text, "Benny config points at the feature map")
    require("draft: true" in config_text, "Benny pull requests stay drafts")
    if failures:
        print(f"ENGEL_FEATURE_MAP_VERIFIER_FAIL {len(failures)}")
        return 1
    print("ENGEL_FEATURE_MAP_VERIFIER_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
