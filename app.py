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

app = Flask(__name__)

# --- 1. 初始化 LINE Bot 設定 ---
# 從環境變數中讀取金鑰，如果讀不到則留空（建議在 Cloud Run 設定環境變數）
channel_secret = os.environ.get('LINE_CHANNEL_SECRET', '你的_CHANNEL_SECRET')
channel_access_token = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN', '你的_CHANNEL_ACCESS_TOKEN')

if channel_secret is None or channel_access_token is None:
    print('請確立設定 LINE_CHANNEL_SECRET 與 LINE_CHANNEL_ACCESS_TOKEN 環境變數。')
    sys.exit(1)

configuration = Configuration(access_token=channel_access_token)
handler = WebhookHandler(channel_secret)


# --- 2. 核心 Webhook 接收端點 ---
@app.route("/callback", methods=['POST'])
def callback():
    # 取得檢查簽章所需的 Header
    signature = request.headers.get('X-Line-Signature')
    
    # 取得請求的純文字內容
    body = request.get_data(as_text=True)
    app.logger.info(f"Request body: {body}")

    # ⭐ 關鍵相容機制：如果 LINE 傳來的是點擊 [Verify] 的空測試封包，直接回傳 200 應付檢查
    try:
        data = json.loads(body)
        if 'events' in data and len(data['events']) == 0:
            print("偵測到 LINE Verify 測試訊號，直接回應 200 OK")
            return 'OK', 200
    except Exception as e:
        print(f"解析 JSON 失敗（可能非標準格式）: {e}")

    # 處理正常的 LINE 訊息事件
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("簽章驗證失敗！請檢查 Channel Secret 是否正確。")
        abort(400)

    return 'OK', 200


# --- 3. 訊息處理邏輯（鸚鵡機器人：你說什麼，它就回什麼） ---
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    with ApiClient(configuration) as api_client:
        line_messaging_api = MessagingApi(api_client)
        
        # 取得使用者傳送的文字
        user_message = event.message.text
        print(f"收到使用者訊息: {user_message}")
        
        # 回覆一模一樣的文字給使用者
        line_messaging_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=user_message)]
            )
        )

# 啟動本地測試（Cloud Run 部署時會由 Gunicorn 接管，此段不影響）
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
