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


def parse_time(t: str) -> datetime.time:
    return datetime.strptime(t, "%H:%M").time()

def is_free(user_id: int) -> bool:
    cursor.execute("SELECT status FROM overrides WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    if row:
        return row[0] == "available"

    now = datetime.now()
    weekday = now.strftime("%a")  
    current_time = now.time()     

    cursor.execute("SELECT start, end FROM classes WHERE user_id=? AND day=?", (user_id, weekday))
    rows = cursor.fetchall()
    for start, end in rows:
        start_t = parse_time(start)
        end_t = parse_time(end)
        if start_t <= current_time <= end_t:
            return False
    return True

day_map = {
    "monday": "Mon", "mon": "Mon",
    "tuesday": "Tue", "tue": "Tue",
    "wednesday": "Wed", "wed": "Wed",
    "thursday": "Thu", "thu": "Thu",
    "friday": "Fri", "fri": "Fri",
    "saturday": "Sat", "sat": "Sat",
    "sunday": "Sun", "sun": "Sun",
}


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

def has_activity_role(member: discord.Member, activity: str) -> bool:
    """
    Check if the member has a role matching the activity (case-insensitive).
    """
    return any(role.name.lower() == activity.lower() for role in member.roles)
    
    

# --- Load environment variables ---
env_path = Path(__file__).parent.parent / ".env"  # adjust path if needed
load_dotenv(dotenv_path=env_path)
TOKEN = os.getenv("DISCORD_TOKEN")

# --- Bot setup ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True   
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
async def apologize(ctx):
    await ctx.send("SORRY PARENT OF MINE")

@bot.command()
async def addclass(ctx, day: str, start: str, end: str):
    """Add a class and automatically merge overlapping intervals."""
    day = day_map.get(day.lower(), day)
    cursor.execute(
        "INSERT INTO classes (user_id, day, start, end) VALUES (?, ?, ?, ?)",
        (ctx.author.id, day, start, end)
    )
    # Merge immediately after insertion
    merge_classes(ctx.author.id)
    await ctx.send(f"✅ Added and merged class for {ctx.author.display_name}: {day} {start}-{end}")

@bot.command()
async def removeclass(ctx, day: str, start: str, end: str):
    """Remove a class from your schedule."""
    day = day_map.get(day.lower(), day)

    cursor.execute("SELECT start, end FROM classes WHERE user_id=? AND day=?", (ctx.author.id, day))
    intervals = cursor.fetchall()
    if not intervals:
        await ctx.send(f"⚠️ No classes found on {day} for {ctx.author.display_name}.")
        return

    def parse_time(t):
        return datetime.strptime(t, "%H:%M").time()

    start_t = parse_time(start)
    end_t = parse_time(end)

    new_intervals = []
    for s, e in intervals:
        s_t = parse_time(s)
        e_t = parse_time(e)
        if end_t <= s_t or start_t >= e_t:
            new_intervals.append((s, e))
        else:
            if start_t > s_t:
                new_intervals.append((s, start))
            if end_t < e_t:
                new_intervals.append((end, e))

    cursor.execute("DELETE FROM classes WHERE user_id=? AND day=?", (ctx.author.id, day))
    for s, e in new_intervals:
        cursor.execute(
            "INSERT INTO classes (user_id, day, start, end) VALUES (?, ?, ?, ?)",
            (ctx.author.id, day, s, e)
        )
    conn.commit()

    await ctx.send(f"❌ Updated schedule after removing {day} {start}-{end} for {ctx.author.display_name}.")


@bot.command()
async def ping(ctx, activity: str, *, message: str = ""):
    """
    Ping users who are free and have a specific role/activity.

    Usage: !ping <activity> [optional message]
    Example: !ping studying Come join at the library!
    """
    # Get all members excluding bots
    members = [m for m in ctx.guild.members if not m.bot]

    # Filter members: free AND has role
    valid_members = [
        m for m in members
        if is_free(m.id) and has_activity_role(m, activity)
    ]

    if not valid_members:
        await ctx.send(f"😅 No one is free with the role '{activity}' right now.")
        return

    mentions = " ".join(m.mention for m in valid_members)
    # Include the activity in the message
    activity_msg = f"📢 Pinged for **{activity}**!"
    full_message = f"{ctx.author.display_name} says: {message}\n{activity_msg} {mentions}"
    await ctx.send(full_message)


@bot.command()
async def isfree(ctx, member: discord.Member):
    """
    Check if a specific user is free based on their schedule and overrides.

    Usage: !isfree @username
    """
    free_status = is_free(member.id)
    if free_status:
        await ctx.send(f"✅ {member.display_name} is currently free!")
    else:
        await ctx.send(f"⛔ {member.display_name} is currently busy.")


@bot.command()
async def free(ctx):
    """
    Show all users in the database who are currently free.
    If no one is free, send a message saying so.
    Does NOT ping users, just shows names.
    """
    # Get all user_ids from DB
    cursor.execute("""
        SELECT DISTINCT user_id FROM classes
        UNION
        SELECT DISTINCT user_id FROM overrides
    """)
    rows = cursor.fetchall()

    free_users = []

    for (uid,) in rows:
        member = ctx.guild.get_member(int(uid))
        if member:
            name = member.display_name  # ✅ use name instead of mention
        else:
            name = f"Unknown User ({uid})"  # fallback if not in guild

        if is_free(uid):
            free_users.append(name)

    if free_users:
        await ctx.send(f"✅ These users are free right now: {', '.join(free_users)}")
    else:
        await ctx.send("😅 No one is free right now.")
  
@bot.command()
async def clearoverride(ctx):
    """
    Remove your manual busy/available override.
    After this, your free/busy status will be determined by your schedule only.

    Usage: !clearoverride
    """
    cursor.execute("DELETE FROM overrides WHERE user_id=?", (ctx.author.id,))
    conn.commit()
    await ctx.send(f"🗑️ {ctx.author.display_name}'s override has been cleared. Status now depends only on schedule.")

@bot.command()
async def users(ctx):
    """
    List all users saved in the database.
    Usage: !users
    """
    cursor.execute("SELECT user_id FROM classes")
    rows = cursor.fetchall()

    if not rows:
        await ctx.send("📂 No users found in the database.")
        return

    # Use a set to avoid duplicates
    user_ids = {row[0] for row in rows}

    mentions = []
    for uid in user_ids:
        member = ctx.guild.get_member(int(uid))
        if member:
            mentions.append(member.mention)
        else:
            mentions.append(f"<@{uid}>")  # fallback if not in guild

    await ctx.send(f"👥 Users in database: {', '.join(mentions)}")



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
    
    user_id = ctx.author.id

    # --- Clear existing schedule first ---
    cursor.execute("DELETE FROM classes WHERE user_id=?", (user_id,))
    conn.commit()

    # --- Parse and import new schedule ---
    lines = schedule_text.strip().split("\n")
    inserted = 0
    for line in lines:
        try:
            day, times = line.split()
            day = day_map.get(day.lower(), day)
            start, end = times.split("-")
            cursor.execute(
                "INSERT INTO classes (user_id, day, start, end) VALUES (?, ?, ?, ?)",
                (user_id, day, start, end)
            )
            inserted += 1
        except ValueError:
            await ctx.send(f"⚠️ Invalid line format: `{line}` (expected: 'Day HH:MM-HH:MM')")
            continue

    conn.commit()

    # --- Merge any overlaps ---
    merge_classes(user_id)

    await ctx.send(f"✅ Cleared old schedule and imported {inserted} new entries for {ctx.author.display_name}.")

@bot.command()
async def myroles(ctx):
    """
    List all roles the user currently has.
    """
    roles = [role.name for role in ctx.author.roles if role.name != "@everyone"]
    if roles:
        await ctx.send(f"🎯 {ctx.author.display_name}'s roles: {', '.join(roles)}")
    else:
        await ctx.send(f"⚠️ {ctx.author.display_name} has no roles yet.")
        
        
        
@bot.command()
async def schedule(ctx, member: discord.Member):
    """
    Show another user's schedule.
    
    Usage: !schedule @username
    """
    cursor.execute("SELECT day, start, end FROM classes WHERE user_id=?", (member.id,))
    rows = cursor.fetchall()

    if not rows:
        await ctx.send(f"📅 {member.display_name} has no classes in their schedule.")
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
    embed = discord.Embed(title=f"{member.display_name}'s Schedule 📅", color=0x1abc9c)
    for day in day_order:
        if schedule_dict[day]:
            embed.add_field(name=day, value="\n".join(schedule_dict[day]), inline=False)

    await ctx.send(embed=embed)



# --- Run the bot ---
bot.run(TOKEN)
    