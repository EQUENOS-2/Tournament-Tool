import discord
from discord.ext import commands
from discord.ext.commands import Bot
import asyncio
import os
from pymongo import MongoClient
from datetime import datetime, timedelta, time

#----------------------------------------------+
#                Connections                   |
#----------------------------------------------+
db_token = str(os.environ.get("db_token"))
cluster = MongoClient(db_token)
db = cluster["tournament_tool_db"]

#----------------------------------------------+
#                  Variables                   |
#----------------------------------------------+
mass_dm_start_at = time(21)  # 00 UTC+3


placeholders = {
    "||{i}||": "https://discord.gg/",
    "||{h}||": "https://"
}
key_emoji = "🔎"


def is_guild_moderator():
    def predicate(ctx):
        server = Server(ctx.guild)
        author_role_ids = [r.id for r in ctx.author.roles]
        has = False
        for role_id in server.get_mod_roles():
            if role_id in author_role_ids:
                has = True
                break
        if has:
            return True
        else:
            raise IsNotModerator()
    return commands.check(predicate)


class IsNotModerator(commands.CheckFailure):
    pass


#----------------------------------------------+
#                 Functions                    |
#----------------------------------------------+
from functions import Server


def next_time(time, now=datetime.utcnow()):
    future = datetime(now.year, now.month, now.day, time.hour, time.minute, time.second)
    if future < now:
        future += timedelta(hours=24)
    return future


def dt_from_string(string: str):
    pair = string.split(maxsplit=1)
    if len(pair) < 2:
        return None
    else:
        ymd, hm = pair
        del pair
        ymd = ymd.split(".", maxsplit=2)
        hm = hm.split(":", maxsplit=1)
        if len(ymd) < 3 or len(hm) < 2:
            return None
        else:
            try:
                ymd = [int(el) for el in ymd]
                hm = [int(el) for el in hm]
                try:
                    return datetime(*ymd, *hm) - timedelta(hours=3)
                except Exception:
                    return None
            except Exception:
                return None


def process_text(server: discord.Guild, text: str, table: dict=None):
    """Returns: (Text, Role, UTC)"""
    if table is None:
        table = Server(server.id).get_gameroles()
    table = {kw.lower(): value for kw, value in table.items()}
    strtime = None; game = None
    role_id = 0
    new_text = ""
    for rawline in text.split("\n"):
        line = rawline.lower().replace("*", "")
        # Triangling links
        hi = rawline.find("https://")
        if hi != -1 and rawline[hi - 1] != "<":
            for i in range(hi, len(rawline)):
                if rawline[i] == " ":
                    break
            if rawline[i] != " ":
                i += 1
            rawline = rawline[:hi] + "<" + rawline[hi:i] + ">" + rawline[i:]
        # Finding additional info
        if "начало:" in line and strtime is None:
            strtime = line.split("начало:", maxsplit=1)[1].strip()
            new_text += f"> ⏰ {rawline}\n"
        elif "игра:" in line and game is None:
            game = line.split("игра:", maxsplit=1)[1].strip()
            role_id = table.get(game, 0)
        else:
            new_text += f"> {rawline}\n"
    del text

    target_role = server.get_role(role_id)
    if strtime is None:
        utc_game_start = None
    else:
        utc_game_start = dt_from_string(strtime)
    
    if utc_game_start is None or target_role is None:
        return None
    else:
        return (new_text, target_role, utc_game_start)


async def cut_send(channel, content):
    lim = 2000
    size = len(content)
    parts = (size - 1) // lim + 1
    msg = None
    for i in range(parts):
        lb = i * lim; ub = min((i + 1) * lim, size)
        if i < parts - 1:
            await channel.send(content[lb:ub])
        else:
            msg = await channel.send(content[lb:ub])
    return msg


async def prepare_notifications(guild):
    server = Server(guild.id)
    table = server.get_gameroles()
    tcs = server.get_tournament_channels()

    now = datetime.utcnow()
    _24_hrs = timedelta(hours=24)
    message_table = {}
    for tc in tcs:
        try:
            async for message in guild.get_channel(tc).history(limit=500):
                triplet = process_text(guild, message.content, table)
                if triplet is not None:
                    text, role, utc_game_start = triplet
                    del triplet
                    if utc_game_start >= now and now + _24_hrs > utc_game_start:
                        if role.id not in message_table:
                            message_table[role.id] = text
                        else:
                            message_table[role.id] += f"\n{text}"
        except Exception:
            # Most likely permissions error
            pass
    
    total_text = f"🎁 **| Турниры {guild.name} на сегодня |** 🎁\n\n"
    for game, roleid in table.items():
        if roleid in message_table:
            total_text += f"🏆 **__Турниры по игре {game}__** ||<@&{roleid}>||\n\n{message_table[roleid]}\n\n\n"
    if total_text == "":
        total_text = "Уведомлений нет"
    
    return total_text
    

