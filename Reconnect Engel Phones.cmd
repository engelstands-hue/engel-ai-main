@echo off
REM ============================================================
REM  Reconnect Engel Android Remote Workers (Alpha + Beta)
REM  Double-click this button to re-pair the phones on port 8765.
REM  Runs the D-only reconnect script. Nothing writes to C:.
REM ============================================================
title Reconnect Engel Phones
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "D:\b.WorkSpace\Engel App\tools\reconnect_engel_remote_workers.ps1"
echo.
pause
