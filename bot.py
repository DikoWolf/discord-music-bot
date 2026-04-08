import os
import sys
import asyncio
import time
from collections import deque

import discord
from discord.ext import commands
from dotenv import load_dotenv
import yt_dlp
import aiohttp
import urllib.parse

load_dotenv()
TOKEN = os.getenv("TOKEN")

FFMPEG_PATH = r"C:\Users\DikoW\Desktop\discord-music-bot\ffmpeg-2026-04-01-git-eedf8f0165-full_build\ffmpeg-2026-04-01-git-eedf8f0165-full_build\bin\ffmpeg.exe"

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

ytdl_format_options = {
    "format": "bestaudio/best",
    "outtmpl": "%(extractor)s-%(id)s-%(title)s.%(ext)s",
    "restrictfilenames": True,
    "noplaylist": True,
    "nocheckcertificate": True,
    "ignoreerrors": False,
    "quiet": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "headers": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    },
    "cookiefile": "cookies.txt",
    "extractor_args": {
        "youtube": {
            "player_skip": ["webpage", "configs", "js"],
            "player_client": ["android"],
        }
    },
}

# Config untuk search - allow multiple results
ytdl_search_options = {
    "format": "bestaudio/best",
    "restrictfilenames": True,
    "nocheckcertificate": True,
    "ignoreerrors": True,
    "quiet": True,
    "source_address": "0.0.0.0",
    "extract_flat": True,
    "playlistend": 10,
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "cookiefile": "cookies.txt",
}

ffmpeg_options = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)
ytdl_search = yt_dlp.YoutubeDL(ytdl_search_options)


