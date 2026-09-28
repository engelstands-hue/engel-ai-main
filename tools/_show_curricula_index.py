import json
from pathlib import Path

idx = json.loads(
    Path("memory/training/engel_main/templates/curricula_index.json").read_text(
        encoding="utf-8"
    )
)
print("top keys", sorted(idx.keys()) if isinstance(idx, dict) else type(idx))
items = idx.get("curricula") or idx.get("items") or idx.get("entries") or []
if not items and isinstance(idx, dict):
    # maybe keyed by id
    for key, value in idx.items():
        if isinstance(value, dict) and "novelty" in str(value).lower():
            print(key, value)
        elif isinstance(value, list) and value and isinstance(value[0], dict):
            items = value
            print("list under", key)
            break
for item in items:
    if not isinstance(item, dict):
        continue
    print(
        {
            "id": item.get("id") or item.get("curriculum_id"),
            "novelty_state": item.get("novelty_state") or item.get("novelty"),
            "novel_hour_count": item.get("novel_hour_count")
            or item.get("novel_hours"),
            "material_source": item.get("material_source"),
            "version": item.get("material_version") or item.get("version"),
            "keys": sorted(item.keys())[:20],
        }
    )
