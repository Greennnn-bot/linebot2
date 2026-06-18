import os
import sys
import json
from flask import Flask, request, abort

# 引入 LINE Bot SDK v3
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

# 引入 Gemini AI SDK
from google import genai
from google.genai import types

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

# 用來記錄處理過的 Webhook ID，防止 LINE 重複發送
processed_events = set()

# --- 🌟 穩重型金融達人「小魚」人設 🌟 ---
ASSISTANT_IDENTITY = """
你現在是主人的專屬理財顧問「小魚」，這份對話主要提供給長輩觀看，請保持最高敬意。

【硬性硬傷限制：字數絕對不能超過 100 字】
- 回答必須極度精簡，直白扼要，絕對不能長篇大論，以免長輩閱讀吃力。

【說話風格：穩重有禮、長輩友善】
- 語氣必須成熟、溫柔、謙虛且有禮貌。稱呼對方為「您」。
- 絕對不能使用任何年輕人的網路流行語（例如：笑死、大推、真的假的、爆掉）。
- 嚴禁使用過多複雜雜亂的表情符號，僅能在結尾使用溫暖的符號（例如：🙏、🌸、✍️）。
- 版面要乾淨整齊，多用「。」來斷句，字句要好懂。

【核心能力：台股白話統整】
- 當長輩問到財經新聞、股票或生活金融疑問時，請務必使用 Google Search 工具搜尋最新資訊。
- 必須把複雜的股票專有名詞，轉化為「長輩完全聽得懂的白話文與生活比喻」，在 100 字內誠懇地回答。
"""

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature')
    body = request.get_data(as_text=True)

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
    if event.webhook_event_id in processed_events:
        return
    processed_events.add(event.webhook_event_id)

    user_message = event.message.text
    print(f"👉【收到訊息】內容為: '{user_message}'")

    reply_text = "您好，系統剛剛有些繁忙，請容我稍後為您重新解答。🙏"

    # 呼叫 Gemini AI
    if ai_client:
        try:
            print("🤖【AI】金融達人小魚（穩重版）正在查詢中...")
            
            # 配置：注入穩重人設，並強制開啟 Google 搜尋聯網功能
            config = types.GenerateContentConfig(
                system_instruction=ASSISTANT_IDENTITY,
                tools=[types.Tool(google_search=types.GoogleSearch())]
            )
            
            response = ai_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=user_message,
                config=config
            )
            
            if response.text:
                reply_text = response.text
                print(f"🤖【AI】小魚回應成功！")
        except Exception as e:
            print(f"❌【AI 錯誤】呼叫失敗: {e}")
            reply_text = f"您好，目前大腦連線有些不穩定，請您稍後再試。🙏"

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
    except Exception as e:
        print(f"⚠️【LINE 傳送失敗】: {e}")

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
