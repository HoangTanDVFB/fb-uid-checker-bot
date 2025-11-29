import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Gửi mình link Facebook để kiểm tra nhé!")

def check_facebook_profile(url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:
        r = requests.get(url, headers=headers, timeout=10)

        if r.status_code == 404:
            return "❌ Tài khoản không tồn tại (404)."

        if "This Page Isn't Available" in r.text or "Không hiển thị" in r.text:
            return "⚠️ Tài khoản bị ẩn, bị chặn, hoặc không hiển thị công khai."

        if r.status_code == 200:
            return "✅ Tài khoản đang tồn tại & hiển thị công khai."

        return f"⚠️ Không xác định được. HTTP code: {r.status_code}"

    except Exception as e:
        return f"⚠️ Lỗi: {e}"

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()

    if not url.startswith("http"):
        await update.message.reply_text("❗ Vui lòng gửi 1 link Facebook hợp lệ.")
        return

    result = check_facebook_profile(url)
    await update.message.reply_text(result)

def main():
    TOKEN = "7717716622:AAH3kFzfE5nTmEfWoGzbDlpgmn56tT49L_o"

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("check", check))
    app.add_handler(CommandHandler("", check))  # nhận luôn tin nhắn thường

    print("Bot đang chạy...")
    app.run_polling()

if __name__ == "__main__":
    main()