async def fetch_lyrics(artist: str, title: str) -> tuple[str, str]:
    """Fetch lyrics dari multiple sources. Returns (lyrics, source) atau (None, None)"""
    
    # Try 1: lyrics.ovh (API - paling mudah)
    try:
        artist_enc = urllib.parse.quote(artist)
        title_enc = urllib.parse.quote(title)
        url = f"https://api.lyrics.ovh/v1/{artist_enc}/{title_enc}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    lyrics = data.get("lyrics", "").strip()
                    if lyrics:
                        return (lyrics, "lyrics.ovh")
    except Exception as e:
        print(f"lyrics.ovh failed: {e}")
    
    # Try 2: lyrics.my (Scrape - untuk lagu Melayu)
    try:
        # Format: https://www.lyrics.my/artis/<artist>/lagu/<title>
        artist_fmt = artist.replace(" ", "-").lower()
        title_fmt = title.replace(" ", "-").lower()
        url = f"https://www.lyrics.my/artis/{artist_fmt}/lagu/{title_fmt}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    # Simple regex to extract lyrics
                    import re
                    # Look for lyrics content div
                    match = re.search(r'<div class="lyrics-content">(.*?)</div>', html, re.DOTALL)
                    if match:
                        lyrics = re.sub(r'<[^>]+>', '', match.group(1))  # Remove HTML tags
                        lyrics = lyrics.strip()
                        if lyrics:
                            return (lyrics, "lyrics.my")
    except Exception as e:
        print(f"lyrics.my failed: {e}")
    
    # Try 3: Genius (Search + Scrape - authority untuk English)
    try:
        query = f"{artist} {title}"
        search_url = f"https://genius.com/api/search/multi?q={urllib.parse.quote(query)}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        async with aiohttp.ClientSession() as session:
            # Search for song
            async with session.get(search_url, headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    hits = data.get("response", {}).get("sections", [{}])[0].get("hits", [])
                    
                    if hits:
                        # Get first hit URL
                        song_url = hits[0].get("result", {}).get("url")
                        if song_url:
                            # Fetch lyrics page
                            async with session.get(song_url, headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as lyric_resp:
                                if lyric_resp.status == 200:
                                    html = await lyric_resp.text()
                                    import re
                                    # Genius stores lyrics in divs with data-lyrics-container attribute
                                    matches = re.findall(r'<div[^>]*data-lyrics-container="true"[^>]*>(.*?)</div>', html, re.DOTALL)
                                    if matches:
                                        lyrics = "\n".join(matches)
                                        lyrics = re.sub(r'<[^>]+>', '', lyrics)  # Remove HTML
                                        lyrics = lyrics.replace("&amp;", "&")  # Fix HTML entities
                                        lyrics = lyrics.replace("&#x27;", "'")  # Fix apostrophe
                                        lyrics = lyrics.replace("&quot;", '"')  # Fix quotes
                                        
                                        # Remove translation headers
                                        lyrics = re.sub(r'ContributorTranslations.*?(?=[\[\n])', '', lyrics, flags=re.DOTALL)
                                        lyrics = re.sub(r'[A-Za-z]+Translation.*?(?=[\[\n])', '', lyrics)
                                        
                                        # Clean up extra whitespace
                                        lyrics = lyrics.replace("\n\n\n", "\n\n").strip()
                                        if lyrics and len(lyrics) > 50:
                                            return (lyrics, "Genius")
    except Exception as e:
        print(f"Genius failed: {e}")
    
    # Try 4: AZLyrics (Authority website - last resort)
    try:
        # Format: https://www.azlyrics.com/lyrics/<artist>/<title>.html
        artist_fmt = artist.lower().replace(" ", "")
        title_fmt = title.lower().replace(" ", "")
        # Remove special characters
        import re
        artist_fmt = re.sub(r'[^a-z0-9]', '', artist_fmt)
        title_fmt = re.sub(r'[^a-z0-9]', '', title_fmt)
        
        url = f"https://www.azlyrics.com/lyrics/{artist_fmt}/{title_fmt}.html"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    import re
                    # AZLyrics lyrics are in a div with no class, between comments
                    match = re.search(r'<!-- Usage of azlyrics\.com content.*?-->(.*?)<!-- MxM banner -->', html, re.DOTALL)
                    if match:
                        lyrics = match.group(1)
                        lyrics = re.sub(r'<[^>]+>', '', lyrics)  # Remove HTML tags
                        lyrics = lyrics.replace("\r\n", "\n").strip()
                        if lyrics and len(lyrics) > 50:  # Make sure it's actual lyrics
                            return (lyrics, "AZLyrics")
    except Exception as e:
        print(f"AZLyrics failed: {e}")
    
    return (None, None)


def format_lyrics_sections(lyrics: str) -> str:
    """Format lyrics dengan proper section labels [Intro], [Chorus], [Verse], [Bridge], dll"""
    import re
    
    # Common section patterns
    section_patterns = [
        (r'\[Intro[^\]]*\]', '[Intro]'),
        (r'\[Verse\s*\d*[^\]]*\]', None),  # Keep original [Verse 1], [Verse 2], etc
        (r'\[Pre-Chorus[^\]]*\]', '[Pre-Chorus]'),
        (r'\[Chorus[^\]]*\]', '[Chorus]'),
        (r'\[Post-Chorus[^\]]*\]', '[Post-Chorus]'),
        (r'\[Bridge[^\]]*\]', '[Bridge]'),
        (r'\[Outro[^\]]*\]', '[Outro]'),
        (r'\[Hook[^\]]*\]', '[Hook]'),
        (r'\[Refrain[^\]]*\]', '[Refrain]'),
        (r'\[Interlude[^\]]*\]', '[Interlude]'),
    ]
    
    # Normalize existing section headers
    for pattern, replacement in section_patterns:
        if replacement:
            lyrics = re.sub(pattern, replacement, lyrics, flags=re.IGNORECASE)
    
    # Add spacing around section headers for readability
    lyrics = re.sub(r'(\[.+?\])\n', r'\n\1\n', lyrics)
    
    # Clean up multiple consecutive empty lines
    lyrics = re.sub(r'\n{4,}', '\n\n\n', lyrics)
    
    # Ensure section headers are properly capitalized
    def capitalize_section(match):
        section = match.group(0)
        # Keep the brackets, capitalize the content
        content = section[1:-1]
        return f"[{content.capitalize()}]"
    
    lyrics = re.sub(r'\[([a-z]+[^\]]*)\]', capitalize_section, lyrics)
    
    return lyrics.strip()


def format_duration(seconds: int) -> str:
    if not seconds:
        return "0:00"
    minutes, sec = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02}:{sec:02}"
    return f"{minutes}:{sec:02}"


def make_progress_bar(current: int, total: int, length: int = 16) -> str:
    if total <= 0:
        return "─" * length

    current = max(0, min(current, total))
    filled_pos = int((current / total) * (length - 1))
    bar = []

    for i in range(length):
        if i == filled_pos:
            bar.append("◉")
        else:
            bar.append("━")

    return "".join(bar)


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5, original_query=""):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get("title", "Unknown title")
        self.webpage_url = data.get("webpage_url", "")
        self.duration = int(data.get("duration", 0) or 0)
        self.thumbnail = data.get("thumbnail")
        self.original_query = original_query
        self.requester = None

    @classmethod
    async def from_query(cls, query, *, loop=None, volume=0.5, requester=None):
        loop = loop or asyncio.get_event_loop()

        data = await loop.run_in_executor(
            None,
            lambda: ytdl.extract_info(query, download=False)
        )

        if data is None:
            raise Exception("Tak jumpa audio untuk dimainkan.")

        if "entries" in data:
            data = data["entries"][0]
            if data is None:
                raise Exception("Tak jumpa hasil carian.")

        stream_url = data["url"]
        source = discord.FFmpegPCMAudio(
            stream_url,
            executable=FFMPEG_PATH,
            **ffmpeg_options
        )
        player = cls(source, data=data, volume=volume, original_query=query)
        player.requester = requester
        return player


class MusicPlayer:
    def __init__(self):
        self.queue = deque()
        self.history = []
        self.current = None
        self.current_query = None
        self.volume = 0.5
        self.is_playing = False
        self.is_looping = False
        self.control_message = None
        self.text_channel = None

        self.started_at = None
        self.paused_at = None
        self.pause_accumulated = 0
        self.progress_task = None


music_data = {}


def get_guild_player(guild_id: int) -> MusicPlayer:
    if guild_id not in music_data:
        music_data[guild_id] = MusicPlayer()
    return music_data[guild_id]


def get_elapsed_seconds(player: MusicPlayer, voice: discord.VoiceClient | None) -> int:
    if not player.current or not player.started_at:
        return 0

    now = time.time()

    if voice and voice.is_paused() and player.paused_at:
        elapsed = player.paused_at - player.started_at - player.pause_accumulated
    else:
        elapsed = now - player.started_at - player.pause_accumulated

    return max(0, int(elapsed))


