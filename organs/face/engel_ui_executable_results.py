#!/usr/bin/env python3
"""Bounded executable-result writer for Engel UI prompts.

Engel's Meeting Room can ask phones and agents for candidate work. This
module is the local, reviewable finalizer that turns clear user requests into
real files under Engel's artifact folder. It does not run generated code, call
shells, mutate source files, or apply phone output directly.
"""
from __future__ import annotations

import datetime
import html as html_lib
import json
import os
import re
import shutil
import textwrap
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from engel_android_worker_prompt_signals import is_android_lan_pairing_request
from engel_project_paths import resolve_engel_app_root

ENGEL_APP_ROOT = resolve_engel_app_root(__file__)
DEFAULT_ARTIFACT_ROOT = ENGEL_APP_ROOT / "artifacts" / "engel_ui_results"
GAME_RUNTIME_VENDOR = ENGEL_APP_ROOT / "assets" / "engel_game_runtime" / "vendor" / "phaser.min.js"
MAX_PROMPT_CHARS = 4000
MAX_CONTEXT_CHARS = 6000


def _artifact_root() -> Path:
    configured = os.environ.get("ENGEL_EXECUTABLE_RESULTS_DIR", "").strip()
    if configured:
        root = Path(configured)
        if not root.is_absolute():
            root = ENGEL_APP_ROOT / root
        return root
    return DEFAULT_ARTIFACT_ROOT


def _rust_generator_enabled() -> bool:
    runtime = os.environ.get("ENGEL_EXECUTABLE_RESULTS_RUNTIME", "").strip().lower()
    if runtime in {"rust", "rs", "engel-ai-rs", "engel_rs"}:
        return True
    value = os.environ.get("ENGEL_EXECUTABLE_RESULTS_USE_RUST", "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _rust_generator_strict() -> bool:
    value = os.environ.get("ENGEL_EXECUTABLE_RESULTS_RUST_STRICT", "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _now_stamp() -> str:
    return datetime.datetime.now().strftime("%Y%m%dT%H%M%S")


def _slug(text: str, limit: int = 52) -> str:
    clean = re.sub(r"[^A-Za-z0-9]+", "_", str(text or "").lower()).strip("_")
    clean = re.sub(r"_+", "_", clean)
    return (clean[:limit].strip("_") or "engel_result")


def _clip(text: str, limit: int) -> str:
    value = str(text or "").strip()
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 3)].rstrip() + "..."


def _safe_lines(text: str, width: int = 88, max_lines: int = 64) -> list[str]:
    lines: list[str] = []
    for raw in str(text or "").replace("\r", "").split("\n"):
        raw = raw.strip()
        if not raw:
            lines.append("")
            continue
        lines.extend(textwrap.wrap(raw, width=width, replace_whitespace=False) or [""])
        if len(lines) >= max_lines:
            break
    return lines[:max_lines]


def _infer_kind(prompt: str) -> str:
    low = str(prompt or "").lower()
    if not low.strip():
        return ""
    if is_android_lan_pairing_request(low):
        return ""
    if any(token in low for token in ("make this file", "mkae this file", "create file", "write file", "put it here", "save file")):
        return "file"
    save_requested = (
        "save" in low
        and "memory" not in low
        and any(re.search(rf"\b{word}\b", low) for word in ("make", "mkae", "create", "write", "draft", "build"))
    )
    explicit_language = any(
        token in low
        for token in (
            "app wording",
            "write clearer app wording",
            "clearer wording",
            "language for this app",
            "app language",
            "microcopy",
            "error message",
            "error messages",
            "result messages",
            "button labels",
            "status copy",
            "friendly text",
            "plain words",
            "short descriptions",
        )
    )
    language_command = low.strip().startswith(
        (
            "help me write",
            "help with app wording",
            "write clearer app wording",
            "lets work on the language",
            "let's work on the language",
        )
    )
    explicit_pdf = "pdf" in low and any(
        token in low
        for token in ("make me a pdf", "make a pdf", "create a pdf", "write a pdf", "generate a pdf", "pdf report", "pdf about")
    )
    explicit_search = any(token in low for token in ("search internet", "search online", "look online", "web search", "research online", "look up online"))
    explicit_code = any(token in low for token in ("write code", "write me code", "right me code", "rite me code", "code for", "make code", "create code", "script for", "function for"))
    explicit_image = (
        "pdf" not in low and
        any(token in low for token in ("happy face", "smiley", "icon", "logo", "picture", "drawing", "image", "graphic", "illustration"))
        and any(re.search(rf"\b{word}\b", low) for word in ("make", "mkae", "create", "draw", "generate", "build"))
    )
    explicit_game = (
        "video game" in low
        or "create a game" in low
        or "create game" in low
        or bool(re.search(r"\b(?:create|make|build(?!-)|draft)\b[^.?!]{0,160}\bgame\b", low))
        or bool(re.search(r"\b(?:create|make|build(?!-)|draft)\b[^.?!]{0,160}\b(?:maze|puzzle|playable|runner|courier|arcade)\b", low))
    )
    generic_game = "video game" in low or bool(re.search(r"\bgame\b", low))
    if explicit_pdf:
        return "pdf"
    if explicit_search:
        return "research"
    if explicit_code:
        return "code"
    if explicit_language and language_command:
        return "language"
    if explicit_game:
        return "game"
    if explicit_image:
        return "image"
    if explicit_language:
        return "language"
    if generic_game:
        return "game"
    if "pdf" in low:
        return "pdf"
    if any(token in low for token in ("app language", "language for this app", "wording", "copy", "microcopy", "tone", "error message", "error messages")):
        return "language"
    if save_requested:
        return "file"
    return ""


def _make_artifact_dir(kind: str, prompt: str) -> Path:
    root = _artifact_root()
    folder = root / f"{_now_stamp()}_{kind}_{_slug(prompt)}"
    folder.mkdir(parents=True, exist_ok=False)
    return folder


