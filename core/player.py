import discord
from datetime import datetime

queues = {}

def create_embed(title, description, color, song_name, queue_list, song_queuer):
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=datetime.utcnow()
    )

    if song_name:
        embed.add_field(name="Currently Playing", value=song_name, inline=False)
    if queue_list:
        embed.add_field(name="Other Songs in Queue", value="\n".join(queue_list), inline=False)
    if song_queuer:
        embed.add_field(
            name="Requested by",
            value=song_queuer.mention if hasattr(song_queuer, 'mention') else str(song_queuer),
            inline=False
        )

    embed.set_footer(text="Requested via /play")
    return embed


async def play_audio_file(vc_conn, filename, service=None, folder="music", message=None, after=None, queuer=None):
    from core.player import queues

    path = f"data/{folder}/{service + '/' if service else ''}{filename}"
    try:
        vc_conn.play(discord.FFmpegOpusAudio(path), after=after)
    except Exception as e:
        print(f"Playback error: {e}")
        return None
    else:
        embed = create_embed(
            title="Now Playing",
            description=message or filename,
            color=0x1DB954,
            song_name=message or filename,
            queue_list="\n".join([s['title'] for s in queues[vc_conn.guild.id]['queue'][1:]]) if vc_conn.guild.id in queues else None,
            song_queuer=str(queuer) if queuer else "Unknown"
        )
        return embed


def after_track(error, connection):
    from core.player import queues
    import asyncio
    from main import client  # assumes client object is defined in bot.py

    server_id = connection.guild.id
    if error:
        print(f"Error during playback: {error}")
    try:
        if not queues[server_id]['loop']:
            queues[server_id]['queue'].pop(0)
    except KeyError:
        return  # likely already disconnected

    try:
        next_file = queues[server_id]['queue'][0]
        connection.play(
            discord.FFmpegOpusAudio(next_file['file']),
            after=lambda err=None, conn=connection: after_track(err, conn)
        )
        asyncio.run_coroutine_threadsafe(
            connection.channel.edit(status=f"🎶 {next_file['service']}: {next_file['title']}"),
            client.loop
        )
    except IndexError:
        queues.pop(server_id, None)
        asyncio.run_coroutine_threadsafe(safe_disconnect(connection), client.loop).result()


async def connect_and_prepare(interaction: discord.Interaction) -> discord.VoiceClient | None:
    vc_conn = interaction.guild.voice_client

    if not vc_conn:
        try:
            channel = interaction.user.voice.channel
        except AttributeError:
            await interaction.response.send_message("Not connected to a voice channel", ephemeral=True)
            return None

        vc_conn = await channel.connect()

    return vc_conn


async def safe_disconnect(connection: discord.VoiceClient):
    if not connection.is_playing():
        await connection.disconnect()


def cleanup_orphaned_files(toc):
    import os
    tocfiles = [entry['file'] for entry in toc]

    for folder, _, files in os.walk("data/music"):
        for file in files:
            full_path = os.path.join(folder, file).replace("\\", "/")
            if full_path not in tocfiles:
                print(f"Removing orphaned file: {full_path}")
                os.remove(full_path)
