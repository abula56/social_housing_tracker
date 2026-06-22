from pathlib import Path

import pandas as pd
import streamlit as st

from constants import (
    KEY_COLUMNS,
    PRIORITY_ORDER,
    PERIOD_OPTIONS,
    EVENT_LOG_COLUMNS,
)

from utils import (
    add_processed_count,
    append_note,
    available_columns,
    format_date,
    format_number,
    get_data_date,
    read_csv_if_exists,
    to_number,
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
EVENT_LOG_FILE = BASE_DIR / "queue_event_log.csv"

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

def load_event_log() -> pd.DataFrame:
    return read_csv_if_exists(
        EVENT_LOG_FILE,
        columns=EVENT_LOG_COLUMNS,
    )

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

def get_conservative_speed_history_rows(
    history_df: pd.DataFrame,
    project_name,
    queue_type,
    room_type,
    household_type,
) -> pd.DataFrame:
    """
    取得用來估算「保守等待量」最近期間速度的歷史統計列。

    若我的名冊是「隨到隨辦」，估算最近一個月／三個月／六個月／一年速度時，
    也應該納入同社宅、同房型、同戶別中，優先序早於或等於目前名冊的歷史資料。
    """
    if history_df.empty:
        return pd.DataFrame()

    required_columns = ["社會住宅", "遞補類型", "房型", "戶別"]
    missing = [col for col in required_columns if col not in history_df.columns]
    if missing:
        return pd.DataFrame()

    current_priority = PRIORITY_ORDER.get(queue_type)
    if current_priority is None:
        return filter_by_key(history_df, project_name, queue_type, room_type, household_type)

    candidate_rows = history_df[
        (history_df["社會住宅"] == project_name)
        & (history_df["房型"] == room_type)
        & (history_df["戶別"] == household_type)
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

    history_rows = (
        history_rows
        .groupby("抓取日期", as_index=False)["已處理人數"]
        .sum()
        .sort_values("抓取日期")
    )

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
        speed_history_rows = get_conservative_speed_history_rows(
            history_df=history_df,
            project_name=project_name,
            queue_type=queue_type,
            room_type=room_type,
            household_type=household_type,
        )

        if not speed_history_rows.empty:
            base_date = get_data_date(matched_status, speed_history_rows)
            result["資料取得日"] = format_date(base_date)

        speed, speed_note = estimate_recent_speed(
            history_rows=speed_history_rows,
            period_days=period_days,
        )

        if preceding_queue_waiting_count > 0:
            speed_note = append_note(
                speed_note,
                "最近期間速度已改用前置名冊與本名冊合併已處理人數估算",
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


def build_my_related_event_log(
    event_log_df: pd.DataFrame,
    my_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    篩出與我的申請相關的名冊變動。

    若我的申請是「隨到隨辦」，則同案場、同房型、同戶別中，
    優先序早於或等於我的遞補類型的事件都視為相關。

    例：
    我的申請：西屯國安一期 / 隨到隨辦 / 三房型 / 一般戶
    相關事件：
    - 西屯國安一期 / 新案場招租 / 三房型 / 一般戶
    - 西屯國安一期 / 隨到隨辦 / 三房型 / 一般戶
    """
    if event_log_df.empty or my_df.empty:
        return pd.DataFrame()

    required_event_columns = ["社會住宅", "遞補類型", "房型", "戶別"]
    required_my_columns = ["社會住宅", "遞補類型", "房型", "戶別"]

    if any(col not in event_log_df.columns for col in required_event_columns):
        return pd.DataFrame()

    if any(col not in my_df.columns for col in required_my_columns):
        return pd.DataFrame()

    matched_rows = []

    for _, my_row in my_df.iterrows():
        project_name = my_row.get("社會住宅")
        queue_type = my_row.get("遞補類型")
        room_type = my_row.get("房型")
        household_type = my_row.get("戶別")

        my_priority = PRIORITY_ORDER.get(queue_type)

        candidate_rows = event_log_df[
            (event_log_df["社會住宅"] == project_name)
            & (event_log_df["房型"] == room_type)
            & (event_log_df["戶別"] == household_type)
        ].copy()

        if candidate_rows.empty:
            continue

        if my_priority is not None:
            candidate_rows["_priority"] = candidate_rows["遞補類型"].map(PRIORITY_ORDER)

            candidate_rows = candidate_rows[
                candidate_rows["_priority"].notna()
                & (candidate_rows["_priority"] <= my_priority)
            ].copy()

            candidate_rows = candidate_rows.drop(columns=["_priority"])

        else:
            candidate_rows = candidate_rows[
                candidate_rows["遞補類型"] == queue_type
            ].copy()

        candidate_rows["對應我的申請"] = (
            f"{project_name}／{queue_type}／{room_type}／{household_type}"
        )

        matched_rows.append(candidate_rows)

    if not matched_rows:
        return pd.DataFrame()

    result_df = pd.concat(matched_rows, ignore_index=True)
    result_df = result_df.drop_duplicates()

    if "事件日期" in result_df.columns:
        result_df["事件日期"] = pd.to_datetime(
            result_df["事件日期"],
            errors="coerce",
        )
        result_df = result_df.sort_values("事件日期", ascending=False)

    return result_df

def build_my_related_history(
    history_df: pd.DataFrame,
    my_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    篩出與我的申請相關的歷史統計資料。

    若我的申請是「隨到隨辦」，則同案場、同房型、同戶別中，
    優先序早於或等於我的遞補類型的歷史資料都視為相關。
    """
    if history_df.empty or my_df.empty:
        return pd.DataFrame()

    required_columns = ["抓取日期", "社會住宅", "遞補類型", "房型", "戶別"]
    if any(col not in history_df.columns for col in required_columns):
        return pd.DataFrame()

    required_my_columns = ["社會住宅", "遞補類型", "房型", "戶別"]
    if any(col not in my_df.columns for col in required_my_columns):
        return pd.DataFrame()

    matched_rows = []

    for _, my_row in my_df.iterrows():
        project_name = my_row.get("社會住宅")
        queue_type = my_row.get("遞補類型")
        room_type = my_row.get("房型")
        household_type = my_row.get("戶別")

        my_priority = PRIORITY_ORDER.get(queue_type)

        candidate_rows = history_df[
            (history_df["社會住宅"] == project_name)
            & (history_df["房型"] == room_type)
            & (history_df["戶別"] == household_type)
        ].copy()

        if candidate_rows.empty:
            continue

        if my_priority is not None:
            candidate_rows["_priority"] = candidate_rows["遞補類型"].map(PRIORITY_ORDER)
            candidate_rows = candidate_rows[
                candidate_rows["_priority"].notna()
                & (candidate_rows["_priority"] <= my_priority)
            ].copy()
            candidate_rows = candidate_rows.drop(columns=["_priority"])
        else:
            candidate_rows = candidate_rows[
                candidate_rows["遞補類型"] == queue_type
            ].copy()

        candidate_rows["對應我的申請"] = (
            f"{project_name}／{queue_type}／{room_type}／{household_type}"
        )

        candidate_rows["名冊"] = (
            candidate_rows["社會住宅"].astype(str)
            + "／"
            + candidate_rows["遞補類型"].astype(str)
            + "／"
            + candidate_rows["房型"].astype(str)
            + "／"
            + candidate_rows["戶別"].astype(str)
        )

        matched_rows.append(candidate_rows)

    if not matched_rows:
        return pd.DataFrame()

    result_df = pd.concat(matched_rows, ignore_index=True)
    result_df = result_df.drop_duplicates()

    result_df["抓取日期"] = pd.to_datetime(
        result_df["抓取日期"],
        errors="coerce",
    )

    result_df = result_df.dropna(subset=["抓取日期"])
    result_df = result_df.sort_values("抓取日期")

    numeric_columns = [
        "已遞補人數",
        "已放棄人數",
        "待遞補人數",
        "名冊總人數",
    ]

    for col in numeric_columns:
        if col in result_df.columns:
            result_df[col] = pd.to_numeric(result_df[col], errors="coerce")

    return result_df

def build_overall_queue_summary(history_df: pd.DataFrame) -> pd.DataFrame:
    """
    建立全部案場目前狀態與歷史變化摘要。

    目前先用每條名冊的最早與最新資料比較：
    - 待遞補人數變化
    - 已遞補人數變化
    - 已放棄人數變化
    """
    if history_df.empty:
        return pd.DataFrame()

    required_columns = ["抓取日期"] + KEY_COLUMNS
    if any(col not in history_df.columns for col in required_columns):
        return pd.DataFrame()

    df = history_df.copy()
    df["抓取日期"] = pd.to_datetime(df["抓取日期"], errors="coerce")
    df = df.dropna(subset=["抓取日期"])
    df = df.sort_values(["社會住宅", "遞補類型", "房型", "戶別", "抓取日期"])

    numeric_columns = [
        "已遞補人數",
        "已放棄人數",
        "待遞補人數",
        "名冊總人數",
        "實際放棄率",
    ]

    for col in numeric_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    rows = []

    for key_values, group in df.groupby(KEY_COLUMNS, dropna=False):
        group = group.sort_values("抓取日期")

        first = group.iloc[0]
        latest = group.iloc[-1]

        row = {
            "社會住宅": latest["社會住宅"],
            "遞補類型": latest["遞補類型"],
            "房型": latest["房型"],
            "戶別": latest["戶別"],
            "最早資料日": first["抓取日期"].strftime("%Y-%m-%d"),
            "最新資料日": latest["抓取日期"].strftime("%Y-%m-%d"),
        }

        for col in numeric_columns:
            if col in df.columns:
                row[f"目前{col}"] = latest.get(col)
                row[f"{col}變化"] = latest.get(col) - first.get(col)

        rows.append(row)

    summary_df = pd.DataFrame(rows)

    if summary_df.empty:
        return summary_df

    sort_column = "待遞補人數變化"
    if sort_column in summary_df.columns:
        summary_df = summary_df.sort_values(sort_column)

    return summary_df

def build_event_summary(event_log_df: pd.DataFrame) -> dict:
    """
    建立事件摘要卡片資料。

    目前摘要重點：
    - 事件總筆數
    - 最新事件日期
    - 待遞補人數淨變動
    - 已遞補人數淨變動
    - 已放棄人數淨變動
    """
    summary = {
        "事件總筆數": 0,
        "最新事件日期": None,
        "待遞補人數淨變動": 0,
        "已遞補人數淨變動": 0,
        "已放棄人數淨變動": 0,
    }

    if event_log_df.empty:
        return summary

    df = event_log_df.copy()

    summary["事件總筆數"] = len(df)

    if "事件日期" in df.columns:
        parsed_dates = pd.to_datetime(df["事件日期"], errors="coerce")
        latest_date = parsed_dates.max()

        if pd.notna(latest_date):
            summary["最新事件日期"] = latest_date.strftime("%Y-%m-%d")

    if "事件類型" not in df.columns or "變動量" not in df.columns:
        return summary

    df["變動量"] = pd.to_numeric(df["變動量"], errors="coerce").fillna(0)

    pending_rows = df[df["事件類型"] == "待遞補人數變化"]
    completed_rows = df[df["事件類型"] == "已遞補人數變化"]
    abandoned_rows = df[df["事件類型"] == "已放棄人數變化"]

    summary["待遞補人數淨變動"] = int(pending_rows["變動量"].sum())
    summary["已遞補人數淨變動"] = int(completed_rows["變動量"].sum())
    summary["已放棄人數淨變動"] = int(abandoned_rows["變動量"].sum())

    return summary

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
event_log_df = load_event_log()

# =========================
# 介面設定
# =========================

st.sidebar.header("顯示設定")

selected_period_label = st.sidebar.selectbox(
    "估算基準",
    list(PERIOD_OPTIONS.keys()),
    index=2,
    help=(
        "營運以來：用案場營運起始日至資料取得日的平均速度估算。"
        "最近一個月／三個月／六個月／一年：用歷史抓取資料在該期間內的推進速度估算。"
    ),
)

tab_my, tab_trends, tab_settings, tab_official, tab_system = st.tabs(
    [
        "🏠 我的申請",
        "📈 變動與趨勢",
        "📝 候補設定",
        "🏢 官方資料",
        "⚙️ 系統資訊",
    ]
)

# =========================
# 我的申請
# =========================

with tab_my:
    st.header("我的遞補總覽")

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

        summary_col1, summary_col2, summary_col3, summary_col4 = st.columns(4)

        application_count = len(dashboard_df)

        waiting_values = pd.to_numeric(
            dashboard_df.get("前面約剩幾位"),
            errors="coerce",
        )

        if waiting_values.dropna().empty:
            min_waiting_text = "無法估算"
        else:
            min_waiting_text = f"{int(waiting_values.min())} 人"

        estimated_dates = pd.to_datetime(
            dashboard_df.get("預估遞補完成日期"),
            errors="coerce",
        )

        if estimated_dates.dropna().empty:
            earliest_estimated_date_text = "無法估算"
        else:
            earliest_estimated_date_text = estimated_dates.min().strftime("%Y-%m-%d")

        my_related_event_log_df = build_my_related_event_log(
            event_log_df=event_log_df,
            my_df=my_df,
        )

        related_event_count = len(my_related_event_log_df)

        with summary_col1:
            st.metric("追蹤申請數", f"{application_count} 筆")

        with summary_col2:
            st.metric("最少前方等待", min_waiting_text)

        with summary_col3:
            st.metric("最早預估日期", earliest_estimated_date_text)

        with summary_col4:
            st.metric("我的相關變動", f"{related_event_count} 筆")

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

with tab_settings:
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
# 變動與趨勢
# =========================

with tab_trends:
    st.header("變動與趨勢")

    with st.expander("全部案場趨勢分析", expanded=False):
        if history_df.empty:
            st.info("目前尚未找到 detail_queue_stats_history.csv。")
        else:
            overall_summary_df = build_overall_queue_summary(history_df)

            if overall_summary_df.empty:
                st.info("目前沒有足夠歷史資料可分析全部案場趨勢。")
            else:
                col1, col2, col3 = st.columns(3)

                with col1:
                    queue_filter_options = ["全部"]
                    if "遞補類型" in overall_summary_df.columns:
                        queue_filter_options.extend(
                            overall_summary_df["遞補類型"].dropna().drop_duplicates().tolist()
                        )

                    overall_queue_filter = st.selectbox(
                        "遞補類型",
                        queue_filter_options,
                        index=0,
                        key="overall_queue_filter",
                    )

                with col2:
                    overall_room_filter = st.selectbox(
                        "房型",
                        ["全部", "一房型", "二房型", "三房型"],
                        index=0,
                        key="overall_room_filter",
                    )

                with col3:
                    overall_household_filter = st.selectbox(
                        "戶別",
                        ["全部", "一般戶", "關懷戶"],
                        index=0,
                        key="overall_household_filter",
                    )

                display_overall_df = overall_summary_df.copy()

                if overall_queue_filter != "全部" and "遞補類型" in display_overall_df.columns:
                    display_overall_df = display_overall_df[
                        display_overall_df["遞補類型"] == overall_queue_filter
                    ]

                if overall_room_filter != "全部" and "房型" in display_overall_df.columns:
                    display_overall_df = display_overall_df[
                        display_overall_df["房型"] == overall_room_filter
                    ]

                if overall_household_filter != "全部" and "戶別" in display_overall_df.columns:
                    display_overall_df = display_overall_df[
                        display_overall_df["戶別"] == overall_household_filter
                    ]

                st.dataframe(
                    display_overall_df,
                    use_container_width=True,
                    hide_index=True,
                )

    with st.expander("我的申請相關趨勢圖", expanded=True):
        if history_df.empty:
            st.info("目前尚未找到 detail_queue_stats_history.csv。")
        elif my_df.empty:
            st.info("目前尚未新增任何候補資料。")
        else:
            my_related_history_df = build_my_related_history(
                history_df=history_df,
                my_df=my_df,
            )

            if my_related_history_df.empty:
                st.info("目前沒有與我的申請相關的歷史統計資料。")
            else:
                trend_metric = st.selectbox(
                    "選擇趨勢指標",
                    [
                        "待遞補人數",
                        "已遞補人數",
                        "已放棄人數",
                        "名冊總人數",
                    ],
                    index=0,
                    key="my_related_trend_metric",
                )

                if trend_metric not in my_related_history_df.columns:
                    st.info(f"歷史資料缺少欄位：{trend_metric}")
                else:
                    trend_df = my_related_history_df[
                        ["抓取日期", "名冊", trend_metric]
                    ].dropna()

                    if trend_df.empty:
                        st.info("目前沒有足夠資料可繪製趨勢圖。")
                    else:
                        chart_df = trend_df.pivot_table(
                            index="抓取日期",
                            columns="名冊",
                            values=trend_metric,
                            aggfunc="last",
                        ).sort_index()

                        st.line_chart(chart_df)

                        st.dataframe(
                            my_related_history_df[
                                available_columns(
                                    my_related_history_df,
                                    [
                                        "抓取日期",
                                        "對應我的申請",
                                        "社會住宅",
                                        "遞補類型",
                                        "房型",
                                        "戶別",
                                        "已遞補人數",
                                        "已放棄人數",
                                        "待遞補人數",
                                        "名冊總人數",
                                        "實際放棄率",
                                    ],
                                )
                            ].sort_values("抓取日期", ascending=False).head(100),
                            use_container_width=True,
                            hide_index=True,
                        )

    with st.expander("我的申請相關變動", expanded=True):
        if event_log_df.empty:
            st.info("目前尚未找到 queue_event_log.csv，或尚未偵測到名冊變動。")
        elif my_df.empty:
            st.info("目前尚未新增任何候補資料。")
        else:
            my_related_event_log_df = build_my_related_event_log(
                event_log_df=event_log_df,
                my_df=my_df,
            )

            if my_related_event_log_df.empty:
                st.info("目前尚未偵測到與我的申請相關的名冊變動。")
            else:
                summary = build_event_summary(my_related_event_log_df)

                col1, col2, col3, col4, col5 = st.columns(5)

                with col1:
                    st.metric("相關事件", f"{summary['事件總筆數']} 筆")

                with col2:
                    st.metric("最新變動日", summary["最新事件日期"] or "無")

                with col3:
                    st.metric("待遞補淨變動", f"{summary['待遞補人數淨變動']} 人")

                with col4:
                    st.metric("已遞補淨變動", f"{summary['已遞補人數淨變動']} 人")

                with col5:
                    st.metric("已放棄淨變動", f"{summary['已放棄人數淨變動']} 人")

                my_event_columns = [
                    "事件日期",
                    "對應我的申請",
                    "社會住宅",
                    "遞補類型",
                    "房型",
                    "戶別",
                    "事件類型",
                    "前次數值",
                    "本次數值",
                    "變動量",
                    "事件描述",
                ]

                st.dataframe(
                    my_related_event_log_df[
                        available_columns(my_related_event_log_df, my_event_columns)
                    ].head(50),
                    use_container_width=True,
                    hide_index=True,
                )

    with st.expander("最近名冊變動", expanded=True):
        if event_log_df.empty:
            st.info("目前尚未找到 queue_event_log.csv，或尚未偵測到名冊變動。")
        else:
            display_event_log_df = event_log_df.copy()

            if "事件日期" in display_event_log_df.columns:
                display_event_log_df["事件日期"] = pd.to_datetime(
                    display_event_log_df["事件日期"],
                    errors="coerce",
                )
                display_event_log_df = display_event_log_df.sort_values(
                    "事件日期",
                    ascending=False,
                )

            event_columns = [
                "事件日期",
                "社會住宅",
                "遞補類型",
                "房型",
                "戶別",
                "事件類型",
                "前次數值",
                "本次數值",
                "變動量",
                "事件描述",
            ]

            st.dataframe(
                display_event_log_df[available_columns(display_event_log_df, event_columns)].head(50),
                use_container_width=True,
                hide_index=True,
            )

with tab_official:
    st.header("官方資料")

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

with tab_system:
    st.header("系統資訊")

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
            {
                "檔案": EVENT_LOG_FILE.name,
                "用途": "名冊變動事件紀錄，用來顯示最近推進、放棄或名冊總數變化",
                "是否存在": EVENT_LOG_FILE.exists(),
    },
        ])

        st.dataframe(
            file_status,
            use_container_width=True,
            hide_index=True,
        )