def _write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def _context_block(meeting_summary: str, returned_previews: list[str] | None) -> str:
    parts: list[str] = []
    summary = _clip(meeting_summary, MAX_CONTEXT_CHARS // 2)
    if summary:
        parts.append("Meeting Room summary:\n" + summary)
    previews = [str(item).strip() for item in (returned_previews or []) if str(item).strip()]
    if previews:
        parts.append("Agent/device returned previews:\n" + "\n".join(f"- {_clip(item, 700)}" for item in previews[:8]))
    return "\n\n".join(parts)


def _pdf_escape(text: str) -> str:
    safe = str(text or "").encode("latin-1", "replace").decode("latin-1")
    return safe.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _circle_path(cx: float, cy: float, radius: float) -> list[str]:
    k = radius * 0.5522847498
    return [
        f"{cx + radius:.2f} {cy:.2f} m",
        f"{cx + radius:.2f} {cy + k:.2f} {cx + k:.2f} {cy + radius:.2f} {cx:.2f} {cy + radius:.2f} c",
        f"{cx - k:.2f} {cy + radius:.2f} {cx - radius:.2f} {cy + k:.2f} {cx - radius:.2f} {cy:.2f} c",
        f"{cx - radius:.2f} {cy - k:.2f} {cx - k:.2f} {cy - radius:.2f} {cx:.2f} {cy - radius:.2f} c",
        f"{cx + k:.2f} {cy - radius:.2f} {cx + radius:.2f} {cy - k:.2f} {cx + radius:.2f} {cy:.2f} c",
    ]


def _happy_face_pdf_commands() -> list[str]:
    cx, cy, r = 430.0, 525.0, 72.0
    return [
        "q",
        "% Engel visual: happy_face",
        "1 0.86 0.16 rg",
        "0 0.92 0.48 RG",
        "3 w",
        *_circle_path(cx, cy, r),
        "B",
        "0.02 0.07 0.12 rg",
        *_circle_path(cx - 26, cy + 20, 7),
        "f",
        *_circle_path(cx + 26, cy + 20, 7),
        "f",
        "0.02 0.07 0.12 RG",
        "5 w",
        f"{cx - 38:.2f} {cy - 10:.2f} m",
        f"{cx - 20:.2f} {cy - 42:.2f} {cx + 20:.2f} {cy - 42:.2f} {cx + 38:.2f} {cy - 10:.2f} c",
        "S",
        "Q",
    ]


def _engel_mark_pdf_commands() -> list[str]:
    return [
        "q",
        "% Engel visual: brand_panel",
        "0.02 0.04 0.08 rg",
        "0 0.92 0.48 RG",
        "2 w",
        "384 510 144 102 re",
        "B",
        "0 0.92 0.48 RG",
        "1.5 w",
        "404 558 m 438 588 l 484 548 l 510 576 l",
        "S",
        "0.55 0.32 1 RG",
        "1.25 w",
        "410 532 m 500 532 l",
        "S",
        "0 0.92 0.48 rg",
        *_circle_path(404, 558, 4),
        "f",
        *_circle_path(438, 588, 4),
        "f",
        *_circle_path(484, 548, 4),
        "f",
        *_circle_path(510, 576, 4),
        "f",
        "Q",
    ]


def _pdf_visual_kind(prompt: str) -> str:
    low = str(prompt or "").lower()
    if any(token in low for token in ("happy face", "smiley", "smile face", "smiling face")):
        return "happy_face"
    return "engel_mark"


def _pdf_visual_commands(prompt: str) -> list[str]:
    if _pdf_visual_kind(prompt) == "happy_face":
        return _happy_face_pdf_commands()
    return _engel_mark_pdf_commands()


def _write_pdf_visual_asset(out_dir: Path, visual_kind: str) -> Path:
    if visual_kind == "happy_face":
        svg = """<svg xmlns="http://www.w3.org/2000/svg" width="720" height="480" viewBox="0 0 720 480">
  <rect width="720" height="480" fill="#050814"/>
  <circle cx="360" cy="240" r="150" fill="#ffd83d" stroke="#00eb7a" stroke-width="10"/>
  <circle cx="305" cy="205" r="18" fill="#06121f"/>
  <circle cx="415" cy="205" r="18" fill="#06121f"/>
  <path d="M280 270 C315 345 405 345 440 270" fill="none" stroke="#06121f" stroke-width="14" stroke-linecap="round"/>
  <text x="360" y="440" text-anchor="middle" font-family="Consolas, monospace" font-size="28" fill="#00eb7a">ENGEL AI GENERATED VISUAL</text>
</svg>
"""
        return _write_text(out_dir / "visual_happy_face.svg", svg)
    svg = """<svg xmlns="http://www.w3.org/2000/svg" width="720" height="480" viewBox="0 0 720 480">
  <rect width="720" height="480" fill="#050814"/>
  <rect x="155" y="130" width="410" height="220" rx="14" fill="#0b1020" stroke="#00eb7a" stroke-width="6"/>
  <path d="M205 250 L305 185 L410 260 L510 205" fill="none" stroke="#8b5cf6" stroke-width="8"/>
  <circle cx="205" cy="250" r="15" fill="#00eb7a"/>
  <circle cx="305" cy="185" r="15" fill="#00eb7a"/>
  <circle cx="410" cy="260" r="15" fill="#00eb7a"/>
  <circle cx="510" cy="205" r="15" fill="#00eb7a"/>
  <text x="360" y="395" text-anchor="middle" font-family="Consolas, monospace" font-size="28" fill="#00eb7a">ENGEL AI VISUAL PDF MARK</text>
</svg>
"""
    return _write_text(out_dir / "visual_engel_mark.svg", svg)


def _write_simple_pdf(path: Path, title: str, lines: list[str], vector_commands: list[str] | None = None) -> Path:
    y_step = 16
    stream_lines = list(vector_commands or [])
    stream_lines += ["BT", "/F1 16 Tf", "72 742 Td", f"({_pdf_escape(title[:90])}) Tj", "/F1 10 Tf", f"0 -{y_step * 2} Td"]
    for line in lines[:42]:
        if line:
            stream_lines.append(f"({_pdf_escape(line[:105])}) Tj")
        stream_lines.append(f"0 -{y_step} Td")
    stream_lines.append("ET")
    stream = "\n".join(stream_lines).encode("latin-1", "replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for idx, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{idx} 0 obj\n".encode("ascii"))
        output.extend(obj)
        output.extend(b"\nendobj\n")
    xref_at = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n".encode("ascii")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(output))
    return path


def _manifest(kind: str, prompt: str, out_dir: Path, files: list[Path], notes: list[str]) -> Path:
    payload = {
        "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "kind": kind,
        "prompt_preview": _clip(prompt, 500),
        "artifact_dir": str(out_dir),
        "files": [str(path) for path in files],
        "notes": notes,
        "safety": {
            "shell_execution": False,
            "source_mutation": False,
            "phone_worker_output_auto_applied": False,
            "artifact_root_only": True,
        },
    }
    manifest = out_dir / "manifest.json"
    manifest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return manifest


def _create_pdf(prompt: str, out_dir: Path, context: str) -> tuple[list[Path], str]:
    title = _title_from_prompt(prompt, "Engel AI Report")
    visual_kind = _pdf_visual_kind(prompt)
    body = "\n".join([
        f"# {title}",
        "",
        "Generated by Engel AI after Meeting Room routing.",
        "",
        "## Request",
        _clip(prompt, MAX_PROMPT_CHARS),
        "",
        "## Agent Notes",
        context or "No agent preview was attached to this result.",
        "",
        "## Result",
        "This PDF is a real local artifact. Phone worker outputs are included only as reviewable context.",
        f"Visual content: {visual_kind.replace('_', ' ')} drawing embedded in the PDF.",
    ])
    source = _write_text(out_dir / "source.md", body)
    visual_asset = _write_pdf_visual_asset(out_dir, visual_kind)
    pdf = _write_simple_pdf(
        out_dir / "engel_result.pdf",
        title,
        _safe_lines(body, width=96, max_lines=60),
        vector_commands=_pdf_visual_commands(prompt),
    )
    return [source, visual_asset, pdf], f"Created visual PDF artifact: {pdf}"


def _game_title_from_prompt(prompt: str) -> str:
    text = re.sub(r"\s+", " ", str(prompt or "")).strip()
    low = str(prompt or "").lower()
    named = re.search(r"\b(?:called|named|titled)\s+([A-Za-z][A-Za-z0-9 '&:-]{2,70})(?:[.!?,;]|$)", text, flags=re.I)
    if named:
        candidate = named.group(1).strip(" '\"-:")
        if candidate and "metal slug" not in candidate.lower():
            return candidate[:70].strip()
    if any(token in low for token in ("metal slug", "run-and-gun", "run and gun", "side-scrolling", "arcade shooter")):
        return "Engel Iron Route"
    if any(token in low for token in ("maze", "verifier key", "device gate")):
        return "Engel Gate Maze"
    title = _title_from_prompt(prompt, "Engel Signal Runner")
    if "metal slug" in title.lower():
        return "Engel Iron Route"
    return title


def _copy_game_runtime(out_dir: Path) -> Path:
    vendor_dir = out_dir / "vendor"
    vendor_dir.mkdir(parents=True, exist_ok=True)
    runtime_target = vendor_dir / "phaser.min.js"
    if not GAME_RUNTIME_VENDOR.exists():
        raise FileNotFoundError(f"Missing Engel game runtime dependency: {GAME_RUNTIME_VENDOR}")
    shutil.copy2(GAME_RUNTIME_VENDOR, runtime_target)
    return runtime_target


def _create_game(prompt: str, out_dir: Path, context: str) -> tuple[list[Path], str]:
    title = _game_title_from_prompt(prompt)
    escaped_title = html_lib.escape(title)
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escaped_title}</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <main class="game-shell">
    <header class="topbar">
      <div>
        <p class="eyebrow">Engel AI Game Development</p>
        <h1>{escaped_title}</h1>
      </div>
      <div class="scoreboard">
        <span>HP <strong id="hp">100</strong></span>
        <span>Score <strong id="score">0</strong></span>
        <span>Grenades <strong id="grenades">3</strong></span>
        <span>Weapon <strong id="weapon">Pulse</strong></span>
        <span>Stage <strong id="stage">1-1</strong></span>
      </div>
    </header>
    <section id="game-host" aria-label="Playable Engel arcade game"></section>
    <section class="touch-controls" aria-label="Touch controls">
      <div>
        <button type="button" data-control="left" aria-label="Move left">Left</button>
        <button type="button" data-control="right" aria-label="Move right">Right</button>
        <button type="button" data-control="down" aria-label="Crouch">Down</button>
        <button type="button" data-control="dash" aria-label="Dash or sprint">Dash</button>
      </div>
      <div>
        <button type="button" data-control="jump" aria-label="Jump">Jump</button>
        <button type="button" data-control="shoot" aria-label="Shoot">Fire</button>
        <button type="button" data-control="grenade" aria-label="Throw grenade">Bomb</button>
        <button type="button" data-control="cycle" aria-label="Cycle weapon">Cycle</button>
      </div>
    </section>
    <footer class="controls">
      <span>A/D or arrows move</span>
      <span>W/Space jump</span>
      <span>S crouch</span>
      <span>Shift dash/sprint</span>
      <span>J shoot</span>
      <span>K grenade</span>
      <span>Q cycle weapon</span>
      <span>P pause</span>
      <span>R restart</span>
    </footer>
  </main>
  <script src="vendor/phaser.min.js"></script>
  <script src="game.js"></script>
