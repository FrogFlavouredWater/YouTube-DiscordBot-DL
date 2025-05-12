from pathlib import Path
from core.log_config import logger, log_ok, log_failed, log_ready, logtest, soft_clear_terminal

def verify_file_integrity():
    """
    Verify the integrity of the required files and directories.
    """
    required_files = [
        "data/music",
        "data/jukebox",
        "data/playlists",
        "data/toc.json",
        "logs/output.log",
        "logs/discordoutput.log",
        ".env"
    ]

    for file in required_files:
        path = Path(file)

        # Handle toc.json with default content if missing
        if file == "data/toc.json" and not path.exists():
            with open(file, 'w') as f:
                f.write('[]')
            logger.warning(f"File '{file}' was missing. Created with default content.")
            continue

        if not path.exists():
            log_failed(f"Missing required file or directory: '{file}'")
            logger.info("Prompting user to create missing file/directory...")
            print(f"Would you like to create '{file}'? (y/n)")
            response = input().strip().lower()

            if response == 'y':
                if '.' not in path.name:
                    path.mkdir(parents=True, exist_ok=True)
                    logger.info(f"Directory '{file}' created.")
                else:
                    with open(file, 'w') as f:
                        f.write("")
                    logger.info(f"File '{file}' created.")
            else:
                log_failed(f"User declined to create '{file}'. Exiting integrity check.")
                return False

    log_ok("All required files and directories are present.")
    return True
