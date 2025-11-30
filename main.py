# file: main.py
import os
import re
import requests
from bs4 import BeautifulSoup
from telegram.ext import Application, CommandHandler, MessageHandler, filters


def check_facebook(url: str) -> str:
    """
    Trả về LIVE / DIE / UNKNOWN dựa trên HTML Facebook.
    """

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }

    try:
        res = requests.get(url, headers=headers, timeout=15)
    except Exception:
        return "DIE"

    html = res.text.lower()
    soup = BeautifulSoup(res.text, "html.parser")

    if "bạn hiện không xem được nội dung này" in html:
        return "DIE"

    if (
        soup.find("img")
        and ("nhắn tin" in html or "thêm bạn bè" in html or "bài viết" in html)
    ):
        return "LIVE"

    return "UNKNOWN"


async def start(update, context):
    await update.message.reply_text("Gửi link Facebook để check Live/Die.")


async def handle_message(update, context):
    text = update.message.text.strip()

    match = re.search(r"https?://(www\.)?facebook\.com/[^\s]+", text)
    if not match:
        await update.message.reply_text("Hãy gửi 1 URL Facebook hợp lệ.")
        return

    url = match.group(0)
    await update.message.reply_text("⏳ Đang check...")

    result = check_facebook(url)

    if result == "LIVE":
        await update.message.reply_text("✅ LIVE – Profile hiển thị bình thường.")
    elif result == "DIE":
        await update.message.reply_text("❌ DIE – Trang bị hạn chế / không xem được.")
    else:
        await update.message.reply_text("⚠️ UNKNOWN – Không xác định được.")


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Thiếu TELEGRAM_BOT_TOKEN trong ENV.")

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot is running...")
    app.run_polling()  # ⬅️ FIX: KHÔNG DÙNG allowed_updates


if __name__ == "__main__":
    main()
