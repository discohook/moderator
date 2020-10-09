import re

import discord
from bot.utils import wrap_in_code
from discord.ext import commands
from discord.utils import get


class Support(commands.Cog):
    """Support specific commands"""

    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    @commands.command(aliases=["t"])
    @commands.cooldown(1, 3, type=commands.BucketType.channel)
    @commands.guild_only()
    async def tag(self, ctx: commands.Context, *, tag: str):
        """Posts an embed from the help channel"""

        help_channel = get(ctx.guild.channels, name="help")
        if not help_channel:
            return

        async for message in help_channel.history(limit=50):
            for embed in message.embeds:
                if (
                    embed.footer is discord.Embed.Empty
                    or embed.footer.text is discord.Embed.Empty
                ):
                    continue

                tags = embed.footer.text.replace("Tags: ", "", 1).split(", ")

                if tag not in tags:
                    continue

                await ctx.send(embed=embed)
                return

        raise commands.BadArgument(f"Tag {wrap_in_code(tag)} not found.")


def setup(bot: commands.Bot):
    bot.add_cog(Support(bot))