async def play_next(guild: discord.Guild, channel: discord.TextChannel):
    """Main lagu seterusnya dalam queue"""
    voice = guild.voice_client
    player = get_guild_player(guild.id)

    if not voice:
        return

    if player.is_looping and player.current:
        # Kalau looping, main semula lagu yang sama
        query = player.current.webpage_url or player.current.original_query
        try:
            source = await YTDLSource.from_query(
                query, 
                loop=bot.loop, 
                volume=player.volume,
                requester=player.current.requester
            )
            player.current = source
            player.started_at = time.time()
            player.paused_at = None
            player.pause_accumulated = 0

            def after_playing(error):
                if error:
                    print(f"Player error: {error}")
                fut = asyncio.run_coroutine_threadsafe(
                    play_next(guild, channel), 
                    bot.loop
                )
                try:
                    fut.result(timeout=30)
                except Exception as e:
                    print(f"Error in after_playing: {e}")

            voice.play(source, after=after_playing)
            player.is_playing = True

            # Update now playing message
            await update_now_playing(guild, channel)
        except Exception as e:
            await channel.send(f"❌ Error mainkan lagu: {str(e)}")
            player.is_playing = False
            player.current = None
        return

    # Kalau tak looping, cek queue
    if player.queue:
        query = player.queue.popleft()

        # Simpan current dalam history sebelum play yang baru
        if player.current:
            player.history.append(player.current)

        try:
            source = await YTDLSource.from_query(
                query, 
                loop=bot.loop, 
                volume=player.volume,
                requester=None
            )
            player.current = source
            player.started_at = time.time()
            player.paused_at = None
            player.pause_accumulated = 0

            def after_playing(error):
                if error:
                    print(f"Player error: {error}")
                fut = asyncio.run_coroutine_threadsafe(
                    play_next(guild, channel), 
                    bot.loop
                )
                try:
                    fut.result(timeout=30)
                except Exception as e:
                    print(f"Error in after_playing: {e}")

            voice.play(source, after=after_playing)
            player.is_playing = True

            # Update now playing message
            await update_now_playing(guild, channel)
        except Exception as e:
            await channel.send(f"❌ Error mainkan lagu: {str(e)}")
            player.is_playing = False
            player.current = None
    else:
        # Queue kosong
        player.is_playing = False
        player.current = None


async def update_now_playing(guild: discord.Guild, channel: discord.TextChannel):
    """Update atau hantar now playing message"""
    player = get_guild_player(guild.id)

    if player.control_message:
        try:
            await player.control_message.delete()
        except:
            pass

    # Cancel existing progress task
    if player.progress_task:
        player.progress_task.cancel()
        player.progress_task = None

    if player.current:
        embed = make_now_playing_embed(guild)
        view = MusicControlsView(guild.id)
        player.control_message = await channel.send(embed=embed, view=view)
        
        # Start progress updater task
        player.progress_task = asyncio.create_task(
            progress_updater(guild, channel)
        )


async def progress_updater(guild: discord.Guild, channel: discord.TextChannel):
    """Background task untuk update progress bar setiap 1 saat"""
    player = get_guild_player(guild.id)
    
    while player.is_playing and player.current:
        try:
            await asyncio.sleep(1)  # Update every 1 second
            
            voice = guild.voice_client
            if not voice or not player.current:
                break
                
            # Skip update if paused
            if voice.is_paused():
                continue
            
            # Generate updated embed
            embed = make_now_playing_embed(guild)
            
            # Try to edit the existing message
            if player.control_message:
                try:
                    await player.control_message.edit(embed=embed)
                except discord.NotFound:
                    # Message was deleted, stop updating
                    break
                except Exception as e:
                    print(f"Error updating progress: {e}")
                    
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"Progress updater error: {e}")
            break
    
    player.progress_task = None


