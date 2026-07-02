import discord
from discord.ext import commands
from discord.ui import Button, View, Select
import asyncio
from datetime import datetime, timedelta, timezone
import json
import os
import re
import aiohttp
import collections
import yt_dlp
import time
import resource

# ==================== PH TIME ====================
PH_TIME = timezone(timedelta(hours=8))

# ==================== BOT OWNER ====================
BOT_OWNER_ID = 1238037974877212707
BOT_VERSION = "1.0.0"

YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")

# ==================== FILES ====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

WHITELIST_FILE    = os.path.join(DATA_DIR, "whitelist.json")
LOGS_FILE         = os.path.join(DATA_DIR, "logs.json")
CONFIG_FILE       = os.path.join(DATA_DIR, "config.json")
AUTORESPOND_FILE  = os.path.join(DATA_DIR, "autorespond.json")
BACKUP_FILE       = os.path.join(DATA_DIR, "backup.json")
WARNS_FILE        = os.path.join(DATA_DIR, "warns.json")

# ==================== LOAD/SAVE ====================
def load_data(file_name):
    if not os.path.exists(file_name):
        return {}
    try:
        with open(file_name, "r") as f:
            return json.load(f)
    except:
        return {}

def save_data(file_name, data):
    with open(file_name, "w") as f:
        json.dump(data, f, indent=4)

# ==================== DATA ====================
whitelist_data   = load_data(WHITELIST_FILE)
log_channels     = load_data(LOGS_FILE)
config_data      = load_data(CONFIG_FILE)
autorespond_data = load_data(AUTORESPOND_FILE)
backup_store     = load_data(BACKUP_FILE)
warns_data       = load_data(WARNS_FILE)

def save_warns():
    save_data(WARNS_FILE, warns_data)

setup_guilds     = set()
afk_users        = {}
spam_tracker     = collections.defaultdict(list)
BOT_BANNER_URL   = None
sticky_messages  = {}
# snipe_data: {channel_id: {"content": str, "author": str, "author_icon": str, "time": datetime}}
snipe_data       = {}

# ==================== PREFIX ====================
FIXED_PREFIXES = ["$", "x", ","]

async def get_prefix(bot, message):
    if message.guild:
        gid = str(message.guild.id)
        custom = config_data.get(gid, {}).get("prefix")
        prefixes = list(FIXED_PREFIXES)
        if custom and custom not in prefixes:
            prefixes.append(custom)
        return prefixes
    return list(FIXED_PREFIXES)
    return ["$", ""]

# ==================== INTENTS ====================
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True
intents.moderation = True
intents.presences = True

bot = commands.Bot(
    command_prefix=get_prefix,
    intents=intents,
    help_command=None
)
bot_start_time = datetime.now(PH_TIME)

# ==================== HELPERS ====================
def get_guild_config(guild_id):
    gid = str(guild_id)
    if gid not in config_data:
        config_data[gid] = {}
    return config_data[gid]

def save_config():
    save_data(CONFIG_FILE, config_data)

# Regular embeds → white sidebar
def auto_embed_color(title: str) -> int:
    t = (title or "").lower()
    error_words = ["no permission", "error", "invalid", "failed", "denied", "cannot", "can't", "not found", "already", "missing"]
    success_words = ["success", "enabled", "added", "created", "removed", "banned", "kicked", "unbanned", "cleared", "set", "updated"]
    if any(w in t for w in error_words):
        return 0xFF3B3B
    if any(w in t for w in success_words):
        return 0x57F287
    return 0xFFFFFF

def make_embed(title: str = "", description: str = "", color: int = None) -> discord.Embed:
    embed = discord.Embed(color=color if color is not None else auto_embed_color(title))
    if title:
        embed.title = title
    if description:
        embed.description = description
    embed.timestamp = datetime.now(PH_TIME)
    return embed

# Log embeds → black sidebar
def make_log_embed(title: str, description: str = "") -> discord.Embed:
    embed = discord.Embed(color=0x000000)
    if title:
        embed.title = strip_emojis(title)
    if description:
        embed.description = strip_emojis(description)
    embed.timestamp = datetime.now(PH_TIME)
    return embed

async def send_embed(ctx, title, description, color: int = None):
    embed = make_embed(title, description, color=color)
    avatar = bot.user.display_avatar.url if bot.user else None
    embed.set_footer(text="HunterX", icon_url=avatar)
    await ctx.send(embed=embed)

EMOJI_PATTERN = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F1E6-\U0001F1FF"
    "\U00002700-\U000027BF"
    "\U0001F900-\U0001F9FF"
    "\U00002300-\U000023FF"
    "]+", flags=re.UNICODE
)

def strip_emojis(text):
    if not text:
        return text
    text = re.sub(r"<a?:\w+:\d+>", "", text)
    text = EMOJI_PATTERN.sub("", text)
    return re.sub(r"[ \t]+", " ", text).strip()

async def log_action(guild, title, description, thumbnail_url=None):
    channel_id = log_channels.get(str(guild.id))
    if not channel_id:
        return
    channel = guild.get_channel(channel_id)
    if not channel:
        return
    try:
        embed = make_log_embed(title, description)
        avatar = bot.user.display_avatar.url if bot.user else None
        embed.set_footer(text="HunterX", icon_url=avatar)
        if thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)
        await channel.send(embed=embed)
    except:
        pass

async def log_mod_action(guild, title, description, thumbnail_url=None):
    gid = str(guild.id)
    ch_id = config_data.get(gid, {}).get("modlogs_channel")
    if not ch_id:
        return
    channel = guild.get_channel(ch_id)
    if not channel:
        return
    try:
        embed = make_log_embed(title, description)
        embed.timestamp = datetime.now(PH_TIME)
        avatar = bot.user.display_avatar.url if bot.user else None
        embed.set_footer(text="HunterX", icon_url=avatar)
        if thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)
        await channel.send(embed=embed)
    except:
        pass

def is_whitelisted(guild, member):
    gid = str(guild.id)
    if gid not in whitelist_data:
        return False
    return str(member.id) in whitelist_data[gid].get("users", {})

def is_owner(ctx):
    return ctx.author.id == ctx.guild.owner_id or ctx.author.id == BOT_OWNER_ID

def is_antinuke_enabled(guild_id):
    return get_guild_config(guild_id).get("antinuke", False)

def is_guild_owner_or_bot(guild, user):
    return user.id == guild.owner_id or user.id == bot.user.id

def is_higher_role_than_bot(guild, user):
    try:
        bot_top = guild.me.top_role.position
        user_top = user.top_role.position
        return user_top > bot_top
    except:
        return False

# ==================== GIF HELPER ====================
async def fetch_gif(action: str) -> str:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://nekos.best/api/v2/{action}", timeout=aiohttp.ClientTimeout(total=8)) as resp:
                data = await resp.json()
                return data["results"][0]["url"]
    except:
        return None

# ==================== FORMAT NUMBERS ====================
def _fmt_num(n):
    if n is None:
        return "N/A"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)

# ==================== VERIFY VIEW ====================
class VerifyView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="✅ VERIFY!", style=discord.ButtonStyle.secondary, custom_id="hunterx_verify")
    async def verify_button(self, interaction: discord.Interaction, button: Button):
        guild = interaction.guild
        member = interaction.user
        role = discord.utils.get(guild.roles, name="VERIFIED")
        if not role:
            await interaction.response.send_message("VERIFIED role not found. Ask an admin to run $verification setup again.", ephemeral=True)
            return
        if role in member.roles:
            await interaction.response.send_message("You are already verified!", ephemeral=True)
            return
        try:
            await member.add_roles(role)
            await interaction.response.send_message("You have been verified! You can now access all channels.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"<:HunterX:1512787796635422934> Error: {e}", ephemeral=True)

# ==================== INVITE VIEW ====================
class InviteView(View):
    def __init__(self):
        super().__init__(timeout=None)

    def build(self):
        invite_url = f"https://discord.com/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot"
        self.add_item(discord.ui.Button(label="INVITE", url=invite_url, style=discord.ButtonStyle.link))
        self.add_item(discord.ui.Button(label="WEBSITE", url="https://hunterx2.netlify.app", style=discord.ButtonStyle.link))
        return self

# ==================== TICKET LOG HELPER ====================
async def log_ticket(guild, title, description):
    gid = str(guild.id)
    ch_id = config_data.get(gid, {}).get("ticketlog_channel")
    if not ch_id:
        return
    ch = guild.get_channel(ch_id)
    if not ch:
        return
    try:
        embed = make_log_embed(title, description)
        embed.set_footer(text="HunterX")
        embed.timestamp = datetime.now(PH_TIME)
        await ch.send(embed=embed)
    except:
        pass

# ==================== TICKET CLOSE VIEW ====================
class CloseView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, custom_id="hunterx_ticket_close")
    async def close_button(self, interaction: discord.Interaction, button: Button):
        channel = interaction.channel
        guild = interaction.guild
        closer = interaction.user
        ticket_name = channel.name
        owner_id = None
        if channel.topic and "Ticket owner:" in channel.topic:
            try:
                owner_id = int(channel.topic.split("Ticket owner:")[1].strip())
            except:
                pass
        await interaction.response.send_message("Closing ticket in 3 seconds...", ephemeral=False)
        owner_mention = f"<@{owner_id}>" if owner_id else "Unknown"
        await log_ticket(guild, "<:HunterXapp:1512783709198225459> Ticket Closed",
            f"*Ticket:* #{ticket_name}\n**Closed by:** {closer.mention} ({closer.id})\n**Ticket Owner:** {owner_mention}")
        await asyncio.sleep(3)
        try:
            await channel.delete(reason="Ticket closed")
        except:
            pass

# ==================== TICKET CREATE VIEW ====================
class TicketView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="SUPPORT", style=discord.ButtonStyle.secondary, custom_id="hunterx_ticket_create")
    async def create_ticket(self, interaction: discord.Interaction, button: Button):
        guild = interaction.guild
        member = interaction.user
        gid = str(guild.id)
        cfg = get_guild_config(guild.id)

        category = discord.utils.get(guild.categories, name="helpdesk")
        if not category:
            await interaction.response.send_message("Ticket category not found. Ask an admin to run $ticketsetup.", ephemeral=True)
            return

        for ch in category.text_channels:
            if ch.topic and str(member.id) in ch.topic:
                await interaction.response.send_message(f"You already have an open ticket: {ch.mention}", ephemeral=True)
                return

        count = cfg.get("ticket_count", 0) + 1
        cfg["ticket_count"] = count
        save_config()

        ticket_name = f"ticket-{count:02d}"

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
            member: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        }
        for role in guild.roles:
            if role.permissions.administrator:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, manage_channels=True)

        try:
            ticket_ch = await guild.create_text_channel(
                name=ticket_name,
                category=category,
                overwrites=overwrites,
                topic=f"Ticket owner: {member.id}",
                reason=f"Ticket created by {member}"
            )
        except Exception as e:
            await interaction.response.send_message(f"Failed to create ticket: {e}", ephemeral=True)
            return

        await interaction.response.send_message(f"Your ticket has been created: {ticket_ch.mention}", ephemeral=True)

        await log_ticket(guild, "<:HunterXmail:1514600414941675550> Ticket Opened",
            f"*Ticket:* #{ticket_name}\n**Opened by:** {member.mention} ({member.id})\n**Channel:** {ticket_ch.mention}")

        sv_name_caps = guild.name.split()[0].upper() if guild.name.split() else guild.name.upper()
        ticket_embed = discord.Embed(
            description=(
                f"# {sv_name}\n\n"
                f"# TICKET RULES\n\n"
                f"- 5 Hours no reply Ticket Close\n\n"
                f"- If you dont have need dont create ticket\n\n"
                f"- Troll ticket = Timeout 5hrs\n\n"
                f"- Spam ticket = Timeout 3days\n\n"
                f"1st attempt timeout 1 day\n"
                f"2nd attempt timeout 2 days\n"
                f"3rd attempt timeout 5days\n"
                f"4th attempt = Ban"
            ),
            color=0xFFFFFF
        )
        if guild.icon:
            ticket_embed.set_image(url=guild.icon.url)
        ticket_embed.set_footer(text="HunterX")
        await ticket_ch.send(content=member.mention, embed=ticket_embed, view=CloseView())

# ==================== HELP EMBED BUILDER ====================
def build_help_embed(category: str, prefix: str, bot_thumb: str) -> discord.Embed:
    p = prefix

    if category == "hunterx":
        desc = '\n'.join([
            '# __Anti Nuke__',
            '',
            f'>>> `setup`',
            f'`securityall enable/disable`',
            f'`whitelist @user`',
            f'`rwhitelist @user`',
            f'`whitelistboard`',
            f'`antinuke enable/disable`',
            f'`antibotadd enable/disable`',
            f'`antikick enable/disable`',
            f'`antiban enable/disable`',
            f'`anticrtwebhook enable/disable`',
            f'`anticrtadminrole enable/disable`',
            f'`antilink enable/disable`',
            f'`allowedlink @user/role`',
            f'`allowedlinkboard`',
            f'`antispam enable/disable`',
            f'`anticrtchannel enable/disable`',
            f'`antidelchannel enable/disable`',
            f'`antidelrole enable/disable`',
        ])
    elif category == "moderation":
        desc = '\n'.join([
            '# __Moderation__',
            '',
            f'>>> `ban @user [reason]`',
            f'`unban <id> [reason]`',
            f'`unban all`',
            f'`banlist`',
            f'`kick @user [reason]`',
            f'`timeout @user <duration> [reason]`',
            f'`rtimeout @user`',
            f'`role @user @role`',
            f'`drole @user @role`',
            f'`warn @user [reason]`',
            f'`unwarn @user`',
            f'`checkwarns @user`',
            f'`clearwarns @user`',
            f'`lock / unlock #channel`',
            f'`lockdown / unlockdown`',
            f'`purge <amount>`',
            f'`snipe`',
            f'`setprefix <prefix>`',
            f'`config`',
            f'`serverinfo`',
            f'`botstats`',
            f'`autoroleadd @role`',
            f'`setsvicon`',
            f'`setsvbnr`',
            f'`sticky <msg>`',
            f'`unsticky`',
            '',
            '**Setup & Config**',
            '',
            f'`ticketsetup`',
            f'`ticketreset`',
            f'`ticketlogs`',
            f'`deletemsglog`',
            f'`editmsglogs`',
            f'`modlogs`',
            f'`setwelcome`',
            f'`welcome #channel`',
            f'`setmessage <msg>`',
            f'`welcome test`',
            f'`verification setup`',
            f'`boostchannel setup`',
            f'`boostmessage <msg>`',
            f'`autorespondadd <trigger> <reply>`',
            f'`autorespondedit <trigger> <reply>`',
            f'`autorespondremove <trigger>`',
            f'`backupcreate`',
            f'`backuprestore <id>`',
        ])
    elif category == "utility":
        desc = '\n'.join([
            '# __Utility__',
            '',
            f'>>> `av @user` - View avatar/pfp.',
            f'`banner @user` - View banner.',
            f'`userinfo @user` - View userinfo',
            f'`rinfo @role` - View role info',
            f'`svpfp` - View server pfp.',
            f'`svbnr` - View server banner.',
            f'`ig <username>` - Instagram Acc.',
            f'`tt <username>` - Tiktok Acc.',
            f'`yt <channel name>` - Youtube',
            f'`rbx <username>` - Roblox Acc.',
            f'`afk [reason]` - Set AFK',
            f'`ping` - Latency.',
            f'`botinfo` - Bot information.',
        ])
    else:  # fun
        desc = '\n'.join([
            '# __Fun__',
            '',
            f'>>> `kiss @user` - Kiss someone.',
            f'`hug @user` - Hug someone.',
            f'`cuddle @user` - Cuddle someone.',
            f'`slap @user` - Slap someone.',
            f'`punch @user` - Punch someone.',
            f'`boxing @user` - Boxing someone.',
            f'`throw @user` - Throw someone.',
        ])

    embed = discord.Embed(description=desc, color=0xFFFFFF)
    embed.set_author(name="HunterX", icon_url=bot_thumb)
    embed.set_thumbnail(url=bot_thumb)
    embed.set_footer(text="HunterX")
    return embed

