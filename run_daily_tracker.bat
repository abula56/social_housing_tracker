@echo off
setlocal EnableExtensions

set "PROJECT_DIR=%~dp0"
set "PYTHON_EXE=python"
set "LOG_DIR=%PROJECT_DIR%logs"

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "RUN_ID=%%i"

set "LOG_FILE=%LOG_DIR%\daily_tracker_%RUN_ID%.log"
set "LATEST_LOG=%LOG_DIR%\latest_daily_tracker.log"

cd /d "%PROJECT_DIR%"

call :log "=============================="
call :log "台中社宅候補追蹤工具：每日自動更新"
call :log "執行時間：%RUN_ID%"
call :log "專案資料夾：%PROJECT_DIR%"
call :log "=============================="

call :run_step "1/5 抓取詳細候補名冊" scrape_all_detail_lists.py
if errorlevel 1 goto error

call :run_step "2/5 分析遞補進度" analyze_queue_progress.py
if errorlevel 1 goto error

call :run_step "3/5 建立名冊變動事件" build_event_log.py
if errorlevel 1 goto error

call :run_step "4/5 產生每日摘要" generate_daily_summary.py
if errorlevel 1 goto error

call :run_step "5/5 傳送 LINE 通知" send_line_summary.py
if errorlevel 1 goto error

call :log "全部流程完成。"
copy /y "%LOG_FILE%" "%LATEST_LOG%" >nul

exit /b 0

:run_step
call :log ""
call :log "[%~1]"
%PYTHON_EXE% "%~2" >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    call :log "失敗：%~2"
    exit /b 1
)
call :log "完成：%~2"
exit /b 0

:log
echo [%date% %time%] %~1
echo [%date% %time%] %~1>> "%LOG_FILE%"
exit /b 0

:error
call :log "發生錯誤，已停止後續流程。"
copy /y "%LOG_FILE%" "%LATEST_LOG%" >nul
exit /b 1