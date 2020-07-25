import asyncio
import itertools
import re

import discord
from discord.ext import commands


class HelpCommand(commands.HelpCommand):
    async def prepare_help_command(self, ctx, command=None):
        prefix = self.clean_prefix.replace(r"\\", "\\")
        command = f"{prefix}{self.invoked_with}"

        self.embed = discord.Embed(title="Help")
        self.embed.set_footer(text=f'Use "{command} [command]" for more info')

    def get_command_signature(self, command, *, short=False):
        parent = command.full_parent_name
        alias = command.name if not parent else parent + " " + command.name

        if not short and len(command.aliases) > 0:
            name_with_aliases = f"[{command.name}|{'|'.join(command.aliases)}]"
            alias = f"{parent} {name_with_aliases}" if parent else name_with_aliases

        signature = f"{self.context.prefix}{alias}" if not short else alias
        if command.signature:
            signature += f" {command.signature}".replace("_", " ")

        return signature

    def command_not_found(self, string):
        return f'Command "{string}" does not exist'

    def subcommand_not_found(self, command, string):
        return f'Command "{command.qualified_name}" has no subcommand named "{string}"'

    async def send_error_message(self, error):
        await self.get_destination().send(
            embed=discord.Embed(title="Error", description=error)
        )

    async def send_bot_help(self, mapping):
        if self.context.bot.description:
            self.embed.description = self.context.bot.description

        grouped = itertools.groupby(
            await self.filter_commands(
                self.context.bot.commands,
                sort=True,
                key=lambda command: command.cog.qualified_name,
            ),
            key=lambda command: command.cog.qualified_name,
        )

        for category, commands in grouped:
            commands = sorted(commands, key=lambda command: command.name)
            description = []

            for command in commands:
                description.append(
                    f"`{self.get_command_signature(command, short=True)}`: {command.help}"
                )

            self.embed.add_field(
                name=category, value="\n".join(description), inline=False
            )

        await self.get_destination().send(embed=self.embed)

    async def send_cog_help(self, cog: commands.Cog):
        self.embed.title = f"Help: {cog.qualified_name}"

        if cog.description:
            self.embed.description = cog.description

        commands = await self.filter_commands(cog.get_commands(), sort=True)

        for command in commands:
            self.embed.add_field(
                name=f"`{self.get_command_signature(command, short=True)}`",
                value=command.short_doc,
                inline=False,
            )

        await self.get_destination().send(embed=self.embed)

    async def send_group_help(self, group: commands.Group):
        self.embed.title = f"Help: {group.qualified_name}"
        self.embed.description = (
            f"Syntax: `{self.get_command_signature(group)}`\n{group.help}"
        )

        commands = await self.filter_commands(group.commands, sort=True)

        for command in commands:
            self.embed.add_field(
                name=f"`{self.get_command_signature(command, short=True)}`",
                value=command.help,
                inline=False,
            )

        await self.get_destination().send(embed=self.embed)

    async def send_command_help(self, command: commands.Command):
        self.embed.title = f"Help: {command.qualified_name}"

        self.embed.description = (
            f"Syntax: `{self.get_command_signature(command)}`\n{command.help}"
        )

        await self.get_destination().send(embed=self.embed)


class Meta(commands.Cog):
    """Commands related to the bot itself"""

    def __init__(self, bot):
        self.bot = bot
        super().__init__()

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
    meta = Meta(bot)
    bot.add_cog(meta)
    bot.help_command = HelpCommand()
    bot.help_command.cog = meta
