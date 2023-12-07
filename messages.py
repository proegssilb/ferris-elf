# These are defined here instead of in the bot to avoid a circular import 
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

from constants import MAX_DAY

# Messages currently supported:
# Submit                                              : /submit <code> <day> <part>
# Help:                                               : /help
# Info:                                               : /info
# Leaderboard                                         : /best <day> <part>

@dataclass
class SubmitMessage():
    msg: object
    code: str
    day: int
    part: int

    def parse(msg):
        try:
            code = msg.attachments[0].read()
            parts = [p for p in msg.content.split(" ") if p]
            day = int(parts[1])
            part = int(parts[2])
            if day < 1 or day > MAX_DAY or part < 1 or part > 2:
                raise Exception(f"day/part out of bounds: {day} {part}")
            return SubmitMessage(msg,code,day,part)
        except Exception as e:
            raise e
@dataclass
class GetBestTimesMessage():
    msg: object
    day: int
    part: int

    def parse(msg):
        try:
            parts = [p for p in msg.content.split(" ") if p]
            day = int(parts[1]) if len(parts) > 1 else today()
            part = int(parts[2]) if len(parts) > 2 else 0 #0 represents both parts
            if day < 1 or day > MAX_DAY or part < 0 or part > 2:
                raise Exception(f"day/part out of bounds: {day} {part}")
            return GetBestTimesMessage(msg,day,part)
        except Exception as e:
            raise e

@dataclass
class HelpMessage():
    pass
@dataclass
class InfoMessage():
    pass

def today():
    utc = datetime.now(timezone.utc)
    offset = timedelta(hours=-5)
    return min((utc + offset).day, 25)