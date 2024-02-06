import json
import logging
import os
import pathlib
import shutil
import statistics as stats
import tempfile
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional, cast, Self
from zoneinfo import ZoneInfo

import docker
import discord
from discord.ext import commands

from config import settings
import constants
from database import (
    AdventDay,
    AdventPart,
    AocInput,
    Database,
    Picoseconds,
    SessionLabel,
    Submission,
    SubmissionId,
    Year,
)
from ferris_elf.runner import run_cmd

logger = logging.getLogger(__name__)


async def benchmark(
    ctx: commands.Context[Any],
    year: Year,
    day: AdventDay,
    part: AdventPart,
    code: bytes,
) -> None:
    """Run the entire benchmark process, end-to-end."""
    op_name, op_id = ctx.author.name, ctx.author.id

    try:
        results = []

        with Database() as db:
            (version_id, container_tag) = db.newest_container_version(
                constants.SUPPORTED_BENCH_FORMAT
            )

        with tempfile.TemporaryDirectory(suffix=f"-ferris-elf-{op_id}") as tmpdir:
            populate_tmp_dir(tmpdir, code)
            if not await build_code(container_tag, op_name, op_id, tmpdir):
                # This reply is not good UX, but it's better than silence.
                await ctx.reply("Build failed.")
                return

            with Database() as db:
                answers_map = db.load_answers(year, day, part)

                for in_file, contents in db.get_inputs(year, day).items():
                    logger.info("Processing file: %s", in_file)
                    load_input(tmpdir, contents)
                    result_lst = await run_code(container_tag, op_name, op_id, tmpdir, in_file)
                    result = process_run_result(in_file, answers_map, result_lst)
                    if result is not None:
                        results.append(result)

                db.save_results(
                    op_id,
                    year,
                    day,
                    part,
                    code,
                    version_id,
                    constants.SUPPORTED_BENCH_FORMAT,
                    results,
                )

        verified_results = [r for r in results if r.verified]
        if len(verified_results) > 0:
            median = stats.mean([r.median for r in verified_results])
            average = stats.mean([r.average for r in verified_results])
            await ctx.reply(
                embed=discord.Embed(
                    title="Benchmark complete (Verified)",
                    description=f"Median: **{median}**\nAverage: **{average}**",
                )
            )
        else:
            median = stats.mean([r.median for r in results])
            average = stats.mean([r.average for r in results])
            await ctx.reply(
                embed=discord.Embed(
                    title="Benchmark complete (Unverified)",
                    description=f"Median: **{median}**\nAverage: **{average}**",
                )
            )

    except Exception:
        logger.exception(f"Unhandled exception while benchmarking day {day}, part {part}.")
        await ctx.reply(f"Unhandled exception while benchmarking day {day}, part {part}.")


def populate_tmp_dir(tmp_dir: str, solution_code: bytes) -> None:
    """
    Set up tmp_dir for building. This copies in the runner and submitted code,
    but not the AOC inputs. We'll read those later.
    """
    logger.info("Building temp dir to use as volume")
    # Step 1: Copy all the rust files
    script_dir = os.path.dirname(__file__)
    runner_src_dir = os.path.join(script_dir, "runner")
    # The ignores were causing problems with building
    # ignores = shutil.ignore_patterns("target/", "Dockerfile", "**/.gitkeep")
    ignores = shutil.ignore_patterns()
    shutil.copytree(runner_src_dir, tmp_dir, dirs_exist_ok=True, ignore=ignores)

    # Step 2: Write code.
    code_path = os.path.join(tmp_dir, "src", "code.rs")
    with open(code_path, "wb") as code_file:
        code_file.write(solution_code)

    logger.debug("Contents of tmp dir: %s", os.listdir(tmp_dir))


async def build_code(
    container_version: str, author_name: str, author_id: int, tmp_dir: str
) -> bool:
    """
    Designed to be used with a basic rust container. Run the container
    with `cargo build` to build the code. Code is mounted in as a volume,
    so that binaries are saved between build/run.
    """
    logger.info("Running container to build code for %s", author_id)
    image = settings.docker.container_ref
    if ":" not in image:
        image = image + ":" + container_version
    try:
        out = await run_cmd(
            image,
            "timeout --kill-after=5s 90s cargo build --release",
            {},
            vols={
                os.path.join(tmp_dir, "src"): {"bind": "/app/src", "mode": "rw"},
                os.path.join(tmp_dir, "benches"): {"bind": "/app/benches", "mode": "rw"},
                os.path.join(tmp_dir, "target"): {"bind": "/app/target", "mode": "rw"},
            },
        )
        logger.debug("Build container output: %s", out)
        return True
    except docker.errors.ContainerError:
        logger.exception("Error in docker while building code")
        return False


def load_input(tmp_dir: str, input_data: AocInput) -> None:
    """
    Populate tmp_dir with the input files for the requested year/day.
    """
    container_inputs_path = os.path.join(tmp_dir, "inputs")

    # Step 1: Clear out anything there

    for path in pathlib.Path(container_inputs_path).glob("**/*"):
        if path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)

    for path in pathlib.Path(container_inputs_path).glob("**/.*"):
        if path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)

    # Step 2: Copy the appropriate file.

    with open(os.path.join(container_inputs_path, input_data.label), "w") as fp:
        fp.write(input_data.data)


