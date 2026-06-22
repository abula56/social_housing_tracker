from pathlib import Path
from datetime import date
import pandas as pd

BASE_DIR = Path(__file__).parent

MY_APPLICATIONS_FILE = BASE_DIR / "my_applications.csv"
RECORDS_FILE = BASE_DIR / "detail_queue_records.csv"
STATS_FILE = BASE_DIR / "detail_queue_stats.csv"
METADATA_FILE = BASE_DIR / "project_metadata.csv"
PROGRESS_FILE = BASE_DIR / "queue_progress_analysis.csv"

OUTPUT_FILE = BASE_DIR / "my_application_estimates.csv"


def load_csv(file_path):
    if not file_path.exists():
        raise FileNotFoundError(f"找不到檔案：{file_path}")

    return pd.read_csv(file_path)


def estimate_one_application(my_row, records_df, stats_df, metadata_df, progress_df):
    project_name = my_row["社會住宅"]
    room_type = my_row["房型"]
    household_type = my_row["戶別"]
    my_rank = int(my_row["我的候補序號"])

    matched_records = records_df[
        (records_df["社會住宅"] == project_name)
        & (records_df["房型"] == room_type)
        & (records_df["戶別"] == household_type)
    ].copy()

    matched_stats = stats_df[
        (stats_df["社會住宅"] == project_name)
        & (stats_df["房型"] == room_type)
        & (stats_df["戶別"] == household_type)
    ]

    matched_metadata = metadata_df[
        metadata_df["社會住宅"] == project_name
    ]

    matched_progress = progress_df[
        (progress_df["社會住宅"] == project_name)
        & (progress_df["房型"] == room_type)
        & (progress_df["戶別"] == household_type)
    ].copy()

    recent_average_processed_per_week = None
    recent_estimated_weeks = None
    recent_estimated_date = None

    if matched_records.empty:
        return {
            "社會住宅": project_name,
            "房型": room_type,
            "戶別": household_type,
            "我的候補序號": my_rank,
            "我的目前狀態": "找不到名冊資料",
            "前方待遞補人數": None,
            "已處理人數": None,

            "營運以來平均每週推進人數": None,
            "營運以來速度預估剩餘週數": None,
            "營運以來速度預估遞補完成日期": None,

            "最近4次平均推進人數": None,
            "最近速度預估剩餘週數": None,
            "最近速度預估遞補完成日期": None,

            "備註": "detail_queue_records.csv 找不到對應案場、房型、戶別",
        }

    my_record = matched_records[
        matched_records["候補序號"] == my_rank
    ]

    if my_record.empty:
        my_status = "名冊中找不到我的序號"
    else:
        my_status = my_record.iloc[0]["遞補狀態"]

    people_ahead_waiting = matched_records[
        (matched_records["候補序號"] < my_rank)
        & (matched_records["遞補狀態"] == "待遞補")
    ]

    ahead_waiting_count = len(people_ahead_waiting)

    if matched_stats.empty:
        completed_count = None
        abandoned_count = None
        processed_count = None
    else:
        stat_row = matched_stats.iloc[0]
        completed_count = stat_row["已遞補人數"]
        abandoned_count = stat_row["已放棄人數"]
        processed_count = completed_count + abandoned_count

    if matched_metadata.empty:
        average_processed_per_week = None
        estimated_weeks = None
        estimated_date = None
        note = "找不到 project_metadata.csv 的營運開始日"

    else:
        metadata_row = matched_metadata.iloc[0]
        operation_start_date = pd.to_datetime(
            metadata_row["推估用日期"],
            errors="coerce"
        )

        if pd.isna(operation_start_date) or processed_count is None:
            average_processed_per_week = None
            estimated_weeks = None
            estimated_date = None
            note = "營運開始日或已處理人數不足，無法估算日期"

        else:
            today = pd.Timestamp(date.today())
            days_since_start = (today - operation_start_date).days
            weeks_since_start = days_since_start / 7

            if weeks_since_start <= 0 or processed_count <= 0:
                average_processed_per_week = None
                estimated_weeks = None
                estimated_date = None
                note = "營運時間或推進人數不足，無法估算日期"

            else:
                average_processed_per_week = processed_count / weeks_since_start

                if average_processed_per_week <= 0:
                    estimated_weeks = None
                    estimated_date = None
                    note = "平均推進速度為 0，無法估算日期"

                else:
                    estimated_weeks = ahead_waiting_count / average_processed_per_week
                    estimated_date = today + pd.to_timedelta(
                        estimated_weeks,
                        unit="W"
                    )
                    note = ""

                if not matched_progress.empty:
                    matched_progress["抓取日期"] = pd.to_datetime(
                        matched_progress["抓取日期"],
                        errors="coerce"
                    )

                    latest_progress_row = matched_progress.sort_values(
                        "抓取日期"
                    ).iloc[-1]

                    recent_average_processed_per_week = latest_progress_row[
                        "最近4次平均推進人數"
                    ]

                    if pd.isna(recent_average_processed_per_week) or recent_average_processed_per_week <= 0:
                        recent_average_processed_per_week = None
                        recent_estimated_weeks = None
                        recent_estimated_date = None
                    else:
                        recent_estimated_weeks = ahead_waiting_count / recent_average_processed_per_week
                        recent_estimated_date = today + pd.to_timedelta(
                            recent_estimated_weeks,
                            unit="W"
                        )

    return {
        "社會住宅": project_name,
        "房型": room_type,
        "戶別": household_type,
        "我的候補序號": my_rank,
        "我的目前狀態": my_status,
        "前方待遞補人數": ahead_waiting_count,
        "已處理人數": processed_count,

        "營運以來平均每週推進人數": average_processed_per_week,
        "營運以來速度預估剩餘週數": estimated_weeks,
        "營運以來速度預估遞補完成日期": estimated_date.strftime("%Y-%m-%d") if estimated_date is not None else None,

        "最近4次平均推進人數": recent_average_processed_per_week,
        "最近速度預估剩餘週數": recent_estimated_weeks,
        "最近速度預估遞補完成日期": recent_estimated_date.strftime("%Y-%m-%d") if recent_estimated_date is not None else None,

        "備註": note,
    }


def estimate_my_applications():
    my_df = load_csv(MY_APPLICATIONS_FILE)
    records_df = load_csv(RECORDS_FILE)
    stats_df = load_csv(STATS_FILE)
    metadata_df = load_csv(METADATA_FILE)
    progress_df = load_csv(PROGRESS_FILE)

    results = []

    for _, my_row in my_df.iterrows():
        result = estimate_one_application(
            my_row,
            records_df,
            stats_df,
            metadata_df,
            progress_df
        )

        results.append(result)

    result_df = pd.DataFrame(results)

    result_df.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig"
    )

    print("已產生估算結果：", OUTPUT_FILE.resolve())
    print(result_df)

    return result_df


if __name__ == "__main__":
    estimate_my_applications()