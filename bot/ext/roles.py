import re
from datetime import datetime, timedelta

import discord
from bot.ext import config
from discord.ext import commands, tasks
from discord.utils import get


class Roles(commands.Cog):
    """Autorole module"""

    def __init__(self, bot):
        self.bot = bot
        self.add_roles.start()
        super().__init__()

    def cog_unload(self):
        self.add_roles.cancel()
        return super().cog_unload()

    async def get_role(self, guild: discord.Guild, role_type: str):
        cfg = self.bot.get_cog("Config")
        configurable = get(config.configurables, name=f"{role_type}-role")
        role_id = await cfg.get_value(guild, configurable)
        return get(guild.roles, id=role_id)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, member: discord.Member):
        if member.pending or not before.pending:
            return

        join_role = await self.get_role(member.guild, "join")
        new_member_role = await self.get_role(member.guild, "new-member")
        silence_role = await self.get_role(member.guild, "silence")

        is_silenced = await self.bot.db.fetchval(
            """
            SELECT true FROM moderator_action s
            WHERE action_type = 'silence'
            AND target_id = $1
            AND recorded_at > (
                SELECT recorded_at FROM moderator_action u
                WHERE action_type = 'unsilence'
                AND s.target_id = u.target_id
                AND s.guild_id = u.guild_id
                UNION
                SELECT date '2015-01-01' AS recorded_at
                ORDER BY recorded_at DESC
                LIMIT 1
            )
            """,
            member.id,
        )

        await member.add_roles(
            *[
                role
                for role in {
                    join_role,
                    new_member_role,
                    silence_role if is_silenced else None,
                }
                if role
            ]
        )

    @tasks.loop(minutes=1)
    async def add_roles(self):
        active_silences = await self.bot.db.fetch(
            """
            SELECT guild_id, target_id FROM moderator_action s
            WHERE action_type = 'silence'
            AND recorded_at > (
                SELECT recorded_at FROM moderator_action u
                WHERE action_type = 'unsilence'
                AND s.target_id = u.target_id
                AND s.guild_id = u.guild_id
                UNION
                SELECT date '2015-01-01' AS recorded_at
                ORDER BY recorded_at DESC
                LIMIT 1
            )
            """
        )

        for guild in self.bot.guilds:
            if join_role := await self.get_role(guild, "join"):
                for member in guild.members:
                    if member.bot:
                        continue
                    if join_role.id in [role.id for role in member.roles]:
                        continue

                    await member.add_roles(join_role)

            if new_member_role := await self.get_role(guild, "new-member"):
                for member in guild.members:
                    if member.bot:
                        continue
                    if new_member_role.id not in [role.id for role in member.roles]:
                        continue
                    if member.joined_at > datetime.utcnow() - timedelta(minutes=15):
                        continue

                    await member.remove_roles(new_member_role)

            if silence_role := await self.get_role(guild, "silence"):
                for silence in active_silences:
                    if silence["guild_id"] == guild.id:
                        member = guild.get_member(silence["target_id"])
                        if member:
                            await member.add_roles(silence_role)

    @add_roles.before_loop
    async def before_add_roles(self):
        await self.bot.wait_until_ready()


def setup(bot: commands.Bot):
    bot.add_cog(Roles(bot))
