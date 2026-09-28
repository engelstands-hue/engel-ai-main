#!/usr/bin/env python3
"""
Engel AI Main — workspace / programming-environment scaffolder.

This is the first real ACTION capability wired into Engel's chat: when Joshua asks
Engel to "set up / create the <X> programming environment (or workspace/project)",
Engel actually creates a working workspace on disk instead of only talking about it.

It is deliberately BOUNDED and non-destructive: it only CREATES a new workspace
folder under `workspaces/` with starter files. It never overwrites an existing
folder, never installs packages, and never runs arbitrary shell commands (those
belong behind the sandbox + confirmation flow). Reusable + testable on its own.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACES_DIR = ROOT / "workspaces"


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return s[:48] or "workspace"


def _readme_title(dest: Path) -> str:
    """The `# title` line write_project stamps into README.md, casefolded ('' if unreadable)."""
    try:
        first = (dest / "README.md").read_text(encoding="utf-8").splitlines()[0]
        return first.lstrip("#").strip().casefold()
    except Exception:
        return ""


def _resolve_dest(description: str, name: str = "") -> "tuple[Path, str]":
    """Where a project for this description lives. The 48-char slug truncation can
    collide two DIFFERENT requests ('...prints the first 12 fibonacci...' vs
    '...prints the first 15 primes...'); when the existing dir's README title says
    it belongs to another request, this one gets its own deterministic home
    (truncated slug + short description hash) instead of a false 'already exists'."""
    slug = _slug(name) if name else _slug(description)
    dest = WORKSPACES_DIR / slug
    title = (description or slug).strip()
    if dest.exists():
        stored = _readme_title(dest)
        if stored and stored != title.casefold():
            suffix = hashlib.sha1(title.casefold().encode("utf-8")).hexdigest()[:6]
            dest = WORKSPACES_DIR / f"{slug[:41]}_{suffix}"
    return dest, title


def peek_project(description: str, *, name: str = "") -> dict:
    """Where write_project WOULD land, without writing — lets the build lane skip
    an expensive provider generation when the build already exists."""
    dest, _title = _resolve_dest(description, name)
    return {"path": str(dest), "exists": dest.exists()}


def classify(description: str) -> str:
    """Map a free-text request to a known workspace kind."""
    low = str(description or "").lower()
    if any(t in low for t in ("trig", "trigonometr", "sine", "cosine", "angle", "geometry")):
        return "math_trig"
    if any(t in low for t in ("web", "website", "flask", "html", "frontend", "react")):
        return "web"
    if any(t in low for t in ("data", "pandas", "dataframe", "analytics", "csv", "ml", "machine learning")):
        return "data"
    return "python"


# ---- templates -------------------------------------------------------------

_TRIG_TRIG_PY = '''"""Trigonometric programming toolkit (Engel trig_env).

