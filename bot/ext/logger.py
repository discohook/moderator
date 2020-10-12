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

        if not content_data:
            await ctx.send(
                embed=discord.Embed(
                    title="Message history",
                    description="Not found",
                )
            )
            return

        channel = self.bot.get_channel(content_data["channel_id"])
        author = channel.guild.get_member(content_data["author_id"])

        embed = discord.Embed(
            title=f"Message {message_id}",
            url=f"https://discord.com/channels/{channel.guild.id}/{channel.id}/{message_id}",
            description=content_data["content"],
        )
        embed.set_author(
            name=f"{author} \N{BULLET} {author.id}",
            url=f"https://discord.com/users/{author.id}",
            icon_url=author.avatar_url,
        )

        await ctx.send(embed=embed)

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
                    int(event.data["author"]["id"]),
                )
                await conn.execute(
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
            name=f"{author} \N{BULLET} {author.id}",
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
            name=f"{author} \N{BULLET} {author.id}",
            url=f"https://discord.com/users/{author.id}",
            icon_url=author.avatar_url,
        )

        await get(channel.guild.channels, name="message-logs").send(embed=embed)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        await self.bot.db.execute(
            """
            INSERT INTO member_history (guild_id, member_id, version_at, tag, nick)
            VALUES ($1, $2, NOW(), $3, $4)
            """,
            member.guild.id,
            member.id,
            str(member),
            member.nick,
        )

        embed = discord.Embed(description=f"**{member.mention} joined**")
        embed.set_author(
            name=f"{member} \N{BULLET} {member.id}",
            url=f"https://discord.com/users/{member.id}",
            icon_url=member.avatar_url,
        )

        await get(member.guild.channels, name="member-logs").send(embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        await self.bot.db.execute(
            """
            INSERT INTO member_history (guild_id, member_id, version_at, tag, nick)
            VALUES ($1, $2, NOW(), NULL, NULL)
            """,
            member.guild.id,
            member.id,
        )

        embed = discord.Embed(description=f"**{member.mention} left**")
        embed.set_author(
            name=f"{member} \N{BULLET} {member.id}",
            url=f"https://discord.com/users/{member.id}",
            icon_url=member.avatar_url,
        )

        await get(member.guild.channels, name="member-logs").send(embed=embed)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if before.nick == after.nick:
            return

        await self.bot.db.execute(
            """
            INSERT INTO member_history (guild_id, member_id, version_at, tag, nick)
            VALUES ($1, $2, NOW(), $3, $4)
            """,
            after.guild.id,
            after.id,
            str(after),
            after.nick,
        )

        embed = discord.Embed(
            description=f"**{after.mention} changed nickname**"
            f"\n{escape(before.nick) if before.nick else '*none*'}"
            " \N{RIGHTWARDS ARROW}"
            f" {escape(after.nick) if after.nick else '*none*'}"
        )
        embed.set_author(
            name=f"{after} \N{BULLET} {after.id}",
            url=f"https://discord.com/users/{after.id}",
            icon_url=after.avatar_url,
        )

        await get(after.guild.channels, name="member-logs").send(embed=embed)

    @commands.Cog.listener()
    async def on_user_update(self, before, after):
        if str(before) == str(after):
            return

        args = []
        for guild in self.bot.guilds:
            member = guild.get_member(after.id)
            if not member:
                continue

            args.append((guild.id, after.id, str(after), member.nick))

        await self.bot.db.executemany(
            """
            INSERT INTO member_history (guild_id, member_id, version_at, tag, nick)
            VALUES ($1, $2, NOW(), $3, $4)
            """,
            args,
        )


def setup(bot: commands.Bot):
    bot.add_cog(Logger(bot))
