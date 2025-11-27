import requests, json, re, threading, time
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler
)
from datetime import datetime, timedelta, timezone

# ================= CONFIG =================
BOT_TOKEN = "7717716622:AAH3kFzfE5nTmEfWoGzbDlpgmn56tT49L_o"
CHECK_INTERVAL = 300
UID_FILE = "uids.json"
PORT = 8080
VN_TZ = timezone(timedelta(hours=7))
# =========================================

# ========== FLASK KEEP ALIVE ==========
app_flask = Flask(__name__)

@app_flask.route("/")
def home():
    return "✅ Telegram UID Checker Bot is running!", 200

def run_flask():
    app_flask.run(host="0.0.0.0", port=PORT)

# ========== HỖ TRỢ ==========
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

# ========== TELEGRAM ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot đã sẵn sàng!")

async def theodoi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Ví dụ:\n/theodoi 1000123456789 note=test")
        return

    text = " ".join(context.args)
    uid_match = re.search(r"\d{5,}", text)
    if not uid_match:
        await update.message.reply_text("❗ UID không hợp lệ.")
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
            InlineKeyboardButton("✅ Tiếp tục", callback_data=f"keep_{uid}"),
            InlineKeyboardButton("❌ Dừng", callback_data=f"stop_{uid}")
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
        await update.message.reply_text("📭 Chưa có UID nào.")
        return

    msg = "📋 Danh sách UID:\n\n"
    for uid, info in data.items():
        msg += f"🔹 {uid}: {info['status']} ({info['note']})\n"
    await update.message.reply_text(msg)

# ========== BUTTON ==========
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
            await query.edit_message_text(f"🚫 Đã dừng UID {uid}")

    elif query.data.startswith("keep_"):
        await query.answer("✅ Vẫn theo dõi!", show_alert=True)

# ========== AUTO CHECK (CHẠY BACKGROUND = THREAD, KHÔNG DÙNG ASYNC LOOP) ==========
def auto_check_loop(app):
    while True:
        time.sleep(CHECK_INTERVAL)
        data = load_uids()

        for user_id, uids in data.items():
            for uid, info in list(uids.items()):
                old_status = info["status"]
                note = info["note"]
                new_status = "LIVE" if check_facebook_uid(uid) else "DIE"

                if new_status != old_status:
                    data[user_id][uid]["status"] = new_status
                    save_uids(data)

                    keyboard = InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("✅ Tiếp tục", callback_data=f"keep_{uid}"),
                            InlineKeyboardButton("❌ Dừng", callback_data=f"stop_{uid}")
                        ]
                    ])

                    text = (
                        f"🔔 UID {uid} đổi trạng thái!\n"
                        f"📌 {note}\n"
                        f"📡 {old_status} → {new_status}\n"
                        f"🕒 {now_vn()}"
                    )

                    try:
                        app.bot.send_message(
                            chat_id=int(user_id),
                            text=text,
                            reply_markup=keyboard
                        )
                    except:
                        pass

# ========== MAIN (KHÔNG DÙNG asyncio.run NỮA) ==========
def main():
    # Flask
    threading.Thread(target=run_flask, daemon=True).start()

    # Telegram bot
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("theodoi", theodoi))
    app.add_handler(CommandHandler("danhsach", danhsach))
    app.add_handler(CallbackQueryHandler(handle_buttons))

    # Auto check
    threading.Thread(target=auto_check_loop, args=(app,), daemon=True).start()

    print("✅ BOT ĐÃ CHẠY ỔN ĐỊNH")
    app.run_polling()

if __name__ == "__main__":
    main()
