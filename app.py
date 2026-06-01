import os
import sys
import json
from flask import Flask, request, abort

# 引入 LINE Bot SDK v3 相關模組
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

# ⭐ 新增：引入 Google GenAI SDK
from google import genai

app = Flask(__name__)

# --- 1. 初始化 LINE Bot 與 Gemini 設定 ---
channel_secret = os.environ.get('LINE_CHANNEL_SECRET')
channel_access_token = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
gemini_api_key = os.environ.get('GEMINI_API_KEY')  # ⭐ 新增 Gemini 環境變數

if not channel_secret or not channel_access_token:
    print('請確立設定 LINE 相關環境變數。')
    sys.exit(1)

# 初始化 LINE 客户端
configuration = Configuration(access_token=channel_access_token)
handler = WebhookHandler(channel_secret)

# ⭐ 初始化 Gemini 客户端 (會自動讀取 GEMINI_API_KEY 環境變數)
if gemini_api_key:
    ai_client = genai.Client(api_key=gemini_api_key)
else:
    print('警告：未設定 GEMINI_API_KEY，AI 功能將無法運作！')
    ai_client = None


# --- 2. 核心 Webhook 接收端點 ---
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature')
    body = request.get_data(as_text=True)

    # 應付 LINE 點擊 Verify 按鈕的機制
    try:
        data = json.loads(body)
        if 'events' in data and len(data['events']) == 0:
            print("偵測到 LINE Verify 測試訊號，直接回應 200 OK")
            return 'OK', 200
    except Exception as e:
        pass

    # 處理正常的 LINE 訊息事件
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("簽章驗證失敗！")
        abort(400)

    return 'OK', 200


# --- 3. 訊息處理邏輯（串接 Gemini AI 聊天） ---
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_message = event.message.text
    print(f"收到使用者訊息: {user_message}")

    # 預設的回覆內容（萬一 AI 壞掉時的備用訊息）
    reply_text = "抱歉，我現在大腦有點混亂，請稍後再試。"

    # ⭐ 呼叫 Gemini API 產生回應
    if ai_client:
        try:
            # 使用目前最推薦、速度快且免費額度充足的 gemini-2.5-flash 模型
            response = ai_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=user_message,
            )
            if response.text:
                reply_text = response.text
        except Exception as e:
            print(f"Gemini API 呼叫失敗: {e}")
            reply_text = "我的 AI 大腦連線失敗了..."

    # 將 Gemini 的回答傳回給 LINE 使用者
    with ApiClient(configuration) as api_client:
        line_messaging_api = MessagingApi(api_client)
        line_messaging_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)]
            )
        )

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
