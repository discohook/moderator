import re
from datetime import datetime, timedelta

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
        restricted = get(member.guild.roles, name="Restricted")

        await member.add_roles(autorole, restricted)

    @tasks.loop(minutes=1)
    async def add_roles(self):
        for guild in self.bot.guilds:
            autorole = get(guild.roles, name="Member")

            for member in guild.members:
                if member.bot:
                    continue
                if autorole.id in [role.id for role in member.roles]:
                    continue

                await member.add_roles(autorole)

            restricted = get(guild.roles, name="Restricted")

            for member in guild.members:
                if member.bot:
                    continue
                if restricted.id not in [role.id for role in member.roles]:
                    continue
                if member.joined_at > datetime.utcnow() - timedelta(minutes=15):
                    continue

                await member.remove_roles(restricted)

    @add_roles.before_loop
    async def before_add_roles(self):
        await self.bot.wait_until_ready()


def setup(bot: commands.Bot):
    bot.add_cog(Autorole(bot))
