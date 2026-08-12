//! Unsquare interpreter (Rust cross-check; see README "Extra
//! Implementations").
//!
//! A stack-based language with an accumulator.  `O`/`I` push 0/1, `A` pops
//! the stack into the accumulator, `S` swaps the top two, `+`/`-`/`x` add
//! 2/subtract 2/double the accumulator, `P` pushes it, `o` prints the top of
//! the stack as a byte (or a decimal value when it is not a valid
//! character), `i` reads a line of input pushing its first character, and
//! `>`/`<` are a loop bracket pair: `>` jumps forward to the matching `<`
//! when the accumulator is 0 or 1, and `<` jumps back to the matching `>`
//! when it is not 0 nor 1.
//! Error handling: popping an empty stack or an unmatched `<` panics (an
//! invalid operation).  `i` re-prompts until it reads a non-blank line.
//!
//! Invocation: `unsquare <program-file>`; program text from `argv[1]`.
//! Input: the program file is `argv[1]`; `i` reads from stdin.

use core::fmt::Display;
use std::char;
use std::env;
use std::fs;
use std::io::{self, Write};

fn print<T: Display>(value: T) {
    print!("{}", value);
    io::stdout().flush().unwrap();
}

fn run(text: Vec<char>) {
    let mut stk = Vec::new();
    let mut jmp = Vec::new();
    let mut out = false;
    let mut ind = 0;
    let mut acc = 0;

    while ind < text.len() {
        match text[ind] {
            'O' => stk.push(0),
            'I' => stk.push(1),
            'A' => acc = stk.pop().expect("empty stack"),
            'S' => {
                let n = stk.len();
                stk.swap(n - 1, n - 2);
            }
            '+' => acc += 2,
            '-' => acc -= 2,
            'x' => acc *= 2,
            'P' => stk.push(acc),
            'o' => {
                out = true;
                let val = stk.last().expect("empty stack");

                if let Some(c) = char::from_u32(*val as u32) {
                    print(c);
                } else {
                    print(val);
                }
            }
            'i' => {
                let mut val = String::new();

                if out {
                    print('\n');
                    out = false;
                }

                while val.trim() == "" {
                    print("Input: ");
                    io::stdin().read_line(&mut val).unwrap();
                }

                stk.push(val.chars().next().unwrap() as i128);
            }
            '>' => {
                if acc == 0 || acc == 1 {
                    let mut num = 1;

                    while num > 0 {
                        ind += 1;

                        match text[ind] {
                            '>' => num += 1,
                            '<' => num -= 1,
                            _ => (),
                        }
                    }
                } else {
                    jmp.push(ind - 1);
                }
            }
            '<' => ind = jmp.pop().expect("missing bracket"),
            _ => (),
        }

        ind += 1;
    }
}

fn main() {
    let args: Vec<String> = env::args().collect();
    let text = fs::read_to_string(&args[1])
        .expect("invalid file")
        .chars()
        .collect();

    run(text);
}

#[cfg(test)]
mod tests {
    use std::io::Write;
    use std::process::{Command, Stdio};

    fn run_program(program: &str, stdin: &str) -> String {
        // the real binary reads its program from a file argument, like the CI
        // round-trip harness does; the file name is unique per test (an atomic
        // counter) so parallel tests do not clobber each other
        use std::sync::atomic::{AtomicU64, Ordering};

        static COUNTER: AtomicU64 = AtomicU64::new(0);
        let exe = std::env::current_exe()
            .expect("current exe")
            .parent()
            .unwrap()
            .parent()
            .unwrap()
            .join("unsquare");
        let dir = std::env::temp_dir();
        let path = dir.join(format!(
            "unsquare-test-{}-{}.txt",
            std::process::id(),
            COUNTER.fetch_add(1, Ordering::SeqCst)
        ));
        std::fs::write(&path, program).expect("write program");
        let mut child = Command::new(&exe)
            .arg(&path)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .spawn()
            .expect("failed to spawn");
        child
            .stdin
            .take()
            .unwrap()
            .write_all(stdin.as_bytes())
            .unwrap();
        let out = child.wait_with_output().unwrap();
        std::fs::remove_file(&path).ok();
        String::from_utf8(out.stdout).expect("non-utf8 output")
    }

    #[test]
    fn push_and_print_digit() {
        // I pushes 1, o prints the top of the stack as a byte (0x01)
        assert_eq!(run_program("Io", ""), "\u{1}");
    }

    #[test]
    fn accumulator_ops() {
        // I pushes 1, + makes acc 2, P pushes acc (2), o prints 0x02
        assert_eq!(run_program("I+Po", ""), "\u{2}");
        // acc starts 0, + + makes acc 4
        assert_eq!(run_program("++Po", ""), "\u{4}");
        // - makes acc -2, printed as "-2"
        assert_eq!(run_program("-Po", ""), "-2");
        // x doubles acc (0 stays 0)
        assert_eq!(run_program("xxPo", ""), "\u{0}");
    }

    #[test]
    fn swap_orders_stack() {
        // O pushes 0, I pushes 1, S swaps -> top is 0, o prints 0x00
        assert_eq!(run_program("OISo", ""), "\u{0}");
    }

    #[test]
    fn read_input_digit() {
        // i reads a line and pushes its first char, P pushes acc (0), so o
        // prints 0; the "Input: " prompt is part of stdout
        assert_eq!(run_program("iPo", "7\n"), "Input: \u{0}");
    }

    #[test]
    fn print_char_for_letter() {
        // 32 '+' ops make acc 64, P pushes, o prints '@'
        let plus = "+".repeat(32);
        assert_eq!(run_program(&(plus + "Po"), ""), "@");
    }

    #[test]
    fn loop_skips_when_acc_01() {
        // O > I < : acc 0, > sees acc==0 so skips to <, I runs, terminates
        assert_eq!(run_program("O>I<", ""), "");
    }
}
