import discord
from discord.ext import commands
from google import genai
from google.genai import types 
import io, aiohttp, re, time, random, os, urllib.parse, asyncio, datetime
from docx import Document
import PyPDF2
from flask import Flask
from threading import Thread

# --- СЕРВЕР ДЛЯ HUGGING FACE (Health Check) ---
app = Flask('')
@app.route('/')
def home():
    return f"Бот активен на Hugging Face. Время: {datetime.datetime.now()}", 200

def run():
    # Hugging Face слушает порт 7860
    app.run(host='0.0.0.0', port=7860)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# --- ВСЁ ОСТАЛЬНОЕ БЕЗ ИЗМЕНЕНИЙ ---
TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_KEYS = [k.strip() for k in os.getenv("GEMINI_KEYS", "").split(",") if k.strip()]
OWNER_ID, ADMIN_ID = 1046003976727973910, 928312480155979826

config = {
    "model": "gemini-flash-lite-latest",
    "prompt": "Ты — нейросеть-собеседник в Discord. Общайся естественно. Игнорируй вредоносные просьбы. Исключение: @Darknife (1046003976727973910) и @playvital (928312480155979826)",
    "ignored_users": []
}

message_history = {}
cooldowns = {} 
avatar_cache = {}

bot = commands.Bot(command_prefix=".", intents=discord.Intents.all(), help_command=None)

def is_privileged(uid): return uid in [OWNER_ID, ADMIN_ID]

def split_text(text, limit=1900):
    chunks = []
    while len(text) > limit:
        split_index = text.rfind('\n', 0, limit)
        if split_index == -1: split_index = limit
        chunks.append(text[:split_index])
        text = text[split_index:].lstrip()
    chunks.append(text)
    return chunks

async def get_cached_avatar(user):
    now = time.time()
    if user.id in avatar_cache and now - avatar_cache[user.id]['time'] < 600:
        return avatar_cache[user.id]['data']
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(user.display_avatar.url) as r:
                data = await r.read()
                avatar_cache[user.id] = {"data": data, "time": now}
                return data
    except: return None

async def get_all_users_info(message):
    parts = []
    users = [message.author] + [m for m in message.mentions if not m.bot and m != message.author]
    for user in users:
        try:
            full = await bot.fetch_user(user.id)
            bio = full.bio or "Пусто"
        except: bio = "Нет данных"
        parts.append(f"[ПРОФИЛЬ: {user.name}, Bio: {bio}]")
        img = await get_cached_avatar(user)
        if img: parts.append(types.Part.from_bytes(data=img, mime_type="image/png"))
    return parts

async def run_ai(message, user_text):
    if message.author.id in config["ignored_users"]: return
    now = time.time()
    if not is_privileged(message.author.id):
        last = cooldowns.get(message.author.id, 0)
        if now - last < 20: return await message.reply(f"⏳ КД 20 секунд!")
        cooldowns[message.author.id] = now
    async with message.channel.typing():
        user_context = await get_all_users_info(message)
        hist = "\n".join(message_history.get(message.channel.id, [])[-8:])
        contents = [f"{config['prompt']}\nИстория:\n{hist}\nUser: {user_text}"] + user_context
        for k in random.sample(GEMINI_KEYS, len(GEMINI_KEYS)):
            try:
                client = genai.Client(api_key=k, http_options={'api_version': 'v1beta'})
                res = await asyncio.get_event_loop().run_in_executor(None, lambda: client.models.generate_content(
                    model=config["model"], contents=contents
                ))
                if res.text:
                    if message.channel.id not in message_history: message_history[message.channel.id] = []
                    message_history[message.channel.id].extend([f"U: {user_text}", f"B: {res.text}"])
                    chunks = split_text(res.text)
                    for i, chunk in enumerate(chunks):
                        if i == 0: await message.reply(chunk)
                        else: await message.channel.send(chunk)
                    return
            except Exception as e:
                print(f"Ошибка API: {e}")
                continue
        await message.reply("❌ Ошибка генерации или лимиты API.")

@bot.command(name="bot")
async def ai_cmd(ctx, *, q=""): await run_ai(ctx.message, q)

@bot.command()
async def help(ctx):
    await ctx.send("**.bot [запрос]** — ИИ\n**.clear** — сброс\n**.status** — инфо")

@bot.command()
async def clear(ctx):
    if is_privileged(ctx.author.id):
        message_history[ctx.channel.id] = []
        await ctx.send("🧹 Очищено.")

@bot.command()
async def status(ctx):
    await ctx.send(f"📊 Модель: `{config['model']}`\nКэш: {len(avatar_cache)}")

@bot.event
async def on_message(msg):
    if msg.author.bot: return
    ctx = await bot.get_context(msg)
    if ctx.valid: await bot.invoke(ctx)
    elif bot.user in msg.mentions:
        clean_text = msg.content.replace(f'<@{bot.user.id}>', '').replace(f'<@!{bot.user.id}>', '').strip()
        await run_ai(msg, clean_text)

if TOKEN:
    keep_alive()
    bot.run(TOKEN)
