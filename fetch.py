import requests
import os, os.path, sys

from config import settings
from lib import today

keys = settings.aoc_auth.tokens
aoc_base_dir = settings.aoc.inputs_dir


def get(day):
    print(f"Fetching {day}")
    day_dir = os.path.join(aoc_base_dir, str(day))
    for label, k in keys.items():
        r = requests.get(f"https://adventofcode.com/2022/day/{day}/input", cookies=dict(session=k))
        r.raise_for_status()
        if not os.path.exists(day_dir):
            os.makedirs(day_dir)
        with open(os.path.join(day_dir, f"{label}.txt"), "wb+") as f:
            f.write(r.content)


if len(sys.argv) > 1:
    get(int(sys.argv[1]))
else:
    get(today())
