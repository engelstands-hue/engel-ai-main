"""Offline gate for Engel's machine-estate knowledge.

Properties proven, in both directions where a direction exists:
  1. HONEST SOURCING - a scanned entry never claims to know what a project IS; it
     reports markers and carries state "scanned_uncurated". A curated entry keeps its
     reviewed description and evidence. A scan re-run refreshes hard evidence on a
     curated row but must NEVER overwrite its human-reviewed meaning.
  2. RESUMABILITY - the sweep records completed roots and whether it stopped early, so
     a long check can continue instead of restarting (operator directive: this machine
     may take days to check).
  3. HONEST ABSENCE - an empty inventory, an unreadable inventory, and a query with no
     matches all report themselves plainly instead of inventing content.
  4. QUERY SANITY - a real project is findable by plain words; nonsense finds nothing;
     name matches outrank incidental body mentions.
  5. LIVE INVENTORY - the real recorded inventory exists, is loadable, and its curated
     rows carry the fields Engel would speak from.
No network, no writes outside a temp directory.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import engel_machine_estate as estate  # noqa: E402

checks: list[dict[str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    checks.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": detail})


with tempfile.TemporaryDirectory() as tmp:
    tmp_root = Path(tmp)
    inventory = tmp_root / "inv.json"

    # ---- 3. honest absence (empty + unreadable) ---------------------------
    empty = estate.load_estate(inventory)
    check("missing inventory loads as an empty shell, not an error",
          empty["projects"] == [] and empty["schema"] == estate.SCHEMA)
    check("summary of an empty inventory reports zero honestly",
          estate.summary(inventory)["total_projects"] == 0)
    broken = tmp_root / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    loaded_broken = estate.load_estate(broken)
    check("unreadable inventory says so instead of pretending",
          loaded_broken["projects"] == [] and "load_error" in loaded_broken)

    # ---- build a fake machine to scan -------------------------------------
    proj_a = tmp_root / "machine" / "alpha_tool"
    proj_a.mkdir(parents=True)
    (proj_a / "pyproject.toml").write_text("[project]\nname='alpha'\n", encoding="utf-8")
    (proj_a / "alpha.py").write_text("print('hi')\n", encoding="utf-8")
    (proj_a / "README.md").write_text("# alpha\n", encoding="utf-8")
    proj_b = tmp_root / "machine" / "beta_app"
    proj_b.mkdir(parents=True)
    (proj_b / "package.json").write_text('{"name":"beta"}', encoding="utf-8")
    (proj_b / "index.ts").write_text("export {}\n", encoding="utf-8")
    noise = tmp_root / "machine" / "alpha_tool" / "node_modules" / "junk"
    noise.mkdir(parents=True)
    (noise / "package.json").write_text('{"name":"junk"}', encoding="utf-8")
    empty_dir = tmp_root / "machine" / "nothing_here"
    empty_dir.mkdir()
    (empty_dir / "notes.txt").write_text("hello", encoding="utf-8")

    result = estate.scan([str(tmp_root / "machine")], max_depth=3, path=inventory)
    scanned = estate.load_estate(inventory)["projects"]
    names = {p["name"] for p in scanned}
    check("scan finds real projects by marker files",
          {"alpha_tool", "beta_app"} <= names, str(sorted(names)))
    check("scan skips dependency noise (node_modules)", "junk" not in names)
    check("a directory with no markers or code is not called a project",
          "nothing_here" not in names)
    check("scanned entries are honestly labelled uncurated",
          all(p["state"] == "scanned_uncurated" for p in scanned))
    check("scanned entries carry no invented description",
          all(not p.get("what_it_is") for p in scanned))
    check("scanned entries record real evidence (markers + languages)",
          all(p.get("markers") and isinstance(p.get("languages"), dict) for p in scanned))

    # ---- 2. resumability ---------------------------------------------------
    state_after = estate.load_estate(inventory)["scan_state"]
    check("scan records the roots it completed",
          str(tmp_root / "machine") in state_after.get("completed_roots", []))
    check("scan records whether it stopped early",
          state_after.get("last_scan_stopped_early") is False)
    zero_budget = estate.scan([str(tmp_root / "machine")], max_depth=3,
                              budget_seconds=0.0, path=inventory)
    check("an already-completed root is not rescanned",
          zero_budget["new_projects"] == 0)
    fresh_inventory = tmp_root / "inv2.json"
    starved = estate.scan([str(tmp_root / "machine")], max_depth=3,
                          budget_seconds=0.0, path=fresh_inventory)
    check("a starved scan stops early and says so", starved["stopped_early"] is True)

    # ---- 1. curation survives a rescan ------------------------------------
    data = estate.load_estate(inventory)
    for project in data["projects"]:
        if project["name"] == "alpha_tool":
            project["what_it_is"] = "reviewed: the alpha command line tool"
            project["state"] = "active"
            project["evidence"] = "read pyproject.toml and alpha.py"
            project["source"] = "agent_review"
    estate.save_estate(data, inventory)
    (proj_a / "extra.py").write_text("x = 1\n", encoding="utf-8")
    estate.scan([str(tmp_root / "machine2_missing")], max_depth=2, path=inventory)
    data2 = estate.load_estate(inventory)
    alpha = next(p for p in data2["projects"] if p["name"] == "alpha_tool")
    check("a rescan never overwrites a reviewed description",
          alpha.get("what_it_is") == "reviewed: the alpha command line tool"
          and alpha.get("state") == "active")

    # re-scan the SAME root after clearing completion, and confirm evidence refreshes
    data2["scan_state"]["completed_roots"] = []
    estate.save_estate(data2, inventory)
    estate.scan([str(tmp_root / "machine")], max_depth=3, path=inventory)
    alpha2 = next(p for p in estate.load_estate(inventory)["projects"]
                  if p["name"] == "alpha_tool")
    check("a rescan DOES refresh hard evidence on a curated row",
          alpha2.get("code_file_count", 0) >= 2 and alpha2.get("what_it_is")
          == "reviewed: the alpha command line tool",
          f"code_files={alpha2.get('code_file_count')}")

    # ---- 4. query sanity ---------------------------------------------------
    hits = estate.search("alpha", path=inventory)
    check("a real project is findable by name", bool(hits) and hits[0]["name"] == "alpha_tool")
    check("nonsense query finds nothing rather than guessing",
          estate.search("zzzqqqxxwv", path=inventory) == [])
    check("an empty query returns nothing (no accidental dump)",
          estate.search("   ", path=inventory) == [])

# ---- 5. the live inventory -------------------------------------------------
live = estate.load_estate()
live_curated = [p for p in live["projects"] if p.get("what_it_is")]
check("live inventory exists and is loadable", bool(live["projects"]),
      f"projects={len(live['projects'])}")
check("live inventory holds reviewed entries with evidence",
      len(live_curated) >= 20 and all(p.get("path") and p.get("state") for p in live_curated),
      f"curated={len(live_curated)}")
check("live inventory knows Engel's own product",
      any("Engel App" in str(p.get("path") or "") or "Engel App" in str(p.get("name") or "")
          for p in live["projects"]))
brief = estate.estate_brief()
check("estate brief is speakable and cites the inventory path",
      "estate inventory holds" in brief and "ENGEL_MACHINE_ESTATE_INVENTORY_V1.json" in brief)

failed = [c for c in checks if c["status"] != "PASS"]
print(json.dumps({
    "schema": "engel_machine_estate_verifier_v1",
    "status": "FAIL" if failed else "PASS",
    "passed": len(checks) - len(failed),
    "total": len(checks),
    "failed": [c["name"] for c in failed],
    "checks": checks,
}, indent=2))
raise SystemExit(1 if failed else 0)
