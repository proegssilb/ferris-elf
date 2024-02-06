
# Ferris Elf

A discord bot that accepts code submissions in Rust, and benchmarks them in Docker containers.

# Using the bot

The bot accepts commands implemented via Discord.py. It does listen to message contents for text-commands,
and also uses app-commands/slash-commands.

You DM the bot to submit a code segment. It replies back with the results of running the benchmark, be they
compile errors or success. Check the help for `/submit` for details.

In a Discord Server, you can use `/leaderboard`, `/lb`, or a couple other aliases in any channel the bot is in, and the bot will reply with the current leaderboard. You can use `/lb 15` to check the leaderboard for Day 15, for example.

# Running the bot

The guidelines for running the bot are a little different depending on your environment.

## Dev
If you don't have `poetry` installed, I recommend you install it via 
[pipx](https://python-poetry.org/docs/#installing-with-pipx) or [asdf](https://asdf-vm.com/).

Put a secrets file in the root of your repository (see below), and run with `poetry run python3 bot.py`.

Inputs can be fetched via `poetry run python3 ferris_elf/fetch.py -d 4`, where `-d` (required) takes which specific day to download, or defaults to the current day.

## The Secrets File
In the root of your clone of the repo, create a file named `.secrets.toml`. Copy these contents into it:

```toml
[discord]
owner_id = "01234567890123456789"
bot_token = "DiscorBotTokenGoesHere"

[docker_auth]
token = "github_token_goes_here"

[aoc_auth.tokens]
token_1_name = "deadbeefaocsession1"
token_2_name ="deadbeefaocsession2"
```

The `owner_id` is the User ID of the person who can make changes to the bot's behavior. If you don't know
who this is, it's you; pull Requests are always welcome. The bot will tell people to contact this User ID if 
there's a problem. So, if you're running the bot, your User ID goes in that spot. In Desktop Discord, enable 
Developer Mode from the settings, and then click your profile icon/username in the bottom-left to get the 
"Copy User ID" option.

The `bot_token` comes from Discord. You'll have to visit the 
[Discord developer portal](https://discord.com/developers/applications) , create an application, then visit 
Settings > Bot , and click "Reset Token" button immediately below the bot's Username to get the token.

The `token` stored in `docker_auth` is used to interact with Github's container registry. Try using a 
Personal Access Token, but an alternative token may also work.

The `aoc_auth.tokens` are session cookies from Advent of Code's website. This setting is only used by the 
fetch script; you can skip this table if you don't intend to use the fetch script. You can add as many (or as 
few) tokens as you like. The name (left of the equals) will be used to name the input files when they're 
downloaded, and the value is the session cookie's value itself.

## Production
We're still working on this. Our recommendation is a VM optimized for minimum interruptions. While this app 
is not Dockerized yet, it shouldn't be too hard to write up a Dockerfile for the app, assuming you can set up 
a Docker HTTP API or Docker-in-Docker. Using a container means you don't have to optimize the VM.

Once you have the sandbox, make sure to put the following in order:

  - The only supported method of running the bot (for now) is via poetry. Install as per the dev instructions.
  - Set up a dedicated user just for the bot, with a home directory (for rootless docker).
  - Make sure the bot has access to Rootless Docker. The bot will be running untrusted code in docker containers, so
    harden it.
  - Clone the repo into the bot user's home directory.
  - Edit the `settings.toml` and `.secrets.toml` files for your environment. There are two valid places to 
    put them:
    - In the repository root
    - In `$HOME/.config/ferris-elf`
  - Run `./ops/install-systemd-svcs.sh` in order to install the systemd scripts to the current user's 
    systemd.
  - Enable systemd linger for the bot user.
  - Start the bot via the `ferris-elf-bot.service`, installed in user systemd.

Note that data is stored in sqlite, so that does impact how you do backups.

# Support

This bot is under active development. We cannot offer formal support at this time. If you're able to 
troubleshoot at a source code level, feel free to file issues if you can identify what's going on in the app 
code, or have detailed Steps to Reproduce that you can share in an issue.

We do welcome pull requests!