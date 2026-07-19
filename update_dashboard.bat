@echo off
REM ============================================================================
REM update_dashboard.bat — after a session: export executions from NT8 into
REM journal\trades\, then double-click this file. It rebuilds the dashboard
REM data and (once deployment is configured) pushes it to your live URL.
REM
REM data.js is uploaded to the host directly and is gitignored — P&L never
REM lands in the repo. See the one-command build, Step 5.
REM ============================================================================
cd /d "%~dp0"

if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
) else (
    echo [warn] no .venv found — using system python
)

python dashboard\build_data.py
if errorlevel 1 goto :err

REM ---- Deployment hook (created during Step 5 of the one-command build) ----
REM Put your deploy command in dashboard\deploy_cmd.bat (gitignored), e.g.:
REM   wrangler pages deploy dashboard --project-name=YOUR_PROJECT
REM   netlify deploy --prod --dir=dashboard
if exist dashboard\deploy_cmd.bat (
    call dashboard\deploy_cmd.bat
    if errorlevel 1 goto :err
) else (
    echo [info] no dashboard\deploy_cmd.bat yet — dashboard updated locally only.
    echo        Open dashboard\index.html in your browser to view it.
)

echo.
echo Dashboard updated.
pause
exit /b 0

:err
echo.
echo *** FAILED — see errors above. Paste them into Claude Code to fix. ***
pause
exit /b 1