class HelpView(discord.ui.View):
    """View untuk bantuan dengan pagination"""
    def __init__(self, author: discord.User, timeout: float = 180):
        super().__init__(timeout=timeout)
        self.author = author
        self.current_page = 0
        self.total_pages = 3
        self.pages = self._build_pages()
        self._update_buttons()
    
    def _build_pages(self) -> list:
        """Build semua pages untuk help"""
        pages = []
        
        # Page 1: Music Commands
        page1 = discord.Embed(
            title="� Music Bot Help System",
            description="[ COMMANDS MUSIC ]\n\nCommands untuk main dan urus muzik.",
            color=discord.Color.from_rgb(88, 101, 242)
        )
        page1.add_field(
            name="🎶 !play <query>",
            value="Main lagu atau tambah ke queue\n*Contoh: !play never gonna give you up*",
            inline=False
        )
        page1.add_field(
            name="📃 !queue",
            value="Tunjuk senarai queue semasa",
            inline=True
        )
        page1.add_field(
            name="🎵 !now",
            value="Tunjuk lagu yang sedang dimainkan",
            inline=True
        )
        page1.add_field(
            name="📜 !lyrics [query]",
            value="Tunjuk lirik lagu semasa atau cari lirik",
            inline=False
        )
        page1.add_field(
            name="🔊 !volume <0-100>",
            value="Ubah volume player",
            inline=True
        )
        page1.add_field(
            name="🔁 !loop",
            value="On/Off loop lagu",
            inline=True
        )
        pages.append(page1)
        
        # Page 2: Playback Controls
        page2 = discord.Embed(
            title="🎵 Music Bot Help System",
            description="[ PLAYBACK CONTROLS ]\n\nCommands untuk kawal playback.",
            color=discord.Color.from_rgb(88, 101, 242)
        )
        page2.add_field(
            name="⏸️ !pause",
            value="Pause lagu semasa",
            inline=True
        )
        page2.add_field(
            name="▶️ !resume",
            value="Resume lagu yang di-pause",
            inline=True
        )
        page2.add_field(
            name="⏭️ !skip",
            value="Skip ke lagu seterusnya",
            inline=True
        )
        page2.add_field(
            name="⏮️ !previous",
            value="Main lagu sebelumnya",
            inline=True
        )
        page2.add_field(
            name="⏹️ !stop",
            value="Stop dan kosongkan queue",
            inline=True
        )
        page2.add_field(
            name="👋 !leave",
            value="Keluar dari voice channel",
            inline=True
        )
        pages.append(page2)
        
        # Page 3: Admin Commands
        page3 = discord.Embed(
            title="🎵 Music Bot Help System",
            description="[ COMMANDS ADMIN ]\n\nCommands yang memerlukan kebenaran admin.",
            color=discord.Color.from_rgb(88, 101, 242)
        )
        page3.add_field(
            name="� !restart",
            value="Restart bot\nKebenaran: Administrator",
            inline=False
        )
        page3.add_field(
            name="📖 !help",
            value="Tunjuk bantuan ini",
            inline=False
        )
        page3.add_field(
            name="💡 Tips",
            value="• Guna !play untuk auto join voice\n• Bot support carian YouTube\n• Volume default adalah 50%",
            inline=False
        )
        pages.append(page3)
        
        return pages
    
    def _update_buttons(self):
        """Update button states and label based on current page"""
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                if child.custom_id == "first":
                    child.disabled = self.current_page == 0
                elif child.custom_id == "prev":
                    child.disabled = self.current_page == 0
                elif child.custom_id == "page":
                    child.label = f"Halaman {self.current_page + 1}/{self.total_pages}"
                elif child.custom_id == "next":
                    child.disabled = self.current_page >= self.total_pages - 1
                elif child.custom_id == "last":
                    child.disabled = self.current_page >= self.total_pages - 1
    
    def get_current_embed(self) -> discord.Embed:
        """Get embed for current page"""
        embed = self.pages[self.current_page]
        embed.set_footer(
            text=f"Diminta oleh {self.author.display_name} | Halaman {self.current_page + 1}/{self.total_pages}",
            icon_url=self.author.display_avatar.url
        )
        return embed
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                "❌ Hanya yang meminta help boleh guna butang ini.",
                ephemeral=True
            )
            return False
        return True
    
    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
    
    @discord.ui.button(label="<<", style=discord.ButtonStyle.secondary, custom_id="first", row=1)
    async def first_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = 0
        self._update_buttons()
        await interaction.response.edit_message(
            embed=self.get_current_embed(),
            view=self
        )
    
    @discord.ui.button(label="<", style=discord.ButtonStyle.primary, custom_id="prev", row=1)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            self._update_buttons()
            await interaction.response.edit_message(
                embed=self.get_current_embed(),
                view=self
            )
    
    @discord.ui.button(label="Halaman X/Y", style=discord.ButtonStyle.secondary, disabled=True, custom_id="page", row=1)
    async def page_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass
    
    @discord.ui.button(label=">", style=discord.ButtonStyle.primary, custom_id="next", row=1)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self._update_buttons()
            await interaction.response.edit_message(
                embed=self.get_current_embed(),
                view=self
            )
    
    @discord.ui.button(label=">>", style=discord.ButtonStyle.secondary, custom_id="last", row=1)
    async def last_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = self.total_pages - 1
        self._update_buttons()
        await interaction.response.edit_message(
            embed=self.get_current_embed(),
            view=self
        )


@bot.command()
async def help(ctx):
    """Bantuan command dengan pagination"""
    view = HelpView(ctx.author)
    embed = view.get_current_embed()
    await ctx.send(embed=embed, view=view)


def make_now_playing_embed(guild: discord.Guild) -> discord.Embed:
    player = get_guild_player(guild.id)
    voice = guild.voice_client

    embed = discord.Embed(
        title="🎵 Music Player",
        color=discord.Color.blurple()
    )

    if player.current:
        elapsed = get_elapsed_seconds(player, voice)
        duration = player.current.duration or 0
        bar = make_progress_bar(elapsed, duration, 18)

        progress_line = f"`{format_duration(elapsed)}` {bar} `{format_duration(duration)}`"

        embed.description = (
            f"**{player.current.title}**\n"
            f"{progress_line}\n"
        )

        if player.current.webpage_url:
            embed.add_field(name="🔗 Link", value=player.current.webpage_url, inline=False)

        embed.add_field(
            name="🔁 Loop",
            value="On" if player.is_looping else "Off",
            inline=True
        )
        embed.add_field(
            name="🔊 Volume",
            value=f"{int(player.volume * 100)}%",
            inline=True
        )
        embed.add_field(
            name="📃 Queue",
            value=str(len(player.queue)),
            inline=True
        )

        if player.current.requester:
            embed.set_footer(text=f"Requested by {player.current.requester}")
        else:
            embed.set_footer(text="Music bot active")

        if player.current.thumbnail:
            embed.set_thumbnail(url=player.current.thumbnail)
    else:
        embed.description = "Tak ada lagu yang sedang dimainkan."
        embed.set_footer(text="Tambah lagu dengan /play atau !play")

    return embed


