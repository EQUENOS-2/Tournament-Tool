import discord
from discord.ext import commands
import asyncio
import os, json
from pymongo import MongoClient
from random import randint

#----------------------------------------------+
#                Connections                   |
#----------------------------------------------+
bot_token = str(os.environ.get("bot_token"))
db_token = str(os.environ.get("db_token"))
prefix = ".."

client = commands.Bot(prefix)
client.remove_command("help")
cluster = MongoClient(db_token)
db = cluster["tournament_tool_db"]


#----------------------------------------------+
#                  Variables                   |
#----------------------------------------------+
owner_ids = [
    301295716066787332
]

#----------------------------------------------+
#                  Functions                   |
#----------------------------------------------+
from functions import antiformat as anf
from functions import has_permissions, is_int, carve_int, get_field, find_alias, display_perms, vis_aliases, Server
from custom_converters import IntConverter



def channel_url(channel):
    return f"https://discordapp.com/channels/{channel.guild.id}/{channel.id}"


def from_hex(hex_code):
    return int(hex_code[1:], 16)


def is_guild_moderator():
    def predicate(ctx):
        mod_roles = Server(ctx.guild.id, projection={"mod_roles", True}).mod_roles
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


def has_instance(_list, _class):
    has = False
    for elem in _list:
        if isinstance(elem, _class):
            has = True
            break
    return has


class IsNotModerator(commands.CheckFailure):
    pass


class Detect:
    def __init__(self, guild):
        self.guild = guild
    
    def member(self, search):
        _id = carve_int(search)
        member = None
        if _id is  not None:
            member = self.guild.get_member(_id)
        if member is None:
            member = self.guild.get_member_named(search)
        return member


class Participant:
    def __init__(self, discord_user):
        if isinstance(discord_user, int):
            self.id = discord_user
        else:
            self.id = discord_user.id
    
    def update_stats(self, points, place):
        collection = db["users"]
        collection.update_one(
            {"_id": self.id},
            {"$push": {"history": {
                "place": place,
                "rating": points
            }}},
            upsert=True
        )
    
    def get_stats(self):
        history = self.get_history()
        pts, trs = 0, 0
        for tournament in history:
            pts += tournament["rating"]
            trs += 1
        return (pts, trs)

    def get_history(self, as_tuples=False):
        collection = db["users"]
        history = get_field(collection.find_one({"_id": self.id}), "history", default=[])
        if as_tuples:
            history = [(t["rating"], t["place"]) for t in history]
        return history

    def rollback(self):
        collection = db["users"]
        history = get_field(collection.find_one_and_update(
            {"_id": self.id},
            {"$pop": {"history": 1}},
            upsert=True
        ), "history", default=[])
        return None if history == [] else history[len(history) - 1]


class Leaderboard:
    def __init__(self, tuple_array, interval=10):
        self.tuples = tuple_array
        self.interval = interval
        self.length = len(self.tuples)
        self.total_pages = (self.length - 1) // self.interval + 1

    def sort_values(self, reverse=True, sort_by=1):
        self.tuples.sort(key=lambda tuple: tuple[sort_by], reverse=reverse)

    def get_page(self, page):
        """
        Partially returns tuple array and index of the left element of this array
        """
        lower_bound = (page - 1) * self.interval
        upper_bound = min(lower_bound + self.interval, self.length)
        return (self.tuples[lower_bound:upper_bound], lower_bound)
    
    def tuple_index(self, tuple_value, compare_by=0):
        out = None
        for i in range(self.length):
            if self.tuples[i][compare_by] == tuple_value:
                out = i
                break
        return out

#----------------------------------------------+
#                    Events                    |
#----------------------------------------------+
@client.event
async def on_ready():
    print(
        f"Bot user: {client.user}\n"
        f"ID: {client.user.id}"
    )

