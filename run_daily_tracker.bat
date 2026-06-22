@echo off
setlocal EnableExtensions

chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

set "PROJECT_DIR=%~dp0"
set "PYTHON_EXE=python"
set "LOG_DIR=%PROJECT_DIR%logs"

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "RUN_ID=%%i"

set "LOG_FILE=%LOG_DIR%\daily_tracker_%RUN_ID%.log"
set "LATEST_LOG=%LOG_DIR%\latest_daily_tracker.log"

cd /d "%PROJECT_DIR%"

call :log "=============================="
call :log "Social Housing Tracker: Daily Update"
call :log "Run ID: %RUN_ID%"
call :log "Project Dir: %PROJECT_DIR%"
call :log "Python: %PYTHON_EXE%"
call :log "=============================="

call :run_step "1/5 Scrape detail queue lists" scrape_all_detail_lists.py
if errorlevel 1 goto error

call :run_step "2/5 Analyze queue progress" analyze_queue_progress.py
if errorlevel 1 goto error

call :run_step "3/5 Build event log" build_event_log.py
if errorlevel 1 goto error

call :run_step "4/5 Generate daily summary" generate_daily_summary.py
if errorlevel 1 goto error

call :log ""
call :log "[5/5 Send LINE summary]"

if not exist "send_line_summary.py" (
    call :log "Skip LINE: send_line_summary.py not found"
    goto success
)

if "%LINE_CHANNEL_ACCESS_TOKEN%"=="" (
    call :log "Skip LINE: LINE_CHANNEL_ACCESS_TOKEN is not set"
    goto success
)

if "%LINE_RECIPIENT_ID%"=="" (
    call :log "Skip LINE: LINE_RECIPIENT_ID is not set"
    goto success
)

"%PYTHON_EXE%" send_line_summary.py >> "%LOG_FILE%" 2>&1
if errorlevel 1 goto error
call :log "Done: send_line_summary.py"

:success
call :log ""
call :log "Daily update completed."
copy /y "%LOG_FILE%" "%LATEST_LOG%" >nul

forfiles /p "%LOG_DIR%" /m daily_tracker_*.log /d -30 /c "cmd /c del @path" >nul 2>&1

exit /b 0


:run_step
call :log ""
call :log "[%~1]"

if not exist "%~2" (
    call :log "ERROR: file not found: %~2"
    exit /b 1
)

"%PYTHON_EXE%" "%~2" >> "%LOG_FILE%" 2>&1

if errorlevel 1 (
    call :log "ERROR: failed: %~2"
    exit /b 1
)

call :log "Done: %~2"
exit /b 0


:log
echo [%date% %time%] %~1
echo [%date% %time%] %~1>> "%LOG_FILE%"
exit /b 0


:error
call :log ""
call :log "ERROR: workflow stopped."
copy /y "%LOG_FILE%" "%LATEST_LOG%" >nul
exit /b 1