# app.py
# Telegram Bot + Facebook Graph API (public info only)
# Why: FastAPI dễ làm webhook cho Render

import os
import requests
from fastapi import FastAPI
from fastapi import Request

BOT_TOKEN = os.getenv("BOT_TOKEN")
FB_TOKEN = os.getenv("FB_TOKEN")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
FB_API_URL = "https://graph.facebook.com"

app = FastAPI()


def send_message(chat_id: int, text: str) -> None:
    """Why: Tách hàm để dễ tái sử dụng khi gửi tin nhắn."""
    requests.post(TELEGRAM_API, json={"chat_id": chat_id, "text": text})


def get_facebook_public_info(user_id: str) -> dict:
    """Why: Chỉ truy vấn thông tin PUBLIC, đúng chính sách Facebook."""
    url = f"{FB_API_URL}/{user_id}"
    params = {
        "fields": "id,name,picture",
        "access_token": FB_TOKEN,
    }
    response = requests.get(url, params=params)
    return response.json()


@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()

    if "message" not in data:
        return {"ok": True}

    message = data["message"]
    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip()

    if not text:
        send_message(chat_id, "Vui lòng nhập Facebook ID hoặc username.")
        return {"ok": True}

    fb_data = get_facebook_public_info(text)

    if "error" in fb_data:
        send_message(chat_id, "Không tìm thấy thông tin công khai hoặc ID không hợp lệ.")
        return {"ok": True}

    reply = (
        f"📌 *Thông tin công khai Facebook*\n"
        f"- ID: {fb_data.get('id')}\n"
        f"- Tên: {fb_data.get('name')}\n"
        f"- Ảnh: {fb_data['picture']['data']['url']}"
    )

    send_message(chat_id, reply)
    return {"ok": True}
