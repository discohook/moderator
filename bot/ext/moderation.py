import asyncio
import typing
from datetime import timedelta

import discord
from bot.utils import converter
from discord.ext import commands, tasks
from discord.utils import get


class Moderation(commands.Cog):
    """Commands related to the bot itself"""

    def __init__(self, bot):
        self.bot = bot
        self.auto_unsilence.start()
        super().__init__()

    @commands.command()
    @commands.has_guild_permissions(ban_members=True)
    async def ban(
        self,
        ctx: commands.Context,
        members: commands.Greedy[
            typing.Union[commands.MemberConverter, commands.UserConverter]
        ],
        *,
        reason: str,
    ):
        """Bans members for a given reason"""

        await asyncio.wait(
            [
                asyncio.create_task(
                    ctx.guild.ban(member, reason=f"[{ctx.author.id}]: {reason}")
                )
                for member in members
            ]
        )

        await ctx.message.add_reaction("\N{WHITE HEAVY CHECK MARK}")

    @commands.command()
    @commands.has_guild_permissions(ban_members=True)
    async def unban(
        self,
        ctx: commands.Context,
        members: commands.Greedy[commands.UserConverter],
        *,
        reason: str,
    ):
        """Unbans members for a given reason"""

        await asyncio.wait(
            [
                asyncio.create_task(
                    ctx.guild.unban(member, reason=f"[{ctx.author.id}]: {reason}")
                )
                for member in members
            ]
        )

        await ctx.message.add_reaction("\N{WHITE HEAVY CHECK MARK}")

    @commands.command()
    @commands.has_guild_permissions(kick_members=True)
    async def kick(
        self,
        ctx: commands.Context,
        members: commands.Greedy[commands.MemberConverter],
        *,
        reason: str,
    ):
        """Kicks members for a given reason"""

        await asyncio.wait(
            [
                asyncio.create_task(
                    ctx.guild.kick(member, reason=f"[{ctx.author.id}]: {reason}")
                )
                for member in members
            ]
        )

        await ctx.message.add_reaction("\N{WHITE HEAVY CHECK MARK}")

    @commands.command(aliases=["mute"])
    @commands.has_guild_permissions(manage_messages=True)
    async def silence(
        self,
        ctx: commands.Context,
        members: commands.Greedy[commands.MemberConverter],
        duration: converter.TimeDurationConverter,
        *,
        reason: str,
    ):
        """Silences members for a given reason"""

        role = await self.bot.get_cog("Roles").get_role(ctx.guild, "silence")
        if not role:
            await ctx.send(
                embed=discord.Embed(
                    title="Error",
                    description="No silence role configured",
                )
            )

        await asyncio.wait(
            [
                asyncio.create_task(
                    member.add_roles(role, reason=f"[{ctx.author.id}]: {reason}")
                )
                for member in members
            ]
        )

        await self.bot.db.executemany(
            """
            INSERT INTO moderator_action (guild_id, target_id, moderator_id, action_type, recorded_at, duration, reason)
            VALUES ($1, $2, $3, 'silence', NOW(), $4, $5)
            """,
            [
                (
                    ctx.guild.id,
                    member.id,
                    ctx.author.id,
                    int(duration.total_seconds()),
                    reason,
                )
                for member in members
            ],
        )

        for member in members:
            try:
                await member.send(
                    f"**You were silenced in {ctx.guild} by {ctx.author.mention} for {duration}**"
                    f"\n**Reason:** {reason}"
                )
            except discord.HTTPException:
                pass

            log_channel = await self.bot.get_cog("Logger").get_log_channel(
                ctx.guild, "moderator"
            )
            if log_channel:
                embed = discord.Embed(
                    description=f"**{member.mention} got silenced by {ctx.author.mention} for {duration}**"
                    f"\n**Reason:** {reason}"
                )
                embed.set_author(
                    name=f"{member} \N{BULLET} {member.id}",
                    url=f"https://discord.com/users/{member.id}",
                    icon_url=member.avatar_url,
                )

                await log_channel.send(embed=embed)

        await ctx.message.add_reaction("\N{WHITE HEAVY CHECK MARK}")

    @commands.command(aliases=["unmute"])
    @commands.has_guild_permissions(manage_messages=True)
    async def unsilence(
        self,
        ctx: commands.Context,
        members: commands.Greedy[commands.MemberConverter],
        *,
        reason: str,
    ):
        """Unsilences members for a given reason"""

        role = await self.bot.get_cog("Roles").get_role(ctx.guild, "silence")
        if not role:
            await ctx.send(
                embed=discord.Embed(
                    title="Error",
                    description="No silence role configured",
                )
            )

        await asyncio.wait(
            [
                asyncio.create_task(
                    member.remove_roles(role, reason=f"[{ctx.author.id}]: {reason}")
                )
                for member in members
            ]
        )

        await self.bot.db.executemany(
            """
            INSERT INTO moderator_action (guild_id, target_id, moderator_id, action_type, recorded_at, reason)
            VALUES ($1, $2, $3, 'unsilence', NOW(), $4)
            """,
            [
                (
                    ctx.guild.id,
                    member.id,
                    ctx.author.id,
                    reason,
                )
                for member in members
            ],
        )

        for member in members:
            try:
                await member.send(
                    f"**You were unsilenced in {ctx.guild} by {ctx.author.mention}**"
                    f"\n**Reason:** {reason}"
                )
            except discord.HTTPException:
                pass

            log_channel = await self.bot.get_cog("Logger").get_log_channel(
                ctx.guild, "moderator"
            )
            if log_channel:
                embed = discord.Embed(
                    description=f"**{member.mention} got unsilenced by {ctx.author.mention}**"
                    f"\n**Reason:** {reason}"
                )
                embed.set_author(
                    name=f"{member} \N{BULLET} {member.id}",
                    url=f"https://discord.com/users/{member.id}",
                    icon_url=member.avatar_url,
                )

            await log_channel.send(embed=embed)

        await ctx.message.add_reaction("\N{WHITE HEAVY CHECK MARK}")

    @commands.command()
    @commands.has_guild_permissions(manage_messages=True)
    async def warn(
        self,
        ctx: commands.Context,
        members: commands.Greedy[commands.MemberConverter],
        *,
        reason: str,
    ):
        """Warns members for a given reason"""

        await self.bot.db.executemany(
            """
            INSERT INTO moderator_action (guild_id, target_id, moderator_id, action_type, recorded_at, reason)
            VALUES ($1, $2, $3, 'warn', NOW(), $4)
            """,
            [
                (
                    ctx.guild.id,
                    member.id,
                    ctx.author.id,
                    reason,
                )
                for member in members
            ],
        )

        for member in members:
            try:
                await member.send(
                    f"**You were warned in {ctx.guild} by {ctx.author.mention}**"
                    f"\n**Reason:** {reason}"
                )
            except discord.HTTPException:
                pass

            log_channel = await self.bot.get_cog("Logger").get_log_channel(
                ctx.guild, "moderator"
            )
            if log_channel:
                embed = discord.Embed(
                    description=f"**{member.mention} got warned by {ctx.author.mention}**"
                    f"\n**Reason:** {reason}"
                )
                embed.set_author(
                    name=f"{member} \N{BULLET} {member.id}",
                    url=f"https://discord.com/users/{member.id}",
                    icon_url=member.avatar_url,
                )

                await log_channel.send(embed=embed)

        await ctx.message.add_reaction("\N{WHITE HEAVY CHECK MARK}")

    @tasks.loop(minutes=1)
    async def auto_unsilence(self):
        queue = await self.bot.db.fetch(
            """
            SELECT guild_id, target_id, duration FROM moderator_action
            WHERE action_type = 'silence'
            AND recorded_at > (
                SELECT recorded_at FROM moderator_action
                WHERE action_type = 'unsilence'
                AND moderator_action.target_id = target_id
                AND moderator_action.guild_id = guild_id
                ORDER BY recorded_at DESC
                LIMIT 1
            )
            AND recorded_at + duration * interval '1 second' < NOW()
            """,
        )

        for row in queue:
            guild = self.bot.get_guild(row["guild_id"])
            if not guild:
                continue

            member = guild.get_member(row["target_id"]) or self.bot.fetch_user(
                row["target_id"]
            )
            duration = timedelta(seconds=row["duration"])

            try:
                await member.send(
                    f"**You were automatically unsilenced after {duration} in {guild}**"
                )
            except discord.HTTPException:
                pass

            if isinstance(member, discord.Member):
                role = await self.bot.get_cog("Roles").get_role(guild, "silence")
                if role:
                    member.remove_roles(role, reason="Automatically unsilenced")

            await self.bot.db.execute(
                """
                INSERT INTO moderator_action (guild_id, target_id, moderator_id, action_type, recorded_at, reason)
                VALUES ($1, $2, $3, 'unsilence', NOW(), 'Automatically unsilenced')
                """,
                guild.id,
                member.id,
                self.bot.user.id,
            )

            log_channel = await self.bot.get_cog("Logger").get_log_channel(
                guild, "moderator"
            )
            if log_channel:
                embed = discord.Embed(
                    description=f"**{member.mention} got automatically unsilenced after {duration}**"
                )
                embed.set_author(
                    name=f"{member} \N{BULLET} {member.id}",
                    url=f"https://discord.com/users/{member.id}",
                    icon_url=member.avatar_url,
                )

            await log_channel.send(embed=embed)

    @auto_unsilence.before_loop
    async def before_auto_unsilence(self):
        await self.bot.wait_until_ready()


def setup(bot: commands.Bot):
    bot.add_cog(Moderation(bot))
