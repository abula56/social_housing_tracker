from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from pathlib import Path
import re
import pandas as pd
from constants import PROJECT_LINK_COLUMNS

BASE_DIR = Path(__file__).parent

HOME_URL = "https://17zu.taichung.gov.tw/Portal/index"
OUTPUT_FILE = BASE_DIR / "project_links.csv"

QUEUE_TYPES = ["新案場招租", "隨到隨辦", "遞補招租"]
ROOM_TYPES = ["一房型", "二房型", "三房型"]
HOUSEHOLD_TYPES = ["一般戶", "關懷戶"]

# 資料品質安全門檻：抓取異常時絕不覆蓋上一版正常資料。
MIN_LINK_COUNT = 5
MIN_PROJECT_COUNT = 3
MIN_RETENTION_RATIO = 0.70


def clean_text(text):
    return re.sub(r"[\s\u3000]+", "", str(text))


def go_to_summary_page(page):
    page.goto(HOME_URL)
    page.wait_for_timeout(3000)

    page.get_by_text("社宅遞補情形").click()
    page.wait_for_timeout(5000)


def detect_queue_type(values):
    for i, value in enumerate(values):
        for queue_type in QUEUE_TYPES:
            if queue_type in value:
                return queue_type, i

    return None, None


def looks_like_project_name(value):
    """
    判斷某個儲存格文字是否可能是案場名稱。

    重點：
    只能從「遞補類型」前面的儲存格判斷案場名稱。
    不能從「房型」「下一位遞補」「遞補清單」等欄位抓案場名。
    """
    value = clean_text(value)

    if not value:
        return False

    if value in QUEUE_TYPES:
        return False

    if value in ROOM_TYPES:
        return False

    if value in HOUSEHOLD_TYPES:
        return False

    bad_keywords = [
        "遞補清單",
        "下一位遞補",
        "申請編號",
        "號(",
        "一般戶",
        "關懷戶",
    ]

    for keyword in bad_keywords:
        if keyword in value:
            return False

    header_words = [
        "社會住宅",
        "遞補類型",
        "房型",
        "一般戶",
        "關懷戶",
    ]

    if value in header_words:
        return False

    return True


def get_project_link_records(page):
    """
    從「社宅遞補情形」總表建立連結清單。

    表格常見結構：
    第一列：西屯國安一期 / 新案場招租 / ...
    第二列：隨到隨辦 / 一房型 / 下一位遞補... / 遞補清單

    第二列不會重複案場名稱，所以必須沿用上一個 current_project_name。
    因此只能從「遞補類型」前面的欄位更新案場名稱。
    """
    html = page.content()
    soup = BeautifulSoup(html, "html.parser")

    tables = soup.find_all("table")

    if len(tables) == 0:
        raise ValueError("找不到總表")

    table = tables[0]
    rows = table.find_all("tr")

    records = []
    current_project_name = None
    link_index = 0

    for row in rows[1:]:
        cells = row.find_all(["th", "td"])
        values = [clean_text(cell.get_text(strip=True)) for cell in cells]
        values = [value for value in values if value]

        if not values:
            continue

        row_text = "".join(values)

        if "遞補清單" not in row_text:
            continue

        queue_type, queue_type_index = detect_queue_type(values)

        if queue_type is None:
            print("警告：找不到遞補類型，略過列：", values)
            link_index += 1
            continue

        # 只允許從「遞補類型」前面的欄位判斷案場名稱。
        # 如果 queue_type_index 是 0，表示本列沒有案場名稱，沿用上一個。
        possible_project_values = [
            value for value in values[:queue_type_index]
            if looks_like_project_name(value)
        ]

        if possible_project_values:
            current_project_name = possible_project_values[0]

        if not current_project_name:
            print("警告：找不到案場名稱，略過列：", values)
            link_index += 1
            continue

        records.append({
            "社會住宅": current_project_name,
            "遞補類型": queue_type,
            "link_index": link_index,
        })

        link_index += 1

    return records



