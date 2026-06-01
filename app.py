import os
import sys
from flask import Flask, request, abort

# 引入 LINE SDK
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage
from linebot.v3.webhooks import MessageEvent, TextMessageContent

# 引入 Gemini SDK (使用最新標準寫法)
import google.generativeai as genai

app = Flask(__name__)

# 1. 讀取 LINE 的環境變數
channel_access_token = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
channel_secret = os.environ.get('LINE_CHANNEL_SECRET')

# 2. 讀取 Gemini 的環境變數
gemini_key = os.environ.get('GEMINI_API_KEY')

# 檢查環境變數是否都有讀到
if not channel_access_token or not channel_secret or not gemini_key:
    print("❌ 錯誤：環境變數設定不完整！請檢查 Render 後台。", file=sys.stderr)

# 初始化 LINE 配置
configuration = Configuration(access_token=channel_access_token)
handler = WebhookHandler(channel_secret)

# 初始化 Gemini 配置
genai.configure(api_key=gemini_key)
model = genai.GenerativeModel('gemini-1.5-flash')

@app.route("/webhook", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature')
    body = request.get_data(as_text=True)
    
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.info("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_msg = event.message.text
    
    try:
        # 呼叫 Gemini 產生回覆
        response = model.generate_content(user_msg)
        reply_text = response.text
    except Exception as e:
        print(f"❌ Gemini 呼叫出錯: {e}", file=sys.stderr)
        reply_text = "系統忙碌中，請稍後再試。"

    # 回傳訊息給使用者
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)]
            )
        )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
