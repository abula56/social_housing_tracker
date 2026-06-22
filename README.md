# 社宅候補追蹤工具

這是一個用來追蹤臺中市社會住宅候補／遞補進度的小工具。

它的主要目標不是單純保存官方名冊，而是把「官方目前候補狀態」和「自己的候補序號」結合，讓使用者可以快速判斷：

- 我目前在名冊中的狀態是什麼？
- 我前面大約還有多少人待遞補？
- 如果依照不同時間尺度的推進速度估算，大約什麼時候可能輪到？
- 哪些案場比較值得繼續等待？

> 注意：所有預估結果都只是依據目前名冊與歷史推進速度計算，不代表官方承諾，也不能作為正式申請、選屋或放棄申請的唯一依據。

---

## 一、目前功能

目前功能包括：

1. 爬取官方遞補名冊。
2. 儲存最新個別名冊與統計資料。
3. 累積歷史統計資料。
4. 計算案場、房型、戶別的遞補推進速度。
5. 新增、刪除自己的候補資料。
6. 在 Streamlit 中顯示「我的遞補總覽」。
7. 可用下拉選單切換不同估算基準：
   - 營運以來
   - 最近一個月
   - 最近三個月
   - 最近六個月
   - 最近一年
8. 可展開比較所有估算基準。
9. 可查看官方統計、metadata、檔案狀態等詳細資料。
10. 可部署到 Streamlit Cloud，分享給家人查看。

---

## 二、專案結構

目前主要檔案如下：

```text
social_housing_tracker/
├─ app.py
├─ build_project_links.py
├─ scrape_all_detail_lists.py
├─ analyze_queue_progress.py
├─ estimate_my_applicaitons.py
├─ project_links.csv
├─ project_metadata.csv
├─ requirements.txt
├─ run_scraper.bat
├─ 台中社宅追蹤工具.bat
├─ scraper_log.txt
└─ README.md
```

執行後可能產生下列資料檔：

```text
my_applications.csv
detail_queue_records.csv
detail_queue_stats.csv
detail_queue_stats_history.csv
queue_progress_analysis.csv
my_application_estimates.csv
backup/
```

其中 `my_applications.csv`、`detail_queue_stats_history.csv` 會涉及個人追蹤資料或長期歷史資料，請不要隨意刪除。

---

## 三、安裝方式

第一次使用前，先安裝 Python 套件。

```bash
pip install -r requirements.txt
```

目前 `requirements.txt` 包含：

```text
streamlit
pandas
openpyxl
```

如果你在 Windows PowerShell 中執行，可使用：

```powershell
pip install -r requirements.txt
```

---

## 四、主要使用方式

### 1. 更新官方資料

可以直接執行：

```bash
python scrape_all_detail_lists.py
python analyze_queue_progress.py
python estimate_my_applicaitons.py
```

或在 Windows 中雙擊：

```text
run_scraper.bat
```

`run_scraper.bat` 目前會依序做：

1. 建立 `backup/` 資料夾。
2. 備份重要 CSV。
3. 執行 `scrape_all_detail_lists.py`。
4. 執行 `analyze_queue_progress.py`。
5. 執行 `estimate_my_applicaitons.py`。

> 注意：目前 `run_scraper.bat` 內可能使用你本機的 Python 絕對路徑。如果換電腦、換 Python 版本、或部署到別的環境，需要檢查批次檔中的 Python 路徑。

---

### 2. 開啟 Streamlit 介面

可在終端機執行：

```bash
streamlit run app.py
```

或在 Windows 中雙擊：

```text
台中社宅追蹤工具.bat
```

開啟後會在瀏覽器中看到「社宅候補追蹤工具」。

---

## 五、Streamlit 介面說明

新版 `app.py` 的首頁以「我的遞補總覽」為主。

### 1. 我的遞補總覽

首頁會整合：

- 我的候補設定
- 官方逐筆名冊
- 我的目前遞補狀態
- 前方待遞補人數
- 所選估算基準
- 平均每週推進人數
- 預估剩餘週數
- 預估遞補完成日期
- 資料取得日
- 備註

首頁主要欄位為：