def validate_project_links(df: pd.DataFrame) -> None:
    """驗證本次名冊連結資料，異常時阻止覆蓋既有檔案。"""
    missing_columns = [
        column
        for column in PROJECT_LINK_COLUMNS
        if column not in df.columns
    ]

    if missing_columns:
        raise RuntimeError(
            "本次 project_links 資料缺少必要欄位："
            + ", ".join(missing_columns)
        )

    if df.empty:
        raise RuntimeError(
            "本次沒有取得任何名冊連結。"
            "為避免空資料覆蓋既有 project_links.csv，已中止更新。"
        )

    link_count = len(df)
    project_count = df["社會住宅"].nunique()

    if link_count < MIN_LINK_COUNT:
        raise RuntimeError(
            f"本次只取得 {link_count} 筆名冊連結，"
            f"低於安全門檻 {MIN_LINK_COUNT} 筆。"
            "中止更新並保留既有資料。"
        )

    if project_count < MIN_PROJECT_COUNT:
        raise RuntimeError(
            f"本次只取得 {project_count} 個案場，"
            f"低於安全門檻 {MIN_PROJECT_COUNT} 個。"
            "中止更新並保留既有資料。"
        )

    normalized_urls = df["名冊網址"].astype("string").str.strip()

    invalid_url_mask = (
        normalized_urls.isna()
        | ~normalized_urls.str.startswith(
            ("http://", "https://"),
            na=False,
        )
    )

    if invalid_url_mask.any():
        invalid_rows = df.loc[
            invalid_url_mask,
            ["社會住宅", "遞補類型", "名冊網址"],
        ]

        raise RuntimeError(
            "發現無效名冊網址，停止更新：\n"
            + invalid_rows.to_string(index=False)
        )

    home_url_mask = normalized_urls.str.rstrip("/") == HOME_URL.rstrip("/")

    if home_url_mask.any():
        home_rows = df.loc[
            home_url_mask,
            ["社會住宅", "遞補類型", "名冊網址"],
        ]

        raise RuntimeError(
            "部分名冊網址仍停留在首頁，表示點擊或導向失敗：\n"
            + home_rows.to_string(index=False)
        )

    duplicate_mask = df.duplicated(
        subset=["社會住宅", "遞補類型"],
        keep=False,
    )

    if duplicate_mask.any():
        duplicate_rows = df.loc[
            duplicate_mask,
            ["社會住宅", "遞補類型", "名冊網址"],
        ].sort_values(["社會住宅", "遞補類型"])

        raise RuntimeError(
            "發現重複案場／遞補類型，停止更新：\n"
            + duplicate_rows.to_string(index=False)
        )

    if OUTPUT_FILE.exists():
        previous_df = pd.read_csv(
            OUTPUT_FILE,
            encoding="utf-8-sig",
        )
        previous_count = len(previous_df)

        if previous_count > 0:
            retention_ratio = link_count / previous_count

            if retention_ratio < MIN_RETENTION_RATIO:
                raise RuntimeError(
                    f"本次只有 {link_count} 筆連結，"
                    f"舊資料有 {previous_count} 筆，"
                    f"僅保留 {retention_ratio:.1%}。"
                    "下降超過 30%，疑似官方頁面或導向異常；"
                    "中止更新並保留既有資料。"
                )


def atomic_write_csv(df: pd.DataFrame, output_file: Path) -> None:
    """先完整寫入暫存檔，再原子替換正式 CSV。"""
    temp_file = output_file.with_suffix(output_file.suffix + ".tmp")

    try:
        df.to_csv(
            temp_file,
            index=False,
            encoding="utf-8-sig",
        )
        temp_file.replace(output_file)
    finally:
        if temp_file.exists():
            temp_file.unlink()


def build_project_links():
    records = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        go_to_summary_page(page)

        summary_records = get_project_link_records(page)

        print("找到遞補清單連結數量：", len(summary_records))
        print(pd.DataFrame(summary_records))

        for record in summary_records:
            print(
                "正在處理：",
                record["社會住宅"],
                record["遞補類型"],
                "link_index=",
                record["link_index"],
            )

            # 每次都重新回到總表，避免上一頁狀態干擾
            go_to_summary_page(page)

            links = page.get_by_text("遞補清單", exact=False)

            print("目前頁面遞補清單連結數量：", links.count())

            if record["link_index"] >= links.count():
                print("警告：link_index 超出範圍，略過：", record)
                print("-" * 50)
                continue

            links.nth(record["link_index"]).click()
            page.wait_for_timeout(1000)

            # 官方頁面有確認視窗時按「是」；如果沒有就略過。
            confirm_button = page.get_by_role("button", name="是")

            if confirm_button.count() > 0:
                confirm_button.click()
                page.wait_for_timeout(3000)
            else:
                page.wait_for_timeout(3000)

            detail_url = page.url

            output_record = {
                "社會住宅": record["社會住宅"],
                "遞補類型": record["遞補類型"],
                "名冊網址": detail_url,
            }

            records.append(output_record)

            print("取得網址：", detail_url)
            print("-" * 50)

        browser.close()

    df = pd.DataFrame(
        records,
        columns=PROJECT_LINK_COLUMNS,
    )

    validate_project_links(df)
    atomic_write_csv(df, OUTPUT_FILE)

    print("已儲存：", OUTPUT_FILE.resolve())
    print(df)

    return df


if __name__ == "__main__":
    build_project_links()
