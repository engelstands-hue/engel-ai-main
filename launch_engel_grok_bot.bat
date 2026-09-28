@echo off
cd /d "%~dp0"
title Engel Grok Bot
set "ENGEL_ROOT=%~dp0"
set "ENGEL_TEMP=%ENGEL_ROOT%runtime\tmp"
set "HOME=%ENGEL_ROOT%runtime\home"
set "ENGEL_HOME=%HOME%\.engel"
set "XDG_CONFIG_HOME=%ENGEL_ROOT%runtime\config"
set "XDG_CACHE_HOME=%ENGEL_ROOT%runtime\cache"
set "XDG_DATA_HOME=%ENGEL_ROOT%runtime\data"
if not exist "%ENGEL_TEMP%" mkdir "%ENGEL_TEMP%"
if not exist "%HOME%" mkdir "%HOME%"
if not exist "%ENGEL_HOME%" mkdir "%ENGEL_HOME%"
if not exist "%XDG_CONFIG_HOME%" mkdir "%XDG_CONFIG_HOME%"
if not exist "%XDG_CACHE_HOME%" mkdir "%XDG_CACHE_HOME%"
if not exist "%XDG_DATA_HOME%" mkdir "%XDG_DATA_HOME%"
set "TEMP=%ENGEL_TEMP%"
set "TMP=%ENGEL_TEMP%"
set "TMPDIR=%ENGEL_TEMP%"
set PYTHONIOENCODING=utf-8
set ENGEL_PY=%~dp0runtime\python310\python.exe
if not exist "%ENGEL_PY%" set ENGEL_PY=python
echo Starting Engel Grok Bot computer (current Engel AI Main / Cosmic Swarm OS)...
"%ENGEL_PY%" engel_grok_bot.py
if errorlevel 1 pause
