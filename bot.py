import asyncio
import logging
import sys
import typing
from typing import Annotated, Optional, Literal

import discord
from discord.ext import commands
from dynaconf import ValidationError

import constants
import lib
from config import settings
from database import Database
from error_handler import ErrorHandlerCog

logger = logging.getLogger(__name__)


class MyBot(commands.Bot):
    __slots__ = ("queue", "db")

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
        logger.info("Logged in as %s", self.user)
        while True:
            try:
                submit_msg = await self.queue.get()
                logger.info("Going to process submission from queue: %s", submit_msg)
                await lib.benchmark(*submit_msg)
                self.queue.task_done()
            except Exception:
                logger.exception("Error while processing submission.")


# if i don't use a cog, the functions would need to be in __name__ == __main__
class Commands(commands.Cog):
    __slots__ = ("bot",)

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
    async def best(self, ctx: commands.Context, day: Annotated[Optional[int], commands.Range[int, 1, 25]] = None,
                   part: Annotated[Optional[Literal[1, 2]], Literal[1, 2]] = None):
        if day is None:
            day = lib.today()
        else:
            if day > lib.today():
                raise commands.BadArgument(f"Day {day} is in the future!")

        async def format_times(times):
            formatted = ""
            for user_id, time in times:
                user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
                if user:
                    formatted += f"\t{user.name}:  **{time}**\n"
            return formatted

        (times1, times2) = lib.get_best_times(day)
        times1_str = await format_times(times1)
        times2_str = await format_times(times2)
        embed = discord.Embed(
            title=f"Top 10 fastest toboggans for day {day}",
            color=0xE84611,
        )
        if times1_str and (part is None or part == 1):
            embed.add_field(name="Part 1", value=times1_str, inline=True)
        if times2_str and (part is None or part == 2):
            embed.add_field(name="Part 2", value=times2_str, inline=True)
        embed.set_footer(text=constants.LEADERBOARD_FOOTER)
        await ctx.reply(embed=embed)

    # i intentionally did not have the default behavior of automatically choosing part 1 because that's confusing
    @commands.hybrid_command()
    async def submit(self, ctx: commands.Context, day: commands.Range[int, 1, 25], part: Literal[1, 2],
                     code: discord.Attachment):
        if day > lib.today():
            raise commands.BadArgument(f"Day {day} is in the future!")
        await ctx.reply("Submitting...")
        logger.info(
            "Queueing submission for %s, message = [%s], queue length = %s",
            ctx.author,
            ctx.args,
            self.bot.queue.qsize(),
        )
        # using a tuple is probably the most readable but shut
        self.bot.queue.put_nowait((ctx, day, part, await code.read()))
        await ctx.interaction.edit_original_response(
            content=f"Your submission for day {day} part {part} has been queued. " +
            f"There are {self.bot.queue.qsize()} submissions in the queue."
        )

    @commands.hybrid_command()
    async def help(self, ctx: commands.Context):
        await ctx.reply(embed=constants.HELP_REPLY)

    @commands.hybrid_command()
    async def info(self, ctx: commands.Context):
        await ctx.reply(embed=constants.INFO_REPLY)


async def prefix(dbot: commands.Bot, message: discord.Message) -> list[str]:
    # TODO: guild-specific prefixes
    return ["aoc ", "aoc", f'<@!{dbot.user.id}> ', f'<@{dbot.user.id}> ', f'<@!{dbot.user.id}>', f'<@{dbot.user.id}>']


if __name__ == "__main__":
    logformat = "%(asctime)s:%(levelname)s:%(name)s:%(message)s"
    logging.basicConfig(encoding="utf-8", level=logging.INFO, datefmt="%a, %d %b %Y %H:%M:%S %z", format=logformat)

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
        # For anyone new to dpy, these are not ulimit style, i/e, any time we want to override this for whatever
        # reason we can, but having it off by default is safe
        # disallows the bot from mentioning things it shouldn't, just in case
        allowed_mentions=discord.AllowedMentions(everyone=False, users=True, roles=False, replied_user=True)
    )
    bot.run(settings.discord.bot_token, log_handler=None)
