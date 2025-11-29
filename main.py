import os
import requests
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import asyncio
import nest_asyncio

# ====== CONFIG ======
TOKEN = os.getenv("BOT_TOKEN")  # đặt biến môi trường
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # https://your-app.onrender.com/webhook
PORT = int(os.environ.get("PORT", 10000))

# ====== FLASK APP ======
app = Flask(__name__)

# ====== TELEGRAM APP ======
telegram_app = Application.builder().token(TOKEN).build()

# ====== TELEGRAM HANDLERS ======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Gửi mình link Facebook để kiểm tra nhé!")

def check_facebook_profile(url: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 404:
            return "❌ Tài khoản không tồn tại."
        if "This Page Isn't Available" in r.text:
            return "⚠️ Profile không hiển thị công khai."
        if r.status_code == 200:
            return "✅ Tài khoản tồn tại & hiển thị công khai."
        return f"⚠️ Không xác định. HTTP {r.status_code}"
    except Exception as e:
        return f"⚠️ Lỗi: {e}"

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not url.startswith("http"):
        await update.message.reply_text("❗ Vui lòng gửi 1 link Facebook.")
        return
    result = check_facebook_profile(url)
    await update.message.reply_text(result)

telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check))

# ====== FLASK WEBHOOK SERVER ======
@app.route("/")
def home():
    return "Telegram bot is running!"

@app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.json, telegram_app.bot)
    telegram_app.update_queue.put_nowait(update)
    return "OK"

# ====== SET WEBHOOK ======
async def setup_webhook():
    await telegram_app.bot.set_webhook(url=WEBHOOK_URL)
    print("Webhook set:", WEBHOOK_URL)

# ====== RUN SERVER ======
if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()  # fix event loop

    # tạo loop và set webhook trước khi chạy
    asyncio.run(setup_webhook())

    telegram_app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=WEBHOOK_URL,
    )