</body>
</html>
"""
    css = """html, body {
  margin: 0;
  min-height: 100%;
  background:
    radial-gradient(circle at 30% 8%, rgba(0, 255, 146, 0.13), transparent 28rem),
    radial-gradient(circle at 75% 18%, rgba(72, 169, 255, 0.13), transparent 30rem),
    #05070d;
  color: #e8fff5;
  font-family: Consolas, "Segoe UI", monospace;
}
.game-shell {
  min-height: 100vh;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto auto;
  gap: 10px;
  padding: 14px;
  box-sizing: border-box;
}
.topbar, .controls {
  border: 1px solid rgba(85, 120, 160, 0.45);
  background: rgba(7, 12, 22, 0.76);
  border-radius: 8px;
  padding: 10px 12px;
}
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
.eyebrow {
  margin: 0 0 3px;
  color: #00ff92;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0;
}
h1 {
  margin: 0;
  color: #ffffff;
  font-size: 30px;
  line-height: 1;
}
.scoreboard {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}
.scoreboard span {
  min-width: 86px;
  border: 1px solid rgba(85, 120, 160, 0.55);
  border-radius: 6px;
  padding: 8px 10px;
  background: rgba(12, 18, 32, 0.86);
  color: #add6ff;
}
.scoreboard strong {
  color: #ffc247;
}
#game-host {
  min-height: 0;
  border: 1px solid rgba(85, 120, 160, 0.42);
  border-radius: 8px;
  overflow: hidden;
  background: #06101d;
}
#game-host canvas {
  display: block;
  width: 100%;
  height: 100%;
}
.controls {
  display: flex;
  gap: 14px;
  justify-content: space-between;
  flex-wrap: wrap;
  color: #9cc8ea;
  font-size: 12px;
}
.touch-controls {
  display: none;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.touch-controls div {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
}
.touch-controls button {
  border: 1px solid rgba(0, 255, 146, 0.45);
  border-radius: 8px;
  background: rgba(5, 20, 30, 0.9);
  color: #00ff92;
  font: 700 12px Consolas, monospace;
  min-height: 44px;
}
@media (hover: none), (max-width: 760px) {
  .game-shell { padding: 8px; gap: 8px; }
  h1 { font-size: 22px; }
  .topbar { align-items: flex-start; }
  .scoreboard span { min-width: 74px; padding: 6px 8px; }
  .touch-controls { display: grid; }
  .controls { font-size: 11px; }
}
"""
    js = """(() => {
  const WIDTH = 960;
  const HEIGHT = 540;
  const STAGE_COUNT = 10;
  const PARTS_PER_STAGE = 5;
  const PART_WIDTH = 1280;
  const STAGE_WIDTH = PART_WIDTH * PARTS_PER_STAGE;
  const LEVEL_WIDTH = STAGE_COUNT * STAGE_WIDTH;
  const GROUND_Y = 468;
  const GAME_TITLE = document.querySelector("h1")?.textContent || "Engel Arcade Route";
  const STAGE_THEMES = [
    { name: "Neon Dock", color: 0x00f08a, bg: 0x0b2330, glow: 0x00f08a },
    { name: "Ash Foundry", color: 0xff6b35, bg: 0x2a1410, glow: 0xffc247 },
    { name: "Glass Jungle", color: 0x4cff8f, bg: 0x0b2518, glow: 0x4cff8f },
    { name: "Storm Rail", color: 0x48a9ff, bg: 0x0d1a33, glow: 0x48a9ff },
    { name: "Desert Array", color: 0xffc247, bg: 0x2f2512, glow: 0xffd55a },
    { name: "Frozen Uplink", color: 0xa8dcff, bg: 0x10243b, glow: 0xa8dcff },
    { name: "Subsea Vault", color: 0x2ee9ff, bg: 0x071d27, glow: 0x2ee9ff },
    { name: "Orbital Yard", color: 0xb78cff, bg: 0x16152f, glow: 0xb78cff },
    { name: "Signal City", color: 0xff4d66, bg: 0x25111e, glow: 0xff4d66 },
    { name: "Core Citadel", color: 0xffffff, bg: 0x111827, glow: 0xffffff },
  ];
  const WEAPONS = {
    pulse: { label: "Pulse", cooldown: 115, speed: 720, damage: 22, tint: 0xffd55a },
    spread: { label: "Spread", cooldown: 165, speed: 650, damage: 18, tint: 0x00f08a },
    laser: { label: "Laser", cooldown: 185, speed: 940, damage: 34, tint: 0x48a9ff },
    rocket: { label: "Rocket", cooldown: 330, speed: 520, damage: 62, tint: 0xff6b35, explosive: true },
    arc: { label: "Arc", cooldown: 210, speed: 760, damage: 28, tint: 0xb78cff },
  };
  const WEAPON_ORDER = ["pulse", "spread", "laser", "rocket", "arc"];
  const touch = new Set();
  const hud = {
    hp: document.getElementById("hp"),
    score: document.getElementById("score"),
    grenades: document.getElementById("grenades"),
    weapon: document.getElementById("weapon"),
    stage: document.getElementById("stage"),
  };
  window.engelCampaignSpec = {
    originalIp: true,
    engine: "Phaser 3.90.0",
    stageCount: STAGE_COUNT,
    partsPerStage: PARTS_PER_STAGE,
    bossCount: STAGE_COUNT,
    weaponUpgrades: WEAPON_ORDER,
    stageThemes: STAGE_THEMES.map((theme) => theme.name),
    partWidth: PART_WIDTH,
    controlUpgrades: ["dash", "sprint", "jump-buffer", "coyote-time", "weapon-cycle", "expanded-touch-controls"],
  };

  function makeTextures(scene) {
    const g = scene.make.graphics({ x: 0, y: 0, add: false });
    const tex = (key, w, h, draw) => {
      g.clear();
      draw(g, w, h);
      g.generateTexture(key, w, h);
    };
    tex("hero", 96, 72, (p) => {
      p.fillStyle(0x07101e, 0.32).fillEllipse(48, 62, 72, 16);
      p.fillStyle(0x00f08a).fillRoundedRect(18, 26, 42, 30, 12);
      p.fillStyle(0x1fb8ff).fillRoundedRect(23, 17, 34, 25, 10);
      p.fillStyle(0xffffff).fillRoundedRect(31, 12, 26, 13, 4);
      p.fillStyle(0xffd55a).fillRoundedRect(50, 31, 28, 9, 4);
      p.fillStyle(0x102033).fillRoundedRect(70, 33, 18, 5, 2);
      p.fillStyle(0x0d1725).fillRoundedRect(22, 53, 13, 12, 4).fillRoundedRect(47, 53, 13, 12, 4);
      p.lineStyle(3, 0xdffcf1, 0.75).strokeRoundedRect(18, 25, 42, 31, 12);
      p.lineStyle(2, 0x00f08a, 0.65).lineBetween(13, 38, 3, 31).lineBetween(62, 37, 70, 30);
    });
    tex("trooper", 78, 70, (p) => {
      p.fillStyle(0xff4d66).fillRoundedRect(20, 25, 37, 30, 10);
      p.fillStyle(0xe4edf5).fillRoundedRect(25, 13, 28, 19, 6);
      p.fillStyle(0x1a2534).fillRoundedRect(8, 34, 20, 7, 3);
      p.fillStyle(0x111827).fillRoundedRect(24, 53, 12, 12, 3).fillRoundedRect(45, 53, 12, 12, 3);
      p.lineStyle(2, 0xff8797).strokeRoundedRect(20, 25, 37, 30, 10);
    });
    tex("shield", 84, 76, (p) => {
      p.fillStyle(0x9fb4c8).fillRoundedRect(22, 24, 38, 34, 10);
      p.fillStyle(0x4a6178).fillRoundedRect(11, 31, 22, 27, 6);
      p.fillStyle(0xe7f7ff).fillRoundedRect(29, 11, 28, 20, 6);
      p.lineStyle(3, 0x48a9ff).strokeRoundedRect(11, 31, 22, 27, 6);
    });
    tex("drone", 86, 48, (p) => {
      p.fillStyle(0x48a9ff).fillRoundedRect(24, 14, 38, 18, 6);
      p.fillStyle(0xc6e7ff).fillRect(32, 9, 18, 9);
      p.fillStyle(0x00f08a).fillRect(13, 21, 14, 5).fillRect(59, 21, 14, 5);
      p.lineStyle(2, 0xa8dcff).strokeRoundedRect(24, 14, 38, 18, 6);
    });
    tex("boss", 230, 150, (p) => {
      p.fillStyle(0x0b1424).fillRoundedRect(32, 44, 156, 82, 18);
      p.fillStyle(0x24384d).fillRoundedRect(55, 18, 84, 44, 12);
      p.fillStyle(0xff4d66).fillCircle(102, 81, 19);
      p.fillStyle(0xffc247).fillRoundedRect(8, 76, 42, 14, 5);
      p.fillStyle(0x8ba8bd).fillRoundedRect(176, 63, 34, 29, 8);
      p.fillStyle(0x192535).fillRoundedRect(44, 116, 24, 20, 6).fillRoundedRect(151, 116, 24, 20, 6);
      p.lineStyle(4, 0x48a9ff, 0.8).strokeRoundedRect(32, 44, 156, 82, 18);
      p.lineStyle(3, 0x00f08a, 0.7).lineBetween(70, 64, 132, 64).lineBetween(71, 98, 142, 98);
    });
    tex("crate", 64, 64, (p) => {
      p.fillStyle(0x8a5b25).fillRoundedRect(5, 5, 54, 54, 4);
      p.lineStyle(4, 0xffc247).strokeRoundedRect(5, 5, 54, 54, 4);
      p.lineStyle(3, 0x5c3516).lineBetween(13, 13, 51, 51).lineBetween(51, 13, 13, 51);
    });
    tex("platform", 128, 34, (p) => {
      p.fillStyle(0x263647).fillRoundedRect(0, 4, 128, 26, 3);
      p.fillStyle(0x3d5369).fillRect(0, 4, 128, 8);
      p.lineStyle(2, 0x7aa4c9, 0.7).strokeRoundedRect(0, 4, 128, 26, 3);
    });
    tex("bullet", 28, 8, (p) => {
      p.fillStyle(0xffd55a).fillRoundedRect(1, 1, 24, 6, 3);
      p.fillStyle(0xffffff, 0.8).fillRect(5, 2, 11, 2);
    });
    tex("enemyBullet", 22, 9, (p) => {
      p.fillStyle(0xff4d66).fillRoundedRect(1, 1, 19, 7, 3);
    });
    tex("grenade", 20, 20, (p) => {
      p.fillStyle(0x121c2a).fillCircle(10, 11, 8);
      p.fillStyle(0x00f08a).fillRoundedRect(6, 2, 8, 5, 2);
      p.lineStyle(2, 0xffc247).strokeCircle(10, 11, 8);
    });
    tex("spark", 12, 12, (p) => {
      p.fillStyle(0xffd55a).fillCircle(6, 6, 5);
      p.fillStyle(0xffffff).fillCircle(5, 4, 2);
    });
    tex("health", 34, 34, (p) => {
      p.fillStyle(0x06121f).fillRoundedRect(2, 2, 30, 30, 7);
      p.fillStyle(0x00f08a).fillRect(14, 7, 6, 20).fillRect(7, 14, 20, 6);
      p.lineStyle(2, 0x00f08a).strokeRoundedRect(2, 2, 30, 30, 7);
    });
    tex("ammo", 34, 34, (p) => {
      p.fillStyle(0x06121f).fillRoundedRect(2, 2, 30, 30, 7);
      p.fillStyle(0xffc247).fillRoundedRect(9, 8, 16, 18, 5);
      p.lineStyle(2, 0xffc247).strokeRoundedRect(2, 2, 30, 30, 7);
    });
    tex("upgrade", 42, 34, (p) => {
      p.fillStyle(0x06121f).fillRoundedRect(2, 2, 38, 30, 8);
      p.fillStyle(0x48a9ff).fillRoundedRect(7, 10, 28, 6, 3);
      p.fillStyle(0x00f08a).fillTriangle(11, 24, 21, 13, 31, 24);
      p.lineStyle(2, 0x00f08a).strokeRoundedRect(2, 2, 38, 30, 8);
    });
    tex("skyTile", 960, 540, (p) => {
      p.fillStyle(0x07101e).fillRect(0, 0, 960, 540);
      p.fillStyle(0x0e2236).fillTriangle(20, 420, 245, 240, 468, 420).fillTriangle(480, 420, 690, 235, 930, 420);
      p.fillStyle(0x121e2e).fillRoundedRect(190, 318, 165, 120, 2).fillRoundedRect(740, 315, 170, 120, 2);
      p.fillStyle(0x243653).fillRect(236, 345, 28, 24).fillRect(292, 363, 34, 24).fillRect(782, 348, 26, 25).fillRect(839, 363, 30, 28);
      p.fillStyle(0x00f08a, 0.15).fillCircle(795, 90, 58);
      p.fillStyle(0x48a9ff, 0.12).fillCircle(165, 105, 38);
    });
  }

  function makePremiumTextures(scene) {
    const roundRect = (ctx, x, y, w, h, r) => {
      const radius = Math.min(r, w / 2, h / 2);
      ctx.beginPath();
      ctx.moveTo(x + radius, y);
      ctx.arcTo(x + w, y, x + w, y + h, radius);
      ctx.arcTo(x + w, y + h, x, y + h, radius);
      ctx.arcTo(x, y + h, x, y, radius);
      ctx.arcTo(x, y, x + w, y, radius);
      ctx.closePath();
    };
    const canvasTex = (key, w, h, draw) => {
      if (scene.textures.exists(key)) scene.textures.remove(key);
      const texture = scene.textures.createCanvas(key, w, h);
      const ctx = texture.getContext();
      ctx.clearRect(0, 0, w, h);
      draw(ctx, w, h);
      texture.refresh();
    };
    canvasTex("skyTile", 960, 540, (ctx, w, h) => {
      let bg = ctx.createLinearGradient(0, 0, 0, h);
      bg.addColorStop(0, "#07101f");
      bg.addColorStop(0.48, "#0a1830");
      bg.addColorStop(1, "#06101a");
      ctx.fillStyle = bg;
      ctx.fillRect(0, 0, w, h);
      for (const glow of [[150, 92, 80, "rgba(72,169,255,.18)"], [760, 115, 115, "rgba(0,240,138,.17)"], [488, 68, 54, "rgba(255,194,71,.08)"], [905, 230, 88, "rgba(255,77,102,.12)"]]) {
        const [x, y, r, color] = glow;
        const g = ctx.createRadialGradient(x, y, 4, x, y, r);
        g.addColorStop(0, color);
        g.addColorStop(1, "rgba(0,0,0,0)");
        ctx.fillStyle = g;
        ctx.beginPath();
        ctx.arc(x, y, r, 0, Math.PI * 2);
        ctx.fill();
      }
      const mountain = ctx.createLinearGradient(0, 250, 0, 430);
      mountain.addColorStop(0, "#17314a");
      mountain.addColorStop(1, "#0a1626");
      ctx.fillStyle = mountain;
      ctx.beginPath();
      ctx.moveTo(0, 430);
      ctx.lineTo(190, 260);
      ctx.lineTo(410, 430);
      ctx.lineTo(520, 430);
      ctx.lineTo(690, 238);
      ctx.lineTo(930, 430);
      ctx.closePath();
      ctx.fill();
      ctx.strokeStyle = "rgba(72,169,255,.18)";
      ctx.lineWidth = 2;
      for (let i = 0; i < 9; i += 1) {
        const y = 62 + i * 38;
        ctx.beginPath();
        ctx.moveTo(-40, y);
        ctx.bezierCurveTo(210, y + 34, 360, y - 38, 610, y + 12);
        ctx.bezierCurveTo(740, y + 38, 880, y - 18, 1040, y + 22);
        ctx.stroke();
      }
      ctx.fillStyle = "rgba(9,20,34,.9)";
      [[160, 300, 198, 140], [714, 292, 218, 148], [398, 332, 132, 108], [560, 354, 96, 85]].forEach(([x, y, bw, bh]) => {
        roundRect(ctx, x, y, bw, bh, 4);
        ctx.fill();
      });
      ctx.fillStyle = "rgba(83,131,184,.46)";
      [[218, 336, 26, 22], [276, 359, 36, 25], [331, 328, 12, 72], [770, 332, 30, 24], [836, 357, 34, 30], [894, 321, 12, 82], [436, 362, 22, 20], [585, 376, 26, 28]].forEach(([x, y, ww, wh]) => ctx.fillRect(x, y, ww, wh));
      ctx.fillStyle = "rgba(0,240,138,.5)";
      for (let i = 0; i < 34; i += 1) {
        ctx.fillRect((i * 137) % w, 72 + ((i * 61) % 275), 2, 2);
      }
    });
    canvasTex("hero", 96, 72, (ctx) => {
      ctx.shadowColor = "rgba(0,240,138,.6)";
      ctx.shadowBlur = 18;
      ctx.fillStyle = "rgba(0,0,0,.35)";
      ctx.beginPath();
      ctx.ellipse(47, 66, 35, 7, 0, 0, Math.PI * 2);
      ctx.fill();
      const armor = ctx.createLinearGradient(21, 16, 64, 62);
      armor.addColorStop(0, "#e9fff8");
      armor.addColorStop(.25, "#29f3bd");
      armor.addColorStop(1, "#138ad9");
      roundRect(ctx, 27, 25, 31, 29, 12);
      ctx.fillStyle = armor;
      ctx.fill();
      ctx.shadowBlur = 0;
      ctx.fillStyle = "#0d1828";
      roundRect(ctx, 34, 33, 18, 17, 6);
      ctx.fill();
      ctx.fillStyle = "#18d5ff";
      roundRect(ctx, 37, 34, 13, 6, 3);
      ctx.fill();
      const helmet = ctx.createLinearGradient(29, 9, 60, 30);
      helmet.addColorStop(0, "#f6fbff");
      helmet.addColorStop(1, "#9bd6f8");
      roundRect(ctx, 27, 9, 35, 23, 10);
      ctx.fillStyle = helmet;
      ctx.fill();
      roundRect(ctx, 32, 15, 26, 7, 4);
      ctx.fillStyle = "#132946";
      ctx.fill();
      ctx.strokeStyle = "rgba(232,255,245,.9)";
      ctx.lineWidth = 3;
      roundRect(ctx, 27.5, 9.5, 34, 22, 10);
      ctx.stroke();
      ctx.strokeStyle = "#14f0a6";
      ctx.lineWidth = 5;
      ctx.lineCap = "round";
      ctx.beginPath();
      ctx.moveTo(28, 46);
      ctx.lineTo(18, 60);
      ctx.moveTo(54, 46);
      ctx.lineTo(64, 61);
      ctx.stroke();
      ctx.strokeStyle = "#ffd55a";
      ctx.lineWidth = 6;
      ctx.beginPath();
      ctx.moveTo(58, 35);
      ctx.lineTo(75, 36);
      ctx.stroke();
      ctx.fillStyle = "#152235";
      roundRect(ctx, 70, 32, 20, 8, 4);
      ctx.fill();
      ctx.strokeStyle = "rgba(0,240,138,.4)";
      ctx.lineWidth = 2;
      roundRect(ctx, 23, 23, 41, 34, 14);
      ctx.stroke();
    });
    canvasTex("trooper", 78, 70, (ctx) => {
      ctx.fillStyle = "rgba(0,0,0,.32)";
      ctx.beginPath();
      ctx.ellipse(39, 65, 28, 6, 0, 0, Math.PI * 2);
      ctx.fill();
      const body = ctx.createLinearGradient(17, 19, 57, 61);
      body.addColorStop(0, "#ff8aa0");
      body.addColorStop(.5, "#e73d62");
      body.addColorStop(1, "#6d1025");
      roundRect(ctx, 22, 26, 34, 29, 12);
      ctx.fillStyle = body;
      ctx.fill();
      roundRect(ctx, 25, 12, 30, 20, 8);
      ctx.fillStyle = "#eff8ff";
      ctx.fill();
      roundRect(ctx, 30, 17, 22, 6, 3);
      ctx.fillStyle = "#271428";
      ctx.fill();
      ctx.strokeStyle = "#f5b2c0";
      ctx.lineWidth = 2;
      roundRect(ctx, 22.5, 26.5, 33, 28, 12);
      ctx.stroke();
      ctx.strokeStyle = "#18243a";
      ctx.lineWidth = 5;
      ctx.lineCap = "round";
      ctx.beginPath();
      ctx.moveTo(24, 42);
      ctx.lineTo(10, 38);
      ctx.stroke();
      ctx.fillStyle = "#1a2534";
      roundRect(ctx, 7, 34, 24, 7, 4);
      ctx.fill();
    });
    canvasTex("shield", 84, 76, (ctx) => {
      ctx.fillStyle = "rgba(0,0,0,.35)";
      ctx.beginPath();
      ctx.ellipse(43, 70, 30, 6, 0, 0, Math.PI * 2);
      ctx.fill();
      const armor = ctx.createLinearGradient(22, 17, 63, 64);
      armor.addColorStop(0, "#f1fbff");
      armor.addColorStop(.55, "#8da7bd");
      armor.addColorStop(1, "#40576d");
      roundRect(ctx, 28, 26, 34, 31, 12);
      ctx.fillStyle = armor;
      ctx.fill();
      const shield = ctx.createLinearGradient(9, 27, 36, 63);
      shield.addColorStop(0, "#8eb6d0");
      shield.addColorStop(1, "#243a52");
      roundRect(ctx, 9, 29, 27, 32, 9);
      ctx.fillStyle = shield;
      ctx.fill();
      ctx.strokeStyle = "#48a9ff";
      ctx.lineWidth = 3;
      ctx.stroke();
      roundRect(ctx, 31, 11, 31, 21, 8);
      ctx.fillStyle = "#f3fbff";
      ctx.fill();
      roundRect(ctx, 36, 16, 22, 6, 3);
      ctx.fillStyle = "#132946";
      ctx.fill();
    });
    canvasTex("drone", 86, 48, (ctx) => {
      ctx.shadowColor = "rgba(72,169,255,.7)";
      ctx.shadowBlur = 14;
      const shell = ctx.createLinearGradient(24, 12, 62, 34);
      shell.addColorStop(0, "#bcecff");
      shell.addColorStop(1, "#248fff");
      ctx.beginPath();
      ctx.ellipse(43, 24, 24, 12, 0, 0, Math.PI * 2);
      ctx.fillStyle = shell;
      ctx.fill();
      ctx.shadowBlur = 0;
      ctx.strokeStyle = "rgba(232,255,245,.8)";
      ctx.lineWidth = 2;
      ctx.stroke();
      ctx.fillStyle = "#00f08a";
      roundRect(ctx, 9, 20, 18, 6, 3);
      ctx.fill();
      roundRect(ctx, 59, 20, 18, 6, 3);
      ctx.fill();
      ctx.fillStyle = "#06101a";
      ctx.beginPath();
      ctx.arc(43, 24, 5, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#ff4d66";
      ctx.beginPath();
      ctx.arc(43, 24, 2, 0, Math.PI * 2);
      ctx.fill();
    });
    canvasTex("boss", 230, 150, (ctx) => {
      ctx.shadowColor = "rgba(255,77,102,.42)";
      ctx.shadowBlur = 24;
      const hull = ctx.createLinearGradient(32, 40, 190, 126);
      hull.addColorStop(0, "#17283f");
      hull.addColorStop(1, "#09111e");
      roundRect(ctx, 28, 42, 166, 86, 22);
      ctx.fillStyle = hull;
      ctx.fill();
      ctx.shadowBlur = 0;
      roundRect(ctx, 55, 17, 84, 45, 14);
      ctx.fillStyle = "#31465f";
      ctx.fill();
      ctx.fillStyle = "#0c1524";
      for (let i = 0; i < 6; i += 1) {
        roundRect(ctx, 44 + i * 22, 53 + (i % 2) * 36, 14, 26, 5);
        ctx.fill();
      }
      const core = ctx.createRadialGradient(102, 81, 4, 102, 81, 23);
      core.addColorStop(0, "#fff3a8");
      core.addColorStop(.35, "#ff4d66");
      core.addColorStop(1, "#5d1022");
      ctx.fillStyle = core;
      ctx.beginPath();
      ctx.arc(102, 81, 22, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#ffc247";
      roundRect(ctx, 8, 76, 42, 14, 6);
      ctx.fill();
      roundRect(ctx, 184, 70, 34, 12, 6);
      ctx.fill();
      ctx.strokeStyle = "rgba(72,169,255,.85)";
      ctx.lineWidth = 4;
      roundRect(ctx, 28.5, 42.5, 165, 85, 22);
      ctx.stroke();
    });
    canvasTex("crate", 64, 64, (ctx) => {
      const wood = ctx.createLinearGradient(5, 5, 59, 59);
      wood.addColorStop(0, "#c98632");
      wood.addColorStop(1, "#6b3a16");
      roundRect(ctx, 5, 5, 54, 54, 6);
      ctx.fillStyle = wood;
      ctx.fill();
      ctx.strokeStyle = "#ffc247";
      ctx.lineWidth = 4;
      ctx.stroke();
      ctx.strokeStyle = "rgba(70,38,16,.72)";
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(14, 14);
      ctx.lineTo(50, 50);
      ctx.moveTo(50, 14);
      ctx.lineTo(14, 50);
      ctx.stroke();
    });
    canvasTex("platform", 128, 34, (ctx) => {
      const deck = ctx.createLinearGradient(0, 4, 0, 31);
      deck.addColorStop(0, "#6f90a9");
      deck.addColorStop(.3, "#30465a");
      deck.addColorStop(1, "#182637");
      roundRect(ctx, 0, 4, 128, 26, 4);
      ctx.fillStyle = deck;
      ctx.fill();
      ctx.strokeStyle = "rgba(170,215,245,.72)";
      ctx.lineWidth = 2;
      ctx.stroke();
      ctx.fillStyle = "rgba(255,255,255,.12)";
      ctx.fillRect(4, 7, 120, 3);
    });
    canvasTex("neonSign", 210, 70, (ctx) => {
      ctx.shadowColor = "rgba(0,240,138,.65)";
      ctx.shadowBlur = 18;
      const shell = ctx.createLinearGradient(0, 0, 210, 70);
      shell.addColorStop(0, "#071321");
      shell.addColorStop(1, "#12263d");
      roundRect(ctx, 4, 7, 202, 56, 12);
      ctx.fillStyle = shell;
      ctx.fill();
      ctx.strokeStyle = "#00f08a";
      ctx.lineWidth = 3;
      ctx.stroke();
      ctx.shadowBlur = 0;
      ctx.fillStyle = "rgba(72,169,255,.4)";
      for (let i = 0; i < 9; i += 1) ctx.fillRect(22 + i * 18, 19, 8, 5);
      ctx.fillStyle = "rgba(255,194,71,.9)";
      ctx.fillRect(22, 38, 146, 4);
    });
    canvasTex("railPost", 36, 92, (ctx) => {
      const metal = ctx.createLinearGradient(0, 0, 36, 0);
      metal.addColorStop(0, "#17283d");
      metal.addColorStop(.5, "#7ba7c5");
      metal.addColorStop(1, "#0d1726");
      ctx.fillStyle = metal;
      roundRect(ctx, 12, 8, 12, 75, 5);
      ctx.fill();
      ctx.fillStyle = "#00f08a";
      roundRect(ctx, 8, 6, 20, 5, 3);
      ctx.fill();
    });
    canvasTex("holoPanel", 86, 120, (ctx) => {
      const panel = ctx.createLinearGradient(0, 0, 0, 120);
      panel.addColorStop(0, "rgba(72,169,255,.55)");
      panel.addColorStop(1, "rgba(0,240,138,.12)");
      ctx.fillStyle = panel;
      roundRect(ctx, 8, 8, 70, 104, 10);
      ctx.fill();
      ctx.strokeStyle = "rgba(232,255,245,.7)";
      ctx.lineWidth = 2;
      ctx.stroke();
      ctx.fillStyle = "rgba(2,8,15,.45)";
      for (let i = 0; i < 6; i += 1) ctx.fillRect(20, 24 + i * 13, 42, 3);
    });
  }

  class RunScene extends Phaser.Scene {
    constructor() {
      super("run");
      this.mode = "title";
      this.score = 0;
      this.hp = 100;
      this.grenades = 3;
      this.facing = 1;
      this.shotCd = 0;
      this.grenadeCd = 0;
      this.hurtCd = 0;
      this.dashCd = 0;
      this.dashTimer = 0;
      this.jumpBufferMs = 0;
      this.coyoteMs = 0;
      this.weaponCycleCd = 0;
      this.weapon = "pulse";
      this.unlockedWeapons = new Set(["pulse"]);
      this.stageIndex = 0;
      this.partIndex = 0;
      this.bossWake = new Set();
    }

    create() {
      makeTextures(this);
      makePremiumTextures(this);
      this.physics.world.setBounds(0, 0, LEVEL_WIDTH, HEIGHT);
      this.cameras.main.setBounds(0, 0, LEVEL_WIDTH, HEIGHT);
      this.sky = this.add.tileSprite(WIDTH / 2, HEIGHT / 2, WIDTH, HEIGHT, "skyTile").setScrollFactor(0).setDepth(-30);
      this.platforms = this.physics.add.staticGroup();
      this.crates = this.physics.add.staticGroup();
      this.enemies = this.physics.add.group();
      this.drones = this.physics.add.group({ allowGravity: false });
      this.bosses = this.physics.add.group({ allowGravity: false });
      this.bullets = this.physics.add.group({ allowGravity: false });
      this.enemyBullets = this.physics.add.group({ allowGravity: false });
      this.grenadeGroup = this.physics.add.group();
      this.pickups = this.physics.add.staticGroup();
      this.createSetDressing();
      this.createLevel();
      this.player = this.physics.add.sprite(150, 330, "hero").setDepth(20);
      this.player.setCollideWorldBounds(true).setDragX(920).setMaxVelocity(520, 900);
      this.player.body.setSize(42, 54).setOffset(22, 14);
      this.cameras.main.startFollow(this.player, true, 0.08, 0.08);
      this.physics.add.collider(this.player, this.platforms);
      this.physics.add.collider(this.player, this.crates);
      this.physics.add.collider(this.enemies, this.platforms);
      this.physics.add.collider(this.crates, this.platforms);
      this.physics.add.collider(this.grenadeGroup, this.platforms);
      this.physics.add.overlap(this.bullets, this.enemies, this.hitEnemy, null, this);
      this.physics.add.overlap(this.bullets, this.drones, this.hitEnemy, null, this);
      this.physics.add.overlap(this.bullets, this.crates, this.hitCrate, null, this);
      this.physics.add.overlap(this.player, this.enemyBullets, this.playerHit, null, this);
      this.physics.add.overlap(this.player, this.pickups, this.takePickup, null, this);
      this.physics.add.overlap(this.player, this.enemies, () => this.damagePlayer(16), null, this);
      this.physics.add.overlap(this.player, this.drones, () => this.damagePlayer(12), null, this);
      this.physics.add.overlap(this.bullets, this.bosses, this.hitBoss, null, this);
      this.physics.add.overlap(this.player, this.bosses, () => this.damagePlayer(20), null, this);
      this.keys = this.input.keyboard.addKeys("A,D,W,S,J,K,Z,X,Q,P,R,SPACE,ENTER,LEFT,RIGHT,UP,DOWN,SHIFT");
      this.input.keyboard.on("keydown-P", () => this.togglePause());
      this.input.keyboard.on("keydown-R", () => this.restart());
      this.input.keyboard.on("keydown-ENTER", () => this.startGame());
      this.input.on("pointerdown", () => this.startGame());
      this.addTouchControls();
      this.overlay = this.add.text(WIDTH / 2, HEIGHT / 2, "", {
        fontFamily: "Consolas, monospace",
        fontSize: "20px",
        color: "#e8fff5",
        align: "center",
        backgroundColor: "rgba(3, 7, 12, 0.72)",
        padding: { x: 22, y: 18 },
      }).setOrigin(0.5).setScrollFactor(0).setDepth(100);
      this.updateHud();
      this.showTitle();
    }

    createLevel() {
      const addPlatform = (x, y, w, h = 34) => {
        const p = this.platforms.create(x, y, "platform").setDisplaySize(w, h).refreshBody();
        p.setDepth(4);
        return p;
      };
      const addCrate = (x, type = "ammo") => {
        const c = this.crates.create(x, GROUND_Y - 32, "crate").refreshBody();
        c.setData({ hp: type === "weapon" ? 48 : 34, type });
        if (type === "weapon") c.setTint(0x48a9ff);
      };
      const troop = (x, stage, part, kind = "trooper") => {
        const key = kind === "shield" || kind === "turret" ? "shield" : "trooper";
        const e = this.enemies.create(x, GROUND_Y - 58, key);
        const hpMap = { trooper: 52, shield: 88, rusher: 46, sniper: 64, grenadier: 70, turret: 105 };
        const tintMap = { trooper: 0xffffff, shield: 0xc9eaff, rusher: 0x00f08a, sniper: 0xffc247, grenadier: 0xb78cff, turret: 0x48a9ff };
        e.setData({ hp: hpMap[kind] + stage * 6, kind, stage, part, dir: -1, shootCd: Phaser.Math.Between(420, 1400) });
        e.setBounce(0).setDragX(kind === "turret" ? 900 : 300).setDepth(15).setTint(tintMap[kind] || 0xffffff);
        e.body.setSize(42, 54).setOffset(18, 12);
        if (kind === "turret") e.setImmovable(true);
      };
      const addDrone = (x, stage, part) => {
        const d = this.drones.create(x, 230 + ((stage + part) % 4) * 18, "drone");
        d.setData({ hp: 44 + stage * 5, stage, part, baseY: d.y, phase: (stage + part) * 0.7, shootCd: Phaser.Math.Between(650, 1500) });
        d.setDepth(18).setTint(STAGE_THEMES[stage].glow);
      };

      for (let stage = 0; stage < STAGE_COUNT; stage += 1) {
        for (let part = 0; part < PARTS_PER_STAGE; part += 1) {
          const base = stage * STAGE_WIDTH + part * PART_WIDTH;
          const center = base + PART_WIDTH / 2;
          addPlatform(center, GROUND_Y + 17, PART_WIDTH + 70, 34);
          addPlatform(base + 230 + (part % 2) * 80, 350 - (stage % 3) * 12, 250 + (stage % 2) * 45);
          addPlatform(base + 610 - (part % 2) * 70, 306 + (part % 3) * 22, 210 + (stage % 3) * 35);
          addPlatform(base + 990 - (stage % 2) * 55, 365 - (part % 3) * 18, 245 + (part % 2) * 50);
          addCrate(base + 250, (stage + part) % 3 === 0 ? "health" : "ammo");
          addCrate(base + 545, (stage + part) % 2 === 0 ? "weapon" : "ammo");
          addCrate(base + 940, (stage + part) % 4 === 0 ? "weapon" : "ammo");
          const enemyKinds = ["trooper", "shield", "rusher", "sniper", "grenadier", "turret"];
          troop(base + 360, stage, part, enemyKinds[(stage + part) % enemyKinds.length]);
          troop(base + 690, stage, part, enemyKinds[(stage * 2 + part + 1) % enemyKinds.length]);
          troop(base + 1050, stage, part, enemyKinds[(stage + part + 3) % enemyKinds.length]);
          if ((stage + part) % 2 === 0) addDrone(base + 775, stage, part);
          if ((stage + part) % 3 === 1) addDrone(base + 1130, stage, part);
          if (part === PARTS_PER_STAGE - 1) {
            const boss = this.bosses.create(base + PART_WIDTH - 170, GROUND_Y - 88, "boss").setImmovable(true).setDepth(22);
            boss.body.setSize(170, 110).setOffset(32, 32);
            boss.setTint(STAGE_THEMES[stage].glow);
            boss.setData({
              hp: 360 + stage * 85,
              maxHp: 360 + stage * 85,
              shootCd: 160,
              phase: stage * 0.25,
              stage,
              name: `Stage ${stage + 1} ${STAGE_THEMES[stage].name} Boss`,
            });
            if (!this.boss) this.boss = boss;
          }
        }
      }
    }

    createSetDressing() {
      for (let stage = 0; stage < STAGE_COUNT; stage += 1) {
        const theme = STAGE_THEMES[stage];
        const base = stage * STAGE_WIDTH;
        const center = base + STAGE_WIDTH / 2;
        this.add.rectangle(center, 270, STAGE_WIDTH, 390, theme.bg, 0.34).setDepth(-24);
        this.add.text(base + 120, 118, `STAGE ${stage + 1}: ${theme.name}`, {
          fontFamily: "Consolas, monospace",
          fontSize: "22px",
          color: "#e8fff5",
          backgroundColor: "rgba(3,7,12,.48)",
          padding: { x: 12, y: 6 },
        }).setDepth(-1);
        for (let part = 0; part < PARTS_PER_STAGE; part += 1) {
          const pbase = base + part * PART_WIDTH;
          this.add.image(pbase + 440, GROUND_Y - 148 - (part % 2) * 35, "neonSign").setDepth(-3).setAlpha(0.76).setTint(theme.glow);
          this.add.image(pbase + 750, GROUND_Y - 190, "holoPanel").setDepth(-2).setAlpha(0.58).setTint(theme.color);
          this.add.text(pbase + 36, GROUND_Y - 96, `${stage + 1}-${part + 1}`, {
            fontFamily: "Consolas, monospace",
            fontSize: "15px",
            color: "#9fd8ff",
          }).setDepth(2);
        }
      }
      for (let x = 120; x < LEVEL_WIDTH; x += 180) {
        this.add.image(x, GROUND_Y - 45, "railPost").setDepth(3).setAlpha(0.45);
      }
    }

    addTouchControls() {
      document.querySelectorAll("[data-control]").forEach((button) => {
        const control = button.getAttribute("data-control");
        const down = (event) => {
          event.preventDefault();
          touch.add(control);
          if (control === "shoot") this.shoot();
          if (control === "grenade") this.throwGrenade();
          if (control === "cycle") this.cycleWeapon();
          this.startGame();
        };
        const up = (event) => {
          event.preventDefault();
          touch.delete(control);
        };
        button.addEventListener("pointerdown", down);
        button.addEventListener("pointerup", up);
        button.addEventListener("pointercancel", up);
        button.addEventListener("pointerleave", up);
      });
    }

    showTitle() {
      this.overlay.setVisible(true).setText(`${GAME_TITLE}\\n\\nOriginal Engel arcade run-and-gun.\\nBreach the route, clear the signal engine, reach extraction.\\n\\nEnter / click / tap to start`);
    }

    startGame() {
      if (this.mode === "title") {
        this.mode = "play";
        this.overlay.setVisible(false);
        this.cameras.main.fadeIn(280, 5, 10, 18);
      }
    }

    togglePause() {
      if (this.mode === "play") {
        this.mode = "pause";
        this.overlay.setVisible(true).setText("PAUSED\\n\\nPress P to resume. Press R to restart.");
      } else if (this.mode === "pause") {
        this.mode = "play";
        this.overlay.setVisible(false);
      }
    }

    restart() {
      this.scene.restart();
    }

    pressed(...names) {
      return names.some((name) => {
        const key = this.keys[name.toUpperCase()];
        return (key && key.isDown) || touch.has(name.toLowerCase());
      });
    }

    justDown(name) {
      const key = this.keys[name.toUpperCase()];
      return key && Phaser.Input.Keyboard.JustDown(key);
    }

    update(time, delta) {
      this.sky.tilePositionX = this.cameras.main.scrollX * 0.18;
      this.updateStageStatus();
      if (this.mode !== "play") return;
      this.handlePlayer(delta);
      this.updateEnemies(delta);
      this.updateDrones(time, delta);
      this.updateBosses(time, delta);
      this.updateProjectiles(delta);
      this.updateHud();
      if (this.hp <= 0) this.endGame(false);
      const remainingBosses = this.bosses.children.entries.filter((boss) => boss.active).length;
      if (remainingBosses === 0 && this.player.x > LEVEL_WIDTH - 260) this.endGame(true);
    }

    updateStageStatus() {
      const stage = Phaser.Math.Clamp(Math.floor(this.player?.x / STAGE_WIDTH), 0, STAGE_COUNT - 1);
      const part = Phaser.Math.Clamp(Math.floor((this.player?.x - stage * STAGE_WIDTH) / PART_WIDTH), 0, PARTS_PER_STAGE - 1);
      if (stage !== this.stageIndex) {
        this.cameras.main.flash(180, 0, 240, 138);
        this.sky.setTint(STAGE_THEMES[stage].color);
      }
      this.stageIndex = stage;
      this.partIndex = part;
    }

    handlePlayer(delta) {
      if (this.shotCd > 0) this.shotCd -= delta;
      if (this.grenadeCd > 0) this.grenadeCd -= delta;
      if (this.hurtCd > 0) this.hurtCd -= delta;
      if (this.dashCd > 0) this.dashCd -= delta;
      if (this.dashTimer > 0) this.dashTimer -= delta;
      if (this.weaponCycleCd > 0) this.weaponCycleCd -= delta;
      if (this.jumpBufferMs > 0) this.jumpBufferMs -= delta;
      const grounded = this.player.body.blocked.down;
      if (grounded) this.coyoteMs = 125;
      else if (this.coyoteMs > 0) this.coyoteMs -= delta;
      const left = this.pressed("left", "a");
      const right = this.pressed("right", "d");
      const crouch = this.pressed("down", "s");
      const sprinting = this.pressed("shift", "dash");
      if ((this.justDown("shift") || touch.has("dash")) && this.dashCd <= 0) {
        this.dashTimer = 155;
        this.dashCd = 680;
        this.cameras.main.shake(55, 0.0018);
      }
      const moveSpeed = this.dashTimer > 0 ? 470 : sprinting ? 325 : 255;
      if (left) {
        this.player.setVelocityX(-moveSpeed);
        this.facing = -1;
      } else if (right) {
        this.player.setVelocityX(moveSpeed);
        this.facing = 1;
      }
      if (this.justDown("space") || this.justDown("w") || this.justDown("up") || touch.has("jump")) {
        this.jumpBufferMs = 145;
      }
      if (this.jumpBufferMs > 0 && this.coyoteMs > 0) {
        this.player.setVelocityY(-565);
        this.jumpBufferMs = 0;
        this.coyoteMs = 0;
      }
      this.player.setFlipX(this.facing < 0);
      this.player.setScale(1, crouch && this.player.body.blocked.down ? 0.82 : 1);
      if (this.justDown("q")) this.cycleWeapon();
      if (this.pressed("shoot", "j", "z")) this.shoot();
      if (this.pressed("grenade", "k", "x")) this.throwGrenade();
    }

    cycleWeapon() {
      if (this.weaponCycleCd > 0) return;
      const unlocked = WEAPON_ORDER.filter((weapon) => this.unlockedWeapons.has(weapon));
      const choices = unlocked.length ? unlocked : ["pulse"];
      const index = choices.indexOf(this.weapon);
      this.weapon = choices[(index + 1 + choices.length) % choices.length];
      this.weaponCycleCd = 180;
      this.burst(this.player.x, this.player.y - 18, 5, WEAPONS[this.weapon].tint);
      this.updateHud();
    }

    shoot() {
      if (this.mode !== "play" || this.shotCd > 0) return;
      const spec = WEAPONS[this.weapon] || WEAPONS.pulse;
      const spawnBullet = (offsetY, velY = 0, scaleX = 1, damage = spec.damage) => {
        const b = this.bullets.create(this.player.x + this.facing * 42, this.player.y - 8 + offsetY, "bullet");
        b.setVelocity(this.facing * spec.speed, velY).setDepth(30).setTint(spec.tint).setData({ damage, explosive: Boolean(spec.explosive), weapon: this.weapon });
        b.body.setSize(24, 6);
        b.setScale(scaleX, this.weapon === "laser" ? 1.35 : 1);
        b.setFlipX(this.facing < 0);
        return b;
      };
      if (this.weapon === "spread") {
        spawnBullet(0, 0, 1.0);
        spawnBullet(-9, -120, 0.92, 16);
        spawnBullet(9, 120, 0.92, 16);
      } else if (this.weapon === "arc") {
        spawnBullet(-4, -80, 1.1, 28);
        spawnBullet(8, 86, 1.1, 28);
      } else if (this.weapon === "rocket") {
        spawnBullet(0, -18, 1.45, spec.damage);
      } else if (this.weapon === "laser") {
        spawnBullet(0, 0, 2.15, spec.damage);
      } else {
        spawnBullet(0);
      }
      this.shotCd = spec.cooldown;
    }

    throwGrenade() {
      if (this.mode !== "play" || this.grenades <= 0 || this.grenadeCd > 0) return;
      this.grenades -= 1;
      const g = this.grenadeGroup.create(this.player.x + this.facing * 28, this.player.y - 24, "grenade");
      g.setVelocity(this.facing * 370, -365).setBounce(0.52).setDragX(35).setDepth(28).setData({ timer: 880 });
      this.grenadeCd = 430;
    }

    updateEnemies(delta) {
      this.enemies.children.iterate((enemy) => {
        if (!enemy || !enemy.active) return;
        const dx = this.player.x - enemy.x;
        const kind = enemy.getData("kind") || "trooper";
        const near = Math.abs(dx) < (kind === "sniper" || kind === "turret" ? 940 : 720);
        if (kind === "rusher") enemy.setVelocityX(near ? Math.sign(dx) * 105 : -55);
        else if (kind === "turret" || kind === "sniper") enemy.setVelocityX(0);
        else enemy.setVelocityX(near ? Math.sign(dx) * (kind === "shield" ? 28 : 42) : -30);
        enemy.setFlipX(dx < 0);
        enemy.setData("shootCd", enemy.getData("shootCd") - delta);
        if (near && enemy.getData("shootCd") <= 0) {
          const dir = Math.sign(dx) || -1;
          const damage = kind === "sniper" ? 20 : kind === "grenadier" ? 18 : kind === "shield" ? 16 : 12;
          this.fireEnemy(enemy.x, enemy.y - 12, dir, damage, kind === "grenadier" ? 18 : 0);
          if (kind === "grenadier") this.time.delayedCall(130, () => this.fireEnemy(enemy.x, enemy.y - 3, dir, 12, -18));
          enemy.setData("shootCd", kind === "turret" ? 760 : kind === "sniper" ? 1750 : kind === "shield" ? 1150 : 1450);
        }
      });
    }

    updateDrones(time, delta) {
      this.drones.children.iterate((drone) => {
        if (!drone || !drone.active) return;
        drone.setData("phase", drone.getData("phase") + delta * 0.004);
        drone.y = drone.getData("baseY") + Math.sin(drone.getData("phase")) * 28;
        const dx = this.player.x - drone.x;
        drone.x += Phaser.Math.Clamp(dx, -1, 1) * 0.45;
        drone.setData("shootCd", drone.getData("shootCd") - delta);
        if (Math.abs(dx) < 780 && drone.getData("shootCd") <= 0) {
          this.fireEnemy(drone.x, drone.y + 12, Math.sign(dx) || -1, 10);
          drone.setData("shootCd", 1350);
        }
      });
    }

    updateBosses(time, delta) {
      this.bosses.children.iterate((boss) => {
        if (!boss || !boss.active || this.player.x < boss.x - 820) return;
        const stage = boss.getData("stage") || 0;
        const wakeKey = `boss-${stage}`;
        if (!this.bossWake.has(wakeKey)) {
          this.bossWake.add(wakeKey);
          this.cameras.main.shake(220, 0.006);
          this.overlay.setVisible(true).setText(`${boss.getData("name")}\\n\\nBoss signal detected. Clear it to complete Stage ${stage + 1}.`);
          this.time.delayedCall(1300, () => {
            if (this.mode === "play") this.overlay.setVisible(false);
          });
        }
        boss.setData("phase", boss.getData("phase") + delta * 0.003);
        boss.y = GROUND_Y - 88 + Math.sin(boss.getData("phase")) * 10;
        boss.setData("shootCd", boss.getData("shootCd") - delta);
        if (boss.getData("shootCd") <= 0) {
          const dir = this.player.x < boss.x ? -1 : 1;
          this.fireEnemy(boss.x + dir * 70, boss.y - 20, dir, 16 + stage);
          this.time.delayedCall(180, () => this.fireEnemy(boss.x + dir * 70, boss.y + 8, dir, 16 + stage));
          if (stage > 4) this.time.delayedCall(320, () => this.fireEnemy(boss.x + dir * 70, boss.y + 28, dir, 12 + stage, 28));
          boss.setData("shootCd", boss.getData("hp") < boss.getData("maxHp") * 0.45 ? 680 : 1040);
        }
      });
    }

    fireEnemy(x, y, dir, damage, velY = 0) {
      const b = this.enemyBullets.create(x, y, "enemyBullet");
      b.setVelocity(dir * 360, velY).setDepth(27).setData({ damage });
      b.setFlipX(dir < 0);
    }

    updateProjectiles(delta) {
      this.bullets.children.iterate((b) => {
        if (b && b.active && Math.abs(b.x - this.player.x) > 980) b.destroy();
      });
      this.enemyBullets.children.iterate((b) => {
        if (b && b.active && Math.abs(b.x - this.player.x) > 1100) b.destroy();
      });
      this.grenadeGroup.children.iterate((g) => {
        if (!g || !g.active) return;
        g.setData("timer", g.getData("timer") - delta);
        if (g.getData("timer") <= 0) this.explode(g.x, g.y, g);
      });
    }

    hitEnemy(bullet, enemy) {
      const x = bullet.x;
      const y = bullet.y;
      const explosive = bullet.getData("explosive");
      const damage = bullet.getData("damage") || 20;
      bullet.destroy();
      if (explosive) {
        this.explode(x, y, null, 130);
        return;
      }
      this.damageTarget(enemy, damage);
    }

    hitBoss(bullet, boss) {
      const x = bullet.x;
      const y = bullet.y;
      const damage = bullet.getData("damage") || 20;
      const explosive = bullet.getData("explosive");
      bullet.destroy();
      if (explosive) this.explode(x, y, null, 120);
      const hp = boss.getData("hp") - damage;
      boss.setData("hp", hp);
      this.burst(x, y, 8, 0xff4d66);
      if (hp <= 0) {
        this.score += 600 + (boss.getData("stage") || 0) * 150;
        this.explode(boss.x, boss.y, boss, 150);
        boss.destroy();
      }
    }

    hitCrate(bullet, crate) {
      const x = bullet.x;
      const y = bullet.y;
      const explosive = bullet.getData("explosive");
      bullet.destroy();
      if (explosive) {
        this.explode(x, y, null, 112);
        return;
      }
      const hp = crate.getData("hp") - 22;
      crate.setData("hp", hp);
      this.burst(crate.x, crate.y, 5, 0xffc247);
      if (hp <= 0) this.breakCrate(crate);
    }

    damageTarget(target, amount) {
      const hp = target.getData("hp") - amount;
      target.setData("hp", hp);
      this.burst(target.x, target.y, 8, 0xff4d66);
      if (hp <= 0) {
        this.score += target.texture.key === "drone" ? 95 : 65;
        target.destroy();
      }
    }

    breakCrate(crate) {
      const type = crate.getData("type") || "ammo";
      this.score += 30;
      this.burst(crate.x, crate.y, 18, 0xffc247);
      const key = type === "health" ? "health" : type === "weapon" ? "upgrade" : "ammo";
      const pickup = this.pickups.create(crate.x, crate.y - 26, key);
      const weapon = WEAPON_ORDER[(this.stageIndex + this.partIndex + Math.floor(crate.x / 200)) % WEAPON_ORDER.length];
      pickup.setData({ type, weapon });
      if (type === "weapon") pickup.setTint(WEAPONS[weapon].tint);
      crate.destroy();
    }

    takePickup(player, pickup) {
      if (pickup.getData("type") === "health") this.hp = Math.min(100, this.hp + 22);
      else if (pickup.getData("type") === "weapon") {
        this.weapon = pickup.getData("weapon") || "spread";
        this.unlockedWeapons.add(this.weapon);
      }
      else this.grenades = Math.min(8, this.grenades + 2);
      this.score += 20;
      this.burst(pickup.x, pickup.y, 10, 0x00f08a);
      pickup.destroy();
    }

    playerHit(player, bullet) {
      const damage = bullet.getData("damage") || 10;
      bullet.destroy();
      this.damagePlayer(damage);
    }

    damagePlayer(amount) {
      if (this.hurtCd > 0 || this.mode !== "play") return;
      this.hp = Math.max(0, this.hp - amount);
      this.hurtCd = 560;
      this.player.setTint(0xff6b7d);
      this.time.delayedCall(120, () => this.player.clearTint());
      this.cameras.main.shake(120, 0.004);
    }

    explode(x, y, source, radius = 118) {
      if (source && source.active) source.destroy();
      this.burst(x, y, 34, 0xffd55a);
      this.cameras.main.shake(140, 0.005);
      const hitCircle = new Phaser.Geom.Circle(x, y, radius);
      const hitGroup = (group, damage) => group.children.iterate((item) => {
        if (item && item.active && Phaser.Geom.Circle.Contains(hitCircle, item.x, item.y)) this.damageTarget(item, damage);
      });
      hitGroup(this.enemies, 80);
      hitGroup(this.drones, 80);
      this.crates.children.iterate((crate) => {
        if (crate && crate.active && Phaser.Geom.Circle.Contains(hitCircle, crate.x, crate.y)) this.breakCrate(crate);
      });
      this.bosses.children.iterate((boss) => {
        if (!boss || !boss.active || !Phaser.Geom.Circle.Contains(hitCircle, boss.x, boss.y)) return;
        boss.setData("hp", boss.getData("hp") - 80);
        if (boss.getData("hp") <= 0) boss.destroy();
      });
    }

    burst(x, y, count, tint) {
      for (let i = 0; i < count; i += 1) {
        const s = this.add.image(x, y, "spark").setTint(tint).setDepth(50);
        this.tweens.add({
          targets: s,
          x: x + Phaser.Math.Between(-80, 80),
          y: y + Phaser.Math.Between(-70, 50),
          alpha: 0,
          scale: 0.15,
          duration: Phaser.Math.Between(280, 620),
          onComplete: () => s.destroy(),
        });
      }
    }

    updateHud() {
      hud.hp.textContent = String(Math.max(0, Math.round(this.hp)));
      hud.score.textContent = String(this.score);
      hud.grenades.textContent = String(this.grenades);
      hud.weapon.textContent = (WEAPONS[this.weapon] || WEAPONS.pulse).label;
      hud.stage.textContent = `${this.stageIndex + 1}-${this.partIndex + 1}`;
    }

    endGame(won) {
      if (this.mode === "win" || this.mode === "lose") return;
      this.mode = won ? "win" : "lose";
      this.overlay.setVisible(true).setText(won
        ? "CAMPAIGN CLEARED\\n\\nAll 10 stage bosses are down. Engel extraction complete.\\n\\nPress R to run again."
        : "SIGNAL LOST\\n\\nThe route overwhelmed the team.\\n\\nPress R to restart.");
    }
  }

  const config = {
    type: Phaser.AUTO,
    parent: "game-host",
    width: WIDTH,
    height: HEIGHT,
    backgroundColor: "#07101e",
    scale: { mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH },
    physics: {
      default: "arcade",
      arcade: { gravity: { y: 1250 }, debug: false },
    },
    scene: RunScene,
  };

  window.engelGame = new Phaser.Game(config);
})();
"""
    readme = "\n".join([
        "# " + title,
        "",
        "Open `index.html` in a browser to run the game.",
        "",
        "## Engine",
        "",
        "- Phaser 3.90.0 is bundled locally in `vendor/phaser.min.js`.",
        "- No CDN is required at play time.",
        "- Graphics are generated as polished vector-style Phaser textures at runtime; no copied franchise assets are used.",
        "",
        "## Controls",
        "",
        "- A/D or arrow keys: move",
        "- Hold Shift: sprint; tap Shift: dash burst",
        "- W/Space: jump",
        "- S/Down: crouch",
        "- J/Z: shoot",
        "- K/X: grenade",
        "- Q: cycle unlocked weapon",
        "- P: pause",
        "- R: restart",
        "- Touch controls appear on mobile/touch screens.",
        "",
        "## Features",
        "",
        "- Side-scrolling level with parallax backdrop",
        "- 10-stage campaign with 5 longer parts per stage and unique background settings",
        "- Boss encounter at the end of every stage",
        "- Physics movement, dash/sprint, jump buffering, coyote-time jumping, crouching, shooting, and grenades",
        "- Weapon upgrades: pulse, spread, laser, rocket, and arc shots",
        "- Weapon cycling across unlocked upgrades",
        "- Troopers, shield units, rushers, snipers, grenadiers, turrets, drones, destructible crates, and pickups",
        "- Win/lose states, pause, HUD, touch controls, camera shake, and particle bursts",
        "",
        "## Original Request",
        _clip(prompt, MAX_PROMPT_CHARS),
        "",
        "## Meeting Room Context",
        context or "No agent preview was attached.",
        "",
        "## IP Safety",
        "This is an original Engel-branded game package. It may be inspired by the broad arcade run-and-gun genre, but it does not copy Metal Slug/SNK names, characters, sprites, screenshots, logos, maps, sounds, or assets.",
        "",
    ])
    runtime_file = _copy_game_runtime(out_dir)
    files = [
        _write_text(out_dir / "index.html", html),
        _write_text(out_dir / "style.css", css),
        _write_text(out_dir / "game.js", js),
        _write_text(out_dir / "README.md", readme),
        runtime_file,
    ]
    return files, f"Created Phaser browser game: {out_dir / 'index.html'}"


def _image_palette(prompt: str) -> tuple[str, str, str]:
    low = str(prompt or "").lower()
    if "yellow" in low:
        return "#ffd83d", "#06121f", "#00eb7a"
    if "green" in low:
        return "#00eb7a", "#06121f", "#8b5cf6"
    if "blue" in low:
        return "#48a7ff", "#06121f", "#00eb7a"
    return "#ffd83d", "#06121f", "#00eb7a"


def _create_image(prompt: str, out_dir: Path, context: str) -> tuple[list[Path], str]:
    title = _title_from_prompt(prompt, "Engel Visual")
    face, ink, accent = _image_palette(prompt)
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="960" height="640" viewBox="0 0 960 640">
  <rect width="960" height="640" fill="#050814"/>
  <rect x="80" y="64" width="800" height="512" rx="22" fill="#0b1020" stroke="{accent}" stroke-width="8"/>
  <circle cx="480" cy="300" r="170" fill="{face}" stroke="{accent}" stroke-width="12"/>
  <circle cx="420" cy="252" r="24" fill="{ink}"/>
  <circle cx="540" cy="252" r="24" fill="{ink}"/>
  <path d="M375 336 C420 430 540 430 585 336" fill="none" stroke="{ink}" stroke-width="18" stroke-linecap="round"/>
  <path d="M240 500 H720" fill="none" stroke="#8b5cf6" stroke-width="5" stroke-linecap="round" opacity="0.75"/>
  <text x="480" y="550" text-anchor="middle" font-family="Consolas, monospace" font-size="30" fill="{accent}">ENGEL AI VISUAL RESULT</text>
</svg>
"""
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html_lib.escape(title)}</title>
  <style>
    body {{ margin: 0; min-height: 100vh; display: grid; place-items: center; background: #050814; }}
    main {{ width: min(960px, 96vw); }}
    img {{ display: block; width: 100%; height: auto; border: 1px solid #1f2a44; }}
  </style>
</head>
<body>
  <main><img src="engel_visual.svg" alt="{html_lib.escape(title)}"></main>
</body>
</html>
"""
    readme = "\n".join([
        f"# {title}",
        "",
        "Generated by Engel AI after Meeting Room routing.",
        "",
        "## Request",
        _clip(prompt, MAX_PROMPT_CHARS),
        "",
        "## Agent Notes",
        context or "No agent preview was attached to this result.",
        "",
        "## Result",
        "This is a real local SVG image artifact plus an HTML preview.",
    ])
    files = [
        _write_text(out_dir / "engel_visual.svg", svg),
        _write_text(out_dir / "index.html", html),
        _write_text(out_dir / "README.md", readme),
    ]
    return files, f"Created visual image artifact: {out_dir / 'engel_visual.svg'}"


def _create_language(prompt: str, out_dir: Path, context: str) -> tuple[list[Path], str]:
    title = _title_from_prompt(prompt, "Engel App Language Pass")
    body = "\n".join([
        "# " + title,
        "",
        "## Clear UI Language",
        "- Main action: Send work to Engel.",
        "- Meeting Room status: Agents are selecting devices and preparing a candidate result.",
        "- Result status: Engel created a reviewable local artifact.",
        "- Phone worker status: Device candidate returned; main Engel finalized the file.",
        "",
        "## Short Button Labels",
        "- Send",
        "- Open Meeting Room",
        "- Show Results",
        "- Export",
        "- Clear",
        "",
        "## User-Facing Result Copy",
        "Engel finished the agent pass and created files you can open locally.",
        "",
        "## Original Request",
        _clip(prompt, MAX_PROMPT_CHARS),
        "",
        "## Agent Context",
        context or "No agent preview was attached.",
        "",
    ])
    path = _write_text(out_dir / "app_language_pass.md", body)
    return [path], f"Created app language pass: {path}"


def _clean_search_query(prompt: str) -> str:
    query = re.sub(r"\b(search|internet|online|web|look up|look online|for any that would be help|help to the project)\b", " ", str(prompt or ""), flags=re.I)
    query = re.sub(r"\s+", " ", query).strip()
    return query or "Engel AI local first agent device workers"


def _web_search(query: str, limit: int = 5) -> tuple[list[dict[str, str]], str]:
    url = "https://duckduckgo.com/html/?q=" + urllib.parse.quote_plus(query)
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 EngelAI/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=6) as response:
            page = response.read(700000).decode("utf-8", "replace")
    except Exception as exc:
        return [], f"live search failed: {type(exc).__name__}: {exc}"
    results: list[dict[str, str]] = []
    for match in re.finditer(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', page, flags=re.I | re.S):
        href = html_lib.unescape(match.group(1))
        parsed = urllib.parse.urlparse(href)
        if "uddg" in urllib.parse.parse_qs(parsed.query):
            href = urllib.parse.parse_qs(parsed.query)["uddg"][0]
        title = re.sub(r"<[^>]+>", "", match.group(2))
        title = html_lib.unescape(re.sub(r"\s+", " ", title)).strip()
        if title and href:
            results.append({"title": title, "url": href})
        if len(results) >= limit:
            break
    return results, "ok" if results else "no results parsed"


def _create_research(prompt: str, out_dir: Path, context: str) -> tuple[list[Path], str]:
    query = _clean_search_query(prompt)
    results, status = _web_search(query)
    lines = [
        "# Engel Web Research Brief",
        "",
        f"Query: `{query}`",
        f"Search status: {status}",
        "",
        "## Results",
    ]
    if results:
        for idx, result in enumerate(results, start=1):
            lines.append(f"{idx}. [{result['title']}]({result['url']})")
    else:
        lines.append("- No live results were captured. Keep this brief as a research task record.")
    lines.extend([
        "",
        "## Agent Context",
        context or "No agent preview was attached.",
        "",
        "## Original Request",
        _clip(prompt, MAX_PROMPT_CHARS),
        "",
        "Safety: this file is a research artifact only. It does not install, execute, or mutate project code.",
    ])
    path = _write_text(out_dir / "research_brief.md", "\n".join(lines))
    return [path], f"Created web research brief: {path}"


def _create_code(prompt: str, out_dir: Path, context: str) -> tuple[list[Path], str]:
    title = _title_from_prompt(prompt, "Engel Generated Helper")
    module_name = _slug(title, limit=38) + ".py"
    code = f'''#!/usr/bin/env python3
"""Generated by Engel AI as a reviewable code artifact.

Request:
{_clip(prompt, 900)}
"""
from __future__ import annotations


def describe_request() -> str:
    return {prompt[:900]!r}


def main() -> None:
    print("Engel generated helper")
    print(describe_request())


if __name__ == "__main__":
    main()
'''
    notes = "\n".join([
        "# Review Notes",
        "",
        "This code artifact is not auto-applied to Engel source.",
        "Run or merge it only after human review.",
        "",
        "## Meeting Room Context",
        context or "No agent preview was attached.",
        "",
    ])
    files = [
        _write_text(out_dir / module_name, code),
        _write_text(out_dir / "REVIEW_NOTES.md", notes),
    ]
    return files, f"Created reviewable code artifact: {out_dir / module_name}"


def _create_file(prompt: str, out_dir: Path, context: str) -> tuple[list[Path], str]:
    title = _title_from_prompt(prompt, "Engel Requested File")
    body = "\n".join([
        "# " + title,
        "",
        "Created from Engel UI as a local artifact.",
        "",
        "## Request",
        _clip(prompt, MAX_PROMPT_CHARS),
        "",
        "## Meeting Room Context",
        context or "No agent preview was attached.",
        "",
    ])
    path = _write_text(out_dir / "requested_file.md", body)
    return [path], f"Created requested file: {path}"


def _title_from_prompt(prompt: str, fallback: str) -> str:
    text = re.sub(r"\s+", " ", str(prompt or "")).strip()
    text = re.sub(r"^(please\s+)?(make|create|write|generate|draft|build)\s+(me\s+)?", "", text, flags=re.I)
    text = text.strip(" .,:;-")
    if not text:
        return fallback
    return text[:70].strip().title()


def execute_ui_result_request(
    prompt: str,
    meeting_summary: str = "",
    returned_previews: list[str] | None = None,
) -> dict[str, Any]:
    """Create a real local artifact for clear Engel UI file/build requests."""
    prompt = str(prompt or "")[:MAX_PROMPT_CHARS]
    kind = _infer_kind(prompt)
    if not kind:
        return {"accepted": False, "reason": "no executable artifact requested"}
    if _rust_generator_enabled():
        try:
            from engel_rust_executable_results_bridge import execute_rust_ui_result_request
            rust_result = execute_rust_ui_result_request(
                prompt,
                meeting_summary=meeting_summary,
                returned_previews=returned_previews,
            )
            if rust_result.get("accepted") or _rust_generator_strict():
                return rust_result
        except Exception:
            if _rust_generator_strict():
                raise
    out_dir = _make_artifact_dir(kind, prompt)
    context = _context_block(meeting_summary, returned_previews)
    notes = [
        "Generated after Engel UI -> Meeting Room routing.",
        "Artifacts are local files; generated code is not auto-executed.",
        "Phone worker previews are context only and remain review-required.",
    ]
    creators = {
        "pdf": _create_pdf,
        "image": _create_image,
        "game": _create_game,
        "language": _create_language,
        "research": _create_research,
        "code": _create_code,
        "file": _create_file,
    }
    files, summary = creators[kind](prompt, out_dir, context)
    manifest = _manifest(kind, prompt, out_dir, files, notes)
    all_files = files + [manifest]
    return {
        "accepted": True,
        "kind": kind,
        "artifact_dir": str(out_dir),
        "files": [str(path) for path in all_files],
        "summary": summary,
        "notes": notes,
    }
