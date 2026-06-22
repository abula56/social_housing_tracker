@echo off
cd /d "%~dp0"

echo ================================
echo  社宅候補追蹤工具：每週更新
echo ================================

echo.
echo [1/4] 建立備份資料夾...
if not exist backup mkdir backup

set TODAY=%date:~0,4%-%date:~5,2%-%date:~8,2%

echo.
echo [2/4] 備份重要資料...
if exist my_applications.csv copy my_applications.csv backup\my_applications_%TODAY%.csv
if exist project_metadata.csv copy project_metadata.csv backup\project_metadata_%TODAY%.csv
if exist detail_queue_stats_history.csv copy detail_queue_stats_history.csv backup\detail_queue_stats_history_%TODAY%.csv

echo.
echo [3/4] 爬取官方遞補資料...
C:/Users/sam00/AppData/Local/Programs/Python/Python311/python.exe scrape_all_detail_lists.py

echo.
echo [4/4] 分析遞補速度與我的預估結果...
C:/Users/sam00/AppData/Local/Programs/Python/Python311/python.exe analyze_queue_progress.py
C:/Users/sam00/AppData/Local/Programs/Python/Python311/python.exe estimate_my_applicaitons.py

echo.
echo ================================
echo  每週更新完成
echo ================================

pause