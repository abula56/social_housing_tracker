from datetime import date
from pathlib import Path
import re

import pandas as pd
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from constants import KEY_COLUMNS


BASE_DIR = Path(__file__).parent

PROJECT_LINKS_FILE = BASE_DIR / "project_links.csv"
RECORDS_OUTPUT_FILE = BASE_DIR / "detail_queue_records.csv"
STATS_OUTPUT_FILE = BASE_DIR / "detail_queue_stats.csv"
STATS_HISTORY_FILE = BASE_DIR / "detail_queue_stats_history.csv"

ROOM_TYPES = ["一房型", "二房型", "三房型"]
HOUSEHOLD_TYPES = ["一般戶", "關懷戶"]

STATS_COLUMNS = [
    "抓取日期",
    "社會住宅",
    "遞補類型",
    "房型",
    "戶別",
    "已遞補人數",
    "已放棄人數",
    "待遞補人數",
    "名冊總人數",
    "實際放棄率",
]

RECORD_COLUMNS = [
    "抓取日期",
    "社會住宅",
    "遞補類型",
    "房型",
    "戶別",
    "候補序號",
    "遞補狀態",
]


def wait_for_room_buttons(page) -> bool:
    """等待官方頁面的房型按鈕載入。"""
    for _ in range(15):
        for room_type in ROOM_TYPES:
            if page.get_by_role("button", name=room_type).count() > 0:
                return True
        page.wait_for_timeout(1000)

    return False


def get_available_room_types(page) -> list[str]:
    """取得目前頁面實際存在的房型。"""
    available_room_types = []

    for room_type in ROOM_TYPES:
        if page.get_by_role("button", name=room_type).count() > 0:
            available_room_types.append(room_type)

    return available_room_types


def clean_text(text) -> str:
    """移除一般空白與全形空白。"""
    return re.sub(r"[\s\u3000]+", "", str(text))


def extract_number_from_rank(rank_text):
    """從候補序號文字中擷取整數。"""
    match = re.search(r"\d+", str(rank_text))

    if match:
        return int(match.group(0))

    return None


def load_project_links() -> pd.DataFrame:
    """讀取案場名冊連結。"""
    if not PROJECT_LINKS_FILE.exists():
        raise FileNotFoundError(
            "找不到 project_links.csv，請先執行 build_project_links.py"
        )

    df = pd.read_csv(PROJECT_LINKS_FILE, encoding="utf-8-sig")

    required_columns = ["社會住宅", "遞補類型", "名冊網址"]
    missing_columns = [
        column for column in required_columns if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            "project_links.csv 缺少必要欄位："
            + ", ".join(missing_columns)
            + "。請先用新版 build_project_links.py 重新產生 project_links.csv。"
        )

    return df


def click_filter(page, text: str) -> bool:
    """點擊房型或戶別篩選按鈕。"""
    button = page.get_by_role("button", name=text)

    if button.count() == 0:
        print(f"找不到按鈕：{text}")
        return False

    button.click(force=True)

    # 官方頁面是前端動態切換；太快解析可能抓到上一個房型或戶別。
    page.wait_for_timeout(2500)

    return True


def get_visible_tables(page):
    """只解析目前畫面可見的表格，避免抓到 DOM 中隱藏的舊表格。"""
    try:
        visible_tables_html = page.locator("table:visible").evaluate_all(
            "(tables) => tables.map((table) => table.outerHTML)"
        )
    except Exception:
        print("警告：無法取得 visible table，退回 page.content() 解析。")
        html = page.content()
        soup = BeautifulSoup(html, "html.parser")
        return soup.find_all("table")

    tables = []

    for table_html in visible_tables_html:
        table_soup = BeautifulSoup(table_html, "html.parser")
        table = table_soup.find("table")

        if table is not None:
            tables.append(table)

    return tables


