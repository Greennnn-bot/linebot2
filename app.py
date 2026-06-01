import os
import sys
from flask import Flask, request, abort

# 使用最穩定的 LINE SDK v2 語法
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

# 使用最經典、絕對不會錯亂的舊版 Gemini 套件
import google.generativeai as genai

app = Flask(__name__)

# 初始化 LINE
line_bot_api = LineBotApi(os.environ.get("LINE_TOKEN"))
handler = WebhookHandler(os.environ.get("LINE_SECRET"))

# 初始化 Gemini (直接定死最安全的傳統寫法)
genai.configure(api_key=os.environ.get("GEMINI_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')

@app.route("/", methods=["POST"])
def callback():
    signature = request.headers.get('X-Line-Signature')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_msg = event.message.text
    try:
        # 最經典的呼叫方式，通吃所有 AQ 開頭的免費與付費金鑰
        response = model.generate_content(user_msg)
        reply_text = response.text
    except Exception as e:
        print(f"❌ Gemini 錯誤: {e}", file=sys.stderr)
        reply_text = "機器人目前維護中，請稍後再試。"

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )

# 為了相容 Vercel 的 WSGI 進入點
import app as application
