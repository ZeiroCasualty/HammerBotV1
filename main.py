import discord
from discord import app_commands
from discord.ext import commands
from flask import Flask
from threading import Thread
import aiohttp
import asyncio
import os
import time
from datetime import datetime
from dotenv import load_dotenv

# --- Load Environment Variables ---
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

# --- Flask App for Railway + Zapier Integration ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

@app.route('/run', methods=['GET'])
def run_task():
    """Triggered by Zapier to send daily tasks."""
    if is_weekday():
        try:
            asyncio.run_coroutine_threadsafe(send_tasks_to_channel(), bot.loop)
            asyncio.run_coroutine_threadsafe(send_tasks_to_members(), bot.loop)
            return "Tasks sent successfully!", 200
        except Exception as e:
            return f"Error: {str(e)}", 500
    else:
        return "No tasks today (weekend).", 200

def run_flask():
    app.run(host="0.0.0.0", port=8080)

Thread(target=run_flask).start()

# --- Discord Bot Setup ---
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# --- Task Config ---
channel_id = 1298102437659414528  # Channel for task posts

members_info = {
    1297751702019113081: "Yasmin",
    182703599397240832: "Bernard",
    1297750232745902196: "Dani",
    1297749519559299102: "Justin",
    1297749741190385736: "Jen",
    1297749740489936939: "Jessa",
    1297752200767868993: "Darling",
    1297749642230104125: "Cris",
    1315867037003944000: "Jonathan",
    744792475696365580: "Kirby",
}

members_tasks = {
    1297751702019113081: ["Cook - Lunch", "Wash Dishes - Breakfast", "Cook - Breakfast", "Organize Dishes / Cook Rice", "Cook - Breakfast"],
    182703599397240832: ["Wash Dishes - Lunch (Indoor)", "Sweep Floor", "Wash Dishes - Lunch (Outdoor)", "Wash Dishes - EOD", "Set/Clean Table/Leftovers"],
    1297750232745902196: ["Organize Dishes / Cook Rice", "Cook - Breakfast", "Cook - Lunch", "Cook - Breakfast", "Cook - Lunch"],
    1297749519559299102: ["Wash Dishes - Breakfast", "Refill Officer", "Wash Dishes - Lunch (Indoor)", "Sweep Floor", "Wash Dishes - Lunch (Outdoor)"],
    1297749741190385736: ["Sweep Floor", "Organize Dishes / Cook Rice", "Wash Dishes - Breakfast", "Set/Clean Table/Leftovers", "Wash Dishes - Lunch (Indoor)"],
    1297749740489936939: ["Set/Clean Table/Leftovers", "Wash Dishes - Lunch (Outdoor)", "Refill Officer", "Wash Dishes - Breakfast", "Organize Dishes / Cook Rice"],
    1297752200767868993: ["Cook - Breakfast", "Cook - Lunch", "Organize Dishes / Cook Rice", "Cook - Lunch", "Refill Officer"],
    1297749642230104125: ["Refill Officer", "Wash Dishes - EOD", "Set/Clean Table/Leftovers", "Wash Dishes - Lunch (Outdoor)", "Sweep Floor"],
    1315867037003944000: ["Wash Dishes - Lunch (Outdoor)", "Wash Dishes - Lunch (Indoor)", "Sweep Floor", "Refill Officer", "Wash Dishes - EOD"],
    744792475696365580: ["Wash Dishes - EOD", "Set/Clean Table/Leftovers", "Wash Dishes - EOD", "Wash Dishes - Lunch (Indoor)", "Wash Dishes - Breakfast"],
}

def is_weekday():
    return datetime.today().weekday() < 5

async def send_tasks_to_channel():
    channel = bot.get_channel(channel_id)
    if channel:
        day = datetime.today().strftime("%A")
        day_index = datetime.today().weekday()
        msg = f"Good morning, today is {day}.\nHere are your daily tasks:\n\n"
        for uid, tasks in members_tasks.items():
            if day_index < len(tasks):
                name = members_info.get(uid, "Unknown")
                msg += f"{name}: {tasks[day_index]}\n"
        await channel.send(msg)

async def send_tasks_to_members():
    day_index = datetime.today().weekday()
    for uid, tasks in members_tasks.items():
        if day_index < len(tasks):
            try:
                user = await bot.fetch_user(uid)
                await user.send(f"Today's task: {tasks[day_index]}")
            except discord.Forbidden:
                print(f"❌ Cannot DM user ID: {uid}")

# --- Report Upload Logic ---
UPLOAD_CHANNEL_ID = 1300794368940183583
TARGET_CHANNEL_ID = 1300794368940183583
FOLDER_NAME = "weekly_reports"
CHAR_LIMIT = 2000
TIME_LIMIT = 60

os.makedirs(FOLDER_NAME, exist_ok=True)

def split_message(content, limit=CHAR_LIMIT):
    sections = content.split("****")
    chunks = []
    for section in sections:
        section = section.strip()
        if not section:
            continue
        section_with_marker = section + "\n****"
        if len(section_with_marker) <= limit:
            chunks.append(section_with_marker)
        else:
            for i in range(0, len(section_with_marker), limit):
                chunks.append(section_with_marker[i:i+limit])
    return chunks

@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ Logged in as {bot.user} and slash commands synced!")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if message.channel.id == UPLOAD_CHANNEL_ID and message.attachments:
        for attachment in message.attachments:
            if attachment.filename.endswith(".txt"):
                timestamp = int(time.time())
                path = os.path.join(FOLDER_NAME, f"{timestamp}.txt")
                async with aiohttp.ClientSession() as session:
                    async with session.get(attachment.url) as resp:
                        if resp.status == 200:
                            with open(path, "wb") as f:
                                f.write(await resp.read())
                            await message.channel.send("✅ File uploaded! Use `/sendfile` within 60 seconds.")

    await bot.process_commands(message)

# --- SLASH COMMANDS ---

@tree.command(name="hello", description="Say hi to the bot")
async def hello(interaction: discord.Interaction):
    await interaction.response.send_message("Hello! I am your new bot!")

@tree.command(name="sendfile", description="Send the most recent uploaded .txt file")
async def sendfile(interaction: discord.Interaction):
    if interaction.channel.id != TARGET_CHANNEL_ID:
        await interaction.response.send_message("⚠️ You can't use this command here.", ephemeral=True)
        return

    now = int(time.time())
    sent = False

    for fname in os.listdir(FOLDER_NAME):
        fpath = os.path.join(FOLDER_NAME, fname)
        ftime = int(fname.split(".")[0])

        if now - ftime <= TIME_LIMIT:
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read().strip()
            if content:
                for chunk in split_message(content):
                    await interaction.channel.send(chunk)
                sent = True
            os.remove(fpath)

    if sent:
        await interaction.response.send_message("✅ Report sent.")
    else:
        await interaction.response.send_message("⚠️ No recent file found to send.")

# --- Start Bot ---
if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ BOT_TOKEN not set.")
