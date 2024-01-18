import datetime
import sqlite3
from typing import (
    TYPE_CHECKING,
    Iterator,
    Literal,
    NewType,
    Optional,
    Self,
    TypeAlias,
    TypeVar,
    cast,
)
from dataclasses import dataclass
import gzip

import config

if TYPE_CHECKING:
    from lib import RunResult


AdventDay: TypeAlias = Literal[
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25
]
AdventPart: TypeAlias = Literal[1, 2]

SessionLabel = NewType("SessionLabel", str)
SubmissionId = NewType("SubmissionId", int)
Year = NewType("Year", int)
ContainerVersionId = NewType("ContainerVersionId", int)


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
class BenchmarkRun:
    submission: SubmissionId
    run_time: Picoseconds
    label: SessionLabel
    answer: str
    completed_at: datetime.datetime


@dataclass(slots=True, frozen=True)
class Submission:
    id: SubmissionId
    user_id: int
    year: Year
    day: AdventDay
    part: AdventPart
    average_time: Optional[Picoseconds]
    code: str
    valid: bool
    submitted_at: datetime.datetime
    bencher_version: ContainerVersionId
    benchmark_format: int
    benches: list[BenchmarkRun]


class ContainerVersionError(Exception):
    __slots__ = ()


_T = TypeVar("_T")


def _unwrap(v: Optional[_T], _typ: type[_T], msg: Optional[object] = None) -> _T:
    class NoneUnwrapError(Exception):
        __slots__ = ()

    if v is None:
        if msg is None:
            raise NoneUnwrapError("unwrapped on a None value")
        else:
            raise NoneUnwrapError(msg)

    return v


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
    return (day - 1 << 1) | (part - 1)


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


@dataclass(slots=True)
class AocInput:
    year: Year
    day: AdventDay
    label: SessionLabel
    data: str
    p1_answer: Optional[str]
    p2_answer: Optional[str]