```text
社宅
房型
戶別
我的序號
狀態
前面約剩幾位
估算基準
平均每週推進人數
預估剩餘週數
預估遞補完成日期
資料取得日
備註
```

這張表是給日常決策使用的，不是完整資料庫匯出。

---

### 2. 估算基準下拉選單

首頁提供下拉選單，可以選擇：

```text
營運以來
最近一個月
最近三個月
最近六個月
最近一年
```

各基準意義如下：

| 估算基準 | 意義 | 優點 | 風險 |
|---|---|---|---|
| 營運以來 | 從案場推估營運日期到目前為止的平均速度 | 資料期間最長，較穩定 | 可能被早期大量放棄或長期停滯稀釋 |
| 最近一個月 | 使用最近約 30 天歷史資料估算 | 最貼近近期狀況 | 容易受短期波動影響 |
| 最近三個月 | 使用最近約 90 天歷史資料估算 | 兼顧近期與穩定性 | 若歷史資料不足，會退而用可取得期間 |
| 最近六個月 | 使用最近約 180 天歷史資料估算 | 比三個月更平滑 | 可能反應較慢 |
| 最近一年 | 使用最近約 365 天歷史資料估算 | 較長期但仍比營運以來貼近近期 | 若案場資料不足一年，會使用可取得期間 |

目前預設選項是：

```text
最近三個月
```

這通常比「最近一個月」穩定，也比「營運以來」更接近近期狀況。

---

### 3. 比較所有估算基準

首頁下方有：

```text
比較所有估算基準
```

展開後可同時查看：

- 營運以來
- 最近一個月
- 最近三個月
- 最近六個月
- 最近一年

這個區塊適合用來判斷不同估算方式是否差距過大。

如果差距很大，通常代表該案場近期遞補速度和長期平均速度不同，不一定是程式錯。

---

### 4. 我的候補設定

可以在 Streamlit 介面中新增或刪除自己的候補資料。

新增時需要設定：

```text
社會住宅
房型
戶別
我的候補序號
備註
```

資料會存入：

```text
my_applications.csv
```

建議不要直接手動亂改 `my_applications.csv`，除非你很確定欄位格式正確。

---

### 5. 詳細資料

首頁下方的「詳細資料」收納了較工程化或驗算用的資料，包括：

- 目前候補設定原始資料
- 官方遞補統計
- 案場營運日期 metadata
- 估算檔案狀態

這些資料不放在首頁主表，是為了避免日常使用時過於雜亂。

---

## 六、重要 Python 檔案說明

### app.py

Streamlit 介面主程式。

目前負責：

- 顯示我的遞補總覽。
- 提供估算基準下拉選單。
- 即時計算營運以來、最近一個月、最近三個月、最近六個月、最近一年估算。
- 新增或刪除自己的候補資料。
- 顯示詳細資料與檔案狀態。

新版 `app.py` 不必依賴 `my_application_estimates.csv` 才能顯示首頁。它會直接使用下列資料重新計算：

```text
my_applications.csv
detail_queue_records.csv
detail_queue_stats.csv
detail_queue_stats_history.csv
queue_progress_analysis.csv
project_metadata.csv
```

其中 `detail_queue_stats_history.csv` 優先作為近期估算依據；如果沒有，才退而使用 `queue_progress_analysis.csv`。

---

### build_project_links.py

用來取得各社宅案場的遞補清單網址。

輸出：

```text
project_links.csv
```

通常不需要每次執行。只有在官方網站新增案場、刪除案場，或名冊連結改變時，才需要重新產生。

---

### scrape_all_detail_lists.py

主要爬蟲。

讀取：

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

是最新的逐筆候補名冊。

```text
detail_queue_stats.csv
```

是最新的各案場、房型、戶別統計。

```text
detail_queue_stats_history.csv
```

是累積歷史統計，用來計算最近一個月、三個月、六個月、一年的推進速度。

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

用來記錄各案場的歷史推進變化。

常見欄位包括：

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

這是舊版個人預估結果檔。新版 `app.py` 已經可以在介面中直接重新估算，因此這個檔案不是首頁顯示的必要條件。

