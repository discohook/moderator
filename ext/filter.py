import re

import discord
from discord.ext import commands
from discord.utils import get

message_filters = [
    (
        re.compile(r"discord[.\s]?gg|discord(?:app)?.com\/invite"),
        "Remove invites from your message",
    ),
    (
        re.compile(r"discord(?:app)?\.com\/api\/webhooks\/\d+\/[\w-]+"),
        "Don't share your webhook URL! They can be abused by anyone to spam your server.",
    ),
]


class Filter(commands.Cog):
    """Message filter"""

    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    async def filter(self, message: discord.Message):
        if message.channel.permissions_for(message.author).manage_messages:
            return

        for (pattern, error) in message_filters:
            if pattern.search(message.content):
                await message.delete()
                await message.channel.send(
                    embed=discord.Embed(title="Message filter", description=error),
                    delete_after=5.0,
                )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        await self.filter(message)

    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload: discord.RawMessageUpdateEvent):
        channel = self.bot.get_channel(payload.channel_id)
        if not channel:
            channel = await self.bot.fetch_channel(payload.channel_id)

        message = await channel.fetch_message(payload.message_id)
        await self.filter(message)


def setup(bot: commands.Bot):
    bot.add_cog(Filter(bot))
