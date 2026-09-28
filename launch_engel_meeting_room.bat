@echo off
cd /d "%~dp0"
set "ENGEL_ROOT=%~dp0"
set "ENGEL_MEMORY_ROOT=F:\ENGEL_APP_MEMORY"
if not exist "F:\" set "ENGEL_MEMORY_ROOT=%ENGEL_ROOT%runtime\engel_memory"
set "ENGEL_TEMP=%ENGEL_ROOT%runtime\tmp"
set "HOME=%ENGEL_MEMORY_ROOT%\home"
set "ENGEL_HOME=%ENGEL_MEMORY_ROOT%\engel-home"
set "ENGEL_RUNPOD_ROOT=%ENGEL_MEMORY_ROOT%\runpod"
set "ENGEL_RUNPOD_API_KEY_FILE=%ENGEL_MEMORY_ROOT%\secrets\runpod_api_key.txt"
set "ENGELCODE_HOME=%ENGEL_MEMORY_ROOT%\engelcode-home"
set "OPENENGEL_HOME=%ENGEL_MEMORY_ROOT%\openengel-home"
set "XDG_CONFIG_HOME=%ENGEL_ROOT%runtime\config"
set "XDG_CACHE_HOME=%ENGEL_ROOT%runtime\cache"
set "XDG_DATA_HOME=%ENGEL_ROOT%runtime\data"
set "ENGEL_PYINSTALLER_CONFIG=%ENGEL_ROOT%runtime\pyinstaller_config"
set "ENGEL_PYINSTALLER_TEMP=%ENGEL_ROOT%runtime\pyinstaller_tmp"
if not exist "%ENGEL_TEMP%" mkdir "%ENGEL_TEMP%"
if not exist "%ENGEL_MEMORY_ROOT%" mkdir "%ENGEL_MEMORY_ROOT%"
if not exist "%HOME%" mkdir "%HOME%"
if not exist "%ENGEL_HOME%" mkdir "%ENGEL_HOME%"
if not exist "%ENGEL_RUNPOD_ROOT%" mkdir "%ENGEL_RUNPOD_ROOT%"
if not exist "%ENGEL_MEMORY_ROOT%\secrets" mkdir "%ENGEL_MEMORY_ROOT%\secrets"
if not exist "%ENGELCODE_HOME%" mkdir "%ENGELCODE_HOME%"
if not exist "%OPENENGEL_HOME%" mkdir "%OPENENGEL_HOME%"
if not exist "%XDG_CONFIG_HOME%" mkdir "%XDG_CONFIG_HOME%"
if not exist "%XDG_CACHE_HOME%" mkdir "%XDG_CACHE_HOME%"
if not exist "%XDG_DATA_HOME%" mkdir "%XDG_DATA_HOME%"
if not exist "%ENGEL_PYINSTALLER_CONFIG%" mkdir "%ENGEL_PYINSTALLER_CONFIG%"
if not exist "%ENGEL_PYINSTALLER_TEMP%" mkdir "%ENGEL_PYINSTALLER_TEMP%"
set "TEMP=%ENGEL_TEMP%"
set "TMP=%ENGEL_TEMP%"
set "TMPDIR=%ENGEL_TEMP%"
set "PYINSTALLER_CONFIG_DIR=%ENGEL_PYINSTALLER_CONFIG%"
set PYTHONIOENCODING=utf-8
REM Prefer Engel-owned D: Python (no C: dependency); fall back to PATH only if missing.
set ENGEL_PY=%~dp0runtime\python310\python.exe
if not exist "%ENGEL_PY%" set ENGEL_PY=python
echo Starting Engel Agent Meeting Room (using "%ENGEL_PY%")...
"%ENGEL_PY%" engel_agent_meeting_room.py
pause
