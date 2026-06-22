from pathlib import Path

import pandas as pd
import streamlit as st


KEY_COLUMNS = ["社會住宅", "遞補類型", "房型", "戶別"]

RECORDS_FILE = Path("detail_queue_records.csv")
STATS_FILE = Path("detail_queue_stats.csv")
HISTORY_FILE = Path("detail_queue_stats_history.csv")


st.set_page_config(
    page_title="臺中社宅候補查詢工具",
    page_icon="🏠",
    layout="wide",
)


@st.cache_data
def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def find_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for col in candidates:
        if col in df.columns:
            return col
    return None


def filter_df(df: pd.DataFrame, filters: dict[str, str]) -> pd.DataFrame:
    result = df.copy()
    for col, value in filters.items():
        if col in result.columns and value:
            result = result[result[col].astype(str) == str(value)]
    return result


def sorted_options(df: pd.DataFrame, column: str) -> list[str]:
    if df.empty or column not in df.columns:
        return []

    values = df[column].dropna().astype(str).unique().tolist()

    if column == "房型":
        room_order = {
            "套房型": 0,
            "一房型": 1,
            "二房型": 2,
            "三房型": 3,
            "四房型": 4,
        }
        return sorted(values, key=lambda x: room_order.get(x, 999))

    if column == "遞補類型":
        queue_order = {
            "新案場招租": 0,
            "隨到隨辦": 1,
        }
        return sorted(values, key=lambda x: queue_order.get(x, 999))

    if column == "戶別":
        household_order = {
            "一般戶": 0,
            "優先戶": 1,
            "共居專案": 2,
            "原住民戶": 3,
            "身心障礙戶": 4,
        }
        return sorted(values, key=lambda x: household_order.get(x, 999))

    return sorted(values)


def get_waiting_count(row: pd.Series) -> int | None:
    for col in ["待遞補人數", "待補人數", "尚待遞補人數"]:
        if col in row.index and pd.notna(row[col]):
            try:
                return int(row[col])
            except Exception:
                return None
    return None


def get_processed_count(row: pd.Series) -> int | None:
    for col in ["已處理人數", "已遞補人數", "已處理"]:
        if col in row.index and pd.notna(row[col]):
            try:
                return int(row[col])
            except Exception:
                return None
    return None


def estimate_same_roster_front_count(
    records_df: pd.DataFrame,
    stats_row: pd.Series | None,
    user_number: int,
) -> int | None:
    serial_col = find_column(records_df, ["序號", "候補序號", "抽籤序號", "遞補序號"])
    status_col = find_column(records_df, ["狀態", "遞補狀態", "候補狀態"])

    if serial_col and status_col and not records_df.empty:
        temp = records_df.copy()
        temp[serial_col] = pd.to_numeric(temp[serial_col], errors="coerce")
        front = temp[temp[serial_col] < user_number]

        pending_mask = front[status_col].astype(str).str.contains(
            "待|尚未|未遞補|候補",
            regex=True,
            na=False,
        )
        return int(pending_mask.sum())

    if stats_row is not None:
        processed = get_processed_count(stats_row)
        if processed is not None:
            return max(user_number - processed - 1, 0)

    return None


def estimate_previous_roster_waiting_count(
    stats_df: pd.DataFrame,
    project: str,
    queue_type: str,
    room_type: str,
    household_type: str,
) -> int:
    if queue_type != "隨到隨辦":
        return 0

    required = ["社會住宅", "遞補類型", "房型", "戶別"]
    if any(col not in stats_df.columns for col in required):
        return 0

    previous = stats_df[
        (stats_df["社會住宅"].astype(str) == str(project))
        & (stats_df["遞補類型"].astype(str) == "新案場招租")
        & (stats_df["房型"].astype(str) == str(room_type))
        & (stats_df["戶別"].astype(str) == str(household_type))
    ]

    if previous.empty:
        return 0

    total = 0
    for _, row in previous.iterrows():
        waiting = get_waiting_count(row)
        if waiting is not None:
            total += waiting

    return int(total)


records_df = load_csv(RECORDS_FILE)
stats_df = load_csv(STATS_FILE)
history_df = load_csv(HISTORY_FILE)

st.title("臺中社宅候補查詢工具")

st.warning(
    "本工具不是臺中市政府官方網站。結果僅依公開候補名冊推估，"
    "實際資格審查、通知、選屋與入住時間仍以官方公告與通知為準。"
)

