import discord
from discord.ext import commands
from discord.ext.commands import Bot
import asyncio
import os

#----------------------------------------------+
#                 Functions                    |
#----------------------------------------------+
from functions import antiformat as anf, detect
what = str(os.environ.get("what"))
tale = str(os.environ.get("tale"))

def check(m):
    return m.guild.id == 422784396425297930 and m.content == what


class events(commands.Cog):
    def __init__(self, client):
        self.client = client

    #----------------------------------------------+
    #                   Events                     |
    #----------------------------------------------+
    @commands.Cog.listener()
    async def on_ready(self):
        print(f">> events cog is loaded")
    

    @commands.Cog.listener()
    async def on_message(self, message):
        if check(message):
            await message.channel.send(tale)

    #----------------------------------------------+
    #                  Commands                    |
    #----------------------------------------------+
    @commands.cooldown(1, 1, commands.BucketType.member)
    @commands.has_permissions(administrator=True)
    @commands.command(help="находит подходящие числа в канале", brief="Правильные числа", usage="123 71")
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
            if counter >= 100000:
                await ctx.send("Исчерпан лимит сообщений")
            
            desc = ""
            for num in nums:
                winners = nums[num]
                if winners != []:
                    last = winners[len(winners) - 1]
                    winners = winners[:-1]
                    desc += f"🎁 **{num} угадано игроком {anf(last)}**\n"
                    if len(winners) > 0:
                        desc += f"> Остальные: "
                        for winner in winners:
                            desc += f"{anf(winner)}, "
                        desc = f"{desc[:-2]}\n\n"
                    else:
                        desc += "\n"
            if desc == "":
                desc = "Ни одно число не угадано"
            
            reply = discord.Embed(
                titile="🏆 Победители",
                description=desc,
                color=discord.Color.gold()
            )
            await ctx.send(embed=reply)


    #----------------------------------------------+
    #                   Errors                     |
    #----------------------------------------------+


def setup(client):
    client.add_cog(events(client))
