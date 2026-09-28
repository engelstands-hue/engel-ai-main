@echo off
REM R.E.P.S. launcher - forwards to the real CLI at the workspace root so you can
REM run `.\reps status` (or `.\reps record`, etc.) from this Engel App terminal.
set "ENGEL_ROOT=%~dp0"
set "ENGEL_PYTHON=%ENGEL_ROOT%runtime\python310\python.exe"

if not exist "%ENGEL_PYTHON%" set "ENGEL_PYTHON=python"

"%ENGEL_PYTHON%" "D:\b.WorkSpace\.claude\reps\reps.py" %*