async def run_code(
    container_version: str, author_name: str, author_id: int, tmp_dir: str, in_file: SessionLabel, /
) -> Optional[list[dict[str, Any]]]:
    """
    Designed to be used with a basic rust container. Given the code already
    built in tmp_dir as a volume, run the benchmark itself.
    """
    in_file_name = os.path.join("/app", "inputs", in_file)
    logger.info("Running container to run code for %s", author_id)
    image = settings.docker.container_ref
    if ":" not in image:
        image = image + ":" + container_version
    try:
        out = await run_cmd(
            image,
            "timeout --kill-after=15s 120s cargo criterion --message-format=json",
            env={
                "FERRIS_ELF_INPUT_FILE_NAME": in_file_name,
            },
            vols={
                os.path.join(tmp_dir, "src"): {"bind": "/app/src", "mode": "rw"},
                os.path.join(tmp_dir, "benches"): {"bind": "/app/benches", "mode": "rw"},
                os.path.join(tmp_dir, "inputs"): {"bind": "/app/inputs", "mode": "rw"},
                os.path.join(tmp_dir, "target"): {"bind": "/app/target", "mode": "rw"},
            },
        )
        logger.debug("Run container output (type: %s):\n%s", type(out), out)
        results = list[dict[str, Any]]()

        for line in out.splitlines():
            if len(line) == 0 or line[0] != "{":
                continue
            l_data = json.loads(line)
            results.append(l_data)

        logger.debug(
            "Results from container run for user %s, file %s: %s", author_id, in_file, results
        )
        return results
    except docker.errors.ContainerError:
        logger.exception("Error in docker while running code")
        return None


@dataclass(slots=True)
class BuildRunResult:
    """Dataclass to build summary of a benchmarking run."""

    answer: int | str
    verified: bool
    # These are optional because defaulting to zero seems like a bad idea.
    # these times are all in nanosecond scale
    typical: Optional[float]
    average: Optional[float]
    median: Optional[float]
    high_bound: Optional[float]
    low_bound: Optional[float]


def from_ns(v: Optional[float]) -> Picoseconds:
    assert v is not None, "got none value while attempting conversion to Picoseconds"
    return Picoseconds.from_nanos(v)


@dataclass(slots=True)
class RunResult:
    """Dataclass with a summary of a benchmarking run."""

    answer: int | str
    verified: bool
    typical: Picoseconds
    average: Picoseconds
    median: Picoseconds  # this is the one we put in the database
    high_bound: Picoseconds
    low_bound: Picoseconds
    from_session: SessionLabel

    @classmethod
    def from_builder_and_session(cls, b: BuildRunResult, session: SessionLabel) -> Self:
        typical, average, median, high_bound, low_bound = map(
            from_ns, [b.typical, b.average, b.median, b.high_bound, b.low_bound]
        )

        return cls(
            answer=b.answer,
            verified=b.verified,
            typical=typical,
            average=average,
            median=median,
            high_bound=high_bound,
            low_bound=low_bound,
            from_session=session,
        )


def process_run_result(
    in_file: SessionLabel,
    answers_map: dict[SessionLabel, str],
    result_lst: Optional[list[dict[str, Any]]],
) -> Optional[RunResult]:
    """Given JSON blobs extracted from a container's stdout, get the core stats out."""
    result = BuildRunResult(
        answer="",
        verified=False,
        typical=None,
        average=None,
        median=None,
        high_bound=None,
        low_bound=None,
    )

    if result_lst is None:
        logger.info("No run result due to lack of container output. Did the container error out?")
        return None
    for blob in result_lst:
        reason = blob.get("reason", None)
        if reason is None:
            continue
        elif reason == "ferris-answer":
            answer = blob["answer"]
            result.answer = answer
            if answers_map.get(in_file, None) == answer:
                result.verified = True
            else:
                result.verified = False
        elif reason == "benchmark-complete":
            result.typical = blob["typical"]["estimate"]
            result.average = blob["mean"]["estimate"]
            result.median = blob["median"]["estimate"]
            result.high_bound = blob["typical"]["upper_bound"]
            result.low_bound = blob["typical"]["lower_bound"]
    logger.info("Computed run result: %s", result)
    return RunResult.from_builder_and_session(result, in_file)


def get_best_times(
    cur_year: Year, day: AdventDay
) -> tuple[list[tuple[int, str]], list[tuple[int, str]]]:
    """
    Get the current contents of the leaderboard for the given day. Results are returned as a
    tuple of lists, first for Part 1, then for Part 2. Each list is of (user_id, formatted_time).
    """

    with Database() as db:
        times1 = [(user, str(time)) for user, time in db.best_times(cur_year, day, 1)]
        times2 = [(user, str(time)) for user, time in db.best_times(cur_year, day, 2)]

    return (times1, times2)


def invalidate_submission(submission_id: SubmissionId) -> Submission:
    """Mark a submission as invalid, and shouldn't be on the leaderboard."""
    with Database() as db:
        submission = db.get_submission_by_id(submission_id)
        if submission is None:
            logger.error("Asked to invalidate submission %s, but not found.", submission_id)
            raise KeyError("Invalid submission.")
        db.mark_submission_invalid(submission_id)

    return submission


def year() -> Year:
    """Return the current year, as AOC code should understand it."""
    # Our day-change happens at the same time as AOC. So, there's no point in
    # changing the season until 12am Dec 1.
    stamp = datetime.now(tz=ZoneInfo("America/New_York"))
    if stamp.month == 12:
        return Year(stamp.year)
    else:
        return Year(stamp.year - 1)


def today() -> AdventDay:
    """Return the current day, as AOC code should understand it."""
    # Our day-change happens at the same time as AOC. So, there's no point in
    # changing the season until 12am Dec 1.
    stamp = datetime.now(tz=ZoneInfo("America/New_York"))
    if stamp.month == 12:
        day = min(stamp.day, constants.MAX_DAY)
        # Satisfy the type-checker
        assert day > 0
        return cast(AdventDay, day)
    else:
        return constants.MAX_DAY
