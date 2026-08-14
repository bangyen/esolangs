//! Kak interpreter (Rust cross-check; see README "Extra Implementations").
//!
//! A one-bit-tape language: `!` advances the pointer and flips the current
//! bit, `<` moves the pointer left (a no-op at cell 0), and `?` is a
//! conditional skip: when the current bit is zero it consumes characters
//! until it has consumed one of `!`/`?`/`<`, skipping them all without
//! executing them.  Every other character is a no-op.  The tape starts as a
//! single zero cell with the pointer on it (which can never be flipped, since
//! `!` always advances before flipping), and there is no input command.
//!
//! After the program text has been read once, the whole tape is printed as a
//! bit string on its own line and execution restarts from the beginning while
//! the current bit is nonzero; the program therefore always runs at least
//! once, and the empty program prints `0`.
//!
//! The `?` skip is read on the fly exactly as the C++ reference did it: when
//! the current bit is zero the `?` consumes the character right after it; if
//! the program ends immediately there, the skip stops without error.
//! Otherwise the `?` keeps consuming characters while they are not
//! `!`/`?`/`<`.  The character that finally stops the skip (a `!`/`?`/`<`)
//! is consumed but not executed, so a skip effectively jumps to just past the
//! next command, and any `!`/`?`/`<` characters encountered along the way are
//! skipped as well.  A `?` that runs off the end of the program while
//! searching for a stopping character (after already consuming at least one
//! non-`!`/`?`/`<` character) exits with status 1, mirroring the reference's
//! EXIT_FAILURE.
//!
//! Invocation: `kak <program-file>`; program text from `argv[1]`.
//! Input: the program file is `argv[1]`; the language has no input command.

use std::env;
use std::fs;
use std::process;

fn run(text: Vec<char>) -> ! {
    let n = text.len();
    let mut tape: Vec<bool> = vec![false];
    let mut ptr = 0usize;

    loop {
        let mut i = 0usize;
        while i < n {
            match text[i] {
                '!' => {
                    ptr += 1;
                    if ptr == tape.len() {
                        tape.push(false);
                    }
                    tape[ptr] = !tape[ptr];
                }
                '?' if !tape[ptr] => {
                    if i + 1 < n {
                        i += 1;
                        while text[i] != '!' && text[i] != '?' && text[i] != '<' {
                            i += 1;
                            if i >= n {
                                process::exit(1);
                            }
                        }
                    }
                }
                '<' if ptr > 0 => ptr -= 1,
                _ => {}
            }
            i += 1;
        }
        let bits: String = tape
            .iter()
            .map(|bit| if *bit { '1' } else { '0' })
            .collect();
        println!("{bits}");
        if !tape[ptr] {
            process::exit(0);
        }
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
    use std::sync::atomic::{AtomicU64, Ordering};

    fn run_program(program: &str) -> String {
        static COUNTER: AtomicU64 = AtomicU64::new(0);
        let exe = std::env::current_exe()
            .expect("current exe")
            .parent()
            .unwrap()
            .parent()
            .unwrap()
            .join("kak");
        let path = std::env::temp_dir().join(format!(
            "kak-test-{}-{}.txt",
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
        child.stdin.take().unwrap().write_all(b"").unwrap();
        let out = child.wait_with_output().unwrap();
        std::fs::remove_file(&path).ok();
        String::from_utf8(out.stdout).expect("non-utf8 output")
    }

    #[test]
    fn empty_program_prints_a_single_zero() {
        assert_eq!(run_program(""), "0\n");
    }

    #[test]
    fn prints_the_tape_until_the_current_bit_clears() {
        // !<! flips cell 1, moves back, flips it again -> both cells 0
        assert_eq!(run_program("!<!"), "00\n");
    }

    #[test]
    fn repeats_while_the_current_bit_is_set() {
        // <!!< leaves cell 1 set after the first pass, then clears it
        assert_eq!(run_program("<!!<"), "011\n000\n");
    }
}
