import re
from os import environ

import aiohttp
import asyncpg
import discord
from discord.ext import commands
from discord.utils import get

from bot.ext import config
from bot.utils import wrap_in_code

initial_extensions = (
    "jishaku",
    "bot.ext.config",
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
            description="Cool moderation bot.",
            help_command=None,
            activity=discord.Activity(
                type=discord.ActivityType.watching, name="the server | @me help"
            ),
            allowed_mentions=discord.AllowedMentions.none(),
            intents=discord.Intents.all(),
            member_cache_flags=discord.MemberCacheFlags.all(),
            max_messages=None,
        )

        for extension in initial_extensions:
            self.load_extension(extension)

    async def get_prefix_list(self, bot, message):
        custom_prefix = await self.get_cog("Config").get_value(
            message.guild,
            get(config.configurables, name="prefix"),
        )

        prefixes = [
            f"<@!{bot.user.id}> ",
            f"<@{bot.user.id}> ",
        ]

        if custom_prefix:
            prefixes[len(prefixes) :] = [
                custom_prefix + " ",
                custom_prefix,
            ]

        return prefixes

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

        if message.guild:
            await self.get_cog("Config").get_value(
                message.guild, get(config.configurables, name="prefix")
            )

        if re.fullmatch(rf"<@!?{self.user.id}>", message.content):
            prefix = await self.get_cog("Config").get_value(
                message.guild,
                get(config.configurables, name="prefix"),
            )
            prefix_md = wrap_in_code(prefix) if prefix else self.user.mention

            await message.channel.send(
                embed=discord.Embed(
                    title="Prefix",
                    description=f"My prefix is {prefix_md}.",
                )
            )

        await self.process_commands(message)

    async def on_error(self, event, *args, **kwargs):
        errors = self.get_cog("Errors")
        if errors:
            await errors.on_error(event, *args, **kwargs)
