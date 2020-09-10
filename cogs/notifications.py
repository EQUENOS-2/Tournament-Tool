import discord
from discord.ext import commands
from discord.ext.commands import Bot
import asyncio

#----------------------------------------------+
#                 Functions                    |
#----------------------------------------------+

class notifications(commands.Cog):
    def __init__(self, client):
        self.client = client

    #----------------------------------------------+
    #                   Events                     |
    #----------------------------------------------+
    @commands.Cog.listener()
    async def on_ready(self):
        print(f">> Notifications cog is loaded")

    #----------------------------------------------+
    #                  Commands                    |
    #----------------------------------------------+
    @commands.cooldown(1, 1, commands.BucketType.member)
    @commands.has_permissions(administrator=True)
    @commands.command(aliases=["tournaments-channel", "t-channel", "t-c", "tc"])
    async def tournaments_channel(self, ctx, *, tc: discord.TextChannel):
        pass


    #----------------------------------------------+
    #                   Errors                     |
    #----------------------------------------------+


def setup(client):
    client.add_cog(notifications(client))