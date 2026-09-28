#!/usr/bin/env python3
"""Verify Code Factory is merged into Engel's Agent Meeting Room flow."""
from __future__ import annotations

import json
import os
import py_compile
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
CODE_FACTORY = WORKSPACE / "code-factory"
BRIDGE_LABEL = "ChatGPT Bridge (Engel no-API handoff)"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def check_sources() -> None:
    files = [
        CODE_FACTORY / "factory.py",
        CODE_FACTORY / "lib" / "llm.py",
        ROOT / "engel_code_factory_bridge.py",
        ROOT / "engel_agent_meeting_room.py",
    ]
    for path in files:
        require(path.exists(), f"missing file: {path}")
        py_compile.compile(str(path), doraise=True)

    requirements = read(CODE_FACTORY / "requirements.txt").lower()
    llm_source = read(CODE_FACTORY / "lib" / "llm.py").lower()
    meeting_room_source = read(ROOT / "engel_agent_meeting_room.py")
    require("openai" not in requirements, "code-factory requirements must not depend on openai")
    forbidden_import_a = "from " + "openai"
    forbidden_import_b = "import " + "openai"
    old_bridge_label = "ChatGPT / " + "OpenAI API"
    require(forbidden_import_a not in llm_source and forbidden_import_b not in llm_source,
            "code-factory LLM bridge must not import OpenAI SDK")
    require("openai_api_key env var not set" not in llm_source,
            "code-factory LLM bridge must not require provider env key")
    require(old_bridge_label not in meeting_room_source,
            "Meeting Room must not expose the old ChatGPT/OpenAI API label")
    require(BRIDGE_LABEL in meeting_room_source,
            "Meeting Room must expose the no-API ChatGPT bridge label")
    require("Code Factory Scout (Engel Meeting Room)" in meeting_room_source,
            "Meeting Room must expose Code Factory Scout bridge")


def check_factory_direct_run() -> None:
    if str(CODE_FACTORY) not in sys.path:
        sys.path.insert(0, str(CODE_FACTORY))
    from lib.llm import LLM

    os.environ.pop("OPENAI_API_KEY", None)
    result = LLM("engel-chatgpt-bridge").complete_json(
        "You are the Scout station of an autonomous software factory.",
        "\n".join(
            [
                "Issue id: verify-local",
                "Title: factory.py should support --version",
                "Priority: P2    Size: small",
                "",
                "Description:",
                "Add a version flag.",
                "",
                "Acceptance criteria:",
                "- Running python factory.py --version prints a version string and exits 0",
                "",
                "---",
                "",
                "Codebase summary:",
                "Repo file list (truncated):",
                "factory.py",
                "lib/llm.py",
                "README.md",
                "",
            ]
        ),
    )
    parsed = result.parsed or {}
    require(BRIDGE_LABEL == result.raw.get("bridge"), "LLM did not use Engel bridge label")
    require("factory.py" in parsed.get("files_to_modify", []),
            "Scout did not select factory.py for --version issue")


def check_meeting_room_real_flow() -> None:
    import engel_agent_meeting_room as room

    prompt = (
        "Use main PC Code Factory Scout: make a builder-ready spec for adding a --version "
        "flag to code-factory factory.py."
    )
    staged = room.submit_order_from_engel_main_ui(prompt, source="Verifier Engel UI Input")
    require(staged.get("accepted"), f"Meeting Room rejected order: {staged}")
    labels = staged.get("station_labels") or []
    require(any("Code Factory Scout" in str(label) for label in labels),
            f"Code Factory Scout was not selected: {labels}")

    completed = room.complete_order_from_engel_main_ui(
        str(staged["order_id"]),
        "Engel main UI accepted the Code Factory Scout job.",
        source="Verifier Engel UI Input",
    )
    require(completed.get("accepted"), f"Meeting Room did not complete order: {completed}")
    previews = "\n".join(str(item) for item in completed.get("returned_previews") or [])
    require("Code Factory Scout returned a Builder-ready spec" in previews,
            f"Code Factory Scout did not return a spec preview: {previews}")

    match = re.search(r"Spec:\s*([^\r\n]+\.json)", previews)
    if match is not None:
        spec_path = Path(match.group(1).strip())
    else:
        specs_root = ROOT / "runtime" / "meeting_room" / "code_factory" / "runtime" / "specs"
        specs = sorted(specs_root.glob("engel-code-factory-*.json"), key=lambda path: path.stat().st_mtime)
        require(specs, f"spec path missing in preview and no spec files found: {previews}")
        spec_path = specs[-1]
    require(spec_path.exists(), f"spec file was not written: {spec_path}")
    require(str(spec_path).startswith(str(ROOT / "runtime" / "meeting_room" / "code_factory")),
            f"spec should be under Engel App runtime, got: {spec_path}")
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    require("factory.py" in spec.get("files_to_modify", []),
            f"Meeting Room Scout spec did not choose factory.py: {spec.get('files_to_modify')}")
    tests = "\n".join(str(item) for item in spec.get("tests") or [])
    require("--version" in tests, f"Meeting Room Scout spec missing --version test: {tests}")


def main() -> int:
    check_sources()
    check_factory_direct_run()
    check_meeting_room_real_flow()
    print("OK: Engel Code Factory Meeting Room bridge verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
