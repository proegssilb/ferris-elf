use criterion::{black_box, criterion_group, criterion_main, Criterion};
use ferris_elf::code;
use pprof::criterion::{Output, PProfProfiler};

//note that criterion does not allow setting hard limits on bench time
//we have to enforce time limits outside - see the ./run_bench.sh script
pub fn all(c: &mut Criterion) {
    let input: &str = include_str!("../inputs/input1.txt");
    let mut group = c.benchmark_group("aoc_sub");

    group.bench_function("run", |b| b.iter(|| code::run(black_box(input.as_ref()))));
    group.finish();
}

criterion_group!(
    name=benches;
    config=Criterion::default().with_profiler(PProfProfiler::new(100, Output::Flamegraph(None)));
    targets=all);
criterion_main!(benches);
