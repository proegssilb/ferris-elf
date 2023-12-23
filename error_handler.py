import datetime
import io
import logging
import traceback
import urllib

import discord
from discord.ext import commands
import discord.ext.commands.errors as commanderrors

logger = logging.getLogger(__name__)


def get_full_class_name(obj):
    """
    Returns the fully qualified class name of `obj`, used for more clear error reporting.
    based on https://stackoverflow.com/a/2020083/9044183
    """
    klass = obj.__class__
    return klass.__module__ + '.' + klass.__qualname__


# TODO: maybe change name?
class NonBugError(Exception):
    """When this is raised instead of a normal Exception, on_command_error() will not attach a traceback or github
    link. """
    pass


# completely overkill error handler shamelessly ripped from MediaForge, a bot i wrote
class ErrorHandlerCog(commands.Cog):
    def __init__(self, bot):
        self.bot: commands.Bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, commanderror: commands.CommandError):
        async def dmauthor(*args, **kwargs):
            try:
                return await ctx.author.send(*args, **kwargs)
            except discord.Forbidden:
                logger.info(f"Reply to {ctx.message.id} and dm to {ctx.author.id} failed. Aborting.")

        async def reply(msg, file=None, embed=None):
            try:
                if ctx.interaction and ctx.interaction.response.is_done():
                    return await ctx.interaction.edit_original_response(
                        content=msg,
                        attachments=[file] if file else None,
                        embed=embed
                    )
                else:
                    return await ctx.reply(msg, file=file, embed=embed)
            except discord.Forbidden:
                logger.debug(f"Forbidden to reply to {ctx.message.id}")
                if ctx.guild:
                    logger.debug("Trying to DM author")
                    return await dmauthor(msg, file=file, embed=embed)

        async def logandreply(message):
            if ctx.guild:
                ch = f"channel #{ctx.channel.name} ({ctx.channel.id}) in server {ctx.guild} ({ctx.guild.id})"
            else:
                ch = "DMs"
            logger.info(f"Command '{ctx.message.content}' by @{ctx.message.author} ({ctx.message.author.id}) in {ch} "
                        f"failed due to {message}.")
            await reply(message)

        # errors in commands are wrapped in these, unwrap for error handling
        # sometimes they're double wrapped,
        # so a while loop to keep unwrapping until we get to the center of the tootsie pop
        while isinstance(commanderror, (
                commanderrors.CommandInvokeError,
                discord.ext.commands.HybridCommandError,
                discord.app_commands.errors.CommandInvokeError
        )):
            commanderror = commanderror.original
        errorstring = str(commanderror)
        match commanderror:
            case discord.Forbidden():
                await dmauthor(f"I don't have permissions to send messages in that channel.")
                logger.info(commanderror)
            case commanderrors.CommandNotFound():
                # remove prefix, remove excess args
                cmd = ctx.message.content[len(ctx.prefix):].split(' ')[0]
                err = f"Command `{cmd}` does not exist. "
                await logandreply(err)
            case commanderrors.NotOwner():
                err = f"You are not authorized to use this command."
                await logandreply(err)
            case commanderrors.UserInputError():
                err = f"{errorstring}"
                if ctx.command:
                    err += f" Run `help` to see how to use this command."
                await logandreply(err)
            case commanderrors.NoPrivateMessage() | commanderrors.CheckFailure():
                err = f"⚠️ {errorstring}"
                await logandreply(err)
            case NonBugError():
                await logandreply(f"‼️ {str(commanderror)[:1000]}")
            case _:
                logger.error(commanderror, exc_info=(type(commanderror), commanderror, commanderror.__traceback__))
                desc = "Please report this error with the attached traceback file to the GitHub."
                embed = discord.Embed(color=0xed1c24, description=desc)
                embed.add_field(name=f"Report Issue to GitHub",
                                value=f"[Create New Issue](https://github.com/proegssilb/ferris-elf/issues/new"
                                      f"?title={urllib.parse.quote(str(commanderror), safe='')[:848]})\n[View Issu"
                                      f"es](https://github.com/proegssilb/ferris-elf/issues)")
                with io.BytesIO() as buf:
                    if ctx.interaction:
                        command = f"/{ctx.command} {ctx.kwargs}"
                    else:
                        command = ctx.message.content
                    trheader = f"DATETIME:{datetime.datetime.now()}\nCOMMAND:{command}\nTRACEBACK:\n"
                    buf.write(bytes(trheader + ''.join(
                        traceback.format_exception(commanderror)), encoding='utf8'))
                    buf.seek(0)
                    errtxt = (f"`{get_full_class_name(commanderror)}: "
                              f"{errorstring}`")[:2000]
                    await reply(errtxt, file=discord.File(buf, filename="traceback.txt"), embed=embed)
