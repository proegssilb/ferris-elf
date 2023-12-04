import docker
import discord
import asyncio
from sqlite4 import SQLite4
import io
import functools
from os import listdir
from os.path import isfile, join
from datetime import datetime, timedelta, timezone

from config import settings

doc = docker.from_env()
db = SQLite4(settings.db.filename)
db.connect()

cur = db.cursor()
cur.execute("""CREATE TABLE IF NOT EXISTS runs
    (user TEXT, code TEXT, day INTEGER, part INTEGER, time REAL, answer INTEGER, answer2)""")
cur.execute("""CREATE TABLE IF NOT EXISTS solutions
    (key TEXT, day INTEGER, part INTEGER, answer INTEGER, answer2)""")
db.commit()

def today():
    utc = datetime.now(timezone.utc)
    offset = timedelta(hours=-5)
    return min((utc + offset).day, 25)

async def build_image(msg, solution):
    print(f"Building for {msg.author.name}")
    status = await msg.reply("Building...")
    with open("runner/src/code.rs", "wb+") as f:
        f.write(solution)

    loop = asyncio.get_event_loop()

    try:
        await loop.run_in_executor(None, functools.partial(doc.images.build, path="runner", tag=f"ferris-elf-{msg.author.id}"))
        return True
    except docker.errors.BuildError as err:
        print(f"Build error: {err}")
        e = ""
        for chunk in err.build_log:
            e += chunk.get("stream") or ""
        await msg.reply(f"Error building benchmark: {err}", file=discord.File(io.BytesIO(e.encode("utf-8")), "build_log.txt"))
        return False
    finally:
        await status.delete()

async def run_image(msg, input):
    print(f"Running for {msg.author.name}")
    # input = ','.join([str(int(x)) for x in input])
    status = await msg.reply("Running benchmark...")
    loop = asyncio.get_event_loop()
    try:
        out = await loop.run_in_executor(None, functools.partial(doc.containers.run, f"ferris-elf-{msg.author.id}", f"timeout 60 ./target/release/ferris-elf", environment=dict(INPUT=input), remove=True, stdout=True, mem_limit="24g", network_mode="none"))
        out = out.decode("utf-8")
        print(out)
        return out
    except docker.errors.ContainerError as err:
        print(f"Run error: {err}")
        await msg.reply(f"Error running benchmark: {err}", file=discord.File(io.BytesIO(err.stderr), "stderr.txt"))
    finally:
        await status.delete()

def avg(l):
    return sum(l) / len(l)

def ns(v):
    if v > 1e9:
        return f"{v / 1e9:.2f}s"
    if v > 1e6:
        return f"{v / 1e6:.2f}ms"
    if v > 1e3:
        return f"{v / 1e3:.2f}µs"
    return f"{v:.2f}ns"

async def benchmark(msg, code, day, part):
    build = await build_image(msg, code)
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
        out = await run_image(msg, input)
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

class MyBot(discord.Client):
    queue = asyncio.Queue()

    async def on_ready(self):
        print("Logged in as", self.user)

        while True:
            try:
                msg = await self.queue.get()
                print(f"Processing request for {msg.author.name}")
                code = await msg.attachments[0].read()
                parts = [p for p in msg.content.split(" ") if p]
                day = int((parts[0:1] or (today(), ))[0])
                part = int((parts[1:2] or (1, ))[0])

                await benchmark(msg, code, day, part)

                self.queue.task_done()
            except Exception as err:
                print("Queue loop exception!", err)

    async def on_message(self, msg):
        if msg.author.bot:
            return

        if msg.content.startswith("best") or msg.content.startswith("aoc"):
            parts = msg.content.split(" ")
            day = int((parts[1:2] or (today(), ))[0])
            print(f"Best for d {day}")

            part1 = ""
            for (user, time) in db.cursor().execute("""SELECT user, MIN(time) FROM runs
WHERE day = ? AND part = 1
GROUP BY user
order by time""", (day, )):
                if user is None or time is None:
                    continue
                user = int(user)
                print(user, time)
                user = self.get_user(user) or await self.fetch_user(user)
                if user:
                    part1 += f"\t{user.name}: **{ns(time)}**\n"
            part2 = ""
            for (user, time) in db.cursor().execute("""SELECT user, MIN(time) FROM runs
WHERE day = ? AND part = 2
GROUP BY user
order by time""", (day, )):
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

        if not isinstance(msg.channel, discord.DMChannel):
            return
        
        if msg.content == "help":
            await msg.reply(embed=discord.Embed(title="Ferris Elf help page", color=0xE84611, description="""
**help** - Send this message
**info** - Some useful information about benchmarking
**best _[day]_** - Best times so far
**_[day]_ _[part]_ <attachment>** - Benchmark attached code

If [_day_] and/or [_part_] is ommited, they are assumed to be today and part 1

Message <@{}> for any questions"""))
            return

        if msg.content == "info":
            await msg.reply(embed=discord.Embed(title="Benchmark information", color=0xE84611, description="""
When sending code for a benchmark, you should make sure it looks like.
```rs
pub fn run(input: &str) -> i64 {
    0
}
```

Input can be either a &str or a &[u8], which ever you prefer. The return should \
be the solution to the day and part. 

Rust version is latest Docker nightly
**Available dependencies**
```toml
bytemuck = "1"
itertools = "0.10"
rayon = "1"
regex = "1"
parse-display = "0.6"
memchr = "2"
core_simd = { git = "https://github.com/rust-lang/portable-simd" }
arrayvec = "0.7"
smallvec = "1"
rustc-hash = "1"
bitvec = "1"
dashmap = "5"
atoi_radix10 = { git = "https://github.com/gilescope/atoi_radix10" }
btoi = "0.4"
```
Check back often as the available dependencies are bound to change over the course of AOC.
If you want a dependency added, ping <@{}> asking them to add it.

**Hardware**
{}


Be kind and do not abuse :)"""))
            return

        if len(msg.attachments) == 0:
            await msg.reply("Please provide the code as a file attachment")
            return

        if not self.queue.empty():
            await msg.reply("Benchmark queued...")

        print("Queued for", msg.author, "(Queue length)", self.queue.qsize())
        self.queue.put_nowait(msg)

bot = MyBot()
bot.run(settings.discord.bot_token)
