from typing import Literal
import discord
from .config import settings

SUPPORTED_BENCH_FORMAT: int = 1

HELP_REPLY = discord.Embed(
    title="Ferris Elf help page",
    color=0xE84611,
    description=f"""
**help** - Send this message
**info** - Some useful information about benchmarking
**best _[day]_ _[part]_** - Best times so far for a day
**submit _[day]_ _[part]_ <attachment>** - Benchmark attached code

If [_day_] and/or [_part_] is ommited, they are assumed to be today and part 1

{settings.discord.support_info}""",
)

INFO_REPLY = discord.Embed(
    title="Benchmark information",
    color=0xE84611,
    description=f"""**Submissions**
When sending code for a benchmark, you should make sure it looks like this:

```rs
pub fn run(input: &str) -> i64 {{
    0
}}
```

Input can be either a &str or a &[u8], which ever you prefer. The return should \
be the solution to the day and part.

Rust version is {{settings.discord.rust_version_info}}.

**Available dependencies**

```toml
bytemuck = "1"
itertools = "0.10"
rayon = "1"
regex = "1"
parse-display = "0.6"
memchr = "2"
arrayvec = "0.7"
smallvec = "1"
rustc-hash = "1"
bitvec = "1"
dashmap = "5"
btoi = "0.4"
nom = "7"
ascii = "1.1.0"
```

Check back often as the available dependencies are bound to change over the course of AOC. \
If you want a dependency added, ping <@{settings.discord.owner_id}> asking them to add it.

**Methodology**
We use Criterion to benchmark, with the input black-boxed via Criterion's `black_box`. \
Submissions may be manually reviewed. Criterion provides a few ways to estimate the runtime. \
Currently, we save what Criterion reports as the 'median', but it is on our to-do list to \
review this choice.

**Hardware**
{settings.discord.hw_info}


Be kind and do not abuse :)""",
)

LEADERBOARD_FOOTER = "Need help? DM me /help or /info to get started."

# Type checking needs to be told this is a literal (and the exact value), else
# it just assumes an int.
MAX_DAY: Literal[25] = 25
