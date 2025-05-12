from datetime import datetime, timezone
import discord

def create_embed(title, description, color, queue_list=[], song_queuer=None, song_name=None):
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=datetime.now(timezone.utc)
    )

    if song_name:
        embed.add_field(name="Currently Playing", value=song_name, inline=False)

    if len(queue_list) > 0:
        if isinstance(queue_list[0], list):
            embed.add_field(name="Other Songs in Queue", value="\n".join(queue_list), inline=False)
        elif isinstance(queue_list[0], dict):
            l = []
            for i in queue_list: l.append(i['title'])
            embed.add_field(name="Other Songs in Queue", value="\n".join(l), inline=False)

    if song_queuer:
        embed.add_field(
            name="Requested by",
            value=song_queuer.mention if hasattr(song_queuer, 'mention') else str(song_queuer),
            inline=False
        )

    return embed

def cleanup_orphaned_files(toc):
    import os
    tocfiles = [entry['file'] for entry in toc]

    for folder, _, files in os.walk("data/music"):
        for file in files:
            full_path = os.path.join(folder, file).replace("\\", "/")
            if full_path not in tocfiles:
                print(f"Removing orphaned file: {full_path}")
                os.remove(full_path)