def dt_from_unix(unix: int) -> datetime.datetime:
    return datetime.datetime.fromtimestamp(unix, tz=datetime.timezone.utc)


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
        self, year: Year, day: AdventDay, part: AdventPart, /
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
        self,
        author_id: int,
        year: Year,
        day: AdventDay,
        part: AdventPart,
        code: bytes,
        container_v: ContainerVersionId,
        benchmark_format: int,
        /,
    ) -> SubmissionId:
        """
        Saves a benchmark submission to the database
        this will insert a NULL into the average_time field,
        it should be filled when all benchmarks are completed

        Returns the unique SubmissionId that was generated for this submission
        """

        compressed = gzip.compress(code)

        # unnamed fields are filled with default types
        rowid = self._cursor.execute(
            "INSERT INTO submissions (user, year, day_part, code, bencher_version, benchmark_format) VALUES (?, ?, ?, ?, ?)",
            (
                str(author_id),
                year,
                pack_day_part(day, part),
                compressed,
                container_v,
                benchmark_format,
            ),
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

        year, day_part = _unwrap(
            self._cursor.execute(
                "SELECT year, day_part FROM submissions WHERE submission_id = ?", (submission_id,)
            ).fetchone(),
            tuple[int, int],
            "submission_id did not exist in database",
        )

        # for some reason mypy loses its beans and thinks year and day_part
        # are not ints, despite the fact we said they were above, by using type-ignore
        # mypy will warn us in the future when this is not needed
        day, part = unpack_day_part(day_part)  # type: ignore[arg-type]

        part_lit: Literal["answer_p1", "answer_p2"] = "answer_p1" if part == 1 else "answer_p2"

        # this should always return a result, but the inner row value may be None
        (known_answer,) = _unwrap(
            self._cursor.execute(
                f"SELECT {part_lit} FROM inputs WHERE (session_label = ? AND year = ? AND day = ?)",
                (input_used, year, day),
            ).fetchone(),
            tuple[Optional[str]],
            "no inputs row exists for this session_label,year,day combination, even though we got a session_label from it earlier",
        )

        if known_answer is not None:
            correct = known_answer == answer

            if not correct:
                self._cursor.execute(
                    "UPDATE submissions SET valid = 0 WHERE submission_id = ?", (submission_id,)
                )

            return correct

        return None

    def process_submission_average_time(self, submission_id: SubmissionId, /) -> bool:
        """
        Processes a submissions average time based on all benched results,
        updating the submissions table in the database, this will also update best_runs

        This should be called once all benchmarks for this submission have completed
        Returns a bool indicating whether this run was valid, and thus considered for the leaderboard
        """

        # assumption: floats/REALs have a mantissa of 53 bits, we lock submissions to a max of 1s
        # 1s is approximately 40 bits, therefore we lose no single picosecond precision in
        # this calculation. Even if we did lose some precision, that is ok because we only
        # care about the most significant parts of the benchmark result anyways, i/e if
        # two solutions are taking 100s of microseconds each, its not changing much if
        # the picoseconds are not perfect, in this way floats are well suited to what we are doing
        valid_i, user, year, day_part = _unwrap(
            self._cursor.execute(
                "UPDATE submissions SET average_time = CAST(result AS INTEGER) "
                + "FROM ( SELECT AVG(CAST(average_time AS REAL)) AS result, submission FROM benchmark_runs WHERE (submission = ?) ) "
                + "WHERE submission_id = submission "
                + "RETURNING valid, user, year, day_part",
                (submission_id,),
            ).fetchone(),
            tuple[int, str, int, int],
            "process_submission_average_time was called, but there were no benchmark_run entries for this submission",
        )

        valid = bool(valid_i)

        if valid:
            # mypy is unable to read the _unwrap tuple definition, and thinks our day_part is unknown
            day, part = unpack_day_part(day_part)  # type: ignore[arg-type]
            # mypy is unable to read the _unwrap tuple definition, and thinks our year/user is unknown
            self.refresh_user_best_runs(year, day, part, user)  # type: ignore[arg-type]

        return valid

    def refresh_user_best_runs(
        self, year: Year, day: AdventDay, part: AdventPart, user_id: int
    ) -> None:
        """
        Flushes the best_runs table for a given user and year-day-part, used when inserting new entries or when marking submissions invalid
        """
        self._cursor.execute(
            "REPLACE INTO best_runs "
            + "SELECT user, year, day_part, MIN(average_time) AS best_time, submission_id AS run_id FROM submissions "
            + "WHERE (year = ? AND day_part = ? AND valid = 1 AND user = ?)",
            (year, pack_day_part(day, part), user_id),
        )

    def save_results(
        self,
        author_id: int,
        year: Year,
        day: AdventDay,
        part: AdventPart,
        code: bytes,
        container_version: ContainerVersionId,
        benchmark_format: int,
        results: list["RunResult"],
        /,
    ) -> None:
        """
        Save the benchmark run results to the DB.

        Legacy API, future code should call save_submission,
        asynchronously save_bench_result for each bench,
        and then finish with process_submission_average_time
        """

        id = self.save_submission(
            author_id, year, day, part, code, container_version, benchmark_format
        )

        for res in results:
            self.save_bench_result(id, res.from_session, res.median, str(res.answer))

        self.process_submission_average_time(id)

    def best_times(
        self, year: Year, day: AdventDay, part: AdventPart, /
    ) -> Iterator[tuple[int, Picoseconds]]:
        """Gets the best times for a given day/part, returning a user_id+timestamp in sorted by lowest time first order"""

        # this will probably stay the same, it is a cache anyways
        query = "SELECT user, best_time FROM best_runs WHERE (year = ? AND day_part = ?) ORDER BY best_time"

        return (
            (int(user), Picoseconds(time))
            for user, time in self._cursor.execute(query, (year, pack_day_part(day, part)))
        )

    def insert_input(
        self, session_label: SessionLabel, year: Year, day: AdventDay, input_data: str
    ) -> None:
        """
        Inserts an input into the database, input data is required to be passed as a utf8str
        because all AOC inputs are valid UTF8 (and valid ascii for that matter)
        """

        comp_input = gzip.compress(input_data.encode("utf8"))

        self._cursor.execute(
            "INSERT INTO inputs (year, day, session_label, input) VALUES (?, ?, ?, ?)",
            (year, day, session_label, comp_input),
        )

    def get_inputs(self, year: Year, day: AdventDay) -> dict[SessionLabel, AocInput]:
        """
        Returns all inputs stored in the database for the given day
        """

        return {
            SessionLabel(label): AocInput(
                year, day, SessionLabel(label), gzip.decompress(data).decode("utf8"), p1, p2
            )
            for label, data, p1, p2 in self._cursor.execute(
                "SELECT session_label, input, answer_p1, answer_p2 FROM inputs WHERE (year = ? AND day = ?)",
                (year, day),
            )
        }

    def get_user_submissions(
        self, year: Year, day: AdventDay, part: AdventPart, user_id: int, /
    ) -> list[Submission]:
        out = []

        for (
            id,
            avg_time,
            code,
            valid,
            submitted_at,
            bencher_version,
            benchmark_format,
        ) in self._cursor.execute(
            "SELECT submission_id, average_time, code, valid, submitted_at, bencher_version, benchmark_format FROM submissions WHERE (year = ? AND day_part = ? AND user = ?)",
            (year, pack_day_part(day, part), str(user_id)),
        ):
            benches = list[BenchmarkRun](
                BenchmarkRun(
                    id, Picoseconds(average_time), label, answer, dt_from_unix(completed_at)
                )
                for label, average_time, answer, completed_at in self._cursor.execute(
                    "SELECT session_label, average_time, answer, completed_at FROM benchmark_runs WHERE (submission = ?)",
                    (id,),
                )
            )

            out.append(
                Submission(
                    id,
                    user_id,
                    year,
                    day,
                    part,
                    Picoseconds(avg_time) if avg_time is not None else None,
                    gzip.decompress(code).decode("utf8"),
                    valid,
                    dt_from_unix(submitted_at),
                    ContainerVersionId(bencher_version),
                    int(benchmark_format),
                    benches,
                )
            )

        return out

    def get_submission_by_id(self, id: SubmissionId, /) -> Optional[Submission]:
        if (
            res := self._cursor.execute(
                "SELECT year, day_part, user, average_time, code, valid, submitted_at, bencher_version, benchmark_format FROM submissions WHERE (submission_id = ?)",
                (id,),
            ).fetchone()
        ) is not None:
            (
                year,
                day_part,
                user_id,
                avg_time,
                code,
                valid,
                submitted_at,
                bencher_version,
                benchmark_format,
            ) = res

            benches = list[BenchmarkRun](
                BenchmarkRun(
                    id, Picoseconds(average_time), label, answer, dt_from_unix(completed_at)
                )
                for label, average_time, answer, completed_at in self._cursor.execute(
                    "SELECT session_label, average_time, answer, completed_at FROM benchmark_runs WHERE (submission = ?)",
                    (id,),
                )
            )

            day, part = unpack_day_part(day_part)

            return Submission(
                id,
                user_id,
                year,
                day,
                part,
                Picoseconds(avg_time) if avg_time is not None else None,
                gzip.decompress(code).decode("utf8"),
                valid,
                dt_from_unix(submitted_at),
                ContainerVersionId(bencher_version),
                int(benchmark_format),
                benches,
            )

        return None

    def mark_submission_invalid(self, submission_id: SubmissionId, /) -> None:
        """
        Marks a submission invalid, also removes from best_runs table if it existed there
        """
        if (
            res := self._cursor.execute(
                "UPDATE submissions SET valid = 0 WHERE submission_id = ? RETURNING year, day_part, user",
                (submission_id,),
            ).fetchone()
        ) is not None:
            year, day_part, user = res

            day, part = unpack_day_part(day_part)

            self.refresh_user_best_runs(year, day, part, user)

    def insert_container_version(
        self,
        rustc_ver: str,
        container_version: str,
        bench_dir: bytes,
        timestamp: Optional[int] = None,
        /,
    ) -> ContainerVersionId:
        if timestamp is None:
            if "." in container_version:
                timestamp = int(container_version.split(".")[1])
            else:
                timestamp = int(container_version)

        id = self._cursor.execute(
            "INSERT INTO container_versions (rustc_version, container_version, bench_directory, timestamp) VALUES (?, ?, ?, ?)",
            (rustc_ver, container_version, bench_dir, timestamp),
        ).lastrowid

        assert id is not None
        return ContainerVersionId(id)

    def in_guild(self, guild_id: int, /) -> GuildDatabase:
        return GuildDatabase(self, guild_id)
