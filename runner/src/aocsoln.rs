/// This is the interface between user solutions and our benchmarks.
/// Solutions must implement this trait
pub trait AOCSolution {
    fn aoc_part1(raw_input: &[u8]) -> String;
    fn aoc_part2(raw_input: &[u8]) -> String;
}
