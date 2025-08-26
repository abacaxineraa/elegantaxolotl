import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

# load .env file (with DISCORD_TOKEN)
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

@bot.command()
async def hello(ctx):
    await ctx.send("Hello, world! 👋")

bot.run(TOKEN)
