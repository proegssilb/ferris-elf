CREATE TABLE IF NOT EXISTS "schema_migrations" (version varchar(128) primary key);
CREATE TABLE best_runs (
  user TEXT NOT NULL,
  year INTEGER NOT NULL,
  /* packing day and part into one int, this also happens to be efficient to unpack */
  day_part INTEGER NOT NULL,
  best_time INTEGER NOT NULL,
  run_id INTEGER NOT NULL REFERENCES submissions (submission_id),

  CONSTRAINT best_runs_index UNIQUE (year, day_part, best_time, user)
) STRICT;
CREATE TABLE submissions (
  submission_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
  user TEXT NOT NULL,
  year INTEGER NOT NULL,
  day_part INTEGER NOT NULL,
  /*
    used on leaderboard, ps resolution, this is an aggregate of benchmark_runs.average_time
    initially it is NULL before all benchmark_runs are complete
  */
  average_time INTEGER DEFAULT NULL,
  /* gzipped code submission */
  code BLOB NOT NULL,
  /* whether or not this run is considered valid, treated as bool */
  valid INTEGER NOT NULL DEFAULT ( 1 ),

  submitted_at INTEGER NOT NULL DEFAULT ( UNIXEPOCH() ),

  bencher_version INTEGER NOT NULL REFERENCES container_versions (id)
) STRICT;
CREATE INDEX submissions_index ON submissions (year, day_part, valid, user, average_time);
CREATE TABLE benchmark_runs (
  submission INTEGER NOT NULL REFERENCES submissions (submission_id),
  /* the session_label of the input that this was run on */
  session_label TEXT NOT NULL,
  average_time INTEGER NOT NULL,
  answer TEXT NOT NULL,
  completed_at INTEGER NOT NULL DEFAULT ( UNIXEPOCH() )
) STRICT;
CREATE INDEX benchmark_runs_index ON benchmark_runs (submission, session_label, answer);
CREATE TABLE inputs (
  year INTEGER NOT NULL,
  /* dont use day-part here since inputs are the same for one day */
  day INTEGER NOT NULL,
  /* provides an ordering of inputs per day */
  session_label TEXT NOT NULL,
  /* gzip compressed input */
  input BLOB NOT NULL,
  /* the validated answer is an optional row up until verified outputs are available */
  answer_p1 TEXT,
  answer_p2 TEXT,

  CONSTRAINT inputs_lookup UNIQUE (year, day, session_label)
) STRICT;
CREATE TABLE container_versions (
  id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
  /* rustc version used as output by `rustc --version` */
  rustc_version TEXT NOT NULL,
  container_version TEXT NOT NULL UNIQUE,
  /*
    a high level indicator of the benchmarking setup used,
    this should be incremented whenever the way the bencher
    benches code changes in a way that affects results
  */
  benchmark_format INTEGER NOT NULL,
  /*
    gzipped tar archive of the default bencher workspace, including
    Cargo.toml, Cargo.lock, and any rs files that were run
  */
  bench_directory BLOB NOT NULL
) STRICT;
CREATE TABLE guild_config (
  guild_id TEXT NOT NULL,
  config_name TEXT NOT NULL,
  config_value TEXT NOT NULL,

  CONSTRAINT single_guild_config UNIQUE (guild_id, config_name)
) STRICT;
CREATE TABLE wrong_answers (
  year INTEGER NOT NULL,
  day_part INTEGER NOT NULL,
  session_label TEXT NOT NULL,
  answer TEXT NOT NULL
) STRICT;
CREATE INDEX wrong_answers_cache ON wrong_answers (year, day_part, session_label, answer);
-- Dbmate schema migrations
INSERT INTO "schema_migrations" (version) VALUES
  ('20240108100950');
