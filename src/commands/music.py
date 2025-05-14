# Allow core.downloader to be used for type hints without actually importing the file
# TYPE_CHECKING will be True when handling type hints but False in runtime
#* (Experimental)
from __future__ import annotations # < assume all type hints are strings so we don't have to put quotes around them
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.downloader import DownloaderHandler

import os
import json
import random
import discord
from discord import app_commands
from core import utils

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
    audiofolders += dirnames
    folder = dirpath.replace('\\','/')[13:]
    for f in filenames:
        audiofiles.append(f"{folder}/{f}".strip('/')) # Trim off the base path

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
class MusicCommands():
    def __init__(self, tree: app_commands.CommandTree, guilds: list, downloader: DownloaderHandler):
        self.tree = tree
        self.guilds = guilds
        self.downloader = downloader
        self.player = downloader.player
        self.register_commands()

    def register_commands(self):
        """Called on MusicCommands()"""
        tree = self.tree
        guilds = self.guilds

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
                queue = self.player.queues[interaction.guild.id]['queue']
            except KeyError:
                await interaction.response.send_message("No active playback", ephemeral=True)
                return

            if n_skips <= 0 or n_skips >= len(queue):
                skipped = len(queue)
                self.player.queues[interaction.guild.id]['queue'] = []
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
                info = self.player.queues[interaction.guild.id]
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
                looping = self.player.queues[interaction.guild.id]['loop']
                self.player.queues[interaction.guild.id]['loop'] = not looping
                await interaction.response.send_message(f"Looping is now {'on' if not looping else 'off'}.", ephemeral=True)
            except KeyError:
                await interaction.response.send_message("No active queue.", ephemeral=True)

        @tree.command(name="shuffle", description="Toggle shuffle mode", guilds=guilds)
        async def shuffle(interaction: discord.Interaction):
            try:
                self.player.queues[interaction.guild.id]['shuffle'] ^= True
                status = "enabled" if self.player.queues[interaction.guild.id]['shuffle'] else "disabled"
                await interaction.response.send_message(f"Shuffle is now {status}.", ephemeral=True)
            except KeyError:
                await interaction.response.send_message("No active queue.", ephemeral=True)

        @tree.command(name="jukebox", description="Play a local jukebox file", guilds=guilds)
        @app_commands.describe(file="The name of the file")
        async def jukebox(interaction: discord.Interaction, file: str):
            conn = await self.player.connect_and_prepare(interaction)
            if not conn:
                return
            if os.path.isfile(f"data/jukebox/{file}"):
                metadata = {
                    'title': file,
                    'file': f"data/jukebox/{file}",
                    'service': 'Jukebox',
                }
                embed = self.player.add_to_queue(
                    metadata=metadata,
                    conn=conn,
                    invoker=interaction.user.name
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)

        @jukebox.autocomplete("file")
        async def autocomplete_jukebox(interaction: discord.Interaction, query: str) -> list[app_commands.Choice[str]]:
            query = query.lower()
            result = []
            search_contains = True
            if query:
                for i in audiofiles:
                    if i.lower().startswith(query):
                        result.append(app_commands.Choice(name=i[:-5],value=i))
                        search_contains = False
            if search_contains:
                for i in audiofolders:
                    if query in i.lower():
                        result.append(app_commands.Choice(name=i+'/', value=i))
                for i in audiofiles:
                    if '/' not in i and query in i.lower():
                        result.append(app_commands.Choice(name=i[:-5], value=i))

            return result[:25] if len(result) > 25 else result
        
        @tree.command(name="createjb", description="Add a jukebox entry", guilds=guilds)
        @app_commands.describe(link="The video or audio link", filename="The filename to save as (with .opus extension)")
        async def createjb(interaction: discord.Interaction, link: str, filename: str):
            vc_conn = await self.player.connect_and_prepare(interaction)
            if not vc_conn:
                return

            service, match = self.downloader.match_service_and_id(link)
            if not (service and match):
                await interaction.response.send_message("Invalid URL or unsupported service.", ephemeral=True)
                return

            # Download to data/jukebox/filename
            import yt_dlp
            import time

            jukebox_path = f"data/jukebox/{filename}"
            ydl_opts = {
                'outtmpl': jukebox_path,
                'format': 'bestaudio/best',
                'noplaylist': True,
                'max-filesize': "25M",
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'opus',
                    'preferredquality': '192',
                }],
            }

            await interaction.response.defer(ephemeral=True)
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(link, download=True)
            except Exception as e:
                await interaction.followup.send(f"Download failed: {e}", ephemeral=True)
                return

            # Add to jukebox index (optional: you can skip this if not needed)
            metadata = {
                'title': filename,
                'file': jukebox_path.replace("\\", "/"),
                'service': 'Jukebox',
                'duration': info.get('duration', 0),
                'timestamp': round(time.time())
            }
            # Optionally, you could update a jukebox TOC here

            embed = self.player.add_to_queue(
                metadata=metadata,
                conn=vc_conn,
                invoker=interaction.user.name
            )
            await interaction.followup.send(f"Downloaded and added `{filename}` to the jukebox!", embed=embed, ephemeral=True)
        
        @tree.command(name="add", description="Add a YouTube or SoundCloud URL to the queue", guilds=guilds)
        @app_commands.describe(link="The video or audio link")
        async def add(interaction: discord.Interaction, link: str):
            vc_conn = await self.player.connect_and_prepare(interaction)
            if not vc_conn:
                return

            service, match = self.downloader.match_service_and_id(link)
            if service and match:
                await self.downloader.download_and_play(interaction, vc_conn, match, service, link, toc, play_now=False)
            else:
                await interaction.response.send_message("Invalid URL or unsupported service.", ephemeral=True)

        @tree.command(name="play", description="Play a YouTube or SoundCloud URL", guilds=guilds)
        @app_commands.describe(link="The video or audio link")
        async def play(interaction: discord.Interaction, link: str):
            vc_conn = await self.player.connect_and_prepare(interaction)
            if not vc_conn:
                return

            service, match = self.downloader.match_service_and_id(link)
            if service and match:
                await self.downloader.download_and_play(interaction, vc_conn, match, service, link, toc, play_now=True)
            else:
                await interaction.response.send_message("Invalid URL or unsupported service.", ephemeral=True)

        @tree.command(name="playlist", description="Play a local playlist folder", guilds=guilds)
        @app_commands.describe(name="The playlist folder name")
        async def playlist(interaction: discord.Interaction, name: str):
            # TODO: Add predefined list to queue
            vc_conn = await self.player.connect_and_prepare(interaction)
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
                queue = self.player.queues[interaction.guild.id]['queue']
                queue.extend(playlist_items)
                queue[:] = deduplicate_queue(queue)

                if self.player.queues[interaction.guild.id].get("shuffle") and len(queue) > 1:
                    first = queue[0]
                    rest = deduplicate_queue(queue[1:])
                    random.shuffle(rest)
                    self.player.queues[interaction.guild.id]['queue'] = [first] + rest

                await interaction.response.send_message(f"Queued {len(playlist_items)} tracks from playlist `{name}`.", ephemeral=True)
            except KeyError:
                deduped = deduplicate_queue(playlist_items)
                self.player.queues[interaction.guild.id] = {
                    'queue': deduped,
                    'loop': False,
                    'shuffle': False
                }
                vc_conn.play(
                    discord.FFmpegOpusAudio(deduped[0]['file']),
                    after=lambda err=None, conn=vc_conn: self.player.after_track(err, conn)
                )
                embed = utils.create_embed(
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
