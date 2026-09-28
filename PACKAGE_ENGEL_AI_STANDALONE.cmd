@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0PACKAGE_ENGEL_AI_STANDALONE.ps1" %*
