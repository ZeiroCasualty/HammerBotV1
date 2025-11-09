import discord
from discord import app_commands
from discord.ext import commands
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
channel_id = 1298102201905840220  # Channel for task posts

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
  1297749741190385736: "Jen",
  1297749740489936939: "Jessa",
  1297749642230104125: "Cris",
  1315867037003944000: "Jonathan",
}

members_tasks = {
  1297751702019113081: [  # Yasmin
      "Cook – Breakfast",                    # Monday
      "Wash – EOD",                          # Tuesday
      "Cook – Lunch",                        # Wednesday
      "Wash – Lunch (Outdoor)",              # Thursday
      "Cook – Breakfast",                    # Friday
  ],
  182703599397240832: [  # Bernard
      "Wash – Lunch (Indoor)",                            # Monday
      "Wash – Breakfast (Indoor) + Organize Dishes",      # Tuesday
      "Wash – Lunch (Outdoor)",                           # Wednesday
      "Wash – EOD",                                       # Thursday
      "Cook Rice w/ Eggs + Set/Clean Table & Leftovers",  # Friday
  ],
  1297750232745902196: [  # Dani
      "Cook – Lunch",                                     # Monday
      "Cook – Breakfast",                                 # Tuesday
      "Wash – Breakfast (Indoor) + Organize Dishes",      # Wednesday
      "Cook – Breakfast",                                 # Thursday
      "Cook – Lunch",                                     # Friday
  ],
  1297749741190385736: [  # Jen
      "Cook Rice w/ Eggs + Set/Clean Table & Leftovers",  # Monday
      "Wash – Lunch (Outdoor)",                           # Tuesday
      "Wash – EOD",                                       # Wednesday
      "Wash – Lunch (Indoor)",                            # Thursday
      "Wash – EOD",                                       # Friday
  ],
  1297749740489936939: [  # Jessa
      "Wash – EOD",                                       # Monday
      "Cook Rice w/ Eggs + Set/Clean Table & Leftovers",  # Tuesday
      "Wash – Lunch (Indoor)",                            # Wednesday
      "Cook Rice w/ Eggs + Set/Clean Table & Leftovers",  # Thursday
      "Wash – Lunch (Outdoor)",                           # Friday
  ],
  1297749642230104125: [  # Cris
      "Wash – Lunch (Outdoor)",                           # Monday
      "Wash – Lunch (Indoor)",                            # Tuesday
      "Cook Rice w/ Eggs + Set/Clean Table & Leftovers",  # Wednesday
      "Wash – Breakfast (Indoor) + Organize Dishes",      # Thursday
      "Wash – Breakfast (Indoor) + Organize Dishes",      # Friday
  ],
  1315867037003944000: [  # Jonathan
      "Wash – Breakfast (Indoor) + Organize Dishes",      # Monday
      "Cook – Lunch",                                     # Tuesday
      "Cook – Breakfast",                                 # Wednesday
      "Cook – Lunch",                                     # Thursday
      "Wash – Lunch (Indoor)",                            # Friday
  ],
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
    if is_nz_holiday_from_ph():
        return
        
    day_index = get_ph_time().weekday()
    for uid, tasks in members_tasks.items():
        if day_index < len(tasks):
            task_text = tasks[day_index]
            try:
                user = await bot.fetch_user(uid)
                await user.send(f"Annyeong! :cherry_blossom: Today's task: {task_text}")
            except discord.Forbidden:
                print(f"❌ Cannot DM user ID: {uid}")

# --- Report Upload Logic ---
CHANNEL_PAIRS = {
    1298113350814793738: 1298102353358225418,  # Target 1 -> Upload 1
    1298435713507004507: 1298102201905840220,  # Target 2 -> Upload 2
}
FOLDER_NAME = "weekly_reports"
CHAR_LIMIT = 2000
TIME_LIMIT = 300

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
        # 7:45 AM PH (UTC+8) on Mon, Wed, Thu, Fri
        # -> 23:45 UTC on Sun, Tue, Wed, Thu
        trigger_745 = CronTrigger(
            hour=23, minute=45,
            day_of_week='sun,tue,wed,thu',
            timezone="UTC"
        )

        # 8:30 AM PH (UTC+8) on Tuesday only
        # -> 00:30 UTC on Tuesday
        trigger_tue_830 = CronTrigger(
            hour=0, minute=30,
            day_of_week='tue',
            timezone="UTC"
        )

        # Schedule both the channel post and the member DMs for each trigger
        for trig in (trigger_745, trigger_tue_830):
            scheduler.add_job(send_tasks_to_channel, trig)
            scheduler.add_job(send_tasks_to_members, trig)

        scheduler.start()
        scheduler_started = True
        print("⏰ Scheduler started. Tasks: 7:45 AM PH (Mon/Wed/Thu/Fri) and 8:30 AM PH (Tue).")
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
                            await message.channel.send(f"✅ `{fname}` uploaded! Use `/sendreport` within 5 minutes")

    await bot.process_commands(message)

# --- SLASH COMMANDS ---

@tree.command(name="hello", description="Say hi to the bot")
async def hello(interaction: discord.Interaction):
    await interaction.response.defer(thinking=False)
    await interaction.followup.send("Hello! I am your new bot!")

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

@tree.command(name="clear", description="Delete all stored files in the weekly_reports folder")
async def clear_files(interaction: discord.Interaction):
    deleted_files = 0
    for fname in os.listdir(FOLDER_NAME):
        if fname.endswith(".txt"):
            fpath = os.path.join(FOLDER_NAME, fname)
            try:
                os.remove(fpath)
                deleted_files += 1
            except Exception as e:
                print(f"❌ Failed to delete {fpath}: {e}")

    if deleted_files > 0:
        await interaction.response.send_message(f"🗑️ Deleted {deleted_files} file(s).")
    else:
        await interaction.response.send_message("📁 No files found to delete.")

@tree.command(name="tasks", description="Manually send daily tasks to the channel")
async def manual_daily(interaction: discord.Interaction):
    await interaction.response.defer()
    await send_tasks_to_channel()
    await interaction.followup.send("📬 Daily tasks have been sent to the channel.")

# --- Start Bot ---
if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ BOT_TOKEN not set.")
