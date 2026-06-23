# 臺中社宅候補查詢工具

這是一個以 Streamlit 製作的臺中市社會住宅候補查詢工具。

使用者可以輸入自己的候補資訊，例如社會住宅、遞補類型、房型、戶別與候補序號，查詢目前公開候補名冊中的位置，並取得粗略的等待時間估算。

本工具不是臺中市政府官方網站，所有查詢與估算結果僅供參考。實際資格審查、通知、選屋與入住時間，仍以臺中市政府住宅發展工程處及官方社會住宅系統公告為準。

## 功能

目前提供以下功能：

* 查詢指定社宅、遞補類型、房型、戶別下的候補狀況
* 輸入自己的候補序號後，估算本名冊前方待遞補人數
* 若為「隨到隨辦」名冊，保守納入同案場前置「新案場招租」名冊尚待遞補人數
* 顯示保守估計前方等待人數
* 依不同時間基準估算平均每週推進人數與可能遞補完成日期
* 顯示官方候補資料與名冊概況
* 透過 GitHub Actions 定期更新公開資料

## 隱私說明

本工具不需要登入，也不會保存使用者輸入的候補序號或個人資料。

使用者在網頁上輸入的資料，只會用於當下查詢與估算，不會寫入資料庫，也不會用於通知、追蹤或其他用途。

## 使用方式

開啟 Streamlit 網頁後，依序選擇：

1. 社會住宅
2. 遞補類型
3. 房型
4. 戶別
5. 我的候補序號

按下「開始查詢」後，系統會顯示：

* 本名冊前方待遞補人數
* 前置名冊待遞補人數
* 保守估計前方等待人數
* 完整預估表
* 對應名冊統計
* 對應候補名冊資料

## 估算邏輯簡述

本工具的估算採取保守原則。

### 本名冊前方待遞補人數

系統會依照公開候補名冊，計算同一社宅、同一遞補類型、同一房型、同一戶別下，候補序號小於使用者輸入序號，且尚未遞補完成的人數。

### 前置名冊待遞補人數

若使用者查詢的是「隨到隨辦」名冊，系統會檢查同一社宅、房型、戶別下，是否仍有「新案場招租」名冊尚未遞補完成。

若有，這些人數會被視為前置名冊待遞補人數，加入保守估計。

### 保守估計前方等待人數

保守估計前方等待人數為：

```text
本名冊前方待遞補人數 + 前置名冊待遞補人數
```

### 等待時間預估

系統會依公開資料中的歷史變化，估算不同期間的平均每週推進人數。

目前包含：

* 營運以來
* 最近一個月
* 最近三個月
* 最近六個月
* 最近一年

若某段期間資料不足，或該期間沒有明確推進，系統會顯示無法估算，而不會任意套用其他期間的速度。

## 資料來源

本工具使用臺中市社會住宅線上申請系統中的公開候補名冊資料進行整理與估算。

資料檔案包含：

```text
project_links.csv
project_metadata.csv
detail_queue_records.csv
detail_queue_stats.csv
detail_queue_stats_history.csv
queue_progress_analysis.csv
queue_event_log.csv
```

資料會透過 GitHub Actions 定期重新抓取與更新。

## 專案檔案說明

主要檔案如下：

```text
query_app.py
```

Streamlit 公開查詢頁主程式。

```text
query_estimator.py
```

候補人數與等待時間估算邏輯。

```text
build_project_links.py
```

建立社宅案場與候補名冊連結資料。

```text
scrape_all_detail_lists.py
```

抓取各案場詳細候補名冊。

```text
analyze_queue_progress.py
```

分析候補名冊推進狀況。

```text
build_event_log.py
```

建立候補資料變動紀錄。

```text
constants.py
utils.py
```

共用常數與工具函數。

```text
.github/workflows/update_queue_data.yml
```

GitHub Actions 自動更新流程。

## 本機執行

### 1. 建立虛擬環境

```bash
python -m venv .venv
source .venv/bin/activate
```

Windows PowerShell 可使用：

```powershell
.venv\Scripts\Activate.ps1
```

### 2. 安裝套件

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

### 3. 更新資料

```bash
python build_project_links.py
python scrape_all_detail_lists.py
python analyze_queue_progress.py
python build_event_log.py
```

### 4. 啟動查詢網頁

```bash
python -m streamlit run query_app.py
```

## 部署到 Streamlit Cloud

Streamlit Cloud 設定：

```text
Repository: abula56/social_housing_tracker
Branch: main
Main file path: query_app.py
```

部署後，Streamlit Cloud 會讀取 repository 中的 CSV 檔案作為查詢資料來源。

## GitHub Actions 自動更新

本專案包含 GitHub Actions workflow：

```text
.github/workflows/update_queue_data.yml
```

它會定期執行：

```bash
python build_project_links.py
python scrape_all_detail_lists.py
python analyze_queue_progress.py
python build_event_log.py
```

並將更新後的 CSV 檔案 commit 回 repository。

也可以手動觸發：

```bash
gh workflow run "Update queue data" --repo abula56/social_housing_tracker --ref main
```

查看最近執行狀態：

```bash
gh run list --workflow="update_queue_data.yml" --repo abula56/social_housing_tracker --limit 3
```

## 注意事項

本工具僅依公開資料進行整理與推估，可能受到以下因素影響：

* 官方資料更新時間
* 名冊格式變動
* 候補人員資格審查結果
* 放棄、取消、遞補、選屋等行政流程
* 不同案場實際釋出戶數與作業速度

因此，預估日期不應視為保證結果。

如需確認正式候補、資格審查、通知或選屋資訊，請以臺中市政府官方公告與通知為準。

## 授權

本專案目前作為公開查詢工具使用。若引用、修改或再利用，請保留非官方工具與資料來源說明。
