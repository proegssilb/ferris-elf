-- migrate:up

/*
  nobody should have anything precious in here
  we are not in prod yet, this is the easy way out
*/
DROP TABLE container_versions;

CREATE TABLE container_versions (
  id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
  /* rustc version used as output by `rustc --version` */
  rustc_version TEXT NOT NULL,
  container_version TEXT NOT NULL UNIQUE,

  /* removed benchmark_format */

  /*
    gzipped tar archive of the default bencher workspace, including
    Cargo.toml, Cargo.lock, and any rs files that were run
  */
  bench_directory BLOB NOT NULL,

  /* NOTE: this is the new field */
  creation_time INTEGER NOT NULL

) STRICT;


ALTER TABLE submissions ADD COLUMN benchmark_format INTEGER NOT NULL DEFAULT ( 0 );

-- migrate:down


DROP TABLE container_versions;

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


ALTER TABLE submissions DROP COLUMN benchmark_format;
