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
import threading

# ================= CONFIG =================
BOT_TOKEN = "7717716622:AAH3kFzfE5nTmEfWoGzbDlpgmn56tT49L_o"
CHECK_INTERVAL = 120
UID_FILE = "uids.json"
PORT = 8080
VN_TZ = timezone(timedelta(hours=7))
lock = threading.Lock()
# =========================================

# ========== FLASK KEEP ALIVE ==========
app_flask = Flask(__name__)

@app_flask.route("/")
def home():
    return "✅ Telegram Checker Bot is running!", 200

def run_flask():
    app_flask.run(host="0.0.0.0", port=PORT)

# ========== HỖ TRỢ ==========
def load_uids():
    try:
        with lock:
            with open(UID_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except:
        return {}

def save_uids(data):
    with lock:
        with open(UID_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

def check_facebook_live(uid: str) -> bool:
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 13)",
        "Accept-Language": "vi-VN,vi;q=0.9"
    }

    # ========== CÁCH 1: CHECK AVATAR GRAPH ==========
    try:
        url_avatar = f"https://graph.facebook.com/{uid}/picture?redirect=0"
        r1 = requests.get(url_avatar, headers=headers, timeout=10)
        if r1.status_code == 404:
            return False  # DIE chắc chắn

        data = r1.json()
        if "data" in data:
            if data["data"].get("is_silhouette") == False:
                return True  # LIVE chuẩn
        # nếu silhouette == True → chưa kết luận, xuống bước 2
    except:
        pass

    # ========== CÁCH 2: CHECK BẰNG M.FACEBOOK ==========
    try:
        url_mb = f"https://m.facebook.com/profile.php?id={uid}"
        r2 = requests.get(url_mb, headers=headers, timeout=10, allow_redirects=True)
        text = r2.text.lower()

        # ----- DIE / DEAD -----
        die_keywords = [
            "this content isn't available",
            "tài khoản bị vô hiệu hóa",
            "nội dung không khả dụng",
            "tưởng nhớ",
            "memorialized",
            "page isn't available",
            "content not found"
        ]
        for k in die_keywords:
            if k in text:
                return False

        # ----- LIVE -----
        if f'content="fb://profile/{uid}"' in text:
            return True

        if "add friend" in text or "thêm bạn bè" in text:
            return True

        if "timeline" in text or "bạn bè" in text:
            return True

        # Nếu redirect về checkpoint → vẫn xem là LIVE
        if "checkpoint" in text:
            return True

        # Không thấy dấu hiệu DIE rõ ràng → mặc định LIVE (chống DIE giả)
        return True

    except:
        return False


# ========== TELEGRAM ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot đã sẵn sàng!")

async def theodoi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Ví dụ:\n/theodoi tuanpham note=test")
        return

    text = " ".join(context.args)

    # Nhận UID / username / profile.php?id=
    uid_match = re.search(r"([a-zA-Z0-9\.=_%\-]+)", text)
    if not uid_match:
        await update.message.reply_text("❗ ID không hợp lệ.")
        return

    uid = uid_match.group()
    note_match = re.search(r"note=(.*)", text)
    note = note_match.group(1).strip() if note_match else "Không có"

    user_id = str(update.effective_user.id)
    data = load_uids()
    if user_id not in data:
        data[user_id] = {}

    status = "LIVE" if check_facebook_live(uid) else "DIE"
    data[user_id][uid] = {"status": status, "note": note}
    save_uids(data)

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Tiếp tục", callback_data=f"keep_{uid}"),
            InlineKeyboardButton("❌ Dừng", callback_data=f"stop_{uid}")
        ]
    ])

    msg = (
        f"👤 ID: {uid}\n"
        f"📌 Ghi chú: {note}\n"
        f"📡 Trạng thái: {status}\n"
        f"🕒 Thời gian: {now_vn()}"
    )

    await update.message.reply_text(msg, reply_markup=keyboard)

async def danhsach(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_uids().get(user_id, {})
    if not data:
        await update.message.reply_text("📭 Chưa có mục nào.")
        return

    msg = "📋 Danh sách đang theo dõi:\n\n"
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
            await query.edit_message_text(f"🚫 Đã dừng theo dõi {uid}")

    elif query.data.startswith("keep_"):
        await query.answer("✅ Vẫn tiếp tục theo dõi!", show_alert=True)

# ========== AUTO CHECK ==========
def auto_check_loop(app):
    while True:
        time.sleep(CHECK_INTERVAL)
        data = load_uids()

        for user_id, uids in data.items():
            for uid, info in list(uids.items()):
                old_status = info["status"]
                note = info["note"]
                new_status = "LIVE" if check_facebook_live(uid) else "DIE"

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
                        f"🔔 TÀI KHOẢN ĐỔI TRẠNG THÁI!\n\n"
                        f"👤 {uid}\n"
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

# ========== MAIN ==========
def main():
    threading.Thread(target=run_flask, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("theodoi", theodoi))
    app.add_handler(CommandHandler("danhsach", danhsach))
    app.add_handler(CallbackQueryHandler(handle_buttons))

    threading.Thread(target=auto_check_loop, args=(app,), daemon=True).start()

    print("✅ BOT ĐÃ CHẠY ỔN ĐỊNH")
    app.run_polling()

if __name__ == "__main__":
    main()

