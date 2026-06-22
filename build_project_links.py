from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from pathlib import Path
import re
import pandas as pd

BASE_DIR = Path(__file__).parent

HOME_URL = "https://17zu.taichung.gov.tw/Portal/index"

OUTPUT_FILE = BASE_DIR / "project_links.csv"


def clean_text(text):
    return re.sub(r"[\s\u3000]+", "", text)


def go_to_summary_page(page):
    page.goto(HOME_URL)
    page.wait_for_timeout(3000)

    page.get_by_text("社宅遞補情形").click()
    page.wait_for_timeout(5000)


def get_project_names(page):
    html = page.content()
    soup = BeautifulSoup(html, "html.parser")

    tables = soup.find_all("table")

    if len(tables) == 0:
        raise ValueError("找不到總表")

    table = tables[0]
    rows = table.find_all("tr")

    project_names = []

    for row in rows[1:]:
        cells = row.find_all(["th", "td"])
        values = [clean_text(cell.get_text(strip=True)) for cell in cells]

        # 有五欄的列通常是每個案場的第一列
        # 例如：社會住宅 / 遞補類型 / 房型 / 一般戶 / 關懷戶
        if len(values) == 5:
            project_name = values[0]

            if project_name:
                project_names.append(project_name)

    return project_names


def build_project_links():
    records = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        go_to_summary_page(page)

        project_names = get_project_names(page)

        print("找到案場數量：", len(project_names))
        print(project_names)

        for i, project_name in enumerate(project_names):
            print("正在處理：", project_name)

            # 每次都重新回到總表，避免上一頁狀態干擾
            go_to_summary_page(page)

            links = page.get_by_text("遞補清單", exact=False)

            print("目前頁面遞補清單連結數量：", links.count())

            links.nth(i).click()
            page.wait_for_timeout(1000)

            page.get_by_role("button", name="是").click()
            page.wait_for_timeout(3000)

            detail_url = page.url

            record = {
                "社會住宅": project_name,
                "名冊網址": detail_url,
            }

            records.append(record)

            print("取得網址：", detail_url)
            print("-" * 50)

        browser.close()

    df = pd.DataFrame(records)

    df.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig"
    )

    print("已儲存：", OUTPUT_FILE.resolve())

    return df


if __name__ == "__main__":
    build_project_links()