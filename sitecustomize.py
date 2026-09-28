"""Engel workspace temp policy startup hook."""
from __future__ import annotations

import engel_organ_paths

engel_organ_paths.install()
import engel_temp_policy  # noqa: E402,F401