不過保留這支程式仍然有用，因為它可以產生一份獨立的個人預估 CSV，方便備份或用 Excel 檢查。

> 注意：檔名目前是 `estimate_my_applicaitons.py`，其中 `applicaitons` 拼字不是標準英文，但只要檔名與批次檔中一致即可正常執行。若要改名，必須同步修改批次檔與 README。

---

## 七、重要 CSV 檔案說明

### project_links.csv

各社宅案場與官方名冊網址的對照表。

常見欄位：

```text
社會住宅
名冊網址
```

用途：

- 提供爬蟲要抓取的名冊連結。
- 提供 Streamlit 新增候補資料時的案場選單。

---

### my_applications.csv

自己的候補資料。

主要欄位：

```text
社會住宅
房型
戶別
我的候補序號
備註
```

用途：

- 讓程式知道你要追蹤哪些案場。
- 讓 Streamlit 計算你的目前狀態、前方待遞補人數與預估日期。

這是個人資料，若 repo 是 public，不應該上傳完整版本。

---

### project_metadata.csv

各社宅案場的營運日期或推估用日期。

主要欄位：

```text
社會住宅
推估用日期
日期精度
資料等級
資料依據
來源網址
```

用途：

- 計算「營運以來平均每週推進人數」。

如果某案場的推估用日期不準，營運以來速度估算就會失真。

---

### detail_queue_records.csv

最新官方逐筆候補名冊。

主要欄位：

```text
抓取日期
社會住宅
房型
戶別
候補序號
遞補狀態
```

用途：

- 判斷你的候補序號目前狀態。
- 計算你前面還有多少人處於「待遞補」。

常見狀態可能包括：

```text
待遞補
已遞補
已放棄
```

如果你的序號在名冊中找不到，Streamlit 會顯示：

```text
名冊中找不到我的序號
```

此時應檢查：

- 社會住宅名稱是否一致。
- 房型是否一致。
- 戶別是否一致。
- 我的候補序號是否輸入正確。
- 官方名冊是否已更新。

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

用途：

- 計算目前已處理人數。
- 計算營運以來平均推進速度。
- 顯示官方整體遞補統計。

---

### detail_queue_stats_history.csv

累積歷史官方統計。

這是近期估算最重要的檔案。

用途：

- 計算最近一個月、最近三個月、最近六個月、最近一年的推進速度。
- 比較近期速度與營運以來速度。
- 保存每次抓取時的案場統計狀態。

請不要刪除這個檔案。

如果刪除，近期估算會失去歷史基礎，只能從新的抓取紀錄重新累積。

---

### queue_progress_analysis.csv

由 `analyze_queue_progress.py` 產生。

用途：

- 記錄歷次抓取之間的推進變化。
- 可作為新版 `app.py` 近期估算的備用資料來源。

如果同時存在 `detail_queue_stats_history.csv` 與 `queue_progress_analysis.csv`，新版 `app.py` 會優先使用：

```text
detail_queue_stats_history.csv
```

---

### my_application_estimates.csv

由 `estimate_my_applicaitons.py` 產生。

這是舊版個人預估結果檔。

新版 `app.py` 不再需要依賴這個檔案才能顯示首頁，但仍可保留作為獨立匯出結果。

---

## 八、估算邏輯

### 1. 已處理人數

```text
已處理人數 = 已遞補人數 + 已放棄人數
```

理由是：對候補進度來說，不管前面的人是接受遞補還是放棄，都代表名冊往前推進。

---

### 2. 前方待遞補人數

```text
前方待遞補人數 =
同一社會住宅、同一房型、同一戶別中，
候補序號小於我的候補序號，
且遞補狀態仍為「待遞補」的人數
```

也就是說，已遞補或已放棄的人不再算在前方等待人數中。

---

### 3. 營運以來速度

```text
營運以來平均每週推進人數 =
目前已處理人數 ÷ 從推估用日期到資料取得日的經過週數
```

其中「推估用日期」來自：

```text
project_metadata.csv
```

優點：

- 資料期間較長。
- 比較不容易受短期波動影響。

缺點：

- 如果早期遞補很快、近期變慢，會高估速度。
- 如果早期長期停滯、近期變快，會低估速度。
- 如果案場推估用日期不準，整個估算會失真。

