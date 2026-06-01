import os
import sys
from flask import Flask, request, abort

# LINE 官方新版 v3 匯入路徑
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

# 改用 Google 官方最新版 SDK 套件
from google import genai

app = Flask(__name__)

# 1. 補齊 LINE 的初始化變數 (你剛剛漏掉了這兩行，導致後面 configuration 崩潰)
configuration = Configuration(access_token=os.environ["LINE_TOKEN"])
handler = WebhookHandler(os.environ["LINE_SECRET"])

# 2. 強制使用新版標準初始化，直接傳入金鑰 (把剛剛重疊的程式碼理乾淨)
client = genai.Client(api_key=os.environ.get("GEMINI_KEY"))

@app.route("/webhook", methods=["POST"])
def callback():
    signature = request.headers.get('X-Line-Signature')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_msg = event.message.text
    
    try:
        # 新版 SDK 呼叫 Gemini 產生內容的標準寫法
        response = client.models.generate_content(
            model='publishers/google/models/gemini-1.5-flash',
            contents=user_msg,
        )
        reply_text = response.text
    except Exception as e:
        print(f"❌ Gemini 呼叫出錯: {e}", file=sys.stderr)
        reply_text = "機器人小幫手目前忙碌中，請稍後再試。"

    # 回覆訊息給使用者
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)]
            )
        )

if __name__ == "__main__":
    # 讓 Render 自動分配 Port 啟動
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