def parse_detail_table(
    page,
    project_name: str,
    queue_type: str,
    room_type: str,
    household_type: str,
) -> pd.DataFrame:
    """解析目前篩選條件下的候補名冊。"""
    tables = get_visible_tables(page)

    if not tables:
        return pd.DataFrame(columns=RECORD_COLUMNS)

    records = []

    for table in tables:
        rows = table.find_all("tr")

        if len(rows) < 2:
            continue

        header_cells = rows[0].find_all(["th", "td"])
        headers = [
            clean_text(cell.get_text(strip=True))
            for cell in header_cells
        ]

        # 官方名冊欄位通常包含：
        # 序號／收件編號／姓名／身分證字號／關懷戶／遞補狀態
        if "序號" in headers:
            rank_index = headers.index("序號")
        elif "候補序號" in headers:
            rank_index = headers.index("候補序號")
        elif "遞補序號" in headers:
            rank_index = headers.index("遞補序號")
        else:
            continue

        if "遞補狀態" in headers:
            status_index = headers.index("遞補狀態")
        elif "狀態" in headers:
            status_index = headers.index("狀態")
        else:
            continue

        for row in rows[1:]:
            cells = row.find_all(["th", "td"])
            values = [
                clean_text(cell.get_text(strip=True))
                for cell in cells
            ]

            if len(values) <= max(rank_index, status_index):
                continue

            rank_number = extract_number_from_rank(values[rank_index])
            status = values[status_index]

            if rank_number is None:
                continue

            records.append(
                {
                    "抓取日期": date.today().strftime("%Y-%m-%d"),
                    "社會住宅": project_name,
                    "遞補類型": queue_type,
                    "房型": room_type,
                    "戶別": household_type,
                    "候補序號": rank_number,
                    "遞補狀態": status,
                }
            )

    return pd.DataFrame(records, columns=RECORD_COLUMNS)


def calculate_stats(
    records_df: pd.DataFrame,
    project_name: str,
    queue_type: str,
    room_type: str,
    household_type: str,
) -> dict:
    """由個別名冊計算該案場、房型、戶別的統計。"""
    base_record = {
        "抓取日期": date.today().strftime("%Y-%m-%d"),
        "社會住宅": project_name,
        "遞補類型": queue_type,
        "房型": room_type,
        "戶別": household_type,
    }

    if records_df.empty:
        return {
            **base_record,
            "已遞補人數": 0,
            "已放棄人數": 0,
            "待遞補人數": 0,
            "名冊總人數": 0,
            "實際放棄率": None,
        }

    status_counts = records_df["遞補狀態"].value_counts()

    completed_count = int(status_counts.get("已遞補", 0))
    abandoned_count = int(status_counts.get("已放棄", 0))
    waiting_count = int(status_counts.get("待遞補", 0))

    processed_count = completed_count + abandoned_count

    if processed_count > 0:
        abandon_rate = abandoned_count / processed_count
    else:
        abandon_rate = None

    return {
        **base_record,
        "已遞補人數": completed_count,
        "已放棄人數": abandoned_count,
        "待遞補人數": waiting_count,
        "名冊總人數": len(records_df),
        "實際放棄率": abandon_rate,
    }


def normalize_key_columns(df: pd.DataFrame) -> pd.DataFrame:
    """統一主鍵欄位格式，避免前後空白造成比對失敗。"""
    result = df.copy()

    for column in KEY_COLUMNS:
        if column in result.columns:
            result[column] = (
                result[column]
                .astype("string")
                .str.strip()
            )

    return result


def get_key_series(df: pd.DataFrame) -> pd.Series:
    """將每列主鍵轉成 tuple，供 isin 比對。"""
    return df[KEY_COLUMNS].apply(
        lambda row: tuple(row.tolist()),
        axis=1,
    )


def load_latest_historical_stats() -> pd.DataFrame:
    """從歷史檔取得每個名冊最後一次實際抓取結果。"""
    if not STATS_HISTORY_FILE.exists():
        return pd.DataFrame(columns=STATS_COLUMNS)

    history_df = pd.read_csv(
        STATS_HISTORY_FILE,
        encoding="utf-8-sig",
    )

    required_columns = ["抓取日期"] + KEY_COLUMNS + ["待遞補人數"]
    missing_columns = [
        column
        for column in required_columns
        if column not in history_df.columns
    ]

    if missing_columns:
        print(
            "警告：detail_queue_stats_history.csv 缺少欄位，"
            "無法用於復原前置名冊："
            + ", ".join(missing_columns)
        )
        return pd.DataFrame(columns=STATS_COLUMNS)

    history_df = normalize_key_columns(history_df)

    history_df["抓取日期"] = pd.to_datetime(
        history_df["抓取日期"],
        errors="coerce",
    )

    history_df["待遞補人數"] = pd.to_numeric(
        history_df["待遞補人數"],
        errors="coerce",
    ).fillna(0)

    history_df = history_df.dropna(
        subset=["抓取日期"] + KEY_COLUMNS
    )

    if history_df.empty:
        return pd.DataFrame(columns=history_df.columns)

    latest_rows = (
        history_df
        .sort_values("抓取日期")
        .drop_duplicates(
            subset=KEY_COLUMNS,
            keep="last",
        )
        .copy()
    )

    latest_rows["抓取日期"] = latest_rows[
        "抓取日期"
    ].dt.strftime("%Y-%m-%d")

    return latest_rows


