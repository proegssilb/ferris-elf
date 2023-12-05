use criterion::{black_box, criterion_group, criterion_main, Criterion};
use ferris_elf::aocsoln::AOCSolution;
use ferris_elf::code;
use pprof::criterion::{Output, PProfProfiler};

//note that criterion does not allow setting hard limits on bench time
//we have to enforce time limits outside - see the ./run_bench.sh script
pub fn all(c: &mut Criterion) {
    let input: &str = include_str!("../inputs/input1.txt");
    let mut group = c.benchmark_group("part1");

    group.sample_size(10);

    group.bench_function("part1", |b| {
        b.iter(|| code::Soln::aoc_part1(black_box(input.as_bytes())))
    });
    group.bench_function("part2", |b| {
        b.iter(|| code::Soln::aoc_part2(black_box(input.as_bytes())))
    });
    group.finish();
}

criterion_group!(
    name=benches;
    config=Criterion::default().with_profiler(PProfProfiler::new(100, Output::Flamegraph(None)));
    targets=all);
criterion_main!(benches);
