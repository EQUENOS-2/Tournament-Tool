import discord
from discord.ext import commands
from discord.ext.commands import Bot
import asyncio
from pymongo import MongoClient
import os


db_token = str(os.environ.get("db_token"))
cluster = MongoClient(db_token)
db = cluster["tournament_tool_db"]
#----------------------------------------------+
#                 Functions                    |
#----------------------------------------------+
from functions import VoiceButton, VConfig, antiformat as anf


class voices(commands.Cog):
    def __init__(self, client):
        self.client = client

    #----------------------------------------------+
    #                   Events                     |
    #----------------------------------------------+
    @commands.Cog.listener()
    async def on_ready(self):
        print(f">> Voices cog is loaded")


    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        was_in = before.channel
        now_in = after.channel
        if was_in is not None or now_in is not None:
            vconf = VConfig(member.guild.id)
            # Checks if user left an empty private room
            if was_in is not None:
                if len(was_in.members) < 1 and vconf.which_creates(was_in.user_limit, was_in.name) is not None:
                    try:
                        await was_in.delete()
                    except:
                        pass
            # Tries to create a private room in a relevant category
            if now_in is not None:
                button = vconf.get(now_in.id)
                if button is not None:
                    category = now_in.category
                    if category is None:
                        category = member.guild
                    try:
                        room = await category.create_voice_channel(name=button.name, user_limit=button.limit)
                        await member.move_to(room)
                    except:
                        pass
            del vconf


    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        if isinstance(channel, discord.VoiceChannel):
            vconf = VConfig(channel.guild.id)
            vconf.remove_button(channel.id)

    #----------------------------------------------+
    #                  Commands                    |
    #----------------------------------------------+
    @commands.cooldown(1, 1, commands.BucketType.member)
    @commands.has_permissions(administrator=True)
    @commands.command(
        aliases=["voice-button", "vb", "voicebutton"],
        help="конвейер приватных голосовых каналов",
        description="создаёт канал-кнопку, при нажатии на которую будут создаваться приватные голосовые каналы.",
        usage="Лимит-людей Название приватов",
        brief="4 Комната на четверых" )
    async def voice_button(self, ctx, limit: int, *, name):
        if not (0 < limit < 100):
            reply = discord.Embed(
                title="❌ | Неверный лимит",
                description="Ограничение на кол-во пользователей в голосовом канале должно быть от `1` до `99`",
                color=discord.Color.dark_red()
            )
            reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
            await ctx.send(embed=reply)
        
        else:
            vc = None
            try:
                vc = await ctx.guild.create_voice_channel(f"[➕] Создать {name}")
            except:
                await ctx.send("💥 Похоже, у меня нет прав на создание голосовых каналов...")
            if vc is not None:
                vconf = VConfig(ctx.guild.id, {"buttons": False})
                vconf.add_button(vc.id, limit, name)

                reply = discord.Embed(
                    title="\\➕ | Создан канал-кнопка",
                    description=(
                        f"На сервере появился голосовой канал {anf(vc.name)}, при входе в который участники будут создавать "
                        f"приваты для `{limit}` человек, под названием {anf(name)}."
                    ),
                    color=discord.Color.dark_green()
                )
                reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
                await ctx.send(embed=reply)


    @commands.cooldown(1, 1, commands.BucketType.member)
    @commands.has_permissions(administrator=True)
    @commands.command(
        aliases=["voice-buttons", "vbs", "voicebuttons"],
        help="просмотреть каналы-кнопки",
        description="отображает полный список настроенных каналов-кнопок",
        usage="",
        brief="" )
    async def voice_buttons(self, ctx):
        vconf = VConfig(ctx.guild.id)
        reply = discord.Embed(
            title="🔊 | Каналы-кнопки сервера",
            description="Каналы-кнопки - это голосовые каналы, при нажатии на которые участник создаёт приватный войс.",
            color=discord.Color.magenta()
        )
        for button in vconf.buttons:
            name = ctx.guild.get_channel(button.id).name
            try:
                reply.add_field(name=name, value=f"> Создаёт канал **{anf(button.name)}** на **{button.limit}** человек", inline=False)
            except:
                pass
        if len(reply.fields) < 1:
            reply.description += "\n\nКаналов-кнопок пока что нет."
        await ctx.send(embed=reply)
        

    #----------------------------------------------+
    #                   Errors                     |
    #----------------------------------------------+


def setup(client):
    client.add_cog(voices(client))