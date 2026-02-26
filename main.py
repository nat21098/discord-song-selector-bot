import discord
import random
import re
import json
import os
import requests
from discord.ext import commands, tasks
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

load_dotenv()

# ==========================================
# 【変更点】URLを環境変数から読み込むようにしました
# ==========================================
JSON_URL = os.getenv('JSON_URL')

# --- 1. Webサーバー設定 ---
app = Flask('')
@app.route('/')
def home(): return "Bot is running!"
def run(): app.run(host='0.0.0.0', port=8080)
def keep_alive():
    t = Thread(target=run)
    t.start()

# --- 2. Discord Bot設定 ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='/', intents=intents, help_command=None)

DIFFICULTY_COLORS = {
    "EASY": 0x66dd11, "NORMAL": 0x33bbee, "HARD": 0xffaa00,
    "EXPERT": 0xee4466, "MASTER": 0xbb33ee, "APPEND": 0xff7dc9,
}
DIFF_MAP = {"e": "EASY", "n": "NORMAL", "h": "HARD", "x": "EXPERT", "m": "MASTER", "a": "APPEND"}

songs_database = []

def load_songs_from_github():
    # URLが設定されていない場合のチェック
    if not JSON_URL:
        print("エラー: JSON_URL が環境変数に設定されていません。")
        return []
    
    try:
        response = requests.get(JSON_URL)
        if response.status_code == 200:
            raw_data = response.json()
            return [{"title": t, "difficulty": k.upper(), "level": v} 
                    for t, info in raw_data.items() if isinstance(info, dict)
                    for k, v in info.items() if k.upper() in DIFFICULTY_COLORS and isinstance(v, int)]
    except Exception as e:
        print(f"読み込みエラー: {e}")
    return []

@tasks.loop(minutes=1)
async def update_songs_task():
    global songs_database
    new_data = load_songs_from_github()
    if new_data: songs_database = new_data

def create_song_embed(song):
    color = DIFFICULTY_COLORS.get(song["difficulty"], 0x95a5a6)
    content = f"**{song['title']}**\n{song['difficulty']} Lv. {song['level']}"
    return discord.Embed(description=content, color=color)

# --- 3. イベントとコマンド ---

@bot.event
async def on_ready():
    if not update_songs_task.is_running():
        update_songs_task.start()
    print(f'Logged in as {bot.user.name}')

@bot.event
async def on_message(message):
    if message.author.bot or not message.content.startswith('/'):
        return

    content = message.content.lower().strip()

    if content == "/help":
        embed = discord.Embed(title="🎮 スラッシュコマンド一覧", color=0x2ecc71)
        embed.add_field(name="基本", value="`/all` : 全曲から完全ランダム", inline=False)
        embed.add_field(name="難易度指定", value="`/m` : MASTERのみ\n`/x` : EXPERTのみ\n`/h` : HARDのみ", inline=True)
        embed.add_field(name="レベル指定", value="`/26` : Lv26のみ\n`/26-28` : Lv26〜28", inline=True)
        embed.add_field(name="組み合わせ例", value="`/m26` : MASTERのLv26\n`/x27-28` : EXPERTのLv27〜28", inline=False)
        embed.set_footer(text="※すべて半角・スペースなしで入力してください")
        await message.channel.send(embed=embed)
        return

    if content == "/all":
        if songs_database:
            await message.channel.send(embed=create_song_embed(random.choice(songs_database)))
        else:
            await message.channel.send("⚠️ データ読み込み中です。1分ほどお待ちください。")
        return

    match = re.match(r"^/([a-z]+)?(\d+)?(?:-(\d+)?)?$", content)
    if match:
        if not songs_database: return
        d_raw, l1, l2 = match.groups()
        diff = DIFF_MAP.get(d_raw)
        min_l, max_l = 0, 100
        try:
            if l1 and l2: min_l, max_l = sorted([int(l1), int(l2)])
            elif l1 and "-" in content: min_l = int(l1)
            elif l1: min_l = max_l = int(l1)
            elif l2: max_l = int(l2)
            elif not diff: return
        except: return
        
        res = [s for s in songs_database if min_l <= s["level"] <= max_l]
        if diff: res = [s for s in res if s["difficulty"] == diff]
        
        if res:
            await message.channel.send(embed=create_song_embed(random.choice(res)))
        else:
            await message.channel.send("❌ 条件に合う曲がありません。")

if __name__ == "__main__":
    songs_database = load_songs_from_github()
    keep_alive()
    token = os.getenv('DISCORD_BOT_TOKEN')
    if token:
        bot.run(token)
    else:
        print("エラー: DISCORD_BOT_TOKEN が設定されていません。")
