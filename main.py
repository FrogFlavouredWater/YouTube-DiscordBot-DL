import os
import sys
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

from commands import music
from core.player import queues, cleanup_orphaned_files

# Load environment variables
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
PREFIX = os.getenv("BOT_PREFIX", ".")
GUILD_ID = os.getenv("GUILD_ID")

if not TOKEN or not GUILD_ID:
    sys.exit("Error: BOT_TOKEN and GUILD_ID must be set in .env")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)
guilds = [discord.Object(id=int(GUILD_ID))]

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")
    await tree.sync(guild=guilds[0])
    print(f"✅ Slash commands synced to guild {GUILD_ID}")

@client.event
async def on_voice_state_update(member: discord.User, before: discord.VoiceState, after: discord.VoiceState):
    if member != client.user:
        return
    if before.channel and not after.channel:
        queues.pop(before.channel.guild.id, None)

def main():
    # Optional: initial cleanup
    try:
        from json import load
        with open("data/toc.json", "r") as f:
            toc = load(f)
        cleanup_orphaned_files(toc)
    except Exception as e:
        print(f"Failed to clean up orphaned files: {e}")

    music.register_commands(tree, guilds)
    client.run(TOKEN)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        if os.getenv("PRINT_STACK_TRACE", "1").lower() in ("1", "true", "t"):
            raise
        print(f"Error: {e}")
