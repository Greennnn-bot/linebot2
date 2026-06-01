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
    print("成功讀取 GEMINI_API_KEY，AI 初始化中...")
    ai_client = genai.Client(api_key=gemini_api_key)
else:
    print("⚠️ 警告：沒有偵測到 GEMINI_API_KEY，將使用備用回覆。")
    ai_client = None

# 用來記錄處理過的 Webhook ID，防止重複處理
processed_intents = set()

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature')
    body = request.get_data(as_text=True)

    # 應付 LINE 點擊 [Verify] 按鈕
    try:
        data = json.loads(body)
        if 'events' in data and len(data['events']) == 0:
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
    # 防止重複事件處理（LINE 重試機制攔截）
    event_id = event.webhook_event_id
    if event_id in processed_intents:
        print(f"攔截到重複的 LINE 請求: {event_id}，跳過處理。")
        return
    processed_intents.add(event_id)

    user_message = event.message.text
    print(f"【開始處理】收到訊息: {user_message}")

    reply_text = "我現在正在思考，請稍等我一下喔！"

    # 呼叫 Gemini AI
    if ai_client:
        try:
            print("正在連線至 Gemini API...")
            response = ai_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=user_message,
            )
            if response.text:
                reply_text = response.text
        except Exception as e:
            print(f"❌ Gemini AI 呼叫失敗: {e}")
            reply_text = "糟了，我的 AI 大腦暫時連不上線..."
    else:
        reply_text = f"你剛剛說的是：「{user_message}」嗎？（提示：Cloud Run 尚未設定 GEMINI_API_KEY）"

    # 回傳給 LINE 使用者
    try:
        with ApiClient(configuration) as api_client:
            line_messaging_api = MessagingApi(api_client)
            line_messaging_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply_text)]
                )
            )
            print("【發送成功】已將回應傳給使用者。")
    except Exception as e:
        # 如果 Token 過期或重複發送，這裡會抓住，不會讓整個 App 噴 500 錯誤
        print(f"⚠️ LINE 回覆失敗（可能 Reply Token 超時）: {e}")

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