# ==================== HELP EMBED FOR NON-ADMINS (no select, direct) ====================
def build_nonadmin_help_embed(prefix: str, bot_thumb: str) -> discord.Embed:
    p = prefix
    desc = '\n'.join([
        '# __Utility__',
        '',
        f'>>> `afk [reason]` - AFK Status.',
        f'`userinfo @user` - UserInfo.',
        f'`av @user` - avatar/pfp.',
        f'`banner @user` - banner.',
        f'`svpfp` - Server profile.',
        f'`svbnr` - Server banner.',
        f'`rbx <username>` - Roblox Account',
        f'`tt <username>` - TikTok Account',
        f'`ig <username>` - Instagram Account',
        f'`yt <channel name>` - Youtube Account',
        f'`ping` - Latency.',
        '',
        '# __Fun__',
        '',
        f'`kiss @user` - Kiss someone.',
        f'`hug @user` - Hug someone.',
        f'`cuddle @user` - Cuddle someone.',
        f'`slap @user` - Slap someone.',
        f'`punch @user` - Punch someone.',
        f'`throw @user` - Throw someone.',
        f'`boxing @user` - Boxing someone.',
    ])
    embed = discord.Embed(description=desc, color=0xFFFFFF)
    embed.set_author(name="HunterX", icon_url=bot_thumb)
    embed.set_thumbnail(url=bot_thumb)
    embed.set_footer(text="HunterX")
    return embed

# ==================== HELP SELECT ====================
class HelpSelect(Select):
    def __init__(self, prefix, member):
        self.prefix = prefix
        options = []

        is_admin = member.guild_permissions.administrator
        is_srv_owner = member.id == member.guild.owner_id  # fixed typo: guildq → guild
        is_bot_owner = member.id == BOT_OWNER_ID

        if is_admin or is_srv_owner or is_bot_owner:
            options.append(discord.SelectOption(
                label="Anti Nuke",
                value="hunterx",
                description="Setup / Anti Nuke Commands"
            ))
            options.append(discord.SelectOption(
                label="Moderation",
                value="moderation",
                description="Mod / Setup / AutoRespond / Etc."
            ))

        options.append(discord.SelectOption(
            label="Utility",
            value="utility",
            description="Social / Server / Etc."
        ))
        options.append(discord.SelectOption(
            label="Fun",
            value="fun",
            description="Fun Commands"
        ))

        super().__init__(placeholder="Select Category", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        embed = build_help_embed(self.values[0], self.prefix, bot.user.display_avatar.url)
        await interaction.response.edit_message(embed=embed, view=self.view)

class HelpView(View):
    def __init__(self, prefix, member):
        super().__init__(timeout=None)
        self.add_item(HelpSelect(prefix, member))

# ==================== BOTSTATS PAGINATOR ====================
SERVERS_PER_PAGE = 6

def build_serverlist_embed(page: int) -> discord.Embed:
    guilds = list(bot.guilds)
    total = len(guilds)
    total_pages = max(1, (total + SERVERS_PER_PAGE - 1) // SERVERS_PER_PAGE)
    page = max(1, min(page, total_pages))

    start = (page - 1) * SERVERS_PER_PAGE
    end = start + SERVERS_PER_PAGE
    page_guilds = guilds[start:end]

    lines = [
        f"**__SERVER LIST__**\n",
        f"╰ **Total Servers:** `{total}`",
        f"╰ **Page {page}/{total_pages}**\n",
    ]
    for i, g in enumerate(page_guilds, start=start + 1):
        status = "Normal"
        members = g.member_count or 0
        lines.append(f"**{i}.** **{g.name}**")
        lines.append(f"└─ **ID:** `{g.id}` | **Members:** `{members}` | **Status:** {status}")
    lines.append(f"\n╰ **Auto-updates every 15 seconds**")

    embed = discord.Embed(description="\n".join(lines), color=0xFFFFFF)
    embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.set_footer(text="HunterX")
    embed.timestamp = datetime.now(PH_TIME)
    return embed

class ServerListView(View):
    def __init__(self, page: int):
        super().__init__(timeout=60)
        self.page = page
        guilds = list(bot.guilds)
        total = len(guilds)
        total_pages = max(1, (total + SERVERS_PER_PAGE - 1) // SERVERS_PER_PAGE)
        self.total_pages = total_pages

    @discord.ui.button(label="< Previous", style=discord.ButtonStyle.secondary, custom_id="serverlist_prev")
    async def prev_button(self, interaction: discord.Interaction, button: Button):
        if self.page > 1:
            self.page -= 1
        embed = build_serverlist_embed(self.page)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Next >", style=discord.ButtonStyle.secondary, custom_id="serverlist_next")
    async def next_button(self, interaction: discord.Interaction, button: Button):
        if self.page < self.total_pages:
            self.page += 1
        embed = build_serverlist_embed(self.page)
        await interaction.response.edit_message(embed=embed, view=self)


# ==================== KEEPALIVE ====================
async def keepalive_loop():
    """Ping the public URL every 10 minutes to prevent Render free-tier spin-down."""
    await bot.wait_until_ready()
    external_url = os.environ.get("RENDER_EXTERNAL_URL")
    if external_url:
        url = external_url
    else:
        port = int(os.environ.get("PORT", 8000))
        url = f"http://localhost:{port}/"
    while not bot.is_closed():
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    pass
        except Exception:
            pass
        await asyncio.sleep(600)

@bot.event
async def on_disconnect():
    print(f"[{datetime.now(PH_TIME).strftime('%Y-%m-%d %H:%M:%S')}] Bot disconnected. Reconnecting...")

# ==================== READY ====================
@bot.event
async def on_ready():
    global BOT_BANNER_URL
    for gid in log_channels:
        setup_guilds.add(int(gid))
    bot.add_view(VerifyView())
    bot.add_view(TicketView())
    bot.add_view(CloseView())
    try:
        bot_user = await bot.fetch_user(bot.user.id)
        if bot_user.banner:
            BOT_BANNER_URL = bot_user.banner.url
    except:
        pass
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash command(s)")
    except Exception as e:
        print(f"Failed to sync slash commands: {e}")
    bot.loop.create_task(keepalive_loop())
    try:
        await bot.change_presence(
            status=discord.Status.dnd,
            activity=discord.Streaming(name="HunterX", url="https://www.twitch.tv/hunterx")
        )
    except Exception as e:
        print(f"Failed to set presence: {e}")
    print(f"Logged in as {bot.user}")

# ==================== BOT JOIN ====================
@bot.event
async def on_guild_join(guild):
    inviter = None
    try:
        async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.bot_add):
            if entry.target and entry.target.id == bot.user.id:
                inviter = entry.user
                break
    except:
        pass

    if inviter:
        try:
            dm_embed = discord.Embed(
                description=(
                    f"**HunterX**\n\n"
                    f"Thankyou For Using <:cutei:1515273052315713617> **HunterX**\n\n"
                    f"Thanks for adding me to **{guild.name}**!\n\n"
                    f"Command\n"
                    f"`$setup`\nTo setup logs\n\n"
                    f"`$help`\nShow Commands\n\n"
                    f"**Prefixes** — `$` | `/` | `x` | `,`"
                ),
                color=0xFFFFFF
            )
            dm_embed.set_thumbnail(url=guild.me.display_avatar.url)
            dm_embed.set_footer(text="HunterX")
            await inviter.send(embed=dm_embed)
        except:
            pass

    for channel in guild.text_channels:
        try:
            if channel.permissions_for(guild.me).send_messages:
                embed = discord.Embed(
                    description=(
                        f"**HunterX**\n\n"
                        f"Thankyou For Using <:cutei:1515273052315713617> **HunterX**\n\n"
                        f"Command\n"
                        f"`$setup`\nTo setup logs\n\n"
                        f"`$help`\nShow Commands\n\n"
                f"**Prefixes** — `$` | `/` | `x` | `,`"
                    ),
                )
                embed.set_thumbnail(url=guild.me.display_avatar.url)
                embed.set_footer(text="HunterX")
                await channel.send(embed=embed)
                break
        except:
            pass

# ==================== PING ====================
@bot.hybrid_command()
async def ping(ctx):
    latency_ms = round(bot.latency * 1000)
    embed = make_embed("<a:HappyHunterXemoji:1512831297582661803> Ping!", f"**Latency:** `{latency_ms}ms`")
    embed.set_footer(text="HunterX")
    await ctx.send(embed=embed)

# ==================== SETUP ====================
@bot.hybrid_command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    guild = ctx.guild
    try:
        gid = str(guild.id)
        tracked_id = log_channels.get(gid)
        tracked_channel = guild.get_channel(tracked_id) if tracked_id else None
        existing = tracked_channel or discord.utils.get(guild.text_channels, name="hunterx-logs")
        if existing:
            log_channels[gid] = existing.id
            save_data(LOGS_FILE, log_channels)
            setup_guilds.add(guild.id)
            embed = discord.Embed(
                description=(
                    f"**Already Setup**\n\n"
                    f"{existing.mention} is already set as the log channel."
                ),
                color=0xFFFFFF
            )
            embed.set_footer(text="HunterX")
            return await ctx.send(embed=embed)
        overwrites = {guild.default_role: discord.PermissionOverwrite(view_channel=False)}
        channel = await guild.create_text_channel(name="hunterx-logs", overwrites=overwrites)
        for role in guild.roles:
            if role.permissions.administrator:
                await channel.set_permissions(role, view_channel=True, send_messages=True, read_message_history=True)
        await channel.set_permissions(guild.me, view_channel=True, send_messages=True, read_message_history=True)
        log_channels[str(guild.id)] = channel.id
        save_data(LOGS_FILE, log_channels)
        setup_guilds.add(guild.id)
        await send_embed(ctx, "Setup Successful", f"{channel.mention} created successfully.")
    except Exception as e:
        await ctx.send(f"```{e}```")

# ==================== HELP ====================
@bot.hybrid_command()
async def help(ctx):
    if not ctx.guild:
        return
    member = ctx.author
    gid = str(ctx.guild.id)
    prefix = config_data.get(gid, {}).get("prefix", "$")
    bot_thumb = bot.user.display_avatar.url

    is_admin = member.guild_permissions.administrator
    is_srv_owner = member.id == ctx.guild.owner_id
    is_bot_owner = member.id == BOT_OWNER_ID

    # If user has no admin/owner role: show commands directly, no select menu
    if not is_admin and not is_srv_owner and not is_bot_owner:
        embed = build_nonadmin_help_embed(prefix, bot_thumb)
        return await ctx.send(embed=embed)

    # Admin/owner: show select menu
    embed = discord.Embed(
        description=(
            f"**Thankyou for using HunterX!**\n"
            f"[INVITE](<https://discord.com/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot>) | [SUPPORT](https://discord.gg/ehWk58hymn)\n\n"
            f"Select a category below to view commands.\n"
            f"**Prefixes:** `$` | `/` | `x` | `,`"
        ),
        color=0xFFFFFF
    )
    embed.set_footer(text="HunterX")
    view = HelpView(prefix, member)
    await ctx.send(embed=embed, view=view)

# ==================== WHITELIST (Owner Only) ====================
@bot.hybrid_command()
async def whitelist(ctx, member: discord.Member):
    if not is_owner(ctx):
        return await send_embed(ctx, "<:HunterX:1512787796635422934> No Permission", "Only the server owner or bot owner can use this command.")
    gid = str(ctx.guild.id)
    if gid not in whitelist_data:
        whitelist_data[gid] = {"users": {}}
    whitelist_data[gid]["users"][str(member.id)] = ["all"]
    save_data(WHITELIST_FILE, whitelist_data)
    await send_embed(ctx, "<:HunteXCheck:1518422536558481448> User Whitelisted", f"{member.mention} is now whitelisted.")

# ==================== REMOVE WHITELIST (Owner Only) ====================
@bot.hybrid_command()
async def rwhitelist(ctx, member: discord.Member):
    if not is_owner(ctx):
        return await send_embed(ctx, "<:HunterX:1512787796635422934> No Permission", "Only the server owner or bot owner can use this command.")
    gid = str(ctx.guild.id)
    if gid in whitelist_data and str(member.id) in whitelist_data[gid].get("users", {}):
        del whitelist_data[gid]["users"][str(member.id)]
        save_data(WHITELIST_FILE, whitelist_data)
        return await send_embed(ctx, "<:HunteXCheck:1518422536558481448> Removed", f"{member.mention} removed from whitelist.")
    await send_embed(ctx, "<:HunterX:1512787796635422934> Not Found", f"{member.mention} is not whitelisted.")

# ==================== WHITELIST BOARD ====================
@bot.hybrid_command()
async def whitelistboard(ctx):
    gid = str(ctx.guild.id)
    users = whitelist_data.get(gid, {}).get("users", {})
    if not users:
        return await send_embed(ctx, "<:249630gradientgear:1512782705522245712> Whitelist", "No whitelisted users.")
    desc = ""
    for i, uid in enumerate(users.keys(), 1):
        member = ctx.guild.get_member(int(uid))
        name = member.mention if member else f"<@{uid}>"
        desc += f"**{i}.** {name}\n"
    embed = make_embed("<:249630gradientgear:1512782705522245712> Whitelist Board", desc)
    embed.set_footer(text="HunterX")
    await ctx.send(embed=embed)

# ==================== SET PREFIX ====================
@bot.hybrid_command()
@commands.has_permissions(administrator=True)
async def setprefix(ctx, new_prefix: str):
    gid = str(ctx.guild.id)
    if gid not in config_data:
        config_data[gid] = {}
    config_data[gid]["prefix"] = new_prefix
    save_config()
    await send_embed(ctx, "<:HunteXCheck:1518422536558481448> Prefix Updated", f"New prefix is now `{new_prefix}`")

# ==================== AUTO ROLE ADD ====================
@bot.hybrid_command()
@commands.has_permissions(administrator=True)
async def autoroleadd(ctx, role: discord.Role):
    gid = str(ctx.guild.id)
    if gid not in config_data:
        config_data[gid] = {}
    config_data[gid]["autorole"] = role.id
    save_config()
    await send_embed(ctx, "<:HunteXCheck:1518422536558481448> AutoRole Set", f"{role.mention} will now be given to all new members.")

# ==================== AVATAR (aliases: av) ====================
@bot.hybrid_command(aliases=["avatar"])
async def av(ctx, member: discord.Member = None):
    target = member or ctx.author
    embed = discord.Embed(
        description=f"**{target.display_name}'s Avatar**",
        color=0xFFFFFF
    )
    embed.set_image(url=target.display_avatar.url)
    embed.set_footer(text="HunterX")
    await ctx.send(embed=embed)

# ==================== BANNER ====================
@bot.hybrid_command()
async def banner(ctx, member: discord.Member = None):
    target = member or ctx.author
    try:
        user = await bot.fetch_user(target.id)
        if not user.banner:
            return await send_embed(ctx, "No Banner", f"{target.display_name} has no banner.")
        embed = discord.Embed(
            description=f"**{target.display_name}'s Banner**",
            color=0xFFFFFF
        )
        embed.set_image(url=user.banner.url)
        embed.set_footer(text="HunterX")
        await ctx.send(embed=embed)
    except Exception as e:
        await send_embed(ctx, "<:HunterX:1512787796635422934> Error", str(e))

# ==================== ROLE INFO ====================
@bot.hybrid_command()
async def rinfo(ctx, role: discord.Role = None):
    if not role:
        return await send_embed(ctx, "Usage", "`$rinfo @role` — mention a role to view its info")
    created = role.created_at.strftime("%B %d, %Y")
    members_with_role = len([m for m in ctx.guild.members if role in m.roles])
    perms = []
    if role.permissions.administrator:
        perms.append("Administrator")
    if role.permissions.manage_guild:
        perms.append("Manage Server")
    if role.permissions.manage_channels:
        perms.append("Manage Channels")
    if role.permissions.manage_roles:
        perms.append("Manage Roles")
    if role.permissions.ban_members:
        perms.append("Ban Members")
    if role.permissions.kick_members:
        perms.append("Kick Members")
    if role.permissions.moderate_members:
        perms.append("Moderate Members")
    if role.permissions.manage_messages:
        perms.append("Manage Messages")
    perms_str = ", ".join(perms) if perms else "No special permissions"

    embed = discord.Embed(
        description=f"**Role Info — {role.mention}**",
        color=role.color if role.color.value else 0xFFFFFF
    )
    embed.add_field(name="Role Name", value=role.name, inline=True)
    embed.add_field(name="Role ID", value=str(role.id), inline=True)
    embed.add_field(name="Color", value=str(role.color), inline=True)
    embed.add_field(name="Position", value=str(role.position), inline=True)
    embed.add_field(name="Members", value=str(members_with_role), inline=True)
    embed.add_field(name="Mentionable", value="Yes" if role.mentionable else "No", inline=True)
    embed.add_field(name="Hoisted", value="Yes" if role.hoist else "No", inline=True)
    embed.add_field(name="Created", value=created, inline=True)
    embed.add_field(name="Key Permissions", value=perms_str, inline=False)
    embed.set_footer(text="HunterX")
    await ctx.send(embed=embed)

# ==================== SERVER PFP ====================
@bot.hybrid_command()
async def svpfp(ctx):
    guild = ctx.guild
    if not guild.icon:
        return await send_embed(ctx, "No Server Icon", "This server has no icon set.")
    embed = discord.Embed(
        description=f"**{guild.name} — Server Icon**",
        color=0xFFFFFF
    )
    embed.set_image(url=guild.icon.url)
    embed.set_footer(text="HunterX")
    await ctx.send(embed=embed)

# ==================== SERVER BANNER ====================
@bot.hybrid_command()
async def svbnr(ctx):
    guild = ctx.guild
    if not guild.banner:
        return await send_embed(ctx, "No Server Banner", "This server has no banner set.")
    embed = discord.Embed(
        description=f"**{guild.name} — Server Banner**",
        color=0xFFFFFF
    )
    embed.set_image(url=guild.banner.url)
    embed.set_footer(text="HunterX")
    await ctx.send(embed=embed)

# ==================== SET SERVER ICON ====================
@bot.hybrid_command()
@commands.has_permissions(manage_guild=True)
async def setsvicon(ctx):
    if not ctx.message.attachments:
        return await send_embed(ctx, "Usage", "`$setsvicon` — attach an image to set as the server icon")
    attachment = ctx.message.attachments[0]
    if not any(attachment.filename.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".gif", ".webp"]):
        return await send_embed(ctx, "<:HunterX:1512787796635422934> Invalid", "Please attach a valid image (PNG, JPG, GIF, WEBP).")
    try:
        image_data = await attachment.read()
        await ctx.guild.edit(icon=image_data, reason=f"HunterX setsvicon by {ctx.author}")
        await send_embed(ctx, "<:HunteXCheck:1518422536558481448> Server Icon Updated", "The server icon has been changed successfully.")
    except Exception as e:
        await send_embed(ctx, "<:HunterX:1512787796635422934> Error", str(e))

# ==================== SET SERVER BANNER ====================
@bot.hybrid_command()
@commands.has_permissions(manage_guild=True)
async def setsvbnr(ctx):
    if not ctx.message.attachments:
        return await send_embed(ctx, "Usage", "`$setsvbnr` — attach an image to set as the server banner")
    attachment = ctx.message.attachments[0]
    if not any(attachment.filename.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".gif", ".webp"]):
        return await send_embed(ctx, "<:HunterX:1512787796635422934> Invalid", "Please attach a valid image (PNG, JPG, GIF, WEBP).")
    try:
        image_data = await attachment.read()
        await ctx.guild.edit(banner=image_data, reason=f"HunterX setsvbnr by {ctx.author}")
        await send_embed(ctx, "<:HunteXCheck:1518422536558481448> Server Banner Updated", "The server banner has been changed successfully.")
    except Exception as e:
        await send_embed(ctx, "<:HunterX:1512787796635422934> Error", str(e))

