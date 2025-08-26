import os
import discord
from discord import Embed
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


def merge_classes(user_id: int):
    """
    Merge overlapping or consecutive class blocks for a user in the database.
    After this runs, each user's schedule will have only continuous blocks.
    """
    cursor.execute("SELECT day, start, end FROM classes WHERE user_id=?", (user_id,))
    classes = {}
    for day, start, end in cursor.fetchall():
        classes.setdefault(day, []).append((start, end))

    # Merge intervals for each day
    merged = {}
    for day, intervals in classes.items():
        sorted_intervals = sorted(intervals, key=lambda x: x[0])
        merged_intervals = []
        for start, end in sorted_intervals:
            if not merged_intervals:
                merged_intervals.append([start, end])
            else:
                last_start, last_end = merged_intervals[-1]
                # Overlapping or consecutive -> merge
                if start <= last_end:
                    merged_intervals[-1][1] = max(end, last_end)
                else:
                    merged_intervals.append([start, end])
        merged[day] = merged_intervals

    # Clear old entries and insert merged
    cursor.execute("DELETE FROM classes WHERE user_id=?", (user_id,))
    for day, intervals in merged.items():
        for start, end in intervals:
            cursor.execute(
                "INSERT INTO classes (user_id, day, start, end) VALUES (?, ?, ?, ?)",
                (user_id, day, start, end)
            )
    conn.commit()



# --- Load environment variables ---
env_path = Path(__file__).parent.parent / ".env"  # adjust path if needed
load_dotenv(dotenv_path=env_path)
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
    """Add a class and automatically merge overlapping intervals."""
    cursor.execute(
        "INSERT INTO classes (user_id, day, start, end) VALUES (?, ?, ?, ?)",
        (ctx.author.id, day, start, end)
    )
    # Merge immediately after insertion
    merge_classes(ctx.author.id)
    await ctx.send(f"✅ Added and merged class for {ctx.author.display_name}: {day} {start}-{end}")


@bot.command()
async def removeclass(ctx, day: str, start: str, end: str):
    """
    Remove a class from your schedule.
    Automatically splits blocks if needed.
    """
    cursor.execute("SELECT start, end FROM classes WHERE user_id=? AND day=?", (ctx.author.id, day))
    intervals = cursor.fetchall()
    new_intervals = []

    for s, e in intervals:
        # No overlap
        if end <= s or start >= e:
            new_intervals.append((s, e))
        else:
            # Overlap exists
            if start > s:
                new_intervals.append((s, start))  # left part remains
            if end < e:
                new_intervals.append((end, e))    # right part remains

    # Delete old intervals and insert new ones
    cursor.execute("DELETE FROM classes WHERE user_id=? AND day=?", (ctx.author.id, day))
    for s, e in new_intervals:
        cursor.execute("INSERT INTO classes (user_id, day, start, end) VALUES (?, ?, ?, ?)",
                       (ctx.author.id, day, s, e))
    conn.commit()
    await ctx.send(f"❌ Updated schedule after removing {day} {start}-{end} for {ctx.author.display_name}.")



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
    Show your schedule in a neat embedded message, ordered by day and time.
    """
    # Fetch all classes for the user
    cursor.execute("SELECT day, start, end FROM classes WHERE user_id=?", (ctx.author.id,))
    rows = cursor.fetchall()
    if not rows:
        await ctx.send("📅 You have no classes in your schedule.")
        return

    # Order days
    day_order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    schedule_dict = {day: [] for day in day_order}
    for day, start, end in rows:
        schedule_dict[day].append(f"{start} - {end}")

    # Sort times within each day
    for day in day_order:
        schedule_dict[day].sort()

    # Build embed
    embed = Embed(title=f"{ctx.author.display_name}'s Schedule 📅", color=0x1abc9c)
    for day in day_order:
        if schedule_dict[day]:
            times = "\n".join(schedule_dict[day])
            embed.add_field(name=day, value=times, inline=False)

    await ctx.send(embed=embed)


@bot.command()
async def importschedule(ctx, *, schedule_text: str):
    """
    Import your weekly schedule from multi-line text.
    """
    lines = schedule_text.strip().split("\n")
    user_id = ctx.author.id

    # Insert all lines into database
    for line in lines:
        try:
            day, times = line.split()
            start, end = times.split("-")
            cursor.execute(
                "INSERT INTO classes (user_id, day, start, end) VALUES (?, ?, ?, ?)",
                (user_id, day, start, end)
            )
        except ValueError:
            await ctx.send(f"⚠️ Invalid line: {line}")
            continue

    # Merge all overlapping/consecutive intervals after insert
    merge_classes(user_id)
    await ctx.send(f"✅ Schedule imported and merged for {ctx.author.display_name}.")







# --- Run the bot ---
bot.run(TOKEN)