---

### 4. 最近期間速度

最近期間速度包括：

```text
最近一個月
最近三個月
最近六個月
最近一年
```

計算方式：

```text
最近期間平均每週推進人數 =
期間內已處理人數變化量 ÷ 實際經過天數 × 7
```

起點取法：

1. 優先找最接近視窗起點、且早於或等於該日期的歷史資料。
2. 如果沒有早於視窗起點的資料，就使用目前可取得的最早資料。
3. 終點使用最新一筆歷史資料。

因此，如果你選「最近一年」，但目前只累積三個月資料，程式會用目前可取得的三個月資料估算，並在備註中提醒資料不足。

---

### 5. 預估剩餘週數

```text
預估剩餘週數 =
前方待遞補人數 ÷ 平均每週推進人數
```

如果所選期間內沒有推進，平均每週推進人數為 0，則不會產生預估日期。

---

### 6. 預估遞補完成日期

```text
預估遞補完成日期 =
資料取得日 + 預估剩餘週數
```

這個日期只是粗估，不是官方保證。

---

## 九、建議使用流程

### 每次更新資料

建議流程：

```text
1. 執行 run_scraper.bat
2. 確認沒有爬蟲錯誤
3. 執行 streamlit run app.py
4. 查看「我的遞補總覽」
5. 用下拉選單比較不同估算基準
```

如果你已經部署到 Streamlit Cloud，還需要：

```bash
git add .
git commit -m "update housing queue data"
git push
```

Streamlit Cloud 會根據 repo 更新重新部署。

---

### 建議估算判讀方式

日常判斷時，建議優先看：

```text
最近三個月
```

再比較：

```text
營運以來
最近一年
```

如果最近三個月和營運以來差很多，應該展開「比較所有估算基準」檢查。

粗略判斷：

| 情況 | 可能意義 |
|---|---|
| 最近一個月很快，但三個月和六個月很慢 | 近期可能剛好集中遞補，不宜過度樂觀 |
| 最近三個月、六個月、一年都快 | 案場近期確實推進較快 |
| 營運以來快，但最近三個月慢 | 早期推進快，近期可能停滯 |
| 所有期間都很慢 | 等待時間可能很長 |
| 最近期間顯示無法估算 | 所選期間沒有推進，或歷史資料不足 |

---

## 十、分享給家人查看

如果只是自己本機使用，不需要部署。

如果要讓家人不用下載資料夾、直接用網址查看，建議使用：

```text
GitHub private repo
+
Streamlit Community Cloud private app
```

### 建議做法

1. 將 GitHub repo 改成 private。
2. 確認不要把不該公開的個資放在 public repo。
3. 將新版 `app.py`、`README.md` 和必要 CSV push 到 private repo。
4. 到 Streamlit Community Cloud 部署 `app.py`。
5. 在 Streamlit app 的 Share 設定中加入家人的 email。
6. 家人用連結登入後即可查看。

### 不建議的做法

不建議把完整個人候補資料放在 public GitHub repo。

尤其不應公開：

```text
完整申請編號
姓名
身分別
共同居住者資訊
戶籍資料
財稅資料
孕婦或醫療證明
完整個人候補序號與備註
```

如果 repo 必須維持 public，請不要上傳 `my_applications.csv` 的完整個人資料版本。

---

## 十一、部署到 Streamlit Cloud 時要注意

Streamlit Cloud 上的 app 只看得到 repo 裡有的檔案。

因此，如果要讓雲端 app 顯示完整結果，private repo 中至少需要有：

```text
app.py
requirements.txt
project_links.csv
project_metadata.csv
my_applications.csv
detail_queue_records.csv
detail_queue_stats.csv
detail_queue_stats_history.csv
```

如果沒有 `detail_queue_stats_history.csv`，則：

- 最近一個月
- 最近三個月
- 最近六個月
- 最近一年

可能無法正常估算。

如果沒有 `project_metadata.csv`，則：

- 營運以來

可能無法正常估算。

如果沒有 `detail_queue_records.csv`，則：

- 我的目前狀態
- 前方待遞補人數

可能無法正常計算。

---

