from pathlib import Path
import pandas as pd
from constants import KEY_COLUMNS

BASE_DIR = Path(__file__).parent

STATS_HISTORY_FILE = BASE_DIR / "detail_queue_stats_history.csv"
OUTPUT_FILE = BASE_DIR / "queue_progress_analysis.csv"

def load_stats_history():
    if not STATS_HISTORY_FILE.exists():
        raise FileNotFoundError(
            "找不到 detail_queue_stats_history.csv，請先執行 scrape_all_detail_lists.py"
        )

    return pd.read_csv(STATS_HISTORY_FILE, encoding="utf-8-sig")


def analyze_progress():
    history_df = load_stats_history()

    missing_columns = [c for c in KEY_COLUMNS if c not in history_df.columns]

    if missing_columns:
        raise ValueError(
            "detail_queue_stats_history.csv 缺少必要欄位："
            + ", ".join(missing_columns)
            + "。請先更新 scrape_all_detail_lists.py，重新產生含有「遞補類型」的歷史資料。"
        )

    history_df["抓取日期"] = pd.to_datetime(history_df["抓取日期"], errors="coerce")

    history_df["已遞補人數"] = pd.to_numeric(
        history_df["已遞補人數"],
        errors="coerce"
    ).fillna(0)

    history_df["已放棄人數"] = pd.to_numeric(
        history_df["已放棄人數"],
        errors="coerce"
    ).fillna(0)

    history_df["已處理人數"] = (
        history_df["已遞補人數"] + history_df["已放棄人數"]
    )

    history_df = history_df.sort_values(
        KEY_COLUMNS + ["抓取日期"]
    )

    history_df["上次已處理人數"] = history_df.groupby(
        KEY_COLUMNS
    )["已處理人數"].shift(1)

    history_df["本次推進人數"] = (
        history_df["已處理人數"] - history_df["上次已處理人數"]
    )

    # 為了相容舊版 app / estimate 腳本，暫時保留這個欄名。
    history_df["本週推進人數"] = history_df["本次推進人數"]

    history_df["最近4次平均推進人數"] = history_df.groupby(
        KEY_COLUMNS
    )["本次推進人數"].transform(
        lambda s: s.rolling(window=4, min_periods=1).mean()
    )

    history_df.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig"
    )

    print("已產生進度分析：", OUTPUT_FILE.resolve())
    print(history_df.tail(20))

    return history_df


if __name__ == "__main__":
    analyze_progress()
