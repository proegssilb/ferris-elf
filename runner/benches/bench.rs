use std::fs;
use std::env;
use criterion::{black_box, criterion_group, criterion_main, Criterion};
use ferris_elf::code;
use pprof::criterion::{Output, PProfProfiler};

//note that criterion does not allow setting hard limits on bench time
//we have to enforce time limits outside - see the ./run_bench.sh script
pub fn all(c: &mut Criterion) {
    let file_name: String = env::var("FERRIS_ELF_INPUT_FILE_NAME").unwrap_or("/app/inputs/input1.txt".to_owned());
    let input = fs::read_to_string(&file_name).expect(&format!("Failed to read file: {}", (&file_name)));
    let mut group = c.benchmark_group("aoc_sub");

    let answer = code::run(input.as_ref());
    println!(r#"{{"reason": "ferris-answer", "answer":"{}" }}"#, answer);

    group.bench_function("run", |b| b.iter(|| code::run(black_box(input.as_ref()))));
    group.finish();
}

criterion_group!(
    name=benches;
    config=Criterion::default().with_profiler(PProfProfiler::new(100, Output::Flamegraph(None)));
    targets=all);
criterion_main!(benches);
