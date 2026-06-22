from pathlib import Path
from datetime import date

import pandas as pd
import streamlit as st

from constants import (
    KEY_COLUMNS,
    PRIORITY_ORDER,
    PERIOD_OPTIONS,
)

from utils import (
    add_processed_count,
    append_note,
    available_columns,
    format_date,
    format_number,
    get_data_date,
    latest_row_by_date,
    read_csv_if_exists,
    to_number,
    to_timestamp,
)


# =========================
# 基本設定
# =========================

BASE_DIR = Path(__file__).parent

PROJECT_LINKS_FILE = BASE_DIR / "project_links.csv"
MY_APPLICATIONS_FILE = BASE_DIR / "my_applications.csv"
RECORDS_FILE = BASE_DIR / "detail_queue_records.csv"
STATS_FILE = BASE_DIR / "detail_queue_stats.csv"
STATS_HISTORY_FILE = BASE_DIR / "detail_queue_stats_history.csv"
PROGRESS_FILE = BASE_DIR / "queue_progress_analysis.csv"
METADATA_FILE = BASE_DIR / "project_metadata.csv"

# 用於保守估算：若我的名冊是「隨到隨辦」，同案場同房型同戶別的「新案場招租」通常應先處理。

st.set_page_config(
    page_title="社宅候補追蹤工具",
    layout="wide",
)

st.title("社宅候補追蹤工具")


# =========================
# 讀寫資料
# =========================

def load_project_links() -> pd.DataFrame:
    return read_csv_if_exists(
        PROJECT_LINKS_FILE,
        columns=["社會住宅", "遞補類型", "名冊網址"],
    )


def load_my_applications() -> pd.DataFrame:
    return read_csv_if_exists(
        MY_APPLICATIONS_FILE,
        columns=[
            "社會住宅",
            "遞補類型",
            "房型",
            "戶別",
            "我的候補序號",
            "營運開始日",
            "備註",
        ],
    )


def save_my_applications(df: pd.DataFrame) -> None:
    df.to_csv(
        MY_APPLICATIONS_FILE,
        index=False,
        encoding="utf-8-sig",
    )


def load_records() -> pd.DataFrame:
    return read_csv_if_exists(RECORDS_FILE)


def load_status() -> pd.DataFrame:
    return read_csv_if_exists(STATS_FILE)


def load_metadata() -> pd.DataFrame:
    return read_csv_if_exists(METADATA_FILE)


def load_history() -> pd.DataFrame:
    """
    用來計算「最近一個月／三個月／六個月／一年」速度。

    優先使用 detail_queue_stats_history.csv。
    若沒有這個檔案，就退而使用 queue_progress_analysis.csv。
    你的 analyze_queue_progress.py 目前輸出的 queue_progress_analysis.csv
    也保留了每次抓取的「抓取日期」與「已處理人數」相關欄位，因此可用來估算期間速度。
    """
    if STATS_HISTORY_FILE.exists():
        return pd.read_csv(STATS_HISTORY_FILE)

    if PROGRESS_FILE.exists():
        return pd.read_csv(PROGRESS_FILE)

    return pd.DataFrame()


# =========================
# 通用工具函式
# =========================

def filter_by_key(df: pd.DataFrame, project_name, queue_type, room_type, household_type) -> pd.DataFrame:
    if df.empty:
        return df

    missing = [col for col in KEY_COLUMNS if col not in df.columns]
    if missing:
        return pd.DataFrame()

    return df[
        (df["社會住宅"] == project_name)
        & (df["遞補類型"] == queue_type)
        & (df["房型"] == room_type)
        & (df["戶別"] == household_type)
    ].copy()

