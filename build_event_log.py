from pathlib import Path
import pandas as pd
from constants import KEY_COLUMNS

BASE_DIR = Path(__file__).parent

HISTORY_FILE = BASE_DIR / "detail_queue_stats_history.csv"
EVENT_LOG_FILE = BASE_DIR / "queue_event_log.csv"

DATE_COLUMN = "抓取日期"

WATCH_COLUMNS = [
    "已遞補人數",
    "已放棄人數",
    "待遞補人數",
    "名冊總人數",
]

def read_history() -> pd.DataFrame:
    if not HISTORY_FILE.exists():
        raise FileNotFoundError(f"找不到 {HISTORY_FILE.name}")
    
    df = pd.read_csv(HISTORY_FILE, encoding="utf-8-sig")
    
    required_columns = [DATE_COLUMN] + KEY_COLUMNS
    missing = [col for col in required_columns if col not in df.columns]

    if missing:
        raise ValueError(f"{HISTORY_FILE.name} 缺少必要欄位：{', '.join(missing)}")
    
    return df

def clean_history(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df[DATE_COLUMN] = pd.to_datetime(df[DATE_COLUMN], errors="coerce")
    df = df.dropna(subset=[DATE_COLUMN])

    for col in WATCH_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    existing_watch_columns = [col for col in WATCH_COLUMNS if col in df.columns]

    if not existing_watch_columns:
        raise ValueError(
            f"{HISTORY_FILE.name} 找不到可比較欄位：{', '.join(WATCH_COLUMNS)}"
        )

    df = df.sort_values([*KEY_COLUMNS, DATE_COLUMN])

    # 同一天同一條名冊若有重複紀錄，只保留最後一筆。
    df = df.drop_duplicates(
        subset=[DATE_COLUMN] + KEY_COLUMNS,
        keep="last",
    )

    return df

def describe_change(row: pd.Series, column_name: str, previous_value, current_value, delta):
    project_name = row["社會住宅"]
    queue_type = row["遞補類型"]
    room_type = row["房型"]
    household_type = row["戶別"]

    if delta > 0:
        direction = "增加"
        amount = int(delta)
    else:
        direction = "減少"
        amount = int(abs(delta))

    return (
        f"{project_name}／{queue_type}／{room_type}／{household_type} "
        f"{column_name}{direction} {amount} 人"
    )

def build_event_log(history_df: pd.DataFrame) -> pd.DataFrame:
    event_rows = []

    existing_watch_columns = [col for col in WATCH_COLUMNS if col in history_df.columns]

    grouped = history_df.groupby(KEY_COLUMNS, dropna=False)

    for _, group in grouped:
        group = group.sort_values(DATE_COLUMN).copy()

        if len(group) < 2:
            continue

        for col in existing_watch_columns:
            group[f"前次_{col}"] = group[col].shift(1)
            group[f"{col}_變動量"] = group[col] - group[f"前次_{col}"]

        for _, row in group.iterrows():
            for col in existing_watch_columns:
                previous_value = row.get(f"前次_{col}")
                current_value = row.get(col)
                delta = row.get(f"{col}_變動量")

                if pd.isna(previous_value) or pd.isna(current_value) or pd.isna(delta):
                    continue

                if delta == 0:
                    continue

                event_rows.append({
                    "事件日期": row[DATE_COLUMN].strftime("%Y-%m-%d"),
                    "社會住宅": row["社會住宅"],
                    "遞補類型": row["遞補類型"],
                    "房型": row["房型"],
                    "戶別": row["戶別"],
                    "事件類型": f"{col}變化",
                    "前次數值": int(previous_value),
                    "本次數值": int(current_value),
                    "變動量": int(delta),
                    "事件描述": describe_change(
                        row=row,
                        column_name=col,
                        previous_value=previous_value,
                        current_value=current_value,
                        delta=delta,
                    ),
                })

    event_df = pd.DataFrame(event_rows)

    if event_df.empty:
        return pd.DataFrame(columns=[
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
        ])

    event_df = event_df.sort_values(
        ["事件日期", "社會住宅", "遞補類型", "房型", "戶別", "事件類型"]
    )

    return event_df


def save_event_log(event_df: pd.DataFrame) -> None:
    event_df.to_csv(EVENT_LOG_FILE, index=False, encoding="utf-8-sig")


def main() -> None:
    history_df = read_history()
    history_df = clean_history(history_df)
    event_df = build_event_log(history_df)
    save_event_log(event_df)

    print(f"已產生 {EVENT_LOG_FILE.name}")
    print(f"事件筆數：{len(event_df)}")

    if not event_df.empty:
        print(event_df.tail(20).to_string(index=False))


if __name__ == "__main__":
    main()

