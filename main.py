# file: fb_bot.py
import os
import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

logging.basicConfig(level=logging.INFO)

driver = None   # Global Selenium driver


# ================= SELENIUM SETUP =================

def create_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(options=chrome_options)
    return driver


# ================= FACEBOOK LOGIN =================

def fb_login(driver, email, password):
    driver.get("https://www.facebook.com/login")

    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.ID, "email"))
    )

    driver.find_element(By.ID, "email").send_keys(email)
    driver.find_element(By.ID, "pass").send_keys(password)

    driver.find_element(By.NAME, "login").click()

    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "[role='feed'], a[aria-label='Home']"))
    )

    time.sleep(2)


# ================= LIVE/DIE CHECK =================

def check_live(url: str) -> str:
    global driver

    try:
        driver.get(url)
    except Exception:
        return "UNKNOWN"

    time.sleep(2)
    html = driver.page_source.lower()

    # DIE signals
    die_signals = [
        "content isn't available",
        "page isn't available",
        "may be broken",
        "unavailable",
        "not found"
    ]

    if any(sig in html for sig in die_signals):
        return "DIE"

    # LIVE signals
    if "profile_id" in html or "entity_id" in html:
        return "LIVE"

    try:
        driver.find_element(By.CSS_SELECTOR, "image, img")
        return "LIVE"
    except:
        pass

    return "UNKNOWN"


# ================= TELEGRAM HANDLERS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Gửi link Facebook để check LIVE/DIE bằng session FB thật.")


async def check_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()

    if "facebook.com" not in url:
        await update.message.reply_text("❌ Vui lòng gửi link Facebook hợp lệ.")
        return

    await update.message.reply_text("⏳ Đang check qua session FB thật...")

    try:
        result = check_live(url)
    except Exception as e:
        result = "UNKNOWN"

    if result == "LIVE":
        msg = "🟢 LIVE — Tài khoản tồn tại."
    elif result == "DIE":
        msg = "🔴 DIE — Tài khoản không tồn tại."
    else:
        msg = "⚠️ UNKNOWN — Không xác định được."

    await update.message.reply_text(msg)


# ================= MAIN =================

def main():
    global driver

    BOT_TOKEN = os.getenv("BOT_TOKEN")
    FB_EMAIL = os.getenv("FB_EMAIL")
    FB_PASS = os.getenv("FB_PASS")

    if not BOT_TOKEN or not FB_EMAIL or not FB_PASS:
        print("❌ Thiếu biến môi trường: BOT_TOKEN / FB_EMAIL / FB_PASS")
        return

    print("🚀 Khởi tạo Chrome headless...")
    driver = create_driver()

    print("🔐 Đăng nhập Facebook...")
    fb_login(driver, FB_EMAIL, FB_PASS)

    print("🟢 FB Login OK — Bot sẵn sàng!")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_handler))

    print("🤖 Bot đang chạy…")
    app.run_polling()


if __name__ == "__main__":
    main()
