import os
import json
import random
import discord
from discord import app_commands
from core import player, downloader
from core.player import queues, connect_and_prepare, play_audio_file, safe_disconnect
from core.downloader import match_service_and_id, download_and_play

# Load the Table of Contents (TOC) for previously downloaded music
with open("data/toc.json", "r") as f:
    toc = list(f.read())
    if isinstance(toc, str):  # If JSON is malformed or empty, fall back to an empty list
        toc = []
    else:
        toc = list(json.load(open("data/toc.json")))

# Load and index audio files and directories from jukebox folder
audiofiles = []
audiofolders = []
for dirpath, dirnames, filenames in os.walk("data/jukebox"):
    audiofolders.extend(dirnames)
    for f in filenames:
        audiofiles.append(os.path.join(dirpath, f)[13:])  # Trim off the base path

# Sort the jukebox file list for consistent ordering
audiofiles.sort()

# Load available playlist folders
playlistfolders = []
for item in os.listdir("data/playlists"):
    path = os.path.join("data/playlists", item)
    if os.path.isdir(path):
        playlistfolders.append(item)

playlistfolders.sort()

def deduplicate_queue(queue):
    seen = set()
    deduped = []
    for track in queue:
        if track['file'] not in seen:
            seen.add(track['file'])
            deduped.append(track)
    return deduped

