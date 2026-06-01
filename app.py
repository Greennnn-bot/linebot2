from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import google.genai as genai
import os

app = Flask(__name__)

# ================= 憑證設定 =================
LINE_CHANNEL_ACCESS_TOKEN = '你的_LINE_CHANNEL_ACCESS_TOKEN'
LINE_CHANNEL_SECRET = '你的_LINE_CHANNEL_SECRET'
GEMINI_API_KEY = '你的_GEMINI_API_KEY'

# 初始化 LINE SDK
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 初始化 Gemini SDK
client = genai.Client(api_key=GEMINI_API_KEY)
# ============================================

@app.route("/callback", methods=['POST'])
def callback():
    # 驗證 LINE 的數位簽章，確保請求來自 LINE 官方
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
        
    return 'OK'

# 處理文字訊息的邏輯
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_message = event.message.text
    
    try:
        # 呼叫 Gemini API 生成回應（此處以 gemini-2.5-flash 模型為例）
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=user_message,
        )
        ai_reply = response.text
    except Exception as e:
        print(f"Gemini API 發生錯誤: {e}")
        ai_reply = "對不起，我現在大腦有點混亂，請稍後再試！"

    # 將 Gemini 的回覆透過 LINE 回傳給使用者
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=ai_reply)
    )

# ... 前面的程式碼保持不變 ...

if __name__ == "__main__":
    # Cloud Run 會指定 PORT 環境變數，若沒有則預設 8080
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
