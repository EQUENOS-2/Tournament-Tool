import discord
from discord.ext import commands
from discord.ext.commands import Bot
import asyncio
from pymongo import MongoClient
import os, random


db_token = str(os.environ.get("db_token"))
cluster = MongoClient(db_token)
db = cluster["tournament_tool_db"]
#----------------------------------------------+
#                 Functions                    |
#----------------------------------------------+
from functions import VoiceButton, VConfig, TemporaryVoices, antiformat as anf


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
            check1 = lambda vc: len(vc.members) < vc.user_limit and vconf.which_creates(vc.user_limit, vc.name) is not None
            check2 = lambda vc: vc.id in vconf.waiting_room_ids and len(vc.members) > 0
            # If left a voice channel
            if was_in is not None:
                if vconf.which_creates(was_in.user_limit, was_in.name) is not None:
                    # Deletes empty private room
                    if len(was_in.members) < 1:
                        try:
                            await was_in.delete()
                        except:
                            pass
                    # Checks waiting rooms
                    else:
                        category = was_in.category
                        if category is None:
                            category = member.guild
                        waiting_rooms = [vc for vc in category.voice_channels if check2(vc)]
                        if waiting_rooms != []:
                            # Moves someone to a private room
                            wr = waiting_rooms[0]
                            del waiting_rooms
                            if len(wr.members) > 0:
                                try:
                                    await wr.members[0].move_to(was_in)
                                except:
                                    pass
                # If left a custom room
                elif len(was_in.members) < 1:
                    temprooms = TemporaryVoices(member.guild.id)
                    owner_id = temprooms.get_owner(was_in.id)
                    if owner_id is not None:
                        try:
                            temprooms.remove_custom(owner_id, was_in.id)
                            await was_in.delete()
                        except:
                            pass
                    del temprooms

            # If joined a voice channel
            if now_in is not None:
                # Pressed a button
                button = vconf.get(now_in.id)
                if button is not None:
                    category = now_in.category
                    if category is None:
                        category = member.guild
                    try:
                        ovw = {member: discord.PermissionOverwrite(move_members=True)}
                        room = await category.create_voice_channel(name=button.name, user_limit=button.limit, overwrites=ovw)
                        await member.move_to(room)
                        # Also checking the queue and moving people
                        waiting_rooms = [vc for vc in category.voice_channels if check2(vc)]
                        broke = False
                        for wr in waiting_rooms:
                            if not broke:
                                for waiter in wr.members:
                                    if len(room.members) >= room.user_limit:
                                        broke = True
                                        break
                                    else:
                                        await waiter.move_to(room)
                            else:
                                break
                        del waiting_rooms
                    except:
                        pass
                # Entered a waiting room
                elif now_in.id in vconf.waiting_room_ids:
                    category = now_in.category
                    if category is None:
                        category = member.guild
                    available_vcs = [vc for vc in category.voice_channels if check1(vc)]
                    if len(available_vcs) > 0:
                        room = random.choice(available_vcs)
                        if len(room.members) < room.user_limit:
                            try:
                                await member.move_to(room)
                            except:
                                pass
                    
            del vconf


    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        if isinstance(channel, discord.VoiceChannel):
            vconf = VConfig(channel.guild.id)
            vconf.remove_button(channel.id)
            vconf.remove_waiting_room(channel.id)

            tv = TemporaryVoices(channel.guild.id)
            owner = tv.get_owner(channel.id)
            if owner is not None:
                tv.remove_custom(owner, channel.id)

    #----------------------------------------------+
    #                  Commands                    |
    #----------------------------------------------+
    @commands.cooldown(1, 1, commands.BucketType.member)
    @commands.command(
        help="создать свой приват",
        description="создаёт приват на указанное число людей. У создателя будут права на кик из войса и его переименование.",
        usage="Лимит-людей Название",
        brief="4 Комната профессионалов" )
    async def create(self, ctx, limit: int, *, name=None):
        isadm = ctx.author.guild_permissions.administrator
        channels = VConfig(ctx.guild.id).room_creation_channel_ids

        if ctx.channel.id not in channels and not isadm:
            pass
        else:
            if not (0 < limit < 100):
                reply = discord.Embed(
                    title="❌ | Неверный лимит",
                    description="Ограничение на кол-во пользователей в голосовом канале должно быть от `1` до `99`",
                    color=discord.Color.dark_red()
                )
                reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
                await ctx.send(embed=reply)
            
            else:
                temporooms = TemporaryVoices(ctx.guild.id, {f"custom_rooms.{ctx.author.id}": True})
                his_rooms = temporooms.custom_rooms.get(ctx.author.id, [])
                for i, room in enumerate(his_rooms):
                    if ctx.guild.get_channel(room) is None:
                        temporooms.remove_custom(ctx.author.id, room)
                        his_rooms.pop(i)
                        break
                
                if len(his_rooms) > 0 and not isadm:
                    reply = discord.Embed(
                        title="❌ | Превышен лимит",
                        description="Вы можете владеть только одной приватной комнатой.",
                        color=discord.Color.dark_red()
                    )
                    reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
                    await ctx.send(embed=reply)
                
                else:
                    if name is None:
                        name = f"Приват {ctx.author}"
                    vc = None
                    try:
                        category = ctx.channel.category
                        if category is None:
                            category = ctx.guild
                        ovw = {ctx.author: discord.PermissionOverwrite(move_members=True, manage_channels=True)}
                        vc = await category.create_voice_channel(name=name, user_limit=limit, overwrites=ovw)
                    except:
                        await ctx.send("💥 Похоже, у меня нет прав на создание голосовых каналов...")
                    if vc is not None:
                        temporooms.add_custom(ctx.author.id, vc.id)

                        reply = discord.Embed(
                            title="🔒 | Создана комната",
                            description=(
                                f"**Название:** {anf(vc.name)}\n"
                                f"**Лимит участников:** {limit}\n"
                                f"У Вас есть права на кик участников из войса и переименование канала."
                            ),
                            color=discord.Color.dark_green()
                        )
                        reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
                        await ctx.send(embed=reply)


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
        vconf = VConfig(ctx.guild.id, {"buttons": True})
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
    

    @commands.cooldown(1, 1, commands.BucketType.member)
    @commands.has_permissions(administrator=True)
    @commands.command(
        name="waiting-rooms",
        aliases=["waiting_rooms", "wrs"],
        help="просмотреть комнаты ожидания",
        description="отображает полный список комнат ожидания",
        usage="",
        brief="" )
    async def waitingrooms(self, ctx):
        vconf = VConfig(ctx.guild.id, {"waiting_room_ids": True})
        reply = discord.Embed(
            title="🔎 | Комнаты ожидания",
            description="Комнаты ожидания - это голосовые каналы, из которых участник перемещается в случайно выбранный приват.",
            color=discord.Color.magenta()
        )
        for wrid in vconf.waiting_room_ids:
            wr = ctx.guild.get_channel(wrid)
            try:
                reply.add_field(name=wr.name, value=f"> Перемещает в любой приват из категории **{anf(wr.category)}**", inline=False)
            except:
                pass
        if len(reply.fields) < 1:
            reply.description += "\n\nКомнат ожидания пока что нет."
        await ctx.send(embed=reply)
    

    @commands.cooldown(1, 1, commands.BucketType.member)
    @commands.has_permissions(administrator=True)
    @commands.command(
        aliases=["add-waiting-room", "awr", "addwaitingroom"],
        help="добавить комнату ожидания",
        description="создаёт комнату ожидания, из которой участники сервера будут случайно распределяться по приватам.",
        usage="",
        brief="" )
    async def add_waiting_room(self, ctx):
        vc = None
        try:
            ovw = {ctx.guild.default_role: discord.PermissionOverwrite(speak=False)}
            vc = await ctx.guild.create_voice_channel(f"🔎 Найти комнату", overwrites=ovw)
        except:
            await ctx.send("💥 Похоже, у меня нет прав на создание голосовых каналов...")
        if vc is not None:
            vconf = VConfig(ctx.guild.id, {"_id": True})
            vconf.add_waiting_room(vc.id)

            reply = discord.Embed(
                title="🔎 | Создана комната ожидания",
                description=(
                    f"На сервере появился голосовой канал {anf(vc.name)}, при входе в который участники будут "
                    f"случайно распределяться по приватным комнатам."
                ),
                color=discord.Color.dark_green()
            )
            reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
            await ctx.send(embed=reply)


    @commands.cooldown(1, 1, commands.BucketType.member)
    @commands.has_permissions(administrator=True)
    @commands.command(
        aliases=["allow-room-creation", "arc", "room-creation"],
        help="указать каналы для создания приватов при помощи команд",
        description="настраивает каналы, в которых участники смогут создавать приваты при помощи команд.",
        usage="#канал-1 #канал-2 ...",
        brief="#создание-приватов" )
    async def allow_room_creation(self, ctx, *, raw_channels):
        channels = []
        listed_trash = ""
        listed_channels = ""
        for raw in raw_channels.split()[:30]:
            try:
                channel = await commands.TextChannelConverter().convert(ctx, raw)
                channels.append(channel.id)
                listed_channels += f"> <#{channel.id}>\n"
            except:
                listed_trash += f"> {raw}\n"
        if len(channels) < 1:
            reply = discord.Embed(
                title="❌ | Неверно указаны каналы",
                description=f"Попробуйте тегнуть нужные каналы, напирмер <#{ctx.channel.id}>",
                color=discord.Color.dark_red()
            )
            reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
            await ctx.send(embed=reply)
        
        else:
            VConfig(ctx.guild.id, {"_id": True}).set_room_creation_channels(channels)

            if listed_trash != "":
                listed_channels += f"\nАргументы, не распознанные как каналы:\n{listed_trash}"
            reply = discord.Embed(
                title="🎧 | Перенастроены каналы для текстовой настройки",
                description=f"Список настроенных каналов:\n{listed_channels}",
                color=discord.Color.dark_green()
            )
            reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
            await ctx.send(embed=reply)


    #----------------------------------------------+
    #                   Errors                     |
    #----------------------------------------------+


def setup(client):
    client.add_cog(voices(client))