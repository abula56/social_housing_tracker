from datetime import date
from pathlib import Path

import pandas as pd


def read_csv_if_exists(file_path: Path, columns=None) -> pd.DataFrame:
    if file_path.exists():
        return pd.read_csv(file_path)
    return pd.DataFrame(columns=columns or [])


def available_columns(df: pd.DataFrame, columns: list[str]) -> list[str]:
    return [col for col in columns if col in df.columns]


def to_number(value):
    return pd.to_numeric(value, errors="coerce")


def to_timestamp(value):
    return pd.to_datetime(value, errors="coerce")


def format_number(value, digits: int = 1):
    if pd.isna(value) or value is None:
        return None

    try:
        value = float(value)
    except Exception:
        return value

    if abs(value - round(value)) < 0.000001:
        return int(round(value))

    return round(value, digits)


def format_date(value):
    if pd.isna(value) or value is None:
        return None

    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None

    return parsed.strftime("%Y-%m-%d")


def add_processed_count(df: pd.DataFrame) -> pd.DataFrame:
    """
    確保資料裡有「已處理人數」。

    已處理人數 = 已遞補人數 + 已放棄人數
    """
    if df.empty:
        return df

    df = df.copy()

    if "已處理人數" not in df.columns:
        if "已遞補人數" in df.columns and "已放棄人數" in df.columns:
            df["已遞補人數"] = pd.to_numeric(df["已遞補人數"], errors="coerce")
            df["已放棄人數"] = pd.to_numeric(df["已放棄人數"], errors="coerce")
            df["已處理人數"] = df["已遞補人數"] + df["已放棄人數"]

    return df


def latest_row_by_date(df: pd.DataFrame) -> pd.Series | None:
    if df.empty:
        return None

    df = df.copy()

    if "抓取日期" in df.columns:
        df["抓取日期"] = pd.to_datetime(df["抓取日期"], errors="coerce")
        df = df.sort_values("抓取日期")

    return df.iloc[-1]


def get_data_date(status_rows: pd.DataFrame, history_rows: pd.DataFrame):
    dates = []

    if not status_rows.empty and "抓取日期" in status_rows.columns:
        dates.extend(pd.to_datetime(status_rows["抓取日期"], errors="coerce").dropna().tolist())

    if not history_rows.empty and "抓取日期" in history_rows.columns:
        dates.extend(pd.to_datetime(history_rows["抓取日期"], errors="coerce").dropna().tolist())

    if not dates:
        return pd.Timestamp(date.today())

    return max(dates).normalize()


def append_note(original_note, new_note):
    if not new_note:
        return original_note if pd.notna(original_note) else ""

    if pd.isna(original_note) or str(original_note).strip() == "":
        return new_note

    return f"{original_note}；{new_note}"