# ==================== STICKY ====================
@bot.hybrid_command(with_app_command=False, )
@commands.has_permissions(manage_messages=True)
async def sticky(ctx, *, message: str):
    channel_id = ctx.channel.id
    if channel_id in sticky_messages:
        return await send_embed(ctx, "<:HunterX:1512787796635422934> Already Set",
            "This channel already has a sticky message. Use `$unsticky` first before setting a new one.")
    sent = await ctx.send(f"{message}")
    sticky_messages[channel_id] = {"text": message, "msg_id": sent.id}
    try:
        await ctx.message.delete()
    except:
        pass

# ==================== UNSTICKY ====================
@bot.hybrid_command()
@commands.has_permissions(manage_messages=True)
async def unsticky(ctx):
    channel_id = ctx.channel.id
    if channel_id not in sticky_messages:
        return await send_embed(ctx, "<:HunterX:1512787796635422934> No Sticky", "There is no sticky message in this channel.")
    old = sticky_messages.pop(channel_id)
    try:
        old_msg = await ctx.channel.fetch_message(old["msg_id"])
        await old_msg.delete()
    except:
        pass
    await send_embed(ctx, "<:HunteXCheck:1518422536558481448> Sticky Removed", "The sticky message has been removed.")

# ==================== SNIPE ====================
@bot.hybrid_command()
async def snipe(ctx):
    data = snipe_data.get(ctx.channel.id)
    if not data:
        return await send_embed(ctx, "<:HunterX:1512787796635422934> Nothing to Snipe", "No recently deleted messages found in this channel.")
    embed = discord.Embed(
        description=data["content"] or "*[No text content]*",
        color=0xFFFFFF,
        timestamp=data["time"]
    )
    embed.set_author(name=data["author"], icon_url=data["author_icon"])
    embed.set_footer(text="HunterX • Deleted message")
    await ctx.send(embed=embed)

# ==================== ROBLOX ====================
@bot.hybrid_command(with_app_command=False, )
async def rbx(ctx, *, username: str):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                "https://users.roblox.com/v1/usernames/users",
                json={"usernames": [username], "excludeBannedUsers": False}
            ) as resp:
                data = await resp.json()
                if not data.get("data"):
                    return await send_embed(ctx, "<:HunterX:1512787796635422934> Not Found", f"Roblox user `{username}` not found.")
                user_data = data["data"][0]
                user_id = user_data["id"]
                display_name = user_data["displayName"]
                roblox_name = user_data["name"]

            async with session.get(f"https://users.roblox.com/v1/users/{user_id}") as resp:
                profile = await resp.json()
                created_raw = profile.get("created", "")
                if created_raw:
                    created_dt = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
                    created_str = created_dt.strftime("%B %d, %Y")
                else:
                    created_str = "Unknown"

            async with session.get(f"https://friends.roblox.com/v1/users/{user_id}/followers/count") as resp:
                followers = (await resp.json()).get("count", 0)
            async with session.get(f"https://friends.roblox.com/v1/users/{user_id}/followings/count") as resp:
                following = (await resp.json()).get("count", 0)
            async with session.get(f"https://friends.roblox.com/v1/users/{user_id}/friends/count") as resp:
                friends = (await resp.json()).get("count", 0)
            async with session.get(
                f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={user_id}&size=150x150&format=Png&isCircular=false"
            ) as resp:
                thumb_data = await resp.json()
                avatar_url = thumb_data.get("data", [{}])[0].get("imageUrl", "")

            embed = make_embed("Roblox Profile")
            embed.add_field(name="Roblox User", value=f"{display_name} (@{roblox_name})", inline=True)
            embed.add_field(name="Roblox ID", value=str(user_id), inline=True)
            embed.add_field(name="\u200b", value="\u200b", inline=False)
            embed.add_field(name="Followers", value=f"{followers:,}", inline=True)
            embed.add_field(name="Following", value=f"{following:,}", inline=True)
            embed.add_field(name="Friends", value=f"{friends:,}", inline=True)
            embed.add_field(name="Account Created", value=created_str, inline=False)
            if avatar_url:
                embed.set_thumbnail(url=avatar_url)
            embed.set_footer(text="HunterX")
            await ctx.send(embed=embed)
        except Exception as e:
            await send_embed(ctx, "<:HunterX:1512787796635422934> Error", str(e))

# ==================== PURGE ====================
@bot.hybrid_command()
@commands.has_permissions(manage_messages=True)
async def purge(ctx, amount: int):
    if amount < 1 or amount > 500:
        return await send_embed(ctx, "Invalid", "Amount must be between 1 and 500.")
    try:
        await ctx.message.delete()
        deleted = await ctx.channel.purge(limit=amount)
        embed = make_embed("<:HunteXCheck:1518422536558481448> Purged", f"Deleted **{len(deleted)}** messages.")
        embed.set_footer(text="HunterX")
        await ctx.send(embed=embed)
    except Exception as e:
        await send_embed(ctx, "<:HunterX:1512787796635422934> Error", str(e))

# ==================== VERIFICATION ====================
@bot.hybrid_command()
@commands.has_permissions(administrator=True)
async def verification(ctx, action: str = "setup"):
    if action.lower() != "setup":
        return await send_embed(ctx, "Invalid", "Usage: $verification setup")
    guild = ctx.guild
    try:
        verified_role = discord.utils.get(guild.roles, name="VERIFIED")
        if not verified_role:
            verified_role = await guild.create_role(name="VERIFIED", color=discord.Color.green(), reason="HunterX Verification")
        existing = discord.utils.get(guild.text_channels, name="hunterx-verify")
        if existing:
            await existing.delete()
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=False),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            verified_role: discord.PermissionOverwrite(view_channel=True, send_messages=False),
        }
        verify_channel = await guild.create_text_channel(name="hunterx-verify", overwrites=overwrites)
        embed = discord.Embed(
            description=(
                f"**Welcome To {guild.name}** <a:kuromicheer:1513064044221960282>\n\n"
                f"Click the button below to verify yourself\n"
                f"and gain access to all channels."
            ),
            color=0xFFFFFF
        )
        embed.set_footer(text="HunterX")
        await verify_channel.send(embed=embed, view=VerifyView())

        hidden = 0
        for ch in list(guild.text_channels) + list(guild.voice_channels):
            if ch.id == verify_channel.id:
                continue
            try:
                await ch.set_permissions(guild.default_role, view_channel=False)
                await ch.set_permissions(verified_role, view_channel=True)
                hidden += 1
            except:
                pass
        for cat in guild.categories:
            try:
                await cat.set_permissions(guild.default_role, view_channel=False)
                await cat.set_permissions(verified_role, view_channel=True)
            except:
                pass

        await send_embed(ctx, "<:HunteXCheck:1518422536558481448> Verification Setup",
            f"{verify_channel.mention} created.\nVerified role: {verified_role.mention}\n\nHidden **{hidden}** channels from @everyone.")
    except Exception as e:
        await send_embed(ctx, "<:HunterX:1512787796635422934> Error", str(e))

# ==================== TICKET SETUP ====================
@bot.hybrid_command(name="ticketsetup", aliases=["ticketsetup1"])
@commands.has_permissions(administrator=True)
async def ticketsetup(ctx):
    guild = ctx.guild
    gid = str(guild.id)
    try:
        category = discord.utils.get(guild.categories, name="helpdesk")
        if not category:
            category = await guild.create_category("helpdesk")

        existing = discord.utils.get(guild.text_channels, name="hunterx-support")
        if existing:
            embed = discord.Embed(
                description=(
                    f"**<:HunteXCheck:1518422536558481448> Already Setup**\n\n"
                    f"Ticket system is already setup at {existing.mention}."
                ),
                color=0xFFFFFF
            )
            embed.set_footer(text="HunterX")
            return await ctx.send(embed=embed)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=False),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
        }
        for role in guild.roles:
            if role.permissions.administrator:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        support_ch = await guild.create_text_channel(
            name="hunterx-support",
            category=category,
            overwrites=overwrites,
            reason="HunterX Ticket Setup"
        )

        config_data.setdefault(gid, {})["ticket_channel"] = support_ch.id
        save_config()

        sv_name_caps = guild.name.split()[0].upper() if guild.name.split() else guild.name.upper()
        panel_embed = discord.Embed(
            description=(
                f"# {sv_name_caps}\n\n"
                f"# TICKET RULES\n\n"
                f"- 5 Hours no reply Ticket Close\n\n"
                f"- If you dont have need dont create ticket\n\n"
                f"- Troll ticket = Timeout 5hrs\n\n"
                f"- Spam ticket = Timeout 3days\n\n"
                f"1st attempt timeout 1 day\n"
                f"2nd attempt timeout 2 days\n"
                f"3rd attempt timeout 5days\n"
                f"4th attempt = Ban"
            ),
            color=0xFFFFFF
        )
        if guild.icon:
            panel_embed.set_image(url=guild.icon.url)
        panel_embed.set_footer(text="HunterX")
        await support_ch.send(embed=panel_embed, view=TicketView())

        await send_embed(ctx, "<:HunteXCheck:1518422536558481448> Ticket Setup Complete",
            f"Category *helpdesk* and {support_ch.mention} created.\nAll tickets will be created here.")
    except Exception as e:
        await send_embed(ctx, "<:HunterX:1512787796635422934> Error", str(e))

# ==================== TICKET LOGS ====================
@bot.hybrid_command(name="ticketlogs")
@commands.has_permissions(administrator=True)
async def ticketlogs(ctx):
    guild = ctx.guild
    gid = str(guild.id)
    try:
        category = discord.utils.get(guild.categories, name="helpdesk")
        if not category:
            category = await guild.create_category("helpdesk")

        existing = discord.utils.get(guild.text_channels, name="hunterx-ticketlogs")
        if existing:
            config_data.setdefault(gid, {})["ticketlog_channel"] = existing.id
            save_config()
            return await send_embed(ctx, "Already Exists", f"{existing.mention} already exists and is set as the ticket log channel.")

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        }
        for role in guild.roles:
            if role.permissions.administrator:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=False, read_message_history=True)

        log_ch = await guild.create_text_channel(
            name="hunterx-ticketlogs",
            category=category,
            overwrites=overwrites,
            reason="HunterX Ticket Log Setup"
        )
        config_data.setdefault(gid, {})["ticketlog_channel"] = log_ch.id
        save_config()
        await send_embed(ctx, "Ticket Log Setup",
            f"{log_ch.mention} created inside *helpdesk* category.\nAll ticket opens and closes will be logged here.")
    except Exception as e:
        await send_embed(ctx, "<:HunterX:1512787796635422934> Error", str(e))

# ==================== TICKET RESET ====================
@bot.hybrid_command(name="ticketreset")
@commands.has_permissions(administrator=True)
async def ticketreset(ctx):
    guild = ctx.guild
    gid = str(guild.id)
    try:
        support_ch = discord.utils.get(guild.text_channels, name="hunterx-support")
        if not support_ch:
            return await send_embed(ctx, "<:HunterX:1512787796635422934> Not Found",
                "No `hunterx-support` channel found. Run `$ticketsetup` first.")

        await support_ch.purge(limit=20)

        sv_name_caps = guild.name.split()[0].upper() if guild.name.split() else guild.name.upper()
        panel_embed = discord.Embed(
            description=(
                f"# {sv_name_caps}\n\n"
                f"# TICKET RULES\n\n"
                f"- 5 Hours no reply Ticket Close\n\n"
                f"- If you dont have need dont create ticket\n\n"
                f"- Troll ticket = Timeout 5hrs\n\n"
                f"- Spam ticket = Timeout 3days\n\n"
                f"1st attempt timeout 1 day\n"
                f"2nd attempt timeout 2 days\n"
                f"3rd attempt timeout 5days\n"
                f"4th attempt = Ban"
            ),
            color=0xFFFFFF
        )
        if guild.icon:
            panel_embed.set_image(url=guild.icon.url)
        panel_embed.set_footer(text="HunterX")
        await support_ch.send(embed=panel_embed, view=TicketView())

        await send_embed(ctx, "<:HunteXCheck:1518422536558481448> Ticket Panel Reset",
            f"Support panel in {support_ch.mention} has been refreshed.")
    except Exception as e:
        await send_embed(ctx, "<:HunterX:1512787796635422934> Error", str(e))

# ==================== USER INFO ====================
@bot.hybrid_command()
async def userinfo(ctx, member: discord.Member = None):
    target = member or ctx.author
    roles = [r.mention for r in target.roles if r.name != "@everyone"]
    roles_str = ", ".join(roles) if roles else "None"
    joined = target.joined_at.strftime("%B %d, %Y") if target.joined_at else "Unknown"
    created = target.created_at.strftime("%B %d, %Y")
    embed = discord.Embed(
        description=f"**User Info — {target.mention}**",
        color=target.color if target.color.value else 0xFFFFFF
    )
    embed.set_author(name=str(target), icon_url=target.display_avatar.url)
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="Display Name", value=target.display_name, inline=True)
    embed.add_field(name="UserID", value=str(target.id), inline=True)
    embed.add_field(name="Bot", value="Yes" if target.bot else "No", inline=True)
    embed.add_field(name="Account Created", value=created, inline=True)
    embed.add_field(name="Joined Server", value=joined, inline=True)
    embed.add_field(name=f"Roles ({len(roles)})", value=roles_str[:1024] if roles_str else "None", inline=False)
    embed.set_footer(text="HunterX")
    await ctx.send(embed=embed)

# ==================== LOCK / UNLOCK ====================
@bot.hybrid_command()
@commands.has_permissions(manage_channels=True)
async def lock(ctx, channel: discord.TextChannel = None):
    channel = channel or ctx.channel
    try:
        await channel.set_permissions(ctx.guild.default_role, send_messages=False)
        embed = make_embed("<:HunteXCheck:1518422536558481448> Channel Locked", f"{channel.mention} has been locked.")
        embed.set_footer(text="HunterX")
        msg = await ctx.send(embed=embed)
        await asyncio.sleep(5)
        try:
            await msg.delete()
            await ctx.message.delete()
        except:
            pass
    except Exception as e:
        await send_embed(ctx, "<:HunterX:1512787796635422934> Error", str(e))

