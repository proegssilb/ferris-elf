import requests
import os, os.path, sys
from datetime import datetime, timedelta, timezone

from config import settings

keys = settings.aoc.tokens
aoc_base_dir = settings.aoc.inputs_dir

def get(day):
    print(f"Fetching {day}")
    day_dir = os.path.join(aoc_base_dir, str(day))
    for (label, k) in keys:
        r = requests.get(f"https://adventofcode.com/2022/day/{day}/input", cookies=dict(session=k))
        r.raise_for_status()
        if not os.path.exists(day_dir):
            os.makedirs(day_dir)
        with open(os.path.join(day_dir, f"{label}.txt"), "wb+") as f:
            f.write(r.content)

def today():
    utc = datetime.now(timezone.utc)
    offset = timedelta(hours=-5)
    return min((utc + offset).day, 25)

if len(sys.argv) > 1:
    get(int(sys.argv[1]))
else:
    get(today())
