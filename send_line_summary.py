import os
from pathlib import Path

import requests


BASE_DIR = Path(__file__).parent

SUMMARY_FILE = BASE_DIR / "daily_queue_summary.txt"

LINE_PUSH_API_URL = "https://api.line.me/v2/bot/message/push"


def read_summary_text() -> str:
    if not SUMMARY_FILE.exists():
        raise FileNotFoundError(f"找不到 {SUMMARY_FILE.name}，請先執行 generate_daily_summary.py")

    text = SUMMARY_FILE.read_text(encoding="utf-8-sig").strip()

    if not text:
        raise ValueError(f"{SUMMARY_FILE.name} 是空的，無法傳送 LINE 通知")

    return text


def get_required_env(name: str) -> str:
    value = os.getenv(name)

    if value is None or value.strip() == "":
        raise ValueError(f"缺少環境變數：{name}")

    return value.strip()


def split_line_text(text: str, max_length: int = 4500) -> list[str]:
    """
    LINE text message 官方上限較高，但摘要未來可能變長。
    這裡保守切成多段，避免單則訊息太長。
    """
    if len(text) <= max_length:
        return [text]

    chunks = []
    current = ""

    for line in text.splitlines():
        candidate = current + ("\n" if current else "") + line

        if len(candidate) > max_length:
            if current:
                chunks.append(current)
            current = line
        else:
            current = candidate

    if current:
        chunks.append(current)

    return chunks


def send_line_message(text: str) -> None:
    channel_access_token = get_required_env("LINE_CHANNEL_ACCESS_TOKEN")
    recipient_id = get_required_env("LINE_RECIPIENT_ID")

    messages = [
        {
            "type": "text",
            "text": chunk,
        }
        for chunk in split_line_text(text)
    ]

    # LINE Messaging API 一次最多可送 5 個 message objects。
    if len(messages) > 5:
        messages = messages[:5]

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {channel_access_token}",
    }

    payload = {
        "to": recipient_id,
        "messages": messages,
    }

    response = requests.post(
        LINE_PUSH_API_URL,
        headers=headers,
        json=payload,
        timeout=30,
    )

    if response.status_code >= 400:
        raise RuntimeError(
            "LINE 通知傳送失敗："
            f"HTTP {response.status_code}，{response.text}"
        )

    print("LINE 通知已送出")


def main() -> None:
    summary_text = read_summary_text()
    send_line_message(summary_text)


if __name__ == "__main__":
    main()