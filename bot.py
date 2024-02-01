import asyncio
from io import StringIO
import logging
import sys
from typing import Annotated, Any, Callable, Optional, Literal, ParamSpec, TypeVar

import discord
from discord.ext import commands
from discord import app_commands
from dynaconf import ValidationError

import constants
import lib
from config import settings
from database import AdventDay, AdventPart, Database, Picoseconds, Year
from error_handler import ErrorHandlerCog
from runner import bg_update

logger = logging.getLogger(__name__)


class MyBot(commands.Bot):
    __slots__ = "queue"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.queue = asyncio.Queue[
            tuple[commands.Context[Any], Year, AdventDay, AdventPart, bytes]
        ]()

    async def setup_hook(self) -> None:
        await asyncio.gather(
            bot.add_cog(Commands(bot)),
            bot.add_cog(ErrorHandlerCog(bot)),
            bot.add_cog(ModCommands(bot)),
        )

    async def on_ready(self) -> None:
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

    def __init__(self, sbot: MyBot) -> None:
        self.bot = sbot

    @commands.is_owner()
    @commands.dm_only()
    @commands.command()
    async def sync(self, ctx: commands.Context[Any]) -> None:
        # sync slash commands
        # this is a separate command because rate limits
        await self.bot.tree.sync()
        await ctx.reply("synced!")

    # intentionally did not use typing.Optional because dpy treats it differently and i dont want that behavior
    # type-ignore for mypy not understanding how to work with hybrid_command decorator
    @commands.hybrid_command()  # type: ignore[arg-type]
    async def leaderboard(
        self,
        ctx: commands.Context[Any],
        day: Annotated[Optional[AdventDay], commands.Range[int, 1, 25]] = None,
        part: Annotated[Optional[Literal[1, 2]], Literal[1, 2]] = None,
    ) -> None:
        if day is None:
            day = lib.today()
        else:
            if day > lib.today():
                raise commands.BadArgument(f"Day {day} is in the future!")

        async def format_times(times: list[tuple[int, str]]) -> str:
            formatted = StringIO()
            for user_id, time in times:
                user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
                if user:
                    formatted.write(f"\t{user.name}:  **{time}**\n")
            return formatted.getvalue()

        (times1, times2) = lib.get_best_times(lib.year(), day)
        times1_str = await format_times(times1)
        times2_str = await format_times(times2)
        embed = discord.Embed(title=f"Top 10 fastest toboggans for day {day}", color=0xE84611)
        if times1_str and (part is None or part == 1):
            embed.add_field(name="Part 1", value=times1_str, inline=True)
        if times2_str and (part is None or part == 2):
            embed.add_field(name="Part 2", value=times2_str, inline=True)
        embed.set_footer(text=constants.LEADERBOARD_FOOTER)
        await ctx.reply(embed=embed)

    # `aliases` argument doesn't work for the slash-cmd part, so do it manually.
    @commands.hybrid_command()  # type: ignore[arg-type]
    async def lb(
        self,
        ctx: commands.Context[Any],
        day: Annotated[Optional[AdventDay], commands.Range[int, 1, 25]] = None,
        part: Annotated[Optional[Literal[1, 2]], Literal[1, 2]] = None,
    ) -> None:
        await self.best(ctx, day, part)  # type: ignore[arg-type]

    @commands.hybrid_command()  # type: ignore[arg-type]
    async def best(
        self,
        ctx: commands.Context[Any],
        day: Annotated[Optional[AdventDay], commands.Range[int, 1, 25]] = None,
        part: Annotated[Optional[Literal[1, 2]], Literal[1, 2]] = None,
    ) -> None:
        await self.best(ctx, day, part)  # type: ignore[arg-type]

    @commands.hybrid_command()  # type: ignore[arg-type]
    async def aoc(
        self,
        ctx: commands.Context[Any],
        day: Annotated[Optional[AdventDay], commands.Range[int, 1, 25]] = None,
        part: Annotated[Optional[Literal[1, 2]], Literal[1, 2]] = None,
    ) -> None:
        await self.best(ctx, day, part)  # type: ignore[arg-type]

    # i intentionally did not have the default behavior of automatically choosing part 1 because that's confusing
    # type-ignore for mypy not understanding how to work with hybrid_command decorator
    @commands.hybrid_command()  # type: ignore[arg-type]
    @commands.dm_only()
    async def submit(
        self,
        ctx: commands.Context[Any],
        day: Annotated[AdventDay, commands.Range[int, 1, 25]],
        part: Literal[1, 2],
        code: discord.Attachment,
    ) -> None:
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
        self.bot.queue.put_nowait((ctx, lib.year(), day, part, await code.read()))

        if ctx.interaction is not None:
            await ctx.interaction.edit_original_response(
                content=f"Your submission for day {day} part {part} has been queued. "
                + f"There are {self.bot.queue.qsize()} submissions in the queue."
            )

    # type-ignore for mypy not understanding how to work with hybrid_command decorator
    @commands.hybrid_command()  # type: ignore[arg-type]
    async def help(self, ctx: commands.Context[Any]) -> None:
        await ctx.reply(embed=constants.HELP_REPLY)

    # type-ignore for mypy not understanding how to work with hybrid_command decorator
    @commands.hybrid_command()  # type: ignore[arg-type]
    async def info(self, ctx: commands.Context[Any]) -> None:
        await ctx.reply(embed=constants.INFO_REPLY)


