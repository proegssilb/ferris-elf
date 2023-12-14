from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import discord

import constants

# Messages defined here:
# Submit                                              : /submit <code> <day> <part>
# Help:                                               : /help
# Info:                                               : /info
# Leaderboard                                         : /best <day> <part>


@dataclass
class SubmitMessage:
    msg: discord.Message
    code: bytes
    day: int
    part: int

    @staticmethod
    def parse(msg: discord.Message, first_attachment: bytes):
        parts = [p for p in msg.content.split(" ") if p]
        day = int(parts[1]) if len(parts) > 1 else today()
        part = int(parts[2]) if len(parts) > 2 else 1
        if day < 1 or day > constants.MAX_DAY or part < 1 or part > 2:
            raise Exception(f"day/part out of bounds: {day} {part}")
        return SubmitMessage(msg, first_attachment, day, part)


@dataclass
class GetBestTimesMessage:
    msg: discord.Message
    day: int
    part: int

    @staticmethod
    def parse(msg):
        parts = [p for p in msg.content.split(" ") if p]
        day = int(parts[1]) if len(parts) > 1 else today()
        part = int(parts[2]) if len(parts) > 2 else 0  # 0 represents both parts
        if day < 1 or day > constants.MAX_DAY or part < 0 or part > 2:
            raise Exception(f"day/part out of bounds: {day} {part}")
        return GetBestTimesMessage(msg, day, part)


@dataclass
class HelpMessage:
    pass


@dataclass
class InfoMessage:
    pass


def today():
    utc = datetime.now(timezone.utc)
    offset = timedelta(hours=-5)
    return min((utc + offset).day, constants.MAX_DAY)
