@echo off
cd /d "%~dp0"
echo Engel OpenAI key installer
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_engel_openai_key_from_clipboard.ps1"
echo.
echo Window will stay open. Tell Codex what it says.
pause
