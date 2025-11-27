import requests, json, asyncio, re, threading
from flask import Flask
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler
)
from datetime import datetime, timedelta, timezone

# --------------------------
BOT_TOKEN = "7717716622:AAH3kFzfE5nTmEfWoGzbDlpgmn56tT49L_o"
CHECK_INTERVAL = 300
UID_FILE = "uids.json"
PORT = 8080
# --------------------------

VN_TZ = timezone(timedelta(hours=7))

app_flask = Flask(__name__)

@app_flask.route("/")
def home():
    return "✅ Telegram UID Checker Bot is running!", 200

def run_flask():
    app_flask.run(host="0.0.0.0", port=PORT)

def load_uids():
    try:
        with open(UID_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_uids(data):
    with open(UID_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def check_facebook_uid(uid: str) -> bool:
    url = f"https://graph.facebook.com/{uid}"
    try:
        r = requests.get(url, timeout=5)
        return r.status_code == 200 and "id" in r.text
    except:
        return False

def now_vn():
    return datetime.now(VN_TZ).strftime("%H:%M:%S %d/%m/%Y")

async def theodoi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Nhập UID cần theo dõi\nVí dụ: /theodoi 1000123456789 note=test")
        return

    text = " ".join(context.args)
    uid_match = re.search(r"\d{5,}", text)
    if not uid_match:
        await update.message.reply_text("❗ Không tìm thấy UID hợp lệ.")
        return

    uid = uid_match.group()
    note_match = re.search(r"note=(.*)", text)
    note = note_match.group(1).strip() if note_match else "Không có"

    user_id = str(update.effective_user.id)
    data = load_uids()
    if user_id not in data:
        data[user_id] = {}

    status = "LIVE" if check_facebook_uid(uid) else "DIE"
    data[user_id][uid] = {"status": status, "note": note}
    save_uids(data)

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Tiếp tục theo dõi", callback_data=f"keep_{uid}"),
            InlineKeyboardButton("❌ Dừng theo dõi", callback_data=f"stop_{uid}")
        ]
    ])

    msg = (
        f"👤 UID: {uid}\n"
        f"📌 Ghi chú: {note}\n"
        f"📡 Trạng thái: {status}\n"
        f"🕒 Thời gian: {now_vn()}"
    )

    await update.message.reply_text(msg, reply_markup=keyboard)

async def danhsach(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_uids().get(user_id, {})
    if not data:
        await update.message.reply_text("📭 Bạn chưa theo dõi UID nào.")
        return

    msg = "📋 Danh sách UID bạn đang theo dõi:\n\n"
    for uid, info in data.items():
        msg += f"🔹 {uid}: {info['status']} ({info['note']})\n"
    await update.message.reply_text(msg)

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    data = load_uids()

    if query.data.startswith("stop_"):
        uid = query.data.replace("stop_", "")
        if user_id in data and uid in data[user_id]:
            del data[user_id][uid]
            save_uids(data)
            await query.edit_message_text(f"🚫 Đã dừng theo dõi UID: {uid}")
        else:
            await query.edit_message_text("❗ UID này không còn trong danh sách.")

async def auto_check(app):
    while True:
        await asyncio.sleep(CHECK_INTERVAL)
        data = load_uids()
        for user_id, uids in data.items():
            for uid, info in list(uids.items()):
                old_status = info["status"]
                note = info.get("note", "Không có")

                new_status = "LIVE" if check_facebook_uid(uid) else "DIE"

                if new_status != old_status:
                    data[user_id][uid]["status"] = new_status
                    save_uids(data)

                    keyboard = InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("✅ Tiếp tục theo dõi", callback_data=f"keep_{uid}"),
                            InlineKeyboardButton("❌ Dừng theo dõi", callback_data=f"stop_{uid}")
                        ]
                    ])

                    text = (
                        f"🔔 UID {uid} đã đổi trạng thái!\n"
                        f"📌 Ghi chú: {note}\n"
                        f"📡 Trạng thái mới: {new_status}\n"
                        f"🕒 Cập nhật: {now_vn()}"
                    )

                    try:
                        await app.bot.send_message(chat_id=int(user_id), text=text, reply_markup=keyboard)
                    except:
                        pass

async def main():
    threading.Thread(target=run_flask).start()

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("theodoi", theodoi))
    app.add_handler(CommandHandler("danhsach", danhsach))
    app.add_handler(CallbackQueryHandler(handle_buttons))

    asyncio.create_task(auto_check(app))
    print("🤖 Bot đang chạy...")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
