# These are defined here instead of in the bot to avoid a circular import 
from dataclasses import dataclass
from datetime import datetime, timezone

# Messages currently supported:
# Submit <code as file>, <day num>, <part num>        : /submit <code> <day> <part>
# Help:                                               : /help
# Info:                                               : /info
# Get Best Times / Leaders for a day (optional partt) : /best <day> <optional: part> (alias: /leader)

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
            part = int(parts[2]) if len(parts) > 2 else 1
            return GetBestTimesMessage(msg,day,part)
        except Exception as e:
            raise e

    def query():
        query = f"""SELECT user, MIN(time) FROM runs WHERE day = ? AND part = ?
           GROUP BY user ORDER BY time"""
        return query
    
@dataclass
class HelpMessage():
    pass
@dataclass
class InfoMessage():
    pass

def today():
    utc = datetime.now(timezone.utc)
    offset = datetime.timedelta(hours=-5)
    return min((utc + offset).day, 25)