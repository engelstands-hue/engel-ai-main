@echo off
setlocal

echo ============================================
echo   Finish Grok Reinstall (Step 2 + 3)
echo ============================================
echo.

cd /d "D:\b.WorkSpace\Engel App\.grok\bin"

if not exist grok.exe.new (
    echo [ERROR] grok.exe.new not found in .grok\bin
    echo Nothing to do. The staged file is missing.
    echo.
    pause
    exit /b 1
)

echo Current files:
dir grok.exe* /b

echo.
echo IMPORTANT: The Grok TUI must be FULLY CLOSED before this swap.
echo If this window was launched from Grok, close the TUI first.
echo.
pause

echo.
echo Swapping: grok.exe.new -> grok.exe ...
move /Y grok.exe.new grok.exe >nul 2>&1
if errorlevel 1 (
    echo [FAILED] Could not replace grok.exe
    echo Make sure all grok.exe / Grok TUI processes are closed.
    echo (Check Task Manager for grok.exe or agent.exe)
    echo.
    pause
    exit /b 1
)

echo [OK] grok.exe replaced with the refreshed binary.
echo.

dir grok.exe* /b

echo.
echo Reinstall complete for main harness.
echo.
echo You can now launch Grok:
echo   - Run: grok
echo   - Or use your normal desktop shortcut / launcher
echo.
pause
endlocal