import collections
import difflib
import re
from datetime import datetime

import discord
from bot.utils import cut_words, diff_message, escape
from discord.ext import commands
from discord.utils import get

LogType = collections.namedtuple("LogType", "emoji channel")

log_types = {
    "member_join": LogType("\N{RIGHTWARDS BLACK ARROW}", "member-logs"),
    "member_leave": LogType("\N{LEFTWARDS BLACK ARROW}", "member-logs"),
}


class Logger(commands.Cog):
    """Magic logging module"""

    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    async def write_log(
        self,
        ctx: commands.Context,
        log_type: LogType,
        text: str,
        *,
        fields,
    ):
        log_channel = get(ctx.guild.channels, name=log_type.channel)

        embed = discord.Embed(description=f"{log_type.emoji} \u200b \u200b {text}")
        for field in fields:
            embed.add_field(**field)

        await log_channel.send(embed=embed)

    @commands.group(invoke_without_command=True, aliases=["hist"])
    @commands.has_guild_permissions(manage_messages=True)
    async def history(self, ctx: commands.Context):
        """Group of commands to browse message history"""
        await ctx.send_help("history")

    @history.command(name="get")
    @commands.has_guild_permissions(manage_messages=True)
    async def history_get(
        self,
        ctx: commands.Context,
        message_id: int,
        version: int = 0,
    ):
        """Gets a message by its ID and it's version

        Versions start at zero, each indexed edit adds one
        """

        content_data = await self.bot.db.fetchrow(
            """
            SELECT message_history.content, message_metadata.* FROM message_history
            JOIN message_metadata ON (message_metadata.message_id = message_history.message_id)
            WHERE message_history.message_id = $1
            ORDER BY version_at
            LIMIT 1 OFFSET $2
            """,
            message_id,
            version,
        )

        channel = self.bot.get_channel(content_data["channel_id"])
        author = channel.guild.get_member(content_data["author_id"])

        embed = discord.Embed(
            title=f"Message {message_id}",
            url=f"https://discord.com/channels/{channel.guild.id}/{channel.id}/{message_id}",
            description=content_data["content"],
        )
        embed.set_author(
            name=f"{author} \N{BULLET} ({author.id})",
            url=f"https://discord.com/users/{author.id}",
            icon_url=author.avatar_url,
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        async with self.bot.db.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    INSERT INTO message_metadata (message_id, channel_id, guild_id, author_id)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT DO NOTHING
                    """,
                    message.id,
                    message.channel.id,
                    message.guild.id,
                    message.author.id,
                )
                await conn.execute(
                    """
                    INSERT INTO message_history (message_id, version_at, content)
                    VALUES ($1, $2, $3)
                    """,
                    message.id,
                    message.created_at,
                    message.content,
                )

    @commands.Cog.listener()
    async def on_raw_message_edit(self, event: discord.RawMessageUpdateEvent):
        if (
            "content" not in event.data
            or "guild_id" not in event.data
            or "webhook_id" in event.data
        ):
            return

        version_at = datetime.strptime(
            event.data["edited_timestamp"], "%Y-%m-%dT%H:%M:%S.%f%z"
        ).replace(tzinfo=None)

        async with self.bot.db.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    INSERT INTO message_metadata (message_id, channel_id, guild_id, author_id)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT DO NOTHING
                    """,
                    event.message_id,
                    event.channel_id,
                    int(event.data["guild_id"]),
                    int(event.data["user"]["id"]),
                )
                await self.bot.db.execute(
                    """
                    INSERT INTO message_history (message_id, version_at, content)
                    VALUES ($1, $2, $3)
                    """,
                    event.message_id,
                    version_at,
                    event.data["content"],
                )

        old_content = await self.bot.db.fetchval(
            """
            SELECT content FROM message_history
            WHERE message_id = $1 AND version_at < $2
            ORDER BY version_at DESC
            LIMIT 1
            """,
            event.message_id,
            version_at,
        )

        channel = self.bot.get_channel(event.channel_id)
        author = channel.guild.get_member(int(event.data["author"]["id"]))

        jump_url = f"https://discord.com/channels/{channel.guild.id}/{channel.id}/{event.message_id}"
        embed = discord.Embed(
            description=f"{author.mention} edited [`{event.message_id}`]({jump_url})"
            f" in <#{event.channel_id}>"
            f"\n{diff_message(old_content, event.data['content'], max_len=250)}"
        )
        embed.set_author(
            name=f"{author} \N{BULLET} ({author.id})",
            url=f"https://discord.com/users/{author.id}",
            icon_url=author.avatar_url,
        )

        await get(channel.guild.channels, name="message-logs").send(embed=embed)

    @commands.Cog.listener()
    async def on_raw_message_delete(self, event: discord.RawMessageDeleteEvent):
        stored_data = await self.bot.db.fetchrow(
            """
            SELECT message_history.content, message_metadata.author_id FROM message_history
            JOIN message_metadata ON (message_metadata.message_id = message_history.message_id)
            WHERE message_history.message_id = $1
            ORDER BY version_at DESC
            LIMIT 1
            """,
            event.message_id,
        )

        if not stored_data:
            return

        channel = self.bot.get_channel(event.channel_id)
        author = channel.guild.get_member(stored_data["author_id"])

        embed = discord.Embed(
            description=f"{author.mention} deleted `{event.message_id}`"
            f" in <#{event.channel_id}>"
            f"\n{cut_words(escape(stored_data['content']), max_len=250, end=' **... [cut off]**')}"
        )
        embed.set_author(
            name=f"{author} \N{BULLET} ({author.id})",
            url=f"https://discord.com/users/{author.id}",
            icon_url=author.avatar_url,
        )

        await get(channel.guild.channels, name="message-logs").send(embed=embed)


def setup(bot: commands.Bot):
    bot.add_cog(Logger(bot))
