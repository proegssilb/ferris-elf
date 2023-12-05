mod aocsoln;
mod code;

use crate::aocsoln::AOCSolution;
trait IntoInput<T: Copy> {
    fn into_input(self) -> T;
}

impl<T: Copy> IntoInput<T> for T {
    fn into_input(self) -> T {
        self
    }
}

impl IntoInput<&[u8]> for Vec<u8> {
    fn into_input(self) -> &'static [u8] {
        self.leak()
    }
}

impl IntoInput<&str> for Vec<u8> {
    fn into_input(self) -> &'static str {
        std::str::from_utf8(self.leak()).unwrap()
    }
}

fn main() {
    //TODO: test that the answer is correct
    let input = std::fs::read("inputs/input1.txt").unwrap();
    let part1 = format!("{}", code::Soln::aoc_part1(&input));
    println!("Part 1 = {part1}");
    let part2 = format!("{}", code::Soln::aoc_part2(&input));
    println!("Part 2 = {part2}");
}