def calculate_preceding_queue_waiting(
    status_df: pd.DataFrame,
    project_name,
    queue_type,
    room_type,
    household_type,
) -> int:
    """
    保守估算前置名冊待遞補人數。

    例：我的申請是「隨到隨辦」時，若同社宅、同房型、同戶別仍有
    「新案場招租」待遞補，則把它列為前置等待量。
    """
    if status_df.empty or "待遞補人數" not in status_df.columns:
        return 0

    required_columns = ["社會住宅", "遞補類型", "房型", "戶別", "待遞補人數"]
    missing = [col for col in required_columns if col not in status_df.columns]
    if missing:
        return 0

    current_priority = PRIORITY_ORDER.get(queue_type)
    if current_priority is None:
        return 0

    candidate_rows = status_df[
        (status_df["社會住宅"] == project_name)
        & (status_df["房型"] == room_type)
        & (status_df["戶別"] == household_type)
    ].copy()

    if candidate_rows.empty:
        return 0

    candidate_rows["_priority"] = candidate_rows["遞補類型"].map(PRIORITY_ORDER)
    candidate_rows["待遞補人數"] = pd.to_numeric(
        candidate_rows["待遞補人數"],
        errors="coerce",
    ).fillna(0)

    preceding_rows = candidate_rows[
        candidate_rows["_priority"].notna()
        & (candidate_rows["_priority"] < current_priority)
    ]

    return int(preceding_rows["待遞補人數"].sum())


def get_conservative_speed_status_rows(
    status_df: pd.DataFrame,
    project_name,
    queue_type,
    room_type,
    household_type,
) -> pd.DataFrame:
    """
    取得用來估算「保守等待量」速度的官方統計列。

    若我的名冊是「隨到隨辦」，估算速度時不能只看隨到隨辦本身，
    因為它可能要等「新案場招租」先消化。
    因此這裡會抓同社宅、同房型、同戶別中，優先序早於或等於目前名冊的列。
    """
    if status_df.empty:
        return pd.DataFrame()

    required_columns = ["社會住宅", "遞補類型", "房型", "戶別"]
    missing = [col for col in required_columns if col not in status_df.columns]
    if missing:
        return pd.DataFrame()

    current_priority = PRIORITY_ORDER.get(queue_type)
    if current_priority is None:
        return filter_by_key(status_df, project_name, queue_type, room_type, household_type)

    candidate_rows = status_df[
        (status_df["社會住宅"] == project_name)
        & (status_df["房型"] == room_type)
        & (status_df["戶別"] == household_type)
    ].copy()

    if candidate_rows.empty:
        return pd.DataFrame()

    candidate_rows["_priority"] = candidate_rows["遞補類型"].map(PRIORITY_ORDER)

    speed_rows = candidate_rows[
        candidate_rows["_priority"].notna()
        & (candidate_rows["_priority"] <= current_priority)
    ].drop(columns=["_priority"])

    return speed_rows.copy()

# =========================
# 估算函式
# =========================

def estimate_long_term_speed(
    status_rows: pd.DataFrame,
    metadata_rows: pd.DataFrame,
    base_date: pd.Timestamp,
):
    """
    營運以來速度：
    已處理人數 ÷ 營運開始日至資料取得日的週數。
    """
    status_rows = add_processed_count(status_rows)

    if status_rows.empty:
        return None, "找不到目前官方遞補統計，無法計算營運以來速度"

    status_rows = status_rows.copy()
    status_rows["已處理人數"] = pd.to_numeric(
        status_rows["已處理人數"],
        errors="coerce",
    )
    processed_count = status_rows["已處理人數"].sum()

    if pd.isna(processed_count):
        return None, "目前官方遞補統計缺少已處理人數"

    if metadata_rows.empty or "推估用日期" not in metadata_rows.columns:
        return None, "找不到 project_metadata.csv 的推估用日期"

    operation_start_date = pd.to_datetime(
        metadata_rows.iloc[0]["推估用日期"],
        errors="coerce",
    )

    if pd.isna(operation_start_date):
        return None, "推估用日期無法解析"

    days_since_start = (base_date - operation_start_date).days
    weeks_since_start = days_since_start / 7

    if weeks_since_start <= 0:
        return None, "營運時間不足，無法估算"

    if processed_count <= 0:
        return None, "營運以來尚無推進紀錄，無法估算"

    speed = processed_count / weeks_since_start
    return speed, ""


