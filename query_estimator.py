import pandas as pd

from constants import KEY_COLUMNS, PRIORITY_ORDER, PERIOD_OPTIONS
from utils import (
    add_processed_count,
    append_note,
    format_date,
    format_number,
    get_data_date,
    to_number,
)

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