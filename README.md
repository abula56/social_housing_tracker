# 社宅候補追蹤工具

這是一個用來追蹤臺中市社會住宅候補／遞補進度的小工具。

目前功能包括：

1. 爬取官方遞補名冊
2. 儲存最新名冊與統計資料
3. 累積每週歷史統計
4. 計算最近遞補速度
5. 估算我的候補案場大約何時可能輪到
6. 用 Streamlit 顯示候補清單、官方統計與預估結果
7. 支援批次檔每週更新
8. 可設定 Windows 或 macOS 自動排程

---

## 一、主要使用方式

平常主要使用兩個批次檔：

### 1. 每週更新資料

雙擊：

```text
weekly_update.bat
```

這會依序執行：

```text
scrape_all_detail_lists.py
analyze_queue_progress.py
estimate_my_applicaitons.py
```

更新完成後，會產生或更新：

```text
detail_queue_records.csv
detail_queue_stats.csv
detail_queue_stats_history.csv
queue_progress_analysis.csv
my_application_estimates.csv
```

### 2. 開啟介面

雙擊：

```text
start_app.bat
```

或在 PowerShell 執行：

```powershell
streamlit run app.py
```

開啟後可在瀏覽器中查看：

```text
我的候補清單
我的遞補預估結果
目前官方遞補統計
最後號預估遞補完成日期
```

---

## 二、建議每週流程

建議每週固定做一次：

```text
1. 雙擊 weekly_update.bat
2. 等待爬蟲與分析完成
3. 雙擊 start_app.bat
4. 查看我的遞補預估結果
```

如果官方網站結構改變，爬蟲可能失敗；此時先不要覆蓋或手動亂改 CSV，應先檢查錯誤訊息。

---

## 三、重要檔案說明

### app.py

Streamlit 介面。

負責顯示：

```text
我的候補設定
目前候補清單
我的遞補預估結果
目前官方遞補統計
最後號預估遞補完成日期
```

也可以在這裡新增或刪除自己的候補資料。

---

### build_project_links.py

用來取得各社宅案場的遞補清單網址。

輸出：

```text
project_links.csv
```

通常不需要每週執行，除非官方網站新增案場或連結改變。

---

### scrape_all_detail_lists.py

主要爬蟲。

負責讀取：

```text
project_links.csv
```

並輸出：

```text
detail_queue_records.csv
detail_queue_stats.csv
detail_queue_stats_history.csv
```

其中：

```text
detail_queue_records.csv
```

是最新的個別候補名冊。

```text
detail_queue_stats.csv
```

是最新的各案場、房型、戶別統計。

```text
detail_queue_stats_history.csv
```

是累積歷史統計，用來追蹤每週遞補速度。

---

### analyze_queue_progress.py

讀取：

```text
detail_queue_stats_history.csv
```

並產生：

```text
queue_progress_analysis.csv
```

用來計算：

```text
已處理人數
上次已處理人數
本週推進人數
最近4次平均推進人數
```

注意：「本週推進人數」實際上是「本次抓取與上次抓取之間的推進人數」。如果不是每週固定抓取，就不一定等於一週速度。

---

### estimate_my_applicaitons.py

讀取：

```text
my_applications.csv
detail_queue_records.csv
detail_queue_stats.csv
project_metadata.csv
queue_progress_analysis.csv
```

並產生：

```text
my_application_estimates.csv
```

用來估算我的候補進度。

目前會同時輸出兩種估算：

```text
營運以來速度估算
最近4次速度估算
```

> 注意：檔名目前是 `estimate_my_applicaitons.py`，其中 `applicaitons` 拼字不是標準英文，但只要檔名與批次檔中一致即可正常執行。若要改名，所有批次檔與 README 中的引用也要一起改。

---

## 四、重要 CSV 檔案說明

### my_applications.csv

我的候補資料。

主要欄位：

