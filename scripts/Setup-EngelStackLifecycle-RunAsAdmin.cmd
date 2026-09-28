@echo off
REM  Engel stack lifecycle setup — double-click this; approve the one UAC prompt.
REM  Converts the ROG stack to: runs only while EngelAIMain.exe is open, all hidden.
REM  Window closes itself when done (transcript: runtime\logs\setup_elevated.log).
title Engel Stack Lifecycle Setup (elevated)

>nul 2>&1 net session
if %errorlevel% neq 0 (
    powershell -NoProfile -Command "Start-Process -Verb RunAs -FilePath cmd.exe -ArgumentList '/c','\"%~f0\"'"
    exit /b
)

echo Running elevated setup...
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\b.WorkSpace\Engel App\scripts\Setup-EngelStackLifecycle.ps1"
echo Done. This window closes in 5 seconds (log: runtime\logs\setup_elevated.log).
timeout /t 5 /nobreak >nul
exit /b
