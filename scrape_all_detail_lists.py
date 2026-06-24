from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from pathlib import Path
from datetime import date
import re
import pandas as pd

from constants import KEY_COLUMNS

BASE_DIR = Path(__file__).parent

PROJECT_LINKS_FILE = BASE_DIR / "project_links.csv"

RECORDS_OUTPUT_FILE = BASE_DIR / "detail_queue_records.csv"
STATS_OUTPUT_FILE = BASE_DIR / "detail_queue_stats.csv"
STATS_HISTORY_FILE = BASE_DIR / "detail_queue_stats_history.csv"

ROOM_TYPES = ["一房型", "二房型", "三房型"]
HOUSEHOLD_TYPES = ["一般戶", "關懷戶"]

def wait_for_room_buttons(page):
    for _ in range(15):
        for room_type in ROOM_TYPES:
            if page.get_by_role("button", name=room_type).count() > 0:
                return True

        page.wait_for_timeout(1000)

    return False

def get_available_room_types(page):
    available_room_types = []

    for room_type in ROOM_TYPES:
        if page.get_by_role("button", name=room_type).count() > 0:
            available_room_types.append(room_type)

    return available_room_types


def clean_text(text):
    return re.sub(r"[\s\u3000]+", "", str(text))


def extract_number_from_rank(rank_text):
    match = re.search(r"\d+", str(rank_text))

    if match:
        return int(match.group(0))
    else:
        return None


def load_project_links():
    if not PROJECT_LINKS_FILE.exists():
        raise FileNotFoundError("找不到 project_links.csv，請先執行 build_project_links.py")

    df = pd.read_csv(PROJECT_LINKS_FILE, encoding="utf-8-sig")

    required_columns = ["社會住宅", "遞補類型", "名冊網址"]
    missing_columns = [col for col in required_columns if col not in df.columns]

    if missing_columns:
        raise ValueError(
            "project_links.csv 缺少必要欄位："
            + ", ".join(missing_columns)
            + "。請先用新版 build_project_links.py 重新產生 project_links.csv。"
        )

    return df


def click_filter(page, text):
    button = page.get_by_role("button", name=text)

    if button.count() == 0:
        print(f"找不到按鈕：{text}")
        return False

    button.click(force=True)

    # 官方頁面是前端動態切換，太快抓會抓到上一個房型或戶別。
    page.wait_for_timeout(2500)

    return True


def get_visible_tables(page):
    """
    只解析目前畫面可見的 table，避免抓到 DOM 中隱藏的舊表格。
    """
    try:
        visible_tables_html = page.locator("table:visible").evaluate_all(
            "(tables) => tables.map(t => t.outerHTML)"
        )
    except Exception:
        # 若 :visible 在某些環境失敗，退回整頁解析，但會印出警告。
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


def parse_detail_table(page, project_name, queue_type, room_type, household_type):
    tables = get_visible_tables(page)

    columns = [
        "抓取日期",
        "社會住宅",
        "遞補類型",
        "房型",
        "戶別",
        "候補序號",
        "遞補狀態",
    ]

    if len(tables) == 0:
        return pd.DataFrame(columns=columns)

    records = []

    for table in tables:
        rows = table.find_all("tr")

        if len(rows) < 2:
            continue

        header_cells = rows[0].find_all(["th", "td"])
        headers = [clean_text(cell.get_text(strip=True)) for cell in header_cells]

        # 目前名冊欄位通常是：
        # 序號 / 收件編號 / 姓名 / 身分證字號 / 關懷戶 / 遞補狀態
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
            values = [clean_text(cell.get_text(strip=True)) for cell in cells]

            if len(values) <= max(rank_index, status_index):
                continue

            rank_number = extract_number_from_rank(values[rank_index])
            status = values[status_index]

            if rank_number is None:
                continue

            record = {
                "抓取日期": date.today().strftime("%Y-%m-%d"),
                "社會住宅": project_name,
                "遞補類型": queue_type,
                "房型": room_type,
                "戶別": household_type,
                "候補序號": rank_number,
                "遞補狀態": status,
            }

            records.append(record)

    return pd.DataFrame(records, columns=columns)