P = ParamSpec("P")
T = TypeVar("T")


def only_from_guilds(*servers: list[int]) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Add a check to make sure the command can only be run from one of a list of servers."""

    # The lazy return type is due to discord.py not being more specific in their return type.
    # `discord.Interaction` is currently a generic type, but is not documented that way.

    def check_guild(itr: discord.Interaction) -> bool:  # type: ignore[type-arg]
        return itr.guild_id in (servers or [])

    return app_commands.check(check_guild)


class ModCommands(commands.Cog):
    __slots__ = ("bot",)

    def __init__(self, sbot: MyBot) -> None:
        self.bot = sbot

    @app_commands.command()
    @app_commands.default_permissions(manage_messages=True)
    @only_from_guilds(*settings.discord.management_servers)
    async def user_code(
        self,
        interaction: discord.Interaction,  # type: ignore[type-arg]
        user: discord.User,
        day: Annotated[AdventDay, app_commands.Range[int, 1, 25]],
        part: Annotated[AdventPart, Literal[1, 2]],
    ) -> None:
        await interaction.response.send_message(content="Loading...")

        with Database() as db:
            results = db.get_user_submissions(lib.year(), day, part, user.id)

        results.sort(key=(lambda r: r.average_time or Picoseconds(5e12)))
        results = results[:10]
        results.sort(key=(lambda r: r.id))

        attachments = []
        for res in results:
            name = f"Submission_{res.id}.rs"
            desc = f"Submission {res.id} from user {user}"
            file_handle = StringIO(res.code)

            # Not sure whether the type is specified incorrectly or this is an ugly hack.
            # Either way, this is what works to get Discord to not open a file.
            f = discord.File(file_handle, filename=name, description=desc)  # type: ignore[arg-type]
            attachments.append(f)

        await interaction.edit_original_response(
            content=f"Ten fastest submissions for user {user} on day {day}, part {part}:",
            attachments=attachments,
        )

    @app_commands.command()
    @app_commands.default_permissions(manage_messages=True)
    @only_from_guilds(*settings.discord.management_servers)
    async def leaderboard_code(
        self,
        interaction: discord.Interaction,  # type: ignore[type-arg]
        day: Annotated[AdventDay, app_commands.Range[int, 1, 25]],
        part: Annotated[AdventPart, Literal[1, 2]],
        place: Optional[app_commands.Range[int, 1, 10]] = None,
    ) -> None:
        await interaction.response.send_message(content="Loading...")

        with Database() as db:
            submisssions = db.get_lb_submissions(lib.year(), day, part)

        if place is not None:
            submisssions = [submisssions[place - 1]]

        attachments = []
        for res in submisssions:
            user = self.bot.get_user(res.user_id) or await self.bot.fetch_user(res.user_id)
            name = f"Submission_{user}_{res.id}.rs"
            desc = f"Submission {res.id} from user {user}"
            file_handle = StringIO(res.code)

            # Not sure whether the type is specified incorrectly or this is an ugly hack.
            # Either way, this is what works to get Discord to not open a file.
            f = discord.File(file_handle, filename=name, description=desc)  # type: ignore[arg-type]
            attachments.append(f)

        await interaction.edit_original_response(
            content=f"Leaderboard submissions on day {day}, part {part}:",
            attachments=attachments,
        )


async def prefix(dbot: commands.Bot, message: discord.Message) -> list[str]:
    # TODO(ultrabear): Bot.user is a Nullable field,
    # we should properly fix this sometime
    assert dbot.user is not None

    # TODO: guild-specific prefixes
    return [
        "aoc ",
        "aoc",
        f"<@!{dbot.user.id}> ",
        f"<@{dbot.user.id}> ",
        f"<@!{dbot.user.id}>",
        f"<@{dbot.user.id}>",
    ]


async def periodic_check_caller() -> None:
    while True:
        try:
            logger.info("calling periodic check function")
            await bg_update()
        except Exception:
            logger.exception("Unknown issue in periodic checking function.")

        # call every 30 minutes
        await asyncio.sleep(60 * 30)


if __name__ == "__main__":
    logformat = "%(asctime)s:%(levelname)s:%(name)s:%(message)s"
    logging.basicConfig(
        encoding="utf-8", level=logging.INFO, datefmt="%a, %d %b %Y %H:%M:%S %z", format=logformat
    )

    intents = discord.Intents.default()
    intents.message_content = True
    intents.messages = True
    intents.guild_messages = True
    intents.dm_messages = True
    intents.typing = False
    intents.presences = False

    try:
        settings.validators.validate()
    except ValidationError:
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
        allowed_mentions=discord.AllowedMentions(
            everyone=False, users=True, roles=False, replied_user=True
        ),
    )

    async def init(bot: discord.Client, token: str) -> None:
        asyncio.create_task(periodic_check_caller())

        async with bot:
            await bot.start(token)

    try:
        asyncio.run(init(bot, settings.discord.bot_token))
    except KeyboardInterrupt:
        pass