def estimate_recent_speed(
    history_rows: pd.DataFrame,
    period_days: int,
):
    """
    最近期間速度：
    以「最近一個月／三個月／六個月／一年」內，已處理人數的變化量估算。

    起點取法：
    1. 優先取最接近「視窗起點」且早於或等於該日期的資料。
    2. 若沒有早於視窗起點的資料，就用目前可取得的最早資料。
    3. 終點取最新資料。

    這樣可以避免因為剛好沒有某一天的抓取紀錄而無法計算。
    """
    history_rows = add_processed_count(history_rows)

    if history_rows.empty:
        return None, "找不到歷史統計資料，無法計算最近期間速度"

    required_columns = ["抓取日期", "已處理人數"]
    missing = [col for col in required_columns if col not in history_rows.columns]
    if missing:
        return None, f"歷史統計資料缺少欄位：{', '.join(missing)}"

    history_rows = history_rows.copy()
    history_rows["抓取日期"] = pd.to_datetime(history_rows["抓取日期"], errors="coerce")
    history_rows["已處理人數"] = pd.to_numeric(history_rows["已處理人數"], errors="coerce")
    history_rows = history_rows.dropna(subset=["抓取日期", "已處理人數"])
    history_rows = history_rows.sort_values("抓取日期")

    if len(history_rows) < 2:
        return None, "歷史資料少於兩筆，無法計算最近期間速度"

    latest = history_rows.iloc[-1]
    latest_date = latest["抓取日期"]
    latest_processed = latest["已處理人數"]

    window_start = latest_date - pd.Timedelta(days=period_days)

    before_or_at_window_start = history_rows[
        history_rows["抓取日期"] <= window_start
    ]

    if before_or_at_window_start.empty:
        start = history_rows.iloc[0]
        data_coverage_note = (
            f"可用歷史資料不足 {period_days} 天，"
            f"本次實際使用 {(latest_date - start['抓取日期']).days} 天資料估算"
        )
    else:
        start = before_or_at_window_start.iloc[-1]
        data_coverage_note = ""

    start_date = start["抓取日期"]
    start_processed = start["已處理人數"]

    days_elapsed = (latest_date - start_date).days
    processed_delta = latest_processed - start_processed

    if days_elapsed <= 0:
        return None, "歷史資料日期間隔不足，無法估算"

    if processed_delta <= 0:
        return None, "所選期間內沒有推進，無法估算遞補日期"

    speed = processed_delta / days_elapsed * 7

    return speed, data_coverage_note