#----------------------------------------------+
#                  Commands                    |
#----------------------------------------------+
@commands.cooldown(1, 1, commands.BucketType.member)
@client.command(aliases=["h"], help="узнать подробнее о каждой команде")
async def help(ctx, *, cmd_s=None):
    p = ctx.prefix
    
    if cmd_s is None:
        cog_desc = f"> `{p}commands main`\n"
        for _cog in client.cogs:
            cog_desc += f"> `{p}commands {_cog}`\n"
        reply = discord.Embed(
            title="📖 Категории команд",
            description=(
                f"Просмотреть каждую категорию:\n{cog_desc}\n"
                f"Подробнее о команде: `{p}help нужная команда`"
            ),
            color=discord.Color.blurple()
        )
        reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
        await ctx.send(embed=reply)

    else:
        cmd = None
        for c in client.commands:
            if cmd_s in [c.name, *c.aliases]:
                cmd = c
                break
        
        if cmd is None:
            reply = discord.Embed(
                title="🔎 | Не нашёл команду, увы",
                description=f"У меня нет команды `{p}{cmd_s}`, может, Вы ошиблись?",
                color=discord.Color.blurple()
            )
            reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
            await ctx.send(embed=reply)
        
        else:
            description = "`-`"; usage = "`-`"; brief = "`-`"; aliases = "-"
            if cmd.description != "":
                description = cmd.description
            if cmd.usage is not None:
                usage = "\n> ".join( [f"`{p}{cmd} {u}`" for u in cmd.usage.split("\n")] )
            if cmd.brief is not None:
                brief = "\n> ".join( [f"`{p}{cmd} {u}`" for u in cmd.brief.split("\n")] )
            if len(cmd.aliases) > 0:
                aliases = ", ".join(cmd.aliases)
            
            reply = discord.Embed(
                title = f"❓ Об аргументах `{p}{cmd}`",
                description = (
                    f"**Описание:** {description}\n"
                    f"**Использование:** {usage}\n"
                    f"**Примеры:** {brief}\n\n"
                    f"**Синонимы:** `{aliases}`"
                )
            )
            reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
            await ctx.send(embed=reply)

            try:
                ctx.command.reset_cooldown(ctx)
            except Exception:
                pass


@commands.cooldown(1, 1, commands.BucketType.member)
@client.command(name="commands", aliases=["cmds"], help="список всех команд из категории")
async def _commands(ctx, *, section=None):
    p = ctx.prefix
    if section is None:
        cog_desc = f"> `{p}commands main`\n"
        for _cog in client.cogs:
            cog_desc += f"> `{p}commands {_cog}`\n"
            
        reply = discord.Embed(
            title="📖 Категории команд",
            description=(
                f"Просмотреть каждую категорию:\n{cog_desc}\n"
                f"Подробнее о команде: `{p}help нужная команда`"
            ),
            color=discord.Color.blurple()
        )
        reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
        await ctx.send(embed=reply)
    
    else:
        cog_found = None
        sec = section.lower()
        if "main".startswith(sec):
            cog_found = "main"
            cog_commands = [c for c in client.commands if c.cog is None]
        else:
            for _cog in client.cogs:
                if str(_cog).lower().startswith(sec):
                    cog_found = _cog
                    cog_commands = client.get_cog(_cog).get_commands()
                    break
        
        if cog_found is None:
            reply = discord.Embed(
                title="🔎 | Не нашёл категорию, увы",
                description=f"У меня нет категории `{section}`, может стоит проверить написание?",
                color=discord.Color.blurple()
            )
            reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
            await ctx.send(embed=reply)
        
        else:
            desc = ""
            for cmd in cog_commands:
                if cmd.help is None:
                    cmdhelp = "[-]"
                else:
                    cmdhelp = cmd.help
                desc += f"`{p}{cmd}` - {cmdhelp}\n"
            reply = discord.Embed(
                title=f"📁 | Категория команд `{cog_found}`",
                description=f"Подробнее о команде: `{p}help нужная команда`\n\n{desc}",
                color=discord.Color.blurple()
            )
            reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
            await ctx.send(embed=reply)


