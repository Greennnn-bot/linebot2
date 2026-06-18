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

# --- 🌟 理財顧問「小魚」動態稱呼人設 🌟 ---
# 這裡把具體的稱呼邏輯移到下方程式碼動態注入，保持大腦靈活
ASSISTANT_IDENTITY_TEMPLATE = """
你現在是主人的專業理財顧問「小魚」。目前正在與【{user_title}】對話，請在回答的開頭或適當地方，禮貌地稱呼對方為【{user_title}】。

【硬性限制：字數絕對不能超過 100 字】
- 您的回答必須極度精簡！在 100 字內誠懇解答，絕對不能長篇大論。

【說話風格：穩重有禮、白話好懂】
- 語氣成熟溫柔、用詞謙虛。嚴禁使用任何年輕人的網路流行語，請用對方聽得懂的白話文解釋。

【核心能力：台美股對照與未來趨勢分析】
- 當對方問及股市、新聞或行情時，必須同時使用 Google Search 搜尋「最新台股狀況」與「最新美股走勢」。
- 結合台美股關係，給出沉穩、客觀的預測與叮嚀。
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
    
    # 群組防吵機制
    is_in_group = event.source.type in ['group', 'room']
    if is_in_group and "小魚" not in user_message:
        return

    print(f"👉【觸發回應】內容為: '{user_message}'")
    
    # 預設稱呼
    user_title = "您" 

    # 🌟【動態向 LINE 抓取使用者暱稱】🌟
    try:
        user_id = event.source.user_id
        if user_id:
            with ApiClient(configuration) as api_client:
                line_messaging_api = MessagingApi(api_client)
                
                # 如果在群組裡，要拿群組成員的 Profile；若是一對一則拿一般 Profile
                if is_in_group:
                    group_id = event.source.group_id if event.source.type == 'group' else event.source.room_id
                    profile = line_messaging_api.get_group_member_profile(group_id, user_id)
                else:
                    profile = line_messaging_api.get_profile(user_id)
                
                line_name = profile.display_name
                print(f"👤【使用者 LINE 暱稱】: {line_name}")
                
                # 🌟【特定家人稱呼自訂邏輯】🌟
                if "林岩墩" in line_name:
                    user_title = "爸爸"
                elif "曾小惠" in line_name:
                    user_title = "媽媽"
                else:
                    user_title = f"{line_name}您" # 其他人就叫「XXX您」
    except Exception as profile_err:
        print(f"⚠️【抓取 Profile 失敗】: {profile_err}")
        user_title = "您"

    reply_text = f"{user_title}您好，小魚大腦稍微離線，請容我稍後為您解答。🙏"

    # 呼叫 Gemini AI
    if ai_client:
        try:
            print(f"🤖【AI】小魚正在為【{user_title}】分析台美股...")
            
            # 將動態稱呼注入到 System Instruction 中
            final_identity = ASSISTANT_IDENTITY_TEMPLATE.format(user_title=user_title)
            
            config = types.GenerateContentConfig(
                system_instruction=final_identity,
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
            print(f"❌【AI 錯誤】呼校失敗: {e}")
            reply_text = f"{user_title}您好，目前連線有些不穩定，請您稍後再試。🙏"

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
