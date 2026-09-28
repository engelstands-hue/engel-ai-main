@echo off
REM Engel AI Main - one-command self-state mirror.
REM Shows: current version, last GREEN verify, dirty files, recent failures,
REM        active tools, and the next safe action. Writes a durable receipt to
REM        reports\health_checks\ENGEL_HEALTH_LATEST.(json|md).
REM Pass --full to also run the full release verifier (records a GREEN stamp).
setlocal
set "ENGEL_ROOT=%~dp0"
set "PY=%ENGEL_ROOT%runtime\python310\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" "%ENGEL_ROOT%tools\engel_health_check.py" %*
endlocal