Degree-first helpers plus exact/symbolic work via sympy. numpy/sympy/scipy are
already installed in the Engel runtime python.
"""
from __future__ import annotations

import math
import numpy as np
import sympy as sp


# --- angle conversion -------------------------------------------------------
def deg2rad(deg: float) -> float:
    return math.radians(deg)


def rad2deg(rad: float) -> float:
    return math.degrees(rad)


# --- degree-based trig (what most people actually want) ---------------------
def sin_d(deg: float) -> float:
    return math.sin(math.radians(deg))


def cos_d(deg: float) -> float:
    return math.cos(math.radians(deg))


def tan_d(deg: float) -> float:
    return math.tan(math.radians(deg))


def asin_d(x: float) -> float:
    return math.degrees(math.asin(x))


def acos_d(x: float) -> float:
    return math.degrees(math.acos(x))


def atan2_d(y: float, x: float) -> float:
    return math.degrees(math.atan2(y, x))


# --- unit circle ------------------------------------------------------------
def unit_circle_point(deg: float) -> tuple[float, float]:
    """(x, y) on the unit circle at `deg` degrees."""
    return (round(cos_d(deg), 12), round(sin_d(deg), 12))


def unit_circle_table(step_deg: int = 30) -> list[tuple[int, float, float]]:
    return [(d, *unit_circle_point(d)) for d in range(0, 361, step_deg)]


# --- triangle solvers -------------------------------------------------------
def right_triangle(*, opposite: float | None = None, adjacent: float | None = None,
                   hypotenuse: float | None = None) -> dict:
    """Solve a right triangle from any two of opposite/adjacent/hypotenuse."""
    o, a, h = opposite, adjacent, hypotenuse
    if o is not None and a is not None:
        h = math.hypot(o, a)
    elif o is not None and h is not None:
        a = math.sqrt(max(h * h - o * o, 0.0))
    elif a is not None and h is not None:
        o = math.sqrt(max(h * h - a * a, 0.0))
    else:
        raise ValueError("provide exactly two of opposite/adjacent/hypotenuse")
    return {
        "opposite": round(o, 10), "adjacent": round(a, 10), "hypotenuse": round(h, 10),
        "angle_deg": round(atan2_d(o, a), 6),
    }


def law_of_cosines(a: float, b: float, angle_C_deg: float) -> float:
    """Side c opposite angle C, given sides a, b and included angle C."""
    return math.sqrt(a * a + b * b - 2 * a * b * cos_d(angle_C_deg))


def law_of_sines_side(a: float, angle_A_deg: float, angle_B_deg: float) -> float:
    """Side b, given side a and its opposite angle A plus angle B."""
    return a * sin_d(angle_B_deg) / sin_d(angle_A_deg)


# --- symbolic / exact -------------------------------------------------------
def exact(deg: int):
    """Exact symbolic value of sin/cos/tan at an integer degree (via sympy)."""
    x = sp.rad(deg)
    return {"sin": sp.simplify(sp.sin(x)), "cos": sp.simplify(sp.cos(x)), "tan": sp.simplify(sp.tan(x))}


def verify_identity(lhs: str, rhs: str) -> bool:
    """True if the two sympy expressions (in theta) are identically equal."""
    theta = sp.symbols("theta")
    ns = {"theta": theta, "sin": sp.sin, "cos": sp.cos, "tan": sp.tan, "sec": sp.sec, "csc": sp.csc, "cot": sp.cot}
    return bool(sp.simplify(sp.sympify(lhs, locals=ns) - sp.sympify(rhs, locals=ns)) == 0)


# --- vectorized (numpy) -----------------------------------------------------
def sample_wave(freq: float = 1.0, n: int = 361):
    """Return (degrees, sin values) sampled over one turn — handy for plots/tables."""
    deg = np.linspace(0, 360, n)
    return deg, np.sin(np.radians(freq * deg))
'''

_TRIG_DEMO_PY = '''"""Runnable demo of the trig toolkit. `python demo.py`"""
import trig

print("== angle conversion ==")
print(" 30 deg =", round(trig.deg2rad(30), 6), "rad")
print("  pi/6  =", round(trig.rad2deg(3.141592653589793 / 6), 6), "deg")

print("\\n== degree trig ==")
for d in (0, 30, 45, 60, 90):
    print(f"  sin({d:2}deg)={trig.sin_d(d):+.4f}  cos={trig.cos_d(d):+.4f}  tan={trig.tan_d(d) if d != 90 else float('inf'):+.4f}")

print("\\n== unit circle ==")
for d, x, y in trig.unit_circle_table(45):
    print(f"  {d:3}deg -> ({x:+.3f}, {y:+.3f})")

print("\\n== right triangle (opp=3, adj=4) ==")
print(" ", trig.right_triangle(opposite=3, adjacent=4))

print("\\n== law of cosines (a=5,b=7,C=60deg) ==")
print("  c =", round(trig.law_of_cosines(5, 7, 60), 6))

print("\\n== exact values (sympy) ==")
print("  sin(30)=", trig.exact(30)["sin"], " cos(45)=", trig.exact(45)["cos"])

print("\\n== identity check: sin^2 + cos^2 == 1 ->",
      trig.verify_identity("sin(theta)**2 + cos(theta)**2", "1"))
'''

_TRIG_REPL_PY = '''"""Interactive trig calculator REPL. `python repl.py`
Type a degree angle (e.g. 30) for sin/cos/tan, or a python expression using the
trig helpers (e.g. right_triangle(opposite=3, adjacent=4)). 'q' to quit."""
import trig

HELP = {k: getattr(trig, k) for k in dir(trig) if not k.startswith("_")}


def main() -> None:
    print("Engel trig REPL — enter an angle in degrees, or a trig expression. 'q' quits.")
    while True:
        try:
            line = input("trig> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if line.lower() in ("q", "quit", "exit"):
            break
        if not line:
            continue
        try:
            if line.replace(".", "", 1).replace("-", "", 1).isdigit():
                d = float(line)
                print(f"  sin={trig.sin_d(d):+.6f}  cos={trig.cos_d(d):+.6f}  tan={trig.tan_d(d):+.6f}")
            else:
                print("  ", eval(line, {"__builtins__": {}}, HELP))  # noqa: S307 (local trig helpers only)
        except Exception as exc:  # noqa: BLE001
            print("  error:", exc)


if __name__ == "__main__":
    main()
'''

_TRIG_README = '''# Trigonometric programming environment (Engel trig_env)

Created by Engel AI Main. Uses the Engel runtime python (numpy / sympy / scipy
already installed) — no extra install needed.

## Run
```
cd workspaces/trig_env
..\\..\\runtime\\python310\\python.exe demo.py     # examples
..\\..\\runtime\\python310\\python.exe repl.py     # interactive trig calculator
```

## Files
- `trig.py`  — the toolkit: `sin_d/cos_d/tan_d` (degrees), `deg2rad/rad2deg`,
  `unit_circle_point`, `right_triangle`, `law_of_cosines`, `law_of_sines_side`,
  `exact` (symbolic sympy values), `verify_identity`, `sample_wave` (numpy).
- `demo.py` — runnable examples.
- `repl.py` — interactive calculator.
- `requirements.txt` — deps (already present in the Engel runtime).

## Examples
```python
import trig
trig.sin_d(30)                       # 0.4999999999999999
trig.unit_circle_point(45)           # (0.7071..., 0.7071...)
trig.right_triangle(opposite=3, adjacent=4)   # -> hypotenuse 5.0, angle 36.87deg
trig.exact(30)["sin"]                # 1/2  (exact, via sympy)
```
'''

_TRIG_REQS = "numpy>=1.26\nsympy>=1.12\nscipy>=1.11\n"

_GENERIC_MAIN = '''"""{title} — starter workspace created by Engel AI Main."""


def main() -> None:
    print("{title} workspace is ready. Add your code in this file.")


if __name__ == "__main__":
    main()
'''

_GENERIC_README = "# {title}\n\nStarter workspace created by Engel AI Main. Uses the Engel runtime python.\n\n## Run\n```\n..\\..\\runtime\\python310\\python.exe main.py\n```\n"


def _files_for(kind: str, title: str) -> dict[str, str]:
    if kind == "math_trig":
        return {
            "trig.py": _TRIG_TRIG_PY,
            "demo.py": _TRIG_DEMO_PY,
            "repl.py": _TRIG_REPL_PY,
            "README.md": _TRIG_README,
            "requirements.txt": _TRIG_REQS,
        }
    return {
        "main.py": _GENERIC_MAIN.format(title=title),
        "README.md": _GENERIC_README.format(title=title),
    }


def scaffold(description: str, *, name: str = "", overwrite: bool = False) -> dict:
    """Create a workspace for the described environment. Non-destructive."""
    kind = classify(description)
    default_name = "trig_env" if kind == "math_trig" else _slug(name or description)
    slug = _slug(name) if name else default_name
    dest = WORKSPACES_DIR / slug
    title = description.strip() or slug
    if dest.exists() and not overwrite:
        existing = sorted(p.name for p in dest.iterdir()) if dest.is_dir() else []
        return {
            "ok": True, "already_exists": True, "kind": kind,
            "path": str(dest), "files": existing,
            "note": f"'{slug}' already exists — left it untouched. Repeat the setup order with the word 'overwrite' to replace it.",
        }
    dest.mkdir(parents=True, exist_ok=True)
    files = _files_for(kind, title)
    for fname, content in files.items():
        (dest / fname).write_text(content, encoding="utf-8")
    return {
        "ok": True, "created": True, "kind": kind, "path": str(dest),
        "files": sorted(files.keys()),
        "note": f"Created a {kind} workspace at {dest} with {len(files)} files.",
    }


def write_program(description: str, code: str, *, name: str = "",
                  entry: str = "main.py", overwrite: bool = False) -> dict:
    """Back-compat single-file shim over write_project(). The build lane now always
    goes through write_project (which handles one OR many files with the right run
    command), so this just wraps a single Python entry file to avoid a second copy of
    the slug/dest/README/not-clobber logic."""
    run_hint = f"..\\..\\runtime\\python310\\python.exe {entry}"
    return write_project(description, {entry: code}, name=name,
                         run_hint=run_hint, overwrite=overwrite)


def write_project(description: str, files: dict[str, str], *, name: str = "",
                  run_hint: str = "", overwrite: bool = False,
                  exact_name: bool = False) -> dict:
    """(2026-07-09) Write a GENERATED multi-file project of any language into a new
    workspace. `files` maps relative path -> contents (e.g. index.html/style.css/
    script.js, or a Python package). Path-escape guarded, non-destructive. `run_hint`
    is the language-appropriate run/build command shown in the README + reply."""
    if exact_name:
        if not name or not re.fullmatch(r"[A-Za-z0-9_.-]+", name):
            return {"ok": False, "error": "exact workspace name is invalid"}
        dest = WORKSPACES_DIR / name
        title = (description or name).strip()
    else:
        dest, title = _resolve_dest(description, name)
    slug = dest.name
    if dest.exists() and not overwrite:
        existing = sorted(p.name for p in dest.rglob("*") if p.is_file()) if dest.is_dir() else []
        return {
            "ok": True, "already_exists": True, "kind": "project",
            "path": str(dest), "files": existing, "run_hint": run_hint,
            "note": f"'{slug}' already exists — left it untouched. Repeat the build order with the word 'overwrite' to rebuild it.",
        }
    valid_files: dict[str, str] = {}
    invalid_files: list[str] = []
    for raw_rel, content in files.items():
        rel = str(raw_rel).strip().replace("\\", "/").lstrip("/")
        parts = rel.split("/") if rel else []
        if not rel or ".." in parts or any(not part for part in parts):
            invalid_files.append(str(raw_rel))
            continue
        valid_files[rel] = str(content)
    if not valid_files:
        return {"ok": False, "error": "no valid files to write"}
    folded_names = {name.casefold(): name for name in valid_files}
    collisions: list[dict[str, str]] = []
    for name in valid_files:
        parts = name.split("/")
        for index in range(1, len(parts)):
            parent = "/".join(parts[:index])
            if parent.casefold() in folded_names:
                collisions.append({"file": folded_names[parent.casefold()], "child": name})
    if collisions:
        return {
            "ok": False,
            "error": "project contains file/directory path collisions",
            "path_collisions": collisions,
            "invalid_files": invalid_files,
        }
    replacing = bool(dest.exists() and overwrite)
    staging_root = WORKSPACES_DIR / ".engel_staging"
    staging_root.mkdir(parents=True, exist_ok=True)
    write_dest = staging_root / f"{slug}_{uuid.uuid4().hex[:10]}"
    write_dest.mkdir(parents=True, exist_ok=False)
    dest_resolved = write_dest.resolve()
    written: list[str] = []
    try:
        file_items = valid_files.items()
        for rel, content in file_items:
            target = write_dest / rel
            try:
                target.resolve().relative_to(dest_resolved)
            except (OSError, ValueError):
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            body = content if content.endswith("\n") else content + "\n"
            target.write_text(body, encoding="utf-8")
            written.append(rel)
    except Exception:
        shutil.rmtree(write_dest, ignore_errors=True)
        raise
    if not written:
        shutil.rmtree(write_dest, ignore_errors=True)
        return {"ok": False, "error": "no valid files to write"}
    entry = written[0]
    readme = (
        f"# {title}\n\nBuilt by Engel AI Main from your request.\n\n"
        f"## Files\n" + "".join(f"- `{f}`\n" for f in written) +
        (f"\n## Run\n```\n{run_hint}\n```\n" if run_hint else "")
    )
    try:
        (write_dest / "README.md").write_text(readme, encoding="utf-8")
    except Exception:
        shutil.rmtree(write_dest, ignore_errors=True)
        raise
    replaced_backup = ""
    if replacing:
        backup_root = WORKSPACES_DIR / ".replaced_builds"
        backup_root.mkdir(parents=True, exist_ok=True)
        backup = backup_root / f"{slug}_{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}_{uuid.uuid4().hex[:6]}"
        dest.replace(backup)
        try:
            write_dest.replace(dest)
        except Exception:
            backup.replace(dest)
            shutil.rmtree(write_dest, ignore_errors=True)
            raise
        replaced_backup = str(backup)
    else:
        if dest.exists():
            shutil.rmtree(write_dest, ignore_errors=True)
            return {
                "ok": False,
                "error": "workspace appeared during staged write; existing workspace left untouched",
            }
        write_dest.replace(dest)
    return {
        "ok": True, "created": True, "kind": "project", "path": str(dest),
        "files": sorted(written + ["README.md"]), "entry": entry, "run_hint": run_hint,
        "replaced_workspace_backup": replaced_backup,
        "invalid_files": invalid_files,
        "note": f"Wrote a {len(written)}-file project to {dest}.",
    }


def restore_workspace_backup(workspace_path: str, backup_path: str) -> dict:
    """Atomically restore a pre-build workspace while preserving the failed candidate."""
    root = WORKSPACES_DIR.resolve()
    dest = Path(workspace_path).resolve()
    backup = Path(backup_path).resolve()
    replaced_root = (root / ".replaced_builds").resolve()
    if dest.parent != root or not dest.is_dir():
        return {"ok": False, "error": "workspace restore target is invalid"}
    try:
        backup.relative_to(replaced_root)
    except ValueError:
        return {"ok": False, "error": "workspace restore backup is outside .replaced_builds"}
    if not backup.is_dir():
        return {"ok": False, "error": "workspace restore backup is missing"}
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    staging_root = root / ".engel_staging"
    failed_root = root / ".failed_builds"
    staging_root.mkdir(parents=True, exist_ok=True)
    failed_root.mkdir(parents=True, exist_ok=True)
    stage = staging_root / f"restore_{dest.name}_{uuid.uuid4().hex[:10]}"
    failed = failed_root / f"{dest.name}_{stamp}_{uuid.uuid4().hex[:6]}"
    try:
        shutil.copytree(backup, stage)
        dest.replace(failed)
        try:
            stage.replace(dest)
        except Exception:
            failed.replace(dest)
            raise
    except Exception as exc:
        shutil.rmtree(stage, ignore_errors=True)
        return {
            "ok": False,
            "error": str(exc)[:500],
            "workspace_path": str(dest),
            "backup_path": str(backup),
        }
    return {
        "ok": True,
        "workspace_path": str(dest),
        "restored_from": str(backup),
        "failed_candidate_backup": str(failed),
    }


def _cli(argv: list[str] | None = None) -> int:
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="Engel workspace/environment scaffolder.")
    ap.add_argument("description", help='e.g. "set up the trigonometric programming environment"')
    ap.add_argument("--name", default="")
    ap.add_argument("--overwrite", action="store_true")
    a = ap.parse_args(argv)
    res = scaffold(a.description, name=a.name, overwrite=a.overwrite)
    print(json.dumps(res, indent=2))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(_cli())