@bot.hybrid_command()
@commands.has_permissions(manage_channels=True)
async def unlock(ctx, channel: discord.TextChannel = None):
    channel = channel or ctx.channel
    try:
        await channel.set_permissions(ctx.guild.default_role, send_messages=None)
        embed = make_embed("<:HunteXCheck:1518422536558481448> Channel Unlocked", f"{channel.mention} has been unlocked.")
        embed.set_footer(text="HunterX")
        msg = await ctx.send(embed=embed)
        await asyncio.sleep(5)
        try:
            await msg.delete()
            await ctx.message.delete()
        except:
            pass
    except Exception as e:
        await send_embed(ctx, "<:HunterX:1512787796635422934> Error", str(e))

# ==================== LOCKDOWN / UNLOCKDOWN ====================
@bot.hybrid_command()
@commands.has_permissions(administrator=True)
async def lockdown(ctx):
    count = 0
    for channel in ctx.guild.text_channels:
        try:
            await channel.set_permissions(ctx.guild.default_role, send_messages=False)
            count += 1
        except:
            pass
    embed = make_embed("<:HunteXCheck:1518422536558481448> Lockdown Active", f"Locked **{count}** channels.")
    embed.set_footer(text="HunterX")
    msg = await ctx.send(embed=embed)
    await asyncio.sleep(5)
    try:
        await msg.delete()
        await ctx.message.delete()
    except:
        pass

@bot.hybrid_command()
@commands.has_permissions(administrator=True)
async def unlockdown(ctx):
    count = 0
    for channel in ctx.guild.text_channels:
        try:
            await channel.set_permissions(ctx.guild.default_role, send_messages=None)
            count += 1
        except:
            pass
    embed = make_embed("<:HunteXCheck:1518422536558481448> Lockdown Lifted", f"Unlocked **{count}** channels.")
    embed.set_footer(text="HunterX")
    msg = await ctx.send(embed=embed)
    await asyncio.sleep(5)
    try:
        await msg.delete()
        await ctx.message.delete()
    except:
        pass

# ==================== ANTINUKE ====================
@bot.hybrid_command()
async def antinuke(ctx, action: str):
    if not is_owner(ctx) and not ctx.author.guild_permissions.administrator:
        return await send_embed(ctx, "<:HunterX:1512787796635422934> No Permission", "You need administrator permission.")
    gid = str(ctx.guild.id)
    config_data.setdefault(gid, {})
    if action.lower() == "enable":
        config_data[gid]["antinuke"] = True
        save_config()
        await send_embed(ctx, "<:HunteXCheck:1518422536558481448> AntiNuke Enabled", "Anti Nuke protection is now **enabled**.")
    elif action.lower() == "disable":
        config_data[gid]["antinuke"] = False
        save_config()
        await send_embed(ctx, "<:HunterXsadkitty:1514606490063868074> AntiNuke Disabled", "Anti Nuke protection is now **disabled**.")
    else:
        await send_embed(ctx, "Invalid", "Usage: `$antinuke enable/disable`")

@bot.hybrid_command()
async def antikick(ctx, action: str):
    if not is_owner(ctx) and not ctx.author.guild_permissions.administrator:
        return await send_embed(ctx, "<:HunterX:1512787796635422934> No Permission", "You need administrator permission.")
    gid = str(ctx.guild.id)
    config_data.setdefault(gid, {})
    if action.lower() == "enable":
        config_data[gid]["antikick"] = True
        save_config()
        await send_embed(ctx, "<:HunteXCheck:1518422536558481448> AntiKick Enabled", "Unauthorized kickers will be **banned**.")
    elif action.lower() == "disable":
        config_data[gid]["antikick"] = False
        save_config()
        await send_embed(ctx, "<:HunterXsadkitty:1514606490063868074> AntiKick Disabled", "AntiKick protection is now **disabled**.")
    else:
        await send_embed(ctx, "Invalid", "Usage: `$antikick enable/disable`")

@bot.hybrid_command()
async def antiban(ctx, action: str):
    if not is_owner(ctx) and not ctx.author.guild_permissions.administrator:
        return await send_embed(ctx, "<:HunterX:1512787796635422934> No Permission", "You need administrator permission.")
    gid = str(ctx.guild.id)
    config_data.setdefault(gid, {})
    if action.lower() == "enable":
        config_data[gid]["antiban"] = True
        save_config()
        await send_embed(ctx, "<:HunteXCheck:1518422536558481448> AntiBan Enabled", "Unauthorized banners will be **banned**.")
    elif action.lower() == "disable":
        config_data[gid]["antiban"] = False
        save_config()
        await send_embed(ctx, "<:HunterXsadkitty:1514606490063868074> AntiBan Disabled", "Anti Ban protection is now **disabled**.")
    else:
        await send_embed(ctx, "Invalid", "Usage: `$antiban enable/disable`")

@bot.hybrid_command()
async def antibotadd(ctx, action: str):
    if not is_owner(ctx) and not ctx.author.guild_permissions.administrator:
        return await send_embed(ctx, "<:HunterX:1512787796635422934> No Permission", "You need administrator permission.")
    gid = str(ctx.guild.id)
    config_data.setdefault(gid, {})
    if action.lower() == "enable":
        config_data[gid]["antibotadd"] = True
        save_config()
        await send_embed(ctx, "<:HunteXCheck:1518422536558481448> AntiBotAdd Enabled", "Unauthorized bot additions will result in a **ban**.")
    elif action.lower() == "disable":
        config_data[gid]["antibotadd"] = False
        save_config()
        await send_embed(ctx, "<:HunterXsadkitty:1514606490063868074> AntiBotAdd Disabled", "AntiBot Add protection is now **disabled**.")
    else:
        await send_embed(ctx, "Invalid", "Usage: `$antibotadd enable/disable`")

@bot.hybrid_command(name="anticrtadminrole", aliases=["anticreateadminrole"])
async def anticrtadminrole(ctx, action: str):
    if not is_owner(ctx) and not ctx.author.guild_permissions.administrator:
        return await send_embed(ctx, "<:HunterX:1512787796635422934> No Permission", "You need administrator permission.")
    gid = str(ctx.guild.id)
    config_data.setdefault(gid, {})
    if action.lower() == "enable":
        config_data[gid]["anticreateadminrole"] = True
        save_config()
        await send_embed(ctx, "<:HunteXCheck:1518422536558481448> AntiCrtAdminRole Enabled", "Creating an admin role without whitelist will result in a **ban**.")
    elif action.lower() == "disable":
        config_data[gid]["anticreateadminrole"] = False
        save_config()
        await send_embed(ctx, "<:HunterXsadkitty:1514606490063868074> AntiCrtAdminRole Disabled", "Protection is now **disabled**.")
    else:
        await send_embed(ctx, "Invalid", "Usage: `$anticrtadminrole enable/disable`")

@bot.hybrid_command(name="anticrtwebhook", aliases=["antiwebhookcreate"])
async def anticrtwebhook(ctx, action: str):
    if not is_owner(ctx) and not ctx.author.guild_permissions.administrator:
        return await send_embed(ctx, "<:HunterX:1512787796635422934> No Permission", "You need administrator permission.")
    gid = str(ctx.guild.id)
    config_data.setdefault(gid, {})
    if action.lower() == "enable":
        config_data[gid]["antiwebhookcreate"] = True
        save_config()
        await send_embed(ctx, "<:HunteXCheck:1518422536558481448> AntiCrtWebhook Enabled", "Unauthorized webhook creation will result in a **ban**.")
    elif action.lower() == "disable":
        config_data[gid]["antiwebhookcreate"] = False
        save_config()
        await send_embed(ctx, "<:HunterXsadkitty:1514606490063868074> AntiCrtWebhook Disabled", "Protection is now **disabled**.")
    else:
        await send_embed(ctx, "Invalid", "Usage: `$anticrtwebhook enable/disable`")

@bot.hybrid_command(name="anticrtchannel", aliases=["anticreatechannel"])
async def anticrtchannel(ctx, action: str):
    if not is_owner(ctx) and not ctx.author.guild_permissions.administrator:
        return await send_embed(ctx, "<:HunterX:1512787796635422934> No Permission", "You need administrator permission.")
    gid = str(ctx.guild.id)
    config_data.setdefault(gid, {})
    if action.lower() == "enable":
        config_data[gid]["anticreatechannel"] = True
        save_config()
        await send_embed(ctx, "<:HunteXCheck:1518422536558481448> AntiCrtChannel Enabled", "Unauthorized channel creation will be blocked and deleted.")
    elif action.lower() == "disable":
        config_data[gid]["anticreatechannel"] = False
        save_config()
        await send_embed(ctx, "<:HunterXsadkitty:1514606490063868074> AntiCrtChannel Disabled", "Protection is now **disabled**.")
    else:
        await send_embed(ctx, "Invalid", "Usage: `$anticrtchannel enable/disable`")

@bot.hybrid_command(name="antidelchannel", aliases=["antideletechannel"])
async def antidelchannel(ctx, action: str):
    if not is_owner(ctx) and not ctx.author.guild_permissions.administrator:
        return await send_embed(ctx, "<:HunterX:1512787796635422934> No Permission", "You need administrator permission.")
    gid = str(ctx.guild.id)
    config_data.setdefault(gid, {})
    if action.lower() == "enable":
        config_data[gid]["antideletechannel"] = True
        save_config()
        await send_embed(ctx, "<:HunteXCheck:1518422536558481448> AntiDeleteChannel Enabled", "Unauthorized channel deletion will be logged and the user banned.")
    elif action.lower() == "disable":
        config_data[gid]["antideletechannel"] = False
        save_config()
        await send_embed(ctx, "<:HunterXsadkitty:1514606490063868074> AntiDeleteChannel Disabled", "Protection is now **disabled**.")
    else:
        await send_embed(ctx, "Invalid", "Usage: `$antidelchannel enable/disable`")

# ==================== ANTI DELETE ROLE ====================
@bot.hybrid_command(name="antidelrole", aliases=["antideleterole"])
async def antidelrole(ctx, action: str):
    if not is_owner(ctx) and not ctx.author.guild_permissions.administrator:
        return await send_embed(ctx, "<:HunterX:1512787796635422934> No Permission", "You need administrator permission.")
    gid = str(ctx.guild.id)
    config_data.setdefault(gid, {})
    if action.lower() == "enable":
        config_data[gid]["antideleterole"] = True
        save_config()
        await send_embed(ctx, "<:HunteXCheck:1518422536558481448> AntiDeleteRole Enabled", "Deleting a role without whitelist will result in a **ban**.")
    elif action.lower() == "disable":
        config_data[gid]["antideleterole"] = False
        save_config()
        await send_embed(ctx, "<:HunterXsadkitty:1514606490063868074> AntiDeleteRole Disabled", "Protection is now **disabled**.")
    else:
        await send_embed(ctx, "Invalid", "Usage: `$antidelrole enable/disable`")

# ==================== ENABLE/DISABLE ALL SECURITY ====================
SECURITY_KEYS = [
    "antinuke",
    "antikick",
    "antiban",
    "antibotadd",
    "anticreateadminrole",
    "antiwebhookcreate",
    "anticreatechannel",
    "antideletechannel",
    "antideleterole",
    "antilink",
    "antispam",
]

SECURITY_LABELS = {
    "antinuke": "Antinuke",
    "antikick": "Antikick",
    "antiban": "Antiban",
    "antibotadd": "Antiaddbot",
    "anticreateadminrole": "Anticreaterole",
    "antiwebhookcreate": "Anticreatewebhook",
    "anticreatechannel": "Anticreatechannel",
    "antideletechannel": "Antideletechannel",
    "antideleterole": "Antideleterole",
    "antilink": "Antilink",
    "antispam": "Antispam",
}

@bot.hybrid_command(name="securityall", aliases=["enableall", "antinukeall"])
async def securityall(ctx, action: str):
    if not is_owner(ctx) and not ctx.author.guild_permissions.administrator:
        return await send_embed(ctx, "<:HunterX:1512787796635422934> No Permission", "You need administrator permission.")
    gid = str(ctx.guild.id)
    config_data.setdefault(gid, {})
    if action.lower() == "enable":
        for key in SECURITY_KEYS:
            config_data[gid][key] = True
        save_config()
        await send_embed(ctx, "All Security Enabled",
            "All Anti Nuke protections are now **enabled**:\n\n" +
            "\n".join(f"`{SECURITY_LABELS[key]}`" for key in SECURITY_KEYS))
    elif action.lower() == "disable":
        for key in SECURITY_KEYS:
            config_data[gid][key] = False
        save_config()
        await send_embed(ctx, "All Security Disabled",
            "All Anti Nuke protections are now **disabled**.")
    else:
        await send_embed(ctx, "Invalid", "Usage: `$securityall enable/disable`")