# Register all application commands to the command tree
def register_commands(tree: app_commands.CommandTree, guilds: list):

    @tree.command(name="pause", description="Pause the currently playing audio", guilds=guilds)
    async def pause(interaction: discord.Interaction):
        vc_conn = interaction.guild.voice_client
        if vc_conn and vc_conn.is_playing():
            try:
                vc_conn.pause()
            except:
                pass
            await interaction.response.send_message("Playback paused", ephemeral=True)
        else:
            await interaction.response.send_message("Nothing is playing.", ephemeral=True)

    @tree.command(name="resume", description="Resume paused audio", guilds=guilds)
    async def resume(interaction: discord.Interaction):
        vc_conn = interaction.guild.voice_client
        if vc_conn and vc_conn.is_paused():
            try:
                vc_conn.resume()
            except:
                pass
            await interaction.response.send_message("Resuming", ephemeral=True)
        else:
            await interaction.response.send_message("Nothing is paused.", ephemeral=True)

    @tree.command(name="stop", description="Stop playback and leave the voice channel", guilds=guilds)
    async def stop(interaction: discord.Interaction):
        vc_conn = interaction.guild.voice_client
        if vc_conn:
            await vc_conn.channel.edit(status=None)
            await vc_conn.disconnect()
            await interaction.response.send_message("Disconnected", ephemeral=True)
        else:
            await interaction.response.send_message("Not connected.", ephemeral=True)

    @tree.command(name="skip", description="Skip one or more tracks", guilds=guilds)
    @app_commands.describe(n_skips="Number of tracks to skip (0 to skip all)")
    async def skip(interaction: discord.Interaction, n_skips: int = 1):
        try:
            queue = queues[interaction.guild.id]['queue']
        except KeyError:
            await interaction.response.send_message("No active playback", ephemeral=True)
            return

        if n_skips <= 0 or n_skips >= len(queue):
            skipped = len(queue)
            queues[interaction.guild.id]['queue'] = []
            interaction.guild.voice_client.stop()
            await interaction.response.send_message(f"Skipped all {skipped} tracks.", ephemeral=True)
            return

        for _ in range(n_skips - 1):
            queue.pop(0)
        interaction.guild.voice_client.stop()
        await interaction.response.send_message(f"Skipped {n_skips} track(s)", ephemeral=True)

    @tree.command(name="nextup", description="Show upcoming tracks in the queue", guilds=guilds)
    async def nextup(interaction: discord.Interaction):
        try:
            info = queues[interaction.guild.id]
        except KeyError:
            await interaction.response.send_message("No queue active.", ephemeral=True)
            return

        embed = discord.Embed(
            title="Queue",
            color=discord.Color.blurple()
        )

        for i, song in enumerate(info["queue"]):
            if i == 0:
                label = "LOOPING" if info["loop"] else "NOW PLAYING"
                embed.add_field(name=f"{label}", value=song['title'], inline=False)
            else:
                embed.add_field(name=f"{i}.", value=song['title'], inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @tree.command(name="loop", description="Toggle loop mode", guilds=guilds)
    async def loop(interaction: discord.Interaction):
        try:
            looping = queues[interaction.guild.id]['loop']
            queues[interaction.guild.id]['loop'] = not looping
            await interaction.response.send_message(f"Looping is now {'on' if not looping else 'off'}.", ephemeral=True)
        except KeyError:
            await interaction.response.send_message("No active queue.", ephemeral=True)

    @tree.command(name="shuffle", description="Toggle shuffle mode", guilds=guilds)
    async def shuffle(interaction: discord.Interaction):
        try:
            queues[interaction.guild.id]['shuffle'] ^= True
            status = "enabled" if queues[interaction.guild.id]['shuffle'] else "disabled"
            await interaction.response.send_message(f"Shuffle is now {status}.", ephemeral=True)
        except KeyError:
            await interaction.response.send_message("No active queue.", ephemeral=True)

    @tree.command(name="jukebox", description="Play a local jukebox file", guilds=guilds)
    @app_commands.describe(file="The name of the file")
    async def jukebox(interaction: discord.Interaction, file: str):
        vc_conn = await connect_and_prepare(interaction)
        if not vc_conn:
            return
        if os.path.isfile(f"data/jukebox/{file}"):
            embed = await play_audio_file(
                vc_conn, file, folder="jukebox", queuer=interaction.user
            )
            if embed:
                await interaction.response.send_message(embed=embed, ephemeral=True)
                await vc_conn.channel.edit(status=f"🎶 Jukebox: {file[:-5]}")
            else:
                await interaction.response.send_message("Playback error.", ephemeral=True)

    @jukebox.autocomplete("file")
    async def autocomplete_jukebox(interaction: discord.Interaction, query: str):
        result = []
        q = query.lower()

        for f in audiofiles:
            if q in f.lower():
                result.append(app_commands.Choice(name=f[:-5], value=f))

        for d in audiofolders:
            if q in d.lower():
                result.append(app_commands.Choice(name=d + "/", value=d))

        return result[:25]

    @tree.command(name="play", description="Play a YouTube or SoundCloud URL", guilds=guilds)
    @app_commands.describe(link="The video or audio link")
    async def play(interaction: discord.Interaction, link: str):
        vc_conn = await connect_and_prepare(interaction)
        if not vc_conn:
            return

        service, match = match_service_and_id(link)
        if service and match:
            await download_and_play(interaction, vc_conn, match, service, link, toc)

            q = queues[interaction.guild.id]
            if q.get("shuffle") and len(q["queue"]) > 1:
                first = q["queue"][0]
                rest = deduplicate_queue(q["queue"][1:])
                random.shuffle(rest)
                q["queue"] = [first] + rest
        else:
            await interaction.response.send_message("Invalid URL or unsupported service.", ephemeral=True)

    @tree.command(name="playlist", description="Play a local playlist folder", guilds=guilds)
    @app_commands.describe(name="The playlist folder name")
    async def playlist(interaction: discord.Interaction, name: str):
        vc_conn = await connect_and_prepare(interaction)
        if not vc_conn:
            return

        folder_path = os.path.join("data/playlists", name)
        if not os.path.isdir(folder_path):
            await interaction.response.send_message("Playlist not found.", ephemeral=True)
            return

        files = [
            f for f in os.listdir(folder_path)
            if os.path.isfile(os.path.join(folder_path, f)) and f.endswith(".opus")
        ]
        if not files:
            await interaction.response.send_message("Playlist is empty.", ephemeral=True)
            return

        playlist_items = []
        for file in sorted(files):
            full_path = os.path.join(folder_path, file)
            playlist_items.append({
                'title': file[:-5],
                'id': file[:-5],
                'file': full_path.replace("\\", "/"),
                'service': "Playlist",
                'duration': 0,
                'timestamp': 0
            })

        try:
            queue = queues[interaction.guild.id]['queue']
            queue.extend(playlist_items)
            queue[:] = deduplicate_queue(queue)

            if queues[interaction.guild.id].get("shuffle") and len(queue) > 1:
                first = queue[0]
                rest = deduplicate_queue(queue[1:])
                random.shuffle(rest)
                queues[interaction.guild.id]['queue'] = [first] + rest

            await interaction.response.send_message(f"Queued {len(playlist_items)} tracks from playlist `{name}`.", ephemeral=True)
        except KeyError:
            deduped = deduplicate_queue(playlist_items)
            queues[interaction.guild.id] = {
                'queue': deduped,
                'loop': False,
                'shuffle': False
            }
            vc_conn.play(
                discord.FFmpegOpusAudio(deduped[0]['file']),
                after=lambda err=None, conn=vc_conn: player.after_track(err, conn)
            )
            embed = player.create_embed(
                title="Now Playing",
                description=deduped[0]['title'],
                color=0x1DB954,
                song_name=deduped[0]['title'],
                queue_list=[s['title'] for s in deduped[1:]],
                song_queuer=interaction.user
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @playlist.autocomplete("name")
    async def autocomplete_playlist(interaction: discord.Interaction, query: str):
        q = query.lower()
        return [
            app_commands.Choice(name=f, value=f)
            for f in playlistfolders if q in f.lower()
        ][:25]
