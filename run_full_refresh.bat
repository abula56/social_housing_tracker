@echo off
setlocal EnableExtensions

set "PROJECT_DIR=%~dp0"
set "PYTHON_EXE=python"
set "LOG_DIR=%PROJECT_DIR%logs"

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "RUN_ID=%%i"

set "LOG_FILE=%LOG_DIR%\full_refresh_%RUN_ID%.log"
set "LATEST_LOG=%LOG_DIR%\latest_full_refresh.log"

cd /d "%PROJECT_DIR%"

call :log "=============================="
call :log "台中社宅候補追蹤工具：完整更新"
call :log "執行時間：%RUN_ID%"
call :log "專案資料夾：%PROJECT_DIR%"
call :log "Python：%PYTHON_EXE%"
call :log "=============================="

call :run_step "1/6 建立官方名冊連結" build_project_links.py
if errorlevel 1 goto error

call :run_step "2/6 抓取詳細候補名冊" scrape_all_detail_lists.py
if errorlevel 1 goto error

call :run_step "3/6 分析遞補進度" analyze_queue_progress.py
if errorlevel 1 goto error

call :run_step "4/6 建立名冊變動事件" build_event_log.py
if errorlevel 1 goto error

call :run_step "5/6 產生每日摘要" generate_daily_summary.py
if errorlevel 1 goto error

call :log ""
call :log "[6/6 傳送 LINE 通知]"

if not exist "send_line_summary.py" (
    call :log "略過 LINE 通知：找不到 send_line_summary.py"
    goto success
)

if "%LINE_CHANNEL_ACCESS_TOKEN%"=="" (
    call :log "略過 LINE 通知：尚未設定 LINE_CHANNEL_ACCESS_TOKEN"
    goto success
)

if "%LINE_RECIPIENT_ID%"=="" (
    call :log "略過 LINE 通知：尚未設定 LINE_RECIPIENT_ID"
    goto success
)

"%PYTHON_EXE%" send_line_summary.py >> "%LOG_FILE%" 2>&1
if errorlevel 1 goto error
call :log "完成：send_line_summary.py"

:success
call :log ""
call :log "完整更新流程完成。"
copy /y "%LOG_FILE%" "%LATEST_LOG%" >nul

forfiles /p "%LOG_DIR%" /m full_refresh_*.log /d -30 /c "cmd /c del @path" >nul 2>&1

exit /b 0


:run_step
call :log ""
call :log "[%~1]"

if not exist "%~2" (
    call :log "失敗：找不到 %~2"
    exit /b 1
)

"%PYTHON_EXE%" "%~2" >> "%LOG_FILE%" 2>&1

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
call :log ""
call :log "發生錯誤，已停止後續流程。"
copy /y "%LOG_FILE%" "%LATEST_LOG%" >nul
exit /b 1