```text
社會住宅
房型
戶別
我的候補序號
備註
```

這個檔案可透過 `app.py` 新增或刪除資料，不建議手動亂改。

---

### project_metadata.csv

各社宅案場的營運日期或推估用日期。

主要用於計算：

```text
營運以來平均每週推進人數
```

如果某案場營運時間不準，營運以來速度估算就會失真。

---

### detail_queue_records.csv

最新官方個別名冊。

主要欄位：

```text
抓取日期
社會住宅
房型
戶別
候補序號
遞補狀態
```

用來判斷我的候補序號目前是：

```text
待遞補
已遞補
已放棄
名冊中找不到我的序號
```

---

### detail_queue_stats.csv

最新官方統計。

主要欄位：

```text
抓取日期
社會住宅
房型
戶別
已遞補人數
已放棄人數
待遞補人數
名冊總人數
實際放棄率
```

---

### detail_queue_stats_history.csv

每週累積統計。

這是很重要的歷史資料，請不要刪除。

如果刪除，就無法計算最近速度。

---

### queue_progress_analysis.csv

由 `analyze_queue_progress.py` 產生。

用來記錄各案場近期推進速度。

重要欄位：

```text
已處理人數
上次已處理人數
本週推進人數
最近4次平均推進人數
```

---

### my_application_estimates.csv

由 `estimate_my_applicaitons.py` 產生。

這是我的個人預估結果。

重要欄位：

```text
我的目前狀態
前方待遞補人數
已處理人數
營運以來平均每週推進人數
營運以來速度預估剩餘週數
營運以來速度預估遞補完成日期
最近4次平均推進人數
最近速度預估剩餘週數
最近速度預估遞補完成日期
```

---

## 五、估算邏輯說明

### 已處理人數

```text
已處理人數 = 已遞補人數 + 已放棄人數
```

因為對候補進度來說，不管前面的人是接受遞補還是放棄，都代表名冊往前推進。

---

### 營運以來速度

```text
營運以來平均每週推進人數 = 已處理人數 ÷ 營運以來經過週數
```

優點：資料基礎較長。  
缺點：可能被早期大量放棄或長期停滯稀釋，不一定反映最近速度。

---

### 最近4次速度

```text
最近4次平均推進人數 = 最近幾次抓取之間的平均推進人數
```

優點：比較接近近期狀況。  
缺點：歷史資料太少時容易不穩定。

---

### 我的預估日期

```text
預估剩餘週數 = 前方待遞補人數 ÷ 平均每週推進人數
```

再用今天日期加上剩餘週數，得到預估遞補完成日期。

---

### 最後號預估遞補完成日期

在 `app.py` 的「目前官方遞補統計」中，最後號預估是用：

```text
最後號預估剩餘週數 = 待遞補人數 ÷ 最近4次平均推進人數
```

再用今天日期加上剩餘週數，得到：

```text
最後號預估遞補完成日期
```

這個欄位不是個人預估，而是該案場、房型、戶別目前名冊中最後一位待遞補者的粗略預估時間。

---

## 六、注意事項

1. 預估日期只是依目前名冊推進速度推算，不代表官方承諾。
2. 實際遞補會受到釋出戶數、放棄率、官方更新頻率、資格審查等影響。
3. 若 `我的目前狀態` 顯示「名冊中找不到我的序號」，請確認：
   - 社會住宅是否正確
   - 房型是否正確
   - 戶別是否正確
   - 我的候補序號是否為官方遞補清單中的序號
4. 若官方網站改版，爬蟲可能需要修改。
5. 不要刪除 `detail_queue_stats_history.csv`，否則最近速度資料會消失。
6. 如果「營運以來速度」與「最近速度」差很多，通常不是程式錯，而是兩者估算基礎不同。

---

## 七、建議備份

重要檔案：

```text
my_applications.csv
project_metadata.csv
detail_queue_stats_history.csv
```

建議每週更新前備份一次。

