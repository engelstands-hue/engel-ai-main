"""Compatibility shim - Engel Graph & Loop Studio moved to D:\\Graph_&_Loop_Studio (2026-08-23).

The Studio is now a standalone codebase. Engel App still references it lazily
(engel_ai_update_routes graph-studio routes, engel_desktop_v2 transcript command,
tools/audit_engel_graph_against_this_computer). This shim loads the real module
from its new home so those callers keep working unchanged.

The new root is APPENDED to sys.path (never inserted first) so Engel App's own
modules always keep import priority.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_NEW_ROOT = Path(r"D:\Graph_&_Loop_Studio")
_REAL = _NEW_ROOT / "engel_graph_loop_studio.py"
if not _REAL.is_file():
    raise ImportError(
        "Engel Graph & Loop Studio was moved to %s but engel_graph_loop_studio.py "
        "was not found there." % _NEW_ROOT
    )
if str(_NEW_ROOT) not in sys.path:
    sys.path.append(str(_NEW_ROOT))

_spec = importlib.util.spec_from_file_location(__name__, str(_REAL))
_module = importlib.util.module_from_spec(_spec)
sys.modules[__name__] = _module
_spec.loader.exec_module(_module)
