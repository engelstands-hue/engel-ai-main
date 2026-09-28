@echo off
setlocal
cd /d "%~dp0"

python codexstatusviewer.py
if errorlevel 1 (
    echo.
    echo Codex Status Viewer failed to launch.
    pause
)