如果已經在 `weekly_update.bat` 裡加入備份功能，確認 `backup/` 資料夾內有日期版本的 CSV。

---

## 八、常見問題

### Q1：為什麼 app.py 不能直接雙擊？

Streamlit app 不能用普通 Python 方式執行。

錯誤方式：

```powershell
python app.py
```

正確方式：

```powershell
streamlit run app.py
```

或雙擊：

```text
start_app.bat
```

---

### Q2：為什麼最近4次平均推進人數是空白？

通常是因為歷史資料還不夠。

至少要有兩次以上的歷史統計，才有辦法算「本次比上次推進多少」。

---

### Q3：為什麼營運以來估算和最近速度估算差很多？

這是正常的。

營運以來速度看的是長期平均；最近速度看的是近期推進。  
如果案場早期很快、後期很慢，或早期很慢、近期突然加速，兩者就會差很多。

---

### Q4：為什麼我的狀態顯示待遞補，但日期很久？

表示你確實在名冊中，但前方待遞補人數仍多，或目前推進速度慢。

---

### Q5：為什麼候補清單裡出現兩個營運日期或 `_x`、`_y` 欄位？

通常是 `my_applications.csv` 和 `project_metadata.csv` 有同名欄位，合併時 pandas 自動加上 `_x`、`_y`。  
解法是在 `app.py` 合併 metadata 時，只選取需要的欄位，例如：

```text
社會住宅
推估用日期
日期精度
資料等級
資料依據
來源網址
```

不要整張 `project_metadata.csv` 都 merge 進來。

---

## 九、目前建議維護方式

不要頻繁改核心邏輯。

目前只需要：

```text
每週更新一次
確認 CSV 有備份
確認 app 顯示正常
確認我的候補序號正確
```

如果要新增功能，優先考慮：

```text
顯示更清楚
備份更穩定
錯誤訊息更容易看懂
```

不要急著做：

```text
自動登入
自動通知
LINE bot
```

那些會大幅增加維護成本。

---

## 十、設定自動排程更新

如果不想每週手動雙擊 `weekly_update.bat`，可以用作業系統內建排程工具自動執行。

建議排程執行的是：

```text
weekly_update.bat
```

而不是直接執行 Python 檔案，因為 `.bat` 已經包含完整流程：

```text
scrape_all_detail_lists.py
analyze_queue_progress.py
estimate_my_applicaitons.py
```

---

### Windows：使用工作排程器

#### 方式一：用圖形介面設定

1. 開啟 Windows 搜尋，輸入：

```text
工作排程器
```

2. 點選右側：

```text
建立基本工作
```

3. 名稱可填：

```text
社宅候補每週更新
```

4. 觸發程序選擇：

```text
每週
```

5. 設定執行日期與時間，例如：

```text
每週一 09:00
```

6. 動作選擇：

```text
啟動程式
```

7. 在「程式或指令碼」選擇你的批次檔，例如：

```text
C:\Users\sam00\OneDrive\social_housing_tracker_starter\weekly_update.bat
```

8. 「起始於」建議填專案資料夾：

```text
C:\Users\sam00\OneDrive\social_housing_tracker_starter
```

9. 完成後，可在工作排程器中右鍵該工作，選擇：

```text
執行
```

用來測試是否能正常更新。

---

#### 方式二：用指令建立排程

在 PowerShell 或命令提示字元中執行：

```powershell
schtasks /Create /SC WEEKLY /D MON /TN "社宅候補每週更新" /TR "C:\Users\sam00\OneDrive\social_housing_tracker_starter\weekly_update.bat" /ST 09:00
```

這會建立一個每週一早上 9 點執行的排程。

如果要手動測試：

```powershell
schtasks /Run /TN "社宅候補每週更新"
```

如果要刪除排程：

```powershell
schtasks /Delete /TN "社宅候補每週更新"
```

---

### macOS：使用 launchd

