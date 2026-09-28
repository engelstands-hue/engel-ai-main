#!/usr/bin/env python3
"""Verifier for ICM Architect applied to Engel AI Main."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import engel_icm_architect as icm  # noqa: E402
from engel_ai_update_routes import resolve_update_route  # noqa: E402
from engel_communication_router import classify_user_input  # noqa: E402
from engel_route_explorer import _group_for_route  # noqa: E402


class Checks:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.passes = 0

    def check(self, condition: bool, name: str, detail: str = "") -> None:
        if condition:
            self.passes += 1
            print("PASS " + name + ((" -- " + detail) if detail else ""))
        else:
            self.failures.append(name + ((": " + detail) if detail else ""))
            print("FAIL " + name + ((" -- " + detail) if detail else ""))


def main() -> int:
    checks = Checks()
    print("ENGEL_ICM_ARCHITECT_VERIFIER")
    checks.check(icm.ICM_PACK.is_dir(), "ICM pack exists on D:")
    checks.check((icm.ICM_PACK / "SKILL.md").is_file(), "ICM SKILL.md present")
    checks.check((icm.WORKSPACE / "CLAUDE.md").is_file(), "Engel ICM catalog exists")
    checks.check((icm.WORKSPACE / "CONTEXT.md").is_file(), "Engel ICM pipeline exists")
    checks.check("Engel App" in str(icm.ROOT), "target is current Engel app")
    checks.check(resolve_update_route("icm status") == "engel.icm.status", "icm status resolves")
    checks.check(resolve_update_route("icm audit") == "engel.icm.audit", "icm audit resolves")
    checks.check(resolve_update_route("icm workspace") == "engel.icm.workspace", "icm workspace resolves")
    checks.check(resolve_update_route("icm outputs") == "engel.icm.outputs", "icm outputs resolves")
    checks.check(resolve_update_route("icm routing") == "engel.icm.routing", "icm routing resolves")
    checks.check((icm.WORKSPACE / "_shared" / "output-routing.md").is_file(), "output routing factory file exists")
    checks.check((icm.WORKSPACE / "stages" / "04_intake" / "CONTEXT.md").is_file(), "04_intake contract exists")
    checks.check((icm.WORKSPACE / "stages" / "05_work" / "CONTEXT.md").is_file(), "05_work contract exists")
    checks.check((icm.WORKSPACE / "stages" / "06_receipt" / "CONTEXT.md").is_file(), "06_receipt contract exists")
    import engel_icm_output_router as router

    filed = router.file_engel_output(
        kind="receipt",
        title="icm-router-verifier",
        body={"ok": True, "note": "verifier sample"},
        source="verify_engel_icm_architect",
    )
    checks.check(filed.get("ok") == "true", "router files a job record", str(filed))
    checks.check(Path(str(filed.get("job_dir") or "")).is_dir(), "job record folder exists")
    checks.check("06_receipt" in str(filed.get("stage") or ""), "receipt kind maps to stage 06")
    checks.check("shutil.move" not in (ROOT / "engel_icm_output_router.py").read_text(encoding="utf-8"), "router does not move source")
    checks.check(classify_user_input("icm this").route_target == "engel.icm.audit", "icm this hits audit")
    checks.check(_group_for_route("engel.icm.status") == "ICM Architect", "explorer group")
    status = icm.render_icm_status()
    checks.check("Engel AI Main" in status and "icm-architect-main" in status, "status names pack and app")
    workspace = icm.render_icm_workspace()
    checks.check("No source files were moved" in workspace, "propose map does not migrate")
    checks.check((icm.PROPOSE_OUT / "migration-map.md").is_file(), "proposal output exists")
    checks.check((icm.WALK_OUT / "walk-test.md").is_file(), "walk-test output exists")
    source = (ROOT / "engel_icm_architect.py").read_text(encoding="utf-8")
    checks.check("unlink" not in source and "shutil.move" not in source and "rmtree" not in source, "module cannot move/delete Engel files")
    if checks.failures:
        print("ENGEL_ICM_ARCHITECT_VERIFY_FAIL")
        for item in checks.failures:
            print(" - " + item)
        return 1
    print(f"ENGEL_ICM_ARCHITECT_VERIFY_PASS {checks.passes}/{checks.passes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
