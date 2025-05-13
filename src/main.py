import os
import sys
import time
import discord
from discord import app_commands
from dotenv import load_dotenv
from pathlib import Path

from core import file_check
file_check.verify_file_integrity()

from commands.music import MusicCommands
from core.player import PlayerHandler
from core.downloader import DownloaderHandler
from core.log_config import logger, log_ok, log_failed, log_ready, logtest, soft_clear_terminal
from core import utils

# Load environment variables
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")

if not TOKEN or not GUILD_ID:
    sys.exit("Error: BOT_TOKEN and GUILD_ID must be set in .env")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)
guilds = [discord.Object(id=int(GUILD_ID))]
player = PlayerHandler(client)
downloader = DownloaderHandler(client, player)
musichandler = MusicCommands(tree, guilds, downloader)

@client.event
async def on_ready():
    logger.info("========================================")
    logger.info("Starting up...")
    time.sleep(0.5)
    soft_clear_terminal()

    # logtest()
    time.sleep(0.5)

    log_ok(f"Logged in as {client.user}")
    await tree.sync(guild=guilds[0])
    log_ok(f"Slash commands synced to {GUILD_ID}")
    time.sleep(0.5)
    log_failed("Ban Scienceboy from the server :(")
    time.sleep(0.2)
    log_ready("Server is ready.")

@client.event
async def on_voice_state_update(member, before, after):
    if member.id == client.user.id:
        return

    if after.channel is None:
        vc_conn = before.channel.guild.voice_client

        user_count = 0
        am_i_here = False
        for member in before.channel.members:
            if not member.bot:
                user_count += 1
            elif member.id == client.user.id:
                am_i_here = True

        if user_count == 0 and am_i_here:
            await player.disconnect(force=False)
            player.queues.pop(before.channel.guild.id, None)

def main():
    try:
        from json import load
        with open("data/toc.json", "r") as f:
            toc = load(f)
        utils.cleanup_orphaned_files(toc)
    except Exception as e:
        logger.error(f"Failed to clean up orphaned files: {e}")

    client.run(TOKEN)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        if os.getenv("PRINT_STACK_TRACE", "1").lower() in ("1", "true", "t"):
            raise
        logger.error(f"Unhandled Exception: {e}")
