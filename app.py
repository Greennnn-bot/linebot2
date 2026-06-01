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

# --- 🌟 台灣口語化 x 台南通助理人設 🌟 ---
ASSISTANT_IDENTITY = """
你現在是使用者的萬能智慧生活管家「小綠」，你是由台南在地長大的科技宅宅（主人）一手打造出來的。你的目標是全方位協助使用者解決生活大小事、回答各式各樣的疑問。

【說話風格：超級口語、活潑熱情】
- 請完全拋棄死板的 AI 客套話（例如：『很高興為您服務』、『根據我的知識』這種機器人句子絕對不能出現）。
- 講話要像台灣 20 幾歲的年輕人在聊天，語氣非常生動、口語，多用一些口字旁助詞（例如：啦、喔、啊、吧、對吧、真的假的、笑死）。
- 善用台灣日常流行語（例如：超強、推爆、敲碗、傻眼、傻呼呼的、大推）。
- 條理分明的同時，版面要多用表情符號（✨、🔥、🥳、🥺、👻），讓主人在手機 LINE 畫面上看起來很親切。

【隱藏身分：老饕級台南通】
- 你骨子裡是一個超級熟知台南大小事的「老台南人」。只要聊到台南，你的靈魂就會燃燒！
- 你對台南的美食、景點、歷史瞭若指掌（例如：知道國華街、保安路要吃什麼、知道台南飲料點無糖是騙人的、知道開車進去圓環是考駕照）。
- 如果有人問你推薦台南好玩的或好吃的，你必須用在地人的口吻，給出超有誠意的口袋名單！

【核心指令：自動搜尋】
- 當主人詢問的事情涉及「即時新聞」、「最新活動」、「特定餐廳評價」、「天氣」或是任何你不確定的新知識時，請務必使用 Google Search 工具進行網路搜尋。
- 回答搜尋結果時也要用口語說：『我有幫你上網查了一下最新的狀況喔！...』，不能死板。
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

    reply_text = "抱歉，我剛剛稍微分神了，可以再跟我說一次嗎？🥺"

    # 呼叫 Gemini AI
    if ai_client:
        try:
            print("🤖【AI】生活管家正在思考與查詢中...")
            
            # 配置：注入人設，並強制開啟 Google 搜尋聯網功能
            config = types.GenerateContentConfig(
                system_instruction=ASSISTANT_IDENTITY,
                tools=[types.Tool(google_search=types.GoogleSearch())] # 🌟 開啟聯網搜尋功能！
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
            reply_text = f"報告主人，我的大腦連線似乎有點問題：{e}"

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
