#!/bin/env python
"""
A wrapper around dbmate that uses this projects settings to automatically set the database location parameter
dbmate can be found at: https://github.com/amacneil/dbmate
"""

# NOTE: This script is run in ops/update.sh

from ferris_elf.config import settings

import subprocess
import sys


def main(args: list[str]) -> int:
    dbfile = f"sqlite:{settings.db.filename}"
    # cut off our program name
    args = args[1:]

    return subprocess.run(["dbmate", "--url", dbfile, *args]).returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv))
