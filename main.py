import discord
import random
import re
import json
import os
import asyncio
import requests
from discord.ext import commands, tasks
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

# .envファイル読み込み（ローカル用）
load_dotenv()

# ==========================================
# 【重要】ここをあなたのRaw URLに書き換えてください
# ==========================================
JSON_URL = "https://raw.githubusercontent.com/nat21098/discord-song-selector-bot/refs/heads/main/songs.json"

# --- 1. Webサーバー設定 (Renderのスリープ防止用) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- 2. Discord Bot設定 (Intents設定済み) ---
intents = discord.Intents.default()
intents.message_content = True  # メッセージ内容を読み取る許可
intents.members = True          # サーバーメンバー情報の取得許可

bot = commands.Bot(command_prefix='/', intents=intents)

# 難易度の色設定
DIFFICULTY_COLORS = {
    "EASY": 0x66dd11, "NORMAL": 0x33bbee, "HARD": 0xffaa00,
    "EXPERT": 0xee4466, "MASTER": 0xbb33ee, "APPEND": 0xff7dc9,
}
DIFF_MAP = {"e": "EASY", "n": "NORMAL", "h": "HARD", "x": "EXPERT", "m": "MASTER", "a": "APPEND"}

songs_database = []

# GitHubからJSONを読み込む関数
def load_songs_from_github():
    try:
        response = requests.get(JSON_URL)
        if response.status_code == 200:
            raw_data = response.json()
            # JSON形式をプログラム用に変換
            return [{"title": t, "difficulty": k.upper(), "level": v} 
                    for t, info in raw_data.items() if isinstance(info, dict)
                    for k, v in info.items() if k.upper() in DIFFICULTY_COLORS and isinstance(v, int)]
    except Exception as e:
        print(f"JSON読み込みエラー: {e}")
    return []

# 10分ごとに自動更新するタスク
@tasks.loop(minutes=10)
async def update_songs_task():
    global songs_database
    new_data = load_songs_from_github()
    if new_data:
        songs_database = new_data
        print("楽曲データをGitHubから最新に更新しました。")

# 送信用埋め込みメッセージ作成
def create_song_embed(song):
    color = DIFFICULTY_COLORS.get(song["difficulty"], 0x95a5a6)
    content = f"**{song['title']}**\n{song['difficulty']} Lv. {song['level']}"
    return discord.Embed(description=content, color=color)

# --- 3. メッセージ受信イベント ---
@bot.event
async def on_message(message):
    # Bot自身の発言は無視、かつ / で始まらない場合は無視
    if message.author.bot or not message.content.startswith('/'):
        return

    content = message.content.lower().strip()
    print(f"受信したコマンド: {content}") # ログ確認用
    
    # 全抽選
    if content == "/all":
        if songs_database:
            await message.channel.send(embed=create_song_embed(random.choice(songs_database)))
        else:
            await message.channel.send("楽曲データが空か、読み込み中です。")
        return
        
    # 条件抽選 (例: /m26, /30, /h20-25)
    match = re.match(r"^/([a-z]+)?(\d+)?(?:-(\d+)?)?$", content)
    if match:
        d_raw, l1, l2 = match.groups()
        diff = DIFF_MAP.get(d_raw)
        min_l, max_l = 0, 100
        try:
            if l1 and l2: min_l, max_l = sorted([int(l1), int(l2)])
            elif l1 and "-" in content: min_l = int(l1)
            elif l1: min_l = max_l = int(l1)
            elif l2: max_l = int(l2)
            elif not diff: return
        except ValueError:
            return
        
        res = [s for s in songs_database if min_l <= s["level"] <= max_l]
        if diff:
            res = [s for s in res if s["difficulty"] == diff]
        
        if res:
            await message.channel.send(embed=create_song_embed(random.choice(res)))
        else:
            await message.channel.send("条件に合う曲が見つかりませんでした。")

# 起動時の処理
@bot.event
async def on_ready():
    print(f'ログインしました: {bot.user.name}')
    # 自動更新タスクが動いていなければ開始
    if not update_songs_task.is_running():
        update_songs_task.start()

# 実行
if __name__ == "__main__":
    # 初回のデータ読み込み
    songs_database = load_songs_from_github()
    # Webサーバー起動（Render用）
    keep_alive()
    # Bot起動（環境変数からトークン取得）
    token = os.getenv('DISCORD_BOT_TOKEN')
    if token:
        bot.run(token)
    else:
        print("エラー: DISCORD_BOT_TOKEN が設定されていません。")
