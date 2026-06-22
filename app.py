from pathlib import Path
import pandas as pd
import streamlit as st

BASE_DIR = Path(__file__).parent

PROJECT_LINKS_FILE = BASE_DIR / "project_links.csv"
MY_APPLICATIONS_FILE = BASE_DIR / "my_applications.csv"
ESTIMATES_FILE = BASE_DIR / "my_application_estimates.csv"
METADATA_FILE = BASE_DIR / "project_metadata.csv"
STATUS_FILE = BASE_DIR / "detail_queue_stats.csv"
PROGRESS_FILE = BASE_DIR / "queue_progress_analysis.csv"


st.set_page_config(
    page_title="社宅候補追蹤工具",
    layout="wide"
)

st.title("社宅候補追蹤工具")


def load_project_links():
    if not PROJECT_LINKS_FILE.exists():
        st.error("找不到 project_links.csv，請先執行 build_project_links.py")
        return pd.DataFrame(columns=["社會住宅", "名冊網址"])

    return pd.read_csv(PROJECT_LINKS_FILE)


def load_my_applications():
    if MY_APPLICATIONS_FILE.exists():
        return pd.read_csv(MY_APPLICATIONS_FILE)

    return pd.DataFrame(columns=[
        "社會住宅",
        "房型",
        "戶別",
        "我的候補序號",
        "備註",
    ])


def save_my_applications(df):
    df.to_csv(
        MY_APPLICATIONS_FILE,
        index=False,
        encoding="utf-8-sig"
    )


def load_estimates():
    if ESTIMATES_FILE.exists():
        return pd.read_csv(ESTIMATES_FILE)

    return pd.DataFrame()


def load_metadata():
    if METADATA_FILE.exists():
        return pd.read_csv(METADATA_FILE)

    return pd.DataFrame()


def load_status():
    if STATUS_FILE.exists():
        return pd.read_csv(STATUS_FILE)

    return pd.DataFrame()

def load_progress():
    if PROGRESS_FILE.exists():
        return pd.read_csv(PROGRESS_FILE)
    
    return pd.DataFrame()

project_links_df = load_project_links()
my_df = load_my_applications()
metadata_df = load_metadata()
estimates_df = load_estimates()
status_df = load_status()
progress_df = load_progress()

if project_links_df.empty:
    st.stop()

project_options = project_links_df["社會住宅"].dropna().tolist()


# =========================
# 新增候補資料
# =========================

st.header("我的候補設定")

with st.expander("新增候補資料", expanded=False):
    with st.form("add_applications_form"):
        selected_projects = st.multiselect(
            "選擇社會住宅案場，可多選",
            project_options
        )

        st.write("請為每個案場分別設定房型、戶別與候補序號：")

        input_records = []

        for project_name in selected_projects:
            st.markdown(f"### {project_name}")

            room_type = st.selectbox(
                f"{project_name}：房型",
                ["一房型", "二房型", "三房型"],
                index=2,
                key=f"room_type_{project_name}"
            )

            household_type = st.selectbox(
                f"{project_name}：戶別",
                ["一般戶", "關懷戶"],
                index=0,
                key=f"household_type_{project_name}"
            )

            my_rank = st.number_input(
                f"{project_name}：我的候補序號",
                min_value=1,
                step=1,
                key=f"rank_{project_name}"
            )

            note = st.text_input(
                f"{project_name}：備註",
                key=f"note_{project_name}"
            )

            input_records.append({
                "社會住宅": project_name,
                "房型": room_type,
                "戶別": household_type,
                "我的候補序號": int(my_rank),
                "備註": note,
            })

        submitted = st.form_submit_button("新增候補資料")

        if submitted:
            if len(input_records) == 0:
                st.warning("請至少選擇一個社會住宅案場")
            else:
                new_df = pd.DataFrame(input_records)

                my_df = pd.concat([my_df, new_df], ignore_index=True)

                my_df = my_df.drop_duplicates(
                    subset=["社會住宅", "房型", "戶別"],
                    keep="last"
                )

                save_my_applications(my_df)

                st.success("已新增候補資料")
                st.rerun()


# =========================
# 目前候補清單
# =========================

st.subheader("目前候補清單")

my_df = load_my_applications()

if my_df.empty:
    st.info("目前尚未新增任何候補資料")
else:
    display_my_df = my_df.copy()

    if not metadata_df.empty and "社會住宅" in metadata_df.columns:
        metadata_columns = [
            "社會住宅",
            "推估用日期",
            "日期精度",
            "資料等級",
            "資料依據"
            "來源網址"
        ]

        available_metadata_columns = [
            col for col in metadata_columns
            if col in metadata_df.columns
        ]

        display_my_df = display_my_df.merge(
            metadata_df[available_metadata_columns],
            on="社會住宅",
            how="left"
        )

        display_my_df = display_my_df.rename(
            columns={
                "推估用日期": "營運推估用日期"
            }
        )

    st.dataframe(display_my_df, width="stretch")