def estimate_one_application(
    my_row: pd.Series,
    records_df: pd.DataFrame,
    status_df: pd.DataFrame,
    metadata_df: pd.DataFrame,
    history_df: pd.DataFrame,
    selected_period_label: str,
) -> dict:
    project_name = my_row.get("社會住宅")
    queue_type = my_row.get("遞補類型")
    room_type = my_row.get("房型")
    household_type = my_row.get("戶別")
    my_rank = to_number(my_row.get("我的候補序號"))
    my_note = my_row.get("備註", "")

    result = {
        "社宅": project_name,
        "遞補類型": queue_type,
        "房型": room_type,
        "戶別": household_type,
        "我的序號": format_number(my_rank, digits=0),
        "狀態": None,
        "前面約剩幾位": None,
        "本名冊前方待遞補人數": None,
        "前置名冊待遞補人數": None,
        "保守估計前方等待人數": None,
        "估算基準": selected_period_label,
        "平均每週推進人數": None,
        "預估剩餘週數": None,
        "預估遞補完成日期": None,
        "資料取得日": None,
        "備註": my_note,
    }

    if pd.isna(my_rank):
        result["狀態"] = "我的候補序號無法解析"
        result["備註"] = append_note(result["備註"], "請確認 my_applications.csv 的我的候補序號")
        return result

    matched_records = filter_by_key(records_df, project_name, queue_type, room_type, household_type)
    matched_status = filter_by_key(status_df, project_name, queue_type, room_type, household_type)
    matched_history = filter_by_key(history_df, project_name, queue_type, room_type, household_type)

    if not metadata_df.empty and "社會住宅" in metadata_df.columns:
        matched_metadata = metadata_df[metadata_df["社會住宅"] == project_name].copy()
    else:
        matched_metadata = pd.DataFrame()

    base_date = get_data_date(matched_status, matched_history)
    result["資料取得日"] = format_date(base_date)

    if matched_records.empty:
        result["狀態"] = "找不到名冊資料"
        result["備註"] = append_note(
            result["備註"],
            "detail_queue_records.csv 找不到對應案場、遞補類型、房型、戶別",
        )
        return result

    matched_records = matched_records.copy()

    if "候補序號" not in matched_records.columns:
        result["狀態"] = "名冊資料缺少候補序號"
        result["備註"] = append_note(result["備註"], "請檢查 detail_queue_records.csv")
        return result

    matched_records["候補序號"] = pd.to_numeric(
        matched_records["候補序號"],
        errors="coerce",
    )

    my_record = matched_records[matched_records["候補序號"] == int(my_rank)]

    if my_record.empty:
        result["狀態"] = "名冊中找不到我的序號"
    elif "遞補狀態" in my_record.columns:
        result["狀態"] = my_record.iloc[0]["遞補狀態"]
    else:
        result["狀態"] = "名冊中有此序號，但缺少遞補狀態"

    if "遞補狀態" not in matched_records.columns:
        result["備註"] = append_note(result["備註"], "名冊資料缺少遞補狀態，無法計算前方待遞補人數")
        return result

    people_ahead_waiting = matched_records[
        (matched_records["候補序號"] < int(my_rank))
        & (matched_records["遞補狀態"] == "待遞補")
    ]

    ahead_waiting_count = len(people_ahead_waiting)
    preceding_queue_waiting_count = calculate_preceding_queue_waiting(
        status_df=status_df,
        project_name=project_name,
        queue_type=queue_type,
        room_type=room_type,
        household_type=household_type,
    )
    conservative_ahead_count = ahead_waiting_count + preceding_queue_waiting_count

    result["本名冊前方待遞補人數"] = ahead_waiting_count
    result["前置名冊待遞補人數"] = preceding_queue_waiting_count
    result["保守估計前方等待人數"] = conservative_ahead_count
    result["前面約剩幾位"] = conservative_ahead_count

    period_days = PERIOD_OPTIONS[selected_period_label]

    if period_days is None:
        speed_status_rows = get_conservative_speed_status_rows(
            status_df=status_df,
            project_name=project_name,
            queue_type=queue_type,
            room_type=room_type,
            household_type=household_type,
        )
        if not speed_status_rows.empty:
            base_date = get_data_date(speed_status_rows, matched_history)
            result["資料取得日"] = format_date(base_date)

        speed, speed_note = estimate_long_term_speed(
            status_rows=speed_status_rows,
            metadata_rows=matched_metadata,
            base_date=base_date,
        )

        if preceding_queue_waiting_count > 0:
            speed_note = append_note(
                speed_note,
                "營運以來速度已改用前置名冊與本名冊合併已處理人數估算",
            )
    else:
        speed, speed_note = estimate_recent_speed(
            history_rows=matched_history,
            period_days=period_days,
        )

    if speed is None or pd.isna(speed) or speed <= 0:
        result["平均每週推進人數"] = None
        result["預估剩餘週數"] = None
        result["預估遞補完成日期"] = None
        result["備註"] = append_note(result["備註"], speed_note)
        return result

    estimated_weeks = conservative_ahead_count / speed
    estimated_date = base_date + pd.to_timedelta(estimated_weeks, unit="W")

    result["平均每週推進人數"] = format_number(speed, digits=2)
    result["預估剩餘週數"] = format_number(estimated_weeks, digits=1)
    result["預估遞補完成日期"] = format_date(estimated_date)
    result["備註"] = append_note(result["備註"], speed_note)

    return result


def build_dashboard(
    my_df: pd.DataFrame,
    records_df: pd.DataFrame,
    status_df: pd.DataFrame,
    metadata_df: pd.DataFrame,
    history_df: pd.DataFrame,
    selected_period_label: str,
) -> pd.DataFrame:
    if my_df.empty:
        return pd.DataFrame()

    rows = []

    for _, my_row in my_df.iterrows():
        rows.append(
            estimate_one_application(
                my_row=my_row,
                records_df=records_df,
                status_df=status_df,
                metadata_df=metadata_df,
                history_df=history_df,
                selected_period_label=selected_period_label,
            )
        )

    return pd.DataFrame(rows)


