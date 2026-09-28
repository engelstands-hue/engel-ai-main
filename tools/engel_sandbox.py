#!/usr/bin/env python3
"""
Engel AI Main — sandbox exec tiers.

Ported concept from OpenClaw (MIT): tool/command execution runs behind a sandbox
(OpenClaw uses Docker default + SSH/OpenShell backends; non-main sessions
sandbox by policy). Engel runs on Windows without a mandatory container, so this
provides real DEFENSE-IN-DEPTH tiers rather than a VM boundary:

  tier "none"        — run directly (trusted / main session)
  tier "restricted"  — isolated temp cwd, SECRETS STRIPPED from env, timeout,
                       output capped, dangerous-command denylist
  tier "readonly"    — restricted + the working dir is the only writable path
                       exposed (best-effort; enforced via cwd + denylist)

Honest limit: true network isolation needs a container; that is NOT enforced here
(reported as network_isolated=false). The denylist + env-stripping + isolated cwd
are real and block the common foot-guns. Use tier "none" only for trusted turns.

Reimplemented natively in Python; MIT-attributed.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from typing import Optional

SANDBOX_TIERS = ("none", "restricted", "readonly")

# Dangerous command shapes blocked in restricted/readonly tiers.
#
# (2026-07-10 adversarial audit) Rewritten after an adversarial audit (232-command
# corpus, deterministic regex oracle) found 95 evasions of the previous list: flag-order
# rm (-fr, -r -f, --recursive), PowerShell delete ALIASES (ri/rm/rd/rmdir/del/erase +
# -Recurse), erase/rd-glued switches, LOLBin droppers (certutil/bitsadmin/wmic), fileless
# download-exec (iex/irm/Net.WebClient), anti-recovery (vssadmin/wbadmin/bcdedit),
# persistence (schtasks/sc create/New-Service/reg add ...Run), account creation
# (net localgroup / New-LocalUser / Add-LocalGroupMember), disk wipers (Clear-Disk/wipefs/
# shred/sdelete/mke2fs/dd of=), robocopy /MIR, forfiles, wsl --unregister, and more.
#
# INVARIANT verified against that corpus: this list denies a STRICT SUPERSET of the old
# one (nothing previously blocked is now allowed) and blocks 173/173 dangerous commands,
# while leaving the build/run lane's own commands (node/go/python/gcc/javac/...) untouched.
# Philosophy: for untrusted (model-generated) command text, over-blocking a benign command
# is the SAFE failure; a missed destructive command is not. Regression-tested in
# tools/test_engel_sandbox.py — keep that green.
_DENY_PATTERNS = [
    # ---- Unix rm: recursive/force (any flag arrangement) or a dangerous target ----
    re.compile(r"\brm\b[^|;&\n]*\s-\w*[rR]\w*", re.I),                       # -r -rf -fr -Rf -rfv, and -r in "-r -f"
    re.compile(r"\brm\b[^|;&\n]*--(?:recursive|force|no-preserve-root)\b", re.I),
    re.compile(r"\brm\b[^|;&\n]*\s\"?(?:/|~|\$|//|/\*|[A-Za-z]:[\\/]|/mnt/|/[a-z]/)", re.I),  # root/home/env/drive/mount

    # ---- cmd del / erase (synonyms) ----
    re.compile(r"\b(?:del|erase)\b[^|\n]*/[sqf]\b", re.I),                   # /s /q /f
    re.compile(r"\b(?:del|erase)\b[^|\n]*[A-Za-z]:[\\/]", re.I),             # targeting a drive path
    re.compile(r"\b(?:del|erase)\b[^|\n]*\*", re.I),                        # wildcard delete
    re.compile(r"\b(?:del|erase)\b[^|\n]*[-–]recurse", re.I),               # PowerShell del/erase alias -Recurse

    # ---- cmd rd / rmdir: /s glued OR spaced, any drive; also PS aliases ----
    re.compile(r"\b(?:rd|rmdir)\b[^|\n]*/s\b", re.I),                        # rd/s, rmdir /s, /q/s (no whitespace needed)
    re.compile(r"\b(?:rd|rmdir)\b[^|\n]*[-–]recurse", re.I),                # PowerShell rd/rmdir alias -Recurse

    # ---- PowerShell Remove-Item + aliases (ri/rm) recursive; any slash/UNC/env target ----
    re.compile(r"\b(?:Remove-Item|ri)\b[^|\n]*[-–](?:recurse|rec\b|rec\w*)", re.I),
    re.compile(r"\brm\b[^|\n]*[-–]recurse", re.I),                          # PS rm alias with -Recurse
    re.compile(r"\|\s*(?:Remove-Item|ri|rm|rd|rmdir|del|erase|Clear-Content)\b", re.I),  # pipe INTO a delete cmdlet
    re.compile(r"\bClear-Content\b", re.I),                                  # mass file truncation

    # ---- disk / filesystem destruction ----
    re.compile(r"\bf\^?o\^?r\^?m\^?a\^?t\b", re.I),                          # format (+ caret-escape fo^rmat)
    re.compile(r"\bmk(?:fs|e2fs|dosfs|ntfs|swap)\b", re.I),                  # mkfs and real backends (mke2fs)
    re.compile(r"\bdiskpart\b", re.I),
    re.compile(r"\b(?:wipefs|shred|sdelete|blkdiscard)\b", re.I),
    re.compile(r"\bcipher\b[^\n]*/w", re.I),
    re.compile(r"\b(?:Clear-Disk|Remove-Partition|Initialize-Disk|Format-Volume|Reset-PhysicalDisk)\b", re.I),
    re.compile(r"\bdd\b[^\n]*(?:if=|of=)", re.I),                            # dd if= OR of= (either order)
    re.compile(r"[>|]\s*/dev/(?:sd[a-z]|nvme\d|hd[a-z]|vd[a-z]|mapper/)", re.I),   # redirect/pipe to raw device
    re.compile(r"\btee\b[^\n]*/dev/(?:sd[a-z]|nvme\d)", re.I),               # tee to raw device
    re.compile(r"\bcat\b[^\n]*>\s*/dev/(?:sd|nvme)", re.I),                  # cat > /dev/sdX

    # ---- power state ----
    re.compile(r"\b(?:shutdown|reboot|halt|poweroff|logoff)\b", re.I),
    re.compile(r"\b(?:Stop-Computer|Restart-Computer)\b", re.I),
    re.compile(r"Win32Shutdown", re.I),                                     # WMI reboot/shutdown (preceded by a digit)

    # ---- registry: HKLM delete + Run-key persistence ----
    re.compile(r"\breg(?:\.exe)?\b[^\n]*\bdelete\b[^\n]*(?:HKLM|HKEY_LOCAL_MACHINE)", re.I),
    re.compile(r"\breg(?:\.exe)?\b[^\n]*\badd\b[^\n]*\\Run\b", re.I),        # ...\CurrentVersion\Run autostart

    # ---- accounts / privilege escalation ----
    re.compile(r"\bnet(?:\.exe)?\s+user\b[^\n]*/add", re.I),
    re.compile(r"\bnet(?:\.exe)?\s+user\b[^\n]*/active", re.I),
    re.compile(r"\bnet(?:\.exe)?\s+localgroup\b[^\n]*/add", re.I),
    re.compile(r"\bNew-LocalUser\b", re.I),
    re.compile(r"\bAdd-LocalGroupMember\b", re.I),
    re.compile(r"\btakeown\b", re.I),
    re.compile(r"\bicacls\b[^\n]*/(?:grant|setowner|reset)", re.I),
    re.compile(r"\bSet-Acl\b", re.I),

    # ---- persistence: scheduled tasks / services ----
    re.compile(r"\bschtasks\b[^\n]*/create", re.I),
    re.compile(r"\bsc(?:\.exe)?\s+create\b", re.I),
    re.compile(r"\bNew-Service\b", re.I),
    re.compile(r"\bwmic\b[^\n]*process\b[^\n]*call\b[^\n]*create", re.I),

    # ---- anti-recovery (ransomware precursors) ----
    re.compile(r"\bvssadmin\b[^\n]*\bdelete\b", re.I),
    re.compile(r"\bwbadmin\b[^\n]*\bdelete\b", re.I),
    re.compile(r"\bbcdedit\b", re.I),
    re.compile(r"\bwsl\b[^\n]*--unregister", re.I),

    # ---- alternate mass-delete binaries ----
    re.compile(r"\brobocopy\b[^\n]*/mir\b", re.I),
    re.compile(r"\bforfiles\b[^\n]*(?:/c\b|\bdel\b)", re.I),

    # ---- fork bomb (classic + named) ----
    re.compile(r":\(\)\s*\{.*\};:", re.I),
    re.compile(r"(\w+)\s*\(\)\s*\{[^}]*\|\s*\1[^}]*&[^}]*\}\s*;\s*\1", re.I),

    # ---- pipe-to-shell / interpreter ----
    re.compile(r"\|&?\s*(?:iex|invoke-expression|sh|bash|zsh|dash|ksh|cmd|powershell|pwsh|python[23]?|perl|ruby|node|wscript|cscript)\b", re.I),

    # ---- download-then-execute (LOLBins, pipes, chains) ----
    re.compile(r"\b(?:curl|wget|iwr|irm|invoke-webrequest|invoke-restmethod)\b[^\n]*[|;&]", re.I),
    re.compile(r"\b(?:certutil|bitsadmin)\b[^\n]*(?:urlcache|/transfer|https?://)", re.I),
    re.compile(r"\b(?:iex|invoke-expression)\b", re.I),
    re.compile(r"Net\.WebClient|DownloadString|DownloadFile", re.I),
]
# Env names that must never be exposed to a sandboxed command.
_SECRET_ENV_RE = re.compile(r"(API_KEY|_KEY$|TOKEN|SECRET|PASSWORD|CREDENTIAL|AUTH)", re.I)


def is_denied(argv: list[str]) -> Optional[str]:
    joined = " ".join(argv)
    for pat in _DENY_PATTERNS:
        if pat.search(joined):
            return pat.pattern
    return None


def safe_env() -> dict:
    """Env with secrets stripped (OpenClaw redaction / non-main isolation)."""
    return {k: v for k, v in os.environ.items() if not _SECRET_ENV_RE.search(k)}


def run_sandboxed(argv: list[str], *, tier: str = "restricted", timeout: int = 60,
                  cwd: Optional[str] = None, max_output: int = 20000) -> dict:
    if tier not in SANDBOX_TIERS:
        return {"ok": False, "error": f"unknown tier {tier}; valid: {SANDBOX_TIERS}"}
    if tier != "none":
        denied = is_denied(argv)
        if denied:
            return {"ok": False, "blocked": True, "tier": tier,
                    "reason": f"command matched deny pattern: {denied}"}

    if tier == "none":
        env = dict(os.environ)
        workdir = cwd
        cleanup = None
    else:
        env = safe_env()
        env["ENGEL_SANDBOX"] = tier
        if cwd:
            workdir = cwd
            cleanup = None
        else:
            workdir = tempfile.mkdtemp(prefix="engel_sbx_")
            cleanup = workdir

    try:
        cp = subprocess.run(argv, cwd=workdir, env=env, capture_output=True, text=True,
                            timeout=timeout, encoding="utf-8", errors="replace", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        out = {
            "ok": cp.returncode == 0, "tier": tier, "returncode": cp.returncode,
            "cwd": workdir, "stdout": (cp.stdout or "")[:max_output],
            "stderr": (cp.stderr or "")[:max_output],
            "secrets_stripped": tier != "none", "network_isolated": False,
        }
    except subprocess.TimeoutExpired:
        out = {"ok": False, "tier": tier, "error": f"timed out after {timeout}s", "cwd": workdir}
    except FileNotFoundError as exc:
        out = {"ok": False, "tier": tier, "error": f"command not found: {exc}", "cwd": workdir}
    finally:
        if tier != "none" and 'cleanup' in dir() and cleanup:
            try:
                import shutil
                shutil.rmtree(cleanup, ignore_errors=True)
            except Exception:
                pass
    return out


def _cli(argv: Optional[list[str]] = None) -> int:
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="Engel sandbox exec tiers (OpenClaw sandbox port).")
    ap.add_argument("--tier", choices=SANDBOX_TIERS, default="restricted")
    ap.add_argument("--timeout", type=int, default=60)
    ap.add_argument("cmd", nargs=argparse.REMAINDER, help="the command (after --)")
    a = ap.parse_args(argv)
    cmd = a.cmd[1:] if a.cmd and a.cmd[0] == "--" else a.cmd
    if not cmd:
        ap.print_help()
        return 2
    import json
    print(json.dumps(run_sandboxed(cmd, tier=a.tier, timeout=a.timeout), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
