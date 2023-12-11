from datetime import datetime
import logging
import os, os.path, sys
from zoneinfo import ZoneInfo

import requests

from config import settings
from lib import today

keys = settings.aoc_auth.tokens
aoc_base_dir = settings.aoc.inputs_dir


logger = logging.getLogger(__name__)


def get(day):
    logger.info("Fetching input for day %s", day)
    day_dir = os.path.join(aoc_base_dir, str(day))
    year = datetime.now(tz=ZoneInfo("America/New_York")).year
    for label, k in keys.items():
        r = requests.get(
            f"https://adventofcode.com/{year}/day/{day}/input", cookies=dict(session=k)
        )
        r.raise_for_status()
        if not os.path.exists(day_dir):
            os.makedirs(day_dir)
        with open(os.path.join(day_dir, f"{label}.txt"), "wb+") as f:
            f.write(r.content)


if __name__ == "__main__":
    logging.basicConfig(encoding="utf-8", level=logging.INFO)
    if len(sys.argv) > 1:
        get(int(sys.argv[1]))
    else:
        get(today())