@commands.cooldown(1, 1, commands.BucketType.member)
@client.command(help="даже не думай")
async def test(ctx, num: IntConverter=None):
    if ctx.author.id not in owner_ids:
        reply = discord.Embed(
            title="⛔ Недостаточно прав",
            description=(
                "Необходимые права:\n"
                "> Разработчик пельменеф"
            ),
            color=discord.Color.dark_red()
        )
        reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
        await ctx.send(embed=reply)
    else:
        # categ = ctx.guild.get_channel(566638204036448257)
        # role = ctx.guild.get_role(681453567516606490)
        # ovw = categ.overwrites()
        # ovw[role] = discord.PermissionOverwrite(manage_permissions=True)
        # await categ.edit(overwrites=ovw)

        word = "хуест"
        _word = ""
        for s in word:
            if randint(0, 1):
                _word += s.upper()
            else:
                _word += s
        await ctx.send(_word)


@commands.cooldown(1, 1, commands.BucketType.member)
@commands.check_any(
    commands.has_permissions(administrator=True),
    is_guild_moderator() )
@client.command(
    aliases=["r"],
    help="изменить чей-то рейтинг",
    description="изменяет рейтинг участника и обновляет историю турниров",
    brief="Число Место @Участник",
    usage="5 1 @User#1234" )
async def rating(ctx, num: int, place: int, *, member: discord.Member):
    user = Participant(member)
    user.update_stats(num, place)
    reply = discord.Embed(
        title="📀 Изменения бережно сохранены",
        description=(
            f"**Участник:** {member}\n"
            f"**Изменения рейтинга:** {num} ⚡\n"
            f"**Место в турнире:** {place} 🏅"
        ),
        color=from_hex("#ecd994")
    )
    reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
    await ctx.send(embed=reply)


@commands.cooldown(1, 1, commands.BucketType.member)
@commands.check_any(
    commands.has_permissions(administrator=True),
    is_guild_moderator() )
@client.command(
    aliases=["clear-top"],
    help="очистить топ",
    description="очищает список участников",
    brief="",
    usage="" )
async def clear_top(ctx):
    Q = discord.Embed(
        title="❓ Вы уверены?",
        description="Напишите `да` или `нет`"  
    )
    Q.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
    await ctx.send(embed=Q)

    yes = ["да", "yes", "1"]
    no = ["нет", "no", "0"]
    try:
        msg = await client.wait_for(
            "message",
            check=lambda m: m.author.id == ctx.author.id and m.channel.id == ctx.channel.id and m.content.lower() in [*yes, *no],
            timeout=60
        )
    except asyncio.TimeoutError:
        await ctx.send(f"{ctx.author.mention}, Вы слишком долго не отвечали, сброс топа отменён")

    else:
        if msg.content.lower() in yes:
            server = Server(ctx.guild.id)
            server.reset_participants()
            reply = discord.Embed(
                title="💥 Очищено",
                description="Топа участников больше нет. До связи.",
                color=discord.Color.orange()
            )
            reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
            await ctx.send(embed=reply)
        else:
            reply = discord.Embed(
                title="👌 Действие отменено",
                description="Топ участников уцелел. Сегодня."
            )
            reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
            await ctx.send(embed=reply)


@commands.cooldown(1, 1, commands.BucketType.member)
@commands.check_any(
    commands.has_permissions(administrator=True),
    is_guild_moderator() )
@client.command(
    help="отменить последнее действие с участником",
    description="отменяет последнее действие с участником",
    brief="@Участник",
    usage="@User#1234" )
async def back(ctx, *, member: discord.Member):
    user = Participant(member)
    result = user.rollback()

    if result is None:
        reply = discord.Embed(
            title="📦 Ошибка",
            description=f"Последних действий с **{member}** не обнаружено"
        )
        reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
        await ctx.send(embed=reply)
    
    else:
        pts, place = result["rating"], result["place"]
        reply = discord.Embed(
            title="♻ Изменения отменены",
            description=(
                "Подробнее об отменённом действии:\n"
                f"> **Участник:** {member}\n"
                f"> **Изменения рейтинга:** {pts} ⚡\n"
                f"> **Место в турнире:** {place} 🏅"
            ),
            color=discord.Color.dark_green()
        )
        reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
        await ctx.send(embed=reply)


