#!/usr/bin/env python3
"""Offline gate for the build-lane overwrite/collision fix (2026-07-11).

Covers:
  - slug-truncation collision: two DIFFERENT requests sharing a 48-char slug
    prefix get SEPARATE workspaces (hash-suffixed), no false "already exists"
  - same request twice: second call reports already_exists (guard intact)
  - 'overwrite' keyword: detected, stripped from the description (slug still
    matches the original dir), and write_project rebuilds in place
  - run_build pre-check: an existing build short-circuits BEFORE the provider
    generate_fn is called; with 'overwrite' generation runs and files replace

No network, no providers, no service — pure module-level simulation.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

import engel_workspace_scaffold as scaffold  # noqa: E402
import engel_build_lane as lane  # noqa: E402

PASS = 0
FAIL = 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"PASS  {label}")
    else:
        FAIL += 1
        print(f"FAIL  {label}  {detail}")


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="engel_build_overwrite_test_"))
    scaffold.WORKSPACES_DIR = tmp
    try:
        # --- write_project: same request twice -> already_exists ------------
        desc_a = "build me a python script that prints the first 12 fibonacci numbers, one per line"
        res1 = scaffold.write_project(desc_a, {"main.py": "print(1)\n"}, run_hint="python main.py")
        check("first build creates", res1.get("created") is True, str(res1))
        res2 = scaffold.write_project(desc_a, {"main.py": "print(2)\n"}, run_hint="python main.py")
        check("same request again -> already_exists", res2.get("already_exists") is True, str(res2))
        check("same request -> SAME dir", res2.get("path") == res1.get("path"),
              f"{res2.get('path')} vs {res1.get('path')}")

        # --- slug truncation collision -> separate workspace ----------------
        desc_b = "build me a python script that prints the first 15 prime numbers as a table"
        assert scaffold._slug(desc_a) == scaffold._slug(desc_b), "test premise: slugs must collide"
        res3 = scaffold.write_project(desc_b, {"main.py": "print(3)\n"}, run_hint="python main.py")
        check("different request, colliding slug -> created (not false already_exists)",
              res3.get("created") is True, str(res3))
        check("different request -> DIFFERENT dir", res3.get("path") != res1.get("path"),
              f"both {res3.get('path')}")
        res3b = scaffold.write_project(desc_b, {"main.py": "print(3)\n"}, run_hint="python main.py")
        check("disambiguated dir is stable on repeat", res3b.get("already_exists") is True
              and res3b.get("path") == res3.get("path"), str(res3b))

        # --- overwrite=True rebuilds in place --------------------------------
        res4 = scaffold.write_project(desc_a, {"main.py": "print(4)\n"},
                                      run_hint="python main.py", overwrite=True)
        body = (Path(res4.get("path", "")) / "main.py").read_text(encoding="utf-8")
        check("overwrite=True rewrites in place", res4.get("created") is True
              and res4.get("path") == res1.get("path") and body == "print(4)\n", str(res4))

        # --- run_build: pre-check skips generation ---------------------------
        calls: list[str] = []

        def gen(prompt: str, timeout_s: int, max_tokens: int) -> str:
            calls.append(prompt)
            return "```python\nprint('generated')\n```"

        r = lane.run_build(desc_a, gen, request_id="t1", allow_execute=False)
        check("existing build short-circuits", r is not None
              and r.get("action", {}).get("result", {}).get("already_exists") is True, str(r))
        check("provider NOT called on short-circuit", calls == [], str(calls))
        check("reply names the workspace + overwrite word",
              r is not None and "overwrite" in r.get("assistant_reply", "")
              and res1.get("path", "?") in r.get("assistant_reply", ""), str(r))

        # --- run_build: 'overwrite' keyword rebuilds the ORIGINAL dir --------
        r2 = lane.run_build(desc_a + ", overwrite", gen, request_id="t2", allow_execute=False)
        check("overwrite order generates", len(calls) == 1, str(calls))
        got = r2.get("action", {}).get("result", {}) if r2 else {}
        check("overwrite order rebuilds SAME dir", got.get("created") is True
              and got.get("path") == res1.get("path"), str(got))
        body = (Path(got.get("path", "")) / "main.py").read_text(encoding="utf-8")
        check("overwrite order replaced the code", body == "print('generated')\n", body)
        check("description in README lost no words except 'overwrite'",
              scaffold._readme_title(Path(got.get("path", ""))) == desc_a.casefold(),
              scaffold._readme_title(Path(got.get("path", ""))))

        # --- fresh build still works end to end ------------------------------
        desc_c = "build me a python script that greets the operator by name"
        r3 = lane.run_build(desc_c, gen, request_id="t3", allow_execute=False)
        got3 = r3.get("action", {}).get("result", {}) if r3 else {}
        check("fresh build creates via lane", got3.get("created") is True, str(r3))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
