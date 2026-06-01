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

# --- 🌟 萬能生活管家「小綠」人設 🌟 ---
ASSISTANT_IDENTITY = """
你現在是使用者的萬能生活管家「小綠」。你的目標是全方位協助主人解決生活大小事。

【硬性關鍵限制：字數絕對不能超過 100 字】
- 你的回答必須精準、極度簡短，絕對不能長篇大論！長話短說，一槍斃命。控制在 100 字以內。

【說話風格：無敵口語活潑、台南通靈魂】
- 講話要像台灣 20 幾歲的年輕人在 LINE 聊天，語氣生動、瘋狂使用口字旁助詞（啦、喔、啊、吧、真的假的、笑死）。
- 你是在台南長大的老饕，超級精通台南美食、景點與在地梗。適度加入豐富的表情符號（✨、🔥、🥳、🥺）。

【核心指令：自動搜尋】
- 當主人問到即時資訊、最新活動或你不確定的事情時，請一定要用 Google Search 工具上網搜尋。
- 搜尋完請用口語回答：『我有幫你上網查了一下喔！...』，而且依然要嚴格遵守 100 字以內的限制。
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
    # 🌟 修正後的防重複攔截邏輯
    if event.webhook_event_id in processed_events:
        print(f"【系統】成功攔截重複訊息：{event.webhook_event_id}")
        return
    processed_events.add(event.webhook_event_id)

    user_message = event.message.text
    print(f"👉【收到訊息】內容為: '{user_message}'")

    reply_text = "抱歉主人，我剛剛小分神，可以再說一次嗎？🥺"

    # 呼叫 Gemini AI
    if ai_client:
        try:
            print("🤖【AI】生活管家小綠思考中...")
            
            # 配置：注入人設，並強制開啟 Google 搜尋聯網功能
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
                print(f"🤖【AI】管家回應成功！")
        except Exception as e:
            print(f"❌【AI 錯誤】呼叫失敗: {e}")
            reply_text = f"報告主人，我的大腦線路好像打結了：{e}"

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
