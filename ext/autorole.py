import re

import discord
from discord.ext import commands, tasks
from discord.utils import get


class Autorole(commands.Cog):
    """Autorole module"""

    def __init__(self, bot):
        self.bot = bot
        self.add_roles.start()
        super().__init__()

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        autorole = get(member.guild.roles, name="Member")
        await member.add_roles(autorole)

    @tasks.loop(minutes=5.0)
    async def add_roles(self):
        for guild in self.bot.guilds:
            autorole = get(guild.roles, name="Member")

            for member in guild.members:
                if autorole.id not in [role.id for role in member.roles]:
                    await member.add_roles(autorole)

    @add_roles.before_loop
    async def before_add_roles(self):
        await self.bot.wait_until_ready()


def setup(bot: commands.Bot):
    bot.add_cog(Autorole(bot))
