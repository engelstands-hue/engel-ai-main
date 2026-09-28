import json
import sys
from pathlib import Path

sys.path.insert(0, "tools")
import engel_curriculum_adoption as adoption

proposal_path = Path(
    "memory/training/engel_main/generated/ENGEL_COMMUNICATION_GENERATED_CARDS_PROPOSAL.json"
)
adopted_path = Path(
    "memory/training/engel_main/generated/ENGEL_COMMUNICATION_GENERATED_CARDS_ADOPTED.json"
)
proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
approval = adoption.required_approval("communication", proposal)
result = adoption.adopt_proposal(
    proposal,
    adopted_path,
    kind="communication",
    approval=approval,
)
print(
    json.dumps(
        {
            "ok": True,
            "approval": approval,
            "material_version": proposal["material_version"],
            "card_count": proposal["card_count"],
            "result_type": type(result).__name__,
        },
        indent=2,
    )
)
