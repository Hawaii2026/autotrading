@echo off
REM ============================================================================
REM start_recorder.bat — record the KarenBridge market feed all session.
REM Read-only capture: polls Karen's GET feed endpoint, writes daily parquet
REM under research\data\ticks\, logs gaps >5s to journal\feed_gaps.log, and
REM feeds the dashboard's live quote strip (dashboard\live.js).
REM
REM Requires KAREN_FEED_URL in .env. Ctrl-C to stop (flushes cleanly).
REM DISPLAY-GRADE data (2 Hz sampled upstream) — never backtest on it.
REM ============================================================================
cd /d "%~dp0"

if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
) else (
    echo [warn] no .venv found — using system python
)

python -m research.lib.tick_recorder %*
pause
