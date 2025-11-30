# file: main.py
import os
import re
import requests
from bs4 import BeautifulSoup
from telegram.ext import Application, CommandHandler, MessageHandler, filters


def check_facebook(url: str) -> str:
    """
    Trả về LIVE / DIE / UNKNOWN dựa trên HTML.
    """

    # Tránh die do Cloudflare → có thể nâng cấp thành cloudscraper nếu cần
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }

    try:
        res = requests.get(url, headers=headers, timeout=15)
    except Exception:
        return "DIE"

    html = res.text.lower()
    soup = BeautifulSoup(res.text, "html.parser")

    # Điều kiện DIE
    if "bạn hiện không xem được nội dung này" in html:
        return "DIE"

    # Điều kiện LIVE (avatar + nút + tên)
    if soup.find("image") or soup.find("img"):
        if "bài viết" in html or "thêm bạn bè" in html or "nhắn tin" in html:
            return "LIVE"

    return "UNKNOWN"


async def start(update, context):
    await update.message.reply_text("Gửi link Facebook để kiểm tra Live/Die.")


async def handle_message(update, context):
    text = update.message.text.strip()

    # Tìm URL Facebook trong message
    match = re.search(r"https?://(www\.)?facebook\.com/[^\s]+", text)
    if not match:
        await update.message.reply_text("Hãy gửi 1 URL Facebook hợp lệ.")
        return

    url = match.group(0)
    await update.message.reply_text("⏳ Đang kiểm tra...")

    result = check_facebook(url)

    if result == "LIVE":
        await update.message.reply_text("✅ LIVE – Profile hiển thị bình thường.")
    elif result == "DIE":
        await update.message.reply_text("❌ DIE – Trang bị hạn chế hoặc không xem được.")
    else:
        await update.message.reply_text("⚠️ UNKNOWN – Không xác định được trạng thái.")


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Thiếu TELEGRAM_BOT_TOKEN trong environment variables")

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()


if __name__ == "__main__":
    main()