def build_period_comparison(
    my_df: pd.DataFrame,
    records_df: pd.DataFrame,
    status_df: pd.DataFrame,
    metadata_df: pd.DataFrame,
    history_df: pd.DataFrame,
) -> pd.DataFrame:
    if my_df.empty:
        return pd.DataFrame()

    all_rows = []

    for period_label in PERIOD_OPTIONS.keys():
        period_df = build_dashboard(
            my_df=my_df,
            records_df=records_df,
            status_df=status_df,
            metadata_df=metadata_df,
            history_df=history_df,
            selected_period_label=period_label,
        )

        all_rows.append(period_df)

    if not all_rows:
        return pd.DataFrame()

    comparison_long = pd.concat(all_rows, ignore_index=True)

    keep_columns = [
        "社宅",
        "遞補類型",
        "房型",
        "戶別",
        "我的序號",
        "前面約剩幾位",
        "本名冊前方待遞補人數",
        "前置名冊待遞補人數",
        "保守估計前方等待人數",
        "估算基準",
        "平均每週推進人數",
        "預估剩餘週數",
        "預估遞補完成日期",
        "資料取得日",
        "備註",
    ]

    return comparison_long[available_columns(comparison_long, keep_columns)]


def build_status_detail(
    status_df: pd.DataFrame,
    history_df: pd.DataFrame,
    selected_period_label: str,
) -> pd.DataFrame:
    """
    官方整體遞補統計。
    這不是首頁主表，只放在詳細資料區。
    """
    if status_df.empty:
        return pd.DataFrame()

    detail_df = add_processed_count(status_df)

    if selected_period_label != "營運以來" and not history_df.empty:
        speed_rows = []

        for _, row in detail_df.iterrows():
            project_name = row.get("社會住宅")
            queue_type = row.get("遞補類型")
            room_type = row.get("房型")
            household_type = row.get("戶別")

            matched_history = filter_by_key(
                history_df,
                project_name,
                queue_type,
                room_type,
                household_type,
            )

            period_days = PERIOD_OPTIONS[selected_period_label]
            speed, speed_note = estimate_recent_speed(matched_history, period_days)

            speed_rows.append({
                "社會住宅": project_name,
                "遞補類型": queue_type,
                "房型": room_type,
                "戶別": household_type,
                "所選基準平均每週推進人數": format_number(speed, digits=2),
                "速度備註": speed_note,
            })

        speed_df = pd.DataFrame(speed_rows)

        detail_df = detail_df.merge(
            speed_df,
            on=KEY_COLUMNS,
            how="left",
        )

    return detail_df


# =========================
# 載入資料
# =========================

project_links_df = load_project_links()
my_df = load_my_applications()
records_df = load_records()
status_df = load_status()
metadata_df = load_metadata()
history_df = load_history()


# =========================
# 我的遞補總覽
# =========================

st.header("我的遞補總覽")

selected_period_label = st.selectbox(
    "選擇估算基準",
    list(PERIOD_OPTIONS.keys()),
    index=2,
    help=(
        "營運以來：用案場營運起始日至資料取得日的平均速度估算。"
        "最近一個月／三個月／六個月／一年：用歷史抓取資料在該期間內的推進速度估算。"
    ),
)

if my_df.empty:
    st.info("目前尚未新增任何候補資料。請先在下方「我的候補設定」新增。")
else:
    dashboard_df = build_dashboard(
        my_df=my_df,
        records_df=records_df,
        status_df=status_df,
        metadata_df=metadata_df,
        history_df=history_df,
        selected_period_label=selected_period_label,
    )

    dashboard_columns = [
        "社宅",
        "遞補類型",
        "房型",
        "戶別",
        "我的序號",
        "狀態",
        "前面約剩幾位",
        "本名冊前方待遞補人數",
        "前置名冊待遞補人數",
        "保守估計前方等待人數",
        "估算基準",
        "平均每週推進人數",
        "預估剩餘週數",
        "預估遞補完成日期",
        "資料取得日",
        "備註",
    ]

    st.dataframe(
        dashboard_df[available_columns(dashboard_df, dashboard_columns)],
        use_container_width=True,
        hide_index=True,
    )

    st.caption(
        "說明：預估日期只是用目前名冊與歷史推進速度推算，"
        "不是官方承諾。若所選期間內沒有推進，該期間估算會顯示為空。"
    )


