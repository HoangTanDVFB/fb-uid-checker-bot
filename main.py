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

# ========== FILE UTILS ==========
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

def now_vn():
    return datetime.now(VN_TZ).strftime("%H:%M:%S %d/%m/%Y")

# =====================================================================
# ========== FACEBOOK LIVE/DIE CHECK (ĐÃ THAY TOÀN BỘ CHO MÀY) ==========
# =====================================================================

def build_target_url(target: str):
    target = target.strip()

    if "facebook.com" in target:
        mobile = target.replace("www.facebook.com", "m.facebook.com")
        mobile = mobile.replace("facebook.com", "m.facebook.com")
        return mobile

    if re.fullmatch(r"\d{5,}", target):
        return f"https://m.facebook.com/profile.php?id={target}"

    return f"https://m.facebook.com/{target}"


def check_facebook_live(target: str) -> bool:
    url = build_target_url(target)

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        ),
        "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8"
    }

    try:
        r = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        html = r.text.lower()
    except:
        return False  # Không truy cập được → DIE

    # --- DIE ---
    die_signs = [
        "bạn hiện không xem được nội dung này",
        "this content isn't available",
        "sorry, this content isn't available",
        "nội dung không khả dụng",
        "page isn't available",
        "tài khoản bị vô hiệu hóa",
        "memorialized"
    ]
    for k in die_signs:
        if k in html:
            return False

    # --- LIVE ---
    live_signs = [
        "timeline",
        "profile picture",
        "add friend",
        "thêm bạn bè",
        "theo dõi",
        "followers",
        "bạn bè",
        "about",
        "photos",
        "intro"
    ]
    for k in live_signs:
        if k in html:
            return True

    # Mặc định: mở được trang nhưng ko thấy cảnh báo = LIVE
    return True

# =====================================================================
# ======================= HẾT PHẦN ĐÃ THAY =============================
# =====================================================================


# ========== TELEGRAM COMMANDS ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✅ BOT SẴN SÀNG\n"
        "Dùng: /theodoi link_or_uid note=ghi chú\n"
        "Xem DS: /danhsach"
    )

async def theodoi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "⚠️ Ví dụ:\n/theodoi abc123 note=khách A"
        )
        return

    text = " ".join(context.args)

    note_match = re.search(r"note=(.*)", text)
    note = note_match.group(1).strip() if note_match else "Không có"
    target_raw = re.sub(r"note=.*", "", text).strip()

    if not target_raw:
        await update.message.reply_text("❗ Thiếu link/uid.")
        return

    target = target_raw
    user_id = str(update.effective_user.id)

    data = load_uids()
    if user_id not in data:
        data[user_id] = {}

    status = "LIVE" if check_facebook_live(target) else "DIE"
    data[user_id][target] = {"status": status, "note": note}
    save_uids(data)

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Tiếp tục", callback_data=f"keep_{target}"),
            InlineKeyboardButton("❌ Dừng", callback_data=f"stop_{target}")
        ]
    ])

    msg = (
        f"🔗 Target: {target}\n"
        f"📌 Note: {note}\n"
        f"📡 Trạng thái: {status}\n"
        f"🕒 {now_vn()}"
    )

    await update.message.reply_text(msg, reply_markup=keyboard)

async def danhsach(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_uids().get(user_id, {})

    if not data:
        await update.message.reply_text("📭 Danh sách rỗng.")
        return

    msg = "📋 DANH SÁCH THEO DÕI:\n\n"
    for target, info in data.items():
        msg += f"🔹 {target}: {info['status']} ({info['note']})\n"

    await update.message.reply_text(msg)

# ========== BUTTON ==========
async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = str(query.from_user.id)
    data = load_uids()

    if query.data.startswith("stop_"):
        target = query.data.replace("stop_", "")
        if user_id in data and target in data[user_id]:
            del data[user_id][target]
            save_uids(data)
            await query.edit_message_text(f"🚫 Đã dừng theo dõi {target}")

    elif query.data.startswith("keep_"):
        await query.answer("✅ Tiếp tục theo dõi", show_alert=True)

# ========== AUTO CHECK ==========
def auto_check_loop(app):
    while True:
        time.sleep(CHECK_INTERVAL)
        data = load_uids()

        for user_id, targets in data.items():
            for target, info in list(targets.items()):
                old_status = info["status"]
                note = info.get("note", "")

                new_status = "LIVE" if check_facebook_live(target) else "DIE"

                if new_status != old_status:
                    data[user_id][target]["status"] = new_status
                    save_uids(data)

                    keyboard = InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("✅ Tiếp tục", callback_data=f"keep_{target}"),
                            InlineKeyboardButton("❌ Dừng", callback_data=f"stop_{target}")
                        ]
                    ])

                    text = (
                        f"🔔 ĐỔI TRẠNG THÁI!\n\n"
                        f"🔗 {target}\n"
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

                time.sleep(1.5)  # tránh bị FB block request

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
