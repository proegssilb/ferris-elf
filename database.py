import sqlite3
from typing import TYPE_CHECKING, Iterator, Optional
from dataclasses import dataclass

import config

if TYPE_CHECKING:
    from lib import RunResult


def format_picos(ts: float | int) -> str:
    timestamp = float(ts)

    base = "ps"
    scalar: list[tuple[str, int]] = [
        ("ns", 1000),
        ("µs", 1000),
        ("ms", 1000),
        ("s", 1000),
        ("m", 60),
        ("h", 60),
    ]

    for name, offset in scalar:
        if timestamp > offset:
            timestamp /= offset
            base = name
        else:
            break

    # remove any trailing stuff
    timestamp = round(timestamp, 2)

    if timestamp.is_integer():
        return f"{timestamp:.0f}{base}"
    else:
        return f"{timestamp:.2f}{base}"


class Nanoseconds(float):
    __slots__ = ()

    def __str__(self) -> str:
        return format_picos(self.as_picos())

    def as_picos(self) -> int:
        return int(self * 1000)

    def as_nanos(self) -> float:
        return self


class Picoseconds(int):
    __slots__ = ()

    def __str__(self) -> str:
        return format_picos(self.as_picos())

    def as_picos(self) -> int:
        return self

    def as_nanos(self) -> float:
        return self / 1000


@dataclass(slots=True, frozen=True)
class BenchedSubmission:
    run_id: int
    user_id: int
    run_time: Nanoseconds | Picoseconds
    code: str
    valid: bool


class GuildDatabase:
    __slots__ = ("_database", "_guild")

    def __init__(self, db: "Database", guild_id: int) -> None:
        self._database = db
        self._guild = guild_id

    def __enter__(self) -> "GuildDatabase":
        return self

    def __exit__(self, *ignore: object) -> None:
        if self._database._auto_commit:
            self._database._cursor.connection.commit()

    def set_config(self, key: str, value: str) -> None:
        raise NotImplementedError

    def delete_config(self, key: str) -> Optional[str]:
        raise NotImplementedError

    def get_config(self, key: str) -> Optional[str]:
        raise NotImplementedError


# connection is a static variable that is shared across all instances of DB
# so we reuse the same connection across all users of this class
class Database:
    __slots__ = ("_cursor", "_auto_commit")

    connection: Optional[sqlite3.Connection] = None

    def __init__(self, *, auto_commit: bool = True) -> None:
        if Database.connection is None:
            Database.connection = sqlite3.connect(config.settings.db.filename)
            cur = Database.connection.cursor()
            cur.execute(
                """CREATE TABLE IF NOT EXISTS runs
                (user TEXT, code TEXT, day INTEGER, part INTEGER, time REAL, answer INTEGER, answer2)"""
            )
            cur.execute(
                """CREATE TABLE IF NOT EXISTS solutions
                (key TEXT, day INTEGER, part INTEGER, answer INTEGER, answer2)"""
            )
            Database.connection.commit()

        self._cursor = Database.connection.cursor()
        self._auto_commit = auto_commit

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, *ignore: object) -> None:
        if self._auto_commit:
            self._cursor.connection.commit()

    # TODO(ultrabear): the current backend has no year concept, but this PR is for the API change first
    def load_answers(self, _year: int, day: int, part: int, /) -> dict[str, str]:
        """Load the expected answers for each input file."""

        rows = self._cursor.execute(
            "SELECT key, answer2 FROM solutions WHERE day = ? AND part = ?",
            (day, part),
        )

        answer_map = {}
        for r in rows:
            (key, answer) = r
            answer_map[key] = answer

        return answer_map

    def save_results(
        self,
        author_id: int,
        _year: int,
        day: int,
        part: int,
        code: bytes,
        results: list["RunResult"],
        /,
    ) -> None:
        """
        Save the benchmark run results to the DB.
        """

        str_code = code.decode()
        db_results = [
            (
                str(author_id),
                str_code,
                day,
                part,
                r.median,
                int(r.answer) if isinstance(r.answer, int) or r.answer.isdigit() else None,
                r.answer,
            )
            for r in results
        ]

        query = "INSERT INTO runs(user, code, day, part, time, answer, answer2) VALUES (?, ?, ?, ?, ?, ?, ?)"

        self._cursor.executemany(query, db_results)

    def best_times(
        self, _year: int, day: int, part: int, /
    ) -> Iterator[tuple[int, Nanoseconds | Picoseconds]]:
        """Gets the best times for a given day/part, returning a user_id+timestamp in sorted by lowest time first order"""

        query = """SELECT user, MIN(time) FROM runs WHERE day = ? AND part = ?
           GROUP BY user ORDER BY time"""

        return (
            (int(user), Nanoseconds(time))
            for user, time in self._cursor.execute(query, (day, part))
            if user is not None and time is not None
        )

    def get_user_submissions(
        self, year: int, day: int, part: int, user_id: int
    ) -> list[BenchedSubmission]:
        raise NotImplementedError

    def get_submission_by_id(self, submission_id: int) -> Optional[BenchedSubmission]:
        raise NotImplementedError

    def mark_submission_invalid(self, submission_id: int) -> bool:
        raise NotImplementedError

    def in_guild(self, guild_id: int) -> GuildDatabase:
        return GuildDatabase(self, guild_id)
