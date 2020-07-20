import re

import discord
from discord.ext import commands
from discord.utils import get


class Tags(commands.Cog):
    """Tag commands"""

    @commands.command(aliases=["t"])
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

        safe_tag = tag.replace("`", "\u200b`\u200b")

        await ctx.send(
            embed=discord.Embed(
                title="Not found",
                description=f"Could not find embed from {help_channel.mention} with tag ``{safe_tag}``.",
            )
        )


def setup(bot: commands.Bot):
    bot.add_cog(Tags(bot))
