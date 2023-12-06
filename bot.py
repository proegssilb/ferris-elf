import discord
import asyncio
import sqlite3


from os import listdir
from os.path import isfile, join
from datetime import datetime, timedelta, timezone

import lib
from dataclasses import dataclass
from config import settings
import constants


db = sqlite3.connect(settings.db.filename)

cur = db.cursor()
cur.execute("""CREATE TABLE IF NOT EXISTS runs
    (user TEXT, code TEXT, day INTEGER, part INTEGER, time REAL, answer INTEGER, answer2)""")
cur.execute("""CREATE TABLE IF NOT EXISTS solutions
    (key TEXT, day INTEGER, part INTEGER, answer INTEGER, answer2)""")
db.commit()


   
async def benchmark(msg, code, day, part):
    build = await lib.build_image(msg, code)
    if not build:
        return

    day_path = f"{day}/"
    try:
        onlyfiles = [f for f in listdir(day_path) if isfile(join(day_path, f))]
    except:
        await msg.reply(f"Failed to read input files for day {day}, part {part}")
        return

    verified = False
    results = []
    for (i, file) in enumerate(onlyfiles):
        rows = db.cursor().execute("SELECT answer2 FROM solutions WHERE key = ? AND day = ? AND part = ?", (file, day, part))
        verify = None
        for row in rows:
            print("Verify", row[0], "file", file)
            verify = str(row[0]).strip()

        with open(join(day_path, file), "r") as f:
            input = f.read()

        status = await msg.reply(f"Benchmarking input {i+1}")
        out = await lib.run_image(msg, input)
        if not out:
            return
        await status.delete()

        result = {}
        for line in out.splitlines():
            if line.startswith("FERRIS_ELF_ANSWER "):
                result["answer"] = str(line[18:]).strip()
            if line.startswith("FERRIS_ELF_MEDIAN "):
                result["median"] = int(line[18:])
            if line.startswith("FERRIS_ELF_AVERAGE "):
                result["average"] = int(line[19:])
            if line.startswith("FERRIS_ELF_MAX "):
                result["max"] = int(line[15:])
            if line.startswith("FERRIS_ELF_MIN "):
                result["min"] = int(line[15:])

        if verify:
            if not result["answer"] == verify:
                await msg.reply(f"Error: Benchmark returned wrong answer for input {i + 1}")
                return
            verified = True
        else:
            print("Cannot verify run", result["answer"])

        cur.execute("INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?)", (str(msg.author.id), code, day, part, result["median"], result["answer"], result["answer"]))
        results.append(result)
    

    median = avg([r["median"] for r in results])
    average = avg([r["average"] for r in results])

    if verified:
        await msg.reply(embed=discord.Embed(title="Benchmark complete", description=f"Median: **{ns(median)}**\nAverage: **{ns(average)}**"))
    else:
        await msg.reply(embed=discord.Embed(title="Benchmark complete (Unverified)", description=f"Median: **{ns(median)}**\nAverage: **{ns(average)}**"))

    db.commit()
    print("Inserted results into DB")

def today():
    utc = datetime.now(timezone.utc)
    offset = timedelta(hours=-5)
    return min((utc + offset).day, 25)

@dataclass
class SubmitMessage:
    msg: object #TODO
    code: str
    day: int
    part: int

    async def parse(msg):
        code = await msg.attachments[0].read()
        parts = [p for p in msg.content.split(" ") if p]
        day = int((parts[0:1] or (today(), ))[0])
        part = int((parts[1:2] or (1, ))[0])
        return SubmitMessage(msg,code,day,part)

@dataclass
class GetBestTimesMessage:
    msg: object
    day: int
    part: int

    def parse(msg):
        parts = [p for p in msg.content.split(" ") if p]
        day = int((parts[1:2] or (today(), ))[0])
        part = int((parts[2:3] or (1, ))[0])
        return GetBestTimesMessage(msg,day,part)

    def query():
        query = f"""SELECT user, MIN(time) FROM runs WHERE day = ? AND part = ?
           GROUP BY user ORDER BY time"""
        return query

class HelpMessage:
    msg: object

class MyBot(discord.Client):
    queue = asyncio.Queue()

    async def on_ready(self):
        print("Logged in as", self.user)
        while True:
            try:
                msg = await self.queue.get()
                print(f"Processing request for {msg.author.name}")
                submit_msg = SubmitMessage.parse(msg)
                await benchmark(submit_msg)
                self.queue.task_done()
            except Exception as err:
                print("Queue loop exception!", err)

    async def handle_best_times_message(self, msg):
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
        embed = discord.Embed(title=f"Top 10 fastest toboggans for day {day}", color=0xE84611)
        if part1:
            embed.add_field(name="Part 1", value=part1, inline=True)
        if part2:
            embed.add_field(name="Part 2", value=part2, inline=True)
        await msg.reply(embed=embed)
        return

    async def on_message(self, msg):
        if msg.author.bot:
            return
        
        print("Message received from", msg.author.name)
        if msg.content.startswith("best") or msg.content.startswith("aoc"):
            await self.handle_best_times_message(msg)
            return

        print("Msg content: " + msg.content)
        if not isinstance(msg.channel, discord.DMChannel):
            return
        
        if msg.content == "help":
            await msg.reply(embed=constants.HELP_REPLY)
            return

        if msg.content == "info":
            await msg.reply(embed=constants.INFO_REPLY)
            return

        if len(msg.attachments) == 0:
            await msg.reply("Please provide the code as a file attachment")
            return

        if not self.queue.empty():
            await msg.reply("Benchmark queued...")

        print("Queued for", msg.author, "(Queue length)", self.queue.qsize())
        self.queue.put_nowait(msg)

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
intents.guild_messages = True
intents.dm_messages = True
intents.typing = False
intents.presences = False

bot = MyBot(intents=intents)
bot.run(settings.discord.bot_token)
