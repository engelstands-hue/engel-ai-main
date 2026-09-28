#!/usr/bin/env python3
"""Verify Engel UI executable-result artifacts stay bounded and real."""
from __future__ import annotations

import json
import os
import py_compile
import shutil
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def assert_inside(path: Path, root: Path) -> None:
    resolved = path.resolve()
    base = root.resolve()
    require(resolved == base or base in resolved.parents, f"path escaped verifier artifact root: {resolved}")


def verify_direct_artifacts() -> None:
    from engel_ui_executable_results import execute_ui_result_request

    test_root = ROOT / "runtime" / "executable_result_verifier"
    if test_root.exists():
        shutil.rmtree(test_root)
    test_root.mkdir(parents=True, exist_ok=True)
    os.environ["ENGEL_EXECUTABLE_RESULTS_DIR"] = str(test_root)

    cases = [
        ("make me a PDF with a happy face on it", "pdf", "engel_result.pdf"),
        ("Create me a happy face. make face yellow", "image", "engel_visual.svg"),
        ("make me a pdf about Engel phone workers", "pdf", "engel_result.pdf"),
        ("make me a PDF about a before-and-after note on the fixed meeting-room maze routing bug", "pdf", "engel_result.pdf"),
        ("Make me a PDF about fourth-wave stress check with clearer wording and artifact uniqueness: a second-pass report on what the first UI training hour proved.", "pdf", "engel_result.pdf"),
        ("create file for an artifact index that lists PDF, game, research, code, and file outputs", "file", "requested_file.md"),
        ("create a polished Phaser video game about packet routing with high quality generated graphics", "game", "index.html"),
        ("create a meeting-room maze where the verifier guards the final door", "game", "index.html"),
        ("create third-wave build-on check using the first two classifier fixes: a packet sorting game with PDF, code, file, and research lanes", "game", "index.html"),
        ("Create fourth-wave stress check with clearer wording and artifact uniqueness: an upgraded meeting-room maze with device gates and verifier keys.", "game", "index.html"),
        ("lets work on the language for this app", "language", "app_language_pass.md"),
        ("write clearer error messages for when a phone is offline or not paired", "language", "app_language_pass.md"),
        ("search internet for helpful local first agent patterns", "research", "research_brief.md"),
        ("search online for phone tools that help create code and documents", "research", "research_brief.md"),
        ("Search online for fourth-wave stress check with clearer wording and artifact uniqueness: prompt classifier design for artifact creation systems and make a short brief.", "research", "research_brief.md"),
        ("write code for a small status helper", "code", ".py"),
        ("right me code for a tiny launcher helper", "code", ".py"),
        ("Write code for fourth-wave stress check with clearer wording and artifact uniqueness: a classifier helper that detects maze and puzzle creation prompts.", "code", ".py"),
        ("make this file and put it here", "file", "requested_file.md"),
    ]
    for prompt, kind, marker in cases:
        result = execute_ui_result_request(
            prompt,
            meeting_summary="Meeting Room updated: Android Worker Alpha returned, Verifier assigned",
            returned_previews=["Alpha: phone candidate returned over wifi", "Verifier: ready for review"],
        )
        require(result.get("accepted") is True, f"result not accepted for {prompt!r}: {result}")
        require(result.get("kind") == kind, f"wrong kind for {prompt!r}: {result.get('kind')}")
        out_dir = Path(str(result.get("artifact_dir")))
        assert_inside(out_dir, test_root)
        require(out_dir.exists(), f"artifact dir missing: {out_dir}")
        files = [Path(str(item)) for item in result.get("files", [])]
        require(files, f"no files returned for {prompt!r}")
        for path in files:
            assert_inside(path, test_root)
            require(path.exists(), f"file missing: {path}")
        manifest = out_dir / "manifest.json"
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        require(payload["safety"]["shell_execution"] is False, "manifest must block shell execution")
        require(payload["safety"]["source_mutation"] is False, "manifest must block source mutation")
        if marker == ".py":
            py_files = [path for path in files if path.suffix == ".py"]
            require(py_files, "code artifact must include a Python file")
            py_compile.compile(str(py_files[0]), doraise=True)
        else:
            require(any(path.name == marker for path in files), f"missing expected marker file {marker}")
        if kind == "game":
            index = out_dir / "index.html"
            game_js = out_dir / "game.js"
            vendor = out_dir / "vendor" / "phaser.min.js"
            require(index.exists() and game_js.exists(), "game artifact missing index/game.js")
            require(vendor.exists() and vendor.stat().st_size > 500000, "game artifact must bundle local Phaser runtime")
            require("vendor/phaser.min.js" in read(index), "game index must load bundled Phaser runtime")
            require("new Phaser.Game" in read(game_js), "game artifact must use Phaser game engine")
            require("makeTextures" in read(game_js), "game artifact must generate polished textures")
            require("makePremiumTextures" in read(game_js), "game artifact must include premium texture pass")
            require("neonSign" in read(game_js) and "holoPanel" in read(game_js), "game artifact must include premium set dressing")
            require("boss" in read(game_js).lower(), "game artifact must include boss logic")
            require("STAGE_COUNT = 10" in read(game_js), "game artifact must include 10 stages")
            require("PARTS_PER_STAGE = 5" in read(game_js), "game artifact must include 5 parts per stage")
            require("PART_WIDTH = 1280" in read(game_js), "game artifact must include longer Game Factory stage parts")
            require("controlUpgrades" in read(game_js), "game artifact must expose Game Factory control upgrades")
            require("cycleWeapon" in read(game_js), "game artifact must include weapon cycling")
            require("jumpBufferMs" in read(game_js) and "coyoteMs" in read(game_js), "game artifact must include jump buffer and coyote time")
            require('data-control="dash"' in read(index) and 'data-control="cycle"' in read(index), "game artifact must include expanded touch controls")
            require("WEAPON_ORDER" in read(game_js) and "spread" in read(game_js) and "rocket" in read(game_js), "game artifact must include weapon upgrades")
            require("this.bosses" in read(game_js), "game artifact must include per-stage boss group")
        if kind == "image":
            svg_files = [path for path in files if path.name == "engel_visual.svg"]
            require(svg_files, "image artifact must include engel_visual.svg")
            svg_text = svg_files[0].read_text(encoding="utf-8")
            require("#ffd83d" in svg_text and "<circle" in svg_text, "yellow happy-face SVG missing real drawing")
    pdfs = list(test_root.glob("**/engel_result.pdf"))
    require(pdfs and pdfs[0].read_bytes().startswith(b"%PDF-1.4"), "PDF artifact is not a real PDF")
    happy_pdfs = [path for path in pdfs if "happy_face" in str(path.parent).lower()]
    require(happy_pdfs, "happy-face PDF case did not produce a PDF")
    require(b"Engel visual: happy_face" in happy_pdfs[0].read_bytes(), "happy-face PDF missing embedded vector visual")
    require((happy_pdfs[0].parent / "visual_happy_face.svg").exists(), "happy-face PDF missing companion visual asset")
    game_index = next(test_root.glob("**/index.html"))
    game_text = game_index.read_text(encoding="utf-8")
    require("game-host" in game_text and "vendor/phaser.min.js" in game_text, "game artifact must include Phaser host/runtime")


