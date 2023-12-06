import asyncio
import functools

import docker
from config import settings

doc = docker.from_env()
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
