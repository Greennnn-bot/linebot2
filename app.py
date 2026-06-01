import os
import google.generativeai as genai
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage

app = Flask(__name__)

line_bot_api = LineBotApi(os.environ["j/NbrdJWfa01UVa8wbYgP5hnPfJoopEN/f8c8yhsZrF5muuoNapiMSLca+N/lfGotuLd4xgUaePbGmDCBBNU1YZ7kDAJIXtiwEX/AmIQ8dC3XkDkL8JRDp7QKB1ImiR1nW27ifU/+CGaMFyb8shzOwdB04t89/1O/w1cDnyilFU="])
handler = WebhookHandler(os.environ["ed59110c3acd37f486606ffd1b930419"])

genai.configure(api_key=os.environ["AQ.Ab8RN6KMvfom3A3j-C2dXQeXl-Z67yATmm9j2XXiVLe6wG8Q2g"])
model = genai.GenerativeModel("gemini-1.5-flash")

@app.route("/webhook", methods=["POST"])
def webhook():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    handler.handle(body, signature)
    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_msg = event.message.text
    response = model.generate_content(user_msg)
    reply = response.text
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply)
    )

if __name__ == "__main__":
    app.run(port=5000)