def verify_source_wiring() -> None:
    desktop = read(ROOT / "engel_desktop_v2.py")
    meeting_room = read(ROOT / "engel_agent_meeting_room.py")
    executor = read(ROOT / "engel_ui_executable_results.py")

    for needle in (
        "_pending_user_text",
        "execute_ui_result_request",
        "_format_executable_result",
        "Engel Result:",
    ):
        require(needle in desktop, f"Desktop V2 missing executable result hook: {needle}")
    for needle in ("create", "write", "search", "generate", "draft"):
        require(f'"{needle}"' in meeting_room, f"Meeting Room order detector missing {needle!r}")
    for forbidden in ("subprocess", "os.system", "shell=True", "eval(", "exec("):
        require(forbidden not in executor, f"executor must not contain unsafe primitive: {forbidden}")
    require("DEFAULT_ARTIFACT_ROOT" in executor and "artifacts" in executor, "executor must write to artifact root")
    require("Engel visual:" in executor, "PDF executor must include embedded visual drawing commands")


def verify_rust_bridge_artifacts() -> None:
    from engel_ui_executable_results import execute_ui_result_request

    test_root = ROOT / "runtime" / "executable_result_verifier_rust_bridge"
    if test_root.exists():
        shutil.rmtree(test_root)
    test_root.mkdir(parents=True, exist_ok=True)

    old_runtime = os.environ.get("ENGEL_EXECUTABLE_RESULTS_RUNTIME")
    old_strict = os.environ.get("ENGEL_EXECUTABLE_RESULTS_RUST_STRICT")
    old_root = os.environ.get("ENGEL_EXECUTABLE_RESULTS_DIR")
    os.environ["ENGEL_EXECUTABLE_RESULTS_RUNTIME"] = "rust"
    os.environ["ENGEL_EXECUTABLE_RESULTS_RUST_STRICT"] = "1"
    os.environ["ENGEL_EXECUTABLE_RESULTS_DIR"] = str(test_root)
    try:
        cases = [
            ("make me a PDF with a happy face on it", "pdf", "engel_result.pdf"),
            ("Create me a happy face. make face yellow", "image", "engel_visual.svg"),
            ("create file for an artifact index", "file", "requested_file.md"),
            ("create a polished Phaser video game about packet routing", "game", "index.html"),
            ("lets work on the language for this app", "language", "app_language_pass.md"),
            ("search online for local-first agent patterns", "research", "research_brief.md"),
            ("write code for a small status helper", "code", ".py"),
        ]
        for prompt, kind, marker in cases:
            result = execute_ui_result_request(
                prompt,
                meeting_summary="Rust bridge verifier Meeting Room summary",
                returned_previews=["Alpha: Rust bridge context"],
            )
            require(result.get("accepted") is True, f"Rust bridge did not accept {prompt!r}: {result}")
            require(result.get("runtime") == "engel-ai-rs", f"Rust bridge did not return Rust runtime: {result}")
            require(result.get("kind") == kind, f"Rust bridge wrong kind for {prompt!r}: {result.get('kind')}")
            out_dir = Path(str(result.get("artifact_dir")))
            assert_inside(out_dir, test_root)
            require(out_dir.exists(), f"Rust bridge artifact dir missing: {out_dir}")
            files = [Path(str(item)) for item in result.get("files", [])]
            require(files, f"Rust bridge returned no files for {prompt!r}")
            for path in files:
                assert_inside(path, test_root)
                require(path.exists(), f"Rust bridge file missing: {path}")
            manifest = out_dir / "manifest.json"
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            require(payload["safety"]["shell_execution"] is False, "Rust bridge manifest must block shell execution")
            require(payload["safety"]["source_mutation"] is False, "Rust bridge manifest must block source mutation")
            if marker == ".py":
                py_files = [path for path in files if path.suffix == ".py"]
                require(py_files, "Rust bridge code artifact must include Python file")
                py_compile.compile(str(py_files[0]), doraise=True)
            else:
                require(any(path.name == marker for path in files), f"Rust bridge missing marker {marker}")
            if kind == "game":
                game_js = out_dir / "game.js"
                index = out_dir / "index.html"
                vendor = out_dir / "vendor" / "phaser.min.js"
                require(vendor.exists() and vendor.stat().st_size > 500000, "Rust bridge game must bundle Phaser")
                require("vendor/phaser.min.js" in read(index), "Rust bridge game index must load Phaser")
                for needle in (
                    "new Phaser.Game",
                    "makeTextures",
                    "makePremiumTextures",
                    "neonSign",
                    "holoPanel",
                    "STAGE_COUNT = 10",
                    "PARTS_PER_STAGE = 5",
                    "PART_WIDTH = 1280",
                    "controlUpgrades",
                    "cycleWeapon",
                    "jumpBufferMs",
                    "coyoteMs",
                    "WEAPON_ORDER",
                    "spread",
                    "rocket",
                    "this.bosses",
                ):
                    require(needle in read(game_js), f"Rust bridge game missing {needle}")
                require('data-control="dash"' in read(index) and 'data-control="cycle"' in read(index), "Rust bridge game missing touch controls")
            if kind == "pdf" and "happy face" in prompt.lower():
                require(b"Engel visual: happy_face" in (out_dir / "engel_result.pdf").read_bytes(), "Rust bridge happy-face PDF missing marker")
                require((out_dir / "visual_happy_face.svg").exists(), "Rust bridge happy-face PDF missing SVG companion")
    finally:
        if old_runtime is None:
            os.environ.pop("ENGEL_EXECUTABLE_RESULTS_RUNTIME", None)
        else:
            os.environ["ENGEL_EXECUTABLE_RESULTS_RUNTIME"] = old_runtime
        if old_strict is None:
            os.environ.pop("ENGEL_EXECUTABLE_RESULTS_RUST_STRICT", None)
        else:
            os.environ["ENGEL_EXECUTABLE_RESULTS_RUST_STRICT"] = old_strict
        if old_root is None:
            os.environ.pop("ENGEL_EXECUTABLE_RESULTS_DIR", None)
        else:
            os.environ["ENGEL_EXECUTABLE_RESULTS_DIR"] = old_root