class SongSelectView(discord.ui.View):
    """View untuk pilih lagu dari hasil carian"""
    def __init__(self, guild_id: int, query_results: list, original_query: str):
        super().__init__(timeout=60)
        self.guild_id = guild_id
        self.query_results = query_results
        self.original_query = original_query

        # Add select dropdown
        options = []
        print(f"Creating SongSelectView with {len(query_results)} results")
        
        for i, entry in enumerate(query_results[:10]):
            try:
                duration = format_duration(entry.get('duration', 0))
                # Account for "10. " prefix (4 chars) when truncating
                prefix_len = len(f"{i+1}. ")
                max_title_len = 100 - prefix_len
                title = entry.get('title', 'Unknown')[:max_title_len]
                # Description max 100 chars
                desc = f"Duration: {duration}"[:100]
                
                label = f"{i+1}. {title}"
                print(f"Option {i} label length: {len(label)}")
                
                options.append(
                    discord.SelectOption(
                        label=label,
                        description=desc,
                        value=str(i)
                    )
                )
            except Exception as e:
                print(f"Error creating option {i}: {e}")
                print(f"Entry: {entry}")

        print(f"Created {len(options)} options")
        
        if options:
            try:
                self.add_item(SongSelect(options))
                print("SongSelect added successfully")
            except Exception as e:
                print(f"Error adding SongSelect: {e}")
        else:
            print("No options to add!")

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item):
        print(f"SongSelectView error: {error}")
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    f"❌ Ralat: {str(error)}",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"❌ Ralat: {str(error)}",
                    ephemeral=True
                )
        except:
            pass


