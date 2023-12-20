import discord

import config

HELP_REPLY = discord.Embed(
    title="Ferris Elf help page",
    color=0xE84611,
    description=f"""
**help** - Send this message
**info** - Some useful information about benchmarking
**best _[day]_ _[part]_** - Best times so far for a day
**submit _[day]_ _[part]_ <attachment>** - Benchmark attached code

If [_day_] and/or [_part_] is ommited, they are assumed to be today and part 1

Message <@{config.settings.discord.owner_id}> for any questions""",
)

INFO_REPLY = discord.Embed(
    title="Benchmark information",
    color=0xE84611,
    description="""
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


Be kind and do not abuse :)""",
)

MAX_DAY = 25