def verify_routing_precedence() -> None:
    from engel_device_capability_registry import infer_job_type_from_text
    from engel_ui_executable_results import _infer_kind

    cases = [
        (
            "Make me a PDF about fourth-wave stress check with clearer wording and artifact uniqueness: a second-pass report on what the first UI training hour proved.",
            "format_report_draft",
            "pdf",
        ),
        (
            "Create fourth-wave stress check with clearer wording and artifact uniqueness: an upgraded meeting-room maze with device gates and verifier keys.",
            "draft_code_artifact",
            "game",
        ),
        (
            "Search online for fourth-wave stress check with clearer wording and artifact uniqueness: prompt classifier design for artifact creation systems and make a short brief.",
            "web_research_brief",
            "research",
        ),
        (
            "Write code for fourth-wave stress check with clearer wording and artifact uniqueness: a classifier helper that detects maze and puzzle creation prompts.",
            "draft_code_artifact",
            "code",
        ),
        (
            "Help me write clearer app wording for third-wave build-on check using the first two classifier fixes: plain words for code, PDF, file, game, language, and research jobs.",
            "summarize_text",
            "language",
        ),
        (
            "Create me a happy face. make face yellow",
            "summarize_text",
            "image",
        ),
    ]
    for prompt, job_type, kind in cases:
        require(infer_job_type_from_text(prompt) == job_type, f"wrong job type precedence for {prompt!r}")
        require(_infer_kind(prompt) == kind, f"wrong artifact kind precedence for {prompt!r}")
    require(infer_job_type_from_text("give me pairing code for wifi") == "return_status", "pairing-code prompt became a code task")
    require(_infer_kind("give me pairing code for wifi") == "", "pairing-code prompt must not create a code artifact")


def main() -> None:
    for module in (
        ROOT / "engel_ui_executable_results.py",
        ROOT / "engel_rust_executable_results_bridge.py",
        ROOT / "engel_agent_meeting_room.py",
        ROOT / "engel_desktop_v2.py",
    ):
        py_compile.compile(str(module), doraise=True)
    verify_direct_artifacts()
    verify_rust_bridge_artifacts()
    verify_source_wiring()
    verify_routing_precedence()
    print("OK: Engel UI executable-result path verified")


if __name__ == "__main__":
    main()
