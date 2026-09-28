#!/usr/bin/env python3
from __future__ import annotations

import json

from engel_chat_humanizer import write_workspace_registry


def main() -> int:
    payload = write_workspace_registry()
    print(
        json.dumps(
            {
                "ok": payload.get("ok") is True,
                "schema": payload.get("schema"),
                "root": payload.get("root"),
                "total_top_level_entries": payload.get("total_top_level_entries"),
                "active_part_count": payload.get("active_part_count"),
                "registry_json_path": payload.get("registry_json_path"),
                "registry_report_path": payload.get("registry_report_path"),
                "humanizer_reference_loaded": payload.get("humanizer_reference_loaded"),
            },
            indent=2,
        )
    )
    return 0 if payload.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
