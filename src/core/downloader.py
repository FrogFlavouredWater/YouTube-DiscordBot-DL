# Allow core.player to be used for type hints without actually importing the file
# TYPE_CHECKING will be True when handling type hints but False in runtime
#* (Experimental)
from __future__ import annotations # < assume all type hints are strings so we don't have to put quotes around them
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.player import PlayerHandler

import os
import re
import time
import asyncio
import yt_dlp
import json
import discord
from core import utils

MAX_AUDIO_FILES = 50
YOUTUBE_MATCH_STRING = r"""(?:.*youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|.*youtu\.be\/)([^"&?\/\s]{11})"""
SOUNDCLOUD_MATCH_STRING = r"""(?:https?:\/\/)?(?:(?:www\.)|(?:m\.))?soundcloud\.com\/([\w-]{1,23})(?:\/)([\w-]{1,23})(?:\/.*)*"""

class PlayerError(Exception): pass
class VideoDownloadError(PlayerError): pass
class VideoTooLargeError(VideoDownloadError): pass

class DownloaderHandler:
    def __init__(self, client: discord.Client, player: PlayerHandler):
        self.client = client
        self.player = player

    @classmethod
    def match_service_and_id(cls, url: str):
        youtube_match = re.match(
            YOUTUBE_MATCH_STRING,
            url, flags=re.IGNORECASE
        )
        if youtube_match:
            return "YouTube", youtube_match

        soundcloud_match = re.match(
            SOUNDCLOUD_MATCH_STRING,
            url, flags=re.IGNORECASE
        )
        if soundcloud_match:
            return "SoundCloud", soundcloud_match

        return None, None


    async def download_and_play(self, interaction: discord.Interaction, conn: discord.VoiceClient, match: re.Match, service: str, link: str, toc: list, play_now: bool = False):
        filename = '.'.join(match.groups())

        # Check if file already exists in TOC
        for i, item in enumerate(toc):
            if item['file'] == f"data/music/{service}/{filename}.opus":
                toc[i]['timestamp'] = round(time.time())  # update access time
                with open("data/toc.json", 'w') as f:
                    json.dump(toc, f)

                if play_now:
                    conn.stop()
                    embed = self.player.add_to_queue(metadata=item, conn=conn, invoker=interaction.user.name, pos=1, skip=True)
                else:
                    embed = self.player.add_to_queue(metadata=item, conn=conn, invoker=interaction.user.name)
                return embed

        await interaction.response.defer(ephemeral=True)

        ydl_opts = {
            'outtmpl': f'data/music/{service}/{filename}.%(ext)s',
            'format': 'bestaudio/best',
            'noplaylist': True,
            'max-filesize': "25M",
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'opus',
                'preferredquality': '192',
            }],
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=False)

            try:
                duration = info.get('duration', 0)
                if duration >= 900:
                    raise VideoTooLargeError("Video too long (must be below 15 minutes)")

            except VideoTooLargeError as e:
                await interaction.followup.send(str(e), ephemeral=True)
                return
            except Exception as e:
                await interaction.followup.send(f"Download failed: {e}", ephemeral=True)
                return
            
            ydl.download(link)

        metadata = {
            'title': info['title'],
            'id': info['id'],
            'file': f"data/music/{service}/{filename}.opus",
            'service': service,
            'duration': info['duration'],
            'timestamp': round(time.time())
        }
        toc.append(metadata)

        # Enforce TOC size limit
        if len(toc) > MAX_AUDIO_FILES:
            toc.sort(key=lambda x: x['timestamp'], reverse=True)
            while len(toc) > MAX_AUDIO_FILES:
                old = toc.pop()
                try:
                    os.remove(old['file'])
                except Exception as e:
                    print(f"Error deleting {old['file']}: {e}")

        with open("data/toc.json", 'w') as f:
            json.dump(toc, f)

        if play_now:
            conn.stop()
            embed = self.player.add_to_queue(metadata=metadata, conn=conn, invoker=interaction.user.name, pos=1, skip=True)
        else:
            embed = self.player.add_to_queue(metadata=metadata, conn=conn, invoker=interaction.user.name)
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        await conn.channel.edit(status=f"🎶 {service}: {metadata['title']}")
