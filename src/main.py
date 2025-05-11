import os
import sys
import time
import shutil
import discord
from colorama import *
import logging
from discord import app_commands
from dotenv import load_dotenv

from commands.music import MusicCommands
from core.player import PlayerHandler
from core.downloader import DownloaderHandler
from core import utils
from pathlib import Path

# Colorama initialization
init()

# Create logger
loggerName = Path(__file__).stem
logger = logging.getLogger(loggerName)
logger.setLevel(logging.DEBUG)

OK_STATUS = f"[{Fore.GREEN}OK{Style.RESET_ALL}]"
FAILED_STATUS = f"[{Fore.RED}FAILED{Style.RESET_ALL}]"
READY_STATUS = f"[{Fore.BLUE}READY{Style.RESET_ALL}]"


def log_ok(msg):
    logger.log(logging.INFO, f"{OK_STATUS} {msg}", extra={"no_level": True})


def log_failed(msg):
    logger.log(logging.ERROR, f"{FAILED_STATUS} {msg}", extra={"no_level": True})

def log_ready(msg):
    logger.log(logging.INFO, f"{READY_STATUS} {msg}", extra={"no_level": True})

class ColorFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG: Fore.CYAN,
        logging.INFO: Fore.WHITE,
        logging.WARNING: Fore.YELLOW,
        logging.ERROR: Fore.RED,
        logging.CRITICAL: Fore.RED + Style.BRIGHT
    }

    def format(self, record):
        # Support skipping level prefix for status messages
        message_only = getattr(record, "no_level", False)

        if message_only:
            return record.getMessage()  # only print the message

        level_color = self.COLORS.get(record.levelno, Fore.WHITE)
        levelname = level_color + record.levelname + Style.RESET_ALL
        record.levelname = levelname
        return super().format(record)


logFormatter = ColorFormatter("[%(levelname)s] :: %(message)s")

# Setup handler
consoleHandler = logging.StreamHandler()
consoleHandler.setLevel(logging.DEBUG)
consoleHandler.setFormatter(logFormatter)

logger.addHandler(consoleHandler)

# Test

def soft_clear_terminal():
    # Soft-clear screen by printing enough lines to fill the visible terminal
    height, _ = shutil.get_terminal_size((80, 24))  # fallback size
    print("\n" * (height//2))

    # Now reset the cursor to top-left safely (Windows-compatible)
    if os.name == 'nt':
        os.system('cls')  # Windows safe "clear" without scrollback wipe
    else:
        print("\033[H", end="")  # Unix-like fallback   

def logtest():
    print("Testing logging... \n\n")

    logger.debug('debug message')
    time.sleep(0.5)
    logger.info('info message')
    time.sleep(0.2)
    logger.warning('warn message')
    time.sleep(0.1)
    logger.error('error message')
    time.sleep(0.1)
    logger.critical('critical message')
    print("\n")

    log_ok('This is an OK message')
    time.sleep(0.01)
    log_failed('This is a FAILED message')
    
    time.sleep(0.3)

    print("\n\nTesting logging complete.")
    print("========================================\n\n")

     # Pause for 2 seconds
    time.sleep(2)
    
    soft_clear_terminal()

    # Now reset the cursor to top-left safely (Windows-compatible)
    if os.name == 'nt':
        os.system('cls')  # Windows safe "clear" without scrollback wipe
    else:
        print("\033[H", end="")  # Unix-like fallback
        
    log_ok("Error Handling test succeeded.")


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
    print("========================================")
    print("Starting up...")
    time.sleep(0.5)
    soft_clear_terminal()
    
    logtest()  # Test logging

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

    # Leave if every other user leaves
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
    # Optional: initial cleanup
    try:
        from json import load
        with open("data/toc.json", "r") as f:
            toc = load(f)
        utils.cleanup_orphaned_files(toc)
    except Exception as e:
        print(f"Failed to clean up orphaned files: {e}")

    client.run(TOKEN)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        if os.getenv("PRINT_STACK_TRACE", "1").lower() in ("1", "true", "t"):
            raise
        print(f"Error: {e}")