@commands.cooldown(1, 1, commands.BucketType.member)
@client.command(aliases=["profile"], help="посмотреть профиль")
async def me(ctx, *, member: discord.Member=None):
    if member is None:
        member = ctx.author
    server = Server(ctx.guild.id, pre_result={})
    lb = Leaderboard(server.get_participants())
    lb.sort_values()
    _index = lb.tuple_index(member.id)

    if _index is None:
        pos_desc = "???"
        pts = 0
        trs = 0
    else:
        pos_desc = f"#{_index + 1}"
        pts = lb.tuples[_index][1]
        trs = lb.tuples[_index][2]

    del lb
    reply = discord.Embed(
        title=f"🗂 Профиль **{member}**",
        description=(
            f"**Очков рейтинга:** {pts} ⚡\n\n"
            f"**Позиция в топе:** {pos_desc}\n\n"
            f"**Сыграно турниров:** {trs} 🏆\n\n"
            f"**История турниров:** `{ctx.prefix}tournament-history 1 {member}`"
        ),
        color=member.color
    )
    reply.set_thumbnail(url=member.avatar_url)
    await ctx.send(embed=reply)


@commands.cooldown(1, 1, commands.BucketType.member)
@client.command(
    aliases=["tournament-history", "th"],
    help="узнать историю турниров",
    description="отображает историю турниров участника",
    brief="Страница @Участник",
    usage="1 @User#1234" )
async def tournament_history(ctx, page: int, *, member: discord.Member=None):
    if member is None:
        member = ctx.author
    
    user = Participant(member)
    lb = Leaderboard(user.get_history(as_tuples=True))
    if lb.tuples == []:
        reply = discord.Embed(
            title="📖 История отсутствует",
            description=f"Пока что у **{member}** нет активности в турнирах"
        )
        reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
        await ctx.send(embed=reply)
    elif page < 1 or page > lb.total_pages:
        reply = discord.Embed(
            title="💢 Страница не найдена",
            description=f"Всего страниц: {lb.total_pages}",
            color=discord.Color.dark_red()
        )
        reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
        await ctx.send(embed=reply)
    else:
        tuples, pos = lb.get_page(page)
        total_pages = lb.total_pages
        del lb
        reply = discord.Embed(
            title=f"🏅 История турниров **{member}**",
            color=from_hex("#ffdead")
        )
        for tup in tuples:
            pos += 1
            reply.add_field(name=f"📁 **Турнир {pos}**", value=(
                f"> **Место:** {tup[1]} \\🏅\n"
                f"> **Рейтинг:** {tup[0]} \\⚡"
            ))
        reply.set_footer(text=f"Стр. {page} / {total_pages}")
        await ctx.send(embed=reply)


@commands.cooldown(1, 3, commands.BucketType.member)
@client.command(help="топ участников")
async def top(ctx, page: int=1):
    server = Server(ctx.guild.id, pre_result={})
    lb = Leaderboard(server.get_participants())

    if lb.tuples == []:
        reply = discord.Embed(
            title="📖 Топ пустует",
            description=f"Пока что ни у кого нет очков"
        )
        reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
        await ctx.send(embed=reply)
    
    elif page > lb.total_pages:
        reply = discord.Embed(
            title="💢 Страница не найдена",
            description=f"Всего страниц: {lb.total_pages}",
            color=discord.Color.dark_red()
        )
        reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
        await ctx.send(embed=reply)
    
    else:
        lb.sort_values()
        total_pages = lb.total_pages
        tuples, pos = lb.get_page(page)
        del lb
        desc = ""
        curl = channel_url(ctx.channel)
        for i, tup in enumerate(tuples):
            nick = f"[{client.get_user(tup[0])}]({curl})"
            desc += f"`{pos + i + 1}.` {nick} | Рейтиг: {tup[1]} \\⚡| Турниров: {tup[2]} \\🏆\n"
        
        reply = discord.Embed(
            title="🏆 Топ участников",
            description=desc,
            color=discord.Color.gold()
        )
        reply.set_footer(text=f"Стр. {page} / {total_pages}")
        await ctx.send(embed=reply)

