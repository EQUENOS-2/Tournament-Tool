import discord
from discord.ext import commands
from discord.ext.commands import Bot
import asyncio
import os, random

#----------------------------------------------+
#                 Functions                    |
#----------------------------------------------+
from functions import antiformat as anf, detect, TreatStorage, TreatUser, is_command
from custom_converters import IntConverter
from functions import EmergencyExit
what = str(os.environ.get("what"))
what2 = str(os.environ.get("what2"))
tale = str(os.environ.get("tale"))

def check(m):
    if m.guild is not None:
        return m.guild.id == 422784396425297930 and m.content in [what, what2]
    else:
        return False



class events(commands.Cog):
    def __init__(self, client):
        self.client = client

    #----------------------------------------------+
    #                   Events                     |
    #----------------------------------------------+
    @commands.Cog.listener()
    async def on_ready(self):
        print(f">> events cog is loaded")

    #----------------------------------------------+
    #                  Commands                    |
    #----------------------------------------------+
    @commands.cooldown(1, 1, commands.BucketType.member)
    @commands.has_permissions(administrator=True)
    @commands.command(
        help="найти числа в истории сообщений канала",
        description="находит подходящие числа в канале",
        brief="Правильные числа",
        usage="123 71" )
    async def find_numbers(self, ctx, channel_search, *, string):
        channel = detect.channel(ctx.guild, channel_search)
        nums = {int(w): [] for w in string.split() if w.isdigit()}

        if channel is None:
            reply = discord.Embed(
                title="💥 Ошибка",
                description=f"Неверно указан канал ({channel_search})",
                color=discord.Color.dark_red()
            )
            reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
            await ctx.send(embed=reply)

        elif len(nums) == 0:
            reply = discord.Embed(
                title="💥 Ошибка",
                description="В строке нет ни одного числа",
                color=discord.Color.dark_red()
            )
            reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
            await ctx.send(embed=reply)
        
        else:
            p_bar = await ctx.send(
                f"🕑 Собираю данные с канала <#{channel.id}>...\n"
                "Проверено сообщений: < 1000"
            )
            counter = 0

            async for message in channel.history(limit=100000):
                try:
                    counter += 1
                    text = message.content
                    if text != "":
                        num = text.split(maxsplit=1)[0]
                        if num.isdigit():
                            num = int(num)
                            if num in nums and str(message.author) not in nums[num]:
                                nums[num].append(str(message.author))
                    if counter % 1000 == 0:
                        await p_bar.edit(
                            content=("🕑 Собираю данные с канала...\n"
                            f"Проверено сообщений: > {counter}")
                        )
                except Exception:
                    pass
            if counter >= 100000:
                await ctx.send("Исчерпан лимит сообщений")
            
            reply = discord.Embed(
                titile="🏆 Победители",
                color=discord.Color.gold()
            )
            for num in nums:
                desc = ""
                winners = nums[num]
                if winners != []:
                    last = winners[len(winners) - 1]
                    title = f"🎁 **{num} угадано игроком {anf(last)}**"
                    winners = winners[:-1]
                    
                    if len(winners) > 0:
                        desc += f"> Остальные: "
                        for winner in winners:
                            desc += f"{anf(winner)}, "
                        desc = f"{desc[:-2]}"
                    else:
                        desc += "> Лол больше никто не угадал"
                    reply.add_field(name=title, value=desc[:256], inline=False)
            
            await ctx.send(embed=reply)


    @commands.cooldown(1, 1, commands.BucketType.member)
    @commands.has_permissions(administrator=True)
    @commands.command(
        help="начислить/отобрать конфеты",
        description="начисляет пользователю конфеты, если указано положительное число, и отбирает, если указано отрицательное.",
        brief="Количество Пользователь",
        usage="5 User#1234" )
    async def treat(self, ctx, amount: IntConverter, *, member: discord.Member=None):
        if member is None:
            member = ctx.author
        # Db manip
        TreatStorage(ctx.guild.id, request_data=False).add_treats(member.id, amount)
        # response
        if amount < 0:
            act = "Отобраны"
            amount = -amount
        else:
            act = "Добавлены"
        reply = discord.Embed(color=discord.Color.magenta())
        reply.title = f"🍬 | {anf(member)}"
        reply.description = f"{act} конфеты: **{amount}**"
        reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
        await ctx.send(embed=reply)


    @commands.cooldown(1, 1, commands.BucketType.member)
    @commands.command(
        aliases=["sweets"],
        help="сколько у тебя конфет",
        description="показывает, сколько у тебя конфет. Можно так же посмотреть чужие, упомянув участника.",
        brief="Пользователь (не обязательно)",
        usage="\nUser#1234" )
    async def treats(self, ctx, *, member: discord.Member=None):
        if member is None: member = ctx.author
        inv = TreatStorage(ctx.guild.id, {f"users.{member.id}": True}, {f"users.{member.id}": {"$exists": True}}).get_user(member.id)
        if inv is None: inv = TreatUser(member.id, 0)
        # Show
        col = random.choice([discord.Color.magenta(), discord.Color.purple(), discord.Color.red()])
        reply = discord.Embed(color=col)
        reply.title = f"🍬 | {anf(member)}"
        reply.description = f"**Конфет:** {inv.treats} 🍬"
        reply.set_thumbnail(url=member.avatar_url)
        reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
        await ctx.send(embed=reply)


    @commands.cooldown(1, 1, commands.BucketType.member)
    @commands.command(
        aliases=["top-sweets", "top-treats", "tt"],
        help="топ самых матёрых сладкоежек",
        description="таблица конфетных толстосумов",
        brief="Страница (по умолчанию 1)",
        usage="\n2" )
    async def top_treats(self, ctx, page: IntConverter=1):
        interv = 15
        ts = TreatStorage(ctx.guild.id)
        total_pages = 1
        if ts.user_count > 0: total_pages = (ts.user_count - 1) * interv + 1
        # Check page
        if not (0 < page <= total_pages):
            page = total_pages
        ts.__users = sorted(ts.users, reverse=True, key=lambda u: u.treats)
        lowerb = (page - 1) * interv
        upperb = min(ts.user_count, page * interv)
        desc = ""
        for i in range(lowerb, upperb):
            u = ts.__users[i]
            member = ctx.guild.get_member(u.id)
            if member is None: member = "[Данные удалены]"
            desc += f"`{i + 1}.` **{anf(member)}** | {u.treats} 🍬\n"
        reply = discord.Embed(color=discord.Color.magenta())
        reply.title = "👑 | Самые запасливые участники сервера"
        reply.description = desc
        reply.set_footer(text=f"Стр. {page}/{total_pages} | {ctx.author}", icon_url=ctx.author.avatar_url)
        await ctx.send(embed=reply)


    @commands.cooldown(1, 1, commands.BucketType.member)
    @commands.has_permissions(administrator=True)
    @commands.command(
        aliases=["reset-treats", "rt"],
        help="обнулить конфеты всех участников",
        description="как только используете - дороги назад не будет, у всех станет по 0 конфет.",
        brief="",
        usage="" )
    async def reset_treats(self, ctx):
        reply = discord.Embed()
        reply.title = "📝 | Подтверждение"
        reply.description = "Скажите, Вы уверены?\nНапишите `да` или `нет`"
        reply.set_footer(text=f"{ctx.author}", icon_url=ctx.author.avatar_url)
        await ctx.send(embed=reply)

        yes = ["y", "yes", "да"]
        no = ["n", "no", "нет"]
        def check(msg):
            if msg.channel.id != ctx.channel.id or msg.author.id != ctx.author.id:
                return False
            if msg.content.lower() in [*yes, *no]:
                return True
            if is_command(msg.content, ctx.prefix, self.client):
                raise EmergencyExit()
            return False
        
        try:
            msg = await self.client.wait_for("message", check=check, timeout=60)
        except asyncio.TimeoutError:
            await ctx.send(f"{ctx.author.mention}, Вы слишком долго не отвечали. Действие отменено.")
        else:
            yn = msg.content.lower()
            if yn in yes:
                TreatStorage(ctx.guild.id, request_data=False).reset()
                reply = discord.Embed(color=discord.Color.orange())
                reply.title = "🎃 | Топ обнулён"
                reply.description = "Ни у кого больше нет кофеток! Хах мда"
                reply.set_footer(text=f"{ctx.author}", icon_url=ctx.author.avatar_url)
                await ctx.send(embed=reply)
            else:
                reply = discord.Embed(color=discord.Color.blue())
                reply.title = "↩ | Действие отменено"
                reply.description = "Правильно, пусть сегодня они спят спокойно."
                reply.set_footer(text=f"{ctx.author}", icon_url=ctx.author.avatar_url)
                await ctx.send(embed=reply)

    #----------------------------------------------+
    #                   Errors                     |
    #----------------------------------------------+


def setup(client):
    client.add_cog(events(client))