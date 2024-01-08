import sqlite3
from typing import TYPE_CHECKING, Iterator, Literal, NewType, Optional, Self, TypeAlias, cast
from dataclasses import dataclass
# unused, caught by ruff
# import gzip

import config

if TYPE_CHECKING:
    from lib import RunResult


AdventDay: TypeAlias = Literal[
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25
]
AdventPart: TypeAlias = Literal[1, 2]

SessionLabel = NewType("SessionLabel", str)


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


class Picoseconds(int):
    __slots__ = ()

    def __str__(self) -> str:
        return format_picos(self.as_picos())

    def as_picos(self) -> int:
        return self

    def as_nanos(self) -> float:
        return self / 1000

    @classmethod
    def from_nanos(cls, v: float) -> Self:
        return cls(int(v * 1000))


@dataclass(slots=True, frozen=True)
class BenchedSubmission:
    run_id: int
    user_id: int
    run_time: Picoseconds
    code: str
    valid: bool


class GuildDatabase:
    """
    GLS (Guild Local Storage) helper class, very hard to leak data between different guilds when used
    """

    __slots__ = ("_database", "_guild")

    def __init__(self, db: "Database", guild_id: int, /) -> None:
        self._database = db
        self._guild = guild_id

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *ignore: object) -> None:
        if self._database._auto_commit:
            self._database._cursor.connection.commit()

    def set_config(self, key: str, value: str, /) -> None:
        self._database._cursor.execute(
            "REPLACE INTO guild_config (guild_id, config_name, config_value) VALUES (?, ?, ?)",
            (self._guild, key, value),
        )

    def delete_config(self, key: str) -> Optional[str]:
        old_config = self._database._cursor.execute(
            "DELETE FROM guild_config WHERE (guild_id = ? AND config_name = ?) RETURNING config_value",
            (self._guild, key),
        )

        # we have if let Some at home T-T
        if (row := old_config.fetchone()) is not None:
            return str(row[0])

        return None

    def get_config(self, key: str) -> Optional[str]:
        config = self._database._cursor.execute(
            "SELECT config_value FROM guild_config WHERE (guild_id = ? AND config_name = ?)",
            (self._guild, key),
        )

        if (row := config.fetchone()) is not None:
            return str(row[0])

        return None


def pack_day_part(day: AdventDay, part: AdventPart) -> int:
    assert 1 <= part <= 2, "part was not 1 or 2, aborting before packing causes corruption"
    return (day - 1 << 1) & (part - 1)


def unpack_day_part(packed: int) -> tuple[AdventDay, AdventPart]:
    day = (packed >> 1) + 1
    # SAFETY: (N & 1) is 0..=1, +1 becomes 1..=2, which is a valid AdventPart
    part = cast(AdventPart, (packed & 1) + 1)

    if 1 <= day <= 25:
        # SAFETY: we have asserted that day is in AdventDay range
        return cast(AdventDay, day), part
    else:
        raise ValueError("Packed value was outside valid range")


def _load_initial_schema(cur: sqlite3.Cursor) -> None:
    # enable foreign key support so that sqlite actually works how it says it does
    # seriously why is this off by default
    cur.execute("PRAGMA foreign_keys = ON")

    # everything else should be handled by dbmate


class Database:
    __slots__ = ("_cursor", "_auto_commit")

    # connection is initialized once at bot startup in this singleton
    connection: Optional[sqlite3.Connection] = None

    def __init__(self, *, auto_commit: bool = True) -> None:
        if Database.connection is None:
            # assigns both to same object
            con = Database.connection = sqlite3.connect(config.settings.db.filename)
            cur = con.cursor()
            _load_initial_schema(cur)
            con.commit()

        self._cursor: sqlite3.Cursor = Database.connection.cursor()
        self._auto_commit: bool = auto_commit

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *ignore: object) -> None:
        if self._auto_commit:
            self._cursor.connection.commit()

    def load_answers(
        self, year: int, day: AdventDay, part: AdventPart, /
    ) -> dict[SessionLabel, str]:
        """Load the expected answers for each input file."""

        raise NotImplementedError("DB implementation not finalized")

    def save_results(
        self,
        author_id: int,
        year: int,
        day: AdventDay,
        part: AdventPart,
        code: bytes,
        results: list["RunResult"],
        /,
    ) -> None:
        """
        Save the benchmark run results to the DB.
        """
        raise NotImplementedError("API needs redesign :C")

    def best_times(
        self, year: int, day: AdventDay, part: AdventPart, /
    ) -> Iterator[tuple[int, Picoseconds]]:
        """Gets the best times for a given day/part, returning a user_id+timestamp in sorted by lowest time first order"""

        # this will probably stay the same, it is a cache anyways
        query = "SELECT user, best_time FROM best_runs WHERE (year = ? AND day_part = ?) ORDER BY best_time"

        return (
            (int(user), Picoseconds(time))
            for user, time in self._cursor.execute(query, (year, pack_day_part(day, part)))
        )

    def get_user_submissions(
        self, year: int, day: int, part: int, user_id: int, /
    ) -> list[BenchedSubmission]:
        raise NotImplementedError

    def get_submission_by_id(self, submission_id: int, /) -> Optional[BenchedSubmission]:
        raise NotImplementedError

    def mark_submission_invalid(self, submission_id: int, /) -> bool:
        raise NotImplementedError

    def in_guild(self, guild_id: int, /) -> GuildDatabase:
        return GuildDatabase(self, guild_id)
