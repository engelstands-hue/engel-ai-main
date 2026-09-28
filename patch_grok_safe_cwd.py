from pathlib import Path

p = Path("engel_rog_grok_cli_http_bridge.py")
s = p.read_text(encoding="utf-8")

s = s.replace("TIMEOUT_SECONDS = 75", "TIMEOUT_SECONDS = 45")

if 'RUN_ROOT = ROOT / "runtime" / "grok_cli_safe_cwd"' not in s:
    s = s.replace(
        'GROK_EXE = ROOT / ".grok" / "bin" / "grok.exe"\n',
        'GROK_EXE = ROOT / ".grok" / "bin" / "grok.exe"\nRUN_ROOT = ROOT / "runtime" / "grok_cli_safe_cwd"\nRUN_ROOT.mkdir(parents=True, exist_ok=True)\n'
    )

s = s.replace('"--cwd", str(ROOT),', '"--cwd", str(RUN_ROOT),')
s = s.replace('cwd=str(ROOT),', 'cwd=str(RUN_ROOT),')

s = s.replace(
'''        "--permission-mode", "plan",
        "--max-turns", "1",
''',
'''        "--permission-mode", "plan",
        "--max-turns", "1",
        "--no-memory",
        "--no-subagents",
        "--disable-web-search",
        "--no-alt-screen",
        "--output-format", "plain",
'''
)

p.write_text(s, encoding="utf-8")
print("patched Grok bridge: safe cwd, no repo scan, shorter timeout")
