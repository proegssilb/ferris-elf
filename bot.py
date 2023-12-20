import asyncio
import logging
import sys
import typing
from datetime import datetime
from typing import Annotated, Optional, Literal, TypeVar
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands
from dynaconf import ValidationError

import constants
import lib
from config import settings
from database import Database
from error_handler import ErrorHandlerCog, NonBugError

T = TypeVar("T")
OrNone = Annotated[Optional[T], T]
# python 3.12 syntax
# type OptFixed[T] = Annotated[Optional[T], T]

logger = logging.getLogger(__name__)


class MyBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queue = asyncio.Queue()
        self.db = Database().get()

    async def setup_hook(self):
        await asyncio.gather(
            bot.add_cog(Commands(bot)),
            bot.add_cog(ErrorHandlerCog(bot))
        )

    async def on_ready(self):
        print("Logged in as", self.user)
        while True:
            try:
                submit_msg = await self.queue.get()
                logger.info("Going to process submission from queue: %s", submit_msg)
                await lib.benchmark(*submit_msg)
                self.queue.task_done()
            except Exception:
                logger.exception("Error while processing submission.")


def today():
    dt = datetime.now(tz=ZoneInfo("America/New_York"))
    return min(dt.day, constants.MAX_DAY)


# TODO: make some ugly hack so slash commands get this hinted before sending
class Day(commands.Converter):
    async def convert(self, ctx: commands.Context, argument: str) -> int:
        day = int(argument)
        if day > today() or day < 1:
            raise commands.BadArgument(f"Day {day} out of bounds.")
        return day


# if i don't use a cog, the functions would need to be in __name__ == __main__
class Commands(commands.Cog):
    def __init__(self, sbot: MyBot):
        self.bot = sbot

    @commands.command()
    @commands.is_owner()
    async def sync(self, ctx: commands.Context):
        # sync slash commands
        # this is a separate command because rate limits
        await self.bot.tree.sync()
        await ctx.reply("synced!")

    # intentionally did not use typing.Optional because dpy treats it differently and i dont want that behavior
    @commands.hybrid_command(aliases=["aoc", "lb"])
    async def best(self, ctx: commands.Context, day: Annotated[Optional[int], Day] = None,
                   part: Annotated[Optional[Literal[1, 2]], Literal[1, 2]] = None):
        if day is None:
            day = today()

        async def format_times(times):
            formatted = ""
            for user_id, time in times:
                user = self.get_user(user_id) or await self.fetch_user(user_id)
                if user:
                    formatted += f"\t{user.name}:  **{time}**\n"
            return formatted

        (times1, times2) = lib.get_best_times(day)
        times1_str = await format_times(times1)
        times2_str = await format_times(times2)
        embed = discord.Embed(
            title=f"Top 10 fastest toboggans for day {day}", color=0xE84611
        )
        if times1_str and (part is None or part == 1):
            embed.add_field(name="Part 1", value=times1_str, inline=True)
        if times2_str and (part is None or part == 2):
            embed.add_field(name="Part 2", value=times2_str, inline=True)
        await ctx.reply(embed=embed)

    # i intentionally did not have the default behavior of automatically choosing part 1 because that's confusing
    @commands.hybrid_command()
    async def submit(self, ctx: commands.Context, day: Annotated[int, Day], part: typing.Literal[1, 2],
                     code: discord.Attachment):
        logger.info(
            "Queueing submission for %s, message = [%s], queue length = %s",
            ctx.author,
            ctx.args,
            self.bot.queue.qsize(),
        )
        # using a tuple is probably the most readable but shut
        self.bot.queue.put_nowait((ctx, day, part, await code.read()))
        await ctx.reply(
            f"Your submission for day {day} part {part} has been queued. "
            f"There are {self.bot.queue.qsize()} submissions in the queue."
        )

    @commands.hybrid_command()
    async def help(self, ctx: commands.Context):
        await ctx.reply(embed=constants.HELP_REPLY)

    @commands.hybrid_command()
    async def info(self, ctx: commands.Context):
        await ctx.reply(embed=constants.INFO_REPLY)


async def prefix(cbot: commands.Bot, message: discord.Message) -> typing.List[str]:
    return ["aoc ", "aoc"]


if __name__ == "__main__":
    logging.basicConfig(encoding="utf-8", level=logging.INFO)

    intents = discord.Intents.default()
    intents.message_content = True
    intents.messages = True
    intents.guild_messages = True
    intents.dm_messages = True
    intents.typing = False
    intents.presences = False

    try:
        settings.validators.validate()
    except ValidationError as ve:
        logger.exception(
            "Invalid config. Did you forget to add the bot token to the `.secrets.toml` file? See the README for more info."
        )
        sys.exit(1)
    bot = MyBot(
        intents=intents,
        command_prefix=prefix,
        case_insensitive=True,
        # dpy comes with a help command, we need to remove it
        help_command=None,
        # disallows the bot from mentioning things it shouldn't, just in case
        allowed_mentions=discord.AllowedMentions(everyone=False, users=True, roles=False, replied_user=True)
    )
    bot.run(settings.discord.bot_token)
