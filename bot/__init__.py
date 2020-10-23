import re
from os import environ

import aiohttp
import asyncpg
import discord
from discord.ext import commands
from discord.utils import get

initial_extensions = (
    "jishaku",
    "bot.ext.errors",
    "bot.ext.meta",
    "bot.ext.help",
    "bot.ext.logger",
    "bot.ext.moderation",
    "bot.ext.filter",
    "bot.ext.roles",
    "bot.ext.support",
)


class Bot(commands.AutoShardedBot):
    def __init__(self):
        super().__init__(
            command_prefix=self.get_prefix_list,
            description="Discohook's private moderation bot.",
            help_command=None,
            activity=discord.Activity(
                type=discord.ActivityType.watching, name="the server | m.help"
            ),
            allowed_mentions=discord.AllowedMentions.none(),
            intents=discord.Intents.all(),
            member_cache_flags=discord.MemberCacheFlags.all(),
            max_messages=None,
        )

        for extension in initial_extensions:
            self.load_extension(extension)

    def get_prefix_list(self, bot, message):
        return (
            f"<@!{bot.user.id}> ",
            f"<@{bot.user.id}> ",
            "m. ",
            "m.",
        )

    async def start(self, *args, **kwargs):
        self.session = aiohttp.ClientSession()
        self.db = await asyncpg.create_pool(environ.get("DATABASE_DSN"))
        await super().start(*args, **kwargs)

    async def close(self):
        await self.session.close()
        await super().close()

    async def on_ready(self):
        print(f"Ready as {self.user} ({self.user.id})")

    async def on_message(self, message):
        if message.author.bot:
            return

        if re.fullmatch(rf"<@!?{self.user.id}>", message.content):
            await message.channel.send(
                embed=discord.Embed(title="Prefix", description="My prefix is `m.`")
            )

        await self.process_commands(message)

    async def on_error(self, event, *args, **kwargs):
        errors = self.get_cog("Errors")
        if errors:
            await errors.on_error(event, *args, **kwargs)
