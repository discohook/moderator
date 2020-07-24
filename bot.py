import asyncio
import re
import sys
import traceback
from os import environ

import aiohttp
import discord
from discord.ext import commands

environ.setdefault("JISHAKU_HIDE", "true")

extensions = (
    "jishaku",
    "ext.autorole",
    "ext.meta",
    "ext.tags",
)

error_types = (
    (commands.CommandOnCooldown, "Cooldown"),
    (commands.UserInputError, "Bad input"),
    (commands.CheckFailure, "Check failed"),
)

message_filters = [
    (
        re.compile(r"discord[.\s]?gg|discord(?:app)?.com\/invite"),
        "Remove invites from your message",
    ),
    (
        re.compile(r"discord(?:app)?\.com\/api\/webhooks\/\d+\/[\w-]+"),
        "Don't share your webhook URL! They can be abused by anyone to spam your server.",
    ),
]


class Bot(commands.AutoShardedBot):
    def __init__(self):
        super().__init__(
            command_prefix=self._get_prefixes,
            description="Private moderation bot for the Discohook server",
            activity=discord.Activity(
                type=discord.ActivityType.watching, name="the server | !help"
            ),
        )

        for extension in extensions:
            self.load_extension(extension)

    def _get_prefixes(self, bot, message):
        return ("!", "! ", f"<@{self.user.id}> ", f"<@!{self.user.id}> ")

    async def on_ready(self):
        print(f"Ready as {self.user} ({self.user.id})")

    async def on_message(self, message):
        if message.author.bot:
            return

        for (pattern, error) in message_filters:
            if pattern.search(message.content):
                await message.delete()
                await message.channel.send(
                    embed=discord.Embed(title="Message filter", description=error),
                    delete_after=5.0,
                )
                return

        if re.fullmatch(rf"<@!?{self.user.id}>", message.content):
            await message.channel.send(
                embed=discord.Embed(title="Prefix", description="My prefix is `!`")
            )
            return

        await self.process_commands(message)

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return

        for (error_type, error_msg) in error_types:
            if isinstance(error, error_type):
                await ctx.send(
                    embed=discord.Embed(title=error_msg, description=str(error)),
                    delete_after=10,
                )
                return

        err = error
        if isinstance(error, commands.CommandInvokeError):
            err = error.original

        if not isinstance(err, discord.HTTPException):
            traceback.print_tb(err.__traceback__)
            print(f"{err.__class__.__name__}: {err}", file=sys.stderr)


def main():
    bot = Bot()
    bot.run(environ.get("DISCORD_TOKEN"))


if __name__ == "__main__":
    main()
