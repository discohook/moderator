import collections
import difflib
import re
from datetime import datetime, timedelta

import discord
from bot.ext import config
from bot.utils import cut_words, diff_message, escape
from discord.ext import commands
from discord.utils import get


class Logger(commands.Cog):
    """Magic logging module"""

    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    async def get_log_channel(self, guild: discord.Guild, log_type: str):
        cfg = self.bot.get_cog("Config")
        configurable = get(config.configurables, name=f"{log_type}-logs")
        channel_id = await cfg.get_value(guild, configurable)
        return get(guild.channels, id=channel_id)

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

        Versions start at zero, each indexed edit adds one.
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
        if not author:
            author = await self.bot.fetch_user(content_data["author_id"])

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

    @history.command(name="difference", aliases=["diff"])
    @commands.has_guild_permissions(manage_messages=True)
    async def history_difference(
        self,
        ctx: commands.Context,
        message_id: int,
        old_version: int = 0,
        new_version: int = -1,
    ):
        """Gets the difference between 2 message versions for a message by its ID and 2 versions

        Versions start at zero, each indexed edit adds one.
        The new version parameter accepts magic value -1 as last message, other negative numbers are not supported.
        """

        old_data = await self.bot.db.fetchrow(
            """
            SELECT message_history.content, message_metadata.* FROM message_history
            JOIN message_metadata ON (message_metadata.message_id = message_history.message_id)
            WHERE message_history.message_id = $1
            ORDER BY version_at
            LIMIT 1 OFFSET $2
            """,
            message_id,
            old_version,
        )

        new_content = ""
        if new_version == -1:
            new_content = await self.bot.db.fetchval(
                """
                SELECT content FROM message_history
                WHERE message_id = $1
                ORDER BY version_at DESC
                LIMIT 1
                """,
                message_id,
            )
        else:
            new_content = await self.bot.db.fetchval(
                """
                SELECT content FROM message_history
                WHERE message_id = $1
                ORDER BY version_at
                LIMIT 1 OFFSET $2
                """,
                message_id,
                new_version,
            )

        if not old_data or not new_content:
            await ctx.send(
                embed=discord.Embed(
                    title="Message history",
                    description="Not found",
                )
            )
            return

        channel = self.bot.get_channel(old_data["channel_id"])
        author = channel.guild.get_member(old_data["author_id"])
        if not author:
            author = await self.bot.fetch_user(old_data["author_id"])

        embed = discord.Embed(
            title=f"Message {message_id}",
            url=f"https://discord.com/channels/{channel.guild.id}/{channel.id}/{message_id}",
            description=diff_message(old_data["content"], new_content),
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
            event.data.get("webhook_id", None)
            or not event.data.get("content", None)
            or not event.data.get("guild_id", None)
            or not event.data.get("edited_timestamp", None)
        ):
            return

        old_content = await self.bot.db.fetchval(
            """
            SELECT content FROM message_history
            WHERE message_id = $1
            ORDER BY version_at DESC
            LIMIT 1
            """,
            event.message_id,
        )

        if not old_content or old_content == event.data["content"]:
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

        channel = self.bot.get_channel(event.channel_id)
        log_channel = await self.get_log_channel(channel.guild, "message")
        if log_channel:
            author = channel.guild.get_member(int(event.data["author"]["id"]))
            if not author:
                author = await self.bot.fetch_user(int(event.data["author"]["id"]))

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

            await log_channel.send(embed=embed)

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
        log_channel = await self.get_log_channel(channel.guild, "message")
        if log_channel:
            author = channel.guild.get_member(stored_data["author_id"])
            if not author:
                author = await self.bot.fetch_user(stored_data["author_id"])

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

            await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        await self.bot.db.execute(
            """
            INSERT INTO member_history (guild_id, member_id, version_at, tag, nick)
            VALUES ($1, $2, $3, $4, $5)
            """,
            member.guild.id,
            member.id,
            member.joined_at,
            str(member),
            member.nick,
        )

        log_channel = await self.get_log_channel(member.guild, "member")
        if log_channel:
            embed = discord.Embed(description=f"**{member.mention} joined**")
            embed.set_author(
                name=f"{member} \N{BULLET} {member.id}",
                url=f"https://discord.com/users/{member.id}",
                icon_url=member.avatar_url,
            )

            await log_channel.send(embed=embed)

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

        async for log in member.guild.audit_logs(action=discord.AuditLogAction.kick):
            if log.created_at < member.joined_at:
                break
            if log.target.id != member.id:
                continue

            moderator = log.user
            reason = log.reason

            if member.id == self.bot.user.id:
                match = re.match(r"^[(\d+)]: (.+)$", reason)
                if match:
                    moderator = member.get_member(int(match.group(1)))
                    reason = match.group(2)

            await self.bot.db.execute(
                """
                INSERT INTO moderator_action (guild_id, target_id, moderator_id, action_type, recorded_at, reason)
                VALUES ($1, $2, $3, $4, NOW(), $5)
                """,
                member.guild.id,
                log.target.id,
                moderator.id,
                "kick",
                reason,
            )

            log_channel = await self.get_log_channel(member.guild, "moderator")
            if log_channel:
                embed = discord.Embed(
                    description=f"**{member.mention} got kicked by {moderator.mention}**"
                    f"\n**Reason:** {reason}"
                )
                embed.set_author(
                    name=f"{member} \N{BULLET} {member.id}",
                    url=f"https://discord.com/users/{member.id}",
                    icon_url=member.avatar_url,
                )

                await log_channel.send(embed=embed)

            break

        log_channel = await self.get_log_channel(member.guild, "member")
        if log_channel:
            embed = discord.Embed(description=f"**{member.mention} left**")
            embed.set_author(
                name=f"{member} \N{BULLET} {member.id}",
                url=f"https://discord.com/users/{member.id}",
                icon_url=member.avatar_url,
            )

            await log_channel.send(embed=embed)

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

        log_channel = await self.get_log_channel(after.guild, "member")
        if log_channel:
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

            await log_channel.send(embed=embed)

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

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        max_created_at = (
            user.joined_at
            if isinstance(user, discord.Member)
            else datetime.utcnow() - timedelta(minutes=5)
        )

        async for log in guild.audit_logs(action=discord.AuditLogAction.ban):
            if log.created_at < max_created_at:
                break
            if log.target.id != user.id:
                continue

            moderator = log.user
            reason = log.reason

            if moderator.id == self.bot.user.id:
                match = re.match(r"^\[(\d+)]: (.+)$", reason)
                if match:
                    moderator = guild.get_member(int(match.group(1)))
                    reason = match.group(2)

            await self.bot.db.execute(
                """
                INSERT INTO moderator_action (guild_id, target_id, moderator_id, action_type, recorded_at, reason)
                VALUES ($1, $2, $3, $4, NOW(), $5)
                """,
                guild.id,
                log.target.id,
                moderator.id,
                "ban",
                reason,
            )

            log_channel = await self.get_log_channel(guild, "moderator")
            if log_channel:
                embed = discord.Embed(
                    description=f"**{user.mention} got banned by {moderator.mention}**"
                    f"\n**Reason:** {reason}"
                )
                embed.set_author(
                    name=f"{user} \N{BULLET} {user.id}",
                    url=f"https://discord.com/users/{user.id}",
                    icon_url=user.avatar_url,
                )

                await log_channel.send(embed=embed)

            break

    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        async for log in guild.audit_logs(action=discord.AuditLogAction.unban):
            if log.created_at < datetime.utcnow() - timedelta(minutes=5):
                break
            if log.target.id != user.id:
                continue

            moderator = log.user
            reason = log.reason

            if moderator.id == self.bot.user.id:
                match = re.match(r"^\[(\d+)]: (.+)$", reason)
                if match:
                    moderator = guild.get_member(int(match.group(1)))
                    reason = match.group(2)

            await self.bot.db.execute(
                """
                INSERT INTO moderator_action (guild_id, target_id, moderator_id, action_type, recorded_at, reason)
                VALUES ($1, $2, $3, $4, NOW(), $5)
                """,
                guild.id,
                log.target.id,
                moderator.id,
                "unban",
                log.reason,
            )

            log_channel = await self.get_log_channel(guild, "moderator")
            if log_channel:
                embed = discord.Embed(
                    description=f"**{user.mention} got unbanned by {moderator.mention}**"
                    f"\n**Reason:** {reason}"
                )
                embed.set_author(
                    name=f"{user} \N{BULLET} {user.id}",
                    url=f"https://discord.com/users/{user.id}",
                    icon_url=user.avatar_url,
                )

                await log_channel.send(embed=embed)

            break


def setup(bot: commands.Bot):
    bot.add_cog(Logger(bot))
