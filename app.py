from flask import Flask, request, abort

from linebot.v3 import (
    WebhookHandler
)
from linebot.v3.exceptions import (
    InvalidSignatureError
)
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent
)

import sqlite3
import os


DB_FILE = '/tmp/poop_count.db'
app = Flask(__name__)

# 初始化資料庫
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS poop_count (
            chat_id TEXT,
            user_id TEXT,
            count INTEGER,
            PRIMARY KEY (chat_id, user_id)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def get_poop_count(chat_id, user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT count FROM poop_count WHERE chat_id=? AND user_id=?', (chat_id, user_id))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def update_poop_count(chat_id, user_id, increment):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    current = get_poop_count(chat_id, user_id)
    new_count = current + increment
    c.execute('REPLACE INTO poop_count (chat_id, user_id, count) VALUES (?, ?, ?)', (chat_id, user_id, new_count))
    conn.commit()
    conn.close()
    return new_count

def get_user_rank(chat_id, user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT user_id, count FROM poop_count WHERE chat_id=? ORDER BY count DESC', (chat_id,))
    results = c.fetchall()
    conn.close()

    rank = 1
    last_count = None
    same_rank_count = 0

    for i, (uid, cnt) in enumerate(results, 1):
        if cnt != last_count:
            rank = i
            last_count = cnt
        if uid == user_id:
            return rank, cnt

    return None, 0

def get_top_poop_ranking(chat_id, limit=5):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT user_id, count FROM poop_count WHERE chat_id=? ORDER BY count DESC LIMIT ?', (chat_id, limit))
    results = c.fetchall()
    conn.close()
    return results


configuration = Configuration(access_token = 'dqDsuZty5lQq2uM2ULC8SCv2UjQ+7wuImSSJUzgEz9jSp7IY7vYT8SB0EOCN+mV13VdMm44bkeYO/OExQllsLbYpCvTETVCr4dkOcxEV+oS7d6GCmXP6GW102lkTuJYb/zwdqFqx82sBjl2yzsm87gdB04t89/1O/w1cDnyilFU=')
line_handler = WebhookHandler('fbf2fcbc6412b8ed37b3ea35fbb913b0')


@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        line_handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.info("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)

    return 'OK'

@line_handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_id = event.source.user_id
    message_text = event.message.text.strip()
    # 判斷是哪種聊天室
    if event.source.type == "group":
        chat_id = event.source.group_id
    elif event.source.type == "room":
        chat_id = event.source.room_id
    else:
        chat_id = user_id

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)

        # 💩 統計
        if "💩" in message_text:
            count = message_text.count("💩")
            total = update_poop_count(chat_id, user_id, count)
            reply_text = f"你已經拉了 {total} 次 💩！"

        elif message_text in ["第幾名", "排名"]:
            rank, count = get_user_rank(chat_id, user_id)
            # 先取得整個排行榜資料，算總人數
            full_ranking = get_top_poop_ranking(chat_id, limit=100)  # 支援很多人
            total_people = len(full_ranking)

            if rank:
                if rank == 1:
                    reply_text = f"你是這個聊天室的 💩王！拉了 {count} 次 💩，穩坐第一名 🏆"
                elif rank == total_people:
                    reply_text = f"你的腸胃要加油啊，第 {rank} 名，只拉了 {count} 次 💩"
                else:
                    reply_text = f"排第 {rank} 名的，再接再厲 ，總共拉了 {count} 次 💩！"

        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)]
            )
         )

if __name__ == "__main__":
    app.run()
