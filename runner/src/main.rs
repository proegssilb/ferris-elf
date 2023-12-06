use ascii::{AsAsciiStr, AsciiStr};
mod code;
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
    let input_ascii: &AsciiStr = input.as_ascii_str().unwrap();
    let answer = code::run(input_ascii.as_ref()).to_string();
    println!("{}", answer);
}