# ==================== WARNS SYSTEM ====================
@bot.hybrid_command(with_app_command=False, name="warn")
@commands.has_permissions(manage_messages=True)
async def warn(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    if member.bot:
        return await send_embed(ctx, "<:HunterX:1512787796635422934> Invalid", "You cannot warn a bot.")
    if member.id == ctx.guild.owner_id:
        return await send_embed(ctx, "<:HunterX:1512787796635422934> Invalid", "You cannot warn the server owner.")
    gid = str(ctx.guild.id)
    uid = str(member.id)
    warns_data.setdefault(gid, {}).setdefault(uid, [])
    warns_data[gid][uid].append({"reason": reason, "mod": str(ctx.author), "time": datetime.now(PH_TIME).strftime("%Y-%m-%d %H:%M")})
    save_warns()
    count = len(warns_data[gid][uid])

    action_taken = ""
    try:
        if count == 1:
            until = discord.utils.utcnow() + timedelta(hours=1)
            await member.timeout(until, reason=f"HunterX Warn #{count}: {reason}")
            action_taken = "\n**Auto Action:** Muted for 1 hour"
        elif count == 2:
            await member.kick(reason=f"HunterX Warn #{count}: {reason}")
            action_taken = "\n**Auto Action:** Kicked from server"
        elif count >= 3:
            await member.ban(reason=f"HunterX Warn #{count}: {reason}")
            action_taken = "\n**Auto Action:** Banned from server"
    except Exception as e:
        action_taken = f"\n**Auto Action failed:** {e}"

    await send_embed(ctx, "<:HunteXCheck:1518422536558481448> User Warned",
        f"**User:** {member.mention}\n**Warns:** `{count}`\n**Reason:** {reason}{action_taken}")
    await log_action(ctx.guild, "<:HunterXwarn:1515422027521986720> Member Warned",
        f"**User:** {member} (`{member.id}`)\n**Warns:** `{count}`\n**Reason:** {reason}\n**Mod:** {ctx.author}",
        member.display_avatar.url)
    await log_mod_action(ctx.guild, "<:HunterXwarn:1515422027521986720> Member Warned",
        f"**User:** {member} (`{member.id}`)\n**Warns:** `{count}`\n**Reason:** {reason}\n**Auto Action:** {action_taken.strip() if action_taken else 'None'}\n**Mod:** {ctx.author}",
        member.display_avatar.url)

@bot.hybrid_command(name="checkwarns")
@commands.has_permissions(manage_messages=True)
async def checkwarns(ctx, member: discord.Member):
    gid = str(ctx.guild.id)
    uid = str(member.id)
    user_warns = warns_data.get(gid, {}).get(uid, [])
    if not user_warns:
        return await send_embed(ctx, "No Warns", f"{member.mention} has no warnings.")
    lines = []
    for i, w in enumerate(user_warns, 1):
        lines.append(f"**{i}.** {w['reason']} — by {w['mod']} ({w['time']})")
    await send_embed(ctx, f"<:HunterXwarn:1515422027521986720> Warns for {member.display_name} ({len(user_warns)})",
        "\n".join(lines))

@bot.hybrid_command(name="clearwarns")
@commands.has_permissions(manage_messages=True)
async def clearwarns(ctx, member: discord.Member):
    gid = str(ctx.guild.id)
    uid = str(member.id)
    if not warns_data.get(gid, {}).get(uid):
        return await send_embed(ctx, "No Warns", f"{member.mention} has no warnings to clear.")
    warns_data[gid][uid] = []
    save_warns()
    await send_embed(ctx, "<:HunteXCheck:1518422536558481448> Warns Cleared",
        f"All warnings for {member.mention} have been cleared.")

@bot.hybrid_command(name="unwarn")
@commands.has_permissions(manage_messages=True)
async def unwarn(ctx, member: discord.Member):
    gid = str(ctx.guild.id)
    uid = str(member.id)
    user_warns = warns_data.get(gid, {}).get(uid, [])
    if not user_warns:
        return await send_embed(ctx, "No Warns", f"{member.mention} has no warnings to remove.")
    removed = user_warns.pop()
    warns_data[gid][uid] = user_warns
    save_warns()
    remaining = len(user_warns)
    await send_embed(ctx, "<:HunteXCheck:1518422536558481448> Warn Removed",
        f"Removed last warning for {member.mention}.\n**Removed reason:** {removed['reason']}\n**Remaining warns:** `{remaining}`")

# ==================== ALLOWED LINK ====================
@bot.hybrid_command(with_app_command=False, )
@commands.has_permissions(administrator=True)
async def allowedlink(ctx, *targets):
    if not targets:
        return await send_embed(ctx, "Usage", "`$allowedlink @user or @role` — mention one or more users/roles")
    gid = str(ctx.guild.id)
    config_data.setdefault(gid, {})
    if "allowed_link_users" not in config_data[gid]:
        config_data[gid]["allowed_link_users"] = []
    if "allowed_link_roles" not in config_data[gid]:
        config_data[gid]["allowed_link_roles"] = []

    added = []
    for user in ctx.message.mentions:
        uid = user.id
        if uid not in config_data[gid]["allowed_link_users"]:
            config_data[gid]["allowed_link_users"].append(uid)
        added.append(user.mention)
    for role in ctx.message.role_mentions:
        rid = role.id
        if rid not in config_data[gid]["allowed_link_roles"]:
            config_data[gid]["allowed_link_roles"].append(rid)
        added.append(role.mention)

    if not added:
        return await send_embed(ctx, "No Targets", "Please mention a user or role.")

    save_config()
    await send_embed(ctx, "<:HunteXCheck:1518422536558481448> Allowed Link Updated",
        "These can now send Discord invite links:\n" + "\n".join(added))

# ==================== ALLOWED LINK BOARD ====================
@bot.hybrid_command()
@commands.has_permissions(administrator=True)
async def allowedlinkboard(ctx):
    gid = str(ctx.guild.id)
    cfg = config_data.get(gid, {})
    user_ids = cfg.get("allowed_link_users", [])
    role_ids = cfg.get("allowed_link_roles", [])
    legacy_role_id = cfg.get("allowed_link_role")
    if legacy_role_id and legacy_role_id not in role_ids:
        role_ids = [legacy_role_id] + role_ids

    lines = []
    for uid in user_ids:
        member = ctx.guild.get_member(uid)
        lines.append(f"{member.mention if member else f'<@{uid}>'}")
    for rid in role_ids:
        role = ctx.guild.get_role(rid)
        lines.append(f"{role.mention if role else f'<@&{rid}>'}")

    if not lines:
        return await send_embed(ctx, "<:249630gradientgear:1512782705522245712> Allowed Link Board", "No users or roles are allowed to send links.")

    embed = make_embed("<:249630gradientgear:1512782705522245712> Allowed Link Board", "\n".join(lines))
    embed.set_footer(text="HunterX")
    await ctx.send(embed=embed)

# ==================== ANTI LINK ====================
@bot.hybrid_command()
async def antilink(ctx, action: str):
    if not is_owner(ctx) and not ctx.author.guild_permissions.administrator:
        return await send_embed(ctx, "<:HunterX:1512787796635422934> No Permission", "You need administrator permission.")
    gid = str(ctx.guild.id)
    config_data.setdefault(gid, {})
    if action.lower() == "enable":
        config_data[gid]["antilink"] = True
        save_config()
        await send_embed(ctx, "<:HunteXCheck:1518422536558481448> AntiLink Enabled", "Discord invite links will be auto deleted.")
    elif action.lower() == "disable":
        config_data[gid]["antilink"] = False
        save_config()
        await send_embed(ctx, "<:HunterXsadkitty:1514606490063868074> AntiLink Disabled", "Discord invite links will NOT be deleted.")
    else:
        await send_embed(ctx, "Invalid", "Usage: `$antilink enable/disable`")

# ==================== ANTI SPAM ====================
@bot.hybrid_command()
async def antispam(ctx, action: str):
    if not is_owner(ctx) and not ctx.author.guild_permissions.administrator:
        return await send_embed(ctx, "<:HunterX:1512787796635422934> No Permission", "You need administrator permission.")
    gid = str(ctx.guild.id)
    config_data.setdefault(gid, {})
    if action.lower() == "enable":
        config_data[gid]["antispam"] = True
        save_config()
        await send_embed(ctx, "<:HunteXCheck:1518422536558481448> AntiSpam Enabled", "Members who spam 10+ messages rapidly will be timed out for 5 minutes.")
    elif action.lower() == "disable":
        config_data[gid]["antispam"] = False
        save_config()
        await send_embed(ctx, "<:HunterXsadkitty:1514606490063868074> AntiSpam Disabled", "AntiSpam protection is now **disabled**.")
    else:
        await send_embed(ctx, "Invalid", "Usage: `$antispam enable/disable`")

# ==================== DELETE MSG LOG COMMAND ====================
@bot.hybrid_command()
@commands.has_permissions(administrator=True)
async def deletemsglog(ctx):
    guild = ctx.guild
    gid = str(guild.id)
    try:
        existing = discord.utils.get(guild.text_channels, name="hunterx-dltmsglogs")
        if existing:
            config_data.setdefault(gid, {})["deletemsg_channel"] = existing.id
            save_config()
            return await send_embed(ctx, "<:HunteXCheck:1518422536558481448> Already Exists",
                f"{existing.mention} is already set as the deleted message log channel.")
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        }
        for role in guild.roles:
            if role.permissions.administrator:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=False, read_message_history=True)
        log_ch = await guild.create_text_channel(
            name="hunterx-dltmsglogs",
            overwrites=overwrites,
            reason="HunterX Delete Message Log Setup"
        )
        config_data.setdefault(gid, {})["deletemsg_channel"] = log_ch.id
        save_config()
        await send_embed(ctx, "<:HunteXCheck:1518422536558481448> Delete Log Setup",
            f"{log_ch.mention} created. Deleted messages will be logged here (admin-only).")
    except Exception as e:
        await send_embed(ctx, "<:HunterX:1512787796635422934> Error", str(e))

# ==================== EDIT MSG LOG COMMAND ====================
@bot.hybrid_command()
@commands.has_permissions(administrator=True)
async def editmsglogs(ctx):
    guild = ctx.guild
    gid = str(guild.id)
    try:
        existing = discord.utils.get(guild.text_channels, name="hunterx-editmsglogs")
        if existing:
            config_data.setdefault(gid, {})["editmsg_channel"] = existing.id
            save_config()
            return await send_embed(ctx, "<:HunteXCheck:1518422536558481448> Already Exists",
                f"{existing.mention} is already set as the edited message log channel.")
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        }
        for role in guild.roles:
            if role.permissions.administrator:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=False, read_message_history=True)
        log_ch = await guild.create_text_channel(
            name="hunterx-editmsglogs",
            overwrites=overwrites,
            reason="HunterX Edit Message Log Setup"
        )
        config_data.setdefault(gid, {})["editmsg_channel"] = log_ch.id
        save_config()
        await send_embed(ctx, "<:HunteXCheck:1518422536558481448> Edit Log Setup",
            f"{log_ch.mention} created. Edited messages will be logged here (admin-only).")
    except Exception as e:
        await send_embed(ctx, "<:HunterX:1512787796635422934> Error", str(e))

# ==================== MOD LOGS COMMAND ====================
@bot.hybrid_command()
@commands.has_permissions(administrator=True)
async def modlogs(ctx):
    guild = ctx.guild
    gid = str(guild.id)
    try:
        existing = discord.utils.get(guild.text_channels, name="hunterx-modlogs")
        if existing:
            config_data.setdefault(gid, {})["modlogs_channel"] = existing.id
            save_config()
            return await send_embed(ctx, "<:HunteXCheck:1518422536558481448> Already Exists",
                f"{existing.mention} is already set as the mod logs channel.")
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        }
        for role in guild.roles:
            if role.permissions.administrator:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=False, read_message_history=True)
        log_ch = await guild.create_text_channel(
            name="hunterx-modlogs",
            overwrites=overwrites,
            reason="HunterX Mod Logs Setup"
        )
        config_data.setdefault(gid, {})["modlogs_channel"] = log_ch.id
        save_config()
        await send_embed(ctx, "<:HunteXCheck:1518422536558481448> Mod Logs Setup",
            f"{log_ch.mention} created. All mod actions (ban, kick, timeout, warn) will be logged here (admin-only).")
    except Exception as e:
        await send_embed(ctx, "<:HunterX:1512787796635422934> Error", str(e))

# ==================== CONFIG ====================
@bot.hybrid_command(name="config")
async def config_cmd(ctx):
    gid = str(ctx.guild.id)
    cfg = config_data.get(gid, {})

    def status(val):
        return "Enabled" if val else "Disabled"

    log_ch = ctx.guild.get_channel(log_channels.get(gid, 0))
    welcome_ch_id = cfg.get("welcome_channel")
    welcome_ch = ctx.guild.get_channel(welcome_ch_id) if welcome_ch_id else None
    autorole_id = cfg.get("autorole")
    autorole = ctx.guild.get_role(autorole_id) if autorole_id else None
    deletemsg_ch_id = cfg.get("deletemsg_channel")
    deletemsg_ch = ctx.guild.get_channel(deletemsg_ch_id) if deletemsg_ch_id else None
    boost_ch_id = cfg.get("boost_channel")
    boost_ch = ctx.guild.get_channel(boost_ch_id) if boost_ch_id else None

    editmsg_ch_id = cfg.get("editmsg_channel")
    editmsg_ch = ctx.guild.get_channel(editmsg_ch_id) if editmsg_ch_id else None
    modlogs_ch_id = cfg.get("modlogs_channel")
    modlogs_ch = ctx.guild.get_channel(modlogs_ch_id) if modlogs_ch_id else None
    not_set = "Not Set"
    embed = make_embed(
        "Server Configuration",
        f"**Anti-Nuke Settings**\n"
        f"Anti Nuke: `{status(cfg.get('antinuke', False))}`\n"
        f"Anti Kick: `{status(cfg.get('antikick', False))}`\n"
        f"Anti Ban: `{status(cfg.get('antiban', False))}`\n"
        f"Anti Bot Add: `{status(cfg.get('antibotadd', False))}`\n"
        f"Anti Admin Role: `{status(cfg.get('anticreateadminrole', False))}`\n"
        f"Anti Webhook: `{status(cfg.get('antiwebhookcreate', False))}`\n"
        f"Anti Link: `{status(cfg.get('antilink', False))}`\n"
        f"Anti Spam: `{status(cfg.get('antispam', False))}`\n"
        f"Anti Create Channel: `{status(cfg.get('anticreatechannel', False))}`\n"
        f"Anti Delete Channel: `{status(cfg.get('antideletechannel', False))}`\n"
        f"Anti Delete Role: `{status(cfg.get('antideleterole', False))}`\n\n"
        f"**Channels**\n"
        f"Log: {log_ch.mention if log_ch else not_set}\n"
        f"Welcome: {welcome_ch.mention if welcome_ch else not_set}\n"
        f"Delete Msg Log: {deletemsg_ch.mention if deletemsg_ch else not_set}\n"
        f"Edit Msg Log: {editmsg_ch.mention if editmsg_ch else not_set}\n"
        f"Mod Logs: {modlogs_ch.mention if modlogs_ch else not_set}\n"
        f"Boost Channel: {boost_ch.mention if boost_ch else not_set}\n\n"
        f"**Other**\n"
        f"Auto Role: {autorole.mention if autorole else not_set}\n"
        f"Prefix: `{cfg.get('prefix', '$')}`"
    )
    embed.set_footer(text="HunterX")
    await ctx.send(embed=embed)

# ==================== AUTO RESPOND ====================
@bot.hybrid_command(with_app_command=False, )
@commands.has_permissions(administrator=True)
async def autorespondadd(ctx, trigger: str, *, reply: str):
    gid = str(ctx.guild.id)
    if gid not in autorespond_data:
        autorespond_data[gid] = {}
    trigger_key = trigger.lower()
    if trigger_key in autorespond_data[gid]:
        return await send_embed(ctx, "Already Exists", f"Trigger `{trigger}` already exists. Use `$autorespondedit` to change it.")
    autorespond_data[gid][trigger_key] = reply
    save_data(AUTORESPOND_FILE, autorespond_data)
    await send_embed(ctx, "<:HunteXCheck:1518422536558481448> AutoRespond Added", f"Trigger: `{trigger}`\nReply: {reply}")

@bot.hybrid_command(with_app_command=False, )
@commands.has_permissions(administrator=True)
async def autorespondedit(ctx, trigger: str, *, reply: str):
    gid = str(ctx.guild.id)
    trigger_key = trigger.lower()
    if gid not in autorespond_data or trigger_key not in autorespond_data.get(gid, {}):
        return await send_embed(ctx, "<:HunterX:1512787796635422934> Not Found", f"Trigger `{trigger}` not found. Use `$autorespondadd` to create it.")
    autorespond_data[gid][trigger_key] = reply
    save_data(AUTORESPOND_FILE, autorespond_data)
    await send_embed(ctx, "<:HunteXCheck:1518422536558481448> AutoRespond Updated", f"Trigger: `{trigger}`\nNew Reply: {reply}")

@bot.hybrid_command()
@commands.has_permissions(administrator=True)
async def autorespondremove(ctx, trigger: str):
    gid = str(ctx.guild.id)
    trigger_key = trigger.lower()
    if gid not in autorespond_data or trigger_key not in autorespond_data.get(gid, {}):
        return await send_embed(ctx, "<:HunterX:1512787796635422934> Not Found", f"Trigger `{trigger}` not found.")
    del autorespond_data[gid][trigger_key]
    save_data(AUTORESPOND_FILE, autorespond_data)
    await send_embed(ctx, "<:HunterXsadkitty:1514606490063868074> AutoRespond Removed", f"Trigger `{trigger}` has been removed.")

# ==================== BACKUP CREATE ====================
import secrets as _secrets

@bot.hybrid_command()
async def backupcreate(ctx):
    if not is_owner(ctx) and not ctx.author.guild_permissions.administrator:
        return await send_embed(ctx, "<:HunterX:1512787796635422934> No Permission", "You need administrator permission.")
    guild = ctx.guild
    gid = str(guild.id)

    backup = {
        "guild_id": gid,
        "guild_name": guild.name,
        "created_by": str(ctx.author.id),
        "created_at": datetime.now(PH_TIME).strftime("%B %d, %Y %I:%M %p"),
        "verification_level": str(guild.verification_level),
        "roles": [],
        "categories": [],
        "channels": [],
        "messages": {},
    }

    for role in guild.roles:
        if role.is_default():
            continue
        backup["roles"].append({
            "name": role.name,
            "color": role.color.value,
            "permissions": role.permissions.value,
            "hoist": role.hoist,
            "mentionable": role.mentionable,
            "position": role.position,
        })

    for cat in guild.categories:
        backup["categories"].append({"name": cat.name, "position": cat.position})

    total_messages = 0
    for ch in guild.channels:
        if isinstance(ch, discord.CategoryChannel):
            continue
        ch_data = {
            "name": ch.name,
            "type": str(ch.type),
            "category_name": ch.category.name if ch.category else None,
            "position": ch.position,
        }
        if isinstance(ch, discord.TextChannel):
            ch_data["topic"] = ch.topic
            ch_data["slowmode_delay"] = ch.slowmode_delay
            ch_data["nsfw"] = ch.nsfw
            try:
                msgs = []
                async for msg in ch.history(limit=100, oldest_first=True):
                    if msg.author.bot:
                        continue
                    attachments = [a.url for a in msg.attachments]
                    msgs.append({
                        "author_name": msg.author.display_name,
                        "author_id": str(msg.author.id),
                        "author_avatar": str(msg.author.display_avatar.url),
                        "content": msg.content,
                        "timestamp": msg.created_at.strftime("%B %d, %Y %I:%M %p"),
                        "attachments": attachments,
                    })
                if msgs:
                    backup["messages"][ch.name] = msgs
                    total_messages += len(msgs)
            except Exception:
                pass
        backup["channels"].append(ch_data)

    backup_id = _secrets.token_hex(4).upper()
    if gid not in backup_store:
        backup_store[gid] = {}
    backup_store[gid][backup_id] = backup
    save_data(BACKUP_FILE, backup_store)

    await send_embed(ctx, "<:HunteXCheck:1518422536558481448> Backup Created",
        f"**Backup ID:** `{backup_id}`\n"
        f"Use `$backuprestore {backup_id}` to restore.\n\n"
        f"**Roles:** {len(backup['roles'])}\n"
        f"**Categories:** {len(backup['categories'])}\n"
        f"**Channels:** {len(backup['channels'])}\n"
        f"**Messages saved:** {total_messages}\n"
        f"**Date:** {backup['created_at']}")
    try:
        await ctx.message.delete()
    except:
        pass

