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


class voices(commands.Cog):
    def __init__(self, client):
        self.client = client

    #----------------------------------------------+
    #                   Events                     |
    #----------------------------------------------+
    @commands.Cog.listener()
    async def on_ready(self):
        print(f">> Voices cog is loaded")

    #----------------------------------------------+
    #                  Commands                    |
    #----------------------------------------------+
    @commands.cooldown(1, 1, commands.BucketType.member)
    @commands.has_permissions(administrator=True)
    @commands.command(
        aliases=["x4-voice-button", "4-voice-button", "4voice-button"],
        help="coming soon" )
    async def x4_voice_button(self, ctx, *, vc: discord.VoiceChannel):
        pass


    #----------------------------------------------+
    #                   Errors                     |
    #----------------------------------------------+


def setup(client):
    client.add_cog(voices(client))