class SongSelect(discord.ui.Select):
    """Dropdown untuk pilih lagu"""
    def __init__(self, options):
        super().__init__(
            placeholder="Pilih lagu untuk mainkan...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            if not interaction.user.voice:
                await interaction.followup.send(
                    "❌ Masuk voice channel dulu.",
                    ephemeral=True
                )
                return

            guild_id = interaction.guild.id
            player = get_guild_player(guild_id)

            # Join voice channel kalau belum
            voice = interaction.guild.voice_client
            if not voice:
                channel = interaction.user.voice.channel
                voice = await channel.connect()
            elif voice.channel != interaction.user.voice.channel:
                await voice.move_to(interaction.user.voice.channel)

            index = int(self.values[0])
            selected = self.view.query_results[index]
            
            # Get URL from entry - extract_flat gives id, need to construct URL
            video_id = selected.get('id')
            url = selected.get('url') or selected.get('webpage_url')
            if not url and video_id:
                # Construct YouTube URL from ID
                url = f"https://www.youtube.com/watch?v={video_id}"
            
            print(f"Selected song: {selected.get('title')} - URL: {url}")
            
            # Add to queue directly - play_next will extract full info
            player.queue.append(url)

            player.text_channel = interaction.channel

            await interaction.followup.send(
                f"🎵 Ditambah ke queue: **{selected.get('title')}**",
                ephemeral=True
            )

            # Main kalau tak tengah main
            if not player.is_playing and not voice.is_playing():
                await play_next(interaction.guild, interaction.channel)
        except Exception as e:
            print(f"Error in SongSelect callback: {e}")
            await interaction.followup.send(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )


class MusicControlsView(discord.ui.View):
    """View untuk butang control music player"""
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        try:
            if not interaction.user.voice:
                await interaction.response.send_message(
                    "❌ Masuk voice channel dulu.",
                    ephemeral=True
                )
                return False
            
            voice = interaction.guild.voice_client
            if voice and voice.channel != interaction.user.voice.channel:
                await interaction.response.send_message(
                    "❌ Bot berada di channel lain.",
                    ephemeral=True
                )
                return False
            return True
        except discord.errors.InteractionResponded:
            return False
        except Exception as e:
            print(f"Error in interaction_check: {e}")
            try:
                await interaction.response.send_message(
                    f"❌ Error: {str(e)}",
                    ephemeral=True
                )
            except:
                pass
            return False

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item):
        print(f"View error: {error}")
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    f"❌ Ralat: {str(error)}",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"❌ Ralat: {str(error)}",
                    ephemeral=True
                )
        except:
            pass

    @discord.ui.button(label="Previous", emoji="⏮️", style=discord.ButtonStyle.secondary, row=0)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        try:
            guild = interaction.guild
            voice = guild.voice_client
            player = get_guild_player(guild.id)

            if not player.history:
                await interaction.followup.send(
                    "❌ Tiada lagu sebelumnya.",
                    ephemeral=True
                )
                return

            previous_song = player.history.pop()

            if player.current:
                player.queue.appendleft(player.current.webpage_url or player.current.original_query)

            player.current = previous_song

            if voice and voice.is_playing():
                voice.stop()

            await interaction.followup.send(
                "⏮️ Main lagu sebelumnya...",
                ephemeral=True
            )
        except Exception as e:
            print(f"Error in previous_button: {e}")
            await interaction.followup.send(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )

    @discord.ui.button(label="Play/Pause", emoji="⏯️", style=discord.ButtonStyle.primary, row=0)
    async def play_pause_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        try:
            guild = interaction.guild
            voice = guild.voice_client
            player = get_guild_player(guild.id)

            if not voice or not player.current:
                await interaction.followup.send(
                    "❌ Tiada lagu sedang dimainkan.",
                    ephemeral=True
                )
                return

            if voice.is_paused():
                voice.resume()
                player.paused_at = None
                await interaction.followup.send(
                    "▶️ Resumed!",
                    ephemeral=True
                )
            elif voice.is_playing():
                voice.pause()
                player.paused_at = time.time()
                await interaction.followup.send(
                    "⏸️ Paused!",
                    ephemeral=True
                )
        except Exception as e:
            print(f"Error in play_pause_button: {e}")
            await interaction.followup.send(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )

    @discord.ui.button(label="Next", emoji="⏭️", style=discord.ButtonStyle.secondary, row=0)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        try:
            guild = interaction.guild
            voice = guild.voice_client
            player = get_guild_player(guild.id)

            if not player.queue:
                await interaction.followup.send(
                    "❌ Queue kosong.",
                    ephemeral=True
                )
                return

            if voice and voice.is_playing():
                voice.stop()

            await interaction.followup.send(
                "⏭️ Skip lagu...",
                ephemeral=True
            )
        except Exception as e:
            print(f"Error in next_button: {e}")
            await interaction.followup.send(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )

    @discord.ui.button(label="Loop", emoji="🔁", style=discord.ButtonStyle.success, row=0)
    async def loop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        try:
            player = get_guild_player(interaction.guild.id)
            player.is_looping = not player.is_looping

            status = "On" if player.is_looping else "Off"
            await interaction.followup.send(
                f"🔁 Loop: **{status}**",
                ephemeral=True
            )
        except Exception as e:
            print(f"Error in loop_button: {e}")
            await interaction.followup.send(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )

    @discord.ui.button(label="Stop", emoji="⏹️", style=discord.ButtonStyle.danger, row=0)
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        try:
            guild = interaction.guild
            voice = guild.voice_client
            player = get_guild_player(guild.id)

            if voice and voice.is_playing():
                voice.stop()

            player.queue.clear()
            player.current = None
            player.is_playing = False

            await interaction.followup.send(
                "⏹️ Stopped dan queue dikosongkan!",
                ephemeral=True
            )
        except Exception as e:
            print(f"Error in stop_button: {e}")
            await interaction.followup.send(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )

    @discord.ui.button(label="Lyrics", emoji="📜", style=discord.ButtonStyle.secondary, row=1)
    async def lyrics_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        try:
            player = get_guild_player(interaction.guild.id)
            
            if not player.current:
                await interaction.followup.send(
                    "❌ Tiada lagu sedang dimainkan.",
                    ephemeral=True
                )
                return
            
            # Extract title dari current song
            title = player.current.title
            import re
            title_clean = re.sub(r'\s*\([^)]*\)', '', title)
            title_clean = re.sub(r'\s*\[[^\]]*\]', '', title_clean)
            
            # Parse artist and title
            if " - " in title_clean:
                parts = title_clean.split(" - ", 1)
                artist = parts[0].strip()
                song_title = parts[1].strip()
            else:
                words = title_clean.split()
                if len(words) > 1:
                    artist = words[0]
                    song_title = " ".join(words[1:])
                else:
                    artist = title_clean
                    song_title = title_clean
            
            # Fetch lyrics dari multiple sources
            lyrics_text, source = await fetch_lyrics(artist, song_title)
            
            if lyrics_text:
                # Clean up lyrics formatting
                lyrics_text = lyrics_text.replace('\r\n', '\n').replace('\r', '\n')
                lyrics_text = re.sub(r'\n{4,}', '\n\n\n', lyrics_text)
                
                # Format with proper sections
                lyrics_text = format_lyrics_sections(lyrics_text)
                
                if len(lyrics_text) > 4000:
                    lyrics_text = lyrics_text[:4000] + "\n\n...[Lyrics dipotong kerana terlalu panjang]"
                
                embed = discord.Embed(
                    title=f"🎤 {artist} — {song_title}",
                    color=discord.Color.green()
                )
                embed.description = f"```{lyrics_text}```"
                embed.set_footer(text=f"📚 Sumber: {source}")
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send(
                    f"❌ Tiada lyrics dijumpai untuk **{title_clean}**\nCuba format: `!lyrics artis - judul`",
                    ephemeral=True
                )
        except Exception as e:
            print(f"Error in lyrics_button: {e}")
            await interaction.followup.send(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )


# ========== TEXT COMMANDS ==========

