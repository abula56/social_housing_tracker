# 臺中社宅候補追蹤工具

這是一個用來追蹤臺中市社會住宅候補名冊變動的自架工具。

本工具可以：

* 抓取公開候補名冊
* 統計各案場、房型、戶別的遞補進度
* 估算個人候補序號前方仍有多少人
* 顯示 Streamlit dashboard
* 產生每日摘要
* 透過 LINE Messaging API 傳送通知

本工具不是臺中市政府官方工具，估算結果僅供參考，不代表官方承諾或實際通知結果。

---

## 專案定位

這個 repository 是 starter 版本，適合使用者 clone 後自行設定、自行執行。

目前不是多人雲端服務，因此不會替使用者保存資料，也不會代替使用者發送 LINE 通知。使用者需要在自己的電腦或伺服器上設定自己的候補資料與 LINE token。

---

## 安裝方式

請先安裝 Python 3.11 或更新版本。

下載專案後，進入專案資料夾：

```powershell
cd social_housing_tracker_starter
```

建議建立虛擬環境：

```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

安裝套件：

```powershell
pip install -r requirements.txt
```

---

## 建立自己的候補資料

本專案不會提供或保存你的私人候補資料。

請先複製範例檔：

```powershell
Copy-Item sample_my_applications.csv my_applications.csv
```

然後打開 `my_applications.csv`，改成自己的候補資料。

格式如下：

```csv
社會住宅,遞補類型,房型,戶別,我的候補序號,營運開始日,備註
西屯國安一期,隨到隨辦,三房型,一般戶,2,,範例資料，請改成自己的候補資料
```

欄位說明：

* `社會住宅`：社宅案場名稱
* `遞補類型`：例如 `新案場招租` 或 `隨到隨辦`
* `房型`：例如 `一房型`、`二房型`、`三房型`
* `戶別`：例如 `一般戶`、`關懷戶`
* `我的候補序號`：你的候補序號
* `營運開始日`：可留空，目前主要使用 `project_metadata.csv`
* `備註`：可自行填寫

---

## 第一次完整更新

第一次使用時，請執行完整更新：

```powershell
.\run_full_refresh.bat
```

完整更新會依序執行：

1. 建立官方名冊連結
2. 抓取詳細候補名冊
3. 分析遞補進度
4. 建立名冊變動事件
5. 產生每日摘要
6. 若有設定 LINE 環境變數，則傳送 LINE 通知

如果沒有設定 LINE，程式會略過 LINE 通知，不會因此失敗。

---

## 日常更新

之後日常更新可以執行：

```powershell
.\run_daily_tracker.bat
```

日常更新不會重新建立官方名冊連結，只會使用既有的 `project_links.csv` 抓取資料。

如果官方新增案場、連結規則改變，或 `project_links.csv` 遺失，請重新執行：

```powershell
.\run_full_refresh.bat
```

---

## 查看 dashboard

執行：

```powershell
python -m streamlit run app.py
```

dashboard 目前包含：

* 我的申請
* 變動與趨勢
* 候補設定
* 官方資料
* 系統資訊

---

## LINE 通知設定

本工具使用 LINE Messaging API，不使用 LINE Notify。

如果要啟用 LINE 通知，需要先建立 LINE 官方帳號與 Messaging API channel，並取得：

* `LINE_CHANNEL_ACCESS_TOKEN`
* `LINE_RECIPIENT_ID`

請把它們設定成 Windows 使用者環境變數，不要寫進 `.py`、`.bat` 或 GitHub repository。

PowerShell 設定方式：

```powershell
[Environment]::SetEnvironmentVariable("LINE_CHANNEL_ACCESS_TOKEN", "你的 Channel access token", "User")
[Environment]::SetEnvironmentVariable("LINE_RECIPIENT_ID", "你的 userId 或 groupId", "User")
```

設定後，請重新開啟 PowerShell，再測試：

```powershell
python generate_daily_summary.py
python send_line_summary.py
```

---

## Windows 工作排程器

若要每日自動執行，可以使用 Windows 工作排程器。

建議動作設定：

程式或指令碼：

```text
C:\你的專案路徑\run_daily_tracker.bat
```

起始位置：

```text
C:\你的專案路徑
```

建議每天早上固定執行一次。

---

## 不應該 commit 的檔案

以下檔案通常是本機資料、私人資料或自動產生資料，不應該 commit：

```text
my_applications.csv
my_application_estimates.csv
detail_queue_records.csv
detail_queue_stats.csv
detail_queue_stats_history.csv
queue_progress_analysis.csv
queue_event_log.csv
daily_queue_summary.txt
logs/
.env
.streamlit/secrets.toml
```

本 repository 的 `.gitignore` 已盡量排除這些檔案，但 commit 前仍建議先檢查：

```powershell
git status
```

---

## 注意事項

本工具依賴臺中市社會住宅公開候補名冊資料。若官方網站格式改變，爬蟲可能需要更新。

本工具的預估日期只是根據目前資料與歷史推進速度計算，不代表官方實際通知時間。

使用者應以臺中市政府或官方社宅平台公告為準。