# ==================== BACKUP RESTORE ====================
@bot.hybrid_command()
async def backuprestore(ctx, backup_id: str = None):
    if not is_owner(ctx) and not ctx.author.guild_permissions.administrator:
        return await send_embed(ctx, "<:HunterX:1512787796635422934> No Permission", "You need administrator permission.")
    if not backup_id:
        return await send_embed(ctx, "<:HunterX:1512787796635422934> Missing ID", "Usage: `$backuprestore <ID>`")

    guild = ctx.guild
    gid = str(guild.id)
    backup_id = backup_id.upper()
    guild_backups = backup_store.get(gid, {})
    backup = guild_backups.get(backup_id)
    if not backup:
        ids = ", ".join([f"`{i}`" for i in guild_backups.keys()]) if guild_backups else "None"
        return await send_embed(ctx, "<:HunterX:1512787796635422934> Backup Not Found",
            f"No backup with ID `{backup_id}`.\n\n**Available IDs:** {ids}")

    await send_embed(ctx, "<a:HunterxRestore:1514609270463791187> Restoring Backup",
        f"Restoring from backup `{backup_id}` ({backup.get('created_at', 'Unknown date')})...\nThis may take a moment.")

    created_roles, created_cats, created_chs, restored_msgs = 0, 0, 0, 0
    existing_role_names = {r.name for r in guild.roles}
    for role_data in sorted(backup.get("roles", []), key=lambda r: r["position"]):
        if role_data["name"] not in existing_role_names:
            try:
                await guild.create_role(
                    name=role_data["name"],
                    color=discord.Color(role_data["color"]),
                    permissions=discord.Permissions(role_data["permissions"]),
                    hoist=role_data["hoist"],
                    mentionable=role_data["mentionable"],
                    reason=f"HunterX Backup Restore [{backup_id}]",
                )
                created_roles += 1
            except:
                pass

    existing_cat_names = {c.name for c in guild.categories}
    for cat_data in sorted(backup.get("categories", []), key=lambda c: c["position"]):
        if cat_data["name"] not in existing_cat_names:
            try:
                await guild.create_category(name=cat_data["name"], reason=f"HunterX Backup Restore [{backup_id}]")
                created_cats += 1
            except:
                pass

    existing_ch_names = {c.name for c in guild.channels}
    restored_channels = {}
    for ch_data in backup.get("channels", []):
        category = discord.utils.get(guild.categories, name=ch_data["category_name"]) if ch_data.get("category_name") else None
        if ch_data["name"] not in existing_ch_names:
            try:
                if ch_data["type"] == "text":
                    new_ch = await guild.create_text_channel(
                        name=ch_data["name"], category=category,
                        topic=ch_data.get("topic"), slowmode_delay=ch_data.get("slowmode_delay", 0),
                        nsfw=ch_data.get("nsfw", False), reason=f"HunterX Backup Restore [{backup_id}]",
                    )
                    restored_channels[ch_data["name"]] = new_ch
                    created_chs += 1
                elif ch_data["type"] == "voice":
                    await guild.create_voice_channel(name=ch_data["name"], category=category,
                        reason=f"HunterX Backup Restore [{backup_id}]")
                    created_chs += 1
            except:
                pass
        else:
            existing_ch = discord.utils.get(guild.text_channels, name=ch_data["name"])
            if existing_ch:
                restored_channels[ch_data["name"]] = existing_ch

    saved_messages = backup.get("messages", {})
    for ch_name, msgs in saved_messages.items():
        target_ch = restored_channels.get(ch_name)
        if not target_ch:
            continue
        for msg_data in msgs:
            try:
                embed = discord.Embed(
                    description=msg_data.get("content", ""),
                    color=0x2F3136,
                    timestamp=datetime.now(PH_TIME)
                )
                embed.set_author(name=msg_data["author_name"], icon_url=msg_data.get("author_avatar", ""))
                embed.set_footer(text=f"Restored • {msg_data.get('timestamp', '')}")
                await target_ch.send(embed=embed)
                restored_msgs += 1
                await asyncio.sleep(0.5)
            except:
                pass

    await send_embed(ctx, "Backup Restored",
        f"Restore from `{backup_id}` complete!\n\n"
        f"*Roles created:* {created_roles}\n"
        f"*Categories created:* {created_cats}\n"
        f"*Channels created:* {created_chs}\n"
        f"*Messages restored:* {restored_msgs}")
    try:
        await ctx.message.delete()
    except:
        pass

# ==================== SET WELCOME ====================
@bot.hybrid_command()
@commands.has_permissions(administrator=True)
async def setwelcome(ctx):
    gid = str(ctx.guild.id)
    config_data.setdefault(gid, {})

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    async def ask(question):
        embed = discord.Embed(description=question, color=0xFFFFFF)
        embed.set_footer(text="HunterX • Mention a channel or type 'skip' — timeout: 60s")
        await ctx.send(embed=embed)
        try:
            msg = await bot.wait_for("message", check=check, timeout=60)
            return msg.content
        except asyncio.TimeoutError:
            return None

    await send_embed(ctx, "Welcome Setup", "I will ask you for up to **2 channels** to link in the welcome message.\nType 'skip' to skip any.")

    channels_set = []
    for i in range(1, 3):
        ans = await ask(f"Mention Channel {i} to add as a link in the welcome message:")
        if ans is None:
            return await send_embed(ctx, "<:HunterX:1512787796635422934> Timed Out", "Setup Cancelled.")
        if ans.lower() == "skip":
            continue
        match = re.search(r"<#(\d+)>", ans)
        if match:
            ch = ctx.guild.get_channel(int(match.group(1)))
            if ch:
                channels_set.append(ch.id)

    config_data[gid]["welcome_channels"] = channels_set
    save_config()

    ch_mentions = " ".join([f"<#{cid}>" for cid in channels_set]) or "None"
    await send_embed(ctx, "<:HunteXCheck:1518422536558481448> Welcome Setup Complete",
        f"Channels linked: {ch_mentions}\n\nNow set the welcome channel: `$welcome #channel`\nSet custom message: `$setmessage <your message>`\nTest it: `$welcome test`")

# ==================== SET MESSAGE ====================
@bot.hybrid_command(with_app_command=False, )
@commands.has_permissions(administrator=True)
async def setmessage(ctx, *, message: str):
    gid = str(ctx.guild.id)
    config_data.setdefault(gid, {})["welcome_message"] = message
    save_config()
    embed = make_embed("<:HunteXCheck:1518422536558481448> Welcome Message Set", f"Custom message saved:\n\n{message}")
    embed.set_footer(text="HunterX • Use {user} for mention, {server} for server name, {count} for member number")
    await ctx.send(embed=embed)

# ==================== WELCOME ====================
@bot.hybrid_command()
@commands.has_permissions(administrator=True)
async def welcome(ctx, arg=None):
    gid = str(ctx.guild.id)
    config_data.setdefault(gid, {})

    if arg and arg.lower() == "test":
        welcome_ch_id = config_data.get(gid, {}).get("welcome_channel")
        if not welcome_ch_id:
            return await send_embed(ctx, "<:HunterX:1512787796635422934> Not Set", "Set a welcome channel first with `$welcome #channel`")
        welcome_ch = ctx.guild.get_channel(welcome_ch_id)
        if not welcome_ch:
            return await send_embed(ctx, "<:HunterX:1512787796635422934> Channel Not Found", "Welcome channel not found.")
        await send_welcome_embed(ctx.guild, ctx.author, welcome_ch)
        await send_embed(ctx, "<:HunteXCheck:1518422536558481448> Test Sent", f"Test welcome sent to {welcome_ch.mention}")
        return

    if ctx.message.channel_mentions:
        ch = ctx.message.channel_mentions[0]
        config_data[gid]["welcome_channel"] = ch.id
        save_config()
        await send_embed(ctx, "<:HunteXCheck:1518422536558481448> Welcome Channel Set", f"Welcome messages will be sent to {ch.mention}")
    else:
        await send_embed(ctx, "<:HunterX:1512787796635422934> Invalid", "Usage: `$welcome #channel` or `$welcome test`")

# ==================== SEND WELCOME EMBED (GREEN + Channel Mentions) ====================
async def send_welcome_embed(guild, member, channel):
    gid = str(guild.id)
    cfg = config_data.get(gid, {})
    # Support both old and new key names
    linked_channel_ids = cfg.get("welcome_channels", cfg.get("WELCOME_CHANNELS <:catwave:1515279541147406416>", []))
    custom_message = cfg.get("welcome_message", "")

    desc = f"**WELCOME {member.mention} TO {guild.name}** <a:HappyHunterXemoji:1512831297582661803>\n\n"

    # Use proper Discord channel mentions (<#id>) so they are clickable
    for cid in linked_channel_ids:
        ch = guild.get_channel(cid)
        if ch:
            desc += f"• {ch.mention}\n"

    if custom_message:
        formatted = custom_message.replace("{user}", member.mention).replace("{server}", guild.name).replace("{count}", str(guild.member_count))
        desc += f"\n{formatted}"

    # GREEN embed color
    embed = discord.Embed(description=desc, timestamp=datetime.now(PH_TIME), color=0x57F287)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text=f"Member #{guild.member_count}")
    await channel.send(content=member.mention, embed=embed)

# ==================== BOOST CHANNEL SETUP ====================
@bot.hybrid_command()
@commands.has_permissions(administrator=True)
async def boostchannel(ctx, action: str = "setup"):
    if action.lower() != "setup":
        return await send_embed(ctx, "Usage", "`$boostchannel setup`")
    guild = ctx.guild
    gid = str(guild.id)

    booster_role = discord.utils.get(guild.roles, name="Booster")
    if not booster_role:
        try:
            booster_role = await guild.create_role(
                name="Booster",
                color=discord.Color.from_rgb(255, 105, 180),
                hoist=True,
                reason="HunterX Boost Setup"
            )
        except Exception as e:
            return await send_embed(ctx, "<:HunterX:1512787796635422934> Error", f"Could not create Booster role: {e}")

    existing = discord.utils.get(guild.text_channels, name="rich")
    if existing:
        config_data.setdefault(gid, {})["boost_channel"] = existing.id
        config_data[gid]["boost_role"] = booster_role.id
        save_config()
        return await send_embed(ctx, "<:HunteXCheck:1518422536558481448> Already Setup",
            f"Boost channel {existing.mention} and {booster_role.mention} role are ready.")

    try:
        boost_ch = await guild.create_text_channel(name="rich", reason="HunterX Boost Channel Setup")
        config_data.setdefault(gid, {})["boost_channel"] = boost_ch.id
        config_data[gid]["boost_role"] = booster_role.id
        save_config()
        await send_embed(ctx, "<:HunteXCheck:1518422536558481448> Boost Setup Complete",
            f"**Channel:** {boost_ch.mention}\n"
            f"**Role:** {booster_role.mention}\n\n"
            f"Set custom boost message with `$boostmessage <msg>`")
    except Exception as e:
        await send_embed(ctx, "<:HunterX:1512787796635422934> Error", str(e))

# ==================== BOOST MESSAGE ====================
@bot.hybrid_command(with_app_command=False, )
@commands.has_permissions(administrator=True)
async def boostmessage(ctx, *, message: str):
    gid = str(ctx.guild.id)
    config_data.setdefault(gid, {})["boost_message"] = message
    save_config()
    await send_embed(ctx, "<:HunteXCheck:1518422536558481448> Boost Message Set",
        f"Custom boost message saved:\n\n{message}\n\n-# Use {{user}} for the booster mention.")

# ==================== SERVER INFO ====================
@bot.hybrid_command()
async def serverinfo(ctx):
    guild = ctx.guild
    humans = len([m for m in guild.members if not m.bot])
    bots_count = len([m for m in guild.members if m.bot])
    boost_level = guild.premium_tier
    boost_count = guild.premium_subscription_count or 0
    created = guild.created_at.strftime("%B %d, %Y")
    emojis = guild.emojis
    emoji_str = " ".join(str(e) for e in emojis[:30]) if emojis else "None"
    if len(emojis) > 30:
        emoji_str += f" ...+{len(emojis) - 30} more"

    embed = discord.Embed(color=0xFFFFFF)
    embed.set_author(name=guild.name, icon_url=guild.icon.url if guild.icon else None)
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)

    embed.add_field(name="Server Owner", value=str(guild.owner), inline=True)
    embed.add_field(name="ID", value=str(guild.owner.id), inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=True)
    embed.add_field(name="Members", value=str(guild.member_count), inline=True)
    embed.add_field(name="Channels", value=str(len(guild.channels)), inline=True)
    embed.add_field(name="Roles", value=str(len(guild.roles)), inline=True)
    embed.add_field(name="Bot", value=str(bots_count), inline=True)
    embed.add_field(name="Human", value=str(humans), inline=True)
    embed.add_field(name="Server Boost", value=f"{boost_count} Boosts (Level {boost_level})", inline=True)
    embed.add_field(name="Server Created", value=created, inline=True)
    embed.add_field(name=f"Emoji List ({len(emojis)})", value=emoji_str, inline=False)
    embed.set_footer(text="HunterX")
    embed.timestamp = datetime.now(PH_TIME)
    await ctx.send(embed=embed)

# ==================== SERVERLIST ====================
@bot.hybrid_command()
async def serverlist(ctx):
    guilds = list(bot.guilds)
    total = len(guilds)
    embed = build_serverlist_embed(1)

    # Show buttons only if more than 6 servers
    if total > 6:
        view = ServerListView(page=1)
        await ctx.send(embed=embed, view=view)
    else:
        await ctx.send(embed=embed)


# ==================== BOT STATS ====================
@bot.hybrid_command()
async def botstats(ctx):
    """Show bot uptime, ping, and server count."""
    now = datetime.now(PH_TIME)
    delta = now - bot_start_time
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime_str = f"`{days}d {hours}h {minutes}m {seconds}s`"

    ping_ms = round(bot.latency * 1000)
    server_count = len(bot.guilds)
    user_count = sum(g.member_count or 0 for g in bot.guilds)

    embed = make_embed(
        "<:249630gradientgear:1512782705522245712> Bot Status",
        f"**Uptime:** {uptime_str}\n"
        f"**Ping:** `{ping_ms}ms`\n"
        f"**Servers:** `{server_count}`\n"
        f"**Total Users:** `{user_count:,}`"
    )
    if bot.user:
        embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.set_footer(text="HunterX")
    await ctx.send(embed=embed)

# ==================== BOT INFO ====================
@bot.hybrid_command(aliases=["bi", "info"])
async def botinfo(ctx):
    """Show detailed bot information."""
    now = datetime.now(PH_TIME)
    delta = now - bot_start_time
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime_str = f"{days}d {hours}h {minutes}m {seconds}s"

    ping_ms = round(bot.latency * 1000)
    server_count = len(bot.guilds)
    user_count = sum(g.member_count or 0 for g in bot.guilds)
    command_count = len(bot.commands)

    mem_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    mem_mb = mem_kb / 1024

    embed = discord.Embed(title="HunterX / Bot Info", color=0xFFFFFF)
    embed.add_field(name="Version", value=f"`{BOT_VERSION}`", inline=True)
    embed.add_field(name="Uptime", value=f"`{uptime_str}`", inline=True)
    embed.add_field(name="Memory", value=f"`{mem_mb:.2f} MB`", inline=True)
    embed.add_field(name="Ping", value=f"`{ping_ms}ms`", inline=True)
    embed.add_field(name="Guilds", value=f"`{server_count}`", inline=True)
    embed.add_field(name="Users", value=f"`{user_count:,}`", inline=True)
    embed.add_field(name="Commands", value=f"`{command_count}`", inline=True)
    embed.add_field(name="Website", value="[hunterx2.netlify.app](https://hunterx2.netlify.app)", inline=True)
    embed.add_field(name="Server Support", value="[HunterX Support](https://discord.gg/k8jj7HCc9)", inline=True)
    embed.add_field(name="Invite", value="[Add HunterX](https://discord.com/oauth2/authorize?client_id=1480996341894217901)", inline=True)
    embed.timestamp = datetime.now(PH_TIME)
    if bot.user:
        embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.set_footer(text="HunterX")
    await ctx.send(embed=embed)

# ==================== FUN / UTILITY ACTIONS ====================
async def fun_action(ctx, target: discord.Member, action: str, past: str):
    gif_url = await fetch_gif(action)
    desc = f"{ctx.author.mention} *{past}* {target.mention}"
    embed = discord.Embed(description=desc, color=0xFFFFFF)
    embed.set_footer(text="HunterX")
    if gif_url:
        embed.set_image(url=gif_url)
    await ctx.send(embed=embed)

@bot.hybrid_command()
async def kiss(ctx, member: discord.Member):
    await fun_action(ctx, member, "kiss", "kissed")