@bot.command()
async def play(ctx, *, query):
    """Main lagu atau tambah ke queue"""
    player = get_guild_player(ctx.guild.id)
    player.text_channel = ctx.channel

    # Check user dalam voice channel
    if not ctx.author.voice:
        await ctx.send("❌ Masuk voice channel dulu!")
        return

    # Join voice channel kalau belum
    voice = ctx.guild.voice_client
    if not voice:
        channel = ctx.author.voice.channel
        voice = await channel.connect()
    elif voice.channel != ctx.author.voice.channel:
        await voice.move_to(ctx.author.voice.channel)

    # Search untuk lagu
    try:
        # Guna ytdl_search dengan ytsearch10 untuk dapat 10 results
        search_query = f"ytsearch10:{query}"
        print(f"Searching: {search_query}")
        
        data = await ctx.bot.loop.run_in_executor(
            None,
            lambda: ytdl_search.extract_info(search_query, download=False)
        )

        if data is None:
            await ctx.send("❌ Tak jumpa lagu.")
            return

        print(f"Search results: {data}")

        # Kalau multiple results, tunjuk dropdown
        if "entries" in data:
            entries = data["entries"][:10]
            # Filter out None entries
            entries = [e for e in entries if e is not None]
            
            print(f"Found {len(entries)} entries")
            
            if not entries:
                await ctx.send("❌ Tiada hasil carian.")
                return

            # Build song list for embed
            song_list = ""
            for i, entry in enumerate(entries, 1):
                duration = format_duration(entry.get('duration', 0))
                title = entry.get('title', 'Unknown')
                song_list += f"**{i}.** {title} (`{duration}`)\n"

            embed = discord.Embed(
                title="🎶 Pilih Lagu",
                description=f"Hasil carian untuk: `{query}`\n\n{song_list}\nPilih lagu dari dropdown bawah:",
                color=discord.Color.blurple()
            )

            view = SongSelectView(ctx.guild.id, entries, query)
            await ctx.send(embed=embed, view=view)
        else:
            # Single result, terus main
            player.queue.append(data.get('webpage_url') or data.get('url'))
            await ctx.send(f"🎵 Ditambah ke queue: **{data.get('title')}**")

            # Main kalau tak tengah main
            if not player.is_playing and not voice.is_playing():
                await play_next(ctx.guild, ctx.channel)

    except Exception as e:
        await ctx.send(f"❌ Error semasa carian lagu: {str(e)}")


@bot.command()
async def now(ctx):
    """Tunjuk lagu semasa"""
    embed = make_now_playing_embed(ctx.guild)
    view = MusicControlsView(ctx.guild.id)
    await ctx.send(embed=embed, view=view)


@bot.command()
async def queue(ctx):
    """Tunjuk queue"""
    player = get_guild_player(ctx.guild.id)

    embed = discord.Embed(
        title="📃 Queue",
        color=discord.Color.blurple()
    )

    if player.current:
        embed.add_field(
            name="🎵 Now Playing",
            value=f"**{player.current.title}**",
            inline=False
        )
    else:
        embed.add_field(
            name="🎵 Now Playing",
            value="Tiada",
            inline=False
        )

    if player.queue:
        queue_text = ""
        for i, item in enumerate(list(player.queue)[:10], 1):
            queue_text += f"{i}. {item}\n"
        if len(player.queue) > 10:
            queue_text += f"... dan {len(player.queue) - 10} lagi"
        embed.add_field(name="Up Next", value=queue_text or "Queue kosong", inline=False)
    else:
        embed.add_field(name="Up Next", value="Queue kosong", inline=False)

    embed.set_footer(text=f"Total: {len(player.queue)} lagu dalam queue")
    await ctx.send(embed=embed)


@bot.command()
async def volume(ctx, vol: int = None):
    """Ubah volume (0-100)"""
    player = get_guild_player(ctx.guild.id)
    voice = ctx.guild.voice_client

    if vol is None:
        await ctx.send(f"🔊 Volume semasa: **{int(player.volume * 100)}%**")
        return

    if not 0 <= vol <= 100:
        await ctx.send("❌ Volume mesti antara 0-100.")
        return

    player.volume = vol / 100

    # Update current player volume
    if voice and voice.source:
        voice.source.volume = player.volume

    await ctx.send(f"🔊 Volume ditukar ke **{vol}%**")


@bot.command()
async def pause(ctx):
    """Pause lagu"""
    voice = ctx.guild.voice_client
    player = get_guild_player(ctx.guild.id)

    if not voice or not voice.is_playing():
        await ctx.send("❌ Tiada lagu sedang dimainkan.")
        return

    voice.pause()
    player.paused_at = time.time()
    await ctx.send("⏸️ Paused!")


@bot.command()
async def resume(ctx):
    """Resume lagu"""
    voice = ctx.guild.voice_client
    player = get_guild_player(ctx.guild.id)

    if not voice or not voice.is_paused():
        await ctx.send("❌ Tiada lagu yang di-pause.")
        return

    voice.resume()
    player.paused_at = None
    await ctx.send("▶️ Resumed!")


@bot.command()
async def skip(ctx):
    """Skip lagu"""
    voice = ctx.guild.voice_client
    player = get_guild_player(ctx.guild.id)

    if not voice or not voice.is_playing():
        await ctx.send("❌ Tiada lagu sedang dimainkan.")
        return

    if not player.queue:
        await ctx.send("⚠️ Queue kosong, lagu akan di-stop.")

    voice.stop()
    await ctx.send("⏭️ Skip lagu!")


@bot.command()
async def previous(ctx):
    """Main lagu sebelumnya"""
    voice = ctx.guild.voice_client
    player = get_guild_player(ctx.guild.id)

    if not player.history:
        await ctx.send("❌ Tiada lagu sebelumnya dalam history.")
        return

    # Ambil lagu terakhir dari history
    previous_song = player.history.pop()

    # Masukkan current ke depan queue
    if player.current:
        player.queue.appendleft(player.current.webpage_url or player.current.original_query)

    # Set current sebagai previous
    player.current = previous_song

    # Stop dan main semula
    if voice and voice.is_playing():
        voice.stop()

    await ctx.send(f"⏮️ Main lagu sebelumnya: **{previous_song.title}**")


