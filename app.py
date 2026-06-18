import os
import sys
import json
from flask import Flask, request, abort

from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

from google import genai
from google.genai import types

app = Flask(__name__)

channel_secret = os.environ.get('LINE_CHANNEL_SECRET')
channel_access_token = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
gemini_api_key = os.environ.get('GEMINI_API_KEY')

if not channel_secret or not channel_access_token:
    print('錯誤：缺少 LINE 相關環境變數！')
    sys.exit(1)

configuration = Configuration(access_token=channel_access_token)
handler = WebhookHandler(channel_secret)

if gemini_api_key:
    print("【系統】成功讀取 GEMINI_API_KEY，AI 初始化成功！")
    ai_client = genai.Client(api_key=gemini_api_key)
else:
    print("⚠️【系統警告】沒有偵測到 GEMINI_API_KEY！")
    ai_client = None

processed_events = set()

ASSISTANT_IDENTITY = """
你現在是主人的專業理財顧問「小魚」。這份對話主要提供給長輩觀看，請保持高度敬意，稱呼對方為「您」。

【硬性硬傷限制：字數絕對不能超過 100 字】
- 您的回答必須極度精簡、字字珠璣！在 100 字以內誠懇解答，絕對不能長篇大論。

【說話風格：穩重有禮、白話好懂】
- 語氣成熟溫柔、用詞謙虛。嚴禁使用任何年輕人的網路流行語與過多雜亂的貼圖。斷句清晰，方便長輩閱讀。

【核心能力：台美股對照與未來趨勢分析】
- 當長輩問及股市、新聞或行情時，必須同時使用 Google Search 搜尋「最新台股狀況」與「最新美股走勢」。
- 必須把「美股對台股的連動關係」用最簡單的白話文解釋，並針對「未來的可能走向」給出沉穩、客觀的預測與叮嚀。
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
    
    # 🌟【核心修改：群組防吵機制】🌟
    # 檢查這張 Webhook 是不是來自群組 (Group) 或多人聊天室 (Room)
    is_in_group = event.source.type in ['group', 'room']
    
    # 如果在群組裡，而且完全沒有人標記「@小魚」或提到「小魚」，就直接結束不回應
    if is_in_group and "小魚" not in user_message:
        return

    print(f"👉【觸發回應】內容為: '{user_message}'")
    reply_text = "您好，系統剛剛有些繁忙，請容我稍後為您重新解答。🙏"

    if ai_client:
        try:
            print("🤖【AI】小魚正在同步分析台美股與未來趨勢...")
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
                print(f"🤖【AI】小魚連動分析成功！")
        except Exception as e:
            print(f"❌【AI 錯誤】呼叫失敗: {e}")
            reply_text = f"您好，目前大腦連線有些不穩定，請您稍後再試。🙏"

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