# =========================
# 刪除候補資料
# =========================

if not my_df.empty:
    st.subheader("刪除候補資料")

    delete_options = [
        f"{idx}｜{row['社會住宅']}｜{row['房型']}｜{row['戶別']}｜序號 {row['我的候補序號']}"
        for idx, row in my_df.iterrows()
    ]

    selected_delete_items = st.multiselect(
        "選擇要刪除的資料，可多選",
        delete_options
    )

    if st.button("刪除選取資料"):
        if len(selected_delete_items) == 0:
            st.warning("請至少選擇一筆要刪除的資料")
        else:
            delete_indexes = []

            for item in selected_delete_items:
                index_text = item.split("｜")[0]
                delete_indexes.append(int(index_text))

            my_df = my_df.drop(index=delete_indexes).reset_index(drop=True)

            save_my_applications(my_df)

            st.success("已刪除選取資料")
            st.rerun()


# =========================
# 我的遞補預估結果
# =========================

st.header("我的遞補預估結果")

estimates_df = load_estimates()

if estimates_df.empty:
    st.info("尚未找到 my_application_estimates.csv，請先執行 estimate_my_applicaitons.py")
else:
    st.dataframe(estimates_df, width="stretch")

    st.caption(
        "說明：營運以來速度是用營運開始日至今的平均推進速度估算；"
        "最近速度是用 queue_progress_analysis.csv 的最近4次平均推進人數估算。"
    )


# =========================
# 官方遞補統計
# =========================

st.header("目前官方遞補統計")

status_df = load_status()
progress_df = load_progress()

if status_df.empty:
    st.info("尚未找到 detail_queue_stats.csv，請先執行 scrape_all_detail_lists.py")
else:
    room_filter = st.selectbox(
        "篩選房型",
        ["全部", "一房型", "二房型", "三房型"],
        index=3
    )

    household_filter = st.selectbox(
        "篩選戶別",
        ["全部", "一般戶", "關懷戶"],
        index=1
    )

    display_status_df = status_df.copy()

    if room_filter != "全部":
        display_status_df = display_status_df[
            display_status_df["房型"] == room_filter
        ]

    if household_filter != "全部":
        display_status_df = display_status_df[
            display_status_df["戶別"] == household_filter
        ]

    if not progress_df.empty:
        latest_progress_df = progress_df.copy()

        latest_progress_df["抓取日期"] = pd.to_datetime(
            latest_progress_df["抓取日期"],
            errors="coerce"
        )

        latest_progress_df = latest_progress_df.sort_values(
            ["社會住宅", "房型", "戶別", "抓取日期"]
        )

        latest_progress_df = latest_progress_df.drop_duplicates(
            subset=["社會住宅", "房型", "戶別"],
            keep="last"
        )

        display_status_df = display_status_df.merge(
            latest_progress_df[
                [
                    "社會住宅",
                    "房型",
                    "戶別",
                    "最近4次平均推進人數",
                ]
            ],
            on=["社會住宅", "房型", "戶別"],
            how="left"
        )

        today = pd.Timestamp.today().normalize()

        display_status_df["最後號預估剩餘週數"] = display_status_df.apply(
            lambda row: (
                row["待遞補人數"] / row["最近4次平均推進人數"]
                if pd.notna(row["最近4次平均推進人數"])
                and row["最近4次平均推進人數"] > 0
                else None
            ),
            axis=1
        )

        display_status_df["最後號預估遞補完成日期"] = display_status_df[
            "最後號預估剩餘週數"
        ].apply(
            lambda weeks: (
                today + pd.to_timedelta(weeks, unit="W")
                if pd.notna(weeks)
                else None
            )
        )

        display_status_df["最後號預估遞補完成日期"] = display_status_df[
            "最後號預估遞補完成日期"
        ].apply(
            lambda value: value.strftime("%Y-%m-%d") if pd.notna(value) else None
        )
    else:
        display_status_df["最近4次平均推進人數"] = None
        display_status_df["最後號預估剩餘週數"] = None
        display_status_df["最後號預估遞補完成日期"] = None

    st.dataframe(display_status_df, width="stretch")

    st.caption(
        "說明：最後號預估是用目前待遞補人數 ÷ 最近4次平均推進人數估算，"
        "表示若照最近速度，該案場、房型、戶別目前名冊最後一位大約何時會被處理到。"
    )