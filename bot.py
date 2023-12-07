import asyncio
import traceback

import discord

import lib
from messages import SubmitMessage, GetBestTimesMessage
from database import Database

from config import settings
import constants

class MyBot(discord.Client):
    queue = asyncio.Queue()
    db = Database().get()

    async def on_ready(self):
        print("Logged in as", self.user)
        while True:
            try:
                submit_msg = await self.queue.get()
                print(f"Going to process submission from queue: {submit_msg}")
                await lib.benchmark(submit_msg)
                self.queue.task_done()
            except Exception as err:
                traceback.print_exception(err)

    async def handle_best(self, msg):
        async def format_times(times):
            formatted = ""
            for (user_id, time) in times:
                user = self.get_user(user_id) or await self.fetch_user(user_id)
                if user:
                    formatted += f"\t{user.name}:  **{time}**\n"
            return formatted

        try:
            get_best_msg = GetBestTimesMessage.parse(msg)
            (times1,times2) = lib.get_best_times(get_best_msg.day)
            times1_str = await format_times(times1)
            times2_str = await format_times(times2)
            embed = discord.Embed(title=f"Top 10 fastest toboggans for day {get_best_msg.day}", color=0xE84611)
            if times1_str and (get_best_msg.part == 0 or get_best_msg.part == 1):
                embed.add_field(name="Part 1", value=times1_str, inline=True)
            if times2_str and (get_best_msg.part == 0 or get_best_msg.part == 2):
                embed.add_field(name="Part 2", value=times2_str, inline=True)
            await msg.reply(embed=embed)
        except Exception as e:
            traceback.print_exception(e) #TODO: we probably dont want to log all incorrectly formatteed messages long term
            await msg.reply(f"Error handling your message", embed=constants.HELP_REPLY)
        return
        
    async def handle_submit(self, msg):
        try:
            if len(msg.attachments) == 0:
                await msg.reply("Please provide the code as a file attachment")
                return
            submit_msg = SubmitMessage.parse(msg)
            print(f"Queueing for {msg.author} , message = {submit_msg} , queue length = {self.queue.qsize()}")
            self.queue.put_nowait(submit_msg)
            await msg.reply(f"Your submission for day {submit_msg.day} part {submit_msg.part} has been queued." +
                            f"There are {self.queue.qsize()} submissions in the queue)")
        except Exception as e:
            traceback.print_exception(e) #TODO: we probably dont want to log all incorrectly formatteed messages long term
            await msg.reply(f"Error handling your message", embed=constants.HELP_REPLY)
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
        print("Message received from", msg.author.name)
        if msg.content.startswith("best") or msg.content.startswith("aoc"):
            await self.handle_best(msg)
        elif msg.content.startswith("submit"):
            await self.handle_submit(msg)
        elif msg.content == "info":
            await self.handle_info(msg)
        else:
            await self.handle_help(msg)
        return

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
intents.guild_messages = True
intents.dm_messages = True
intents.typing = False
intents.presences = False

bot = MyBot(intents=intents)
bot.run(settings.discord.bot_token)
