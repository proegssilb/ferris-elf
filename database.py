import sqlite3
from typing import TYPE_CHECKING, Iterator, Literal, NewType, Optional, Self, TypeAlias, cast
from dataclasses import dataclass
import gzip
import statistics

import config

if TYPE_CHECKING:
    from lib import RunResult


AdventDay: TypeAlias = Literal[
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25
]
AdventPart: TypeAlias = Literal[1, 2]

SessionLabel = NewType("SessionLabel", str)
SubmissionId = NewType("SubmissionId", int)


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

    # fun awesome fact, int decays to float in typeck directly,
    # but is_integer is only implemented on float so if we didn't
    # explicitly call timestamp = float(ts), this could break
    # and typeck would be ok with it :D
    if timestamp.is_integer():
        return f"{timestamp:.0f}{base}"
    else:
        return f"{timestamp:.2f}{base}"


class Picoseconds(int):
    __slots__ = ()

    def __repr__(self) -> str:
        return f"Picoseconds({int(self)})"

    def __str__(self) -> str:
        return format_picos(self.as_picos())

    def as_picos(self) -> int:
        return self

    def as_nanos(self) -> float:
        return self / 1000

    @classmethod
    def from_nanos(cls, v: float) -> Self:
        return cls(int(v * 1000))

    @classmethod
    def from_picos(cls, v: int) -> Self:
        return cls(v)


@dataclass(slots=True, frozen=True)
class BenchedSubmission:
    run_id: int
    user_id: int
    run_time: Picoseconds
    code: str
    valid: bool


class ContainerVersionError(Exception):
    __slots__ = ()


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
        """Load the expected answers for each input file, if they exist"""

        # apply a literal here to avoid potential future runtime pollution
        checkpart: Literal["answer_p1", "answer_p2"] = "answer_p1" if part == 1 else "answer_p2"

        result = {
            SessionLabel(label): str(ans)
            for label, ans in self._cursor.execute(
                f"SELECT session_label, {checkpart} FROM inputs WHERE (year = ? AND day = ? AND {checkpart} IS NOT NULL)",
                (year, day),
            )
        }

        return result

    def save_submission(
        self, author_id: int, year: int, day: AdventDay, part: AdventPart, code: bytes, /
    ) -> SubmissionId:
        """
        Saves a benchmark submission to the database
        this will insert a NULL into the average_time field,
        it should be filled when all benchmarks are completed

        Returns the unique SubmissionId that was generated for this submission
        """

        # TODO(ultrabear): assuming we are using the latest container
        # version is probably ok maybe but its also kinda bad
        # we should discuss this sometime idk
        container_v = self._cursor.execute("SELECT MAX(id) FROM container_versions").fetchone()

        if container_v is None:
            raise ContainerVersionError("No container versions are initialized in the database")

        compressed = gzip.compress(code)

        # unnamed fields are filled with default types
        rowid = self._cursor.execute(
            "INSERT INTO submissions (user, year, day_part, code, bencher_version) VALUES (?, ?, ?, ?, ?)",
            (str(author_id), year, pack_day_part(day, part), compressed, container_v),
        ).lastrowid

        # must be non null after successful .execute call
        assert rowid is not None

        return SubmissionId(rowid)

    def save_bench_result(
        self,
        submission_id: SubmissionId,
        input_used: SessionLabel,
        avg_time: Picoseconds,
        answer: str,
        /,
    ) -> Optional[bool]:
        """
        Saves result of a benchmarking run to the database, returns
        True if answer was valid, False if it was not valid, and None if the answer
        was not available to check
        """

        self._cursor.execute(
            "INSERT INTO benchmark_runs (submission, session_label, average_time, answer) VALUES (?, ?, ?, ?)",
            (submission_id, input_used, avg_time.as_picos(), answer),
        )

        # TODO(ultrabear): we should also add answer validity checks here, and process_submission_average_time should take that into account

        return None

    def process_submission_average_time(self, submission_id: SubmissionId, /) -> None:
        """
        Processes a submissions average time based on all benched results,
        updating the submissions table in the database, this will also update best_runs

        This shuold be called once all benchmarks for this submission have completed
        """

        # assumption: floats have a mantissa of 53 bits, we lock submissions to a max of 1s
        # 1s is approximately 40 bits, therefore we lose no single picosecond precision in
        # this calculation. Even if we did lose some precision, that is ok because we only
        # care about the most significant parts of the benchmark result anyways, i/e if
        # two solutions are taking 100s of microseconds each, its not changing much if
        # the picoseconds are not perfect, in this way floats are well suited to what we are doing
        picos = statistics.mean(
            float(avg)
            for (avg,) in self._cursor.execute(
                "SELECT average_time FROM benchmark_runs WHERE (submission = ?)", (submission_id,)
            )
        )

        rounded = int(round(picos))

        self._cursor.execute(
            "UPDATE submissions SET average_time = ? WHERE submission_id = ?",
            (rounded, submission_id),
        )

        # TODO(ultrabear): also update best_runs based on validity

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

        Legacy API, future code should call save_submission,
        asynchronously save_bench_result for each bench,
        and then finish with process_submission_average_time
        """

        id = self.save_submission(author_id, year, day, part, code)

        for res in results:
            self.save_bench_result(id, res.from_session, res.median, str(res.answer))

        self.process_submission_average_time(id)

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
        self, year: int, day: AdventDay, part: AdventPart, user_id: int, /
    ) -> list[BenchedSubmission]:
        raise NotImplementedError

    def get_submission_by_id(self, submission_id: SubmissionId, /) -> Optional[BenchedSubmission]:
        raise NotImplementedError

    def mark_submission_invalid(self, submission_id: SubmissionId, /) -> bool:
        raise NotImplementedError

    def in_guild(self, guild_id: int, /) -> GuildDatabase:
        return GuildDatabase(self, guild_id)
