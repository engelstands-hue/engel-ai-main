import os, sys, json
ROOT = r"D:\b.WorkSpace\Engel App"
os.chdir(ROOT)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
import engel_conductor as ec

print("PID", os.getpid())
print("MODULE", getattr(ec, "__file__", "?"))
print("HAS_REJECT_FN", hasattr(ec, "_non_engelscript_reject_problems"))

nl = "ChatGPT/OpenAI is wired into Engel, but it is not positive training or inference material."
humanize = "I stopped this turn because the local draft and every available fallback failed the missing-input safety checks."
valid = 'plan "check storage"\nroute "status"\nsay "ok"'

r1 = ec._non_engelscript_reject_problems(nl)
r2 = ec._non_engelscript_reject_problems(humanize)
r3 = ec._non_engelscript_reject_problems(valid)
print("REJECT_NL", r1)
print("REJECT_HUMANIZE", r2)
print("ACCEPT_VALID", r3)
print("SHAPED_ACCEPT_EMPTY_PROBLEMS", r3 == [])

calls = {"n": 0}
def draft_fn(prompt: str) -> str:
    calls["n"] += 1
    return nl

receipt = ec.conduct(
    "dry reject proof goal",
    draft_fn=draft_fn,
    allow_actions=False,
    write_receipt=False,
    max_rounds=2,
)
print("CONDUCT_STATUS", receipt.get("status"))
print("CONDUCT_OK", receipt.get("ok"))
print("CONDUCT_ROUNDS", len(receipt.get("rounds") or []))
print("CONDUCT_DRAFT_CALLS", calls["n"])
print("CONDUCT_VALIDATE", (receipt.get("rounds") or [{}])[0].get("validate_errors"))
print("CONDUCT_ORIGIN", (receipt.get("rounds") or [{}])[0].get("origin"))
# execute_routes / execute markers
round0 = (receipt.get("rounds") or [{}])[0]
print("ROUND_KEYS", sorted(round0.keys()))
print("PROOF_DONE")
