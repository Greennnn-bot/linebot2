from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import anthropic

app = Flask(__name__)

line_bot_api = LineBotApi("j/NbrdJWfa01UVa8wbYgP5hnPfJoopEN/f8c8yhsZrF5muuoNapiMSLca+N/lfGotuLd4xgUaePbGmDCBBNU1YZ7kDAJIXtiwEX/AmIQ8dC3XkDkL8JRDp7QKB1ImiR1nW27ifU/+CGaMFyb8shzOwdB04t89/1O/w1cDnyilFU=")
handler = WebhookHandler("ed59110c3acd37f486606ffd1b930419")
claude = anthropic.Anthropic(api_key=“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")

@app.route("/webhook", methods=["POST"])
def webhook():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    handler.handle(body, signature)
    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_msg = event.message.text
    response = claude.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        messages=[{"role": "user", "content": user_msg}]
    )
    reply = response.content[0].text
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply)
    )

if __name__ == "__main__":
    app.run(port=5000)