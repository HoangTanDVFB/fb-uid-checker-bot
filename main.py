import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, CommandHandler, ContextTypes
import cloudscraper
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)

scraper = cloudscraper.create_scraper(
    browser={
        "browser": "chrome",
        "platform": "windows",
        "mobile": False
    }
)

# ================= UTIL =================

def normalize_facebook_url(url):
    if "facebook.com" not in url:
        return None
    return url.strip().split("?")[0]

# ================= CHECK LIVE/DIE =================

def check_facebook_live(url):
    try:
        r = scraper.get(url, timeout=10)

        if r.status_code != 200:
            return "DIE"

        html = r.text

        die_signals = [
            "Sorry, this content isn't available",
            "This Page Isn't Available",
            "Content Not Found",
        ]
        if any(sig in html for sig in die_signals):
            return "DIE"

        soup = BeautifulSoup(html, "html.parser")

        if soup.find("meta", {"property": "al:android:url"}):
            return "LIVE"

        if "profile_id" in html:
            return "LIVE"

        return "UNKNOWN"
    except:
        return "UNKNOWN"

# ================= HANDLERS =================

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

# ================= MAIN =================

def main():
    import os
    BOT_TOKEN = os.getenv("BOT_TOKEN")

    if not BOT_TOKEN:
        print("❌ BOT_TOKEN chưa được set trong Render")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_handler))

    print("Bot is running...")
    app.run_polling()     # ✔ KHÔNG DÙNG async, KHÔNG lỗi loop

if __name__ == "__main__":
    main()