class notifications(commands.Cog):
    def __init__(self, client):
        self.client = client

    #----------------------------------------------+
    #                   Events                     |
    #----------------------------------------------+
    @commands.Cog.listener()
    async def on_ready(self):
        print(f">> Notifications cog is loaded")

        now = datetime.utcnow()
        start_at = next_time(mass_dm_start_at, now)
            
        delta = (start_at - now).total_seconds()
        print(f"--> Notifications: T-{delta}s")
        await asyncio.sleep(delta)
        print("--> Notifications: collecting data")

        collection = db["config"]
        results = collection.find({})
        for result in results:
            try:
                if result.get("tournament_channels", []) is not None:
                    guild = self.client.get_guild(result["_id"])
                    channel = guild.get_channel(result.get("notifications_channel", 0))
                    if channel is not None:
                        text = await prepare_notifications(guild)
                        try:
                            await channel.purge()
                        except:
                            pass
                        msg = await cut_send(channel, text)
                        await msg.publish()
            except Exception:
                pass
        
        print("--> Notifications: sent")


    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        my_id = self.client.user.id
        if payload.guild_id is None and payload.emoji.name == key_emoji and payload.user_id != my_id:
            user = self.client.get_user(payload.user_id)
            channel = user.dm_channel
            if channel is None:
                channel = await user.create_dm()
            message = await channel.fetch_message(payload.message_id)
            if message.author.id == my_id:
                text = message.content
                changed = False
                for ph, original in placeholders.items():
                    if ph in text:
                        text = text.replace(ph, original)
                        changed = True
                if changed:
                    await message.edit(content=text)
        return

    #----------------------------------------------+
    #                  Commands                    |
    #----------------------------------------------+
    @commands.cooldown(1, 1, commands.BucketType.member)
    @commands.has_permissions(administrator=True)
    @commands.command(
        aliases=["add-tournament-channel", "add-t-channel", "a-t-c", "atc"],
        help="добавить канал с расписанием труниров",
        description="добавляет канал с расписанием турниров для последующей рассылки указанной там информации.",
        usage="#канал",
        brief="#турниры" )
    async def add_tournament_channel(self, ctx, *, tc: discord.TextChannel):
        Server(ctx.guild.id).add_tournament_channel(tc.id)
        reply = discord.Embed(
            title="📅 | Каналы с расписанием турниров",
            description=f"Добавлен канал <#{tc.id}>",
            color=discord.Color.blurple()
        )
        reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
        await ctx.send(embed=reply)
    

    @commands.cooldown(1, 1, commands.BucketType.member)
    @commands.has_permissions(administrator=True)
    @commands.command(
        aliases=["remove-tournament-channel", "rem-t-channel", "r-t-c", "rtc"],
        help="убрать канал с расписанием труниров",
        description="убирает канал с расписанием турниров. Больше рассылка турниров оттуда осуществляться не будет.",
        usage="#канал",
        brief="#турниры-2018" )
    async def remove_tournament_channel(self, ctx, *, tc: discord.TextChannel):
        Server(ctx.guild.id).remove_tournament_channel(tc.id)
        reply = discord.Embed(
            title="📅 | Каналы с расписанием турниров",
            description=f"Убран канал <#{tc.id}>",
            color=discord.Color.blurple()
        )
        reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
        await ctx.send(embed=reply)
    

    @commands.cooldown(1, 1, commands.BucketType.member)
    @commands.has_permissions(administrator=True)
    @commands.command(
        aliases=["log-channel", "set-log-channel", "lc"],
        help="настроить канал логов",
        description="настраивает канал логов для последующей отправки некоторых отчётов в него.",
        usage="#канал",
        brief="#турниры" )
    async def log_channel(self, ctx, *, tc: discord.TextChannel):
        Server(ctx.guild.id).set_log_channel(tc.id)
        reply = discord.Embed(
            title="📋 | Канал отчётов",
            description=f"Настроен как <#{tc.id}>",
            color=discord.Color.blurple()
        )
        reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
        await ctx.send(embed=reply)
    

    @commands.cooldown(1, 1, commands.BucketType.member)
    @commands.check_any(
        commands.has_permissions(administrator=True),
        is_guild_moderator() )
    @commands.command(
        aliases=["notifications-config", "n-conf"],
        help="текущие настройки уведомлений",
        description="показывает настройки уведомлений о расписании.",
        usage="",
        brief="" )
    async def notofocations_config(self, ctx):
        server = Server(ctx.guild.id)
        data = server.load_data()
        table = data.get("gameroles", {})
        tc = data.get("tournament_channels", [])
        lc = data.get("notifications_channel")
        del data
        
        # Visual roles
        tabledesc = ""
        for kw, rid in table.items():
            tabledesc += f"> {kw}: <@&{rid}>\n"
        if tabledesc == "":
            tabledesc = "> -"
        # Visual channels
        tcdesc = ""; ghost_channels = []
        for cid in tc:
            if ctx.guild.get_channel(cid) is None:
                ghost_channels.append(cid)
            else:
                tcdesc += f"> <#{cid}>\n"
        if tcdesc == "":
            tcdesc = "> -"
        # Visual "notifications channel
        lcdesc = "> Не настроен"
        if lc is not None:
            lcdesc = f"> <#{lc}>"
        
        reply = discord.Embed(
            title=":gear: | Настройки уведомлений",
            color=discord.Color.blurple()
        )
        reply.add_field(name="Каналы с расписанием", value=tcdesc, inline=False)
        reply.add_field(name="Таблица ролей игр", value=tabledesc, inline=False)
        reply.add_field(name="Канал для уведомлений", value=lcdesc)
        reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
        await ctx.send(embed=reply)

        # Deleting ghost data
        server.pull_tournament_channels(ghost_channels)


    @commands.cooldown(1, 1, commands.BucketType.member)
    @commands.has_permissions(administrator=True)
    @commands.command(
        aliases=["preview-notifications"],
        help="заранее просмотреть уведомления",
        description="показывает, как будут выглядеть уведомления.",
        usage="",
        brief="" )
    async def preview(self, ctx):
        await ctx.send("Идёт чтение каналов...")
        text = await prepare_notifications(ctx.guild)
        
        await cut_send(ctx.channel, text)


    @commands.cooldown(1, 1, commands.BucketType.member)
    @commands.has_permissions(administrator=True)
    @commands.command(
        aliases=["force-notifications", "force-notif", "fn"],
        help="экстренная рассылка",
        description="выслать уведомления раньше установленного срока.",
        usage="",
        brief="" )
    async def force_notifications(self, ctx):
        await ctx.send("Идёт чтение каналов...")
        text = await prepare_notifications(ctx.guild)

        reply = discord.Embed(
            title="📥 | Каналы прочитаны",
            description=f"Выслал уведомления в новостной канал",
            color=discord.Color.blurple()
        )
        reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
        await ctx.send(embed=reply)

        ncid = Server(ctx.guild.id).get_notifications_channel()
        channel = ctx.guild.get_channel(ncid)
        if channel is not None:
            try:
                await channel.purge()
            except:
                pass
            msg = await cut_send(channel, text)
            try:
                await msg.publish()
            except:
                pass


    @commands.cooldown(1, 1, commands.BucketType.member)
    @commands.has_permissions(administrator=True)
    @commands.command(
        aliases=["notifications-channel", "notif-channel", "nc"],
        help="настроить канал для уведомлений",
        description="настраивает канал для публикации уведомлений. Чтобы сбросить настройку, используйте команду без аргументов.",
        usage="#канал",
        brief="#турниры-сегодня" )
    async def notifications_channel(self, ctx, channel: discord.TextChannel=None):
        if channel is None:
            Server(ctx.guild.id).set_notifications_channel(None)
            reply = discord.Embed(
                title="🗑 | Канал для уведомлений сброшен",
                description=f"Ок чё",
                color=discord.Color.blurple()
            )
            reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
            await ctx.send(embed=reply)
       
        else:
            Server(ctx.guild.id).set_notifications_channel(channel.id)
            reply = discord.Embed(
                title="📢 | Настроен канал для уведомлений",
                description=f"Теперь уведомления будут приходить в <#{channel.id}>",
                color=discord.Color.blurple()
            )
            reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
            await ctx.send(embed=reply)


    #----------------------------------------------+
    #                   Errors                     |
    #----------------------------------------------+


def setup(client):
    client.add_cog(notifications(client))