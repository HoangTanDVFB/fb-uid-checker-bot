import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes, CommandHandler
import cloudscraper
from bs4 import BeautifulSoup
import re

logging.basicConfig(level=logging.INFO)

scraper = cloudscraper.create_scraper(browser={
    "browser": "chrome",
    "platform": "windows",
    "mobile": False
})

# =============== EXTRACT UID OR CLEAN URL ==================

def normalize_facebook_url(url):
    if "facebook.com" not in url:
        return None
    return url.strip().split("?")[0]

# =============== SCRAPER LIVE/DIE CHECK ==================

def check_facebook_live(url):
    try:
        r = scraper.get(url, timeout=10)

        # DIE nếu status != 200
        if r.status_code != 200:
            return "DIE"

        html = r.text

        # Các dấu hiệu profile không tồn tại
        die_signals = [
            "Sorry, this content isn't available",
            "This content isn't available",
            "This Page Isn't Available",
            "Content Not Found",
        ]
        if any(text in html for text in die_signals):
            return "DIE"

        soup = BeautifulSoup(html, "html.parser")

        # LIVE nếu có meta profile
        if soup.find("meta", {"property": "al:android:url"}):
            return "LIVE"

        # LIVE nếu có profile_id trong html
        if "profile_id" in html:
            return "LIVE"

        # Không chắc chắn → UNKNOWN
        return "UNKNOWN"

    except Exception as e:
        return "UNKNOWN"

# =============== TELEGRAM BOT HANDLERS ==================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Gửi link Facebook để check Live/Die.")

async def check_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    url = update.message.text.strip()
    clean_url = normalize_facebook_url(url)

    if not clean_url:
        await update.message.reply_text("❌ Vui lòng gửi link Facebook hợp lệ.")
        return

    await update.message.reply_text("⏳ Đang check...")

    result = check_facebook_live(clean_url)

    if result == "LIVE":
        msg = "🟢 LIVE — Tài khoản tồn tại."
    elif result == "DIE":
        msg = "🔴 DIE — Tài khoản không tồn tại."
    else:
        msg = "⚠️ UNKNOWN — Không xác định được."

    await update.message.reply_text(msg)

# =============== MAIN BOT ==================

async def main():
    BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_handler))

    print("Bot is running...")
    await app.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
