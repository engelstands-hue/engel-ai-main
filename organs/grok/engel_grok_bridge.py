from pathlib import Path
import subprocess, sys, datetime, os

ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
GROK = ROOT / ".grok" / "bin" / "grok.exe"
LOCAL_OUT = ROOT / "reports" / "grok_bridge"
LOCAL_OUT.mkdir(parents=True, exist_ok=True)

CT_HOST = "engel-spine-01"
CT_ID = "246"
CT_DIR = "/srv/engel/grok_bridge"

prompt = " ".join(sys.argv[1:]).strip() or "Give Engel AI Main one safe next step."
stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
out_file = LOCAL_OUT / f"GROK_REPLY_{stamp}.md"

cmd = [
    str(GROK),
    "-p", prompt,
    "--cwd", str(ROOT),
    "--permission-mode", "plan",
    "--max-turns", "3",
    "--no-memory"
]

result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
text = (result.stdout.strip() or result.stderr.strip() or "[no grok output]")
out_file.write_text(text, encoding="utf-8")

print(text)
print(f"\nSaved local: {out_file}")

remote_tmp = f"/tmp/{out_file.name}"
ct_target = f"{CT_DIR}/{out_file.name}"

print("\nCopying receipt to Dell CT246...")
subprocess.run(["scp", str(out_file), f"root@{CT_HOST}:{remote_tmp}"])
subprocess.run([
    "ssh", f"root@{CT_HOST}",
    f"pct push {CT_ID} {remote_tmp} {ct_target} && rm -f {remote_tmp} && pct exec {CT_ID} -- ls -l {ct_target}"
])
print(f"Saved CT246: {ct_target}")