with st.expander("比較所有估算基準", expanded=False):
    if my_df.empty:
        st.info("目前尚未新增任何候補資料。")
    else:
        comparison_df = build_period_comparison(
            my_df=my_df,
            records_df=records_df,
            status_df=status_df,
            metadata_df=metadata_df,
            history_df=history_df,
        )

        st.dataframe(
            comparison_df,
            use_container_width=True,
            hide_index=True,
        )


# =========================
# 我的候補設定
# =========================

st.header("我的候補設定")

if project_links_df.empty:
    st.warning("找不到 project_links.csv，新增候補資料時無法提供案場選單。")
    project_options = []
else:
    project_options = sorted(project_links_df["社會住宅"].dropna().unique().tolist())


with st.expander("新增候補資料", expanded=False):
    if not project_options:
        st.info("請先建立 project_links.csv。")
    else:
        with st.form("add_applications_form"):
            selected_projects = st.multiselect(
                "選擇社會住宅案場，可多選",
                project_options,
            )

            st.write("請為每個案場分別設定房型、戶別與候補序號：")

            input_records = []

            for project_name in selected_projects:
                st.markdown(f"### {project_name}")

                if "遞補類型" in project_links_df.columns:
                    queue_type_options = (
                        project_links_df[project_links_df["社會住宅"] == project_name]["遞補類型"]
                        .dropna()
                        .unique()
                        .tolist()
                    )
                else:
                    queue_type_options = []

                if not queue_type_options:
                    queue_type_options = ["隨到隨辦", "新案場招租"]

                queue_type = st.selectbox(
                    f"{project_name}：遞補類型",
                    queue_type_options,
                    index=0,
                    key=f"queue_type_{project_name}",
                )

                room_type = st.selectbox(
                    f"{project_name}：房型",
                    ["一房型", "二房型", "三房型"],
                    index=2,
                    key=f"room_type_{project_name}",
                )

                household_type = st.selectbox(
                    f"{project_name}：戶別",
                    ["一般戶", "關懷戶"],
                    index=0,
                    key=f"household_type_{project_name}",
                )

                my_rank = st.number_input(
                    f"{project_name}：我的候補序號",
                    min_value=1,
                    step=1,
                    key=f"rank_{project_name}",
                )

                note = st.text_input(
                    f"{project_name}：備註",
                    key=f"note_{project_name}",
                )

                input_records.append({
                    "社會住宅": project_name,
                    "遞補類型": queue_type,
                    "房型": room_type,
                    "戶別": household_type,
                    "我的候補序號": int(my_rank),
                    "營運開始日": "",
                    "備註": note,
                })

            submitted = st.form_submit_button("新增候補資料")

            if submitted:
                if len(input_records) == 0:
                    st.warning("請至少選擇一個社會住宅案場")
                else:
                    new_df = pd.DataFrame(input_records)

                    updated_my_df = pd.concat(
                        [my_df, new_df],
                        ignore_index=True,
                    )

                    updated_my_df = updated_my_df.drop_duplicates(
                        subset=KEY_COLUMNS,
                        keep="last",
                    )

                    save_my_applications(updated_my_df)

                    st.success("已新增候補資料")
                    st.rerun()


if not my_df.empty:
    with st.expander("刪除候補資料", expanded=False):
        delete_options = [
            f"{idx}｜{row['社會住宅']}｜{row.get('遞補類型', '')}｜{row['房型']}｜{row['戶別']}｜序號 {row['我的候補序號']}"
            for idx, row in my_df.iterrows()
        ]

        selected_delete_items = st.multiselect(
            "選擇要刪除的資料，可多選",
            delete_options,
        )

        if st.button("刪除選取資料"):
            if len(selected_delete_items) == 0:
                st.warning("請至少選擇一筆要刪除的資料")
            else:
                delete_indexes = []

                for item in selected_delete_items:
                    index_text = item.split("｜")[0]
                    delete_indexes.append(int(index_text))

                updated_my_df = my_df.drop(index=delete_indexes).reset_index(drop=True)

                save_my_applications(updated_my_df)

                st.success("已刪除選取資料")
                st.rerun()


