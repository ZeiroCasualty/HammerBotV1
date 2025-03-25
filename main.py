import discord
from discord.ext import commands
from flask import Flask
from threading import Thread
import asyncio
import os
from datetime import datetime
from dotenv import load_dotenv

# Load bot token from .env
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

# Discord bot setup
bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())
channel_id = 1298102437659414528

# Define member names and their corresponding IDs
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

# Dictionary to store members and their tasks
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


# Function to check if it's a weekday
def is_weekday():
    return datetime.today().weekday() < 5


# Function to send tasks to channel
async def send_tasks_to_channel():
    channel = bot.get_channel(channel_id)
    if channel:
        day_of_week = datetime.today().strftime("%A")
        message = f"Good morning, today is {day_of_week}.\nHere are your daily tasks:\n\n"
        day_index = datetime.today().weekday()

        for member_id, task_list in members_tasks.items():
            if day_index < len(task_list):
                task = task_list[day_index]
                name = members_info.get(member_id, "Unknown")
                message += f"{name}: {task}\n"

        await channel.send(message)


# Function to send tasks as DM
async def send_tasks_to_members():
    day_index = datetime.today().weekday()

    for member_id, task_list in members_tasks.items():
        if day_index < len(task_list):
            task = task_list[day_index]
            try:
                member = await bot.fetch_user(member_id)
                await member.send(f"Today's task: {task}")
            except discord.Forbidden:
                print(f"Could not DM user with ID: {member_id}")


# Flask Web Server
app = Flask('')

@app.route('/')
def home():
    return "Bot is running."

@app.route('/run', methods=['GET'])
def run_task():
    """Runs the task from a Flask webhook."""
    if is_weekday():
        try:
            asyncio.run_coroutine_threadsafe(send_tasks_to_channel(), bot.loop)
            asyncio.run_coroutine_threadsafe(send_tasks_to_members(), bot.loop)
            return "Tasks sent successfully!", 200
        except Exception as e:
            return f"Error: {str(e)}", 500
    else:
        return "No tasks today (weekend).", 200


# Keep Flask running in the background
def keep_alive():
    app.run(host='0.0.0.0', port=8080)


# Start the web server thread before running the bot
if __name__ == "__main__":
    Thread(target=keep_alive).start()
    bot.run(TOKEN)