def calculate_stats(records_df, project_name, queue_type, room_type, household_type):
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

    completed_count = status_counts.get("已遞補", 0)
    abandoned_count = status_counts.get("已放棄", 0)
    waiting_count = status_counts.get("待遞補", 0)

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


def save_stats_history(stats_result_df):
    """
    把本次爬到的統計資料，追加到 detail_queue_stats_history.csv。
    如果同一天、同案場、同遞補類型、同房型、同戶別已經存在，就保留最後一次。
    """
    if STATS_HISTORY_FILE.exists():
        old_history_df = pd.read_csv(STATS_HISTORY_FILE, encoding="utf-8-sig")

        # 舊版 history 沒有遞補類型，不能和新版資料混用。
        if "遞補類型" not in old_history_df.columns:
            raise ValueError(
                "偵測到舊版 detail_queue_stats_history.csv 缺少「遞補類型」。"
                "請先把舊檔移走或改名，再重新執行爬蟲。"
            )

        history_df = pd.concat(
            [old_history_df, stats_result_df],
            ignore_index=True
        )
    else:
        history_df = stats_result_df.copy()

    history_df = history_df.drop_duplicates(
        subset=["抓取日期"] + KEY_COLUMNS,
        keep="last"
    )

    history_df = history_df.sort_values(
        KEY_COLUMNS + ["抓取日期"]
    )

    history_df.to_csv(
        STATS_HISTORY_FILE,
        index=False,
        encoding="utf-8-sig"
    )

    print("已更新歷史統計資料：", STATS_HISTORY_FILE.resolve())


def scrape_all_detail_lists():
    project_links_df = load_project_links()

    all_records = []
    all_stats = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        for _, project in project_links_df.iterrows():
            project_name = project["社會住宅"]
            queue_type = project["遞補類型"]
            detail_url = project["名冊網址"]

            print("正在處理案場：", project_name, "/", queue_type)

            page.goto(detail_url)
            page.wait_for_timeout(3000)

            has_room_buttons = wait_for_room_buttons(page)

            if not has_room_buttons:
                print("等不到房型按鈕，跳過案場：", project_name, "/", queue_type)
                print("-" * 60)
                continue

            available_room_types = get_available_room_types(page)

            if not available_room_types:

                print("找不到任何房型按鈕，跳過案場：", project_name, "/", queue_type)

                print("-" * 60)

                continue

            for room_type in available_room_types:
                
                print("  房型：", room_type)

                room_clicked = click_filter(page, room_type)

                if not room_clicked:
                    continue

                for household_type in HOUSEHOLD_TYPES:
                    print("    戶別：", household_type)

                    household_clicked = click_filter(page, household_type)

                    if not household_clicked:
                        continue

                    records_df = parse_detail_table(
                        page,
                        project_name,
                        queue_type,
                        room_type,
                        household_type
                    )

                    stats = calculate_stats(
                        records_df,
                        project_name,
                        queue_type,
                        room_type,
                        household_type
                    )

                    all_records.append(records_df)
                    all_stats.append(stats)

                    print(
                        "    完成：",
                        "總人數", stats["名冊總人數"],
                        "已遞補", stats["已遞補人數"],
                        "已放棄", stats["已放棄人數"],
                        "待遞補", stats["待遞補人數"],
                    )

            print("-" * 60)

        browser.close()

    if len(all_records) > 0:
        records_result_df = pd.concat(all_records, ignore_index=True)
    else:
        records_result_df = pd.DataFrame(columns=[
            "抓取日期",
            "社會住宅",
            "遞補類型",
            "房型",
            "戶別",
            "候補序號",
            "遞補狀態",
        ])

    stats_result_df = pd.DataFrame(all_stats)

    records_result_df.to_csv(
        RECORDS_OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig"
    )

    stats_result_df.to_csv(
        STATS_OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig"
    )

    print("已儲存個別名冊資料：", RECORDS_OUTPUT_FILE.resolve())
    print("已儲存統計資料：", STATS_OUTPUT_FILE.resolve())

    save_stats_history(stats_result_df)

    return records_result_df, stats_result_df


if __name__ == "__main__":
    scrape_all_detail_lists()
