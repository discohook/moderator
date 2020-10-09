import asyncio
import itertools
import re

import discord
from discord.ext import commands


class Meta(commands.Cog):
    """Commands related to the bot itself"""

    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    @commands.command()
    @commands.cooldown(3, 8, commands.BucketType.channel)
    async def about(self, ctx: commands.Context):
        """Gives information about this bot"""

        await ctx.send(
            embed=discord.Embed(title="About", description=self.bot.description)
        )

    @commands.command()
    @commands.cooldown(3, 8, commands.BucketType.channel)
    async def invite(self, ctx: commands.Context):
        """This bot is private"""

        await ctx.send(
            embed=discord.Embed(title="Invite", description="This bot is private")
        )


def setup(bot: commands.Bot):
    bot.add_cog(Meta(bot))
