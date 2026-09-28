#!/usr/bin/env python
"""Quick local verification that Chat LLM conversation tweaks are in place."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

print("=== Verify Chat LLM (SSD/local) conversation feel changes ===\n")

# 1. Profile system prompt
profile = ROOT / "runtime" / "engel_standalone_chat_llm" / "engel_chat_profile.json"
with open(profile, encoding="utf-8-sig") as f:
    data = json.load(f)
sp = data.get("system_prompt", "")
print("1. Profile system_prompt updated for real conversation?")
print("   Contains 'real ongoing conversation':", "real ongoing conversation" in sp.lower())
print("   Contains 'natural rhythm':", "natural rhythm" in sp.lower())
print("   Preview:", sp[:160], "...\n")

# 2. Prompt builder
sys.path.insert(0, str(ROOT / "tools"))
try:
    from run_engel_standalone_chat_llm import build_local_user_prompt
    p = build_local_user_prompt(
        "How's the local model on the fast drive feeling today?",
        None,
        "- 2026... Joshua: any SSD progress?\n  Engel: The Q5 model loads quick from G: via F: runtime."
    )
    print("2. build_local_user_prompt improved?")
    print("   Uses 'Recent turns in our conversation':", "Recent turns in our conversation" in p)
    print("   Has 'Real conversation guidance':", "Real conversation guidance" in p)
    print("   Softer end instructions (no 'obey exact length'):", "obey exact length" not in p.lower())
    print("   Sample tail:\n", p[-420:], "\n")
except Exception as e:
    print("2. Prompt builder check skipped (import):", e)

# 3. Temps
import engel_local_model_service as svc
src = open(svc.__file__).read()
print("3. Local model service temperature raised?")
print("   0.72 in source:", "0.72" in src)
print("   Old 0.15 gone from defaults:", "0.15" not in src.split("temperature: float = 0.72")[0][-200:] if "0.72" in src else "check manually")

print("\n4. Large chat default?")
with open(ROOT / "engel_large_chat_llm.py") as f:
    lc = f.read()
print("   0.72 default present:", "0.72" in lc and "LARGE_CHAT_LLM_TEMPERATURE" in lc)

print("\n5. llama cli chat cmd has conversational sampling?")
with open(ROOT / "engel_llama_cli_runner.py") as f:
    lr = f.read()
print("   --temp and repeat in _build_chat_cmd:", "--temp" in lr and "repeat_penalty" in lr.lower())

print("\n=== Verification script complete ===")
print("Run full: python _route_smoke.py or the standalone verifier if needed.")