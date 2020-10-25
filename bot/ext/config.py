import asyncio
import collections
import re
from os import environ

import asyncpg
import discord
import lru
from discord.ext import commands
from discord.utils import get

Configurable = collections.namedtuple(
    "Configurable",
    "name description column required type",
)


configurables = [
    Configurable(
        name="prefix",
        description="Prefix specific to server, mention prefix will always work.",
        column="prefix",
        required=False,
        type=str,
    ),
    Configurable(
        name="member-logs",
        description="Location of logs for member actions.",
        column="member_log_channel_id",
        required=False,
        type=discord.TextChannel,
    ),
    Configurable(
        name="message-logs",
        description="Location of logs for message edits and deletes.",
        column="message_log_channel_id",
        required=False,
        type=discord.TextChannel,
    ),
    Configurable(
        name="moderator-logs",
        description="Location of logs for moderator actions.",
        column="moderator_log_channel_id",
        required=False,
        type=discord.TextChannel,
    ),
]


type_names = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    discord.TextChannel: "text channel",
}

enabled_values = ("yes", "y", "true", "t", "1", "enable", "on")
disabled_values = ("no", "n", "false", "f", "0", "disable", "off")


def resolve_value(expected_type, user_input: str, required=True):
    lowered = user_input.lower()

    if not required and lowered in disabled_values:
        return None

    if expected_type is bool:
        if lowered in enabled_values:
            return True
        elif lowered in disabled_values:
            return False
        else:
            raise RuntimeError(f"{user_input!r} can't be resolved to {expected_type}")

    try:
        if expected_type.__module__.startswith("discord."):
            if match := re.search(r"\d+", user_input):
                return int(match.group(0))
            else:
                raise RuntimeError(
                    f"{user_input!r} can't be resolved to {expected_type}"
                )
    except AttributeError:
        pass

    try:
        return expected_type(user_input)
    except:
        raise RuntimeError(f"{user_input!r} can't be resolved to {expected_type}")


class Config(commands.Cog):
    """State management for the bot"""

    def __init__(self, bot):
        self.bot = bot
        self.cache = lru.LRU(256)
        super().__init__()

    async def ensure(self, guild: discord.Guild):
        if guild.id in self.cache:
            return self.cache[guild.id]

        row = await self.bot.db.fetchrow(
            """
            SELECT * FROM guild_config
            WHERE guild_id = $1
            """,
            guild.id,
        )
        if row:
            self.cache[guild.id] = dict(row)
            return await self.ensure(guild)

        await self.bot.db.execute(
            """
            INSERT INTO guild_config (guild_id)
            VALUES ($1)
            ON CONFLICT DO NOTHING
            """,
            guild.id,
        )

        return await self.ensure(guild)

    async def get_value(
        self,
        guild: discord.Guild,
        configurable: Configurable,
    ):
        config = await self.ensure(guild)
        return config[configurable.column]

    async def set_value(
        self,
        guild: discord.Guild,
        configurable: Configurable,
        new_value,
    ):
        config = await self.ensure(guild)

        config[configurable.column] = new_value

        await self.bot.db.execute(
            f"""
            UPDATE guild_config
            SET {configurable.column} = $2
            WHERE guild_id = $1
            """,
            guild.id,
            new_value,
        )

    async def delete_data(self, guild: discord.Guild):
        await self.bot.db.execute(
            f"""
            DELETE FROM guild_config
            WHERE guild_id = $1
            """,
            guild.id,
        )

        del self.cache[guild.id]


def setup(bot: commands.Bot):
    config = Config(bot)
    bot.add_cog(config)
