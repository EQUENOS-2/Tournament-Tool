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
anygame = "[anygame]"


def is_guild_moderator():
    def predicate(ctx):
        mod_roles = Server(ctx.guild.id, {"mod_roles": True}).mod_roles
        author_role_ids = [r.id for r in ctx.author.roles]
        has = False
        for role_id in mod_roles:
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
    """Reads the time as UTC+3 and returns UTC"""
    triplet = string.split(maxsplit=2)
    if len(triplet) <= 1:
        return None
    else:
        ymd, hm = triplet[0], triplet[1]
        del triplet
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


def process_text(server: discord.Guild, text: str, table: list):
    """Returns: (Text, GameTuple, UTC)"""
    del server
    strtime = None; game = None
    new_text = ""
    for rawline in text.split("\n"):
        rawline = rawline.replace("@", "@ ")
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
            try:
                game = line.split("игра:", maxsplit=1)[1].strip().lower()
                if game not in [gt.game.lower() for gt in table]:
                    new_text += f"> 🎮 {rawline}\n"
                    game = anygame
            except:
                pass
        else:
            new_text += f"> {rawline}\n"
    del text

    if strtime is None or game is None:
        return None
    utc_game_start = dt_from_string(strtime)
    if utc_game_start is None:
        return None
    
    target_gametuple = None
    for gt in table:
        if gt.game.lower() == game:
            target_gametuple = gt
            break

    if target_gametuple is None:
        return None
    return (new_text, target_gametuple, utc_game_start)


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
    """Returns a dictionary {channel_id: text_to_send}"""
    server = Server(guild.id, {"gametable": True, "tournament_channels": True})
    table = server.gametable
    tcs = server.tournament_channels
    del server

    now = datetime.utcnow()
    _24_hrs = timedelta(hours=24)
    message_table = {}
    for tc in tcs:
        try:
            async for message in guild.get_channel(tc).history(limit=500):
                triplet = process_text(guild, message.content, table)
                if triplet is not None:
                    text, gametuple, utc_game_start = triplet
                    del triplet
                    if utc_game_start >= now and now + _24_hrs > utc_game_start:
                        if gametuple not in message_table:
                            message_table[gametuple] = [(utc_game_start, text)]
                        else:
                            message_table[gametuple].append((utc_game_start, text))
        except:
            # Most likely permissions error
            pass
    
    final_message_table = {}
    for gametuple, pairs in message_table.items():
        if gametuple.game == anygame: gametuple.game = "другим играм"
        text = f"🏆 **| Турниры по __{gametuple.game}__ на сегодня**\n\n"
        for _, granula in sorted(pairs, key=lambda p: p[0]):
            text += f"\n{granula}"
        final_message_table[gametuple.channel] = text
    del message_table
    return final_message_table
    

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
            result = Server(result["_id"], pre_result=result)
            try:
                if result.tournament_channels != []:
                    guild = self.client.get_guild(result.id)
                    if guild is not None:
                        pairs = await prepare_notifications(guild)
                        for channel_id, text in pairs.items():
                            if channel_id is not None:
                                channel = guild.get_channel(channel_id)
                                try:
                                    await channel.purge()
                                except:
                                    pass
                                msg = await cut_send(channel, text)
                                await msg.publish()
            except Exception:
                pass
        
        print("--> Notifications: sent")


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
        aliases=["notifications-config", "nconf", "nc"],
        help="текущие настройки уведомлений",
        description="показывает настройки уведомлений о расписании.",
        usage="",
        brief="" )
    async def notifications_config(self, ctx):
        server = Server(ctx.guild.id)
        
        # Visual GameTable
        tabledesc = ""
        for gt in server.gametable:
            if gt.game == anygame:
                gt.game = "Остальные игры"
            tabledesc += f"> {gt.game}: <#{gt.channel}>\n"
        if tabledesc == "":
            tabledesc = "> -"
        # Visual channels
        tcdesc = ""; ghost_channels = []
        for cid in server.tournament_channels:
            if ctx.guild.get_channel(cid) is None:
                ghost_channels.append(cid)
            else:
                tcdesc += f"> <#{cid}>\n"
        if tcdesc == "":
            tcdesc = "> -"
        
        
        reply = discord.Embed(
            title=":gear: | Настройки уведомлений",
            color=discord.Color.blurple()
        )
        reply.add_field(name="Каналы с расписанием", value=tcdesc, inline=False)
        reply.add_field(name="Каналы для уведомлений по играм", value=tabledesc, inline=False)
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
        pairs = await prepare_notifications(ctx.guild)
        for text in pairs.values():
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
        pairs = await prepare_notifications(ctx.guild)

        desc = ""
        for channel_id, text in pairs.items():
            if channel_id is not None:
                channel = ctx.guild.get_channel(channel_id)
                if channel is not None: desc += f"> <#{channel_id}>\n"
                try:
                    await channel.purge()
                except:
                    pass
                msg = await cut_send(channel, text)
                try:
                    await msg.publish()
                except:
                    pass
        
        if desc == "": desc = "> -"
        reply = discord.Embed(
            title="📥 | Уведомления высланы досрочно",
            description=f"Их можно просмотреть в одном из каналов:\n{desc}",
            color=discord.Color.blurple()
        )
        reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
        await ctx.send(embed=reply)


    @commands.cooldown(1, 1, commands.BucketType.member)
    @commands.has_permissions(administrator=True)
    @commands.command(
        aliases=["add-game-channel", "addgamechannel", "agc"],
        help="настроить канал для уведомлений по конкретной игре",
        description="настраивает канал для публикации уведомлений по указанной игре.",
        usage="#канал Название Игры",
        brief="#brawlstars-сегодня Brawl Stars" )
    async def add_game_channel(self, ctx, channel: discord.TextChannel, *, gamename):
        Server(ctx.guild.id, pre_result={}).add_game_channel(gamename, channel.id)
        reply = discord.Embed(
            title="📢 | Настроен канал для уведомлений",
            description=f"Теперь уведомления по игре **{gamename}** будут приходить в <#{channel.id}>",
            color=discord.Color.blurple()
        )
        reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
        await ctx.send(embed=reply)
    

    @commands.cooldown(1, 1, commands.BucketType.member)
    @commands.has_permissions(administrator=True)
    @commands.command(
        aliases=["remove-game-channel", "remgamechannel", "rgc"],
        help="сбросить канал для уведомлений по конкретной игре",
        description="сбрасывает канал для публикации уведомлений по указанной игре.",
        usage="Название игры",
        brief="Brawl Stars" )
    async def remove_game_channel(self, ctx, *, gamename):
        server = Server(ctx.guild.id, {"gametable": True})
        if gamename not in [gt.game for gt in server.gametable]:
            await ctx.send(f"❌ | Расписание по игре **{gamename}** не отсылается ни в один канал.\nПроверьте: `{ctx.prefix}nc`")
        else:
            server.remove_game_channel(gamename)
            reply = discord.Embed(
                title="📢 | Сброшен канал для уведомлений",
                description=f"Теперь уведомления по игре **{gamename}** не будут приходить.",
                color=discord.Color.blurple()
            )
            reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
            await ctx.send(embed=reply)


    #----------------------------------------------+
    #                   Errors                     |
    #----------------------------------------------+


def setup(client):
    client.add_cog(notifications(client))