@bot.command()
async def stop(ctx):
    """Stop dan kosongkan queue"""
    voice = ctx.guild.voice_client
    player = get_guild_player(ctx.guild.id)

    if voice and voice.is_playing():
        voice.stop()

    # Cancel progress task
    if player.progress_task:
        player.progress_task.cancel()
        player.progress_task = None

    player.queue.clear()
    player.current = None
    player.is_playing = False
    player.is_looping = False

    await ctx.send("⏹️ Stopped dan queue dikosongkan!")


@bot.command()
async def loop(ctx):
    """Toggle loop on/off"""
    player = get_guild_player(ctx.guild.id)
    player.is_looping = not player.is_looping

    status = "On" if player.is_looping else "Off"
    emoji = "🔁" if player.is_looping else "🔂"
    await ctx.send(f"{emoji} Loop: **{status}**")


@bot.command()
async def join(ctx):
    """Masuk voice channel"""
    if not ctx.author.voice:
        await ctx.send("❌ Masuk voice channel dulu!")
        return

    voice = ctx.guild.voice_client
    channel = ctx.author.voice.channel

    if voice:
        if voice.channel == channel:
            await ctx.send("ℹ️ Dah dalam channel ni.")
        else:
            await voice.move_to(channel)
            await ctx.send(f"✅ Berpindah ke **{channel.name}**")
    else:
        await channel.connect()
        await ctx.send(f"✅ Masuk ke **{channel.name}**")


@bot.command()
async def leave(ctx):
    """Keluar voice channel"""
    voice = ctx.guild.voice_client

    if not voice:
        await ctx.send("❌ Bot tak dalam voice channel.")
        return

    # Clear player data
    player = get_guild_player(ctx.guild.id)
    if voice.is_playing():
        voice.stop()
    player.queue.clear()
    player.current = None
    player.is_playing = False

    await voice.disconnect()
    await ctx.send("👋 Keluar dari voice channel.")


@bot.command()
async def lyrics(ctx, *, query: str = None):
    """Tunjuk lyrics untuk lagu semasa atau carian"""
    player = get_guild_player(ctx.guild.id)
    
    # Kalau tak ada query, guna lagu semasa
    if not query:
        if not player.current:
            await ctx.send("❌ Tiada lagu sedang dimainkan. Guna `!lyrics <artis> - <judul>` untuk cari.")
            return
        # Extract title dari current song
        title = player.current.title
        import re
        title = re.sub(r'\s*\([^)]*\)', '', title)
        title = re.sub(r'\s*\[[^\]]*\]', '', title)
        query = title
    
    await ctx.send(f"🔍 Mencari lyrics untuk: **{query}**...")
    
    try:
        # Parse artist and title
        if " - " in query:
            parts = query.split(" - ", 1)
            artist = parts[0].strip()
            title = parts[1].strip()
        else:
            words = query.split()
            if len(words) > 1:
                artist = words[0]
                title = " ".join(words[1:])
            else:
                artist = query
                title = query
        
        # Fetch lyrics dari multiple sources
        lyrics_text, source = await fetch_lyrics(artist, title)
        
        if lyrics_text:
            # Clean up lyrics formatting
            lyrics_text = lyrics_text.replace('\r\n', '\n').replace('\r', '\n')
            # Remove multiple consecutive empty lines
            import re
            lyrics_text = re.sub(r'\n{4,}', '\n\n\n', lyrics_text)
            
            # Format with proper sections
            lyrics_text = format_lyrics_sections(lyrics_text)
            
            # Truncate if too long (Discord limit 4096 chars per field)
            if len(lyrics_text) > 4000:
                lyrics_text = lyrics_text[:4000] + "\n\n...[Lyrics dipotong kerana terlalu panjang]"
            
            embed = discord.Embed(
                title=f"🎤 {artist} — {title}",
                color=discord.Color.green()
            )
            embed.description = f"```{lyrics_text}```"
            embed.set_footer(text=f"📚 Sumber: {source}")
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"❌ Tiada lyrics dijumpai untuk **{query}**\nCuba format: `!lyrics artis - judul`")
    except Exception as e:
        await ctx.send(f"❌ Error mencari lyrics: {str(e)}")


@bot.command()
async def restart(ctx):
    """Restart bot (owner only)"""
    # Check if user is bot owner or has admin permissions
    if ctx.author.id != ctx.guild.owner_id and not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ Hanya admin atau server owner boleh restart bot.")
        return
    
    await ctx.send("🔄 Restarting bot...")
    
    # Cleanup voice connections
    for guild in bot.guilds:
        voice = guild.voice_client
        if voice:
            voice.stop()
            await voice.disconnect()
    
    # Restart the bot
    os.execv(sys.executable, ['python'] + sys.argv)




@bot.event
async def on_ready():
    print(f"Bot {bot.user} dah sedia!")
    print(f"Logged in as {bot.user.name}")
    print(f"ID: {bot.user.id}")
    print("------")


bot.run(TOKEN)
