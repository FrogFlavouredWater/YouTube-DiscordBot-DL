from pathlib import Path

def verify_file_integrity():
    """
    Verify the integrity of the required files and directories.
    """
    # List of required files and directories
    required_files = [
        "data/music",
        "data/jukebox",
        "data/playlists",
        "data/toc.json",
        "logs/output.log",
        ".env"
    ]

    # Check if each required file exists
    for file in required_files:
        if file == "data/toc.json" and not Path(file).exists():
            # create toc.josn and add: [] to it
            with open(file, 'w') as f:
                f.write('[]')
                print(f"File '{file}' created with default content.")
            continue
        
        if not Path(file).exists():
            print(f"Error: Required file '{file}' is missing.")
            print("Would you like to create it? (y/n)")
            response = input().strip().lower()
            if response == 'y':
                if Path(file).is_dir():
                    Path(file).mkdir(parents=True, exist_ok=True)
                    print(f"Directory '{file}' created.")
                else:
                    with open(file, 'w') as f:
                        f.write("")
            return False

    print("All required files are present.")
    return True