macOS 不使用 `.bat`，建議另外建立一個 shell script，例如：

```text
weekly_update.sh
```

放在專案資料夾中。

內容範例：

```bash
#!/bin/bash

cd "$(dirname "$0")"

/usr/bin/python3 scrape_all_detail_lists.py
/usr/bin/python3 analyze_queue_progress.py
/usr/bin/python3 estimate_my_applicaitons.py
```

儲存後，在終端機執行：

```bash
chmod +x weekly_update.sh
```

---

#### 建立 launchd plist

建立檔案：

```text
~/Library/LaunchAgents/com.socialhousing.weeklyupdate.plist
```

內容範例：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key>
    <string>com.socialhousing.weeklyupdate</string>

    <key>ProgramArguments</key>
    <array>
      <string>/bin/bash</string>
      <string>/Users/YOUR_USERNAME/OneDrive/social_housing_tracker_starter/weekly_update.sh</string>
    </array>

    <key>WorkingDirectory</key>
    <string>/Users/YOUR_USERNAME/OneDrive/social_housing_tracker_starter</string>

    <key>StartCalendarInterval</key>
    <dict>
      <key>Weekday</key>
      <integer>1</integer>
      <key>Hour</key>
      <integer>9</integer>
      <key>Minute</key>
      <integer>0</integer>
    </dict>

    <key>StandardOutPath</key>
    <string>/Users/YOUR_USERNAME/OneDrive/social_housing_tracker_starter/weekly_update.log</string>

    <key>StandardErrorPath</key>
    <string>/Users/YOUR_USERNAME/OneDrive/social_housing_tracker_starter/weekly_update_error.log</string>
  </dict>
</plist>
```

請把：

```text
YOUR_USERNAME
```

改成你的 macOS 使用者名稱。

---

#### 載入排程

在終端機執行：

```bash
launchctl load ~/Library/LaunchAgents/com.socialhousing.weeklyupdate.plist
```

如果要手動測試：

```bash
launchctl start com.socialhousing.weeklyupdate
```

如果要停用：

```bash
launchctl unload ~/Library/LaunchAgents/com.socialhousing.weeklyupdate.plist
```

---

### 排程注意事項

1. 排程執行時，電腦必須開機。
2. 如果電腦睡眠，排程可能不會準時執行。
3. Windows 建議在工作排程器中勾選「喚醒電腦以執行此工作」。
4. macOS 若使用 OneDrive 資料夾，需確認 OneDrive 已同步完成。
5. 若爬蟲需要開啟瀏覽器，排程執行時使用者環境可能會影響 Playwright 是否正常啟動。
6. 第一次設定排程後，務必手動測試一次。
7. 若排程失敗，先檢查：
   - Python 路徑是否正確
   - 專案資料夾路徑是否正確
   - `weekly_update.bat` 或 `weekly_update.sh` 是否可手動執行
   - 官方網站是否改版
   - log 檔是否有錯誤訊息

---

## 十一、建議專案結構

```text
social_housing_tracker_starter/
├─ app.py
├─ build_project_links.py
├─ scrape_all_detail_lists.py
├─ analyze_queue_progress.py
├─ estimate_my_applicaitons.py
├─ weekly_update.bat
├─ start_app.bat
├─ README.md
├─ project_links.csv
├─ my_applications.csv
├─ project_metadata.csv
├─ detail_queue_records.csv
├─ detail_queue_stats.csv
├─ detail_queue_stats_history.csv
├─ queue_progress_analysis.csv
├─ my_application_estimates.csv
└─ backup/
```

---

## 十二、版本狀態

目前版本可視為：

```text
v1.0：可用版
```

已完成：

```text
官方遞補名冊爬取
每週歷史資料累積
最近速度分析
個人候補進度估算
Streamlit 視覺化介面
批次檔更新
自動排程說明
```

接下來除非必要，不建議大幅重構核心邏輯。
