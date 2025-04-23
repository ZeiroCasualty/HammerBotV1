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
import pytz
from dotenv import load_dotenv

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# --- Load Environment Variables ---
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

scheduler = AsyncIOScheduler()
scheduler_started = False  # Track if it’s started

# --- Flask App (for Railway health check only) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    app.run(host="0.0.0.0", port=8080)

Thread(target=run_flask).start()

# --- Discord Bot Setup ---
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# --- Time Helper ---
def get_ph_time():
    return datetime.now(pytz.timezone("Asia/Manila"))

def is_weekday():
    return get_ph_time().weekday() < 5

# --- Task Config ---
channel_id = 1298102437659414528  # Channel for task posts

# --- New Zealand Holidays (Manual List) ---
NZ_HOLIDAYS_2025 = {
    "2025-01-01",  # New Year's Day
    "2025-01-02",  # Day after New Year's Day
    "2025-02-06",  # Waitangi Day
    "2025-04-18",  # Good Friday
    "2025-04-21",  # Easter Monday
    "2025-04-25",  # Anzac Day
    "2025-06-02",  # King's Birthday
    "2025-06-20",  # Matariki
    "2025-10-27",  # Labour Day
    "2025-12-25",  # Christmas Day
    "2025-12-26",  # Boxing Day
}

# --- Convert PH time to NZ date ---
def get_nz_date_from_ph():
    ph_time = get_ph_time()
    nz_time = ph_time.astimezone(pytz.timezone("Pacific/Auckland"))
    return nz_time.strftime("%Y-%m-%d")

# --- Check if NZ date is a holiday ---
def is_nz_holiday_from_ph():
    return get_nz_date_from_ph() in NZ_HOLIDAYS_2025

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
    1297749519559299102: ["Wash Dishes - Breakfast", "CR Officer", "Wash Dishes - Lunch (Indoor)", "Sweep Floor", "Wash Dishes - Lunch (Outdoor)"],
    1297749741190385736: ["Sweep Floor", "Organize Dishes / Cook Rice", "Wash Dishes - Breakfast", "Set/Clean Table/Leftovers", "Wash Dishes - Lunch (Indoor)"],
    1297749740489936939: ["Set/Clean Table/Leftovers", "Wash Dishes - Lunch (Outdoor)", "CR Officer", "Wash Dishes - Breakfast", "Organize Dishes / Cook Rice"],
    1297752200767868993: ["Cook - Breakfast", "Cook - Lunch", "Organize Dishes / Cook Rice", "Cook - Lunch", "CR Officer"],
    1297749642230104125: ["CR Officer", "Wash Dishes - EOD", "Set/Clean Table/Leftovers", "Wash Dishes - Lunch (Outdoor)", "Sweep Floor"],
    1315867037003944000: ["Wash Dishes - Lunch (Outdoor)", "Wash Dishes - Lunch (Indoor)", "Sweep Floor", "CR Officer", "Wash Dishes - EOD"],
    744792475696365580: ["Wash Dishes - EOD", "Set/Clean Table/Leftovers", "Wash Dishes - EOD", "Wash Dishes - Lunch (Indoor)", "Wash Dishes - Breakfast"],
}

async def send_tasks_to_channel():
    channel = bot.get_channel(channel_id)
    if not channel:
        return

    if not is_weekday():
        return  # Skip weekends (PH time)

    if is_nz_holiday_from_ph():
        await channel.send("Good morning, today is a holiday!\nNo daily tasks. Hooray! :partying_face:")
        return

    now = get_ph_time()
    day = now.strftime("%A")
    day_index = now.weekday()
    msg = f"Good morning, today is {day}.\nHere are your daily tasks: :pencil:\n\n"
    for uid, tasks in members_tasks.items():
        if day_index < len(tasks):
            name = members_info.get(uid, "Unknown")
            msg += f"{name}: {tasks[day_index]}\n"
    await channel.send(msg)

async def send_tasks_to_members():
    day_index = get_ph_time().weekday()
    for uid, tasks in members_tasks.items():
        if day_index < len(tasks):
            try:
                user = await bot.fetch_user(uid)
                await user.send(f"Today's task: {tasks[day_index]}")
            except discord.Forbidden:
                print(f"❌ Cannot DM user ID: {uid}")

