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
mass_dm_start_at = time(21)  # 5 am UTC+3


placeholders = {
    "||{i}||": "https://discord.gg/",
    "||{h}||": "https://"
}
key_emoji = "🔎"

mass_dms = {}

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


class BadMassDM(Exception):
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
        # Removing links
        for ph, original in placeholders.items():
            if original in rawline:
                rawline = rawline.replace(original, ph)
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


async def prepare_mass_dm(guild):
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
    
    targets = []
    for target in guild.members:
        subs = [r.id for r in target.roles if r.id in message_table]
        if subs != []:
            targets.append((target, subs))
    
    if targets != []:
        global mass_dms
        mass_dms[guild.id] = MassDM(guild, message_table, table, targets)


class MassDM:
    def __init__(self, guild: discord.Guild, message_table: dict, gametable: dict, targets: list):
        self.id = guild.id
        self.name = guild.name
        lcid = Server(self.id).get_log_channel()
        if lcid is None:
            self.log_channel = None
        else:
            self.log_channel = guild.get_channel(lcid)
        del guild
        self.targets = targets
        self.table = gametable
        self.message_table = message_table
        self.total_targets = len(self.targets)
        self.total_recieved = 0
        self.started_at = None
        self.messages_per_minute = 22
        self.__dead = False
    
    @property
    def estimated_end(self):
        et_mins = (self.total_targets - self.total_recieved) / self.messages_per_minute
        return self.started_at + timedelta(minutes=et_mins)
    
    async def launch(self):
        self.started_at = datetime.utcnow()
        for member, subs in self.targets:        # target = (Member, [role_IDs])
            # Checking if process is killed
            if self.__dead:
                self.__dead = False
                break
            # Waiting a bit not to get ratelimited
            await asyncio.sleep(1)
            # Forming text
            total_text = f"🎁 | **Турниры {self.name}**\n\n"
            for game, roleid in self.table.items():
                if roleid in subs and roleid in self.message_table:
                    total_text += f"🏆 **__Турниры по игре {game}__**\n\n{self.message_table[roleid]}\n\n\n"
            # Sending text
            try:
                msg = await cut_send(member, total_text)
                self.total_recieved += 1
                await msg.add_reaction(key_emoji)
            except Exception:
                pass
            # Updating sending speed
            delta = (datetime.utcnow() - self.started_at).total_seconds()
            if self.total_recieved > 0 and delta > 0:
                self.messages_per_minute = 60 * self.total_recieved / delta
        try:
            global mass_dms
            mass_dms.pop(self.id)

            # Log
            stats = discord.Embed(
                title="📚 | Итоги рассылки",
                description=(
                    f"**Получено сообщений:** `{self.total_recieved} / {self.total_targets}`\n"
                    f"**Средняя скорость рассылки:** `{self.messages_per_minute}` сооб./мин.\n"
                    f"**Длительность:** `{datetime.utcnow() - self.started_at}`\n"
                ),
                color=discord.Color.blurple()
            )
            await self.log_channel.send(embed=stats)
        except Exception:
            pass

        return
    
    def kill(self):
        self.__dead = True


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
                    await prepare_mass_dm(guild)
            except Exception:
                pass
        
        for task in mass_dms.values():
            self.client.loop.create_task(task.launch())
        print("--> Notifications: mass DMs were launched")


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
        aliases=["mass-dm-config", "mdc", "md-config"],
        help="текущие настройки массовой рассылки",
        description="показывает настройки массовой рассылки расписания.",
        usage="",
        brief="" )
    async def mass_dm_config(self, ctx):
        server = Server(ctx.guild.id)
        data = server.load_data()
        table = data.get("gameroles", {})
        tc = data.get("tournament_channels", [])
        lc = data.get("log_channel")
        
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
        # Visual log channel
        lcdesc = "> Не настроен"
        if lc is not None:
            lcdesc = f"> <#{lc}>"
        
        reply = discord.Embed(
            title=":gear: | Настройки массовой рассылки",
            color=discord.Color.blurple()
        )
        reply.add_field(name="Каналы с расписанием", value=tcdesc, inline=False)
        reply.add_field(name="Таблица ролей игр", value=tabledesc, inline=False)
        reply.add_field(name="Канал отчётов", value=lcdesc)
        reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
        await ctx.send(embed=reply)

        # Deleting ghost data
        server.pull_tournament_channels(ghost_channels)


    @commands.cooldown(1, 1, commands.BucketType.member)
    @commands.has_permissions(administrator=True)
    @commands.command(
        aliases=["mass-dms"],
        help="статус активных рассылок",
        description="отображает данные об активных рассылках.",
        usage="",
        brief="" )
    async def tasks(self, ctx):
        _3_hrs = timedelta(hours=3)
        task = mass_dms.get(ctx.guild.id)
        if task is None:
            desc = "Активных рассылок нет."
        else:
            if task.started_at is not None:
                startdesc = f"**Началось в:** `{task.started_at + _3_hrs} (МСК)`"
            else:
                startdesc = f"**Начнётся в:** `{next_time(mass_dm_start_at) + _3_hrs}` (МСК)"
            enddesc = "-"
            if task.started_at is not None:
                enddesc = str(task.estimated_end + _3_hrs)
            desc = (
                f"{startdesc}\n"
                f"**Отправлено сообщений:** `{task.total_recieved} / {task.total_targets}`\n"
                f"**Скорость отправки:** `{task.messages_per_minute} сооб./мин.`\n"
                f"**Примерное окончание:** `{enddesc} (МСК)`\n"
            )
        reply = discord.Embed(
            title="📡 | Статус рассылок",
            description=desc,
            color=discord.Color.blurple()
        )
        reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
        await ctx.send(embed=reply)


    @commands.cooldown(1, 1, commands.BucketType.member)
    @commands.has_permissions(administrator=True)
    @commands.command(
        aliases=["preview-notifications"],
        help="заранее просмотреть уведомления",
        description="показывает, как будут выглядеть уведомления.",
        usage="",
        brief="" )
    async def preview(self, ctx):
        task = mass_dms.get(ctx.guild.id)
        if task is None:
            await ctx.send("Идёт чтение каналов...")
            await prepare_mass_dm(ctx.guild)
        
        task = mass_dms.get(ctx.guild.id)
        if task is None:
            total_text = "Уведомлений нет"
        else:
            total_text = ""
            for game, roleid in task.table.items():
                if roleid in task.message_table:
                    total_text += f"🏆 **__Турниры по игре {game}__**\n\n{task.message_table[roleid]}\n\n\n"
            if total_text == "":
                total_text = "Уведомлений нет"
        await cut_send(ctx.channel, total_text)


    @commands.cooldown(1, 1, commands.BucketType.member)
    @commands.has_permissions(administrator=True)
    @commands.command(
        aliases=["read-tournament-channels", "read-t-channels", "read-tchannel", "read-tc"],
        help="заранее сформировать уведомления",
        description="просматривает все каналы с расписаниями и формирует уведомления.",
        usage="",
        brief="" )
    async def read_tournament_channels(self, ctx):
        await ctx.send("Идёт чтение каналов...")
        await prepare_mass_dm(ctx.guild)
        reply = discord.Embed(
            title="📥 | Уведомления сформированы",
            description=f"Статус задач: `{ctx.prefix}tasks`",
            color=discord.Color.blurple()
        )
        reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
        await ctx.send(embed=reply)


    @commands.cooldown(1, 1, commands.BucketType.member)
    @commands.has_permissions(administrator=True)
    @commands.command(
        aliases=["force-mass-dms", "force-md", "fmd"],
        help="экстренная рассылка",
        description="начать рассылку раньше установленного срока.",
        usage="",
        brief="" )
    async def force_mass_dms(self, ctx):
        await ctx.send("Идёт чтение каналов...")
        await prepare_mass_dm(ctx.guild)
        task = mass_dms.get(ctx.guild.id)
        reply = discord.Embed(
            title="📥 | Уведомления сформированы, начинаю рассылку",
            description=f"Статус задач: `{ctx.prefix}tasks`",
            color=discord.Color.blurple()
        )
        reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
        await ctx.send(embed=reply)
        await task.launch()


    @commands.cooldown(1, 1, commands.BucketType.member)
    @commands.has_permissions(administrator=True)
    @commands.command(
        aliases=["kill-tasks"],
        help="прервать рассылку",
        description="прерывает рассылку на любом её этапе.",
        usage="",
        brief="" )
    async def kill_tasks(self, ctx):
        task = mass_dms.get(ctx.guild.id)
        if task is None:
            reply = discord.Embed(
                title="❌ | Активных рассылок нет",
                description=f"Убедитесь в этом сами: `{ctx.prefix}tasks`",
                color=discord.Color.dark_red()
            )
            reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
            await ctx.send(embed=reply)
       
        else:
            task.kill()
            mass_dms.pop(ctx.guild.id)
            reply = discord.Embed(
                title="🗑 | Рассылка прервана",
                description=f"Задачи сняты, проверьте `{ctx.prefix}tasks`",
                color=discord.Color.blue()
            )
            reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
            await ctx.send(embed=reply)


    #----------------------------------------------+
    #                   Errors                     |
    #----------------------------------------------+


def setup(client):
    client.add_cog(notifications(client))