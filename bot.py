import asyncio
import logging
import sys
import traceback

import discord
from dynaconf import ValidationError

import lib
from messages import SubmitMessage, GetBestTimesMessage
from database import Database
from config import settings
import constants

logger = logging.getLogger(__name__)


class MyBot(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queue = asyncio.Queue()
        self.db = Database().get()

    async def on_ready(self):
        print("Logged in as", self.user)
        while True:
            try:
                submit_msg = await self.queue.get()
                logger.info("Going to process submission from queue: %s", submit_msg)
                await lib.benchmark(submit_msg)
                self.queue.task_done()
            except Exception:
                logger.exception("Error while processing submission.")

    async def handle_best(self, msg):
        async def format_times(times):
            formatted = ""
            for user_id, time in times:
                user = self.get_user(user_id) or await self.fetch_user(user_id)
                if user:
                    formatted += f"\t{user.name}:  **{time}**\n"
            return formatted

        try:
            get_best_msg = GetBestTimesMessage.parse(msg)
            (times1, times2) = lib.get_best_times(get_best_msg.day)
            times1_str = await format_times(times1)
            times2_str = await format_times(times2)
            embed = discord.Embed(
                title=f"Top 10 fastest toboggans for day {get_best_msg.day}", color=0xE84611
            )
            if times1_str and (get_best_msg.part == 0 or get_best_msg.part == 1):
                embed.add_field(name="Part 1", value=times1_str, inline=True)
            if times2_str and (get_best_msg.part == 0 or get_best_msg.part == 2):
                embed.add_field(name="Part 2", value=times2_str, inline=True)
            await msg.reply(embed=embed)
        except Exception:
            logger.exception("Error while processing request for leaderboard.")
            await msg.reply("Error handling your message", embed=constants.HELP_REPLY)
        return

    async def handle_submit(self, msg):
        try:
            if len(msg.attachments) == 0:
                await msg.reply("Please provide the code as a file attachment")
                return
            submit_msg = SubmitMessage.parse(msg)
            logger.info(
                "Queueing submission for %s, message = [%s], queue length = %s",
                msg.author,
                submit_msg,
                self.queue.qsize(),
            )
            self.queue.put_nowait(submit_msg)
            await msg.reply(
                f"Your submission for day {submit_msg.day} part {submit_msg.part} has been queued."
                + f"There are {self.queue.qsize()} submissions in the queue)"
            )
        except Exception:
            logger.exception("Error while queueing submission")
            await msg.reply("Error handling your message", embed=constants.HELP_REPLY)
        return

    async def handle_help(self, msg):
        await msg.reply(embed=constants.HELP_REPLY)
        return

    async def handle_info(self, msg):
        await msg.reply(embed=constants.INFO_REPLY)
        return

    async def on_message(self, msg):
        if msg.author.bot:
            return
        logger.info("Message received from %s", msg.author.name)
        if msg.content.startswith("best") or msg.content.startswith("aoc"):
            await self.handle_best(msg)
        elif msg.content.startswith("submit"):
            await self.handle_submit(msg)
        elif msg.content == "info":
            await self.handle_info(msg)
        else:
            await self.handle_help(msg)
        return


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
    bot = MyBot(intents=intents)
    bot.run(settings.discord.bot_token)