@bot.hybrid_command()
async def hug(ctx, member: discord.Member):
    await fun_action(ctx, member, "hug", "hugged")

@bot.hybrid_command()
async def cuddle(ctx, member: discord.Member):
    await fun_action(ctx, member, "cuddle", "cuddled")

@bot.hybrid_command()
async def slap(ctx, member: discord.Member):
    await fun_action(ctx, member, "slap", "slapped")

@bot.hybrid_command()
async def punch(ctx, member: discord.Member):
    await fun_action(ctx, member, "punch", "punched")

@bot.hybrid_command()
async def throw(ctx, member: discord.Member):
    gif_url = await fetch_gif("throw") or await fetch_gif("kick")
    desc = f"{ctx.author.mention} *threw* {member.mention}"
    embed = discord.Embed(description=desc, color=0xFFFFFF)
    embed.set_footer(text="HunterX")
    if gif_url:
        embed.set_image(url=gif_url)
    await ctx.send(embed=embed)

@bot.hybrid_command()
async def boxing(ctx, member: discord.Member):
    gif_url = await fetch_gif("punch")
    desc = f"{ctx.author.mention} *is boxing* {member.mention}"
    embed = discord.Embed(description=desc, color=0xFFFFFF)
    embed.set_footer(text="HunterX")
    if gif_url:
        embed.set_image(url=gif_url)
    await ctx.send(embed=embed)

# ==================== TIKTOK ====================
@bot.hybrid_command(with_app_command=False, )
async def tt(ctx, *, username: str):
    username = username.lstrip("@").strip().replace(" ", "")
    tt_link = f"https://www.tiktok.com/@{username}"
    followers = None
    avatar = None
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
        "Referer": "https://www.tiktok.com/",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://www.tiktok.com/api/user/detail/?uniqueId={username}&aid=1988&app_name=tiktok_web",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=8)
            ) as resp:
                data = await resp.json(content_type=None)
        user_info = data.get("userInfo", {})
        user = user_info.get("user", {})
        stats = user_info.get("stats", {})
        if user:
            followers = stats.get("followerCount")
            avatar = user.get("avatarMedium", "")
    except Exception:
        pass

    embed = discord.Embed(
        description=f"**<:TiktokHunterX:1512864012969316432> TikTok**\n**Account:** [@{username}]({tt_link})",
        color=0xFFFFFF
    )
    if avatar:
        embed.set_thumbnail(url=avatar)
    if followers is not None:
        embed.add_field(name="Followers", value=_fmt_num(followers), inline=True)
    embed.set_footer(text="HunterX")
    await ctx.send(embed=embed)

# ==================== INSTAGRAM ====================
@bot.hybrid_command(with_app_command=False, )
async def ig(ctx, *, username: str):
    username = username.lstrip("@").strip().replace(" ", "")
    ig_link = f"https://www.instagram.com/{username}/"
    followers = None
    avatar = None
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "X-IG-App-ID": "936619743392459",
        "Accept": "*/*",
        "Referer": "https://www.instagram.com/",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=8)
            ) as resp:
                data = await resp.json(content_type=None)
        user = data.get("data", {}).get("user", {})
        if user:
            followers = user.get("edge_followed_by", {}).get("count")
            avatar = user.get("profile_pic_url_hd") or user.get("profile_pic_url", "")
    except Exception:
        pass

    embed = discord.Embed(
        description=f"**<:HunterXig:1515267890113413230> INSTAGRAM**\n**Account:** [@{username}]({ig_link})",
        color=0xFFFFFF
    )
    if avatar:
        embed.set_thumbnail(url=avatar)
    if followers is not None:
        embed.add_field(name="Followers", value=_fmt_num(followers), inline=True)
    embed.set_footer(text="HunterX")
    await ctx.send(embed=embed)

# ==================== YOUTUBE ====================
@bot.hybrid_command(with_app_command=False, )
async def yt(ctx, *, query: str):
    await ctx.typing()
    loop = asyncio.get_event_loop()

    def _get_channel_info():
        flat_opts = {"quiet": True, "no_warnings": True, "extract_flat": True}
        with yt_dlp.YoutubeDL(flat_opts) as ydl:
            result = ydl.extract_info(f"ytsearch1:{query}", download=False)
            if not result or not result.get("entries"):
                return None
            entry = result["entries"][0]
            channel_name = entry.get("channel") or entry.get("uploader", "")
            channel_id = entry.get("channel_id", "")
            channel_url = entry.get("channel_url") or entry.get("uploader_url") or (
                f"https://www.youtube.com/channel/{channel_id}" if channel_id else ""
            )
        if not channel_url:
            return None
        chan_opts = {"quiet": True, "no_warnings": True, "extract_flat": True, "playlist_items": "0"}
        try:
            with yt_dlp.YoutubeDL(chan_opts) as ydl:
                info = ydl.extract_info(channel_url, download=False)
                subs = info.get("channel_follower_count") or info.get("subscriber_count")
                videos = info.get("playlist_count") or info.get("video_count")
                avatar = info.get("thumbnails", [{}])[-1].get("url", "") if info.get("thumbnails") else ""
                bio = (info.get("description") or "").strip()
        except Exception:
            subs = None; videos = None; avatar = ""; bio = ""
        return {"channel": channel_name, "channel_url": channel_url, "subscribers": subs, "videos": videos, "avatar": avatar, "bio": bio}

    try:
        data = await loop.run_in_executor(None, _get_channel_info)
        if not data or not data["channel"]:
            return await send_embed(ctx, "<:HunterX:1512787796635422934> Not Found", f"No YouTube channel found for `{query}`.")
        embed = discord.Embed(
            description=f"**<:hunterXyoutube:1512864016588865787> YouTube**\n> [{data['channel']}]({data['channel_url']})",
            color=0xFFFFFF
        )
        if data["avatar"]:
            embed.set_thumbnail(url=data["avatar"])
        embed.add_field(name="Subscribers", value=_fmt_num(data["subscribers"]), inline=True)
        embed.add_field(name="Videos", value=_fmt_num(data["videos"]), inline=True)
        if data.get("bio"):
            embed.add_field(name="Bio", value=data["bio"][:300], inline=False)
        embed.set_footer(text="HunterX")
        await ctx.send(embed=embed)
    except Exception as e:
        await send_embed(ctx, "<:HunterX:1512787796635422934> Error", str(e))

# ==================== AFK ====================
@bot.hybrid_command(with_app_command=False, aliases=["a"])
async def afk(ctx, *, reason="No reason"):
    afk_users[ctx.author.id] = {"reason": reason, "time": datetime.now(PH_TIME)}
    embed = make_embed("<a:kuromihelp:1512786350170963989> AFK", f"{ctx.author.mention} is now AFK\n\nReason: {reason}")
    embed.set_footer(text="HunterX")
    await ctx.send(embed=embed)

# ==================== ROLE ====================
@bot.hybrid_command()
@commands.has_permissions(manage_roles=True)
async def role(ctx, member: discord.Member, role: discord.Role):
    if role in member.roles:
        return await send_embed(ctx, "<:HunterX:1512787796635422934> Error", "Member already has role.")
    try:
        await member.add_roles(role)
        await send_embed(ctx, "<:HunteXCheck:1518422536558481448> Role Added", f"Gave {role.mention} to {member.mention}")
    except Exception as e:
        await send_embed(ctx, "<:HunterX:1512787796635422934> Error", f"{e}")

# ==================== REMOVE ROLE ====================
@bot.hybrid_command()
@commands.has_permissions(manage_roles=True)
async def drole(ctx, member: discord.Member, role: discord.Role):
    if role not in member.roles:
        return await send_embed(ctx, "<:HunterX:1512787796635422934> Error", "Member does not have role.")
    try:
        await member.remove_roles(role)
        await send_embed(ctx, "<:HunterXsadkitty:1514606490063868074> Role Removed", f"Removed {role.mention} from {member.mention}")
    except Exception as e:
        await send_embed(ctx, "<:HunterX:1512787796635422934> Error", f"{e}")

# ==================== BAN ====================
@bot.hybrid_command(with_app_command=False, )
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason="No reason"):
    try:
        avatar = member.display_avatar.url
        await member.ban(reason=reason)
        embed = make_embed(
            "Banned",
            f"**User:** {member.mention}\n"
            f"**UserID:** `{member.id}`\n"
            f"**Moderator:** {ctx.author.mention}\n"
            f"**Reason:** {reason}"
        )
        embed.set_thumbnail(url=avatar)
        embed.set_footer(text="HunterX")
        await ctx.send(embed=embed)
        await log_action(ctx.guild, "Banned",
            f"**User:** {member} ({member.id})\n**Moderator:** {ctx.author} (`{ctx.author.id}`)\n**Reason:** {reason}", avatar)
        await log_mod_action(ctx.guild, "Banned",
            f"**User:** {member} (`{member.id}`)\n**Moderator:** {ctx.author} (`{ctx.author.id}`)\n**Reason:** {reason}", avatar)
    except Exception as e:
        await send_embed(ctx, "<:HunterX:1512787796635422934> Error", str(e))

# ==================== UNBAN ====================
@bot.hybrid_command()
@commands.has_permissions(ban_members=True)
async def unban(ctx, user_id: str):
    # ── UNBAN ALL ─────────────────────────────────────────────────────────
    if user_id.lower() == "all":
        bans = [entry async for entry in ctx.guild.bans()]
        if not bans:
            return await send_embed(ctx, "<:HunteXCheck:1518422536558481448> No Bans", "There are no banned users in this server.")
        progress_embed = make_embed(
            "<a:kuromihelp:1512786350170963989> Unbanning All...",
            f"Processing **{len(bans)}** banned users. Please wait..."
        )
        progress_embed.set_footer(text="HunterX")
        msg = await ctx.send(embed=progress_embed)
        success = 0
        failed = 0
        for entry in bans:
            try:
                await ctx.guild.unban(entry.user, reason=f"Mass Unban by {ctx.author}")
                success += 1
                await asyncio.sleep(0.5)
            except:
                failed += 1
        result_embed = make_embed(
            "<:HunteXCheck:1518422536558481448> Unban All Complete",
            f"**Unbanned:** `{success}` users\n**Failed:** `{failed}` users\n**Moderator:** {ctx.author.mention}"
        )
        result_embed.set_footer(text="HunterX")
        await msg.edit(embed=result_embed)
        await log_action(ctx.guild, "<:HunteXCheck:1518422536558481448> Mass Unban",
            f"**Moderator:** {ctx.author} (`{ctx.author.id}`)\n**Unbanned:** {success} users\n**Failed:** {failed}")
        await log_mod_action(ctx.guild, "<:HunteXCheck:1518422536558481448> Mass Unban",
            f"**Moderator:** {ctx.author} (`{ctx.author.id}`)\n**Unbanned:** {success} users\n**Failed:** {failed}")
        return
    # ── UNBAN SINGLE USER ─────────────────────────────────────────────────
    try:
        uid = int(user_id)
    except ValueError:
        return await send_embed(ctx, "<:HunterX:1512787796635422934> Invalid",
            "Usage: `$unban <user_id>` or `$unban all`")
    try:
        user = await bot.fetch_user(uid)
        await ctx.guild.unban(user)
        embed = make_embed(
            "<:HunteXCheck:1518422536558481448> Unbanned",
            f"**User:** {user.mention}\n"
            f"**UserID:** `{user.id}`\n"
            f"**Moderator:** {ctx.author.mention}"
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_footer(text="HunterX")
        await ctx.send(embed=embed)
        await log_action(ctx.guild, "Unbanned",
            f"**User:** {user} (`{user.id}`)\n**Moderator:** {ctx.author} (`{ctx.author.id}`)")
        await log_mod_action(ctx.guild, "<:HunteXCheck:1518422536558481448> Unbanned",
            f"**User:** {user} (`{user.id}`)\n**Moderator:** {ctx.author} (`{ctx.author.id}`)", user.display_avatar.url)
    except Exception as e:
        await send_embed(ctx, "<:HunterX:1512787796635422934> Error", str(e))

# ==================== BAN LIST ====================
@bot.hybrid_command()
@commands.has_permissions(ban_members=True)
async def banlist(ctx):
    bans = [entry async for entry in ctx.guild.bans()]
    if not bans:
        return await send_embed(ctx, "<:249630gradientgear:1512782705522245712> Ban List", "No banned users.")
    description = ""
    for i, entry in enumerate(bans, start=1):
        description += f"**{i}.** {entry.user} (`{entry.user.id}`)\n"
    embed = make_embed("<:249630gradientgear:1512782705522245712> Ban List", description)
    embed.set_footer(text="HunterX")
    await ctx.send(embed=embed)

# ==================== KICK ====================
@bot.hybrid_command(with_app_command=False, )
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason="No reason"):
    try:
        avatar = member.display_avatar.url
        await member.kick(reason=reason)
        embed = make_embed(
            "<:HunteXCheck:1518422536558481448> Kicked",
            f"**User:** {member.mention}\n"
            f"**UserID:** `{member.id}`\n"
            f"**Moderator:** {ctx.author.mention}\n"
            f"**Reason:** {reason}"
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text="HunterX")
        await ctx.send(embed=embed)
        await log_action(ctx.guild, "__Kicked__",
            f"**User:** {member} ({member.id})\n**Moderator:** {ctx.author} (`{ctx.author.id}`)\n**Reason:** {reason}", avatar)
        await log_mod_action(ctx.guild, "<:HunteXCheck:1518422536558481448> Member Kicked",
            f"**User:** {member} (`{member.id}`)\n**Moderator:** {ctx.author} (`{ctx.author.id}`)\n**Reason:** {reason}", avatar)
    except Exception as e:
        await send_embed(ctx, "<:HunterX:1512787796635422934> Error", str(e))

# ==================== PARSE TIME ====================
def parse_time(time_string):
    time_string = time_string.lower()
    units = {"s": 1, "sec": 1, "second": 1, "seconds": 1, "m": 60, "min": 60, "minute": 60, "minutes": 60,
             "h": 3600, "hr": 3600, "hour": 3600, "hours": 3600, "d": 86400, "day": 86400, "days": 86400,
             "w": 604800, "week": 604800, "weeks": 604800}
    total_seconds = 0
    matches = re.findall(r"(\d+)([a-zA-Z]+)", time_string)
    for amount, unit in matches:
        if unit in units:
            total_seconds += int(amount) * units[unit]
    return total_seconds

# ==================== TIMEOUT ====================
@bot.hybrid_command(with_app_command=False, )
@commands.has_permissions(moderate_members=True)
async def timeout(ctx, member: discord.Member, duration: str, *, reason="No reason"):
    try:
        seconds = parse_time(duration)
        if seconds <= 0:
            return await send_embed(ctx, "<:HunterX:1512787796635422934> Invalid Time", "Example: `1h` / `30m` / `1day` / `2weeks`")
        until = discord.utils.utcnow() + timedelta(seconds=seconds)
        await member.edit(timed_out_until=until, reason=reason)
        embed = make_embed(
            "<:HunteXCheck:1518422536558481448> Timeout",
            f"**User:** {member.mention}\n"
            f"**UserID:** `{member.id}`\n"
            f"**Moderator:** {ctx.author.mention}\n"
            f"**Duration:** `{duration}`\n"
            f"**Reason:** {reason}"
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text="HunterX")
        await ctx.send(embed=embed)
        await log_action(ctx.guild, "<:HunterXTimeout:1513168503232790668> Time Out",
            f"**User:** {member} ({member.id})\n**Moderator:** {ctx.author} (`{ctx.author.id}`)\n**Duration:** {duration}\n**Reason:** {reason}",
            member.display_avatar.url)
        await log_mod_action(ctx.guild, "<:SecureXTimeout:1513168503232790668> Timed Out",
            f"**User:** {member} (`{member.id}`)\n**Moderator:** {ctx.author} (`{ctx.author.id}`)\n**Duration:** {duration}\n**Reason:** {reason}",
            member.display_avatar.url)
    except Exception as e:
        await send_embed(ctx, "<:HunterX:1512787796635422934> Error", str(e))

# ==================== REMOVE TIMEOUT ====================
@bot.hybrid_command()
@commands.has_permissions(moderate_members=True)
async def rtimeout(ctx, member: discord.Member):
    try:
        await member.edit(timed_out_until=None)
        embed = make_embed(
            "<:HunteXCheck:1518422536558481448> Timeout Removed",
            f"**User:** {member.mention}\n"
            f"**UserID:** `{member.id}`\n"
            f"**Moderator:** {ctx.author.mention}"
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text="HunterX")
        await ctx.send(embed=embed)
    except Exception as e:
        await send_embed(ctx, "<:HunterX:1512787796635422934> Error", str(e))

