@echo off
REM Test script for additional computers (Sub-Engel) usage for AI
REM Run on main PC after setting up a second machine with Engel OS or Windows Sub-Engel package.
REM Requires the packages populated (item 1) and consumer wired.

echo Testing Sub-Engel job dispatch for more computer AI usage...
python engel_ai.py ask "sub engel status"
python engel_ai.py ask "sub engel create job sub_engel_os_worker|summarize_text|Test Note|Summarize this test instruction for additional computer."

echo.
echo On the Sub-Engel node (Engel OS):
echo   engel-node jobs   (or look in /opt/engel-node/jobs )
echo   engel cluster status
echo.
echo Then stage a result in the expected outbox and call complete on main if needed.
pause
