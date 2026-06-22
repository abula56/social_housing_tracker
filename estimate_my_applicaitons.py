# -*- coding: utf-8 -*-
"""
estimate_my_applicaitons.py

新版估算程式：支援「遞補類型」。
注意：檔名沿用原專案的拼字 estimate_my_applicaitons.py。

輸入：
- my_applications.csv
- detail_queue_stats.csv
- detail_queue_records.csv

輸出：
- my_application_estimates.csv

核心修正：
1. 主鍵從 ["社會住宅", "房型", "戶別"]
   改為 ["社會住宅", "遞補類型", "房型", "戶別"]。
2. 對「隨到隨辦」新增保守估算：
   若同一社宅、房型、戶別仍有「新案場招租」待遞補，
   則將其列為「前置名冊待遞補人數」。
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd

from constants import (
    KEY_COLUMNS,
    PRIORITY_ORDER,
    PERIOD_OPTIONS,
)


CSV_ENCODING = "utf-8-sig"
BASE_COLUMNS = ["社會住宅", "房型", "戶別"]

# 數字越小，代表越可能要先被消化。
# 目前依臺中社宅實務與你的觀察，先以「新案場招租」優先於「隨到隨辦」處理。

def normalize_text_columns(df: pd.DataFrame) -> pd.DataFrame:
    """清理文字欄位前後空白，避免 merge 因空白失敗。"""
    df = df.copy()
    for col in df.columns:
        if df[col].dtype == "object":
            df[col] = df[col].astype(str).str.strip()
            df.loc[df[col].isin(["nan", "None", "NaT"]), col] = ""
    return df


def read_csv(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"找不到檔案：{path}")
    return normalize_text_columns(pd.read_csv(path, encoding=CSV_ENCODING))


def ensure_columns(df: pd.DataFrame, required: Iterable[str], filename: str) -> None:
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(
            f"{filename} 缺少必要欄位：{missing}\n"
            f"目前欄位：{list(df.columns)}"
        )


def to_number(series: pd.Series, default: int | float = 0) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(default)


def latest_snapshot(df: pd.DataFrame, key_columns: list[str]) -> pd.DataFrame:
    """
    若 history 或 stats 內有多日資料，只保留每組 key 最新一筆。
    若只有單日資料，結果等於原資料。
    """
    df = df.copy()

    if "抓取日期" not in df.columns:
        return df.drop_duplicates(subset=key_columns, keep="last")

    df["_抓取日期_dt"] = pd.to_datetime(df["抓取日期"], errors="coerce")
    df = df.sort_values(["_抓取日期_dt"] + key_columns)
    df = df.drop_duplicates(subset=key_columns, keep="last")
    df = df.drop(columns=["_抓取日期_dt"])
    return df


def current_records_snapshot(records: pd.DataFrame) -> pd.DataFrame:
    """detail_queue_records 只保留最新抓取日期。"""
    records = records.copy()
    if "抓取日期" not in records.columns:
        return records

    records["_抓取日期_dt"] = pd.to_datetime(records["抓取日期"], errors="coerce")
    latest_date = records["_抓取日期_dt"].max()

    if pd.isna(latest_date):
        records = records.drop(columns=["_抓取日期_dt"])
        return records

    records = records[records["_抓取日期_dt"] == latest_date].copy()
    records = records.drop(columns=["_抓取日期_dt"])
    return records


def key_filter(df: pd.DataFrame, values: pd.Series | dict, columns: list[str]) -> pd.Series:
    mask = pd.Series(True, index=df.index)
    for col in columns:
        mask &= df[col].astype(str).str.strip().eq(str(values[col]).strip())
    return mask


def priority_rank(queue_type: str) -> int:
    """
    未知遞補類型放在很後面。
    這樣不會錯把未知類型當成前置名冊。
    """
    return PRIORITY_ORDER.get(str(queue_type).strip(), 999)


def build_preceding_queue_info(
    app_row: pd.Series,
    stats_latest: pd.DataFrame,
) -> tuple[int, str]:
    """
    計算同一社會住宅、房型、戶別中，比我的遞補類型更優先的名冊仍有多少人待遞補。

    例如：
    我的名冊 = 隨到隨辦
    同一社宅/房型/戶別的新案場招租仍有 24 人待遞補
    => 前置名冊待遞補人數 = 24
    """
    current_type = str(app_row["遞補類型"]).strip()
    current_rank = priority_rank(current_type)

    if current_rank == 999:
        return 0, "未知遞補類型，未套用前置名冊估算。"

    same_base = stats_latest[key_filter(stats_latest, app_row, BASE_COLUMNS)].copy()
    if same_base.empty:
        return 0, "查無同案場同房型同戶別統計資料。"

    same_base["_priority_rank"] = same_base["遞補類型"].map(priority_rank)
    preceding = same_base[same_base["_priority_rank"] < current_rank].copy()

    if preceding.empty:
        return 0, "無更優先的前置名冊。"

    preceding["待遞補人數"] = to_number(preceding["待遞補人數"], default=0).astype(int)
    total = int(preceding["待遞補人數"].sum())

    details = []
    for _, row in preceding.sort_values("_priority_rank").iterrows():
        details.append(f"{row['遞補類型']}：{int(row['待遞補人數'])} 人")

    return total, "；".join(details)


def build_one_estimate(
    app_row: pd.Series,
    stats_latest: pd.DataFrame,
    records_current: pd.DataFrame,
) -> dict:
    result = app_row.to_dict()

    my_seq = pd.to_numeric(app_row.get("我的候補序號"), errors="coerce")
    if pd.isna(my_seq):
        my_seq_int = None
    else:
        my_seq_int = int(my_seq)

    # 找本名冊統計
    stat_match = stats_latest[key_filter(stats_latest, app_row, KEY_COLUMNS)].copy()

    if not stat_match.empty:
        stat_row = stat_match.iloc[0].to_dict()
        for col in ["抓取日期", "已遞補人數", "已放棄人數", "待遞補人數", "名冊總人數", "實際放棄率"]:
            result[col] = stat_row.get(col, pd.NA)
    else:
        for col in ["抓取日期", "已遞補人數", "已放棄人數", "待遞補人數", "名冊總人數", "實際放棄率"]:
            result[col] = pd.NA

    # 找本名冊明細
    exact_records = records_current[key_filter(records_current, app_row, KEY_COLUMNS)].copy()

    if not exact_records.empty and "候補序號" in exact_records.columns:
        exact_records["候補序號"] = to_number(exact_records["候補序號"], default=-1).astype(int)

    my_status = "查無此候補序號"
    my_record_found = False
    same_list_ahead_pending = pd.NA
    same_list_pending_total = pd.NA

    if my_seq_int is not None and not exact_records.empty:
        same_list_pending = exact_records[exact_records["遞補狀態"].astype(str).str.contains("待", na=False)]
        same_list_pending_total = int(len(same_list_pending))

        my_record = exact_records[exact_records["候補序號"] == my_seq_int]
        if not my_record.empty:
            my_record_found = True
            my_status = str(my_record.iloc[0].get("遞補狀態", "")).strip() or "狀態空白"

        same_list_ahead_pending = int(
            len(
                same_list_pending[
                    same_list_pending["候補序號"] < my_seq_int
                ]
            )
        )

    elif my_seq_int is not None and exact_records.empty:
        same_list_ahead_pending = pd.NA
        same_list_pending_total = pd.NA

    preceding_pending, preceding_desc = build_preceding_queue_info(app_row, stats_latest)

    if my_status == "已遞補":
        conservative_wait = 0
    elif pd.isna(same_list_ahead_pending):
        conservative_wait = pd.NA
    else:
        conservative_wait = int(same_list_ahead_pending) + int(preceding_pending)

    warnings = []
    if not stat_match.empty and not my_record_found and my_seq_int is not None:
        warnings.append("本名冊統計存在，但明細中查無你的候補序號。請確認 my_applications.csv 的候補序號、房型、戶別、遞補類型是否完全一致。")
    if preceding_pending > 0:
        warnings.append("同案場同房型同戶別仍有更優先名冊待遞補；本工具將其納入保守估算。")
    if stat_match.empty:
        warnings.append("查無本名冊統計資料。請確認 detail_queue_stats.csv 是否已用新版爬蟲重新產生。")

    if preceding_pending > 0 and my_status != "已遞補":
        estimate_note = (
            f"本名冊前方待遞補 {same_list_ahead_pending} 人；"
            f"前置名冊待遞補 {preceding_pending} 人；"
            f"保守估計前方等待 {conservative_wait} 人。"
        )
    elif my_status == "已遞補":
        estimate_note = "明細顯示已遞補。"
    else:
        estimate_note = f"本名冊前方待遞補 {same_list_ahead_pending} 人。"

    result.update(
        {
            "我的目前狀態": my_status,
            "本名冊待遞補總人數": same_list_pending_total,
            "本名冊前方待遞補人數": same_list_ahead_pending,
            "前置名冊待遞補人數": int(preceding_pending),
            "前置名冊說明": preceding_desc,
            "保守估計前方等待人數": conservative_wait,
            "估算說明": estimate_note,
            "資料警告": "；".join(warnings),
        }
    )

    return result


def build_estimates(
    my_applications_path: str | Path = "my_applications.csv",
    stats_path: str | Path = "detail_queue_stats.csv",
    records_path: str | Path = "detail_queue_records.csv",
    output_path: str | Path = "my_application_estimates.csv",
) -> pd.DataFrame:
    apps = read_csv(my_applications_path)
    stats = read_csv(stats_path)
    records = read_csv(records_path)

    ensure_columns(
        apps,
        KEY_COLUMNS + ["我的候補序號"],
        str(my_applications_path),
    )
    ensure_columns(
        stats,
        KEY_COLUMNS + ["抓取日期", "已遞補人數", "已放棄人數", "待遞補人數", "名冊總人數"],
        str(stats_path),
    )
    ensure_columns(
        records,
        KEY_COLUMNS + ["抓取日期", "候補序號", "遞補狀態"],
        str(records_path),
    )

    apps["我的候補序號"] = to_number(apps["我的候補序號"], default=pd.NA)

    for col in ["已遞補人數", "已放棄人數", "待遞補人數", "名冊總人數"]:
        stats[col] = to_number(stats[col], default=0).astype(int)

    stats_latest = latest_snapshot(stats, KEY_COLUMNS)
    records_current = current_records_snapshot(records)

    estimates = []
    for _, app_row in apps.iterrows():
        estimates.append(build_one_estimate(app_row, stats_latest, records_current))

    out = pd.DataFrame(estimates)

    preferred_order = [
        "社會住宅",
        "遞補類型",
        "房型",
        "戶別",
        "我的候補序號",
        "我的目前狀態",
        "本名冊前方待遞補人數",
        "前置名冊待遞補人數",
        "保守估計前方等待人數",
        "本名冊待遞補總人數",
        "抓取日期",
        "已遞補人數",
        "已放棄人數",
        "待遞補人數",
        "名冊總人數",
        "實際放棄率",
        "前置名冊說明",
        "估算說明",
        "資料警告",
        "營運開始日",
        "備註",
    ]
    existing_preferred = [col for col in preferred_order if col in out.columns]
    remaining = [col for col in out.columns if col not in existing_preferred]
    out = out[existing_preferred + remaining]

    output_path = Path(output_path)
    out.to_csv(output_path, index=False, encoding=CSV_ENCODING)
    return out


def main() -> None:
    out = build_estimates()
    print("已產生 my_application_estimates.csv")
    print()
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
