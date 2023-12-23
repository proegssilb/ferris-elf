import datetime
import io
import logging
import traceback
import urllib

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


def get_full_class_name(obj):
    module = obj.__class__.__module__
    if module is None or module == str.__class__.__module__:
        return obj.__class__.__name__
    return module + '.' + obj.__class__.__name__


class NonBugError(Exception):
    """When this is raised instead of a normal Exception, on_command_error() will not attach a traceback or github
    link. """
    pass


# completely overkill error handler shamelessly ripped from MediaForge, a bot i wrote
class ErrorHandlerCog(commands.Cog):
    def __init__(self, bot):
        self.bot: commands.Bot = bot
        self.antispambucket = {}

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, commanderror: commands.CommandError):
        async def dmauthor(*args, **kwargs):
            try:
                return await ctx.author.send(*args, **kwargs)
            except discord.Forbidden:
                logger.info(f"Reply to {ctx.message.id} and dm to {ctx.author.id} failed. Aborting.")

        async def reply(msg, file=None, embed=None):
            if ctx.interaction:
                if ctx.interaction.response.is_done():
                    return await ctx.interaction.edit_original_response(content=msg,
                                                                        attachments=[file] if file else None,
                                                                        embed=embed)
                else:
                    return await ctx.reply(msg, file=file, embed=embed)
            elif ctx.guild and not ctx.channel.permissions_for(ctx.me).send_messages:
                logger.debug(f"No permissions to reply to {ctx.message.id}, trying to DM author.")
                return await dmauthor(msg, file=file, embed=embed)
            else:
                try:
                    return await ctx.reply(msg, file=file, embed=embed)
                except discord.Forbidden:
                    logger.debug(f"Forbidden to reply to {ctx.message.id}, trying to DM author")
                    return await dmauthor(msg, file=file, embed=embed)

        async def logandreply(message):
            if ctx.guild:
                ch = f"channel #{ctx.channel.name} ({ctx.channel.id}) in server {ctx.guild} ({ctx.guild.id})"
            else:
                ch = "DMs"
            logger.info(f"Command '{ctx.message.content}' by "
                        f"@{ctx.message.author.name}#{ctx.message.author.discriminator} ({ctx.message.author.id}) "
                        f"in {ch} failed due to {message}.")
            await reply(message)

        errorstring = str(commanderror)
        if isinstance(commanderror, discord.Forbidden):
            await dmauthor(f"I don't have permissions to send messages in that channel.")
            logger.info(commanderror)
        if isinstance(commanderror, discord.ext.commands.errors.CommandNotFound):
            # remove prefix, remove excess args
            cmd = ctx.message.content[len(ctx.prefix):].split(' ')[0]
            err = f"Command `{cmd}` does not exist. "
            await logandreply(err)
        elif isinstance(commanderror, discord.ext.commands.errors.NotOwner):
            err = f"You are not authorized to use this command."
            await logandreply(err)
        elif isinstance(commanderror, discord.ext.commands.errors.UserInputError):
            err = f"{errorstring}"
            if ctx.command:
                err += f" Run `help` to see how to use this command."
            await logandreply(err)
        elif isinstance(commanderror, discord.ext.commands.errors.NoPrivateMessage):
            err = f"⚠️ {errorstring}"
            await logandreply(err)
        elif isinstance(commanderror, discord.ext.commands.errors.CheckFailure):
            err = f"⚠️ {errorstring}"
            await logandreply(err)
        elif isinstance(commanderror, discord.ext.commands.errors.CommandInvokeError) and \
                isinstance(commanderror.original, NonBugError):
            await logandreply(f"‼️ {str(commanderror.original)[:1000]}")
        else:
            if isinstance(commanderror, discord.ext.commands.errors.CommandInvokeError) or \
                    isinstance(commanderror, discord.ext.commands.HybridCommandError):
                commanderror = commanderror.original
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