# --- Report Upload Logic ---
CHANNEL_PAIRS = {
    1298113350814793738: 1298102353358225418,  # Target 1 -> Upload 1
    1298435713507004507: 1298102201905840220,  # Target 2 -> Upload 2
}
FOLDER_NAME = "weekly_reports"
CHAR_LIMIT = 2000
TIME_LIMIT = 60

os.makedirs(FOLDER_NAME, exist_ok=True)

def split_message(content, limit=CHAR_LIMIT):
    sections = content.split("----")
    chunks = []
    for section in sections:
        section = section.strip()
        if not section:
            continue
        section_with_marker = section + "\n----\n"
        if len(section_with_marker) <= limit:
            chunks.append(section_with_marker)
        else:
            for i in range(0, len(section_with_marker), limit):
                chunks.append(section_with_marker[i:i+limit])
    return chunks

@bot.event
async def on_ready():
    global scheduler_started

    await tree.sync()
    print(f"✅ Logged in as {bot.user}")

    if not scheduler_started:
        trigger = CronTrigger(hour=23, minute=45, day_of_week='sun,mon,tue,wed,thu', timezone="UTC")
        scheduler.add_job(send_tasks_to_channel, trigger)
        scheduler.add_job(send_tasks_to_members, trigger)
        scheduler.start()
        scheduler_started = True
        print("⏰ Scheduler started. Tasks will be sent at 7:45 AM PH time.")
    else:
        print("⏩ Scheduler already started. Skipping re-initialization.")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if message.channel.id in CHANNEL_PAIRS.values() and message.attachments:
        current_time = int(time.time())
        async with aiohttp.ClientSession() as session:
            for attachment in message.attachments:
                fname = attachment.filename.lower()
                if fname in ["message.txt", "weekly.txt"]:
                    timestamp = current_time
                    clean_name = fname.replace(" ", "_")
                    # Include channel ID in filename
                    save_path = os.path.join(FOLDER_NAME, f"{timestamp}_{message.channel.id}_{clean_name}")

                    async with session.get(attachment.url) as resp:
                        if resp.status == 200:
                            with open(save_path, "wb") as f:
                                f.write(await resp.read())
                            await message.channel.send(f"✅ `{fname}` uploaded! Use `/sendreport` within 60 seconds.")

    await bot.process_commands(message)

# --- SLASH COMMANDS ---

@tree.command(name="hello", description="Say hi to the bot")
async def hello(interaction: discord.Interaction):
    await interaction.response.send_message("Hello! I am your new bot!")

@tree.command(name="sendreport", description="Send the most recent uploaded .txt files")
async def sendreport(interaction: discord.Interaction):
    await interaction.response.defer()

    target_channel_id = interaction.channel.id
    upload_channel_id = CHANNEL_PAIRS.get(target_channel_id)

    if upload_channel_id is None:
        await interaction.followup.send("⚠️ This channel is not allowed to use /sendreport.", ephemeral=True)
        return

    now = int(time.time())
    sent = False

    valid_filenames = ["message.txt", "weekly.txt"]
    matching_files = []

    for fname in sorted(os.listdir(FOLDER_NAME)):
        fpath = os.path.join(FOLDER_NAME, fname)
        try:
            parts = fname.split("_", 2)
            ftime = int(parts[0])
            file_upload_channel_id = int(parts[1])
            actual_name = parts[2]
        except (ValueError, IndexError):
            continue

        if (
            now - ftime <= TIME_LIMIT
            and file_upload_channel_id == upload_channel_id
            and actual_name in valid_filenames
        ):
            matching_files.append((ftime, fpath))

    for _, fpath in sorted(matching_files):
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if content:
            for chunk in split_message(content):
                await interaction.channel.send(chunk)
            sent = True
        os.remove(fpath)

    if sent:
        await interaction.followup.send("✅ Reports sent.")
    else:
        await interaction.followup.send("⚠️ No recent file found from the expected upload channel.")

# --- Start Bot ---
if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ BOT_TOKEN not set.")
