# log_config.py
import logging
import os
import time
import shutil
from pathlib import Path
from colorama import init, Fore, Style

# Ensure logs directory exists
Path("logs").mkdir(parents=True, exist_ok=True)

# Clear custom log file
with open("logs/output.log", "w", encoding="utf-8") as f:
    f.truncate(0)

# Clear Discord log file
with open("logs/discordoutput.log", "w", encoding="utf-8") as f:
    f.truncate(0)

# Colorama setup
init(strip=False, convert=False, autoreset=True)

# Custom log format with color support
class ColorFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG: Fore.CYAN,
        logging.INFO: Fore.WHITE,
        logging.WARNING: Fore.YELLOW,
        logging.ERROR: Fore.RED,
        logging.CRITICAL: Fore.RED + Style.BRIGHT
    }

    ANSI_RESET = Style.RESET_ALL + "\033[0m"

    def format(self, record):
        message_only = getattr(record, "no_level", False)
        suffix = self.ANSI_RESET + "\n"

        if message_only:
            return record.getMessage().rstrip() + suffix

        level_color = self.COLORS.get(record.levelno, Fore.WHITE)
        record.levelname = level_color + record.levelname + self.ANSI_RESET

        base_message = super().format(record)
        return base_message.rstrip() + suffix

# Formatter instance
logFormatter = ColorFormatter("[%(levelname)s] :: %(message)s")

# Create and configure main bot logger
logger = logging.getLogger("bot")
logger.setLevel(logging.DEBUG)

# Console handler
consoleHandler = logging.StreamHandler()
consoleHandler.setLevel(logging.DEBUG)
consoleHandler.setFormatter(logFormatter)
logger.addHandler(consoleHandler)

# File handler for custom logs
fileHandler = logging.FileHandler("logs/output.log", encoding="utf-8")
fileHandler.setLevel(logging.DEBUG)
fileHandler.setFormatter(logFormatter)
logger.addHandler(fileHandler)

# File handler for Discord logs only (no color formatter)
discordFileHandler = logging.FileHandler("logs/discordoutput.log", encoding="utf-8")
discordFileHandler.setLevel(logging.DEBUG)
discordFileHandler.setFormatter(logging.Formatter("[%(levelname)s] :: %(message)s"))

# Hook Discord's loggers separately (file only)
for name in ("discord", "discord.client", "discord.gateway", "discord.voice_state"):
    discord_logger = logging.getLogger(name)
    discord_logger.setLevel(logging.INFO)
    discord_logger.handlers.clear()
    discord_logger.addHandler(discordFileHandler)

# Shortcut functions for special tags
OK_STATUS = f"[{Fore.GREEN}OK{Style.RESET_ALL}]"
FAILED_STATUS = f"[{Fore.RED}FAILED{Style.RESET_ALL}]"
READY_STATUS = f"[{Fore.BLUE}READY{Style.RESET_ALL}]"

def log_ok(msg):
    logger.log(logging.INFO, f"{OK_STATUS} {msg}", extra={"no_level": True})

def log_failed(msg):
    logger.log(logging.ERROR, f"{FAILED_STATUS} {msg}", extra={"no_level": True})

def log_ready(msg):
    logger.log(logging.INFO, f"{READY_STATUS} {msg}", extra={"no_level": True})

def soft_clear_terminal():
    height, _ = shutil.get_terminal_size((80, 24))
    print("\n" * (height // 2))
    if os.name == 'nt':
        os.system('cls')
    else:
        print("\033[H", end="")

def logtest():
    logger.info("Current Time: " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()))
    logger.info("Testing logging...\n")

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

    logger.info("Testing logging complete.")
    logger.info("========================================")
    time.sleep(2)

    soft_clear_terminal()
    log_ok("Error Handling test succeeded.")
