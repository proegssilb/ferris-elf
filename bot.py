import asyncio
from os import listdir
from os.path import isfile, join
import sqlite3
import traceback

import discord

import lib
from messages import SubmitMessage, GetBestTimesMessage

from config import settings
import constants

db = sqlite3.connect(settings.db.filename)

cur = db.cursor()
cur.execute("""CREATE TABLE IF NOT EXISTS runs
    (user TEXT, code TEXT, day INTEGER, part INTEGER, time REAL, answer INTEGER, answer2)""")
cur.execute("""CREATE TABLE IF NOT EXISTS solutions
    (key TEXT, day INTEGER, part INTEGER, answer INTEGER, answer2)""")
db.commit()


class MyBot(discord.Client):
    queue = asyncio.Queue()

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
                print("Queue loop exception!", err)

    async def handle_best(self, msg):
        try:
            get_best_msg = GetBestTimesMessage.parse(msg)
            part1 = ""
            for (user, time) in db.cursor().execute(GetBestTimesMessage.query(), (get_best_msg.day, get_best_msg.part)):
                if user is None or time is None:
                    continue
                user = int(user)
                print(user, time)
                user = self.get_user(user) or await self.fetch_user(user)
                if user:
                    part1 += f"\t{user.name}: **{ns(time)}**\n"
            part2 = ""
            for (user, time) in db.cursor().execute(GetBestTimesMessage.query(), (get_best_msg.day, get_best_msg.part)):
                if user is None or time is None:
                    continue
                user = int(user)
                print(user, time)
                user = self.get_user(user) or await self.fetch_user(user)
                if user:
                    part2 += f"\t{user.name}: **{ns(time)}**\n"
            embed = discord.Embed(title=f"Top 10 fastest toboggans for day {get_best_msg.day}", color=0xE84611)
            if part1:
                embed.add_field(name="Part 1", value=part1, inline=True)
            if part2:
                embed.add_field(name="Part 2", value=part2, inline=True)
            await msg.reply(embed=embed)
        except Exception as e:
            traceback.print_exception(e)
            await msg.reply(f"Error handling your message: {e}") #TODO returning the actual exception is probably not safe, this is for testing
        return
        
    async def handle_submit(self, msg):
        try:
            submit_msg = SubmitMessage.parse(msg)
            if len(msg.attachments) == 0:
                await msg.reply("Please provide the code as a file attachment")
                return
            print(f"Queueing for {msg.author} , message = {submit_msg} , queue length = {self.queue.qsize()}")
            self.queue.put_nowait(submit_msg)
            await msg.reply(f"Your submission has been queued ({self.queue.qsize()} submissions in queue)")
        except Exception as e:
            traceback.print_exception(e)
            await msg.reply(f"Error handling your message: {e}") #TODO returning the actual exception is probably not safe, this is for testing
        return

    async def on_message(self, msg):
        if msg.author.bot:
            return
        
        print("Message received from", msg.author.name)
        if msg.content.startswith("best") or msg.content.startswith("aoc"):
            await self.handle_best(msg)
            return
        elif msg.content.startswith("submit"):
            await self.handle_submit(msg)
        elif msg.content == "help":
            await msg.reply(embed=constants.HELP_REPLY)
            return
        elif msg.content == "info":
            await msg.reply(embed=constants.INFO_REPLY)
            return
        else:
            await msg.reply(embed=constants.HELP_REPLY)
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