# =========================
# 詳細資料
# =========================

st.header("詳細資料")

with st.expander("目前候補設定原始資料", expanded=False):
    if my_df.empty:
        st.info("目前尚未新增任何候補資料。")
    else:
        st.dataframe(
            my_df,
            use_container_width=True,
            hide_index=True,
        )


with st.expander("官方遞補統計", expanded=False):
    if status_df.empty:
        st.info("尚未找到 detail_queue_stats.csv，請先執行 scrape_all_detail_lists.py。")
    else:
        col1, col2 = st.columns(2)

        with col1:
            room_filter = st.selectbox(
                "篩選房型",
                ["全部", "一房型", "二房型", "三房型"],
                index=0,
                key="status_room_filter",
            )

        with col2:
            household_filter = st.selectbox(
                "篩選戶別",
                ["全部", "一般戶", "關懷戶"],
                index=0,
                key="status_household_filter",
            )

        detail_status_df = build_status_detail(
            status_df=status_df,
            history_df=history_df,
            selected_period_label=selected_period_label,
        )

        if room_filter != "全部" and "房型" in detail_status_df.columns:
            detail_status_df = detail_status_df[detail_status_df["房型"] == room_filter]

        if household_filter != "全部" and "戶別" in detail_status_df.columns:
            detail_status_df = detail_status_df[detail_status_df["戶別"] == household_filter]

        detail_columns = [
            "社會住宅",
            "遞補類型",
            "房型",
            "戶別",
            "抓取日期",
            "已遞補人數",
            "已放棄人數",
            "已處理人數",
            "待遞補人數",
            "名冊總人數",
            "實際放棄率",
            "所選基準平均每週推進人數",
            "速度備註",
        ]

        st.dataframe(
            detail_status_df[available_columns(detail_status_df, detail_columns)],
            use_container_width=True,
            hide_index=True,
        )


with st.expander("案場營運日期 metadata", expanded=False):
    if metadata_df.empty:
        st.info("尚未找到 project_metadata.csv。")
    else:
        metadata_columns = [
            "社會住宅",
            "推估用日期",
            "日期精度",
            "資料等級",
            "資料依據",
            "來源網址",
        ]

        st.dataframe(
            metadata_df[available_columns(metadata_df, metadata_columns)],
            use_container_width=True,
            hide_index=True,
        )


with st.expander("估算檔案狀態", expanded=False):
    file_status = pd.DataFrame([
        {
            "檔案": PROJECT_LINKS_FILE.name,
            "用途": "新增候補資料時提供案場選單",
            "是否存在": PROJECT_LINKS_FILE.exists(),
        },
        {
            "檔案": MY_APPLICATIONS_FILE.name,
            "用途": "你的候補設定",
            "是否存在": MY_APPLICATIONS_FILE.exists(),
        },
        {
            "檔案": RECORDS_FILE.name,
            "用途": "逐筆候補名冊，用來計算前方待遞補人數與我的狀態",
            "是否存在": RECORDS_FILE.exists(),
        },
        {
            "檔案": STATS_FILE.name,
            "用途": "目前官方統計，用來計算營運以來速度",
            "是否存在": STATS_FILE.exists(),
        },
        {
            "檔案": STATS_HISTORY_FILE.name,
            "用途": "歷史統計，用來計算最近一個月／三個月／六個月／一年速度",
            "是否存在": STATS_HISTORY_FILE.exists(),
        },
        {
            "檔案": PROGRESS_FILE.name,
            "用途": "若沒有歷史統計檔，作為最近期間估算的備用來源",
            "是否存在": PROGRESS_FILE.exists(),
        },
        {
            "檔案": METADATA_FILE.name,
            "用途": "案場營運推估日期，用來計算營運以來速度",
            "是否存在": METADATA_FILE.exists(),
        },
    ])

    st.dataframe(
        file_status,
        use_container_width=True,
        hide_index=True,
    )