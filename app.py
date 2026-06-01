import os
import sys
import json
from flask import Flask, request, abort

# 引入 LINE Bot SDK v3
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

# 引入 Gemini AI SDK
from google import genai

app = Flask(__name__)

# --- 1. 初始化設定 ---
channel_secret = os.environ.get('LINE_CHANNEL_SECRET')
channel_access_token = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
gemini_api_key = os.environ.get('GEMINI_API_KEY')

if not channel_secret or not channel_access_token:
    print('錯誤：缺少 LINE 相關環境變數！')
    sys.exit(1)

configuration = Configuration(access_token=channel_access_token)
handler = WebhookHandler(channel_secret)

# 初始化 Gemini
if gemini_api_key:
    print("【系統】成功讀取 GEMINI_API_KEY，AI 初始化成功！")
    ai_client = genai.Client(api_key=gemini_api_key)
else:
    print("⚠️【系統警告】沒有偵測到 GEMINI_API_KEY！")
    ai_client = None

# 用來記錄處理過的 Webhook ID，防止 LINE 重複發送卡死
processed_events = set()

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature')
    body = request.get_data(as_text=True)

    # 應付 LINE 點擊 [Verify] 按鈕
    try:
        data = json.loads(body)
        if 'events' in data and len(data['events']) == 0:
            print("【系統】偵測到 LINE Verify 測試訊號，直接回應 200")
            return 'OK', 200
    except:
        pass

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK', 200

# --- 2. 訊息處理邏輯 ---
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    # 【核心防摔機制 1】攔截 LINE 的重複重試請求
    event_id = event.webhook_event_id
    if event_id in processed_events:
        print(f"【系統】攔截到重複發送的事件: {event_id}，直接跳過不處理。")
        return
    processed_events.add(event_id)

    user_message = event.message.text
    print(f"👉【收到訊息】內容為: '{user_message}'")

    # 預設回覆
    reply_text = "我現在大腦卡住了，請等我一下..."

    # 呼叫 Gemini AI
    if ai_client:
        try:
            print("🤖【AI】正在連線至 Gemini API 產生回應...")
            response = ai_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=user_message,
            )
            if response.text:
                reply_text = response.text
                print(f"🤖【AI】Gemini 回應成功: {reply_text[:20]}...")
        except Exception as e:
            print(f"❌【AI 錯誤】Gemini API 呼叫失敗，原因為: {e}")
            reply_text = f"抱歉，我的 AI 連線失敗：{e}"
    else:
        print("❌【系統錯誤】因為沒有設定 GEMINI_API_KEY，無法呼叫 AI！")
        reply_text = "你目前沒有在 Cloud Run 設定 GEMINI_API_KEY 環境變數喔！"

    # 【核心防摔機制 2】包裹回傳邏輯，就算憑證過期，伺服器也絕對不噴 500
    try:
        with ApiClient(configuration) as api_client:
            line_messaging_api = MessagingApi(api_client)
            line_messaging_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply_text)]
                )
            )
            print("✨【發送】已成功將訊息傳回給手機使用者！")
    except Exception as e:
        print(f"⚠️【LINE 傳送失敗】(可能 Reply Token 已超時失效): {e}")

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
