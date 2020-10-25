import asyncio
import itertools
import re
import typing

import discord
from bot.ext import config
from bot.utils import paginators, wrap_in_code
from discord.ext import commands
from discord.utils import get


class Meta(commands.Cog):
    """Commands related to the bot itself"""

    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    @commands.command(invoke_without_command=True)
    @commands.cooldown(3, 8, commands.BucketType.channel)
    @commands.guild_only()
    async def config(
        self,
        ctx: commands.Context,
        option: typing.Optional[str],
        *,
        new_value: typing.Optional[str],
    ):
        """Manages server configuration for bot"""

        command = f"{ctx.prefix}{self.config.qualified_name}"

        if option:
            configurable = get(config.configurables, name=option.lower())
            if configurable is None:
                raise commands.UserInputError(
                    f"Option {wrap_in_code(option)} not found"
                )

            if new_value:
                await commands.has_guild_permissions(manage_guild=True).predicate(ctx)

                try:
                    parsed_value = config.resolve_value(
                        configurable.type, new_value, configurable.required
                    )

                    await self.bot.get_cog("Config").set_value(
                        ctx.guild, configurable, parsed_value
                    )
                except:
                    raise commands.BadArgument(
                        f"Value {wrap_in_code(new_value)} is does not fit"
                        f" expected type {config.type_names[configurable.type]}"
                    )

            value = (
                parsed_value
                if new_value is not None
                else await self.bot.get_cog("Config").get_value(ctx.guild, configurable)
            )
            if value is None:
                value = "*disabled*"
            elif isinstance(value, bool):
                value = "`yes`" if value else "`no`"
            elif configurable.type is discord.TextChannel:
                value = f"<#{value}>"
            else:
                value = wrap_in_code(str(value))

            set_configurable_signature = wrap_in_code(
                f"{command} {configurable.name} <new value>"
            )
            disable_configurable_signature = wrap_in_code(
                f"{command} {configurable.name} disable"
            )

            message = (
                f"Option {configurable.name} is currently set to {value}."
                f"\nUse {set_configurable_signature} to set it."
            )
            if not configurable.required:
                message += f"\nUse {disable_configurable_signature} to disable it."
            if new_value:
                message = f"Option {configurable.name} has been set to {value}."

            await ctx.send(
                embed=discord.Embed(title="Configuration", description=message)
            )
            return

        get_signature = wrap_in_code(f"{command} <option>")
        set_signature = wrap_in_code(f"{command} <option> <new value>")
        disable_signature = wrap_in_code(f"{command} <option> disable")

        embed = discord.Embed(
            title="Configuration",
            description="Command to manage the bot's configuration for a server."
            f"\nTo get the value of an option use {get_signature}."
            f"\nTo set the value of an option use {set_signature}."
            f"\nTo disable an optional option use {disable_signature}."
            "\nList of options can be found below:",
        )
        embed.set_footer(
            text="Page {current_page}/{total_pages}, "
            "showing option {first_field}..{last_field}/{total_fields}"
        )
        paginator = paginators.FieldPaginator(self.bot, base_embed=embed)

        for configurable in config.configurables:
            paginator.add_field(
                name=configurable.name.capitalize(),
                value=configurable.description,
            )

        await paginator.send(target=ctx.channel, owner=ctx.author)

    @commands.command()
    @commands.cooldown(3, 8, commands.BucketType.channel)
    async def about(self, ctx: commands.Context):
        """Gives information about this bot"""

        await ctx.send(
            embed=discord.Embed(title="About", description=self.bot.description)
        )

    @commands.command()
    @commands.cooldown(3, 8, commands.BucketType.channel)
    async def invite(self, ctx: commands.Context):
        """This bot is private"""

        await ctx.send(
            embed=discord.Embed(title="Invite", description="This bot is private")
        )


def setup(bot: commands.Bot):
    bot.add_cog(Meta(bot))
