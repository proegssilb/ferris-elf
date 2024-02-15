# NOTE: this is called in ops/systemd/ferris-elf-fetch.service
# any changes to the CLI api should be reflected there

import logging
import argparse
from typing import cast

import requests

from ferris_elf import lib
from ferris_elf.config import settings
from ferris_elf.lib import today
from ferris_elf.database import AdventDay, Database, Year

keys = settings.aoc_auth.tokens


logger = logging.getLogger(__name__)


def get(year: Year, day: AdventDay) -> None:
    logger.info("Fetching input for day %s", day)

    for label, k in keys.items():
        r = requests.get(
            f"https://adventofcode.com/{year}/day/{day}/input", cookies=dict(session=k)
        )
        r.raise_for_status()

        # require utf8 response
        content = r.content.decode("utf8")

        with Database() as db:
            db.insert_input(label, year, day, content)


def split_yd(data: str) -> tuple[Year, AdventDay]:
    res = data.split(":")

    if len(res) == 2:
        yd = int(res[0]), int(res[1])
    elif res:
        yd = lib.year(), int(res[0])
    else:
        raise RuntimeError("Unreachable!")

    assert 1 <= yd[1] <= 25, "day not within valid range (1..=25)"

    # SAFETY: just asserted above that yd[1] is in valid range
    return cast(tuple[Year, AdventDay], yd)


if __name__ == "__main__":
    logging.basicConfig(encoding="utf-8", level=logging.INFO)

    parser = argparse.ArgumentParser("aoc-fetch")
    parser.add_argument(
        "--download",
        "-d",
        const=str(today()),
        nargs="?",
        required=True,
        help="download all inputs for a given day, defaults to current year and day, pass day or year:day to override",
    )

    parsed = parser.parse_args()

    year, day = split_yd(parsed.download)

    get(year, day)