#----------------------------------------------+
#                   Errors                     |
#----------------------------------------------+
@client.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        
        def TimeExpand(time):
            if time//60 > 0:
                return str(time//60)+'мин. '+str(time%60)+' сек.'
            elif time > 0:
                return str(time)+' сек.'
            else:
                return f"0.1 сек."
        
        cool_notify = discord.Embed(
                title='⏳ Подождите немного',
                description = f"Осталось {TimeExpand(int(error.retry_after))}"
            )
        await ctx.send(embed=cool_notify)
    
    elif isinstance(error, commands.MissingPermissions):
        if ctx.author.id not in owner_ids:
            reply = discord.Embed(
                title="❌ Недостаточно прав",
                description=f"Необходимые права:\n{display_perms(error.missing_perms)}",
                color=discord.Color.dark_red()
            )
            reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
            await ctx.send(embed=reply)
        else:
            try:
                await ctx.reinvoke()
            except Exception as e:
                await on_command_error(ctx, e)
    
    elif isinstance(error, commands.MissingRequiredArgument):
        p = ctx.prefix
        cmd = ctx.command
        reply = discord.Embed(
            title=f"🗃 `{cmd.name}`: недостаточно аргументов",
            description=(
                "Как правильно?\n"
                f"**Использование:** `{p}{cmd.name} {cmd.brief}`\n"
                f"**Пример:** `{p}{cmd.name} {cmd.usage}`\n\n"
                f"**Подробнее об этой команде:** `{p}help {cmd}`"
            ),
            color=discord.Color.dark_red()
        )
        reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
        await ctx.send(embed=reply)

    elif isinstance(error, commands.CheckAnyFailure):
        if ctx.author.id not in owner_ids:
            if has_instance(error.errors, IsNotModerator):
                reply = discord.Embed(
                    title="❌ Недостаточно прав",
                    description=f"Необходимые права:\n> Модератор",
                    color=discord.Color.dark_red()
                )
                reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
                await ctx.send(embed=reply)
            elif len(error.errors) > 0:
                await on_command_error(ctx, error.errors[0])
            
        else:
            try:
                await ctx.reinvoke()
            except Exception as e:
                await on_command_error(ctx, e)

    elif isinstance(error, commands.BadArgument):
        print(error)
        obj, arg, rest = str(error).split('"', maxsplit=2)
        obj = obj.strip().lower()
        del rest
        ru_msgs = {
            "role": f"Роль **{arg}** не была найдена на сервере.",
            "member": f"Участник **{arg}** не был найден на сервере.",
            "user": f"Пользователь **{arg}** не был найден, возможно, у меня с ним нет общих серверов.",
            "channel": f"Канал **{arg}** не был найден на сервере.",
            "int": f"Аргумент **{arg}** должен быть целым числом, например `5`."
        }
        desc = ru_msgs.get(obj, "Кажется, введённые аргументы не соответствуют требуемому формату.")
        
        reply = discord.Embed(
            title=f"📍 | Что-то введено неправильно",
            description=desc,
            color=discord.Color.dark_red()
        )
        reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
        await ctx.send(embed=reply)

    elif isinstance(error, commands.CommandNotFound):
        pass

    else:
        raise error

#----------------------------------------------+
#                  Loading Cogs                |
#----------------------------------------------+
for file_name in os.listdir("./cogs"):
    if file_name.endswith(".py"):
        client.load_extension(f"cogs.{file_name[:-3]}")

# Running
client.run(bot_token)