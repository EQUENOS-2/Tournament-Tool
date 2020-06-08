import discord
from discord.ext import commands
import asyncio
import os, json
import pymongo
from pymongo import MongoClient
from random import randint

#----------------------------------------------+
#                Connections                   |
#----------------------------------------------+
bot_token = str(os.environ.get("bot_token"))
db_token = str(os.environ.get("db_token"))
prefix = "+"

client = commands.Bot(prefix)
client.remove_command("help")
cluster = MongoClient(db_token)
db = cluster["tournament_tool_db"]

#----------------------------------------------+
#                  Variables                   |
#----------------------------------------------+
owner_ids = [
    301295716066787332,
    647388176251617290
]

#----------------------------------------------+
#                  Functions                   |
#----------------------------------------------+
from functions import antiformat as anf
from functions import has_permissions, is_int, carve_int, get_field, find_alias, display_perms, vis_aliases


def channel_url(channel):
    return f"https://discordapp.com/channels/{channel.guild.id}/{channel.id}"


def from_hex(hex_code):
    return int(hex_code[1:], 16)


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
        if "int" in str(type(discord_user)).lower():
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


class Server:
    def __init__(self, discord_guild):
        self.id = discord_guild.id
    
    def get_participants(self):
        collection = db["users"]
        results = collection.find({})
        if results is None:
            return []
        else:
            out = []
            for result in results:
                pts, trs = 0, 0
                for t in result.get("history", []):
                    pts += t["rating"]
                    trs += 1
                out.append((result.get("_id"), pts, trs))
            return out


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
@client.command(aliases=["h"])
async def help(ctx, *, section=None):
    p = ctx.prefix
    reply = discord.Embed(
        title="📖 Меню команд",
        description=(
            f"Подробнее о команде: `{p}команда`\n\n"
            f"`{p}rating` - изменить историю турниров\n"
            f"`{p}back` - отменить изменение\n"
            f"`{p}me` - профиль\n"
            f"`{p}tournament-history` - история турниров\n"
            f"`{p}top` - топ участников\n"
            f"`{p}random` - случайное число\n"
            f"`{p}embed` - рамка с текстом\n"
            f"`{p}edit` - редактировать embed\n"
        )
    )
    await ctx.send(embed=reply)


@commands.cooldown(1, 1, commands.BucketType.member)
@client.command()
async def test(ctx):
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
        word = "хуест"
        _word = ""
        for s in word:
            if randint(0, 1):
                _word += s.upper()
            else:
                _word += s
        await ctx.send(_word)


@commands.cooldown(1, 1, commands.BucketType.member)
@client.command(
    aliases=["r"],
    help="изменяет рейтинг участника и обновляет историю турниров",
    brief="Число Место @Участник",
    usage="5 1 @User#1234"
)
async def rating(ctx, num, place, *, member_search):
    detect = Detect(ctx.guild)
    member = detect.member(member_search)
    if not has_permissions(ctx.author, ["administrator"]):
        reply = discord.Embed(
            title="⛔ Недостаточно прав",
            description=(
                "Необходимые права:\n"
                "> Администратор"
            ),
            color=discord.Color.dark_red()
        )
        reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
        await ctx.send(embed=reply)
    
    elif not is_int(num):
        reply = discord.Embed(
            title="💥 Неверный аргумент",
            description=f"Аргумент **{num}** должен быть целым числом, например `5` или `-5`",
            color=discord.Color.dark_red()
        )
        reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
        await ctx.send(embed=reply)
    
    elif not place.isdigit() or int(place) < 1:
        reply = discord.Embed(
            title="💥 Неверный аргумент",
            description=f"Аргумент **{place}** должен быть целым числом больше `1`, например `3`",
            color=discord.Color.dark_red()
        )
        reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
        await ctx.send(embed=reply)
    
    elif member is None:
        reply = discord.Embed(
            title="💥 Участник не найден",
            description=f"По поиску **{member_search}** не найдено результатов. Увы.",
            color=discord.Color.dark_red()
        )
        reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
        await ctx.send(embed=reply)
    
    else:
        num = int(num)
        place = int(place)

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
@client.command(
    help="отменяет последнее действие с участником",
    brief="@Участник",
    usage="@User#1234"
)
async def back(ctx, *, member_search):
    detect = Detect(ctx.guild)
    member = detect.member(member_search)
    if not has_permissions(ctx.author, ["administrator"]):
        reply = discord.Embed(
            title="⛔ Недостаточно прав",
            description=(
                "Необходимые права:\n"
                "> Администратор"
            ),
            color=discord.Color.dark_red()
        )
        reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
        await ctx.send(embed=reply)
    
    elif member is None:
        reply = discord.Embed(
            title="💥 Участник не найден",
            description=f"По поиску **{member_search}** не найдено результатов. Увы.",
            color=discord.Color.dark_red()
        )
        reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
        await ctx.send(embed=reply)
    
    else:
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
@client.command(aliases=["profile"])
async def me(ctx, *, member_search=None):
    if member_search is None:
        member = ctx.author
    else:
        member = Detect(ctx.guild).member(member_search)
    if member is None:
        reply = discord.Embed(
            title="💥 Участник не найден",
            description=f"По поиску **{member_search}** не найдено результатов. Увы.",
            color=discord.Color.dark_red()
        )
        reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
        await ctx.send(embed=reply)
    else:
        server = Server(ctx.guild)
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
    help="отображает историю турниров участника",
    brief="Страница @Участник",
    usage="1 @User#1234"
)
async def tournament_history(ctx, page, *, member_search=None):
    if member_search is None:
        member = ctx.author
    else:
        member = Detect(ctx.guild).member(member_search)
    
    if not page.isdigit():
        reply = discord.Embed(
            title="💥 Неверный аргумент",
            description=f"Аргумент **{page}** должен быть целым числом",
            color=discord.Color.dark_red()
        )
        reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
        await ctx.send(embed=reply)
    
    elif member is None:
        reply = discord.Embed(
            title="💥 Участник не найден",
            description=f"По поиску **{member_search}** не найдено результатов. Увы.",
            color=discord.Color.dark_red()
        )
        reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
        await ctx.send(embed=reply)
    else:
        page = int(page)
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
@client.command()
async def top(ctx, page="1"):
    if not page.isdigit():
        reply = discord.Embed(
            title="💥 Неверный аргумент",
            description=f"Аргумент **{page}** должен быть целым числом",
            color=discord.Color.dark_red()
        )
        reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
        await ctx.send(embed=reply)
    
    else:
        page = int(page)
        server = Server(ctx.guild)
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
        reply = discord.Embed(
            title="❌ Недостаточно прав",
            description=f"Необходимые права:\n{display_perms(error.missing_perms)}",
            color=discord.Color.dark_red()
        )
        reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
        await ctx.send(embed=reply)
    
    elif isinstance(error, commands.MissingRequiredArgument):
        p = ctx.prefix
        cmd = ctx.command
        reply = discord.Embed(
            title=f"🗃 О команде `{cmd.name}`",
            description=(
                f"**Описание:** {cmd.help}\n"
                f"**Использование:** `{p}{cmd.name} {cmd.brief}`\n"
                f"**Пример:** `{p}{cmd.name} {cmd.usage}`\n\n"
                f"{vis_aliases(cmd.aliases)}"
            )
        )
        reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
        await ctx.send(embed=reply)

#----------------------------------------------+
#                  Loading Cogs                |
#----------------------------------------------+
for file_name in os.listdir("./cogs"):
    if file_name.endswith(".py"):
        client.load_extension(f"cogs.{file_name[:-3]}")

# Running all the stuff
client.run(bot_token)