import datetime
import io
import logging
import traceback
from typing import Any, Optional, cast
import urllib

import discord
from discord.ext import commands
import discord.ext.commands.errors as commanderrors

logger = logging.getLogger(__name__)


def get_full_class_name(obj: object) -> str:
    """
    Returns the fully qualified class name of `obj`, used for more clear error reporting.
    based on https://stackoverflow.com/a/2020083/9044183
    """
    klass = obj.__class__
    return klass.__module__ + "." + klass.__qualname__


# TODO: maybe change name?
class NonBugError(Exception):
    """When this is raised instead of a normal Exception, on_command_error() will not attach a traceback or github
    link."""

    pass


def unwrap_base_error(original: Exception) -> Exception:
    # errors in commands are wrapped in these, unwrap for error handling
    # sometimes they're double wrapped,
    # so a while loop to keep unwrapping until we get to the center of the tootsie pop

    while isinstance(
        original,
        (
            commanderrors.CommandInvokeError,
            discord.ext.commands.HybridCommandError,
            discord.app_commands.errors.CommandInvokeError,
        ),
    ):
        original = original.original

    return original


# completely overkill error handler shamelessly ripped from MediaForge, a bot i wrote
class ErrorHandlerCog(commands.Cog):
    __slots__ = ("bot",)

    def __init__(self, bot: commands.Bot) -> None:
        self.bot: commands.Bot = bot

    @commands.Cog.listener()
    async def on_command_error(
        self, ctx: commands.Context[Any], commanderror: commands.CommandError
    ) -> None:
        async def dmauthor(*args: Any, **kwargs: Any) -> Optional[discord.Message]:
            try:
                return await ctx.author.send(*args, **kwargs)
            except discord.Forbidden:
                logger.info(
                    f"Reply to {ctx.message.id} and dm to {ctx.author.id} failed. Aborting."
                )
                # yes we need to do this for mypy
                return None

        async def reply(
            msg: str, file: Optional[discord.File] = None, embed: Optional[discord.Embed] = None
        ) -> Optional[discord.Message]:
            try:
                if ctx.interaction and ctx.interaction.response.is_done():
                    return await ctx.interaction.edit_original_response(
                        content=msg, attachments=[file] if file else [], embed=embed
                    )
                else:
                    # cast here because mypy and pyright both agree we cant pass None to file/embed
                    # even though that is what happens codeside by default, it must be a stubs error
                    return await ctx.reply(
                        msg, file=cast(discord.File, file), embed=cast(discord.Embed, embed)
                    )
            except discord.Forbidden:
                logger.debug(f"Forbidden to reply to {ctx.message.id}")
                if ctx.guild:
                    logger.debug("Trying to DM author")
                    return await dmauthor(msg, file=file, embed=embed)

            # we need this for mypy
            return None

        async def logandreply(message: str) -> None:
            if ctx.guild and not isinstance(
                ctx.channel, (discord.DMChannel, discord.PartialMessageable)
            ):
                ch = f"channel #{ctx.channel.name} ({ctx.channel.id}) in server {ctx.guild} ({ctx.guild.id})"
            else:
                ch = "DMs"
            logger.info(
                f"Command '{ctx.message.content}' by @{ctx.message.author} ({ctx.message.author.id}) in {ch} "
                f"failed due to {message}."
            )
            await reply(message)

        original: Exception = unwrap_base_error(commanderror)

        errorstring = str(original)
        match original:
            case discord.Forbidden():
                await dmauthor("I don't have permissions to send messages in that channel.")
                logger.info(original)
            case commanderrors.CommandNotFound():
                # remove prefix, remove excess args
                cmd = ctx.message.content[len(ctx.prefix or "") :].split(" ")[0]
                err = f"Command `{cmd}` does not exist. "
                await logandreply(err)
            case commanderrors.NotOwner():
                err = "You are not authorized to use this command."
                await logandreply(err)
            case commanderrors.UserInputError():
                err = f"{errorstring}"
                if ctx.command:
                    err += " Run `help` to see how to use this command."
                await logandreply(err)
            case commanderrors.NoPrivateMessage() | commanderrors.CheckFailure():
                err = f"⚠️ {errorstring}"
                await logandreply(err)
            case NonBugError():
                await logandreply(f"‼️ {str(original)[:1000]}")
            case _:
                logger.error(
                    original,
                    exc_info=(type(original), original, original.__traceback__),
                )
                desc = "Please report this error with the attached traceback file to the GitHub."
                embed = discord.Embed(color=0xED1C24, description=desc)
                embed.add_field(
                    name="Report Issue to GitHub",
                    value="[Create New Issue](https://github.com/proegssilb/ferris-elf/issues/new"
                    f"?title={urllib.parse.quote(str(original), safe='')[:848]})\n[View Issu"
                    "es](https://github.com/proegssilb/ferris-elf/issues)",
                )
                with io.BytesIO() as buf:
                    if ctx.interaction:
                        command = f"/{ctx.command} {ctx.kwargs}"
                    else:
                        command = ctx.message.content
                    trheader = (
                        f"DATETIME:{datetime.datetime.now()}\nCOMMAND:{command}\nTRACEBACK:\n"
                    )
                    buf.write(
                        bytes(
                            trheader + "".join(traceback.format_exception(commanderror)),
                            encoding="utf8",
                        )
                    )
                    buf.seek(0)
                    errtxt = (f"`{get_full_class_name(commanderror)}: " f"{errorstring}`")[:2000]
                    await reply(
                        errtxt, file=discord.File(buf, filename="traceback.txt"), embed=embed
                    )
