import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import sqlite3
from pathlib import Path
from datetime import datetime

# --- Database setup ---
conn = sqlite3.connect('schedules.db')
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS classes (
    user_id INTEGER,
    day TEXT,
    start TEXT,
    end TEXT
)
''')

# Overrides table for busy/available manual status
cursor.execute('''
CREATE TABLE IF NOT EXISTS overrides (
    user_id INTEGER PRIMARY KEY,
    status TEXT
)
''')

conn.commit()

# --- Helper functions ---
def is_free(user_id: int) -> bool:
    """
    Check if a user is currently free.

    Returns:
        True if the user is free (not in class and not marked busy), False otherwise.
    """
    # Check manual override first
    cursor.execute("SELECT status FROM overrides WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    if row:
        return row[0] == "available"

    now = datetime.now()
    weekday = now.strftime("%a")
    current_time = now.strftime("%H:%M")

    cursor.execute("SELECT start, end FROM classes WHERE user_id=? AND day=?", (user_id, weekday))
    for start, end in cursor.fetchall():
        if start <= current_time <= end:
            return False
    return True

# --- Load environment variables ---
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# --- Bot setup ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- Events ---
@bot.event
async def on_ready():
    """
    Event triggered when the bot is online.
    """
    print(f"✅ Logged in as {bot.user}")

# --- Commands ---
@bot.command()
async def hello(ctx):
    """
    Test command to check if the bot is online.

    Usage: !hello
    """
    await ctx.send("Hellu, world!")

@bot.command()
async def addclass(ctx, day: str, start: str, end: str):
    """
    Add a class to your schedule.

    Usage: !addclass <day> <start> <end>
    Example: !addclass Mon 10:00 14:00
    """
    cursor.execute(
        "INSERT INTO classes (user_id, day, start, end) VALUES (?, ?, ?, ?)",
        (ctx.author.id, day, start, end)
    )
    conn.commit()
    await ctx.send(f"✅ Added class for {ctx.author.display_name}: {day} {start}-{end}")

@bot.command()
async def removeclass(ctx, day: str, start: str, end: str):
    """
    Remove a class from your schedule.

    Usage: !removeclass <day> <start> <end>
    Example: !removeclass Mon 10:00 14:00
    """
    cursor.execute(
        "DELETE FROM classes WHERE user_id=? AND day=? AND start=? AND end=?",
        (ctx.author.id, day, start, end)
    )
    conn.commit()
    await ctx.send(f"❌ Removed class for {ctx.author.display_name}: {day} {start}-{end}")

@bot.command()
async def study(ctx, location: str, duration: str = "30min"):
    """
    Announce a study session and ping only users who are free.

    Usage: !study <location> [duration]
    Default duration: 30min
    Example: !study Library 45min
    """
    cursor.execute("SELECT DISTINCT user_id FROM classes")
    user_ids = [row[0] for row in cursor.fetchall()]
    free_users = [ctx.guild.get_member(uid) for uid in user_ids if is_free(uid)]
    mentions = " ".join([u.mention for u in free_users if u])
    await ctx.send(f"📚 {ctx.author.display_name} is studying at {location} for {duration}. Come join! {mentions}")

@bot.command()
async def free(ctx):
    """
    Check who is free right now.

    Usage: !free
    """
    free_users = []
    for member in ctx.guild.members:
        if member.bot:
            continue
        if is_free(member.id):
            free_users.append(member.mention)

    if free_users:
        await ctx.send(f"✅ These users are free right now: {', '.join(free_users)}")
    else:
        await ctx.send("😅 No one is free right now.")

@bot.command()
async def busy(ctx):
    """
    Mark yourself as busy manually, overriding your schedule.

    Usage: !busy
    """
    cursor.execute(
        "INSERT OR REPLACE INTO overrides (user_id, status) VALUES (?, ?)",
        (ctx.author.id, "busy")
    )
    conn.commit()
    await ctx.send(f"⛔ {ctx.author.display_name} is now marked as busy.")

@bot.command()
async def available(ctx):
    """
    Mark yourself as available manually, overriding your schedule.

    Usage: !available
    """
    cursor.execute(
        "INSERT OR REPLACE INTO overrides (user_id, status) VALUES (?, ?)",
        (ctx.author.id, "available")
    )
    conn.commit()
    await ctx.send(f"✅ {ctx.author.display_name} is now marked as available.")

@bot.command()
async def myschedule(ctx):
    """
    Display your weekly schedule.

    Usage: !myschedule
    Shows all classes sorted by day and start time.
    """
    cursor.execute(
        "SELECT day, start, end FROM classes WHERE user_id=? ORDER BY day, start",
        (ctx.author.id,)
    )
    rows = cursor.fetchall()
    if rows:
        schedule = "\n".join([f"{day}: {start} - {end}" for day, start, end in rows])
        await ctx.send(f"📅 {ctx.author.display_name}'s schedule:\n{schedule}")
    else:
        await ctx.send("📅 You have no classes in your schedule.")

# --- Run the bot ---
bot.run(TOKEN)
ot.run(TOKEN)