st.caption("本頁不會保存使用者輸入的候補序號或個人資料。")

if stats_df.empty and records_df.empty:
    st.error(
        "目前找不到候補資料 CSV。請先執行 build_project_links.py、"
        "scrape_all_detail_lists.py、analyze_queue_progress.py。"
    )
    st.stop()

source_df = stats_df if not stats_df.empty else records_df

missing_key_columns = [col for col in KEY_COLUMNS if col not in source_df.columns]
if missing_key_columns:
    st.error(f"資料缺少必要欄位：{', '.join(missing_key_columns)}")
    st.stop()


tab_query, tab_stats, tab_about = st.tabs(["🏠 候補查詢", "📊 名冊概況", "ℹ️ 說明"])

with tab_query:
    st.subheader("輸入候補資訊")

    project = st.selectbox("社會住宅", sorted_options(source_df, "社會住宅"))

    df_project = filter_df(source_df, {"社會住宅": project})
    queue_type = st.selectbox("遞補類型", sorted_options(df_project, "遞補類型"))

    df_queue = filter_df(
        source_df,
        {
            "社會住宅": project,
            "遞補類型": queue_type,
        },
    )
    room_type = st.selectbox("房型", sorted_options(df_queue, "房型"))

    df_room = filter_df(
        source_df,
        {
            "社會住宅": project,
            "遞補類型": queue_type,
            "房型": room_type,
        },
    )
    household_type = st.selectbox("戶別", sorted_options(df_room, "戶別"))

    user_number = st.number_input(
        "我的候補序號",
        min_value=1,
        step=1,
        value=1,
    )

    if st.button("開始查詢", type="primary"):
        filters = {
            "社會住宅": project,
            "遞補類型": queue_type,
            "房型": room_type,
            "戶別": household_type,
        }

        matched_stats = filter_df(stats_df, filters) if not stats_df.empty else pd.DataFrame()
        matched_records = filter_df(records_df, filters) if not records_df.empty else pd.DataFrame()

        stats_row = None
        if not matched_stats.empty:
            stats_row = matched_stats.iloc[0]

        same_roster_front = estimate_same_roster_front_count(
            matched_records,
            stats_row,
            int(user_number),
        )

        previous_roster_waiting = estimate_previous_roster_waiting_count(
            stats_df,
            project,
            queue_type,
            room_type,
            household_type,
        )

        conservative_front = None
        if same_roster_front is not None:
            conservative_front = same_roster_front + previous_roster_waiting

        st.divider()
        st.subheader("查詢結果")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                "本名冊前方待遞補",
                "無法估算" if same_roster_front is None else f"{same_roster_front} 人",
            )

        with col2:
            st.metric(
                "前置名冊待遞補",
                f"{previous_roster_waiting} 人",
            )

        with col3:
            st.metric(
                "保守估計前方等待",
                "無法估算" if conservative_front is None else f"{conservative_front} 人",
            )

        if matched_stats.empty:
            st.info("目前沒有找到完全對應的統計資料。")
        else:
            st.markdown("### 對應名冊統計")
            st.dataframe(matched_stats, use_container_width=True)

        if not matched_records.empty:
            st.markdown("### 對應候補名冊")
            st.dataframe(matched_records, use_container_width=True)

        st.caption(
            "若你的申請是「隨到隨辦」，本工具會把同社宅、同房型、同戶別的"
            "「新案場招租」待遞補人數視為前置等待，以避免過度樂觀。"
        )

with tab_stats:
    st.subheader("目前名冊概況")

    if stats_df.empty:
        st.info("目前沒有 detail_queue_stats.csv。")
    else:
        st.dataframe(stats_df, use_container_width=True)

with tab_about:
    st.subheader("使用說明")

    st.markdown(
        """
        這是一個公開候補資料查詢工具。使用者可以輸入自己的候補序號，
        查詢目前公開名冊中可能還有多少人在前方等待。

        ### 注意事項

        - 本工具不是臺中市政府官方網站。
        - 本工具不會保存使用者輸入的資料。
        - 本工具只依公開候補名冊推估，不代表官方遞補結果。
        - 如果短期速度無法估算，可能代表近期名冊沒有變動，或歷史資料不足。
        - 實際遞補、資格審查、選屋與入住時間，仍以官方公告與通知為準。
        """
    )