@echo off
REM ============================================================================
REM  Harden-EngelSecrets-RunAsAdmin.cmd   (2026-07-10 security hardening)
REM
REM  RIGHT-CLICK -> "Run as administrator".
REM
REM  D:\b.WorkSpace is shared (EngelWorkspace / W) AND its NTFS grants Everyone:Modify,
REM  so every file under it -- INCLUDING the provider-bridge secrets -- is readable and
REM  writable by any host on your LAN. This does NOT touch your shares or the rest of the
REM  workspace (your Sub-Engel W: mapping and PC file access keep working). It ONLY removes
REM  Everyone / Authenticated Users / the sandbox group from the SECRET paths, leaving
REM  owner (ziese) + SYSTEM + Administrators. Engel's services run as ziese, so they keep
REM  full access.
REM
REM  To REVERT any path later:  icacls "<path>" /reset /t /c
REM ============================================================================
setlocal
set ACCT=ziese
set BASE=D:\b.WorkSpace\Engel App

echo(
echo === Locking secret paths (remove LAN/Everyone, keep %ACCT% + SYSTEM + Admins) ===

for %%P in (
  "%BASE%\run\secrets"
  "%BASE%\.env"
  "%BASE%\memory\personality"
) do (
  if exist %%P (
    echo Locking %%P
    icacls %%P /inheritance:r /grant:r "%ACCT%:(OI)(CI)F" "SYSTEM:(OI)(CI)F" "Administrators:(OI)(CI)F" >nul 2>&1
    if errorlevel 1 ( echo   ^!^! FAILED %%P ) else ( echo   OK )
  )
)

REM browser_profile holds the ChatGPT session (DPAPI-encrypted, but keep it private + tamper-proof)
if exist "%BASE%\browser_profile" (
  echo Locking browser_profile ^(recursive, ~600 files, may take a few seconds^)
  icacls "%BASE%\browser_profile" /inheritance:r /grant:r "%ACCT%:(OI)(CI)F" "SYSTEM:(OI)(CI)F" "Administrators:(OI)(CI)F" >nul 2>&1
  if errorlevel 1 ( echo   ^!^! FAILED browser_profile ) else ( echo   OK )
)

echo(
echo === AFTER: who can now read run\secrets (Everyone should be GONE) ===
icacls "%BASE%\run\secrets"
echo(
echo Done. Secrets are now local-only; your file shares are unchanged.
pause
