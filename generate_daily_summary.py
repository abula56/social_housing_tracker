from pathlib import Path

import pandas as pd

from constants import PRIORITY_ORDER


BASE_DIR = Path(__file__).parent

EVENT_LOG_FILE = BASE_DIR / "queue_event_log.csv"
MY_APPLICATIONS_FILE = BASE_DIR / "my_applications.csv"
SUMMARY_FILE = BASE_DIR / "daily_queue_summary.txt"


def read_csv_if_exists(file_path: Path) -> pd.DataFrame:
    if not file_path.exists():
        return pd.DataFrame()

    return pd.read_csv(file_path, encoding="utf-8-sig")


def build_my_related_event_log(
    event_log_df: pd.DataFrame,
    my_df: pd.DataFrame,
) -> pd.DataFrame:
    if event_log_df.empty or my_df.empty:
        return pd.DataFrame()

    required_columns = ["社會住宅", "遞補類型", "房型", "戶別"]
    if any(col not in event_log_df.columns for col in required_columns):
        return pd.DataFrame()

    if any(col not in my_df.columns for col in required_columns):
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
        result_df = result_df.dropna(subset=["事件日期"])
        result_df = result_df.sort_values("事件日期", ascending=False)

    return result_df


def format_delta(value) -> str:
    try:
        value = int(value)
    except Exception:
        return str(value)

    if value > 0:
        return f"+{value}"

    return str(value)


def build_summary_text(event_log_df: pd.DataFrame, my_df: pd.DataFrame) -> str:
    if event_log_df.empty:
        return "目前尚未偵測到名冊變動。"

    if "事件日期" not in event_log_df.columns:
        return "queue_event_log.csv 缺少事件日期欄位，無法產生每日摘要。"

    event_log_df = event_log_df.copy()
    event_log_df["事件日期"] = pd.to_datetime(
        event_log_df["事件日期"],
        errors="coerce",
    )
    event_log_df = event_log_df.dropna(subset=["事件日期"])

    if event_log_df.empty:
        return "目前尚未偵測到有效日期的名冊變動。"

    latest_date = event_log_df["事件日期"].max()
    latest_date_text = latest_date.strftime("%Y-%m-%d")

    latest_events = event_log_df[
        event_log_df["事件日期"] == latest_date
    ].copy()

    my_related_events = build_my_related_event_log(
        latest_events,
        my_df,
    )

    lines = []
    lines.append(f"臺中社宅候補追蹤每日摘要")
    lines.append(f"日期：{latest_date_text}")
    lines.append("")

    lines.append(f"全部名冊變動：{len(latest_events)} 筆")

    if my_df.empty:
        lines.append("尚未設定我的申請，因此未產生個人相關摘要。")
    elif my_related_events.empty:
        lines.append("我的申請相關變動：0 筆")
    else:
        lines.append(f"我的申請相關變動：{len(my_related_events)} 筆")
        lines.append("")

        for _, row in my_related_events.iterrows():
            description = row.get("事件描述", "")
            delta = format_delta(row.get("變動量", ""))
            event_type = row.get("事件類型", "")

            lines.append(f"- {description}（{event_type}：{delta}）")

    lines.append("")
    lines.append("提醒：本摘要僅依官方名冊資料變動推算，實際遞補仍以官方通知為準。")

    return "\n".join(lines)


def save_summary(text: str) -> None:
    SUMMARY_FILE.write_text(text, encoding="utf-8-sig")


def main() -> None:
    event_log_df = read_csv_if_exists(EVENT_LOG_FILE)
    my_df = read_csv_if_exists(MY_APPLICATIONS_FILE)

    summary_text = build_summary_text(
        event_log_df=event_log_df,
        my_df=my_df,
    )

    save_summary(summary_text)

    print(summary_text)
    print()
    print(f"已產生 {SUMMARY_FILE.name}")


if __name__ == "__main__":
    main()