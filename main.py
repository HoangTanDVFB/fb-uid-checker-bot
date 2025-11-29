from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import requests

# Hàm check link FB
def check_fb_link(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code == 404 or "content isn’t available" in r.text:
            return "❌ Tài khoản không tồn tại hoặc đã chết"
        else:
            return "✅ Tài khoản còn sống hoặc công khai"
    except:
        return "⚠️ Lỗi khi kết nối đến Facebook"

# Command /check
async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Gửi link Facebook sau lệnh /check")
        return
    url = context.args[0]
    result = check_fb_link(url)
    await update.message.reply_text(result)

# Main
app = ApplicationBuilder().token("BOT_TOKEN").build()
app.add_handler(CommandHandler("check", check))

print("Bot chạy rồi!")
app.run_polling()
