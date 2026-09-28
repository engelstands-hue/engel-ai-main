import json
import sys
from pathlib import Path

sys.path.insert(0, "tools")
from pathlib import Path as P

adopted = json.loads(
    P("memory/training/engel_main/generated/ENGEL_COMMUNICATION_GENERATED_CARDS_ADOPTED.json").read_text(
        encoding="utf-8"
    )
)
print("keys", sorted(adopted.keys())[:30])
cards = adopted.get("cards") or []
print("cards", len(cards))
if cards:
    print("topic0", cards[0].get("topic"))

import engel_training_assets as a

for c in a.ALL_CURRICULA:
    if c["id"] == "chat_communication":
        print(
            "source",
            c.get("material_source"),
            c.get("generated_source_id"),
            c.get("version"),
        )
        print("first topic", c["cards"][0].get("topic"))
