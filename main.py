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

load_dotenv()

# --- 1. 設定項目（ここを自分のものに書き換える） ---
# GitHubでsongs.jsonを開き、「Raw」ボタンを押した先のURLを貼ってください
JSON_URL = "https://raw.githubusercontent.com/nat21098/discord-song-selector-bot/refs/heads/main/songs.json?token=GHSAT0AAAAAADWMJMUYSHPBCEHUKZHB5U622M7VWIA"

# --- 2. Webサーバー設定 (Renderのスリープ防止用) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- 3. Discord Bot設定 ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='/', intents=intents)

DIFFICULTY_COLORS = {
    "EASY": 0x66dd11, "NORMAL": 0x33bbee, "HARD": 0xffaa00,
    "EXPERT": 0xee4466, "MASTER": 0xbb33ee, "APPEND": 0xff7dc9,
}
DIFF_MAP = {"e": "EASY", "n": "NORMAL", "h": "HARD", "x": "EXPERT", "m": "MASTER", "a": "APPEND"}

songs_database = []

def load_songs_from_github():
    try:
        response = requests.get(JSON_URL)
        if response.status_code == 200:
            raw_data = response.json()
            return [{"title": t, "difficulty": k.upper(), "level": v} 
                    for t, info in raw_data.items() if isinstance(info, dict)
                    for k, v in info.items() if k.upper() in DIFFICULTY_COLORS and isinstance(v, int)]
    except Exception as e:
        print(f"Data Update Error: {e}")
    return []

@tasks.loop(minutes=10)
async def update_songs_task():
    global songs_database
    new_data = load_songs_from_github()
    if new_data:
        songs_database = new_data
        print("Songs database updated from GitHub.")

def create_song_embed(song):
    color = DIFFICULTY_COLORS.get(song["difficulty"], 0x95a5a6)
    content = f"**{song['title']}**\n{song['difficulty']} Lv. {song['level']}"
    return discord.Embed(description=content, color=color)

@bot.event
async def on_message(message):
    if message.author.bot or not message.content.startswith('/'): return
    content = message.content.lower().strip()
    
    if content == "/all":
        if songs_database: await message.channel.send(embed=create_song_embed(random.choice(songs_database)))
        return
        
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
        except ValueError: return
        
        res = [s for s in songs_database if min_l <= s["level"] <= max_l]
        if diff: res = [s for s in res if s["difficulty"] == diff]
        if res: await message.channel.send(embed=create_song_embed(random.choice(res)))

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    if not update_songs_task.is_running():
        update_songs_task.start()

# 起動処理
if __name__ == "__main__":
    songs_database = load_songs_from_github()
    keep_alive() # Webサーバー起動
    bot.run(os.getenv('DISCORD_BOT_TOKEN'))
