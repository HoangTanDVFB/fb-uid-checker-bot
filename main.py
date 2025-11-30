import os
import time
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


logging.basicConfig(level=logging.INFO)


# ===========================
#  FACEBOOK LOGIN
# ===========================
def fb_login(driver, email, password):
    driver.get("https://www.facebook.com/login")
    time.sleep(2)

    # nhập email
    try:
        email_box = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "email"))
        )
        email_box.send_keys(email)
    except:
        raise Exception("❌ Không tìm thấy ô Email — Facebook chặn hoặc UI khác.")

    # nhập pass
    try:
        pass_box = driver.find_element(By.ID, "pass")
        pass_box.send_keys(password)
    except:
        raise Exception("❌ Không tìm thấy ô Password.")

    time.sleep(1)

    # ---- CÁCH 1: BUTTON login mặc định
    try:
        driver.find_element(By.CSS_SELECTOR, "button[name='login']").click()
        logging.info("Login bằng button[name=login]")
    except:
        pass

    # ---- CÁCH 2: DIV login (Render hay gặp)
    try:
        driver.find_element(By.CSS_SELECTOR, "div[role='button'][tabindex='0']").click()
        logging.info("Login bằng div[role=button]")
    except:
        pass

    # ---- CÁCH 3: submit form
    try:
        pass_box.submit()
        logging.info("Login bằng form.submit()")
    except:
        pass

    # chờ vào trang Home
    try:
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "a[aria-label='Home'], [role='feed']")
            )
        )
    except:
        raise Exception("❌ Login fail hoặc bị checkpoint.")

    logging.info("🎉 Login Facebook thành công!")
    time.sleep(2)


# ===========================
# KIỂM TRA LIVE/DIE
# ===========================
def check_profile(driver, url):
    driver.get(url)
    time.sleep(3)

    html = driver.page_source

    if any(sig in html for sig in [
        "This content isn't available",
        "Content Not Found",
        "Page Not Found",
        "Sorry, this content isn't available"
    ]):
        return "DIE"

    if "profile_id" in html or 'Timeline' in html or 'Friends' in html:
        return "LIVE"

    return "UNKNOWN"


# ===========================
# TELEGRAM BOT HANDLERS
# ===========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Gửi link Facebook để kiểm tra LIVE / DIE.")


async def check_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()

    if "facebook.com" not in url:
        await update.message.reply_text("❌ Vui lòng gửi link Facebook hợp lệ.")
        return

    await update.message.reply_text("⏳ Đang kiểm tra...")

    driver = context.bot_data["driver"]
    result = check_profile(driver, url)

    if result == "LIVE":
        msg = "🟢 LIVE — Tài khoản tồn tại."
    elif result == "DIE":
        msg = "🔴 DIE — Tài khoản không tồn tại."
    else:
        msg = "⚠️ UNKNOWN — Không xác định được."

    await update.message.reply_text(msg)


# ===========================
# MAIN — KHỞI ĐỘNG BOT
# ===========================
def main():
    FB_EMAIL = os.getenv("FB_EMAIL")
    FB_PASSWORD = os.getenv("FB_PASSWORD")
    BOT_TOKEN = os.getenv("BOT_TOKEN")

    if not all([FB_EMAIL, FB_PASSWORD, BOT_TOKEN]):
        print("❌ Thiếu FB_EMAIL hoặc FB_PASSWORD hoặc BOT_TOKEN")
        return

    # Khởi tạo Chrome headless
    options = uc.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = uc.Chrome(options=options)

    # Login Facebook
    fb_login(driver, FB_EMAIL, FB_PASSWORD)

    # Telegram bot
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.bot_data["driver"] = driver

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_handler))

    print("🚀 BOT ĐANG CHẠY TRÊN RENDER…")
    app.run_polling()


if __name__ == "__main__":
    main()
