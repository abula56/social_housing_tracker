from pathlib import Path

import pandas as pd
import streamlit as st

from constants import PERIOD_OPTIONS
from query_estimator import estimate_one_application


KEY_COLUMNS = ["社會住宅", "遞補類型", "房型", "戶別"]
MY_APPLICATION_COLUMNS = [*KEY_COLUMNS, "我的候補序號"]
OPTIONAL_MY_APPLICATION_COLUMNS = ["備註"]

RECORDS_FILE = Path("detail_queue_records.csv")
STATS_FILE = Path("detail_queue_stats.csv")
HISTORY_FILE = Path("detail_queue_stats_history.csv")
METADATA_FILE = Path("project_metadata.csv")


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


def editor_options(source_df: pd.DataFrame, column: str, current_values=None) -> list[str]:
    options = [""]
    options.extend(sorted_options(source_df, column))

    if current_values is not None:
        try:
            values = pd.Series(current_values).dropna().astype(str).str.strip().tolist()
        except Exception:
            values = []
        options.extend([value for value in values if value])

    return list(dict.fromkeys(options))


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


def make_my_applications_template(source_df: pd.DataFrame) -> pd.DataFrame:
    if source_df.empty or any(col not in source_df.columns for col in KEY_COLUMNS):
        return pd.DataFrame(
            [
                {
                    "社會住宅": "南屯建功1號",
                    "遞補類型": "隨到隨辦",
                    "房型": "二房型",
                    "戶別": "一般戶",
                    "我的候補序號": 1,
                    "備註": "範例，請刪除或改成自己的資料",
                }
            ]
        )

    sample = source_df[KEY_COLUMNS].drop_duplicates().head(3).copy()
    if sample.empty:
        sample = pd.DataFrame(
            [
                {
                    "社會住宅": "南屯建功1號",
                    "遞補類型": "隨到隨辦",
                    "房型": "二房型",
                    "戶別": "一般戶",
                }
            ]
        )

    sample["我的候補序號"] = 1
    sample["備註"] = "範例，請刪除或改成自己的資料"
    return sample[[*MY_APPLICATION_COLUMNS, "備註"]]


