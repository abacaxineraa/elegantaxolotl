import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

import sqlite3
from pathlib import Path


env_path = Path(__file__).parent.parent / ".env"  # one folder up
load_dotenv(dotenv_path=env_path)
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


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
conn.commit()


def is_free(user_id: int) -> bool:
    now = datetime.now()
    weekday = now.strftime("%a")  # "Mon", "Tue", etc.
    current_time = now.strftime("%H:%M")

    cursor.execute("SELECT start, end FROM classes WHERE user_id=? AND day=?", (user_id, weekday))
    for start, end in cursor.fetchall():
        if start <= current_time <= end:
            return False
    return True



@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

@bot.command()
async def hello(ctx):
    await ctx.send("Hellu, world!")


@bot.command()
async def addclass(ctx, day: str, start: str, end: str):
    """Add a class: !addclass Mon 09:00 10:30"""
    cursor.execute(
        "INSERT INTO classes (user_id, day, start, end) VALUES (?, ?, ?, ?)",
        (ctx.author.id, day, start, end)
    )
    conn.commit()
    await ctx.send(f"✅ Added class for {ctx.author.display_name}: {day} {start}-{end}")



@bot.command()
async def study(ctx, location: str, duration: str = "30min"):
    """Announce a study session and ping only free users."""
    cursor.execute("SELECT DISTINCT user_id FROM classes")
    user_ids = [row[0] for row in cursor.fetchall()]

    free_users = [ctx.guild.get_member(uid) for uid in user_ids if is_free(uid)]
    mentions = " ".join([u.mention for u in free_users if u])

    await ctx.send(f"📚 {ctx.author.display_name} is studying at {location} for {duration}. Come join! {mentions}")


bot.run(TOKEN)