def preserve_unfinished_missing_queues(
    current_stats_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    保留本日已從 project_links.csv 消失、但最後一次紀錄仍有待遞補者的名冊。

    用途：
    當「新案場招租」連結從官方網站消失，而「隨到隨辦」名冊開始出現時，
    舊名冊仍可能是後續名冊的前置等待量。若直接覆寫目前統計檔，
    query_estimator.py 就會錯把前置名冊等待人數算成 0。

    注意：
    1. 保留列沿用最後一次實際抓取日期，不偽裝為今日資料。
    2. history 檔仍只追加本日真正抓到的資料。
    3. 最後一次待遞補人數為 0 的名冊不保留。
    """
    current_stats_df = normalize_key_columns(current_stats_df)

    sources = []

    # 優先讀取上一版目前統計檔。
    if STATS_OUTPUT_FILE.exists():
        previous_stats_df = pd.read_csv(
            STATS_OUTPUT_FILE,
            encoding="utf-8-sig",
        )

        if all(
            column in previous_stats_df.columns
            for column in KEY_COLUMNS + ["待遞補人數"]
        ):
            sources.append(normalize_key_columns(previous_stats_df))
        else:
            print(
                "警告：舊 detail_queue_stats.csv 欄位不完整，"
                "略過舊目前統計檔。"
            )

    # 再用歷史檔補救已經在舊目前統計檔中消失的名冊。
    latest_historical_df = load_latest_historical_stats()

    if not latest_historical_df.empty:
        sources.append(latest_historical_df)

    if not sources:
        return current_stats_df

    fallback_df = pd.concat(
        sources,
        ignore_index=True,
        sort=False,
    )

    fallback_df = normalize_key_columns(fallback_df)

    fallback_df["待遞補人數"] = pd.to_numeric(
        fallback_df["待遞補人數"],
        errors="coerce",
    ).fillna(0)

    # 同一主鍵可能同時出現在舊 stats 與 history。
    # 日期較新者優先。
    fallback_df["_抓取日期排序"] = pd.to_datetime(
        fallback_df.get("抓取日期"),
        errors="coerce",
    )

    fallback_df = (
        fallback_df
        .sort_values("_抓取日期排序")
        .drop_duplicates(
            subset=KEY_COLUMNS,
            keep="last",
        )
        .drop(columns=["_抓取日期排序"])
    )

    current_keys = set(
        get_key_series(current_stats_df).tolist()
    )

    carry_forward_df = fallback_df[
        (fallback_df["待遞補人數"] > 0)
        & ~get_key_series(fallback_df).isin(current_keys)
    ].copy()

    if carry_forward_df.empty:
        return current_stats_df

    print("以下名冊今日連結已消失，但最後紀錄仍有待遞補者，將保留於目前統計：")

    for _, row in carry_forward_df.iterrows():
        print(
            "  - "
            f"{row.get('社會住宅')} / "
            f"{row.get('遞補類型')} / "
            f"{row.get('房型')} / "
            f"{row.get('戶別')}："
            f"待遞補 {int(row.get('待遞補人數', 0))} 人，"
            f"最後抓取日 {row.get('抓取日期')}"
        )

    combined_df = pd.concat(
        [current_stats_df, carry_forward_df],
        ignore_index=True,
        sort=False,
    )

    # 今日實際抓到的資料放在前面，因此同鍵時保留今日資料。
    combined_df = combined_df.drop_duplicates(
        subset=KEY_COLUMNS,
        keep="first",
    )

    # 確保欄位順序穩定；若舊資料含額外欄位，放在標準欄位後面。
    ordered_columns = [
        column
        for column in STATS_COLUMNS
        if column in combined_df.columns
    ]
    extra_columns = [
        column
        for column in combined_df.columns
        if column not in ordered_columns
    ]

    combined_df = combined_df[
        ordered_columns + extra_columns
    ]

    return combined_df.sort_values(
        KEY_COLUMNS,
        kind="stable",
    ).reset_index(drop=True)


def save_stats_history(
    actual_scraped_stats_df: pd.DataFrame,
) -> None:
    """
    把本次真正爬到的統計資料追加到歷史檔。

    不把 carry-forward 的舊名冊重複寫成今日資料，
    以免扭曲最近一個月／三個月／六個月的推進速度。
    """
    if actual_scraped_stats_df.empty:
        print("本次沒有實際抓到統計資料，不更新歷史統計檔。")
        return

    actual_scraped_stats_df = normalize_key_columns(
        actual_scraped_stats_df
    )

    if STATS_HISTORY_FILE.exists():
        old_history_df = pd.read_csv(
            STATS_HISTORY_FILE,
            encoding="utf-8-sig",
        )

        if "遞補類型" not in old_history_df.columns:
            raise ValueError(
                "偵測到舊版 detail_queue_stats_history.csv "
                "缺少「遞補類型」。"
                "請先把舊檔移走或改名，再重新執行爬蟲。"
            )

        old_history_df = normalize_key_columns(old_history_df)

        history_df = pd.concat(
            [old_history_df, actual_scraped_stats_df],
            ignore_index=True,
            sort=False,
        )
    else:
        history_df = actual_scraped_stats_df.copy()

    history_df = history_df.drop_duplicates(
        subset=["抓取日期"] + KEY_COLUMNS,
        keep="last",
    )

    history_df = history_df.sort_values(
        KEY_COLUMNS + ["抓取日期"],
        kind="stable",
    )

    history_df.to_csv(
        STATS_HISTORY_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    print(
        "已更新歷史統計資料：",
        STATS_HISTORY_FILE.resolve(),
    )


def scrape_all_detail_lists():
    """抓取所有案場的個別名冊與統計資料。"""
    project_links_df = load_project_links()

    all_records = []
    all_stats = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()

        for _, project in project_links_df.iterrows():
            project_name = str(project["社會住宅"]).strip()
            queue_type = str(project["遞補類型"]).strip()
            detail_url = str(project["名冊網址"]).strip()

            print(
                "正在處理案場：",
                project_name,
                "/",
                queue_type,
            )

            try:
                page.goto(
                    detail_url,
                    wait_until="domcontentloaded",
                    timeout=60_000,
                )
                page.wait_for_timeout(3000)
            except Exception as error:
                print(
                    "開啟名冊頁面失敗，跳過：",
                    project_name,
                    "/",
                    queue_type,
                    "/",
                    error,
                )
                print("-" * 60)
                continue

            has_room_buttons = wait_for_room_buttons(page)

            if not has_room_buttons:
                print(
                    "等不到房型按鈕，跳過案場：",
                    project_name,
                    "/",
                    queue_type,
                )
                print("-" * 60)
                continue

            available_room_types = get_available_room_types(page)

            if not available_room_types:
                print(
                    "找不到任何房型按鈕，跳過案場：",
                    project_name,
                    "/",
                    queue_type,
                )
                print("-" * 60)
                continue

            for room_type in available_room_types:
                print("  房型：", room_type)

                if not click_filter(page, room_type):
                    continue

                for household_type in HOUSEHOLD_TYPES:
                    print("    戶別：", household_type)

                    if not click_filter(page, household_type):
                        continue

                    records_df = parse_detail_table(
                        page=page,
                        project_name=project_name,
                        queue_type=queue_type,
                        room_type=room_type,
                        household_type=household_type,
                    )

                    stats = calculate_stats(
                        records_df=records_df,
                        project_name=project_name,
                        queue_type=queue_type,
                        room_type=room_type,
                        household_type=household_type,
                    )

                    all_records.append(records_df)
                    all_stats.append(stats)

                    print(
                        "      完成：",
                        "總人數",
                        stats["名冊總人數"],
                        "已遞補",
                        stats["已遞補人數"],
                        "已放棄",
                        stats["已放棄人數"],
                        "待遞補",
                        stats["待遞補人數"],
                    )

            print("-" * 60)

        browser.close()

    if all_records:
        records_result_df = pd.concat(
            all_records,
            ignore_index=True,
        )
    else:
        records_result_df = pd.DataFrame(
            columns=RECORD_COLUMNS
        )

    actual_stats_df = pd.DataFrame(
        all_stats,
        columns=STATS_COLUMNS,
    )

    # 必須在覆寫 detail_queue_stats.csv 之前讀取舊檔。
    output_stats_df = preserve_unfinished_missing_queues(
        actual_stats_df
    )

    records_result_df.to_csv(
        RECORDS_OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    output_stats_df.to_csv(
        STATS_OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    print(
        "已儲存個別名冊資料：",
        RECORDS_OUTPUT_FILE.resolve(),
    )
    print(
        "已儲存目前統計資料：",
        STATS_OUTPUT_FILE.resolve(),
    )

    # 只將本日真正抓到的資料寫入 history。
    save_stats_history(actual_stats_df)

    return records_result_df, output_stats_df


if __name__ == "__main__":
    scrape_all_detail_lists()