# ==================== MESSAGE HANDLER ====================
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Bot mention → show prefix info
    if message.guild and bot.user in message.mentions:
        content_clean = message.content.replace(f"<@{bot.user.id}>", "").replace(f"<@!{bot.user.id}>", "").strip()
        if not content_clean:
            gid_m = str(message.guild.id)
            prefix = config_data.get(gid_m, {}).get("prefix", "$")
            embed = discord.Embed(
                description=f"**HunterX**\n\nHi {message.author.mention}, my prefix is `{prefix}`\nType `{prefix}help` to see commands.",
                color=0xFFFFFF
            )
            embed.set_thumbnail(url=bot.user.display_avatar.url)
            embed.set_footer(text="HunterX")
            view = InviteView().build()
            await message.channel.send(embed=embed, view=view)
            return

    gid = str(message.guild.id) if message.guild else None

    if gid:
        cfg = config_data.get(gid, {})

        # Anti link
        if cfg.get("antilink", False) and message.guild:
            if re.search(r"(discord\.gg|discord\.com/invite)/\S+", message.content):
                allowed_users = cfg.get("allowed_link_users", [])
                allowed_roles = cfg.get("allowed_link_roles", [])
                legacy_role = cfg.get("allowed_link_role")
                if legacy_role:
                    allowed_roles = allowed_roles + [legacy_role]
                user_role_ids = [r.id for r in message.author.roles]
                has_allowed = (
                    message.author.id in allowed_users
                    or any(rid in user_role_ids for rid in allowed_roles)
                )
                if (not is_whitelisted(message.guild, message.author)
                        and not message.author.guild_permissions.administrator
                        and not has_allowed
                        and message.author.id != message.guild.owner_id):
                    try:
                        await message.delete()
                        await log_action(message.guild, "<:HunteXCheck:1518422536558481448> Link Deleted",
                            f"**User:** {message.author} ({message.author.id})\n**Channel:** {message.channel.mention}")
                    except:
                        pass
                    return

        # Anti Spam
        if cfg.get("antispam", False) and message.guild:
            if (not is_whitelisted(message.guild, message.author)
                    and not message.author.guild_permissions.administrator
                    and message.author.id != message.guild.owner_id):
                key = (message.guild.id, message.author.id)
                now = discord.utils.utcnow().timestamp()
                spam_tracker[key] = [t for t in spam_tracker[key] if now - t < 5]
                spam_tracker[key].append(now)
                if len(spam_tracker[key]) >= 10:
                    spam_tracker[key] = []
                    try:
                        until = discord.utils.utcnow() + timedelta(minutes=5)
                        await message.author.edit(timed_out_until=until, reason="HunterX Anti Spam")
                        await log_action(message.guild, "<:HunteXCheck:1518422536558481448> Anti Spam Timeout",
                            f"**User:** {message.author} ({message.author.id}) timed out 5min for spam.")
                    except:
                        pass
                    return

        # AFK check
        if message.guild:
            if message.author.id in afk_users:
                del afk_users[message.author.id]
                try:
                    await message.channel.send(
                        embed=discord.Embed(
                            description=f"Welcome back {message.author.mention}! AFK removed.",
                            color=0xFFFFFF
                        ).set_footer(text="HunterX"),
                        delete_after=5
                    )
                except:
                    pass
            for mentioned in message.mentions:
                if mentioned.id in afk_users:
                    data = afk_users[mentioned.id]
                    reason = data.get("reason", "No reason")
                    try:
                        await message.channel.send(
                            embed=discord.Embed(
                                description=f"{mentioned.mention} is currently AFK\nReason: {reason}",
                                color=0xFFFFFF
                            ).set_footer(text="HunterX"),
                            delete_after=8
                        )
                    except:
                        pass

        # Auto respond
        if gid and message.guild:
            triggers = autorespond_data.get(gid, {})
            lower_content = message.content.lower()
            for trigger, reply in triggers.items():
                if trigger in lower_content:
                    try:
                        await message.channel.send(reply)
                    except:
                        pass
                    break

        # Sticky message resend
        if message.guild:
            channel_id = message.channel.id
            if channel_id in sticky_messages:
                old = sticky_messages[channel_id]
                try:
                    old_msg = await message.channel.fetch_message(old["msg_id"])
                    await old_msg.delete()
                except:
                    pass
                sent = await message.channel.send(f"{old['text']}")
                sticky_messages[channel_id] = {"text": old["text"], "msg_id": sent.id}

    await bot.process_commands(message)

# ==================== MESSAGE EDIT LOG ====================
@bot.event
async def on_message_edit(before, after):
    if before.author.bot:
        return
    if before.content == after.content:
        return
    if not before.guild:
        return
    gid = str(before.guild.id)
    ch_id = config_data.get(gid, {}).get("editmsg_channel")
    if not ch_id:
        return
    log_ch = before.guild.get_channel(ch_id)
    if not log_ch:
        return
    try:
        embed = make_log_embed("Message Edited")
        embed.set_author(name=f"{before.author} | {before.author.id}", icon_url=before.author.display_avatar.url)
        embed.add_field(name="Channel", value=before.channel.mention, inline=True)
        embed.add_field(name="Before", value=before.content[:1024] if before.content else "[No text]", inline=False)
        embed.add_field(name="After", value=after.content[:1024] if after.content else "[No text]", inline=False)
        embed.set_footer(text="HunterX")
        embed.timestamp = datetime.now(PH_TIME)
        await log_ch.send(embed=embed)
    except:
        pass

# ==================== MESSAGE DELETE (Snipe + Delete Log) ====================
@bot.event
async def on_message_delete(message):
    if message.author.bot:
        return

    # Store for $snipe
    if message.content:
        snipe_data[message.channel.id] = {
            "content": message.content,
            "author": str(message.author),
            "author_icon": str(message.author.display_avatar.url),
            "time": datetime.now(PH_TIME),
        }

    # Delete message log
    if not message.guild:
        return
    gid = str(message.guild.id)
    ch_id = config_data.get(gid, {}).get("deletemsg_channel")
    if not ch_id:
        return
    log_ch = message.guild.get_channel(ch_id)
    if not log_ch:
        return
    try:
        embed = make_log_embed("Message Deleted")
        embed.set_author(name=f"{message.author} | {message.author.id}", icon_url=message.author.display_avatar.url)
        embed.add_field(name="Channel", value=message.channel.mention, inline=True)
        embed.add_field(name="Content", value=message.content[:1024] if message.content else "[No text content]", inline=False)
        embed.set_footer(text="HunterX")
        embed.timestamp = datetime.now(PH_TIME)
        await log_ch.send(embed=embed)
    except:
        pass

# ==================== WELCOME EVENT ====================
@bot.event
async def on_member_join(member):
    if member.bot:
        await _check_bot_add(member)
        return
    guild = member.guild
    gid = str(guild.id)
    cfg = config_data.get(gid, {})

    autorole_id = cfg.get("autorole")
    if autorole_id:
        autorole = guild.get_role(autorole_id)
        if autorole:
            try:
                await member.add_roles(autorole, reason="HunterX Auto Role")
            except:
                pass

    welcome_ch_id = cfg.get("welcome_channel")
    if welcome_ch_id:
        channel = guild.get_channel(welcome_ch_id)
        if channel:
            await send_welcome_embed(guild, member, channel)

# ==================== BOOST EVENT ====================
@bot.event
async def on_member_update(before, after):
    guild = after.guild
    gid = str(guild.id)
    cfg = config_data.get(gid, {})

    if before.premium_since is None and after.premium_since is not None:
        boost_role_id = cfg.get("boost_role")
        if boost_role_id:
            boost_role = guild.get_role(boost_role_id)
            if boost_role and boost_role not in after.roles:
                try:
                    await after.add_roles(boost_role, reason="HunterX Boost Auto Role")
                except:
                    pass

        boost_ch_id = cfg.get("boost_channel")
        if boost_ch_id:
            boost_ch = guild.get_channel(boost_ch_id)
            if boost_ch:
                boost_msg = cfg.get("boost_message", "")
                boost_role_id = cfg.get("boost_role")
                boost_role_mention = f"<@&{boost_role_id}>" if boost_role_id else "@Booster"
                embed = discord.Embed(color=0xFF69B4)
                embed.add_field(name="Booster", value=after.name, inline=True)
                embed.add_field(name="Role", value=boost_role_mention, inline=True)
                if boost_msg:
                    formatted = boost_msg.replace("{user}", after.mention)
                    embed.description = f"-# {formatted}"
                embed.set_thumbnail(url=after.display_avatar.url)
                embed.set_footer(text="HunterX")
                try:
                    await boost_ch.send(embed=embed)
                except:
                    pass

    if before.premium_since is not None and after.premium_since is None:
        boost_role_id = cfg.get("boost_role")
        if boost_role_id:
            boost_role = guild.get_role(boost_role_id)
            if boost_role and boost_role in after.roles:
                try:
                    await after.remove_roles(boost_role, reason="HunterX Boost Ended")
                except:
                    pass

# ==================== ANTI BOT ADD ====================
async def _check_bot_add(member):
    guild = member.guild
    gid = str(guild.id)
    if not config_data.get(gid, {}).get("antibotadd", False):
        return
    try:
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.bot_add):
            user = entry.user
            if is_guild_owner_or_bot(guild, user):
                return
            if is_higher_role_than_bot(guild, user):
                return
            if is_whitelisted(guild, user):
                return
            try:
                await member.ban(reason="HunterX Anti Bot Add")
            except:
                pass
            try:
                await guild.ban(user, reason="HunterX Anti Bot Add")
            except:
                pass
            await log_action(guild, "<:staff1:1512771763199545394> Unauthorized Bot Add",
                f"**Banned Adder:** {user} (`{user.id}`)\n**Banned Bot:** {member}",
                user.display_avatar.url)
            break
    except:
        pass

# ==================== ANTI ROLE CREATE ====================
@bot.event
async def on_guild_role_create(role):
    guild = role.guild
    gid = str(guild.id)
    cfg = config_data.get(gid, {})

    try:
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.role_create):
            user = entry.user

            if is_guild_owner_or_bot(guild, user):
                return
            if is_higher_role_than_bot(guild, user):
                return
            if is_whitelisted(guild, user):
                return

            if cfg.get("antinuke", False):
                try:
                    await role.delete()
                except:
                    pass
                try:
                    await guild.ban(user, reason="HunterX Anti Role Create")
                except:
                    pass
                await log_action(guild, "Unauthorized Role Create",
                    f"**Banned:** {user} (`{user.id}`)\n**Role:** {role.name}",
                    user.display_avatar.url)
                return

            if cfg.get("anticreateadminrole", False) and role.permissions.administrator:
                try:
                    await role.delete()
                except:
                    pass
                try:
                    await guild.ban(user, reason="HunterX Anti Create Admin Role")
                except:
                    pass
                await log_action(guild, "Unauthorized Admin Role Created",
                    f"**Banned:** {user} (`{user.id}`)\n**Role:** {role.name} (had Administrator perms)",
                    user.display_avatar.url)
            break
    except:
        pass

# ==================== ANTI ROLE DELETE ====================
@bot.event
async def on_guild_role_delete(role):
    guild = role.guild
    gid = str(guild.id)
    cfg = config_data.get(gid, {})
    if not is_antinuke_enabled(guild.id) and not cfg.get("antideleterole", False):
        return
    try:
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.role_delete):
            user = entry.user
            if is_guild_owner_or_bot(guild, user):
                return
            if is_higher_role_than_bot(guild, user):
                return
            if is_whitelisted(guild, user):
                return
            try:
                await guild.ban(user, reason="HunterX Anti Role Delete")
            except:
                pass
            await log_action(guild, "Unauthorized Role Delete",
                f"**Banned:** {user} (`{user.id}`)\n**Role:** {role.name}",
                user.display_avatar.url)
            break
    except:
        pass

# ==================== ANTI CHANNEL CREATE ====================
@bot.event
async def on_guild_channel_create(channel):
    guild = channel.guild
    gid = str(guild.id)
    cfg = config_data.get(gid, {})

    hunterx_channels = ("hunterx-logs", "hunterx-verify", "hunterx-support", "hunterx-ticketlogs",
                        "deletemessage-logs", "rich", "hunterx-dltmsglogs", "hunterx-editmsglogs", "hunterx-modlogs")
    if channel.name in hunterx_channels:
        return
    if channel.category and channel.category.name == "helpdesk":
        return

    if not cfg.get("antinuke", False) and not cfg.get("anticreatechannel", False):
        return

    try:
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_create):
            user = entry.user
            if is_guild_owner_or_bot(guild, user):
                return
            if is_higher_role_than_bot(guild, user):
                return
            if is_whitelisted(guild, user):
                return
            try:
                await channel.delete()
            except:
                pass
            try:
                await guild.ban(user, reason="HunterX Anti Channel Create")
            except:
                pass
            await log_action(guild, "Unauthorized Channel Create",
                f"**Banned:** {user} (`{user.id}`)\n**Channel:** {channel.name}",
                user.display_avatar.url)
            break
    except:
        pass

# ==================== ANTI CHANNEL DELETE ====================
@bot.event
async def on_guild_channel_delete(channel):
    guild = channel.guild
    gid = str(guild.id)
    cfg = config_data.get(gid, {})

    if not cfg.get("antinuke", False) and not cfg.get("antideletechannel", False):
        return

    try:
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
            user = entry.user
            if is_guild_owner_or_bot(guild, user):
                return
            if is_higher_role_than_bot(guild, user):
                return
            if is_whitelisted(guild, user):
                return
            try:
                await guild.ban(user, reason="HunterX Anti Channel Delete")
            except:
                pass
            await log_action(guild, "Unauthorized Channel Delete",
                f"**Banned:** {user} (`{user.id}`)\n**Channel:** {channel.name}",
                user.display_avatar.url)
            break
    except:
        pass

# ==================== ANTI MEMBER KICK ====================
@bot.event
async def on_member_remove(member):
    guild = member.guild
    gid = str(guild.id)
    if not config_data.get(gid, {}).get("antikick", False):
        return
    try:
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.kick):
            if entry.target.id != member.id:
                continue
            user = entry.user
            if is_guild_owner_or_bot(guild, user):
                return
            if is_higher_role_than_bot(guild, user):
                return
            if is_whitelisted(guild, user):
                return
            try:
                await guild.ban(user, reason="HunterX Anti Member Kick")
            except:
                pass
            await log_action(guild, "Unauthorized Member Kick",
                f"**Banned:** {user} (`{user.id}`)\n**Victim:** {member}",
                user.display_avatar.url)
            break
    except:
        pass

# ==================== ANTI BAN EVENT ====================
@bot.event
async def on_member_ban(guild, user):
    gid = str(guild.id)
    if not config_data.get(gid, {}).get("antiban", False):
        return
    try:
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):
            if entry.target.id != user.id:
                continue
            moderator = entry.user
            if is_guild_owner_or_bot(guild, moderator):
                return
            if is_higher_role_than_bot(guild, moderator):
                return
            if is_whitelisted(guild, moderator):
                return
            try:
                await guild.ban(moderator, reason="HunterX Anti Ban")
            except:
                pass
            await log_action(guild, "Unauthorized Member Ban",
                f"**Banned:** {moderator} ({moderator.id})\n**Victim:** {user}",
                moderator.display_avatar.url)
            break
    except:
        pass

# ==================== ANTI WEBHOOK CREATE ====================
@bot.event
async def on_webhooks_update(channel):
    guild = channel.guild
    gid = str(guild.id)
    if not config_data.get(gid, {}).get("antiwebhookcreate", False):
        return
    try:
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.webhook_create):
            user = entry.user
            if is_guild_owner_or_bot(guild, user):
                return
            if is_higher_role_than_bot(guild, user):
                return
            if is_whitelisted(guild, user):
                return
            try:
                webhook = entry.target
                if hasattr(webhook, "delete"):
                    await webhook.delete()
            except:
                pass
            try:
                await guild.ban(user, reason="HunterX Anti Webhook Create")
            except:
                pass
            await log_action(guild, "Unauthorized Webhook Created",
                f"**Banned:** {user} (`{user.id}`)\n**Channel:** {channel.mention}",
                user.display_avatar.url)
            break
    except:
        pass


# ==================== WEB SERVER (keep-alive) ====================
from aiohttp import web as aio_web

async def start_web_server():
    async def handle(request):
        return aio_web.Response(text="HunterX is online!")
    app = aio_web.Application()
    app.router.add_get("/", handle)
    runner = aio_web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = aio_web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

# ==================== RUN ====================
token = os.environ.get("DISCORD_TOKEN")
if not token:
    raise RuntimeError("DISCORD_TOKEN is not set. Please add it to your Render Environment Variables.")

async def main():
    await start_web_server()
    await bot.start(token)

asyncio.run(main())
