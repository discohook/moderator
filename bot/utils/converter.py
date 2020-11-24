import re
from datetime import timedelta

from discord.ext import commands


class TimeDurationConverter(commands.Converter):
    async def convert(self, ctx, argument):
        match = re.match(r"^(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$", argument)

        if match is None or not match.group(0):
            raise commands.BadArgument("Invalid duration given")

        return timedelta(
            days=int(match.group(1) or 0),
            hours=int(match.group(2) or 0),
            minutes=int(match.group(3) or 0),
            seconds=int(match.group(4) or 0),
        )


class UserConverter(commands.UserConverter):
    async def convert(self, ctx, argument):
        try:
            return await super().convert(ctx, argument)
        except commands.UserNotFound:
            if match := self._get_id_match(argument):
                user_id = int(match.group(1))
                user = await ctx.bot.fetch_user(user_id)
                if user:
                    return user

            raise
