import discord
from core import utils
from core.log_config import logger, log_failed

class PlayerHandler:
    def __init__(self, client: discord.Client):
        self.queues = {}
        self.client = client

    async def play_audio_file(self, conn, filename, service=None, folder="music", message=None, queuer=None):
        path = f"data/{folder}/{service + '/' if service else ''}{filename}"
        logger.debug(f"Attempting to play file: {path}")
        try:
            conn.play(
                discord.FFmpegOpusAudio(path),
                after=lambda error=None, conn=conn: self.after_track(error, conn)
            )
        except Exception as e:
            log_failed(f"Playback error: {e}")
            return None
        else:
            embed = utils.create_embed(
                title="Now Playing",
                description=message or filename,
                color=0x1DB954,
                queue_list="\n".join([s['title'] for s in self.queues[conn.guild.id]['queue'][1:]]) if conn.guild.id in self.queues else None,
                song_queuer=str(queuer) if queuer else "Unknown"
            )
            logger.info(f"Now playing: {filename} queued by {queuer}")
            return embed

    def after_track(self, error, conn):
        server_id = conn.guild.id
        if error:
            log_failed(f"Error during playback: {error}")
        else:
            logger.debug(f"Track finished on guild {server_id}")

        try:
            if not self.queues[server_id]['loop']:
                self.queues[server_id]['queue'].pop(0)
        except KeyError:
            logger.debug("Queue already cleared or disconnected.")
            return

        try:
            next_file = self.queues[server_id]['queue'][0]
            logger.debug(f"Playing next track: {next_file['title']} ({next_file['file']})")

            conn.play(
                discord.FFmpegOpusAudio(next_file['file']),
                after=lambda err=None, conn=conn: self.after_track(err, conn)
            )

            self.client.loop.create_task(
                conn.channel.edit(status=f"🎶 {next_file['service']}: {next_file['title']}")
            )
        except IndexError:
            logger.debug(f"No more tracks in queue for guild {server_id}")
            self.queues.pop(server_id, None)

    def add_to_queue(self, metadata: dict, conn: discord.VoiceClient, invoker: discord.User = None, pos: int = -1, skip: bool = False):
        try:
            if pos < 0:
                self.queues[conn.guild.id]['queue'].append(metadata)
            else:
                self.queues[conn.guild.id]['queue'].insert(pos, metadata)
            logger.info(f"Track queued: {metadata['title']} (pos={pos}) by {invoker}")
            
            if not skip:
                embed = utils.create_embed(
                    title=f"Added to queue ({len(self.queues[conn.guild.id]['queue'])-1})",
                    description=metadata['title'],
                    color=0x1DB954,
                    queue_list=[],
                    song_queuer=invoker
                )
                return embed
        except KeyError:
            self.queues[conn.guild.id] = {'queue': [metadata], 'loop': False}
            logger.info(f"New queue created and track added: {metadata['title']}")

        conn.play(
            discord.FFmpegOpusAudio(metadata['file']),
            after=lambda err=None, conn=conn: self.after_track(err, conn)
        )

        embed = utils.create_embed(
            title="Now Playing",
            description=metadata['title'],
            color=0x1DB954,
            queue_list=[],
            song_queuer=invoker
        )
        return embed

    async def connect_and_prepare(self, interaction: discord.Interaction) -> discord.VoiceClient | None:
        conn = interaction.guild.voice_client

        if not conn:
            try:
                channel = interaction.user.voice.channel
            except AttributeError:
                await interaction.response.send_message("Not connected to a voice channel", ephemeral=True)
                return None

            conn = await channel.connect()
            logger.info(f"Connected to voice channel: {channel.name} in guild {interaction.guild.name}")

        return conn

    async def safe_disconnect(self, conn: discord.VoiceClient):
        if not conn.is_playing():
            await conn.disconnect()
            logger.info(f"Disconnected from voice channel in guild {conn.guild.name}")
