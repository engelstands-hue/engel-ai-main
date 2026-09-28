#!/usr/bin/env python3
"""Verify Engel models/brains catalog and Sub-Engel add-on packs."""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAT = ROOT / "runtime" / "next_stage" / "models_brains" / "CATALOG.json"
ZIP_CAT = ROOT / "dist" / "EngelAI-SubEngel-Models-Brains-Catalog-20260825.zip"
ZIP_W = ROOT / "dist" / "EngelAI-SubEngel-Models-Brains-Weights-20260825.zip"
SKILL = ROOT / "skills" / "engel-models-brains-catalog" / "SKILL.md"
AGENT = ROOT / "agents" / "engel-models-brains-librarian.md"
CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""))


def main() -> int:
    check("catalog_exists", CAT.is_file())
    data = json.loads(CAT.read_text(encoding="utf-8")) if CAT.is_file() else {}
    lanes = data.get("ct246_llm_and_brain_lanes") or []
    check("live_7b_untouched", data.get("live_7b_untouched") is True)
    check("sot_ct246", data.get("source_of_truth") == "CT246 /opt/engel/models-active")
    live = [x for x in lanes if x.get("live") is True]
    check("two_live_rows", len(live) == 2, str(len(live)))
    check("live_is_7b_and_lora", any("qwen2.5-7b" in str(x.get("home")) for x in live) and any("khdeh9t1" in str(x.get("home")) for x in live))
    check("companion_sub_copy", any(x.get("lane") == "daily_local_companion_3b" and x.get("sub_engel_copy") for x in lanes))
    check("nemotron_not_copied", any(x.get("lane") == "nemotron_30b_lightning" and not x.get("sub_engel_copy") for x in lanes))
    check("slm_brains_6", len(data.get("slm_brains") or []) == 6, str(len(data.get("slm_brains") or [])))
    check("skill_saved", SKILL.is_file() and "APPROVE_ENGEL_MODEL_PROMOTION_V1" in SKILL.read_text(encoding="utf-8"))
    check("agent_saved", AGENT.is_file())
    check("catalog_zip", ZIP_CAT.is_file() and ZIP_CAT.stat().st_size < 5_000_000)
    check("weights_zip", ZIP_W.is_file() and ZIP_W.stat().st_size > 2_000_000_000, str(ZIP_W.stat().st_size if ZIP_W.is_file() else 0))
    if ZIP_CAT.is_file():
        with zipfile.ZipFile(ZIP_CAT) as zf:
            names = zf.namelist()
        check("catalog_zip_has_apply", "Apply-EngelSubEngelModelsBrainsAddon.ps1" in names)
        check("catalog_zip_no_gguf", not any(n.endswith(".gguf") for n in names))
        apply = zipfile.ZipFile(ZIP_CAT).read("Apply-EngelSubEngelModelsBrainsAddon.ps1").decode("utf-8")
        check("apply_refuses_c", "Refusing Sub-Engel NodeRoot on C:" in apply)
        check("apply_no_live_7b_copy", "live 7B not copied" in apply or "live_7b_copied = $false" in apply)
    if ZIP_W.is_file():
        with zipfile.ZipFile(ZIP_W) as zf:
            wnames = zf.namelist()
        check("weights_has_companion", "engel-companion-002.gguf" in wnames)
        check("weights_no_7b", not any("7b-instruct" in n.lower() for n in wnames))
        check("weights_no_nemotron", not any("nemotron" in n.lower() for n in wnames))
    failed = [n for n, ok, _ in CHECKS if not ok]
    print("RESULT " + ("PASS" if not failed else "FAIL") + f" {len(CHECKS)-len(failed)}/{len(CHECKS)}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