## 十二、隱私與安全建議

這個工具雖然是小工具，但資料可能涉及家庭住居決策，不建議公開。

建議：

1. repo 改成 private。
2. 不要把身份證字號、戶籍資料、財稅資料、醫療證明放進 repo。
3. 不要把完整申請文件放進 repo。
4. `my_applications.csv` 只保留追蹤需要的最低限度欄位。
5. 若要公開展示作品，另做一份假資料 demo。
6. 若要分享給家人，使用 private app viewer，而不是 public URL。

---

## 十三、常見問題

### Q1：為什麼 Streamlit 顯示「尚未新增任何候補資料」？

通常是因為找不到：

```text
my_applications.csv
```

可以在 Streamlit 中的「我的候補設定」新增資料。

---

### Q2：為什麼顯示「找不到名冊資料」？

通常是以下原因之一：

1. 還沒有執行 `scrape_all_detail_lists.py`。
2. `detail_queue_records.csv` 不存在。
3. 你的社會住宅名稱、房型、戶別與官方資料不一致。
4. 官方網站結構改變，爬蟲沒有正確抓到資料。

---

### Q3：為什麼顯示「名冊中找不到我的序號」？

請確認：

1. 我的候補序號是否輸入正確。
2. 房型是否正確。
3. 戶別是否正確。
4. 社會住宅名稱是否完全一致。
5. 官方是否尚未更新你的資料。

---

### Q4：為什麼最近一個月無法估算？

可能原因：

1. 最近一個月內沒有任何推進。
2. 歷史資料少於兩筆。
3. 沒有 `detail_queue_stats_history.csv`。
4. 歷史資料中缺少 `抓取日期` 或 `已處理人數`。

---

### Q5：為什麼營運以來可以估，但最近三個月不能估？

因為兩者使用的資料不同。

營運以來主要依賴：

```text
detail_queue_stats.csv
project_metadata.csv
```

最近期間主要依賴：

```text
detail_queue_stats_history.csv
```

所以如果缺少歷史資料，近期估算就會失敗。

---

### Q6：為什麼不同估算基準差很多？

這很正常。

不同估算基準反映不同時間尺度：

- 營運以來：長期平均。
- 最近一個月：短期波動。
- 最近三個月：近期趨勢。
- 最近六個月：中期趨勢。
- 最近一年：較長期趨勢。

如果差距很大，應該把它視為「不確定性變高」，而不是選一個最樂觀的日期相信。

---

### Q7：為什麼 app.py 不能直接雙擊？

Streamlit app 不能用普通 Python 腳本方式開啟。

錯誤方式：

```bash
python app.py
```

正確方式：

```bash
streamlit run app.py
```

或使用批次檔：

```text
台中社宅追蹤工具.bat
```

---

### Q8：官方網站改版怎麼辦？

如果官方網站改版，爬蟲可能失敗。

此時應該先檢查：

```text
scraper_log.txt
```

以及終端機錯誤訊息。

不要直接手動亂改產生出來的 CSV，因為這可能讓後續估算更混亂。

---

## 十四、備份建議

重要檔案：

```text
my_applications.csv
project_metadata.csv
detail_queue_stats_history.csv
```

建議每次更新前備份。

目前 `run_scraper.bat` 已經有備份設計，會把重要檔案複製到：

```text
backup/
```

建議定期確認 `backup/` 裡真的有日期版本的 CSV。

---

## 十五、Git 更新流程

如果只是本機使用，不一定需要每次 push。

如果要讓 Streamlit Cloud 上的家人也看到最新結果，更新資料後需要：

```bash
git add .
git commit -m "update queue data"
git push
```

如果只是改程式：

```bash
git add app.py README.md
git commit -m "update dashboard and readme"
git push
```

---

## 十六、重要提醒

1. 預估日期不是官方承諾。
2. 遞補速度可能突然變快或突然停滯。
3. 釋出戶數、放棄率、審查速度、官方更新頻率都會影響結果。
4. 營運以來速度與近期速度差很多時，應該保守解讀。
5. 家庭決策不要只看單一估算日期。
6. 若涉及個資，repo 與 Streamlit app 都應設為 private。
