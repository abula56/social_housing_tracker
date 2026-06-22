from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).parent

STATS_HISTORY_FILE = BASE_DIR / "detail_queue_stats_history.csv"
OUTPUT_FILE = BASE_DIR / "queue_progress_analysis.csv"

def load_stats_history():
    if not STATS_HISTORY_FILE.exists():
        raise FileNotFoundError(
            "找不到 detail_queue_stats_history.cvs，請先執行 scrape_all_detail_lists.py"
        )
    
    return pd.read_csv(STATS_HISTORY_FILE)

def analyze_progess():
    history_df = load_stats_history()

    history_df["抓取日期"] = pd.to_datetime(history_df["抓取日期"])

    history_df["已處理人數"] = (
        history_df["已遞補人數"] + history_df["已放棄人數"]
    )

    history_df = history_df.sort_values(
        ["社會住宅", "房型", "戶別", "抓取日期"]
    )

    group_columns = ["社會住宅", "房型", "戶別"]

    history_df["上次已處理人數"] = history_df.groupby(
        group_columns
    )["已處理人數"].shift(1)

    history_df["本週推進人數"] = (
        history_df["已處理人數"] - history_df["上次已處理人數"]
    )

    history_df["最近4次平均推進人數"] = history_df.groupby(
        group_columns
    )["本週推進人數"].transform(
        lambda s:s.rolling(window=4, min_periods=1).mean()
    )

    history_df.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig"
    )

    print("以產生進度分析：", OUTPUT_FILE.resolve())
    print(history_df.tail(20))

    return history_df

if __name__ == "__main__":
    analyze_progess()