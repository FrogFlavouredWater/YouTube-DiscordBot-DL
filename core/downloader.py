import os
import re
import time
import asyncio
import yt_dlp
import json
import discord
from discord import app_commands
from core.player import queues, create_embed, after_track, play_audio_file

MAX_AUDIO_FILES = 50

class PlayerError(Exception): pass
class VideoDownloadError(PlayerError): pass
class VideoTooLargeError(VideoDownloadError): pass


def match_service_and_id(url: str):
    youtube_match = re.match(
        r"""(?:.*youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|.*youtu\.be\/)([^"&?\/\s]{11})""",
        url, flags=re.IGNORECASE
    )
    if youtube_match:
        return "YouTube", youtube_match

    soundcloud_match = re.match(
        r"""(?:https?:\/\/)?(?:(?:www\.)|(?:m\.))?soundcloud\.com\/([\w-]{1,23})(?:\/)([\w-]{1,23})(?:\/.*)*""",
        url, flags=re.IGNORECASE
    )
    if soundcloud_match:
        return "SoundCloud", soundcloud_match

    return None, None


async def download_and_play(interaction, vc_conn, match: re.Match, service: str, link: str, toc: list):
    filename = '.'.join(match.groups())

    # Check if file already exists in TOC
    for i, item in enumerate(toc):
        if item['file'] == f"data/music/{service}/{filename}.opus":
            toc[i]['timestamp'] = round(time.time())  # update access time
            with open("data/toc.json", 'w') as f:
                json.dump(toc, f)

            try:
                queues[vc_conn.guild.id]['queue'].append(item)
                msg = f"Added `{item['title']}` from {service} to queue"
                if interaction.response.is_done():
                    await interaction.followup.send(msg, ephemeral=True)
                else:
                    await interaction.response.send_message(msg, ephemeral=True)
            except KeyError:
                queues[vc_conn.guild.id] = {'queue': [item], 'loop': False}
                embed = await play_audio_file(
                    vc_conn, filename + ".opus", service,
                    message=item['title'],
                    after=lambda error=None, conn=vc_conn: after_track(error, conn),
                    queuer=interaction.user
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
            return

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

    def sync_download():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(link, download=True)

    try:
        info = await asyncio.to_thread(sync_download)
        duration = info.get('duration', 0)
        if duration >= 900:
            raise VideoTooLargeError("Video too long (must be below 15 minutes)")

    except VideoTooLargeError as e:
        await interaction.followup.send(str(e), ephemeral=True)
        return
    except Exception as e:
        await interaction.followup.send(f"Download failed: {e}", ephemeral=True)
        return

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

    try:
        queues[vc_conn.guild.id]['queue'].append(metadata)
    except KeyError:
        queues[vc_conn.guild.id] = {'queue': [metadata], 'loop': False}
        vc_conn.play(
            discord.FFmpegOpusAudio(metadata['file']),
            after=lambda err=None, conn=vc_conn: after_track(err, conn)
        )
        embed = create_embed(
            title="Now Playing",
            description=metadata['title'],
            color=0x1DB954,
            song_name=metadata['title'],
            queue_list=[],
            song_queuer=str(interaction.user)
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

        await vc_conn.channel.edit(status=f"🎶 {service}: {metadata['title']}")
