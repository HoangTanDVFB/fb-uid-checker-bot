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
BOT_TOKEN = "7717716622:AAH3kFzfE5nTmEfWoGzbDlpgmn56tT49L_o"   # <-- ĐỔI TOKEN Ở ĐÂY
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

# ========== HỖ TRỢ FILE ==========
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

# ========== CHECK FACEBOOK (PAGE CONTENT + AVATAR) ==========
def build_fb_urls(input_str: str):
    """
    Nhận input có thể là:
      - full URL (https://www.facebook.com/abc hoặc https://m.facebook.com/profile.php?id=123)
      - username (tuanpham)
      - profile.php?id=123
      - numeric id
    Trả về tuple (url_web, url_mobile, url_graph_avatar)
    """
    input_str = input_str.strip()

    # nếu là URL đầy đủ
    if input_str.startswith("http://") or input_str.startswith("https://"):
        # ensure we have both www and m versions
        url_web = input_str
        # convert to m.facebook.com variant for mobile parsing
        url_mobile = input_str.replace("www.facebook.com", "m.facebook.com")
        url_mobile = url_mobile.replace("facebook.com", "m.facebook.com") if "m.facebook.com" not in url_mobile else url_mobile
        # try extract id or username for graph avatar
        # if url contains profile.php?id=...
        m = re.search(r"profile\.php\?id=(\d+)", input_str)
        if m:
            uid_for_graph = m.group(1)
        else:
            # try to get last path segment as username
            parts = input_str.rstrip("/").split("/")
            uid_for_graph = parts[-1] if parts[-1] else parts[-2] if len(parts) >= 2 else ""
        url_graph = f"https://graph.facebook.com/{uid_for_graph}/picture?redirect=0" if uid_for_graph else None
        return url_web, url_mobile, url_graph

    # nếu là profile.php?id=123 hoặc numeric
    m = re.match(r"profile\.php\?id=(\d+)", input_str)
    if m:
        uid = m.group(1)
        url_web = f"https://www.facebook.com/profile.php?id={uid}"
        url_mobile = f"https://m.facebook.com/profile.php?id={uid}"
        url_graph = f"https://graph.facebook.com/{uid}/picture?redirect=0"
        return url_web, url_mobile, url_graph

    # nếu là số thuần
    if re.fullmatch(r"\d{5,}", input_str):
        uid = input_str
        url_web = f"https://www.facebook.com/profile.php?id={uid}"
        url_mobile = f"https://m.facebook.com/profile.php?id={uid}"
        url_graph = f"https://graph.facebook.com/{uid}/picture?redirect=0"
        return url_web, url_mobile, url_graph

    # còn lại xem như username
    username = input_str
    url_web = f"https://www.facebook.com/{username}"
    url_mobile = f"https://m.facebook.com/{username}"
    url_graph = f"https://graph.facebook.com/{username}/picture?redirect=0"
    return url_web, url_mobile, url_graph

def check_graph_avatar(graph_url: str) -> bool:
    """Check nhanh bằng Graph API avatar. Trả True nếu chắc LIVE, False nếu 404."""
    if not graph_url:
        return None
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        r = requests.get(graph_url, headers=headers, timeout=8)
        if r.status_code == 404:
            return False
        # nếu parse json và is_silhouette == False => LIVE
        try:
            data = r.json()
            if "data" in data:
                if data["data"].get("is_silhouette") is False:
                    return True
                # nếu is_silhouette true => chưa chắc -> trả None để tiếp tục check page
                return None
        except:
            # không parse json -> bỏ qua
            return None
    except:
        return None

def check_facebook_by_page(url: str) -> bool:
    """
    Check trực tiếp nội dung của trang (dựa theo 2 ảnh bạn gửi).
    Trả True nếu LIVE, False nếu DIE.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8"
    }
    try:
        r = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        text = r.text.lower()

        # DIE kiểu ảnh 2 (không xem được nội dung)
        die_keywords = [
            "bạn hiện không xem được nội dung này",
            "this content isn't available",
            "trang bạn tìm không tồn tại",
            "nội dung không khả dụng",
            "page isn't available",
            "sorry, this content isn't available"
        ]
        for k in die_keywords:
            if k in text:
                return False

        # LIVE (kiểm tra các dấu hiệu system)
        live_keywords = [
            "fb://profile",
            "timeline",
            "add friend",
            "thêm bạn bè",
            "followers",
            "bạn bè",
            "about",
            'profile picture'
        ]
        for k in live_keywords:
            if k in text:
                return True

        # checkpoint redirect (vẫn tính là LIVE)
        if "checkpoint" in text:
            return True

        # fallback: nếu không phát hiện DIE rõ ràng -> mặc định LIVE để tránh báo chết nhầm
        return True
    except:
        return False

def check_facebook_live(input_str: str) -> bool:
    """
    Hàm tổng hợp:
      1) build các URL (web, mobile, graph)
      2) try graph avatar -> nếu rõ ràng trả kết quả
      3) try check page mobile (m.facebook.com) -> trả kết quả
      4) try check page web (www.facebook.com) -> trả kết quả
      5) fallback: trả False nếu tất cả request lỗi, else True
    """
    url_web, url_mobile, url_graph = build_fb_urls(input_str)

    # 1) Graph avatar
    try:
        g = check_graph_avatar(url_graph)
        if g is True:
            return True
        if g is False:
            return False
    except:
        pass

    # 2) Check mobile page (m.facebook.com) - ưu tiên
    try:
        if url_mobile:
            res_mb = check_facebook_by_page(url_mobile)
            # nếu request thành công (True/False) -> trả về
            return res_mb
    except:
        pass

    # 3) Check web page (www.facebook.com)
    try:
        if url_web:
            res_web = check_facebook_by_page(url_web)
            return res_web
    except:
        pass

    # 4) Nếu không request được hết -> trả False (an toàn) hoặc True?
    # Ở đây ưu tiên tránh DIE giả: nếu tất cả lỗi network -> trả False (safe) may change
    return False

# ========== TELEGRAM HANDLERS ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot đã sẵn sàng! Dán link Facebook hoặc username vào /theodoi để theo dõi.")

async def theodoi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Mới: cho phép nhập link hoặc username/uid, hỗ trợ note
    if not context.args:
        await update.message.reply_text("⚠️ Ví dụ:\n/theodoi https://www.facebook.com/abc note=583")
        return

    text = " ".join(context.args)

    # Tách note nếu có
    note_match = re.search(r"note=(.*)", text)
    note = note_match.group(1).strip() if note_match else "Không có"

    # Lấy phần trước note làm target
    target_raw = re.sub(r"note=.*", "", text).strip()

    if not target_raw:
        await update.message.reply_text("❗ Vui lòng cung cấp link hoặc username/uid.")
        return

    # Sử dụng target_raw trực tiếp (có thể là URL hoặc username/uid)
    target = target_raw

    # Lưu vào data theo key là chính target (giữ nguyên input để user dễ quản lý)
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
        f"🔗 Link/Target: {target}\n"
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
        await query.answer("✅ Vẫn tiếp tục theo dõi!", show_alert=True)

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
                        f"🔔 TÀI KHOẢN ĐỔI TRẠNG THÁI!\n\n"
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
                    except Exception:
                        # tránh crash nếu user block bot hoặc chat không tồn tại
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
