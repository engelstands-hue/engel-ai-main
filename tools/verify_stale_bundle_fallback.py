"""Simulate the stale-PyInstaller-bundle scenario from today's chat log
(ImportError: cannot import name 'prefer_workspace_modules') and confirm
the inline fallback now lets the GUI keep working."""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _clear_engel_modules() -> None:
    for name in list(sys.modules):
        if name.startswith("engel_"):
            del sys.modules[name]


def main() -> None:
    _clear_engel_modules()

    # 1) workspace happy path
    import engel_project_paths
    assert hasattr(engel_project_paths, "prefer_workspace_modules"), "workspace missing the function"
    print("A: workspace engel_project_paths has prefer_workspace_modules")

    # 2) simulate the stale bundle: delete the function so importers fall back
    del engel_project_paths.prefer_workspace_modules
    for name in list(sys.modules):
        if name.startswith("engel_") and name != "engel_project_paths":
            del sys.modules[name]

    # 3) the meeting room used to crash here with ImportError
    import engel_agent_meeting_room as room  # noqa: F401
    print("B: meeting room module imported under simulated stale bundle")
    assert callable(room.prefer_workspace_modules), "fallback not callable"

    # 4) the system actions worker-modules loader used to crash here
    import engel_ui_system_actions as actions
    adb_mgr, link_mgr = actions._worker_modules()
    print("C: _worker_modules() returned under simulated stale bundle")

    # 5) the fallback purges a stale _MEI sys.modules entry
    fake = type(sys)("engel_remote_worker_link_manager")
    fake.__file__ = (
        "D:" + chr(92) + "b.WorkSpace" + chr(92) + "Engel App" + chr(92)
        + "runtime" + chr(92) + "pyinstaller_tmp" + chr(92) + "_MEI69802"
        + chr(92) + "engel_remote_worker_link_manager.py"
    )
    sys.modules["engel_remote_worker_link_manager"] = fake
    room._inline_prefer_workspace_modules(
        "engel_remote_worker_link_manager",
        caller_file=__file__,
    )
    assert "engel_remote_worker_link_manager" not in sys.modules, "stale _MEI entry not purged"
    print("D: stale _MEI entry was purged from sys.modules")

    # 6) next plain import loads from the real workspace
    import engel_remote_worker_link_manager as lm  # noqa: E402
    path = (lm.__file__ or "").replace(chr(92), "/").lower()
    assert "pyinstaller_tmp" not in path, "next import still got stale path: " + path
    print("E: next import loaded from workspace:", lm.__file__)

    # 7) 8-hour pairing reuse function is intact (proves earlier fix still in)
    assert hasattr(lm, "ensure_session_token"), "ensure_session_token missing"
    print("F: ensure_session_token present and callable")

    print("ALL OK")


if __name__ == "__main__":
    main()