def clean_my_applications_df(my_df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    errors = []

    if my_df is None or my_df.empty:
        return pd.DataFrame(columns=[*MY_APPLICATION_COLUMNS, "備註"]), errors

    my_df = my_df.copy()
    my_df.columns = [str(col).strip() for col in my_df.columns]

    missing = [col for col in MY_APPLICATION_COLUMNS if col not in my_df.columns]
    if missing:
        errors.append(f"上傳檔案缺少必要欄位：{', '.join(missing)}")
        return pd.DataFrame(columns=[*MY_APPLICATION_COLUMNS, "備註"]), errors

    if "備註" not in my_df.columns:
        my_df["備註"] = ""

    keep_columns = [*MY_APPLICATION_COLUMNS, "備註"]
    my_df = my_df[keep_columns]

    for col in KEY_COLUMNS + ["備註"]:
        my_df[col] = my_df[col].fillna("").astype(str).str.strip()

    my_df["我的候補序號"] = pd.to_numeric(
        my_df["我的候補序號"],
        errors="coerce",
    )

    required_text_filled = my_df[KEY_COLUMNS].apply(
        lambda row: any(str(value).strip() for value in row),
        axis=1,
    )
    rank_filled = my_df["我的候補序號"].notna()
    my_df = my_df[required_text_filled | rank_filled].copy()

    if my_df.empty:
        return pd.DataFrame(columns=keep_columns), errors

    incomplete_rows = my_df[
        my_df[KEY_COLUMNS].eq("").any(axis=1)
        | my_df["我的候補序號"].isna()
        | (my_df["我的候補序號"] < 1)
    ]

    if not incomplete_rows.empty:
        errors.append(
            "有資料列缺少社會住宅、遞補類型、房型、戶別，或候補序號不是大於等於 1 的數字。"
        )

    valid_df = my_df.drop(incomplete_rows.index).copy()
    if valid_df.empty:
        return pd.DataFrame(columns=keep_columns), errors

    valid_df["我的候補序號"] = valid_df["我的候補序號"].astype(int)
    return valid_df.reset_index(drop=True), errors


def estimate_my_applications(
    my_df: pd.DataFrame,
    records_df: pd.DataFrame,
    stats_df: pd.DataFrame,
    metadata_df: pd.DataFrame,
    history_df: pd.DataFrame,
    period_labels: list[str],
) -> pd.DataFrame:
    results = []
    for index, my_row in my_df.iterrows():
        for period_label in period_labels:
            result = estimate_one_application(
                my_row=my_row,
                records_df=records_df,
                status_df=stats_df,
                metadata_df=metadata_df,
                history_df=history_df,
                selected_period_label=period_label,
            )
            result.insert(0, "筆數", index + 1)
            results.append(result)

    return pd.DataFrame(results)


records_df = load_csv(RECORDS_FILE)
stats_df = load_csv(STATS_FILE)
history_df = load_csv(HISTORY_FILE)
metadata_df = load_csv(METADATA_FILE)

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


tab_query, tab_my, tab_stats, tab_about = st.tabs(["🏠 候補查詢", "📁 我的候補估算", "📊 名冊概況", "ℹ️ 說明"])

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

        application_row = pd.Series(
            {
                "社會住宅": project,
                "遞補類型": queue_type,
                "房型": room_type,
                "戶別": household_type,
                "我的候補序號": int(user_number),
                "備註": "",
            }
        )

        estimate_results = []

        for period_label in PERIOD_OPTIONS.keys():
            estimate_result = estimate_one_application(
                my_row=application_row,
                records_df=records_df,
                status_df=stats_df,
                metadata_df=metadata_df,
                history_df=history_df,
                selected_period_label=period_label,
            )
            estimate_results.append(estimate_result)

        estimate_df = pd.DataFrame(estimate_results)

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

        st.markdown("### 完整預估")

        display_columns = [
            "估算基準",
            "狀態",
            "本名冊前方待遞補人數",
            "前置名冊待遞補人數",
            "保守估計前方等待人數",
            "平均每週推進人數",
            "預估剩餘週數",
            "預估遞補完成日期",
            "資料取得日",
            "備註",
        ]

        existing_display_columns = [
            col for col in display_columns if col in estimate_df.columns
        ]

        st.dataframe(
            estimate_df[existing_display_columns],
            use_container_width=True,
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

with tab_my:
    st.subheader("上傳或建立我的候補資料")

    st.info(
        "這個功能只在當次瀏覽器 session 使用你上傳或輸入的資料進行估算，"
        "不會把 my_applications.csv 寫入 GitHub，也不會保存到伺服器。"
    )

    template_df = make_my_applications_template(source_df)
    template_csv = template_df.to_csv(index=False).encode("utf-8-sig")

    st.download_button(
        "下載 my_applications.csv 範本",
        data=template_csv,
        file_name="my_applications_template.csv",
        mime="text/csv",
    )

    uploaded_my_file = st.file_uploader(
        "上傳 my_applications.csv",
        type=["csv"],
        help="必要欄位：社會住宅、遞補類型、房型、戶別、我的候補序號。備註欄可有可無。",
    )

    uploaded_my_df = pd.DataFrame(columns=[*MY_APPLICATION_COLUMNS, "備註"])
    if uploaded_my_file is not None:
        try:
            uploaded_my_df = pd.read_csv(uploaded_my_file)
        except Exception as exc:
            st.error(f"CSV 讀取失敗：{exc}")
            uploaded_my_df = pd.DataFrame(columns=[*MY_APPLICATION_COLUMNS, "備註"])

    st.markdown("### 或直接在表格輸入")
    st.caption("可以新增多列；若已上傳 CSV，表格會先帶入上傳內容，你也可以再修改後查詢。")

    if uploaded_my_df.empty:
        editor_initial_df = pd.DataFrame(
            [
                {
                    "社會住宅": "",
                    "遞補類型": "",
                    "房型": "",
                    "戶別": "",
                    "我的候補序號": None,
                    "備註": "",
                }
            ]
        )
    else:
        editor_initial_df = uploaded_my_df.copy()
        for col in [*MY_APPLICATION_COLUMNS, "備註"]:
            if col not in editor_initial_df.columns:
                editor_initial_df[col] = ""
        editor_initial_df = editor_initial_df[[*MY_APPLICATION_COLUMNS, "備註"]]

    editor_initial_df["我的候補序號"] = pd.to_numeric(
        editor_initial_df["我的候補序號"],
        errors="coerce",
    )

    edited_my_df = st.data_editor(
        editor_initial_df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "社會住宅": st.column_config.SelectboxColumn(
                "社會住宅",
                options=editor_options(source_df, "社會住宅", editor_initial_df["社會住宅"]),
            ),
            "遞補類型": st.column_config.SelectboxColumn(
                "遞補類型",
                options=editor_options(source_df, "遞補類型", editor_initial_df["遞補類型"]),
            ),
            "房型": st.column_config.SelectboxColumn(
                "房型",
                options=editor_options(source_df, "房型", editor_initial_df["房型"]),
            ),
            "戶別": st.column_config.SelectboxColumn(
                "戶別",
                options=editor_options(source_df, "戶別", editor_initial_df["戶別"]),
            ),
            "我的候補序號": st.column_config.NumberColumn(
                "我的候補序號",
                min_value=1,
                step=1,
                format="%d",
            ),
            "備註": st.column_config.TextColumn("備註"),
        },
        key="my_applications_editor",
    )

    cleaned_my_df, my_errors = clean_my_applications_df(edited_my_df)

    for error in my_errors:
        st.warning(error)

    if not cleaned_my_df.empty:
        st.markdown("### 本次候補資料")
        st.dataframe(cleaned_my_df, use_container_width=True)

        cleaned_csv = cleaned_my_df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "下載本次 my_applications.csv",
            data=cleaned_csv,
            file_name="my_applications.csv",
            mime="text/csv",
        )

    period_labels = st.multiselect(
        "估算基準",
        options=list(PERIOD_OPTIONS.keys()),
        default=list(PERIOD_OPTIONS.keys()),
    )

    if st.button("估算我的候補資料", type="primary"):
        if cleaned_my_df.empty:
            st.error("請先上傳或輸入至少一筆完整候補資料。")
        elif not period_labels:
            st.error("請至少選擇一個估算基準。")
        else:
            estimate_df = estimate_my_applications(
                my_df=cleaned_my_df,
                records_df=records_df,
                stats_df=stats_df,
                metadata_df=metadata_df,
                history_df=history_df,
                period_labels=period_labels,
            )

            st.divider()
            st.subheader("我的候補估算結果")

            display_columns = [
                "筆數",
                "社宅",
                "遞補類型",
                "房型",
                "戶別",
                "我的序號",
                "估算基準",
                "狀態",
                "本名冊前方待遞補人數",
                "前置名冊待遞補人數",
                "保守估計前方等待人數",
                "平均每週推進人數",
                "預估剩餘週數",
                "預估遞補完成日期",
                "資料取得日",
                "備註",
            ]
            existing_display_columns = [
                col for col in display_columns if col in estimate_df.columns
            ]

            st.dataframe(
                estimate_df[existing_display_columns],
                use_container_width=True,
            )

            result_csv = estimate_df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "下載估算結果 CSV",
                data=result_csv,
                file_name="my_application_estimates.csv",
                mime="text/csv",
            )

            st.caption(
                "若狀態顯示找不到名冊資料，通常是社會住宅、遞補類型、房型、戶別其中一欄與公開名冊不完全一致。"
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
        - 本工具不會保存使用者輸入或上傳的資料。
        - 「我的候補估算」只在當次 session 使用上傳的 my_applications.csv，不會寫入 GitHub 或伺服器。
        - 本工具只依公開候補名冊推估，不代表官方遞補結果。
        - 如果短期速度無法估算，可能代表近期名冊沒有變動，或歷史資料不足。
        - 實際遞補、資格審查、選屋與入住時間，仍以官方公告與通知為準。
        """
    )